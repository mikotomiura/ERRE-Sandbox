"""M10-A S4 GPU smoke wiring: the path(a) S4 forward-decision orchestration (CPU only).

Composition root for the S4 decision plumbing the pre-flight ADR
(``.steering/20260603-m10a-s4-preflight-design-adr/``) pre-registered: it drives one
corner run's N=3 seeds through ``assemble`` → H2 gate → density audit → §6.1 decision
table and returns the ``GO`` / ``Y'_pivot`` / ``Y'_direct`` / ``ESCALATE`` action plus
its evidence (:class:`S4Decision`).

It composes three leaves one-directionally — :mod:`path_a_pipeline` (assemble, with the
论点 d focal-base filter), :mod:`path_a_gate` (``score_path_a_gate`` 5-state verdict),
:mod:`path_a_density_audit` (per-owner density + the frozen escalation feasibility) —
and imports **none** of the frozen §9 judgment path (``c3b_verdict`` /
``centroid_panel`` / ``layer1`` / ``c3b_pipeline``), so the frozen sentinel stays
``exit=0``. It does
**not** run the GPU smoke, inference, the ~4.2h corner run, or S5 (all still BLOCK): it
is the CPU-verifiable evaluator the smoke drives, exercised on synthetic published
DuckDB views.

Two aggregation boundaries the ADR §6 froze, made executable here:

* **H2 verdict (5→3)**: ``score_path_a_gate`` already does the N=3 seed-AND +
  most-severe precedence and returns a 5-state :class:`~path_a_gate.PathAVerdict`; the
  decision table is keyed on the 3-way :class:`~path_a_h2_gate.H2Verdict`, so
  :func:`_map_gate_to_h2` collapses ``GO→PASS`` / ``INVALID→INVALID`` /
  ``{NO_GO, REJECT, INCONCLUSIVE}→INCONCLUSIVE`` (NO_GO/REJECT = "individuation signal
  absent, measurer sound" = INCONCLUSIVE, not the INVALID "measurer non-conformant").
  ``GO`` ⟹ every seed ``GO`` = ADR §6.1 "PASS は N=3 seed AND" (DA-S4GS-4).
* **density / escalation (per-seed, never cross-seed)**: ``experiment_d_pass =
  all(seed.d_pass)`` is a pure boolean AND (≡ ``min(seed.min_d) >= D_target``). The
  escalation feasibility is the **frozen single-run min-of-3** statistic
  (:func:`path_a_density_audit.escalation_feasible`, Šidák-corrected for the min over 3
  owners), so it is evaluated **per seed** on each ``seed.min_d`` (a genuine 3-owner
  min) and the experiment escalates iff **any** seed is feasible — which, as feasibility
  is monotone in ``d_min``, is the optimistic (max-``min_d``) seed = ADR §6.5 "Y' direct
  only when even the optimistic side cannot reach". The cross-seed ``min(seed.min_d)``
  (a min-of-9 draw, heavier lower tail) is **never** fed into the 3-owner-corrected
  function — doing so would underestimate ``rho_upper`` and break the family-wise
  false-fast-fail guarantee (early-termination guard, DA-S4GS-5). It is kept only as a
  reporting diagnostic (``experiment_min_d``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from erre_sandbox.evidence.individuation.path_a_density_audit import (
    DensityAudit,
    DensityDecision,
    EscalationFeasibility,
    audit_density_from_view,
    decision,
    escalation_feasible,
)
from erre_sandbox.evidence.individuation.path_a_gate import (
    PathAExperiment,
    PathAScoreReport,
    PathAVerdict,
    score_path_a_gate,
)
from erre_sandbox.evidence.individuation.path_a_h2_gate import H2Verdict
from erre_sandbox.evidence.individuation.path_a_pipeline import (
    assemble_path_a_run_from_view,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from erre_sandbox.evidence.individuation.path_a_gate import PathARunInput
    from erre_sandbox.evidence.individuation.runner import IndividuationContext


class S4RunnerError(RuntimeError):
    """Raised when the S4 orchestration's inputs are inconsistent.

    The load-bearing case is the measured-3 cross-check: the gate assembly resolves
    the measured trio from ``MetricResult.base_persona_id`` while the density audit
    resolves it from the loader's raw_dialog ``base_groups`` (two independent sources,
    DA-S4GS-3). When they disagree the population roster is malformed, so we fail loud
    rather than silently audit one trio and gate another.
    """


# H2 (5→3) verdict map (DA-S4GS-4). ``score_path_a_gate`` aggregates the N=3 seeds
# (seed-AND + most-severe precedence) into a 5-state PathAVerdict; the decision table
# is keyed on the 3-way H2Verdict, so NO_GO/REJECT (individuation signal absent,
# measurer sound) collapse to INCONCLUSIVE — distinct from INVALID (measurer
# non-conformant). GO ⟹ every seed GO = "PASS は N=3 seed AND".
_GATE_TO_H2: Final[dict[PathAVerdict, H2Verdict]] = {
    PathAVerdict.GO: H2Verdict.PASS,
    PathAVerdict.NO_GO: H2Verdict.INCONCLUSIVE,
    PathAVerdict.REJECT: H2Verdict.INCONCLUSIVE,
    PathAVerdict.INCONCLUSIVE: H2Verdict.INCONCLUSIVE,
    PathAVerdict.INVALID: H2Verdict.INVALID,
}


def _map_gate_to_h2(verdict: PathAVerdict) -> H2Verdict:
    """Collapse the experiment-level 5-state gate verdict to the decision table's 3-way.

    ``GO→PASS`` / ``INVALID→INVALID`` / ``{NO_GO, REJECT, INCONCLUSIVE}→INCONCLUSIVE``
    (DA-S4GS-4). The map is total over :class:`PathAVerdict`.
    """
    return _GATE_TO_H2[verdict]


@dataclass(frozen=True, slots=True)
class S4Decision:
    """The S4 forward decision for one corner run (N=3 seeds).

    ``experiment_min_d`` (= ``min`` of the per-seed ``min_d`` over the 3 seeds) is a
    **reporting diagnostic only**: ``experiment_d_pass`` is the gate, and the
    escalation feasibility lives on the per-seed :class:`EscalationFeasibility` tuple
    (the frozen single-run min-of-3 statistic, never the cross-seed min — DA-S4GS-5).
    ``experiment_escalation_feasible`` is the experiment-level ``any`` over those
    per-seed flags (the optimistic seed, ADR §6.5) and is the boolean fed to
    :func:`path_a_density_audit.decision`.
    """

    focal_persona: str
    experiment_run_id: str
    score_report: PathAScoreReport
    h2_verdict: H2Verdict
    per_seed_audits: tuple[DensityAudit, ...]
    per_seed_escalation: tuple[EscalationFeasibility, ...]
    experiment_min_d: int
    experiment_d_pass: bool
    experiment_escalation_feasible: bool
    density_decision: DensityDecision


def run_s4_decision(
    captures: Sequence[tuple[Path | str, str, int]],
    *,
    focal_persona: str,
    experiment_run_id: str,
    ctx: IndividuationContext,
) -> S4Decision:
    """Drive one corner run's N=3 seeds to a §6.1 forward decision (CPU, GPU-free).

    ``captures`` is the N=3 ``(published .duckdb path, run_id, run_idx)`` tuple. For
    each seed the view is opened once and used for **both** the gate assembly
    (:func:`assemble_path_a_run_from_view` with the 论点 d ``focal_persona`` filter)
    and the density audit (:func:`audit_density_from_view`), then closed. The measured
    trio is cross-checked between the two sources (DA-S4GS-3) before scoring.

    Aggregation follows DA-S4GS-4/5/6: ``score_path_a_gate`` (already seed-AND'd) →
    :func:`_map_gate_to_h2`; ``experiment_d_pass = all(seed.d_pass)``; escalation is
    per-seed (frozen 3-owner statistic) aggregated with ``any`` (optimistic seed). The
    GPU smoke / inference / corner run / S5 are **not** invoked.

    Raises:
        S4RunnerError: the measured trio disagrees between the gate assembly and the
            density audit for any seed (malformed population roster).
    """
    from erre_sandbox.evidence.eval_store import (  # noqa: PLC0415  # cycle-safe lazy
        connect_analysis_view,
    )

    runs: list[PathARunInput] = []
    audits: list[DensityAudit] = []
    for path, run_id, run_idx in captures:
        view = connect_analysis_view(path)
        try:
            run_input = assemble_path_a_run_from_view(
                view,
                run_id=run_id,
                run_idx=run_idx,
                ctx=ctx,
                focal_persona=focal_persona,
            )
            audit = audit_density_from_view(
                view, run_id=run_id, focal_persona=focal_persona
            )
        finally:
            view.close()
        _cross_check_measured(run_id, run_input, audit)
        runs.append(run_input)
        audits.append(audit)

    score_report = score_path_a_gate(
        PathAExperiment(run_id=experiment_run_id, runs=tuple(runs))
    )
    h2_verdict = _map_gate_to_h2(score_report.verdict)

    per_seed_audits = tuple(audits)
    experiment_d_pass = all(a.d_pass for a in per_seed_audits)
    experiment_min_d = min(a.min_d for a in per_seed_audits)
    # Per-seed escalation: each ``a.min_d`` is a genuine 3-owner min, so the frozen
    # single-run Šidák-corrected statistic applies exactly (DA-S4GS-5). The cross-seed
    # ``experiment_min_d`` is NEVER passed here.
    per_seed_escalation = tuple(escalation_feasible(a.min_d) for a in per_seed_audits)
    experiment_escalation_feasible = any(e.feasible for e in per_seed_escalation)

    density_decision = decision(
        h2_verdict,
        d_pass=experiment_d_pass,
        escalation_feasible=experiment_escalation_feasible,
    )
    return S4Decision(
        focal_persona=focal_persona,
        experiment_run_id=experiment_run_id,
        score_report=score_report,
        h2_verdict=h2_verdict,
        per_seed_audits=per_seed_audits,
        per_seed_escalation=per_seed_escalation,
        experiment_min_d=experiment_min_d,
        experiment_d_pass=experiment_d_pass,
        experiment_escalation_feasible=experiment_escalation_feasible,
        density_decision=density_decision,
    )


def _cross_check_measured(
    run_id: str, run_input: PathARunInput, audit: DensityAudit
) -> None:
    """Assert the gate assembly and the density audit resolved the same measured trio.

    The gate keys on ``MetricResult.base_persona_id``; the audit keys on the loader's
    raw_dialog ``base_groups`` (DA-S4GS-3). A mismatch is a malformed population roster.
    """
    gate_ids = {ind.individual_id for ind in run_input.individuals}
    audit_ids = {owner_id for owner_id, _ in audit.per_owner}
    if gate_ids != audit_ids:
        msg = (
            f"seed {run_id!r}: gate-assembled measured trio {sorted(gate_ids)} !="
            f" density-audited trio {sorted(audit_ids)} (the gate resolves the trio"
            " from belief_variance base_persona_id, the audit from raw_dialog"
            " base_groups; a disagreement is a malformed population roster)"
        )
        raise S4RunnerError(msg)


__all__ = [
    "S4Decision",
    "S4RunnerError",
    "run_s4_decision",
]
