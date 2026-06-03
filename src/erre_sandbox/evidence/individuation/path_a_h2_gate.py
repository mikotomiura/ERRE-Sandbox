"""M10-A PR-S4b: H2 value-aware conformance evaluator (supersedes path(a) ④).

The S3.5 BLK-1 finding proved the legacy ④ ``swm_key_shuffle_projection`` — a
count-preserving relabel of the **synthesised** SWM ``(axis, key)`` multiset — can
never reach the frozen PASS threshold (an identical SWM gives ``central ≈ 0.46``),
because a permutation preserves a multiset's spread and so carries no
homogenisation mechanism. The path(a) gate was therefore structurally GO-incapable.

This module is the **superseding null-control** the stage-A H2 conformance ADR froze
(``.steering/20260602-m10a-stage-a-h2-conformance-adr/h2-conformance-adr.md``) on top
of the stage-A spike ``spike_h2_conformance.py`` and the S3.5a record-level
re-synthesis null (``s3.5a-null-control-supersede-adr.md`` H1-(a)). The observed
statistic is the H2 **value-aware** distance and the null is a **raw-unit
(record-level) owner-shuffle re-synthesis** — the homogenisation happens *before*
``synthesize_world_model`` collapses the records into the small (zone + self) key
space, which is exactly the mechanism the legacy key-relabel lacked. We do **not**
retreat to a key-relabel null (BLK-1 unreachability re-prevention).

Frozen decision rule (stage-A ADR §3, ported single-source from the spike's
``_observed`` / ``_null_distribution`` / ``_evaluate`` to prevent drift):

* **statistic** ``d_obs`` = median pairwise ``mean|Δvalue|`` over the ``(axis,key)``
  INTERSECTION of the 3 individuals' synthesised SWMs (NaN if no finite pair);
* **null** = K owner-shuffle re-synthesised distances (count-preserving: pool the
  raw :class:`PromotedEvidenceUnit`, permute the owner labels, rebuild
  ``record.id = belief_record_id(new_owner, other)`` / ``record.agent_id = new_owner``
  / ``bond.other_agent_id = other`` and re-synthesise, then re-measure the distance);
* **separation** = one-sided permutation ``p_high = (#{finite null >= d_obs}+1) /
  (len(finite_null)+1)``; PASS if ``p_high <= H2_ALPHA``;
* **3-way verdict** (mutually exclusive, precedence INVALID > PASS > INCONCLUSIVE):
  INVALID if ``d_obs`` NaN **or** ``finite_null`` empty **or** ``null_central >=
  d_obs`` (shuffle did not collapse the separation = owner-identity-independent
  artifact); PASS if not INVALID ∧ ``p_high <= H2_ALPHA`` ∧ powered; else INCONCLUSIVE;
* **powered** (S3.5a HIGH-1, ``min(D_i)``-dominated): a same-per-owner-count synthetic
  systematic positive control separates (``p_high <= H2_ALPHA``). Gates PASS emission
  only; INVALID is density-independent. The D_target>=20 density gate itself is
  **PR-S4c** — this evaluator emits only the powered *flag*.

Decoupling (PR-S4b plan-review HIGH): this module imports **nothing** from
``path_a_gate`` (it returns its own :class:`H2Verdict` / :class:`H2NullControlResult`
over a ``members`` tuple of ``(individual_id, evidence)``), so the scorer depends on
it one-directionally and the direct-import smoke never cycles. It also imports none
of the frozen §9 judgment path (``c3b_verdict`` / ``centroid_panel`` / ``layer1`` /
``c3b_pipeline``), so the frozen sentinel stays ``exit=0``.

"bit-equivalence" boundary (DA-S4B-3): the deterministic core (``_observed`` /
``_pairwise_value_dist`` / the finite-null + verdict formula / the re-synthesis
mechanism) is literally equivalent to the spike (same input → same output). The
null + powered RNG is seeded from ``derive_seed(base_persona_id, run_idx, salt)``
(production's canonical per-(persona, seed) scheme, mirroring the legacy ④) — **not**
the throwaway spike's shared module RNG — so the random draws are reproducible but do
not coincide with the spike's; literal draw-identity is neither possible nor claimed.

CPU only — no GPU / model / DB. The evaluator is exercised on synthetic
:class:`PromotedEvidenceUnit` fixtures with K=1000 and a fixed seed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from statistics import median
from typing import TYPE_CHECKING, Final, Literal, cast

import numpy as np

from erre_sandbox.cognition.belief_ids import belief_record_id
from erre_sandbox.cognition.world_model import synthesize_world_model
from erre_sandbox.evidence.golden_baseline import derive_seed
from erre_sandbox.schemas import RelationshipBond, SemanticMemoryRecord, Zone

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.contracts.cognition_layers import (
        PromotedEvidenceUnit,
        SubjectiveWorldModel,
    )

# --- frozen stage-A ADR constants (one source, §3 / spike) -------------------
H2_ALPHA: Final[float] = 0.05
"""§3.3 one-sided permutation separation threshold ``p_high <= 0.05`` (frozen)."""
H2_NULL_SHUFFLE_K: Final[int] = 1000
"""§3.2 owner-shuffle permutation count (frozen, inherits ④ K=1000)."""
H2_NULL_SHUFFLE_SALT: Final[str] = "m10a-s4b-h2-owner-shuffle-resynth"
"""``derive_seed`` salt for the owner-shuffle null RNG (frozen)."""
H2_POWERED_SALT: Final[str] = "m10a-s4b-h2-powered-positive-control"
"""``derive_seed`` salt for the powered synthetic positive-control RNG (frozen)."""
H2_NULL_CONTROL_KIND: Final[str] = "h2_owner_shuffle_resynth"
"""§4.1 null-control kind stamped into the sidecar (supersedes
``swm_key_shuffle_projection``): the record-level owner-shuffle re-synthesis null."""
H2_NULL_CONTROL_CONFORMANCE: Final[str] = "conformant"
"""§4.1 conformance marker: the stage-A spike proved this null reaches PASS on
separated substrate (no BLK-1 unreachability), so the gate is no longer structurally
GO-incapable (supersedes ``non_conformant_pending_supersede``)."""

# Powered synthetic positive-control calibration (spike-inherited, frozen). NOT a
# general-purpose generator — it exists only to self-calibrate the powered flag
# (§3.4): a same-per-owner-count systematic-divergence substrate that *should*
# separate, used to tell "underpowered density" apart from "no individuation".
_PC_BIAS: Final[tuple[float, ...]] = (0.6, -0.5, 0.1)
"""Per-owner systematic disposition bias for the powered positive control."""
_PC_NOISE_SD: Final[float] = 0.15
_PC_AFF_CLIP: Final[float] = 0.95
_PC_FAMILIARITY: Final[float] = 0.5
_PC_TICK: Final[int] = 100
_PC_ZONES: Final[tuple[Zone, ...]] = (
    Zone.STUDY,
    Zone.PERIPATOS,
    Zone.CHASHITSU,
    Zone.AGORA,
    Zone.GARDEN,
)
_RESYNTH_TICK: Final[int] = 200
"""``synthesize_world_model`` ``current_tick`` for re-synthesis. Value-irrelevant
(DA-S4B-6): ``current_tick`` only weights recency *salience ordering*; the H2 entry
``value`` (zone-mean affinity / self-mean disposition) and the never-trimmed
≤50-entry cap are tick-independent, so the distance statistic does not depend on it.
Fixed to the spike's value for parity."""

_BeliefKindLit = Literal["trust", "clash", "wary", "curious", "ambivalent"]
_TRUST_AFF: Final[float] = 0.70
_CLASH_AFF: Final[float] = -0.70


class H2Verdict(StrEnum):
    """The H2 null-control's own 3-way outcome (mapped to PathAVerdict by the gate).

    Kept distinct from ``path_a_gate.PathAVerdict`` so this module stays a leaf with
    no import of the scorer (PR-S4b decoupling). The gate maps PASS→GO /
    INVALID→INVALID / INCONCLUSIVE→INCONCLUSIVE.
    """

    PASS = "pass"  # noqa: S105  # enum member value, not a secret
    INVALID = "invalid"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class H2NullControlResult:
    """One seed's H2 owner-shuffle-resynth 3-way outcome + evidence.

    ``powered`` is ``None`` when it was not decision-relevant (INVALID, or
    ``p_high > H2_ALPHA``) and so not computed — it gates PASS emission only.
    ``d_obs`` / ``null_central`` / ``p_high`` are ``None`` only on the substrate
    short-circuits (a member with no captured evidence, or an empty pool).
    """

    outcome: H2Verdict
    reason: str
    d_obs: float | None = None
    null_central: float | None = None
    p_high: float | None = None
    n_finite_null: int | None = None
    powered: bool | None = None
    k: int = H2_NULL_SHUFFLE_K


# --- record/bond reconstruction (single-source via synthesize_world_model) ----


def _units_to_swm(
    owner: str, units: Sequence[PromotedEvidenceUnit]
) -> SubjectiveWorldModel:
    """Rebuild ``(records, bonds)`` from raw units and synthesise the owner's SWM.

    ``record.id = belief_record_id(owner, other)`` / ``record.agent_id = owner`` /
    ``bond.other_agent_id = other`` so :func:`synthesize_world_model`'s
    promoted-dyad matching (``record.agent_id == owner`` ∧
    ``belief_record_id(owner, bond.other) == record.id``) holds after an owner
    re-assignment without orphaning (stage-A ADR §6 / null-control §4.1 invariant).
    Calls the production synthesiser so the H2 substrate can never drift from the
    algorithm that produced the entries.
    """
    records: list[SemanticMemoryRecord] = []
    bonds: list[RelationshipBond] = []
    for unit in units:
        records.append(
            SemanticMemoryRecord(
                id=belief_record_id(owner, unit.other_agent_id),
                agent_id=owner,
                summary=f"belief about {unit.other_agent_id}",
                belief_kind=cast("_BeliefKindLit | None", unit.belief_kind),
                confidence=unit.confidence,
            )
        )
        bonds.append(
            RelationshipBond(
                other_agent_id=unit.other_agent_id,
                affinity=unit.affinity,
                familiarity=unit.familiarity,
                last_interaction_tick=unit.last_interaction_tick,
                last_interaction_zone=unit.last_interaction_zone,
            )
        )
    return synthesize_world_model(
        records, bonds, agent_id=owner, current_tick=_RESYNTH_TICK
    )


def _value_map(swm: SubjectiveWorldModel) -> dict[tuple[str, str], float]:
    return {(e.axis, e.key): e.value for e in swm.entries}


def _pairwise_value_dist(maps: Sequence[dict[tuple[str, str], float]]) -> float:
    """Median pairwise ``mean|Δvalue|`` over the ``(axis,key)`` INTERSECTION.

    Empty-intersection pairs are dropped; NaN when no finite pair (stage-A §3.1).
    """
    ds: list[float] = []
    for a in range(len(maps)):
        for b in range(a + 1, len(maps)):
            shared = set(maps[a]) & set(maps[b])
            if shared:
                ds.append(
                    float(np.mean([abs(maps[a][k] - maps[b][k]) for k in shared]))
                )
    return float(np.median(ds)) if ds else float("nan")


def _distance_for(
    owners: Sequence[str], per_owner: Sequence[Sequence[PromotedEvidenceUnit]]
) -> float:
    """Synthesise each owner's SWM and return the pairwise value distance."""
    maps = [
        _value_map(_units_to_swm(owners[i], per_owner[i])) for i in range(len(owners))
    ]
    return _pairwise_value_dist(maps)


def _null_distribution(
    owners: Sequence[str],
    per_owner: Sequence[Sequence[PromotedEvidenceUnit]],
    rng: np.random.Generator,
) -> list[float]:
    """K owner-shuffle re-synthesised null distances (count-preserving, §3.2)."""
    counts = [len(u) for u in per_owner]
    pool: list[PromotedEvidenceUnit] = [u for units in per_owner for u in units]
    index = np.arange(len(pool))
    out: list[float] = []
    for _ in range(H2_NULL_SHUFFLE_K):
        rng.shuffle(index)
        chunks: list[list[PromotedEvidenceUnit]] = []
        offset = 0
        for count in counts:
            chunk = [pool[int(index[offset + j])] for j in range(count)]
            offset += count
            chunks.append(chunk)
        out.append(_distance_for(owners, chunks))
    return out


# --- powered self-calibration (§3.4, min(D_i)-dominated) ----------------------


def _kind_for(affinity: float) -> _BeliefKindLit:
    if affinity >= _TRUST_AFF:
        return "trust"
    if affinity > 0.0:
        return "curious"
    if affinity <= _CLASH_AFF:
        return "clash"
    return "wary"


def _synth_positive_control(
    counts: Sequence[int], rng: np.random.Generator
) -> list[list[PromotedEvidenceUnit]]:
    """Per-owner systematic-divergence substrate at the given counts (spike-port).

    Distinct ``other_agent_id`` per (owner, dyad), zones drawn uniformly, affinity =
    owner bias + N(0, sd). ``min(D_i)`` dominates because the smallest owner's key
    set gates the pairwise homogenisation.
    """
    from erre_sandbox.contracts.cognition_layers import (  # noqa: PLC0415  # leaf-keep
        PromotedEvidenceUnit,
    )

    per_owner: list[list[PromotedEvidenceUnit]] = []
    for owner_idx, count in enumerate(counts):
        bias = _PC_BIAS[owner_idx % len(_PC_BIAS)]
        units: list[PromotedEvidenceUnit] = []
        for j in range(count):
            zone = _PC_ZONES[int(rng.integers(0, len(_PC_ZONES)))]
            affinity = float(
                np.clip(
                    bias + rng.normal(0.0, _PC_NOISE_SD), -_PC_AFF_CLIP, _PC_AFF_CLIP
                )
            )
            units.append(
                PromotedEvidenceUnit(
                    other_agent_id=f"pc_{owner_idx}_{j}",
                    belief_kind=_kind_for(affinity),
                    confidence=0.8,
                    affinity=affinity,
                    familiarity=_PC_FAMILIARITY,
                    last_interaction_zone=zone,
                    last_interaction_tick=_PC_TICK,
                )
            )
        per_owner.append(units)
    return per_owner


def _powered_for(
    owners: Sequence[str], counts: Sequence[int], rng: np.random.Generator
) -> bool:
    """True iff a same-count synthetic systematic positive control separates.

    Runs the frozen statistic + null on the synthetic substrate and checks
    ``p_high <= H2_ALPHA`` (judged by separation only, no recursive powered gate).
    """
    pc = _synth_positive_control(counts, rng)
    d_obs = _distance_for(owners, pc)
    null = _null_distribution(owners, pc, rng)
    finite_null = [x for x in null if math.isfinite(x)]
    if not (math.isfinite(d_obs) and finite_null):
        return False
    p_high = (sum(1 for x in finite_null if x >= d_obs) + 1) / (len(finite_null) + 1)
    return p_high <= H2_ALPHA


# --- public evaluator --------------------------------------------------------


def h2_owner_shuffle_resynth_3way(
    members: Sequence[tuple[str, tuple[PromotedEvidenceUnit, ...] | None]],
    *,
    base_persona_id: str,
    run_idx: int,
) -> H2NullControlResult:
    """H2 value-aware 3-way null-control for one seed (stage-A frozen rule).

    ``members`` is ``(individual_id, evidence)`` per individual; ``evidence`` is the
    final-tick raw :class:`PromotedEvidenceUnit` tuple (loader
    ``IndividualStateWindow.world_model_evidence``) or ``None`` when no SWM was
    synthesised.

    Two short-circuits with a deliberate distinction (Codex PR-S4b HIGH-1):

    * a member with ``None`` evidence is INCONCLUSIVE — a **non-frozen precondition
      exception**: the SWM was never captured (pre-段B / flag-off), so there is no
      substrate to apply the frozen rule to (mirrors the legacy ④ shortfall);
    * an all-present-but-empty pool (every member ``()`` → all SWMs empty, so the
      statistic is on real-but-degenerate substrate) is **INVALID** per the frozen
      rule (``d_obs`` NaN → INVALID, stage-A §3.3), not a precondition shortfall.

    Returns the 3-way :class:`H2NullControlResult`; the scorer maps PASS→GO /
    INVALID→INVALID / INCONCLUSIVE→INCONCLUSIVE.
    """
    owners = [m[0] for m in members]
    evidences = [m[1] for m in members]
    if any(ev is None for ev in evidences):
        return H2NullControlResult(
            H2Verdict.INCONCLUSIVE,
            "insufficient SWM substrate (a member has no captured evidence units)",
        )
    per_owner: list[list[PromotedEvidenceUnit]] = [list(ev or ()) for ev in evidences]
    if sum(len(u) for u in per_owner) == 0:
        # All members present but empty → d_obs NaN → INVALID (frozen §3.3), not a
        # precondition shortfall (Codex HIGH-1).
        return H2NullControlResult(
            H2Verdict.INVALID,
            "H2 INVALID: empty substrate (no evidence units → d_obs NaN)",
            d_obs=None,
            n_finite_null=0,
        )
    # Density D_i is the distinct-other dyad count (stage-A / S4 pre-flight ADR), NOT
    # the raw unit count — duplicate other_agent_id must not inflate power (Codex
    # HIGH-2). The observed/null statistic runs on the raw units (synthesise dedups by
    # belief_record_id); only the powered self-calibration is keyed on distinct-other.
    distinct_counts = [len({u.other_agent_id for u in units}) for units in per_owner]

    null_rng = np.random.Generator(
        np.random.PCG64(
            derive_seed(base_persona_id, run_idx, salt=H2_NULL_SHUFFLE_SALT)
        )
    )
    d_obs = _distance_for(owners, per_owner)
    null = _null_distribution(owners, per_owner, null_rng)
    finite_null = [x for x in null if math.isfinite(x)]
    n_fin = len(finite_null)
    null_central = float(median(finite_null)) if n_fin else None
    if math.isfinite(d_obs) and n_fin:
        p_high: float | None = (sum(1 for x in finite_null if x >= d_obs) + 1) / (
            n_fin + 1
        )
    else:
        p_high = None

    invalid = (
        (not math.isfinite(d_obs))
        or (n_fin == 0)
        or (null_central is not None and null_central >= d_obs)
    )
    d_obs_out = d_obs if math.isfinite(d_obs) else None

    if invalid:
        return H2NullControlResult(
            H2Verdict.INVALID,
            _invalid_reason(d_obs_out, n_fin, null_central),
            d_obs=d_obs_out,
            null_central=null_central,
            p_high=p_high,
            n_finite_null=n_fin,
            powered=None,
        )
    if p_high is not None and p_high <= H2_ALPHA:
        powered_rng = np.random.Generator(
            np.random.PCG64(derive_seed(base_persona_id, run_idx, salt=H2_POWERED_SALT))
        )
        powered = _powered_for(owners, distinct_counts, powered_rng)
        outcome = H2Verdict.PASS if powered else H2Verdict.INCONCLUSIVE
        reason = (
            f"H2 PASS: p_high {p_high:.4f} <= {H2_ALPHA} and powered"
            f" (distinct-other counts {tuple(distinct_counts)} reach separation)"
            if powered
            else (
                f"underpowered: p_high {p_high:.4f} <= {H2_ALPHA} but distinct-other"
                f" counts {tuple(distinct_counts)} below the homogenisation threshold;"
                " recapture at higher density"
            )
        )
        return H2NullControlResult(
            outcome,
            reason,
            d_obs=d_obs_out,
            null_central=null_central,
            p_high=p_high,
            n_finite_null=n_fin,
            powered=powered,
        )
    return H2NullControlResult(
        H2Verdict.INCONCLUSIVE,
        f"H2 inconclusive: p_high {p_high:.4f} > {H2_ALPHA} (no separation)"
        if p_high is not None
        else "H2 inconclusive: p_high undefined",
        d_obs=d_obs_out,
        null_central=null_central,
        p_high=p_high,
        n_finite_null=n_fin,
        powered=None,
    )


def _invalid_reason(d_obs: float | None, n_fin: int, null_central: float | None) -> str:
    if d_obs is None:
        return (
            "H2 INVALID: d_obs is NaN (empty (axis,key) intersection / D<2 / no self)"
        )
    if n_fin == 0:
        return "H2 INVALID: no finite owner-shuffle null distances"
    return (
        f"H2 INVALID: null_central {null_central:.4f} >= d_obs {d_obs:.4f}"
        " (owner-shuffle did not collapse the separation = identity-independent"
        " fixture / metric artifact)"
    )


__all__ = [
    "H2_ALPHA",
    "H2_NULL_CONTROL_CONFORMANCE",
    "H2_NULL_CONTROL_KIND",
    "H2_NULL_SHUFFLE_K",
    "H2_NULL_SHUFFLE_SALT",
    "H2_POWERED_SALT",
    "H2NullControlResult",
    "H2Verdict",
    "h2_owner_shuffle_resynth_3way",
]
