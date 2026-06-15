"""Deterministic replay engine coverage (U5, versioned-measurement ADR §5.2).

CPU-only, pure (no DuckDB / GPU / LLM). Drives the **unchanged** reconcile kernel
through ``replay_arm`` and verifies the four properties the replay must hold:

* **determinism** — replaying the same stream twice is bit-identical (Codex MED-2: the
  claim is the logical output, not file bytes);
* **carry separation** — the ON arm registers retention across a cross-fp churn
  (``r_retained > 0``) while the OFF arm does not (``r_retained == 0``), the
  ``test_stm_carry_versioned_end_to_end`` property re-expressed through the replay;
* **hint re-evaluation (Codex HIGH-1 / MED-3 ③)** — the carry-dependent
  ``adopted`` ↔ ``rejected_no_effect`` boundary flips between arms (a source ``adopted``
  that saturates to the unit bound under carry becomes ``rejected_no_effect`` in the ON
  arm while staying ``adopted`` in the OFF arm), and the carry-independent dispositions
  are carried verbatim;
* **same-arm fidelity (Codex MED-3 ②)** — replaying the arm the source stream was built
  under reproduces the source's post-reconcile snapshots exactly.
"""

from __future__ import annotations

from erre_sandbox.cognition.world_model import (
    WorldModelRuntimeState,
    apply_world_model_update_hint,
    project_world_model_snapshot,
    reconcile_world_model,
)
from erre_sandbox.cognition.world_model_replay import (
    ReplayInputTick,
    replay_arm,
)
from erre_sandbox.contracts.cognition_layers import (
    SubjectiveWorldModel,
    WorldModelEntry,
    WorldModelHintDisposition,
    WorldModelUpdateHint,
)
from erre_sandbox.evidence.saturation.constants import T_WARMUP
from erre_sandbox.evidence.saturation.trace_ddl import (
    SaturationTraceRow,
    build_saturation_trace_rows,
)
from erre_sandbox.evidence.saturation.versioned_loader import (
    ArmRunBundle,
    score_versioned_saturation,
)

_AXIS = "env"
_KEY = "agora"
_IND = "rikyu"
_CITE = "belief_rikyu__kant"


def _entry(value: float, *, confidence: float = 0.6) -> WorldModelEntry:
    return WorldModelEntry(
        axis=_AXIS,  # type: ignore[arg-type]
        key=_KEY,
        value=value,
        confidence=confidence,
        cited_memory_ids=(_CITE,),
        last_updated_tick=100,
    )


def _floor(value: float, *, confidence: float = 0.6) -> SubjectiveWorldModel:
    return SubjectiveWorldModel(entries=[_entry(value, confidence=confidence)])


def _adopted_strengthen() -> WorldModelHintDisposition:
    """A source disposition the replay re-evaluates per arm (carry-dependent)."""
    return WorldModelHintDisposition(
        llm_status="ok",
        emitted=True,
        disposition="adopted",
        target_axis=_AXIS,  # type: ignore[arg-type]
        target_key=_KEY,
        direction="strengthen",
        adopted_signed_step=0.05,
        exposed_entry_count=1,
    )


def _stepping_stream(ticks: range, *, step: float = 0.001) -> list[ReplayInputTick]:
    """A single-channel stream whose floor steps every tick (cross-fp, sign stable)."""
    return [
        ReplayInputTick(
            individual_id=_IND,
            tick=t,
            floor=_floor(0.50 + step * t),
            source_disposition=_adopted_strengthen(),
        )
        for t in ticks
    ]


def _rows(
    results: list, *, run_id: str = "r", seed: int = 7
) -> list[SaturationTraceRow]:
    out: list[SaturationTraceRow] = []
    for r in results:
        out.extend(
            build_saturation_trace_rows(
                r.snapshot,
                run_id=run_id,
                seed=seed,
                individual_id=r.individual_id,
                tick=r.tick,
                individual_layer_enabled=True,
            )
        )
    return out


def test_replay_is_deterministic() -> None:
    stream = _stepping_stream(range(T_WARMUP, T_WARMUP + 8))
    first = replay_arm(stream, stm_carry=True)
    second = replay_arm(stream, stm_carry=True)
    # ReplayOutputTick is a frozen dataclass of frozen pydantic models -> value eq.
    assert first == second


def test_on_arm_registers_retention_off_arm_does_not() -> None:
    """Carry separation: the only difference is ``stm_carry`` (mirrors the e2e test)."""
    stream = _stepping_stream(range(T_WARMUP, T_WARMUP + 12))
    on_rows = _rows(replay_arm(stream, stm_carry=True))
    off_rows = _rows(replay_arm(stream, stm_carry=False))

    on = score_versioned_saturation(
        [ArmRunBundle(arm="ON", run_id="r", source_run_id="r", rows=on_rows)]
    ).on_partitions[0]
    off = score_versioned_saturation(
        [ArmRunBundle(arm="OFF", run_id="r", source_run_id="r", rows=off_rows)]
    ).off_partitions[0]

    assert on.r_retained > 0
    assert on.retained_rate is not None
    assert on.retained_rate > 0.0
    assert on.n_retained_channels >= 1
    # OFF (frozen drop): the pre-nudge snapshot re-grounds to the floor every cross-fp
    # tick, so nothing is retained.
    assert off.r_retained == 0
    assert off.n_retained_channels == 0


def test_hint_adopted_no_effect_flips_between_arms() -> None:
    """Codex HIGH-1 / MED-3 ③: the carry-dependent disposition differs per arm.

    Floor value is pinned at 0.90 while confidence steps (fp changes, value/sign
    stable): the ON arm carries the strengthen offset until the modulated value
    saturates to the unit bound (1.0), where a further strengthen is a no-op
    (``rejected_no_effect``); the OFF arm re-grounds to 0.90 every tick, so the same
    source hint stays ``adopted``.
    """
    stream = [
        ReplayInputTick(
            individual_id=_IND,
            tick=t,
            floor=_floor(0.90, confidence=0.60 + 0.001 * t),
            source_disposition=_adopted_strengthen(),
        )
        for t in range(T_WARMUP, T_WARMUP + 5)
    ]
    on = replay_arm(stream, stm_carry=True)
    off = replay_arm(stream, stm_carry=False)

    on_dispositions = [t.disposition.disposition for t in on]
    off_dispositions = [t.disposition.disposition for t in off]
    # ON saturates to the unit bound and rejects further nudges; OFF always adopts.
    assert "rejected_no_effect" in on_dispositions
    assert all(d == "adopted" for d in off_dispositions)
    # The flip is real: at least one tick where ON != OFF.
    assert any(o != f for o, f in zip(on_dispositions, off_dispositions, strict=True))


def test_carry_independent_disposition_carried_verbatim() -> None:
    """A non-emitted / pre-gate-4 source disposition is copied (no nudge, no flip)."""
    not_emitted = WorldModelHintDisposition(
        llm_status="ok",
        emitted=False,
        disposition="not_emitted",
        target_axis=None,
        target_key=None,
        direction=None,
        adopted_signed_step=0.0,
        exposed_entry_count=1,
    )
    stream = [
        ReplayInputTick(
            individual_id=_IND,
            tick=t,
            floor=_floor(0.50 + 0.001 * t),
            source_disposition=not_emitted,
        )
        for t in range(T_WARMUP, T_WARMUP + 4)
    ]
    for stm_carry in (True, False):
        out = replay_arm(stream, stm_carry=stm_carry)
        assert all(t.disposition == not_emitted for t in out)
        # No nudge ever applied -> the modulated view equals the floor every tick.
        assert all(
            t.snapshot.modulated.entries[0].value
            == t.snapshot.base_floor.entries[0].value
            for t in out
        )


def test_same_arm_replay_reproduces_source_snapshots() -> None:
    """Codex MED-3 ②: replaying the arm the source was built under reproduces it.

    Builds a 'source' by running the cycle's own per-tick loop (reconcile -> snapshot ->
    real adopted nudge) under ``stm_carry=True``, recording the floor stream + per-tick
    disposition + the post-reconcile snapshots; then ``replay_arm`` over that floor/hint
    stream (with the synthetic-citation re-application) reproduces the same snapshots.
    """
    ticks = range(T_WARMUP, T_WARMUP + 9)
    exposed = {(_AXIS, _KEY): frozenset({_CITE})}
    hint = WorldModelUpdateHint(
        axis=_AXIS,  # type: ignore[arg-type]
        key=_KEY,
        direction="strengthen",
        cited_memory_ids=(_CITE,),
    )

    prior: WorldModelRuntimeState | None = None
    source_stream: list[ReplayInputTick] = []
    source_snapshots = []
    for t in ticks:
        floor = _floor(0.50 + 0.001 * t)
        reconciled = reconcile_world_model(prior, floor, current_tick=t, stm_carry=True)
        source_snapshots.append(project_world_model_snapshot(reconciled))
        nudged = apply_world_model_update_hint(reconciled.modulated, hint, exposed)
        if nudged is not None:
            disposition = "adopted"
            prior = reconciled.model_copy(update={"modulated": nudged})
        else:
            disposition = "rejected_no_effect"
            prior = reconciled
        source_stream.append(
            ReplayInputTick(
                individual_id=_IND,
                tick=t,
                floor=floor,
                source_disposition=WorldModelHintDisposition(
                    llm_status="ok",
                    emitted=True,
                    disposition=disposition,  # type: ignore[arg-type]
                    target_axis=_AXIS,  # type: ignore[arg-type]
                    target_key=_KEY,
                    direction="strengthen",
                    adopted_signed_step=0.0,
                    exposed_entry_count=1,
                ),
            )
        )

    replayed = replay_arm(source_stream, stm_carry=True)
    assert [r.snapshot for r in replayed] == source_snapshots
