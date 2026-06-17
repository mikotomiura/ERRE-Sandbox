"""DuckDB-backed ``relational.trace_reader`` coverage (sidecar + 2-trace read).

CPU-only synthetic fixtures: one small DuckDB carrying the bond-affinity +
saturation traces plus its ``.capture.json`` sidecar, read back through
:func:`read_bond_capture`. Asserts the matrix-identity keys flow from the sidecar
(with ``stm_carry_arm`` normalised "on"/"off" -> "ON"/"OFF"), the existing lockstep
readers return both row sets, and a capture with no sidecar raises
:class:`BondAffinityReadError` (loud-not-silent); matrix *incompleteness* is the
assembler's job, not raised here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import duckdb
import pytest

from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.capture_sidecar import (
    SidecarV1,
    sidecar_path_for,
    write_sidecar_atomic,
)
from erre_sandbox.evidence.relational.bond_affinity_trace_ddl import (
    TABLE_NAME as _BOND_TABLE,
)
from erre_sandbox.evidence.relational.bond_affinity_trace_ddl import (
    bootstrap_bond_affinity_trace_schema,
    build_bond_affinity_trace_rows,
)
from erre_sandbox.evidence.relational.bond_affinity_trace_ddl import (
    column_names as _bond_columns,
)
from erre_sandbox.evidence.relational.trace_reader import (
    BondAffinityReadError,
    read_bond_capture,
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
from erre_sandbox.schemas import RelationshipBond, Zone

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pathlib import Path


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


def _build_capture(
    tmp_path: Path, *, seed: int, arm: str, replicate_id: int, n_bonds: int = 3
) -> Path:
    """Write one capture (bond + saturation traces) + its sidecar; return the path."""
    duckdb_path = tmp_path / f"{seed}_{arm}_{replicate_id}.duckdb"
    run_id = f"kant_natural_{seed}_{arm}_{replicate_id}"
    con = duckdb.connect(str(duckdb_path))
    try:
        con.execute(f"CREATE SCHEMA {METRICS_SCHEMA}")
        bootstrap_bond_affinity_trace_schema(con, METRICS_SCHEMA)
        bootstrap_saturation_trace_schema(con, METRICS_SCHEMA)
        bonds = [
            RelationshipBond(
                other_agent_id=f"o{i}",
                affinity=0.44,
                ichigo_ichie_count=6,
                last_interaction_tick=10,
                last_interaction_zone=Zone.STUDY,
            )
            for i in range(n_bonds)
        ]
        for row in build_bond_affinity_trace_rows(
            bonds,
            run_id=run_id,
            seed=seed,
            individual_id="kant",
            tick=10,
            individual_layer_enabled=True,
        ):
            _insert(con, _BOND_TABLE, _bond_columns(), row.to_row())
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
                tick=10,
                base_floor_value=0.5,
                modulated_value=0.65,
                floor_fingerprint_hash="h",
                individual_layer_enabled=True,
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
            total_rows=n_bonds + 1,
            wall_timeout_min=1.0,
            drain_completed=True,
            runtime_drain_timeout=False,
            git_sha="abc1234",
            captured_at="2026-06-18T00:00:00Z",
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
    path = _build_capture(tmp_path, seed=42, arm="on", replicate_id=1, n_bonds=4)
    capture = read_bond_capture(path)
    assert capture.seed == 42
    # arm is normalised from the sidecar's lower-case "on" to the scorer's "ON".
    assert capture.arm == "ON"
    assert capture.replicate_id == 1
    assert len(capture.bond_rows) == 4
    assert len(capture.saturation_rows) == 1
    assert {r.run_id for r in capture.bond_rows} == {"kant_natural_42_on_1"}
    assert capture.path == str(path)


def test_read_capture_normalises_off_arm(tmp_path: Path) -> None:
    path = _build_capture(tmp_path, seed=7, arm="off", replicate_id=0)
    capture = read_bond_capture(path)
    assert capture.arm == "OFF"


def test_read_capture_missing_sidecar_raises(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "no_sidecar.duckdb"
    con = duckdb.connect(str(duckdb_path))
    con.close()
    with pytest.raises(BondAffinityReadError):
        read_bond_capture(duckdb_path)
