"""Movement + recombination kernel for the M13-ES2 replay apparatus.

Three deterministic primitives, all GPU/LLM-free and ``numpy``/stdlib-only:

* **④ movement** (:func:`preferential_return_walk`, ``design-final.md`` §2) — a
  Pólya-urn α=1 preferential-return walk over the zone adjacency graph. Early
  stochastic reinforcement diverges two same-base individuals into distinct
  home-ranges with re-visits.
* **② semantic competition** (:func:`synthetic_embeddings` /
  :func:`semantic_matrix`, §3) — a deterministic synthetic structured embedding
  ``e_i = unit(hash(EMBED_SALT, i))`` so pairwise cosine varies and the replay
  kernel makes space and meaning *compete*. This is **synthetic** semantic
  competition (verdict-blind, not natural meaning; Codex M3); a
  ``var(pairwise cosine)`` validity gate lives in :mod:`verdict_report`.
* **③ recombination kernel** (:func:`kernel_weights` / :func:`replay_walks`, §4)
  — a **stochastic replay walk** whose transition weight is
  ``w_{i→j} ∝ proximity(loc_i, loc_j) · sem(e_i, e_j)``. ``proximity`` reuses the
  ES-1 frozen :func:`erre_sandbox.memory.retrieval.spatial_proximity` term
  (read-only; :func:`proximity_matrix` is the vectorised equivalent and is pinned
  byte-equal to it in the test). The kernel reads **neither temporal order, nor
  A/B label, nor novelty** (non-circularity). Codex H2: ``w_{i→i} = 0`` and the
  walk is self-avoiding, so each seed is ``L_SEED`` *distinct* fragments
  (``unique_fragment_count == L_SEED``); a degenerate (graph-unreachable) walk is
  marked invalid.

**Crossover is deliberately not implemented** (DA-ES2-1): a segment-crossover
replay would *construct* experience-absent splice transitions, mechanically
guaranteeing de-novo novelty → covertly circular w.r.t. ③. Novelty must emerge
from the order-blind walk, which is why the kernel is a plain weighted walk.
"""

from __future__ import annotations

import hashlib
import math
from typing import TYPE_CHECKING

import numpy as np

from erre_sandbox.evidence.es2_replay import constants as _c
from erre_sandbox.memory.retrieval import (
    DEFAULT_SPATIAL_COORD_REF,
    DEFAULT_SPATIAL_GAMMA,
)

if TYPE_CHECKING:
    import random
    from collections.abc import Sequence

# --- ④ movement: preferential-return walk (§2) --------------------------------


def preferential_return_walk(
    start: int,
    steps: int,
    neighbors: Sequence[Sequence[int]],
    rng: random.Random,
    *,
    alpha: float = _c.POLYA_ALPHA,
) -> list[int]:
    """Length-``steps`` Pólya-urn preferential-return walk over ``neighbors``.

    ``neighbors[z]`` lists the zone indices adjacent to zone ``z`` (a static
    adjacency graph). At each step the current zone is recorded, then the walker
    moves to a neighbour drawn with probability ``∝ alpha + visit_count(neighbour)``
    and that neighbour's visit count is incremented (Song 2010 preferential
    return; ``alpha`` is the canonical Pólya prior). ``trajectory[i]`` is the zone
    occupied when experience fragment ``i`` is formed; ``trajectory[0] == start``
    so two arms sharing a blind-drawn start co-locate fragment 0 (a conservative
    matched element). Fully determined by ``rng``.
    """
    here = start
    visit_count = [0] * len(neighbors)
    visit_count[start] = 1
    trajectory: list[int] = []
    for _ in range(steps):
        trajectory.append(here)
        nbrs = neighbors[here]
        weights = [alpha + visit_count[z] for z in nbrs]
        here = rng.choices(list(nbrs), weights=weights, k=1)[0]
        visit_count[here] += 1
    return trajectory


# --- ② semantic competition: synthetic structured embedding (§3) --------------


def synthetic_embeddings(
    m: int,
    *,
    dim: int = _c.EMBED_DIM,
    salt: str = _c.EMBED_SALT,
) -> np.ndarray:
    """Deterministic unit embeddings ``e_i = unit(hash(salt, i))`` (Codex M3).

    Each component is derived from a SHA-256 of ``f"{salt}:{i}:{d}"`` mapped to
    ``[-1, 1)``, then the row is L2-normalised. Reproducible across interpreters
    (no ``hash()`` salting). Returns an ``(m, dim)`` array of unit rows whose
    pairwise cosine varies — the ② "synthetic semantic competition" the kernel
    weighs against space. ``var(pairwise cosine)`` is gated in :mod:`verdict_report`.
    """
    out = np.empty((m, dim), dtype=np.float64)
    for i in range(m):
        for d in range(dim):
            digest = hashlib.sha256(f"{salt}:{i}:{d}".encode()).digest()
            u = int.from_bytes(digest[:8], "big") / float(1 << 64)  # [0, 1)
            out[i, d] = 2.0 * u - 1.0
        norm = math.sqrt(float(out[i] @ out[i]))
        if norm > 0.0:
            out[i] /= norm
    return out


def pairwise_cosine(embeddings: np.ndarray) -> np.ndarray:
    """Pairwise cosine matrix for L2-normalised ``embeddings`` (= dot products)."""
    return embeddings @ embeddings.T


def semantic_matrix(embeddings: np.ndarray) -> np.ndarray:
    """``sem(e_i, e_j) = (1 + cosine) / 2 ∈ (0, 1]`` (§4).

    Strictly positive off the antipodal degenerate case, so the kernel never zeroes
    a transition on the semantic factor alone.
    """
    return (1.0 + pairwise_cosine(embeddings)) / 2.0


# --- ③ recombination kernel: proximity × semantic replay walk (§4) ------------


def proximity_matrix(
    coords: np.ndarray,
    *,
    gamma: float = DEFAULT_SPATIAL_GAMMA,
    coord_ref: float = DEFAULT_SPATIAL_COORD_REF,
) -> np.ndarray:
    """Vectorised ``proximity(loc_i, loc_j)`` over fragment locations ``coords``.

    ``coords`` is ``(m, 3)`` (normalised-lattice zone centroids). Returns
    ``exp(-gamma * euclidean(i, j) / coord_ref)`` — the exact formula of the ES-1
    frozen :func:`erre_sandbox.memory.retrieval.spatial_proximity`, evaluated as a
    matrix. The defaults are imported from ``memory.retrieval`` (the frozen
    spatial-term knobs, ``gamma=0.5`` / ``coord_ref=1.0``), not re-invented, and
    ``tests/test_evidence/test_es2_recombination.py`` pins every element equal to a
    direct ``spatial_proximity`` call so this vectorisation cannot silently drift.
    """
    diff = coords[:, None, :] - coords[None, :, :]
    dist = np.sqrt(np.einsum("ijk,ijk->ij", diff, diff))
    ref = coord_ref if coord_ref > 0.0 else 1.0
    return np.exp(-gamma * dist / ref)


def kernel_weights(proximity: np.ndarray, semantic: np.ndarray) -> np.ndarray:
    """``w_{i→j} = proximity · semantic`` with the diagonal zeroed (Codex H2).

    ``w_{i→i} = 0`` removes the self-loop that ``proximity(i, i) = 1`` would
    otherwise make the strongest transition (which would inflate de-novo rate on a
    same-fragment repeat). Verdict-blind: no temporal / label / novelty term.
    """
    w = proximity * semantic
    np.fill_diagonal(w, 0.0)
    return w


def replay_walks(
    weights: np.ndarray,
    n_replay: int,
    l_seed: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Sample ``n_replay`` self-avoiding weighted walks of length ``l_seed``.

    Each walk starts at a uniformly drawn fragment and, at every step, moves to a
    **not-yet-visited** fragment chosen with probability ``∝ weights[cur, :]``
    (self-avoidance ⇒ ``w_{i→i}=0``, adjacent-duplicate forbidden, and
    ``unique_fragment_count == l_seed`` for a valid walk; Codex H2). A walk that
    reaches a dead end (every unvisited candidate has weight 0 — only possible on a
    degenerate graph) is flagged invalid.

    Returns ``(seeds, valid)``: ``seeds`` is ``(n_replay, l_seed)`` int64 fragment
    indices; ``valid`` is ``(n_replay,)`` bool. Deterministic under ``rng`` (the
    bitstream is consumed in a fixed order: start indices, then one uniform vector
    per step).
    """
    m = weights.shape[0]
    rows = np.arange(n_replay)
    seeds = np.empty((n_replay, l_seed), dtype=np.int64)
    seeds[:, 0] = rng.integers(0, m, size=n_replay)
    visited = np.zeros((n_replay, m), dtype=bool)
    visited[rows, seeds[:, 0]] = True
    valid = np.ones(n_replay, dtype=bool)

    for step in range(1, l_seed):
        cur = seeds[:, step - 1]
        w = np.where(visited, 0.0, weights[cur])
        totals = w.sum(axis=1)
        valid &= totals > 0.0
        safe = np.where(totals > 0.0, totals, 1.0)
        cdf = np.cumsum(w / safe[:, None], axis=1)
        u = rng.random(n_replay)
        nxt = np.clip((cdf < u[:, None]).sum(axis=1), 0, m - 1)
        seeds[:, step] = nxt
        visited[rows, nxt] = True

    return seeds, valid


def structure_ids(seeds: np.ndarray, m: int) -> np.ndarray:
    """Encode each seed's fragment sequence as a single base-``m`` integer id.

    ``canonical_seed_structure_id`` over **content** ids (Codex H1): both arms form
    the same canonical content set ``c_0..c_{m-1}``, so a seed's content-id sequence
    *is* its fragment-index sequence here. The integer ``Σ seq[k] · m^{L-1-k}`` is a
    collision-free, order-sensitive encoding (``m^L = 48^4 ≈ 5.3e6`` fits int64),
    used for fast set divergence; the raw per-arm fragment id (disjoint across arms)
    never enters this comparison key.
    """
    ids = np.zeros(seeds.shape[0], dtype=np.int64)
    for k in range(seeds.shape[1]):
        ids = ids * m + seeds[:, k]
    return ids


__all__ = [
    "kernel_weights",
    "pairwise_cosine",
    "preferential_return_walk",
    "proximity_matrix",
    "replay_walks",
    "semantic_matrix",
    "structure_ids",
    "synthetic_embeddings",
]
