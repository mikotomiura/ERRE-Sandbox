"""判別性 gate 段 2 — 第 1 段 (stage pilot) の封印の write / verify (prereg §J・§K)。

- ``--write --stage pilot``: 対象の sha256 と、status 行を正規化した prereg の sha256 を
  ``manifest.json`` に書く。prereg の status が PILOT-FROZEN でなければ書かない。
- ``--verify --stage pilot``: sha256 の一致・status・見取り図の結論 (door-close でない・size 合格)・
  fixture の差の点検の入力 (凍結 dir の fixture 表) の sha256 を照合し、``MANIFEST OK (stage pilot)`` を出す。
- 第 2 段 (stage main) はこの module の範囲外 (次のタスクで、本 manifest を照合する形で足す)。

使い方: ``python -m scripts.benchmark_stage2_manifest --verify --stage pilot``
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent

EXP: Final[str] = "experiments/20261126-benchmark-stage2-discriminability"
MANIFEST: Final[str] = f"{EXP}/manifest.json"
PREREG: Final[str] = f"{EXP}/prereg.md"
SKETCH: Final[str] = f"{EXP}/results/sketch.json"
FIXTURE_DIFFS: Final[str] = f"{EXP}/results/fixture_diffs.json"
FROZEN_FILES: Final[tuple[str, ...]] = (
    f"{EXP}/run.sh",
    f"{EXP}/results/models.json",
    SKETCH,
    FIXTURE_DIFFS,
    "scripts/benchmark_stage2_stats.py",
    "scripts/benchmark_stage2_sim.py",
    "scripts/benchmark_stage2_manifest.py",
    # stats が実行時に読む段 1 の秒の表と chi2_ppf (Codex r1 MEDIUM-5)
    "scripts/benchmark_stage1_reanalysis.py",
    "tests/test_benchmark_stage2/__init__.py",
    "tests/test_benchmark_stage2/conftest.py",
    "tests/test_benchmark_stage2/test_stats.py",
    "tests/test_benchmark_stage2/test_sim.py",
    "tests/test_benchmark_stage2/test_manifest.py",
)
STATUS_PREFIX: Final[str] = "- status: "
STATUS_PILOT: Final[str] = "- status: **PILOT-FROZEN**"
OK_LINE: Final[str] = "MANIFEST OK (stage pilot)"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prereg_body_sha256(text: str) -> str:
    """最初の status 行を正規化した sha256 (第 2 段で status 行だけの変更を許す)."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith(STATUS_PREFIX):
            lines[i] = STATUS_PREFIX + "<SEALED>"
            break
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def status_line(text: str) -> str | None:
    return next((ln for ln in text.split("\n") if ln.startswith(STATUS_PREFIX)), None)


def build(root: Path) -> dict[str, Any]:
    text = (root / PREREG).read_text(encoding="utf-8")
    return {
        "stage": "pilot",
        "files": {f: sha256(root / f) for f in FROZEN_FILES},
        "prereg_sha256": sha256(root / PREREG),
        "prereg_body_sha256": prereg_body_sha256(text),
    }


def sketch_violations(root: Path) -> list[str]:
    out = []
    sk = json.loads((root / SKETCH).read_text(encoding="utf-8"))
    if sk.get("door_close_any") is not False:
        out.append("sketch: door-close (the most favorable row misses power 0.8)")
    if sk.get("size_ok") is not True:
        out.append("sketch: a branch size exceeds the MC acceptance")
    fx = json.loads((root / FIXTURE_DIFFS).read_text(encoding="utf-8"))
    for name, row in fx["batteries"].items():
        src = row["source"]
        if "sha256" in src and sha256(root / src["path"]) != src["sha256"]:
            out.append(f"fixture_diffs: {name} source differs from the frozen table")
    return out


def violations(root: Path, manifest: dict[str, Any]) -> list[str]:
    out = []
    text = (root / PREREG).read_text(encoding="utf-8")
    if status_line(text) != STATUS_PILOT:
        out.append("prereg: status is not PILOT-FROZEN")
    if manifest.get("stage") != "pilot":
        out.append("manifest: stage is not pilot")
    files = manifest.get("files", {})
    if set(files) != set(FROZEN_FILES):
        out.append("manifest: the frozen file set differs")
    for f, want in files.items():
        p = root / f
        if not p.is_file():
            out.append(f"{f}: missing")
        elif sha256(p) != want:
            out.append(f"{f}: sha256 differs")
    if manifest.get("prereg_sha256") != sha256(root / PREREG):
        out.append("prereg: sha256 differs")
    if manifest.get("prereg_body_sha256") != prereg_body_sha256(text):
        out.append("prereg: body differs")
    out.extend(sketch_violations(root))
    return out


def write_manifest(root: Path) -> list[str]:
    text = (root / PREREG).read_text(encoding="utf-8")
    if status_line(text) != STATUS_PILOT:
        return ["prereg: status is not PILOT-FROZEN"]
    pre = sketch_violations(root)
    if pre:
        return pre
    body = json.dumps(build(root), ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    (root / MANIFEST).write_bytes(body.encode("utf-8"))
    return []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--verify", action="store_true")
    ap.add_argument("--stage", choices=("pilot",), required=True)
    ap.add_argument("--root", type=Path, default=_REPO_ROOT)
    args = ap.parse_args(argv)
    if args.write:
        errs = write_manifest(args.root)
    else:
        path = args.root / MANIFEST
        if not path.is_file():
            errs = ["manifest.json: missing"]
        else:
            errs = violations(args.root, json.loads(path.read_text(encoding="utf-8")))
    for e in errs:
        print(f"VIOLATION: {e}")
    if errs:
        return 1
    print(OK_LINE if args.verify else "MANIFEST WRITTEN (stage pilot)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
