"""閉ループ分散 pilot — 世界・ループ状態・renderer・seed・呼び出し plan と機械検査 (prereg v4).

事前登録 = ``experiments/20260927-closed-loop-divergence-pilot/prereg.md``。凍結 v2 battery
(``scripts/skill_lever_battery.py``) の規則表・probe・layout (π_r と Ω_q の巡回)・probe の decoding seed・
probe 部 renderer・実行条件を import し、本モジュールは **閉ループの部品** だけを定める。

* 世界 = v2 の 4 arm (A / A_rot / B / B_rot)。族 {A, A_rot}・{B, B_rot}。ペルソナは経験する世界だけで
  個体化する (persona YAML・初期の種なし、全員が空状態から始まる)。
* ループ段: replicate r・世界 w ごとに、開発 12 signature を π_r 順に M 周する。状況 t の選択肢
  Ω_dev = 4 世界の規則がその weather に指す 4 行動を (r + t) mod 4 だけ巡回したもの。成否は決定的
  (行動 = 世界の規則[weather] で成功)。
* 状態 = aggregator が更新する: 成功した signature の集合 (R1) と、試した (signature, 行動) の集合 (R1+)。
  renderer は状態から決定的に文字列を作る。行の順は π_r に固定し、変わるのは行の有無だけ。
* seed: ループ段は ``loop_seed(r, t)`` (世界を引数に取らない = 4 世界で共有)、probe 段・C0 は v2 の
  ``sample_seed`` をそのまま使う。両者の値域は互いに素 (``check_seed_disjoint``)。

世界名は prompt・状態に出さない (非漏洩、``check_non_leakage``)。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from scripts import skill_lever_battery as v2
from scripts.stage_b_battery import ACTIONS, SIGMA, dev_signatures
from scripts.stage_b_scorer import (
    Probe,
    Snapshot,
    StageBData,
    integrity_violations,
    signature_text,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from scripts.stage_b_battery import Signature

WORLDS: Final[tuple[str, ...]] = v2.LEVER_ARMS
FAMILIES: Final[tuple[tuple[str, str], ...]] = v2.FAMILIES
ARM_C0: Final[str] = v2.ARM_C0

RENDERER_R1: Final[str] = "R1"
RENDERER_R1PLUS: Final[str] = "R1plus"
RENDERERS: Final[tuple[str, ...]] = (RENDERER_R1, RENDERER_R1PLUS)

R_MAX: Final[int] = 12  # user 裁定 (v2/v3 と同じ)
K_MAX: Final[int] = 20
M_CHOICES: Final[tuple[int, ...]] = (3, 4)  # ADR D4
N_DEV: Final[int] = 12  # 開発 signature 数 (1 周の長さ)
T_MAX: Final[int] = N_DEV * max(M_CHOICES)
N_POSITIONS: Final[int] = v2.N_POSITIONS
LOOP_SEED_BASE: Final[int] = 21_260_926
LOOP_SEED_STRIDE: Final[int] = 1000

# ---- 状態ブロックの固定文言 (prereg v4 §2.2)
STATE_HEADER: Final[str] = v2.STATE_HEADER
SUCCESS_MARK: Final[str] = "(成功あり)"
EMPTY_R1: Final[str] = "(成功した記録はない)"
R1PLUS_SUCCESS_HEADER: Final[str] = "成功した行動:"
R1PLUS_TRIED_HEADER: Final[str] = "試した行動 (成否を問わない):"
EMPTY_SECTION: Final[str] = "(なし)"
TRIED_SEP: Final[str] = "、"

# ---- 呼び出し plan の phase
PHASE_C0: Final[str] = "c0"
PHASE_LOOP: Final[str] = "loop"
PHASE_PROBE: Final[str] = "probe"
PHASE_REPLAY: Final[str] = "replay"


def rule(world: str) -> dict[str, str]:
    """世界の規則表 weather → 成功する行動 (v2 と同じ)."""
    return v2.rule(world)


# ------------------------------------------------------------------ loop


def n_steps(m: int) -> int:
    return N_DEV * m


def loop_signature(r: int, t: int) -> Signature:
    """ループ段 t の状況 = π_r の (t mod 12) 番目の開発 signature."""
    return v2.layout(r).entry_order[t % N_DEV]


def dev_omega(weather: str) -> tuple[str, ...]:
    """正準順の Ω_dev = 4 世界の規則が weather に指す行動 (相異なる、σ で閉じる)."""
    return tuple(rule(w)[weather] for w in WORLDS)


def dev_options(r: int, t: int) -> tuple[str, ...]:
    """表示順の Ω_dev: 正準順を (r + t) mod 4 だけ巡回 (ADR D4)."""
    om = dev_omega(loop_signature(r, t)[0])
    shift = (r + t) % N_POSITIONS
    return om[shift:] + om[:shift]


def loop_seed(r: int, t: int) -> int:
    """ループ段の decoding seed。世界を引数に取らないので 4 世界で共有する."""
    return LOOP_SEED_BASE + LOOP_SEED_STRIDE * r + t


def world_order(r: int) -> tuple[str, ...]:
    """(r, t) / (r, q, k) の block 内で 4 世界を呼ぶ順 = WORLDS を r mod 4 だけ巡回."""
    shift = r % len(WORLDS)
    return WORLDS[shift:] + WORLDS[:shift]


# ------------------------------------------------------------------ state


@dataclass(frozen=True)
class State:
    """aggregator の状態。成否は記録から scorer が導出する (driver の申告を使わない)."""

    succeeded: frozenset[Signature] = frozenset()
    tried: frozenset[tuple[Signature, str]] = frozenset()


EMPTY_STATE: Final[State] = State()


def is_success(world: str, sig: Signature, choice: str | None) -> bool:
    """決定的な成否。⊥ (None) と Ω_dev 外は失敗 (規則の行動は常に Ω_dev 内)."""
    return choice is not None and choice == rule(world)[sig[0]]


def update(state: State, world: str, sig: Signature, choice: str | None) -> State:
    """1 ステップの更新。⊥ は試行に数えない (行動が無い)。語彙内の label は試行に数える."""
    tried = state.tried
    if choice is not None and choice in ACTIONS:
        tried = tried | {(sig, choice)}
    succeeded = state.succeeded
    if is_success(world, sig, choice):
        succeeded = succeeded | {sig}
    return State(succeeded=succeeded, tried=tried)


# ---------------------------------------------------------------- renderer


def success_line(sig: Signature, action: str) -> str:
    return f"条件: {signature_text(sig)} → 行動: {action} {SUCCESS_MARK}"


def tried_line(sig: Signature, actions: Sequence[str]) -> str:
    return f"条件: {signature_text(sig)} → 試した: {TRIED_SEP.join(actions)}"


def success_lines(state: State, world: str, r: int) -> list[str]:
    table = rule(world)
    return [
        success_line(sig, table[sig[0]])
        for sig in v2.layout(r).entry_order
        if sig in state.succeeded
    ]


def tried_lines(state: State, r: int) -> list[str]:
    out = []
    for sig in v2.layout(r).entry_order:
        acts = [a for a in ACTIONS if (sig, a) in state.tried]
        if acts:
            out.append(tried_line(sig, acts))
    return out


def render_state(state: State, world: str, r: int, renderer: str) -> str:
    """状態ブロック。行の順は π_r、label の並びは ACTIONS 順 (試した順は使わない)."""
    succ = success_lines(state, world, r)
    if renderer == RENDERER_R1:
        return "\n".join([STATE_HEADER, *(succ or [EMPTY_R1])])
    if renderer == RENDERER_R1PLUS:
        tried = tried_lines(state, r)
        return "\n".join(
            [
                STATE_HEADER,
                R1PLUS_SUCCESS_HEADER,
                *(succ or [EMPTY_SECTION]),
                R1PLUS_TRIED_HEADER,
                *(tried or [EMPTY_SECTION]),
            ]
        )
    msg = f"unknown renderer {renderer!r}"
    raise ValueError(msg)


def render_situation(sig: Signature, options: Sequence[str]) -> str:
    """状況部。v2 の probe 部 (``render_probe``) と同じ書式 (test で byte 一致を pin)."""
    return (
        f"状況: 天候={sig[0]}、時刻={sig[1]}、同伴={sig[2]}。\n"
        f"次の行動から 1 つだけ選び、行動名だけを答えよ: {'、'.join(options)}"
    )


def _messages(user: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": v2.SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def loop_messages(
    state: State, world: str, r: int, t: int, renderer: str
) -> list[dict[str, str]]:
    block = render_state(state, world, r, renderer)
    situation = render_situation(loop_signature(r, t), dev_options(r, t))
    return _messages(f"{block}\n\n{situation}")


def probe_messages(
    state: State, world: str, r: int, qi: int, renderer: str
) -> list[dict[str, str]]:
    probe = v2.lever_probes()[qi]
    block = render_state(state, world, r, renderer)
    return _messages(f"{block}\n\n{v2.render_probe(probe, v2.layout(r))}")


def c0_messages(r: int, qi: int) -> list[dict[str, str]]:
    """N0 = C0: 状態ブロックなし。v2 の C0 と byte 一致する."""
    return v2.render_messages(ARM_C0, v2.lever_probes()[qi], v2.layout(r))


def prompt_bytes(messages: Sequence[Mapping[str, str]]) -> int:
    return v2.prompt_bytes(messages)


# ---------------------------------------------------------------- plan


@dataclass(frozen=True)
class PlanKey:
    """呼び出し plan の 1 件。loop は step、probe / c0 は (probe_id, k) を持つ.

    replay は元の呼び出しの key (phase・world・replicate・step / probe_id・k) を ``of`` に持つ。
    """

    phase: str
    world: str
    replicate: int
    step: int | None = None
    probe_id: str | None = None
    k: int | None = None
    of: PlanKey | None = None


def replay_targets(r: int, m: int) -> list[PlanKey]:
    """決定性 replay の登録部分集合 (r ごとに 9 件、prereg v4 §7)."""
    order = world_order(r)
    last = n_steps(m) - 1
    q0 = v2.lever_probes()[0].probe_id
    out = [PlanKey(PHASE_LOOP, order[0], r, step=0)]
    out += [PlanKey(PHASE_LOOP, w, r, step=last) for w in order]
    out += [PlanKey(PHASE_PROBE, w, r, probe_id=q0, k=0) for w in order]
    return out


def plan(r_count: int, k_count: int, m: int) -> list[PlanKey]:
    """凍結する呼び出し順。call_index = この list の位置.

    1. C0 を全て ((r, q, k) の辞書順)。
    2. r ごとに: ループ段 (t ごとに 4 世界を ``world_order(r)`` の順) → probe 段 ((q, k) ごとに同じ順)。
    3. 最後に決定性 replay (r ごとに ``replay_targets``)。判定には使わない。
    """
    probes = v2.lever_probes()
    out = [
        PlanKey(PHASE_C0, ARM_C0, r, probe_id=p.probe_id, k=k)
        for r in range(r_count)
        for p in probes
        for k in range(k_count)
    ]
    for r in range(r_count):
        order = world_order(r)
        out += [
            PlanKey(PHASE_LOOP, w, r, step=t) for t in range(n_steps(m)) for w in order
        ]
        out += [
            PlanKey(PHASE_PROBE, w, r, probe_id=p.probe_id, k=k)
            for p in probes
            for k in range(k_count)
            for w in order
        ]
    for r in range(r_count):
        out += [
            PlanKey(PHASE_REPLAY, t.world, r, t.step, t.probe_id, t.k, of=t)
            for t in replay_targets(r, m)
        ]
    return out


def n_main_calls(r_count: int, k_count: int, m: int) -> int:
    """判定に使う呼び出し数 (replay を除く) = R (30K + 48M)。"""
    n_q = len(v2.lever_probes())
    return r_count * (n_q * k_count + len(WORLDS) * (n_steps(m) + n_q * k_count))


# ------------------------------------------------------------------ checks


def _extreme_states(world: str) -> list[State]:
    """byte 予算・非漏洩の検査に使う状態: 空・全成功・全成功かつ全語彙を試行."""
    devs = dev_signatures()
    full = frozenset(devs)
    tried_all = frozenset((s, a) for s in devs for a in ACTIONS)
    tried_rule = frozenset((s, rule(world)[s[0]]) for s in devs)
    return [
        EMPTY_STATE,
        State(succeeded=full, tried=tried_rule),
        State(succeeded=full, tried=tried_all),
    ]


def max_prompt_bytes(r_count: int = R_MAX) -> int:
    """全 renderer・全世界・極端な状態・全ループ段と probe での最大 byte."""
    best = 0
    for r in range(r_count):
        for renderer in RENDERERS:
            for w in WORLDS:
                for st in _extreme_states(w):
                    for t in range(N_DEV):
                        best = max(
                            best, prompt_bytes(loop_messages(st, w, r, t, renderer))
                        )
                    for qi in range(len(v2.lever_probes())):
                        best = max(
                            best, prompt_bytes(probe_messages(st, w, r, qi, renderer))
                        )
    return best


def check_prompt_budget(r_count: int = R_MAX) -> list[str]:
    """描画 prompt が切り詰められえないことの静的保証 (token ≤ UTF-8 byte、v2 と同じ上限)."""
    problems: list[str] = []
    if v2.MAX_PROMPT_BYTES + v2.CHAT_TEMPLATE_OVERHEAD + v2.NUM_PREDICT > v2.NUM_CTX:
        problems.append("byte budget does not fit num_ctx")
    n = max_prompt_bytes(r_count)
    if n > v2.MAX_PROMPT_BYTES:
        problems.append(f"max prompt {n} bytes > {v2.MAX_PROMPT_BYTES}")
    return problems


def check_seed_disjoint(
    r_count: int = R_MAX, k_count: int = K_MAX, t_count: int = T_MAX
) -> list[str]:
    """ループ段の seed と probe の seed が 1 つも衝突しない (全組)."""
    loop = {loop_seed(r, t) for r in range(r_count) for t in range(t_count)}
    probe = {
        v2.sample_seed(r, qi, k)
        for r in range(r_count)
        for qi in range(len(v2.lever_probes()))
        for k in range(k_count)
    }
    problems = []
    if len(loop) != r_count * t_count:
        problems.append("loop seeds are not unique")
    if loop & probe:
        problems.append(f"{len(loop & probe)} loop seeds collide with probe seeds")
    return problems


def check_dev_options(r_count: int = R_MAX) -> list[str]:
    """Ω_dev は 4 世界の規則と 1 対 1・σ で閉じ、巡回量 (r + t) mod 4 が各周の中で 3 回ずつ使われる.

    weather ごとの位置の均衡は (r + t) mod 4 の巡回 (ADR D4 の文言) では保証されない。その位置効果は
    power 模擬が実際の巡回で扱う (prereg v4 §6)。
    """
    problems: list[str] = []
    for sig in dev_signatures():
        om = dev_omega(sig[0])
        if len(set(om)) != len(WORLDS):
            problems.append(f"{sig}: Ω_dev is not distinct")
        if {SIGMA[o] for o in om} != set(om):
            problems.append(f"{sig}: Ω_dev is not closed under σ")
        if [rule(w)[sig[0]] for w in WORLDS] != list(om):
            problems.append(f"{sig}: Ω_dev is not the worlds' rules")
    for r in range(r_count):
        for m in range(max(M_CHOICES)):
            shifts = [
                dev_options(r, t).index(dev_omega(loop_signature(r, t)[0])[0])
                for t in range(N_DEV * m, N_DEV * (m + 1))
            ]
            counts = [shifts.count(s) for s in range(N_POSITIONS)]
            if len(set(counts)) != 1:
                problems.append(f"r={r} cycle {m}: rotation shifts unbalanced")
    return problems


def check_state_neutrality(r_count: int = R_MAX) -> list[str]:
    """空状態の文字列は全世界で同一。行の順は π_r・状態の包含に単調 (R1 ⊂ R1+)."""
    problems: list[str] = []
    for r in range(r_count):
        for renderer in RENDERERS:
            empties = {render_state(EMPTY_STATE, w, r, renderer) for w in WORLDS}
            if len(empties) != 1:
                problems.append(f"r={r} {renderer}: empty state differs across worlds")
        for w in WORLDS:
            st = _extreme_states(w)[1]
            r1 = render_state(st, w, r, RENDERER_R1).splitlines()[1:]
            r1p = render_state(st, w, r, RENDERER_R1PLUS).splitlines()
            if r1p[2 : 2 + len(r1)] != r1:
                problems.append(f"r={r} {w}: R1 lines are not embedded in R1plus")
    return problems


def check_c0_is_v2(r_count: int = R_MAX) -> list[str]:
    """N0 = C0 の prompt は v2 の C0 と同じ関数で描く・状況部は v2 の probe 部と byte 一致."""
    problems: list[str] = []
    for r in range(r_count):
        lay = v2.layout(r)
        for qi, p in enumerate(v2.lever_probes()):
            if c0_messages(r, qi) != v2.render_messages(ARM_C0, p, lay):
                problems.append(f"r={r} {p.probe_id}: C0 differs from v2")
            situ = render_situation(p.signature, lay.option_order[p.probe_id])
            if situ != v2.render_probe(p, lay):
                problems.append(f"r={r} {p.probe_id}: situation format differs")
    return problems


def check_world_order(r_count: int) -> list[str]:
    """R が 4 の倍数のとき、各世界が block 内の各位置に同数回来る."""
    if r_count % len(WORLDS):
        return [f"R={r_count} is not a multiple of {len(WORLDS)}"]
    counts = {(w, pos): 0 for w in WORLDS for pos in range(len(WORLDS))}
    for r in range(r_count):
        for pos, w in enumerate(world_order(r)):
            counts[(w, pos)] += 1
    return [] if len(set(counts.values())) == 1 else ["world order is unbalanced"]


def check_non_leakage(r_count: int = R_MAX) -> list[str]:
    """v2 と同じ integrity 検査 (``stage_b_scorer.integrity_violations``) + 世界名 token."""
    ps = v2.lever_probes()
    probe_sets = (
        tuple(
            Probe(p.probe_id, p.omega, p.pointed[WORLDS[0]], p.pointed[WORLDS[2]])
            for p in ps
        ),
        tuple(
            Probe(p.probe_id, p.omega, p.pointed[WORLDS[1]], p.pointed[WORLDS[3]])
            for p in ps
        ),
    )
    problems: list[str] = []
    texts: list[str] = []
    snapshots = []
    for r in range(r_count):
        for renderer in RENDERERS:
            for w in WORLDS:
                for n, st in enumerate(_extreme_states(w)):
                    pre = tuple(st.succeeded) + tuple(s for s, _ in st.tried)
                    snapshots.append(
                        Snapshot(
                            ind_id=f"r{r}-{renderer}-{w}-{n}",
                            preconditions=pre,
                            text=render_state(st, w, r, renderer),
                        )
                    )
                    texts.extend(
                        loop_messages(st, w, r, t, renderer)[1]["content"]
                        for t in range(N_DEV)
                    )
                    texts.extend(
                        probe_messages(st, w, r, qi, renderer)[1]["content"]
                        for qi in range(len(ps))
                    )
    for probe_set in probe_sets:
        data = StageBData(
            probes=probe_set,
            probe_signatures={p.probe_id: p.signature for p in ps},
            dev_signatures=frozenset(dev_signatures()),
            di=(),
            di_ablation=(),
            ci=(),
            snapshots=tuple(snapshots),
            probe_prompts=tuple(texts),
        )
        problems.extend(integrity_violations(data))
    tokens = ("a_rot", "b_rot", "c0", "arm", "world", "r1plus")
    for text in texts:
        low = text.lower()
        problems.extend(f"prompt contains {tok!r}" for tok in tokens if tok in low)
    return sorted(set(problems))


def battery_report(r_count: int) -> dict[str, object]:
    return {
        "n_probes": len(v2.lever_probes()),
        "n_dev": len(dev_signatures()),
        "max_prompt_bytes": max_prompt_bytes(max(r_count, R_MAX)),
        "pointed_bijection": v2.check_pointed_bijection(),
        "position_balance": v2.check_position_balance(r_count),
        "dev_options": check_dev_options(max(r_count, R_MAX)),
        "seed_disjoint": check_seed_disjoint(),
        "state_neutrality": check_state_neutrality(max(r_count, R_MAX)),
        "c0_is_v2": check_c0_is_v2(max(r_count, R_MAX)),
        "world_order": check_world_order(r_count),
        "non_leakage": check_non_leakage(r_count),
        "prompt_budget": check_prompt_budget(max(r_count, R_MAX)),
    }
