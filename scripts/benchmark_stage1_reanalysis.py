"""判別性 gate 段 1 — 凍結 dir の既存記録の再解析 (CPU・read-only)。

規則の SSOT は ``experiments/20261126-benchmark-stage1-reanalysis/rules.md`` (FROZEN)。
本 module の定数はその写しで、rules.md と食い違えば rules.md が正しい。

- 凍結 dir の scorer / battery / pilot gate は **import だけ** にする (書き換えない)。
- 項目別に見る量は対を完成させた d / D (arm ごとの |s の平均| は使わない)。
- 雑音は replicate を cluster にした推定 (解析解、乱数なし)。
- 「採る / 保留」は段 2 の主たる battery の優先順位づけで、battery を閉じる判断ではない。
  1 モデル (qwen3:8b) の結果で battery を閉じない。旧 verdict を再判定しない。

使い方: ``python -m scripts.benchmark_stage1_reanalysis --out <dir>`` (``PYTHONDONTWRITEBYTECODE=1`` を付ける)。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from statistics import NormalDist
from typing import TYPE_CHECKING, Any, Final

import numpy as np
from scripts import generalization_probe_battery as gbat
from scripts import generalization_probe_pilot_gate as gpg
from scripts import generalization_probe_scorer as gsc
from scripts import o_time_probe_battery as obat
from scripts import o_time_probe_pilot_gate as opg
from scripts import o_time_probe_scorer as osc
from scripts import skill_experience_battery as v3bat
from scripts import skill_experience_scorer as v3sc
from scripts import skill_lever_battery as v2bat
from scripts import skill_lever_scorer as v2sc

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------ 凍結の規則 (rules.md の写し)

_V2: Final[str] = "experiments/20260926-skill-lever-pilot/results"
_V3: Final[str] = "experiments/20260926-experience-skill-pilot/results"
_G: Final[str] = "experiments/20261001-generalization-probe-pilot/results"
_OT: Final[str] = "experiments/20261008-o-time-probe-pilot/results"

# rules.md §1: 入力の sha256。不一致なら停止する。
INPUTS: Final[dict[str, tuple[str, str]]] = {
    "v2_records": (
        f"{_V2}/run/samples.jsonl",
        "d0cf5084201a138f92f391ba60d4c66bd9cab6ce7f0c95d8af0b4b8692f7125a",
    ),
    "v2_results": (
        f"{_V2}/run/results.json",
        "fc71df8e9c94c5f4005b6267062bb818bba4dbd62fffafacb52902741b8da2c0",
    ),
    "v3_records": (
        f"{_V3}/run/samples.jsonl",
        "52c2140fa9e34c9105197be13acb6a1e6a6eb5f4c1208529194bde1e7a85c8cc",
    ),
    "v3_results": (
        f"{_V3}/run/results.json",
        "508893ba1a5c0fff52afd17df25842732b08b28bfee55598961920744d8c3c81",
    ),
    "g_records": (
        f"{_G}/run/records.jsonl",
        "97ec2c5b88907583611135d36285e672c723329a9cd4eb2796ebb4348b14766d",
    ),
    "g_results": (
        f"{_G}/run/results.json",
        "430f2724504f7114486ddc009b7dd753b7d58f17b90098cd0f9113d98dc71d44",
    ),
    "g_pilot_records": (
        f"{_G}/pilot/records.jsonl",
        "eb9495cd63aa0893d8193a02f305619f3ebb7a2cb5f703a3f56b3027dceba4ef",
    ),
    "ot_records": (
        f"{_OT}/run/records.jsonl",
        "26a18bcd9e179dd4d7f049865b2a024050bdf270f15a65c4c2adb8e9665eb972",
    ),
    "ot_results": (
        f"{_OT}/run/results.json",
        "156c64affadc6a7e962b321bad8cd218941895e7543d3eb1d95f0a7dc618e274",
    ),
    "ot_pilot_records": (
        f"{_OT}/pilot/records.jsonl",
        "29935540360d8efdf4863bd1674554cdb356c390b23b7a149c1f73f7fb1dd13b",
    ),
}

BATTERIES: Final[tuple[str, ...]] = ("v2", "v3", "G", "O_time")

# rules.md §5: 1 呼び出しあたりの秒 = qwen3:8b の本走の実績 (ADR §2 の表の 秒 / 呼び出し数)。
# 費用は有理数で正確に計算する (Codex HIGH-3)。
SEC_PER_CALL: Final[dict[str, Fraction]] = {
    "v2": Fraction(200, 1200),  # 約 3 分 20 秒
    "v3": Fraction(420, 2160),  # 約 7 分
    "G": Fraction(375, 1728),  # 約 6 分 15 秒
    "O_time": Fraction(7500, 13824),  # 約 2 時間 5 分
}
# 表示位置が一巡する R の倍数 (各 battery の check_position_balance。Codex HIGH-1)
R_MULTIPLE: Final[dict[str, int]] = {
    "v2": v2bat.N_POSITIONS,
    "v3": v2bat.N_POSITIONS,  # v3 は v2 の layout を使う
    "G": gbat.N_POSITIONS,
    "O_time": obat.N_POSITIONS,
}
SPEED_14B: Final[int] = (
    2  # 14B は qwen3:8b の 2 倍遅いと仮定 (未実測。記述の列だけに使う)
)
ALPHA: Final[float] = 0.05
N_PAIRS: Final[int] = 15  # 6 モデルの対
POWER: Final[float] = 0.8
DELTA_GRID: Final[tuple[float, ...]] = (0.10, 0.15, 0.20)
DELTA_REF: Final[float] = 0.15  # R の見積もりの参照値 (Δ_min ではない)
SIGMA_UP_LEVEL: Final[float] = 0.95  # σ の χ² 上側限界の信頼水準
R_FLOOR: Final[int] = 2  # 分散を推定できる最小の R

# rules.md §6: 採る / 保留
BOT_HOLD: Final[float] = 0.2  # いずれかの arm の ⊥ 率がこれを超えれば保留
Q_HOLD: Final[float] = 0.5  # battery 全体の q がこれ未満なら保留
CEILING: Final[float] = 0.95  # C + Z_CEIL·SE がこれ以上なら保留
Z_CEIL: Final[float] = 1.96
BUDGET_SECONDS: Final[int] = (
    3 * 3600
)  # 1 モデルあたりの累計 (qwen3:8b 換算・モデルの平均。DU-7)
C_MATCH_TOL: Final[float] = 1e-12  # results.json の C との一致

CATEGORIES: Final[tuple[str, ...]] = ("w", "foil", "other", "oov", "bot")

DECISION_ADOPT: Final[str] = "ADOPT"
DECISION_HOLD: Final[str] = "HOLD"


class InputError(RuntimeError):
    """入力の hash 不一致・自己照合の失敗・非有限値。集計を止める."""


# ------------------------------------------------------------------ 入力


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_inputs(
    root: Path, inputs: Mapping[str, tuple[str, str]] = INPUTS
) -> dict[str, str]:
    """全入力の sha256 を照合する。1 つでも違えば InputError (読めないも含む)."""
    bad = []
    for name, (rel, want) in inputs.items():
        p = root / rel
        got = sha256_file(p) if p.is_file() else "<missing>"
        if got != want:
            bad.append(f"{name}: {rel} sha256 {got} != {want}")
    if bad:
        raise InputError("; ".join(bad))
    return {name: want for name, (_, want) in inputs.items()}


def jsonl_lines(text: str) -> list[str]:
    """JSONL を改行 (LF) だけで行に割る。``splitlines()`` は U+2028 等でも割るので使わない."""
    return [ln for ln in text.split("\n") if ln.strip()]


def _read_lines(root: Path, key: str) -> list[str]:
    return jsonl_lines((root / INPUTS[key][0]).read_text(encoding="utf-8"))


def _read_json(root: Path, key: str) -> dict[str, Any]:
    out: dict[str, Any] = json.loads(
        (root / INPUTS[key][0]).read_text(encoding="utf-8")
    )
    return out


# ------------------------------------------------------------------ 分布


def _reg_lower_gamma(a: float, x: float) -> float:
    """正則化された下側不完全ガンマ P(a, x) (級数。x < a+1 の外では連分数)."""
    if x <= 0.0:
        return 0.0
    lg = math.lgamma(a)
    if x < a + 1.0:
        term = 1.0 / a
        total = term
        n = 0
        while abs(term) > abs(total) * 1e-16 and n < 100_000:
            n += 1
            term *= x / (a + n)
            total += term
        return total * math.exp(-x + a * math.log(x) - lg)
    # 上側 Q の連分数 (Lentz)
    tiny = 1e-300
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 100_000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        d = tiny if abs(d) < tiny else d
        c = b + an / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-16:
            break
    return 1.0 - math.exp(-x + a * math.log(x) - lg) * h


def chi2_ppf(p: float, df: int) -> float:
    """χ² 分布の p 分位点 (二分法)."""
    lo, hi = 0.0, max(10.0, df * 10.0)
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if _reg_lower_gamma(df / 2.0, mid / 2.0) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def z_sum() -> float:
    """(z_{1−α/(2·N_PAIRS)} + z_{POWER})."""
    nd = NormalDist()
    return nd.inv_cdf(1.0 - ALPHA / (2 * N_PAIRS)) + nd.inv_cdf(POWER)


def r_needed(sigma: float, delta: float) -> int:
    """R(Δ) = ⌈2·σ²·(z + z)² / Δ²⌉ (下限 R_FLOOR)。モデル間の共分散は 0 と置く (保守側)."""
    return max(R_FLOOR, math.ceil(2.0 * sigma**2 * z_sum() ** 2 / delta**2))


# ------------------------------------------------------------ battery ごとの集計


@dataclass
class BatteryData:
    """1 battery の再解析の材料."""

    name: str
    rep_units: np.ndarray  # (R, U) 対を完成させた単位の値 (replicate ごと)
    items: dict[
        str, list[float]
    ]  # 項目 → replicate ごとの項目の値 (対を完成させたもの)
    cats: dict[str, Counter[str]]  # lever arm → 出力の分類の数
    total_calls: int  # 記録の全呼び出し (C0・対照 arm を含む)
    describe: dict[str, Any] = field(default_factory=dict)


def _cell(cs: Sequence[str | None], cat: Callable[[str | None], str]) -> float:
    return sum((cat(c) == "w") - (cat(c) == "foil") for c in cs) / len(cs)


def _v2v3(
    name: str,
    lines: Sequence[str],
    arms: Sequence[str],
    as_arm: Mapping[str, str],
    r_count: int,
    frozen_units: Callable[[dict[tuple[str, int, str], list[str | None]]], np.ndarray],
) -> BatteryData:
    samples = v2sc.load_records(lines)
    choices: dict[tuple[str, int, str], list[str | None]] = {}
    for s in samples:
        choices.setdefault((s.arm, s.replicate, s.probe_id), []).append(s.parsed)
    probes = v2bat.lever_probes()
    fams = [(arms[0], arms[1]), (arms[2], arms[3])]
    cats: dict[str, Counter[str]] = {a: Counter() for a in arms}
    s_cell: dict[tuple[str, int, str], float] = {}
    for a in arms:
        for r in range(r_count):
            for p in probes:
                cs = choices[(a, r, p.probe_id)]
                for c in cs:
                    cats[a][v2sc.category(c, p, as_arm[a])] += 1
                s_cell[(a, r, p.probe_id)] = _cell(
                    cs, lambda c, p=p, a=a: v2sc.category(c, p, as_arm[a])
                )
    # 単位 (族, r) の d と、項目 (probe) の値。単位の値は凍結の関数で照合する。
    rep_units = np.zeros((r_count, len(fams)))
    items: dict[str, list[float]] = {p.probe_id: [] for p in probes}
    for r in range(r_count):
        for fi, (a, b) in enumerate(fams):
            per_probe = [
                (s_cell[(a, r, p.probe_id)] + s_cell[(b, r, p.probe_id)]) / 2.0
                for p in probes
            ]
            rep_units[r, fi] = float(np.mean(per_probe))
        for p in probes:
            items[p.probe_id].append(
                float(
                    np.mean(
                        [
                            (s_cell[(a, r, p.probe_id)] + s_cell[(b, r, p.probe_id)])
                            / 2.0
                            for a, b in fams
                        ]
                    )
                )
            )
    frozen = frozen_units(choices)  # (2R,) 族 0 の r 順、族 1 の r 順
    mine = np.concatenate([rep_units[:, 0], rep_units[:, 1]])
    if not np.allclose(mine, frozen, rtol=0.0, atol=C_MATCH_TOL):
        msg = f"{name}: unit values differ from the frozen scorer"
        raise InputError(msg)
    return BatteryData(
        name=name,
        rep_units=rep_units,
        items=items,
        cats=cats,
        total_calls=len(samples),
    )


def battery_v2(lines: Sequence[str]) -> BatteryData:
    arms = v2bat.LEVER_ARMS
    r_count = v2sc.FROZEN_R
    return _v2v3(
        "v2",
        lines,
        arms,
        {a: a for a in arms},
        r_count,
        lambda ch: v2sc.family_units(v2sc.component_scores(ch, r_count)),
    )


def battery_v3(lines: Sequence[str]) -> BatteryData:
    arms = v3bat.JUDGE_ARMS
    r_count = v3sc.FROZEN_R
    return _v2v3(
        "v3",
        lines,
        arms,
        {a: v3bat.POINTS_AS[a] for a in arms},
        r_count,
        lambda ch: v2sc.family_units(v3sc.component_scores(ch, arms, r_count)),
    )


def battery_g(lines: Sequence[str], r_count: int) -> BatteryData:
    samples = gsc.load_records(lines)
    choices: dict[tuple[str, int, str], list[str | None]] = {}
    for s in samples:
        choices.setdefault((s.arm, s.replicate, s.probe_id), []).append(s.parsed)
    probes = gbat.probes()
    cats: dict[str, Counter[str]] = {a: Counter() for a in gbat.LEVER_ARMS}
    s_cell: dict[tuple[str, int, str], float] = {}
    for a in gbat.LEVER_ARMS:
        for r in range(r_count):
            for p in probes:
                cs = choices[(a, r, p.probe_id)]
                for c in cs:
                    cats[a][gsc.category(c, p, a)] += 1
                s_cell[(a, r, p.probe_id)] = _cell(
                    cs, lambda c, p=p, a=a: gsc.category(c, p, a)
                )
    frozen = gsc.unit_scores(gsc.arm_unit_scores(choices, r_count), r_count)
    units = gbat.units(r_count)
    per_rep = len(units) // r_count
    mine = []
    for u in units:
        a, b = gbat.FAMILIES[u.family]
        mine.append(
            float(
                np.mean(
                    [
                        (
                            s_cell[(a, u.replicate, p.probe_id)]
                            + s_cell[(b, u.replicate, p.probe_id)]
                        )
                        / 2.0
                        for p in gbat.triple_probes(u.triple)
                    ]
                )
            )
        )
    if not np.allclose(np.array(mine), frozen, rtol=0.0, atol=C_MATCH_TOL):
        msg = "G: unit values differ from the frozen scorer"
        raise InputError(msg)
    rep_units = np.array(mine).reshape(r_count, per_rep)  # units は r が外側
    items: dict[str, list[float]] = {p.probe_id: [] for p in probes}
    for r in range(r_count):
        for p in probes:
            items[p.probe_id].append(
                float(
                    np.mean(
                        [
                            (s_cell[(a, r, p.probe_id)] + s_cell[(b, r, p.probe_id)])
                            / 2.0
                            for a, b in gbat.FAMILIES
                        ]
                    )
                )
            )
    return BatteryData(
        name="G",
        rep_units=rep_units,
        items=items,
        cats=cats,
        total_calls=len(samples),
    )


def o_time_units(
    choices: Mapping[tuple[str, str, int, int], Sequence[str | None]], r_count: int
) -> tuple[np.ndarray, dict[tuple[str, str, int, int], float]]:
    """凍結の関数で (n,) の D と、セル得点を返す."""
    s = osc.cell_scores(choices, r_count)
    return osc.unit_scores(s, r_count), s


def battery_o_time(lines: Sequence[str], r_count: int) -> BatteryData:
    samples = osc.load_records(lines)
    choices: dict[tuple[str, str, int, int], list[str | None]] = {}
    for s in samples:
        choices.setdefault(
            (s.arm, s.encoding, osc.room_index(s.probe_id), s.replicate), []
        ).append(s.parsed)
    cats: dict[str, Counter[str]] = {a: Counter() for a in obat.LEVER_ARMS}
    for (arm, _, i, _), cs in choices.items():
        for c in cs:
            cats[arm][osc.category(c, arm, i)] += 1
    d, s_cell = o_time_units(choices, r_count)
    units = obat.units(r_count)
    mine = []
    for u in units:
        fwd, bwd = obat.FAMILIES[u.family]
        per_enc = []
        for enc in obat.ENCODINGS:
            arm_s = [
                _cell(
                    choices[(a, enc, u.room, u.replicate)],
                    lambda c, a=a, i=u.room: osc.category(c, a, i),
                )
                for a in (fwd, bwd)
            ]
            per_enc.append((arm_s[0] + arm_s[1]) / 2.0)
        mine.append((per_enc[0] + per_enc[1]) / 2.0)
    if not np.allclose(np.array(mine), d, rtol=0.0, atol=C_MATCH_TOL):
        msg = "O_time: unit values differ from the frozen scorer"
        raise InputError(msg)
    per_rep = len(units) // r_count
    rep_units = d.reshape(r_count, per_rep)
    items: dict[str, list[float]] = {f"room{i}": [] for i in range(obat.N_ROOMS)}
    by_room: dict[tuple[int, int], list[float]] = {}
    for u, v in zip(units, d, strict=True):
        by_room.setdefault((u.room, u.replicate), []).append(float(v))
    for i in range(obat.N_ROOMS):
        for r in range(r_count):
            items[f"room{i}"].append(float(np.mean(by_room[(i, r)])))
    desc = osc.describe(choices, s_cell, r_count)
    comps = osc.components(s_cell)
    return BatteryData(
        name="O_time",
        rep_units=rep_units,
        items=items,
        cats=cats,
        total_calls=len(samples),
        describe={
            **{k: float(v) for k, v in desc.items()},
            "components": {
                f"{dr}_{e}": float(c)
                for (dr, e), c in zip(osc.COMPONENTS, comps, strict=True)
            },
        },
    )


# ------------------------------------------------------------ pilot の null (記述のみ)


def null_g(lines: Sequence[str]) -> dict[str, float]:
    samples = gsc.load_records(lines)
    x, _ = gpg.cell_scores(samples)  # (族, つ組, R, probe, arm)
    unit = x.mean(axis=(3, 4))  # (族, つ組, R)
    m = unit.mean(axis=(0, 1))  # (R,)
    return _null_summary(m)


def null_o_time(lines: Sequence[str]) -> dict[str, float]:
    samples = osc.load_records(lines)
    x, _, _ = opg.cell_scores(samples, "masked")  # (族, 部屋, R, 書き方, arm)
    unit = x.mean(axis=(3, 4))
    m = unit.mean(axis=(0, 1))
    return _null_summary(m)


def _null_summary(m: np.ndarray) -> dict[str, float]:
    return {
        "R": int(m.size),
        "C_null": float(m.mean()),
        "sigma_rep_null": float(m.std(ddof=1)),
    }


# ------------------------------------------------------------ 規則の適用


def noise(rep_units: np.ndarray) -> dict[str, float]:
    """Replicate を cluster にした雑音の推定 (rules.md §4)."""
    m = rep_units.mean(axis=1)
    r_count = int(m.size)
    sigma = float(m.std(ddof=1))
    df = r_count - 1
    sigma_up = sigma * math.sqrt(df / chi2_ppf(1.0 - SIGMA_UP_LEVEL, df))
    return {
        "R": r_count,
        "C": float(m.mean()),
        "sigma_rep": sigma,
        "se": sigma / math.sqrt(r_count),
        "sigma_up": sigma_up,
    }


def output_classes(cats: Mapping[str, Counter[str]]) -> dict[str, Any]:
    per_arm = {}
    for arm, c in cats.items():
        n = sum(c.values())
        w, f = c["w"], c["foil"]
        per_arm[arm] = {
            **{k: c[k] / n for k in CATEGORIES},
            "n": n,
            "q": (w + f) / n,
            "r": (w / (w + f)) if w + f else None,
            "bot_rate": c["bot"] / n,
        }
    tot: Counter[str] = Counter()
    for c in cats.values():
        tot.update(c)
    n = sum(tot.values())
    return {
        "per_arm": per_arm,
        "q": (tot["w"] + tot["foil"]) / n,
        "r": (tot["w"] / (tot["w"] + tot["foil"])) if tot["w"] + tot["foil"] else None,
        "max_bot_rate": max(v["bot_rate"] for v in per_arm.values()),
    }


def r_cost(r_raw: int, multiple: int) -> int:
    """表示位置が一巡する最小の倍数に切り上げる (Codex HIGH-1)."""
    return -(-r_raw // multiple) * multiple


def cost_seconds(name: str, r: int, total_calls: int, r_count: int) -> Fraction:
    """R replicate の本走の時間 (秒、qwen3:8b 換算、正確な有理数)."""
    return r * Fraction(total_calls, r_count) * SEC_PER_CALL[name]


def r_table(
    name: str, sigma_up: float, total_calls: int, r_count: int
) -> dict[str, Any]:
    """単一 battery で差 0 の対から Δ を識別する、1 対あたりの R の概算 (rules.md §5)."""
    rows = {}
    for delta in DELTA_GRID:
        r_raw = r_needed(sigma_up, delta)
        r_c = r_cost(r_raw, R_MULTIPLE[name])
        sec = cost_seconds(name, r_c, total_calls, r_count)
        r1 = r_cost(r_needed(1.0, delta), R_MULTIPLE[name])
        sec1 = cost_seconds(name, r1, total_calls, r_count)
        rows[f"{delta:.2f}"] = {
            "R_raw": r_raw,
            "R_cost": r_c,
            "calls": float(r_c * Fraction(total_calls, r_count)),
            "seconds_exact": [sec.numerator, sec.denominator],
            "hours_8b": float(sec / 3600),
            "hours_14b_assumed": float(sec * SPEED_14B / 3600),
            "R_cost_sigma1": r1,
            "hours_8b_sigma1": float(sec1 / 3600),
        }
    return rows


def _check_inputs(name: str, row: Mapping[str, Any]) -> None:
    """判定の入力の検証。q の NaN (validity で保留) 以外の非有限値は停止 (Codex LOW-1)."""
    vals = [
        row["output_classes"]["max_bot_rate"],
        row["noise"]["C"],
        row["noise"]["se"],
    ]
    if not all(
        isinstance(v, float | int) and not isinstance(v, bool) and math.isfinite(v)
        for v in vals
    ):
        msg = f"{name}: non-finite decision input"
        raise InputError(msg)


def decide(rows: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """rules.md §6 の (a) 妥当性 → (b) 天井 → (c) 費用 を順に当てる."""
    out: dict[str, dict[str, Any]] = {}
    passing = []
    for name, row in rows.items():
        _check_inputs(name, row)
        oc = row["output_classes"]
        nz = row["noise"]
        if oc["max_bot_rate"] > BOT_HOLD or not oc["q"] >= Q_HOLD:
            out[name] = {"decision": DECISION_HOLD, "reason": "validity"}
        elif nz["C"] + Z_CEIL * nz["se"] >= CEILING:
            out[name] = {"decision": DECISION_HOLD, "reason": "ceiling"}
        else:
            passing.append(name)
    sec = {
        n: Fraction(*rows[n]["r_table"][f"{DELTA_REF:.2f}"]["seconds_exact"])
        for n in passing
    }
    cum = Fraction(0)
    for name in sorted(passing, key=lambda n: (sec[n], n)):
        if cum + sec[name] <= BUDGET_SECONDS:
            cum += sec[name]
            out[name] = {
                "decision": DECISION_ADOPT,
                "reason": "within_budget",
                "cumulative_hours_8b": float(cum / 3600),
            }
        else:
            out[name] = {
                "decision": DECISION_HOLD,
                "reason": "cost",
                "cumulative_hours_8b_if_added": float((cum + sec[name]) / 3600),
            }
    return out


def _finite(x: Any) -> bool:
    if isinstance(x, dict):
        return all(_finite(v) for v in x.values())
    if isinstance(x, list):
        return all(_finite(v) for v in x)
    if isinstance(x, float):
        return math.isfinite(x)
    return True


def replicates(n_units: object, per_rep: int) -> int:
    """n_units から R を逆算する。整数・割り切れる・R ≥ 2 でなければ停止 (Codex LOW-2)."""
    if type(n_units) is not int:
        msg = f"n_units {n_units!r} is not an int"
        raise InputError(msg)
    r, rem = divmod(n_units, per_rep)
    if rem or r < R_FLOOR:
        msg = f"n_units {n_units} is not R x {per_rep} with R >= {R_FLOOR}"
        raise InputError(msg)
    return r


def analyse(root: Path) -> dict[str, Any]:
    hashes = verify_inputs(root)
    g_r = replicates(
        _read_json(root, "g_results")["n_units"], len(gbat.FAMILIES) * gbat.N_TRIPLES
    )
    ot_r = replicates(
        _read_json(root, "ot_results")["n_units"], len(obat.FAMILIES) * obat.N_ROOMS
    )
    data = {
        "v2": battery_v2(_read_lines(root, "v2_records")),
        "v3": battery_v3(_read_lines(root, "v3_records")),
        "G": battery_g(_read_lines(root, "g_records"), g_r),
        "O_time": battery_o_time(_read_lines(root, "ot_records"), ot_r),
    }
    known = {
        "v2": _read_json(root, "v2_results")["C"],
        "v3": _read_json(root, "v3_results")["C"],
        "G": _read_json(root, "g_results")["C"],
        "O_time": _read_json(root, "ot_results")["C"],
    }
    rows: dict[str, dict[str, Any]] = {}
    for name in BATTERIES:
        bd = data[name]
        nz = noise(bd.rep_units)
        if not (math.isfinite(nz["C"]) and abs(nz["C"] - known[name]) <= C_MATCH_TOL):
            msg = f"{name}: C {nz['C']} != results.json {known[name]}"
            raise InputError(msg)
        items = {
            k: {
                "mean": float(np.mean(v)),
                "se": float(np.std(v, ddof=1) / math.sqrt(len(v))),
            }
            for k, v in bd.items.items()
        }
        rows[name] = {
            "noise": nz,
            "items": items,
            "output_classes": output_classes(bd.cats),
            "total_calls": bd.total_calls,
            "calls_per_rep": bd.total_calls / nz["R"],
            "sec_per_call_8b": float(SEC_PER_CALL[name]),
            "r_table": r_table(name, nz["sigma_up"], bd.total_calls, nz["R"]),
            "describe": bd.describe,
        }
    nulls = {
        "G": null_g(_read_lines(root, "g_pilot_records")),
        "O_time": null_o_time(_read_lines(root, "ot_pilot_records")),
    }
    out = {
        "inputs_sha256": hashes,
        "batteries": rows,
        "pilot_null": nulls,
        "decisions": decide(rows),
        "z_sum": z_sum(),
        "note": (
            "段 1 の採る / 保留は段 2 の優先順位づけで、battery を閉じる判断ではない。"
            "1 モデル (qwen3:8b) の結果で閉じない。旧 verdict を再判定しない。"
            "段 1 で見た記録は段 2 の確認データにしない。"
        ),
    }
    if not _finite({k: v for k, v in out.items() if k != "batteries"}) or not all(
        _finite(r["noise"]) and _finite(r["r_table"]) for r in rows.values()
    ):
        msg = "non-finite value in the decision inputs"
        raise InputError(msg)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        res = analyse(_REPO_ROOT)
    except InputError as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "stage1.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    for name, d in sorted(res["decisions"].items()):
        print(f"{name}: {d['decision']} ({d['reason']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
