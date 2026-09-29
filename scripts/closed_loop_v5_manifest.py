#!/usr/bin/env python
"""閉ループ v5 前段 — 較正 pilot の凍結 manifest の書き出しと照合 (pilot prereg §8).

凍結時に、写像に関わる全ファイルの sha256 を ``manifest.json`` に書く。対象は prereg・本登録のコード
(battery・pilot scorer・v5 模擬・写像)・manifest 検査・変異 harness・import する凍結物 (v4 battery / sim、
v2 / 旧 Stage B の scorer / battery)・v4 の較正値の入力 (v4 の実走記録)・test・certification・
見取り図・run.sh・SEED。pilot の実走後の写像 (``run.sh``) は、v2・v4 manifest の照合に続けてこれを照合し、
1 つでも違えば写像を計算しない。さらに次の整合を照合する:

* certification (``results/pilot_mutation.json``) が全 KILLED で、記録 sha256 が現在の 10 ファイルと一致
* 見取り図 (``results/decision_table.json``) の記録 sha256 が現在の 10 ファイルと一致

実行 (repo root から)::

    uv run python scripts/closed_loop_v5_manifest.py --write    # 凍結時のみ
    uv run python scripts/closed_loop_v5_manifest.py --verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import closed_loop_v5_select as sel  # noqa: E402

EXP = "experiments/20260928-closed-loop-v5-calibration-pilot"
MANIFEST = f"{EXP}/manifest.json"
CERT = f"{EXP}/results/pilot_mutation.json"
TABLE = f"{EXP}/results/decision_table.json"
_TESTS = "tests/test_closed_loop_v5"
FROZEN_FILES: tuple[str, ...] = (
    f"{EXP}/prereg.md",
    f"{EXP}/run.sh",
    f"{EXP}/SEED",
    CERT,
    TABLE,
    "scripts/closed_loop_v5_battery.py",
    "scripts/closed_loop_v5_pilot_scorer.py",
    "scripts/closed_loop_v5_sim.py",
    "scripts/closed_loop_v5_select.py",
    "scripts/closed_loop_v5_manifest.py",
    "scripts/closed_loop_v5_mutation_check.py",
    "scripts/closed_loop_battery.py",
    "scripts/closed_loop_sim.py",
    "scripts/skill_lever_scorer.py",
    "scripts/skill_lever_battery.py",
    "scripts/stage_b_scorer.py",
    "scripts/stage_b_battery.py",
    sel.V4_RECORDS,
    f"{_TESTS}/__init__.py",
    f"{_TESTS}/conftest.py",
    f"{_TESTS}/test_battery.py",
    f"{_TESTS}/test_scorer.py",
    f"{_TESTS}/test_sim.py",
    f"{_TESTS}/test_select.py",
    f"{_TESTS}/test_manifest.py",
)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest(
    root: pathlib.Path, files: tuple[str, ...] = FROZEN_FILES
) -> dict[str, str]:
    return {f: sha256(root / f) for f in files}


def manifest_violations(manifest: dict[str, str], root: pathlib.Path) -> list[str]:
    out: list[str] = []
    for f, want in manifest.items():
        p = root / f
        if not p.is_file():
            out.append(f"{f}: missing")
        elif sha256(p) != want:
            out.append(f"{f}: sha256 differs from the frozen manifest")
    return out


def consistency_violations(root: pathlib.Path) -> list[str]:
    """Certification と見取り図が現在のコードに結び付いているか."""
    out: list[str] = []
    now = sel.certified_sha256(root)
    try:
        cert: dict[str, Any] = json.loads((root / CERT).read_text(encoding="utf-8"))
        table: dict[str, Any] = json.loads((root / TABLE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"cannot read certification / decision table: {exc}"]
    if cert.get("all_killed") is not True:
        out.append("certification: not all mutants KILLED")
    if cert.get("target_sha256") != now:
        out.append("certification: recorded sha256 differs from current code")
    if table.get("target_sha256") != now:
        out.append("decision table: recorded sha256 differs from current code")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = ap.parse_args(argv)

    problems = consistency_violations(_REPO_ROOT)
    if args.write:
        if problems:
            print("\n".join(f"ERROR: {p}" for p in problems))
            return 1
        path = _REPO_ROOT / MANIFEST
        path.write_text(
            json.dumps(build_manifest(_REPO_ROOT), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"wrote {MANIFEST} ({len(FROZEN_FILES)} files)")
        return 0
    manifest = json.loads((_REPO_ROOT / MANIFEST).read_text(encoding="utf-8"))
    problems = manifest_violations(manifest, _REPO_ROOT) + problems
    if set(manifest) != set(FROZEN_FILES):
        problems.append("manifest file list differs from FROZEN_FILES")
    for p in problems:
        print(f"MISMATCH: {p}")
    print("MANIFEST OK" if not problems else f"MANIFEST MISMATCH ({len(problems)})")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
