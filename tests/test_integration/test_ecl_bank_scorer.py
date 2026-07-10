"""C-proper scorer tests (§S7) — the §CB4.4 verdict over synthetic annotation.

Result-independent by construction: every fixture is an **exact-count** synthetic
annotation (no live LLM, no sampling in the fixture), so the five verdict branches
fire deterministically and the entropy / TV known-values are analytic. RNG enters
only through the seeded power gate and the seeded within-context permutation test
(``seed=POWER_SEED_DEFAULT``), whose determinism is asserted directly.

These tests freeze the instrument *before* the powered sealed run
(``.steering/20260710-m13-c-proper/design-final.md`` §S8 seal). The statistical
branches run with ``require_powered_scale=False`` (small K keeps them fast and lets
the underpowered branch be reachable); the powered-scale precondition itself (Codex
HIGH-2) has its own tests with the default ``True``.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from erre_sandbox.integration.embodied import bank_scorer as s
from erre_sandbox.integration.embodied.bank_power import (
    ALPHA_SIGNIFICANCE,
    DELTA_TV_MIN,
    H_MIN_BITS,
    K_MIN,
    M_MIN,
    POWER_MIN,
    POWER_SEED_DEFAULT,
    RHO_MIN,
)

_ZONES = [z.value for z in s.ZONES]
# A modest replicate count keeps the tests fast; every fixture sits far from the
# power=0.8 / α=0.05 boundaries, so Monte-Carlo noise never flips a branch.
_NREP = 400


def _rows(
    ctx: str, cond: str, counts: dict[str | None, int], *, start: int = 0
) -> list[dict[str, Any]]:
    """Exact-count annotation rows: ``counts`` maps a zone value (or ``None``) to
    the number of draws with that ``pre_bias_destination_zone``. ``mc_index`` runs
    0..(total-1) within the cell (satisfies the exact-index gate)."""
    rows: list[dict[str, Any]] = []
    mc = start
    for zone_value, n in counts.items():
        for _ in range(n):
            rows.append(
                {
                    "frozen_ctx_id": ctx,
                    "condition": cond,
                    "mc_index": mc,
                    "pre_bias_destination_zone": zone_value,
                    "resolved_from": "pre_bias_direct_parse",
                }
            )
            mc += 1
    return rows


def _manifest(
    *, m_draws: int, k_contexts: int, think: bool | None = False
) -> dict[str, Any]:
    return {
        "run": {"m_draws": m_draws, "k_contexts": k_contexts},
        "env_pins": {"think": think},
    }


def _score(rows: list[dict[str, Any]], manifest: dict[str, Any]) -> s.CProperVerdict:
    """Score a statistical-branch fixture (small scale allowed, fast replicates)."""
    return s.score_bank_annotation(
        annotation_rows=rows,
        manifest=manifest,
        n_replicates=_NREP,
        require_powered_scale=False,
    )


def _uniform(m: int) -> dict[str | None, int]:
    """Even split of ``m`` draws across the 5 zones (m must be divisible by 5)."""
    per = m // 5
    return dict.fromkeys(_ZONES, per)


def _skew(hi_zone: str, m: int, hi_frac: float) -> dict[str | None, int]:
    """``hi_frac`` mass on ``hi_zone``, the rest split over the other four."""
    hi = round(m * hi_frac)
    rest = m - hi
    per = rest // 4
    counts: dict[str | None, int] = {hi_zone: hi + (rest - per * 4)}
    for z in _ZONES:
        if z != hi_zone:
            counts[z] = per
    return counts


# --------------------------------------------------------------------------- #
# Branch 1 — validity gate → INCONCLUSIVE (non-spend)
# --------------------------------------------------------------------------- #


def test_think_regime_mismatch_is_inconclusive() -> None:
    rows = _rows("c0", "on", _uniform(300)) + _rows("c0", "off", _uniform(300))
    v = _score(rows, _manifest(m_draws=300, k_contexts=1, think=True))
    assert v.verdict == "INCONCLUSIVE"
    assert "think-regime-mismatch" in v.reason[0]


def test_incomplete_draws_is_inconclusive() -> None:
    rows = _rows("c0", "on", _uniform(300)) + _rows("c0", "off", _uniform(295))
    v = _score(rows, _manifest(m_draws=300, k_contexts=1))
    assert v.verdict == "INCONCLUSIVE"
    assert "incomplete-draws" in v.reason[0]


def test_excessive_none_is_inconclusive() -> None:
    # 60% None in the off cell (> NONE_RATE_MAX=0.5) → degenerate estimator.
    on = _rows("c0", "on", _uniform(300))
    off = _rows("c0", "off", {None: 180, **dict.fromkeys(_ZONES[:4], 30)})
    v = _score(on + off, _manifest(m_draws=300, k_contexts=1))
    assert v.verdict == "INCONCLUSIVE"
    assert "excessive-none" in v.reason[0]


# --------------------------------------------------------------------------- #
# Branch 2 — (i) collapse → NO_CHANNEL_CONFORMANCE (valid FAIL)
# --------------------------------------------------------------------------- #


def test_collapse_below_rho_is_no_conformance() -> None:
    # K=4: only c0 has non-degenerate H; c1..c3 are single-zone (H=0) → rho=0.25.
    rows: list[dict[str, Any]] = []
    rows += _rows("c0", "on", _uniform(10)) + _rows("c0", "off", _uniform(10))
    for ctx in ("c1", "c2", "c3"):
        rows += _rows(ctx, "on", {_ZONES[0]: 10}) + _rows(ctx, "off", {_ZONES[0]: 10})
    v = _score(rows, _manifest(m_draws=10, k_contexts=4))
    assert v.verdict == "NO_CHANNEL_CONFORMANCE"
    assert v.effective_k == 1
    assert v.rho_hat == pytest.approx(0.25)
    assert "collapse" in v.reason[0]


# --------------------------------------------------------------------------- #
# Branch 3 — (i) PASS ∧ underpowered → INCONCLUSIVE_UNDERPOWERED (non-spend)
# --------------------------------------------------------------------------- #


def test_underpowered_is_non_spend() -> None:
    # m=10, K'=1 → power≈0.1 « 0.8; H high (uniform) so (i) PASS.
    on = _rows("c0", "on", _uniform(10))
    off = _rows("c0", "off", _skew(_ZONES[0], 10, 0.6))
    v = _score(on + off, _manifest(m_draws=10, k_contexts=1))
    assert v.verdict == "INCONCLUSIVE_UNDERPOWERED"
    assert v.power is not None
    assert v.power < POWER_MIN


# --------------------------------------------------------------------------- #
# Branch 4 — (i) PASS ∧ power ∧ shift → CHANNEL_CONFORMANCE_DETECTED
# --------------------------------------------------------------------------- #


def test_clear_shift_is_detected() -> None:
    rows: list[dict[str, Any]] = []
    for ctx in ("c0", "c1"):
        rows += _rows(ctx, "on", _skew(_ZONES[0], 300, 0.5))
        rows += _rows(ctx, "off", _skew(_ZONES[4], 300, 0.5))
    v = _score(rows, _manifest(m_draws=300, k_contexts=2))
    assert v.verdict == "CHANNEL_CONFORMANCE_DETECTED"
    assert v.tv_bar is not None
    assert v.tv_bar >= DELTA_TV_MIN
    assert v.permutation_reject is True
    assert v.power is not None
    assert v.power >= POWER_MIN


# --------------------------------------------------------------------------- #
# Branch 5 — (i) PASS ∧ power ∧ no shift → NO_CHANNEL_CONFORMANCE (effect-absent)
# --------------------------------------------------------------------------- #


def test_no_shift_is_no_conformance() -> None:
    # on == off exactly (spread) → tv_bar=0, power passes → effect-absent valid FAIL.
    rows: list[dict[str, Any]] = []
    for ctx in ("c0", "c1"):
        rows += _rows(ctx, "on", _uniform(300))
        rows += _rows(ctx, "off", _uniform(300))
    v = _score(rows, _manifest(m_draws=300, k_contexts=2))
    assert v.verdict == "NO_CHANNEL_CONFORMANCE"
    assert v.tv_bar == pytest.approx(0.0, abs=1e-9)
    assert v.permutation_reject is False


# --------------------------------------------------------------------------- #
# reimagine v2 core — reverse-direction shifts must NOT cancel (v1 would)
# --------------------------------------------------------------------------- #


def test_opposite_direction_shifts_survive_stratification() -> None:
    # c0 shifts on→zone0/off→zone4; c1 shifts the opposite way. Pooled TV cancels
    # (≈0), but the stratified TV̄ stays ≈0.5 → DETECTED. This is the v2 guarantee.
    rows: list[dict[str, Any]] = []
    rows += _rows("c0", "on", _skew(_ZONES[0], 300, 0.5))
    rows += _rows("c0", "off", _skew(_ZONES[4], 300, 0.5))
    rows += _rows("c1", "on", _skew(_ZONES[4], 300, 0.5))
    rows += _rows("c1", "off", _skew(_ZONES[0], 300, 0.5))
    v = _score(rows, _manifest(m_draws=300, k_contexts=2))
    assert v.verdict == "CHANNEL_CONFORMANCE_DETECTED"
    assert v.tv_bar is not None
    assert v.tv_bar >= DELTA_TV_MIN
    # pooled view cancels — the exact reason a pooled (v1) primary test would miss it.
    assert v.tv_pool is not None
    assert v.tv_pool < v.tv_bar
    assert v.tv_pool < 0.05


# --------------------------------------------------------------------------- #
# Codex HIGH-2 — powered-scale precondition (default require_powered_scale=True)
# --------------------------------------------------------------------------- #


def test_below_powered_scale_is_inconclusive() -> None:
    # A sub-powered bundle can never yield a spend verdict, even with a clear shift.
    rows: list[dict[str, Any]] = []
    for ctx in ("c0", "c1"):
        rows += _rows(ctx, "on", _skew(_ZONES[0], 300, 0.5))
        rows += _rows(ctx, "off", _skew(_ZONES[4], 300, 0.5))
    v = s.score_bank_annotation(
        annotation_rows=rows,
        manifest=_manifest(m_draws=300, k_contexts=2),  # K=2 < K_MIN=8
        n_replicates=_NREP,
    )
    assert v.verdict == "INCONCLUSIVE"
    assert "below-powered-scale" in v.reason[0]


def test_missing_m_k_is_inconclusive() -> None:
    rows = _rows("c0", "on", _uniform(300)) + _rows("c0", "off", _uniform(300))
    v = s.score_bank_annotation(
        annotation_rows=rows, manifest={"run": {}, "env_pins": {"think": False}}
    )
    assert v.verdict == "INCONCLUSIVE"
    assert "schema-invalid" in v.reason[0]


# --------------------------------------------------------------------------- #
# Codex MEDIUM-1/2 — malformed rows and mc_index integrity
# --------------------------------------------------------------------------- #


def test_malformed_row_is_inconclusive_not_crash() -> None:
    rows = _rows("c0", "on", _uniform(10))
    rows.append(
        {  # unknown zone value → _tally raises → schema-invalid INCONCLUSIVE
            "frozen_ctx_id": "c0",
            "condition": "off",
            "mc_index": 0,
            "pre_bias_destination_zone": "not_a_zone",
            "resolved_from": "pre_bias_direct_parse",
        }
    )
    v = _score(rows, _manifest(m_draws=10, k_contexts=1))
    assert v.verdict == "INCONCLUSIVE"
    assert "schema-invalid" in v.reason[0]


def test_duplicate_mc_index_is_inconclusive() -> None:
    # right total count, but a duplicated mc_index (0 twice, 9 missing).
    on = _rows("c0", "on", _uniform(10))
    off = _rows("c0", "off", _uniform(10))
    off[-1]["mc_index"] = 0  # collide with the first row's index
    v = _score(on + off, _manifest(m_draws=10, k_contexts=1))
    assert v.verdict == "INCONCLUSIVE"
    assert "mc-index-set-invalid" in v.reason[0]


def test_context_id_mismatch_is_inconclusive() -> None:
    rows = _rows("c0", "on", _uniform(10)) + _rows("c0", "off", _uniform(10))
    manifest = _manifest(m_draws=10, k_contexts=1)
    manifest["run"]["context_ids"] = ["a-different-ctx"]
    v = _score(rows, manifest)
    assert v.verdict == "INCONCLUSIVE"
    assert "context-id-mismatch" in v.reason[0]


# --------------------------------------------------------------------------- #
# Known values — entropy, TV, seed determinism, threshold echo, conservative p
# --------------------------------------------------------------------------- #


def test_entropy_of_uniform_is_log2_five() -> None:
    rows = _rows("c0", "on", _uniform(300)) + _rows("c0", "off", _uniform(300))
    v = _score(rows, _manifest(m_draws=300, k_contexts=1))
    assert v.per_context_h["c0"] == pytest.approx(math.log2(5), abs=1e-6)


def test_tv_known_value() -> None:
    # on: 60% zone0 / 10% each other; off: uniform 20%. TV = 0.5*Σ|Δ| = 0.4.
    on = _rows("c0", "on", {_ZONES[0]: 180, **dict.fromkeys(_ZONES[1:], 30)})
    off = _rows("c0", "off", _uniform(300))
    v = _score(on + off, _manifest(m_draws=300, k_contexts=1))
    assert v.tv_per_context["c0"] == pytest.approx(0.4, abs=1e-9)


def test_conservative_p_value_is_never_zero() -> None:
    # (ge+1)/(n+1) floor: even a maximal shift keeps p >= 1/(n+1) > 0 (Codex HIGH-3).
    rows: list[dict[str, Any]] = []
    for ctx in ("c0", "c1"):
        rows += _rows(ctx, "on", _skew(_ZONES[0], 300, 0.9))
        rows += _rows(ctx, "off", _skew(_ZONES[4], 300, 0.9))
    v = _score(rows, _manifest(m_draws=300, k_contexts=2))
    assert v.permutation_p_value is not None
    assert v.permutation_p_value >= 1.0 / (_NREP + 1)
    assert v.permutation_p_value == pytest.approx(1.0 / (_NREP + 1))


def test_seed_determinism() -> None:
    rows: list[dict[str, Any]] = []
    for ctx in ("c0", "c1"):
        rows += _rows(ctx, "on", _skew(_ZONES[0], 300, 0.35))
        rows += _rows(ctx, "off", _skew(_ZONES[4], 300, 0.35))
    a = _score(rows, _manifest(m_draws=300, k_contexts=2))
    b = _score(rows, _manifest(m_draws=300, k_contexts=2))
    assert a.permutation_p_value == b.permutation_p_value
    assert a.power == b.power
    assert a.verdict == b.verdict


def test_thresholds_echo_bank_power_constants() -> None:
    rows = _rows("c0", "on", _uniform(300)) + _rows("c0", "off", _uniform(300))
    v = _score(rows, _manifest(m_draws=300, k_contexts=1))
    t = v.thresholds
    assert t["delta_tv_min"] == DELTA_TV_MIN
    assert t["power_min"] == POWER_MIN
    assert t["h_min_bits"] == H_MIN_BITS
    assert t["rho_min"] == RHO_MIN
    assert t["alpha"] == ALPHA_SIGNIFICANCE
    assert t["m_min"] == float(M_MIN)
    assert t["k_min"] == float(K_MIN)
    assert t["seed"] == float(POWER_SEED_DEFAULT)


def test_verdict_to_dict_quantises_floats() -> None:
    rows = _rows("c0", "on", _uniform(300)) + _rows("c0", "off", _uniform(300))
    v = _score(rows, _manifest(m_draws=300, k_contexts=1))
    d = s.verdict_to_dict(v)
    # every emitted float carries at most 6 decimals
    for value in d["per_context_h"].values():
        assert value is None or round(value, 6) == value
    assert d["scorer_schema_version"] == s.SCORER_SCHEMA_VERSION


def test_none_draws_excluded_but_within_rate_ok() -> None:
    # 30% None in each cell (< 0.5): excluded from the 5-way but not degenerate.
    on = _rows("c0", "on", {None: 90, **_skew(_ZONES[0], 210, 0.5)})
    off = _rows("c0", "off", {None: 90, **_skew(_ZONES[4], 210, 0.5)})
    v = _score(on + off, _manifest(m_draws=300, k_contexts=1))
    assert v.verdict != "INCONCLUSIVE"
    assert v.none_rate_max_observed == pytest.approx(0.3, abs=1e-9)
