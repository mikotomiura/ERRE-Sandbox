"""Cross-arm verdict routing coverage for ``live_carry.scorer`` (freeze ADR §1-§7).

CPU-only, synthetic :class:`LiveCarryCapture` objects (no DuckDB) so the four-state
decision + every INCONCLUSIVE / INVALID branch is exercised in isolation from the
trace reader. The 12-run matrix ``seed x arm{ON,OFF} x replicate{0,1}`` is built per
scenario from small helpers; the distance itself is the real frozen
``world_model_overlap_jaccard_active`` (re-impl forbidden, ADR §1).
"""

from __future__ import annotations

from dataclasses import replace

from erre_sandbox.contracts.cognition_layers import (
    SubjectiveWorldModel,
    WorldModelEntry,
)
from erre_sandbox.evidence.live_carry.scorer import (
    CONFIRMED,
    INCONCLUSIVE,
    INVALID,
    NO_DETECTABLE,
    score_live_carry,
)
from erre_sandbox.evidence.live_carry.trace_reader import (
    CoherenceRow,
    LiveCarryCapture,
)
from erre_sandbox.evidence.saturation.floor_input_trace_ddl import FloorInputTraceRow
from erre_sandbox.evidence.saturation.trace_ddl import SaturationTraceRow

_SEEDS = (1, 2, 3)
_Key = tuple[str, str]


def _floor_json(keys: list[_Key]) -> str:
    return SubjectiveWorldModel(
        entries=[
            WorldModelEntry(
                axis=axis,  # type: ignore[arg-type]  # Literal axis from test data
                key=key,
                value=0.5,
                confidence=0.5,
                cited_memory_ids=("m1",),
                last_updated_tick=0,
            )
            for axis, key in keys
        ]
    ).model_dump_json()


def _floor_rows(
    seed: int, arm: str, rep: int, keys: list[_Key], *, n_ticks: int = 15
) -> tuple[FloorInputTraceRow, ...]:
    run_id = f"{seed}_{arm}_{rep}"
    return tuple(
        FloorInputTraceRow(
            run_id=run_id,
            seed=seed,
            individual_id="kant",
            tick=t,
            floor_swm_json=_floor_json(keys),
            individual_layer_enabled=True,
        )
        for t in range(n_ticks)
    )


def _engagement_sat(
    seed: int, arm: str, rep: int, *, events: int, offset: float = 0.1
) -> tuple[SaturationTraceRow, ...]:
    """A channel whose fingerprint toggles each tick with a non-zero offset.

    ``events + 1`` ticks → ``events`` consecutive fp-change-with-offset events.
    """
    run_id = f"{seed}_{arm}_{rep}"
    return tuple(
        SaturationTraceRow(
            run_id=run_id,
            seed=seed,
            individual_id="kant",
            axis="self",
            key="eng",
            tick=t,
            base_floor_value=0.5,
            modulated_value=0.5 + offset,
            floor_fingerprint_hash=f"fp{t}",
            individual_layer_enabled=True,
        )
        for t in range(events + 1)
    )


def _benign_sat(
    seed: int, arm: str, rep: int, *, offset: float = 0.1
) -> tuple[SaturationTraceRow, ...]:
    """A constant-fingerprint channel within the cap (0 engagement events)."""
    run_id = f"{seed}_{arm}_{rep}"
    return tuple(
        SaturationTraceRow(
            run_id=run_id,
            seed=seed,
            individual_id="kant",
            axis="self",
            key="benign",
            tick=t,
            base_floor_value=0.5,
            modulated_value=0.5 + offset,
            floor_fingerprint_hash="fp_const",
            individual_layer_enabled=True,
        )
        for t in range(3)
    )


def _capture(
    seed: int,
    arm: str,
    rep: int,
    *,
    keys: list[_Key],
    sat: tuple[SaturationTraceRow, ...],
    n_ticks: int = 15,
    coherence: tuple[CoherenceRow, ...] = (),
) -> LiveCarryCapture:
    return LiveCarryCapture(
        path=f"{seed}_{arm}_{rep}.duckdb",
        seed=seed,
        arm=arm,
        replicate_id=rep,
        floor_rows=_floor_rows(seed, arm, rep, keys, n_ticks=n_ticks),
        saturation_rows=sat,
        coherence_rows=coherence,
    )


def _matrix(
    *,
    on_keys: list[_Key],
    off_keys: list[_Key],
    on_r1_keys: list[_Key] | None = None,
    off_r1_keys: list[_Key] | None = None,
    on_events: int = 6,
    n_ticks: int = 15,
    on_r0_cap_offset: float = 0.1,
) -> list[LiveCarryCapture]:
    """Build a full 12-run matrix from per-role floor-key specs + ON r0 engagement."""
    on_r1 = on_r1_keys if on_r1_keys is not None else on_keys
    off_r1 = off_r1_keys if off_r1_keys is not None else off_keys
    caps: list[LiveCarryCapture] = []
    for seed in _SEEDS:
        caps.append(
            _capture(
                seed,
                "on",
                0,
                keys=on_keys,
                sat=_engagement_sat(
                    seed, "on", 0, events=on_events, offset=on_r0_cap_offset
                ),
                n_ticks=n_ticks,
            )
        )
        caps.append(
            _capture(
                seed,
                "on",
                1,
                keys=on_r1,
                sat=_benign_sat(seed, "on", 1),
                n_ticks=n_ticks,
            )
        )
        caps.append(
            _capture(
                seed,
                "off",
                0,
                keys=off_keys,
                sat=_benign_sat(seed, "off", 0),
                n_ticks=n_ticks,
            )
        )
        caps.append(
            _capture(
                seed,
                "off",
                1,
                keys=off_r1,
                sat=_benign_sat(seed, "off", 1),
                n_ticks=n_ticks,
            )
        )
    return caps


# ---------------------------------------------------------------------------
# Four substantive verdicts
# ---------------------------------------------------------------------------


def test_confirmed_disjoint_floors_bounded_engaged() -> None:
    """Disjoint ON/OFF floors + engagement + bounded → CONFIRMED."""
    caps = _matrix(on_keys=[("self", "on_key")], off_keys=[("self", "off_key")])
    result = score_live_carry(caps)
    assert result.verdict == CONFIRMED
    assert result.m1 is not None
    assert result.m1.go
    assert result.m1.s_on_off == (1.0, 1.0, 1.0)
    assert result.m1.s_off_off_null == (0.0, 0.0, 0.0)
    assert result.m0 is not None
    assert result.m0.status == "pass"
    assert result.m2 is not None
    assert result.m2.status == "pass"


def test_no_detectable_identical_floors_adequate_coverage() -> None:
    """Identical ON/OFF floors, adequate coverage, engaged, bounded → NO_DETECTABLE."""
    caps = _matrix(on_keys=[("self", "shared")], off_keys=[("self", "shared")])
    result = score_live_carry(caps)
    assert result.verdict == NO_DETECTABLE
    assert result.m1 is not None
    assert not result.m1.go
    assert result.m1.coverage_ok


def test_inconclusive_low_coverage() -> None:
    """< MIN_TICK_PAIRS valid aligned pairs → INCONCLUSIVE_LOW_POWER."""
    caps = _matrix(
        on_keys=[("self", "on_key")], off_keys=[("self", "off_key")], n_ticks=5
    )
    result = score_live_carry(caps)
    assert result.verdict == INCONCLUSIVE
    assert result.m1 is not None
    assert not result.m1.coverage_ok


def test_inconclusive_under_engaged() -> None:
    """M0 engagement 1..4 on a seed → INCONCLUSIVE_LOW_POWER."""
    caps = _matrix(
        on_keys=[("self", "on_key")], off_keys=[("self", "off_key")], on_events=3
    )
    result = score_live_carry(caps)
    assert result.verdict == INCONCLUSIVE
    assert result.m0 is not None
    assert result.m0.status == "inconclusive"


def test_inconclusive_on_on_sanity_fail() -> None:
    """ON/ON sanity separation > 1.5 x OFF/OFF null → INCONCLUSIVE_LOW_POWER."""
    caps = _matrix(
        on_keys=[("self", "on_key")],
        off_keys=[("self", "off_key")],
        on_r1_keys=[("self", "on_key_drifted")],  # ON r0 vs ON r1 → S=1 >> null 0
    )
    result = score_live_carry(caps)
    assert result.verdict == INCONCLUSIVE
    assert result.m1 is not None
    assert not result.m1.on_noise_ok


def test_inconclusive_no_valid_null() -> None:
    """Empty OFF floors → OFF/OFF pairs degenerate → no valid null → INCONCLUSIVE."""
    caps = _matrix(on_keys=[("self", "on_key")], off_keys=[])
    result = score_live_carry(caps)
    assert result.verdict == INCONCLUSIVE
    assert result.m1 is not None
    assert all(s is None for s in result.m1.s_off_off_null)


# ---------------------------------------------------------------------------
# INVALID_MEASUREMENT branches
# ---------------------------------------------------------------------------


def test_invalid_zero_engagement() -> None:
    """M0 engagement 0 (carry never fired) → INVALID_MEASUREMENT (not NO_DETECTABLE)."""
    caps = _matrix(
        on_keys=[("self", "on_key")], off_keys=[("self", "off_key")], on_events=0
    )
    result = score_live_carry(caps)
    assert result.verdict == INVALID
    assert result.m0 is not None
    assert result.m0.status == "invalid"


def test_invalid_cap_violation() -> None:
    """A modulated offset beyond cap + transient → INVALID_MEASUREMENT (M2)."""
    caps = _matrix(
        on_keys=[("self", "on_key")],
        off_keys=[("self", "off_key")],
        on_r0_cap_offset=0.5,  # |mod - floor| = 0.5 > 0.15 + 0.05
    )
    result = score_live_carry(caps)
    assert result.verdict == INVALID
    assert result.m2 is not None
    assert not result.m2.cap_ok


def test_invalid_throughput_non_inferiority() -> None:
    """ON r0 materially shorter than OFF r0 → INVALID_MEASUREMENT (M2 throughput)."""
    caps: list[LiveCarryCapture] = []
    for seed in _SEEDS:
        caps.append(
            _capture(
                seed,
                "on",
                0,
                keys=[("self", "on_key")],
                sat=_engagement_sat(seed, "on", 0, events=6),
                n_ticks=5,  # ON r0 short
            )
        )
        caps.append(
            _capture(
                seed, "on", 1, keys=[("self", "on_key")], sat=_benign_sat(seed, "on", 1)
            )
        )
        caps.append(
            _capture(
                seed,
                "off",
                0,
                keys=[("self", "off_key")],
                sat=_benign_sat(seed, "off", 0),
                n_ticks=20,
            )
        )
        caps.append(
            _capture(
                seed,
                "off",
                1,
                keys=[("self", "off_key")],
                sat=_benign_sat(seed, "off", 1),
                n_ticks=20,
            )
        )
    result = score_live_carry(caps)
    assert result.verdict == INVALID
    assert result.m2 is not None
    assert not result.m2.throughput_ok


def test_invalid_coherence_non_inferiority() -> None:
    """ON coherence far below OFF − margin → INVALID_MEASUREMENT (M2 coherence)."""
    caps: list[LiveCarryCapture] = []
    low = tuple(
        CoherenceRow(individual_id="kant", tick=t, coherence_score=0.2)
        for t in range(15)
    )
    high = tuple(
        CoherenceRow(individual_id="kant", tick=t, coherence_score=0.9)
        for t in range(15)
    )
    for seed in _SEEDS:
        caps.append(
            _capture(
                seed,
                "on",
                0,
                keys=[("self", "on_key")],
                sat=_engagement_sat(seed, "on", 0, events=6),
                coherence=low,
            )
        )
        caps.append(
            _capture(
                seed, "on", 1, keys=[("self", "on_key")], sat=_benign_sat(seed, "on", 1)
            )
        )
        caps.append(
            _capture(
                seed,
                "off",
                0,
                keys=[("self", "off_key")],
                sat=_benign_sat(seed, "off", 0),
                coherence=high,
            )
        )
        caps.append(
            _capture(
                seed,
                "off",
                1,
                keys=[("self", "off_key")],
                sat=_benign_sat(seed, "off", 1),
            )
        )
    result = score_live_carry(caps)
    assert result.verdict == INVALID
    assert result.m2 is not None
    assert not result.m2.coherence_ok


# ---------------------------------------------------------------------------
# Matrix-integrity → INVALID_MEASUREMENT (ADR §0/§3)
# ---------------------------------------------------------------------------


def test_invalid_incomplete_matrix() -> None:
    """11 captures (one cell missing) → INVALID_MEASUREMENT."""
    caps = _matrix(on_keys=[("self", "on_key")], off_keys=[("self", "off_key")])
    result = score_live_carry(caps[:-1])
    assert result.verdict == INVALID
    assert result.m1 is None


def test_invalid_missing_replicate_key() -> None:
    """A capture with no replicate_id → INVALID_MEASUREMENT (matrix identity gap)."""
    caps = _matrix(on_keys=[("self", "on_key")], off_keys=[("self", "off_key")])
    caps[0] = replace(caps[0], replicate_id=None)
    result = score_live_carry(caps)
    assert result.verdict == INVALID


def test_invalid_duplicate_matrix_key() -> None:
    """Two captures colliding on (seed, arm, replicate) → INVALID_MEASUREMENT."""
    caps = _matrix(on_keys=[("self", "on_key")], off_keys=[("self", "off_key")])
    caps[1] = replace(caps[1], replicate_id=0)  # ON r1 relabelled as a 2nd ON r0
    result = score_live_carry(caps)
    assert result.verdict == INVALID


def test_invalid_wrong_seed_count() -> None:
    """Only 2 distinct seeds (8 runs) → INVALID_MEASUREMENT (N_SEED mismatch)."""
    caps = [
        c
        for c in _matrix(on_keys=[("self", "a")], off_keys=[("self", "b")])
        if c.seed != 3
    ]
    result = score_live_carry(caps)
    assert result.verdict == INVALID
