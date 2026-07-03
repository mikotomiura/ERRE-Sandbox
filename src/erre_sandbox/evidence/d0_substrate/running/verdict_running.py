"""Running-track verdict schema (design-final.md §6, INCONCLUSIVE-first).

Maps the frozen D0 pack's 3-way ``structural_status`` branch logic onto
running-specific tokens (the branch logic itself is unchanged, design-final.md
§4.2/§6):

* **``INCONCLUSIVE_RUNNING``** — apparatus/running invalid: running-ness gate
  fail (``CI_lower(TV) <= RUNNINGNESS_TV_FLOOR``), replay-checksum mismatch,
  ``n_valid_seeds < MIN_VALID_SEEDS``, an uncollapsed structure-destroying null
  / situated-function control (R0 :func:`~...verdict_report.evaluate_rung`
  INCONCLUSIVE), or **D_1 degenerate** (arms never diverge — ``max_seed(d1) <=
  ZERO_TOL``, §2.3 failure-3, kept distinct from a ``Δ_1 ≈ 0`` with ``D_1 > 0``
  which is the NO_STRUCTURAL_FLOOR failure-1). Not a substantive floor claim;
  the 2×2 stop rule does not apply.
* **``NO_STRUCTURAL_FLOOR_RUNNING``** — valid ∧ gate pass ∧ ``R* < R1``. ->
  §5-5 one-shot kill -> close-reconsideration ADR (§4.3 saturation forensic
  attached).
* **``STRUCTURAL_READY_RUNNING``** — valid ∧ gate pass ∧ ``R* >= R1`` ∧ paired
  contrast (``running_R_star >= R1`` ∧ ``frozen_R_star == R0``). This
  milestone's primary deliverable: within-zone structural outcome measurable
  non-circularly **on a running trace**, and the frozen<->running distinction
  is real. **NOT a divergence test; the R1 advance is not itself
  running-specific** (design-final.md §4.1/§6/§7).

``claim_scope`` is machine-decided from the forensic report (design-final.md
§6.1): an **unconditional** caveat that "R1 advance is not itself
running-specific; running-ness is certified separately by the §3 gate" is
always embedded (Codex M4), plus the 5-zone vs CHASHITSU-local narrowing
(§8.1) and the teaching-to-the-test caveat (§7).

**Verdict value is never pinned in a test** (circular re-baking guard, house
style) — only the branch logic, over synthetic fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from erre_sandbox.evidence.d0_substrate import constants as _c
from erre_sandbox.evidence.d0_substrate.running import constants as _rc
from erre_sandbox.evidence.d0_substrate.verdict_report import evaluate_rung

if TYPE_CHECKING:
    from collections.abc import Mapping

    from erre_sandbox.evidence.d0_substrate.ladder import RungName, RungResult
    from erre_sandbox.evidence.d0_substrate.running.forensic import ForensicReport
    from erre_sandbox.evidence.d0_substrate.running.runningness import RunningnessResult

StructuralStatusRunning = Literal[
    "INCONCLUSIVE_RUNNING", "NO_STRUCTURAL_FLOOR_RUNNING", "STRUCTURAL_READY_RUNNING"
]

_RUNG_ORDER: tuple[RungName, ...] = ("R0", "R1", "R2", "R3")

_BASE_CLAIM: str = "structural_running_within_zone_existence_terminal_anchored"
_UNCONDITIONAL_CAVEAT: str = (
    "R1_advance_not_itself_running_specific__runningness_certified_separately_by_gate"
)
_TEACHING_CAVEAT: str = (
    "existence_proof_under_return_to_home_errand__not_spontaneous_substrate_property"
)


@dataclass(frozen=True)
class RunningVerdict:
    """The full running-track report (design-final.md §6/§8)."""

    structural_status_running: StructuralStatusRunning
    running_r_star: RungName | None
    frozen_r_star: RungName | None
    running_ness_tv_ci_lower: float
    running_ness_gate_pass: bool
    running_tv_indep_baseline: float
    running_tv_other_cloud_baseline: float
    replay_checksum: str
    replay_ok: bool
    n_valid_seeds: int
    d1_degenerate: bool
    within_zone_geometry_present: bool
    topk_zone_saturated: float
    clamp_rate: float
    per_zone_memory_count: Mapping[str, float]
    per_zone_delta1_contribution: Mapping[str, float]
    prop_free_zone_delta1: float
    memoryless_r1_pass: bool
    memoryless_running_tv_ci_lower: float
    spontaneous_r1_pass: bool
    spontaneous_median_delta1: float
    spontaneous_terminal_zone_memory_count: float
    no_reflect_r1_pass: bool
    uniform_centroid_r1_pass: bool
    top1_centroid_r1_pass: bool
    rung_states: Mapping[str, str]
    claim_scope: str
    reasons: tuple[str, ...]
    semantic_status: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    gpu_hours: float = 0.0


def _build_claim_scope(forensic: ForensicReport) -> str:
    """Machine-decide ``claim_scope`` from the forensic report (design-final.md §6.1).

    Authoritative for ``STRUCTURAL_READY_RUNNING``; harmless (caveat-only) for
    the other statuses. The unconditional caveat is embedded regardless of the
    control outcomes (Codex M4).
    """
    parts = [_BASE_CLAIM, f"caveat={_UNCONDITIONAL_CAVEAT}"]
    if forensic.prop_free_zone_delta1 >= _c.RESIDUAL_JACCARD_FLOOR:
        parts.append("scope=5zone")
    else:
        parts.append("scope=chashitsu_prop_local_only")
    if forensic.memoryless_r1_pass:
        parts.append("note=same_concentration_passes_R1_memorylessly")
    if not forensic.spontaneous_r1_pass:
        parts.append("note=spontaneous_emergence_unmeasured")
    parts.append(f"caveat={_TEACHING_CAVEAT}")
    return " | ".join(parts)


def render_running_verdict(  # noqa: PLR0911, C901 — INCONCLUSIVE-first guard sequence
    running_rungs: Mapping[RungName, RungResult],
    *,
    frozen_r_star: RungName | None,
    runningness: RunningnessResult,
    forensic: ForensicReport,
    replay_checksum: str,
    replay_ok: bool,
    max_d1: float,
) -> RunningVerdict:
    """Render ``structural_status_running`` + ``R*`` (design-final.md §6).

    ``max_d1`` is the maximum per-seed raw R1 divergence across the seed bank
    (the D_1-degenerate discriminator, §2.3 failure-3). Checked INCONCLUSIVE-
    first: running-ness / replay / apparatus validity / degeneracy before the
    magnitude verdict, so an unreliable measurement is never mistaken for a
    (progressive) NO_STRUCTURAL_FLOOR.
    """
    verdicts = {rung: evaluate_rung(running_rungs[rung]) for rung in _RUNG_ORDER}
    r0_verdict = verdicts["R0"]
    n_valid = running_rungs["R0"].n_valid_seeds
    d1_degenerate = max_d1 <= _c.ZERO_TOL
    claim_scope = _build_claim_scope(forensic)

    def _base(
        status: StructuralStatusRunning,
        r_star: RungName | None,
        reasons: tuple[str, ...],
    ) -> RunningVerdict:
        return RunningVerdict(
            structural_status_running=status,
            running_r_star=r_star,
            frozen_r_star=frozen_r_star,
            running_ness_tv_ci_lower=runningness.tv_ci_lower,
            running_ness_gate_pass=runningness.gate_pass,
            running_tv_indep_baseline=runningness.tv_ci_lower_indep_baseline,
            running_tv_other_cloud_baseline=runningness.tv_ci_lower_other_cloud_baseline,
            replay_checksum=replay_checksum,
            replay_ok=replay_ok,
            n_valid_seeds=n_valid,
            d1_degenerate=d1_degenerate,
            within_zone_geometry_present=forensic.within_zone_geometry_present,
            topk_zone_saturated=forensic.topk_zone_saturated,
            clamp_rate=forensic.clamp_rate,
            per_zone_memory_count=forensic.per_zone_memory_count,
            per_zone_delta1_contribution=forensic.per_zone_delta1_contribution,
            prop_free_zone_delta1=forensic.prop_free_zone_delta1,
            memoryless_r1_pass=forensic.memoryless_r1_pass,
            memoryless_running_tv_ci_lower=forensic.memoryless_running_tv_ci_lower,
            spontaneous_r1_pass=forensic.spontaneous_r1_pass,
            spontaneous_median_delta1=forensic.spontaneous_median_delta1,
            spontaneous_terminal_zone_memory_count=(
                forensic.spontaneous_terminal_zone_memory_count
            ),
            no_reflect_r1_pass=forensic.no_reflect_r1_pass,
            uniform_centroid_r1_pass=forensic.uniform_centroid_r1_pass,
            top1_centroid_r1_pass=forensic.top1_centroid_r1_pass,
            rung_states={rung: verdicts[rung].state for rung in _RUNG_ORDER},
            claim_scope=claim_scope,
            reasons=reasons,
        )

    # --- INCONCLUSIVE-first apparatus/running validity gates -------------------
    if not replay_ok:
        return _base("INCONCLUSIVE_RUNNING", None, ("replay checksum mismatch",))
    if n_valid < _c.MIN_VALID_SEEDS:
        # Explicit guard (code-reviewer HIGH-2): R0's own evaluate_rung also
        # catches this, but making it a first-class INCONCLUSIVE_RUNNING branch
        # matches the schema docstring and covers a short seed bank directly.
        return _base(
            "INCONCLUSIVE_RUNNING",
            None,
            (f"valid seeds {n_valid} < MIN_VALID_SEEDS {_c.MIN_VALID_SEEDS}",),
        )
    if not runningness.gate_pass:
        return _base(
            "INCONCLUSIVE_RUNNING",
            None,
            (
                f"running-ness gate fail: CI_lower(TV)={runningness.tv_ci_lower:.4f} "
                f"<= RUNNINGNESS_TV_FLOOR {_rc.RUNNINGNESS_TV_FLOOR} "
                "(memoryless / frozen-replay adjacent)",
            ),
        )
    if d1_degenerate:
        return _base(
            "INCONCLUSIVE_RUNNING",
            None,
            (
                f"D_1 degenerate: max per-seed d1 {max_d1:.4g} <= ZERO_TOL "
                "(arms never diverge)",
            ),
        )
    if r0_verdict.state == "INCONCLUSIVE":
        return _base(
            "INCONCLUSIVE_RUNNING",
            None,
            ("R0 (ES-1 anchor) apparatus invalid: " + "; ".join(r0_verdict.reasons),),
        )
    if r0_verdict.state == "FAIL":
        return _base(
            "NO_STRUCTURAL_FLOOR_RUNNING",
            None,
            (
                "R0 (ES-1 anchor) did not clear its own floor: "
                + "; ".join(r0_verdict.reasons),
            ),
        )

    # --- contiguous PASS walk + paired-contrast corroboration ------------------
    r_star: RungName = "R0"
    for rung in _RUNG_ORDER[1:]:
        if verdicts[rung].state != "PASS":
            break
        r_star = rung
    r_star_index = _RUNG_ORDER.index(r_star)
    # Paired contrast requires the blind apparatus to reach EXACTLY R0 (PR #44
    # known result). ``frozen_r_star is None`` (blind INCONCLUSIVE or R0-fail)
    # must NOT corroborate — Codex HIGH-2: a coerced "R0" would falsely pass.
    paired_ok = frozen_r_star == "R0"

    if r_star_index >= _c.STRUCTURAL_READY_MIN_RUNG and paired_ok:
        return _base(
            "STRUCTURAL_READY_RUNNING",
            r_star,
            (
                f"R* = {r_star} (contiguous PASS from R0) >= R1; paired contrast "
                "corroborated (frozen_R* == R0); running-ness gate pass",
            ),
        )
    reason = (
        f"R* = {r_star} < R1 (within-zone structure not non-circularly measurable)"
        if r_star_index < _c.STRUCTURAL_READY_MIN_RUNG
        else f"paired contrast not corroborated (frozen_R* = {frozen_r_star} != R0)"
    )
    return _base("NO_STRUCTURAL_FLOOR_RUNNING", r_star, (reason,))


__all__ = [
    "RunningVerdict",
    "StructuralStatusRunning",
    "render_running_verdict",
]
