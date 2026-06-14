"""U4: ``versioned_verdict_manifest`` CLI — atomic write, round-trip, collision."""

from __future__ import annotations

from typing import TYPE_CHECKING

import duckdb
import pytest

from erre_sandbox.cli.versioned_verdict_manifest import main
from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.capture_sidecar import (
    SidecarV1,
    sidecar_path_for,
    write_sidecar_atomic,
)
from erre_sandbox.evidence.saturation.trace_ddl import (
    TABLE_NAME,
    SaturationTraceRow,
    bootstrap_saturation_trace_schema,
    column_names,
)
from erre_sandbox.evidence.saturation.versioned_verdict_report import load_manifest

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pathlib import Path


def _rows(seed: int, run_id: str, *, on: bool) -> list[SaturationTraceRow]:
    out: list[SaturationTraceRow] = []
    for i in range(6):
        for t in range(10, 30):
            fv = 0.50 + 0.001 * t
            mod = fv + (0.10 if (t <= 18 if on else t % 2 == 0) else 0.0)
            out.append(
                SaturationTraceRow(
                    run_id=run_id,
                    seed=seed,
                    individual_id="kant",
                    axis="self",
                    key=f"k{i}",
                    tick=t,
                    base_floor_value=fv,
                    modulated_value=mod,
                    floor_fingerprint_hash=f"fp{round(fv, 6)}",
                    individual_layer_enabled=True,
                )
            )
    return out


def _capture(
    path: Path, rows: list[SaturationTraceRow], *, run_idx: int, seed: int, arm: str
) -> Path:
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
    write_sidecar_atomic(
        sidecar_path_for(path),
        SidecarV1(
            status="complete",
            stop_reason="complete",
            focal_target=1,
            focal_observed=1,
            total_rows=1,
            wall_timeout_min=1.0,
            drain_completed=True,
            runtime_drain_timeout=False,
            git_sha="deadbeef",
            captured_at="2026-06-15T00:00:00Z",
            persona="kant",
            condition="natural",
            run_idx=run_idx,
            duckdb_path=str(path),
            stm_carry_arm=arm,  # type: ignore[arg-type]
            seed=seed,
            seed_salt="m9-eval-v1",
        ),
    )
    return path


def _three_pairs(tmp_path: Path) -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    for i, seed in enumerate((101, 102, 103)):
        run_id = f"kant_natural_run{i}"
        on = _capture(
            tmp_path / f"on{i}.duckdb",
            _rows(seed, run_id, on=True),
            run_idx=i,
            seed=seed,
            arm="on",
        )
        off = _capture(
            tmp_path / f"off{i}.duckdb",
            _rows(seed, run_id, on=False),
            run_idx=i,
            seed=seed,
            arm="off",
        )
        pairs.append((on, off))
    return pairs


def _pairing_args(pairs: list[tuple[Path, Path]]) -> list[str]:
    args: list[str] = []
    for on, off in pairs:
        args += ["--pairing", f"on={on},off={off}"]
    return args


def test_cli_writes_manifest_and_round_trips(tmp_path: Path) -> None:
    pairs = _three_pairs(tmp_path)
    out = tmp_path / "manifest.json"
    rc = main(
        [
            *_pairing_args(pairs),
            "--source-run-id-base",
            "kant_iiia",
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    assert out.is_file()
    manifest = load_manifest(out)
    assert len(manifest.entries) == 6
    assert manifest.contrast_kind == "live"


def test_cli_rejects_out_colliding_with_a_capture(tmp_path: Path) -> None:
    pairs = _three_pairs(tmp_path)
    # --out points at an input capture: the collision guard must refuse.
    with pytest.raises(SystemExit, match="refusing to overwrite"):
        main(
            [
                *_pairing_args(pairs),
                "--source-run-id-base",
                "kant_iiia",
                "--out",
                str(pairs[0][0]),
            ]
        )


def test_cli_rejects_a_mistagged_compose(tmp_path: Path) -> None:
    """A non-zero exit + no manifest when the compose is rejected by the builder."""
    pairs = _three_pairs(tmp_path)
    # Re-write the first ON capture's sidecar to declare OFF (mis-tag).
    write_sidecar_atomic(
        sidecar_path_for(pairs[0][0]),
        SidecarV1(
            status="complete",
            stop_reason="complete",
            focal_target=1,
            focal_observed=1,
            total_rows=1,
            wall_timeout_min=1.0,
            drain_completed=True,
            runtime_drain_timeout=False,
            git_sha="deadbeef",
            captured_at="2026-06-15T00:00:00Z",
            persona="kant",
            condition="natural",
            run_idx=0,
            duckdb_path=str(pairs[0][0]),
            stm_carry_arm="off",
            seed=101,
            seed_salt="m9-eval-v1",
        ),
    )
    out = tmp_path / "manifest.json"
    rc = main(
        [*_pairing_args(pairs), "--source-run-id-base", "kant_iiia", "--out", str(out)]
    )
    assert rc == 2
    assert not out.exists()
