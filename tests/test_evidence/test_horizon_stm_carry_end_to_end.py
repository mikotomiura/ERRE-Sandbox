"""End-to-end: the real III-a STM carry is read as *admitted retention* by CV2.

Drives the production :func:`reconcile_world_model` in its ``stm_carry=True`` arm over a
churning floor for several channels, across an observation window long enough that the
carry both expires in-window AND has follow-up past ``t0 + H_SAFETY`` (so the episode is
ADMITTED, not censored). Confirms the horizon Conditional-V2 layer reads the real carry
as an admitted, healthy retention (PASS), the reachability the wall-cut frozen V2 could
not register. CPU-only (no GPU, no DuckDB). Mirrors
``test_stm_carry_versioned_end_to_end`` (which proves the frozen layer reads it as
retention).
"""

from __future__ import annotations

from erre_sandbox.cognition.world_model import (
    WorldModelRuntimeState,
    reconcile_world_model,
)
from erre_sandbox.contracts.cognition_layers import (
    SubjectiveWorldModel,
    WorldModelEntry,
)
from erre_sandbox.evidence.saturation.constants import T_WARMUP
from erre_sandbox.evidence.saturation.horizon_versioned_loader import (
    _conditional_v2,
    score_horizon_versioned_saturation,
)
from erre_sandbox.evidence.saturation.trace_ddl import SaturationTraceRow
from erre_sandbox.evidence.saturation.versioned_constants import (
    H_SAFETY,
    RETAINED_CHANNEL_MIN,
)
from erre_sandbox.evidence.saturation.versioned_loader import ArmRunBundle

_AXIS = "env"
_KEY_PREFIX = "agora"
_SEED = 7
_RUN = "run-horizon-e2e"


def _entry(value: float) -> WorldModelEntry:
    return WorldModelEntry(
        axis=_AXIS,  # type: ignore[arg-type]
        key=_KEY_PREFIX,
        value=value,
        confidence=0.6,
        cited_memory_ids=("belief_kant__nietzsche",),
        last_updated_tick=100,
    )


def _swm(value: float) -> SubjectiveWorldModel:
    return SubjectiveWorldModel(entries=[_entry(value)])


def _drive_channel(key: str, ticks: range) -> list[SaturationTraceRow]:
    """Drive the real STM-carry reconcile over a cross-fp floor for one channel."""
    state = WorldModelRuntimeState(base_floor=_swm(0.50), modulated=_swm(0.60))
    rows: list[SaturationTraceRow] = []
    for tick in ticks:
        floor_value = 0.50 + 0.001 * tick  # fp changes each tick, sign stable
        state = reconcile_world_model(
            state, _swm(floor_value), current_tick=tick, stm_carry=True
        )
        rows.append(
            SaturationTraceRow(
                run_id=_RUN,
                seed=_SEED,
                individual_id="kant",
                axis=_AXIS,
                key=key,
                tick=tick,
                base_floor_value=floor_value,
                modulated_value=state.modulated.entries[0].value,
                floor_fingerprint_hash=f"fp{round(floor_value, 6)}",
                individual_layer_enabled=True,
            )
        )
    return rows


def test_real_stm_carry_is_admitted_and_passes_cv2() -> None:
    # Window long enough that the carry expires AND has follow-up past t0 + H_SAFETY.
    ticks = range(T_WARMUP, T_WARMUP + H_SAFETY + 6)
    rows: list[SaturationTraceRow] = []
    for i in range(RETAINED_CHANNEL_MIN):
        rows += _drive_channel(f"{_KEY_PREFIX}{i}", ticks)

    cv2, admitted, excluded = _conditional_v2(rows)
    # the real carry is admitted (sufficient follow-up) and healthy (expires in-window)
    assert len(admitted) == RETAINED_CHANNEL_MIN
    assert len(excluded) == 0
    assert cv2 == "PASS"

    part = score_horizon_versioned_saturation(
        [ArmRunBundle(arm="ON", run_id=_RUN, source_run_id=_RUN, rows=rows)]
    ).on_partitions[0]
    assert part.cv2_status == "PASS"
    assert part.cv2_forensic.n_admitted_channels == RETAINED_CHANNEL_MIN
