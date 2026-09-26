"""判定 rule (prereg v2 §5): 各 verdict 枝に到達する合成 fixture と、推定量・構造検査.

DB-1 (到達不能な判定枝) の再発防止として、5 語すべてと not_computed に、そこへ到達する
fixture を置く。fixture は実モデル出力でなく、方針 (arm・r・probe・k → 生テキスト)
から作る。
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import replace
from typing import TYPE_CHECKING

import numpy as np
import pytest
from scripts import skill_lever_battery as bat
from scripts import skill_lever_scorer as sc
from scripts.stage_b_scorer import (
    VERDICT_ABSENT,
    VERDICT_INVALID_BATTERY,
    VERDICT_INVALID_SCORER,
    VERDICT_PASS,
    VERDICT_UNDERPOWERED,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def build(
    policy: Callable[[str, int, bat.LeverProbe, int], str | None],
) -> list[sc.Sample]:
    """C0 を先に全て、次に lever 4 arm (prereg v2 §4 の呼び出し順).

    call_index は通し番号。
    """
    out = []
    for arm in (bat.ARM_C0, *bat.LEVER_ARMS):
        for r in range(sc.FROZEN_R):
            for qi, p in enumerate(bat.lever_probes()):
                for k in range(sc.FROZEN_K):
                    seed, sha = sc.expected_sample(arm, r, qi, k)
                    raw = policy(arm, r, p, k)
                    parsed = None if raw is None else sc.parse_choice(raw)
                    out.append(
                        sc.Sample(
                            len(out), arm, r, p.probe_id, k, seed, sha, raw, parsed
                        )
                    )
    return out


def to_lines(samples: list[sc.Sample]) -> list[str]:
    return [json.dumps(dataclasses.asdict(s), ensure_ascii=False) for s in samples]


@pytest.fixture
def cert(tmp_path: Path) -> Path:
    path = tmp_path / "cert.json"
    shas = {
        name: hashlib.sha256(p.read_bytes()).hexdigest()
        for name, p in sc.certified_targets().items()
    }
    path.write_text(
        json.dumps({"target_sha256": shas, "all_killed": True}), encoding="utf-8"
    )
    return path


def run(samples: list[sc.Sample], cert: Path) -> dict[str, object]:
    return sc.evaluate(samples, sc.request_meta(), cert)


# ---- 方針 (arm, r, probe, k → 生テキスト)


def lookup(arm: str, r: int, p: bat.LeverProbe, _k: int) -> str:
    """規則どおり (C0 は Ω_q 先頭)."""
    if arm == bat.ARM_C0:
        return bat.layout(r).option_order[p.probe_id][0]
    return p.pointed[arm]


def fraction(frac_w: float) -> Callable[[str, int, bat.LeverProbe, int], str]:
    """各 (arm, r, probe) の K sample のうち frac_w を w、残りを other に (分散 0)."""

    def policy(arm: str, _r: int, p: bat.LeverProbe, k: int) -> str:
        if arm == bat.ARM_C0:
            return p.omega[0]
        if k < round(frac_w * sc.FROZEN_K):
            return p.pointed[arm]
        others = [
            o for o in p.omega if o not in (p.pointed[arm], p.pointed[bat.FOIL[arm]])
        ]
        return others[k % len(others)]

    return policy


def priming_only(arm: str, r: int, p: bat.LeverProbe, k: int) -> str:
    """状態に出た label を一様に選ぶだけ (weather との対応を読まない)."""
    if arm == bat.ARM_C0:
        return p.omega[k % 4]
    labels = sorted({x for _, x in bat.state_entries(arm, bat.layout(r))})
    return labels[k % len(labels)]


def uniform_null(_arm: str, r: int, p: bat.LeverProbe, k: int) -> str:
    return bat.layout(r).option_order[p.probe_id][(k + r) % 4]


# ---- 各 verdict 枝への到達


def test_lookup_is_pass(cert: Path) -> None:
    rep = run(build(lookup), cert)
    assert rep["verdict"] == VERDICT_PASS
    assert rep["C"] == pytest.approx(1.0)


def test_priming_only_is_not_pass(cert: Path) -> None:
    """label priming だけのモデルは C = 0 → NO_GO.

    旧型の A vs B 対比では正に出る (交絡の実証)。
    """
    samples = build(priming_only)
    rep = run(samples, cert)
    assert rep["C"] == pytest.approx(0.0, abs=1e-12)
    assert rep["verdict"] == VERDICT_ABSENT
    a_rows = [s for s in samples if s.arm == bat.ARM_A]
    probes = {p.probe_id: p for p in bat.lever_probes()}
    g_a = np.mean([s.parsed == probes[s.probe_id].pointed[bat.ARM_A] for s in a_rows])
    g_b = np.mean([s.parsed == probes[s.probe_id].pointed[bat.ARM_B] for s in a_rows])
    assert g_a - g_b > 0.3


def test_uniform_null_is_no_go(cert: Path) -> None:
    rep = run(build(uniform_null), cert)
    assert rep["verdict"] == VERDICT_ABSENT


def test_small_effect_is_no_go(cert: Path) -> None:
    """C = 0.2 (> 0 は有意だが τ 未満) → PASS でなく NO_GO."""
    rep = run(build(fraction(0.2)), cert)
    assert rep["C"] == pytest.approx(0.2)
    assert rep["p_zero"] < 0.05
    assert rep["verdict"] == VERDICT_ABSENT


def test_effect_at_threshold_is_inconclusive(cert: Path) -> None:
    rep = run(build(fraction(0.3)), cert)
    assert rep["C"] == pytest.approx(0.3)
    assert rep["verdict"] == VERDICT_UNDERPOWERED


def test_effect_above_threshold_is_pass(cert: Path) -> None:
    rep = run(build(fraction(0.4)), cert)
    assert rep["verdict"] == VERDICT_PASS


def test_one_arm_failure_is_not_pass(cert: Path) -> None:
    """B_rot だけ規則を読まない (成分 0) → C は τ を大きく超えても PASS にしない."""

    def policy(arm: str, r: int, p: bat.LeverProbe, k: int) -> str:
        if arm == bat.ARM_B_ROT:
            return fraction(0.0)(arm, r, p, k)
        return lookup(arm, r, p, k)

    rep = run(build(policy), cert)
    assert rep["C"] > sc.TAU
    assert rep["components"][bat.ARM_B_ROT] == pytest.approx(0.0)
    assert rep["verdict"] == VERDICT_UNDERPOWERED


def test_noisy_effect_straddling_threshold_is_inconclusive(cert: Path) -> None:
    """replicate によって規則を読んだり読まなかったりする → 区間が τ をまたぐ.

    d は 0.9 と −0.3 に割れる (平均 0.3)。
    """

    def policy(arm: str, r: int, p: bat.LeverProbe, k: int) -> str:
        if arm == bat.ARM_C0:
            return p.omega[0]
        if r % 2 == 0:
            return fraction(0.9)(arm, r, p, k)
        if k < 3:
            return p.pointed[bat.FOIL[arm]]
        return fraction(0.0)(arm, r, p, k)

    rep = run(build(policy), cert)
    assert rep["verdict"] == VERDICT_UNDERPOWERED
    assert rep["p_upper"] >= 0.05
    assert rep["p_lower"] >= 0.05


def test_c0_bottom_rate_is_invalid_battery(cert: Path) -> None:
    def policy(arm: str, r: int, p: bat.LeverProbe, k: int) -> str:
        if arm == bat.ARM_C0 and k < 3:
            return "わかりません"
        return lookup(arm, r, p, k)

    rep = run(build(policy), cert)
    assert rep["verdict"] == VERDICT_INVALID_BATTERY
    assert rep["reasons"] == ["c0_bottom_rate"]


def test_c0_gate_precedes_missing_lever_rows(cert: Path) -> None:
    """C0 が落ちたら lever run は走らない (行が無くても INVALID_TASK_BATTERY)."""
    samples = [s for s in build(lambda *_: "?") if s.arm == bat.ARM_C0]
    rep = run(samples, cert)
    assert rep["verdict"] == VERDICT_INVALID_BATTERY


def test_lever_bottom_rate_is_invalid_battery(cert: Path) -> None:
    def policy(arm: str, r: int, p: bat.LeverProbe, k: int) -> str:
        if arm in (bat.ARM_A, bat.ARM_A_ROT) and k < 3:
            return ""
        return lookup(arm, r, p, k)

    rep = run(build(policy), cert)
    assert rep["verdict"] == VERDICT_INVALID_BATTERY
    assert rep["reasons"] == ["lever_bottom_gate"]


def test_family_bottom_gap_is_invalid_battery(cert: Path) -> None:
    """族内の ⊥ 率差 0.1 ≥ τ/4 (各 arm は ≤ 0.2 でも)."""

    def policy(arm: str, r: int, p: bat.LeverProbe, k: int) -> str:
        if arm == bat.ARM_A and k < 1:
            return ""
        return lookup(arm, r, p, k)

    rep = run(build(policy), cert)
    assert rep["lever_bottom_rates"][bat.ARM_A] == pytest.approx(0.1)
    assert rep["verdict"] == VERDICT_INVALID_BATTERY


def test_bottom_counts_in_denominator() -> None:
    """⊥ は分母に含め、w にも foil にも数えない."""
    probes = bat.lever_probes()
    choices = {}
    for arm in bat.LEVER_ARMS:
        for p in probes:
            ws = [p.pointed[arm]] * 5 + [None] * 5
            choices[(arm, 0, p.probe_id)] = ws
    s = sc.component_scores(choices, 1)
    assert np.allclose(s, 0.5)


def test_family_units_pair_within_family() -> None:
    s = np.array([[0.2, 0.4], [0.6, 0.0], [1.0, -1.0], [0.0, 0.5]])
    d = sc.family_units(s)
    assert np.allclose(d, [0.4, 0.2, 0.5, -0.25])


def test_foil_label_swap_flips_unit_sign() -> None:
    """族内で arm を入れ替えると d の符号が反転する (符号反転検定の前提)."""

    def swapped(arm: str, r: int, p: bat.LeverProbe, k: int) -> str:
        partner = {bat.ARM_A: bat.ARM_A_ROT, bat.ARM_A_ROT: bat.ARM_A}.get(arm, arm)
        return fraction(0.4)(partner, r, p, k)

    base = build(fraction(0.4))
    swap = build(swapped)
    for samples, sign in ((base, 1.0), (swap, -1.0)):
        choices: dict[tuple[str, int, str], list[str | None]] = {}
        for s in samples:
            choices.setdefault((s.arm, s.replicate, s.probe_id), []).append(s.parsed)
        d = sc.family_units(sc.component_scores(choices, sc.FROZEN_R))
        assert np.allclose(d[: sc.FROZEN_R], sign * 0.4)


# ---- INVALID_SCORER


def test_missing_certification_is_invalid_scorer(tmp_path: Path) -> None:
    rep = run(build(lookup), tmp_path / "absent.json")
    assert rep["verdict"] == VERDICT_INVALID_SCORER


def test_stale_certification_is_invalid_scorer(cert: Path) -> None:
    obj = json.loads(cert.read_text(encoding="utf-8"))
    obj["target_sha256"]["skill_lever_scorer.py"] = "0" * 64
    cert.write_text(json.dumps(obj), encoding="utf-8")
    rep = run(build(lookup), cert)
    assert rep["verdict"] == VERDICT_INVALID_SCORER


def test_uncertified_harness_is_invalid_scorer(cert: Path) -> None:
    obj = json.loads(cert.read_text(encoding="utf-8"))
    obj["all_killed"] = False
    cert.write_text(json.dumps(obj), encoding="utf-8")
    assert run(build(lookup), cert)["verdict"] == VERDICT_INVALID_SCORER


def test_request_meta_mismatch_is_invalid_scorer(cert: Path) -> None:
    meta = {**sc.request_meta(), "temperature": 1.0}
    rep = sc.evaluate(build(lookup), meta, cert)
    assert rep["verdict"] == VERDICT_INVALID_SCORER


def test_duplicate_sample_is_invalid_scorer(cert: Path) -> None:
    samples = build(lookup)
    # call_index は別にして、key (arm, r, probe, k) だけが重複する行
    rep = run([*samples, replace(samples[-1], call_index=len(samples))], cert)
    assert rep["verdict"] == VERDICT_INVALID_SCORER


def test_unexpected_replicate_is_invalid_scorer(cert: Path) -> None:
    """凍結 R を超える replicate を足した run は INVALID_SCORER.

    seed・prompt は正しい行でも拒む (optional stopping の封鎖)。
    """
    samples = build(lookup)
    p = bat.lever_probes()[0]
    seed, sha = sc.expected_sample(bat.ARM_A, sc.FROZEN_R, 0, 0)
    extra = sc.Sample(
        len(samples),
        bat.ARM_A,
        sc.FROZEN_R,
        p.probe_id,
        0,
        seed,
        sha,
        "read_book",
        "read_book",
    )
    assert run([*samples, extra], cert)["verdict"] == VERDICT_INVALID_SCORER


def test_wrong_seed_is_invalid_scorer(cert: Path) -> None:
    samples = build(lookup)
    samples[5] = replace(samples[5], seed=samples[5].seed + 1)
    assert run(samples, cert)["verdict"] == VERDICT_INVALID_SCORER


def test_unfrozen_prompt_is_invalid_scorer(cert: Path) -> None:
    samples = build(lookup)
    samples[7] = replace(samples[7], prompt_sha256="f" * 64)
    assert run(samples, cert)["verdict"] == VERDICT_INVALID_SCORER


def test_recorded_parse_mismatch_is_invalid_scorer(cert: Path) -> None:
    samples = build(lookup)
    samples[9] = replace(samples[9], parsed="rest_eyes")
    assert run(samples, cert)["verdict"] == VERDICT_INVALID_SCORER


# ---- not_computed (「実行できなかった」を verdict に畳まない)


def test_transport_failure_is_not_computed(cert: Path) -> None:
    samples = build(lookup)
    samples[3] = replace(samples[3], raw=None, parsed=None)
    rep = run(samples, cert)
    assert rep["status"] == sc.STATUS_NOT_COMPUTED
    assert rep["verdict"] is None


def test_missing_lever_rows_is_not_computed(cert: Path) -> None:
    samples = [
        s for s in build(lookup) if not (s.arm == bat.ARM_B and s.replicate == 0)
    ]
    rep = run(samples, cert)
    assert rep["status"] == sc.STATUS_NOT_COMPUTED


def test_missing_c0_rows_is_not_computed(cert: Path) -> None:
    samples = [s for s in build(lookup) if s.arm != bat.ARM_C0]
    rep = run(samples, cert)
    assert rep["status"] == sc.STATUS_NOT_COMPUTED


def test_all_verdict_words_are_reachable(cert: Path) -> None:
    """5 語すべてに fixture で到達する (DB-1 型の到達不能枝が無い)."""
    reached = {
        run(build(pol), cert)["verdict"]
        for pol in (lookup, uniform_null, fraction(0.3))
    }
    reached.add(run(build(lookup), cert.parent / "absent.json")["verdict"])
    reached.add(run(build(lambda *_: "?"), cert)["verdict"])
    assert reached == {
        VERDICT_PASS,
        VERDICT_ABSENT,
        VERDICT_UNDERPOWERED,
        VERDICT_INVALID_SCORER,
        VERDICT_INVALID_BATTERY,
    }


def test_frozen_values() -> None:
    assert pytest.approx(0.30) == sc.TAU
    assert pytest.approx(2 * sc.TAU) == sc.DELTA_PLANT
    assert pytest.approx(sc.TAU / 4) == sc.BOT_FAMILY_GAP
    assert sc.FROZEN_R % bat.N_POSITIONS == 0
    assert sc.FROZEN_R <= 12
    assert sc.FROZEN_K <= 20


# ---- Codex review (MEDIUM-1 / 3 / 4) の反映


def test_lever_before_c0_is_invalid_scorer(cert: Path) -> None:
    """lever の呼び出しが C0 の終わりより前にある run は INVALID_SCORER.

    C0 先行の監査。
    """
    samples = build(lookup)
    first_lever = next(i for i, s in enumerate(samples) if s.arm != bat.ARM_C0)
    last_c0 = first_lever - 1
    a, b = samples[last_c0], samples[first_lever]
    samples[last_c0] = replace(a, call_index=b.call_index)
    samples[first_lever] = replace(b, call_index=a.call_index)
    rep = run(samples, cert)
    assert rep["verdict"] == VERDICT_INVALID_SCORER
    assert (
        "a lever call precedes the end of the C0 phase" in rep["structure_violations"]
    )


def test_duplicate_call_index_is_invalid_scorer(cert: Path) -> None:
    samples = build(lookup)
    samples[1] = replace(samples[1], call_index=samples[0].call_index)
    rep = run(samples, cert)
    assert rep["verdict"] == VERDICT_INVALID_SCORER
    assert "call_index is not unique and non-negative" in rep["structure_violations"]


def test_records_roundtrip_matches_evaluate(cert: Path) -> None:
    samples = build(lookup)
    meta = json.dumps(sc.request_meta())
    assert sc.evaluate_records(to_lines(samples), meta, cert)["verdict"] == VERDICT_PASS


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda _o: "{not json",
        lambda o: json.dumps({k: v for k, v in o.items() if k != "seed"}),
        lambda o: json.dumps({**o, "extra": 1}),
        lambda o: json.dumps({**o, "k": True}),
        lambda o: json.dumps({**o, "replicate": 1.0}),
        lambda o: json.dumps({**o, "raw": 123}),
        lambda o: json.dumps({**o, "parsed": ["read_book"]}),
        lambda o: json.dumps({**o, "arm": None}),
        lambda o: json.dumps([o]),
    ],
)
def test_malformed_record_is_invalid_scorer(cert: Path, corrupt: Callable) -> None:
    """読めない・欄の過不足・型違いの記録は例外で落ちず INVALID_SCORER.

    型の coercion をしない。
    """
    samples = build(lookup)
    lines = to_lines(samples)
    lines[4] = corrupt(dataclasses.asdict(samples[4]))
    rep = sc.evaluate_records(lines, json.dumps(sc.request_meta()), cert)
    assert rep["verdict"] == VERDICT_INVALID_SCORER
    assert rep["reasons"] == ["record_schema"]


@pytest.mark.parametrize("meta_text", ["[]", "not json", "null"])
def test_malformed_meta_is_invalid_scorer(cert: Path, meta_text: str) -> None:
    rep = sc.evaluate_records(to_lines(build(lookup)), meta_text, cert)
    assert rep["verdict"] == VERDICT_INVALID_SCORER


def test_recency_only_is_not_pass(cert: Path) -> None:
    """状態の最後のエントリの label を選ぶだけ (recency) のモデルは C = 0 → NO_GO.

    最後のエントリの weather と probe の weather の関係は weather の均衡 (各 2 probe) で
    打ち消し合う。登録した nuisance class の 1 つ。
    """

    def policy(arm: str, r: int, p: bat.LeverProbe, k: int) -> str:
        if arm == bat.ARM_C0:
            return p.omega[k % 4]
        return bat.state_entries(arm, bat.layout(r))[-1][1]

    rep = run(build(policy), cert)
    assert rep["C"] == pytest.approx(0.0, abs=1e-12)
    assert rep["verdict"] == VERDICT_ABSENT


def test_position_only_is_not_pass(cert: Path) -> None:
    """表示位置だけで選ぶ (常に先頭) モデルは C = 0 → NO_GO."""

    def policy(_arm: str, r: int, p: bat.LeverProbe, _k: int) -> str:
        return bat.layout(r).option_order[p.probe_id][0]

    rep = run(build(policy), cert)
    assert rep["C"] == pytest.approx(0.0, abs=1e-12)
    assert rep["verdict"] == VERDICT_ABSENT
