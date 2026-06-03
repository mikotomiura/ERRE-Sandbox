"""M10-A PR-S4b H2 owner-shuffle-resynth evaluator coverage (CPU, no GPU/model/DB).

Pins the frozen stage-A H2 conformance rule as a single-source implementation: the
deterministic core (``_pairwise_value_dist`` / ``_distance_for``) is asserted
bit-equivalent to a hand computation, the seeded null + powered are reproducible, and
the 3-way verdict (INVALID > PASS > INCONCLUSIVE) is exercised across the spike's four
controls (positive systematic / no-separation / degenerate / no-self) plus the
finite-null edges. K=1000 with a fixed ``derive_seed`` per (persona, run_idx).

"bit-equivalence" boundary (DA-S4B-3): the deterministic statistic is literally
equivalent to the spike; the null/powered RNG uses production's ``derive_seed`` scheme
(not the throwaway spike's module RNG), so draws are reproducible but not claimed
identical to the spike's.
"""

from __future__ import annotations

import math
from statistics import median

import numpy as np

from erre_sandbox.contracts.cognition_layers import PromotedEvidenceUnit
from erre_sandbox.evidence.individuation.path_a_h2_gate import (
    H2_ALPHA,
    H2_NULL_CONTROL_CONFORMANCE,
    H2_NULL_CONTROL_KIND,
    H2_NULL_SHUFFLE_K,
    H2NullControlResult,
    H2Verdict,
    _distance_for,
    _pairwise_value_dist,
    _powered_for,
    _units_to_swm,
    _value_map,
    h2_owner_shuffle_resynth_3way,
)
from erre_sandbox.schemas import Zone

_IDS = ("ind0", "ind1", "ind2")
_BASE = "rikyu"
_ZONES = (Zone.STUDY, Zone.PERIPATOS, Zone.CHASHITSU, Zone.AGORA, Zone.GARDEN)
_BIAS = (0.6, -0.5, 0.1)


def _unit(other: str, zone: Zone, aff: float) -> PromotedEvidenceUnit:
    kind = (
        "trust"
        if aff >= 0.70
        else "curious"
        if aff > 0.0
        else "clash"
        if aff <= -0.70
        else "wary"
    )
    return PromotedEvidenceUnit(
        other_agent_id=other,
        belief_kind=kind,
        confidence=0.8,
        affinity=aff,
        familiarity=0.5,
        last_interaction_zone=zone,
        last_interaction_tick=100,
    )


def _pos_units(owner_idx: int, d: int, seed: int) -> tuple[PromotedEvidenceUnit, ...]:
    """Systematic-divergence units for one owner (drives PASS at high D)."""
    rng = np.random.default_rng(seed)
    out: list[PromotedEvidenceUnit] = []
    for j in range(d):
        zone = _ZONES[int(rng.integers(0, len(_ZONES)))]
        aff = float(np.clip(_BIAS[owner_idx] + rng.normal(0.0, 0.15), -0.95, 0.95))
        out.append(_unit(f"o_{owner_idx}_{j}", zone, aff))
    return tuple(out)


def _members(
    per_owner: tuple[tuple[PromotedEvidenceUnit, ...] | None, ...],
) -> list[tuple[str, tuple[PromotedEvidenceUnit, ...] | None]]:
    return [(_IDS[i], per_owner[i]) for i in range(3)]


def _positive_members(
    d: int = 20, base_seed: int = 1000
) -> list[tuple[str, tuple[PromotedEvidenceUnit, ...] | None]]:
    return _members(tuple(_pos_units(i, d, base_seed + i) for i in range(3)))


# --- deterministic-core bit-equivalence pins (no RNG) ------------------------


def test_pairwise_value_dist_matches_hand_computation() -> None:
    """``_pairwise_value_dist`` = median pairwise mean|Δvalue| over the intersection."""
    maps = [
        {("self", "rd"): 0.5, ("env", "agora"): 0.2},
        {("self", "rd"): 0.1, ("env", "agora"): 0.8, ("env", "study"): 0.3},
        {("self", "rd"): 0.9},
    ]
    # pairs: (0,1) shared {rd,agora} mean(|0.4|,|0.6|)=0.5; (0,2) shared {rd} 0.4;
    # (1,2) shared {rd} 0.8 → median(0.5,0.4,0.8)=0.5.
    assert _pairwise_value_dist(maps) == median([0.5, 0.4, 0.8])


def test_pairwise_value_dist_empty_intersection_is_nan() -> None:
    maps = [{("env", "study"): 0.1}, {("env", "agora"): 0.2}, {("env", "garden"): 0.3}]
    assert math.isnan(_pairwise_value_dist(maps))


def test_observed_distance_is_deterministic() -> None:
    """The observed statistic is RNG-free: identical input → identical distance."""
    members = _positive_members(d=12)
    owners = [m[0] for m in members]
    per_owner = [list(m[1] or ()) for m in members]
    a = _distance_for(owners, per_owner)
    b = _distance_for(owners, per_owner)
    assert a == b
    assert math.isfinite(a)


def test_units_to_swm_value_map_independent_of_owner_label() -> None:
    """Re-owning rebuilds record ids so the synthesised value map is label-stable."""
    units = _pos_units(0, 6, 42)
    m1 = _value_map(_units_to_swm("ind0", units))
    m2 = _value_map(_units_to_swm("ind9", units))
    assert m1 == m2  # same evidence under a different owner → same SWM values


# --- 3-way verdict branches (spike four controls) ----------------------------


def test_positive_systematic_high_density_passes() -> None:
    """(1) positive systematic at D=20 → PASS ∧ powered (multiple seeds)."""
    for run_idx in (0, 1):
        res = h2_owner_shuffle_resynth_3way(
            _positive_members(d=20), base_persona_id=_BASE, run_idx=run_idx
        )
        assert res.outcome is H2Verdict.PASS
        assert res.powered is True
        assert res.p_high is not None
        assert res.p_high <= H2_ALPHA


def test_no_separation_is_invalid() -> None:
    """(NC1) identical evidence across owners → INVALID (null did not collapse)."""
    shared = _pos_units(0, 12, 7)
    res = h2_owner_shuffle_resynth_3way(
        _members((shared, shared, shared)), base_persona_id=_BASE, run_idx=0
    )
    assert res.outcome is H2Verdict.INVALID
    assert res.d_obs is not None
    assert res.null_central is not None
    assert res.null_central >= res.d_obs


def test_degenerate_d1_is_invalid() -> None:
    """(NC2) one dyad per owner, distinct single zone, no self → INVALID (d_obs NaN)."""
    members = _members(
        tuple((_unit(f"only_{i}", _ZONES[i], _BIAS[i]),) for i in range(3))
    )
    res = h2_owner_shuffle_resynth_3way(members, base_persona_id=_BASE, run_idx=0)
    assert res.outcome is H2Verdict.INVALID
    assert res.d_obs is None


def test_no_self_empty_overlap_is_invalid() -> None:
    """(4) 2 units to the SAME other (1 distinct dyad → no self), disjoint zones."""
    members = []
    for i in range(3):
        u1 = _unit(f"shared_{i}", _ZONES[i], _BIAS[i])
        u2 = PromotedEvidenceUnit(
            other_agent_id=f"shared_{i}",
            belief_kind=u1.belief_kind,
            confidence=0.8,
            affinity=_BIAS[i],
            familiarity=0.5,
            last_interaction_zone=_ZONES[i],
            last_interaction_tick=101,
        )
        members.append((_IDS[i], (u1, u2)))
    res = h2_owner_shuffle_resynth_3way(members, base_persona_id=_BASE, run_idx=0)
    assert res.outcome is H2Verdict.INVALID
    assert res.d_obs is None


def test_low_density_is_inconclusive() -> None:
    """A low-density positive (D=3) is INCONCLUSIVE (no separation / underpowered)."""
    res = h2_owner_shuffle_resynth_3way(
        _positive_members(d=3, base_seed=20), base_persona_id="p0", run_idx=0
    )
    assert res.outcome is H2Verdict.INCONCLUSIVE
    assert res.powered is None  # not computed when p_high > ALPHA


# --- substrate short-circuits ------------------------------------------------


def test_member_without_evidence_is_inconclusive() -> None:
    members = _positive_members(d=8)
    members[0] = (_IDS[0], None)
    res = h2_owner_shuffle_resynth_3way(members, base_persona_id=_BASE, run_idx=0)
    assert res.outcome is H2Verdict.INCONCLUSIVE
    assert "insufficient" in res.reason


def test_empty_pool_is_invalid() -> None:
    """All members present but empty → d_obs NaN → INVALID (frozen §3.3, Codex HIGH-1).

    Distinct from a ``None`` member (a non-frozen precondition shortfall →
    INCONCLUSIVE): an all-empty pool is real-but-degenerate substrate the frozen rule
    rejects as INVALID, not a "not captured" shortfall.
    """
    res = h2_owner_shuffle_resynth_3way(
        _members(((), (), ())), base_persona_id=_BASE, run_idx=0
    )
    assert res.outcome is H2Verdict.INVALID
    assert res.d_obs is None
    assert res.n_finite_null == 0


def test_duplicate_units_do_not_inflate_power() -> None:
    """Codex HIGH-2: many duplicate units but distinct-other min=1 cannot emit PASS.

    Each owner's evidence is many copies of a single other (raw count is large but the
    distinct-other density D_i=1), so the powered self-calibration is keyed on the
    distinct vector (1,1,1) → never PASS regardless of a chance ``p_high <= ALPHA``.
    """
    members = []
    for i in range(3):
        u = _unit(f"dup_{i}", _ZONES[i], _BIAS[i])
        members.append((_IDS[i], (u,) * 25))  # 25 raw copies, 1 distinct other
    res = h2_owner_shuffle_resynth_3way(members, base_persona_id=_BASE, run_idx=0)
    assert res.outcome is not H2Verdict.PASS
    # if it reached the powered gate at all, the distinct vector (1,1,1) is unpowered.
    assert res.powered in (None, False)


# --- reproducibility + powered self-calibration ------------------------------


def test_same_seed_is_bit_reproducible() -> None:
    """Same (persona, run_idx, salt) → identical d_obs / null_central / p_high."""
    members = _positive_members(d=12, base_seed=300)
    a = h2_owner_shuffle_resynth_3way(members, base_persona_id=_BASE, run_idx=1)
    b = h2_owner_shuffle_resynth_3way(members, base_persona_id=_BASE, run_idx=1)
    assert a.d_obs == b.d_obs
    assert a.null_central == b.null_central
    assert a.p_high == b.p_high
    assert a.outcome is b.outcome


def test_powered_for_separates_high_density_not_low() -> None:
    """§3.4 powered self-calibration: high counts separate, min(D_i)=1 does not."""
    rng_hi = np.random.Generator(np.random.PCG64(12345))
    assert _powered_for(_IDS, (20, 20, 20), rng_hi) is True
    rng_lo = np.random.Generator(np.random.PCG64(12345))
    assert _powered_for(_IDS, (1, 1, 1), rng_lo) is False


def test_min_di_dominates_powered() -> None:
    """A skewed vector (20,20,1) is underpowered (min(D_i)=1 gates homogenisation)."""
    rng = np.random.Generator(np.random.PCG64(999))
    assert _powered_for(_IDS, (20, 20, 1), rng) is False


# --- frozen constants --------------------------------------------------------


def test_frozen_constants() -> None:
    assert H2_ALPHA == 0.05
    assert H2_NULL_SHUFFLE_K == 1000
    assert H2_NULL_CONTROL_KIND == "h2_owner_shuffle_resynth"
    assert H2_NULL_CONTROL_CONFORMANCE == "conformant"


def test_result_dataclass_is_frozen() -> None:
    res = H2NullControlResult(H2Verdict.INCONCLUSIVE, "x")
    import pytest

    with pytest.raises((AttributeError, TypeError)):
        res.outcome = H2Verdict.PASS  # type: ignore[misc]
