"""判定 rule (prereg v4 §5): 全 verdict 枝・schedule 監査・連鎖
replay・claim・記述に到達する合成 fixture.

記録は実モデル出力でなく、方針 (plan key・状態・表示された選択肢 → 生テキスト) から
``synth`` で作る。
"""

from __future__ import annotations

import dataclasses
import json
from typing import TYPE_CHECKING

import pytest
from scripts import closed_loop_battery as bat
from scripts import closed_loop_scorer as sc
from scripts import skill_lever_battery as v2

from .conftest import synth, to_lines

if TYPE_CHECKING:
    from pathlib import Path

N_Q = len(v2.lever_probes())


def run(records: list[sc.Record], cert: Path) -> dict[str, object]:
    return sc.evaluate(records, sc.request_meta(), cert)


def _probe(key: bat.PlanKey) -> v2.LeverProbe:
    return next(p for p in v2.lever_probes() if p.probe_id == key.probe_id)


def _row_label(state: bat.State, world: str, weather: str) -> str | None:
    """状態に同じ weather の成功行があれば、その行の label (= 世界の規則)."""
    if any(s[0] == weather for s in state.succeeded):
        return bat.rule(world)[weather]
    return None


def explorer(key: bat.PlanKey, state: bat.State, opts: tuple[str, ...]) -> str | None:
    """ループ段: 同じ weather の成功行に従い、無ければ未試行の選択肢を表示順に試す
    (探索が完了する).
    """
    sig = bat.loop_signature(key.replicate, key.step or 0)
    got = _row_label(state, key.world, sig[0])
    if got is not None:
        return got
    return next((o for o in opts if (sig, o) not in state.tried), opts[0])


def lookup(key: bat.PlanKey, state: bat.State, opts: tuple[str, ...]) -> str | None:
    """完全な reader: probe でも同じ weather の成功行に従う (C0 は表示先頭)."""
    if key.phase == bat.PHASE_LOOP:
        return explorer(key, state, opts)
    if key.phase == bat.PHASE_PROBE:
        got = _row_label(state, key.world, _probe(key).signature[0])
        if got is not None:
            return got
    return opts[0]


def blind(_key: bat.PlanKey, _state: bat.State, opts: tuple[str, ...]) -> str | None:
    return opts[0]


def probe_fraction(frac_w: float) -> object:
    """probe 段の 6K sample のうち frac_w を自分の規則、残りを族外の選択肢に.

    (分散 0)
    """

    def policy(key: bat.PlanKey, state: bat.State, opts: tuple[str, ...]) -> str | None:
        if key.phase != bat.PHASE_PROBE:
            return lookup(key, state, opts)
        p = _probe(key)
        cell = [q.probe_id for q in v2.lever_probes()].index(p.probe_id) * sc.FROZEN_K
        cell += key.k or 0
        if cell < round(frac_w * N_Q * sc.FROZEN_K):
            return p.pointed[key.world]
        fam = {p.pointed[key.world], p.pointed[v2.FOIL[key.world]]}
        others = [o for o in p.omega if o not in fam]
        return others[(key.k or 0) % len(others)]

    return policy


@pytest.fixture(scope="module")
def pass_records() -> list[sc.Record]:
    return synth(lookup)


# ---------------------------------------------------------------- verdicts


def test_full_lookup_is_pass_with_claim(
    pass_records: list[sc.Record], cert: Path
) -> None:
    rep = run(pass_records, cert)
    assert rep["verdict"] == sc.VERDICT_PASS
    assert rep["C"] == pytest.approx(1.0)
    assert rep["claim_branch"] == sc.CLAIM_PASS
    cov = rep["coverage"]
    assert cov["weather_coverage"] == 1.0
    assert cov["discovered_weathers"] == 3 * 4 * sc.FROZEN_R
    text = rep["claim_text"]
    assert "weather coverage = 1.000" in text
    assert f"発見した weather = {3 * 4 * sc.FROZEN_R} / {3 * 4 * sc.FROZEN_R}" in text
    assert "向きの付いた下界" in text
    assert sc.FLAGGED_FIXTURES == ("F1_most_label",)
    assert sc.FLAGGED_NOTE in text  # τ/4 を超えた fixture を PASS の文に入れる (DU-3)


def test_state_blind_policy_is_no_go_with_zero_units(cert: Path) -> None:
    rep = run(synth(blind), cert)
    assert rep["verdict"] == sc.VERDICT_ABSENT
    assert rep["units"] == [0.0] * (2 * sc.FROZEN_R)


def test_small_effect_is_no_go(cert: Path) -> None:
    rep = run(synth(probe_fraction(0.1)), cert)
    assert rep["C"] == pytest.approx(0.1)
    assert rep["verdict"] == sc.VERDICT_ABSENT
    assert rep["claim_branch"] == sc.CLAIM_NO_GO_LOOKUP


def test_effect_at_threshold_is_inconclusive(cert: Path) -> None:
    rep = run(synth(probe_fraction(0.3)), cert)
    assert rep["C"] == pytest.approx(0.3)
    assert rep["verdict"] == sc.VERDICT_UNDERPOWERED
    assert rep["claim_branch"] is None


def test_moderate_effect_is_pass(cert: Path) -> None:
    rep = run(synth(probe_fraction(0.5)), cert)
    assert rep["verdict"] == sc.VERDICT_PASS


def test_one_world_failure_is_not_pass(cert: Path) -> None:
    """1 世界 (B_rot) だけ規則も foil も選ばない → 成分 0。C と下限は τ を超えるが PASS
    にしない.
    """

    def policy(key: bat.PlanKey, state: bat.State, opts: tuple[str, ...]) -> str | None:
        if key.phase == bat.PHASE_PROBE and key.world == "B_rot":
            p = _probe(key)
            fam = {p.pointed["B_rot"], p.pointed[v2.FOIL["B_rot"]]}
            return next(o for o in p.omega if o not in fam)
        return lookup(key, state, opts)

    rep = run(synth(policy), cert)
    assert rep["components"]["B_rot"] == 0.0
    assert rep["C"] > 0.5
    assert rep["p_lower"] < sc.ALPHA
    assert rep["verdict"] == sc.VERDICT_UNDERPOWERED


def test_frozen_design_values() -> None:
    """凍結値 (power 表の選定、prereg v4 §4) を literal で pin する."""
    assert (sc.FROZEN_RENDERER, sc.FROZEN_R, sc.FROZEN_K, sc.FROZEN_M) == (
        bat.RENDERER_R1PLUS,
        8,
        5,
        4,
    )


def test_no_go_with_low_coverage_is_exploration_limited(cert: Path) -> None:
    """ループ段で常に B_rot の規則を選ぶ (状態を読まない) → 他 3 世界は発見しない →
    探索の不足側.
    """

    def fixed(key: bat.PlanKey, _state: bat.State, opts: tuple[str, ...]) -> str | None:
        if key.phase == bat.PHASE_LOOP:
            return bat.rule("B_rot")[
                bat.loop_signature(key.replicate, key.step or 0)[0]
            ]
        return opts[0]

    rep = run(synth(fixed), cert)
    assert rep["verdict"] == sc.VERDICT_ABSENT
    assert rep["coverage"]["by_world"]["B_rot"] == 1.0
    assert rep["coverage"]["weather_coverage"] < sc.COVERAGE_BRANCH
    assert rep["claim_branch"] == sc.CLAIM_NO_GO_EXPLORATION


def test_claim_branch_table() -> None:
    lo = {"weather_coverage": 0.5}
    hi = {"weather_coverage": 0.9}
    assert sc.claim_branch(sc.VERDICT_PASS, lo) == sc.CLAIM_PASS
    assert sc.claim_branch(sc.VERDICT_ABSENT, lo) == sc.CLAIM_NO_GO_EXPLORATION
    assert sc.claim_branch(sc.VERDICT_ABSENT, hi) == sc.CLAIM_NO_GO_LOOKUP
    assert sc.claim_branch(sc.VERDICT_ABSENT, {"weather_coverage": 2 / 3}) == (
        sc.CLAIM_NO_GO_LOOKUP
    )
    for v in (sc.VERDICT_UNDERPOWERED, sc.VERDICT_INVALID_BATTERY, None):
        assert sc.claim_branch(v, hi) is None


# ---------------------------------------------------------------- ⊥ gates


def _bottom_in(phase: str, world: str | None, frac: float) -> object:
    def policy(key: bat.PlanKey, state: bat.State, opts: tuple[str, ...]) -> str | None:
        if key.phase == phase and (world is None or key.world == world):
            idx = key.step if key.step is not None else (key.k or 0)
            if (idx % 10) < round(frac * 10):
                return "わからない"
        return lookup(key, state, opts)

    return policy


def test_c0_bottom_rate_is_invalid_battery(cert: Path) -> None:
    rep = run(synth(_bottom_in(bat.PHASE_C0, None, 0.4)), cert)
    assert rep["verdict"] == sc.VERDICT_INVALID_BATTERY
    assert rep["reasons"] == ["c0_bottom_rate"]


def test_c0_gate_precedes_missing_state_rows(cert: Path) -> None:
    recs = synth(_bottom_in(bat.PHASE_C0, None, 0.4), stop_after=sc.n_c0() + 3)
    rep = run(recs, cert)
    assert rep["verdict"] == sc.VERDICT_INVALID_BATTERY


def test_loop_bottom_rate_is_invalid_battery(cert: Path) -> None:
    rep = run(synth(_bottom_in(bat.PHASE_LOOP, "B", 0.3)), cert)
    assert rep["verdict"] == sc.VERDICT_INVALID_BATTERY
    assert rep["reasons"] == ["loop_bottom_rate"]
    assert rep["loop_bottom_rates"]["B"] > sc.LOOP_BOT_MAX


def test_probe_bottom_rate_is_invalid_battery(cert: Path) -> None:
    rep = run(synth(_bottom_in(bat.PHASE_PROBE, "A", 0.3)), cert)
    assert rep["verdict"] == sc.VERDICT_INVALID_BATTERY
    assert rep["reasons"] == ["probe_bottom_gate"]


def test_family_bottom_gap_is_invalid_battery(cert: Path) -> None:
    rep = run(synth(_bottom_in(bat.PHASE_PROBE, "A", 0.1)), cert)
    assert rep["verdict"] == sc.VERDICT_INVALID_BATTERY
    assert rep["reasons"] == ["probe_bottom_gate"]


def test_bottom_counts_in_denominator(cert: Path) -> None:
    def policy(key: bat.PlanKey, state: bat.State, opts: tuple[str, ...]) -> str | None:
        if key.phase == bat.PHASE_PROBE and (key.k or 0) == 0 and key.probe_id == "q00":
            return "わからない"
        return lookup(key, state, opts)

    rep = run(synth(policy), cert)
    assert rep["C"] == pytest.approx(1.0 - 1.0 / (N_Q * sc.FROZEN_K))


# ---------------------------------------------------------------- not computed


def test_transport_failure_is_not_computed(cert: Path) -> None:
    recs = synth(lookup, stop_after=sc.n_c0() + 10)
    recs[-1] = dataclasses.replace(recs[-1], raw=None, parsed=None)
    rep = run(recs, cert)
    assert rep["status"] == sc.STATUS_NOT_COMPUTED
    assert rep["reasons"] == ["transport_failure"]


def test_c0_incomplete_is_not_computed(cert: Path) -> None:
    rep = run(synth(lookup, stop_after=sc.n_c0() - 1), cert)
    assert rep["status"] == sc.STATUS_NOT_COMPUTED
    assert rep["reasons"] == ["c0_incomplete"]


def test_main_incomplete_is_not_computed(cert: Path) -> None:
    rep = run(synth(lookup, stop_after=sc.n_main() - 1), cert)
    assert rep["status"] == sc.STATUS_NOT_COMPUTED
    assert rep["reasons"] == ["main_incomplete"]


def test_missing_replay_does_not_block_verdict(
    pass_records: list[sc.Record], cert: Path
) -> None:
    rep = run(pass_records[: sc.n_main()], cert)
    assert rep["verdict"] == sc.VERDICT_PASS
    assert rep["describe"]["determinism"]["replay_n"] == 0


# ---------------------------------------------------------------- INVALID_SCORER


def test_missing_certification_is_invalid_scorer(
    pass_records: list[sc.Record], tmp_path: Path
) -> None:
    rep = run(pass_records, tmp_path / "none.json")
    assert rep["reasons"] == ["certification_missing_or_stale"]


def test_stale_certification_is_invalid_scorer(
    pass_records: list[sc.Record], cert: Path
) -> None:
    obj = json.loads(cert.read_text(encoding="utf-8"))
    obj["target_sha256"]["closed_loop_sim.py"] = "0" * 64
    cert.write_text(json.dumps(obj), encoding="utf-8")
    assert run(pass_records, cert)["reasons"] == ["certification_missing_or_stale"]


def test_uncertified_harness_is_invalid_scorer(
    pass_records: list[sc.Record], cert: Path
) -> None:
    obj = json.loads(cert.read_text(encoding="utf-8"))
    cert.write_text(json.dumps({**obj, "all_killed": False}), encoding="utf-8")
    assert run(pass_records, cert)["reasons"] == ["certification_missing_or_stale"]


def test_certification_covers_all_seven_files() -> None:
    assert set(sc.certified_targets()) == {
        "closed_loop_scorer.py",
        "closed_loop_battery.py",
        "closed_loop_sim.py",
        "skill_lever_scorer.py",
        "skill_lever_battery.py",
        "stage_b_scorer.py",
        "stage_b_battery.py",
    }


def test_battery_violation_is_invalid_scorer(
    pass_records: list[sc.Record], cert: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sc, "battery_violations", lambda _r: ["x: y"])
    assert run(pass_records, cert)["reasons"] == ["battery_checks"]


def test_meta_mismatch_is_invalid_scorer(
    pass_records: list[sc.Record], cert: Path
) -> None:
    meta = {**sc.request_meta(), "temperature": 0.8}
    rep = sc.evaluate(pass_records, meta, cert)
    assert rep["reasons"] == ["request_meta_mismatch"]


def test_schedule_gap_is_invalid_scorer(
    pass_records: list[sc.Record], cert: Path
) -> None:
    recs = [r for r in pass_records if r.call_index != 5]
    assert run(recs, cert)["reasons"] == ["schedule"]


def test_physical_line_swap_is_invalid_scorer(
    pass_records: list[sc.Record], cert: Path
) -> None:
    """call_index はそのままで、記録の行順だけを入れ替える."""
    recs = list(pass_records)
    i = sc.n_c0() + 3
    recs[i], recs[i + 1] = recs[i + 1], recs[i]
    assert run(recs, cert)["reasons"] == ["schedule"]


def test_schedule_swapped_worlds_is_invalid_scorer(
    pass_records: list[sc.Record], cert: Path
) -> None:
    """同じ block の 2 世界の呼び出し順を入れ替える (call_index を交換)."""
    recs = list(pass_records)
    i = sc.n_c0()
    a, b = recs[i], recs[i + 1]
    recs[i] = dataclasses.replace(b, call_index=a.call_index)
    recs[i + 1] = dataclasses.replace(a, call_index=b.call_index)
    rep = run(recs, cert)
    assert rep["reasons"] == ["schedule"]


def test_state_before_c0_is_invalid_scorer(
    pass_records: list[sc.Record], cert: Path
) -> None:
    recs = list(pass_records)
    i = sc.n_c0()
    recs[0], recs[i] = (
        dataclasses.replace(recs[i], call_index=0),
        dataclasses.replace(recs[0], call_index=i),
    )
    assert run(recs, cert)["reasons"] == ["schedule"]


def test_wrong_seed_is_invalid_scorer(
    pass_records: list[sc.Record], cert: Path
) -> None:
    recs = list(pass_records)
    i = sc.n_c0() + 2
    recs[i] = dataclasses.replace(recs[i], seed=recs[i].seed + 1)
    assert run(recs, cert)["reasons"] == ["schedule"]


def test_probe_seed_is_checked(pass_records: list[sc.Record], cert: Path) -> None:
    recs = list(pass_records)
    i = next(n for n, r in enumerate(recs) if r.phase == bat.PHASE_PROBE)
    recs[i] = dataclasses.replace(recs[i], seed=recs[i].seed + 1)
    assert run(recs, cert)["reasons"] == ["schedule"]


def test_records_after_transport_failure_are_invalid(
    pass_records: list[sc.Record], cert: Path
) -> None:
    recs = list(pass_records[: sc.n_c0() + 20])
    recs[sc.n_c0() + 5] = dataclasses.replace(
        recs[sc.n_c0() + 5], raw=None, parsed=None
    )
    assert run(recs, cert)["reasons"] == ["schedule"]


def test_parse_mismatch_is_invalid_scorer(
    pass_records: list[sc.Record], cert: Path
) -> None:
    recs = list(pass_records)
    i = sc.n_c0() + 7
    recs[i] = dataclasses.replace(
        recs[i], parsed="sit_quiet" if recs[i].parsed != "sit_quiet" else "read_book"
    )
    assert run(recs, cert)["reasons"] == ["parse"]


def test_chain_detects_tampered_prompt(
    pass_records: list[sc.Record], cert: Path
) -> None:
    recs = list(pass_records)
    i = sc.n_c0() + 40
    recs[i] = dataclasses.replace(recs[i], prompt_sha256="0" * 64)
    assert run(recs, cert)["reasons"] == ["chain_replay"]


def test_chain_detects_forged_outcome(
    pass_records: list[sc.Record], cert: Path
) -> None:
    """ある loop 段の行動 (raw と parsed) を書き換える.

    以後の prompt が再構成と食い違う。
    """
    recs = list(pass_records)
    i = next(
        n
        for n, r in enumerate(recs)
        if r.phase == bat.PHASE_LOOP and r.step == 0 and r.replicate == 0
    )
    rec = recs[i]
    opts = bat.dev_options(0, 0)
    other = next(o for o in opts if o != rec.parsed)
    recs[i] = dataclasses.replace(rec, raw=other, parsed=other)
    assert run(recs, cert)["reasons"] == ["chain_replay"]


def test_chain_detects_wrong_renderer(cert: Path) -> None:
    other = next(x for x in bat.RENDERERS if x != sc.FROZEN_RENDERER)
    recs = synth(lookup, renderer=other)
    assert run(recs, cert)["reasons"] == ["chain_replay"]


def test_chain_detects_probe_from_wrong_state(
    pass_records: list[sc.Record], cert: Path
) -> None:
    recs = list(pass_records)
    # replay の対象 (q00, k = 0) でない probe を改ざんする (replay 照合でなく probe
    # 照合で捕まえる)
    i = next(n for n, r in enumerate(recs) if r.phase == bat.PHASE_PROBE and r.k == 1)
    rec = recs[i]
    assert rec.probe_id is not None
    qi = [p.probe_id for p in v2.lever_probes()].index(rec.probe_id)
    msgs = bat.probe_messages(
        bat.EMPTY_STATE, rec.world, rec.replicate, qi, sc.FROZEN_RENDERER
    )
    recs[i] = dataclasses.replace(rec, prompt_sha256=sc.messages_sha256(msgs))
    assert run(recs, cert)["reasons"] == ["chain_replay"]


def test_chain_detects_tampered_c0(pass_records: list[sc.Record], cert: Path) -> None:
    recs = list(pass_records)
    recs[3] = dataclasses.replace(recs[3], prompt_sha256="1" * 64)
    assert run(recs, cert)["reasons"] == ["chain_replay"]


def test_chain_detects_replay_prompt_mismatch(
    pass_records: list[sc.Record], cert: Path
) -> None:
    recs = list(pass_records)
    recs[-1] = dataclasses.replace(recs[-1], prompt_sha256="2" * 64)
    assert run(recs, cert)["reasons"] == ["chain_replay"]


def test_chain_replay_reconstructs_final_states(pass_records: list[sc.Record]) -> None:
    final, problems = sc.replay_states(pass_records)
    assert problems == []
    assert len(final) == 4 * sc.FROZEN_R
    assert all(len(st.succeeded) == 12 for st in final.values())


def test_record_schema_violations(pass_records: list[sc.Record], cert: Path) -> None:
    lines = to_lines(pass_records)
    meta = json.dumps(sc.request_meta())
    assert sc.evaluate_records(lines, meta, cert)["verdict"] == sc.VERDICT_PASS
    bad_cases = []
    obj = json.loads(lines[sc.n_c0()])
    bad_cases.append({**obj, "step": 1.0})  # float
    bad_cases.append({**obj, "probe_id": "q00"})  # loop なのに probe_id
    bad_cases.append({k: v for k, v in obj.items() if k != "seed"})
    bad_cases.append({**obj, "phase": "other"})
    bad_cases.append({**obj, "replicate": True})
    for bad in bad_cases:
        mutated = [*lines]
        mutated[sc.n_c0()] = json.dumps(bad)
        rep = sc.evaluate_records(mutated, meta, cert)
        assert rep["reasons"] == ["record_schema"], bad
    assert sc.evaluate_records(["{nope"], meta, cert)["reasons"] == ["record_schema"]
    assert sc.evaluate_records(lines, "[]", cert)["reasons"] == ["record_schema"]


# ---------------------------------------------------------------- describe


def test_determinism_rates(pass_records: list[sc.Record]) -> None:
    det = sc.determinism(pass_records)
    assert (
        det["in_run_groups"] >= sc.FROZEN_R
    )  # t = 0 は 4 世界が同一 prompt・同一 seed
    assert det["in_run_identical_rate"] == 1.0
    assert det["replay_n"] == 9 * sc.FROZEN_R
    assert det["replay_identical_rate"] == 1.0
    assert det["exact_cancellation"] is True
    recs = list(pass_records)
    recs[-1] = dataclasses.replace(recs[-1], raw="other text")
    assert sc.determinism(recs)["exact_cancellation"] is False


def test_describe_reports_strata_and_tv(
    pass_records: list[sc.Record], cert: Path
) -> None:
    rep = run(pass_records, cert)
    desc = rep["describe"]
    assert set(desc["lambda_strata"]) == {"4"}  # 全 signature を発見
    assert desc["lambda_strata"]["4"]["mean_w_minus_foil"] == 1.0
    assert desc["family_tv_mean"] == 1.0
    assert desc["split_half_tv_mean"] == 0.0


def test_all_verdict_words_reachable(
    cert: Path, pass_records: list[sc.Record], tmp_path: Path
) -> None:
    got = {
        run(pass_records, cert)["verdict"],
        run(synth(blind), cert)["verdict"],
        run(synth(probe_fraction(0.3)), cert)["verdict"],
        run(synth(_bottom_in(bat.PHASE_C0, None, 0.4)), cert)["verdict"],
        run(pass_records, tmp_path / "none.json")["verdict"],
    }
    assert got == {
        sc.VERDICT_PASS,
        sc.VERDICT_ABSENT,
        sc.VERDICT_UNDERPOWERED,
        sc.VERDICT_INVALID_BATTERY,
        sc.VERDICT_INVALID_SCORER,
    }
