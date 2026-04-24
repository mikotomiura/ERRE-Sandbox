"""Unit tests for :mod:`erre_sandbox.cognition.prompting`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from erre_sandbox.cognition.prompting import (
    RESPONSE_SCHEMA_HINT,
    build_system_prompt,
    build_user_prompt,
    format_memories,
)
from erre_sandbox.schemas import MemoryEntry, MemoryKind, ProximityEvent, Zone

if TYPE_CHECKING:
    from erre_sandbox.schemas import AgentState, PersonaSpec


@dataclass(frozen=True)
class _FakeRanked:
    entry: MemoryEntry
    strength: float
    cosine_sim: float = 0.9


def _mem(content: str, *, kind: MemoryKind = MemoryKind.EPISODIC) -> MemoryEntry:
    return MemoryEntry(
        id=f"m_{hash(content) & 0xFFFF}",
        agent_id="a_kant_001",
        kind=kind,
        content=content,
        importance=0.5,
        created_at=datetime.now(tz=UTC),
    )


def test_system_prompt_contains_persona_habits(
    make_persona_spec,
    agent_state_kant: AgentState,
) -> None:
    persona: PersonaSpec = make_persona_spec()
    prompt = build_system_prompt(persona, agent_state_kant)
    assert "15:30 daily walk" in prompt
    assert "fact" in prompt.lower()
    assert persona.display_name in prompt


def test_system_prompt_contains_personality_fields(
    make_persona_spec,
    agent_state_kant: AgentState,
) -> None:
    """M7 A1: Big Five + wabi/ma_sense must appear in the persona block.

    Without this, the LLM has no handle on per-agent personality differences
    and all three agents' Reasoning panels collapse to the same voice
    (observed live on 2026-04-22). The default fixture is Kant with
    conscientiousness=0.95, openness=0.85, so the prompt must reflect those.
    """
    persona: PersonaSpec = make_persona_spec()
    prompt = build_system_prompt(persona, agent_state_kant)
    # Big Five keys present
    assert "openness=" in prompt
    assert "conscientiousness=" in prompt
    assert "extraversion=" in prompt
    assert "agreeableness=" in prompt
    assert "neuroticism=" in prompt
    # ERRE-specific aesthetic traits present
    assert "wabi=" in prompt
    assert "ma_sense=" in prompt
    # Kant fixture values flow through
    assert "openness=0.85" in prompt
    assert "conscientiousness=0.95" in prompt


def test_persona_block_differentiates_two_personas(
    make_persona_spec,
    agent_state_kant: AgentState,
) -> None:
    """Two personas with different Big Five must produce distinct prompts.

    Guard against a future refactor that accidentally drops personality
    into a shared constant.
    """
    kant = make_persona_spec(
        persona_id="kant",
        personality={"openness": 0.85, "conscientiousness": 0.95},
    )
    rikyu = make_persona_spec(
        persona_id="rikyu",
        display_name="Sen no Rikyu",
        personality={"openness": 0.60, "wabi": 0.95, "ma_sense": 0.90},
    )
    kant_prompt = build_system_prompt(kant, agent_state_kant)
    rikyu_prompt = build_system_prompt(rikyu, agent_state_kant)
    # Numeric signatures must differ
    assert "openness=0.85" in kant_prompt
    assert "openness=0.60" in rikyu_prompt
    assert "wabi=0.95" in rikyu_prompt
    assert "wabi=0.95" not in kant_prompt


def test_system_prompt_starts_with_common_prefix(
    make_persona_spec,
    agent_state_kant: AgentState,
) -> None:
    prompt = build_system_prompt(make_persona_spec(), agent_state_kant)
    # RadixAttention optimisation: common prefix must precede persona details.
    common_idx = prompt.find("ERRE-Sandbox")
    persona_idx = prompt.find("Immanuel Kant")
    assert common_idx < persona_idx


def test_format_memories_sorted_by_strength() -> None:
    memories = [
        _FakeRanked(_mem("weak memory"), strength=0.2),
        _FakeRanked(_mem("strong memory"), strength=0.9),
        _FakeRanked(_mem("mid memory"), strength=0.5),
    ]
    rendered = format_memories(memories)  # type: ignore[arg-type]
    # Strongest appears on the first line.
    first_line = rendered.splitlines()[0]
    assert "strong memory" in first_line


def test_format_memories_empty() -> None:
    out = format_memories([])
    assert "(no relevant memories)" in out


def test_build_user_prompt_embeds_recent_observations(
    perception_event,
    speech_event,
) -> None:
    prompt = build_user_prompt(
        [perception_event, speech_event],
        memories=[],
    )
    assert "library shelves" in prompt  # perception content
    assert "guten Tag" in prompt  # speech utterance
    assert RESPONSE_SCHEMA_HINT.splitlines()[0] in prompt


def test_build_user_prompt_respects_recent_limit(perception_event) -> None:
    many = [perception_event] * 10
    prompt = build_user_prompt(many, memories=[], recent_limit=3)
    # Only the last 3 perception lines should appear.
    count = prompt.count("[perception]")
    assert count == 3


def test_build_user_prompt_zone_transition_formatted(zone_entry_event) -> None:
    prompt = build_user_prompt([zone_entry_event], memories=[])
    assert "study -> peripatos" in prompt


# ---------- M6-A-2b: window 5→10 default + proximity per-type clamp --------


def test_build_user_prompt_default_window_is_ten(perception_event) -> None:
    """The default window widened from 5 to 10 in M6-A-2b."""
    many = [perception_event] * 15
    prompt = build_user_prompt(many, memories=[])
    assert prompt.count("[perception]") == 10


def test_build_user_prompt_clamps_proximity_to_two_latest() -> None:
    def _prox(i: int) -> ProximityEvent:
        return ProximityEvent(
            tick=i,
            agent_id="a_kant_001",
            other_agent_id=f"a_peer_{i:03d}",
            distance_prev=7.0,
            distance_now=3.0,
            crossing="enter",
        )

    # Five proximity events, all inside the default window of 10.
    observations = [_prox(i) for i in range(5)]
    prompt = build_user_prompt(observations, memories=[])
    # Only the two most recent should survive the clamp.
    assert prompt.count("[proximity enter]") == 2
    assert "a_peer_003" in prompt
    assert "a_peer_004" in prompt
    # The oldest three must be gone.
    for i in range(3):
        assert f"a_peer_{i:03d}" not in prompt


def test_build_user_prompt_proximity_clamp_preserves_other_types(
    perception_event,
    zone_entry_event,
) -> None:
    """Clamping proximity must not drop non-proximity observations."""
    prox = [
        ProximityEvent(
            tick=i,
            agent_id="a_kant_001",
            other_agent_id=f"a_peer_{i:03d}",
            distance_prev=7.0,
            distance_now=3.0,
            crossing="enter",
        )
        for i in range(4)
    ]
    observations = [*prox, perception_event, zone_entry_event]
    prompt = build_user_prompt(observations, memories=[])
    assert prompt.count("[proximity enter]") == 2
    assert "library shelves" in prompt  # perception preserved
    assert "study -> peripatos" in prompt  # zone transition preserved


def test_zone_value_exposed_in_system_prompt(
    make_persona_spec,
    agent_state_kant: AgentState,
) -> None:
    prompt = build_system_prompt(make_persona_spec(), agent_state_kant)
    assert Zone.STUDY.value in prompt
