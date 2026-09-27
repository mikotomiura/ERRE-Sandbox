"""実走の終了状態の gate — 判定に進めない run を機械的に止める.

凍結 run.sh は provenance を読まないので、aborted でも記録が揃えば verdict を出せる。
gate が run.sh の前にそれを止めることを、driver の mock run で確かめる。
"""

from __future__ import annotations

import json
import shutil
from typing import TYPE_CHECKING, Any

import pytest
from scripts import closed_loop_driver as drv
from scripts import closed_loop_run_gate as gate
from scripts import skill_lever_battery as v2bat
from scripts.stage_b_scorer import VERDICT_PASS

from tests.test_closed_loop_driver._mock import (
    N_C0,
    N_PLAN,
    c0_bottom,
    do_run,
    evaluate,
    provenance,
)

if TYPE_CHECKING:
    from pathlib import Path

    from tests.test_closed_loop_driver.test_driver import Run


def _copy(run: Run, tmp_path: Path) -> Path:
    dst = tmp_path / "run"
    shutil.copytree(run[0], dst)
    return dst


def _rewrite_prov(run_dir: Path, **changes: object) -> None:
    prov = {**provenance(run_dir), **changes}
    (run_dir / "provenance.json").write_text(json.dumps(prov), encoding="utf-8")


def _lines(run_dir: Path) -> list[str]:
    return (run_dir / "records.jsonl").read_text(encoding="utf-8").splitlines()


def _write_lines(run_dir: Path, lines: list[str], tail: str = "\n") -> None:
    text = "\n".join(lines) + tail
    (run_dir / "records.jsonl").write_text(text, encoding="utf-8")


def test_completed_run_passes_the_gate(follow_run: Run, tmp_path: Path) -> None:
    run_dir = _copy(follow_run, tmp_path)
    assert gate.run_gate_problems(run_dir) == []
    assert gate.main(["--run-dir", str(run_dir)]) == 0


def test_c0_gate_stop_passes_the_gate(tmp_path: Path) -> None:
    reason, _ = do_run(tmp_path / "run", c0_bottom(49))
    assert reason == drv.REASON_C0_GATE
    assert gate.run_gate_problems(tmp_path / "run") == []


def test_aborted_run_with_complete_records_is_stopped(
    follow_run: Run, tmp_path: Path
) -> None:
    """記録は揃い scorer は verdict を出すが、driver が aborted なら gate が止める."""
    run_dir = _copy(follow_run, tmp_path)
    _rewrite_prov(run_dir, exit_reason=drv.REASON_ABORTED)
    assert evaluate(run_dir)["verdict"] == VERDICT_PASS
    problems = gate.run_gate_problems(run_dir)
    assert problems == ["exit_reason='aborted'"]
    assert gate.main(["--run-dir", str(run_dir)]) == 1


@pytest.mark.parametrize(
    ("changes", "fragment"),
    [
        ({"exit_reason": "transport_failure"}, "exit_reason"),
        ({"meta_matches_frozen": None}, "meta_matches_frozen"),
        ({"meta_matches_frozen": False}, "meta_matches_frozen"),
        ({"driver_sha256_start": None, "driver_sha256_end": None}, "driver sha256"),
        ({"driver_sha256_end": "b" * 64}, "driver sha256"),
        ({"model_digest_start": None, "model_digest_end": None}, "model digest"),
        ({"model_digest_end": "sha256:" + "1" * 64}, "model digest"),
        ({"response_models": []}, "response_models"),
        ({"response_models": ["qwen3:4b"]}, "response_models"),
        ({"response_models": [v2bat.MODEL, "qwen3:4b"]}, "response_models"),
        ({"n_records": N_PLAN - 1}, "n_records"),
        ({"endpoint": "http://example:11434"}, "endpoint"),
        ({"endpoint": None}, "endpoint"),
    ],
)
def test_each_provenance_field_is_checked(
    follow_run: Run, tmp_path: Path, changes: dict[str, Any], fragment: str
) -> None:
    run_dir = _copy(follow_run, tmp_path)
    _rewrite_prov(run_dir, **changes)
    problems = gate.run_gate_problems(run_dir)
    assert len(problems) == 1
    assert fragment in problems[0]


def test_truncated_records_are_stopped(follow_run: Run, tmp_path: Path) -> None:
    """行数と n_records が一致しても、completed の件数 (2,808) に足りなければ止める."""
    run_dir = _copy(follow_run, tmp_path)
    _write_lines(run_dir, _lines(run_dir)[:-1])
    _rewrite_prov(run_dir, n_records=N_PLAN - 1)
    problems = gate.run_gate_problems(run_dir)
    assert problems == [f"{N_PLAN - 1} lines != {N_PLAN} for completed"]


def test_c0_gate_needs_exactly_the_c0_rows(follow_run: Run, tmp_path: Path) -> None:
    run_dir = _copy(follow_run, tmp_path)
    _rewrite_prov(run_dir, exit_reason=drv.REASON_C0_GATE)
    assert gate.run_gate_problems(run_dir) == [f"{N_PLAN} lines != {N_C0} for c0_gate"]


def test_null_rows_are_stopped(follow_run: Run, tmp_path: Path) -> None:
    run_dir = _copy(follow_run, tmp_path)
    lines = _lines(run_dir)
    row = json.loads(lines[-1])
    lines[-1] = json.dumps({**row, "raw": None, "parsed": None})
    _write_lines(run_dir, lines)
    assert gate.run_gate_problems(run_dir) == ["1 transport-failure rows (raw = null)"]


def test_blank_lines_are_not_counted(follow_run: Run, tmp_path: Path) -> None:
    run_dir = _copy(follow_run, tmp_path)
    _write_lines(run_dir, _lines(run_dir), tail="\n\n\n")
    assert gate.run_gate_problems(run_dir) == []


def test_missing_or_unreadable_files_are_stopped(
    follow_run: Run, tmp_path: Path
) -> None:
    run_dir = _copy(follow_run, tmp_path)
    lines = _lines(run_dir)
    lines[5] = "not json"
    _write_lines(run_dir, lines)
    assert gate.run_gate_problems(run_dir) == ["records.jsonl has an unreadable line"]
    (run_dir / "records.jsonl").unlink()
    assert gate.run_gate_problems(run_dir) == ["records.jsonl is missing"]
    (run_dir / "provenance.json").write_text("[]", encoding="utf-8")
    assert gate.run_gate_problems(run_dir) == ["provenance.json is not a JSON object"]
    (run_dir / "provenance.json").unlink()
    assert gate.run_gate_problems(run_dir) == [
        "provenance.json is missing or unreadable"
    ]


def test_expected_endpoint_is_the_driver_default() -> None:
    assert gate.EXPECTED_ENDPOINT == drv.DEFAULT_ENDPOINT
