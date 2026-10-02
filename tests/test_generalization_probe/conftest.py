"""Fixtures for tests/test_generalization_probe.

候補 G (汎化 probe) の battery / fixture / scorer / 見取り図 / pilot 判定は
``scripts/generalization_probe_*.py``。repository root を ``sys.path`` に置き、
``scripts.generalization_probe_scorer`` などとして import する
(``tests/test_skill_lever/conftest.py`` と同じ型)。
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
