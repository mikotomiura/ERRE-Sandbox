#!/usr/bin/env python
"""閉ループ分散 pilot — 実走の終了状態の gate (判定の前、v3 DE-R5 を継承)。

凍結 ``run.sh`` / ``closed_loop_evaluate.py`` は driver の来歴 (``provenance.json``) を読まない。そのため
「driver は aborted で終わったが、記録は揃っている」run でも、run.sh は verdict を出せてしまう。本 gate を
run.sh の **前** に通し、落ちたら run.sh を呼ばず not_computed と扱う (判断記録
``.steering/20260928-closed-loop-pilot-run/decisions.md``、実データを見る前に commit)。

合格条件 (label は読まない。provenance と行の構造だけを見る):

* ``provenance.json`` が読める JSON object。
* ``exit_reason`` が ``completed`` または ``c0_gate``。
* ``meta_matches_frozen`` が True。
* driver の sha256 と model digest が、開始時と終了時で一致。
* 応答の model 名が凍結 model だけ。
* ``n_records`` が ``records.jsonl`` の非空行数と一致し、その行数が終了理由の期待値
  (completed = 凍結 plan の全件、c0_gate = C0 の全件) と一致。
* raw が null の行 (transport 失敗) が無い。
* ``endpoint`` が既定の local Ollama (driver の ``main`` は endpoint を取らない、DR-7)。

実行 (repo root から)::

    uv run python scripts/closed_loop_run_gate.py \\
        --run-dir experiments/20260927-closed-loop-divergence-pilot/results/run
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Final

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import closed_loop_scorer as sc  # noqa: E402
from scripts import skill_lever_battery as v2bat  # noqa: E402

ACCEPTED_EXIT: Final[frozenset[str]] = frozenset({"completed", "c0_gate"})
GATE_OK: Final[str] = "RUN GATE OK"
EXPECTED_ENDPOINT: Final[str] = "http://127.0.0.1:11434"


def expected_lines(exit_reason: object) -> int | None:
    """終了理由ごとの行数。completed = 凍結 plan の全件、c0_gate = C0 の全件."""
    if exit_reason == "completed":
        return len(sc.frozen_plan())
    if exit_reason == "c0_gate":
        return sc.n_c0()
    return None


def run_gate_problems(run_dir: pathlib.Path) -> list[str]:
    """空なら判定に進んでよい。1 つでもあれば not_computed (verdict を書かない)."""
    try:
        prov = json.loads((run_dir / "provenance.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["provenance.json is missing or unreadable"]
    if not isinstance(prov, dict):
        return ["provenance.json is not a JSON object"]
    problems: list[str] = []
    if prov.get("exit_reason") not in ACCEPTED_EXIT:
        problems.append(f"exit_reason={prov.get('exit_reason')!r}")
    if prov.get("meta_matches_frozen") is not True:
        problems.append(f"meta_matches_frozen={prov.get('meta_matches_frozen')!r}")
    start, end = prov.get("driver_sha256_start"), prov.get("driver_sha256_end")
    if not start or start != end:
        problems.append("driver sha256 changed during the run (or missing)")
    d_start, d_end = prov.get("model_digest_start"), prov.get("model_digest_end")
    if not d_start or d_start != d_end:
        problems.append("model digest changed during the run (or missing)")
    if prov.get("response_models") != [v2bat.MODEL]:
        problems.append(f"response_models={prov.get('response_models')!r}")
    if prov.get("endpoint") != EXPECTED_ENDPOINT:
        problems.append(f"endpoint={prov.get('endpoint')!r}")
    try:
        text = (run_dir / "records.jsonl").read_text(encoding="utf-8")
    except OSError:
        return [*problems, "records.jsonl is missing"]
    lines = [line for line in text.splitlines() if line.strip()]
    n_lines = len(lines)
    if prov.get("n_records") != n_lines:
        problems.append(f"n_records={prov.get('n_records')!r} != {n_lines} lines")
    want = expected_lines(prov.get("exit_reason"))
    if want is not None and n_lines != want:
        problems.append(f"{n_lines} lines != {want} for {prov.get('exit_reason')}")
    try:
        n_null = sum(json.loads(line).get("raw") is None for line in lines)
    except (ValueError, AttributeError):
        return [*problems, "records.jsonl has an unreadable line"]
    if n_null:
        problems.append(f"{n_null} transport-failure rows (raw = null)")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=pathlib.Path, required=True)
    args = ap.parse_args(argv)
    problems = run_gate_problems(args.run_dir)
    for p in problems:
        print(f"[run-gate] {p}")
    print(GATE_OK if not problems else f"RUN GATE FAILED ({len(problems)})")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
