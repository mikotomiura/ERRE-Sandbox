"""Unit tests for :mod:`erre_sandbox.cli.eval_audit` (m9-eval-cli-partial-fix).

Covers ME-9 ADR §2 (audit gate) and Codex 2026-05-06 review HIGH-1 (run_id
same-run integrity) + MEDIUM-3 (training-ish path warn). The DuckDB
fixtures bootstrap the ``raw_dialog`` schema via the production helpers
so the test surface mirrors real captures.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest

from erre_sandbox.cli.eval_audit import (
    EXIT_INCOMPLETE,
    EXIT_MISMATCH,
    EXIT_MISSING_SIDECAR,
    EXIT_PASS,
    main,
)
from erre_sandbox.evidence.capture_sidecar import (
    SidecarV1,
    sidecar_path_for,
    write_sidecar_atomic,
)
from erre_sandbox.evidence.eval_store import bootstrap_schema

pytestmark = pytest.mark.eval


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _bootstrap_capture(
    duckdb_path: Path,
    *,
    persona: str,
    condition: str,
    run_idx: int,
    focal_rows: int,
    foreign_focal_rows: int = 0,
) -> tuple[int, int]:
    """Create a DuckDB capture with ``focal_rows`` focal-speaker rows.

    Returns ``(total_rows, focal_rows)`` so the caller knows what to plug
    into the sidecar. Optionally inserts ``foreign_focal_rows`` rows for
    a *different* persona under the same ``run_id`` so cross-persona
    counts can be tested.
    """
    run_id = f"{persona}_{condition}_run{run_idx}"
    con = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        bootstrap_schema(con)
        for i in range(focal_rows):
            con.execute(
                "INSERT INTO raw_dialog.dialog"
                ' ("id", "run_id", "dialog_id", "tick", "turn_index",'
                ' "speaker_agent_id", "speaker_persona_id",'
                ' "addressee_agent_id", "addressee_persona_id",'
                ' "utterance", "mode", "zone", "reasoning", "epoch_phase",'
                ' "created_at") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (
                    f"row_{i}",
                    run_id,
                    f"d{i}",
                    i,
                    0,
                    f"a_{persona}_001",
                    persona,
                    "a_other_001",
                    "other",
                    f"focal-{i}",
                    "",
                    "AGORA",
                    "",
                    "autonomous",
                    datetime.now(UTC),
                ),
            )
        for i in range(foreign_focal_rows):
            con.execute(
                "INSERT INTO raw_dialog.dialog"
                ' ("id", "run_id", "dialog_id", "tick", "turn_index",'
                ' "speaker_agent_id", "speaker_persona_id",'
                ' "addressee_agent_id", "addressee_persona_id",'
                ' "utterance", "mode", "zone", "reasoning", "epoch_phase",'
                ' "created_at") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (
                    f"foreign_{i}",
                    run_id,
                    f"d{i}",
                    i,
                    1,
                    "a_other_001",
                    "other",
                    f"a_{persona}_001",
                    persona,
                    f"foreign-{i}",
                    "",
                    "AGORA",
                    "",
                    "autonomous",
                    datetime.now(UTC),
                ),
            )
        con.execute("CHECKPOINT")
    finally:
        con.close()
    total_rows = focal_rows + foreign_focal_rows
    return total_rows, focal_rows


def _write_sidecar(
    duckdb_path: Path,
    *,
    persona: str,
    condition: str,
    run_idx: int,
    status: str,
    stop_reason: str,
    focal_target: int,
    focal_observed: int,
    total_rows: int,
    drain_completed: bool = True,
    runtime_drain_timeout: bool = False,
) -> Path:
    """Write a SidecarV1 next to *duckdb_path* and return its path."""
    sidecar_path = sidecar_path_for(duckdb_path)
    payload = SidecarV1.model_validate(
        {
            "schema_version": "1",
            "status": status,
            "stop_reason": stop_reason,
            "focal_target": focal_target,
            "focal_observed": focal_observed,
            "total_rows": total_rows,
            "wall_timeout_min": 360.0,
            "drain_completed": drain_completed,
            "runtime_drain_timeout": runtime_drain_timeout,
            "git_sha": "deadbee",
            "captured_at": "2026-05-06T12:00:00Z",
            "persona": persona,
            "condition": condition,
            "run_idx": run_idx,
            "duckdb_path": str(duckdb_path),
        },
    )
    write_sidecar_atomic(sidecar_path, payload)
    return sidecar_path


# ---------------------------------------------------------------------------
# 1. complete + focal >= target → 0 (PASS)
# ---------------------------------------------------------------------------


def test_audit_complete_focal_at_target_passes(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "kant_natural_run0.duckdb"
    total_rows, focal_rows = _bootstrap_capture(
        duckdb_path,
        persona="kant",
        condition="natural",
        run_idx=0,
        focal_rows=500,
    )
    _write_sidecar(
        duckdb_path,
        persona="kant",
        condition="natural",
        run_idx=0,
        status="complete",
        stop_reason="complete",
        focal_target=500,
        focal_observed=focal_rows,
        total_rows=total_rows,
    )
    code = main(
        ["--duckdb", str(duckdb_path), "--focal-target", "500"],
    )
    assert code == EXIT_PASS


# ---------------------------------------------------------------------------
# 2. complete + focal < target → 6 (FAIL — focal_observed below target)
# ---------------------------------------------------------------------------


def test_audit_complete_below_target_fails(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "kant_natural_run0.duckdb"
    total_rows, focal_rows = _bootstrap_capture(
        duckdb_path,
        persona="kant",
        condition="natural",
        run_idx=0,
        focal_rows=200,
    )
    _write_sidecar(
        duckdb_path,
        persona="kant",
        condition="natural",
        run_idx=0,
        status="complete",
        stop_reason="complete",
        focal_target=500,
        focal_observed=focal_rows,
        total_rows=total_rows,
    )
    code = main(
        ["--duckdb", str(duckdb_path), "--focal-target", "500"],
    )
    assert code == EXIT_INCOMPLETE


# ---------------------------------------------------------------------------
# 3. partial + --allow-partial → 0
# ---------------------------------------------------------------------------


def test_audit_partial_with_allow_passes(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "kant_natural_run0.duckdb"
    total_rows, focal_rows = _bootstrap_capture(
        duckdb_path,
        persona="kant",
        condition="natural",
        run_idx=0,
        focal_rows=381,
    )
    _write_sidecar(
        duckdb_path,
        persona="kant",
        condition="natural",
        run_idx=0,
        status="partial",
        stop_reason="wall_timeout",
        focal_target=500,
        focal_observed=focal_rows,
        total_rows=total_rows,
    )
    code = main(
        [
            "--duckdb",
            str(duckdb_path),
            "--focal-target",
            "500",
            "--allow-partial",
        ],
    )
    assert code == EXIT_PASS


# ---------------------------------------------------------------------------
# 4. partial without flag → 6 (FAIL — diagnostic mode required)
# ---------------------------------------------------------------------------


def test_audit_partial_without_allow_fails(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "kant_natural_run0.duckdb"
    total_rows, focal_rows = _bootstrap_capture(
        duckdb_path,
        persona="kant",
        condition="natural",
        run_idx=0,
        focal_rows=381,
    )
    _write_sidecar(
        duckdb_path,
        persona="kant",
        condition="natural",
        run_idx=0,
        status="partial",
        stop_reason="wall_timeout",
        focal_target=500,
        focal_observed=focal_rows,
        total_rows=total_rows,
    )
    code = main(["--duckdb", str(duckdb_path), "--focal-target", "500"])
    assert code == EXIT_INCOMPLETE


# ---------------------------------------------------------------------------
# 5. missing sidecar → 4
# ---------------------------------------------------------------------------


def test_audit_missing_sidecar_returns_4(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "kant_natural_run0.duckdb"
    _bootstrap_capture(
        duckdb_path,
        persona="kant",
        condition="natural",
        run_idx=0,
        focal_rows=500,
    )
    # No sidecar written.
    code = main(["--duckdb", str(duckdb_path), "--focal-target", "500"])
    assert code == EXIT_MISSING_SIDECAR


# ---------------------------------------------------------------------------
# 6. row count mismatch → 5
# ---------------------------------------------------------------------------


def test_audit_row_count_mismatch_returns_5(tmp_path: Path) -> None:
    """Sidecar claims a different total than DuckDB ⇒ structural mismatch."""
    duckdb_path = tmp_path / "kant_natural_run0.duckdb"
    total_rows, focal_rows = _bootstrap_capture(
        duckdb_path,
        persona="kant",
        condition="natural",
        run_idx=0,
        focal_rows=500,
    )
    _write_sidecar(
        duckdb_path,
        persona="kant",
        condition="natural",
        run_idx=0,
        status="complete",
        stop_reason="complete",
        focal_target=500,
        focal_observed=focal_rows,
        total_rows=total_rows + 7,  # lie
    )
    code = main(["--duckdb", str(duckdb_path), "--focal-target", "500"])
    assert code == EXIT_MISMATCH


# ---------------------------------------------------------------------------
# 7. run_id mismatch → 5 (Codex H1, 2026-05-06)
# ---------------------------------------------------------------------------


def test_audit_run_id_mismatch_returns_5(tmp_path: Path) -> None:
    """A foreign sidecar (different persona / run_idx) must trip return 5."""
    duckdb_path = tmp_path / "kant_natural_run0.duckdb"
    total_rows, focal_rows = _bootstrap_capture(
        duckdb_path,
        persona="kant",
        condition="natural",
        run_idx=0,
        focal_rows=500,
    )
    # Sidecar pretends this DB is a *different* cell.
    _write_sidecar(
        duckdb_path,
        persona="rikyu",  # kant rows, but sidecar claims rikyu
        condition="natural",
        run_idx=2,
        status="complete",
        stop_reason="complete",
        focal_target=500,
        focal_observed=focal_rows,
        total_rows=total_rows,
    )
    code = main(["--duckdb", str(duckdb_path), "--focal-target", "500"])
    # The persona-keyed focal count in the DB is 0 for rikyu, so the
    # focal_mismatch check fires before run_id_mismatch — both are EXIT_MISMATCH.
    assert code == EXIT_MISMATCH


# ---------------------------------------------------------------------------
# 8. batch: JSON report + max() exit code (Codex M3)
# ---------------------------------------------------------------------------


def test_audit_batch_writes_atomic_json_report(tmp_path: Path) -> None:
    """Three captures (complete, partial, missing-sidecar) → JSON + max()."""
    pass_path = tmp_path / "kant_natural_run0.duckdb"
    total_rows, focal_rows = _bootstrap_capture(
        pass_path,
        persona="kant",
        condition="natural",
        run_idx=0,
        focal_rows=500,
    )
    _write_sidecar(
        pass_path,
        persona="kant",
        condition="natural",
        run_idx=0,
        status="complete",
        stop_reason="complete",
        focal_target=500,
        focal_observed=focal_rows,
        total_rows=total_rows,
    )

    partial_path = tmp_path / "nietzsche_natural_run0.duckdb"
    n_total, n_focal = _bootstrap_capture(
        partial_path,
        persona="nietzsche",
        condition="natural",
        run_idx=0,
        focal_rows=381,
    )
    _write_sidecar(
        partial_path,
        persona="nietzsche",
        condition="natural",
        run_idx=0,
        status="partial",
        stop_reason="wall_timeout",
        focal_target=500,
        focal_observed=n_focal,
        total_rows=n_total,
    )

    legacy_path = tmp_path / "rikyu_natural_run0.duckdb"
    _bootstrap_capture(
        legacy_path,
        persona="rikyu",
        condition="natural",
        run_idx=0,
        focal_rows=500,
    )
    # No sidecar — legacy.

    report_path = tmp_path / "audit-report.json"
    code = main(
        [
            "--duckdb-glob",
            str(tmp_path / "*.duckdb"),
            "--focal-target",
            "500",
            "--report-json",
            str(report_path),
        ],
    )
    # legacy returns 4; partial without --allow-partial returns 6;
    # max() = 6.
    assert code == EXIT_INCOMPLETE
    report: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["total"] == 3
    assert report["complete"] == 1
    assert report["missing_sidecar"] == 1
    # partial without --allow-partial counts as fail
    assert report["fail"] == 1
    assert report["overall_exit_code"] == EXIT_INCOMPLETE
    # No leftover .tmp from the atomic write
    assert not report_path.with_suffix(report_path.suffix + ".tmp").exists()


# ---------------------------------------------------------------------------
# 9. training-ish path warn (Codex M3)
# ---------------------------------------------------------------------------


def test_audit_batch_warns_for_training_path(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Warn on stderr when --report-json points at an egress-shaped path."""
    duckdb_path = tmp_path / "kant_natural_run0.duckdb"
    total_rows, focal_rows = _bootstrap_capture(
        duckdb_path,
        persona="kant",
        condition="natural",
        run_idx=0,
        focal_rows=500,
    )
    _write_sidecar(
        duckdb_path,
        persona="kant",
        condition="natural",
        run_idx=0,
        status="complete",
        stop_reason="complete",
        focal_target=500,
        focal_observed=focal_rows,
        total_rows=total_rows,
    )
    egress_path = tmp_path / "eval" / "training" / "audit.json"
    egress_path.parent.mkdir(parents=True, exist_ok=True)

    main(
        [
            "--duckdb-glob",
            str(tmp_path / "*.duckdb"),
            "--focal-target",
            "500",
            "--report-json",
            str(egress_path),
        ],
    )
    err = capsys.readouterr().err
    assert "training" in err.lower()
    assert egress_path.exists()
