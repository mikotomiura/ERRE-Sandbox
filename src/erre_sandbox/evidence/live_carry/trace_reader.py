"""Read one III-a paired-arm capture into the cross-arm scorer's input shape.

Each live §5.3 capture is a ``.duckdb`` whose sibling ``.capture.json`` sidecar
carries the matrix-identity keys (``seed`` / ``stm_carry_arm`` / ``replicate_id``,
freeze ADR §0/§3) and whose ``metrics`` schema holds the three frozen III-a
traces. This module opens the capture **read-only** and pulls those traces via the
**existing** lockstep readers — :func:`read_floor_input_trace_rows` (M1 distal floor
substrate) and :func:`read_saturation_trace_rows` (M0 engagement + M2 cap) — plus a
small per-tick coherence SELECT for the M2 non-inferiority series (the existing
``load_individual_state_windows`` collapses to the *final* tick only, so it cannot
supply the per-tick coherence median the freeze ADR §5 wants).

No scoring lives here: it only assembles raw rows + the sidecar provenance into a
:class:`LiveCarryCapture`; :mod:`.scorer` owns the entire decision. The qualified
table name is composed from ``METRICS_SCHEMA`` (never a schema-dot literal — CI
eval-egress grep gate); the per-tick coherence SELECT column list is the
individual-state trace's own ``column_names`` so it stays in lockstep with the DDL.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

import duckdb

from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.capture_sidecar import read_sidecar, sidecar_path_for
from erre_sandbox.evidence.individuation.trace_ddl import (
    TABLE_NAME as _INDIVIDUAL_STATE_TABLE,
)
from erre_sandbox.evidence.saturation.floor_input_trace_ddl import (
    read_floor_input_trace_rows,
)
from erre_sandbox.evidence.saturation.loader import read_saturation_trace_rows

if TYPE_CHECKING:
    from erre_sandbox.evidence.saturation.floor_input_trace_ddl import (
        FloorInputTraceRow,
    )
    from erre_sandbox.evidence.saturation.trace_ddl import SaturationTraceRow

_COHERENCE_COLUMNS: Final[tuple[str, ...]] = (
    "individual_id",
    "tick",
    "coherence_score",
)
"""Per-tick coherence projection (subset of the individual-state trace columns)."""


class LiveCarryReadError(RuntimeError):
    """A capture could not be read (missing sidecar, unreadable DuckDB).

    A genuinely unreadable input is loud-not-silent; matrix *incompleteness*
    (missing / duplicate / role-swapped key) is **not** raised here — that is a
    scorer verdict (``INVALID_MEASUREMENT``), so the sidecar's matrix keys are
    passed straight through (possibly ``None``) for the scorer to adjudicate.
    """


@dataclass(frozen=True, slots=True)
class CoherenceRow:
    """One per-tick narrative-coherence observation (``None`` when no arc)."""

    individual_id: str
    tick: int
    coherence_score: float | None


@dataclass(frozen=True, slots=True)
class LiveCarryCapture:
    """One capture's matrix identity + the three raw traces the scorer reads."""

    path: str
    seed: int | None
    arm: str | None
    replicate_id: int | None
    floor_rows: tuple[FloorInputTraceRow, ...]
    saturation_rows: tuple[SaturationTraceRow, ...]
    coherence_rows: tuple[CoherenceRow, ...]


def _read_coherence_rows(
    con: duckdb.DuckDBPyConnection, *, schema: str
) -> tuple[CoherenceRow, ...]:
    """Read per-tick ``coherence_score`` from the individual-state trace.

    Returns an empty tuple when the table is absent (a flag-off run never creates
    it). The qualified name is composed from *schema* + the trace's own table
    constant (no schema-dot literal); the column list is a fixed subset of the
    individual-state DDL columns. ``coherence_score`` is nullable (NULL on a tick
    that synthesised no narrative arc), so the M2 median is taken over non-NULL
    observations downstream.
    """
    present = con.execute(
        "SELECT 1 FROM information_schema.tables"
        " WHERE table_schema = ? AND table_name = ?",
        (schema, _INDIVIDUAL_STATE_TABLE),
    ).fetchone()
    if present is None:
        return ()
    columns_sql = ", ".join(f'"{c}"' for c in _COHERENCE_COLUMNS)
    select_sql = f"SELECT {columns_sql} FROM {schema}.{_INDIVIDUAL_STATE_TABLE}"  # noqa: S608 — static identifiers only
    result = con.execute(select_sql).fetchall()
    return tuple(
        CoherenceRow(
            individual_id=str(row[0]),
            tick=int(row[1]),
            coherence_score=None if row[2] is None else float(row[2]),
        )
        for row in result
    )


def read_capture(
    duckdb_path: Path | str, *, schema: str = METRICS_SCHEMA
) -> LiveCarryCapture:
    """Open one capture read-only and assemble its sidecar identity + raw traces.

    The sidecar's matrix keys (``seed`` / ``stm_carry_arm`` / ``replicate_id``) are
    passed through verbatim (possibly ``None`` for a pre-live-§5.3 or non-arm
    capture) — the scorer routes any incomplete matrix to ``INVALID_MEASUREMENT``.
    Raises :class:`LiveCarryReadError` only when the capture itself cannot be read.
    """
    path = Path(duckdb_path)
    try:
        sidecar = read_sidecar(sidecar_path_for(path))
    except (OSError, ValueError) as exc:
        msg = f"could not read sidecar for capture {path}: {exc}"
        raise LiveCarryReadError(msg) from exc
    try:
        con = duckdb.connect(str(path), read_only=True)
    except duckdb.Error as exc:
        msg = f"could not open capture DuckDB {path}: {exc}"
        raise LiveCarryReadError(msg) from exc
    try:
        floor_rows = tuple(read_floor_input_trace_rows(con, schema=schema))
        saturation_rows = tuple(read_saturation_trace_rows(con, schema=schema))
        coherence_rows = _read_coherence_rows(con, schema=schema)
    except duckdb.Error as exc:
        msg = f"could not read traces from capture {path}: {exc}"
        raise LiveCarryReadError(msg) from exc
    finally:
        con.close()
    return LiveCarryCapture(
        path=str(path),
        seed=sidecar.seed,
        arm=sidecar.stm_carry_arm,
        replicate_id=sidecar.replicate_id,
        floor_rows=floor_rows,
        saturation_rows=saturation_rows,
        coherence_rows=coherence_rows,
    )


__all__ = [
    "CoherenceRow",
    "LiveCarryCapture",
    "LiveCarryReadError",
    "read_capture",
]
