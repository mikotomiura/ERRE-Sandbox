"""凍結 manifest (prereg v3 §8).

改変の検出と、判定コードとの結び付き。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from scripts import skill_experience_manifest as man
from scripts import skill_experience_scorer as sc

_ROOT = Path(__file__).resolve().parents[2]


def test_manifest_detects_changed_and_missing_files(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    (tmp_path / "b.txt").write_text("y", encoding="utf-8")
    manifest = man.build_manifest(tmp_path, ("a.txt", "b.txt"))
    assert man.manifest_violations(manifest, tmp_path) == []
    (tmp_path / "a.txt").write_text("x2", encoding="utf-8")
    (tmp_path / "b.txt").unlink()
    got = man.manifest_violations(manifest, tmp_path)
    assert got == [
        "a.txt: sha256 differs from the frozen manifest",
        "b.txt: missing",
    ]


def _fake_root(tmp_path: Path) -> Path:
    for name, src in sc.certified_targets().items():
        dst = tmp_path / "scripts" / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    shas = {n: man.sha256(tmp_path / "scripts" / n) for n in sc.certified_targets()}
    for rel, obj in (
        (man.CERT, {"all_killed": True, "target_sha256": shas}),
        (
            man.POWER,
            {"target_sha256": shas, "chosen": {"R": sc.FROZEN_R, "K": sc.FROZEN_K}},
        ),
    ):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj), encoding="utf-8")
    return tmp_path


def test_consistency_passes_when_bound(tmp_path: Path) -> None:
    assert man.consistency_violations(_fake_root(tmp_path)) == []


def test_consistency_detects_code_changed_after_certification(tmp_path: Path) -> None:
    root = _fake_root(tmp_path)
    scorer = root / "scripts" / "skill_experience_scorer.py"
    scorer.write_text(
        scorer.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8"
    )
    got = man.consistency_violations(root)
    assert "certification: recorded sha256 differs from current code" in got
    assert "power table: recorded sha256 differs from current code" in got


def test_consistency_detects_unkilled_certification(tmp_path: Path) -> None:
    root = _fake_root(tmp_path)
    cert = root / man.CERT
    obj = json.loads(cert.read_text(encoding="utf-8"))
    cert.write_text(json.dumps({**obj, "all_killed": False}), encoding="utf-8")
    assert "certification: not all mutants KILLED" in man.consistency_violations(root)


def test_consistency_detects_power_choice_mismatch(tmp_path: Path) -> None:
    root = _fake_root(tmp_path)
    power = root / man.POWER
    obj = json.loads(power.read_text(encoding="utf-8"))
    power.write_text(
        json.dumps({**obj, "chosen": {"R": 12, "K": 20}}), encoding="utf-8"
    )
    got = man.consistency_violations(root)
    assert "power table: chosen (R, K) differs from the scorer's frozen values" in got


def test_committed_artifacts_are_consistent() -> None:
    """commit 済みの manifest・certification・power 表が現在と一致する (無ければ skip
    でなく fail)."""
    assert (_ROOT / man.MANIFEST).is_file()
    manifest = json.loads((_ROOT / man.MANIFEST).read_text(encoding="utf-8"))
    assert set(manifest) == set(man.FROZEN_FILES)
    assert man.manifest_violations(manifest, _ROOT) == []
    assert man.consistency_violations(_ROOT) == []
