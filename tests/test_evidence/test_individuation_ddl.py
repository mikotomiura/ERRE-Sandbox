"""DDL + writer coverage for metrics.individuation (M10-0 PR-1).

Asserts the additive bootstrap, the DB-side CHECK constraints (generic
structural invariants only — Codex MEDIUM-1), the namespace allow-list +
"no extra Layer 2 table" pin (A6), and write_individuation_rows full-run
replace idempotency + in-batch duplicate rejection (Codex HIGH-3).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest

from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.eval_store import (
    bootstrap_schema,
    write_individuation_rows,
)
from erre_sandbox.evidence.individuation import row_field_names
from erre_sandbox.evidence.individuation.cite_belief import (
    all_cite_belief_pins,
    provisional_to_promoted_rate_pin,
)
from erre_sandbox.evidence.individuation.ddl import (
    _INDIVIDUATION_DDL_COLUMNS,
    INDIVIDUATION_COLUMN_COUNT,
)
from erre_sandbox.evidence.individuation.models import MetricResult, Provenance
from erre_sandbox.evidence.individuation.policy import (
    ALLOWED_METRIC_NAMES,
    DYAD_SEP,
    AggregationLevel,
    MetricChannel,
    MetricStatus,
)


def _writable(db: Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db), read_only=False)


def _booted(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    con = _writable(tmp_path / "ind.duckdb")
    bootstrap_schema(con)
    return con


def _raw_row(**over: Any) -> list[Any]:
    """A DB-valid 18-value row in column order; override per CHECK test."""
    base: dict[str, Any] = {
        "run_id": "run0",
        "individual_id": "kant_A",
        "base_persona_id": "kant",
        "aggregation_level": "per_individual",
        "tick": 0,
        "metric_name": "burrows_base_retention",
        "channel": "utterance",
        "status": "valid",
        "value": 0.5,
        "reason": None,
        "metric_schema_version": "m10-0.1",
        "source_table": "raw_dialog.dialog",
        "source_run_id": "run0",
        "source_epoch_phase": "phase_b",
        "source_individual_layer_enabled": False,
        "source_filter_hash": "deadbeef",
        "embedding_model_id": None,
        "computed_at": datetime.now(UTC),
    }
    base.update(over)
    return [base[name] for name, _ in _INDIVIDUATION_DDL_COLUMNS]


def _insert(con: duckdb.DuckDBPyConnection, row: list[Any]) -> None:
    cols = ", ".join(row_field_names())
    ph = ", ".join("?" for _ in row)
    con.execute(
        f"INSERT INTO {METRICS_SCHEMA}.individuation ({cols}) VALUES ({ph})",  # noqa: S608  # module constants
        row,
    )


def test_bootstrap_creates_individuation_with_18_columns(tmp_path: Path) -> None:
    con = _booted(tmp_path)
    try:
        cols = con.execute(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_schema = ? AND table_name = 'individuation'",
            (METRICS_SCHEMA,),
        ).fetchall()
    finally:
        con.close()
    assert {c[0] for c in cols} == set(row_field_names())
    assert len(cols) == INDIVIDUATION_COLUMN_COUNT == 18


def test_bootstrap_idempotent_for_individuation(tmp_path: Path) -> None:
    con = _booted(tmp_path)
    try:
        bootstrap_schema(con)  # second call must not raise
        _insert(con, _raw_row())
        (n,) = con.execute(
            f"SELECT count(*) FROM {METRICS_SCHEMA}.individuation"  # noqa: S608  # module constants
        ).fetchone()
    finally:
        con.close()
    assert n == 1


def test_db_check_rejects_bad_status(tmp_path: Path) -> None:
    con = _booted(tmp_path)
    try:
        with pytest.raises(duckdb.ConstraintException):
            _insert(con, _raw_row(status="bogus", value=None, reason="x"))
    finally:
        con.close()


def test_db_check_rejects_bad_aggregation_level(tmp_path: Path) -> None:
    con = _booted(tmp_path)
    try:
        with pytest.raises(duckdb.ConstraintException):
            _insert(con, _raw_row(aggregation_level="galaxy"))
    finally:
        con.close()


def test_db_check_rejects_value_reason_coupling(tmp_path: Path) -> None:
    con = _booted(tmp_path)
    try:
        # unsupported must not carry a value
        with pytest.raises(duckdb.ConstraintException):
            _insert(con, _raw_row(status="unsupported", value=0.5, reason="x"))
        # valid must not carry a reason
        with pytest.raises(duckdb.ConstraintException):
            _insert(con, _raw_row(status="valid", value=0.5, reason="x"))
    finally:
        con.close()


def test_db_check_rejects_tick_below_minus_one(tmp_path: Path) -> None:
    con = _booted(tmp_path)
    try:
        with pytest.raises(duckdb.ConstraintException):
            _insert(
                con, _raw_row(tick=-2, status="unsupported", value=None, reason="x")
            )
        # -1 sentinel is allowed
        _insert(con, _raw_row(tick=-1, status="unsupported", value=None, reason="x"))
    finally:
        con.close()


def test_metric_name_namespace_allowlist() -> None:
    # the three Layer 2 dotted names are present; no unknown name sneaks in
    expected_layer2 = {
        "cite_belief_discipline.provisional_to_promoted_rate",
        "cite_belief_discipline.cited_memory_id_source_distribution",
        "cite_belief_discipline.counterfactual_challenge_rejection_rate",
    }
    assert expected_layer2 <= ALLOWED_METRIC_NAMES
    # SWM Jaccard / recovery are function/protocol-only but still named here
    assert "world_model_overlap_jaccard" in ALLOWED_METRIC_NAMES
    assert "intervention_recovery_rate" in ALLOWED_METRIC_NAMES


def test_no_extra_layer2_table_created(tmp_path: Path) -> None:
    # A6: Layer 2 lives in the same table via dotted metric_name; no
    # metrics.social_tom / cite_belief / layer2 table may exist.
    con = _booted(tmp_path)
    try:
        names = {
            row[0]
            for row in con.execute(
                "SELECT table_name FROM information_schema.tables"
                " WHERE table_schema = ?",
                (METRICS_SCHEMA,),
            ).fetchall()
        }
    finally:
        con.close()
    assert names == {"tier_a", "tier_b", "tier_c", "individuation"}
    for forbidden in ("cite_belief", "social_tom", "layer2"):
        assert not any(forbidden in name for name in names)


def test_write_individuation_rows_full_run_replace_idempotent(tmp_path: Path) -> None:
    con = _booted(tmp_path)
    try:
        pins = list(
            all_cite_belief_pins(
                run_id="run0",
                individual_id="kant_A",
                base_persona_id="kant",
                source_epoch_phase="phase_b",
                source_individual_layer_enabled=False,
            )
        )
        assert write_individuation_rows(con, pins) == 3
        # re-write the same run: full-run replace keeps row count stable
        assert write_individuation_rows(con, pins) == 3
        (n,) = con.execute(
            f"SELECT count(*) FROM {METRICS_SCHEMA}.individuation"  # noqa: S608  # module constants
        ).fetchone()
    finally:
        con.close()
    assert n == 3


def test_write_individuation_rows_rejects_in_batch_duplicate(tmp_path: Path) -> None:
    con = _booted(tmp_path)
    try:
        pin = provisional_to_promoted_rate_pin(
            run_id="run0",
            individual_id="kant_A",
            base_persona_id="kant",
            source_epoch_phase="phase_b",
            source_individual_layer_enabled=False,
        )
        with pytest.raises(ValueError, match="duplicate natural key"):
            write_individuation_rows(con, [pin, pin])
    finally:
        con.close()


def test_write_individuation_rows_empty_is_noop(tmp_path: Path) -> None:
    con = _booted(tmp_path)
    try:
        assert write_individuation_rows(con, []) == 0
    finally:
        con.close()


# --- M11-C3b HIGH-2: multi-encoder centroid natural-key roundtrip ----------


def _panel_centroid_row(model_id: str, value: float) -> MetricResult:
    """A per-dyad centroid row for one encoder.

    Every field except ``embedding_model_id`` (and the value) matches the other
    encoders' rows — including ``source_filter_hash`` (window-derived, so
    encoder-independent). Before the HIGH-2 natural-key fix these three rows
    collided on the in-batch dedup key (DA-M11C3b-P1-5).
    """
    return MetricResult(
        run_id="run0",
        individual_id=f"a_rikyu_001{DYAD_SEP}a_rikyu_002",
        base_persona_id=f"rikyu{DYAD_SEP}rikyu",
        aggregation_level=AggregationLevel.PER_DYAD,
        tick=-1,
        metric_name="semantic_centroid_distance",
        channel=MetricChannel.UTTERANCE,
        status=MetricStatus.VALID,
        value=value,
        reason=None,
        provenance=Provenance(
            metric_schema_version="m10-0.1",
            source_table="raw_dialog.dialog",
            source_run_id="run0",
            source_epoch_phase="autonomous",
            source_individual_layer_enabled=True,
            source_filter_hash="shared-window-hash",  # encoder-independent
            embedding_model_id=model_id,
        ),
        computed_at=datetime.now(UTC),
    )


def test_write_individuation_rows_multi_encoder_centroid_distinct(
    tmp_path: Path,
) -> None:
    # Three encoders, same dyad / window / natural key but for embedding_model_id.
    rows = [
        _panel_centroid_row("sentence-transformers/all-mpnet-base-v2", 0.11),
        _panel_centroid_row("intfloat/multilingual-e5-large", 0.22),
        _panel_centroid_row("BAAI/bge-m3", 0.33),
    ]
    con = _booted(tmp_path)
    try:
        # No "duplicate natural key" ValueError now that embedding_model_id is
        # part of the key — all three persist.
        assert write_individuation_rows(con, rows) == 3
        read = con.execute(
            f"SELECT embedding_model_id, value"  # noqa: S608  # module constants
            f" FROM {METRICS_SCHEMA}.individuation"
            " WHERE metric_name = 'semantic_centroid_distance'"
            " ORDER BY embedding_model_id"
        ).fetchall()
    finally:
        con.close()
    # Each encoder's value survives intact (no overwrite / no confusion).
    by_model = dict(read)
    assert by_model == {
        "sentence-transformers/all-mpnet-base-v2": 0.11,
        "intfloat/multilingual-e5-large": 0.22,
        "BAAI/bge-m3": 0.33,
    }


def test_write_individuation_rows_still_rejects_true_duplicate(tmp_path: Path) -> None:
    # Same embedding_model_id + same everything -> still a duplicate (fix is
    # additive, not a loosening).
    row = _panel_centroid_row("intfloat/multilingual-e5-large", 0.5)
    con = _booted(tmp_path)
    try:
        with pytest.raises(ValueError, match="duplicate natural key"):
            write_individuation_rows(con, [row, row])
    finally:
        con.close()
