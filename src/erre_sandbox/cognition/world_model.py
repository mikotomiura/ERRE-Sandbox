"""Read-only subjective-world-model synthesis (M10-B).

Periodically distils an agent's **observable evidence** — its belief-promoted
:class:`~erre_sandbox.schemas.SemanticMemoryRecord` rows plus the matching
:class:`~erre_sandbox.schemas.RelationshipBond` state — into a bounded
:class:`~erre_sandbox.contracts.cognition_layers.SubjectiveWorldModel`. The
result is injected into the *user* prompt (never the system prompt) as a
bounded top-K so SGLang RadixAttention's shared system prefix is preserved.

Design constraints:

* **Observable evidence only.** An entry exists only because a dyad was
  *promoted* to a belief record by
  :func:`erre_sandbox.cognition.belief.maybe_promote_belief`. The LLM never
  declares a world-model entry — Python distils one from the promoted record +
  bond. This module is **pure** (no I/O); the caller (the cognition cycle) owns
  reading the records via :meth:`MemoryStore.list_semantic_beliefs`.
* **cited ⊆ input.** Every :attr:`WorldModelEntry.cited_memory_ids` is a subset
  of the input record ids — a record-centric honesty invariant verified by
  ``tests/test_cognition/test_world_model.py``.
* **dyadic ⊥ class-wise.** The ``self`` axis only emits when ``>= 2``
  distinct dyads contribute, so it is a *generalised* self-model rather than a
  relabel of a single dyadic belief.
* **Deterministic.** Entries sort by ``(-salience, axis, key)``, cited ids are
  ``tuple(sorted(...))`` and bonds are visited in ``other_agent_id`` order, so
  a fixed input yields byte-stable downstream prompts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict

from erre_sandbox.cognition.belief_ids import belief_record_id
from erre_sandbox.contracts.cognition_layers import (
    PromotedEvidenceUnit,
    SubjectiveWorldModel,
    WorldModelEntry,
    WorldModelSnapshot,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from erre_sandbox.contracts.cognition_layers import WorldModelUpdateHint
    from erre_sandbox.schemas import RelationshipBond, SemanticMemoryRecord


_SELF_MIN_DISTINCT_DYADS: Final[int] = 2
"""``self`` axis emits only with at least this many distinct dyads.

A single dyad would make ``self.relational_disposition`` a relabel of a dyadic
belief, violating the class-wise ⊥ dyadic orthogonality. Two or more
distinct dyads make the aggregate a genuine *generalised* self-model.
"""

_RELATIONAL_DISPOSITION_KEY: Final[str] = "relational_disposition"
"""``self`` axis key for the agent's generalised pro-/anti-social stance."""


@dataclass(frozen=True)
class _Evidence:
    """One promoted dyad: the belief record (id / confidence) + its bond."""

    record: SemanticMemoryRecord
    bond: RelationshipBond


def _recency_weight(current_tick: int, last_updated_tick: int, half_life: int) -> float:
    """Exponential recency decay in ``(0, 1]`` (1.0 when freshly updated).

    Folds interaction recency into entry salience (DA-M10B-7) without adding a
    separate ``temporal`` axis: a stale belief ranks below a fresh one of equal
    magnitude/confidence.
    """
    age = max(0, current_tick - last_updated_tick)
    return 0.5 ** (age / float(half_life))


def _salience(entry: WorldModelEntry, current_tick: int) -> float:
    """Ranking score = ``|value| * confidence * recency`` (not a stored field)."""
    recency = _recency_weight(
        current_tick,
        entry.last_updated_tick,
        entry.decay_half_life_ticks,
    )
    return abs(entry.value) * entry.confidence * recency


def _last_tick(evidence: Sequence[_Evidence], *, current_tick: int) -> int:
    """Max non-``None`` ``last_interaction_tick``; ``current_tick`` if all None."""
    ticks = [
        e.bond.last_interaction_tick
        for e in evidence
        if e.bond.last_interaction_tick is not None
    ]
    return max(ticks) if ticks else current_tick


def _sorted_cited(evidence: Sequence[_Evidence]) -> tuple[str, ...]:
    """Deterministic, deduplicated, sorted cited record ids."""
    return tuple(sorted({e.record.id for e in evidence}))


def _derive_env(
    evidence: Sequence[_Evidence],
    *,
    current_tick: int,
) -> list[WorldModelEntry]:
    """One ``env`` entry per interaction zone (bonds with a known last zone).

    ``value`` = mean affinity in the zone (how positively the individual
    relates to others *there*), ``confidence`` = mean familiarity. Bonds whose
    ``last_interaction_zone`` is ``None`` are skipped for ``env`` (no zone to
    key on) but still feed ``self``.
    """
    by_zone: dict[str, list[_Evidence]] = {}
    for e in evidence:
        zone = e.bond.last_interaction_zone
        if zone is None:
            continue
        by_zone.setdefault(zone.value, []).append(e)

    entries: list[WorldModelEntry] = []
    # ``sorted`` keeps the pre-final-sort order deterministic too (the final
    # salience sort would mask insertion order, but an explicit sort is cheaper
    # to reason about than relying on dict-insertion order — code-review MED-2).
    for zone_key, group in sorted(by_zone.items()):
        affinity = sum(e.bond.affinity for e in group) / len(group)
        familiarity = sum(e.bond.familiarity for e in group) / len(group)
        entries.append(
            WorldModelEntry(
                axis="env",
                key=zone_key,
                value=affinity,
                confidence=familiarity,
                cited_memory_ids=_sorted_cited(group),
                last_updated_tick=_last_tick(group, current_tick=current_tick),
            ),
        )
    return entries


def _derive_self(
    evidence: Sequence[_Evidence],
    *,
    current_tick: int,
) -> list[WorldModelEntry]:
    """A single generalised ``self`` disposition entry (>= 2 distinct dyads).

    ``value`` = mean affinity across dyads (net pro-/anti-social stance).
    ``confidence`` = mean belief confidence * **agreement** (the fraction by
    which the dyad affinity signs agree), so a self-model built from conflicting
    dyads (trust some, clash others) is low-confidence rather than a misleading
    near-zero average presented confidently.
    """
    distinct = {e.bond.other_agent_id for e in evidence}
    if len(distinct) < _SELF_MIN_DISTINCT_DYADS:
        return []

    affinities = [e.bond.affinity for e in evidence]
    value = sum(affinities) / len(affinities)
    mean_conf = sum(e.record.confidence for e in evidence) / len(evidence)
    # Agreement in [0, 1]: 1.0 when every dyad shares one sign, ~0 when balanced.
    signs = [(1 if a > 0 else -1 if a < 0 else 0) for a in affinities]
    agreement = abs(sum(signs)) / len(signs)
    confidence = max(0.0, min(1.0, mean_conf * agreement))
    return [
        WorldModelEntry(
            axis="self",
            key=_RELATIONAL_DISPOSITION_KEY,
            value=value,
            confidence=confidence,
            cited_memory_ids=_sorted_cited(evidence),
            last_updated_tick=_last_tick(evidence, current_tick=current_tick),
        ),
    ]


# Module-local deriver table (DA-M10B-11): a small fixed tuple, not a plugin
# registry. concept / norm / temporal have no deterministic observable evidence
# in M10-B and are intentionally absent (no fabricated axes); a future milestone
# adds a deriver here when a structured evidence type for them exists.
_DERIVERS: Final = (_derive_env, _derive_self)


def collect_promoted_evidence(
    belief_records: Sequence[SemanticMemoryRecord],
    bonds: Sequence[RelationshipBond],
    *,
    agent_id: str,
) -> list[_Evidence]:
    """Match each bond to its promoted belief record (single source of truth).

    The *set* of promoted dyads ``synthesize_world_model`` derives entries from
    and :func:`collect_promoted_evidence_units` persists are identical because
    both route through this one helper — so the persisted H2 substrate can never
    drift from the algorithm that produced the entries (stage-A ADR §6).

    A dyad is evidence iff its bond's ``other_agent_id`` resolves (via the
    deterministic :func:`belief_record_id`) to a belief-promoted record owned by
    *agent_id*: foreign-agent records, non-belief records (``belief_kind is None``)
    and orphan bonds (no matching record) are all rejected. Visited in
    ``other_agent_id`` order so a fixed input is byte-stable downstream.
    """
    valid_by_id: dict[str, SemanticMemoryRecord] = {
        r.id: r
        for r in belief_records
        if r.agent_id == agent_id and r.belief_kind is not None
    }
    evidence: list[_Evidence] = []
    for bond in sorted(bonds, key=lambda b: b.other_agent_id):
        record = valid_by_id.get(belief_record_id(agent_id, bond.other_agent_id))
        if record is not None:
            evidence.append(_Evidence(record=record, bond=bond))
    return evidence


def collect_promoted_evidence_units(
    belief_records: Sequence[SemanticMemoryRecord],
    bonds: Sequence[RelationshipBond],
    *,
    agent_id: str,
) -> list[PromotedEvidenceUnit]:
    """Project the matched promoted evidence into serialisable units (M10-A 段B).

    The H2 conformance substrate carrier: the cognition cycle calls this in its
    flag-on block and rides the result out on ``CycleResult.world_model_evidence``
    so the ``world`` layer never imports ``memory`` (mirrors ``belief_classes``,
    DA-M11C2-2 / DA-SB-1). Units are returned in ``other_agent_id`` order
    (:func:`collect_promoted_evidence` sorts bonds by it) so a fixed input yields
    a byte-stable persisted payload.

    Floats are **not** rounded here — the contract type stays exact for any other
    consumer; the trace serialiser owns the ``round(6)`` quantisation (DA-SB-4).
    """
    return [
        PromotedEvidenceUnit(
            other_agent_id=e.bond.other_agent_id,
            belief_kind=e.record.belief_kind,
            confidence=e.record.confidence,
            affinity=e.bond.affinity,
            familiarity=e.bond.familiarity,
            last_interaction_zone=e.bond.last_interaction_zone,
            last_interaction_tick=e.bond.last_interaction_tick,
        )
        for e in collect_promoted_evidence(belief_records, bonds, agent_id=agent_id)
    ]


def synthesize_world_model(
    belief_records: Sequence[SemanticMemoryRecord],
    bonds: Sequence[RelationshipBond],
    *,
    agent_id: str,
    current_tick: int,
    max_entries: int = 50,
) -> SubjectiveWorldModel:
    """Distil observable evidence into a bounded :class:`SubjectiveWorldModel`.

    Pure and deterministic. The cognition cycle reads *belief_records* via
    :meth:`MemoryStore.list_semantic_beliefs` and passes the agent's bonds.

    Evidence is the set of *promoted dyads*: a belief record whose deterministic
    id matches a bond. Foreign-agent records (``agent_id`` mismatch), non-belief
    records (``belief_kind is None``) and orphan records (no matching bond) are
    rejected, so no entry can cite a record outside the valid promoted set.

    Args:
        belief_records: The agent's belief-promoted semantic records.
        bonds: The agent's current relationship bonds.
        agent_id: The synthesising agent; records for any other agent are
            ignored (defensive — the store query already scopes by agent).
        current_tick: Used for recency-weighted salience ranking.
        max_entries: Hard upper bound on retained entries (schema allows 50).

    Returns:
        A :class:`SubjectiveWorldModel` whose entries are sorted by descending
        salience (ties broken by ``axis`` then ``key``) and capped at
        *max_entries*.
    """
    evidence = collect_promoted_evidence(belief_records, bonds, agent_id=agent_id)

    entries: list[WorldModelEntry] = []
    for deriver in _DERIVERS:
        entries.extend(deriver(evidence, current_tick=current_tick))

    entries.sort(key=lambda e: (-_salience(e, current_tick), e.axis, e.key))
    return SubjectiveWorldModel(entries=entries[:max_entries])


# ---------------------------------------------------------------------------
# M10-C — bounded LLM value modulation on top of the evidence floor
# ---------------------------------------------------------------------------
#
# Core invariant (decisions.md DA-M10C-2/4): the per-tick ``synthesize_world_model``
# output is the **evidence floor** and is authoritative for confidence /
# last_updated_tick / cited ids. The LLM, via a verified
# :class:`WorldModelUpdateHint`, may only nudge an existing entry's ``value`` by a
# bounded step in the direction of its current sign — it can never flip a sign,
# create an entry, or touch confidence / recency. Evidence change drops the
# modulation, so a belief the world stopped supporting cannot be kept alive by an
# LLM that liked it (continuity-bias guard).

VALUE_STEP: Final[float] = 0.05
"""Per-tick magnitude nudge a verified hint applies to an entry's ``value``.

The ``value`` step is calibrated by property tests (repeated nudge
converges to the cap, evidence change resets), *not* by the adoption-rate band.
"""

MAX_TOTAL_MODULATION: Final[float] = 0.15
"""Hard cap on how far the carried modulation may drift an entry from its floor.

Enforced in :func:`reconcile_world_model` when carrying a modulation across a
fresh floor. A same-direction nudge in the current tick may transiently sit one
:data:`VALUE_STEP` beyond this (~0.20, the top of the recommended band)
*before* it is injected — but the next reconcile re-clamps to ``+/-0.15`` so no
prompt ever shows a value past the cap.
"""


_FLOOR_FINGERPRINT_PRECISION: Final[int] = 6
"""Decimal places the floor fingerprint rounds value/confidence to.

``synthesize_world_model`` derives value/confidence as floating-point means
(``sum()/len()``); comparing those with exact ``==`` would treat sub-ULP
representational jitter as an evidence change and silently reset the LLM
modulation every tick. Rounding to 6 dp absorbs that jitter while staying far
below any real affinity/familiarity change (>= 0.01), so a genuine evidence shift
still drops the stale modulation (code-review HIGH-1)."""


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _floor_fingerprint(
    entry: WorldModelEntry,
) -> tuple[str, str, float, float, tuple[str, ...], int]:
    """Identity of an entry's *evidence* content (DA-M10C-2).

    A modulation is carried across ticks only while the floor entry it was based
    on is fingerprint-identical; any change here (value/confidence/cited/recency
    moved) means the evidence shifted, so the stale LLM modulation is dropped.
    value/confidence are rounded (:data:`_FLOOR_FINGERPRINT_PRECISION`) so
    floating-point mean jitter is not mistaken for an evidence change (HIGH-1).
    """
    return (
        entry.axis,
        entry.key,
        round(entry.value, _FLOOR_FINGERPRINT_PRECISION),
        round(entry.confidence, _FLOOR_FINGERPRINT_PRECISION),
        entry.cited_memory_ids,
        entry.last_updated_tick,
    )


def _nudge_value(value: float, direction: str) -> float | None:
    """Return the bounded one-step nudge of ``value``, or ``None`` if inapplicable.

    Sign is preserved (``weaken`` stops at 0, never crosses it; ``strengthen``
    grows magnitude toward 1). A zero-valued entry has no sign to push, so both
    directions are inapplicable.
    """
    if value == 0.0:
        return None
    sign = 1.0 if value > 0 else -1.0
    magnitude = abs(value)
    if direction == "strengthen":
        magnitude = min(1.0, magnitude + VALUE_STEP)
    elif direction == "weaken":
        magnitude = max(0.0, magnitude - VALUE_STEP)
    else:  # "no_change" is handled by the caller; defensive.
        return None
    return sign * magnitude


def apply_world_model_update_hint(
    swm: SubjectiveWorldModel,
    hint: WorldModelUpdateHint,
    exposed_entry_citations: Mapping[tuple[str, str], frozenset[str]],
) -> SubjectiveWorldModel | None:
    """Apply a verified hint as a bounded value nudge, or reject it (``None``).

    Pure. The LLM is a *candidate*; Python is the *authority* (ME-9 guard). A hint
    is adopted only when **all** of these hold (else ``None`` — non-adoption):

    * its ``(axis, key)`` names an entry that was actually displayed this turn
      (present in *exposed_entry_citations*);
    * every ``cited_memory_id`` is among the belief ids displayed *on that very
      entry* (entry-local grounding, DA-M10C-3 — not a global memory set);
    * ``direction`` is ``strengthen`` / ``weaken`` (``no_change`` is a no-op);
    * the nudge actually moves ``value`` (a zero-valued or already-saturated entry
      yields no change).

    Only ``value`` changes; ``confidence`` / ``last_updated_tick`` /
    ``cited_memory_ids`` stay floor-derived (DA-M10C-4) so the LLM cannot launder
    recency or certainty. The cumulative ``+/-MAX_TOTAL_MODULATION`` cap is
    enforced by :func:`reconcile_world_model`, not here.

    Args:
        swm: The reconciled SWM that was injected this turn.
        hint: The bounded update the LLM requested.
        exposed_entry_citations: ``(axis, key) -> displayed belief ids`` for the
            entries actually shown this turn (built by
            :func:`erre_sandbox.cognition.prompting.visible_entry_citations`).

    Returns:
        A new :class:`SubjectiveWorldModel` with the one nudged entry, or ``None``
        when the hint is not adopted.
    """
    key = (hint.axis, hint.key)
    visible = exposed_entry_citations.get(key)
    if visible is None:
        return None
    cited = set(hint.cited_memory_ids)
    if not cited or not cited.issubset(visible):
        return None
    if hint.direction == "no_change":
        return None

    idx = next(
        (i for i, e in enumerate(swm.entries) if (e.axis, e.key) == key),
        None,
    )
    if idx is None:  # displayed but absent from the SWM — defensive, shouldn't happen.
        return None
    entry = swm.entries[idx]
    new_value = _nudge_value(entry.value, hint.direction)
    if new_value is None or new_value == entry.value:
        return None
    new_entries = list(swm.entries)
    new_entries[idx] = entry.model_copy(update={"value": new_value})
    return SubjectiveWorldModel(entries=new_entries)


class WorldModelRuntimeState(BaseModel):
    """Per-agent runtime state separating the evidence floor from LLM modulation.

    Held by ``world.tick.AgentRuntime`` (never the shared ``CognitionCycle``, to
    avoid multi-agent crosstalk — DA-M10C-6) and carried out of the cycle on
    :class:`~erre_sandbox.cognition.cycle.CycleResult`. Storing both the
    ``base_floor`` the modulations were computed against *and* the ``modulated``
    result lets :func:`reconcile_world_model` tell an evidence change apart from
    an LLM nudge (DA-M10C-2) instead of guessing from a single-SWM diff.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_floor: SubjectiveWorldModel
    modulated: SubjectiveWorldModel


def project_world_model_snapshot(
    state: WorldModelRuntimeState,
) -> WorldModelSnapshot:
    """Project a live :class:`WorldModelRuntimeState` into an immutable read-model.

    Pure and deterministic. ``base_floor`` / ``modulated`` are **deep-copied**
    — although :class:`WorldModelSnapshot` is ``frozen``, its inner
    :class:`SubjectiveWorldModel.entries` is a mutable ``list`` of non-frozen
    :class:`WorldModelEntry`, so sharing the instances would let a snapshot
    consumer mutate the single-source ``AgentRuntime`` state. The deep copy
    severs that alias (owner single source, ``contracts`` read-model is derived).
    """
    return WorldModelSnapshot(
        base_floor=state.base_floor.model_copy(deep=True),
        modulated=state.modulated.model_copy(deep=True),
    )


def reconcile_world_model(
    state: WorldModelRuntimeState | None,
    new_floor: SubjectiveWorldModel,
) -> WorldModelRuntimeState:
    """Carry bounded LLM value-modulations forward onto a fresh evidence floor.

    Pure and deterministic. For each entry of *new_floor* (already salience-sorted
    by :func:`synthesize_world_model`):

    * if the previous floor had a fingerprint-identical entry for the same
      ``(axis, key)``, the evidence is unchanged, so the prior modulated value is
      carried — clamped to ``floor +/- MAX_TOTAL_MODULATION`` and to ``[-1, 1]``;
    * otherwise (evidence moved, or the entry is new) the modulation is dropped and
      the floor value stands.

    The floor's salience order is preserved (the LLM nudges *values*, never the
    ranking). On the first tick (``state is None``) the modulated view equals the
    floor.
    """
    if state is None:
        return WorldModelRuntimeState(base_floor=new_floor, modulated=new_floor)

    prev_by_key = {(e.axis, e.key): e for e in state.base_floor.entries}
    mod_by_key = {(e.axis, e.key): e for e in state.modulated.entries}

    reconciled: list[WorldModelEntry] = []
    for e_new in new_floor.entries:
        key = (e_new.axis, e_new.key)
        prev = prev_by_key.get(key)
        mod = mod_by_key.get(key)
        if (
            prev is not None
            and mod is not None
            and _floor_fingerprint(prev) == _floor_fingerprint(e_new)
        ):
            lo = max(-1.0, e_new.value - MAX_TOTAL_MODULATION)
            hi = min(1.0, e_new.value + MAX_TOTAL_MODULATION)
            capped = _clamp(mod.value, lo, hi)
            reconciled.append(
                e_new
                if capped == e_new.value
                else e_new.model_copy(update={"value": capped}),
            )
        else:
            reconciled.append(e_new)

    return WorldModelRuntimeState(
        base_floor=new_floor,
        modulated=SubjectiveWorldModel(entries=reconciled),
    )


__all__ = [
    "MAX_TOTAL_MODULATION",
    "VALUE_STEP",
    "WorldModelRuntimeState",
    "apply_world_model_update_hint",
    "collect_promoted_evidence_units",
    "reconcile_world_model",
    "synthesize_world_model",
]
