"""Unit tests for ``InMemoryDialogScheduler.golden_baseline_mode`` flag.

m9-eval-system P2b minimum patch (design-final.md §Orchestrator,
decisions.md ME-7): the external golden baseline driver flips this flag
during the 200-stimulus phase to bypass cooldown / timeout / zone
restriction. Default ``False`` keeps every existing test green; this
suite verifies only the *bypass* semantics and the *runtime toggle*
contract that the driver depends on (P2c uses one scheduler instance
across stimulus + natural phases by flipping the public attribute).
"""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING

from erre_sandbox.integration.dialog import InMemoryDialogScheduler
from erre_sandbox.schemas import DialogInitiateMsg, Zone

if TYPE_CHECKING:
    from collections.abc import Callable

    from erre_sandbox.schemas import ControlEnvelope


def _collector() -> tuple[list[ControlEnvelope], Callable[[ControlEnvelope], None]]:
    captured: list[ControlEnvelope] = []

    def sink(env: ControlEnvelope) -> None:
        captured.append(env)

    return captured, sink


# ---------------------------------------------------------------------------
# Default behaviour (False) — existing semantics unchanged
# ---------------------------------------------------------------------------


def test_default_constructor_keeps_mode_false() -> None:
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    assert scheduler.golden_baseline_mode is False


# ---------------------------------------------------------------------------
# Mode True — zone restriction bypass (Zone.STUDY admitted)
# ---------------------------------------------------------------------------


def test_mode_true_admits_study_zone() -> None:
    """Stimulus battery includes ``Zone.STUDY`` for Kant/Nietzsche claims."""
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink,
        golden_baseline_mode=True,
    )
    admitted = scheduler.schedule_initiate("kant", "interlocutor", Zone.STUDY, tick=0)
    assert isinstance(admitted, DialogInitiateMsg)
    assert admitted.zone == Zone.STUDY


def test_mode_false_still_rejects_study_zone() -> None:
    """Default mode keeps the natural-dialog cultural restriction."""
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    assert scheduler.schedule_initiate("a", "b", Zone.STUDY, tick=0) is None


# ---------------------------------------------------------------------------
# Mode True — cooldown bypass (rapid stimulus loop on same pair)
# ---------------------------------------------------------------------------


def test_mode_true_bypasses_cooldown_on_same_pair() -> None:
    """70 stimulus × 3 cycles drives the same persona pair without 30-tick gaps."""
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink,
        golden_baseline_mode=True,
    )
    scheduler.schedule_initiate("kant", "interlocutor", Zone.PERIPATOS, tick=0)
    dialog_id = scheduler.get_dialog_id("kant", "interlocutor")
    assert dialog_id is not None
    scheduler.close_dialog(dialog_id, reason="completed", tick=0)
    # Re-open immediately at tick=1 (well within the 30-tick cooldown window).
    reopened = scheduler.schedule_initiate(
        "kant",
        "interlocutor",
        Zone.PERIPATOS,
        tick=1,
    )
    assert isinstance(reopened, DialogInitiateMsg)


def test_mode_false_still_rejects_during_cooldown() -> None:
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
    dialog_id = scheduler.get_dialog_id("a", "b")
    assert dialog_id is not None
    scheduler.close_dialog(dialog_id, reason="completed")
    inside_cooldown = scheduler.schedule_initiate(
        "a",
        "b",
        Zone.PERIPATOS,
        tick=InMemoryDialogScheduler.COOLDOWN_TICKS - 1,
    )
    assert inside_cooldown is None


# ---------------------------------------------------------------------------
# Mode True — timeout suppression in tick()
# ---------------------------------------------------------------------------


def test_mode_true_suppresses_timeout_close_in_tick() -> None:
    """Driver explicitly closes dialogs; tick() must not race-close them."""
    _captured, sink = _collector()
    rng = Random(0)
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink,
        rng=rng,
        golden_baseline_mode=True,
    )
    scheduler.schedule_initiate("kant", "interlocutor", Zone.PERIPATOS, tick=0)
    dialog_id = scheduler.get_dialog_id("kant", "interlocutor")
    assert dialog_id is not None
    # Empty agents iterable so auto-fire path doesn't add new dialogs.
    scheduler.tick(InMemoryDialogScheduler.TIMEOUT_TICKS + 100, agents=())
    # Dialog must still be open — driver is the sole closer in golden mode.
    assert scheduler.open_count == 1
    assert scheduler.get_dialog_id("kant", "interlocutor") == dialog_id


def test_mode_false_still_auto_closes_on_timeout() -> None:
    _captured, sink = _collector()
    rng = Random(0)
    scheduler = InMemoryDialogScheduler(envelope_sink=sink, rng=rng)
    scheduler.schedule_initiate("a", "b", Zone.PERIPATOS, tick=0)
    assert scheduler.open_count == 1
    scheduler.tick(InMemoryDialogScheduler.TIMEOUT_TICKS + 1, agents=())
    assert scheduler.open_count == 0


# ---------------------------------------------------------------------------
# Mode True — invariants that MUST still hold (sanity for driver)
# ---------------------------------------------------------------------------


def test_mode_true_still_rejects_self_pair() -> None:
    """Same-id initiator/target is a programming error in any mode."""
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink,
        golden_baseline_mode=True,
    )
    assert scheduler.schedule_initiate("kant", "kant", Zone.STUDY, tick=0) is None


def test_mode_true_still_rejects_already_open_pair() -> None:
    """Driver must close before re-opening even in golden mode."""
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink,
        golden_baseline_mode=True,
    )
    scheduler.schedule_initiate("kant", "interlocutor", Zone.STUDY, tick=0)
    second = scheduler.schedule_initiate("kant", "interlocutor", Zone.STUDY, tick=1)
    assert second is None


# ---------------------------------------------------------------------------
# Runtime toggle (driver flips between phases on one instance)
# ---------------------------------------------------------------------------


def test_runtime_toggle_enables_then_disables_bypass() -> None:
    """P2c driver: stimulus phase mode=True → flip → natural phase mode=False."""
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink,
        golden_baseline_mode=True,
    )
    # Phase 1: STUDY admitted while True.
    admitted = scheduler.schedule_initiate("kant", "interlocutor", Zone.STUDY, tick=0)
    assert isinstance(admitted, DialogInitiateMsg)
    dialog_id = scheduler.get_dialog_id("kant", "interlocutor")
    assert dialog_id is not None
    scheduler.close_dialog(dialog_id, reason="completed", tick=0)

    # Driver flips to False between phases.
    scheduler.golden_baseline_mode = False

    # Phase 2: STUDY is now rejected again (natural-dialog rules restored).
    rejected = scheduler.schedule_initiate(
        "kant",
        "interlocutor",
        Zone.STUDY,
        tick=InMemoryDialogScheduler.COOLDOWN_TICKS + 1,
    )
    assert rejected is None
    # And cooldown applies again — at tick just past close, PERIPATOS within
    # cooldown also rejected.
    inside_cooldown = scheduler.schedule_initiate(
        "kant",
        "interlocutor",
        Zone.PERIPATOS,
        tick=1,
    )
    assert inside_cooldown is None
