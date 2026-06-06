"""Loader + scorer coverage for the hint-engagement instrument (ADR §5 / §6).

CPU-only. Verifies the recomputed metrics, the DuckDB round-trip, the duplicate-key
loud-fail, and every branch of the ADR §6 decision table including the
INSTRUMENT_INCONCLUSIVE boundaries. The headline guard (補強 §6) is
``test_channel_floor_is_global_stability_gate`` + the adoption-low∧channel<floor case,
which must route to the **global** stability INCONCLUSIVE, not state (b).
"""

from __future__ import annotations

import dataclasses
import itertools

import duckdb
import pytest

from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.hint_engagement.constants import (
    CHANNEL_FLOOR,
    N_MIN,
    THETA_E,
)
from erre_sandbox.evidence.hint_engagement.loader import (
    HintEngagementLoaderError,
    read_hint_engagement_trace_rows,
    score_hint_engagement,
)
from erre_sandbox.evidence.hint_engagement.trace_ddl import (
    TABLE_NAME,
    HintEngagementTraceRow,
    bootstrap_hint_engagement_trace_schema,
    column_names,
)

# Monotonic tick supply so every row has a unique (run, seed, individual, tick) key.
_TICKS = itertools.count(10)  # all >= WARMUP_TICKS (5)


def _adopted(
    key: str, *, direction: str = "strengthen", step: float = 0.05
) -> HintEngagementTraceRow:
    return HintEngagementTraceRow(
        run_id="r",
        seed=1,
        individual_id="kant",
        tick=next(_TICKS),
        llm_status="ok",
        exposed_entry_count=3,
        emitted=True,
        disposition="adopted",
        target_axis="self",
        target_key=key,
        direction=direction,
        adopted_signed_step=step,
        individual_layer_enabled=True,
    )


def _rejected(reason: str, *, key: str = "k") -> HintEngagementTraceRow:
    return HintEngagementTraceRow(
        run_id="r",
        seed=1,
        individual_id="kant",
        tick=next(_TICKS),
        llm_status="ok",
        exposed_entry_count=3,
        emitted=True,
        disposition=reason,
        target_axis="self",
        target_key=key,
        direction="strengthen",
        adopted_signed_step=0.0,
        individual_layer_enabled=True,
    )


def _not_emitted(*, llm_status: str = "ok", exposed: int = 3) -> HintEngagementTraceRow:
    return HintEngagementTraceRow(
        run_id="r",
        seed=1,
        individual_id="kant",
        tick=next(_TICKS),
        llm_status=llm_status,
        exposed_entry_count=exposed,
        emitted=False,
        disposition="not_emitted",
        target_axis=None,
        target_key=None,
        direction=None,
        adopted_signed_step=0.0,
        individual_layer_enabled=True,
    )


def _channels(
    n: int, per_channel: int, *, direction: str = "strengthen", step: float = 0.05
) -> list[HintEngagementTraceRow]:
    """``n`` distinct adopted channels, each adopted ``per_channel`` times (one dir)."""
    return [
        _adopted(f"k{c}", direction=direction, step=step)
        for c in range(n)
        for _ in range(per_channel)
    ]


# --- recompute + round-trip ---------------------------------------------------


def test_metrics_recompute_is_stable() -> None:
    rows = [*_channels(9, 3), _rejected("rejected_citation")]
    first = score_hint_engagement(rows)
    second = score_hint_engagement(rows)
    assert first == second


def test_duckdb_round_trip_matches_direct_score() -> None:
    rows = [*_channels(9, 3), _rejected("rejected_no_change")]
    con = duckdb.connect(":memory:")
    con.execute(f"CREATE SCHEMA {METRICS_SCHEMA}")
    bootstrap_hint_engagement_trace_schema(con, METRICS_SCHEMA)
    cols = column_names()
    insert_sql = (
        f"INSERT INTO {METRICS_SCHEMA}.{TABLE_NAME} "  # noqa: S608 — static identifiers, test
        f"({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    )
    for r in rows:
        con.execute(insert_sql, r.to_row())
    read_back = read_hint_engagement_trace_rows(con)
    assert (
        score_hint_engagement(read_back).verdict == score_hint_engagement(rows).verdict
    )
    assert {r.tick for r in read_back} == {r.tick for r in rows}


def test_duplicate_key_raises_loud() -> None:
    dup = _adopted("k0")
    twin = dataclasses.replace(dup)  # same (run, seed, ind, tick)
    with pytest.raises(HintEngagementLoaderError, match="duplicate"):
        score_hint_engagement([dup, twin])


# --- decision-table branches --------------------------------------------------


def test_all_healthy() -> None:
    result = score_hint_engagement(_channels(9, 3))
    assert result.verdict == "STATE_ALL_HEALTHY"
    assert result.emission_rate == pytest.approx(1.0)
    assert result.adoption_rate == pytest.approx(1.0)
    assert result.adopted_direction_consistency_rate == pytest.approx(1.0)


def test_state_a_emission_rare() -> None:
    # 24 adopted over 8 channels (stability passes) drowned by not_emitted ticks so
    # emission_rate < THETA_E.
    rows = _channels(8, 3) + [_not_emitted() for _ in range(220)]
    result = score_hint_engagement(rows)
    assert result.emission_rate is not None
    assert result.emission_rate < THETA_E
    assert result.verdict == "STATE_A_EMISSION_RARE"


def test_state_b_adoption_rejected_with_dominant_gate() -> None:
    # 8 channels x 2 adopted (16) + 20 rejected_citation -> adoption 16/36 < 0.5.
    rows = _channels(8, 2) + [_rejected("rejected_citation") for _ in range(20)]
    result = score_hint_engagement(rows)
    assert result.verdict == "STATE_B_ADOPTION_REJECTED"
    assert result.adoption_rate is not None
    assert result.adoption_rate < 0.5
    assert result.dominant_gate == "rejected_citation"
    assert result.per_gate_rejection_share["rejected_citation"] == pytest.approx(1.0)


def test_state_b_dominant_gate_tie_is_none() -> None:
    rows = (
        _channels(8, 2)
        + [_rejected("rejected_citation") for _ in range(10)]
        + [_rejected("rejected_no_change") for _ in range(10)]
    )
    result = score_hint_engagement(rows)
    assert result.verdict == "STATE_B_ADOPTION_REJECTED"
    assert result.dominant_gate is None  # argmax tie (DA-EII-11)


def test_state_c_direction_inconsistent() -> None:
    # 10 channels, each one +0.05 and one -0.05 adopted tick -> all cancel (ratio 0).
    rows: list[HintEngagementTraceRow] = []
    for c in range(10):
        rows.append(_adopted(f"k{c}", direction="strengthen", step=0.05))
        rows.append(_adopted(f"k{c}", direction="weaken", step=-0.05))
    result = score_hint_engagement(rows)
    assert result.verdict == "STATE_C_DIRECTION_INCONSISTENT"
    assert result.adoption_rate == pytest.approx(1.0)
    assert result.adopted_direction_consistency_rate == pytest.approx(0.0)


# --- INSTRUMENT_INCONCLUSIVE boundaries (補強 §6) ------------------------------


def test_stability_gate_below_n_min_is_inconclusive() -> None:
    # 19 emitted (< N_MIN=20) even though channels would be plenty.
    rows = [*_channels(9, 2), _adopted("k0")]  # 18 + 1 = 19 emitted
    assert len(rows) == N_MIN - 1
    result = score_hint_engagement(rows)
    assert result.verdict == "INSTRUMENT_INCONCLUSIVE"
    assert "stability gate" in result.notes


def test_stability_gate_at_n_min_passes_to_routing() -> None:
    # 20 emitted (== N_MIN) with 10 healthy channels -> routes (== floor passes).
    rows = _channels(10, 2)
    assert len(rows) == N_MIN
    result = score_hint_engagement(rows)
    assert result.verdict == "STATE_ALL_HEALTHY"


def test_channel_floor_is_global_stability_gate() -> None:
    """channels < CHANNEL_FLOOR -> INSTRUMENT_INCONCLUSIVE despite ample emitted ticks.

    7 channels (< 8) each adopted twice (14) + 6 rejected = 20 emitted. n_emitted meets
    N_MIN, but the eligible-channel count is below the floor, so the **global**
    stability gate fires (ADR §6 precedence first; 補強 §6).
    """
    rows = _channels(CHANNEL_FLOOR - 1, 2) + [
        _rejected("rejected_citation") for _ in range(6)
    ]
    result = score_hint_engagement(rows)
    assert result.n_eligible_channels == CHANNEL_FLOOR - 1
    assert result.n_emitted >= N_MIN
    assert result.verdict == "INSTRUMENT_INCONCLUSIVE"


def test_adoption_low_and_channel_below_floor_is_global_not_state_b() -> None:
    """The headline 補強 §6 case: adoption < THETA_A *and* channels < floor -> global.

    Adoption sits below θ_a (it would route to state (b) if it reached routing), but the
    eligible-channel count is below the floor, so the verdict is the global stability
    INSTRUMENT_INCONCLUSIVE — **not** STATE_B_ADOPTION_REJECTED.
    """
    rows = (
        _channels(CHANNEL_FLOOR - 1, 2)  # 14 adopted, 7 channels
        + [_rejected("rejected_citation") for _ in range(20)]  # adoption 14/34 < 0.5
    )
    result = score_hint_engagement(rows)
    assert result.adoption_rate is not None
    assert result.adoption_rate < 0.5
    assert result.n_eligible_channels < CHANNEL_FLOOR
    assert result.verdict == "INSTRUMENT_INCONCLUSIVE"
    assert result.verdict != "STATE_B_ADOPTION_REJECTED"


def test_channel_floor_at_boundary_passes() -> None:
    # Exactly CHANNEL_FLOOR channels (== floor) with enough emitted -> routes.
    rows = _channels(CHANNEL_FLOOR, 3)  # 8 channels x 3 = 24 emitted
    result = score_hint_engagement(rows)
    assert result.n_eligible_channels == CHANNEL_FLOOR
    assert result.verdict == "STATE_ALL_HEALTHY"


def test_emission_rate_boundary_tie_is_inconclusive() -> None:
    # emission_rate exactly == THETA_E (20/200) -> boundary tie -> INCONCLUSIVE.
    rows = _channels(8, 2) + [
        _adopted(f"k{c}") for c in range(4)
    ]  # 16 + 4 = 20 emitted, 8 channels
    n_not_emitted = 180  # 20 / (20 + 180) = 0.10 == THETA_E
    rows += [_not_emitted() for _ in range(n_not_emitted)]
    result = score_hint_engagement(rows)
    assert result.emission_rate == pytest.approx(THETA_E)
    assert result.verdict == "INSTRUMENT_INCONCLUSIVE"
    assert "boundary tie" in result.notes


# --- provenance / eligibility -------------------------------------------------


def test_provenance_false_is_inconclusive() -> None:
    rows = _channels(9, 3)
    bad = dataclasses.replace(rows[0], individual_layer_enabled=False)
    result = score_hint_engagement([*rows[1:], bad])
    assert result.verdict == "INSTRUMENT_INCONCLUSIVE"
    assert result.notes == "provenance_false"


def test_warmup_and_fallback_ticks_are_excluded_from_eligible() -> None:
    # A warmup tick and a fallback (non-ok) tick must not count toward emission.
    warmup = HintEngagementTraceRow(
        run_id="r",
        seed=1,
        individual_id="kant",
        tick=0,  # < WARMUP_TICKS
        llm_status="ok",
        exposed_entry_count=3,
        emitted=True,
        disposition="adopted",
        target_axis="self",
        target_key="kw",
        direction="strengthen",
        adopted_signed_step=0.05,
        individual_layer_enabled=True,
    )
    fallback = _not_emitted(llm_status="unavailable")
    zero_exposed = HintEngagementTraceRow(
        run_id="r",
        seed=1,
        individual_id="kant",
        tick=next(_TICKS),
        llm_status="ok",
        exposed_entry_count=0,
        emitted=True,
        disposition="adopted",
        target_axis="self",
        target_key="kz",
        direction="strengthen",
        adopted_signed_step=0.05,
        individual_layer_enabled=True,
    )
    base = _channels(9, 3)
    n_eligible = score_hint_engagement(base).n_eligible_ticks
    augmented = score_hint_engagement([*base, warmup, fallback, zero_exposed])
    # The three excluded ticks do not change the eligible population.
    assert augmented.n_eligible_ticks == n_eligible
