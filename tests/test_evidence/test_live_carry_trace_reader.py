"""DuckDB-backed ``live_carry.trace_reader`` coverage (sidecar + 3-trace read).

CPU-only synthetic fixtures: one small DuckDB carrying all three frozen III-a traces
plus its ``.capture.json`` sidecar, read back through :func:`read_capture`. Asserts the
matrix identity keys flow from the sidecar, the existing lockstep readers return the
floor + saturation rows, and the per-tick coherence SELECT returns the (nullable)
coherence series the M2 non-inferiority median needs. A capture with no sidecar raises
:class:`LiveCarryReadError` (loud-not-silent); matrix *incompleteness* is the scorer's
job, not raised here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import duckdb
import pytest

from erre_sandbox.contracts.cognition_layers import (
    SubjectiveWorldModel,
    WorldModelEntry,
)
from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.capture_sidecar import (
    SidecarV1,
    sidecar_path_for,
    write_sidecar_atomic,
)
from erre_sandbox.evidence.individuation.trace_ddl import (
    TABLE_NAME as _STATE_TABLE,
)
from erre_sandbox.evidence.individuation.trace_ddl import (
    IndividualStateTraceRow,
    bootstrap_individual_state_trace_schema,
)
from erre_sandbox.evidence.individuation.trace_ddl import (
    column_names as _state_columns,
)
from erre_sandbox.evidence.live_carry.trace_reader import (
    LiveCarryReadError,
    read_capture,
)
from erre_sandbox.evidence.saturation.floor_input_trace_ddl import (
    TABLE_NAME as _FLOOR_TABLE,
)
from erre_sandbox.evidence.saturation.floor_input_trace_ddl import (
    FloorInputTraceRow,
    bootstrap_floor_input_trace_schema,
)
from erre_sandbox.evidence.saturation.floor_input_trace_ddl import (
    column_names as _floor_columns,
)
from erre_sandbox.evidence.saturation.trace_ddl import (
    TABLE_NAME as _SAT_TABLE,
)
from erre_sandbox.evidence.saturation.trace_ddl import (
    SaturationTraceRow,
    bootstrap_saturation_trace_schema,
)
from erre_sandbox.evidence.saturation.trace_ddl import (
    column_names as _sat_columns,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pathlib import Path


def _floor_json(keys: list[tuple[str, str]]) -> str:
    return SubjectiveWorldModel(
        entries=[
            WorldModelEntry(
                axis=axis,  # type: ignore[arg-type]
                key=key,
                value=0.5,
                confidence=0.5,
                cited_memory_ids=("m1",),
                last_updated_tick=0,
            )
            for axis, key in keys
        ]
    ).model_dump_json()


def _insert(
    con: duckdb.DuckDBPyConnection,
    table: str,
    cols: tuple[str, ...],
    row: tuple[object, ...],
) -> None:
    qualified = f"{METRICS_SCHEMA}.{table}"
    cols_sql = ", ".join(cols)
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT INTO {qualified} ({cols_sql}) VALUES ({placeholders})"  # noqa: S608
    con.execute(sql, row)


def _build_capture(tmp_path: Path, *, seed: int, arm: str, replicate_id: int) -> Path:
    duckdb_path = tmp_path / f"{seed}_{arm}_{replicate_id}.duckdb"
    con = duckdb.connect(str(duckdb_path))
    try:
        con.execute(f"CREATE SCHEMA {METRICS_SCHEMA}")
        bootstrap_floor_input_trace_schema(con, METRICS_SCHEMA)
        bootstrap_saturation_trace_schema(con, METRICS_SCHEMA)
        bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
        run_id = f"kant_natural_run{replicate_id}"
        for tick in range(3):
            _insert(
                con,
                _FLOOR_TABLE,
                _floor_columns(),
                FloorInputTraceRow(
                    run_id=run_id,
                    seed=seed,
                    individual_id="kant",
                    tick=tick,
                    floor_swm_json=_floor_json([("self", "k")]),
                    individual_layer_enabled=True,
                ).to_row(),
            )
            _insert(
                con,
                _SAT_TABLE,
                _sat_columns(),
                SaturationTraceRow(
                    run_id=run_id,
                    seed=seed,
                    individual_id="kant",
                    axis="self",
                    key="k",
                    tick=tick,
                    base_floor_value=0.5,
                    modulated_value=0.6,
                    floor_fingerprint_hash=f"fp{tick}",
                    individual_layer_enabled=True,
                ).to_row(),
            )
            _insert(
                con,
                _STATE_TABLE,
                _state_columns(),
                IndividualStateTraceRow(
                    run_id=run_id,
                    individual_id="kant",
                    tick=tick,
                    development_stage=None,
                    coherence_score=None if tick == 0 else 0.7,
                    belief_classes_json=None,
                    arc_segment_count=0,
                    world_model_keys_json=None,
                    world_model_evidence_json=None,
                ).to_row(),
            )
    finally:
        con.close()
    write_sidecar_atomic(
        sidecar_path_for(duckdb_path),
        SidecarV1(
            status="complete",
            stop_reason="complete",
            focal_target=1,
            focal_observed=1,
            total_rows=3,
            wall_timeout_min=1.0,
            drain_completed=True,
            runtime_drain_timeout=False,
            git_sha="abc1234",
            captured_at="2026-06-16T00:00:00Z",
            persona="kant",
            condition="natural",
            run_idx=replicate_id,
            duckdb_path=str(duckdb_path),
            seed=seed,
            seed_salt="m9-eval-v1",
            stm_carry_arm=arm,  # type: ignore[arg-type]
            replicate_id=replicate_id,
        ),
    )
    return duckdb_path


def test_read_capture_returns_identity_and_traces(tmp_path: Path) -> None:
    path = _build_capture(tmp_path, seed=42, arm="on", replicate_id=1)
    capture = read_capture(path)
    assert capture.seed == 42
    assert capture.arm == "on"
    assert capture.replicate_id == 1
    assert len(capture.floor_rows) == 3
    assert len(capture.saturation_rows) == 3
    # coherence series is per-tick (tick 0 → NULL, ticks 1/2 → 0.7).
    assert len(capture.coherence_rows) == 3
    scores = sorted(
        (r.coherence_score for r in capture.coherence_rows),
        key=lambda v: (v is None, v),
    )
    assert scores == [0.7, 0.7, None]


def test_read_capture_missing_sidecar_raises(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "no_sidecar.duckdb"
    con = duckdb.connect(str(duckdb_path))
    con.close()
    with pytest.raises(LiveCarryReadError):
        read_capture(duckdb_path)
