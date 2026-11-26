"""Fixtures for tests/test_benchmark_stage2.

判別性 gate 段 2 の stats / 見取り図 / manifest は ``scripts/benchmark_stage2_*.py``。
repository root を ``sys.path`` に置き、
``scripts.benchmark_stage2_stats`` などとして import する
(``tests/test_o_time_probe/conftest.py`` と同じ型)。
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
