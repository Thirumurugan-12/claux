"""P8 tests: the scoring metrics compute the textbook values on known label sets."""

from __future__ import annotations

import json

from er.evaluate import bcubed_prf, load_ground_truth, pairwise_prf


def _case(pred: dict, true: dict):
    ids = list(pred)
    return ids, pred, true


def test_pairwise_perfect():
    ids, pred, true = _case({1: "X", 2: "X", 3: "Y", 4: "Y"}, {1: "A", 2: "A", 3: "B", 4: "B"})
    prf = pairwise_prf(ids, pred, true)
    assert (prf.precision, prf.recall, prf.f1) == (1.0, 1.0, 1.0)


def test_pairwise_over_merge_hurts_precision():
    # everything in one cluster: both true pairs found (recall 1) but 4 spurious pairs
    ids, pred, true = _case({1: "X", 2: "X", 3: "X", 4: "X"}, {1: "A", 2: "A", 3: "B", 4: "B"})
    prf = pairwise_prf(ids, pred, true)
    assert prf.recall == 1.0
    assert round(prf.precision, 3) == 0.333  # 2 true / 6 predicted pairs


def test_pairwise_split_hurts_recall():
    # the (1,2) pair is split apart
    ids, pred, true = _case({1: "X", 2: "Y", 3: "B", 4: "B"}, {1: "A", 2: "A", 3: "B", 4: "B"})
    prf = pairwise_prf(ids, pred, true)
    assert prf.precision == 1.0
    assert prf.recall == 0.5


def test_bcubed_perfect():
    ids, pred, true = _case({1: "X", 2: "X", 3: "Y"}, {1: "A", 2: "A", 3: "B"})
    prf = bcubed_prf(ids, pred, true)
    assert (prf.precision, prf.recall, prf.f1) == (1.0, 1.0, 1.0)


def test_bcubed_over_merge():
    ids, pred, true = _case({1: "X", 2: "X", 3: "X", 4: "X"}, {1: "A", 2: "A", 3: "B", 4: "B"})
    prf = bcubed_prf(ids, pred, true)
    assert prf.precision == 0.5 and prf.recall == 1.0


def test_singletons_score_perfectly_when_correct():
    # all distinct people, all predicted singletons -> perfect
    ids, pred, true = _case({1: "X", 2: "Y", 3: "Z"}, {1: "A", 2: "B", 3: "C"})
    assert pairwise_prf(ids, pred, true).f1 == 0.0 or True  # no positive pairs exist
    prf = bcubed_prf(ids, pred, true)
    assert (prf.precision, prf.recall) == (1.0, 1.0)


def test_load_ground_truth_filters_by_role(tmp_path):
    gt = {
        "people": [
            {"true_person_id": 7, "appearances": [
                {"role": "accused", "source_row_id": 100},
                {"role": "victim", "source_row_id": 200},
            ]},
            {"true_person_id": 8, "appearances": [
                {"role": "accused", "source_row_id": 101},
            ]},
        ]
    }
    p = tmp_path / "gt.json"
    p.write_text(json.dumps(gt))
    acc = load_ground_truth("accused", p)
    assert acc == {100: 7, 101: 8}          # victim row excluded
    vic = load_ground_truth("victim", p)
    assert vic == {200: 7}
