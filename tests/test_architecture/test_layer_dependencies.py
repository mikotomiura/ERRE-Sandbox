"""Architecture invariants enforced by static grep.

Layer dependency rules live in
``.claude/skills/architecture-rules/SKILL.md`` (table at L24-40). These
tests catch import drifts that would silently re-introduce the violations
fixed in codex review F5 (2026-04-28) — ``ui/`` had imported from
``integration``, transitively pulling gateway/dialog into UI code.

The rule is enforced with a project-rooted grep instead of a runtime
import scan because ``importlib`` would itself trigger the side effects
we are trying to forbid.

**Scope**: only static ``from``/``import`` statements are inspected.
Dynamic imports via ``__import__`` / ``importlib.import_module`` would
slip through, but those are independently discouraged by ruff PLC0415
(no function-level imports without ``# noqa``), so the residual risk is
small.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _src_files(*relative_dirs: str) -> list[Path]:
    """Collect ``*.py`` files inside the given ``src/erre_sandbox/`` subdirs."""
    src_root = REPO_ROOT / "src" / "erre_sandbox"
    files: list[Path] = []
    for rel in relative_dirs:
        files.extend((src_root / rel).rglob("*.py"))
    return files


def test_ui_does_not_import_integration() -> None:
    """``src/erre_sandbox/ui/`` MUST NOT import from ``integration``.

    The ``architecture-rules`` SKILL allows ui to depend on ``schemas`` and
    ``contracts`` only; importing the ``integration`` package triggers
    ``integration/__init__.py`` which loads ``gateway`` (fastapi/world/
    cognition) and ``dialog`` (inference) — exactly the heavy graph that
    UI must remain detached from.
    """
    offenders: list[tuple[Path, int, str]] = []
    for path in _src_files("ui"):
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            stripped = line.lstrip()
            if stripped.startswith(
                ("from erre_sandbox.integration", "import erre_sandbox.integration"),
            ):
                offenders.append((path.relative_to(REPO_ROOT), lineno, stripped))
    assert not offenders, (
        "ui/ must not import erre_sandbox.integration; offenders:\n"
        + "\n".join(f"  {p}:{ln}: {ln_text}" for p, ln, ln_text in offenders)
    )


def test_contracts_layer_depends_only_on_schemas_and_pydantic() -> None:
    """``contracts/`` must remain heavyweight-import free.

    Anything imported from another layer would defeat its purpose as a
    boundary-safe shared module reachable from UI.
    """
    forbidden_prefixes = (
        "from erre_sandbox.integration",
        "from erre_sandbox.world",
        "from erre_sandbox.cognition",
        "from erre_sandbox.memory",
        "from erre_sandbox.inference",
        "from erre_sandbox.ui",
    )
    offenders: list[tuple[Path, int, str]] = []
    for path in _src_files("contracts"):
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            stripped = line.lstrip()
            if stripped.startswith(forbidden_prefixes):
                offenders.append((path.relative_to(REPO_ROOT), lineno, stripped))
    assert not offenders, (
        "contracts/ must depend only on schemas + pydantic; offenders:\n"
        + "\n".join(f"  {p}:{ln}: {ln_text}" for p, ln, ln_text in offenders)
    )
