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
    # Both ``from erre_sandbox.X import ...`` and ``import erre_sandbox.X``
    # forms are forbidden (Codex M11-C1 MED-1: a ``from``-only gate left an
    # ``import``-statement hole in the HIGH-1 contracts→cognition regression
    # guard, e.g. ``WorldModelSnapshot`` must not drag cognition into contracts).
    heavy_layers = ("integration", "world", "cognition", "memory", "inference", "ui")
    forbidden_prefixes = tuple(
        f"{kw} erre_sandbox.{layer}"
        for layer in heavy_layers
        for kw in ("from", "import")
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


def test_world_does_not_import_memory_or_evidence() -> None:
    """``src/erre_sandbox/world/`` MUST NOT import ``memory`` or ``evidence``.

    The ``architecture-rules`` SKILL forbids ``world → memory``. M11-C2 relies on
    this: the per-tick individual-state trace sink reads promoted-belief classes
    off ``CycleResult.belief_classes`` (filled by ``cognition``) rather than
    calling ``memory.store.list_semantic_beliefs`` from ``world`` (DA-M11C2-2),
    and it forwards a contracts ``IndividualProfile`` to an orchestrator-owned
    sink rather than importing the ``evidence`` trace writer. Both ``from`` and
    ``import`` statement forms are checked (mirrors the contracts gate).
    """
    forbidden_layers = ("memory", "evidence")
    forbidden_prefixes = tuple(
        f"{kw} erre_sandbox.{layer}"
        for layer in forbidden_layers
        for kw in ("from", "import")
    )
    offenders: list[tuple[Path, int, str]] = []
    for path in _src_files("world"):
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            stripped = line.lstrip()
            if stripped.startswith(forbidden_prefixes):
                offenders.append((path.relative_to(REPO_ROOT), lineno, stripped))
    assert not offenders, (
        "world/ must not import erre_sandbox.memory / erre_sandbox.evidence;"
        " offenders:\n"
        + "\n".join(f"  {p}:{ln}: {ln_text}" for p, ln, ln_text in offenders)
    )


def test_runtime_burrows_paths_do_not_import_build_vectors() -> None:
    """Runtime Burrows code MUST NOT import the ``_build_vectors`` build script.

    M11-C3a made ``tokenise_ja`` the single source by hoisting it into
    ``tier_a.burrows`` and having ``_build_vectors`` *re-export* it. The
    dependency direction is therefore ``reference_corpus._build_vectors ->
    tier_a.burrows`` (one way). The runtime evaluation paths (``individuation``,
    ``tier_a``) must never import the offline build script back — that would
    invert the direction and re-open the convention-drift seam this PR closed
    (Codex M11-C3a 観点5). Both ``from`` and ``import`` forms are checked.
    """
    forbidden_prefixes = (
        "from erre_sandbox.evidence.reference_corpus._build_vectors",
        "import erre_sandbox.evidence.reference_corpus._build_vectors",
    )
    offenders: list[tuple[Path, int, str]] = []
    for path in _src_files("evidence/individuation", "evidence/tier_a"):
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            stripped = line.lstrip()
            if stripped.startswith(forbidden_prefixes):
                offenders.append((path.relative_to(REPO_ROOT), lineno, stripped))
    assert not offenders, (
        "individuation/ + tier_a/ must not import the _build_vectors build"
        " script (use tier_a.burrows.tokenise_ja, the single source);"
        " offenders:\n"
        + "\n".join(f"  {p}:{ln}: {ln_text}" for p, ln, ln_text in offenders)
    )
