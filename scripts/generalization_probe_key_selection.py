"""probe key の選定 (実データ前・モデル不使用): 字面の写し方の fixture を釣り合わせる決定的な局所探索.

手順 (prereg §2.3 に登録する):
1. pool = 各分類の、よく知られた動物名で、次を満たすもの (下の POOLS。基準で外した語は EXCLUDED に理由つきで残す)。
   - 4 文字以上。分類を示す語素 (fly / bug / bee / fish / bird) を含まない。
   - dev key・label・distractor と文字 4-gram を共有せず、部分文字列の関係にない。
   - 一般的な意味が動物以外に強く寄らない (pike・mullet・snapper は外した)。
2. 各 (key, つ組 j, R) について、登録した key の字面の方策 (66 種) の寄与 x を、**選定用の行順**
   (``bat.selection_entry_order``、本走と別の seed。Codex HIGH-4) と凍結した表示順の上で計算する。
   本走の行順は選定に使わない。本走の行順の上の fixture gate は、選定の後の確認 (落ちたら door-close、選び直さない)。
3. 目的関数 = R ∈ {6, 12, 18} と方策での max |C| (C = 24 probe の x の平均)。副目的 = 二乗和。
4. seed 20261001 の乱択初期値 × 200 回、各回で交換 (未使用の pool の語と / 同じ分類の 2 slot) の山登り。最良を採る。
   見るのは字面の方策の C だけで、モデルの出力・汎化のしやすさは見ない。

出力の assignment は ``generalization_probe_battery.PROBE_KEYS`` と一致する (test と manifest が照合する)。

実行 (repo root から、所要 2 分ほど)::

    uv run python scripts/generalization_probe_key_selection.py \
        --out experiments/20261001-generalization-probe-pilot/results/key_selection.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import generalization_probe_battery as bat  # noqa: E402
from scripts import generalization_probe_fixtures as fx  # noqa: E402

POOLS = {
    "bird": [
        "eagle",
        "toucan",
        "robin",
        "falcon",
        "pelican",
        "flamingo",
        "penguin",
        "ostrich",
        "raven",
        "hawk",
        "finch",
        "wren",
        "stork",
        "swan",
        "vulture",
        "canary",
        "albatross",
    ],
    "fish": [
        "salmon",
        "mackerel",
        "halibut",
        "anchovy",
        "tuna",
        "haddock",
        "minnow",
        "tilapia",
        "shark",
        "flounder",
        "guppy",
        "barracuda",
        "marlin",
    ],
    "insect": [
        "cicada",
        "termite",
        "mantis",
        "flea",
        "wasp",
        "moth",
        "cockroach",
        "aphid",
        "weevil",
        "gnat",
        "louse",
        "earwig",
        "midge",
        "katydid",
    ],
}
EXCLUDED = {
    "parrot": "sparrow と 4-gram 'parr' を共有",
    "pike": "武器の意味が強い",
    "mullet": "髪型の意味が強い",
    "snapper": "カメ・写真の意味",
    "owl": "3 文字",
    "cod": "3 文字",
    "eel": "3 文字",
    "ant": "3 文字",
    "swordfish": "語素 fish",
    "catfish": "語素 fish",
    "firefly": "語素 fly",
    "dragonfly": "語素 fly",
    "butterfly": "語素 fly",
    "ladybug": "語素 bug",
    "bumblebee": "語素 bee",
    "kingfisher": "語素 fish",
}
R_VALUES = (6, 12, 18)
SEED = 20261001
RESTARTS = 200


def surface_policies() -> dict[str, object]:
    return {
        n: p for n, (fam, p) in fx.registered_policies().items() if fam == "key_surface"
    }


def contribution(
    key: str, cls: str, j: int, r_count: int, pols: dict[str, object]
) -> np.ndarray:
    ci = bat.CLASSES.index(cls)
    place, company = bat.COMBOS[j % len(bat.COMBOS)]
    sit = object.__new__(bat.Situation)
    object.__setattr__(sit, "key", key)
    object.__setattr__(sit, "place", place)
    object.__setattr__(sit, "company", company)
    pointed = {a: bat.rule(a)[cls] for a in bat.LEVER_ARMS}
    idx = 3 * j + ci
    probe = bat.Probe(f"q{idx:02d}", idx, j, sit, pointed)
    out = np.zeros(len(pols))
    for fi, fam in enumerate(bat.FAMILIES):
        for r in range(r_count):
            ctxs = []
            for arm in fam:
                table = bat.state_table(arm)
                rows = tuple(
                    fx.Row(s.key, s.place, s.company, table[s][0])
                    for s in bat.selection_entry_order(fi, j, r)
                )
                ctxs.append(
                    (
                        arm,
                        fx.Context(
                            rows, key, place, company, bat.option_order(fi, j, r)
                        ),
                    )
                )
            for pi, pol in enumerate(pols.values()):
                out[pi] += (
                    sum(fx.category(pol(ctx), probe, arm) for arm, ctx in ctxs) / 2.0
                )
    return out / (len(bat.FAMILIES) * r_count)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    pols = surface_policies()
    names = list(pols)
    # x[cls][key] = (8 j, len(R), n_pol)
    x = {
        c: {
            k: np.stack(
                [
                    np.stack([contribution(k, c, j, r, pols) for r in R_VALUES])
                    for j in range(8)
                ]
            )
            for k in POOLS[c]
        }
        for c in bat.CLASSES
    }
    rng = np.random.default_rng(SEED)

    def score(assign: dict[str, list[str]]) -> tuple[float, float]:
        tot = (
            sum(x[c][assign[c][j]][j] for c in bat.CLASSES for j in range(8)) / 24.0
        )  # (R, pol)
        return float(np.max(np.abs(tot))), float(np.sum(tot**2))

    best = None
    for _ in range(RESTARTS):
        assign = {
            c: list(rng.choice(POOLS[c], size=8, replace=False)) for c in bat.CLASSES
        }
        cur = score(assign)
        improved = True
        while improved:
            improved = False
            for c in bat.CLASSES:
                unused = [k for k in POOLS[c] if k not in assign[c]]
                moves = [(j, k) for j in range(8) for k in unused] + [
                    (j, -(j2 + 1)) for j in range(8) for j2 in range(j + 1, 8)
                ]
                for j, k in moves:
                    if isinstance(k, str) and k in assign[c]:
                        continue  # 先に採った手で使用済みになった語
                    trial = {cc: list(v) for cc, v in assign.items()}
                    if isinstance(k, str):
                        trial[c][j] = k
                    else:
                        j2 = -k - 1
                        trial[c][j], trial[c][j2] = trial[c][j2], trial[c][j]
                    s = score(trial)
                    if s < cur:
                        assign, cur, improved = trial, s, True
        if best is None or cur < best[0]:
            best = (cur, assign)
    (max_abs, ssq), assign = best
    assert all(len(set(v)) == len(v) for v in assign.values()), "duplicate key"
    tot = sum(x[c][assign[c][j]][j] for c in bat.CLASSES for j in range(8)) / 24.0
    worst = {
        f"R{r}": {
            names[i]: round(float(tot[ri, i]), 6)
            for i in np.argsort(-np.abs(tot[ri]))[:5]
        }
        for ri, r in enumerate(R_VALUES)
    }
    result = {
        "seed": SEED,
        "restarts": RESTARTS,
        "R_values": list(R_VALUES),
        "n_policies": len(names),
        "max_abs_C": max_abs,
        "sum_sq": ssq,
        "assignment": assign,
        "worst5": worst,
        "pools": POOLS,
        "excluded": EXCLUDED,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
