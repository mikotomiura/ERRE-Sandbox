#!/usr/bin/env python3
"""SH-1 banned-import scanner (CI backstop, Codex 14th HIGH-2).

The Codex hook (``.codex/hooks/pre_tool_use_policy.py``) already enforces
the same rules at IDE / shell time; this scanner is the CI counterpart so
a forbidden import that slips past local hooks (e.g. a developer who ran
Codex with hooks disabled) still fails the PR.

Replaces the prior regex-based grep in ``policy-grep-gate`` because the
regex required whitespace after the module name and so missed the
``import openai, os`` comma form (Codex 14th HIGH-2). An ``ast.walk`` of
each ``src/erre_sandbox/**/*.py`` file catches every Python-legal import
shape:

* ``import openai``
* ``import openai as client``
* ``import openai, os``
* ``import openai.submodule``
* ``from openai import OpenAI``
* ``from openai.submodule import X``

Exit code 0 on clean, 1 on any violation. Emits ``::error::`` lines so
GitHub Actions surfaces them as PR annotations.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BANNED_ROOTS = frozenset({"openai", "anthropic", "bpy"})
"""Top-level module names whose presence inside ``src/erre_sandbox/`` is a
policy violation. ``bpy`` keeps the GPL/Blender code isolated; ``openai``
/ ``anthropic`` keep the cloud-LLM dependency surface out of the core."""


def scan_file(path: Path) -> list[str]:
    """Return descriptive violation strings; empty when the file is clean."""
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{path}: read failed: {exc}"]
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [f"{path}:{exc.lineno}: SyntaxError: {exc.msg}"]
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.partition(".")[0]
                if root in BANNED_ROOTS:
                    violations.append(
                        f"{path}:{node.lineno}: import {alias.name}"
                        + (f" as {alias.asname}" if alias.asname else "")
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.partition(".")[0]
            if root in BANNED_ROOTS:
                names = ", ".join(a.name for a in node.names)
                violations.append(
                    f"{path}:{node.lineno}: from {module} import {names}"
                )
    return violations


def main() -> int:
    base = Path("src/erre_sandbox")
    if not base.is_dir():
        print(f"[policy_banned_imports] {base} not found (running from wrong CWD?)", file=sys.stderr)
        return 1
    violations: list[str] = []
    files_scanned = 0
    for py in sorted(base.rglob("*.py")):
        files_scanned += 1
        violations.extend(scan_file(py))
    if violations:
        for v in violations:
            print(f"::error::SH-1 banned import: {v}", file=sys.stderr)
        print(
            f"[policy_banned_imports] {len(violations)} violation(s) "
            f"in {files_scanned} files",
            file=sys.stderr,
        )
        return 1
    print(f"[policy_banned_imports] {files_scanned} files scanned, no violations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
