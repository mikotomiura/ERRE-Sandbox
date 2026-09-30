"""凍結 manifest (pilot prereg §8).

改変の検出、certification・見取り図とコードの結び付き、先行凍結物の無変更。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from scripts import body_walk_manifest as man
from scripts import body_walk_mutation_check as mut
from scripts import body_walk_select as sel
from scripts import closed_loop_manifest as v4man
from scripts import closed_loop_v5_manifest as v5man

_ROOT = Path(__file__).resolve().parents[2]
EDIT_MARK = "\n# edited\n"


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
    """凍結条件を満たす certification と見取り図を持つ偽の repository root."""
    for name in sel.CERTIFIED:
        dst = tmp_path / "scripts" / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_ROOT / "scripts" / name, dst)
    for rel in (sel.HARNESS, *(f"{sel.TESTS_DIR}/{n}" for n in sel.tests_sha256())):
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_ROOT / rel, dst)
    shas = sel.certified_sha256(tmp_path)
    cert = {
        "all_killed": True,
        "target_sha256": shas,
        "tests_sha256": sel.tests_sha256(tmp_path),
        "harness_sha256": sel.harness_sha256(tmp_path),
        "mutants": [
            {"label": m.label, "status": "KILLED", "expected_any_of": sorted(m.expect)}
            for m in mut.MUTANTS
        ],
    }
    rows = [
        {
            "s": s,
            "pilot": {"status": "computed"},
            "mapping": {"status": sel.STATUS_CHOSEN if s == 0.0 else "door_close"},
        }
        for s in sel.TABLE_ROWS
    ]
    for rel, obj in (
        (man.CERT, cert),
        (man.TABLE, {"target_sha256": shas, "rows": rows}),
    ):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj), encoding="utf-8")
    return tmp_path


def _edit(root: Path, rel: str, **changes: object) -> None:
    p = root / rel
    obj = json.loads(p.read_text(encoding="utf-8"))
    p.write_text(json.dumps({**obj, **changes}), encoding="utf-8")


def _load(root: Path, rel: str) -> dict[str, Any]:
    return json.loads((root / rel).read_text(encoding="utf-8"))


def test_consistency_passes_when_bound(tmp_path: Path) -> None:
    assert man.consistency_violations(_fake_root(tmp_path)) == []


def test_consistency_detects_code_changed_after_certification(tmp_path: Path) -> None:
    root = _fake_root(tmp_path)
    p = root / "scripts" / "body_walk_sim.py"
    p.write_text(p.read_text(encoding="utf-8") + EDIT_MARK, encoding="utf-8")
    got = man.consistency_violations(root)
    assert "certification: recorded sha256 differs from current code" in got
    assert "decision table: recorded sha256 differs from current code" in got


def test_consistency_detects_changed_tests_and_harness(tmp_path: Path) -> None:
    root = _fake_root(tmp_path)
    for rel in (f"{sel.TESTS_DIR}/test_sim.py", sel.HARNESS):
        p = root / rel
        p.write_text(p.read_text(encoding="utf-8") + EDIT_MARK, encoding="utf-8")
    got = man.consistency_violations(root)
    assert "certification: recorded test sha256 differs from current tests" in got
    assert "certification: recorded harness sha256 differs from current harness" in got


def test_consistency_detects_unkilled_certification(tmp_path: Path) -> None:
    root = _fake_root(tmp_path)
    _edit(root, man.CERT, all_killed=False)
    assert "certification: not all mutants KILLED" in man.consistency_violations(root)
    rows = _load(root, man.CERT)["mutants"]
    rows[3]["status"] = "SURVIVED"
    _edit(root, man.CERT, all_killed=True, mutants=rows)
    assert "certification: a mutant row is not KILLED" in (
        man.consistency_violations(root)
    )


def test_consistency_detects_unregistered_mutant_rows(tmp_path: Path) -> None:
    root = _fake_root(tmp_path)
    rows = _load(root, man.CERT)["mutants"]
    _edit(root, man.CERT, mutants=rows[:-1])
    want = "certification: mutant rows differ from the registered mutants"
    assert want in man.consistency_violations(root)
    rows[0]["expected_any_of"] = ["test_something_else"]
    _edit(root, man.CERT, mutants=rows)
    assert want in man.consistency_violations(root)


def test_consistency_checks_the_decision_table_rows(tmp_path: Path) -> None:
    root = _fake_root(tmp_path)
    rows = _load(root, man.TABLE)["rows"]
    _edit(root, man.TABLE, rows=[])
    assert "decision table: rows differ from TABLE_ROWS" in (
        man.consistency_violations(root)
    )
    trivial = [dict(x, mapping={"status": "door_close"}) for x in rows]
    _edit(root, man.TABLE, rows=trivial)
    assert "decision table: the s = 0 row is door-close (trivially door-close)" in (
        man.consistency_violations(root)
    )
    broken = [dict(rows[0]), dict(rows[1], pilot={"status": "invalid"}), rows[2]]
    _edit(root, man.TABLE, rows=broken)
    assert "decision table: row s=0.5 was not computed and mapped" in (
        man.consistency_violations(root)
    )


def test_certification_gate_of_the_mapping(tmp_path: Path) -> None:
    root = _fake_root(tmp_path)
    assert sel.load_certification(root / man.CERT, root)
    good = _load(root, man.CERT)
    bad_rows = [dict(x) for x in good["mutants"]]
    bad_rows[0]["status"] = "SURVIVED"
    for changes in (
        {"all_killed": False},
        {"mutants": []},
        {"mutants": bad_rows},
        {"mutants": [good["mutants"][0], good["mutants"][0]]},
        {"tests_sha256": {}},
        {"harness_sha256": "0" * 64},
    ):
        _edit(root, man.CERT, **{**good, **changes})
        assert not sel.load_certification(root / man.CERT, root), changes
    assert not sel.load_certification(root / "missing.json", root)
    out = sel.map_run([], "{}", certification=root / "missing.json")
    assert out == {
        "pilot": None,
        "mapping": {"status": sel.STATUS_INVALID_CERT, "chosen": None},
    }


def test_frozen_file_list_covers_imports() -> None:
    names = {Path(f).name for f in man.FROZEN_FILES}
    assert set(sel.CERTIFIED) <= names
    assert {Path(f).name for f in (_ROOT / "tests/test_body_walk").glob("*.py")} <= (
        names
    )


def test_earlier_frozen_registrations_are_unchanged() -> None:
    """v4 と v5 の凍結 manifest は本登録で変わらない."""
    for mod in (v4man, v5man):
        manifest = json.loads((_ROOT / mod.MANIFEST).read_text(encoding="utf-8"))
        assert mod.manifest_violations(manifest, _ROOT) == []


def test_binding_excludes_the_freeze_condition(tmp_path: Path) -> None:
    """結び付きと凍結条件は別に照合する.

    s = 0 の door-close は、結び付きの違反ではない。
    """
    root = _fake_root(tmp_path)
    rows = _load(root, man.TABLE)["rows"]
    trivial = [dict(x, mapping={"status": "door_close"}) for x in rows]
    _edit(root, man.TABLE, rows=trivial)
    assert man.binding_violations(root) == []
    assert man.freeze_violations(_load(root, man.TABLE)) == [man.TRIVIAL_DOOR_CLOSE]
    assert man.TRIVIAL_DOOR_CLOSE in man.consistency_violations(root)
    assert man.freeze_violations({"rows": []}) == [man.TRIVIAL_DOOR_CLOSE]


def test_committed_artifacts_are_bound_and_door_close() -> None:
    """commit 済みの manifest・証拠は現在と結び付き、凍結条件は満たさない.

    2026-09-30 の見取り図では、最も有利な仮想挙動 (s = 0) でも写像が
    door-close だった。user 裁定 DU-4 で door-close を確定し、写像は凍結しない
    (manifest は証拠の記録。run.sh は凍結条件で止まる)。無ければ fail。
    """
    assert (_ROOT / man.MANIFEST).is_file()
    manifest = json.loads((_ROOT / man.MANIFEST).read_text(encoding="utf-8"))
    assert set(manifest) == set(man.FROZEN_FILES)
    assert man.manifest_violations(manifest, _ROOT) == []
    assert man.binding_violations(_ROOT) == []
    table = json.loads((_ROOT / man.TABLE).read_text(encoding="utf-8"))
    assert man.freeze_violations(table) == [man.TRIVIAL_DOOR_CLOSE]
    assert [x["mapping"]["status"] for x in table["rows"]] == [
        sel.STATUS_DOOR_CLOSE
    ] * len(sel.TABLE_ROWS)
