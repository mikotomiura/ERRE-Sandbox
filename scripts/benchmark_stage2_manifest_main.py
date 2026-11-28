"""判別性 gate 段 2 — 第 2 段 (stage main) の封印 ``manifest_main.json`` の照合 (DD-12 H2).

本走の入口 (driver の送信前・scorer の判定前) がこの module の ``require`` を呼ぶ。
検査 (``check``、違反の文の先頭の語が検査の対象を表す):

1. ``stage == "main"``・prereg の status 行が FROZEN・prereg の全体の sha が記録と一致
2. 第 1 段の封印: ``manifest.json`` の sha が記録と一致し、その ``files`` (13 件) の sha が
   現在と一致、``prereg_body_sha256`` (status 行を正規化した本文) が一致、
   見取り図の結論 (``man.sketch_violations``)
3. 証明書 (本走前の certification、version ``pre_main``): sha が記録と一致・変異の行を
   数え直して全 KILLED (各対象に 1 件以上)・meta-test が全部成立・対象が 9 module・
   ``target_sha256`` / ``witness_tests_sha256`` / ``inputs_sha256`` が root の現在の
   ファイルと一致 (段 2 のコードと test の束縛は証明書を根にし、sha を二重に持たない)
4. gate: 渡された bytes の sha = 記録 = 証明書の ``inputs_sha256`` = root の gate.json
5. models.json: 渡された sha = 記録 = 第 1 段の ``files`` の models.json
6. ``fixture_diffs_main.json``: sha が記録と一致 (scorer は自分が読んだ bytes を渡す)
7. 見取り図: 記録 (書き手が再計算した出力の sha) = 現在の ``results/sketch.json``
8. ``battery_checks``: 記録の R が gate の GO の battery の R と一致し、項目の名前の集合が
   登録どおりで、全項目が空リスト
9. 段 2 の外の module: driver・scorer から import で届く ``scripts/`` の module のうち
   証明書と第 1 段が束ねないもの (閉じた chain の battery・scorer 等) の集合と sha が記録と一致
   (書き手は、各 module が既存の chain の封印の sha と一致することを確かめてから記録する)

本 module は plan・driver・harness を import しない (scorer が import する。AST の test)。
書き手 (再計算と排他的作成) は ``scripts/benchmark_stage2_freeze.py``。
第 1 段の ``scripts/benchmark_stage2_manifest.py`` は封印済みなので、関数を import するだけ。
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Final

from scripts import benchmark_stage2_manifest as man
from scripts import benchmark_stage2_stats as st

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent

EXP: Final[str] = man.EXP
MANIFEST_MAIN: Final[str] = f"{EXP}/manifest_main.json"
GATE: Final[str] = f"{EXP}/results/pilot/gate.json"
MODELS: Final[str] = f"{EXP}/results/models.json"
FIXTURE_MAIN: Final[str] = f"{EXP}/results/fixture_diffs_main.json"
CERT: Final[str] = (
    "experiments/20261126-benchmark-stage2-driver/results/driver_mutation.json"
)
CERT_VERSION: Final[str] = "pre_main"
# 証明書の対象 (harness の ``_TARGETS``。harness を import しないので写す。一致は test が見る)
CERT_TARGETS: Final[dict[str, str]] = {
    "driver": "scripts/benchmark_stage2_driver.py",
    "plan": "scripts/benchmark_stage2_plan.py",
    "units": "scripts/benchmark_stage2_units.py",
    "records": "scripts/benchmark_stage2_records.py",
    "pilot_gate": "scripts/benchmark_stage2_pilot_gate.py",
    "stats": "scripts/benchmark_stage2_stats.py",
    "fixtures": "scripts/benchmark_stage2_fixtures.py",
    "scorer": "scripts/benchmark_stage2_scorer.py",
    "manifest_main": "scripts/benchmark_stage2_manifest_main.py",
}
CERT_HARNESS: Final[str] = "scripts/benchmark_stage2_driver_mutation_check.py"
CERT_TEST_DIR: Final[str] = "tests/test_benchmark_stage2_driver"
CERT_WITNESS_EXTRA: Final[tuple[str, ...]] = (
    "tests/test_benchmark_stage2/test_stats.py",
    "tests/test_skill_lever/test_scorer.py",
    "tests/test_skill_experience/test_nuisance.py",
)
KILLED: Final[str] = "KILLED"
META_OK: Final[str] = "FAILED_AS_EXPECTED"
# 本走の入口 (import の閉包の根)
ENTRY_MODULES: Final[tuple[str, ...]] = (
    "scripts/benchmark_stage2_driver.py",
    "scripts/benchmark_stage2_scorer.py",
)

# 8. battery_checks の項目の名前 (plan ``battery_checks`` の出力。plan を import しないので写す。一致は test)
_CHECK_ITEMS: Final[dict[str, tuple[str, ...]]] = {
    "v2": (
        "label_balance",
        "non_leakage",
        "pointed_bijection",
        "position_balance",
        "prompt_budget",
        "r_range",
        "shared_layout",
    ),
    "v3": (
        "control_construction",
        "control_family",
        "family_identity",
        "non_leakage",
        "outcome_balance",
        "pointed_bijection",
        "position_balance",
        "prompt_budget",
        "r_range",
        "shared_layout",
        "trial_sharing",
    ),
    "G": (
        "dev_design",
        "know_balance",
        "label_frequency",
        "masked_states",
        "non_leakage",
        "pointed",
        "position_balance",
        "probe_keys_absent",
        "prompt_budget",
        "r_range",
        "selection_layout_separate",
        "shared_within_family",
        "state_tables",
        "surface_overlap",
        "triple_prompts_differ_only_in_key",
        "triples",
    ),
    "O_time": (
        "layer1",
        "layer2",
        "m0_states",
        "masked_states",
        "multiset",
        "non_leakage",
        "position_balance",
        "prompt_budget",
        "r_range",
        "rules",
        "state_tables",
        "tags",
        "vocabulary",
    ),
}
_AUX_BATTERIES: Final[frozenset[str]] = frozenset({"G", "O_time"})


def check_keys(battery: str) -> frozenset[str]:
    """本走の R を与えた ``battery_checks`` の項目の名前の集合 (登録)."""
    keys = {
        f"{stage}:{k}" for stage in ("pilot", "main") for k in _CHECK_ITEMS[battery]
    }
    keys |= {"seed_namespaces", "prompt_budget_sent"}
    if battery in _AUX_BATTERIES:
        keys |= {"pilot_aux:r_range", "pilot_aux:position_balance"}
    return frozenset(keys)


STAGE: Final[str] = "main"
STATUS_MAIN: Final[str] = "- status: **FROZEN**"
OK_LINE: Final[str] = "MANIFEST OK (stage main)"


class ManifestError(RuntimeError):
    """``manifest_main.json`` の照合が通らない (本走の送信・判定をしない)."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(root: Path, rel: str) -> str | None:
    p = root / rel
    return sha256_bytes(p.read_bytes()) if p.is_file() else None


def _same(want: object, got: object) -> bool:
    """両方が在って等しい (片方が無い None・null は常に違反)."""
    return want is not None and got is not None and want == got


def go_r(gate_bytes: bytes) -> dict[str, int]:
    """GO の battery の R (gate.json から。gate の契約の検査は driver・scorer の読み手)."""
    gate = json.loads(gate_bytes.decode("utf-8"))
    return {
        b: e["R"] for b, e in gate["batteries"].items() if e.get("gate") == st.GATE_GO
    }


# ------------------------------------------------------------ 9. import の閉包


def _imported(root: Path, rel: str) -> set[str]:
    """``rel`` が import する ``scripts/`` の module (関数の中の import も数える)."""
    tree = ast.parse((root / rel).read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "scripts":
            out.update(f"scripts/{a.name}.py" for a in node.names)
        elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "scripts."
        ):
            out.add(str(node.module).replace(".", "/") + ".py")
        elif isinstance(node, ast.Import):
            out.update(
                a.name.replace(".", "/") + ".py"
                for a in node.names
                if a.name.startswith("scripts.")
            )
    return out


def import_closure(root: Path, entries: tuple[str, ...] = ENTRY_MODULES) -> set[str]:
    """入口から import で届く ``scripts/`` の module の全体 (入口を含む)."""
    seen: set[str] = set()
    todo = list(entries)
    while todo:
        rel = todo.pop()
        if rel in seen or not (root / rel).is_file():
            continue
        seen.add(rel)
        todo.extend(_imported(root, rel) - seen)
    return seen


def bound_files() -> frozenset[str]:
    """証明書と第 1 段が既に束ねる module."""
    return frozenset({*CERT_TARGETS.values(), CERT_HARNESS, *man.FROZEN_FILES})


def external_modules(root: Path) -> list[str]:
    return sorted(import_closure(root) - bound_files())


def build(
    root: Path,
    *,
    gate_bytes: bytes,
    models_sha: str,
    fixture_bytes: bytes,
    battery_checks: dict[str, dict[str, list[str]]],
    sketch_sha: str,
) -> dict[str, Any]:
    """記録の中身 (純粋。書き出しと、書く前の再計算は freeze module)."""
    r = go_r(gate_bytes)
    return {
        "stage": STAGE,
        "prereg_sha256": _sha_file(root, man.PREREG),
        "manifest_pilot_sha256": _sha_file(root, man.MANIFEST),
        "certificate_sha256": _sha_file(root, CERT),
        "gate_sha256": sha256_bytes(gate_bytes),
        "models_json_sha256": models_sha,
        "fixture_diffs_main_sha256": sha256_bytes(fixture_bytes),
        "sketch_sha256": sketch_sha,
        "battery_checks": {
            b: {"R": r[b], "checks": battery_checks[b]} for b in sorted(r)
        },
        "external_sha256": {
            rel: _sha_file(root, rel) for rel in external_modules(root)
        },
    }


# ------------------------------------------------------------ 検査


def _stage1_violations(root: Path, rec: dict[str, Any], models_sha: str) -> list[str]:
    sha = _sha_file(root, man.MANIFEST)
    if sha is None:
        return ["manifest.json: missing"]
    if not _same(rec.get("manifest_pilot_sha256"), sha):
        return ["manifest.json: sha256 differs from the record"]
    stage1 = json.loads((root / man.MANIFEST).read_text(encoding="utf-8"))
    files = stage1.get("files", {})
    out: list[str] = []
    if set(files) != set(man.FROZEN_FILES):
        out.append("manifest.json: the frozen file set differs")
    out.extend(
        f"{f}: sha256 differs from manifest.json"
        for f in man.FROZEN_FILES
        if not _same(_sha_file(root, f), files.get(f))
    )
    text = (root / man.PREREG).read_text(encoding="utf-8")
    if not _same(stage1.get("prereg_body_sha256"), man.prereg_body_sha256(text)):
        out.append(
            "prereg: body differs from manifest.json (only the status line may change)"
        )
    # 5. 渡された models.json は第 1 段が封印した models.json
    if not _same(files.get(MODELS), models_sha):
        out.append("models.json: sha256 differs from manifest.json")
    if not out:
        out.extend(man.sketch_violations(root))
    return out


def _mutant_violations(cert: dict[str, Any]) -> list[str]:
    """証明書の自己申告 (all_killed) でなく、行を数え直す."""
    out: list[str] = []
    if cert.get("all_killed") is not True:
        out.append("certificate: not all killed")
    rows = cert.get("mutants")
    if not isinstance(rows, list) or not rows:
        return [*out, "certificate: no mutant rows"]
    if any(not isinstance(r, dict) or r.get("status") != KILLED for r in rows):
        out.append("certificate: a mutant row is not KILLED")
    covered = {r.get("target") for r in rows if isinstance(r, dict)}
    if not set(CERT_TARGETS.values()) <= covered:
        out.append("certificate: a target has no mutant")
    meta = cert.get("meta_test")
    if (
        not isinstance(meta, list)
        or not meta
        or any(not isinstance(m, dict) or m.get("status") != META_OK for m in meta)
    ):
        out.append("certificate: the meta-test did not hold")
    return out


def _cert_violations(root: Path, rec: dict[str, Any], gate_sha: str) -> list[str]:
    sha = _sha_file(root, CERT)
    if sha is None:
        return ["certificate: missing"]
    if not _same(rec.get("certificate_sha256"), sha):
        return ["certificate: sha256 differs from the record"]
    cert = json.loads((root / CERT).read_text(encoding="utf-8"))
    out: list[str] = []
    if cert.get("version") != CERT_VERSION:
        out.append("certificate: version is not pre_main")
    out.extend(_mutant_violations(cert))
    if cert.get("targets") != CERT_TARGETS:
        out.append("certificate: targets differ (manifest_main must be a target)")
    want: dict[str, str | None] = {
        Path(rel).name: _sha_file(root, rel)
        for rel in [*CERT_TARGETS.values(), CERT_HARNESS]
    }
    for p in sorted((root / CERT_TEST_DIR).glob("*.py")):
        want["tests/" + p.name] = _sha_file(root, f"{CERT_TEST_DIR}/{p.name}")
    got = cert.get("target_sha256")
    if not isinstance(got, dict) or set(got) != set(want):
        out.append("certificate: target_sha256 covers a different file set")
    else:
        out.extend(
            f"certificate: {k} differs from the current file"
            for k in sorted(want)
            if not _same(got.get(k), want[k])
        )
    wit = cert.get("witness_tests_sha256")
    if not isinstance(wit, dict) or set(wit) != set(CERT_WITNESS_EXTRA):
        out.append("certificate: witness_tests_sha256 covers a different file set")
    else:
        out.extend(
            f"certificate: {rel} differs from the current file"
            for rel in CERT_WITNESS_EXTRA
            if not _same(wit.get(rel), _sha_file(root, rel))
        )
    inputs = cert.get("inputs_sha256")
    if not isinstance(inputs, dict) or set(inputs) != {GATE}:
        out.append("certificate: inputs_sha256 covers a different file set")
    elif not _same(inputs.get(GATE), _sha_file(root, GATE)):
        out.append("certificate: inputs_sha256 differs from the current gate.json")
    elif not _same(inputs.get(GATE), gate_sha):
        out.append("gate.json: the passed gate differs from the certified gate")
    return out


def _battery_check_violations(rec: dict[str, Any], gate_bytes: bytes) -> list[str]:
    bc = rec.get("battery_checks")
    if not isinstance(bc, dict) or not all(isinstance(e, dict) for e in bc.values()):
        return ["battery_checks: missing or malformed"]
    out: list[str] = []
    if {b: e.get("R") for b, e in bc.items()} != go_r(gate_bytes):
        out.append("battery_checks: R differs from the GO batteries of the gate")
    for b, e in sorted(bc.items()):
        checks = e.get("checks")
        if not isinstance(checks, dict) or b not in _CHECK_ITEMS:
            out.append(f"battery_checks: {b} has no checks")
        elif set(checks) != check_keys(b):
            out.append(f"battery_checks: {b} check names differ from the registration")
        elif any(v != [] for v in checks.values()):
            out.append(f"battery_checks: {b} has a failed check")
    return out


def _external_violations(root: Path, rec: dict[str, Any]) -> list[str]:
    ext = rec.get("external_sha256")
    want = external_modules(root)
    if not isinstance(ext, dict) or sorted(ext) != want:
        return ["external modules: the set differs from the import closure"]
    return [
        f"external modules: {rel} differs from the record"
        for rel in want
        if not _same(ext.get(rel), _sha_file(root, rel))
    ]


def _check(
    root: Path,
    rec: dict[str, Any],
    gate_bytes: bytes,
    models_sha: str,
    fixture_bytes: bytes | None,
) -> list[str]:
    out: list[str] = []
    # 1. stage・status・prereg
    if rec.get("stage") != STAGE:
        out.append("manifest_main: stage is not main")
    if not (root / man.PREREG).is_file():
        return [*out, "prereg: missing"]
    text = (root / man.PREREG).read_text(encoding="utf-8")
    if man.status_line(text) != STATUS_MAIN:
        out.append("prereg: status is not FROZEN")
    if not _same(rec.get("prereg_sha256"), _sha_file(root, man.PREREG)):
        out.append("prereg: sha256 differs from the record")
    # 2. 第 1 段の封印 (と 5 の後半)
    out.extend(_stage1_violations(root, rec, models_sha))
    # 3. 証明書 (と 4 の後半)
    gate_sha = sha256_bytes(gate_bytes)
    out.extend(_cert_violations(root, rec, gate_sha))
    # 4. gate
    if not _same(rec.get("gate_sha256"), gate_sha):
        out.append("gate.json: sha256 differs from the record")
    # 5. models.json
    if not _same(rec.get("models_json_sha256"), models_sha):
        out.append("models.json: sha256 differs from the record")
    # 6. fixture_diffs_main.json
    if fixture_bytes is None:
        p = root / FIXTURE_MAIN
        fixture_bytes = p.read_bytes() if p.is_file() else None
    if fixture_bytes is None:
        out.append("fixture_diffs_main.json: missing")
    elif not _same(rec.get("fixture_diffs_main_sha256"), sha256_bytes(fixture_bytes)):
        out.append("fixture_diffs_main.json: sha256 differs from the record")
    # 7. 見取り図
    if not _same(rec.get("sketch_sha256"), _sha_file(root, man.SKETCH)):
        out.append("sketch.json: sha256 differs from the recomputed sketch")
    # 8. battery_checks
    out.extend(_battery_check_violations(rec, gate_bytes))
    # 9. 段 2 の外の module
    out.extend(_external_violations(root, rec))
    return out


def check(
    root: Path,
    rec: dict[str, Any],
    *,
    gate_bytes: bytes,
    models_sha: str,
    fixture_bytes: bytes | None = None,
) -> list[str]:
    """記録 ``rec`` の照合 (検査 1〜9)。空なら合格。壊れた JSON・型も違反として返す."""
    try:
        return _check(root, rec, gate_bytes, models_sha, fixture_bytes)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return [f"manifest_main: malformed input ({type(exc).__name__}: {exc})"]


def load(root: Path) -> dict[str, Any] | None:
    """記録を読む。無ければ None、読めない・object でなければ ``ManifestError``."""
    p = root / MANIFEST_MAIN
    if not p.is_file():
        return None
    try:
        obj = json.loads(p.read_bytes().decode("utf-8"))
    except (OSError, ValueError) as exc:
        msg = f"manifest_main.json: unreadable ({type(exc).__name__})"
        raise ManifestError(msg) from exc
    if not isinstance(obj, dict):
        msg = "manifest_main.json: not an object"
        raise ManifestError(msg)
    return obj


def violations(
    root: Path,
    *,
    gate_bytes: bytes,
    models_sha: str,
    fixture_bytes: bytes | None = None,
) -> list[str]:
    try:
        rec = load(root)
    except ManifestError as exc:
        return [str(exc)]
    if rec is None:
        return ["manifest_main.json: missing"]
    return check(
        root,
        rec,
        gate_bytes=gate_bytes,
        models_sha=models_sha,
        fixture_bytes=fixture_bytes,
    )


def require(
    root: Path,
    *,
    gate_bytes: bytes,
    models_sha: str,
    fixture_bytes: bytes | None = None,
) -> dict[str, Any]:
    """照合が通れば記録を返す。通らなければ ``ManifestError``."""
    rec = load(root)
    if rec is None:
        msg = "manifest_main.json: missing"
        raise ManifestError(msg)
    errs = check(
        root,
        rec,
        gate_bytes=gate_bytes,
        models_sha=models_sha,
        fixture_bytes=fixture_bytes,
    )
    if errs:
        raise ManifestError("; ".join(errs))
    return rec
