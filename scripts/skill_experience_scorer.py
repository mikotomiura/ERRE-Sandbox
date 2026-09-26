"""経験由来 Skill pilot — 推定量・判定 rule・対照・OC 模擬 (prereg v3).

事前登録 = ``experiments/20260926-experience-skill-pilot/prereg.md``。凍結 v2 scorer
(``scripts/skill_lever_scorer.py``) からは **純粋関数だけ** を import する (parse・記録の読み取り・
category・族単位・⊥ gate・3 分岐・符号反転・攪乱の base 分布)。v2 の ``evaluate`` / ``_grid`` /
``expected_sample`` / ``structure_violations`` / ``simulate`` は v2 の FROZEN_R/K と v2 battery に結び付くので
使わず、本モジュールに対応物を置く (scoping Codex MEDIUM-3)。

用語 (prereg v3 §3): 判定 arm a ∈ {A, A_rot, B, B_rot} の成分 s_{a,r}・単位 d_{r,f}・C は v2 と同じ式。
対照 arm L_* は、対応する判定 arm と同じ選択肢を指し、同じ式で対照の C と verdict を別に出す
(判定 5 語には混ぜない。§9 の claim 分岐にだけ使う)。

判定 (評価順、prereg v3 §5): INVALID_SCORER → (計算しない) → INVALID_TASK_BATTERY → PASS →
NO_GO_EFFECT_ABSENT → INCONCLUSIVE_UNDERPOWERED。計算は CPU・numpy のみ。
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import numpy as np
from scripts import skill_experience_battery as bat
from scripts import skill_lever_battery as v2bat
from scripts.skill_lever_scorer import (
    BOT_MAX,
    DELTA_PLANT,
    POWER_TARGET,
    STATUS_COMPUTED,
    STATUS_NOT_COMPUTED,
    TAU,
    Nuisance,
    Sample,
    _flip_matrix,
    _flip_p,
    base_probs,
    bottom_gate_ok,
    category,
    decide,
    family_units,
    load_records,
    messages_sha256,
    parse_choice,
    request_meta,
    tests_exact,
)
from scripts.stage_b_scorer import (
    ALPHA,
    VERDICT_ABSENT,
    VERDICT_INVALID_BATTERY,
    VERDICT_INVALID_SCORER,
    VERDICT_PASS,
    VERDICT_UNDERPOWERED,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = [
    "ALPHA",
    "BOT_MAX",
    "DELTA_PLANT",
    "POWER_TARGET",
    "STATUS_COMPUTED",
    "STATUS_NOT_COMPUTED",
    "TAU",
    "Nuisance",
    "Sample",
    "parse_choice",
    "request_meta",
]

# ---- 凍結値 (prereg v3 §4 / §6)
FROZEN_R: Final[int] = 8  # power 表の選定 (results/power_table.json)
FROZEN_K: Final[int] = 5
SD_EXACT_MAX: Final[float] = (
    0.3  # これ以下の sd では size を α + 3SE で要求 (v2 と同じ)
)
SIZE_CAP_WIDE: Final[float] = 1.5 * ALPHA  # sd > SD_EXACT_MAX の size 上限 (user 裁定)
SIM_SEED: Final[int] = 20260926

CLAIM_PASS: Final[str] = "pass_outcome_conditioned_rule_extraction"
CLAIM_NO_GO_CONTROL_PASS: Final[str] = "no_go_not_explained_by_length_or_format"
CLAIM_NO_GO_NARROW: Final[str] = "no_go_this_renderer_only"

# 呼び出し順 (prereg v3 §2.4): C0 を全て ((r, probe, k) の辞書順) → (r, probe, k) の block ごとに状態 8 arm を、
# この順を block 通し番号 mod 8 だけ巡回して呼ぶ (v2 driver DR-2 と同じ。族内差に時間ドリフトが乗らない)
CALL_ARM_ORDER: Final[tuple[str, ...]] = bat.STATE_ARMS


# -------------------------------------------------------------- records


def expected_sample(arm: str, r: int, qi: int, k: int) -> tuple[int, str]:
    probe = v2bat.lever_probes()[qi]
    msgs = bat.render_messages(arm, probe, v2bat.layout(r))
    return v2bat.sample_seed(r, qi, k), messages_sha256(msgs)


def call_block(r: int, qi: int, k: int) -> int:
    """(r, probe, k) の block 通し番号 (辞書順)."""
    return (r * len(v2bat.lever_probes()) + qi) * FROZEN_K + k


def block_arm_order(block: int) -> tuple[str, ...]:
    """Block 内で状態 arm を呼ぶ順 = ``CALL_ARM_ORDER`` を block mod 8 だけ巡回."""
    shift = block % len(CALL_ARM_ORDER)
    return CALL_ARM_ORDER[shift:] + CALL_ARM_ORDER[:shift]


def call_rank(arm: str, r: int, qi: int, k: int) -> tuple[int, int, int]:
    """凍結した呼び出し順での位置 (C0 が先、以後 block 順・block 内は巡回順)."""
    block = call_block(r, qi, k)
    if arm == bat.ARM_C0:
        return (0, block, 0)
    return (1, block, block_arm_order(block).index(arm))


def grid(arms: Sequence[str]) -> set[tuple[str, int, str, int]]:
    return {
        (arm, r, p.probe_id, k)
        for arm in arms
        for r in range(FROZEN_R)
        for p in v2bat.lever_probes()
        for k in range(FROZEN_K)
    }


def structure_violations(samples: Sequence[Sample]) -> list[str]:
    """重複・想定外の key・seed / prompt / parse の不一致・呼び出し順 (→ INVALID_SCORER)."""
    out: list[str] = []
    qidx = {p.probe_id: i for i, p in enumerate(v2bat.lever_probes())}
    full = grid(bat.ALL_ARMS)
    seen: set[tuple[str, int, str, int]] = set()
    calls = [s.call_index for s in samples]
    if len(set(calls)) != len(calls) or any(c < 0 for c in calls):
        out.append("call_index is not unique and non-negative")
    c0_calls = [s.call_index for s in samples if s.arm == bat.ARM_C0]
    state_calls = [s.call_index for s in samples if s.arm != bat.ARM_C0]
    if c0_calls and state_calls and max(c0_calls) > min(state_calls):
        out.append("a state-arm call precedes the end of the C0 phase")
    for s in samples:
        key = (s.arm, s.replicate, s.probe_id, s.k)
        if key in seen:
            out.append(f"duplicate sample {key}")
            continue
        seen.add(key)
        if key not in full:
            out.append(f"unexpected sample {key}")
            continue
        seed, sha = expected_sample(s.arm, s.replicate, qidx[s.probe_id], s.k)
        if s.seed != seed:
            out.append(f"{key}: seed {s.seed} != {seed}")
        if s.prompt_sha256 != sha:
            out.append(f"{key}: prompt differs from the frozen renderer")
        if s.raw is not None and s.parsed != parse_choice(s.raw):
            out.append(f"{key}: recorded parse differs from re-parse")
    if not out:
        by_call = sorted(samples, key=lambda x: x.call_index)
        ranks = [call_rank(s.arm, s.replicate, qidx[s.probe_id], s.k) for s in by_call]
        if ranks != sorted(ranks):
            out.append("call order differs from the frozen order")
    return out


# ------------------------------------------------------------- estimand


def component_scores(
    choices: Mapping[tuple[str, int, str], Sequence[str | None]],
    arms: Sequence[str],
    r_count: int,
) -> np.ndarray:
    """(4, R) の s_{a,r}。arms は (A, A_rot, B, B_rot) またはそれに対応する対照 4 arm の順."""
    probes = v2bat.lever_probes()
    out = np.zeros((len(arms), r_count))
    for ai, arm in enumerate(arms):
        as_arm = bat.POINTS_AS[arm]
        for r in range(r_count):
            n = 0
            net = 0
            for p in probes:
                for c in choices[(arm, r, p.probe_id)]:
                    cat = category(c, p, as_arm)
                    net += (cat == "w") - (cat == "foil")
                    n += 1
            out[ai, r] = net / n
    return out


def bottom_rates(
    choices: Mapping[tuple[str, int, str], Sequence[str | None]],
    arms: Sequence[str],
    r_count: int,
) -> np.ndarray:
    probes = v2bat.lever_probes()
    out = []
    for arm in arms:
        cs = [
            c
            for r in range(r_count)
            for p in probes
            for c in choices[(arm, r, p.probe_id)]
        ]
        out.append(sum(c is None for c in cs) / len(cs))
    return np.array(out)


def judge_arms(
    choices: Mapping[tuple[str, int, str], Sequence[str | None]],
    arms: Sequence[str],
) -> dict[str, Any]:
    """4 arm (判定または対照) の ⊥ gate → 3 分岐。C0 gate は呼び出し側で先に済ませる."""
    bot = bottom_rates(choices, arms, FROZEN_R)
    rep: dict[str, Any] = {
        "bottom_rates": dict(zip(arms, bot.tolist(), strict=True)),
    }
    if not bool(bottom_gate_ok(bot)):
        rep.update(verdict=VERDICT_INVALID_BATTERY, reason="bottom_gate")
        return rep
    s = component_scores(choices, arms, FROZEN_R)
    d = family_units(s)
    comps = s.mean(axis=1)
    p_zero, p_lower, p_upper = tests_exact(d)
    rep.update(
        C=float(d.mean()),
        components=dict(zip(arms, comps.tolist(), strict=True)),
        units=d.tolist(),
        p_zero=p_zero,
        p_lower=p_lower,
        p_upper=p_upper,
        verdict=str(decide(np.float64(p_lower), np.float64(p_upper), comps)),
        reason="decided",
    )
    return rep


def claim_branch(main_verdict: str | None, control_verdict: str | None) -> str | None:
    """Prereg v3 §9 の claim 分岐 (判定 verdict は変えない)."""
    if main_verdict == VERDICT_PASS:
        return CLAIM_PASS
    if main_verdict == VERDICT_ABSENT:
        if control_verdict == VERDICT_PASS:
            return CLAIM_NO_GO_CONTROL_PASS
        return CLAIM_NO_GO_NARROW
    return None


# ------------------------------------------------------------ certification


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def certified_targets() -> dict[str, Path]:
    root = Path(__file__).resolve().parent
    names = (
        "skill_experience_scorer.py",
        "skill_experience_battery.py",
        "skill_lever_scorer.py",
        "skill_lever_battery.py",
        "stage_b_scorer.py",
        "stage_b_battery.py",
    )
    return {n: root / n for n in names}


def load_certification(path: Path) -> bool:
    """変異 harness の記録。全 KILLED ∧ 記録 sha256 が現在の 6 ファイルと一致。読めない = 不合格."""
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        recorded = obj["target_sha256"]
        all_killed = obj["all_killed"] is True
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return all_killed and all(
        recorded.get(name) == _sha256(p) for name, p in certified_targets().items()
    )


def battery_violations(r_count: int) -> list[str]:
    rep = bat.battery_report(r_count)
    return [f"{k}: {v}" for k, v in rep.items() if isinstance(v, list) and v]


# -------------------------------------------------------------- evaluate


def evaluate(
    samples: Sequence[Sample], meta: Mapping[str, Any], certification: Path
) -> dict[str, Any]:
    """Prereg v3 §5 の評価順で判定 verdict を返し、対照 verdict と claim 分岐を添える."""
    report: dict[str, Any] = {
        "status": STATUS_COMPUTED,
        "verdict": None,
        "reasons": [],
        "control": None,
        "claim_branch": None,
    }

    def done(verdict: str | None, reason: str) -> dict[str, Any]:
        report["reasons"].append(reason)
        report["verdict"] = verdict
        if verdict is None:
            report["status"] = STATUS_NOT_COMPUTED
        return report

    # ---- 1. INVALID_SCORER
    if not load_certification(certification):
        return done(VERDICT_INVALID_SCORER, "certification_missing_or_stale")
    battery = battery_violations(FROZEN_R)
    report["battery_violations"] = battery
    if battery:
        return done(VERDICT_INVALID_SCORER, "battery_checks")
    if dict(meta) != request_meta():
        return done(VERDICT_INVALID_SCORER, "request_meta_mismatch")
    structure = structure_violations(samples)
    report["structure_violations"] = structure
    if structure:
        return done(VERDICT_INVALID_SCORER, "structure")

    # ---- 計算できない (⊥ に畳まない)
    if any(s.raw is None for s in samples):
        return done(None, "transport_failure")
    present = {(s.arm, s.replicate, s.probe_id, s.k) for s in samples}
    choices: dict[tuple[str, int, str], list[str | None]] = {}
    for s in sorted(samples, key=lambda x: x.k):
        choices.setdefault((s.arm, s.replicate, s.probe_id), []).append(s.parsed)

    # ---- 2. INVALID_TASK_BATTERY (C0 は状態 arm の前に実走する)
    if not grid((bat.ARM_C0,)) <= present:
        return done(None, "c0_incomplete")
    c0_bot = float(bottom_rates(choices, (bat.ARM_C0,), FROZEN_R)[0])
    report["c0_bottom_rate"] = c0_bot
    if c0_bot > BOT_MAX:
        return done(VERDICT_INVALID_BATTERY, "c0_bottom_rate")
    if not grid(bat.JUDGE_ARMS) <= present:
        return done(None, "judge_incomplete")
    main = judge_arms(choices, bat.JUDGE_ARMS)
    report["lever_bottom_rates"] = main["bottom_rates"]
    for key in ("C", "components", "units", "p_zero", "p_lower", "p_upper"):
        if key in main:
            report[key] = main[key]

    # ---- 対照 (判定 verdict には影響しない)
    if grid(bat.CONTROL_ARMS) <= present:
        control = judge_arms(choices, bat.CONTROL_ARMS)
        control["status"] = STATUS_COMPUTED
    else:
        control = {"status": STATUS_NOT_COMPUTED, "verdict": None}
    report["control"] = control

    if main["verdict"] == VERDICT_INVALID_BATTERY:
        return done(VERDICT_INVALID_BATTERY, "lever_bottom_gate")
    verdict = main["verdict"]
    report["claim_branch"] = claim_branch(verdict, control["verdict"])
    return done(verdict, "decided")


def evaluate_records(
    lines: Sequence[str], meta_text: str, certification: Path
) -> dict[str, Any]:
    """JSONL の行と meta の JSON テキストから。読めない・schema 違反は INVALID_SCORER."""
    try:
        samples = load_records(lines)
        meta = json.loads(meta_text)
    except ValueError as exc:  # RecordError を含む
        return {
            "status": STATUS_COMPUTED,
            "verdict": VERDICT_INVALID_SCORER,
            "reasons": ["record_schema"],
            "record_error": str(exc),
        }
    if not isinstance(meta, dict):
        return {
            "status": STATUS_COMPUTED,
            "verdict": VERDICT_INVALID_SCORER,
            "reasons": ["record_schema"],
            "record_error": "meta must be a JSON object",
        }
    return evaluate(samples, meta, certification)


# ------------------------------------------------------------ OC 模擬


def _phi(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def clipped_effect(nominal: float, sd: float, bot: float) -> float:
    """名目の効果 μ を植えたときの真の C = (1−b)·E[clip((μ + sd·Z)/(1−b), −1, 1)] (閉形式)."""
    live = 1.0 - bot
    m = nominal / live
    if sd == 0.0:
        return live * min(1.0, max(-1.0, m))
    s = sd / live
    a, b = (-1.0 - m) / s, (1.0 - m) / s
    e = -_cdf(a) + (1.0 - _cdf(b)) + m * (_cdf(b) - _cdf(a)) + s * (_phi(a) - _phi(b))
    return live * e


def nominal_effect(true_c: float, sd: float, bot: float) -> float:
    """真の C (clip 後の期待値) から植える名目値を bisection で逆算する (scoping DE-9)."""
    lo, hi = -3.0, 3.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if clipped_effect(mid, sd, bot) < true_c:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def simulate(
    nu: Nuisance,
    r_count: int,
    k: int,
    true_c: float,
    n_sims: int,
    seed: int = SIM_SEED,
) -> dict[str, float]:
    """真の C = true_c (clip 後の期待値) で pipeline (⊥ gate → 3 分岐) を n_sims 回模擬する.

    効果のモデルは v2 と同じ (arm × replicate の名目効果 e = μ + N(0, sd²)、λ = clip(e/(1−b), −1, 1)、
    ⊥ 以外の質量を (1−|λ|)·base と |λ|·(w または foil) の混合)。v2 と違い、μ は
    ``nominal_effect(true_c)`` で補正し、表の効果は clip 後の期待値を指す。
    """
    rng = np.random.default_rng(seed)
    probes = v2bat.lever_probes()
    arms = bat.JUDGE_ARMS
    n_arm, n_q = len(arms), len(probes)
    bw = np.zeros((r_count, n_arm, n_q))
    bf = np.zeros_like(bw)
    for r in range(r_count):
        for qi, p in enumerate(probes):
            b = base_probs(nu, r, p)
            for ai, arm in enumerate(arms):
                bw[r, ai, qi] = b[p.pointed[arm]]
                bf[r, ai, qi] = b[p.pointed[v2bat.FOIL[arm]]]
    live = 1.0 - nu.bot
    mu = nominal_effect(true_c, nu.sd, nu.bot)
    e = mu + nu.sd * rng.standard_normal((n_sims, r_count, n_arm))
    lam = np.clip(e / live, -1.0, 1.0)[..., None]
    mix = np.abs(lam)
    pw = (1.0 - mix) * bw + np.where(lam > 0, mix * live, 0.0)
    pf = (1.0 - mix) * bf + np.where(lam < 0, mix * live, 0.0)
    pb = np.full_like(pw, nu.bot)
    rest = np.clip(1.0 - pw - pf - pb, 0.0, 1.0)
    pvals = np.stack([pw, pf, pb, rest], axis=-1)
    pvals /= pvals.sum(axis=-1, keepdims=True)
    counts = rng.multinomial(k, pvals)  # (n_sims, R, arm, probe, 4)
    denom = n_q * k
    s = (counts[..., 0] - counts[..., 1]).sum(axis=-1) / denom  # (n_sims, R, arm)
    idx = {a: i for i, a in enumerate(arms)}
    d = np.concatenate(
        [(s[:, :, idx[a]] + s[:, :, idx[b]]) / 2.0 for a, b in bat.JUDGE_FAMILIES],
        axis=1,
    )
    comps = s.mean(axis=1)
    bot = counts[..., 2].sum(axis=(1, 3)) / (r_count * denom)
    flips, exact = _flip_matrix(d.shape[1], rng)
    verdict = decide(
        _flip_p(d - TAU, flips, exact),
        _flip_p(TAU - d, flips, exact),
        comps,
    )
    verdict = np.where(bottom_gate_ok(bot), verdict, VERDICT_INVALID_BATTERY)
    return {
        v: float(np.mean(verdict == v))
        for v in (
            VERDICT_PASS,
            VERDICT_ABSENT,
            VERDICT_UNDERPOWERED,
            VERDICT_INVALID_BATTERY,
        )
    }


def mc_margin(n_sims: int, rate: float = ALPHA) -> float:
    """Size 条件の Monte Carlo 許容幅 = 3 SE."""
    return 3.0 * float(np.sqrt(rate * (1.0 - rate) / n_sims))


def size_cap(sd: float, n_sims: int) -> float:
    """Sd ≤ 0.3: α + 3SE (v2 と同じ)。sd > 0.3: 1.5α (clip による歪みで符号反転の size が
    R に依らず ~0.055〜0.06 になるため。user 裁定、prereg v3 §6).
    """
    if sd <= SD_EXACT_MAX:
        return ALPHA + mc_margin(n_sims)
    return SIZE_CAP_WIDE


@dataclass(frozen=True)
class Criteria:
    pass_at_plant: float
    no_go_at_zero: float
    pass_at_tau: float
    no_go_at_tau: float
    size_cap: float

    @property
    def ok(self) -> bool:
        return (
            self.pass_at_plant >= POWER_TARGET
            and self.no_go_at_zero >= POWER_TARGET
            and self.pass_at_tau <= self.size_cap
            and self.no_go_at_tau <= self.size_cap
        )


def design_criteria(nu: Nuisance, r_count: int, k: int, n_sims: int) -> Criteria:
    """1 つの攪乱での 4 条件 (prereg v3 §6)。効果は全て clip 後の期待値."""
    at_plant = simulate(nu, r_count, k, DELTA_PLANT, n_sims)
    at_zero = simulate(nu, r_count, k, 0.0, n_sims)
    at_tau = simulate(nu, r_count, k, TAU, n_sims)
    return Criteria(
        pass_at_plant=at_plant[VERDICT_PASS],
        no_go_at_zero=at_zero[VERDICT_ABSENT],
        pass_at_tau=at_tau[VERDICT_PASS],
        no_go_at_tau=at_tau[VERDICT_ABSENT],
        size_cap=size_cap(nu.sd, n_sims),
    )
