"""Capture-level assembler coverage for ``score_bond_affinity_captures`` (D1/D3).

The pure ``score_bond_affinity`` (PR #26) is arm/replicate-blind; the routing of the
six closed verdict states over a *coherent* matrix is covered by
``test_bond_affinity_loader``. This file focuses on what the thin captures wrapper
*adds*: the matrix-integrity gate the flat scorer cannot see — a duplicate
``(seed, arm, replicate)`` sidecar key and a ``run_id`` shared across two captures both
route to ``INVALID_MEASUREMENT`` (mirroring the live-carry scorer's ``_assemble_matrix``
incoherence handling) — plus the delegation path: a coherent 12-cell matrix flows
straight through to the scorer, an incomplete one to ``INCONCLUSIVE_LOW_POWER``, a
provenance-false capture to ``INVALID_MEASUREMENT``, and a non-arm capture contributes
its rows without breaking a coherent matrix.

In-memory ``BondAffinityCapture`` objects (no DuckDB) — the DuckDB read round-trip is
covered by ``test_bond_affinity_trace_reader``.
"""

from __future__ import annotations

from erre_sandbox.evidence.relational.bond_affinity_trace_ddl import (
    build_bond_affinity_trace_rows,
)
from erre_sandbox.evidence.relational.loader import score_bond_affinity_captures
from erre_sandbox.evidence.relational.trace_reader import BondAffinityCapture
from erre_sandbox.evidence.saturation.trace_ddl import SaturationTraceRow
from erre_sandbox.schemas import RelationshipBond, Zone

_TICK = 10


def _bond_rows(run_id, seed, abs_aff, sign, n, *, provenance=True):
    rows = []
    for i in range(n):
        rows.extend(
            build_bond_affinity_trace_rows(
                [
                    RelationshipBond(
                        other_agent_id=f"o{i}",
                        affinity=sign * abs_aff,
                        ichigo_ichie_count=6,
                        last_interaction_tick=_TICK,
                        last_interaction_zone=Zone.STUDY,
                    )
                ],
                run_id=run_id,
                seed=seed,
                individual_id="kant",
                tick=_TICK,
                individual_layer_enabled=provenance,
            )
        )
    return rows


def _sat_rows(run_id, seed, *, provenance=True, exposure=True):
    if not exposure:
        return []
    return [
        SaturationTraceRow(
            run_id=run_id,
            seed=seed,
            individual_id="kant",
            axis="self",
            key="k",
            tick=_TICK,
            base_floor_value=0.5,
            modulated_value=0.65,
            floor_fingerprint_hash="h",
            individual_layer_enabled=provenance,
        )
    ]


def _capture(
    seed,
    arm,
    replicate,
    abs_aff,
    *,
    sign=1.0,
    n=10,
    run_id=None,
    provenance=True,
    exposure=True,
):
    rid = run_id or f"s{seed}_{arm}_{replicate}"
    # path is the capture file identity (distinct per capture object); run_id is the
    # value baked into the rows. Two captures may share a run_id (the collision case)
    # while living in different files, so the path must not be derived from run_id.
    return BondAffinityCapture(
        path=f"/captures/{seed}_{arm}_{replicate}_{rid}.duckdb",
        seed=seed,
        arm=arm,
        replicate_id=replicate,
        bond_rows=tuple(_bond_rows(rid, seed, abs_aff, sign, n, provenance=provenance)),
        saturation_rows=tuple(
            _sat_rows(rid, seed, provenance=provenance, exposure=exposure)
        ),
    )


def _matrix_captures():
    """A coherent 12-run matrix engineered to route (i)-LEANING (ratio path)."""
    caps = []
    for seed in (1, 2, 3):
        caps.append(_capture(seed, "ON", 0, 0.44))
        caps.append(_capture(seed, "OFF", 0, 0.20))
        caps.append(_capture(seed, "OFF", 1, 0.16))
        caps.append(_capture(seed, "ON", 1, 0.44))
    return caps


def test_coherent_matrix_delegates_to_scorer() -> None:
    result = score_bond_affinity_captures(_matrix_captures())
    assert result.verdict == "(i)-LEANING"
    assert result.paired_seeds == (1, 2, 3)


def test_duplicate_cell_routes_invalid() -> None:
    """Two captures claiming the same (seed, arm, replicate) -> INVALID (dup key)."""
    caps = [
        *_matrix_captures(),
        _capture(1, "ON", 0, 0.44, run_id="duplicate_extra"),  # same cell, new run_id
    ]
    result = score_bond_affinity_captures(caps)
    assert result.verdict == "INVALID_MEASUREMENT"
    assert "duplicate" in result.notes.lower()


def test_shared_run_id_across_seed_cells_is_tolerated() -> None:
    """Per-capture assembly (工程1): a seed's four cells sharing one run_id is fine.

    The frozen captures reuse ``kant_natural_run{idx}`` across a seed's four cells; the
    old shared-run_id guard wrongly INVALIDated that. With sidecar-keyed per-capture
    assembly there is no cross-capture exposure leak, so a coherent 12-cell matrix whose
    cells share a per-seed run_id routes the substantive verdict, not INVALID.
    """
    caps = []
    for seed in (1, 2, 3):
        shared = (
            f"kant_natural_run{seed}"  # one run_id for all four of the seed's cells
        )
        caps.append(_capture(seed, "ON", 0, 0.44, run_id=shared))
        caps.append(_capture(seed, "OFF", 0, 0.20, run_id=shared))
        caps.append(_capture(seed, "OFF", 1, 0.16, run_id=shared))
        caps.append(_capture(seed, "ON", 1, 0.44, run_id=shared))
    result = score_bond_affinity_captures(caps)
    assert result.verdict == "(i)-LEANING"
    assert result.paired_seeds == (1, 2, 3)


def test_incomplete_matrix_routes_low_power() -> None:
    """A missing cell drops its seed; < 2 paired seeds -> LOW_POWER (not INVALID)."""
    caps = [
        _capture(1, "ON", 0, 0.44),
        _capture(1, "OFF", 0, 0.20),
        _capture(1, "OFF", 1, 0.16),
        _capture(1, "ON", 1, 0.44),
        # seed 2 missing its ON r1 cell -> seed 2 not paired -> only seed 1 paired.
        _capture(2, "ON", 0, 0.44),
        _capture(2, "OFF", 0, 0.20),
        _capture(2, "OFF", 1, 0.16),
    ]
    result = score_bond_affinity_captures(caps)
    assert result.verdict == "INCONCLUSIVE_LOW_POWER"
    assert result.paired_seeds == (1,)


def test_provenance_false_capture_routes_invalid() -> None:
    """A provenance-false capture is delegated and routes INVALID (scorer §7)."""
    caps = [_capture(1, "ON", 0, 0.44, provenance=False)]
    result = score_bond_affinity_captures(caps)
    assert result.verdict == "INVALID_MEASUREMENT"
    assert "provenance_false" in result.notes


def test_non_arm_capture_is_tolerated() -> None:
    """A None-arm capture contributes rows but no cell; coherent matrix still routes."""
    caps = [
        *_matrix_captures(),
        _capture(99, None, None, 0.44, run_id="stray_non_arm"),
    ]
    result = score_bond_affinity_captures(caps)
    assert result.verdict == "(i)-LEANING"
    assert result.paired_seeds == (1, 2, 3)


def test_capture_with_multiple_run_ids_is_invalid() -> None:
    """A capture whose rows span two run_ids is contaminated -> INVALID (HIGH-1)."""
    rows = _bond_rows("r1", 1, 0.44, 1.0, 5) + _bond_rows("r2", 1, 0.44, 1.0, 5)
    cap = BondAffinityCapture(
        path="/captures/contaminated.duckdb",
        seed=1,
        arm="ON",
        replicate_id=0,
        bond_rows=tuple(rows),
        saturation_rows=tuple(_sat_rows("r1", 1)),
    )
    result = score_bond_affinity_captures([cap])
    assert result.verdict == "INVALID_MEASUREMENT"
    assert "multiple run_ids" in result.notes


def test_capture_with_multiple_row_seeds_is_invalid() -> None:
    """A capture whose rows carry two seeds is contaminated -> INVALID (HIGH-1)."""
    rows = _bond_rows("r1", 1, 0.44, 1.0, 5) + _bond_rows("r1", 2, 0.44, 1.0, 5)
    cap = BondAffinityCapture(
        path="/captures/contaminated.duckdb",
        seed=1,
        arm="ON",
        replicate_id=0,
        bond_rows=tuple(rows),
        saturation_rows=tuple(_sat_rows("r1", 1)),
    )
    result = score_bond_affinity_captures([cap])
    assert result.verdict == "INVALID_MEASUREMENT"
    assert "multiple row seeds" in result.notes


def test_capture_sidecar_seed_row_seed_mismatch_is_invalid() -> None:
    """A sidecar seed disagreeing with the row seed is a mismatch (HIGH-1)."""
    cap = BondAffinityCapture(
        path="/captures/mismatch.duckdb",
        seed=99,  # sidecar says 99 ...
        arm="ON",
        replicate_id=0,
        bond_rows=tuple(_bond_rows("r1", 1, 0.44, 1.0, 5)),  # ... rows say 1
        saturation_rows=tuple(_sat_rows("r1", 1)),
    )
    result = score_bond_affinity_captures([cap])
    assert result.verdict == "INVALID_MEASUREMENT"
    assert "provenance mismatch" in result.notes


def test_out_of_domain_replicate_is_invalid() -> None:
    """An arm-bearing capture with replicate_id not in {0,1} -> INVALID (HIGH-2)."""
    result = score_bond_affinity_captures([_capture(1, "ON", 2, 0.44)])
    assert result.verdict == "INVALID_MEASUREMENT"
    assert "out-of-domain matrix key" in result.notes


def test_arm_bearing_capture_without_seed_is_invalid() -> None:
    """An arm-bearing capture with a None seed has an incomplete identity -> INVALID."""
    cap = BondAffinityCapture(
        path="/captures/no_seed.duckdb",
        seed=None,
        arm="ON",
        replicate_id=0,
        bond_rows=tuple(_bond_rows("r1", 1, 0.44, 1.0, 5)),
        saturation_rows=tuple(_sat_rows("r1", 1)),
    )
    result = score_bond_affinity_captures([cap])
    assert result.verdict == "INVALID_MEASUREMENT"
    assert "out-of-domain matrix key" in result.notes
