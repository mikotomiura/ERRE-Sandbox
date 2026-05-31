"""Tests for ``InMemoryDialogScheduler.eval_natural_mode`` flag.

m9-eval-system P3a-decide Task 1 — natural runtime gating bug fix.

Background (from `.steering/20260430-m9-eval-system/design-natural-gating-fix.md`):
G-GEAR pilot 採取で natural condition (3 persona × 30 focal target) が
**初動 burst 2-3 dialogs 後に admission が完全停止**する症状が観測された。
root cause は LLM-driven ``destination_zone`` で agents が AGORA から散り、
``_iter_colocated_pairs`` の ``a.zone == b.zone`` 制約で 0 pair 返却 →
新規 dialog が立ち上がらない、というもの。``ERRE_ZONE_BIAS_P=0.2`` default
で 80% は LLM zone を honor するため preferred_zones override では救えない。

修正: ``eval_natural_mode: bool = False`` flag を scheduler に追加し、True
のとき ``tick()`` の zone equality / reflective zone 制約を bypass。
cooldown / probability / timeout / 自己 dialog reject / 二重 open reject の
invariant は両 mode で保持される (natural cadence は維持)。

Default ``False`` で既存 1221 PASS は完全互換、``True`` opt-in は CLI
``capture_natural`` のみが指定する。
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
    DialogTurnMsg,
    Zone,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from erre_sandbox.schemas import ControlEnvelope


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collector() -> tuple[list[ControlEnvelope], Callable[[ControlEnvelope], None]]:
    captured: list[ControlEnvelope] = []

    def sink(env: ControlEnvelope) -> None:
        captured.append(env)

    return captured, sink


def _always_fire() -> Random:
    """RNG whose ``random()`` always returns 0.0 (≤ AUTO_FIRE_PROB)."""
    r = Random(0)
    r.random = lambda: 0.0  # type: ignore[method-assign]
    return r


def _never_fire() -> Random:
    """RNG whose ``random()`` always returns 0.99 (> AUTO_FIRE_PROB)."""
    r = Random(0)
    r.random = lambda: 0.99  # type: ignore[method-assign]
    return r


# ---------------------------------------------------------------------------
# Default constructor: eval_natural_mode is False (M4-frozen behaviour)
# ---------------------------------------------------------------------------


def test_default_constructor_keeps_eval_natural_mode_false() -> None:
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink)
    assert scheduler.eval_natural_mode is False


def test_eval_natural_mode_is_independent_of_golden_baseline_mode() -> None:
    """Two flags address orthogonal concerns and can be set independently."""
    _captured, sink = _collector()
    scheduler_a = InMemoryDialogScheduler(
        envelope_sink=sink, eval_natural_mode=True, golden_baseline_mode=False
    )
    scheduler_b = InMemoryDialogScheduler(
        envelope_sink=sink, eval_natural_mode=False, golden_baseline_mode=True
    )
    assert scheduler_a.eval_natural_mode is True
    assert scheduler_a.golden_baseline_mode is False
    assert scheduler_b.eval_natural_mode is False
    assert scheduler_b.golden_baseline_mode is True


def test_combining_both_modes_is_rejected() -> None:
    """Codex review LOW-1: the two flags cover disjoint capture phases.
    Combining them on the same instance would silently let
    ``golden_baseline_mode`` override the cooldown / timeout invariant
    that ``eval_natural_mode`` advertises — surface the inconsistency at
    construction instead.
    """
    _captured, sink = _collector()
    with pytest.raises(ValueError, match="golden_baseline_mode and eval_natural_mode"):
        InMemoryDialogScheduler(
            envelope_sink=sink,
            golden_baseline_mode=True,
            eval_natural_mode=True,
        )


# ---------------------------------------------------------------------------
# Bug repro (default False): zone drift halts admission
# ---------------------------------------------------------------------------


def test_default_mode_admission_stops_when_agents_scatter() -> None:
    """Document the gating bug: when agents drift to different zones the
    proximity-only ``tick()`` cannot admit new dialogs.

    This mirrors the G-GEAR pilot natural-condition pattern: initial burst
    fires while all 3 personas are still in AGORA, then LLM-driven
    ``destination_zone`` scatters them and ``_iter_colocated_pairs``
    returns nothing → new admissions plateau at 0.
    """
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=False
    )

    # Tick 0 — all three in AGORA. Three pairs eligible, all admit.
    co_located = [
        AgentView(agent_id="kant", zone=Zone.AGORA, tick=0),
        AgentView(agent_id="nietzsche", zone=Zone.AGORA, tick=0),
        AgentView(agent_id="rikyu", zone=Zone.AGORA, tick=0),
    ]
    scheduler.tick(world_tick=0, agents=co_located)
    assert scheduler.open_count == 3, (
        "all three pairs should admit on tick 0 with rng=always_fire"
    )

    # Close all three (simulate budget exhaustion, much sooner than timeout).
    for did, _i, _t, _z in list(scheduler.iter_open_dialogs()):
        scheduler.close_dialog(did, reason="exhausted", tick=0)
    assert scheduler.open_count == 0

    # Advance world tick past COOLDOWN_TICKS so cooldown is no longer the gate.
    far_tick = scheduler.COOLDOWN_TICKS + 5

    # Now agents have scattered (LLM destination_zone moved them).
    scattered = [
        AgentView(agent_id="kant", zone=Zone.STUDY, tick=far_tick),
        AgentView(agent_id="nietzsche", zone=Zone.PERIPATOS, tick=far_tick),
        AgentView(agent_id="rikyu", zone=Zone.CHASHITSU, tick=far_tick),
    ]
    scheduler.tick(world_tick=far_tick, agents=scattered)
    assert scheduler.open_count == 0, (
        "BUG REPRO: with default mode, scattered agents have 0 co-located "
        "pairs, so even after cooldown expires no admit fires"
    )


# ---------------------------------------------------------------------------
# Fix: eval_natural_mode=True admits any pair regardless of zone
# ---------------------------------------------------------------------------


def test_eval_natural_mode_admits_pairs_across_different_zones() -> None:
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
    )
    scattered = [
        AgentView(agent_id="kant", zone=Zone.STUDY, tick=0),
        AgentView(agent_id="nietzsche", zone=Zone.PERIPATOS, tick=0),
        AgentView(agent_id="rikyu", zone=Zone.CHASHITSU, tick=0),
    ]
    scheduler.tick(world_tick=0, agents=scattered)
    assert scheduler.open_count == 3, (
        "all three distinct pairs should admit regardless of zone"
    )


def test_eval_natural_mode_admits_two_study_agents() -> None:
    """``Zone.STUDY`` is excluded from ``_REFLECTIVE_ZONES`` in default
    mode but eval natural treats all pairs as eligible — including STUDY-STUDY."""
    captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
    )
    agents = [
        AgentView(agent_id="kant", zone=Zone.STUDY, tick=0),
        AgentView(agent_id="nietzsche", zone=Zone.STUDY, tick=0),
    ]
    scheduler.tick(world_tick=0, agents=agents)
    assert scheduler.open_count == 1
    initiates = [env for env in captured if isinstance(env, DialogInitiateMsg)]
    assert len(initiates) == 1


# ---------------------------------------------------------------------------
# Invariants preserved in eval_natural_mode
# ---------------------------------------------------------------------------


def test_eval_natural_mode_preserves_self_dialog_reject() -> None:
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink, eval_natural_mode=True)
    result = scheduler.schedule_initiate("kant", "kant", Zone.AGORA, tick=0)
    assert result is None


def test_eval_natural_mode_preserves_double_open_reject() -> None:
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink, eval_natural_mode=True)
    first = scheduler.schedule_initiate("kant", "rikyu", Zone.AGORA, tick=0)
    assert isinstance(first, DialogInitiateMsg)
    second = scheduler.schedule_initiate("kant", "rikyu", Zone.AGORA, tick=1)
    assert second is None


def test_eval_natural_mode_uses_reduced_cooldown() -> None:
    """Cooldown still applies after a close — eval mode uses
    ``COOLDOWN_TICKS_EVAL=5`` instead of the live ``COOLDOWN_TICKS=30``.

    m9-eval-system P3a-decide v2 (ME-8 amendment 2026-05-01): the empirical
    cognition_period ≈ 120 s/tick on qwen3:8b Q4_K_M makes the live 30-tick
    cooldown translate to ~60 min wall; reducing to 5 ticks brings the
    cooldown to ~10 min wall so multiple admit cycles fit inside a 120 min
    wall budget.
    """
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
    )
    agents = [
        AgentView(agent_id="kant", zone=Zone.STUDY, tick=0),
        AgentView(agent_id="rikyu", zone=Zone.GARDEN, tick=0),
    ]
    scheduler.tick(world_tick=0, agents=agents)
    assert scheduler.open_count == 1
    [(did, _i, _t, _z)] = list(scheduler.iter_open_dialogs())
    scheduler.close_dialog(did, reason="exhausted", tick=0)

    # Within eval cooldown window — no re-admit.
    for w in range(1, scheduler.COOLDOWN_TICKS_EVAL):
        scheduler.tick(world_tick=w, agents=agents)
        assert scheduler.open_count == 0, (
            f"eval cooldown breached at tick {w}: same pair re-admitted "
            f"within {scheduler.COOLDOWN_TICKS_EVAL} ticks"
        )

    # Past eval cooldown — admit again.
    scheduler.tick(world_tick=scheduler.COOLDOWN_TICKS_EVAL, agents=agents)
    assert scheduler.open_count == 1


def test_eval_natural_mode_preserves_probability_gate() -> None:
    """RNG > AUTO_FIRE_PROB still suppresses admit even with zone bypass."""
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink, rng=_never_fire(), eval_natural_mode=True
    )
    agents = [
        AgentView(agent_id="kant", zone=Zone.STUDY, tick=0),
        AgentView(agent_id="rikyu", zone=Zone.GARDEN, tick=0),
    ]
    scheduler.tick(world_tick=0, agents=agents)
    assert scheduler.open_count == 0


def test_eval_natural_mode_preserves_timeout_close() -> None:
    """In-flight dialogs still time out when ``last_activity_tick`` is stale."""
    captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
    )
    agents = [
        AgentView(agent_id="kant", zone=Zone.STUDY, tick=0),
        AgentView(agent_id="rikyu", zone=Zone.GARDEN, tick=0),
    ]
    scheduler.tick(world_tick=0, agents=agents)
    assert scheduler.open_count == 1

    # No activity recorded for TIMEOUT_TICKS ticks → tick() should auto-close.
    scheduler.tick(world_tick=scheduler.TIMEOUT_TICKS, agents=agents)
    close_envs = [e for e in captured if isinstance(e, DialogCloseMsg)]
    assert len(close_envs) == 1
    assert close_envs[0].reason == "timeout"
    assert scheduler.open_count == 0


# ---------------------------------------------------------------------------
# Sustained admission scenario (Red→Green core)
# ---------------------------------------------------------------------------


def test_eval_natural_mode_sustains_admission_after_initial_burst() -> None:
    """Reproduce the natural-condition observation pattern: initial burst,
    then continued admission across many ticks despite zone drift.

    Counter-example to the bug repro above: with eval_natural_mode=True,
    even after agents scatter, admit fires resume after cooldown.
    """
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=True
    )

    agents_initial = [
        AgentView(agent_id="kant", zone=Zone.AGORA, tick=0),
        AgentView(agent_id="nietzsche", zone=Zone.AGORA, tick=0),
        AgentView(agent_id="rikyu", zone=Zone.AGORA, tick=0),
    ]
    scheduler.tick(world_tick=0, agents=agents_initial)
    assert scheduler.open_count == 3

    # Simulate dialog turns + exhaustion close at tick 6 (mock budget=6).
    open_now = list(scheduler.iter_open_dialogs())
    for did, init_id, target_id, _z in open_now:
        # Stamp activity at tick 6 so close anchors cooldown there.
        scheduler.record_turn(
            DialogTurnMsg(
                tick=6,
                dialog_id=did,
                speaker_id=init_id,
                addressee_id=target_id,
                turn_index=0,
                utterance="warmup",
            )
        )
        scheduler.close_dialog(did, reason="exhausted", tick=6)
    assert scheduler.open_count == 0

    # Now agents scatter. Drive ticks past the eval cooldown and check
    # admit resumes. m9-eval-system P3a-decide v2: eval mode uses
    # ``COOLDOWN_TICKS_EVAL=5`` so far_tick is anchored at 11 (= turn_index
    # close at tick 6 + 5-tick eval cooldown), not at 36 like live mode.
    scattered = [
        AgentView(agent_id="kant", zone=Zone.STUDY, tick=11),
        AgentView(agent_id="nietzsche", zone=Zone.PERIPATOS, tick=11),
        AgentView(agent_id="rikyu", zone=Zone.CHASHITSU, tick=11),
    ]
    far_tick = 6 + scheduler.COOLDOWN_TICKS_EVAL  # 11
    scheduler.tick(world_tick=far_tick, agents=scattered)
    assert scheduler.open_count == 3, (
        "after eval cooldown expires, all three pairs should re-admit even "
        "though every agent is in a different zone"
    )


# ---------------------------------------------------------------------------
# v2 additions: _effective_cooldown helper + live-mode parity behavior tests
# ---------------------------------------------------------------------------


def test_effective_cooldown_returns_eval_value_when_flag_true() -> None:
    """``_effective_cooldown()`` returns ``COOLDOWN_TICKS_EVAL=5`` in eval mode."""
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink, eval_natural_mode=True)
    assert scheduler._effective_cooldown() == scheduler.COOLDOWN_TICKS_EVAL
    assert scheduler.COOLDOWN_TICKS_EVAL == 5


def test_effective_cooldown_returns_live_value_when_flag_false() -> None:
    """``_effective_cooldown()`` returns ``COOLDOWN_TICKS=30`` in live mode.

    Guards against accidental regression where the eval-mode reduced threshold
    leaks into live multi-agent runs and shortens the live natural cadence.
    """
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(envelope_sink=sink, eval_natural_mode=False)
    assert scheduler._effective_cooldown() == scheduler.COOLDOWN_TICKS
    assert scheduler.COOLDOWN_TICKS == 30


def test_live_mode_cooldown_unchanged_via_tick() -> None:
    """Live mode (``eval_natural_mode=False``) keeps the 30-tick cooldown.

    m9-eval-system P3a-decide v2 invariant test: the v2 ``_effective_cooldown()``
    refactor must not regress live-mode behaviour. Reject re-admit at tick 29,
    admit again at tick 30. Co-located in AGORA so the only gate left after
    close is cooldown itself.
    """
    _captured, sink = _collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=sink, rng=_always_fire(), eval_natural_mode=False
    )
    agents = [
        AgentView(agent_id="kant", zone=Zone.AGORA, tick=0),
        AgentView(agent_id="rikyu", zone=Zone.AGORA, tick=0),
    ]
    scheduler.tick(world_tick=0, agents=agents)
    assert scheduler.open_count == 1
    [(did, _i, _t, _z)] = list(scheduler.iter_open_dialogs())
    scheduler.close_dialog(did, reason="exhausted", tick=0)

    # Tick 29 — still inside live-mode cooldown.
    scheduler.tick(world_tick=scheduler.COOLDOWN_TICKS - 1, agents=agents)
    assert scheduler.open_count == 0, (
        "live-mode cooldown breached: same pair re-admitted before "
        f"COOLDOWN_TICKS={scheduler.COOLDOWN_TICKS}"
    )

    # Tick 30 — cooldown expired, re-admit.
    scheduler.tick(world_tick=scheduler.COOLDOWN_TICKS, agents=agents)
    assert scheduler.open_count == 1
