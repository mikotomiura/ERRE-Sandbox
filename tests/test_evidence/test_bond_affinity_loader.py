"""Loader + scorer coverage for the bond-affinity near-miss diagnostic.

CPU-only, synthetic fixtures. Two layers:

* **descriptive** (PR #25, byte-invariant): the read round-trip (incl. nullable
  recency), the near-miss gate recompute, the stale-bond guard (HIGH-1), the
  cap-exposure join (individual vs entry-linked, MED-3), the signed trust/clash split,
  and the no-exposure-leak invariants. These exercise ``identify_near_miss`` /
  ``_cell_stats`` whose statistics are unchanged by the v2 decision layer.
* **decision (v2, freeze ADR §1-§3)**: the signal-to-noise / non-circular null
  hierarchy — replicate-cell power gate (MED-1), 2-of-3 paired-seed floor (MED-3),
  ON-noise sanity, materiality floor + ratio with degenerate-null handling (HIGH-2),
  rank-non-overlap, and the six closed routing states incl. INCONCLUSIVE_MIXED_SEED
  (HIGH-1) and provenance-false → INVALID_MEASUREMENT (ADR §7, was INCONCLUSIVE).
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
    BondAffinityProbeResult,
    CellStats,
    has_eligible_near_miss,
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


# --- v2 matrix fixture helpers ------------------------------------------------


def _matrix(cells, *, individual="kant", tick=10):
    """Build (bond_rows, sat_rows, arm_of, replicate_of) for a list of cell specs.

    Each cell spec is ``(seed, arm, replicate, abs_aff, sign, n)``: *n* near-miss bonds
    at distinct dyads, all touched at *tick* with ``|affinity| == abs_aff`` and the
    given *sign*, plus one cap-saturated saturation entry for the cell's run. A cell
    filled with *n* equal magnitudes has ``p95 == abs_aff`` exactly, so the per-seed S
    values are deterministic.
    """
    bond_rows: list = []
    sat_rows: list = []
    arm_of: dict[str, str] = {}
    replicate_of: dict[str, int] = {}
    for seed, arm, replicate, abs_aff, sign, n in cells:
        run_id = f"s{seed}_{arm}{replicate}"
        arm_of[run_id] = arm
        replicate_of[run_id] = replicate
        bond_rows.extend(
            _bond_row(
                individual,
                f"o{i}",
                tick,
                sign * abs_aff,
                count=6,
                last_tick=tick,
                run_id=run_id,
                seed=seed,
            )
            for i in range(n)
        )
        sat_rows.append(
            _sat_row(individual, tick, offset=0.15, seed=seed, run_id=run_id)
        )
    return bond_rows, sat_rows, arm_of, replicate_of


def _seed_quad(seed, on0, off0, off1, on1, *, n=10):
    """Four powered cells for one seed at the given p95 proximities."""
    return [
        (seed, "ON", 0, on0, 1.0, n),
        (seed, "OFF", 0, off0, 1.0, n),
        (seed, "OFF", 1, off1, 1.0, n),
        (seed, "ON", 1, on1, 1.0, n),
    ]


def _find_cell(result: BondAffinityProbeResult, seed, arm, replicate) -> CellStats:
    for c in result.cells:
        if (c.seed, c.arm, c.replicate) == (seed, arm, replicate):
            return c
    msg = f"cell ({seed}, {arm}, {replicate}) not in result"
    raise AssertionError(msg)


# --- descriptive layer (PR #25, byte-invariant) -------------------------------


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


def test_signed_split_trust_vs_clash() -> None:
    """The per-cell signed split is unchanged from PR #25 (read via cells now)."""
    sat = [_sat_row("kant", 10, offset=0.15, run_id="on", seed=1)]
    rows = [
        _bond_row("kant", "a", 10, 0.44, count=6, last_tick=10, run_id="on", seed=1),
        _bond_row("kant", "b", 10, -0.43, count=6, last_tick=10, run_id="on", seed=1),
    ]
    result = score_bond_affinity(rows, sat, arm_of={"on": "ON"}, replicate_of={"on": 0})
    cell = _find_cell(result, 1, "ON", 0)
    assert cell.n_trust == 1
    assert cell.n_clash == 1


def test_neutral_affinity_counted_separately() -> None:
    """``affinity == 0.0`` is neutral; n_trust + n_clash + n_neutral == n."""
    sat = [_sat_row("kant", 10, offset=0.15, run_id="on", seed=1)]
    rows = [
        _bond_row("kant", "a", 10, 0.30, count=6, last_tick=10, run_id="on", seed=1),
        _bond_row("kant", "b", 10, -0.30, count=6, last_tick=10, run_id="on", seed=1),
        _bond_row("kant", "c", 10, 0.0, count=6, last_tick=10, run_id="on", seed=1),
    ]
    result = score_bond_affinity(rows, sat, arm_of={"on": "ON"}, replicate_of={"on": 0})
    cell = _find_cell(result, 1, "ON", 0)
    assert (cell.n_trust, cell.n_clash, cell.n_neutral) == (1, 1, 1)
    assert cell.n_trust + cell.n_clash + cell.n_neutral == cell.n


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


# --- Phase 0 preflight helper (freeze ADR §5) ---------------------------------


def test_has_eligible_near_miss_is_bare_gate() -> None:
    """Phase 0 is now bare-gate (superseding §5'): exposure is no longer required."""
    rows = [
        _bond_row("kant", "a", 10, 0.44, count=6, last_tick=10, run_id="on", seed=1)
    ]
    # A bare near-miss is eligible with or without cap exposure.
    assert has_eligible_near_miss(rows, []) is True
    sat = [_sat_row("kant", 10, offset=0.15, run_id="on", seed=1)]
    assert has_eligible_near_miss(rows, sat) is True
    # A bond above the affinity gate is not a near-miss -> not eligible.
    promoted = [
        _bond_row("kant", "a", 10, 0.46, count=6, last_tick=10, run_id="on", seed=1)
    ]
    assert has_eligible_near_miss(promoted, []) is False


# --- v2 decision layer: routing states ----------------------------------------


def test_provenance_false_is_invalid_measurement() -> None:
    """A provenance-false row routes INVALID_MEASUREMENT (ADR §7; was INCONCLUSIVE)."""
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
        flagged, sat, arm_of={"on": "ON"}, replicate_of={"on": 0}
    )
    assert result.verdict == "INVALID_MEASUREMENT"
    assert "provenance_false" in result.notes


def test_no_near_miss_routes_inconclusive_no_near_miss() -> None:
    """All bonds above the affinity gate -> empty bare substrate (bare-gate §2'.2).

    Under the superseding bare-gate the exposure join no longer filters, so an empty
    substrate now means the bonds themselves fail the gate (here |aff| >= 0.45,
    i.e. already promoted), not "no cap exposure".
    """
    bond_rows, _sat, arm_of, replicate_of = _matrix(
        _seed_quad(1, 0.50, 0.50, 0.50, 0.50) + _seed_quad(2, 0.50, 0.50, 0.50, 0.50)
    )
    result = score_bond_affinity(
        bond_rows, [], arm_of=arm_of, replicate_of=replicate_of
    )
    assert result.verdict == "INCONCLUSIVE_NO_NEAR_MISS"
    assert all(c.n == 0 for c in result.cells)


def test_low_power_too_few_paired_seeds_via_cell_granularity() -> None:
    """One under-floor replicate cell drops its whole seed (4-cell power, MED-1)."""
    # seed 1: all four cells powered (n=10 >= frozen floor). seed 2: ON r0 has only n=4,
    # so even with three strong cells seed 2 is not paired -> only seed 1 paired (< 2).
    cells = [
        *_seed_quad(1, 0.40, 0.20, 0.20, 0.40),
        (2, "ON", 0, 0.40, 1.0, 4),  # under the frozen floor -> seed 2 not paired
        (2, "OFF", 0, 0.20, 1.0, 10),
        (2, "OFF", 1, 0.20, 1.0, 10),
        (2, "ON", 1, 0.40, 1.0, 10),
    ]
    bond_rows, sat_rows, arm_of, replicate_of = _matrix(cells)
    result = score_bond_affinity(
        bond_rows, sat_rows, arm_of=arm_of, replicate_of=replicate_of
    )
    assert result.verdict == "INCONCLUSIVE_LOW_POWER"
    assert result.paired_seeds == (1,)
    assert "paired seed" in result.notes


def test_low_power_on_noise_sanity_violation() -> None:
    """ON-specific run-to-run noise above the OFF/OFF floor downgrades to LOW_POWER."""
    # S(ON/ON) = |0.44 - 0.20| = 0.24, S(OFF/OFF) = 0 -> on_noise_ok False.
    cells = _seed_quad(1, 0.44, 0.30, 0.30, 0.20) + _seed_quad(
        2, 0.44, 0.30, 0.30, 0.20
    )
    bond_rows, sat_rows, arm_of, replicate_of = _matrix(cells)
    result = score_bond_affinity(
        bond_rows, sat_rows, arm_of=arm_of, replicate_of=replicate_of
    )
    assert result.verdict == "INCONCLUSIVE_LOW_POWER"
    assert result.on_noise_ok is False
    assert "ON-specific noise" in result.notes


def test_i_leaning_non_degenerate_null() -> None:
    """ON approaches the gate above a real noise floor (ratio path) -> (i)-LEANING."""
    cells = _seed_quad(1, 0.44, 0.20, 0.16, 0.44) + _seed_quad(
        2, 0.44, 0.20, 0.16, 0.44
    )
    bond_rows, sat_rows, arm_of, replicate_of = _matrix(cells)
    result = score_bond_affinity(
        bond_rows, sat_rows, arm_of=arm_of, replicate_of=replicate_of
    )
    assert result.verdict == "(i)-LEANING"
    assert result.paired_seeds == (1, 2)
    assert result.null_degenerate is False
    assert result.magnitude_ok is True
    assert result.rank_ok is True
    assert result.on_noise_ok is True
    # null hierarchy exposed (LOW-1): S(OFF/OFF) ~= 0.04, S(ON/ON) ~= 0.
    assert result.max_off_off_null is not None
    assert abs(result.max_off_off_null - 0.04) < 1e-9
    assert result.max_on_on_null is not None
    assert abs(result.max_on_on_null) < 1e-9


def test_i_leaning_degenerate_floor_when_null_all_zero() -> None:
    """An all-zero OFF/OFF null falls back to the absolute materiality floor."""
    cells = _seed_quad(1, 0.30, 0.20, 0.20, 0.30) + _seed_quad(
        2, 0.30, 0.20, 0.20, 0.30
    )
    bond_rows, sat_rows, arm_of, replicate_of = _matrix(cells)
    result = score_bond_affinity(
        bond_rows, sat_rows, arm_of=arm_of, replicate_of=replicate_of
    )
    assert result.verdict == "(i)-LEANING"
    assert result.null_degenerate is True  # max S(OFF/OFF) == 0


def test_ii_leaning_when_separation_below_materiality() -> None:
    """A separation under the materiality floor -> (ii)-LEANING (not decoupling)."""
    cells = _seed_quad(1, 0.21, 0.20, 0.18, 0.21) + _seed_quad(
        2, 0.21, 0.20, 0.18, 0.21
    )
    bond_rows, sat_rows, arm_of, replicate_of = _matrix(cells)
    result = score_bond_affinity(
        bond_rows, sat_rows, arm_of=arm_of, replicate_of=replicate_of
    )
    assert result.verdict == "(ii)-LEANING"
    assert result.magnitude_ok is False


def test_near_zero_null_does_not_fake_i_leaning_high2() -> None:
    """A tiny non-zero null must not let a sub-materiality signal pass (ratio blow-up).

    S(ON-OFF)=0.015 (< floor 0.02), S(OFF/OFF)=1e-6. The naive ratio 0.015/1e-6=15000
    would clear R_MIN_BOND; the degenerate-null floor (HIGH-2) instead requires the
    absolute materiality floor, which 0.015 fails -> (ii)-LEANING, never (i).
    """
    cells = _seed_quad(1, 0.215, 0.200000, 0.200001, 0.215) + _seed_quad(
        2, 0.215, 0.200000, 0.200001, 0.215
    )
    bond_rows, sat_rows, arm_of, replicate_of = _matrix(cells)
    result = score_bond_affinity(
        bond_rows, sat_rows, arm_of=arm_of, replicate_of=replicate_of
    )
    assert result.verdict == "(ii)-LEANING"
    assert result.null_degenerate is True
    assert result.magnitude_ok is False


def test_mixed_seed_when_magnitude_passes_but_rank_fails() -> None:
    """Median clears magnitude but a per-seed signal sinks into noise -> MIXED_SEED."""
    # seed 1 strong (S_on_off=0.30, S_off_off=0.05); seed 2 weak (S_on_off=0.01).
    cells = _seed_quad(1, 0.44, 0.14, 0.09, 0.44) + _seed_quad(
        2, 0.30, 0.29, 0.29, 0.30
    )
    bond_rows, sat_rows, arm_of, replicate_of = _matrix(cells)
    result = score_bond_affinity(
        bond_rows, sat_rows, arm_of=arm_of, replicate_of=replicate_of
    )
    assert result.verdict == "INCONCLUSIVE_MIXED_SEED"
    assert result.magnitude_ok is True
    assert result.rank_ok is False


def test_unmapped_run_rows_are_dropped() -> None:
    """A run absent from arm_of/replicate_of cannot be placed in the matrix."""
    cells = _seed_quad(1, 0.44, 0.20, 0.16, 0.44) + _seed_quad(
        2, 0.44, 0.20, 0.16, 0.44
    )
    bond_rows, sat_rows, arm_of, replicate_of = _matrix(cells)
    # Drop one run from the maps -> its seed loses a cell -> not paired.
    del arm_of["s2_ON0"]
    del replicate_of["s2_ON0"]
    result = score_bond_affinity(
        bond_rows, sat_rows, arm_of=arm_of, replicate_of=replicate_of
    )
    assert result.verdict == "INCONCLUSIVE_LOW_POWER"
    assert result.paired_seeds == (1,)


def test_all_unmapped_with_eligible_near_miss_is_invalid() -> None:
    """Eligible near-miss exist but every run is unmapped -> broken assembly (MED-2).

    A genuinely empty substrate routes NO_NEAR_MISS; an empty *matrix* over a non-empty
    substrate (all runs absent from the maps) is an assembly error -> INVALID, never
    masked as "no near-miss".
    """
    cells = _seed_quad(1, 0.44, 0.20, 0.16, 0.44)
    bond_rows, sat_rows, _arm_of, _replicate_of = _matrix(cells)
    result = score_bond_affinity(bond_rows, sat_rows, arm_of={}, replicate_of={})
    assert result.verdict == "INVALID_MEASUREMENT"
    assert "none mapped" in result.notes


def test_has_eligible_near_miss_false_on_provenance_false() -> None:
    """A provenance-false (flag-off) smoke is not diagnostically eligible (LOW-1)."""
    sat = [_sat_row("kant", 10, offset=0.15, run_id="on", seed=1)]
    flagged = build_bond_affinity_trace_rows(
        [_bond("a", 0.44, count=6, last_tick=10)],
        run_id="on",
        seed=1,
        individual_id="kant",
        tick=10,
        individual_layer_enabled=False,
    )
    assert has_eligible_near_miss(flagged, sat) is False


# --- estimand-redesign §2'.2/§2'.3/§3': bare-gate, secondary, truncation guard --------


def _truncation_matrix(*, on_r0_promoted: int, off_r0_promoted: int):
    """Two paired seeds, p95 equal across arms (magnitude unmet), ON r0 promotion-heavy.

    Each cell holds 10 near-miss bonds at |aff|=0.30 (so every S(ON-OFF)=0 → magnitude
    unmet → the (ii) route is reached and the truncation guard is evaluated). Promoted
    bonds (|aff|=0.50, gate met) are added to the ON r0 / OFF r0 cells over ticks 11-14
    to drive the promotion incidence ρ.
    """
    bond_rows: list = []
    arm_of: dict[str, str] = {}
    replicate_of: dict[str, int] = {}
    for seed in (1, 2):
        for arm, replicate in (("ON", 0), ("OFF", 0), ("OFF", 1), ("ON", 1)):
            run_id = f"s{seed}_{arm}{replicate}"
            arm_of[run_id] = arm
            replicate_of[run_id] = replicate
            bond_rows.extend(
                _bond_row(
                    "kant",
                    f"n{i}",
                    10,
                    0.30,
                    count=6,
                    last_tick=10,
                    run_id=run_id,
                    seed=seed,
                )
                for i in range(10)
            )
            promoted = (
                on_r0_promoted
                if (arm, replicate) == ("ON", 0)
                else off_r0_promoted
                if (arm, replicate) == ("OFF", 0)
                else 0
            )
            bond_rows.extend(
                _bond_row(
                    "kant",
                    f"p{j}",
                    11 + (j % 4),
                    0.50,
                    count=6,
                    last_tick=11 + (j % 4),
                    run_id=run_id,
                    seed=seed,
                )
                for j in range(promoted)
            )
    return bond_rows, arm_of, replicate_of


def test_truncation_guard_degenerate_fires_inconclusive_truncated() -> None:
    """ON drains its near-miss pool (ρ(OFF)=0) -> INCONCLUSIVE_TRUNCATED, not (ii)."""
    bond_rows, arm_of, replicate_of = _truncation_matrix(
        on_r0_promoted=6, off_r0_promoted=0
    )
    result = score_bond_affinity(
        bond_rows, [], arm_of=arm_of, replicate_of=replicate_of
    )
    assert result.verdict == "INCONCLUSIVE_TRUNCATED"
    assert result.truncation_guard_fired is True
    assert result.magnitude_ok is False
    # degenerate ρ(OFF)=0 -> imbalance ratio undefined (None), guard via the count test.
    assert result.promotion_imbalance is None
    assert all(v > 0 for v in result.promotion_incidence_on.values())
    assert all(v == 0 for v in result.promotion_incidence_off.values())


def test_truncation_guard_ratio_fires_inconclusive_truncated() -> None:
    """ON ρ over 2x OFF ρ (non-degenerate) -> INCONCLUSIVE_TRUNCATED via the ratio."""
    bond_rows, arm_of, replicate_of = _truncation_matrix(
        on_r0_promoted=8, off_r0_promoted=2
    )
    result = score_bond_affinity(
        bond_rows, [], arm_of=arm_of, replicate_of=replicate_of
    )
    assert result.verdict == "INCONCLUSIVE_TRUNCATED"
    assert result.truncation_guard_fired is True
    assert result.promotion_imbalance is not None
    assert result.promotion_imbalance > 2.0


def test_truncation_guard_passes_yields_ii_leaning() -> None:
    """No ON promotion imbalance -> the (ii) route is not suppressed (guard passes)."""
    bond_rows, arm_of, replicate_of = _truncation_matrix(
        on_r0_promoted=0, off_r0_promoted=0
    )
    result = score_bond_affinity(
        bond_rows, [], arm_of=arm_of, replicate_of=replicate_of
    )
    assert result.verdict == "(ii)-LEANING"
    assert result.truncation_guard_fired is False


def test_truncation_guard_not_applied_to_i_leaning() -> None:
    """Even a promotion imbalance does not block (i)-LEANING (asymmetric guard, §3')."""
    # (i)-LEANING magnitude path (ON 0.44 vs OFF 0.20/0.16), plus heavy ON r0 promotion.
    bond_rows, sat_rows, arm_of, replicate_of = _matrix(
        _seed_quad(1, 0.44, 0.20, 0.16, 0.44) + _seed_quad(2, 0.44, 0.20, 0.16, 0.44)
    )
    for seed in (1, 2):
        run_id = f"s{seed}_ON0"
        bond_rows.extend(
            _bond_row(
                "kant",
                f"p{j}",
                11 + (j % 4),
                0.50,
                count=6,
                last_tick=11 + (j % 4),
                run_id=run_id,
                seed=seed,
            )
            for j in range(8)
        )
    result = score_bond_affinity(
        bond_rows, sat_rows, arm_of=arm_of, replicate_of=replicate_of
    )
    assert result.verdict == "(i)-LEANING"
    assert result.truncation_guard_fired is False


def test_secondary_cap_exposed_split_is_descriptive() -> None:
    """Within-cell near-miss splits cap-exposed vs non-exposed (§2'.3, descriptive)."""
    # 6 near-miss at tick 10 (cap-saturated), 4 at tick 20 (no saturation there).
    sat = [_sat_row("kant", 10, offset=0.15, run_id="on", seed=1)]
    rows = [
        _bond_row("kant", f"e{i}", 10, 0.44, count=6, last_tick=10, run_id="on", seed=1)
        for i in range(6)
    ]
    rows += [
        _bond_row("kant", f"u{i}", 20, 0.44, count=6, last_tick=20, run_id="on", seed=1)
        for i in range(4)
    ]
    result = score_bond_affinity(rows, sat, arm_of={"on": "ON"}, replicate_of={"on": 0})
    cell = _find_cell(result, 1, "ON", 0)
    assert cell.n == 10
    assert cell.cap_exposed_n == 6
    assert cell.cap_unexposed_n == 4
    assert cell.cap_exposed_p95_abs is not None
    assert cell.cap_unexposed_p95_abs is not None


def test_fresh_sensitivity_and_promotion_fields_reported() -> None:
    """n_no_fresh >= n, fresh drop counted, and promotion incidence over raw ticks."""
    sat = [_sat_row("kant", 10, offset=0.15, run_id="on", seed=1)]
    # one fresh near-miss (touched) + one stale parked one (dropped by fresh guard).
    rows = [
        _bond_row(
            "kant", "fresh", 10, 0.44, count=6, last_tick=10, run_id="on", seed=1
        ),
        *[
            _bond_row(
                "kant", "park", t, 0.44, count=7, last_tick=2, run_id="on", seed=1
            )
            for t in (6, 7, 8, 9, 10)
        ],
        # a promoted dyad at tick 11 (leaves the near-miss pool).
        _bond_row("kant", "prom", 11, 0.50, count=6, last_tick=11, run_id="on", seed=1),
    ]
    result = score_bond_affinity(rows, sat, arm_of={"on": "ON"}, replicate_of={"on": 0})
    cell = _find_cell(result, 1, "ON", 0)
    assert cell.n == 1  # only the fresh near-miss
    assert cell.n_no_fresh >= 2  # fresh + parked both pass the bare gate without fresh
    assert cell.n_fresh_dropped == cell.n_no_fresh - cell.n
    assert cell.promoted_dyads == 1
    assert cell.distinct_ticks == 1  # the near-miss substrate spans only tick 10
    assert cell.promotion_incidence is not None
