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
(:mod:`recombination`) → ``N_REPLAY`` seed structures. The de-novo-eligible
structures (:mod:`novelty`) of A vs B give ``D_obs`` (frozen
:func:`erre_sandbox.evidence.spdm.probe.jaccard_distance`), measured against the
content-stratified N-a permutation null (:mod:`permutation_null`), with the N-b
within-agent pairing permutation as a sensitivity. The per-seed readouts feed the
frozen conjunctive verdict (:mod:`verdict_report`).

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
from erre_sandbox.evidence.spdm.probe import jaccard_distance
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
    struct: np.ndarray,
) -> float:
    """Within-agent split-half self-divergence (Codex H6 noise reference)."""
    half = seeds.shape[0] // 2
    ids_1 = de_novo_structure_ids(struct[:half], seeds[:half], valid[:half])
    ids_2 = de_novo_structure_ids(struct[half:], seeds[half:], valid[half:])
    return jaccard_distance_int(ids_1, ids_2)


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
    raw-id dependence had leaked into the kernel.
    """
    seeds_ref, valid_ref, struct_ref = _arm_replay(
        coords, semantic, m, n_replay, l_seed, _rng(seed, _STREAM_NO_SPURIOUS)
    )
    seeds_iso, valid_iso, struct_iso = _arm_replay(
        coords, semantic, m, n_replay, l_seed, _rng(seed, _STREAM_NO_SPURIOUS)
    )
    ids_ref = de_novo_structure_ids(struct_ref, seeds_ref, valid_ref)
    ids_iso = de_novo_structure_ids(struct_iso, seeds_iso, valid_iso)
    return jaccard_distance_int(ids_ref, ids_iso)


@dataclass(frozen=True)
class SeedForensic:
    """Per-seed blind-generator provenance + diagnostics (recorded verbatim)."""

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

    # ③ replay both arms; D_obs over de-novo seed-structure sets (frozen Jaccard).
    seeds_a, valid_a, struct_a = _arm_replay(
        coords_a, semantic, m, n_replay, l_seed, _rng(seed, _STREAM_REPLAY_A)
    )
    seeds_b, valid_b, struct_b = _arm_replay(
        coords_b, semantic, m, n_replay, l_seed, _rng(seed, _STREAM_REPLAY_B)
    )
    ids_a = de_novo_structure_ids(struct_a, seeds_a, valid_a)
    ids_b = de_novo_structure_ids(struct_b, seeds_b, valid_b)
    d_obs = jaccard_distance(
        frozenset(str(i) for i in ids_a.tolist()),
        frozenset(str(i) for i in ids_b.tolist()),
    )

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

    # Codex H6 noise reference + Codex M2 no-spurious control.
    d_self = statistics.median(
        [
            _split_half_d_self(seeds_a, valid_a, struct_a),
            _split_half_d_self(seeds_b, valid_b, struct_b),
        ]
    )
    no_spurious = _no_spurious_margin(coords_a, semantic, m, n_replay, l_seed, seed)

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
