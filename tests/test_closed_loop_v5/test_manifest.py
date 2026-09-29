"""凍結 manifest (pilot prereg §8): 改変の検出、certification・
見取り図とコードの結び付き、先行凍結物の無変更.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from scripts import closed_loop_manifest as v4man
from scripts import closed_loop_v5_manifest as man
from scripts import closed_loop_v5_select as sel

_ROOT = Path(__file__).resolve().parents[2]


def test_manifest_detects_changed_and_missing_files(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    (tmp_path / "b.txt").write_text("y", encoding="utf-8")
    manifest = man.build_manifest(tmp_path, ("a.txt", "b.txt"))
    assert man.manifest_violations(manifest, tmp_path) == []
    (tmp_path / "a.txt").write_text("x2", encoding="utf-8")
    (tmp_path / "b.txt").unlink()
    assert man.manifest_violations(manifest, tmp_path) == [
        "a.txt: sha256 differs from the frozen manifest",
        "b.txt: missing",
    ]


def _fake_root(tmp_path: Path) -> Path:
    for name in sel.CERTIFIED:
        dst = tmp_path / "scripts" / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_ROOT / "scripts" / name, dst)
    shas = sel.certified_sha256(tmp_path)
    for rel, obj in (
        (man.CERT, {"all_killed": True, "target_sha256": shas}),
        (man.TABLE, {"target_sha256": shas, "rows": []}),
    ):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj), encoding="utf-8")
    return tmp_path


def _edit(root: Path, rel: str, **changes: object) -> None:
    p = root / rel
    obj = json.loads(p.read_text(encoding="utf-8"))
    p.write_text(json.dumps({**obj, **changes}), encoding="utf-8")


def test_consistency_passes_when_bound(tmp_path: Path) -> None:
    assert man.consistency_violations(_fake_root(tmp_path)) == []


def test_consistency_detects_code_changed_after_certification(tmp_path: Path) -> None:
    root = _fake_root(tmp_path)
    p = root / "scripts" / "closed_loop_v5_sim.py"
    p.write_text(p.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
    got = man.consistency_violations(root)
    assert "certification: recorded sha256 differs from current code" in got
    assert "decision table: recorded sha256 differs from current code" in got


def test_consistency_detects_unkilled_certification(tmp_path: Path) -> None:
    root = _fake_root(tmp_path)
    _edit(root, man.CERT, all_killed=False)
    assert "certification: not all mutants KILLED" in man.consistency_violations(root)


def test_certification_gate_of_the_mapping(tmp_path: Path) -> None:
    root = _fake_root(tmp_path)
    assert sel.load_certification(root / man.CERT, root)
    _edit(root, man.CERT, all_killed=False)
    assert not sel.load_certification(root / man.CERT, root)
    assert not sel.load_certification(root / "missing.json", root)
    out = sel.map_run([], "{}", certification=root / "missing.json")
    assert out["mapping"]["status"] == sel.STATUS_INVALID_CERT


def test_frozen_file_list_covers_imports() -> None:
    names = {Path(f).name for f in man.FROZEN_FILES}
    assert set(sel.CERTIFIED) <= names
    assert {
        Path(f).name for f in (_ROOT / "tests/test_closed_loop_v5").glob("*.py")
    } <= names


def test_earlier_frozen_registrations_are_unchanged() -> None:
    """v4 (と v4 が照合する v2 の資産) の凍結 manifest は本登録で変わらない."""
    manifest = json.loads((_ROOT / v4man.MANIFEST).read_text(encoding="utf-8"))
    assert v4man.manifest_violations(manifest, _ROOT) == []


def test_committed_artifacts_are_consistent() -> None:
    """commit 済みの manifest・certification・見取り図が現在と一致する.

    無ければ fail。
    """
    assert (_ROOT / man.MANIFEST).is_file()
    manifest = json.loads((_ROOT / man.MANIFEST).read_text(encoding="utf-8"))
    assert set(manifest) == set(man.FROZEN_FILES)
    assert man.manifest_violations(manifest, _ROOT) == []
    assert man.consistency_violations(_ROOT) == []
