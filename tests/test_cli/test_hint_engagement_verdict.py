"""CLI assembly coverage for ``hint_engagement_verdict`` (instrument ADR §6).

CPU-only, synthetic multi-file fixtures: each test writes one small DuckDB through the
real DDL, then drives ``main`` and asserts the verdict JSON the CLI rendered. The
routing decision itself is owned by ``score_hint_engagement`` (the CLI calls it
verbatim); these
tests focus on what the CLI *adds* — multi-file pooling, read, provenance (sha256 /
row_count / seeds / run_ids / max_tick), output shape, frozen-threshold echo, the
seed-pool / run-id channel separation observed end-to-end, the ``--out`` ⇄ ``--capture``
collision guard (DA-HEV-1), and the ``--schema`` / ``--table`` SQL-identifier guard.

Unlike the saturation verdict CLI there is **no exactly-N gating**: the instrument pools
any number of seeds/runs, so each scenario builder targets one of the five ADR §6
routing verdicts directly.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import re
from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from erre_sandbox.cli.hint_engagement_verdict import main
from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.hint_engagement import constants as _c
from erre_sandbox.evidence.hint_engagement.trace_ddl import (
    TABLE_NAME,
    HintEngagementTraceRow,
    bootstrap_hint_engagement_trace_schema,
    column_names,
)

_WARMUP = _c.WARMUP_TICKS  # 5 — first eligible tick
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


# ---------------------------------------------------------------------------
# Row builders — every row is post-warmup, llm ok, exposure >= 1 (= eligible).
# ---------------------------------------------------------------------------


def _mk(
    tick: int,
    *,
    seed: int = 1,
    run_id: str = "r",
    individual: str = "kant",
    llm_status: str = "ok",
    exposed: int = 3,
    emitted: bool,
    disposition: str,
    axis: str | None = None,
    key: str | None = None,
    direction: str | None = None,
    step: float = 0.0,
    layer: bool = True,
) -> HintEngagementTraceRow:
    return HintEngagementTraceRow(
        run_id=run_id,
        seed=seed,
        individual_id=individual,
        tick=tick,
        llm_status=llm_status,
        exposed_entry_count=exposed,
        emitted=emitted,
        disposition=disposition,
        target_axis=axis,
        target_key=key,
        direction=direction,
        adopted_signed_step=step,
        individual_layer_enabled=layer,
    )


def _adopted(
    tick: int, key: str, step: float, *, seed: int = 1, run_id: str = "r"
) -> HintEngagementTraceRow:
    return _mk(
        tick,
        seed=seed,
        run_id=run_id,
        emitted=True,
        disposition="adopted",
        axis="self",
        key=key,
        direction="up" if step >= 0 else "down",
        step=step,
    )


def _reject(tick: int, gate: str) -> HintEngagementTraceRow:
    return _mk(
        tick,
        emitted=True,
        disposition=gate,
        axis="self",
        key="kr",
        direction="up",
        step=0.0,
    )


def _not_emitted(tick: int) -> HintEngagementTraceRow:
    return _mk(tick, emitted=False, disposition="not_emitted")


# ---------------------------------------------------------------------------
# Scenario builders — one per ADR §6 routing verdict.
# ---------------------------------------------------------------------------


def _all_healthy_rows(
    *, seed: int = 1, run_id: str = "r", n_channels: int = 8, reps: int = 3
) -> list[HintEngagementTraceRow]:
    """n_channels adopted channels, each with ``reps`` same-direction nudges."""
    t: Iterator[int] = itertools.count(_WARMUP)
    return [
        _adopted(next(t), f"k{ch}", 0.05, seed=seed, run_id=run_id)
        for ch in range(n_channels)
        for _ in range(reps)
    ]


def _emission_rare_rows() -> list[HintEngagementTraceRow]:
    """24 adopted (8x3) drowned by 220 not_emitted -> emission < 0.10."""
    t: Iterator[int] = itertools.count(_WARMUP)
    rows = [_adopted(next(t), f"k{ch}", 0.05) for ch in range(8) for _ in range(3)]
    rows += [_not_emitted(next(t)) for _ in range(220)]
    return rows  # n_emitted=24 (>=20), channels=8, emission=24/244≈0.098 < 0.10


def _adoption_rejected_rows() -> list[HintEngagementTraceRow]:
    """16 adopted (8 channels x 2) + 20 single-gate rejects (adoption 16/36 < 0.50)."""
    t: Iterator[int] = itertools.count(_WARMUP)
    rows = [_adopted(next(t), f"k{ch}", 0.05) for ch in range(8) for _ in range(2)]
    rows += [_reject(next(t), "rejected_no_change") for _ in range(20)]
    return rows  # n_emitted=36, channels=8, emission=1.0, adoption≈0.444 < 0.50


def _direction_inconsistent_rows() -> list[HintEngagementTraceRow]:
    """8 channels x [+,-,+] adopted — each cancels (|sum|/gross=0.33 < 0.60)."""
    t: Iterator[int] = itertools.count(_WARMUP)
    # n_emitted=24, channels=8, emission=adoption=1.0, direction=0 < 0.60
    return [
        _adopted(next(t), f"k{ch}", step)
        for ch in range(8)
        for step in (0.05, -0.05, 0.05)
    ]


def _stability_low_emitted_rows() -> list[HintEngagementTraceRow]:
    """8 channels x 2 adopted — channels=8 but n_emitted=16 < N_MIN(20)."""
    t: Iterator[int] = itertools.count(_WARMUP)
    return [_adopted(next(t), f"k{ch}", 0.05) for ch in range(8) for _ in range(2)]


def _stability_low_channels_rows() -> list[HintEngagementTraceRow]:
    """3 channels x 8 adopted — n_emitted=24 but channels=3 < CHANNEL_FLOOR(8)."""
    t: Iterator[int] = itertools.count(_WARMUP)
    return [_adopted(next(t), f"k{ch}", 0.05) for ch in range(3) for _ in range(8)]


def _boundary_tie_rows() -> list[HintEngagementTraceRow]:
    """emission_rate exactly 0.10 (20 emitted / 200 eligible) -> boundary tie."""
    t: Iterator[int] = itertools.count(_WARMUP)
    rows = [  # 4*3 + 4*2 = 20 adopted across 8 channels
        _adopted(next(t), f"k{ch}", 0.05)
        for ch in range(8)
        for _ in range(3 if ch < 4 else 2)
    ]
    rows += [_not_emitted(next(t)) for _ in range(180)]
    return rows  # n_emitted=20, channels=8, emission=20/200=0.10 == THETA_E


def _provenance_false_rows() -> list[HintEngagementTraceRow]:
    """A single provenance-false row short-circuits the whole result."""
    return [_mk(_WARMUP, emitted=False, disposition="not_emitted", layer=False)]


# ---------------------------------------------------------------------------
# Capture I/O helpers.
# ---------------------------------------------------------------------------


def _write_capture(path: Path, rows: list[HintEngagementTraceRow]) -> Path:
    """Persist *rows* into a fresh DuckDB at *path* through the real DDL."""
    con = duckdb.connect(str(path))
    try:
        con.execute(f"CREATE SCHEMA {METRICS_SCHEMA}")
        bootstrap_hint_engagement_trace_schema(con, METRICS_SCHEMA)
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
# Routing verdicts, observed end-to-end through the CLI.
# ---------------------------------------------------------------------------


def test_cli_all_healthy(tmp_path: Path) -> None:
    cap = _write_capture(tmp_path / "run.duckdb", _all_healthy_rows())
    payload = _run_verdict(tmp_path, [cap])
    assert payload["verdict"] == "STATE_ALL_HEALTHY"
    assert payload["emission_rate"] == 1.0
    assert payload["adoption_rate"] == 1.0
    assert payload["adopted_direction_consistency_rate"] == 1.0
    assert payload["n_eligible_channels"] == 8


def test_cli_emission_rare(tmp_path: Path) -> None:
    cap = _write_capture(tmp_path / "run.duckdb", _emission_rare_rows())
    payload = _run_verdict(tmp_path, [cap])
    assert payload["verdict"] == "STATE_A_EMISSION_RARE"
    assert payload["emission_rate"] < _c.THETA_E


def test_cli_adoption_rejected(tmp_path: Path) -> None:
    cap = _write_capture(tmp_path / "run.duckdb", _adoption_rejected_rows())
    payload = _run_verdict(tmp_path, [cap])
    assert payload["verdict"] == "STATE_B_ADOPTION_REJECTED"
    assert payload["adoption_rate"] < _c.THETA_A
    assert payload["dominant_gate"] == "rejected_no_change"
    assert "dominant_gate=rejected_no_change" in payload["notes"]


def test_cli_direction_inconsistent(tmp_path: Path) -> None:
    cap = _write_capture(tmp_path / "run.duckdb", _direction_inconsistent_rows())
    payload = _run_verdict(tmp_path, [cap])
    assert payload["verdict"] == "STATE_C_DIRECTION_INCONSISTENT"
    assert payload["adopted_direction_consistency_rate"] < _c.THETA_DIR


def test_cli_stability_low_emitted(tmp_path: Path) -> None:
    cap = _write_capture(tmp_path / "run.duckdb", _stability_low_emitted_rows())
    payload = _run_verdict(tmp_path, [cap])
    assert payload["verdict"] == "INSTRUMENT_INCONCLUSIVE"
    assert payload["n_emitted"] == 16
    assert "stability gate" in payload["notes"]


def test_cli_stability_low_channels(tmp_path: Path) -> None:
    cap = _write_capture(tmp_path / "run.duckdb", _stability_low_channels_rows())
    payload = _run_verdict(tmp_path, [cap])
    assert payload["verdict"] == "INSTRUMENT_INCONCLUSIVE"
    assert payload["n_eligible_channels"] == 3
    assert "stability gate" in payload["notes"]


def test_cli_boundary_tie_inconclusive(tmp_path: Path) -> None:
    cap = _write_capture(tmp_path / "run.duckdb", _boundary_tie_rows())
    payload = _run_verdict(tmp_path, [cap])
    assert payload["verdict"] == "INSTRUMENT_INCONCLUSIVE"
    assert payload["emission_rate"] == _c.THETA_E
    assert "boundary tie" in payload["notes"]


def test_cli_provenance_false_inconclusive(tmp_path: Path) -> None:
    cap = _write_capture(tmp_path / "run.duckdb", _provenance_false_rows())
    payload = _run_verdict(tmp_path, [cap])
    assert payload["verdict"] == "INSTRUMENT_INCONCLUSIVE"
    assert payload["notes"] == "provenance_false"


# ---------------------------------------------------------------------------
# Seed pooling + run-id channel separation (DA-EII-12 / DA-HEV-4).
# ---------------------------------------------------------------------------


def test_cli_run_id_channel_separation(tmp_path: Path) -> None:
    """Same seed, different run_id, identical keys: channels must NOT merge.

    Each capture carries 4 channels (k0..k3). If the scorer keyed channels by
    ``(seed, axis, key)`` they would collapse to 4 (< CHANNEL_FLOOR -> INCONCLUSIVE);
    keyed by full run identity they stay 8 -> STATE_ALL_HEALTHY. Asserting both the
    channel count and the verdict pins the run-id separation end-to-end.
    """
    cap_a = _write_capture(
        tmp_path / "a.duckdb",
        _all_healthy_rows(seed=7, run_id="rA", n_channels=4),
    )
    cap_b = _write_capture(
        tmp_path / "b.duckdb",
        _all_healthy_rows(seed=7, run_id="rB", n_channels=4),
    )
    payload = _run_verdict(tmp_path, [cap_a, cap_b])
    assert payload["n_eligible_channels"] == 8
    assert payload["verdict"] == "STATE_ALL_HEALTHY"
    assert payload["seeds"] == [7]
    assert payload["sources"][0]["run_ids"] == ["rA"]
    assert payload["sources"][1]["run_ids"] == ["rB"]


def test_cli_cross_seed_pooling(tmp_path: Path) -> None:
    """The scorer pools eligible ticks/channels across seeds (not per-seed scored).

    Two different seeds, 4 channels / 12 emitted each: each capture alone fails the
    stability gate (channels=4 < CHANNEL_FLOOR, n_emitted=12 < N_MIN -> INCONCLUSIVE),
    but the union reaches 8 channels / 24 emitted -> STATE_ALL_HEALTHY. This pins the
    pooling semantics so a per-seed-scoring/agreement regression is caught (DA-HEV-7).
    """
    cap_a = _write_capture(
        tmp_path / "a.duckdb", _all_healthy_rows(seed=1, n_channels=4)
    )
    cap_b = _write_capture(
        tmp_path / "b.duckdb", _all_healthy_rows(seed=2, n_channels=4)
    )
    assert _run_verdict(tmp_path, [cap_a])["verdict"] == "INSTRUMENT_INCONCLUSIVE"
    assert _run_verdict(tmp_path, [cap_b])["verdict"] == "INSTRUMENT_INCONCLUSIVE"
    payload = _run_verdict(tmp_path, [cap_a, cap_b])
    assert payload["verdict"] == "STATE_ALL_HEALTHY"
    assert payload["n_eligible_channels"] == 8
    assert payload["n_emitted"] == 24
    assert payload["seeds"] == [1, 2]


# ---------------------------------------------------------------------------
# Provenance + output shape + frozen-threshold echo.
# ---------------------------------------------------------------------------


def test_cli_provenance_and_thresholds(tmp_path: Path) -> None:
    caps = [
        _write_capture(tmp_path / f"run{i}.duckdb", _all_healthy_rows(seed=seed))
        for i, seed in enumerate((11, 22, 33))
    ]
    payload = _run_verdict(tmp_path, caps, run_id="prov-run")

    assert payload["run_id"] == "prov-run"
    assert payload["schema_version"] == "hint-engagement-verdict-1"

    sources = payload["sources"]
    assert len(sources) == 3
    for src, (cap, seed) in zip(
        sources, zip(caps, (11, 22, 33), strict=True), strict=True
    ):
        assert src["path"] == str(cap)
        assert _SHA256_RE.match(src["sha256"])
        # Exact identity, not just shape: echoed hash == the capture's bytes (LOW-1).
        assert src["sha256"] == hashlib.sha256(cap.read_bytes()).hexdigest()
        assert src["row_count"] == 24  # 8 channels x 3 reps
        assert src["seeds"] == [seed]
        assert src["run_ids"] == ["r"]
        assert src["max_tick"] == _WARMUP + 23  # ticks 5..28

    # Every frozen threshold must echo its constants value verbatim: table-driven so a
    # future field added to FrozenThresholds without a constants echo is caught here,
    # and "no threshold was tuned after the result" stays auditable (ADR §8).
    expected = {
        "warmup_ticks": _c.WARMUP_TICKS,
        "n_min": _c.N_MIN,
        "channel_floor": _c.CHANNEL_FLOOR,
        "theta_e": _c.THETA_E,
        "theta_a": _c.THETA_A,
        "theta_dir": _c.THETA_DIR,
        "adopted_channel_min": _c.ADOPTED_CHANNEL_MIN,
    }
    assert payload["thresholds"] == expected

    for field in (
        "emission_rate",
        "adoption_rate",
        "adopted_direction_consistency_rate",
        "per_gate_rejection_share",
        "dominant_gate",
        "n_eligible_ticks",
        "n_emitted",
        "n_adopted",
        "n_rejected",
        "n_eligible_channels",
        "notes",
    ):
        assert field in payload


def test_cli_default_out_path(tmp_path: Path) -> None:
    """No --out -> sidecar lands beside the first capture."""
    cap = _write_capture(tmp_path / "run.duckdb", _all_healthy_rows())
    rc = main(["--capture", str(cap), "--run-id", "default-out"])
    assert rc == 0
    sidecar = cap.with_name(cap.name + ".hint_engagement_verdict.json")
    assert sidecar.exists()
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["verdict"] == "STATE_ALL_HEALTHY"


# ---------------------------------------------------------------------------
# --out / --capture collision guard (DA-HEV-1).
# ---------------------------------------------------------------------------


def test_cli_rejects_out_over_capture(tmp_path: Path) -> None:
    """--out aliasing an input capture must be refused (never overwrite the trace)."""
    cap = _write_capture(tmp_path / "run.duckdb", _all_healthy_rows())
    with pytest.raises(SystemExit):
        main(["--capture", str(cap), "--run-id", "x", "--out", str(cap)])
    # The capture is still a readable DuckDB (not clobbered by the verdict JSON).
    con = duckdb.connect(str(cap), read_only=True)
    try:
        n = con.execute(
            f"SELECT count(*) FROM {METRICS_SCHEMA}.{TABLE_NAME}"  # noqa: S608 — static, test
        ).fetchone()
        assert n is not None
        assert n[0] == 24
    finally:
        con.close()


def test_cli_rejects_out_over_capture_relative(tmp_path: Path) -> None:
    """A relative --out that resolves to a capture is caught too (resolve-based)."""
    cap = _write_capture(tmp_path / "run.duckdb", _all_healthy_rows())
    nested = tmp_path / "sub" / ".." / "run.duckdb"
    with pytest.raises(SystemExit):
        main(["--capture", str(cap), "--run-id", "x", "--out", str(nested)])


def test_cli_rejects_out_tmp_over_capture(tmp_path: Path) -> None:
    """--out whose ``.tmp`` sibling aliases a capture is refused (Codex HIGH-1).

    The writer's intermediate ``<out>.tmp`` write would clobber the capture before the
    final rename, even though the final ``--out`` path differs.
    """
    cap = _write_capture(tmp_path / "v.json.tmp", _all_healthy_rows())
    with pytest.raises(SystemExit):
        main(
            ["--capture", str(cap), "--run-id", "x", "--out", str(tmp_path / "v.json")]
        )
    # The capture (= the would-be temp path) is intact, not clobbered by the temp write.
    con = duckdb.connect(str(cap), read_only=True)
    try:
        n = con.execute(
            f"SELECT count(*) FROM {METRICS_SCHEMA}.{TABLE_NAME}"  # noqa: S608 — static, test
        ).fetchone()
        assert n is not None
        assert n[0] == 24
    finally:
        con.close()


# ---------------------------------------------------------------------------
# SQL-identifier guard on --schema / --table.
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
    cap = _write_capture(tmp_path / "run.duckdb", _all_healthy_rows())
    with pytest.raises(SystemExit):
        main(["--capture", str(cap), "--run-id", "x", *bad_arg])
