"""探索を身体側へ (b) — 凍結模擬: 歩行の dev 段 (パラメトリック・経験点) と合成 pilot (pilot prereg §5).

CPU のみ。実モデルは呼ばない。

**dev 段 (パラメトリック) = 経験的混合方策** (v5 の分岐から探索指示の分岐を除いたもの。R1・v4 の表示回転)。
κ に依らない (モデルの dev 段の挙動は pilot で測る値であり、植える対象ではない)。未成功の signature で、
上から最初に当たった分岐をとる:

  0. ⊥ (確率 b)。行動なし (試行にも前回にも数えない)
  1. 同 signature の成功 → 規則 (成功済みなら常に)
  3. 描画した prompt が今回と同一の以前の訪問があり、その応答が表示中なら、確率 s_same でその応答を反復。
     無ければ、前回の label が表示中にあるとき確率 s_changed で前回を反復
  4. 同 weather の成功が 1 つ以上あれば確率 λ_dev で規則
  5. base (表示中の 4 選択肢上の分布)
  最後に、未成功の signature で ⊥ でない応答は確率 oov で Ω_dev 外の label に置き換わる (失敗に数える)。

分岐ごとに独立の一様乱数を使う。同一 prompt の記憶の key は **成功集合の bitmask** (R1 の描画は
(世界, 成功集合, signature, 表示順) の関数で、表示順は signature ごとに周で不変なので、bitmask は描画状態そのもの。
成功数の近似は使わない)。逐次の参照実装 (``simulate_dev_reference``) は同一 prompt を描画した messages の
完全一致で判定し、vectorize 版と同じ一様乱数で完全一致することを test で pin する。

乱数の結合 (Codex MEDIUM-1・DC-2): ``coupled`` なら描画が同一の世界は同じ一様乱数 (v4 の ``_state_keys`` /
``_coupled``)、``independent`` なら世界ごとに独立。写像は両端を審査する。

**経験点**: pilot の窓 M の終状態 (r block × 4 世界の成功集合と ⊥ 数) を r block 単位で復元抽出し、本登録の
R 個分の ``DevResult`` を作る。族内の共通 seed の結合をそのまま保つ。

**probe 段・基準**: v5 模擬 (``closed_loop_v5_sim``) の ``kappa_curve`` / ``design_criteria`` を import して使う
(``DevResult`` だけに依り、軸に依らない)。

**合成 pilot** (``synthetic_records``): 逐次参照の方策を mock model にして、凍結 plan どおりの記録を作る。
一様乱数は (描画 prompt の sha256, seed) から導くので、同一の request は同一の応答になる (決定的なモデルの写し)。
replay には非決定性の率を植えられる。scorer の回収 test・写像の end-to-end test・見取り図に使う。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

import numpy as np
from scripts import body_walk_battery as bat
from scripts import closed_loop_battery as v4bat
from scripts import closed_loop_sim as v4sim
from scripts import closed_loop_v5_sim as v5sim
from scripts.skill_lever_scorer import messages_sha256, parse_choice
from scripts.stage_b_battery import ACTIONS, WEATHER, dev_signatures

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    BaseTable = tuple[tuple[str, tuple[tuple[str, float], ...]], ...]

N_U: Final[int] = 6  # 1 呼び出しの一様乱数の列数
U_BOT, U_REP, U_SW, U_BASE, U_OOV, U_OOV_WHICH = range(N_U)
DEVS: Final = dev_signatures()
BITS: Final = (np.int64(1) << np.arange(bat.N_DEV, dtype=np.int64)).astype(np.int64)
SYNTH_BOTTOM_RAW: Final[str] = ""  # 合成 pilot の ⊥ の raw (parse すると None)
SYNTH_FLIP_SUFFIX: Final[str] = "。"  # 合成 replay の非決定性: raw だけを変える

base_table = v5sim.base_table


# ---------------------------------------------------------------- 挙動


@dataclass(frozen=True)
class Behaviour:
    """dev 段の方策の 1 点。base: weather → label → 確率 (位置効果なし、Ω_dev 上)."""

    lam_dev: float
    base: BaseTable
    bot: float
    oov: float
    s_same: float
    s_changed: float
    coupled: bool = True


def base_probs(beh: Behaviour, weather: str, options: Sequence[str]) -> np.ndarray:
    """表示中の 4 選択肢上の base 分布."""
    table = dict(dict(beh.base)[weather])
    p = np.array([table[o] for o in options], dtype=float)
    return p / p.sum()


def tempered_table(
    probs: Mapping[str, Mapping[str, float]], exponent: float
) -> BaseTable:
    """base を p^exponent で平らにして正規化した表 (見取り図の仮想値にだけ使う)."""
    out = {}
    for wt in WEATHER:
        om = v4bat.dev_omega(wt)
        p = np.array([probs[wt][a] for a in om], dtype=float) ** exponent
        out[wt] = dict(zip(om, (p / p.sum()).tolist(), strict=True))
    return base_table(out)


# ---------------------------------------------------------------- 前計算


@dataclass(frozen=True)
class Geo:
    """(r, t mod 12) ごとの前計算 (表示順は周で不変)."""

    sig_idx: np.ndarray  # (R, 12)
    dev_w: np.ndarray  # (R, 12)
    rule_pos: np.ndarray  # (R, 12, W)
    opt_act: np.ndarray  # (R, 12, 4)
    non_act: np.ndarray  # (R, 12, 2)
    pb: np.ndarray  # (R, 12, 4)


def geo(beh: Behaviour, r_values: Sequence[int]) -> Geo:
    rr = len(r_values)
    n_dev = bat.N_DEV
    sig_idx = np.zeros((rr, n_dev), dtype=np.int64)
    dev_w = np.zeros_like(sig_idx)
    rule_pos = np.zeros((rr, n_dev, len(v4bat.WORLDS)), dtype=np.int64)
    opt_act = np.zeros((rr, n_dev, bat.N_POSITIONS), dtype=np.int64)
    non_act = np.zeros((rr, n_dev, len(ACTIONS) - bat.N_POSITIONS), dtype=np.int64)
    pb = np.zeros((rr, n_dev, bat.N_POSITIONS))
    for i, r in enumerate(r_values):
        for tt in range(n_dev):
            sig = v4bat.loop_signature(r, tt)
            opts = bat.dev_options(r, tt)
            sig_idx[i, tt] = DEVS.index(sig)
            dev_w[i, tt] = WEATHER.index(sig[0])
            for wi, w in enumerate(v4bat.WORLDS):
                rule_pos[i, tt, wi] = opts.index(v4bat.rule(w)[sig[0]])
            opt_act[i, tt] = [ACTIONS.index(o) for o in opts]
            non_act[i, tt] = [ACTIONS.index(a) for a in ACTIONS if a not in opts]
            pb[i, tt] = base_probs(beh, sig[0], opts)
    return Geo(sig_idx, dev_w, rule_pos, opt_act, non_act, pb)


def _position(labels: np.ndarray, opt_act: np.ndarray) -> np.ndarray:
    """labels (…) の、表示位置 opt_act (…, 4) 上の位置 (無ければ −1)."""
    pos = np.full(labels.shape, -1)
    for p in range(bat.N_POSITIONS):
        pos = np.where(labels == opt_act[..., p], p, pos)
    return pos


# ---------------------------------------------------------------- dev 段 (vectorize)


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
    g = geo(beh, r_values)
    rr = len(r_values)
    n_w = len(v4bat.WORLDS)
    steps = bat.N_DEV * m
    succ = np.zeros((n, rr, n_w, bat.N_DEV), dtype=bool)
    last = np.full(succ.shape, -1, dtype=np.int64)
    # signature ごとの直近の ⊥ でない訪問: その時の成功集合 (bitmask) と応答
    mem_mask = np.full(succ.shape, -1, dtype=np.int64)
    mem_act = np.full(succ.shape, -1, dtype=np.int64)
    loop_bot = np.zeros((n, rr, n_w), dtype=np.int64)
    picks = np.full((n, rr, n_w, steps), -1) if record else None
    w_masks = np.array([[DEVS[j][0] == wt for j in range(bat.N_DEV)] for wt in WEATHER])
    rix = np.arange(rr)
    wix = np.arange(n_w)
    for t in range(steps):
        tt = t % bat.N_DEV
        j = g.sig_idx[:, tt]
        wi_w = g.dev_w[:, tt]
        u = rng.random((n, rr, n_w, N_U))
        if beh.coupled:
            u = v4sim._coupled(u, v4sim._state_keys(succ, None))
        sl = (slice(None), rix[:, None], wix[None, :], j[:, None])  # → (N, R, W)
        done = succ[sl]
        mask = (succ.astype(np.int64) * BITS).sum(-1)
        n_sw = (succ & w_masks[wi_w][None, :, None, :]).sum(-1)
        opt_act = np.broadcast_to(g.opt_act[:, tt][None, :, None, :], (n, rr, n_w, 4))
        rp = np.broadcast_to(g.rule_pos[:, tt][None], (n, rr, n_w))
        pb = np.broadcast_to(g.pb[:, tt][None, :, None, :], (n, rr, n_w, 4))
        prev = last[sl]
        prev_pos = _position(prev, opt_act)
        has_prev = prev_pos >= 0
        ma = mem_act[sl]
        mem_pos = _position(ma, opt_act)
        same_prompt = (mem_mask[sl] == mask) & (mem_pos >= 0)
        # 5. base
        pick = v5sim._pick_weighted(pb, u[..., U_BASE])
        # 4. 同 weather の成功
        pick = np.where((n_sw > 0) & (u[..., U_SW] < beh.lam_dev), rp, pick)
        # 3. 再訪の反復 (同一 prompt の以前の訪問が優先)
        pick = np.where(
            ~same_prompt & has_prev & (u[..., U_REP] < beh.s_changed), prev_pos, pick
        )
        pick = np.where(same_prompt & (u[..., U_REP] < beh.s_same), mem_pos, pick)
        # 1. 成功済み
        pick = np.where(done, rp, pick)
        is_bot = u[..., U_BOT] < beh.bot
        acted = ~is_bot
        oov = acted & ~done & (u[..., U_OOV] < beh.oov)
        act = np.take_along_axis(opt_act, pick[..., None], axis=-1)[..., 0]
        non = np.broadcast_to(g.non_act[:, tt][None, :, None, :], (n, rr, n_w, 2))
        act = np.where(
            oov, np.where(u[..., U_OOV_WHICH] >= 0.5, non[..., 1], non[..., 0]), act
        )
        success = acted & ~oov & (pick == rp)
        succ[sl] = done | success
        last[sl] = np.where(acted, act, prev)
        mem_mask[sl] = np.where(acted, mask, mem_mask[sl])
        mem_act[sl] = np.where(acted, act, ma)
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
    u: Sequence[float] | np.ndarray,
) -> str | None:
    """1 ステップの逐次版。vectorize 版と同じ一様乱数で同じ行動を返す (test で pin). ⊥ は None.

    last = その signature での直近の ⊥ でない応答、same_choice = 描画した prompt が今回と同一の以前の訪問の
    直近の ⊥ でない応答 (無ければ None)。
    """
    sig = v4bat.loop_signature(r, t)
    opts = bat.dev_options(r, t)
    rule = v4bat.rule(world)[sig[0]]
    if u[U_BOT] < beh.bot:
        return None
    if sig in state.succeeded:
        return rule
    pb = base_probs(beh, sig[0], opts)
    choice = opts[int(v5sim._pick_weighted(pb, np.array(u[U_BASE])))]
    if any(s[0] == sig[0] for s in state.succeeded) and u[U_SW] < beh.lam_dev:
        choice = rule
    if same_choice is not None and same_choice in opts:
        if u[U_REP] < beh.s_same:
            choice = same_choice
    elif last is not None and last in opts and u[U_REP] < beh.s_changed:
        choice = last
    if u[U_OOV] < beh.oov:
        non = [a for a in ACTIONS if a not in opts]
        return non[1] if u[U_OOV_WHICH] >= 0.5 else non[0]
    return choice


def simulate_dev_reference(
    beh: Behaviour, m: int, r_values: Sequence[int], n: int, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """vectorize 版と同じ乱数列で回す逐次参照。結合と「同一 prompt」は描画した messages の完全一致で判定する.

    返り値 = (succ (N, R, W, 12)、picks (N, R, W, T))。
    """
    worlds = v4bat.WORLDS
    rr = len(r_values)
    steps = bat.N_DEV * m
    states = {
        (i, r, w): v4bat.EMPTY_STATE for i in range(n) for r in r_values for w in worlds
    }
    last: dict[tuple[int, int, str, Any], str] = {}
    hist: dict[tuple[int, int, str, Any], list[tuple[Any, str]]] = {}
    picks = np.full((n, rr, len(worlds), steps), -1)
    for t in range(steps):
        u = rng.random((n, rr, len(worlds), N_U))
        new = {}
        for i in range(n):
            for ri, r in enumerate(r_values):
                sig = v4bat.loop_signature(r, t)
                msgs_of = {
                    w: bat.loop_messages(states[(i, r, w)], w, r, t) for w in worlds
                }
                for wi, w in enumerate(worlds):
                    st = states[(i, r, w)]
                    src = (
                        next(
                            k for k in range(wi + 1) if msgs_of[worlds[k]] == msgs_of[w]
                        )
                        if beh.coupled
                        else wi
                    )
                    key = (i, r, w, sig)
                    same = [c for mm, c in hist.get(key, []) if mm == msgs_of[w]]
                    choice = dev_choice_reference(
                        beh,
                        st,
                        w,
                        r,
                        t,
                        last.get(key),
                        same[-1] if same else None,
                        u[i, ri, src],
                    )
                    if choice is not None:
                        picks[i, ri, wi, t] = ACTIONS.index(choice)
                        last[key] = choice
                        hist.setdefault(key, []).append((msgs_of[w], choice))
                    new[(i, r, w)] = v4bat.update(st, w, sig, choice)
        states = new
    succ = np.zeros((n, rr, len(worlds), bat.N_DEV), dtype=bool)
    for (i, r, w), st in states.items():
        for s in st.succeeded:
            succ[i, r_values.index(r), worlds.index(w), DEVS.index(s)] = True
    return succ, picks


# ---------------------------------------------------------------- 経験点


def empirical_dev(
    chains: Mapping[str, Any], r_count: int, n: int, rng: np.random.Generator
) -> v4sim.DevResult:
    """pilot の窓 M の終状態を r block 単位で復元抽出した dev 段 (族内の共通 seed の結合を保つ).

    chains = scorer の ``chains`` の出力 (succ[b][w][j]・bot[b][w]・steps)。
    """
    succ = np.asarray(chains["succ"], dtype=bool)
    bot = np.asarray(chains["bot"], dtype=np.int64)
    idx = rng.integers(0, succ.shape[0], size=(n, r_count))
    return v4sim.DevResult(
        succ=succ[idx], loop_bot=bot[idx], steps=int(chains["steps"])
    )


# ---------------------------------------------------------------- 合成 pilot


def _uniforms(tag: str, sha: str, seed: int) -> np.ndarray:
    """(prompt sha, seed) から決まる一様乱数 (同一の request は同一の乱数)."""
    h = hashlib.sha256(f"{tag}|{sha}|{seed}".encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "little")).random(N_U)


def synthetic_records(
    beh: Behaviour,
    *,
    tag: str = "synthetic",
    replay_flip: float = 0.0,
    stop_after: int | None = None,
    policy: Callable[[bat.PilotKey, v4bat.State, tuple[str, ...]], str | None]
    | None = None,
) -> list[dict[str, Any]]:
    """凍結 plan を上から呼ぶ合成 run (記録の dict の list、scorer の schema どおり).

    既定の方策は逐次参照 (``dev_choice_reference``)。``policy`` を渡すと (key, 状態, 表示中の選択肢) → raw で置き換える
    (test の手で数えられる場面用)。replay は元の raw を返し、確率 ``replay_flip`` で raw だけを変える。
    """
    states: dict[tuple[str, int], v4bat.State] = {}
    last: dict[tuple[str, int, Any], str] = {}
    hist: dict[tuple[str, int, Any], dict[str, str]] = {}
    orig: dict[tuple[str, int, int], tuple[str, str]] = {}
    out: list[dict[str, Any]] = []
    for i, key in enumerate(bat.pilot_plan()):
        if stop_after is not None and i >= stop_after:
            break
        w, r, t = key.world, key.replicate, key.step
        seed = bat.pilot_seed(r, t)
        if key.phase == bat.PHASE_LOOP:
            st = states.get((w, r), v4bat.EMPTY_STATE)
            sha = messages_sha256(bat.loop_messages(st, w, r, t))
            sig = v4bat.loop_signature(r, t)
            ck = (w, r, sig)
            if policy is not None:
                raw = policy(key, st, bat.dev_options(r, t))
                choice = None if raw is None else parse_choice(raw)
                raw = SYNTH_BOTTOM_RAW if raw is None else raw
            else:
                choice = dev_choice_reference(
                    beh,
                    st,
                    w,
                    r,
                    t,
                    last.get(ck),
                    hist.get(ck, {}).get(sha),
                    _uniforms(tag, sha, seed),
                )
                raw = SYNTH_BOTTOM_RAW if choice is None else choice
            if choice is not None:
                last[ck] = choice
                hist.setdefault(ck, {})[sha] = choice
            states[(w, r)] = v4bat.update(st, w, sig, choice)
            orig[(w, r, t)] = (raw, sha)
        else:
            raw, sha = orig[(w, r, t)]
            if _uniforms(f"{tag}|replay", sha, seed)[0] < replay_flip:
                raw += SYNTH_FLIP_SUFFIX
        out.append(
            {
                "call_index": i,
                "phase": key.phase,
                "world": w,
                "replicate": r,
                "step": t,
                "seed": seed,
                "prompt_sha256": sha,
                "raw": raw,
                "parsed": parse_choice(raw),
            }
        )
    return out
