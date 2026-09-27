"""記述報告 (prereg v4 §10) — evaluate に無い項目・§9 の抑制・records との結び付け."""

from __future__ import annotations

import json
import shutil
from typing import TYPE_CHECKING, Any

import pytest
from scripts import closed_loop_battery as bat
from scripts import closed_loop_describe as ds
from scripts import closed_loop_evaluate as ev
from scripts import closed_loop_scorer as sc
from scripts.stage_b_scorer import (
    VERDICT_INVALID_BATTERY,
    VERDICT_INVALID_SCORER,
    VERDICT_PASS,
    VERDICT_UNDERPOWERED,
)

from tests.test_closed_loop_driver._mock import CERT, N_C0, records

if TYPE_CHECKING:
    from pathlib import Path

    from tests.test_closed_loop_driver.test_driver import Run


def _results(run_dir: Path, out: Path) -> dict[str, Any]:
    ev.main(
        [
            "--records",
            str(run_dir / "records.jsonl"),
            "--meta",
            str(run_dir / "meta.json"),
            "--cert",
            str(CERT),
            "--out",
            str(out),
        ]
    )
    return json.loads(out.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pass_report(
    follow_run: Run, tmp_path_factory: pytest.TempPathFactory
) -> dict[str, Any]:
    tmp = tmp_path_factory.mktemp("describe")
    run_dir, _, _ = follow_run
    _results(run_dir, tmp / "results.json")
    out = tmp / "describe.json"
    code = ds.main(
        [
            "--records",
            str(run_dir / "records.jsonl"),
            "--results",
            str(tmp / "results.json"),
            "--run-dir",
            str(run_dir),
            "--out",
            str(out),
        ]
    )
    assert code == 0
    return json.loads(out.read_text(encoding="utf-8"))


def test_pass_run_description(pass_report: dict[str, Any]) -> None:
    rep = pass_report
    assert rep["verdict"]["verdict"] == VERDICT_PASS
    assert rep["verdict"]["claim_branch"] == sc.CLAIM_PASS
    assert rep["run_gate_problems"] == []
    assert rep["effects_suppressed"] is None
    assert rep["effects"]["C"] == 1.0
    assert rep["effects"]["coverage"]["weather_coverage"] == 1.0
    assert sc.FLAGGED_NOTE in rep["effects"]["claim_text"]
    assert rep["c0"]["n"] == N_C0
    assert rep["c0"]["bottom_rate"] == 0.0
    assert rep["interpretation_note"] is None
    # mock は body に決定的なので、同一 prompt・seed の群は raw も一致する
    assert rep["cancellation_wording"] == ds.EXACT
    assert rep["n_resends"] == 0
    assert rep["n_finish_length"] == 0


def test_c0_agreement_uses_the_same_keys_as_v2_and_v3(
    pass_report: dict[str, Any],
) -> None:
    """§10 (iii): v4 の C0 は v2 / v3 の C0 と byte 一致する prompt・seed を持つ."""
    agree = pass_report["c0_agreement"]
    assert set(agree) == {"v2", "v3"}
    assert agree["v3"]["n_common"] == N_C0
    assert agree["v2"]["n_common"] > 0
    for row in agree.values():
        assert 0.0 <= row["raw_identical_rate"] <= 1.0


def test_c0_agreement_counts_raw_and_parsed_separately() -> None:
    key = sc.frozen_plan()[0]
    mine = sc.Record(0, key.phase, key.world, 0, None, key.probe_id, 0, 7, "s",
                     " read_book", "read_book")  # fmt: skip
    prev = ds.v2sc.Sample(0, bat.ARM_C0, 0, key.probe_id or "", 0, 7, "s",
                          "read_book", "read_book")  # fmt: skip
    other_seed = ds.v2sc.Sample(1, bat.ARM_C0, 0, key.probe_id or "", 0, 8, "s",
                                "read_book", "read_book")  # fmt: skip
    got = ds.c0_agreement([mine], [prev, other_seed])
    assert got == {
        "n_common": 1,
        "raw_identical_rate": 0.0,
        "parsed_identical_rate": 1.0,
    }


def test_c0_positions_separate_bottom_and_out_of_omega() -> None:
    plan = sc.frozen_plan()
    rows = []
    for i, key in enumerate(plan[:3]):
        order = ds.v2bat.layout(key.replicate).option_order[key.probe_id or ""]
        parsed = [order[1], None, next(a for a in bat.ACTIONS if a not in order)][i]
        rows.append(
            sc.Record(
                i,
                key.phase,
                key.world,
                key.replicate,
                None,
                key.probe_id,
                key.k,
                0,
                "s",
                "x",
                parsed,
            )
        )
    dist = ds.c0_distribution(rows)
    assert dist["position_rates"] == {"1": 1 / 3, "bot": 1 / 3, "oov": 1 / 3}
    assert dist["bottom_rate"] == pytest.approx(1 / 3)


def _minimal(verdict: str | None, status: str = sc.STATUS_COMPUTED) -> dict[str, Any]:
    return {
        "status": status,
        "verdict": verdict,
        "claim_branch": "x",
        "C": 0.5,
        "components": {},
        "coverage": {"weather_coverage": 1.0},
        "describe": {"determinism": {"exact_cancellation": False}},
    }


def _describe(results: dict[str, Any], gate: tuple[str, ...] = ()) -> dict[str, Any]:
    return ds.describe([], results, {}, {}, gate)


@pytest.mark.parametrize(
    ("verdict", "status"),
    [
        (VERDICT_INVALID_SCORER, sc.STATUS_COMPUTED),
        (VERDICT_INVALID_BATTERY, sc.STATUS_COMPUTED),
        (None, sc.STATUS_NOT_COMPUTED),
    ],
)
def test_effects_are_suppressed_unless_the_verdict_is_valid(
    verdict: str | None, status: str
) -> None:
    rep = _describe(_minimal(verdict, status))
    assert rep["effects"] is None
    assert rep["cancellation_wording"] is None
    assert rep["effects_suppressed"] is not None


def test_run_gate_problems_suppress_every_effect() -> None:
    rep = _describe(_minimal(VERDICT_PASS), ("exit_reason='aborted'",))
    assert rep["effects"] is None
    assert rep["verdict"]["status"] == sc.STATUS_NOT_COMPUTED
    assert rep["verdict"]["verdict"] is None
    assert rep["verdict"]["claim_branch"] is None


def test_inconclusive_keeps_numbers_with_a_note() -> None:
    rep = _describe(_minimal(VERDICT_UNDERPOWERED))
    assert rep["effects"]["C"] == 0.5
    assert "効果の有無を書かない" in rep["interpretation_note"]


def test_cancellation_wording_is_downgraded_below_one() -> None:
    assert _describe(_minimal(VERDICT_PASS))["cancellation_wording"] == ds.EXPECTED
    exact = _minimal(VERDICT_PASS)
    exact["describe"]["determinism"]["exact_cancellation"] = True
    assert _describe(exact)["cancellation_wording"] == ds.EXACT


def test_main_refuses_a_run_that_fails_the_gate(
    follow_run: Run, tmp_path: Path, pass_report: dict[str, Any]
) -> None:
    """DR-6: gate が落ちた run の label を見ない (records を読まずに止まる)."""
    assert pass_report["effects"] is not None
    run_dir = tmp_path / "run"
    shutil.copytree(follow_run[0], run_dir)
    prov = json.loads((run_dir / "provenance.json").read_text(encoding="utf-8"))
    prov["exit_reason"] = "aborted"
    (run_dir / "provenance.json").write_text(json.dumps(prov), encoding="utf-8")
    _results(run_dir, tmp_path / "results.json")
    out = tmp_path / "describe.json"
    args = ["--records", str(run_dir / "records.jsonl"), "--results",
            str(tmp_path / "results.json"), "--run-dir", str(run_dir),
            "--out", str(out)]  # fmt: skip
    assert ds.main(args) == 2
    assert not out.exists()


def test_main_requires_the_records_of_the_run_dir(
    follow_run: Run, first_run: Run, tmp_path: Path
) -> None:
    """--records と --run-dir が別の run なら止まる (gate 合格を流用しない)."""
    _results(first_run[0], tmp_path / "results.json")
    args = ["--records", str(first_run[0] / "records.jsonl"), "--results",
            str(tmp_path / "results.json"), "--run-dir", str(follow_run[0]),
            "--out", str(tmp_path / "d.json")]  # fmt: skip
    assert ds.main(args) == 2
    assert not (tmp_path / "d.json").exists()


def test_main_refuses_results_of_other_records(
    follow_run: Run, first_run: Run, tmp_path: Path
) -> None:
    _results(first_run[0], tmp_path / "results.json")
    args = ["--records", str(follow_run[0] / "records.jsonl"), "--results",
            str(tmp_path / "results.json"), "--run-dir", str(follow_run[0]),
            "--out", str(tmp_path / "d.json")]  # fmt: skip
    assert ds.main(args) == 2  # results.json は first_run の records から
    assert not (tmp_path / "d.json").exists()


def test_non_exact_label_rate_by_phase(varying_run: Run) -> None:
    recs = records(varying_run[0])
    rep = ds.describe(recs, _minimal(VERDICT_PASS), {}, {})
    rates = rep["non_exact_label_rate"]
    assert set(rates) == {
        bat.PHASE_C0,
        bat.PHASE_LOOP,
        bat.PHASE_PROBE,
        bat.PHASE_REPLAY,
    }
    assert 0.0 < rates[bat.PHASE_LOOP] < 1.0


def test_unreadable_previous_records_are_an_error_not_zero() -> None:
    """v2 / v3 の記録が読めないことを「0 件一致」に畳まない."""
    assert ds.c0_agreement([], None) == {
        "error": "previous C0 records could not be read"
    }
    got = ds._read_previous({"x": ds.PREVIOUS_C0["v3"].with_name("missing.jsonl")})
    assert got == {"x": None}
