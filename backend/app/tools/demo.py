"""Two demo tools that exercise the framework end to end.

These prove the base class works — a person-level tool with scope enforcement, and an
aggregate tool with k-anonymity. The real retrieval / network / trend catalogue lands
in P10–P13 on top of exactly this machinery.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.tools.base import Principal, Provenance, Tool, ToolDenied, ToolResult, sql_hash


class GetCaseParams(BaseModel):
    case_master_id: int = Field(..., description="The case_master_id (FIR) to fetch.")


class GetCaseTool(Tool):
    """Fetch one FIR with its parties. Person-level (returns names), so it is scoped to
    the caller's units and disabled for aggregate-only roles."""

    name = "get_case"
    description = "Fetch a single FIR by case_master_id, with its accused and victims."
    Params = GetCaseParams
    person_level = True

    _SQL = """
        SELECT c.case_master_id, c.crime_no, c.crime_registered_date, c.police_station_id,
               u.district_id, c.brief_facts
        FROM ksp.case_master c
        LEFT JOIN ksp.unit u ON u.unit_id = c.police_station_id
        WHERE c.case_master_id = :cid
    """

    def _run(self, principal: Principal, params: GetCaseParams, session: Session) -> ToolResult:
        row = session.execute(text(self._SQL), {"cid": params.case_master_id}).mappings().first()
        if row is None:
            raise ToolDenied(f"case {params.case_master_id} not found")

        self.assert_unit_in_scope(principal, row["police_station_id"], session)

        accused = (
            session.execute(
                text(
                    "SELECT accused_master_id, accused_name FROM ksp.accused "
                    "WHERE case_master_id = :cid"
                ),
                {"cid": params.case_master_id},
            )
            .mappings()
            .all()
        )

        data = {
            "case_master_id": row["case_master_id"],
            "crime_no": row["crime_no"],
            "registered": str(row["crime_registered_date"]),
            "district_id": row["district_id"],
            "brief_facts": row["brief_facts"],
            "accused": [dict(a) for a in accused],
        }
        return ToolResult(
            data=data,
            provenance=Provenance(
                sql_hash=sql_hash(self._SQL, {"cid": params.case_master_id}),
                row_ids=[row["case_master_id"]],
                crime_nos=[row["crime_no"]] if row["crime_no"] else [],
            ),
        )


class CaseCountParams(BaseModel):
    crime_major_head_id: int | None = Field(
        None, description="Optional crime head id to filter by."
    )


class CaseCountByDistrictTool(Tool):
    """Case counts per district. Aggregate + k-anonymised for analyst/policymaker, and
    scoped to the caller's units for operational roles."""

    name = "case_count_by_district"
    description = "Count registered cases grouped by district, optionally by crime head."
    Params = CaseCountParams
    aggregate = True
    count_field = "cases"

    def _run(self, principal: Principal, params: CaseCountParams, session: Session) -> ToolResult:
        scope_sql, scope_params = self.scope_clause(principal, session, "c.police_station_id")
        head_sql = ""
        bind = dict(scope_params)
        if params.crime_major_head_id is not None:
            head_sql = " AND c.crime_major_head_id = :head"
            bind["head"] = params.crime_major_head_id

        sql = (
            "SELECT u.district_id, d.district_name, count(*) AS cases "
            "FROM ksp.case_master c "
            "JOIN ksp.unit u ON u.unit_id = c.police_station_id "
            "JOIN ksp.district d ON d.district_id = u.district_id "
            "WHERE 1=1" + scope_sql + head_sql + " "
            "GROUP BY u.district_id, d.district_name ORDER BY cases DESC"
        )
        rows = session.execute(text(sql), bind).mappings().all()
        data = [
            {
                "district_id": r["district_id"],
                "district_name": r["district_name"],
                "cases": r["cases"],
            }
            for r in rows
        ]
        return ToolResult(
            data=data,
            provenance=Provenance(
                sql_hash=sql_hash(sql, bind),
                row_ids=[r["district_id"] for r in rows],
                crime_nos=[],
            ),
        )


def build_default_registry():
    """A registry with the demo tools registered — a stand-in until P10+ populate the
    real catalogue."""
    from app.tools.base import ToolRegistry

    registry = ToolRegistry()
    registry.register(GetCaseTool())
    registry.register(CaseCountByDistrictTool())
    return registry
