"""Fixtures for tests/test_analysis (m9-c-adopt retrain v2 design).

The analysis script under ``scripts/analysis/`` is a standalone module
that imports from ``erre_sandbox.evidence.eval_store`` only inside
:func:`iter_shard_rows` (lazy), so tests can exercise per-row and
aggregate logic without booting DuckDB. We expose a path helper that
makes the script importable under ``scripts.analysis`` namespace.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make scripts/ importable so tests can ``import scripts.analysis...``.
# The repository root sits two levels up from this file
# (``tests/test_analysis/conftest.py``).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_PARENT = str(_REPO_ROOT)
if _SCRIPTS_PARENT not in sys.path:
    sys.path.insert(0, _SCRIPTS_PARENT)
