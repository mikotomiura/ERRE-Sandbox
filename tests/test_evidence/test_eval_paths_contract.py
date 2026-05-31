"""Behavioural CI test for the m9-eval-system data-path contract.

Layer 2 of the four-layer defence specified in
``.steering/20260430-m9-eval-system/design-final.md`` §"DuckDB 単 file +
named schema + 4 層 contract" — a sentinel-row red-team fixture
(Codex HIGH-1 verification suggestion) that proves no training-egress
route surfaces ``metrics`` data.

Egress paths under test:

* :func:`erre_sandbox.evidence.eval_store.connect_training_view` and
  the :class:`RawTrainingRelation` it returns.
* The existing ``erre-sandbox export-log`` CLI in
  :mod:`erre_sandbox.cli.export_log` — included even though it pre-dates
  the DuckDB store, because the M9 LoRA training pipeline currently
  reads ``dialog_turns`` through it.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from erre_sandbox.__main__ import cli
from erre_sandbox.contracts.eval_paths import (
    ALLOWED_RAW_DIALOG_KEYS,
    FORBIDDEN_METRIC_KEY_PATTERNS,
    METRICS_SCHEMA,
    RAW_DIALOG_SCHEMA,
    SENTINEL_LEAK_PREFIX,
    EvaluationContaminationError,
    RawTrainingRelation,
    assert_no_metrics_leak,
    assert_no_sentinel_leak,
)
from erre_sandbox.evidence.eval_store import (
    RAW_DIALOG_TABLE,
    connect_training_view,
)
from erre_sandbox.memory import MemoryStore
from erre_sandbox.schemas import DialogTurnMsg

# ---------------------------------------------------------------------------
# Sentinel constants
# ---------------------------------------------------------------------------

ALLOWED_SENTINEL = "M9_EVAL_SENTINEL_RAW_OK"
"""Sentinel value placed inside raw_dialog. MUST surface — it is on the
allow-list. Used to confirm the egress is not silently swallowing
legitimate rows along with the leak guard."""

LEAK_SENTINELS = (
    f"{SENTINEL_LEAK_PREFIX}BURROWS_DELTA_4_2",
    f"{SENTINEL_LEAK_PREFIX}VENDI_SCORE_3_1",
    f"{SENTINEL_LEAK_PREFIX}BIG5_ICC_OPENNESS",
)
"""Values planted in metrics.tier_a — none of these may surface through
any training-egress route. ``assert_no_sentinel_leak`` is the assertion."""


# ---------------------------------------------------------------------------
# DuckDB fixture (raw_dialog allowed + metrics poisoned)
# ---------------------------------------------------------------------------


def _seed_duckdb_with_sentinel_rows(
    db_path: Path,
    *,
    raw_dialog_extra_columns: tuple[str, ...] = (),
) -> None:
    """Build a DuckDB file with both schemas, seeded with sentinel rows.

    *raw_dialog_extra_columns* lets the red-team test inject a forbidden
    column into the physical ``raw_dialog.dialog`` table to verify the
    contract raises at construction time.
    """
    con = duckdb.connect(str(db_path))
    try:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {RAW_DIALOG_SCHEMA}")
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {METRICS_SCHEMA}")

        # raw_dialog.dialog — allow-listed columns only (plus optional poison).
        cols_sql = [
            "id TEXT",
            "run_id TEXT",
            "dialog_id TEXT",
            "tick INTEGER",
            "turn_index INTEGER",
            "speaker_persona_id TEXT",
            "addressee_persona_id TEXT",
            "utterance TEXT",
            '"mode" TEXT',
            '"zone" TEXT',
            "created_at TIMESTAMP",
        ]
        cols_sql.extend(f'"{extra}" TEXT' for extra in raw_dialog_extra_columns)
        con.execute(
            f"CREATE TABLE {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}"
            f" ({', '.join(cols_sql)})",
        )
        rows = [
            (
                "row1",
                "run-001",
                "d_kant_nietzsche_0001",
                10,
                0,
                "kant",
                "nietzsche",
                f"opening utterance {ALLOWED_SENTINEL}",
                "peripatos",
                "agora",
                "2026-04-30 00:00:00",
            ),
            (
                "row2",
                "run-001",
                "d_kant_nietzsche_0001",
                11,
                1,
                "nietzsche",
                "kant",
                f"reply utterance {ALLOWED_SENTINEL}",
                "peripatos",
                "agora",
                "2026-04-30 00:00:01",
            ),
        ]
        if raw_dialog_extra_columns:
            # Pad each row with empty strings for the extra columns.
            rows = [tuple(list(r) + [""] * len(raw_dialog_extra_columns)) for r in rows]
        placeholders = ", ".join(["?"] * len(rows[0]))
        con.executemany(
            f"INSERT INTO {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}"  # noqa: S608  # test-controlled identifiers and value count
            f" VALUES ({placeholders})",
            rows,
        )

        # metrics.tier_a — poisoned with leak sentinels.
        con.execute(
            f"CREATE TABLE {METRICS_SCHEMA}.tier_a ("
            "  run_id TEXT,"
            "  persona_id TEXT,"
            "  turn_idx INTEGER,"
            "  metric_name TEXT,"
            "  metric_value DOUBLE,"
            "  notes TEXT"
            ")",
        )
        con.executemany(
            f"INSERT INTO {METRICS_SCHEMA}.tier_a VALUES (?,?,?,?,?,?)",  # noqa: S608  # test-controlled module-constant identifier
            [
                ("run-001", "kant", 0, "burrows_delta", 4.2, LEAK_SENTINELS[0]),
                ("run-001", "kant", 0, "vendi_score", 3.1, LEAK_SENTINELS[1]),
                ("run-001", "kant", 1, "icc_openness", 0.62, LEAK_SENTINELS[2]),
            ],
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()


@pytest.fixture
def seeded_duckdb(tmp_path: Path) -> Path:
    db = tmp_path / "eval-store.duckdb"
    _seed_duckdb_with_sentinel_rows(db)
    return db


# ---------------------------------------------------------------------------
# connect_training_view contract
# ---------------------------------------------------------------------------


def test_relation_implements_protocol(seeded_duckdb: Path) -> None:
    relation = connect_training_view(seeded_duckdb)
    try:
        assert isinstance(relation, RawTrainingRelation)
        assert relation.schema_name == RAW_DIALOG_SCHEMA
    finally:
        relation.close()  # type: ignore[attr-defined]


def test_columns_subset_of_allowlist(seeded_duckdb: Path) -> None:
    relation = connect_training_view(seeded_duckdb)
    try:
        assert set(relation.columns) <= ALLOWED_RAW_DIALOG_KEYS
        assert "utterance" in relation.columns
    finally:
        relation.close()  # type: ignore[attr-defined]


def test_iter_rows_does_not_leak_metrics(seeded_duckdb: Path) -> None:
    relation = connect_training_view(seeded_duckdb)
    try:
        rows = list(relation.iter_rows())
        assert len(rows) == 2
        seen_values: list[object] = []
        for row in rows:
            assert set(row.keys()) <= ALLOWED_RAW_DIALOG_KEYS
            for key in row:
                assert not any(key.startswith(p) for p in FORBIDDEN_METRIC_KEY_PATTERNS)
            seen_values.extend(row.values())
        # Allowed sentinel survives, leak sentinels never appear.
        assert any(isinstance(v, str) and ALLOWED_SENTINEL in v for v in seen_values)
        for leak in LEAK_SENTINELS:
            assert not any(isinstance(v, str) and leak in v for v in seen_values)
    finally:
        relation.close()  # type: ignore[attr-defined]


def test_row_count_matches_seed(seeded_duckdb: Path) -> None:
    relation = connect_training_view(seeded_duckdb)
    try:
        assert relation.row_count() == 2
    finally:
        relation.close()  # type: ignore[attr-defined]


def test_relation_hides_connection_attribute(seeded_duckdb: Path) -> None:
    """The constrained relation must not expose the DuckDB connection.

    Codex HIGH-1: returning a raw connection re-opens an arbitrary-SQL
    surface and defeats the contract. The protocol forbids it; this
    test asserts the concrete implementation honours the protocol's
    spirit.
    """
    relation = connect_training_view(seeded_duckdb)
    try:
        public_attrs = [attr for attr in dir(relation) if not attr.startswith("_")]
        for forbidden in ("execute", "sql", "query", "cursor", "conn", "connection"):
            assert forbidden not in public_attrs, (
                f"RawTrainingRelation must not expose {forbidden!r}"
            )
    finally:
        relation.close()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Red-team: physical schema with poisoned column
# ---------------------------------------------------------------------------


def test_construction_raises_when_raw_dialog_has_metric_column(
    tmp_path: Path,
) -> None:
    """Even if a future migration adds ``metric_burrows_delta`` to
    ``raw_dialog.dialog``, the constrained relation must refuse to
    construct."""
    db = tmp_path / "poisoned.duckdb"
    _seed_duckdb_with_sentinel_rows(
        db,
        raw_dialog_extra_columns=("metric_burrows_delta",),
    )
    with pytest.raises(EvaluationContaminationError) as exc:
        connect_training_view(db)
    assert "metric_burrows_delta" in str(exc.value)


def test_construction_raises_when_table_missing(tmp_path: Path) -> None:
    db = tmp_path / "empty.duckdb"
    con = duckdb.connect(str(db))
    try:
        con.execute(f"CREATE SCHEMA {RAW_DIALOG_SCHEMA}")
    finally:
        con.close()
    with pytest.raises(EvaluationContaminationError):
        connect_training_view(db)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_assert_no_metrics_leak_rejects_forbidden_prefix() -> None:
    with pytest.raises(EvaluationContaminationError) as exc:
        assert_no_metrics_leak(
            ["utterance", "burrows_delta_score"],
            context="unit",
        )
    assert "burrows_delta_score" in str(exc.value)


def test_assert_no_metrics_leak_rejects_keys_outside_allowlist() -> None:
    with pytest.raises(EvaluationContaminationError):
        assert_no_metrics_leak(
            ["utterance", "private_unknown_key"],
            context="unit",
        )


def test_assert_no_metrics_leak_passes_for_allowlist_only() -> None:
    assert_no_metrics_leak(
        ["utterance", "speaker_persona_id", "turn_index"],
        context="unit",
    )


def test_assert_no_sentinel_leak_detects_leak_prefix() -> None:
    with pytest.raises(EvaluationContaminationError) as exc:
        assert_no_sentinel_leak(
            [f"{SENTINEL_LEAK_PREFIX}whatever", "harmless"],
            context="unit",
        )
    assert SENTINEL_LEAK_PREFIX in str(exc.value)


def test_assert_no_sentinel_leak_ignores_non_strings() -> None:
    assert_no_sentinel_leak([0, 1.5, None, "ok"], context="unit")


# ---------------------------------------------------------------------------
# B-1 (m9-individual-layer-schema-add) — allow-list and constant export
# ---------------------------------------------------------------------------


def test_individual_layer_enabled_in_allowed_keys() -> None:
    """B-1: allow-list must include the DB11 / M10-A flag column.

    Without this membership ``connect_training_view`` would either drop
    the column at construction-time subset check (legacy DB) or raise
    contract-divergence at import time (post-B-1 DB)."""
    assert "individual_layer_enabled" in ALLOWED_RAW_DIALOG_KEYS


def test_individual_layer_enabled_key_constant_exported() -> None:
    """B-1 (Codex MEDIUM-3): export the constant from ``eval_paths`` so
    that the training gate (``train_kant_lora``) imports it and the
    allow-list membership is keyed by a single source of truth."""
    import erre_sandbox.contracts.eval_paths as ep

    assert hasattr(ep, "INDIVIDUAL_LAYER_ENABLED_KEY"), (
        "INDIVIDUAL_LAYER_ENABLED_KEY constant must be exported by eval_paths"
    )
    assert ep.INDIVIDUAL_LAYER_ENABLED_KEY == "individual_layer_enabled"
    assert "INDIVIDUAL_LAYER_ENABLED_KEY" in ep.__all__, (
        "INDIVIDUAL_LAYER_ENABLED_KEY must be listed in __all__"
    )


# ---------------------------------------------------------------------------
# Existing-egress audit: erre-sandbox export-log
# ---------------------------------------------------------------------------


def _seed_dialog_turns_with_sentinel(db_path: Path) -> int:
    """Write three Kant turns whose utterance contains the allowed
    sentinel; return the row count."""
    store = MemoryStore(db_path=db_path)
    store.create_schema()
    for i in range(3):
        store.add_dialog_turn_sync(
            DialogTurnMsg(
                tick=10 + i,
                dialog_id="d_kant_nietzsche_0001",
                speaker_id="a_kant_001",
                addressee_id="a_nietzsche_001",
                utterance=f"opening {ALLOWED_SENTINEL} turn={i}",
                turn_index=i,
            ),
            speaker_persona_id="kant",
            addressee_persona_id="nietzsche",
        )
    # Insert one row whose utterance carries a leak sentinel — even if
    # this slips into dialog_turns it must NOT propagate as a metric
    # column. The contract's job is column-level, not value filtering;
    # this row therefore exercises ``assert_no_metrics_leak`` over keys.
    store.add_dialog_turn_sync(
        DialogTurnMsg(
            tick=99,
            dialog_id="d_kant_nietzsche_0001",
            speaker_id="a_kant_001",
            addressee_id="a_nietzsche_001",
            utterance=f"poisoned {LEAK_SENTINELS[0]} body",
            turn_index=99,
        ),
        speaker_persona_id="kant",
        addressee_persona_id="nietzsche",
    )
    return 4


def test_export_log_egress_only_emits_allowlisted_keys(
    tmp_path: Path,
) -> None:
    """``erre-sandbox export-log`` is on the M9 training-egress path
    (the LoRA pipeline currently consumes its JSONL). Every row it
    emits must therefore live within
    :data:`ALLOWED_RAW_DIALOG_KEYS` and carry no metric-shaped key.

    The leak-sentinel value living inside ``utterance`` is allowed to
    surface (column-level contract) — the contract refuses metric
    *columns*, not utterance content. The point of including the row
    is that downstream training data may legitimately quote the
    sentinel string, and the contract must not over-fire on values.
    """
    db = tmp_path / "kant.db"
    expected = _seed_dialog_turns_with_sentinel(db)
    out = tmp_path / "log.jsonl"

    rc = cli(["export-log", "--db", str(db), "--out", str(out)])
    assert rc == 0

    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == expected
    rows = [json.loads(line) for line in lines]
    for row in rows:
        # Every emitted key must be on the raw_dialog allow-list…
        keys = set(row.keys())
        leaked = keys - ALLOWED_RAW_DIALOG_KEYS
        assert keys <= ALLOWED_RAW_DIALOG_KEYS, (
            f"export-log emitted out-of-allowlist key(s) {leaked!r}"
        )
        # …and must not match any metric-shaped prefix.
        assert_no_metrics_leak(row.keys(), context="export-log row")


def test_export_log_egress_does_not_synthesize_metric_keys(
    tmp_path: Path,
) -> None:
    """If a future change widens dialog_turns with a metric-named
    column, the JSONL must not ferry it. Today's iter_dialog_turns
    SELECT is column-explicit, so we assert that property: no metric-
    prefixed key appears in the JSONL output even after a contamination
    attempt at the value level."""
    db = tmp_path / "kant.db"
    _seed_dialog_turns_with_sentinel(db)
    out = tmp_path / "log.jsonl"
    cli(["export-log", "--db", str(db), "--out", str(out)])
    text = out.read_text(encoding="utf-8")
    # Key-shape check: no JSON key beginning with a metric prefix.
    for line in text.strip().splitlines():
        row = json.loads(line)
        for key in row:
            for pattern in FORBIDDEN_METRIC_KEY_PATTERNS:
                assert not key.startswith(pattern), (
                    f"export-log JSONL grew metric-shaped key {key!r}"
                )
