"""Fixtures for tests/test_stage_b.

The Stage B scorer / B-pre / battery live in ``scripts/stage_b_*.py``; put the
repository root on ``sys.path`` so it is importable as ``scripts.stage_b_scorer`` etc.
(same pattern as ``tests/test_paper01_g1/conftest.py``).
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
