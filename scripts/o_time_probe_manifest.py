#!/usr/bin/env python
"""候補 O_time (時期の評価) — 凍結 manifest の書き出しと照合 (prereg §9・§10).

凍結は 2 段 (G prereg §9 の型):

* 第 1 段 ``PILOT-FROZEN``: pilot の計画・機械判定・本走の設計 (battery・scorer・見取り図・fixture) を封印する。
  ``manifest.json`` = {"files": 対象の sha256, "prereg_body_sha256": status 行を正規化した prereg の sha256}。
* 第 2 段 ``FROZEN``: pilot の GO・driver の certification・証拠の結び付きが揃ってから、確認実験を凍結する。
  第 1 段の ``manifest.json`` を必須にし、prereg は status 行だけが変わったこと、他の対象は封印時と同じことを照合する。
  ``manifest_main.json`` は第 1 段の対象・``manifest.json``・固定した証拠の集合を持つ。

照合:

* 結び付き (``binding_violations``):
  - certification: 変異の明細が登録変異の集合 (label と期待 test) と一致し、全て KILLED で、期待した test で実際に落ちた。
    記録 sha256 が現在のコード・test・harness・本 manifest 検査と一致。meta-test が登録 (label と期待集合) どおりに落ちた
  - 見取り図: 記録 sha256 が現在のコードと一致し、設定 (params) が凍結値と型まで一致する。期待する点がすべてあり、
    行の per_seed から値・4 条件・閾値を**独立に**再計算して記録と一致し、選定 (4 条件を満たす最大の R) も再計算と一致する。
    sweep の点の完全性・到達上限・率・最有利行の到達・境目を照合する
  - fixture 表: 現在のコードで計算し直した表と一致し、gate を通る
* 凍結条件 (``freeze_violations``): 段ごと。第 1 段 = 選定が R を選んだ (door-close でない)・最有利行が 2τ に届く・status が
  PILOT-FROZEN か FROZEN。第 2 段 = それに加えて status が FROZEN、第 1 段の封印の保存、pilot の機械判定を入力から
  再計算して記録と一致し GO で R が選定と一致、provenance が driver と記録・meta を結ぶ、driver の certification が契約を満たす。

実行 (repo root から)::

    uv run python scripts/o_time_probe_manifest.py --write --stage pilot
    uv run python scripts/o_time_probe_manifest.py --verify --stage pilot
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

from scripts import o_time_probe_battery as bat  # noqa: E402
from scripts import o_time_probe_fixtures as fx  # noqa: E402
from scripts import o_time_probe_mutation_check as mut  # noqa: E402
from scripts import o_time_probe_pilot_gate as pg  # noqa: E402
from scripts import o_time_probe_scorer as sc  # noqa: E402
from scripts import o_time_probe_sim as sim  # noqa: E402

EXP = "experiments/20261008-o-time-probe-pilot"
MANIFEST = f"{EXP}/manifest.json"
MANIFEST_MAIN = f"{EXP}/manifest_main.json"
PREREG = f"{EXP}/prereg.md"
CERT = f"{EXP}/results/certification.json"
SKETCH = f"{EXP}/results/sketch.json"
FIXTURES = f"{EXP}/results/fixture_table.json"
PILOT_RECORDS = f"{EXP}/results/pilot/records.jsonl"
PILOT_META = f"{EXP}/results/pilot/meta.json"
PILOT_PROVENANCE = f"{EXP}/results/pilot/provenance.json"
PILOT_GATE = f"{EXP}/results/pilot/gate.json"
DRIVER = "scripts/o_time_probe_driver.py"
DRIVER_HARNESS = "scripts/o_time_probe_driver_mutation_check.py"
DRIVER_HARNESS_MODULE = "scripts.o_time_probe_driver_mutation_check"
DRIVER_TEST = "tests/test_o_time_probe/test_driver.py"
DRIVER_CERT = f"{EXP}/results/driver_certification.json"
SELF = "scripts/o_time_probe_manifest.py"
_TESTS = "tests/test_o_time_probe"
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
HARNESS = "scripts/o_time_probe_mutation_check.py"
FROZEN_FILES: tuple[str, ...] = (
    PREREG,
    f"{EXP}/run.sh",
    f"{EXP}/SEED",
    CERT,
    SKETCH,
    FIXTURES,
    *(f"scripts/{name}" for name in sc.CERTIFIED),
    "scripts/o_time_probe_render_sketch.py",
    SELF,
    HARNESS,
    *TEST_FILES,
)
# 第 2 段で足せる証拠の集合 (固定)
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
DOOR_CLOSE = "sketch: the selection rule chose no R (door-close)"
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


# ------------------------------------------------------------- certification


def _name(x: object) -> bool:
    """空でない、空白だけでない文字列 (label・test 名。Codex LOW-6)."""
    return isinstance(x, str) and bool(x.strip())


def _strs(x: object) -> TypeGuard[list[str]]:
    return isinstance(x, list) and all(_name(t) for t in x)


def failed_for_expected(row: dict[str, Any]) -> bool:
    """変異の行が、期待した test のどれかで実際に落ちたか (違う理由の失敗を KILLED に数えない)."""
    failed = row.get("failed")
    expect = row.get("expected_any_of")
    return _strs(failed) and _strs(expect) and bool(set(failed) & set(expect))


def _registry(pairs: list[tuple[object, object]]) -> dict[str, list[str]] | None:
    """登録 (label, 落ちるべき test の集合) の表。label が一意の文字列で、集合が空でない test 名でなければ None."""
    want: dict[str, list[str]] = {}
    for label, expect in pairs:
        if not _name(label) or label in want:
            return None
        if not isinstance(expect, (list, tuple, set, frozenset)) or not expect:
            return None
        if not all(_name(t) for t in expect):
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
    """登録した meta-test のケース (先頭 = label、末尾 = 落ちるべき test の集合) から、照合する表を作る."""
    if not isinstance(cases, (list, tuple)):
        return None
    if not all(isinstance(c, (list, tuple)) and len(c) >= 2 for c in cases):  # noqa: PLR2004
        return None
    return _registry([(c[0], c[-1]) for c in cases])


def meta_contract_ok(meta: object, want: dict[str, list[str]] | None) -> bool:
    """meta-test が登録ケースと一対一で、各ケースが期待集合をすべて実際に落としたか."""
    if not want or not isinstance(meta, list):
        return False
    if not all(isinstance(m, dict) for m in meta):
        return False
    labels = [m.get("label") for m in meta]
    if not all(isinstance(lb, str) for lb in labels):
        return False
    if len(set(labels)) != len(labels) or set(labels) != set(want):
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


# ---- 登録 (prereg §7.1 の文面から書き、sim から導かない。Codex HIGH-4: sim の FORMS や攪乱点を削ると、
#      sim から導いた期待集合も同時に縮んで欠けを検出できない)
REGISTERED_R: tuple[int, ...] = (96, 192, 288)
REGISTERED_FORMS: tuple[str, ...] = (
    "homog_sd005",
    "homog_sd030",
    "sparse_1of3",
    "sparse_2of3",
    "asc_only",
    "chrono_only",
    "aon_cell",
    "aon_unit",
    "aon_arm_unit",
    "aon_item",
    "logodds",
    "reverse_1of6",
)
REGISTERED_NUISANCES: tuple[tuple[str, float, str], ...] = tuple(
    (base, bot, coupling)
    for base in ("uniform", "label_skew", "position_skew")
    for bot in (0.0, 0.1)
    for coupling in ("crn", "indep", "anti")
)
REGISTERED_SWEEP_NUISANCES: dict[str, tuple[str, float, str]] = {
    "favorable": ("uniform", 0.0, "crn"),
    "adverse": ("label_skew", 0.1, "anti"),
}
REGISTERED_GRID: tuple[float, ...] = tuple(round(0.025 * i, 3) for i in range(33))
BAND_BASES: tuple[str, ...] = ("uniform", "position_skew")  # user 裁定 DU-3
CALIBRATION_TOL = 0.01
REGISTERED_N_SIM_POWER = 2_000
REGISTERED_N_SIM_SIZE = 10_000
REGISTERED_SEEDS: tuple[int, ...] = (20261008, 20261009)
POWER_TARGET = 0.8
# α = 1/20 と MC の FWER = 1/100 を有理数で持つ (size の閾値を整数で正確に計算するため)
ALPHA_DEN = 20
FWER_DEN = 100


@functools.cache
def registered_size_threshold(
    n_checks: int, n_sims: int = REGISTERED_N_SIM_SIZE
) -> int:
    """size の合格の上限 x を、sim と独立に整数の算術で正確に計算する (Codex 2 周目 MEDIUM-1).

    x は P(X > x) ≤ (1/100) / n_checks を満たす最小の整数 (X ~ Binomial(n_sims, 1/20))。
    20^n · P(X = k) = C(n, k) · 19^(n − k) は整数なので、条件は 100 · n_checks · Σ_{k > x} C(n, k) 19^(n − k) ≤ 20^n。
    sim の ``size_count_threshold`` (log 空間の浮動小数の和) とは別の計算で、生成側の誤りを共有しない。
    """
    terms = [0] * (n_sims + 1)
    terms[0] = (ALPHA_DEN - 1) ** n_sims
    for k in range(n_sims):
        terms[k + 1] = terms[k] * (n_sims - k) // ((k + 1) * (ALPHA_DEN - 1))
    total = ALPHA_DEN**n_sims
    tail = [0] * (n_sims + 2)
    for k in range(n_sims, -1, -1):
        tail[k] = tail[k + 1] + terms[k]
    if tail[0] != total:
        msg = "binomial terms do not sum to 20^n"
        raise ArithmeticError(msg)
    x = 0
    while FWER_DEN * n_checks * tail[x + 1] > total:
        x += 1
    return x


def registered_boundary(
    points: list[tuple[float, float]], *, rising: bool = True
) -> float | None:
    """境目 (P が 0.8 を越える / 下回る E[C]) の線形補間を、sim の ``boundary`` と独立に書く (Codex 2 周目 MEDIUM-1)."""
    pts = sorted(points)
    for i in range(len(pts) - 1):
        (c0, p0), (c1, p1) = pts[i], pts[i + 1]
        crosses = (p0 < POWER_TARGET <= p1) if rising else (p1 < POWER_TARGET <= p0)
        if crosses:
            return c0 + (c1 - c0) * (POWER_TARGET - p0) / (p1 - p0)
    if rising and pts and pts[0][1] >= POWER_TARGET:
        return pts[0][0]
    return None


def _chrono_factor(r_count: int, base: str) -> float:
    """時系列の表示でだけ評価する形の較正係数 F = mean_u mean_a m_a (1 − g_a) を、battery から独立に計算する."""
    hi, lo = 0.95 * 0.7, 0.95 * 0.15
    total = 0.0
    us = bat.units(r_count)
    for u in us:
        room = bat.ROOMS[u.room]
        order = bat.entry_order(u.family, u.room, u.replicate)
        a_first = order.index(
            (room, bat.first_rule_label(u.family, u.room))
        ) < order.index((room, bat.second_rule_label(u.family, u.room)))
        a_idx, b_idx = u.room % 3, (u.room + 1) % 3
        if base == "uniform":
            p_a = p_b = 0.95 / 3.0
        elif base == "label_skew":
            p_a, p_b = hi, lo
        else:
            first = (u.replicate + u.room) % 3
            p_a = hi if a_idx == first else lo
            p_b = hi if b_idx == first else lo
        g_fwd = p_b - p_a  # fwd の w = B 側
        total += (1.0 - g_fwd) if a_first else (1.0 + g_fwd)
    return total / (2 * len(us))


def registered_reach(form: str, base: str, bot: float, r_count: int) -> float:
    """形の到達上限 (prereg §7.1)。sim の ``reachable`` と独立に計算する."""
    live = 1.0 - bot
    simple = {
        "sparse_1of3": live * 2 / 6,
        "sparse_2of3": live * 4 / 6,
        "asc_only": live * 0.5,
        "reverse_1of6": live * (1.0 - 2.0 / 6.0),
        "logodds": live * 0.95 * 0.999,
    }
    if form == "chrono_only":
        return live * _chrono_factor(r_count, base)
    return simple.get(form, live)


def expected_points() -> set[tuple[str, str, float, str, float, str]]:
    """選定規則が要る (kind, form, target, base, bot, coupling) の全点 (登録から列挙し、sim から導かない)."""
    grid = REGISTERED_NUISANCES
    skew = tuple(nu for nu in grid if nu[0] == "label_skew")
    pts: set[tuple[str, str, float, str, float, str]] = set()
    for form in ("homog_sd005", "homog_sd030", "logodds"):
        for nu in skew if form == "logodds" else grid:
            pts.add(("power_pass", form, sc.DELTA_PLANT, *nu))
    for form in ("homog_sd005", "homog_sd030"):
        for nu in grid:
            pts.add(("power_no_go", form, 0.0, *nu))
            if nu[2] == "crn":
                kind = "band" if nu[0] in BAND_BASES else "band_diag"
                for target in (0.25, 0.35):
                    pts.add((kind, form, target, *nu))
    size_forms = [(f, sc.TAU, br) for f in REGISTERED_FORMS for br in ("pass", "no_go")]
    size_forms.append(("weak_null", 0.0, "pass"))
    size_forms += [(f"pass_extremal_{m}", sc.TAU, "pass") for m in (0.4, 0.6, 0.8, 1.0)]
    size_forms += [
        (f"no_go_extremal_{m}", sc.TAU, "no_go") for m in (-1.0, -0.5, 0.0, 0.2)
    ]
    for form, target, branch in size_forms:
        for nu in skew if form == "logodds" else grid:
            pts.add((f"size_{branch}", form, target, *nu))
    return pts


VERDICTS: tuple[str, ...] = (
    sc.VERDICT_PASS,
    sc.VERDICT_ABSENT,
    sc.VERDICT_UNDERPOWERED,
    sc.VERDICT_INVALID_BATTERY,
)
_POINT = ("form", "target_C", "base", "bot", "coupling")
_ROW_KEYS = frozenset({"kind", "R", *_POINT, "per_seed", "value"})
_SWEEP_KEYS = frozenset({"R", *_POINT, "reachable", "pass", "no_go", "per_seed"})


def _scalars(x: dict[str, Any], keys: tuple[str, ...]) -> bool:
    """点の欄が文字列か数値 (JSON の真偽値は数値に数えない)."""
    return all(
        isinstance(x[k], (str, int, float)) and not isinstance(x[k], bool) for k in keys
    )


def _num(x: object) -> float:
    """数値なら float、それ以外 (JSON の真偽値を含む) は NaN."""
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return float(x)
    return float("nan")


def _same_json(a: object, b: object) -> bool:
    """型まで含めた一致 (1.0 と true、2000 と 2000.0 を区別する)。キーの順は問わない."""
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _close(a: float, b: float) -> bool:
    return math.isfinite(a) and math.isfinite(b) and abs(a - b) <= 1e-12


def rates_ok(p: object, n_sims: int) -> bool:
    """1 seed の結果が率の組として妥当か (4 判定の率が有限で [0, 1]・合計 1・n_sims 回の格子の上・実現 C が有限)."""
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
        and len(per_seed) == len(REGISTERED_SEEDS)
        and all(rates_ok(p, n_sims) for p in per_seed)
    )


def _row_value(kind: str, per_seed: list[dict[str, float]]) -> float:
    n = len(per_seed)
    if kind == "power_pass":
        return sum(p[sc.VERDICT_PASS] for p in per_seed) / n
    if kind == "power_no_go":
        return sum(p[sc.VERDICT_ABSENT] for p in per_seed) / n
    if kind in ("band", "band_diag"):
        return (
            sum(1.0 - p[sc.VERDICT_PASS] - p[sc.VERDICT_ABSENT] for p in per_seed) / n
        )
    if kind == "size_pass":
        return max(p[sc.VERDICT_PASS] for p in per_seed)
    return max(p[sc.VERDICT_ABSENT] for p in per_seed)


def recheck_r(res: dict[str, Any]) -> list[str]:
    """1 つの R について、行の per_seed から値・4 条件・閾値を独立に再計算し、記録と照合する."""
    out: list[str] = []
    r_count = res.get("R")
    rows = res.get("rows")
    if not isinstance(r_count, int) or isinstance(r_count, bool):
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
    if keys != expected_points() or len(rows) != len(keys):
        out.append(f"sketch R{r_count}: rows differ from the points the rule requires")
    if any(x["R"] != r_count for x in rows):
        out.append(f"sketch R{r_count}: a row's R differs from its block")
    values: dict[str, list[float]] = {}
    for x in rows:
        kind = x["kind"]
        n_sims = (
            REGISTERED_N_SIM_SIZE if kind.startswith("size") else REGISTERED_N_SIM_POWER
        )
        if not per_seed_ok(x["per_seed"], n_sims):
            out.append(
                f"sketch R{r_count}: a row's per-seed results are not one valid set of rates per seed"
            )
            continue
        v = _row_value(kind, x["per_seed"])
        if not _close(v, _num(x["value"])):
            out.append(
                f"sketch R{r_count}: a row value differs from its per-seed results"
            )
        values.setdefault(kind, []).append(v)
    sizes = values.get("size_pass", []) + values.get("size_no_go", [])
    n_checks = len(sizes) * len(REGISTERED_SEEDS)
    x_max = registered_size_threshold(n_checks) if n_checks else -1
    calibrated = all(
        isinstance(p, dict)
        and abs(_num(p.get("realized_C")) - _num(x["target_C"])) <= CALIBRATION_TOL
        for x in rows
        for p in (x["per_seed"] if isinstance(x["per_seed"], list) else [None])
    )
    flags = {
        "calibrated": calibrated,
        "power_ok": all(v >= POWER_TARGET for v in values.get("power_pass", [])),
        "no_go_ok": all(v >= POWER_TARGET for v in values.get("power_no_go", [])),
        "band_ok": all(v <= 0.2 + 1e-12 for v in values.get("band", [])),
        "size_ok": all(round(v * REGISTERED_N_SIM_SIZE) <= x_max for v in sizes),
    }
    for flag, want in flags.items():
        if res.get(flag) is not want:
            out.append(
                f"sketch R{r_count}: {flag} differs from a recomputation from the rows"
            )
    if (
        res.get("n_size_checks") != n_checks
        or res.get("size_count_threshold") != x_max
        or not _close(_num(res.get("size_cap")), x_max / REGISTERED_N_SIM_SIZE)
    ):
        out.append(
            f"sketch R{r_count}: the size threshold differs from a recomputation"
        )
    if sizes and not _close(_num(res.get("worst_size")), max(sizes)):
        out.append(f"sketch R{r_count}: worst_size differs from a recomputation")
    n_units = 12 * r_count
    if res.get("n_units") != n_units or res.get("calls") != 4 * n_units:
        out.append(
            f"sketch R{r_count}: the unit and call counts differ from the design"
        )
    return list(dict.fromkeys(out))


def expected_params() -> dict[str, Any]:
    """見取り図の凍結する設定 (``sim.params`` と同じ形。sim と独立に書く)."""
    params = {
        "R_candidates": list(REGISTERED_R),
        "grid": list(REGISTERED_GRID),
        "n_sim_power": REGISTERED_N_SIM_POWER,
        "n_sim_size": REGISTERED_N_SIM_SIZE,
        "seeds": list(REGISTERED_SEEDS),
        "tau": 0.30,
        "alpha": 1 / ALPHA_DEN,
        "delta_plant": 0.6,
        "power_target": POWER_TARGET,
        "undecided_max": 0.2,
        "calibration_tol": CALIBRATION_TOL,
        "band_delta": 0.05,
        "band_bases": list(BAND_BASES),
        "mc_fwer": 1 / FWER_DEN,
        "oov": 0.05,
        "skew": 0.7,
        "lambda_fractions": [0.25, 0.5, 0.75, 1.0],
        "weak_null": {"p_up": 5.0 / 7.0, "up": 0.4, "down": -1.0},
        "reverse_fraction": 1.0 / 6.0,
    }
    return json.loads(json.dumps(params))


def recompute_selection(per_r: list[dict[str, Any]]) -> dict[str, Any]:
    """選定規則 (4 条件を満たし較正された候補のうち最大、無ければ door-close) を sim と独立に計算する."""
    flags = ("power_ok", "no_go_ok", "size_ok", "band_ok", "calibrated")
    ok = [x["R"] for x in per_r if all(x.get(f) is True for f in flags)]
    return (
        {"selected_R": max(ok), "door_close": False}
        if ok
        else {"selected_R": None, "door_close": True}
    )


def _sweep_nuisances(form: str) -> tuple[tuple[str, sim.Nuisance], ...]:
    """sweep の 2 攪乱点 (登録から。対数オッズは label_skew に固定)."""
    out = []
    for kind, (base, bot, coupling) in REGISTERED_SWEEP_NUISANCES.items():
        out.append(
            (
                kind,
                sim.Nuisance(
                    "label_skew" if form == "logodds" else base, bot, coupling
                ),
            )
        )
    return tuple(out)


@functools.cache
def _reach(form: str, base: str, bot: float, r_count: int) -> float:
    return registered_reach(form, base, bot, r_count)


def expected_sweep_points() -> set[tuple[Any, ...]]:
    """sweep が要る (R, form, target, base, bot, coupling) の全点 (登録と独立な到達上限から)."""
    pts: set[tuple[Any, ...]] = set()
    for r_count in REGISTERED_R:
        for form in REGISTERED_FORMS:
            for _, nu in _sweep_nuisances(form):
                reach = _reach(form, nu.base, nu.bot, r_count)
                pts |= {
                    (r_count, form, t, nu.base, nu.bot, nu.coupling)
                    for t in REGISTERED_GRID
                    if t <= reach + 1e-9
                }
    return pts


def favorable_reaches(sweeps: list[dict[str, Any]]) -> bool:
    """最も有利な行 (一様 sd 0.05・uniform・⊥ 0・crn) が 2τ で power 0.8 に届くか (sim と独立に計算する)."""
    return any(
        x["form"] == "homog_sd005"
        and (x["base"], x["bot"], x["coupling"])
        == REGISTERED_SWEEP_NUISANCES["favorable"]
        and abs(_num(x["target_C"]) - 0.6) < 1e-9
        and _num(x["pass"]) >= 0.8
        for x in sweeps
    )


def sweep_boundaries(sweeps: list[dict[str, Any]]) -> dict[str, Any]:
    """境目の表を sweep の行から計算し直す (``sim.sweep_boundaries`` と同じ形。補間は manifest の独立な実装)."""
    out: dict[str, Any] = {}
    for r in REGISTERED_R:
        out[f"R{r}"] = {}
        for form in REGISTERED_FORMS:
            out[f"R{r}"][form] = {}
            for kind, nu in _sweep_nuisances(form):
                rows = [
                    x
                    for x in sweeps
                    if x["R"] == r
                    and x["form"] == form
                    and (x["base"], x["bot"], x["coupling"])
                    == (nu.base, nu.bot, nu.coupling)
                ]
                out[f"R{r}"][form][kind] = {
                    "pass_08": registered_boundary(
                        [(x["target_C"], x["pass"]) for x in rows]
                    ),
                    "no_go_08": registered_boundary(
                        [(x["target_C"], x["no_go"]) for x in rows], rising=False
                    ),
                }
    return out


def sweep_violations(sketch: dict[str, Any]) -> list[str]:
    """sweep の完全性・行の到達上限・per_seed との整合・最有利行の到達・境目を照合する."""
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
        if not isinstance(x["R"], int) or x["form"] not in REGISTERED_FORMS:
            out.append("sketch: a sweep row's R or form is not registered")
            continue
        reach = _reach(x["form"], x["base"], x["bot"], x["R"])
        if not _close(_num(x["reachable"]), reach):
            out.append("sketch: a sweep row's reachable differs from a recomputation")
        if not per_seed_ok(x["per_seed"], REGISTERED_N_SIM_POWER):
            out.append("sketch: a sweep row's per-seed results are not valid rates")
            continue
        n = len(REGISTERED_SEEDS)
        if not _close(
            _num(x["pass"]), sum(p[sc.VERDICT_PASS] for p in x["per_seed"]) / n
        ):
            out.append("sketch: a sweep row's pass differs from its per-seed results")
        if not _close(
            _num(x["no_go"]), sum(p[sc.VERDICT_ABSENT] for p in x["per_seed"]) / n
        ):
            out.append("sketch: a sweep row's no_go differs from its per-seed results")
        if any(
            abs(_num(p["realized_C"]) - _num(x["target_C"])) > CALIBRATION_TOL
            for p in x["per_seed"]
        ):
            out.append("sketch: a sweep row is not calibrated to its target")
    if sketch.get("most_favorable_reaches") is not favorable_reaches(sweeps):
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
    if sketch.get("R_run") != list(REGISTERED_R):
        out.append("sketch: R_run does not cover the R candidates")
    per_r = sketch.get("per_R")
    if (
        not isinstance(per_r, list)
        or not all(isinstance(x, dict) for x in per_r)
        or [x.get("R") for x in per_r] != list(REGISTERED_R)
    ):
        return [*out, "sketch: per_R does not cover the R candidates"]
    for res in per_r:
        out += recheck_r(res)
    if sketch.get("selection") != recompute_selection(per_r):
        out.append("sketch: the selection differs from a recomputation of the rule")
    out += sweep_violations(sketch)
    return out


def fixture_violations(table: dict[str, Any]) -> list[str]:
    out: list[str] = []
    fresh = {f"R{r}": fx.fixture_table(r) for r in REGISTERED_R}
    if table.get("tables") != json.loads(json.dumps(fresh)):
        out.append("fixture table: differs from a recomputation with the current code")
    if table.get("passed") is not True:
        out.append("fixture table: the τ/4 gate failed")
    return out


# ------------------------------------------------------------- 第 2 段の証拠


def driver_certification_violations(cert: object, root: pathlib.Path) -> list[str]:
    """driver の certification の契約 (第 1 段で固定)."""
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
    """pilot の機械判定を凍結した関数で入力から再計算し、記録と照合する."""
    if not isinstance(gate, dict):
        return ["pilot gate: missing"]
    out: list[str] = []
    try:
        samples = sc.load_records(
            (root / PILOT_RECORDS).read_text(encoding="utf-8").split("\n")
        )
        meta = json.loads((root / PILOT_META).read_text(encoding="utf-8"))
    except (OSError, ValueError, sc.RecordError):
        return ["pilot gate: the pilot records cannot be read"]
    fresh = pg.decide_pilot(
        samples,
        meta,
        certified=sc.load_certification(root / CERT),
        selected_r=selected_r if type(selected_r) is int else None,
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
    # provenance は driver と、その driver が書いた records・meta を同時に結ぶ
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
    selected = sel.get("selected_R")
    if (
        sel.get("door_close") is not False
        or type(selected) is not int
        or selected not in REGISTERED_R
    ):
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
            selected,
            root,
        )
        out += driver_certification_violations(_load_optional(root, DRIVER_CERT), root)
    return out


def _load(root: pathlib.Path) -> tuple[dict[str, Any], ...] | str:
    try:
        return tuple(
            json.loads((root / p).read_text(encoding="utf-8"))
            for p in (CERT, SKETCH, FIXTURES)
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
    cert, sketch, fixtures = loaded
    return (
        certification_violations(cert, root)
        + sketch_violations(sketch, root)
        + fixture_violations(fixtures)
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
