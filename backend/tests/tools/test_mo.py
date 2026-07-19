"""P15 tests — MO fingerprinting pipeline + the two MO tools.

The pipeline is tested on a subsample (HDBSCAN on the full 50k is an offline job). The tools
are tested against whatever `python -m ml.mo` persisted; if MO hasn't been computed they are
skipped rather than failing, so the suite is green on a fresh DB.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db import SessionLocal
from app.tools.base import Principal, Role, ToolDenied
from app.tools.catalog import build_registry
from app.tools.mo import FindSimilarCasesTool, GetMoClusterTool
from ml.mo.fingerprint import _romanise, fit_clusters


@pytest.fixture()
def session():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


ANALYST = Principal(name="scrb", role=Role.SCRB_ANALYST)


def _mo_ready(session) -> bool:
    return session.execute(text("SELECT count(*) FROM derived.mo_cluster")).scalar_one() > 0


# --- pipeline ----------------------------------------------------------------


def test_romanise_transliterates_kannada_only():
    assert _romanise("gold chain snatched") == "gold chain snatched"  # roman passes through
    out = _romanise("ಚಿನ್ನದ ಸರ")
    assert out and out != "ಚಿನ್ನದ ಸರ"  # kannada script was romanised


def test_fit_clusters_finds_structure_on_a_subsample(session):
    rows = session.execute(
        text(
            "SELECT case_master_id, brief_facts FROM ksp.case_master "
            "WHERE brief_facts IS NOT NULL LIMIT 3000"
        )
    ).mappings().all()
    cases = [{"case_master_id": r["case_master_id"], "text": _romanise(r["brief_facts"]),
              "cs_type": None} for r in rows]
    emb, labels, meta = fit_clusters(cases, min_cluster_size=30, min_samples=8)
    assert emb.shape == (len(cases), 128)
    # at least a few interpretable clusters, each with distinguishing terms
    assert len(meta) >= 3
    assert all(m["top_terms"] for m in meta)


# --- tools (skip if MO not yet computed) -------------------------------------


def test_find_similar_cases_returns_outcomes(session):
    if not _mo_ready(session):
        pytest.skip("MO clustering not computed (run `python -m ml.mo`)")
    cid = session.execute(
        text("SELECT case_master_id FROM derived.case_mo_assignment LIMIT 1")
    ).scalar_one()
    result = FindSimilarCasesTool().run(ANALYST, {"case_master_id": cid, "limit": 10}, session)
    assert "summary" in result.data
    assert result.data["count"] <= 10
    valid = {"chargesheeted", "false case", "undetected", "open"}
    for s in result.data["similar_cases"]:
        assert s["outcome"] in valid
        assert 0.0 <= s["similarity"] <= 1.0
    # sorted by similarity descending (nearest first)
    sims = [s["similarity"] for s in result.data["similar_cases"]]
    assert sims == sorted(sims, reverse=True)


def test_get_mo_cluster_describes_pattern(session):
    if not _mo_ready(session):
        pytest.skip("MO clustering not computed")
    mid = session.execute(
        text("SELECT mo_cluster_id FROM derived.mo_cluster ORDER BY size DESC LIMIT 1")
    ).scalar_one()
    result = GetMoClusterTool().run(ANALYST, {"mo_cluster_id": mid}, session)
    assert result.data["distinguishing_terms"]
    assert result.data["size"] > 0
    o = result.data["outcomes"]
    assert {"chargesheeted", "false_case", "undetected", "open"} <= set(o)


def test_mo_tools_denied_when_not_computed_is_graceful(session):
    # if computed, this asserts a bogus id is a clean denial; if not, the not-ready denial
    with pytest.raises(ToolDenied):
        GetMoClusterTool().run(ANALYST, {"mo_cluster_id": 999999}, session)


def test_mo_tools_registered():
    names = {s["name"] for s in build_registry().anthropic_schemas()}
    assert {"get_mo_cluster", "find_similar_cases"} <= names
