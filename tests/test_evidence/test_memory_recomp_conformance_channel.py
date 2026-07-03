"""Channel ``C`` helpers: argmax cell decode + formation-zone map (design §2)."""

from __future__ import annotations

import numpy as np

from erre_sandbox.evidence.memory_recomp_conformance.channel import (
    dominant_transition_cell,
    zone_of_formation,
)


def _encode(i: int, j: int, m: int) -> int:
    """ES-2 compact directed off-diagonal cell id (mirror of ``_bigram_cells``)."""
    return i * (m - 1) + (j - int(j > i))


def test_decode_is_inverse_of_encoding_for_every_cell() -> None:
    m = 6
    for i in range(m):
        for j in range(m):
            if i == j:
                continue
            dist = np.zeros(m * (m - 1))
            dist[_encode(i, j, m)] = 1.0
            assert dominant_transition_cell(dist, m) == (i, j)


def test_argmax_tie_break_is_content_index_ascending() -> None:
    # Two cells tie for the max mass; np.argmax + the lexicographic encoding must
    # pick the smaller (from, to) — content-index ascending (design §2).
    m = 6
    dist = np.zeros(m * (m - 1))
    dist[_encode(4, 5, m)] = 0.5
    dist[_encode(1, 0, m)] = 0.5  # lower (from, to) → must win the tie
    assert dominant_transition_cell(dist, m) == (1, 0)


def test_zone_of_formation_reads_trajectory_at_content_index() -> None:
    trajectory = [2, 0, 4, 1, 3, 3, 0]
    assert zone_of_formation(trajectory, 0) == 2
    assert zone_of_formation(trajectory, 2) == 4
    assert zone_of_formation(trajectory, 6) == 0
