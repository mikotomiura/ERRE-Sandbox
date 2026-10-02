#!/usr/bin/env python
"""候補 G (汎化 probe) — 凍結 manifest の書き出しと照合 (prereg §9・§10).

凍結は 2 段 (Codex 1 回目 HIGH-3、decisions DC-3):

* 第 1 段 ``PILOT-FROZEN``: pilot の計画・機械判定・本走の設計 (battery・scorer・見取り図・fixture・key 選定) を封印する。
  ``manifest.json`` = {"files": 対象の sha256, "prereg_body_sha256": status 行を正規化した prereg の sha256}。
* 第 2 段 ``FROZEN``: pilot の GO・driver の certification・証拠の結び付きが揃ってから、確認実験を凍結する。
  第 1 段の ``manifest.json`` を必須にし、prereg は status 行だけが変わったこと、他の対象は封印時と同じことを照合する
  (Codex 2 回目 HIGH-2)。``manifest_main.json`` は第 1 段の対象・``manifest.json``・固定した証拠の集合を持つ。

照合:

* 結び付き (``binding_violations``):
  - certification: 変異の明細が登録変異の集合 (label と期待 test) と一致し、全て KILLED。記録 sha256 が現在の
    コード・test・harness・本 manifest 検査と一致。meta-test が登録 (label と期待集合) どおりに落ちた
  - 見取り図: 記録 sha256 が現在のコードと一致し、R の候補・MC の設定が凍結値と一致する。期待する点がすべて
    あり、行の値から 3 条件・閾値・最有利行の到達・選定を再計算して記録と一致する (Codex 2 回目 MEDIUM-5)
  - fixture 表: 現在のコードで計算し直した表と一致し、gate を通る
  - probe key の選定: 出力の割り当てが battery の PROBE_KEYS と一致
* 凍結条件 (``freeze_violations``): 段ごと。第 1 段 = 選定が R_MAIN・最有利行が 2τ に届く・status が PILOT-FROZEN か
  FROZEN。第 2 段 = それに加えて status が FROZEN、第 1 段の封印の保存、pilot の機械判定を入力から再計算して
  記録と一致し GO で R が選定と一致、driver の certification が契約を満たす (Codex 2 回目 HIGH-3)。

実行 (repo root から)::

    uv run python scripts/generalization_probe_manifest.py --write --stage pilot
    uv run python scripts/generalization_probe_manifest.py --verify --stage pilot
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import importlib
import json
import math
import pathlib
import sys
from typing import Any, TypeGuard

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import generalization_probe_battery as bat  # noqa: E402
from scripts import generalization_probe_fixtures as fx  # noqa: E402
from scripts import generalization_probe_mutation_check as mut  # noqa: E402
from scripts import generalization_probe_pilot_gate as pg  # noqa: E402
from scripts import generalization_probe_scorer as sc  # noqa: E402
from scripts import generalization_probe_sim as sim  # noqa: E402

EXP = "experiments/20261001-generalization-probe-pilot"
MANIFEST = f"{EXP}/manifest.json"
MANIFEST_MAIN = f"{EXP}/manifest_main.json"
PREREG = f"{EXP}/prereg.md"
CERT = f"{EXP}/results/certification.json"
SKETCH = f"{EXP}/results/sketch.json"
FIXTURES = f"{EXP}/results/fixture_table.json"
KEYS = f"{EXP}/results/key_selection.json"
PILOT_RECORDS = f"{EXP}/results/pilot/records.jsonl"
PILOT_META = f"{EXP}/results/pilot/meta.json"
PILOT_PROVENANCE = f"{EXP}/results/pilot/provenance.json"
PILOT_GATE = f"{EXP}/results/pilot/gate.json"
DRIVER = "scripts/generalization_probe_driver.py"
DRIVER_HARNESS = "scripts/generalization_probe_driver_mutation_check.py"
DRIVER_HARNESS_MODULE = "scripts.generalization_probe_driver_mutation_check"
DRIVER_TEST = "tests/test_generalization_probe/test_driver.py"
DRIVER_CERT = f"{EXP}/results/driver_certification.json"
SELF = "scripts/generalization_probe_manifest.py"
_TESTS = "tests/test_generalization_probe"
TEST_FILES: tuple[str, ...] = (
    f"{_TESTS}/__init__.py",
    f"{_TESTS}/conftest.py",
    f"{_TESTS}/test_battery.py",
    f"{_TESTS}/test_fixtures.py",
    f"{_TESTS}/test_scorer.py",
    f"{_TESTS}/test_sim.py",
    f"{_TESTS}/test_pilot_gate.py",
    f"{_TESTS}/test_manifest.py",
)
HARNESS = "scripts/generalization_probe_mutation_check.py"
FROZEN_FILES: tuple[str, ...] = (
    PREREG,
    f"{EXP}/run.sh",
    f"{EXP}/SEED",
    CERT,
    SKETCH,
    FIXTURES,
    KEYS,
    *(f"scripts/{name}" for name in sc.CERTIFIED),
    "scripts/generalization_probe_key_selection.py",
    "scripts/generalization_probe_render_sketch.py",
    SELF,
    HARNESS,
    *TEST_FILES,
)
# 第 2 段で足せる証拠の集合 (固定。Codex 2 回目 HIGH-2)
MAIN_EVIDENCE: tuple[str, ...] = (
    MANIFEST,
    PILOT_RECORDS,
    PILOT_META,
    PILOT_PROVENANCE,
    PILOT_GATE,
    DRIVER,
    DRIVER_HARNESS,
    DRIVER_TEST,
    DRIVER_CERT,
)
STAGES: tuple[str, ...] = ("pilot", "main")
STATUS_PILOT_LINE = "status: **PILOT-FROZEN**"
STATUS_FROZEN_LINE = "status: **FROZEN**"
STATUS_PREFIX = "- status: "
DOOR_CLOSE = "sketch: the selection rule did not choose R_MAIN (door-close)"
NOT_REACHED = (
    "sketch: the most favourable row does not reach power 0.8 at 2τ (door-close)"
)
DRAFT = "prereg: status is not PILOT-FROZEN or FROZEN (draft)"
NOT_MAIN_FROZEN = "prereg: status is not FROZEN (the confirmatory run is not frozen)"


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def certified_sha256(root: pathlib.Path) -> dict[str, str]:
    return {f"scripts/{name}": sha256(root / "scripts" / name) for name in sc.CERTIFIED}


def tests_sha256(root: pathlib.Path) -> dict[str, str]:
    return {f: sha256(root / f) for f in TEST_FILES}


def harness_sha256(root: pathlib.Path) -> str:
    return sha256(root / HARNESS)


def prereg_body_sha256(text: str) -> str:
    """status 行 (``- status: `` で始まる最初の行) を正規化した prereg の sha256。第 2 段で status 行だけの変更を許す."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith(STATUS_PREFIX):
            lines[i] = STATUS_PREFIX + "<SEALED>"
            break
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def build_manifest(
    root: pathlib.Path, files: tuple[str, ...] = FROZEN_FILES
) -> dict[str, Any]:
    return {
        "files": {f: sha256(root / f) for f in files},
        "prereg_body_sha256": prereg_body_sha256(
            (root / PREREG).read_text(encoding="utf-8")
        ),
    }


def manifest_violations(files: dict[str, str], root: pathlib.Path) -> list[str]:
    out: list[str] = []
    for f, want in files.items():
        p = root / f
        if not p.is_file():
            out.append(f"{f}: missing")
        elif sha256(p) != want:
            out.append(f"{f}: sha256 differs from the frozen manifest")
    return out


def stage1_seal_violations(root: pathlib.Path) -> list[str]:
    """第 2 段: 第 1 段の封印が保たれているか (prereg は status 行以外、他の対象は sha256 が封印時と同じ)."""
    try:
        sealed = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["stage 1: manifest.json is missing or unreadable"]
    files = sealed.get("files") if isinstance(sealed, dict) else None
    if not isinstance(files, dict) or set(files) != set(FROZEN_FILES):
        return ["stage 1: sealed file set differs from FROZEN_FILES"]
    out = manifest_violations({f: h for f, h in files.items() if f != PREREG}, root)
    body = prereg_body_sha256((root / PREREG).read_text(encoding="utf-8"))
    if sealed.get("prereg_body_sha256") != body:
        out.append(
            "stage 1: prereg changed beyond its status line since the pilot seal"
        )
    return [f"stage 1: {v}" if not v.startswith("stage 1") else v for v in out]


def _strs(x: object) -> TypeGuard[list[str]]:
    return isinstance(x, list) and all(isinstance(t, str) for t in x)


def failed_for_expected(row: dict[str, Any]) -> bool:
    """変異の行が、期待した test のどれかで実際に落ちたか (違う理由の失敗を KILLED に数えない、Codex 3 回目 HIGH-1)."""
    failed = row.get("failed")
    expect = row.get("expected_any_of")
    return _strs(failed) and _strs(expect) and bool(set(failed) & set(expect))


def _registry(pairs: list[tuple[object, object]]) -> dict[str, list[str]] | None:
    """登録 (label, 落ちるべき test の集合) の表 (Codex 4 回目 HIGH-1).

    label が一意の文字列で、集合が空でない test 名でなければ None (空の集合は失敗 0 でも成り立ち、label の重複は
    辞書にすると前の登録が消えて一対一にならない)。
    """
    want: dict[str, list[str]] = {}
    for label, expect in pairs:
        if not isinstance(label, str) or label in want:
            return None
        if not isinstance(expect, (list, tuple, set, frozenset)) or not expect:
            return None
        if not all(isinstance(t, str) for t in expect):
            return None
        want[label] = sorted(expect)
    return want or None


def mutant_want(mutants: object) -> dict[str, list[str]] | None:
    """登録変異 (``label`` と ``expect`` を持つ) から、照合する表を作る。形が崩れていれば None."""
    try:
        pairs = [(m.label, m.expect) for m in mutants]  # type: ignore[attr-defined]
    except (TypeError, AttributeError):
        return None
    return _registry(pairs)


def meta_want(cases: object) -> dict[str, list[str]] | None:
    """登録した meta-test のケース (先頭 = label、末尾 = 落ちるべき test の集合) から、照合する表を作る。形が崩れていれば None."""
    if not isinstance(cases, (list, tuple)):
        return None
    if not all(isinstance(c, (list, tuple)) and len(c) >= 2 for c in cases):  # noqa: PLR2004
        return None
    return _registry([(c[0], c[-1]) for c in cases])


def meta_contract_ok(meta: object, want: dict[str, list[str]] | None) -> bool:
    """meta-test が登録ケースと一対一で、各ケースが期待集合をすべて実際に落としたか (Codex 3 回目 HIGH-1)."""
    if not want or not isinstance(meta, list):
        return False
    if not all(isinstance(m, dict) for m in meta):
        return False
    labels = [m.get("label") for m in meta]
    if not all(isinstance(lb, str) for lb in labels):
        return False
    if len(set(labels)) != len(labels):
        return False
    if set(labels) != set(want):
        return False
    for m in meta:
        expect = want[m["label"]]
        failed = m.get("failed")
        if (
            m.get("status") != "FAILED_AS_EXPECTED"
            or m.get("expected_all_of") != expect
        ):
            return False
        if not _strs(failed) or not set(expect) <= set(failed):
            return False
    return True


def meta_test_violations(meta: object) -> list[str]:
    if not meta_contract_ok(meta, meta_want(mut.META_CASES)):
        return [
            "certification: the meta-test differs from the registered cases or did not fail as expected"
        ]
    return []


def certification_violations(cert: dict[str, Any], root: pathlib.Path) -> list[str]:
    out: list[str] = []
    if cert.get("all_killed") is not True:
        out.append("certification: not all mutants KILLED")
    if cert.get("target_sha256") != certified_sha256(root):
        out.append("certification: recorded sha256 differs from current code")
    if cert.get("tests_sha256") != tests_sha256(root):
        out.append("certification: recorded test sha256 differs from current tests")
    if cert.get("harness_sha256") != harness_sha256(root):
        out.append(
            "certification: recorded harness sha256 differs from current harness"
        )
    if cert.get("manifest_sha256") != sha256(root / SELF):
        out.append(
            "certification: recorded manifest-check sha256 differs from current file"
        )
    out += meta_test_violations(cert.get("meta_test"))
    rows = cert.get("mutants")
    if not isinstance(rows, list):
        return [*out, "certification: no mutant rows"]
    want = mutant_want(mut.MUTANTS)
    got = {
        x.get("label"): x.get("expected_any_of") for x in rows if isinstance(x, dict)
    }
    if want is None or len(rows) != len(want) or got != want:
        out.append("certification: mutant rows differ from the registered mutants")
    if any(not isinstance(x, dict) or x.get("status") != "KILLED" for x in rows):
        out.append("certification: a mutant row is not KILLED")
    if any(not isinstance(x, dict) or not failed_for_expected(x) for x in rows):
        out.append("certification: a mutant row did not fail for an expected reason")
    return out


# ------------------------------------------------------------- 見取り図


def expected_points(r_count: int) -> set[tuple[str, str, float, str, float, str]]:
    """選定規則が要る (kind, form, target, base, bot, coupling) の全点."""
    pts: set[tuple[str, str, float, str, float, str]] = set()
    for form in sim.POWER_FORMS:
        for nu in sim._nuisances_for(form):  # noqa: SLF001
            pts.add(("power_pass", form, sc.DELTA_PLANT, nu.base, nu.bot, nu.coupling))
    for form in sim.NO_GO_FORMS:
        for nu in sim.nuisance_grid():
            pts.add(("power_no_go", form, 0.0, nu.base, nu.bot, nu.coupling))
    for form, target, branch in sim.size_points():
        for nu in sim._nuisances_for(form):  # noqa: SLF001
            pts.add((f"size_{branch}", form, target, nu.base, nu.bot, nu.coupling))
    del r_count
    return pts


VERDICTS: tuple[str, ...] = (
    sc.VERDICT_PASS,
    sc.VERDICT_ABSENT,
    sc.VERDICT_UNDERPOWERED,
    sc.VERDICT_INVALID_BATTERY,
)
_POINT = ("form", "target_C", "base", "bot", "coupling")
_ROW_KEYS = frozenset({"kind", "R", *_POINT, "per_seed", "value"})
_SWEEP_KEYS = frozenset({"R", *_POINT, "reachable", "pass", "per_seed"})


def _scalars(x: dict[str, Any], keys: tuple[str, ...]) -> bool:
    """点の欄が文字列か数値 (JSON の真偽値は数値に数えない、Codex 4 回目 LOW-2)."""
    return all(
        isinstance(x[k], (str, int, float)) and not isinstance(x[k], bool) for k in keys
    )


def _num(x: object) -> float:
    """数値なら float、それ以外 (JSON の真偽値を含む、Codex 4 回目 LOW-2) は NaN."""
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return float(x)
    return float("nan")


def _same_json(a: object, b: object) -> bool:
    """型まで含めた一致 (1.0 と true、2000 と 2000.0 を区別する)。キーの順は問わない."""
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def rates_ok(p: object, n_sims: int) -> bool:
    """1 seed の結果が率の組として妥当か (Codex 3 回目 MEDIUM-3).

    4 判定の率が有限で [0, 1]・合計 1・n_sims 回の格子の上にあり、実現 C が有限。
    """
    if not isinstance(p, dict) or set(p) != {*VERDICTS, "realized_C"}:
        return False
    vals = [_num(p[k]) for k in VERDICTS]
    if not all(math.isfinite(v) and 0.0 <= v <= 1.0 for v in vals):
        return False
    if abs(sum(vals) - 1.0) > 1e-9:
        return False
    if not all(abs(v * n_sims - round(v * n_sims)) < 1e-6 for v in vals):
        return False
    return math.isfinite(_num(p["realized_C"]))


def per_seed_ok(per_seed: object, n_sims: int) -> bool:
    return (
        isinstance(per_seed, list)
        and len(per_seed) == len(sim.SEEDS)
        and all(rates_ok(p, n_sims) for p in per_seed)
    )


@functools.cache
def _size_threshold(n_checks: int) -> int:
    """``sim.size_count_threshold`` (二項の尾の正確な和で重い) を点の数ごとに 1 回だけ計算する."""
    return sim.size_count_threshold(n_checks)


def recheck_r(res: dict[str, Any]) -> list[str]:
    """1 つの R について、行の per_seed から値・3 条件・閾値を再計算し、記録と照合する."""
    out: list[str] = []
    r_count = res.get("R")
    rows = res.get("rows")
    if not isinstance(r_count, int):
        return ["sketch: a per_R entry has no integer R"]
    if not isinstance(rows, list) or not all(
        isinstance(x, dict) and _ROW_KEYS <= set(x) and _scalars(x, ("kind", *_POINT))
        for x in rows
    ):
        return [f"sketch R{r_count}: rows are missing or malformed"]
    keys = {
        (x["kind"], x["form"], x["target_C"], x["base"], x["bot"], x["coupling"])
        for x in rows
    }
    if keys != expected_points(r_count) or len(rows) != len(keys):
        out.append(f"sketch R{r_count}: rows differ from the points the rule requires")
    if any(x["R"] != r_count for x in rows):
        out.append(f"sketch R{r_count}: a row's R differs from its block")
    values: dict[str, list[float]] = {}
    for x in rows:
        kind = x["kind"]
        n_sims = sim.N_SIM_POWER if kind.startswith("power") else sim.N_SIM_SIZE
        per_seed = x["per_seed"]
        if not per_seed_ok(per_seed, n_sims):
            out.append(
                f"sketch R{r_count}: a row's per-seed results are not one valid set of rates per seed"
            )
            continue
        if kind == "power_pass":
            v = sum(p[sc.VERDICT_PASS] for p in per_seed) / len(per_seed)
        elif kind == "power_no_go":
            v = sum(p[sc.VERDICT_ABSENT] for p in per_seed) / len(per_seed)
        elif kind == "size_pass":
            v = max(p[sc.VERDICT_PASS] for p in per_seed)
        else:
            v = max(p[sc.VERDICT_ABSENT] for p in per_seed)
        if not _close(v, _num(x["value"])):
            out.append(
                f"sketch R{r_count}: a row value differs from its per-seed results"
            )
        values.setdefault(kind, []).append(v)
    sizes = values.get("size_pass", []) + values.get("size_no_go", [])
    n_checks = len(sizes) * len(sim.SEEDS)
    cap = _size_threshold(n_checks) / sim.N_SIM_SIZE if n_checks else -1.0
    flags = {
        "power_ok": all(v >= sim.POWER_TARGET for v in values.get("power_pass", [])),
        "no_go_ok": all(v >= sim.POWER_TARGET for v in values.get("power_no_go", [])),
        "size_ok": all(v <= cap + 1e-12 for v in sizes),
    }
    for flag, want in flags.items():
        if res.get(flag) is not want:
            out.append(
                f"sketch R{r_count}: {flag} differs from a recomputation from the rows"
            )
    if res.get("n_size_checks") != n_checks or not _close(
        _num(res.get("size_cap")), cap
    ):
        out.append(
            f"sketch R{r_count}: the size threshold differs from a recomputation"
        )
    if sizes and not _close(_num(res.get("worst_size")), max(sizes)):
        out.append(f"sketch R{r_count}: worst_size differs from a recomputation")
    return list(dict.fromkeys(out))


def _close(a: float, b: float) -> bool:
    return math.isfinite(a) and math.isfinite(b) and abs(a - b) <= 1e-12


def expected_params() -> dict[str, Any]:
    """見取り図の凍結する設定 (``sim.main`` が書く params と同じ形、Codex 3 回目 MEDIUM-3)."""
    params = {
        "R_candidates": list(sim.R_CANDIDATES),
        "grid": list(sim.GRID),
        "n_sim_power": sim.N_SIM_POWER,
        "n_sim_size": sim.N_SIM_SIZE,
        "seeds": list(sim.SEEDS),
        "tau": sc.TAU,
        "alpha": sc.ALPHA,
        "delta_plant": sc.DELTA_PLANT,
        "power_target": sim.POWER_TARGET,
        "mc_fwer": sim.MC_FWER,
        "oov": sim.OOV,
        "skew": sim.SKEW,
        "lambda_fractions": list(sc.LAMBDA_FRACTIONS),
        "weak_null": sim.WEAK_NULL,
        "reverse_fraction": sim.REVERSE_FRACTION,
    }
    return json.loads(json.dumps(params))


def _sweep_nuisances(form: str) -> tuple[tuple[str, sim.Nuisance], ...]:
    """sweep の 2 攪乱点 (対数オッズは label_skew に固定)."""
    out = []
    for kind, nu in (("favorable", sim.FAVORABLE), ("adverse", sim.ADVERSE)):
        base = "label_skew" if form == "logodds" else nu.base
        out.append((kind, sim.Nuisance(base, nu.bot, nu.coupling)))
    return tuple(out)


def expected_sweep_points() -> set[tuple[Any, ...]]:
    """sweep が要る (R, form, target, base, bot, coupling) の全点 (Codex 3 回目 MEDIUM-3)."""
    pts: set[tuple[Any, ...]] = set()
    for r_count in sim.R_CANDIDATES:
        for form in sim.FORMS:
            for _, nu in _sweep_nuisances(form):
                reach = sim.reachable(form, nu)
                pts |= {
                    (r_count, form, t, nu.base, nu.bot, nu.coupling)
                    for t in sim.GRID
                    if t <= reach + 1e-9
                }
    return pts


def sweep_boundaries(sweeps: list[dict[str, Any]]) -> dict[str, Any]:
    """power 0.8 の境目の表を sweep の行から計算し直す (``sim.main`` の boundaries と同じ形)."""
    return {
        f"R{r}": {
            form: {
                kind: sim.boundary(
                    [
                        x
                        for x in sweeps
                        if x["R"] == r
                        and x["form"] == form
                        and (x["base"], x["bot"], x["coupling"])
                        == (nu.base, nu.bot, nu.coupling)
                    ]
                )
                for kind, nu in _sweep_nuisances(form)
            }
            for form in sim.FORMS
        }
        for r in sim.R_CANDIDATES
    }


def sweep_violations(sketch: dict[str, Any]) -> list[str]:
    """sweep の完全性・行の到達上限・per_seed との整合・最有利行の到達・境目を照合する (Codex 3 回目 MEDIUM-3)."""
    sweeps = sketch.get("sweeps")
    if not isinstance(sweeps, list) or not all(
        isinstance(x, dict) and _SWEEP_KEYS <= set(x) and _scalars(x, ("R", *_POINT))
        for x in sweeps
    ):
        return ["sketch: sweeps are missing or malformed"]
    out: list[str] = []
    keys = [(x["R"], *(x[k] for k in _POINT)) for x in sweeps]
    if set(keys) != expected_sweep_points() or len(keys) != len(set(keys)):
        out.append("sketch: sweep rows differ from the points the rule requires")
    for x in sweeps:
        nu = sim.Nuisance(x["base"], x["bot"], x["coupling"])
        if not _close(_num(x["reachable"]), sim.reachable(x["form"], nu)):
            out.append("sketch: a sweep row's reachable differs from a recomputation")
        if not per_seed_ok(x["per_seed"], sim.N_SIM_POWER):
            out.append("sketch: a sweep row's per-seed results are not valid rates")
            continue
        mean = sum(p[sc.VERDICT_PASS] for p in x["per_seed"]) / len(sim.SEEDS)
        if not _close(_num(x["pass"]), mean):
            out.append("sketch: a sweep row's pass differs from its per-seed results")
    if sketch.get("most_favorable_reaches") is not sim.most_favorable_reaches(sweeps):
        out.append(
            "sketch: most_favorable_reaches differs from a recomputation from the sweeps"
        )
    fresh = json.loads(json.dumps(sweep_boundaries(sweeps)))
    if sketch.get("boundaries") != fresh:
        out.append("sketch: boundaries differ from a recomputation from the sweeps")
    return list(dict.fromkeys(out))


def sketch_violations(sketch: dict[str, Any], root: pathlib.Path) -> list[str]:
    out: list[str] = []
    if sketch.get("target_sha256") != certified_sha256(root):
        out.append("sketch: recorded sha256 differs from current code")
    if not _same_json(sketch.get("params"), expected_params()):
        out.append("sketch: params differ from the frozen settings")
    per_r = sketch.get("per_R")
    if (
        not isinstance(per_r, list)
        or not all(isinstance(x, dict) for x in per_r)
        or [x.get("R") for x in per_r] != list(sim.R_CANDIDATES)
    ):
        return [*out, "sketch: per_R does not cover the R candidates"]
    for res in per_r:
        out += recheck_r(res)
    if sketch.get("selection") != sim.select(per_r):
        out.append("sketch: the selection differs from a recomputation of the rule")
    out += sweep_violations(sketch)
    return out


def fixture_violations(table: dict[str, Any]) -> list[str]:
    out: list[str] = []
    fresh = {f"R{r}": fx.fixture_table(r) for r in sim.R_CANDIDATES}
    if table.get("tables") != json.loads(json.dumps(fresh)):
        out.append("fixture table: differs from a recomputation with the current code")
    if table.get("passed") is not True:
        out.append("fixture table: the τ/4 gate failed")
    return out


def key_violations(keys: dict[str, Any]) -> list[str]:
    want = {c: list(v) for c, v in bat.PROBE_KEYS.items()}
    if keys.get("assignment") != want:
        return ["key selection: assignment differs from PROBE_KEYS"]
    return []


# ------------------------------------------------------------- 第 2 段の証拠


def driver_certification_violations(cert: object, root: pathlib.Path) -> list[str]:
    """driver の certification の契約 (第 1 段で固定、Codex 2 回目 HIGH-3)."""
    if not isinstance(cert, dict):
        return ["driver: certification missing"]
    out: list[str] = []
    if cert.get("all_killed") is not True:
        out.append("driver: certification is not all KILLED")
    rows = cert.get("mutants")
    if (
        not isinstance(rows, list)
        or not rows
        or not all(isinstance(x, dict) for x in rows)
    ):
        return [*out, "driver: certification has no mutant rows"]
    labels = [x.get("label") for x in rows]
    if not all(isinstance(lb, str) for lb in labels) or len(set(labels)) != len(labels):
        out.append("driver: mutant labels are not unique strings")
    if any(x.get("status") != "KILLED" for x in rows):
        out.append("driver: a mutant row is not KILLED")
    if any(
        not isinstance(x.get("expected_any_of"), list) or not x["expected_any_of"]
        for x in rows
    ):
        out.append("driver: a mutant row has no expected diagnosis")
    if any(not failed_for_expected(x) for x in rows):
        out.append("driver: a mutant row did not fail for an expected reason")
    try:
        harness: object = importlib.import_module(DRIVER_HARNESS_MODULE)
    except ImportError:
        harness = None
    want = mutant_want(getattr(harness, "MUTANTS", None))
    want_meta = meta_want(getattr(harness, "META_CASES", None))
    got = {x.get("label"): x.get("expected_any_of") for x in rows}
    if want is None or got != want:
        out.append("driver: mutant rows differ from the registered driver mutants")
    if want_meta is None or not meta_contract_ok(cert.get("meta_test"), want_meta):
        out.append(
            "driver: the meta-test differs from the registered driver cases or did not fail as expected"
        )
    for key, rel in (
        ("target_sha256", DRIVER),
        ("tests_sha256", DRIVER_TEST),
        ("harness_sha256", DRIVER_HARNESS),
    ):
        p = root / rel
        if not p.is_file() or cert.get(key) != {rel: sha256(p)}:
            out.append(f"driver: recorded {key} differs from the current file")
    return out


def pilot_gate_violations(
    gate: object, provenance: object, selected_r: object, root: pathlib.Path
) -> list[str]:
    """pilot の機械判定を凍結した関数で入力から再計算し、記録と照合する (Codex 2 回目 MEDIUM-5)."""
    if not isinstance(gate, dict):
        return ["pilot gate: missing"]
    out: list[str] = []
    try:
        samples = sc.load_records(
            (root / PILOT_RECORDS).read_text(encoding="utf-8").splitlines()
        )
        meta = json.loads((root / PILOT_META).read_text(encoding="utf-8"))
    except (OSError, ValueError, sc.RecordError):
        return ["pilot gate: the pilot records cannot be read"]
    fresh = pg.decide_pilot(
        samples,
        meta,
        certified=sc.load_certification(root / CERT),
        selected_r=selected_r if isinstance(selected_r, int) else None,
    )
    for key in ("decision", "R", "masked_max_bottom", "observed"):
        if fresh.get(key) != gate.get(key):
            out.append(
                f"pilot gate: {key} differs from a recomputation from the inputs"
            )
    if gate.get("decision") != pg.DECISION_GO:
        out.append("pilot gate: not GO")
    if gate.get("R") != selected_r:
        out.append("pilot gate: R differs from the sketch selection")
    inputs = gate.get("inputs_sha256") or {}
    for name, rel in (
        ("records", PILOT_RECORDS),
        ("meta", PILOT_META),
        ("cert", CERT),
        ("sketch", SKETCH),
    ):
        p = root / rel
        if not p.is_file() or inputs.get(name) != sha256(p):
            out.append(f"pilot gate: input {name} is not bound to the current file")
    # provenance は driver と、その driver が書いた records・meta を同時に結ぶ (Codex 3 回目 HIGH-2)
    for key, rel in (
        ("driver_sha256", DRIVER),
        ("records_sha256", PILOT_RECORDS),
        ("meta_sha256", PILOT_META),
    ):
        p = root / rel
        if (
            not isinstance(provenance, dict)
            or not p.is_file()
            or provenance.get(key) != sha256(p)
        ):
            out.append(f"pilot: provenance {key} does not bind the current {rel}")
    return out


def _status(prereg_text: str) -> str | None:
    head = prereg_text.splitlines()[:12]
    if any(STATUS_FROZEN_LINE in line for line in head):
        return "FROZEN"
    if any(STATUS_PILOT_LINE in line for line in head):
        return "PILOT-FROZEN"
    return None


def freeze_violations(
    sketch: dict[str, Any],
    prereg_text: str,
    stage: str = "pilot",
    root: pathlib.Path = _REPO_ROOT,
) -> list[str]:
    out: list[str] = []
    sel = sketch.get("selection") or {}
    if sel.get("door_close") is not False or sel.get("selected_R") != sim.R_MAIN:
        out.append(DOOR_CLOSE)
    if sketch.get("most_favorable_reaches") is not True:
        out.append(NOT_REACHED)
    status = _status(prereg_text)
    if status is None:
        out.append(DRAFT)
    if stage == "main":
        if status != "FROZEN":
            out.append(NOT_MAIN_FROZEN)
        out += stage1_seal_violations(root)
        out += pilot_gate_violations(
            _load_optional(root, PILOT_GATE),
            _load_optional(root, PILOT_PROVENANCE),
            sel.get("selected_R"),
            root,
        )
        out += driver_certification_violations(_load_optional(root, DRIVER_CERT), root)
    return out


def _load(root: pathlib.Path) -> tuple[dict[str, Any], ...] | str:
    try:
        return tuple(
            json.loads((root / p).read_text(encoding="utf-8"))
            for p in (CERT, SKETCH, FIXTURES, KEYS)
        )
    except (OSError, ValueError) as exc:
        return f"cannot read the bound artifacts: {exc}"


def _load_optional(root: pathlib.Path, rel: str) -> dict[str, Any] | None:
    try:
        obj = json.loads((root / rel).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


def binding_violations(root: pathlib.Path) -> list[str]:
    loaded = _load(root)
    if isinstance(loaded, str):
        return [loaded]
    cert, sketch, fixtures, keys = loaded
    return (
        certification_violations(cert, root)
        + sketch_violations(sketch, root)
        + fixture_violations(fixtures)
        + key_violations(keys)
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    ap.add_argument("--stage", choices=STAGES, required=True)
    args = ap.parse_args(argv)

    files = FROZEN_FILES if args.stage == "pilot" else (*FROZEN_FILES, *MAIN_EVIDENCE)
    target = MANIFEST if args.stage == "pilot" else MANIFEST_MAIN
    binding = binding_violations(_REPO_ROOT)
    if args.write:
        if binding:
            print("\n".join(f"ERROR: {p}" for p in binding))
            return 1
        path = _REPO_ROOT / target
        path.write_text(
            json.dumps(build_manifest(_REPO_ROOT, files), indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"wrote {target} ({len(files)} files)")
        return 0
    problems = list(binding)
    try:
        manifest = json.loads((_REPO_ROOT / target).read_text(encoding="utf-8"))
        recorded = manifest["files"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        problems.append(f"cannot read {target}: {exc}")
    else:
        problems += manifest_violations(recorded, _REPO_ROOT)
        if set(recorded) != set(files):
            problems.append(
                f"{target}: file list differs from the stage's frozen files"
            )
    for p in problems:
        print(f"MISMATCH: {p}")
    loaded = _load(_REPO_ROOT)
    freeze = (
        []
        if isinstance(loaded, str)
        else freeze_violations(
            loaded[1], (_REPO_ROOT / PREREG).read_text(encoding="utf-8"), args.stage
        )
    )
    for p in freeze:
        print(f"NOT FROZEN: {p}")
    if problems:
        print(f"MANIFEST MISMATCH ({len(problems)})")
    elif freeze:
        kind = (
            "door-close"
            if any(p in (DOOR_CLOSE, NOT_REACHED) for p in freeze)
            else "draft"
        )
        print(f"MANIFEST BOUND, NOT FROZEN ({kind}, stage {args.stage})")
    else:
        print(f"MANIFEST OK (stage {args.stage})")
    return 0 if not problems and not freeze else 1


if __name__ == "__main__":
    sys.exit(main())
