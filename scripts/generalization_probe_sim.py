"""候補 G (汎化 probe) — 見取り図 (判定に使わない) と R の選定 (prereg §7、計測台 ADR §4.3).

凍結した判定式 (``generalization_probe_scorer`` の e-value・``decide``・⊥ gate) を、凍結した設計 (単位・つ組・表示順) の上で
合成の選択に当てる。効果の形は統合系 ADR §5.2 の 6 形 (逆向きを含む) と、帰無の領域の非対称な分布。

生成の模型 (prereg §7.1):

* セル = (単位 u, つ組の probe q, arm a)、K = 1。⊥ は確率 b。残りの質量で、確率 |λ| で w (λ > 0) か foil (λ < 0) を
  選び、それ以外は base (Ω = 族の 3 label と OOΩ 5%) から引く。混合の形では E[C] = (1 − b) · E[λ]。
* 族内の 2 arm の乱数の結合 (Codex MEDIUM-10 で「両端」を「代表的な 3 結合」に改めた): ``crn`` = 共通の一様乱数
  (同じ seed の写し。族内の 2 arm とつ組の 3 probe で共有)、``indep`` = 独立、``anti`` = 逆向き
  (u と 1 − u、⊥ も v と 1 − v)。
* 攪乱点 18 = base {uniform, label_skew, position_skew} × b {0, 0.1} × 結合 {crn, indep, anti}。
* 対数オッズの形だけは混合でなく、base (label_skew に固定) の w の対数オッズに β を足す。E[C] は β で較正する。
* 項目単位の形 (項目の全か無か・逆向き) は、項目の数を厳密にして実現平均を目標に一致させる (帰無は固定した
  prompt の schedule に条件付ける。prereg §5.2)。

R の選定規則 (実データ前。2026-10-02 の user 裁定 DU-1 で「最小の合格 R」から改め、Codex HIGH-1 で候補を 3 の倍数に
した。prereg §7・decisions DU-1・DC-1): 本走の R は候補の最大 R_MAIN = 18。R_MAIN が次の 3 条件をすべて満たせば選び、
満たさなければ door-close。他の R の候補は、境目と size を報告するためだけに計算する。
* 18 攪乱点で、一様 sd 0.05 / sd 0.3 の P(PASS | E[C] = 2τ) ≥ 0.8、対数オッズの形 (6 点) でも ≥ 0.8。
* 18 攪乱点で、一様 sd 0.05 / sd 0.3 の P(NO_GO | E[C] = 0) ≥ 0.8。
* 全形の境界 (E[C] = τ) と帰無の領域 (二点の極値・弱い null) で、両枝の棄却の数 X が合格 (X ≤ x)。
  size の上限は α (定理、scorer の docstring)。x は P(X > x) ≤ 0.01 / G を満たす最小の整数 (X ~ Binomial(N, α)、
  G = その R で確かめる size の点の数 × seed 数。Codex MEDIUM-9・2 回目 LOW-6)。棄却は X ≥ x + 1。
最も有利な行 (一様 sd 0.05・uniform・b 0・crn) が、どの R でも E[C] = 2τ の点で power 0.8 に届かなければ door-close。

実行 (repo root から、所要は数十分)::

    uv run python scripts/generalization_probe_sim.py --out experiments/20261001-generalization-probe-pilot/results/sketch.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Any, Final

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import generalization_probe_battery as bat  # noqa: E402
from scripts import generalization_probe_scorer as sc  # noqa: E402

R_CANDIDATES: Final[tuple[int, ...]] = (6, 12, 18)
R_MAIN: Final[int] = 18  # 本走の R (候補の最大。user 裁定 DU-1、3 の倍数は DC-1)
GRID: Final[tuple[float, ...]] = tuple(round(0.30 + 0.025 * i, 3) for i in range(21))
N_SIM_POWER: Final[int] = 2_000
N_SIM_SIZE: Final[int] = 10_000
SEEDS: Final[tuple[int, ...]] = (20261001, 20261002)
POWER_TARGET: Final[float] = 0.8
MC_FWER: Final[float] = 0.01
CHUNK: Final[int] = 1_000
OOV: Final[float] = 0.05
SKEW: Final[float] = 0.7

FORMS: Final[tuple[str, ...]] = (
    "homog_sd005",
    "homog_sd030",
    "sparse_1of3",
    "sparse_2of3",
    "aon_cell",
    "aon_unit",
    "aon_arm_unit",
    "aon_item",
    "logodds",
    "reverse_1of6",
)
POWER_FORMS: Final[tuple[str, ...]] = ("homog_sd005", "homog_sd030", "logodds")
NO_GO_FORMS: Final[tuple[str, ...]] = ("homog_sd005", "homog_sd030")
GAUSS_SD: Final[dict[str, float]] = {"homog_sd005": 0.05, "homog_sd030": 0.30}
SPARSE_CLASSES: Final[dict[str, int]] = {"sparse_1of3": 1, "sparse_2of3": 2}
REVERSE_FRACTION: Final[float] = 1.0 / 6.0
WEAK_NULL: Final[dict[str, float]] = {"p_up": 5.0 / 7.0, "up": 0.4, "down": -1.0}
PASS_EXTREMAL_M: Final[tuple[float, ...]] = (0.4, 0.6, 0.8, 1.0)
NO_GO_EXTREMAL_M: Final[tuple[float, ...]] = (-1.0, -0.5, 0.0, 0.2)


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
    unit_triple: np.ndarray  # (U,)
    unit_r: np.ndarray  # (U,)
    probe_class: np.ndarray  # (U, 3) 分類番号
    position0: np.ndarray  # (U, 3) 表示先頭の label の、族の正準順での index
    w_idx: np.ndarray  # (U, 3, 2) arm (族内の 0 = A / B、1 = 回転) の w の正準 index
    foil_idx: np.ndarray  # (U, 3, 2) foil の正準 index


def design(r_count: int) -> Design:
    us = bat.units(r_count)
    fam = np.array([u.family for u in us])
    tri = np.array([u.triple for u in us])
    rr = np.array([u.replicate for u in us])
    cls = np.zeros((len(us), 3), dtype=int)
    pos0 = np.zeros((len(us), 3), dtype=int)
    for ui, u in enumerate(us):
        for qi, p in enumerate(bat.triple_probes(u.triple)):
            cls[ui, qi] = bat.CLASSES.index(p.situation.latent)
            pos0[ui, qi] = (u.replicate + u.triple) % bat.N_POSITIONS
    # 族の正準順は分類の順 (A(c) = index c)。arm 0 の w = c、arm 1 (回転) の w = c + 1 (mod 3)
    w0 = cls
    w1 = (cls + 1) % 3
    w_idx = np.stack([w0, w1], axis=-1)
    foil_idx = np.stack([w1, w0], axis=-1)
    return Design(r_count, fam, tri, rr, cls, pos0, w_idx, foil_idx)


def arm_indices(dz: Design) -> tuple[np.ndarray, np.ndarray]:
    """(U, 3, 2) の w と foil の、族の正準順での index."""
    return dz.w_idx, dz.foil_idx


def base_probs(dz: Design, base: str) -> np.ndarray:
    """(U, 3, 4) = Ω の 3 label (族の正準順) と OOΩ の、⊥ 以外の質量の中の確率.

    label_skew は arm 0 の w (= 分類 c の label) に 0.7、position_skew は表示の先頭に 0.7。
    """
    n_u = dz.unit_family.size
    live = 1.0 - OOV
    p = np.zeros((n_u, 3, 4))
    if base == "uniform":
        p[..., :3] = live / 3.0
    else:
        target = dz.probe_class if base == "label_skew" else dz.position0
        rest = (1.0 - SKEW) / 2.0
        p[..., :3] = live * rest
        np.put_along_axis(p, target[..., None], live * SKEW, axis=-1)
    p[..., 3] = OOV
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


def reachable(form: str, nu: Nuisance) -> float:
    live = 1.0 - nu.bot
    if form in SPARSE_CLASSES:
        return live * SPARSE_CLASSES[form] / 3.0
    if form == "reverse_1of6":
        return live * (1.0 - 2.0 * REVERSE_FRACTION)
    if form == "logodds":
        return live * (1.0 - OOV) * 0.999
    return live


def lam_array(
    form: str, target: float, dz: Design, nu: Nuisance, n: int, rng: np.random.Generator
) -> np.ndarray:
    """(n, U, 3, 2) の λ (混合の形)。E[C] = (1 − b) · E[λ] = target になるよう較正."""
    n_u = dz.unit_family.size
    t = target / (1.0 - nu.bot)
    if form in GAUSS_SD:
        sd = GAUSS_SD[form]
        e = _loc_for(t, sd) + sd * rng.standard_normal((n, n_u, 1, 2))
        return np.broadcast_to(np.clip(e, -1.0, 1.0), (n, n_u, 3, 2))
    if form in SPARSE_CLASSES:
        k = SPARSE_CLASSES[form]
        on = (dz.probe_class < k).astype(float)  # (U, 3)
        lam = min(1.0, t * 3.0 / k)
        return np.broadcast_to((lam * on)[None, :, :, None], (n, n_u, 3, 2))
    if form == "aon_cell":
        return (rng.random((n, n_u, 3, 2)) < t).astype(float)
    if form == "aon_unit":
        on = (rng.random((n, n_u, 1, 1)) < t).astype(float)
        return np.broadcast_to(on, (n, n_u, 3, 2))
    if form == "aon_arm_unit":
        # arm × 単位の全か無か (ADR §5.2 の形 3。本設計では r が単位の間で共有する乱数を持たないので、
        # replicate を単位の間で共有する形は置かない。prereg §7.1)
        on = (rng.random((n, n_u, 1, 2)) < t).astype(float)
        return np.broadcast_to(on, (n, n_u, 3, 2))
    if form == "aon_item":
        # 項目 (族・つ組・probe、計 48) ごとに 0 か 1、r を通じて固定。項目平均が厳密に t になるよう、
        # 1 の数を floor(48t) にし、端数を 1 項目の λ に置く (帰無は項目に条件付けた平均。prereg §7.1)
        return _item_pattern(_exact_item_values(t, n, rng, low=0.0, high=1.0), dz, n)
    if form == "reverse_1of6":
        # 項目の 1/6 (8 項目) が逆向き (λ = −1)、残り 40 項目は κ。項目平均は厳密に t
        n_items = len(bat.FAMILIES) * bat.N_TRIPLES * 3
        n_rev = round(n_items * REVERSE_FRACTION)
        kappa = (t * n_items + n_rev) / (n_items - n_rev)
        vals = np.full((n, n_items), kappa)
        vals[:, :n_rev] = -1.0
        return _item_pattern(rng.permuted(vals, axis=1), dz, n)
    if form == "weak_null":
        up = rng.random((n, n_u, 1, 1)) < WEAK_NULL["p_up"]
        lam = np.where(up, WEAK_NULL["up"], WEAK_NULL["down"])
        return np.broadcast_to(lam, (n, n_u, 3, 2))
    if form.startswith(("pass_extremal_", "no_go_extremal_")):
        m = float(form.rsplit("_", 1)[1])
        other = -1.0 if form.startswith("pass") else 1.0
        p = (t - other) / (m - other)
        hit = rng.random((n, n_u, 1, 1)) < p
        lam = np.where(hit, m, other)
        return np.broadcast_to(lam, (n, n_u, 3, 2))
    msg = f"unknown form {form!r}"
    raise ValueError(msg)


def _exact_item_values(
    t: float, n: int, rng: np.random.Generator, low: float, high: float
) -> np.ndarray:
    """(n, 48) の項目の λ。値は low / high で、平均が厳密に t (端数は 1 項目に置く)。配置は無作為."""
    n_items = len(bat.FAMILIES) * bat.N_TRIPLES * 3
    total = (t - low) * n_items / (high - low)
    k = int(math.floor(total + 1e-12))
    vals = np.full((n, n_items), low)
    vals[:, :k] = high
    if k < n_items:
        vals[:, k] = low + (total - k) * (high - low)
    return rng.permuted(vals, axis=1)


def _item_pattern(vals: np.ndarray, dz: Design, n: int) -> np.ndarray:
    """(n, 48) の項目の λ → (n, U, 3, 2)。項目 = (族, つ組, つ組内の probe)."""
    grid = vals.reshape(n, len(bat.FAMILIES), bat.N_TRIPLES, 3)
    lam = grid[:, dz.unit_family, dz.unit_triple, :]
    return np.broadcast_to(lam[..., None], (n, dz.unit_family.size, 3, 2))


def _logodds_probs(dz: Design, beta: float) -> np.ndarray:
    """(U, 3, 2, 4): label_skew の base の w の対数オッズに β を足した分布 (⊥ 以外の質量の中)."""
    base = base_probs(dz, "label_skew")  # (U, 3, 4)
    w, _ = arm_indices(dz)
    p = np.repeat(base[:, :, None, :], 2, axis=2)
    boost = np.zeros_like(p)
    np.put_along_axis(boost, w[..., None], beta, axis=-1)
    q = p * np.exp(boost)
    q[..., :3] *= (1.0 - OOV) / q[..., :3].sum(axis=-1, keepdims=True)
    return q


def _expected_c_logodds(dz: Design, beta: float, bot: float) -> float:
    q = _logodds_probs(dz, beta)
    w, foil = arm_indices(dz)
    pw = np.take_along_axis(q, w[..., None], -1)
    pf = np.take_along_axis(q, foil[..., None], -1)
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
    probs: np.ndarray, nu: Nuisance, rng: np.random.Generator, n: int
) -> tuple[np.ndarray, np.ndarray]:
    """probs (n, U, 3, 2, 4) から outcome index (n, U, 3, 2) と ⊥ (n, U, 3, 2) を引く (結合に従う)."""
    shape = probs.shape[:-1]
    if nu.coupling == "crn":
        # 族内の 2 arm とつ組の 3 probe で共通 (seed の共有の写し、Codex 2 回目 HIGH-1)
        u = np.broadcast_to(rng.random((*shape[:-2], 1, 1)), shape)
        v = np.broadcast_to(rng.random((*shape[:-2], 1, 1)), shape)
    elif nu.coupling == "anti":
        u0 = rng.random((*shape[:-1], 1))
        v0 = rng.random((*shape[:-1], 1))
        u = np.concatenate([u0, 1.0 - u0], axis=-1)
        v = np.concatenate([v0, 1.0 - v0], axis=-1)
    else:
        u = rng.random(shape)
        v = rng.random(shape)
    cdf = np.cumsum(probs, axis=-1)
    idx = np.minimum((cdf < u[..., None]).sum(axis=-1), probs.shape[-1] - 1)
    del n
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
    w, foil = arm_indices(dz)  # (U, 3, 2)
    if form == "logodds":
        assert beta is not None
        probs = np.broadcast_to(_logodds_probs(dz, beta)[None], (n, *w.shape, 4))
    else:
        lam = lam_array(form, target, dz, nu, n, rng)  # (n, U, 3, 2)
        base = np.broadcast_to(
            base_probs(dz, nu.base)[None, :, :, None, :], (*lam.shape, 4)
        )
        mix = np.abs(lam)[..., None]
        point = np.zeros((*lam.shape, 4))
        tgt = np.where(lam > 0, w[None], foil[None])
        np.put_along_axis(point, tgt[..., None], 1.0, axis=-1)
        probs = (1.0 - mix) * base + mix * point
    idx, bot = _draw(probs, nu, rng, n)
    score = (idx == w[None]).astype(float) - (idx == foil[None])
    score = np.where(bot, 0.0, score)
    s = score.mean(axis=2)  # (n, U, 2) 単位の成分 (K = 1、3 probe)
    d = s.mean(axis=2)  # (n, U)
    # 成分: arm ごとの s の平均 (LEVER_ARMS の順)
    comps = np.stack(
        [
            s[:, dz.unit_family == f, a].mean(axis=1)
            for f in range(len(bat.FAMILIES))
            for a in range(2)
        ],
        axis=1,
    )
    botr = np.stack(
        [
            bot[..., a][:, dz.unit_family == f].mean(axis=(1, 2))
            for f in range(len(bat.FAMILIES))
            for a in range(2)
        ],
        axis=1,
    )
    le_plus, le_minus, _ = sc.e_values(d)
    verdict = sc.decide(le_plus, le_minus, comps)
    verdict = np.where(sc.bottom_gate_ok(botr), verdict, sc.VERDICT_INVALID_BATTERY)
    return verdict, d.mean(axis=1)


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
    for start in range(0, n_sims, CHUNK):
        n = min(CHUNK, n_sims - start)
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


def _tag(form: str, nu: Nuisance) -> tuple[int, ...]:
    h = hashlib.sha256(f"{form}|{nu.base}|{nu.bot}|{nu.coupling}".encode()).digest()
    return (int.from_bytes(h[:4], "little"),)


def pure_extremal_size(
    m: float, n_units: int, n_sims: int, seed: int, branch: str
) -> float:
    """単位 d を二点 {m, −1} (PASS 枝) / {m, +1} (NO_GO 枝) から直接引いたときの、その枝の棄却率 (定理の確認)."""
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


def evaluate_r(r_count: int, log: Any = None) -> dict[str, Any]:
    """1 つの R について、選定規則の 3 条件と最も有利な行を計算する."""
    rows: list[dict[str, Any]] = []

    def run(
        kind: str, form: str, target: float, nu: Nuisance, n_sims: int
    ) -> dict[str, Any]:
        per_seed = [simulate(form, target, r_count, nu, n_sims, s) for s in SEEDS]
        row = {
            "kind": kind,
            "R": r_count,
            "form": form,
            "target_C": target,
            **asdict(nu),
        }
        row["per_seed"] = per_seed
        rows.append(row)
        if log:
            log(row)
        return row

    power_ok = True
    for form in POWER_FORMS:
        for nu in _nuisances_for(form):
            row = run("power_pass", form, sc.DELTA_PLANT, nu, N_SIM_POWER)
            val = float(np.mean([p[sc.VERDICT_PASS] for p in row["per_seed"]]))
            row["value"] = val
            power_ok &= val >= POWER_TARGET
    no_go_ok = True
    for form in NO_GO_FORMS:
        for nu in nuisance_grid():
            row = run("power_no_go", form, 0.0, nu, N_SIM_POWER)
            val = float(np.mean([p[sc.VERDICT_ABSENT] for p in row["per_seed"]]))
            row["value"] = val
            no_go_ok &= val >= POWER_TARGET
    size_rows = []
    for form, target, branch in size_points():
        for nu in _nuisances_for(form):
            row = run(f"size_{branch}", form, target, nu, N_SIM_SIZE)
            key = sc.VERDICT_PASS if branch == "pass" else sc.VERDICT_ABSENT
            row["value"] = float(max(p[key] for p in row["per_seed"]))
            size_rows.append(row)
    n_checks = len(size_rows) * len(SEEDS)
    tol = mc_tolerance(n_checks)
    cap = sc.ALPHA + tol
    size_ok = all(r["value"] <= cap + 1e-12 for r in size_rows)
    pure = {
        f"{branch}_{m}": max(
            pure_extremal_size(m, len(bat.units(r_count)), N_SIM_SIZE, s, branch)
            for s in SEEDS
        )
        for branch, ms in (("pass", PASS_EXTREMAL_M), ("no_go", NO_GO_EXTREMAL_M))
        for m in ms
    }
    return {
        "R": r_count,
        "n_units": len(bat.units(r_count)),
        "calls_lever": len(bat.units(r_count)) * 2 * 3 * sc.FROZEN_K,
        "calls_c0": r_count * len(bat.probes()) * sc.FROZEN_K,
        "power_ok": bool(power_ok),
        "no_go_ok": bool(no_go_ok),
        "size_ok": bool(size_ok),
        "size_cap": cap,
        "mc_tolerance": tol,
        "n_size_checks": n_checks,
        "worst_size": max(r["value"] for r in size_rows),
        "pure_extremal_size": pure,
        "rows": rows,
    }


def sweep(r_count: int, log: Any = None) -> list[dict[str, Any]]:
    """形ごとの E[C] 掃引 (有利・不利の 2 攪乱点)。power 0.8 の境目を読むための表 (判定に使わない)."""
    out = []
    for form in FORMS:
        for nu in (FAVORABLE, ADVERSE):
            if form == "logodds" and nu.base != "label_skew":
                nu = Nuisance("label_skew", nu.bot, nu.coupling)  # noqa: PLW2901
            reach = reachable(form, nu)
            for target in [c for c in GRID if c <= reach + 1e-9]:
                per_seed = [
                    simulate(form, target, r_count, nu, N_SIM_POWER, s) for s in SEEDS
                ]
                row = {
                    "R": r_count,
                    "form": form,
                    "target_C": target,
                    **asdict(nu),
                    "reachable": reach,
                    "pass": float(np.mean([p[sc.VERDICT_PASS] for p in per_seed])),
                    "per_seed": per_seed,
                }
                out.append(row)
                if log:
                    log(row)
    return out


def boundary(rows: list[dict[str, Any]]) -> float | None:
    """P(PASS) が 0.8 を最初に越える E[C] (線形補間)。届かなければ None."""
    pts = sorted((r["target_C"], r["pass"]) for r in rows)
    for (c0, p0), (c1, p1) in zip(pts, pts[1:], strict=False):
        if p0 < POWER_TARGET <= p1:
            return c0 + (POWER_TARGET - p0) * (c1 - c0) / (p1 - p0)
    if pts and pts[0][1] >= POWER_TARGET:
        return pts[0][0]
    return None


def select(per_r: list[dict[str, Any]]) -> dict[str, Any]:
    """選定規則 (docstring)。R_MAIN が 3 条件を満たせば R_MAIN、満たさないか計算されていなければ door-close."""
    for res in per_r:
        if res["R"] == R_MAIN:
            ok = bool(res["power_ok"] and res["no_go_ok"] and res["size_ok"])
            return {"selected_R": R_MAIN if ok else None, "door_close": not ok}
    return {"selected_R": None, "door_close": True}


def most_favorable_reaches(sweeps: list[dict[str, Any]]) -> bool:
    """最も有利な行 (一様 sd 0.05・FAVORABLE) が、どれかの R で 2τ に到達でき、power 0.8 に届くか."""
    for r_count in R_CANDIDATES:
        rows = [
            r
            for r in sweeps
            if r["R"] == r_count
            and r["form"] == "homog_sd005"
            and (r["base"], r["bot"], r["coupling"])
            == (FAVORABLE.base, FAVORABLE.bot, FAVORABLE.coupling)
        ]
        if any(
            abs(r["target_C"] - sc.DELTA_PLANT) < 1e-9 and r["pass"] >= POWER_TARGET
            for r in rows
        ):
            return True
    return False


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--r", type=int, nargs="*", default=list(R_CANDIDATES))
    args = ap.parse_args(argv)
    # 結び付ける sha256 は計算の前に読む (長い計算の間にファイルが変わっても、使ったコードの値を残す)
    bound = {k: _sha256(v) for k, v in sc.certified_targets().items()}

    def log(row: dict[str, Any]) -> None:
        print(
            json.dumps(
                {k: v for k, v in row.items() if k != "per_seed"}, ensure_ascii=False
            ),
            flush=True,
        )

    per_r = [evaluate_r(r, log) for r in args.r]
    sweeps = [row for r in args.r for row in sweep(r, log)]
    bounds = {
        f"R{r}": {
            form: {
                kind: boundary(
                    [
                        x
                        for x in sweeps
                        if x["R"] == r
                        and x["form"] == form
                        and (x["base"], x["bot"], x["coupling"])
                        == (
                            (nu.base if form != "logodds" else "label_skew"),
                            nu.bot,
                            nu.coupling,
                        )
                    ]
                )
                for kind, nu in (("favorable", FAVORABLE), ("adverse", ADVERSE))
            }
            for form in FORMS
        }
        for r in args.r
    }
    result = {
        "note": "判定に使わない見取り図。凍結する判定式で、合成の選択に効果の形を当てた。",
        "target_sha256": bound,
        "numpy": np.__version__,
        "params": {
            "R_candidates": list(args.r),
            "grid": list(GRID),
            "n_sim_power": N_SIM_POWER,
            "n_sim_size": N_SIM_SIZE,
            "seeds": list(SEEDS),
            "tau": sc.TAU,
            "alpha": sc.ALPHA,
            "delta_plant": sc.DELTA_PLANT,
            "power_target": POWER_TARGET,
            "mc_fwer": MC_FWER,
            "oov": OOV,
            "skew": SKEW,
            "lambda_fractions": list(sc.LAMBDA_FRACTIONS),
            "weak_null": WEAK_NULL,
            "reverse_fraction": REVERSE_FRACTION,
        },
        "per_R": per_r,
        "sweeps": sweeps,
        "boundaries": bounds,
        "most_favorable_reaches": most_favorable_reaches(sweeps),
        "selection": select(per_r),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
