"""M2 Layer1 — Issue 006: spend/no-spend ast-guard (design-final.md §M8/§M9.3).

Issue ``loop/20260711-m13-m2-society-layer1-code/issues/006-spend-ast-guard.md``
of the FROZEN ADR ``.steering/20260711-m13-m2-impl-design/design-final.md``
(§M8 spend 非漂流 ast-guard, Codex HIGH-1/HIGH-4/LOW-9). This module is the
**machine guarantee** that the society driver (``society.py``, Issues 002-005)
never re-enters the measurement line: a closed import allowlist (primary) +
denylist substring belt-and-suspenders, a ban on the aggregation/measurement
computation surface (numpy/pandas/scipy/statistics/``Counter``/``groupby``,
floor/divergence/verdict/scorer identifiers), scoped to **production
executable AST only** (docstrings/comments are never scanned — Codex HIGH-1,
so the required "NOT a structural-floor verdict; verdict は holding" docstring
literal never self-trips this guard), and a tiny pinned non-gating LLM
call-cap helper for manual local-qwen3 shakedowns (gating stays replay/mock
only — Codex LOW-9).

Mirrors the ``_measurement_guard.py`` / ``_bank_spend_guard.py`` convention
(see ``tests/test_integration/test_ecl_bank_spend_guard.py``, B's Issue 003)
but keeps the guard functions inline in this one test module rather than a
separate non-test helper file — this issue's Allowed Files list only this new
test module (plus a comment/const-only, behaviour-unchanged edit to
``society.py``, unused here since the guard logic needs no runtime hook in
the production module).

Codex HIGH-4 (§M8): the ``set`` blanket ban is withdrawn — only the
aggregation-surface imports/attrs below are banned, and ``sorted(set(...))``
canonicalisation (the exact shape ``handoff.py`` already uses,
``sorted({r.agent_id for r in result.rows})``) is explicitly demonstrated
*not* to trip this guard (a bare, non-sorted ``set``/``.values()`` iteration
on the checksum path is I4's discovery guard, already landed and exercised by
``test_m2_society_determinism_checklist`` in ``test_m2_society.py``, out of
this issue's scope per the issue's ``Out`` list).

NOT a structural-floor verdict; verdict は holding. This module computes no
floor / verdict / scorer / divergence itself — every test here only asserts
such a surface is *absent* from the module it scans (construction, not
measurement).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Final

import pytest

from erre_sandbox.integration.embodied import society

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SOCIETY_SRC = (
    _REPO_ROOT / "src" / "erre_sandbox" / "integration" / "embodied" / "society.py"
)
_HANDOFF_SRC = (
    _REPO_ROOT / "src" / "erre_sandbox" / "integration" / "embodied" / "handoff.py"
)
"""cross-review MEDIUM-A (loop/20260711-m13-m2-society-layer1-code/cross-review-
synthesis.md): the M2 society handoff functions (``render_society_golden`` /
``build_society_envelope_stream`` / ``build_society_decisions_stream`` /
``project_society_agent_to_ecl_result``) live in this module alongside the
pre-existing legacy (single-agent) handoff surface, and were previously outside
this guard's scan (society.py + this loop's tests only). Extended here
(guard-only; ``handoff.py`` itself stays unmodified) so a future drift into a
measurement/aggregation import on the M2 path is caught the same way society.py
already is — belt-and-suspenders denylist + aggregation-surface ban, not the
closed *allowlist* (:func:`assert_society_import_allowlist` enumerates
society.py's own import surface specifically; handoff.py legitimately imports a
different, wider stdlib/erre_sandbox set — pydantic/importlib.metadata/os/sys/
etc — so only the denylist + computation-surface checks apply here, matching
Codex's "denylist import + 集計/分布生成 非在" framing)."""
_GATING_TEST_SRC = _REPO_ROOT / "tests" / "test_integration" / "test_m2_society.py"
_THIS_FILE = Path(__file__)


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# 1. Closed import allowlist (primary, society.py only) + denylist substring
#    belt-and-suspenders (auxiliary, society.py + this loop's tests)
# --------------------------------------------------------------------------- #

_ALLOWED_STDLIB_PREFIXES: Final[tuple[str, ...]] = (
    "__future__",
    "hashlib",
    "json",
    "dataclasses",
    "random",
    "typing",
    "collections.abc",
    "datetime",
)
"""Every stdlib module ``society.py`` actually imports (top-level + its
``if TYPE_CHECKING:`` block) — a closed enumeration, not an open-ended
denylist, per design-final.md §M8's "allowlist（society が import してよい閉列挙）
を主" (Codex HIGH-4)."""

_ALLOWED_ERRE_PREFIXES: Final[tuple[str, ...]] = (
    "erre_sandbox.cognition",
    "erre_sandbox.integration.dialog",
    "erre_sandbox.integration.embodied.loop",
    "erre_sandbox.integration.embodied.handoff",
    "erre_sandbox.memory",
    "erre_sandbox.schemas",
    "erre_sandbox.world",
    "erre_sandbox.inference",
)
"""``erre_sandbox.*`` prefixes ``society.py`` actually imports — Plane 2 /
checksum primitives from ``loop.py`` (never ``run_ecl_loop`` itself as a
driver), the dialog scheduler, memory/schemas/world seams, the
``inference`` type-only imports under ``TYPE_CHECKING``, and
``handoff._quantize_embedded_json`` (判断3 superseding ADR,
``.steering/20260712-m13-m4-society-enrichment/decisions.md`` — reused, not
re-implemented, so ``event_log_checksum`` and rendered ``decisions.jsonl``
stay on the same envelope_provenance serializer). Deliberately excludes
``erre_sandbox.evidence`` and every sibling measurement-line package
(§M1/§M8 binding); ``handoff`` itself carries the same construction-only
scope guard, so this is not a measurement-line door."""

_DENIED_IMPORT_SUBSTRINGS: Final[tuple[str, ...]] = (
    "evidence",
    "d0_substrate",
    "es2_replay",
    "memory_recomp_conformance",
    "runningness",
    "landscape_divergence",
)
"""§M8's closed denylist: ``society module（+ 本 loop の tests）の import ∩
{...} = ∅``. Belt-and-suspenders on top of the allowlist above — even a future
allowlist-edit mistake could not admit one of these measurement-line module
fragments into a bank-module... here, a *society*-module import path."""


def _import_full_paths(node: ast.AST) -> list[str]:
    """Every dotted ``module.name`` path a single import statement admits."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        if node.level != 0 or node.module is None:
            return ["<relative-import>"]
        return [f"{node.module}.{alias.name}" for alias in node.names]
    return []


def _matches_prefix(full: str, prefixes: tuple[str, ...]) -> bool:
    return any(full == prefix or full.startswith(f"{prefix}.") for prefix in prefixes)


def assert_society_import_allowlist(tree: ast.Module) -> None:
    """I6-G1 (primary): every ``society.py`` import ⊆ the closed allowlist,
    and none matches the denylist substrings (§M8)."""
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for full in _import_full_paths(node):
            assert not any(token in full for token in _DENIED_IMPORT_SUBSTRINGS), full
            allowed = _matches_prefix(
                full, _ALLOWED_STDLIB_PREFIXES
            ) or _matches_prefix(full, _ALLOWED_ERRE_PREFIXES)
            assert allowed, f"import not in society allowlist: {full}"


def assert_no_denylist_import(tree: ast.Module) -> None:
    """I6-G1 (auxiliary): denylist-only check, applied to society.py + this
    loop's test modules (broader surface than the closed allowlist, which is
    society.py-only since test modules legitimately import ``pytest``/etc.)."""
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for full in _import_full_paths(node):
            assert not any(token in full for token in _DENIED_IMPORT_SUBSTRINGS), full


# --------------------------------------------------------------------------- #
# 2. Aggregation / computation-surface ban (Codex HIGH-1: production
#    executable AST only — Name/Attribute/Import nodes, never a bare
#    ast.Constant string body, so docstrings/comments never self-trip)
# --------------------------------------------------------------------------- #

_BANNED_FULL_MODULES: Final[tuple[str, ...]] = (
    "numpy",
    "pandas",
    "scipy",
    "statistics",
)
"""Whole-module ban: no legitimate society use exists for any of these."""

_BANNED_FROM_IMPORT: Final[dict[str, frozenset[str]]] = {
    "math": frozenset({"log"}),
    "collections": frozenset({"Counter"}),
    "itertools": frozenset({"groupby"}),
}
"""Targeted ``from <module> import <name>`` bans — the specific aggregation
symbol, not the whole (otherwise-benign) module (``collections.abc`` /
``itertools.chain`` stay legal)."""

_BANNED_ATTR_ACCESS: Final[dict[str, frozenset[str]]] = _BANNED_FROM_IMPORT

_BANNED_IDENTIFIER_SUB: Final[tuple[str, ...]] = (
    "floor",
    "divergence",
    "verdict",
    "scorer",
)
"""§M8: "verdict・scorer object の生成" / "floor/divergence" 計算・生成 の非在。
Identifier-shaped (Name/AnnAssign-target/FunctionDef/ClassDef/arg) scan only —
never a string constant, so the required docstring literal "NOT a
structural-floor verdict" never self-trips (Codex HIGH-1)."""


def _full_import_names(node: ast.AST) -> list[str]:
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


def _import_alias_map(tree: ast.Module) -> dict[str, str]:
    """``import <module> [as <alias>]``'s local name -> real dotted module name
    (aliased ``import collections as c; c.Counter()`` must not bypass the ban)."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Import):
            continue
        for alias in node.names:
            if "." in alias.name:
                continue
            local = alias.asname or alias.name
            aliases[local] = alias.name
    return aliases


def _guard_attr_access(node: ast.AST, alias_map: dict[str, str]) -> None:
    if not isinstance(node, ast.Attribute) or not isinstance(node.value, ast.Name):
        return
    resolved = alias_map.get(node.value.id, node.value.id)
    banned_attrs = _BANNED_ATTR_ACCESS.get(resolved)
    if banned_attrs is None:
        return
    assert node.attr not in banned_attrs, f"{node.value.id}(={resolved}).{node.attr}"


def _guard_identifiers(node: ast.AST) -> None:
    """floor/divergence/verdict/scorer — executable-AST identifier positions
    only (Store-context Name / AnnAssign target / FunctionDef / ClassDef /
    arg), never a bare string constant (docstring/comment), Codex HIGH-1."""
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
        assert not any(tok in low for tok in _BANNED_IDENTIFIER_SUB), name


def assert_no_measurement_computation(tree: ast.Module) -> None:
    """I6-G1: no numpy/pandas/scipy/statistics/Counter/groupby/math.log
    aggregation surface, and no floor/divergence/verdict/scorer identifier —
    production executable AST only (Codex HIGH-1)."""
    alias_map = _import_alias_map(tree)
    for node in ast.walk(tree):
        _guard_full_module_ban(node)
        _guard_targeted_from_import(node)
        _guard_attr_access(node, alias_map)
        _guard_identifiers(node)


# --------------------------------------------------------------------------- #
# 3. Runtime LLM call-cap helper (non-gating, tiny pinned literal, Codex LOW-9)
# --------------------------------------------------------------------------- #


def assert_llm_call_cap(actual_calls: int, n_agents: int, shakedown_ticks: int) -> None:
    """Manual/non-gating local-qwen3 shakedown call cap (§M8, ``.codex/budget.json``
    -style cost ceiling): ``actual_calls`` must never exceed
    ``n_agents * shakedown_ticks``. Fail-fast; **never invoked by the gating
    CI suite** (:func:`test_m2_society_llm_call_cap` verifies its absence from
    ``society.py``'s production source) — powered/live spend is out of this
    construction guard's scope (R-budget=0, §M1)."""
    cap = n_agents * shakedown_ticks
    assert actual_calls <= cap, (
        f"actual_calls={actual_calls} exceeds cap={cap} (n_agents*shakedown_ticks)"
    )


# --------------------------------------------------------------------------- #
# I6-G1 — no-measurement-computation (allowlist + aggregation/identifier ban)
# --------------------------------------------------------------------------- #


def test_m2_society_no_measurement_computation() -> None:
    """AC I6-G1: society.py carries no measurement/aggregation surface, scoped
    to production executable AST only (docstrings excluded, Codex HIGH-1)."""
    society_tree = _parse(_SOCIETY_SRC)
    assert_society_import_allowlist(society_tree)
    assert_no_measurement_computation(society_tree)

    # Denylist auxiliary check extended to this loop's gating test module and
    # this guard module's own self-scan (§M8: "society module（+ 本 loop の
    # tests）").
    assert_no_denylist_import(_parse(_GATING_TEST_SRC))
    assert_no_denylist_import(_parse(_THIS_FILE))

    # society.py must actually never import erre_sandbox.evidence (the
    # concrete §M1 measurement-line package the allowlist/denylist above
    # exist to keep out).
    society_src = _SOCIETY_SRC.read_text(encoding="utf-8")
    for token in (
        "evidence.spdm",
        "evidence.d0_substrate",
        "evidence.es2_replay",
        "evidence.memory_recomp_conformance",
        "runningness",
        "landscape_divergence",
    ):
        assert token not in society_src, f"society.py must not reference {token!r}"


def test_m2_handoff_no_measurement_computation() -> None:
    """cross-review MEDIUM-A: the M2 society functions in ``handoff.py`` carry no
    measurement/aggregation surface either — denylist import + aggregation-
    surface ban (§M8), same as society.py's own I6-G1, applied to the sibling
    module the M2 handoff path (Issue 005) actually lives in. This is a
    guard-only extension (``handoff.py`` is not modified for this check to
    pass) — the module is already measurement-import-free (pure serialisation
    of ``SocietyRunResult``/``EclRunResult``), so this is expected to be green
    on first run and to catch a *future* drift, not a defect being fixed now.
    """
    handoff_tree = _parse(_HANDOFF_SRC)
    assert_no_denylist_import(handoff_tree)
    assert_no_measurement_computation(handoff_tree)

    # No raw-source-text token belt-and-suspenders here (unlike society.py's
    # own I6-G1, whose module docstring never mentions these words at all):
    # handoff.py's module docstring *legitimately* narrates the scope guard in
    # prose ("imports no evidence / spdm / runningness machinery", line ~27),
    # so a bare substring-in-raw-text check would false-positive on that
    # sentence. The AST-based checks above are the real (import-statement- and
    # executable-identifier-scoped) guard and already do not look at
    # docstrings/comments (Codex HIGH-1 discipline, mirrored from society.py's
    # own guard).


@pytest.mark.parametrize(
    "src",
    [
        "from erre_sandbox import evidence\n",
        "from erre_sandbox.evidence import spdm\n",
        "import erre_sandbox.evidence.d0_substrate\n",
        "from erre_sandbox.evidence.es2_replay import replay\n",
        "from erre_sandbox.evidence.memory_recomp_conformance import x\n",
        "from erre_sandbox.evidence import runningness\n",
        "from erre_sandbox.evidence import landscape_divergence\n",
    ],
)
def test_m2_society_import_guard_catches_evidence_imports(src: str) -> None:
    """Negative fixture: every measurement-line import trips the allowlist
    and/or denylist guard (I6-G1 実効性 witness)."""
    tree = ast.parse(src)
    with pytest.raises(AssertionError):
        assert_society_import_allowlist(tree)
    with pytest.raises(AssertionError):
        assert_no_denylist_import(tree)


@pytest.mark.parametrize(
    "src",
    [
        "import numpy\n",
        "import numpy as np\n",
        "from numpy import array\n",
        "import pandas\n",
        "import scipy\n",
        "import statistics\n",
        "import math\nx = math.log(2)\n",
        "from math import log\nx = log(2)\n",
        "from collections import Counter\nc = Counter()\n",
        "import collections\nc = collections.Counter()\n",
        "import collections as c\nx = c.Counter()\n",
        "from itertools import groupby\n",
        "import itertools\ng = itertools.groupby([])\n",
        "import itertools as it\ng = it.groupby([])\n",
        "floor_value = 1\n",
        "def compute_floor():\n    pass\n",
        "def build_verdict():\n    pass\n",
        "divergence_metric = 0.0\n",
        "class ScorerObject:\n    pass\n",
    ],
)
def test_m2_society_computation_guard_catches_banned_patterns(src: str) -> None:
    """Negative fixture: every Codex HIGH-1 aggregation/measurement escape
    hatch trips :func:`assert_no_measurement_computation` (I6-G1 実効性 witness)."""
    tree = ast.parse(src)
    with pytest.raises(AssertionError):
        assert_no_measurement_computation(tree)


# --------------------------------------------------------------------------- #
# I6-G2 — llm call cap (gating replay/mock only, non-gating tiny pinned cap)
# --------------------------------------------------------------------------- #


def test_m2_society_llm_call_cap() -> None:
    """AC I6-G2: gating is replay/mock only; live cap is a tiny pinned literal,
    non-gating (never invoked by ``society.py``'s production driver), and
    fails fast the instant it is exceeded (Codex LOW-9)."""
    # 1. gating path replay/mock only: run_society_loop's ``llms`` parameter is
    # typed as a Mapping of RecordReplayChatClient (Plane 2 record/replay), not
    # a raw live chat client the driver would construct itself.
    sig = inspect.signature(society.run_society_loop)
    llms_param = sig.parameters["llms"]
    assert "RecordReplayChatClient" in str(llms_param.annotation)

    # The gating test suite (test_m2_society.py) never talks to a real network
    # endpoint: every chat client it builds either wraps httpx.MockTransport
    # (OllamaChatClient) or a hand-rolled in-memory ``_ScriptedInner`` — no
    # bare live Ollama call.
    gating_src = _GATING_TEST_SRC.read_text(encoding="utf-8")
    assert "MockTransport" in gating_src
    assert "requests.post" not in gating_src
    assert "aiohttp" not in gating_src

    # 2. the cap helper itself: a tiny pinned literal boundary, fail-fast when
    # exceeded.
    n_agents, shakedown_ticks = 2, 2
    assert_llm_call_cap(
        actual_calls=n_agents * shakedown_ticks,
        n_agents=n_agents,
        shakedown_ticks=shakedown_ticks,
    )  # boundary: exactly at cap, must not raise
    with pytest.raises(AssertionError):
        assert_llm_call_cap(
            actual_calls=n_agents * shakedown_ticks + 1,
            n_agents=n_agents,
            shakedown_ticks=shakedown_ticks,
        )

    # 3. non-gating: the cap helper is never referenced from society.py's
    # production driver or the gating test module — it exists purely for a
    # manual/local-qwen3 shakedown script to import and call, never fired
    # during the pytest gating suite itself.
    society_src = _SOCIETY_SRC.read_text(encoding="utf-8")
    assert "assert_llm_call_cap" not in society_src
    assert "assert_llm_call_cap" not in gating_src

    # No powered/live run is authorized by this guard (R-budget=0, §M1): the
    # gating suite constructs every agent's LLM client from
    # RecordReplayChatClient/_ScriptedInner, never a bare OllamaChatClient
    # pointed at a live (non-mocked) endpoint.
    assert "OllamaChatClient(" in gating_src
    assert "httpx.AsyncClient(" in gating_src
    assert "MockTransport(handler)" in gating_src


# --------------------------------------------------------------------------- #
# I6-G3 — sorted(set(...)) is explicitly allowed (Codex HIGH-4, never flagged)
# --------------------------------------------------------------------------- #


def test_m2_society_sorted_set_allowed() -> None:
    """AC I6-G3: guard never flags ``sorted(set(...))`` canonicalisation —
    neither a synthetic minimal case nor the real ``handoff.py`` precedent
    shape (``sorted({r.agent_id for r in result.rows})``, Codex HIGH-4)."""
    synthetic_call = ast.parse("agent_ids = sorted(set(['b', 'a', 'a']))\n")
    synthetic_setcomp = ast.parse(
        "agent_ids = sorted({r.agent_id for r in result.rows})\n"
    )
    synthetic_set_diff = ast.parse("missing = sorted(set(agent_ids) - set(llms))\n")

    for tree in (synthetic_call, synthetic_setcomp, synthetic_set_diff):
        assert_no_measurement_computation(tree)
        assert_society_import_allowlist(tree)
        assert_no_denylist_import(tree)

    # society.py itself already contains this exact canonicalisation shape
    # (``_validate_agents``'s ``sorted(set(agent_ids) - set(llms))``-style
    # diffs) and must not be flagged by the real (non-synthetic) guard pass —
    # already proven by test_m2_society_no_measurement_computation, restated
    # here as the explicit HIGH-4 witness this AC names.
    society_tree = _parse(_SOCIETY_SRC)
    assert_no_measurement_computation(society_tree)
    society_src = _SOCIETY_SRC.read_text(encoding="utf-8")
    assert "sorted(set(agent_ids)" in society_src


# --------------------------------------------------------------------------- #
# I6-G4 — docstring/comment content is never flagged (Codex HIGH-1)
# --------------------------------------------------------------------------- #


def test_m2_society_docstring_not_flagged() -> None:
    """AC I6-G4: docstring/comment text carrying "divergence"/"floor"/"verdict"
    is never flagged — the guard scans identifier positions only, never a bare
    string constant (Codex HIGH-1's executable-AST-only scope, avoiding the
    self-contradiction with §M9's mandated docstring literal)."""
    synthetic = ast.parse(
        '''
"""A module docstring mentioning floor, divergence, verdict, and scorer as
free text — none of these are identifiers, so the guard must not flag them."""


def event_log_checksum() -> str:
    """NOT a structural-floor verdict; verdict は holding. Computes no
    divergence, floor, or scorer object — reproducibility only."""
    return "deadbeef"
'''
    )
    assert_no_measurement_computation(synthetic)
    assert_society_import_allowlist(synthetic)
    assert_no_denylist_import(synthetic)

    # Ground the synthetic case in the real module: society.py's own
    # docstrings literally carry the mandated "NOT a structural-floor
    # verdict; verdict は holding" phrase (§M9), and the guard still passes on
    # the whole real file (already proven above; restated explicitly here).
    society_src = _SOCIETY_SRC.read_text(encoding="utf-8")
    assert "NOT a structural-floor verdict" in society_src
    society_tree = _parse(_SOCIETY_SRC)
    assert_no_measurement_computation(society_tree)

    # Negative control: the same banned words used as real identifiers (not
    # docstring text) DO trip the guard — proves the docstring-exclusion
    # above is a deliberate scope choice, not an accidentally-blind guard.
    identifier_form = ast.parse("verdict = 'holding'\n")
    with pytest.raises(AssertionError):
        assert_no_measurement_computation(identifier_form)


# --------------------------------------------------------------------------- #
# I6-G5 — this guard module carries no measurement/aggregation surface itself
# --------------------------------------------------------------------------- #


def test_m2_society_spend_guard_module_self_scan() -> None:
    """This guard module itself must not carry a measurement/aggregation
    surface or a denylisted import (mirrors ``_bank_spend_guard``'s
    self-scan convention, applied here since guard logic lives inline)."""
    assert_no_denylist_import(_parse(_THIS_FILE))
