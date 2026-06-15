"""Read + fail-fast-validate a replay **source** capture into canonical streams (U5).

The deterministic replay (versioned-measurement ADR §5.2) re-applies one captured
``floor`` + ``hint`` stream under both carry arms. This module is the **evidence-layer**
front door: it reads a source DuckDB's ``swm_floor_input_trace`` (PR-1) +
``swm_hint_engagement_trace`` tables and assembles a canonical, fully-validated
stream of ``contracts`` types — it does **not** thread the reconcile kernel (that is the
``cognition`` layer's job, U5 HIGH-4 / repository-structure §4: ``evidence`` may not
import ``cognition``). The composition-root CLI hands the result to
``cognition.world_model_replay`` and converts the per-arm output back into trace rows.

Why fail-fast here (Codex HIGH-3): the frozen saturation/hint readers have **no**
``ORDER BY`` and the replay's determinism + fidelity both depend on a single, total,
duplicate-free, census-consistent input. Silently treating a missing hint row as a no-op
or a duplicate floor row as last-write-wins would break both. So this assembler rejects:

* a duplicate ``(run_id, seed, individual_id, tick)`` natural key in either table;
* a non-exactly-one ``run_id`` / ``seed`` (within or across the two tables);
* any ``individual_layer_enabled = False`` row (a provenance-false source);
* a ``(individual_id, tick)`` **census mismatch** between floor and hint (the cycle
  co-emits both every flag-on tick, so a mismatch is a corrupt/partial capture);

and returns the stream **canonically sorted** by ``(individual_id, tick)`` so the
downstream threading + INSERT order is deterministic regardless of DuckDB row order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

from pydantic import ValidationError

from erre_sandbox.contracts.cognition_layers import (
    SubjectiveWorldModel,
    WorldModelHintDisposition,
)
from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.hint_engagement.loader import read_hint_engagement_trace_rows
from erre_sandbox.evidence.hint_engagement.trace_ddl import (
    TABLE_NAME as HINT_TABLE_NAME,
)
from erre_sandbox.evidence.saturation.floor_input_trace_ddl import (
    TABLE_NAME as FLOOR_TABLE_NAME,
)
from erre_sandbox.evidence.saturation.floor_input_trace_ddl import (
    read_floor_input_trace_rows,
)

if TYPE_CHECKING:
    import duckdb

    from erre_sandbox.evidence.hint_engagement.trace_ddl import HintEngagementTraceRow
    from erre_sandbox.evidence.saturation.floor_input_trace_ddl import (
        FloorInputTraceRow,
    )


class ReplaySourceError(RuntimeError):
    """A replay source capture is structurally unusable (dup / census / provenance)."""


@dataclass(frozen=True, slots=True)
class ReplayTickInput:
    """One ``(individual_id, tick)`` of the source stream: floor + source disposition.

    ``floor`` is the **reconcile input** (the full ``SubjectiveWorldModel`` PR-1
    persisted). ``source_disposition`` is what the source run's authority did to the
    hint this tick — the replay re-evaluates only its carry-dependent part per arm
    (``adopted`` ↔ ``rejected_no_effect``), the rest is carry-independent.
    """

    individual_id: str
    tick: int
    floor: SubjectiveWorldModel
    source_disposition: WorldModelHintDisposition


@dataclass(frozen=True, slots=True)
class ReplaySource:
    """A validated, canonically-ordered source stream for one ``(run_id, seed)``."""

    run_id: str
    seed: int
    ticks: tuple[ReplayTickInput, ...]


_Scalar = TypeVar("_Scalar", str, int)


def _one(values: set[_Scalar], *, what: str) -> _Scalar:
    if len(values) != 1:
        raise ReplaySourceError(
            f"{what} is not exactly-one in the source capture: "
            f"found {sorted(map(str, values))}"
        )
    return next(iter(values))


def _reject_floor_dups(rows: list[FloorInputTraceRow]) -> None:
    seen: set[tuple[str, int, str, int]] = set()
    for r in rows:
        key = (r.run_id, r.seed, r.individual_id, r.tick)
        if key in seen:
            raise ReplaySourceError(f"duplicate floor natural key {key}")
        seen.add(key)


def _reject_hint_dups(rows: list[HintEngagementTraceRow]) -> None:
    seen: set[tuple[str, int, str, int]] = set()
    for r in rows:
        key = (r.run_id, r.seed, r.individual_id, r.tick)
        if key in seen:
            raise ReplaySourceError(f"duplicate hint natural key {key}")
        seen.add(key)


def _disposition_from_row(row: HintEngagementTraceRow) -> WorldModelHintDisposition:
    """Rebuild the carried ``WorldModelHintDisposition`` from a persisted hint row.

    The trace DDL's CHECKs already pin the field invariants (target triple NULL iff
    ``not_emitted`` etc.); pydantic re-validates the Literal vocabularies here, so a
    schema-foreign value surfaces as a structural :class:`ReplaySourceError` rather than
    a silent mis-replay.
    """
    try:
        return WorldModelHintDisposition.model_validate(
            {
                "llm_status": row.llm_status,
                "emitted": row.emitted,
                "disposition": row.disposition,
                "target_axis": row.target_axis,
                "target_key": row.target_key,
                "direction": row.direction,
                "adopted_signed_step": row.adopted_signed_step,
                "exposed_entry_count": row.exposed_entry_count,
            }
        )
    except ValidationError as exc:
        raise ReplaySourceError(
            f"hint row at (ind={row.individual_id!r}, tick={row.tick}) is not a valid "
            f"WorldModelHintDisposition: {exc}"
        ) from exc


def _floor_from_row(row: FloorInputTraceRow) -> SubjectiveWorldModel:
    try:
        return SubjectiveWorldModel.model_validate_json(row.floor_swm_json)
    except ValidationError as exc:
        raise ReplaySourceError(
            f"floor row at (ind={row.individual_id!r}, tick={row.tick}) has invalid "
            f"floor_swm_json: {exc}"
        ) from exc


def assemble_replay_source(
    con: duckdb.DuckDBPyConnection,
    *,
    schema: str = METRICS_SCHEMA,
    floor_table: str = FLOOR_TABLE_NAME,
    hint_table: str = HINT_TABLE_NAME,
) -> ReplaySource:
    """Read + fail-fast-validate one source capture into a canonical replay stream.

    *con* is an open (read-only is fine) connection to the source DuckDB, which holds
    **both** the floor-input and hint-engagement tables (an individual-layer-on natural
    capture). Raises :class:`ReplaySourceError` on any structural defect (Codex HIGH-3);
    a valid return is sorted by ``(individual_id, tick)``.
    """
    floor_rows = read_floor_input_trace_rows(con, schema=schema, table=floor_table)
    hint_rows = read_hint_engagement_trace_rows(con, schema=schema, table=hint_table)
    if not floor_rows:
        raise ReplaySourceError(
            "source capture has no floor-input rows (run_id/seed undecidable; "
            "was it captured with --individual-layer on after U5 PR-1?)"
        )
    if not hint_rows:
        raise ReplaySourceError("source capture has no hint-engagement rows")

    _reject_floor_dups(floor_rows)
    _reject_hint_dups(hint_rows)

    if any(not r.individual_layer_enabled for r in floor_rows) or any(
        not r.individual_layer_enabled for r in hint_rows
    ):
        raise ReplaySourceError(
            "source capture has individual_layer_enabled=False rows (provenance-false; "
            "not a real flag-on capture)"
        )

    run_id = str(
        _one(
            {r.run_id for r in floor_rows} | {r.run_id for r in hint_rows},
            what="run_id",
        )
    )
    seed = int(
        _one({r.seed for r in floor_rows} | {r.seed for r in hint_rows}, what="seed")
    )

    floor_by: dict[tuple[str, int], FloorInputTraceRow] = {
        (r.individual_id, r.tick): r for r in floor_rows
    }
    hint_by: dict[tuple[str, int], HintEngagementTraceRow] = {
        (r.individual_id, r.tick): r for r in hint_rows
    }
    floor_keys = set(floor_by)
    hint_keys = set(hint_by)
    if floor_keys != hint_keys:
        only_floor = sorted(floor_keys - hint_keys)
        only_hint = sorted(hint_keys - floor_keys)
        raise ReplaySourceError(
            "floor/hint (individual_id, tick) census mismatch "
            f"(floor-only={only_floor[:5]}, hint-only={only_hint[:5]}); the cycle "
            "co-emits both every flag-on tick, so a mismatch means a partial/corrupt "
            "capture"
        )

    ticks = tuple(
        ReplayTickInput(
            individual_id=ind,
            tick=tick,
            floor=_floor_from_row(floor_by[(ind, tick)]),
            source_disposition=_disposition_from_row(hint_by[(ind, tick)]),
        )
        for ind, tick in sorted(floor_keys)
    )
    return ReplaySource(run_id=run_id, seed=seed, ticks=ticks)


__all__ = [
    "ReplaySource",
    "ReplaySourceError",
    "ReplayTickInput",
    "assemble_replay_source",
]
