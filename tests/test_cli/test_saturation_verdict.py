"""CLI assembly coverage for ``saturation_verdict`` (ADR section 3.4).

CPU-only, synthetic multi-file fixtures: each test writes one small DuckDB **per
seed** through the real DDL, then drives ``main`` and asserts the verdict JSON the
CLI rendered. The 3-way decision itself is already covered by
``test_saturation_loader`` (the CLI calls the same ``score_saturation``); these
tests focus on what the CLI *adds* — multi-file union, read, provenance (sha256 /
row_count / seeds / max_tick), output shape, frozen-threshold echo, the exactly-3
boundary as observed end-to-end, and the ``--schema`` / ``--table`` SQL-identifier
guard.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path

import duckdb
import pytest

from erre_sandbox.cli.saturation_verdict import main
from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.saturation import constants as _c
from erre_sandbox.evidence.saturation.trace_ddl import (
    TABLE_NAME,
    SaturationTraceRow,
    bootstrap_saturation_trace_schema,
    column_names,
)

_FULL_TICKS = range(10, 30)  # post-warmup; T_run = 29 (>= 25), terminal = [25, 29]
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _channel(
    *,
    seed: int,
    key: str,
    floor: float,
    mod: float,
    ticks: Iterable[int] = _FULL_TICKS,
    individual: str = "kant",
    axis: str = "self",
    run_id: str = "r",
) -> list[SaturationTraceRow]:
    """One channel's rows; fingerprint tracks the floor value (constant -> no drop)."""
    return [
        SaturationTraceRow(
            run_id=run_id,
            seed=seed,
            individual_id=individual,
            axis=axis,
            key=key,
            tick=t,
            base_floor_value=floor,
            modulated_value=mod,
            floor_fingerprint_hash=f"fp{round(floor, 6)}",
            individual_layer_enabled=True,
        )
        for t in ticks
    ]


def _saturated_seed(seed: int, *, n: int = 6) -> list[SaturationTraceRow]:
    """n channels pinned at the cap (floor 0.5, modulated 0.65 -> magnitude 0.15)."""
    rows: list[SaturationTraceRow] = []
    for i in range(n):
        rows += _channel(seed=seed, key=f"k{i}", floor=0.5, mod=0.65)
    return rows


def _non_saturated_seed(seed: int, *, n: int = 6) -> list[SaturationTraceRow]:
    """n active channels with headroom (magnitude 0.05, cap_distance 0.10 > eta)."""
    rows: list[SaturationTraceRow] = []
    for i in range(n):
        rows += _channel(seed=seed, key=f"k{i}", floor=0.5, mod=0.55)
    return rows


def _short_seed(seed: int, *, n: int = 6) -> list[SaturationTraceRow]:
    """Saturated channels but T_run = 19 < 25 -> seed INVALID (t_run_below_min)."""
    rows: list[SaturationTraceRow] = []
    for i in range(n):
        rows += _channel(
            seed=seed, key=f"k{i}", floor=0.5, mod=0.65, ticks=range(10, 20)
        )
    return rows


def _write_capture(path: Path, rows: list[SaturationTraceRow]) -> Path:
    """Persist *rows* into a fresh DuckDB at *path* through the real DDL."""
    con = duckdb.connect(str(path))
    try:
        con.execute(f"CREATE SCHEMA {METRICS_SCHEMA}")
        bootstrap_saturation_trace_schema(con, METRICS_SCHEMA)
        cols = column_names()
        insert_sql = (
            f"INSERT INTO {METRICS_SCHEMA}.{TABLE_NAME} "  # noqa: S608 — static identifiers, test
            f"({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
        )
        for row in rows:
            con.execute(insert_sql, row.to_row())
    finally:
        con.close()
    return path


def _run_verdict(tmp_path: Path, captures: list[Path], run_id: str = "t") -> dict:
    """Drive the CLI over *captures* and return the parsed verdict JSON."""
    out = tmp_path / "verdict.json"
    argv: list[str] = []
    for cap in captures:
        argv += ["--capture", str(cap)]
    argv += ["--run-id", run_id, "--out", str(out)]
    rc = main(argv)
    assert rc == 0
    return json.loads(out.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 3-way verdict, observed end-to-end through the CLI
# ---------------------------------------------------------------------------


def test_cli_saturated_three_files(tmp_path: Path) -> None:
    caps = [
        _write_capture(tmp_path / f"run{i}.duckdb", _saturated_seed(seed))
        for i, seed in enumerate((1, 2, 3))
    ]
    payload = _run_verdict(tmp_path, caps)
    assert payload["verdict"] == "SATURATED"
    assert payload["n_valid_seeds"] == 3
    assert payload["median_sat_frac"] == 1.0
    assert {s["label"] for s in payload["seeds"]} == {"SATURATED"}


def test_cli_non_saturated_three_files(tmp_path: Path) -> None:
    caps = [
        _write_capture(tmp_path / f"run{i}.duckdb", _non_saturated_seed(seed))
        for i, seed in enumerate((1, 2, 3))
    ]
    payload = _run_verdict(tmp_path, caps)
    assert payload["verdict"] == "NON-SATURATED"
    assert payload["median_sat_frac"] == 0.0


def test_cli_mixed_labels_inconclusive(tmp_path: Path) -> None:
    caps = [
        _write_capture(tmp_path / "run0.duckdb", _saturated_seed(1)),
        _write_capture(tmp_path / "run1.duckdb", _non_saturated_seed(2)),
        _write_capture(tmp_path / "run2.duckdb", _non_saturated_seed(3)),
    ]
    payload = _run_verdict(tmp_path, caps)
    assert payload["verdict"] == "INCONCLUSIVE"


# ---------------------------------------------------------------------------
# exactly-3 boundary (Codex HIGH-2 / DA-IMPL-7)
# ---------------------------------------------------------------------------


def test_cli_four_agreeing_seeds_inconclusive(tmp_path: Path) -> None:
    """4 agreeing SATURATED seeds must NOT bind a verdict (exactly N=3)."""
    caps = [
        _write_capture(tmp_path / f"run{i}.duckdb", _saturated_seed(seed))
        for i, seed in enumerate((1, 2, 3, 4))
    ]
    payload = _run_verdict(tmp_path, caps)
    assert payload["verdict"] == "INCONCLUSIVE"
    assert "paired N=3 not met" in payload["notes"]


def test_cli_three_seeds_one_invalid_inconclusive(tmp_path: Path) -> None:
    """3 seeds, one with T_run < 25 -> INVALID seed -> INCONCLUSIVE verdict."""
    caps = [
        _write_capture(tmp_path / "run0.duckdb", _saturated_seed(1)),
        _write_capture(tmp_path / "run1.duckdb", _saturated_seed(2)),
        _write_capture(tmp_path / "run2.duckdb", _short_seed(3)),
    ]
    payload = _run_verdict(tmp_path, caps)
    assert payload["verdict"] == "INCONCLUSIVE"
    invalid = [s for s in payload["seeds"] if not s["valid"]]
    assert len(invalid) == 1
    assert invalid[0]["seed"] == 3
    assert invalid[0]["invalid_reason"] == "t_run_below_min"
    assert invalid[0]["label"] == "INVALID"


# ---------------------------------------------------------------------------
# Provenance + output shape + frozen-threshold echo
# ---------------------------------------------------------------------------


def test_cli_provenance_and_thresholds(tmp_path: Path) -> None:
    caps = [
        _write_capture(tmp_path / f"run{i}.duckdb", _saturated_seed(seed))
        for i, seed in enumerate((11, 22, 33))
    ]
    payload = _run_verdict(tmp_path, caps, run_id="prov-run")

    assert payload["run_id"] == "prov-run"
    assert payload["schema_version"] == "saturation-verdict-1"

    sources = payload["sources"]
    assert len(sources) == 3
    expected = list(zip(caps, (11, 22, 33), strict=True))
    for src, (cap, seed) in zip(sources, expected, strict=True):
        assert src["path"] == str(cap)
        assert _SHA256_RE.match(src["sha256"])
        assert src["row_count"] == 6 * len(_FULL_TICKS)  # 6 channels x 20 ticks
        assert src["seeds"] == [seed]
        assert src["max_tick"] == 29

    # Every frozen threshold must echo its constants value verbatim (Codex LOW-1):
    # table-driven so a future field added to FrozenThresholds without a constants
    # echo is caught here, and "no threshold was tuned after the result" is auditable.
    thr = payload["thresholds"]
    expected = {
        "max_total_modulation": _c.MAX_TOTAL_MODULATION,
        "fingerprint_precision": _c.FINGERPRINT_PRECISION,
        "epsilon_mod": _c.EPSILON_MOD,
        "eta_pinned": _c.ETA_PINNED,
        "slope_tol": _c.SLOPE_TOL,
        "w_term": _c.W_TERM,
        "t_warmup": _c.T_WARMUP,
        "t_run_min": _c.T_RUN_MIN,
        "terminal_presence_min": _c.TERMINAL_PRESENCE_MIN,
        "engagement_min": _c.ENGAGEMENT_MIN,
        "min_active_channels": _c.MIN_ACTIVE_CHANNELS,
        "drop_high": _c.DROP_HIGH,
        "transient_high": _c.TRANSIENT_HIGH,
        "theta_high": _c.THETA_HIGH,
        "theta_low": _c.THETA_LOW,
        "n_seeds": _c.N_SEEDS,
    }
    assert thr == expected

    seed_report = payload["seeds"][0]
    for field in (
        "engagement_rate",
        "drop_rate",
        "transient_active_rate",
        "gate_pass",
        "n_active",
        "n_saturated",
        "n_boundary_floor",
        "total_channels",
        "t_run",
    ):
        assert field in seed_report


def test_cli_default_out_path(tmp_path: Path) -> None:
    """No --out -> sidecar lands beside the first capture."""
    caps = [
        _write_capture(tmp_path / f"run{i}.duckdb", _saturated_seed(seed))
        for i, seed in enumerate((1, 2, 3))
    ]
    argv: list[str] = []
    for c in caps:
        argv += ["--capture", str(c)]
    argv += ["--run-id", "default-out"]
    rc = main(argv)
    assert rc == 0
    sidecar = caps[0].with_name(caps[0].name + ".saturation_verdict.json")
    assert sidecar.exists()
    assert json.loads(sidecar.read_text(encoding="utf-8"))["verdict"] == "SATURATED"


# ---------------------------------------------------------------------------
# SQL-identifier guard on --schema / --table
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_arg",
    [
        ["--schema", "metrics; DROP TABLE x"],
        ["--schema", "bad-schema"],
        ["--table", "t t"],
        ["--table", "1abc"],
    ],
)
def test_cli_rejects_non_identifier(tmp_path: Path, bad_arg: list[str]) -> None:
    cap = _write_capture(tmp_path / "run0.duckdb", _saturated_seed(1))
    with pytest.raises(SystemExit):
        main(["--capture", str(cap), "--run-id", "x", *bad_arg])


# ---------------------------------------------------------------------------
# --out / --capture collision guard (DA-HEV-1)
# ---------------------------------------------------------------------------


def test_cli_rejects_out_over_capture(tmp_path: Path) -> None:
    """--out aliasing an input capture must be refused (never overwrite the trace)."""
    cap = _write_capture(tmp_path / "run0.duckdb", _saturated_seed(1))
    with pytest.raises(SystemExit):
        main(["--capture", str(cap), "--run-id", "x", "--out", str(cap)])
    # The capture is still a readable DuckDB (not clobbered by the verdict JSON).
    con = duckdb.connect(str(cap), read_only=True)
    try:
        n = con.execute(
            f"SELECT count(*) FROM {METRICS_SCHEMA}.{TABLE_NAME}"  # noqa: S608 — static, test
        ).fetchone()
        assert n is not None
        assert n[0] == 6 * len(_FULL_TICKS)
    finally:
        con.close()


def test_cli_rejects_out_over_capture_relative(tmp_path: Path) -> None:
    """A relative --out that resolves to a capture is caught too (resolve-based)."""
    cap = _write_capture(tmp_path / "run0.duckdb", _saturated_seed(1))
    nested = tmp_path / "sub" / ".." / "run0.duckdb"
    with pytest.raises(SystemExit):
        main(["--capture", str(cap), "--run-id", "x", "--out", str(nested)])


def test_cli_rejects_out_tmp_over_capture(tmp_path: Path) -> None:
    """--out whose ``.tmp`` sibling aliases a capture is refused (Codex HIGH-1)."""
    cap = _write_capture(tmp_path / "v.json.tmp", _saturated_seed(1))
    with pytest.raises(SystemExit):
        main(
            ["--capture", str(cap), "--run-id", "x", "--out", str(tmp_path / "v.json")]
        )
    con = duckdb.connect(str(cap), read_only=True)
    try:
        n = con.execute(
            f"SELECT count(*) FROM {METRICS_SCHEMA}.{TABLE_NAME}"  # noqa: S608 — static, test
        ).fetchone()
        assert n is not None
        assert n[0] == 6 * len(_FULL_TICKS)
    finally:
        con.close()
