"""Blind scenario generator: determinism, world-geometry reuse, seed bank."""

from __future__ import annotations

from erre_sandbox.evidence.es2_replay.scenario import ADJACENCY as _ES2_ADJACENCY
from erre_sandbox.evidence.memory_recomp_conformance import constants as _c
from erre_sandbox.evidence.memory_recomp_conformance import scenario


def test_build_seed_result_is_deterministic() -> None:
    kw = {"m": 12, "n_replay": 256, "l_seed": 4, "n_argmax_resamples": 50}
    a = scenario.build_seed_result(3, **kw)
    b = scenario.build_seed_result(3, **kw)
    assert a == b


def test_seed_result_fields_well_formed() -> None:
    r = scenario.build_seed_result(
        0, m=12, n_replay=256, l_seed=4, n_argmax_resamples=50
    )
    assert 0 <= r.target_zone < len(scenario.ZONES)
    assert 0 <= r.start_zone < len(scenario.ZONES)
    assert len(r.conform_row) == len(scenario.ZONES)
    assert 0.0 <= r.argmax_stability <= 1.0
    assert r.channel_effective_support >= 0.0


def test_world_geometry_reused_from_es2_not_remirrored() -> None:
    # The adjacency mask is built from the ES-2 ADJACENCY (already pinned to
    # world.zones in the ES-2 scenario test) — no independent re-mirror to drift.
    for i, z in enumerate(scenario.ZONES):
        neighbors = {
            scenario.ZONES[j]
            for j in range(len(scenario.ZONES))
            if scenario._ADJ_MASK[i, j]
        }
        assert neighbors == set(_ES2_ADJACENCY[z])


def test_default_seed_bank_is_range_n_seed() -> None:
    assert scenario.default_seed_bank() == tuple(range(_c.N_SEED))
