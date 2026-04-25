"""Pure-function affinity computation for the M7 Slice γ relational hook.

The single public function :func:`compute_affinity_delta` returns the
adjustment that should be applied to a :class:`RelationshipBond.affinity`
field when one :class:`DialogTurnMsg` is recorded. It is intentionally a
pure function (no I/O, no side effects, no global state) so:

* the bootstrap-level chain sink in
  :mod:`erre_sandbox.bootstrap` can wrap it without a runtime dependency, and
* unit tests can drive every branch without a live LLM, sqlite store, or
  scheduler.

For γ MVP the delta is a constant ``+0.02`` clamped to ``[-1.0, 1.0]``.
The full ``(turn, recent_transcript, persona)`` signature is already in
place so a future Slice δ can replace the body with the lexical heuristic
+ persona prior described in
``.steering/20260425-m7-slice-gamma/design-final.md`` *without changing
any call site*.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.schemas import DialogTurnMsg, PersonaSpec

GAMMA_CONSTANT_DELTA: Final[float] = 0.02
"""γ MVP affinity nudge per recorded :class:`DialogTurnMsg` (always positive).

Validated qualitatively in the live β acceptance run (``20260425-m7-beta-
live-acceptance``): 6-turn dialogs over a 90-second run accumulated +0.12
between two agents — a meaningfully observable but conservative signal in
the 2-decimal Godot UI display."""

AFFINITY_LOWER: Final[float] = -1.0
AFFINITY_UPPER: Final[float] = 1.0


def clamp_affinity_delta(delta: float) -> float:
    """Clamp ``delta`` to the :class:`RelationshipBond.affinity` ``_Signed`` range.

    Mirrors the field constraint on :class:`RelationshipBond.affinity`
    (``ge=-1.0`` / ``le=1.0``). Centralised here so future δ deltas that
    add or subtract multiple terms cannot accidentally bypass the bound.
    """
    if delta < AFFINITY_LOWER:
        return AFFINITY_LOWER
    if delta > AFFINITY_UPPER:
        return AFFINITY_UPPER
    return delta


def compute_affinity_delta(
    turn: DialogTurnMsg,
    recent_transcript: Sequence[DialogTurnMsg],
    persona: PersonaSpec,
) -> float:
    """Return the affinity adjustment for one recorded :class:`DialogTurnMsg`.

    Both ``recent_transcript`` and ``persona`` are accepted (and intentionally
    unused) so the γ → δ migration is mechanical: replace the body, leave
    every caller untouched.

    Args:
        turn: The dialog turn that was just recorded by the scheduler. The
            speaker / addressee / utterance are available for the future
            δ lexical heuristic.
        recent_transcript: All preceding turns of the same dialog, oldest
            first. Future δ heuristics may inspect tone shifts.
        persona: The speaker's persona. Future δ heuristics may use
            personality traits to bias the delta sign or magnitude.

    Returns:
        A clamped affinity delta to add to :class:`RelationshipBond.affinity`.
        For γ the value is always :data:`GAMMA_CONSTANT_DELTA`.
    """
    del turn, recent_transcript, persona  # γ keeps the signature future-proof.
    return clamp_affinity_delta(GAMMA_CONSTANT_DELTA)


def apply_affinity(current: float, delta: float) -> float:
    """Add ``delta`` to ``current`` and clamp to the legal range.

    Convenience wrapper used at every call site that needs to mutate a
    :class:`RelationshipBond.affinity` so the clamp logic is not repeated.
    """
    return clamp_affinity_delta(current + delta)


__all__ = [
    "AFFINITY_LOWER",
    "AFFINITY_UPPER",
    "GAMMA_CONSTANT_DELTA",
    "apply_affinity",
    "clamp_affinity_delta",
    "compute_affinity_delta",
]
