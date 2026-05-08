"""4 種 hard-fail gate tests (CS-3, m9-c-spike Phase I)."""

from __future__ import annotations

import pytest

from erre_sandbox.training.exceptions import (
    BlockerNotResolvedError,
    EvaluationContaminationError,
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
