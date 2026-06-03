"""M10-A S3.5 path(a) gate scorer coverage + BLK-1 structural finding regression.

No GPU / model / DuckDB: every input is a hand-built :class:`MetricResult` /
:class:`IndividualSubstrate`, so the five-state precedence (INVALID > NO_GO >
REJECT > INCONCLUSIVE > GO), each criterion (①②③④), the seed matrix / identity
gates and the seeded null-control are pinned against the frozen ADR thresholds —
the "GO 基準後出し封じ" guard made executable.

It also **pins the BLK-1 structural finding** (finding ADR
``s3.5-null-control-finding-adr.md``): the ``swm_key_shuffle_projection`` null can
never reach the frozen §3.A④ PASS threshold (``central >= 0.90``), so the gate can
never emit GO — the regression guard so a future supersede must consciously change
the null-control rather than silently "fix" the unreachability.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest

from erre_sandbox.contracts.cognition_layers import PromotedEvidenceUnit
from erre_sandbox.evidence.golden_baseline import derive_seed
from erre_sandbox.evidence.individuation.models import MetricResult, Provenance
from erre_sandbox.evidence.individuation.path_a_gate import (
    _LEGACY_NULL_CONTROL_KIND,
    NULL_CONTROL_CONFORMANCE,
    NULL_CONTROL_KIND,
    NULL_SHUFFLE_SALT,
    CriterionResult,
    IndividualSubstrate,
    PathAExperiment,
    PathARunInput,
    PathAVerdict,
    score_path_a_gate,
    swm_key_shuffle_projection_3way,
)
from erre_sandbox.evidence.individuation.path_a_h2_gate import H2Verdict
from erre_sandbox.evidence.individuation.policy import (
    DYAD_SEP,
    AggregationLevel,
    MetricChannel,
    MetricStatus,
)
from erre_sandbox.schemas import Zone

_ZONES = (Zone.STUDY, Zone.PERIPATOS, Zone.CHASHITSU, Zone.AGORA, Zone.GARDEN)
_POS_BIAS = (0.6, -0.5, 0.1)


def _pos_evidence(
    owner_idx: int, d: int, seed: int
) -> tuple[PromotedEvidenceUnit, ...]:
    """Systematic-divergence evidence for one owner (drives H2 ④ PASS at high D)."""
    rng = np.random.default_rng(seed)
    bias = _POS_BIAS[owner_idx]
    units: list[PromotedEvidenceUnit] = []
    for j in range(d):
        zone = _ZONES[int(rng.integers(0, len(_ZONES)))]
        aff = float(np.clip(bias + rng.normal(0.0, 0.15), -0.95, 0.95))
        kind = (
            "trust"
            if aff >= 0.70
            else "curious"
            if aff > 0.0
            else "clash"
            if aff <= -0.70
            else "wary"
        )
        units.append(
            PromotedEvidenceUnit(
                other_agent_id=f"o_{owner_idx}_{j}",
                belief_kind=kind,
                confidence=0.8,
                affinity=aff,
                familiarity=0.5,
                last_interaction_zone=zone,
                last_interaction_tick=100,
            )
        )
    return tuple(units)


def _identical_evidence(d: int, seed: int) -> tuple[PromotedEvidenceUnit, ...]:
    """One shared evidence set every owner reuses (no separation → H2 ④ INVALID)."""
    return _pos_evidence(0, d, seed)


def _pos_evidence_map(d: int = 20) -> dict[str, tuple[PromotedEvidenceUnit, ...]]:
    return {_IDS[i]: _pos_evidence(i, d, 1000 + i) for i in range(3)}


def _identical_evidence_map(d: int = 12) -> dict[str, tuple[PromotedEvidenceUnit, ...]]:
    shared = _identical_evidence(d, 7)
    return dict.fromkeys(_IDS, shared)


_NOW = datetime(2026, 6, 1, tzinfo=UTC)
_IDS = ("a_rikyu_001", "a_rikyu_002", "a_rikyu_003")
_BASE = "rikyu"
_DYAD_BASE = f"{_BASE}{DYAD_SEP}{_BASE}"


def _prov(sfh: str) -> Provenance:
    return Provenance(
        metric_schema_version="m10-0.1",
        source_table="metrics.individual_state_trace",
        source_run_id="run0",
        source_epoch_phase="evaluation",
        source_individual_layer_enabled=True,
        source_filter_hash=sfh,
        embedding_model_id=None,
    )


def _bv(individual: str, *, valid: bool, run_id: str = "run0") -> MetricResult:
    """A per-individual ``belief_variance`` row (VALID or degenerate)."""
    return MetricResult(
        run_id=run_id,
        individual_id=individual,
        base_persona_id=_BASE,
        aggregation_level=AggregationLevel.PER_INDIVIDUAL,
        tick=-1,
        metric_name="belief_variance",
        channel=MetricChannel.BELIEF_SUBSTRATE,
        status=MetricStatus.VALID if valid else MetricStatus.DEGENERATE,
        value=0.5 if valid else None,
        reason=None if valid else "single belief class (no variance)",
        provenance=_prov(individual),
        computed_at=_NOW,
    )


def _jac(a: str, b: str, value: float | None, *, run_id: str = "run0") -> MetricResult:
    """A per-dyad ``world_model_overlap_jaccard`` row (VALID or degenerate)."""
    valid = value is not None
    return MetricResult(
        run_id=run_id,
        individual_id=f"{a}{DYAD_SEP}{b}",
        base_persona_id=_DYAD_BASE,
        aggregation_level=AggregationLevel.PER_DYAD,
        tick=-1,
        metric_name="world_model_overlap_jaccard",
        channel=MetricChannel.WORLD_MODEL,
        status=MetricStatus.VALID if valid else MetricStatus.DEGENERATE,
        value=value,
        reason=None if valid else "empty world-model union",
        provenance=_prov(f"{a}{DYAD_SEP}{b}"),
        computed_at=_NOW,
    )


def _all_bv(*, run_id: str = "run0", valid: bool = True) -> tuple[MetricResult, ...]:
    return tuple(_bv(i, valid=valid, run_id=run_id) for i in _IDS)


def _all_jac(
    values: tuple[float | None, float | None, float | None],
    *,
    run_id: str = "run0",
) -> tuple[MetricResult, ...]:
    pairs = ((_IDS[0], _IDS[1]), (_IDS[0], _IDS[2]), (_IDS[1], _IDS[2]))
    return tuple(
        _jac(a, b, v, run_id=run_id) for (a, b), v in zip(pairs, values, strict=True)
    )


# SWM key fixtures (axis,key) tuples.
def _keys(*specs: tuple[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(specs)


_IDENTICAL_SWM = {
    i: _keys(("self", "rd"), ("env", "agora"), ("env", "study")) for i in _IDS
}
_DIFFERENTIATED_SWM = {
    _IDS[0]: _keys(("self", "rd"), ("env", "agora"), ("env", "study")),
    _IDS[1]: _keys(("self", "rd"), ("env", "peripatos"), ("env", "agora")),
    _IDS[2]: _keys(("self", "rd"), ("env", "chashitsu"), ("env", "garden")),
}


def _subs(
    swm: dict[str, tuple[tuple[str, str], ...]] | None,
    beliefs: dict[str, tuple[str, ...] | None] | None = None,
    evidence: dict[str, tuple[PromotedEvidenceUnit, ...]] | None = None,
) -> tuple[IndividualSubstrate, ...]:
    default_beliefs = dict.fromkeys(_IDS, ("trust", "wary"))
    beliefs = beliefs or default_beliefs
    return tuple(
        IndividualSubstrate(
            individual_id=i,
            belief_classes=beliefs.get(i),
            world_model_keys=(swm.get(i) if swm is not None else None),
            world_model_evidence=(evidence.get(i) if evidence is not None else None),
        )
        for i in _IDS
    )


def _run(
    *,
    run_idx: int,
    run_id: str = "run0",
    swm: dict[str, tuple[tuple[str, str], ...]] | None = None,
    beliefs: dict[str, tuple[str, ...] | None] | None = None,
    evidence: dict[str, tuple[PromotedEvidenceUnit, ...]] | None = None,
    bv_valid: bool = True,
    jaccard: tuple[float | None, float | None, float | None] = (0.2, 0.2, 0.5),
) -> PathARunInput:
    return PathARunInput(
        run_idx=run_idx,
        run_id=run_id,
        base_persona_id=_BASE,
        individuals=_subs(swm, beliefs, evidence),
        belief_variance_rows=_all_bv(run_id=run_id, valid=bv_valid),
        jaccard_rows=_all_jac(jaccard, run_id=run_id),
    )


def _experiment(*runs: PathARunInput) -> PathAExperiment:
    return PathAExperiment(run_id="run0", runs=tuple(runs))


# --- BLK-1 structural finding regression pins --------------------------------


def test_null_control_pass_threshold_unreachable_identical_swm() -> None:
    """BLK-1: even an identical SWM cannot reach central >= 0.90 (never PASS)."""
    result = swm_key_shuffle_projection_3way(
        _subs(_IDENTICAL_SWM), base_persona_id=_BASE, run_idx=0
    )
    assert result.central is not None
    assert result.central < 0.90
    assert result.outcome is not PathAVerdict.GO


def test_null_control_differentiated_is_invalid() -> None:
    """BLK-1: a separated (differentiated) SWM is flagged INVALID by the projection."""
    result = swm_key_shuffle_projection_3way(
        _subs(_DIFFERENTIATED_SWM), base_persona_id=_BASE, run_idx=0
    )
    assert result.outcome is PathAVerdict.INVALID
    assert result.p95 is not None
    assert result.p95 <= 0.60


def test_gate_emits_go_on_positive_substrate() -> None:
    """PR-S4b supersede headline: the gate CAN emit GO (no longer GO-incapable).

    ①✓ valid belief_variance + ② distinct distributions + ③ separated + the H2 ④
    PASS on systematic-divergence evidence at high density (D=20) → GO across all 3
    seeds (⑤ seed AND). The sidecar stamps the H2 markers (h2_owner_shuffle_resynth /
    conformant), superseding the legacy BLK-1 non-conformant projection.
    """
    distinct = {
        _IDS[0]: ("trust", "wary"),
        _IDS[1]: ("trust", "trust", "wary"),
        _IDS[2]: ("trust", "wary", "wary"),
    }
    ev = _pos_evidence_map(d=20)
    exp = _experiment(
        _run(run_idx=0, beliefs=distinct, evidence=ev, jaccard=(0.2, 0.2, 0.5)),
        _run(run_idx=1, beliefs=distinct, evidence=ev, jaccard=(0.2, 0.2, 0.5)),
        _run(run_idx=2, beliefs=distinct, evidence=ev, jaccard=(0.2, 0.2, 0.5)),
    )
    report = score_path_a_gate(exp)
    assert report.verdict is PathAVerdict.GO
    assert report.null_control_kind == NULL_CONTROL_KIND == "h2_owner_shuffle_resynth"
    assert report.null_control_conformance == NULL_CONTROL_CONFORMANCE == "conformant"
    seed0 = next(s for s in report.seeds if s.run_idx == 0)
    assert seed0.null_control is not None
    assert seed0.null_control.outcome is H2Verdict.PASS
    assert seed0.null_control.powered is True


# --- criterion isolation (④ pinned to INCONCLUSIVE via identical SWM) ---------


def test_belief_variance_no_go() -> None:
    """① any individual belief_variance not VALID → seed NO_GO."""
    exp = _experiment(
        _run(run_idx=0, swm=_IDENTICAL_SWM, bv_valid=False),
        _run(run_idx=1, swm=_IDENTICAL_SWM),
        _run(run_idx=2, swm=_IDENTICAL_SWM),
    )
    report = score_path_a_gate(exp)
    assert report.verdict is PathAVerdict.NO_GO


def test_no_go_not_overridden_by_null_invalid() -> None:
    """CX-MED-1: ① NO_GO skips the H2 ④ (INCONCLUSIVE), never escalating above NO_GO.

    ④ is only evaluated after ① passes; on NO_GO it is skipped (H2 INCONCLUSIVE), so
    a ④ INVALID can never escalate above NO_GO and mislabel a substrate-absent seed.
    """
    seed = _run(run_idx=0, evidence=_identical_evidence_map(), bv_valid=False)
    exp = _experiment(seed, _run(run_idx=1), _run(run_idx=2))
    report = score_path_a_gate(exp)
    assert report.verdict is PathAVerdict.NO_GO
    seed0 = next(s for s in report.seeds if s.run_idx == 0)
    assert seed0.verdict is PathAVerdict.NO_GO
    assert seed0.null_control is not None
    assert seed0.null_control.outcome is H2Verdict.INCONCLUSIVE


def test_belief_distribution_reject_when_all_identical() -> None:
    """② all 3 belief-class distributions identical → REJECT (④ pinned inconclusive)."""
    identical_beliefs = dict.fromkeys(_IDS, ("trust", "wary"))
    exp = _experiment(
        _run(run_idx=0, swm=_IDENTICAL_SWM, beliefs=identical_beliefs),
        _run(run_idx=1, swm=_IDENTICAL_SWM, beliefs=identical_beliefs),
        _run(run_idx=2, swm=_IDENTICAL_SWM, beliefs=identical_beliefs),
    )
    report = score_path_a_gate(exp)
    assert report.verdict is PathAVerdict.REJECT
    seed0 = next(s for s in report.seeds if s.run_idx == 0)
    assert seed0.belief_distribution is not None
    assert seed0.belief_distribution.outcome is PathAVerdict.REJECT


def test_belief_distribution_pass_when_distinct() -> None:
    """② >= 1 distinct distribution passes (seed then driven by ④ inconclusive)."""
    distinct = {
        _IDS[0]: ("trust", "wary"),
        _IDS[1]: ("trust", "trust", "wary"),
        _IDS[2]: ("trust", "wary", "wary"),
    }
    report = score_path_a_gate(
        _experiment(
            _run(run_idx=0, swm=_IDENTICAL_SWM, beliefs=distinct),
            _run(run_idx=1, swm=_IDENTICAL_SWM, beliefs=distinct),
            _run(run_idx=2, swm=_IDENTICAL_SWM, beliefs=distinct),
        )
    )
    seed0 = next(s for s in report.seeds if s.run_idx == 0)
    assert seed0.belief_distribution is not None
    assert seed0.belief_distribution.outcome is PathAVerdict.GO
    # identical SWM → ④ inconclusive → seed inconclusive (③ sep ok, ② distinct).
    assert seed0.verdict is PathAVerdict.INCONCLUSIVE


def test_jaccard_reject_when_median_above_floor() -> None:
    """③ median pairwise jaccard > 0.60 → REJECT (④ pinned inconclusive)."""
    distinct = {
        _IDS[0]: ("trust", "wary"),
        _IDS[1]: ("trust", "trust", "wary"),
        _IDS[2]: ("trust", "wary", "wary"),
    }
    report = score_path_a_gate(
        _experiment(
            _run(
                run_idx=0, swm=_IDENTICAL_SWM, beliefs=distinct, jaccard=(0.8, 0.9, 0.7)
            ),
            _run(
                run_idx=1, swm=_IDENTICAL_SWM, beliefs=distinct, jaccard=(0.8, 0.9, 0.7)
            ),
            _run(
                run_idx=2, swm=_IDENTICAL_SWM, beliefs=distinct, jaccard=(0.8, 0.9, 0.7)
            ),
        )
    )
    assert report.verdict is PathAVerdict.REJECT


def test_jaccard_inconclusive_when_short_valid_rows() -> None:
    """③ fewer than 3 VALID dyad rows → INCONCLUSIVE (sample shortfall, DA-S3.5-4)."""
    distinct = {
        _IDS[0]: ("trust", "wary"),
        _IDS[1]: ("trust", "trust", "wary"),
        _IDS[2]: ("trust", "wary", "wary"),
    }
    # one degenerate dyad (None) → only 2 VALID jaccard rows.
    report = score_path_a_gate(
        _experiment(
            _run(
                run_idx=0,
                swm=_IDENTICAL_SWM,
                beliefs=distinct,
                jaccard=(0.2, None, 0.5),
            ),
            _run(
                run_idx=1,
                swm=_IDENTICAL_SWM,
                beliefs=distinct,
                jaccard=(0.2, None, 0.5),
            ),
            _run(
                run_idx=2,
                swm=_IDENTICAL_SWM,
                beliefs=distinct,
                jaccard=(0.2, None, 0.5),
            ),
        )
    )
    assert report.verdict is PathAVerdict.INCONCLUSIVE


def test_null_control_inconclusive_when_no_swm_substrate() -> None:
    """④ a member with no captured SWM → INCONCLUSIVE (insufficient substrate)."""
    result = swm_key_shuffle_projection_3way(
        _subs(None), base_persona_id=_BASE, run_idx=0
    )
    assert result.outcome is PathAVerdict.INCONCLUSIVE


# --- seed matrix + identity gates (→ INVALID) --------------------------------


def test_matrix_violation_missing_seed() -> None:
    report = score_path_a_gate(_experiment(_run(run_idx=0), _run(run_idx=1)))
    assert report.verdict is PathAVerdict.INVALID
    assert "missing" in report.reason or "!= required" in report.reason


def test_matrix_violation_duplicate_seed() -> None:
    report = score_path_a_gate(
        _experiment(_run(run_idx=0), _run(run_idx=0), _run(run_idx=2))
    )
    assert report.verdict is PathAVerdict.INVALID
    assert "duplicate" in report.reason


def test_matrix_violation_illegal_seed() -> None:
    report = score_path_a_gate(
        _experiment(_run(run_idx=0), _run(run_idx=1), _run(run_idx=3))
    )
    assert report.verdict is PathAVerdict.INVALID


def test_identity_violation_wrong_individual_count() -> None:
    bad = PathARunInput(
        run_idx=0,
        run_id="run0",
        base_persona_id=_BASE,
        individuals=_subs(_IDENTICAL_SWM)[:2],  # only 2 individuals
        belief_variance_rows=_all_bv(),
        jaccard_rows=_all_jac((0.2, 0.2, 0.5)),
    )
    report = score_path_a_gate(_experiment(bad, _run(run_idx=1), _run(run_idx=2)))
    assert report.verdict is PathAVerdict.INVALID
    seed0 = next(s for s in report.seeds if s.run_idx == 0)
    assert seed0.invalid_reason is not None


def test_identity_violation_run_id_mismatch() -> None:
    bad = PathARunInput(
        run_idx=0,
        run_id="run0",
        base_persona_id=_BASE,
        individuals=_subs(_IDENTICAL_SWM),
        belief_variance_rows=_all_bv(run_id="OTHER"),  # rows from a different run
        jaccard_rows=_all_jac((0.2, 0.2, 0.5)),
    )
    report = score_path_a_gate(_experiment(bad, _run(run_idx=1), _run(run_idx=2)))
    assert report.verdict is PathAVerdict.INVALID


# --- ⑤ across-seed precedence + reproducibility ------------------------------


def test_experiment_invalid_dominates_across_seeds() -> None:
    """⑤ one INVALID seed (identical evidence → H2 ④ INVALID) makes it INVALID."""
    report = score_path_a_gate(
        _experiment(
            _run(run_idx=0),  # evidence None → ④ INCONCLUSIVE
            _run(run_idx=1),
            _run(run_idx=2, evidence=_identical_evidence_map()),  # ④ INVALID
        )
    )
    assert report.verdict is PathAVerdict.INVALID
    seed2 = next(s for s in report.seeds if s.run_idx == 2)
    assert seed2.null_control is not None
    assert seed2.null_control.outcome is H2Verdict.INVALID


def test_null_control_seed_reproducible() -> None:
    """The seeded shuffle is bit-reproducible (same seed → identical central/p95)."""
    subs = _subs(_DIFFERENTIATED_SWM)
    a = swm_key_shuffle_projection_3way(subs, base_persona_id=_BASE, run_idx=1)
    b = swm_key_shuffle_projection_3way(subs, base_persona_id=_BASE, run_idx=1)
    # Same (persona, run_idx, salt) → bit-identical summary statistics.
    assert a.central == b.central
    assert a.p95 == b.p95
    # A different run_idx draws an independent stream (the coarse central/p95 may
    # coincide for a tight null, so only the same-seed identity is pinned).
    c = swm_key_shuffle_projection_3way(subs, base_persona_id=_BASE, run_idx=2)
    assert c.central is not None
    assert c.p95 is not None


def test_null_control_records_raw_and_unique_counts() -> None:
    """MF-2: pooled raw vs unique key counts are surfaced for transparency."""
    result = swm_key_shuffle_projection_3way(
        _subs(_DIFFERENTIATED_SWM), base_persona_id=_BASE, run_idx=0
    )
    # differentiated: self/rd ×3 + agora ×2 + study/peripatos/chashitsu/garden ×1.
    assert result.swm_raw_key_count == 9
    assert result.swm_unique_key_count == 6


def test_null_shuffle_seed_uses_frozen_salt() -> None:
    """The shuffle seed is derived from the frozen reactivate-ADR salt."""
    assert NULL_SHUFFLE_SALT == "c3b-reactivate-null-shuffle"
    # sanity: derive_seed is deterministic for the salt.
    assert derive_seed(_BASE, 0, salt=NULL_SHUFFLE_SALT) == derive_seed(
        _BASE, 0, salt=NULL_SHUFFLE_SALT
    )


def test_null_control_kind_is_h2_after_supersede() -> None:
    """PR-S4b: the live null-control kind is the H2 resynth; legacy kept as history."""
    assert NULL_CONTROL_KIND == "h2_owner_shuffle_resynth"
    assert NULL_CONTROL_CONFORMANCE == "conformant"
    # legacy BLK-1 marker retained for the history function (no longer live).
    assert _LEGACY_NULL_CONTROL_KIND == "swm_key_shuffle_projection"


@pytest.mark.parametrize(
    ("a", "b", "expected_more_severe"),
    [
        (PathAVerdict.INVALID, PathAVerdict.NO_GO, PathAVerdict.INVALID),
        (PathAVerdict.NO_GO, PathAVerdict.REJECT, PathAVerdict.NO_GO),
        (PathAVerdict.REJECT, PathAVerdict.INCONCLUSIVE, PathAVerdict.REJECT),
        (PathAVerdict.INCONCLUSIVE, PathAVerdict.GO, PathAVerdict.INCONCLUSIVE),
    ],
)
def test_precedence_ordering(
    a: PathAVerdict, b: PathAVerdict, expected_more_severe: PathAVerdict
) -> None:
    """DA-S3.5-2 precedence: INVALID > NO_GO > REJECT > INCONCLUSIVE > GO."""
    from erre_sandbox.evidence.individuation.path_a_gate import _most_severe

    assert _most_severe([a, b]) is expected_more_severe
    assert _most_severe([b, a]) is expected_more_severe


def test_criterion_result_pass_is_go_sentinel() -> None:
    """A passing criterion uses GO as its sentinel (rank 0)."""
    cr = CriterionResult(PathAVerdict.GO, "ok")
    assert cr.outcome is PathAVerdict.GO
