"""較正 pilot の腕・decode・plan・機械検査 (pilot prereg §2).

各検査には、壊した設定を捕まえる陽性対照を添える。
"""

from __future__ import annotations

import pytest
from scripts import body_walk_battery as bat
from scripts import closed_loop_battery as v4
from scripts import closed_loop_v5_battery as v5
from scripts import skill_lever_battery as v2
from scripts.skill_lever_scorer import request_meta
from scripts.stage_b_battery import dev_signatures

from erre_sandbox.erre.locomotion_sampling import (
    DEFAULT_LOCO_GAIN_P,
    DEFAULT_LOCO_GAIN_T,
    locomotion_delta,
)
from erre_sandbox.erre.sampling_table import SAMPLING_DELTA_BY_MODE
from erre_sandbox.inference.sampling import compose_sampling
from erre_sandbox.schemas import ERREModeName, LocomotionState, SamplingBase


def test_battery_checks_pass() -> None:
    assert bat.battery_violations() == []


def test_frozen_constants() -> None:
    assert tuple(range(16, 28)) == bat.PILOT_R
    assert bat.PILOT_M == 8
    assert bat.M_WINDOWS == (4, 6, 8)
    assert bat.WALK_LAMBDA == 1.0
    assert bat.n_loop_calls() == 4608
    assert bat.n_replay_calls() == 108
    assert len(bat.pilot_plan()) == 4716
    assert bat.pilot_seed(16, 0) == 23_276_930
    assert bat.OLLAMA_VERSION == "0.32.12"
    assert bat.MODEL_DIGEST.startswith("500a1f067a9f")
    assert "top_k                          20" in bat.MODEL_PARAMETERS


def test_walk_sampling_is_the_composed_endpoint() -> None:
    """歩行 = compose_sampling の出力そのもの.

    手書きの 0.95 を正本にしない。値は ERRE の凍結値から。
    """
    want = compose_sampling(
        SamplingBase(temperature=0.7, top_p=0.8, repeat_penalty=1.0),
        SAMPLING_DELTA_BY_MODE[ERREModeName.PERIPATETIC],
        locomotion_delta(
            LocomotionState(lam=1.0),
            gain_t=DEFAULT_LOCO_GAIN_T,
            gain_p=DEFAULT_LOCO_GAIN_P,
        ),
    )
    walk = bat.walk_sampling()
    assert walk == want
    assert (walk.temperature, walk.top_p, walk.repeat_penalty) == bat.FROZEN_WALK
    assert bat.FROZEN_WALK == (1.3, 0.9500000000000001, 0.9)
    sit = bat.sit_sampling()
    assert (sit.temperature, sit.top_p, sit.repeat_penalty) == (
        v2.TEMPERATURE,
        v2.TOP_P,
        v2.REPEAT_PENALTY,
    )


def test_request_meta_walk() -> None:
    meta = bat.request_meta_walk()
    walk = bat.walk_sampling()
    base = request_meta()
    assert set(meta) == {*base, "ollama_version", "model_digest", "model_parameters"}
    assert meta["temperature"] == walk.temperature
    assert meta["top_p"] == walk.top_p
    assert meta["repeat_penalty"] == walk.repeat_penalty
    for key in ("model", "think", "num_ctx", "num_predict"):
        assert meta[key] == base[key]
    assert meta["ollama_version"] == bat.OLLAMA_VERSION
    assert meta["model_digest"] == bat.MODEL_DIGEST
    assert meta["model_parameters"] == bat.MODEL_PARAMETERS


def test_sampling_check_catches_a_broken_direction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert bat.check_sampling() == []
    monkeypatch.setattr(bat, "WALK_LAMBDA", 0.5)
    # λ を変えると凍結時の観測値と合わない (向きの検査は通る)
    assert bat.check_sampling() == [
        "walk sampling differs from the value observed at freeze"
    ]
    monkeypatch.setattr(bat, "walk_sampling", bat.sit_sampling)
    assert "walk does not move T / top_p up and repeat_penalty down" in (
        bat.check_sampling()
    )


def test_messages_are_v4_r1() -> None:
    full = v4.State(succeeded=frozenset(dev_signatures()))
    for st in (v4.EMPTY_STATE, full):
        for w in v4.WORLDS:
            for t in (0, 5, 13, 95):
                msgs = bat.loop_messages(st, w, 16, t)
                assert msgs == v4.loop_messages(st, w, 16, t, v4.RENDERER_R1)
                assert v4.R1PLUS_TRIED_HEADER not in msgs[1]["content"]
    assert bat.render_state(v4.EMPTY_STATE, v4.WORLDS[0], 16) == v4.render_state(
        v4.EMPTY_STATE, v4.WORLDS[0], 16, v4.RENDERER_R1
    )


def test_rotation() -> None:
    for r in bat.PILOT_R:
        for t in range(bat.PILOT_T):
            assert bat.dev_options(r, t) == v4.dev_options(r, t)
            assert bat.dev_options(r, t) == bat.dev_options(r, t % bat.N_DEV)
    assert bat.check_rotation() == []


def test_replicates() -> None:
    assert bat.check_replicates() == []
    assert not set(bat.PILOT_R) & set(v5.PILOT_R)
    assert min(bat.PILOT_R) >= bat.MAIN_R_MAX


@pytest.mark.parametrize(
    ("r_values", "problem"),
    [
        (
            (0, *range(17, 28)),
            "pilot replicates overlap the main registration (r < 12)",
        ),
        ((12, *range(17, 28)), "pilot replicates overlap the v5 pilot"),
        ((16, *range(16, 27)), "pilot replicates are not unique"),
        (tuple(range(16, 27)), "pilot replicates do not balance r mod 4"),
    ],
)
def test_replicates_check_catches(
    monkeypatch: pytest.MonkeyPatch, r_values: tuple[int, ...], problem: str
) -> None:
    monkeypatch.setattr(bat, "PILOT_R", r_values)
    assert problem in bat.check_replicates()


def test_seed_disjoint() -> None:
    assert bat.check_seed_disjoint() == []
    seeds = bat.pilot_seeds()
    assert len(seeds) == 12 * 96
    assert not seeds & v5.pilot_seeds()


@pytest.mark.parametrize(
    ("base", "name"),
    [
        (v4.LOOP_SEED_BASE, "v4 loop"),
        (v5.PILOT_SEED_BASE, "v5 pilot"),
        (v2.SEED_BASE, "v2 probe"),
    ],
)
def test_seed_check_catches_collisions(
    monkeypatch: pytest.MonkeyPatch, base: int, name: str
) -> None:
    monkeypatch.setattr(bat, "PILOT_SEED_BASE", base)
    if name == "v5 pilot":
        monkeypatch.setattr(bat, "PILOT_R", v5.PILOT_R * 3)
    assert any(name in p for p in bat.check_seed_disjoint())


def test_plan_order() -> None:
    plan = bat.pilot_plan()
    n = bat.n_loop_calls()
    assert [k.world for k in plan[:4]] == list(v4.world_order(16))
    assert all(k.phase == bat.PHASE_LOOP for k in plan[:n])
    assert all(k.phase == bat.PHASE_REPLAY for k in plan[n:])
    assert [(k.replicate, k.step) for k in plan[:5]] == [(16, 0)] * 4 + [(16, 1)]
    replay16 = plan[n : n + 9]
    order = v4.world_order(16)
    assert [(k.world, k.step) for k in replay16] == [
        (order[0], 0),
        *((w, 47) for w in order),
        *((w, 95) for w in order),
    ]
    assert bat.check_plan() == []


def test_plan_check_catches_a_broken_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    good = bat.pilot_plan()
    monkeypatch.setattr(bat, "pilot_plan", lambda: [good[1], good[0], *good[2:]])
    assert bat.check_plan() == [
        "loop part is not in the frozen (r, t, world order) order"
    ]
    monkeypatch.setattr(bat, "pilot_plan", lambda: good[:-1])
    assert "replay part is not the registered subset after the loop" in (
        bat.check_plan()
    )
    monkeypatch.setattr(bat, "pilot_plan", lambda: [good[0], *good])
    assert "loop part does not cover each (world, r, t) exactly once" in (
        bat.check_plan()
    )


def test_non_leakage_and_budget() -> None:
    assert bat.check_non_leakage() == []
    assert bat.check_prompt_budget() == []
    assert bat.max_prompt_bytes() <= v2.MAX_PROMPT_BYTES


def test_non_leakage_catches_world_names(monkeypatch: pytest.MonkeyPatch) -> None:
    orig = bat.loop_messages

    def leaky(state: v4.State, world: str, r: int, t: int) -> list[dict[str, str]]:
        msgs = orig(state, world, r, t)
        return [msgs[0], {**msgs[1], "content": msgs[1]["content"] + f" {world}"}]

    monkeypatch.setattr(bat, "loop_messages", leaky)
    assert any("a_rot" in p or "b_rot" in p for p in bat.check_non_leakage())


def test_plan_check_catches_a_wrong_world_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """世界順を r に依らず固定した plan は、被覆は同じでも凍結順と違う."""
    good = bat.pilot_plan()
    n = bat.n_loop_calls()
    fixed = sorted(
        good[:n], key=lambda k: (k.replicate, k.step, v4.WORLDS.index(k.world))
    )
    monkeypatch.setattr(bat, "pilot_plan", lambda: [*fixed, *good[n:]])
    assert bat.check_plan() == [
        "loop part is not in the frozen (r, t, world order) order"
    ]
    assert [k.world for k in good[4 * 96 : 4 * 96 + 4]] == list(v4.world_order(17))


def test_rotation_check_catches_a_lap_rotation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bat, "dev_options", lambda r, t: v5.dev_options("B", r, t))
    got = bat.check_rotation()
    assert any("rotation differs from v4" in p for p in got)
    assert any("rotation changes across laps" in p for p in got)


@pytest.mark.parametrize(
    "name",
    [
        "check_sampling",
        "check_replicates",
        "check_seed_disjoint",
        "check_rotation",
        "check_plan",
        "check_non_leakage",
        "check_prompt_budget",
    ],
)
def test_battery_violations_aggregates_every_check(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    monkeypatch.setattr(bat, name, lambda: [f"marker {name}"])
    assert bat.battery_violations() == [f"marker {name}"]
