"""Guard: the horizon compose layer must not modify the frozen versioned scorer.

Codex U7 MED-2 / DA-U7-6: the horizon-reservation layer is USE-only over the frozen
``versioned_loader`` / ``versioned_constants`` (and the frozen saturation ``loader`` /
``constants``). This asserts their working-tree state is unchanged
(``git diff --quiet``) so a PR that touches the horizon layer cannot edit a frozen file.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_FROZEN_FILES = (
    "src/erre_sandbox/evidence/saturation/versioned_loader.py",
    "src/erre_sandbox/evidence/saturation/versioned_constants.py",
    "src/erre_sandbox/evidence/saturation/loader.py",
    "src/erre_sandbox/evidence/saturation/constants.py",
    "src/erre_sandbox/evidence/saturation/versioned_verdict_report.py",
    "src/erre_sandbox/cognition/world_model.py",
)


def _repo_root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            return parent
    return None


@pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")
def test_frozen_scorer_files_unmodified() -> None:
    root = _repo_root()
    if root is None:
        pytest.skip("not a git checkout")
    result = subprocess.run(  # noqa: S603
        ["git", "diff", "--quiet", "--", *_FROZEN_FILES],  # noqa: S607
        cwd=root,
        check=False,
    )
    assert result.returncode == 0, (
        "a frozen versioned/saturation scorer file has an uncommitted modification; "
        "the horizon layer must be USE-only (DA-U7-6)"
    )
