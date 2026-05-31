"""Unit tests for :mod:`erre_sandbox.training.plan_b_v5_gate`.

PR-5 prep DP5-4 acceptance gate: the v5 supplemental hard gate
(``de_en_mass>=0.85``, ``ja_mass<=0.10``, ``de_mass>=0.40``) must hard-fail
when any axis is unmet, and pass cleanly when all three thresholds are
satisfied. Also includes a **DA-14/16 regression guard** that locks the
existing :mod:`erre_sandbox.training.plan_b_gate` thresholds to their
preregistered values so future ADRs do not silently relax them.

References:
* PR-5 prep ``decisions.md`` DP5-1 / DP5-2 / DP5-4
* DA-17 ADR ``decisions.md`` DA17-4 / DA17-7
* DA-16 ADR ``decisions.md`` DA16-4 (thresholds 不変 binding)
"""

from __future__ import annotations

import pytest

from erre_sandbox.training.plan_b_v5_gate import (
    DE_EN_MASS_MIN_V5,
    DE_MASS_MIN_V5,
    JA_MASS_MAX_V5,
    V5_GATE_FAIL_EXIT_CODE,
    V5_GATE_SCHEMA_VERSION,
    audit_corpus_v5,
)

# ---------------------------------------------------------------------------
# Threshold constant guards (preregistered, must not drift silently)
# ---------------------------------------------------------------------------


def test_v5_gate_thresholds_preregistered() -> None:
    """v5 hard floor 定数が PR-5 prep DP5-1 仕様と一致 (regression guard)."""
    assert DE_EN_MASS_MIN_V5 == 0.85
    assert JA_MASS_MAX_V5 == 0.10
    assert DE_MASS_MIN_V5 == 0.40
    assert V5_GATE_FAIL_EXIT_CODE == 9
    assert V5_GATE_SCHEMA_VERSION == 1


# ---------------------------------------------------------------------------
# audit_corpus_v5 — pass / fail behaviour
# ---------------------------------------------------------------------------


def _good_v5_audit() -> dict[str, object]:
    """全 3 v5 floor を pass する synthetic audit dict.

    DP5-2 採用案 A1 (`_LANG_FACTORS["ja"]=0.05`) の予想結果に合致:
    de_en=0.86 (>=0.85), ja=0.08 (<=0.10), de=0.43 (>=0.40)。
    """
    return {
        "per_language_weighted_mass": {
            "de": 0.43,
            "en": 0.43,
            "ja": 0.08,
            "mixed": 0.06,
        },
    }


def test_audit_corpus_v5_passes_when_all_thresholds_met() -> None:
    result = audit_corpus_v5(
        _good_v5_audit(),
        weight_audit_path="path/to/weight-audit.json",
        merge_sha="abc123",
    )
    assert result["v5_gate"] == "pass"
    assert result["failed_axes"] == []
    assert result["schema_version"] == V5_GATE_SCHEMA_VERSION
    assert result["thresholds"]["de_en_mass_min"] == 0.85
    assert result["thresholds"]["ja_mass_max"] == 0.10
    assert result["thresholds"]["de_mass_min"] == 0.40
    assert result["achieved"]["de_en_mass"] == pytest.approx(0.86)
    assert result["achieved"]["ja_mass"] == pytest.approx(0.08)
    assert result["achieved"]["de_mass"] == pytest.approx(0.43)
    assert result["weight_audit_path"] == "path/to/weight-audit.json"
    assert result["merge_sha"] == "abc123"


def test_audit_corpus_v5_fail_ja_mass_high() -> None:
    """ja_mass=0.15 (>0.10) で ja_mass_v5 fail (主目標 axis、PR-5 主旨)."""
    audit = _good_v5_audit()
    audit["per_language_weighted_mass"] = {
        "de": 0.40,
        "en": 0.40,
        "ja": 0.15,  # > 0.10 floor を violate
        "mixed": 0.05,
    }
    result = audit_corpus_v5(
        audit,
        weight_audit_path="x.json",
        merge_sha="sha",
    )
    assert result["v5_gate"] == "fail"
    assert "ja_mass_v5" in result["failed_axes"]


def test_audit_corpus_v5_fail_de_en_mass_low() -> None:
    """de_en_mass=0.80 (<0.85) で de_en_mass_v5 fail."""
    audit = _good_v5_audit()
    audit["per_language_weighted_mass"] = {
        "de": 0.42,
        "en": 0.38,  # de+en=0.80 < 0.85
        "ja": 0.08,
        "mixed": 0.12,
    }
    result = audit_corpus_v5(
        audit,
        weight_audit_path="x.json",
        merge_sha="sha",
    )
    assert result["v5_gate"] == "fail"
    assert "de_en_mass_v5" in result["failed_axes"]


def test_audit_corpus_v5_fail_de_mass_low() -> None:
    """de_mass=0.35 (<0.40) で de_mass_v5 fail (en が独占する corner case)."""
    audit = _good_v5_audit()
    audit["per_language_weighted_mass"] = {
        "de": 0.35,  # < 0.40
        "en": 0.55,  # de+en=0.90 pass、ja=0.05 pass、de だけ fail
        "ja": 0.05,
        "mixed": 0.05,
    }
    result = audit_corpus_v5(
        audit,
        weight_audit_path="x.json",
        merge_sha="sha",
    )
    assert result["v5_gate"] == "fail"
    assert "de_mass_v5" in result["failed_axes"]
    assert "de_en_mass_v5" not in result["failed_axes"]  # de+en は pass
    assert "ja_mass_v5" not in result["failed_axes"]  # ja は pass


def test_audit_corpus_v5_fails_multiple_axes_at_once() -> None:
    """v4 baseline (ja=0.389, de=0.385) は 3 axis 中 2 axis で fail (ja + de_en)."""
    v4_baseline = {
        "per_language_weighted_mass": {
            "de": 0.385,
            "en": 0.216,
            "ja": 0.389,  # > 0.10、最大 fail axis
            "mixed": 0.010,
        },
    }
    result = audit_corpus_v5(
        v4_baseline,
        weight_audit_path="x.json",
        merge_sha="sha",
    )
    assert result["v5_gate"] == "fail"
    # v4: de_en_mass=0.601 < 0.85 → fail、ja_mass=0.389 > 0.10 → fail
    # de_mass=0.385 < 0.40 → fail
    assert set(result["failed_axes"]) == {
        "de_en_mass_v5",
        "ja_mass_v5",
        "de_mass_v5",
    }


def test_audit_corpus_v5_handles_missing_keys_safely() -> None:
    """``per_language_weighted_mass`` 欠落時は default で fail (defensive)."""
    audit: dict[str, object] = {}
    result = audit_corpus_v5(
        audit,
        weight_audit_path="x.json",
        merge_sha="sha",
    )
    # de_mass=0 / en_mass=0 / ja_mass=1.0 (default) で全 axis fail 想定
    assert result["v5_gate"] == "fail"
    assert result["failed_axes"]


def test_audit_corpus_v5_threshold_kwargs_overridable_for_tests() -> None:
    """テスト用 kwargs で閾値 override 可能 (production CLI は固定値)."""
    audit = _good_v5_audit()
    # de_en=0.86 を 0.95 floor (相対的に高い) に当てれば fail させられる
    result = audit_corpus_v5(
        audit,
        weight_audit_path="x.json",
        merge_sha="sha",
        de_en_mass_min=0.95,
    )
    assert result["v5_gate"] == "fail"
    assert "de_en_mass_v5" in result["failed_axes"]


# ---------------------------------------------------------------------------
# DA-14/16 existing gate regression guard (DA16-4 binding)
# ---------------------------------------------------------------------------


def test_existing_da14_gate_thresholds_unchanged() -> None:
    """DA-14/16 既存 4 gate (`plan_b_gate.audit_corpus`) の閾値 regression guard.

    PR-5 prep / DA-17 ADR で既存 gate を **変更してはならない** (DA16-4
    binding)。本 test は将来の意図しない閾値ドリフトを検出する。
    """
    from erre_sandbox.training.plan_b_gate import (
        DE_EN_MASS_MIN,
        DE_MASS_MIN,
        GATE_FAIL_EXIT_CODE,
        N_EFF_MIN,
        TOP_5_PCT_MAX,
    )

    assert DE_EN_MASS_MIN == 0.60
    assert DE_MASS_MIN == 0.30
    assert N_EFF_MIN == 1500.0
    assert TOP_5_PCT_MAX == 0.35
    assert GATE_FAIL_EXIT_CODE == 8


def test_existing_da14_gate_v4_baseline_passes() -> None:
    """v4 baseline (de_en=0.6010, de=0.385, n_eff=4358, top_5_pct=0.1249) が
    DA-14/16 既存 gate で pass を維持する (regression guard)."""
    from erre_sandbox.training.plan_b_gate import audit_corpus

    v4_audit = {
        "n_eff": 4358.0,
        "top_5_pct_weight_share": 0.1249,
        "per_language_weighted_mass": {
            "de": 0.385,
            "en": 0.216,
            "ja": 0.389,
            "mixed": 0.010,
        },
    }
    result = audit_corpus(
        v4_audit,
        weight_audit_path="x.json",
        merge_sha="sha",
    )
    assert result["plan_b_gate"] == "pass"
    assert result["failed_axes"] == []
