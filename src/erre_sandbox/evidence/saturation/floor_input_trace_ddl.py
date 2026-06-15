"""DDL + row builder for ``metrics.swm_floor_input_trace`` (U5 replay infra).

A per-``(agent, tick)`` longitudinal trace of the **reconcile input floor** — the
pre-modulation evidence floor ``synthesize_world_model`` produced this tick — stored as
the **full** :class:`~erre_sandbox.contracts.cognition_layers.SubjectiveWorldModel` so a
deterministic replay can re-feed it into the unchanged ``reconcile_world_model`` kernel.

Why a *new* table rather than re-using the saturation trace (U5 design DA-U5-1): the
frozen ``swm_modulation_saturation_trace`` (案 B, unchanged) is **lossy** — it stores
only ``base_floor_value`` + ``floor_fingerprint_hash`` per entry, dropping
``confidence`` / ``cited_memory_ids`` / ``last_updated_tick``. The carry kernel
recomputes the floor fingerprint from those exact fields, so the saturation trace alone
cannot faithfully drive a replay. This shadow table persists the full floor (the
``base_floor`` already carried on ``CycleResult.world_model_saturation`` — no cognition
change), so "recorded == reconcile input" holds by construction (the replay fidelity
property, DA-U5-2 / Codex MED-3).

Grain is **per-(individual, tick)**, one row whose ``floor_swm_json`` is the canonical
JSON of the whole floor model (DA-U5-2): unlike the per-entry saturation grain, an
**empty** floor (no promoted beliefs yet) still emits a row, so the replay can reproduce
``reconcile_world_model``'s vanished-key drop on an empty-floor tick. (The frozen scorer
never sees these rows — they are state-threading substrate for the replay driver, which
re-emits the *lossy* saturation trace from them; Codex MED-4.)

Placement mirrors ``evidence.saturation.trace_ddl`` — a **new-module shadow**: it shares
no column order, no measure, and no schema with the frozen
``swm_modulation_saturation_trace`` / ``swm_hint_engagement_trace`` /
``individual_state_trace`` tables, so those frozen gates stay untouched. The module owns
its column order as the single source of truth and never embeds a ``metrics``-dot schema
literal — the qualified name is composed by the caller from ``METRICS_SCHEMA`` (CI
eval-egress grep gate). The table is created **only when the individual layer is
enabled** (``bootstrap_floor_input_trace_schema`` is never called from
``bootstrap_schema``), so a flag-off run leaves the DuckDB byte-identical.

The table lives in the ``metrics`` schema (eval-only): it carries individual-layer
numeric outputs, never the raw training-egress utterance stream.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    import duckdb

    from erre_sandbox.contracts.cognition_layers import WorldModelSnapshot

TABLE_NAME: Final[str] = "swm_floor_input_trace"
"""Bare table name inside the metrics schema (never qualified here)."""

# Column order is the single source of truth: ``FloorInputTraceRow.to_row`` and
# ``column_names`` both derive from this, and the orchestrator's INSERT binds in this
# order. ``seed`` is UBIGINT because the per-run seed is ``golden_baseline.derive_seed``
# — an unsigned 64-bit blake2b digest that overflows a signed BIGINT (saturation trace
# DA-IMPL-2). ``floor_swm_json`` is the canonical JSON of the full floor
# ``SubjectiveWorldModel`` (a possibly-empty entry list), so even an empty-floor tick
# emits exactly one row. Everything is NOT NULL.
_FLOOR_INPUT_TRACE_COLUMNS: Final[tuple[tuple[str, str], ...]] = (
    ("run_id", "TEXT NOT NULL"),
    ("seed", "UBIGINT NOT NULL"),
    ("individual_id", "TEXT NOT NULL"),
    ("tick", "BIGINT NOT NULL"),
    ("floor_swm_json", "TEXT NOT NULL"),
    ("individual_layer_enabled", "BOOLEAN NOT NULL"),
)

FLOOR_INPUT_TRACE_COLUMN_COUNT: Final[int] = len(_FLOOR_INPUT_TRACE_COLUMNS)


def column_names() -> tuple[str, ...]:
    """Ordered column names — the order ``FloorInputTraceRow.to_row`` emits."""
    return tuple(name for name, _ in _FLOOR_INPUT_TRACE_COLUMNS)


def floor_input_trace_ddl_sql(schema: str, table: str = TABLE_NAME) -> str:
    """Return ``CREATE TABLE IF NOT EXISTS {schema}.{table}`` DDL.

    *schema* is supplied by the caller (the eval orchestrator passes
    ``METRICS_SCHEMA``); this module never embeds a schema-dot literal. The DDL is
    idempotent (``IF NOT EXISTS``) so the flag-on conditional bootstrap is safe to call
    repeatedly. ``tick >= 0`` is the only structural CHECK.
    """
    cols = ",\n  ".join(
        f"{name} {sqltype}" for name, sqltype in _FLOOR_INPUT_TRACE_COLUMNS
    )
    return (
        f"CREATE TABLE IF NOT EXISTS {schema}.{table} (\n"
        f"  {cols},\n"
        f"  CHECK (tick >= 0)\n"
        f")"
    )


def bootstrap_floor_input_trace_schema(
    con: duckdb.DuckDBPyConnection, schema: str, table: str = TABLE_NAME
) -> None:
    """Create the trace table on *con* (flag-on conditional bootstrap).

    Called **only** from the eval orchestrator's individual-layer-enabled branch —
    never from ``bootstrap_schema`` — so a flag-off run never issues this DDL and the
    DuckDB stays byte-identical.
    """
    con.execute(floor_input_trace_ddl_sql(schema, table))


@dataclass(frozen=True, slots=True)
class FloorInputTraceRow:
    """One ``(run_id, seed, individual_id, tick)`` reconcile-input floor row.

    Immutable; ``to_row`` emits values in ``_FLOOR_INPUT_TRACE_COLUMNS`` order so the
    INSERT bind stays in lockstep with the DDL. ``floor_swm_json`` is the canonical
    ``SubjectiveWorldModel`` JSON — see :func:`build_floor_input_trace_row`.
    """

    run_id: str
    seed: int
    individual_id: str
    tick: int
    floor_swm_json: str
    individual_layer_enabled: bool

    def to_row(self) -> tuple[object, ...]:
        """Positional tuple in DDL column order (INSERT bind order)."""
        return (
            self.run_id,
            self.seed,
            self.individual_id,
            self.tick,
            self.floor_swm_json,
            self.individual_layer_enabled,
        )


def build_floor_input_trace_row(
    snapshot: WorldModelSnapshot,
    *,
    run_id: str,
    seed: int,
    individual_id: str,
    tick: int,
    individual_layer_enabled: bool,
) -> FloorInputTraceRow:
    """Project a post-reconcile snapshot's **floor** into one trace row (pure).

    *snapshot* is the **post-reconcile, pre-nudge** ``WorldModelSnapshot`` captured at
    ``cycle.py`` reconcile and carried out on ``CycleResult.world_model_saturation`` —
    the same carrier the saturation sink reads, so ``world`` imports neither
    ``evidence`` nor ``cognition`` (hands the carrier through). ``snapshot.base_floor``
    equals the ``synthesize_world_model`` output (``reconcile_world_model`` returns
    ``base_floor=new_floor``), i.e. the **reconcile input**; it is serialised with
    :meth:`pydantic.BaseModel.model_dump_json` so field order, ``cited_memory_ids`` list
    order and float repr are byte-stable (the replay determinism precondition,
    DA-U5-2 / Codex HIGH-3). One row even for an empty floor (``entries == []``).

    ``individual_layer_enabled`` is bound here (always ``True`` on this flag-on path) so
    a reader can reject a provenance-false seed; binding it explicitly avoids the
    M11-C3b-exec column-omission bug.
    """
    return FloorInputTraceRow(
        run_id=run_id,
        seed=seed,
        individual_id=individual_id,
        tick=tick,
        floor_swm_json=snapshot.base_floor.model_dump_json(),
        individual_layer_enabled=individual_layer_enabled,
    )


def read_floor_input_trace_rows(
    con: duckdb.DuckDBPyConnection,
    *,
    schema: str,
    table: str = TABLE_NAME,
) -> list[FloorInputTraceRow]:
    """Read all floor-input trace rows from *con* into typed rows (column-lockstep).

    Plain ``SELECT`` over the metrics trace (no ``raw_dialog`` egress guard). The SELECT
    column list is :func:`column_names` so it stays in lockstep with the DDL, and the
    qualified table name is composed from *schema* so no ``metrics``-dot literal appears
    here. The SELECT has **no** ``ORDER BY`` (mirroring the frozen saturation/hint
    readers); the replay source assembler is responsible for the canonical sort before
    threading (Codex HIGH-3).
    """
    cols = column_names()
    columns_sql = ", ".join(f'"{c}"' for c in cols)
    select_sql = f"SELECT {columns_sql} FROM {schema}.{table}"  # noqa: S608 — static identifiers only
    result = con.execute(select_sql).fetchall()
    return [
        FloorInputTraceRow(
            run_id=str(row[0]),
            seed=int(row[1]),
            individual_id=str(row[2]),
            tick=int(row[3]),
            floor_swm_json=str(row[4]),
            individual_layer_enabled=bool(row[5]),
        )
        for row in result
    ]


__all__ = [
    "FLOOR_INPUT_TRACE_COLUMN_COUNT",
    "TABLE_NAME",
    "FloorInputTraceRow",
    "bootstrap_floor_input_trace_schema",
    "build_floor_input_trace_row",
    "column_names",
    "floor_input_trace_ddl_sql",
    "read_floor_input_trace_rows",
]
