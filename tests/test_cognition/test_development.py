"""Pure + adversarial tests for M11-B evidence-driven development transitions.

Covers :mod:`erre_sandbox.cognition.development`: the ``belief_signature`` churn
fingerprint, ``DevelopmentEvidence`` validation, the ``min``-AND maturity gauge,
the 5-condition transition gate, regression latching, single-step advance, the
1000-tick acceptance, and the adversarial negative-controls that pin
*LLM-cannot-fire* (design-final §2.6, DA-M11B-1, Codex HIGH-1).

See ``.steering/20260527-m11-b-development-state-transition/`` (design.md,
decisions.md, codex-review.md).
"""

from __future__ import annotations

import math

import pytest

from erre_sandbox.cognition.development import (
    DEVELOPMENT_COHERENCE_THRESHOLD,
    MEMORY_VOLUME_TARGET,
    MIN_BELIEFS_S2,
    MIN_COHERENT_TICKS_S2,
    MIN_TICKS_S2,
    STABILITY_TARGET,
    DevelopmentEvidence,
    belief_signature,
    maybe_advance_development,
)
from erre_sandbox.contracts.cognition_layers import DevelopmentState
from erre_sandbox.schemas import SemanticMemoryRecord

# A signature value that is irrelevant to most tests (stability uses sameness,
# not the value itself); fixed so a held-constant signature extends the streak.
_FIXED_SIG = 424242


def _belief(
    id_: str, kind: str = "trust", confidence: float = 0.8
) -> SemanticMemoryRecord:
    return SemanticMemoryRecord(
        id=id_,
        agent_id="a_kant_001",
        summary=f"belief {id_}",
        belief_kind=kind,  # type: ignore[arg-type]
        confidence=confidence,
    )


def _evidence(
    *,
    new_episodic_count: int = 1,
    fresh_coherence: float = 0.9,
    belief_count: int = 3,
    mean_belief_confidence: float = 0.8,
    belief_signature_value: int = _FIXED_SIG,
) -> DevelopmentEvidence:
    """A 'healthy' fresh-evidence tick by default (advances volume + stability)."""
    return DevelopmentEvidence(
        new_episodic_count=new_episodic_count,
        fresh_coherence=fresh_coherence,
        belief_count=belief_count,
        mean_belief_confidence=mean_belief_confidence,
        belief_signature=belief_signature_value,
    )


def _drive(
    n: int,
    *,
    state: DevelopmentState | None = None,
    **evidence_kwargs: object,
) -> tuple[DevelopmentState, list[str]]:
    """Apply ``n`` identical fresh-evidence ticks; return (final state, stage trail)."""
    current = state or DevelopmentState()
    trail = [current.stage]
    for _ in range(n):
        current = maybe_advance_development(current, _evidence(**evidence_kwargs))  # type: ignore[arg-type]
        trail.append(current.stage)
    return current, trail


# ---------------------------------------------------------------------------
# belief_signature (Codex HIGH-2 churn detection / MEDIUM-2 digest)
# ---------------------------------------------------------------------------


def test_belief_signature_is_deterministic_and_order_independent() -> None:
    a = [_belief("b1"), _belief("b2", "clash", 0.6)]
    b = [_belief("b2", "clash", 0.6), _belief("b1")]  # reordered
    assert belief_signature(a) == belief_signature(b)
    # Non-negative, 48-bit, JSON-safe (< 2**53).
    sig = belief_signature(a)
    assert 0 <= sig < 2**48


def test_belief_signature_detects_same_count_churn() -> None:
    before = [_belief("b1"), _belief("b2")]
    after = [_belief("b1"), _belief("b3")]  # same count, one swapped
    assert belief_signature(before) != belief_signature(after)


def test_belief_signature_confidence_bucket_tolerates_subbucket_drift() -> None:
    # Within one CONFIDENCE_BUCKET (0.1): 0.80 and 0.84 bucket to the same value.
    assert belief_signature([_belief("b1", confidence=0.80)]) == belief_signature(
        [_belief("b1", confidence=0.84)]
    )
    # Across a bucket boundary the signature changes.
    assert belief_signature([_belief("b1", confidence=0.80)]) != belief_signature(
        [_belief("b1", confidence=0.95)]
    )


def test_belief_signature_empty_is_stable_value() -> None:
    assert belief_signature([]) == belief_signature([])
    assert 0 <= belief_signature([]) < 2**48


# ---------------------------------------------------------------------------
# DevelopmentEvidence validation (Codex MEDIUM-4)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fresh_coherence": math.nan},
        {"fresh_coherence": 1.5},
        {"fresh_coherence": -1.5},
        {"new_episodic_count": -1},
        {"belief_count": -1},
        {"mean_belief_confidence": 1.2},
        {"mean_belief_confidence": -0.1},
        {"mean_belief_confidence": math.nan},
        {"belief_signature_value": -1},
    ],
)
def test_evidence_rejects_invalid_inputs(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="must be"):
        _evidence(**kwargs)  # type: ignore[arg-type]


def test_evidence_accepts_boundary_values() -> None:
    _evidence(fresh_coherence=-1.0, mean_belief_confidence=0.0, belief_count=0)
    _evidence(fresh_coherence=1.0, mean_belief_confidence=1.0)


# ---------------------------------------------------------------------------
# maturity gauge = min (Codex HIGH-2 no compensation)
# ---------------------------------------------------------------------------


def test_maturity_is_min_of_volume_and_stability() -> None:
    # High volume, zero stability: a *different* signature every tick (churn) so
    # the stability streak never grows.
    state = DevelopmentState()
    for sig in range(1, MEMORY_VOLUME_TARGET + 6):
        state = maybe_advance_development(state, _evidence(belief_signature_value=sig))
    assert state.maturity_score == pytest.approx(0.0)  # m_stab == 0 pins min
    assert state.stage == "S1_seed"


def test_high_coherence_alone_cannot_advance(  # SWM-echo adversarial (Codex HIGH-1)
) -> None:
    # Max coherence every tick but NO episodic volume and NO stable beliefs.
    state, trail = _drive(
        500,
        new_episodic_count=0,
        fresh_coherence=1.0,
        belief_count=0,
        mean_belief_confidence=0.0,
    )
    assert state.stage == "S1_seed"
    assert set(trail) == {"S1_seed"}
    assert state.maturity_score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 5-condition transition gate — each condition blocks independently
# ---------------------------------------------------------------------------


def _ripe_s1_state() -> DevelopmentState:
    """An S1 state one healthy tick away from S2 on every axis."""
    return DevelopmentState(
        stage="S1_seed",
        maturity_score=1.0,
        transition_evidence={
            "episodic_seen_count": MEMORY_VOLUME_TARGET,
            "stable_streak": STABILITY_TARGET,
            "last_belief_signature": _FIXED_SIG,
            "ticks_in_stage": MIN_TICKS_S2,
            "stage_high_coherence_ticks": MIN_COHERENT_TICKS_S2,
        },
    )


def test_ripe_state_advances_on_healthy_tick() -> None:
    out = maybe_advance_development(_ripe_s1_state(), _evidence())
    assert out.stage == "S2_exploring"
    # Stage-local counters reset; lifetime preserved.
    assert out.transition_evidence["ticks_in_stage"] == 0
    assert out.transition_evidence["stage_high_coherence_ticks"] == 0
    assert out.transition_evidence["episodic_seen_count"] >= MEMORY_VOLUME_TARGET
    assert out.transition_evidence["stable_streak"] >= STABILITY_TARGET


def test_this_tick_low_coherence_blocks_even_with_high_rate() -> None:
    # Codex HIGH-3 original: rate is satisfied, but this tick is incoherent.
    out = maybe_advance_development(
        _ripe_s1_state(),
        _evidence(fresh_coherence=DEVELOPMENT_COHERENCE_THRESHOLD - 0.01),
    )
    assert out.stage == "S1_seed"


def test_insufficient_beliefs_blocks() -> None:  # Codex MEDIUM-3
    out = maybe_advance_development(
        _ripe_s1_state(), _evidence(belief_count=MIN_BELIEFS_S2 - 1)
    )
    assert out.stage == "S1_seed"


def test_insufficient_dwell_blocks() -> None:
    state = _ripe_s1_state()
    state.transition_evidence["ticks_in_stage"] = MIN_TICKS_S2 - 2
    out = maybe_advance_development(state, _evidence())
    assert out.stage == "S1_seed"


def test_insufficient_stage_coherence_ticks_blocks() -> None:
    state = _ripe_s1_state()
    # Drop sustained-coherence count and feed an incoherent tick so it can't catch up.
    state.transition_evidence["stage_high_coherence_ticks"] = MIN_COHERENT_TICKS_S2 - 2
    out = maybe_advance_development(state, _evidence(fresh_coherence=0.9))
    assert out.stage == "S1_seed"


def test_low_maturity_blocks() -> None:
    state = _ripe_s1_state()
    state.transition_evidence["stable_streak"] = 1  # m_stab tiny -> maturity tiny
    out = maybe_advance_development(state, _evidence())
    assert out.stage == "S1_seed"


# ---------------------------------------------------------------------------
# regression latch + single-step + purity
# ---------------------------------------------------------------------------


def test_regression_forbidden_stage_latches() -> None:
    s3 = DevelopmentState(
        stage="S3_consolidated",
        maturity_score=0.9,
        transition_evidence={
            "episodic_seen_count": MEMORY_VOLUME_TARGET,
            "stable_streak": STABILITY_TARGET,
            "last_belief_signature": _FIXED_SIG,
            "ticks_in_stage": 100,
            "stage_high_coherence_ticks": 100,
        },
    )
    # Collapse all evidence to nothing — stage must not regress.
    out = maybe_advance_development(
        s3,
        _evidence(
            new_episodic_count=0,
            fresh_coherence=-1.0,
            belief_count=0,
            mean_belief_confidence=0.0,
            belief_signature_value=999,
        ),
    )
    assert out.stage == "S3_consolidated"


def test_single_step_only_one_stage_per_call() -> None:
    # Even from a maximally-ripe S1 state, one call reaches S2, never S3.
    out = maybe_advance_development(_ripe_s1_state(), _evidence())
    assert out.stage == "S2_exploring"


def test_input_state_not_mutated() -> None:  # Codex LOW-2
    state = _ripe_s1_state()
    before = dict(state.transition_evidence)
    before_stage = state.stage
    maybe_advance_development(state, _evidence())
    assert state.transition_evidence == before
    assert state.stage == before_stage


def test_first_tick_seeds_all_counters() -> None:  # Codex LOW-1
    out = maybe_advance_development(DevelopmentState(), _evidence())
    keys = {
        "episodic_seen_count",
        "stable_streak",
        "last_belief_signature",
        "ticks_in_stage",
        "stage_high_coherence_ticks",
    }
    assert set(out.transition_evidence) == keys
    assert out.transition_evidence["ticks_in_stage"] == 1
    assert out.transition_evidence["stable_streak"] == 0  # no prior signature to match
    assert out.stage == "S1_seed"


def test_transition_preserves_lifetime_axes_and_gauge() -> None:  # DA-M11B-3
    ripe = _ripe_s1_state()
    out = maybe_advance_development(ripe, _evidence())
    assert out.stage == "S2_exploring"
    # Lifetime axes carried through the transition, so maturity does not drop.
    assert out.maturity_score == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 1000-tick acceptance (design-final §5 M11-B)
# ---------------------------------------------------------------------------


def test_acceptance_1000_ticks_s1_to_s2_to_s3() -> None:
    """A single individual fed healthy evidence matures S1 -> S2 -> S3."""
    state = DevelopmentState()
    seen: list[str] = []
    transition_ticks: dict[str, int] = {}
    for tick in range(1000):
        state = maybe_advance_development(state, _evidence())
        if state.stage not in transition_ticks:
            transition_ticks[state.stage] = tick
        seen.append(state.stage)

    # All three stages reached, in order, never regressing.
    assert state.stage == "S3_consolidated"
    order = {"S1_seed": 0, "S2_exploring": 1, "S3_consolidated": 2}
    ranks = [order[s] for s in seen]
    assert ranks == sorted(ranks)  # monotonic non-decreasing
    assert transition_ticks["S2_exploring"] < transition_ticks["S3_consolidated"]


def test_acceptance_low_volume_never_reaches_s3() -> None:
    # Stable + coherent but starved of episodic volume: m_vol caps maturity low.
    state, _ = _drive(1000, new_episodic_count=0)
    assert state.stage == "S1_seed"
