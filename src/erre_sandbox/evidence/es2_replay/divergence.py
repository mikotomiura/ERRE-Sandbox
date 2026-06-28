"""Distribution-divergence scoring for the M13-ES2 replay (measurable ADR §1-§2).

This module **supersedes** the ES-2 set-Jaccard scoring. The /reimagine hybrid
(``.steering/20260628-es2-measurable-adr/``) moved the statistic from a *set*
over seed-structure tuples (support ``M^L = 48^4 ≈ 5.3e6`` ≫ ``N_REPLAY=4096`` ⇒
structurally saturated, the old INCONCLUSIVE artifact) to a *distribution* over a
support **much smaller** than the observation count, so the estimator is
**consistent** (the within-agent split-half noise shrinks with sample size rather
than pinning at 1).

Primary estimand (ADR §1, Codex M1/L2) — the **transition distribution among
de-novo-eligible seeds**: pool every adjacent directed bigram ``(seq[k]→seq[k+1])``
of every de-novo-eligible seed (with multiplicity), over the directed off-diagonal
cells ``(i→j), i≠j`` (support ``M²−M``), then normalise. This is **not** "the
distribution of novel bigrams" — the de-novo condition selects the *seeds*, then
**all** their transitions are counted (Codex M1). The novel-only transition
distribution is a forensic-only contrast.

Divergence (ADR §2, Codex L1) = **Jensen-Shannon, base-2, ∈[0,1]**: symmetric,
bounded, graceful on zero support (``0·log0 = 0``), and **no smoothing parameter**
(no rigging surface). It is a *divergence*, not a metric (triangle inequality not
required). Total-variation distance is provided as a forensic contrast only.

Everything here is ``numpy``/stdlib-only and verdict-blind: it reads the seed
sequences (content indices) the frozen apparatus emits and nothing else. The raw
per-arm fragment id never enters a transition cell (H1: the cells are on the
shared canonical content index).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from erre_sandbox.evidence.es2_replay.novelty import de_novo_eligible


def _bigram_cells(seeds: np.ndarray, m: int) -> np.ndarray:
    """Compact directed off-diagonal cell ids for every adjacent bigram of ``seeds``.

    ``seeds`` is ``(n, l_seed)`` content indices. The frozen kernel is self-avoiding
    (``seq[k+1] != seq[k]``), so every adjacent bigram ``(i, j)`` has ``i != j`` and
    maps bijectively to ``[0, m·(m-1))`` via ``i·(m-1) + (j - [j > i])`` (drop the
    diagonal slot). Returns a flat ``(n·(l_seed-1),)`` int64 array; empty if there
    is no transition.
    """
    if seeds.size == 0 or seeds.shape[1] < 2:  # noqa: PLR2004 — need ≥2 to form a bigram
        return np.empty(0, dtype=np.int64)
    froms = seeds[:, :-1].reshape(-1).astype(np.int64)
    tos = seeds[:, 1:].reshape(-1).astype(np.int64)
    return froms * (m - 1) + (tos - (tos > froms).astype(np.int64))


def _normalise(counts: np.ndarray) -> np.ndarray:
    """Normalise non-negative counts to a probability vector (zeros stay zeros)."""
    total = counts.sum()
    if total <= 0:
        return counts.astype(np.float64)
    return counts.astype(np.float64) / float(total)


def transition_distribution(seeds: np.ndarray, valid: np.ndarray, m: int) -> np.ndarray:
    """Primary estimand: pooled directed-transition distribution over de-novo seeds.

    Selects the seeds that are both ``valid`` and de-novo-eligible, pools **all**
    their adjacent directed bigrams with multiplicity, and normalises over the
    ``m·(m-1)`` off-diagonal cells (ADR §1). Returns a ``(m·(m-1),)`` distribution
    (all-zeros if no de-novo seed exists; the verdict gate handles under-sampling).
    """
    mask = valid & de_novo_eligible(seeds)
    cells = _bigram_cells(seeds[mask], m)
    counts = np.bincount(cells, minlength=m * (m - 1)).astype(np.float64)
    return _normalise(counts)


def transition_distribution_all(seeds: np.ndarray, m: int) -> np.ndarray:
    """Unfiltered directed-transition distribution over **all** ``seeds`` (forensic).

    No de-novo filter (Codex H3): used only for the temporal-replay control's
    transition forensic, where the de-novo-eligible set is empty by construction so
    the filtered estimand is ill-defined. Never feeds the verdict.
    """
    cells = _bigram_cells(seeds, m)
    counts = np.bincount(cells, minlength=m * (m - 1)).astype(np.float64)
    return _normalise(counts)


def co_occurrence_distribution(
    seeds: np.ndarray, valid: np.ndarray, m: int
) -> np.ndarray:
    """R-2 forensic: pooled **undirected** adjacent co-occurrence distribution.

    Support ``m·(m-1)/2`` (folds ``(i,j)`` and ``(j,i)``). Forensic contrast so the
    primary directed signal is shown not to be a co-occurrence marginal artifact.
    """
    mask = valid & de_novo_eligible(seeds)
    sub = seeds[mask]
    if sub.size == 0 or sub.shape[1] < 2:  # noqa: PLR2004
        return np.zeros(m * (m - 1) // 2, dtype=np.float64)
    a = sub[:, :-1].reshape(-1).astype(np.int64)
    b = sub[:, 1:].reshape(-1).astype(np.int64)
    lo = np.minimum(a, b)
    hi = np.maximum(a, b)
    # Upper-triangular pair index: Σ_{r<lo}(m-1-r) + (hi-lo-1).
    idx = lo * (2 * m - lo - 1) // 2 + (hi - lo - 1)
    counts = np.bincount(idx, minlength=m * (m - 1) // 2).astype(np.float64)
    return _normalise(counts)


def unigram_distribution(seeds: np.ndarray, valid: np.ndarray, m: int) -> np.ndarray:
    """R-3 forensic: pooled fragment-occupancy unigram distribution (support ``m``).

    Forensic contrast so the primary directed signal is shown not to be an occupancy
    marginal artifact.
    """
    mask = valid & de_novo_eligible(seeds)
    sub = seeds[mask]
    if sub.size == 0:
        return np.zeros(m, dtype=np.float64)
    counts = np.bincount(sub.reshape(-1).astype(np.int64), minlength=m).astype(
        np.float64
    )
    return _normalise(counts)


def novel_only_transition_distribution(
    seeds: np.ndarray, valid: np.ndarray, m: int
) -> np.ndarray:
    """Forensic: directed-transition distribution counting **only novel** bigrams.

    Like :func:`transition_distribution` but a bigram ``(i, j)`` is counted only if
    it is novel (``j != i + 1``, i.e. not a recorded formation-order step). Codex M1
    keeps this distinct from the primary (which counts *all* bigrams of de-novo
    seeds); forensic, never the verdict.
    """
    mask = valid & de_novo_eligible(seeds)
    sub = seeds[mask]
    if sub.size == 0 or sub.shape[1] < 2:  # noqa: PLR2004
        return np.zeros(m * (m - 1), dtype=np.float64)
    froms = sub[:, :-1].reshape(-1).astype(np.int64)
    tos = sub[:, 1:].reshape(-1).astype(np.int64)
    novel = tos != froms + 1
    froms, tos = froms[novel], tos[novel]
    cells = froms * (m - 1) + (tos - (tos > froms).astype(np.int64))
    counts = np.bincount(cells, minlength=m * (m - 1)).astype(np.float64)
    return _normalise(counts)


def _kl_base2(p: np.ndarray, q: np.ndarray) -> float:
    """``Σ p·log2(p/q)`` with the ``0·log0 = 0`` convention (``q>0`` where ``p>0``)."""
    mask = p > 0.0
    return float(np.sum(p[mask] * np.log2(p[mask] / q[mask])))


def js_divergence(p: np.ndarray, q: np.ndarray) -> float:
    """Jensen-Shannon divergence (base-2, ∈[0,1]) between distributions ``p``/``q``.

    ``JS = ½·KL(p‖M) + ½·KL(q‖M)`` with ``M = ½(p+q)`` and ``log₂``. Inputs are
    normalised defensively (counts accepted); a zero-mass input yields 0.0
    (ill-defined distribution — the under-sampling gate, not this function, rejects
    it). Disjoint support correctly gives JS = 1 (genuinely non-overlapping
    distributions — distinct from the set-Jaccard's sparse-driven spurious 1).
    """
    p = np.asarray(p, dtype=np.float64)
    q = np.asarray(q, dtype=np.float64)
    sp = float(p.sum())
    sq = float(q.sum())
    if sp <= 0.0 or sq <= 0.0:
        return 0.0
    p = p / sp
    q = q / sq
    mix = 0.5 * (p + q)
    js = 0.5 * _kl_base2(p, mix) + 0.5 * _kl_base2(q, mix)
    return float(min(max(js, 0.0), 1.0))


def tv_distance(p: np.ndarray, q: np.ndarray) -> float:
    """Total-variation distance ``½‖p−q‖₁ ∈ [0,1]`` (forensic metric contrast)."""
    p = np.asarray(p, dtype=np.float64)
    q = np.asarray(q, dtype=np.float64)
    sp = float(p.sum())
    sq = float(q.sum())
    if sp <= 0.0 or sq <= 0.0:
        return 0.0
    return float(0.5 * np.abs(p / sp - q / sq).sum())


@dataclass(frozen=True)
class SupportDiagnostics:
    """Effective-support diagnostics for one observed distribution (Codex H2).

    Forensic, threshold-free. When ``D_self`` re-masks the signal these say whether
    that is a **metric artifact or a true low-power** measurement: a plug-in JS on a
    same-distribution split is small only when the effective support is small
    relative to the sample size.
    """

    nonzero: int
    """Number of occupied cells (raw occupancy)."""
    coverage: float
    """``nonzero / support`` (occupied fraction of the ``m·(m-1)`` cells)."""
    hill1: float
    """Shannon effective support ``exp(H)``, ``H`` in nats (Hill number order 1)."""
    simpson: float
    """Inverse-Simpson effective support ``1 / Σ p²`` (Hill number order 2)."""


def effective_support(p: np.ndarray) -> SupportDiagnostics:
    """Effective-support diagnostics of a (count or normalised) distribution ``p``."""
    p = np.asarray(p, dtype=np.float64)
    total = float(p.sum())
    support = int(p.size)
    if total <= 0.0:
        return SupportDiagnostics(nonzero=0, coverage=0.0, hill1=0.0, simpson=0.0)
    p = p / total
    nz = p[p > 0.0]
    nonzero = int(nz.size)
    entropy = float(-np.sum(nz * np.log(nz)))  # nats
    hill1 = float(np.exp(entropy))
    simpson = float(1.0 / np.sum(p * p))
    coverage = nonzero / support if support > 0 else 0.0
    return SupportDiagnostics(
        nonzero=nonzero,
        coverage=coverage,
        hill1=hill1,
        simpson=simpson,
    )


__all__ = [
    "SupportDiagnostics",
    "co_occurrence_distribution",
    "effective_support",
    "js_divergence",
    "novel_only_transition_distribution",
    "transition_distribution",
    "transition_distribution_all",
    "tv_distance",
    "unigram_distribution",
]
