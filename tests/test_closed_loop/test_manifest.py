"""凍結 manifest (prereg v4 §8): 改変の検出と、判定コード・凍結値との結び付き."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from scripts import closed_loop_manifest as man
from scripts import closed_loop_scorer as sc
from scripts import closed_loop_sim as sim

_ROOT = Path(__file__).resolve().parents[2]
# fixture 表の rows (F1 だけが τ/4 を超え、硬い gate τ/2 は通る)
_ROWS = [
    {"fixture": "F1_most_label", "mean": 0.08, "se": 0.003},
    {"fixture": "F8_neighbor", "mean": -0.9, "se": 0.001},
    {"fixture": "P_lookup", "mean": 0.9, "se": 0.001},
]


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
    for name, src in sc.certified_targets().items():
        dst = tmp_path / "scripts" / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    shas = {n: man.sha256(tmp_path / "scripts" / n) for n in sc.certified_targets()}
    design = man.frozen_design()
    for rel, obj in (
        (man.CERT, {"all_killed": True, "target_sha256": shas}),
        (man.POWER, {"target_sha256": shas, "chosen": design}),
        (
            man.FIXTURES,
            {
                "target_sha256": shas,
                "design": design,
                "gate_ok": True,
                "flagged": list(sc.FLAGGED_FIXTURES),
                "worst_positive": _ROWS[0],
                "gate_threshold_hard": sim.FIXTURE_HARD,
                "gate_threshold_flag": sim.FIXTURE_GATE,
                "rows": _ROWS,
            },
        ),
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
    sim = root / "scripts" / "closed_loop_sim.py"
    sim.write_text(sim.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
    got = man.consistency_violations(root)
    assert "certification: recorded sha256 differs from current code" in got
    assert "power table: recorded sha256 differs from current code" in got
    assert "fixture table: recorded sha256 differs from current code" in got


def test_consistency_detects_unkilled_certification(tmp_path: Path) -> None:
    root = _fake_root(tmp_path)
    _edit(root, man.CERT, all_killed=False)
    assert "certification: not all mutants KILLED" in man.consistency_violations(root)


def test_consistency_detects_design_mismatch(tmp_path: Path) -> None:
    root = _fake_root(tmp_path)
    _edit(root, man.POWER, chosen={**man.frozen_design(), "M": 3})
    _edit(root, man.FIXTURES, design={**man.frozen_design(), "renderer": "R1"})
    got = man.consistency_violations(root)
    assert "power table: chosen design differs from the scorer's frozen values" in got
    assert "fixture table: design differs from the scorer's frozen values" in got


def test_consistency_detects_failed_fixture_gate(tmp_path: Path) -> None:
    root = _fake_root(tmp_path)
    _edit(root, man.FIXTURES, gate_ok=False)
    assert "fixture table: positive-side gate not passed" in man.consistency_violations(
        root
    )


def test_consistency_detects_flagged_mismatch(tmp_path: Path) -> None:
    root = _fake_root(tmp_path)
    _edit(root, man.FIXTURES, flagged=[])
    got = man.consistency_violations(root)
    assert "fixture table: flagged fixtures differ from the scorer's claim list" in got


def test_consistency_recomputes_gate_from_rows(tmp_path: Path) -> None:
    """要約欄 (gate_ok・flagged) は正しいまま、rows だけを硬い gate 違反に壊す."""
    root = _fake_root(tmp_path)
    bad = [{"fixture": "F1_most_label", "mean": 0.2, "se": 0.0}, *_ROWS[1:]]
    _edit(root, man.FIXTURES, rows=bad)
    got = man.consistency_violations(root)
    assert "fixture table: gate recomputed from rows does not pass" in got
    assert "fixture table: worst_positive differs from the rows" in got


def test_consistency_recomputes_flagged_from_rows(tmp_path: Path) -> None:
    root = _fake_root(tmp_path)
    extra = [*_ROWS, {"fixture": "F3_last_row", "mean": 0.09, "se": 0.0}]
    _edit(root, man.FIXTURES, rows=extra)
    got = man.consistency_violations(root)
    assert "fixture table: flagged recomputed from rows differs" in got


def test_committed_artifacts_are_consistent() -> None:
    """commit 済みの manifest・certification・power / fixture 表が現在と一致する

    (無ければ
    fail).
    """
    assert (_ROOT / man.MANIFEST).is_file()
    manifest = json.loads((_ROOT / man.MANIFEST).read_text(encoding="utf-8"))
    assert set(manifest) == set(man.FROZEN_FILES)
    assert man.manifest_violations(manifest, _ROOT) == []
    assert man.consistency_violations(_ROOT) == []
