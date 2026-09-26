#!/usr/bin/env python
"""Skill lever pilot — 凍結前の power / size 表 (prereg v2 §6、CPU・合成のみ).

``scripts/skill_lever_scorer.py`` の ``simulate`` / ``design_criteria`` (判定と同じ ``decide`` と
⊥ gate を通す) で、攪乱格子の全点について 4 条件を評価し、全点で満たす最小の (R, K) を選ぶ。

1. screening: 全 (R, K) 候補 × 全攪乱を ``--screen-sims`` 回で。
2. 本確認: screening を通った候補を呼び出し数 (R·K) の少ない順に ``--final-sims`` 回で再評価し、
   最初に全攪乱で通ったものを選ぶ。選んだ (R, K) の OC 曲線も同じ回数で出す。

実データは使わない。実行 (repo root から)::

    uv run python scripts/skill_lever_power_table.py --out <power_table.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from itertools import product

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import skill_lever_scorer as s  # noqa: E402

R_CANDIDATES = (
    4,
    8,
    12,
)  # 4 の倍数 (Ω_q 位置のラテン方格)、R_max = 12 (user 裁定 DL-3)
K_CANDIDATES = (5, 10, 20)  # K ≤ 20 (DL-3)
NUISANCES = tuple(
    s.Nuisance(base=b, bot=bot, sd=sd)
    for b, bot, sd in product(
        ("uniform", "label_skew", "position_skew"), (0.0, 0.1), (0.05, 0.3)
    )
)
OC_EFFECTS = tuple(round(0.1 * i, 1) for i in range(9))


def _nu(nu: s.Nuisance) -> dict[str, object]:
    return {"base": nu.base, "bot": nu.bot, "sd": nu.sd, "oov": nu.oov, "skew": nu.skew}


def _round(obj: object) -> object:
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, dict):
        return {k: _round(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round(v) for v in obj]
    return obj


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--screen-sims", type=int, default=2_000)
    ap.add_argument("--final-sims", type=int, default=10_000)
    args = ap.parse_args(argv)

    cands = sorted(
        product(R_CANDIDATES, K_CANDIDATES), key=lambda rk: (rk[0] * rk[1], rk[0])
    )
    screening = []
    for r, k in cands:
        rows = [
            {"nuisance": _nu(nu), **s.design_criteria(nu, r, k, args.screen_sims)}
            for nu in NUISANCES
        ]
        ok = all(row["ok"] for row in rows)
        screening.append(
            {"R": r, "K": k, "calls": 5 * r * 6 * k, "ok": ok, "rows": rows}
        )
        print(f"screen R={r:2d} K={k:2d} ok={ok}", flush=True)

    chosen = None
    finals = []
    for cand in screening:
        if not cand["ok"]:
            continue
        r, k = cand["R"], cand["K"]
        rows = [
            {"nuisance": _nu(nu), **s.design_criteria(nu, r, k, args.final_sims)}
            for nu in NUISANCES
        ]
        ok = all(row["ok"] for row in rows)
        finals.append({"R": r, "K": k, "ok": ok, "rows": rows})
        print(f"final  R={r:2d} K={k:2d} ok={ok}", flush=True)
        if ok:
            chosen = (r, k)
            break

    oc = []
    if chosen is not None:
        r, k = chosen
        for nu in NUISANCES:
            curve = {
                str(e): s.simulate(nu, r, k, e, args.final_sims) for e in OC_EFFECTS
            }
            oc.append({"nuisance": _nu(nu), "curve": curve})

    out = {
        "tau": s.TAU,
        "delta_plant": s.DELTA_PLANT,
        "alpha": s.ALPHA,
        "power_target": s.POWER_TARGET,
        "size_cap_final": s.ALPHA + s.mc_margin(args.final_sims),
        "screen_sims": args.screen_sims,
        "final_sims": args.final_sims,
        # certification と同じ 4 ファイル (判定コード) に結び付ける (Codex HIGH-1)
        "target_sha256": {
            name: hashlib.sha256(p.read_bytes()).hexdigest()
            for name, p in s.certified_targets().items()
        },
        "chosen": None if chosen is None else {"R": chosen[0], "K": chosen[1]},
        "screening": screening,
        "final": finals,
        "oc_curve": oc,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(_round(out), indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"chosen = {out['chosen']}")
    return 0 if chosen is not None else 1


if __name__ == "__main__":
    sys.exit(main())
