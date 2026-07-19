"""MO tools (P15) — the modus-operandi layer as tools the chat can call.

get_mo_cluster describes one derived MO pattern (label, distinguishing terms, and its outcome
mix). find_similar_cases is the useful one: given a case, it returns the nearest cases by MO
embedding (pgvector cosine) *with each one's cstype outcome*, plus a summary — "12 similar
cases, 8 were chargesheeted" — because the outcome mix is what tells an investigator whether
this pattern tends to get solved and how.

Both read ``derived.case_mo_assignment`` / ``derived.mo_cluster``, which ``python -m ml.mo``
populates. If MO clustering hasn't been run, the tools say so rather than failing.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.tools.base import Principal, Provenance, Tool, ToolDenied, ToolResult, sql_hash

_CS_MEANING = {"A": "chargesheeted", "B": "false case", "C": "undetected", None: "open"}


def _mo_ready(session: Session) -> bool:
    return session.execute(text("SELECT count(*) FROM derived.mo_cluster")).scalar_one() > 0


# -----------------------------------------------------------------------------
# get_mo_cluster
# -----------------------------------------------------------------------------


class GetMoClusterParams(BaseModel):
    mo_cluster_id: int = Field(..., description="The MO cluster id.")
    sample_size: int = Field(6, ge=1, le=25)


class GetMoClusterTool(Tool):
    name = "get_mo_cluster"
    description = (
        "Describe one derived modus-operandi pattern: its label, distinguishing terms, size, "
        "outcome (chargesheet/false/undetected) mix, and a few example cases in your scope."
    )
    Params = GetMoClusterParams

    def _run(
        self, principal: Principal, params: GetMoClusterParams, session: Session
    ) -> ToolResult:
        if not _mo_ready(session):
            raise ToolDenied("MO clustering has not been computed yet (run `python -m ml.mo`)")
        cl = session.execute(
            text(
                "SELECT mo_cluster_id, label, top_terms, size, cstype_a, cstype_b, cstype_c, "
                "cstype_open FROM derived.mo_cluster WHERE mo_cluster_id = :id"
            ),
            {"id": params.mo_cluster_id},
        ).mappings().first()
        if cl is None:
            raise ToolDenied(f"MO cluster {params.mo_cluster_id} not found")

        scope_sql, bind = self.scope_clause(principal, session, "c.police_station_id")
        bind.update({"id": params.mo_cluster_id, "lim": params.sample_size})
        samples = session.execute(
            text(
                "SELECT c.case_master_id, c.crime_no, cs.cs_type "
                "FROM derived.case_mo_assignment a "
                "JOIN ksp.case_master c ON c.case_master_id = a.case_master_id "
                "LEFT JOIN ksp.chargesheet_details cs ON cs.case_master_id = c.case_master_id "
                "WHERE a.mo_cluster_id = :id" + scope_sql + " LIMIT :lim"
            ),
            bind,
        ).mappings().all()

        data = {
            "mo_cluster_id": cl["mo_cluster_id"],
            "label": cl["label"],
            "distinguishing_terms": list(cl["top_terms"]),
            "size": cl["size"],
            "outcomes": {
                "chargesheeted": cl["cstype_a"],
                "false_case": cl["cstype_b"],
                "undetected": cl["cstype_c"],
                "open": cl["cstype_open"],
            },
            "examples": [
                {
                    "case_master_id": s["case_master_id"],
                    "crime_no": s["crime_no"],
                    "outcome": _CS_MEANING.get(s["cs_type"], "open"),
                }
                for s in samples
            ],
        }
        return ToolResult(
            data=data,
            provenance=Provenance(
                sql_hash=sql_hash("get_mo_cluster", {"id": params.mo_cluster_id}),
                row_ids=[s["case_master_id"] for s in samples],
                crime_nos=[s["crime_no"] for s in samples if s["crime_no"]],
            ),
        )


# -----------------------------------------------------------------------------
# find_similar_cases
# -----------------------------------------------------------------------------


class FindSimilarCasesParams(BaseModel):
    case_master_id: int | None = Field(None, description="The case to find neighbours of.")
    crime_no: str | None = None
    limit: int = Field(12, ge=1, le=100)

    @model_validator(mode="after")
    def _one_of(self):
        if self.case_master_id is None and not self.crime_no:
            raise ValueError("provide case_master_id or crime_no")
        return self


class FindSimilarCasesTool(Tool):
    name = "find_similar_cases"
    description = (
        "Given a case, find the most similar cases by modus operandi (MO embedding, cosine "
        "similarity) — each returned WITH its outcome, plus a summary of how many of the "
        "similar cases were chargesheeted vs undetected. Answers 'what usually happens with "
        "this kind of case'."
    )
    Params = FindSimilarCasesParams

    def _run(
        self, principal: Principal, params: FindSimilarCasesParams, session: Session
    ) -> ToolResult:
        if not _mo_ready(session):
            raise ToolDenied("MO clustering has not been computed yet (run `python -m ml.mo`)")

        seed = session.execute(
            text(
                "SELECT c.case_master_id, c.crime_no, c.police_station_id "
                "FROM ksp.case_master c WHERE "
                + (
                    "c.case_master_id = :cid"
                    if params.case_master_id is not None
                    else "c.crime_no = :cno"
                )
            ),
            {"cid": params.case_master_id, "cno": params.crime_no},
        ).mappings().first()
        if seed is None:
            raise ToolDenied("case not found")
        self.assert_unit_in_scope(principal, seed["police_station_id"], session)
        cid = seed["case_master_id"]

        has_emb = session.execute(
            text("SELECT 1 FROM derived.case_mo_assignment WHERE case_master_id = :cid"),
            {"cid": cid},
        ).first()
        if has_emb is None:
            raise ToolDenied("this case has no MO embedding (its BriefFacts may be empty)")

        scope_sql, bind = self.scope_clause(principal, session, "c.police_station_id")
        bind.update({"cid": cid, "lim": params.limit})
        rows = session.execute(
            text(
                "SELECT a.case_master_id, c.crime_no, u.district_id, cs.cs_type, "
                "       a.mo_cluster_id, "
                "       (a.embedding <=> (SELECT embedding FROM derived.case_mo_assignment "
                "                         WHERE case_master_id = :cid)) AS distance "
                "FROM derived.case_mo_assignment a "
                "JOIN ksp.case_master c ON c.case_master_id = a.case_master_id "
                "JOIN ksp.unit u ON u.unit_id = c.police_station_id "
                "LEFT JOIN ksp.chargesheet_details cs ON cs.case_master_id = a.case_master_id "
                "WHERE a.case_master_id <> :cid" + scope_sql + " "
                "ORDER BY a.embedding <=> (SELECT embedding FROM derived.case_mo_assignment "
                "                          WHERE case_master_id = :cid) "
                "LIMIT :lim"
            ),
            bind,
        ).mappings().all()

        similar = [
            {
                "case_master_id": r["case_master_id"],
                "crime_no": r["crime_no"],
                "district_id": r["district_id"],
                "outcome": _CS_MEANING.get(r["cs_type"], "open"),
                "mo_cluster_id": r["mo_cluster_id"],
                "similarity": round(1.0 - float(r["distance"]), 3),
            }
            for r in rows
        ]
        n = len(similar)
        chargesheeted = sum(1 for s in similar if s["outcome"] == "chargesheeted")
        undetected = sum(1 for s in similar if s["outcome"] == "undetected")
        summary = (
            f"{n} similar cases in scope: {chargesheeted} chargesheeted, {undetected} undetected, "
            f"{n - chargesheeted - undetected} other."
            if n
            else "No similar cases within your scope."
        )
        return ToolResult(
            data={"seed_crime_no": seed["crime_no"], "count": n, "summary": summary,
                  "similar_cases": similar},
            provenance=Provenance(
                sql_hash=sql_hash("find_similar_cases", {"cid": cid, "lim": params.limit}),
                row_ids=[s["case_master_id"] for s in similar],
                crime_nos=[s["crime_no"] for s in similar if s["crime_no"]],
            ),
        )
