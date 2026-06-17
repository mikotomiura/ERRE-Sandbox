"""Loader + scorer coverage for the bond-affinity near-miss diagnostic (ADR 3.4).

CPU-only, synthetic fixtures. Covers the read round-trip (incl. nullable recency),
near-miss gate recompute, the stale-bond guard (HIGH-1), the cap-exposure join
(individual vs entry-linked, MED-3), the signed trust/clash split, the seed-paired
cross-arm contrast, and low-power → INCONCLUSIVE (never folded into (ii)).
"""

from __future__ import annotations

import duckdb

from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.relational.bond_affinity_trace_ddl import (
    TABLE_NAME,
    bootstrap_bond_affinity_trace_schema,
    build_bond_affinity_trace_rows,
    column_names,
)
from erre_sandbox.evidence.relational.loader import (
    identify_near_miss,
    read_bond_affinity_trace_rows,
    score_bond_affinity,
)
from erre_sandbox.evidence.saturation.trace_ddl import SaturationTraceRow
from erre_sandbox.schemas import RelationshipBond, Zone


def _bond(
    other: str,
    affinity: float,
    *,
    count: int = 6,
    last_tick: int | None = 5,
    zone: Zone | None = Zone.STUDY,
) -> RelationshipBond:
    return RelationshipBond(
        other_agent_id=other,
        affinity=affinity,
        ichigo_ichie_count=count,
        last_interaction_tick=last_tick,
        last_interaction_zone=zone,
    )


def _sat_row(
    individual: str, tick: int, *, offset: float, seed: int = 1, run_id: str = "on"
) -> SaturationTraceRow:
    """A saturation row whose ``|modulated - base_floor|`` equals *offset*."""
    return SaturationTraceRow(
        run_id=run_id,
        seed=seed,
        individual_id=individual,
        axis="self",
        key="k",
        tick=tick,
        base_floor_value=0.5,
        modulated_value=0.5 + offset,
        floor_fingerprint_hash="h",
        individual_layer_enabled=True,
    )


def _bond_row(individual, other, tick, affinity, *, count, last_tick, run_id, seed):
    rows = build_bond_affinity_trace_rows(
        [_bond(other, affinity, count=count, last_tick=last_tick)],
        run_id=run_id,
        seed=seed,
        individual_id=individual,
        tick=tick,
        individual_layer_enabled=True,
    )
    return rows[0]


def test_read_round_trip_all_columns_incl_nullable(tmp_path) -> None:
    con = duckdb.connect(str(tmp_path / "rt.duckdb"))
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {METRICS_SCHEMA}")
    bootstrap_bond_affinity_trace_schema(con, METRICS_SCHEMA)
    built = build_bond_affinity_trace_rows(
        [
            _bond("nietzsche", -0.44, count=7, last_tick=9, zone=Zone.AGORA),
            _bond("hume", 0.20, count=3, last_tick=None, zone=None),
        ],
        run_id="on_run",
        seed=2**64 - 1,
        individual_id="kant",
        tick=12,
        individual_layer_enabled=True,
    )
    cols = column_names()
    insert_sql = (
        f"INSERT INTO {METRICS_SCHEMA}.{TABLE_NAME} "  # noqa: S608 — static identifiers, test
        f"({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    )
    for row in built:
        con.execute(insert_sql, row.to_row())

    read = read_bond_affinity_trace_rows(con, schema=METRICS_SCHEMA)
    by_other = {r.other_agent_id: r for r in read}
    assert by_other["nietzsche"].affinity == -0.44
    assert by_other["nietzsche"].seed == 2**64 - 1
    assert by_other["nietzsche"].last_interaction_tick == 9
    assert by_other["nietzsche"].last_interaction_zone == "agora"
    # Nullable recency round-trips as None.
    assert by_other["hume"].last_interaction_tick is None
    assert by_other["hume"].last_interaction_zone is None


def test_near_miss_gate_recomputed_from_raw() -> None:
    sat = [_sat_row("kant", 10, offset=0.15)]
    rows = [
        # below affinity gate AND interaction-count gate satisfied -> near-miss
        _bond_row("kant", "a", 10, 0.44, count=6, last_tick=10, run_id="on", seed=1),
        # affinity already promoted (>=0.45) -> excluded
        _bond_row("kant", "b", 10, 0.46, count=9, last_tick=10, run_id="on", seed=1),
        # interaction-count gate not met -> excluded
        _bond_row("kant", "c", 10, 0.40, count=5, last_tick=10, run_id="on", seed=1),
    ]
    obs = identify_near_miss(rows, sat)
    assert {o.other_agent_id for o in obs} == {"a"}


def test_exposure_join_individual_vs_entry() -> None:
    # Two saturated entries at (kant, 10): entry count = 2, individual exposure True.
    sat = [
        _sat_row("kant", 10, offset=0.15),
        _sat_row("kant", 10, offset=0.15),
    ]
    rows = [
        _bond_row("kant", "a", 10, 0.44, count=6, last_tick=10, run_id="on", seed=1)
    ]
    obs = identify_near_miss(rows, sat)
    assert len(obs) == 1
    assert obs[0].under_individual_exposure is True
    assert obs[0].entry_exposure_count == 2
    # A bond at a tick with no cap-saturated entry is dropped under require_exposure.
    rows_no_exp = [
        _bond_row("kant", "a", 20, 0.44, count=6, last_tick=20, run_id="on", seed=1)
    ]
    assert identify_near_miss(rows_no_exp, sat) == []


def test_stale_guard_excludes_parked_bond() -> None:
    """A bond near 0.45 from before the exposure, not touched and flat, is excluded."""
    sat = [_sat_row("kant", 30, offset=0.15)]
    # Flat affinity series across ticks; last interaction long before tick 30.
    parked = [
        _bond_row("kant", "a", t, 0.44, count=7, last_tick=5, run_id="on", seed=1)
        for t in (26, 27, 28, 29, 30)
    ]
    assert identify_near_miss(parked, sat) == []
    # Same bond but touched at the exposure tick -> kept (fresh).
    fresh = [
        *parked[:-1],
        _bond_row("kant", "a", 30, 0.44, count=7, last_tick=30, run_id="on", seed=1),
    ]
    obs = identify_near_miss(fresh, sat)
    assert len(obs) == 1
    assert obs[0].touched_this_tick


def test_signed_split_trust_vs_clash() -> None:
    sat = [_sat_row("kant", 10, offset=0.15)]
    rows = [
        _bond_row("kant", "a", 10, 0.44, count=6, last_tick=10, run_id="on", seed=1),
        _bond_row("kant", "b", 10, -0.43, count=6, last_tick=10, run_id="on", seed=1),
    ]
    result = score_bond_affinity(rows, sat, arm_of={"on": "ON"}, min_near_miss_n=1)
    assert result.on_stats is not None
    assert result.on_stats.n_trust == 1
    assert result.on_stats.n_clash == 1


def test_low_power_is_inconclusive_not_ii() -> None:
    sat = [_sat_row("kant", 10, offset=0.15, run_id="on")]
    rows = [
        _bond_row("kant", "a", 10, 0.44, count=6, last_tick=10, run_id="on", seed=1)
    ]
    # default min floor (10) not met by a single observation.
    result = score_bond_affinity(rows, sat, arm_of={"on": "ON", "off": "OFF"})
    assert result.verdict == "INCONCLUSIVE"
    assert "low power" in result.notes


def _arm_rows(run_id: str, individual: str, affinities, *, seed: int):
    """One near-miss bond per affinity at distinct dyads, all touched at tick 10."""
    rows = []
    for i, aff in enumerate(affinities):
        rows.append(
            _bond_row(
                individual,
                f"other{i}",
                10,
                aff,
                count=6,
                last_tick=10,
                run_id=run_id,
                seed=seed,
            )
        )
    return rows


def test_cross_arm_i_leaning_when_on_approaches_more() -> None:
    sat = [
        _sat_row("kant", 10, offset=0.15, run_id="on", seed=1),
        _sat_row("kant", 10, offset=0.15, run_id="off", seed=1),
    ]
    # ON max|aff| ~0.44, OFF max|aff| ~0.20 -> ON approaches the 0.45 gate more.
    on = _arm_rows("on", "kant", [0.30, 0.44] * 6, seed=1)
    off = _arm_rows("off", "kant", [0.15, 0.20] * 6, seed=1)
    result = score_bond_affinity(
        on + off,
        sat,
        arm_of={"on": "ON", "off": "OFF"},
        min_near_miss_n=5,
        min_paired_seeds=1,
    )
    assert result.verdict == "(i)-LEANING"
    assert result.median_paired_gap is not None
    assert result.median_paired_gap > 0


def test_cross_arm_ii_leaning_when_arms_match() -> None:
    sat = [
        _sat_row("kant", 10, offset=0.15, run_id="on", seed=1),
        _sat_row("kant", 10, offset=0.15, run_id="off", seed=1),
    ]
    on = _arm_rows("on", "kant", [0.30, 0.40] * 6, seed=1)
    off = _arm_rows("off", "kant", [0.30, 0.40] * 6, seed=1)
    result = score_bond_affinity(
        on + off,
        sat,
        arm_of={"on": "ON", "off": "OFF"},
        min_near_miss_n=5,
        min_paired_seeds=1,
    )
    assert result.verdict == "(ii)-LEANING"


def test_no_paired_seed_is_inconclusive() -> None:
    sat = [
        _sat_row("kant", 10, offset=0.15, run_id="on", seed=1),
        _sat_row("kant", 10, offset=0.15, run_id="off", seed=2),
    ]
    on = _arm_rows("on", "kant", [0.40] * 12, seed=1)
    off = _arm_rows("off", "kant", [0.40] * 12, seed=2)  # different seed
    result = score_bond_affinity(
        on + off,
        sat,
        arm_of={"on": "ON", "off": "OFF"},
        min_near_miss_n=5,
        min_paired_seeds=1,
    )
    assert result.verdict == "INCONCLUSIVE"
    assert result.paired_seeds == []
    assert "paired seeds" in result.notes


def test_total_rows_equals_sum_of_per_tick_bonds(tmp_path) -> None:
    """Carrier A volume monitor (the ``--dry-run`` substitute, ADR section 3.3).

    Carrier A emits one row per bond per tick, so the persisted row count must equal
    ``Σ_tick |bonds(tick)|``. This makes the (large) volume characteristic explicit /
    checkable in CI since the eval CLI has no ``--dry-run`` coverage report."""
    con = duckdb.connect(str(tmp_path / "vol.duckdb"))
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {METRICS_SCHEMA}")
    bootstrap_bond_affinity_trace_schema(con, METRICS_SCHEMA)
    cols = column_names()
    insert_sql = (
        f"INSERT INTO {METRICS_SCHEMA}.{TABLE_NAME} "  # noqa: S608 — static identifiers, test
        f"({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    )
    # Tick -> number of bonds that tick (e.g. dyads accreting over time).
    per_tick_bonds = {10: 1, 11: 2, 12: 3, 13: 3}
    expected_total = sum(per_tick_bonds.values())
    for tick, n in per_tick_bonds.items():
        rows = build_bond_affinity_trace_rows(
            [_bond(f"o{i}", 0.30) for i in range(n)],
            run_id="on",
            seed=1,
            individual_id="kant",
            tick=tick,
            individual_layer_enabled=True,
        )
        for row in rows:
            con.execute(insert_sql, row.to_row())
    count = con.execute(
        f"SELECT COUNT(*) FROM {METRICS_SCHEMA}.{TABLE_NAME}"  # noqa: S608 — static identifiers
    ).fetchone()
    assert count is not None
    assert count[0] == expected_total


def test_exposure_does_not_leak_across_arms() -> None:
    """An ON-arm cap exposure must not make an OFF-arm same-tick bond a near-miss."""
    # Only the ON run has a cap-saturated entry at (kant, 10).
    sat = [_sat_row("kant", 10, offset=0.15, run_id="on", seed=1)]
    on = _bond_row("kant", "a", 10, 0.44, count=6, last_tick=10, run_id="on", seed=1)
    off = _bond_row("kant", "a", 10, 0.44, count=6, last_tick=10, run_id="off", seed=1)
    obs = identify_near_miss([on, off], sat)
    # Only the ON bond joins the exposure; the OFF bond does not inherit it.
    assert {o.run_id for o in obs} == {"on"}


def test_exposure_does_not_leak_across_seeds() -> None:
    """A seed-1 cap exposure must not make a seed-2 same-tick bond a near-miss."""
    sat = [_sat_row("kant", 10, offset=0.15, run_id="on", seed=1)]
    s1 = _bond_row("kant", "a", 10, 0.44, count=6, last_tick=10, run_id="on", seed=1)
    s2 = _bond_row("kant", "a", 10, 0.44, count=6, last_tick=10, run_id="on", seed=2)
    obs = identify_near_miss([s1, s2], sat)
    assert {o.seed for o in obs} == {1}


def test_clash_bond_rising_in_magnitude_is_fresh() -> None:
    """A clash bond moving -0.30 -> -0.44 (|aff| rising) is fresh via the abs slope."""
    sat = [_sat_row("kant", 30, offset=0.15, run_id="on", seed=1)]
    # |affinity| rises into tick 30 though signed affinity falls; never touched.
    series = [
        _bond_row("kant", "a", t, aff, count=7, last_tick=5, run_id="on", seed=1)
        for t, aff in [(26, -0.30), (27, -0.34), (28, -0.38), (29, -0.41), (30, -0.44)]
    ]
    obs = identify_near_miss(series, sat)
    assert len(obs) == 1
    assert obs[0].lagged_slope > 0  # abs(affinity) slope, not signed
    assert not obs[0].touched_this_tick


def test_provenance_false_is_inconclusive() -> None:
    sat = [_sat_row("kant", 10, offset=0.15, run_id="on", seed=1)]
    flagged = build_bond_affinity_trace_rows(
        [_bond("a", 0.44, count=6, last_tick=10)],
        run_id="on",
        seed=1,
        individual_id="kant",
        tick=10,
        individual_layer_enabled=False,  # provenance-false row
    )
    result = score_bond_affinity(
        flagged, sat, arm_of={"on": "ON"}, min_near_miss_n=1, min_paired_seeds=1
    )
    assert result.verdict == "INCONCLUSIVE"
    assert "provenance_false" in result.notes


def test_min_paired_seeds_floor_is_inconclusive() -> None:
    """A single paired seed (default floor 2) is not seed-reproducible."""
    sat = [
        _sat_row("kant", 10, offset=0.15, run_id="on", seed=1),
        _sat_row("kant", 10, offset=0.15, run_id="off", seed=1),
    ]
    on = _arm_rows("on", "kant", [0.40] * 12, seed=1)
    off = _arm_rows("off", "kant", [0.40] * 12, seed=1)
    result = score_bond_affinity(
        on + off, sat, arm_of={"on": "ON", "off": "OFF"}, min_near_miss_n=5
    )  # default min_paired_seeds=2, only seed 1 is paired
    assert result.verdict == "INCONCLUSIVE"
    assert "paired seeds" in result.notes


def test_neutral_affinity_counted_separately() -> None:
    """``affinity == 0.0`` is neutral; n_trust + n_clash + n_neutral == n."""
    sat = [_sat_row("kant", 10, offset=0.15, run_id="on", seed=1)]
    rows = [
        _bond_row("kant", "a", 10, 0.30, count=6, last_tick=10, run_id="on", seed=1),
        _bond_row("kant", "b", 10, -0.30, count=6, last_tick=10, run_id="on", seed=1),
        _bond_row("kant", "c", 10, 0.0, count=6, last_tick=10, run_id="on", seed=1),
    ]
    result = score_bond_affinity(
        rows, sat, arm_of={"on": "ON"}, min_near_miss_n=1, min_paired_seeds=1
    )
    s = result.on_stats
    assert s is not None
    assert (s.n_trust, s.n_clash, s.n_neutral) == (1, 1, 1)
    assert s.n_trust + s.n_clash + s.n_neutral == s.n
