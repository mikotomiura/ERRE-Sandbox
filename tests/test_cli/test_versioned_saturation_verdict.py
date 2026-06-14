"""CLI assembly + two-layer-exit coverage for ``versioned_saturation_verdict``.

CPU-only synthetic DuckDB + JSON manifest fixtures. The 3-way decision is covered by
``test_versioned_saturation_loader`` and the F4 validation by
``test_versioned_verdict_assembler``; these tests focus on what the CLI *adds* — the
manifest → assemble → score → sidecar pipeline, the **F5 two-layer exit** (structural
anomaly = non-zero + no sidecar; scientific outcome = sidecar + exit 0), provenance, the
§3.0' threshold echo, the exactly-3 boundary observed end-to-end, V3 wiring through the
manifest, and the ``--out`` collision guard.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from pathlib import Path

import duckdb
import pytest

from erre_sandbox.cli.versioned_saturation_verdict import main
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
from erre_sandbox.evidence.saturation import constants as _c
from erre_sandbox.evidence.saturation import versioned_constants as _vc
from erre_sandbox.evidence.saturation.trace_ddl import (
    TABLE_NAME,
    SaturationTraceRow,
    bootstrap_saturation_trace_schema,
    column_names,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FloatOrFn = float | Callable[[int], float]


# ---------------------------------------------------------------------------
# Row + retention fixtures (mirrors test_versioned_saturation_loader)
# ---------------------------------------------------------------------------


def _val(spec: _FloatOrFn, tick: int) -> float:
    return spec(tick) if callable(spec) else spec


def _chan(
    *,
    seed: int,
    key: str,
    run_id: str,
    floor: _FloatOrFn,
    mod: _FloatOrFn,
    ticks: Iterable[int] = range(10, 30),
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


def _floor_stepping(t: int) -> float:
    return 0.50 + 0.001 * t


def _on_pass_seed(
    seed: int, run_id: str, *, n: int = 6, carry_until: int = 18
) -> list[SaturationTraceRow]:
    rows: list[SaturationTraceRow] = []
    for i in range(n):
        rows += _chan(
            seed=seed,
            key=f"k{i}",
            run_id=run_id,
            floor=_floor_stepping,
            mod=lambda t, _c=carry_until: (
                _floor_stepping(t) + (0.10 if t <= _c else 0.0)
            ),
        )
    return rows


def _off_trial_seed(seed: int, run_id: str, *, n: int = 6) -> list[SaturationTraceRow]:
    rows: list[SaturationTraceRow] = []
    for i in range(n):
        rows += _chan(
            seed=seed,
            key=f"k{i}",
            run_id=run_id,
            floor=_floor_stepping,
            mod=lambda t: _floor_stepping(t) + (0.10 if t % 2 == 0 else 0.0),
        )
    return rows


def _adopted_strengthen_hints(
    seed: int, run_id: str, *, carry_until: int = 18
) -> list[HintEngagementTraceRow]:
    return [
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
        for t in range(10, carry_until + 1)
    ]


# ---------------------------------------------------------------------------
# Capture + manifest writers
# ---------------------------------------------------------------------------


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
    path: Path, entries: list[dict[str, object]], *, contrast_kind: str = "live"
) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": "versioned-verdict-manifest-1",
                "contrast_kind": contrast_kind,
                "envelope": {"personas": ["kant"], "model": "qwen3:8b"},
                "entries": entries,
            }
        ),
        encoding="utf-8",
    )
    return path


def _full_pass_manifest(tmp_path: Path, *, contrast_kind: str = "live") -> Path:
    """3 matched ON/OFF pairs (shared source_run_id), V3 complete -> conclusive."""
    entries: list[dict[str, object]] = []
    for seed in (1, 2, 3):
        on_run = "on" if contrast_kind == "replay" else f"on{seed}"
        off_run = "on" if contrast_kind == "replay" else f"off{seed}"
        on_cap = _write_sat_capture(
            tmp_path / f"on{seed}.duckdb", _on_pass_seed(seed, on_run)
        )
        off_cap = _write_sat_capture(
            tmp_path / f"off{seed}.duckdb", _off_trial_seed(seed, off_run)
        )
        hint_cap = _write_hint_capture(
            tmp_path / f"hint{seed}.duckdb", _adopted_strengthen_hints(seed, on_run)
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
    return _write_manifest(
        tmp_path / "manifest.json", entries, contrast_kind=contrast_kind
    )


def _run(tmp_path: Path, manifest: Path, *, run_id: str = "t") -> tuple[int, Path]:
    out = tmp_path / "verdict.json"
    rc = main(["--manifest", str(manifest), "--run-id", run_id, "--out", str(out)])
    return rc, out


# ---------------------------------------------------------------------------
# Scientific outcome -> sidecar + exit 0
# ---------------------------------------------------------------------------


def test_cli_full_pass_live(tmp_path: Path) -> None:
    rc, out = _run(tmp_path, _full_pass_manifest(tmp_path, contrast_kind="live"))
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["on_verdict"] == "NON-SATURATED"
    assert payload["off_control_complete"] is True
    assert payload["contrast_kind"] == "live"
    assert len(payload["on_partitions"]) == 3
    assert all(p["gate_pass"] for p in payload["on_partitions"])
    assert all(p["non_inferiority"] == "PASS" for p in payload["on_partitions"])


def test_cli_full_pass_replay(tmp_path: Path) -> None:
    rc, out = _run(tmp_path, _full_pass_manifest(tmp_path, contrast_kind="replay"))
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["on_verdict"] == "NON-SATURATED"
    assert payload["contrast_kind"] == "replay"


def test_cli_provenance_and_threshold_echo(tmp_path: Path) -> None:
    rc, out = _run(tmp_path, _full_pass_manifest(tmp_path), run_id="prov")
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))

    assert payload["run_id"] == "prov"
    assert payload["schema_version"] == "versioned-saturation-verdict-1"
    assert payload["scorer_contract_version"] == "versioned-loader-1"
    assert _SHA256_RE.match(payload["manifest_sha256"])
    assert payload["manifest"]["contrast_kind"] == "live"

    sources = payload["sources"]
    assert len(sources) == 6  # 3 ON + 3 OFF
    on_sources = [s for s in sources if s["arm"] == "ON"]
    assert len(on_sources) == 3
    for s in sources:
        assert _SHA256_RE.match(s["sha256"])
        assert s["arm"] in {"ON", "OFF"}
        assert s["source_run_id"].startswith("src")
        assert s["run_id"]
        assert s["row_count"] > 0
        assert s["n_individuals"] == 1
        assert s["file_size_bytes"] > 0
    for s in on_sources:
        assert _SHA256_RE.match(s["hint_sha256"])
        assert s["hint_row_count"] == 9  # ticks 10..18

    thr = payload["thresholds"]
    expected = {
        "rho_retain_min": _vc.RHO_RETAIN_MIN,
        "min_d_fp": _vc.MIN_D_FP,
        "crossfp_channel_min": _vc.CROSSFP_CHANNEL_MIN,
        "retained_channel_min": _vc.RETAINED_CHANNEL_MIN,
        "disappear_margin": _vc.DISAPPEAR_MARGIN,
        "h_safety": _vc.H_SAFETY,
        "cancel_high": _vc.CANCEL_HIGH,
        "engagement_min": _c.ENGAGEMENT_MIN,
        "min_active_channels": _c.MIN_ACTIVE_CHANNELS,
        "transient_high": _c.TRANSIENT_HIGH,
        "theta_high": _c.THETA_HIGH,
        "theta_low": _c.THETA_LOW,
        "n_seeds": _c.N_SEEDS,
        "epsilon_mod": _c.EPSILON_MOD,
        "t_warmup": _c.T_WARMUP,
        "max_total_modulation": _c.MAX_TOTAL_MODULATION,
    }
    assert thr == expected


def test_cli_v3_not_evaluated_without_hint(tmp_path: Path) -> None:
    """ON with hint_capture=null -> V3 NOT_EVALUATED -> gate fail -> INCONCLUSIVE."""
    entries: list[dict[str, object]] = []
    for seed in (1, 2, 3):
        on_cap = _write_sat_capture(
            tmp_path / f"on{seed}.duckdb", _on_pass_seed(seed, f"on{seed}")
        )
        off_cap = _write_sat_capture(
            tmp_path / f"off{seed}.duckdb", _off_trial_seed(seed, f"off{seed}")
        )
        entries.append(
            {
                "capture": str(on_cap),
                "arm": "ON",
                "source_run_id": f"src{seed}",
                "hint_capture": None,
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
    m = _write_manifest(tmp_path / "m.json", entries)
    rc, out = _run(tmp_path, m)
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["on_verdict"] == "INCONCLUSIVE"
    assert {p["v3_status"] for p in payload["on_partitions"]} == {"NOT_EVALUATED"}
    assert all(not p["gate_pass"] for p in payload["on_partitions"])


def test_cli_four_on_seeds_inconclusive(tmp_path: Path) -> None:
    """4 ON seeds must not bind a verdict (exactly N=3) -> sidecar + exit 0."""
    m = _full_pass_manifest(tmp_path)
    extra_on = _write_sat_capture(tmp_path / "on4.duckdb", _on_pass_seed(4, "on4"))
    extra_off = _write_sat_capture(tmp_path / "off4.duckdb", _off_trial_seed(4, "off4"))
    extra_hint = _write_hint_capture(
        tmp_path / "hint4.duckdb", _adopted_strengthen_hints(4, "on4")
    )
    manifest = json.loads(m.read_text(encoding="utf-8"))
    manifest["entries"] += [
        {
            "capture": str(extra_on),
            "arm": "ON",
            "source_run_id": "src4",
            "hint_capture": str(extra_hint),
        },
        {
            "capture": str(extra_off),
            "arm": "OFF",
            "source_run_id": "src4",
            "hint_capture": None,
        },
    ]
    m.write_text(json.dumps(manifest), encoding="utf-8")
    rc, out = _run(tmp_path, m)
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["on_verdict"] == "INCONCLUSIVE"
    assert "paired N=3 not met" in payload["notes"]


def test_cli_default_out_path(tmp_path: Path) -> None:
    m = _full_pass_manifest(tmp_path)
    rc = main(["--manifest", str(m), "--run-id", "d"])
    assert rc == 0
    sidecar = (tmp_path / "on1.duckdb").with_name(
        "on1.duckdb.versioned_saturation_verdict.json"
    )
    assert sidecar.exists()


# ---------------------------------------------------------------------------
# Structural anomaly -> non-zero exit + NO sidecar (F5)
# ---------------------------------------------------------------------------


def test_cli_bad_manifest_exit2_no_sidecar(tmp_path: Path) -> None:
    bad = tmp_path / "m.json"
    bad.write_text("{broken", encoding="utf-8")
    out = tmp_path / "verdict.json"
    rc = main(["--manifest", str(bad), "--run-id", "x", "--out", str(out)])
    assert rc == 2
    assert not out.exists()


def test_cli_mixed_run_id_exit2_no_sidecar(tmp_path: Path) -> None:
    rows = _on_pass_seed(1, "a") + _on_pass_seed(1, "b")  # two run_ids in one capture
    cap = _write_sat_capture(tmp_path / "c.duckdb", rows)
    m = _write_manifest(
        tmp_path / "m.json",
        [
            {
                "capture": str(cap),
                "arm": "ON",
                "source_run_id": "s",
                "hint_capture": None,
            }
        ],
    )
    out = tmp_path / "verdict.json"
    rc = main(["--manifest", str(m), "--run-id", "x", "--out", str(out)])
    assert rc == 2
    assert not out.exists()


def test_cli_population_mismatch_exit2_no_sidecar(tmp_path: Path) -> None:
    on_rows = _on_pass_seed(1, "on") + _chan(
        seed=1,
        key="k0",
        run_id="on",
        individual="hume",
        floor=_floor_stepping,
        mod=lambda t: _floor_stepping(t) + 0.10,
    )
    on = _write_sat_capture(tmp_path / "on.duckdb", on_rows)
    off = _write_sat_capture(tmp_path / "off.duckdb", _off_trial_seed(1, "off"))
    m = _write_manifest(
        tmp_path / "m.json",
        [
            {
                "capture": str(on),
                "arm": "ON",
                "source_run_id": "s",
                "hint_capture": None,
            },
            {
                "capture": str(off),
                "arm": "OFF",
                "source_run_id": "s",
                "hint_capture": None,
            },
        ],
    )
    out = tmp_path / "verdict.json"
    rc = main(["--manifest", str(m), "--run-id", "x", "--out", str(out)])
    assert rc == 2
    assert not out.exists()


# ---------------------------------------------------------------------------
# Collision guard + SQL-identifier guard
# ---------------------------------------------------------------------------


def test_cli_rejects_out_over_capture(tmp_path: Path) -> None:
    cap = _write_sat_capture(tmp_path / "on1.duckdb", _on_pass_seed(1, "on1"))
    m = _write_manifest(
        tmp_path / "m.json",
        [
            {
                "capture": str(cap),
                "arm": "ON",
                "source_run_id": "s",
                "hint_capture": None,
            }
        ],
    )
    with pytest.raises(SystemExit):
        main(["--manifest", str(m), "--run-id", "x", "--out", str(cap)])
    # capture still readable (not clobbered)
    con = duckdb.connect(str(cap), read_only=True)
    try:
        n = con.execute(
            f"SELECT count(*) FROM {METRICS_SCHEMA}.{TABLE_NAME}"  # noqa: S608 — static, test
        ).fetchone()
        assert n is not None
        assert n[0] > 0
    finally:
        con.close()


def test_cli_rejects_out_over_manifest(tmp_path: Path) -> None:
    cap = _write_sat_capture(tmp_path / "on1.duckdb", _on_pass_seed(1, "on1"))
    m = _write_manifest(
        tmp_path / "m.json",
        [
            {
                "capture": str(cap),
                "arm": "ON",
                "source_run_id": "s",
                "hint_capture": None,
            }
        ],
    )
    with pytest.raises(SystemExit):
        main(["--manifest", str(m), "--run-id", "x", "--out", str(m)])


@pytest.mark.parametrize("bad", [["--schema", "bad-schema"], ["--table", "t t"]])
def test_cli_rejects_non_identifier(tmp_path: Path, bad: list[str]) -> None:
    cap = _write_sat_capture(tmp_path / "on1.duckdb", _on_pass_seed(1, "on1"))
    m = _write_manifest(
        tmp_path / "m.json",
        [
            {
                "capture": str(cap),
                "arm": "ON",
                "source_run_id": "s",
                "hint_capture": None,
            }
        ],
    )
    with pytest.raises(SystemExit):
        main(["--manifest", str(m), "--run-id", "x", *bad])
