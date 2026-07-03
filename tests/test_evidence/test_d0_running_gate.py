"""Running-ness gate mechanics (design-final.md §3): overlap form + ablation.

Tests that the counterfactual-rollout gate mechanism distinguishes a
history-reading policy (P-A) from a memoryless one (C-memoryless) — a validity
check, not the sealed R1 verdict. The memoryless generator MUST fail the gate
(δ = 0 => TV = 0), and the P-A generator's per-seed TV MUST exceed it, which is
what makes the gate a genuine (non-tautological) certifier of history-dependence.
"""

from __future__ import annotations

import math

import pytest

from erre_sandbox.evidence.d0_substrate import constants as _c
from erre_sandbox.evidence.d0_substrate.running import constants as _rc
from erre_sandbox.evidence.d0_substrate.running.runningness import (
    compute_runningness,
    two_disc_overlap_fraction,
)

_R = _c.CELL_MICRO_RADIUS_M


def test_overlap_fraction_endpoints_and_symmetry() -> None:
    assert two_disc_overlap_fraction(0.0, _R) == 1.0
    assert two_disc_overlap_fraction(2.0 * _R, _R) == 0.0
    assert two_disc_overlap_fraction(3.0 * _R, _R) == 0.0
    # symmetric in delta
    assert two_disc_overlap_fraction(_R, _R) == two_disc_overlap_fraction(-_R, _R)


def test_overlap_fraction_half_radius_separation() -> None:
    # Two equal circles at centre distance R overlap by the standard lens
    # fraction (2*acos(1/2)/pi - sqrt(3)/(2*pi)) ~= 0.3910.
    frac = two_disc_overlap_fraction(_R, _R)
    assert math.isclose(frac, 0.391002, abs_tol=1e-5)


def test_overlap_fraction_monotone_decreasing() -> None:
    prev = 1.0
    for step in range(21):
        d = step * (2.0 * _R) / 20.0
        cur = two_disc_overlap_fraction(d, _R)
        assert cur <= prev + 1e-12
        prev = cur


@pytest.mark.asyncio
async def test_memoryless_fails_gate_and_p_a_reads_more_history() -> None:
    seed_bank = tuple(range(3))
    memoryless = await compute_runningness(seed_bank, "memoryless")
    p_a = await compute_runningness(seed_bank, "P-A")

    # Memoryless: retrieved centroid == terminal centroid => δ = 0 => TV = 0, so
    # the gate must fail (design-final.md §4.1 pre-registered expectation).
    assert memoryless.tv_median == 0.0
    assert memoryless.gate_pass is False
    assert memoryless.tv_ci_lower <= _rc.RUNNINGNESS_TV_FLOOR

    # P-A reads its own history, so it must move the destination off the
    # memoryless baseline strictly more than the memoryless control does.
    assert p_a.tv_median > memoryless.tv_median
