"""``swm_modulation_saturation_trace`` DDL + row-builder coverage (ADR section 5).

CPU-only. Verifies the column-order single source, DDL idempotency, the flag-on
conditional bootstrap (flag-off leaves the table absent), the floor-derived
fingerprint hash, and the row builder's per-``(axis, key)`` explosion. Also guards
the CI eval-egress contract: the module composes its qualified name from
``METRICS_SCHEMA`` and never embeds a ``metrics``-dot schema literal.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from erre_sandbox.contracts.cognition_layers import (
    SubjectiveWorldModel,
    WorldModelEntry,
    WorldModelSnapshot,
)
from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.eval_store import bootstrap_schema
from erre_sandbox.evidence.saturation.trace_ddl import (
    SATURATION_TRACE_COLUMN_COUNT,
    TABLE_NAME,
    SaturationTraceRow,
    bootstrap_saturation_trace_schema,
    build_saturation_trace_rows,
    column_names,
    floor_fingerprint_hash,
    saturation_trace_ddl_sql,
)

_EXPECTED_COLUMNS = (
    "run_id",
    "seed",
    "individual_id",
    "axis",
    "key",
    "tick",
    "base_floor_value",
    "modulated_value",
    "floor_fingerprint_hash",
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
        cited_memory_ids=("m1",),
        last_updated_tick=3,
    )


def test_column_names_are_the_frozen_order() -> None:
    assert column_names() == _EXPECTED_COLUMNS
    assert len(_EXPECTED_COLUMNS) == SATURATION_TRACE_COLUMN_COUNT


def test_to_row_is_column_lockstep() -> None:
    row = SaturationTraceRow(
        run_id="r",
        seed=9980935715884061059,  # uint64 > 2^63-1
        individual_id="kant",
        axis="self",
        key="k",
        tick=12,
        base_floor_value=0.5,
        modulated_value=0.64,
        floor_fingerprint_hash="deadbeef",
        individual_layer_enabled=True,
    )
    by_name = dict(zip(column_names(), row.to_row(), strict=True))
    assert by_name["seed"] == 9980935715884061059
    assert by_name["base_floor_value"] == 0.5
    assert by_name["modulated_value"] == 0.64
    assert by_name["individual_layer_enabled"] is True


def test_ddl_idempotent_and_ubigint_accepts_uint64() -> None:
    con = duckdb.connect(":memory:")
    con.execute(f"CREATE SCHEMA {METRICS_SCHEMA}")
    bootstrap_saturation_trace_schema(con, METRICS_SCHEMA)
    bootstrap_saturation_trace_schema(con, METRICS_SCHEMA)  # idempotent (IF NOT EXISTS)
    cols = column_names()
    insert_sql = (
        f"INSERT INTO {METRICS_SCHEMA}.{TABLE_NAME} "  # noqa: S608 — static identifiers, test
        f"({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    )
    big_seed = 2**64 - 1
    con.execute(
        insert_sql,
        ("r", big_seed, "kant", "self", "k", 7, 0.1, 0.2, "h", True),
    )
    stored = con.execute(
        f"SELECT seed FROM {METRICS_SCHEMA}.{TABLE_NAME}"  # noqa: S608 — static identifiers
    ).fetchone()
    assert stored is not None
    assert stored[0] == big_seed


def test_flag_off_bootstrap_does_not_create_table(tmp_path: Path) -> None:
    """The base ``bootstrap_schema`` (flag-off) never creates the saturation table.

    The table is created only by ``bootstrap_saturation_trace_schema`` in the
    flag-on branch, so a flag-off run leaves the DuckDB byte-identical (no new
    table). This is the DDL-level proof of the flag-off invariant.
    """
    con = duckdb.connect(str(tmp_path / "flagoff.duckdb"))
    bootstrap_schema(con)
    present = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
        (TABLE_NAME,),
    ).fetchone()
    assert present is not None
    assert present[0] == 0


def test_fingerprint_is_floor_derived_and_deterministic() -> None:
    floor = _entry("self", "k", 0.5)
    # Same floor entry -> identical hash (deterministic).
    assert floor_fingerprint_hash(floor) == floor_fingerprint_hash(floor)
    # A different floor value -> different hash.
    assert floor_fingerprint_hash(floor) != floor_fingerprint_hash(
        _entry("self", "k", 0.6)
    )
    # 64-hex SHA-256.
    assert len(floor_fingerprint_hash(floor)) == 64


def test_build_rows_explodes_per_channel_with_floor_fingerprint() -> None:
    floor = SubjectiveWorldModel(
        entries=[_entry("self", "a", 0.5), _entry("env", "b", -0.3)]
    )
    # Modulated shares the (axis, key) set; only values differ (reconcile invariant).
    modulated = SubjectiveWorldModel(
        entries=[_entry("self", "a", 0.62), _entry("env", "b", -0.4)]
    )
    snapshot = WorldModelSnapshot(base_floor=floor, modulated=modulated)
    rows = build_saturation_trace_rows(
        snapshot,
        run_id="r",
        seed=42,
        individual_id="kant",
        tick=15,
        individual_layer_enabled=True,
    )
    assert len(rows) == 2
    by_key = {(r.axis, r.key): r for r in rows}
    a = by_key[("self", "a")]
    assert a.base_floor_value == 0.5
    assert a.modulated_value == 0.62
    # The hash is the FLOOR entry's fingerprint (modulated value does not enter it).
    assert a.floor_fingerprint_hash == floor_fingerprint_hash(_entry("self", "a", 0.5))
    assert all(r.seed == 42 and r.individual_layer_enabled for r in rows)


def test_build_rows_loud_fails_on_reconcile_invariant_break() -> None:
    """A floor key absent from the modulated view raises, not a silent 0 (LOW-1)."""
    floor = SubjectiveWorldModel(
        entries=[_entry("self", "a", 0.5), _entry("env", "b", -0.3)]
    )
    # Modulated is missing ("env", "b") -> reconcile invariant violated.
    modulated = SubjectiveWorldModel(entries=[_entry("self", "a", 0.62)])
    snapshot = WorldModelSnapshot(base_floor=floor, modulated=modulated)
    with pytest.raises(ValueError, match="reconcile invariant violated"):
        build_saturation_trace_rows(
            snapshot,
            run_id="r",
            seed=1,
            individual_id="kant",
            tick=15,
            individual_layer_enabled=True,
        )


def test_ddl_sql_is_schema_parameterised() -> None:
    """The DDL composes the table name from the caller's schema, not a hardcode.

    Mirrors ``evidence.individuation.trace_ddl``: executable SQL strings are
    composed from the passed schema (here ``METRICS_SCHEMA``) so the qualified name
    is never a hardcoded literal. Passing a different schema must re-target the DDL.
    """
    sql = saturation_trace_ddl_sql(METRICS_SCHEMA)
    assert f"{METRICS_SCHEMA}.{TABLE_NAME}" in sql
    assert "seed UBIGINT NOT NULL" in sql
    other = saturation_trace_ddl_sql("scratch")
    assert f"scratch.{TABLE_NAME}" in other
