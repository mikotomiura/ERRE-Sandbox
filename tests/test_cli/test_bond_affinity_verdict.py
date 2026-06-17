"""CLI assembly coverage for ``bond_affinity_verdict`` (verdict mode + Phase 0).

CPU-only synthetic 12-run matrix: each cell is one small DuckDB (bond-affinity +
saturation traces) plus its ``.capture.json`` sidecar carrying the matrix identity
(``seed`` / ``stm_carry_arm`` / ``replicate_id``). The routing itself is covered by
``test_bond_affinity_loader`` / ``test_bond_affinity_captures``; this test focuses on
what the CLI *adds* — multi-file read via :func:`read_bond_capture`, sidecar-driven
provenance, the frozen-§1-threshold echo, the verdict-over-capture collision guard, an
end-to-end (i)-LEANING render, and the Phase 0 stop-gate token.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import duckdb
import pytest

from erre_sandbox.cli.bond_affinity_verdict import main
from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.capture_sidecar import (
    SidecarV1,
    sidecar_path_for,
    write_sidecar_atomic,
)
from erre_sandbox.evidence.relational import constants as _c
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

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SEEDS = (1, 2, 3)
_TICK = 10


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
    abs_aff: float,
    n: int = 10,
    exposure: bool = True,
    provenance: bool = True,
) -> Path:
    """Write one matrix cell (bond + saturation traces) + its sidecar; return path."""
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
                affinity=abs_aff,
                ichigo_ichie_count=6,
                last_interaction_tick=_TICK,
                last_interaction_zone=Zone.STUDY,
            )
            for i in range(n)
        ]
        for row in build_bond_affinity_trace_rows(
            bonds,
            run_id=run_id,
            seed=seed,
            individual_id="kant",
            tick=_TICK,
            individual_layer_enabled=provenance,
        ):
            _insert(con, _BOND_TABLE, _bond_columns(), row.to_row())
        if exposure:
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
                    tick=_TICK,
                    base_floor_value=0.5,
                    modulated_value=0.65,
                    floor_fingerprint_hash="h",
                    individual_layer_enabled=provenance,
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
            total_rows=n + (1 if exposure else 0),
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
            stm_carry_arm=arm.lower(),  # type: ignore[arg-type]
            replicate_id=replicate_id,
        ),
    )
    return duckdb_path


def _i_leaning_matrix(tmp_path: Path) -> list[Path]:
    """A 12-run matrix engineered to route (i)-LEANING (ratio path)."""
    paths: list[Path] = []
    for seed in _SEEDS:
        paths.append(
            _write_cell(tmp_path, seed=seed, arm="ON", replicate_id=0, abs_aff=0.44)
        )
        paths.append(
            _write_cell(tmp_path, seed=seed, arm="OFF", replicate_id=0, abs_aff=0.20)
        )
        paths.append(
            _write_cell(tmp_path, seed=seed, arm="OFF", replicate_id=1, abs_aff=0.16)
        )
        paths.append(
            _write_cell(tmp_path, seed=seed, arm="ON", replicate_id=1, abs_aff=0.44)
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


def test_cli_i_leaning_end_to_end(tmp_path: Path) -> None:
    payload = _run(tmp_path, _i_leaning_matrix(tmp_path), run_id="bond-run")
    assert payload["verdict"] == "(i)-LEANING"
    assert payload["run_id"] == "bond-run"
    assert payload["schema_version"] == "bond-affinity-verdict-1"
    assert sorted(payload["paired_seeds"]) == [1, 2, 3]
    assert payload["magnitude_ok"] is True
    assert payload["rank_ok"] is True
    assert payload["on_noise_ok"] is True
    assert len(payload["cells"]) == 12


def test_cli_provenance_and_thresholds(tmp_path: Path) -> None:
    payload = _run(tmp_path, _i_leaning_matrix(tmp_path))
    sources = payload["sources"]
    assert len(sources) == 12
    for src in sources:
        assert _SHA256_RE.match(src["sha256"])
        assert src["seed"] in _SEEDS
        assert src["arm"] in ("ON", "OFF")  # normalised from sidecar "on"/"off"
        assert src["replicate_id"] in (0, 1)
        assert src["bond_row_count"] == 10
        assert src["saturation_row_count"] == 1

    thr = payload["thresholds"]
    expected = {
        "belief_threshold": _c.BELIEF_THRESHOLD,
        "belief_min_interactions": _c.BELIEF_MIN_INTERACTIONS,
        "eps_band_lo": _c.EPS_BAND_LO,
        "cap_offset": _c.CAP_OFFSET,
        "cap_saturation_tol": _c.CAP_SATURATION_TOL,
        "r_min_bond": _c.R_MIN_BOND,
        "degenerate_gap_floor": _c.DEGENERATE_GAP_FLOOR,
        "on_noise_factor": _c.ON_NOISE_FACTOR,
        "min_near_miss_n": _c.MIN_NEAR_MISS_N,
        "min_paired_seeds": _c.MIN_PAIRED_SEEDS,
        "slope_window": _c.SLOPE_WINDOW,
    }
    assert thr == expected


def test_cli_default_out_path(tmp_path: Path) -> None:
    caps = _i_leaning_matrix(tmp_path)
    argv: list[str] = []
    for c in caps:
        argv += ["--capture", str(c)]
    argv += ["--run-id", "default-out"]
    assert main(argv) == 0
    sidecar = caps[0].with_name(caps[0].name + ".bond_affinity_verdict.json")
    assert sidecar.exists()


def test_cli_rejects_out_over_capture(tmp_path: Path) -> None:
    caps = _i_leaning_matrix(tmp_path)
    with pytest.raises(SystemExit):
        main(["--capture", str(caps[0]), "--run-id", "x", "--out", str(caps[0])])


def test_cli_rejects_out_over_capture_sidecar(tmp_path: Path) -> None:
    """--out resolving to a capture's sidecar is refused (Codex MEDIUM)."""
    cap = _write_cell(tmp_path, seed=1, arm="ON", replicate_id=0, abs_aff=0.44)
    sidecar = sidecar_path_for(cap)
    with pytest.raises(SystemExit):
        main(["--capture", str(cap), "--run-id", "x", "--out", str(sidecar)])


def test_cli_verdict_mode_requires_run_id(tmp_path: Path) -> None:
    cap = _write_cell(tmp_path, seed=1, arm="ON", replicate_id=0, abs_aff=0.44)
    with pytest.raises(SystemExit):
        main(["--capture", str(cap)])


def test_phase0_go(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cap = _write_cell(tmp_path, seed=1, arm="ON", replicate_id=0, abs_aff=0.44)
    assert main(["--phase0", "--capture", str(cap)]) == 0
    assert capsys.readouterr().out.strip() == "GO"


def test_phase0_no_near_miss_when_no_exposure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cap = _write_cell(
        tmp_path, seed=1, arm="ON", replicate_id=0, abs_aff=0.44, exposure=False
    )
    assert main(["--phase0", "--capture", str(cap)]) == 0
    assert capsys.readouterr().out.strip() == "INCONCLUSIVE_NO_NEAR_MISS"


def test_phase0_provenance_false_is_not_eligible(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cap = _write_cell(
        tmp_path, seed=1, arm="ON", replicate_id=0, abs_aff=0.44, provenance=False
    )
    assert main(["--phase0", "--capture", str(cap)]) == 0
    assert capsys.readouterr().out.strip() == "INCONCLUSIVE_NO_NEAR_MISS"


def test_phase0_rejects_multiple_captures(tmp_path: Path) -> None:
    c1 = _write_cell(tmp_path, seed=1, arm="ON", replicate_id=0, abs_aff=0.44)
    c2 = _write_cell(tmp_path, seed=1, arm="OFF", replicate_id=0, abs_aff=0.20)
    with pytest.raises(SystemExit):
        main(["--phase0", "--capture", str(c1), "--capture", str(c2)])
