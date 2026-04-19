"""Tests for ``erre_sandbox.world.physics`` (T13)."""

from __future__ import annotations

import math

import pytest

from erre_sandbox.schemas import MoveMsg, Position, Zone
from erre_sandbox.world.physics import Kinematics, apply_move_command, step_kinematics
from erre_sandbox.world.zones import default_spawn


@pytest.fixture
def kin_at_peripatos_centre() -> Kinematics:
    return Kinematics(position=default_spawn(Zone.PERIPATOS))


class TestStepKinematicsIdleCases:
    def test_no_destination_keeps_position_and_zone(
        self,
        kin_at_peripatos_centre: Kinematics,
    ) -> None:
        before = kin_at_peripatos_centre.position
        new_pos, zone_changed = step_kinematics(kin_at_peripatos_centre, 1.0)
        assert new_pos == before
        assert zone_changed is None

    def test_zero_dt_is_a_no_op_even_with_destination(
        self,
        kin_at_peripatos_centre: Kinematics,
    ) -> None:
        kin_at_peripatos_centre.destination = default_spawn(Zone.GARDEN)
        before = kin_at_peripatos_centre.position
        new_pos, zone_changed = step_kinematics(kin_at_peripatos_centre, 0.0)
        assert new_pos == before
        assert zone_changed is None


class TestStepKinematicsMoving:
    def test_short_step_interpolates_without_reaching_destination(
        self,
        kin_at_peripatos_centre: Kinematics,
    ) -> None:
        # Peripatos centre (0, 0, 0) → Garden centre (20, 0, 20), 1.3 m/s, dt=1s.
        kin_at_peripatos_centre.destination = default_spawn(Zone.GARDEN)
        kin_at_peripatos_centre.speed_mps = 1.3
        new_pos, _zone_changed = step_kinematics(kin_at_peripatos_centre, 1.0)
        # Total distance is hypot(20, 20) ≈ 28.28 m, so after 1 s of 1.3 m/s we
        # should have travelled ~1.3 m along the direct line.
        travelled = math.hypot(new_pos.x, new_pos.z)
        assert travelled == pytest.approx(1.3, abs=1e-6)
        assert kin_at_peripatos_centre.destination is not None

    def test_long_step_snaps_to_destination_and_clears_it(
        self,
        kin_at_peripatos_centre: Kinematics,
    ) -> None:
        dest = default_spawn(Zone.GARDEN)
        kin_at_peripatos_centre.destination = dest
        kin_at_peripatos_centre.speed_mps = 100.0
        new_pos, zone_changed = step_kinematics(kin_at_peripatos_centre, 1.0)
        assert new_pos == dest
        assert kin_at_peripatos_centre.destination is None
        assert zone_changed is Zone.GARDEN

    def test_zone_change_reported_when_crossing_boundary(
        self,
        kin_at_peripatos_centre: Kinematics,
    ) -> None:
        # Start at (0,0,0) peripatos, go to (11, 0, 11) — just into GARDEN.
        kin_at_peripatos_centre.destination = Position(
            x=11.0,
            y=0.0,
            z=11.0,
            zone=Zone.GARDEN,
        )
        kin_at_peripatos_centre.speed_mps = 100.0
        new_pos, zone_changed = step_kinematics(kin_at_peripatos_centre, 1.0)
        assert zone_changed is Zone.GARDEN
        assert new_pos.zone is Zone.GARDEN

    def test_no_zone_change_when_staying_within_cell(
        self,
        kin_at_peripatos_centre: Kinematics,
    ) -> None:
        kin_at_peripatos_centre.destination = Position(
            x=2.0,
            y=0.0,
            z=2.0,
            zone=Zone.PERIPATOS,
        )
        kin_at_peripatos_centre.speed_mps = 1.0
        _new_pos, zone_changed = step_kinematics(kin_at_peripatos_centre, 0.5)
        assert zone_changed is None

    def test_position_preserves_yaw_and_pitch(
        self,
        kin_at_peripatos_centre: Kinematics,
    ) -> None:
        kin_at_peripatos_centre.position = Position(
            x=0.0,
            y=0.0,
            z=0.0,
            zone=Zone.PERIPATOS,
            yaw=1.5,
            pitch=-0.2,
        )
        kin_at_peripatos_centre.destination = Position(
            x=5.0,
            y=0.0,
            z=0.0,
            zone=Zone.PERIPATOS,
        )
        kin_at_peripatos_centre.speed_mps = 1.0
        new_pos, _ = step_kinematics(kin_at_peripatos_centre, 1.0)
        assert new_pos.yaw == pytest.approx(1.5)
        assert new_pos.pitch == pytest.approx(-0.2)


class TestApplyMoveCommand:
    def test_sets_destination_and_speed(
        self,
        kin_at_peripatos_centre: Kinematics,
    ) -> None:
        target = Position(x=5.0, y=0.0, z=5.0, zone=Zone.PERIPATOS)
        move = MoveMsg(tick=7, agent_id="a_kant_001", target=target, speed=2.5)
        apply_move_command(kin_at_peripatos_centre, move)
        assert kin_at_peripatos_centre.destination == target
        assert kin_at_peripatos_centre.speed_mps == pytest.approx(2.5)

    def test_zero_speed_is_coerced_to_default(
        self,
        kin_at_peripatos_centre: Kinematics,
    ) -> None:
        target = Position(x=5.0, y=0.0, z=0.0, zone=Zone.PERIPATOS)
        move = MoveMsg(tick=7, agent_id="a_kant_001", target=target, speed=0.0)
        apply_move_command(kin_at_peripatos_centre, move)
        assert kin_at_peripatos_centre.speed_mps == pytest.approx(1.3)


class TestNonFiniteDestination:
    """Defence against NaN / Inf coordinates injected via LLM-generated moves.

    Security-checker flagged that a malformed ``MoveMsg.target`` would
    otherwise propagate NaN into ``Position`` and silently bias ``locate_zone``
    toward the first zone. See decisions.md for the trade-off.
    """

    @pytest.mark.parametrize(
        "bad_xyz",
        [
            (math.inf, 0.0, 0.0),
            (0.0, math.nan, 0.0),
            (0.0, 0.0, -math.inf),
        ],
    )
    def test_non_finite_destination_is_cleared(
        self,
        kin_at_peripatos_centre: Kinematics,
        bad_xyz: tuple[float, float, float],
    ) -> None:
        bx, by, bz = bad_xyz
        kin_at_peripatos_centre.destination = Position(
            x=bx,
            y=by,
            z=bz,
            zone=Zone.PERIPATOS,
        )
        before = kin_at_peripatos_centre.position
        new_pos, zone_changed = step_kinematics(kin_at_peripatos_centre, 1.0)
        assert new_pos == before
        assert zone_changed is None
        assert kin_at_peripatos_centre.destination is None
