"""登録した写し方 (fixture) の C と τ/4 gate (prereg §6)."""

from __future__ import annotations

import hashlib
from functools import lru_cache

import numpy as np
import pytest
from scripts import generalization_probe_battery as bat
from scripts import generalization_probe_fixtures as fx

R = 6


@lru_cache(maxsize=1)
def _table() -> dict[str, object]:
    return fx.fixture_table(R)


def test_fixture_gate_passes() -> None:
    table = _table()
    assert table["passed"] is True
    assert table["max_abs_C"] < fx.FIXTURE_GATE
    assert pytest.approx(0.075) == fx.FIXTURE_GATE
    assert fx.fixture_violations(R) == []


def test_fixture_table_pinned() -> None:
    """凍結した設計の上の値 (R = 6)。方策・平均・同点処理を壊すと動く."""
    table = _table()
    assert len(fx.registered_policies()) == 120
    pol = table["policies"]
    assert table["max_abs_C"] == pytest.approx(0.046875)
    assert table["max_abs_C_key_blind"] == 0.0
    assert pol["surface_lcs_substring[first,first]"]["C"] == pytest.approx(-0.046875)
    assert pol["surface_first_letter[last,first]"]["C"] == pytest.approx(0.041666666667)
    assert pol["surface_levenshtein[first,first]"]["C"] == pytest.approx(0.03125)
    assert pol["surface_lcs_subsequence[last,first]"]["C"] == pytest.approx(
        0.010416666667
    )
    assert pol["surface_alphabetical[last,bot]"]["C"] == pytest.approx(-0.010416666667)
    assert pol["surface_bigram_jaccard_top3_vote[last,first]"]["C"] == pytest.approx(
        0.005208333333
    )
    for name in (
        "label_position",
        "omega_missing_label_lookup",
        "order_lookup",
        "first_row[first]",
    ):
        assert pol[name]["C"] == 0.0


def test_key_blind_policies_are_exactly_zero_per_unit() -> None:
    """key に依らない任意の方策は、どの単位でも d = 0.

    つ組の prompt は key だけが違う (prereg §6 の定理)。
    """

    def hashed(salt: str):
        def policy(ctx: fx.Context) -> str | None:
            blob = repr((salt, ctx.rows, ctx.place, ctx.company, ctx.options)).encode()
            h = int(hashlib.sha256(blob).hexdigest(), 16)
            if h % 7 == 0:
                return None
            return (
                ctx.options[h % len(ctx.options)]
                if h % 2
                else ctx.rows[h % len(ctx.rows)].label
            )

        return policy

    for salt in ("a", "b", "c"):
        assert np.all(fx.policy_units(hashed(salt), R) == 0.0)
    for name, (fam, pol) in fx.registered_policies().items():
        if fam == "key_blind":
            assert np.all(fx.policy_units(pol, 3) == 0.0), name


def test_positive_controls() -> None:
    controls = _table()["positive_controls"]
    assert controls["oracle_latent"] == pytest.approx(1.0)
    assert controls["oracle_next_class"] == pytest.approx(-0.5)


def test_fixture_violations_detects(monkeypatch: pytest.MonkeyPatch) -> None:
    """|C| が τ/4 を超える方策を検出する.

    |C| = 1/2 (1 未満) の方策でも落ちる (閾値を 1 に上げる変異を捕まえる)。
    """
    reg = {
        "oracle": ("key_surface", fx.oracle_latent),
        "next_class": ("key_surface", fx.oracle_next_class),
        "blind": ("key_blind", fx.empty_state_first),
    }
    monkeypatch.setattr(fx, "registered_policies", lambda: reg)
    out = fx.fixture_violations(R)
    assert [v.split(":")[0] for v in out] == ["oracle", "next_class"]
    table = fx.fixture_table(R)
    assert table["passed"] is False
    assert table["max_abs_C"] == pytest.approx(1.0)
    only_half = {"next_class": reg["next_class"], "blind": reg["blind"]}
    monkeypatch.setattr(fx, "registered_policies", lambda: only_half)
    assert fx.fixture_table(R)["passed"] is False


def test_fixture_violations_detects_a_nonzero_key_blind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """key を見ない族の方策が 0 でなければ落とす.

    定理の破れ (実装の誤り) として扱う。
    """
    reg = {"leaky": ("key_blind", fx.oracle_latent)}
    monkeypatch.setattr(fx, "registered_policies", lambda: reg)
    out = fx.fixture_violations(R)
    assert any("key-blind policy has C" in v for v in out)


def test_levenshtein_and_similarity() -> None:
    assert fx.levenshtein("kitten", "sitting") == 3
    assert fx.levenshtein("abc", "abc") == 0
    assert fx.lcs_substring("heron", "herring") == 3
    assert fx.lcs_substring("abc", "axbyc") == 1
    assert fx.lcs_subsequence("abc", "axbyc") == 3
    assert fx.jaccard("night", "nacht", 2) == pytest.approx(1 / 7)
    assert fx.jaccard("abc", "abc", 3) == 1.0


def _ctx(
    options: tuple[str, ...] = ("fold_linen", "sort_cards", "stack_cups"),
) -> fx.Context:
    rows = (
        fx.Row("heron", "library", "solo", "sort_cards"),
        fx.Row("trout", "library", "pair", "fold_linen"),
        fx.Row("beetle", "workshop", "solo", "stack_cups"),
    )
    return fx.Context(rows, "eagle", "workshop", "solo", options)


def test_policies_on_handmade_context() -> None:
    ctx = _ctx()
    assert fx.first_row("first")(ctx) == "sort_cards"
    assert fx.last_row("first")(ctx) == "stack_cups"
    # 最上位 (場所と同伴が一致) は beetle の行
    assert fx.nn_distractor("first", "first")(ctx) == "stack_cups"
    assert (
        fx.topk_vote(2, "first", "first")(ctx) == "stack_cups"
    )  # 上位 2 = beetle・heron
    assert fx.empty_state_first(ctx) == "fold_linen"
    assert fx.row_count_position(ctx) == ctx.options[0]
    assert fx.oracle_latent(ctx) == "sort_cards"  # eagle = bird → heron の行
    assert fx.order_lookup(ctx) == "fold_linen"  # 先頭 fold_linen → trout の行
    assert fx.omega_missing_label_lookup(ctx) == "sort_cards"  # 欠けなし → 最初の行
    leaky = _ctx(
        ("sort_cards", "fold_linen", "wind_clock")
    )  # stack_cups が欠ける (旧設計の型)
    assert (
        fx.omega_missing_label_lookup(leaky) == "sort_cards"
    )  # stack_cups → sparrow は無い → fallback


def test_selection_contexts_use_selection_layouts() -> None:
    main = fx.contexts(bat.ARM_A, 0)
    sel = fx.contexts(bat.ARM_A, 0, selection=True)
    assert main[0][1].rows != sel[0][1].rows
    assert main[0][1].options == sel[0][1].options


def test_category_signs() -> None:
    p = bat.probes()[0]
    assert fx.category(p.pointed[bat.ARM_A], p, bat.ARM_A) == 1
    assert fx.category(p.pointed[bat.ARM_A_ROT], p, bat.ARM_A) == -1
    assert fx.category(p.pointed[bat.ARM_B], p, bat.ARM_A) == 0
    assert fx.category(None, p, bat.ARM_A) == 0
