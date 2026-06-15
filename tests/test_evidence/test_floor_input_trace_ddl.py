"""``swm_floor_input_trace`` DDL + row-builder coverage (U5 replay infra).

CPU-only. Verifies the column-order single source, DDL idempotency, the flag-on
conditional bootstrap (flag-off leaves the table absent), the **full-floor** JSON
round-trip (``deserialize(captured base_floor) == reconcile input`` — the replay
fidelity property, Codex MED-3 ①), the empty-floor row (one row even with no entries —
the empty-tick state-threading substrate, DA-U5-2), and the DuckDB reader round-trip.
Also guards the CI eval-egress contract: the module composes its qualified name from
``METRICS_SCHEMA`` and never embeds a ``metrics``-dot schema literal.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from erre_sandbox.contracts.cognition_layers import (
    SubjectiveWorldModel,
    WorldModelEntry,
    WorldModelSnapshot,
)
from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.eval_store import bootstrap_schema
from erre_sandbox.evidence.saturation.floor_input_trace_ddl import (
    FLOOR_INPUT_TRACE_COLUMN_COUNT,
    TABLE_NAME,
    FloorInputTraceRow,
    bootstrap_floor_input_trace_schema,
    build_floor_input_trace_row,
    column_names,
    floor_input_trace_ddl_sql,
    read_floor_input_trace_rows,
)

_EXPECTED_COLUMNS = (
    "run_id",
    "seed",
    "individual_id",
    "tick",
    "floor_swm_json",
    "individual_layer_enabled",
)


def _entry(
    axis: str, key: str, value: float, *, confidence: float = 0.8
) -> WorldModelEntry:
    return WorldModelEntry(
        axis=axis,
        key=key,
        value=value,
        confidence=confidence,
        cited_memory_ids=("m1", "m2"),
        last_updated_tick=3,
    )


def _snapshot(floor: SubjectiveWorldModel) -> WorldModelSnapshot:
    # The replay only reads ``base_floor``; ``modulated`` is irrelevant here, so a
    # cheap copy keeps the snapshot construction valid (frozen model needs both).
    return WorldModelSnapshot(base_floor=floor, modulated=floor.model_copy(deep=True))


def test_column_names_are_the_frozen_order() -> None:
    assert column_names() == _EXPECTED_COLUMNS
    assert len(_EXPECTED_COLUMNS) == FLOOR_INPUT_TRACE_COLUMN_COUNT


def test_to_row_is_column_lockstep() -> None:
    row = FloorInputTraceRow(
        run_id="r",
        seed=9980935715884061059,  # uint64 > 2^63-1
        individual_id="rikyu",
        tick=12,
        floor_swm_json='{"entries":[]}',
        individual_layer_enabled=True,
    )
    by_name = dict(zip(column_names(), row.to_row(), strict=True))
    assert by_name["seed"] == 9980935715884061059
    assert by_name["floor_swm_json"] == '{"entries":[]}'
    assert by_name["individual_layer_enabled"] is True


def test_ddl_idempotent_and_ubigint_accepts_uint64() -> None:
    con = duckdb.connect(":memory:")
    con.execute(f"CREATE SCHEMA {METRICS_SCHEMA}")
    bootstrap_floor_input_trace_schema(con, METRICS_SCHEMA)
    bootstrap_floor_input_trace_schema(
        con, METRICS_SCHEMA
    )  # idempotent (IF NOT EXISTS)
    cols = column_names()
    insert_sql = (
        f"INSERT INTO {METRICS_SCHEMA}.{TABLE_NAME} "  # noqa: S608 — static identifiers, test
        f"({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    )
    big_seed = 2**64 - 1
    con.execute(insert_sql, ("r", big_seed, "rikyu", 7, '{"entries":[]}', True))
    stored = con.execute(
        f"SELECT seed FROM {METRICS_SCHEMA}.{TABLE_NAME}"  # noqa: S608 — static identifiers
    ).fetchone()
    assert stored is not None
    assert stored[0] == big_seed


def test_flag_off_bootstrap_does_not_create_table(tmp_path: Path) -> None:
    """The base ``bootstrap_schema`` (flag-off) never creates the floor-input table.

    The table is created only by ``bootstrap_floor_input_trace_schema`` in the flag-on
    branch, so a flag-off run leaves the DuckDB byte-identical (no new table). This is
    the DDL-level proof of the flag-off invariant.
    """
    con = duckdb.connect(str(tmp_path / "flagoff.duckdb"))
    bootstrap_schema(con)
    present = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
        (TABLE_NAME,),
    ).fetchone()
    assert present is not None
    assert present[0] == 0


def test_build_row_round_trips_full_floor() -> None:
    """``deserialize(captured base_floor) == reconcile input`` (Codex MED-3 ①).

    The whole point of the new table over the lossy saturation trace: the full floor
    (value + confidence + cited_memory_ids + last_updated_tick) round-trips exactly, so
    a replay re-feeds the *identical* reconcile input into the unchanged kernel.
    """
    floor = SubjectiveWorldModel(
        entries=[_entry("self", "a", 0.5, confidence=0.71), _entry("env", "b", -0.3)]
    )
    row = build_floor_input_trace_row(
        _snapshot(floor),
        run_id="r",
        seed=42,
        individual_id="rikyu",
        tick=15,
        individual_layer_enabled=True,
    )
    restored = SubjectiveWorldModel.model_validate_json(row.floor_swm_json)
    assert restored == floor
    # The lossy saturation fields are all preserved here (not just the value).
    assert restored.entries[0].confidence == 0.71
    assert restored.entries[0].cited_memory_ids == ("m1", "m2")
    assert restored.entries[0].last_updated_tick == 3


def test_empty_floor_emits_one_row() -> None:
    """An empty floor (no promoted beliefs) still emits exactly one row (DA-U5-2).

    The per-entry saturation trace drops an empty-floor tick; the per-(ind,tick) JSON
    grain keeps it so the replay can reproduce ``reconcile_world_model``'s vanished-key
    drop on an empty-floor tick.
    """
    row = build_floor_input_trace_row(
        _snapshot(SubjectiveWorldModel(entries=[])),
        run_id="r",
        seed=1,
        individual_id="rikyu",
        tick=9,
        individual_layer_enabled=True,
    )
    restored = SubjectiveWorldModel.model_validate_json(row.floor_swm_json)
    assert restored.entries == []


def test_reader_round_trips_through_duckdb() -> None:
    con = duckdb.connect(":memory:")
    con.execute(f"CREATE SCHEMA {METRICS_SCHEMA}")
    bootstrap_floor_input_trace_schema(con, METRICS_SCHEMA)
    cols = column_names()
    insert_sql = (
        f"INSERT INTO {METRICS_SCHEMA}.{TABLE_NAME} "  # noqa: S608 — static identifiers, test
        f"({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    )
    floor = SubjectiveWorldModel(entries=[_entry("self", "a", 0.5)])
    written = build_floor_input_trace_row(
        _snapshot(floor),
        run_id="r",
        seed=2**64 - 5,
        individual_id="rikyu",
        tick=4,
        individual_layer_enabled=True,
    )
    con.execute(insert_sql, written.to_row())
    rows = read_floor_input_trace_rows(con, schema=METRICS_SCHEMA)
    assert len(rows) == 1
    assert rows[0] == written
    assert SubjectiveWorldModel.model_validate_json(rows[0].floor_swm_json) == floor


def test_ddl_sql_is_schema_parameterised() -> None:
    """The DDL composes the table name from the caller's schema, not a hardcode."""
    sql = floor_input_trace_ddl_sql(METRICS_SCHEMA)
    assert f"{METRICS_SCHEMA}.{TABLE_NAME}" in sql
    assert "seed UBIGINT NOT NULL" in sql
    other = floor_input_trace_ddl_sql("scratch")
    assert f"scratch.{TABLE_NAME}" in other
