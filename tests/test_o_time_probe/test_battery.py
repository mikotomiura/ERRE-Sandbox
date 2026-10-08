"""battery・曝露・日ごとの aggregator・並び・renderer と機械検査 (prereg §2)."""

from __future__ import annotations

from collections import Counter

import pytest
from scripts import o_time_probe_battery as bat

R = 6
U = bat.Unit(0, 2, 5)


def test_battery_checks_pass() -> None:
    assert bat.battery_violations(R) == []


def test_rules_pinned() -> None:
    assert [bat.first_rule_label(0, i) for i in range(6)] == [
        "ring_bell",
        "open_gate",
        "fill_jar",
        "ring_bell",
        "open_gate",
        "fill_jar",
    ]
    assert [bat.second_rule_label(0, i) for i in range(6)] == [
        "open_gate",
        "fill_jar",
        "ring_bell",
        "open_gate",
        "fill_jar",
        "ring_bell",
    ]
    assert bat.third_label(1, 0) == "hang_rope"
    assert bat.rule_on_day(bat.ARM_AB, 1)["crimson"] == "ring_bell"
    assert bat.rule_on_day(bat.ARM_AB, 2)["crimson"] == "open_gate"
    assert bat.rule_on_day(bat.ARM_BA, 1)["crimson"] == "open_gate"
    assert bat.rule_on_day(bat.ARM_DC, 2)["violet"] == "seal_crate"
    assert bat.check_rules() == []


def test_pointed_is_newer_day() -> None:
    """w = 新しい日 (2 日目) の規則の行動、foil = 古い日の規則の行動.

    族の 2 arm で入れ替わる。
    """
    for arm in bat.LEVER_ARMS:
        for i in range(bat.N_ROOMS):
            w, foil = bat.pointed(arm, i)
            room = bat.ROOMS[i]
            assert w == bat.rule_on_day(arm, 2)[room]
            assert foil == bat.rule_on_day(arm, 1)[room]
            assert bat.pointed(bat.FOIL[arm], i) == (foil, w)
    assert bat.pointed(bat.ARM_AB, 0) == ("open_gate", "ring_bell")


def test_directions() -> None:
    assert [bat.direction(a) for a in bat.LEVER_ARMS] == ["fwd", "bwd", "fwd", "bwd"]


def test_state_rows_follow_daily_rule() -> None:
    assert bat.check_state_tables() == []
    for arm in bat.LEVER_ARMS:
        table = bat.state_table(arm)
        assert sorted(table) == [1, 2]
        for day in (1, 2):
            assert len(table[day]) == 6
            for room, (act, n) in table[day].items():
                assert act == bat.rule_on_day(arm, day)[room]
                assert n == bat.TRIALS_PER_ACTION


def test_aggregator_is_daily() -> None:
    """日をまたいで数えると、どの行動も成功と失敗が混じって行が残らない.

    日ごとに数える理由。
    """
    obs = bat.observe(bat.ARM_AB)
    merged = [bat.Observation(1, o.room, o.action, o.success) for o in obs]
    assert bat.aggregate(merged) == {}
    assert len(bat.aggregate(obs)[2]) == 6


def test_aggregator_rejects_two_rows() -> None:
    obs = [
        bat.Observation(1, "crimson", "ring_bell", success=True),
        bat.Observation(1, "crimson", "open_gate", success=True),
    ]
    with pytest.raises(ValueError, match="two success rows"):
        bat.aggregate(obs)


def test_exposure_is_shared_within_family() -> None:
    sched = bat.exposure_schedule(0)
    assert len(sched) == 2 * 6 * 3 * bat.TRIALS_PER_ACTION
    obs_ab = bat.observe(bat.ARM_AB)
    obs_ba = bat.observe(bat.ARM_BA)
    assert [(o.day, o.room, o.action) for o in obs_ab] == [
        (o.day, o.room, o.action) for o in obs_ba
    ]
    assert [o.success for o in obs_ab] != [o.success for o in obs_ba]


def test_multiset_invariant() -> None:
    assert bat.check_multiset() == []
    for a, b in bat.FAMILIES:
        ms = [
            Counter(
                (room, act)
                for d in bat.DAYS
                for room, (act, _) in bat.state_table(arm)[d].items()
            )
            for arm in (a, b)
        ]
        assert ms[0] == ms[1]


def test_tags_pinned() -> None:
    assert bat.TAGS == {
        "asc": {1: "1 日目", 2: "2 日目"},
        "ago": {1: "2 日前", 2: "1 日前"},
    }
    assert bat.check_tags() == []
    assert bat.tag("ago", 2, masked=True) == "? 日前"


def test_render_row_text() -> None:
    state = bat.render_state(bat.ARM_AB, "asc", U).splitlines()
    assert state[0] == "これまでの経験の記録:"
    assert state[1] == "[2 日目] 条件: violet の部屋 → 行動: fill_jar (成功 3 / 失敗 0)"
    assert len(state) == 13
    ago = bat.render_state(bat.ARM_BA, "ago", U).splitlines()
    assert ago[1] == "[2 日前] 条件: violet の部屋 → 行動: fill_jar (成功 3 / 失敗 0)"


def test_render_probe_text() -> None:
    msgs = bat.render_messages(bat.ARM_AB, "asc", U)
    assert msgs[0] == {"role": "system", "content": bat.SYSTEM_PROMPT}
    assert msgs[1]["content"].split("\n\n")[1] == (
        "今の状況: amber の部屋。\n次の行動から 1 つだけ選び、行動名だけを答えよ: "
        "open_gate、fill_jar、ring_bell"
    )


def test_render_rejects_wrong_family() -> None:
    with pytest.raises(ValueError, match="not in family"):
        bat.render_messages(bat.ARM_CD, "asc", U)


def test_entry_order_pinned_and_shared() -> None:
    order = bat.entry_order(0, 2, 5)
    assert len(order) == 12
    assert sorted(order) == sorted(bat.row_slots(0))
    assert order[:2] == (("violet", "fill_jar"), ("cobalt", "ring_bell"))
    assert bat.entry_order(0, 2, 6) != order
    assert bat.entry_order(0, 3, 5) != order


def test_option_order() -> None:
    assert bat.option_order(0, 2, 5) == ("open_gate", "fill_jar", "ring_bell")
    assert bat.option_order(1, 0, 0) == bat.LABELS[1]
    for fi in range(2):
        for i in range(6):
            for r in range(R):
                assert sorted(bat.option_order(fi, i, r)) == sorted(bat.LABELS[fi])


def test_layer1_holds() -> None:
    assert bat.check_layer1(R) == []


def test_layer1_detects(monkeypatch: pytest.MonkeyPatch) -> None:
    original = bat.option_order

    def leaky(fi: int, i: int, r: int) -> tuple[str, ...]:
        return original(fi, i, r + (1 if leaky.toggle else 0))

    leaky.toggle = False  # type: ignore[attr-defined]
    original_render = bat.render_messages

    def render(
        arm: str, enc: str, unit: bat.Unit, mode: str = "main"
    ) -> list[dict[str, str]]:
        leaky.toggle = arm in bat.FWD  # type: ignore[attr-defined]
        return original_render(arm, enc, unit, mode)

    monkeypatch.setattr(bat, "option_order", leaky)
    monkeypatch.setattr(bat, "render_messages", render)
    assert bat.check_layer1(R) != []


def test_layer2_holds() -> None:
    assert bat.check_layer2(R) == []


def test_layer2_detects(monkeypatch: pytest.MonkeyPatch) -> None:
    """ago の数字の向きを asc と同じにすると、定理 2 の前提が崩れる."""
    monkeypatch.setitem(bat.TAGS, "ago", {1: "1 日前", 2: "2 日前"})
    assert bat.check_layer2(R) != []
    assert bat.check_tags() != []


def test_mask_helpers() -> None:
    text = "[1 日目] a\n[2 日前] b"
    assert bat.mask_digits(text) == "[<D> 日目] a\n[<D> 日前] b"
    assert bat.mask_suffix(text) == "[1 日<S>] a\n[2 日<S>] b"


def test_position_balance() -> None:
    assert bat.check_position_balance(R) == []
    assert bat.check_position_balance(4) == ["R = 4 is not a multiple of 3"]


def test_non_leakage() -> None:
    assert bat.check_non_leakage(3) == []


def test_non_leakage_detects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bat, "STATE_HEADER", "これまでの経験の記録 (AB):")
    assert any("'AB'" in v for v in bat.check_non_leakage(3))


def test_vocabulary() -> None:
    assert bat.check_vocabulary() == []


def test_vocabulary_detects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bat, "ROOMS", (*bat.ROOMS[:5], "clocks"))
    assert any("prior battery" in v for v in bat.check_vocabulary())
    monkeypatch.setattr(bat, "ROOMS", (*bat.ROOMS[:5], "room7"))
    assert any("digit" in v for v in bat.check_vocabulary())


def test_masked_states() -> None:
    assert bat.check_masked_states() == []
    a = bat.render_messages(bat.ARM_AB, "ago", U, "masked")
    b = bat.render_messages(bat.ARM_BA, "ago", U, "masked")
    assert a == b
    assert "[? 日前]" in a[1]["content"]
    assert "[1 日前]" not in a[1]["content"]


def test_m0_states() -> None:
    assert bat.check_m0_states() == []
    lines = bat.render_state(bat.ARM_BA, "ago", U, "m0").splitlines()[1:]
    assert len(lines) == 6
    assert all(line.startswith("[1 日前]") for line in lines)
    assert all(
        f"行動: {bat.rule_on_day(bat.ARM_BA, 2)[line.split()[3]]} " in line
        for line in lines
    )


def test_seed() -> None:
    assert bat.sample_seed("fam0", 5, 2, 0) == 20261008 + 50_000 + 200
    assert bat.sample_seed("m0_fam1", 100, 0, 0) == 20261008 + 60_000_000 + 1_000_000
    with pytest.raises(ValueError, match="out of range"):
        bat.sample_seed("fam0", 1000, 0, 0)
    assert bat.check_seed_namespaces(R) == []
    assert bat.check_seed_namespaces(bat.R_MAX + 3) != []


def test_prompt_budget() -> None:
    assert bat.check_prompt_budget(3) == []
    worst = max(
        bat.prompt_bytes(bat.render_messages(arm, enc, u, mode))
        for u in bat.units(3)
        for arm, enc in bat.unit_calls(u)
        for mode in bat.MODES
    )
    assert worst < 1500


def test_units_order() -> None:
    us = bat.units(2)
    assert len(us) == 24
    assert us[0] == bat.Unit(0, 0, 0)
    assert us[6] == bat.Unit(1, 0, 0)
    assert us[12] == bat.Unit(0, 0, 1)
    assert len(bat.pilot_units()) == 72
    assert bat.unit_calls(U) == (
        ("AB", "asc"),
        ("AB", "ago"),
        ("BA", "asc"),
        ("BA", "ago"),
    )


def test_frozen_conditions() -> None:
    assert bat.MODEL == "qwen3:8b"
    assert bat.THINK is False
    assert (bat.TEMPERATURE, bat.TOP_P, bat.REPEAT_PENALTY) == (0.7, 0.8, 1.0)
    assert (bat.NUM_CTX, bat.NUM_PREDICT) == (4096, 32)
    assert (bat.R_MAX, bat.PILOT_R0, bat.PILOT_R) == (288, 300, 6)


# ------------------------------------------------------- 検査器が実際に落とすこと


def test_row_day_requires_one_day(monkeypatch: pytest.MonkeyPatch) -> None:
    table = {1: {"crimson": ("ring_bell", 3)}, 2: {"crimson": ("ring_bell", 3)}}
    monkeypatch.setattr(bat, "state_table", lambda _arm: table)
    with pytest.raises(ValueError, match="exactly one day"):
        bat.row_day(bat.ARM_AB, "crimson", "ring_bell")


def test_rules_detect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bat, "second_rule_label", bat.first_rule_label)
    assert "family 0: the two rules agree on a room" in bat.check_rules()


def test_state_table_check_detects(monkeypatch: pytest.MonkeyPatch) -> None:
    real = {arm: bat.state_table(arm) for arm in bat.LEVER_ARMS}

    def swapped(arm: str) -> dict[int, dict[str, tuple[str, int]]]:
        if arm != bat.ARM_AB:
            return real[arm]
        return {1: real[arm][2], 2: real[arm][1]}

    monkeypatch.setattr(bat, "state_table", swapped)
    out = bat.check_state_tables()
    assert "AB: day 1 row crimson disagrees with the world rule" in out


def test_multiset_detects(monkeypatch: pytest.MonkeyPatch) -> None:
    real = {arm: bat.state_table(arm) for arm in bat.LEVER_ARMS}

    def other(arm: str) -> dict[int, dict[str, tuple[str, int]]]:
        if arm != bat.ARM_BA:
            return real[arm]
        return {1: real[bat.ARM_CD][1], 2: real[bat.ARM_CD][2]}

    monkeypatch.setattr(bat, "state_table", other)
    assert "(room, label) multiset differs within family AB/BA" in bat.check_multiset()


def test_tags_detect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(bat.TAGS, "ago", {1: "2 日前", 2: "1 日後"})
    assert bat.check_tags() == ["ago: the two day tags differ beyond the digit"]


def test_position_balance_detects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bat, "option_order", lambda fi, _i, _r: bat.LABELS[fi])
    out = bat.check_position_balance(R)
    assert "family 0 room 0: option positions are not balanced" in out


def test_prompt_budget_detects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bat, "MAX_PROMPT_BYTES", 100)
    assert any("exceeds 100" in v for v in bat.check_prompt_budget(3))


def test_masked_states_detect(monkeypatch: pytest.MonkeyPatch) -> None:
    original = bat.render_state

    def leaky(arm: str, enc: str, unit: bat.Unit, mode: str = "main") -> str:
        text = original(arm, enc, unit, mode)
        return text + ("\n." if mode == "masked" and arm in bat.FWD else "")

    monkeypatch.setattr(bat, "render_state", leaky)
    out = bat.check_masked_states()
    assert any(v.endswith("masked prompts differ between the arms") for v in out)


def test_m0_states_detect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bat, "m0_order", lambda _fi, _i, _r: bat.ROOMS[:5])
    out = bat.check_m0_states()
    assert any(v.endswith("M0 rows are not the newer-day rows") for v in out)
    assert any(v.endswith("M0 state does not have one row per room") for v in out)


def test_seed_namespaces_detect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(bat.SEED_NS, "m0_fam0", 3)
    assert bat.check_seed_namespaces(R) == ["seed namespaces overlap"]


def test_layer_checks_compare_the_whole_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """定理の前提の検査は、system・role・追加の message も比べる.

    Codex HIGH-1 の反例: ago の system にだけ「数の小さい札を選ぶ。」を足すと、
    後ろの語を読まずに C = 1 にできる。user の文面だけを比べる検査はこれを通してしまう。
    """
    original = bat.render_messages

    def ago_system(
        arm: str, enc: str, unit: bat.Unit, mode: str = "main"
    ) -> list[dict[str, str]]:
        msgs = original(arm, enc, unit, mode)
        if enc == "ago":
            msgs[0] = {
                **msgs[0],
                "content": msgs[0]["content"] + "数の小さい札を選ぶ。",
            }
        return msgs

    monkeypatch.setattr(bat, "render_messages", ago_system)
    assert bat.check_layer1(3) == []  # 同じ書き方の 2 arm では system が同じ
    assert bat.check_layer2(3) != []

    def extra_message(
        arm: str, enc: str, unit: bat.Unit, mode: str = "main"
    ) -> list[dict[str, str]]:
        msgs = original(arm, enc, unit, mode)
        if arm in bat.FWD:
            msgs.append({"role": "assistant", "content": "了解"})
        return msgs

    monkeypatch.setattr(bat, "render_messages", extra_message)
    assert bat.check_layer1(3) != []
    assert any(
        v.endswith("masked prompts differ between the arms")
        for v in bat.check_masked_states()
    )

    def role_change(
        arm: str, enc: str, unit: bat.Unit, mode: str = "main"
    ) -> list[dict[str, str]]:
        msgs = original(arm, enc, unit, mode)
        if arm in bat.FWD:
            msgs[0] = {**msgs[0], "role": "user"}
        return msgs

    monkeypatch.setattr(bat, "render_messages", role_change)
    assert bat.check_layer1(3) != []


def test_normalized_messages() -> None:
    msgs = [
        {"role": "system", "content": "a1"},
        {"role": "user", "content": "[1 日目] x"},
    ]
    assert bat.normalized_messages(msgs, str) != bat.normalized_messages(msgs[:1], str)
    assert "<D> 日目" in bat.normalized_messages(msgs, bat.mask_digits)
