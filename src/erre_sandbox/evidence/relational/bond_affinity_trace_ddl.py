"""DDL + row builder for ``swm_bond_affinity_trace`` (instrumentation ADR section 3.1).

A per-``(individual, other_agent, tick)`` longitudinal trace of every
:class:`~erre_sandbox.schemas.RelationshipBond` an agent holds this tick, stored as
**raw** fields: the *signed* affinity, the interaction count, and the bond's recency
(``last_interaction_tick`` / ``last_interaction_zone``). The read side recomputes the
near-miss gate (``|affinity| < 0.45`` ∧ ``ichigo_ichie_count >= 6``) and the stale-bond
guard from these raw values — the capture never bakes the promotion thresholds in, so
already-captured stock stays re-analysable if a threshold later moves (trace stores raw,
loader recomputes; the same recompute-stable pattern the saturation trace uses).

Placement mirrors ``evidence.saturation.trace_ddl`` but the table is a
**new-module shadow**: it shares no column order, no measure, and no schema with the
frozen ``individual_state_trace`` / ``swm_modulation_saturation_trace`` /
``swm_hint_engagement_trace`` / ``swm_floor_input_trace`` tables, so those frozen gates
stay untouched. The module owns its column order as the single source of truth and never
embeds a schema-dot literal — the qualified name is composed by the caller from the
``METRICS_SCHEMA`` constant (CI eval-egress grep gate). The table is created **only when
the individual layer is enabled** (``bootstrap_bond_affinity_trace_schema`` is never
called from ``bootstrap_schema``), so a flag-off run leaves the DuckDB byte-identical.

The table lives in the eval-only metrics schema: it carries individual-layer numeric
outputs, never the raw training-egress utterance stream.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Sequence

    import duckdb

    from erre_sandbox.schemas import RelationshipBond

TABLE_NAME: Final[str] = "swm_bond_affinity_trace"
"""Bare table name inside the metrics schema (never qualified here)."""

# Column order is the single source of truth: ``BondAffinityTraceRow.to_row`` and
# ``column_names`` both derive from this, and the orchestrator's INSERT binds in this
# order. ``seed`` is UBIGINT because the per-run seed is ``golden_baseline.derive_seed``
# — an unsigned 64-bit blake2b digest that overflows a signed BIGINT (saturation trace
# DA-IMPL-2). ``affinity`` is the *signed* bond affinity (the read side takes ``abs``;
# negative clash bonds are gate targets too). ``last_interaction_tick`` /
# ``last_interaction_zone`` are nullable (a bond may never have interacted) and stored
# raw so the loader can recompute the stale-near-miss guard (ADR HIGH-1: a bond that was
# near 0.45 long before a cap-saturated tick must not count as a fresh approach).
_BOND_AFFINITY_TRACE_COLUMNS: Final[tuple[tuple[str, str], ...]] = (
    ("run_id", "TEXT NOT NULL"),
    ("seed", "UBIGINT NOT NULL"),
    ("individual_id", "TEXT NOT NULL"),
    ("other_agent_id", "TEXT NOT NULL"),
    ("tick", "BIGINT NOT NULL"),
    ("affinity", "DOUBLE NOT NULL"),
    ("ichigo_ichie_count", "BIGINT NOT NULL"),
    ("last_interaction_tick", "BIGINT"),
    ("last_interaction_zone", "TEXT"),
    ("individual_layer_enabled", "BOOLEAN NOT NULL"),
)

BOND_AFFINITY_TRACE_COLUMN_COUNT: Final[int] = len(_BOND_AFFINITY_TRACE_COLUMNS)


def column_names() -> tuple[str, ...]:
    """Ordered column names — the order ``BondAffinityTraceRow.to_row`` emits."""
    return tuple(name for name, _ in _BOND_AFFINITY_TRACE_COLUMNS)


def bond_affinity_trace_ddl_sql(schema: str, table: str = TABLE_NAME) -> str:
    """Return ``CREATE TABLE IF NOT EXISTS {schema}.{table}`` DDL.

    *schema* is supplied by the caller (the eval orchestrator passes
    ``METRICS_SCHEMA``); this module never embeds a schema-dot literal. The DDL is
    idempotent (``IF NOT EXISTS``) so the flag-on conditional bootstrap is safe to call
    repeatedly. ``tick >= 0`` is the only structural CHECK.
    """
    cols = ",\n  ".join(
        f"{name} {sqltype}" for name, sqltype in _BOND_AFFINITY_TRACE_COLUMNS
    )
    return (
        f"CREATE TABLE IF NOT EXISTS {schema}.{table} (\n"
        f"  {cols},\n"
        f"  CHECK (tick >= 0)\n"
        f")"
    )


def bootstrap_bond_affinity_trace_schema(
    con: duckdb.DuckDBPyConnection, schema: str, table: str = TABLE_NAME
) -> None:
    """Create the trace table on *con* (flag-on conditional bootstrap).

    Called **only** from the eval orchestrator's individual-layer-enabled branch —
    never from ``bootstrap_schema`` — so a flag-off run never issues this DDL and the
    DuckDB stays byte-identical.
    """
    con.execute(bond_affinity_trace_ddl_sql(schema, table))


@dataclass(frozen=True, slots=True)
class BondAffinityTraceRow:
    """One ``(run_id, seed, individual_id, other_agent_id, tick)`` bond-affinity row.

    Immutable; ``to_row`` emits values in ``_BOND_AFFINITY_TRACE_COLUMNS`` order so the
    INSERT bind stays in lockstep with the DDL. ``affinity`` is signed (clash bonds keep
    their negative sign); ``last_interaction_tick`` / ``last_interaction_zone`` are
    ``None`` for a bond that has not interacted.
    """

    run_id: str
    seed: int
    individual_id: str
    other_agent_id: str
    tick: int
    affinity: float
    ichigo_ichie_count: int
    last_interaction_tick: int | None
    last_interaction_zone: str | None
    individual_layer_enabled: bool

    def to_row(self) -> tuple[object, ...]:
        """Positional tuple in DDL column order (INSERT bind order)."""
        return (
            self.run_id,
            self.seed,
            self.individual_id,
            self.other_agent_id,
            self.tick,
            self.affinity,
            self.ichigo_ichie_count,
            self.last_interaction_tick,
            self.last_interaction_zone,
            self.individual_layer_enabled,
        )


def build_bond_affinity_trace_rows(
    relationships: Sequence[RelationshipBond],
    *,
    run_id: str,
    seed: int,
    individual_id: str,
    tick: int,
    individual_layer_enabled: bool,
) -> list[BondAffinityTraceRow]:
    """Project an agent's bond list into per-dyad trace rows for this tick (pure).

    *relationships* is ``AgentState.relationships`` carried out on
    ``CycleResult.agent_state`` at the ``world`` cycle boundary; ``world`` passes the
    list straight through to the eval-side sink so it never imports ``evidence`` (the
    row build happens here, called by the orchestrator's closure). One row per bond,
    storing the **raw** signed affinity and interaction count — no near-miss flag, no
    threshold-derived column (recompute-stable, ADR section 3.2).
    ``last_interaction_zone`` (a :class:`~erre_sandbox.schemas.Zone` ``StrEnum`` or
    ``None``) is normalised to its underlying string for the TEXT column.

    ``individual_layer_enabled`` is bound here (always ``True`` on this flag-on path) so
    the loader can reject a provenance-false seed; binding it explicitly avoids the
    M11-C3b-exec column-omission bug.
    """
    rows: list[BondAffinityTraceRow] = []
    for bond in relationships:
        zone = bond.last_interaction_zone
        rows.append(
            BondAffinityTraceRow(
                run_id=run_id,
                seed=seed,
                individual_id=individual_id,
                other_agent_id=bond.other_agent_id,
                tick=tick,
                affinity=bond.affinity,
                ichigo_ichie_count=bond.ichigo_ichie_count,
                last_interaction_tick=bond.last_interaction_tick,
                last_interaction_zone=zone.value if zone is not None else None,
                individual_layer_enabled=individual_layer_enabled,
            )
        )
    return rows


__all__ = [
    "BOND_AFFINITY_TRACE_COLUMN_COUNT",
    "TABLE_NAME",
    "BondAffinityTraceRow",
    "bond_affinity_trace_ddl_sql",
    "bootstrap_bond_affinity_trace_schema",
    "build_bond_affinity_trace_rows",
    "column_names",
]
