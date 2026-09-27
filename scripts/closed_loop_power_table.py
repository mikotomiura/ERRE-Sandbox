#!/usr/bin/env python
"""閉ループ分散 pilot — 凍結前の power / size 表と fixture 表 (prereg v4 §2.5 / §6、CPU・合成のみ).

``scripts/closed_loop_sim.py`` の閉ループ模擬 (判定と同じ v2 の ``decide`` と ⊥ gate を通す) で、
攪乱格子 48 点 (base 4 × ⊥ 率 2 × sd 3 × λ 版 2) の全点について 4 条件を評価し、全点で満たす
(renderer, R, K, M) を選ぶ。真の C は E[C] (κ の格子上で解く、植えられない点は不合格)。

1. κ 曲線: (renderer, M, base, b, λ 版) ごとに κ の格子で E[C] を計算する (sd は閉形式で全点)。
2. screening: renderer は R1 → R1+ の順 (ADR: R1 が primary、R1+ は予備)、その中で呼び出し数
   R(30K + 48M) の少ない順に、全格子点を ``--screen-sims`` 回で評価する。最初の違反点で打ち切り、
   その点を理由として残す。
3. 本確認: screening を通った候補を同じ順に ``--final-sims`` 回で全点評価し、最初に全点で通ったものを選ぶ。
4. 選んだ設計の OC 曲線・λ 層別・固着 (κ = 1 の上限と coverage)・γ 感度 (γ = κ/2, 0、DU-2 の記述)。
5. ``--fixtures``: 選んだ設計で fixture 表を計算し、正側 gate (DU-1) を判定する。

実データは使わない (実測 base は凍結済みの C0 記録から推定した定数)。実行 (repo root から)::

    uv run python scripts/closed_loop_power_table.py --out <power_table.json>
    uv run python scripts/closed_loop_power_table.py --fixtures --power <power_table.json> \\
        --out <fixture_table.json>
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import pathlib
import sys
import time
from itertools import product
from typing import Any

import numpy as np

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import closed_loop_battery as bat  # noqa: E402
from scripts import closed_loop_scorer as sc  # noqa: E402
from scripts import closed_loop_sim as sim  # noqa: E402

R_CANDIDATES = (4, 8, 12)  # 4 の倍数 (Ω_q 位置・世界順のラテン方格)、R_max = 12
K_CANDIDATES = (5, 10, 20)  # K ≤ 20 (user 裁定)
BOTS = (0.0, 0.1)
SDS = (0.05, 0.3, 0.5)
# 実測 base を先に評価する (違反が最も出やすい点で早く打ち切る)
BASE_ORDER = ("measured", "uniform", "label_skew", "position_skew")
OC_EFFECTS = tuple(round(0.1 * i, 1) for i in range(7))
FIXTURE_ITERS = 250
GAMMA_SENSITIVITY = (0.5, 0.0)

Point = tuple[str, float, float, str]


def _round(obj: object) -> object:
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, dict):
        return {k: _round(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round(v) for v in obj]
    return obj


def _points() -> list[Point]:
    return list(product(BASE_ORDER, BOTS, SDS, sim.LAMBDA_VERSIONS))


def _point(p: Point) -> dict[str, object]:
    base, bot, sd, lam = p
    return {"base": base, "bot": bot, "sd": sd, "lam": lam}


def build_curves(
    renderer: str, m: int, curve_sims: int, gamma_factor: float = 1.0
) -> dict[Point, sim.KappaCurve]:
    out = {}
    for base, bot, lam in product(BASE_ORDER, BOTS, sim.LAMBDA_VERSIONS):
        cfg = sim.Config(
            base=base,
            bot=bot,
            sd=SDS[0],
            lam=lam,
            renderer=renderer,
            m=m,
            gamma_factor=gamma_factor,
        )
        for sd, curve in sim.kappa_curves(cfg, SDS, n=curve_sims).items():
            out[(base, bot, sd, lam)] = curve
    return out


def _row(
    curves: dict[Point, sim.KappaCurve], p: Point, r: int, k: int, n: int
) -> dict[str, object]:
    curve = curves[p]
    crit = sim.design_criteria(curve.cfg, curve, r, k, n)
    return {
        "point": _point(p),
        **dataclasses.asdict(crit),
        "reachable": crit.reachable,
        "ok": crit.ok,
        "c_at_kappa1": float(curve.expected_c(r)[-1]),
    }


def candidates() -> list[tuple[str, int, int, int]]:
    """R1 → R1+。その中で呼び出し数の少ない順 (同数なら M・R の小さい順)."""
    out = []
    for renderer in bat.RENDERERS:
        cands = sorted(
            product(R_CANDIDATES, K_CANDIDATES, bat.M_CHOICES),
            key=lambda x: (bat.n_main_calls(*x), x[2], x[0]),
        )
        out += [(renderer, r, k, m) for r, k, m in cands]
    return out


def _extras(
    chosen: dict[str, Any],
    curves: dict[Point, sim.KappaCurve],
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    renderer, r, k, m = chosen["renderer"], chosen["R"], chosen["K"], chosen["M"]
    oc, strata, gamma = [], [], []
    for p in _points():
        if p[1] != 0.1 or p[2] != 0.3:
            continue
        curve = curves[p]
        row: dict[str, Any] = {"point": _point(p), "curve": {}}
        for eff in OC_EFFECTS:
            kap = curve.solve(eff, r)
            row["curve"][str(eff)] = (
                None
                if kap is None
                else {
                    "kappa": kap,
                    **sim.simulate_verdicts(curve.cfg, kap, r, k, args.final_sims),
                }
            )
        oc.append(row)
        kap = curve.solve(sim.DELTA_PLANT, r)
        if kap is not None:
            strata.append(
                {
                    "point": _point(p),
                    "kappa": kap,
                    "strata": sim.lambda_strata(curve.cfg, kap, r),
                }
            )
    for gf in GAMMA_SENSITIVITY:
        gc = build_curves(renderer, m, args.curve_sims, gamma_factor=gf)
        for p, curve in gc.items():
            if p[2] != 0.3:
                continue
            kap = curve.solve(sim.DELTA_PLANT, r)
            entry: dict[str, Any] = {
                "gamma_factor": gf,
                "point": _point(p),
                "c_at_kappa1": float(curve.expected_c(r)[-1]),
                "coverage_at_kappa1": float(curve.coverage[-1]),
                "plant_reachable": kap is not None,
            }
            if kap is not None and p[0] == "measured":
                entry["at_plant"] = sim.simulate_verdicts(
                    curve.cfg, kap, r, k, args.screen_sims
                )
            gamma.append(entry)
    return oc, strata, gamma


def power_main(args: argparse.Namespace) -> int:
    t0 = time.time()
    curves: dict[tuple[str, int], dict[Point, sim.KappaCurve]] = {}
    for renderer, m in product(bat.RENDERERS, bat.M_CHOICES):
        curves[(renderer, m)] = build_curves(renderer, m, args.curve_sims)
        print(f"curves {renderer} M={m} ({time.time() - t0:.0f}s)", flush=True)
    reach = [
        {
            "renderer": renderer,
            "M": m,
            "point": _point(p),
            "c_at_kappa1_R8": float(c.expected_c(8)[-1]),
            "coverage_at_kappa1": float(c.coverage[-1]),
        }
        for (renderer, m), cs in curves.items()
        for p, c in cs.items()
        if p[2] == SDS[0]
    ]

    screening = []
    for renderer, r, k, m in candidates():
        rows = []
        ok = True
        for p in _points():
            row = _row(curves[(renderer, m)], p, r, k, args.screen_sims)
            rows.append(row)
            if not row["ok"]:
                ok = False
                break
        screening.append(
            {
                "renderer": renderer,
                "R": r,
                "K": k,
                "M": m,
                "calls": bat.n_main_calls(r, k, m),
                "ok": ok,
                "evaluated_points": len(rows),
                "first_violation": None if ok else rows[-1],
                "rows": rows,
            }
        )
        print(
            f"screen {renderer} R={r} K={k} M={m} ok={ok} ({time.time() - t0:.0f}s)",
            flush=True,
        )

    chosen = None
    finals = []
    for cand in screening:
        if not cand["ok"]:
            continue
        renderer, r, k, m = cand["renderer"], cand["R"], cand["K"], cand["M"]
        rows = [
            _row(curves[(renderer, m)], p, r, k, args.final_sims) for p in _points()
        ]
        ok = all(row["ok"] for row in rows)
        finals.append(
            {"renderer": renderer, "R": r, "K": k, "M": m, "ok": ok, "rows": rows}
        )
        print(
            f"final  {renderer} R={r} K={k} M={m} ok={ok} ({time.time() - t0:.0f}s)",
            flush=True,
        )
        if ok:
            chosen = {"renderer": renderer, "R": r, "K": k, "M": m}
            break

    oc: list[dict[str, Any]] = []
    strata: list[dict[str, Any]] = []
    gamma: list[dict[str, Any]] = []
    if chosen is not None:
        oc, strata, gamma = _extras(
            chosen, curves[(chosen["renderer"], chosen["M"])], args
        )
        print(f"oc / strata / gamma ({time.time() - t0:.0f}s)", flush=True)

    out = {
        "tau": sc.TAU,
        "delta_plant": sim.DELTA_PLANT,
        "alpha": sc.ALPHA,
        "power_target": sim.POWER_TARGET,
        "effect_definition": "expected_C_loop_via_kappa",
        "kappa_grid": list(sim.KAPPA_GRID),
        "sd_exact_max": sim.SD_EXACT_MAX,
        "size_cap_wide": sim.SIZE_CAP_WIDE,
        "curve_sims": args.curve_sims,
        "screen_sims": args.screen_sims,
        "final_sims": args.final_sims,
        "gamma_factor_for_selection": 1.0,
        "measured_base": {
            "alpha": [list(x) for x in sim.MEASURED_ALPHA],
            "beta": list(sim.MEASURED_BETA),
            "inputs": sim.MEASURED_INPUT_SHA256,
        },
        "target_sha256": {
            name: hashlib.sha256(p.read_bytes()).hexdigest()
            for name, p in sc.certified_targets().items()
        },
        "chosen": chosen,
        "reachability": reach,
        "screening": screening,
        "final": finals,
        "oc_curve": oc,
        "lambda_strata": strata,
        "gamma_sensitivity": gamma,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(_round(out), indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"chosen = {chosen} ({time.time() - t0:.0f}s)")
    return 0 if chosen is not None else 1


def fixture_main(args: argparse.Namespace) -> int:
    power = json.loads(args.power.read_text(encoding="utf-8"))
    chosen = power["chosen"]
    if chosen is None:
        print("ERROR: power table has no chosen design")
        return 2
    renderer, r, k, m = chosen["renderer"], chosen["R"], chosen["K"], chosen["M"]
    policies = dict(sim.FIXTURES)
    if renderer != bat.RENDERER_R1PLUS:
        policies = {n: f for n, f in policies.items() if n not in sim.R1PLUS_ONLY}
    name_pc, pc = sim.POSITIVE_CONTROL
    rows = []
    for base in BASE_ORDER:
        cfg = sim.Config(
            base=base, bot=0.0, sd=SDS[0], lam="flat", renderer=renderer, m=m
        )
        curve = sim.kappa_curves(cfg, (SDS[0],), n=args.curve_sims)[SDS[0]]
        settings: list[tuple[str, float | None, float, str]] = [
            ("P", curve.solve(c, r), 1.0, f"C={c}")
            for c in (0.0, sc.TAU, sim.DELTA_PLANT)
        ]
        settings += [("L", 0.0, rho, f"rho={rho}") for rho in (0.5, 1.0)]
        for mode, kap, rho, label in settings:
            if kap is None:
                continue
            for name, pol in [*policies.items(), (name_pc, pc)]:
                res = sim.run_fixture(
                    pol,
                    mode=mode,
                    cfg=cfg,
                    kappa=kap,
                    rho=rho,
                    r_count=r,
                    k=k,
                    n_iter=args.fixture_iters,
                    seed=sim.SIM_SEED,
                )
                u = np.array(res.units)
                mean = float(u.mean())
                se = float(u.std(ddof=1) / np.sqrt(len(u)))
                rows.append(
                    {
                        "fixture": name,
                        "base": base,
                        "mode": mode,
                        "setting": label,
                        "kappa": kap,
                        "rho": rho,
                        "mean": mean,
                        "se": se,
                        "upper": mean + 3.0 * se,
                        "n_units": len(u),
                    }
                )
                print(
                    f"{base:13s} {mode} {label:8s} {name:22s} {mean:+.4f} ± {se:.4f}",
                    flush=True,
                )
    gate_ok, worst, flagged = sim.fixture_gate(rows)
    registered = [x for x in rows if x["fixture"] != name_pc]
    most_negative = min(registered, key=lambda x: x["mean"])
    out = {
        "design": chosen,
        "gate": (
            "hard: max over registered fixtures of (mean + 3SE) < tau/2; "
            "fixtures with (mean + 3SE) >= tau/4 are listed in the claim "
            "(positive side only, DU-1 / DU-3)"
        ),
        "gate_threshold_hard": sim.FIXTURE_HARD,
        "gate_threshold_flag": sim.FIXTURE_GATE,
        "gate_ok": gate_ok,
        "flagged": flagged,
        "worst_positive": worst,
        "most_negative": most_negative,
        "fixture_iters": args.fixture_iters,
        "target_sha256": power["target_sha256"],
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(_round(out), indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"gate_ok = {out['gate_ok']} worst = {worst['fixture']} "
        f"{worst['upper']:.4f} flagged = {flagged}"
    )
    return 0 if out["gate_ok"] else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--fixtures", action="store_true")
    ap.add_argument("--power", type=pathlib.Path)
    ap.add_argument("--curve-sims", type=int, default=1_000)
    ap.add_argument("--screen-sims", type=int, default=2_000)
    ap.add_argument("--final-sims", type=int, default=10_000)
    ap.add_argument("--fixture-iters", type=int, default=FIXTURE_ITERS)
    args = ap.parse_args(argv)
    if args.fixtures:
        return fixture_main(args)
    return power_main(args)


if __name__ == "__main__":
    sys.exit(main())
