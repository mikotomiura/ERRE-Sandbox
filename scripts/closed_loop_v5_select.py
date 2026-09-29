"""閉ループ v5 前段 — pilot の測定量から v5 の設計を選ぶ凍結写像 (pilot prereg §6、scoping ADR §3.3).

pilot の実データより前に凍結する。pilot の結果を見て変えない。

1. pilot の記録を検証し測る (``closed_loop_v5_pilot_scorer``)。``computed`` 以外なら写像を計算しない。
   測定量は候補の M ごとに、pilot の step < 12M の窓で計算したものを使う (user 裁定 DP-4)。
2. その窓で世界別 ⊥ 率の最大 > 0.2 の軸は、その M で不採用 (再走しない)。
3. 挙動値を保守限界 (呼び出し単位と (世界, r) cluster 単位の Wilson 95% の外側、DP-5) に置く:
   B は ŝ_changed の上限、C は ε̂ の下限 (ρ = 1)。oov = max(0.05, 世界別 Ω 外率の上限の最大)、
   ⊥ の格子値 b_hi = 世界別 ⊥ 率の呼び出し単位 Wilson 上限の最大 (床なし、user 裁定 DP-6)。s_same = 0.96 (v4 の実測)。
4. 攪乱格子の全点で、v4 と同じ 4 条件 (C = 2τ を植えられる・P(PASS | 2τ) ≥ 0.8・P(NO_GO | 0) ≥ 0.8・
   size (C = τ) が上限以下) を満たすかを審査する。
   dev 段: λ_dev {pilot, v4} × base {pilot, v4 ループ段, v4 C0 実測} × b {0, b_hi} × 未試行の選び方 {一様, base 制限} (C のみ)
   probe 段: base {measured, uniform, label_skew, position_skew} × sd {0.05, 0.3, 0.5} × g {flat, graded} × k_rep {0, 0.944}
5. 候補 (R, K, M) ∈ {8, 12} × {5, 10} × {4, 6, 8} を (呼び出し数 R(30K + 48M), M, R) の昇順、各候補で軸 B → C。
   screening 2,000 回 (最初の違反点で打ち切る) → 本確認 10⁴ 回 → 最初に全点で合格したものを v5 の設計とする。
6. どれも合格しなければ door-close。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from itertools import product
from typing import TYPE_CHECKING, Any, Final

import numpy as np
from scripts import closed_loop_battery as v4bat
from scripts import closed_loop_sim as v4sim
from scripts import closed_loop_v5_battery as bat
from scripts import closed_loop_v5_pilot_scorer as ps
from scripts import closed_loop_v5_sim as sim
from scripts.stage_b_battery import WEATHER

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

R_CANDIDATES: Final[tuple[int, ...]] = (8, 12)
K_CANDIDATES: Final[tuple[int, ...]] = (5, 10)
M_CANDIDATES: Final[tuple[int, ...]] = (4, 6, 8)
OOV_FLOOR: Final[float] = v4sim.OOV
S_SAME: Final[float] = 0.96  # v4 の同一 prompt・別 seed の選択一致 (scoping ADR §1.2-4)
K_REP_V4: Final[float] = 0.944  # v4 の probe の同一 prompt・別 seed の選択一致 (同上)
K_REPS: Final[tuple[float, ...]] = (0.0, K_REP_V4)
SDS: Final[tuple[float, ...]] = (0.05, 0.3, 0.5)
PROBE_BASES: Final[tuple[str, ...]] = (
    "measured",
    "uniform",
    "label_skew",
    "position_skew",
)
CURVE_SIMS: Final[int] = 1_000
SCREEN_SIMS: Final[int] = 2_000
FINAL_SIMS: Final[int] = 10_000
CURVE_R: Final[tuple[int, ...]] = tuple(range(max(R_CANDIDATES)))

# v4 の実走記録から scoping ADR §2.1 の定義で較正した値 (全 r)。``v4_calibration`` の再計算と test で一致を pin
V4_LAM_DEV: Final[float] = 0.43387853429694445
V4_LOOP_BASE: Final[dict[str, dict[str, float]]] = {
    "rain": {
        "read_book": 0.19072164948453607,
        "walk_path": 0.17010309278350516,
        "sit_quiet": 0.5927835051546392,
        "talk_peer": 0.04639175257731959,
    },
    "clear": {
        "walk_path": 0.3602150537634409,
        "tend_moss": 0.08064516129032258,
        "talk_peer": 0.05913978494623656,
        "rest_eyes": 0.5,
    },
    "wind": {
        "tend_moss": 0.11386138613861387,
        "read_book": 0.06435643564356436,
        "rest_eyes": 0.4405940594059406,
        "sit_quiet": 0.3811881188118812,
    },
}
V4_RECORDS: Final[str] = (
    "experiments/20260927-closed-loop-divergence-pilot/results/run/records.jsonl"
)

# certification (変異試験) が結び付く 10 ファイル: 本登録の 4 本と、import する凍結物 6 本
CERTIFIED: Final[tuple[str, ...]] = (
    "closed_loop_v5_battery.py",
    "closed_loop_v5_pilot_scorer.py",
    "closed_loop_v5_sim.py",
    "closed_loop_v5_select.py",
    "closed_loop_battery.py",
    "closed_loop_sim.py",
    "skill_lever_scorer.py",
    "skill_lever_battery.py",
    "stage_b_scorer.py",
    "stage_b_battery.py",
)

STATUS_CHOSEN: Final[str] = "chosen"
STATUS_DOOR_CLOSE: Final[str] = "door_close"
STATUS_NOT_MAPPED: Final[str] = "not_mapped"
STATUS_INVALID_CERT: Final[str] = "invalid_certification"


def certified_sha256(root: pathlib.Path = _REPO_ROOT) -> dict[str, str]:
    return {
        name: hashlib.sha256((root / "scripts" / name).read_bytes()).hexdigest()
        for name in CERTIFIED
    }


def load_certification(path: pathlib.Path, root: pathlib.Path = _REPO_ROOT) -> bool:
    """certification が有り、全変異が KILLED で、記録 sha256 が現在の 10 ファイルと一致するか."""
    try:
        cert = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (
        isinstance(cert, dict)
        and cert.get("all_killed") is True
        and cert.get("target_sha256") == certified_sha256(root)
    )


# ---------------------------------------------------------------- v4 の較正値


def v4_calibration(
    root: pathlib.Path = _REPO_ROOT,
) -> tuple[float, dict[str, dict[str, float]]]:
    """v4 のループ段の記録から λ_dev とループ段 base を再計算する (scoping ADR §2.1 の ``calibrate`` と同じ定義).

    初訪 = その (世界, r) でその signature に前の記録が無い (⊥ も訪問に数える)。
    """
    rows = [
        json.loads(x)
        for x in (root / V4_RECORDS).read_text(encoding="utf-8").splitlines()
    ]
    loops: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for x in rows:
        if x["phase"] == v4bat.PHASE_LOOP:
            loops[(x["world"], x["replicate"])].append(x)
    sw_n = sw_k = fr_n = fr_k = 0
    fresh: dict[str, dict[str, int]] = {wt: defaultdict(int) for wt in WEATHER}
    for (w, r), xs in sorted(loops.items()):
        xs.sort(key=lambda x: x["step"])
        st = v4bat.EMPTY_STATE
        tb = v4bat.rule(w)
        seen: set[Any] = set()
        for x in xs:
            sig = v4bat.loop_signature(r, x["step"])
            ch = x["parsed"]
            if sig not in st.succeeded and sig not in seen:
                n_sw = sum(1 for s in st.succeeded if s[0] == sig[0])
                if n_sw:
                    sw_n += 1
                    sw_k += ch == tb[sig[0]]
                else:
                    fr_n += 1
                    fr_k += ch == tb[sig[0]]
                    fresh[sig[0]][ch] += 1
            seen.add(sig)
            st = v4bat.update(st, w, sig, ch)
    h0 = fr_k / fr_n
    lam = max(0.0, (sw_k / sw_n - h0) / (1.0 - h0))
    base = {}
    for wt in WEATHER:
        om = v4bat.dev_omega(wt)
        c = np.array([fresh[wt][a] + 0.5 for a in om])
        base[wt] = dict(zip(om, (c / c.sum()).tolist(), strict=True))
    return lam, base


# ---------------------------------------------------------------- 格子


@dataclass(frozen=True)
class DevPoint:
    lam_src: str  # "pilot" / "v4"
    base_src: str  # "pilot" / "v4_loop" / "v4_c0"
    bot: float
    untried: str


def conservative_values(axis: str, m: Mapping[str, Any]) -> dict[str, float]:
    """保守側の固定値 (§6-3)."""
    out = {
        "oov": max(OOV_FLOOR, float(m["oov_hi"])),
        "bot_hi": float(m["bottom_hi"]),
    }
    if axis == bat.AXIS_B:
        out["s_changed"] = float(m["s_changed"]["hi"])
    else:
        out["eps"] = float(m["eps"]["lo"])
    return out


def dev_points(axis: str, m: Mapping[str, Any]) -> list[DevPoint]:
    cv = conservative_values(axis, m)
    untried = sim.UNTRIED_MODES if axis == bat.AXIS_C else (sim.UNTRIED_UNIFORM,)
    return [
        DevPoint(lam, base, bot, un)
        for lam, base, bot, un in product(
            ("pilot", "v4"),
            ("pilot", "v4_loop", "v4_c0"),
            sorted({0.0, cv["bot_hi"]}),
            untried,
        )
    ]


def probe_points() -> list[sim.ProbePoint]:
    return [
        sim.ProbePoint(base, sd, lam, kr)
        for base, sd, lam, kr in product(
            PROBE_BASES, SDS, v4sim.LAMBDA_VERSIONS, K_REPS
        )
    ]


def behaviour(axis: str, m: Mapping[str, Any], dp: DevPoint) -> sim.Behaviour:
    cv = conservative_values(axis, m)
    lam_pilot = m["lam_dev"]
    lam = (
        V4_LAM_DEV
        if dp.lam_src == "v4"
        else (0.0 if lam_pilot is None else float(lam_pilot))
    )
    base = {
        "pilot": sim.base_table(m["base"]),
        "v4_loop": sim.base_table(V4_LOOP_BASE),
        "v4_c0": None,
    }[dp.base_src]
    kw: dict[str, Any] = {}
    if axis == bat.AXIS_B:
        kw["s_changed"] = cv["s_changed"]
    else:
        kw["eps"] = cv["eps"]
        kw["rho"] = 1.0
    return sim.Behaviour(
        axis=axis,
        lam_dev=lam,
        base=base,
        bot=dp.bot,
        oov=cv["oov"],
        s_same=S_SAME,
        untried=dp.untried,
        **kw,
    )


def candidates() -> list[tuple[int, int, int]]:
    """(R, K, M) を (呼び出し数, M, R) の昇順で."""
    return sorted(
        product(R_CANDIDATES, K_CANDIDATES, M_CANDIDATES),
        key=lambda x: (v4bat.n_main_calls(*x), x[2], x[0]),
    )


# ---------------------------------------------------------------- 審査


@dataclass
class Sims:
    curve: int = CURVE_SIMS
    screen: int = SCREEN_SIMS
    final: int = FINAL_SIMS


class Evaluator:
    """dev 段は κ に依らないので、(軸, dev 点, M, R, 回数) ごとに 1 回だけ回してキャッシュする.

    measures = 候補 M (文字列) → 軸 → 測定量。
    """

    def __init__(
        self, measures: Mapping[str, Mapping[str, Mapping[str, Any]]], sims: Sims
    ) -> None:
        self.measures = measures
        self.sims = sims
        self._dev: dict[tuple[Any, ...], v4sim.DevResult] = {}
        self._curve: dict[tuple[Any, ...], v4sim.KappaCurve] = {}

    def dev(
        self, axis: str, dp: DevPoint, m: int, r_values: Sequence[int], n: int, tag: str
    ) -> v4sim.DevResult:
        key = (axis, dp, m, tuple(r_values), n, tag)
        if key not in self._dev:
            beh = behaviour(axis, self.measures[str(m)][axis], dp)
            rng = np.random.default_rng(
                sim.point_seed(axis, asdict(dp), m, tuple(r_values), n, tag)
            )
            self._dev[key] = sim.simulate_dev(beh, m, r_values, n, rng)
        return self._dev[key]

    def row(
        self,
        axis: str,
        dp: DevPoint,
        pp: sim.ProbePoint,
        r: int,
        k: int,
        m: int,
        n: int,
        tag: str,
    ) -> dict[str, Any]:
        ckey = (axis, dp, m, pp)
        if ckey not in self._curve:
            curve_dev = self.dev(axis, dp, m, CURVE_R, self.sims.curve, "curve")
            self._curve[ckey] = sim.kappa_curve(pp, dp.bot, curve_dev)
        curve = self._curve[ckey]
        dev = self.dev(axis, dp, m, tuple(range(r)), n, tag)
        crit = sim.design_criteria(
            pp, dp.bot, curve, dev, k, (axis, asdict(dp), asdict(pp), r, k, m, n, tag)
        )
        return {
            "dev_point": asdict(dp),
            "probe_point": asdict(pp),
            **asdict(crit),
            "reachable": crit.reachable,
            "ok": crit.ok,
            "c_at_kappa1": float(curve.expected_c(r)[-1]),
            "coverage": float(curve.coverage[-1]),
        }

    def check(
        self, axis: str, r: int, k: int, m: int, n: int, tag: str
    ) -> tuple[bool, list[dict[str, Any]]]:
        """全格子点を審査する。最初の違反点で打ち切る."""
        rows = []
        for dp in dev_points(axis, self.measures[str(m)][axis]):
            for pp in probe_points():
                row = self.row(axis, dp, pp, r, k, m, n, tag)
                rows.append(row)
                if not row["ok"]:
                    return False, rows
        return True, rows


def select(
    measures: Mapping[str, Mapping[str, Mapping[str, Any]]],
    sims: Sims | None = None,
    log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """測定量 → v5 の設計 (軸, R, K, M) か door-close (§6)."""
    sims = sims or Sims()
    ev = Evaluator(measures, sims)
    rejected = {
        str(m): sorted(a for a in bat.AXES if measures[str(m)][a]["rejected_bottom"])
        for m in M_CANDIDATES
    }
    screening = []
    finals = []
    chosen = None
    for r, k, m in candidates():
        for axis in (a for a in bat.AXES if a not in rejected[str(m)]):
            ok, rows = ev.check(axis, r, k, m, sims.screen, "screen")
            screening.append(
                {
                    "axis": axis,
                    "R": r,
                    "K": k,
                    "M": m,
                    "calls": v4bat.n_main_calls(r, k, m),
                    "ok": ok,
                    "evaluated_points": len(rows),
                    "first_violation": None if ok else rows[-1],
                }
            )
            if log:
                log(f"screen {axis} R={r} K={k} M={m} ok={ok} points={len(rows)}")
            if not ok:
                continue
            ok_f, rows_f = ev.check(axis, r, k, m, sims.final, "final")
            finals.append(
                {
                    "axis": axis,
                    "R": r,
                    "K": k,
                    "M": m,
                    "ok": ok_f,
                    "evaluated_points": len(rows_f),
                    "first_violation": None if ok_f else rows_f[-1],
                    "worst": _worst(rows_f),
                }
            )
            if log:
                log(f"final  {axis} R={r} K={k} M={m} ok={ok_f}")
            if ok_f:
                chosen = {
                    "axis": axis,
                    "R": r,
                    "K": k,
                    "M": m,
                    "calls": v4bat.n_main_calls(r, k, m),
                }
                break
        if chosen is not None:
            break
    return {
        "status": STATUS_CHOSEN if chosen else STATUS_DOOR_CLOSE,
        "rejected_axes": rejected,
        "conservative_values": {
            str(m): {
                a: conservative_values(a, measures[str(m)][a])
                for a in bat.AXES
                if a not in rejected[str(m)]
            }
            for m in M_CANDIDATES
        },
        "chosen": chosen,
        "screening": screening,
        "final": finals,
        "sims": asdict(sims),
    }


def _worst(rows: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    return {
        "pass_at_plant_min": min(x["pass_at_plant"] for x in rows),
        "no_go_at_zero_min": min(x["no_go_at_zero"] for x in rows),
        "pass_at_tau_max": max(x["pass_at_tau"] for x in rows),
        "no_go_at_tau_max": max(x["no_go_at_tau"] for x in rows),
    }


def _round(obj: object) -> object:
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, dict):
        return {k: _round(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_round(v) for v in obj]
    return obj


def dumps(obj: object) -> str:
    return json.dumps(_round(obj), indent=1, ensure_ascii=False, sort_keys=True) + "\n"


# ---------------------------------------------------------------- 入口


def map_run(
    lines: Sequence[str],
    meta_text: str,
    sims: Sims | None = None,
    log: Callable[[str], None] | None = None,
    certification: pathlib.Path | None = None,
) -> dict[str, Any]:
    """pilot の記録 → 検証 → 測定 → 写像。certification を渡したら先に照合し、不備なら何も計算しない.

    pilot が ``computed`` でなければ写像を計算しない。
    """
    if certification is not None and not load_certification(certification):
        return {
            "pilot": None,
            "mapping": {"status": STATUS_INVALID_CERT, "chosen": None},
        }
    report = ps.evaluate_records(lines, meta_text)
    if report["status"] != ps.STATUS_COMPUTED:
        return {
            "pilot": report,
            "mapping": {"status": STATUS_NOT_MAPPED, "chosen": None},
        }
    return {"pilot": report, "mapping": select(report["measures"], sims, log)}


def hypothetical_measures(
    s_changed_hi: float, eps_lo: float
) -> dict[str, dict[str, dict[str, Any]]]:
    """見取り図用の仮想の測定量.

    挙動値だけを与え (全 M で同じ)、λ_dev・base は v4 の値とする。⊥ と Ω 外は pilot で 0 件だったとして、
    上限を窓の世界別呼び出し数 (12M × 4 r) の Wilson 上限に置く。
    """

    def tally(lo: float, hi: float) -> dict[str, Any]:
        return {"k": 0, "n": 0, "clusters": 0, "rate": None, "lo": lo, "hi": hi}

    out = {}
    for m in M_CANDIDATES:
        zero_hi = ps.wilson(0, bat.N_DEV * m * len(bat.PILOT_R))[1]
        common = {
            "rejected_bottom": False,
            "bottom_hi": zero_hi,
            "oov_hi": zero_hi,
            "lam_dev": V4_LAM_DEV,
            "base": V4_LOOP_BASE,
        }
        out[str(m)] = {
            bat.AXIS_B: {**common, "s_changed": tally(s_changed_hi, s_changed_hi)},
            bat.AXIS_C: {**common, "eps": tally(eps_lo, eps_lo)},
        }
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--records", type=pathlib.Path)
    ap.add_argument("--meta", type=pathlib.Path)
    ap.add_argument("--cert", type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument(
        "--decision-table",
        action="store_true",
        help="仮想の挙動値で写像の見取り図を作る (判定に使わない)",
    )
    args = ap.parse_args(argv)
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{msg} ({time.time() - t0:.0f}s)", flush=True)

    if args.decision_table:
        target = (
            certified_sha256()
        )  # 開始時に記録する (実行中にファイルが書き換わっても結び付きがずれない)
        rows = []
        for s_hi, e_lo in ((0.0, 0.8), (0.5, 0.5), (0.9, 0.2)):
            log(f"hypothetical s_changed_hi={s_hi} eps_lo={e_lo}")
            res = select(hypothetical_measures(s_hi, e_lo), log=log)
            rows.append({"s_changed_hi": s_hi, "eps_lo": e_lo, **res})
        out: Any = {
            "note": "判定に使わない見取り図。仮想の挙動値・λ_dev と base は v4 の値",
            "target_sha256": target,
            "rows": rows,
        }
    else:
        if args.records is None or args.meta is None or args.cert is None:
            ap.error("--records, --meta and --cert are required")
        out = map_run(
            args.records.read_text(encoding="utf-8").splitlines(),
            args.meta.read_text(encoding="utf-8"),
            log=log,
            certification=args.cert,
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(dumps(out), encoding="utf-8", newline="\n")
    log("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
