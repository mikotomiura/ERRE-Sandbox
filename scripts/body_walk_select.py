"""探索を身体側へ (b) — pilot の測定量から本登録の設計を選ぶ凍結写像 (pilot prereg §6).

pilot の実データより前に凍結する。pilot の結果を見て変えない。

1. certification が不備なら何も計算しない。pilot の記録を検証し測る (``body_walk_pilot_scorer``)。
   ``computed`` 以外なら写像を計算しない (``not_mapped``)。測定量は候補の M ごとに、pilot の step < 12M の窓で計算したもの。
2. その窓で世界別 ⊥ 率の最大 > 0.2 なら、その M の候補を審査しない (再走しない)。
3. 挙動値を保守側に置く: s_same = ŝ_same の上限、s_changed = ŝ_changed の上限
   (呼び出し単位と (世界, r) cluster 単位の Wilson 95% の外側)、oov = max(0.05, 世界別 Ω 外率の上限の最大)、
   ⊥ の格子値 b_hi = 世界別 ⊥ 率の呼び出し単位 Wilson 上限の最大 (床なし)。
4. 攪乱格子の全点で、v4 と同じ 4 条件 (C = 2τ を κ ≤ 1 で植えられる・P(PASS | 2τ) ≥ 0.8・P(NO_GO | 0) ≥ 0.8・
   size (C = τ) が上限以下) を満たすかを審査する。
   dev 段 (18 点):
     経験点 = pilot の終状態の r block 復元抽出 × b {0, b_hi}
     パラメトリック = λ_dev {pilot, v4} × base {pilot, pilot_low} × b {0, b_hi} × 結合 {coupled, independent}
   probe 段 (48 点、v5 と同じ): base {measured, uniform, label_skew, position_skew} × sd {0.05, 0.3, 0.5} ×
     g {flat, graded} × k_rep {0, 0.944}
5. 候補 (R, K, M) ∈ {8, 12} × {5, 10} × {4, 6, 8} を (呼び出し数 R(30K + 48M), M, R) の昇順 (v5 と同じ)。
   screening 2,000 回 (最初の違反点で打ち切る) → 本確認 10⁴ 回 → 最初に全点で合格したものを本登録の設計とする。
6. どれも合格しなければ door-close (既定)。呼称は「凍結 channel 上限 endpoint での door-close」。

pilot_low (Codex LOW-1・DC-4): 各 weather で平滑化後の点推定が最小の label ℓ (同値は正準順の先) の質量を、その生の数の
保守下限 lo (呼び出し単位と cluster 単位の Wilson 下限の小さい方) に置き、他の label a を p_a·(1 − lo)/(1 − p_ℓ) にする。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time
from dataclasses import asdict, dataclass
from itertools import product
from typing import TYPE_CHECKING, Any, Final

import numpy as np
from scripts import body_walk_battery as bat
from scripts import body_walk_pilot_scorer as ps
from scripts import body_walk_sim as sim
from scripts import closed_loop_battery as v4bat
from scripts import closed_loop_sim as v4sim
from scripts import closed_loop_v5_select as v5sel
from scripts import closed_loop_v5_sim as v5sim
from scripts.stage_b_battery import WEATHER

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

SIM_TAG: Final[str] = "body_walk"
R_CANDIDATES: Final[tuple[int, ...]] = v5sel.R_CANDIDATES
K_CANDIDATES: Final[tuple[int, ...]] = v5sel.K_CANDIDATES
M_CANDIDATES: Final[tuple[int, ...]] = v5sel.M_CANDIDATES
OOV_FLOOR: Final[float] = v4sim.OOV
V4_LAM_DEV: Final[float] = v5sel.V4_LAM_DEV
V4_LOOP_BASE: Final[dict[str, dict[str, float]]] = v5sel.V4_LOOP_BASE
CURVE_SIMS: Final[int] = v5sel.CURVE_SIMS
SCREEN_SIMS: Final[int] = v5sel.SCREEN_SIMS
FINAL_SIMS: Final[int] = v5sel.FINAL_SIMS
CURVE_R: Final[tuple[int, ...]] = tuple(range(max(R_CANDIDATES)))
KIND_PARAMETRIC: Final[str] = "parametric"
KIND_EMPIRICAL: Final[str] = "empirical"
LAM_SOURCES: Final[tuple[str, ...]] = ("pilot", "v4")
BASE_SOURCES: Final[tuple[str, ...]] = ("pilot", "pilot_low")
COUPLINGS: Final[tuple[bool, ...]] = (True, False)
# 見取り図の仮想の挙動値 (s_same = s_changed)
TABLE_ROWS: Final[tuple[float, ...]] = (0.0, 0.5, 0.9)

# certification (変異試験) が結び付くファイル: 本登録の 4 本と、import する凍結物 10 本
CERTIFIED: Final[tuple[str, ...]] = (
    "body_walk_battery.py",
    "body_walk_pilot_scorer.py",
    "body_walk_sim.py",
    "body_walk_select.py",
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

TESTS_DIR: Final[str] = "tests/test_body_walk"
HARNESS: Final[str] = "scripts/body_walk_mutation_check.py"

STATUS_CHOSEN: Final[str] = "chosen"
STATUS_DOOR_CLOSE: Final[str] = "door_close"
STATUS_NOT_MAPPED: Final[str] = "not_mapped"
STATUS_INVALID_CERT: Final[str] = "invalid_certification"


def certified_sha256(root: pathlib.Path = _REPO_ROOT) -> dict[str, str]:
    return {
        name: hashlib.sha256((root / "scripts" / name).read_bytes()).hexdigest()
        for name in CERTIFIED
    }


def tests_sha256(root: pathlib.Path = _REPO_ROOT) -> dict[str, str]:
    """certification が結び付く test (``tests/test_body_walk/*.py``) の sha256."""
    return {
        f.name: hashlib.sha256(f.read_bytes()).hexdigest()
        for f in sorted((root / TESTS_DIR).glob("*.py"))
    }


def harness_sha256(root: pathlib.Path = _REPO_ROOT) -> str:
    return hashlib.sha256((root / HARNESS).read_bytes()).hexdigest()


def load_certification(path: pathlib.Path, root: pathlib.Path = _REPO_ROOT) -> bool:
    """certification が有り、全変異が KILLED で、記録 sha256 が現在のファイルと一致するか (Codex 2 回目 HIGH).

    自己申告の ``all_killed`` だけでなく、変異の明細 (1 件以上・label が一意・全て KILLED)、
    コード 14 本・test・変異 harness の sha256 を照合する。登録変異の集合との一致は manifest が照合する。
    """
    try:
        cert = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(cert, dict):
        return False
    rows = cert.get("mutants")
    return (
        cert.get("all_killed") is True
        and isinstance(rows, list)
        and len(rows) > 0
        and all(isinstance(x, dict) and x.get("status") == "KILLED" for x in rows)
        and len({x.get("label") for x in rows}) == len(rows)
        and cert.get("target_sha256") == certified_sha256(root)
        and cert.get("tests_sha256") == tests_sha256(root)
        and cert.get("harness_sha256") == harness_sha256(root)
    )


# ---------------------------------------------------------------- 格子


@dataclass(frozen=True)
class DevPoint:
    kind: str  # "empirical" / "parametric"
    lam_src: str | None  # "pilot" / "v4" (パラメトリックのみ)
    base_src: str | None  # "pilot" / "pilot_low" (パラメトリックのみ)
    bot: float
    coupled: (
        bool | None
    )  # True = 描画が同一の世界は同じ乱数 / False = 独立 (パラメトリックのみ)


def conservative_values(m: Mapping[str, Any]) -> dict[str, float]:
    """保守側の固定値 (§6-3)."""
    return {
        "s_same": float(m["s_same"]["hi"]),
        "s_changed": float(m["s_changed"]["hi"]),
        "oov": max(OOV_FLOOR, float(m["oov_hi"])),
        "bot_hi": float(m["bottom_hi"]),
    }


def pilot_low(m: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    """最小 label を保守下限に置き、他の label を元の比で補った base (DC-4)."""
    out = {}
    for wt in WEATHER:
        base = m["base"][wt]
        low = m["low_prior"][wt]
        label, lo = low["label"], float(low["lo"])
        scale = (1.0 - lo) / (1.0 - float(base[label]))
        out[wt] = {
            a: lo if a == label else float(base[a]) * scale for a in v4bat.dev_omega(wt)
        }
    return out


def dev_points(m: Mapping[str, Any]) -> list[DevPoint]:
    """dev 段の格子 (経験点が先。b_hi = 0 なら b は 1 値に畳む)."""
    bots = sorted({0.0, conservative_values(m)["bot_hi"]})
    emp = [DevPoint(KIND_EMPIRICAL, None, None, b, None) for b in bots]
    par = [
        DevPoint(KIND_PARAMETRIC, lam, base, b, c)
        for lam, base, b, c in product(LAM_SOURCES, BASE_SOURCES, bots, COUPLINGS)
    ]
    return emp + par


def probe_points() -> list[v5sim.ProbePoint]:
    """probe 段の格子 (v5 と同じ 48 点)."""
    return v5sel.probe_points()


def behaviour(m: Mapping[str, Any], dp: DevPoint) -> sim.Behaviour:
    """パラメトリック点の方策."""
    cv = conservative_values(m)
    lam_pilot = m["lam_dev"]
    lam = (
        V4_LAM_DEV
        if dp.lam_src == "v4"
        else (0.0 if lam_pilot is None else float(lam_pilot))
    )
    probs = m["base"] if dp.base_src == "pilot" else pilot_low(m)
    return sim.Behaviour(
        lam_dev=lam,
        base=sim.base_table(probs),
        bot=dp.bot,
        oov=cv["oov"],
        s_same=cv["s_same"],
        s_changed=cv["s_changed"],
        coupled=bool(dp.coupled),
    )


def candidates() -> list[tuple[int, int, int]]:
    """(R, K, M) を (呼び出し数, M, R) の昇順で (v5 と同じ)."""
    return v5sel.candidates()


# ---------------------------------------------------------------- 審査


@dataclass
class Sims:
    curve: int = CURVE_SIMS
    screen: int = SCREEN_SIMS
    final: int = FINAL_SIMS


class Evaluator:
    """dev 段は κ に依らないので、(dev 点, M, R, 回数, 段) ごとに 1 回だけ回してキャッシュする.

    measures / chains = 候補 M (文字列) → 測定量 / 経験点の入力。
    """

    def __init__(
        self,
        measures: Mapping[str, Mapping[str, Any]],
        chains: Mapping[str, Mapping[str, Any]],
        sims: Sims,
    ) -> None:
        self.measures = measures
        self.chains = chains
        self.sims = sims
        self._dev: dict[tuple[Any, ...], v4sim.DevResult] = {}
        self._curve: dict[tuple[Any, ...], v4sim.KappaCurve] = {}

    def dev(
        self, dp: DevPoint, m: int, r_values: Sequence[int], n: int, tag: str
    ) -> v4sim.DevResult:
        key = (dp, m, tuple(r_values), n, tag)
        if key not in self._dev:
            rng = np.random.default_rng(
                v5sim.point_seed(SIM_TAG, asdict(dp), m, tuple(r_values), n, tag)
            )
            if dp.kind == KIND_EMPIRICAL:
                self._dev[key] = sim.empirical_dev(
                    self.chains[str(m)], len(r_values), n, rng
                )
            else:
                beh = behaviour(self.measures[str(m)], dp)
                self._dev[key] = sim.simulate_dev(beh, m, r_values, n, rng)
        return self._dev[key]

    def row(
        self,
        dp: DevPoint,
        pp: v5sim.ProbePoint,
        r: int,
        k: int,
        m: int,
        n: int,
        tag: str,
    ) -> dict[str, Any]:
        ckey = (dp, m, pp)
        if ckey not in self._curve:
            curve_dev = self.dev(dp, m, CURVE_R, self.sims.curve, "curve")
            self._curve[ckey] = v5sim.kappa_curve(pp, dp.bot, curve_dev)
        curve = self._curve[ckey]
        dev = self.dev(dp, m, tuple(range(r)), n, tag)
        crit = v5sim.design_criteria(
            pp,
            dp.bot,
            curve,
            dev,
            k,
            (SIM_TAG, asdict(dp), asdict(pp), r, k, m, n, tag),
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
        self, r: int, k: int, m: int, n: int, tag: str
    ) -> tuple[bool, list[dict[str, Any]]]:
        """全格子点を審査する。最初の違反点で打ち切る."""
        rows = []
        for dp in dev_points(self.measures[str(m)]):
            for pp in probe_points():
                row = self.row(dp, pp, r, k, m, n, tag)
                rows.append(row)
                if not row["ok"]:
                    return False, rows
        return True, rows


def _worst(rows: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    return {
        "pass_at_plant_min": min(x["pass_at_plant"] for x in rows),
        "no_go_at_zero_min": min(x["no_go_at_zero"] for x in rows),
        "pass_at_tau_max": max(x["pass_at_tau"] for x in rows),
        "no_go_at_tau_max": max(x["no_go_at_tau"] for x in rows),
    }


def select(
    measures: Mapping[str, Mapping[str, Any]],
    chains: Mapping[str, Mapping[str, Any]],
    sims: Sims | None = None,
    log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """測定量・経験点の入力 → 本登録の設計 (R, K, M) か door-close (§6)."""
    sims = sims or Sims()
    ev = Evaluator(measures, chains, sims)
    rejected = sorted(m for m in M_CANDIDATES if measures[str(m)]["rejected_bottom"])
    screening = []
    finals = []
    chosen = None
    for r, k, m in candidates():
        if m in rejected:
            continue
        ok, rows = ev.check(r, k, m, sims.screen, "screen")
        screening.append(
            {
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
            log(f"screen R={r} K={k} M={m} ok={ok} points={len(rows)}")
        if not ok:
            continue
        ok_f, rows_f = ev.check(r, k, m, sims.final, "final")
        finals.append(
            {
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
            log(f"final  R={r} K={k} M={m} ok={ok_f}")
        if ok_f:
            chosen = {"R": r, "K": k, "M": m, "calls": v4bat.n_main_calls(r, k, m)}
            break
    return {
        "status": STATUS_CHOSEN if chosen else STATUS_DOOR_CLOSE,
        "rejected_bottom_M": rejected,
        "conservative_values": {
            str(m): conservative_values(measures[str(m)])
            for m in M_CANDIDATES
            if m not in rejected
        },
        "pilot_low": {
            str(m): pilot_low(measures[str(m)])
            for m in M_CANDIDATES
            if m not in rejected
        },
        "chosen": chosen,
        "screening": screening,
        "final": finals,
        "sims": asdict(sims),
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
    return {
        "pilot": report,
        "mapping": select(report["measures"], report["chains"], sims, log),
    }


def hypothetical_behaviour(s: float) -> sim.Behaviour:
    """見取り図の仮想の方策: s_same = s_changed = s、λ_dev は v4 の値、⊥・Ω 外は 0。

    base は v4 のループ段 base を p^(T_sit / T_walk) で平らにした仮想値 (scoping ADR §1.3 の近似。判定に使わない)。
    """
    exponent = bat.sit_sampling().temperature / bat.walk_sampling().temperature
    return sim.Behaviour(
        lam_dev=V4_LAM_DEV,
        base=sim.tempered_table(V4_LOOP_BASE, exponent),
        bot=0.0,
        oov=0.0,
        s_same=s,
        s_changed=s,
    )


def decision_table(
    sims: Sims | None = None, log: Callable[[str], None] | None = None
) -> list[dict[str, Any]]:
    """見取り図: 仮想の挙動 → 合成 pilot (凍結 plan) → 凍結と同じ ``map_run`` (certification なし)."""
    meta = json.dumps(bat.request_meta_walk())
    rows = []
    for s in TABLE_ROWS:
        if log:
            log(f"hypothetical s_same = s_changed = {s}")
        recs = sim.synthetic_records(hypothetical_behaviour(s), tag=f"table|{s}")
        lines = [json.dumps(x, ensure_ascii=True) for x in recs]
        rows.append({"s": s, **map_run(lines, meta, sims, log)})
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--records", type=pathlib.Path)
    ap.add_argument("--meta", type=pathlib.Path)
    ap.add_argument("--cert", type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument(
        "--decision-table",
        action="store_true",
        help="仮想の挙動値と合成 pilot で写像の見取り図を作る (判定に使わない)",
    )
    args = ap.parse_args(argv)
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{msg} ({time.time() - t0:.0f}s)", flush=True)

    if args.decision_table:
        # 開始時に記録する (実行中にファイルが書き換わっても結び付きがずれない)
        target = certified_sha256()
        out: Any = {
            "note": (
                "判定に使わない見取り図。仮想の挙動値 (s_same = s_changed)・λ_dev は v4 の値・"
                "base は v4 ループ段 base を T の比で平らにした仮想値・⊥ と Ω 外は 0。"
                "合成 pilot を凍結と同じ map_run に通した"
            ),
            "target_sha256": target,
            "rows": decision_table(log=log),
        }
    else:
        if args.records is None or args.meta is None or args.cert is None:
            ap.error("--records, --meta and --cert are required")
        out = map_run(
            # U+2028 などで行を割らない (JSONL は改行文字だけで区切る)
            args.records.read_text(encoding="utf-8").split("\n"),
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
