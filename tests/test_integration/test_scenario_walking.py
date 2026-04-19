"""Skeleton for S_WALKING scenario (skipped until T14 gateway lands).

The scenario data lives in :data:`erre_sandbox.integration.SCENARIO_WALKING`.
These tests are placeholders that reference the steps of that scenario by
index. When T14 provides a live gateway, drop the module-level skip marker
and fill each ``TODO`` with actual assertions against the WS stream.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="T19 実行フェーズ待ち (T14 完成後に点灯)")


def test_s_walking_step0_world_registers_kant_in_peripatos(walking_scenario):  # type: ignore[no-untyped-def]
    # TODO(T19): start WorldRuntime, register Kant in Peripatos,
    # drain one AgentUpdateMsg, assert erre_mode=SHALLOW, zone=PERIPATOS.
    step = walking_scenario.steps[0]
    assert step.actor == "world"


def test_s_walking_step1_gateway_heartbeat(walking_scenario):  # type: ignore[no-untyped-def]
    # TODO(T19): wait ~1s, expect one WorldTickMsg on the client.
    step = walking_scenario.steps[1]
    assert step.actor == "gateway"


def test_s_walking_step2_cognition_emits_move(walking_scenario):  # type: ignore[no-untyped-def]
    # TODO(T19): advance 10s, expect a MoveMsg with speed>0 and ERRE mode
    # transitioned to PERIPATETIC.
    step = walking_scenario.steps[2]
    assert step.actor == "cognition"


def test_s_walking_step3_godot_avatar_moves(walking_scenario):  # type: ignore[no-untyped-def]
    # TODO(T19): assert Godot side received animation=walk and the avatar
    # tween moved toward the target.
    step = walking_scenario.steps[3]
    assert step.actor == "godot"
