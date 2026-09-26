"""battery (prereg v2 §2): foil 設計・counterbalance・非漏洩・切り詰め不能の機械検査."""

from __future__ import annotations

from typing import TYPE_CHECKING

from scripts import skill_lever_battery as bat
from scripts import skill_lever_scorer as sc
from scripts.stage_b_battery import SIGMA

if TYPE_CHECKING:
    import pytest


def test_battery_report_clean_at_frozen_r() -> None:
    report = bat.battery_report(sc.FROZEN_R)
    for key, value in report.items():
        if isinstance(value, list) and key != "actions":
            assert value == [], key


def test_four_arms_point_to_distinct_options() -> None:
    for p in bat.lever_probes():
        assert sorted(p.omega) == sorted(set(p.omega))
        assert p.pointed[bat.ARM_B] == SIGMA[p.pointed[bat.ARM_A]]
        assert p.pointed[bat.ARM_B_ROT] == SIGMA[p.pointed[bat.ARM_A_ROT]]
        assert p.pointed[bat.ARM_A] != p.pointed[bat.ARM_A_ROT]


def test_foil_is_the_family_partner() -> None:
    for a, b in bat.FAMILIES:
        assert bat.FOIL[a] == b
        assert bat.FOIL[b] == a


def test_family_states_share_label_multiset() -> None:
    """priming の相殺条件: 族内 2 arm の状態は同じ label を同じ回数だけ持つ."""
    for r in range(sc.FROZEN_R):
        lay = bat.layout(r)
        for a, b in bat.FAMILIES:
            la = sorted(x for _, x in bat.state_entries(a, lay))
            lb = sorted(x for _, x in bat.state_entries(b, lay))
            assert la == lb
            assert [s for s, _ in bat.state_entries(a, lay)] == [
                s for s, _ in bat.state_entries(b, lay)
            ]


def test_rotation_rule_differs_only_in_mapping() -> None:
    a, rot = bat.rule(bat.ARM_A), bat.rule(bat.ARM_A_ROT)
    assert sorted(a.values()) == sorted(rot.values())
    assert all(a[w] != rot[w] for w in a)


def test_position_balance_requires_multiple_of_four() -> None:
    assert bat.check_position_balance(sc.FROZEN_R) == []
    assert bat.check_position_balance(6) != []


def test_c0_has_no_state_and_shares_probe_part() -> None:
    lay = bat.layout(0)
    p = bat.lever_probes()[0]
    c0 = bat.render_messages(bat.ARM_C0, p, lay)[1]["content"]
    a = bat.render_messages(bat.ARM_A, p, lay)[1]["content"]
    assert bat.STATE_HEADER not in c0
    assert a.endswith(c0)


def test_prompt_budget_is_static() -> None:
    assert (
        bat.MAX_PROMPT_BYTES + bat.CHAT_TEMPLATE_OVERHEAD + bat.NUM_PREDICT
        <= bat.NUM_CTX
    )
    assert bat.check_prompt_budget(12) == []


def test_arm_names_do_not_leak() -> None:
    assert bat.check_non_leakage(12) == []


def test_seeds_shared_across_arms_distinct_within_arm() -> None:
    seeds = {
        bat.sample_seed(r, qi, k)
        for r in range(12)
        for qi in range(len(bat.lever_probes()))
        for k in range(20)
    }
    assert len(seeds) == 12 * len(bat.lever_probes()) * 20


def test_label_balance_detects_signature_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """族内でエントリの signature 順が食い違う state は battery 検査で捕まる."""
    original = bat.state_entries

    def skewed(arm: str, lay: bat.Layout) -> list[tuple[tuple[str, str, str], str]]:
        entries = original(arm, lay)
        return entries[::-1] if arm == bat.ARM_A_ROT else entries

    monkeypatch.setattr(bat, "state_entries", skewed)
    assert "A/A_rot: state signature orders differ" in bat.check_label_balance(1)
