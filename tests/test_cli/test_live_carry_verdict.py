"""CLI assembly coverage for ``live_carry_verdict`` (freeze ADR §0-§7).

CPU-only synthetic 12-run matrix: each cell is one small DuckDB (floor-input +
saturation traces) plus its ``.capture.json`` sidecar carrying the matrix identity
(``seed`` / ``stm_carry_arm`` / ``replicate_id``). The four-state decision itself is
covered by ``test_live_carry_scorer``; this test focuses on what the CLI *adds* —
multi-file read via :func:`read_capture`, sidecar-driven provenance, the frozen-
threshold echo, the verdict-over-capture collision guard, and an end-to-end CONFIRMED
render.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import duckdb
import pytest

from erre_sandbox.cli.live_carry_verdict import main
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
from erre_sandbox.evidence.live_carry import constants as _c
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

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SEEDS = (1, 2, 3)


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


def _write_cell(
    tmp_path: Path,
    *,
    seed: int,
    arm: str,
    replicate_id: int,
    keys: list[tuple[str, str]],
    engaged: bool,
) -> Path:
    duckdb_path = tmp_path / f"{seed}_{arm}_{replicate_id}.duckdb"
    run_id = f"kant_natural_run{replicate_id}"
    con = duckdb.connect(str(duckdb_path))
    try:
        con.execute(f"CREATE SCHEMA {METRICS_SCHEMA}")
        bootstrap_floor_input_trace_schema(con, METRICS_SCHEMA)
        bootstrap_saturation_trace_schema(con, METRICS_SCHEMA)
        bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
        for tick in range(15):
            # Coherence non-inferiority is a required M2 gate (flat ON==OFF series).
            _insert(
                con,
                _STATE_TABLE,
                _state_columns(),
                IndividualStateTraceRow(
                    run_id=run_id,
                    individual_id="kant",
                    tick=tick,
                    development_stage=None,
                    coherence_score=0.7,
                    belief_classes_json=None,
                    arc_segment_count=0,
                    world_model_keys_json=None,
                    world_model_evidence_json=None,
                ).to_row(),
            )
            _insert(
                con,
                _FLOOR_TABLE,
                _floor_columns(),
                FloorInputTraceRow(
                    run_id=run_id,
                    seed=seed,
                    individual_id="kant",
                    tick=tick,
                    floor_swm_json=_floor_json(keys),
                    individual_layer_enabled=True,
                ).to_row(),
            )
            # ON r0 toggles its fingerprint each tick (>=5 retained-offset events);
            # every other run keeps a constant fingerprint (0 events).
            fp = f"fp{tick}" if engaged else "fp_const"
            _insert(
                con,
                _SAT_TABLE,
                _sat_columns(),
                SaturationTraceRow(
                    run_id=run_id,
                    seed=seed,
                    individual_id="kant",
                    axis="self",
                    key="eng",
                    tick=tick,
                    base_floor_value=0.5,
                    modulated_value=0.6,
                    floor_fingerprint_hash=fp,
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
            total_rows=15,
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


def _confirmed_matrix(tmp_path: Path) -> list[Path]:
    """A 12-run matrix engineered to route CONFIRMED (disjoint ON/OFF floors)."""
    paths: list[Path] = []
    for seed in _SEEDS:
        paths.append(
            _write_cell(
                tmp_path,
                seed=seed,
                arm="on",
                replicate_id=0,
                keys=[("self", "on")],
                engaged=True,
            )
        )
        paths.append(
            _write_cell(
                tmp_path,
                seed=seed,
                arm="on",
                replicate_id=1,
                keys=[("self", "on")],
                engaged=False,
            )
        )
        paths.append(
            _write_cell(
                tmp_path,
                seed=seed,
                arm="off",
                replicate_id=0,
                keys=[("self", "off")],
                engaged=False,
            )
        )
        paths.append(
            _write_cell(
                tmp_path,
                seed=seed,
                arm="off",
                replicate_id=1,
                keys=[("self", "off")],
                engaged=False,
            )
        )
    return paths


def _run(tmp_path: Path, captures: list[Path], run_id: str = "t") -> dict:
    out = tmp_path / "verdict.json"
    argv: list[str] = []
    for cap in captures:
        argv += ["--capture", str(cap)]
    argv += ["--run-id", run_id, "--out", str(out)]
    assert main(argv) == 0
    return json.loads(out.read_text(encoding="utf-8"))


def test_cli_confirmed_end_to_end(tmp_path: Path) -> None:
    payload = _run(tmp_path, _confirmed_matrix(tmp_path), run_id="live-run")
    assert payload["verdict"] == "LIVE_CARRY_TRAJECTORY_EFFECT_CONFIRMED"
    assert payload["run_id"] == "live-run"
    assert payload["schema_version"] == "live-carry-verdict-1"
    assert sorted(payload["seeds"]) == [1, 2, 3]
    assert payload["m1"]["go"] is True
    assert payload["m0"]["status"] == "pass"
    assert payload["m2"]["status"] == "pass"


def test_cli_provenance_and_thresholds(tmp_path: Path) -> None:
    payload = _run(tmp_path, _confirmed_matrix(tmp_path))
    sources = payload["sources"]
    assert len(sources) == 12
    for src in sources:
        assert _SHA256_RE.match(src["sha256"])
        assert src["seed"] in _SEEDS
        assert src["arm"] in ("on", "off")
        assert src["replicate_id"] in (0, 1)
        assert src["floor_row_count"] == 15

    thr = payload["thresholds"]
    expected = {
        "r_min": _c.R_MIN,
        "degenerate_null_floor": _c.DEGENERATE_NULL_FLOOR,
        "on_noise_factor": _c.ON_NOISE_FACTOR,
        "m0_engagement_floor": _c.M0_ENGAGEMENT_FLOOR,
        "coverage_min": _c.COVERAGE_MIN,
        "min_tick_pairs": _c.MIN_TICK_PAIRS,
        "m2_cap": _c.M2_CAP,
        "m2_transient_tol": _c.M2_TRANSIENT_TOL,
        "m2_coherence_margin": _c.M2_COHERENCE_MARGIN,
        "m2_throughput_ratio": _c.M2_THROUGHPUT_RATIO,
        "reach_null_max": _c.REACH_NULL_MAX,
        "reach_pos_min": _c.REACH_POS_MIN,
        "n_seed": _c.N_SEED,
        "rerun_per_arm": _c.RERUN_PER_ARM,
    }
    assert thr == expected


def test_cli_default_out_path(tmp_path: Path) -> None:
    caps = _confirmed_matrix(tmp_path)
    argv: list[str] = []
    for c in caps:
        argv += ["--capture", str(c)]
    argv += ["--run-id", "default-out"]
    assert main(argv) == 0
    sidecar = caps[0].with_name(caps[0].name + ".live_carry_verdict.json")
    assert sidecar.exists()


def test_cli_rejects_out_over_capture(tmp_path: Path) -> None:
    caps = _confirmed_matrix(tmp_path)
    with pytest.raises(SystemExit):
        main(["--capture", str(caps[0]), "--run-id", "x", "--out", str(caps[0])])
