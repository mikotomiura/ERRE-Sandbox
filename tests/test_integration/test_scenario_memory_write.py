"""Skeleton for S_MEMORY_WRITE scenario (skipped until T14 gateway lands).

The scenario data lives in
:data:`erre_sandbox.integration.SCENARIO_MEMORY_WRITE`. These placeholders
verify memory-store writes happen in the expected ratio (4 episodic + 1
semantic) during peripatetic walking.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="T19 実行フェーズ待ち (T14 完成後に点灯)")


def test_s_memory_write_steps_are_three(memory_write_scenario):  # type: ignore[no-untyped-def]
    # TODO(T19): sanity check that the scenario still has 3 steps after
    # T14 lands; extend this test with real assertions.
    assert len(memory_write_scenario.steps) == 3


def test_s_memory_write_writes_four_episodic_one_semantic(memory_write_scenario):  # type: ignore[no-untyped-def]
    # TODO(T19): execute the scenario with a real MemoryStore and assert the
    # exact kind distribution (episodic=4, semantic=1).
    _ = memory_write_scenario


def test_s_memory_write_embedding_prefix_applied(memory_write_scenario):  # type: ignore[no-untyped-def]
    # TODO(T19): after execution, inspect the stored rows and confirm
    # search_document / query prefix rules were applied at insertion time.
    _ = memory_write_scenario
