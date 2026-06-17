"""Loader + pure scorer for the bond-affinity near-miss diagnostic (ADR section 3.4).

Two halves, both touching only the bond-affinity trace (and the saturation trace it
joins against for cap exposure):

* :func:`read_bond_affinity_trace_rows` — a plain typed reader over the metrics trace.
  No ``raw_dialog`` egress guard (it is an internal ``metrics -> analysis`` read), and
  the qualified name is composed from ``METRICS_SCHEMA`` (never a schema-dot literal; CI
  grep gate). Nullable recency columns deserialise to ``int | None`` / ``str | None``.
* :func:`score_bond_affinity` — a pure function. It recomputes the near-miss gate
  (``|affinity| < BELIEF_THRESHOLD`` ∧ ``ichigo_ichie_count >= MIN_INTERACTIONS``) from
  raw rows, joins each near-miss bond to its tick's cap-saturation exposure, applies the
  stale-bond guard (ADR HIGH-1: a bond near 0.45 from *before* a cap exposure that
  merely sits there must not count as a fresh approach), folds the per-arm near-miss
  population into a seed-paired distribution (primary, ADR MED-1), and contrasts ON/OFF.

The numeric ``(i)``-vs-``(ii)`` decision cutoff and the low-power N floor are **explicit
parameters with provisional defaults**, not frozen module constants: per the project's
forking-paths guard they must be frozen by a future GO/NO-GO ADR before any real run is
scored (this scorer's *execution* is out of the implementing task's scope — no stock
exists yet). What is hard-wired follows the ADR contract: empty / low-power →
INCONCLUSIVE (never folded into (ii)), the stale guard, the signed (trust/clash) split,
and the split of individual-level vs entry-linked exposure (ADR MED-3).
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
    EPS_BAND_LO,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    import duckdb

    from erre_sandbox.evidence.saturation.trace_ddl import SaturationTraceRow

Verdict = Literal["(i)-LEANING", "(ii)-LEANING", "INCONCLUSIVE"]
"""``(i)-LEANING`` = cap-binding suggested (ON approaches 0.45 more than OFF) →
warrants a cap-relax GO/NO-GO ADR. ``(ii)-LEANING`` = no differential approach (lowers
fork (C) VoI; *not* a decoupling proof, ADR MED-2). ``INCONCLUSIVE`` = empty / low-power
/ no paired seeds."""

I_LEANING: Final[str] = "(i)-LEANING"
II_LEANING: Final[str] = "(ii)-LEANING"
INCONCLUSIVE: Final[str] = "INCONCLUSIVE"

_PROVISIONAL_APPROACH_MARGIN: Final[float] = 0.01
"""Provisional ``(i)``-vs-``(ii)`` cutoff — **NOT frozen** (a future GO/NO-GO ADR sets
the real value). Median seed-paired ``max|aff|`` gap (ON - OFF) above this leans (i)."""

_PROVISIONAL_MIN_NEAR_MISS_N: Final[int] = 10
"""Provisional per-arm low-power floor — **NOT frozen**. Below this an arm is
underpowered → INCONCLUSIVE (never NO_DETECTABLE / (ii))."""

_PROVISIONAL_MIN_PAIRED_SEEDS: Final[int] = 2
"""Provisional minimum number of seeds present in **both** arms — **NOT frozen**.
A single paired seed cannot establish a seed-reproducible contrast, so below this the
verdict is INCONCLUSIVE (Codex MED-4)."""

_DEFAULT_SLOPE_WINDOW: Final[int] = 5
"""Lagged-slope window (ticks) for the stale guard's "did affinity rise into the
exposure" test. A descriptive window, not a verdict threshold."""

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
class ArmNearMissStats:
    """Per-arm near-miss distribution (ADR section 3.4 primary report quantities)."""

    arm: str
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

    per_seed_max_abs: dict[int, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BondAffinityProbeResult:
    """Cross-arm verdict + per-arm distributions — the reportable diagnostic outcome."""

    verdict: Verdict
    on_stats: ArmNearMissStats | None
    off_stats: ArmNearMissStats | None
    paired_seeds: list[int] = field(default_factory=list)
    median_paired_gap: float | None = None
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
    slope_window: int = _DEFAULT_SLOPE_WINDOW,
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


def _arm_stats(arm: str, obs: Sequence[NearMissObservation]) -> ArmNearMissStats:
    """Fold one arm's near-miss observations into the ADR 3.4 report quantities."""
    abs_vals = [o.abs_affinity for o in obs]
    dyads = {(o.individual_id, o.other_agent_id) for o in obs}
    n_band = sum(1 for v in abs_vals if EPS_BAND_LO <= v < BELIEF_THRESHOLD)
    per_seed: dict[int, float] = {}
    for o in obs:
        prev = per_seed.get(o.seed)
        if prev is None or o.abs_affinity > prev:
            per_seed[o.seed] = o.abs_affinity
    return ArmNearMissStats(
        arm=arm,
        n=len(obs),
        unique_dyads=len(dyads),
        p90_abs=_percentile(abs_vals, 0.90),
        p95_abs=_percentile(abs_vals, 0.95),
        max_abs=max(abs_vals) if abs_vals else None,
        eps_band_density=(n_band / len(abs_vals)) if abs_vals else None,
        n_trust=sum(1 for o in obs if o.affinity > 0.0),
        n_clash=sum(1 for o in obs if o.affinity < 0.0),
        n_neutral=sum(1 for o in obs if o.affinity == 0.0),
        per_seed_max_abs=per_seed,
    )


def score_bond_affinity(
    bond_rows: Sequence[BondAffinityTraceRow],
    saturation_rows: Sequence[SaturationTraceRow],
    *,
    arm_of: Mapping[str, str],
    approach_margin: float = _PROVISIONAL_APPROACH_MARGIN,
    min_near_miss_n: int = _PROVISIONAL_MIN_NEAR_MISS_N,
    min_paired_seeds: int = _PROVISIONAL_MIN_PAIRED_SEEDS,
    slope_window: int = _DEFAULT_SLOPE_WINDOW,
) -> BondAffinityProbeResult:
    """Score the bond-affinity trace into the ON-vs-OFF near-miss verdict (ADR 3.4).

    *arm_of* maps each ``run_id`` to ``"ON"`` or ``"OFF"`` (the caller assembles the
    paired arms, mirroring the live-carry bundle assembler — the trace itself is
    arm-blind by design, ADR section 3.2-5). The primary statistic is the
    **seed-paired** gap of ``max|affinity|`` (ON - OFF) over seeds present in both arms
    (ADR MED-1): a positive median gap above *approach_margin* means the ON arm pushes
    near-miss bonds closer to the 0.45 gate → ``(i)-LEANING``; a gap within the margin →
    ``(ii)-LEANING`` (lowers fork (C) VoI, not a decoupling proof).

    ``INCONCLUSIVE`` (never folded into (ii)) when: a provenance-false row is present
    (mirrors the saturation loader's INVALID, Codex MED-3); either arm is under-powered
    (``n < min_near_miss_n``); or fewer than *min_paired_seeds* seeds are in both arms
    (a single paired seed is not seed-reproducible, Codex MED-4). *approach_margin* /
    *min_near_miss_n* / *min_paired_seeds* are provisional and **must be frozen by a
    GO/NO-GO ADR** before a real run.
    """
    on_rows = [r for r in bond_rows if arm_of.get(r.run_id) == "ON"]
    off_rows = [r for r in bond_rows if arm_of.get(r.run_id) == "OFF"]

    if any(not r.individual_layer_enabled for r in bond_rows) or any(
        not r.individual_layer_enabled for r in saturation_rows
    ):
        return BondAffinityProbeResult(
            verdict="INCONCLUSIVE",
            on_stats=None,
            off_stats=None,
            notes="provenance_false (a row carries individual_layer_enabled=False)",
        )

    on_obs = identify_near_miss(on_rows, saturation_rows, slope_window=slope_window)
    off_obs = identify_near_miss(off_rows, saturation_rows, slope_window=slope_window)
    on_stats = _arm_stats("ON", on_obs)
    off_stats = _arm_stats("OFF", off_obs)

    if on_stats.n < min_near_miss_n or off_stats.n < min_near_miss_n:
        return BondAffinityProbeResult(
            verdict="INCONCLUSIVE",
            on_stats=on_stats,
            off_stats=off_stats,
            notes=(
                f"low power (ON n={on_stats.n}, OFF n={off_stats.n}, "
                f"floor={min_near_miss_n})"
            ),
        )

    paired = sorted(set(on_stats.per_seed_max_abs) & set(off_stats.per_seed_max_abs))
    if len(paired) < min_paired_seeds:
        return BondAffinityProbeResult(
            verdict="INCONCLUSIVE",
            on_stats=on_stats,
            off_stats=off_stats,
            paired_seeds=paired,
            notes=(
                f"too few paired seeds ({len(paired)} < {min_paired_seeds}); "
                "a single paired seed is not seed-reproducible"
            ),
        )

    gaps = [
        on_stats.per_seed_max_abs[s] - off_stats.per_seed_max_abs[s] for s in paired
    ]
    median_gap = median(gaps)
    verdict: Verdict = "(i)-LEANING" if median_gap > approach_margin else "(ii)-LEANING"
    return BondAffinityProbeResult(
        verdict=verdict,
        on_stats=on_stats,
        off_stats=off_stats,
        paired_seeds=paired,
        median_paired_gap=median_gap,
        notes=(
            f"seed-paired median max|aff| gap (ON-OFF)={median_gap:.4f} "
            f"vs provisional margin={approach_margin} (NOT frozen)"
        ),
    )


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
    "INCONCLUSIVE",
    "I_LEANING",
    "ArmNearMissStats",
    "BondAffinityProbeResult",
    "NearMissObservation",
    "identify_near_miss",
    "read_bond_affinity_trace_rows",
    "score_bond_affinity",
]
