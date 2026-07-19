"""Network tools (P12) — tools 7–10 of PLAN.md §3, over the resolved-person graph.

The entity-resolution spine (P5–P8) turned per-FIR accused rows into resolved people
(``person_cluster``). These tools ask the questions that only make sense once you have
*people*: who does this person offend with, how are two people connected, which groups
operate as a unit — and, the flagship, which of those groups span multiple police stations
and are therefore invisible to any single station.

The graph is at the **person level**: nodes are ``person_cluster_id``, and two people share an
edge when they were arrested in the same event (``ksp.inv_arrest_surrender_accused``, the
authoritative co-arrest junction). This is distinct from ``er/graph.py``, whose nodes are
per-FIR accused rows and which exists to power collective resolution. Here we build on top of
the resolution it produced.

Building the graph touches ~55k member rows and ~28k co-arrest rows, so it is **built once and
cached** (``get_person_graph``); every tool call works over the cache and an RBAC-induced
subgraph. Outputs are Cytoscape.js-ready ``{nodes, edges}`` for the P20 network pane.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations

import networkx as nx
from pydantic import BaseModel, Field
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

# -----------------------------------------------------------------------------
# Cached person-level co-offending graph
# -----------------------------------------------------------------------------

_PERSON_GRAPH: nx.Graph | None = None


def build_person_graph(session: Session) -> nx.Graph:
    """Nodes = resolved accused persons (``person_cluster_id``) with identity + jurisdiction
    metadata; edges = co-arrest, weighted by how many arrest events two people share."""
    g = nx.Graph()

    # Nodes: one row per accused appearance; aggregate the stations/districts a person spans.
    node_rows = session.execute(
        text(
            "SELECT pcm.person_cluster_id AS pid, pc.display_name, pc.member_count, "
            "       pc.gender_id, pc.est_birth_year, c.police_station_id AS station, "
            "       u.district_id AS district "
            "FROM derived.person_cluster_member pcm "
            "JOIN derived.person_cluster pc ON pc.person_cluster_id = pcm.person_cluster_id "
            "JOIN ksp.case_master c ON c.case_master_id = pcm.case_master_id "
            "JOIN ksp.unit u ON u.unit_id = c.police_station_id "
            "WHERE pcm.role = 'accused'"
        )
    ).mappings()
    for r in node_rows:
        pid = r["pid"]
        if pid not in g:
            g.add_node(
                pid,
                display_name=r["display_name"],
                firs=r["member_count"],
                gender_id=r["gender_id"],
                est_birth_year=r["est_birth_year"],
                stations=set(),
                districts=set(),
            )
        if r["station"] is not None:
            g.nodes[pid]["stations"].add(r["station"])
        if r["district"] is not None:
            g.nodes[pid]["districts"].add(r["district"])

    # Edges: group co-arrested people by arrest event, connect every distinct pair.
    edge_rows = session.execute(
        text(
            "SELECT j.arrest_surrender_id AS eid, pcm.person_cluster_id AS pid, "
            "       c.crime_no AS crime_no "
            "FROM ksp.inv_arrest_surrender_accused j "
            "JOIN derived.person_cluster_member pcm "
            "  ON pcm.role = 'accused' AND pcm.source_row_id = j.accused_master_id "
            "JOIN ksp.case_master c ON c.case_master_id = pcm.case_master_id"
        )
    ).mappings()
    events: dict[int, dict[int, str]] = defaultdict(dict)
    for r in edge_rows:
        events[r["eid"]][r["pid"]] = r["crime_no"]  # pid -> crime_no of that event's FIR

    for members in events.values():
        for a, b in combinations(sorted(members), 2):
            if g.has_edge(a, b):
                g[a][b]["weight"] += 1
                g[a][b]["crime_nos"].add(members[a])
            else:
                g.add_edge(a, b, weight=1, crime_nos={members[a]})
    return g


def get_person_graph(session: Session) -> nx.Graph:
    """The cached graph, built on first use. Static within a run (the data does not change
    mid-session), so it is safe to reuse across calls — the point of P12's caching note."""
    global _PERSON_GRAPH
    if _PERSON_GRAPH is None:
        _PERSON_GRAPH = build_person_graph(session)
    return _PERSON_GRAPH


def reset_person_graph() -> None:
    """Drop the cache (tests, or after a re-resolve)."""
    global _PERSON_GRAPH
    _PERSON_GRAPH = None


# -----------------------------------------------------------------------------
# RBAC: an operational principal sees only the subgraph of people in their units
# -----------------------------------------------------------------------------


def _scope_units(principal: Principal, session: Session) -> set[int] | None:
    return units_in_scope(principal, session)


def _in_scope(node_data: dict, scope: set[int] | None) -> bool:
    return scope is None or bool(node_data["stations"] & scope)


def _scoped_subgraph(graph: nx.Graph, scope: set[int] | None) -> nx.Graph:
    """The induced subgraph of people who have at least one FIR in the caller's units. This
    is the network RBAC boundary: you can traverse and enumerate only your own jurisdiction's
    people — the same rule get_person uses for appearances, lifted to the graph."""
    if scope is None:
        return graph
    keep = [n for n, d in graph.nodes(data=True) if d["stations"] & scope]
    return graph.subgraph(keep)


def _stations_in_view(node_data: dict, scope: set[int] | None) -> set[int]:
    """The person's stations the caller is allowed to see — all of them for a state role,
    otherwise only those inside the caller's scope."""
    return node_data["stations"] if scope is None else (node_data["stations"] & scope)


def _node_payload(graph: nx.Graph, pid: int, scope: set[int] | None) -> dict:
    d = graph.nodes[pid]
    stations = sorted(_stations_in_view(d, scope))
    districts = sorted(d["districts"] if scope is None else d["districts"])
    return {
        "data": {
            "id": str(pid),
            "person_cluster_id": pid,
            "label": d["display_name"],
            "firs": d["firs"],
            "stations": stations,
            "districts": districts,
        }
    }


def _cytoscape(graph: nx.Graph, nodes: list[int], scope: set[int] | None) -> dict:
    """Serialise an induced node set + the edges among them for Cytoscape.js."""
    node_set = set(nodes)
    out_nodes = [_node_payload(graph, n, scope) for n in nodes]
    out_edges = []
    crime_nos: set[str] = set()
    for a, b in graph.subgraph(node_set).edges():
        w = graph[a][b]["weight"]
        cns = sorted(graph[a][b]["crime_nos"])
        crime_nos.update(cns)
        out_edges.append(
            {"data": {"source": str(a), "target": str(b), "weight": w, "crime_nos": cns}}
        )
    return {"nodes": out_nodes, "edges": out_edges, "_crime_nos": sorted(crime_nos)}


# -----------------------------------------------------------------------------
# 7. get_person_network
# -----------------------------------------------------------------------------


class GetPersonNetworkParams(BaseModel):
    person_cluster_id: int = Field(..., description="The person to centre the network on.")
    depth: int = Field(1, ge=1, le=3, description="How many co-offending hops to expand.")
    max_nodes: int = Field(60, ge=1, le=300, description="Cap on returned nodes.")


class GetPersonNetworkTool(Tool):
    name = "get_person_network"
    description = (
        "The co-offending network around one resolved person, expanded a given number of hops "
        "(who they were arrested with, who those people were arrested with, ...). Returns a "
        "Cytoscape graph."
    )
    Params = GetPersonNetworkParams
    person_level = True

    def _run(
        self, principal: Principal, params: GetPersonNetworkParams, session: Session
    ) -> ToolResult:
        graph = get_person_graph(session)
        scope = _scope_units(principal, session)
        if params.person_cluster_id not in graph:
            raise ToolDenied(
                f"person_cluster {params.person_cluster_id} has no accused record to network on"
            )
        if not _in_scope(graph.nodes[params.person_cluster_id], scope):
            raise ToolDenied(
                f"person_cluster {params.person_cluster_id} has no FIRs in your scope"
            )
        sub = _scoped_subgraph(graph, scope)
        ego = nx.ego_graph(sub, params.person_cluster_id, radius=params.depth)
        # cap by proximity: BFS order from the seed, keep the nearest max_nodes
        ordered = [params.person_cluster_id] + [
            n for n in nx.bfs_tree(ego, params.person_cluster_id).nodes()
            if n != params.person_cluster_id
        ]
        kept = ordered[: params.max_nodes]
        cyto = _cytoscape(graph, kept, scope)
        data = {
            "seed": params.person_cluster_id,
            "depth": params.depth,
            "node_count": len(cyto["nodes"]),
            "edge_count": len(cyto["edges"]),
            "direct_cooffenders": ego.degree(params.person_cluster_id),
            "graph": {"nodes": cyto["nodes"], "edges": cyto["edges"]},
        }
        return ToolResult(
            data=data,
            provenance=Provenance(
                sql_hash=sql_hash("get_person_network", {"id": params.person_cluster_id,
                                                          "depth": params.depth}),
                row_ids=kept,
                crime_nos=cyto["_crime_nos"],
            ),
        )


# -----------------------------------------------------------------------------
# 8. find_shortest_path
# -----------------------------------------------------------------------------


class FindShortestPathParams(BaseModel):
    source_person_cluster_id: int = Field(..., description="Start person.")
    target_person_cluster_id: int = Field(..., description="End person.")


class FindShortestPathTool(Tool):
    name = "find_shortest_path"
    description = (
        "The shortest co-offending chain between two resolved people — how one is connected to "
        "the other through shared arrests. Returns the path as a Cytoscape graph, or that none "
        "exists."
    )
    Params = FindShortestPathParams
    person_level = True

    def _run(
        self, principal: Principal, params: FindShortestPathParams, session: Session
    ) -> ToolResult:
        graph = get_person_graph(session)
        scope = _scope_units(principal, session)
        src, tgt = params.source_person_cluster_id, params.target_person_cluster_id
        for pid in (src, tgt):
            if pid not in graph:
                raise ToolDenied(f"person_cluster {pid} has no accused record")
            if not _in_scope(graph.nodes[pid], scope):
                raise ToolDenied(f"person_cluster {pid} has no FIRs in your scope")
        sub = _scoped_subgraph(graph, scope)
        try:
            path = nx.shortest_path(sub, src, tgt)
        except nx.NetworkXNoPath:
            path = None
        if path is None:
            return ToolResult(
                data={"connected": False, "source": src, "target": tgt, "graph": None},
                provenance=Provenance(
                    sql_hash=sql_hash("find_shortest_path", {"s": src, "t": tgt}),
                    row_ids=[src, tgt],
                    crime_nos=[],
                ),
            )
        cyto = _cytoscape(graph, path, scope)
        data = {
            "connected": True,
            "source": src,
            "target": tgt,
            "degrees_of_separation": len(path) - 1,
            "path": path,
            "graph": {"nodes": cyto["nodes"], "edges": cyto["edges"]},
        }
        return ToolResult(
            data=data,
            provenance=Provenance(
                sql_hash=sql_hash("find_shortest_path", {"s": src, "t": tgt}),
                row_ids=path,
                crime_nos=cyto["_crime_nos"],
            ),
        )


# -----------------------------------------------------------------------------
# 9. detect_communities (Louvain)
# -----------------------------------------------------------------------------


class DetectCommunitiesParams(BaseModel):
    min_size: int = Field(3, ge=2, le=50, description="Smallest group to report.")
    cross_jurisdiction_only: bool = Field(
        False, description="Only groups that span more than one police station."
    )
    limit: int = Field(25, ge=1, le=200, description="Max groups to return.")


class DetectCommunitiesTool(Tool):
    name = "detect_communities"
    description = (
        "Detect co-offending groups (Louvain community detection) and flag the ones that span "
        "multiple police stations — cross-jurisdiction groups are invisible to any single "
        "station and are the ones worth surfacing."
    )
    Params = DetectCommunitiesParams
    person_level = True

    def _run(
        self, principal: Principal, params: DetectCommunitiesParams, session: Session
    ) -> ToolResult:
        graph = get_person_graph(session)
        scope = _scope_units(principal, session)
        sub = _scoped_subgraph(graph, scope)
        # drop isolates — a community needs edges
        core = sub.subgraph([n for n, d in sub.degree() if d > 0])
        if core.number_of_nodes() == 0:
            return ToolResult(
                data={"community_count": 0, "communities": []},
                provenance=Provenance(
                    sql_hash=sql_hash("detect_communities", {}), row_ids=[], crime_nos=[]
                ),
            )
        communities = nx.community.louvain_communities(core, weight="weight", seed=42)

        results = []
        all_ids: list[int] = []
        all_crime_nos: set[str] = set()
        for members in communities:
            if len(members) < params.min_size:
                continue
            stations: set[int] = set()
            for pid in members:
                stations |= _stations_in_view(graph.nodes[pid], scope)
            cross = len(stations) > 1
            if params.cross_jurisdiction_only and not cross:
                continue
            member_list = sorted(members, key=lambda p: graph.nodes[p]["firs"], reverse=True)
            cyto = _cytoscape(graph, member_list, scope)
            all_crime_nos.update(cyto["_crime_nos"])
            all_ids.extend(member_list)
            results.append(
                {
                    "size": len(members),
                    "cross_jurisdiction": cross,
                    "stations_spanned": sorted(stations),
                    "members": [
                        {
                            "person_cluster_id": p,
                            "display_name": graph.nodes[p]["display_name"],
                            "firs": graph.nodes[p]["firs"],
                        }
                        for p in member_list
                    ],
                    "graph": {"nodes": cyto["nodes"], "edges": cyto["edges"]},
                }
            )
        # most interesting first: cross-jurisdiction, then larger
        results.sort(key=lambda c: (c["cross_jurisdiction"], c["size"]), reverse=True)
        results = results[: params.limit]
        return ToolResult(
            data={
                "community_count": len(results),
                "cross_jurisdiction_count": sum(c["cross_jurisdiction"] for c in results),
                "communities": results,
            },
            provenance=Provenance(
                sql_hash=sql_hash(
                    "detect_communities",
                    {"min_size": params.min_size, "xj": params.cross_jurisdiction_only},
                ),
                row_ids=all_ids,
                crime_nos=sorted(all_crime_nos),
            ),
        )


# -----------------------------------------------------------------------------
# 10. get_repeat_offenders
# -----------------------------------------------------------------------------


class GetRepeatOffendersParams(BaseModel):
    min_firs: int = Field(3, ge=2, le=50, description="Minimum linked FIRs to qualify.")
    limit: int = Field(25, ge=1, le=200)


class GetRepeatOffendersTool(Tool):
    name = "get_repeat_offenders"
    description = (
        "Resolved people linked to many FIRs — the prolific offenders — with how many "
        "co-offenders each has. Scoped to the caller's jurisdiction."
    )
    Params = GetRepeatOffendersParams
    person_level = True

    def _run(
        self, principal: Principal, params: GetRepeatOffendersParams, session: Session
    ) -> ToolResult:
        graph = get_person_graph(session)
        scope = _scope_units(principal, session)
        sub = _scoped_subgraph(graph, scope)
        rows = [
            (n, d) for n, d in sub.nodes(data=True) if d["firs"] >= params.min_firs
        ]
        rows.sort(key=lambda t: t[1]["firs"], reverse=True)
        rows = rows[: params.limit]
        offenders = [
            {
                "person_cluster_id": n,
                "display_name": d["display_name"],
                "firs": d["firs"],
                "co_offenders": sub.degree(n),
                "districts": sorted(d["districts"]),
                "stations": sorted(_stations_in_view(d, scope)),
            }
            for n, d in rows
        ]
        return ToolResult(
            data={"count": len(offenders), "offenders": offenders},
            provenance=Provenance(
                sql_hash=sql_hash("get_repeat_offenders", {"min_firs": params.min_firs}),
                row_ids=[o["person_cluster_id"] for o in offenders],
                crime_nos=[],
            ),
        )
