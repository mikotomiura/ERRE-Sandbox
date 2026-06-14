"""End-to-end: the real III-a STM carry is read as *retained* by the versioned scorer.

This is the one test that closes the loop the whole fork (III-a) chain exists to
measure: drive the production :func:`reconcile_world_model` in its ``stm_carry=True``
arm across a churning (cross-fp) floor, serialise the resulting post-reconcile values
into :class:`SaturationTraceRow` rows exactly as the trace sink would, and confirm
``score_versioned_saturation`` classifies the carried transitions as retention
(``r_retained > 0`` / ``retained_rate > 0`` / ``n_retained_channels >= 1``) — the
``retained_across_fp_change_rate`` the frozen ``drop_rate`` could never register.

CPU-only synthetic fixture (no GPU, no DuckDB). The fingerprint hash mirrors the
versioned loader test convention (``fp{round(floor,6)}``) so a stepping floor is a
cross-fp trial every tick — the same notion the real ``_floor_fingerprint`` encodes.
The production timing (pre-step ``current_tick`` vs the trace's tick) is reproduced by
using the same ``tick`` for the reconcile call and the row (Codex LOW-1).

See ``.steering/20260614-iiia-ltm-stm-impl/``.
"""

from __future__ import annotations

from erre_sandbox.cognition.world_model import (
    STM_HORIZON,
    WorldModelRuntimeState,
    reconcile_world_model,
)
from erre_sandbox.contracts.cognition_layers import (
    SubjectiveWorldModel,
    WorldModelEntry,
)
from erre_sandbox.evidence.saturation.constants import T_WARMUP
from erre_sandbox.evidence.saturation.trace_ddl import SaturationTraceRow
from erre_sandbox.evidence.saturation.versioned_loader import (
    ArmRunBundle,
    score_versioned_saturation,
)

_AXIS = "env"
_KEY = "agora"
_SEED = 7
_RUN = "run-e2e"


def _entry(value: float) -> WorldModelEntry:
    return WorldModelEntry(
        axis=_AXIS,  # type: ignore[arg-type]
        key=_KEY,
        value=value,
        confidence=0.6,
        cited_memory_ids=("belief_kant__nietzsche",),
        last_updated_tick=100,
    )


def _swm(entry: WorldModelEntry) -> SubjectiveWorldModel:
    return SubjectiveWorldModel(entries=[entry])


def _drive_real_reconcile(ticks: range) -> list[SaturationTraceRow]:
    """Run the real STM-carry reconcile over a cross-fp floor; build trace rows.

    Prior state holds a +0.10 offset; the floor steps every tick (cross-fp, positive
    sign), so the ON arm carries the offset until the STM horizon expires within the
    observation window.
    """
    state = WorldModelRuntimeState(
        base_floor=_swm(_entry(0.50)), modulated=_swm(_entry(0.60))
    )
    rows: list[SaturationTraceRow] = []
    for tick in ticks:
        floor_value = 0.50 + 0.001 * tick  # fp changes each tick, sign stable
        state = reconcile_world_model(
            state, _swm(_entry(floor_value)), current_tick=tick, stm_carry=True
        )
        modulated = state.modulated.entries[0].value
        rows.append(
            SaturationTraceRow(
                run_id=_RUN,
                seed=_SEED,
                individual_id="kant",
                axis=_AXIS,
                key=_KEY,
                tick=tick,
                base_floor_value=floor_value,
                modulated_value=modulated,
                floor_fingerprint_hash=f"fp{round(floor_value, 6)}",
                individual_layer_enabled=True,
            )
        )
    return rows


def test_real_stm_carry_is_read_as_retained_by_versioned_scorer() -> None:
    # Observation window: warmup .. past STM_HORIZON so the carry expires in-window.
    rows = _drive_real_reconcile(range(T_WARMUP, T_WARMUP + STM_HORIZON + 3))
    result = score_versioned_saturation(
        [ArmRunBundle(arm="ON", run_id=_RUN, source_run_id=_RUN, rows=rows)]
    )
    assert len(result.on_partitions) == 1
    part = result.on_partitions[0]
    # The frozen drop_rate would count every cross-fp tick as a drop; the versioned
    # scorer instead registers the carried offset as retention.
    assert part.r_retained > 0
    assert part.retained_rate is not None
    assert part.retained_rate > 0.0
    assert part.n_retained_channels >= 1
    assert part.d_fp > 0  # cross-fp trials were actually present


def test_off_arm_frozen_drop_registers_zero_retention() -> None:
    """The OFF control: a frozen drop-on-churn stream retains nothing (R == 0)."""
    state = WorldModelRuntimeState(
        base_floor=_swm(_entry(0.50)), modulated=_swm(_entry(0.60))
    )
    rows: list[SaturationTraceRow] = []
    for tick in range(T_WARMUP, T_WARMUP + 12):
        floor_value = 0.50 + 0.001 * tick
        # Frozen arm: stm_carry defaults off -> cross-fp drops the modulation.
        state = reconcile_world_model(state, _swm(_entry(floor_value)))
        # Re-apply a fresh +0.10 offset each even tick (so D_fp > 0) the way a live
        # nudge would; the next tick's frozen reconcile drops it.
        modulated = floor_value + (0.10 if tick % 2 == 0 else 0.0)
        state = WorldModelRuntimeState(
            base_floor=_swm(_entry(floor_value)),
            modulated=_swm(_entry(modulated)),
        )
        rows.append(
            SaturationTraceRow(
                run_id=_RUN,
                seed=_SEED,
                individual_id="kant",
                axis=_AXIS,
                key=_KEY,
                tick=tick,
                base_floor_value=floor_value,
                modulated_value=modulated,
                floor_fingerprint_hash=f"fp{round(floor_value, 6)}",
                individual_layer_enabled=True,
            )
        )
    result = score_versioned_saturation(
        [ArmRunBundle(arm="OFF", run_id=_RUN, source_run_id=_RUN, rows=rows)]
    )
    part = result.off_partitions[0]
    assert part.r_retained == 0
    assert part.n_retained_channels == 0
