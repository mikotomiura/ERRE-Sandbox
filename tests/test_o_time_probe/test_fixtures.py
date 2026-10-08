"""登録した方策 (fixture) の C と τ/4 gate、定理 1・2 (prereg §6)."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np
import pytest
from scripts import o_time_probe_battery as bat
from scripts import o_time_probe_fixtures as fx

if TYPE_CHECKING:
    from collections.abc import Callable

R = 6


@lru_cache(maxsize=1)
def _table() -> dict[str, object]:
    return fx.fixture_table(R)


def test_fixture_gate_passes() -> None:
    table = _table()
    assert table["passed"] is True
    assert table["max_abs_C"] == 0.0
    assert pytest.approx(0.075) == fx.FIXTURE_GATE
    assert fx.fixture_violations(R) == []


def test_fixture_table_pinned() -> None:
    """凍結した設計の上の値 (R = 6)。方策・平均・書き方の対を壊すと動く."""
    pol = _table()["policies"]
    assert len(fx.registered_policies()) == 29
    fams = {v["family"] for v in pol.values()}  # type: ignore[union-attr]
    assert fams == {"tag_blind", "tag_relative", "tag_literal"}
    for name in (
        "digit_max",
        "digit_is_2",
        "tag_lex_max",
        "bigger_digit_if_later[first]",
    ):
        assert (pol[name]["C_asc"], pol[name]["C_ago"], pol[name]["C"]) == (
            1.0,
            -1.0,
            0.0,
        )
    for name in ("digit_min", "digit_is_1", "tag_lex_min"):
        assert (pol[name]["C_asc"], pol[name]["C_ago"]) == (-1.0, 1.0)
    assert (
        pol["bigger_digit_if_later[third]"]["C_asc"],
        pol["bigger_digit_if_later[third]"]["C_ago"],
    ) == (0.5, -0.5)
    for name, v in pol.items():  # type: ignore[union-attr]
        assert v["C"] == 0.0, name
        if v["family"] != "tag_literal":
            assert (v["C_asc"], v["C_ago"]) == (0.0, 0.0), name


def test_positive_controls() -> None:
    ctl = _table()["positive_controls"]
    assert ctl["follow_newer"] == {"C": 1.0, "C_asc": 1.0, "C_ago": 1.0}
    assert ctl["follow_older"] == {"C": -1.0, "C_asc": -1.0, "C_ago": -1.0}
    assert ctl["newer_in_asc_only"] == {"C": 0.5, "C_asc": 1.0, "C_ago": 0.0}


def _hashed(
    salt: str, view: Callable[[fx.Context], object]
) -> Callable[[fx.Context], str | None]:
    """view(ctx) の任意の決定的な関数 (hash で選ぶ) である方策."""

    def policy(ctx: fx.Context) -> str | None:
        blob = repr((salt, view(ctx))).encode()
        h = int(hashlib.sha256(blob).hexdigest(), 16)
        if h % 7 == 0:
            return None
        if h % 2:
            return ctx.options[h % len(ctx.options)]
        return ctx.rows[h % len(ctx.rows)].label

    return policy


def _digit_blind_view(ctx: fx.Context) -> object:
    """札の数字を伏せた文脈 (定理 1 の方策が見てよいもの)."""
    return (
        tuple((r.tag[1:], r.room, r.label) for r in ctx.rows),
        ctx.room,
        ctx.options,
    )


def _suffix_blind_view(ctx: fx.Context) -> object:
    """札の後ろの語を伏せた文脈 (定理 2 の方策が見てよいもの)."""
    return (
        tuple((r.tag[:-1], r.room, r.label) for r in ctx.rows),
        ctx.room,
        ctx.options,
    )


def test_theorem1_digit_blind_policies_are_zero_per_unit() -> None:
    """札の数字を見ない任意の決定的な方策は、どの単位・どの書き方でも d = 0."""
    for salt in ("a", "b", "c"):
        d = fx.policy_units(_hashed(salt, _digit_blind_view), R)
        assert np.all(d == 0.0)


def test_theorem2_suffix_blind_policies_cancel_per_unit() -> None:
    """後ろの語を読まない任意の決定的な方策は、どの単位でも d_ago = −d_asc (D = 0)."""
    nonzero = 0
    for salt in ("a", "b", "c"):
        d = fx.policy_units(_hashed(salt, _suffix_blind_view), R)
        assert np.all(d[:, 1] == -d[:, 0])
        nonzero += int(np.count_nonzero(d[:, 0]))
    assert nonzero > 0  # 数字を読むので書き方の中では 0 にならない (打ち消しは対の中)


def test_suffix_reading_policy_is_not_cancelled() -> None:
    """後ろの語を読む方策 (意味の評価) は打ち消されない (陽性対照が +1 になる理由)."""
    d = fx.policy_units(fx.follow_newer, 3)
    assert np.all(d == 1.0)


def test_registered_policies_exact_per_unit() -> None:
    for name, (fam, pol) in fx.registered_policies().items():
        d = fx.policy_units(pol, 3)
        if fam == "tag_literal":
            assert np.all(d[:, 1] == -d[:, 0]), name
        else:
            assert np.all(d == 0.0), name


def test_fixture_violations_detect(monkeypatch: pytest.MonkeyPatch) -> None:
    reg = fx.registered_policies()
    monkeypatch.setattr(
        fx,
        "registered_policies",
        lambda: {**reg, "planted": ("tag_literal", fx.newer_in_asc_only)},
    )
    out = fx.fixture_violations(3)
    assert any(v.startswith("planted: |C| = 0.5000") for v in out)
    assert any(v.startswith("planted: tag_literal policy has C") for v in out)


def test_fixture_violations_detect_small_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """|C| が gate 未満でも、3 族の方策が 0 でなければ実装か前提の誤りとして落とす."""

    def tiny(ctx: fx.Context) -> str | None:
        if ctx.room == "crimson" and ctx.options[0] == bat.LABELS[0][0]:
            return fx.follow_newer(ctx)
        return fx.match_first(ctx)

    reg = fx.registered_policies()
    monkeypatch.setattr(
        fx, "registered_policies", lambda: {**reg, "tiny": ("tag_blind", tiny)}
    )
    out = fx.fixture_violations(3)
    assert [v for v in out if v.startswith("tiny")] == [
        v for v in out if "tag_blind policy has C" in v
    ]
    assert any(v.startswith("tiny: tag_blind policy has C") for v in out)


def test_cell_score() -> None:
    u = bat.Unit(0, 0, 0)
    assert fx.cell_score("open_gate", bat.ARM_AB, u) == 1
    assert fx.cell_score("ring_bell", bat.ARM_AB, u) == -1
    assert fx.cell_score("fill_jar", bat.ARM_AB, u) == 0
    assert fx.cell_score(None, bat.ARM_AB, u) == 0
    assert fx.cell_score("ring_bell", bat.ARM_BA, u) == 1


def test_context_matches_renderer() -> None:
    u = bat.Unit(1, 4, 2)
    for arm, enc in bat.unit_calls(u):
        ctx = fx.context(arm, enc, u)
        lines = bat.render_state(arm, enc, u).splitlines()[1:]
        assert [
            bat.render_row(r.tag, r.room, r.label, bat.TRIALS_PER_ACTION)
            for r in ctx.rows
        ] == lines
        assert ctx.options == bat.option_order(1, 4, 2)
        assert ctx.room == "ivory"


def test_policy_c_averages_encodings() -> None:
    c = fx.policy_c(fx.newer_in_asc_only, 3)
    assert c == {"C": 0.5, "C_asc": 1.0, "C_ago": 0.0}


def test_fixture_table_passed_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    reg = fx.registered_policies()
    monkeypatch.setattr(
        fx,
        "registered_policies",
        lambda: {**reg, "planted": ("tag_literal", fx.follow_newer)},
    )
    table = fx.fixture_table(3)
    assert table["passed"] is False
    assert table["max_abs_C"] == 1.0
