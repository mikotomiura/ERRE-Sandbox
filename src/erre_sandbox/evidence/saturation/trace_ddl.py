"""DDL + row builder for ``metrics.swm_modulation_saturation_trace`` (ADR section 5).

A per-``(agent, axis, key, tick)`` longitudinal trace of the **post-reconcile,
pre-nudge** SWM (saturation ADR section 2.1): for every entry that
``reconcile_world_model`` produced this tick, one row records the floor value,
the modulated value, and a hash of the floor entry's fingerprint. The loader
recomputes magnitude / effective cap_distance / saturation / drop_rate from these
raw values (trace stores raw, loader recomputes — recompute-stable, ADR section 5).

Placement mirrors ``evidence.individuation.trace_ddl`` but the table is a
**new-module shadow**: it shares no column order, no measure, and no schema with
``individual_state_trace`` so the frozen M11-C3b gates stay untouched. The module
owns its column order as the single source of truth and never embeds a
``metrics``-dot schema literal — the qualified name is composed by the caller from
the ``METRICS_SCHEMA`` constant (CI eval-egress grep gate). The table is created
**only when the individual layer is enabled** (``bootstrap_saturation_trace_schema``
is never called from ``bootstrap_schema``), so a flag-off run leaves the DuckDB
byte-identical.

The table lives in the ``metrics`` schema (eval-only): it carries individual-layer
numeric outputs, never the raw training-egress utterance stream.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from erre_sandbox.evidence.saturation.constants import FINGERPRINT_PRECISION

if TYPE_CHECKING:
    import duckdb

    from erre_sandbox.contracts.cognition_layers import (
        WorldModelEntry,
        WorldModelSnapshot,
    )

TABLE_NAME: Final[str] = "swm_modulation_saturation_trace"
"""Bare table name inside the metrics schema (never qualified here)."""

# Column order is the single source of truth: ``SaturationTraceRow.to_row`` and
# ``column_names`` both derive from this, and the orchestrator's INSERT binds in
# this order. ``seed`` is UBIGINT because the per-run seed is
# ``golden_baseline.derive_seed`` — an unsigned 64-bit blake2b digest whose value
# overflows a signed BIGINT (DA-IMPL-2 / ADR section 5 revised BIGINT -> UBIGINT).
# Everything is NOT NULL: a saturation row is only ever written for a concrete
# reconciled entry (no nullable snapshot field, unlike individual_state_trace).
_SATURATION_TRACE_COLUMNS: Final[tuple[tuple[str, str], ...]] = (
    ("run_id", "TEXT NOT NULL"),
    ("seed", "UBIGINT NOT NULL"),
    ("individual_id", "TEXT NOT NULL"),
    ("axis", "TEXT NOT NULL"),
    ("key", "TEXT NOT NULL"),
    ("tick", "BIGINT NOT NULL"),
    ("base_floor_value", "DOUBLE NOT NULL"),
    ("modulated_value", "DOUBLE NOT NULL"),
    ("floor_fingerprint_hash", "TEXT NOT NULL"),
    ("individual_layer_enabled", "BOOLEAN NOT NULL"),
)

SATURATION_TRACE_COLUMN_COUNT: Final[int] = len(_SATURATION_TRACE_COLUMNS)


def column_names() -> tuple[str, ...]:
    """Ordered column names — the order ``SaturationTraceRow.to_row`` emits."""
    return tuple(name for name, _ in _SATURATION_TRACE_COLUMNS)


def saturation_trace_ddl_sql(schema: str, table: str = TABLE_NAME) -> str:
    """Return ``CREATE TABLE IF NOT EXISTS {schema}.{table}`` DDL.

    *schema* is supplied by the caller (the eval orchestrator passes
    ``METRICS_SCHEMA``); this module never embeds a schema-dot literal. The DDL is
    idempotent (``IF NOT EXISTS``) so the flag-on conditional bootstrap is safe to
    call repeatedly. ``tick >= 0`` is the only structural CHECK.
    """
    cols = ",\n  ".join(
        f"{name} {sqltype}" for name, sqltype in _SATURATION_TRACE_COLUMNS
    )
    return (
        f"CREATE TABLE IF NOT EXISTS {schema}.{table} (\n"
        f"  {cols},\n"
        f"  CHECK (tick >= 0)\n"
        f")"
    )


def bootstrap_saturation_trace_schema(
    con: duckdb.DuckDBPyConnection, schema: str, table: str = TABLE_NAME
) -> None:
    """Create the trace table on *con* (flag-on conditional bootstrap).

    Called **only** from the eval orchestrator's individual-layer-enabled branch —
    never from ``bootstrap_schema`` — so a flag-off run never issues this DDL and
    the DuckDB stays byte-identical.
    """
    con.execute(saturation_trace_ddl_sql(schema, table))


def floor_fingerprint_hash(entry: WorldModelEntry) -> str:
    """Hash an entry's evidence-content fingerprint (ADR section 5 / DA-SPA-4).

    Mirrors ``cognition.world_model._floor_fingerprint``: the identity tuple is
    ``(axis, key, round(value, 6), round(confidence, 6), cited_memory_ids,
    last_updated_tick)`` with value/confidence rounded to
    :data:`~erre_sandbox.evidence.saturation.constants.FINGERPRINT_PRECISION` (the
    same precision the reconcile uses to drop a stale modulation). The tuple is
    serialised canonically (a JSON array, ``cited_memory_ids`` as an ordered list)
    and SHA-256 hashed so the loader can tell a *drop-induced* ``magnitude == 0``
    (fingerprint changed) apart from an *un-modulated* ``magnitude == 0``
    (fingerprint stable) — base/modulated values alone cannot distinguish them.
    """
    payload = [
        entry.axis,
        entry.key,
        round(entry.value, FINGERPRINT_PRECISION),
        round(entry.confidence, FINGERPRINT_PRECISION),
        list(entry.cited_memory_ids),
        entry.last_updated_tick,
    ]
    canonical = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SaturationTraceRow:
    """One ``(run_id, seed, individual_id, axis, key, tick)`` saturation row.

    Immutable; ``to_row`` emits values in ``_SATURATION_TRACE_COLUMNS`` order so
    the INSERT bind stays in lockstep with the DDL.
    """

    run_id: str
    seed: int
    individual_id: str
    axis: str
    key: str
    tick: int
    base_floor_value: float
    modulated_value: float
    floor_fingerprint_hash: str
    individual_layer_enabled: bool

    def to_row(self) -> tuple[object, ...]:
        """Positional tuple in DDL column order (INSERT bind order)."""
        return (
            self.run_id,
            self.seed,
            self.individual_id,
            self.axis,
            self.key,
            self.tick,
            self.base_floor_value,
            self.modulated_value,
            self.floor_fingerprint_hash,
            self.individual_layer_enabled,
        )


def build_saturation_trace_rows(
    snapshot: WorldModelSnapshot,
    *,
    run_id: str,
    seed: int,
    individual_id: str,
    tick: int,
    individual_layer_enabled: bool,
) -> list[SaturationTraceRow]:
    """Explode a post-reconcile snapshot into per-``(axis, key)`` trace rows (pure).

    *snapshot* is the **post-reconcile, pre-nudge** ``WorldModelSnapshot`` captured
    at ``cycle.py`` reconcile (ADR section 2.1) and carried out on ``CycleResult``;
    ``world`` passes it straight through so it never imports ``cognition``. One row
    per floor entry: ``base_floor_value`` is the floor value, ``modulated_value``
    is the matching modulated entry's value (matched by ``(axis, key)`` — the
    reconcile invariant guarantees the modulated view shares the floor's key set),
    and ``floor_fingerprint_hash`` is computed from the **floor** entry. A floor key
    absent from the modulated view violates the reconcile invariant, so it
    **raises** :class:`ValueError` (loud-not-silent, Codex LOW-1) rather than
    recording a phantom ``magnitude == 0`` that would silently bias the probe toward
    NON-SATURATED.

    ``individual_layer_enabled`` is bound here (always ``True`` on this flag-on
    path) so the loader can reject a provenance-false seed; binding it explicitly
    avoids the M11-C3b-exec column-omission bug.
    """
    modulated_by_key = {
        (entry.axis, entry.key): entry.value for entry in snapshot.modulated.entries
    }
    rows: list[SaturationTraceRow] = []
    for floor_entry in snapshot.base_floor.entries:
        key = (floor_entry.axis, floor_entry.key)
        if key not in modulated_by_key:
            raise ValueError(
                "reconcile invariant violated: floor entry "
                f"{key!r} (individual {individual_id!r}, tick {tick}) has no "
                "matching modulated entry"
            )
        modulated_value = modulated_by_key[key]
        rows.append(
            SaturationTraceRow(
                run_id=run_id,
                seed=seed,
                individual_id=individual_id,
                axis=floor_entry.axis,
                key=floor_entry.key,
                tick=tick,
                base_floor_value=floor_entry.value,
                modulated_value=modulated_value,
                floor_fingerprint_hash=floor_fingerprint_hash(floor_entry),
                individual_layer_enabled=individual_layer_enabled,
            )
        )
    return rows


__all__ = [
    "SATURATION_TRACE_COLUMN_COUNT",
    "TABLE_NAME",
    "SaturationTraceRow",
    "bootstrap_saturation_trace_schema",
    "build_saturation_trace_rows",
    "column_names",
    "floor_fingerprint_hash",
    "saturation_trace_ddl_sql",
]
