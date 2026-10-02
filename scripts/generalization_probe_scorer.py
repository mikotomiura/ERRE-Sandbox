"""候補 G (汎化 probe) — parse・推定量・τ 判定 (有界の平均の betting e-value)・判定 rule (prereg §3〜§5).

用語 (prereg §3):

* arm a ∈ {A, A_rot, B, B_rot}、単位 u = (族 f, つ組 j, replicate r)。w_a(q) = arm a の規則が probe q で指す
  選択肢、foil_a(q) = 族内の相手 arm が指す選択肢。Ω = 族の 3 label (分類に依らない)。
* 単位の成分 s_{a,u} = (w_a を選んだ数 − foil_a を選んだ数) / (3K) (つ組の 3 probe × K)。⊥・OOΩ (語彙内だが
  Ω 外) と Ω の残り 1 つは分母に含め、w にも foil にも数えない (v2 と同じ)。
* d_u = (s_{a,u} + s_{a',u}) / 2 (族 f = {a, a'})。C = mean_u d_u。成分 = arm ごとの s の平均 (4 つ)。

τ 判定 (prereg §5、統合系 ADR §6 gate 2 の (a)):

* PASS 枝: E⁺ = mean_{λ∈Λ⁺} Π_u (1 + λ(d_u − τ))、Λ⁺ = {j/4 · 1/(1+τ) : j = 1..4}。
* NO_GO 枝: E⁻ = mean_{μ∈Λ⁻} Π_u (1 + μ(τ − d_u))、Λ⁻ = {j/4 · 1/(1−τ)}。
* 有効性: 固定した prompt の schedule に条件付け、単位の d が独立で [−1, 1] に有界なら、単位平均の平均 ≤ τ
  (PASS 枝の帰無) の下で、固定の λ について E[Π(1 + λ(d_u − τ))] = Π(1 + λ(μ_u − τ)) ≤ (1 + λ(μ̄ − τ))^n ≤ 1
  (AM-GM。各因子は非負)。混合も同じ。Markov で P(E⁺ ≥ 1/α) ≤ α。対称性・同分布・交換可能性を仮定しない。
  NO_GO 枝も同じ。2 枝は同時に立たない (log の凹性: d̄ ≤ τ なら E⁺ ≤ 1、d̄ ≥ τ なら E⁻ ≤ 1)。

判定 (評価順): INVALID_SCORER → (status=not_computed) → INVALID_TASK_BATTERY → PASS → NO_GO_EFFECT_ABSENT →
INCONCLUSIVE_UNDERPOWERED。verdict 語彙は research-positioning §8 の 5 語 (旧 Stage B scorer の定数を import)。
計算は CPU・numpy のみ。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import generalization_probe_battery as bat  # noqa: E402
from scripts import generalization_probe_fixtures as fx  # noqa: E402
from scripts.stage_b_scorer import (  # noqa: E402
    ALPHA,
    VERDICT_ABSENT,
    VERDICT_INVALID_BATTERY,
    VERDICT_INVALID_SCORER,
    VERDICT_PASS,
    VERDICT_UNDERPOWERED,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

# ---- 凍結値 (prereg §4 / §5)
TAU: Final[float] = 0.30  # v2 と同じ (user 裁定 DL-2 の literal を継ぐ)
DELTA_PLANT: Final[float] = 2.0 * TAU
BOT_MAX: Final[float] = 0.2
BOT_FAMILY_GAP: Final[float] = TAU / 4.0
ENVELOPE_MARGIN: Final[float] = (
    0.05  # 本走の ⊥ 率は pilot の masked の最大 + 0.05 まで (Codex MEDIUM-6)
)
FROZEN_K: Final[int] = 1
LAMBDA_FRACTIONS: Final[tuple[float, ...]] = (0.25, 0.5, 0.75, 1.0)
CAP_PLUS: Final[float] = 1.0 / (1.0 + TAU)
CAP_MINUS: Final[float] = 1.0 / (1.0 - TAU)
LOG_THRESHOLD: Final[float] = math.log(1.0 / ALPHA)
OBSERVED_FIELDS: Final[tuple[str, ...]] = (
    "model_digest",
    "ollama_version",
    "template_sha256",
)

STATUS_COMPUTED: Final[str] = "computed"
STATUS_NOT_COMPUTED: Final[str] = "not_computed"

# ---------------------------------------------------------------- parse

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)
_LABEL_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    label: re.compile(
        r"(?<![a-z0-9])"
        + r"[\s_\-]+".join(map(re.escape, label.split("_")))
        + r"(?![a-z0-9])"
    )
    for label in bat.ACTIONS
}


def parse_choice(raw: str) -> str | None:
    """生テキスト → 行動 label (6 語彙のどれか) または None (= ⊥)。v2 と同じ規則を新語彙で.

    NFKC → 小文字化 → 閉じた think ブロックを除去 (閉じない tag が残れば ⊥) → 6 label のちょうど 1 種を
    単語境界で含めばその label。0 種・2 種以上は ⊥。
    """
    text = unicodedata.normalize("NFKC", raw).lower()
    text = _THINK_BLOCK.sub(" ", text)
    if "<think" in text or "</think" in text:
        return None
    found = [label for label, pat in _LABEL_PATTERNS.items() if pat.search(text)]
    if len(found) != 1:
        return None
    return found[0]


# ---------------------------------------------------------------- records


@dataclass(frozen=True)
class Sample:
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
    """記録の schema 違反 (prereg §4)。evaluate は例外で止めず INVALID_SCORER を返す."""


_INT_FIELDS: Final[tuple[str, ...]] = ("call_index", "replicate", "k", "seed")
_STR_FIELDS: Final[tuple[str, ...]] = ("arm", "probe_id", "prompt_sha256")
_OPT_STR_FIELDS: Final[tuple[str, ...]] = ("raw", "parsed")
_FIELDS: Final[frozenset[str]] = frozenset(
    (*_INT_FIELDS, *_STR_FIELDS, *_OPT_STR_FIELDS)
)


def sample_from_json(obj: object) -> Sample:
    if not isinstance(obj, dict) or set(obj) != _FIELDS:
        msg = "record fields differ from the schema"
        raise RecordError(msg)
    for f in _INT_FIELDS:
        if type(obj[f]) is not int:
            msg = f"field {f} is not an int"
            raise RecordError(msg)
    for f in _STR_FIELDS:
        if not isinstance(obj[f], str):
            msg = f"field {f} is not a str"
            raise RecordError(msg)
    for f in _OPT_STR_FIELDS:
        if obj[f] is not None and not isinstance(obj[f], str):
            msg = f"field {f} is not a str or null"
            raise RecordError(msg)
    return Sample(**obj)


def load_records(lines: Sequence[str]) -> list[Sample]:
    out = []
    for line in lines:
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            msg = "record is not JSON"
            raise RecordError(msg) from exc
        out.append(sample_from_json(obj))
    return out


def messages_sha256(messages: Sequence[Mapping[str, str]]) -> str:
    blob = json.dumps(list(messages), ensure_ascii=False, sort_keys=True).encode(
        "utf-8"
    )
    return hashlib.sha256(blob).hexdigest()


def request_meta() -> dict[str, Any]:
    """run が meta.json の ``request`` に記録し、一致を検査する要求条件 (prereg §4)."""
    return {
        "model": bat.MODEL,
        "think": bat.THINK,
        "options": {
            "temperature": bat.TEMPERATURE,
            "top_p": bat.TOP_P,
            "repeat_penalty": bat.REPEAT_PENALTY,
            "num_ctx": bat.NUM_CTX,
            "num_predict": bat.NUM_PREDICT,
        },
    }


def meta_violations(
    meta: object, reference_observed: Mapping[str, str] | None = None
) -> list[str]:
    """meta = {"request": request_meta(), "observed": {model_digest, ollama_version, template_sha256}}.

    observed は driver が実行環境から読んだ値 (モデルの同定、Codex MEDIUM-11)。reference が与えられたら
    (本走では pilot の値)、一致を要求する。
    """
    if not isinstance(meta, dict) or set(meta) != {"request", "observed"}:
        return ["meta: fields differ from the schema"]
    out = []
    if meta["request"] != request_meta():
        out.append("meta: request differs from the frozen values")
    observed = meta["observed"]
    if (
        not isinstance(observed, dict)
        or set(observed) != set(OBSERVED_FIELDS)
        or not all(
            isinstance(observed[f], str) and observed[f] for f in OBSERVED_FIELDS
        )
    ):
        out.append("meta: observed environment is missing or malformed")
    elif reference_observed is not None and dict(observed) != dict(reference_observed):
        out.append("meta: observed environment differs from the pilot")
    return out


_PROBE_BY_ID: Final[dict[str, bat.Probe]] = {p.probe_id: p for p in bat.probes()}


def expected_sample(arm: str, r: int, probe: bat.Probe, k: int) -> tuple[int, str]:
    """(seed, prompt sha256)。族ごとの名前空間で、族内の 2 arm とつ組の 3 probe が seed を共有する."""
    ns = f"fam{bat.ARM_FAMILY[arm]}"
    return bat.sample_seed(ns, r, probe.triple, k), messages_sha256(
        bat.render_messages(arm, probe, r)
    )


def grid(r_count: int, k_count: int) -> set[tuple[str, int, str, int]]:
    return {
        (arm, r, p.probe_id, k)
        for arm in bat.LEVER_ARMS
        for r in range(r_count)
        for p in bat.probes()
        for k in range(k_count)
    }


def structure_violations(
    samples: Sequence[Sample], r_count: int, k_count: int
) -> list[str]:
    """記録の構造 (prereg §5-1): 重複・grid 外・seed・prompt・parse・call_index."""
    out: list[str] = []
    keys = [(s.arm, s.replicate, s.probe_id, s.k) for s in samples]
    if len(set(keys)) != len(keys):
        out.append("duplicate (arm, replicate, probe, k)")
    the_grid = grid(r_count, k_count)
    if not set(keys) <= the_grid:
        out.append("record outside the frozen grid")
    idx = [s.call_index for s in samples]
    if len(set(idx)) != len(idx) or any(i < 0 for i in idx):
        out.append("call_index is not unique and non-negative")
    for s in samples:
        if (s.arm, s.replicate, s.probe_id, s.k) not in the_grid:
            continue
        seed, sha = expected_sample(s.arm, s.replicate, _PROBE_BY_ID[s.probe_id], s.k)
        if s.seed != seed:
            out.append("seed differs from the frozen schedule")
        if s.prompt_sha256 != sha:
            out.append("prompt differs from the frozen renderer")
        if s.raw is not None and parse_choice(s.raw) != s.parsed:
            out.append("recorded parse differs from re-parse")
    return sorted(set(out))


# ------------------------------------------------------------- estimand


def category(choice: str | None, probe: bat.Probe, arm: str) -> str:
    """'w' / 'foil' / 'other' (Ω の残り 1 つ) / 'oov' (語彙内・Ω 外) / 'bot' (⊥)."""
    if choice is None:
        return "bot"
    if choice == probe.pointed[arm]:
        return "w"
    if choice == probe.pointed[bat.FOIL[arm]]:
        return "foil"
    if choice in bat.family_actions(bat.ARM_FAMILY[arm]):
        return "other"
    return "oov"


def arm_unit_scores(
    choices: Mapping[tuple[str, int, str], Sequence[str | None]], r_count: int
) -> dict[tuple[str, int, int], float]:
    """(arm, j, r) → s_{a,u}。choices[(arm, r, probe_id)] = K 個の parse 結果."""
    out: dict[tuple[str, int, int], float] = {}
    for arm in bat.LEVER_ARMS:
        for r in range(r_count):
            for j in range(bat.N_TRIPLES):
                net = 0
                n = 0
                for p in bat.triple_probes(j):
                    for c in choices[(arm, r, p.probe_id)]:
                        cat = category(c, p, arm)
                        net += (cat == "w") - (cat == "foil")
                        n += 1
                out[(arm, j, r)] = net / n
    return out


def unit_scores(s: Mapping[tuple[str, int, int], float], r_count: int) -> np.ndarray:
    """(n,) の d。単位の順は ``bat.units`` (r, 族, つ組)."""
    out = []
    for u in bat.units(r_count):
        a, b = bat.FAMILIES[u.family]
        out.append(
            (s[(a, u.triple, u.replicate)] + s[(b, u.triple, u.replicate)]) / 2.0
        )
    return np.array(out)


def components(s: Mapping[tuple[str, int, int], float]) -> np.ndarray:
    """(4,) arm ごとの s の平均 (LEVER_ARMS の順)."""
    return np.array(
        [
            np.mean([v for (arm, _, _), v in s.items() if arm == a])
            for a in bat.LEVER_ARMS
        ]
    )


def bottom_rates(
    choices: Mapping[tuple[str, int, str], Sequence[str | None]],
    arms: Sequence[str],
    r_count: int,
) -> np.ndarray:
    out = []
    for arm in arms:
        cs = [
            c
            for r in range(r_count)
            for p in bat.probes()
            for c in choices[(arm, r, p.probe_id)]
        ]
        out.append(sum(c is None for c in cs) / len(cs))
    return np.array(out)


# --------------------------------------------------------------- τ 判定


def log_capital(x: np.ndarray, lam: float) -> np.ndarray:
    """log Π_u (1 + λ x_u) (最後の軸で)。因子が 0 なら −inf。x は (…, n)."""
    f = 1.0 + lam * np.asarray(x, dtype=float)
    f = np.maximum(f, 0.0)  # 浮動小数の誤差で僅かに負になる分を 0 に (有界の仮定の内側)
    with np.errstate(divide="ignore"):
        return np.log(f).sum(axis=-1)


def log_e_value(x: np.ndarray, cap: float) -> np.ndarray:
    """log mean_{λ∈Λ} Π_u (1 + λ x_u)、Λ = {j/4 · cap : j = 1..4}."""
    logs = np.stack([log_capital(x, fr * cap) for fr in LAMBDA_FRACTIONS], axis=-1)
    top = np.max(logs, axis=-1, keepdims=True)
    safe = np.where(np.isfinite(top), top, 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        mixed = np.log(np.mean(np.exp(logs - safe), axis=-1)) + safe[..., 0]
    return np.where(np.isfinite(top[..., 0]), mixed, -np.inf)


def e_values(d: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(log E⁺, log E⁻, log E⁰)。E⁰ = 平均 > 0 の e-value (記述報告のみ)."""
    d = np.asarray(d, dtype=float)
    return (
        log_e_value(d - TAU, CAP_PLUS),
        log_e_value(TAU - d, CAP_MINUS),
        log_e_value(d, 1.0),
    )


def decide(
    log_e_plus: np.ndarray, log_e_minus: np.ndarray, comps: np.ndarray
) -> np.ndarray:
    """gate 通過後の 3 分岐 (prereg §5-4〜6)。スカラーでも配列でも同じ式.

    PASS = E⁺ ≥ 1/α (H0: C ≤ τ を棄却) ∧ 4 成分すべて > 0
    NO_GO = E⁻ ≥ 1/α (H0: C ≥ τ を棄却)
    それ以外 = INCONCLUSIVE_UNDERPOWERED
    """
    comps_positive = np.all(np.asarray(comps) > 0, axis=-1)
    passed = (np.asarray(log_e_plus) >= LOG_THRESHOLD) & comps_positive
    no_go = np.asarray(log_e_minus) >= LOG_THRESHOLD
    return np.where(
        passed, VERDICT_PASS, np.where(no_go, VERDICT_ABSENT, VERDICT_UNDERPOWERED)
    )


def bottom_gate_ok(bot: np.ndarray, bot_max: float = BOT_MAX) -> np.ndarray:
    """(…, 4) の lever arm ⊥ 率 → gate 通過。arm ごと ≤ bot_max ∧ 族内差 < BOT_FAMILY_GAP."""
    idx = {a: i for i, a in enumerate(bat.LEVER_ARMS)}
    per_arm = np.all(bot <= bot_max, axis=-1)
    gaps = [np.abs(bot[..., idx[a]] - bot[..., idx[b]]) for a, b in bat.FAMILIES]
    family = np.all(np.stack(gaps, axis=-1) < BOT_FAMILY_GAP, axis=-1)
    return per_arm & family


def envelope_bottom_max(pilot_max_bottom: float) -> float:
    """本走の arm ごとの ⊥ 率の上限 = min(0.2, pilot の masked の最大 + 0.05) (prereg §8.3)."""
    return min(BOT_MAX, pilot_max_bottom + ENVELOPE_MARGIN)


# ------------------------------------------------------------ certification


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


CERTIFIED: Final[tuple[str, ...]] = (
    "generalization_probe_battery.py",
    "generalization_probe_fixtures.py",
    "generalization_probe_scorer.py",
    "generalization_probe_sim.py",
    "generalization_probe_pilot_gate.py",
    "stage_b_scorer.py",
)


def certified_targets() -> dict[str, Path]:
    root = Path(__file__).resolve().parent
    return {f"scripts/{name}": root / name for name in CERTIFIED}


def load_certification(path: Path) -> bool:
    """certification が存在し、明細が 1 件以上・label が一意・全 KILLED で、記録 sha256 が現在のコードと一致するか."""
    try:
        cert = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(cert, dict):
        return False
    mutants = cert.get("mutants")
    if not isinstance(mutants, list) or not mutants:
        return False
    if not all(isinstance(m, dict) for m in mutants):
        return False
    labels = [m.get("label") for m in mutants]
    if len(set(labels)) != len(labels):
        return False
    if not all(m.get("status") == "KILLED" for m in mutants):
        return False
    recorded = cert.get("target_sha256")
    if not isinstance(recorded, dict):
        return False
    current = {k: _sha256(v) for k, v in certified_targets().items()}
    return recorded == current


# ----------------------------------------------------------------- 判定


def evaluate(
    samples: Sequence[Sample],
    meta: object,
    *,
    certified: bool,
    r_count: int,
    pilot_max_bottom: float,
    reference_observed: Mapping[str, str] | None,
    k_count: int = FROZEN_K,
) -> dict[str, Any]:
    """記録 → 判定 (prereg §5 の評価順)。pilot_max_bottom・reference_observed は pilot の機械判定の出力から."""
    result: dict[str, Any] = {"status": STATUS_COMPUTED, "verdict": None, "reasons": []}
    invalid: list[str] = []
    if not certified:
        invalid.append("certification missing, stale, or not all KILLED")
    if bat.battery_violations(r_count):
        invalid.append("battery check failed")
    if fx.fixture_violations(r_count):
        invalid.append("fixture gate failed")
    invalid += meta_violations(meta, reference_observed)
    invalid += structure_violations(samples, r_count, k_count)
    if invalid:
        result.update(verdict=VERDICT_INVALID_SCORER, reasons=invalid)
        return result
    if any(s.raw is None for s in samples) or len(samples) != len(
        grid(r_count, k_count)
    ):
        result.update(
            status=STATUS_NOT_COMPUTED, reasons=["transport failure or missing rows"]
        )
        return result
    choices: dict[tuple[str, int, str], list[str | None]] = {}
    for s in sorted(samples, key=lambda x: (x.arm, x.replicate, x.probe_id, x.k)):
        choices.setdefault((s.arm, s.replicate, s.probe_id), []).append(s.parsed)
    lever_bot = bottom_rates(choices, bat.LEVER_ARMS, r_count)
    bot_max = envelope_bottom_max(pilot_max_bottom)
    result["lever_bottom_rates"] = dict(
        zip(bat.LEVER_ARMS, map(float, lever_bot), strict=True)
    )
    result["bottom_max"] = bot_max
    if not bool(bottom_gate_ok(lever_bot, bot_max)):
        result.update(
            verdict=VERDICT_INVALID_BATTERY, reasons=["bottom-rate gate / envelope"]
        )
        return result
    s = arm_unit_scores(choices, r_count)
    d = unit_scores(s, r_count)
    comps = components(s)
    le_plus, le_minus, le_zero = e_values(d)
    result.update(
        verdict=str(decide(le_plus, le_minus, comps)),
        reasons=["decided"],
        C=float(np.mean(d)),
        n_units=int(d.size),
        components=dict(zip(bat.LEVER_ARMS, map(float, comps), strict=True)),
        log_e_plus=float(le_plus),
        log_e_minus=float(le_minus),
        log_e_zero=float(le_zero),
    )
    return result


def main(argv: list[str] | None = None) -> int:
    """本走の判定 (prereg §9)。R・envelope・観測環境は pilot の機械判定 (GO) の出力から読む."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", type=Path, required=True)
    ap.add_argument("--meta", type=Path, required=True)
    ap.add_argument("--cert", type=Path, required=True)
    ap.add_argument("--gate", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    gate = json.loads(args.gate.read_text(encoding="utf-8"))
    go = (
        isinstance(gate, dict)
        and gate.get("decision") == "GO"
        and type(gate.get("R")) is int
        and isinstance(gate.get("masked_max_bottom"), float)
        and isinstance(gate.get("observed"), dict)
    )
    result: dict[str, Any]
    if not go:
        result = {
            "status": STATUS_NOT_COMPUTED,
            "verdict": None,
            "reasons": ["the pilot gate did not decide GO"],
        }
    else:
        try:
            samples = load_records(
                args.records.read_text(encoding="utf-8").splitlines()
            )
            meta = json.loads(args.meta.read_text(encoding="utf-8"))
        except (RecordError, json.JSONDecodeError) as exc:
            result = {
                "status": STATUS_COMPUTED,
                "verdict": VERDICT_INVALID_SCORER,
                "reasons": [f"record_schema: {exc}"],
            }
        else:
            result = evaluate(
                samples,
                meta,
                certified=load_certification(args.cert),
                r_count=gate["R"],
                pilot_max_bottom=gate["masked_max_bottom"],
                reference_observed=gate["observed"],
            )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
