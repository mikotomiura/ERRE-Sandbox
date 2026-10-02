"""battery・曝露・aggregator・layout・renderer と機械検査 (prereg §2)."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

import pytest
from scripts import generalization_probe_battery as bat

if TYPE_CHECKING:
    from collections.abc import Iterator

R = 6


def _clear_caches() -> None:
    for fn in (
        bat.probes,
        bat.dev_situations,
        bat.state_table,
        bat.entry_order,
        bat.selection_entry_order,
    ):
        fn.cache_clear()


@pytest.fixture
def fresh() -> Iterator[None]:
    _clear_caches()
    yield
    _clear_caches()


def test_battery_checks_pass() -> None:
    assert bat.battery_violations(R) == []


def test_rotation_and_sigma() -> None:
    a = bat.rule(bat.ARM_A)
    assert a == {"bird": "sort_cards", "fish": "fold_linen", "insect": "stack_cups"}
    assert bat.rule(bat.ARM_A_ROT) == {
        "bird": "fold_linen",
        "fish": "stack_cups",
        "insect": "sort_cards",
    }
    assert bat.rule(bat.ARM_B) == {
        "bird": "wind_clock",
        "fish": "count_keys",
        "insect": "tidy_shelf",
    }
    assert bat.rule(bat.ARM_B_ROT) == {
        "bird": "count_keys",
        "fish": "tidy_shelf",
        "insect": "wind_clock",
    }


def test_pointed() -> None:
    assert bat.check_pointed() == []
    for p in bat.probes():
        assert len(set(p.pointed.values())) == 4
        assert p.pointed[bat.ARM_A] in bat.ACTIONS_A
        assert p.pointed[bat.ARM_B_ROT] in bat.ACTIONS_B


def test_state_rows_follow_world_rule() -> None:
    assert bat.check_state_tables() == []
    for arm in bat.LEVER_ARMS:
        table = bat.state_table(arm)
        assert len(table) == 12
        for sit, (act, n) in table.items():
            assert act == bat.rule(arm)[sit.latent]
            assert n == bat.TRIALS_PER_ACTION


def test_exposure_is_shared_within_family_and_rule_free() -> None:
    sched_a = bat.exposure_schedule(0)
    assert len(sched_a) == 12 * 3 * bat.TRIALS_PER_ACTION
    obs_a = bat.observe(bat.ARM_A)
    obs_rot = bat.observe(bat.ARM_A_ROT)
    pairs_a = [(o.situation, o.action) for o in obs_a]
    assert pairs_a == [(o.situation, o.action) for o in obs_rot]
    assert [o.success for o in obs_a] != [o.success for o in obs_rot]


def test_render_row_text() -> None:
    order = bat.entry_order(0, 0, 0)
    state = bat.render_state(bat.ARM_A, order)
    lines = state.splitlines()
    assert lines[0] == "これまでの経験の記録:"
    sit = order[0]
    act = bat.rule(bat.ARM_A)[sit.latent]
    assert (
        lines[1] == f"条件: {sit.key} / {sit.place} / {sit.company} → 行動: {act} "
        "(成功 3 / 失敗 0)"
    )


def test_render_probe_text() -> None:
    p = bat.probes()[0]
    msgs = bat.render_messages(bat.ARM_A, p, 0)
    assert msgs[0] == {"role": "system", "content": bat.SYSTEM_PROMPT}
    probe_part = msgs[1]["content"].split("\n\n")[1]
    assert probe_part == (
        f"状況: 生き物={p.situation.key}、場所={p.situation.place}、"
        f"同伴={p.situation.company}。\n"
        "次の行動から 1 つだけ選び、行動名だけを答えよ: "
        + "、".join(bat.option_order(0, 0, 0))
    )


def test_options_are_family_labels_independent_of_class() -> None:
    """Ω は族の 3 label で、表示順はつ組と r だけで決まる (Codex HIGH-1)."""
    for fi in range(2):
        for j in range(bat.N_TRIPLES):
            for r in range(R):
                order = bat.option_order(fi, j, r)
                assert sorted(order) == sorted(bat.family_actions(fi))
    assert bat.option_order(0, 0, 1) == ("fold_linen", "stack_cups", "sort_cards")
    assert bat.option_order(0, 1, 0) == ("fold_linen", "stack_cups", "sort_cards")
    assert bat.option_order(1, 2, 0) == ("tidy_shelf", "wind_clock", "count_keys")


def test_triple_prompts_differ_only_in_key() -> None:
    assert bat.check_triple_prompts_differ_only_in_key(R) == []


def test_triple_prompts_check_detects(monkeypatch: pytest.MonkeyPatch) -> None:
    original = bat.render_messages

    def leaky(
        arm: str, probe: bat.Probe, r: int, *, masked: bool = False
    ) -> list[dict[str, str]]:
        msgs = original(arm, probe, r, masked=masked)
        rotated = bat.option_order(bat.ARM_FAMILY[arm], probe.triple, r + probe.index)
        head = msgs[1]["content"].rsplit(": ", 1)[0]
        msgs[1]["content"] = head + ": " + "、".join(rotated)
        return msgs

    monkeypatch.setattr(bat, "render_messages", leaky)
    assert bat.check_triple_prompts_differ_only_in_key(R) != []


def test_label_frequency_invariant() -> None:
    assert bat.check_label_frequency() == []
    for a, b in bat.FAMILIES:
        la = Counter(act for act, _ in bat.state_table(a).values())
        lb = Counter(act for act, _ in bat.state_table(b).values())
        assert la == lb


def test_frequency_vector_counterexample() -> None:
    """統合系 ADR §5.1 の反例.

    (x, x, y) を x↔y で置換すると (y, y, x)。頻度ベクトルは不変でない。
    """
    assert not bat.frequency_vector_invariant(["x", "x", "y"], ["y", "y", "x"])
    assert bat.frequency_vector_invariant(["x", "y", "z"], ["y", "z", "x"])


def test_dev_design_one_per_combo_and_class() -> None:
    assert bat.check_dev_design() == []
    cells = Counter(((s.place, s.company), s.latent) for s in bat.dev_situations())
    assert len(cells) == 12
    assert set(cells.values()) == {1}


def test_triples_share_distractors() -> None:
    assert bat.check_triples() == []
    for j in range(bat.N_TRIPLES):
        tp = bat.triple_probes(j)
        assert {(p.situation.place, p.situation.company) for p in tp} == {
            bat.COMBOS[j % 4]
        }
        assert [p.situation.latent for p in tp] == list(bat.CLASSES)


def test_probe_keys_absent() -> None:
    assert bat.check_probe_keys_absent(R) == []
    dev = {s.key for s in bat.dev_situations()}
    assert not dev & {p.situation.key for p in bat.probes()}


def test_probe_keys_absent_detects(
    fresh: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    del fresh
    keys = list(bat.PROBE_KEYS["bird"])
    keys[0] = "sparrow"  # dev key
    monkeypatch.setitem(bat.PROBE_KEYS, "bird", tuple(keys))
    _clear_caches()
    assert bat.check_probe_keys_absent(R) != []


def test_surface_overlap() -> None:
    assert bat.check_surface_overlap() == []


def test_surface_overlap_detects(fresh: None, monkeypatch: pytest.MonkeyPatch) -> None:
    del fresh
    keys = list(bat.PROBE_KEYS["bird"])
    keys[0] = "parrot"  # sparrow と 4-gram 'parr' を共有
    monkeypatch.setitem(bat.PROBE_KEYS, "bird", tuple(keys))
    _clear_caches()
    out = bat.check_surface_overlap()
    assert any("parrot" in v for v in out)


def test_non_leakage() -> None:
    assert bat.check_non_leakage(R) == []


def test_non_leakage_detects_class_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bat, "STATE_HEADER", "これまでの bird の記録:")
    assert bat.check_non_leakage(R) != []


def test_position_balance() -> None:
    assert bat.check_position_balance(R) == []
    assert bat.check_position_balance(4) != []
    firsts = Counter(bat.option_order(1, 5, r)[0] for r in range(3))
    assert set(firsts.values()) == {1}


def test_shared_within_family() -> None:
    assert bat.check_shared_within_family(R) == []
    p = bat.probes()[0]
    a = bat.render_messages(bat.ARM_A, p, 1)[1]["content"]
    b = bat.render_messages(bat.ARM_A_ROT, p, 1)[1]["content"]
    assert a != b
    assert a.splitlines()[1].split(" → ")[0] == b.splitlines()[1].split(" → ")[0]


def test_entry_order_differs_across_units() -> None:
    assert bat.entry_order(0, 0, 0) != bat.entry_order(0, 0, 1)
    assert bat.entry_order(0, 0, 0) != bat.entry_order(0, 1, 0)


def test_selection_layout_separate() -> None:
    assert bat.check_selection_layout_separate(R) == []
    assert bat.selection_entry_order(0, 0, 0) != bat.entry_order(0, 0, 0)


def test_masked_states() -> None:
    assert bat.check_masked_states() == []
    p = bat.probes()[0]
    text = bat.render_messages(bat.ARM_A, p, bat.PILOT_R0, masked=True)[1]["content"]
    assert "条件: 不明 /" in text
    for s in bat.dev_situations():
        assert s.key not in text.split("\n\n")[0]


def test_seed_namespaces() -> None:
    assert bat.check_seed_namespaces(R) == []
    assert bat.sample_seed("fam0", 1, 2, 0) == 20261001 + 10_000 + 200
    assert bat.sample_seed("pilot_fam0", 1, 2, 0) != bat.sample_seed("fam0", 1, 2, 0)


def test_prompt_budget() -> None:
    assert bat.check_prompt_budget(bat.R_MAX) == []
    worst = max(
        bat.prompt_bytes(bat.render_messages(a, p, r))
        for a in bat.LEVER_ARMS
        for p in bat.probes()
        for r in range(3)
    )
    assert worst < bat.MAX_PROMPT_BYTES


def test_know_options_balance_the_answer_position() -> None:
    """知識確認の正答の位置は 3 試行で一巡する.

    先頭・末尾を答える方策は、各 key で 1/3 しか当たらない (Codex HIGH-2)。
    """
    assert bat.check_know_balance() == []
    for i, key in enumerate(bat.all_keys()):
        truth = bat.key_class(key)
        opts = [bat.know_options(i, k) for k in range(bat.KNOW_K)]
        assert all(sorted(o) == sorted(bat.CLASSES) for o in opts)
        assert sum(o[0] == truth for o in opts) == 1
        assert sum(o[-1] == truth for o in opts) == 1
    msgs = bat.render_know_messages(0, 1)
    assert msgs[1]["content"].startswith(f"生き物: {bat.all_keys()[0]}\n")
    assert len(set(bat.all_keys())) == 36


def test_frozen_vocabulary() -> None:
    assert bat.PROBE_KEYS == {
        "bird": (
            "falcon",
            "ostrich",
            "hawk",
            "stork",
            "canary",
            "penguin",
            "eagle",
            "robin",
        ),
        "fish": (
            "halibut",
            "salmon",
            "guppy",
            "marlin",
            "tuna",
            "barracuda",
            "anchovy",
            "minnow",
        ),
        "insect": (
            "mantis",
            "cicada",
            "flea",
            "weevil",
            "midge",
            "earwig",
            "wasp",
            "aphid",
        ),
    }
    assert bat.ACTIONS == (
        "sort_cards",
        "fold_linen",
        "stack_cups",
        "wind_clock",
        "count_keys",
        "tidy_shelf",
    )
    assert (bat.TEMPERATURE, bat.TOP_P, bat.NUM_PREDICT) == (0.7, 0.8, 32)
    assert (bat.N_POSITIONS, bat.PILOT_R, bat.KNOW_K) == (3, 6, 3)
