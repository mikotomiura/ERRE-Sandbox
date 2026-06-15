"""CLI e2e for ``horizon_versioned_saturation_verdict`` — what the horizon CLI adds.

CPU-only synthetic DuckDB + JSON manifest fixtures. The CV2 decision table is covered
by ``test_horizon_versioned_saturation_loader``; this focuses on the manifest ->
assemble -> horizon-score -> sidecar pipeline and the fields the horizon sidecar adds
over the versioned one: the Conditional-V2 status + admitted/excluded coverage
forensic, the frozen universal V2 it overrides (``frozen`` sub-record), the mechanised
``overall_verdict``, and the frozen-scorer blob SHA-256 provenance pin. Plus F5 exit.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from pathlib import Path

import duckdb

from erre_sandbox.cli.horizon_versioned_saturation_verdict import main
from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.hint_engagement.trace_ddl import (
    TABLE_NAME as HINT_TABLE_NAME,
)
from erre_sandbox.evidence.hint_engagement.trace_ddl import (
    HintEngagementTraceRow,
    bootstrap_hint_engagement_trace_schema,
)
from erre_sandbox.evidence.hint_engagement.trace_ddl import (
    column_names as hint_column_names,
)
from erre_sandbox.evidence.saturation.trace_ddl import (
    TABLE_NAME,
    SaturationTraceRow,
    bootstrap_saturation_trace_schema,
    column_names,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FloatOrFn = float | Callable[[int], float]


def _val(spec: _FloatOrFn, tick: int) -> float:
    return spec(tick) if callable(spec) else spec


def _floor_stepping(t: int) -> float:
    return 0.50 + 0.001 * t


def _chan(
    *,
    seed: int,
    key: str,
    run_id: str,
    floor: _FloatOrFn,
    mod: _FloatOrFn,
    ticks: Iterable[int],
    individual: str = "kant",
    axis: str = "self",
) -> list[SaturationTraceRow]:
    rows: list[SaturationTraceRow] = []
    for t in ticks:
        fv = _val(floor, t)
        rows.append(
            SaturationTraceRow(
                run_id=run_id,
                seed=seed,
                individual_id=individual,
                axis=axis,
                key=key,
                tick=t,
                base_floor_value=fv,
                modulated_value=_val(mod, t),
                floor_fingerprint_hash=f"fp{round(fv, 6)}",
                individual_layer_enabled=True,
            )
        )
    return rows


def _on_rows(seed: int, run_id: str) -> list[SaturationTraceRow]:
    """6 admitted-healthy kant channels (long grid) + 3 censored hume channels."""
    rows: list[SaturationTraceRow] = []
    for i in range(6):
        rows += _chan(
            seed=seed,
            key=f"k{i}",
            run_id=run_id,
            individual="kant",
            ticks=range(10, 45),
            floor=_floor_stepping,
            mod=lambda t: _floor_stepping(t) + (0.10 if t <= 17 else 0.0),
        )
    for i in range(3):
        rows += _chan(
            seed=seed,
            key=f"h{i}",
            run_id=run_id,
            individual="hume",
            ticks=range(10, 28),  # short individual grid -> censored / excluded
            floor=_floor_stepping,
            mod=lambda t: _floor_stepping(t) + 0.10,
        )
    return rows


def _off_rows(seed: int, run_id: str) -> list[SaturationTraceRow]:
    """OFF control with the SAME population (kant + hume) — drop-on-churn trials."""
    rows: list[SaturationTraceRow] = []
    for i in range(6):
        rows += _chan(
            seed=seed,
            key=f"k{i}",
            run_id=run_id,
            individual="kant",
            ticks=range(10, 45),
            floor=_floor_stepping,
            mod=lambda t: _floor_stepping(t) + (0.10 if t % 2 == 0 else 0.0),
        )
    for i in range(3):
        rows += _chan(
            seed=seed,
            key=f"h{i}",
            run_id=run_id,
            individual="hume",
            ticks=range(10, 28),
            floor=_floor_stepping,
            mod=lambda t: _floor_stepping(t) + (0.10 if t % 2 == 0 else 0.0),
        )
    return rows


def _hints(seed: int, run_id: str) -> list[HintEngagementTraceRow]:
    hints: list[HintEngagementTraceRow] = [
        HintEngagementTraceRow(
            run_id=run_id,
            seed=seed,
            individual_id="kant",
            tick=t,
            llm_status="ok",
            exposed_entry_count=3,
            emitted=True,
            disposition="adopted",
            target_axis="self",
            target_key="k0",
            direction="strengthen",
            adopted_signed_step=0.05,
            individual_layer_enabled=True,
        )
        for t in range(10, 18)
    ]
    hints += [
        HintEngagementTraceRow(
            run_id=run_id,
            seed=seed,
            individual_id="hume",
            tick=t,
            llm_status="ok",
            exposed_entry_count=3,
            emitted=False,
            disposition="not_emitted",
            target_axis=None,
            target_key=None,
            direction=None,
            adopted_signed_step=0.0,
            individual_layer_enabled=True,
        )
        for t in range(10, 28)
    ]
    return hints


def _write_sat(path: Path, rows: list[SaturationTraceRow]) -> Path:
    con = duckdb.connect(str(path))
    try:
        con.execute(f"CREATE SCHEMA {METRICS_SCHEMA}")
        bootstrap_saturation_trace_schema(con, METRICS_SCHEMA)
        cols = column_names()
        sql = (
            f"INSERT INTO {METRICS_SCHEMA}.{TABLE_NAME} "  # noqa: S608 — static, test
            f"({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
        )
        for row in rows:
            con.execute(sql, row.to_row())
    finally:
        con.close()
    return path


def _write_hint(path: Path, rows: list[HintEngagementTraceRow]) -> Path:
    con = duckdb.connect(str(path))
    try:
        con.execute(f"CREATE SCHEMA {METRICS_SCHEMA}")
        bootstrap_hint_engagement_trace_schema(con, METRICS_SCHEMA)
        cols = hint_column_names()
        sql = (
            f"INSERT INTO {METRICS_SCHEMA}.{HINT_TABLE_NAME} "  # noqa: S608 — static, test
            f"({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
        )
        for row in rows:
            con.execute(sql, row.to_row())
    finally:
        con.close()
    return path


def _manifest(tmp_path: Path) -> Path:
    entries: list[dict[str, object]] = []
    for seed in (1, 2, 3):
        on_cap = _write_sat(tmp_path / f"on{seed}.duckdb", _on_rows(seed, f"on{seed}"))
        off_cap = _write_sat(
            tmp_path / f"off{seed}.duckdb", _off_rows(seed, f"off{seed}")
        )
        hint_cap = _write_hint(
            tmp_path / f"hint{seed}.duckdb", _hints(seed, f"on{seed}")
        )
        entries.append(
            {
                "capture": str(on_cap),
                "arm": "ON",
                "source_run_id": f"src{seed}",
                "hint_capture": str(hint_cap),
            }
        )
        entries.append(
            {
                "capture": str(off_cap),
                "arm": "OFF",
                "source_run_id": f"src{seed}",
                "hint_capture": None,
            }
        )
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "versioned-verdict-manifest-1",
                "contrast_kind": "replay",
                "envelope": {"personas": ["kant"], "model": "qwen3:8b"},
                "entries": entries,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_cli_horizon_reachability_sidecar(tmp_path: Path) -> None:
    """Frozen would be INCONCLUSIVE (censored tail); horizon CV2 -> NON-SATURATED."""
    out = tmp_path / "verdict.json"
    rc = main(
        ["--manifest", str(_manifest(tmp_path)), "--run-id", "h", "--out", str(out)]
    )
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "horizon-versioned-saturation-verdict-1"
    assert payload["scorer_contract_version"] == "horizon-versioned-loader-1"
    assert payload["on_verdict"] == "NON-SATURATED"
    assert payload["overall_verdict"] == "NON-SATURATED"
    assert payload["off_control_complete"] is True
    assert len(payload["on_partitions"]) == 3
    for p in payload["on_partitions"]:
        assert p["cv2_status"] == "PASS"
        assert p["gate_pass"] is True
        assert p["versioned_label"] == "NON-SATURATED"
        assert p["n_admitted_channels"] == 6
        assert p["n_excluded_channels"] == 3
        assert p["coverage"] == 6 / 9
        # the frozen universal V2 it overrides is recorded for the diff
        assert p["frozen"]["v2_status"] == "INCONCLUSIVE"
        assert p["frozen"]["gate_pass"] is False
    # frozen-scorer blob provenance pin (Codex U7 MED-2)
    blobs = payload["frozen_scorer_blob_sha256"]
    assert "versioned_loader.py" in blobs
    assert "versioned_constants.py" in blobs
    assert all(_SHA256_RE.match(v) for v in blobs.values())


def test_cli_bad_manifest_exit2_no_sidecar(tmp_path: Path) -> None:
    bad = tmp_path / "m.json"
    bad.write_text("{broken", encoding="utf-8")
    out = tmp_path / "verdict.json"
    rc = main(["--manifest", str(bad), "--run-id", "x", "--out", str(out)])
    assert rc == 2
    assert not out.exists()
