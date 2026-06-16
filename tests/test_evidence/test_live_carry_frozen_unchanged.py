"""Guard: the live-carry verdict layer must not modify any frozen III-a file.

Freeze ADR §9: the cross-arm scorer is **USE-only** over the frozen reconcile kernel
(``cognition.world_model`` — cap 0.15, value range, ``STM_HORIZON``, ``VALUE_STEP``),
the frozen distance body (``world_model_overlap_jaccard_active``), and the frozen
saturation constants. This asserts their working-tree state is unchanged
(``git diff --quiet``) so a PR that adds the live-carry layer cannot edit a frozen
file (the mechanical "src/frozen implementation diff 空" proof, ADR §9 / LOW-1).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_FROZEN_FILES = (
    # reconcile kernel + cap=0.15 + value-range clamp + STM_HORIZON + VALUE_STEP
    "src/erre_sandbox/cognition/world_model.py",
    # frozen pairwise SWM distance body (world_model_overlap_jaccard_active)
    "src/erre_sandbox/evidence/individuation/world_model_metrics.py",
    # frozen saturation thresholds the cap geometry mirrors (USE-only import)
    "src/erre_sandbox/evidence/saturation/constants.py",
    "src/erre_sandbox/evidence/saturation/versioned_constants.py",
)


def _repo_root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            return parent
    return None


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )


def _merge_base(root: Path) -> str | None:
    """Merge-base of HEAD with the default branch, or ``None`` if unresolvable."""
    for ref in ("origin/main", "main"):
        if _git(root, "rev-parse", "--verify", "--quiet", ref).returncode != 0:
            continue
        result = _git(root, "merge-base", "HEAD", ref)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return None


@pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")
def test_frozen_iiia_files_unmodified() -> None:
    root = _repo_root()
    if root is None:
        pytest.skip("not a git checkout")

    # (1) working tree is clean for the frozen files (catches uncommitted edits).
    working_tree = _git(root, "diff", "--quiet", "--", *_FROZEN_FILES)
    assert working_tree.returncode == 0, (
        "a frozen III-a file has an uncommitted modification; the live-carry verdict "
        "layer must be USE-only (freeze ADR §9)"
    )

    # (2) committed changes since the branch base are clean too (the PR guard a
    # working-tree-only diff misses, Codex MEDIUM). Skip gracefully when no base ref
    # is resolvable (a detached/shallow CI checkout without origin/main).
    base = _merge_base(root)
    if base is None:
        pytest.skip("no base ref (origin/main / main) to diff committed frozen changes")
    committed = _git(root, "diff", "--quiet", base, "HEAD", "--", *_FROZEN_FILES)
    assert committed.returncode == 0, (
        "a frozen III-a file was modified in a commit on this branch; the live-carry "
        "verdict layer must be USE-only (freeze ADR §9)"
    )
