"""Skill lever-only feasibility pilot — parse・推定量・判定 rule・OC 模擬 (prereg v2).

事前登録 = ``experiments/20260926-skill-lever-pilot/prereg.md``。旧 Stage B の scorer
(``scripts/stage_b_scorer.py``、旧 prereg に結び付く) は変更せず、符号反転 p (``signflip_p``) と
verdict 語彙だけを import する。

用語 (prereg v2 §3):

* arm a ∈ {A, A_rot, B, B_rot}、replicate r。w_a(q) = arm a の規則が probe q で指す選択肢、
  foil_a(q) = 族内の相手 arm が指す選択肢。
* 成分 s_{a,r} = (w_a を選んだ数 − foil_a を選んだ数) / (probe 数 × K)。⊥ と OOΩ (語彙内だが Ω_q 外) は
  分母に含め、w にも foil にも数えない。
* 単位 d_{r,f} = (s_{a,r} + s_{a_rot,r}) / 2 (族 f = {a, a_rot})。族内で arm ラベルを入れ替えると符号が反転する。
* C = mean d (2R 単位) = 4 成分の平均。完全 lookup = 1、label priming のみ = 0。

判定 (評価順、prereg v2 §5): INVALID_SCORER → INVALID_TASK_BATTERY → PASS → NO_GO_EFFECT_ABSENT →
INCONCLUSIVE_UNDERPOWERED。計算できない (transport 失敗・欠損) は ``status=not_computed``・verdict なし。
計算は CPU・numpy のみ。生成テキストの judge 採点・自由文 embedding は使わない。
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import numpy as np

from scripts import skill_lever_battery as bat
from scripts.stage_b_scorer import (
    ALPHA,
    VERDICT_ABSENT,
    VERDICT_INVALID_BATTERY,
    VERDICT_INVALID_SCORER,
    VERDICT_PASS,
    VERDICT_UNDERPOWERED,
    signflip_p,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

# ---- 凍結値 (prereg v2 §4 / §5)
TAU: Final[float] = 0.30  # PASS / NO_GO の境界 (user 裁定 DL-2)
# power を評価する効果量 (τ と別の数、DB-1 の修正)
DELTA_PLANT: Final[float] = 2.0 * TAU
BOT_MAX: Final[float] = 0.2  # arm ごと (C0 を含む) の ⊥ 率の上限
BOT_FAMILY_GAP: Final[float] = TAU / 4.0  # 族内の ⊥ 率差の上限
POWER_TARGET: Final[float] = 0.8
FROZEN_R: Final[int] = 4  # power 表の選定 (prereg v2 §6、results/power_table.json)
FROZEN_K: Final[int] = 10
TIE_TOL: Final[float] = 1e-12
EXACT_FLIP_UNITS: Final[int] = 16  # 模擬で符号反転を全列挙する単位数の上限
N_MC_FLIPS: Final[int] = 16_384  # それを超えるときの無作為 flip 数 (模擬のみ)
SIM_SEED: Final[int] = 20260926

STATUS_COMPUTED: Final[str] = "computed"
STATUS_NOT_COMPUTED: Final[str] = "not_computed"

# ---------------------------------------------------------------- parse

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)
_EDGE = "\"'`*「」『』（）()[]【】.。,、!！?？:：;；"
_LABEL_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    label: re.compile(
        r"(?<![a-z0-9])"
        + r"[\s_\-]+".join(map(re.escape, label.split("_")))
        + r"(?![a-z0-9])"
    )
    for label in bat.ACTIONS
}


def parse_choice(raw: str) -> str | None:
    """生テキスト → 行動 label (6 語彙のどれか) または None (= ⊥)。

    1. NFKC → 小文字化 (``<THINK>`` や全角の tag も同じ形になる)。
    2. ``<think>…</think>`` を除去し、閉じていないタグが残れば ⊥。
    3. 前後の空白と ``_EDGE`` の文字を除去。空なら ⊥。
    4. 各 label を単語境界 (英数字でない) で照合 (``read book`` / ``read-book`` も同じ label)。
       ちょうど 1 種の label が見つかればそれ、0 種・2 種以上は ⊥。
    """
    text = unicodedata.normalize("NFKC", raw).lower()
    text = _THINK_BLOCK.sub("", text)
    if "<think" in text or "</think" in text:
        return None
    text = text.strip().strip(_EDGE).strip()
    if not text:
        return None
    found = [label for label, pat in _LABEL_PATTERNS.items() if pat.search(text)]
    return found[0] if len(found) == 1 else None


# -------------------------------------------------------------- records


@dataclass(frozen=True)
class Sample:
    """1 回の生成。raw = None は transport 失敗 (再送 3 回後も失敗、⊥ ではない).

    call_index = run 全体での呼び出し順 (0 始まり、一意)。C0 が lever より先に走ったことの監査に使う。
    """

    call_index: int
    arm: str
    replicate: int
    probe_id: str
    k: int
    seed: int
    prompt_sha256: str
    raw: str | None
    parsed: str | None


class RecordError(ValueError):
    """記録の schema 違反 (JSON として読めない・欄の過不足・型違い)。INVALID_SCORER に落とす."""


_INT_FIELDS: Final[tuple[str, ...]] = ("call_index", "replicate", "k", "seed")
_STR_FIELDS: Final[tuple[str, ...]] = ("arm", "probe_id", "prompt_sha256")
_OPT_STR_FIELDS: Final[tuple[str, ...]] = ("raw", "parsed")
_FIELDS: Final[frozenset[str]] = frozenset(_INT_FIELDS + _STR_FIELDS + _OPT_STR_FIELDS)


def sample_from_json(obj: object) -> Sample:
    """厳密に読む: 欄の過不足・型違い (bool を int に、数値を str に等の coercion をしない) は RecordError."""
    if not isinstance(obj, dict) or set(obj) != _FIELDS:
        msg = f"record fields must be exactly {sorted(_FIELDS)}"
        raise RecordError(msg)
    for f in _INT_FIELDS:
        if type(obj[f]) is not int:
            msg = f"{f} must be int"
            raise RecordError(msg)
    for f in _STR_FIELDS:
        if type(obj[f]) is not str:
            msg = f"{f} must be str"
            raise RecordError(msg)
    for f in _OPT_STR_FIELDS:
        if obj[f] is not None and type(obj[f]) is not str:
            msg = f"{f} must be str or null"
            raise RecordError(msg)
    return Sample(**{f: obj[f] for f in _FIELDS})


def load_records(lines: Sequence[str]) -> list[Sample]:
    out = []
    for n, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError as exc:
            msg = f"line {n}: not JSON"
            raise RecordError(msg) from exc
        out.append(sample_from_json(obj))
    return out


def messages_sha256(messages: Sequence[Mapping[str, str]]) -> str:
    blob = json.dumps(list(messages), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def request_meta() -> dict[str, Any]:
    """run が記録しなければならない要求条件 (凍結値との一致を検査する)."""
    return {
        "model": bat.MODEL,
        "think": bat.THINK,
        "temperature": bat.TEMPERATURE,
        "top_p": bat.TOP_P,
        "repeat_penalty": bat.REPEAT_PENALTY,
        "num_ctx": bat.NUM_CTX,
        "num_predict": bat.NUM_PREDICT,
    }


def expected_sample(arm: str, r: int, qi: int, k: int) -> tuple[int, str]:
    probe = bat.lever_probes()[qi]
    msgs = bat.render_messages(arm, probe, bat.layout(r))
    return bat.sample_seed(r, qi, k), messages_sha256(msgs)


# ------------------------------------------------------------- estimand


def category(choice: str | None, probe: bat.LeverProbe, arm: str) -> str:
    """'w' / 'foil' / 'other' (Ω_q 内の残り 2 つ) / 'oov' (語彙内・Ω_q 外) / 'bot' (⊥)."""
    if choice is None:
        return "bot"
    if choice == probe.pointed[arm]:
        return "w"
    if choice == probe.pointed[bat.FOIL[arm]]:
        return "foil"
    if choice in probe.omega:
        return "other"
    return "oov"


def component_scores(
    choices: Mapping[tuple[str, int, str], Sequence[str | None]], r_count: int
) -> np.ndarray:
    """(4 arm, R) の s_{a,r}。choices[(arm, r, probe_id)] = K 個の parse 結果."""
    probes = bat.lever_probes()
    out = np.zeros((len(bat.LEVER_ARMS), r_count))
    for ai, arm in enumerate(bat.LEVER_ARMS):
        for r in range(r_count):
            n = 0
            net = 0
            for p in probes:
                for c in choices[(arm, r, p.probe_id)]:
                    cat = category(c, p, arm)
                    net += (cat == "w") - (cat == "foil")
                    n += 1
            out[ai, r] = net / n
    return out


def family_units(s: np.ndarray) -> np.ndarray:
    """(2R,) の d。族 {A, A_rot} の r 番目、族 {B, B_rot} の r 番目 の順."""
    idx = {a: i for i, a in enumerate(bat.LEVER_ARMS)}
    units = [(s[idx[a]] + s[idx[b]]) / 2.0 for a, b in bat.FAMILIES]
    return np.concatenate(units)


def bottom_rates(
    choices: Mapping[tuple[str, int, str], Sequence[str | None]],
    arms: Sequence[str],
    r_count: int,
) -> np.ndarray:
    probes = bat.lever_probes()
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


# --------------------------------------------------------------- decide


def bottom_gate_ok(bot: np.ndarray) -> np.ndarray:
    """(…, 4) の lever arm ⊥ 率 → gate 通過。arm ごと ≤ BOT_MAX ∧ 族内差 < BOT_FAMILY_GAP."""
    idx = {a: i for i, a in enumerate(bat.LEVER_ARMS)}
    per_arm = np.all(bot <= BOT_MAX, axis=-1)
    gaps = [np.abs(bot[..., idx[a]] - bot[..., idx[b]]) for a, b in bat.FAMILIES]
    family = np.all(np.stack(gaps, axis=-1) < BOT_FAMILY_GAP, axis=-1)
    return per_arm & family


def decide(p_lower: np.ndarray, p_upper: np.ndarray, comps: np.ndarray) -> np.ndarray:
    """gate 通過後の 3 分岐 (prereg v2 §5-3〜5)。スカラーでも配列でも同じ式.

    PASS = 片側下限 > τ (H0: C ≤ τ を棄却) ∧ 4 成分すべて > 0
    NO_GO = 片側上限 < τ (H0: C ≥ τ を棄却)
    それ以外 = INCONCLUSIVE_UNDERPOWERED
    (C > 0 の検定 p_zero は記述報告。下限 > τ が成り立てば実質的に含意され、判定行としては検出不能)
    """
    comps_positive = np.all(np.asarray(comps) > 0, axis=-1)
    passed = (np.asarray(p_lower) < ALPHA) & comps_positive
    no_go = np.asarray(p_upper) < ALPHA
    return np.where(
        passed, VERDICT_PASS, np.where(no_go, VERDICT_ABSENT, VERDICT_UNDERPOWERED)
    )


def tests_exact(d: np.ndarray) -> tuple[float, float, float]:
    """(p_zero, p_lower, p_upper)。符号反転の全列挙 (``stage_b_scorer.signflip_p``)."""
    return signflip_p(d), signflip_p(d - TAU), signflip_p(TAU - d)


# ------------------------------------------------------------ certification


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def certified_targets() -> dict[str, Path]:
    root = Path(__file__).resolve().parent
    return {
        "skill_lever_scorer.py": root / "skill_lever_scorer.py",
        "skill_lever_battery.py": root / "skill_lever_battery.py",
        "stage_b_scorer.py": root / "stage_b_scorer.py",
        "stage_b_battery.py": root / "stage_b_battery.py",
    }


def load_certification(path: Path) -> bool:
    """変異 harness の記録。全 KILLED ∧ 記録 sha256 が現在の 4 ファイルと一致。読めない = 不合格."""
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
    return [
        f"{k}: {v}"
        for k, v in rep.items()
        if isinstance(v, list) and v and k != "actions"
    ]


# -------------------------------------------------------------- evaluate


def _grid(arms: Sequence[str]) -> set[tuple[str, int, str, int]]:
    return {
        (arm, r, p.probe_id, k)
        for arm in arms
        for r in range(FROZEN_R)
        for p in bat.lever_probes()
        for k in range(FROZEN_K)
    }


def structure_violations(samples: Sequence[Sample]) -> list[str]:
    """重複・想定外の key・seed / prompt / parse の不一致 (apparatus の誤り → INVALID_SCORER)."""
    out: list[str] = []
    qidx = {p.probe_id: i for i, p in enumerate(bat.lever_probes())}
    grid = _grid(bat.ALL_ARMS)
    seen: set[tuple[str, int, str, int]] = set()
    calls = [s.call_index for s in samples]
    if len(set(calls)) != len(calls) or any(c < 0 for c in calls):
        out.append("call_index is not unique and non-negative")
    c0_calls = [s.call_index for s in samples if s.arm == bat.ARM_C0]
    lever_calls = [s.call_index for s in samples if s.arm != bat.ARM_C0]
    if c0_calls and lever_calls and max(c0_calls) > min(lever_calls):
        out.append("a lever call precedes the end of the C0 phase")
    for s in samples:
        key = (s.arm, s.replicate, s.probe_id, s.k)
        if key in seen:
            out.append(f"duplicate sample {key}")
            continue
        seen.add(key)
        if key not in grid:
            out.append(f"unexpected sample {key}")
            continue
        seed, sha = expected_sample(s.arm, s.replicate, qidx[s.probe_id], s.k)
        if s.seed != seed:
            out.append(f"{key}: seed {s.seed} != {seed}")
        if s.prompt_sha256 != sha:
            out.append(f"{key}: prompt differs from the frozen renderer")
        if s.raw is not None and s.parsed != parse_choice(s.raw):
            out.append(f"{key}: recorded parse differs from re-parse")
    return out


def evaluate(
    samples: Sequence[Sample], meta: Mapping[str, Any], certification: Path
) -> dict[str, Any]:
    """prereg v2 §5 の評価順で verdict を返す (最初に当たったもの)."""
    report: dict[str, Any] = {"status": STATUS_COMPUTED, "verdict": None, "reasons": []}

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

    # ---- 2. INVALID_TASK_BATTERY (C0 は lever run の前に実走する)
    if not _grid((bat.ARM_C0,)) <= present:
        return done(None, "c0_incomplete")
    c0_bot = float(bottom_rates(choices, (bat.ARM_C0,), FROZEN_R)[0])
    report["c0_bottom_rate"] = c0_bot
    if c0_bot > BOT_MAX:
        return done(VERDICT_INVALID_BATTERY, "c0_bottom_rate")
    if not _grid(bat.LEVER_ARMS) <= present:
        return done(None, "lever_incomplete")
    bot = bottom_rates(choices, bat.LEVER_ARMS, FROZEN_R)
    report["lever_bottom_rates"] = dict(zip(bat.LEVER_ARMS, bot.tolist(), strict=True))
    if not bool(bottom_gate_ok(bot)):
        return done(VERDICT_INVALID_BATTERY, "lever_bottom_gate")

    # ---- 3〜5.
    s = component_scores(choices, FROZEN_R)
    d = family_units(s)
    comps = s.mean(axis=1)
    p_zero, p_lower, p_upper = tests_exact(d)
    report.update(
        C=float(d.mean()),
        components=dict(zip(bat.LEVER_ARMS, comps.tolist(), strict=True)),
        p_zero=p_zero,
        p_lower=p_lower,
        p_upper=p_upper,
    )
    verdict = str(decide(np.float64(p_lower), np.float64(p_upper), comps))
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


@dataclass(frozen=True)
class Nuisance:
    """模擬の攪乱。base = 状態なしの選択分布の形、bot = ⊥ 率、sd = arm×replicate の効果のばらつき."""

    base: str  # "uniform" | "label_skew" | "position_skew"
    bot: float
    sd: float
    oov: float = 0.05  # ⊥ 以外の質量のうち語彙内・Ω_q 外に落ちる割合
    skew: float = 0.7  # skew 時に 1 選択肢へ寄る割合 (Ω_q 内の質量のうち)


def base_probs(nu: Nuisance, r: int, probe: bat.LeverProbe) -> dict[str, float]:
    """(r, probe) の状態なし分布: Ω_q の 4 label + 'oov' + 'bot'."""
    live = (1.0 - nu.bot) * (1.0 - nu.oov)
    if nu.base == "uniform":
        weights = dict.fromkeys(probe.omega, 0.25)
    else:
        target = (
            probe.pointed[bat.ARM_A]
            if nu.base == "label_skew"
            else bat.layout(r).option_order[probe.probe_id][0]
        )
        rest = (1.0 - nu.skew) / (len(probe.omega) - 1)
        weights = {o: (nu.skew if o == target else rest) for o in probe.omega}
    out = {o: live * w for o, w in weights.items()}
    out["oov"] = (1.0 - nu.bot) * nu.oov
    out["bot"] = nu.bot
    return out


def _flip_matrix(n: int, rng: np.random.Generator) -> tuple[np.ndarray, bool]:
    if n <= EXACT_FLIP_UNITS:
        ints = np.arange(1 << n, dtype=np.int64)
        bits = np.arange(n, dtype=np.int64)
        return 1.0 - 2.0 * ((ints[:, None] >> bits) & 1), True
    return rng.choice(np.array([-1.0, 1.0]), size=(N_MC_FLIPS, n)), False


def _flip_p(x: np.ndarray, flips: np.ndarray, exact: bool) -> np.ndarray:
    """(n_sims, n) → 片側 p。exact は ``signflip_p`` と同じ定義 (観測を含む全列挙)."""
    n = x.shape[1]
    obs = x.mean(axis=1)
    out = np.empty(x.shape[0])
    step = max(1, (1 << 24) // flips.shape[0])
    for i in range(0, x.shape[0], step):
        stats = x[i : i + step] @ flips.T / n
        count = np.count_nonzero(stats >= obs[i : i + step, None] - TIE_TOL, axis=1)
        out[i : i + step] = (
            count / flips.shape[0] if exact else (count + 1) / (flips.shape[0] + 1)
        )
    return out


def simulate(
    nu: Nuisance, r_count: int, k: int, effect: float, n_sims: int, seed: int = SIM_SEED
) -> dict[str, float]:
    """真の C = effect の下で pipeline (⊥ gate → 3 分岐) を n_sims 回模擬し、verdict の率を返す.

    効果のモデル: arm a・replicate r の効果 e = effect + N(0, sd²)。λ = clip(e/(1−bot), −1, 1)。
    ⊥ 以外の質量を (1−|λ|)·base と |λ|·(λ>0 なら w、λ<0 なら foil) の混合にする (simplex 内に留まる)。
    このとき E[s_{a,r}] = λ(1−bot) + (1−|λ|)(base(w) − base(foil))、族内で base の差は相殺する。
    """
    rng = np.random.default_rng(seed)
    probes = bat.lever_probes()
    n_arm, n_q = len(bat.LEVER_ARMS), len(probes)
    # base の (w, foil, bot) を (R, arm, probe) で
    bw = np.zeros((r_count, n_arm, n_q))
    bf = np.zeros_like(bw)
    for r in range(r_count):
        for qi, p in enumerate(probes):
            b = base_probs(nu, r, p)
            for ai, arm in enumerate(bat.LEVER_ARMS):
                bw[r, ai, qi] = b[p.pointed[arm]]
                bf[r, ai, qi] = b[p.pointed[bat.FOIL[arm]]]
    live = 1.0 - nu.bot
    e = effect + nu.sd * rng.standard_normal((n_sims, r_count, n_arm))
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
    idx = {a: i for i, a in enumerate(bat.LEVER_ARMS)}
    d = np.concatenate(
        [(s[:, :, idx[a]] + s[:, :, idx[b]]) / 2.0 for a, b in bat.FAMILIES], axis=1
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
    """size 条件の Monte Carlo 許容幅 = 3 SE."""
    return 3.0 * float(np.sqrt(rate * (1.0 - rate) / n_sims))


def design_criteria(nu: Nuisance, r_count: int, k: int, n_sims: int) -> dict[str, Any]:
    """1 つの攪乱での 4 条件 (prereg v2 §6)。"""
    at_plant = simulate(nu, r_count, k, DELTA_PLANT, n_sims)
    at_zero = simulate(nu, r_count, k, 0.0, n_sims)
    at_tau = simulate(nu, r_count, k, TAU, n_sims)
    size_cap = ALPHA + mc_margin(n_sims)
    crit = {
        "pass_at_plant": at_plant[VERDICT_PASS],
        "no_go_at_zero": at_zero[VERDICT_ABSENT],
        "pass_at_tau": at_tau[VERDICT_PASS],
        "no_go_at_tau": at_tau[VERDICT_ABSENT],
    }
    crit["ok"] = (
        crit["pass_at_plant"] >= POWER_TARGET
        and crit["no_go_at_zero"] >= POWER_TARGET
        and crit["pass_at_tau"] <= size_cap
        and crit["no_go_at_tau"] <= size_cap
    )
    return crit
