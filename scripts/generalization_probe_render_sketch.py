#!/usr/bin/env python
"""候補 G (汎化 probe) — 見取り図 (``results/sketch.json``) から prereg §7 の表を機械生成する (判定に使わない).

prereg の ``<!-- SKETCH:BEGIN -->`` と ``<!-- SKETCH:END -->`` の間を置き換える (``--write``)、または標準出力に出す。
表の数値はすべて JSON から読む。読み (解釈) の文は prereg の本文に人が書く。

実行 (repo root から)::

    uv run python scripts/generalization_probe_render_sketch.py --write
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
EXP = _REPO_ROOT / "experiments/20261001-generalization-probe-pilot"
BEGIN = "<!-- SKETCH:BEGIN -->"
END = "<!-- SKETCH:END -->"

FORM_JA = {
    "homog_sd005": "一様の混合 sd 0.05 (最も有利)",
    "homog_sd030": "一様の混合 sd 0.3",
    "sparse_1of3": "分類の 1/3 に集中",
    "sparse_2of3": "分類の 2/3 に集中",
    "aon_cell": "セルの全か無か",
    "aon_unit": "単位の全か無か",
    "aon_arm_unit": "arm × 単位の全か無か",
    "aon_item": "項目の全か無か (r を通じて固定)",
    "logodds": "事前偏り × 対数オッズ (base = label_skew)",
    "reverse_1of6": "逆向きの汎化 (項目の 1/6 が λ = −1)",
    "weak_null": "弱い null (単位で 0.4 が 5/7・−1 が 2/7)",
}


def _fmt(x: float | None, nd: int = 3) -> str:
    return "届かない" if x is None else f"{x:.{nd}f}"


def render(sk: dict[str, Any]) -> str:
    p = sk["params"]
    rs = [r["R"] for r in sk["per_R"]]
    lines = [
        BEGIN,
        "",
        "**条件** (`results/sketch.json`、2 回の独立な実行で byte 一致):",
        f"- 判定式は凍結する scorer (`e_values`・`decide`・⊥ gate) をそのまま使った。R の候補 {rs}、K = 1、"
        f"τ = {p['tau']}・α = {p['alpha']}・植える効果 2τ = {p['delta_plant']}。",
        f"- 回数: power の点は {p['n_sim_power']:,} 回、size の点は {p['n_sim_size']:,} 回、各 2 seed ({p['seeds']})。"
        "power は 2 seed の平均、size は大きい方。",
        "- 攪乱点 18 = base {uniform, label_skew, position_skew} × ⊥ {0, 0.1} × 結合 {crn, indep, anti}。"
        "対数オッズの形は base = label_skew の 6 点。",
        "- **size の上限 = α (定理、§5.2)** と **MC の採否** を別の数にした。棄却の数 X について合格は X ≤ x、"
        f"棄却は X ≥ x + 1。x は P(X > x) ≤ {p['mc_fwer']}/G を満たす最小の整数 (X ~ Binomial(N, α)、"
        "G = その R の size の点の数 × seed 数)。表の閾値 (率) は x / N。",
        "",
        "**表 1**: R ごとの選定規則の 3 条件 (§7 の docstring と `select`)。",
        "",
        "| R | 単位 | 呼び出し | P(PASS \\| 2τ) ≥ 0.8 | P(NO_GO \\| 0) ≥ 0.8 | size ≤ 閾値 | 最悪の size | size の点 G | 閾値 (率) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sk["per_R"]:
        lines.append(
            f"| {r['R']} | {r['n_units']} | {r['calls_lever']} | "
            f"{'○' if r['power_ok'] else '×'} | {'○' if r['no_go_ok'] else '×'} | {'○' if r['size_ok'] else '×'} | "
            f"{r['worst_size']:.4f} | {r['n_size_checks']} | {r['size_cap']:.4f} |"
        )
    sel = sk["selection"]
    sel_text = (
        "door-close (R_MAIN が 3 条件を満たさない)"
        if sel["door_close"]
        else "R = " + str(sel["selected_R"])
    )
    lines += [
        "",
        f"**選定**: {sel_text}。"
        f"最も有利な行 (一様 sd 0.05・uniform・⊥ 0・crn) が 2τ で power 0.8 に届く: {'はい' if sk['most_favorable_reaches'] else 'いいえ'}。",
        "",
        "**表 2**: 選定規則の power の最悪値 (攪乱点の中で最小)。",
        "",
        "| R | P(PASS \\| 2τ) 一様 sd 0.05 | 一様 sd 0.3 | 対数オッズ | P(NO_GO \\| 0) 一様 sd 0.05 | 一様 sd 0.3 |",
        "|---|---|---|---|---|---|",
    ]
    for r in sk["per_R"]:

        def worst(
            kind: str, form: str, rows: list[dict[str, Any]] = r["rows"]
        ) -> float:
            return min(
                x["value"] for x in rows if x["kind"] == kind and x["form"] == form
            )

        lines.append(
            f"| {r['R']} | {worst('power_pass', 'homog_sd005'):.3f} | {worst('power_pass', 'homog_sd030'):.3f} | "
            f"{worst('power_pass', 'logodds'):.3f} | {worst('power_no_go', 'homog_sd005'):.3f} | "
            f"{worst('power_no_go', 'homog_sd030'):.3f} |"
        )
    lines += [
        "",
        "**表 3**: 形ごとの power 0.8 の境目 E[C] (掃引の線形補間、判定に使わない)。各欄 有利 (uniform・⊥ 0・crn) / 不利 (label_skew・⊥ 0.1・anti)。",
        "",
        "| 形 | " + " | ".join(f"R = {r}" for r in rs) + " | 到達上限 (有利 / 不利) |",
        "|---|" + "---|" * len(rs) + "---|",
    ]
    reach: dict[str, tuple[float, float]] = {}
    for row in sk["sweeps"]:
        key = row["form"]
        fav = row["bot"] == 0.0 and row["coupling"] == "crn"
        lo, hi = reach.get(key, (0.0, 0.0))
        reach[key] = (row["reachable"], hi) if fav else (lo, row["reachable"])
    for form in FORM_JA:
        if form == "weak_null":
            continue
        cells = []
        for r in rs:
            b = sk["boundaries"][f"R{r}"][form]
            cells.append(f"{_fmt(b['favorable'])} / {_fmt(b['adverse'])}")
        lo, hi = reach.get(form, (0.0, 0.0))
        lines.append(
            f"| {FORM_JA[form]} | " + " | ".join(cells) + f" | {lo:.3f} / {hi:.3f} |"
        )
    lines += [
        "",
        "**表 4**: 枝ごとの size の最悪値 (攪乱点の中で最大、2 seed の大きい方)。境界 E[C] = τ の全形と、帰無の領域 (弱い null・二点の極値)。",
        "",
        "| 点 | 枝 | " + " | ".join(f"R = {r}" for r in rs) + " |",
        "|---|---|" + "---|" * len(rs),
    ]
    keys: list[tuple[str, str]] = []
    for r in sk["per_R"]:
        for x in r["rows"]:
            if x["kind"].startswith("size_"):
                k = (x["form"], x["kind"][5:])
                if k not in keys:
                    keys.append(k)
    for form, branch in keys:
        vals = []
        for r in sk["per_R"]:
            v = [
                x["value"]
                for x in r["rows"]
                if x["form"] == form and x["kind"] == f"size_{branch}"
            ]
            vals.append(f"{max(v):.4f}" if v else "—")
        name = FORM_JA.get(
            form,
            form.replace("pass_extremal_", "二点の極値 {m, −1} m = ").replace(
                "no_go_extremal_", "二点の極値 {m, +1} m = "
            ),
        )
        lines.append(
            f"| {name} | {'PASS' if branch == 'pass' else 'NO_GO'} | "
            + " | ".join(vals)
            + " |"
        )
    lines += [
        "",
        "**表 5**: 定理の直接の確認 (判定式に、単位 d を二点分布から直接与えた棄却率、10⁴ 回 × 2 seed の大きい方)。",
        "",
        "| 二点 | " + " | ".join(f"R = {r}" for r in rs) + " |",
        "|---|" + "---|" * len(rs),
    ]
    pure_keys = list(sk["per_R"][0]["pure_extremal_size"])
    for k in pure_keys:
        branch, m = (
            k.split("_", 1)
            if not k.startswith("no_go")
            else ("no_go", k[len("no_go_") :])
        )
        label = (
            f"{{{m}, −1}} (PASS 枝)" if branch == "pass" else f"{{{m}, +1}} (NO_GO 枝)"
        )
        lines.append(
            f"| {label} | "
            + " | ".join(f"{r['pure_extremal_size'][k]:.4f}" for r in sk["per_R"])
            + " |"
        )
    lines += ["", END]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sketch", type=pathlib.Path, default=EXP / "results/sketch.json")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    sk = json.loads(args.sketch.read_text(encoding="utf-8"))
    text = render(sk)
    if not args.write:
        sys.stdout.write(text + "\n")
        return 0
    prereg = EXP / "prereg.md"
    src = prereg.read_text(encoding="utf-8")
    i, j = src.index(BEGIN), src.index(END) + len(END)
    prereg.write_text(src[:i] + text + src[j:], encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
