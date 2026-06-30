"""Fixtures for tests/test_es4_diag (M13-ES4 offline scorer diagnostic).

The diagnostic harness lives in ``scripts/es4_scorer_diag.py`` (a tracked,
non-excluded research script). It must be importable under the ``scripts``
namespace, so — mirroring ``tests/test_analysis/conftest.py`` — we put the
repository root on ``sys.path``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The repository root sits two levels up from this file
# (``tests/test_es4_diag/conftest.py``).
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
