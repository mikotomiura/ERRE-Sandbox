"""Unit tests for :class:`~erre_sandbox.integration.dialog.InMemoryDialogScheduler`.

Covers the Protocol surface (admit/reject/turn/close) plus the extension
API (`tick`, `get_dialog_id`) and the envelope-sink delivery path. All
randomness flows through an injected :class:`~random.Random`, so the
auto-fire path is deterministic — no retries, no sleep.
"""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING

import pytest

from erre_sandbox.integration.dialog import (
    AgentView,
    InMemoryDialogScheduler,
)
from erre_sandbox.schemas import (
    DialogCloseMsg,
    DialogInitiateMsg,
    DialogScheduler,
    DialogTurnMsg,
    Zone,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from erre_sandbox.schemas import ControlEnvelope


def _collector() -> tuple[list[ControlEnvelope], Callable[[ControlEnvelope], None]]:
    """Return (captured-list, sink-callable) pair for sink instrumentation."""
    captured: list[ControlEnvelope] = []

    def sink(env: ControlEnvelope) -> None:
        captured.append(env)

    return captured, sink


def _fire(rng_value: float) -> Random:
    """Seed a Random whose ``random()`` returns a fixed value.

    Used to make the auto-fire probability path deterministic: 0.0 always
    admits (<= AUTO_FIRE_PROB), 0.99 always skips (> AUTO_FIRE_PROB).
    """
    r = Random(0)
    r.random = lambda: rng_value  # type: ignore[method-assign]
    return r


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_scheduler_conforms_to_dialog_scheduler_protocol() -> None:
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    # isinstance on a Protocol requires `@runtime_checkable`; our Protocol is
    # *not* runtime_checkable, so we do a structural assertion instead.
    for method in ("schedule_initiate", "record_turn", "close_dialog"):
        assert callable(getattr(scheduler, method))
    # Quiet "unused" warning for the DialogScheduler import: document the
    # Protocol link so future greps find this test.
    _: type[DialogScheduler] = DialogScheduler


# ---------------------------------------------------------------------------
# schedule_initiate — admission rules
# ---------------------------------------------------------------------------


def test_schedule_initiate_admits_first_pair_and_emits_via_sink() -> None:
    captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink)

    env = scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=10)

    assert isinstance(env, DialogInitiateMsg)
    assert env.initiator_agent_id == "a"
    assert env.target_agent_id == "b"
    assert env.zone is Zone.PERIPATOS
    # Sink received the same envelope (identity, not just equality).
    assert captured == [env]
    assert scheduler.open_count == 1
    assert scheduler.get_dialog_id("a", "b") is not None
    # Order-agnostic lookup.
    assert scheduler.get_dialog_id("b", "a") == scheduler.get_dialog_id("a", "b")


def test_schedule_initiate_rejects_self_pair() -> None:
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    assert scheduler.schedule_initiate("a", "a", Zone.PERIPATOS, tick=0) is None
    assert scheduler.open_count == 0


def test_schedule_initiate_rejects_non_reflective_zone() -> None:
    """The study is intentionally excluded from dialog admission."""
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    assert scheduler.schedule_initiate("a", "b", Zone.STUDY, tick=0) is None


def test_schedule_initiate_rejects_second_pair_while_open() -> None:
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
    # Same pair, even swapped direction, must be rejected while open.
    assert scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=1) is None
    assert scheduler.schedule_initiate("b", "a", Zone.PERIPATOS, tick=1) is None


def test_schedule_initiate_rejects_during_cooldown() -> None:
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    first = scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
    assert first is not None
    dialog_id = scheduler.get_dialog_id("a", "b")
    assert dialog_id is not None
    scheduler.close_dialog(dialog_id, reason="completed")
    # Cooldown window: still inside = reject.
    inside = scheduler.schedule_initiate(
        "a",
        "b",
        Zone.PERIPATOS,
        tick=InMemoryDialogScheduler.COOLDOWN_TICKS - 1,
    )
    assert inside is None


def test_schedule_initiate_admits_after_cooldown_elapsed() -> None:
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
    dialog_id = scheduler.get_dialog_id("a", "b")
    assert dialog_id is not None
    scheduler.close_dialog(dialog_id, reason="completed")
    elapsed = scheduler.schedule_initiate(
        "a",
        "b",
        Zone.PERIPATOS,
        tick=InMemoryDialogScheduler.COOLDOWN_TICKS + 1,
    )
    assert isinstance(elapsed, DialogInitiateMsg)


# ---------------------------------------------------------------------------
# record_turn / close_dialog
# ---------------------------------------------------------------------------


def test_record_turn_appends_to_transcript() -> None:
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
    dialog_id = scheduler.get_dialog_id("a", "b")
    assert dialog_id is not None
    turn = DialogTurnMsg(
        tick=1,
        dialog_id=dialog_id,
        speaker_id="a",
        addressee_id="b",
        utterance="hi",
        turn_index=0,
    )
    scheduler.record_turn(turn)
    assert scheduler.transcript_of(dialog_id) == [turn]


def test_record_turn_raises_for_unknown_dialog() -> None:
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    bogus = DialogTurnMsg(
        tick=0,
        dialog_id="d_nonexistent",
        speaker_id="a",
        addressee_id="b",
        utterance="!",
        turn_index=0,
    )
    with pytest.raises(KeyError, match="unknown dialog_id"):
        scheduler.record_turn(bogus)


def test_close_dialog_emits_envelope_and_frees_pair() -> None:
    captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
    dialog_id = scheduler.get_dialog_id("a", "b")
    assert dialog_id is not None

    close = scheduler.close_dialog(dialog_id, reason="completed")

    assert isinstance(close, DialogCloseMsg)
    assert close.dialog_id == dialog_id
    assert close.reason == "completed"
    # Sink got both initiate and close in order.
    assert [c.kind for c in captured] == ["dialog_initiate", "dialog_close"]
    # Pair is no longer tracked as open.
    assert scheduler.get_dialog_id("a", "b") is None
    assert scheduler.open_count == 0


def test_close_dialog_raises_for_unknown_id() -> None:
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    with pytest.raises(KeyError):
        scheduler.close_dialog("d_missing", reason="completed")


# ---------------------------------------------------------------------------
# tick() — proximity gate + timeout
# ---------------------------------------------------------------------------


def test_tick_auto_fires_when_two_agents_share_reflective_zone() -> None:
    captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink, rng=_fire(0.0))
    views = [
        AgentView(agent_id="a", zone=Zone.PERIPATOS, tick=5),
        AgentView(agent_id="b", zone=Zone.PERIPATOS, tick=5),
    ]
    scheduler.tick(5, views)
    assert any(isinstance(c, DialogInitiateMsg) for c in captured)
    assert scheduler.open_count == 1


def test_tick_skips_when_rng_above_probability() -> None:
    captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink, rng=_fire(0.99))
    views = [
        AgentView(agent_id="a", zone=Zone.PERIPATOS, tick=5),
        AgentView(agent_id="b", zone=Zone.PERIPATOS, tick=5),
    ]
    scheduler.tick(5, views)
    assert captured == []
    assert scheduler.open_count == 0


def test_tick_skips_for_lone_agent() -> None:
    captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink, rng=_fire(0.0))
    scheduler.tick(1, [AgentView(agent_id="solo", zone=Zone.PERIPATOS, tick=1)])
    assert captured == []


def test_tick_skips_when_agents_in_different_zones() -> None:
    captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink, rng=_fire(0.0))
    scheduler.tick(
        1,
        [
            AgentView(agent_id="a", zone=Zone.PERIPATOS, tick=1),
            AgentView(agent_id="b", zone=Zone.CHASHITSU, tick=1),
        ],
    )
    assert captured == []


def test_tick_auto_closes_timed_out_dialog() -> None:
    captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink, rng=_fire(0.99))
    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
    # Fast-forward past TIMEOUT_TICKS with no turns recorded.
    scheduler.tick(
        InMemoryDialogScheduler.TIMEOUT_TICKS + 1,
        [
            AgentView(agent_id="a", zone=Zone.PERIPATOS, tick=1),
            AgentView(agent_id="b", zone=Zone.PERIPATOS, tick=1),
        ],
    )
    assert any(
        isinstance(c, DialogCloseMsg) and c.reason == "timeout" for c in captured
    )
    assert scheduler.open_count == 0


def test_tick_respects_cooldown_after_auto_close() -> None:
    captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink, rng=_fire(0.0))
    views_same_zone = [
        AgentView(agent_id="a", zone=Zone.PERIPATOS, tick=0),
        AgentView(agent_id="b", zone=Zone.PERIPATOS, tick=0),
    ]
    # Open then timeout-close.
    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
    scheduler.tick(InMemoryDialogScheduler.TIMEOUT_TICKS + 1, views_same_zone)
    initial_envelopes = len(captured)
    # Immediately tick again — cooldown must suppress auto re-firing even
    # though the RNG would otherwise admit.
    scheduler.tick(InMemoryDialogScheduler.TIMEOUT_TICKS + 2, views_same_zone)
    assert len(captured) == initial_envelopes  # no new initiate/close


# ---------------------------------------------------------------------------
# iter_open_dialogs — orchestrator-integration enumerator (M5)
# ---------------------------------------------------------------------------


def test_iter_open_dialogs_returns_empty_when_no_open() -> None:
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    assert list(scheduler.iter_open_dialogs()) == []


def test_iter_open_dialogs_yields_dialog_id_pair_and_zone() -> None:
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
    entries = list(scheduler.iter_open_dialogs())
    assert len(entries) == 1
    did, init, target, zone = entries[0]
    assert init == "a"
    assert target == "b"
    assert zone is Zone.PERIPATOS
    # The dialog_id must match scheduler.get_dialog_id for the same pair.
    assert scheduler.get_dialog_id("a", "b") == did


def test_iter_open_dialogs_enumerates_multiple_dialogs() -> None:
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
    scheduler.schedule_initiate("c", "d", Zone.CHASHITSU, tick=0)
    entries = list(scheduler.iter_open_dialogs())
    assert len(entries) == 2
    pairs = {(init, target) for _did, init, target, _zone in entries}
    assert pairs == {("a", "b"), ("c", "d")}


def test_iter_open_dialogs_drops_closed_dialogs() -> None:
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
    did = scheduler.get_dialog_id("a", "b")
    assert did is not None
    scheduler.close_dialog(did, reason="completed")
    assert list(scheduler.iter_open_dialogs()) == []


# ---------------------------------------------------------------------------
# F1 regression — close_dialog tick parameter (codex review 2026-04-28)
# ---------------------------------------------------------------------------


def test_close_dialog_uses_explicit_tick_when_provided() -> None:
    captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink, rng=_fire(0.0))
    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
    did = scheduler.get_dialog_id("a", "b")
    assert did is not None
    explicit_tick = 42
    close = scheduler.close_dialog(did, reason="completed", tick=explicit_tick)
    assert close.tick == explicit_tick
    closes = [c for c in captured if isinstance(c, DialogCloseMsg)]
    assert closes[-1].tick == explicit_tick
    cooldown = InMemoryDialogScheduler.COOLDOWN_TICKS
    assert (
        scheduler.schedule_initiate(
            "a",
            "b",
            Zone.PERIPATOS,
            tick=explicit_tick + cooldown - 1,
        )
        is None
    )
    assert (
        scheduler.schedule_initiate(
            "a",
            "b",
            Zone.PERIPATOS,
            tick=explicit_tick + cooldown + 1,
        )
        is not None
    )


def test_tick_timeout_close_emits_current_tick_not_last_activity() -> None:
    captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink, rng=_fire(0.99))
    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
    timeout_world_tick = InMemoryDialogScheduler.TIMEOUT_TICKS + 1
    scheduler.tick(
        timeout_world_tick,
        [
            AgentView(agent_id="a", zone=Zone.PERIPATOS, tick=timeout_world_tick),
            AgentView(agent_id="b", zone=Zone.PERIPATOS, tick=timeout_world_tick),
        ],
    )
    closes = [c for c in captured if isinstance(c, DialogCloseMsg)]
    assert len(closes) == 1
    assert closes[0].reason == "timeout"
    assert closes[0].tick == timeout_world_tick


def test_close_dialog_falls_back_to_last_activity_when_tick_omitted() -> None:
    captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
    did = scheduler.get_dialog_id("a", "b")
    assert did is not None
    turn = DialogTurnMsg(
        tick=5,
        dialog_id=did,
        speaker_id="a",
        addressee_id="b",
        utterance="hello",
        turn_index=0,
    )
    scheduler.record_turn(turn)
    close = scheduler.close_dialog(did, reason="completed")
    assert close.tick == 5
    closes = [c for c in captured if isinstance(c, DialogCloseMsg)]
    assert closes[-1].tick == 5
