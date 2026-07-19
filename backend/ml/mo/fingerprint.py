"""MO fingerprinting (P15) — deriving a modus-operandi layer the KSP schema lacks.

There is no MO field: it has to be *derived* from ``BriefFacts`` free text. The pipeline is

    text  ->  TF-IDF  ->  TruncatedSVD (LSA, 128-d, L2-normalised)  ->  HDBSCAN  ->  label

and the per-case vector + cluster land in ``derived.case_mo_assignment`` (pgvector) /
``derived.mo_cluster``, so ``find_similar_cases`` is a cosine nearest-neighbour query and
every cluster carries its outcome (cstype) mix.

**Why lexical, not a neural multilingual embedding (the P15 prompt's first choice):** a
sentence-transformer needs torch (~GB) which the build environment can't take. The generator
keeps each MO's *signature slot words* (e.g. "gold chain", "motorcycle", "iron rod") stable as
literal Roman tokens across the English and transliterated renderings (~75% of cases), so
TF-IDF has real, clusterable signal there; Kannada-script cases (~25%) are transliterated to
Roman first (best-effort) and otherwise cluster among themselves until P4 fills ``BriefFacts_en``.
Quality is measured against the hidden ``mo_by_case`` ground truth (V-measure / homogeneity),
so the trade-off is quantified rather than hand-waved. Cluster labelling is pluggable: the
default is deterministic (top TF-IDF terms); an LLM labeller can be supplied for prettier names.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from sklearn.cluster import HDBSCAN
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import completeness_score, homogeneity_score, v_measure_score
from sklearn.preprocessing import normalize
from sqlalchemy import text

from app.db import SessionLocal

EMBED_DIM = 128  # stored vector width (pgvector) for cosine similarity
CLUSTER_DIM = 24  # lower-dim view HDBSCAN actually clusters on (fast + interpretable)
_KANNADA = re.compile(r"[ಀ-೿]")


def _romanise(s: str) -> str:
    """Transliterate any Kannada-script text to Roman so its tokens can meet the English /
    transliterated renderings part-way. Roman text passes through unchanged."""
    if not s or not _KANNADA.search(s):
        return s or ""
    try:
        from indic_transliteration import sanscript

        return sanscript.transliterate(s, sanscript.KANNADA, sanscript.ITRANS).lower()
    except Exception:
        return s


@dataclass
class MoReport:
    n_cases: int
    n_clusters: int
    noise: int
    v_measure: float
    homogeneity: float
    completeness: float
    clusters: list[dict]  # id, label, size, top_terms, cstype mix, sample_texts


def _load_cases(session) -> list[dict]:
    rows = session.execute(
        text(
            "SELECT c.case_master_id, c.brief_facts, c.crime_major_head_id, cs.cs_type "
            "FROM ksp.case_master c "
            "LEFT JOIN ksp.chargesheet_details cs ON cs.case_master_id = c.case_master_id "
            "WHERE c.brief_facts IS NOT NULL"
        )
    ).mappings().all()
    # a case can have at most one chargesheet row here; dedupe defensively on case id
    seen: dict[int, dict] = {}
    for r in rows:
        seen.setdefault(
            r["case_master_id"],
            {
                "case_master_id": r["case_master_id"],
                "text": _romanise(r["brief_facts"]),
                "head": r["crime_major_head_id"],
                "cs_type": r["cs_type"],
            },
        )
    return list(seen.values())


def _label_from_terms(terms: list[str]) -> str:
    return " / ".join(terms[:4]) if terms else "unlabelled pattern"


def fit_clusters(
    cases: list[dict],
    min_cluster_size: int = 120,
    min_samples: int = 15,
    labeller: Callable[[list[str], list[str]], str] | None = None,
) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """Vectorise → reduce → cluster → label. Returns (embeddings, labels, cluster_meta).
    ``labeller(top_terms, sample_texts) -> str`` overrides the default top-terms label
    (e.g. an LLM); it is optional so the pipeline runs fully offline."""
    texts = [c["text"] for c in cases]
    tfidf = TfidfVectorizer(
        max_features=6000, ngram_range=(1, 2), min_df=5, sublinear_tf=True,
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]+\b",
    )
    X = tfidf.fit_transform(texts)
    vocab = np.array(tfidf.get_feature_names_out())

    svd = TruncatedSVD(n_components=EMBED_DIM, random_state=42)
    emb = normalize(svd.fit_transform(X)).astype(np.float32)

    # Cluster on the top-variance sub-space, re-normalised: HDBSCAN's neighbour search
    # degrades badly in 128-d, and the leading SVD components already carry the MO signal.
    # The full 128-d vector is still what we store for cosine similarity.
    cluster_dims = min(CLUSTER_DIM, emb.shape[1])
    cluster_view = normalize(emb[:, :cluster_dims])
    labels = HDBSCAN(
        min_cluster_size=min_cluster_size, min_samples=min_samples, metric="euclidean"
    ).fit_predict(cluster_view)

    # top TF-IDF terms per cluster (mean over members)
    meta: list[dict] = []
    Xcsr = X.tocsr()
    for cid in sorted(set(labels) - {-1}):
        idx = np.where(labels == cid)[0]
        mean_tfidf = np.asarray(Xcsr[idx].mean(axis=0)).ravel()
        top = vocab[np.argsort(mean_tfidf)[::-1][:8]].tolist()
        samples = [cases[i]["text"] for i in idx[:5]]
        label = labeller(top, samples) if labeller else _label_from_terms(top)
        meta.append({"cluster_id": int(cid), "top_terms": top, "label": label, "size": len(idx)})
    return emb, labels, meta


_CS_BUCKET = {"A": "cstype_a", "B": "cstype_b", "C": "cstype_c", None: "cstype_open"}


def _persist(session, cases, emb, labels, meta) -> None:
    """Replace derived.mo_cluster + derived.case_mo_assignment with this run's output."""
    session.execute(text("TRUNCATE derived.case_mo_assignment"))
    session.execute(text("TRUNCATE derived.mo_cluster CASCADE"))

    by_cluster: dict[int, dict] = {}
    for m in meta:
        by_cluster[m["cluster_id"]] = {
            "mo_cluster_id": m["cluster_id"],
            "label": m["label"][:200],
            "top_terms": m["top_terms"],
            "size": m["size"],
            "cstype_a": 0, "cstype_b": 0, "cstype_c": 0, "cstype_open": 0,
        }
    for c, lab in zip(cases, labels, strict=True):
        if lab != -1:
            by_cluster[int(lab)][_CS_BUCKET.get(c["cs_type"], "cstype_open")] += 1

    if by_cluster:
        session.execute(
            text(
                "INSERT INTO derived.mo_cluster "
                "(mo_cluster_id, label, top_terms, size, cstype_a, cstype_b, cstype_c, cstype_open)"
                " VALUES (:mo_cluster_id, :label, :top_terms, :size, "
                ":cstype_a, :cstype_b, :cstype_c, :cstype_open)"
            ),
            list(by_cluster.values()),
        )
    session.execute(
        text(
            "INSERT INTO derived.case_mo_assignment (case_master_id, mo_cluster_id, embedding) "
            "VALUES (:cid, :cl, CAST(:emb AS vector))"
        ),
        [
            {
                "cid": c["case_master_id"],
                "cl": None if lab == -1 else int(lab),
                "emb": "[" + ",".join(f"{x:.5f}" for x in vec) + "]",
            }
            for c, lab, vec in zip(cases, labels, emb, strict=True)
        ],
    )
    session.commit()


def run(
    persist: bool = True,
    min_cluster_size: int = 120,
    labeller: Callable[[list[str], list[str]], str] | None = None,
) -> MoReport:
    session = SessionLocal()
    try:
        cases = _load_cases(session)
        emb, labels, meta = fit_clusters(
            cases, min_cluster_size=min_cluster_size, labeller=labeller
        )

        # score against the hidden MO ground truth, on the clustered (non-noise) cases
        report_clusters = []
        cs_counts: dict[int, dict] = {
            m["cluster_id"]: {"A": 0, "B": 0, "C": 0, "open": 0} for m in meta
        }
        for c, lab in zip(cases, labels, strict=True):
            if lab != -1:
                cs_counts[int(lab)][c["cs_type"] or "open"] += 1
        samples_by_cluster: dict[int, list[str]] = {}
        for c, lab in zip(cases, labels, strict=True):
            if lab != -1 and len(samples_by_cluster.setdefault(int(lab), [])) < 5:
                samples_by_cluster[int(lab)].append(c["text"][:160])
        for m in meta:
            cc = cs_counts[m["cluster_id"]]
            report_clusters.append(
                {**m, "cstype": cc, "sample_texts": samples_by_cluster.get(m["cluster_id"], [])}
            )
        report_clusters.sort(key=lambda x: x["size"], reverse=True)

        gt = _ground_truth_mo()
        v = h = comp = float("nan")
        if gt:
            pairs = [
                (gt[c["case_master_id"]], int(lab))
                for c, lab in zip(cases, labels, strict=True)
                if lab != -1 and c["case_master_id"] in gt
            ]
            if pairs:
                truth, pred = zip(*pairs, strict=True)
                v = v_measure_score(truth, pred)
                h = homogeneity_score(truth, pred)
                comp = completeness_score(truth, pred)

        if persist:
            _persist(session, cases, emb, labels, meta)

        return MoReport(
            n_cases=len(cases),
            n_clusters=len(meta),
            noise=int((labels == -1).sum()),
            v_measure=v,
            homogeneity=h,
            completeness=comp,
            clusters=report_clusters,
        )
    finally:
        session.close()


def _ground_truth_mo() -> dict[int, str]:
    """Load mo_by_case from the hidden ground-truth file, if present. Only the P15 EVALUATION
    may read this — never the clustering itself (it is not passed into fit_clusters)."""
    import json
    from pathlib import Path

    gt_path = Path(__file__).resolve().parents[2] / "ingest" / "synth" / "ground_truth.json"
    if not gt_path.exists():
        return {}
    data = json.loads(gt_path.read_text())
    return {int(k): v for k, v in data.get("mo_by_case", {}).items()}
