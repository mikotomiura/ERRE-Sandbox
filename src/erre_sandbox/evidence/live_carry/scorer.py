"""Cross-arm live-carry verdict scorer (freeze ADR §1-§7, pure).

A pure function over a sequence of :class:`~.trace_reader.LiveCarryCapture` (the
12-run matrix ``seed x arm{ON,OFF} x replicate{0,1}``). It computes the **four-state
verdict-readiness** the GPU 前 threshold freeze ADR pre-registered:

* **M0** manipulation/fidelity — per-seed ON replicate-0 cross-fp retained-offset
  event count (§6);
* **M1** distal separation — ``S = 1 - Jaccard(floor keys)`` via the frozen
  ``world_model_overlap_jaccard_active`` body, paired ON-OFF vs OFF/OFF null vs
  ON/ON sanity, with the rank-non-overlap + ratio + coverage gate (§1/§2/§3);
* **M2** boundedness/non-inferiority — cap + ``[-1, 1]`` range + coherence/throughput
  non-inferiority (§5);
* routed to ``LIVE_CARRY_TRAJECTORY_EFFECT_CONFIRMED`` / ``NO_DETECTABLE_LIVE_EFFECT``
  / ``INCONCLUSIVE_LOW_POWER`` / ``INVALID_MEASUREMENT`` (§7), all under seed-AND.

What it returns is the **compute path** a later GPU live exec re-scores — *not* a
verdict (no GPU data exists yet). M1 GO (were it to occur on real data) =
behaviour-change existence (a necessary condition), not divergence/core-thesis proof
(GO = Gate B / wall② warrant). The scorer never re-tunes a threshold (all read from
:mod:`.constants`) and never touches the frozen reconcile kernel or the frozen
distance body — it *uses* ``world_model_overlap_jaccard_active`` (re-implementation
forbidden, ADR §1/§9).
"""

from __future__ import annotations

import itertools
import math
import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from erre_sandbox.contracts.cognition_layers import SubjectiveWorldModel
from erre_sandbox.evidence.individuation.layer1 import MetricContext
from erre_sandbox.evidence.individuation.policy import AggregationLevel, MetricStatus
from erre_sandbox.evidence.individuation.world_model_metrics import (
    world_model_overlap_jaccard_active,
)
from erre_sandbox.evidence.live_carry import constants as _c

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.evidence.live_carry.trace_reader import (
        CoherenceRow,
        LiveCarryCapture,
    )
    from erre_sandbox.evidence.saturation.floor_input_trace_ddl import (
        FloorInputTraceRow,
    )
    from erre_sandbox.evidence.saturation.trace_ddl import SaturationTraceRow

# --- verdict labels (ADR §7) --------------------------------------------------

CONFIRMED: Final[str] = "LIVE_CARRY_TRAJECTORY_EFFECT_CONFIRMED"
NO_DETECTABLE: Final[str] = "NO_DETECTABLE_LIVE_EFFECT"
INCONCLUSIVE: Final[str] = "INCONCLUSIVE_LOW_POWER"
INVALID: Final[str] = "INVALID_MEASUREMENT"

_ARMS: Final[tuple[str, str]] = ("on", "off")
_REPLICATES: Final[tuple[int, int]] = (0, 1)
_OFFSET_EPS: Final[float] = 1e-12
"""Below this an offset ``|modulated - base_floor|`` is treated as exactly zero."""

# Thin shim so the frozen ``world_model_overlap_jaccard_active`` body can be *used*
# without re-implementing the Jaccard: only ``.value`` / ``.status`` of its result
# are consumed, so the provenance fields below are inert placeholders, not real
# row identity. The distance is the only thing borrowed (ADR §1, re-impl forbidden).
_DISCARDED_COMPUTED_AT: Final[datetime] = datetime(1970, 1, 1, tzinfo=UTC)
_SHIM_CTX: Final[MetricContext] = MetricContext(
    run_id="live-carry-m1",
    individual_id="live-carry-a|live-carry-b",  # PER_DYAD requires a '|'-joined pair
    base_persona_id="live-carry",
    # The frozen metric registers only PER_DYAD (it is a pairwise SWM distance); the
    # shim must satisfy the MetricResult validator even though only .value/.status
    # are consumed.
    aggregation_level=AggregationLevel.PER_DYAD,
    tick=0,
    source_epoch_phase="live_carry_m1",
    source_individual_layer_enabled=True,
    source_filter_hash="live-carry-m1-shim",
)

_Key = tuple[str, str]
_MatrixKey = tuple[int, str, int]  # (seed, arm, replicate_id)


# --- result types -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RunPairSeparation:
    """One run-pair's distal-separation summary (median S + coverage)."""

    median_separation: float | None
    aligned_tick_pairs: int
    valid_tick_pairs: int


@dataclass(frozen=True, slots=True)
class M1Result:
    """M1 distal-separation gate outcome across the N seeds."""

    go: bool
    coverage_ok: bool
    nulls_complete: bool
    sanity_complete: bool
    rank_non_overlap: bool
    ratio_ok: bool
    on_noise_ok: bool
    s_on_off: tuple[float | None, ...]
    s_off_off_null: tuple[float | None, ...]
    s_on_on_sanity: tuple[float | None, ...]
    coverage_ratios: tuple[float | None, ...]
    valid_tick_pairs: tuple[int, ...]
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class M0Result:
    """M0 engagement gate outcome (per-seed ON r0 retained-offset events)."""

    status: str  # "pass" | "invalid" | "inconclusive"
    events_per_seed: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class M2Result:
    """M2 boundedness + non-inferiority gate outcome."""

    status: str  # "pass" | "invalid"
    range_ok: bool
    cap_ok: bool
    coherence_ok: bool
    throughput_ok: bool
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class LiveCarryResult:
    """The whole cross-arm verdict + component outcomes + provenance summary."""

    verdict: str
    seeds: tuple[int, ...]
    m0: M0Result | None
    m1: M1Result | None
    m2: M2Result | None
    notes: str


# --- floor-key projection + separation (USE the frozen distance) --------------


def _floor_keys(floor_swm_json: str) -> tuple[_Key, ...]:
    """Project a floor ``SubjectiveWorldModel`` JSON into its sorted ``(axis,key)`` set.

    The distal floor (``base_floor``) is the M1 source (``modulated_value`` unused =
    tautology avoidance, ADR §1/§8). De-duplicated + sorted so the key set is stable.
    """
    swm = SubjectiveWorldModel.model_validate_json(floor_swm_json)
    return tuple(sorted({(entry.axis, entry.key) for entry in swm.entries}))


def _separation(keys_a: tuple[_Key, ...], keys_b: tuple[_Key, ...]) -> float | None:
    """``S = 1 - Jaccard`` via the frozen active fn; ``None`` when the union is empty.

    Re-uses ``world_model_overlap_jaccard_active`` (ADR §1, re-impl forbidden). A
    ``DEGENERATE`` result (both floors empty → undefined Jaccard) is **not** valid —
    it is dropped from the coverage numerator (ADR §2/§4(c)), signalled as ``None``.
    """
    result = world_model_overlap_jaccard_active(
        keys_a, keys_b, ctx=_SHIM_CTX, computed_at=_DISCARDED_COMPUTED_AT
    )
    if result.status is MetricStatus.DEGENERATE or result.value is None:
        return None
    return 1.0 - float(result.value)


def _keys_by_tick(
    rows: Sequence[FloorInputTraceRow],
) -> dict[tuple[str, int], tuple[_Key, ...]]:
    """Map ``(individual_id, tick) -> floor (axis,key) set`` for one capture."""
    return {
        (row.individual_id, row.tick): _floor_keys(row.floor_swm_json) for row in rows
    }


def _run_pair_separation(
    a: Sequence[FloorInputTraceRow], b: Sequence[FloorInputTraceRow]
) -> RunPairSeparation:
    """Median S over the matched ``(individual, tick)`` common set of two runs.

    aligned = common ``(individual, tick)`` keys; valid = of those, the pairs whose
    union is non-empty (Jaccard defined). The run-pair value is the **tick median**
    of the valid separations (ADR §1). ``median_separation`` is ``None`` when no
    valid pair exists (the seed routes to coverage / no-valid-null handling).
    """
    keys_a = _keys_by_tick(a)
    keys_b = _keys_by_tick(b)
    aligned = sorted(keys_a.keys() & keys_b.keys())
    valid: list[float] = []
    for tick_key in aligned:
        sep = _separation(keys_a[tick_key], keys_b[tick_key])
        if sep is not None:
            valid.append(sep)
    median = statistics.median(valid) if valid else None
    return RunPairSeparation(
        median_separation=median,
        aligned_tick_pairs=len(aligned),
        valid_tick_pairs=len(valid),
    )


# --- matrix assembly ----------------------------------------------------------


def _assemble_matrix(
    captures: Sequence[LiveCarryCapture],
) -> tuple[dict[_MatrixKey, LiveCarryCapture] | None, tuple[int, ...], str]:
    """Index captures by ``(seed, arm, replicate_id)``; ``None`` on an invalid matrix.

    Returns ``(matrix | None, seeds, note)``. An incomplete matrix (a key missing /
    duplicated / role-swapped, a capture lacking any identity key, or not exactly
    ``N_SEED`` seeds x 2 arms x 2 replicates = 12 runs) yields ``None`` so the caller
    routes ``INVALID_MEASUREMENT`` (ADR §0/§3/§7) — never a crash.
    """
    matrix: dict[_MatrixKey, LiveCarryCapture] = {}
    for cap in captures:
        if cap.seed is None or cap.arm is None or cap.replicate_id is None:
            return (
                None,
                (),
                (
                    f"capture {cap.path} is missing a matrix key (seed={cap.seed},"
                    f" arm={cap.arm}, replicate_id={cap.replicate_id})"
                ),
            )
        if cap.arm not in _ARMS or cap.replicate_id not in _REPLICATES:
            return (
                None,
                (),
                (
                    f"capture {cap.path} has an out-of-domain key"
                    f" (arm={cap.arm}, replicate_id={cap.replicate_id})"
                ),
            )
        key: _MatrixKey = (cap.seed, cap.arm, cap.replicate_id)
        if key in matrix:
            return None, (), f"duplicate matrix key {key} (captures collide)"
        matrix[key] = cap

    seeds = tuple(sorted({k[0] for k in matrix}))
    if len(seeds) != _c.N_SEED:
        return (
            None,
            seeds,
            (f"expected exactly N_SEED={_c.N_SEED} distinct seeds, got {len(seeds)}"),
        )
    for seed in seeds:
        for arm in _ARMS:
            for rep in _REPLICATES:
                if (seed, arm, rep) not in matrix:
                    return (
                        None,
                        seeds,
                        (
                            f"matrix incomplete: missing (seed={seed}, arm={arm},"
                            f" replicate={rep})"
                        ),
                    )
    return matrix, seeds, "matrix complete (12 runs)"


# --- M0 engagement ------------------------------------------------------------


def _retained_offset_events(rows: Sequence[SaturationTraceRow]) -> int:
    """Count cross-fp retained-offset events in one run's saturation trace.

    An event = a tick where a channel ``(individual, axis, key)`` shows a
    floor-fingerprint change vs its previous observed tick **and** carries a non-zero
    offset ``|modulated - base_floor| > 0`` at that tick (the carry survived a churn,
    ADR §6). Mirrors the saturation retained-across-fp semantic (event-count form),
    computed here rather than imported because the ``retained_rate`` denominator/gate
    serve a different purpose.
    """
    by_channel: dict[tuple[str, str, str], list[SaturationTraceRow]] = {}
    for row in rows:
        by_channel.setdefault((row.individual_id, row.axis, row.key), []).append(row)
    events = 0
    for channel_rows in by_channel.values():
        ordered = sorted(channel_rows, key=lambda r: r.tick)
        for prev, cur in itertools.pairwise(ordered):
            fp_changed = cur.floor_fingerprint_hash != prev.floor_fingerprint_hash
            offset = abs(cur.modulated_value - cur.base_floor_value)
            if fp_changed and offset > _OFFSET_EPS:
                events += 1
    return events


def _score_m0(
    matrix: dict[_MatrixKey, LiveCarryCapture], seeds: Sequence[int]
) -> M0Result:
    """Per-seed ON replicate-0 engagement (seed-AND, ADR §6)."""
    events = tuple(
        _retained_offset_events(matrix[(seed, "on", 0)].saturation_rows)
        for seed in seeds
    )
    if any(e == 0 for e in events):
        status = "invalid"  # carry never fired → manipulation absent
    elif any(e < _c.M0_ENGAGEMENT_FLOOR for e in events):
        status = "inconclusive"  # 1..4 → under-engaged
    else:
        status = "pass"
    return M0Result(status=status, events_per_seed=events)


# --- M2 boundedness + non-inferiority -----------------------------------------


def _distinct_ticks(rows: Sequence[FloorInputTraceRow]) -> int:
    """Run length in ticks (the M2 throughput denominator)."""
    return len({row.tick for row in rows})


def _median_coherence(rows: Sequence[CoherenceRow]) -> float | None:
    """Median of the **finite** non-NULL per-tick coherence observations.

    ``None`` when no finite observation exists (the M2 non-inferiority gate is then
    non-evaluable → INVALID, Codex HIGH-3). A non-finite (NaN/inf) score is dropped
    here and separately flagged by :func:`_has_nonfinite_coherence`.
    """
    values = [
        r.coherence_score
        for r in rows
        if r.coherence_score is not None and math.isfinite(r.coherence_score)
    ]
    return statistics.median(values) if values else None


def _has_nonfinite_coherence(rows: Sequence[CoherenceRow]) -> bool:
    """True if any observed coherence score is NaN/inf (a data-integrity violation)."""
    return any(
        r.coherence_score is not None and not math.isfinite(r.coherence_score)
        for r in rows
    )


def _cap_violation(rows: Sequence[SaturationTraceRow]) -> bool:
    """True if any channel breaches the frozen cap beyond a single injection transient.

    ADR §5 caps the steady offset ``|modulated - base_floor|`` at ``M2_CAP`` (0.15) and
    tolerates one ``VALUE_STEP`` (0.05) transient **only at injection**, which the next
    reconcile re-clamps. So an offset in ``(M2_CAP, M2_CAP + M2_TRANSIENT_TOL]`` is
    allowed only if the **next** observed tick of the same channel re-clamps to
    ``<= M2_CAP``; a sustained over-cap (next tick still over cap, or no next tick to
    confirm the re-clamp) and any offset beyond ``M2_CAP + M2_TRANSIENT_TOL`` are
    violations (Codex HIGH-2 — a blanket ``+0.05`` cap would let a sustained 0.18 pass).
    """
    by_channel: dict[tuple[str, str, str], list[SaturationTraceRow]] = {}
    for row in rows:
        by_channel.setdefault((row.individual_id, row.axis, row.key), []).append(row)
    for channel_rows in by_channel.values():
        ordered = sorted(channel_rows, key=lambda r: r.tick)
        for idx, row in enumerate(ordered):
            offset = abs(row.modulated_value - row.base_floor_value)
            if offset > _c.M2_CAP + _c.M2_TRANSIENT_TOL:
                return True  # beyond even a transient injection
            if offset > _c.M2_CAP:
                nxt = ordered[idx + 1] if idx + 1 < len(ordered) else None
                if (
                    nxt is None
                    or abs(nxt.modulated_value - nxt.base_floor_value) > _c.M2_CAP
                ):
                    return True  # sustained over-cap (no confirmed re-clamp)
    return False


def _score_m2(
    matrix: dict[_MatrixKey, LiveCarryCapture], seeds: Sequence[int]
) -> M2Result:
    """Value-range + cap (all runs) + per-seed r0 non-inferiority (seed-AND, ADR §5)."""
    notes: list[str] = []
    range_ok = True
    cap_ok = True
    for cap in matrix.values():
        for row in cap.saturation_rows:
            if not (-1.0 <= row.modulated_value <= 1.0):
                range_ok = False
        if _cap_violation(cap.saturation_rows):
            cap_ok = False

    coherence_ok = True
    throughput_ok = True
    for seed in seeds:
        on_r0 = matrix[(seed, "on", 0)]
        off_r0 = matrix[(seed, "off", 0)]
        # Coherence non-inferiority is a **required** M2 gate (ADR §5): a non-evaluable
        # series (no finite observation) or a non-finite score cannot rule out carry
        # degrading the agent, so it routes INVALID — not skipped (Codex HIGH-3).
        if _has_nonfinite_coherence(on_r0.coherence_rows) or _has_nonfinite_coherence(
            off_r0.coherence_rows
        ):
            coherence_ok = False
            notes.append(f"seed {seed}: non-finite coherence observation → INVALID")
            continue
        coh_on = _median_coherence(on_r0.coherence_rows)
        coh_off = _median_coherence(off_r0.coherence_rows)
        if coh_on is None or coh_off is None:
            coherence_ok = False
            notes.append(
                f"seed {seed}: coherence non-inferiority non-evaluable"
                " (no finite ON r0 / OFF r0 observation) → INVALID"
            )
        elif coh_on < coh_off - _c.M2_COHERENCE_MARGIN:
            coherence_ok = False

        ticks_on = _distinct_ticks(on_r0.floor_rows)
        ticks_off = _distinct_ticks(off_r0.floor_rows)
        if ticks_on < _c.M2_THROUGHPUT_RATIO * ticks_off:
            throughput_ok = False

    status = (
        "pass"
        if (range_ok and cap_ok and coherence_ok and throughput_ok)
        else "invalid"
    )
    return M2Result(
        status=status,
        range_ok=range_ok,
        cap_ok=cap_ok,
        coherence_ok=coherence_ok,
        throughput_ok=throughput_ok,
        notes=tuple(notes),
    )


# --- M1 distal separation -----------------------------------------------------


def _score_m1(
    matrix: dict[_MatrixKey, LiveCarryCapture], seeds: Sequence[int]
) -> M1Result:
    """Paired ON-OFF vs OFF/OFF null vs ON/ON sanity separation gate (ADR §1/§2/§3)."""
    notes: list[str] = []
    on_off: list[float | None] = []
    off_off: list[float | None] = []
    on_on: list[float | None] = []
    coverage_ratios: list[float | None] = []
    valid_counts: list[int] = []

    for seed in seeds:
        primary = _run_pair_separation(
            matrix[(seed, "on", 0)].floor_rows, matrix[(seed, "off", 0)].floor_rows
        )
        null_pair = _run_pair_separation(
            matrix[(seed, "off", 0)].floor_rows, matrix[(seed, "off", 1)].floor_rows
        )
        sanity = _run_pair_separation(
            matrix[(seed, "on", 0)].floor_rows, matrix[(seed, "on", 1)].floor_rows
        )
        on_off.append(primary.median_separation)
        off_off.append(null_pair.median_separation)
        on_on.append(sanity.median_separation)
        ratio = (
            primary.valid_tick_pairs / primary.aligned_tick_pairs
            if primary.aligned_tick_pairs > 0
            else None
        )
        coverage_ratios.append(ratio)
        valid_counts.append(primary.valid_tick_pairs)

    # coverage前提 (HIGH-1): per seed, ratio >= COVERAGE_MIN ∧ valid >= MIN_TICK_PAIRS
    coverage_ok = all(
        r is not None and r >= _c.COVERAGE_MIN and v >= _c.MIN_TICK_PAIRS
        for r, v in zip(coverage_ratios, valid_counts, strict=True)
    )
    if not coverage_ok:
        notes.append(
            "coverage前提 unmet (ratio < COVERAGE_MIN or valid < MIN_TICK_PAIRS)"
        )

    valid_nulls = [s for s in off_off if s is not None]
    valid_on_off = [s for s in on_off if s is not None]
    valid_on_on = [s for s in on_on if s is not None]

    # ADR §2 is a strict 3-vs-3 descriptive comparison + an ON/ON sanity null over all
    # seeds. A *partial* null or sanity substrate (a degenerate run-pair on some seed)
    # cannot support the rank/sanity claim, so it routes INCONCLUSIVE — never CONFIRMED
    # / NO_DETECTABLE (Codex HIGH-1). ``on_noise_ok`` therefore defaults False (a
    # missing sanity is not a silent pass).
    on_off_complete = len(valid_on_off) == _c.N_SEED
    nulls_complete = len(valid_nulls) == _c.N_SEED
    sanity_complete = len(valid_on_on) == _c.N_SEED

    rank_non_overlap = False
    ratio_ok = False
    on_noise_ok = False
    if not nulls_complete:
        notes.append("OFF/OFF null incomplete (need N_SEED valid) → INCONCLUSIVE")
    if not sanity_complete:
        notes.append("ON/ON sanity incomplete (need N_SEED valid) → INCONCLUSIVE")
    if not on_off_complete:
        notes.append("a primary ON-OFF pair has no valid separation → INCONCLUSIVE")

    if on_off_complete and nulls_complete:
        max_null = max(valid_nulls)
        rank_non_overlap = min(valid_on_off) > max_null
        median_on_off = statistics.median(valid_on_off)
        if max_null == 0.0:
            ratio_ok = (
                median_on_off >= _c.DEGENERATE_NULL_FLOOR
            )  # all-zero null → floor
        else:
            ratio_ok = (median_on_off / max_null) >= _c.R_MIN

    if sanity_complete and nulls_complete:
        on_noise_ok = max(valid_on_on) <= _c.ON_NOISE_FACTOR * max(valid_nulls)
        if not on_noise_ok:
            notes.append("ON/ON sanity FAIL (ON-specific noise suspected)")

    go = (
        coverage_ok
        and on_off_complete
        and nulls_complete
        and sanity_complete
        and rank_non_overlap
        and ratio_ok
        and on_noise_ok
    )
    return M1Result(
        go=go,
        coverage_ok=coverage_ok,
        nulls_complete=nulls_complete,
        sanity_complete=sanity_complete,
        rank_non_overlap=rank_non_overlap,
        ratio_ok=ratio_ok,
        on_noise_ok=on_noise_ok,
        s_on_off=tuple(on_off),
        s_off_off_null=tuple(off_off),
        s_on_on_sanity=tuple(on_on),
        coverage_ratios=tuple(coverage_ratios),
        valid_tick_pairs=tuple(valid_counts),
        notes=tuple(notes),
    )


# --- verdict routing (ADR §7) -------------------------------------------------


def score_live_carry(captures: Sequence[LiveCarryCapture]) -> LiveCarryResult:
    """Route the 12-run matrix to the four-state verdict-readiness (seed-AND, ADR §7).

    Precedence: an invalid measurement (matrix gap / M0 zero-engagement / M2 cap or
    range or non-inferiority violation) beats everything; under-power (M0 1..4 /
    M1 coverage / no-valid-null / ON-noise / N mismatch) beats a substantive call;
    a clean M0+M2 with M1 GO is CONFIRMED, with M1 FAIL on adequate coverage is
    NO_DETECTABLE. What this produces is verdict-*readiness*, not a verdict.
    """
    matrix, seeds, matrix_note = _assemble_matrix(captures)
    if matrix is None:
        return LiveCarryResult(
            verdict=INVALID,
            seeds=seeds,
            m0=None,
            m1=None,
            m2=None,
            notes=matrix_note,
        )

    m0 = _score_m0(matrix, seeds)
    m2 = _score_m2(matrix, seeds)
    m1 = _score_m1(matrix, seeds)
    notes_parts = [matrix_note, *m2.notes, *m1.notes]

    # INVALID_MEASUREMENT — M0 zero-engagement or any M2 hard violation.
    if m0.status == "invalid":
        verdict = INVALID
        notes_parts.append("M0 engagement 0 (manipulation absent)")
    elif m2.status == "invalid":
        verdict = INVALID
        notes_parts.append("M2 violation (range / cap / non-inferiority)")
    # INCONCLUSIVE_LOW_POWER — under-engaged or under-powered M1.
    elif m0.status == "inconclusive":
        verdict = INCONCLUSIVE
        notes_parts.append("M0 engagement 1..4 (under-engaged)")
    elif (
        not m1.coverage_ok
        or not m1.nulls_complete
        or not m1.sanity_complete
        or not m1.on_noise_ok
    ):
        verdict = INCONCLUSIVE
    # Substantive calls — M0 PASS ∧ M2 PASS.
    elif m1.go:
        verdict = CONFIRMED
        notes_parts.append(
            "M1 GO (bounded distal separation; necessary condition only)"
        )
    else:
        verdict = NO_DETECTABLE
        notes_parts.append("M1 FAIL on adequate coverage (no detectable separation)")

    return LiveCarryResult(
        verdict=verdict,
        seeds=seeds,
        m0=m0,
        m1=m1,
        m2=m2,
        notes="; ".join(p for p in notes_parts if p),
    )


__all__ = [
    "CONFIRMED",
    "INCONCLUSIVE",
    "INVALID",
    "NO_DETECTABLE",
    "LiveCarryResult",
    "M0Result",
    "M1Result",
    "M2Result",
    "RunPairSeparation",
    "score_live_carry",
]
