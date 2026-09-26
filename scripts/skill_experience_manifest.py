#!/usr/bin/env python
"""経験由来 Skill pilot — 凍結 manifest の書き出しと照合 (prereg v3 §8).

凍結時に、判定に関わる全ファイルの sha256 を ``manifest.json`` に書く。対象は prereg・v3 の判定コード・
判定 CLI・変異 harness・power 表生成・manifest 検査・import する v2 / 旧資産・test・certification・
power 表・run.sh・SEED。実走後の判定 (``run.sh``) は v2 manifest の照合に続けてこれを照合し、1 つでも
違えば判定を計算しない。さらに次の整合を照合する:

* certification (``results/v3_mutation.json``) が全 KILLED で、記録 sha256 が現在の 6 ファイルと一致
* power 表 (``results/power_table.json``) の記録 sha256 が現在の 6 ファイルと一致し、選定 (R, K) が
  scorer の凍結値と一致

実行 (repo root から)::

    uv run python scripts/skill_experience_manifest.py --write    # 凍結時のみ
    uv run python scripts/skill_experience_manifest.py --verify
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

from scripts import skill_experience_scorer as sc  # noqa: E402

EXP = "experiments/20260926-experience-skill-pilot"
MANIFEST = f"{EXP}/manifest.json"
CERT = f"{EXP}/results/v3_mutation.json"
POWER = f"{EXP}/results/power_table.json"
_TESTS = "tests/test_skill_experience"
FROZEN_FILES: tuple[str, ...] = (
    f"{EXP}/prereg.md",
    f"{EXP}/run.sh",
    f"{EXP}/SEED",
    CERT,
    POWER,
    "scripts/skill_experience_scorer.py",
    "scripts/skill_experience_battery.py",
    "scripts/skill_experience_evaluate.py",
    "scripts/skill_experience_mutation_check.py",
    "scripts/skill_experience_power_table.py",
    "scripts/skill_experience_manifest.py",
    "scripts/skill_lever_scorer.py",
    "scripts/skill_lever_battery.py",
    "scripts/stage_b_scorer.py",
    "scripts/stage_b_battery.py",
    f"{_TESTS}/__init__.py",
    f"{_TESTS}/conftest.py",
    f"{_TESTS}/test_battery.py",
    f"{_TESTS}/test_manifest.py",
    f"{_TESTS}/test_nuisance.py",
    f"{_TESTS}/test_power.py",
    f"{_TESTS}/test_scorer.py",
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


def _certified_now(root: pathlib.Path) -> dict[str, str]:
    return {name: sha256(root / "scripts" / name) for name in sc.certified_targets()}


def consistency_violations(root: pathlib.Path) -> list[str]:
    """Certification と power 表が現在の判定コードに結び付いているか."""
    out: list[str] = []
    now = _certified_now(root)
    try:
        cert: dict[str, Any] = json.loads((root / CERT).read_text(encoding="utf-8"))
        power: dict[str, Any] = json.loads((root / POWER).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"cannot read certification / power table: {exc}"]
    if cert.get("all_killed") is not True:
        out.append("certification: not all mutants KILLED")
    if cert.get("target_sha256") != now:
        out.append("certification: recorded sha256 differs from current code")
    if power.get("target_sha256") != now:
        out.append("power table: recorded sha256 differs from current code")
    if power.get("chosen") != {"R": sc.FROZEN_R, "K": sc.FROZEN_K}:
        out.append("power table: chosen (R, K) differs from the scorer's frozen values")
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
