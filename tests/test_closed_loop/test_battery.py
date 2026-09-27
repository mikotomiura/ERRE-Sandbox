"""battery (prereg v4 §2).

行の文言・空状態・R1 ⊂ R1+・seed・Ω_dev・plan・非漏洩・byte 予算。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scripts import closed_loop_battery as bat
from scripts import skill_lever_battery as v2
from scripts.stage_b_battery import ACTIONS, dev_signatures

if TYPE_CHECKING:
    import pytest


def test_battery_report_clean() -> None:
    for r_count in (4, 8, 12):
        report = bat.battery_report(r_count)
        for key, value in report.items():
            if isinstance(value, list):
                assert value == [], (r_count, key)


def test_max_prompt_bytes_is_pinned() -> None:
    """全 renderer・極端な状態 (全成功・全語彙を試行) の最大 byte を pin する."""
    assert bat.max_prompt_bytes(bat.R_MAX) == 2504
    assert bat.check_prompt_budget(bat.R_MAX) == []


def test_prompt_budget_detects_overflow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bat.v2, "MAX_PROMPT_BYTES", 2000)
    assert bat.check_prompt_budget(4) != []


def test_row_wording_is_pinned() -> None:
    sig = dev_signatures()[0]
    assert bat.success_line(sig, "read_book") == (
        "条件: rain / dawn / alone → 行動: read_book (成功あり)"
    )
    assert bat.tried_line(sig, ["read_book", "sit_quiet"]) == (
        "条件: rain / dawn / alone → 試した: read_book、sit_quiet"
    )


def test_empty_state_strings() -> None:
    for w in bat.WORLDS:
        assert bat.render_state(bat.EMPTY_STATE, w, 0, bat.RENDERER_R1) == (
            "これまでの経験の記録:\n(成功した記録はない)"
        )
        assert bat.render_state(bat.EMPTY_STATE, w, 3, bat.RENDERER_R1PLUS) == (
            "これまでの経験の記録:\n成功した行動:\n(なし)\n"
            "試した行動 (成否を問わない):\n(なし)"
        )


def test_rows_follow_pi_r_and_only_presence_changes() -> None:
    devs = dev_signatures()
    for r in (0, 5):
        order = v2.layout(r).entry_order
        some = frozenset(devs[i] for i in (0, 3, 7, 10))
        st = bat.State(succeeded=some)
        lines = bat.render_state(st, bat.WORLDS[1], r, bat.RENDERER_R1).splitlines()[1:]
        want = [
            bat.success_line(s, bat.rule(bat.WORLDS[1])[s[0]])
            for s in order
            if s in some
        ]
        assert lines == want


def test_tried_labels_in_action_order_not_trial_order() -> None:
    sig = dev_signatures()[2]
    st = bat.State(tried=frozenset({(sig, "walk_path"), (sig, "read_book")}))
    lines = bat.tried_lines(st, 0)
    assert lines == [bat.tried_line(sig, ["read_book", "walk_path"])]


def test_r1_lines_embedded_in_r1plus() -> None:
    assert bat.check_state_neutrality(bat.R_MAX) == []


def test_update_success_bottom_and_oov() -> None:
    sig = next(s for s in dev_signatures() if s[0] == "rain")
    world = bat.WORLDS[0]  # A: rain → read_book
    st = bat.update(bat.EMPTY_STATE, world, sig, "read_book")
    assert st.succeeded == frozenset({sig})
    assert st.tried == frozenset({(sig, "read_book")})
    st2 = bat.update(bat.EMPTY_STATE, world, sig, None)
    assert st2 == bat.EMPTY_STATE  # ⊥ は試行でも成功でもない
    st3 = bat.update(bat.EMPTY_STATE, world, sig, "tend_moss")  # Ω_dev(rain) の外
    assert st3.succeeded == frozenset()
    assert st3.tried == frozenset({(sig, "tend_moss")})
    st4 = bat.update(bat.EMPTY_STATE, bat.WORLDS[1], sig, "read_book")  # A_rot では失敗
    assert st4.succeeded == frozenset()


def test_loop_seed_shared_and_disjoint_from_probe_seeds() -> None:
    assert bat.check_seed_disjoint() == []
    assert bat.loop_seed(3, 17) == 21_260_926 + 3000 + 17
    loop = {bat.loop_seed(r, t) for r in range(bat.R_MAX) for t in range(bat.T_MAX)}
    probe = {
        v2.sample_seed(r, q, k)
        for r in range(bat.R_MAX)
        for q in range(6)
        for k in range(bat.K_MAX)
    }
    assert not loop & probe


def test_seed_check_detects_collision(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bat, "LOOP_SEED_BASE", v2.SEED_BASE)
    assert bat.check_seed_disjoint() != []


def test_dev_options_are_world_rules_rotated() -> None:
    assert bat.check_dev_options() == []
    for r in (0, 1, 6):
        for t in range(bat.T_MAX):
            sig = bat.loop_signature(r, t)
            om = bat.dev_omega(sig[0])
            shift = (r + t) % 4
            assert bat.dev_options(r, t) == om[shift:] + om[:shift]
            assert sig == v2.layout(r).entry_order[t % 12]


def test_dev_rotation_check_detects_fixed_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        bat, "dev_options", lambda r, t: bat.dev_omega(bat.loop_signature(r, t)[0])
    )
    assert bat.check_dev_options(4) != []


def test_c0_is_v2_c0_and_situation_matches_v2_probe() -> None:
    assert bat.check_c0_is_v2() == []


def test_plan_layout_and_counts() -> None:
    for r_count, k, m in ((4, 5, 3), (8, 5, 4), (12, 10, 3)):
        p = bat.plan(r_count, k, m)
        n_main = bat.n_main_calls(r_count, k, m)
        assert n_main == r_count * (30 * k + 48 * m)
        assert len(p) == n_main + 9 * r_count
        c0 = [x for x in p if x.phase == bat.PHASE_C0]
        assert p[: len(c0)] == c0  # C0 が先
        assert len(c0) == 6 * k * r_count
        # r ごとに loop → probe、block 内は world_order(r)
        body = p[len(c0) : n_main]
        per_r = 4 * (12 * m + 6 * k)
        for r in range(r_count):
            chunk = body[r * per_r : (r + 1) * per_r]
            assert all(x.replicate == r for x in chunk)
            loop = chunk[: 4 * 12 * m]
            assert all(x.phase == bat.PHASE_LOOP for x in loop)
            for t in range(12 * m):
                blk = loop[4 * t : 4 * t + 4]
                assert tuple(x.world for x in blk) == bat.world_order(r)
                assert {x.step for x in blk} == {t}
            probe = chunk[4 * 12 * m :]
            assert all(x.phase == bat.PHASE_PROBE for x in probe)
            for b in range(6 * k):
                assert tuple(
                    x.world for x in probe[4 * b : 4 * b + 4]
                ) == bat.world_order(r)
        assert all(x.phase == bat.PHASE_REPLAY for x in p[n_main:])


def test_world_order_rotates_per_replicate() -> None:
    assert bat.world_order(0) == ("A", "A_rot", "B", "B_rot")
    assert bat.world_order(1) == ("A_rot", "B", "B_rot", "A")
    assert bat.check_world_order(8) == []
    assert bat.check_world_order(6) != []


def test_world_order_check_detects_unrotated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bat, "world_order", lambda _r: bat.WORLDS)
    assert bat.check_world_order(8) == ["world order is unbalanced"]


def test_replay_targets() -> None:
    t = bat.replay_targets(2, 4)
    assert len(t) == 9
    assert t[0] == bat.PlanKey(bat.PHASE_LOOP, bat.world_order(2)[0], 2, step=0)
    assert [x.step for x in t[1:5]] == [47] * 4
    assert all(x.probe_id == "q00" and x.k == 0 for x in t[5:])


def test_non_leakage_clean_and_detects_arm_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert bat.check_non_leakage(4) == []
    monkeypatch.setattr(bat, "EMPTY_R1", "(A_rot の記録はない)")
    assert bat.check_non_leakage(1) != []


def test_extreme_states_cover_all_vocab() -> None:
    st = bat._extreme_states("B")[2]
    assert len(st.tried) == 12 * len(ACTIONS)
