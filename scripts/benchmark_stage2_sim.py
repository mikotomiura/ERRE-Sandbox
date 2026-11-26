"""判別性 gate 段 2 — 見取り図 (gate 4、CPU、実データの前) と fixture の差の点検。

規則の SSOT は prereg §I。判定式は ``benchmark_stage2_stats`` の検定と ``classify`` をそのまま使う
(単位の値の分布を数で持ち、同じ検定を (N,) 本まとめて計算する)。

生成の模型 (prereg §I):
- 単位 = 対 n_p 個の平均。対の値 ∈ {+1, 0, −1} (0 は相殺・⊥・Ω 内の残りをまとめた)。
- モデル m の単位 u の平均 μ = C_m + h·z_u、z_u = ±1 (単位の順に交互、固定の schedule)。
  対の値は P(+1) = (g_m + μ)/2・P(−1) = (g_m − μ)/2、g_m = min(1, |C_m| + h + e) (相殺しない率)。
- 結合: crn = z と対の一様乱数をモデル間で共有、indep = モデルごとに独立 (z は交互の並びの置換)。

使い方: ``python -m scripts.benchmark_stage2_sim --out <dir>`` (``PYTHONDONTWRITEBYTECODE=1``)。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from fractions import Fraction
import sys
from pathlib import Path
from typing import Any, Final

import numpy as np
from scripts import benchmark_stage2_stats as st

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent

PAIRS_PER_UNIT: Final[dict[str, int]] = {"v2": 2, "v3": 2, "G": 3, "O_time": 2}
R_GRID: Final[dict[str, tuple[int, ...]]] = {
    "v2": (8, 16, 32),
    "v3": (8, 16, 32),
    "G": (12, 24, 36),
    "O_time": (12, 24, 48),
}
NOISE: Final[tuple[tuple[str, float, float, str], ...]] = (
    ("low_crn", 0.0, 0.0, "crn"),  # 最も有利な行 (小さい σ、door-close の判定に使う)
    ("low_indep", 0.0, 0.0, "indep"),
    ("mid_crn", 0.2, 0.3, "crn"),
    ("mid_indep", 0.2, 0.3, "indep"),
    ("high_crn", 0.3, 1.0, "crn"),
    ("high_indep", 0.3, 1.0, "indep"),
)
N_SIMS: Final[int] = 2000
SIM_SEED: Final[int] = 20261126
# K と ΣM: 対象の battery の pilot の入場 M_p に、他の 3 battery が各 6 本入場した場合を足す
# (M_p に対して K が最大 = 対差の検定の閾値が最も厳しい。size は K に依らず定理で守られる)
OTHER_BATTERIES: Final[int] = 3
OTHER_ENTRANTS: Final[int] = 6
BASE: Final[float] = 0.3


def shapes() -> dict[str, dict[str, Any]]:
    """形 (prereg §I)。C はモデルの真の C、zero は相殺しない率を 1 にするモデル (0 点率の違い)."""
    six = 6
    out: dict[str, dict[str, Any]] = {
        "all_equal": {"C": [BASE] * six},
        "one_diff_boundary": {"C": [BASE] * 5 + [BASE + st.DELTA_MIN]},
        "one_diff_2dmin": {"C": [BASE] * 5 + [BASE + st.PLAN_GAP]},
        "monotone": {"C": [round(0.2 + 0.08 * i, 10) for i in range(six)]},
        "family": {"C": [BASE] * 4 + [BASE + st.PLAN_GAP] * 2},
        "ties": {"C": [0.3, 0.3, 0.4, 0.4, 0.5, 0.5]},
        "zero_rate": {"C": [BASE] * six, "zero": [1, 3, 5]},
        "floor_all": {"C": [0.0] * six},
        "floor_one": {"C": [0.0] * 5 + [st.PLAN_GAP]},
        "ceiling_all": {"C": [0.97] * six},
        "negative": {"C": [-BASE] * 5 + [-BASE + st.PLAN_GAP]},
    }
    for m in (3, 4, 5):
        out[f"select_{m}"] = {"C": [BASE] * (m - 1) + [BASE + st.PLAN_GAP]}
    # 入場から最終判定まで (Codex r1 HIGH-2): pilot の入場集合で K を決め、
    # 本走で外れたモデルを除いて判定する
    out["drop_diff"] = {"C": [BASE] * 3 + [BASE + 0.3], "drop": [3]}
    out["drop_equal"] = {"C": [BASE] * 5 + [BASE + st.PLAN_GAP], "drop": [0]}
    out["drop_to_2"] = {"C": [BASE, BASE, BASE + st.PLAN_GAP], "drop": [2]}
    # 共通の lookup で 3 本だけが通る: 他の battery も最大 3 本 (K = 3·2 + 3·3·2 = 24。Codex r2 HIGH-1)
    out["lookup_3"] = {"C": [BASE, BASE, BASE + st.PLAN_GAP], "others": 3}
    # 登録した規則を試行ごとに当てる行 (Codex r2 HIGH-1): pilot の ⊥ 率 ≤ 0.2 で入場、
    # 本走の ⊥ 率 > min(0.2, pilot の ⊥ 率 + 0.05) で除外。⊥ のセルは 0 点 (得点と ⊥ が同じ出力から決まる)
    out["rule_bot_diff"] = {"C": [BASE] * 5 + [0.55], "bot": [0.0] * 5 + [0.19]}
    out["rule_bot_all"] = {"C": [BASE] * 5 + [0.55], "bot": [0.18] * 6}
    return out


def _engagement(c: float, h: float, e: float) -> float:
    return min(1.0, abs(c) + h + e)


def generate(
    battery: str,
    c: list[float],
    zero: list[int],
    h: float,
    e: float,
    coupling: str,
    r_main: int,
    rng: np.random.Generator,
    n_sims: int,
) -> np.ndarray:
    """(N, M, n) の単位の分子 (対の値の和、整数 ∈ [−n_p, n_p])."""
    n_p = PAIRS_PER_UNIT[battery]
    n = r_main * st.SPECS[battery].units_per_rep
    m_count = len(c)
    hh = min(h, 1.0 - max(abs(x) for x in c))  # |μ| ≤ 1 を保つ (天井の形)
    alt = np.where(np.arange(n) % 2 == 0, 1.0, -1.0)
    out = np.empty((n_sims, m_count, n), dtype=np.int64)
    shared_u = rng.random((n_sims, n, n_p)) if coupling == "crn" else None
    for mi, cm in enumerate(c):
        z = alt if coupling == "crn" else rng.permutation(alt)
        mu = cm + hh * z  # (n,)
        g = 1.0 if mi in zero else _engagement(cm, hh, e)
        p_plus = ((g + mu) / 2.0)[None, :, None]
        p_minus = ((g - mu) / 2.0)[None, :, None]
        u = shared_u if shared_u is not None else rng.random((n_sims, n, n_p))
        vals = (u < p_plus).astype(np.int64) - (u > 1.0 - p_minus).astype(np.int64)
        out[:, mi, :] = vals.sum(axis=2)
    return out


def generate_bot(
    battery: str,
    c: list[float],
    bot: list[float],
    h: float,
    e: float,
    coupling: str,
    r_main: int,
    rng: np.random.Generator,
    n_sims: int,
) -> tuple[np.ndarray, np.ndarray]:
    """generate と同じ模型で、対ごとに確率 b で ⊥ (その対の値 0) を入れる.

    返り値: (N, M, n) の分子と、(N, M) の本走の ⊥ の対の割合。⊥ を含めた真の C は (1 − b)·C。
    """
    n_p = PAIRS_PER_UNIT[battery]
    n = r_main * st.SPECS[battery].units_per_rep
    hh = min(h, 1.0 - max(abs(x) for x in c))
    alt = np.where(np.arange(n) % 2 == 0, 1.0, -1.0)
    out = np.empty((n_sims, len(c), n), dtype=np.int64)
    bot_frac = np.zeros((n_sims, len(c)))
    shared_u = rng.random((n_sims, n, n_p)) if coupling == "crn" else None
    for mi, cm in enumerate(c):
        z = alt if coupling == "crn" else rng.permutation(alt)
        mu = cm + hh * z
        g = _engagement(cm, hh, e)
        p_plus = ((g + mu) / 2.0)[None, :, None]
        p_minus = ((g - mu) / 2.0)[None, :, None]
        u = shared_u if shared_u is not None else rng.random((n_sims, n, n_p))
        vals = (u < p_plus).astype(np.int64) - (u > 1.0 - p_minus).astype(np.int64)
        mask = rng.random((n_sims, n, n_p)) < bot[mi]
        vals[mask] = 0
        out[:, mi, :] = vals.sum(axis=2)
        bot_frac[:, mi] = mask.mean(axis=(1, 2))
    return out, bot_frac


def _counts(num: np.ndarray, offset: int, width: int) -> np.ndarray:
    """(N, n) の整数から (N, width) の度数."""
    n_sims = num.shape[0]
    flat = (num + offset) + width * np.arange(n_sims)[:, None]
    return (
        np.bincount(flat.ravel(), minlength=n_sims * width)
        .reshape(n_sims, width)
        .astype(float)
    )


def batch_flags(
    battery: str, num: np.ndarray, k_tests: int, sum_m: int, r_main: int
) -> dict[str, np.ndarray]:
    """Stats の検定と同じ booleans を (N,) 本まとめて計算する."""
    n_p = PAIRS_PER_UNIT[battery]
    spec = st.SPECS[battery]
    main_r = list(range(spec.main_r0, spec.main_r0 + r_main))
    halves = st.half_labels(spec, main_r)
    m_count = num.shape[1]
    pairs = st.ordered_pairs(m_count)
    thr = math.log(1.0 / (st.ALPHA / k_tests))
    dvals = np.arange(-2 * n_p, 2 * n_p + 1) / n_p
    est, rep, equiv = [], [], []
    for a, b in pairs:
        d = num[:, a, :] - num[:, b, :]
        cnt = _counts(d, 2 * n_p, 4 * n_p + 1)
        est.append(st.log_e_lower(dvals, cnt, st.DELTA_MIN, -2.0) >= thr)
        equiv.append(st.log_e_lower(dvals, cnt, -st.EQUIV, -2.0) >= thr)
        h_ok = np.ones(num.shape[0], dtype=bool)
        for hv in (0, 1):
            h_ok &= d[:, halves == hv].mean(axis=1) / n_p > st.DELTA_MIN
        rep.append(h_ok)
    lvl = math.log(1.0 / (st.ALPHA / (2 * sum_m)))
    mvals = np.arange(-n_p, n_p + 1) / n_p
    floor = np.ones(num.shape[0], dtype=bool)
    ceil = np.ones(num.shape[0], dtype=bool)
    for mi in range(m_count):
        cnt = _counts(num[:, mi, :], n_p, 2 * n_p + 1)
        floor &= (st.log_e_lower(mvals, cnt, st.FLOOR_BAND[0], -1.0) >= lvl) & (
            st.log_e_upper(mvals, cnt, st.FLOOR_BAND[1], 1.0) >= lvl
        )
        ceil &= st.log_e_lower(mvals, cnt, st.CEILING_BAND[0], -1.0) >= lvl
    return {
        "est": np.stack(est, axis=1),
        "rep": np.stack(rep, axis=1),
        "equiv": np.stack(equiv, axis=1),
        "concentrated": floor | ceil,
    }


def point(
    battery: str,
    shape: dict[str, Any],
    noise: tuple[str, float, float, str],
    r_main: int,
    rng: np.random.Generator,
    n_sims: int = N_SIMS,
) -> dict[str, Any]:
    c_all = shape["C"]
    m_pilot = len(c_all)
    k_tests = m_pilot * (m_pilot - 1) + OTHER_BATTERIES * OTHER_ENTRANTS * (
        OTHER_ENTRANTS - 1
    )
    sum_m = m_pilot + OTHER_BATTERIES * OTHER_ENTRANTS
    if "bot" in shape:
        return _point_rules(battery, shape, noise, r_main, rng, n_sims)
    others = shape.get("others", OTHER_ENTRANTS)
    k_tests = m_pilot * (m_pilot - 1) + OTHER_BATTERIES * others * (others - 1)
    sum_m = m_pilot + OTHER_BATTERIES * others
    _, h, e, coupling = noise
    num_all = generate(
        battery, c_all, shape.get("zero", []), h, e, coupling, r_main, rng, n_sims
    )
    real_c = num_all.mean(axis=(0, 2)) / PAIRS_PER_UNIT[battery]
    calib = float(np.max(np.abs(real_c - np.array(c_all))))
    keep = [i for i in range(m_pilot) if i not in shape.get("drop", [])]
    c = [c_all[i] for i in keep]
    m_count = len(c)
    base = {
        "K": k_tests,
        "sum_M": sum_m,
        "reported_models": m_count,
        "max_calibration_err": calib,
    }
    if m_count < st.MIN_ENTRANTS:
        return {
            **base,
            "P1": 0.0,
            "P2": 0.0,
            "P3": 0.0,
            "P_not_qualified": 1.0,
            "P1_pair": None,
            "false_establish": 0,
            "false_negative": 0,
            "negative_size_applies": False,
            "concentrated": 0.0,
            **_bounds(0, 0, 0, 0, n_sims),
        }
    num = num_all[:, keep, :]
    fl = batch_flags(battery, num, k_tests, sum_m, r_main)
    verdict = st.classify(fl["est"], fl["rep"], fl["equiv"], fl["concentrated"])
    pairs = st.ordered_pairs(m_count)
    true_d = np.array([c[a] - c[b] for a, b in pairs])
    named = fl["est"] & fl["rep"] & (verdict == st.VERDICT_ESTABLISHED)[:, None]
    false_est = np.any(named & (true_d <= st.DELTA_MIN + 1e-12)[None, :], axis=1)
    max_abs = float(np.max(np.abs(true_d)))
    k1 = int(np.sum(verdict == st.VERDICT_ESTABLISHED))
    k2 = int(np.sum(verdict == st.VERDICT_NEGATIVE))
    applies = max_abs >= st.EQUIV - 1e-12
    fe = int(false_est.sum())
    fn = k2 if applies else 0
    pair_idx = int(np.argmax(true_d))  # 真の差が最大の順序対 (指定の一対)
    return {
        **base,
        "P1": k1 / n_sims,
        "P2": k2 / n_sims,
        "P3": 1.0 - (k1 + k2) / n_sims,
        "P_not_qualified": 0.0,
        "P1_pair": float(np.mean(named[:, pair_idx])) if max_abs > 0 else None,
        "false_establish": fe,
        "false_negative": fn,
        "negative_size_applies": applies,
        "concentrated": float(np.mean(fl["concentrated"])),
        **_bounds(k1, k2, fe, fn, n_sims),
    }


# arm の数と、arm あたりの呼び出し (pilot の R 12 の全体 / 本走の 1 replicate)。v2 は C0 を含む 5 arm
ARMS: Final[dict[str, int]] = {"v2": 5, "v3": 4, "G": 4, "O_time": 4}
ARM_CALLS: Final[dict[str, tuple[int, int]]] = {
    "v2": (720, 60),
    "v3": (360, 30),
    "G": (288, 24),
    "O_time": (144, 12),
}


def qualify_arms(k: np.ndarray, n: int) -> tuple[bool, Fraction]:
    """資格の規則は stats の凍結の関数をそのまま呼ぶ (見取り図と pilot gate で 1 つ、Codex r4 HIGH-1)."""
    return st.parse_rule([int(x) for x in k], n)


def _k_sum(m_pilot: int) -> tuple[int, int]:
    k = m_pilot * (m_pilot - 1) + OTHER_BATTERIES * OTHER_ENTRANTS * (
        OTHER_ENTRANTS - 1
    )
    return k, m_pilot + OTHER_BATTERIES * OTHER_ENTRANTS


def _point_rules(
    battery: str,
    shape: dict[str, Any],
    noise: tuple[str, float, float, str],
    r_main: int,
    rng: np.random.Generator,
    n_sims: int,
) -> dict[str, Any]:
    """登録した資格・除外の規則を試行ごとに当て、入場集合で K を、報告集合で誤りを数える."""
    c_raw = shape["C"]
    bot = shape["bot"]
    m_all = len(c_raw)
    _, h, e, coupling = noise
    num, _ = generate_bot(battery, c_raw, bot, h, e, coupling, r_main, rng, n_sims)
    # 選別の前の較正: 全試行のモデル別の実現平均と (1 − b)·C (Codex r3 MEDIUM-1)
    true_c = [(1.0 - b) * cv for cv, b in zip(c_raw, bot, strict=True)]
    real_c = num.mean(axis=(0, 2)) / PAIRS_PER_UNIT[battery]
    calib = float(np.max(np.abs(real_c - np.array(true_c))))
    # 資格と除外は arm 別の ⊥ の数で当てる (Codex r3 HIGH-1): 得点の ⊥ と同じ確率 b で、
    # arm ごとの呼び出しの数の二項から引く (どの出力が ⊥ かと得点の結び付きは率だけを共有する)
    n_arm_p, n_arm_m = ARM_CALLS[battery]
    n_arm_m *= r_main
    n_arms = ARMS[battery]
    entered = np.zeros((n_sims, m_all), dtype=bool)
    reported = np.zeros((n_sims, m_all), dtype=bool)
    for mi, b in enumerate(bot):
        kp = rng.binomial(n_arm_p, b, size=(n_sims, n_arms))
        km = rng.binomial(n_arm_m, b, size=(n_sims, n_arms))
        for t in range(n_sims):
            ok, env = qualify_arms(kp[t], n_arm_p)
            entered[t, mi] = ok
            reported[t, mi] = ok and not st.envelope_exceeded(km[t], n_arm_m, env)
    counts = {"P1": 0, "P2": 0, "P3": 0, "NQ": 0, "fe": 0, "fn": 0}
    m_entered_sum = 0
    k_counts: dict[tuple[int, int], int] = {}
    groups: dict[tuple[tuple[bool, ...], tuple[bool, ...]], list[int]] = {}
    for t in range(n_sims):
        groups.setdefault((tuple(entered[t]), tuple(reported[t])), []).append(t)
    for (ent, rep), idx in sorted(groups.items()):
        m_p = sum(ent)
        m_entered_sum += m_p * len(idx)
        keep = [i for i in range(m_all) if rep[i]]
        if m_p < st.MIN_ENTRANTS or len(keep) < st.MIN_ENTRANTS:
            counts["NQ"] += len(idx)
            continue
        k_tests, sum_m = _k_sum(m_p)
        k_counts[(k_tests, sum_m)] = k_counts.get((k_tests, sum_m), 0) + len(idx)
        sub_num = num[np.array(idx)][:, keep, :]
        fl = batch_flags(battery, sub_num, k_tests, sum_m, r_main)
        verdict = st.classify(fl["est"], fl["rep"], fl["equiv"], fl["concentrated"])
        pairs = st.ordered_pairs(len(keep))
        cs = [true_c[i] for i in keep]
        true_d = np.array([cs[a] - cs[b] for a, b in pairs])
        named = fl["est"] & fl["rep"] & (verdict == st.VERDICT_ESTABLISHED)[:, None]
        counts["fe"] += int(
            np.any(named & (true_d <= st.DELTA_MIN + 1e-12)[None, :], axis=1).sum()
        )
        k2 = int(np.sum(verdict == st.VERDICT_NEGATIVE))
        if float(np.max(np.abs(true_d))) >= st.EQUIV - 1e-12:
            counts["fn"] += k2
        counts["P1"] += int(np.sum(verdict == st.VERDICT_ESTABLISHED))
        counts["P2"] += k2
        counts["P3"] += int(np.sum(verdict == st.VERDICT_INCONCLUSIVE))
    k_ref, sum_ref = _k_sum(m_all)
    return {
        "K": k_ref,  # 上限 (全候補が入場した場合)。実際に使った値は K_counts
        "sum_M": sum_ref,
        "K_counts": {f"{k},{sm}": v for (k, sm), v in sorted(k_counts.items())},
        "reported_models": float(reported.sum(axis=1).mean()),
        "mean_entered": m_entered_sum / n_sims,
        "max_calibration_err": calib,
        "P1": counts["P1"] / n_sims,
        "P2": counts["P2"] / n_sims,
        "P3": counts["P3"] / n_sims,
        "P_not_qualified": counts["NQ"] / n_sims,
        "P1_pair": None,
        "false_establish": counts["fe"],
        "false_negative": counts["fn"],
        "negative_size_applies": True,
        "concentrated": None,
        **_bounds(counts["P1"], counts["P2"], counts["fe"], counts["fn"], n_sims),
    }


def _bounds(k1: int, k2: int, fe: int, fn: int, n: int) -> dict[str, float]:
    """端点でも読める二項の片側 95% の限界 (Clopper-Pearson、Codex r1 MEDIUM-2)."""
    return {
        "P1_lower95": 1.0 - st.binom_upper(n - k1, n),
        "P1_upper95": st.binom_upper(k1, n),
        "P2_upper95": st.binom_upper(k2, n),
        "false_establish_upper95": st.binom_upper(fe, n),
        "false_negative_upper95": st.binom_upper(fn, n),
    }


def detection_prob(n: int, x: int, p: float) -> float:
    """MC の検査が、真の誤り率 p の点を不合格 (X > x) にする確率 (正確な二項の和)."""
    terms = [
        math.lgamma(n + 1)
        - math.lgamma(i + 1)
        - math.lgamma(n - i + 1)
        + i * math.log(p)
        + (n - i) * math.log1p(-p)
        for i in range(x + 1)
    ]
    mx = max(terms)
    return 1.0 - math.exp(mx) * sum(math.exp(t - mx) for t in terms)


def _seed(*parts: str) -> int:
    h = hashlib.sha256("|".join((str(SIM_SEED), *parts)).encode()).digest()
    return int.from_bytes(h[:8], "little")


def sketch(n_sims: int = N_SIMS) -> dict[str, Any]:
    rows = []
    for battery in st.BATTERIES:
        for r_main in R_GRID[battery]:
            for sname, shape in shapes().items():
                for noise in NOISE:
                    rng = np.random.default_rng(
                        _seed(battery, str(r_main), sname, noise[0])
                    )
                    res = point(battery, shape, noise, r_main, rng, n_sims)
                    rows.append(
                        {
                            "battery": battery,
                            "R": r_main,
                            "shape": sname,
                            "noise": noise[0],
                            **res,
                        }
                    )
    n_size = sum(1 for r in rows) * 2
    acc = st.binom_accept_max(n_sims, st.ALPHA, n_size)
    size_ok = all(
        r["false_establish"] <= acc and r["false_negative"] <= acc for r in rows
    )
    door = {}
    for battery in st.BATTERIES:
        best = [
            r
            for r in rows
            if r["battery"] == battery
            and r["shape"] == "one_diff_2dmin"
            and r["noise"] == NOISE[0][0]
        ]
        top = max(best, key=lambda r: r["R"])
        door[battery] = {
            "R": top["R"],
            "P1": top["P1"],
            "P1_pair": top["P1_pair"],
            "reaches_power": top["P1_pair"] >= st.POWER,
            "hours_8b": float(top["R"] * st.SPECS[battery].sec_per_rep() / 3600),
        }
    return {
        "params": {
            "alpha": st.ALPHA,
            "delta_min": st.DELTA_MIN,
            "equiv": st.EQUIV,
            "lambda_c": [float(x) for x in st.LAMBDA_C],
            "n_sims": n_sims,
            "sim_seed": SIM_SEED,
            "r_grid": {k: list(v) for k, v in R_GRID.items()},
            "noise": [list(n) for n in NOISE],
            "pairs_per_unit": PAIRS_PER_UNIT,
            "units_per_rep": {k: v.units_per_rep for k, v in st.SPECS.items()},
            "k_tests_assumed": "M_p*(M_p-1) + 3*6*5",
            "sum_m_assumed": "M_p + 3*6",
            "shapes": shapes(),
        },
        "size_accept_max": acc,
        "mc_detection": {
            str(p): detection_prob(n_sims, acc, p) for p in (0.075, 0.10, 0.15)
        },
        "size_points": n_size,
        "size_ok": size_ok,
        "door_close": door,
        "door_close_any": not all(d["reaches_power"] for d in door.values()),
        "rows": rows,
    }


# ------------------------------------------------------------ fixture の差の点検 (§I)

FIXTURE_SOURCES: Final[dict[str, str]] = {
    "G": "experiments/20261001-generalization-probe-pilot/results/fixture_table.json",
    "O_time": "experiments/20261008-o-time-probe-pilot/results/fixture_table.json",
}
# v2・v3 は fixture の表の JSON を持たない。各 prereg の表の値を写す (出典の節を併記)。
FIXTURE_LITERAL: Final[dict[str, dict[str, Any]]] = {
    "v2": {
        "source": "experiments/20260926-skill-lever-pilot/prereg.md §2 (登録 nuisance class は合成 fixture で 0)",
        "policies": {
            "priming": 0.0,
            "label_prior": 0.0,
            "position": 0.0,
            "recency_last_entry": 0.0,
            "positive_control_rule_lookup": 1.0,
        },
    },
    "v3": {
        "source": "experiments/20260926-experience-skill-pilot/prereg.md §2.5 の表 (R = 8)",
        "policies": {
            "outcome_blind": 0.0,
            "most_success_label": 0.0,
            "first_or_last_success_row": 0.0,
            "row_after_success": -1.0 / 12.0,
            "row_before_success": 1.0 / 12.0,
            "nearest_neighbor_ignoring_weather": -1.0,
            "positive_control_weather_match": 1.0,
        },
    },
}


def fixture_diffs(root: Path = _REPO_ROOT) -> dict[str, Any]:
    out: dict[str, Any] = {"delta_min": st.DELTA_MIN, "batteries": {}}
    for battery in st.BATTERIES:
        if battery in FIXTURE_SOURCES:
            path = root / FIXTURE_SOURCES[battery]
            raw = path.read_bytes()
            table = json.loads(raw.decode("utf-8"))
            tabs = table["tables"]
            key = max(tabs, key=lambda k: tabs[k]["R"])
            pol = {k: float(v["C"]) for k, v in tabs[key]["policies"].items()}
            src = {
                "path": FIXTURE_SOURCES[battery],
                "sha256": hashlib.sha256(raw).hexdigest(),
                "table": key,
            }
        else:
            pol = dict(FIXTURE_LITERAL[battery]["policies"])
            src = {"path": FIXTURE_LITERAL[battery]["source"]}
        names = sorted(pol)
        big = [
            {"high": a, "low": b, "diff": pol[a] - pol[b]}
            for a in names
            for b in names
            if pol[a] - pol[b] > st.DELTA_MIN + 1e-12
        ]
        out["batteries"][battery] = {
            "source": src,
            "n_policies": len(names),
            "max_abs_C": max(abs(v) for v in pol.values()),
            "pairs_over_delta_min": big,
            "nuisance_pairs_over_delta_min": [
                q
                for q in big
                if not q["high"].startswith("positive_control")
                and not q["low"].startswith("positive_control")
            ],
        }
    return out


def render(sk: dict[str, Any], fx: dict[str, Any]) -> tuple[str, str]:
    """Prereg §I.2・§I.3 の表を JSON から機械的に作る (判定に使わない)."""
    rows = sk["rows"]
    lines = [
        f"**条件**: `results/sketch.json` (2 回の独立な実行で byte 一致)。N = {sk['params']['n_sims']}、"
        f"size の点 G = {sk['size_points']}、MC の採否 x = {sk['size_accept_max']} (率 {sk['size_accept_max'] / sk['params']['n_sims']:.4f})。",
        f"size の採否: {'全点で合格' if sk['size_ok'] else '不合格の点がある'}。door-close: {'あり' if sk['door_close_any'] else 'なし'}。",
        "",
        "**表 1**: 止める条件 (最も有利な行 = 低・crn、1 モデルだけ +0.20、格子の最大の R)。",
        "",
        "| battery | R | 単位 | P((1)) | P(指定の一対を名指す) | 到達 (指定の一対) | 8B 換算の時間 |",
        "|---|---|---|---|---|---|---|",
    ]
    for b, d in sk["door_close"].items():
        n_u = d["R"] * st.SPECS[b].units_per_rep
        lines.append(
            f"| {b} | {d['R']} | {n_u} | {d['P1']:.3f} | {d['P1_pair']:.3f} | {'○' if d['reaches_power'] else '×'} | {d['hours_8b']:.2f} h |"
        )
    lines += [
        "",
        "**表 2**: 1 モデルだけ +0.20 の P((1)) / P(指定の一対を名指す) (雑音の 6 行 × R)。",
        "",
        "| battery | R | " + " | ".join(n[0] for n in NOISE) + " |",
        "|---|---|" + "---|" * len(NOISE),
    ]
    for b in st.BATTERIES:
        for r in R_GRID[b]:
            cells = []
            for n in NOISE:
                row = next(
                    x
                    for x in rows
                    if x["battery"] == b
                    and x["R"] == r
                    and x["shape"] == "one_diff_2dmin"
                    and x["noise"] == n[0]
                )
                cells.append(f"{row['P1']:.3f} / {row['P1_pair']:.3f}")
            lines.append(f"| {b} | {r} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "**表 3**: 形ごとの P((1)) / P((2)) / P((3)) (各 battery の格子の最大の R、中・indep と低・crn)。"
        "「資格不足」は pilot の入場か本走の報告集合が 3 本未満 (§F-3) の率 (Codex r4 LOW-2)。",
        "",
        "| 形 | 雑音 | v2 | v3 | G | O_time |",
        "|---|---|---|---|---|---|",
    ]
    for s in shapes():
        for n in ("low_crn", "mid_indep"):
            cells = []
            for b in st.BATTERIES:
                row = next(
                    x
                    for x in rows
                    if x["battery"] == b
                    and x["R"] == R_GRID[b][-1]
                    and x["shape"] == s
                    and x["noise"] == n
                )
                if row["P_not_qualified"] == 1.0:
                    cells.append("資格不足")
                elif row["P_not_qualified"] > 0:
                    cells.append(
                        f"{row['P1']:.2f} / {row['P2']:.2f} / {row['P3']:.2f}"
                        f" (資格不足: {row['P_not_qualified']:.2f})"
                    )
                else:
                    cells.append(f"{row['P1']:.2f} / {row['P2']:.2f} / {row['P3']:.2f}")
            lines.append(f"| {s} | {n} | " + " | ".join(cells) + " |")
    worst_fe = max(rows, key=lambda x: x["false_establish"])
    worst_fn = max(rows, key=lambda x: x["false_negative"])
    calib = max(x["max_calibration_err"] for x in rows)
    ub_fe = max(x["false_establish_upper95"] for x in rows)
    ub_fn = max(x["false_negative_upper95"] for x in rows)
    det = ", ".join(f"p = {k}: {v:.3f}" for k, v in sk["mc_detection"].items())
    n = sk["params"]["n_sims"]
    lines += [
        "",
        f"**枝ごとの size**: (1) の誤った名指しの数の最大 {worst_fe['false_establish']} / {n} "
        f"({worst_fe['battery']}・R {worst_fe['R']}・{worst_fe['shape']}・{worst_fe['noise']})、"
        f"(2) の誤った否定の数の最大 {worst_fn['false_negative']} / {n} "
        f"({worst_fn['battery']}・R {worst_fn['R']}・{worst_fn['shape']}・{worst_fn['noise']})。"
        f"二項の片側 95% の上限 (Clopper-Pearson) の最大は、それぞれ {ub_fe:.4f}・{ub_fn:.4f}。",
        f"**MC の検査の検出力** (実装の異常を見つける検査。size の保証は §D の定理): 真の誤り率 p の点を不合格にする確率 {det}。",
        f"**模擬の較正**: 実現した C と目標の差の最大 {calib:.4f}。",
    ]
    flines = [
        "| battery | 方策の数 | 最大 \\|C\\| | \\|ΔC\\| > Δ_min の対 | 出典 |",
        "|---|---|---|---|---|",
    ]
    for b, d in fx["batteries"].items():
        pairs = d["nuisance_pairs_over_delta_min"]
        shown = "; ".join(
            f"{p['high']} − {p['low']} = {p['diff']:+.3f}" for p in pairs[:6]
        )
        more = f" ほか {len(pairs) - 6} 対" if len(pairs) > 6 else ""
        flines.append(
            f"| {b} | {d['n_policies']} | {d['max_abs_C']:.4f} | {len(pairs)} 対: {shown or 'なし'}{more} | `{d['source']['path']}` |"
        )
    return "\n".join(lines), "\n".join(flines)


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    path.write_bytes(text.encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n-sims", type=int, default=N_SIMS)
    args = ap.parse_args(argv)
    write_json(args.out / "fixture_diffs.json", fixture_diffs())
    sk = sketch(args.n_sims)
    write_json(args.out / "sketch.json", sk)
    print(
        json.dumps(
            {"door_close": sk["door_close"], "size_ok": sk["size_ok"]},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
