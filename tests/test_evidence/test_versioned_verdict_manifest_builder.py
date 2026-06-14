"""U4: ``build_paired_manifest`` — machine-grounded 案 C manifest construction.

CPU-only synthetic DuckDB captures + sidecars (mirrors
``tests/test_cli/test_versioned_saturation_verdict`` fixtures). Covers the happy 3-pair
path, every fail-fast guard the independent review required (mis-tag / mis-pair / stale
sidecar / status / count / completeness), and the end-to-end flow into the scorer.
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
from erre_sandbox.evidence.saturation.trace_ddl import (
    TABLE_NAME,
    SaturationTraceRow,
    bootstrap_saturation_trace_schema,
    column_names,
)
from erre_sandbox.evidence.saturation.versioned_loader import (
    score_versioned_saturation,
)
from erre_sandbox.evidence.saturation.versioned_verdict_manifest_builder import (
    CapturePairing,
    PairedManifestBuildError,
    build_paired_manifest,
)
from erre_sandbox.evidence.saturation.versioned_verdict_report import assemble_bundles

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pathlib import Path

_SALT = "m9-eval-v1"


# ---------------------------------------------------------------------------
# Row + capture + sidecar fixtures
# ---------------------------------------------------------------------------


def _floor_stepping(t: int) -> float:
    return 0.50 + 0.001 * t


def _chan(
    *, seed: int, key: str, run_id: str, on: bool, ticks: range = range(10, 30)
) -> list[SaturationTraceRow]:
    rows: list[SaturationTraceRow] = []
    for t in ticks:
        fv = _floor_stepping(t)
        if on:
            mod = fv + (0.10 if t <= 18 else 0.0)
        else:
            mod = fv + (0.10 if t % 2 == 0 else 0.0)
        rows.append(
            SaturationTraceRow(
                run_id=run_id,
                seed=seed,
                individual_id="kant",
                axis="self",
                key=key,
                tick=t,
                base_floor_value=fv,
                modulated_value=mod,
                floor_fingerprint_hash=f"fp{round(fv, 6)}",
                individual_layer_enabled=True,
            )
        )
    return rows


def _arm_rows(
    seed: int, run_id: str, *, on: bool, n: int = 6
) -> list[SaturationTraceRow]:
    rows: list[SaturationTraceRow] = []
    for i in range(n):
        rows += _chan(seed=seed, key=f"k{i}", run_id=run_id, on=on)
    return rows


def _write_sat_capture(path: Path, rows: list[SaturationTraceRow]) -> Path:
    con = duckdb.connect(str(path))
    try:
        con.execute(f"CREATE SCHEMA {METRICS_SCHEMA}")
        bootstrap_saturation_trace_schema(con, METRICS_SCHEMA)
        cols = column_names()
        insert_sql = (
            f"INSERT INTO {METRICS_SCHEMA}.{TABLE_NAME} "  # noqa: S608 — static, test
            f"({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
        )
        for row in rows:
            con.execute(insert_sql, row.to_row())
    finally:
        con.close()
    return path


def _write_sidecar(
    capture: Path,
    *,
    run_idx: int,
    seed: int,
    arm: str | None,
    persona: str = "kant",
    condition: str = "natural",
    status: str = "complete",
    salt: str | None = _SALT,
    duckdb_path: Path | None = None,
) -> None:
    payload = SidecarV1(
        status=status,  # type: ignore[arg-type]
        stop_reason="complete",
        focal_target=1,
        focal_observed=1,
        total_rows=1,
        wall_timeout_min=1.0,
        drain_completed=True,
        runtime_drain_timeout=False,
        git_sha="deadbeef",
        captured_at="2026-06-15T00:00:00Z",
        persona=persona,
        condition=condition,  # type: ignore[arg-type]
        run_idx=run_idx,
        duckdb_path=str(duckdb_path if duckdb_path is not None else capture),
        stm_carry_arm=arm,  # type: ignore[arg-type]
        seed=seed,
        seed_salt=salt,
    )
    write_sidecar_atomic(sidecar_path_for(capture), payload)


def _make_pair(tmp_path: Path, idx: int, *, seed: int, run_idx: int) -> CapturePairing:
    run_id = f"kant_natural_run{run_idx}"
    on_cap = _write_sat_capture(
        tmp_path / f"on{idx}.duckdb", _arm_rows(seed, run_id, on=True)
    )
    off_cap = _write_sat_capture(
        tmp_path / f"off{idx}.duckdb", _arm_rows(seed, run_id, on=False)
    )
    _write_sidecar(on_cap, run_idx=run_idx, seed=seed, arm="on")
    _write_sidecar(off_cap, run_idx=run_idx, seed=seed, arm="off")
    return CapturePairing(on_capture=on_cap, off_capture=off_cap)


def _good_pairs(tmp_path: Path) -> list[CapturePairing]:
    return [
        _make_pair(tmp_path, 0, seed=101, run_idx=0),
        _make_pair(tmp_path, 1, seed=102, run_idx=1),
        _make_pair(tmp_path, 2, seed=103, run_idx=2),
    ]


def _build(tmp_path: Path, pairs: list[CapturePairing], **kw: object):
    return build_paired_manifest(
        pairs,
        source_run_id_base="kant_iiia",
        manifest_path=tmp_path / "manifest.json",
        **kw,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_three_pairs_build_a_valid_manifest(tmp_path: Path) -> None:
    manifest = _build(tmp_path, _good_pairs(tmp_path))
    assert manifest.schema_version == "versioned-verdict-manifest-1"
    assert len(manifest.entries) == 6
    # ON then OFF per pair; source_run_id is per-pair distinct.
    arms = [e.arm for e in manifest.entries]
    assert arms == ["ON", "OFF", "ON", "OFF", "ON", "OFF"]
    src_ids = {e.source_run_id for e in manifest.entries}
    assert src_ids == {"kant_iiia_pair0", "kant_iiia_pair1", "kant_iiia_pair2"}
    # ON and OFF of each pair share their source_run_id.
    for i in range(3):
        assert manifest.entries[2 * i].source_run_id == f"kant_iiia_pair{i}"
        assert manifest.entries[2 * i + 1].source_run_id == f"kant_iiia_pair{i}"


def test_generated_manifest_flows_to_a_verdict(tmp_path: Path) -> None:
    """End-to-end: builder -> assemble_bundles -> frozen scorer yields a verdict."""
    manifest = _build(tmp_path, _good_pairs(tmp_path))
    bundles, _sources = assemble_bundles(manifest, tmp_path / "manifest.json")
    result = score_versioned_saturation(bundles)
    assert len(result.on_partitions) == 3
    assert len(result.off_partitions) == 3
    assert isinstance(result.on_verdict, str)


# ---------------------------------------------------------------------------
# Fail-fast guards (independent review HIGH-1/2/5)
# ---------------------------------------------------------------------------


def test_wrong_pair_count_rejected(tmp_path: Path) -> None:
    pairs = _good_pairs(tmp_path)[:2]
    with pytest.raises(PairedManifestBuildError, match="exactly 3 pair"):
        _build(tmp_path, pairs)


def test_sidecar_arm_mismatch_rejected(tmp_path: Path) -> None:
    pairs = _good_pairs(tmp_path)
    # Corrupt the first ON capture's sidecar to declare OFF.
    _write_sidecar(pairs[0].on_capture, run_idx=0, seed=101, arm="off")
    with pytest.raises(PairedManifestBuildError, match="declared arm ON"):
        _build(tmp_path, pairs)


def test_within_pair_seed_mismatch_rejected(tmp_path: Path) -> None:
    pairs = _good_pairs(tmp_path)
    # OFF sidecar claims a different seed than its ON partner (HIGH-1).
    _write_sidecar(pairs[0].off_capture, run_idx=0, seed=999, arm="off")
    with pytest.raises(PairedManifestBuildError, match="seed"):
        _build(tmp_path, pairs)


def test_partial_status_rejected(tmp_path: Path) -> None:
    pairs = _good_pairs(tmp_path)
    _write_sidecar(pairs[0].on_capture, run_idx=0, seed=101, arm="on", status="partial")
    with pytest.raises(PairedManifestBuildError, match="status"):
        _build(tmp_path, pairs)


def test_persona_mismatch_rejected(tmp_path: Path) -> None:
    pairs = _good_pairs(tmp_path)
    _write_sidecar(
        pairs[0].on_capture, run_idx=0, seed=101, arm="on", persona="nietzsche"
    )
    with pytest.raises(PairedManifestBuildError, match="persona"):
        _build(tmp_path, pairs)


def test_stale_sidecar_duckdb_path_swap_rejected(tmp_path: Path) -> None:
    pairs = _good_pairs(tmp_path)
    # Sidecar points at a different (existing) file than the capture it describes.
    other = pairs[1].off_capture
    _write_sidecar(
        pairs[0].on_capture, run_idx=0, seed=101, arm="on", duckdb_path=other
    )
    with pytest.raises(PairedManifestBuildError, match="stale or swapped"):
        _build(tmp_path, pairs)


def test_duplicate_actual_seed_across_pairs_rejected(tmp_path: Path) -> None:
    """Distinct run_idx but a reused actual seed -> N=3 completeness fails."""
    pairs = [
        _make_pair(tmp_path, 0, seed=101, run_idx=0),
        _make_pair(tmp_path, 1, seed=101, run_idx=1),  # duplicate seed
        _make_pair(tmp_path, 2, seed=103, run_idx=2),
    ]
    with pytest.raises(PairedManifestBuildError, match="distinct actual seed"):
        _build(tmp_path, pairs)


def test_missing_sidecar_rejected(tmp_path: Path) -> None:
    pairs = _good_pairs(tmp_path)
    sidecar_path_for(pairs[0].on_capture).unlink()
    with pytest.raises(PairedManifestBuildError, match="no sidecar"):
        _build(tmp_path, pairs)
