"""Trace loader + belief_variance wiring coverage (M11-C2).

Covers ``load_individual_state_windows`` (final-tick selection DA-M11C2-8,
max-tick conflict fail-fast Codex MEDIUM-2, table-absent → empty) and the
runner wiring that turns the final-tick belief set into a ``valid``
``belief_variance`` with trace-aware provenance (Codex HIGH-1) + idempotent
recompute.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest

from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.eval_store import bootstrap_schema, connect_analysis_view
from erre_sandbox.evidence.individuation.layer1 import stub_embedding_provider
from erre_sandbox.evidence.individuation.loader import (
    IndividualStateTraceConflictError,
    load_individual_state_windows,
)
from erre_sandbox.evidence.individuation.policy import MetricStatus
from erre_sandbox.evidence.individuation.runner import (
    IndividuationContext,
    compute_individuation,
)
from erre_sandbox.evidence.individuation.trace_ddl import (
    TABLE_NAME,
    bootstrap_individual_state_trace_schema,
    column_names,
)

_NOW = datetime(2026, 5, 27, tzinfo=UTC)
_DIALOG_COLS = (
    "id",
    "run_id",
    "dialog_id",
    "tick",
    "turn_index",
    "speaker_agent_id",
    "speaker_persona_id",
    "addressee_agent_id",
    "addressee_persona_id",
    "utterance",
    "mode",
    "zone",
    "reasoning",
    "epoch_phase",
    "individual_layer_enabled",
    "created_at",
)


def _dialog_row(idx: int, agent: str, persona: str, utt: str) -> dict[str, Any]:
    return {
        "id": f"{agent}-{idx}",
        "run_id": "run0",
        "dialog_id": "d0",
        "tick": idx,
        "turn_index": 0,
        "speaker_agent_id": agent,
        "speaker_persona_id": persona,
        "addressee_agent_id": "a_other",
        "addressee_persona_id": "other",
        "utterance": utt,
        "mode": "",
        "zone": "study",
        "reasoning": "",
        "epoch_phase": "autonomous",
        "individual_layer_enabled": True,
        "created_at": _NOW,
    }


def _insert_dialog(con: duckdb.DuckDBPyConnection, row: dict[str, Any]) -> None:
    cols = ", ".join(_DIALOG_COLS)
    ph = ", ".join("?" for _ in _DIALOG_COLS)
    con.execute(
        f"INSERT INTO raw_dialog.dialog ({cols}) VALUES ({ph})",  # noqa: S608  # static cols
        [row[c] for c in _DIALOG_COLS],
    )


def _insert_trace(
    con: duckdb.DuckDBPyConnection,
    *,
    run_id: str,
    individual_id: str,
    tick: int,
    belief_classes_json: str | None,
    development_stage: str | None = None,
    coherence_score: float | None = None,
    arc_segment_count: int = 0,
) -> None:
    cols = ", ".join(column_names())
    ph = ", ".join("?" for _ in column_names())
    con.execute(
        f"INSERT INTO {METRICS_SCHEMA}.{TABLE_NAME} ({cols}) VALUES ({ph})",  # noqa: S608  # module constants
        (
            run_id,
            individual_id,
            tick,
            development_stage,
            coherence_score,
            belief_classes_json,
            arc_segment_count,
        ),
    )


# --- loader: table-absent / final-tick / conflict / NULL --------------------


def test_load_returns_empty_when_trace_table_absent(tmp_path: Path) -> None:
    """A flag-off run never creates the trace table -> loader yields {}."""
    db = tmp_path / "noflag.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)  # no conditional trace bootstrap
    con.execute("CHECKPOINT")
    con.close()
    view = connect_analysis_view(db)
    try:
        assert load_individual_state_windows(view) == {}
    finally:
        view.close()


def test_load_uses_final_tick_belief_set(tmp_path: Path) -> None:
    db = tmp_path / "trace.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_rikyu_001",
        tick=0,
        belief_classes_json='["trust"]',
    )
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_rikyu_001",
        tick=1,
        belief_classes_json='["trust", "wary"]',
    )
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_rikyu_001",
        tick=2,
        belief_classes_json='["trust", "wary", "curious"]',
    )
    con.execute("CHECKPOINT")
    con.close()
    view = connect_analysis_view(db)
    try:
        windows = load_individual_state_windows(view, run_id="run0")
    finally:
        view.close()
    win = windows[("run0", "a_rikyu_001")]
    assert win.final_tick == 2
    assert win.belief_classes == ("trust", "wary", "curious")
    assert win.source_table.endswith(f".{TABLE_NAME}")


def test_load_raises_on_divergent_final_tick(tmp_path: Path) -> None:
    db = tmp_path / "conflict.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
    # two rows at the SAME (final) tick with different belief sets
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_kant_001",
        tick=5,
        belief_classes_json='["trust"]',
    )
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_kant_001",
        tick=5,
        belief_classes_json='["wary"]',
    )
    con.execute("CHECKPOINT")
    con.close()
    view = connect_analysis_view(db)
    try:
        with pytest.raises(IndividualStateTraceConflictError):
            load_individual_state_windows(view)
    finally:
        view.close()


def test_load_collapses_identical_duplicate_final_tick(tmp_path: Path) -> None:
    """Byte-identical duplicate rows at the final tick collapse (idempotent)."""
    db = tmp_path / "dup.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_kant_001",
        tick=5,
        belief_classes_json='["trust", "wary"]',
    )
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_kant_001",
        tick=5,
        belief_classes_json='["trust", "wary"]',
    )
    con.execute("CHECKPOINT")
    con.close()
    view = connect_analysis_view(db)
    try:
        windows = load_individual_state_windows(view)
    finally:
        view.close()
    assert windows[("run0", "a_kant_001")].belief_classes == ("trust", "wary")


def test_load_null_json_is_none(tmp_path: Path) -> None:
    db = tmp_path / "null.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
    _insert_trace(
        con, run_id="run0", individual_id="a_kant_001", tick=0, belief_classes_json=None
    )
    con.execute("CHECKPOINT")
    con.close()
    view = connect_analysis_view(db)
    try:
        windows = load_individual_state_windows(view)
    finally:
        view.close()
    assert windows[("run0", "a_kant_001")].belief_classes is None


# --- runner: trace -> valid belief_variance w/ trace provenance -------------


def _booted_run_with_trace(tmp_path: Path, *, final_belief_json: str | None) -> Path:
    """One individual a_kant_001 with raw_dialog window + a 3-tick trace."""
    db = tmp_path / "run.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
    _insert_dialog(con, _dialog_row(1, "a_kant_001", "kant", "the of and study"))
    _insert_dialog(con, _dialog_row(2, "a_kant_001", "kant", "more text here please"))
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_kant_001",
        tick=1,
        belief_classes_json='["trust"]',
    )
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_kant_001",
        tick=2,
        belief_classes_json=final_belief_json,
    )
    con.execute("CHECKPOINT")
    con.close()
    return db


def _belief_result(db: Path, tmp_path: Path) -> Any:
    ctx = IndividuationContext(
        personas_dir=tmp_path,
        provider=stub_embedding_provider(),
        computed_at=_NOW,
    )
    view = connect_analysis_view(db)
    try:
        results = compute_individuation(view, run_id="run0", ctx=ctx)
    finally:
        view.close()
    beliefs = [r for r in results if r.metric_name == "belief_variance"]
    assert len(beliefs) == 1
    return beliefs[0]


def test_runner_belief_variance_valid_from_trace(tmp_path: Path) -> None:
    db = _booted_run_with_trace(tmp_path, final_belief_json='["trust", "wary"]')
    res = _belief_result(db, tmp_path)
    assert res.status is MetricStatus.VALID
    # Gini-Simpson of {trust, wary} (one each) = 1 - (0.25 + 0.25) = 0.5
    assert res.value == pytest.approx(0.5)
    # Codex HIGH-1: provenance points at the trace table, not raw_dialog.dialog.
    assert res.provenance.source_table.endswith(f".{TABLE_NAME}")


def test_runner_belief_variance_degenerate_single_class(tmp_path: Path) -> None:
    db = _booted_run_with_trace(tmp_path, final_belief_json='["trust", "trust"]')
    res = _belief_result(db, tmp_path)
    assert res.status is MetricStatus.DEGENERATE


def test_runner_belief_variance_unsupported_without_trace(tmp_path: Path) -> None:
    """No trace table -> None -> unsupported, with raw_dialog provenance."""
    db = tmp_path / "notrace.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    _insert_dialog(con, _dialog_row(1, "a_kant_001", "kant", "the of and study"))
    con.execute("CHECKPOINT")
    con.close()
    res = _belief_result(db, tmp_path)
    assert res.status is MetricStatus.UNSUPPORTED
    assert res.provenance.source_table == "raw_dialog.dialog"


def test_runner_belief_variance_idempotent_recompute(tmp_path: Path) -> None:
    db = _booted_run_with_trace(tmp_path, final_belief_json='["trust", "wary"]')
    a = _belief_result(db, tmp_path)
    b = _belief_result(db, tmp_path)
    assert a.to_row() == b.to_row()
