#!/usr/bin/env python
"""閉ループ分散 pilot — 凍結 manifest の書き出しと照合 (prereg v4 §8).

凍結時に、判定に関わる全ファイルの sha256 を ``manifest.json`` に書く。対象は prereg・v4 の判定コード
(battery・sim・scorer)・判定 CLI・変異 harness・power / fixture 表生成・manifest 検査・import する v2 /
旧 Stage B 資産・evidence の divergence・実測 base の入力 (v2 / v3 の実走記録)・test・certification・
power 表・fixture 表・run.sh・SEED。実走後の判定 (``run.sh``) は v2 manifest の照合に続けてこれを照合し、
1 つでも違えば判定を計算しない。さらに次の整合を照合する:

* certification (``results/v4_mutation.json``) が全 KILLED で、記録 sha256 が現在の 7 ファイルと一致
* power 表 (``results/power_table.json``) の記録 sha256 が現在の 7 ファイルと一致し、選定
  (renderer, R, K, M) が scorer の凍結値と一致
* fixture 表 (``results/fixture_table.json``) の硬い gate が合格で、設計が選定と一致し、記録 sha256 が
  一致し、τ/4 を超えた fixture の一覧が scorer の ``FLAGGED_FIXTURES`` と一致

実行 (repo root から)::

    uv run python scripts/closed_loop_manifest.py --write    # 凍結時のみ
    uv run python scripts/closed_loop_manifest.py --verify
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

from scripts import closed_loop_scorer as sc  # noqa: E402
from scripts import closed_loop_sim as sim  # noqa: E402

EXP = "experiments/20260927-closed-loop-divergence-pilot"
MANIFEST = f"{EXP}/manifest.json"
CERT = f"{EXP}/results/v4_mutation.json"
POWER = f"{EXP}/results/power_table.json"
FIXTURES = f"{EXP}/results/fixture_table.json"
_TESTS = "tests/test_closed_loop"
FROZEN_FILES: tuple[str, ...] = (
    f"{EXP}/prereg.md",
    f"{EXP}/run.sh",
    f"{EXP}/SEED",
    CERT,
    POWER,
    FIXTURES,
    "scripts/closed_loop_scorer.py",
    "scripts/closed_loop_battery.py",
    "scripts/closed_loop_sim.py",
    "scripts/closed_loop_evaluate.py",
    "scripts/closed_loop_mutation_check.py",
    "scripts/closed_loop_power_table.py",
    "scripts/closed_loop_manifest.py",
    "scripts/skill_lever_scorer.py",
    "scripts/skill_lever_battery.py",
    "scripts/stage_b_scorer.py",
    "scripts/stage_b_battery.py",
    "src/erre_sandbox/evidence/es2_replay/divergence.py",
    sim.V2_SAMPLES,
    sim.V3_SAMPLES,
    f"{_TESTS}/__init__.py",
    f"{_TESTS}/conftest.py",
    f"{_TESTS}/test_base_fit.py",
    f"{_TESTS}/test_battery.py",
    f"{_TESTS}/test_fixtures.py",
    f"{_TESTS}/test_manifest.py",
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


def frozen_design() -> dict[str, Any]:
    return {
        "renderer": sc.FROZEN_RENDERER,
        "R": sc.FROZEN_R,
        "K": sc.FROZEN_K,
        "M": sc.FROZEN_M,
    }


def consistency_violations(root: pathlib.Path) -> list[str]:
    """Certification・power 表・fixture 表が現在の判定コードと凍結値に結び付いているか."""
    out: list[str] = []
    now = _certified_now(root)
    try:
        cert: dict[str, Any] = json.loads((root / CERT).read_text(encoding="utf-8"))
        power: dict[str, Any] = json.loads((root / POWER).read_text(encoding="utf-8"))
        fixt: dict[str, Any] = json.loads((root / FIXTURES).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"cannot read certification / power / fixture table: {exc}"]
    if cert.get("all_killed") is not True:
        out.append("certification: not all mutants KILLED")
    if cert.get("target_sha256") != now:
        out.append("certification: recorded sha256 differs from current code")
    if power.get("target_sha256") != now:
        out.append("power table: recorded sha256 differs from current code")
    if power.get("chosen") != frozen_design():
        out.append("power table: chosen design differs from the scorer's frozen values")
    if fixt.get("target_sha256") != now:
        out.append("fixture table: recorded sha256 differs from current code")
    if fixt.get("design") != frozen_design():
        out.append("fixture table: design differs from the scorer's frozen values")
    if fixt.get("gate_ok") is not True:
        out.append("fixture table: positive-side gate not passed")
    if fixt.get("flagged") != list(sc.FLAGGED_FIXTURES):
        out.append(
            "fixture table: flagged fixtures differ from the scorer's claim list"
        )
    # 要約欄を信用せず、rows から gate と列挙を再計算して照合する (Codex 2 回目 MEDIUM)
    try:
        ok, worst, flagged = sim.fixture_gate(fixt["rows"])
    except (KeyError, TypeError, ValueError):
        return [*out, "fixture table: rows cannot be re-evaluated"]
    if not ok or fixt.get("gate_ok") is not ok:
        out.append("fixture table: gate recomputed from rows does not pass")
    if flagged != fixt.get("flagged"):
        out.append("fixture table: flagged recomputed from rows differs")
    if fixt.get("worst_positive") != worst:
        out.append("fixture table: worst_positive differs from the rows")
    if (
        fixt.get("gate_threshold_hard") != sim.FIXTURE_HARD
        or fixt.get("gate_threshold_flag") != sim.FIXTURE_GATE
    ):
        out.append("fixture table: gate thresholds differ from the code")
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
