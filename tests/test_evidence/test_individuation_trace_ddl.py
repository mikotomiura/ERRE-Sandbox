"""DDL + row-builder coverage for metrics.individual_state_trace (M11-C2 / M10-A 段B).

Pins the substrate primitives that do not depend on the live cognition run: the
flag-on conditional DDL (and its absence from ``bootstrap_schema`` = flag-off DB
schema invariance, DA-M11C2-1), the ``tick >= 0`` CHECK, the None-safe projection
of a C1 ``IndividualProfile`` snapshot into a trace row (no fabrication; mirrors C1
Option B), and the 段B per-dyad raw evidence serialisation (canonical field names,
round(6), other_agent_id sort, None/"[]" distinction; DA-SB-2/4).
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from erre_sandbox.contracts.cognition_layers import (
    ArcSegment,
    DevelopmentState,
    IndividualProfile,
    NarrativeArc,
    PromotedEvidenceUnit,
    SubjectiveWorldModel,
    WorldModelEntry,
    WorldModelSnapshot,
)
from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.eval_store import bootstrap_schema
from erre_sandbox.evidence.individuation.trace_ddl import (
    INDIVIDUAL_STATE_TRACE_COLUMN_COUNT,
    TABLE_NAME,
    IndividualStateTraceRow,
    bootstrap_individual_state_trace_schema,
    build_individual_state_trace_row,
    column_names,
)
from erre_sandbox.schemas import Zone


def _booted(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(tmp_path / "trace.duckdb"), read_only=False)
    bootstrap_schema(con)
    return con


def _table_names(con: duckdb.DuckDBPyConnection) -> set[str]:
    return {
        row[0]
        for row in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = ?",
            (METRICS_SCHEMA,),
        ).fetchall()
    }


# --- flag-off DB schema invariance (DA-M11C2-1 / Codex MEDIUM-6) -------------


def test_bootstrap_schema_omits_trace_table(tmp_path: Path) -> None:
    """bootstrap_schema must NOT create the trace table (flag-off byte invariance)."""
    con = _booted(tmp_path)
    try:
        names = _table_names(con)
    finally:
        con.close()
    assert TABLE_NAME not in names
    # the existing M10-0 table set is unchanged (no trace leakage)
    assert names == {"tier_a", "tier_b", "tier_c", "individuation"}


def test_conditional_bootstrap_creates_trace_table(tmp_path: Path) -> None:
    con = _booted(tmp_path)
    try:
        bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
        names = _table_names(con)
        cols = con.execute(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_schema = ? AND table_name = ?",
            (METRICS_SCHEMA, TABLE_NAME),
        ).fetchall()
    finally:
        con.close()
    assert TABLE_NAME in names
    assert {c[0] for c in cols} == set(column_names())
    # M10-A E2 (world_model_keys_json) + 段B (world_model_evidence_json) -> 9 columns.
    assert len(cols) == INDIVIDUAL_STATE_TRACE_COLUMN_COUNT == 9


def test_conditional_bootstrap_idempotent(tmp_path: Path) -> None:
    con = _booted(tmp_path)
    try:
        bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
        bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)  # must not raise
    finally:
        con.close()


def _insert(con: duckdb.DuckDBPyConnection, row: IndividualStateTraceRow) -> None:
    cols = ", ".join(column_names())
    ph = ", ".join("?" for _ in column_names())
    con.execute(
        f"INSERT INTO {METRICS_SCHEMA}.{TABLE_NAME} ({cols}) VALUES ({ph})",  # noqa: S608  # module constants
        row.to_row(),
    )


def test_check_rejects_negative_tick(tmp_path: Path) -> None:
    con = _booted(tmp_path)
    try:
        bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
        with pytest.raises(duckdb.ConstraintException):
            _insert(
                con,
                IndividualStateTraceRow(
                    run_id="r0",
                    individual_id="a_rikyu_001",
                    tick=-1,
                    development_stage=None,
                    coherence_score=None,
                    belief_classes_json=None,
                    arc_segment_count=0,
                    world_model_keys_json=None,
                    world_model_evidence_json=None,
                ),
            )
        # tick == 0 is accepted
        _insert(
            con,
            IndividualStateTraceRow(
                run_id="r0",
                individual_id="a_rikyu_001",
                tick=0,
                development_stage=None,
                coherence_score=None,
                belief_classes_json=None,
                arc_segment_count=0,
                world_model_keys_json=None,
                world_model_evidence_json=None,
            ),
        )
    finally:
        con.close()


# --- build_individual_state_trace_row None-safety (DA-M11C2-3) ---------------


def test_build_row_none_safety() -> None:
    """A flag-on tick that advanced no stage / synthesised no arc writes NULLs."""
    profile = IndividualProfile(individual_id="a_rikyu_001", base_persona_id="rikyu")
    row = build_individual_state_trace_row(profile, None, None, run_id="r0", tick=3)
    assert row.individual_id == "a_rikyu_001"
    assert row.tick == 3
    assert row.development_stage is None
    assert row.coherence_score is None
    assert row.belief_classes_json is None
    assert row.arc_segment_count == 0  # no arc -> zero observed segments
    # no SWM snapshot -> NULL (honest "not captured", distinct from "[]")
    assert row.world_model_keys_json is None
    # no evidence carried -> NULL (honest "not captured", distinct from "[]")
    assert row.world_model_evidence_json is None


def _snapshot(*entries: tuple[str, str]) -> WorldModelSnapshot:
    """Build a WorldModelSnapshot whose base_floor carries the given (axis,key)s."""
    floor = SubjectiveWorldModel(
        entries=[
            WorldModelEntry(
                axis=axis,  # type: ignore[arg-type]  # test feeds valid axis literals
                key=key,
                value=0.5,
                confidence=0.5,
                cited_memory_ids=("m1",),
                last_updated_tick=1,
            )
            for axis, key in entries
        ]
    )
    return WorldModelSnapshot(base_floor=floor, modulated=floor)


def test_build_row_world_model_keys_pair_array_sorted() -> None:
    """SWM keys serialise to a de-duplicated, sorted [["axis","key"], ...] array.

    Insertion order is intentionally not sorted, and a key containing ':' is
    included to prove the pair-array form is unambiguous (DA-S1-2).
    """
    profile = IndividualProfile(
        individual_id="a_rikyu_001",
        base_persona_id="rikyu",
        world_model=_snapshot(
            ("self", "relational_disposition"),
            ("env", "agora"),
            ("env", "chashitsu:inner"),  # ':' in key -> pair array, not "axis:key"
            ("self", "relational_disposition"),  # duplicate collapses
        ),
    )
    row = build_individual_state_trace_row(
        profile, ["trust"], None, run_id="r0", tick=4
    )
    assert row.world_model_keys_json == (
        '[["env", "agora"], ["env", "chashitsu:inner"],'
        ' ["self", "relational_disposition"]]'
    )


def test_build_row_empty_swm_distinct_from_none() -> None:
    """A synthesised-but-empty SWM serialises to '[]', not NULL."""
    profile = IndividualProfile(
        individual_id="a_rikyu_002",
        base_persona_id="rikyu",
        world_model=_snapshot(),
    )
    row = build_individual_state_trace_row(profile, None, None, run_id="r0", tick=2)
    assert row.world_model_keys_json == "[]"


def test_build_row_populated() -> None:
    profile = IndividualProfile(
        individual_id="a_rikyu_002",
        base_persona_id="rikyu",
        development_state=DevelopmentState(stage="S2_exploring", maturity_score=0.5),
        narrative_arc=NarrativeArc(
            synthesized_at_tick=5,
            arc_segments=[
                ArcSegment(
                    segment_label="early study",
                    start_tick=0,
                    end_tick=5,
                    cited_memory_ids=("m1", "m2"),
                ),
            ],
            coherence_score=0.6,
            last_episodic_pointer="ep-42",
        ),
    )
    row = build_individual_state_trace_row(
        profile, ["trust", "wary", "trust"], None, run_id="r1", tick=7
    )
    assert row.development_stage == "S2_exploring"
    assert row.coherence_score == pytest.approx(0.6)
    assert row.arc_segment_count == 1
    assert row.belief_classes_json == '["trust", "wary", "trust"]'


def test_build_row_empty_belief_classes_distinct_from_none() -> None:
    """Empty list (flag-on, no promoted beliefs) serialises to '[]', not NULL."""
    profile = IndividualProfile(individual_id="a_kant_001", base_persona_id="kant")
    row = build_individual_state_trace_row(profile, [], None, run_id="r0", tick=1)
    assert row.belief_classes_json == "[]"


# --- 段B world_model_evidence serialisation (DA-SB-2/4) ----------------------


def _unit(
    other: str,
    *,
    affinity: float,
    zone: Zone | None = Zone.STUDY,
    belief_kind: str | None = "trust",
    confidence: float = 0.8,
    familiarity: float = 0.5,
    tick: int | None = 100,
) -> PromotedEvidenceUnit:
    return PromotedEvidenceUnit(
        other_agent_id=other,
        belief_kind=belief_kind,
        confidence=confidence,
        affinity=affinity,
        familiarity=familiarity,
        last_interaction_zone=zone,
        last_interaction_tick=tick,
    )


def test_build_row_evidence_none_distinct_from_empty() -> None:
    """``None`` evidence -> NULL; empty list -> '[]' (same honest distinction)."""
    profile = IndividualProfile(individual_id="a_kant_001", base_persona_id="kant")
    none_row = build_individual_state_trace_row(
        profile, None, None, run_id="r0", tick=1
    )
    assert none_row.world_model_evidence_json is None
    empty_row = build_individual_state_trace_row(profile, None, [], run_id="r0", tick=1)
    assert empty_row.world_model_evidence_json == "[]"


def test_build_row_evidence_canonical_names_sorted_rounded() -> None:
    """Evidence serialises with canonical field names, other-sorted, round(6)."""
    profile = IndividualProfile(individual_id="a_kant_001", base_persona_id="kant")
    # deliberately out of other_agent_id order; affinity carries >6dp jitter.
    units = [
        _unit("o_z", affinity=0.1234567, zone=Zone.AGORA),
        _unit("o_a", affinity=0.6, zone=None, belief_kind="curious", tick=None),
    ]
    row = build_individual_state_trace_row(
        profile, ["trust"], units, run_id="r0", tick=4
    )
    # other_agent_id ascending: o_a then o_z; keys sorted within each object.
    assert row.world_model_evidence_json == (
        '[{"affinity": 0.6, "belief_kind": "curious", "confidence": 0.8,'
        ' "familiarity": 0.5, "last_interaction_tick": null,'
        ' "last_interaction_zone": null, "other_agent_id": "o_a"},'
        ' {"affinity": 0.123457, "belief_kind": "trust", "confidence": 0.8,'
        ' "familiarity": 0.5, "last_interaction_tick": 100,'
        ' "last_interaction_zone": "agora", "other_agent_id": "o_z"}]'
    )


def test_to_row_lockstep_round_trip(tmp_path: Path) -> None:
    """to_row() order matches column_names() so an INSERT round-trips."""
    con = _booted(tmp_path)
    try:
        bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
        profile = IndividualProfile(
            individual_id="a_rikyu_001",
            base_persona_id="rikyu",
            development_state=DevelopmentState(stage="S3_consolidated"),
        )
        row = build_individual_state_trace_row(
            profile, ["curious"], None, run_id="r9", tick=12
        )
        assert len(row.to_row()) == INDIVIDUAL_STATE_TRACE_COLUMN_COUNT
        _insert(con, row)
        fetched = con.execute(
            f"SELECT {', '.join(column_names())}"  # noqa: S608  # module constants
            f" FROM {METRICS_SCHEMA}.{TABLE_NAME}"
        ).fetchone()
    finally:
        con.close()
    assert fetched == (
        "r9",
        "a_rikyu_001",
        12,
        "S3_consolidated",
        None,
        '["curious"]',
        0,
        None,  # world_model_keys_json: this profile carries no SWM snapshot
        None,  # world_model_evidence_json: no evidence carried
    )
