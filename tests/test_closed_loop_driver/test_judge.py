"""判定の単一入口 (DR-7、Codex HIGH).

run gate が落ちた run では凍結 run.sh を呼ばない。
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest
from scripts import closed_loop_judge as judge

if TYPE_CHECKING:
    from pathlib import Path

    from tests.test_closed_loop_driver.test_driver import Run

OK = "[run.sh] repeat byte-identical"


@dataclass
class Calls:
    run_sh_result: tuple[int, str] = (0, OK + "\n")
    run_sh: int = 0
    describe: list[list[str]] = field(default_factory=list)


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> Calls:
    """run.sh と describe を stub に置き換える (実 run.sh は走らせない)."""
    seen = Calls()

    def fake_run_sh() -> tuple[int, str]:
        seen.run_sh += 1
        return seen.run_sh_result

    def fake_describe(argv: list[str]) -> int:
        seen.describe.append(argv)
        return 0

    monkeypatch.setattr(judge, "run_sh", fake_run_sh)
    monkeypatch.setattr(judge.describe, "main", fake_describe)
    return seen


def _copy(run: Run, tmp_path: Path) -> Path:
    dst = tmp_path / "run"
    shutil.copytree(run[0], dst)
    return dst


def test_gate_failure_does_not_call_run_sh(
    follow_run: Run, tmp_path: Path, calls: Calls
) -> None:
    run_dir = _copy(follow_run, tmp_path)
    prov = json.loads((run_dir / "provenance.json").read_text(encoding="utf-8"))
    prov["exit_reason"] = "aborted"
    (run_dir / "provenance.json").write_text(json.dumps(prov), encoding="utf-8")
    assert judge.judge(run_dir) == judge.EXIT_NOT_COMPUTED
    assert calls.run_sh == 0
    assert calls.describe == []


def test_gate_pass_calls_run_sh_then_describe(
    follow_run: Run, tmp_path: Path, calls: Calls
) -> None:
    run_dir = _copy(follow_run, tmp_path)
    assert judge.judge(run_dir) == judge.EXIT_OK
    assert calls.run_sh == 1
    assert len(calls.describe) == 1
    assert str(run_dir / "records.jsonl") in calls.describe[0]


@pytest.mark.parametrize(
    "outcome", [(0, "[run.sh] something else\n"), (1, OK + "\n"), (0, "")]
)
def test_run_sh_must_end_byte_identical(
    follow_run: Run, tmp_path: Path, calls: Calls, outcome: tuple[int, str]
) -> None:
    calls.run_sh_result = outcome
    run_dir = _copy(follow_run, tmp_path)
    assert judge.judge(run_dir) == judge.EXIT_RUN_SH_FAILED
    assert calls.describe == []


def test_run_sh_ok_reads_the_last_line() -> None:
    assert judge.run_sh_ok(0, f"MANIFEST OK\n{OK}\n\n")
    assert not judge.run_sh_ok(0, f"{OK}\nlater line\n")
    assert not judge.run_sh_ok(3, OK)


def test_bash_is_not_wsl_on_windows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Windows では PATH 上の bash (WSL でありうる) より Git Bash を使う."""
    monkeypatch.setenv("BASH", "/custom/bash")
    assert judge.bash_path() == "/custom/bash"
    monkeypatch.delenv("BASH")
    git_bash = tmp_path / "bash.exe"
    git_bash.write_text("", encoding="utf-8")
    wsl = "C:\\Windows\\System32\\bash.exe"
    monkeypatch.setattr(judge, "_GIT_BASH", git_bash)
    monkeypatch.setattr(judge.shutil, "which", lambda _name: wsl)
    monkeypatch.setattr(judge.sys, "platform", "win32")
    assert judge.bash_path() == str(git_bash)
    monkeypatch.setattr(judge.sys, "platform", "linux")
    assert judge.bash_path() == wsl
