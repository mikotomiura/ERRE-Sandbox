"""第 2 段の封印 (``manifest_main.json``) が通る一時の root を作る (test 用).

本走の入口 (driver ``plan_for`` の本走の枝・scorer ``compute_verdict``) は root の
``manifest_main.json`` を照合する。test が使う合成の gate・models.json・fixture でも
照合が通るように、一時 dir に次を置く:

* 第 1 段の 13 ファイルと prereg (status 行だけを FROZEN に) を repo から写し、
  ``manifest.json`` は写したファイルから第 1 段の ``build`` で作り直す
* 証明書の対象 (9 対象・harness・本 dir の全 .py・原本の test) を写し、
  **現在のファイルから合成した証明書** を置く (変異の run の中でも整合するので、
  既存の本走の枝の test が封印の不一致という別の理由で落ちない)
* gate・fixture_diffs_main を渡された bytes で置き、
  battery_checks を gate の R で計算する
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
from typing import Any

from scripts import benchmark_stage2_fixtures as fxm
from scripts import benchmark_stage2_manifest as man
from scripts import benchmark_stage2_manifest_main as mm
from scripts import benchmark_stage2_plan as pl

REPO = pathlib.Path(__file__).resolve().parents[2]


def _sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy(rel: str, root: pathlib.Path) -> None:
    dst = root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO / rel, dst)


def fixture_sources() -> list[str]:
    fx = json.loads((REPO / man.FIXTURE_DIFFS).read_text(encoding="utf-8"))
    return sorted(
        r["source"]["path"] for r in fx["batteries"].values() if "sha256" in r["source"]
    )


def chain_seals() -> list[str]:
    """既存の chain の封印 (段 2 の 2 つの manifest は除く)."""
    own = {man.MANIFEST, mm.MANIFEST_MAIN}
    return sorted(
        rel
        for p in REPO.glob("experiments/*/manifest*.json")
        if (rel := p.relative_to(REPO).as_posix()) not in own
    )


def frozen_prereg_text() -> str:
    text = (REPO / man.PREREG).read_text(encoding="utf-8")
    line = man.status_line(text)
    assert line is not None
    return text.replace(line, mm.STATUS_MAIN, 1)


def cert_rels() -> list[str]:
    tests = sorted(
        f"{mm.CERT_TEST_DIR}/{p.name}" for p in (REPO / mm.CERT_TEST_DIR).glob("*.py")
    )
    return [
        *mm.CERT_TARGETS.values(),
        mm.CERT_HARNESS,
        *tests,
        *mm.CERT_WITNESS_EXTRA,
    ]


def synth_certificate(root: pathlib.Path) -> dict[str, Any]:
    target = {
        pathlib.PurePath(rel).name: _sha(root / rel)
        for rel in [*mm.CERT_TARGETS.values(), mm.CERT_HARNESS]
    }
    for p in sorted((root / mm.CERT_TEST_DIR).glob("*.py")):
        target["tests/" + p.name] = _sha(p)
    return {
        "version": mm.CERT_VERSION,
        # 各対象に KILLED の行を 1 つ・meta-test 1 つ (照合は行を数え直す)
        "mutants": [
            {"label": f"x{i:02d}", "target": rel, "status": mm.KILLED}
            for i, rel in enumerate(mm.CERT_TARGETS.values())
        ],
        "meta_test": [{"label": "meta", "status": mm.META_OK}],
        "target_sha256": target,
        "witness_tests_sha256": {
            rel: _sha(root / rel) for rel in mm.CERT_WITNESS_EXTRA
        },
        "inputs_sha256": {mm.GATE: _sha(root / mm.GATE)},
        "targets": dict(mm.CERT_TARGETS),
        "all_killed": True,
    }


def write_json(path: pathlib.Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    path.write_bytes(text.encode("utf-8"))


def build_tree(
    root: pathlib.Path,
    *,
    gate_bytes: bytes,
    models_bytes: bytes,
    fixture_bytes: bytes | None = None,
) -> pathlib.Path:
    """``manifest_main.check`` が通る root を作って返す."""
    for rel in man.FROZEN_FILES:
        _copy(rel, root)
    # 渡された models.json を第 1 段の封印の位置に置く
    (root / mm.MODELS).write_bytes(models_bytes)
    for rel in fixture_sources():  # 見取り図の検査が sha を照合する凍結の fixture 表
        _copy(rel, root)
    (root / man.PREREG).write_bytes(frozen_prereg_text().encode("utf-8"))
    write_json(root / man.MANIFEST, man.build(root))
    for rel in cert_rels():
        _copy(rel, root)
    for rel in sorted(mm.import_closure(REPO) - mm.bound_files()):
        _copy(rel, root)  # 段 2 の外の module (閉じた chain の battery・scorer 等)
    for rel in chain_seals():
        _copy(rel, root)  # 書き手がその module を照合する既存の封印
    gate = root / mm.GATE
    gate.parent.mkdir(parents=True, exist_ok=True)
    gate.write_bytes(gate_bytes)
    if fixture_bytes is None:
        fixture_bytes = fxm.compute_text(gate).encode("utf-8")
    (root / mm.FIXTURE_MAIN).write_bytes(fixture_bytes)
    write_json(root / mm.CERT, synth_certificate(root))
    checks = {b: pl.battery_checks(b, r) for b, r in mm.go_r(gate_bytes).items()}
    rec = mm.build(
        root,
        gate_bytes=gate_bytes,
        models_sha=hashlib.sha256(models_bytes).hexdigest(),
        fixture_bytes=fixture_bytes,
        battery_checks=checks,
        sketch_sha=_sha(root / man.SKETCH),
    )
    write_json(root / mm.MANIFEST_MAIN, rec)
    return root
