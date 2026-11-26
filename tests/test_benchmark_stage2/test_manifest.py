"""判別性 gate 段 2 の第 1 段の manifest (prereg §J・§K).

改変・status・見取り図の結論の検出。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from scripts import benchmark_stage2_manifest as man

_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    files = [*man.FROZEN_FILES, man.PREREG]
    fx = json.loads((_REPO_ROOT / man.FIXTURE_DIFFS).read_text(encoding="utf-8"))
    files += [
        r["source"]["path"] for r in fx["batteries"].values() if "sha256" in r["source"]
    ]
    for f in files:
        dst = tmp_path / f
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_REPO_ROOT / f, dst)
    p = tmp_path / man.PREREG
    lines = p.read_text(encoding="utf-8").split("\n")
    for i, ln in enumerate(lines):
        if ln.startswith(man.STATUS_PREFIX):
            lines[i] = man.STATUS_PILOT
            break
    p.write_bytes("\n".join(lines).encode("utf-8"))
    assert man.write_manifest(tmp_path) == []
    return tmp_path


def _verify(root: Path) -> list[str]:
    return man.violations(
        root, json.loads((root / man.MANIFEST).read_text(encoding="utf-8"))
    )


def test_roundtrip_ok(tree: Path) -> None:
    assert _verify(tree) == []
    assert man.main(["--verify", "--stage", "pilot", "--root", str(tree)]) == 0


def test_detects_tampered_file(tree: Path) -> None:
    p = tree / "scripts/benchmark_stage2_stats.py"
    p.write_bytes(p.read_bytes() + b"\n")
    assert "scripts/benchmark_stage2_stats.py: sha256 differs" in _verify(tree)


def test_detects_prereg_body_change(tree: Path) -> None:
    p = tree / man.PREREG
    p.write_bytes(p.read_bytes() + b"x")
    errs = _verify(tree)
    assert "prereg: body differs" in errs
    assert "prereg: sha256 differs" in errs


def test_status_only_change_keeps_body(tree: Path) -> None:
    text = (tree / man.PREREG).read_text(encoding="utf-8")
    other = text.replace(man.STATUS_PILOT, "- status: **FROZEN**", 1)
    assert man.prereg_body_sha256(other) == man.prereg_body_sha256(text)
    (tree / man.PREREG).write_bytes(other.encode("utf-8"))
    errs = _verify(tree)
    assert "prereg: status is not PILOT-FROZEN" in errs
    assert "prereg: body differs" not in errs


def test_refuses_draft(tree: Path) -> None:
    p = tree / man.PREREG
    p.write_bytes(
        p.read_bytes().replace(man.STATUS_PILOT.encode(), b"- status: DRAFT", 1)
    )
    assert man.write_manifest(tree) == ["prereg: status is not PILOT-FROZEN"]


def test_detects_door_close_sketch(tree: Path) -> None:
    p = tree / man.SKETCH
    sk = json.loads(p.read_text(encoding="utf-8"))
    sk["door_close_any"] = True
    p.write_bytes(json.dumps(sk).encode("utf-8"))
    errs = _verify(tree)
    assert any("door-close" in e for e in errs)


def test_detects_fixture_source_change(tree: Path) -> None:
    fx = json.loads((tree / man.FIXTURE_DIFFS).read_text(encoding="utf-8"))
    src = tree / fx["batteries"]["G"]["source"]["path"]
    src.write_bytes(src.read_bytes() + b" ")
    assert "fixture_diffs: G source differs from the frozen table" in _verify(tree)


def test_detects_missing_and_extra_files(tree: Path) -> None:
    m = json.loads((tree / man.MANIFEST).read_text(encoding="utf-8"))
    m["files"]["extra.txt"] = "0" * 64
    errs = man.violations(tree, m)
    assert "manifest: the frozen file set differs" in errs
    assert "extra.txt: missing" in errs


def test_missing_manifest(tmp_path: Path) -> None:
    assert man.main(["--verify", "--stage", "pilot", "--root", str(tmp_path)]) == 1
