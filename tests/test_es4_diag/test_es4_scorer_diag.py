"""Unit tests for the M13-ES4 offline scorer diagnostic harness.

The statistics + decision rule are pure numpy / stdlib, so they run without
sentence-transformers (no ``importorskip`` needed): candidates are built from
deterministic stub rarity closures. These tests pin the Codex-hardened gates —
the leave-anchor-out audit, the among-appropriate gold test, and the
``SCORER_OK × SIGNAL_PLAUSIBLE`` decision rule.
"""

from __future__ import annotations

import numpy as np
import pytest
from scripts.es4_scorer_diag import (
    Candidate,
    CandidateReport,
    GenDQ,
    build_idf,
    cluster_paired_delta,
    decide,
    embed_rarity,
    gold_good_vs_common,
    jaccard_rarity,
    rarity_ok,
    tfidf_rarity,
)

from erre_sandbox.evidence.es4_actuator import constants as _c
from erre_sandbox.evidence.es4_actuator.battery import (
    AdversarialItem,
    load_adversarial_labeled,
)


# --- embed_rarity + leave-anchor-out -----------------------------------------
def test_embed_rarity_max_and_mean() -> None:
    vec = np.array([1.0, 0.0])
    ref = np.array([[1.0, 0.0], [0.0, 1.0]])  # one identical, one orthogonal
    assert embed_rarity(vec, ref, leave_anchor_out=False, agg="max") == pytest.approx(
        0.0
    )
    assert embed_rarity(vec, ref, leave_anchor_out=False, agg="mean") == pytest.approx(
        0.5
    )


def test_embed_rarity_leave_anchor_out_drops_near_dup() -> None:
    vec = np.array([1.0, 0.0])
    ref = np.array([[1.0, 0.0], [0.0, 1.0]])  # first is the literal anchor (cos 1.0)
    # full: rarity 0 (the anchor matches); LAO: anchor dropped -> only orthogonal left.
    assert embed_rarity(vec, ref, leave_anchor_out=False, agg="max") == pytest.approx(
        0.0
    )
    assert embed_rarity(vec, ref, leave_anchor_out=True, agg="max") == pytest.approx(
        1.0
    )


def test_embed_rarity_all_dropped_is_zero() -> None:
    vec = np.array([1.0, 0.0])
    ref = np.array([[1.0, 0.0]])  # only a near-dup; LAO removes it
    assert embed_rarity(vec, ref, leave_anchor_out=True, agg="max") == pytest.approx(
        0.0
    )


# --- lexical / tfidf ---------------------------------------------------------
def test_jaccard_rarity() -> None:
    # identical tokens -> jaccard 1 -> rarity 0; disjoint -> rarity 1.
    assert jaccard_rarity(
        "build a wall", ["build a wall"], drop_dup=False
    ) == pytest.approx(0.0)
    assert jaccard_rarity(
        "quantum flux", ["build a wall"], drop_dup=False
    ) == pytest.approx(1.0)


def test_tfidf_rarity_rarer_tokens_score_higher() -> None:
    corpus = ["build a wall", "build a path", "build a house"]
    idf = build_idf(corpus)
    default = 5.0
    common = tfidf_rarity("build a wall", idf, default)
    rare = tfidf_rarity("zzz qqq", idf, default)  # unseen tokens -> default idf
    assert rare > common


# --- gold good-vs-common AUC + leave-anchor-out collapse ---------------------
def _gold_pair() -> list[AdversarialItem]:
    gold = load_adversarial_labeled()
    return [g for g in gold if g.category in {"good", "common_use_only"}]


def test_gold_perfect_separator_passes_both() -> None:
    good = {g.text for g in _gold_pair() if g.category == "good"}

    def rarity(object_id: str, text: str, *, leave_anchor_out: bool) -> float:  # noqa: ARG001
        return 0.9 if text in good else 0.1

    cand = Candidate("perfect", "stub", rarity)
    res = gold_good_vs_common(cand, _gold_pair())
    assert res.auc_full == pytest.approx(1.0)
    assert res.auc_leave_anchor_out == pytest.approx(1.0)


def test_gold_anchor_recogniser_collapses_under_leave_anchor_out() -> None:
    """The Codex HIGH-1 mechanism: a scorer that only recognises its literal negative
    anchors scores high on the full reference but collapses under leave-anchor-out."""
    good = {g.text for g in _gold_pair() if g.category == "good"}

    def rarity(object_id: str, text: str, *, leave_anchor_out: bool) -> float:  # noqa: ARG001
        if text in good:
            return 0.9
        return (
            0.95 if leave_anchor_out else 0.1
        )  # common looks rare once anchor removed

    cand = Candidate("anchor", "stub", rarity)
    res = gold_good_vs_common(cand, _gold_pair())
    assert res.auc_full == pytest.approx(1.0)
    assert res.auc_leave_anchor_out < 0.5


# --- cluster-paired delta ----------------------------------------------------
def test_cluster_paired_delta_positive_effect() -> None:
    units = [
        GenDQ("kant", "brick", "A0", 0, 0.10, 1.0),
        GenDQ("kant", "brick", "A2", 0, 0.30, 1.0),
        GenDQ("kant", "key", "A0", 0, 0.20, 1.0),
        GenDQ("kant", "key", "A2", 0, 0.40, 1.0),
    ]
    raw, lo, hi, n = cluster_paired_delta(units)
    assert raw == pytest.approx(0.20)
    assert n == 2
    assert lo <= raw <= hi


def test_cluster_paired_delta_empty() -> None:
    assert cluster_paired_delta([]) == (0.0, 0.0, 0.0, 0)


# --- rarity_ok gate ----------------------------------------------------------
def _report(**kw: object) -> CandidateReport:
    base: dict[str, object] = {
        "key": "c",
        "description": "d",
        "available": True,
        "gold_auc_full": 0.9,
        "gold_auc_leave_anchor_out": 0.9,
        "gold_perm_p": 0.0,
        "adversarial_full_auc": 0.5,
        "rarity_ok": False,
    }
    base.update(kw)
    return CandidateReport(**base)  # type: ignore[arg-type]


def test_rarity_ok_requires_both_full_and_leave_anchor_out() -> None:
    assert rarity_ok(_report(gold_auc_full=0.9, gold_auc_leave_anchor_out=0.9))
    # full passes but leave-anchor-out fails -> not RARITY_OK (the Codex HIGH-1 guard)
    assert not rarity_ok(_report(gold_auc_full=0.99, gold_auc_leave_anchor_out=0.6))
    assert not rarity_ok(_report(available=False))


# --- decision rule -----------------------------------------------------------
def _scorer_ok_report(*, signal: bool) -> CandidateReport:
    return _report(
        rarity_ok=True,
        entropy_ok=True,
        evaluated_signal=True,
        delta_ci_upper=(_c.DQ_FLOOR_RAW + 0.01 if signal else _c.DQ_FLOOR_RAW - 0.01),
    )


def test_decide_pass_when_scorer_ok_and_signal() -> None:
    out = decide([_scorer_ok_report(signal=True)])
    assert out["verdict"] == "PASS"
    assert out["recommended_direction"] == "D"


def test_decide_scorer_ok_but_signal_absent_is_b() -> None:
    out = decide([_scorer_ok_report(signal=False)])
    assert out["verdict"] == "SCORER_OK_SIGNAL_ABSENT"
    assert out["recommended_direction"] == "B"


def test_decide_rarity_ok_but_entropy_fails_is_no_valid_scorer() -> None:
    # mirrors the real run's C5 Jaccard: RARITY_OK passes, ENTROPY_OK fails.
    rep = _report(rarity_ok=True, entropy_ok=False, evaluated_signal=True)
    out = decide([rep])
    assert out["verdict"] == "NO_VALID_SCORER"
    assert out["recommended_direction"] == "B"
    assert out["rarity_ok_candidates"] == ["c"]


def test_decide_no_rarity_ok_is_no_valid_scorer() -> None:
    out = decide([_report(gold_auc_leave_anchor_out=0.5)])
    assert out["verdict"] == "NO_VALID_SCORER"
    assert out["recommended_direction"] == "B"
