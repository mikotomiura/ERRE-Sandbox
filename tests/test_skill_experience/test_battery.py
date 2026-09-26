"""battery (prereg v3 §2): 合成経験の状態・族内一致・位置均衡・対照の構成・非漏洩・byte
予算."""

from __future__ import annotations

from typing import TYPE_CHECKING

from scripts import skill_experience_battery as bat
from scripts import skill_experience_scorer as sc
from scripts import skill_lever_battery as v2
from scripts.stage_b_battery import ACTIONS, SIGMA

if TYPE_CHECKING:
    import pytest


def test_battery_report_clean_at_r_max() -> None:
    report = bat.battery_report(bat.R_MAX)
    for key, value in report.items():
        if isinstance(value, list):
            assert value == [], key


def test_max_prompt_bytes_is_pinned() -> None:
    """ADR の転記値 (2,909) を信用せず、r < R_max・全 arm・全 probe で計算して pin
    する."""
    assert bat.max_prompt_bytes(bat.R_MAX) == 2909
    assert bat.check_prompt_budget(bat.R_MAX) == []


def test_state_has_36_rows_with_12_successes() -> None:
    lay = v2.layout(0)
    for arm in bat.STATE_ARMS:
        rows = bat.state_rows(arm, lay)
        assert len(rows) == 36
        assert sum(x.success for x in rows) == 12


def test_success_row_text_equals_v2_lever_line() -> None:
    """成功行の文面は v2 lever 行と同一 (v3 − v2 の差は失敗行と族の foil に限られる)."""
    for r in range(bat.R_MAX):
        lay = v2.layout(r)
        for arm in bat.JUDGE_ARMS:
            v3_lines = {
                bat.render_row(x) for x in bat.state_rows(arm, lay) if x.success
            }
            v2_lines = set(v2.render_state(arm, lay).splitlines()[1:])
            assert v3_lines == v2_lines


def test_success_follows_the_arm_rule() -> None:
    for r in (0, 5):
        lay = v2.layout(r)
        for arm in bat.STATE_ARMS:
            table = bat.rule(arm)
            for x in bat.state_rows(arm, lay):
                assert x.success == (x.tried == table[x.signature[0]])


def test_family_states_identical_outside_outcomes() -> None:
    """族内 2 状態は成否欄を消すと byte 一致し、成否欄だけが違う."""
    for r in range(bat.R_MAX):
        lay = v2.layout(r)
        for a, b in bat.JUDGE_FAMILIES:
            sa, sb = bat.render_state(a, lay), bat.render_state(b, lay)
            assert sa != sb
            assert bat.mask_outcomes(sa) == bat.mask_outcomes(sb)
    assert bat.check_family_identity(bat.R_MAX) == []


def test_family_b_trials_are_sigma_image() -> None:
    for w in ("rain", "clear", "wind"):
        a = bat.trial_actions(bat.ARM_A, w)
        b = bat.trial_actions(bat.ARM_B, w)
        assert b == tuple(SIGMA[x] for x in a)
        assert bat.trial_actions(bat.ARM_A_ROT, w) == a


def test_success_positions_balanced_within_each_r() -> None:
    """各 r の中で成功行の block 内位置が 4/4/4 (block 番号 = π_r 後の描画順 index)."""
    for r in range(bat.R_MAX):
        lay = v2.layout(r)
        for arm in bat.STATE_ARMS:
            pos = [x.position for x in bat.state_rows(arm, lay) if x.success]
            assert [pos.count(k) for k in range(3)] == [4, 4, 4]
    assert bat.check_outcome_balance(bat.R_MAX) == []


def test_block_rotation_uses_render_order_index() -> None:
    lay = v2.layout(3)
    rows = bat.state_rows(bat.ARM_A, lay)
    for j, sig in enumerate(lay.entry_order):
        block = [x for x in rows if x.block == j]
        canon = bat.trial_actions(bat.ARM_A, sig[0])
        shift = (3 + j) % 3
        assert [x.tried for x in block] == list(canon[shift:] + canon[:shift])


def test_trial_sequences_shared_within_family() -> None:
    assert bat.check_trial_sharing(bat.R_MAX) == []


def test_control_is_filler_swap_of_judge_state() -> None:
    """対照 = 判定 arm の状態の失敗行 label だけを filler にしたもの。byte 長は同一."""
    for r in range(bat.R_MAX):
        lay = v2.layout(r)
        for ctl, judge in zip(bat.CONTROL_ARMS, bat.JUDGE_ARMS, strict=True):
            rc, rj = bat.state_rows(ctl, lay), bat.state_rows(judge, lay)
            for xc, xj in zip(rc, rj, strict=True):
                assert (xc.signature, xc.tried, xc.success) == (
                    xj.signature,
                    xj.tried,
                    xj.success,
                )
                if xj.success:
                    assert xc.action == xj.action
                else:
                    assert xc.action in bat.FILLERS
            assert len(bat.render_state(ctl, lay).encode()) == len(
                bat.render_state(judge, lay).encode()
            )
    assert bat.check_control_construction(bat.R_MAX) == []
    assert bat.check_control_family(bat.R_MAX) == []


def test_fillers_are_out_of_vocabulary_and_parse_to_bottom() -> None:
    for f in bat.FILLERS:
        assert f not in ACTIONS
        assert len(f) == len(ACTIONS[0])
        assert sc.parse_choice(f) is None


def test_control_points_like_its_judge_arm() -> None:
    for ctl, judge in zip(bat.CONTROL_ARMS, bat.JUDGE_ARMS, strict=True):
        assert bat.POINTS_AS[ctl] == judge
        assert bat.rule(ctl) == v2.rule(judge)


def test_c0_has_no_state_and_shares_probe_part() -> None:
    lay = v2.layout(0)
    p = v2.lever_probes()[0]
    c0 = bat.render_messages(bat.ARM_C0, p, lay)[1]["content"]
    for arm in bat.STATE_ARMS:
        a = bat.render_messages(arm, p, lay)[1]["content"]
        assert a.endswith(c0)
    assert bat.STATE_HEADER not in c0
    assert c0 == v2.render_messages(bat.ARM_C0, p, lay)[1]["content"]


def test_arm_names_do_not_leak() -> None:
    assert bat.check_non_leakage(bat.R_MAX) == []


def test_family_identity_detects_shifted_trials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """族内で試行列をずらした状態は族内一致検査で捕まる."""
    original = bat.trial_actions

    def shifted(arm: str, w: str) -> tuple[str, ...]:
        t = original(arm, w)
        return t[1:] + t[:1] if arm == bat.ARM_A_ROT else t

    monkeypatch.setattr(bat, "trial_actions", shifted)
    assert bat.check_family_identity(1) != []
    assert bat.check_trial_sharing(1) != []


def test_outcome_balance_detects_unrotated_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """block 内巡回を外すと成功行の位置が偏り、均衡検査で捕まる."""
    monkeypatch.setattr(bat, "block_shift", lambda _r, _j: 0)
    got = bat.check_outcome_balance(1)
    assert any("success positions unbalanced" in g for g in got)


def test_prompt_budget_detects_overflow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(v2, "MAX_PROMPT_BYTES", 2000)
    assert any("max prompt" in g for g in bat.check_prompt_budget(1))


def test_control_check_detects_unswapped_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """対照が判定 arm と同じ label を持つ (filler に置き換わっていない)
    と構成検査で捕まる."""
    original = bat.state_rows

    def unswapped(arm: str, lay: v2.Layout) -> list[bat.Row]:
        return original(bat.POINTS_AS[arm], lay)

    monkeypatch.setattr(bat, "state_rows", unswapped)
    got = bat.check_control_construction(1)
    assert any("labels are not the filler swap" in g for g in got)
