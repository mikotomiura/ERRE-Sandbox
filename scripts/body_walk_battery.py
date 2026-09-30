"""探索を身体側へ (b) 歩行 → decode 条件 — 較正 pilot の腕・decode・plan と機械検査 (pilot prereg).

事前登録 = ``experiments/20260930-body-walk-calibration-pilot/prereg.md``。設計の正本は scoping ADR
``.steering/20260930-exploration-by-body-scoping/design-final.md`` (FROZEN) の §3・§6・§8-1。
凍結 v4 battery (``scripts/closed_loop_battery.py``) の世界・規則・状態・更新・renderer R1・状況部・表示回転を
import し、本モジュールは **歩行の腕 W の差分だけ** を定める。

* 腕 W = R1 (試した行なし) + v4 の表示回転 (r + t) mod 4 (周で不変) + 開発段の decode = 歩行。
  request の messages は v4 の ``loop_messages(..., RENDERER_R1)`` と byte 一致し、違うのは options の 3 値だけ。
* 歩行の decode = ERRE の live 凍結値の上限 endpoint (λ = 1、user 裁定 DU-2)。値は ``compose_sampling`` の
  出力そのもの (手書きの定数を正本にしない)。着座 (probe) は v2 の値のまま。
* pilot = ループ段のみ (probe・C0 なし)、r ∈ {16..27} (user 裁定 DU-3)、M = 8、4 世界 = 4,608 呼び出し。
  その後に決定性 replay を r ごとに 9 件 (判定に使わない)。seed は v2・v4・v5 と値域が互いに素な新しい基点。
* meta は要求条件に加えて、driver が実行時に観測した Ollama の版・model digest・model parameters を持つ
  (Codex HIGH-1、DC-1)。期待値は 2026-09-30 にローカルの Ollama から観測した値。

世界名は prompt に出さない (``check_non_leakage``)。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from erre_sandbox.erre.locomotion_sampling import (
    DEFAULT_LOCO_GAIN_P,
    DEFAULT_LOCO_GAIN_T,
    locomotion_delta,
)
from erre_sandbox.erre.sampling_table import SAMPLING_DELTA_BY_MODE
from erre_sandbox.inference.sampling import ResolvedSampling, compose_sampling
from erre_sandbox.schemas import (
    ERREModeName,
    LocomotionState,
    SamplingBase,
    SamplingDelta,
)
from scripts import closed_loop_battery as v4
from scripts import closed_loop_v5_battery as v5
from scripts import skill_lever_battery as v2
from scripts.skill_lever_scorer import request_meta
from scripts.stage_b_battery import dev_signatures
from scripts.stage_b_scorer import (
    Probe,
    Snapshot,
    StageBData,
    integrity_violations,
)

# ---- 歩行の decode (user 裁定 DU-2: endpoint のみ)
WALK_LAMBDA: Final[float] = 1.0
# 凍結時 (2026-09-30) に ``walk_sampling()`` の出力として観測した値 (temperature, top_p, repeat_penalty)。正本は
# compose の出力で、これは凍結後に ERRE の凍結値が変わったことを検出する封印 (変われば battery 違反 → invalid)
FROZEN_WALK: Final[tuple[float, float, float]] = (1.3, 0.9500000000000001, 0.9)

# ---- 実行環境の観測値 (Codex HIGH-1・DC-1。2026-09-30 にローカルの Ollama から観測: /api/version・/api/tags・
# /api/show。推論はしていない)。driver は実行時に同じ API から観測した値を meta に書く (手で書かない)
OLLAMA_VERSION: Final[str] = "0.32.12"
MODEL_DIGEST: Final[str] = (
    "500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41"
)
MODEL_PARAMETERS: Final[str] = (
    'stop                           "<|im_start|>"\n'
    'stop                           "<|im_end|>"\n'
    "temperature                    0.6\n"
    "top_k                          20\n"
    "top_p                          0.95\n"
    "repeat_penalty                 1"
)

# ---- pilot の範囲 (user 裁定 DU-3)
PILOT_R: Final[tuple[int, ...]] = tuple(range(16, 28))
PILOT_M: Final[int] = 8
M_WINDOWS: Final[tuple[int, ...]] = (4, 6, 8)  # 本登録の候補 M。測定は t < 12M の窓ごと
N_DEV: Final[int] = v4.N_DEV
N_POSITIONS: Final[int] = v4.N_POSITIONS
PILOT_T: Final[int] = N_DEV * PILOT_M
PILOT_SEED_BASE: Final[int] = 23_260_930
PILOT_SEED_STRIDE: Final[int] = 1000
# 本登録が使いうる r (候補 R ≤ 12 → r < 12)。pilot の r はこれと v5 pilot の r に重ならない
MAIN_R_MAX: Final[int] = 12
# 他の登録の seed の検査範囲 (本登録の r と pilot の r を覆う)
OTHER_R_MAX: Final[int] = 32
OTHER_K_MAX: Final[int] = v4.K_MAX
# 決定性 replay の対象 step (M = 4 / 8 の窓の終わりと t = 0)
REPLAY_LEAD_STEP: Final[int] = 0
REPLAY_ALL_STEPS: Final[tuple[int, ...]] = (N_DEV * 4 - 1, PILOT_T - 1)

PHASE_LOOP: Final[str] = v4.PHASE_LOOP
PHASE_REPLAY: Final[str] = v4.PHASE_REPLAY
RENDERER: Final[str] = v4.RENDERER_R1


# ------------------------------------------------------------------ decode


def _sit_base() -> SamplingBase:
    return SamplingBase(
        temperature=v2.TEMPERATURE, top_p=v2.TOP_P, repeat_penalty=v2.REPEAT_PENALTY
    )


def _walk_deltas() -> tuple[SamplingDelta, SamplingDelta]:
    mode = SAMPLING_DELTA_BY_MODE[ERREModeName.PERIPATETIC]
    loco = locomotion_delta(
        LocomotionState(lam=WALK_LAMBDA),
        gain_t=DEFAULT_LOCO_GAIN_T,
        gain_p=DEFAULT_LOCO_GAIN_P,
    )
    return mode, loco


def walk_sampling() -> ResolvedSampling:
    """開発段 = 歩行: v2 の値 + peripatetic delta + locomotion (λ = 1) を ``compose_sampling`` で合成した値."""
    mode, loco = _walk_deltas()
    return compose_sampling(_sit_base(), mode, loco)


def sit_sampling() -> ResolvedSampling:
    """着座 (probe・v2〜v5 の全呼び出し): v2 の値に delta 0 を合成した値 (= v2 の値)."""
    return compose_sampling(_sit_base(), SamplingDelta())


def request_meta_walk() -> dict[str, Any]:
    """pilot の run が記録しなければならない要求条件と、実行時に観測する環境 (凍結値との一致を検査する)."""
    walk = walk_sampling()
    meta = dict(request_meta())
    meta.update(
        temperature=walk.temperature,
        top_p=walk.top_p,
        repeat_penalty=walk.repeat_penalty,
        ollama_version=OLLAMA_VERSION,
        model_digest=MODEL_DIGEST,
        model_parameters=MODEL_PARAMETERS,
    )
    return meta


# ------------------------------------------------------------------ 腕 W


def dev_options(r: int, t: int) -> tuple[str, ...]:
    """表示順の Ω_dev = v4 と同じ (r + t) mod 4 の巡回。周で不変 (12 ≡ 0 mod 4)."""
    return v4.dev_options(r, t)


def render_state(state: v4.State, world: str, r: int) -> str:
    return v4.render_state(state, world, r, RENDERER)


def loop_messages(state: v4.State, world: str, r: int, t: int) -> list[dict[str, str]]:
    """v4 の R1 のループ段の messages と byte 一致する."""
    return v4.loop_messages(state, world, r, t, RENDERER)


def pilot_seed(r: int, t: int) -> int:
    """Pilot の decoding seed。世界を引数に取らない (4 世界で共有 = 共通乱数)."""
    return PILOT_SEED_BASE + PILOT_SEED_STRIDE * r + t


# ---------------------------------------------------------------- plan


@dataclass(frozen=True)
class PilotKey:
    phase: str
    world: str
    replicate: int
    step: int


def replay_targets(r: int) -> list[PilotKey]:
    """決定性 replay の登録部分集合 (r ごとに 9 件): t = 0 の先頭世界、t = 47・95 の 4 世界."""
    order = v4.world_order(r)
    out = [PilotKey(PHASE_LOOP, order[0], r, REPLAY_LEAD_STEP)]
    out += [PilotKey(PHASE_LOOP, w, r, t) for t in REPLAY_ALL_STEPS for w in order]
    return out


def pilot_plan() -> list[PilotKey]:
    """凍結する呼び出し順。call_index = この list の位置.

    1. r ごとに、t = 0..95 の各 t で、4 世界を v4 ``world_order(r)`` の順に呼ぶ (ループ段)。
    2. 最後に決定性 replay (r ごとに ``replay_targets``)。元の呼び出しと同じ request・seed。判定に使わない。
    """
    loop = [
        PilotKey(PHASE_LOOP, w, r, t)
        for r in PILOT_R
        for t in range(PILOT_T)
        for w in v4.world_order(r)
    ]
    replay = [
        PilotKey(PHASE_REPLAY, k.world, k.replicate, k.step)
        for r in PILOT_R
        for k in replay_targets(r)
    ]
    return loop + replay


def n_loop_calls() -> int:
    return len(v4.WORLDS) * len(PILOT_R) * PILOT_T


def n_replay_calls() -> int:
    return len(PILOT_R) * (1 + len(REPLAY_ALL_STEPS) * len(v4.WORLDS))


# ------------------------------------------------------------------ checks


def check_sampling() -> list[str]:
    """歩行は compose の出力 (clamp されていない)・向きが凍結 channel どおり・着座は v2 の値・meta は歩行の値."""
    problems: list[str] = []
    walk = walk_sampling()
    sit = sit_sampling()
    base = _sit_base()
    if (walk.temperature, walk.top_p, walk.repeat_penalty) != FROZEN_WALK:
        problems.append("walk sampling differs from the value observed at freeze")
    mode, loco = _walk_deltas()
    for name in ("temperature", "top_p", "repeat_penalty"):
        raw = getattr(base, name) + getattr(mode, name) + getattr(loco, name)
        if getattr(walk, name) != raw:
            problems.append(f"walk {name} is clamped or not the composed sum")
    if (sit.temperature, sit.top_p, sit.repeat_penalty) != (
        v2.TEMPERATURE,
        v2.TOP_P,
        v2.REPEAT_PENALTY,
    ):
        problems.append("sit sampling differs from the v2 values")
    if not (
        walk.temperature > sit.temperature
        and walk.top_p > sit.top_p
        and walk.repeat_penalty < sit.repeat_penalty
    ):
        problems.append("walk does not move T / top_p up and repeat_penalty down")
    meta = request_meta_walk()
    if (meta["temperature"], meta["top_p"], meta["repeat_penalty"]) != (
        walk.temperature,
        walk.top_p,
        walk.repeat_penalty,
    ):
        problems.append("request meta does not carry the walk sampling")
    if set(meta) != {
        *request_meta(),
        "ollama_version",
        "model_digest",
        "model_parameters",
    }:
        problems.append("request meta keys differ")
    return problems


def check_replicates() -> list[str]:
    """Pilot の r は本登録 (r < 12)・v5 pilot と重ならず、一意で、r mod 4 が同数回 (DU-3)."""
    problems: list[str] = []
    if len(set(PILOT_R)) != len(PILOT_R):
        problems.append("pilot replicates are not unique")
    if any(r < MAIN_R_MAX for r in PILOT_R):
        problems.append("pilot replicates overlap the main registration (r < 12)")
    if set(PILOT_R) & set(v5.PILOT_R):
        problems.append("pilot replicates overlap the v5 pilot")
    counts = [sum(1 for r in PILOT_R if r % N_POSITIONS == s) for s in range(4)]
    if len(set(counts)) != 1:
        problems.append("pilot replicates do not balance r mod 4")
    return problems


def pilot_seeds() -> set[int]:
    return {pilot_seed(r, t) for r in PILOT_R for t in range(PILOT_T)}


def check_seed_disjoint() -> list[str]:
    """Pilot の seed は一意で、v2 probe・v4 ループ段・v5 pilot の seed と 1 つも衝突しない.

    本登録のループ段・probe の seed は ``pilot_seeds()`` と交わらないことを、本登録の prereg が機械検査する。
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
    v4_loop = {v4.loop_seed(r, t) for r in range(OTHER_R_MAX) for t in range(PILOT_T)}
    for name, other in (
        ("v2 probe", v2_probe),
        ("v4 loop", v4_loop),
        ("v5 pilot", v5.pilot_seeds()),
    ):
        if seeds & other:
            problems.append(f"{len(seeds & other)} pilot seeds collide with {name}")
    return problems


def check_rotation() -> list[str]:
    """表示回転は v4 と同じで周で不変。各周で巡回量 0〜3 が 3 回ずつ."""
    problems: list[str] = []
    for r in PILOT_R:
        for t in range(PILOT_T):
            opts = dev_options(r, t)
            if opts != v4.dev_options(r, t):
                problems.append(f"r={r} t={t}: rotation differs from v4")
            if t + N_DEV < PILOT_T and opts != dev_options(r, t + N_DEV):
                problems.append(f"r={r} t={t}: rotation changes across laps")
        for lap in range(PILOT_M):
            shifts = [
                dev_options(r, t).index(v4.dev_omega(v4.loop_signature(r, t)[0])[0])
                for t in range(N_DEV * lap, N_DEV * (lap + 1))
            ]
            if [shifts.count(s) for s in range(N_POSITIONS)] != [3] * N_POSITIONS:
                problems.append(f"r={r} lap {lap}: rotation shifts unbalanced")
    return sorted(set(problems))


def check_plan() -> list[str]:
    """ループ段は (世界, r, t) の全組をちょうど 1 回、replay は全ループの後で元の key を持つ、世界順は均衡."""
    keys = pilot_plan()
    problems: list[str] = []
    n_loop = n_loop_calls()
    loop, replay = keys[:n_loop], keys[n_loop:]
    want = {(w, r, t) for w in v4.WORLDS for r in PILOT_R for t in range(PILOT_T)}
    got = [(k.world, k.replicate, k.step) for k in loop]
    if (
        any(k.phase != PHASE_LOOP for k in loop)
        or len(got) != len(set(got))
        or set(got) != want
    ):
        problems.append("loop part does not cover each (world, r, t) exactly once")
    elif got != [
        (w, r, t) for r in PILOT_R for t in range(PILOT_T) for w in v4.world_order(r)
    ]:
        problems.append("loop part is not in the frozen (r, t, world order) order")
    if len(replay) != n_replay_calls() or any(k.phase != PHASE_REPLAY for k in replay):
        problems.append("replay part is not the registered subset after the loop")
    if [(k.world, k.replicate, k.step) for k in replay] != [
        (k.world, k.replicate, k.step) for r in PILOT_R for k in replay_targets(r)
    ]:
        problems.append("replay keys differ from the registered targets")
    counts = {(w, pos): 0 for w in v4.WORLDS for pos in range(len(v4.WORLDS))}
    for r in PILOT_R:
        for pos, w in enumerate(v4.world_order(r)):
            counts[(w, pos)] += 1
    if len(set(counts.values())) != 1:
        problems.append("world order is unbalanced")
    return problems


def _extreme_states(world: str) -> list[v4.State]:
    """Byte 予算・非漏洩の検査に使う状態: 空・全成功 (R1 は試行行を描かない)."""
    devs = dev_signatures()
    return [v4.EMPTY_STATE, v4.State(succeeded=frozenset(devs))]


def max_prompt_bytes() -> int:
    best = 0
    for r in PILOT_R:
        for w in v4.WORLDS:
            for st in _extreme_states(w):
                for t in range(N_DEV):
                    best = max(best, v2.prompt_bytes(loop_messages(st, w, r, t)))
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


def check_non_leakage() -> list[str]:
    """v2 / v4 と同じ integrity 検査 + 世界名 token (全ループ段の prompt、R1)."""
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
        for w in v4.WORLDS:
            for n, st in enumerate(_extreme_states(w)):
                snapshots.append(
                    Snapshot(
                        ind_id=f"r{r}-{w}-{n}",
                        preconditions=tuple(st.succeeded),
                        text=render_state(st, w, r),
                    )
                )
                texts.extend(
                    loop_messages(st, w, r, t)[1]["content"] for t in range(N_DEV)
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
    # 行動 label (walk_path 等) と衝突しない token だけを見る (v5 と同じ集合)
    tokens = ("a_rot", "b_rot", "c0", "arm", "world", "r1plus", "axis")
    for text in texts:
        low = text.lower()
        problems.extend(f"prompt contains {tok!r}" for tok in tokens if tok in low)
    return sorted(set(problems))


def battery_violations() -> list[str]:
    """Pilot の battery の機械検査 (全て空なら合格)."""
    return [
        *check_sampling(),
        *check_replicates(),
        *check_seed_disjoint(),
        *check_rotation(),
        *check_plan(),
        *check_non_leakage(),
        *check_prompt_budget(),
    ]


def battery_report() -> dict[str, object]:
    walk = walk_sampling()
    return {
        "n_loop_calls": n_loop_calls(),
        "n_replay_calls": n_replay_calls(),
        "walk_sampling": walk.model_dump(),
        "max_prompt_bytes": max_prompt_bytes(),
        "sampling": check_sampling(),
        "replicates": check_replicates(),
        "seed_disjoint": check_seed_disjoint(),
        "rotation": check_rotation(),
        "plan": check_plan(),
        "non_leakage": check_non_leakage(),
        "prompt_budget": check_prompt_budget(),
    }
