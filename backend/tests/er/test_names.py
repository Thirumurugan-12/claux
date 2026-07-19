"""P5 tests for name parsing and normalization.

Two kinds of check:

1. **Parsing** — the structural extraction (given / alias / patronymic / relation /
   honorifics) on hand-written cases, including the acceptance example.
2. **Blocking recall against P2's own corruption** — the honest test. We take a
   canonical identity, run it through the exact corruption machinery the synthetic
   generator uses, and assert that the phonetic key survives it. This measures the
   thing that actually matters: does the blocking key keep a real person's variants
   together? A key that fails here silently caps recall for the whole ER pipeline.
"""

from __future__ import annotations

import random

import pytest

from er.names import dravidian_stem, parse, phonetic_key

# ingest.synth is not part of ER; using its corruption here is legitimate test setup —
# it is exactly the distribution P5 must survive on the real workload.
from ingest.synth.names import NameParts, render_variant


def test_acceptance_all_four_components():
    p = parse("Ramesh @ Rami S/o Krishnappa")
    assert p.given == "Ramesh"
    assert p.alias == "Rami"
    assert p.relation == "S/o"
    assert p.patronymic == "Krishnappa"


@pytest.mark.parametrize(
    "raw,given,relation,patronymic",
    [
        ("Suresh S/o Nanjappa", "Suresh", "S/o", "Nanjappa"),
        ("Lakshmi D/o Krishnappa", "Lakshmi", "D/o", "Krishnappa"),
        ("Geetha W/o Ramesh", "Geetha", "W/o", "Ramesh"),
        ("Ravi C/o Manjunath", "Ravi", "C/o", "Manjunath"),
        ("Kumar son of Basavaraj", "Kumar", "S/o", "Basavaraj"),
        ("Divya daughter of Shivappa", "Divya", "D/o", "Shivappa"),
    ],
)
def test_relation_variants(raw, given, relation, patronymic):
    p = parse(raw)
    assert (p.given, p.relation, p.patronymic) == (given, relation, patronymic)


def test_honorifics_stripped_and_recorded():
    p = parse("Sri Manjunath S/o Kempegowda")
    assert p.given == "Manjunath"
    assert [h.lower() for h in p.honorifics] == ["sri"]


def test_late_prefix_removed_from_patronymic():
    p = parse("Nagaraj S/o Late Krishnappa")
    assert p.given == "Nagaraj"
    assert p.patronymic == "Krishnappa"  # "Late" dropped, name preserved


def test_alias_without_patronymic():
    p = parse("Mahesh @ Macha")
    assert p.given == "Mahesh" and p.alias == "Macha" and p.patronymic is None


def test_empty_and_none_are_safe():
    for raw in (None, "", "   ", "@@@"):
        p = parse(raw)
        assert p.given == "" and p.phonetic_key == ""


def test_kannada_script_transliterated():
    p = parse("ರಮೇಶ")
    assert p.script == "kannada"
    assert p.normalized_given.startswith("rame")
    assert p.phonetic_key == phonetic_key("Ramesh")  # script-independent key


def test_terminal_vowel_variants_share_key():
    assert phonetic_key("Ramesh") == phonetic_key("Ramesha") == phonetic_key("Rameshu")


def test_kinship_suffix_variants_share_key():
    keys = {phonetic_key(v) for v in ["Chandru", "Chandruappa", "Chandruanna", "Chandruu"]}
    assert len(keys) == 1


def test_transliteration_noise_collapses():
    # sh<->s, th<->t, doubled consonants
    assert phonetic_key("Suresh") == phonetic_key("Suresha")
    assert dravidian_stem("Maranna") == dravidian_stem("Marappa")  # patronymic drift


def test_distinct_names_stay_distinct():
    keys = [phonetic_key(n) for n in ["Ramesh", "Suresh", "Ganesh", "Manjunath", "Lakshmi"]]
    assert len(set(keys)) == len(keys), "distinct names must not collapse to one block"


def test_short_names_not_over_stripped():
    # the kinship-suffix strip must not nuke a short given name down to one letter
    assert len(dravidian_stem("Rama")) >= 2
    assert phonetic_key("Rama") != phonetic_key("Ravi")


def test_blocking_recall_against_p2_corruption():
    """The headline P5 metric: across many corrupted variants of one canonical
    identity, the phonetic key of the given name should be stable for the large
    majority. This is the recall ceiling the blocker (P6) inherits."""
    rng = random.Random(2026)
    canon = NameParts(given="Ramesh", patronymic="Krishnappa", relation="S/o", alias="Rami")
    base_key = phonetic_key("Ramesh")
    hits = 0
    n = 400
    for _ in range(n):
        variant = render_variant(canon, rng)
        if parse(variant).phonetic_key == base_key:
            hits += 1
    recall = hits / n
    assert recall > 0.9, f"blocking recall on corrupted variants too low: {recall:.2%}"


def test_blocking_recall_across_many_identities():
    """Same check, averaged over many distinct canonical names, to be sure the key
    isn't just tuned to one example."""
    rng = random.Random(7)
    givens = ["Suresh", "Manjunath", "Basavaraj", "Nagaraj", "Lakshmi", "Shivakumar", "Girish"]
    total, hits = 0, 0
    for g in givens:
        canon = NameParts(given=g, patronymic="Nanjappa", relation="S/o", alias=None)
        base_key = phonetic_key(g)
        for _ in range(60):
            variant = render_variant(canon, rng)
            total += 1
            hits += parse(variant).phonetic_key == base_key
    recall = hits / total
    assert recall > 0.85, f"average blocking recall too low: {recall:.2%}"
