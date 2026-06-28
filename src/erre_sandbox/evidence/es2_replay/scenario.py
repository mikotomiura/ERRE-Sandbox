"""Blind scenario generator for the M13-ES2 path-recombination replay verdict.

Two same-base individuals A/B take **preferential-return walks** (Pólya-urn α=1)
over the real zone adjacency graph (mirrored from :mod:`erre_sandbox.world.zones`
and pinned to it in the scenario test). The only free quantity is the seed; the
walk has no stickiness/bias knob a designer could turn to manufacture divergence.
The start zone is blind-drawn and **shared by both arms** (matched nuisance).
Both arms form the **same canonical contents** ``c_0..c_{m-1}`` (shared synthetic
embeddings); **only where each content is formed differs, as a consequence of the
walk** — never hand-assigned.

Each arm's experience fragments feed the verdict-blind **replay kernel**
(:mod:`recombination`) → ``N_REPLAY`` seed structures. The de-novo-eligible seeds
(:mod:`novelty`) of A vs B give ``D_obs`` = the **Jensen-Shannon divergence** over
their pooled directed-transition distributions (:mod:`divergence`, measurable ADR
``.steering/20260628-es2-measurable-adr/`` — this supersedes the saturated
set-Jaccard scoring), measured against the content-stratified N-a permutation null
(:mod:`permutation_null`), with the N-b within-agent pairing permutation as a
sensitivity. The per-seed readouts feed the frozen conjunctive verdict
(:mod:`verdict_report`). The superseded Jaccard ``D_obs`` is kept as a forensic
contrast only.

This is **path-recombination** replay, distinct from
:mod:`erre_sandbox.cognition.world_model_replay` (fixed-stream reconcile replay).

Architecture: this module stays inside the ``evidence`` USE-surface (``schemas`` +
``memory`` + intra-``evidence``); world geometry is **mirrored** as local
constants and the scenario test asserts byte-equality with ``world.zones`` so the
mirror cannot silently drift. The GO / NO_GO / INCONCLUSIVE outcome is whatever
emerges and is recorded by ``scripts/es2_verdict_run.py`` — deliberately **not**
pinned in a test (pinning the verdict would re-bake the answer into the apparatus).
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import numpy as np

from erre_sandbox.evidence.es2_replay import constants as _c
from erre_sandbox.evidence.es2_replay.divergence import (
    co_occurrence_distribution,
    effective_support,
    js_divergence,
    novel_only_transition_distribution,
    transition_distribution,
    transition_distribution_all,
    tv_distance,
    unigram_distribution,
)
from erre_sandbox.evidence.es2_replay.novelty import (
    de_novo_structure_ids,
    exact_de_novo_rate,
    novel_transition_rate,
    temporal_replay_seeds,
)
from erre_sandbox.evidence.es2_replay.permutation_null import (
    jaccard_distance_int,
    n_a_null_distribution,
    n_b_null_distribution,
)
from erre_sandbox.evidence.es2_replay.recombination import (
    kernel_weights,
    pairwise_cosine,
    preferential_return_walk,
    proximity_matrix,
    replay_walks,
    semantic_matrix,
    structure_ids,
    synthetic_embeddings,
)
from erre_sandbox.evidence.es2_replay.verdict_report import (
    Es2Verdict,
    SeedResult,
    evaluate_verdict,
)
from erre_sandbox.schemas import Zone

if TYPE_CHECKING:
    from collections.abc import Sequence

# --- world-geometry mirror (pinned to erre_sandbox.world.zones in the test) ----

ZONES: tuple[Zone, ...] = (
    Zone.STUDY,
    Zone.PERIPATOS,
    Zone.CHASHITSU,
    Zone.AGORA,
    Zone.GARDEN,
)
"""The five zones in ``Zone`` declaration order (deterministic across interpreters)."""

NORMALIZED_ZONE_CENTERS: dict[Zone, tuple[float, float, float]] = {
    Zone.STUDY: (-1.0, 0.0, -1.0),
    Zone.PERIPATOS: (0.0, 0.0, 0.0),
    Zone.CHASHITSU: (1.0, 0.0, -1.0),
    Zone.AGORA: (0.0, 0.0, 1.0),
    Zone.GARDEN: (1.0, 0.0, 1.0),
}
"""Zone centroids on a **unit reference lattice** = ``world.zones.ZONE_CENTERS``
divided by ``world.zones._ZONE_OFFSET`` (identical mirror to ES-1; graded
proximity under the frozen ``gamma=0.5`` / ``coord_ref=1.0``)."""

ADJACENCY: dict[Zone, tuple[Zone, ...]] = {
    Zone.STUDY: (Zone.PERIPATOS,),
    Zone.PERIPATOS: (Zone.STUDY, Zone.CHASHITSU, Zone.AGORA, Zone.GARDEN),
    Zone.CHASHITSU: (Zone.PERIPATOS, Zone.GARDEN),
    Zone.AGORA: (Zone.PERIPATOS, Zone.GARDEN),
    Zone.GARDEN: (Zone.PERIPATOS, Zone.CHASHITSU, Zone.AGORA),
}
"""Walkable adjacency mirrored from ``world.zones.ADJACENCY`` (neighbour tuples in
``ZONES`` order so the walk is reproducible). Pinned in the test."""

_ZONE_INDEX: Final[dict[Zone, int]] = {z: i for i, z in enumerate(ZONES)}
_NEIGHBORS_IDX: Final[tuple[tuple[int, ...], ...]] = tuple(
    tuple(_ZONE_INDEX[n] for n in ADJACENCY[z]) for z in ZONES
)
_CENTERS_ARRAY: Final[np.ndarray] = np.array(
    [NORMALIZED_ZONE_CENTERS[z] for z in ZONES],
    dtype=np.float64,
)

# Deterministic numpy stream ids (one per independent sampling role per seed).
_SEED_BASE: Final[int] = 0x_E5_2A
_STREAM_REPLAY_A: Final[int] = 0
_STREAM_REPLAY_B: Final[int] = 1
_STREAM_TEMPORAL: Final[int] = 2
_STREAM_NULL_A: Final[int] = 3
_STREAM_NULL_B: Final[int] = 4
_STREAM_NO_SPURIOUS: Final[int] = 5


def _rng(seed: int, stream: int) -> np.random.Generator:
    """Independent reproducible numpy stream for one ``(scenario seed, role)``."""
    return np.random.default_rng([_SEED_BASE, seed, stream])


def _coords_of(trajectory: Sequence[int]) -> np.ndarray:
    """``(m, 3)`` formation-location array = visited zone centroids (lattice)."""
    return _CENTERS_ARRAY[np.asarray(trajectory, dtype=np.int64)]


def _effective_zones(trajectory: Sequence[int]) -> int:
    return len(set(trajectory))


def _arm_replay(
    coords: np.ndarray,
    semantic: np.ndarray,
    m: int,
    n_replay: int,
    l_seed: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Replay one arm → ``(seeds, valid, struct_ids)`` (all ``(n_replay, …)``)."""
    weights = kernel_weights(proximity_matrix(coords), semantic)
    seeds, valid = replay_walks(weights, n_replay, l_seed, rng)
    return seeds, valid, structure_ids(seeds, m)


def _split_half_d_self(
    seeds: np.ndarray,
    valid: np.ndarray,
    m: int,
) -> float:
    """Within-agent split-half self-divergence (Codex H6 noise reference, JS).

    Each half's de-novo directed-transition distribution is scored by JS. Because
    the new metric is **consistent** (the transition support ≪ the per-half
    transition count), this self-null shrinks with sample size instead of pinning at
    the saturation ceiling that made the old set-Jaccard ``D_self`` ≈ 1 — the
    structural defect the measurable ADR resolves.
    """
    half = seeds.shape[0] // 2
    p1 = transition_distribution(seeds[:half], valid[:half], m)
    p2 = transition_distribution(seeds[half:], valid[half:], m)
    return js_divergence(p1, p2)


def _no_spurious_margin(
    coords: np.ndarray,
    semantic: np.ndarray,
    m: int,
    n_replay: int,
    l_seed: int,
    seed: int,
) -> float:
    """③ semantic-isomorphic relabel control margin (Codex M2, ``design-final.md`` §8).

    Same trajectory, same pairwise semantic matrix, only the raw fragment-id
    namespace changed. Because **no** kernel / novelty primitive reads a raw
    fragment id (transition weight is ``proximity · semantic``; de-novo reads the
    formation-order index), relabeling the raw ids leaves the de-novo position set
    bit-identical, so the divergence collapses to 0 — proof the divergence is not a
    raw-id artifact (the ES-1 HIGH-2 / parity-confound failure mode). Realised as
    two replays of the identical apparatus on the **same** rng stream (the strongest
    isomorphism = identity semantic matrix); a non-zero margin could only appear if a
    raw-id dependence had leaked into the kernel. Scored by JS over the de-novo
    directed-transition distribution (bit-identical inputs ⇒ JS = 0).
    """
    seeds_ref, valid_ref, _struct_ref = _arm_replay(
        coords, semantic, m, n_replay, l_seed, _rng(seed, _STREAM_NO_SPURIOUS)
    )
    seeds_iso, valid_iso, _struct_iso = _arm_replay(
        coords, semantic, m, n_replay, l_seed, _rng(seed, _STREAM_NO_SPURIOUS)
    )
    p_ref = transition_distribution(seeds_ref, valid_ref, m)
    p_iso = transition_distribution(seeds_iso, valid_iso, m)
    return js_divergence(p_ref, p_iso)


@dataclass(frozen=True)
class SeedForensic:
    """Per-seed blind-generator provenance + diagnostics (recorded verbatim).

    The verdict-driving fields mirror :class:`SeedResult`; the remaining fields are
    **forensic only** (measurable ADR §6, non-promoting: they never change the
    verdict). They record the superseded Jaccard contrast, the TV / R-2 / R-3 /
    novel-only divergence contrasts, and the Codex H2 effective-support diagnostics
    that distinguish a true low-power INCONCLUSIVE from a metric artifact.
    """

    seed: int
    start_zone: Zone
    trajectory_a: tuple[Zone, ...]
    trajectory_b: tuple[Zone, ...]
    effective_zones_a: int
    effective_zones_b: int
    d_obs: float
    null_q_a: float
    delta_a: float
    null_q_b: float
    delta_b: float
    novel_transition_rate: float
    exact_de_novo_rate: float
    temporal_novel_rate: float
    n_denovo_a: int
    n_denovo_b: int
    d_self: float
    no_spurious_margin: float
    var_cosine: float
    # --- forensic only (non-promoting, measurable ADR §6) ---
    d_obs_jaccard: float
    """Superseded set-Jaccard ``D_obs`` (old saturated metric), kept for contrast."""
    tv_obs: float
    """Total-variation distance of the A/B transition distributions (contrast)."""
    novel_only_js: float
    """JS over the novel-only directed-transition distributions (Codex M1 contrast)."""
    cooccur_js: float
    """R-2 JS over the undirected co-occurrence distributions (marginal contrast)."""
    unigram_js: float
    """R-3 JS over the occupancy unigram distributions (marginal contrast)."""
    eff_support_a: float
    eff_support_b: float
    """Inverse-Simpson effective support of each arm's transition distribution (H2)."""
    hill1_a: float
    hill1_b: float
    """Shannon effective support ``exp(H)`` of each arm's transition dist (H2)."""
    nonzero_a: int
    nonzero_b: int
    """Occupied-cell count of each arm's transition distribution (H2)."""
    coverage_a: float
    coverage_b: float
    """Occupied fraction of the ``M²−M`` support of each arm (H2)."""
    temporal_nonzero: int
    """Occupied-cell count of the temporal-control unfiltered transition dist."""


def _content_var_cosine(semantic_cosine: np.ndarray) -> float:
    """``var(pairwise cosine)`` over the off-diagonal (② competition validity)."""
    m = semantic_cosine.shape[0]
    iu = np.triu_indices(m, k=1)
    return float(np.var(semantic_cosine[iu]))


def build_seed_result(
    seed: int,
    *,
    m: int = _c.M_FRAGMENTS,
    n_replay: int = _c.N_REPLAY,
    n_perm: int = _c.N_PERM,
    l_seed: int = _c.L_SEED,
) -> tuple[SeedResult, SeedForensic]:
    """One blind apparatus instantiation: walks → replay → null → ``SeedResult``.

    The two arms differ **only** by their preferential-return RNG sub-stream; the
    blind-drawn start, the canonical contents (shared synthetic embeddings), the
    fragment count, and every numpy sampling role are matched. The overridable
    sizes default to the frozen §11 constants; a test may pass small values for a
    fast pipeline check (the recorded verdict always uses the frozen defaults).
    """
    # ④ movement: shared blind start, two preferential-return walks.
    base = random.Random(f"es2-seed-{seed}")  # noqa: S311 — deterministic science RNG
    start = base.randrange(len(ZONES))
    rng_a = random.Random(f"es2-seed-{seed}-armA")  # noqa: S311 — deterministic RNG
    rng_b = random.Random(f"es2-seed-{seed}-armB")  # noqa: S311 — deterministic RNG
    traj_a = preferential_return_walk(start, m, _NEIGHBORS_IDX, rng_a)
    traj_b = preferential_return_walk(start, m, _NEIGHBORS_IDX, rng_b)
    coords_a = _coords_of(traj_a)
    coords_b = _coords_of(traj_b)

    # ② synthetic semantic competition (shared across arms; content-only).
    embeddings = synthetic_embeddings(m)
    cosine = pairwise_cosine(embeddings)
    semantic = semantic_matrix(embeddings)
    var_cosine = _content_var_cosine(cosine)

    # ③ replay both arms; D_obs = JS over the de-novo directed-transition
    # distributions (measurable ADR §1-§2). The replay kernel / walk / de-novo filter
    # are the frozen apparatus; only the readout is the JS-scored distribution.
    seeds_a, valid_a, struct_a = _arm_replay(
        coords_a, semantic, m, n_replay, l_seed, _rng(seed, _STREAM_REPLAY_A)
    )
    seeds_b, valid_b, struct_b = _arm_replay(
        coords_b, semantic, m, n_replay, l_seed, _rng(seed, _STREAM_REPLAY_B)
    )
    dist_a = transition_distribution(seeds_a, valid_a, m)
    dist_b = transition_distribution(seeds_b, valid_b, m)
    d_obs = js_divergence(dist_a, dist_b)

    # de-novo seed counts (sampling-adequacy gate input) + superseded Jaccard contrast.
    ids_a = de_novo_structure_ids(struct_a, seeds_a, valid_a)
    ids_b = de_novo_structure_ids(struct_b, seeds_b, valid_b)
    d_obs_jaccard = jaccard_distance_int(ids_a, ids_b)

    # ① N-a primary null + N-b sensitivity null → per-seed quantiles/deltas.
    d_perm_a = n_a_null_distribution(
        coords_a,
        coords_b,
        semantic,
        n_perm=n_perm,
        n_replay=n_replay,
        l_seed=l_seed,
        rng=_rng(seed, _STREAM_NULL_A),
    )
    d_perm_b = n_b_null_distribution(
        coords_a,
        coords_b,
        semantic,
        n_perm=n_perm,
        n_replay=n_replay,
        l_seed=l_seed,
        rng=_rng(seed, _STREAM_NULL_B),
    )
    null_q_a = float(np.quantile(d_perm_a, _c.PERM_NULL_QUANTILE))
    null_q_b = float(np.quantile(d_perm_b, _c.PERM_NULL_QUANTILE))

    # ③ novelty: primary novel-transition + secondary exact + temporal control.
    novel = statistics.median(
        [
            novel_transition_rate(seeds_a, valid_a),
            novel_transition_rate(seeds_b, valid_b),
        ]
    )
    exact = statistics.median(
        [
            exact_de_novo_rate(seeds_a, valid_a),
            exact_de_novo_rate(seeds_b, valid_b),
        ]
    )
    temporal_seeds = temporal_replay_seeds(
        m, l_seed, n_replay, _rng(seed, _STREAM_TEMPORAL)
    )
    temporal_valid = np.ones(temporal_seeds.shape[0], dtype=bool)
    temporal_novel = novel_transition_rate(temporal_seeds, temporal_valid)

    # Codex H6 noise reference (split-half JS) + Codex M2 no-spurious control (JS).
    d_self = statistics.median(
        [
            _split_half_d_self(seeds_a, valid_a, m),
            _split_half_d_self(seeds_b, valid_b, m),
        ]
    )
    no_spurious = _no_spurious_margin(coords_a, semantic, m, n_replay, l_seed, seed)

    # Forensic contrasts (non-promoting, measurable ADR §6): TV / R-2 / R-3 /
    # novel-only divergences + Codex H2 effective-support diagnostics + temporal JS.
    tv_obs = tv_distance(dist_a, dist_b)
    novel_only_js = js_divergence(
        novel_only_transition_distribution(seeds_a, valid_a, m),
        novel_only_transition_distribution(seeds_b, valid_b, m),
    )
    cooccur_js = js_divergence(
        co_occurrence_distribution(seeds_a, valid_a, m),
        co_occurrence_distribution(seeds_b, valid_b, m),
    )
    unigram_js = js_divergence(
        unigram_distribution(seeds_a, valid_a, m),
        unigram_distribution(seeds_b, valid_b, m),
    )
    supp_a = effective_support(dist_a)
    supp_b = effective_support(dist_b)
    temporal_nonzero = effective_support(
        transition_distribution_all(temporal_seeds, m)
    ).nonzero

    eff_a = _effective_zones(traj_a)
    eff_b = _effective_zones(traj_b)
    result = SeedResult(
        seed=seed,
        valid=True,
        d_obs=d_obs,
        null_q_a=null_q_a,
        delta_a=d_obs - null_q_a,
        null_q_b=null_q_b,
        delta_b=d_obs - null_q_b,
        novel_transition_rate=novel,
        exact_de_novo_rate=exact,
        temporal_novel_rate=temporal_novel,
        n_denovo_a=int(ids_a.size),
        n_denovo_b=int(ids_b.size),
        effective_zones_a=eff_a,
        effective_zones_b=eff_b,
        d_self=d_self,
        no_spurious_margin=no_spurious,
        var_cosine=var_cosine,
    )
    forensic = SeedForensic(
        seed=seed,
        start_zone=ZONES[start],
        trajectory_a=tuple(ZONES[i] for i in traj_a),
        trajectory_b=tuple(ZONES[i] for i in traj_b),
        effective_zones_a=eff_a,
        effective_zones_b=eff_b,
        d_obs=d_obs,
        null_q_a=null_q_a,
        delta_a=d_obs - null_q_a,
        null_q_b=null_q_b,
        delta_b=d_obs - null_q_b,
        novel_transition_rate=novel,
        exact_de_novo_rate=exact,
        temporal_novel_rate=temporal_novel,
        n_denovo_a=int(ids_a.size),
        n_denovo_b=int(ids_b.size),
        d_self=d_self,
        no_spurious_margin=no_spurious,
        var_cosine=var_cosine,
        d_obs_jaccard=d_obs_jaccard,
        tv_obs=tv_obs,
        novel_only_js=novel_only_js,
        cooccur_js=cooccur_js,
        unigram_js=unigram_js,
        eff_support_a=supp_a.simpson,
        eff_support_b=supp_b.simpson,
        hill1_a=supp_a.hill1,
        hill1_b=supp_b.hill1,
        nonzero_a=supp_a.nonzero,
        nonzero_b=supp_b.nonzero,
        coverage_a=supp_a.coverage,
        coverage_b=supp_b.coverage,
        temporal_nonzero=int(temporal_nonzero),
    )
    return result, forensic


@dataclass(frozen=True)
class VerdictRun:
    """The frozen ES-2 verdict plus the full blind-generator forensic trail."""

    verdict: Es2Verdict
    seeds: tuple[SeedForensic, ...]
    median_d_obs: float


def run_verdict(seed_bank: Sequence[int]) -> VerdictRun:
    """Run the blind generator over ``seed_bank`` and render the frozen verdict."""
    results: list[SeedResult] = []
    forensics: list[SeedForensic] = []
    for seed in seed_bank:
        result, forensic = build_seed_result(seed)
        results.append(result)
        forensics.append(forensic)
    verdict = evaluate_verdict(results)
    median_d_obs = statistics.median([r.d_obs for r in results]) if results else 0.0
    return VerdictRun(
        verdict=verdict,
        seeds=tuple(forensics),
        median_d_obs=median_d_obs,
    )


def default_seed_bank() -> tuple[int, ...]:
    """The pre-registered blind seed bank: ``range(N_SEED)`` (= 0..63).

    Fixed before the run; no seed is added or dropped after seeing a divergence
    (forking-paths guard). A superseding ADR is required to change it.
    """
    return tuple(range(_c.N_SEED))


__all__ = [
    "ADJACENCY",
    "NORMALIZED_ZONE_CENTERS",
    "ZONES",
    "SeedForensic",
    "VerdictRun",
    "build_seed_result",
    "default_seed_bank",
    "run_verdict",
]
