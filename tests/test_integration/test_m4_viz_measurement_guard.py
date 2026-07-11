"""M4 situated-3D — Issue 001 (I1): AC5 measurement-zero guard (.py AST + .gd text).

Issue ``loop/20260711-m13-m4-code/issues/001-measurement-gpl-guard.md`` of the
FROZEN M4 impl-design ADR ``.steering/20260711-m13-m4-impl-design/design-final.md``
(§5 AC5 measurement-zero guard, §10 AC5, §11 不可侵). This module is the **machine
guarantee** that every file the M4 3D-visualisation Loop adds (layout/parser tool,
geometry ``.glb`` exporters, the ``SocietyReplayViewer`` GDScript, and the new test
modules) computes and emits **no** measurement surface: no floor / landscape /
verdict / scorer / divergence / ``D_*`` statistic, no ``erre_sandbox.evidence``
(or sibling measurement-line package) import, and no aggregation/distribution
surface (numpy / pandas / scipy / statistics / ``Counter`` / ``groupby`` /
``math.log``). Construction, not measurement — R-budget stays 0.

Mirrors the ``_measurement_guard.py`` 3-hole AST guard (ECL v1, Codex HIGH-2) and
the M2 ``test_m2_society_spend_guard.py`` landed precedent (import denylist +
aggregation ban + executable-AST-only identifier scan + ``.gd`` text scan +
negative fixture + self-scan). The guard logic lives inline in this one test
module (this issue's Allowed Files list only this test + the GPL boundary test +
an SPDX-header line on ``export_chashitsu.py``).

NOT a structural-floor verdict; verdict は holding. This module computes no floor
/ verdict / scorer / divergence itself — every test here only asserts such a
surface is *absent* from the files it scans. It scans the M4-new files
**dynamically** (existing files only, so it never breaks while I2-I6 files are
still absent, and auto-covers them once they land — I6 re-confirms full coverage).

Codex HIGH-1 / MEDIUM-2 reflected:

* **HIGH-1** — the identifier scan inspects **executable AST identifier
  positions only** (Store-context ``Name`` / ``AnnAssign`` target / ``FunctionDef``
  / ``ClassDef`` / ``arg``), never a bare string constant, so a docstring/comment
  that merely *mentions* "floor" / "verdict" never self-trips the guard.
* **MEDIUM-2** — the denylist is split by guard kind to suppress false positives:
  ``divergence`` / ``verdict`` / ``scorer`` are banned as identifier substrings
  everywhere; ``floor`` is banned as an identifier only in the layout/parser/test
  tier (geometry exporters and GDScript legitimately use "floor" for building
  floors / Godot's ``floor()`` built-in, so the geometry tier and the ``.gd``
  scan drop the bare-``floor`` identifier ban and rely on the import /
  aggregation / emit / exact-key guards instead). ``evidence`` / ``spdm`` /
  ``runningness`` / ``landscape`` / ``D_*`` / ``bank`` are matched on the import
  module-path segment + emitted dict-key / artifact-filename axis, not as broad
  identifier substrings.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Final

import pytest

_REPO_ROOT: Final = Path(__file__).resolve().parents[2]
_THIS_FILE: Final = Path(__file__)


# --------------------------------------------------------------------------- #
# Denylists (pinned; scoping HIGH-1 全幅, split by guard kind per MEDIUM-2)
# --------------------------------------------------------------------------- #

_BANNED_IMPORT_SUBSTR: Final[tuple[str, ...]] = (
    "evidence",
    "spdm",
    "runningness",
    "landscape",
    "floor",
    "divergence",
    "verdict",
    "scorer",
    "es2_replay",
    "d0_substrate",
    "memory_recomp_conformance",
    "bank",
)
"""Measurement-line module fragments banned from any ``import`` path segment or
dynamic-import string constant (belt-and-suspenders; no M4 construction file has
a legitimate reason to import any of these)."""

# Identifier substring ban, split by tier (MEDIUM-2 false-positive mitigation).
_IDENTIFIER_BAN_FULL: Final[tuple[str, ...]] = (
    "floor",
    "divergence",
    "verdict",
    "scorer",
)
"""Layout / parser / test tier — no legitimate geometry vocabulary, so bare
``floor`` is safe to ban here."""

_IDENTIFIER_BAN_GEOMETRY: Final[tuple[str, ...]] = ("divergence", "verdict", "scorer")
"""Geometry ``.glb`` exporters + GDScript — ``floor`` dropped (building floors /
Godot ``floor()`` are legitimate; measurement-floor re-entry is still caught by
the import / aggregation / exact-key emit guards)."""

_BANNED_AGGREGATION_MODULES: Final[tuple[str, ...]] = (
    "numpy",
    "pandas",
    "scipy",
    "statistics",
)
_BANNED_FROM_IMPORT: Final[dict[str, frozenset[str]]] = {
    "math": frozenset({"log"}),
    "collections": frozenset({"Counter"}),
    "itertools": frozenset({"groupby"}),
}

# Emit guard (hole-3): a measurement name used as a dict **key** (exact) or a
# ``.json`` / ``.jsonl`` artifact **filename** — an emitted annotation surface.
_BANNED_EMIT_KEY_EXACT: Final[frozenset[str]] = frozenset(
    {
        "d_loco",
        "d_running",
        "floor",
        "landscape",
        "divergence",
        "verdict",
        "scorer",
        "spdm",
        "runningness",
    }
)
_BANNED_EMIT_FILENAME_SUBSTR: Final[tuple[str, ...]] = (
    "verdict",
    "scorer",
    "divergence",
    "landscape",
    "spdm",
    "runningness",
    "d_loco",
)

# GDScript text-scan token denylist (reduced: bare ``floor`` dropped, Godot's
# ``floor()`` built-in is legitimate).
_GD_BANNED_TOKENS: Final[tuple[str, ...]] = (
    "evidence",
    "spdm",
    "runningness",
    "landscape",
    "divergence",
    "verdict",
    "scorer",
    "es2_replay",
    "d0_substrate",
    "bank_scorer",
    "d_loco",
)


# --------------------------------------------------------------------------- #
# Dynamic collection of the M4-new files (existing only, glob-based)
# --------------------------------------------------------------------------- #


def _existing(paths: list[Path]) -> list[Path]:
    return [p for p in paths if p.is_file()]


def _m4_layout_and_test_python() -> list[Path]:
    """Layer-A python (layout tool, GLB-JSON parser helper, M4 test modules) —
    full identifier ban (incl bare ``floor``)."""
    fixed = [
        _REPO_ROOT / "scripts" / "export_zone_layout.py",
        _REPO_ROOT / "tests" / "_glb_json.py",
    ]
    globbed: list[Path] = []
    for sub in ("test_integration", "test_architecture"):
        globbed.extend((_REPO_ROOT / "tests" / sub).glob("test_m4_*.py"))
    return _existing(fixed) + sorted(globbed)


def _m4_geometry_python() -> list[Path]:
    """Geometry ``.glb`` exporters this Loop adds (reduced identifier ban).

    Globs ``erre-sandbox-blender/scripts/export_*.py`` minus the pre-existing
    (non-M4) legacy exporters — those carry legitimate ``floor`` geometry
    identifiers and are out of the M4-new scan (their GPL boundary is covered by
    ``test_m4_gpl_spdx_boundary.py``)."""
    legacy = {"export_chashitsu.py"}
    root = _REPO_ROOT / "erre-sandbox-blender" / "scripts"
    return sorted(p for p in root.glob("export_*.py") if p.name not in legacy)


def _m4_gdscript() -> list[Path]:
    """M4-new GDScript (the ``SocietyReplayViewer`` + any ``Society*`` helper).

    Pinned to the M4 ``Society*`` prefix so the frozen ``EclReplayPlayer.gd`` /
    ``FixturePlayer.gd`` (read-only apparatus) are never scanned."""
    dev = _REPO_ROOT / "godot_project" / "scripts" / "dev"
    return sorted(dev.glob("Society*.gd"))


# --------------------------------------------------------------------------- #
# .py AST guard (executable-AST-only, HIGH-1)
# --------------------------------------------------------------------------- #


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _import_paths(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
        return [node.module, *(f"{node.module}.{a.name}" for a in node.names)]
    return []


def _guard_imports(node: ast.AST) -> None:
    """Import-path denylist (segment substring) + dynamic-import string (hole-2)."""
    for full in _import_paths(node):
        low = full.lower()
        assert not any(tok in low for tok in _BANNED_IMPORT_SUBSTR), full
    if isinstance(node, ast.Call):
        func = node.func
        is_dyn = (isinstance(func, ast.Attribute) and func.attr == "import_module") or (
            isinstance(func, ast.Name) and func.id == "__import__"
        )
        if is_dyn:
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    low = arg.value.lower()
                    assert not any(tok in low for tok in _BANNED_IMPORT_SUBSTR), (
                        arg.value
                    )


def _alias_map(tree: ast.Module) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "." not in alias.name:
                    aliases[alias.asname or alias.name] = alias.name
    return aliases


def _guard_aggregation(node: ast.AST, alias_map: dict[str, str]) -> None:
    """numpy/pandas/scipy/statistics full-module ban + targeted from-import +
    aliased attribute access (``import collections as c; c.Counter()``)."""
    for full in _import_paths(node):
        assert not any(
            full == banned or full.startswith(f"{banned}.")
            for banned in _BANNED_AGGREGATION_MODULES
        ), full
    if isinstance(node, ast.ImportFrom) and node.module in _BANNED_FROM_IMPORT:
        banned_names = _BANNED_FROM_IMPORT[node.module]
        for alias in node.names:
            assert alias.name not in banned_names, f"{node.module}.{alias.name}"
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        resolved = alias_map.get(node.value.id, node.value.id)
        banned_attrs = _BANNED_FROM_IMPORT.get(resolved)
        if banned_attrs is not None:
            assert node.attr not in banned_attrs, f"{resolved}.{node.attr}"


def _guard_identifiers(node: ast.AST, tokens: tuple[str, ...]) -> None:
    """Banned-identifier scan — executable-AST identifier positions only, never a
    bare string constant (HIGH-1: docstrings/comments never self-trip)."""
    names: list[str] = []
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
        names.append(node.id)
    elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
        # Assignment/annotation target attribute — ``self.verdict = ...`` /
        # ``obj.scorer = ...`` (the ``.attr`` in a Store context).
        names.append(node.attr)
    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        names.append(node.target.id)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        names.append(node.name)
    elif isinstance(node, ast.arg):
        names.append(node.arg)
    elif isinstance(node, ast.keyword) and node.arg is not None:
        # A keyword-argument name at a call site — ``emit(floor=...)`` (``**kw``
        # unpacking carries ``arg is None`` and is skipped).
        names.append(node.arg)
    for name in names:
        low = name.lower()
        assert not any(tok in low for tok in tokens), name


def _guard_emit(node: ast.AST) -> None:
    """Hole-3: a measurement name as a dict **key** (exact) or a ``.json`` /
    ``.jsonl`` artifact filename carrying a measurement token."""
    if isinstance(node, ast.Dict):
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                assert key.value.lower() not in _BANNED_EMIT_KEY_EXACT, key.value
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        low = node.value.lower()
        if low.endswith((".json", ".jsonl")):
            stem = low.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            assert stem not in _BANNED_EMIT_KEY_EXACT, node.value
            assert not any(tok in stem for tok in _BANNED_EMIT_FILENAME_SUBSTR), (
                node.value
            )


def assert_no_measurement_surface_py(
    tree: ast.Module, *, identifier_tokens: tuple[str, ...]
) -> None:
    """The full .py guard: import denylist + aggregation ban + executable-AST
    identifier ban + emit (dict-key / filename) guard."""
    alias_map = _alias_map(tree)
    for node in ast.walk(tree):
        _guard_imports(node)
        _guard_aggregation(node, alias_map)
        _guard_identifiers(node, identifier_tokens)
        _guard_emit(node)


# --------------------------------------------------------------------------- #
# .gd text guard (regex/text scan, comment-stripped)
# --------------------------------------------------------------------------- #


def _strip_gd_comments(src: str) -> str:
    """Remove ``#`` comments respecting ``"``/``'`` string literals, so a banned
    token that appears only in a GDScript comment is not flagged (the ``.gd``
    analogue of the HIGH-1 docstring exclusion)."""
    out_lines: list[str] = []
    for line in src.splitlines():
        quote: str | None = None
        cut = len(line)
        i = 0
        n = len(line)
        while i < n:
            ch = line[i]
            if quote is not None:
                if ch == "\\":
                    # Backslash escape inside a string literal: skip the escaped
                    # char so an escaped quote (``"a \" # b"``) does not close the
                    # string early and mis-classify a ``#`` inside it as a comment.
                    i += 2
                    continue
                if ch == quote:
                    quote = None
            elif ch in ('"', "'"):
                quote = ch
            elif ch == "#":
                cut = i
                break
            i += 1
        out_lines.append(line[:cut])
    return "\n".join(out_lines)


def assert_no_measurement_in_gdscript(src: str) -> None:
    """No banned measurement token appears in the code (comment-stripped) text."""
    code = _strip_gd_comments(src).lower()
    for tok in _GD_BANNED_TOKENS:
        assert not re.search(re.escape(tok), code), tok


# --------------------------------------------------------------------------- #
# I1-G1 — no measurement import/identifier/emit in the M4-new .py surface
# --------------------------------------------------------------------------- #


def test_m4_viz_no_measurement_import_or_emit() -> None:
    """AC I1-G1: every M4-new ``.py`` file (layout/parser/test tier = full ban,
    geometry exporter tier = reduced ban) carries no measurement import /
    identifier / aggregation / emitted-key surface — executable AST only."""
    for path in _m4_layout_and_test_python():
        assert_no_measurement_surface_py(
            _parse(path), identifier_tokens=_IDENTIFIER_BAN_FULL
        )
    for path in _m4_geometry_python():
        assert_no_measurement_surface_py(
            _parse(path), identifier_tokens=_IDENTIFIER_BAN_GEOMETRY
        )

    # Self-scan: this guard module is itself an M4-new ``test_m4_*`` file (picked
    # up by the glob above), so its own executable AST is already covered — the
    # explicit restatement here documents the M2 I6-G5 self-scan convention.
    assert _THIS_FILE in _m4_layout_and_test_python()


# --------------------------------------------------------------------------- #
# I1-G2 — no measurement token in the M4-new .gd surface
# --------------------------------------------------------------------------- #


def test_m4_viz_gdscript_no_measurement() -> None:
    """AC I1-G2: every M4-new ``.gd`` file's code text carries no banned
    measurement token (import/preload path, identifier, dict key, artifact
    filename). Skips cleanly while the viewer (I5) is not yet landed."""
    for path in _m4_gdscript():
        assert_no_measurement_in_gdscript(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# I1-G3 — the guard actually trips on a planted measurement surface (efficacy)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "src",
    [
        "from erre_sandbox import evidence\n",
        "from erre_sandbox.evidence import spdm\n",
        "import erre_sandbox.evidence.es2_replay\n",
        "from erre_sandbox.evidence.d0_substrate import x\n",
        "from erre_sandbox.evidence import runningness\n",
        "from erre_sandbox.evidence import landscape_divergence\n",
        "import bank_scorer\n",
        "import numpy\n",
        "import numpy as np\n",
        "from numpy import array\n",
        "import pandas\n",
        "import scipy\n",
        "import statistics\n",
        "from math import log\nx = log(2)\n",
        "import math\nx = math.log(2)\n",
        "from collections import Counter\nc = Counter()\n",
        "import collections as c\nx = c.Counter()\n",
        "from itertools import groupby\n",
        "floor_value = 1\n",
        "def compute_floor():\n    pass\n",
        "def build_verdict():\n    pass\n",
        "divergence_metric = 0.0\n",
        "class ScorerObject:\n    pass\n",
        'd = {"d_loco": 0.0}\n',
        'path = "results/spdm_verdict.jsonl"\n',
        'importlib.import_module("erre_sandbox.evidence.spdm")\n',
        # Attribute-target (Store) assignments — MEDIUM: previously missed.
        "self.verdict = 1\n",
        "obj.scorer = 2\n",
        "self.divergence: float = 0.0\n",
        # Keyword-argument name at a call site — MEDIUM: previously missed.
        "emit(floor=3)\n",
        "record(scorer=obj)\n",
    ],
)
def test_m4_viz_guard_catches_negative_fixture(src: str) -> None:
    """AC I1-G3 (.py): each planted measurement escape hatch trips the full-tier
    ``.py`` guard (efficacy witness — the guard is not vacuous)."""
    with pytest.raises(AssertionError):
        assert_no_measurement_surface_py(
            ast.parse(src), identifier_tokens=_IDENTIFIER_BAN_FULL
        )


def test_m4_viz_guard_geometry_tier_allows_building_keyword() -> None:
    """MEDIUM-2 tier policy: a building-floor attribute/keyword is legitimate
    vocabulary in the geometry exporter tier and must NOT trip that tier's guard,
    while the FULL tier still catches it (proving the tier split is deliberate)."""
    # Geometry tier: bare ``floor`` dropped — building-floor vocabulary allowed.
    assert_no_measurement_surface_py(
        ast.parse("place(floor=3)\nself.floor_height = 0.15\n"),
        identifier_tokens=_IDENTIFIER_BAN_GEOMETRY,
    )
    # But ``verdict`` / ``scorer`` attribute+keyword still trip the geometry tier.
    with pytest.raises(AssertionError):
        assert_no_measurement_surface_py(
            ast.parse("self.verdict = 1\n"), identifier_tokens=_IDENTIFIER_BAN_GEOMETRY
        )
    # And the FULL tier still catches ``floor=`` (layout/parser/test tier).
    with pytest.raises(AssertionError):
        assert_no_measurement_surface_py(
            ast.parse("place(floor=3)\n"), identifier_tokens=_IDENTIFIER_BAN_FULL
        )


@pytest.mark.parametrize(
    "src",
    [
        'const SPDM = preload("res://evidence/scorer.gd")\n',
        "var verdict_value = 1\n",
        'var out = {"divergence": 0.0}\n',
        'save_json("runningness_landscape.json")\n',
        "var s = scorer.compute()\n",
    ],
)
def test_m4_viz_guard_catches_negative_fixture_gd(src: str) -> None:
    """AC I1-G3 (.gd): each planted measurement token trips the ``.gd`` text
    guard (efficacy witness for the GDScript scanner)."""
    with pytest.raises(AssertionError):
        assert_no_measurement_in_gdscript(src)


# --------------------------------------------------------------------------- #
# I1-G4 — docstring / comment content is never flagged (HIGH-1)
# --------------------------------------------------------------------------- #


def test_m4_viz_gd_comment_strip_respects_escapes() -> None:
    """MEDIUM (.gd escape): an escaped quote inside a string literal must not be
    treated as closing the string — otherwise a ``#`` inside the string is
    mis-read as a comment start, silently hiding real denylist code after it."""
    # WITHOUT escape handling, the ``\"`` closes the string early, the ``#`` is
    # taken as a comment, and the trailing ``scorer`` code is stripped away
    # (a missed detection). With escape handling the string stays open through
    # the ``#`` and the real ``scorer`` identifier is caught.
    with pytest.raises(AssertionError):
        assert_no_measurement_in_gdscript('var s = "x \\" #"\nvar scorer = 1\n')

    # A legitimate string containing an escaped quote (no denylist token in real
    # code) must NOT trip — the escape must not corrupt normal parsing.
    assert_no_measurement_in_gdscript('var label = "a \\" b"\nvar y = floor(3.7)\n')


def test_m4_viz_guard_docstring_not_flagged() -> None:
    """AC I1-G4: banned words appearing only in docstrings/comments (``.py``) or
    ``#`` comments (``.gd``) are never flagged — the guard scans executable
    identifier positions / comment-stripped code only (HIGH-1)."""
    py_src = ast.parse(
        '''
"""Module docstring mentioning floor, divergence, verdict, scorer, evidence,
spdm and landscape as free text — none are identifiers, so no flag."""


def render_scene() -> str:
    """This construction viewer computes no floor / verdict / scorer /
    divergence — reproducibility only (offline .glb replay)."""
    zone_floor_height = 0.15  # a *comment* naming verdict/scorer must not trip
    return "ok"
'''
    )
    assert_no_measurement_surface_py(py_src, identifier_tokens=_IDENTIFIER_BAN_GEOMETRY)

    gd_src = (
        "# this viewer references verdict, scorer, divergence and evidence\n"
        "# only in comments — the scanner must strip these before matching.\n"
        "extends Node3D\n"
        "func _ready() -> void:\n"
        "    var y = floor(3.7)  # Godot floor() built-in, legitimate\n"
        "    print(y)\n"
    )
    assert_no_measurement_in_gdscript(gd_src)

    # Negative control: the same words as real identifiers / real code DO trip,
    # proving the exclusion above is a deliberate scope choice, not a blind guard.
    with pytest.raises(AssertionError):
        assert_no_measurement_surface_py(
            ast.parse("verdict = 'x'\n"), identifier_tokens=_IDENTIFIER_BAN_GEOMETRY
        )
    with pytest.raises(AssertionError):
        assert_no_measurement_in_gdscript("var scorer = 1\n")
