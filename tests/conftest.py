"""Shared pytest fixtures for ERRE-Sandbox (T08 test-schemas onward).

Callable factories let tests customise any field of ``AgentState`` /
``PersonaSpec`` / ``ControlEnvelope`` while convenience fixtures cover the
most common case (Kant in ``study`` at tick 0). Phase P tests (T10-T14)
reuse this baseline to avoid re-inventing construction boilerplate.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from erre_sandbox.schemas import (
    AgentState,
    AgentUpdateMsg,
    AnimationMsg,
    CognitiveHabit,
    ControlEnvelope,
    DialogCloseMsg,
    DialogInitiateMsg,
    DialogTurnMsg,
    ErrorMsg,
    HabitFlag,
    HandshakeMsg,
    MoveMsg,
    PersonalityTraits,
    PersonaSpec,
    SpeechMsg,
    WorldTickMsg,
    Zone,
)

MakeAgentState = Callable[..., AgentState]
MakePersonaSpec = Callable[..., PersonaSpec]
MakeEnvelope = Callable[..., ControlEnvelope]


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``overrides`` into ``base``.

    Nested dicts are merged key-by-key so callers can override only the
    fields they care about (e.g. ``make_agent_state(position={"zone": "peripatos"})``
    keeps the default ``x/y/z`` coordinates).
    """
    merged = dict(base)
    for key, value in overrides.items():
        existing = merged.get(key)
        if isinstance(value, dict) and isinstance(existing, dict):
            merged[key] = _deep_merge(existing, value)
        else:
            merged[key] = value
    return merged


# ---------- AgentState ---------------------------------------------------


@pytest.fixture
def make_agent_state() -> MakeAgentState:
    """Factory: Kant in ``study`` / ``deep_work`` at tick 0 by default.

    Any field can be overridden. ``overrides`` are shallow-merged into a
    base dict passed to ``AgentState.model_validate``, so nested values
    should be supplied as full sub-dicts.
    """

    def _factory(**overrides: Any) -> AgentState:
        base: dict[str, Any] = {
            "agent_id": "a_kant_001",
            "persona_id": "kant",
            "tick": 0,
            "position": {"x": 0.0, "y": 0.0, "z": 0.0, "zone": "study"},
            "erre": {"name": "deep_work", "entered_at_tick": 0},
        }
        return AgentState.model_validate(_deep_merge(base, overrides))

    return _factory


@pytest.fixture
def agent_state_kant(make_agent_state: MakeAgentState) -> AgentState:
    """Convenience: Kant in ``study`` / ``deep_work`` at tick 0."""
    return make_agent_state()


# ---------- PersonaSpec --------------------------------------------------


@pytest.fixture
def make_persona_spec() -> MakePersonaSpec:
    """Factory: minimal Kant-shaped ``PersonaSpec`` (fact flag, study+peripatos)."""

    def _factory(**overrides: Any) -> PersonaSpec:
        base: dict[str, Any] = {
            "persona_id": "kant",
            "display_name": "Immanuel Kant",
            "era": "1724-1804",
            "primary_corpus_refs": ["kuehn2001"],
            "personality": PersonalityTraits(
                conscientiousness=0.95,
                openness=0.85,
            ).model_dump(),
            "cognitive_habits": [
                CognitiveHabit(
                    description="15:30 daily walk",
                    source="kuehn2001",
                    flag=HabitFlag.FACT,
                    mechanism="DMN activation via rhythmic locomotion",
                    trigger_zone=Zone.PERIPATOS,
                ).model_dump(mode="json"),
            ],
            "preferred_zones": ["study", "peripatos"],
        }
        return PersonaSpec.model_validate(_deep_merge(base, overrides))

    return _factory


# ---------- ControlEnvelope ---------------------------------------------


@pytest.fixture
def make_envelope() -> MakeEnvelope:
    """Factory: generate any ``ControlEnvelope`` member by ``kind``.

    Supported kinds: ``handshake``, ``agent_update``, ``speech``, ``move``,
    ``animation``, ``world_tick``, ``error``. Unknown kinds raise ``ValueError``.
    Required payload for each kind can be overridden; sensible defaults mirror
    the ``fixtures/control_envelope/*.json`` scenario (tick 42, Kant).
    """

    def _factory(kind: str, **overrides: Any) -> ControlEnvelope:
        tick = overrides.pop("tick", 0 if kind == "handshake" else 42)
        builder = _ENVELOPE_BUILDERS.get(kind)
        if builder is None:
            msg = f"unknown envelope kind: {kind!r}"
            raise ValueError(msg)
        envelope = builder(tick, overrides)
        if overrides:
            msg = (
                f"unexpected overrides for {kind!r}: {sorted(overrides)} "
                f"— this is likely a typo."
            )
            raise ValueError(msg)
        return envelope

    return _factory


def _build_handshake(tick: int, overrides: dict[str, Any]) -> HandshakeMsg:
    return HandshakeMsg(
        tick=tick,
        peer=overrides.pop("peer", "g-gear"),
        capabilities=overrides.pop(
            "capabilities",
            ["handshake", "agent_update", "speech"],
        ),
    )


def _build_agent_update(tick: int, overrides: dict[str, Any]) -> AgentUpdateMsg:
    state = overrides.pop("agent_state", None)
    if state is None:
        msg = "agent_update requires agent_state (use make_agent_state)"
        raise ValueError(msg)
    return AgentUpdateMsg(tick=tick, agent_state=state)


def _build_speech(tick: int, overrides: dict[str, Any]) -> SpeechMsg:
    return SpeechMsg(
        tick=tick,
        agent_id=overrides.pop("agent_id", "a_kant_001"),
        utterance=overrides.pop("utterance", "..."),
        zone=overrides.pop("zone", Zone.PERIPATOS),
    )


def _build_move(tick: int, overrides: dict[str, Any]) -> MoveMsg:
    return MoveMsg(
        tick=tick,
        agent_id=overrides.pop("agent_id", "a_kant_001"),
        target=overrides.pop(
            "target",
            {"x": 1.0, "y": 0.0, "z": 0.0, "zone": "peripatos"},
        ),
        speed=overrides.pop("speed", 1.3),
    )


def _build_animation(tick: int, overrides: dict[str, Any]) -> AnimationMsg:
    return AnimationMsg(
        tick=tick,
        agent_id=overrides.pop("agent_id", "a_kant_001"),
        animation_name=overrides.pop("animation_name", "walk"),
        loop=overrides.pop("loop", True),
    )


def _build_world_tick(tick: int, overrides: dict[str, Any]) -> WorldTickMsg:
    return WorldTickMsg(tick=tick, active_agents=overrides.pop("active_agents", 1))


def _build_error(tick: int, overrides: dict[str, Any]) -> ErrorMsg:
    return ErrorMsg(
        tick=tick,
        code=overrides.pop("code", "UNKNOWN_KIND"),
        detail=overrides.pop("detail", "test error"),
    )


def _build_dialog_initiate(tick: int, overrides: dict[str, Any]) -> DialogInitiateMsg:
    return DialogInitiateMsg(
        tick=tick,
        initiator_agent_id=overrides.pop("initiator_agent_id", "a_kant_001"),
        target_agent_id=overrides.pop("target_agent_id", "a_nietzsche_001"),
        zone=overrides.pop("zone", Zone.PERIPATOS),
    )


def _build_dialog_turn(tick: int, overrides: dict[str, Any]) -> DialogTurnMsg:
    return DialogTurnMsg(
        tick=tick,
        dialog_id=overrides.pop("dialog_id", "d_kant_nietzsche_0001"),
        speaker_id=overrides.pop("speaker_id", "a_kant_001"),
        addressee_id=overrides.pop("addressee_id", "a_nietzsche_001"),
        utterance=overrides.pop("utterance", "..."),
    )


def _build_dialog_close(tick: int, overrides: dict[str, Any]) -> DialogCloseMsg:
    return DialogCloseMsg(
        tick=tick,
        dialog_id=overrides.pop("dialog_id", "d_kant_nietzsche_0001"),
        reason=overrides.pop("reason", "completed"),
    )


_ENVELOPE_BUILDERS: dict[str, Callable[[int, dict[str, Any]], ControlEnvelope]] = {
    "handshake": _build_handshake,
    "agent_update": _build_agent_update,
    "speech": _build_speech,
    "move": _build_move,
    "animation": _build_animation,
    "world_tick": _build_world_tick,
    "error": _build_error,
    "dialog_initiate": _build_dialog_initiate,
    "dialog_turn": _build_dialog_turn,
    "dialog_close": _build_dialog_close,
}
