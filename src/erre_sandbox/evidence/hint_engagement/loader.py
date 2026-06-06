"""Loader + pure scorer for the hint-engagement instrument (ADR §5 / §6).

Two halves, both touching only the hint-engagement trace:

* :func:`read_hint_engagement_trace_rows` — a plain typed reader over
  ``metrics.swm_hint_engagement_trace``. Like the saturation reader it does **not**
  apply the ``raw_dialog`` training-egress guard: this is an internal
  ``metrics -> analysis`` read whose columns are not on that allow-list. The qualified
  name is composed from ``METRICS_SCHEMA`` (never a schema-dot literal; CI grep gate).
* :func:`score_hint_engagement` — a pure function over a sequence of
  :class:`~erre_sandbox.evidence.hint_engagement.trace_ddl.HintEngagementTraceRow`. It
  recomputes the emission / adoption / per-gate / direction-consistency rates over the
  eligible population and applies the frozen ADR §6 decision table (thresholds imported
  from :mod:`.constants`) to a single routing verdict. No DuckDB dependency, so the
  whole decision table is unit-testable on synthetic fixtures.

The scorer **never re-runs classification** — it aggregates the stored ``disposition``
labels the cognition-time shadow already assigned (faithfulness fixed at cycle time).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final, Literal

from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.hint_engagement.constants import (
    ADOPTED_CHANNEL_MIN,
    CHANNEL_FLOOR,
    N_MIN,
    THETA_A,
    THETA_DIR,
    THETA_E,
    WARMUP_TICKS,
)
from erre_sandbox.evidence.hint_engagement.trace_ddl import (
    TABLE_NAME,
    HintEngagementTraceRow,
    column_names,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    import duckdb

# Routing verdicts (ADR §6). ``INSTRUMENT_INCONCLUSIVE`` is the global stability /
# boundary-tie / provenance outcome; the four ``STATE_*`` verdicts are the mutually
# exclusive engagement-floor states the decision table routes to. None of them
# authorise downstream work — they name the next ADR's question (ADR §6 / §8).
Verdict = Literal[
    "INSTRUMENT_INCONCLUSIVE",
    "STATE_A_EMISSION_RARE",
    "STATE_B_ADOPTION_REJECTED",
    "STATE_C_DIRECTION_INCONSISTENT",
    "STATE_ALL_HEALTHY",
]

INSTRUMENT_INCONCLUSIVE: Final[str] = "INSTRUMENT_INCONCLUSIVE"
STATE_A_EMISSION_RARE: Final[str] = "STATE_A_EMISSION_RARE"
STATE_B_ADOPTION_REJECTED: Final[str] = "STATE_B_ADOPTION_REJECTED"
STATE_C_DIRECTION_INCONSISTENT: Final[str] = "STATE_C_DIRECTION_INCONSISTENT"
STATE_ALL_HEALTHY: Final[str] = "STATE_ALL_HEALTHY"

# The four reject gates (ADR §2), in the authority's predicate order. Their shares sum
# to 1 over the rejected population; the dominant gate is the argmax (None on a tie).
REJECT_GATES: Final[tuple[str, ...]] = (
    "rejected_not_displayed",
    "rejected_citation",
    "rejected_no_change",
    "rejected_no_effect",
)


class HintEngagementLoaderError(RuntimeError):
    """Raised on a structurally broken trace (duplicate key) — loud, not silent."""


@dataclass(frozen=True, slots=True)
class HintEngagementResult:
    """Aggregate engagement metrics + routing verdict (ADR §5 / §6)."""

    verdict: Verdict
    emission_rate: float | None
    adoption_rate: float | None
    per_gate_rejection_share: dict[str, float]
    adopted_direction_consistency_rate: float | None
    dominant_gate: str | None
    n_eligible_ticks: int
    n_emitted: int
    n_adopted: int
    n_rejected: int
    n_eligible_channels: int
    notes: str = ""
    seeds: tuple[int, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

_Channel = tuple[str, int, str, str, str]
"""``(run_id, seed, individual_id, axis, key)`` — the adopted-nudge channel identity.

Keyed by the full run identity so adopted ticks from different seeds / runs never
merge into one channel (the engagement metrics pool across seeds, the channels do not).
"""


def _check_duplicate_keys(rows: Sequence[HintEngagementTraceRow]) -> None:
    """Raise on a duplicate ``(run_id, seed, individual_id, tick)`` key (loud-fail)."""
    seen: set[tuple[str, int, str, int]] = set()
    for r in rows:
        key = (r.run_id, r.seed, r.individual_id, r.tick)
        if key in seen:
            raise HintEngagementLoaderError(
                f"duplicate hint-engagement trace key {key!r}"
            )
        seen.add(key)


def _is_eligible(row: HintEngagementTraceRow) -> bool:
    """Eligible tick = post-warmup ∧ ``llm_status='ok'`` ∧ ``exposed_entry_count>=1``.

    The denominator population for emission_rate (ADR §5 / Codex LOW-3): warmup ticks,
    fallback ticks (``unavailable`` / ``unparseable``) and zero-exposure ticks are
    excluded so a transient outage or an empty SWM never inflates the rate.
    """
    return (
        row.tick >= WARMUP_TICKS
        and row.llm_status == "ok"
        and row.exposed_entry_count >= 1
    )


def _route_threshold(
    value: float, threshold: float
) -> Literal["below", "tie", "above"]:
    """Three-way compare for a routing stage (ADR §6 tie handling).

    ``below`` routes to the stage's state, ``above`` falls through downstream, and an
    exact ``tie`` (the rate sits on the threshold) is **not** sent downstream — it
    yields INSTRUMENT_INCONCLUSIVE (ADR §6 "境界同点なら下流へ送らず INCONCLUSIVE").
    """
    if value < threshold:
        return "below"
    if value == threshold:
        return "tie"
    return "above"


def _per_gate_share(
    rejected_counts: dict[str, int], n_rejected: int
) -> dict[str, float]:
    """Share of each reject gate within the rejected population (shares sum to 1)."""
    if n_rejected == 0:
        return dict.fromkeys(REJECT_GATES, 0.0)
    return {gate: rejected_counts.get(gate, 0) / n_rejected for gate in REJECT_GATES}


def _dominant_gate(per_gate_share: dict[str, float]) -> str | None:
    """The argmax reject gate, or ``None`` when the top share is tied (ADR §6)."""
    if not any(per_gate_share.values()):
        return None
    top = max(per_gate_share.values())
    leaders = [gate for gate, share in per_gate_share.items() if share == top]
    return leaders[0] if len(leaders) == 1 else None


def _direction_consistency(
    adopted_steps: dict[_Channel, list[float]],
) -> tuple[float | None, int]:
    """Same-direction-dominant share over channels with enough adopted nudges.

    A channel enters the population with ``>= ADOPTED_CHANNEL_MIN`` adopted nudges.
    Returns ``(rate, n_eligible_channels)``. A channel is *dominant* when
    ``|sum step| / sum|step| >= THETA_DIR`` (adopted intent points one way rather than
    cancelling). ``rate`` is ``None`` when no channel reaches the adopted-count floor —
    the global stability gate catches that case before routing reads the rate.
    """
    eligible = {
        ch: steps
        for ch, steps in adopted_steps.items()
        if len(steps) >= ADOPTED_CHANNEL_MIN
    }
    if not eligible:
        return None, 0
    dominant = 0
    for steps in eligible.values():
        gross = sum(abs(s) for s in steps)
        if gross == 0.0:
            continue  # every nudge was a zero step — cannot point a direction
        if abs(sum(steps)) / gross >= THETA_DIR:
            dominant += 1
    return dominant / len(eligible), len(eligible)


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _Tallies:
    n_eligible_ticks: int = 0
    n_emitted: int = 0
    n_adopted: int = 0
    n_rejected: int = 0


def _aggregate(
    rows: Sequence[HintEngagementTraceRow],
) -> tuple[_Tallies, dict[str, int], dict[_Channel, list[float]]]:
    """Fold the eligible rows into tallies, per-gate counts, and per-channel steps."""
    tallies = _Tallies()
    rejected_counts: dict[str, int] = {}
    adopted_steps: dict[_Channel, list[float]] = {}
    for r in rows:
        if not _is_eligible(r):
            continue
        tallies.n_eligible_ticks += 1
        if not r.emitted:
            continue
        tallies.n_emitted += 1
        if r.disposition == "adopted":
            tallies.n_adopted += 1
            ch: _Channel = (
                r.run_id,
                r.seed,
                r.individual_id,
                str(r.target_axis),
                str(r.target_key),
            )
            adopted_steps.setdefault(ch, []).append(r.adopted_signed_step)
        elif r.disposition in REJECT_GATES:
            tallies.n_rejected += 1
            rejected_counts[r.disposition] = rejected_counts.get(r.disposition, 0) + 1
    return tallies, rejected_counts, adopted_steps


def _route(
    *,
    emission_rate: float,
    adoption_rate: float,
    direction_rate: float | None,
    dominant_gate: str | None,
) -> tuple[Verdict, str]:
    """Apply the ADR §6 precedence cascade (stability passed) -> (verdict, note).

    ``direction_rate`` is not None here: the stability gate guaranteed at least
    ``CHANNEL_FLOOR`` eligible channels (compute its rate before calling).
    """
    assert direction_rate is not None
    # Upstream precedence: (a) emission, (b) adoption, (c) direction.
    stages: list[tuple[float, float, Verdict, str]] = [
        (emission_rate, THETA_E, "STATE_A_EMISSION_RARE", "emission_rate"),
        (adoption_rate, THETA_A, "STATE_B_ADOPTION_REJECTED", "adoption_rate"),
        (direction_rate, THETA_DIR, "STATE_C_DIRECTION_INCONSISTENT", "direction"),
    ]
    for value, threshold, state, label in stages:
        outcome = _route_threshold(value, threshold)
        if outcome == "tie":
            return "INSTRUMENT_INCONCLUSIVE", f"{label} at threshold (boundary tie)"
        if outcome == "below":
            note = f"{label} < threshold"
            if state == "STATE_B_ADOPTION_REJECTED":
                shown = dominant_gate if dominant_gate is not None else "tied"
                note = f"{note}; dominant_gate={shown}"
            return state, note
    return "STATE_ALL_HEALTHY", "emission, adoption and direction all healthy"


def score_hint_engagement(
    rows: Sequence[HintEngagementTraceRow],
) -> HintEngagementResult:
    """Score a hint-engagement trace into the ADR §6 routing verdict (pure).

    Rows may pool multiple seeds/runs; the engagement metrics are computed over the
    union of eligible ticks, while adopted-nudge channels are keyed by full run
    identity so cross-run ticks never merge. The precedence cascade (ADR §6),
    evaluated only after the **global stability gate** passes:

    1. **stability** — ``n_emitted < N_MIN`` *or* ``n_eligible_channels <
       CHANNEL_FLOOR`` (the direction-consistency population) ->
       INSTRUMENT_INCONCLUSIVE. Evaluated first (補強 §6): an adoption-low run whose
       channel count is below the floor routes here, **not** to state (b);
    2. (a) ``emission_rate < THETA_E`` -> emission rarity;
    3. (b) ``adoption_rate < THETA_A`` (emission healthy) -> adoption rejection
       (+ dominant reject gate, ``None`` on an argmax tie);
    4. (c) ``adopted_direction_consistency_rate < THETA_DIR`` -> direction
       inconsistency;
    5. all healthy.

    A rate sitting exactly on a routing threshold is a boundary tie ->
    INSTRUMENT_INCONCLUSIVE (ADR §6). A provenance-false row
    (``individual_layer_enabled`` is False) makes the whole result
    INSTRUMENT_INCONCLUSIVE (cannot trust the layer). A duplicate
    ``(run_id, seed, individual_id, tick)`` key raises (loud-not-silent).
    """
    _check_duplicate_keys(rows)
    seeds = tuple(sorted({r.seed for r in rows}))

    if any(not r.individual_layer_enabled for r in rows):
        return HintEngagementResult(
            verdict="INSTRUMENT_INCONCLUSIVE",
            emission_rate=None,
            adoption_rate=None,
            per_gate_rejection_share=dict.fromkeys(REJECT_GATES, 0.0),
            adopted_direction_consistency_rate=None,
            dominant_gate=None,
            n_eligible_ticks=0,
            n_emitted=0,
            n_adopted=0,
            n_rejected=0,
            n_eligible_channels=0,
            notes="provenance_false",
            seeds=seeds,
        )

    tallies, rejected_counts, adopted_steps = _aggregate(rows)
    per_gate_share = _per_gate_share(rejected_counts, tallies.n_rejected)
    dominant = _dominant_gate(per_gate_share)
    direction_rate, n_eligible_channels = _direction_consistency(adopted_steps)

    emission_rate = (
        tallies.n_emitted / tallies.n_eligible_ticks
        if tallies.n_eligible_ticks > 0
        else None
    )
    adoption_rate = (
        tallies.n_adopted / tallies.n_emitted if tallies.n_emitted > 0 else None
    )

    # Stage 1: global stability gate (ADR §6 precedence first; 補強 §6).
    if tallies.n_emitted < N_MIN or n_eligible_channels < CHANNEL_FLOOR:
        verdict: Verdict = "INSTRUMENT_INCONCLUSIVE"
        notes = (
            f"stability gate: n_emitted={tallies.n_emitted} (N_MIN={N_MIN}), "
            f"n_eligible_channels={n_eligible_channels} (CHANNEL_FLOOR={CHANNEL_FLOOR})"
        )
    else:
        # n_emitted >= N_MIN > 0 and n_eligible_channels >= CHANNEL_FLOOR > 0, so the
        # rates below are all defined (not None).
        assert emission_rate is not None
        assert adoption_rate is not None
        verdict, notes = _route(
            emission_rate=emission_rate,
            adoption_rate=adoption_rate,
            direction_rate=direction_rate,
            dominant_gate=dominant,
        )

    return HintEngagementResult(
        verdict=verdict,
        emission_rate=emission_rate,
        adoption_rate=adoption_rate,
        per_gate_rejection_share=per_gate_share,
        adopted_direction_consistency_rate=direction_rate,
        dominant_gate=dominant,
        n_eligible_ticks=tallies.n_eligible_ticks,
        n_emitted=tallies.n_emitted,
        n_adopted=tallies.n_adopted,
        n_rejected=tallies.n_rejected,
        n_eligible_channels=n_eligible_channels,
        notes=notes,
        seeds=seeds,
    )


# ---------------------------------------------------------------------------
# DuckDB reader (metrics -> analysis, no training-egress guard)
# ---------------------------------------------------------------------------


def read_hint_engagement_trace_rows(
    con: duckdb.DuckDBPyConnection,
    *,
    schema: str = METRICS_SCHEMA,
    table: str = TABLE_NAME,
) -> list[HintEngagementTraceRow]:
    """Read all hint-engagement trace rows from *con* into typed rows (column-lockstep).

    Plain ``SELECT`` over the metrics trace — no ``raw_dialog`` egress guard. The SELECT
    column list is :func:`column_names` so it stays in lockstep with the DDL, and the
    qualified table name is composed from *schema* (``METRICS_SCHEMA`` by default) so no
    ``metrics``-dot literal appears here.
    """
    cols = column_names()
    columns_sql = ", ".join(f'"{c}"' for c in cols)
    select_sql = f"SELECT {columns_sql} FROM {schema}.{table}"  # noqa: S608 — static identifiers only
    result = con.execute(select_sql).fetchall()
    return [
        HintEngagementTraceRow(
            run_id=str(row[0]),
            seed=int(row[1]),
            individual_id=str(row[2]),
            tick=int(row[3]),
            llm_status=str(row[4]),
            exposed_entry_count=int(row[5]),
            emitted=bool(row[6]),
            disposition=str(row[7]),
            target_axis=None if row[8] is None else str(row[8]),
            target_key=None if row[9] is None else str(row[9]),
            direction=None if row[10] is None else str(row[10]),
            adopted_signed_step=float(row[11]),
            individual_layer_enabled=bool(row[12]),
        )
        for row in result
    ]


__all__ = [
    "INSTRUMENT_INCONCLUSIVE",
    "REJECT_GATES",
    "STATE_ALL_HEALTHY",
    "STATE_A_EMISSION_RARE",
    "STATE_B_ADOPTION_REJECTED",
    "STATE_C_DIRECTION_INCONSISTENT",
    "HintEngagementLoaderError",
    "HintEngagementResult",
    "read_hint_engagement_trace_rows",
    "score_hint_engagement",
]
