"""Verdict gate coverage for the memory-recomposition seam (design §4-4 / §5).

Constructs controlled :class:`SeedResult` banks to exercise every branch — the
INCONCLUSIVE gate (checked first), the GO conjunction (``CI_lower > 0``), and NO_GO
— plus the tune-to-pass audit (``coupling_strength_used == POLYA_ALPHA``).
"""

from __future__ import annotations

import pytest

from erre_sandbox.evidence.memory_recomp_conformance import constants as _c
from erre_sandbox.evidence.memory_recomp_conformance.verdict_report import (
    SeedResult,
    evaluate_verdict,
)

_Z = 5


def _mk(
    seed: int,
    target: int,
    row: tuple[float, ...],
    *,
    valid: bool = True,
    argmax: float = 1.0,
    supp: float = 10.0,
) -> SeedResult:
    return SeedResult(
        seed=seed,
        valid=valid,
        start_zone=0,
        target_zone=target,
        conform_row=row,
        argmax_stability=argmax,
        channel_effective_support=supp,
    )


def _go_bank() -> list[SeedResult]:
    """40 seeds: 32 flat background (delta 0) + 8 signal at rare zones (delta > 0).

    Each signal seed targets a zone held by only 2 of 40 seeds (collision 1/39 ≈
    2.6 % < the 5 % the 0.95 null quantile tolerates), so its null quantile sits
    below its own conform → delta ≈ 1. The mean lifts the bootstrap CI lower > 0.
    """
    bank = [_mk(s, 0, (0.0, 0.0, 0.0, 0.0, 0.0)) for s in range(32)]
    for i in range(8):
        zone = 1 + (i % 4)  # zones 1..4, two seeds each
        row = tuple(1.0 if z == zone else 0.0 for z in range(_Z))
        bank.append(_mk(100 + i, zone, row))
    return bank


def _flat_bank(n: int = 40) -> list[SeedResult]:
    return [_mk(s, 0, (0.0, 0.0, 0.0, 0.0, 0.0)) for s in range(n)]


def test_go_when_all_gates_pass_and_ci_lower_positive() -> None:
    v = evaluate_verdict(
        _go_bank(),
        synthetic_power_pass_rate=0.9,
        coupling_strength_used=_c.POLYA_ALPHA,
    )
    assert v.recomposition_channel_status == "GO"
    assert v.ci_lower > 0.0


def test_no_go_when_gates_pass_but_ci_straddles_zero() -> None:
    v = evaluate_verdict(
        _flat_bank(),
        synthetic_power_pass_rate=0.9,
        coupling_strength_used=_c.POLYA_ALPHA,
    )
    assert v.recomposition_channel_status == "NO_GO"
    assert v.ci_lower <= 0.0


def test_inconclusive_when_too_few_valid_seeds() -> None:
    bank = _flat_bank(_c.MIN_VALID_SEEDS - 1)
    v = evaluate_verdict(
        bank, synthetic_power_pass_rate=0.9, coupling_strength_used=_c.POLYA_ALPHA
    )
    assert v.recomposition_channel_status == "INCONCLUSIVE"
    assert "MIN_VALID_SEEDS" in v.reasons[0]


def test_inconclusive_when_argmax_unstable() -> None:
    bank = [_mk(s, 0, (0.0,) * _Z, argmax=0.3) for s in range(40)]
    v = evaluate_verdict(
        bank, synthetic_power_pass_rate=0.9, coupling_strength_used=_c.POLYA_ALPHA
    )
    assert v.recomposition_channel_status == "INCONCLUSIVE"
    assert "ill-posed" in v.reasons[0]


def test_inconclusive_when_channel_degenerate() -> None:
    bank = [_mk(s, 0, (0.0,) * _Z, supp=1.5) for s in range(40)]
    v = evaluate_verdict(
        bank, synthetic_power_pass_rate=0.9, coupling_strength_used=_c.POLYA_ALPHA
    )
    assert v.recomposition_channel_status == "INCONCLUSIVE"
    assert "degenerate" in v.reasons[0]


def test_inconclusive_when_underpowered() -> None:
    v = evaluate_verdict(
        _go_bank(),
        synthetic_power_pass_rate=0.5,
        coupling_strength_used=_c.POLYA_ALPHA,
    )
    assert v.recomposition_channel_status == "INCONCLUSIVE"
    assert "underpowered" in v.reasons[0]


def test_inconclusive_when_cost_ceiling_exceeded() -> None:
    v = evaluate_verdict(
        _go_bank(),
        synthetic_power_pass_rate=0.9,
        coupling_strength_used=_c.POLYA_ALPHA,
        cost_ceiling_exceeded=True,
    )
    assert v.recomposition_channel_status == "INCONCLUSIVE"
    assert "cost ceiling" in v.reasons[0]


def test_coupling_strength_audit_rejects_non_polya_alpha() -> None:
    with pytest.raises(ValueError, match="POLYA_ALPHA"):
        evaluate_verdict(
            _flat_bank(),
            synthetic_power_pass_rate=0.9,
            coupling_strength_used=_c.POLYA_ALPHA * 2.0,
        )


def test_claim_boundary_fields_are_machine_readable() -> None:
    v = evaluate_verdict(
        _flat_bank(),
        synthetic_power_pass_rate=0.9,
        coupling_strength_used=_c.POLYA_ALPHA,
    )
    assert v.claim_scope == "synthetic_post_idle_walk_only"
    assert v.live_agent_connected is False
