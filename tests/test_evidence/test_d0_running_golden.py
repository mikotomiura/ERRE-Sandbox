"""Blind-equivalence golden test (design-final.md §2.1, the most important test).

``running_ladder`` re-implements the frozen ``ladder`` R0/R1 readout recipe
driven by a swappable builder. Driving it with the **blind**
``stub.build_seed_pair`` must reproduce ``ladder.evaluate_r0_and_r1`` /
``ladder.r0_r1_seed_point`` **byte-for-byte** — proving the recipe is a
faithful copy so any difference in the sealed run is attributable to the
running *generator* alone (the non-circular paired contrast, design-final.md
§4.3). If this ever fails, the recipe has drifted from the frozen original and
the running verdict is not comparable — a Stop condition (report, do not
re-tune).
"""

from __future__ import annotations

import dataclasses

import pytest

from erre_sandbox.evidence.d0_substrate.ladder import (
    evaluate_r0_and_r1,
    r0_r1_seed_point,
)
from erre_sandbox.evidence.d0_substrate.running.running_ladder import (
    blind_builder,
    evaluate_r0_and_r1_running,
    r0_r1_seed_point_running,
)

_SEED_BANK = tuple(range(4))


@pytest.mark.asyncio
async def test_seed_point_blind_equivalence() -> None:
    for seed in _SEED_BANK:
        frozen = await r0_r1_seed_point(seed)
        running = await r0_r1_seed_point_running(seed, blind_builder)
        assert dataclasses.asdict(running) == dataclasses.asdict(frozen)


@pytest.mark.asyncio
async def test_evaluate_r0_r1_blind_equivalence() -> None:
    frozen_r0, frozen_r1 = await evaluate_r0_and_r1(_SEED_BANK)
    running_r0, running_r1 = await evaluate_r0_and_r1_running(_SEED_BANK, blind_builder)
    assert dataclasses.asdict(running_r0) == dataclasses.asdict(frozen_r0)
    assert dataclasses.asdict(running_r1) == dataclasses.asdict(frozen_r1)


@pytest.mark.asyncio
async def test_bootstrap_seed_threaded_identically() -> None:
    # A non-zero bootstrap_seed must thread through exactly as the frozen ladder
    # does (r0 uses bootstrap_seed, r1's delta CI uses bootstrap_seed + 1).
    frozen_r0, frozen_r1 = await evaluate_r0_and_r1(_SEED_BANK, bootstrap_seed=7)
    running_r0, running_r1 = await evaluate_r0_and_r1_running(
        _SEED_BANK, blind_builder, bootstrap_seed=7
    )
    assert dataclasses.asdict(running_r0) == dataclasses.asdict(frozen_r0)
    assert dataclasses.asdict(running_r1) == dataclasses.asdict(frozen_r1)
