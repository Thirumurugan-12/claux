"""P12 tests for the network tools, over the resolved-person co-offending graph.

Exercised against the loaded data + person_cluster. Fixtures pull a real co-offending pair
and a well-connected person so the graph logic and RBAC scope are tested against the actual
hierarchy, not a toy graph.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db import SessionLocal
from app.tools.base import Principal, Role, ToolDenied
from app.tools.catalog import build_registry
from app.tools.network import (
    DetectCommunitiesTool,
    FindShortestPathTool,
    GetPersonNetworkTool,
    GetRepeatOffendersTool,
    build_person_graph,
    get_person_graph,
    reset_person_graph,
)


@pytest.fixture()
def session():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(scope="module")
def graph():
    s = SessionLocal()
    try:
        reset_person_graph()
        return get_person_graph(s)
    finally:
        s.close()


@pytest.fixture()
def cooffender_pair(session):
    """Two resolved people arrested in the same event, and the district of that shared FIR."""
    row = (
        session.execute(
            text(
                "SELECT p.a AS a, p.b AS b, u.district_id AS district "
                "FROM ("
                "  SELECT j.arrest_surrender_id AS eid, "
                "         min(pcm.person_cluster_id) AS a, max(pcm.person_cluster_id) AS b, "
                "         min(pcm.case_master_id) AS cmid "
                "  FROM ksp.inv_arrest_surrender_accused j "
                "  JOIN derived.person_cluster_member pcm "
                "    ON pcm.role = 'accused' AND pcm.source_row_id = j.accused_master_id "
                "  GROUP BY j.arrest_surrender_id "
                "  HAVING count(DISTINCT pcm.person_cluster_id) >= 2"
                ") p JOIN ksp.case_master c ON c.case_master_id = p.cmid "
                "JOIN ksp.unit u ON u.unit_id = c.police_station_id LIMIT 1"
            )
        )
        .mappings()
        .first()
    )
    return dict(row)


def _sp(district):
    return Principal(name="sp", role=Role.SP, district_id=district)


# --- graph build -------------------------------------------------------------


def test_graph_has_person_nodes_and_cooffending_edges(graph):
    assert graph.number_of_nodes() > 1000
    assert graph.number_of_edges() > 0
    # every node carries the identity + jurisdiction metadata the tools rely on
    n0 = next(iter(graph.nodes))
    d = graph.nodes[n0]
    assert {"display_name", "firs", "stations", "districts"} <= set(d)


def test_cooffending_edge_exists_for_a_real_pair(graph, cooffender_pair):
    assert graph.has_edge(cooffender_pair["a"], cooffender_pair["b"])
    assert graph[cooffender_pair["a"]][cooffender_pair["b"]]["weight"] >= 1


def test_cache_is_reused(session):
    reset_person_graph()
    g1 = get_person_graph(session)
    g2 = get_person_graph(session)
    assert g1 is g2  # second call returns the cached instance, not a rebuild


# --- get_person_network ------------------------------------------------------


def test_person_network_returns_cytoscape_ego_graph(session, cooffender_pair):
    sp = _sp(cooffender_pair["district"])
    result = GetPersonNetworkTool().run(
        sp, {"person_cluster_id": cooffender_pair["a"], "depth": 2}, session
    )
    g = result.data["graph"]
    ids = {n["data"]["person_cluster_id"] for n in g["nodes"]}
    assert cooffender_pair["a"] in ids
    assert cooffender_pair["b"] in ids  # a direct co-offender is within depth 2
    # cytoscape edge shape
    if g["edges"]:
        e = g["edges"][0]["data"]
        assert {"source", "target", "weight"} <= set(e)
    # provenance carries the people it touched
    assert cooffender_pair["a"] in result.provenance.row_ids


def test_person_network_denies_out_of_scope_seed(session, graph, cooffender_pair):
    # an SP of a district the seed does NOT appear in
    seed = cooffender_pair["a"]
    seed_districts = graph.nodes[seed]["districts"]
    other = session.execute(
        text(
            "SELECT district_id FROM ksp.district WHERE district_id <> ALL(:ds) LIMIT 1"
        ),
        {"ds": list(seed_districts)},
    ).scalar_one()
    with pytest.raises(ToolDenied):
        GetPersonNetworkTool().run(_sp(other), {"person_cluster_id": seed}, session)


def test_person_network_denies_person_with_no_accused_record(session):
    with pytest.raises(ToolDenied):
        GetPersonNetworkTool().run(_sp(1), {"person_cluster_id": 99_999_999}, session)


# --- find_shortest_path ------------------------------------------------------


def test_shortest_path_between_cooffenders(session, cooffender_pair):
    sp = _sp(cooffender_pair["district"])
    result = FindShortestPathTool().run(
        sp,
        {
            "source_person_cluster_id": cooffender_pair["a"],
            "target_person_cluster_id": cooffender_pair["b"],
        },
        session,
    )
    assert result.data["connected"] is True
    assert result.data["degrees_of_separation"] == 1  # co-arrested = directly linked
    assert result.data["path"][0] == cooffender_pair["a"]
    assert result.data["path"][-1] == cooffender_pair["b"]


# --- detect_communities ------------------------------------------------------


def test_communities_flag_cross_jurisdiction(session, cooffender_pair):
    sp = _sp(cooffender_pair["district"])
    result = DetectCommunitiesTool().run(sp, {"min_size": 3}, session)
    comms = result.data["communities"]
    assert comms, "expected at least one co-offending group"
    for c in comms:
        # the flag is consistent with the number of distinct stations spanned
        assert c["cross_jurisdiction"] == (len(c["stations_spanned"]) > 1)
        assert c["size"] >= 3


def test_communities_cross_jurisdiction_only_filter(session, cooffender_pair):
    sp = _sp(cooffender_pair["district"])
    result = DetectCommunitiesTool().run(
        sp, {"min_size": 3, "cross_jurisdiction_only": True}, session
    )
    assert all(c["cross_jurisdiction"] for c in result.data["communities"])


# --- get_repeat_offenders ----------------------------------------------------


def test_repeat_offenders_sorted_and_thresholded(session, cooffender_pair):
    sp = _sp(cooffender_pair["district"])
    result = GetRepeatOffendersTool().run(sp, {"min_firs": 3, "limit": 10}, session)
    offenders = result.data["offenders"]
    assert all(o["firs"] >= 3 for o in offenders)
    assert [o["firs"] for o in offenders] == sorted(
        (o["firs"] for o in offenders), reverse=True
    )
    assert len(offenders) <= 10


def test_repeat_offenders_denied_for_analyst(session):
    # person-level tool: aggregate-only roles are denied at the boundary
    with pytest.raises(ToolDenied):
        GetRepeatOffendersTool().run(
            Principal(name="a", role=Role.SCRB_ANALYST), {"min_firs": 3}, session
        )


# --- catalog -----------------------------------------------------------------


def test_network_tools_registered():
    names = {s["name"] for s in build_registry().anthropic_schemas()}
    assert {
        "get_person_network",
        "find_shortest_path",
        "detect_communities",
        "get_repeat_offenders",
    } <= names


def test_build_is_deterministic_enough(session):
    """A fresh build has the same node/edge counts as the cached one (no nondeterminism in
    graph construction)."""
    reset_person_graph()
    g1 = build_person_graph(session)
    g2 = build_person_graph(session)
    assert g1.number_of_nodes() == g2.number_of_nodes()
    assert g1.number_of_edges() == g2.number_of_edges()
