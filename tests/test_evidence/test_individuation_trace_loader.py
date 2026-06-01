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
    IndividualStateTraceSchemaError,
    build_world_model_overlap_source_filter_hash,
    individual_state_trace_table,
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
    world_model_keys_json: str | None = None,
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
            world_model_keys_json,
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
    # No SWM column written here either -> world_model_keys is None.
    assert windows[("run0", "a_kant_001")].world_model_keys is None


# --- E2: SWM key set read / backward compat / conflict / shape (DA-S1-2/3) ---


def test_load_reads_final_tick_world_model_keys(tmp_path: Path) -> None:
    """SWM pair-array JSON round-trips to a final-tick (axis,key) tuple set."""
    db = tmp_path / "swm.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_rikyu_001",
        tick=0,
        belief_classes_json='["trust"]',
        world_model_keys_json='[["env", "agora"]]',
    )
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_rikyu_001",
        tick=1,
        belief_classes_json='["trust", "wary"]',
        world_model_keys_json='[["env", "agora"], ["self", "relational_disposition"]]',
    )
    con.execute("CHECKPOINT")
    con.close()
    view = connect_analysis_view(db)
    try:
        windows = load_individual_state_windows(view, run_id="run0")
    finally:
        view.close()
    win = windows[("run0", "a_rikyu_001")]
    assert win.final_tick == 1
    # final-tick SWM key set (parsed pair array)
    assert win.world_model_keys == (
        ("env", "agora"),
        ("self", "relational_disposition"),
    )
    # belief read is unaffected by the SWM column being present
    assert win.belief_classes == ("trust", "wary")


def test_load_empty_swm_distinct_from_none(tmp_path: Path) -> None:
    """'[]' -> empty tuple (synthesised, no entries); NULL -> None (not captured)."""
    db = tmp_path / "swm_empty.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_rikyu_001",
        tick=0,
        belief_classes_json="[]",
        world_model_keys_json="[]",
    )
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_rikyu_002",
        tick=0,
        belief_classes_json=None,
        world_model_keys_json=None,
    )
    con.execute("CHECKPOINT")
    con.close()
    view = connect_analysis_view(db)
    try:
        windows = load_individual_state_windows(view, run_id="run0")
    finally:
        view.close()
    assert windows[("run0", "a_rikyu_001")].world_model_keys == ()
    assert windows[("run0", "a_rikyu_002")].world_model_keys is None


def test_load_pre_e2_table_without_swm_column_reads_none(tmp_path: Path) -> None:
    """A pre-E2 trace table (no world_model_keys_json column) reads as None (DA-S1-3).

    Builds the legacy 7-column table by hand (the column the loader would
    otherwise SELECT is absent) so the SELECT must omit it and not raise.
    """
    db = tmp_path / "pre_e2.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {METRICS_SCHEMA}")
    con.execute(
        f"CREATE TABLE {METRICS_SCHEMA}.{TABLE_NAME} ("  # module constants
        " run_id TEXT NOT NULL, individual_id TEXT NOT NULL, tick BIGINT NOT NULL,"
        " development_stage TEXT, coherence_score DOUBLE, belief_classes_json TEXT,"
        " arc_segment_count BIGINT NOT NULL, CHECK (tick >= 0))"
    )
    con.execute(
        f"INSERT INTO {METRICS_SCHEMA}.{TABLE_NAME}"  # noqa: S608  # module constants
        " (run_id, individual_id, tick, development_stage, coherence_score,"
        " belief_classes_json, arc_segment_count)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("run0", "a_rikyu_001", 1, None, None, '["trust", "wary"]', 0),
    )
    con.execute("CHECKPOINT")
    con.close()
    view = connect_analysis_view(db)
    try:
        windows = load_individual_state_windows(view, run_id="run0")
    finally:
        view.close()
    win = windows[("run0", "a_rikyu_001")]
    # belief still read; SWM absent -> None (no broken SELECT)
    assert win.belief_classes == ("trust", "wary")
    assert win.world_model_keys is None


def test_load_raises_on_divergent_final_tick_world_model_keys(tmp_path: Path) -> None:
    """Same final tick, identical belief but divergent SWM keys -> conflict (C5a)."""
    db = tmp_path / "swm_conflict.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_kant_001",
        tick=5,
        belief_classes_json='["trust"]',
        world_model_keys_json='[["env", "agora"]]',
    )
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_kant_001",
        tick=5,
        belief_classes_json='["trust"]',
        world_model_keys_json='[["env", "study"]]',
    )
    con.execute("CHECKPOINT")
    con.close()
    view = connect_analysis_view(db)
    try:
        with pytest.raises(IndividualStateTraceConflictError):
            load_individual_state_windows(view)
    finally:
        view.close()


def test_load_raises_on_malformed_world_model_keys_shape(tmp_path: Path) -> None:
    """A non pair-array world_model_keys_json fails fast (C5c)."""
    db = tmp_path / "swm_bad.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_kant_001",
        tick=0,
        belief_classes_json='["trust"]',
        world_model_keys_json='["env", "agora"]',  # flat list, not a pair array
    )
    con.execute("CHECKPOINT")
    con.close()
    view = connect_analysis_view(db)
    try:
        with pytest.raises(IndividualStateTraceSchemaError):
            load_individual_state_windows(view)
    finally:
        view.close()


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


# --- M10-A S3 (E2b): a self-pair with SWM present stays UNSUPPORTED (C-2) ----


def test_world_model_overlap_jaccard_self_pair_stays_unsupported_with_swm_trace(
    tmp_path: Path,
) -> None:
    """A single individual (N=1 self-pair) never fabricates the active VALID=1.0.

    Even after E2b activates the metric, an ``A|A`` self-pair routes to the frozen
    ``layer1`` stub (``unsupported``) — a self-overlap of ``1.0`` is meaningless and
    must never pollute the §3.A③ gate (DA-S3-3 / C-2). The active VALID path needs
    **two distinct** individuals with present SWM (exercised by the E2b runner test).
    """
    db = tmp_path / "swm_present.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
    _insert_dialog(con, _dialog_row(1, "a_kant_001", "kant", "the of and study"))
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_kant_001",
        tick=1,
        belief_classes_json='["trust", "wary"]',
        world_model_keys_json='[["env", "agora"], ["self", "relational_disposition"]]',
    )
    con.execute("CHECKPOINT")
    con.close()
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
    jaccard = [r for r in results if r.metric_name == "world_model_overlap_jaccard"]
    assert jaccard, "expected a world_model_overlap_jaccard row"
    assert all(r.status is MetricStatus.UNSUPPORTED for r in jaccard)


def test_world_model_overlap_jaccard_active_for_two_distinct_individuals(
    tmp_path: Path,
) -> None:
    """E2b active path: two distinct same-base individuals with present SWM → VALID.

    Asserts the Jaccard value (1/3 for the fixtures), the trace-table source, and a
    world-model-specific provenance hash (DA-S3-2 / C-1) that is NOT the raw_dialog
    centroid hash for the same dyad.
    """
    db = tmp_path / "two_kant.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
    for agent in ("a_kant_001", "a_kant_002"):
        _insert_dialog(con, _dialog_row(1, agent, "kant", "the of and study here"))
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_kant_001",
        tick=1,
        belief_classes_json='["trust", "wary"]',
        world_model_keys_json='[["env", "agora"], ["self", "relational_disposition"]]',
    )
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_kant_002",
        tick=1,
        belief_classes_json='["trust"]',
        world_model_keys_json='[["env", "agora"], ["env", "study"]]',
    )
    con.execute("CHECKPOINT")
    con.close()
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
    jaccard = [r for r in results if r.metric_name == "world_model_overlap_jaccard"]
    assert len(jaccard) == 1
    row = jaccard[0]
    assert row.status is MetricStatus.VALID
    # ∩ = {env:agora} = 1 ; ∪ = {env:agora, self:rel, env:study} = 3 → 1/3
    assert row.value == pytest.approx(1.0 / 3.0)
    # C-1: provenance is trace-table + world-model-specific hash, never raw_dialog.
    assert row.provenance.source_table == individual_state_trace_table()
    expected_hash = build_world_model_overlap_source_filter_hash(
        run_id="run0",
        source_table=individual_state_trace_table(),
        members=(
            ("a_kant_001", 1, (("env", "agora"), ("self", "relational_disposition"))),
            ("a_kant_002", 1, (("env", "agora"), ("env", "study"))),
        ),
    )
    assert row.provenance.source_filter_hash == expected_hash
    # the centroid row for the same dyad keeps the raw_dialog-derived hash.
    centroid = [r for r in results if r.metric_name == "semantic_centroid_distance"]
    assert centroid
    centroid_hash = centroid[0].provenance.source_filter_hash
    assert centroid_hash != row.provenance.source_filter_hash
    assert centroid[0].provenance.source_table == "raw_dialog.dialog"


def test_world_model_overlap_hash_symmetric_and_distinct_token() -> None:
    """The dyad SWM hash is member-order symmetric and uses its own schema token."""
    members_ab = (
        ("a_kant_001", 1, (("env", "agora"),)),
        ("a_kant_002", 1, (("env", "study"),)),
    )
    members_ba = (members_ab[1], members_ab[0])
    table = individual_state_trace_table()
    h_ab = build_world_model_overlap_source_filter_hash(
        run_id="run0", source_table=table, members=members_ab
    )
    h_ba = build_world_model_overlap_source_filter_hash(
        run_id="run0", source_table=table, members=members_ba
    )
    assert h_ab == h_ba  # symmetric: sorted by individual_id
    # distinct from a single-member projection (token + payload differ)
    h_one = build_world_model_overlap_source_filter_hash(
        run_id="run0", source_table=table, members=(members_ab[0],)
    )
    assert h_one != h_ab


def test_policy_allows_valid_world_model_overlap_jaccard_at_m10a_s3() -> None:
    """E2b (M10-A S3): the SWM Jaccard claim boundary widens to VALID-capable.

    Supersedes the M10-0 ``never-VALID`` pin — the reactivate-ADR §3.A③ path(a)
    gate metric is activated here, so the spec must allow ``valid`` (the active
    implementation lives in ``world_model_metrics.py``, frozen layer1 untouched).
    """
    from erre_sandbox.evidence.individuation.policy import METRIC_SPECS

    spec = METRIC_SPECS["world_model_overlap_jaccard"]
    assert MetricStatus.VALID in spec.allowed_statuses
    assert spec.allowed_statuses == frozenset(
        {MetricStatus.VALID, MetricStatus.DEGENERATE, MetricStatus.UNSUPPORTED}
    )


# --- M10-A S2 (E3): narrative / development substrate read + provenance -------


def test_load_reads_final_tick_narrative_development(tmp_path: Path) -> None:
    """coherence_score / development_stage / arc_segment_count read at final tick."""
    db = tmp_path / "narr.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_rikyu_001",
        tick=0,
        belief_classes_json='["trust"]',
        development_stage="S1_seed",
        coherence_score=0.10,
        arc_segment_count=1,
    )
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_rikyu_001",
        tick=3,
        belief_classes_json='["trust", "wary"]',
        development_stage="S2_exploring",
        coherence_score=0.55,
        arc_segment_count=2,
    )
    con.execute("CHECKPOINT")
    con.close()
    view = connect_analysis_view(db)
    try:
        windows = load_individual_state_windows(view, run_id="run0")
    finally:
        view.close()
    win = windows[("run0", "a_rikyu_001")]
    assert win.final_tick == 3
    assert win.coherence_score == pytest.approx(0.55)
    assert win.development_stage == "S2_exploring"
    assert win.arc_segment_count == 2


def test_per_metric_provenance_hashes_are_distinct(tmp_path: Path) -> None:
    """narrative / development hashes differ from each other AND from belief (CX3)."""
    db = tmp_path / "hash.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_rikyu_001",
        tick=0,
        belief_classes_json='["trust", "wary"]',
        development_stage="S2_exploring",
        coherence_score=0.55,
        arc_segment_count=2,
    )
    con.execute("CHECKPOINT")
    con.close()
    view = connect_analysis_view(db)
    try:
        win = load_individual_state_windows(view, run_id="run0")[
            ("run0", "a_rikyu_001")
        ]
    finally:
        view.close()
    hashes = {
        win.source_filter_hash,  # belief
        win.narrative_source_filter_hash,
        win.development_source_filter_hash,
    }
    assert len(hashes) == 3  # all three distinct (no belief-hash reuse)


def test_load_raises_on_divergent_final_tick_coherence(tmp_path: Path) -> None:
    """Same final tick, divergent coherence_score -> conflict (C5a extended)."""
    db = tmp_path / "coh_conflict.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_kant_001",
        tick=5,
        belief_classes_json='["trust"]',
        coherence_score=0.3,
    )
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_kant_001",
        tick=5,
        belief_classes_json='["trust"]',
        coherence_score=0.9,
    )
    con.execute("CHECKPOINT")
    con.close()
    view = connect_analysis_view(db)
    try:
        with pytest.raises(IndividualStateTraceConflictError):
            load_individual_state_windows(view)
    finally:
        view.close()


def test_load_raises_on_non_finite_coherence(tmp_path: Path) -> None:
    """A non-finite coherence_score is corrupt trace -> fail fast (CX4)."""
    db = tmp_path / "nan.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_kant_001",
        tick=0,
        belief_classes_json='["trust"]',
        coherence_score=float("nan"),
    )
    con.execute("CHECKPOINT")
    con.close()
    view = connect_analysis_view(db)
    try:
        with pytest.raises(IndividualStateTraceSchemaError):
            load_individual_state_windows(view)
    finally:
        view.close()


def test_load_raises_on_negative_arc_segment_count(tmp_path: Path) -> None:
    """A negative arc_segment_count is corrupt trace -> fail fast (CX4)."""
    db = tmp_path / "negarc.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_kant_001",
        tick=0,
        belief_classes_json='["trust"]',
        arc_segment_count=-1,
    )
    con.execute("CHECKPOINT")
    con.close()
    view = connect_analysis_view(db)
    try:
        with pytest.raises(IndividualStateTraceSchemaError):
            load_individual_state_windows(view)
    finally:
        view.close()


# --- M10-A S2 (E3): runner emits diagnostic metrics from the trace ----------


def _state_metric(db: Path, tmp_path: Path, name: str) -> Any:
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
    rows = [r for r in results if r.metric_name == name]
    assert len(rows) == 1
    return rows[0]


def _booted_run_with_state(
    tmp_path: Path, *, stage: str | None, coherence: float | None
) -> Path:
    db = tmp_path / "state.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
    _insert_dialog(con, _dialog_row(1, "a_kant_001", "kant", "the of and study"))
    _insert_trace(
        con,
        run_id="run0",
        individual_id="a_kant_001",
        tick=1,
        belief_classes_json='["trust"]',
        development_stage=stage,
        coherence_score=coherence,
        arc_segment_count=2 if coherence is not None else 0,
    )
    con.execute("CHECKPOINT")
    con.close()
    return db


def test_runner_narrative_development_valid_from_trace(tmp_path: Path) -> None:
    db = _booted_run_with_state(tmp_path, stage="S2_exploring", coherence=0.55)
    narr = _state_metric(db, tmp_path, "narrative_coherence")
    dev = _state_metric(db, tmp_path, "development_stage_ordinal")
    assert narr.status is MetricStatus.VALID
    assert narr.value == pytest.approx(0.55)
    assert narr.provenance.source_table.endswith(f".{TABLE_NAME}")
    assert dev.status is MetricStatus.VALID
    assert dev.value == pytest.approx(1.0)  # S2_exploring ordinal


def test_runner_narrative_development_unsupported_without_trace(tmp_path: Path) -> None:
    """No trace table -> unsupported, provenance points at the trace table (CX3).

    Crucially NOT raw_dialog.dialog: the diagnostic metrics' substrate is the
    (absent) trace table, so an unsupported row must not look raw_dialog-derived.
    """
    db = tmp_path / "nostate.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    _insert_dialog(con, _dialog_row(1, "a_kant_001", "kant", "the of and study"))
    con.execute("CHECKPOINT")
    con.close()
    narr = _state_metric(db, tmp_path, "narrative_coherence")
    dev = _state_metric(db, tmp_path, "development_stage_ordinal")
    assert narr.status is MetricStatus.UNSUPPORTED
    assert dev.status is MetricStatus.UNSUPPORTED
    assert narr.provenance.source_table.endswith(f".{TABLE_NAME}")
    assert narr.provenance.source_table != "raw_dialog.dialog"
    assert dev.provenance.source_table.endswith(f".{TABLE_NAME}")


def test_runner_diagnostic_metrics_not_in_verdict_read_set() -> None:
    """Claim boundary pin (Codex CX1): the frozen C3b verdict never reads them.

    ``c3b_verdict`` / ``c3b_pipeline`` select metrics by name; the diagnostic
    names must not collide with the verdict's consumed set (centroid / floor /
    burrows), so adding them can never move a verdict.
    """
    from erre_sandbox.evidence.individuation import c3b_pipeline, c3b_verdict

    verdict_names = {
        c3b_verdict._CENTROID_METRIC,  # pin test reads the constants
        c3b_verdict._FLOOR_METRIC,
        c3b_verdict._BURROWS_METRIC,
        c3b_pipeline._CENTROID_METRIC,
        c3b_pipeline._FLOOR_METRIC,
        c3b_pipeline._BURROWS_METRIC,
    }
    assert "narrative_coherence" not in verdict_names
    assert "development_stage_ordinal" not in verdict_names
