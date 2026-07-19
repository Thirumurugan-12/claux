"""The co-offending graph — the structure collective resolution propagates over.

Two accused arrested in the same event are co-offenders. An arrest event belongs to
a single FIR, so every co-offending edge is *within* one case (different people who
offended together). The value shows up across cases: if accused A1 in FIR-1 and A2 in
FIR-2 are candidate same-person, and A1's co-offender resolves to the same person as
A2's co-offender, that shared resolved associate is strong evidence A1 and A2 are the
same person too. This graph is what makes that check possible (and it is reused by the
community-detection tools in P12).

Built with networkx per PLAN.md §2 stage 5. Nodes are accused record indices; edges
connect co-arrested records.
"""

from __future__ import annotations

from collections import defaultdict

import networkx as nx

from er.records import PartyRecord


def build_cooffending_graph(records: list[PartyRecord]) -> nx.Graph:
    """Nodes = accused record indices; edge between two records co-arrested together."""
    g = nx.Graph()
    # group accused record indices by the arrest events they belong to
    event_members: dict[int, list[int]] = defaultdict(list)
    for r in records:
        if r.role != "accused":
            continue
        g.add_node(r.idx)
        for event_id in r.arrest_events:
            event_members[event_id].append(r.idx)

    for members in event_members.values():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                g.add_edge(members[i], members[j])
    return g


def cooffender_map(graph: nx.Graph) -> dict[int, frozenset[int]]:
    """idx -> the set of record indices it was co-arrested with (its graph neighbours)."""
    return {n: frozenset(graph.neighbors(n)) for n in graph.nodes}
