"""M13-ES4 condition-axis resolution + seed discipline (§1 / §7).

Pins the ablation identity (A0 ≡ ``loco_delta=None``), the M2 distribution-match,
common-seed pairing across A0/A1/A2, seed-range disjointness, and the frozen
generation counts. LLM-free (no seam is invoked).
"""

from __future__ import annotations

from collections import defaultdict

from erre_sandbox.evidence.es4_actuator import constants as _c
from erre_sandbox.evidence.es4_actuator.scenario import (
    band_lambda_pool,
    build_aut_requests,
    build_rat_requests,
    derive_m2_seed,
    derive_ref_seed,
    derive_unit_seed,
    lambda_for,
    resolve_lambda_sampling,
)
from erre_sandbox.inference.sampling import compose_sampling
from erre_sandbox.schemas import SamplingDelta

_BASE = _c.PERSONA_ROSTER[0][1]


def test_band_pool_within_band() -> None:
    for band in (_c.LAMBDA_BAND_A1, _c.LAMBDA_BAND_A2):
        pool = band_lambda_pool(band)
        assert pool
        assert all(band[0] <= x <= band[1] for x in pool)


def test_lambda_for_deterministic_and_in_band() -> None:
    a = lambda_for(_c.LAMBDA_BAND_A2, "kant", "brick", 3)
    b = lambda_for(_c.LAMBDA_BAND_A2, "kant", "brick", 3)
    assert a == b
    assert _c.LAMBDA_BAND_A2[0] <= a <= _c.LAMBDA_BAND_A2[1]


def test_a0_is_ablation_identity() -> None:
    """A0 (λ=0) resolves bit-identically to the ``loco_delta=None`` path (§0)."""
    none_path = compose_sampling(_BASE, SamplingDelta())
    a0 = resolve_lambda_sampling(_BASE, _c.LAMBDA_A0)
    assert a0.temperature == none_path.temperature
    assert a0.top_p == none_path.top_p
    assert a0.repeat_penalty == none_path.repeat_penalty


def test_gain_p_zero_means_top_p_unchanged() -> None:
    """ES-4 temperature-only actuator: λ never moves top_p (Codex HIGH-1)."""
    hi = resolve_lambda_sampling(_BASE, 1.0)
    assert hi.top_p == _BASE.top_p
    assert hi.temperature > _BASE.temperature


def test_phase0_has_no_m2_or_f() -> None:
    conds = {r.condition for r in build_aut_requests("phase0")}
    assert conds == {"A0", "A1", "A2"}


def test_phase1_has_all_conditions() -> None:
    conds = {r.condition for r in build_aut_requests("phase1")}
    assert conds == {"A0", "A1", "A2", "M2", "F"}


def test_phase1_aut_generation_count() -> None:
    """3 persona × 16 item × (A0 20 + A1 20 + A2 20 + M2 20 + F 10) = 4320 (§4.2)."""
    reqs = build_aut_requests("phase1")
    assert len(reqs) == 4320


def test_phase1_rat_generation_count() -> None:
    """3 persona × 16 item × {A0, A2} × 20 = 1920 (§4.2)."""
    assert len(build_rat_requests("phase1")) == 1920


def test_common_seed_pairing_across_a0_a1_a2() -> None:
    reqs = build_aut_requests("phase1")
    by_key: dict[tuple[str, str, int], dict[str, int]] = defaultdict(dict)
    for r in reqs:
        if r.condition in {"A0", "A1", "A2"}:
            by_key[(r.persona_id, r.item_id, r.seed_idx)][r.condition] = r.seed
    for conds in by_key.values():
        assert conds["A0"] == conds["A1"] == conds["A2"]


def test_m2_distribution_matches_a2_per_cluster() -> None:
    reqs = build_aut_requests("phase1")
    a2: dict[tuple[str, str], list[float]] = defaultdict(list)
    m2: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in reqs:
        if r.condition == "A2":
            a2[(r.persona_id, r.item_id)].append(round(r.resolved.temperature, 12))
        elif r.condition == "M2":
            m2[(r.persona_id, r.item_id)].append(round(r.resolved.temperature, 12))
    assert a2.keys() == m2.keys()
    for key, a2_temps in a2.items():
        assert sorted(a2_temps) == sorted(m2[key]), key


def test_seed_ranges_disjoint() -> None:
    """Verdict / M2 / reference seeds never collide (holdout discipline)."""
    verdict = {derive_unit_seed("kant", "brick", i) for i in range(_c.N_SEED_PHASE1)}
    m2 = {derive_m2_seed("kant", "brick", i) for i in range(_c.N_SEED_PHASE1)}
    ref = {derive_ref_seed("brick", i) for i in range(_c.REF_SEEDS)}
    assert verdict.isdisjoint(m2)
    assert verdict.isdisjoint(ref)
    assert m2.isdisjoint(ref)
