"""Fixtures for tests/test_o_time_probe.

候補 O_time (時期の評価) の battery / fixture / scorer / 見取り図 /
pilot 判定 / manifest は
``scripts/o_time_probe_*.py``。repository root を ``sys.path`` に置き、
``scripts.o_time_probe_scorer`` などとして import する
(``tests/test_generalization_probe/conftest.py`` と同じ型)。
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
