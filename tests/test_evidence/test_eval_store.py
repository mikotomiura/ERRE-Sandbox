"""Tests for :mod:`erre_sandbox.evidence.eval_store` P0c additions.

Covers (per ``.steering/20260430-m9-eval-system/tasklist.md`` §P0c):

* :func:`bootstrap_schema` idempotency and column-set lock-step with
  :data:`ALLOWED_RAW_DIALOG_KEYS`.
* :func:`connect_training_view` opens read-only after bootstrap and
  refuses writes (defence verification at the implementation level —
  the public protocol surface is already covered by
  ``test_eval_paths_contract.py``).
* :func:`connect_analysis_view` returns an :class:`AnalysisView` that
  can SELECT both schemas but cannot INSERT.
* :func:`export_raw_only_snapshot` writes a Parquet whose columns are
  a subset of the raw allow-list and whose rows carry no metric
  sentinel even when the source database has metrics rows.
* :func:`write_with_checkpoint` + :func:`atomic_temp_rename`
  round-trip: a CHECKPOINTed file moved to a new path is openable via
  :func:`connect_analysis_view`.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from erre_sandbox.contracts.eval_paths import (
    ALLOWED_RAW_DIALOG_KEYS,
    METRICS_SCHEMA,
    RAW_DIALOG_SCHEMA,
    SENTINEL_LEAK_PREFIX,
)
from erre_sandbox.evidence.eval_store import (
    RAW_DIALOG_TABLE,
    TIER_B_METRIC_SCHEMA_VERSION,
    AnalysisView,
    TierBMetricRow,
    atomic_temp_rename,
    bootstrap_schema,
    connect_analysis_view,
    connect_training_view,
    export_raw_only_snapshot,
    fetch_tier_b_metric,
    make_tier_b_notes,
    write_with_checkpoint,
)


def _writable(db: Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db), read_only=False)


# ---------------------------------------------------------------------------
# bootstrap_schema
# ---------------------------------------------------------------------------


def test_bootstrap_creates_full_allowlist_for_raw_dialog(tmp_path: Path) -> None:
    db = tmp_path / "fresh.duckdb"
    con = _writable(db)
    try:
        bootstrap_schema(con)
        rows = con.execute(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_schema = ? AND table_name = ?",
            (RAW_DIALOG_SCHEMA, RAW_DIALOG_TABLE),
        ).fetchall()
    finally:
        con.close()
    assert {row[0] for row in rows} == ALLOWED_RAW_DIALOG_KEYS


def test_bootstrap_creates_three_metric_tier_tables(tmp_path: Path) -> None:
    db = tmp_path / "fresh.duckdb"
    con = _writable(db)
    try:
        bootstrap_schema(con)
        rows = con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = ?",
            (METRICS_SCHEMA,),
        ).fetchall()
    finally:
        con.close()
    assert {row[0] for row in rows} == {"tier_a", "tier_b", "tier_c"}


def test_bootstrap_is_idempotent(tmp_path: Path) -> None:
    """Repeated bootstrap calls on the same connection must not raise."""
    db = tmp_path / "fresh.duckdb"
    con = _writable(db)
    try:
        bootstrap_schema(con)
        bootstrap_schema(con)
        bootstrap_schema(con)
    finally:
        con.close()


def test_bootstrap_then_training_view_yields_zero_rows(tmp_path: Path) -> None:
    """Bootstrap-only files open cleanly via the training view with
    row_count() == 0, confirming the constrained relation is
    constructable on a freshly-bootstrapped store."""
    db = tmp_path / "fresh.duckdb"
    con = _writable(db)
    try:
        bootstrap_schema(con)
        con.execute("CHECKPOINT")
    finally:
        con.close()
    relation = connect_training_view(db)
    try:
        assert relation.row_count() == 0
        assert set(relation.columns) == ALLOWED_RAW_DIALOG_KEYS
        assert list(relation.iter_rows()) == []
    finally:
        relation.close()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# B-1 (m9-individual-layer-schema-add) — DDL contract for the new column
# ---------------------------------------------------------------------------


def test_bootstrap_individual_layer_enabled_column_is_not_null_with_default_false(
    tmp_path: Path,
) -> None:
    """B-1 (Codex HIGH-1): the new ``individual_layer_enabled`` column must
    be ``BOOLEAN NOT NULL DEFAULT FALSE``. A nullable column would let
    ``bool(NULL or False) → False`` slip a contamination row past the
    Python-level gate, breaking the bivalent contract."""
    db = tmp_path / "with_layer.duckdb"
    con = _writable(db)
    try:
        bootstrap_schema(con)
        meta = con.execute(
            "SELECT data_type, is_nullable, column_default"
            " FROM information_schema.columns"
            " WHERE table_schema = ? AND table_name = ? AND column_name = ?",
            (RAW_DIALOG_SCHEMA, RAW_DIALOG_TABLE, "individual_layer_enabled"),
        ).fetchone()
    finally:
        con.close()
    assert meta is not None, (
        "individual_layer_enabled column not found in raw_dialog.dialog"
    )
    data_type, is_nullable, column_default = meta
    assert data_type == "BOOLEAN", f"unexpected data_type: {data_type!r}"
    assert is_nullable == "NO", (
        f"individual_layer_enabled must be NOT NULL, got is_nullable={is_nullable!r}"
    )
    # DuckDB renders the default as 'FALSE' / 'false' / "CAST('f' AS BOOLEAN)";
    # accept any falsy spelling.
    default_norm = str(column_default).strip().lower()
    assert default_norm in {"false", "cast('f' as boolean)", "0"}, (
        "individual_layer_enabled default must be FALSE,"
        f" got column_default={column_default!r}"
    )


def test_explicit_null_insert_into_individual_layer_enabled_rejected(
    tmp_path: Path,
) -> None:
    """B-1 (Codex HIGH-1): an explicit NULL insert must trip the NOT NULL
    constraint, otherwise the bivalent contract has a hole.

    The precondition guard distinguishes pre-G2 (column missing → DuckDB
    binder error, false-pass risk) from post-G2 (NOT NULL constraint
    violation, the real signal).
    """
    db = tmp_path / "null_reject.duckdb"
    con = _writable(db)
    try:
        bootstrap_schema(con)
        # Pre-G2 guard: column must exist before we can meaningfully
        # test NOT NULL. Without this, a "Column not found" binder error
        # would also satisfy ``pytest.raises(duckdb.Error)``.
        cols = {
            r[0]
            for r in con.execute(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_schema = ? AND table_name = ?",
                (RAW_DIALOG_SCHEMA, RAW_DIALOG_TABLE),
            ).fetchall()
        }
        assert "individual_layer_enabled" in cols, (
            "G2 precondition: column must exist before testing NOT NULL"
            " (run after eval_store.py DDL update)"
        )
        with pytest.raises(duckdb.Error, match=r"(?i)not[ _]null"):
            con.execute(
                f"INSERT INTO {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}"  # noqa: S608  # module constants
                ' ("id", "individual_layer_enabled") VALUES (?, ?)',
                ("null-row", None),
            )
    finally:
        con.close()


# ---------------------------------------------------------------------------
# connect_analysis_view (Mac-side full read)
# ---------------------------------------------------------------------------


def test_analysis_view_reads_metrics_tier_a(tmp_path: Path) -> None:
    db = tmp_path / "with_metrics.duckdb"
    con = _writable(db)
    try:
        bootstrap_schema(con)
        insert_sql = (
            f"INSERT INTO {METRICS_SCHEMA}.tier_a"  # noqa: S608  # module constants
            ' ("run_id", "persona_id", "turn_idx", "metric_name",'
            ' "metric_value", "notes") VALUES (?, ?, ?, ?, ?, ?)'
        )
        con.execute(
            insert_sql,
            ("run-001", "kant", 0, "burrows_delta", 4.2, "fixture"),
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()
    view = connect_analysis_view(db)
    try:
        select_sql = (
            f"SELECT metric_name, metric_value FROM {METRICS_SCHEMA}.tier_a"  # noqa: S608  # module constants
            " ORDER BY turn_idx"
        )
        rows = view.execute(select_sql)
    finally:
        view.close()
    assert rows == [("burrows_delta", 4.2)]


def test_analysis_view_supports_context_manager(tmp_path: Path) -> None:
    db = tmp_path / "ctx.duckdb"
    con = _writable(db)
    try:
        bootstrap_schema(con)
        con.execute("CHECKPOINT")
    finally:
        con.close()
    with connect_analysis_view(db) as view:
        assert isinstance(view, AnalysisView)
        result = view.execute("SELECT 1")
        assert result == [(1,)]


# ---------------------------------------------------------------------------
# read_only enforcement (both entries)
# ---------------------------------------------------------------------------


def test_training_view_underlying_connection_is_read_only(tmp_path: Path) -> None:
    """The constrained relation's protocol forbids SQL execution from
    the public surface, but as a defence in depth the underlying
    DuckDB handle is also opened ``read_only=True`` so a contract
    bug that leaked the connection would still fail loud."""
    db = tmp_path / "ro.duckdb"
    con = _writable(db)
    try:
        bootstrap_schema(con)
    finally:
        write_with_checkpoint(con)

    rogue_sql = f'INSERT INTO {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE} ("id") VALUES (?)'  # noqa: S608  # module constants

    relation = connect_training_view(db)
    try:
        private_conn = relation._conn  # type: ignore[attr-defined]
        with pytest.raises(duckdb.Error):
            private_conn.execute(rogue_sql, ("rogue",))
    finally:
        relation.close()  # type: ignore[attr-defined]


def test_analysis_view_refuses_writes(tmp_path: Path) -> None:
    db = tmp_path / "ro.duckdb"
    con = _writable(db)
    try:
        bootstrap_schema(con)
    finally:
        write_with_checkpoint(con)

    rogue_sql = f'INSERT INTO {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE} ("id") VALUES (?)'  # noqa: S608  # module constants

    view = connect_analysis_view(db)
    try:
        with pytest.raises(duckdb.Error):
            view.execute(rogue_sql, ("rogue",))
    finally:
        view.close()


# ---------------------------------------------------------------------------
# export_raw_only_snapshot
# ---------------------------------------------------------------------------


def _seed_raw_and_metrics(db: Path) -> None:
    raw_insert_sql = (
        f"INSERT INTO {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}"  # noqa: S608  # module constants
        ' ("id", "run_id", "dialog_id", "tick", "turn_index",'
        ' "speaker_persona_id", "addressee_persona_id", "utterance",'
        ' "mode", "zone", "created_at")'
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    metric_insert_sql = (
        f"INSERT INTO {METRICS_SCHEMA}.tier_a"  # noqa: S608  # module constants
        ' ("run_id", "persona_id", "turn_idx", "metric_name",'
        ' "metric_value", "notes") VALUES (?, ?, ?, ?, ?, ?)'
    )

    con = _writable(db)
    try:
        bootstrap_schema(con)
        con.execute(
            raw_insert_sql,
            (
                "row1",
                "run-001",
                "d_kant_nietzsche_0001",
                10,
                0,
                "kant",
                "nietzsche",
                "raw utterance kept",
                "peripatos",
                "agora",
                "2026-04-30 00:00:00",
            ),
        )
        con.execute(
            metric_insert_sql,
            (
                "run-001",
                "kant",
                0,
                "burrows_delta",
                4.2,
                f"{SENTINEL_LEAK_PREFIX}TIER_A_NOTES",
            ),
        )
    finally:
        write_with_checkpoint(con)


def test_export_raw_only_snapshot_writes_parquet_subset_columns(
    tmp_path: Path,
) -> None:
    src = tmp_path / "src.duckdb"
    _seed_raw_and_metrics(src)

    out = tmp_path / "snapshot.parquet"
    export_raw_only_snapshot(src, out)
    assert out.exists()

    select_all_sql = f"SELECT * FROM read_parquet('{out}')"  # noqa: S608  # tmp_path-derived

    verify = duckdb.connect(":memory:")
    try:
        cursor = verify.execute(select_all_sql)
        col_set = {desc[0] for desc in cursor.description}
        assert col_set == ALLOWED_RAW_DIALOG_KEYS

        all_rows = cursor.fetchall()
        assert len(all_rows) == 1
        # No leak sentinel ever surfaces — the metrics row in the source
        # store stays put.
        for row in all_rows:
            for cell in row:
                assert SENTINEL_LEAK_PREFIX not in str(cell)
    finally:
        verify.close()


def test_export_raw_only_snapshot_rejects_quote_in_path(tmp_path: Path) -> None:
    """The COPY statement embeds *out* as a quoted SQL literal; rejecting
    paths with embedded single-quotes keeps that boundary tight without
    relying on caller-side escaping."""
    src = tmp_path / "src.duckdb"
    con = _writable(src)
    try:
        bootstrap_schema(con)
    finally:
        write_with_checkpoint(con)

    bad = tmp_path / "out'with'quote.parquet"
    with pytest.raises(ValueError, match="single quote"):
        export_raw_only_snapshot(src, bad)


# ---------------------------------------------------------------------------
# ME-2 helpers
# ---------------------------------------------------------------------------


def test_write_with_checkpoint_then_atomic_rename_round_trip(
    tmp_path: Path,
) -> None:
    """Mirror the G-GEAR snapshot protocol from ME-2 inside a single
    tmp_path (same filesystem device): bootstrap → CHECKPOINT + close →
    atomic_temp_rename → open via analysis view."""
    src = tmp_path / "live.duckdb"
    final = tmp_path / "final.duckdb"

    con = _writable(src)
    bootstrap_schema(con)
    write_with_checkpoint(con)
    assert src.exists()

    atomic_temp_rename(src, final)
    assert not src.exists()
    assert final.exists()

    count_sql = f"SELECT COUNT(*) FROM {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}"  # noqa: S608  # identifiers are module constants
    with connect_analysis_view(final) as view:
        rows = view.execute(count_sql)
    assert rows == [(0,)]


def test_atomic_temp_rename_overwrites_existing_target(tmp_path: Path) -> None:
    """``os.replace`` on POSIX overwrites the destination atomically;
    the helper must preserve that semantic so partial-rsync state
    can never linger."""
    src = tmp_path / "live.duckdb"
    final = tmp_path / "final.duckdb"

    con = _writable(src)
    bootstrap_schema(con)
    write_with_checkpoint(con)

    final.write_bytes(b"stale-snapshot")
    atomic_temp_rename(src, final)
    assert not src.exists()
    # The fresh DuckDB file replaced the stub.
    count_sql = f"SELECT COUNT(*) FROM {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}"  # noqa: S608  # identifiers are module constants
    with connect_analysis_view(final) as view:
        rows = view.execute(count_sql)
    assert rows == [(0,)]


# ---------------------------------------------------------------------------
# P4a — Tier B retrieval helpers (M9-eval ME-15)
# ---------------------------------------------------------------------------


def _seed_tier_b_rows(
    db: Path,
    *,
    run_id: str,
    persona_id: str,
    metric_name: str,
    rows: list[tuple[int, float, str | None]],
) -> None:
    """Insert Tier B rows for the helper-coverage test."""
    con = _writable(db)
    bootstrap_schema(con)
    insert_sql = (
        f"INSERT INTO {METRICS_SCHEMA}.tier_b"  # noqa: S608  # module constants
        ' ("run_id", "persona_id", "turn_idx", "metric_name", "metric_value", "notes")'
        " VALUES (?, ?, ?, ?, ?, ?)"
    )
    for window_index, metric_value, notes in rows:
        con.execute(
            insert_sql,
            (run_id, persona_id, window_index, metric_name, metric_value, notes),
        )
    write_with_checkpoint(con)


def test_fetch_tier_b_metric_returns_window_index_and_notes_metadata(
    tmp_path: Path,
) -> None:
    """ME-15: helper exposes window_index + notes JSON, ordered by window."""
    db = tmp_path / "tier_b.duckdb"
    notes_w0 = make_tier_b_notes(
        window_start_turn=0,
        window_end_turn=99,
        window_size=100,
        kernel_name="semantic",
    )
    notes_w1 = make_tier_b_notes(
        window_start_turn=100,
        window_end_turn=199,
        window_size=100,
        kernel_name="semantic",
    )
    _seed_tier_b_rows(
        db,
        run_id="r1",
        persona_id="kant",
        metric_name="tier_b.vendi_score",
        rows=[
            (1, 5.5, notes_w1),  # inserted out of order
            (0, 4.2, notes_w0),
        ],
    )

    with connect_analysis_view(db) as view:
        decoded = fetch_tier_b_metric(
            view,
            run_id="r1",
            persona_id="kant",
            metric_name="tier_b.vendi_score",
        )

    assert len(decoded) == 2
    assert all(isinstance(row, TierBMetricRow) for row in decoded)
    # Ordered by window_index ascending
    assert decoded[0].window_index == 0
    assert decoded[1].window_index == 1
    # Notes JSON parsed
    assert decoded[0].window_start_turn == 0
    assert decoded[0].window_end_turn == 99
    assert decoded[0].window_size == 100
    assert decoded[0].metric_schema_version == TIER_B_METRIC_SCHEMA_VERSION
    assert decoded[1].window_start_turn == 100
    # Metric values intact
    assert decoded[0].metric_value == pytest.approx(4.2)
    assert decoded[1].metric_value == pytest.approx(5.5)


def test_fetch_tier_b_metric_handles_missing_notes_gracefully(tmp_path: Path) -> None:
    """Forward compat: rows with NULL notes still decode (zero-fill metadata)."""
    db = tmp_path / "tier_b_nullnotes.duckdb"
    _seed_tier_b_rows(
        db,
        run_id="r2",
        persona_id="rikyu",
        metric_name="tier_b.big5_stability_icc",
        rows=[(0, 0.78, None)],
    )
    with connect_analysis_view(db) as view:
        decoded = fetch_tier_b_metric(
            view,
            run_id="r2",
            persona_id="rikyu",
            metric_name="tier_b.big5_stability_icc",
        )
    assert len(decoded) == 1
    assert decoded[0].window_index == 0
    assert decoded[0].window_start_turn == 0
    assert decoded[0].window_size == 0  # null notes → zero-fill window metadata
    assert decoded[0].metric_schema_version == ""


def test_make_tier_b_notes_emits_fixed_schema() -> None:
    """ME-15 schema version pinned, optional fields appear only when set."""
    payload = make_tier_b_notes(
        window_start_turn=0,
        window_end_turn=99,
        window_size=100,
        kernel_name="semantic",
    )
    assert '"metric_schema_version":"tier-b-v1"' in payload
    assert '"kernel_name":"semantic"' in payload
    assert '"ipip_version"' not in payload
    assert '"icc_formula"' not in payload


def test_tier_b_metric_isolation_from_training_view(tmp_path: Path) -> None:
    """DB5 sentinel: training view never surfaces metrics.tier_b columns."""
    db = tmp_path / "tier_b_isolation.duckdb"
    _seed_tier_b_rows(
        db,
        run_id="r3",
        persona_id="nietzsche",
        metric_name="tier_b.vendi_score",
        rows=[
            (
                0,
                3.14,
                make_tier_b_notes(
                    window_start_turn=0,
                    window_end_turn=99,
                    window_size=100,
                    kernel_name="semantic",
                ),
            )
        ],
    )
    relation = connect_training_view(db)
    try:
        # Training view's columns set must equal the raw_dialog allow-list,
        # never include any "tier_b" column.
        assert set(relation.columns) == ALLOWED_RAW_DIALOG_KEYS
        for col in relation.columns:
            assert "tier_b" not in col
            assert "metric_value" not in col
            assert "metric_name" not in col
    finally:
        relation.close()
