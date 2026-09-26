"""記述報告 (prereg v3 §10) — 合成記録で既知の値を返すこと (判定には使わない)."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import TYPE_CHECKING

import pytest
from scripts import skill_experience_battery as bat
from scripts import skill_experience_describe as ds
from scripts import skill_experience_driver as drv
from scripts import skill_experience_scorer as sc
from scripts import skill_lever_battery as v2bat
from scripts.stage_b_battery import ACTIONS
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


def results(verdict: str | None, control: str | None = VERDICT_PASS) -> dict:
    status = sc.STATUS_COMPUTED if verdict is not None else sc.STATUS_NOT_COMPUTED
    return {"status": status, "verdict": verdict, "control": {"verdict": control}}


V2 = {
    "C": 0.8,
    "components": {"A": 0.7, "A_rot": 0.8, "B": 0.8, "B_rot": 0.9},
}


def synth(policy: Callable[[drv.Key], str], keys: list[drv.Key]) -> list[sc.Sample]:
    probes = v2bat.lever_probes()
    out = []
    for i, key in enumerate(keys):
        arm, r, qi, k = key
        seed, sha = sc.expected_sample(*key)
        raw = policy(key)
        out.append(
            sc.Sample(
                i, arm, r, probes[qi].probe_id, k, seed, sha, raw, sc.parse_choice(raw)
            )
        )
    return out


def extract(key: drv.Key) -> str:
    arm, r, qi, _ = key
    probe = v2bat.lever_probes()[qi]
    if arm == bat.ARM_C0:
        return v2bat.layout(r).option_order[probe.probe_id][0]
    return probe.pointed[bat.POINTS_AS[arm]]


def first_shown(key: drv.Key) -> str:
    """成否を読まない: 表示先頭 (arm に依らない)."""
    _, r, qi, _ = key
    return v2bat.layout(r).option_order[v2bat.lever_probes()[qi].probe_id][0]


def test_extracting_run_description() -> None:
    rep = ds.describe(synth(extract, drv.schedule()), results(VERDICT_PASS), V2)
    assert rep["n_transport_failures"] == 0
    assert rep["c0"]["position_rates"] == {"0": 1.0}
    assert rep["c0"]["bottom_rate"] == 0.0
    assert sum(rep["c0"]["pointed_rates"].values()) == pytest.approx(1.0)
    for arm in bat.STATE_ARMS:
        row = rep["state_arms"][arm]
        assert row["w_rate"] == 1.0
        assert row["foil_rate"] == 0.0
        assert row["filler_rate"] == 0.0
        assert row["w_rate_minus_c0"] == pytest.approx(
            1.0 - rep["c0"]["pointed_rates"][bat.POINTS_AS[arm]]
        )
    for est in (rep["judge_estimand"], rep["control_estimand"]):
        assert est["C"] == 1.0
        assert set(est["components"].values()) == {1.0}
        assert est["p_zero"] == pytest.approx(1 / 2 ** (2 * sc.FROZEN_R))
    assert set(rep["control_estimand"]["components"]) == set(bat.CONTROL_ARMS)
    assert rep["control_C_minus_judge_C"] == 0.0
    assert rep["v2_anchor"]["C_v3_over_C_v2"] == pytest.approx(1.25)
    assert rep["v2_anchor"]["component_minus_v2"]["A"] == pytest.approx(0.3)
    assert set(rep["non_exact_label_rate"].values()) == {0.0}


def test_control_minus_judge_and_filler_rate() -> None:
    """判定は成否を読まず、対照は抽出。L_B は filler を言い添え、L_A は filler だけ."""

    def policy(key: drv.Key) -> str:
        if key[0] == "L_B":
            return f"{extract(key)} ({bat.FILLERS[1]} ではない)"
        if key[0] == "L_A" and key[3] == 0:
            return f"**{bat.FILLERS[0].upper()}**"
        return extract(key) if key[0] in bat.CONTROL_ARMS else first_shown(key)

    rep = ds.describe(
        synth(policy, drv.schedule()), results(VERDICT_ABSENT, VERDICT_PASS), V2
    )
    assert rep["judge_estimand"]["C"] == 0.0
    assert rep["control_C_minus_judge_C"] == rep["control_estimand"]["C"]
    lb, la = rep["state_arms"]["L_B"], rep["state_arms"]["L_A"]
    # 言及しただけ (label も答えた) は filler を答えたことにしない
    assert lb["filler_rate"] == 0.0
    assert lb["filler_mention_rate"] == 1.0
    assert la["filler_rate"] == pytest.approx(1 / sc.FROZEN_K)
    assert la["filler_mention_rate"] == pytest.approx(1 / sc.FROZEN_K)
    assert la["bot_rate"] == pytest.approx(1 / sc.FROZEN_K)
    assert rep["state_arms"]["A"]["filler_rate"] == 0.0
    assert rep["non_exact_label_rate"]["L_B"] == 1.0


def test_answered_filler_needs_bottom_and_exactly_one_filler() -> None:
    f0, f1 = bat.FILLERS
    assert ds.answered_filler(f0)
    assert ds.answered_filler(f"<think>read_book</think> {f1}。")
    assert ds.answered_filler("".join(chr(ord(c) + 0xFEE0) for c in f0.upper()))
    assert not ds.answered_filler(f"{f0} と {f1}")  # 2 種
    assert not ds.answered_filler(f"read_book ({f0} ではない)")  # label あり
    assert not ds.answered_filler("わからない")
    assert not ds.answered_filler(f"x{f0}")  # 単語境界


def test_c0_positions_separate_bottom_and_out_of_omega() -> None:
    def policy(key: drv.Key) -> str:
        _, r, qi, k = key
        if k == 0:
            return "わからない"
        if k == 1:
            probe = v2bat.lever_probes()[qi]
            shown = v2bat.layout(r).option_order[probe.probe_id]
            return next(a for a in ACTIONS if a not in shown)
        return extract(key)

    rep = ds.describe(synth(policy, drv.c0_schedule()), results(VERDICT_PASS))
    rates = rep["c0"]["position_rates"]
    assert rates["bot"] == pytest.approx(1 / sc.FROZEN_K)
    assert rates["oov"] == pytest.approx(1 / sc.FROZEN_K)
    assert rates["0"] == pytest.approx(1 - 2 / sc.FROZEN_K)
    assert "none" not in rates


def test_c0_only_and_verbose_answers() -> None:
    rows = synth(lambda key: f" {extract(key)} です。", drv.c0_schedule())
    rep = ds.describe(rows, results(VERDICT_INVALID_BATTERY, None))
    assert rep["judge_estimand"] is None
    assert rep["control_estimand"] is None
    assert rep["state_arms"][bat.ARM_A]["w_rate"] is None
    assert rep["non_exact_label_rate"] == {bat.ARM_C0: 1.0}


@pytest.mark.parametrize(
    "res",
    [
        results(VERDICT_INVALID_SCORER),
        results(VERDICT_INVALID_BATTERY),
        results(None, None),
    ],
)
def test_effects_are_suppressed_unless_the_verdict_is_valid(res: dict) -> None:
    rep = ds.describe(synth(extract, drv.schedule()), res, V2)
    assert rep["effects_suppressed"]
    assert rep["control_effects_suppressed"]
    assert rep["judge_estimand"] is None
    assert rep["control_estimand"] is None
    assert rep["v2_anchor"] is None
    assert rep["control_C_minus_judge_C"] is None
    for row in rep["state_arms"].values():
        assert row["w_rate"] is None
        assert row["w_rate_minus_c0"] is None
        assert row["bot_rate"] == 0.0  # ⊥ 率は INVALID の説明に要るので残す
    assert rep["c0"]["position_rates"] == {"0": 1.0}


def test_control_effects_are_suppressed_when_the_control_is_invalid() -> None:
    rep = ds.describe(
        synth(extract, drv.schedule()),
        results(VERDICT_PASS, VERDICT_INVALID_BATTERY),
        V2,
    )
    assert rep["effects_suppressed"] is None
    assert rep["judge_estimand"]["C"] == 1.0
    assert rep["control_effects_suppressed"]
    assert rep["control_estimand"] is None
    assert rep["control_C_minus_judge_C"] is None
    assert rep["state_arms"]["L_A"]["w_rate"] is None
    assert rep["state_arms"]["A"]["w_rate"] == 1.0


def test_inconclusive_keeps_numbers_with_a_note() -> None:
    rep = ds.describe(
        synth(extract, drv.schedule()),
        results(VERDICT_UNDERPOWERED, VERDICT_UNDERPOWERED),
        V2,
    )
    assert rep["effects_suppressed"] is None
    assert rep["judge_estimand"]["p_zero"] is not None
    assert "効果の有無を書かない" in rep["interpretation_note"]
    for verdict in (VERDICT_PASS, VERDICT_ABSENT):
        rep = ds.describe(synth(extract, drv.schedule()), results(verdict), V2)
        assert rep["interpretation_note"] is None


def test_run_gate_problems_suppress_every_effect() -> None:
    rep = ds.describe(
        synth(extract, drv.schedule()),
        results(VERDICT_PASS),
        V2,
        ["exit_reason='aborted'"],
    )
    assert rep["run_gate_problems"] == ["exit_reason='aborted'"]
    assert rep["effects_suppressed"]
    assert rep["control_effects_suppressed"]
    assert rep["judge_estimand"] is None
    assert rep["control_estimand"] is None
    assert rep["interpretation_note"] is None
    assert all(row["w_rate"] is None for row in rep["state_arms"].values())


def _files(tmp_path: Path, n_prov: int | None = None) -> tuple[Path, Path, Path]:
    rows = synth(extract, drv.schedule())
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    rec = run_dir / "samples.jsonl"
    rec.write_text(
        "".join(
            json.dumps(dataclasses.asdict(s), ensure_ascii=False) + "\n" for s in rows
        ),
        encoding="utf-8",
    )
    prov = {
        "exit_reason": "completed",
        "meta_matches_frozen": True,
        "driver_sha256_start": "a" * 64,
        "driver_sha256_end": "a" * 64,
        "model_digest_start": "d",
        "model_digest_end": "d",
        "response_models": [v2bat.MODEL],
        "n_samples": len(rows) if n_prov is None else n_prov,
    }
    (run_dir / "provenance.json").write_text(json.dumps(prov), encoding="utf-8")
    res = tmp_path / "results.json"
    sha = hashlib.sha256(rec.read_bytes()).hexdigest()
    res.write_text(
        json.dumps({**results(VERDICT_PASS), "inputs": {"records_sha256": sha}}),
        encoding="utf-8",
    )
    return rec, res, run_dir


def _main(rec: Path, res: Path, run_dir: Path, out: Path, *extra: str) -> int:
    args = ["--records", str(rec), "--results", str(res), "--run-dir", str(run_dir)]
    return ds.main([*args, "--out", str(out), *extra])


def test_main_reads_the_v2_anchor_and_tolerates_its_absence(tmp_path: Path) -> None:
    rec, res, run_dir = _files(tmp_path)
    out = tmp_path / "describe.json"
    assert _main(rec, res, run_dir, out) == 0
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["run_gate_problems"] == []
    committed = json.loads(ds.V2_RESULTS.read_text(encoding="utf-8"))
    assert rep["v2_anchor"]["C_v2"] == committed["C"]
    missing = str(tmp_path / "missing.json")
    assert _main(rec, res, run_dir, out, "--v2-results", missing) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["v2_anchor"] is None


def test_main_applies_the_run_gate(tmp_path: Path) -> None:
    rec, res, run_dir = _files(tmp_path, n_prov=1)
    out = tmp_path / "describe.json"
    assert _main(rec, res, run_dir, out) == 0
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["run_gate_problems"]
    assert rep["judge_estimand"] is None


def test_main_refuses_results_of_other_records(tmp_path: Path) -> None:
    rec, res, run_dir = _files(tmp_path)
    obj = json.loads(res.read_text(encoding="utf-8"))
    obj["inputs"]["records_sha256"] = "0" * 64
    res.write_text(json.dumps(obj), encoding="utf-8")
    out = tmp_path / "describe.json"
    assert _main(rec, res, run_dir, out) == 2
    assert not out.exists()
