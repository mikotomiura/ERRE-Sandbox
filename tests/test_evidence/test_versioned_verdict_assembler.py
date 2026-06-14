"""Assembler F4 fail-fast coverage for the versioned verdict (versioned-measurement).

CPU-only, synthetic DuckDB fixtures. The scorer (``score_versioned_saturation``) pairs
on ``(source_run_id, seed)`` and never detects a mis-pairing; these tests pin the
assembler's job — to reject a structurally broken compose **before** the scorer runs
(run_id/seed exactly-one, natural-key de-dup, hint identity, cross-bundle / alias
de-dup, per-pairing population agreement) — and to pass every *scientific* shape
straight through. The decision itself is covered by the loader test.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

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
from erre_sandbox.evidence.saturation.versioned_verdict_report import (
    VersionedVerdictAssemblyError,
    VersionedVerdictManifestError,
    assemble_bundles,
    load_manifest,
)

# ---------------------------------------------------------------------------
# Fixtures: row + capture + manifest builders
# ---------------------------------------------------------------------------


def _row(
    *,
    run_id: str = "r",
    seed: int = 1,
    individual: str = "kant",
    axis: str = "self",
    key: str = "k0",
    tick: int = 10,
    floor: float = 0.5,
    mod: float = 0.55,
) -> SaturationTraceRow:
    return SaturationTraceRow(
        run_id=run_id,
        seed=seed,
        individual_id=individual,
        axis=axis,
        key=key,
        tick=tick,
        base_floor_value=floor,
        modulated_value=mod,
        floor_fingerprint_hash=f"fp{round(floor, 6)}",
        individual_layer_enabled=True,
    )


def _capture(
    *, run_id: str = "r", seed: int = 1, individuals: tuple[str, ...] = ("kant",)
) -> list[SaturationTraceRow]:
    """A small well-formed capture: each individual gets ticks 10..12 on one channel."""
    return [
        _row(run_id=run_id, seed=seed, individual=ind, tick=tick)
        for ind in individuals
        for tick in range(10, 13)
    ]


def _hint_row(
    *, run_id: str = "r", seed: int = 1, individual: str = "kant", tick: int = 10
) -> HintEngagementTraceRow:
    return HintEngagementTraceRow(
        run_id=run_id,
        seed=seed,
        individual_id=individual,
        tick=tick,
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


def _write_hint_capture(path: Path, rows: list[HintEngagementTraceRow]) -> Path:
    con = duckdb.connect(str(path))
    try:
        con.execute(f"CREATE SCHEMA {METRICS_SCHEMA}")
        bootstrap_hint_engagement_trace_schema(con, METRICS_SCHEMA)
        cols = hint_column_names()
        insert_sql = (
            f"INSERT INTO {METRICS_SCHEMA}.{HINT_TABLE_NAME} "  # noqa: S608 — static, test
            f"({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
        )
        for row in rows:
            con.execute(insert_sql, row.to_row())
    finally:
        con.close()
    return path


def _write_manifest(
    path: Path,
    entries: list[dict[str, object]],
    *,
    contrast_kind: str = "replay",
    schema_version: str = "versioned-verdict-manifest-1",
    envelope: dict[str, object] | None = None,
) -> Path:
    payload: dict[str, object] = {
        "schema_version": schema_version,
        "contrast_kind": contrast_kind,
        "entries": entries,
    }
    if envelope is not None:
        payload["envelope"] = envelope
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _entry(
    capture: Path,
    arm: str,
    source_run_id: str,
    hint_capture: Path | None = None,
) -> dict[str, object]:
    return {
        "capture": str(capture),
        "arm": arm,
        "source_run_id": source_run_id,
        "hint_capture": None if hint_capture is None else str(hint_capture),
    }


# ---------------------------------------------------------------------------
# Manifest schema (structural)
# ---------------------------------------------------------------------------


def test_manifest_parse_error(tmp_path: Path) -> None:
    bad = tmp_path / "m.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(VersionedVerdictManifestError):
        load_manifest(bad)


def test_manifest_schema_error_bad_arm(tmp_path: Path) -> None:
    cap = _write_sat_capture(tmp_path / "c.duckdb", _capture())
    m = _write_manifest(tmp_path / "m.json", [_entry(cap, "SIDEWAYS", "s")])
    with pytest.raises(VersionedVerdictManifestError):
        load_manifest(m)


def test_manifest_missing_required_key(tmp_path: Path) -> None:
    m = tmp_path / "m.json"
    m.write_text(json.dumps({"contrast_kind": "replay", "entries": []}), "utf-8")
    with pytest.raises(VersionedVerdictManifestError):
        load_manifest(m)


def test_manifest_bad_schema_version(tmp_path: Path) -> None:
    cap = _write_sat_capture(tmp_path / "c.duckdb", _capture())
    m = _write_manifest(
        tmp_path / "m.json", [_entry(cap, "ON", "s")], schema_version="v999"
    )
    with pytest.raises(VersionedVerdictManifestError):
        load_manifest(m)


def test_manifest_empty_entries(tmp_path: Path) -> None:
    m = _write_manifest(tmp_path / "m.json", [])
    with pytest.raises(VersionedVerdictManifestError):
        load_manifest(m)


# ---------------------------------------------------------------------------
# Per-capture structural anomalies
# ---------------------------------------------------------------------------


def test_missing_capture_file(tmp_path: Path) -> None:
    m = _write_manifest(
        tmp_path / "m.json", [_entry(tmp_path / "nope.duckdb", "ON", "s")]
    )
    manifest = load_manifest(m)
    with pytest.raises(VersionedVerdictManifestError):
        assemble_bundles(manifest, m)


def test_empty_capture_zero_rows(tmp_path: Path) -> None:
    cap = _write_sat_capture(tmp_path / "c.duckdb", [])
    m = _write_manifest(tmp_path / "m.json", [_entry(cap, "ON", "s")])
    with pytest.raises(VersionedVerdictAssemblyError):
        assemble_bundles(load_manifest(m), m)


def test_mixed_run_id_in_one_capture(tmp_path: Path) -> None:
    rows = _capture(run_id="a") + _capture(run_id="b", individuals=("hume",))
    cap = _write_sat_capture(tmp_path / "c.duckdb", rows)
    m = _write_manifest(tmp_path / "m.json", [_entry(cap, "ON", "s")])
    with pytest.raises(VersionedVerdictAssemblyError):
        assemble_bundles(load_manifest(m), m)


def test_multi_seed_in_one_capture(tmp_path: Path) -> None:
    rows = _capture(seed=1) + _capture(seed=2, individuals=("hume",))
    cap = _write_sat_capture(tmp_path / "c.duckdb", rows)
    m = _write_manifest(tmp_path / "m.json", [_entry(cap, "ON", "s")])
    with pytest.raises(VersionedVerdictAssemblyError):
        assemble_bundles(load_manifest(m), m)


def test_natural_key_dup_in_one_capture(tmp_path: Path) -> None:
    rows = _capture()
    rows.append(rows[0])  # exact duplicate of an existing natural key
    cap = _write_sat_capture(tmp_path / "c.duckdb", rows)
    m = _write_manifest(tmp_path / "m.json", [_entry(cap, "ON", "s")])
    with pytest.raises(VersionedVerdictAssemblyError):
        assemble_bundles(load_manifest(m), m)


# ---------------------------------------------------------------------------
# Hint identity (structural) + empty hint pass-through (scientific)
# ---------------------------------------------------------------------------


def test_hint_run_id_mismatch(tmp_path: Path) -> None:
    cap = _write_sat_capture(tmp_path / "c.duckdb", _capture(run_id="r"))
    hint = _write_hint_capture(
        tmp_path / "h.duckdb", [_hint_row(run_id="OTHER", seed=1)]
    )
    m = _write_manifest(tmp_path / "m.json", [_entry(cap, "ON", "s", hint)])
    with pytest.raises(VersionedVerdictAssemblyError):
        assemble_bundles(load_manifest(m), m)


def test_hint_seed_mismatch(tmp_path: Path) -> None:
    cap = _write_sat_capture(tmp_path / "c.duckdb", _capture(run_id="r", seed=1))
    hint = _write_hint_capture(tmp_path / "h.duckdb", [_hint_row(run_id="r", seed=2)])
    m = _write_manifest(tmp_path / "m.json", [_entry(cap, "ON", "s", hint)])
    with pytest.raises(VersionedVerdictAssemblyError):
        assemble_bundles(load_manifest(m), m)


def test_hint_natural_key_dup(tmp_path: Path) -> None:
    cap = _write_sat_capture(tmp_path / "c.duckdb", _capture(run_id="r", seed=1))
    dup = _hint_row(run_id="r", seed=1, tick=10)
    hint = _write_hint_capture(tmp_path / "h.duckdb", [dup, dup])
    m = _write_manifest(tmp_path / "m.json", [_entry(cap, "ON", "s", hint)])
    with pytest.raises(VersionedVerdictAssemblyError):
        assemble_bundles(load_manifest(m), m)


def test_empty_hint_capture_passes_through(tmp_path: Path) -> None:
    """An empty hint capture is scientific (V3 INVALID), not a structural error."""
    cap = _write_sat_capture(tmp_path / "c.duckdb", _capture(run_id="r", seed=1))
    hint = _write_hint_capture(tmp_path / "h.duckdb", [])
    m = _write_manifest(tmp_path / "m.json", [_entry(cap, "ON", "s", hint)])
    bundles, _ = assemble_bundles(load_manifest(m), m)
    assert len(bundles) == 1
    assert bundles[0].hint_rows == []  # passed through, not rejected


# ---------------------------------------------------------------------------
# Cross-bundle structural anomalies
# ---------------------------------------------------------------------------


def test_same_physical_capture_registered_twice(tmp_path: Path) -> None:
    cap = _write_sat_capture(tmp_path / "c.duckdb", _capture())
    m = _write_manifest(
        tmp_path / "m.json",
        [_entry(cap, "ON", "s1"), _entry(cap, "OFF", "s2")],
    )
    with pytest.raises(VersionedVerdictAssemblyError):
        assemble_bundles(load_manifest(m), m)


def test_duplicate_source_run_id_seed_arm(tmp_path: Path) -> None:
    a = _write_sat_capture(tmp_path / "a.duckdb", _capture(run_id="ra", seed=1))
    b = _write_sat_capture(tmp_path / "b.duckdb", _capture(run_id="rb", seed=1))
    m = _write_manifest(
        tmp_path / "m.json",
        [_entry(a, "ON", "shared"), _entry(b, "ON", "shared")],
    )
    with pytest.raises(VersionedVerdictAssemblyError):
        assemble_bundles(load_manifest(m), m)


def test_duplicate_arm_run_seed(tmp_path: Path) -> None:
    a = _write_sat_capture(tmp_path / "a.duckdb", _capture(run_id="same", seed=1))
    b = _write_sat_capture(tmp_path / "b.duckdb", _capture(run_id="same", seed=1))
    m = _write_manifest(
        tmp_path / "m.json",
        [_entry(a, "ON", "s1"), _entry(b, "ON", "s2")],
    )
    with pytest.raises(VersionedVerdictAssemblyError):
        assemble_bundles(load_manifest(m), m)


def test_on_off_population_mismatch(tmp_path: Path) -> None:
    on = _write_sat_capture(
        tmp_path / "on.duckdb",
        _capture(run_id="on", seed=1, individuals=("kant", "hume")),
    )
    off = _write_sat_capture(
        tmp_path / "off.duckdb", _capture(run_id="off", seed=1, individuals=("kant",))
    )
    m = _write_manifest(
        tmp_path / "m.json",
        [_entry(on, "ON", "shared"), _entry(off, "OFF", "shared")],
    )
    with pytest.raises(VersionedVerdictAssemblyError):
        assemble_bundles(load_manifest(m), m)


def test_sql_identifier_guard_in_assembler(tmp_path: Path) -> None:
    cap = _write_sat_capture(tmp_path / "c.duckdb", _capture())
    m = _write_manifest(tmp_path / "m.json", [_entry(cap, "ON", "s")])
    with pytest.raises(VersionedVerdictAssemblyError):
        assemble_bundles(load_manifest(m), m, schema="bad-schema")


# ---------------------------------------------------------------------------
# Happy path: run_id derived, pairing population matches, both arms returned
# ---------------------------------------------------------------------------


def test_assemble_pairs_replay_and_live(tmp_path: Path) -> None:
    """run_id derived from rows; matched ON/OFF (same population) assemble cleanly."""
    on = _write_sat_capture(tmp_path / "on.duckdb", _capture(run_id="ron", seed=1))
    off = _write_sat_capture(tmp_path / "off.duckdb", _capture(run_id="roff", seed=1))
    m = _write_manifest(
        tmp_path / "m.json",
        [_entry(on, "ON", "shared"), _entry(off, "OFF", "shared")],
        contrast_kind="live",
    )
    bundles, sources = assemble_bundles(load_manifest(m), m)
    assert {b.arm for b in bundles} == {"ON", "OFF"}
    on_bundle = next(b for b in bundles if b.arm == "ON")
    off_bundle = next(b for b in bundles if b.arm == "OFF")
    assert on_bundle.run_id == "ron"  # derived from the rows, not the manifest
    assert off_bundle.run_id == "roff"
    assert on_bundle.source_run_id == off_bundle.source_run_id == "shared"
    assert {s.arm for s in sources} == {"ON", "OFF"}
    assert all(s.sha256 for s in sources)


def test_relative_manifest_paths_resolve_against_manifest_dir(tmp_path: Path) -> None:
    """A relative ``capture`` resolves against the manifest dir, not the cwd (MED-1)."""
    sub = tmp_path / "sub"
    sub.mkdir()
    _write_sat_capture(sub / "c.duckdb", _capture())
    m = _write_manifest(
        sub / "m.json",
        [
            {
                "capture": "c.duckdb",
                "arm": "ON",
                "source_run_id": "s",
                "hint_capture": None,
            }
        ],
    )
    bundles, _ = assemble_bundles(load_manifest(m), m)
    assert len(bundles) == 1
