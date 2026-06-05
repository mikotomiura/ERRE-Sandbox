"""Loader + pure scorer for the SWM saturation probe (ADR section 2.2 / 3.1-3.5).

Two halves, both touching only the saturation trace:

* :func:`read_saturation_trace_rows` — a plain typed reader over
  ``metrics.swm_modulation_saturation_trace``. It does **not** apply the
  ``raw_dialog`` training-egress allow-list guard (``assert_no_metrics_leak``):
  that guard is for the training-eligible utterance stream, and this is an
  internal ``metrics -> analysis`` read whose columns (``seed`` /
  ``base_floor_value`` ...) are not on that allow-list by construction (DA-IMPL-3).
  The qualified name is composed from ``METRICS_SCHEMA`` (never a schema-dot
  literal; CI eval-egress grep gate).
* :func:`score_saturation` — a pure function over a sequence of
  :class:`~erre_sandbox.evidence.saturation.trace_ddl.SaturationTraceRow`. It
  recomputes magnitude / effective cap_distance / saturation / sat_frac /
  engagement / drop_rate / transient rate per seed and folds the N=3 paired seeds
  into a single 3-way verdict, applying the frozen ADR section 3.0 thresholds
  verbatim (imported from :mod:`.constants`). No DuckDB dependency, so the whole
  decision table is unit-testable on synthetic fixtures.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import median
from typing import TYPE_CHECKING, Final, Literal

from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.saturation.constants import (
    BOUNDARY_FLOOR_THRESHOLD,
    DROP_HIGH,
    ENGAGEMENT_MIN,
    EPSILON_MOD,
    ETA_PINNED,
    MAX_TOTAL_MODULATION,
    MIN_ACTIVE_CHANNELS,
    N_SEEDS,
    SLOPE_TOL,
    T_RUN_MIN,
    T_WARMUP,
    TERMINAL_PRESENCE_MIN,
    THETA_HIGH,
    THETA_LOW,
    TRANSIENT_HIGH,
    W_TERM,
)
from erre_sandbox.evidence.saturation.trace_ddl import (
    TABLE_NAME,
    SaturationTraceRow,
    column_names,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    import duckdb

# 3-way labels (ADR section 4.1) + the per-seed INVALID disposition (ADR section 3.5).
# Values match the ADR's decision-table spelling verbatim ("NON-SATURATED" with a
# hyphen, Codex HIGH-1) so a downstream consumer reads the frozen label, not a
# code-only underscore variant. The Python constant name stays NON_SATURATED.
SeedLabel = Literal["SATURATED", "NON-SATURATED", "INCONCLUSIVE", "INVALID"]
Verdict = Literal["SATURATED", "NON-SATURATED", "INCONCLUSIVE"]

SATURATED: Final[str] = "SATURATED"
NON_SATURATED: Final[str] = "NON-SATURATED"
INCONCLUSIVE: Final[str] = "INCONCLUSIVE"
INVALID: Final[str] = "INVALID"


class SaturationLoaderError(RuntimeError):
    """Raised on a structurally broken trace (duplicate key) — loud, not silent."""


@dataclass(frozen=True, slots=True)
class SeedScore:
    """Per-seed saturation diagnostics + 3-way label (ADR section 3.1-3.5)."""

    seed: int
    label: SeedLabel
    valid: bool
    invalid_reason: str | None
    t_run: int
    total_channels: int
    n_active: int
    n_eligible: int
    n_saturated: int
    n_transient_active: int
    n_terminal_exit: int
    n_boundary_floor: int
    sat_frac: float | None
    engagement_rate: float
    drop_rate: float
    transient_active_rate: float
    gate_pass: bool


@dataclass(frozen=True, slots=True)
class SaturationProbeResult:
    """N=3 aggregate (ADR section 3.4) — the probe's reportable outcome."""

    verdict: Verdict
    median_sat_frac: float | None
    n_valid_seeds: int
    seeds: list[SeedScore] = field(default_factory=list)
    notes: str = ""


# ---------------------------------------------------------------------------
# Pure numeric helpers
# ---------------------------------------------------------------------------


_OLS_MIN_POINTS: Final[int] = 2
"""A slope needs at least two points; below this it is undefined (-> 0.0)."""


def _ols_slope(xs: Sequence[int], ys: Sequence[float]) -> float:
    """Ordinary-least-squares slope of *ys* on *xs* (0.0 when undefined)."""
    n = len(xs)
    if n < _OLS_MIN_POINTS:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    den = sum((x - mean_x) ** 2 for x in xs)
    if den == 0.0:
        return 0.0
    return num / den


def _room_eff(floor: float, signed_magnitude: float) -> float:
    """Signed-direction effective cap room (ADR section 2.2).

    The reconcile clamps to ``[max(-1, floor-0.15), min(1, floor+0.15)]``, so a
    floor near ``+/-1`` has < 0.15 of room on the saturating side. ``room_eff`` is
    the distance from the floor to the clamp boundary in the direction the
    modulation actually moved.
    """
    if signed_magnitude >= 0.0:
        return min(MAX_TOTAL_MODULATION, 1.0 - floor)
    return min(MAX_TOTAL_MODULATION, floor + 1.0)


def _cap_distance(floor: float, modulated: float) -> float:
    """Effective cap_distance at one tick (``room_eff - magnitude``, clamped >=0)."""
    signed = modulated - floor
    room = _room_eff(floor, signed)
    return max(0.0, room - abs(signed))


# ---------------------------------------------------------------------------
# Per-channel / per-seed intermediates (not exported)
# ---------------------------------------------------------------------------

_Channel = tuple[str, str, str]
"""``(individual_id, axis, key)`` — the saturation channel identity."""


@dataclass(slots=True)
class _SeedSubstrate:
    """Per-channel post-warmup tick maps + per-individual tick grids for one seed."""

    mod: dict[_Channel, dict[int, float]]
    floor: dict[_Channel, dict[int, float]]
    fp: dict[_Channel, dict[int, str]]
    individual_grids: dict[str, list[int]]


@dataclass(slots=True)
class _SeedCounts:
    """Per-seed category tallies (ADR section 3.1-3.3)."""

    n_active: int = 0
    n_eligible: int = 0
    n_saturated: int = 0
    n_transient_active: int = 0
    n_terminal_exit: int = 0
    n_boundary_floor: int = 0


@dataclass(slots=True)
class _ChannelEval:
    """Intermediate per-``(individual, axis, key)`` evaluation (not exported)."""

    active: bool
    terminal_assessable: bool
    saturated: bool
    terminal_exit: bool
    boundary_floor: bool


def _eval_channel(
    *,
    ticks: list[int],
    floor_by_tick: dict[int, float],
    mod_by_tick: dict[int, float],
    term_lo: int,
) -> _ChannelEval:
    """Score one channel over its present eval-window ticks (ADR section 3.2)."""
    peak = max(abs(mod_by_tick[t] - floor_by_tick[t]) for t in ticks)
    active = peak >= EPSILON_MOD

    terminal_ticks = sorted(t for t in ticks if t >= term_lo)
    terminal_presence = len(terminal_ticks)
    terminal_assessable = terminal_presence >= TERMINAL_PRESENCE_MIN

    boundary_floor = any(
        abs(floor_by_tick[t]) > BOUNDARY_FLOOR_THRESHOLD for t in terminal_ticks
    )

    saturated = False
    terminal_exit = False
    if active and terminal_assessable:
        cap_distances = [
            _cap_distance(floor_by_tick[t], mod_by_tick[t]) for t in terminal_ticks
        ]
        magnitudes = [abs(mod_by_tick[t] - floor_by_tick[t]) for t in terminal_ticks]
        terminal_mean_cap = sum(cap_distances) / len(cap_distances)
        slope = _ols_slope(terminal_ticks, magnitudes)
        pinned = terminal_mean_cap <= ETA_PINNED
        flat = abs(slope) <= SLOPE_TOL
        saturated = pinned and flat
        terminal_exit = slope < -SLOPE_TOL

    return _ChannelEval(
        active=active,
        terminal_assessable=terminal_assessable,
        saturated=saturated,
        terminal_exit=terminal_exit,
        boundary_floor=boundary_floor,
    )


# ---------------------------------------------------------------------------
# Per-seed scoring
# ---------------------------------------------------------------------------


def _invalid_seed(seed: int, t_run: int, reason: str) -> SeedScore:
    return SeedScore(
        seed=seed,
        label="INVALID",
        valid=False,
        invalid_reason=reason,
        t_run=t_run,
        total_channels=0,
        n_active=0,
        n_eligible=0,
        n_saturated=0,
        n_transient_active=0,
        n_terminal_exit=0,
        n_boundary_floor=0,
        sat_frac=None,
        engagement_rate=0.0,
        drop_rate=0.0,
        transient_active_rate=0.0,
        gate_pass=False,
    )


def _drop_rate(
    *,
    channel_ticks: dict[tuple[str, str, str], dict[int, float]],
    channel_fp: dict[tuple[str, str, str], dict[int, str]],
    individual_grids: dict[str, list[int]],
    floor_by_channel: dict[tuple[str, str, str], dict[int, float]],
) -> float:
    """Recompute drop_rate from raw substrate (ADR section 5, DA-IMPL-5).

    Adjacency runs over each **individual's** grid — here the ticks at which that
    individual emitted at least one saturation row — so a gap means the
    ``(axis, key)`` churned out while >= 1 sibling channel persisted, not that the
    whole individual fell silent. For each ``(channel, prev)`` whose magnitude(prev)
    >= ``EPSILON_MOD`` and which has a next grid tick, a drop is counted when at the
    next grid tick the channel row is either (a) present with a changed fingerprint,
    or (b) absent while a sibling is present.

    Known bounded limitation (Codex MEDIUM-1, DA-IMPL-6): the grid is *row-derived*,
    so a tick where the individual stepped but emitted **zero** SWM entries (total
    SWM collapse — no row at all) is absent from the grid and is **not** counted as a
    drop. ``drop_rate`` is therefore a *lower bound* on churn: per-channel
    disappearance is caught, total-collapse is not (it cannot be seen from the
    saturation rows alone). Post-warmup total collapse is rare (an agent with beliefs
    or bonds synthesises a non-empty floor); if it proves frequent in the real run,
    the trace would need a per-(agent, tick) sentinel — out of scope for this probe.
    """
    numerator = 0
    denominator = 0
    for ch, mod_by_tick in channel_ticks.items():
        individual_id = ch[0]
        grid = individual_grids[individual_id]
        grid_index = {t: i for i, t in enumerate(grid)}
        floor_by_tick = floor_by_channel[ch]
        fp_by_tick = channel_fp[ch]
        for prev in sorted(mod_by_tick):
            magnitude_prev = abs(mod_by_tick[prev] - floor_by_tick[prev])
            if magnitude_prev < EPSILON_MOD:
                continue
            i = grid_index[prev]
            if i + 1 >= len(grid):
                continue  # no next step for this individual -> not a denominator unit
            next_t = grid[i + 1]
            denominator += 1
            if next_t in mod_by_tick:
                if fp_by_tick[next_t] != fp_by_tick[prev]:  # (a) fingerprint reset
                    numerator += 1
            else:  # (b) channel disappeared while the individual kept stepping
                numerator += 1
    return numerator / denominator if denominator > 0 else 0.0


def _label_seed(sat_frac: float | None, *, gate_pass: bool) -> SeedLabel:
    if sat_frac is None or not gate_pass:
        return "INCONCLUSIVE"
    if sat_frac >= THETA_HIGH:
        return "SATURATED"
    if sat_frac <= THETA_LOW:
        return "NON-SATURATED"
    return "INCONCLUSIVE"


def _check_duplicate_keys(seed: int, rows: list[SaturationTraceRow]) -> None:
    """Raise on a duplicate unique key (ADR section 5 integrity, loud-not-silent)."""
    seen: set[tuple[str, int, str, str, str, int]] = set()
    for r in rows:
        key = (r.run_id, r.seed, r.individual_id, r.axis, r.key, r.tick)
        if key in seen:
            raise SaturationLoaderError(
                f"duplicate saturation trace key {key!r} (seed {seed})"
            )
        seen.add(key)


def _invalid_reason(rows: list[SaturationTraceRow], t_run: int) -> str | None:
    """Return the seed's INVALID reason (ADR section 3.5), or None if measurable."""
    if any(not r.individual_layer_enabled for r in rows):
        return "provenance_false"
    if any(
        math.isnan(r.base_floor_value) or math.isnan(r.modulated_value) for r in rows
    ):
        return "nan_value"
    if t_run < T_RUN_MIN:
        return "t_run_below_min"
    return None


def _build_substrate(rows: list[SaturationTraceRow]) -> _SeedSubstrate:
    """Project the post-warmup rows into per-channel tick maps + individual grids."""
    mod: dict[_Channel, dict[int, float]] = {}
    floor: dict[_Channel, dict[int, float]] = {}
    fp: dict[_Channel, dict[int, str]] = {}
    individual_ticks: dict[str, set[int]] = {}
    for r in rows:
        if r.tick < T_WARMUP:
            continue
        ch = (r.individual_id, r.axis, r.key)
        mod.setdefault(ch, {})[r.tick] = r.modulated_value
        floor.setdefault(ch, {})[r.tick] = r.base_floor_value
        fp.setdefault(ch, {})[r.tick] = r.floor_fingerprint_hash
        individual_ticks.setdefault(r.individual_id, set()).add(r.tick)
    grids = {ind: sorted(ticks) for ind, ticks in individual_ticks.items()}
    return _SeedSubstrate(mod=mod, floor=floor, fp=fp, individual_grids=grids)


def _aggregate_counts(sub: _SeedSubstrate, term_lo: int) -> _SeedCounts:
    """Fold per-channel evaluations into the seed's category counts (ADR 3.1-3.3)."""
    c = _SeedCounts()
    for ch, mod_by_tick in sub.mod.items():
        ev = _eval_channel(
            ticks=sorted(mod_by_tick),
            floor_by_tick=sub.floor[ch],
            mod_by_tick=mod_by_tick,
            term_lo=term_lo,
        )
        if ev.boundary_floor:
            c.n_boundary_floor += 1
        if not ev.active:
            continue
        c.n_active += 1
        if not ev.terminal_assessable:
            c.n_transient_active += 1
            continue
        c.n_eligible += 1
        if ev.saturated:
            c.n_saturated += 1
        if ev.terminal_exit:
            c.n_terminal_exit += 1
    return c


def _score_seed(seed: int, rows: list[SaturationTraceRow]) -> SeedScore:
    _check_duplicate_keys(seed, rows)
    t_run = max(r.tick for r in rows)
    reason = _invalid_reason(rows, t_run)
    if reason is not None:
        return _invalid_seed(seed, t_run, reason)

    sub = _build_substrate(rows)
    total_channels = len(sub.mod)
    counts = _aggregate_counts(sub, t_run - W_TERM + 1)

    sat_frac = counts.n_saturated / counts.n_eligible if counts.n_eligible > 0 else None
    engagement_rate = counts.n_active / total_channels if total_channels > 0 else 0.0
    transient_active_rate = (
        counts.n_transient_active / counts.n_active if counts.n_active > 0 else 0.0
    )
    drop_rate = _drop_rate(
        channel_ticks=sub.mod,
        channel_fp=sub.fp,
        individual_grids=sub.individual_grids,
        floor_by_channel=sub.floor,
    )

    gate_pass = (
        engagement_rate >= ENGAGEMENT_MIN
        and counts.n_active >= MIN_ACTIVE_CHANNELS
        and drop_rate < DROP_HIGH
        and transient_active_rate < TRANSIENT_HIGH
    )
    label = _label_seed(sat_frac, gate_pass=gate_pass)

    return SeedScore(
        seed=seed,
        label=label,
        valid=True,
        invalid_reason=None,
        t_run=t_run,
        total_channels=total_channels,
        n_active=counts.n_active,
        n_eligible=counts.n_eligible,
        n_saturated=counts.n_saturated,
        n_transient_active=counts.n_transient_active,
        n_terminal_exit=counts.n_terminal_exit,
        n_boundary_floor=counts.n_boundary_floor,
        sat_frac=sat_frac,
        engagement_rate=engagement_rate,
        drop_rate=drop_rate,
        transient_active_rate=transient_active_rate,
        gate_pass=gate_pass,
    )


def score_saturation(rows: Sequence[SaturationTraceRow]) -> SaturationProbeResult:
    """Score a saturation trace into the N=3 paired-seed 3-way verdict (ADR 3.4).

    Rows may span seeds; they are partitioned by ``seed`` and each seed is scored
    independently. The probe is a **paired N=3** design, so the verdict binds only
    when there are **exactly** ``N_SEEDS`` seeds, **all** valid (non-INVALID), and
    **all** agreeing on the same SATURATED / NON-SATURATED label (Codex HIGH-2:
    ``>= N_SEEDS`` would let a 4th agreeing seed bind, a forking-paths risk). Any
    extra/missing seed, any INVALID or INCONCLUSIVE seed, or any disagreement yields
    INCONCLUSIVE. ``median_sat_frac`` is the median over valid seeds with a sat_frac.
    """
    by_seed: dict[int, list[SaturationTraceRow]] = {}
    for r in rows:
        by_seed.setdefault(r.seed, []).append(r)

    seed_scores = [_score_seed(seed, by_seed[seed]) for seed in sorted(by_seed)]
    valid_seeds = [s for s in seed_scores if s.valid]
    fracs = [s.sat_frac for s in valid_seeds if s.sat_frac is not None]
    median_sat_frac = median(fracs) if fracs else None

    verdict: Verdict
    if len(by_seed) != N_SEEDS or len(valid_seeds) != N_SEEDS:
        verdict = "INCONCLUSIVE"
        notes = (
            f"paired N={N_SEEDS} not met (seeds={len(by_seed)}, "
            f"valid={len(valid_seeds)})"
        )
    else:
        labels = {s.label for s in valid_seeds}
        if labels == {"SATURATED"}:
            verdict = "SATURATED"
        elif labels == {"NON-SATURATED"}:
            verdict = "NON-SATURATED"
        else:
            verdict = "INCONCLUSIVE"
        notes = f"valid seed labels: {sorted(labels)}"

    return SaturationProbeResult(
        verdict=verdict,
        median_sat_frac=median_sat_frac,
        n_valid_seeds=len(valid_seeds),
        seeds=seed_scores,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# DuckDB reader (metrics -> analysis, no training-egress guard; DA-IMPL-3)
# ---------------------------------------------------------------------------


def read_saturation_trace_rows(
    con: duckdb.DuckDBPyConnection,
    *,
    schema: str = METRICS_SCHEMA,
    table: str = TABLE_NAME,
) -> list[SaturationTraceRow]:
    """Read all saturation trace rows from *con* into typed rows (column-lockstep).

    Plain ``SELECT`` over the metrics trace — no ``raw_dialog`` egress guard
    (DA-IMPL-3). The SELECT column list is :func:`column_names` so it stays in
    lockstep with the DDL, and the qualified table name is composed from *schema*
    (``METRICS_SCHEMA`` by default) so no ``metrics``-dot literal appears here.
    """
    cols = column_names()
    columns_sql = ", ".join(f'"{c}"' for c in cols)
    select_sql = f"SELECT {columns_sql} FROM {schema}.{table}"  # noqa: S608 — static identifiers only
    result = con.execute(select_sql).fetchall()
    return [
        SaturationTraceRow(
            run_id=str(row[0]),
            seed=int(row[1]),
            individual_id=str(row[2]),
            axis=str(row[3]),
            key=str(row[4]),
            tick=int(row[5]),
            base_floor_value=float(row[6]),
            modulated_value=float(row[7]),
            floor_fingerprint_hash=str(row[8]),
            individual_layer_enabled=bool(row[9]),
        )
        for row in result
    ]


__all__ = [
    "INCONCLUSIVE",
    "INVALID",
    "NON_SATURATED",
    "SATURATED",
    "SaturationLoaderError",
    "SaturationProbeResult",
    "SeedScore",
    "read_saturation_trace_rows",
    "score_saturation",
]
