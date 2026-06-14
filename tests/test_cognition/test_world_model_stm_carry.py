"""Unit tests for the fork III-a STM carry arm of ``reconcile_world_model``.

The ``stm_carry=True`` arm carries a bounded LLM **offset** across a floor
fingerprint change (a ``T-fp`` cross-fp transition: evidence churned but the floor
sign is unchanged) for a bounded :data:`STM_HORIZON`, instead of the frozen arm's
unconditional drop. These tests pin the conformance points the versioned scorer
(``evidence.saturation.versioned_loader``) and its measurement ADR require:

* **offset carry** (Codex HIGH-1): the offset survives, not the absolute value — a
  floor move cannot flip the offset sign or synthesise a modulation from nothing.
* **conservative safety clock** (Codex HIGH-2): a per-key clock starts at the first
  cross-fp carry and expires at ``> STM_HORIZON`` ticks, so a retained modulation
  structurally cannot trip the V2 staleness guard (``STM_HORIZON <= H_SAFETY``).
* **T-flip drop** (versioned V4): a floor sign reversal drops the offset.
* **cap / range** (versioned V1): the carried value stays within ``floor +/- 0.15``
  and ``[-1, 1]``.
* **arm gate** (versioned §5.1): ``stm_carry=False`` is the frozen control; the
  bounded horizon cannot be bypassed by a caller (Codex HIGH-3).

See ``.steering/20260614-iiia-ltm-stm-impl/``.
"""

from __future__ import annotations

import pytest

from erre_sandbox.cognition.world_model import (
    MAX_TOTAL_MODULATION,
    STM_HORIZON,
    WorldModelRuntimeState,
    reconcile_world_model,
)
from erre_sandbox.contracts.cognition_layers import (
    SubjectiveWorldModel,
    WorldModelEntry,
)
from erre_sandbox.evidence.saturation.versioned_constants import H_SAFETY

_EPS = 1e-9


def _entry(value: float, *, axis: str = "env", key: str = "agora") -> WorldModelEntry:
    return WorldModelEntry(
        axis=axis,  # type: ignore[arg-type]
        key=key,
        value=value,
        confidence=0.6,
        cited_memory_ids=("belief_kant__nietzsche",),
        last_updated_tick=100,
    )


def _swm(*entries: WorldModelEntry) -> SubjectiveWorldModel:
    return SubjectiveWorldModel(entries=list(entries))


def _state(
    floor_value: float,
    mod_value: float,
    *,
    carried_since: tuple[tuple[tuple[str, str], int], ...] = (),
) -> WorldModelRuntimeState:
    """A prior state with one ``env/agora`` entry: floor + carried modulation."""
    return WorldModelRuntimeState(
        base_floor=_swm(_entry(floor_value)),
        modulated=_swm(_entry(mod_value)),
        carried_since=carried_since,
    )


def _value(state: WorldModelRuntimeState) -> float:
    return state.modulated.entries[0].value


# ---------- offset carry (Codex HIGH-1) ------------------------------------


def test_cross_fp_carries_offset_not_absolute_value() -> None:
    """A cross-fp carry preserves the *offset*, so a floor move keeps the sign.

    Floor 0.40 -> 0.60 (fp changes, sign unchanged), prior offset +0.10. The carried
    value must be 0.70 (offset preserved), NOT 0.50 (the absolute-value carry the
    HIGH-1 bug would produce, which flips the offset to -0.10).
    """
    state = _state(0.40, 0.50)  # offset +0.10
    out = reconcile_world_model(
        state, _swm(_entry(0.60)), current_tick=5, stm_carry=True
    )
    assert _value(out) == pytest.approx(0.70)  # offset carried, same sign
    assert out.carried_since == ((("env", "agora"), 5),)


def test_no_modulation_is_not_synthesised_from_a_floor_move() -> None:
    """With no prior offset (delta == 0) a floor move never creates a modulation."""
    state = _state(0.40, 0.40)  # offset 0
    out = reconcile_world_model(
        state, _swm(_entry(0.60)), current_tick=5, stm_carry=True
    )
    assert _value(out) == pytest.approx(0.60)  # floor stands
    assert out.carried_since == ()


def test_fp_stable_carry_reduces_to_offset_preservation() -> None:
    """On a fingerprint-identical tick the offset is preserved (no clock started)."""
    state = _state(0.40, 0.50)
    out = reconcile_world_model(
        state, _swm(_entry(0.40)), current_tick=5, stm_carry=True
    )
    assert _value(out) == pytest.approx(0.50)
    assert out.carried_since == ()  # no cross-fp yet -> clock not started


# ---------- T-flip drop (versioned V4) -------------------------------------


def test_t_flip_floor_sign_reversal_drops_offset() -> None:
    """A floor sign reversal across a fp change drops the carry (no stale offset)."""
    state = _state(-0.40, -0.50)  # offset -0.10
    out = reconcile_world_model(
        state, _swm(_entry(0.30)), current_tick=5, stm_carry=True
    )
    assert _value(out) == pytest.approx(0.30)  # dropped to floor
    assert out.carried_since == ()


# ---------- cap / range (versioned V1) -------------------------------------


def test_carried_offset_clamped_to_cap() -> None:
    """A transient over-cap offset (~0.18) re-clamps to floor + 0.15 on carry."""
    state = _state(0.40, 0.58)  # offset +0.18 (one step past the cap)
    out = reconcile_world_model(
        state, _swm(_entry(0.42)), current_tick=5, stm_carry=True
    )
    assert _value(out) == pytest.approx(0.42 + MAX_TOTAL_MODULATION)
    assert abs(_value(out) - 0.42) <= MAX_TOTAL_MODULATION + _EPS


def test_carried_value_clamped_to_unit_range() -> None:
    """The carried value never leaves ``[-1, 1]`` even near the boundary."""
    state = _state(0.92, 1.0)  # offset +0.08
    out = reconcile_world_model(
        state, _swm(_entry(0.95)), current_tick=5, stm_carry=True
    )
    assert _value(out) <= 1.0 + _EPS
    assert _value(out) == pytest.approx(1.0)  # 0.95 + 0.08 = 1.03 -> clamp to 1.0


# ---------- conservative safety clock / STM horizon (Codex HIGH-2) ---------


def test_stm_horizon_at_most_h_safety() -> None:
    """The intervention horizon must stay within the measurement TTL ceiling.

    Asserted at the test layer (which may import both modules) so cognition never
    imports the evidence layer (architecture dependency direction, Codex valid pt).
    """
    assert STM_HORIZON <= H_SAFETY


def _drive_cross_fp(ticks: int) -> list[tuple[int, float, float]]:
    """Drive a continuous cross-fp carrying run; return (tick, floor, modulated)."""
    state = _state(0.40, 0.50)  # offset +0.10
    rows: list[tuple[int, float, float]] = []
    for tick in range(ticks):
        floor_value = 0.40 + (tick + 1) * 0.001  # fp changes every tick, sign stable
        state = reconcile_world_model(
            state, _swm(_entry(floor_value)), current_tick=tick, stm_carry=True
        )
        rows.append((tick, floor_value, _value(state)))
    return rows


def test_carry_expires_strictly_after_stm_horizon() -> None:
    """Offset survives through age == STM_HORIZON and drops at age == STM_HORIZON+1.

    The first cross-fp carry is at tick 0, so ``carried_since == 0`` and expiry fires
    when ``current_tick - 0 > STM_HORIZON``.
    """
    rows = _drive_cross_fp(STM_HORIZON + 2)
    # age == STM_HORIZON (last carrying tick): offset still ~+0.10.
    _, floor_h, mod_h = rows[STM_HORIZON]
    assert mod_h - floor_h == pytest.approx(0.10)
    # age == STM_HORIZON + 1: expired -> re-grounded to the floor (offset 0).
    _, floor_x, mod_x = rows[STM_HORIZON + 1]
    assert mod_x == pytest.approx(floor_x)


def test_clock_survives_fingerprint_stabilisation() -> None:
    """After the first cross-fp carry the clock keeps running even if fp re-stabilises.

    This is the V2 structural guarantee: a carry that becomes fp-stable still expires
    within the horizon, so ``episode_end - t0`` cannot exceed STM_HORIZON < H_safety.
    """
    # tick 0: cross-fp carry starts the clock (since = 0).
    state = reconcile_world_model(
        _state(0.40, 0.50), _swm(_entry(0.42)), current_tick=0, stm_carry=True
    )
    assert state.carried_since == ((("env", "agora"), 0),)
    # ticks 1..STM_HORIZON: fingerprint-stable carries (floor frozen at 0.42).
    last = state
    for tick in range(1, STM_HORIZON + 2):
        last = reconcile_world_model(
            last, _swm(_entry(0.42)), current_tick=tick, stm_carry=True
        )
    # At age STM_HORIZON+1 the offset has expired despite the stable fingerprint.
    assert _value(last) == pytest.approx(0.42)
    assert last.carried_since == ()


# ---------- arm gate / no horizon bypass (Codex HIGH-3, §5.1) --------------


def test_off_arm_drops_cross_fp_like_frozen() -> None:
    """``stm_carry=False`` (default) drops the modulation on a fp change (control)."""
    state = _state(0.40, 0.50)
    out = reconcile_world_model(state, _swm(_entry(0.42)))  # default OFF
    assert _value(out) == pytest.approx(0.42)  # frozen drop
    assert out.carried_since == ()


def test_on_arm_carries_where_off_arm_drops() -> None:
    """The same input carries ON and drops OFF — the clean arm contrast (§5.2)."""
    state = _state(0.40, 0.50)
    new_floor = _swm(_entry(0.42))
    off = reconcile_world_model(state, new_floor)
    on = reconcile_world_model(state, new_floor, current_tick=5, stm_carry=True)
    assert _value(off) == pytest.approx(0.42)
    assert _value(on) == pytest.approx(0.52)


def test_stm_carry_requires_current_tick() -> None:
    """The ON arm fails fast without a tick (no silent unbounded clock)."""
    with pytest.raises(ValueError, match="current_tick is required"):
        reconcile_world_model(_state(0.40, 0.50), _swm(_entry(0.42)), stm_carry=True)


def test_tick_reversal_fails_fast() -> None:
    """A current_tick before carried_since is a clock inversion -> fail fast."""
    state = _state(0.40, 0.50, carried_since=((("env", "agora"), 10),))
    with pytest.raises(ValueError, match="cannot run backward"):
        reconcile_world_model(state, _swm(_entry(0.40)), current_tick=5, stm_carry=True)


def test_horizon_is_not_a_public_parameter() -> None:
    """There is no per-call ``stm_horizon`` override that could exceed H_safety."""
    import inspect

    params = inspect.signature(reconcile_world_model).parameters
    assert "stm_horizon" not in params
