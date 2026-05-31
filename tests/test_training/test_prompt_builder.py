"""Unit tests for :mod:`erre_sandbox.training.prompt_builder` (m9-c-spike Phase I)."""

from __future__ import annotations

import pytest

from erre_sandbox.training.prompt_builder import (
    KANT_SYSTEM_PROMPT,
    build_chatml_prompt,
)


def test_kant_prompt_contains_persona_system_message() -> None:
    """ChatML output must embed the Kant system prompt verbatim (CS-6 traceability)."""
    text = build_chatml_prompt("kant", "Today's walk shall be brief.")
    assert KANT_SYSTEM_PROMPT in text
    # ChatML role markers are present in the right order: system → assistant.
    assert text.startswith("<|im_start|>system\n")
    assert text.rstrip().endswith("<|im_end|>")


def test_kant_prompt_addressee_inserts_user_turn() -> None:
    """Addressee context appears as a user-role ChatML segment."""
    text = build_chatml_prompt(
        "kant",
        "Indeed, dear Miura.",
        addressee_persona_id="miura",
    )
    assert "<|im_start|>user\n" in text
    assert "addressed by miura" in text
    # Order: system → user → assistant
    sys_idx = text.index("<|im_start|>system\n")
    user_idx = text.index("<|im_start|>user\n")
    asst_idx = text.index("<|im_start|>assistant\n")
    assert sys_idx < user_idx < asst_idx


def test_kant_prompt_no_addressee_omits_user_turn() -> None:
    """``addressee_persona_id=None`` produces a system + assistant pair only.

    This is the monologue / writing-window case — Phase β data may include
    these (Kant's 05:00-07:00 writing window has no interlocutor).
    """
    text = build_chatml_prompt("kant", "The categorical imperative requires...")
    assert "<|im_start|>user\n" not in text
    assert "<|im_start|>system\n" in text
    assert "<|im_start|>assistant\n" in text


def test_unsupported_persona_id_raises() -> None:
    """Only ``"kant"`` is supported in the m9-c-spike (CS-5 scope guard)."""
    with pytest.raises(ValueError, match="unsupported persona_id"):
        build_chatml_prompt("nietzsche", "Become who you are.")
