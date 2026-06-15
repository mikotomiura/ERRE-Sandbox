"""Deterministic replay threading of the world-model reconcile kernel (U5, §5.2).

The III-a deterministic replay (versioned-measurement ADR §5.2, the *primary* path)
fixes one captured ``floor`` + ``hint`` stream and re-runs the reconcile kernel under
both carry arms — the **only** difference between the ON and OFF arms is the
``stm_carry`` flag. The LLM is never re-invoked: the recorded hint disposition is
re-applied through the unchanged authority, which is what makes the contrast clean (same
floor, same hint stream, carry rule differs) and the output bit-stable.

Layering (U5 HIGH-4): this lives in ``cognition`` — it *uses* the
``cognition.world_model`` kernel (``reconcile_world_model`` /
``apply_world_model_update_hint`` / ``project_world_model_snapshot``) and the
``hint_engagement`` measurement, which ``evidence`` may not import. It is **pure** (no
DuckDB, no I/O, no RNG, no clock) and returns ``contracts`` read-models; the
composition-root CLI assembles the input from the source trace and converts the output
back into trace rows.

Hint re-application (Codex HIGH-1). The carry rule changes an entry's *modulated* value,
so whether a hint has an effect can differ between arms. Of the six dispositions, only
``adopted`` ↔ ``rejected_no_effect`` is carry-dependent (it turns on gate 4 —
``apply_world_model_update_hint``'s "did the value move?" — which reads the modulated
value). The other four (``not_emitted`` / ``rejected_not_displayed`` /
``rejected_citation`` / ``rejected_no_change``) gate on the key set, the floor-derived
citations, or the requested direction — all carry-independent — so they are carried
verbatim. For a source ``adopted`` / ``rejected_no_effect`` tick the replay re-runs the
**unchanged** authority against *this arm's* modulated SWM (gates 1-3 already passed in
the source and are carry-independent, so a trivially-valid synthetic citation drives
gate 4 only) and emits the arm-specific disposition + the **measured** step — never a
copy of the source disposition (which would feed V3 a wrong adopted direction).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from erre_sandbox.cognition.hint_engagement import measure_adopted_signed_step
from erre_sandbox.cognition.world_model import (
    WorldModelRuntimeState,
    apply_world_model_update_hint,
    project_world_model_snapshot,
    reconcile_world_model,
)
from erre_sandbox.contracts.cognition_layers import (
    WorldModelHintDisposition,
    WorldModelUpdateHint,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.contracts.cognition_layers import (
        SubjectiveWorldModel,
        WorldModelSnapshot,
    )

_REPLAY_CITATION: Final[str] = "__replay__"
"""Synthetic cited id used to re-drive the unchanged hint authority.

A source ``adopted`` / ``rejected_no_effect`` tick already passed gates 1-3 (displayed /
citation / direction), all carry-independent, so the replay only needs gate 4 re-checked
against this arm's modulated value. Pairing a one-element ``cited_memory_ids`` with a
matching one-element ``exposed_citations`` makes gates 1-2 pass trivially without
fabricating real evidence — the value computation never reads the cited ids."""

_CARRY_INDEPENDENT_DISPOSITIONS: Final[frozenset[str]] = frozenset(
    {
        "not_emitted",
        "rejected_not_displayed",
        "rejected_citation",
        "rejected_no_change",
    }
)
"""Dispositions whose outcome does not depend on the carried modulated value.

Their gates read the key set / floor-derived citations / requested direction — none of
which the carry rule changes — so they are carried verbatim (no nudge applied)."""


class WorldModelReplayError(RuntimeError):
    """A replay input tick is internally inconsistent (e.g. a target-less adoption)."""


@dataclass(frozen=True, slots=True)
class ReplayInputTick:
    """One source-stream tick: the reconcile-input floor + the source disposition.

    All members are ``contracts`` read-models so this stays a pure ``cognition`` input
    (the composition-root CLI maps the ``evidence``-layer source stream onto it).
    """

    individual_id: str
    tick: int
    floor: SubjectiveWorldModel
    source_disposition: WorldModelHintDisposition


@dataclass(frozen=True, slots=True)
class ReplayOutputTick:
    """One replayed tick for a single arm: the saturation snapshot + arm disposition.

    ``snapshot`` is the **post-reconcile, pre-nudge** ``WorldModelSnapshot`` (the exact
    grain the frozen saturation serialiser expects). ``disposition`` is **this arm's**
    re-evaluated hint disposition (Codex HIGH-1), not the source's.
    """

    individual_id: str
    tick: int
    snapshot: WorldModelSnapshot
    disposition: WorldModelHintDisposition


def _reapply_hint(
    reconciled: WorldModelRuntimeState,
    source: WorldModelHintDisposition,
) -> tuple[WorldModelHintDisposition, WorldModelRuntimeState]:
    """Re-evaluate the source hint against *this arm's* state (Codex HIGH-1).

    Returns ``(arm_disposition, next_state)``. For a carry-independent disposition the
    source disposition is carried verbatim and the state is unchanged. For a source
    ``adopted`` / ``rejected_no_effect`` the unchanged authority is re-run against the
    arm's modulated SWM: an effect → ``adopted`` (measured step, modulated updated), no
    effect → ``rejected_no_effect`` (step ``0.0``, state unchanged).
    """
    if source.disposition in _CARRY_INDEPENDENT_DISPOSITIONS:
        return source, reconciled

    # adopted / rejected_no_effect: the only carry-dependent boundary.
    if (
        source.target_axis is None
        or source.target_key is None
        or source.direction is None
    ):
        raise WorldModelReplayError(
            f"disposition {source.disposition!r} has a null target/direction "
            "(violates the hint-trace CHECK invariant); source capture is corrupt"
        )
    hint = WorldModelUpdateHint(
        axis=source.target_axis,
        key=source.target_key,
        direction=source.direction,
        cited_memory_ids=(_REPLAY_CITATION,),
    )
    exposed: dict[tuple[str, str], frozenset[str]] = {
        (source.target_axis, source.target_key): frozenset({_REPLAY_CITATION})
    }
    nudged = apply_world_model_update_hint(reconciled.modulated, hint, exposed)
    if nudged is None:
        arm = source.model_copy(
            update={"disposition": "rejected_no_effect", "adopted_signed_step": 0.0}
        )
        return arm, reconciled
    step = measure_adopted_signed_step(
        reconciled.modulated, nudged, axis=source.target_axis, key=source.target_key
    )
    arm = source.model_copy(
        update={"disposition": "adopted", "adopted_signed_step": step}
    )
    next_state = reconciled.model_copy(update={"modulated": nudged})
    return arm, next_state


def replay_arm(
    stream: Sequence[ReplayInputTick],
    *,
    stm_carry: bool,
) -> list[ReplayOutputTick]:
    """Replay one arm of a fixed floor/hint stream (pure, deterministic).

    Each individual is threaded independently (its own ``WorldModelRuntimeState``); for
    every tick in ascending order the reconcile kernel runs with the given *stm_carry*,
    the post-reconcile snapshot is captured, and the source hint is re-applied for this
    arm (see :func:`_reapply_hint`). Individuals are visited in sorted id order and
    ticks in ascending order, so the output is canonical (the deterministic INSERT order
    CLI relies on) regardless of the input row order. The **only** difference between an
    ON and an OFF replay of the same stream is *stm_carry*.
    """
    by_individual: dict[str, list[ReplayInputTick]] = {}
    for item in stream:
        by_individual.setdefault(item.individual_id, []).append(item)

    out: list[ReplayOutputTick] = []
    for individual_id in sorted(by_individual):
        prior: WorldModelRuntimeState | None = None
        for item in sorted(by_individual[individual_id], key=lambda t: t.tick):
            reconciled = reconcile_world_model(
                prior,
                item.floor,
                current_tick=item.tick,
                stm_carry=stm_carry,
            )
            snapshot = project_world_model_snapshot(reconciled)
            disposition, prior = _reapply_hint(reconciled, item.source_disposition)
            out.append(
                ReplayOutputTick(
                    individual_id=individual_id,
                    tick=item.tick,
                    snapshot=snapshot,
                    disposition=disposition,
                )
            )
    return out


__all__ = [
    "ReplayInputTick",
    "ReplayOutputTick",
    "WorldModelReplayError",
    "replay_arm",
]
