"""閉ループ v5 前段 — 凍結 v5 模擬 (pilot prereg §5).

CPU のみ。pilot が測った挙動を入れて、v5 の候補設計 (軸, R, K, M) が v4 と同じ基準を満たすかを審査する。

**dev 段 = 経験的混合方策** (scoping ADR §2.1 の原型 ``sim/v5_feasibility.py`` を写す)。κ に依らない
(モデルの dev 段の挙動は pilot で測る値であり、植える対象ではない)。未成功の signature で、上から最初に当たった分岐をとる:

  0. ⊥ (確率 b)。行動なし (試行にも前回にも数えない)
  1. 同 signature の成功行 → 規則 (成功済みなら常に)
  2. C のみ: 表示中の選択肢に試行済みがあり未試行も残るとき、確率 ε で未試行から選ぶ
     (一様 / base を未試行に制限して正規化、user 裁定 DP-3)。選ばなければ確率 ρ で前回を写す
  3. 同一 prompt の以前の訪問があれば、確率 s_same でその時の応答を反復 (B は 4 周ごとに回転の位相が戻る)。
     無ければ、再訪で前回の label が表示中にあるとき確率 s_changed で前回を反復
  4. 同 weather の成功行が 1 本以上あれば確率 λ_dev で規則
  5. base (表示中の 4 選択肢上の分布)
  最後に、未成功の signature で ⊥ でない応答は確率 oov で Ω_dev 外の label に置き換わる (失敗・試行に数える)。

分岐ごとに独立の一様乱数を使う。乱数の結合は v4 と同じ: 描画した prompt が同一の世界は同じ一様乱数
(``closed_loop_sim._state_keys`` / ``_coupled``)。prompt が同一の世界は履歴も同一 (結合の下で帰納的に)。

**probe 段 = v4 と同一の植え付け** e = clip(κ·g(n)·1[n>0] + sd·Z, −1, 1)。E[C] は閉形式 (v4 ``expected_units``)。
K 回は、1 回目を引いた後、各回が確率 k_rep で 1 回目を反復し、残りは独立に引く (user 裁定 DP-3)。
null は κ = 0、size は E[C] = τ を与える κ、power は E[C] = 2τ を与える κ。基準は v4 の ``Criteria`` をそのまま使う。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Final

import numpy as np
from scripts import closed_loop_battery as v4bat
from scripts import closed_loop_sim as v4sim
from scripts import closed_loop_v5_battery as bat
from scripts import skill_lever_battery as v2bat
from scripts.skill_lever_scorer import TAU, _flip_matrix, _flip_p, decide
from scripts.stage_b_battery import ACTIONS, WEATHER, dev_signatures
from scripts.stage_b_scorer import VERDICT_ABSENT, VERDICT_INVALID_BATTERY, VERDICT_PASS

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

SIM_SEED: Final[int] = 20260928
UNTRIED_UNIFORM: Final[str] = "uniform"
UNTRIED_BASE: Final[str] = "base_restricted"
UNTRIED_MODES: Final[tuple[str, ...]] = (UNTRIED_UNIFORM, UNTRIED_BASE)
BASE_C0: Final[str] = "measured"  # v4 凍結の実測 base (C0 由来、位置効果つき)
N_U: Final[int] = 9  # 1 呼び出しの一様乱数の列数

# 列の割り当て (分岐ごとに独立)
U_BOT, U_EPS, U_UNTRIED, U_COPY, U_REP, U_SW, U_BASE, U_OOV, U_OOV_WHICH = range(N_U)

DEVS: Final = dev_signatures()


# ---------------------------------------------------------------- 挙動


@dataclass(frozen=True)
class Behaviour:
    """dev 段の方策の 1 点.

    base: weather → label → 確率 (位置効果なし、Ω_dev 上) / None なら v4 凍結の実測 base (``BASE_C0``)。
    """

    axis: str
    lam_dev: float
    base: tuple[tuple[str, tuple[tuple[str, float], ...]], ...] | None
    bot: float
    oov: float
    s_changed: float = 1.0
    s_same: float = 0.96
    eps: float = 0.0
    rho: float = 1.0
    untried: str = UNTRIED_UNIFORM

    @property
    def tried_rows(self) -> bool:
        return self.axis == bat.AXIS_C


def base_table(
    probs: Mapping[str, Mapping[str, float]],
) -> tuple[tuple[str, tuple[tuple[str, float], ...]], ...]:
    return tuple(
        (wt, tuple((a, float(probs[wt][a])) for a in v4bat.dev_omega(wt)))
        for wt in WEATHER
    )


def base_probs(beh: Behaviour, weather: str, options: Sequence[str]) -> np.ndarray:
    """表示中の 4 選択肢上の base 分布."""
    if beh.base is None:
        return v4sim.base_option_probs(BASE_C0, weather, options)
    table = dict(dict(beh.base)[weather])
    p = np.array([table[o] for o in options], dtype=float)
    return p / p.sum()


# ---------------------------------------------------------------- 前計算


@dataclass(frozen=True)
class Geo:
    sig_idx: np.ndarray  # (R, 12)
    dev_w: np.ndarray  # (R, 12)
    shift: np.ndarray  # (R, T)
    rule_pos: np.ndarray  # (R, T, W)
    opt_act: np.ndarray  # (R, T, 4)
    non_act: np.ndarray  # (R, T, 2)
    pb: np.ndarray  # (R, T, 4)


def geo(beh: Behaviour, r_values: Sequence[int], m: int) -> Geo:
    steps = bat.N_DEV * m
    rr = len(r_values)
    sig_idx = np.zeros((rr, bat.N_DEV), dtype=np.int64)
    dev_w = np.zeros_like(sig_idx)
    shift = np.zeros((rr, steps), dtype=np.int64)
    rule_pos = np.zeros((rr, steps, len(v4bat.WORLDS)), dtype=np.int64)
    opt_act = np.zeros((rr, steps, bat.N_POSITIONS), dtype=np.int64)
    non_act = np.zeros((rr, steps, len(ACTIONS) - bat.N_POSITIONS), dtype=np.int64)
    pb = np.zeros((rr, steps, bat.N_POSITIONS))
    for i, r in enumerate(r_values):
        for t in range(steps):
            sig = v4bat.loop_signature(r, t)
            opts = bat.dev_options(beh.axis, r, t)
            if t < bat.N_DEV:
                sig_idx[i, t] = DEVS.index(sig)
                dev_w[i, t] = WEATHER.index(sig[0])
            shift[i, t] = bat.shift(beh.axis, r, t)
            for wi, w in enumerate(v4bat.WORLDS):
                rule_pos[i, t, wi] = opts.index(v4bat.rule(w)[sig[0]])
            opt_act[i, t] = [ACTIONS.index(o) for o in opts]
            non_act[i, t] = [ACTIONS.index(a) for a in ACTIONS if a not in opts]
            pb[i, t] = base_probs(beh, sig[0], opts)
    return Geo(sig_idx, dev_w, shift, rule_pos, opt_act, non_act, pb)


# ---------------------------------------------------------------- dev 段 (vectorize)


def _pick_weighted(weights: np.ndarray, u: np.ndarray) -> np.ndarray:
    """(…, 4) の重みと (…) の一様乱数から位置を選ぶ (重みが全て 0 なら 0)."""
    cdf = np.cumsum(weights, axis=-1)
    tot = np.maximum(cdf[..., -1:], 1e-300)
    return np.minimum((u[..., None] >= cdf / tot).sum(-1), bat.N_POSITIONS - 1)


def simulate_dev(
    beh: Behaviour,
    m: int,
    r_values: Sequence[int],
    n: int,
    rng: np.random.Generator,
    *,
    record: bool = False,
) -> v4sim.DevResult:
    """経験的混合方策の dev 段。返り値は v4 の ``DevResult`` (succ (N, R, W, 12)、loop_bot (N, R, W))."""
    g = geo(beh, r_values, m)
    rr = len(r_values)
    n_w = len(v4bat.WORLDS)
    n_act = len(ACTIONS)
    steps = bat.N_DEV * m
    succ = np.zeros((n, rr, n_w, bat.N_DEV), dtype=bool)
    tried = np.zeros((*succ.shape, n_act), dtype=bool)
    last = np.full(succ.shape, -1, dtype=np.int64)
    # 巡回量ごとの直近の訪問: その時の (成功数, 試行数) と応答。状態は単調なので数の一致 ⇔ 描画の一致
    mem_key = np.full((*succ.shape, bat.N_POSITIONS, 2), -1, dtype=np.int64)
    mem_act = np.full((*succ.shape, bat.N_POSITIONS), -1, dtype=np.int64)
    loop_bot = np.zeros((n, rr, n_w), dtype=np.int64)
    picks = np.full((n, rr, n_w, steps), -1) if record else None
    w_masks = np.array([[DEVS[j][0] == wt for j in range(bat.N_DEV)] for wt in WEATHER])
    rix = np.arange(rr)
    wix = np.arange(n_w)
    for t in range(steps):
        tt = t % bat.N_DEV
        j = g.sig_idx[rix, tt]  # (R,)
        wi_w = g.dev_w[rix, tt]
        keys = v4sim._state_keys(succ, tried if beh.tried_rows else None)
        u = v4sim._coupled(rng.random((n, rr, n_w, N_U)), keys)
        sl = (slice(None), rix[:, None], wix[None, :], j[:, None])  # → (N, R, W)
        done = succ[sl]
        n_sw = (succ & w_masks[wi_w][None, :, None, :]).sum(-1)
        opt_act = np.broadcast_to(g.opt_act[:, t][None, :, None, :], (n, rr, n_w, 4))
        rp = np.broadcast_to(g.rule_pos[:, t][None], (n, rr, n_w))
        pb = np.broadcast_to(g.pb[:, t][None, :, None, :], (n, rr, n_w, 4))
        tr = np.take_along_axis(tried[sl], opt_act, axis=-1)  # (N, R, W, 4)
        prev = last[sl]
        # 前回の label の表示位置 (無い・表示中に無ければ −1)
        prev_pos = np.full(prev.shape, -1)
        for p in range(bat.N_POSITIONS):
            prev_pos = np.where(prev == opt_act[..., p], p, prev_pos)
        has_prev = prev_pos >= 0
        now = np.stack(
            [
                succ.sum(-1),
                tried.sum((-1, -2))
                if beh.tried_rows
                else np.zeros(succ.shape[:3], dtype=np.int64),
            ],
            axis=-1,
        )
        sh = g.shift[:, t]  # (R,)
        mk = np.take_along_axis(
            mem_key[sl],
            np.broadcast_to(sh[None, :, None, None, None], (n, rr, n_w, 1, 2)),
            axis=3,
        )[..., 0, :]
        ma = np.take_along_axis(
            mem_act[sl],
            np.broadcast_to(sh[None, :, None, None], (n, rr, n_w, 1)),
            axis=3,
        )[..., 0]
        mem_pos = np.full(ma.shape, -1)
        for p in range(bat.N_POSITIONS):
            mem_pos = np.where(ma == opt_act[..., p], p, mem_pos)
        same_prompt = np.all(mk == now, axis=-1) & (mem_pos >= 0)
        # 5. base
        pick = _pick_weighted(pb, u[..., U_BASE])
        # 4. 同 weather の成功行
        pick = np.where((n_sw > 0) & (u[..., U_SW] < beh.lam_dev), rp, pick)
        # 3. 再訪の反復 (同一 prompt の以前の訪問が優先)
        pick = np.where(
            ~same_prompt & has_prev & (u[..., U_REP] < beh.s_changed), prev_pos, pick
        )
        pick = np.where(same_prompt & (u[..., U_REP] < beh.s_same), mem_pos, pick)
        # 2. C: 探索指示 → 写し
        if beh.tried_rows:
            pick = np.where(has_prev & (u[..., U_COPY] < beh.rho), prev_pos, pick)
            untried_any = tr.any(-1) & ~tr.all(-1)
            if beh.untried == UNTRIED_UNIFORM:
                w_un = (~tr).astype(float)
            else:
                w_un = pb * ~tr
            explore = untried_any & (u[..., U_EPS] < beh.eps)
            pick = np.where(explore, _pick_weighted(w_un, u[..., U_UNTRIED]), pick)
        # 1. 成功済み
        pick = np.where(done, rp, pick)
        is_bot = u[..., U_BOT] < beh.bot
        acted = ~is_bot
        oov = acted & ~done & (u[..., U_OOV] < beh.oov)
        act = np.take_along_axis(opt_act, pick[..., None], axis=-1)[..., 0]
        non = np.broadcast_to(g.non_act[:, t][None, :, None, :], (n, rr, n_w, 2))
        act = np.where(
            oov, np.where(u[..., U_OOV_WHICH] >= 0.5, non[..., 1], non[..., 0]), act
        )
        success = acted & ~oov & (pick == rp)
        onehot = np.eye(n_act, dtype=bool)[act] & acted[..., None]
        succ[sl] = done | success
        tried[sl] = tried[sl] | onehot
        last[sl] = np.where(acted, act, prev)
        mk_all = mem_key[sl]  # (N, R, W, 4, 2)
        ma_all = mem_act[sl]
        at = (
            np.arange(bat.N_POSITIONS)[None, None, None, :] == sh[None, :, None, None]
        )  # (1, R, 1, 4)
        upd = acted[..., None] & at
        mem_key[sl] = np.where(upd[..., None], now[..., None, :], mk_all)
        mem_act[sl] = np.where(upd, act[..., None], ma_all)
        loop_bot += is_bot
        if picks is not None:
            picks[..., t] = np.where(acted, act, -1)
    return v4sim.DevResult(succ=succ, loop_bot=loop_bot, steps=steps, picks=picks)


# ---------------------------------------------------------------- 逐次の参照実装


def dev_choice_reference(
    beh: Behaviour,
    state: v4bat.State,
    world: str,
    r: int,
    t: int,
    last: str | None,
    same_choice: str | None,
    u: Sequence[float],
) -> str | None:
    """1 ステップの逐次版。vectorize 版と同じ一様乱数で同じ行動を返す (test で pin). ⊥ は None.

    last = その signature での直近の ⊥ でない応答、same_choice = 描画した prompt が今回と同一の以前の訪問の応答
    (無ければ None)。
    """
    sig = v4bat.loop_signature(r, t)
    opts = bat.dev_options(beh.axis, r, t)
    rule = v4bat.rule(world)[sig[0]]
    if u[U_BOT] < beh.bot:
        return None
    if sig in state.succeeded:
        return rule
    pb = base_probs(beh, sig[0], opts)
    choice = opts[int(_pick_weighted(pb, np.array(u[U_BASE])))]
    n_sw = sum(1 for s in state.succeeded if s[0] == sig[0])
    if n_sw and u[U_SW] < beh.lam_dev:
        choice = rule
    has_prev = last is not None and last in opts
    if same_choice is not None and same_choice in opts:
        if u[U_REP] < beh.s_same:
            choice = same_choice
    elif has_prev and u[U_REP] < beh.s_changed:
        choice = last
    if beh.tried_rows:
        if has_prev and u[U_COPY] < beh.rho:
            choice = last
        tr = np.array([(sig, o) in state.tried for o in opts])
        if tr.any() and not tr.all() and u[U_EPS] < beh.eps:
            w = (~tr).astype(float) if beh.untried == UNTRIED_UNIFORM else pb * ~tr
            choice = opts[int(_pick_weighted(w, np.array(u[U_UNTRIED])))]
    if u[U_OOV] < beh.oov:
        non = [a for a in ACTIONS if a not in opts]
        return non[1] if u[U_OOV_WHICH] >= 0.5 else non[0]
    return choice


# ---------------------------------------------------------------- probe 段


@dataclass(frozen=True)
class ProbePoint:
    """probe 段の攪乱の 1 点 (v4 の base・sd・λ 版 + k_rep)."""

    base: str
    sd: float
    lam: str
    k_rep: float


def v4_config(pp: ProbePoint, bot: float) -> v4sim.Config:
    """v4 の probe 段の関数 (``expected_units`` 等) に渡す設定。renderer・M は probe 段では使わない."""
    return v4sim.Config(
        base=pp.base, bot=bot, sd=pp.sd, lam=pp.lam, renderer=v4bat.RENDERER_R1PLUS, m=4
    )


def expected_units(cfg: v4sim.Config, kappa: float, dev: v4sim.DevResult) -> np.ndarray:
    """v4 ``expected_units`` と同じ式 (np.vectorize を表引きに置き換えた高速版。一致を test で pin)."""
    geom = v4sim.geometry()
    r_count = dev.succ.shape[1]
    n_q = v4sim._probe_n(dev.succ)
    lam = v4sim.lam_table(cfg.lam)
    parts = np.array([v4sim.clipped_parts(kappa * lam[c], cfg.sd) for c in range(5)])
    ep = parts[:, 0][n_q]
    em = parts[:, 1][n_q]
    pw = geom.probe_pw[cfg.base][:r_count][None]
    pf = geom.probe_pf[cfg.base][:r_count][None]
    live = 1.0 - cfg.bot
    diff = live * (ep - em + (1.0 - ep - em) * (1.0 - cfg.oov) * (pw - pf))
    s = diff.mean(-1)
    idx = {w: i for i, w in enumerate(v4bat.WORLDS)}
    fam = [(s[..., idx[a]] + s[..., idx[b]]) / 2.0 for a, b in v4bat.FAMILIES]
    return np.mean(fam, axis=0).mean(0)


def kappa_curve(pp: ProbePoint, bot: float, dev: v4sim.DevResult) -> v4sim.KappaCurve:
    """κ の格子上の E[d] (r ごと)。dev 段は κ に依らないので、同じ dev を全 κ で使う."""
    cfg = v4_config(pp, bot)
    r_count = dev.succ.shape[1]
    per_r = np.zeros((len(v4sim.KAPPA_GRID), v4bat.R_MAX))
    for i, kappa in enumerate(v4sim.KAPPA_GRID):
        per_r[i, :r_count] = expected_units(cfg, kappa, dev)
    cov = np.full(len(v4sim.KAPPA_GRID), float(v4sim.weather_coverage(dev.succ).mean()))
    return v4sim.KappaCurve(cfg=cfg, per_r=per_r, coverage=cov)


def _repeat_draws(
    pvals: np.ndarray, k: int, k_rep: float, rng: np.random.Generator
) -> np.ndarray:
    """(…, 4) の確率で K 回引いた各カテゴリの回数 (…, 4).

    1 回目を引き、2 回目以降の各回は確率 k_rep で 1 回目を反復し、残りは独立に引く。反復の回数は
    Binomial(K − 1, k_rep)、独立に引く回は多項分布で、各回を逐次に引くのと同じ分布になる。
    """
    shape = pvals.shape[:-1]
    cdf = np.cumsum(pvals, axis=-1)
    cdf /= cdf[..., -1:]
    first = np.minimum((rng.random(shape)[..., None] >= cdf).sum(-1), 3)
    reps = rng.binomial(k - 1, k_rep, size=shape)
    fresh = rng.multinomial(k - 1 - reps, pvals / pvals.sum(-1, keepdims=True))
    counts = fresh.astype(np.int64)
    np.put_along_axis(
        counts,
        first[..., None],
        np.take_along_axis(counts, first[..., None], -1) + 1 + reps[..., None],
        axis=-1,
    )
    return counts


def simulate_verdicts(
    pp: ProbePoint,
    bot: float,
    kappa: float,
    k: int,
    dev: v4sim.DevResult,
    rng: np.random.Generator,
) -> dict[str, float]:
    """κ を植えた probe 段と pipeline (C0 gate → ループ ⊥ gate → probe ⊥ gate → 3 分岐)。v4 と同じ式."""
    geom = v4sim.geometry()
    n_sims, r_count, n_w = dev.succ.shape[:3]
    n_q = len(v2bat.lever_probes())
    nq = v4sim._probe_n(dev.succ)
    lam = v4sim.lam_table(pp.lam)
    lvec = np.array([lam[c] for c in range(5)]) * kappa
    e = np.clip(
        lvec[nq] + pp.sd * rng.standard_normal((n_sims, r_count, n_w, 1)), -1.0, 1.0
    )
    live = 1.0 - bot
    mix = np.abs(e)
    pw = geom.probe_pw[pp.base][:r_count][None]
    pf = geom.probe_pf[pp.base][:r_count][None]
    base_live = live * (1.0 - mix) * (1.0 - v4sim.OOV)
    p_w = base_live * pw + np.where(e > 0, live * mix, 0.0)
    p_f = base_live * pf + np.where(e < 0, live * mix, 0.0)
    p_b = np.full_like(p_w, bot)
    rest = np.clip(1.0 - p_w - p_f - p_b, 0.0, 1.0)
    pvals = np.stack([p_w, p_f, p_b, rest], axis=-1)
    pvals /= pvals.sum(-1, keepdims=True)
    counts = _repeat_draws(pvals, k, pp.k_rep, rng)  # (N, R, W, 6, 4)
    denom = n_q * k
    s = (counts[..., 0] - counts[..., 1]).sum(-1) / denom
    idx = {w: i for i, w in enumerate(v4bat.WORLDS)}
    d = np.concatenate(
        [(s[:, :, idx[a]] + s[:, :, idx[b]]) / 2.0 for a, b in v4bat.FAMILIES], axis=1
    )
    comps = s.mean(axis=1)
    probe_bot = counts[..., 2].sum(axis=(1, 3)) / (r_count * denom)
    loop_bot = dev.loop_bot.sum(1) / (r_count * dev.steps)
    c0_bot = rng.binomial(r_count * denom, bot, size=n_sims) / (r_count * denom)
    flips, exact = _flip_matrix(d.shape[1], rng)
    verdict = decide(
        _flip_p(d - TAU, flips, exact), _flip_p(TAU - d, flips, exact), comps
    )
    verdict = np.where(
        v4sim.pipeline_gates(c0_bot, loop_bot, probe_bot),
        verdict,
        VERDICT_INVALID_BATTERY,
    )
    out = {v: float(np.mean(verdict == v)) for v in v4sim.VERDICTS}
    out["mean_C"] = float(d.mean())
    out["weather_coverage"] = float(v4sim.weather_coverage(dev.succ).mean())
    return out


def point_seed(*parts: object) -> int:
    """点ごとの決定的な sim seed (評価順に依らない): sha256(canonical JSON) の先頭 8 byte を little-endian で."""
    text = json.dumps(
        [SIM_SEED, *parts], sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "little")


def design_criteria(
    pp: ProbePoint,
    bot: float,
    curve: v4sim.KappaCurve,
    dev: v4sim.DevResult,
    k: int,
    seed_parts: tuple[object, ...],
) -> v4sim.Criteria:
    """C = 0 / τ / 2τ を植えて verdict の率を測る (v4 ``design_criteria`` と同じ 4 条件)."""
    r_count = dev.succ.shape[1]
    n_sims = dev.succ.shape[0]
    k_tau = curve.solve(TAU, r_count)
    k_plant = curve.solve(v4sim.DELTA_PLANT, r_count)
    cap = v4sim.size_cap(pp.sd, n_sims)
    if k_tau is None or k_plant is None:
        return v4sim.Criteria(k_tau, k_plant, None, None, 0.0, 0.0, 1.0, 1.0, cap)

    def run(kappa: float, level: str) -> dict[str, float]:
        return simulate_verdicts(
            pp,
            bot,
            kappa,
            k,
            dev,
            np.random.default_rng(point_seed(*seed_parts, level)),
        )

    at_plant = run(k_plant, "plant")
    at_zero = run(0.0, "zero")
    at_tau = run(k_tau, "tau")
    return v4sim.Criteria(
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


def with_axis(beh: Behaviour, **kw: object) -> Behaviour:
    return replace(beh, **kw)  # type: ignore[arg-type]
