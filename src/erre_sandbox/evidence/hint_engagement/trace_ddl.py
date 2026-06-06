"""DDL + row builder for ``metrics.swm_hint_engagement_trace`` (instrument ADR §4).

A per-``(agent, tick)`` trace of the world-model update hint's disposition: one row
records whether a hint was emitted this tick, how the authority disposed of it
(adopted / one of four reject reasons / not emitted), the measured signed nudge step,
and the LLM status (so a fallback tick is not silently dropped from the emission-rate
denominator, Codex HIGH-1). The loader recomputes emission / adoption / per-gate /
direction-consistency rates from these raw rows (trace stores raw, loader recomputes).

Placement mirrors ``evidence.saturation.trace_ddl`` — a **new-module shadow**: it
shares no column order, no measure, and no schema with the frozen
``swm_modulation_saturation_trace`` / ``individual_state_trace`` tables, so those
frozen gates stay untouched. The module owns its column order as the single source of
truth and never embeds a ``metrics``-dot schema literal — the qualified name is
composed by the caller from ``METRICS_SCHEMA`` (CI eval-egress grep gate). The table
is created **only when the individual layer is enabled**
(``bootstrap_hint_engagement_trace_schema`` is never called from ``bootstrap_schema``),
so a flag-off run leaves the DuckDB byte-identical.

Layering: this module imports only ``contracts`` (the carrier read-model) + stdlib;
it never imports ``cognition`` (the classifier / carrier builder live there). The
``world`` sink hands the carrier straight through, so ``world`` never imports
``evidence`` either — only the ``cli`` composition root does.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    import duckdb

    from erre_sandbox.contracts.cognition_layers import WorldModelHintDisposition

TABLE_NAME: Final[str] = "swm_hint_engagement_trace"
"""Bare table name inside the metrics schema (never qualified here)."""

NOT_EMITTED: Final[str] = "not_emitted"
"""The disposition value whose CHECK invariant pins all three target columns NULL."""

ADOPTED: Final[str] = "adopted"
"""The only disposition under which ``adopted_signed_step`` may be non-zero."""

# Column order is the single source of truth: ``HintEngagementTraceRow.to_row`` and
# ``column_names`` both derive from this, and the orchestrator's INSERT binds in this
# order. ``seed`` is UBIGINT because the per-run seed is ``golden_baseline.derive_seed``
# — an unsigned 64-bit blake2b digest that overflows a signed BIGINT (saturation trace
# DA-IMPL-2). ``target_axis`` / ``target_key`` / ``direction`` are the only nullable
# columns: they are NULL iff the hint was not emitted (the CHECK below pins this).
_HINT_ENGAGEMENT_TRACE_COLUMNS: Final[tuple[tuple[str, str], ...]] = (
    ("run_id", "TEXT NOT NULL"),
    ("seed", "UBIGINT NOT NULL"),
    ("individual_id", "TEXT NOT NULL"),
    ("tick", "BIGINT NOT NULL"),
    ("llm_status", "TEXT NOT NULL"),
    ("exposed_entry_count", "INTEGER NOT NULL"),
    ("emitted", "BOOLEAN NOT NULL"),
    ("disposition", "TEXT NOT NULL"),
    ("target_axis", "TEXT"),
    ("target_key", "TEXT"),
    ("direction", "TEXT"),
    ("adopted_signed_step", "DOUBLE NOT NULL"),
    ("individual_layer_enabled", "BOOLEAN NOT NULL"),
)

HINT_ENGAGEMENT_TRACE_COLUMN_COUNT: Final[int] = len(_HINT_ENGAGEMENT_TRACE_COLUMNS)


def column_names() -> tuple[str, ...]:
    """Ordered column names — the order ``HintEngagementTraceRow.to_row`` emits."""
    return tuple(name for name, _ in _HINT_ENGAGEMENT_TRACE_COLUMNS)


def hint_engagement_trace_ddl_sql(schema: str, table: str = TABLE_NAME) -> str:
    """Return ``CREATE TABLE IF NOT EXISTS {schema}.{table}`` DDL (instrument ADR §4).

    *schema* is supplied by the caller (the eval orchestrator passes
    ``METRICS_SCHEMA``); this module never embeds a schema-dot literal. The DDL is
    idempotent (``IF NOT EXISTS``) so the flag-on conditional bootstrap is safe to call
    repeatedly. The CHECKs pin the disposition/column invariants (補強 §5):

    * ``tick >= 0``;
    * ``not_emitted`` iff all three target columns are NULL (and, contrapositively,
      every other disposition has a non-NULL axis/key/direction);
    * ``emitted`` iff the disposition is not ``not_emitted``;
    * a non-zero ``adopted_signed_step`` implies ``disposition='adopted'``.
    """
    cols = ",\n  ".join(
        f"{name} {sqltype}" for name, sqltype in _HINT_ENGAGEMENT_TRACE_COLUMNS
    )
    targets_all_null = (
        "target_axis IS NULL AND target_key IS NULL AND direction IS NULL"
    )
    return (
        f"CREATE TABLE IF NOT EXISTS {schema}.{table} (\n"
        f"  {cols},\n"
        f"  CHECK (tick >= 0),\n"
        f"  CHECK ((disposition = '{NOT_EMITTED}') = ({targets_all_null})),\n"
        f"  CHECK (emitted = (disposition <> '{NOT_EMITTED}')),\n"
        f"  CHECK (adopted_signed_step = 0.0 OR disposition = '{ADOPTED}')\n"
        f")"
    )


def bootstrap_hint_engagement_trace_schema(
    con: duckdb.DuckDBPyConnection, schema: str, table: str = TABLE_NAME
) -> None:
    """Create the trace table on *con* (flag-on conditional bootstrap).

    Called **only** from the eval orchestrator's individual-layer-enabled branch —
    never from ``bootstrap_schema`` — so a flag-off run never issues this DDL and the
    DuckDB stays byte-identical.
    """
    con.execute(hint_engagement_trace_ddl_sql(schema, table))


@dataclass(frozen=True, slots=True)
class HintEngagementTraceRow:
    """One ``(run_id, seed, individual_id, tick)`` hint-engagement row.

    Immutable; ``to_row`` emits values in ``_HINT_ENGAGEMENT_TRACE_COLUMNS`` order so
    the INSERT bind stays in lockstep with the DDL.
    """

    run_id: str
    seed: int
    individual_id: str
    tick: int
    llm_status: str
    exposed_entry_count: int
    emitted: bool
    disposition: str
    target_axis: str | None
    target_key: str | None
    direction: str | None
    adopted_signed_step: float
    individual_layer_enabled: bool

    def to_row(self) -> tuple[object, ...]:
        """Positional tuple in DDL column order (INSERT bind order)."""
        return (
            self.run_id,
            self.seed,
            self.individual_id,
            self.tick,
            self.llm_status,
            self.exposed_entry_count,
            self.emitted,
            self.disposition,
            self.target_axis,
            self.target_key,
            self.direction,
            self.adopted_signed_step,
            self.individual_layer_enabled,
        )


def build_hint_engagement_trace_row(
    disposition: WorldModelHintDisposition,
    *,
    run_id: str,
    seed: int,
    individual_id: str,
    tick: int,
    individual_layer_enabled: bool,
) -> HintEngagementTraceRow:
    """Project a carrier + run identity into one trace row (pure).

    *disposition* is the ``WorldModelHintDisposition`` carried off ``CycleResult``;
    ``world`` passes it straight through so it never imports ``evidence``. The run
    identity (``run_id`` / ``seed`` / ``individual_id`` / ``tick``) and the provenance
    flag are bound here by the ``cli`` composition root. ``individual_layer_enabled``
    is bound explicitly (always ``True`` on this flag-on path) so the loader can reject
    a provenance-false seed — avoiding the M11-C3b-exec column-omission bug.
    """
    return HintEngagementTraceRow(
        run_id=run_id,
        seed=seed,
        individual_id=individual_id,
        tick=tick,
        llm_status=disposition.llm_status,
        exposed_entry_count=disposition.exposed_entry_count,
        emitted=disposition.emitted,
        disposition=disposition.disposition,
        target_axis=disposition.target_axis,
        target_key=disposition.target_key,
        direction=disposition.direction,
        adopted_signed_step=disposition.adopted_signed_step,
        individual_layer_enabled=individual_layer_enabled,
    )


__all__ = [
    "ADOPTED",
    "HINT_ENGAGEMENT_TRACE_COLUMN_COUNT",
    "NOT_EMITTED",
    "TABLE_NAME",
    "HintEngagementTraceRow",
    "bootstrap_hint_engagement_trace_schema",
    "build_hint_engagement_trace_row",
    "column_names",
    "hint_engagement_trace_ddl_sql",
]
