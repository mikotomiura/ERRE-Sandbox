"""候補 O_time (時期の評価) — 見取り図 (判定に使わない) と R の選定 (prereg §7、計測台 ADR §4.3).

凍結した判定式 (``o_time_probe_scorer`` の e-value・``decide``・⊥ gate) を、凍結した設計 (単位・書き方の対・表示順・並び) の上で
合成の選択に当てる。効果の形は scoping ADR §5.2 の型を O_time の単位で書いたものと、帰無の領域の非対称な分布。

生成の模型 (prereg §7.1、G prereg §7.1 を継ぐ):

* セル = (単位 u, 書き方 e, arm a)、K = 1。⊥ は確率 b。残りの質量で、確率 |λ| で w (λ > 0) か foil (λ < 0) を選び、
  それ以外は base (Ω = 族の 3 label と OOΩ 5%) から引く。混合の形では E[C] = (1 − b) · E[λ]。ただし時系列の表示でだけ
  評価する形 (``chrono_only``) は λ を一部の arm にだけ置くので、E[C] = (1 − b) · L · F (F = ``chrono_factor``、到達上限は (1 − b) · F)。
* 結合: ``crn`` = 単位の 4 セルで共通の一様乱数 (seed の共有の写し)、``indep`` = 独立、``anti`` = 書き方ごとに
  2 arm が u と 1 − u (⊥ も v と 1 − v)。
* 攪乱点 18 = base {uniform, label_skew (A 側の label に 0.7), position_skew (表示の先頭に 0.7)} × b {0, 0.1} × 結合 3。
* 対数オッズの形だけは混合でなく、base (label_skew に固定) の w の対数オッズに β を足す。E[C] は β で較正する。
* 項目単位の形 (項目 = (族, 部屋) の全か無か・逆向き) は、項目の数を厳密にして実現平均を目標に一致させる
  (帰無は固定した prompt の schedule に条件付ける)。

R の選定規則 (prereg §7.1・scoping ADR §7 の読み 5): 候補 {96, 192, 288} (1 回目の見取り図の後・実データの前に {24, 48, 72, 96} から
広げた。user 裁定 DU-2)。次の 4 条件をすべて満たす候補の
うち最大の R を R_MAIN とする。満たす候補が無ければ door-close。
1. 18 攪乱点で、一様 sd 0.05 / sd 0.3 の P(PASS | E[C] = 2τ) ≥ 0.8、対数オッズの形 (6 点) でも ≥ 0.8。
2. 18 攪乱点で、一様 sd 0.05 / sd 0.3 の P(NO_GO | E[C] = 0) ≥ 0.8。
3. 全形の境界 (E[C] = τ) と帰無の領域 (二点の極値・弱い null) で、両枝の棄却の数 X が合格 (X ≤ x)。
   size の上限は α (定理)。x は P(X > x) ≤ 0.01 / G を満たす最小の整数 (X ~ Binomial(N, α)、G = その R の size の点の数 × seed 数)。
4. crn の uniform・position_skew × ⊥ {0, 0.1} の 4 攪乱点で、一様 sd 0.05 / sd 0.3 について、E[C] = τ − 0.05 と τ + 0.05 の
   それぞれで、決着しない確率 1 − P(PASS) − P(NO_GO) ≤ 0.2 (label_skew の点は外した。user 裁定 DU-3)。
最も有利な行 (一様 sd 0.05・uniform・b 0・crn) が、どの R でも E[C] = 2τ の点で power 0.8 に届かなければ door-close。
模擬の健全性 (Codex HIGH-3): その R の全行・全 seed で、実現した C が目標から 0.01 以内 (``calibrated``)。満たさない R は選ばない
(混合の形の較正が崩れていれば、帰無の境界や帯を模擬したことにならない)。

実行 (repo root から、detached で)::

    uv run python scripts/o_time_probe_sim.py --out <sketch.json> --workers 12
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from statistics import NormalDist
from typing import Any, Final

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import o_time_probe_battery as bat  # noqa: E402
from scripts import o_time_probe_scorer as sc  # noqa: E402

R_CANDIDATES: Final[tuple[int, ...]] = (96, 192, 288)
GRID: Final[tuple[float, ...]] = tuple(round(0.025 * i, 3) for i in range(33))  # 0〜0.8
N_SIM_POWER: Final[int] = 2_000
N_SIM_SIZE: Final[int] = 10_000
SEEDS: Final[tuple[int, ...]] = (20261008, 20261009)
POWER_TARGET: Final[float] = 0.8
UNDECIDED_MAX: Final[float] = 0.2
CALIBRATION_TOL: Final[float] = (
    0.01  # 実現した C と目標の差の許容 (模擬の健全性、Codex HIGH-3)
)
BAND_DELTA: Final[float] = 0.05
MC_FWER: Final[float] = 0.01
CHUNK: Final[int] = 500  # 二点の極値の直接の確認 (配列が小さい)
CHUNK_UNIT_SIMS: Final[int] = 288_000  # 模擬の 1 回の配列の大きさ (模擬の数 × 単位の数)
OOV: Final[float] = 0.05
SKEW: Final[float] = 0.7

FORMS: Final[tuple[str, ...]] = (
    "homog_sd005",
    "homog_sd030",
    "sparse_1of3",
    "sparse_2of3",
    "asc_only",
    "chrono_only",
    "aon_cell",
    "aon_unit",
    "aon_arm_unit",
    "aon_item",
    "logodds",
    "reverse_1of6",
)
POWER_FORMS: Final[tuple[str, ...]] = ("homog_sd005", "homog_sd030", "logodds")
NO_GO_FORMS: Final[tuple[str, ...]] = ("homog_sd005", "homog_sd030")
BAND_FORMS: Final[tuple[str, ...]] = ("homog_sd005", "homog_sd030")
BAND_BASES: Final[tuple[str, ...]] = ("uniform", "position_skew")  # user 裁定 DU-3
GAUSS_SD: Final[dict[str, float]] = {"homog_sd005": 0.05, "homog_sd030": 0.30}
SPARSE_ROOMS: Final[dict[str, int]] = {"sparse_1of3": 2, "sparse_2of3": 4}
REVERSE_FRACTION: Final[float] = 1.0 / 6.0
WEAK_NULL: Final[dict[str, float]] = {"p_up": 5.0 / 7.0, "up": 0.4, "down": -1.0}
PASS_EXTREMAL_M: Final[tuple[float, ...]] = (0.4, 0.6, 0.8, 1.0)
NO_GO_EXTREMAL_M: Final[tuple[float, ...]] = (-1.0, -0.5, 0.0, 0.2)
N_ITEMS: Final[int] = len(bat.FAMILIES) * bat.N_ROOMS


@dataclass(frozen=True)
class Nuisance:
    base: str  # "uniform" | "label_skew" | "position_skew"
    bot: float
    coupling: str  # "crn" | "indep" | "anti"


def nuisance_grid() -> tuple[Nuisance, ...]:
    return tuple(
        Nuisance(base, bot, coupling)
        for base in ("uniform", "label_skew", "position_skew")
        for bot in (0.0, 0.1)
        for coupling in ("crn", "indep", "anti")
    )


FAVORABLE: Final[Nuisance] = Nuisance("uniform", 0.0, "crn")
ADVERSE: Final[Nuisance] = Nuisance("label_skew", 0.1, "anti")


# ------------------------------------------------------------ 設計の配列


@dataclass(frozen=True)
class Design:
    r_count: int
    unit_family: np.ndarray  # (U,)
    unit_room: np.ndarray  # (U,)
    position0: np.ndarray  # (U,) 表示先頭の label の、族の正準順での index
    a_side: np.ndarray  # (U,) A 側 (族の第 1 の規則) の label の正準 index
    b_side: np.ndarray  # (U,) B 側 (第 2 の規則) の label の正準 index
    a_first: np.ndarray  # (U,) その部屋の A 側の行が B 側の行より先に表示されるか
    w_idx: np.ndarray  # (U, 2) arm (0 = fwd、1 = bwd) の w の正準 index
    foil_idx: np.ndarray  # (U, 2)


@lru_cache(maxsize=8)
def design(r_count: int) -> Design:
    us = bat.units(r_count)
    fam = np.array([u.family for u in us])
    room = np.array([u.room for u in us])
    pos0 = np.array([(u.replicate + u.room) % bat.N_POSITIONS for u in us])
    a_side = room % 3
    b_side = (room + 1) % 3
    a_first = []
    for u in us:
        order = bat.entry_order(u.family, u.room, u.replicate)
        name = bat.ROOMS[u.room]
        pa = order.index((name, bat.first_rule_label(u.family, u.room)))
        pb = order.index((name, bat.second_rule_label(u.family, u.room)))
        a_first.append(pa < pb)
    w_idx = np.stack([b_side, a_side], axis=-1)
    foil_idx = np.stack([a_side, b_side], axis=-1)
    return Design(
        r_count, fam, room, pos0, a_side, b_side, np.array(a_first), w_idx, foil_idx
    )


def base_probs(dz: Design, base: str) -> np.ndarray:
    """(U, 4) = Ω の 3 label (族の正準順) と OOΩ の、⊥ 以外の質量の中の確率.

    label_skew は A 側の label (部屋の番号 mod 3) に 0.7、position_skew は表示の先頭に 0.7。
    """
    n_u = dz.unit_family.size
    live = 1.0 - OOV
    p = np.zeros((n_u, 4))
    if base == "uniform":
        p[:, :3] = live / 3.0
    else:
        target = dz.a_side if base == "label_skew" else dz.position0
        rest = (1.0 - SKEW) / 2.0
        p[:, :3] = live * rest
        p[np.arange(n_u), target] = live * SKEW
    p[:, 3] = OOV
    return p


# ------------------------------------------------------------ λ の形


def _clipped_normal_mean(mu: float, sd: float) -> float:
    nd = NormalDist()
    a, b = (-1.0 - mu) / sd, (1.0 - mu) / sd
    pa, pb = nd.cdf(a), nd.cdf(b)
    inside = mu * (pb - pa) + sd * (nd.pdf(a) - nd.pdf(b))
    return -1.0 * pa + inside + 1.0 * (1.0 - pb)


def _loc_for(target: float, sd: float) -> float:
    lo, hi = -3.0, 3.0
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if _clipped_normal_mean(mid, sd) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def base_gap(dz: Design, base: str) -> np.ndarray:
    """(U, 2) の g_a = base の w_a の確率 − foil_a の確率 (⊥ 以外の質量の中)。1 単位の 2 arm で g_fwd = −g_bwd."""
    p = base_probs(dz, base)  # (U, 4)
    pw = np.take_along_axis(p, dz.w_idx, axis=-1)
    pf = np.take_along_axis(p, dz.foil_idx, axis=-1)
    return pw - pf


def chrono_mask(dz: Design) -> np.ndarray:
    """(U, 2) その部屋の 2 行が古い順に表示される arm (fwd は A 側が先なら、bwd は B 側が先なら)."""
    return np.stack([dz.a_first, ~dz.a_first], axis=-1).astype(float)


def chrono_factor(dz: Design, base: str) -> float:
    """時系列の表示でだけ評価する形の較正係数 F = mean_u mean_a m_a (1 − g_a).

    セルの期待得点は g_a + L·m_a·(1 − g_a) で、g は 2 arm で打ち消すので E[C] = (1 − b)·L·F (Codex HIGH-3)。
    base が一様なら g = 0 で F = 0.5。偏った base では、凍結した並びの A 先 / B 先の割合で F が決まる。
    """
    return float(np.mean(chrono_mask(dz) * (1.0 - base_gap(dz, base))))


def reachable(form: str, nu: Nuisance, r_count: int) -> float:
    live = 1.0 - nu.bot
    if form in SPARSE_ROOMS:
        return live * SPARSE_ROOMS[form] / bat.N_ROOMS
    if form == "asc_only":
        return live * 0.5
    if form == "chrono_only":
        return live * chrono_factor(design(r_count), nu.base)
    if form == "reverse_1of6":
        return live * (1.0 - 2.0 * REVERSE_FRACTION)
    if form == "logodds":
        return live * (1.0 - OOV) * 0.999
    return live


def _cells(lam: np.ndarray, n: int, n_u: int) -> np.ndarray:
    return np.broadcast_to(lam, (n, n_u, 2, 2))


def lam_array(
    form: str, target: float, dz: Design, nu: Nuisance, n: int, rng: np.random.Generator
) -> np.ndarray:
    """(n, U, 2 書き方, 2 arm) の λ (混合の形)。E[C] = target になるよう較正 (chrono_only は (1 − b)·L·F、他は (1 − b)·E[λ])."""
    n_u = dz.unit_family.size
    t = target / (1.0 - nu.bot)
    if form in GAUSS_SD:
        sd = GAUSS_SD[form]
        e = _loc_for(t, sd) + sd * rng.standard_normal((n, n_u, 1, 2))
        return _cells(np.clip(e, -1.0, 1.0), n, n_u)
    if form in SPARSE_ROOMS:
        k = SPARSE_ROOMS[form]
        on = (dz.unit_room < k).astype(float)
        lam = min(1.0, t * bat.N_ROOMS / k)
        return _cells((lam * on)[None, :, None, None], n, n_u)
    if form == "asc_only":
        lam = np.zeros((1, 1, 2, 1))
        lam[0, 0, 0, 0] = min(1.0, 2.0 * t)
        return _cells(lam, n, n_u)
    if form == "chrono_only":
        # その部屋の 2 行が古い順に表示される arm でだけ評価する。注入量は凍結した並びの上で較正する
        lam = min(1.0, t / chrono_factor(dz, nu.base))
        return _cells(lam * chrono_mask(dz)[None, :, None, :], n, n_u)
    if form == "aon_cell":
        return (rng.random((n, n_u, 2, 2)) < t).astype(float)
    if form == "aon_unit":
        return _cells((rng.random((n, n_u, 1, 1)) < t).astype(float), n, n_u)
    if form == "aon_arm_unit":
        return _cells((rng.random((n, n_u, 1, 2)) < t).astype(float), n, n_u)
    if form == "aon_item":
        return _item_pattern(_exact_item_values(t, n, rng, low=0.0, high=1.0), dz, n)
    if form == "reverse_1of6":
        n_rev = round(N_ITEMS * REVERSE_FRACTION)
        kappa = (t * N_ITEMS + n_rev) / (N_ITEMS - n_rev)
        vals = np.full((n, N_ITEMS), kappa)
        vals[:, :n_rev] = -1.0
        return _item_pattern(rng.permuted(vals, axis=1), dz, n)
    if form == "weak_null":
        up = rng.random((n, n_u, 1, 1)) < WEAK_NULL["p_up"]
        return _cells(np.where(up, WEAK_NULL["up"], WEAK_NULL["down"]), n, n_u)
    if form.startswith(("pass_extremal_", "no_go_extremal_")):
        m = float(form.rsplit("_", 1)[1])
        other = -1.0 if form.startswith("pass") else 1.0
        p = (t - other) / (m - other)
        hit = rng.random((n, n_u, 1, 1)) < p
        return _cells(np.where(hit, m, other), n, n_u)
    msg = f"unknown form {form!r}"
    raise ValueError(msg)


def _exact_item_values(
    t: float, n: int, rng: np.random.Generator, low: float, high: float
) -> np.ndarray:
    """(n, 12) の項目の λ。値は low / high で、平均が厳密に t (端数は 1 項目に置く)。配置は無作為."""
    total = (t - low) * N_ITEMS / (high - low)
    k = int(math.floor(total + 1e-12))
    vals = np.full((n, N_ITEMS), low)
    vals[:, :k] = high
    if k < N_ITEMS:
        vals[:, k] = low + (total - k) * (high - low)
    return rng.permuted(vals, axis=1)


def _item_pattern(vals: np.ndarray, dz: Design, n: int) -> np.ndarray:
    """(n, 12) の項目の λ → (n, U, 2, 2)。項目 = (族, 部屋)."""
    grid = vals.reshape(n, len(bat.FAMILIES), bat.N_ROOMS)
    lam = grid[:, dz.unit_family, dz.unit_room]
    return _cells(lam[:, :, None, None], n, dz.unit_family.size)


def _logodds_probs(dz: Design, beta: float) -> np.ndarray:
    """(U, 2 arm, 4): label_skew の base の w の対数オッズに β を足した分布 (⊥ 以外の質量の中)."""
    base = base_probs(dz, "label_skew")
    p = np.repeat(base[:, None, :], 2, axis=1)
    boost = np.zeros_like(p)
    np.put_along_axis(boost, dz.w_idx[..., None], beta, axis=-1)
    q = p * np.exp(boost)
    q[..., :3] *= (1.0 - OOV) / q[..., :3].sum(axis=-1, keepdims=True)
    return q


def _expected_c_logodds(dz: Design, beta: float, bot: float) -> float:
    q = _logodds_probs(dz, beta)
    pw = np.take_along_axis(q, dz.w_idx[..., None], -1)
    pf = np.take_along_axis(q, dz.foil_idx[..., None], -1)
    return float((1.0 - bot) * np.mean(pw - pf))


def _beta_for(target: float, dz: Design, bot: float) -> float:
    lo, hi = 0.0, 30.0
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if _expected_c_logodds(dz, mid, bot) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


# ------------------------------------------------------------ 模擬


def _draw(
    cdf: np.ndarray, nu: Nuisance, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """累積分布 cdf (n, U, 2, 2, 4) から outcome index (n, U, 2, 2) と ⊥ (n, U, 2, 2) を引く (結合に従う)."""
    shape = cdf.shape[:-1]
    if nu.coupling == "crn":
        # 単位の 4 セルで共通 (seed の共有の写し)
        u = np.broadcast_to(rng.random((*shape[:2], 1, 1)), shape)
        v = np.broadcast_to(rng.random((*shape[:2], 1, 1)), shape)
    elif nu.coupling == "anti":
        u0 = rng.random((*shape[:3], 1))
        v0 = rng.random((*shape[:3], 1))
        u = np.concatenate([u0, 1.0 - u0], axis=-1)
        v = np.concatenate([v0, 1.0 - v0], axis=-1)
    else:
        u = rng.random(shape)
        v = rng.random(shape)
    idx = np.minimum((cdf < u[..., None]).sum(axis=-1), cdf.shape[-1] - 1)
    return idx, v < nu.bot


def _verdicts_chunk(
    form: str,
    target: float,
    dz: Design,
    nu: Nuisance,
    n: int,
    rng: np.random.Generator,
    beta: float | None,
) -> tuple[np.ndarray, np.ndarray]:
    w = dz.w_idx[:, None, :]  # (U, 1, 2) 書き方で共通
    foil = dz.foil_idx[:, None, :]
    n_u = dz.unit_family.size
    if form == "logodds":
        assert beta is not None
        q = np.cumsum(_logodds_probs(dz, beta), axis=-1)  # (U, 2, 4)
        cdf = np.broadcast_to(q[None, :, None, :, :], (n, n_u, 2, 2, 4))
    else:
        lam = lam_array(form, target, dz, nu, n, rng)  # (n, U, 2, 2)
        # 混合 (1 − |λ|)·base + |λ|·点 の累積分布 = (1 − |λ|)·cumsum(base) + |λ|·[k ≥ 点]
        # (確率の配列を作らずに組む。prereg §7.1 の模型と同じ分布)
        cdf_base = np.cumsum(base_probs(dz, nu.base), axis=-1)[None, :, None, None, :]
        mix = np.abs(lam)[..., None]
        tgt = np.where(lam > 0, w[None], foil[None])
        step = np.arange(4) >= tgt[..., None]
        cdf = (1.0 - mix) * cdf_base + mix * step
    idx, bot = _draw(cdf, nu, rng)
    score = (idx == w[None]).astype(float) - (idx == foil[None])
    score = np.where(bot, 0.0, score)  # (n, U, 2 書き方, 2 arm)
    d = score.mean(axis=(2, 3))  # (n, U) = D_u
    comps = np.stack(
        [score[:, :, e, a].mean(axis=1) for a in range(2) for e in range(2)], axis=1
    )  # COMPONENTS の順 (fwd asc, fwd ago, bwd asc, bwd ago)
    botr = np.stack(
        [
            bot[:, dz.unit_family == f][..., a].mean(axis=(1, 2))
            for f in range(len(bat.FAMILIES))
            for a in range(2)
        ],
        axis=1,
    )  # LEVER_ARMS の順 (AB, BA, CD, DC)
    le_plus, le_minus, _ = sc.e_values(d)
    verdict = sc.decide(le_plus, le_minus, comps)
    verdict = np.where(sc.bottom_gate_ok(botr), verdict, sc.VERDICT_INVALID_BATTERY)
    return verdict, d.mean(axis=1)


def chunk_size(n_units: int) -> int:
    """1 回に回す模擬の数。配列 (模擬 × 単位 × 4 セル × 4) の大きさを R に依らず抑える (worker のメモリ)."""
    return max(1, CHUNK_UNIT_SIMS // n_units)


def _tag(form: str, nu: Nuisance) -> tuple[int, ...]:
    h = hashlib.sha256(f"{form}|{nu.base}|{nu.bot}|{nu.coupling}".encode()).digest()
    return (int.from_bytes(h[:4], "little"),)


def simulate(
    form: str, target: float, r_count: int, nu: Nuisance, n_sims: int, seed: int
) -> dict[str, float]:
    dz = design(r_count)
    rng = np.random.default_rng(
        [seed, r_count, int(round(target * 10_000)), *_tag(form, nu)]
    )
    beta = _beta_for(target, dz, nu.bot) if form == "logodds" else None
    verdicts = []
    cs = []
    chunk = chunk_size(dz.unit_family.size)
    for start in range(0, n_sims, chunk):
        n = min(chunk, n_sims - start)
        v, c = _verdicts_chunk(form, target, dz, nu, n, rng, beta)
        verdicts.append(v)
        cs.append(c)
    verdict = np.concatenate(verdicts)
    out = {
        key: float(np.mean(verdict == key))
        for key in (
            sc.VERDICT_PASS,
            sc.VERDICT_ABSENT,
            sc.VERDICT_UNDERPOWERED,
            sc.VERDICT_INVALID_BATTERY,
        )
    }
    out["realized_C"] = float(np.mean(np.concatenate(cs)))
    return out


def pure_extremal_size(
    m: float, n_units: int, n_sims: int, seed: int, branch: str
) -> float:
    """単位 D を二点 {m, −1} (PASS 枝) / {m, +1} (NO_GO 枝) から直接引いたときの、その枝の棄却率 (定理の確認)."""
    rng = np.random.default_rng(
        [seed, n_units, int(round((m + 2) * 1000)), branch == "pass"]
    )
    other = -1.0 if branch == "pass" else 1.0
    p = (sc.TAU - other) / (m - other)
    rej = 0
    for start in range(0, n_sims, CHUNK):
        n = min(CHUNK, n_sims - start)
        d = np.where(rng.random((n, n_units)) < p, m, other)
        le_plus, le_minus, _ = sc.e_values(d)
        hit = le_plus if branch == "pass" else le_minus
        rej += int(np.count_nonzero(hit >= sc.LOG_THRESHOLD))
    return rej / n_sims


# ------------------------------------------------------------ 見取り図


def binom_upper_tail(x: int, n: int, p: float) -> float:
    """P(X ≥ x)、X ~ Binomial(n, p)。log 空間で正確に足す."""
    if x <= 0:
        return 1.0
    logs = [
        math.lgamma(n + 1)
        - math.lgamma(k + 1)
        - math.lgamma(n - k + 1)
        + k * math.log(p)
        + (n - k) * math.log1p(-p)
        for k in range(x, n + 1)
    ]
    top = max(logs)
    return math.exp(top) * sum(math.exp(v - top) for v in logs)


def size_count_threshold(n_checks: int, n_sims: int = N_SIM_SIZE) -> int:
    """合格の上限 x (棄却の数): 合格は X ≤ x、棄却は X ≥ x + 1.

    x は P(X > x) ≤ MC_FWER / n_checks を満たす最小の整数 (X ~ Binomial(n_sims, α))。
    """
    level = MC_FWER / n_checks
    x = int(sc.ALPHA * n_sims)
    while binom_upper_tail(x + 1, n_sims, sc.ALPHA) > level:
        x += 1
    return x


def mc_tolerance(n_checks: int, n_sims: int = N_SIM_SIZE) -> float:
    """率に直した MC 許容 = 閾値 / N − α (報告用。採否は ``size_count_threshold`` の整数で行う)."""
    return size_count_threshold(n_checks, n_sims) / n_sims - sc.ALPHA


def size_points() -> list[tuple[str, float, str]]:
    """(形, 目標 E[C], 見る枝)。境界 τ の全形 (両枝)・弱い null・二点の極値."""
    pts = [(form, sc.TAU, br) for form in FORMS for br in ("pass", "no_go")]
    pts.append(("weak_null", 0.0, "pass"))
    pts += [(f"pass_extremal_{m}", sc.TAU, "pass") for m in PASS_EXTREMAL_M]
    pts += [(f"no_go_extremal_{m}", sc.TAU, "no_go") for m in NO_GO_EXTREMAL_M]
    return pts


def _nuisances_for(form: str) -> tuple[Nuisance, ...]:
    if form == "logodds":
        return tuple(nu for nu in nuisance_grid() if nu.base == "label_skew")
    return nuisance_grid()


def band_points() -> list[tuple[str, float, Nuisance]]:
    """条件 4 の点: 一様 2 形 × crn の uniform・position_skew の 4 攪乱点 × E[C] = τ ± δ.

    label_skew の点は外す (user 裁定 DU-3): そこでは fwd の成分の期待値が E[C] = 0.35 で 0.0104 しかない。一様の形の crn では
    fwd の 2 成分 (asc・ago) の標本平均が同一なので、条件は 1 つの事象で、P(fwd の標本平均 > 0) は三項分布の数え上げで
    R 288 で 0.740、0.8 に届くのは R ≈ 490 (有限標本の power と費用の判断。Codex MEDIUM-5、2 周目 MEDIUM-3 で数え直した)。
    外した点は ``band_diag_points`` として計算し、記述にだけ使う。
    """
    return [
        (form, round(sc.TAU + sgn * BAND_DELTA, 3), nu)
        for form in BAND_FORMS
        for nu in nuisance_grid()
        if nu.coupling == "crn" and nu.base in BAND_BASES
        for sgn in (-1.0, 1.0)
    ]


def band_diag_points() -> list[tuple[str, float, Nuisance]]:
    """条件 4 から外した crn の label_skew の点 (診断用。選定に使わない、Codex MEDIUM-5)."""
    return [
        (form, round(sc.TAU + sgn * BAND_DELTA, 3), nu)
        for form in BAND_FORMS
        for nu in nuisance_grid()
        if nu.coupling == "crn" and nu.base not in BAND_BASES
        for sgn in (-1.0, 1.0)
    ]


def _point(args: tuple[str, float, int, Nuisance, int]) -> list[dict[str, float]]:
    form, target, r_count, nu, n_sims = args
    return [simulate(form, target, r_count, nu, n_sims, s) for s in SEEDS]


def _pure(args: tuple[float, int, int, str]) -> float:
    m, n_units, n_sims, branch = args
    return max(pure_extremal_size(m, n_units, n_sims, s, branch) for s in SEEDS)


def plan_r(r_count: int) -> list[tuple[str, str, float, Nuisance, int]]:
    """1 つの R の点の計画 (kind, form, target, nu, n_sims)。順序は固定 (出力の byte 一致のため)."""
    out: list[tuple[str, str, float, Nuisance, int]] = []
    for form in POWER_FORMS:
        out += [
            ("power_pass", form, sc.DELTA_PLANT, nu, N_SIM_POWER)
            for nu in _nuisances_for(form)
        ]
    for form in NO_GO_FORMS:
        out += [("power_no_go", form, 0.0, nu, N_SIM_POWER) for nu in nuisance_grid()]
    out += [
        ("band", form, target, nu, N_SIM_POWER) for form, target, nu in band_points()
    ]
    out += [
        ("band_diag", form, target, nu, N_SIM_POWER)
        for form, target, nu in band_diag_points()
    ]
    for form, target, branch in size_points():
        out += [
            (f"size_{branch}", form, target, nu, N_SIM_SIZE)
            for nu in _nuisances_for(form)
        ]
    return out


def judge_r(
    r_count: int, rows: list[dict[str, Any]], pure: dict[str, float]
) -> dict[str, Any]:
    """1 つの R の行から、選定規則の 4 条件と模擬の較正を計算する (manifest は独立に再計算する)."""
    power_ok = True
    no_go_ok = True
    band_ok = True
    size_rows = []
    calibrated = all(
        abs(p["realized_C"] - row["target_C"]) <= CALIBRATION_TOL
        for row in rows
        for p in row["per_seed"]
    )
    for row in rows:
        ps = row["per_seed"]
        if row["kind"] == "band_diag":
            row["value"] = float(
                np.mean([1.0 - p[sc.VERDICT_PASS] - p[sc.VERDICT_ABSENT] for p in ps])
            )
        elif row["kind"] == "power_pass":
            row["value"] = float(np.mean([p[sc.VERDICT_PASS] for p in ps]))
            power_ok &= row["value"] >= POWER_TARGET
        elif row["kind"] == "power_no_go":
            row["value"] = float(np.mean([p[sc.VERDICT_ABSENT] for p in ps]))
            no_go_ok &= row["value"] >= POWER_TARGET
        elif row["kind"] == "band":
            row["value"] = float(
                np.mean([1.0 - p[sc.VERDICT_PASS] - p[sc.VERDICT_ABSENT] for p in ps])
            )
            band_ok &= row["value"] <= UNDECIDED_MAX
        else:
            key = sc.VERDICT_PASS if row["kind"] == "size_pass" else sc.VERDICT_ABSENT
            row["value"] = float(max(p[key] for p in ps))
            size_rows.append(row)
    n_checks = len(size_rows) * len(SEEDS)
    x = size_count_threshold(n_checks)
    size_ok = all(round(r["value"] * N_SIM_SIZE) <= x for r in size_rows)
    return {
        "R": r_count,
        "n_units": len(bat.units(r_count)),
        "calls": len(bat.units(r_count)) * 4 * sc.FROZEN_K,
        "power_ok": bool(power_ok),
        "no_go_ok": bool(no_go_ok),
        "band_ok": bool(band_ok),
        "size_ok": bool(size_ok),
        "calibrated": bool(calibrated),
        "size_count_threshold": x,
        "size_cap": x / N_SIM_SIZE,
        "mc_tolerance": x / N_SIM_SIZE - sc.ALPHA,
        "n_size_checks": n_checks,
        "worst_size": max(r["value"] for r in size_rows),
        "pure_extremal_size": pure,
        "rows": rows,
    }


def sweep_plan(r_count: int) -> list[tuple[str, float, Nuisance, float]]:
    """形ごとの E[C] 掃引 (有利・不利の 2 攪乱点)。境目を読むための表 (判定に使わない)."""
    out = []
    for form in FORMS:
        for nu0 in (FAVORABLE, ADVERSE):
            nu = (
                Nuisance("label_skew", nu0.bot, nu0.coupling)
                if form == "logodds"
                else nu0
            )
            reach = reachable(form, nu, r_count)
            out += [(form, c, nu, reach) for c in GRID if c <= reach + 1e-9]
    return out


def boundary(points: list[tuple[float, float]], *, rising: bool = True) -> float | None:
    """P が 0.8 を越える E[C] (rising) / P が 0.8 を下回る E[C] (falling) を線形補間。無ければ None."""
    pts = sorted(points)
    for (c0, p0), (c1, p1) in zip(pts, pts[1:], strict=False):
        if rising and p0 < POWER_TARGET <= p1:
            return c0 + (POWER_TARGET - p0) * (c1 - c0) / (p1 - p0)
        if not rising and p0 >= POWER_TARGET > p1:
            return c0 + (p0 - POWER_TARGET) * (c1 - c0) / (p0 - p1)
    if rising and pts and pts[0][1] >= POWER_TARGET:
        return pts[0][0]
    return None


def select(per_r: list[dict[str, Any]]) -> dict[str, Any]:
    """選定規則 (docstring)。4 条件を満たし、模擬が較正されている候補のうち最大。無ければ door-close."""
    ok = [
        res["R"]
        for res in per_r
        if res["power_ok"]
        and res["no_go_ok"]
        and res["size_ok"]
        and res["band_ok"]
        and res["calibrated"]
    ]
    if not ok:
        return {"selected_R": None, "door_close": True}
    return {"selected_R": max(ok), "door_close": False}


def most_favorable_reaches(sweeps: list[dict[str, Any]]) -> bool:
    """最も有利な行 (一様 sd 0.05・FAVORABLE) が、どれかの R で 2τ に到達でき、power 0.8 に届くか."""
    return any(
        r["form"] == "homog_sd005"
        and (r["base"], r["bot"], r["coupling"])
        == (FAVORABLE.base, FAVORABLE.bot, FAVORABLE.coupling)
        and abs(r["target_C"] - sc.DELTA_PLANT) < 1e-9
        and r["pass"] >= POWER_TARGET
        for r in sweeps
    )


def sweep_boundaries(
    sweeps: list[dict[str, Any]], r_values: list[int]
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for r in r_values:
        out[f"R{r}"] = {}
        for form in FORMS:
            out[f"R{r}"][form] = {}
            for kind, nu0 in (("favorable", FAVORABLE), ("adverse", ADVERSE)):
                base = "label_skew" if form == "logodds" else nu0.base
                rows = [
                    x
                    for x in sweeps
                    if x["R"] == r
                    and x["form"] == form
                    and (x["base"], x["bot"], x["coupling"])
                    == (base, nu0.bot, nu0.coupling)
                ]
                out[f"R{r}"][form][kind] = {
                    "pass_08": boundary([(x["target_C"], x["pass"]) for x in rows]),
                    "no_go_08": boundary(
                        [(x["target_C"], x["no_go"]) for x in rows], rising=False
                    ),
                }
    return out


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def params() -> dict[str, Any]:
    return {
        "R_candidates": list(R_CANDIDATES),
        "grid": list(GRID),
        "n_sim_power": N_SIM_POWER,
        "n_sim_size": N_SIM_SIZE,
        "seeds": list(SEEDS),
        "tau": sc.TAU,
        "alpha": sc.ALPHA,
        "delta_plant": sc.DELTA_PLANT,
        "power_target": POWER_TARGET,
        "undecided_max": UNDECIDED_MAX,
        "calibration_tol": CALIBRATION_TOL,
        "band_delta": BAND_DELTA,
        "band_bases": list(BAND_BASES),
        "mc_fwer": MC_FWER,
        "oov": OOV,
        "skew": SKEW,
        "lambda_fractions": list(sc.LAMBDA_FRACTIONS),
        "weak_null": WEAK_NULL,
        "reverse_fraction": REVERSE_FRACTION,
    }


def run(r_values: list[int], workers: int, log: Any = None) -> dict[str, Any]:
    # 結び付ける sha256 は計算の前に読む (長い計算の間にファイルが変わっても、使ったコードの値を残す)
    bound = {k: _sha256(v) for k, v in sc.certified_targets().items()}
    plans = {r: plan_r(r) for r in r_values}
    sweeps_plan = {r: sweep_plan(r) for r in r_values}
    jobs: list[tuple[str, float, int, Nuisance, int]] = []
    for r in r_values:
        jobs += [(form, target, r, nu, n) for _, form, target, nu, n in plans[r]]
        jobs += [(form, c, r, nu, N_SIM_POWER) for form, c, nu, _ in sweeps_plan[r]]
    pure_jobs = [
        (m, len(bat.units(r)), N_SIM_SIZE, branch)
        for r in r_values
        for branch, ms in (("pass", PASS_EXTREMAL_M), ("no_go", NO_GO_EXTREMAL_M))
        for m in ms
    ]
    if workers <= 1:
        # 逐次 (test が simulate を差し替えられる経路。結果は並列と同じ: 点ごとに乱数が独立)
        results = [_point(job) for job in jobs]
        pure_vals = [_pure(job) for job in pure_jobs]
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(_point, jobs, chunksize=1))
            pure_vals = list(ex.map(_pure, pure_jobs, chunksize=1))
    it = iter(results)
    pit = iter(pure_vals)
    per_r = []
    sweeps = []
    for r in r_values:
        rows = []
        for kind, form, target, nu, _ in plans[r]:
            rows.append(
                {
                    "kind": kind,
                    "R": r,
                    "form": form,
                    "target_C": target,
                    **asdict(nu),
                    "per_seed": next(it),
                }
            )
        for form, c, nu, reach in sweeps_plan[r]:
            ps = next(it)
            row = {
                "R": r,
                "form": form,
                "target_C": c,
                **asdict(nu),
                "reachable": reach,
                "pass": float(np.mean([p[sc.VERDICT_PASS] for p in ps])),
                "no_go": float(np.mean([p[sc.VERDICT_ABSENT] for p in ps])),
                "per_seed": ps,
            }
            sweeps.append(row)
        pure = {
            f"{branch}_{m}": next(pit)
            for branch, ms in (("pass", PASS_EXTREMAL_M), ("no_go", NO_GO_EXTREMAL_M))
            for m in ms
        }
        res = judge_r(r, rows, pure)
        per_r.append(res)
        if log:
            log(
                {
                    k: v
                    for k, v in res.items()
                    if k not in ("rows", "pure_extremal_size")
                }
            )
    return {
        "note": "判定に使わない見取り図。凍結する判定式で、合成の選択に効果の形を当てた。",
        "target_sha256": bound,
        "numpy": np.__version__,
        "params": params(),
        "R_run": list(r_values),
        "per_R": per_r,
        "sweeps": sweeps,
        "boundaries": sweep_boundaries(sweeps, r_values),
        "most_favorable_reaches": most_favorable_reaches(sweeps),
        "selection": select(per_r),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--r", type=int, nargs="*", default=list(R_CANDIDATES))
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args(argv)

    def log(row: dict[str, Any]) -> None:
        print(json.dumps(row, ensure_ascii=False), flush=True)

    result = run(list(args.r), args.workers, log)
    sc.write_json(args.out, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
