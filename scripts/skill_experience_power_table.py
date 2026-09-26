#!/usr/bin/env python
"""経験由来 Skill pilot — 凍結前の power / size 表 (prereg v3 §6、CPU・合成のみ).

``scripts/skill_experience_scorer.py`` の ``simulate`` / ``design_criteria`` (判定と同じ ``decide`` と
⊥ gate を通す) で、攪乱格子 18 点の全点について 4 条件を評価し、全点で満たす最小の (R, K) を選ぶ。
効果は全て **clip 後の期待値** (真の C)。表には植えた名目値を併記する。

1. screening: 全 (R, K) 候補 × 全攪乱を ``--screen-sims`` 回で。
2. 本確認: screening を通った候補を呼び出し数の少ない順に ``--final-sims`` 回で再評価し、
   最初に全攪乱で通ったものを選ぶ。選んだ (R, K) の OC 曲線も同じ回数で出す。

実データは使わない。実行 (repo root から)::

    uv run python scripts/skill_experience_power_table.py --out <power_table.json>
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import pathlib
import sys
from itertools import product

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import skill_experience_battery as bat  # noqa: E402
from scripts import skill_experience_scorer as s  # noqa: E402

R_CANDIDATES = (4, 8, 12)  # 4 の倍数 (Ω_q 位置のラテン方格)、R_max = 12 (user 裁定)
K_CANDIDATES = (5, 10, 20)  # K ≤ 20 (user 裁定)
SDS = (0.05, 0.3, 0.5)
NUISANCES = tuple(
    s.Nuisance(base=b, bot=bot, sd=sd)
    for b, bot, sd in product(
        ("uniform", "label_skew", "position_skew"), (0.0, 0.1), SDS
    )
)
OC_EFFECTS = tuple(round(0.1 * i, 1) for i in range(9))
N_CALL_ARMS = len(bat.ALL_ARMS)


def _nu(nu: s.Nuisance) -> dict[str, object]:
    return {
        "base": nu.base,
        "bot": nu.bot,
        "sd": nu.sd,
        "oov": nu.oov,
        "skew": nu.skew,
        # 植えた名目値 (clip 後の期待値が 0 / τ / δ_plant になる μ)
        "nominal": {
            str(c): s.nominal_effect(c, nu.sd, nu.bot)
            for c in (0.0, s.TAU, s.DELTA_PLANT)
        },
    }


def _round(obj: object) -> object:
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, dict):
        return {k: _round(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round(v) for v in obj]
    return obj


def _row(nu: s.Nuisance, r: int, k: int, n: int) -> dict[str, object]:
    crit = s.design_criteria(nu, r, k, n)
    return {"nuisance": _nu(nu), **dataclasses.asdict(crit), "ok": crit.ok}


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
        rows = [_row(nu, r, k, args.screen_sims) for nu in NUISANCES]
        ok = all(row["ok"] for row in rows)
        screening.append(
            {"R": r, "K": k, "calls": N_CALL_ARMS * r * 6 * k, "ok": ok, "rows": rows}
        )
        print(f"screen R={r:2d} K={k:2d} ok={ok}", flush=True)

    chosen = None
    finals = []
    for cand in screening:
        if not cand["ok"]:
            continue
        r, k = cand["R"], cand["K"]
        rows = [_row(nu, r, k, args.final_sims) for nu in NUISANCES]
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
        "effect_definition": "clipped_expectation",
        "sd_exact_max": s.SD_EXACT_MAX,
        "size_cap_final_exact": s.size_cap(0.0, args.final_sims),
        "size_cap_wide": s.SIZE_CAP_WIDE,
        "screen_sims": args.screen_sims,
        "final_sims": args.final_sims,
        "n_call_arms": N_CALL_ARMS,
        # certification と同じ判定コードに結び付ける
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
