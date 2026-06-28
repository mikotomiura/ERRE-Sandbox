"""③ de-novo novelty for the M13-ES2 replay apparatus (``design-final.md`` §6).

An individual's **recorded experience path** is its formation order
``[0, 1, …, m-1]`` (fragment ``i`` was laid down at step ``i``), so its recorded
**directed bigrams** are ``{(i, i+1)}``. A replay seed is novel to the extent its
transitions are *not* in that set.

* **primary floor** (Codex H3) — ``novel directed-transition rate``: the fraction
  of seeds containing **≥1** directed bigram ``(a, b)`` absent from the recorded
  path (i.e. ``b ≠ a + 1``). ``min_unseen_bigram_per_seed ≥ 1`` is the per-seed
  de-novo validity used for the A/B comparison.
* **secondary** (non-degenerate floor, *not* the primary) — ``exact de-novo
  rate``: the fraction of seeds whose sequence is **not** a contiguous
  sub-sequence of the recorded path. On this linear recorded path a contiguous
  sub-sequence is exactly a consecutive run ``[k, k+1, …]``, so the secondary
  coincides numerically with the primary here; it is kept distinct because Codex
  H3 demotes the (otherwise near-always-true) exact rate from the floor's lead.
* **temporal-replay negative control** (Codex H3) — a stream replay that follows
  formation order (:func:`temporal_replay_seeds`) must score **below** the novelty
  floor. If it does not, the novelty test is vacuous → apparatus INVALID →
  INCONCLUSIVE (the apparatus-validity floor, analogous to the ES-1 w0 ablation).

The kernel that produced ``seeds`` is order-blind (see :mod:`recombination`), so a
high novel rate here is *emergent*, not constructed — the non-circularity the
crossover rejection protects.
"""

from __future__ import annotations

import numpy as np


def _recorded_transition_mask(seeds: np.ndarray) -> np.ndarray:
    """``(n, l_seed-1)`` bool: transition ``k`` lands on the recorded next fragment.

    A directed bigram ``(seq[k], seq[k+1])`` is in the recorded path iff
    ``seq[k+1] == seq[k] + 1`` (the formation order ``[0..m-1]``).
    """
    return seeds[:, 1:] == seeds[:, :-1] + 1


def de_novo_eligible(seeds: np.ndarray) -> np.ndarray:
    """``(n,)`` bool: seed has ≥1 novel directed transition (primary, Codex H3).

    A seed is eligible unless **every** transition is a recorded ``(i, i+1)`` step.
    """
    if seeds.shape[1] < 2:  # noqa: PLR2004 — a single fragment has no transition
        return np.zeros(seeds.shape[0], dtype=bool)
    all_recorded = np.asarray(_recorded_transition_mask(seeds).all(axis=1))
    return ~all_recorded


def exact_de_novo_eligible(seeds: np.ndarray) -> np.ndarray:
    """``(n,)`` bool: seed is not a contiguous sub-sequence of the recorded path.

    Secondary floor (Codex H3, demoted): on the linear recorded path this is the
    complement of a consecutive run, which equals :func:`de_novo_eligible` here;
    surfaced separately so the forensic records both rates.
    """
    if seeds.shape[1] < 2:  # noqa: PLR2004
        return np.zeros(seeds.shape[0], dtype=bool)
    all_recorded = np.asarray(_recorded_transition_mask(seeds).all(axis=1))
    return ~all_recorded


def novel_transition_rate(seeds: np.ndarray, valid: np.ndarray) -> float:
    """Mean :func:`de_novo_eligible` over the **valid** seeds (0.0 if none valid)."""
    if not valid.any():
        return 0.0
    eligible = de_novo_eligible(seeds)
    return float(eligible[valid].mean())


def exact_de_novo_rate(seeds: np.ndarray, valid: np.ndarray) -> float:
    """Mean :func:`exact_de_novo_eligible` over the valid seeds (secondary)."""
    if not valid.any():
        return 0.0
    eligible = exact_de_novo_eligible(seeds)
    return float(eligible[valid].mean())


def de_novo_structure_ids(
    structure_ids: np.ndarray,
    seeds: np.ndarray,
    valid: np.ndarray,
) -> np.ndarray:
    """The structure ids of the seeds that are both valid and de-novo-eligible.

    These are the elements of an individual's de-novo seed-structure set that the
    A/B Jaccard divergence (and the within-agent split-half self-null) read.
    """
    mask = valid & de_novo_eligible(seeds)
    return structure_ids[mask]


def temporal_replay_seeds(
    m: int,
    l_seed: int,
    n: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """``(n, l_seed)`` seeds that follow the recorded temporal order (negative control).

    Each seed is a contiguous formation-order window ``[k, k+1, …, k+l_seed-1]`` for
    a uniformly drawn start ``k ∈ [0, m - l_seed]`` — a *stream replay* baseline.
    By construction every transition is a recorded ``(i, i+1)`` bigram, so
    :func:`novel_transition_rate` over these is 0.0: the control proves the novelty
    test **can fail** (Codex H3). Deterministic under ``rng``.
    """
    starts = rng.integers(0, m - l_seed + 1, size=n)
    offsets = np.arange(l_seed)
    return starts[:, None] + offsets[None, :]


__all__ = [
    "de_novo_eligible",
    "de_novo_structure_ids",
    "exact_de_novo_eligible",
    "exact_de_novo_rate",
    "novel_transition_rate",
    "temporal_replay_seeds",
]
