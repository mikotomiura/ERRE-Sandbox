"""Input channel ``C`` for the memory-recomposition seam (design-final.md §2).

``C`` is the **argmax directed-transition cell** of an individual's idle
recomposition batch — the ES-2 ``transition_distribution`` (byte-inherited) over
the shared canonical content index. Two pure, deterministic helpers:

* :func:`dominant_transition_cell` — decode the argmax cell id of a
  ``(m·(m-1),)`` directed off-diagonal transition distribution back to a
  ``(from_content, to_content)`` pair. The argmax tie-break is **content-index
  ascending**, which ``np.argmax`` (first maximum) gives for free because the ES-2
  compact cell encoding ``i·(m-1) + (j - [j>i])`` is lexicographic in
  ``(from, to)`` (design-final.md §2, HIGH-1).
* :func:`zone_of_formation` — map the channel's ``to_content`` to the zone where
  that content was formed. On the ES-2 shared canonical contents the content index
  *is* the formation step, and formation happens exactly once per content, so the
  formation zone is simply ``trajectory[to_content]`` (1:1, no tie-break).

Neither helper reads any downstream ``D`` state — ``C`` is computed entirely from
the frozen ES-2 kernel's output (``DA-MEMSEAM-IMPL-1``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence


def dominant_transition_cell(distribution: np.ndarray, m: int) -> tuple[int, int]:
    """Decode the argmax cell of a directed off-diagonal transition distribution.

    ``distribution`` is a ``(m·(m-1),)`` probability (or count) vector over the ES-2
    compact directed off-diagonal cells ``cell = i·(m-1) + (j - [j > i])`` for
    ``i != j`` (see ``es2_replay.divergence._bigram_cells``). Returns the
    ``(from_content, to_content)`` pair of the argmax cell.

    The tie-break is **content-index ascending**: ``np.argmax`` returns the first
    maximal index and the encoding is monotone (lexicographic) in ``(i, j)``, so
    the smallest ``(from, to)`` wins a tie with no extra code (design-final.md §2).

    The inverse of the encoding: ``i = cell // (m-1)``; with ``r = cell % (m-1)``,
    ``j = r`` when ``r < i`` (the diagonal slot ``j = i`` was dropped, so low
    remainders are the below-diagonal targets) else ``j = r + 1``.
    """
    if m < 2:  # noqa: PLR2004 — a transition needs ≥2 contents
        msg = f"m must be >= 2 to have a transition cell (got {m})"
        raise ValueError(msg)
    cell = int(np.argmax(np.asarray(distribution)))
    from_content = cell // (m - 1)
    remainder = cell % (m - 1)
    to_content = remainder if remainder < from_content else remainder + 1
    return from_content, to_content


def zone_of_formation(trajectory: Sequence[int], to_content: int) -> int:
    """Zone index where content ``to_content`` was formed.

    On the ES-2 shared canonical contents the content index equals the formation
    step, and each content is formed exactly once, so the formation zone is the
    zone occupied at that step: ``trajectory[to_content]`` (design-final.md §2, a
    1:1 map — no tie-break). ``trajectory`` is the length-``M_FRAGMENTS`` formation
    walk of zone indices (``preferential_return_walk`` output).
    """
    return int(trajectory[to_content])


__all__ = ["dominant_transition_cell", "zone_of_formation"]
