"""M10-A S4 GPU smoke wiring: the **CPU-offline subset** of the G0-1〜6 smoke harness.

This is execution-support plumbing (a harness), **not** an evaluator and **not** the
full S4 GPU smoke gate. The pre-flight ADR
(``.steering/20260603-m10a-s4-preflight-design-adr/`` §5) froze six hard gates
``G0-1〜6`` that must all PASS / exit-0 **before** the ~4.2h corner density-bearing run.
Two of them are intrinsically GPU-side and cannot run here:

* **G0-2** inference-backend live smoke (Ollama qwen3:8b / SGLang fp8),
* **G0-5** DB-column provenance (``source_individual_layer_enabled`` written non-None
  by a real run's INSERT).

This module runs only the **CPU-offline four** — ``G0-1`` (launcher roster contract),
``G0-3`` (density instrumentation computes), ``G0-4`` (H2 verdict path + sidecar), and
``G0-6`` (admission-invariance regression) — and reports ``G0-2`` / ``G0-5`` as
:data:`SmokeGateStatus.BLOCKED_GPU`. A ``BLOCKED_GPU`` gate is **never** counted as a
PASS, and :attr:`CpuSmokeReport.cpu_subset_pass` (the four CPU gates) is explicitly
**not** full-gate authorization (:attr:`CpuSmokeReport.full_gate_authorized` is False
while any GPU gate is outstanding). Authorizing the corner run is the next session's
GPU smoke (a separate BLOCK gate, user-authorized), which drives this same harness plus
the live G0-2/5.

``cli.eval_run_golden`` and ``integration.dialog`` are imported **lazily** inside the
gate functions (this module is a harness over them, not part of the evaluation leaf
chain), and the frozen §9 judgment path is never imported, so the frozen sentinel stays
``exit=0``. CPU only — no GPU / model / live backend.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from erre_sandbox.evidence.individuation.path_a_density_audit import N_CORNER
from erre_sandbox.evidence.individuation.path_a_h2_gate import (
    H2_NULL_CONTROL_CONFORMANCE,
    H2_NULL_CONTROL_KIND,
    H2Verdict,
)
from erre_sandbox.evidence.individuation.path_a_s4_runner import (
    S4Decision,
    run_s4_decision,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from erre_sandbox.evidence.individuation.runner import IndividuationContext

_MEASURED_COUNT = 3
_REQUIRED_SEEDS = 3  # ⑤ N=3 corner: exactly 3 seeds (run_idx 0/1/2)
_H2_THREE_WAY = (H2Verdict.PASS, H2Verdict.INVALID, H2Verdict.INCONCLUSIVE)


class SmokeGateStatus(StrEnum):
    """A smoke gate's outcome.

    ``BLOCKED_GPU`` is **distinct from** ``PASS`` — a gate that requires the GPU run is
    neither passed nor failed by this CPU harness.
    """

    PASS = "pass"  # noqa: S105  # enum member value, not a secret
    FAIL = "fail"
    BLOCKED_GPU = "blocked_gpu"


@dataclass(frozen=True, slots=True)
class SmokeGateResult:
    """One smoke gate's result (id, status, human-readable detail)."""

    gate_id: str
    status: SmokeGateStatus
    detail: str


@dataclass(frozen=True, slots=True)
class CpuSmokeReport:
    """The CPU-offline smoke subset's results (G0-1/3/4/6 + the BLOCKED_GPU G0-2/5).

    :attr:`cpu_subset_pass` is True iff none of the CPU gates FAILed; it deliberately
    ignores the ``BLOCKED_GPU`` gates. It is **not** full-gate authorization:
    :attr:`full_gate_authorized` stays False while any gate is ``BLOCKED_GPU`` (the
    corner run is authorized only after the GPU smoke runs G0-2/5).
    """

    gates: tuple[SmokeGateResult, ...]

    @property
    def cpu_subset_pass(self) -> bool:
        """All CPU gates passed (``BLOCKED_GPU`` gates excluded, never counted PASS)."""
        cpu = [g for g in self.gates if g.status is not SmokeGateStatus.BLOCKED_GPU]
        return bool(cpu) and all(g.status is SmokeGateStatus.PASS for g in cpu)

    @property
    def blocked_gpu_gates(self) -> tuple[str, ...]:
        """The gate ids still requiring the GPU run (G0-2 / G0-5)."""
        return tuple(
            g.gate_id for g in self.gates if g.status is SmokeGateStatus.BLOCKED_GPU
        )

    @property
    def full_gate_authorized(self) -> bool:
        """Always False while a GPU gate is outstanding (BLOCKED_GPU ≠ PASS).

        Full G0-1〜6 authorization requires the GPU-side G0-2/5 to PASS in the GPU
        smoke; this CPU harness cannot grant it.
        """
        return self.cpu_subset_pass and not self.blocked_gpu_gates


# --- CPU-offline gates -------------------------------------------------------


def g0_1_launcher_health(
    focal_persona: str, *, world_size: int = N_CORNER
) -> SmokeGateResult:
    """G0-1: the population roster contract (measured 3 same-base + background split).

    Builds the roster offline (:func:`cli.eval_run_golden.build_population_roster`,
    PR-S4a — no Ollama / SGLang) and asserts the ADR §5 PASS condition: world size N,
    N distinct agents, the measured 3 same-base focal individuals distinct from the
    cross-base background, no ValueError. The registration seam
    (``_register_population_roster``) is covered by the PR-S4a launcher test; this gate
    verifies the roster contract the density audit's measured-3 isolation relies on.
    """
    from erre_sandbox.cli.eval_run_golden import (  # noqa: PLC0415  # lazy harness import
        build_population_roster,
    )

    try:
        roster = build_population_roster(focal_persona, world_size=world_size)
    except ValueError as exc:
        return SmokeGateResult(
            "G0-1", SmokeGateStatus.FAIL, f"roster build raised: {exc}"
        )
    entries = roster.all_entries()
    problems: list[str] = []
    if roster.world_size != world_size:
        problems.append(f"world_size {roster.world_size} != {world_size}")
    if len(roster.measured) != _MEASURED_COUNT:
        problems.append(f"{len(roster.measured)} measured != {_MEASURED_COUNT}")
    if any(base != focal_persona for base, _ in roster.measured):
        problems.append("a measured individual is not the focal base")
    if any(base == focal_persona for base, _ in roster.background):
        problems.append("a background individual shares the focal base")
    if len(set(entries)) != world_size:
        problems.append(f"{len(set(entries))} distinct agents != {world_size}")
    if problems:
        return SmokeGateResult("G0-1", SmokeGateStatus.FAIL, "; ".join(problems))
    return SmokeGateResult(
        "G0-1",
        SmokeGateStatus.PASS,
        f"roster N={world_size}: 3 measured {focal_persona} + {len(roster.background)}"
        " cross-base background, all distinct",
    )


def g0_3_density_instrumentation(decision: S4Decision) -> SmokeGateResult:
    """G0-3: the density audit *computes* per-owner D_i / min(D_i) (ADR §5).

    Verifies the instrumentation produced a per-seed audit for **each of the N=3 seeds**
    (⑤ N=3 — a 1-/2-capture set must FAIL here, Codex MED-1: otherwise a capture-count
    shortfall could slip through with G0-4 reading the resulting matrix INVALID as a
    valid 3-way), each over exactly 3 measured owners with an integral ``min_d`` — the
    audit **computing** is the gate, a *passing* density is not required here (ADR §5).
    """
    audits = decision.per_seed_audits
    problems: list[str] = []
    if len(audits) != _REQUIRED_SEEDS:
        problems.append(
            f"{len(audits)} per-seed audits != {_REQUIRED_SEEDS} (⑤ N=3 corner)"
        )
    for i, audit in enumerate(audits):
        if len(audit.per_owner) != _MEASURED_COUNT:
            problems.append(
                f"seed {i}: {len(audit.per_owner)} owners != {_MEASURED_COUNT}"
            )
        if not isinstance(audit.min_d, int):
            problems.append(f"seed {i}: min_d not computed")
    if problems:
        return SmokeGateResult("G0-3", SmokeGateStatus.FAIL, "; ".join(problems))
    return SmokeGateResult(
        "G0-3",
        SmokeGateStatus.PASS,
        f"{len(audits)} seeds audited; per-seed min(D_i)="
        f"{[a.min_d for a in audits]} computed (passing density not required at G0)",
    )


def g0_4_h2_verdict_path(decision: S4Decision) -> SmokeGateResult:
    """G0-4: the H2 evaluator emits a 3-way verdict + the superseded sidecar (ADR §5).

    Asserts the experiment H2 verdict is one of the mutually-exclusive 3-way outcomes
    and the score-report sidecar carries the PR-S4b supersede markers
    (``null_control_kind = h2_owner_shuffle_resynth`` / ``conformance = conformant``),
    not the legacy ``swm_key_shuffle_projection`` / its old conformance marker.
    """
    report = decision.score_report
    problems: list[str] = []
    if decision.h2_verdict not in _H2_THREE_WAY:
        problems.append(f"h2_verdict {decision.h2_verdict!r} not 3-way")
    if report.null_control_kind != H2_NULL_CONTROL_KIND:
        problems.append(
            f"null_control_kind {report.null_control_kind!r}"
            f" != {H2_NULL_CONTROL_KIND!r}"
        )
    if report.null_control_conformance != H2_NULL_CONTROL_CONFORMANCE:
        problems.append(
            f"conformance {report.null_control_conformance!r}"
            f" != {H2_NULL_CONTROL_CONFORMANCE!r}"
        )
    if problems:
        return SmokeGateResult("G0-4", SmokeGateStatus.FAIL, "; ".join(problems))
    return SmokeGateResult(
        "G0-4",
        SmokeGateStatus.PASS,
        f"H2 verdict={decision.h2_verdict.value}, sidecar"
        f" {report.null_control_kind}/{report.null_control_conformance}",
    )


def g0_6_admission_invariance() -> SmokeGateResult:
    """G0-6: ``eval_natural_mode`` admission unchanged ((a) rejected, ADR §5 / HIGH-4).

    Asserts the frozen cadence constants (``COOLDOWN_TICKS_EVAL=5`` /
    ``AUTO_FIRE_PROB_PER_TICK=0.25`` / ``TIMEOUT_TICKS=6``) and that
    ``_iter_all_distinct_pairs`` enumerates **every** distinct pair — proximity-free,
    with no same-base preference — so density is never engineered through admission.
    """
    from erre_sandbox.integration.dialog import (  # noqa: PLC0415  # lazy harness import
        InMemoryDialogScheduler,
        _iter_all_distinct_pairs,
    )
    from erre_sandbox.schemas import (  # noqa: PLC0415  # lazy harness import
        AgentView,
        Zone,
    )

    problems: list[str] = []
    if InMemoryDialogScheduler.COOLDOWN_TICKS_EVAL != 5:  # noqa: PLR2004
        problems.append(
            f"COOLDOWN_TICKS_EVAL {InMemoryDialogScheduler.COOLDOWN_TICKS_EVAL} != 5"
        )
    if InMemoryDialogScheduler.AUTO_FIRE_PROB_PER_TICK != 0.25:  # noqa: PLR2004
        problems.append(
            "AUTO_FIRE_PROB_PER_TICK"
            f" {InMemoryDialogScheduler.AUTO_FIRE_PROB_PER_TICK} != 0.25"
        )
    if InMemoryDialogScheduler.TIMEOUT_TICKS != 6:  # noqa: PLR2004
        problems.append(f"TIMEOUT_TICKS {InMemoryDialogScheduler.TIMEOUT_TICKS} != 6")

    # Mixed bases + mixed zones: the candidate set must equal ALL distinct pairs
    # (same-base bias absent, proximity dropped).
    agents = [
        AgentView("a_kant_001", Zone.AGORA, 0),
        AgentView("a_kant_002", Zone.STUDY, 0),
        AgentView("a_kant_003", Zone.GARDEN, 0),
        AgentView("a_nietzsche_001", Zone.PERIPATOS, 0),
        AgentView("a_rikyu_001", Zone.CHASHITSU, 0),
    ]
    got = {(a.agent_id, b.agent_id) for a, b in _iter_all_distinct_pairs(agents)}
    expected = set(itertools.combinations(sorted(a.agent_id for a in agents), 2))
    if got != expected:
        problems.append("candidate set != all distinct pairs (proximity / base bias)")

    if problems:
        return SmokeGateResult("G0-6", SmokeGateStatus.FAIL, "; ".join(problems))
    return SmokeGateResult(
        "G0-6",
        SmokeGateStatus.PASS,
        "admission invariant: cooldown 5 / prob 0.25 / timeout 6, candidate ="
        f" all C({len(agents)},2)={len(expected)} pairs, no same-base bias",
    )


# --- GPU-side gates (BLOCKED here, verified in the GPU run) -------------------


def g0_2_inference_backend() -> SmokeGateResult:
    """G0-2: inference-backend live smoke — GPU-side, BLOCKED in this CPU harness."""
    return SmokeGateResult(
        "G0-2",
        SmokeGateStatus.BLOCKED_GPU,
        "inference backend live smoke (Ollama qwen3:8b base-only or SGLang fp8)"
        " requires the GPU host; verified in the GPU run, not this CPU harness",
    )


def g0_5_provenance_db_column() -> SmokeGateResult:
    """G0-5: DB-column provenance — GPU-side, BLOCKED in this CPU harness."""
    return SmokeGateResult(
        "G0-5",
        SmokeGateStatus.BLOCKED_GPU,
        "DB-column provenance (source_individual_layer_enabled written non-None by a"
        " real run's INSERT) requires the GPU run; verified there, not this harness",
    )


def run_cpu_smoke_gates(
    captures: Sequence[tuple[Path | str, str, int]],
    *,
    focal_persona: str,
    experiment_run_id: str,
    ctx: IndividuationContext,
) -> CpuSmokeReport:
    """Run the CPU-offline smoke subset over a synthetic / published N=3 capture set.

    Drives :func:`path_a_s4_runner.run_s4_decision` once (CPU, GPU-free) and runs
    G0-1/3/4/6 against it; G0-2/5 are reported ``BLOCKED_GPU``. The returned
    :class:`CpuSmokeReport` separates :attr:`~CpuSmokeReport.cpu_subset_pass` (the four
    CPU gates) from :attr:`~CpuSmokeReport.full_gate_authorized` (always False here —
    the GPU gates are outstanding).
    """
    decision = run_s4_decision(
        captures,
        focal_persona=focal_persona,
        experiment_run_id=experiment_run_id,
        ctx=ctx,
    )
    gates = (
        g0_1_launcher_health(focal_persona),
        g0_2_inference_backend(),
        g0_3_density_instrumentation(decision),
        g0_4_h2_verdict_path(decision),
        g0_5_provenance_db_column(),
        g0_6_admission_invariance(),
    )
    return CpuSmokeReport(gates=gates)


__all__ = [
    "CpuSmokeReport",
    "SmokeGateResult",
    "SmokeGateStatus",
    "g0_1_launcher_health",
    "g0_2_inference_backend",
    "g0_3_density_instrumentation",
    "g0_4_h2_verdict_path",
    "g0_5_provenance_db_column",
    "g0_6_admission_invariance",
    "run_cpu_smoke_gates",
]
