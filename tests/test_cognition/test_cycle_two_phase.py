"""Cycle-level spy test for the Phase 4 two-phase locomotion knob.

Boolean causal-wiring at the *organ* boundary (Codex HIGH-1): a spy
``OllamaChatClient`` captures the resolved ``options`` (temperature / top_p /
repeat_penalty) actually sent to the backend, proving the injected
:class:`~erre_sandbox.erre.two_phase.TwoPhaseKnob` reaches
``llm.chat(sampling=...)`` — not just the pure helper (the ECL v1 silent-fail
lesson). It verifies:

* **off** (``two_phase_knob=None``) == the frozen ``locomotion_delta`` composition;
* **on + generation-phase mode** preserves the divergence baseline (== off);
* **on + evaluation-phase mode** inverts temp/top_p and lifts repeat_penalty —
  the sign flip = wiring fires, the "調合スイッチ" witnessed live.

A headroom base sampling (Codex HIGH-2) keeps the delta visible in the clamped
resolved payload. No effect size / detectability is measured — construction only.
"""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING, Any

import pytest

from erre_sandbox.cognition import CognitionCycle
from erre_sandbox.erre import TwoPhaseKnob
from erre_sandbox.erre.locomotion_sampling import (
    DEFAULT_LOCO_GAIN_P,
    DEFAULT_LOCO_GAIN_T,
)
from erre_sandbox.erre.two_phase import (
    TWO_PHASE_GAIN_P,
    TWO_PHASE_GAIN_R,
    TWO_PHASE_GAIN_T,
)
from erre_sandbox.schemas import ERREModeName

if TYPE_CHECKING:
    from collections.abc import Callable

    from erre_sandbox.inference.ollama_adapter import OllamaChatClient
    from erre_sandbox.memory import EmbeddingClient, MemoryStore, Retriever
    from erre_sandbox.schemas import PerceptionEvent

# Headroom base so neither the up (generation) nor down (evaluation) delta clamps.
_HEADROOM_SAMPLING = {"temperature": 0.7, "top_p": 0.7, "repeat_penalty": 1.0}
_LAM = 0.8


async def _resolved_options(
    *,
    mode: ERREModeName,
    two_phase_knob: TwoPhaseKnob | None,
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> dict[str, float]:
    """Run one cycle step and return the ``options`` the LLM actually received.

    Assumes exactly one chat call per step: the ``perception_event`` fixture has
    ``importance_hint`` below ``REFLECTION_IMPORTANCE_THRESHOLD`` and a non-reflective
    source zone, so no reflection LLM call fires. A future fixture that trips
    reflection would need to disambiguate the captured calls.
    """
    captured: list[dict[str, Any]] = []
    persona = make_persona_spec(default_sampling=_HEADROOM_SAMPLING)
    agent = make_agent_state(
        locomotion={"lam": _LAM},
        erre={"name": mode.value, "entered_at_tick": 0},
    )
    embedding = make_embedding_client()
    llm = make_chat_client(captured=captured)
    try:
        cycle = CognitionCycle(
            retriever=cognition_retriever,
            store=cognition_store,
            embedding=embedding,
            llm=llm,
            rng=Random(0),
            two_phase_knob=two_phase_knob,
        )
        await cycle.step(agent, persona, [perception_event])
    finally:
        await embedding.close()
        await llm.close()
    # Exactly the action LLM call (importance 0.4 < 1.5 and study zone is not
    # reflective, so no reflection LLM call is made).
    assert len(captured) == 1
    return captured[0]["options"]


async def test_knob_off_matches_frozen_locomotion_path(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    """off = base + (zero mode override) + the divergence-only locomotion_delta."""
    opts = await _resolved_options(
        mode=ERREModeName.CHASHITSU,
        two_phase_knob=None,
        make_agent_state=make_agent_state,
        make_persona_spec=make_persona_spec,
        make_chat_client=make_chat_client,
        make_embedding_client=make_embedding_client,
        cognition_store=cognition_store,
        cognition_retriever=cognition_retriever,
        perception_event=perception_event,
    )
    assert opts["temperature"] == pytest.approx(0.7 + DEFAULT_LOCO_GAIN_T * _LAM)
    assert opts["top_p"] == pytest.approx(0.7 + DEFAULT_LOCO_GAIN_P * _LAM)
    assert opts["repeat_penalty"] == pytest.approx(1.0)


async def test_generation_phase_preserves_divergence_baseline(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    """In a generation-phase mode the knob reproduces the off (divergence) payload."""
    common = {
        "mode": ERREModeName.PERIPATETIC,  # generation phase
        "make_agent_state": make_agent_state,
        "make_persona_spec": make_persona_spec,
        "make_chat_client": make_chat_client,
        "make_embedding_client": make_embedding_client,
        "cognition_store": cognition_store,
        "cognition_retriever": cognition_retriever,
        "perception_event": perception_event,
    }
    off = await _resolved_options(two_phase_knob=None, **common)
    on = await _resolved_options(two_phase_knob=TwoPhaseKnob(), **common)
    assert on["temperature"] == pytest.approx(off["temperature"])
    assert on["top_p"] == pytest.approx(off["top_p"])
    assert on["repeat_penalty"] == pytest.approx(off["repeat_penalty"])


async def test_evaluation_phase_inverts_sign_wiring_fires(
    make_agent_state: Callable[..., Any],
    make_persona_spec: Callable[..., Any],
    make_chat_client: Callable[..., OllamaChatClient],
    make_embedding_client: Callable[[], EmbeddingClient],
    cognition_store: MemoryStore,
    cognition_retriever: Retriever,
    perception_event: PerceptionEvent,
) -> None:
    """In an evaluation-phase mode the knob inverts temp/top_p and lifts rp (fires)."""
    common = {
        "mode": ERREModeName.CHASHITSU,  # evaluation phase
        "make_agent_state": make_agent_state,
        "make_persona_spec": make_persona_spec,
        "make_chat_client": make_chat_client,
        "make_embedding_client": make_embedding_client,
        "cognition_store": cognition_store,
        "cognition_retriever": cognition_retriever,
        "perception_event": perception_event,
    }
    off = await _resolved_options(two_phase_knob=None, **common)
    on = await _resolved_options(two_phase_knob=TwoPhaseKnob(), **common)
    # Sign flip = wiring fires: same |λ|, convergence instead of divergence.
    assert on["temperature"] < off["temperature"]
    assert on["top_p"] < off["top_p"]
    assert on["repeat_penalty"] > off["repeat_penalty"]
    # Exact resolved values (base 0.7 / 0.7 / 1.0, λ=0.8, evaluation σ=(-,-,+)).
    assert on["temperature"] == pytest.approx(0.7 - TWO_PHASE_GAIN_T * _LAM)
    assert on["top_p"] == pytest.approx(0.7 - TWO_PHASE_GAIN_P * _LAM)
    assert on["repeat_penalty"] == pytest.approx(1.0 + TWO_PHASE_GAIN_R * _LAM)
