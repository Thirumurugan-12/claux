"""Collective entity resolution — the novel core (PLAN.md §2 stage 5).

Identity and network are solved jointly and iteratively:

  1. Score every candidate pair once (P6) — the *base* score.
  2. Cluster: union every pair at or above the auto-merge threshold (union-find).
  3. Propagate: for each candidate pair, add a boost if the two records have
     co-offenders that are already resolved to the *same* person. Two "Ramesh"
     records each arrested alongside what turns out to be the same "Suresh" are far
     more likely to be the same Ramesh.
  4. Re-cluster with base + boost, and repeat 2–3 rounds until the clustering stops
     changing.

The lift from step 3 — how many more true merges the network evidence buys over the
name-only baseline — is the headline number P8 measures. This module reports the
auto-merge count with propagation off vs on so the effect is visible immediately.

Output is persisted to ``derived``: one ``person_cluster`` per resolved person, a
``person_cluster_member`` per source row carrying the *evidence* for its link (which
signals fired, which co-offenders), and the 0.60–0.85 band written to
``er_review_queue`` and never auto-merged.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import psycopg

from er.blocking import candidate_pairs
from er.graph import build_cooffending_graph, cooffender_map
from er.records import PartyRecord
from er.scoring import (
    AUTO_MERGE,
    DEFAULT_WEIGHTS,
    REVIEW_FLOOR,
    ScoringWeights,
    score_detail,
    score_value,
)

RESOLVER_VERSION = "collective-v1"


@dataclass
class ResolveConfig:
    weights: ScoringWeights = field(default_factory=lambda: DEFAULT_WEIGHTS)
    # a pair is worth carrying through propagation if its base score could plausibly
    # cross a decision threshold once the network boost is added
    propagation_floor: float = 0.45
    boost_per_cooffender: float = 0.12
    boost_cap: float = 0.25
    max_rounds: int = 3


# -----------------------------------------------------------------------------
# Union-Find
# -----------------------------------------------------------------------------


class UnionFind:
    """Union-find with two per-cluster *cannot-link* constraints that stop a borderline
    bridge edge from transitively fusing distinct people:

      * **patronymic label** — different non-null patronymic phonetic keys can't merge
        (Marappa vs Mallappa), while corrupted-but-same keys (Marappa/Maranna) do.
      * **birth-year span** — since est_birth_year = reg_year − age is stable within a
        few years for one person, a merge whose cluster birth-year span would exceed
        ``max_birth_span`` is refused (two different "Manjunath S/o Basavanna" of
        different ages stay apart).
    """

    def __init__(
        self,
        n: int,
        labels: list | None = None,
        births: list | None = None,
        max_birth_span: int = 5,
    ):
        self.parent = list(range(n))
        self.rank = [0] * n
        self.label = list(labels) if labels is not None else [None] * n
        self.bmin = list(births) if births is not None else [None] * n
        self.bmax = list(births) if births is not None else [None] * n
        self.max_birth_span = max_birth_span

    def find(self, x: int) -> int:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:  # path compression
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: int, b: int) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return True
        la, lb = self.label[ra], self.label[rb]
        if la and lb and la != lb:
            return False  # cannot-link: conflicting patronymics
        lo = _min_opt(self.bmin[ra], self.bmin[rb])
        hi = _max_opt(self.bmax[ra], self.bmax[rb])
        if lo is not None and hi is not None and hi - lo > self.max_birth_span:
            return False  # cannot-link: birth years too far apart
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        self.label[ra] = la or lb
        self.bmin[ra], self.bmax[ra] = lo, hi
        return True


def _min_opt(a, b):
    return b if a is None else (a if b is None else min(a, b))


def _max_opt(a, b):
    return b if a is None else (a if b is None else max(a, b))


# -----------------------------------------------------------------------------
# Result types
# -----------------------------------------------------------------------------


@dataclass
class WorkingPair:
    a: int
    b: int
    base: float
    boost: float = 0.0
    shared_cooffenders: list[tuple[int, int]] = field(default_factory=list)
    signals: dict[str, float] | None = None  # filled lazily, only for kept pairs

    @property
    def score(self) -> float:
        return min(1.0, self.base + self.boost)


@dataclass
class ResolveResult:
    records: list[PartyRecord]
    clusters: dict[int, list[int]]  # root idx -> member record indices
    member_evidence: dict[int, dict]  # record idx -> evidence dict
    member_confidence: dict[int, float]  # record idx -> match confidence
    review_pairs: list[WorkingPair]
    stats: dict[str, int]


# -----------------------------------------------------------------------------
# Resolution
# -----------------------------------------------------------------------------


@dataclass
class Prepared:
    """The one-time, config-independent work (graph + scored working set) so a caller
    can cluster the same pairs under several configs — P8 runs propagation off vs on
    without paying the score pass twice."""

    records: list[PartyRecord]
    working: list[WorkingPair]
    co: dict[int, frozenset[int]]
    patro_labels: list
    births: list
    n_candidate_pairs: int
    adjacency: dict[int, set[int]] | None


def prepare(records: list[PartyRecord], cfg: ResolveConfig,
            adjacency: dict[int, set[int]] | None = None) -> Prepared:
    graph = build_cooffending_graph(records)
    co = cooffender_map(graph)
    working, n = _score_working_set(records, cfg, adjacency)
    return Prepared(records, working, co, [r.patronymic_key for r in records],
                    [r.est_birth_year for r in records], n, adjacency)


def resolve(
    records: list[PartyRecord],
    cfg: ResolveConfig | None = None,
    adjacency: dict[int, set[int]] | None = None,
) -> ResolveResult:
    cfg = cfg or ResolveConfig()
    return resolve_prepared(prepare(records, cfg, adjacency), cfg)


def resolve_prepared(prep: Prepared, cfg: ResolveConfig,
                     attach_review_signals: bool = True) -> ResolveResult:
    """Cluster a prepared working set under ``cfg`` (boosts are reset so a Prepared
    can be reused across configs). ``attach_review_signals`` computes the per-signal
    breakdown for the review band; the evaluation harness turns it off since it only
    needs the clustering, not the human-facing evidence."""
    records, working, co = prep.records, prep.working, prep.co
    patro_labels, births, adjacency = prep.patro_labels, prep.births, prep.adjacency
    for wp in working:  # reset any boost left from a previous config
        wp.boost = 0.0
        wp.shared_cooffenders = []

    base_auto = 0
    uf = _cluster(records, working, patro_labels, births)
    for rnd in range(cfg.max_rounds):
        if rnd == 0:
            base_auto = sum(1 for wp in working if wp.score >= AUTO_MERGE)
        # propagate: recompute the boost from the clustering just formed
        changed = _propagate(working, co, uf, cfg)
        if changed == 0 and rnd > 0:
            break
        uf = _cluster(records, working, patro_labels, births)  # re-cluster with boosts

    final_auto = sum(1 for wp in working if wp.score >= AUTO_MERGE)

    clusters = _collect_clusters(records, uf)
    member_ev, member_conf = _member_evidence(records, working, uf, cfg, adjacency)
    review = [
        wp
        for wp in working
        if REVIEW_FLOOR <= wp.score < AUTO_MERGE and uf.find(wp.a) != uf.find(wp.b)
    ]
    if attach_review_signals:  # the breakdown a human will see; skipped in eval
        for wp in review:
            wp.signals = score_detail(records[wp.a], records[wp.b], cfg.weights, adjacency)[1]

    stats = {
        "records": len(records),
        "candidate_pairs": prep.n_candidate_pairs,
        "working_pairs": len(working),
        "clusters": len(clusters),
        "multi_member_clusters": sum(1 for m in clusters.values() if len(m) > 1),
        "auto_merges_base": base_auto,
        "auto_merges_final": final_auto,
        "collective_lift": final_auto - base_auto,
        "review_pairs": len(review),
    }
    return ResolveResult(records, clusters, member_ev, member_conf, review, stats)


def _score_working_set(records, cfg, adjacency) -> tuple[list[WorkingPair], int]:
    """Score all blocked pairs on the fast path, keep those above the propagation
    floor, and compute the full signal breakdown only for those. Returns the working
    set and the total number of candidate pairs blocking produced."""
    pairs = candidate_pairs(records)
    working: list[WorkingPair] = []
    for ia, ib in pairs:
        base = score_value(records[ia], records[ib], cfg.weights, adjacency)
        if base >= cfg.propagation_floor:
            working.append(WorkingPair(ia, ib, base))
    return working, len(pairs)


def _propagate(working: list[WorkingPair], co, uf: UnionFind, cfg: ResolveConfig) -> int:
    """Recompute each pair's boost from resolved shared co-offenders. Returns the
    number of pairs whose auto-merge status flipped this round."""
    changed = 0
    for wp in working:
        prev_auto = wp.score >= AUTO_MERGE
        shared: list[tuple[int, int]] = []
        roots_seen: set[int] = set()
        co_a = co.get(wp.a, ())
        co_b = co.get(wp.b, ())
        if co_a and co_b:
            for ca in co_a:
                ra = uf.find(ca)
                for cb in co_b:
                    if ca != cb and ra == uf.find(cb):
                        if ra not in roots_seen:
                            roots_seen.add(ra)
                            shared.append((ca, cb))
        wp.shared_cooffenders = shared
        wp.boost = min(cfg.boost_cap, cfg.boost_per_cooffender * len(shared))
        if (wp.score >= AUTO_MERGE) != prev_auto:
            changed += 1
    return changed


def _cluster(records, working: list[WorkingPair], labels: list, births: list) -> UnionFind:
    """Build clusters by unioning auto-merge edges strongest-first, honouring the
    patronymic and birth-year cannot-link constraints so a weak bridge can't fuse
    two people."""
    uf = UnionFind(len(records), labels, births)
    edges = [wp for wp in working if wp.score >= AUTO_MERGE]
    edges.sort(key=lambda wp: wp.score, reverse=True)
    for wp in edges:
        uf.union(wp.a, wp.b)
    return uf


def _collect_clusters(records, uf: UnionFind) -> dict[int, list[int]]:
    clusters: dict[int, list[int]] = {}
    for r in records:
        clusters.setdefault(uf.find(r.idx), []).append(r.idx)
    return clusters


def _member_evidence(records, working, uf: UnionFind, cfg, adjacency):
    """For each record, keep the strongest in-cluster edge as its link evidence."""
    best: dict[int, WorkingPair] = {}
    for wp in working:
        if wp.score >= AUTO_MERGE and uf.find(wp.a) == uf.find(wp.b):
            for node in (wp.a, wp.b):
                cur = best.get(node)
                if cur is None or wp.score > cur.score:
                    best[node] = wp

    evidence: dict[int, dict] = {}
    confidence: dict[int, float] = {}
    for r in records:
        wp = best.get(r.idx)
        if wp is None:
            evidence[r.idx] = {"singleton": True}
            confidence[r.idx] = 1.0
            continue
        if wp.signals is None:  # compute the breakdown once, only for edges we keep
            wp.signals = score_detail(records[wp.a], records[wp.b], cfg.weights, adjacency)[1]
        other = wp.b if wp.a == r.idx else wp.a
        evidence[r.idx] = {
            "linked_to": {
                "role": records[other].role,
                "source_row_id": records[other].source_row_id,
                "crime_no_case": records[other].case_master_id,
            },
            "score": round(wp.score, 4),
            "signals": wp.signals,
            "collective_boost": round(wp.boost, 4),
            "shared_resolved_cooffenders": [
                {
                    "a": records[ca].source_row_id,
                    "b": records[cb].source_row_id,
                }
                for ca, cb in wp.shared_cooffenders
            ],
        }
        confidence[r.idx] = round(wp.score, 4)
    return evidence, confidence


# -----------------------------------------------------------------------------
# Persistence
# -----------------------------------------------------------------------------

_TRUNCATE = (
    "TRUNCATE derived.person_cluster_member, derived.person_cluster, "
    "derived.er_review_queue RESTART IDENTITY CASCADE"
)


def persist(conn: psycopg.Connection, result: ResolveResult) -> None:
    """Write clusters, members (with evidence) and the review queue to ``derived``."""
    records = result.records
    with conn.cursor() as cur:
        cur.execute(_TRUNCATE)

        cluster_id_of: dict[int, int] = {}
        cluster_rows = []
        member_rows = []
        for cid, (root, members) in enumerate(result.clusters.items(), start=1):
            cluster_id_of[root] = cid
            recs = [records[i] for i in members]
            confs = [result.member_confidence[i] for i in members]
            canon = _canonical(recs)
            cluster_rows.append(
                (
                    cid,
                    canon["display_name"],
                    canon["given"],
                    canon["patronymic"],
                    canon["phonetic_key"],
                    canon["est_birth_year"],
                    canon["gender_id"],
                    len(members),
                    round(sum(confs) / len(confs), 3),
                    RESOLVER_VERSION,
                )
            )
            for i in members:
                r = records[i]
                member_rows.append(
                    (
                        cid,
                        r.role,
                        r.source_row_id,
                        r.case_master_id,
                        r.raw_name,
                        r.parsed.given or None,
                        r.parsed.alias,
                        r.parsed.patronymic,
                        r.parsed.relation,
                        r.age_year,
                        result.member_confidence[i],
                        json.dumps(result.member_evidence[i]),
                    )
                )

        _copy(
            cur,
            "derived.person_cluster",
            (
                "person_cluster_id",
                "display_name",
                "canonical_given",
                "canonical_patronymic",
                "phonetic_key",
                "est_birth_year",
                "gender_id",
                "member_count",
                "confidence",
                "resolver_version",
            ),
            cluster_rows,
        )
        _copy(
            cur,
            "derived.person_cluster_member",
            (
                "person_cluster_id",
                "role",
                "source_row_id",
                "case_master_id",
                "raw_name",
                "parsed_given",
                "parsed_alias",
                "parsed_patronymic",
                "parsed_relation",
                "age_year",
                "match_confidence",
                "match_evidence",
            ),
            member_rows,
        )

        review_rows = [
            (
                records[wp.a].role,
                records[wp.a].source_row_id,
                records[wp.b].role,
                records[wp.b].source_row_id,
                round(wp.score, 3),
                json.dumps({"signals": wp.signals, "boost": round(wp.boost, 4)}),
            )
            for wp in result.review_pairs
        ]
        _copy(
            cur,
            "derived.er_review_queue",
            ("role_a", "source_row_id_a", "role_b", "source_row_id_b", "score", "signals"),
            review_rows,
        )
    conn.commit()


def _canonical(recs: list[PartyRecord]) -> dict:
    from collections import Counter

    givens = [r.parsed.given for r in recs if r.parsed.given]
    patros = [r.parsed.patronymic for r in recs if r.parsed.patronymic]
    keys = [r.phonetic_key for r in recs if r.phonetic_key]
    genders = [r.gender_id for r in recs if r.gender_id is not None]
    births = [r.est_birth_year for r in recs if r.est_birth_year is not None]
    given = Counter(givens).most_common(1)[0][0] if givens else None
    patro = Counter(patros).most_common(1)[0][0] if patros else None
    display = (
        f"{given} {recs[0].parsed.relation} {patro}"
        if (given and patro)
        else (given or recs[0].raw_name)
    )
    return {
        "display_name": display,
        "given": given,
        "patronymic": patro,
        "phonetic_key": Counter(keys).most_common(1)[0][0] if keys else None,
        "gender_id": Counter(genders).most_common(1)[0][0] if genders else None,
        "est_birth_year": sorted(births)[len(births) // 2] if births else None,
    }


def _copy(cur, table: str, columns: tuple[str, ...], rows: list[tuple]) -> None:
    if not rows:
        return
    collist = ", ".join(columns)
    with cur.copy(f"COPY {table} ({collist}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)
