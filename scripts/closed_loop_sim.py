"""閉ループ分散 pilot — base 推定・閉ループの模擬・κ の植え付け・fixture 表 (prereg v4 §2.5 / §6).

CPU のみ。実モデルは呼ばない。実際のループの部品 (世界の規則・π_r・Ω_dev の巡回・probe の layout・
v2 の ⊥ gate / 3 分岐 / 符号反転) を import して使う。

**植える方策** (ADR §3.4、prereg v4 §6): 1 次元の強さ κ ∈ [0, 1] で「状態を読む reader」を表す。
* dev 段: 同じ signature の成功行があれば確率 κ で従う。無ければ、同じ weather の成功行 (distinct な
  signature 数 n ≥ 1) に確率 λ(n) で従う。flat: λ(n) = κ、graded: λ(1) = κ/2・λ(2, 3) = 3κ/4・λ(4) = κ。
  従わないときは base から引く。R1+ では、既に試した行動の重みを (1 − γ) 倍にする (γ = κ、user 裁定 DU-2)。
  ⊥ (確率 b) と Ω 外 (⊥ 以外の 5%) は失敗。
* probe 段: e = clip(κ·g(n)·1[n>0] + sd·Z, −1, 1) (Z は世界 × replicate)。e > 0 なら確率 e で自分の成功行の
  label、e < 0 なら確率 |e| で foil (v2/v3 と同じ対称な攪乱)、残りは base。
* 乱数の結合: ループ段で 2 世界の状態 (= prompt) が同一なら同じ一様乱数、違えば独立 (実モデルは prompt が
  違えば同じ seed でも別の出力を返す。独立は単位分散について保守側)。probe 段は独立。

真の C は E[C] (dev 段は Monte Carlo、probe 段は clip した正規の閉形式)。κ の格子上で E[C] を計算し、
目標の C を与える κ を線形補間で解く (κ = 1 でも届かなければ「植えられない」)。
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import numpy as np
from scripts import closed_loop_battery as bat
from scripts import skill_lever_battery as v2bat
from scripts.skill_lever_scorer import (
    BOT_MAX,
    TAU,
    _flip_matrix,
    _flip_p,
    bottom_gate_ok,
    decide,
)
from scripts.stage_b_battery import ACTIONS, WEATHER, dev_signatures
from scripts.stage_b_scorer import (
    ALPHA,
    VERDICT_ABSENT,
    VERDICT_INVALID_BATTERY,
    VERDICT_PASS,
    VERDICT_UNDERPOWERED,
)

from collections.abc import Callable

if TYPE_CHECKING:
    from collections.abc import Sequence

SIM_SEED: Final[int] = 20260927
OOV: Final[float] = 0.05  # ⊥ 以外の質量のうち Ω 外に落ちる割合 (v2/v3 と同じ)
SKEW: Final[float] = (
    0.7  # label_skew / position_skew で 1 選択肢に寄る割合 (v2/v3 と同じ)
)
BASES: Final[tuple[str, ...]] = ("uniform", "label_skew", "position_skew", "measured")
LAMBDA_VERSIONS: Final[tuple[str, ...]] = ("flat", "graded")
GRADED: Final[dict[int, float]] = {0: 0.0, 1: 0.5, 2: 0.75, 3: 0.75, 4: 1.0}
FLAT: Final[dict[int, float]] = {0: 0.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0}
KAPPA_GRID: Final[tuple[float, ...]] = tuple(round(0.04 * i, 2) for i in range(26))
VERDICTS: Final[tuple[str, ...]] = (
    VERDICT_PASS,
    VERDICT_ABSENT,
    VERDICT_UNDERPOWERED,
    VERDICT_INVALID_BATTERY,
)

# ---------------------------------------------------------------- 実測 base

# 入力 (凍結済み・変更しない): v2 と v3 の実走記録。C0 の key が重なる 120 件は raw が byte 一致する。
V2_SAMPLES: Final[str] = (
    "experiments/20260926-skill-lever-pilot/results/run/samples.jsonl"
)
V3_SAMPLES: Final[str] = (
    "experiments/20260926-experience-skill-pilot/results/run/samples.jsonl"
)
FIT_RIDGE_SD: Final[float] = 2.0  # L2 罰則 = θ² / (2·2²)
# softmax(α[weather, label] + β[表示位置]) の罰則付き MLE (``fit_measured_base``、test で再推定と一致を pin)
MEASURED_ALPHA: Final[tuple[tuple[float, ...], ...]] = (
    (-2.865426, 2.55331, 0.20555, 0.106566, 0.0, 0.0),
    (0.0, 0.0, 2.650322, -0.057289, -2.718406, 0.125374),
    (-0.504951, 1.4953, 0.0, 0.0, -0.415205, -0.575143),
)
MEASURED_BETA: Final[tuple[float, ...]] = (-1.515986, 0.079821, 0.466302, 0.969863)
MEASURED_INPUT_SHA256: Final[dict[str, str]] = {
    V2_SAMPLES: "d0cf5084201a138f92f391ba60d4c66bd9cab6ce7f0c95d8af0b4b8692f7125a",
    V3_SAMPLES: "52c2140fa9e34c9105197be13acb6a1e6a6eb5f4c1208529194bde1e7a85c8cc",
}


def c0_fit_data(root: Path) -> list[tuple[int, tuple[int, ...], int]]:
    """(weather 番号, 表示順の label 番号 4 つ, 選んだ表示位置)。v3 の C0 全件 + v2 だけにある key.

    ⊥ と Ω 外は除く (C0 の実測ではどちらも 0 件)。
    """
    by_key: dict[tuple[int, str, int], dict[str, Any]] = {}
    for rel in (V2_SAMPLES, V3_SAMPLES):  # 後から読む v3 が重なる key を上書きする
        for line in (root / rel).read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                if rec["arm"] == v2bat.ARM_C0:
                    by_key[(rec["replicate"], rec["probe_id"], rec["k"])] = rec
    probes = {p.probe_id: p for p in v2bat.lever_probes()}
    out = []
    for (r, pid, _), rec in sorted(by_key.items()):
        order = v2bat.layout(r).option_order[pid]
        if rec["parsed"] in order:
            out.append(
                (
                    WEATHER.index(probes[pid].signature[0]),
                    tuple(ACTIONS.index(o) for o in order),
                    order.index(rec["parsed"]),
                )
            )
    return out


def fit_measured_base(
    data: Sequence[tuple[int, tuple[int, ...], int]], iters: int = 50
) -> tuple[np.ndarray, np.ndarray]:
    """罰則付き多項 logit の Newton 法。θ = (α 18 個, β 4 個)."""
    n_a = len(WEATHER) * len(ACTIONS)
    dim = n_a + bat.N_POSITIONS
    design = []
    for wi, opts, choice in data:
        x = np.zeros((bat.N_POSITIONS, dim))
        for pos, lab in enumerate(opts):
            x[pos, wi * len(ACTIONS) + lab] = 1.0
            x[pos, n_a + pos] = 1.0
        design.append((x, choice))
    theta = np.zeros(dim)
    ridge = 1.0 / FIT_RIDGE_SD**2
    for _ in range(iters):
        grad = -ridge * theta
        hess = -ridge * np.eye(dim)
        for x, choice in design:
            z = x @ theta
            p = np.exp(z - z.max())
            p /= p.sum()
            mean = p @ x
            grad += x[choice] - mean
            hess -= (x.T * p) @ x - np.outer(mean, mean)
        step = np.linalg.solve(hess, grad)
        theta -= step
        if np.max(np.abs(step)) < 1e-12:
            break
    return theta[:n_a].reshape(len(WEATHER), len(ACTIONS)), theta[n_a:]


def input_sha256(root: Path) -> dict[str, str]:
    return {
        rel: hashlib.sha256((root / rel).read_bytes()).hexdigest()
        for rel in (V2_SAMPLES, V3_SAMPLES)
    }


# ---------------------------------------------------------------- base 分布


def base_option_probs(base: str, weather: str, options: Sequence[str]) -> np.ndarray:
    """状態を読まない選択の、表示された 4 選択肢上の分布 (⊥・Ω 外を除いた条件付き)."""
    n = len(options)
    if base == "uniform":
        return np.full(n, 1.0 / n)
    if base == "label_skew":
        target = bat.rule(bat.WORLDS[0])[weather]
        return np.array(
            [SKEW if o == target else (1 - SKEW) / (n - 1) for o in options]
        )
    if base == "position_skew":
        return np.array([SKEW if i == 0 else (1 - SKEW) / (n - 1) for i in range(n)])
    if base == "measured":
        alpha = np.array(MEASURED_ALPHA)
        beta = np.array(MEASURED_BETA)
        wi = WEATHER.index(weather)
        z = np.array(
            [alpha[wi, ACTIONS.index(o)] + beta[i] for i, o in enumerate(options)]
        )
        p = np.exp(z - z.max())
        return p / p.sum()
    msg = f"unknown base {base!r}"
    raise ValueError(msg)


def lam_table(version: str) -> dict[int, float]:
    if version == "flat":
        return FLAT
    if version == "graded":
        return GRADED
    msg = f"unknown λ version {version!r}"
    raise ValueError(msg)


# ------------------------------------------------------------ 設定と前計算


@dataclass(frozen=True)
class Config:
    """模擬の 1 設定 (攪乱の格子点 + 候補の設計)."""

    base: str
    bot: float
    sd: float
    lam: str
    renderer: str
    m: int
    gamma_factor: float = 1.0  # γ = gamma_factor·κ (DU-2: 選定は 1.0、0.5 / 0 は記述)
    oov: float = OOV


@dataclass(frozen=True)
class Geometry:
    """r < R_MAX の前計算 (世界・signature・選択肢・base 分布の添字)."""

    sig_idx: (
        np.ndarray
    )  # (R, 12) ループ段 t mod 12 の signature 番号 (dev_signatures 内)
    dev_w: np.ndarray  # (R, 12) weather 番号
    rule_pos: np.ndarray  # (R, 12, W) 世界の規則が表示位置のどこにあるか
    opt_act: np.ndarray  # (R, 12, 4) 表示位置 → 行動 label の番号 (ACTIONS 内)
    non_act: np.ndarray  # (R, 12, 2) Ω_dev 外の 2 label の番号 (ACTIONS 順)
    dev_pb: dict[str, np.ndarray]  # base → (R, 12, 4)
    sig_weather: np.ndarray  # (12,) 開発 signature の weather 番号
    probe_w: np.ndarray  # (6,)
    probe_pw: dict[str, np.ndarray]  # base → (R, W, 6) 自分の規則の base 確率
    probe_pf: dict[str, np.ndarray]  # base → (R, W, 6) foil の base 確率


@lru_cache(maxsize=1)
def geometry() -> Geometry:
    devs = dev_signatures()
    rr = bat.R_MAX
    sig_idx = np.zeros((rr, bat.N_DEV), dtype=np.int64)
    dev_w = np.zeros_like(sig_idx)
    rule_pos = np.zeros((rr, bat.N_DEV, len(bat.WORLDS)), dtype=np.int64)
    opt_act = np.zeros((rr, bat.N_DEV, bat.N_POSITIONS), dtype=np.int64)
    non_act = np.zeros((rr, bat.N_DEV, len(ACTIONS) - bat.N_POSITIONS), dtype=np.int64)
    dev_pb = {b: np.zeros((rr, bat.N_DEV, bat.N_POSITIONS)) for b in BASES}
    for r in range(rr):
        for t in range(bat.N_DEV):
            sig = bat.loop_signature(r, t)
            opts = bat.dev_options(r, t)
            sig_idx[r, t] = devs.index(sig)
            dev_w[r, t] = WEATHER.index(sig[0])
            for wi, w in enumerate(bat.WORLDS):
                rule_pos[r, t, wi] = opts.index(bat.rule(w)[sig[0]])
            opt_act[r, t] = [ACTIONS.index(o) for o in opts]
            non_act[r, t] = [ACTIONS.index(a) for a in ACTIONS if a not in opts]
            for b in BASES:
                dev_pb[b][r, t] = base_option_probs(b, sig[0], opts)
    probes = v2bat.lever_probes()
    probe_pw = {b: np.zeros((rr, len(bat.WORLDS), len(probes))) for b in BASES}
    probe_pf = {b: np.zeros_like(probe_pw[b]) for b in BASES}
    for r in range(rr):
        lay = v2bat.layout(r)
        for qi, p in enumerate(probes):
            opts = lay.option_order[p.probe_id]
            for b in BASES:
                pb = base_option_probs(b, p.signature[0], opts)
                for wi, w in enumerate(bat.WORLDS):
                    probe_pw[b][r, wi, qi] = pb[opts.index(p.pointed[w])]
                    probe_pf[b][r, wi, qi] = pb[opts.index(p.pointed[v2bat.FOIL[w]])]
    return Geometry(
        sig_idx=sig_idx,
        dev_w=dev_w,
        rule_pos=rule_pos,
        opt_act=opt_act,
        non_act=non_act,
        dev_pb=dev_pb,
        sig_weather=np.array([WEATHER.index(s[0]) for s in devs]),
        probe_w=np.array([WEATHER.index(p.signature[0]) for p in probes]),
        probe_pw=probe_pw,
        probe_pf=probe_pf,
    )


# ------------------------------------------------------------ dev 段 (vectorize)


@dataclass
class DevResult:
    succ: np.ndarray  # (N, R, W, 12) bool
    loop_bot: np.ndarray  # (N, R, W) ⊥ の回数
    steps: int
    picks: np.ndarray | None = (
        None  # (N, R, W, T) 選んだ行動の番号 (⊥ は −1)、record 時のみ
    )


def _state_keys(succ: np.ndarray, tried: np.ndarray | None) -> np.ndarray:
    """(N, R, W, L) の状態 key。2 世界の key が一致 ⇔ 描画した状態ブロック (= prompt) が一致.

    成功行の label は世界の規則なので、成功行が 1 本でもあれば世界ごとに prompt が違う (4 世界の規則は
    どの weather でも相異なる)。したがって key = (成功集合, 成功行があれば世界番号 / 無ければ −1,
    R1+ なら試行集合)。試行行は世界に依らない (signature と label だけ)。
    """
    n_w = succ.shape[2]
    world = np.broadcast_to(np.arange(n_w)[None, None, :], succ.shape[:3])
    flag = np.where(succ.any(-1), world, -1)[..., None]
    parts = [succ.astype(np.int64), flag.astype(np.int64)]
    if tried is not None:
        parts.append(tried.reshape(*tried.shape[:3], -1).astype(np.int64))
    return np.concatenate(parts, axis=-1)


def _coupled(u: np.ndarray, keys: np.ndarray) -> np.ndarray:
    """状態 (= prompt) が同一の世界は、番号の小さい方の一様乱数を使う. u: (N, R, W, …)."""
    n_w = keys.shape[2]
    src = np.broadcast_to(np.arange(n_w), keys.shape[:3]).copy()
    for i in range(1, n_w):
        for j in range(i):
            same = np.all(keys[:, :, i] == keys[:, :, j], axis=-1) & (src[:, :, i] == i)
            src[:, :, i] = np.where(same, j, src[:, :, i])
    idx = src.reshape(*src.shape, *([1] * (u.ndim - 3)))
    return np.take_along_axis(u, np.broadcast_to(idx, u.shape), axis=2)


def simulate_dev(
    cfg: Config,
    kappa: float,
    n: int,
    r_count: int,
    rng: np.random.Generator,
    *,
    record: bool = False,
) -> DevResult:
    geo = geometry()
    n_w = len(bat.WORLDS)
    n_act = len(ACTIONS)
    lam = lam_table(cfg.lam)
    lam_vec = np.array([lam[i] for i in range(5)]) * kappa
    gamma = cfg.gamma_factor * kappa
    plus = cfg.renderer == bat.RENDERER_R1PLUS
    succ = np.zeros((n, r_count, n_w, bat.N_DEV), dtype=bool)
    tried = np.zeros((*succ.shape, n_act), dtype=bool) if plus else None
    loop_bot = np.zeros((n, r_count, n_w), dtype=np.int64)
    picks = np.full((n, r_count, n_w, bat.n_steps(cfg.m)), -1) if record else None
    w_masks = geo.sig_weather[None, :] == np.arange(len(WEATHER))[:, None]  # (3, 12)
    rix = np.arange(r_count)
    steps = bat.n_steps(cfg.m)
    for t in range(steps):
        tt = t % bat.N_DEV
        j = geo.sig_idx[rix, tt]  # (R,)
        wi = geo.dev_w[rix, tt]  # (R,)
        u = _coupled(rng.random((n, r_count, n_w, 4)), _state_keys(succ, tried))
        same = np.moveaxis(succ[:, rix, :, j], 0, 1)  # (N, R, W)
        n_same_w = (succ & w_masks[wi][None, :, None, :]).sum(-1)  # (N, R, W)
        p_follow = np.where(same, kappa, lam_vec[np.minimum(n_same_w, 4)])
        is_bot = u[..., 0] < cfg.bot
        follow = ~is_bot & (u[..., 1] < p_follow)
        base = ~is_bot & ~follow
        oov = base & (u[..., 2] < cfg.oov)
        pb = np.broadcast_to(
            geo.dev_pb[cfg.base][rix, tt][None, :, None, :], (*u.shape[:3], 4)
        )
        opt_act = np.broadcast_to(geo.opt_act[rix, tt][None, :, None, :], pb.shape)
        if plus:
            assert tried is not None
            tr_sig = np.moveaxis(tried[:, rix, :, j, :], 0, 1)  # (N, R, W, 6)
            tr = np.take_along_axis(tr_sig, opt_act, axis=-1)  # (N, R, W, 4)
            weights = pb * np.where(tr, 1.0 - gamma, 1.0)
            weights = np.where(tr.all(-1, keepdims=True), pb, weights)
        else:
            weights = pb
        cdf = np.cumsum(weights, axis=-1)
        cdf /= cdf[..., -1:]
        chosen = np.minimum((u[..., 3:4] >= cdf).sum(-1), bat.N_POSITIONS - 1)
        rp = np.broadcast_to(geo.rule_pos[rix, tt][None], chosen.shape)
        pick = np.where(follow, rp, chosen)
        act = np.take_along_axis(opt_act, pick[..., None], axis=-1)[..., 0]
        # Ω 外: 語彙内の Ω_dev 外 2 label のどちらか (u[2] / oov < 0.5 なら先の方)。失敗・試行に数える
        non = np.broadcast_to(geo.non_act[rix, tt][None, :, None, :], (*u.shape[:3], 2))
        second = (u[..., 2] / cfg.oov >= 0.5) if cfg.oov > 0 else np.zeros_like(oov)
        act = np.where(oov, np.where(second, non[..., 1], non[..., 0]), act)
        acted = ~is_bot
        success = acted & ~oov & (pick == rp)
        sl = (slice(None), rix[:, None], np.arange(n_w)[None, :], j[:, None])
        succ[sl] |= success
        if plus:
            assert tried is not None
            onehot = np.eye(n_act, dtype=bool)[act] & acted[..., None]
            tried[sl] = tried[sl] | onehot
        loop_bot += is_bot
        if picks is not None:
            picks[..., t] = np.where(acted, act, -1)
    return DevResult(succ=succ, loop_bot=loop_bot, steps=steps, picks=picks)


# ------------------------------------------------------------ probe 段


def _phi(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def clipped_parts(mean: float, sd: float) -> tuple[float, float]:
    """e = clip(mean + sd·Z, −1, 1) の (E[e⁺], E[e⁻]) (閉形式)."""

    def pos(m: float) -> float:
        if sd == 0.0:
            return min(1.0, max(0.0, m))
        a, b = (0.0 - m) / sd, (1.0 - m) / sd
        return m * (_cdf(b) - _cdf(a)) + sd * (_phi(a) - _phi(b)) + (1.0 - _cdf(b))

    return pos(mean), pos(-mean)


def _probe_n(succ: np.ndarray) -> np.ndarray:
    """(N, R, W, 6): probe の weather の成功 signature 数."""
    geo = geometry()
    masks = geo.sig_weather[None, :] == geo.probe_w[:, None]  # (6, 12)
    return (succ[..., None, :] & masks).sum(-1)


def expected_units(cfg: Config, kappa: float, dev: DevResult) -> np.ndarray:
    """(R,) の E[d] を r ごとに (族と模擬で平均)。probe 段は閉形式."""
    geo = geometry()
    r_count = dev.succ.shape[1]
    n_q = _probe_n(dev.succ)
    lam = lam_table(cfg.lam)
    parts = {c: clipped_parts(kappa * lam[c], cfg.sd) for c in range(5)}
    ep = np.vectorize(lambda c: parts[int(c)][0])(n_q)
    em = np.vectorize(lambda c: parts[int(c)][1])(n_q)
    pw = geo.probe_pw[cfg.base][:r_count][None]
    pf = geo.probe_pf[cfg.base][:r_count][None]
    live = 1.0 - cfg.bot
    diff = live * (ep - em + (1.0 - ep - em) * (1.0 - cfg.oov) * (pw - pf))
    s = diff.mean(-1)  # (N, R, W)
    idx = {w: i for i, w in enumerate(bat.WORLDS)}
    fam = [(s[..., idx[a]] + s[..., idx[b]]) / 2.0 for a, b in bat.FAMILIES]
    return np.mean(fam, axis=0).mean(0)  # (R,)


@dataclass
class KappaCurve:
    """κ の格子上の E[d] (r ごと)。植え付けは r < R の平均を線形補間で解く."""

    cfg: Config
    per_r: np.ndarray  # (len(KAPPA_GRID), R_MAX)
    coverage: np.ndarray  # (len(KAPPA_GRID),) 終点 weather coverage の平均

    def expected_c(self, r_count: int) -> np.ndarray:
        return self.per_r[:, :r_count].mean(-1)

    def solve(self, target: float, r_count: int) -> float | None:
        """E[C](κ) = target の κ。κ = 0 で 0 を返す。κ = 1 でも届かなければ None."""
        if target == 0.0:
            return 0.0
        ec = np.maximum.accumulate(self.expected_c(r_count))
        if ec[-1] < target:
            return None
        i = int(np.searchsorted(ec, target))
        if i == 0:
            return KAPPA_GRID[0]
        k0, k1 = KAPPA_GRID[i - 1], KAPPA_GRID[i]
        c0, c1 = ec[i - 1], ec[i]
        return k0 if c1 == c0 else k0 + (target - c0) * (k1 - k0) / (c1 - c0)


def kappa_curves(
    cfg: Config, sds: Sequence[float], n: int = 1000, seed: int = SIM_SEED
) -> dict[float, KappaCurve]:
    """共通乱数 (同じ seed) で κ の格子を走査する。dev 段は sd によらないので 1 回だけ回す."""
    per_r = {sd: np.zeros((len(KAPPA_GRID), bat.R_MAX)) for sd in sds}
    cov = np.zeros(len(KAPPA_GRID))
    for i, kappa in enumerate(KAPPA_GRID):
        dev = simulate_dev(cfg, kappa, n, bat.R_MAX, np.random.default_rng(seed))
        cov[i] = weather_coverage(dev.succ).mean()
        for sd in sds:
            per_r[sd][i] = expected_units(replace(cfg, sd=sd), kappa, dev)
    return {
        sd: KappaCurve(cfg=replace(cfg, sd=sd), per_r=per_r[sd], coverage=cov)
        for sd in sds
    }


def weather_coverage(succ: np.ndarray) -> np.ndarray:
    """(N, R, W) の終点 weather coverage."""
    geo = geometry()
    masks = geo.sig_weather[None, :] == np.arange(len(WEATHER))[:, None]
    return (succ[..., None, :] & masks).any(-1).mean(-1)


# ------------------------------------------------------------ verdict の模擬


def pipeline_gates(
    c0_bot: np.ndarray, loop_bot: np.ndarray, probe_bot: np.ndarray
) -> np.ndarray:
    """模擬の INVALID_TASK_BATTERY 判定 (scorer と同じ 3 段): C0 ⊥ ≤ 0.2・ループ段の世界別 ⊥ ≤ 0.2・
    probe の ``bottom_gate_ok`` (世界別 ≤ 0.2 ∧ 族内差 < τ/4)。形 = (N,) / (N, W) / (N, W)."""
    c0_ok = c0_bot <= BOT_MAX
    loop_ok = np.all(loop_bot <= BOT_MAX, axis=-1)
    return c0_ok & loop_ok & bottom_gate_ok(probe_bot)


def simulate_verdicts(
    cfg: Config, kappa: float, r_count: int, k: int, n_sims: int, seed: int = SIM_SEED
) -> dict[str, float]:
    """κ を植えた閉ループで pipeline (C0 gate → ループ ⊥ gate → probe ⊥ gate → 3 分岐) を n_sims 回."""
    rng = np.random.default_rng(seed)
    geo = geometry()
    dev = simulate_dev(cfg, kappa, n_sims, r_count, rng)
    n_w = len(bat.WORLDS)
    n_q = len(v2bat.lever_probes())
    nq = _probe_n(dev.succ)
    lam = lam_table(cfg.lam)
    lvec = np.array([lam[c] for c in range(5)]) * kappa
    e = np.clip(
        lvec[nq] + cfg.sd * rng.standard_normal((n_sims, r_count, n_w, 1)), -1.0, 1.0
    )
    live = 1.0 - cfg.bot
    mix = np.abs(e)
    pw = geo.probe_pw[cfg.base][:r_count][None]
    pf = geo.probe_pf[cfg.base][:r_count][None]
    base_live = live * (1.0 - mix) * (1.0 - cfg.oov)
    p_w = base_live * pw + np.where(e > 0, live * mix, 0.0)
    p_f = base_live * pf + np.where(e < 0, live * mix, 0.0)
    p_b = np.full_like(p_w, cfg.bot)
    rest = np.clip(1.0 - p_w - p_f - p_b, 0.0, 1.0)
    pvals = np.stack([p_w, p_f, p_b, rest], axis=-1)
    pvals /= pvals.sum(-1, keepdims=True)
    counts = rng.multinomial(k, pvals)  # (N, R, W, 6, 4)
    denom = n_q * k
    s = (counts[..., 0] - counts[..., 1]).sum(-1) / denom  # (N, R, W)
    idx = {w: i for i, w in enumerate(bat.WORLDS)}
    d = np.concatenate(
        [(s[:, :, idx[a]] + s[:, :, idx[b]]) / 2.0 for a, b in bat.FAMILIES], axis=1
    )
    comps = s.mean(axis=1)
    probe_bot = counts[..., 2].sum(axis=(1, 3)) / (r_count * denom)
    loop_bot = dev.loop_bot.sum(1) / (r_count * dev.steps)
    c0_bot = rng.binomial(r_count * denom, cfg.bot, size=n_sims) / (r_count * denom)
    flips, exact = _flip_matrix(d.shape[1], rng)
    verdict = decide(
        _flip_p(d - TAU, flips, exact), _flip_p(TAU - d, flips, exact), comps
    )
    verdict = np.where(
        pipeline_gates(c0_bot, loop_bot, probe_bot), verdict, VERDICT_INVALID_BATTERY
    )
    out = {v: float(np.mean(verdict == v)) for v in VERDICTS}
    out["mean_C"] = float(d.mean())
    out["unit_sd"] = float(d.std(axis=1, ddof=1).mean())
    out["weather_coverage"] = float(weather_coverage(dev.succ).mean())
    return out


# ------------------------------------------------------------ 参照の逐次実装


@dataclass
class Uniforms:
    """1 呼び出し分の一様乱数 (⊥・追従・Ω 外・選択)."""

    bot: float
    follow: float
    oov: float
    choice: float


def dev_choice_reference(
    cfg: Config,
    kappa: float,
    state: bat.State,
    world: str,
    r: int,
    t: int,
    u: Uniforms,
) -> str | None:
    """植えた方策の 1 ステップ (逐次版)。vectorize 版と同じ一様乱数で同じ行動を返す (test で pin).

    ⊥ は None。Ω 外は語彙内で Ω_dev 外の label (失敗・試行に数える、battery の ``update`` と同じ)。
    """
    sig = bat.loop_signature(r, t)
    opts = bat.dev_options(r, t)
    lam = lam_table(cfg.lam)
    if u.bot < cfg.bot:
        return None
    n_w = sum(s[0] == sig[0] for s in state.succeeded)
    p_follow = kappa if sig in state.succeeded else kappa * lam[min(n_w, 4)]
    if u.follow < p_follow:
        return bat.rule(world)[sig[0]]
    if u.oov < cfg.oov:
        non = [a for a in ACTIONS if a not in opts]
        return non[1] if u.oov / cfg.oov >= 0.5 else non[0]
    pb = base_option_probs(cfg.base, sig[0], opts)
    if cfg.renderer == bat.RENDERER_R1PLUS:
        tr = np.array([(sig, o) in state.tried for o in opts])
        if not tr.all():
            pb = pb * np.where(tr, 1.0 - cfg.gamma_factor * kappa, 1.0)
    cdf = np.cumsum(pb) / pb.sum()
    return opts[min(int((u.choice >= cdf).sum()), bat.N_POSITIONS - 1)]


# ------------------------------------------------------------ fixture 表


@dataclass(frozen=True)
class View:
    """fixture が読める情報: 状態テキストの label 列・行数・状況・表示された選択肢・自分の直前の選択."""

    success: tuple[tuple[bat.Signature, str], ...]  # π_r 順の (signature, label)
    tried: tuple[tuple[bat.Signature, str], ...]  # π_r × ACTIONS 順 (R1+ のみ)
    n_lines: int
    text: str
    sig: bat.Signature
    options: tuple[str, ...]
    last: str | None
    seed: int
    stage: str

    @property
    def labels(self) -> list[str]:
        return [a for _, a in self.success] + [a for _, a in self.tried]


def make_view(
    state: bat.State,
    world: str,
    r: int,
    renderer: str,
    sig: bat.Signature,
    options: Sequence[str],
    last: str | None,
    seed: int,
    stage: str,
) -> View:
    lay = v2bat.layout(r)
    table = bat.rule(world)
    success = tuple((s, table[s[0]]) for s in lay.entry_order if s in state.succeeded)
    tried: tuple[tuple[bat.Signature, str], ...] = ()
    if renderer == bat.RENDERER_R1PLUS:
        tried = tuple(
            (s, a) for s in lay.entry_order for a in ACTIONS if (s, a) in state.tried
        )
    text = bat.render_state(state, world, r, renderer)
    n_lines = len(success) + len({s for s, _ in tried})
    return View(success, tried, n_lines, text, sig, tuple(options), last, seed, stage)


Fixture = Callable[[View], str | None]


def _first_in(labels: Sequence[str], options: Sequence[str]) -> str | None:
    return next((a for a in labels if a in options), None)


def f_most(v: View) -> str | None:
    counts = {o: v.labels.count(o) for o in v.options}
    top = max(counts.values())
    return None if top == 0 else next(o for o in v.options if counts[o] == top)


def f_first(v: View) -> str | None:
    return _first_in(v.labels, v.options)


def f_last(v: View) -> str | None:
    return _first_in(list(reversed(v.labels)), v.options)


def f_count(v: View) -> str | None:
    return v.options[v.n_lines % len(v.options)]


def f_nonempty(v: View) -> str | None:
    return v.options[0] if v.n_lines else None


def f_label_position(v: View) -> str | None:
    if not v.labels:
        return None
    return v.options[ACTIONS.index(v.labels[0]) % len(v.options)]


def f_repeat(v: View) -> str | None:
    return v.last if v.last in v.options else None


def f_neighbor(v: View) -> str | None:
    rows = [a for s, a in v.success if s[1:] == v.sig[1:] and s != v.sig]
    return _first_in(rows, v.options)


def _hash_pick(salt: str, text: str, options: Sequence[str]) -> str:
    h = hashlib.sha256(f"{salt}\n{text}".encode()).digest()
    return options[h[0] % len(options)]


def f_hash_a(v: View) -> str | None:
    return _hash_pick("a", v.text, v.options)


def f_hash_b(v: View) -> str | None:
    return _hash_pick("b", v.text, v.options)


def f_hash_c(v: View) -> str | None:
    return _hash_pick("c", v.text, v.options)


def _tried_count(v: View) -> dict[str, int]:
    return {o: sum(a == o for _, a in v.tried) for o in v.options}


def f_least_tried(v: View) -> str | None:
    if not v.tried:
        return None
    c = _tried_count(v)
    low = min(c.values())
    return next(o for o in v.options if c[o] == low)


def f_most_tried(v: View) -> str | None:
    if not v.tried:
        return None
    c = _tried_count(v)
    top = max(c.values())
    return next(o for o in v.options if c[o] == top)


def f_lookup(v: View) -> str | None:
    """陽性対照: weather が一致する成功行の label."""
    return _first_in([a for s, a in v.success if s[0] == v.sig[0]], v.options)


# 状態を読まない方策 (相殺の定理の test 用。状況・選択肢・seed だけの関数)
def sb_seed_position(v: View) -> str | None:
    return v.options[v.seed % len(v.options)]


def sb_label_prior(v: View) -> str | None:
    return min(v.options, key=ACTIONS.index)


def sb_situation_hash(v: View) -> str | None:
    return _hash_pick(
        f"{v.seed}", "/".join(v.sig) + "|" + "、".join(v.options), v.options
    )


FIXTURES: Final[dict[str, Fixture]] = {
    "F1_most_label": f_most,
    "F2_first_row": f_first,
    "F3_last_row": f_last,
    "F4_line_count": f_count,
    "F5_nonempty": f_nonempty,
    "F6_label_x_position": f_label_position,
    "F7_repeat_previous": f_repeat,
    "F8_neighbor": f_neighbor,
    "F9_hash_a": f_hash_a,
    "F10_hash_b": f_hash_b,
    "F11_hash_c": f_hash_c,
    "F12_least_tried": f_least_tried,
    "F13_most_tried": f_most_tried,
}
R1PLUS_ONLY: Final[frozenset[str]] = frozenset({"F12_least_tried", "F13_most_tried"})
POSITIVE_CONTROL: Final[tuple[str, Fixture]] = ("P_lookup", f_lookup)
STATE_BLIND: Final[dict[str, Fixture]] = {
    "SB1_seed_position": sb_seed_position,
    "SB2_label_prior": sb_label_prior,
    "SB3_situation_hash": sb_situation_hash,
}


@dataclass
class FixtureRun:
    units: list[float] = field(default_factory=list)  # 族単位 d (模擬 × r × 族)


def run_fixture(
    policy: Fixture,
    *,
    mode: str,
    cfg: Config,
    kappa: float,
    rho: float,
    r_count: int,
    k: int,
    n_iter: int,
    seed: int,
) -> FixtureRun:
    """逐次の参照実装で fixture の C_loop 寄与を計算する (⊥ は b = cfg.bot).

    mode "P": dev 段は植えた方策 (κ)、probe 段は fixture (候補が無ければ base)。
    mode "L": dev・probe の両段で確率 ρ で fixture、それ以外は base から引く (κ = 0)。
    一様乱数は seed 単位で世界に共有する (期待値は結合によらない。状態を読まない方策は族内で一致する)。
    """
    rng = np.random.default_rng(seed)
    out = FixtureRun()
    probes = v2bat.lever_probes()
    steps = bat.n_steps(cfg.m)
    for _ in range(n_iter):
        for r in range(r_count):
            lay = v2bat.layout(r)
            u_dev = rng.random((steps, 5))
            u_probe = rng.random((len(probes), k, 3))
            comp = {}
            for world in bat.WORLDS:
                state = bat.EMPTY_STATE
                last: str | None = None
                for t in range(steps):
                    sig = bat.loop_signature(r, t)
                    opts = bat.dev_options(r, t)
                    uu = Uniforms(*u_dev[t, :4])
                    choice: str | None
                    if mode == "L" and u_dev[t, 4] < rho and uu.bot >= cfg.bot:
                        view = make_view(
                            state,
                            world,
                            r,
                            cfg.renderer,
                            sig,
                            opts,
                            last,
                            bat.loop_seed(r, t),
                            "loop",
                        )
                        choice = policy(view)
                        if choice is None:
                            choice = dev_choice_reference(
                                cfg, 0.0, state, world, r, t, uu
                            )
                    else:
                        kap = kappa if mode == "P" else 0.0
                        choice = dev_choice_reference(cfg, kap, state, world, r, t, uu)
                    real = choice if choice in ACTIONS else None
                    if choice is not None:
                        last = real
                    state = bat.update(state, world, sig, real)
                own = foil = 0
                for qi, p in enumerate(probes):
                    opts = lay.option_order[p.probe_id]
                    for kk in range(k):
                        ub, uf, uc = u_probe[qi, kk]
                        if ub < cfg.bot:
                            continue
                        pick = None
                        if mode == "P" or uf < rho:
                            view = make_view(
                                state,
                                world,
                                r,
                                cfg.renderer,
                                p.signature,
                                opts,
                                last,
                                v2bat.sample_seed(r, qi, kk),
                                "probe",
                            )
                            pick = policy(view)
                        if pick is None:
                            pb = base_option_probs(cfg.base, p.signature[0], opts)
                            cdf = np.cumsum(pb) / pb.sum()
                            pick = opts[
                                min(int((uc >= cdf).sum()), bat.N_POSITIONS - 1)
                            ]
                        own += pick == p.pointed[world]
                        foil += pick == p.pointed[v2bat.FOIL[world]]
                comp[world] = (own - foil) / (len(probes) * k)
            out.units.extend((comp[a] + comp[b]) / 2.0 for a, b in bat.FAMILIES)
    return out


# ------------------------------------------------------------ 選定基準 (v3 を継承)

SD_EXACT_MAX: Final[float] = (
    0.3  # これ以下の sd では size を α + 3SE で要求 (v2/v3 と同じ)
)
SIZE_CAP_WIDE: Final[float] = (
    1.5 * ALPHA
)  # sd > 0.3 の size 上限 (v3 の user 裁定を継承)
POWER_TARGET: Final[float] = 0.8
DELTA_PLANT: Final[float] = 2.0 * TAU
PLANT_TOL: Final[float] = 0.02  # 植えた C の許容誤差 (抽選の平均と目標の差)


def mc_margin(n_sims: int, rate: float = ALPHA) -> float:
    """Size 条件の Monte Carlo 許容幅 = 3 SE."""
    return 3.0 * float(np.sqrt(rate * (1.0 - rate) / n_sims))


def size_cap(sd: float, n_sims: int) -> float:
    if sd <= SD_EXACT_MAX:
        return ALPHA + mc_margin(n_sims)
    return SIZE_CAP_WIDE


@dataclass(frozen=True)
class Criteria:
    """1 つの格子点での 4 条件。kappa_* は植えた κ (None = κ = 1 でも届かない)."""

    kappa_tau: float | None
    kappa_plant: float | None
    realized_tau: (
        float | None
    )  # 植えた κ での抽選の平均 C (目標との差 ≤ PLANT_TOL を要求)
    realized_plant: float | None
    pass_at_plant: float
    no_go_at_zero: float
    pass_at_tau: float
    no_go_at_tau: float
    size_cap: float

    @property
    def reachable(self) -> bool:
        return self.kappa_tau is not None and self.kappa_plant is not None

    @property
    def planted(self) -> bool:
        """植えた κ で実際に目標の C に達したか (κ の補間・曲線の MC 誤差の再確認)."""
        return (
            self.realized_tau is not None
            and self.realized_plant is not None
            and abs(self.realized_tau - TAU) <= PLANT_TOL
            and abs(self.realized_plant - DELTA_PLANT) <= PLANT_TOL
        )

    @property
    def ok(self) -> bool:
        return (
            self.reachable
            and self.planted
            and self.pass_at_plant >= POWER_TARGET
            and self.no_go_at_zero >= POWER_TARGET
            and self.pass_at_tau <= self.size_cap
            and self.no_go_at_tau <= self.size_cap
        )


def design_criteria(
    cfg: Config, curve: KappaCurve, r_count: int, k: int, n_sims: int
) -> Criteria:
    """C = 0 / τ / 2τ を植えた閉ループで verdict の率を測る。size は閉ループの単位分布の下で C = τ."""
    k_tau = curve.solve(TAU, r_count)
    k_plant = curve.solve(DELTA_PLANT, r_count)
    cap = size_cap(cfg.sd, n_sims)
    if k_tau is None or k_plant is None:
        return Criteria(k_tau, k_plant, None, None, 0.0, 0.0, 1.0, 1.0, cap)
    at_plant = simulate_verdicts(cfg, k_plant, r_count, k, n_sims)
    at_zero = simulate_verdicts(cfg, 0.0, r_count, k, n_sims)
    at_tau = simulate_verdicts(cfg, k_tau, r_count, k, n_sims)
    return Criteria(
        kappa_tau=k_tau,
        kappa_plant=k_plant,
        realized_tau=at_tau["mean_C"],
        realized_plant=at_plant["mean_C"],
        pass_at_plant=at_plant[VERDICT_PASS],
        no_go_at_zero=at_zero[VERDICT_ABSENT],
        pass_at_tau=at_tau[VERDICT_PASS],
        no_go_at_tau=at_tau[VERDICT_ABSENT],
        size_cap=cap,
    )


FIXTURE_GATE: Final[float] = TAU / 4.0  # これを超えた fixture は claim に列挙する
FIXTURE_HARD: Final[float] = TAU / 2.0  # 硬い上限 (2 つ重なっても τ に届かない)


def _upper(x: dict[str, Any]) -> float:
    return float(x["mean"] + 3.0 * x["se"])


def fixture_gate(
    rows: Sequence[dict[str, Any]],
) -> tuple[bool, dict[str, Any], list[str]]:
    """正側の fixture gate (user 裁定 DU-1 / DU-3).

    * 硬い gate: 登録 fixture の (mean + 3SE) の最大 < τ/2。
    * 列挙: (mean + 3SE) ≥ τ/4 の fixture 名 (重複なし・名前順)。scorer の凍結定数
      ``FLAGGED_FIXTURES`` と一致しなければならず (manifest 検査)、PASS の文に必ず入る。

    陽性対照 (``POSITIVE_CONTROL``) は対象外。負の寄与は gate に掛けない (表で報告し、NO_GO の claim の
    範囲に含める)。返り値 = (硬い gate の合否, 最悪の行, τ/4 を超えた fixture 名)。
    """
    registered = [x for x in rows if x["fixture"] != POSITIVE_CONTROL[0]]
    worst = max(registered, key=_upper)
    flagged = sorted({x["fixture"] for x in registered if _upper(x) >= FIXTURE_GATE})
    return _upper(worst) < FIXTURE_HARD, worst, flagged


def lambda_strata(
    cfg: Config, kappa: float, r_count: int, n: int = 1000, seed: int = SIM_SEED
) -> dict[str, dict[str, float]]:
    """probe のセルを、その weather の成功 signature 数 n で層別する (ADR §3.4 の λ 感度分析).

    層 = "0" / "1" / "2-3" / "4" (= その weather の全 signature)。各層のセル割合と、
    E[P(自分の規則) − P(foil)] の平均 (世界ごとのセル単位、族で平均しない) を返す。
    """
    geo = geometry()
    dev = simulate_dev(cfg, kappa, n, r_count, np.random.default_rng(seed))
    nq = _probe_n(dev.succ)
    lam = lam_table(cfg.lam)
    parts = {c: clipped_parts(kappa * lam[c], cfg.sd) for c in range(5)}
    ep = np.vectorize(lambda c: parts[int(c)][0])(nq)
    em = np.vectorize(lambda c: parts[int(c)][1])(nq)
    pw = geo.probe_pw[cfg.base][:r_count][None]
    pf = geo.probe_pf[cfg.base][:r_count][None]
    live = 1.0 - cfg.bot
    diff = live * (ep - em + (1.0 - ep - em) * (1.0 - cfg.oov) * (pw - pf))
    out = {}
    for name, lo, hi in (("0", 0, 0), ("1", 1, 1), ("2-3", 2, 3), ("4", 4, 4)):
        mask = (nq >= lo) & (nq <= hi)
        out[name] = {
            "cell_share": float(mask.mean()),
            "mean_w_minus_foil": float(diff[mask].mean()) if mask.any() else 0.0,
        }
    return out
