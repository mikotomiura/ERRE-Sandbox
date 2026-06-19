"""Loader + pure scorer for the bond-affinity near-miss diagnostic (ADR section 3.4).

Two halves, both touching only the bond-affinity trace (and the saturation trace it
joins against for cap exposure):

* :func:`read_bond_affinity_trace_rows` — a plain typed reader over the metrics trace.
  No ``raw_dialog`` egress guard (it is an internal ``metrics -> analysis`` read), and
  the qualified name is composed from ``METRICS_SCHEMA`` (never a schema-dot literal; CI
  grep gate). Nullable recency columns deserialise to ``int | None`` / ``str | None``.
* :func:`route_bond_affinity_cells` — the signal-to-noise decision layer the freeze ADR
  pre-registered (``…/20260617-bond-affinity-diagnostic-freeze/threshold-freeze-adr.md``
  §1-§3, ACCEPTED 2026-06-17) as **superseded** by the estimand-redesign ADR
  (``…/20260619-bond-affinity-estimand-redesign/estimand-redesign-adr.md`` §2', ACCEPTED
  2026-06-19, binding=user). The substrate is now the **bare** near-miss
  (``|affinity| < BELIEF_THRESHOLD`` ∧ ``ichigo_ichie_count >= MIN_INTERACTIONS`` ∧
  fresh) — the cap-saturation exposure join was a post-treatment collider and is **no
  longer** a verdict gate (§0). It folds each ``(seed, arm, replicate)`` cell into a
  proximity statistic (the **p95 |affinity|**) and routes the cross-arm verdict by
  contrasting the ON-OFF separation against the same-arm run-to-run noise floor —
  non-circular (freeze ADR §0) — with a §3' **truncation guard** suppressing a survivor
  ``(ii)`` when ON drains its near-miss pool by promotion.

The decision layer ports the III-a live §5.3 null-hierarchy structure
(:mod:`erre_sandbox.evidence.live_carry.scorer`): a per-seed ``S(ON-OFF)`` cross-arm
signal, an ``S(OFF/OFF)`` run-to-run noise floor, and an ``S(ON/ON)`` ON-specific
sanity null, gated by a materiality floor + ratio (degenerate-null aware, HIGH-2),
rank-non-overlap, and a 4-replicate-cell power gate (MED-1). Each cell also reports the
within-cell cap-saturation **secondary** split (§2'.3, descriptive / routing-inert) and
the promotion incidence (§3'). The numeric thresholds are **frozen** (freeze ADR §1 +
estimand-redesign §1') — imported from :mod:`.constants`. The **production** scorer is
:func:`score_bond_affinity_captures` (per-capture assembly, no cross-capture exposure
leak); :func:`score_bond_affinity` is a **test-only** routing helper (DA-4).
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
    PROMOTION_IMBALANCE_FACTOR,
    R_MIN_BOND,
    SLOPE_WINDOW,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    import duckdb

    from erre_sandbox.evidence.relational.trace_reader import BondAffinityCapture
    from erre_sandbox.evidence.saturation.trace_ddl import SaturationTraceRow

Verdict = Literal[
    "(i)-LEANING",
    "(ii)-LEANING",
    "INCONCLUSIVE_MIXED_SEED",
    "INCONCLUSIVE_LOW_POWER",
    "INCONCLUSIVE_NO_NEAR_MISS",
    "INCONCLUSIVE_TRUNCATED",
    "INVALID_MEASUREMENT",
]
"""The seven closed verdict states (freeze ADR §3 routing + estimand-redesign §3').

``(i)-LEANING`` = cap-binding **suggested** (a *weak* warrant): the ON arm pushes the
**bare** near-miss bonds closer to the 0.45 gate than OFF, above the noise floor — a
necessary condition for cap-binding, but the bare-gate substrate does **not** isolate
the cap from generic carry (superseding ADR §6', Codex L2), so it warrants a cap-relax
GO/NO-GO **in a separate ADR**, never proves it (this scorer does not authorise cap
variation). ``(ii)-LEANING`` = no differential approach above the noise floor **and**
the truncation guard did not fire (lowers fork (C) VoI; *not* a decoupling proof, ADR
MED-2). ``INCONCLUSIVE_MIXED_SEED`` = the median separation clears magnitude but a
per-seed signal sinks into the noise (seed reproducibility absent, HIGH-1).
``INCONCLUSIVE_LOW_POWER`` = under-powered (a replicate cell below the near-miss floor,
too few paired seeds, or ON-specific noise). ``INCONCLUSIVE_NO_NEAR_MISS`` = the
diagnostic substrate is empty. ``INCONCLUSIVE_TRUNCATED`` = magnitude unmet **but** the
ON arm promotes near-miss bonds past the gate at a rate imbalanced against OFF
(``ρ(ON)/ρ(OFF) > PROMOTION_IMBALANCE_FACTOR``), so the surviving-near-miss p95 may be a
truncation artifact — ``(ii)`` is suppressed and the claim bounded to *survivor
near-miss only* (superseding ADR §3'/§6', Codex HIGH-2). ``INVALID_MEASUREMENT`` = a
provenance-false row (freeze ADR §7: PR #25 was INCONCLUSIVE; v2 raises to INVALID)."""

I_LEANING: Final[str] = "(i)-LEANING"
II_LEANING: Final[str] = "(ii)-LEANING"
INCONCLUSIVE_MIXED_SEED: Final[str] = "INCONCLUSIVE_MIXED_SEED"
INCONCLUSIVE_LOW_POWER: Final[str] = "INCONCLUSIVE_LOW_POWER"
INCONCLUSIVE_NO_NEAR_MISS: Final[str] = "INCONCLUSIVE_NO_NEAR_MISS"
INCONCLUSIVE_TRUNCATED: Final[str] = "INCONCLUSIVE_TRUNCATED"
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
    of this cell's **bare** near-miss population, superseding ADR §2'.2); the rest are
    the §3 / LOW-1 / §2'.4 mandatory report so the verdict never rests on one statistic.
    Three blocks of read-only fields are added by the estimand-redesign superseding ADR:

    * **tick concentration + fresh sensitivity** (§2'.4 / Codex L1 / M1):
      :attr:`distinct_ticks` + :attr:`max_tick_share` expose whether the cell rides a
      few dyads / a single tick (a bare-gate ``n >= MIN_NEAR_MISS_N`` can otherwise be a
      weak power guard); :attr:`n_no_fresh` + :attr:`n_fresh_dropped` are the
      ``require_fresh`` sensitivity (did the stale guard drive the result?).
    * **promotion incidence** (§2'.2 / §3' / Codex HIGH-2): :attr:`promoted_dyads` +
      :attr:`promotion_incidence` (``ρ`` = promoted dyads / distinct ticks) are the
      truncation-guard substrate — they quantify how much the outcome-band selection
      drained this cell's pool.
    * **within-cell cap-saturation secondary** (§2'.3 / Codex M2): the bare near-miss
      split into cap-exposed vs non-exposed sub-populations. **Descriptive only**
      (routing-inert) — a *consistent descriptive co-incidence* of cap exposure with
      high proximity, never causal corroboration.
    """

    seed: int
    arm: str  # "ON" | "OFF"
    replicate: int  # 0 | 1
    n: int
    unique_dyads: int
    distinct_ticks: int
    """distinct ticks the cell's near-miss bonds span (tick-concentration context)."""
    max_tick_share: float | None
    """fraction of the near-miss population in its single busiest tick (``None`` when
    empty) — a high share warns the verdict rides one tick (§2'.4, Codex L1)."""
    p90_abs: float | None
    p95_abs: float | None
    max_abs: float | None
    eps_band_density: float | None
    n_trust: int
    n_clash: int
    n_neutral: int
    """near-miss bonds with ``affinity == 0.0`` (neither trust nor clash). Kept so the
    invariant ``n_trust + n_clash + n_neutral == n`` holds (Codex/CR HIGH-1)."""
    n_no_fresh: int
    """near-miss count with the stale guard **off** (``require_fresh=False``) — the
    fresh-sensitivity numerator (§2'.2, Codex M1)."""
    n_fresh_dropped: int
    """``n_no_fresh - n``: how many gate-passing bonds the stale guard removed."""
    promoted_dyads: int
    """distinct dyads in this cell that reached ``|affinity| >= BELIEF_THRESHOLD`` with
    the interaction gate met — bonds that *left* the pool by promoting (§3')."""
    promotion_incidence: float | None
    """``ρ`` = :attr:`promoted_dyads` / distinct ticks of the raw cell rows (``None`` if
    the cell has no ticks) — the truncation-guard rate (superseding ADR §1'/§3')."""
    cap_exposed_n: int
    cap_exposed_p95_abs: float | None
    cap_exposed_eps_band_density: float | None
    cap_unexposed_n: int
    cap_unexposed_p95_abs: float | None
    cap_unexposed_eps_band_density: float | None


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
    promotion_incidence_on: dict[int, float] = field(default_factory=dict)
    """per paired seed: ``ρ`` of the ON r0 cell (promoted dyads / distinct ticks)."""
    promotion_incidence_off: dict[int, float] = field(default_factory=dict)
    """per paired seed: ``ρ`` of the OFF r0 cell (the truncation-guard denominator)."""
    promotion_imbalance: float | None = None
    """``median_seed ρ(ON r0) / median_seed ρ(OFF r0)`` (``None`` for a degenerate
    ``ρ(OFF)=0`` null — the guard then uses the non-negligibility branch, §3')."""
    truncation_guard_fired: bool = False
    """True only when the verdict is ``INCONCLUSIVE_TRUNCATED`` (the (ii) route was
    suppressed because ON promotion drained the near-miss pool, §3'/Codex HIGH-2)."""
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
    """Phase 0 preflight (superseding ADR §5'): is there >= 1 **bare** near-miss?

    The primary substrate is now bare-gate (``require_exposure=False`` ∧
    ``require_fresh=True``, superseding ADR §2'.2): the cap-exposure join was a
    post-treatment collider and is no longer a verdict gate, so the Phase 0 stop-gate
    must match — it is now satisfied by a bare near-miss alone, **not** cap-exposed
    (the old exposure-gated smoke depended on the superseded §2 estimand, Codex HIGH-1).
    The secondary cap-saturation diagnostic (§2'.3) is descriptive and does **not** stop
    the smoke, so a capture with bare near-miss but zero cap exposure is still GO.

    A future smoke audit calls this on a sufficient-horizon flag-on capture before
    committing to the 12-run GPU matrix: an empty result on an adequate-horizon smoke
    routes ``INCONCLUSIVE_NO_NEAR_MISS`` (capture cannot discriminate), stopping the GPU
    investment early. A short-horizon empty is **not** a stop signal — the smoke must
    satisfy the live §5.3 horizon convention first (the caller's responsibility).

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
            require_exposure=False,
            require_fresh=True,
            slope_window=slope_window,
        )
    )


def _band_density(obs: Sequence[NearMissObservation]) -> float | None:
    """ε-band density over the near-miss obs (``None`` when the cell is empty)."""
    if not obs:
        return None
    n_band = sum(1 for o in obs if EPS_BAND_LO <= o.abs_affinity < BELIEF_THRESHOLD)
    return n_band / len(obs)


def _cell_stats(
    seed: int,
    arm: str,
    replicate: int,
    bond_rows: Sequence[BondAffinityTraceRow],
    saturation_rows: Sequence[SaturationTraceRow],
) -> CellStats:
    """Fold one ``(seed, arm, replicate)`` cell's raw rows into the §3/§2'.4 report.

    The primary substrate is the **bare** near-miss (superseding ADR §2'.2,
    ``require_exposure=False`` ∧ ``require_fresh=True``): the cap-exposure join is no
    longer a verdict gate (it was a post-treatment collider, ADR §0). Exposure is still
    *tagged* on each obs, so the within-cell cap-saturation secondary (§2'.3) can split
    the population descriptively. The promotion incidence (§3') and the fresh
    sensitivity (§2'.2) come from the same raw rows. The p95 / p90 / max / ε-band
    density / signed split are the PR #25 statistics, now over the bare substrate.
    """
    obs = identify_near_miss(
        bond_rows, saturation_rows, require_exposure=False, require_fresh=True
    )
    obs_no_fresh = identify_near_miss(
        bond_rows, saturation_rows, require_exposure=False, require_fresh=False
    )
    abs_vals = [o.abs_affinity for o in obs]
    dyads = {(o.individual_id, o.other_agent_id) for o in obs}

    # tick concentration — distinct ticks + the busiest single tick's share (§2'.4, L1).
    by_tick: dict[int, int] = {}
    for o in obs:
        by_tick[o.tick] = by_tick.get(o.tick, 0) + 1
    max_tick_share = (max(by_tick.values()) / len(obs)) if obs else None

    # promotion incidence — dyads that left the pool by reaching the gate, over the raw
    # cell rows (NOT the near-miss obs, which by construction exclude them, §3').
    promoted = {
        (r.individual_id, r.other_agent_id)
        for r in bond_rows
        if r.ichigo_ichie_count >= BELIEF_MIN_INTERACTIONS
        and abs(r.affinity) >= BELIEF_THRESHOLD
    }
    raw_distinct_ticks = len({r.tick for r in bond_rows})
    promotion_incidence = (
        len(promoted) / raw_distinct_ticks if raw_distinct_ticks > 0 else None
    )

    # within-cell cap-saturation secondary — descriptive split (routing-inert, §2'.3).
    exposed = [o for o in obs if o.under_individual_exposure]
    unexposed = [o for o in obs if not o.under_individual_exposure]

    return CellStats(
        seed=seed,
        arm=arm,
        replicate=replicate,
        n=len(obs),
        unique_dyads=len(dyads),
        distinct_ticks=len(by_tick),
        max_tick_share=max_tick_share,
        p90_abs=_percentile(abs_vals, 0.90),
        p95_abs=_percentile(abs_vals, 0.95),
        max_abs=max(abs_vals) if abs_vals else None,
        eps_band_density=_band_density(obs),
        n_trust=sum(1 for o in obs if o.affinity > 0.0),
        n_clash=sum(1 for o in obs if o.affinity < 0.0),
        n_neutral=sum(1 for o in obs if o.affinity == 0.0),
        n_no_fresh=len(obs_no_fresh),
        n_fresh_dropped=len(obs_no_fresh) - len(obs),
        promoted_dyads=len(promoted),
        promotion_incidence=promotion_incidence,
        cap_exposed_n=len(exposed),
        cap_exposed_p95_abs=_percentile([o.abs_affinity for o in exposed], 0.95),
        cap_exposed_eps_band_density=_band_density(exposed),
        cap_unexposed_n=len(unexposed),
        cap_unexposed_p95_abs=_percentile([o.abs_affinity for o in unexposed], 0.95),
        cap_unexposed_eps_band_density=_band_density(unexposed),
    )


_CellKey = tuple[int, str, int]  # (seed, arm, replicate)


def _assemble_cells(
    bond_rows: Sequence[BondAffinityTraceRow],
    saturation_rows: Sequence[SaturationTraceRow],
    *,
    arm_of: Mapping[str, str],
    replicate_of: Mapping[str, int],
) -> dict[_CellKey, CellStats]:
    """Group rows by ``(seed, arm, replicate)`` via run_id maps and fold each cell.

    **Test-only assembly path** (synthetic routing unit checks): production uses the
    per-capture :func:`score_bond_affinity_captures`, which keys cells by the capture
    sidecar identity and never passes a global saturation table to a cell (no
    cross-capture exposure leak, superseding ADR §9 / Codex MED-3). Here a row is placed
    by ``arm_of[run_id]`` / ``replicate_of[run_id]``; a row whose ``run_id`` is absent
    from either map, or whose arm is not ON/OFF, is dropped. The exposure tag is still
    keyed by ``(run_id, seed, ...)`` inside :func:`identify_near_miss`, so a synthetic
    fixture whose saturation rows carry the matching run_id/seed gets the correct
    per-cell split despite the shared table.
    """
    rows_by_cell: dict[_CellKey, list[BondAffinityTraceRow]] = {}
    for r in bond_rows:
        arm = arm_of.get(r.run_id)
        replicate = replicate_of.get(r.run_id)
        if arm not in (_ARM_ON, _ARM_OFF) or replicate is None:
            continue
        rows_by_cell.setdefault((r.seed, arm, replicate), []).append(r)
    return {
        (seed, arm, replicate): _cell_stats(
            seed, arm, replicate, cell_rows, saturation_rows
        )
        for (seed, arm, replicate), cell_rows in rows_by_cell.items()
    }


def _proximity(cells: Mapping[_CellKey, CellStats], key: _CellKey) -> float | None:
    """The cell's p95 ``|affinity|`` proximity statistic (``None`` if cell absent)."""
    cell = cells.get(key)
    return None if cell is None else cell.p95_abs


def _truncation_imbalanced(
    rho_on: Mapping[int, float],
    rho_off: Mapping[int, float],
    promoted_on: Mapping[int, int],
    nearmiss_on: Mapping[int, int],
) -> tuple[float | None, bool]:
    """Evaluate the §3' truncation guard; return ``(promotion_imbalance, fired)``.

    The guard fires when the ON arm promotes near-miss bonds past the gate at a rate
    imbalanced against OFF, so the surviving ON p95 may be a truncation artifact rather
    than a real null (superseding ADR §1'/§3', Codex HIGH-2). With a non-degenerate
    ``ρ(OFF)`` the test is the ratio ``median ρ(ON) / median ρ(OFF) >
    PROMOTION_IMBALANCE_FACTOR``. With a degenerate ``ρ(OFF)=0`` the ratio is undefined,
    so the guard fires only when the ON promotion is **non-negligible** against the
    surviving near-miss pool (``median ON promoted dyads >= median ON near-miss n /
    PROMOTION_IMBALANCE_FACTOR``) — a lone stray promotion cannot trip it. The
    ``promotion_imbalance`` returned is the ratio (``None`` in the degenerate branch).
    """
    median_rho_on = median(rho_on.values())
    median_rho_off = median(rho_off.values())
    if median_rho_off > 0.0:
        imbalance = median_rho_on / median_rho_off
        return imbalance, imbalance > PROMOTION_IMBALANCE_FACTOR
    # degenerate ρ(OFF)=0 — fall back to the absolute non-negligibility test.
    median_promoted_on = median(promoted_on.values())
    median_nearmiss_on = median(nearmiss_on.values())
    fired = (
        median_rho_on > 0.0
        and median_nearmiss_on > 0
        and median_promoted_on >= median_nearmiss_on / PROMOTION_IMBALANCE_FACTOR
    )
    return None, fired


@dataclass(frozen=True, slots=True)
class _PairedSignals:
    """Per-paired-seed cross-arm signals + ON r0 promotion incidence (assembly unit)."""

    s_on_off: dict[int, float]
    s_off_off: dict[int, float]
    s_on_on: dict[int, float]
    rho_on: dict[int, float]
    rho_off: dict[int, float]
    promoted_on: dict[int, int]
    nearmiss_on: dict[int, int]


def _paired_signals(
    cells: Mapping[_CellKey, CellStats], paired: Sequence[int]
) -> _PairedSignals:
    """Assemble per-seed S(ON-OFF) / nulls + ON r0 promotion incidence (r0 contrast).

    The proximity contrast uses replicate 0 (ON r0 vs OFF r0); the OFF/OFF and ON/ON
    nulls use both replicates. The promotion incidence is read off the ON r0 / OFF r0
    cells (the same cells the verdict contrasts, §3'). A seed missing any cell proximity
    is skipped defensively (the caller's power gate already guarantees all four).
    """
    s_on_off: dict[int, float] = {}
    s_off_off: dict[int, float] = {}
    s_on_on: dict[int, float] = {}
    rho_on: dict[int, float] = {}
    rho_off: dict[int, float] = {}
    promoted_on: dict[int, int] = {}
    nearmiss_on: dict[int, int] = {}
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
        on0 = cells[(seed, _ARM_ON, 0)]
        off0 = cells[(seed, _ARM_OFF, 0)]
        rho_on[seed] = on0.promotion_incidence or 0.0
        rho_off[seed] = off0.promotion_incidence or 0.0
        promoted_on[seed] = on0.promoted_dyads
        nearmiss_on[seed] = on0.n
    return _PairedSignals(
        s_on_off=s_on_off,
        s_off_off=s_off_off,
        s_on_on=s_on_on,
        rho_on=rho_on,
        rho_off=rho_off,
        promoted_on=promoted_on,
        nearmiss_on=nearmiss_on,
    )


def _route_paired_verdict(
    cell_tuple: tuple[CellStats, ...],
    cells: Mapping[_CellKey, CellStats],
    paired: Sequence[int],
) -> BondAffinityProbeResult:
    """Build the per-seed null hierarchy over the paired seeds and route the verdict.

    The per-seed signals + promotion incidences are assembled by
    :func:`_paired_signals`; this function applies the gates (freeze ADR §1 + §3'). The
    caller guarantees every paired seed has all four powered cells, so each proximity is
    defined. All thresholds are the frozen §1/§1' constants (single source).
    """
    sig = _paired_signals(cells, paired)
    s_on_off = sig.s_on_off

    max_off_off = max(sig.s_off_off.values())
    max_on_on = max(sig.s_on_on.values())
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

    # truncation guard (superseding ADR §3', Codex HIGH-2) — only the (ii) route can be
    # a survivor artifact, so it is evaluated just before emitting a bare (ii).
    promotion_imbalance, truncation_imbalanced = _truncation_imbalanced(
        sig.rho_on, sig.rho_off, sig.promoted_on, sig.nearmiss_on
    )
    med_rho_on = median(sig.rho_on.values())
    med_rho_off = median(sig.rho_off.values())

    # Route (freeze ADR §3 + §3': power -> ON-noise -> magnitude[+guard] -> rank).
    verdict: Verdict
    truncation_fired = False
    if not on_noise_ok:
        verdict = "INCONCLUSIVE_LOW_POWER"
        notes = (
            f"ON/ON noise {max_on_on:.4f} > {ON_NOISE_FACTOR} * OFF/OFF "
            f"floor {max_off_off:.4f} (ON-specific noise suspected)"
        )
    elif not magnitude_ok and truncation_imbalanced:
        verdict = "INCONCLUSIVE_TRUNCATED"
        truncation_fired = True
        notes = (
            f"magnitude unmet (median S(ON-OFF)={median_on_off:.4f}) but ON drains its "
            f"pool: median ρ(ON)={med_rho_on:.4f} vs ρ(OFF)={med_rho_off:.4f} "
            f"(imbalance={promotion_imbalance}, factor={PROMOTION_IMBALANCE_FACTOR}); "
            "(ii) suppressed — survivor near-miss only (§6')"
        )
    elif not magnitude_ok:
        verdict = "(ii)-LEANING"
        notes = (
            f"no differential approach above noise: median S(ON-OFF)="
            f"{median_on_off:.4f}, OFF/OFF floor={max_off_off:.4f}, "
            f"degenerate={null_degenerate}; truncation guard passed "
            f"(imbalance {promotion_imbalance} <= {PROMOTION_IMBALANCE_FACTOR}) "
            "(lowers fork (C) VoI, not decoupling)"
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
            f"floor); rank-non-overlap holds; {len(paired)} seed(s). cap-binding "
            "suggested (weak warrant — bare-gate does not isolate the cap, §6')"
        )

    return BondAffinityProbeResult(
        verdict=verdict,
        cells=cell_tuple,
        paired_seeds=tuple(paired),
        s_on_off=s_on_off,
        s_off_off_null=sig.s_off_off,
        s_on_on_null=sig.s_on_on,
        median_s_on_off=median_on_off,
        max_off_off_null=max_off_off,
        max_on_on_null=max_on_on,
        magnitude_ok=magnitude_ok,
        rank_ok=rank_ok,
        on_noise_ok=on_noise_ok,
        null_degenerate=null_degenerate,
        promotion_incidence_on=sig.rho_on,
        promotion_incidence_off=sig.rho_off,
        promotion_imbalance=promotion_imbalance,
        truncation_guard_fired=truncation_fired,
        notes=notes,
    )


def route_bond_affinity_cells(
    cells: Mapping[_CellKey, CellStats],
) -> BondAffinityProbeResult:
    """Route an assembled ``(seed, arm, replicate) -> CellStats`` matrix to the verdict.

    The **single** decision layer (Codex MED-3): both the production capture path
    (:func:`score_bond_affinity_captures`) and the test-only :func:`score_bond_affinity`
    assemble their cells, then delegate here. No provenance / assembly-integrity logic
    lives here (the callers own that) — only statistical routing over a coherent cell
    map. The proximity statistic per cell is the **p95 |affinity|** of its bare
    population (superseding ADR §2'.2). Per paired seed it forms a cross-arm signal
    ``S(ON-OFF) = p95(ON r0) - p95(OFF r0)``, a run-to-run noise floor
    ``S(OFF/OFF) = |p95(OFF r0) - p95(OFF r1)|``, and an ON-specific sanity null
    ``S(ON/ON) = |p95(ON r0) - p95(ON r1)|``. Routing order (freeze ADR §3 + §3'):

    * all cells empty → ``INCONCLUSIVE_NO_NEAR_MISS``;
    * power gate — a *paired seed* has all four cells (ON r0 / OFF r0 / OFF r1 / ON r1)
      with ``>= MIN_NEAR_MISS_N`` near-misses; fewer than ``MIN_PAIRED_SEEDS`` paired →
      ``INCONCLUSIVE_LOW_POWER`` (MED-1 / MED-3, 2-of-3 dropout-tolerant);
    * ON-noise sanity — ``max S(ON/ON) <= ON_NOISE_FACTOR * max S(OFF/OFF)`` else
      ``INCONCLUSIVE_LOW_POWER``;
    * magnitude — a materiality floor ``median S(ON-OFF) >= DEGENERATE_GAP_FLOOR``
      always, plus (when the null is non-degenerate) a ratio
      ``median S(ON-OFF) / max S(OFF/OFF) >= R_MIN_BOND``; a degenerate null needs only
      the floor (HIGH-2). Unmet → the **truncation guard** (§3'): an ON-imbalanced
      promotion incidence routes ``INCONCLUSIVE_TRUNCATED``, else ``(ii)-LEANING``;
    * rank-non-overlap — ``min S(ON-OFF) > max S(OFF/OFF)``; magnitude met but rank
      failed → ``INCONCLUSIVE_MIXED_SEED`` (HIGH-1); both met → ``(i)-LEANING``.

    All thresholds are the frozen §1/§1' constants (:mod:`.constants`, single source).
    """
    cell_tuple = tuple(cells[k] for k in sorted(cells))

    if sum(c.n for c in cell_tuple) == 0:
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


def score_bond_affinity(
    bond_rows: Sequence[BondAffinityTraceRow],
    saturation_rows: Sequence[SaturationTraceRow],
    *,
    arm_of: Mapping[str, str],
    replicate_of: Mapping[str, int],
) -> BondAffinityProbeResult:
    """**Test-only** routing helper over synthetic ``run_id``-keyed rows (DA-4).

    Production scoring is :func:`score_bond_affinity_captures` (per-capture assembly, no
    cross-capture exposure leak, superseding ADR §9 / Codex MED-3). This helper is kept
    only for the synthetic routing unit tests, which hand-build ``arm_of`` /
    ``replicate_of`` maps to exercise a single closed verdict state; it shares the exact
    decision path (:func:`route_bond_affinity_cells`) so those tests stay valid, but
    it passes a **global** saturation table to :func:`_assemble_cells`, so must not be
    used on real multi-capture stock (that is the leak the capture path closes). It
    handles provenance + the broken-assembly distinction itself, then delegates routing.
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
    result = route_bond_affinity_cells(cells)
    # Distinguish a genuinely empty substrate from a broken assembly (Codex MED-2): if
    # eligible near-miss exist over the raw rows but none landed in a cell (every run
    # unmapped), that is an INVALID matrix, not "no near-miss".
    if result.verdict == "INCONCLUSIVE_NO_NEAR_MISS" and has_eligible_near_miss(
        bond_rows, saturation_rows
    ):
        return BondAffinityProbeResult(
            verdict="INVALID_MEASUREMENT",
            cells=result.cells,
            notes=(
                "eligible near-miss exist but none mapped to a cell "
                "(arm_of/replicate_of incomplete — broken matrix assembly)"
            ),
        )
    return result


def _capture_identity_note(cap: BondAffinityCapture, run_ids: set[str]) -> str | None:
    """Per-capture integrity check (returns an INVALID note, or ``None`` if coherent).

    A sound single-run capture carries exactly one ``run_id`` and one seed; the cell key
    uses each row's **own** ``seed`` (:func:`_assemble_cells`), so a capture whose rows
    disagree with each other (or with the sidecar seed) would silently populate / merge
    cells past the cross-capture checks (Codex HIGH-1). An arm-bearing capture must also
    carry a complete, in-domain identity: a seed and a replicate in ``{0, 1}`` (Codex
    HIGH-2, mirroring live_carry's out-of-domain key rejection). A null-arm capture
    claims no cell and is tolerated (its rows are dropped by the arm/replicate-blind
    scorer).
    """
    row_seeds = {r.seed for r in cap.bond_rows} | {r.seed for r in cap.saturation_rows}
    if len(run_ids) > 1:
        return (
            f"capture {cap.path} carries multiple run_ids {sorted(run_ids)} "
            "— contaminated single-run capture"
        )
    if len(row_seeds) > 1:
        return (
            f"capture {cap.path} carries multiple row seeds {sorted(row_seeds)} "
            "— contaminated single-run capture"
        )
    if cap.seed is not None and row_seeds and row_seeds != {cap.seed}:
        return (
            f"capture {cap.path} sidecar seed {cap.seed} disagrees with row "
            f"seed(s) {sorted(row_seeds)} — provenance mismatch"
        )
    if cap.arm in (_ARM_ON, _ARM_OFF) and (
        cap.seed is None or cap.replicate_id not in (0, 1)
    ):
        return (
            f"capture {cap.path} declares arm {cap.arm} but has an invalid matrix "
            f"identity (seed={cap.seed}, replicate_id={cap.replicate_id}) "
            "— out-of-domain matrix key"
        )
    return None


def score_bond_affinity_captures(
    captures: Sequence[BondAffinityCapture],
) -> BondAffinityProbeResult:
    """Capture-level entry — the **only** production scorer (Codex MED-3).

    Per-capture assembly mirroring the live-carry ``_assemble_matrix``, then route. Each
    capture is indexed by its **sidecar** identity ``(seed, arm, replicate_id)`` and its
    near-miss is computed from **that capture's own rows only** (superseding ADR §9):
    ``identify_near_miss`` is never handed a global saturation table, so the ON arm's
    cap-saturation can no longer leak into an OFF cell's exposure join (the structural
    fix the freeze-ADR run_id-key assumption missed — the frozen captures reuse one
    ``run_id`` = ``persona_natural_run{idx}`` across a seed's four cells, which the old
    shared-``run_id`` guard wrongly INVALIDated). Because cells are keyed by sidecar
    identity, a shared ``run_id`` across captures is now **irrelevant** (no leak).

    Integrity gates retained (mirroring ``_assemble_matrix`` incoherence handling): a
    provenance-false row anywhere, a capture whose rows span multiple ``run_id`` / seeds
    or disagree with the sidecar seed, an arm-bearing capture with an out-of-domain
    matrix key, and a **duplicate** ``(seed, arm, replicate)`` cell all route
    ``INVALID_MEASUREMENT``. A null-arm capture (stimulus / flag-off natural) adds
    no cell and is tolerated. An incomplete-but-coherent matrix routes
    ``INCONCLUSIVE_LOW_POWER`` via the power gate; a non-empty bare near-miss substrate
    that lands in **no** cell (every eligible capture non-arm) routes
    ``INVALID_MEASUREMENT`` (broken assembly, MED-2), not masked as "no near-miss".
    """
    # provenance gate (global) — a single flag-off row invalidates the whole matrix.
    for cap in captures:
        if any(not r.individual_layer_enabled for r in cap.bond_rows) or any(
            not r.individual_layer_enabled for r in cap.saturation_rows
        ):
            return BondAffinityProbeResult(
                verdict="INVALID_MEASUREMENT",
                notes="provenance_false (a row carries individual_layer_enabled=False)",
            )

    matrix: dict[_CellKey, BondAffinityCapture] = {}
    seen_cells: dict[_CellKey, str] = {}
    for cap in captures:
        run_ids = {r.run_id for r in cap.bond_rows} | {
            r.run_id for r in cap.saturation_rows
        }
        note = _capture_identity_note(cap, run_ids)
        if note is not None:
            return BondAffinityProbeResult(verdict="INVALID_MEASUREMENT", notes=note)
        # ``_capture_identity_note`` already INVALIDated an arm-bearing capture with a
        # ``None`` seed or out-of-domain replicate, so the guards here only narrow the
        # types for the cell key; a null-arm capture claims no cell and is tolerated.
        if cap.arm in (_ARM_ON, _ARM_OFF) and (
            cap.seed is not None and cap.replicate_id is not None
        ):
            cell_key = (cap.seed, cap.arm, cap.replicate_id)
            if cell_key in seen_cells:
                return BondAffinityProbeResult(
                    verdict="INVALID_MEASUREMENT",
                    notes=(
                        f"duplicate matrix cell {cell_key} claimed by two captures "
                        f"({seen_cells[cell_key]} and {cap.path}) — dup sidecar key"
                    ),
                )
            seen_cells[cell_key] = cap.path
            matrix[cell_key] = cap

    # per-capture fold — each cell's near-miss is over its own rows + own saturation.
    cells: dict[_CellKey, CellStats] = {
        cell_key: _cell_stats(
            cell_key[0], cell_key[1], cell_key[2], cap.bond_rows, cap.saturation_rows
        )
        for cell_key, cap in matrix.items()
    }
    result = route_bond_affinity_cells(cells)
    # broken assembly (MED-2): an empty matrix substrate over captures that *do* carry a
    # bare near-miss (every eligible capture non-arm) is INVALID, not "no near-miss".
    if result.verdict == "INCONCLUSIVE_NO_NEAR_MISS" and any(
        has_eligible_near_miss(cap.bond_rows, cap.saturation_rows) for cap in captures
    ):
        return BondAffinityProbeResult(
            verdict="INVALID_MEASUREMENT",
            cells=result.cells,
            notes=(
                "eligible near-miss exist but none mapped to a cell "
                "(every eligible capture is non-arm — broken matrix assembly)"
            ),
        )
    return result


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
    "INCONCLUSIVE_TRUNCATED",
    "INVALID_MEASUREMENT",
    "I_LEANING",
    "BondAffinityProbeResult",
    "CellStats",
    "NearMissObservation",
    "has_eligible_near_miss",
    "identify_near_miss",
    "read_bond_affinity_trace_rows",
    "route_bond_affinity_cells",
    "score_bond_affinity",
    "score_bond_affinity_captures",
]
