"""候補 O_time (時期の評価) — 登録した方策 (fixture) の C への寄与と τ/4 gate (prereg §6).

モデルが登録した方策に完全に従ったときの C を、凍結した設計 (単位・並び・表示順・書き方の対) の上で厳密に計算する。
gate (G prereg §6 の型): 登録 fixture 全体の最大 |C| < τ/4。さらに、下の 3 族はどれも定理で厳密に 0 なので、
0 でなければ実装か前提の誤りとして落とす。

方策の族 (どれも prompt に見えるものだけを読む。arm・書き方の名・規則は見ない):

* ``tag_blind`` (層 1、定理 1): 札を読まない。条件の合う行の最初 / 最後・最多の label・最初 / 最後の行・表示の先頭 / 末尾・
  行数・label × 位置・隣の行の写し・記録に無い行動・label の辞書順。同じ書き方の 2 arm は札の数字だけが違うので、
  2 arm で同じ label を選び、d = 0。
* ``tag_relative``: 札を読むが、札の入れ替え (1 日目 ↔ 2 日目) に不変 (最初の行と同じ札の行に従う など)。2 arm で同じ label → 0。
* ``tag_literal`` (層 2、定理 2): 札の数字・字面を読むが、後ろの語 (目 / 前) の意味を読まない (大きい数・小さい数・数字 "2"・
  辞書順・札の長さ・数字 × 位置)。ago の fwd arm の prompt は後ろの語を除くと asc の bwd arm と同じなので、d_ago = −d_asc → D = 0。

陽性対照 (gate の対象外): 新しい日に従う (+1)・古い日に従う (−1)・asc でだけ新しい日に従う (ago は条件の合う最初の行) (+0.5)。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Final

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import o_time_probe_battery as bat  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

TAU: Final[float] = 0.30
FIXTURE_GATE: Final[float] = TAU / 4.0
EXACT_ZERO: Final[float] = 1e-9
R_TABLE: Final[tuple[int, ...]] = (96, 192, 288)
GATED_FAMILIES: Final[tuple[str, ...]] = ("tag_blind", "tag_relative", "tag_literal")


@dataclass(frozen=True)
class Row:
    tag: str  # 表示された札 (例 "2 日前")
    room: str
    label: str


@dataclass(frozen=True)
class Context:
    """方策が見るもの: 状態の行 (表示順)・probe の部屋・選択肢 (表示順)."""

    rows: tuple[Row, ...]
    room: str
    options: tuple[str, ...]


Policy = "Callable[[Context], str | None]"


@lru_cache(maxsize=65536)
def context(arm: str, enc: str, unit: bat.Unit) -> Context:
    """本走の 1 呼び出しの文脈 (renderer と同じ並び・札・表示順)."""
    fi = bat.ARM_FAMILY[arm]
    table = bat.state_table(arm)
    rows = []
    for room, lab in bat.entry_order(fi, unit.room, unit.replicate):
        day = bat.row_day(arm, room, lab)
        rows.append(Row(bat.tag(enc, day), room, table[day][room][0]))
    return Context(
        tuple(rows),
        bat.ROOMS[unit.room],
        bat.option_order(fi, unit.room, unit.replicate),
    )


# ------------------------------------------------------------- 方策の部品


def _matching(ctx: Context) -> list[Row]:
    return [r for r in ctx.rows if r.room == ctx.room]


def _digit(row: Row) -> int:
    return int(row.tag.split(" ")[0])


def _suffix(row: Row) -> str:
    return row.tag[-1]


def _pick(ctx: Context, rows: Sequence[Row], fallback: str) -> str | None:
    """候補行 (優先順) の最初の Ω 内 label。無ければ fallback ('first' / 'last' / 'bot')."""
    for row in rows:
        if row.label in ctx.options:
            return row.label
    if fallback == "first":
        return ctx.options[0]
    if fallback == "last":
        return ctx.options[-1]
    return None


def _third(ctx: Context) -> str | None:
    """記録に無い行動 (条件の合う行の label 以外の選択肢)."""
    seen = {r.label for r in _matching(ctx)}
    rest = [o for o in ctx.options if o not in seen]
    return rest[0] if rest else None


# ------------------------------------------------------- 札を見ない方策 (層 1)


def match_first(ctx: Context) -> str | None:
    return _pick(ctx, _matching(ctx), "bot")


def match_last(ctx: Context) -> str | None:
    return _pick(ctx, _matching(ctx)[::-1], "bot")


def most_frequent(tie: str):
    def policy(ctx: Context) -> str | None:
        rows = list(ctx.rows) if tie == "first" else list(ctx.rows)[::-1]
        labels = [r.label for r in rows if r.label in ctx.options]
        counts = Counter(labels)
        best = max(counts.values())
        return next(lab for lab in labels if counts[lab] == best)

    return policy


def first_row(ctx: Context) -> str | None:
    return _pick(ctx, ctx.rows, "first")


def last_row(ctx: Context) -> str | None:
    return _pick(ctx, ctx.rows[::-1], "first")


def option_first(ctx: Context) -> str | None:
    return ctx.options[0]


def option_last(ctx: Context) -> str | None:
    return ctx.options[-1]


def row_count_position(ctx: Context) -> str | None:
    return ctx.options[len(ctx.rows) % len(ctx.options)]


def label_position(ctx: Context) -> str | None:
    """条件の合う最初の行の番号 mod 3 の表示位置 (label × 位置)."""
    idx = next(i for i, r in enumerate(ctx.rows) if r.room == ctx.room)
    return ctx.options[idx % len(ctx.options)]


def neighbor_copy(ctx: Context) -> str | None:
    """条件の合う最初の行の次の行の label (状況をまたぐ写し)."""
    idx = next(i for i, r in enumerate(ctx.rows) if r.room == ctx.room)
    return _pick(ctx, ctx.rows[idx + 1 :] + ctx.rows[:idx], "first")


def third_option(ctx: Context) -> str | None:
    return _third(ctx)


def label_alpha(order: str):
    """条件の合う 2 行の label の辞書順で最小 / 最大 (label の事前傾向の一形)."""

    def policy(ctx: Context) -> str | None:
        labels = sorted(r.label for r in _matching(ctx))
        return labels[0] if order == "min" else labels[-1]

    return policy


# ------------------------------------------------- 札の相対の方策 (入れ替えに不変)


def same_tag_as_row(which: str):
    """最初 / 最後の行と同じ札の、条件の合う行に従う."""

    def policy(ctx: Context) -> str | None:
        ref = ctx.rows[0] if which == "first" else ctx.rows[-1]
        return _pick(ctx, [r for r in _matching(ctx) if r.tag == ref.tag], "bot")

    return policy


def majority_tag_first3(ctx: Context) -> str | None:
    """先頭 3 行で多い札の、条件の合う行に従う."""
    counts = Counter(r.tag for r in ctx.rows[:3])
    best = max(counts.values())
    tag = next(r.tag for r in ctx.rows[:3] if counts[r.tag] == best)
    return _pick(ctx, [r for r in _matching(ctx) if r.tag == tag], "bot")


def minority_tag_state(ctx: Context) -> str | None:
    """状態の最後の 5 行で少ない札の、条件の合う行に従う (同数なら最初の行の札)."""
    tail = ctx.rows[-5:]
    counts = Counter(r.tag for r in tail)
    tags = sorted(counts, key=lambda t: (counts[t], [r.tag for r in tail].index(t)))
    return _pick(ctx, [r for r in _matching(ctx) if r.tag == tags[0]], "bot")


# ------------------------------------- 札の字面の方策 (後ろの語を読まない、層 2)


def digit_rank(order: str):
    """条件の合う 2 行のうち、札の数が大きい / 小さい行."""

    def policy(ctx: Context) -> str | None:
        rows = sorted(_matching(ctx), key=_digit, reverse=order == "max")
        return _pick(ctx, rows, "bot")

    return policy


def digit_is(d: int):
    """札の数字が d の、条件の合う行."""

    def policy(ctx: Context) -> str | None:
        return _pick(ctx, [r for r in _matching(ctx) if _digit(r) == d], "bot")

    return policy


def tag_lex(order: str):
    """札の文字列の辞書順で大きい / 小さい行."""

    def policy(ctx: Context) -> str | None:
        rows = sorted(_matching(ctx), key=lambda r: r.tag, reverse=order == "max")
        return _pick(ctx, rows, "bot")

    return policy


def tag_length(tie: str):
    """札の長い行 (同点は表示順で最初 / 最後)."""

    def policy(ctx: Context) -> str | None:
        rows = _matching(ctx) if tie == "first" else _matching(ctx)[::-1]
        return _pick(ctx, sorted(rows, key=lambda r: -len(r.tag)), "bot")

    return policy


def bigger_digit_if_later(fallback: str):
    """大きい数の行が後に表示されていればそれ、そうでなければ fallback (記録に無い行動 / 最初の行)."""

    def policy(ctx: Context) -> str | None:
        rows = _matching(ctx)
        big = max(rows, key=_digit)
        if rows.index(big) == len(rows) - 1:
            return big.label
        return _third(ctx) if fallback == "third" else rows[0].label

    return policy


def digit_plus_position(ctx: Context) -> str | None:
    """札の数 + 表示位置 (状態の中の番号) が大きい行."""
    scored = max(
        (_digit(r) + i, i, r.label)
        for i, r in enumerate(ctx.rows)
        if r.room == ctx.room
    )
    return scored[2]


# ------------------------------------------------------- 陽性対照 (gate 外)


def _is_newer(row: Row, other: Row) -> bool:
    """札の意味で row が other より新しいか (目 = 起点から数える、前 = 今から遡る)."""
    if _suffix(row) == "目":
        return _digit(row) > _digit(other)
    return _digit(row) < _digit(other)


def follow_newer(ctx: Context) -> str | None:
    a, b = _matching(ctx)
    return a.label if _is_newer(a, b) else b.label


def follow_older(ctx: Context) -> str | None:
    a, b = _matching(ctx)
    return b.label if _is_newer(a, b) else a.label


def newer_in_asc_only(ctx: Context) -> str | None:
    rows = _matching(ctx)
    if _suffix(rows[0]) == "目":
        return follow_newer(ctx)
    return rows[0].label


# ------------------------------------------------------------- 登録表


def registered_policies() -> dict[str, tuple[str, Callable[[Context], str | None]]]:
    """名前 → (族, 方策)。族 = 'tag_blind' / 'tag_relative' / 'tag_literal'."""
    reg: dict[str, tuple[str, Callable[[Context], str | None]]] = {
        "match_first": ("tag_blind", match_first),
        "match_last": ("tag_blind", match_last),
        "first_row": ("tag_blind", first_row),
        "last_row": ("tag_blind", last_row),
        "option_first": ("tag_blind", option_first),
        "option_last": ("tag_blind", option_last),
        "row_count_position": ("tag_blind", row_count_position),
        "label_position": ("tag_blind", label_position),
        "neighbor_copy": ("tag_blind", neighbor_copy),
        "third_option": ("tag_blind", third_option),
        "same_tag_as_first_row": ("tag_relative", same_tag_as_row("first")),
        "same_tag_as_last_row": ("tag_relative", same_tag_as_row("last")),
        "majority_tag_first3": ("tag_relative", majority_tag_first3),
        "minority_tag_tail5": ("tag_relative", minority_tag_state),
        "digit_max": ("tag_literal", digit_rank("max")),
        "digit_min": ("tag_literal", digit_rank("min")),
        "digit_is_2": ("tag_literal", digit_is(2)),
        "digit_is_1": ("tag_literal", digit_is(1)),
        "tag_lex_max": ("tag_literal", tag_lex("max")),
        "tag_lex_min": ("tag_literal", tag_lex("min")),
        "bigger_digit_if_later[third]": (
            "tag_literal",
            bigger_digit_if_later("third"),
        ),
        "bigger_digit_if_later[first]": (
            "tag_literal",
            bigger_digit_if_later("first"),
        ),
        "digit_plus_position": ("tag_literal", digit_plus_position),
    }
    for tie in ("first", "last"):
        reg[f"most_frequent[{tie}]"] = ("tag_blind", most_frequent(tie))
        reg[f"tag_length[{tie}]"] = ("tag_literal", tag_length(tie))
    for order in ("min", "max"):
        reg[f"label_alpha[{order}]"] = ("tag_blind", label_alpha(order))
    return reg


def positive_controls() -> dict[str, Callable[[Context], str | None]]:
    return {
        "follow_newer": follow_newer,
        "follow_older": follow_older,
        "newer_in_asc_only": newer_in_asc_only,
    }


# ----------------------------------------------------------------- 計算


def cell_score(choice: str | None, arm: str, unit: bat.Unit) -> int:
    """+1 = w (新しい日の規則の行動)、−1 = foil (古い日)、0 = その他・⊥."""
    w, foil = bat.pointed(arm, unit.room)
    if choice is None:
        return 0
    if choice == w:
        return 1
    if choice == foil:
        return -1
    return 0


def policy_units(policy: Callable[[Context], str | None], r_count: int) -> np.ndarray:
    """(n, 2) = 単位ごとの (d_asc, d_ago)。単位の順は ``bat.units``."""
    out = []
    for u in bat.units(r_count):
        fwd, bwd = bat.FAMILIES[u.family]
        row = []
        for enc in bat.ENCODINGS:
            s = [cell_score(policy(context(arm, enc, u)), arm, u) for arm in (fwd, bwd)]
            row.append((s[0] + s[1]) / 2.0)
        out.append(row)
    return np.array(out)


def policy_c(policy: Callable[[Context], str | None], r_count: int) -> dict[str, float]:
    d = policy_units(policy, r_count)
    return {
        "C": float(np.mean(d.mean(axis=1))),
        "C_asc": float(np.mean(d[:, 0])),
        "C_ago": float(np.mean(d[:, 1])),
    }


def fixture_table(r_count: int) -> dict[str, object]:
    rows = {}
    for name, (fam, pol) in registered_policies().items():
        c = policy_c(pol, r_count)
        rows[name] = {"family": fam, **{k: round(v, 12) for k, v in c.items()}}
    controls = {
        name: {k: round(v, 12) for k, v in policy_c(pol, r_count).items()}
        for name, pol in positive_controls().items()
    }
    worst = max(abs(v["C"]) for v in rows.values())
    return {
        "R": r_count,
        "gate": FIXTURE_GATE,
        "max_abs_C": worst,
        "passed": worst < FIXTURE_GATE,
        "policies": rows,
        "positive_controls": controls,
    }


def fixture_violations(r_count: int) -> list[str]:
    """gate: 登録 fixture 全体の最大 |C| < τ/4。3 族はどれも定理で 0 (0 でなければ実装か前提の誤り)."""
    table = fixture_table(r_count)
    pol = table["policies"]
    out = [
        f"{name}: |C| = {abs(v['C']):.4f} >= {FIXTURE_GATE}"
        for name, v in pol.items()  # type: ignore[union-attr]
        if abs(v["C"]) >= FIXTURE_GATE
    ]
    out += [
        f"{name}: {v['family']} policy has C = {v['C']:.6f} != 0"
        for name, v in pol.items()  # type: ignore[union-attr]
        if v["family"] in GATED_FAMILIES and abs(v["C"]) > EXACT_ZERO
    ]
    return out


def main(argv: list[str] | None = None) -> int:
    """fixture 表を R の候補すべてについて書き出す (prereg §6、manifest が結び付ける)."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--r", type=int, nargs="*", default=list(R_TABLE))
    args = ap.parse_args(argv)
    tables = {f"R{r}": fixture_table(r) for r in args.r}
    result = {
        "gate": FIXTURE_GATE,
        "passed": all(t["passed"] for t in tables.values()),
        "max_abs_C": max(t["max_abs_C"] for t in tables.values()),
        "tables": tables,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(
            json.dumps(result, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
