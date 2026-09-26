#!/usr/bin/env python
"""経験由来 Skill pilot — 実走の終了状態の gate (判定の前、prereg v3 §5-2 の読み方を機械化)。

凍結 ``run.sh`` / ``skill_experience_evaluate.py`` は driver の来歴 (``provenance.json``) を読まない。そのため
「driver は aborted で終わったが、記録は grid 分揃っている」run でも、run.sh は verdict を出せてしまう
(例: 最後の preflight で digest が変わった、最後の block の対照 arm で非 transport 例外が出た)。
本 gate を run.sh の **前** に通し、落ちたら run.sh を呼ばず not_computed と扱う
(判断記録 ``.steering/20260927-experience-skill-pilot-run/decisions.md`` DE-R5、実データを見る前に commit)。

合格条件 (label は読まない。provenance と行数だけを見る):

* ``provenance.json`` が読める JSON object。
* ``exit_reason`` が ``completed`` または ``c0_gate``。
* ``meta_matches_frozen`` が True (送った全 body の要求条件が凍結値と値・型で一致)。
* driver の sha256 が開始時と終了時で一致し、model digest も開始時と終了時で一致。
* 応答の model 名が凍結 model だけ。
* ``n_samples`` が ``samples.jsonl`` の非空行数と一致。

実行 (repo root から)::

    uv run python scripts/skill_experience_run_gate.py \\
        --run-dir experiments/20260926-experience-skill-pilot/results/run
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

from scripts import skill_lever_battery as v2bat  # noqa: E402

ACCEPTED_EXIT: Final[frozenset[str]] = frozenset({"completed", "c0_gate"})
GATE_OK: Final[str] = "RUN GATE OK"


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
    try:
        text = (run_dir / "samples.jsonl").read_text(encoding="utf-8")
    except OSError:
        return [*problems, "samples.jsonl is missing"]
    n_lines = sum(bool(line.strip()) for line in text.splitlines())
    if prov.get("n_samples") != n_lines:
        problems.append(f"n_samples={prov.get('n_samples')!r} != {n_lines} lines")
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
