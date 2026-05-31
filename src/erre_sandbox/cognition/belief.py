"""Belief promotion bridge from RelationshipBond to SemanticMemoryRecord (M7δ).

The CSDG 2-layer memory pattern (short-term / long-term) is realised in
δ as a one-way bridge: when an agent's :class:`RelationshipBond` toward
a peer crosses an ``|affinity|`` threshold *and* the dyad has had at
least ``min_interactions`` turns, the bond is distilled into a typed
:class:`SemanticMemoryRecord` (``belief_kind`` × ``confidence``). The
record is upserted with a deterministic id so subsequent crossings
overwrite the prior belief in place rather than spamming the semantic
table.

Threshold / N calibration is exercised in
``tests/test_cognition/test_relational_simulation.py``: a 30-line
recurrence simulation iterates the M7δ semi-formula over 20 turns × 3
trait pairs and confirms saturation lands at turns 8-14, well inside
the live G-GEAR 90-120s window. The calibration values
(``threshold=0.45`` / ``min_interactions=6``) are part of the M7δ Axis 3
calibration.

This module is intentionally pure — :func:`maybe_promote_belief` builds
the record but does not write it to storage. The bootstrap relational
sink owns the synchronous ``_upsert_semantic_sync`` call so the layer
boundary (``cognition/`` does not import ``memory/``) is preserved.

See Also:
--------
* :class:`erre_sandbox.schemas.SemanticMemoryRecord` for the typed
  ``belief_kind`` and ``confidence`` fields (M7δ C1, schemas.py:752+).
* :mod:`erre_sandbox.cognition.relational` for the formula that drives
  ``RelationshipBond.affinity`` toward the saturation regime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Literal

from erre_sandbox.cognition.belief_ids import belief_record_id
from erre_sandbox.cognition.relational import AFFINITY_UPPER
from erre_sandbox.schemas import SemanticMemoryRecord

if TYPE_CHECKING:
    from erre_sandbox.schemas import PersonaSpec, RelationshipBond


BELIEF_THRESHOLD: Final[float] = 0.45
"""``|affinity|`` floor for belief promotion (M7δ Axis 3 calibration).

Picked from the simulation in ``test_relational_simulation.py`` so that
saturating dyads cross around turn 8-14 — comfortably inside the 90-120s
live G-GEAR run and below the trivial-noise band where decay alone
would push affinity past the floor. v1 had asserted 0.5; v2's
simulation-driven 0.45 was adopted (design-final Phase 3 row "3").
"""

BELIEF_MIN_INTERACTIONS: Final[int] = 6
"""Minimum ``ichigo_ichie_count`` before a bond can be distilled.

Guards against a single high-magnitude antagonism turn (kant↔nietzsche
fires -0.255 on turn 1) immediately spawning a "clash" belief: real
beliefs need a small history of repeated interaction. v1 picked N=5;
v2's N=6 was adopted to match the simulation-derived saturation window.
"""

_TRUST_FLOOR: Final[float] = 0.70
"""Above this ``|affinity|`` magnitude the belief is "trust" / "clash"."""

BeliefKind = Literal["trust", "clash", "wary", "curious", "ambivalent"]
"""Mirrors the ``belief_kind`` Literal on :class:`SemanticMemoryRecord`."""


def _classify_belief(affinity: float) -> BeliefKind:
    """Map a saturated ``affinity`` value to a typed belief kind.

    The thresholds are split so that ``trust`` / ``clash`` mark strongly
    consolidated beliefs, while ``curious`` / ``wary`` mark beliefs that
    have crossed the promotion threshold but have not yet reached the
    high-confidence regime. ``ambivalent`` is reserved for future
    history-aware classification (oscillating beliefs); the M7δ
    promotion path never fires it because ``|affinity| > threshold`` is
    required.
    """
    if affinity >= _TRUST_FLOOR:
        return "trust"
    if affinity > 0.0:
        return "curious"
    if affinity <= -_TRUST_FLOOR:
        return "clash"
    return "wary"


def _compute_confidence(
    affinity: float,
    interactions: int,
    *,
    min_interactions: int,
) -> float:
    """``min(1.0, |affinity|/AFFINITY_UPPER * (interactions/min_interactions))``.

    Combines belief magnitude with interaction-count evidence. A bond at
    ``|affinity|=0.5`` after exactly ``min_interactions`` turns yields
    confidence 0.5; the same magnitude after 12 turns yields ~1.0 (the
    additional interactions strengthen the same belief).
    """
    if min_interactions <= 0:
        # Defensive: caller passed a non-positive threshold; fall back to
        # magnitude alone so we never divide by zero.
        return min(1.0, abs(affinity) / AFFINITY_UPPER)
    raw = (abs(affinity) / AFFINITY_UPPER) * (
        float(interactions) / float(min_interactions)
    )
    return min(1.0, raw)


def _belief_summary(
    addressee_persona: PersonaSpec,
    kind: BeliefKind,
) -> str:
    """Render a human-readable belief summary for the SemanticMemoryRecord.

    Kept minimal — m8-affinity-dynamics Critics will query
    ``belief_kind`` directly so this string is mainly for the Godot
    ReasoningPanel and reflection log readability.
    """
    verb = {
        "trust": "trust",
        "curious": "feel drawn to",
        "wary": "feel wary of",
        "clash": "clash with",
        "ambivalent": "feel ambivalent toward",
    }[kind]
    return f"belief: I {verb} {addressee_persona.display_name}"


def maybe_promote_belief(
    bond: RelationshipBond,
    *,
    agent_id: str,
    persona: PersonaSpec,
    addressee_persona: PersonaSpec,
    threshold: float = BELIEF_THRESHOLD,
    min_interactions: int = BELIEF_MIN_INTERACTIONS,
) -> SemanticMemoryRecord | None:
    """Build a :class:`SemanticMemoryRecord` if ``bond`` qualifies for promotion.

    Returns ``None`` (no promotion) when either gate fails:

    * ``abs(bond.affinity) < threshold`` — bond hasn't reached belief
      magnitude yet.
    * ``bond.ichigo_ichie_count < min_interactions`` — too few turns to
      treat as a stable belief.

    When both gates pass, returns a populated record with a deterministic
    id so the caller's :meth:`MemoryStore.upsert_semantic` overwrites
    any prior promotion for the same dyad. The caller is responsible for
    persistence; this function is pure (no I/O).

    Args:
        bond: The :class:`RelationshipBond` *after* the apply_affinity_delta
            update for the current turn.
        agent_id: The bond-holder's ``agent_id`` (the SemanticMemoryRecord
            row is scoped to this id).
        persona: The bond-holder's :class:`PersonaSpec` (currently only
            used by the summary template; kept on the signature so future
            iterations can scale ``confidence`` by neuroticism etc.).
        addressee_persona: The other party's :class:`PersonaSpec`. Provides
            ``display_name`` for the summary.
        threshold: Override the module default ``BELIEF_THRESHOLD``. Tests
            use this to exercise the gate without touching the constant.
        min_interactions: Override ``BELIEF_MIN_INTERACTIONS``.

    Returns:
        A :class:`SemanticMemoryRecord` ready for ``upsert_semantic``, or
        ``None`` when the bond does not yet qualify.
    """
    del persona  # reserved for future scaling factors; unused in δ MVP.
    if abs(bond.affinity) < threshold:
        return None
    if bond.ichigo_ichie_count < min_interactions:
        return None
    kind = _classify_belief(bond.affinity)
    confidence = _compute_confidence(
        bond.affinity,
        bond.ichigo_ichie_count,
        min_interactions=min_interactions,
    )
    return SemanticMemoryRecord(
        id=belief_record_id(agent_id, bond.other_agent_id),
        agent_id=agent_id,
        embedding=[],  # belief promotions ship without embeddings; m8 may add.
        summary=_belief_summary(addressee_persona=addressee_persona, kind=kind),
        origin_reflection_id=None,
        belief_kind=kind,
        confidence=confidence,
    )


__all__ = [
    "BELIEF_MIN_INTERACTIONS",
    "BELIEF_THRESHOLD",
    "BeliefKind",
    "maybe_promote_belief",
]
