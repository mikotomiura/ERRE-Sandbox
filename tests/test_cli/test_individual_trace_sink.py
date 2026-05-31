"""``_make_individual_trace_sink`` coverage (M11-C2, Codex HIGH-2).

Proves the orchestrator's flag-on trace sink actually writes a row the loader
can read (run_id bound in the closure, DA-M11C2-4) and that a DuckDB failure is
surfaced as a fatal capture error (mirrors ``_make_duckdb_sink``, Codex HIGH-3),
so the full mock wiring — not just paper acceptance — is verified.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from erre_sandbox.cli.eval_run_golden import (
    CaptureFatalError,
    _make_individual_trace_sink,
    _SinkState,
)
from erre_sandbox.contracts.cognition_layers import (
    DevelopmentState,
    IndividualProfile,
    NarrativeArc,
)
from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.eval_store import bootstrap_schema
from erre_sandbox.evidence.individuation.trace_ddl import (
    TABLE_NAME,
    bootstrap_individual_state_trace_schema,
    column_names,
)


def _profile() -> IndividualProfile:
    return IndividualProfile(
        individual_id="a_rikyu_001",
        base_persona_id="rikyu",
        development_state=DevelopmentState(stage="S2_exploring", maturity_score=0.5),
        narrative_arc=NarrativeArc(
            synthesized_at_tick=3,
            arc_segments=[],
            coherence_score=0.25,
            last_episodic_pointer="ep-1",
        ),
    )


def test_sink_writes_row_loader_can_read(tmp_path: Path) -> None:
    db = tmp_path / "trace.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    try:
        bootstrap_schema(con)
        bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
        state = _SinkState()
        sink = _make_individual_trace_sink(con=con, run_id="run0", state=state)

        sink(_profile(), ["trust", "wary"], 7)

        row = con.execute(
            f"SELECT {', '.join(column_names())}"  # noqa: S608  # module constants
            f" FROM {METRICS_SCHEMA}.{TABLE_NAME}"
        ).fetchone()
    finally:
        con.close()
    assert row == (
        "run0",
        "a_rikyu_001",
        7,
        "S2_exploring",
        0.25,
        '["trust", "wary"]',
        0,
        None,  # world_model_keys_json: _profile() carries no SWM snapshot
    )
    assert state.fatal_error is None


def test_sink_raises_capture_fatal_on_duckdb_error(tmp_path: Path) -> None:
    """No trace table -> INSERT raises duckdb.Error -> fatal (half-write guard)."""
    db = tmp_path / "notable.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    try:
        bootstrap_schema(con)  # deliberately NOT bootstrapping the trace table
        state = _SinkState()
        sink = _make_individual_trace_sink(con=con, run_id="run0", state=state)
        with pytest.raises(CaptureFatalError):
            sink(_profile(), ["trust"], 1)
    finally:
        con.close()
    assert state.fatal_error is not None
    assert "individual_state_trace" in state.fatal_error


def test_sink_skips_when_already_fatal(tmp_path: Path) -> None:
    """Once a fatal landed, the sink is a no-op (mirrors _make_duckdb_sink)."""
    db = tmp_path / "trace.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    try:
        bootstrap_schema(con)
        bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
        state = _SinkState()
        state.set_fatal("earlier failure")
        sink = _make_individual_trace_sink(con=con, run_id="run0", state=state)
        sink(_profile(), ["trust"], 1)  # must not write, must not raise
        (n,) = con.execute(
            f"SELECT count(*) FROM {METRICS_SCHEMA}.{TABLE_NAME}"  # noqa: S608  # module constants
        ).fetchone()
    finally:
        con.close()
    assert n == 0
