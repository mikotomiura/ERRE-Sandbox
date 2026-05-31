"""Unit tests for the SH-1 AST-based banned-import scanner.

Codex 14th HIGH-2 replaced the previous CI grep (which missed
``import openai, os`` comma forms) with ``scripts/policy_banned_imports.py``
running ``ast.walk``. These tests cover all the regex bypass cases plus
the original happy/benign paths so a future regex regression does not
silently re-open the gap.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "policy_banned_imports.py"

# Pull ``scan_file`` directly so each case targets the parser without
# spawning a subprocess per assertion.
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import policy_banned_imports  # noqa: E402 — path injected above


@pytest.fixture
def make_pyfile(tmp_path: Path):
    """Return a helper that writes Python source to ``tmp/src/erre_sandbox/x.py``."""

    def _write(source: str) -> Path:
        target = tmp_path / "x.py"
        target.write_text(textwrap.dedent(source), encoding="utf-8")
        return target

    return _write


class TestScanFileViolations:
    def test_import_openai_plain(self, make_pyfile) -> None:
        f = make_pyfile("import openai\n")
        violations = policy_banned_imports.scan_file(f)
        assert violations
        assert "import openai" in violations[0]

    def test_import_openai_with_alias(self, make_pyfile) -> None:
        f = make_pyfile("import openai as client\n")
        violations = policy_banned_imports.scan_file(f)
        assert violations
        assert "as client" in violations[0]

    def test_import_openai_comma_form_is_caught(self, make_pyfile) -> None:
        """Codex 14th HIGH-2 regression: comma form bypassed regex."""
        f = make_pyfile("import openai, os\n")
        violations = policy_banned_imports.scan_file(f)
        assert violations
        assert "openai" in violations[0]

    def test_import_openai_submodule_is_caught(self, make_pyfile) -> None:
        f = make_pyfile("import openai.types\n")
        violations = policy_banned_imports.scan_file(f)
        assert violations
        assert "openai.types" in violations[0] or "openai" in violations[0]

    def test_from_openai_import_form_is_caught(self, make_pyfile) -> None:
        f = make_pyfile("from openai import OpenAI\n")
        violations = policy_banned_imports.scan_file(f)
        assert violations
        assert "from openai" in violations[0]

    def test_from_openai_submodule_form_is_caught(self, make_pyfile) -> None:
        f = make_pyfile("from openai.types import ChatCompletion\n")
        violations = policy_banned_imports.scan_file(f)
        assert violations
        assert "openai" in violations[0]

    def test_import_anthropic_plain(self, make_pyfile) -> None:
        f = make_pyfile("import anthropic\n")
        violations = policy_banned_imports.scan_file(f)
        assert violations
        assert "anthropic" in violations[0]

    def test_import_bpy_plain(self, make_pyfile) -> None:
        f = make_pyfile("import bpy\n")
        violations = policy_banned_imports.scan_file(f)
        assert violations
        assert "bpy" in violations[0]


class TestScanFileClean:
    def test_benign_imports_pass(self, make_pyfile) -> None:
        f = make_pyfile(
            """
            import asyncio
            import os
            from pathlib import Path
            from typing import Any
            """
        )
        assert policy_banned_imports.scan_file(f) == []

    def test_string_mentioning_openai_does_not_match(self, make_pyfile) -> None:
        """Only AST-level imports trigger; string literals are not violations."""
        f = make_pyfile(
            """
            import asyncio

            DOC = "we deliberately do not import openai here"
            """
        )
        assert policy_banned_imports.scan_file(f) == []

    def test_module_named_openai_test_in_comment_is_ignored(self, make_pyfile) -> None:
        f = make_pyfile(
            """
            # historical note: we evaluated import openai and rejected it
            import json
            """
        )
        assert policy_banned_imports.scan_file(f) == []

    def test_syntax_error_is_reported_but_not_a_silent_pass(self, make_pyfile) -> None:
        """Broken Python flags itself so a malformed file cannot smuggle imports."""
        f = make_pyfile("import openai\nthis is not valid python\n")
        violations = policy_banned_imports.scan_file(f)
        assert violations
        assert "SyntaxError" in violations[0]
