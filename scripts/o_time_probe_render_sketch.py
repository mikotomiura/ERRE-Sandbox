#!/usr/bin/env python
"""候補 O_time (時期の評価) — 見取り図 (``results/sketch.json``) から prereg §7 の表を機械生成する (判定に使わない).

prereg の ``<!-- SKETCH:BEGIN -->`` と ``<!-- SKETCH:END -->`` の間を置き換える (``--write``)、または標準出力に出す。
表の数値はすべて JSON から読む。読み (解釈) の文は prereg の本文に人が書く。

実行 (repo root から)::

    uv run python scripts/o_time_probe_render_sketch.py --write
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
EXP = _REPO_ROOT / "experiments/20261008-o-time-probe-pilot"
BEGIN = "<!-- SKETCH:BEGIN -->"
END = "<!-- SKETCH:END -->"

FORM_JA = {
    "homog_sd005": "一様の混合 sd 0.05 (最も有利)",
    "homog_sd030": "一様の混合 sd 0.3",
    "sparse_1of3": "部屋の 1/3 に集中",
    "sparse_2of3": "部屋の 2/3 に集中",
    "asc_only": "書き方の集中 (asc だけ)",
    "chrono_only": "時系列の表示でだけ評価",
    "aon_cell": "セルの全か無か",
    "aon_unit": "単位の全か無か",
    "aon_arm_unit": "arm × 単位の全か無か",
    "aon_item": "項目の全か無か (r を通じて固定)",
    "logodds": "事前偏り × 対数オッズ (base = label_skew)",
    "reverse_1of6": "逆向き (項目の 1/6 が古い日に従う)",
    "weak_null": "弱い null (単位で 0.4 が 5/7・−1 が 2/7)",
}
SWEEP_COLUMNS = (0.0, 0.1, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6)


def _fmt(x: float | None, nd: int = 3) -> str:
    return "—" if x is None else f"{x:.{nd}f}"


def _ok(flag: bool) -> str:
    return "○" if flag else "×"


def render(sk: dict[str, Any]) -> str:  # noqa: PLR0915
    p = sk["params"]
    rs = [r["R"] for r in sk["per_R"]]
    lines = [
        BEGIN,
        "",
        "**条件** (`results/sketch.json`、2 回の独立な実行で byte 一致):",
        f"- 判定式は凍結する scorer (`e_values`・`decide`・⊥ gate) をそのまま使った。R の候補 {rs}、K = 1、"
        f"τ = {p['tau']}・α = {p['alpha']}・植える効果 2τ = {p['delta_plant']}。",
        f"- 回数: power と帯の点は {p['n_sim_power']:,} 回、size の点は {p['n_sim_size']:,} 回、各 2 seed ({p['seeds']})。"
        "power と帯は 2 seed の平均、size は大きい方。",
        "- 攪乱点 18 = base {uniform, label_skew, position_skew} × ⊥ {0, 0.1} × 結合 {crn, indep, anti}。"
        "対数オッズの形は base = label_skew の 6 点。",
        "- **size の上限 = α (定理、§5.2)** と **MC の採否** を別の数にした。棄却の数 X について合格は X ≤ x、"
        f"棄却は X ≥ x + 1。x は P(X > x) ≤ {p['mc_fwer']}/G を満たす最小の整数 (X ~ Binomial(N, α)、"
        "G = その R の size の点の数 × seed 数)。表の閾値 (率) は x / N。",
        f"- 条件 4 (帯): crn の {{{', '.join(p['band_bases'])}}} × ⊥ {{0, 0.1}} の攪乱点で、一様 2 形の "
        f"E[C] = τ ± {p['band_delta']} の決着しない確率 1 − P(PASS) − P(NO_GO) ≤ {p['undecided_max']}。"
        "それ以外の crn の攪乱点 (label_skew) は診断用 (表 2 の右の 2 列、選定に使わない)。",
        f"- 模擬の健全性: 全行・全 seed で、実現した C が目標から {p['calibration_tol']} 以内 (表 1 の「較正」)。",
        "",
        "**表 1**: R ごとの選定規則の 4 条件と模擬の較正 (§7.1 と `select`)。",
        "",
        "| R | 単位 | 呼び出し | P(PASS \\| 2τ) ≥ 0.8 | P(NO_GO \\| 0) ≥ 0.8 | size ≤ 閾値 | 帯の決着しない確率 ≤ 0.2 | 較正 | 最悪の size | size の点 G | 閾値 (率) |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sk["per_R"]:
        lines.append(
            f"| {r['R']} | {r['n_units']} | {r['calls']} | {_ok(r['power_ok'])} | {_ok(r['no_go_ok'])} | "
            f"{_ok(r['size_ok'])} | {_ok(r['band_ok'])} | {_ok(r['calibrated'])} | {r['worst_size']:.4f} | "
            f"{r['n_size_checks']} | {r['size_cap']:.4f} |"
        )
    sel = sk["selection"]
    sel_text = (
        "door-close (4 条件を満たす R が無い)"
        if sel["door_close"]
        else f"R_MAIN = {sel['selected_R']}"
    )
    lines += [
        "",
        f"**選定**: {sel_text}。最も有利な行 (一様 sd 0.05・uniform・⊥ 0・crn) が 2τ で power 0.8 に届く: "
        f"{'はい' if sk['most_favorable_reaches'] else 'いいえ'}。",
        "",
        "**表 2**: 選定規則の power の最悪値 (攪乱点の中で最小) と、帯の決着しない確率の最悪値 (条件 4 の攪乱点の中で最大)。"
        "右の 2 列は条件 4 から外した crn の攪乱点 (診断用、選定に使わない)。",
        "",
        "| R | P(PASS \\| 2τ) 一様 sd 0.05 | 一様 sd 0.3 | 対数オッズ | P(NO_GO \\| 0) 一様 sd 0.05 | 一様 sd 0.3 | 帯 τ − 0.05 | 帯 τ + 0.05 | 診断 τ − 0.05 | 診断 τ + 0.05 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sk["per_R"]:
        rows = r["rows"]

        def pick(
            kind: str, rows: list[dict[str, Any]] = rows, **match: Any
        ) -> list[float]:
            return [
                x["value"]
                for x in rows
                if x["kind"] == kind and all(x[k] == v for k, v in match.items())
            ]

        lines.append(
            f"| {r['R']} | {min(pick('power_pass', form='homog_sd005')):.3f} | "
            f"{min(pick('power_pass', form='homog_sd030')):.3f} | {min(pick('power_pass', form='logodds')):.3f} | "
            f"{min(pick('power_no_go', form='homog_sd005')):.3f} | {min(pick('power_no_go', form='homog_sd030')):.3f} | "
            f"{max(pick('band', target_C=0.25)):.3f} | {max(pick('band', target_C=0.35)):.3f} | "
            f"{max(pick('band_diag', target_C=0.25)):.3f} | {max(pick('band_diag', target_C=0.35)):.3f} |"
        )
    lines += [
        "",
        "**表 3**: 形ごとの境目 E[C] (掃引の線形補間、判定に使わない)。各欄 P(PASS) が 0.8 を越える点 / P(NO_GO) が 0.8 を下回る点。"
        "有利 = uniform・⊥ 0・crn、不利 = label_skew・⊥ 0.1・anti。— は掃引の範囲 (到達上限まで) で越えない。"
        "到達上限は R ごとに計算する (時系列の形は凍結した並びの上で較正するので R で変わる)。R で違う値は R の順に / で並べる。",
        "",
        "| 形 | 攪乱点 | " + " | ".join(f"R = {r}" for r in rs) + " | 到達上限 |",
        "|---|---|" + "---|" * len(rs) + "---|",
    ]
    reach: dict[tuple[str, str, int], float] = {}
    for row in sk["sweeps"]:
        kind = (
            "favorable" if row["bot"] == 0.0 and row["coupling"] == "crn" else "adverse"
        )
        reach[(row["form"], kind, row["R"])] = row["reachable"]
    for form, name in FORM_JA.items():
        if form == "weak_null":
            continue
        for kind, ja in (("favorable", "有利"), ("adverse", "不利")):
            cells = []
            for r in rs:
                b = sk["boundaries"][f"R{r}"][form][kind]
                cells.append(f"{_fmt(b['pass_08'])} / {_fmt(b['no_go_08'])}")
            shown = list(
                dict.fromkeys(f"{reach.get((form, kind, r), 0.0):.3f}" for r in rs)
            )
            lines.append(
                f"| {name} | {ja} | " + " | ".join(cells) + f" | {' / '.join(shown)} |"
            )
    lines += [
        "",
        f"**表 4**: 選ばれた R での P(PASS) / P(NO_GO) / 決着しない確率 (2 seed の平均、有利な攪乱点)。列 = E[C]。",
        "",
        "| 形 | " + " | ".join(f"{c:g}" for c in SWEEP_COLUMNS) + " |",
        "|---|" + "---|" * len(SWEEP_COLUMNS),
    ]
    r_show = sel["selected_R"] if sel["selected_R"] is not None else rs[-1]
    for form, name in FORM_JA.items():
        if form == "weak_null":
            continue
        cells = []
        for c in SWEEP_COLUMNS:
            hit = [
                x
                for x in sk["sweeps"]
                if x["R"] == r_show
                and x["form"] == form
                and x["bot"] == 0.0
                and x["coupling"] == "crn"
                and abs(x["target_C"] - c) < 1e-9
            ]
            if hit:
                x = hit[0]
                und = 1.0 - x["pass"] - x["no_go"]
                cells.append(f"{x['pass']:.2f} / {x['no_go']:.2f} / {und:.2f}")
            else:
                cells.append("—")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "**表 5**: 枝ごとの size の最悪値 (攪乱点の中で最大、2 seed の大きい方)。境界 E[C] = τ の全形と、帰無の領域 (弱い null・二点の極値)。",
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
        "**表 6**: 定理の直接の確認 (判定式に、単位 D を二点分布から直接与えた棄却率、10⁴ 回 × 2 seed の大きい方)。",
        "",
        "| 二点 | " + " | ".join(f"R = {r}" for r in rs) + " |",
        "|---|" + "---|" * len(rs),
    ]
    for k in sk["per_R"][0]["pure_extremal_size"]:
        if k.startswith("no_go"):
            label = f"{{{k[len('no_go_') :]}, +1}} (NO_GO 枝)"
        else:
            label = f"{{{k[len('pass_') :]}, −1}} (PASS 枝)"
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
