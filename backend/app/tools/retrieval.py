"""Retrieval tools (P10) — tools 1–6 of PLAN.md §3.

get_case, search_cases, get_person, search_persons, get_case_timeline,
get_chargesheet_status. All on the P9 framework (RBAC / provenance / audit).

The one that matters most is **get_person**: it returns the resolved profile across
*every* linked FIR via ``derived.person_cluster`` — never by joining on
``accused_master_id``, which is a per-FIR row id, not a person. That join is the whole
point of the project, and doing it wrong is the single most damaging bug (CLAUDE.md).
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.tools.base import (
    Principal,
    Provenance,
    Tool,
    ToolDenied,
    ToolResult,
    sql_hash,
    units_in_scope,
)
from er.names import phonetic_key

# -----------------------------------------------------------------------------
# 1. get_case
# -----------------------------------------------------------------------------


class GetCaseParams(BaseModel):
    case_master_id: int | None = Field(None, description="The FIR's case_master_id.")
    crime_no: str | None = Field(None, description="The 18-digit CrimeNo, as an alternative.")

    @model_validator(mode="after")
    def _one_of(self):
        if self.case_master_id is None and not self.crime_no:
            raise ValueError("provide case_master_id or crime_no")
        return self


class GetCaseTool(Tool):
    name = "get_case"
    description = (
        "Fetch one FIR by case_master_id or crime_no: core details, acts/sections, "
        "parties (accused linked to their resolved person_cluster), and chargesheet status."
    )
    Params = GetCaseParams
    person_level = True

    def _run(self, principal: Principal, params: GetCaseParams, session: Session) -> ToolResult:
        where = (
            "c.case_master_id = :cid" if params.case_master_id is not None else "c.crime_no = :cno"
        )
        bind = {"cid": params.case_master_id, "cno": params.crime_no}
        case = (
            session.execute(
                text(
                    "SELECT c.case_master_id, c.crime_no, c.crime_registered_date, "
                    "c.police_station_id, u.district_id, u.unit_name AS station, "
                    "c.case_status_id, c.gravity_offence_id, c.crime_major_head_id, c.brief_facts "
                    "FROM ksp.case_master c "
                    "LEFT JOIN ksp.unit u ON u.unit_id = c.police_station_id "
                    f"WHERE {where}"
                ),
                bind,
            )
            .mappings()
            .first()
        )
        if case is None:
            raise ToolDenied("case not found")
        self.assert_unit_in_scope(principal, case["police_station_id"], session)
        cid = case["case_master_id"]

        # accused joined to their RESOLVED person (via person_cluster_member.source_row_id,
        # NOT by treating accused_master_id as a person id).
        accused = (
            session.execute(
                text(
                    "SELECT a.accused_master_id, a.accused_name, pcm.person_cluster_id, "
                    "       pcm.match_confidence "
                    "FROM ksp.accused a "
                    "LEFT JOIN derived.person_cluster_member pcm "
                    "  ON pcm.role = 'accused' AND pcm.source_row_id = a.accused_master_id "
                    "WHERE a.case_master_id = :cid"
                ),
                {"cid": cid},
            )
            .mappings()
            .all()
        )
        victims = (
            session.execute(
                text(
                    "SELECT victim_master_id, victim_name FROM ksp.victim "
                    "WHERE case_master_id = :cid"
                ),
                {"cid": cid},
            )
            .mappings()
            .all()
        )
        sections = (
            session.execute(
                text(
                    "SELECT act_code, section_code FROM ksp.act_section_association "
                    "WHERE case_master_id = :cid ORDER BY act_order_id"
                ),
                {"cid": cid},
            )
            .mappings()
            .all()
        )
        cs = (
            session.execute(
                text(
                    "SELECT cs_type, cs_date FROM ksp.chargesheet_details "
                    "WHERE case_master_id = :cid"
                ),
                {"cid": cid},
            )
            .mappings()
            .first()
        )

        data = {
            "case_master_id": cid,
            "crime_no": case["crime_no"],
            "registered": str(case["crime_registered_date"]),
            "station": case["station"],
            "district_id": case["district_id"],
            "crime_major_head_id": case["crime_major_head_id"],
            "heinous": case["gravity_offence_id"] == 1,
            "sections": [f"{s['act_code']} {s['section_code']}" for s in sections],
            "brief_facts": case["brief_facts"],
            "accused": [
                {
                    "accused_master_id": a["accused_master_id"],
                    "name": a["accused_name"],
                    "person_cluster_id": a["person_cluster_id"],
                    "resolution_confidence": float(a["match_confidence"])
                    if a["match_confidence"] is not None
                    else None,
                }
                for a in accused
            ],
            "victims": [
                {"victim_master_id": v["victim_master_id"], "name": v["victim_name"]}
                for v in victims
            ],
            "chargesheet": {"cs_type": cs["cs_type"], "cs_date": str(cs["cs_date"])}
            if cs
            else None,
        }
        return ToolResult(
            data=data,
            provenance=Provenance(
                sql_hash=sql_hash("get_case", {k: str(v) for k, v in bind.items()}),
                row_ids=[cid],
                crime_nos=[case["crime_no"]] if case["crime_no"] else [],
            ),
        )


# -----------------------------------------------------------------------------
# 2. search_cases
# -----------------------------------------------------------------------------


class SearchCasesParams(BaseModel):
    district_id: int | None = None
    station_id: int | None = None
    date_from: date | None = None
    date_to: date | None = None
    crime_major_head_id: int | None = None
    case_status_id: int | None = None
    gravity_offence_id: int | None = None
    act_code: str | None = None
    section_code: str | None = None
    limit: int = Field(50, ge=1, le=500)


class SearchCasesTool(Tool):
    name = "search_cases"
    description = (
        "Search FIRs by district, station, date range, crime head, status, gravity, or act/section."
    )
    Params = SearchCasesParams

    def _run(self, principal: Principal, params: SearchCasesParams, session: Session) -> ToolResult:
        scope_sql, bind = self.scope_clause(principal, session, "c.police_station_id")
        clauses = []
        if params.district_id is not None:
            clauses.append("u.district_id = :district")
            bind["district"] = params.district_id
        if params.station_id is not None:
            clauses.append("c.police_station_id = :station")
            bind["station"] = params.station_id
        if params.date_from is not None:
            clauses.append("c.crime_registered_date >= :dfrom")
            bind["dfrom"] = params.date_from
        if params.date_to is not None:
            clauses.append("c.crime_registered_date <= :dto")
            bind["dto"] = params.date_to
        if params.crime_major_head_id is not None:
            clauses.append("c.crime_major_head_id = :head")
            bind["head"] = params.crime_major_head_id
        if params.case_status_id is not None:
            clauses.append("c.case_status_id = :status")
            bind["status"] = params.case_status_id
        if params.gravity_offence_id is not None:
            clauses.append("c.gravity_offence_id = :grav")
            bind["grav"] = params.gravity_offence_id
        join_sec = ""
        if params.act_code is not None or params.section_code is not None:
            join_sec = (
                "JOIN ksp.act_section_association asa ON asa.case_master_id = c.case_master_id"
            )
            if params.act_code is not None:
                clauses.append("asa.act_code = :act")
                bind["act"] = params.act_code
            if params.section_code is not None:
                clauses.append("asa.section_code = :section")
                bind["section"] = params.section_code

        where = (" AND " + " AND ".join(clauses)) if clauses else ""
        bind["lim"] = params.limit
        sql = (
            "SELECT DISTINCT c.case_master_id, c.crime_no, c.crime_registered_date, "
            "u.district_id, u.unit_name AS station, c.crime_major_head_id, c.case_status_id "
            "FROM ksp.case_master c "
            "JOIN ksp.unit u ON u.unit_id = c.police_station_id " + join_sec + " "
            "WHERE 1=1" + scope_sql + where + " "
            "ORDER BY c.crime_registered_date DESC LIMIT :lim"
        )
        rows = session.execute(text(sql), bind).mappings().all()
        data = [
            {
                "case_master_id": r["case_master_id"],
                "crime_no": r["crime_no"],
                "registered": str(r["crime_registered_date"]),
                "station": r["station"],
                "district_id": r["district_id"],
                "crime_major_head_id": r["crime_major_head_id"],
                "case_status_id": r["case_status_id"],
            }
            for r in rows
        ]
        return ToolResult(
            data={"count": len(data), "cases": data},
            provenance=Provenance(
                sql_hash=sql_hash(sql, {k: str(v) for k, v in bind.items()}),
                row_ids=[r["case_master_id"] for r in rows],
                crime_nos=[r["crime_no"] for r in rows if r["crime_no"]],
            ),
        )


# -----------------------------------------------------------------------------
# 3. get_person — the resolved profile across ALL linked FIRs
# -----------------------------------------------------------------------------


class GetPersonParams(BaseModel):
    person_cluster_id: int = Field(..., description="The resolved person's cluster id.")


class GetPersonTool(Tool):
    name = "get_person"
    description = (
        "The resolved profile of one person across ALL their linked FIRs (via "
        "person_cluster, never accused_master_id), with resolution confidence."
    )
    Params = GetPersonParams
    person_level = True

    def _run(self, principal: Principal, params: GetPersonParams, session: Session) -> ToolResult:
        cluster = (
            session.execute(
                text(
                    "SELECT person_cluster_id, display_name, canonical_given, "
                "canonical_patronymic, "
                    "gender_id, est_birth_year, member_count, confidence "
                    "FROM derived.person_cluster WHERE person_cluster_id = :id"
                ),
                {"id": params.person_cluster_id},
            )
            .mappings()
            .first()
        )
        if cluster is None:
            raise ToolDenied(f"person_cluster {params.person_cluster_id} not found")

        members = (
            session.execute(
                text(
                    "SELECT pcm.role, pcm.source_row_id, pcm.case_master_id, pcm.raw_name, "
                    "       pcm.match_confidence, c.crime_no, c.crime_registered_date, "
                    "       c.police_station_id, u.district_id, u.unit_name AS station "
                    "FROM derived.person_cluster_member pcm "
                    "JOIN ksp.case_master c ON c.case_master_id = pcm.case_master_id "
                    "LEFT JOIN ksp.unit u ON u.unit_id = c.police_station_id "
                    "WHERE pcm.person_cluster_id = :id ORDER BY c.crime_registered_date"
                ),
                {"id": params.person_cluster_id},
            )
            .mappings()
            .all()
        )

        # RBAC: an operational principal sees only the FIRs within their scope. If none
        # of this person's FIRs are in scope, the person is not in their jurisdiction.
        scope = units_in_scope(principal, session)
        in_scope = [m for m in members if scope is None or m["police_station_id"] in scope]
        if not in_scope:
            raise ToolDenied(f"person_cluster {params.person_cluster_id} has no FIRs in your scope")
        hidden = len(members) - len(in_scope)

        data = {
            "person_cluster_id": cluster["person_cluster_id"],
            "display_name": cluster["display_name"],
            "canonical_given": cluster["canonical_given"],
            "canonical_patronymic": cluster["canonical_patronymic"],
            "gender_id": cluster["gender_id"],
            "est_birth_year": cluster["est_birth_year"],
            "total_linked_firs": cluster["member_count"],
            "cluster_confidence": float(cluster["confidence"]) if cluster["confidence"] else None,
            "firs_out_of_scope_hidden": hidden,
            "appearances": [
                {
                    "role": m["role"],
                    "case_master_id": m["case_master_id"],
                    "crime_no": m["crime_no"],
                    "registered": str(m["crime_registered_date"]),
                    "station": m["station"],
                    "district_id": m["district_id"],
                    "name_as_written": m["raw_name"],
                    "link_confidence": float(m["match_confidence"])
                    if m["match_confidence"]
                    else None,
                }
                for m in in_scope
            ],
        }
        return ToolResult(
            data=data,
            provenance=Provenance(
                sql_hash=sql_hash("get_person", {"id": params.person_cluster_id}),
                row_ids=[m["case_master_id"] for m in in_scope],
                crime_nos=[m["crime_no"] for m in in_scope if m["crime_no"]],
            ),
        )


# -----------------------------------------------------------------------------
# 4. search_persons
# -----------------------------------------------------------------------------


class SearchPersonsParams(BaseModel):
    name: str | None = Field(None, description="A name to match (phonetically + fuzzily).")
    gender_id: int | None = None
    birth_year: int | None = Field(None, description="Approximate birth year (+/- 3 tolerance).")
    limit: int = Field(25, ge=1, le=200)


class SearchPersonsTool(Tool):
    name = "search_persons"
    description = (
        "Find resolved persons by name (phonetic), gender, or approximate birth year, "
        "with confidence."
    )
    Params = SearchPersonsParams
    person_level = True

    def _run(
        self, principal: Principal, params: SearchPersonsParams, session: Session
    ) -> ToolResult:
        clauses, bind = [], {}
        if params.name:
            bind["pkey"] = phonetic_key(params.name.split()[0]) if params.name.split() else ""
            bind["like"] = f"%{params.name}%"
            clauses.append("(phonetic_key = :pkey OR display_name ILIKE :like)")
        if params.gender_id is not None:
            clauses.append("gender_id = :gender")
            bind["gender"] = params.gender_id
        if params.birth_year is not None:
            clauses.append("abs(est_birth_year - :by) <= 3")
            bind["by"] = params.birth_year
        where = (" AND " + " AND ".join(clauses)) if clauses else ""

        # scope: restrict to persons with at least one FIR in the caller's units
        scope = units_in_scope(principal, session)
        scope_sql = ""
        if scope is not None:
            scope_sql = (
                " AND person_cluster_id IN (SELECT pcm.person_cluster_id "
                "FROM derived.person_cluster_member pcm "
                "JOIN ksp.case_master c ON c.case_master_id = pcm.case_master_id "
                "WHERE c.police_station_id = ANY(:scope_units))"
            )
            bind["scope_units"] = list(scope) or [-1]

        bind["lim"] = params.limit
        sql = (
            "SELECT person_cluster_id, display_name, gender_id, est_birth_year, member_count, "
            "confidence FROM derived.person_cluster WHERE 1=1" + where + scope_sql + " "
            "ORDER BY member_count DESC, confidence DESC LIMIT :lim"
        )
        rows = session.execute(text(sql), bind).mappings().all()
        data = [
            {
                "person_cluster_id": r["person_cluster_id"],
                "display_name": r["display_name"],
                "gender_id": r["gender_id"],
                "est_birth_year": r["est_birth_year"],
                "linked_firs": r["member_count"],
                "cluster_confidence": float(r["confidence"]) if r["confidence"] else None,
            }
            for r in rows
        ]
        return ToolResult(
            data={"count": len(data), "persons": data},
            provenance=Provenance(
                sql_hash=sql_hash(sql, {k: str(v) for k, v in bind.items()}),
                row_ids=[r["person_cluster_id"] for r in rows],
                crime_nos=[],
            ),
        )


# -----------------------------------------------------------------------------
# 5. get_case_timeline
# -----------------------------------------------------------------------------


class CaseIdParams(BaseModel):
    case_master_id: int = Field(..., description="The FIR's case_master_id.")


class GetCaseTimelineTool(Tool):
    name = "get_case_timeline"
    description = (
        "The ordered investigation date chain for a case — incident, info received, "
        "registered, arrest(s), chargesheet — with the gap in days between each step."
    )
    Params = CaseIdParams

    def _run(self, principal: Principal, params: CaseIdParams, session: Session) -> ToolResult:
        case = (
            session.execute(
                text(
                    "SELECT case_master_id, crime_no, police_station_id, incident_from_date, "
                    "info_received_ps_date, crime_registered_date FROM ksp.case_master "
                    "WHERE case_master_id = :cid"
                ),
                {"cid": params.case_master_id},
            )
            .mappings()
            .first()
        )
        if case is None:
            raise ToolDenied("case not found")
        self.assert_unit_in_scope(principal, case["police_station_id"], session)

        arrests = session.execute(
            text(
                "SELECT MIN(arrest_surrender_date) AS first_arrest "
                "FROM ksp.arrest_surrender WHERE case_master_id = :cid"
            ),
            {"cid": params.case_master_id},
        ).scalar_one_or_none()
        cs = session.execute(
            text(
                "SELECT MIN(cs_date) AS cs FROM ksp.chargesheet_details WHERE case_master_id = :cid"
            ),
            {"cid": params.case_master_id},
        ).scalar_one_or_none()

        events = []
        for label, ts in (
            ("incident", case["incident_from_date"]),
            ("info_received", case["info_received_ps_date"]),
            ("registered", case["crime_registered_date"]),
            ("first_arrest", arrests),
            ("chargesheet", cs),
        ):
            if ts is not None:
                events.append({"event": label, "date": str(ts)})
        # compute gap in days from the previous event
        from datetime import datetime

        def as_dt(s):
            return datetime.fromisoformat(str(s)[:19]) if s else None

        for i, ev in enumerate(events):
            if i == 0:
                ev["gap_days_from_prev"] = None
            else:
                d0, d1 = as_dt(events[i - 1]["date"]), as_dt(ev["date"])
                ev["gap_days_from_prev"] = (d1.date() - d0.date()).days if d0 and d1 else None

        return ToolResult(
            data={
                "case_master_id": params.case_master_id,
                "crime_no": case["crime_no"],
                "timeline": events,
            },
            provenance=Provenance(
                sql_hash=sql_hash("get_case_timeline", {"cid": params.case_master_id}),
                row_ids=[params.case_master_id],
                crime_nos=[case["crime_no"]] if case["crime_no"] else [],
            ),
        )


# -----------------------------------------------------------------------------
# 6. get_chargesheet_status
# -----------------------------------------------------------------------------

_CS_TYPE = {"A": "Chargesheet filed", "B": "False case", "C": "Undetected", None: "Pending / open"}


class GetChargesheetStatusTool(Tool):
    name = "get_chargesheet_status"
    description = (
        "Whether a case has a chargesheet, its type (A/B/C), and the arrest-to-chargesheet gap."
    )
    Params = CaseIdParams

    def _run(self, principal: Principal, params: CaseIdParams, session: Session) -> ToolResult:
        case = (
            session.execute(
                text(
                    "SELECT case_master_id, crime_no, police_station_id, gravity_offence_id "
                    "FROM ksp.case_master WHERE case_master_id = :cid"
                ),
                {"cid": params.case_master_id},
            )
            .mappings()
            .first()
        )
        if case is None:
            raise ToolDenied("case not found")
        self.assert_unit_in_scope(principal, case["police_station_id"], session)

        cs = (
            session.execute(
                text(
                    "SELECT cs_type, cs_date FROM ksp.chargesheet_details "
                    "WHERE case_master_id = :cid ORDER BY cs_date LIMIT 1"
                ),
                {"cid": params.case_master_id},
            )
            .mappings()
            .first()
        )
        first_arrest = session.execute(
            text(
                "SELECT MIN(arrest_surrender_date) FROM ksp.arrest_surrender "
                "WHERE case_master_id = :cid"
            ),
            {"cid": params.case_master_id},
        ).scalar_one_or_none()

        cs_type = cs["cs_type"] if cs else None
        gap = None
        if cs and cs["cs_date"] and first_arrest:
            gap = (cs["cs_date"].date() - first_arrest).days
        data = {
            "case_master_id": params.case_master_id,
            "crime_no": case["crime_no"],
            "has_chargesheet": cs is not None,
            "cs_type": cs_type,
            "cs_type_meaning": _CS_TYPE.get(cs_type, "Unknown"),
            "cs_date": str(cs["cs_date"]) if cs else None,
            "first_arrest": str(first_arrest) if first_arrest else None,
            "arrest_to_chargesheet_days": gap,
        }
        return ToolResult(
            data=data,
            provenance=Provenance(
                sql_hash=sql_hash("get_chargesheet_status", {"cid": params.case_master_id}),
                row_ids=[params.case_master_id],
                crime_nos=[case["crime_no"]] if case["crime_no"] else [],
            ),
        )
