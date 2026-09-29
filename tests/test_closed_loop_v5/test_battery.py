"""較正 pilot の軸・renderer・plan・機械検査 (pilot prereg §2).

各検査には、壊した設定を捕まえる陽性対照を添える。
"""

from __future__ import annotations

import pytest
from scripts import closed_loop_battery as v4
from scripts import closed_loop_v5_battery as bat
from scripts import skill_lever_battery as v2


def test_battery_checks_pass() -> None:
    assert bat.battery_violations() == []


def test_frozen_constants() -> None:
    assert bat.PILOT_R == (12, 13, 14, 15)
    assert bat.PILOT_M == 8
    assert bat.M_WINDOWS == (4, 6, 8)
    assert bat.n_pilot_calls() == 3072 == len(bat.pilot_plan())
    assert bat.EXPLORE_SENTENCE == (
        "成功した記録の無い条件では、まだ試していない行動も試して、成功する行動を探すこと。"
    )
    assert bat.pilot_seed(12, 0) == 22_272_928


def test_rotation() -> None:
    for r in bat.PILOT_R:
        for t in range(bat.PILOT_T):
            assert bat.shift("B", r, t) == (r + t + t // 12) % 4
            assert bat.dev_options("C", r, t) == v4.dev_options(r, t)
            # B は 4 周ごとに位相が戻る
            if t + 48 < bat.PILOT_T:
                assert bat.dev_options("B", r, t) == bat.dev_options("B", r, t + 48)
    with pytest.raises(ValueError, match="unknown axis"):
        bat.shift("D", 0, 0)


def test_messages_layout() -> None:
    st = v4.EMPTY_STATE
    w = v4.WORLDS[0]
    b = bat.loop_messages(st, w, 12, 3, "B")
    c = bat.loop_messages(st, w, 12, 3, "C")
    assert b[0] == c[0] == {"role": "system", "content": v2.SYSTEM_PROMPT}
    assert b[1]["content"].startswith(v4.render_state(st, w, 12, v4.RENDERER_R1))
    assert c[1]["content"].startswith(v4.render_state(st, w, 12, v4.RENDERER_R1PLUS))
    parts = c[1]["content"].split("\n\n")
    assert parts[1] == bat.EXPLORE_SENTENCE
    assert parts[2] == v4.render_situation(
        v4.loop_signature(12, 3), bat.dev_options("C", 12, 3)
    )


def test_plan_order() -> None:
    plan = bat.pilot_plan()
    first = plan[:8]
    assert [k.axis for k in first] == ["B"] * 4 + ["C"] * 4
    assert [k.world for k in first[:4]] == list(v4.world_order(12))
    r13 = [k for k in plan if k.replicate == 13][:8]
    assert [k.axis for k in r13] == ["C"] * 4 + ["B"] * 4
    assert all(k.step == 0 for k in first)


# ---------------------------------------------------------------- 陽性対照


def test_replicate_check_catches_overlap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bat, "PILOT_R", (8, 9, 10, 11))
    assert bat.check_replicates() == [
        "pilot replicates overlap the v5 layouts (r < 12)"
    ]
    monkeypatch.setattr(bat, "PILOT_R", (12, 13, 14, 16))
    assert bat.check_replicates() == ["pilot replicates do not cover r mod 4"]


def test_seed_check_catches_collision(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bat, "PILOT_SEED_BASE", v4.LOOP_SEED_BASE)
    assert any("v4 loop" in x for x in bat.check_seed_disjoint())
    monkeypatch.setattr(bat, "PILOT_SEED_BASE", v2.SEED_BASE + 12 * 10_000 - 12_000)
    assert any("v2 probe" in x for x in bat.check_seed_disjoint())
    monkeypatch.setattr(bat, "PILOT_SEED_STRIDE", 0)
    assert "pilot seeds are not unique" in bat.check_seed_disjoint()


def test_rotation_check_catches_lap_invariant_b(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = bat.shift

    def v4_like(axis: str, r: int, t: int) -> int:
        return (r + t) % 4 if axis == "B" else real(axis, r, t)

    monkeypatch.setattr(bat, "shift", v4_like)
    assert any("does not change across laps" in x for x in bat.check_rotation_balance())


def test_rotation_check_catches_unbalanced(monkeypatch: pytest.MonkeyPatch) -> None:
    real = bat.shift
    monkeypatch.setattr(
        bat, "shift", lambda a, r, t: 0 if (a == "C" and t % 12 == 0) else real(a, r, t)
    )
    assert any("unbalanced" in x for x in bat.check_rotation_balance())


def test_renderer_check_catches_leaks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(v2, "SYSTEM_PROMPT", v2.SYSTEM_PROMPT + bat.EXPLORE_SENTENCE)
    assert "explore sentence appears in the system prompt" in bat.check_axis_renderers()


def test_renderer_check_catches_sentence_in_b(monkeypatch: pytest.MonkeyPatch) -> None:
    real = bat.loop_user_text

    def leaky(state, world, r, t, axis):
        return real(state, world, r, t, bat.AXIS_C if axis == bat.AXIS_B else axis)

    monkeypatch.setattr(bat, "loop_user_text", leaky)
    problems = bat.check_axis_renderers()
    assert any("explore sentence in B" in x for x in problems)


def test_renderer_check_catches_answer_in_sentence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bat, "EXPLORE_SENTENCE", "迷ったら read_book を選ぶこと。")
    assert "explore sentence contains 'read_book'" in bat.check_axis_renderers()


def test_non_leakage_catches_world_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bat, "EXPLORE_SENTENCE", "world A_rot の規則を探すこと。")
    assert any("a_rot" in x for x in bat.check_non_leakage())


def test_plan_check_catches_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    real = bat.pilot_plan
    monkeypatch.setattr(bat, "pilot_plan", lambda: real()[:-1])
    assert (
        "plan does not cover each (axis, world, r, t) exactly once" in bat.check_plan()
    )
    monkeypatch.setattr(bat, "pilot_plan", real)
    monkeypatch.setattr(bat, "axis_order", lambda _r: bat.AXES)
    assert "axis order is unbalanced" in bat.check_plan()


def test_budget_check_catches_overflow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bat, "EXPLORE_SENTENCE", "探索すること。" * 200)
    assert any("bytes >" in x for x in bat.check_prompt_budget())
