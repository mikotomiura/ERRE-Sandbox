"""実走の終了状態の gate (DE-R5) — 判定に進めない run を機械的に止める.

凍結 run.sh は provenance を読まないので、aborted でも記録が揃えば verdict を出せる。
gate が run.sh の前にそれを止めることを、driver の実 run (mock transport) で確かめる。
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import httpx
from scripts import skill_experience_driver as drv
from scripts import skill_experience_run_gate as gate
from scripts.stage_b_scorer import VERDICT_PASS

from tests.test_skill_experience_driver.test_driver import (
    DIGEST,
    N_ALL,
    Ollama,
    _c0_bottom,
    do_run,
    evaluate,
    extract,
    records,
)

if TYPE_CHECKING:
    from pathlib import Path


def _prov(run_dir: Path) -> dict[str, Any]:
    return json.loads((run_dir / "provenance.json").read_text(encoding="utf-8"))


def _rewrite_prov(run_dir: Path, **changes: object) -> None:
    prov = {**_prov(run_dir), **changes}
    (run_dir / "provenance.json").write_text(json.dumps(prov), encoding="utf-8")


def test_completed_run_passes_the_gate(tmp_path: Path) -> None:
    reason, _ = do_run(tmp_path / "run", extract)
    assert reason == drv.REASON_COMPLETED
    assert gate.run_gate_problems(tmp_path / "run") == []
    assert gate.main(["--run-dir", str(tmp_path / "run")]) == 0


def test_c0_gate_stop_passes_the_gate(tmp_path: Path) -> None:
    reason, _ = do_run(tmp_path / "run", _c0_bottom(49))
    assert reason == drv.REASON_C0_GATE
    assert gate.run_gate_problems(tmp_path / "run") == []


def test_aborted_run_with_complete_records_is_stopped(tmp_path: Path) -> None:
    """digest が最後に変わった run: scorer は verdict を出すが gate が止める."""
    ollama = Ollama(extract, digests=(DIGEST, "sha256:" + "1" * 64))
    reason = asyncio.run(
        drv.run(tmp_path / "run", httpx.MockTransport(ollama), backoff_s=0.0)
    )
    assert reason == drv.REASON_ABORTED
    assert len(records(tmp_path / "run")) == N_ALL
    assert evaluate(tmp_path / "run")["verdict"] == VERDICT_PASS  # 凍結 run.sh の出力
    problems = gate.run_gate_problems(tmp_path / "run")
    assert "exit_reason='aborted'" in problems
    assert any("model digest changed" in p for p in problems)
    assert gate.main(["--run-dir", str(tmp_path / "run")]) == 1


def test_missing_or_broken_provenance_is_stopped(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "samples.jsonl").write_text("", encoding="utf-8")
    assert gate.run_gate_problems(run_dir) == [
        "provenance.json is missing or unreadable"
    ]
    (run_dir / "provenance.json").write_text("[1]", encoding="utf-8")
    assert gate.run_gate_problems(run_dir) == ["provenance.json is not a JSON object"]


def test_each_provenance_field_is_checked(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    reason, _ = do_run(run_dir, extract)
    assert reason == drv.REASON_COMPLETED
    good = _prov(run_dir)
    cases: list[tuple[dict[str, object], str]] = [
        ({"exit_reason": "transport_failure"}, "exit_reason"),
        ({"meta_matches_frozen": None}, "meta_matches_frozen"),
        ({"driver_sha256_end": "0" * 64}, "driver sha256"),
        ({"driver_sha256_start": None, "driver_sha256_end": None}, "driver sha256"),
        ({"model_digest_end": None}, "model digest"),
        ({"response_models": ["qwen3:8b", "qwen3:4b"]}, "response_models"),
        ({"response_models": []}, "response_models"),
        ({"n_samples": N_ALL - 1}, "n_samples"),
    ]
    for change, fragment in cases:
        _rewrite_prov(run_dir, **{**good, **change})
        problems = gate.run_gate_problems(run_dir)
        assert len(problems) == 1, (change, problems)
        assert fragment in problems[0]
    _rewrite_prov(run_dir, **good)
    assert gate.run_gate_problems(run_dir) == []


def test_truncated_samples_are_stopped(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    do_run(run_dir, extract)
    lines = (run_dir / "samples.jsonl").read_text(encoding="utf-8").splitlines()
    (run_dir / "samples.jsonl").write_text(
        "\n".join(lines[:-1]) + "\n", encoding="utf-8"
    )
    problems = gate.run_gate_problems(run_dir)
    assert problems == [f"n_samples={N_ALL} != {N_ALL - 1} lines"]
    (run_dir / "samples.jsonl").unlink()
    assert gate.run_gate_problems(run_dir) == ["samples.jsonl is missing"]
