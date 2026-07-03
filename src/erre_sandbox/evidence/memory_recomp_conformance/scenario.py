"""Blind scenario generator for the memory-recomposition seam verdict (§2 / §5).

Each scenario seed instantiates **one** same-base individual:

1. a shared blind-drawn **start zone** feeds a Pólya-urn **formation walk** (the
   ES-2 ``preferential_return_walk``, byte-inherited) → the formation trajectory;
2. the trajectory's fragment locations + the ES-2 synthetic semantic competition
   feed the frozen **replay kernel** → the **idle recomposition batch** whose
   directed-transition distribution's argmax cell is the channel ``C``
   (``STREAM_C_IDLE``);
3. ``C``'s ``to_content`` fixes a ``target_zone`` (``zone_of_formation``);
4. an **independent** post-idle occupancy walk ``D`` (``STREAM_D_POST_IDLE``,
   independent ``visit_count``, the **same shared start** as the formation walk —
   the "post-idle" spatial continuity, ``DA-MEMSEAM-IMPL-2``) is run for the
   marginal + each ``target_zone`` config on shared per-step noise → the
   ``conform`` 5-vector.

World geometry is **reused** from :mod:`erre_sandbox.evidence.es2_replay.scenario`
(already pinned byte-equal to ``world.zones`` in the ES-2 scenario test) rather than
re-mirrored. The verdict is whatever emerges and is recorded by
``scripts/memory_recomp_conformance_verdict_run.py`` — deliberately **not** pinned
in a test (pinning the verdict would re-bake the answer into the apparatus).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import numpy as np

from erre_sandbox.evidence.es2_replay.divergence import transition_distribution
from erre_sandbox.evidence.es2_replay.recombination import (
    kernel_weights,
    preferential_return_walk,
    proximity_matrix,
    replay_walks,
    semantic_matrix,
    synthetic_embeddings,
)
from erre_sandbox.evidence.es2_replay.scenario import (
    ADJACENCY,
    NORMALIZED_ZONE_CENTERS,
    ZONES,
)
from erre_sandbox.evidence.memory_recomp_conformance import constants as _c
from erre_sandbox.evidence.memory_recomp_conformance.channel import (
    dominant_transition_cell,
    zone_of_formation,
)
from erre_sandbox.evidence.memory_recomp_conformance.conformance_stats import (
    argmax_stability,
    channel_effective_support,
    conform_vector,
    synthetic_power_curve,
)
from erre_sandbox.evidence.memory_recomp_conformance.coupled_walk import (
    post_idle_walk_occupancies,
)
from erre_sandbox.evidence.memory_recomp_conformance.verdict_report import (
    RecompVerdict,
    SeedResult,
    evaluate_verdict,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

_Z: Final[int] = len(ZONES)
_ZONE_INDEX: Final = {z: i for i, z in enumerate(ZONES)}
_NEIGHBORS_IDX: Final[tuple[tuple[int, ...], ...]] = tuple(
    tuple(_ZONE_INDEX[n] for n in ADJACENCY[z]) for z in ZONES
)
_CENTERS_ARRAY: Final[np.ndarray] = np.array(
    [NORMALIZED_ZONE_CENTERS[z] for z in ZONES], dtype=np.float64
)
_ADJ_MASK: Final[np.ndarray] = np.zeros((_Z, _Z), dtype=bool)
for _i, _z in enumerate(ZONES):
    for _n in _NEIGHBORS_IDX[_i]:
        _ADJ_MASK[_i, _n] = True

# Config batch for the post-idle walk: [marginal, z=0, ..., z=Z-1].
_CONFIG_TARGETS: Final[np.ndarray] = np.concatenate(
    [np.array([-1], dtype=np.int64), np.arange(_Z, dtype=np.int64)]
)


def build_seed_result(
    seed: int,
    *,
    m: int = _c.M_FRAGMENTS,
    n_replay: int = _c.N_REPLAY,
    l_seed: int = _c.L_SEED,
    n_argmax_resamples: int = _c.N_RESAMPLES,
) -> SeedResult:
    """One blind apparatus instantiation: formation → C → target_zone → D → conform.

    The overridable sizes default to the frozen constants; a test may pass small
    values for a fast pipeline check (the recorded verdict always uses the frozen
    defaults).
    """
    # (1) shared blind start + (2) formation walk (ES-2 Pólya-urn, byte-inherited).
    # RNG families differ by design (DA-MEMSEAM-IMPL-7 note): the formation walk uses
    # the ES-2-inherited stdlib random.Random with a string seed; the post-idle walk C
    # replay and D use independent numpy streams (_c.stream_rng([_SEED_BASE, seed,
    # stream])). Independence is guaranteed by the distinct base + stream ids, not by
    # the RNG family.
    start = random.Random(f"memseam-start-{seed}").randrange(_Z)  # noqa: S311
    formation_rng = random.Random(f"memseam-formation-{seed}")  # noqa: S311
    trajectory = preferential_return_walk(start, m, _NEIGHBORS_IDX, formation_rng)

    # (2b) idle recomposition batch → channel C (STREAM_C_IDLE).
    coords = _CENTERS_ARRAY[np.asarray(trajectory, dtype=np.int64)]
    embeddings = synthetic_embeddings(m)
    semantic = semantic_matrix(embeddings)
    weights = kernel_weights(proximity_matrix(coords), semantic)
    seeds_c, valid_c = replay_walks(
        weights, n_replay, l_seed, _c.stream_rng(seed, _c.STREAM_C_IDLE)
    )
    dist_c = transition_distribution(seeds_c, valid_c, m)
    _from_content, to_content = dominant_transition_cell(dist_c, m)

    # (3) target_zone = formation zone of C's to_content.
    target_zone = zone_of_formation(trajectory, to_content)

    # channel diagnostics (well-posedness + non-collapse).
    channel_eff = channel_effective_support(dist_c)
    argmax_stab = argmax_stability(
        seeds_c,
        valid_c,
        m,
        _c.stream_rng(seed, _c.STREAM_ARGMAX_BOOT),
        n_argmax_resamples,
    )

    # (4) independent post-idle walk D: marginal + each target-zone config, pooled
    # over R realizations on shared per-realization noise. Independent visit_count
    # init; the shared start is the "post-idle" spatial continuity (§2), the ONLY
    # C→D path is the target_zone bonus (§5).
    uniforms = _c.stream_rng(seed, _c.STREAM_D_POST_IDLE).random(
        (_c.POST_IDLE_REALIZATIONS, m)
    )
    occ = post_idle_walk_occupancies(
        start,
        m,
        _ADJ_MASK,
        uniforms,
        _CONFIG_TARGETS,
        alpha=_c.POLYA_ALPHA,
        bonus=_c.POLYA_ALPHA,
    )
    conform_row = conform_vector(occ[0], occ[1:])
    valid = bool(np.all(np.isfinite(conform_row)))

    return SeedResult(
        seed=seed,
        valid=valid,
        start_zone=start,
        target_zone=target_zone,
        conform_row=tuple(float(x) for x in conform_row),
        argmax_stability=argmax_stab,
        channel_effective_support=channel_eff,
    )


@dataclass(frozen=True)
class VerdictRun:
    """The verdict plus the full blind-generator forensic trail."""

    verdict: RecompVerdict
    seeds: tuple[SeedResult, ...]
    synthetic_power_curve: dict[float, float]


def run_verdict(seed_bank: Sequence[int], *, bootstrap_seed: int = 0) -> VerdictRun:
    """Run the blind generator over ``seed_bank`` and render the frozen verdict."""
    results = tuple(build_seed_result(s) for s in seed_bank)

    curve = synthetic_power_curve(
        _ADJ_MASK,
        steps=_c.M_FRAGMENTS,
        realizations=_c.POST_IDLE_REALIZATIONS,
        n_seed=_c.N_SEED,
        ladder=_c.SYNTH_COUPLING_LADDER,
        n_replicates=_c.SYNTH_N_REPLICATES,
        alpha=_c.POLYA_ALPHA,
        quantile=_c.PERM_NULL_QUANTILE,
        n_resamples=_c.N_RESAMPLES,
        ci_alpha=_c.CI_ALPHA,
        rng=_c.stream_rng(0, _c.STREAM_SYNTH_POWER),
    )
    power_at_full = curve.get(1.0, 0.0)

    verdict = evaluate_verdict(
        results,
        synthetic_power_pass_rate=power_at_full,
        coupling_strength_used=_c.POLYA_ALPHA,
        bootstrap_seed=bootstrap_seed,
    )
    return VerdictRun(verdict=verdict, seeds=results, synthetic_power_curve=curve)


def default_seed_bank() -> tuple[int, ...]:
    """The pre-registered blind seed bank: ``range(N_SEED)`` (= 0..63).

    Fixed before the run; no seed is added or dropped after seeing a result
    (forking-paths guard). A superseding ADR is required to change it.
    """
    return tuple(range(_c.N_SEED))


__all__ = [
    "VerdictRun",
    "build_seed_result",
    "default_seed_bank",
    "run_verdict",
]
