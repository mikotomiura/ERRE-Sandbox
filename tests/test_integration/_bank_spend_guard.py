"""ECL B — bank spend/no-spend ast-guard (Codex HIGH-4 superset, §I4).

Issue 003 (``loop/20260708-m13-b-code-impl/issues/003-spend-ast-guard.md``) of
the FROZEN ADR ``.steering/20260707-m13-b-impl-design/design-final.md`` (§I4
spend/no-spend boundary, §B5.2 binding prohibition). This is a **non-test
helper module** (leading-underscore, no ``test_`` prefix), so pytest never
collects it and no guard here ever self-scans its own definitions — the same
convention as ``_measurement_guard.py`` (the shared ECL v1 measurement-line
guard this module extends).

The bank driver (``bank.py``/``bank_fixtures.py``, Issue 001/002) is a
*construction* apparatus that records **raw rows only**
(:class:`~erre_sandbox.integration.embodied.bank.BankLlmCallRecord`); Codex
HIGH-4 identified that a raw-row-only contract alone leaves an implicit
aggregation escape hatch — ``Counter`` / ``len(set(zone for ...))`` / a
``numpy``/``pandas`` one-liner can synthesize an ``H(zone|ctx)``-shaped proxy
statistic from those raw rows without ever importing the banned ``evidence.*``
measurement machinery the shared v1 guard already closes. This module adds
five independent guards that, together with the reused v1 guard, make that
escape hatch a machine-checked non-surface:

1. :func:`assert_no_aggregation_surface` — bans ``math.log`` /
   ``collections.Counter`` / ``itertools.groupby`` / a whole-module
   ``numpy``/``pandas``/``scipy``/``statistics`` import, **and** a
   ``set``/``{...}`` construct built over a zone-valued expression (the
   precise "set over zones" reading from the ADR: a legitimate
   ``{r.system_prompt for r in records}`` prompt-dedup set is never banned,
   only a set/comprehension whose element expression names a ``*zone*``
   attribute or identifier).
2. :func:`assert_no_adaptive_topup` — ``m_draws``/``k_contexts`` parameters
   must default to a frozen int literal (or a module-level frozen int
   constant reference, e.g. ``m_draws: int = BANK_M_GOLDEN``), and no
   ``while`` loop exists anywhere in the scanned module (the structural
   marker of a runtime top-up branch; the bake-out loop is ``for``-only by
   construction).
3. :func:`assert_bank_annotation_opaque` — an identifier-ban extension
   (mirrors ``_measurement_guard``'s substring-ban style) closing
   ``diversity``/``entropy``/``distinct``-shaped identifiers a B-side test
   could otherwise assert against.
4. :func:`assert_bank_import_allowlist` — a **closed** import allowlist for
   the bank modules (denylist-substring belt-and-suspenders on top), rather
   than an open-ended denylist that a new banned import could slip past.
5. :func:`assert_llm_call_cap` — a runtime (not AST) helper: fail-fast when
   an observed call count exceeds ``2 * m_draws * k_contexts`` (the
   ``.codex/budget.json``-style cost-ceiling precedent), the construction
   shakedown's own spend cap.

Free-text docstrings are never substring-scanned (mirrors
``_measurement_guard``'s "a scope-guard note that merely mentions a banned
token does not self-trip" convention) — every guard here walks only
``ast.Name``/``ast.Attribute``/``ast.arg``/``ast.FunctionDef``/``ast.ClassDef``/
``ast.Import``/``ast.ImportFrom``/``ast.Set``/``ast.SetComp``/``ast.Call``
nodes, never a bare ``ast.Constant`` string body.
"""

from __future__ import annotations

import ast
from typing import Final

from tests.test_integration._measurement_guard import assert_no_measurement_surface_v1

__all__ = [
    "assert_bank_annotation_opaque",
    "assert_bank_import_allowlist",
    "assert_bank_no_measurement_surface",
    "assert_llm_call_cap",
    "assert_no_adaptive_topup",
    "assert_no_aggregation_surface",
]

# --------------------------------------------------------------------------- #
# 1. Aggregation-surface ban (Codex HIGH-4)
# --------------------------------------------------------------------------- #

_BANNED_FULL_MODULES: Final[tuple[str, ...]] = (
    "numpy",
    "pandas",
    "scipy",
    "statistics",
)
"""Whole-module ban: no legitimate bank use exists for any of these, so the
entire module import is forbidden regardless of which symbol is pulled in."""

_BANNED_FROM_IMPORT: Final[dict[str, frozenset[str]]] = {
    "math": frozenset({"log"}),
    "collections": frozenset({"Counter"}),
    "itertools": frozenset({"groupby"}),
}
"""``from <module> import <name>`` bans targeted at the specific aggregation
symbol, not the whole (otherwise-benign) module — ``collections.abc`` /
``itertools.chain`` stay legal."""

_BANNED_ATTR_ACCESS: Final[dict[str, frozenset[str]]] = _BANNED_FROM_IMPORT
"""``<module>.<attr>`` attribute-access ban — covers the ``import math`` +
``math.log(...)`` usage form a from-import ban alone would miss."""

_ZONE_SUBSTRING: Final[str] = "zone"


def _full_import_names(node: ast.AST) -> list[str]:
    """Every dotted module path a single ``import`` statement pulls in."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
        return [node.module]
    return []


def _guard_full_module_ban(node: ast.AST) -> None:
    for name in _full_import_names(node):
        assert not any(
            name == banned or name.startswith(f"{banned}.")
            for banned in _BANNED_FULL_MODULES
        ), name


def _guard_targeted_from_import(node: ast.AST) -> None:
    if not isinstance(node, ast.ImportFrom) or node.module is None:
        return
    banned_names = _BANNED_FROM_IMPORT.get(node.module)
    if banned_names is None:
        return
    for alias in node.names:
        assert alias.name not in banned_names, f"{node.module}.{alias.name}"


def _guard_attr_access(node: ast.AST) -> None:
    """``import math`` + ``math.log(...)`` (or ``collections.Counter`` /
    ``itertools.groupby``) attribute-access usage form."""
    if not isinstance(node, ast.Attribute) or not isinstance(node.value, ast.Name):
        return
    banned_attrs = _BANNED_ATTR_ACCESS.get(node.value.id)
    if banned_attrs is None:
        return
    assert node.attr not in banned_attrs, f"{node.value.id}.{node.attr}"


def _references_zone(node: ast.AST) -> bool:
    """``True`` if any ``Name``/``Attribute`` under ``node`` names a zone field."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and _ZONE_SUBSTRING in sub.attr.lower():
            return True
        if isinstance(sub, ast.Name) and _ZONE_SUBSTRING in sub.id.lower():
            return True
    return False


def _guard_zone_set_aggregation(node: ast.AST) -> None:
    """A ``set``/``{...}`` construct over a zone-valued expression (an
    ``H(zone|ctx)`` proxy, Codex HIGH-4) — never a bare ``set``/``{...}`` over
    a non-zone field (e.g. a ``system_prompt`` dedup set stays legal)."""
    if isinstance(node, (ast.Set, ast.SetComp)):
        assert not _references_zone(node), "set literal/comprehension over a zone field"
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "set"
    ):
        for arg in node.args:
            assert not _references_zone(arg), "set(...) call over a zone field"


def assert_no_aggregation_surface(tree: ast.Module) -> None:
    """Codex HIGH-4: ban the implicit-aggregation ("H もどき") escape hatches.

    ``math.log`` / ``collections.Counter`` / ``itertools.groupby`` / a whole
    ``numpy``/``pandas``/``scipy``/``statistics`` import, and a
    ``set``/``{...}`` construct built over a zone-valued expression. A set
    over a non-zone field (e.g. prompt dedup) is never flagged — only the
    zone-aggregation reading of "set over zones" (§I4).
    """
    for node in ast.walk(tree):
        _guard_full_module_ban(node)
        _guard_targeted_from_import(node)
        _guard_attr_access(node)
        _guard_zone_set_aggregation(node)


def assert_bank_no_measurement_surface(tree: ast.Module, *, scan_strings: bool) -> None:
    """Superset guard for a bank apparatus file: the shared v1 3-hole guard
    (evidence/spdm/runningness/floor/landscape/verdict/divergence, reused
    unmodified) plus the Codex HIGH-4 aggregation-surface ban (§I4)."""
    assert_no_measurement_surface_v1(tree, scan_strings=scan_strings)
    assert_no_aggregation_surface(tree)


# --------------------------------------------------------------------------- #
# 2. No-adaptive-topup guard
# --------------------------------------------------------------------------- #

_FROZEN_PARAM_NAMES: Final[frozenset[str]] = frozenset({"m_draws", "k_contexts"})


def _module_level_int_constants(tree: ast.Module) -> dict[str, int]:
    """Module-level ``NAME: int = <literal>`` / ``NAME = <literal>`` constants."""
    constants: dict[str, int] = {}
    for node in tree.body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target, value = node.target, node.value
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            target, value = node.targets[0], node.value
        if target is None or value is None:
            continue
        if isinstance(value, ast.Constant) and isinstance(value.value, int):
            constants[target.id] = value.value
    return constants


def assert_no_adaptive_topup(tree: ast.Module) -> None:
    """I3-G3: M/K are frozen literals, never grown at runtime off an
    annotation read (§I4 ``adaptive top-up 禁止``).

    Two independent checks: (a) no ``while`` loop anywhere in the module —
    the bake-out M-loop is ``for``-only by construction (§I1.4), so a
    ``while`` is the structural marker of a runtime top-up branch; (b) every
    ``m_draws``/``k_contexts`` parameter default is either a bare int literal
    or a reference to a module-level frozen int constant (e.g.
    ``m_draws: int = BANK_M_GOLDEN``) — never a ``Call``/``Attribute`` that
    could resolve a value dynamically (e.g. from an annotation file).
    """
    for node in ast.walk(tree):
        assert not isinstance(node, ast.While), "adaptive top-up marker: a while loop"

    frozen = _module_level_int_constants(tree)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        positional = [*node.args.posonlyargs, *node.args.args]
        defaults = node.args.defaults
        paired = zip(
            positional[len(positional) - len(defaults) :], defaults, strict=True
        )
        for arg, default in paired:
            if arg.arg not in _FROZEN_PARAM_NAMES:
                continue
            if isinstance(default, ast.Constant) and isinstance(default.value, int):
                continue
            if isinstance(default, ast.Name) and default.id in frozen:
                continue
            msg = (
                f"{node.name}({arg.arg}=...) default is not a frozen int literal "
                "(adaptive top-up risk)"
            )
            raise AssertionError(msg)


# --------------------------------------------------------------------------- #
# 3. Annotation-opaque identifier guard
# --------------------------------------------------------------------------- #

_BANK_BANNED_IDENTIFIER_SUB: Final[tuple[str, ...]] = (
    "diversity",
    "entropy",
    "distinct",
)
_BANK_BANNED_IDENTIFIER_EXACT: Final[frozenset[str]] = frozenset(
    {
        "h",
        "h_zone",
        "hzone",
        "shannon_entropy",
        "zone_count",
        "count_zones",
        "n_distinct",
    }
)


def _guard_bank_identifiers(node: ast.AST) -> None:
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
        assert low not in _BANK_BANNED_IDENTIFIER_EXACT, name
        assert not any(tok in low for tok in _BANK_BANNED_IDENTIFIER_SUB), name


def assert_bank_annotation_opaque(tree: ast.Module) -> None:
    """I3-G4: the bank module + B-side test never compute/assert
    count/diversity/H/distinct-zone (§I4 ``annotation は B 側で opaque``)."""
    for node in ast.walk(tree):
        _guard_bank_identifiers(node)


# --------------------------------------------------------------------------- #
# 4. Closed import allowlist
# --------------------------------------------------------------------------- #

_ALLOWED_STDLIB_PREFIXES: Final[tuple[str, ...]] = (
    "__future__",
    "os",
    "contextlib",
    "dataclasses",
    "typing",
    "collections.abc",
    "json",
    "datetime",
)
_ALLOWED_ERRE_PREFIXES: Final[tuple[str, ...]] = (
    "erre_sandbox.cognition",
    "erre_sandbox.inference",
    "erre_sandbox.integration.embodied.loop",
    "erre_sandbox.integration.embodied.live",
    "erre_sandbox.integration.embodied.bank_fixtures",
    "erre_sandbox.memory",
    "erre_sandbox.schemas",
)
"""``erre_sandbox.integration.embodied.live`` is an *exact* boundary-safe
prefix (``full == prefix or full.startswith(prefix + ".")``) — it never
accidentally admits ``erre_sandbox.integration.embodied.live_v1`` (a sibling
module, not a sub-attribute of ``live``)."""

_DENIED_SUBSTRINGS: Final[tuple[str, ...]] = (
    "evidence",
    "d0_substrate",
    "es2_replay",
    "memory_recomp_conformance",
    "runningness",
    "landscape_divergence",
)
"""Belt-and-suspenders denylist (§I4): even if a future allowlist edit were
mistaken, none of these measurement-line module fragments may appear in a
bank-module import path."""


def _matches_prefix(full: str, prefixes: tuple[str, ...]) -> bool:
    return any(full == prefix or full.startswith(f"{prefix}.") for prefix in prefixes)


def _import_full_paths(node: ast.AST) -> list[str]:
    """Every dotted ``module.name`` path a single import statement admits."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        if node.level != 0 or node.module is None:
            return ["<relative-import>"]
        return [f"{node.module}.{alias.name}" for alias in node.names]
    return []


def assert_bank_import_allowlist(tree: ast.Module) -> None:
    """I3-G5: bank module import ⊆ closed allowlist ∧ ∩ denylist = ∅ (§I4)."""
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for full in _import_full_paths(node):
            assert not any(token in full for token in _DENIED_SUBSTRINGS), full
            allowed = _matches_prefix(
                full, _ALLOWED_STDLIB_PREFIXES
            ) or _matches_prefix(full, _ALLOWED_ERRE_PREFIXES)
            assert allowed, f"import not in bank allowlist: {full}"


# --------------------------------------------------------------------------- #
# 5. Runtime LLM call-cap helper
# --------------------------------------------------------------------------- #


def assert_llm_call_cap(actual_calls: int, m_draws: int, k_contexts: int) -> None:
    """Construction shakedown call cap (§I4, ``.codex/budget.json``-style cost
    ceiling): ``actual_calls`` must never exceed ``2 * m_draws * k_contexts``
    (T_on + T_off, each drawing ``m_draws`` times, over ``k_contexts``).
    Fail-fast (:class:`AssertionError`) the instant the cap is exceeded —
    powered/live spend authorization is out of this construction guard's
    scope (C-proper).
    """
    cap = 2 * m_draws * k_contexts
    assert actual_calls <= cap, f"actual_calls={actual_calls} exceeds cap={cap} (2*M*K)"
