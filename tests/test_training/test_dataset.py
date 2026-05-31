"""Unit tests for :mod:`erre_sandbox.training.dataset` (m9-c-spike Phase I)."""

from __future__ import annotations

from erre_sandbox.training.dataset import build_examples
from tests.test_training.conftest import make_kant_row


def test_build_examples_filters_non_persona_rows_and_evaluation() -> None:
    """Only Kant utterances from non-evaluation epochs reach the example list."""
    rows = [
        make_kant_row(utterance="Kant clean utterance"),
        make_kant_row(utterance="Should drop", epoch_phase="evaluation"),
        # Non-Kant speaker — must drop
        {**make_kant_row(utterance="Miura says hi"), "speaker_persona_id": "miura"},
        # Empty utterance — must drop
        make_kant_row(utterance="   "),
    ]
    examples = build_examples(rows, persona_id="kant")
    assert len(examples) == 1
    assert "Kant clean utterance" in examples[0]["text"]


def test_build_examples_returns_chatml_text_dicts() -> None:
    """Every example is a ``{"text": chatml}`` dict (HF SFTTrainer compat)."""
    rows = [make_kant_row(utterance=f"Sentence {i}") for i in range(5)]
    examples = build_examples(rows, persona_id="kant")
    assert len(examples) == 5
    for example in examples:
        assert set(example.keys()) == {"text"}
        assert "<|im_start|>system\n" in example["text"]
        assert "<|im_start|>assistant\n" in example["text"]
