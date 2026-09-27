"""Fixtures for tests/test_closed_loop_driver.

The closed-loop pilot driver / scorer live in
``scripts/closed_loop_*.py``; put
the repository root on ``sys.path`` so it is importable as
``scripts.closed_loop_scorer`` etc.
(same pattern as ``tests/test_paper01_g1/conftest.py``).
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


# ---- full run (2,808 呼び出し、mock) は session で 1 回ずつだけ走らせる (1 本 ~12 秒)
import pytest  # noqa: E402

from tests.test_closed_loop_driver import _mock  # noqa: E402


def _full(tmp_path_factory: pytest.TempPathFactory, name: str, policy: object):
    run_dir = tmp_path_factory.mktemp(name) / "run"
    reason, ollama = _mock.do_run(run_dir, policy)
    return run_dir, reason, ollama


@pytest.fixture(scope="session")
def varying_run(tmp_path_factory: pytest.TempPathFactory):
    """連鎖を分岐させる mock (表示肢・Ω 外・⊥・装飾付き)."""
    return _full(tmp_path_factory, "varying", _mock.varying)


@pytest.fixture(scope="session")
def follow_run(tmp_path_factory: pytest.TempPathFactory):
    """同じ weather の成功行に従い、無ければ試していない表示肢を試す mock (→ PASS)."""
    return _full(tmp_path_factory, "follow", _mock.follow_success)


@pytest.fixture(scope="session")
def first_run(tmp_path_factory: pytest.TempPathFactory):
    """状態を読まず表示の先頭を答える mock (→ NO_GO)."""
    return _full(tmp_path_factory, "first", _mock.first_shown)
