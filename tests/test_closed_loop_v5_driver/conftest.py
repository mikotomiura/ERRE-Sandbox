"""Fixtures for tests/test_closed_loop_v5_driver.

The closed-loop v5 calibration pilot driver lives in
``scripts/closed_loop_v5_driver.py``; put the repository root on ``sys.path``
so it is importable as ``scripts.closed_loop_v5_driver``
(same pattern as ``tests/test_closed_loop_driver/conftest.py``).
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import pytest  # noqa: E402

from tests.test_closed_loop_v5_driver import _mock  # noqa: E402


@pytest.fixture(scope="session")
def varying_run(tmp_path_factory: pytest.TempPathFactory):
    """Full run (3,072 呼び出し、mock) を session で 1 回だけ走らせる.

    連鎖を分岐させる mock (表示肢・Ω 外・⊥・装飾付き・U+2028 / U+2029 / U+0085 付き)。
    """
    run_dir = tmp_path_factory.mktemp("varying") / "run"
    reason, ollama = _mock.do_run(run_dir, _mock.varying)
    return run_dir, reason, ollama


@pytest.fixture
def short_plan(monkeypatch: pytest.MonkeyPatch) -> tuple[object, ...]:
    """Driver の plan を先頭 48 件に短縮する (failure 系・来歴系を軽く回す).

    短縮した run は凍結 validate で incomplete (not_computed) になり、公開されない。
    """
    keys = _mock.FULL_PLAN[: _mock.N_SHORT]
    monkeypatch.setattr(_mock.drv, "_plan", lambda: keys)
    return keys


@pytest.fixture
def short_run(
    short_plan: tuple[object, ...], monkeypatch: pytest.MonkeyPatch
) -> tuple[object, ...]:
    """短縮 plan + 凍結 validate を「computed」に差し替えた run (Codex HIGH-1).

    短縮 run は本物の validate では必ず incomplete になる。
    そのままでは、公開を止める理由がそれだけに見えてしまう。
    来歴・manifest の公開条件の test では validate を computed に固定し、
    その条件だけで公開が止まることを見る。
    陽性対照は ``test_publication_is_two_phase`` (異常の無い短縮 run は公開される)。
    """
    monkeypatch.setattr(
        _mock.drv, "frozen_status", lambda _run_dir: (_mock.ps.STATUS_COMPUTED, [])
    )
    return short_plan
