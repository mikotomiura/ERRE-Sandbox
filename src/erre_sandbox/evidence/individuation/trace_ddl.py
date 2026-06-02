"""DDL + row builder for ``metrics.individual_state_trace`` (M11-C2 substrate).

Per-tick individual-state substrate captured **flag-on only** so that the
loader can recompute per-individual ``belief_variance`` (and report the
diagnostic development-stage / narrative-coherence series) without the live
``world`` loop ever importing ``memory`` (the source flows through
``CycleResult.belief_classes``; DA-M11C2-2).

Placement follows ``ddl.py``: this module owns the **column order** as the
single source of truth and never embeds a ``metrics.`` schema literal — the
qualified name is composed by the caller from the ``METRICS_SCHEMA`` constant
(CI eval-egress grep gate). The table is created **only when the individual
layer is enabled**: ``bootstrap_schema`` does not
touch it, so a flag-off run leaves the DuckDB byte-identical.

The table lives in the metrics schema (NOT ``raw_dialog``): it carries
individual-layer outputs, never the raw training-egress utterance stream, so
``ALLOWED_RAW_DIALOG_KEYS`` is untouched (DB byte ⊥ egress invariance).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Sequence

    import duckdb

    from erre_sandbox.contracts.cognition_layers import (
        IndividualProfile,
        PromotedEvidenceUnit,
    )

TABLE_NAME: Final[str] = "individual_state_trace"
"""Bare table name inside the metrics schema (never qualified here)."""

# Column order is the single source of truth: ``IndividualStateTraceRow.to_row``
# and ``column_names`` both derive from this. Nullable everywhere the snapshot
# field can be ``None`` (no fabrication — mirrors C1's Option B): a flag-on tick
# without a synthesised arc / advanced stage writes NULL, not a phantom value.
_INDIVIDUAL_STATE_TRACE_COLUMNS: Final[tuple[tuple[str, str], ...]] = (
    ("run_id", "TEXT NOT NULL"),
    ("individual_id", "TEXT NOT NULL"),
    ("tick", "BIGINT NOT NULL"),
    ("development_stage", "TEXT"),
    ("coherence_score", "DOUBLE"),
    ("belief_classes_json", "TEXT"),
    ("arc_segment_count", "BIGINT NOT NULL"),
    # M10-A E2 (DA-S1-2): per-individual SubjectiveWorldModel key set, persisted
    # as a ``[["axis","key"], ...]`` pair-array JSON (NOT ``"axis:key"`` strings —
    # WorldModelEntry.key is an arbitrary string that may contain ``:``). NULL
    # when no SWM was synthesised (honest "not captured"), ``"[]"`` when a SWM was
    # synthesised but holds no entries. Appended last so the column order of the
    # M11-C2 prefix is unchanged.
    ("world_model_keys_json", "TEXT"),
    # M10-A 段B (DA-SB-2): per-dyad raw promoted evidence units, persisted as a
    # canonical array-of-objects JSON
    # ``[{"other_agent_id","belief_kind","confidence","affinity","familiarity",
    # "last_interaction_zone","last_interaction_tick"}, ...]``. This is the H2
    # value-aware conformance substrate (stage-A ADR §6): the synthesised SWM keys
    # (``world_model_keys_json``) aggregate per-dyad values away, so the raw unit is
    # required to recompute the observed (axis,key)-intersection distance and the
    # owner-shuffle null. NULL when no SWM was synthesised (honest "not captured");
    # ``"[]"`` when synthesised with no promoted dyad. Appended last so the prior
    # column order (M11-C2 prefix + E2 world_model_keys_json) is unchanged.
    ("world_model_evidence_json", "TEXT"),
)

INDIVIDUAL_STATE_TRACE_COLUMN_COUNT: Final[int] = len(_INDIVIDUAL_STATE_TRACE_COLUMNS)


def column_names() -> tuple[str, ...]:
    """Ordered column names — the order ``IndividualStateTraceRow.to_row`` emits."""
    return tuple(name for name, _ in _INDIVIDUAL_STATE_TRACE_COLUMNS)


def individual_state_trace_ddl_sql(schema: str, table: str = TABLE_NAME) -> str:
    """Return ``CREATE TABLE IF NOT EXISTS {schema}.{table}`` DDL.

    *schema* is supplied by the caller (the eval orchestrator passes
    ``METRICS_SCHEMA``); this module never embeds a schema-dot literal. The DDL
    is idempotent (``IF NOT EXISTS``) so the flag-on conditional bootstrap is
    safe to call repeatedly. ``tick >= 0`` is the only structural CHECK — trace
    rows are always real ticks (no aggregate sentinel, unlike ``individuation``).
    """
    cols = ",\n  ".join(
        f"{name} {sqltype}" for name, sqltype in _INDIVIDUAL_STATE_TRACE_COLUMNS
    )
    return (
        f"CREATE TABLE IF NOT EXISTS {schema}.{table} (\n"
        f"  {cols},\n"
        f"  CHECK (tick >= 0)\n"
        f")"
    )


def bootstrap_individual_state_trace_schema(
    con: duckdb.DuckDBPyConnection, schema: str, table: str = TABLE_NAME
) -> None:
    """Create the trace table on *con* (flag-on conditional bootstrap, DA-M11C2-1).

    Called **only** from the eval orchestrator's individual-layer-enabled branch
    — never from ``bootstrap_schema`` — so a flag-off run never issues this DDL
    and the DuckDB stays byte-identical.
    """
    con.execute(individual_state_trace_ddl_sql(schema, table))


@dataclass(frozen=True, slots=True)
class IndividualStateTraceRow:
    """One ``(run_id, individual_id, tick)`` individual-state trace row.

    Immutable; ``to_row`` emits values in ``_INDIVIDUAL_STATE_TRACE_COLUMNS``
    order so the INSERT bind stays in lockstep with the DDL.
    """

    run_id: str
    individual_id: str
    tick: int
    development_stage: str | None
    coherence_score: float | None
    belief_classes_json: str | None
    arc_segment_count: int
    world_model_keys_json: str | None
    world_model_evidence_json: str | None

    def to_row(self) -> tuple[object, ...]:
        """Positional tuple in DDL column order (INSERT bind order)."""
        return (
            self.run_id,
            self.individual_id,
            self.tick,
            self.development_stage,
            self.coherence_score,
            self.belief_classes_json,
            self.arc_segment_count,
            self.world_model_keys_json,
            self.world_model_evidence_json,
        )


def _world_model_keys_json(profile: IndividualProfile) -> str | None:
    """Serialise the individual's SWM key set as a ``[["axis","key"], ...]`` JSON.

    M10-A E2 (DA-S1-2/DA-S1-5). The key set is taken from the **evidence floor**
    (``world_model.base_floor`` — belief-records + bonds derived, LLM-uninvolved);
    by the ``reconcile_world_model`` invariant the modulated view shares the same
    ``(axis, key)`` set (modulation only nudges values), so for the key-overlap
    substrate the floor is the honest, deterministic source.

    Returns ``None`` when no SWM was synthesised (``world_model is None`` — a
    flag-off or pre-synthesis tick: honest "not captured"), distinct from an
    empty ``"[]"`` (a synthesised SWM holding no entries). Keys are de-duplicated
    and sorted so a fixed SWM yields a byte-stable payload (recompute-stable).
    Pair arrays — not ``"axis:key"`` strings — because ``WorldModelEntry.key`` is
    an arbitrary string that may contain ``:`` (DA-S1-2).
    """
    snapshot = profile.world_model
    if snapshot is None:
        return None
    keys = sorted({(entry.axis, entry.key) for entry in snapshot.base_floor.entries})
    return json.dumps([[axis, key] for axis, key in keys])


_EVIDENCE_FLOAT_PRECISION: Final[int] = 6
"""Decimal places evidence floats round to (M10-A 段B, DA-SB-4).

Mirrors ``cognition.world_model._FLOOR_FINGERPRINT_PRECISION`` (kept as a local
constant rather than importing across the cognition→evidence layer). Quantises
``affinity`` / ``familiarity`` / ``confidence`` so a fixed SWM yields a byte-stable
payload and the persisted substrate recomputes to the same H2 distance as the
round(6)-quantised in-memory evidence (the round-trip test compares on this same
quantised basis, not against the raw float)."""


def _world_model_evidence_json(
    units: Sequence[PromotedEvidenceUnit] | None,
) -> str | None:
    """Serialise per-dyad raw evidence units as a canonical array-of-objects JSON.

    M10-A 段B (DA-SB-2). ``None`` (flag-off / pre-synthesis tick) → NULL; an empty
    sequence (a synthesised SWM with no promoted dyad) → ``"[]"`` — the same honest
    None/empty distinction as :func:`_world_model_keys_json`. Objects use the
    **canonical** ``RelationshipBond`` / ``SemanticMemoryRecord`` field names (no
    abbreviation) and are emitted in ``other_agent_id`` order with sorted keys so a
    fixed input is byte-stable (recompute-stable). Floats round to
    :data:`_EVIDENCE_FLOAT_PRECISION`; ``last_interaction_zone`` is the
    ``Zone.value`` string (or ``None``), ``last_interaction_tick`` an int (or
    ``None``).
    """
    if units is None:
        return None
    payload = [
        {
            "other_agent_id": unit.other_agent_id,
            "belief_kind": unit.belief_kind,
            "confidence": round(unit.confidence, _EVIDENCE_FLOAT_PRECISION),
            "affinity": round(unit.affinity, _EVIDENCE_FLOAT_PRECISION),
            "familiarity": round(unit.familiarity, _EVIDENCE_FLOAT_PRECISION),
            "last_interaction_zone": (
                None
                if unit.last_interaction_zone is None
                else unit.last_interaction_zone.value
            ),
            "last_interaction_tick": unit.last_interaction_tick,
        }
        for unit in sorted(units, key=lambda u: u.other_agent_id)
    ]
    return json.dumps(payload, sort_keys=True)


def build_individual_state_trace_row(
    profile: IndividualProfile,
    belief_classes: list[str] | None,
    world_model_evidence: Sequence[PromotedEvidenceUnit] | None,
    *,
    run_id: str,
    tick: int,
) -> IndividualStateTraceRow:
    """Project a C1 :class:`IndividualProfile` snapshot into a trace row (pure).

    None-safe throughout: ``development_state`` / ``narrative_arc`` are ``None``
    on a flag-on tick that advanced no stage / synthesised no arc, so the
    categorical / continuous fields stay NULL rather than fabricating a value
    (mirrors C1 Option B). ``arc_segment_count`` reads 0 when there is no arc
    (a count of zero observed segments, per the M11-C2 spec). *run_id* is bound
    by the orchestrator's sink closure — ``world`` never knows it (DA-M11C2-4).
    *belief_classes* comes off ``CycleResult`` so ``world`` never imports
    ``memory`` (DA-M11C2-2); ``None`` flag-off, a possibly-empty list flag-on.
    ``world_model_keys_json`` (M10-A E2) is the SWM key set from the snapshot's
    evidence floor — see :func:`_world_model_keys_json`. ``world_model_evidence``
    (M10-A 段B) is the per-dyad raw promoted evidence carried off ``CycleResult``
    (``None`` flag-off / pre-synthesis) — the H2 conformance substrate, serialised
    by :func:`_world_model_evidence_json`. It is **not** read off *profile*: like
    ``belief_classes`` it rides in separately so ``world`` never imports ``memory``
    (DA-SB-1).
    """
    dev = profile.development_state
    arc = profile.narrative_arc
    belief_classes_json = None if belief_classes is None else json.dumps(belief_classes)
    return IndividualStateTraceRow(
        run_id=run_id,
        individual_id=profile.individual_id,
        tick=tick,
        development_stage=None if dev is None else str(dev.stage),
        coherence_score=None if arc is None else arc.coherence_score,
        belief_classes_json=belief_classes_json,
        arc_segment_count=0 if arc is None else len(arc.arc_segments),
        world_model_keys_json=_world_model_keys_json(profile),
        world_model_evidence_json=_world_model_evidence_json(world_model_evidence),
    )


__all__ = [
    "INDIVIDUAL_STATE_TRACE_COLUMN_COUNT",
    "TABLE_NAME",
    "IndividualStateTraceRow",
    "bootstrap_individual_state_trace_schema",
    "build_individual_state_trace_row",
    "column_names",
    "individual_state_trace_ddl_sql",
]
