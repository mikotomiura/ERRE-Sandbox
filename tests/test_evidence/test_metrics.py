"""Unit tests for :mod:`erre_sandbox.evidence.metrics` (M8 baseline).

Every metric is pure, so these tests build ``list[dict]`` fixtures directly
and assert on the scalar output. ``aggregate()`` is exercised separately
via a fresh in-memory MemoryStore so its sqlite I/O path is covered end
to end without going through the CLI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from erre_sandbox.evidence import (
    aggregate,
    compute_bias_fired_rate,
    compute_cross_persona_echo_rate,
    compute_self_repetition_rate,
)
from erre_sandbox.memory.store import MemoryStore

# ---------------------------------------------------------------------------
# self_repetition_rate
# ---------------------------------------------------------------------------


def test_self_repetition_returns_none_on_empty_input() -> None:
    assert compute_self_repetition_rate([]) is None


def test_self_repetition_returns_none_when_only_one_turn_per_persona() -> None:
    """Need at least 2 turns per persona to form a comparison pair."""
    turns = [
        {"speaker_persona_id": "kant", "utterance": "a b c d e"},
        {"speaker_persona_id": "rikyu", "utterance": "f g h i j"},
    ]
    assert compute_self_repetition_rate(turns) is None


def test_self_repetition_identical_utterances_score_one() -> None:
    turns = [
        {"speaker_persona_id": "kant", "utterance": "a b c d"},
        {"speaker_persona_id": "kant", "utterance": "a b c d"},
    ]
    score = compute_self_repetition_rate(turns)
    assert score is not None
    assert score == pytest.approx(1.0)


def test_self_repetition_disjoint_utterances_score_zero() -> None:
    turns = [
        {"speaker_persona_id": "kant", "utterance": "a b c d"},
        {"speaker_persona_id": "kant", "utterance": "w x y z"},
    ]
    score = compute_self_repetition_rate(turns)
    assert score is not None
    assert score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# cross_persona_echo_rate
# ---------------------------------------------------------------------------


def test_cross_persona_echo_returns_none_on_single_persona() -> None:
    turns = [
        {"dialog_id": "d0", "speaker_persona_id": "kant", "utterance": "a b c"},
        {"dialog_id": "d0", "speaker_persona_id": "kant", "utterance": "a b c"},
    ]
    assert compute_cross_persona_echo_rate(turns) is None


def test_cross_persona_echo_picks_up_shared_trigrams_across_personas() -> None:
    """Two personas saying the same 3-word phrase should score 1.0."""
    turns = [
        {"dialog_id": "d0", "speaker_persona_id": "kant", "utterance": "a b c d"},
        {"dialog_id": "d0", "speaker_persona_id": "rikyu", "utterance": "a b c d"},
    ]
    score = compute_cross_persona_echo_rate(turns)
    assert score is not None
    assert score == pytest.approx(1.0)


def test_cross_persona_echo_ignores_same_persona_pairs() -> None:
    """Self-repetition must not leak into the cross-persona metric."""
    turns = [
        # Kant echoes himself within the same dialog.
        {"dialog_id": "d0", "speaker_persona_id": "kant", "utterance": "a b c"},
        {"dialog_id": "d0", "speaker_persona_id": "kant", "utterance": "a b c"},
        # Rikyū speaks something disjoint.
        {"dialog_id": "d0", "speaker_persona_id": "rikyu", "utterance": "x y z"},
    ]
    score = compute_cross_persona_echo_rate(turns)
    assert score is not None
    # Self-echo ignored; only cross-persona pairs (kant,rikyu) × 2 = 0.0 each.
    assert score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# bias_fired_rate
# ---------------------------------------------------------------------------


def test_bias_fired_rate_none_when_no_events() -> None:
    assert compute_bias_fired_rate([], run_duration_s=60.0, num_agents=3) is None


def test_bias_fired_rate_scales_with_event_count() -> None:
    """Double the events at constant run/p -> double the ratio."""
    events_one = [{"bias_p": 0.2}]
    events_two = [{"bias_p": 0.2}, {"bias_p": 0.2}]
    rate_one = compute_bias_fired_rate(events_one, run_duration_s=60.0, num_agents=3)
    rate_two = compute_bias_fired_rate(events_two, run_duration_s=60.0, num_agents=3)
    assert rate_one is not None
    assert rate_two is not None
    assert rate_two == pytest.approx(rate_one * 2)


def test_bias_fired_rate_none_for_invalid_denominator() -> None:
    events = [{"bias_p": 0.2}]
    assert compute_bias_fired_rate(events, run_duration_s=0.0, num_agents=3) is None
    assert compute_bias_fired_rate(events, run_duration_s=60.0, num_agents=0) is None


# ---------------------------------------------------------------------------
# aggregate() — I/O wrapper
# ---------------------------------------------------------------------------


def test_aggregate_returns_null_metrics_for_empty_db(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.db"
    result = aggregate(db_path)
    assert result["schema"] == "baseline_metrics_v1"
    assert result["turn_count"] == 0
    assert result["bias_event_count"] == 0
    assert result["self_repetition_rate"] is None
    assert result["cross_persona_echo_rate"] is None
    assert result["bias_fired_rate"] is None
    # affinity deferred per decisions D1 — shape must stay stable for M9.
    assert result["affinity_trajectory"] is None


def test_aggregate_populates_metrics_from_seeded_db(tmp_path: Path) -> None:
    """End-to-end: seed dialog_turns + bias_events, aggregate, assert shape."""
    from erre_sandbox.schemas import DialogTurnMsg

    db_path = tmp_path / "seeded.db"
    store = MemoryStore(db_path=db_path)
    store.create_schema()

    # 2 Kant turns (same text -> self_repetition=1.0), 1 Rikyū turn distinct.
    for i in range(2):
        store.add_dialog_turn_sync(
            DialogTurnMsg(
                tick=10 + i,
                dialog_id="d0",
                speaker_id="a_kant_001",
                addressee_id="a_rikyu_001",
                utterance="the same three words",
                turn_index=i,
            ),
            speaker_persona_id="kant",
            addressee_persona_id="rikyu",
        )
    store.add_dialog_turn_sync(
        DialogTurnMsg(
            tick=30,
            dialog_id="d0",
            speaker_id="a_rikyu_001",
            addressee_id="a_kant_001",
            utterance="wabi sabi ichigo ichie",
            turn_index=2,
        ),
        speaker_persona_id="rikyu",
        addressee_persona_id="kant",
    )
    store.add_bias_event_sync(
        tick=10,
        agent_id="a_kant_001",
        persona_id="kant",
        from_zone="agora",
        to_zone="peripatos",
        bias_p=0.2,
    )

    result = aggregate(db_path)
    assert result["turn_count"] == 3
    assert result["bias_event_count"] == 1
    assert result["num_agents"] == 2
    # run_duration derived from tick delta (30 - 10 = 20 ticks * 10s = 200s).
    assert result["run_duration_s"] == pytest.approx(200.0)
    # Kant's two identical turns -> self_repetition close to 1.0 (only kant votes).
    assert result["self_repetition_rate"] is not None
    assert result["self_repetition_rate"] == pytest.approx(1.0)
    # Cross-persona pair (kant vs rikyu) has no trigram overlap.
    assert result["cross_persona_echo_rate"] is not None
    assert result["cross_persona_echo_rate"] == pytest.approx(0.0)
    # bias_fired_rate is a positive finite number.
    assert result["bias_fired_rate"] is not None
    assert result["bias_fired_rate"] > 0
    assert result["affinity_trajectory"] is None
