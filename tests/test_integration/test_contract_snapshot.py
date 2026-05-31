"""Drift-detection snapshot of the integration contract (always ON).

Unlike the skeleton scenario tests (skipped until T14), this module runs in
CI today. It locks down the **shape and values** of the integration contract
so that any silent drift in :mod:`erre_sandbox.integration` surfaces as a
failing test during review — before it reaches main.

Covered invariants:

* session lifecycle constants (heartbeat, timeouts, backlog bounds)
* ``SessionPhase`` enum membership
* ``Thresholds`` Pydantic model schema + ``M2_THRESHOLDS`` values
* ``Scenario`` / ``ScenarioStep`` shape + ``M2_SCENARIOS`` ids and cardinality
* ``AcceptanceItem`` shape + ``ACCEPTANCE_CHECKLIST`` id uniqueness

When a test here fails, the expected flow is:

1. Is the drift *intended*? → add a ``decisions.md`` entry, then update the
   matching literal in this file in the same PR.
2. Is the drift *accidental*? → revert the offending change.
"""

from __future__ import annotations

from erre_sandbox.integration import (
    ACCEPTANCE_CHECKLIST,
    HANDSHAKE_TIMEOUT_S,
    HEARTBEAT_INTERVAL_S,
    IDLE_DISCONNECT_S,
    M2_SCENARIOS,
    M2_THRESHOLDS,
    MAX_ENVELOPE_BACKLOG,
    SCENARIO_MEMORY_WRITE,
    SCENARIO_TICK_ROBUSTNESS,
    SCENARIO_WALKING,
    AcceptanceItem,
    Scenario,
    ScenarioStep,
    SessionPhase,
    Thresholds,
)
from erre_sandbox.schemas import ERREModeName, Zone

# ---------------------------------------------------------------------------
# Session lifecycle constants
# ---------------------------------------------------------------------------


def test_heartbeat_interval_is_one_second() -> None:
    assert HEARTBEAT_INTERVAL_S == 1.0


def test_handshake_timeout_is_five_seconds() -> None:
    assert HANDSHAKE_TIMEOUT_S == 5.0


def test_idle_disconnect_is_one_minute() -> None:
    assert IDLE_DISCONNECT_S == 60.0


def test_max_envelope_backlog_is_256() -> None:
    assert MAX_ENVELOPE_BACKLOG == 256


def test_session_phase_membership() -> None:
    assert {p.value for p in SessionPhase} == {
        "awaiting_handshake",
        "active",
        "closing",
    }


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------


def test_thresholds_is_frozen() -> None:
    assert Thresholds.model_config.get("frozen") is True


def test_thresholds_forbids_extra_fields() -> None:
    assert Thresholds.model_config.get("extra") == "forbid"


def test_m2_thresholds_values() -> None:
    assert M2_THRESHOLDS.latency_p50_ms_max == 100.0
    assert M2_THRESHOLDS.latency_p95_ms_max == 250.0
    assert M2_THRESHOLDS.tick_jitter_sigma_max == 0.20
    assert M2_THRESHOLDS.memory_write_success_rate_min == 0.98
    assert M2_THRESHOLDS.arousal_min == 0.0
    assert M2_THRESHOLDS.arousal_max == 1.0
    assert M2_THRESHOLDS.valence_min == -1.0
    assert M2_THRESHOLDS.valence_max == 1.0
    assert M2_THRESHOLDS.attention_min == 0.0
    assert M2_THRESHOLDS.attention_max == 1.0


def test_m2_thresholds_schema_field_names() -> None:
    expected = {
        "latency_p50_ms_max",
        "latency_p95_ms_max",
        "tick_jitter_sigma_max",
        "memory_write_success_rate_min",
        "arousal_min",
        "arousal_max",
        "valence_min",
        "valence_max",
        "attention_min",
        "attention_max",
    }
    assert set(Thresholds.model_fields.keys()) == expected


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


def test_m2_scenarios_has_three_items() -> None:
    assert len(M2_SCENARIOS) == 3


def test_m2_scenario_ids() -> None:
    assert tuple(s.id for s in M2_SCENARIOS) == (
        "S_WALKING",
        "S_MEMORY_WRITE",
        "S_TICK_ROBUSTNESS",
    )


def test_all_scenarios_are_kant_in_peripatos() -> None:
    for scenario in M2_SCENARIOS:
        assert scenario.persona_id == "kant"
        assert scenario.zone == Zone.PERIPATOS


def test_scenario_walking_erre_modes() -> None:
    assert SCENARIO_WALKING.erre_modes == (
        ERREModeName.SHALLOW,
        ERREModeName.PERIPATETIC,
    )


def test_scenario_memory_write_erre_mode() -> None:
    assert SCENARIO_MEMORY_WRITE.erre_modes == (ERREModeName.PERIPATETIC,)


def test_scenario_tick_robustness_erre_modes() -> None:
    assert SCENARIO_TICK_ROBUSTNESS.erre_modes == (
        ERREModeName.SHALLOW,
        ERREModeName.PERIPATETIC,
    )


def test_scenario_steps_are_monotonic_in_time() -> None:
    for scenario in M2_SCENARIOS:
        times = [step.t_s for step in scenario.steps]
        assert times == sorted(times), (
            f"Scenario {scenario.id} steps must be sorted by t_s"
        )


def test_scenario_step_actors_are_known() -> None:
    known = {"world", "cognition", "gateway", "godot"}
    for scenario in M2_SCENARIOS:
        for step in scenario.steps:
            assert step.actor in known, (
                f"Scenario {scenario.id} has unknown actor {step.actor!r}"
            )


def test_scenario_is_frozen() -> None:
    assert Scenario.__dataclass_params__.frozen is True
    assert ScenarioStep.__dataclass_params__.frozen is True


# ---------------------------------------------------------------------------
# Acceptance checklist
# ---------------------------------------------------------------------------


def test_acceptance_checklist_has_15_items() -> None:
    assert len(ACCEPTANCE_CHECKLIST) == 15


def test_acceptance_ids_are_unique() -> None:
    ids = [item.id for item in ACCEPTANCE_CHECKLIST]
    assert len(set(ids)) == len(ids)


def test_acceptance_ids_have_acc_prefix() -> None:
    for item in ACCEPTANCE_CHECKLIST:
        assert item.id.startswith("ACC-"), (
            f"Acceptance id must start with ACC-, got {item.id!r}"
        )


def test_acceptance_categories_whitelist() -> None:
    known = {
        "schema",
        "runtime",
        "memory",
        "observability",
        "reproducibility",
        "docs",
    }
    for item in ACCEPTANCE_CHECKLIST:
        assert item.category in known, (
            f"{item.id} has unknown category {item.category!r}"
        )


def test_acceptance_item_is_frozen() -> None:
    assert AcceptanceItem.__dataclass_params__.frozen is True
