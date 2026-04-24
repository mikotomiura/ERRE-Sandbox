"""End-to-end: ``InMemoryDialogScheduler`` persists turns into ``MemoryStore``.

Covers the M8 L6-D1 sink wiring. Opens an in-memory :class:`MemoryStore`,
constructs a scheduler whose ``turn_sink`` resolves ``agent_id → persona_id``
via a static dict, emits three ``record_turn`` calls under one dialog, and
asserts the sqlite ``dialog_turns`` table contains the expected rows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from erre_sandbox.integration.dialog import InMemoryDialogScheduler
from erre_sandbox.memory import MemoryStore
from erre_sandbox.schemas import ControlEnvelope, DialogTurnMsg, Zone

if TYPE_CHECKING:
    from collections.abc import Callable


_AGENT_TO_PERSONA: dict[str, str] = {
    "a_kant_001": "kant",
    "a_rikyu_001": "rikyu",
    "a_nietzsche_001": "nietzsche",
}


@pytest.fixture
async def store() -> MemoryStore:
    s = MemoryStore(db_path=":memory:")
    s.create_schema()
    yield s
    await s.close()


def _make_sink(store: MemoryStore) -> Callable[[DialogTurnMsg], None]:
    """Mirror the closure that bootstrap.py builds in production."""

    def _sink(turn: DialogTurnMsg) -> None:
        store.add_dialog_turn_sync(
            turn,
            speaker_persona_id=_AGENT_TO_PERSONA[turn.speaker_id],
            addressee_persona_id=_AGENT_TO_PERSONA[turn.addressee_id],
        )

    return _sink


def _open_dialog(
    scheduler: InMemoryDialogScheduler,
) -> str:
    """Open a Kant ↔ Nietzsche dialog and return its internal ``dialog_id``.

    ``DialogInitiateMsg`` does not carry the id (admission-only envelope),
    so tests peek at ``scheduler._open`` to drive ``record_turn`` with a
    valid id.
    """
    initiate = scheduler.schedule_initiate(
        initiator_id="a_kant_001",
        target_id="a_nietzsche_001",
        zone=Zone.PERIPATOS,
        tick=5,
    )
    assert initiate is not None
    return next(iter(scheduler._open))  # noqa: SLF001 — test-only introspection


async def test_record_turn_persists_through_sink(store: MemoryStore) -> None:
    captured: list[ControlEnvelope] = []
    scheduler = InMemoryDialogScheduler(
        envelope_sink=captured.append,
        turn_sink=_make_sink(store),
    )
    dialog_id = _open_dialog(scheduler)

    for i, (speaker, addressee, utterance) in enumerate(
        [
            ("a_kant_001", "a_nietzsche_001", "Guten Tag."),
            ("a_nietzsche_001", "a_kant_001", "Was soll das heißen?"),
            ("a_kant_001", "a_nietzsche_001", "Der kategorische Imperativ."),
        ],
    ):
        scheduler.record_turn(
            DialogTurnMsg(
                tick=10 + i,
                dialog_id=dialog_id,
                speaker_id=speaker,
                addressee_id=addressee,
                utterance=utterance,
                turn_index=i,
            ),
        )

    rows = list(store.iter_dialog_turns())
    assert len(rows) == 3
    assert [r["turn_index"] for r in rows] == [0, 1, 2]
    assert [r["speaker_persona_id"] for r in rows] == ["kant", "nietzsche", "kant"]


async def test_sink_failure_does_not_tear_down_loop(store: MemoryStore) -> None:
    """A raising sink must be swallowed so the live dialog loop survives."""
    captured: list[ControlEnvelope] = []

    def _broken_sink(turn: DialogTurnMsg) -> None:
        raise RuntimeError("simulated persistence glitch")

    scheduler = InMemoryDialogScheduler(
        envelope_sink=captured.append,
        turn_sink=_broken_sink,
    )
    dialog_id = _open_dialog(scheduler)

    # Should NOT raise — logger.exception swallows sink failures.
    scheduler.record_turn(
        DialogTurnMsg(
            tick=10,
            dialog_id=dialog_id,
            speaker_id="a_kant_001",
            addressee_id="a_nietzsche_001",
            utterance="...",
            turn_index=0,
        ),
    )

    # The in-memory transcript still captured the turn even when the sink failed.
    assert len(scheduler.transcript_of(dialog_id)) == 1
