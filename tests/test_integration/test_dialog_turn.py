"""Unit + integration tests for :class:`OllamaDialogTurnGenerator`.

The LLM is mocked via ``httpx.MockTransport`` so these tests stay fast,
deterministic, and do not touch G-GEAR. The mock lets us inspect the exact
request body (for ``think=False`` / ``num_predict`` / ``stop`` assertions)
and inject pathological responses for the M5 spike hallucination regression
guard (empty string, split-utterance, oversized, language-leak).

Coverage maps to :file:`.steering/20260421-m5-dialog-turn-generator/design.md`
§テスト戦略 → 11 cases.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from erre_sandbox.inference import OllamaChatClient
from erre_sandbox.integration.dialog import InMemoryDialogScheduler
from erre_sandbox.integration.dialog_turn import (
    OllamaDialogTurnGenerator,
    _sanitize_utterance,
)
from erre_sandbox.schemas import DialogTurnMsg, Zone

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from erre_sandbox.schemas import AgentState, ControlEnvelope, PersonaSpec


# ---------------------------------------------------------------------------
# Mock wire fixtures
# ---------------------------------------------------------------------------


def _ok_transport(
    captured: list[dict[str, Any]],
    responses: Iterator[str],
) -> httpx.MockTransport:
    """Return a transport that records request bodies and yields ``responses``."""

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        try:
            content = next(responses)
        except StopIteration:  # pragma: no cover — test misuse
            content = ""
        return httpx.Response(
            httpx.codes.OK,
            json={
                "model": "qwen3:8b",
                "message": {"role": "assistant", "content": content},
                "done": True,
                "done_reason": "stop",
                "total_duration": 1_500_000_000,
                "eval_count": 42,
                "prompt_eval_count": 128,
            },
        )

    return httpx.MockTransport(handler)


def _always(content: str) -> Iterator[str]:
    while True:
        yield content


def _raising_transport(exc: Exception) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
        raise exc

    return httpx.MockTransport(handler)


def _make_client(transport: httpx.MockTransport) -> OllamaChatClient:
    return OllamaChatClient(
        client=httpx.AsyncClient(
            base_url=OllamaChatClient.DEFAULT_ENDPOINT,
            transport=transport,
        ),
    )


# ---------------------------------------------------------------------------
# Persona + state fixtures (co-located so ad-hoc overrides stay readable)
# ---------------------------------------------------------------------------


@pytest.fixture
def kant_state(
    make_agent_state: Callable[..., AgentState],
) -> AgentState:
    return make_agent_state(
        agent_id="a_kant_001",
        persona_id="kant",
        position={"x": 0.0, "y": 0.0, "z": 0.0, "zone": "peripatos"},
        erre={"name": "peripatetic", "entered_at_tick": 0},
    )


@pytest.fixture
def rikyu_state(
    make_agent_state: Callable[..., AgentState],
) -> AgentState:
    return make_agent_state(
        agent_id="a_rikyu_001",
        persona_id="rikyu",
        position={"x": 0.5, "y": 0.0, "z": 0.0, "zone": "peripatos"},
        erre={"name": "peripatetic", "entered_at_tick": 0},
    )


@pytest.fixture
def kant_persona(
    make_persona_spec: Callable[..., PersonaSpec],
) -> PersonaSpec:
    return make_persona_spec()


@pytest.fixture
def rikyu_persona(
    make_persona_spec: Callable[..., PersonaSpec],
) -> PersonaSpec:
    return make_persona_spec(
        persona_id="rikyu",
        display_name="千 利休",
        era="1522-1591",
        preferred_zones=["chashitsu", "garden"],
    )


@pytest.fixture
def personas(
    kant_persona: PersonaSpec,
    rikyu_persona: PersonaSpec,
) -> dict[str, PersonaSpec]:
    return {
        kant_persona.persona_id: kant_persona,
        rikyu_persona.persona_id: rikyu_persona,
    }


# ---------------------------------------------------------------------------
# 1. Happy path — 4 sequential turns produce turn_index=0..3
# ---------------------------------------------------------------------------


async def test_generate_turn_returns_monotonic_turn_index(
    kant_state: AgentState,
    rikyu_state: AgentState,
    kant_persona: PersonaSpec,
    rikyu_persona: PersonaSpec,
    personas: dict[str, PersonaSpec],
) -> None:
    captured: list[dict[str, Any]] = []
    responses = iter(["turn zero.", "turn one.", "turn two.", "turn three."])
    async with _make_client(_ok_transport(captured, responses)) as llm:
        gen = OllamaDialogTurnGenerator(llm=llm, personas=personas)
        transcript: list[DialogTurnMsg] = []
        speakers = (kant_state, rikyu_state, kant_state, rikyu_state)
        speaker_personas = (kant_persona, rikyu_persona, kant_persona, rikyu_persona)
        addressees = (rikyu_state, kant_state, rikyu_state, kant_state)
        for i, (sp_state, sp_persona, ad_state) in enumerate(
            zip(speakers, speaker_personas, addressees, strict=True),
        ):
            msg = await gen.generate_turn(
                dialog_id="d_test_001",
                speaker_state=sp_state,
                speaker_persona=sp_persona,
                addressee_state=ad_state,
                transcript=tuple(transcript),
                world_tick=10 + i,
            )
            assert msg is not None
            assert msg.turn_index == i
            assert msg.dialog_id == "d_test_001"
            assert msg.speaker_id == sp_state.agent_id
            assert msg.addressee_id == ad_state.agent_id
            transcript.append(msg)

    assert [t.speaker_id for t in transcript] == [
        "a_kant_001",
        "a_rikyu_001",
        "a_kant_001",
        "a_rikyu_001",
    ]


# ---------------------------------------------------------------------------
# 2. Exhausted close — orchestrator-equivalent code emits reason='exhausted'
#     when len(transcript) >= dialog_turn_budget, using scheduler.transcript_of
# ---------------------------------------------------------------------------


async def test_budget_reached_triggers_exhausted_close(
    kant_state: AgentState,
    rikyu_state: AgentState,
) -> None:
    emitted: list[ControlEnvelope] = []
    scheduler = InMemoryDialogScheduler(envelope_sink=emitted.append)
    init_env = scheduler.schedule_initiate(
        initiator_id=kant_state.agent_id,
        target_id=rikyu_state.agent_id,
        zone=Zone.PERIPATOS,
        tick=0,
    )
    assert init_env is not None
    # ``DialogInitiateMsg`` does not carry the allocated dialog_id — the
    # scheduler assigns it internally. Retrieve it via the read accessor.
    dialog_id = scheduler.get_dialog_id(kant_state.agent_id, rikyu_state.agent_id)
    assert dialog_id is not None

    # Simulate the orchestrator's budget check: feed six turns into the
    # scheduler, then the orchestrator's "next tick" computation reads
    # ``len(scheduler.transcript_of(did)) >= budget`` and closes with
    # ``reason='exhausted'``.
    for i in range(6):
        scheduler.record_turn(
            DialogTurnMsg(
                tick=1 + i,
                dialog_id=dialog_id,
                speaker_id=kant_state.agent_id if i % 2 == 0 else rikyu_state.agent_id,
                addressee_id=rikyu_state.agent_id
                if i % 2 == 0
                else kant_state.agent_id,
                utterance=f"turn {i}",
                turn_index=i,
            ),
        )

    budget = kant_state.cognitive.dialog_turn_budget
    assert len(scheduler.transcript_of(dialog_id)) >= budget
    close_env = scheduler.close_dialog(dialog_id, reason="exhausted")
    assert close_env.reason == "exhausted"
    # Contract (see ``integration/dialog.py``): the scheduler only emits
    # envelopes via the sink from ``schedule_initiate`` and ``close_dialog``.
    # ``record_turn`` accumulates transcript state silently — the gateway is
    # expected to route the turn envelope on its own when the generator
    # returns it. So the sink here sees exactly initiate + close.
    kinds = [env.kind for env in emitted]
    assert kinds == ["dialog_initiate", "dialog_close"]
    assert emitted[-1].reason == "exhausted"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# 3. LLM unreachable → generator returns None (no exception)
# ---------------------------------------------------------------------------


async def test_generate_turn_returns_none_on_ollama_unavailable(
    kant_state: AgentState,
    rikyu_state: AgentState,
    kant_persona: PersonaSpec,
    personas: dict[str, PersonaSpec],
) -> None:
    transport = _raising_transport(httpx.ConnectError("refused"))
    async with _make_client(transport) as llm:
        gen = OllamaDialogTurnGenerator(llm=llm, personas=personas)
        result = await gen.generate_turn(
            dialog_id="d_fail_001",
            speaker_state=kant_state,
            speaker_persona=kant_persona,
            addressee_state=rikyu_state,
            transcript=(),
            world_tick=0,
        )
    assert result is None


# ---------------------------------------------------------------------------
# 4. Empty response → generator returns None
# ---------------------------------------------------------------------------


async def test_generate_turn_returns_none_on_empty_content(
    kant_state: AgentState,
    rikyu_state: AgentState,
    kant_persona: PersonaSpec,
    personas: dict[str, PersonaSpec],
) -> None:
    captured: list[dict[str, Any]] = []
    async with _make_client(_ok_transport(captured, _always(""))) as llm:
        gen = OllamaDialogTurnGenerator(llm=llm, personas=personas)
        result = await gen.generate_turn(
            dialog_id="d_empty",
            speaker_state=kant_state,
            speaker_persona=kant_persona,
            addressee_state=rikyu_state,
            transcript=(),
            world_tick=0,
        )
    assert result is None


# ---------------------------------------------------------------------------
# 5. Multi-utterance ("A.\n\nB.") → only the first is kept
# ---------------------------------------------------------------------------


async def test_generate_turn_splits_multi_utterance(
    kant_state: AgentState,
    rikyu_state: AgentState,
    kant_persona: PersonaSpec,
    personas: dict[str, PersonaSpec],
) -> None:
    captured: list[dict[str, Any]] = []
    raw = "The mind seeks truth.\n\nYet we must also rest."
    async with _make_client(_ok_transport(captured, _always(raw))) as llm:
        gen = OllamaDialogTurnGenerator(llm=llm, personas=personas)
        msg = await gen.generate_turn(
            dialog_id="d_split",
            speaker_state=kant_state,
            speaker_persona=kant_persona,
            addressee_state=rikyu_state,
            transcript=(),
            world_tick=0,
        )
    assert msg is not None
    assert msg.utterance == "The mind seeks truth."


# ---------------------------------------------------------------------------
# 6. Oversized response → truncated to 160 chars + "…"
# ---------------------------------------------------------------------------


async def test_generate_turn_truncates_hard_cap(
    kant_state: AgentState,
    rikyu_state: AgentState,
    kant_persona: PersonaSpec,
    personas: dict[str, PersonaSpec],
) -> None:
    raw = "x" * 200
    captured: list[dict[str, Any]] = []
    async with _make_client(_ok_transport(captured, _always(raw))) as llm:
        gen = OllamaDialogTurnGenerator(llm=llm, personas=personas)
        msg = await gen.generate_turn(
            dialog_id="d_long",
            speaker_state=kant_state,
            speaker_persona=kant_persona,
            addressee_state=rikyu_state,
            transcript=(),
            world_tick=0,
        )
    assert msg is not None
    assert msg.utterance == ("x" * 160) + "…"


# ---------------------------------------------------------------------------
# 7. Payload contains think=False at top level (not in options)
# ---------------------------------------------------------------------------


async def test_generate_turn_sends_think_false_top_level(
    kant_state: AgentState,
    rikyu_state: AgentState,
    kant_persona: PersonaSpec,
    personas: dict[str, PersonaSpec],
) -> None:
    captured: list[dict[str, Any]] = []
    async with _make_client(_ok_transport(captured, _always("ok."))) as llm:
        gen = OllamaDialogTurnGenerator(llm=llm, personas=personas)
        await gen.generate_turn(
            dialog_id="d_think",
            speaker_state=kant_state,
            speaker_persona=kant_persona,
            addressee_state=rikyu_state,
            transcript=(),
            world_tick=0,
        )
    body = captured[0]
    assert body["think"] is False
    assert "think" not in body["options"]


# ---------------------------------------------------------------------------
# 8. Payload options carry num_predict=120 and stop=["\n\n"]
# ---------------------------------------------------------------------------


async def test_generate_turn_sends_spike_derived_options(
    kant_state: AgentState,
    rikyu_state: AgentState,
    kant_persona: PersonaSpec,
    personas: dict[str, PersonaSpec],
) -> None:
    captured: list[dict[str, Any]] = []
    async with _make_client(_ok_transport(captured, _always("ok."))) as llm:
        gen = OllamaDialogTurnGenerator(llm=llm, personas=personas)
        await gen.generate_turn(
            dialog_id="d_opts",
            speaker_state=kant_state,
            speaker_persona=kant_persona,
            addressee_state=rikyu_state,
            transcript=(),
            world_tick=0,
        )
    options = captured[0]["options"]
    assert options["num_predict"] == 120
    assert options["stop"] == ["\n\n"]


# ---------------------------------------------------------------------------
# 9. Per-persona language hint appears in the system prompt
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("persona_id", "expected_hint"),
    [
        ("kant", "Respond in English."),
        ("rikyu", "日本語で応答せよ"),
    ],
)
async def test_generate_turn_injects_lang_hint(
    persona_id: str,
    expected_hint: str,
    make_agent_state: Callable[..., AgentState],
    personas: dict[str, PersonaSpec],
) -> None:
    speaker_state = make_agent_state(
        agent_id=f"a_{persona_id}_001",
        persona_id=persona_id,
        position={"x": 0.0, "y": 0.0, "z": 0.0, "zone": "peripatos"},
        erre={"name": "peripatetic", "entered_at_tick": 0},
    )
    speaker_persona = personas[persona_id]
    addressee_state = make_agent_state(
        agent_id="a_other_001",
        persona_id="kant" if persona_id != "kant" else "rikyu",
        position={"x": 1.0, "y": 0.0, "z": 0.0, "zone": "peripatos"},
        erre={"name": "peripatetic", "entered_at_tick": 0},
    )
    captured: list[dict[str, Any]] = []
    async with _make_client(_ok_transport(captured, _always("ok."))) as llm:
        gen = OllamaDialogTurnGenerator(llm=llm, personas=personas)
        await gen.generate_turn(
            dialog_id="d_lang",
            speaker_state=speaker_state,
            speaker_persona=speaker_persona,
            addressee_state=addressee_state,
            transcript=(),
            world_tick=0,
        )
    system_prompt = captured[0]["messages"][0]["content"]
    assert expected_hint in system_prompt


# ---------------------------------------------------------------------------
# 10. turn_index=0/1 → no anti-repeat instruction; turn_index>=2 → present
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("prior_turns", "expect_anti_repeat"),
    [
        (0, False),
        (1, False),
        (2, True),
        (5, True),
    ],
)
async def test_generate_turn_anti_repeat_bounded_by_turn_index(
    prior_turns: int,
    expect_anti_repeat: bool,  # noqa: FBT001 — parametrize fixture value, not API
    kant_state: AgentState,
    rikyu_state: AgentState,
    kant_persona: PersonaSpec,
    personas: dict[str, PersonaSpec],
) -> None:
    transcript = tuple(
        DialogTurnMsg(
            tick=i,
            dialog_id="d_ar",
            speaker_id=kant_state.agent_id if i % 2 == 0 else rikyu_state.agent_id,
            addressee_id=rikyu_state.agent_id if i % 2 == 0 else kant_state.agent_id,
            utterance=f"prior turn {i}",
            turn_index=i,
        )
        for i in range(prior_turns)
    )
    captured: list[dict[str, Any]] = []
    async with _make_client(_ok_transport(captured, _always("next."))) as llm:
        gen = OllamaDialogTurnGenerator(llm=llm, personas=personas)
        await gen.generate_turn(
            dialog_id="d_ar",
            speaker_state=kant_state,
            speaker_persona=kant_persona,
            addressee_state=rikyu_state,
            transcript=transcript,
            world_tick=prior_turns,
        )
    user_prompt = captured[0]["messages"][1]["content"]
    has_anti_repeat = "does NOT repeat" in user_prompt
    assert has_anti_repeat is expect_anti_repeat


# ---------------------------------------------------------------------------
# 11. Addressee display_name is resolved from the persona registry
# ---------------------------------------------------------------------------


async def test_generate_turn_uses_addressee_display_name_from_registry(
    kant_state: AgentState,
    rikyu_state: AgentState,
    kant_persona: PersonaSpec,
    rikyu_persona: PersonaSpec,
    personas: dict[str, PersonaSpec],
) -> None:
    captured: list[dict[str, Any]] = []
    async with _make_client(_ok_transport(captured, _always("ok."))) as llm:
        gen = OllamaDialogTurnGenerator(llm=llm, personas=personas)
        await gen.generate_turn(
            dialog_id="d_display",
            speaker_state=kant_state,
            speaker_persona=kant_persona,
            addressee_state=rikyu_state,
            transcript=(),
            world_tick=0,
        )
    system_prompt = captured[0]["messages"][0]["content"]
    assert rikyu_persona.display_name in system_prompt
    # Degradation check: if the persona isn't registered, the generator must
    # fall back to agent_id rather than raising.
    captured.clear()
    async with _make_client(_ok_transport(captured, _always("ok."))) as llm2:
        gen_empty = OllamaDialogTurnGenerator(llm=llm2, personas={})
        await gen_empty.generate_turn(
            dialog_id="d_fallback",
            speaker_state=kant_state,
            speaker_persona=kant_persona,
            addressee_state=rikyu_state,
            transcript=(),
            world_tick=0,
        )
    fallback_prompt = captured[0]["messages"][0]["content"]
    assert rikyu_state.agent_id in fallback_prompt


# ---------------------------------------------------------------------------
# 12. _sanitize_utterance direct tests — regression guard for the 6-step
#     pipeline called by generate_turn (strip → split → control-char strip →
#     collapse → empty → truncate).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("hello.", "hello."),
        ("", None),
        ("   ", None),
        ("\n\n\n", None),
        ("  padded  text  ", "padded text"),
        ("multi\nline\ntext", "multi line text"),
        ("A.\n\nB.", "A."),  # pattern 5 split
        ("x" * 160, "x" * 160),  # boundary: no truncation
        ("x" * 161, ("x" * 160) + "…"),  # boundary: truncated with ellipsis
        ("x" * 300, ("x" * 160) + "…"),
        ("\x1b[31mred\x1b[0m alert", "red alert"),  # ANSI CSI scrub
        ("bell\x07 and null\x00", "bell and null"),  # C0 control chars scrub
        ("\x1b[31m\x1b[0m", None),  # scrubs to empty → None
        ("静けさは心の境なり。", "静けさは心の境なり。"),
        ("tab\there", "tab here"),  # \t is whitespace — collapsed by split
    ],
)
def test_sanitize_utterance_pipeline(raw: str, expected: str | None) -> None:
    assert _sanitize_utterance(raw) == expected
