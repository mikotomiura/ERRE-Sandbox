#!/usr/bin/env python
"""閉ループ分散 pilot — 判定の単一入口: run gate → 凍結 run.sh → 記述報告 (DR-7、Codex HIGH)。

凍結 ``run.sh`` は driver の来歴 (``provenance.json``) を読まないので、aborted で終わった run でも記録が
揃えば verdict を出せる。本 script は、run gate (``closed_loop_run_gate.py``) が ``RUN GATE OK`` でなければ
**run.sh を呼ばずに** not_computed として止まる。gate を通った run だけ run.sh (凍結 v2 / v4 manifest の照合
→ 判定を 2 回計算して byte 一致) を実行し、末尾が ``[run.sh] repeat byte-identical`` のときだけ記述報告
(``closed_loop_describe.py``) を書く。凍結 run.sh・evaluate は変えない。

実行 (repo root から、実走の後)::

    uv run python scripts/closed_loop_judge.py
"""

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
from typing import Final

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import closed_loop_describe as describe  # noqa: E402
from scripts import closed_loop_run_gate as gate  # noqa: E402

_EXP_DIR: Final[pathlib.Path] = (
    _REPO_ROOT / "experiments" / "20260927-closed-loop-divergence-pilot"
)
RUN_DIR: Final[pathlib.Path] = _EXP_DIR / "results" / "run"
RUN_SH: Final[str] = "experiments/20260927-closed-loop-divergence-pilot/run.sh"
RUN_SH_OK: Final[str] = "[run.sh] repeat byte-identical"
_GIT_BASH: Final[pathlib.Path] = pathlib.Path("C:/Program Files/Git/bin/bash.exe")

EXIT_OK: Final[int] = 0
EXIT_NOT_COMPUTED: Final[int] = 1
EXIT_RUN_SH_FAILED: Final[int] = 2
EXIT_DESCRIBE_FAILED: Final[int] = 3


def bash_path() -> str:
    """run.sh を実行する bash。Windows では WSL の bash でなく Git Bash (環境変数 BASH で上書き可)."""
    if os.environ.get("BASH"):
        return os.environ["BASH"]
    if sys.platform == "win32" and _GIT_BASH.exists():
        return str(_GIT_BASH)
    return shutil.which("bash") or "bash"


def run_sh() -> tuple[int, str]:
    """凍結 run.sh を実行し、(exit code, stdout+stderr) を返す."""
    proc = subprocess.run(  # noqa: S603
        [bash_path(), RUN_SH],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=dict(os.environ, PYTHONUTF8="1"),
        check=False,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def run_sh_ok(code: int, output: str) -> bool:
    lines = [line for line in output.strip().splitlines() if line.strip()]
    return code == 0 and bool(lines) and RUN_SH_OK in lines[-1]


def judge(run_dir: pathlib.Path = RUN_DIR) -> int:
    problems = gate.run_gate_problems(run_dir)
    if problems:
        for p in problems:
            print(f"[judge] run gate: {p}")
        print("[judge] NOT COMPUTED (run gate failed; run.sh was not called)")
        return EXIT_NOT_COMPUTED
    print(f"[judge] {gate.GATE_OK}")
    code, output = run_sh()
    print(output, end="" if output.endswith("\n") else "\n")
    if not run_sh_ok(code, output):
        print(f"[judge] run.sh did not finish byte-identical (exit {code})")
        return EXIT_RUN_SH_FAILED
    code = describe.main(
        [
            "--records",
            str(run_dir / "records.jsonl"),
            "--results",
            str(run_dir / "results.json"),
            "--run-dir",
            str(run_dir),
            "--out",
            str(run_dir / "describe.json"),
        ]
    )
    if code != 0:
        print(f"[judge] describe failed (exit {code})")
        return EXIT_DESCRIBE_FAILED
    print("[judge] JUDGED")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args(argv)
    return judge()


if __name__ == "__main__":
    sys.exit(main())
