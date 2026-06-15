"""Replay driver CLI end-to-end coverage (U5, versioned-measurement ADR §5.2).

CPU-only synthetic DuckDB (no GPU / LLM). Builds 3 synthetic source captures (floor +
hint + sidecar), runs the replay driver, and verifies the **whole pipeline flows
unchanged into the verdict authority**: ``run_replay`` → ``build_paired_manifest``
(preflight assemble passes) → ``score_versioned_saturation`` yields a verdict over the
six (3 ON + 3 OFF) replayed captures. Also checks determinism (the logical arm-capture
content is reproducible) and the N=3 fail-fast.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from erre_sandbox.cli.versioned_replay import run_replay
from erre_sandbox.contracts.cognition_layers import (
    SubjectiveWorldModel,
    WorldModelEntry,
)
from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.capture_sidecar import SidecarV1, write_sidecar_atomic
from erre_sandbox.evidence.capture_sidecar import sidecar_path_for as sidecar_for
from erre_sandbox.evidence.hint_engagement.trace_ddl import (
    TABLE_NAME as HINT_TABLE,
)
from erre_sandbox.evidence.hint_engagement.trace_ddl import (
    HintEngagementTraceRow,
    bootstrap_hint_engagement_trace_schema,
)
from erre_sandbox.evidence.hint_engagement.trace_ddl import (
    column_names as hint_columns,
)
from erre_sandbox.evidence.saturation.floor_input_trace_ddl import (
    TABLE_NAME as FLOOR_TABLE,
)
from erre_sandbox.evidence.saturation.floor_input_trace_ddl import (
    FloorInputTraceRow,
    bootstrap_floor_input_trace_schema,
)
from erre_sandbox.evidence.saturation.floor_input_trace_ddl import (
    column_names as floor_columns,
)
from erre_sandbox.evidence.saturation.loader import read_saturation_trace_rows
from erre_sandbox.evidence.saturation.versioned_loader import (
    score_versioned_saturation,
)
from erre_sandbox.evidence.saturation.versioned_verdict_report import assemble_bundles

_PERSONA = "rikyu"
_SALT = "testsalt"
_INDIVIDUALS = ("rikyu_a", "rikyu_b")
_T0 = 10  # T_WARMUP
_N_TICKS = 16


def _floor_json(value: float) -> str:
    return SubjectiveWorldModel(
        entries=[
            WorldModelEntry(
                axis="env",
                key="agora",
                value=value,
                confidence=0.6,
                cited_memory_ids=("m1",),
                last_updated_tick=5,
            )
        ]
    ).model_dump_json()


def _make_source(tmp_path: Path, run_idx: int, seed: int) -> Path:
    """Write a synthetic individual-layer-on natural source capture + its sidecar."""
    run_id = f"{_PERSONA}_natural_run{run_idx}"
    db = tmp_path / f"source_run{run_idx}.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    con.execute(f"CREATE SCHEMA {METRICS_SCHEMA}")
    bootstrap_floor_input_trace_schema(con, METRICS_SCHEMA)
    bootstrap_hint_engagement_trace_schema(con, METRICS_SCHEMA)
    fcols = floor_columns()
    finsert = (
        f"INSERT INTO {METRICS_SCHEMA}.{FLOOR_TABLE} "  # noqa: S608 — static identifiers, test
        f"({', '.join(fcols)}) VALUES ({', '.join('?' for _ in fcols)})"
    )
    hcols = hint_columns()
    hinsert = (
        f"INSERT INTO {METRICS_SCHEMA}.{HINT_TABLE} "  # noqa: S608 — static identifiers, test
        f"({', '.join(hcols)}) VALUES ({', '.join('?' for _ in hcols)})"
    )
    for ind in _INDIVIDUALS:
        for k in range(_N_TICKS):
            tick = _T0 + k
            con.execute(
                finsert,
                FloorInputTraceRow(
                    run_id=run_id,
                    seed=seed,
                    individual_id=ind,
                    tick=tick,
                    floor_swm_json=_floor_json(0.50 + 0.001 * tick),
                    individual_layer_enabled=True,
                ).to_row(),
            )
            con.execute(
                hinsert,
                HintEngagementTraceRow(
                    run_id=run_id,
                    seed=seed,
                    individual_id=ind,
                    tick=tick,
                    llm_status="ok",
                    exposed_entry_count=1,
                    emitted=True,
                    disposition="adopted",
                    target_axis="env",
                    target_key="agora",
                    direction="strengthen",
                    adopted_signed_step=0.05,
                    individual_layer_enabled=True,
                ).to_row(),
            )
    con.close()
    write_sidecar_atomic(
        sidecar_for(db),
        SidecarV1(
            status="complete",
            stop_reason="complete",
            focal_target=0,
            focal_observed=0,
            total_rows=len(_INDIVIDUALS) * _N_TICKS,
            wall_timeout_min=90.0,
            drain_completed=True,
            runtime_drain_timeout=False,
            git_sha="deadbeef",
            captured_at="2026-06-15T00:00:00+00:00",
            persona=_PERSONA,
            condition="natural",
            run_idx=run_idx,
            duckdb_path=str(db.resolve()),
            stm_carry_arm="off",
            seed=seed,
            seed_salt=_SALT,
        ),
    )
    return db


def _three_sources(tmp_path: Path) -> list[Path]:
    return [_make_source(tmp_path, run_idx=i, seed=1000 + i) for i in range(3)]


def test_replay_pipeline_flows_into_verdict(tmp_path: Path) -> None:
    sources = _three_sources(tmp_path)
    out_dir = tmp_path / "out"
    manifest_path = out_dir / "replay_manifest.json"

    manifest = run_replay(
        sources,
        out_dir=out_dir,
        source_run_id_base="replay_e2e",
        manifest_path=manifest_path,
    )
    # 3 pairs -> 6 entries; replay is recorded as such.
    assert manifest.contrast_kind == "replay"
    assert len(manifest.entries) == 6
    assert all(e.hint_capture is not None for e in manifest.entries)  # HIGH-2

    # The manifest grounds (preflight assemble) and the scorer produces a verdict.
    bundles, _sources_prov = assemble_bundles(manifest, manifest_path)
    result = score_versioned_saturation(bundles)
    assert result.on_verdict in {"SATURATED", "NON-SATURATED", "INCONCLUSIVE"}
    assert len(result.on_partitions) == 3
    assert len(result.off_partitions) == 3
    # The ON arm carried retention across the cross-fp churn; the OFF arm did not —
    # the carry separation survives the full round-trip through the trace files.
    assert all(p.r_retained > 0 for p in result.on_partitions)
    assert all(p.r_retained == 0 for p in result.off_partitions)


def test_replay_arm_capture_content_is_deterministic(tmp_path: Path) -> None:
    """Codex MED-2: the logical arm-capture rows are reproducible (not file bytes)."""
    sources = _three_sources(tmp_path)
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    run_replay(
        sources, out_dir=out_a, source_run_id_base="x", manifest_path=out_a / "m.json"
    )
    run_replay(
        sources, out_dir=out_b, source_run_id_base="x", manifest_path=out_b / "m.json"
    )
    on_a = out_a / f"{_PERSONA}_natural_run0_replay_on.duckdb"
    on_b = out_b / f"{_PERSONA}_natural_run0_replay_on.duckdb"
    rows_a = _saturation_rows(on_a)
    rows_b = _saturation_rows(on_b)
    assert rows_a == rows_b
    assert rows_a  # non-empty


def _saturation_rows(db: Path) -> list[tuple[object, ...]]:
    con = duckdb.connect(str(db), read_only=True)
    try:
        rows = read_saturation_trace_rows(con, schema=METRICS_SCHEMA)
    finally:
        con.close()
    return [r.to_row() for r in rows]


def test_replay_rejects_single_source(tmp_path: Path) -> None:
    """N=3 binding: a single-seed contrast cannot yield a verdict (fail-fast)."""
    sources = [_make_source(tmp_path, run_idx=0, seed=1000)]
    out_dir = tmp_path / "out"
    with pytest.raises(Exception, match=r"3 pair|expected exactly"):
        run_replay(
            sources,
            out_dir=out_dir,
            source_run_id_base="x",
            manifest_path=out_dir / "m.json",
        )
