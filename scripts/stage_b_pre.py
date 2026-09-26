"""developmental substrate Stage B — B-pre: M13 C-proper bank の CPU 再解析 (prereg §7).

事前登録 = ``experiments/20260926-developmental-substrate-stage-b/prereg.md``。本スクリプトは
起動時に prereg と入力 bank の sha256 を観測して results.json に書く (封印値を引数 default に
置かない)。入力の sha256 が prereg §7 の値と一致しない・読めない場合は計算せず、
``b_pre_established = false`` / verdict = INVALID_TASK_BATTERY を返す (「実行できなかった」を
「成立」に畳まない)。

rule (prereg §7):

* 分布は ``pre_bias_destination_zone`` の経験分布 (plug-in、平滑化なし)、TV = ½ Σ|p − q|。
  None (parse 不能 / destination なし) は 1 カテゴリ ⊥ として数える (decisions DB-3、user 裁定、
  §7 の 150 / 150 を保つ読み)。⊥ 率は context・条件別に記述報告する。
* ``default_rng(20260926)`` で ``mc_index`` 0..299 の順列を 1 回引き、前半 150 = 半分 1、後半 = 半分 2
  (全 context・両条件で同じ分割)。
* within(c) = TV(半分 1, 半分 2)、between(c, c') = TV(c の半分 1, c' の半分 1)。
* 床 = within の最大値。成立 = 28 対の between 中央値 > 床、を on / off 両方で。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any, Final

import numpy as np

EXP_REL: Final[str] = "experiments/20260926-developmental-substrate-stage-b"
PREREG_REL: Final[str] = f"{EXP_REL}/prereg.md"
BANK_REL: Final[str] = (
    "experiments/20260710-m13-c-proper/artifacts/bank_annotation.jsonl"
)
# prereg §7 に書かれた値 (照合の相手。観測値は起動時に計算する)
BANK_SHA256_PREREG: Final[str] = (
    "378b5423d5b9d927f884e4381c80dd2116ef9342b6f05a92a07b12cd17bdc6fc"
)
SPLIT_SEED: Final[int] = 20260926
N_MC: Final[int] = 300
HALF: Final[int] = 150
N_CONTEXTS: Final[int] = 8
CONDITIONS: Final[tuple[str, ...]] = ("off", "on")
ZONE_KEY: Final[str] = "pre_bias_destination_zone"
BOTTOM: Final[str] = "⊥"  # None の zone (DB-3)

VERDICT_INVALID_BATTERY: Final[str] = "INVALID_TASK_BATTERY"


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def split_halves() -> tuple[frozenset[int], frozenset[int]]:
    """mc_index の順列を 1 回引き、前半 150 / 後半 150 (全 context・両条件で共通)."""
    perm = np.random.default_rng(SPLIT_SEED).permutation(N_MC)
    return frozenset(int(i) for i in perm[:HALF]), frozenset(
        int(i) for i in perm[HALF:]
    )


def tv(p: Counter[str], q: Counter[str]) -> float:
    """plug-in 経験分布の total variation (平滑化なし)."""
    np_, nq = sum(p.values()), sum(q.values())
    zones = set(p) | set(q)
    return 0.5 * sum(abs(p[z] / np_ - q[z] / nq) for z in zones)


def load_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def check_structure(rows: list[dict[str, Any]]) -> list[str]:
    """8 context × 2 条件 × mc_index 0..299 が 1 回ずつ揃っているか."""
    problems: list[str] = []
    keys = Counter((r["condition"], r["frozen_ctx_id"], r["mc_index"]) for r in rows)
    if any(n != 1 for n in keys.values()):
        problems.append("duplicate (condition, context, mc_index)")
    conds = {r["condition"] for r in rows}
    if conds != set(CONDITIONS):
        problems.append(f"conditions {sorted(conds)} != {sorted(CONDITIONS)}")
    for cond in CONDITIONS:
        ctxs = {r["frozen_ctx_id"] for r in rows if r["condition"] == cond}
        if len(ctxs) != N_CONTEXTS:
            problems.append(f"{cond}: {len(ctxs)} contexts != {N_CONTEXTS}")
        for ctx in ctxs:
            idx = {
                r["mc_index"]
                for r in rows
                if r["condition"] == cond and r["frozen_ctx_id"] == ctx
            }
            if idx != set(range(N_MC)):
                problems.append(f"{cond}/{ctx}: mc_index is not 0..{N_MC - 1}")
    if any(ZONE_KEY not in r or not isinstance(r[ZONE_KEY], str | None) for r in rows):
        problems.append(f"{ZONE_KEY} missing or neither string nor None")
    if any(r.get(ZONE_KEY) == BOTTOM for r in rows):
        problems.append(f"{ZONE_KEY} collides with the ⊥ label")
    return problems


def analyse_condition(
    rows: list[dict[str, Any]], cond: str, half1: frozenset[int]
) -> dict[str, Any]:
    ctxs = sorted({r["frozen_ctx_id"] for r in rows if r["condition"] == cond})
    h1: dict[str, Counter[str]] = {c: Counter() for c in ctxs}
    h2: dict[str, Counter[str]] = {c: Counter() for c in ctxs}
    for r in rows:
        if r["condition"] != cond:
            continue
        target = h1 if r["mc_index"] in half1 else h2
        zone = r[ZONE_KEY]
        target[r["frozen_ctx_id"]][BOTTOM if zone is None else zone] += 1
    within = {c: tv(h1[c], h2[c]) for c in ctxs}
    between = {f"{a}|{b}": tv(h1[a], h1[b]) for a, b in combinations(ctxs, 2)}
    floor = max(within.values())
    median = float(np.median(list(between.values())))
    bottom = {c: round((h1[c][BOTTOM] + h2[c][BOTTOM]) / N_MC, 6) for c in ctxs}
    return {
        "bottom_rate": bottom,
        "within": {c: round(v, 6) for c, v in within.items()},
        "between": {k: round(v, 6) for k, v in between.items()},
        "floor": round(floor, 6),
        "between_median": round(median, 6),
        "n_pairs": len(between),
        "established": median > floor,
    }


def run(bank: Path, prereg: Path) -> dict[str, Any]:
    out: dict[str, Any] = {
        "inputs": {
            "bank": {"path": BANK_REL, "sha256": sha256_file(bank)},
            "bank_sha256_prereg": BANK_SHA256_PREREG,
        },
        "prereg_sha256": sha256_file(prereg),
        "split_seed": SPLIT_SEED,
    }
    # 計算できなかった状態を「不成立」(INVALID_TASK_BATTERY) に畳まない (DB-3)
    not_computed = {"status": "not_computed", "b_pre_established": False, "verdict": None}
    if out["inputs"]["bank"]["sha256"] != BANK_SHA256_PREREG:
        out.update(not_computed, reason="input_sha256_mismatch_or_missing")
        return out
    rows = load_rows(bank)
    problems = check_structure(rows)
    if problems:
        out.update(not_computed, reason="input_structure: " + "; ".join(problems))
        return out
    out["status"] = "computed"
    half1, _ = split_halves()
    per_cond = {c: analyse_condition(rows, c, half1) for c in CONDITIONS}
    established = all(v["established"] for v in per_cond.values())
    out["conditions"] = per_cond
    out["b_pre_established"] = established
    if not established:
        out["verdict"] = VERDICT_INVALID_BATTERY
        out["reason"] = "between_median_not_above_floor"
    else:
        out["verdict"] = None
        out["reason"] = "established (gate passed; no Stage B verdict at B-pre)"
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--root", type=Path, default=Path())
    args = ap.parse_args(argv)
    result = run(args.root / BANK_REL, args.root / PREREG_REL)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "event": "STAGE_B_PRE_DONE",
                "status": result["status"],
                "b_pre_established": result["b_pre_established"],
                "verdict": result["verdict"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
