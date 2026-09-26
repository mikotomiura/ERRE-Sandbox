"""判定 rule (prereg v3 §5): 各 verdict 枝・対照の claim 分岐・構造検査に到達する合成
fixture.

fixture は実モデル出力でなく、方針 (arm・r・probe・k → 生テキスト) から作る。登録
nuisance 方策
(prereg v3 §2.5、scoping DE-9) は ``test_nuisance.py``。
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import replace
from typing import TYPE_CHECKING

import numpy as np
import pytest
from scripts import skill_experience_battery as bat
from scripts import skill_experience_scorer as sc
from scripts import skill_lever_battery as v2
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
    policy: Callable[[str, int, v2.LeverProbe, int], str | None],
) -> list[sc.Sample]:
    """凍結した呼び出し順 (prereg v3 §2.4): C0 を全て → block ごとに状態 8 arm
    を巡回順で."""
    blocks = [
        (r, qi, k)
        for r in range(sc.FROZEN_R)
        for qi in range(len(v2.lever_probes()))
        for k in range(sc.FROZEN_K)
    ]
    keys = [(bat.ARM_C0, r, qi, k) for r, qi, k in blocks]
    keys += [
        (arm, r, qi, k)
        for b, (r, qi, k) in enumerate(blocks)
        for arm in sc.block_arm_order(b)
    ]
    out = []
    for arm, r, qi, k in keys:
        p = v2.lever_probes()[qi]
        seed, sha = sc.expected_sample(arm, r, qi, k)
        raw = policy(arm, r, p, k)
        parsed = None if raw is None else sc.parse_choice(raw)
        out.append(sc.Sample(len(out), arm, r, p.probe_id, k, seed, sha, raw, parsed))
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


# ---- 方針


def first_option(_arm: str, r: int, p: v2.LeverProbe, _k: int) -> str:
    return v2.layout(r).option_order[p.probe_id][0]


def lookup(arm: str, r: int, p: v2.LeverProbe, k: int) -> str:
    """成否の集計が示す規則どおり (C0 は Ω_q 先頭)."""
    if arm == bat.ARM_C0:
        return first_option(arm, r, p, k)
    return p.pointed[bat.POINTS_AS[arm]]


def _cell(p: v2.LeverProbe, k: int) -> int:
    """(probe, k) の通し番号 0..6K−1 (K によらず割合を正確に作るため)."""
    return [q.probe_id for q in v2.lever_probes()].index(p.probe_id) * sc.FROZEN_K + k


def _n_cells() -> int:
    return len(v2.lever_probes()) * sc.FROZEN_K


def fraction(frac_w: float) -> Callable[[str, int, v2.LeverProbe, int], str]:
    """各 (arm, r) の 6K sample のうち frac_w を w、残りを other に (分散 0)."""

    def policy(arm: str, _r: int, p: v2.LeverProbe, k: int) -> str:
        if arm == bat.ARM_C0:
            return p.omega[0]
        a = bat.POINTS_AS[arm]
        if _cell(p, k) < round(frac_w * _n_cells()):
            return p.pointed[a]
        others = [o for o in p.omega if o not in (p.pointed[a], p.pointed[v2.FOIL[a]])]
        return others[k % len(others)]

    return policy


def uniform_null(_arm: str, r: int, p: v2.LeverProbe, k: int) -> str:
    return v2.layout(r).option_order[p.probe_id][(k + r) % 4]


def split(
    judge: Callable[[str, int, v2.LeverProbe, int], str | None],
    control: Callable[[str, int, v2.LeverProbe, int], str | None],
) -> Callable[[str, int, v2.LeverProbe, int], str | None]:
    def policy(arm: str, r: int, p: v2.LeverProbe, k: int) -> str | None:
        return (control if arm in bat.CONTROL_ARMS else judge)(arm, r, p, k)

    return policy


# ---- 各 verdict 枝への到達


def test_lookup_is_pass(cert: Path) -> None:
    rep = run(build(lookup), cert)
    assert rep["verdict"] == VERDICT_PASS
    assert rep["C"] == pytest.approx(1.0)
    assert rep["claim_branch"] == sc.CLAIM_PASS
    assert rep["control"]["verdict"] == VERDICT_PASS


def test_uniform_null_is_no_go(cert: Path) -> None:
    rep = run(build(uniform_null), cert)
    assert rep["verdict"] == VERDICT_ABSENT


def test_small_effect_is_no_go(cert: Path) -> None:
    rep = run(build(fraction(0.2)), cert)
    assert rep["C"] == pytest.approx(0.2)
    assert rep["p_zero"] < 0.05
    assert rep["verdict"] == VERDICT_ABSENT


def test_effect_at_threshold_is_inconclusive(cert: Path) -> None:
    rep = run(build(fraction(0.3)), cert)
    assert rep["C"] == pytest.approx(0.3)
    assert rep["verdict"] == VERDICT_UNDERPOWERED
    assert rep["claim_branch"] is None


def test_effect_above_threshold_is_pass(cert: Path) -> None:
    rep = run(build(fraction(0.4)), cert)
    assert rep["verdict"] == VERDICT_PASS


def test_one_arm_failure_is_not_pass(cert: Path) -> None:
    def policy(arm: str, r: int, p: v2.LeverProbe, k: int) -> str:
        if arm == bat.ARM_B_ROT:
            return fraction(0.0)(arm, r, p, k)
        return lookup(arm, r, p, k)

    rep = run(build(policy), cert)
    assert rep["C"] > sc.TAU
    assert rep["components"][bat.ARM_B_ROT] == pytest.approx(0.0)
    assert rep["verdict"] == VERDICT_UNDERPOWERED


def test_noisy_effect_straddling_threshold_is_inconclusive(cert: Path) -> None:
    def policy(arm: str, r: int, p: v2.LeverProbe, k: int) -> str:
        if arm == bat.ARM_C0:
            return p.omega[0]
        if r % 2 == 0:
            return fraction(0.9)(arm, r, p, k)
        if k < 3:
            return p.pointed[v2.FOIL[bat.POINTS_AS[arm]]]
        return fraction(0.0)(arm, r, p, k)

    rep = run(build(policy), cert)
    assert rep["verdict"] == VERDICT_UNDERPOWERED
    assert rep["p_upper"] >= 0.05
    assert rep["p_lower"] >= 0.05


def test_c0_bottom_rate_is_invalid_battery(cert: Path) -> None:
    def policy(arm: str, r: int, p: v2.LeverProbe, k: int) -> str:
        if arm == bat.ARM_C0 and k < 3:
            return "わかりません"
        return lookup(arm, r, p, k)

    rep = run(build(policy), cert)
    assert rep["verdict"] == VERDICT_INVALID_BATTERY
    assert rep["reasons"] == ["c0_bottom_rate"]


def test_c0_gate_precedes_missing_state_rows(cert: Path) -> None:
    samples = [s for s in build(lambda *_: "?") if s.arm == bat.ARM_C0]
    rep = run(samples, cert)
    assert rep["verdict"] == VERDICT_INVALID_BATTERY


def test_lever_bottom_rate_is_invalid_battery(cert: Path) -> None:
    def policy(arm: str, r: int, p: v2.LeverProbe, k: int) -> str:
        if arm in (bat.ARM_A, bat.ARM_A_ROT) and k < 3:
            return ""
        return lookup(arm, r, p, k)

    rep = run(build(policy), cert)
    assert rep["verdict"] == VERDICT_INVALID_BATTERY
    assert rep["reasons"] == ["lever_bottom_gate"]


def test_family_bottom_gap_is_invalid_battery(cert: Path) -> None:
    def policy(arm: str, r: int, p: v2.LeverProbe, k: int) -> str:
        if arm == bat.ARM_A and _cell(p, k) < round(0.1 * _n_cells()):
            return ""
        return lookup(arm, r, p, k)

    rep = run(build(policy), cert)
    assert rep["lever_bottom_rates"][bat.ARM_A] == pytest.approx(0.1)
    assert rep["verdict"] == VERDICT_INVALID_BATTERY


def test_bottom_counts_in_denominator() -> None:
    choices = {}
    for arm in bat.JUDGE_ARMS:
        for p in v2.lever_probes():
            choices[(arm, 0, p.probe_id)] = [p.pointed[arm]] * 5 + [None] * 5
    s = sc.component_scores(choices, bat.JUDGE_ARMS, 1)
    assert np.allclose(s, 0.5)


def test_control_component_uses_judge_pointing() -> None:
    """対照 arm は対応する判定 arm の w / foil で数える."""
    choices = {}
    for arm in bat.CONTROL_ARMS:
        for p in v2.lever_probes():
            j = bat.POINTS_AS[arm]
            choices[(arm, 0, p.probe_id)] = [p.pointed[j]] * 6 + [
                p.pointed[v2.FOIL[j]]
            ] * 4
    s = sc.component_scores(choices, bat.CONTROL_ARMS, 1)
    assert np.allclose(s, 0.2)


# ---- 対照と claim 分岐 (prereg v3 §9)


def test_no_go_with_control_pass_is_attributed(cert: Path) -> None:
    """判定は NO_GO・対照は PASS → 長さ・形式では説明されない側の claim."""
    rep = run(build(split(uniform_null, lookup)), cert)
    assert rep["verdict"] == VERDICT_ABSENT
    assert rep["control"]["verdict"] == VERDICT_PASS
    assert rep["claim_branch"] == sc.CLAIM_NO_GO_CONTROL_PASS


def test_no_go_with_control_no_go_stays_narrow(cert: Path) -> None:
    rep = run(build(uniform_null), cert)
    assert rep["control"]["verdict"] == VERDICT_ABSENT
    assert rep["claim_branch"] == sc.CLAIM_NO_GO_NARROW


def test_control_does_not_change_the_verdict(cert: Path) -> None:
    """対照の結果は判定 verdict・C を変えない (判定 5 語に混ぜない)."""
    base = run(build(split(lookup, uniform_null)), cert)
    other = run(build(lookup), cert)
    assert base["verdict"] == other["verdict"] == VERDICT_PASS
    assert base["C"] == other["C"]
    assert base["control"]["verdict"] == VERDICT_ABSENT


def test_control_bottom_gate_only_affects_control(cert: Path) -> None:
    def policy(arm: str, r: int, p: v2.LeverProbe, k: int) -> str:
        if arm in bat.CONTROL_ARMS and k < 3:
            return ""
        return uniform_null(arm, r, p, k)

    rep = run(build(policy), cert)
    assert rep["verdict"] == VERDICT_ABSENT
    assert rep["control"]["verdict"] == VERDICT_INVALID_BATTERY
    assert rep["claim_branch"] == sc.CLAIM_NO_GO_NARROW


def test_missing_control_rows_leave_the_verdict(cert: Path) -> None:
    samples = [
        s for s in build(split(uniform_null, lookup)) if s.arm not in bat.CONTROL_ARMS
    ]
    rep = run(samples, cert)
    assert rep["verdict"] == VERDICT_ABSENT
    assert rep["control"]["status"] == sc.STATUS_NOT_COMPUTED
    assert rep["claim_branch"] == sc.CLAIM_NO_GO_NARROW


def test_claim_branch_table() -> None:
    assert sc.claim_branch(VERDICT_PASS, None) == sc.CLAIM_PASS
    assert sc.claim_branch(VERDICT_ABSENT, VERDICT_PASS) == sc.CLAIM_NO_GO_CONTROL_PASS
    for c in (VERDICT_ABSENT, VERDICT_UNDERPOWERED, VERDICT_INVALID_BATTERY, None):
        assert sc.claim_branch(VERDICT_ABSENT, c) == sc.CLAIM_NO_GO_NARROW
    for v in (VERDICT_UNDERPOWERED, VERDICT_INVALID_BATTERY, VERDICT_INVALID_SCORER):
        assert sc.claim_branch(v, VERDICT_PASS) is None


# ---- INVALID_SCORER


def test_missing_certification_is_invalid_scorer(tmp_path: Path) -> None:
    rep = run(build(lookup), tmp_path / "absent.json")
    assert rep["verdict"] == VERDICT_INVALID_SCORER


def test_stale_certification_is_invalid_scorer(cert: Path) -> None:
    obj = json.loads(cert.read_text(encoding="utf-8"))
    obj["target_sha256"]["skill_experience_scorer.py"] = "0" * 64
    cert.write_text(json.dumps(obj), encoding="utf-8")
    assert run(build(lookup), cert)["verdict"] == VERDICT_INVALID_SCORER


@pytest.mark.parametrize(
    "name",
    [
        "skill_experience_scorer.py",
        "skill_experience_battery.py",
        "skill_lever_scorer.py",
        "skill_lever_battery.py",
        "stage_b_scorer.py",
        "stage_b_battery.py",
    ],
)
def test_certification_must_cover_all_six_files(cert: Path, name: str) -> None:
    """certification は v3 の 2 本と、import する v2 / 旧資産 4 本の sha256
    を全て含まなければならない."""
    assert name in sc.certified_targets()
    obj = json.loads(cert.read_text(encoding="utf-8"))
    del obj["target_sha256"][name]
    cert.write_text(json.dumps(obj), encoding="utf-8")
    assert run(build(lookup), cert)["verdict"] == VERDICT_INVALID_SCORER


def test_uncertified_harness_is_invalid_scorer(cert: Path) -> None:
    obj = json.loads(cert.read_text(encoding="utf-8"))
    obj["all_killed"] = False
    cert.write_text(json.dumps(obj), encoding="utf-8")
    assert run(build(lookup), cert)["verdict"] == VERDICT_INVALID_SCORER


def test_battery_violation_is_invalid_scorer(
    cert: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bat, "check_family_identity", lambda _r: ["broken"])
    rep = run(build(lookup), cert)
    assert rep["verdict"] == VERDICT_INVALID_SCORER
    assert rep["reasons"] == ["battery_checks"]


def test_request_meta_mismatch_is_invalid_scorer(cert: Path) -> None:
    meta = {**sc.request_meta(), "temperature": 1.0}
    assert sc.evaluate(build(lookup), meta, cert)["verdict"] == VERDICT_INVALID_SCORER


def test_duplicate_sample_is_invalid_scorer(cert: Path) -> None:
    samples = build(lookup)
    rep = run([*samples, replace(samples[-1], call_index=len(samples))], cert)
    assert rep["verdict"] == VERDICT_INVALID_SCORER


def test_unexpected_replicate_is_invalid_scorer(cert: Path) -> None:
    samples = build(lookup)
    p = v2.lever_probes()[0]
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


def test_v2_prompt_is_invalid_scorer(cert: Path) -> None:
    """v2 の lever renderer で描いた prompt (失敗行なし) は v3 の凍結 renderer
    と一致しない."""
    samples = build(lookup)
    i = next(i for i, s in enumerate(samples) if s.arm == bat.ARM_A)
    s = samples[i]
    qi = [p.probe_id for p in v2.lever_probes()].index(s.probe_id)
    v2_msgs = v2.render_messages(
        bat.ARM_A, v2.lever_probes()[qi], v2.layout(s.replicate)
    )
    samples[i] = replace(s, prompt_sha256=sc.messages_sha256(v2_msgs))
    assert run(samples, cert)["verdict"] == VERDICT_INVALID_SCORER


def test_recorded_parse_mismatch_is_invalid_scorer(cert: Path) -> None:
    samples = build(lookup)
    samples[9] = replace(samples[9], parsed="rest_eyes")
    assert run(samples, cert)["verdict"] == VERDICT_INVALID_SCORER


def test_state_call_before_c0_is_invalid_scorer(cert: Path) -> None:
    samples = build(lookup)
    first = next(i for i, s in enumerate(samples) if s.arm != bat.ARM_C0)
    a, b = samples[first - 1], samples[first]
    samples[first - 1] = replace(a, call_index=b.call_index)
    samples[first] = replace(b, call_index=a.call_index)
    rep = run(samples, cert)
    assert rep["verdict"] == VERDICT_INVALID_SCORER
    assert (
        "a state-arm call precedes the end of the C0 phase"
        in rep["structure_violations"]
    )


def test_out_of_order_state_calls_are_invalid_scorer(cert: Path) -> None:
    """C0 の後の呼び出し順が凍結順 (block 順) と違う run は INVALID_SCORER."""
    samples = build(lookup)
    i = next(
        i for i, s in enumerate(samples) if s.arm == bat.ARM_A and s.replicate == 0
    )
    j = next(
        i for i, s in enumerate(samples) if s.arm == bat.ARM_A and s.replicate == 1
    )
    a, b = samples[i], samples[j]
    samples[i] = replace(a, call_index=b.call_index)
    samples[j] = replace(b, call_index=a.call_index)
    rep = run(samples, cert)
    assert rep["verdict"] == VERDICT_INVALID_SCORER
    assert rep["structure_violations"] == ["call order differs from the frozen order"]


def test_arms_rotate_within_each_block(cert: Path) -> None:
    """block 内の arm 順が巡回していない run (毎 block 同じ順) は INVALID_SCORER
    (族内差の時間ドリフト対策)."""
    samples = build(lookup)
    state = [s for s in samples if s.arm != bat.ARM_C0]
    fixed = sorted(
        state,
        key=lambda s: (
            sc.call_block(s.replicate, int(s.probe_id[1:]), s.k),
            sc.CALL_ARM_ORDER.index(s.arm),
        ),
    )
    n0 = len(samples) - len(state)
    relabelled = [replace(s, call_index=n0 + i) for i, s in enumerate(fixed)]
    rep = run(samples[:n0] + relabelled, cert)
    assert rep["verdict"] == VERDICT_INVALID_SCORER
    assert rep["structure_violations"] == ["call order differs from the frozen order"]


def test_block_arm_order_is_a_rotation() -> None:
    orders = [sc.block_arm_order(b) for b in range(len(sc.CALL_ARM_ORDER))]
    for o in orders:
        assert sorted(o) == sorted(bat.STATE_ARMS)
    for pos in range(len(sc.CALL_ARM_ORDER)):
        assert sorted(o[pos] for o in orders) == sorted(bat.STATE_ARMS)


def test_duplicate_call_index_is_invalid_scorer(cert: Path) -> None:
    samples = build(lookup)
    samples[1] = replace(samples[1], call_index=samples[0].call_index)
    rep = run(samples, cert)
    assert rep["verdict"] == VERDICT_INVALID_SCORER
    assert "call_index is not unique and non-negative" in rep["structure_violations"]


# ---- not_computed


def test_transport_failure_is_not_computed(cert: Path) -> None:
    samples = build(lookup)
    samples[3] = replace(samples[3], raw=None, parsed=None)
    rep = run(samples, cert)
    assert rep["status"] == sc.STATUS_NOT_COMPUTED
    assert rep["verdict"] is None


def test_missing_judge_rows_is_not_computed(cert: Path) -> None:
    samples = [
        s for s in build(lookup) if not (s.arm == bat.ARM_B and s.replicate == 0)
    ]
    assert run(samples, cert)["status"] == sc.STATUS_NOT_COMPUTED


def test_missing_c0_rows_is_not_computed(cert: Path) -> None:
    samples = [s for s in build(lookup) if s.arm != bat.ARM_C0]
    assert run(samples, cert)["status"] == sc.STATUS_NOT_COMPUTED


def test_all_verdict_words_are_reachable(cert: Path) -> None:
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
    assert pytest.approx(1.5 * sc.ALPHA) == sc.SIZE_CAP_WIDE
    assert pytest.approx(0.3) == sc.SD_EXACT_MAX
    assert sc.FROZEN_R % v2.N_POSITIONS == 0
    assert sc.FROZEN_R <= bat.R_MAX
    assert sc.FROZEN_K <= bat.K_MAX


# ---- 記録の schema (v2 の読み取り関数を使う)


def test_records_roundtrip_matches_evaluate(cert: Path) -> None:
    lines = to_lines(build(lookup))
    rep = sc.evaluate_records(lines, json.dumps(sc.request_meta()), cert)
    assert rep["verdict"] == VERDICT_PASS


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda _o: "{not json",
        lambda o: json.dumps({k: v for k, v in o.items() if k != "seed"}),
        lambda o: json.dumps({**o, "k": True}),
        lambda o: json.dumps({**o, "raw": 123}),
        lambda o: json.dumps([o]),
    ],
)
def test_malformed_record_is_invalid_scorer(cert: Path, corrupt: Callable) -> None:
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
