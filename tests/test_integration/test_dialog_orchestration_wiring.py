"""Tests for the M5 orchestrator wiring in :class:`WorldRuntime`.

Covers :meth:`WorldRuntime.attach_dialog_generator` and the private
``_drive_dialog_turns`` step called from ``_on_cognition_tick``:

* budget boundary (`turn_index >= dialog_turn_budget` => exhausted close)
* speaker alternation (`turn_index % 2 == 0` => initiator, else target)
* graceful ``None`` return from the generator (no record, no emit)
* generator exception isolation across sibling dialogs
* orchestrator no-op when no generator is attached (M4-equivalent behaviour)

The tests build a real :class:`InMemoryDialogScheduler` and a fake
:class:`DialogTurnGenerator` so the orchestration logic is exercised
end-to-end without the LLM. The ``_drive_dialog_turns`` method is called
directly rather than via the full tick-loop to keep assertions focused.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from erre_sandbox.integration.dialog import InMemoryDialogScheduler
from erre_sandbox.schemas import (
    DialogCloseMsg,
    DialogInitiateMsg,
    DialogTurnMsg,
    Position,
    Zone,
)
from erre_sandbox.world import ManualClock, WorldRuntime

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from typing import Any

    from erre_sandbox.schemas import AgentState, ControlEnvelope, PersonaSpec


# ---------------------------------------------------------------------------
# Fake generator — records inputs, returns scripted outputs
# ---------------------------------------------------------------------------


class _FakeGenerator:
    """Minimal :class:`DialogTurnGenerator` substitute for wiring tests.

    ``responder`` receives the full kwargs dict and returns either
    a :class:`DialogTurnMsg`, ``None`` (soft close), or raises.
    """

    def __init__(
        self,
        responder: Callable[[dict[str, Any]], DialogTurnMsg | None] | None = None,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._responder = responder

    async def generate_turn(
        self,
        *,
        dialog_id: str,
        speaker_state: AgentState,
        speaker_persona: PersonaSpec,
        addressee_state: AgentState,
        transcript: Sequence[DialogTurnMsg],
        world_tick: int,
    ) -> DialogTurnMsg | None:
        payload: dict[str, Any] = {
            "dialog_id": dialog_id,
            "speaker_state": speaker_state,
            "speaker_persona": speaker_persona,
            "addressee_state": addressee_state,
            "transcript": list(transcript),
            "world_tick": world_tick,
        }
        self.calls.append(payload)
        if self._responder is None:
            # Default: produce a deterministic turn the caller can assert on.
            return DialogTurnMsg(
                tick=world_tick,
                dialog_id=dialog_id,
                speaker_id=speaker_state.agent_id,
                addressee_id=addressee_state.agent_id,
                utterance=f"fake-turn-{len(transcript)}",
                turn_index=len(transcript),
            )
        return self._responder(payload)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_runtime_with_two_agents(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
    *,
    budget: int = 6,
) -> tuple[WorldRuntime, InMemoryDialogScheduler, list[ControlEnvelope]]:
    """Build a runtime + scheduler pre-wired with two peripatos agents.

    The third return value is a list that records every envelope the runtime
    fans out. Scheduler-side emissions (initiate / close) and orchestrator-
    side emissions (turn) both land in the runtime's queue via
    :meth:`WorldRuntime.inject_envelope`, so we instrument that single choke
    point — mirroring what a real WebSocket consumer sees.
    """

    class _NoopCycle:
        async def step(self, *_args: Any, **_kwargs: Any) -> Any:
            msg = "MockCycle is not expected to run in orchestration tests"
            raise AssertionError(msg)

    runtime = WorldRuntime(
        cycle=_NoopCycle(),  # type: ignore[arg-type]
        clock=ManualClock(),
    )

    kant = make_agent_state(
        agent_id="a_kant_001",
        persona_id="kant",
        position={"x": 0.0, "y": 0.0, "z": 0.0, "zone": "peripatos"},
        cognitive={"dialog_turn_budget": budget},
    )
    nietzsche = make_agent_state(
        agent_id="a_nietzsche_001",
        persona_id="nietzsche",
        position={"x": 1.0, "y": 0.0, "z": 0.0, "zone": "peripatos"},
        cognitive={"dialog_turn_budget": budget},
    )
    runtime.register_agent(kant, make_persona_spec(persona_id="kant"))
    runtime.register_agent(
        nietzsche,
        make_persona_spec(
            persona_id="nietzsche",
            display_name="Friedrich Nietzsche",
        ),
    )

    captured: list[ControlEnvelope] = []
    original_inject = runtime.inject_envelope

    def tracked_inject(env: ControlEnvelope) -> None:
        captured.append(env)
        original_inject(env)

    runtime.inject_envelope = tracked_inject  # type: ignore[method-assign]

    scheduler = InMemoryDialogScheduler(envelope_sink=runtime.inject_envelope)
    runtime.attach_dialog_scheduler(scheduler)
    return runtime, scheduler, captured


def _seed_turn(
    scheduler: InMemoryDialogScheduler,
    *,
    dialog_id: str,
    speaker: str,
    addressee: str,
    turn_index: int,
    tick: int,
) -> None:
    """Append one fabricated turn to the scheduler's transcript."""
    scheduler.record_turn(
        DialogTurnMsg(
            tick=tick,
            dialog_id=dialog_id,
            speaker_id=speaker,
            addressee_id=addressee,
            utterance=f"seed-{turn_index}",
            turn_index=turn_index,
        ),
    )


# ---------------------------------------------------------------------------
# Tests — budget boundary
# ---------------------------------------------------------------------------


async def test_drive_dialog_turns_generates_when_under_budget(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    runtime, scheduler, captured = _make_runtime_with_two_agents(
        make_agent_state,
        make_persona_spec,
        budget=6,
    )
    generator = _FakeGenerator()
    runtime.attach_dialog_generator(generator)  # type: ignore[arg-type]

    scheduler.schedule_initiate("a_kant_001", "a_nietzsche_001", Zone.PERIPATOS, tick=0)
    initial_envelope_count = len(captured)

    await runtime._drive_dialog_turns(world_tick=1)

    # One generator call, one DialogTurnMsg emitted on the sink, and the
    # scheduler's transcript now has turn_index=0.
    assert len(generator.calls) == 1
    turn_envelopes = [e for e in captured if isinstance(e, DialogTurnMsg)]
    assert len(turn_envelopes) == 1
    assert turn_envelopes[0].turn_index == 0
    assert len(captured) == initial_envelope_count + 1  # only the turn msg added
    did = scheduler.get_dialog_id("a_kant_001", "a_nietzsche_001")
    assert did is not None
    assert len(scheduler.transcript_of(did)) == 1


async def test_drive_dialog_turns_closes_with_exhausted_when_budget_hit(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    runtime, scheduler, captured = _make_runtime_with_two_agents(
        make_agent_state,
        make_persona_spec,
        budget=6,
    )
    generator = _FakeGenerator()
    runtime.attach_dialog_generator(generator)  # type: ignore[arg-type]

    scheduler.schedule_initiate("a_kant_001", "a_nietzsche_001", Zone.PERIPATOS, tick=0)
    did = scheduler.get_dialog_id("a_kant_001", "a_nietzsche_001")
    assert did is not None
    # Seed 6 turns — exactly at budget.
    for i in range(6):
        _seed_turn(
            scheduler,
            dialog_id=did,
            speaker=("a_kant_001" if i % 2 == 0 else "a_nietzsche_001"),
            addressee=("a_nietzsche_001" if i % 2 == 0 else "a_kant_001"),
            turn_index=i,
            tick=i,
        )

    await runtime._drive_dialog_turns(world_tick=10)

    # Budget exhausted: generator was NOT called, and a DialogCloseMsg with
    # reason="exhausted" was emitted.
    assert generator.calls == []
    close_envelopes = [e for e in captured if isinstance(e, DialogCloseMsg)]
    assert len(close_envelopes) == 1
    assert close_envelopes[0].reason == "exhausted"
    assert close_envelopes[0].dialog_id == did
    # Dialog is no longer open.
    assert scheduler.open_count == 0


# ---------------------------------------------------------------------------
# Tests — speaker alternation
# ---------------------------------------------------------------------------


async def test_drive_dialog_turns_speaker_alternation(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    runtime, scheduler, _captured = _make_runtime_with_two_agents(
        make_agent_state,
        make_persona_spec,
    )
    generator = _FakeGenerator()
    runtime.attach_dialog_generator(generator)  # type: ignore[arg-type]

    scheduler.schedule_initiate("a_kant_001", "a_nietzsche_001", Zone.PERIPATOS, tick=0)
    did = scheduler.get_dialog_id("a_kant_001", "a_nietzsche_001")
    assert did is not None

    # Turn 0: no prior transcript → speaker = initiator (kant)
    await runtime._drive_dialog_turns(world_tick=1)
    assert generator.calls[-1]["speaker_state"].agent_id == "a_kant_001"
    assert generator.calls[-1]["addressee_state"].agent_id == "a_nietzsche_001"

    # Turn 1: one prior → speaker = target (nietzsche)
    await runtime._drive_dialog_turns(world_tick=2)
    assert generator.calls[-1]["speaker_state"].agent_id == "a_nietzsche_001"
    assert generator.calls[-1]["addressee_state"].agent_id == "a_kant_001"

    # Turn 2: two priors → speaker = initiator again
    await runtime._drive_dialog_turns(world_tick=3)
    assert generator.calls[-1]["speaker_state"].agent_id == "a_kant_001"


# ---------------------------------------------------------------------------
# Tests — graceful failure paths
# ---------------------------------------------------------------------------


async def test_drive_dialog_turns_none_return_emits_nothing(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    runtime, scheduler, captured = _make_runtime_with_two_agents(
        make_agent_state,
        make_persona_spec,
    )
    generator = _FakeGenerator(responder=lambda _payload: None)
    runtime.attach_dialog_generator(generator)  # type: ignore[arg-type]

    scheduler.schedule_initiate("a_kant_001", "a_nietzsche_001", Zone.PERIPATOS, tick=0)
    did = scheduler.get_dialog_id("a_kant_001", "a_nietzsche_001")
    assert did is not None

    # Snapshot envelope count after initiate.
    baseline = len(captured)

    await runtime._drive_dialog_turns(world_tick=1)

    # Generator was called but returned None — no record_turn, no sink emit.
    assert len(generator.calls) == 1
    assert len(scheduler.transcript_of(did)) == 0
    assert len(captured) == baseline  # no new envelopes


async def test_drive_dialog_turns_exception_does_not_break_siblings(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    runtime, scheduler, _captured = _make_runtime_with_two_agents(
        make_agent_state,
        make_persona_spec,
    )
    rikyu = make_agent_state(
        agent_id="a_rikyu_001",
        persona_id="rikyu",
        position={"x": 2.0, "y": 0.0, "z": 0.0, "zone": "peripatos"},
    )
    runtime.register_agent(rikyu, make_persona_spec(persona_id="rikyu"))

    # Fail the Kant-Nietzsche dialog, succeed the Kant-Rikyu dialog.
    def responder(payload: dict[str, Any]) -> DialogTurnMsg | None:
        speaker: AgentState = payload["speaker_state"]
        if speaker.agent_id == "a_kant_001" and (
            payload["addressee_state"].agent_id == "a_nietzsche_001"
        ):
            msg = "synthetic generator failure"
            raise RuntimeError(msg)
        return DialogTurnMsg(
            tick=payload["world_tick"],
            dialog_id=payload["dialog_id"],
            speaker_id=speaker.agent_id,
            addressee_id=payload["addressee_state"].agent_id,
            utterance="rikyu-ok",
            turn_index=len(payload["transcript"]),
        )

    generator = _FakeGenerator(responder=responder)
    runtime.attach_dialog_generator(generator)  # type: ignore[arg-type]

    scheduler.schedule_initiate("a_kant_001", "a_nietzsche_001", Zone.PERIPATOS, tick=0)
    scheduler.schedule_initiate("a_kant_001", "a_rikyu_001", Zone.PERIPATOS, tick=0)

    await runtime._drive_dialog_turns(world_tick=1)

    # The rikyu dialog still recorded its turn despite the sibling failure.
    did_rikyu = scheduler.get_dialog_id("a_kant_001", "a_rikyu_001")
    assert did_rikyu is not None
    assert len(scheduler.transcript_of(did_rikyu)) == 1
    # The failing dialog left no record.
    did_n = scheduler.get_dialog_id("a_kant_001", "a_nietzsche_001")
    assert did_n is not None
    assert len(scheduler.transcript_of(did_n)) == 0


# ---------------------------------------------------------------------------
# Tests — orchestrator disabled paths
# ---------------------------------------------------------------------------


async def test_drive_dialog_turns_without_generator_is_noop(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    runtime, scheduler, captured = _make_runtime_with_two_agents(
        make_agent_state,
        make_persona_spec,
    )
    # Deliberately DO NOT attach_dialog_generator.
    scheduler.schedule_initiate("a_kant_001", "a_nietzsche_001", Zone.PERIPATOS, tick=0)
    baseline = len(captured)

    await runtime._drive_dialog_turns(world_tick=1)

    # No turns generated, no close fired — dialog stays open for the
    # existing timeout path to reap later.
    did = scheduler.get_dialog_id("a_kant_001", "a_nietzsche_001")
    assert did is not None
    assert len(scheduler.transcript_of(did)) == 0
    assert len(captured) == baseline


async def test_drive_dialog_turns_without_scheduler_is_noop() -> None:
    """If no scheduler was attached, driving turns is a silent no-op."""

    class _NoopCycle:
        async def step(self, *_args: Any, **_kwargs: Any) -> Any:
            msg = "unused"
            raise AssertionError(msg)

    runtime = WorldRuntime(
        cycle=_NoopCycle(),  # type: ignore[arg-type]
        clock=ManualClock(),
    )
    generator = _FakeGenerator()
    runtime.attach_dialog_generator(generator)  # type: ignore[arg-type]

    # No exception even though scheduler is None.
    await runtime._drive_dialog_turns(world_tick=1)
    assert generator.calls == []


# ---------------------------------------------------------------------------
# Tests — initiate envelope is not duplicated by orchestration
# ---------------------------------------------------------------------------


async def test_drive_dialog_turns_preserves_initiate_envelope(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """DialogInitiateMsg emitted by scheduler must survive orchestration."""
    runtime, scheduler, captured = _make_runtime_with_two_agents(
        make_agent_state,
        make_persona_spec,
    )
    generator = _FakeGenerator()
    runtime.attach_dialog_generator(generator)  # type: ignore[arg-type]

    scheduler.schedule_initiate("a_kant_001", "a_nietzsche_001", Zone.PERIPATOS, tick=0)

    initiate_envs = [e for e in captured if isinstance(e, DialogInitiateMsg)]
    assert len(initiate_envs) == 1

    await runtime._drive_dialog_turns(world_tick=1)

    # Still only one initiate envelope — orchestrator did not re-emit it.
    initiate_envs = [e for e in captured if isinstance(e, DialogInitiateMsg)]
    assert len(initiate_envs) == 1


# ---------------------------------------------------------------------------
# Test — position isn't used by orchestrator (sanity: agents don't need to
# share a zone at the time of turn generation)
# ---------------------------------------------------------------------------


async def test_drive_dialog_turns_works_after_participants_leave_zone(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """Zone change mid-dialog must not block the next turn.

    Admission checks zone; once admitted the dialog is tracked by id and
    the orchestrator must not re-check co-location.
    """
    runtime, scheduler, _captured = _make_runtime_with_two_agents(
        make_agent_state,
        make_persona_spec,
    )
    generator = _FakeGenerator()
    runtime.attach_dialog_generator(generator)  # type: ignore[arg-type]

    scheduler.schedule_initiate("a_kant_001", "a_nietzsche_001", Zone.PERIPATOS, tick=0)
    # Simulate kant wandering off to the study after admission.
    runtime._agents["a_kant_001"].state = runtime._agents[
        "a_kant_001"
    ].state.model_copy(
        update={"position": Position(x=0.0, y=0.0, z=0.0, zone=Zone.STUDY)},
    )

    await runtime._drive_dialog_turns(world_tick=1)
    assert len(generator.calls) == 1


# ---------------------------------------------------------------------------
# Regression — attach_dialog_generator is idempotent in intent
# ---------------------------------------------------------------------------


def test_attach_dialog_generator_replaces_previous(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    """Attaching twice keeps only the most recent generator (last-writer-wins).

    The method mirrors :meth:`WorldRuntime.attach_dialog_scheduler`'s
    semantics — there is no multiplexing, the newest attached callable is
    the one the runtime consults on the next tick.
    """
    runtime, _scheduler, _captured = _make_runtime_with_two_agents(
        make_agent_state,
        make_persona_spec,
    )
    gen1 = _FakeGenerator()
    gen2 = _FakeGenerator()
    runtime.attach_dialog_generator(gen1)  # type: ignore[arg-type]
    runtime.attach_dialog_generator(gen2)  # type: ignore[arg-type]
    assert runtime._dialog_generator is gen2


# ---------------------------------------------------------------------------
# Parametrised regression — budget boundaries (0, 1, 5, 6 turns seeded)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("seeded_turns", "expect_exhausted_close"),
    [
        (0, False),  # fresh dialog — generator called
        (1, False),
        (5, False),  # one slot left
        (6, True),  # at budget — exhausted close
    ],
)
async def test_drive_dialog_turns_budget_boundary(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
    seeded_turns: int,
    expect_exhausted_close: bool,  # noqa: FBT001 — pytest parametrize
) -> None:
    runtime, scheduler, captured = _make_runtime_with_two_agents(
        make_agent_state,
        make_persona_spec,
        budget=6,
    )
    generator = _FakeGenerator()
    runtime.attach_dialog_generator(generator)  # type: ignore[arg-type]

    scheduler.schedule_initiate("a_kant_001", "a_nietzsche_001", Zone.PERIPATOS, tick=0)
    did = scheduler.get_dialog_id("a_kant_001", "a_nietzsche_001")
    assert did is not None
    for i in range(seeded_turns):
        _seed_turn(
            scheduler,
            dialog_id=did,
            speaker=("a_kant_001" if i % 2 == 0 else "a_nietzsche_001"),
            addressee=("a_nietzsche_001" if i % 2 == 0 else "a_kant_001"),
            turn_index=i,
            tick=i,
        )

    await runtime._drive_dialog_turns(world_tick=10)

    close_envelopes = [
        e for e in captured if isinstance(e, DialogCloseMsg) and e.reason == "exhausted"
    ]
    if expect_exhausted_close:
        assert len(close_envelopes) == 1
        assert generator.calls == []
    else:
        assert close_envelopes == []
        assert len(generator.calls) == 1
