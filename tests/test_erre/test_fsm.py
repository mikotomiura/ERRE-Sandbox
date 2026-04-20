"""Unit tests for the event-driven ERRE mode FSM (M5).

Covers two layers:

* **Per-handler (pure function) tests** for ``_on_zone_transition``,
  ``_on_internal``, ``_on_mode_shift``. These isolate the parsing / lookup
  logic of each Observation kind from the accumulation loop in the policy
  class.
* **Integration tests** for ``DefaultERREModePolicy.next_mode``, validating
  the "latest signal wins" accumulation semantics, the idempotency wrap
  (``None`` when the aggregate equals ``current``), and the DI contract
  (``zone_defaults`` overridable).

The FSM itself is pure and synchronous, so tests are simple constructors
without fixtures.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from erre_sandbox.erre.fsm import (
    SHUHARI_TO_MODE,
    ZONE_TO_DEFAULT_ERRE_MODE,
    DefaultERREModePolicy,
    _on_internal,
    _on_mode_shift,
    _on_zone_transition,
)
from erre_sandbox.schemas import (
    ERREModeName,
    ERREModeShiftEvent,
    InternalEvent,
    PerceptionEvent,
    ShuhariStage,
    Zone,
    ZoneTransitionEvent,
)

# ---------- shared helpers -----------------------------------------------


def _zone_ev(
    to_zone: Zone, *, from_zone: Zone = Zone.STUDY, tick: int = 1
) -> ZoneTransitionEvent:
    return ZoneTransitionEvent(
        tick=tick,
        agent_id="a_kant_001",
        from_zone=from_zone,
        to_zone=to_zone,
    )


def _internal_ev(content: str, *, tick: int = 1) -> InternalEvent:
    return InternalEvent(tick=tick, agent_id="a_kant_001", content=content)


def _shift_ev(
    reason: str,
    *,
    previous: ERREModeName = ERREModeName.DEEP_WORK,
    current: ERREModeName = ERREModeName.PERIPATETIC,
    tick: int = 1,
) -> ERREModeShiftEvent:
    return ERREModeShiftEvent(
        tick=tick,
        agent_id="a_kant_001",
        previous=previous,
        current=current,
        # parametrized str → Literal narrowing is safe in test context
        reason=reason,  # type: ignore[arg-type]
    )


# =========================================================================
# Per-handler tests (_on_zone_transition)
# =========================================================================


@pytest.mark.parametrize(
    ("to_zone", "expected_mode"),
    [
        (Zone.STUDY, ERREModeName.DEEP_WORK),
        (Zone.PERIPATOS, ERREModeName.PERIPATETIC),
        (Zone.CHASHITSU, ERREModeName.CHASHITSU),
        (Zone.AGORA, ERREModeName.SHALLOW),
        (Zone.GARDEN, ERREModeName.PERIPATETIC),
    ],
)
def test_zone_transition_handler_returns_zone_default(
    to_zone: Zone,
    expected_mode: ERREModeName,
) -> None:
    ev = _zone_ev(to_zone)
    assert (
        _on_zone_transition(ev, zone_defaults=ZONE_TO_DEFAULT_ERRE_MODE)
        == expected_mode
    )


def test_zone_transition_handler_returns_none_for_unmapped_zone() -> None:
    # Construct a map missing one entry and verify miss → None.
    sparse_map = {Zone.STUDY: ERREModeName.DEEP_WORK}
    ev = _zone_ev(Zone.PERIPATOS)
    assert _on_zone_transition(ev, zone_defaults=sparse_map) is None


# =========================================================================
# Per-handler tests (_on_internal)
# =========================================================================


@pytest.mark.parametrize(
    ("content", "expected_mode"),
    [
        ("shuhari_promote:shu", ERREModeName.SHU_KATA),
        ("shuhari_promote:ha", ERREModeName.HA_DEVIATE),
        ("shuhari_promote:ri", ERREModeName.RI_CREATE),
    ],
)
def test_internal_handler_recognises_shuhari_promote(
    content: str,
    expected_mode: ERREModeName,
) -> None:
    assert _on_internal(_internal_ev(content)) == expected_mode


def test_internal_handler_ignores_invalid_shuhari_stage() -> None:
    assert _on_internal(_internal_ev("shuhari_promote:xyz")) is None


def test_internal_handler_recognises_fatigue_prefix() -> None:
    # Prefix-based match; suffix content is not parsed.
    assert _on_internal(_internal_ev("fatigue: mild onset")) == ERREModeName.CHASHITSU


def test_internal_handler_recognises_empty_fatigue() -> None:
    assert _on_internal(_internal_ev("fatigue:")) == ERREModeName.CHASHITSU


def test_internal_handler_ignores_unknown_content() -> None:
    assert _on_internal(_internal_ev("just thinking")) is None


# =========================================================================
# Per-handler tests (_on_mode_shift)
# =========================================================================


def test_mode_shift_handler_returns_none_for_external_reason() -> None:
    assert _on_mode_shift(_shift_ev("external")) is None


@pytest.mark.parametrize("reason", ["scheduled", "zone", "fatigue", "reflection"])
def test_mode_shift_handler_returns_event_current_for_other_reasons(
    reason: str,
) -> None:
    ev = _shift_ev(reason, current=ERREModeName.ZAZEN)
    assert _on_mode_shift(ev) == ERREModeName.ZAZEN


# =========================================================================
# FSM integration tests (DefaultERREModePolicy.next_mode)
# =========================================================================


class TestDefaultPolicyIntegration:
    def _policy(self) -> DefaultERREModePolicy:
        return DefaultERREModePolicy()

    def test_empty_observations_returns_none(self) -> None:
        assert (
            self._policy().next_mode(
                current=ERREModeName.DEEP_WORK,
                zone=Zone.STUDY,
                observations=[],
                tick=0,
            )
            is None
        )

    def test_zone_entry_returns_default_mode_for_zone(self) -> None:
        result = self._policy().next_mode(
            current=ERREModeName.DEEP_WORK,
            zone=Zone.STUDY,
            observations=[_zone_ev(Zone.PERIPATOS)],
            tick=1,
        )
        assert result == ERREModeName.PERIPATETIC

    def test_zone_entry_returns_none_when_already_in_default(self) -> None:
        result = self._policy().next_mode(
            current=ERREModeName.PERIPATETIC,
            zone=Zone.PERIPATOS,
            observations=[_zone_ev(Zone.PERIPATOS)],
            tick=1,
        )
        assert result is None

    def test_latest_signal_wins_fatigue_after_zone(self) -> None:
        # Zone entry first, then fatigue — latest (fatigue) wins → CHASHITSU.
        result = self._policy().next_mode(
            current=ERREModeName.DEEP_WORK,
            zone=Zone.STUDY,
            observations=[
                _zone_ev(Zone.PERIPATOS, tick=1),
                _internal_ev("fatigue:", tick=2),
            ],
            tick=2,
        )
        assert result == ERREModeName.CHASHITSU

    def test_latest_signal_wins_zone_after_fatigue(self) -> None:
        # Fatigue first, zone entry later → PERIPATETIC.
        result = self._policy().next_mode(
            current=ERREModeName.DEEP_WORK,
            zone=Zone.STUDY,
            observations=[
                _internal_ev("fatigue:", tick=1),
                _zone_ev(Zone.PERIPATOS, tick=2),
            ],
            tick=2,
        )
        assert result == ERREModeName.PERIPATETIC

    def test_external_shift_is_noop_even_with_other_signals(self) -> None:
        # Fatigue would normally trigger CHASHITSU, but external shift after
        # returns None (caller already updated state). Since the external
        # handler returns None, the accumulated value is CHASHITSU; the caller
        # then updates AgentState to CHASHITSU via the returned mode. The
        # "no-op" guarantee is that external doesn't overwrite CHASHITSU.
        result = self._policy().next_mode(
            current=ERREModeName.DEEP_WORK,
            zone=Zone.STUDY,
            observations=[
                _internal_ev("fatigue:", tick=1),
                _shift_ev("external", tick=2),
            ],
            tick=2,
        )
        assert result == ERREModeName.CHASHITSU

    def test_external_shift_returns_none_when_matching_current(self) -> None:
        # Matches the docstring guarantee: if caller has already updated state,
        # passing current=CHASHITSU with external shift → None.
        result = self._policy().next_mode(
            current=ERREModeName.CHASHITSU,
            zone=Zone.STUDY,
            observations=[_shift_ev("external", tick=1)],
            tick=1,
        )
        assert result is None

    def test_mode_shift_scheduled_adopts_event_current(self) -> None:
        result = self._policy().next_mode(
            current=ERREModeName.DEEP_WORK,
            zone=Zone.STUDY,
            observations=[_shift_ev("scheduled", current=ERREModeName.ZAZEN)],
            tick=1,
        )
        assert result == ERREModeName.ZAZEN

    def test_unknown_observation_kind_returns_none(self) -> None:
        perception = PerceptionEvent(
            tick=1,
            agent_id="a_kant_001",
            modality="sight",
            source_zone=Zone.PERIPATOS,
            content="cherry blossom",
            wall_clock=datetime.now(tz=UTC),
        )
        assert (
            self._policy().next_mode(
                current=ERREModeName.DEEP_WORK,
                zone=Zone.STUDY,
                observations=[perception],
                tick=1,
            )
            is None
        )

    def test_shuhari_promote_flow(self) -> None:
        policy = self._policy()
        # shu → shu_kata
        assert (
            policy.next_mode(
                current=ERREModeName.DEEP_WORK,
                zone=Zone.STUDY,
                observations=[_internal_ev("shuhari_promote:shu")],
                tick=1,
            )
            == ERREModeName.SHU_KATA
        )
        # ha → ha_deviate
        assert (
            policy.next_mode(
                current=ERREModeName.SHU_KATA,
                zone=Zone.STUDY,
                observations=[_internal_ev("shuhari_promote:ha")],
                tick=1,
            )
            == ERREModeName.HA_DEVIATE
        )
        # ri → ri_create
        assert (
            policy.next_mode(
                current=ERREModeName.HA_DEVIATE,
                zone=Zone.STUDY,
                observations=[_internal_ev("shuhari_promote:ri")],
                tick=1,
            )
            == ERREModeName.RI_CREATE
        )


# =========================================================================
# DI: zone_defaults override
# =========================================================================


def test_custom_zone_defaults_respected() -> None:
    custom_map = {
        Zone.STUDY: ERREModeName.ZAZEN,  # override STUDY → ZAZEN
        Zone.PERIPATOS: ERREModeName.PERIPATETIC,
        Zone.CHASHITSU: ERREModeName.CHASHITSU,
        Zone.AGORA: ERREModeName.SHALLOW,
        Zone.GARDEN: ERREModeName.PERIPATETIC,
    }
    policy = DefaultERREModePolicy(zone_defaults=custom_map)
    result = policy.next_mode(
        current=ERREModeName.DEEP_WORK,
        zone=Zone.PERIPATOS,
        observations=[_zone_ev(Zone.STUDY)],
        tick=1,
    )
    assert result == ERREModeName.ZAZEN


# =========================================================================
# Invariants of the canonical maps
# =========================================================================


def test_zone_to_default_map_covers_all_zones() -> None:
    for zone in Zone:
        assert zone in ZONE_TO_DEFAULT_ERRE_MODE, f"zone {zone} missing a default mode"


def test_shuhari_to_mode_covers_all_stages() -> None:
    for stage in ShuhariStage:
        assert stage in SHUHARI_TO_MODE, f"stage {stage} missing a target mode"
