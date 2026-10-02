"""候補 G (汎化 probe) — 登録した写し方 (fixture) の C への寄与と τ/4 gate (prereg §6).

モデルが登録した方策に完全に従ったときの C を、凍結した設計 (単位・layout・表示順) の上で厳密に計算する。
gate (統合系 ADR §5.2、v4 ADR §3.1 の型): 登録 fixture 全体の最大 |C| < τ/4。

方策の 2 つの族:

* **key を見ない方策** (近傍の 1 行・上位 k の投票・特徴の重み・最多・最初・最後・行数・空状態・label × 位置・
  Ω や表示順から分類を推す設計を知った方策): つ組の 3 probe の prompt は probe key だけが違う
  (battery の ``check_triple_prompts_differ_only_in_key``) ので、方策の出力はつ組で同じ label L になる。
  arm a について L は 3 分類のうちちょうど 1 つで w、1 つで foil、1 つで other なので、つ組の和は 0。
  よって key に依らない方策は、どの単位でも d = 0 (定理。確率的な方策なら期待値で 0)。表で 0 を確かめる。
* **key の字面を使う方策** (編集距離・連続する最長共通部分文字列・最長共通部分列・文字 2/3-gram の Jaccard・
  長さ・頭文字・末尾の文字・辞書順の隣):
  probe key の字面から dev 行を選ぶ。分類と字面の関係は語の選び方に依るので、寄与を計算して gate にかける。

陽性対照 (gate の対象外): 分類を読む方策 (oracle) は C = +1、別の分類の行を写す方策は C = −1/2。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import generalization_probe_battery as bat  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

TAU: Final[float] = 0.30
FIXTURE_GATE: Final[float] = TAU / 4.0


@dataclass(frozen=True)
class Row:
    key: str
    place: str
    company: str
    label: str


@dataclass(frozen=True)
class Context:
    """方策が見るもの: 状態の行 (表示順)・probe の状況・選択肢 (表示順)."""

    rows: tuple[Row, ...]
    key: str
    place: str
    company: str
    options: tuple[str, ...]


Policy = "Callable[[Context], str | None]"


def contexts(
    arm: str, r: int, *, selection: bool = False
) -> list[tuple[bat.Probe, Context]]:
    """arm・replicate r の 24 probe の文脈。selection=True は probe key の選定用の行順 (本走と別)."""
    fi = bat.ARM_FAMILY[arm]
    table = bat.state_table(arm)
    order_fn = bat.selection_entry_order if selection else bat.entry_order
    out = []
    for p in bat.probes():
        order = order_fn(fi, p.triple, r)
        rows = tuple(Row(s.key, s.place, s.company, table[s][0]) for s in order)
        sit = p.situation
        options = bat.option_order(fi, p.triple, r)
        out.append((p, Context(rows, sit.key, sit.place, sit.company, options)))
    return out


# ------------------------------------------------------------- 方策の部品


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


def _ordered(ctx: Context, score: Callable[[Row], float], tie: str) -> list[Row]:
    """Score の降順。同点は状態の表示順 (tie='first') か逆順 (tie='last')."""
    idx = range(len(ctx.rows)) if tie == "first" else range(len(ctx.rows) - 1, -1, -1)
    rows = [ctx.rows[i] for i in idx]
    return sorted(rows, key=lambda row: -score(row))


def _vote(ctx: Context, rows: Sequence[Row], fallback: str) -> str | None:
    """Rows の中で Ω 内 label の最多。同点は rows の中で先に出た label."""
    labels = [row.label for row in rows if row.label in ctx.options]
    if not labels:
        return _pick(ctx, (), fallback)
    counts = Counter(labels)
    best = max(counts.values())
    return next(lab for lab in labels if counts[lab] == best)


def distractor_match(
    ctx: Context, row: Row, w_place: float = 1.0, w_company: float = 1.0
) -> float:
    return w_place * (row.place == ctx.place) + w_company * (row.company == ctx.company)


# ------------------------------------------------------- key を見ない方策


def nn_distractor(
    tie: str, fallback: str, w_place: float = 1.0, w_company: float = 1.0
):
    def policy(ctx: Context) -> str | None:
        ranked = _ordered(
            ctx, lambda row: distractor_match(ctx, row, w_place, w_company), tie
        )
        top = distractor_match(ctx, ranked[0], w_place, w_company)
        return _pick(
            ctx,
            [r for r in ranked if distractor_match(ctx, r, w_place, w_company) == top],
            fallback,
        )

    return policy


def topk_vote(k: int, tie: str, fallback: str):
    def policy(ctx: Context) -> str | None:
        ranked = _ordered(ctx, lambda row: distractor_match(ctx, row), tie)
        return _vote(ctx, ranked[:k], fallback)

    return policy


def exact_vote(tie: str, fallback: str):
    def policy(ctx: Context) -> str | None:
        rows = [r for r in ctx.rows if distractor_match(ctx, r) == 2]
        if tie == "last":
            rows = rows[::-1]
        return _vote(ctx, rows, fallback)

    return policy


def most_frequent(tie: str, fallback: str):
    def policy(ctx: Context) -> str | None:
        rows = list(ctx.rows) if tie == "first" else list(ctx.rows)[::-1]
        return _vote(ctx, rows, fallback)

    return policy


def first_row(fallback: str):
    def policy(ctx: Context) -> str | None:
        return _pick(ctx, ctx.rows, fallback)

    return policy


def last_row(fallback: str):
    def policy(ctx: Context) -> str | None:
        return _pick(ctx, ctx.rows[::-1], fallback)

    return policy


def row_count_position(ctx: Context) -> str | None:
    """行数 mod 4 の表示位置を選ぶ (状態の向きを見ない)."""
    return ctx.options[len(ctx.rows) % len(ctx.options)]


def empty_state_first(ctx: Context) -> str | None:
    """空状態 (C0) と同じ選び方: 表示の先頭."""
    return ctx.options[0]


def label_position(ctx: Context) -> str | None:
    """状態で最初に Ω 内 label が出た行番号 mod 4 の表示位置を選ぶ (label × 位置)."""
    for i, row in enumerate(ctx.rows):
        if row.label in ctx.options:
            return ctx.options[i % len(ctx.options)]
    return ctx.options[0]


def position_of_label(ctx: Context) -> str | None:
    """最初の行の label が表示で占める位置の、次の位置の選択肢 (label × 位置の交互作用)."""
    lab = _pick(ctx, ctx.rows, "first")
    i = ctx.options.index(lab) if lab in ctx.options else 0
    return ctx.options[(i + 1) % len(ctx.options)]


# --------------------------------------------------- key の字面を使う方策


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def lcs_substring(a: str, b: str) -> int:
    best = 0
    for i in range(len(a)):
        for j in range(len(b)):
            n = 0
            while i + n < len(a) and j + n < len(b) and a[i + n] == b[j + n]:
                n += 1
            best = max(best, n)
    return best


def lcs_subsequence(a: str, b: str) -> int:
    """最長共通部分列 (連続でなくてよい) の長さ."""
    prev = [0] * (len(b) + 1)
    for ca in a:
        cur = [0]
        for j, cb in enumerate(b, 1):
            cur.append(prev[j - 1] + 1 if ca == cb else max(prev[j], cur[j - 1]))
        prev = cur
    return prev[-1]


def jaccard(a: str, b: str, n: int) -> float:
    ga = bat.char_ngrams(a, n)
    gb = bat.char_ngrams(b, n)
    if not ga and not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


SURFACE_SCORES: Final[dict[str, Callable[[str, str], float]]] = {
    "levenshtein": lambda a, b: -levenshtein(a, b),
    "lcs_substring": lambda a, b: lcs_substring(a, b),
    "lcs_subsequence": lambda a, b: lcs_subsequence(a, b),
    "bigram_jaccard": lambda a, b: jaccard(a, b, 2),
    "trigram_jaccard": lambda a, b: jaccard(a, b, 3),
    "length": lambda a, b: -abs(len(a) - len(b)),
    "first_letter": lambda a, b: float(a[0] == b[0]),
    "last_letter": lambda a, b: float(a[-1] == b[-1]),
}


def alphabetical_rank(a: str, b: str, keys: Sequence[str]) -> float:
    allk = sorted({*keys, a})
    return -abs(allk.index(a) - allk.index(b))


def surface_nn(metric: str, tie: str, fallback: str):
    def policy(ctx: Context) -> str | None:
        if metric == "alphabetical":
            keys = [r.key for r in ctx.rows]
            ranked = _ordered(
                ctx, lambda row: alphabetical_rank(ctx.key, row.key, keys), tie
            )
            score = lambda row: alphabetical_rank(ctx.key, row.key, keys)  # noqa: E731
        else:
            fn = SURFACE_SCORES[metric]
            ranked = _ordered(ctx, lambda row: fn(ctx.key, row.key), tie)
            score = lambda row: fn(ctx.key, row.key)  # noqa: E731
        top = score(ranked[0])
        return _pick(ctx, [r for r in ranked if score(r) == top], fallback)

    return policy


def surface_vote(metric: str, k: int, tie: str, fallback: str):
    fn = SURFACE_SCORES[metric]

    def policy(ctx: Context) -> str | None:
        ranked = _ordered(ctx, lambda row: fn(ctx.key, row.key), tie)
        return _vote(ctx, ranked[:k], fallback)

    return policy


# ------------------------------------- 設計を知った、key を見ない方策 (Codex HIGH-1)

# Ω に無い label → 写す dev key (Codex の反例の写像)。旧設計では Ω が分類を明かしたので C = 1 になった
OMEGA_LOOKUP: Final[dict[str, str]] = {
    "stack_cups": "sparrow",
    "sort_cards": "trout",
    "fold_linen": "beetle",
    "tidy_shelf": "sparrow",
    "wind_clock": "trout",
    "count_keys": "beetle",
}
# 表示の先頭の label → 写す dev key (表示順が分類を明かせば正答する)
ORDER_LOOKUP: Final[dict[str, str]] = {
    "sort_cards": "sparrow",
    "fold_linen": "trout",
    "stack_cups": "beetle",
    "wind_clock": "sparrow",
    "count_keys": "trout",
    "tidy_shelf": "beetle",
}


def _copy_key(ctx: Context, key: str) -> str | None:
    return _pick(ctx, [r for r in ctx.rows if r.key == key], "first")


def omega_missing_label_lookup(ctx: Context) -> str | None:
    """状態の label のうち Ω に無いものから分類を推し、その分類の dev 行を写す (無ければ最初の行)."""
    missing = sorted({r.label for r in ctx.rows} - set(ctx.options))
    if missing:
        return _copy_key(ctx, OMEGA_LOOKUP[missing[0]])
    return _pick(ctx, ctx.rows, "first")


def order_lookup(ctx: Context) -> str | None:
    """表示の先頭の label から分類を推し、その分類の dev 行を写す."""
    return _copy_key(ctx, ORDER_LOOKUP[ctx.options[0]])


# ------------------------------------------------------- 陽性対照 (gate 外)


def oracle_latent(ctx: Context) -> str | None:
    """Probe key の分類と同じ分類の行の label (汎化の完全な形)."""
    c = bat.key_class(ctx.key)
    return _pick(ctx, [r for r in ctx.rows if bat.key_class(r.key) == c], "first")


def oracle_next_class(ctx: Context) -> str | None:
    """次の分類の行の label を写す (逆向きの一形)."""
    c = bat.next_class(bat.key_class(ctx.key))
    return _pick(ctx, [r for r in ctx.rows if bat.key_class(r.key) == c], "first")


# ------------------------------------------------------------- 登録表


def registered_policies() -> dict[str, tuple[str, object]]:
    """名前 → (族, 方策)。族 = 'key_blind' / 'key_surface'."""
    reg: dict[str, tuple[str, object]] = {}
    for tie in ("first", "last"):
        for fb in ("first", "last", "bot"):
            reg[f"nn_distractor[{tie},{fb}]"] = ("key_blind", nn_distractor(tie, fb))
            reg[f"nn_place_weighted[{tie},{fb}]"] = (
                "key_blind",
                nn_distractor(tie, fb, 2.0, 1.0),
            )
            reg[f"nn_company_weighted[{tie},{fb}]"] = (
                "key_blind",
                nn_distractor(tie, fb, 1.0, 2.0),
            )
            reg[f"exact_vote[{tie},{fb}]"] = ("key_blind", exact_vote(tie, fb))
            reg[f"most_frequent[{tie},{fb}]"] = ("key_blind", most_frequent(tie, fb))
            for k in (3, 5):
                reg[f"top{k}_vote[{tie},{fb}]"] = ("key_blind", topk_vote(k, tie, fb))
            metrics = (*SURFACE_SCORES, "alphabetical")
            for metric in metrics:
                reg[f"surface_{metric}[{tie},{fb}]"] = (
                    "key_surface",
                    surface_nn(metric, tie, fb),
                )
            for metric in ("levenshtein", "bigram_jaccard"):
                reg[f"surface_{metric}_top3_vote[{tie},{fb}]"] = (
                    "key_surface",
                    surface_vote(metric, 3, tie, fb),
                )
    for fb in ("first", "last", "bot"):
        reg[f"first_row[{fb}]"] = ("key_blind", first_row(fb))
        reg[f"last_row[{fb}]"] = ("key_blind", last_row(fb))
    reg["row_count_position"] = ("key_blind", row_count_position)
    reg["empty_state_first"] = ("key_blind", empty_state_first)
    reg["label_position"] = ("key_blind", label_position)
    reg["omega_missing_label_lookup"] = ("key_blind", omega_missing_label_lookup)
    reg["order_lookup"] = ("key_blind", order_lookup)
    reg["position_of_label"] = ("key_blind", position_of_label)
    return reg


def positive_controls() -> dict[str, object]:
    return {"oracle_latent": oracle_latent, "oracle_next_class": oracle_next_class}


# ----------------------------------------------------------------- 計算


def category(choice: str | None, probe: bat.Probe, arm: str) -> int:
    """+1 = w、−1 = foil、0 = その他・⊥."""
    if choice is None:
        return 0
    if choice == probe.pointed[arm]:
        return 1
    if choice == probe.pointed[bat.FOIL[arm]]:
        return -1
    return 0


def policy_c(policy, r_count: int, *, selection: bool = False) -> float:
    """方策に完全に従ったときの C (単位 d の平均、K = 1、全単位)."""
    d = policy_units(policy, r_count, selection=selection)
    return float(np.mean(d))


def policy_units(policy, r_count: int, *, selection: bool = False) -> np.ndarray:
    s: dict[tuple[str, int, int], float] = {}
    for arm in bat.LEVER_ARMS:
        for r in range(r_count):
            per_triple: dict[int, list[int]] = {}
            for p, ctx in contexts(arm, r, selection=selection):
                per_triple.setdefault(p.triple, []).append(
                    category(policy(ctx), p, arm)
                )
            for j, cats in per_triple.items():
                s[(arm, j, r)] = sum(cats) / len(cats)
    out = []
    for u in bat.units(r_count):
        a, b = bat.FAMILIES[u.family]
        out.append(
            (s[(a, u.triple, u.replicate)] + s[(b, u.triple, u.replicate)]) / 2.0
        )
    return np.array(out)


def fixture_table(r_count: int, *, selection: bool = False) -> dict[str, object]:
    rows = {}
    for name, (fam, pol) in registered_policies().items():
        c = policy_c(pol, r_count, selection=selection)
        rows[name] = {"family": fam, "C": round(c, 12)}
    controls = {
        name: round(policy_c(pol, r_count, selection=selection), 12)
        for name, pol in positive_controls().items()
    }
    worst = max(abs(v["C"]) for v in rows.values())
    blind_worst = max(abs(v["C"]) for v in rows.values() if v["family"] == "key_blind")
    return {
        "R": r_count,
        "gate": FIXTURE_GATE,
        "max_abs_C": worst,
        "max_abs_C_key_blind": blind_worst,
        "passed": worst < FIXTURE_GATE,
        "policies": rows,
        "positive_controls": controls,
    }


def fixture_violations(r_count: int) -> list[str]:
    """gate: 登録 fixture 全体の最大 |C| < τ/4。key を見ない方策は定理で 0 (0 でなければ実装の誤り)."""
    table = fixture_table(r_count)
    pol = table["policies"]
    out = [
        f"{name}: |C| = {abs(v['C']):.4f} >= {FIXTURE_GATE}"
        for name, v in pol.items()  # type: ignore[union-attr]
        if abs(v["C"]) >= FIXTURE_GATE
    ]
    out += [
        f"{name}: key-blind policy has C = {v['C']:.6f} != 0"
        for name, v in pol.items()  # type: ignore[union-attr]
        if v["family"] == "key_blind" and abs(v["C"]) > 1e-9
    ]
    return out


def main(argv: list[str] | None = None) -> int:
    """fixture 表を R の候補すべてについて書き出す (prereg §6、manifest が結び付ける)."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--r", type=int, nargs="*", default=[6, 12, 18])
    args = ap.parse_args(argv)
    tables = {f"R{r}": fixture_table(r) for r in args.r}
    result = {
        "gate": FIXTURE_GATE,
        "passed": all(t["passed"] for t in tables.values()),
        "max_abs_C": max(t["max_abs_C"] for t in tables.values()),
        "tables": tables,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
