"""Shared ECL v1 measurement-line non-re-entry guard (Codex HIGH-2, ADR §G).

The enhanced 3-hole AST guard both v1 test modules
(``test_ecl_v1_locomotion.py`` and ``test_ecl_v1_live_golden.py``) apply to the
v1 apparatus (``live_v1.py`` / ``scripts/ecl_v1_live_capture.py``) and to
themselves — extracted here so the safety-critical guard logic lives in exactly
one place (mirrors the ``_ws_helpers.py`` shared-helper convention). This is a
non-test helper module (leading-underscore, no ``test_`` prefix), so pytest never
collects it and the guard's own self-scan never targets it.

The FROZEN ADR ``.steering/20260707-ecl-v1-adr/design-final.md`` §G binds the v1
apparatus to compute/emit **no** measurement surface (floor / landscape / verdict
/ divergence / an ``evidence`` import). This guard closes the three holes Codex
HIGH-2 identified over the v0 guard:

1. ``from erre_sandbox import evidence`` (an ``ImportFrom(module="erre_sandbox")``
   the classic prefix check misses).
2. a dynamic ``importlib.import_module("erre_sandbox.evidence…")`` / ``__import__``
   string constant.
3. a measurement name used as a dict **key** (exact match) or a ``.json`` /
   ``.jsonl`` **filename** — an emitted annotation surface, not just an identifier.

The **v0** guard in ``test_ecl_live_golden.py`` is intentionally left untouched
(ADR §H byte-invariance contract); this shared module scopes to the v1 files only.
"""

from __future__ import annotations

import ast

# Banned measurement imports/identifiers (superset of the v0 guard).
BANNED_IMPORT_PREFIX = ("erre_sandbox.evidence",)
BANNED_IMPORT_SUB = ("spdm", "runningness")
BANNED_IDENTIFIER_SUB = (
    "floor",
    "landscape",
    "verdict",
    "jaccard",
    "divergence",
    "r_min",
)
# Exact ES-3 measurement output names (ADR §G, Codex LOW-2: exact, not substring,
# so a legit "schema_conformance" key or a bare "verdict": None marker does not
# collide).
BANNED_MEASUREMENT_KEY_EXACT = frozenset(
    {
        "d_loco",
        "evaluate_verdict",
        "es3verdict",
        "amplitude",
        "headroom",
        "floor",
        "landscape",
        "divergence",
    }
)


def _guard_imports(node: ast.AST) -> None:
    """Hole 1 + classic import guard (every v1 file)."""
    if isinstance(node, ast.ImportFrom) and node.module is not None:
        assert not node.module.startswith(BANNED_IMPORT_PREFIX), node.module
        assert not any(s in node.module for s in BANNED_IMPORT_SUB), node.module
        if node.module == "erre_sandbox":  # hole 1: from erre_sandbox import evidence
            for alias in node.names:
                assert not alias.name.startswith("evidence"), alias.name
    if isinstance(node, ast.Import):
        for alias in node.names:
            assert not alias.name.startswith(BANNED_IMPORT_PREFIX), alias.name
            assert not any(s in alias.name for s in BANNED_IMPORT_SUB), alias.name


def _guard_identifiers(node: ast.AST) -> None:
    """Banned-identifier guard (every v1 file), mirrors the v0 guard."""
    names: list[str] = []
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
        names.append(node.id)
    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        names.append(node.target.id)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        names.append(node.name)
    elif isinstance(node, ast.arg):
        names.append(node.arg)
    for name in names:
        low = name.lower()
        assert not any(tok in low for tok in BANNED_IDENTIFIER_SUB), name


def _guard_dynamic_import(node: ast.AST) -> None:
    """Hole 2: a dynamic ``importlib.import_module``/``__import__`` string constant."""
    if not isinstance(node, ast.Call):
        return
    func = node.func
    is_dynamic_import = (
        isinstance(func, ast.Attribute) and func.attr == "import_module"
    ) or (isinstance(func, ast.Name) and func.id == "__import__")
    if not is_dynamic_import:
        return
    for arg in node.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            low = arg.value.lower()
            assert not low.startswith(BANNED_IMPORT_PREFIX), arg.value
            assert not any(s in low for s in BANNED_IMPORT_SUB), arg.value


def _guard_keys_and_filenames(node: ast.AST) -> None:
    """Hole 3: a measurement name as a dict **key** (exact) or a ``.json`` filename."""
    if isinstance(node, ast.Dict):
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                assert key.value.lower() not in BANNED_MEASUREMENT_KEY_EXACT, key.value
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        low = node.value.lower()
        if low.endswith((".json", ".jsonl")):
            stem = low.rsplit(".", 1)[0]
            assert stem not in BANNED_MEASUREMENT_KEY_EXACT, node.value
            assert not any(tok in stem for tok in BANNED_IDENTIFIER_SUB), node.value


def assert_no_measurement_surface_v1(tree: ast.Module, *, scan_strings: bool) -> None:
    """The enhanced 3-hole guard (Codex HIGH-2), superset of the v0 guard.

    Always (every v1 file): banned imports (incl. hole 1 —
    ``from erre_sandbox import evidence``) and banned identifiers.

    ``scan_strings`` (apparatus files only, never a test module which legitimately
    imports the banned lists): hole 2 — a dynamic
    ``importlib.import_module("erre_sandbox.evidence…")`` string constant; hole 3 —
    a measurement name used as a dict **key** (exact) or a ``.json`` / ``.jsonl``
    **filename** carrying a banned token. Free-text docstrings are never
    substring-scanned, so a scope-guard note that merely *mentions* ``evidence`` /
    ``spdm`` / ``divergence`` does not self-trip.
    """
    for node in ast.walk(tree):
        _guard_imports(node)
        _guard_identifiers(node)
        if scan_strings:
            _guard_dynamic_import(node)
            _guard_keys_and_filenames(node)
