"""Loader + pure scorer for the bond-affinity near-miss diagnostic (ADR section 3.4).

Two halves, both touching only the bond-affinity trace (and the saturation trace it
joins against for cap exposure):

* :func:`read_bond_affinity_trace_rows` — a plain typed reader over the metrics trace.
  No ``raw_dialog`` egress guard (it is an internal ``metrics -> analysis`` read), and
  the qualified name is composed from ``METRICS_SCHEMA`` (never a schema-dot literal; CI
  grep gate). Nullable recency columns deserialise to ``int | None`` / ``str | None``.
* :func:`score_bond_affinity` — a pure function implementing the **v2 signal-to-noise**
  decision layer the freeze ADR pre-registered
  (``.steering/20260617-bond-affinity-diagnostic-freeze/threshold-freeze-adr.md`` §1-§3,
  ACCEPTED 2026-06-17, binding=user). It recomputes the near-miss gate
  (``|affinity| < BELIEF_THRESHOLD`` ∧ ``ichigo_ichie_count >= MIN_INTERACTIONS``) from
  raw rows, joins each near-miss bond to its tick's cap-saturation exposure, applies the
  stale-bond guard (ADR HIGH-1), folds each ``(seed, arm, replicate)`` cell's near-miss
  population into a proximity statistic (the **p95 |affinity|**), and routes the
  cross-arm verdict by contrasting the ON-OFF separation against the same-arm
  run-to-run noise floor — **non-circular**, unlike the PR #25 single-shot absolute
  margin (which never compared the ON-OFF gap to any noise; circular, freeze ADR §0).

The v2 layer ports the III-a live §5.3 null-hierarchy structure
(:mod:`erre_sandbox.evidence.live_carry.scorer`): a per-seed ``S(ON-OFF)`` cross-arm
signal, an ``S(OFF/OFF)`` run-to-run noise floor, and an ``S(ON/ON)`` ON-specific
sanity null, gated by a materiality floor + ratio (degenerate-null aware, HIGH-2),
rank-non-overlap, and a 4-replicate-cell power gate (MED-1). The numeric thresholds are
now **frozen** (freeze ADR §1) — imported from :mod:`.constants` as the defaults of the
keyword parameters; a caller overrides only for unit tests. The descriptive half
(near-miss identification, the stale guard, the signed trust/clash split, the per-cell
report statistics) is unchanged from PR #25.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import TYPE_CHECKING, Final, Literal

from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.relational.bond_affinity_trace_ddl import (
    TABLE_NAME,
    BondAffinityTraceRow,
    column_names,
)
from erre_sandbox.evidence.relational.constants import (
    BELIEF_MIN_INTERACTIONS,
    BELIEF_THRESHOLD,
    CAP_OFFSET,
    CAP_SATURATION_TOL,
    DEGENERATE_GAP_FLOOR,
    EPS_BAND_LO,
    MIN_NEAR_MISS_N,
    MIN_PAIRED_SEEDS,
    ON_NOISE_FACTOR,
    R_MIN_BOND,
    SLOPE_WINDOW,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    import duckdb

    from erre_sandbox.evidence.saturation.trace_ddl import SaturationTraceRow

Verdict = Literal[
    "(i)-LEANING",
    "(ii)-LEANING",
    "INCONCLUSIVE_MIXED_SEED",
    "INCONCLUSIVE_LOW_POWER",
    "INCONCLUSIVE_NO_NEAR_MISS",
    "INVALID_MEASUREMENT",
]
"""The six closed verdict states (freeze ADR §3 routing, all states reachable).

``(i)-LEANING`` = cap-binding suggested (ON pushes near-miss bonds closer to the 0.45
gate than OFF, above the noise floor) → warrants a cap-relax GO/NO-GO **in a separate
ADR** (this scorer does not authorise cap variation). ``(ii)-LEANING`` = no differential
approach above the noise floor (lowers fork (C) VoI; *not* a decoupling proof, ADR
MED-2). ``INCONCLUSIVE_MIXED_SEED`` = the median separation clears magnitude but a
per-seed signal sinks into the noise (seed reproducibility absent, HIGH-1).
``INCONCLUSIVE_LOW_POWER`` = under-powered (a replicate cell below the near-miss floor,
too few paired seeds, or ON-specific noise). ``INCONCLUSIVE_NO_NEAR_MISS`` = the
diagnostic substrate is empty. ``INVALID_MEASUREMENT`` = a provenance-false row (freeze
ADR §7: PR #25 returned INCONCLUSIVE here, v2 raises it to INVALID)."""

I_LEANING: Final[str] = "(i)-LEANING"
II_LEANING: Final[str] = "(ii)-LEANING"
INCONCLUSIVE_MIXED_SEED: Final[str] = "INCONCLUSIVE_MIXED_SEED"
INCONCLUSIVE_LOW_POWER: Final[str] = "INCONCLUSIVE_LOW_POWER"
INCONCLUSIVE_NO_NEAR_MISS: Final[str] = "INCONCLUSIVE_NO_NEAR_MISS"
INVALID_MEASUREMENT: Final[str] = "INVALID_MEASUREMENT"

_ARM_ON: Final[str] = "ON"
_ARM_OFF: Final[str] = "OFF"

_OLS_MIN_POINTS: Final[int] = 2


def _ols_slope(xs: Sequence[int], ys: Sequence[float]) -> float:
    """Ordinary-least-squares slope of *ys* on *xs* (0.0 when undefined)."""
    n = len(xs)
    if n < _OLS_MIN_POINTS:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    den = sum((x - mean_x) ** 2 for x in xs)
    # ``den`` is a non-negative sum of squares; it is 0 only when every x is equal
    # (a 1-tick window, already excluded above, or duplicate ticks). ``<= 0.0`` keeps
    # the guard robust without a spurious epsilon on the well-separated integer ticks.
    if den <= 0.0:
        return 0.0
    return num / den


def _percentile(values: Sequence[float], q: float) -> float | None:
    """Linear-interpolation percentile (*q* in [0, 1]); ``None`` for empty input."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = q * (len(ordered) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * frac


@dataclass(frozen=True, slots=True)
class NearMissObservation:
    """One near-miss bond row that passed the gate + stale guard (ADR section 3.4)."""

    run_id: str
    seed: int
    individual_id: str
    other_agent_id: str
    tick: int
    affinity: float
    abs_affinity: float
    touched_this_tick: bool
    lagged_slope: float
    under_individual_exposure: bool
    entry_exposure_count: int
    """#saturation entries at cap for this ``(run, seed, individual, tick)`` — the
    entry-linked exposure resolution (ADR MED-3), kept as a count (not a bool) so the
    read side can weight individual-level vs entry-linked exposure."""


@dataclass(frozen=True, slots=True)
class CellStats:
    """Per ``(seed, arm, replicate)`` near-miss distribution (ADR §3 report unit).

    The proximity statistic the verdict uses is :attr:`p95_abs` (the p95 ``|affinity|``
    of this cell's near-miss population); the rest are the ADR §3 / LOW-1 mandatory
    report so the verdict never rests on a single statistic.
    """

    seed: int
    arm: str  # "ON" | "OFF"
    replicate: int  # 0 | 1
    n: int
    unique_dyads: int
    p90_abs: float | None
    p95_abs: float | None
    max_abs: float | None
    eps_band_density: float | None
    n_trust: int
    n_clash: int
    n_neutral: int
    """near-miss bonds with ``affinity == 0.0`` (neither trust nor clash). Kept so the
    invariant ``n_trust + n_clash + n_neutral == n`` holds (Codex/CR HIGH-1)."""


@dataclass(frozen=True, slots=True)
class BondAffinityProbeResult:
    """Cross-arm verdict + per-cell distributions + the v2 null-hierarchy quantities.

    The reportable diagnostic outcome. ``cells`` is the ADR §3 mandatory report (every
    ``(seed, arm, replicate)`` cell). The ``s_*`` maps (per paired seed) and the
    ``*_ok`` flags expose the non-circular decision path so no single statistic is
    opaque (LOW-1).
    """

    verdict: Verdict
    cells: tuple[CellStats, ...] = ()
    paired_seeds: tuple[int, ...] = ()
    s_on_off: dict[int, float] = field(default_factory=dict)
    """per paired seed: ``p95(ON r0) - p95(OFF r0)`` (signed cross-arm signal)."""
    s_off_off_null: dict[int, float] = field(default_factory=dict)
    """per paired seed: ``|p95(OFF r0) - p95(OFF r1)|`` (run-to-run noise floor)."""
    s_on_on_null: dict[int, float] = field(default_factory=dict)
    """per paired seed: ``|p95(ON r0) - p95(ON r1)|`` (ON-specific noise sanity)."""
    median_s_on_off: float | None = None
    max_off_off_null: float | None = None
    max_on_on_null: float | None = None
    magnitude_ok: bool = False
    rank_ok: bool = False
    on_noise_ok: bool = False
    null_degenerate: bool = False
    notes: str = ""


_ExposureKey = tuple[str, int, str, int]
"""``(run_id, seed, individual_id, tick)`` — the cap-exposure join identity.

Keyed by ``run_id`` **and** ``seed`` (not just ``(individual, tick)``) so a cap
exposure in one arm / seed never leaks into another: paired ON/OFF runs share
``(individual, tick)`` keys, so a coarser key would let an OFF near-miss bond inherit
the ON arm's exposure (Codex HIGH / CR MED-3)."""


def _cap_saturated_entry_count(
    saturation_rows: Sequence[SaturationTraceRow],
) -> dict[_ExposureKey, int]:
    """``(run_id, seed, individual_id, tick) -> #entries at cap`` (ADR MED-3).

    Per-``(run, seed, individual, tick)`` count of saturation entries sitting at the
    cap. The entry-linked resolution (count) and the individual-level exposure
    (count > 0) are both derived from this single map, keyed so exposure never crosses
    arm / seed boundaries.
    """
    threshold = CAP_OFFSET - CAP_SATURATION_TOL
    counts: dict[_ExposureKey, int] = {}
    for r in saturation_rows:
        if abs(r.modulated_value - r.base_floor_value) >= threshold:
            key = (r.run_id, r.seed, r.individual_id, r.tick)
            counts[key] = counts.get(key, 0) + 1
    return counts


_Dyad = tuple[str, int, str, str]
"""``(run_id, seed, individual_id, other_agent_id)`` — the affinity-series identity."""


def _dyad_series(
    bond_rows: Sequence[BondAffinityTraceRow],
) -> dict[_Dyad, list[tuple[int, float]]]:
    """Group rows into per-dyad ``[(tick, affinity), ...]`` sorted by tick."""
    series: dict[_Dyad, list[tuple[int, float]]] = {}
    for r in bond_rows:
        key = (r.run_id, r.seed, r.individual_id, r.other_agent_id)
        series.setdefault(key, []).append((r.tick, r.affinity))
    for pts in series.values():
        pts.sort(key=lambda p: p[0])
    return series


def identify_near_miss(
    bond_rows: Sequence[BondAffinityTraceRow],
    saturation_rows: Sequence[SaturationTraceRow],
    *,
    require_exposure: bool = True,
    require_fresh: bool = True,
    slope_window: int = SLOPE_WINDOW,
) -> list[NearMissObservation]:
    """Identify near-miss bonds under cap exposure, applying the stale guard (pure).

    near-miss = ``ichigo_ichie_count >= BELIEF_MIN_INTERACTIONS`` ∧
    ``|affinity| < BELIEF_THRESHOLD`` (gate recomputed here, not baked at capture).
    *require_exposure* keeps only bonds whose ``(run, seed, individual, tick)`` has a
    cap-saturated saturation entry — the exposure key includes ``run_id`` / ``seed`` so
    no exposure leaks across arms or seeds (Codex HIGH / CR MED-3). *require_fresh*
    applies the ADR HIGH-1 stale guard: keep only a bond touched this tick
    (``last_interaction_tick == tick``) or whose **|affinity|** rose into the tick
    (lagged slope > 0 over the last *slope_window* ticks) — a bond parked near 0.45 from
    before the exposure is excluded so it cannot fake an (i)-leaning approach. The slope
    is over ``|affinity|`` (not signed), so a clash bond moving ``-0.30 -> -0.44`` (i.e.
    approaching the gate in magnitude) reads as rising (Codex MED-1 / CR MED-4).
    """
    entry_counts = _cap_saturated_entry_count(saturation_rows)
    series = _dyad_series(bond_rows)
    out: list[NearMissObservation] = []
    for r in bond_rows:
        if r.ichigo_ichie_count < BELIEF_MIN_INTERACTIONS:
            continue
        abs_aff = abs(r.affinity)
        if abs_aff >= BELIEF_THRESHOLD:
            continue
        exposure_key = (r.run_id, r.seed, r.individual_id, r.tick)
        entry_count = entry_counts.get(exposure_key, 0)
        under_individual = entry_count > 0
        if require_exposure and not under_individual:
            continue
        touched = r.last_interaction_tick == r.tick
        dyad = (r.run_id, r.seed, r.individual_id, r.other_agent_id)
        window = [
            (t, a) for t, a in series[dyad] if r.tick - slope_window <= t <= r.tick
        ]
        slope = _ols_slope([t for t, _ in window], [abs(a) for _, a in window])
        fresh = touched or slope > 0.0
        if require_fresh and not fresh:
            continue
        out.append(
            NearMissObservation(
                run_id=r.run_id,
                seed=r.seed,
                individual_id=r.individual_id,
                other_agent_id=r.other_agent_id,
                tick=r.tick,
                affinity=r.affinity,
                abs_affinity=abs_aff,
                touched_this_tick=touched,
                lagged_slope=slope,
                under_individual_exposure=under_individual,
                entry_exposure_count=entry_count,
            )
        )
    return out


def has_eligible_near_miss(
    bond_rows: Sequence[BondAffinityTraceRow],
    saturation_rows: Sequence[SaturationTraceRow],
    *,
    slope_window: int = SLOPE_WINDOW,
) -> bool:
    """Phase 0 preflight (freeze ADR §5): is there >= 1 diagnostic-eligible near-miss?

    A single condition over :func:`identify_near_miss` with both gates on
    (``require_exposure`` ∧ ``require_fresh``) — raw near-miss presence and the
    cap-exposure join are checked **together**, not separately (instrumentation ADR
    MED-2). A future smoke audit calls this on a sufficient-horizon flag-on capture
    before committing to the 12-run GPU matrix: an empty result on an adequate-horizon
    smoke routes ``INCONCLUSIVE_NO_NEAR_MISS`` (capture cannot discriminate), stopping
    the GPU investment early. A short-horizon empty is **not** a stop signal — the smoke
    must satisfy the live §5.3 horizon convention first (the caller's responsibility).

    A provenance-false capture is **not** eligible (returns ``False``): an
    ``individual_layer_enabled=False`` row means the smoke was misconfigured (flag-off),
    so it cannot supply a valid diagnostic substrate — proceeding to the 12-run would be
    wrong (review LOW-1; the full scorer routes the same row to INVALID_MEASUREMENT).
    """
    if any(not r.individual_layer_enabled for r in bond_rows) or any(
        not r.individual_layer_enabled for r in saturation_rows
    ):
        return False
    return bool(
        identify_near_miss(
            bond_rows,
            saturation_rows,
            require_exposure=True,
            require_fresh=True,
            slope_window=slope_window,
        )
    )


def _cell_stats(
    seed: int, arm: str, replicate: int, obs: Sequence[NearMissObservation]
) -> CellStats:
    """Fold one ``(seed, arm, replicate)`` cell's near-miss obs into the report unit.

    The statistical computation (p95 / p90 / max / ε-band density / signed split) is
    unchanged from PR #25's per-arm fold — only the grouping key is finer (per replicate
    cell, freeze ADR §2 / MED-1).
    """
    abs_vals = [o.abs_affinity for o in obs]
    dyads = {(o.individual_id, o.other_agent_id) for o in obs}
    n_band = sum(1 for v in abs_vals if EPS_BAND_LO <= v < BELIEF_THRESHOLD)
    return CellStats(
        seed=seed,
        arm=arm,
        replicate=replicate,
        n=len(obs),
        unique_dyads=len(dyads),
        p90_abs=_percentile(abs_vals, 0.90),
        p95_abs=_percentile(abs_vals, 0.95),
        max_abs=max(abs_vals) if abs_vals else None,
        eps_band_density=(n_band / len(abs_vals)) if abs_vals else None,
        n_trust=sum(1 for o in obs if o.affinity > 0.0),
        n_clash=sum(1 for o in obs if o.affinity < 0.0),
        n_neutral=sum(1 for o in obs if o.affinity == 0.0),
    )


_CellKey = tuple[int, str, int]  # (seed, arm, replicate)


def _assemble_cells(
    bond_rows: Sequence[BondAffinityTraceRow],
    saturation_rows: Sequence[SaturationTraceRow],
    *,
    arm_of: Mapping[str, str],
    replicate_of: Mapping[str, int],
) -> dict[_CellKey, CellStats]:
    """Group near-miss observations by ``(seed, arm, replicate)`` and fold each cell.

    A row is placed by ``arm_of[run_id]`` / ``replicate_of[run_id]`` (the caller
    assembles the matrix from the capture sidecars, mirroring the live-carry bundle
    assembler — the trace itself is arm/replicate-blind, ADR §3.2-5). A row whose
    ``run_id`` is absent from either map, or whose arm is not ON/OFF, is dropped (it
    cannot be placed in the matrix). The near-miss identification per cell is identical
    to the per-arm fold because :func:`identify_near_miss` keys its dyad series and
    exposure join by ``(run_id, seed, ...)`` — grouping never changes which bonds count.
    """
    rows_by_cell: dict[_CellKey, list[BondAffinityTraceRow]] = {}
    for r in bond_rows:
        arm = arm_of.get(r.run_id)
        replicate = replicate_of.get(r.run_id)
        if arm not in (_ARM_ON, _ARM_OFF) or replicate is None:
            continue
        rows_by_cell.setdefault((r.seed, arm, replicate), []).append(r)
    cells: dict[_CellKey, CellStats] = {}
    for (seed, arm, replicate), cell_rows in rows_by_cell.items():
        obs = identify_near_miss(cell_rows, saturation_rows)
        cells[(seed, arm, replicate)] = _cell_stats(seed, arm, replicate, obs)
    return cells


def _proximity(cells: Mapping[_CellKey, CellStats], key: _CellKey) -> float | None:
    """The cell's p95 ``|affinity|`` proximity statistic (``None`` if cell absent)."""
    cell = cells.get(key)
    return None if cell is None else cell.p95_abs


def _route_paired_verdict(
    cell_tuple: tuple[CellStats, ...],
    cells: Mapping[_CellKey, CellStats],
    paired: Sequence[int],
) -> BondAffinityProbeResult:
    """Build the per-seed null hierarchy over the paired seeds and route the verdict.

    Split out of :func:`score_bond_affinity` so each half stays within the project's
    branch-complexity budget. The caller guarantees every paired seed has all four
    powered cells, so each ``_proximity`` is defined (the ``None`` skip is defensive).
    All thresholds are the frozen freeze-ADR §1 constants (single source, no override).
    """
    s_on_off: dict[int, float] = {}
    s_off_off: dict[int, float] = {}
    s_on_on: dict[int, float] = {}
    for seed in paired:
        p_on0 = _proximity(cells, (seed, _ARM_ON, 0))
        p_off0 = _proximity(cells, (seed, _ARM_OFF, 0))
        p_off1 = _proximity(cells, (seed, _ARM_OFF, 1))
        p_on1 = _proximity(cells, (seed, _ARM_ON, 1))
        if p_on0 is None or p_off0 is None or p_off1 is None or p_on1 is None:
            continue
        s_on_off[seed] = p_on0 - p_off0
        s_off_off[seed] = abs(p_off0 - p_off1)
        s_on_on[seed] = abs(p_on0 - p_on1)

    max_off_off = max(s_off_off.values())
    max_on_on = max(s_on_on.values())
    median_on_off = median(s_on_off.values())

    # ON-noise sanity — ON-specific run-to-run noise must not exceed the OFF/OFF floor
    # by more than the factor (else the ON arm may fabricate separation, ADR §3).
    on_noise_ok = max_on_on <= ON_NOISE_FACTOR * max_off_off

    # magnitude — materiality floor always; ratio only when the null is non-degenerate
    # (a near-zero OFF/OFF floor makes the ratio blow up, HIGH-2 — fall back to floor).
    null_degenerate = max_off_off < DEGENERATE_GAP_FLOOR / R_MIN_BOND
    materiality_ok = median_on_off >= DEGENERATE_GAP_FLOOR
    if null_degenerate:
        magnitude_ok = materiality_ok
    else:
        magnitude_ok = materiality_ok and (median_on_off / max_off_off) >= R_MIN_BOND

    # rank-non-overlap — the weakest per-seed signal must clear the strongest noise.
    rank_ok = min(s_on_off.values()) > max_off_off

    # Route (freeze ADR §3, evaluation order = power -> ON-noise -> magnitude -> rank).
    verdict: Verdict
    if not on_noise_ok:
        verdict = "INCONCLUSIVE_LOW_POWER"
        notes = (
            f"ON/ON noise {max_on_on:.4f} > {ON_NOISE_FACTOR} * OFF/OFF "
            f"floor {max_off_off:.4f} (ON-specific noise suspected)"
        )
    elif not magnitude_ok:
        verdict = "(ii)-LEANING"
        notes = (
            f"no differential approach above noise: median S(ON-OFF)="
            f"{median_on_off:.4f}, OFF/OFF floor={max_off_off:.4f}, "
            f"degenerate={null_degenerate} (lowers fork (C) VoI, not decoupling)"
        )
    elif not rank_ok:
        verdict = "INCONCLUSIVE_MIXED_SEED"
        notes = (
            f"magnitude met (median S(ON-OFF)={median_on_off:.4f}) but min per-seed "
            f"signal {min(s_on_off.values()):.4f} <= OFF/OFF floor "
            f"{max_off_off:.4f} (seed reproducibility absent)"
        )
    else:
        verdict = "(i)-LEANING"
        notes = (
            f"differential approach above noise: median S(ON-OFF)={median_on_off:.4f} "
            f"/ OFF/OFF floor={max_off_off:.4f} >= r_min={R_MIN_BOND} (or degenerate "
            f"floor); rank-non-overlap holds; {len(paired)} paired seed(s)"
        )

    return BondAffinityProbeResult(
        verdict=verdict,
        cells=cell_tuple,
        paired_seeds=tuple(paired),
        s_on_off=s_on_off,
        s_off_off_null=s_off_off,
        s_on_on_null=s_on_on,
        median_s_on_off=median_on_off,
        max_off_off_null=max_off_off,
        max_on_on_null=max_on_on,
        magnitude_ok=magnitude_ok,
        rank_ok=rank_ok,
        on_noise_ok=on_noise_ok,
        null_degenerate=null_degenerate,
        notes=notes,
    )


def score_bond_affinity(
    bond_rows: Sequence[BondAffinityTraceRow],
    saturation_rows: Sequence[SaturationTraceRow],
    *,
    arm_of: Mapping[str, str],
    replicate_of: Mapping[str, int],
) -> BondAffinityProbeResult:
    """Score the bond-affinity trace into the v2 non-circular cross-arm verdict (§3).

    *arm_of* / *replicate_of* map each ``run_id`` to ``"ON"``/``"OFF"`` and to its
    replicate index ``0``/``1`` (the caller assembles the paired arms + replicates from
    the capture sidecars, mirroring the live-carry bundle assembler — the trace itself
    is arm/replicate-blind, ADR §3.2-5).

    The proximity statistic per ``(seed, arm, replicate)`` cell is the **p95
    |affinity|** of its near-miss population (robust to a single outlier dyad, ADR
    MED-1). Per paired seed the scorer forms a cross-arm signal
    ``S(ON-OFF) = p95(ON r0) - p95(OFF r0)``,
    a run-to-run noise floor ``S(OFF/OFF) = |p95(OFF r0) - p95(OFF r1)|``, and an
    ON-specific sanity null ``S(ON/ON) = |p95(ON r0) - p95(ON r1)|``. The verdict is
    routed (freeze ADR §3, all states closed) by, in order:

    * provenance-false row → ``INVALID_MEASUREMENT`` (freeze ADR §7);
    * no eligible near-miss anywhere → ``INCONCLUSIVE_NO_NEAR_MISS``; but eligible
      near-miss that **exist yet land in no cell** (every run absent from the maps = a
      broken assembly, not an empty substrate) → ``INVALID_MEASUREMENT`` (MED-2);
    * power gate — a *paired seed* has all four cells (ON r0 / OFF r0 / OFF r1 / ON r1)
      with ``>= MIN_NEAR_MISS_N`` near-misses; fewer than ``MIN_PAIRED_SEEDS`` paired →
      ``INCONCLUSIVE_LOW_POWER`` (MED-1 / MED-3, 2-of-3 dropout-tolerant);
    * ON-noise sanity — ``max S(ON/ON) <= ON_NOISE_FACTOR * max S(OFF/OFF)`` else
      ``INCONCLUSIVE_LOW_POWER``;
    * magnitude — a materiality floor ``median S(ON-OFF) >= DEGENERATE_GAP_FLOOR``
      always, plus (when the null is non-degenerate) a ratio
      ``median S(ON-OFF) / max S(OFF/OFF) >= R_MIN_BOND``; a degenerate null
      (``max S(OFF/OFF) < DEGENERATE_GAP_FLOOR / R_MIN_BOND``, near-zero included) needs
      only the floor (HIGH-2 — no near-zero ratio blow-up). Unmet → ``(ii)-LEANING``;
    * rank-non-overlap — ``min S(ON-OFF) > max S(OFF/OFF)``; magnitude met but rank
      failed → ``INCONCLUSIVE_MIXED_SEED`` (HIGH-1); both met → ``(i)-LEANING``.

    All thresholds are the frozen freeze-ADR §1 constants (:mod:`.constants`, single
    source); they are not parameters — changing one needs a superseding ADR.
    """
    if any(not r.individual_layer_enabled for r in bond_rows) or any(
        not r.individual_layer_enabled for r in saturation_rows
    ):
        return BondAffinityProbeResult(
            verdict="INVALID_MEASUREMENT",
            notes="provenance_false (a row carries individual_layer_enabled=False)",
        )

    cells = _assemble_cells(
        bond_rows, saturation_rows, arm_of=arm_of, replicate_of=replicate_of
    )
    cell_tuple = tuple(cells[k] for k in sorted(cells))

    if sum(c.n for c in cell_tuple) == 0:
        # Distinguish a genuinely empty substrate from a broken assembly (Codex MED-2):
        # if eligible near-miss exist over the raw rows but none landed in a cell, every
        # run is unmapped (arm_of/replicate_of incomplete) — that is an INVALID matrix,
        # not "no near-miss". A truly empty substrate (raw eligible 0) is NO_NEAR_MISS.
        if has_eligible_near_miss(bond_rows, saturation_rows):
            return BondAffinityProbeResult(
                verdict="INVALID_MEASUREMENT",
                cells=cell_tuple,
                notes=(
                    "eligible near-miss exist but none mapped to a cell "
                    "(arm_of/replicate_of incomplete — broken matrix assembly)"
                ),
            )
        return BondAffinityProbeResult(
            verdict="INCONCLUSIVE_NO_NEAR_MISS",
            cells=cell_tuple,
            notes="no eligible near-miss observation in any cell",
        )

    # power gate — a paired seed has all four replicate cells over the near-miss floor.
    seeds = sorted({c.seed for c in cell_tuple})
    paired: list[int] = []
    for seed in seeds:
        quad = (
            cells.get((seed, _ARM_ON, 0)),
            cells.get((seed, _ARM_OFF, 0)),
            cells.get((seed, _ARM_OFF, 1)),
            cells.get((seed, _ARM_ON, 1)),
        )
        if all(c is not None and c.n >= MIN_NEAR_MISS_N for c in quad):
            paired.append(seed)

    if len(paired) < MIN_PAIRED_SEEDS:
        return BondAffinityProbeResult(
            verdict="INCONCLUSIVE_LOW_POWER",
            cells=cell_tuple,
            paired_seeds=tuple(paired),
            notes=(
                f"low power: {len(paired)} paired seed(s) "
                f"(4 cells each >= {MIN_NEAR_MISS_N}) < floor {MIN_PAIRED_SEEDS}"
            ),
        )

    return _route_paired_verdict(cell_tuple, cells, paired)


def read_bond_affinity_trace_rows(
    con: duckdb.DuckDBPyConnection,
    *,
    schema: str = METRICS_SCHEMA,
    table: str = TABLE_NAME,
) -> list[BondAffinityTraceRow]:
    """Read all bond-affinity trace rows from *con* into typed rows (column-lockstep).

    Plain ``SELECT`` over the metrics trace — no ``raw_dialog`` egress guard. The SELECT
    column list is :func:`column_names` so it stays in lockstep with the DDL, and the
    qualified table name is composed from *schema* (``METRICS_SCHEMA`` by default) so no
    schema-dot literal appears here. The nullable recency columns deserialise to
    ``int | None`` / ``str | None``.
    """
    cols = column_names()
    columns_sql = ", ".join(f'"{c}"' for c in cols)
    select_sql = f"SELECT {columns_sql} FROM {schema}.{table}"  # noqa: S608 — static identifiers only
    result = con.execute(select_sql).fetchall()
    return [
        BondAffinityTraceRow(
            run_id=str(row[0]),
            seed=int(row[1]),
            individual_id=str(row[2]),
            other_agent_id=str(row[3]),
            tick=int(row[4]),
            affinity=float(row[5]),
            ichigo_ichie_count=int(row[6]),
            last_interaction_tick=None if row[7] is None else int(row[7]),
            last_interaction_zone=None if row[8] is None else str(row[8]),
            individual_layer_enabled=bool(row[9]),
        )
        for row in result
    ]


__all__ = [
    "II_LEANING",
    "INCONCLUSIVE_LOW_POWER",
    "INCONCLUSIVE_MIXED_SEED",
    "INCONCLUSIVE_NO_NEAR_MISS",
    "INVALID_MEASUREMENT",
    "I_LEANING",
    "BondAffinityProbeResult",
    "CellStats",
    "NearMissObservation",
    "has_eligible_near_miss",
    "identify_near_miss",
    "read_bond_affinity_trace_rows",
    "score_bond_affinity",
]
