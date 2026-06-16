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


@pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")
def test_frozen_iiia_files_unmodified() -> None:
    root = _repo_root()
    if root is None:
        pytest.skip("not a git checkout")
    result = subprocess.run(  # noqa: S603
        ["git", "diff", "--quiet", "--", *_FROZEN_FILES],  # noqa: S607
        cwd=root,
        check=False,
    )
    assert result.returncode == 0, (
        "a frozen III-a file has an uncommitted modification; the live-carry verdict "
        "layer must be USE-only (freeze ADR §9)"
    )
