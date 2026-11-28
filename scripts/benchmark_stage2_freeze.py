"""判別性 gate 段 2 — 第 2 段 (stage main) の凍結の書き手 (prereg §J・§K の 4).

- ``--write``: 次をすべて確かめてから ``manifest_main.json`` を排他的に作る (既にあれば書かない)。
  1. 第 1 段の ``manifest.json`` が pilot の凍結の commit (b626962、PR #161) の版と同じ bytes
  2. pilot の ``gate.json`` を driver の読み手で読み、GO の battery の実 R で
     ``plan.battery_checks`` が全部空
  3. 見取り図を certify した stats で一時 dir に再計算し、``results/sketch.json``・
     ``fixture_diffs.json`` と byte 一致 (記録する sha は再計算の出力のもの)
  4. ``fixture_diffs_main.json`` が gate からの再計算と byte 一致 (``fixtures --check`` 相当)
  5. 段 2 の外の module (driver・scorer の import の閉包) が、それぞれ既存の chain の
     封印 (``experiments/*/manifest*.json``) の sha と一致
  6. 書く記録が ``manifest_main.check`` を通る (prereg が FROZEN・第 1 段の封印・証明書 ...)
- ``--verify``: ``manifest_main.violations`` と、battery_checks の再計算が記録と一致することを見て
  ``MANIFEST OK (stage main)`` を出す。

本 module は書き手なので plan・driver・sim・fixtures を import してよい (本走の入口の照合は
``scripts/benchmark_stage2_manifest_main.py``、scorer はそちらだけを import する)。

使い方: ``python -m scripts.benchmark_stage2_freeze --verify``
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Final

from scripts import benchmark_stage2_driver as dr
from scripts import benchmark_stage2_fixtures as fxm
from scripts import benchmark_stage2_manifest as man
from scripts import benchmark_stage2_manifest_main as mm
from scripts import benchmark_stage2_plan as pl

_REPO_ROOT = Path(__file__).resolve().parent.parent
# 第 1 段の manifest.json の sha (pilot の凍結の commit b626962 の版、`git show` で確かめた)
MANIFEST_PILOT_SHA256: Final[str] = (
    "432dc3386579554183b3bd947399f9ca7b9014cbbdd9197c4785d0cb7943c4d6"
)
SEALS_GLOB: Final[str] = "experiments/*/manifest*.json"


def recompute_checks(r_by_battery: dict[str, int]) -> dict[str, dict[str, list[str]]]:
    return {b: pl.battery_checks(b, r) for b, r in sorted(r_by_battery.items())}


def _inputs(root: Path) -> tuple[bytes, str, dict[str, int]]:
    gate_bytes = (root / mm.GATE).read_bytes()
    models_sha = mm.sha256_bytes((root / mm.MODELS).read_bytes())
    gate = dr.read_gate(json.loads(gate_bytes.decode("utf-8")), models_sha)
    return gate_bytes, models_sha, dict(gate.r_by_battery)


def recompute_sketch(root: Path) -> tuple[list[str], str | None]:
    """見取り図を一時 dir に再計算し、凍結の 2 ファイルと byte 比較する.

    返す sha は再計算の出力の ``sketch.json`` のもの (現在のファイルからは取らない)。
    """
    with tempfile.TemporaryDirectory(prefix="bs2_sketch_") as tmp:
        proc = subprocess.run(  # noqa: S603 — 固定の module を同じ interpreter で
            [sys.executable, "-m", "scripts.benchmark_stage2_sim", "--out", tmp],
            cwd=root,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            return [f"sketch: the recomputation failed (exit {proc.returncode})"], None
        out = Path(tmp)
        problems = [
            f"sketch: {Path(rel).name} differs from the recomputation"
            for rel in (man.SKETCH, man.FIXTURE_DIFFS)
            if (out / Path(rel).name).read_bytes() != (root / rel).read_bytes()
        ]
        return problems, mm.sha256_bytes((out / "sketch.json").read_bytes())


def _seal_entries(obj: object) -> list[tuple[str, object]]:
    if isinstance(obj, dict):
        out: list[tuple[str, object]] = []
        for k, v in obj.items():
            if isinstance(v, str) and k.endswith(".py"):
                out.append((k, v))
            out.extend(_seal_entries(v))
        return out
    if isinstance(obj, list):
        return [e for v in obj for e in _seal_entries(v)]
    return []


def external_seal_problems(root: Path) -> list[str]:
    """段 2 の外の module が、既存の chain の封印に記録された sha と一致する (1 つ以上・全部)."""
    seals: dict[str, list[tuple[str, object]]] = {}
    for p in sorted(root.glob(SEALS_GLOB)):
        if p.as_posix().endswith(mm.MANIFEST_MAIN):
            continue  # 本 module が書く記録そのもの
        obj = json.loads(p.read_text(encoding="utf-8"))
        for rel, sha in _seal_entries(obj):
            seals.setdefault(rel, []).append((p.relative_to(root).as_posix(), sha))
    out: list[str] = []
    for rel in mm.external_modules(root):
        cur = mm.sha256_bytes((root / rel).read_bytes())
        found = seals.get(rel, [])
        if not found:
            out.append(f"external modules: {rel} is not in any chain seal")
        out.extend(
            f"external modules: {rel} differs from the seal {m}"
            for m, sha in found
            if sha != cur
        )
    return out


def prepare(
    root: Path, *, pilot_manifest_sha: str = MANIFEST_PILOT_SHA256
) -> tuple[dict[str, Any], list[str]]:
    """書く記録と、書く前の検査の違反."""
    errs: list[str] = []
    if mm.sha256_bytes((root / man.MANIFEST).read_bytes()) != pilot_manifest_sha:
        errs.append("manifest.json: differs from the pilot freeze commit")
    gate_bytes, models_sha, r = _inputs(root)
    checks = recompute_checks(r)
    errs += [
        f"battery_checks: {b} {k}: {v}"
        for b, c in checks.items()
        for k, v in c.items()
        if v
    ]
    sketch_errs, sketch_sha = recompute_sketch(root)
    errs += sketch_errs
    fx = root / mm.FIXTURE_MAIN
    if not fx.is_file():
        errs.append("fixture_diffs_main.json: missing")
        fx_bytes = b""
    else:
        fx_bytes = fx.read_bytes()
        if fxm.compute_text(root / mm.GATE).encode("utf-8") != fx_bytes:
            errs.append("fixture_diffs_main.json: differs from the recomputation")
    errs += external_seal_problems(root)
    rec = mm.build(
        root,
        gate_bytes=gate_bytes,
        models_sha=models_sha,
        fixture_bytes=fx_bytes,
        battery_checks=checks,
        sketch_sha=sketch_sha or "",
    )
    if not errs:
        errs += mm.check(root, rec, gate_bytes=gate_bytes, models_sha=models_sha)
    return rec, errs


def write(root: Path, *, pilot_manifest_sha: str = MANIFEST_PILOT_SHA256) -> list[str]:
    rec, errs = prepare(root, pilot_manifest_sha=pilot_manifest_sha)
    if errs:
        return errs
    body = json.dumps(rec, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    try:  # 排他的作成
        with (root / mm.MANIFEST_MAIN).open("xb") as fh:
            fh.write(body.encode("utf-8"))
    except FileExistsError:
        return ["manifest_main.json: already exists (refusing to overwrite)"]
    return []


def verify(root: Path) -> list[str]:
    gate_bytes, models_sha, r = _inputs(root)
    errs = mm.violations(root, gate_bytes=gate_bytes, models_sha=models_sha)
    if errs:
        return errs
    rec = mm.load(root) or {}
    recorded = {b: e["checks"] for b, e in rec["battery_checks"].items()}
    if recompute_checks(r) != recorded:
        return ["battery_checks: the recomputation differs from the record"]
    return []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--verify", action="store_true")
    args = ap.parse_args(argv)
    root = _REPO_ROOT
    try:
        errs = write(root) if args.write else verify(root)
    except dr.PreflightError as exc:
        errs = [f"gate.json: {exc}"]
    for e in errs:
        print(f"VIOLATION: {e}")  # noqa: T201
    if errs:
        return 1
    print(mm.OK_LINE if args.verify else "MANIFEST WRITTEN (stage main)")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
