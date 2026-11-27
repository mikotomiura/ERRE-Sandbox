"""判別性 gate 段 2 — 本走の判別性 scorer (prereg §F・§E・§B・§J・§M).

規則の SSOT は ``experiments/20261126-benchmark-stage2-discriminability/prereg.md`` (第 1 段 PILOT-FROZEN)。
判定は ``benchmark_stage2_stats`` の関数だけで行う。記録は ``benchmark_stage2_records`` (plan に頼らない読み手) で読む。
``benchmark_stage2_plan``・``benchmark_stage2_driver`` は import しない (DD-1。test で AST を検査する)。

手順:

1. **gate.json の照合** (Codex r1 H5): driver の ``read_gate`` と同じ契約を独立に書く。違反は ``GateError`` で止める
   (判定を出さない)。K・ΣM・envelope は gate の値を使い、本走で外したモデルの分を減らさない (§D・§F)。
2. **記録** ``rd.read_run(stage=main, r_by_battery=GO の R, models_by_battery=入場集合)``。
3. **fixture の照合** (§J): ``fixture_diffs_main.json`` を ``benchmark_stage2_fixtures`` で計算し直し、byte が違えば
   全 battery を INVALID (§F-1 の照合)。
4. battery ごとに §F の順: INVALID (読み手の違反がその battery の区切りか run 全体にある・全モデルが meta の違反) →
   not_computed (記録のあるモデルが無い) → モデル単位で外す (meta の違反 = INVALID、not_computed、⊥ の envelope の超過
   ``stats.envelope_exceeded``) → ``stats.decide_battery``。
5. 記述 (判定に使わない): 全対の点推定・両方向の下限・相関、モデルの C の両側区間 (α/(2ΣM))・q・r・6 分類、
   v2・v3 の ``replicate_lower_bounds``、名指した対の q/r の差・感度・fixture の併記、床の集中の成分、qwen3 の大きさの順の予測、
   §M の報告文の材料。
6. 2 回計算して byte 一致を確かめてから書く (上書きしない)。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import sys
from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING, Any, Final

import numpy as np
from scripts import benchmark_stage2_fixtures as fxm
from scripts import benchmark_stage2_records as rd
from scripts import benchmark_stage2_stats as st
from scripts import benchmark_stage2_units as un
from scripts import o_time_probe_battery as obat

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

_REPO_ROOT: Final[pathlib.Path] = pathlib.Path(__file__).resolve().parent.parent
EXP: Final[pathlib.Path] = (
    _REPO_ROOT / "experiments" / "20261126-benchmark-stage2-discriminability"
)
RESULTS: Final[pathlib.Path] = EXP / "results"
MODELS_JSON: Final[pathlib.Path] = RESULTS / "models.json"
GATE_JSON: Final[pathlib.Path] = RESULTS / "pilot" / "gate.json"
FIXTURE_JSON: Final[pathlib.Path] = RESULTS / "fixture_diffs_main.json"
VERDICT_JSON: Final[pathlib.Path] = RESULTS / "main" / "verdict.json"

SCHEMA: Final[str] = "benchmark_stage2_verdict/1"
GATE_SCHEMA: Final[str] = "benchmark_stage2_pilot_gate/1"
NOT_RUN_GATES: Final[frozenset[str]] = frozenset(
    {
        st.GATE_STOP_POWER,
        st.GATE_HELD_COST,
        st.VERDICT_NOT_QUALIFIED,
        st.VERDICT_NOT_COMPUTED,
    }
)
QWEN3_SIZE_ORDER: Final[tuple[str, ...]] = (  # §M の予測: 大きいほど C が高い
    "qwen3:1.7b",
    "qwen3:4b-q4_K_M",
    "qwen3:8b",
    "qwen3:14b",
)
EXCL_INVALID: Final[str] = "INVALID"
EXCL_NOT_COMPUTED: Final[str] = "not_computed"
EXCL_ENVELOPE: Final[str] = "bot_envelope_exceeded"
ROUND: Final[int] = 12


class GateError(ValueError):
    """gate.json の契約 (H5) の違反。判定を出さない."""


# ------------------------------------------------------------ 1. gate.json の照合 (driver と独立)


@dataclass(frozen=True)
class GateRead:
    labels: dict[str, str]
    r_go: dict[str, int]
    entrants: dict[str, tuple[str, ...]]
    envelopes: dict[tuple[str, str], Fraction]
    k_tests: int
    sum_m: int


def _int_eq(got: object, want: int) -> bool:
    return type(got) is int and got == want


def read_gate(gate: Mapping[str, Any], models_json_sha256: str) -> GateRead:
    if gate.get("schema") != GATE_SCHEMA or gate.get("status") != "OK":
        raise GateError("schema or status is not an OK pilot gate")
    inputs = gate.get("inputs")
    if (
        not isinstance(inputs, dict)
        or inputs.get("models_json_sha256") != models_json_sha256
    ):
        raise GateError("models_json_sha256 differs from the models.json in use")
    batteries = gate.get("batteries")
    if not isinstance(batteries, dict) or set(batteries) != set(st.BATTERIES):
        raise GateError("batteries differ from the registered 4")
    labels: dict[str, str] = {}
    r_sel: dict[str, int] = {}
    entrants: dict[str, tuple[str, ...]] = {}
    envelopes: dict[tuple[str, str], Fraction] = {}
    for b in st.BATTERIES:
        entry = batteries[b]
        if not isinstance(entry, dict):
            raise GateError(f"{b}: entry is not an object")
        models = entry.get("models")
        if not isinstance(models, dict):
            raise GateError(f"{b}: models is not an object")
        ent = entry.get("entrants")
        # 入場 = models の status が entered のモデル (§A.1 の順)。pilot gate の生成規則と同じ
        entered = [
            m
            for m in rd.MODELS
            if isinstance(models.get(m), dict) and models[m].get("status") == st.ENTERED
        ]
        if ent != entered or not _int_eq(entry.get("n_entered"), len(entered)):
            raise GateError(f"{b}: entrants differ from the entered models")
        entrants[b] = tuple(entered)
        label = entry.get("gate")
        r = entry.get("R")
        qualified = len(ent) >= st.MIN_ENTRANTS
        if label in (st.GATE_GO, st.GATE_HELD_COST):
            if (
                not qualified
                or type(r) is not int
                or r not in st.r_candidates(st.SPECS[b])
            ):
                raise GateError(f"{b}: R {r!r} is not a registered candidate")
            r_sel[b] = r
        elif label == st.GATE_STOP_POWER:
            if not qualified or r is not None:
                raise GateError(f"{b}: STOP_POWER needs >= 3 entrants and no R")
        elif label in (st.VERDICT_NOT_QUALIFIED, st.VERDICT_NOT_COMPUTED):
            if qualified or r is not None:
                raise GateError(f"{b}: {label} with >= 3 entrants or an R")
        else:
            raise GateError(f"{b}: unknown gate {label!r}")
        labels[b] = label
        for m in entered:
            env = models[m].get("envelope")
            if (
                not isinstance(env, dict)
                or type(env.get("numerator")) is not int
                or type(env.get("denominator")) is not int
                or env["denominator"] <= 0
            ):
                raise GateError(f"{b}/{m}: envelope is not an integer fraction")
            envelopes[(b, m)] = Fraction(env["numerator"], env["denominator"])
            # 保存の ⊥ の数は登録の arm の数の [0, bot_n] の整数で、入場モデルは parse の規則を
            # 通り (stats.qualify)、envelope はその数から復元した分数と一致する (DD-12 H1)
            counts = models[m].get("bot_counts")
            n_bot = models[m].get("bot_n")
            if not isinstance(counts, list):
                raise GateError(f"{b}/{m}: bot_counts is not a list")
            if len(counts) != st.N_ARMS[b]:
                raise GateError(f"{b}/{m}: bot_counts differ from the registered arms")
            if type(n_bot) is not int or n_bot <= 0:
                raise GateError(f"{b}/{m}: bot_n is not a positive integer")
            if not all(type(k) is int for k in counts):
                raise GateError(f"{b}/{m}: bot_counts are not integers")
            if not all(0 <= k <= n_bot for k in counts):
                raise GateError(f"{b}/{m}: bot_counts are outside [0, bot_n]")
            parse_ok, want_env = st.parse_rule(counts, n_bot)
            if not parse_ok:
                raise GateError(
                    f"{b}/{m}: entered but the bot counts fail the parse rule"
                )
            if envelopes[(b, m)] != want_env:
                raise GateError(f"{b}/{m}: envelope differs from the pilot bot counts")
    n_entered = {b: len(e) for b, e in entrants.items()}
    k_tests = st.n_tests(n_entered)
    sum_m = sum(n for n in n_entered.values() if n >= st.MIN_ENTRANTS)
    if not _int_eq(gate.get("K"), k_tests) or not _int_eq(gate.get("sum_M"), sum_m):
        raise GateError("K or sum_M differs from the entrants")
    if st.budget(r_sel) != {b: labels[b] for b in r_sel}:
        raise GateError("GO / HELD_COST differ from the budget rule")
    r_go = {b: r for b, r in r_sel.items() if labels[b] == st.GATE_GO}
    if not r_go:
        raise GateError("no GO battery")
    return GateRead(labels, r_go, entrants, envelopes, k_tests, sum_m)


# ------------------------------------------------------------ 記述の部品


def _f(x: Any) -> float:
    return round(float(x), ROUND)


def _jsonable(x: object) -> object:
    if isinstance(x, float):
        return str(x) if not math.isfinite(x) else x
    if isinstance(x, np.floating):
        return _jsonable(float(x))
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [_jsonable(v) for v in x]
    return x


def six_classes_by_encoding(
    choices: Mapping[tuple[Any, ...], str | None], r_list: Sequence[int]
) -> dict[str, dict[str, int]]:
    """O_time の 6 分類を (arm, 書き方) ごとに (§B の記述、DD-12 M4)。key = ``"<arm>|<書き方>"``.

    分類は ``units.six_classes`` と同じ (``units.category``)。O_time のセルの key は (arm, 書き方, r, probe, k)。
    本走の記録に通信の欠測の行は無い (記録の読み手が区切りごと拒む) ので ``missing`` は 0。
    """
    out: dict[str, dict[str, int]] = {}
    for cell in un.lever_cells("O_time", r_list):
        arm, enc = cell.key[0], cell.key[1]
        row = out.setdefault(f"{arm}|{enc}", dict.fromkeys(un.CLASSES, 0))
        cat = un.category("O_time", cell.key, choices[cell.key])
        row[un._CAT_TO_CLASS[cat]] += 1  # noqa: SLF001
    return out


def main_r_list(battery: str, r_count: int) -> list[int]:
    r0 = rd.MAIN_R0[battery]
    return list(range(r0, r0 + r_count))


def component_key(battery: str, key: tuple[Any, ...]) -> str:
    """§E の成分: v2・v3 = arm、G = arm・probe、O_time = 向き × 書き方."""
    if battery in ("v2", "v3"):
        return str(key[0])
    if battery == "G":
        return f"{key[0]}/{key[2]}"
    return f"{obat.direction(key[0])}/{key[1]}"


def components(
    battery: str, choices: Mapping[tuple[Any, ...], str | None], r_list: Sequence[int]
) -> dict[str, float]:
    acc: dict[str, list[int]] = {}
    for cell in un.lever_cells(battery, r_list):
        cat = un.category(battery, cell.key, choices[cell.key])
        acc.setdefault(component_key(battery, cell.key), []).append(
            1 if cat == "w" else -1 if cat == "foil" else 0
        )
    return {k: _f(np.mean(v)) for k, v in sorted(acc.items())}


def component_sign(comps: Mapping[str, float]) -> str:
    vals = list(comps.values())
    if vals and all(v < 0 for v in vals):
        return "all_negative"  # 負への集中
    if any(v < 0 for v in vals) and any(v > 0 for v in vals):
        return "mixed_signs"  # 相殺の可能性
    return "neither"


def correlation(a: np.ndarray, b: np.ndarray) -> float | None:
    if a.size < 2 or float(np.std(a)) == 0.0 or float(np.std(b)) == 0.0:
        return None
    return _f(np.corrcoef(a, b)[0, 1])


def qwen3_prediction(
    report: Sequence[str],
    model_c: Mapping[str, float],
    named: Sequence[tuple[str, str]],
) -> dict[str, Any]:
    """§M の向きの予測 (記述): qwen3 は大きいほど C が高い。族をまたぐ対は予測しない."""
    rank = {m: i for i, m in enumerate(QWEN3_SIZE_ORDER)}
    pairs = []
    for a, b in named:
        if a in rank and b in rank:
            agree = rank[a] > rank[b]
            pairs.append(
                {
                    "pair": [a, b],
                    "prediction": "一致" if agree else "逆転",
                    **(
                        {}
                        if agree
                        else {"note": "得点差は大きさと逆向き。能力の差の証拠としない"}
                    ),
                }
            )
    qs = [m for m in QWEN3_SIZE_ORDER if m in report]
    cs = [model_c[m] for m in qs]
    if len(qs) < 2:
        order = None
    elif len(set(cs)) < len(cs):
        order = "同点を含む"
    else:
        order = "一致" if cs == sorted(cs) else "不一致"
    return {"named_pairs": pairs, "qwen3_models": qs, "size_order": order}


COMMON_TEXT: Final[tuple[str, ...]] = (
    "この battery・この schedule (layout・表示順・書き方) に条件付けた。事前に固定した seed の列は decoding の乱数の標本とみなした (§D)。"
    "新しい layout・新しい項目への一般化は示さない",
    "この着座の下で",
    "母集団は共通の lookup (§A.2) で限ったものである",
)
O_TIME_TEXT: Final[str] = (
    "O_time では、lookup に同じ battery の M0 の腕を使ったので、選別された母集団の上の結果である"
)
NOT_RUN_TEXT: Final[dict[str, str]] = {
    st.GATE_STOP_POWER: "この雑音と予算の R では検定を起こせない (設計容量)。判別性について何も言わない",
    st.GATE_HELD_COST: "予算の外 (未実行)。判別性について何も言わない",
    st.VERDICT_NOT_QUALIFIED: "資格不足",
    st.VERDICT_NOT_COMPUTED: "pilot で記録が無い (not_computed)",
}
LINE_END_TEXT: Final[str] = "登録したモデル・予算で、判別性を確立できずに終了"
CONC_NAME: Final[dict[str | None, str]] = {
    "floor": "床",
    "ceiling": "天井",
    None: "なし",
}


def report_text(battery: str, out: Mapping[str, Any]) -> list[str]:
    """§M の報告文の材料 (定型の文言。判定から機械的に作る)."""
    v = out["verdict"]
    lines = list(COMMON_TEXT)
    if battery == "O_time":
        lines.append(O_TIME_TEXT)
    report = out["report_set"]
    frac = f"{len(report)} / {out['n_entered']}"
    if v == st.VERDICT_ESTABLISHED:
        names = "; ".join(f"{p['pair'][0]} > {p['pair'][1]}" for p in out["named"])
        lines.append(
            "この battery・この schedule・この着座で、≲14B の、登録した入場モデルの間に、指定した属性が定める向きの得点差が、"
            f"信頼性をもって出た (名指しした対: {names})"
        )
        lines.append(
            "両半分の点推定が Δ_min を超え、登録した集中の条件に当たらなかった (真の値についての主張ではない)"
        )
        if battery == "v3":
            lines.append(
                "v3 の (1) は得点差までに固定する (属性への反応とは言わない、§I.3)"
            )
        for p in out["named"]:
            if p["fixture_pairs"]:
                lines.append(
                    f"{p['pair'][0]} − {p['pair'][1]}: この差は、登録した方策の対 ("
                    + "; ".join(f"{q['high']} − {q['low']}" for q in p["fixture_pairs"])
                    + ") でも説明しうる"
                )
            if not p["sensitivity_ok"] or battery == "v3":
                lines.append(
                    f"{p['pair'][0]} − {p['pair'][1]}: 得点差まで (その内訳が q の差で説明されうる)"
                )
    elif v in (st.VERDICT_NEGATIVE, st.VERDICT_NEGATIVE_SUBSET):
        lines.append(
            "この battery・この schedule・この着座で、報告集合 ("
            + ", ".join(report)
            + f"、{frac}) の全対の得点差は ±0.10 の内"
        )
        lines.append(
            "正答率に換算して最大約 5 ポイント (q = 1 のとき) の差は否定しない"
        )
        if out["concentration"] == "floor":
            lines.append(
                "報告集合の各モデルの C の同時区間が登録した床の帯 [−0.10, 0.10] に入り、全対差の区間が同等域に入った"
            )
        else:
            lines.append("列挙した報告集合の全対で差が同等域の内")
        for e in out["excluded"]:
            lines.append(
                f"外したモデル {e['model']} ({e['reason']}) の対については何も言わない"
            )
    elif v == st.VERDICT_INCONCLUSIVE:
        lines.append("決着しない (「判別しない」「差が無い」とは書かない)")
    elif v == st.VERDICT_NOT_QUALIFIED:
        lines.append(f"資格不足 (報告集合 {frac})")
    elif v == st.VERDICT_NOT_COMPUTED:
        lines.append("not_computed (全モデルで記録が無い)")
    else:
        lines.append("INVALID (照合・記録・meta の違反)")
    lines.append(f"床・天井の集中: {CONC_NAME[out.get('concentration')]}")
    return lines


# ------------------------------------------------------------ 4. battery の判定


def _battery_violations(
    battery: str, run: rd.RunRead, names: Sequence[str]
) -> list[str]:
    all_names = list(run.segments)
    out = []
    for v in run.violations:
        own = [n for n in all_names if v.startswith(n + ": ")]
        if not own or any(n in names for n in own):
            out.append(v)
    return out


def score_battery(
    battery: str,
    run: rd.RunRead,
    gate: GateRead,
    fixture: Mapping[str, Any] | None,
    invalid_reasons: Sequence[str],
) -> dict[str, Any]:
    spec = st.SPECS[battery]
    r_list = main_r_list(battery, gate.r_go[battery])
    entrants = gate.entrants[battery]
    names = [rd.seg_name(rd.STAGE_MAIN, battery, m) for m in entrants]
    viol = list(invalid_reasons) + _battery_violations(battery, run, names)
    if any(n not in run.segments for n in names):
        viol.append("segments missing for this battery")
    base: dict[str, Any] = {
        "R": len(r_list),
        "r_list": [r_list[0], r_list[-1] + 1],
        "n_entered": len(entrants),
        "entrants": list(entrants),
        "K": gate.k_tests,
        "sum_M": gate.sum_m,
    }
    n_units = len(r_list) * spec.units_per_rep
    halves = st.half_labels(spec, r_list)
    if viol:
        dec = st.decide_battery(
            np.empty((0, n_units)),
            gate.k_tests,
            gate.sum_m,
            halves,
            invalid=True,
            n_entered=len(entrants),
        )
        out = {
            **base,
            "verdict": dec.verdict,
            "violations": sorted(set(viol)),
            "report_set": [],
            "excluded": [],
            "named": [],
            "concentration": None,
        }
        out["report_text"] = report_text(battery, out)
        return out
    excluded: list[dict[str, Any]] = []
    report: list[str] = []
    units, counts, choices_by = [], [], {}
    models_out: dict[str, Any] = {}
    statuses = []
    for m, name in zip(entrants, names, strict=True):
        sr = run.segments[name]
        statuses.append(sr.status)
        if sr.status in (rd.R_INVALID_META, rd.R_INVALID_VERSION):
            excluded.append(
                {
                    "model": m,
                    "reason": EXCL_INVALID,
                    "detail": f"{sr.status}: {sr.reason}",
                }
            )
            continue
        if sr.status != rd.R_OK:
            excluded.append(
                {
                    "model": m,
                    "reason": EXCL_NOT_COMPUTED,
                    "detail": str(sr.reason or sr.status),
                }
            )
            continue
        choices = rd.unit_choices(battery, sr.rows)
        bots, n_arm = un.bot_counts(battery, choices, r_list)
        env = gate.envelopes[(battery, m)]
        models_out[m] = {
            "bot_counts": list(bots),
            "bot_n": n_arm,
            "envelope": {"numerator": env.numerator, "denominator": env.denominator},
            "six_classes": un.six_classes(battery, choices, r_list),
        }
        if battery == "O_time":
            models_out[m]["six_classes_by_encoding"] = six_classes_by_encoding(
                choices, r_list
            )
        if st.envelope_exceeded(bots, n_arm, env):
            excluded.append(
                {
                    "model": m,
                    "reason": EXCL_ENVELOPE,
                    "detail": f"max {max(bots)}/{n_arm} > {env}",
                }
            )
            continue
        c = un.unit_counts(battery, choices, r_list)
        report.append(m)
        counts.append(c)
        units.append(un.unit_values(c))
        choices_by[m] = choices
    all_invalid = all(s in (rd.R_INVALID_META, rd.R_INVALID_VERSION) for s in statuses)
    no_records = all(s != rd.R_OK for s in statuses)
    u_arr = np.stack(units) if units else np.empty((0, n_units))
    c_arr = np.stack(counts) if counts else np.empty((0, n_units, 3), dtype=int)
    dec = st.decide_battery(
        u_arr,
        gate.k_tests,
        gate.sum_m,
        halves,
        cell_counts=c_arr,
        invalid=all_invalid,
        not_computed=no_records and not all_invalid,
        n_entered=len(entrants),
    )
    out = {
        **base,
        "verdict": dec.verdict,
        "violations": [],
        "report_set": report,
        "n_excluded": len(entrants) - len(report),
        "excluded": excluded,
        "concentration": dec.concentration,
        "models": models_out,
        "named": [],
    }
    if dec.verdict in (st.VERDICT_INVALID, st.VERDICT_NOT_COMPUTED):
        out["report_text"] = report_text(battery, out)
        return out
    level_c = st.ALPHA / (2 * gate.sum_m)
    model_c = {}
    qr = {}
    for i, m in enumerate(report):
        q, r = un.q_and_r(c_arr[i])
        qr[m] = (q, r)
        model_c[m] = _f(u_arr[i].mean())
        models_out[m].update(
            {
                "C": model_c[m],
                "C_interval": [
                    _f(st.lower_bound(u_arr[i], -1.0, 1.0, level_c)),
                    _f(st.upper_bound(u_arr[i], -1.0, 1.0, level_c)),
                ],
                "q": _f(q),
                "r": None if r is None else _f(r),
            }
        )
    level = st.ALPHA / gate.k_tests  # 判定と同じ片側の水準 (記述は報告集合の全対)
    pair_rows = []
    for a in range(len(report)):
        for b in range(a + 1, len(report)):
            d = u_arr[a] - u_arr[b]
            pair_rows.append(
                {
                    "pair": [report[a], report[b]],
                    "estimate": _f(d.mean()),
                    "lower_bound_a_minus_b": _f(st.lower_bound(d, -2.0, 2.0, level)),
                    "lower_bound_b_minus_a": _f(st.lower_bound(-d, -2.0, 2.0, level)),
                    "n_units": int(d.size),
                    "correlation": correlation(u_arr[a], u_arr[b]),
                    "halves": [_f(d[halves == h].mean()) for h in (0, 1)],
                }
            )
    out["pairs"] = pair_rows
    if battery in ("v2", "v3") and len(report) >= 2:
        rep = st.replicate_lower_bounds(u_arr, spec.units_per_rep, gate.k_tests)
        out["replicate_lower_bounds"] = {
            f"{report[int(k.split('-')[0])]} - {report[int(k.split('-')[1])]}": _f(v)
            for k, v in rep.items()
        }
    fx_pairs = list((fixture or {}).get("nuisance_pairs_over_delta_min", []))
    sens = set(dec.sensitivity_ok)
    named: list[dict[str, Any]] = []
    named_pairs: list[tuple[str, str]] = []
    for a, b in dec.established:
        named_pairs.append((report[a], report[b]))
        ra, rb = qr[report[a]][1], qr[report[b]][1]
        named.append(
            {
                "pair": [report[a], report[b]],
                "lower_bound": _f(
                    st.lower_bound(u_arr[a] - u_arr[b], -2.0, 2.0, level)
                ),
                "q_diff": _f(qr[report[a]][0] - qr[report[b]][0]),
                "r_diff": None if ra is None or rb is None else _f(ra - rb),
                "sensitivity_ok": (a, b) in sens,
                "fixture_pairs": fx_pairs,
            }
        )
    out["named"] = named
    if dec.concentration == "floor":
        out["floor_components"] = {
            m: {
                "components": (comps := components(battery, choices_by[m], r_list)),
                "q": _f(qr[m][0]),
                "sign": component_sign(comps),
            }
            for m in report
        }
    out["qwen3_prediction"] = qwen3_prediction(report, model_c, named_pairs)
    out["report_text"] = report_text(battery, out)
    return out


# ------------------------------------------------------------ 全体


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_verdict(
    run_dir: pathlib.Path,
    gate_path: pathlib.Path,
    models_json: pathlib.Path,
    fixture_path: pathlib.Path,
) -> dict[str, Any]:
    reference, ref_sha = rd.load_reference(models_json)
    gate_bytes = gate_path.read_bytes()
    gate = read_gate(json.loads(gate_bytes.decode("utf-8")), ref_sha)
    run = rd.read_run(
        run_dir,
        rd.STAGE_MAIN,
        reference,
        r_by_battery=gate.r_go,
        models_by_battery={b: gate.entrants[b] for b in gate.r_go},
    )
    global_invalid: list[str] = []
    fixture: dict[str, Any] = {}
    try:
        fx_bytes = fixture_path.read_bytes()
    except OSError:
        fx_bytes = None
        global_invalid.append("fixture_diffs_main.json is missing")
    if fx_bytes is not None:
        if fxm.compute_text(gate_path).encode("utf-8") != fx_bytes:
            global_invalid.append(
                "fixture_diffs_main.json differs from the recomputation"
            )
        else:
            fixture = json.loads(fx_bytes.decode("utf-8"))["batteries"]
    batteries: dict[str, Any] = {}
    for b in st.BATTERIES:
        if b in gate.r_go:
            batteries[b] = score_battery(b, run, gate, fixture.get(b), global_invalid)
        else:
            label = gate.labels[b]
            batteries[b] = {
                "verdict": None,
                "pilot_gate": label,
                "report_text": [NOT_RUN_TEXT[label]],
            }
    established = [
        b for b, e in batteries.items() if e.get("verdict") == st.VERDICT_ESTABLISHED
    ]
    inputs = {
        "models_json_sha256": ref_sha,
        "gate_json_sha256": _sha(gate_bytes),
        "fixture_diffs_main_sha256": None if fx_bytes is None else _sha(fx_bytes),
        **run.inputs,
    }
    return _jsonable(  # type: ignore[return-value]
        {
            "schema": SCHEMA,
            "K": gate.k_tests,
            "sum_M": gate.sum_m,
            "alpha": st.ALPHA,
            "delta_min": st.DELTA_MIN,
            "batteries": batteries,
            "established_batteries": established,
            "line_end": None if established else LINE_END_TEXT,
            "record_violations": list(run.violations),
            "inputs": inputs,
        }
    )


def verdict_text(obj: Mapping[str, Any]) -> str:
    return (
        json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False)
        + "\n"
    )


class NotDeterministicError(RuntimeError):
    """2 回の計算の byte が違う."""


def compute_twice(
    run_dir: pathlib.Path,
    gate_path: pathlib.Path,
    models_json: pathlib.Path,
    fixture_path: pathlib.Path,
) -> str:
    texts = [
        verdict_text(compute_verdict(run_dir, gate_path, models_json, fixture_path))
        for _ in range(2)
    ]
    if texts[0] != texts[1]:
        msg = "two computations differ"
        raise NotDeterministicError(msg)
    return texts[0]


def run_scorer(
    run_dir: pathlib.Path,
    out: pathlib.Path,
    *,
    gate_path: pathlib.Path = GATE_JSON,
    models_json: pathlib.Path = MODELS_JSON,
    fixture_path: pathlib.Path = FIXTURE_JSON,
) -> str:
    body = compute_twice(run_dir, gate_path, models_json, fixture_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:  # 排他的作成 (存在の確認と書き込みの間に別のプロセスが書く競合を残さない、DD-12 L1)
        with out.open("xb") as fh:
            fh.write(body.encode("utf-8"))
    except FileExistsError as exc:
        msg = f"refusing to overwrite {out}"
        raise FileExistsError(msg) from exc
    return body


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", type=pathlib.Path, default=RESULTS)
    ap.add_argument("--out", type=pathlib.Path, default=VERDICT_JSON)
    ap.add_argument("--gate", type=pathlib.Path, default=GATE_JSON)
    ap.add_argument("--models-json", type=pathlib.Path, default=MODELS_JSON)
    ap.add_argument("--fixtures", type=pathlib.Path, default=FIXTURE_JSON)
    ap.add_argument(
        "--check", action="store_true", help="計算し直して --out と byte 比較"
    )
    args = ap.parse_args(argv)
    try:
        if args.check:
            body = compute_twice(
                args.run_dir, args.gate, args.models_json, args.fixtures
            )
            same = args.out.read_bytes() == body.encode("utf-8")
            print("[scorer] " + ("MATCH" if same else "DIFFERS"))  # noqa: T201
            return 0 if same else 3
        body = run_scorer(
            args.run_dir,
            args.out,
            gate_path=args.gate,
            models_json=args.models_json,
            fixture_path=args.fixtures,
        )
    except GateError as exc:
        print(f"[scorer] refused: gate.json: {exc}", file=sys.stderr)  # noqa: T201
        return 2
    obj = json.loads(body)
    print(  # noqa: T201
        "[scorer] "
        + ", ".join(
            f"{b}={e.get('verdict') or e.get('pilot_gate')}"
            for b, e in obj["batteries"].items()
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
