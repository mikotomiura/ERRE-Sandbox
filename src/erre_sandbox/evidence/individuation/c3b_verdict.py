"""M11-C3b GO/NO-GO verdict scorer (frozen-ADR decision rule, pure function).

Turns the captured artifacts of a same-base rikyu pilot into one of four
verdicts — ``GO`` / ``REJECT`` / ``inconclusive`` / ``invalid`` — by applying the
**frozen** decision rule of the M11-C3b GO/NO-GO ADR
(§4.2 / §5 / §6 / §7 / §7.1). Every threshold (1.5× floor
margin, 0.02 backstop, Burrows Δ≤4.0, 0.70 throughput floor, N=2 seeds) is a
module-level :data:`Final` so the scorer cannot silently drift from the ADR.

The scorer is a **pure function over already-loaded rows** (panel + Burrows
:class:`MetricResult` rows + throughput primitives), never a DuckDB reader, so
the precedence machine is exercised by synthetic fixtures with no GPU / model /
DB — the "GO criteria 後出し封じ" lesson made executable.

Decision order (ADR §7.1 precedence, evaluated top-down, first match wins):

1. **invalid** — any seed/condition fails preflight (P-1) or the flag-off
   throughput denominator is not a ``complete`` run (§5.2/§5.3/§10).
2. **REJECT** — a *scorable* hard fail in any seed: a primary encoder direction
   collapse, a primary encoder gate miss, Burrows worse than the floor/control,
   or throughput below 70% (§5.4, 緩和禁止).
3. **inconclusive** — preflight held, no hard fail, but a sample-floor shortfall
   (degenerate dyad / floor, all-unsupported Burrows) or fewer than the required
   seeds blocks scoring (§5.2/§3).
4. **GO** — every hard axis passes in all required seeds (§7).

The centroid axis is judged against the **within-individual** odd/even floor
(ADR §2.1, the primary control); flag-off only supplies the Burrows control
ratio and the throughput denominator (ADR §2.2). belief_variance / Vendi /
stage branching are diagnostic and never enter this scorer (continuity-bias
guard, §1.2/§11).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from statistics import median
from typing import TYPE_CHECKING, Final

from erre_sandbox.evidence.individuation.policy import (
    AggregationLevel,
    MetricStatus,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.evidence.individuation.models import MetricResult

# --- frozen ADR constants (one source, ADR §9) -----------------------------
CENTROID_FLOOR_MARGIN: Final[float] = 1.5
"""ADR §4.2: ``median_dyad(d_cross) >= 1.5 × d_within_floor`` (effect margin)."""
CENTROID_ABS_BACKSTOP: Final[float] = 0.02
"""ADR §4.2: ``min_dyad(d_cross) >= 0.02`` (conservative degeneracy backstop)."""
BURROWS_DELTA_MAX: Final[float] = 4.0
"""ADR §4.1: absolute Burrows ``delta <= 4.0`` for base retention."""
THROUGHPUT_FLOOR_RATIO: Final[float] = 0.70
"""ADR §5.3: treatment throughput ``>= 0.70 × flag-off complete reference``."""
REQUIRED_SEED_COUNT: Final[int] = 2
"""ADR §6: N=2 seeds (run_idx 0,1); seed=1 縮退禁止."""
PRIMARY_ENCODER_IDS: Final[tuple[str, ...]] = (
    "sentence-transformers/all-mpnet-base-v2",
    "intfloat/multilingual-e5-large",
)
"""ADR §5.1 primary panel encoders (mpnet + multilingual-e5-large). bge-m3 is
exploratory (reported, not gated) so it is not in the agreement set."""
EXPLORATORY_ENCODER_IDS: Final[tuple[str, ...]] = ("BAAI/bge-m3",)
"""ADR §5.1 exploratory encoder (bge-m3): its centroid/floor gate is *computed
and recorded* in the verdict sidecar (報告必須) but kept out of the agreement
aggregation (gate 非寄与)."""
REQUIRED_SEED_IDS: Final[tuple[int, ...]] = (0, 1)
"""ADR §6: the only legal seed values (run_idx 0,1). A seed value outside this
set is a frozen-binding protocol violation -> invalid, distinct from the
'fewer than 2 well-formed seeds' sample shortfall that maps to inconclusive
(DA-M11C3b-exec-2). This closes the {0,2}-passes-count==2 hole."""

_CENTROID_METRIC: Final[str] = "semantic_centroid_distance"
_FLOOR_METRIC: Final[str] = "semantic_centroid_within_floor"
_BURROWS_METRIC: Final[str] = "burrows_base_retention"
_COMPLETE_STATUS: Final[str] = "complete"


class Verdict(StrEnum):
    """The four-state C3b real-run verdict (ADR §0.1)."""

    GO = "go"
    REJECT = "reject"
    INCONCLUSIVE = "inconclusive"
    INVALID = "invalid"


class AxisOutcome(StrEnum):
    """One hard axis' (or encoder gate's) outcome for one seed."""

    PASS = "pass"  # noqa: S105 — an axis outcome label, not a credential
    FAIL = "fail"  # scorable hard fail -> REJECT (§5.4)
    INSUFFICIENT = "insufficient"  # sample-floor shortfall -> inconclusive (§3)


# --- inputs ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConditionRun:
    """One ``(seed, condition)`` capture's scorable artifacts.

    ``individual_layer_enabled`` is ``True`` for the treatment (flag-on) run and
    ``False`` for the flag-off control. ``panel_rows`` are the centroid +
    within-floor rows from :func:`compute_centroid_panel`; ``burrows_rows`` the
    per-individual ``burrows_base_retention`` rows from
    :func:`compute_individuation`. ``focal_rows`` / ``elapsed_seconds`` /
    ``capture_status`` come from the capture sidecar (P1a instrumentation).
    """

    seed: int
    individual_layer_enabled: bool
    preflight_ok: bool
    capture_status: str
    focal_rows: int
    elapsed_seconds: float | None
    panel_rows: tuple[MetricResult, ...] = ()
    burrows_rows: tuple[MetricResult, ...] = ()


@dataclass(frozen=True, slots=True)
class VerdictExperiment:
    """All ``(seed, condition)`` runs of one C3b pilot to be scored together."""

    run_id: str
    runs: tuple[ConditionRun, ...]
    primary_encoder_ids: tuple[str, ...] = PRIMARY_ENCODER_IDS
    exploratory_encoder_ids: tuple[str, ...] = EXPLORATORY_ENCODER_IDS
    required_seeds: int = REQUIRED_SEED_COUNT


# --- outputs ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EncoderGate:
    """Per-encoder centroid gate result (ADR §4.2)."""

    encoder_id: str
    outcome: AxisOutcome
    reason: str
    median_cross: float | None = None
    min_cross: float | None = None
    floor: float | None = None
    direction_positive: bool | None = None


@dataclass(frozen=True, slots=True)
class AxisResult:
    """One hard axis' aggregated outcome for one seed."""

    outcome: AxisOutcome
    reason: str


@dataclass(frozen=True, slots=True)
class SeedResult:
    """Per-seed scoring (or the invalid reason that stops it)."""

    seed: int
    valid: bool
    invalid_reason: str | None = None
    centroid: AxisResult | None = None
    burrows: AxisResult | None = None
    throughput: AxisResult | None = None
    encoder_gates: tuple[EncoderGate, ...] = ()
    exploratory_gates: tuple[EncoderGate, ...] = ()
    """ADR §5.1 exploratory (bge-m3) gate(s): recorded for the sidecar 報告
    obligation but never folded into the agreement aggregation."""


@dataclass(frozen=True, slots=True)
class VerdictReport:
    """The final four-state verdict + the per-seed evidence that produced it."""

    run_id: str
    verdict: Verdict
    reason: str
    seeds: tuple[SeedResult, ...] = field(default_factory=tuple)


# --- scorer ----------------------------------------------------------------


def score_c3b_verdict(experiment: VerdictExperiment) -> VerdictReport:
    """Score one C3b pilot to a four-state verdict (ADR §7.1 precedence).

    The seed/condition matrix is validated **before** any scoring (B-1): a
    protocol-violating shape (illegal seed value, duplicate (seed, condition),
    or a present seed missing one condition) is ``invalid`` and never reaches the
    axis scoring — the "GO 基準後出し封じ" cannot be bypassed by a malformed grid.
    A merely *incomplete* but well-formed grid (e.g. only seed 0's on/off pair)
    is not a violation here; it falls through to the inconclusive sample-shortfall
    branch in :func:`_aggregate` (DA-M11C3b-exec-2).
    """
    matrix_violation = _validate_matrix(experiment.runs)
    if matrix_violation is not None:
        return VerdictReport(
            run_id=experiment.run_id,
            verdict=Verdict.INVALID,
            reason=f"2x2 seed/condition matrix protocol violation — {matrix_violation}",
            seeds=(),
        )

    by_seed: dict[int, dict[bool, ConditionRun]] = {}
    for run in experiment.runs:
        by_seed.setdefault(run.seed, {})[run.individual_layer_enabled] = run

    seed_results = tuple(
        _score_seed(seed, by_seed[seed], experiment) for seed in sorted(by_seed)
    )
    verdict, reason = _aggregate(seed_results, experiment)
    return VerdictReport(
        run_id=experiment.run_id,
        verdict=verdict,
        reason=reason,
        seeds=seed_results,
    )


def _score_seed(
    seed: int,
    conditions: dict[bool, ConditionRun],
    experiment: VerdictExperiment,
) -> SeedResult:
    treatment = conditions.get(True)
    control = conditions.get(False)
    invalid_reason = _seed_invalid_reason(treatment, control)
    if invalid_reason is not None:
        return SeedResult(seed=seed, valid=False, invalid_reason=invalid_reason)

    # treatment / control are non-None and scorable past the invalid gate.
    assert treatment is not None  # narrowed by _seed_invalid_reason
    assert control is not None
    gates = tuple(
        _score_encoder(treatment.panel_rows, encoder_id)
        for encoder_id in experiment.primary_encoder_ids
    )
    # Exploratory (bge-m3) gates are computed for the sidecar's 報告 obligation
    # (ADR §5.1) but never enter _aggregate_encoder_gates → gate 非寄与.
    exploratory = tuple(
        _score_encoder(treatment.panel_rows, encoder_id)
        for encoder_id in experiment.exploratory_encoder_ids
    )
    return SeedResult(
        seed=seed,
        valid=True,
        centroid=_aggregate_encoder_gates(gates),
        burrows=_score_burrows(treatment.burrows_rows, control.burrows_rows),
        throughput=_score_throughput(treatment, control),
        encoder_gates=gates,
        exploratory_gates=exploratory,
    )


def _validate_matrix(runs: Sequence[ConditionRun]) -> str | None:
    """Exact 2x2 seed/condition matrix check (ADR §6, B-1).

    Returns a violation reason (→ invalid) or ``None`` when the supplied runs are
    *well-formed*: every seed value is in :data:`REQUIRED_SEED_IDS`, no duplicate
    ``(seed, condition)``, and every present seed carries both flag-on and
    flag-off. Fewer than the required number of well-formed seeds is **not** a
    violation — that sample shortfall is mapped to inconclusive downstream
    (DA-M11C3b-exec-2), preserving the only-one-seed re-capture semantics while
    still refusing illegal seed values ({0,2}), duplicates, and half pairs.
    """
    illegal = sorted({r.seed for r in runs if r.seed not in REQUIRED_SEED_IDS})
    if illegal:
        return (
            f"illegal seed value(s) {illegal}; only run_idx"
            f" {list(REQUIRED_SEED_IDS)} are the frozen ADR §6 binding"
        )
    seen: set[tuple[int, bool]] = set()
    for r in runs:
        key = (r.seed, r.individual_layer_enabled)
        if key in seen:
            cond = "flag-on" if r.individual_layer_enabled else "flag-off"
            return f"duplicate (seed {r.seed}, {cond}) run"
        seen.add(key)
    by_seed: dict[int, set[bool]] = {}
    for r in runs:
        by_seed.setdefault(r.seed, set()).add(r.individual_layer_enabled)
    for seed, conds in sorted(by_seed.items()):
        if conds != {True, False}:
            missing = "flag-off" if True in conds else "flag-on"
            return f"seed {seed} missing {missing} condition (incomplete pair)"
    return None


def _seed_invalid_reason(
    treatment: ConditionRun | None,
    control: ConditionRun | None,
) -> str | None:
    """Why this seed is invalid (preflight / denominator), or ``None`` if scorable."""
    if treatment is None or control is None:
        missing = "treatment (flag-on)" if treatment is None else "control (flag-off)"
        return f"missing {missing} condition for the seed"
    # First failing check wins (kept as a table to stay within the return budget).
    checks: list[tuple[bool, str]] = [
        (
            not treatment.preflight_ok or not control.preflight_ok,
            "preflight (P-1) not satisfied (launcher / panel / e5 prefix)",
        ),
        (
            control.capture_status != _COMPLETE_STATUS,
            f"flag-off reference not complete (status={control.capture_status!r});"
            " throughput denominator invalid",
        ),
        (
            control.elapsed_seconds is None or control.elapsed_seconds <= 0,
            "flag-off reference elapsed_seconds missing/non-positive",
        ),
        (
            treatment.capture_status == "fatal" or treatment.elapsed_seconds is None,
            "treatment capture fatal / no runtime-phase elapsed",
        ),
        (
            treatment.elapsed_seconds is not None and treatment.elapsed_seconds <= 0,
            "treatment elapsed_seconds non-positive",
        ),
    ]
    return next((reason for failed, reason in checks if failed), None)


def _score_encoder(
    panel_rows: Sequence[MetricResult],
    encoder_id: str,
) -> EncoderGate:
    """Per-encoder centroid gate vs the within-individual floor (ADR §4.2).

    A degenerate dyad / floor is encoder-independent (an empty or too-small
    window fails for *every* encoder) and its ``MetricResult`` carries
    ``embedding_model_id=None`` (the ``_degenerate`` path strips it, enforced by
    M10-0's ``test_centroid_n1_degenerate``). So degeneracy is detected globally
    over the metric/level, while VALID rows are matched to this ``encoder_id``.
    """
    valid_cross = [
        r.value
        for r in panel_rows
        if r.metric_name == _CENTROID_METRIC
        and r.aggregation_level is AggregationLevel.PER_DYAD
        and r.status is MetricStatus.VALID
        and r.provenance.embedding_model_id == encoder_id
        and r.value is not None
    ]
    valid_floor = [
        r.value
        for r in panel_rows
        if r.metric_name == _FLOOR_METRIC
        and r.aggregation_level is AggregationLevel.PER_INDIVIDUAL
        and r.status is MetricStatus.VALID
        and r.provenance.embedding_model_id == encoder_id
        and r.value is not None
    ]
    # ADR §3: any degenerate dyad / floor -> sample shortfall -> inconclusive
    # (encoder-agnostic: degenerate rows carry no embedding_model_id).
    if _has_degenerate(panel_rows, _CENTROID_METRIC, AggregationLevel.PER_DYAD):
        return EncoderGate(
            encoder_id, AxisOutcome.INSUFFICIENT, "degenerate dyad (sample floor)"
        )
    if _has_degenerate(panel_rows, _FLOOR_METRIC, AggregationLevel.PER_INDIVIDUAL):
        return EncoderGate(
            encoder_id,
            AxisOutcome.INSUFFICIENT,
            "degenerate within-floor (sample floor)",
        )
    if not valid_cross or not valid_floor:
        return EncoderGate(
            encoder_id,
            AxisOutcome.INSUFFICIENT,
            "no valid centroid / floor rows for this encoder",
        )

    median_cross = float(median(valid_cross))
    min_cross = float(min(valid_cross))
    floor = float(median(valid_floor))  # 3-individual median (scorer step, §2.1)
    direction_positive = median_cross > floor
    if not direction_positive:
        return EncoderGate(
            encoder_id,
            AxisOutcome.FAIL,
            f"direction collapse: median_dyad {median_cross:.4f} <= floor {floor:.4f}",
            median_cross,
            min_cross,
            floor,
            direction_positive,
        )
    gate_pass = (
        median_cross >= CENTROID_FLOOR_MARGIN * floor
        and min_cross >= CENTROID_ABS_BACKSTOP
    )
    if not gate_pass:
        return EncoderGate(
            encoder_id,
            AxisOutcome.FAIL,
            (
                f"gate miss: median {median_cross:.4f} vs"
                f" {CENTROID_FLOOR_MARGIN}×floor {CENTROID_FLOOR_MARGIN * floor:.4f},"
                f" min {min_cross:.4f} vs backstop {CENTROID_ABS_BACKSTOP}"
            ),
            median_cross,
            min_cross,
            floor,
            direction_positive,
        )
    return EncoderGate(
        encoder_id,
        AxisOutcome.PASS,
        "median >= 1.5×floor, min >= backstop, direction positive",
        median_cross,
        min_cross,
        floor,
        direction_positive,
    )


def _aggregate_encoder_gates(gates: Sequence[EncoderGate]) -> AxisResult:
    """Encoder agreement: both primaries PASS (with positive direction), §5.1/§7."""
    failed = [g for g in gates if g.outcome is AxisOutcome.FAIL]
    if failed:
        names = ", ".join(f"{g.encoder_id} ({g.reason})" for g in failed)
        return AxisResult(AxisOutcome.FAIL, f"primary encoder hard fail: {names}")
    insufficient = [g for g in gates if g.outcome is AxisOutcome.INSUFFICIENT]
    if insufficient:
        names = ", ".join(f"{g.encoder_id} ({g.reason})" for g in insufficient)
        return AxisResult(
            AxisOutcome.INSUFFICIENT, f"encoder sample shortfall: {names}"
        )
    return AxisResult(
        AxisOutcome.PASS, "both primary encoders pass gate + direction positive"
    )


def _score_burrows(
    treatment_rows: Sequence[MetricResult],
    control_rows: Sequence[MetricResult],
) -> AxisResult:
    """Burrows base retention: 3/3 individuals Δ≤4.0 AND control non-increase (§7)."""
    treatment = _burrows_by_individual(treatment_rows)
    control = _burrows_by_individual(control_rows)
    if not treatment:
        return AxisResult(
            AxisOutcome.INSUFFICIENT, "no treatment burrows rows (ja adapter unfired?)"
        )

    outcomes: list[tuple[AxisOutcome, str]] = []
    for individual_id, t_value in treatment.items():
        c_value = control.get(individual_id)
        if t_value is None or c_value is None:
            outcomes.append(
                (
                    AxisOutcome.INSUFFICIENT,
                    f"{individual_id}: treatment/control burrows not both valid",
                )
            )
            continue
        if t_value > BURROWS_DELTA_MAX:
            outcomes.append(
                (AxisOutcome.FAIL, f"{individual_id}: delta {t_value:.3f} > 4.0")
            )
        elif t_value > c_value:
            outcomes.append(
                (
                    AxisOutcome.FAIL,
                    f"{individual_id}: flag-on {t_value:.3f} > flag-off {c_value:.3f}",
                )
            )
        else:
            outcomes.append((AxisOutcome.PASS, f"{individual_id}: ok"))

    return _reduce_outcomes(
        outcomes,
        fail_prefix="burrows hard fail",
        insufficient_prefix="burrows sample shortfall",
        ok_reason="all individuals delta <= 4.0 and <= flag-off control",
    )


def _score_throughput(
    treatment: ConditionRun,
    control: ConditionRun,
) -> AxisResult:
    """Treatment throughput >= 0.70 × flag-off complete reference (§5.3)."""
    # Non-None / positive elapsed guaranteed by _seed_invalid_reason.
    assert treatment.elapsed_seconds is not None
    assert control.elapsed_seconds is not None
    treatment_tp = treatment.focal_rows / (treatment.elapsed_seconds / 60.0)
    control_tp = control.focal_rows / (control.elapsed_seconds / 60.0)
    if control_tp <= 0:
        return AxisResult(
            AxisOutcome.INSUFFICIENT,
            "flag-off reference throughput is zero (no focal rows)",
        )
    floor = THROUGHPUT_FLOOR_RATIO * control_tp
    if treatment_tp < floor:
        return AxisResult(
            AxisOutcome.FAIL,
            (
                f"throughput {treatment_tp:.3f}/min <"
                f" 0.70×{control_tp:.3f} = {floor:.3f}/min"
            ),
        )
    return AxisResult(
        AxisOutcome.PASS,
        f"throughput {treatment_tp:.3f}/min >= {floor:.3f}/min (70% of flag-off)",
    )


def _aggregate(
    seed_results: Sequence[SeedResult],
    experiment: VerdictExperiment,
) -> tuple[Verdict, str]:
    """Apply the §7.1 precedence: invalid > REJECT > inconclusive > GO."""
    if not seed_results:
        return Verdict.INCONCLUSIVE, "no seeds supplied"

    invalid = [s for s in seed_results if not s.valid]
    if invalid:
        reasons = "; ".join(f"seed {s.seed}: {s.invalid_reason}" for s in invalid)
        return Verdict.INVALID, f"preflight / denominator invalid — {reasons}"

    axes = [
        (s.seed, name, axis)
        for s in seed_results
        for name, axis in (
            ("centroid", s.centroid),
            ("burrows", s.burrows),
            ("throughput", s.throughput),
        )
        if axis is not None
    ]
    fails = [
        f"seed {seed} {name}: {axis.reason}"
        for seed, name, axis in axes
        if axis.outcome is AxisOutcome.FAIL
    ]
    if fails:
        return Verdict.REJECT, "scorable hard fail (緩和禁止) — " + "; ".join(fails)

    if len(seed_results) < experiment.required_seeds:
        return (
            Verdict.INCONCLUSIVE,
            (
                f"only {len(seed_results)} of {experiment.required_seeds} required"
                " seeds present (seed=1 縮退禁止, §6); re-capture"
            ),
        )

    insufficient = [
        f"seed {seed} {name}: {axis.reason}"
        for seed, name, axis in axes
        if axis.outcome is AxisOutcome.INSUFFICIENT
    ]
    if insufficient:
        return (
            Verdict.INCONCLUSIVE,
            "sample shortfall (re-capture, same thresholds) — "
            + "; ".join(insufficient),
        )

    return (
        Verdict.GO,
        (
            f"all hard axes pass in {experiment.required_seeds}/"
            f"{experiment.required_seeds} seeds"
        ),
    )


# --- helpers ---------------------------------------------------------------


def _has_degenerate(
    rows: Sequence[MetricResult],
    metric_name: str,
    level: AggregationLevel,
) -> bool:
    """Whether any ``(metric_name, level)`` row is degenerate (any encoder).

    Degenerate panel rows carry ``embedding_model_id=None``, so degeneracy is
    matched on metric + level only; it marks an encoder-independent sample-floor
    shortfall (ADR §3) that makes every encoder's gate insufficient.
    """
    return any(
        r.metric_name == metric_name
        and r.aggregation_level is level
        and r.status is MetricStatus.DEGENERATE
        for r in rows
    )


def _burrows_by_individual(
    rows: Sequence[MetricResult],
) -> dict[str, float | None]:
    """Map individual_id -> burrows delta (``None`` for non-valid rows)."""
    out: dict[str, float | None] = {}
    for r in rows:
        if (
            r.metric_name == _BURROWS_METRIC
            and r.aggregation_level is AggregationLevel.PER_INDIVIDUAL
        ):
            out[r.individual_id] = r.value if r.status is MetricStatus.VALID else None
    return out


def _reduce_outcomes(
    outcomes: Sequence[tuple[AxisOutcome, str]],
    *,
    fail_prefix: str,
    insufficient_prefix: str,
    ok_reason: str,
) -> AxisResult:
    """FAIL > INSUFFICIENT > PASS reduction over per-individual outcomes."""
    fails = [reason for outcome, reason in outcomes if outcome is AxisOutcome.FAIL]
    if fails:
        return AxisResult(AxisOutcome.FAIL, f"{fail_prefix}: " + "; ".join(fails))
    short = [
        reason for outcome, reason in outcomes if outcome is AxisOutcome.INSUFFICIENT
    ]
    if short:
        return AxisResult(
            AxisOutcome.INSUFFICIENT, f"{insufficient_prefix}: " + "; ".join(short)
        )
    return AxisResult(AxisOutcome.PASS, ok_reason)


__all__ = [
    "BURROWS_DELTA_MAX",
    "CENTROID_ABS_BACKSTOP",
    "CENTROID_FLOOR_MARGIN",
    "EXPLORATORY_ENCODER_IDS",
    "PRIMARY_ENCODER_IDS",
    "REQUIRED_SEED_COUNT",
    "REQUIRED_SEED_IDS",
    "THROUGHPUT_FLOOR_RATIO",
    "AxisOutcome",
    "AxisResult",
    "ConditionRun",
    "EncoderGate",
    "SeedResult",
    "Verdict",
    "VerdictExperiment",
    "VerdictReport",
    "score_c3b_verdict",
]
