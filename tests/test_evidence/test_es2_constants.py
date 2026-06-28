"""Pin the M13-ES2 frozen §11 constants to the ADR table verbatim.

The ES-2 pre-registration freeze (``.steering/20260628-m13-es2-replay/``,
/reimagine hybrid + Codex ADOPT-WITH-CHANGES → all 6 HIGH reflected before
freeze) fixed every threshold **before** any replay result was seen. This test is
the forking-paths guard's regression pin: a constant can only change by a
deliberate edit that also updates this expected table (which itself requires a
superseding ADR).
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
    assert _c.DENOVO_DIVERGENCE_FLOOR == 0.10
    assert _c.NOVELTY_FLOOR == 0.20
    assert _c.NO_SPURIOUS_TOL == 0.05
    assert _c.COMPETITION_MIN_VAR == 0.02


def test_embedding_constants_verbatim() -> None:
    assert _c.EMBED_DIM == 16
    assert _c.EMBED_SALT == "es2-replay-v1"
