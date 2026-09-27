"""閉ループ分散 pilot — 記録・schedule 監査・連鎖 replay・推定量・判定 rule・claim (prereg v4).

事前登録 = ``experiments/20260927-closed-loop-divergence-pilot/prereg.md``。凍結 v2 scorer
(``scripts/skill_lever_scorer.py``) からは **純粋関数だけ** を import する (parse・messages sha・要求条件・
成分・族単位・⊥ 率・⊥ gate・3 分岐・符号反転)。v2 の ``evaluate`` / ``structure_violations`` /
``simulate`` は v2 の grid と battery に結び付くので使わない。

推定量 (ADR §1、v2 と同じ式): 世界 a・replicate r の成分 s_{a,r} = (#t_a − #t_{a'}) / (6K)、単位
d_{r,f} = (s_{a,r} + s_{a',r}) / 2、C_loop = mean d (2R 単位)。C_loop は held-out probe 上の族内
エージェント間の選択分布 TV に対する、向きの付いた下界 (期待値の意味で)。

判定 (評価順、prereg v4 §5): INVALID_SCORER → (計算しない) → INVALID_TASK_BATTERY → PASS →
NO_GO_EFFECT_ABSENT → INCONCLUSIVE_UNDERPOWERED。coverage は gate にしない (ADR D8)。計算は CPU のみ。
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import numpy as np
from scripts import closed_loop_battery as bat
from scripts import skill_lever_battery as v2bat
from scripts.skill_lever_scorer import (
    BOT_MAX,
    DELTA_PLANT,
    POWER_TARGET,
    STATUS_COMPUTED,
    STATUS_NOT_COMPUTED,
    TAU,
    bottom_gate_ok,
    bottom_rates,
    component_scores,
    decide,
    family_units,
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

from erre_sandbox.evidence.es2_replay.divergence import tv_distance

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
    "VERDICT_ABSENT",
    "VERDICT_INVALID_BATTERY",
    "VERDICT_INVALID_SCORER",
    "VERDICT_PASS",
    "VERDICT_UNDERPOWERED",
    "parse_choice",
    "request_meta",
]

# ---- 凍結値 (prereg v4 §4 / §6。power 表の選定と一致することを manifest が検査する)
FROZEN_RENDERER: Final[str] = bat.RENDERER_R1PLUS
FROZEN_R: Final[int] = 8
FROZEN_K: Final[int] = 5
FROZEN_M: Final[int] = 4
LOOP_BOT_MAX: Final[float] = BOT_MAX  # ループ段の世界別 ⊥ 率の上限 (ADR §3.3)
# fixture 表で (mean + 3SE) ≥ τ/4 だった weather を読まない方策 (user 裁定 DU-3)。
# fixture 表の flagged と一致することを manifest が検査する。PASS の文に必ず入る。
FLAGGED_FIXTURES: Final[tuple[str, ...]] = ("F1_most_label",)
FLAGGED_NOTE: Final[str] = (
    "weather を読まず状態内で最多の label を選ぶ読み方 (fixture F1) でも、"
    "実測 base・C = 0.6 の模擬で約 0.08 の正の寄与が生じうる (τ/4 超、user 裁定 DU-3)。"
)
COVERAGE_BRANCH: Final[float] = (
    2.0 / 3.0
)  # NO_GO の claim 分岐 (探索の不足か lookup の不足か)

CLAIM_PASS: Final[str] = "pass_within_discovered_rows"
CLAIM_NO_GO_EXPLORATION: Final[str] = "no_go_exploration_limited"
CLAIM_NO_GO_LOOKUP: Final[str] = "no_go_lookup_limited"

# ---------------------------------------------------------------- records


@dataclass(frozen=True)
class Record:
    """1 回の呼び出し。raw = None は transport 失敗 (再送 3 回後も失敗、⊥ ではない).

    phase ∈ {c0, loop, probe, replay}。loop は step を持ち probe_id / k は null。c0 / probe は
    probe_id / k を持ち step は null。replay は再送した元の呼び出しの key をそのまま持つ。
    成否は記録しない (scorer が連鎖 replay で導出する)。
    """

    call_index: int
    phase: str
    world: str
    replicate: int
    step: int | None
    probe_id: str | None
    k: int | None
    seed: int
    prompt_sha256: str
    raw: str | None
    parsed: str | None

    def key(self) -> bat.PlanKey:
        return bat.PlanKey(
            self.phase, self.world, self.replicate, self.step, self.probe_id, self.k
        )


class RecordError(ValueError):
    """記録の schema 違反。INVALID_SCORER に落とす."""


_FIELDS: Final[frozenset[str]] = frozenset(Record.__dataclass_fields__)
_INT: Final[tuple[str, ...]] = ("call_index", "replicate", "seed")
_STR: Final[tuple[str, ...]] = ("phase", "world", "prompt_sha256")
_OPT_STR: Final[tuple[str, ...]] = ("raw", "parsed")
_PHASES: Final[frozenset[str]] = frozenset(
    {bat.PHASE_C0, bat.PHASE_LOOP, bat.PHASE_PROBE, bat.PHASE_REPLAY}
)


def _is_int(x: object) -> bool:
    return type(x) is int


def record_from_json(obj: object) -> Record:
    """厳密に読む: 欄の過不足・型違い (coercion しない)・phase と欄の組み合わせ違反は RecordError."""
    if not isinstance(obj, dict) or set(obj) != _FIELDS:
        msg = f"record fields must be exactly {sorted(_FIELDS)}"
        raise RecordError(msg)
    for f in _INT:
        if not _is_int(obj[f]):
            msg = f"{f} must be int"
            raise RecordError(msg)
    for f in _STR:
        if type(obj[f]) is not str:
            msg = f"{f} must be str"
            raise RecordError(msg)
    for f in _OPT_STR:
        if obj[f] is not None and type(obj[f]) is not str:
            msg = f"{f} must be str or null"
            raise RecordError(msg)
    if obj["phase"] not in _PHASES:
        msg = f"unknown phase {obj['phase']!r}"
        raise RecordError(msg)
    loop_shape = _is_int(obj["step"]) and obj["probe_id"] is None and obj["k"] is None
    probe_shape = (
        obj["step"] is None and type(obj["probe_id"]) is str and _is_int(obj["k"])
    )
    ok = {
        bat.PHASE_LOOP: loop_shape,
        bat.PHASE_C0: probe_shape,
        bat.PHASE_PROBE: probe_shape,
        bat.PHASE_REPLAY: loop_shape or probe_shape,
    }[obj["phase"]]
    if not ok:
        msg = f"fields do not match phase {obj['phase']!r}"
        raise RecordError(msg)
    return Record(**{f: obj[f] for f in _FIELDS})


def load_records(lines: Sequence[str]) -> list[Record]:
    out = []
    for n, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError as exc:
            msg = f"line {n}: not JSON"
            raise RecordError(msg) from exc
        out.append(record_from_json(obj))
    return out


# ------------------------------------------------------------- expected


def frozen_plan() -> list[bat.PlanKey]:
    return bat.plan(FROZEN_R, FROZEN_K, FROZEN_M)


def n_main() -> int:
    return bat.n_main_calls(FROZEN_R, FROZEN_K, FROZEN_M)


def n_c0() -> int:
    return FROZEN_R * len(v2bat.lever_probes()) * FROZEN_K


def _qidx(probe_id: str) -> int:
    return {p.probe_id: i for i, p in enumerate(v2bat.lever_probes())}[probe_id]


def expected_seed(key: bat.PlanKey) -> int:
    if key.step is not None:
        return bat.loop_seed(key.replicate, key.step)
    assert key.probe_id is not None and key.k is not None
    return v2bat.sample_seed(key.replicate, _qidx(key.probe_id), key.k)


def schedule_violations(records: Sequence[Record]) -> list[str]:
    """記録が凍結 plan の接頭辞であること (ファイルの行順 = call_index = plan の位置、key・seed の一致).

    欠け (接頭辞だが短い) は違反ではない (計算しない側で扱う)。transport 失敗 (raw = null) の後に
    記録が続くことも違反 (driver は transport 失敗で止まる、prereg v4 §4)。
    """
    out: list[str] = []
    full = frozen_plan()
    if [x.call_index for x in records] != list(range(len(records))):
        return [
            "records are not 0..n-1 in file order (not a prefix of the frozen plan)"
        ]
    ordered = list(records)
    if len(ordered) > len(full):
        return ["more records than the frozen plan"]
    for rec in ordered:
        want = full[rec.call_index]
        got = rec.key()
        if (got.phase, got.world, got.replicate, got.step, got.probe_id, got.k) != (
            want.phase,
            want.world,
            want.replicate,
            want.step,
            want.probe_id,
            want.k,
        ):
            out.append(f"call {rec.call_index}: key differs from the frozen plan")
            continue
        if rec.seed != expected_seed(want):
            out.append(
                f"call {rec.call_index}: seed {rec.seed} != {expected_seed(want)}"
            )
    failed = [x.call_index for x in ordered if x.raw is None]
    if failed and failed[0] != ordered[-1].call_index:
        out.append("records continue after a transport failure")
    return out


def parse_violations(records: Sequence[Record]) -> list[str]:
    out = []
    for rec in records:
        want = None if rec.raw is None else parse_choice(rec.raw)
        if rec.parsed != want:
            out.append(f"call {rec.call_index}: recorded parse differs from re-parse")
    return out


def replay_states(
    records: Sequence[Record], renderer: str = FROZEN_RENDERER
) -> tuple[dict[tuple[str, int], bat.State], list[str]]:
    """連鎖 replay (ADR §3.3)。記録した行動・世界の規則・renderer から全ループ段の prompt を再構成し、
    記録の sha256 と照合する。返り値 = 完了したループの終状態と、不一致の説明.
    """
    out: list[str] = []
    loops: dict[tuple[str, int], list[Record]] = defaultdict(list)
    for rec in records:
        if rec.phase == bat.PHASE_LOOP:
            loops[(rec.world, rec.replicate)].append(rec)
    final: dict[tuple[str, int], bat.State] = {}
    for (world, r), recs in sorted(loops.items()):
        state = bat.EMPTY_STATE
        for n, rec in enumerate(sorted(recs, key=lambda x: x.call_index)):
            if rec.step != n:
                out.append(f"{world} r={r}: loop steps are not 0..n-1")
                break
            msgs = bat.loop_messages(state, world, r, n, renderer)
            if rec.prompt_sha256 != messages_sha256(msgs):
                out.append(f"{world} r={r} t={n}: prompt differs from the chain replay")
                break
            state = bat.update(state, world, bat.loop_signature(r, n), rec.parsed)
        else:
            if len(recs) == bat.n_steps(FROZEN_M):
                final[(world, r)] = state
    return final, out


def chain_violations(
    records: Sequence[Record], renderer: str = FROZEN_RENDERER
) -> list[str]:
    """連鎖 replay + probe (終状態から) + C0 + replay (元の呼び出しと同じ prompt) の sha 照合."""
    final, out = replay_states(records, renderer)
    by_key = {r.key(): r for r in records if r.phase != bat.PHASE_REPLAY}
    for rec in records:
        if rec.phase == bat.PHASE_C0:
            assert rec.probe_id is not None
            want = messages_sha256(bat.c0_messages(rec.replicate, _qidx(rec.probe_id)))
            if rec.prompt_sha256 != want:
                out.append(f"call {rec.call_index}: C0 prompt differs")
        elif rec.phase == bat.PHASE_PROBE:
            state = final.get((rec.world, rec.replicate))
            if state is None:
                out.append(f"call {rec.call_index}: probe before its loop completed")
                continue
            assert rec.probe_id is not None
            msgs = bat.probe_messages(
                state, rec.world, rec.replicate, _qidx(rec.probe_id), renderer
            )
            if rec.prompt_sha256 != messages_sha256(msgs):
                out.append(
                    f"call {rec.call_index}: probe prompt differs from the chain"
                )
        elif rec.phase == bat.PHASE_REPLAY:
            k = rec.key()
            target = by_key.get(
                bat.PlanKey(
                    bat.PHASE_LOOP if k.step is not None else bat.PHASE_PROBE,
                    k.world,
                    k.replicate,
                    k.step,
                    k.probe_id,
                    k.k,
                )
            )
            if target is None or target.prompt_sha256 != rec.prompt_sha256:
                out.append(f"call {rec.call_index}: replay prompt differs from target")
    return out


# ------------------------------------------------------------- estimand


def probe_choices(
    records: Sequence[Record],
) -> dict[tuple[str, int, str], list[str | None]]:
    """(world, r, probe_id) → k 順の parse 結果 (C0 は world = 'C0')."""
    out: dict[tuple[str, int, str], list[str | None]] = {}
    for rec in sorted(records, key=lambda x: x.k or 0):
        if rec.phase in (bat.PHASE_PROBE, bat.PHASE_C0):
            assert rec.probe_id is not None
            out.setdefault((rec.world, rec.replicate, rec.probe_id), []).append(
                rec.parsed
            )
    return out


def loop_bottom_rates(records: Sequence[Record]) -> dict[str, float]:
    out = {}
    for w in bat.WORLDS:
        cs = [x.parsed for x in records if x.phase == bat.PHASE_LOOP and x.world == w]
        out[w] = sum(c is None for c in cs) / len(cs)
    return out


def coverage(final: Mapping[tuple[str, int], bat.State]) -> dict[str, Any]:
    """終点の coverage (記述と claim 分岐のみ、gate にしない — ADR D8)."""
    n_w = len({s[0] for s in bat.dev_signatures()})
    weathers = {
        key: len({s[0] for s in st.succeeded}) for key, st in sorted(final.items())
    }
    sigs = {key: len(st.succeeded) for key, st in sorted(final.items())}
    vals = list(weathers.values())
    return {
        "weather_coverage": float(np.mean(vals)) / n_w,
        "discovered_weathers": int(sum(vals)),
        "possible_weathers": n_w * len(vals),
        "all_weathers_rate": float(np.mean([v == n_w for v in vals])),
        "signature_coverage": float(np.mean(list(sigs.values()))) / bat.N_DEV,
        "by_world": {
            w: float(np.mean([v for (ww, _), v in weathers.items() if ww == w])) / n_w
            for w in bat.WORLDS
        },
    }


def claim_branch(verdict: str | None, cov: Mapping[str, Any] | None) -> str | None:
    if verdict == VERDICT_PASS:
        return CLAIM_PASS
    if verdict == VERDICT_ABSENT:
        assert cov is not None
        if cov["weather_coverage"] < COVERAGE_BRANCH:
            return CLAIM_NO_GO_EXPLORATION
        return CLAIM_NO_GO_LOOKUP
    return None


def pass_claim_text(c: float, cov: Mapping[str, Any]) -> str:
    """PASS の文 (ADR §5)。終点の coverage と発見した weather の数を必ず含む."""
    return (
        f"1 つの凍結 qwen3:8b (think=False) の上で、合成した 18 状況の決定的な成否規則だけが違う世界で、"
        f"各自の行動と結果から aggregator が prompt に置く状態を育てたエージェントは、held-out 状況で"
        f"自分の経験の向きに違う選択をした (C_loop = {c:.3f} > τ = {TAU})。"
        f"C_loop は held-out probe 上の族内エージェント間の選択分布 TV に対する、向きの付いた下界である。"
        f"終点の weather coverage = {cov['weather_coverage']:.3f} "
        f"(発見した weather = {cov['discovered_weathers']} / {cov['possible_weathers']}、"
        f"全 weather を発見した率 = {cov['all_weathers_rate']:.3f}、"
        f"signature coverage = {cov['signature_coverage']:.3f})。"
        f"言えるのは、発見済みの成功行を aggregator が prompt にした範囲で held-out の選択が動いた、まで。"
        f"{FLAGGED_NOTE if FLAGGED_FIXTURES else ''}"
    )


# ------------------------------------------------------------ describe


def _dist(cs: Sequence[str | None]) -> np.ndarray:
    labels = [*bat.ACTIONS, None]
    return np.array([sum(c == x for c in cs) for x in labels], dtype=float)


def describe(
    records: Sequence[Record], final: Mapping[tuple[str, int], bat.State]
) -> dict[str, Any]:
    """記述報告 (判定に使わない、prereg v4 §10)."""
    ch = probe_choices(records)
    probes = v2bat.lever_probes()
    fam_tv, half_tv = [], []
    for a, b in bat.FAMILIES:
        for r in range(FROZEN_R):
            for p in probes:
                fam_tv.append(
                    tv_distance(
                        _dist(ch[(a, r, p.probe_id)]), _dist(ch[(b, r, p.probe_id)])
                    )
                )
    for w in bat.WORLDS:
        for r in range(FROZEN_R):
            for p in probes:
                cs = ch[(w, r, p.probe_id)]
                h = len(cs) // 2
                half_tv.append(tv_distance(_dist(cs[:h]), _dist(cs[h : 2 * h])))
    strata: dict[str, list[float]] = defaultdict(list)
    for w in bat.WORLDS:
        for r in range(FROZEN_R):
            st = final[(w, r)]
            for p in probes:
                n = sum(s[0] == p.signature[0] for s in st.succeeded)
                name = "0" if n == 0 else "1" if n == 1 else "2-3" if n < 4 else "4"
                cs = ch[(w, r, p.probe_id)]
                own = sum(c == p.pointed[w] for c in cs)
                foil = sum(c == p.pointed[v2bat.FOIL[w]] for c in cs)
                strata[name].append((own - foil) / len(cs))
    c0 = [x for x in records if x.phase == bat.PHASE_C0]
    return {
        "family_tv_mean": float(np.mean(fam_tv)),
        "split_half_tv_mean": float(np.mean(half_tv)),
        "lambda_strata": {
            k: {"cells": len(v), "mean_w_minus_foil": float(np.mean(v))}
            for k, v in sorted(strata.items())
        },
        "c0_label_rates": {
            lab: sum(x.parsed == lab for x in c0) / len(c0) for lab in bat.ACTIONS
        },
        "loop_bottom_rates": loop_bottom_rates(records),
        "determinism": determinism(records),
    }


def determinism(records: Sequence[Record]) -> dict[str, Any]:
    """決定性 (記述、prereg v4 §7): (i) run 内で prompt と seed が同一の群の raw 一致率、
    (iii) 登録 replay の raw 一致率。どれかが 1.0 未満なら「厳密」を「期待値で 0」に格下げする.
    """
    groups: dict[tuple[str, int], list[str | None]] = defaultdict(list)
    for rec in records:
        if rec.phase != bat.PHASE_REPLAY:
            groups[(rec.prompt_sha256, rec.seed)].append(rec.raw)
    multi = [g for g in groups.values() if len(g) > 1]
    in_run = float(np.mean([len(set(g)) == 1 for g in multi])) if multi else None
    by_key = {r.key(): r for r in records if r.phase != bat.PHASE_REPLAY}
    rep = []
    for rec in records:
        if rec.phase == bat.PHASE_REPLAY:
            k = rec.key()
            phase = bat.PHASE_LOOP if k.step is not None else bat.PHASE_PROBE
            target = by_key.get(
                bat.PlanKey(phase, k.world, k.replicate, k.step, k.probe_id, k.k)
            )
            if target is not None:
                rep.append(target.raw == rec.raw)
    replay = float(np.mean(rep)) if rep else None
    rates = [x for x in (in_run, replay) if x is not None]
    return {
        "in_run_groups": len(multi),
        "in_run_identical_rate": in_run,
        "replay_n": len(rep),
        "replay_identical_rate": replay,
        "exact_cancellation": bool(rates) and all(x == 1.0 for x in rates),
    }


# ------------------------------------------------------------ certification


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def certified_targets() -> dict[str, Path]:
    root = Path(__file__).resolve().parent
    names = (
        "closed_loop_scorer.py",
        "closed_loop_battery.py",
        "closed_loop_sim.py",
        "skill_lever_scorer.py",
        "skill_lever_battery.py",
        "stage_b_scorer.py",
        "stage_b_battery.py",
    )
    return {n: root / n for n in names}


def load_certification(path: Path) -> bool:
    """変異 harness の記録。全 KILLED ∧ 記録 sha256 が現在の 7 ファイルと一致。読めない = 不合格."""
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
    records: Sequence[Record], meta: Mapping[str, Any], certification: Path
) -> dict[str, Any]:
    """Prereg v4 §5 の評価順で verdict を返し、coverage・claim 分岐・記述を添える."""
    report: dict[str, Any] = {
        "status": STATUS_COMPUTED,
        "verdict": None,
        "reasons": [],
        "claim_branch": None,
        "claim_text": None,
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
    schedule = schedule_violations(records)
    report["schedule_violations"] = schedule
    if schedule:
        return done(VERDICT_INVALID_SCORER, "schedule")
    parse = parse_violations(records)
    report["parse_violations"] = parse
    if parse:
        return done(VERDICT_INVALID_SCORER, "parse")
    chain = chain_violations(records)
    report["chain_violations"] = chain
    if chain:
        return done(VERDICT_INVALID_SCORER, "chain_replay")

    # ---- 計算できない (⊥ に畳まない)
    if any(x.raw is None for x in records):
        return done(None, "transport_failure")
    if len(records) < n_c0():
        return done(None, "c0_incomplete")

    # ---- 2. INVALID_TASK_BATTERY (C0 は状態側の前に実走する)
    ch = probe_choices(records)
    c0_bot = float(bottom_rates(ch, (bat.ARM_C0,), FROZEN_R)[0])
    report["c0_bottom_rate"] = c0_bot
    if c0_bot > BOT_MAX:
        return done(VERDICT_INVALID_BATTERY, "c0_bottom_rate")
    if len(records) < n_main():
        return done(None, "main_incomplete")
    loop_bot = loop_bottom_rates(records)
    report["loop_bottom_rates"] = loop_bot
    if max(loop_bot.values()) > LOOP_BOT_MAX:
        return done(VERDICT_INVALID_BATTERY, "loop_bottom_rate")
    bot = bottom_rates(ch, bat.WORLDS, FROZEN_R)
    report["probe_bottom_rates"] = dict(zip(bat.WORLDS, bot.tolist(), strict=True))
    if not bool(bottom_gate_ok(bot)):
        return done(VERDICT_INVALID_BATTERY, "probe_bottom_gate")

    # ---- 3〜5.
    final, _ = replay_states(records)
    s = component_scores(ch, FROZEN_R)
    d = family_units(s)
    comps = s.mean(axis=1)
    p_zero, p_lower, p_upper = tests_exact(d)
    cov = coverage(final)
    c = float(d.mean())
    report.update(
        C=c,
        components=dict(zip(bat.WORLDS, comps.tolist(), strict=True)),
        units=d.tolist(),
        p_zero=p_zero,
        p_lower=p_lower,
        p_upper=p_upper,
        coverage=cov,
        describe=describe(records, final),
    )
    verdict = str(decide(np.float64(p_lower), np.float64(p_upper), comps))
    report["claim_branch"] = claim_branch(verdict, cov)
    if verdict == VERDICT_PASS:
        report["claim_text"] = pass_claim_text(c, cov)
    return done(verdict, "decided")


def evaluate_records(
    lines: Sequence[str], meta_text: str, certification: Path
) -> dict[str, Any]:
    """JSONL の行と meta の JSON テキストから。読めない・schema 違反は INVALID_SCORER."""
    try:
        records = load_records(lines)
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
    return evaluate(records, meta, certification)
