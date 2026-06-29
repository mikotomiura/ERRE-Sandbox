"""Decomposition unit tests: reduced-model residual, headroom, ``D_loco`` (§2)."""

from __future__ import annotations

import numpy as np

from erre_sandbox.evidence.es3_locomotion import constants as _c
from erre_sandbox.evidence.es3_locomotion.controls import (
    ZONE_FUNCTION_LAMBDA,
    zone_function_d_loco,
)
from erre_sandbox.evidence.es3_locomotion.decomposition import (
    cell_statistics,
    d_loco_from_cells,
    decompose,
)
from erre_sandbox.evidence.es3_locomotion.scenario import (
    build_observations,
    default_seed_bank,
    observe_trajectory,
    trajectory,
)


def test_cell_headroom_equals_temp_max_minus_e_abl() -> None:
    cells = cell_statistics(build_observations((0,)))
    for c in cells:
        assert c.headroom == _c.TEMP_MAX - c.e_abl
        assert c.headroom_valid == (c.headroom > _c.HEADROOM_MIN)


def test_amplitude_is_efull_std_over_headroom() -> None:
    cells = cell_statistics(build_observations((0,)))
    for c in cells:
        if c.headroom > 0:
            assert c.amplitude == c.e_full_std / c.headroom


def test_repeat_penalty_is_invariant_within_cells() -> None:
    """Locomotion never moves repeat_penalty ⇒ within-cell var is ~0."""
    decomp = decompose(build_observations((0, 1)))
    assert decomp.max_repeat_penalty_var <= _c.ZERO_TOL


def test_d_loco_is_median_over_headroom_valid_cells() -> None:
    """ADR §2.3: the pooled D_loco median is over headroom-valid cells (not the
    measurement-valid subset) so spread-collapsed cells drag it down (§2.4)."""
    cells = cell_statistics(build_observations((0,)))
    valid = [c for c in cells if c.headroom_valid]
    amps = [c.amplitude for c in valid]
    expected = float(np.median(amps)) if amps else 0.0
    assert d_loco_from_cells(cells) == expected
    assert d_loco_from_cells(cells) >= 0.0


def test_zone_function_pooled_d_loco_is_zero_via_headroom_filter() -> None:
    """λ=h(z): cells are headroom-valid but spread-collapsed ⇒ a_s≈0 ⇒ D_loco≈0.

    This is the falsifiability the headroom-valid (not measurement-valid) filter
    preserves: were D_loco filtered to spread-valid cells, the empty set would
    return 0 trivially; here it is 0 because every headroom-valid cell's a_s is ~0.
    """
    obs = []
    for seed in (0, 1):
        walk = trajectory(seed)
        lams = [ZONE_FUNCTION_LAMBDA[z] for z in walk.zones]
        obs.extend(observe_trajectory(walk, lams))
    cells = cell_statistics(obs)
    assert all(c.headroom_valid for c in cells)  # headroom unaffected by λ
    assert d_loco_from_cells(cells) <= _c.ZERO_TOL


def test_zone_function_lambda_collapses_within_cell_variation() -> None:
    """λ = h(z) ⇒ λ constant in a cell ⇒ E_full std = 0 ⇒ amplitude 0 (separation)."""
    obs = []
    for seed in (0, 1):
        walk = trajectory(seed)
        lams = [ZONE_FUNCTION_LAMBDA[z] for z in walk.zones]
        obs.extend(observe_trajectory(walk, lams))
    cells = cell_statistics(obs)
    for c in cells:
        assert c.lam_var <= _c.ZERO_TOL
        assert c.e_full_std <= _c.ZERO_TOL


def test_zone_function_d_loco_is_zero() -> None:
    assert zone_function_d_loco(default_seed_bank()) <= _c.ZERO_TOL


def test_decompose_pooled_fields_consistent() -> None:
    decomp = decompose(build_observations((0, 1, 2, 3)))
    assert decomp.n_cells == 15  # 3 personas × 5 zones
    assert 0 <= decomp.n_headroom_valid <= decomp.n_cells
    assert decomp.headroom_valid_fraction == decomp.n_headroom_valid / decomp.n_cells
    assert decomp.n_valid_walk_seeds == len(decomp.per_seed_d_loco)
    assert all(v >= 0.0 for v in decomp.per_seed_d_loco)


def test_blind_walk_cells_have_lambda_spread() -> None:
    """The blind walk (unlike zone-function h(z)) gives real within-cell λ var."""
    cells = cell_statistics(build_observations((0, 1, 2, 3)))
    spread_valid = [c for c in cells if c.spread_valid]
    # The self-loop walk should leave most cells with measurable λ spread.
    assert len(spread_valid) >= _c.MIN_CELLS
