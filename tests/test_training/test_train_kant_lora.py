"""4 種 hard-fail gate tests (CS-3, m9-c-spike Phase I).

Includes B-1 (m9-individual-layer-schema-add) integration tests against
real DuckDB schemas (placement per Codex MEDIUM-2): the schema-contract
DDL invariants live in ``tests/test_evidence/test_eval_store.py``, and
the end-to-end gate-through-real-loader tests live here so the test
suite reflects which layer surfaces each error.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from erre_sandbox.contracts.eval_paths import (
    RAW_DIALOG_SCHEMA,
    EvaluationContaminationError,
)
from erre_sandbox.evidence.eval_store import (
    RAW_DIALOG_TABLE,
    bootstrap_schema,
    connect_training_view,
)
from erre_sandbox.training.exceptions import (
    BlockerNotResolvedError,
    InsufficientTrainingDataError,
)
from erre_sandbox.training.train_kant_lora import assert_phase_beta_ready
from tests.test_training.conftest import make_kant_row, make_relation


def test_evaluation_phase_row_raises_contamination_error() -> None:
    """Hard-fail #1: any ``epoch_phase=evaluation`` row triggers (CS-3)."""
    rows = [
        make_kant_row(utterance="Clean autonomous turn"),
        make_kant_row(utterance="LEAKED EVAL", epoch_phase="evaluation"),
    ]
    relation = make_relation(rows, with_individual_layer_column=True)
    with pytest.raises(EvaluationContaminationError, match="epoch_phase"):
        assert_phase_beta_ready(relation, persona_id="kant", min_examples=1)


def test_individual_layer_column_absent_raises_blocker_not_resolved() -> None:
    """Hard-fail #2: missing column raises BlockerNotResolvedError w/ B-1 ref."""
    rows = [
        make_kant_row(utterance="Clean turn", individual_layer_enabled=None),
    ]
    relation = make_relation(rows, with_individual_layer_column=False)
    with pytest.raises(
        BlockerNotResolvedError,
        match="m9-individual-layer-schema-add",
    ):
        assert_phase_beta_ready(relation, persona_id="kant", min_examples=1)


def test_individual_layer_true_row_raises_contamination_error() -> None:
    """Hard-fail #3: ``individual_layer_enabled=True`` row triggers (DB11)."""
    rows = [
        make_kant_row(utterance="Clean turn"),
        make_kant_row(utterance="LEAKED IND", individual_layer_enabled=True),
    ]
    relation = make_relation(rows, with_individual_layer_column=True)
    with pytest.raises(
        EvaluationContaminationError,
        match="individual_layer_enabled",
    ):
        assert_phase_beta_ready(relation, persona_id="kant", min_examples=1)


def test_realised_examples_below_threshold_raises() -> None:
    """Hard-fail #4: realised count < ``min_examples`` raises (CS-3)."""
    rows = [
        make_kant_row(utterance=f"Sentence {i}", individual_layer_enabled=False)
        for i in range(3)
    ]
    relation = make_relation(rows, with_individual_layer_column=True)
    with pytest.raises(
        InsufficientTrainingDataError,
        match=r"realised 'kant' example count 3",
    ):
        assert_phase_beta_ready(relation, persona_id="kant", min_examples=1000)


def test_evaluation_phase_casing_variation_still_caught() -> None:
    """``Evaluation``/``EVALUATION`` casing still trips the gate (sec MEDIUM-2)."""
    rows = [
        make_kant_row(utterance="OK turn"),
        make_kant_row(utterance="LEAKED CASING", epoch_phase="EVALUATION"),
    ]
    relation = make_relation(rows, with_individual_layer_column=True)
    with pytest.raises(EvaluationContaminationError, match="epoch_phase"):
        assert_phase_beta_ready(relation, persona_id="kant", min_examples=1)


def test_individual_layer_truthy_non_bool_caught() -> None:
    """Non-bool truthy ``individual_layer_enabled`` trips guard (sec MEDIUM-3)."""
    rows = [
        make_kant_row(utterance="OK turn"),
        # int 1 instead of True — would have slipped past ``is True``.
        {**make_kant_row(utterance="LEAKED INT"), "individual_layer_enabled": 1},
    ]
    relation = make_relation(rows, with_individual_layer_column=True)
    with pytest.raises(EvaluationContaminationError, match="truthy"):
        assert_phase_beta_ready(relation, persona_id="kant", min_examples=1)


def test_clean_dataset_returns_realised_count() -> None:
    """Happy path: gate clears, returns realised example count (CS-3 trace)."""
    rows = [
        make_kant_row(utterance=f"Sentence {i}", individual_layer_enabled=False)
        for i in range(50)
    ]
    relation = make_relation(rows, with_individual_layer_column=True)
    realised = assert_phase_beta_ready(
        relation,
        persona_id="kant",
        min_examples=10,
    )
    assert realised == 50


# ---------------------------------------------------------------------------
# B-1 integration tests — bootstrap_schema → INSERT → connect_training_view
# (Codex MEDIUM-2: real-DuckDB tests live next to the gate they exercise)
# ---------------------------------------------------------------------------


def _writable(db: Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db), read_only=False)


def _insert_kant_row(
    con: duckdb.DuckDBPyConnection,
    row: dict[str, object],
) -> None:
    """Insert a kant ``raw_dialog.dialog`` row dict by enumerating its keys.

    Uses explicit column names so a missing schema column trips the
    DuckDB binder rather than silently shifting positional inserts.
    """
    keys = sorted(row.keys())
    cols_sql = ", ".join(f'"{k}"' for k in keys)
    placeholders = ", ".join(["?"] * len(keys))
    sql = (
        f"INSERT INTO {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}"  # noqa: S608  # module constants + sorted keys
        f" ({cols_sql}) VALUES ({placeholders})"
    )
    con.execute(sql, [row[k] for k in keys])


def test_post_b1_real_relation_passes_blocker_check(tmp_path: Path) -> None:
    """B-1 GREEN: bootstrap → insert 3 clean rows → connect_training_view →
    ``assert_phase_beta_ready(min_examples=1)`` returns realised count
    without raising :class:`BlockerNotResolvedError`. Pre-B-1 the schema
    lacks the column and this test fails at the blocker gate.
    """
    db = tmp_path / "post_b1.duckdb"
    con = _writable(db)
    try:
        bootstrap_schema(con)
        for i in range(3):
            row = make_kant_row(
                utterance=f"Pure reason iteration {i}",
                individual_layer_enabled=False,
            )
            row["id"] = f"kant-row-{i}"
            row["turn_index"] = i
            _insert_kant_row(con, row)
        con.execute("CHECKPOINT")
    finally:
        con.close()
    relation = connect_training_view(db)
    try:
        realised = assert_phase_beta_ready(
            relation,
            persona_id="kant",
            min_examples=1,
        )
    finally:
        relation.close()  # type: ignore[attr-defined]
    assert realised >= 1, f"realised={realised}, expected >= 1 clean kant example"


def test_assert_phase_beta_ready_blocks_individual_layer_true_via_real_relation(
    tmp_path: Path,
) -> None:
    """B-1 (Codex HIGH-2): a truthy ``individual_layer_enabled`` row must be
    rejected at construction time by the loader-level aggregate assert in
    ``_DuckDBRawTrainingRelation``. Pre-G7 (no construction-time
    fail-fast) this test fails; post-G7 the row is rejected with
    :class:`EvaluationContaminationError`."""
    db = tmp_path / "truthy_ind.duckdb"
    con = _writable(db)
    try:
        bootstrap_schema(con)
        # 1 truthy contamination row
        truthy_row = make_kant_row(
            utterance="LEAKED IND",
            individual_layer_enabled=True,
        )
        truthy_row["id"] = "truthy-1"
        _insert_kant_row(con, truthy_row)
        # Plus a few clean rows so any post-filter dataset still has content
        for i in range(2):
            clean = make_kant_row(
                utterance=f"Clean turn {i}",
                individual_layer_enabled=False,
            )
            clean["id"] = f"clean-{i}"
            clean["turn_index"] = i
            _insert_kant_row(con, clean)
        con.execute("CHECKPOINT")
    finally:
        con.close()
    with pytest.raises(EvaluationContaminationError, match="individual_layer_enabled"):
        connect_training_view(db)


def test_assert_phase_beta_ready_blocks_evaluation_phase_via_real_relation(
    tmp_path: Path,
) -> None:
    """B-1 (Codex HIGH-2): an ``epoch_phase=evaluation`` row must be
    rejected at construction time by the loader-level aggregate assert.
    Pre-G7 this test fails (the row only trips the Python-layer gate
    inside ``assert_phase_beta_ready``); post-G7 the row is rejected at
    ``connect_training_view`` with :class:`EvaluationContaminationError`."""
    db = tmp_path / "eval_phase.duckdb"
    con = _writable(db)
    try:
        bootstrap_schema(con)
        contam = make_kant_row(
            utterance="LEAKED EVAL PHASE",
            epoch_phase="evaluation",
            individual_layer_enabled=False,
        )
        contam["id"] = "contam-1"
        _insert_kant_row(con, contam)
        clean = make_kant_row(
            utterance="Clean turn",
            individual_layer_enabled=False,
        )
        clean["id"] = "clean-1"
        clean["turn_index"] = 1
        _insert_kant_row(con, clean)
        con.execute("CHECKPOINT")
    finally:
        con.close()
    with pytest.raises(EvaluationContaminationError, match="epoch_phase"):
        connect_training_view(db)
