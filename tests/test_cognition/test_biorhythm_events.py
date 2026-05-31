"""Tests for the M6-A-2b BiorhythmEvent firing in :class:`CognitionCycle`.

The cognition cycle compares the agent's fatigue / hunger before and after
the CSDG :func:`~erre_sandbox.cognition.state.advance_physical` half-step
and emits a :class:`~erre_sandbox.schemas.BiorhythmEvent` for every signal
that crossed the mid-band threshold. The event is appended to the tick's
observation stream so the LLM prompt (Step 5), FSM (Step 2.5 runs before
the emission — see design note) and reflector (Step 10) all see it.

Two layers covered:

* **Helper** — :func:`_detect_biorhythm_crossings` is exercised directly
  with hand-crafted :class:`Physical` snapshots.
* **Integration** — the cycle's ``step`` is driven with a fabricated
  ``Physical`` update and the resulting LLM user prompt is inspected for
  the rendered ``[biorhythm ...]`` line.
"""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from erre_sandbox.cognition import CognitionCycle
from erre_sandbox.cognition.cycle import (
    _detect_biorhythm_crossings,
    _detect_stress_crossing,
)
from erre_sandbox.schemas import (
    BiorhythmEvent,
    Cognitive,
    Physical,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from erre_sandbox.inference.ollama_adapter import OllamaChatClient
    from erre_sandbox.memory import EmbeddingClient, MemoryStore, Retriever
    from erre_sandbox.schemas import PersonaSpec


# ---------- Helper: _detect_biorhythm_crossings ----------


def test_detect_returns_empty_when_no_threshold_crossed() -> None:
    events = _detect_biorhythm_crossings(
        previous=Physical(fatigue=0.2, hunger=0.3),
        current=Physical(fatigue=0.25, hunger=0.35),
        agent_id="a_kant_001",
        tick=3,
    )
    assert events == []


@pytest.mark.parametrize(
    ("field", "prev", "curr", "expected_direction"),
    [
        ("fatigue", 0.40, 0.60, "up"),
        ("fatigue", 0.60, 0.40, "down"),
        ("hunger", 0.30, 0.80, "up"),
        ("hunger", 0.80, 0.30, "down"),
    ],
)
def test_detect_emits_event_on_mid_band_crossing(
    field: str,
    prev: float,
    curr: float,
    expected_direction: str,
) -> None:
    events = _detect_biorhythm_crossings(
        previous=Physical.model_validate({field: prev}),
        current=Physical.model_validate({field: curr}),
        agent_id="a_kant_001",
        tick=11,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, BiorhythmEvent)
    assert event.signal == field
    assert event.level_prev == pytest.approx(prev)
    assert event.level_now == pytest.approx(curr)
    assert event.threshold_crossed == expected_direction
    assert event.tick == 11
    assert event.agent_id == "a_kant_001"


def test_detect_emits_one_event_per_signal_crossed() -> None:
    """Both fatigue and hunger cross the mid band → two events emitted."""
    events = _detect_biorhythm_crossings(
        previous=Physical(fatigue=0.20, hunger=0.20),
        current=Physical(fatigue=0.80, hunger=0.80),
        agent_id="a_rikyu_001",
        tick=7,
    )
    assert {e.signal for e in events} == {"fatigue", "hunger"}
    assert {e.threshold_crossed for e in events} == {"up"}


def test_detect_does_not_emit_when_staying_above_threshold() -> None:
    events = _detect_biorhythm_crossings(
        previous=Physical(fatigue=0.60, hunger=0.60),
        current=Physical(fatigue=0.80, hunger=0.55),
        agent_id="a",
        tick=1,
    )
    # Neither signal crossed the 0.5 mid-band — they both remained above.
    assert events == []


# ---------- M6-A-2b: _detect_stress_crossing (Cognitive mid-band) ----------


def test_stress_crossing_up_emits_event() -> None:
    events = _detect_stress_crossing(
        previous=Cognitive(stress=0.30),
        current=Cognitive(stress=0.70),
        agent_id="a_kant_001",
        tick=5,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, BiorhythmEvent)
    assert event.signal == "stress"
    assert event.threshold_crossed == "up"
    assert event.level_prev == pytest.approx(0.30)
    assert event.level_now == pytest.approx(0.70)
    assert event.tick == 5
    assert event.agent_id == "a_kant_001"


def test_stress_crossing_down_emits_event() -> None:
    events = _detect_stress_crossing(
        previous=Cognitive(stress=0.80),
        current=Cognitive(stress=0.20),
        agent_id="a",
        tick=9,
    )
    assert len(events) == 1
    assert events[0].threshold_crossed == "down"


def test_stress_no_crossing_emits_nothing() -> None:
    events = _detect_stress_crossing(
        previous=Cognitive(stress=0.20),
        current=Cognitive(stress=0.25),
        agent_id="a",
        tick=1,
    )
    assert events == []


def test_stress_staying_above_threshold_emits_nothing() -> None:
    events = _detect_stress_crossing(
        previous=Cognitive(stress=0.70),
        current=Cognitive(stress=0.90),
        agent_id="a",
        tick=1,
    )
    assert events == []


# ---------- Integration: cycle emits via observation stream ----------


async def test_cycle_emits_biorhythm_into_llm_prompt(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    """End-to-end: fatigue crosses the mid band → rendered in user prompt."""
    # Agent starts well-rested.
    agent = make_agent_state(physical={"fatigue": 0.30, "hunger": 0.30})
    persona: PersonaSpec = make_persona_spec()

    # Patch advance_physical (imported at the top of cycle.py) to return a
    # fatigued Physical so the pre/post diff crosses mid-band deterministically
    # without caring about the real CSDG math.
    fatigued = Physical(fatigue=0.75, hunger=0.30)

    captured: list[dict[str, Any]] = []
    embedding = make_embedding_client()
    llm = make_chat_client(captured=captured)
    try:
        cycle = CognitionCycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            rng=Random(0),
        )
        with patch(
            "erre_sandbox.cognition.cycle.advance_physical",
            return_value=fatigued,
        ):
            await cycle.step(agent, persona, [])
    finally:
        await embedding.close()
        await llm.close()

    assert captured, "main cycle LLM call should have been captured"
    user_msg = [m for m in captured[0]["messages"] if m["role"] == "user"][-1]
    prompt = user_msg["content"]
    assert "[biorhythm fatigue:up]" in prompt
    # hunger did not cross — must not appear.
    assert "biorhythm hunger" not in prompt


async def test_cycle_skips_biorhythm_when_no_crossing(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    agent = make_agent_state(physical={"fatigue": 0.20, "hunger": 0.20})
    persona: PersonaSpec = make_persona_spec()

    captured: list[dict[str, Any]] = []
    embedding = make_embedding_client()
    llm = make_chat_client(captured=captured)
    try:
        cycle = CognitionCycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            rng=Random(0),
        )
        # Small increase but no threshold crossing.
        with patch(
            "erre_sandbox.cognition.cycle.advance_physical",
            return_value=Physical(fatigue=0.25, hunger=0.25),
        ):
            await cycle.step(agent, persona, [])
    finally:
        await embedding.close()
        await llm.close()

    user_msg = [m for m in captured[0]["messages"] if m["role"] == "user"][-1]
    assert "[biorhythm" not in user_msg["content"]


async def test_cycle_defers_stress_crossing_to_follow_up_observations(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
) -> None:
    """Stress crossings surface via ``CycleResult.follow_up_observations``."""
    agent = make_agent_state(cognitive={"stress": 0.30})
    persona: PersonaSpec = make_persona_spec()

    captured: list[dict[str, Any]] = []
    embedding = make_embedding_client()
    llm = make_chat_client(captured=captured)
    try:
        cycle = CognitionCycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            rng=Random(0),
        )
        # Force apply_llm_delta to return a stressed Cognitive so the
        # pre/post diff crosses the 0.5 mid-band.
        stressed = Cognitive(stress=0.80)
        with patch(
            "erre_sandbox.cognition.cycle.apply_llm_delta",
            return_value=stressed,
        ):
            result = await cycle.step(agent, persona, [])
    finally:
        await embedding.close()
        await llm.close()

    assert len(result.follow_up_observations) == 1
    event = result.follow_up_observations[0]
    assert isinstance(event, BiorhythmEvent)
    assert event.signal == "stress"
    assert event.threshold_crossed == "up"
    # tick is the POST-step tick so the event attaches to the tick it'll be
    # surfaced in (next cognition cycle).
    assert event.tick == agent.tick + 1
