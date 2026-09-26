"""Skill lever-only feasibility pilot — battery・layout・renderer と機械検査 (prereg v2).

事前登録 = ``experiments/20260926-skill-lever-pilot/prereg.md``。旧 Stage B の battery ドラフト
(``scripts/stage_b_battery.py``、未凍結) の状況 signature・行動 label・規則表 A・σ・held-out probe を
そのまま使い、本モジュールで 4 arm の規則表・replicate ごとの counterbalance・prompt renderer を定める。

arm (prereg v2 §2):

* ``A``: 規則表 A (weather → 行動)。``A_rot``: A_rot(w) = A(next(w))。
* ``B`` = σ ∘ A、``B_rot`` = σ ∘ A_rot。族 = {A, A_rot} と {B, B_rot}。
* 族内の 2 arm は状態に出る label の集合・頻度が同じで、weather との対応だけが違う。
* probe q で 4 arm が指す選択肢は Ω_q = {g_A, x, g_B, σx} と 1 対 1 (x = 次の weather の A 規則行動)。
* ``C0`` (baseline): 状態なし。判定には使わず、⊥ gate と記述報告に使う。

arm 名は prompt・状態に出さない (非漏洩、``check_non_leakage``)。
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Final

import numpy as np

from scripts.stage_b_battery import (
    ACTIONS,
    RULE_A,
    SIGMA,
    WEATHER,
    Signature,
    dev_signatures,
    probe_signatures,
)
from scripts.stage_b_scorer import (
    Probe,
    Snapshot,
    StageBData,
    integrity_violations,
    signature_text,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

ARM_A: Final[str] = "A"
ARM_A_ROT: Final[str] = "A_rot"
ARM_B: Final[str] = "B"
ARM_B_ROT: Final[str] = "B_rot"
ARM_C0: Final[str] = "C0"
LEVER_ARMS: Final[tuple[str, ...]] = (ARM_A, ARM_A_ROT, ARM_B, ARM_B_ROT)
ALL_ARMS: Final[tuple[str, ...]] = (*LEVER_ARMS, ARM_C0)
FAMILIES: Final[tuple[tuple[str, str], ...]] = ((ARM_A, ARM_A_ROT), (ARM_B, ARM_B_ROT))
FOIL: Final[dict[str, str]] = {
    ARM_A: ARM_A_ROT,
    ARM_A_ROT: ARM_A,
    ARM_B: ARM_B_ROT,
    ARM_B_ROT: ARM_B,
}

# ---- 凍結する実行条件 (prereg v2 §4)
MODEL: Final[str] = "qwen3:8b"
THINK: Final[bool] = False
TEMPERATURE: Final[float] = 0.7
TOP_P: Final[float] = 0.8
REPEAT_PENALTY: Final[float] = 1.0
NUM_CTX: Final[int] = 4096
NUM_PREDICT: Final[int] = 32
CHAT_TEMPLATE_OVERHEAD: Final[int] = 64  # system/user の区切り token の上限見積り
MAX_PROMPT_BYTES: Final[int] = 3000  # token 数 ≤ UTF-8 byte 数 (byte-level BPE)
SEED_BASE: Final[int] = 20260926
LAYOUT_SEED: Final[int] = 20260926
N_POSITIONS: Final[int] = 4

SYSTEM_PROMPT: Final[str] = (
    "あなたは与えられた状況で、示された行動の中から 1 つを選ぶ。"
)
STATE_HEADER: Final[str] = "これまでの経験の記録:"


def _next_weather(w: str) -> str:
    return WEATHER[(WEATHER.index(w) + 1) % len(WEATHER)]


def rule(arm: str) -> dict[str, str]:
    """arm の規則表 weather → 行動 (C0 は規則を持たない)."""
    if arm == ARM_A:
        return dict(RULE_A)
    if arm == ARM_A_ROT:
        return {w: RULE_A[_next_weather(w)] for w in WEATHER}
    if arm == ARM_B:
        return {w: SIGMA[a] for w, a in rule(ARM_A).items()}
    if arm == ARM_B_ROT:
        return {w: SIGMA[a] for w, a in rule(ARM_A_ROT).items()}
    msg = f"arm {arm!r} has no rule table"
    raise ValueError(msg)


# ------------------------------------------------------------------ probes


@dataclass(frozen=True)
class LeverProbe:
    """held-out probe: 4 arm が指す選択肢 (相異なる) と正準順の Ω_q."""

    probe_id: str
    signature: Signature
    pointed: Mapping[str, str]  # arm → その arm の規則が指す選択肢

    @property
    def omega(self) -> tuple[str, ...]:
        return tuple(self.pointed[a] for a in LEVER_ARMS)


@lru_cache(maxsize=1)
def lever_probes() -> tuple[LeverProbe, ...]:
    out = []
    for n, sig in enumerate(probe_signatures()):
        pointed = {a: rule(a)[sig[0]] for a in LEVER_ARMS}
        out.append(LeverProbe(probe_id=f"q{n:02d}", signature=sig, pointed=pointed))
    return tuple(out)


# ------------------------------------------------------------------ layout


@dataclass(frozen=True)
class Layout:
    """replicate r の counterbalance セル (全 arm で共有)."""

    replicate: int
    option_order: Mapping[str, tuple[str, ...]]  # probe_id → 表示順の Ω_q
    entry_order: tuple[Signature, ...]  # Skill エントリに使う発達 signature の順


@lru_cache(maxsize=64)
def layout(r: int) -> Layout:
    """Ω_q は正準順を (r + probe 番号) mod 4 だけ巡回 (R が 4 の倍数なら各選択肢が各位置に同数)。

    Skill エントリの順は発達 signature の置換 π_r (``default_rng(LAYOUT_SEED + r)``)。
    """
    order: dict[str, tuple[str, ...]] = {}
    for qi, probe in enumerate(lever_probes()):
        om = probe.omega
        shift = (r + qi) % N_POSITIONS
        order[probe.probe_id] = om[shift:] + om[:shift]
    devs = dev_signatures()
    perm = np.random.default_rng(LAYOUT_SEED + r).permutation(len(devs))
    return Layout(r, order, tuple(devs[int(i)] for i in perm))


def sample_seed(r: int, probe_index: int, k: int) -> int:
    """decoding seed。arm 間で共有する (同じ r・probe・k は全 arm で同じ seed)."""
    return SEED_BASE + r * 10_000 + probe_index * 100 + k


# ---------------------------------------------------------------- renderer


def state_entries(arm: str, lay: Layout) -> list[tuple[Signature, str]]:
    table = rule(arm)
    return [(sig, table[sig[0]]) for sig in lay.entry_order]


def render_state(arm: str, lay: Layout) -> str:
    lines = [
        f"条件: {signature_text(sig)} → 行動: {act} (成功 3 / 失敗 0)"
        for sig, act in state_entries(arm, lay)
    ]
    return "\n".join([STATE_HEADER, *lines])


def render_probe(probe: LeverProbe, lay: Layout) -> str:
    sig = probe.signature
    options = "、".join(lay.option_order[probe.probe_id])
    return (
        f"状況: 天候={sig[0]}、時刻={sig[1]}、同伴={sig[2]}。\n"
        f"次の行動から 1 つだけ選び、行動名だけを答えよ: {options}"
    )


def render_messages(arm: str, probe: LeverProbe, lay: Layout) -> list[dict[str, str]]:
    """Ollama /api/chat に渡す messages。C0 は状態ブロックを持たない."""
    probe_text = render_probe(probe, lay)
    user = probe_text if arm == ARM_C0 else f"{render_state(arm, lay)}\n\n{probe_text}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def prompt_bytes(messages: Sequence[Mapping[str, str]]) -> int:
    return sum(len(m["content"].encode("utf-8")) for m in messages)


# ------------------------------------------------------------------ checks


def check_prompt_budget(r_max: int) -> list[str]:
    """描画 prompt が切り詰められえないことの静的保証 (token ≤ UTF-8 byte)."""
    problems: list[str] = []
    if MAX_PROMPT_BYTES + CHAT_TEMPLATE_OVERHEAD + NUM_PREDICT > NUM_CTX:
        problems.append("byte budget does not fit num_ctx")
    for r in range(r_max):
        lay = layout(r)
        for probe in lever_probes():
            for arm in ALL_ARMS:
                n = prompt_bytes(render_messages(arm, probe, lay))
                if n > MAX_PROMPT_BYTES:
                    problems.append(f"r={r} {probe.probe_id} {arm}: {n} bytes")
    return problems


def check_pointed_bijection() -> list[str]:
    """各 probe で 4 arm の指す選択肢が相異なり、Ω_q が σ で閉じる."""
    problems: list[str] = []
    for p in lever_probes():
        if len(set(p.omega)) != len(LEVER_ARMS):
            problems.append(f"{p.probe_id}: pointed options are not distinct")
        if {SIGMA[o] for o in p.omega} != set(p.omega):
            problems.append(f"{p.probe_id}: Ω_q is not closed under σ")
        for a, b in ((ARM_A, ARM_B), (ARM_A_ROT, ARM_B_ROT)):
            if SIGMA[p.pointed[a]] != p.pointed[b]:
                problems.append(f"{p.probe_id}: {b} is not the σ image of {a}")
    return problems


def check_label_balance(r_count: int = 1) -> list[str]:
    """族内の 2 arm は、全 r で状態の signature 順と label の多重集合が一致する (priming の相殺条件)."""
    problems: list[str] = []
    for r in range(r_count):
        problems.extend(_label_balance_at(r))
    return problems


def _label_balance_at(r: int) -> list[str]:
    problems: list[str] = []
    lay = layout(r)
    for a, b in FAMILIES:
        la = sorted(act for _, act in state_entries(a, lay))
        lb = sorted(act for _, act in state_entries(b, lay))
        if la != lb:
            problems.append(f"{a}/{b}: state label multisets differ")
        sa = [sig for sig, _ in state_entries(a, lay)]
        sb = [sig for sig, _ in state_entries(b, lay)]
        if sa != sb:
            problems.append(f"{a}/{b}: state signature orders differ")
        if len(render_state(a, lay)) != len(render_state(b, lay)):
            problems.append(f"{a}/{b}: state lengths differ")
    return problems


def check_position_balance(r_count: int) -> list[str]:
    """R が 4 の倍数のとき、各 probe で各選択肢が各表示位置に同数回来る."""
    problems: list[str] = []
    if r_count % N_POSITIONS:
        problems.append(f"R={r_count} is not a multiple of {N_POSITIONS}")
        return problems
    for p in lever_probes():
        counts = {(o, pos): 0 for o in p.omega for pos in range(N_POSITIONS)}
        for r in range(r_count):
            for pos, o in enumerate(layout(r).option_order[p.probe_id]):
                counts[(o, pos)] += 1
        if len(set(counts.values())) != 1:
            problems.append(f"{p.probe_id}: option positions are unbalanced")
    return problems


def check_shared_layout(r_count: int) -> list[str]:
    """同じ r の中で、全 arm の probe 部分 (状況・選択肢の順) と seed が一致する."""
    problems: list[str] = []
    for r in range(r_count):
        lay = layout(r)
        for p in lever_probes():
            tails = {
                arm: render_messages(arm, p, lay)[1]["content"].rsplit("\n\n", 1)[-1]
                for arm in ALL_ARMS
            }
            if len(set(tails.values())) != 1:
                problems.append(f"r={r} {p.probe_id}: probe part differs across arms")
    return problems


def check_non_leakage(r_count: int) -> list[str]:
    """旧 prereg §2.2 と同じ integrity 検査 (``stage_b_scorer.integrity_violations``) を全 arm・全 r に."""
    ps = lever_probes()
    # integrity 検査は g_A / g_B の answer key を探す。4 arm 分を 2 つの Probe に分けて渡す。
    as_probes = tuple(
        Probe(p.probe_id, p.omega, p.pointed[ARM_A], p.pointed[ARM_B]) for p in ps
    )
    as_probes_rot = tuple(
        Probe(p.probe_id, p.omega, p.pointed[ARM_A_ROT], p.pointed[ARM_B_ROT])
        for p in ps
    )
    problems: list[str] = []
    for probe_set in (as_probes, as_probes_rot):
        snapshots = []
        prompts = []
        for r in range(r_count):
            lay = layout(r)
            for arm in LEVER_ARMS:
                snapshots.append(
                    Snapshot(
                        ind_id=f"r{r}-{arm}",
                        preconditions=tuple(s for s, _ in state_entries(arm, lay)),
                        text=render_state(arm, lay),
                    )
                )
            for p in ps:
                prompts.extend(
                    render_messages(arm, p, lay)[1]["content"] for arm in ALL_ARMS
                )
        data = StageBData(
            probes=probe_set,
            probe_signatures={p.probe_id: p.signature for p in ps},
            dev_signatures=frozenset(dev_signatures()),
            di=(),
            di_ablation=(),
            ci=(),
            snapshots=tuple(snapshots),
            probe_prompts=tuple(prompts),
        )
        problems.extend(integrity_violations(data))
    arm_tokens = ("a_rot", "b_rot", "c0", "arm")
    for r in range(r_count):
        lay = layout(r)
        for p in ps:
            for arm in ALL_ARMS:
                low = render_messages(arm, p, lay)[1]["content"].lower()
                problems.extend(
                    f"r={r} {arm}: prompt contains {tok!r}"
                    for tok in arm_tokens
                    if tok in low
                )
    return sorted(set(problems))


def battery_report(r_count: int) -> dict[str, object]:
    return {
        "n_probes": len(lever_probes()),
        "n_state_entries": len(dev_signatures()),
        "actions": list(ACTIONS),
        "pointed_bijection": check_pointed_bijection(),
        "label_balance": check_label_balance(r_count),
        "position_balance": check_position_balance(r_count),
        "shared_layout": check_shared_layout(r_count),
        "non_leakage": check_non_leakage(r_count),
        "prompt_budget": check_prompt_budget(r_count),
    }
