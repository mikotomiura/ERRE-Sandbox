"""Deterministic orchestration that joins the M13-ES4 seams into a verdict.

The single place that wires generation (:data:`scenario.InferenceFn`), embedding
(:data:`scoring.EncoderFn`) and the appropriateness judge (:data:`scoring.JudgeFn`)
through reference construction → scoring → decomposition → controls → verdict.
Every LLM touch is a seam, so this whole pipeline runs under deterministic mocks
in Session 1 and against the real SGLang backend in Session 2 with **no apparatus
change** — only the seams differ.

This module computes nothing tunable; it assembles the frozen-constant gates from
the other modules. The ``scripts/es4_phase{0,1}_run.py`` CLIs are thin wrappers
that pass seams in and serialise the result.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from erre_sandbox.evidence.es4_actuator import constants as _c
from erre_sandbox.evidence.es4_actuator import controls as _controls
from erre_sandbox.evidence.es4_actuator.battery import (
    load_adversarial_labeled,
    load_aut_battery,
    load_common_uses,
    load_rat_battery,
)
from erre_sandbox.evidence.es4_actuator.decomposition import (
    Decomposition,
    ScoredUnit,
    decompose,
)
from erre_sandbox.evidence.es4_actuator.reference import (
    build_reference_requests,
    construct_all_references,
)
from erre_sandbox.evidence.es4_actuator.scenario import (
    build_aut_requests,
    build_rat_requests,
    generate,
)
from erre_sandbox.evidence.es4_actuator.scoring import score_generation
from erre_sandbox.evidence.es4_actuator.verdict_report import (
    BatteryValidity,
    BudgetStatus,
    Es4Verdict,
    ScorerControls,
    evaluate_phase0,
    evaluate_phase1,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from erre_sandbox.evidence.es4_actuator.scenario import (
        Generation,
        InferenceFn,
        Phase,
    )
    from erre_sandbox.evidence.es4_actuator.scoring import (
        EncoderFn,
        JudgeFn,
        RarityReference,
    )


def assemble_references(
    inference_fn: InferenceFn,
    encoder_fn: EncoderFn,
    judge_fn: JudgeFn,
) -> dict[str, RarityReference]:
    """Build every object's frozen ``R_object`` (§2.2b) via the seams."""
    aut = load_aut_battery()
    curated = load_common_uses()
    requests = build_reference_requests(aut)
    gens = generate(requests, inference_fn)
    responses: dict[str, list[str]] = {it.object_id: [] for it in aut.items}
    for g in gens:
        responses[g.request.item_id].append(g.response)
    objects_by_id = {it.object_id: it.object for it in aut.items}
    return construct_all_references(
        curated, responses, objects_by_id, encoder_fn, judge_fn
    )


def score_aut(
    gens: Sequence[Generation],
    references: Mapping[str, RarityReference],
    encoder_fn: EncoderFn,
    judge_fn: JudgeFn,
) -> list[ScoredUnit]:
    """Score every AUT generation whose object has a (non-dropped) reference."""
    aut = load_aut_battery()
    obj_str = {it.object_id: it.object for it in aut.items}
    units: list[ScoredUnit] = []
    for g in gens:
        ref = references.get(g.request.item_id)
        if ref is None:
            continue
        score = score_generation(
            g.response, obj_str[g.request.item_id], ref, encoder_fn, judge_fn
        )
        units.append(
            ScoredUnit(
                persona_id=g.request.persona_id,
                item_id=g.request.item_id,
                condition=g.request.condition,
                seed_idx=g.request.seed_idx,
                score=score,
            )
        )
    return units


def _aut_item_valid(a0_units: Sequence[ScoredUnit]) -> bool:
    if not a0_units:
        return False
    frac_two = float(
        np.mean([u.score.n_valid >= _c.AUT_MIN_IDEAS_BASE for u in a0_units])
    )
    parse_ok = float(
        np.mean([not (u.score.parse_fail or u.score.empty) for u in a0_units])
    )
    return frac_two >= _c.AUT_MIN_TRIAL_FRAC and parse_ok >= _c.PARSE_SUCCESS_MIN


def count_valid_aut(
    units: Sequence[ScoredUnit], references: Mapping[str, RarityReference]
) -> int:
    """Valid-AUT count: object has a reference ∧ passes the base-temp item gate."""
    by_item_a0: dict[str, list[ScoredUnit]] = {}
    for u in units:
        if u.condition == "A0":
            by_item_a0.setdefault(u.item_id, []).append(u)
    return sum(1 for obj in references if _aut_item_valid(by_item_a0.get(obj, [])))


def rat_accuracy_by_item(
    gens: Sequence[Generation], condition: str
) -> dict[str, float]:
    """Per-item exact-match RAT accuracy at ``condition`` (answer token present)."""
    rat = load_rat_battery()
    answers = {it.item_id: it.answer.lower() for it in rat.items}
    hits: dict[str, list[int]] = {it.item_id: [] for it in rat.items}
    for g in gens:
        if g.request.task != "rat" or g.request.condition != condition:
            continue
        ans = answers[g.request.item_id]
        toks = g.response.lower().split()
        hits[g.request.item_id].append(1 if ans in toks else 0)
    return {k: (float(np.mean(v)) if v else 0.0) for k, v in hits.items()}


def count_valid_rat(gens: Sequence[Generation]) -> tuple[int, bool]:
    """Valid-RAT count + contamination flag (§6 / §8.2).

    An item is valid iff base (A0) accuracy ∈ (RAT_ACC_MIN, RAT_ACC_MAX); accuracy
    ≥ RAT_ACC_MAX is excluded as contaminated (no replacement). Contamination flag
    fires when the surviving valid count is below the floor.
    """
    base_acc = rat_accuracy_by_item(gens, "A0")
    valid = sum(1 for acc in base_acc.values() if _c.RAT_ACC_MIN < acc < _c.RAT_ACC_MAX)
    return valid, valid < _c.MIN_VALID_RAT


def build_scorer_controls(
    units: Sequence[ScoredUnit], score_fn: _controls.ScoreFn
) -> ScorerControls:
    """Assemble the scorer non-tautology controls from scored AUT data + the seam."""
    adv = load_adversarial_labeled()
    adversarial_auc = _controls.adversarial_judge_auc(adv, score_fn)

    # (a1) within-condition good-vs-garbage discrimination on the generations.
    scores = [u.score.dq if not u.score.is_garbage else 0.0 for u in units]
    labels = [0 if u.score.is_garbage else 1 for u in units]
    strata = [u.condition for u in units]
    a1 = _controls.stratified_min_auc(scores, labels, strata)

    # (a2) held-out entropy residual over the A0/A2 paired generations.
    paired = [u for u in units if u.condition in {"A0", "A2"}]
    dq = [u.score.dq for u in paired]
    hp = [u.score.h_proxy for u in paired]
    hi = [1 if u.condition == "A2" else 0 for u in paired]
    holdout = [1 if u.seed_idx % 2 == 0 else 0 for u in paired]
    a2 = _controls.held_out_residual(dq, hp, hi, holdout)

    return ScorerControls(
        a1_min_auc=a1,
        a2_residual_survives=a2.survives,
        a2_residual_ci_lower=a2.residual_ci_lower,
        adversarial_auc=adversarial_auc,
    )


def build_battery_validity(
    units: Sequence[ScoredUnit],
    decomp: Decomposition,
    references: Mapping[str, RarityReference],
    rat_gens: Sequence[Generation],
    *,
    persona_collapse: bool = False,
) -> BatteryValidity:
    """Assemble the item-level battery validity gate (§3 / §8.2)."""
    empty_parse_rate = (
        float(np.mean([u.score.empty or u.score.parse_fail for u in units]))
        if units
        else 1.0
    )
    valid_rat, rat_contam = count_valid_rat(rat_gens)
    return BatteryValidity(
        n_valid_aut=count_valid_aut(units, references),
        n_valid_rat=valid_rat,
        empty_parse_rate=empty_parse_rate,
        cross_cond_valid_divergence=decomp.cross_condition_valid_divergence,
        cross_cond_missing_divergence=decomp.cross_condition_missing_divergence,
        persona_collapse=persona_collapse,
        rat_contamination=rat_contam,
    )


def run_phase(
    phase: Phase,
    inference_fn: InferenceFn,
    encoder_fn: EncoderFn,
    judge_fn: JudgeFn,
    score_fn: _controls.ScoreFn,
    *,
    projected_gpu_hours: float = 0.0,
    persona_collapse: bool = False,
    bootstrap_seed: int = 0,
) -> Es4Verdict:
    """Full LLM-free-capable ES-4 pipeline for ``phase`` (seams supply the LLM).

    Pre-flight sampling-hash equivalence is asserted first (hard abort on a code
    defect, §0); then references are built, generations scored, the cluster-paired
    estimand decomposed, the controls + battery assembled, and the phase verdict
    rendered.
    """
    preflight = _controls.preflight_sampling_hash(phase)
    if not preflight.ok:
        raise AssertionError(
            f"pre-flight sampling-hash equivalence failed: "
            f"loco0≡none={preflight.loco_zero_equals_none}, "
            f"M2≡A2={preflight.m2_matches_a2_distribution}"
        )

    references = assemble_references(inference_fn, encoder_fn, judge_fn)
    aut_gens = generate(build_aut_requests(phase), inference_fn)
    rat_gens = generate(build_rat_requests(phase), inference_fn)
    units = score_aut(aut_gens, references, encoder_fn, judge_fn)
    decomp = decompose(units, bootstrap_seed=bootstrap_seed)
    scorer = build_scorer_controls(units, score_fn)
    battery = build_battery_validity(
        units, decomp, references, rat_gens, persona_collapse=persona_collapse
    )

    if phase == "phase0":
        budget = BudgetStatus(
            projected_gpu_hours=projected_gpu_hours,
            cap_gpu_hours=_c.PHASE0_GPU_HOUR_CAP,
        )
        return evaluate_phase0(decomp, scorer, battery, budget)
    return evaluate_phase1(decomp, scorer, battery)


__all__ = [
    "assemble_references",
    "build_battery_validity",
    "build_scorer_controls",
    "count_valid_aut",
    "count_valid_rat",
    "rat_accuracy_by_item",
    "run_phase",
    "score_aut",
]
