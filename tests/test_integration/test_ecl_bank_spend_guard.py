"""ECL B — bank spend/no-spend ast-guard tests (Codex HIGH-4, §I4).

Issue 003 (``loop/20260708-m13-b-code-impl/issues/003-spend-ast-guard.md``) of
the FROZEN ADR ``.steering/20260707-m13-b-impl-design/design-final.md`` (§I4).
Guards ``bank.py`` / ``bank_fixtures.py`` (Issue 001/002) at the AST level:
raw-row-only (no ``math.log`` / ``Counter`` / set-over-zone / ``groupby`` /
``numpy``/``pandas``/``scipy``/``statistics`` aggregation), a call-cap runtime
helper, no adaptive top-up, annotation-opaque identifiers, and a closed
import allowlist. The guard logic itself lives in ``_bank_spend_guard.py``
(non-test helper, mirrors the ``_measurement_guard.py`` convention) so pytest
never collects it and this module's own self-scan never targets it.

Scope guard (§I4/§I9, binding, mirrors ``test_ecl_bank_driver.py`` /
``test_ecl_bank_fixtures.py``). This is a *construction* apparatus guard,
**NOT a measurement line**: it computes no ``H(zone|ctx)`` / count /
diversity itself — every test here only asserts such a surface is *absent*
from the modules it scans (:func:`test_bank_annotation_opaque` self-scans
this very module for the same reason).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.test_integration._bank_spend_guard import (
    assert_bank_annotation_opaque,
    assert_bank_import_allowlist,
    assert_bank_no_measurement_surface,
    assert_llm_call_cap,
    assert_no_adaptive_topup,
    assert_no_aggregation_surface,
)

_THIS_FILE = Path(__file__)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_BANK_SRC = _REPO_ROOT / "src" / "erre_sandbox" / "integration" / "embodied" / "bank.py"
_BANK_FIXTURES_SRC = (
    _REPO_ROOT
    / "src"
    / "erre_sandbox"
    / "integration"
    / "embodied"
    / "bank_fixtures.py"
)
_BANK_FILES = (_BANK_SRC, _BANK_FIXTURES_SRC)
# The capture CLI (Issue 005) is the annotation *writer* — §I4/grill-goals D-6 lists
# ``scripts/ecl_bank_*.py`` in the bank-module scan set, so the aggregation /
# measurement / annotation-opaque guards cover it too. It is intentionally *not*
# under the strict bank-module import-allowlist: a thin CLI legitimately imports
# ``argparse`` / ``sys`` / ``json`` / ``handoff`` that the core modules do not.
_BANK_CAPTURE_SRC = _REPO_ROOT / "scripts" / "ecl_bank_capture.py"
_BANK_AGG_FILES = (*_BANK_FILES, _BANK_CAPTURE_SRC)


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# I3-G1 — no measurement / aggregation computation (Codex HIGH-4 superset)
# --------------------------------------------------------------------------- #


def test_bank_no_measurement_computation() -> None:
    """AC I3-G1: bank.py/bank_fixtures.py/ecl_bank_capture.py carry no measurement
    or aggregation surface (§I4 superset of the shared v1 3-hole guard)."""
    for path in _BANK_AGG_FILES:
        assert_bank_no_measurement_surface(_parse(path), scan_strings=True)
    # self-scan (mirrors test_ecl_v1_locomotion.py's test_v1_measurement_guard
    # _THIS_FILE entry): this test module itself carries no measurement surface.
    assert_bank_no_measurement_surface(_parse(_THIS_FILE), scan_strings=False)


@pytest.mark.parametrize(
    "src",
    [
        "import math\nx = math.log(2)\n",
        "from math import log\nx = log(2)\n",
        "from collections import Counter\nc = Counter()\n",
        "import collections\nc = collections.Counter()\n",
        "from itertools import groupby\n",
        "import itertools\ng = itertools.groupby([])\n",
        "import numpy\n",
        "import numpy as np\n",
        "from numpy import array\n",
        "import pandas\n",
        "import scipy\n",
        "import statistics\n",
        "zones = {r.pre_bias_destination_zone for r in records}\n",
        "distinct = len(set(r.destination_zone for r in records))\n",
        "zs = {a.zone, b.zone}\n",
    ],
)
def test_bank_aggregation_guard_catches_banned_patterns(src: str) -> None:
    """Negative fixture: every Codex HIGH-4 aggregation escape hatch trips
    ``assert_no_aggregation_surface`` (I3-G1 実効性 witness, §I4 Test Plan)."""
    tree = ast.parse(src)
    with pytest.raises(AssertionError):
        assert_no_aggregation_surface(tree)


@pytest.mark.parametrize(
    "src",
    [
        "prompts = {r.system_prompt for r in records}\n",
        "seen = {r.frozen_ctx_id for r in records}\n",
        "import itertools\nc = itertools.chain([], [])\n",
        "import collections\nq = collections.abc.Sequence\n",
        "from collections.abc import Sequence\n",
    ],
)
def test_bank_aggregation_guard_allows_legitimate_patterns(src: str) -> None:
    """Positive fixture: prompt-set dedup and non-aggregation stdlib usage
    never false-trip (§I4 精密 set-over-zones guard requirement)."""
    tree = ast.parse(src)
    assert_no_aggregation_surface(tree)  # must not raise


# --------------------------------------------------------------------------- #
# I3-G2 — LLM call-cap runtime helper
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("actual_calls", "m_draws", "k_contexts", "should_raise"),
    [
        (16, 4, 2, False),  # == cap (2*4*2=16), boundary pass
        (17, 4, 2, True),  # cap+1, boundary fail
        (0, 4, 2, False),
        (2, 1, 1, False),  # == cap (2*1*1=2)
        (3, 1, 1, True),  # cap+1
    ],
)
def test_bank_llm_call_cap(
    actual_calls: int, m_draws: int, k_contexts: int, *, should_raise: bool
) -> None:
    """AC I3-G2: ``actual_calls`` fail-fasts past ``2*m_draws*k_contexts`` (§I4)."""
    if should_raise:
        with pytest.raises(AssertionError):
            assert_llm_call_cap(actual_calls, m_draws, k_contexts)
    else:
        assert_llm_call_cap(actual_calls, m_draws, k_contexts)  # must not raise


# --------------------------------------------------------------------------- #
# I3-G3 — no adaptive top-up
# --------------------------------------------------------------------------- #


def test_bank_no_adaptive_topup() -> None:
    """AC I3-G3: M/K are frozen literals; no while-loop top-up branch (§I4)."""
    for path in _BANK_AGG_FILES:
        assert_no_adaptive_topup(_parse(path))


def test_bank_no_adaptive_topup_catches_while_loop() -> None:
    src = "def f(m_draws: int = 4) -> None:\n    while True:\n        m_draws += 1\n"
    tree = ast.parse(src)
    with pytest.raises(AssertionError):
        assert_no_adaptive_topup(tree)


def test_bank_no_adaptive_topup_catches_nonliteral_default() -> None:
    src = (
        "def compute() -> int:\n"
        "    return 4\n"
        "\n"
        "def f(m_draws: int = compute()) -> None:\n"
        "    pass\n"
    )
    tree = ast.parse(src)
    with pytest.raises(AssertionError):
        assert_no_adaptive_topup(tree)


def test_bank_no_adaptive_topup_allows_frozen_constant_default() -> None:
    src = "M_GOLDEN: int = 4\n\n\ndef f(m_draws: int = M_GOLDEN) -> None:\n    pass\n"
    tree = ast.parse(src)
    assert_no_adaptive_topup(tree)  # must not raise


def test_bank_no_adaptive_topup_allows_bare_int_default() -> None:
    src = "def f(m_draws: int = 4, k_contexts: int = 2) -> None:\n    pass\n"
    tree = ast.parse(src)
    assert_no_adaptive_topup(tree)  # must not raise


# --------------------------------------------------------------------------- #
# I3-G4 — annotation-opaque identifiers
# --------------------------------------------------------------------------- #


def test_bank_annotation_opaque() -> None:
    """AC I3-G4: bank module + capture writer + this test module never
    compute/assert count/diversity/H/distinct-zone (§I4 ``annotation は B 側で
    opaque``)."""
    for path in (*_BANK_AGG_FILES, _THIS_FILE):
        assert_bank_annotation_opaque(_parse(path))


@pytest.mark.parametrize(
    "src",
    [
        "diversity = 0.5\n",
        "def compute_entropy() -> None:\n    pass\n",
        "distinct_zones = 3\n",
        "h_zone = 0.1\n",
        "zone_count = 2\n",
        "count_zones = 4\n",
        "def f(shannon_entropy: float) -> None:\n    pass\n",
    ],
)
def test_bank_annotation_opaque_catches_banned_identifiers(src: str) -> None:
    tree = ast.parse(src)
    with pytest.raises(AssertionError):
        assert_bank_annotation_opaque(tree)


# --------------------------------------------------------------------------- #
# I3-G5 — closed import allowlist
# --------------------------------------------------------------------------- #


def test_bank_import_allowlist_guard() -> None:
    """AC I3-G5: bank module import ⊆ allowlist ∧ ∩ denylist = ∅ (§I4)."""
    for path in _BANK_FILES:
        assert_bank_import_allowlist(_parse(path))


@pytest.mark.parametrize(
    "src",
    [
        "from erre_sandbox import evidence\n",
        "from erre_sandbox.evidence.spdm import compute_h\n",
        "from erre_sandbox.evidence import d0_substrate\n",
        "from erre_sandbox.integration.embodied import es2_replay\n",
        "import numpy\n",
        # sibling module, not allowlisted
        "from erre_sandbox.integration.embodied import live_v1\n",
        "import sqlite3\n",  # unlisted stdlib module
    ],
)
def test_bank_import_allowlist_guard_catches_disallowed_imports(src: str) -> None:
    tree = ast.parse(src)
    with pytest.raises(AssertionError):
        assert_bank_import_allowlist(tree)


def test_bank_import_allowlist_guard_allows_legitimate_imports() -> None:
    """Positive fixture: bank.py's/bank_fixtures.py's actual import surface."""
    src = (
        "from __future__ import annotations\n"
        "import os\n"
        "from contextlib import contextmanager\n"
        "from dataclasses import dataclass\n"
        "from typing import TYPE_CHECKING, Any, Final, Literal\n"
        "from collections.abc import Sequence\n"
        "from datetime import datetime\n"
        "from erre_sandbox.cognition import parse_llm_plan\n"
        "from erre_sandbox.inference.ollama_adapter import ChatMessage, ChatResponse\n"
        "from erre_sandbox.inference.sampling import ResolvedSampling\n"
        "from erre_sandbox.integration.embodied import live\n"
        "from erre_sandbox.integration.embodied.bank_fixtures import FrozenContext\n"
        "from erre_sandbox.integration.embodied.loop import RecordReplayChatClient\n"
        "from erre_sandbox.memory import RankedMemory\n"
        "from erre_sandbox.schemas import Zone\n"
    )
    tree = ast.parse(src)
    assert_bank_import_allowlist(tree)  # must not raise
