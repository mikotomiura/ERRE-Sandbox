"""閉ループ v5 前段 — 挙動較正 pilot の軸・renderer・plan と機械検査 (pilot prereg).

事前登録 = ``experiments/20260928-closed-loop-v5-calibration-pilot/prereg.md``。設計の正本は
scoping ADR ``.steering/20260928-closed-loop-v5-scoping/design-final.md`` (FROZEN) の §3・§5。
凍結 v4 battery (``scripts/closed_loop_battery.py``) の世界・規則・状態・更新・renderer・状況部を import し、
本モジュールは **2 つの候補軸の差分だけ** を定める。

* 軸 B = R1 (試した行なし) + 周で変わる表示回転 (r + t + ⌊t/12⌋) mod 4。
* 軸 C = R1+ (v4 と同じ試した行) + 開発段の user 文にだけ置く探索指示 (固定 1 文、``EXPLORE_SENTENCE``)。
  指示は状態ブロックと状況部の間に独立の段落で置く。状況部・system prompt は v4 と同じ。
* pilot = ループ段のみ (probe・C0・replay なし)、r ∈ {12, 13, 14, 15} (user 裁定 DP-1)、M = 8 (user 裁定 DP-4)、
  4 世界、軸ごと 1 回 = 3,072 呼び出し。候補の M ごとに t < 12M の記録だけで測る。seed は v2・v4 と値域が互いに素な新しい基点 (``check_seed_disjoint``)。

世界名は prompt に出さない (``check_non_leakage``)。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from scripts import closed_loop_battery as v4
from scripts import skill_lever_battery as v2
from scripts.stage_b_battery import ACTIONS, WEATHER, dev_signatures
from scripts.stage_b_scorer import (
    Probe,
    Snapshot,
    StageBData,
    integrity_violations,
)

AXIS_B: Final[str] = "B"
AXIS_C: Final[str] = "C"
AXES: Final[tuple[str, ...]] = (AXIS_B, AXIS_C)
RENDERER_OF: Final[dict[str, str]] = {
    AXIS_B: v4.RENDERER_R1,
    AXIS_C: v4.RENDERER_R1PLUS,
}

# ---- 探索指示 (user 裁定 DP-2。凍結後は変更しない・反復調整しない)
EXPLORE_SENTENCE: Final[str] = (
    "成功した記録の無い条件では、まだ試していない行動も試して、成功する行動を探すこと。"
)

# ---- pilot の範囲 (ADR §3.2。r は user 裁定 DP-1 で {12..15}、M は DP-4 で 8)
PILOT_R: Final[tuple[int, ...]] = (12, 13, 14, 15)
PILOT_M: Final[int] = 8
M_WINDOWS: Final[tuple[int, ...]] = (4, 6, 8)  # v5 の候補 M。測定は t < 12M の窓ごと
N_DEV: Final[int] = v4.N_DEV
N_POSITIONS: Final[int] = v4.N_POSITIONS
PILOT_T: Final[int] = N_DEV * PILOT_M
PILOT_SEED_BASE: Final[int] = 22_260_928
PILOT_SEED_STRIDE: Final[int] = 1000
# v5 本番が使いうる範囲 (候補 R ≤ 12 → r < 12、候補 M ≤ 8 → t < 96)。pilot はこれと重ならない。
V5_R_MAX: Final[int] = 12
V5_T_MAX: Final[int] = N_DEV * 8
# 他の登録で使う seed の検査範囲 (v2 の probe は r < 16 まで、v4 のループ段は v5 の範囲まで広げて検査)
OTHER_R_MAX: Final[int] = 16
OTHER_K_MAX: Final[int] = v4.K_MAX

PHASE_LOOP: Final[str] = v4.PHASE_LOOP


# ------------------------------------------------------------------ axis


def shift(axis: str, r: int, t: int) -> int:
    """表示回転の巡回量。B は周ごとに 1 ずつ進む、C は v4 と同じ."""
    if axis == AXIS_B:
        return (r + t + t // N_DEV) % N_POSITIONS
    if axis == AXIS_C:
        return (r + t) % N_POSITIONS
    msg = f"unknown axis {axis!r}"
    raise ValueError(msg)


def dev_options(axis: str, r: int, t: int) -> tuple[str, ...]:
    """表示順の Ω_dev: 正準順 (v4 ``dev_omega``) を ``shift`` だけ巡回."""
    om = v4.dev_omega(v4.loop_signature(r, t)[0])
    s = shift(axis, r, t)
    return om[s:] + om[:s]


def render_state(state: v4.State, world: str, r: int, axis: str) -> str:
    return v4.render_state(state, world, r, RENDERER_OF[axis])


def loop_user_text(state: v4.State, world: str, r: int, t: int, axis: str) -> str:
    block = render_state(state, world, r, axis)
    situation = v4.render_situation(v4.loop_signature(r, t), dev_options(axis, r, t))
    if axis == AXIS_C:
        return f"{block}\n\n{EXPLORE_SENTENCE}\n\n{situation}"
    return f"{block}\n\n{situation}"


def loop_messages(
    state: v4.State, world: str, r: int, t: int, axis: str
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": v2.SYSTEM_PROMPT},
        {"role": "user", "content": loop_user_text(state, world, r, t, axis)},
    ]


def pilot_seed(r: int, t: int) -> int:
    """Pilot の decoding seed。軸・世界を引数に取らない (両軸・4 世界で共有 = 共通乱数)."""
    return PILOT_SEED_BASE + PILOT_SEED_STRIDE * r + t


# ---------------------------------------------------------------- plan


@dataclass(frozen=True)
class PilotKey:
    axis: str
    world: str
    replicate: int
    step: int


def axis_order(r: int) -> tuple[str, ...]:
    """(r, t) の block 内で軸を呼ぶ順。r の偶奇で B → C / C → B."""
    return AXES if r % 2 == 0 else AXES[::-1]


def pilot_plan() -> list[PilotKey]:
    """凍結する呼び出し順。call_index = この list の位置.

    r ごとに、t = 0..95 の各 t で、軸を ``axis_order(r)`` の順に、各軸の中で 4 世界を v4 ``world_order(r)`` の順に呼ぶ。
    """
    return [
        PilotKey(axis, w, r, t)
        for r in PILOT_R
        for t in range(PILOT_T)
        for axis in axis_order(r)
        for w in v4.world_order(r)
    ]


def n_pilot_calls() -> int:
    return len(AXES) * len(v4.WORLDS) * len(PILOT_R) * PILOT_T


# ------------------------------------------------------------------ checks


def _extreme_states(world: str) -> list[v4.State]:
    """Byte 予算・非漏洩の検査に使う状態: 空・全成功・全成功かつ全語彙を試行 (v4 と同じ)."""
    devs = dev_signatures()
    full = frozenset(devs)
    tried_all = frozenset((s, a) for s in devs for a in ACTIONS)
    tried_rule = frozenset((s, v4.rule(world)[s[0]]) for s in devs)
    return [
        v4.EMPTY_STATE,
        v4.State(succeeded=full, tried=tried_rule),
        v4.State(succeeded=full, tried=tried_all),
    ]


def max_prompt_bytes() -> int:
    best = 0
    for r in PILOT_R:
        for axis in AXES:
            for w in v4.WORLDS:
                for st in _extreme_states(w):
                    for t in range(PILOT_T):
                        best = max(
                            best, v2.prompt_bytes(loop_messages(st, w, r, t, axis))
                        )
    return best


def check_prompt_budget() -> list[str]:
    """描画 prompt が切り詰められえない (v2 / v4 と同じ上限 3,000 byte)."""
    problems: list[str] = []
    if v2.MAX_PROMPT_BYTES + v2.CHAT_TEMPLATE_OVERHEAD + v2.NUM_PREDICT > v2.NUM_CTX:
        problems.append("byte budget does not fit num_ctx")
    n = max_prompt_bytes()
    if n > v2.MAX_PROMPT_BYTES:
        problems.append(f"max prompt {n} bytes > {v2.MAX_PROMPT_BYTES}")
    return problems


def pilot_seeds() -> set[int]:
    return {pilot_seed(r, t) for r in PILOT_R for t in range(PILOT_T)}


def check_seed_disjoint() -> list[str]:
    """Pilot の seed は一意で、v2 probe・v4 ループ段 (v5 が使いうる範囲まで) と 1 つも衝突しない.

    v5 本番のループ段の seed 基点は未定。v5 prereg は ``pilot_seeds()`` との非交差を機械検査する (本 prereg §2.4)。
    """
    problems: list[str] = []
    seeds = pilot_seeds()
    if len(seeds) != len(PILOT_R) * PILOT_T:
        problems.append("pilot seeds are not unique")
    v2_probe = {
        v2.sample_seed(r, qi, k)
        for r in range(OTHER_R_MAX)
        for qi in range(len(v2.lever_probes()))
        for k in range(OTHER_K_MAX)
    }
    v4_loop = {v4.loop_seed(r, t) for r in range(OTHER_R_MAX) for t in range(V5_T_MAX)}
    if seeds & v2_probe:
        problems.append(
            f"{len(seeds & v2_probe)} pilot seeds collide with v2 probe seeds"
        )
    if seeds & v4_loop:
        problems.append(
            f"{len(seeds & v4_loop)} pilot seeds collide with v4 loop seeds"
        )
    return problems


def check_replicates() -> list[str]:
    """Pilot の r は v5 本番が使いうる r (< 12) と重ならず、4 の倍数個で mod 4 が一巡する (DP-1)."""
    problems: list[str] = []
    if any(r < V5_R_MAX for r in PILOT_R):
        problems.append("pilot replicates overlap the v5 layouts (r < 12)")
    if sorted(r % 4 for r in PILOT_R) != [0, 1, 2, 3]:
        problems.append("pilot replicates do not cover r mod 4")
    return problems


def check_rotation_balance() -> list[str]:
    """両軸で、各周の中で巡回量 0〜3 がそれぞれ 3 回ずつ使われる。B は周ごとに巡回量が変わる (ADR §5)."""
    problems: list[str] = []
    for axis in AXES:
        for r in PILOT_R:
            for lap in range(PILOT_M):
                shifts = [
                    dev_options(axis, r, t).index(
                        v4.dev_omega(v4.loop_signature(r, t)[0])[0]
                    )
                    for t in range(N_DEV * lap, N_DEV * (lap + 1))
                ]
                if [shifts.count(s) for s in range(N_POSITIONS)] != [3] * N_POSITIONS:
                    problems.append(
                        f"{axis} r={r} lap {lap}: rotation shifts unbalanced"
                    )
    for r in PILOT_R:
        for t in range(N_DEV * (PILOT_M - 1)):
            if dev_options(AXIS_B, r, t) == dev_options(AXIS_B, r, t + N_DEV):
                problems.append(f"B r={r} t={t}: rotation does not change across laps")
            if dev_options(AXIS_C, r, t) != v4.dev_options(r, t):
                problems.append(f"C r={r} t={t}: rotation differs from v4")
    return problems


def check_axis_renderers() -> list[str]:
    """B の request = v4 R1 の request (選択肢の巡回だけ違う)、C の request = v4 R1+ の request + 指示の段落.

    指示文は C の user 文にちょうど 1 回だけ現れ、B・system prompt・状態ブロックには現れない (ADR §5 の漏洩検査)。
    指示文は行動 label・状況の値を含まない (特定の答えを指さない)。
    """
    problems: list[str] = []
    if EXPLORE_SENTENCE in v2.SYSTEM_PROMPT:
        problems.append("explore sentence appears in the system prompt")
    for tok in (*ACTIONS, *WEATHER, *(x for s in dev_signatures() for x in s)):
        if tok in EXPLORE_SENTENCE:
            problems.append(f"explore sentence contains {tok!r}")
    for r in PILOT_R:
        for w in v4.WORLDS:
            for st in _extreme_states(w):
                for axis in AXES:
                    if EXPLORE_SENTENCE in render_state(st, w, r, axis):
                        problems.append(
                            f"{axis} r={r} {w}: explore sentence in state block"
                        )
                for t in range(PILOT_T):
                    b = loop_messages(st, w, r, t, AXIS_B)
                    c = loop_messages(st, w, r, t, AXIS_C)
                    b_v4 = v4.loop_messages(st, w, r, t, v4.RENDERER_R1)
                    c_v4 = v4.loop_messages(st, w, r, t, v4.RENDERER_R1PLUS)
                    b_opts = "、".join(dev_options(AXIS_B, r, t))
                    v4_opts = "、".join(v4.dev_options(r, t))
                    if (
                        b[0] != b_v4[0]
                        or b[1]["content"].replace(b_opts, v4_opts)
                        != b_v4[1]["content"]
                    ):
                        problems.append(
                            f"B r={r} t={t} {w}: request differs from v4 R1"
                        )
                    if c[0] != c_v4[0]:
                        problems.append(f"C r={r} t={t} {w}: system differs from v4")
                    if c[1]["content"].count(EXPLORE_SENTENCE) != 1:
                        problems.append(
                            f"C r={r} t={t} {w}: explore sentence not exactly once"
                        )
                    stripped = c[1]["content"].replace(f"\n\n{EXPLORE_SENTENCE}", "", 1)
                    if stripped != c_v4[1]["content"]:
                        problems.append(
                            f"C r={r} t={t} {w}: request differs from v4 R1plus"
                        )
                    if EXPLORE_SENTENCE in b[1]["content"]:
                        problems.append(f"B r={r} t={t} {w}: explore sentence in B")
    return sorted(set(problems))


def check_plan() -> list[str]:
    """Plan は (軸, 世界, r, t) の全組をちょうど 1 回ずつ含み、各軸が block の先頭に同数回来る."""
    keys = pilot_plan()
    problems: list[str] = []
    want = {
        (a, w, r, t)
        for a in AXES
        for w in v4.WORLDS
        for r in PILOT_R
        for t in range(PILOT_T)
    }
    got = [(k.axis, k.world, k.replicate, k.step) for k in keys]
    if len(got) != n_pilot_calls() or set(got) != want or len(set(got)) != len(got):
        problems.append("plan does not cover each (axis, world, r, t) exactly once")
    firsts = [axis_order(r)[0] for r in PILOT_R]
    if len({firsts.count(a) for a in AXES}) != 1:
        problems.append("axis order is unbalanced")
    problems += v4.check_world_order(len(PILOT_R))
    return problems


def check_non_leakage() -> list[str]:
    """v2 / v4 と同じ integrity 検査 + 世界名 token (両軸の全ループ段の prompt)."""
    ps = v2.lever_probes()
    probe_sets = (
        tuple(
            Probe(p.probe_id, p.omega, p.pointed[v4.WORLDS[0]], p.pointed[v4.WORLDS[2]])
            for p in ps
        ),
        tuple(
            Probe(p.probe_id, p.omega, p.pointed[v4.WORLDS[1]], p.pointed[v4.WORLDS[3]])
            for p in ps
        ),
    )
    problems: list[str] = []
    texts: list[str] = []
    snapshots = []
    for r in PILOT_R:
        for axis in AXES:
            for w in v4.WORLDS:
                for n, st in enumerate(_extreme_states(w)):
                    pre = tuple(st.succeeded) + tuple(s for s, _ in st.tried)
                    snapshots.append(
                        Snapshot(
                            ind_id=f"r{r}-{axis}-{w}-{n}",
                            preconditions=pre,
                            text=render_state(st, w, r, axis),
                        )
                    )
                    texts.extend(
                        loop_user_text(st, w, r, t, axis) for t in range(PILOT_T)
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
    tokens = ("a_rot", "b_rot", "c0", "arm", "world", "r1plus", "axis")
    for text in texts:
        low = text.lower()
        problems.extend(f"prompt contains {tok!r}" for tok in tokens if tok in low)
    return sorted(set(problems))


def describe_sentence() -> str:
    """Prereg に載せる指示文と、それが置かれる位置の例 (空状態・r=12・t=0・軸 C)."""
    return loop_user_text(v4.EMPTY_STATE, v4.WORLDS[0], PILOT_R[0], 0, AXIS_C)


def battery_violations() -> list[str]:
    """Pilot の battery の機械検査 (全て空なら合格)."""
    return [
        *check_replicates(),
        *check_seed_disjoint(),
        *check_rotation_balance(),
        *check_axis_renderers(),
        *check_plan(),
        *check_non_leakage(),
        *check_prompt_budget(),
    ]


def battery_report() -> dict[str, object]:
    return {
        "n_calls": n_pilot_calls(),
        "max_prompt_bytes": max_prompt_bytes(),
        "replicates": check_replicates(),
        "seed_disjoint": check_seed_disjoint(),
        "rotation_balance": check_rotation_balance(),
        "axis_renderers": check_axis_renderers(),
        "plan": check_plan(),
        "non_leakage": check_non_leakage(),
        "prompt_budget": check_prompt_budget(),
    }
