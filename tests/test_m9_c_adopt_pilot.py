"""Smoke tests for ``scripts/m9-c-adopt/tier_b_pilot.py`` multi-turn logic.

Codex HIGH-4 mitigation 1 (m9-c-adopt-pilot-multiturn investigation
2026-05-14): ensure ``_focal_turn_count`` / ``_total_turn_count`` /
``_stratified_slice`` honour ``expected_turn_count`` and the
``--multi-turn-max`` cap without spinning up SGLang. The end-to-end DuckDB
schema + speaker alternation is exercised by the post-capture validation
query stored alongside the artefacts.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PILOT_PATH = _REPO_ROOT / "scripts" / "m9-c-adopt" / "tier_b_pilot.py"


@pytest.fixture(scope="module")
def pilot_module():
    spec = importlib.util.spec_from_file_location("tier_b_pilot", _PILOT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["tier_b_pilot"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("expected_turn_count", "multi_turn_max", "expected_focal", "expected_total"),
    [
        # single-turn legacy mode (DA-11, multi_turn_max=1)
        (1, 1, 1, 1),
        (2, 1, 1, 1),
        (3, 1, 1, 1),
        # multi-turn investigation (HIGH-1)
        (1, 6, 1, 1),
        (2, 6, 1, 2),  # focal=1 (turn 0), interlocutor=1 (turn 1)
        (3, 6, 2, 3),  # focal=2 (turn 0, 2), interlocutor=1 (turn 1)
        # multi-turn cap fires when expected > max
        (5, 3, 2, 3),  # capped to 3 turns: focal=2 (0, 2), interlocutor=1
        (4, 2, 1, 2),  # capped to 2 turns: focal=1 (0), interlocutor=1
    ],
)
def test_focal_and_total_turn_count(
    pilot_module, expected_turn_count, multi_turn_max, expected_focal, expected_total
):
    stim = {"stimulus_id": "test", "expected_turn_count": expected_turn_count}
    assert pilot_module._focal_turn_count(stim, multi_turn_max) == expected_focal
    assert pilot_module._total_turn_count(stim, multi_turn_max) == expected_total


def test_stratified_slice_multi_turn_target(pilot_module):
    """Stratified slice should pick enough stimuli to cover focal target."""
    battery = [
        {"stimulus_id": f"s{i}", "category": "wachsmuth", "expected_turn_count": 2}
        for i in range(10)
    ] + [
        {"stimulus_id": f"r{i}", "category": "roleeval", "expected_turn_count": 1}
        for i in range(5)
    ]
    # single-turn: every stim contributes 1 focal turn, target 8 → 8 stims
    sliced_single = pilot_module._stratified_slice(
        battery, target_focal_per_cycle=8, multi_turn_max=1
    )
    assert sum(
        pilot_module._focal_turn_count(s, 1) for s in sliced_single
    ) >= 8
    # multi-turn max=2: wachsmuth 2-turn → ceil(2/2)=1 focal each, roleeval 1-turn → 1
    # same as single in this synthetic battery; capacity = 15
    sliced_multi = pilot_module._stratified_slice(
        battery, target_focal_per_cycle=8, multi_turn_max=6
    )
    assert sum(
        pilot_module._focal_turn_count(s, 6) for s in sliced_multi
    ) >= 8


def test_stratified_slice_returns_full_battery_on_oversize_target(pilot_module):
    battery = [
        {"stimulus_id": f"s{i}", "category": "wachsmuth", "expected_turn_count": 1}
        for i in range(3)
    ]
    sliced = pilot_module._stratified_slice(
        battery, target_focal_per_cycle=999, multi_turn_max=1
    )
    assert len(sliced) == len(battery)


def test_derive_seed_distinct_for_lora_vs_nolora(pilot_module):
    s_lora = pilot_module._derive_seed("kant", 8, 0, no_lora=False)
    s_nolora = pilot_module._derive_seed("kant", 8, 0, no_lora=True)
    assert s_lora != s_nolora


def test_derive_seed_stable(pilot_module):
    a = pilot_module._derive_seed("kant", 8, 0, no_lora=False)
    b = pilot_module._derive_seed("kant", 8, 0, no_lora=False)
    assert a == b
    # Different run_idx must yield distinct seeds.
    c = pilot_module._derive_seed("kant", 8, 1, no_lora=False)
    assert a != c


def test_build_user_prompt_includes_turn_marker(pilot_module):
    stim = {
        "stimulus_id": "kant_w01",
        "category": "wachsmuth",
        "prompt_text": "Formuliere die These.",
    }
    p0 = pilot_module._build_user_prompt(stim, cycle_idx=2, turn_index=0)
    p1 = pilot_module._build_user_prompt(stim, cycle_idx=2, turn_index=1)
    assert "turn=0" in p0
    assert "turn=1" in p1
    assert "Formuliere die These." in p0
