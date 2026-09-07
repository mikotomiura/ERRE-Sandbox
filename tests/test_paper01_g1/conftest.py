"""Fixtures for tests/test_paper01_g1 (paper01 G1 external-audit fetch layer).

The fetch script lives in ``scripts/paper01_fetch_sources.py`` (a tracked,
non-excluded research script). It must be importable under the ``scripts``
namespace, so -- mirroring ``tests/test_es4_diag/conftest.py`` -- we put the
repository root on ``sys.path``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The repository root sits two levels up from this file
# (``tests/test_paper01_g1/conftest.py``).
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
