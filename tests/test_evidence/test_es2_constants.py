"""Pin the M13-ES2 frozen constants to the ADR table verbatim.

The apparatus constants come from the original pre-registration freeze
(``.steering/20260628-m13-es2-replay/``); the **scoring** constants were superseded
by the measurable ADR (``.steering/20260628-es2-measurable-adr/`` — /reimagine
set→distribution + Codex ADOPT-WITH-CHANGES, all HIGH reflected before freeze):
the absolute ``DENOVO_DIVERGENCE_FLOOR`` was retired and ``DIVERGENCE`` /
``FLOOR_REL`` / ``TRANSITION_SUPPORT`` added. Every threshold was fixed **before**
any replay result was seen. This test is the forking-paths guard's regression pin:
a constant can only change by a deliberate edit that also updates this expected
table (which itself requires a superseding ADR). The verdict value is **not**
pinned here.
"""

from __future__ import annotations

from erre_sandbox.evidence.es2_replay import constants as _c


def test_movement_constants_verbatim() -> None:
    assert _c.POLYA_ALPHA == 1.0
    assert _c.M_FRAGMENTS == 48


def test_kernel_constants_verbatim() -> None:
    assert _c.L_SEED == 4
    assert _c.N_REPLAY == 4096


def test_statistics_constants_verbatim() -> None:
    assert _c.N_SEED == 64
    assert _c.N_PERM == 5000
    assert _c.PERM_NULL_QUANTILE == 0.95
    assert _c.CI_ALPHA == 0.10
    assert _c.N_RESAMPLES == 2000


def test_inconclusive_gate_constants_verbatim() -> None:
    assert _c.MIN_VALID_SEEDS == 32
    assert _c.MIN_DENOVO_SEEDS == 256
    assert _c.NULL_NOISE_FACTOR == 1.5


def test_verdict_threshold_constants_verbatim() -> None:
    assert _c.NOVELTY_FLOOR == 0.20
    assert _c.NO_SPURIOUS_TOL == 0.05
    assert _c.COMPETITION_MIN_VAR == 0.02


def test_scoring_constants_verbatim() -> None:
    # Superseding scoring constants (measurable ADR §5): JS metric, self-calibrating
    # gate (no absolute floor), directed-bigram support derived from M_FRAGMENTS.
    assert _c.DIVERGENCE == "jensen_shannon_base2"
    assert _c.FLOOR_REL == 0.0
    assert _c.TRANSITION_SUPPORT == 2256
    assert _c.TRANSITION_SUPPORT == _c.M_FRAGMENTS * (_c.M_FRAGMENTS - 1)


def test_retired_absolute_floor_is_absent() -> None:
    # The old absolute Jaccard floor was retired by the measurable ADR (Codex H1).
    assert not hasattr(_c, "DENOVO_DIVERGENCE_FLOOR")


def test_embedding_constants_verbatim() -> None:
    assert _c.EMBED_DIM == 16
    assert _c.EMBED_SALT == "es2-replay-v1"
