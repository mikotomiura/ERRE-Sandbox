"""Pin the memory-recomposition seam frozen constants (forking-paths guard).

Two kinds of pin (design-final.md §6 / ``DA-MEMSEAM-IMPL-1``):

* **inherited** constants are asserted **identical** (``is``) to their
  ``es2_replay`` source — proving they are *re-exported*, never re-declared or
  re-tuned;
* **newly frozen** gate thresholds / stream ids are pinned **verbatim** to the
  values fixed from result-independent principle before the verdict run.

A constant can only change by a deliberate edit that also updates this table
(which itself requires a superseding ADR). The verdict value is **not** pinned.
"""

from __future__ import annotations

from erre_sandbox.evidence.es2_replay import constants as _es2_c
from erre_sandbox.evidence.memory_recomp_conformance import constants as _c


def test_inherited_constants_are_reexported_identically() -> None:
    # `is` proves byte inheritance (re-export), not a re-declared literal.
    assert _c.POLYA_ALPHA is _es2_c.POLYA_ALPHA
    assert _c.M_FRAGMENTS is _es2_c.M_FRAGMENTS
    assert _c.L_SEED is _es2_c.L_SEED
    assert _c.N_REPLAY is _es2_c.N_REPLAY
    assert _c.N_SEED is _es2_c.N_SEED
    assert _c.N_PERM is _es2_c.N_PERM
    assert _c.PERM_NULL_QUANTILE is _es2_c.PERM_NULL_QUANTILE
    assert _c.CI_ALPHA is _es2_c.CI_ALPHA
    assert _c.N_RESAMPLES is _es2_c.N_RESAMPLES
    assert _c.MIN_VALID_SEEDS is _es2_c.MIN_VALID_SEEDS


def test_newly_frozen_gate_thresholds_verbatim() -> None:
    assert _c.ARGMAX_STABILITY_MIN == 0.5
    assert _c.EFFECTIVE_SUPPORT_MIN == 2.0
    assert _c.SYNTHETIC_POWER_PASS_MIN == 0.80


def test_monte_carlo_realizations_derivation() -> None:
    # POST_IDLE_REALIZATIONS = ES-2 per-arm pooled sample size / walk length
    # = N_REPLAY*(L_SEED-1) / M_FRAGMENTS = 4096*3 / 48 = 256 (DA-MEMSEAM-IMPL-5).
    assert _c.POST_IDLE_REALIZATIONS == 256
    assert _c.POST_IDLE_REALIZATIONS == _c.N_REPLAY * (_c.L_SEED - 1) // _c.M_FRAGMENTS


def test_synthetic_power_sim_parameters_verbatim() -> None:
    assert _c.SYNTH_COUPLING_LADDER == (0.0, 0.25, 0.5, 1.0)
    assert _c.SYNTH_N_REPLICATES == 100


def test_rng_base_distinct_from_es2() -> None:
    # The private base must differ from ES-2's (0x_E5_2A, in es2_replay.scenario) so
    # the two homes' streams never collide even at equal (seed, stream) (§5).
    from erre_sandbox.evidence.es2_replay.scenario import _SEED_BASE as _ES2_BASE

    assert _c._SEED_BASE == 0x_135C
    assert _ES2_BASE != _c._SEED_BASE


def test_stream_ids_distinct_and_verbatim() -> None:
    ids = (
        _c.STREAM_C_IDLE,
        _c.STREAM_D_POST_IDLE,
        _c.STREAM_ARGMAX_BOOT,
        _c.STREAM_SYNTH_POWER,
    )
    assert ids == (0, 1, 2, 3)
    assert len(set(ids)) == len(ids)
