"""Structural verdict schema (design-final.md §6): the D0 pack's report shape.

``structural_status`` is a **first-class report field** (Codex MEDIUM-5) with
three values, INCONCLUSIVE-first conjunctive (house style (d), ES-1/ES-3):

* ``INCONCLUSIVE_STRUCTURAL`` — apparatus invalid: too few valid seeds, a
  structure-destroying null or situated-function control failed to collapse,
  or the D0b-runtime veto smoke failed. **Never** a substantive-negative
  claim. The 2×2 stop rule (design-final.md §6/§8) does not apply here.
* ``NO_STRUCTURAL_FLOOR`` — valid apparatus, but ``R* < R1`` (only the R0 /
  ES-1-anchor rung is non-circularly measurable).
* ``STRUCTURAL_READY`` — valid apparatus ∧ D0b-runtime pass ∧ ``R* >= R1``
  (this milestone's primary deliverable: substrate wiring + measurement
  capability, **G-GEAR runtime-ready**, *not* Godot render-ready, *not* a
  divergence test — over-claim guard, design-final.md §6).

``R*`` (:data:`RungName`) is the **highest contiguous PASS rung** starting
from R0 (design-final.md §2: "報告 = R0 から contiguous に PASS した最高
rung"). A rung earns PASS by clearing every one of design-final.md §2's five
conditions (:func:`evaluate_rung`); R2/R3's own prop-fixture-minimum gate
(``prop_fixture_valid=False``) reports that rung INCONCLUSIVE without
breaking the *overall* ``structural_status`` (only R0's own apparatus
validity gates the top-level INCONCLUSIVE_STRUCTURAL branch — R2/R3 sparsity
is an *anticipated*, honest INCONCLUSIVE, design-final.md §2 "MVP asset
sparsity 下では R2/R3 が INCONCLUSIVE に落ち R*=R1 になるのが honest な
既定予測").

The semantic track (fork C / LAO) is **out of scope** for this module
(``.steering/20260702-m13-sub1-d0-structural/requirement.md``); the 2×2
stop-rule table itself is not evaluated here — the caller (the verdict-run
script) must record the semantic side as unevaluated / ``NO_VALID_SCORER``
未評価扱い so the claim boundary in design-final.md §6 stays honest.

**Verdict value is never pinned in a test** (circular re-baking guard,
inherited house style) — only the *branch logic* is test-covered with
synthetic fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from erre_sandbox.evidence.d0_substrate import constants as _c

if TYPE_CHECKING:
    from erre_sandbox.evidence.d0_substrate.ladder import RungName, RungResult
    from erre_sandbox.evidence.d0_substrate.smoke import SmokeResult

RungPassState = Literal["PASS", "FAIL", "INCONCLUSIVE"]
StructuralStatus = Literal[
    "INCONCLUSIVE_STRUCTURAL", "NO_STRUCTURAL_FLOOR", "STRUCTURAL_READY"
]

_RUNG_ORDER: tuple[RungName, ...] = ("R0", "R1", "R2", "R3")


@dataclass(frozen=True)
class RungVerdict:
    """One rung's PASS/FAIL/INCONCLUSIVE call + the reasons behind it."""

    rung: RungName
    state: RungPassState
    reasons: tuple[str, ...]
    result: RungResult


def _apparatus_invalid_reason(result: RungResult) -> str | None:
    """First apparatus-validity failure, else ``None`` (checked before FAIL)."""
    if not result.prop_fixture_valid:
        return result.reasons[0] if result.reasons else "prop-fixture gate not met"
    if result.n_valid_seeds < _c.MIN_VALID_SEEDS:
        return (
            f"valid seeds {result.n_valid_seeds} < MIN_VALID_SEEDS {_c.MIN_VALID_SEEDS}"
        )
    if not result.null_ok:
        return (
            f"structure-destroying null did not collapse (max {result.max_null:.4f}); "
            "apparatus invalid"
        )
    if not result.control_ok:
        return (
            "situated-function control did not collapse "
            f"(value {result.control_value:.4f}); apparatus invalid"
        )
    return None


def _magnitude_failures(result: RungResult) -> list[str]:
    """GO/NO-GO magnitude conditions (only reached once the apparatus is valid)."""
    rung = result.rung
    floor = _c.CLOSURE_AMP_FLOOR if rung == "R3" else _c.LANDSCAPE_JACCARD_FLOOR
    failures: list[str] = []
    if result.median_estimand < floor:
        failures.append(f"median estimand {result.median_estimand:.4f} < floor {floor}")
    if result.ratio < _c.R_MIN:
        failures.append(f"ratio {result.ratio:.3f} < R_MIN {_c.R_MIN}")
    if result.ci_lower <= 0.0:
        failures.append(f"bootstrap CI lower {result.ci_lower:.4f} <= 0")
    if rung == "R0":
        return failures
    if result.delta_median is None or result.delta_median < _c.RESIDUAL_JACCARD_FLOOR:
        failures.append(
            f"anti-collapse median(Delta) {result.delta_median} < "
            f"RESIDUAL_JACCARD_FLOOR {_c.RESIDUAL_JACCARD_FLOOR}"
        )
    if result.delta_ci_lower is None or result.delta_ci_lower <= 0.0:
        failures.append(f"anti-collapse Delta CI lower {result.delta_ci_lower} <= 0")
    return failures


def evaluate_rung(result: RungResult) -> RungVerdict:
    """Apply design-final.md §2's five PASS conditions to one rung's result.

    Checked in the INCONCLUSIVE-first order every apparatus in this codebase
    uses: apparatus-validity failures (prop-fixture gate, too few valid
    seeds, an uncollapsed null/control) are reported before the GO/NO-GO
    magnitude conditions, so an unreliable measurement is never mistaken for
    a (progressive) FAIL.
    """
    rung = result.rung
    invalid_reason = _apparatus_invalid_reason(result)
    if invalid_reason is not None:
        return RungVerdict(rung, "INCONCLUSIVE", (invalid_reason,), result)

    failures = _magnitude_failures(result)
    if failures:
        return RungVerdict(rung, "FAIL", tuple(failures), result)
    return RungVerdict(rung, "PASS", (), result)


@dataclass(frozen=True)
class StructuralVerdict:
    """The full structural-track report (design-final.md §6)."""

    structural_status: StructuralStatus
    r_star: RungName | None
    """Highest contiguous PASS rung, or ``None`` if even R0 did not PASS."""
    rung_verdicts: tuple[RungVerdict, ...]
    smoke: SmokeResult
    reasons: tuple[str, ...]
    claim_boundary: str = (
        "STRUCTURAL_READY = substrate wiring + measurement capability "
        "(G-GEAR runtime-ready), NOT Godot render-ready, NOT a divergence "
        "test. Semantic track (fork C) is out of scope for this module; "
        "the 2x2 stop rule's semantic axis is NO_VALID_SCORER-unevaluated, "
        "not evaluated here."
    )


def render_structural_verdict(
    rung_results: dict[RungName, RungResult], smoke: SmokeResult
) -> StructuralVerdict:
    """Render the ``structural_status`` + ``R*`` from rung results + D0b smoke.

    ``rung_results`` must contain all of R0-R3 (:data:`_RUNG_ORDER`). The
    D0b-runtime veto is checked first (design-final.md §3: a smoke failure
    downgrades to ``INCONCLUSIVE_STRUCTURAL`` without trusting the ladder
    ``R*``); then R0's own verdict gates whether an ``R*`` can be reported at
    all; then contiguous PASS is walked from R0 upward.
    """
    verdicts = {rung: evaluate_rung(rung_results[rung]) for rung in _RUNG_ORDER}
    ordered = tuple(verdicts[rung] for rung in _RUNG_ORDER)

    if not smoke.passed:
        return StructuralVerdict(
            structural_status="INCONCLUSIVE_STRUCTURAL",
            r_star=None,
            rung_verdicts=ordered,
            smoke=smoke,
            reasons=("D0b-runtime veto smoke failed: " + "; ".join(smoke.reasons),),
        )

    r0_verdict = verdicts["R0"]
    if r0_verdict.state == "INCONCLUSIVE":
        return StructuralVerdict(
            structural_status="INCONCLUSIVE_STRUCTURAL",
            r_star=None,
            rung_verdicts=ordered,
            smoke=smoke,
            reasons=(
                "R0 (ES-1 anchor) apparatus invalid: " + "; ".join(r0_verdict.reasons),
            ),
        )
    if r0_verdict.state == "FAIL":
        return StructuralVerdict(
            structural_status="NO_STRUCTURAL_FLOOR",
            r_star=None,
            rung_verdicts=ordered,
            smoke=smoke,
            reasons=(
                "R0 (ES-1 anchor) did not clear its own floor: "
                + "; ".join(r0_verdict.reasons),
            ),
        )

    r_star: RungName = "R0"
    for rung in _RUNG_ORDER[1:]:
        if verdicts[rung].state != "PASS":
            break
        r_star = rung

    r_star_index = _RUNG_ORDER.index(r_star)
    status: StructuralStatus = (
        "STRUCTURAL_READY"
        if r_star_index >= _c.STRUCTURAL_READY_MIN_RUNG
        else "NO_STRUCTURAL_FLOOR"
    )
    return StructuralVerdict(
        structural_status=status,
        r_star=r_star,
        rung_verdicts=ordered,
        smoke=smoke,
        reasons=(f"R* = {r_star} (contiguous PASS from R0)",),
    )


__all__ = [
    "RungPassState",
    "RungVerdict",
    "StructuralStatus",
    "StructuralVerdict",
    "evaluate_rung",
    "render_structural_verdict",
]
