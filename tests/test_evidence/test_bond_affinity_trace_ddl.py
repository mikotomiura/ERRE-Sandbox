"""``swm_bond_affinity_trace`` DDL + row-builder coverage (instrumentation ADR 3.1).

CPU-only. Verifies the 10-column single source of truth, DDL idempotency + UBIGINT
seed, the ``tick >= 0`` CHECK, the flag-on conditional bootstrap (flag-off leaves the
table absent), the row builder's per-bond projection with *signed* affinity and
nullable recency passthrough, the raw-only invariant (no threshold-derived column), and
the CI eval-egress contract: the module composes its qualified name from
``METRICS_SCHEMA`` and never embeds a schema-dot literal.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.eval_store import bootstrap_schema
from erre_sandbox.evidence.relational import bond_affinity_trace_ddl
from erre_sandbox.evidence.relational.bond_affinity_trace_ddl import (
    BOND_AFFINITY_TRACE_COLUMN_COUNT,
    TABLE_NAME,
    BondAffinityTraceRow,
    bond_affinity_trace_ddl_sql,
    bootstrap_bond_affinity_trace_schema,
    build_bond_affinity_trace_rows,
    column_names,
)
from erre_sandbox.schemas import RelationshipBond, Zone

_EXPECTED_COLUMNS = (
    "run_id",
    "seed",
    "individual_id",
    "other_agent_id",
    "tick",
    "affinity",
    "ichigo_ichie_count",
    "last_interaction_tick",
    "last_interaction_zone",
    "individual_layer_enabled",
)


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


def test_column_names_are_the_frozen_order() -> None:
    assert column_names() == _EXPECTED_COLUMNS
    assert len(_EXPECTED_COLUMNS) == BOND_AFFINITY_TRACE_COLUMN_COUNT == 10


def test_to_row_is_column_lockstep() -> None:
    row = BondAffinityTraceRow(
        run_id="r",
        seed=9980935715884061059,  # uint64 > 2^63-1
        individual_id="kant",
        other_agent_id="nietzsche",
        tick=12,
        affinity=-0.44,
        ichigo_ichie_count=7,
        last_interaction_tick=11,
        last_interaction_zone="study",
        individual_layer_enabled=True,
    )
    by_name = dict(zip(column_names(), row.to_row(), strict=True))
    assert by_name["seed"] == 9980935715884061059
    assert by_name["other_agent_id"] == "nietzsche"
    assert by_name["affinity"] == -0.44  # signed preserved
    assert by_name["ichigo_ichie_count"] == 7
    assert by_name["last_interaction_tick"] == 11
    assert by_name["last_interaction_zone"] == "study"
    assert by_name["individual_layer_enabled"] is True


def test_ddl_idempotent_and_ubigint_accepts_uint64() -> None:
    con = duckdb.connect(":memory:")
    con.execute(f"CREATE SCHEMA {METRICS_SCHEMA}")
    bootstrap_bond_affinity_trace_schema(con, METRICS_SCHEMA)
    bootstrap_bond_affinity_trace_schema(
        con, METRICS_SCHEMA
    )  # idempotent (IF NOT EXISTS)
    cols = column_names()
    insert_sql = (
        f"INSERT INTO {METRICS_SCHEMA}.{TABLE_NAME} "  # noqa: S608 — static identifiers, test
        f"({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    )
    big_seed = 2**64 - 1
    con.execute(
        insert_sql,
        ("r", big_seed, "kant", "nietzsche", 7, -0.44, 6, 5, "study", True),
    )
    stored = con.execute(
        f"SELECT seed, affinity FROM {METRICS_SCHEMA}.{TABLE_NAME}"  # noqa: S608 — static identifiers
    ).fetchone()
    assert stored is not None
    assert stored[0] == big_seed
    assert stored[1] == -0.44


def test_ddl_tick_check_rejects_negative() -> None:
    con = duckdb.connect(":memory:")
    con.execute(f"CREATE SCHEMA {METRICS_SCHEMA}")
    bootstrap_bond_affinity_trace_schema(con, METRICS_SCHEMA)
    cols = column_names()
    insert_sql = (
        f"INSERT INTO {METRICS_SCHEMA}.{TABLE_NAME} "  # noqa: S608 — static identifiers, test
        f"({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    )
    with pytest.raises(duckdb.ConstraintException):
        con.execute(
            insert_sql,
            ("r", 1, "kant", "nietzsche", -1, 0.1, 6, 5, "study", True),
        )


def test_flag_off_bootstrap_does_not_create_table(tmp_path: Path) -> None:
    """The base ``bootstrap_schema`` (flag-off) never creates the bond trace table.

    The table is created only by ``bootstrap_bond_affinity_trace_schema`` in the
    flag-on branch, so a flag-off run leaves the DuckDB byte-identical (no new table).
    This is the DDL-level proof of the flag-off invariant (ADR section 6).
    """
    con = duckdb.connect(str(tmp_path / "flagoff.duckdb"))
    bootstrap_schema(con)
    present = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
        (TABLE_NAME,),
    ).fetchone()
    assert present is not None
    assert present[0] == 0


def test_build_rows_one_per_bond_signed_affinity() -> None:
    rows = build_bond_affinity_trace_rows(
        [_bond("nietzsche", -0.44, count=7), _bond("hume", 0.30, count=3)],
        run_id="r",
        seed=42,
        individual_id="kant",
        tick=15,
        individual_layer_enabled=True,
    )
    assert len(rows) == 2
    by_other = {r.other_agent_id: r for r in rows}
    # Clash bond keeps its negative sign (not abs'd) — read side takes abs.
    assert by_other["nietzsche"].affinity == -0.44
    assert by_other["nietzsche"].ichigo_ichie_count == 7
    assert by_other["hume"].affinity == 0.30
    assert all(r.seed == 42 and r.tick == 15 for r in rows)
    assert all(r.individual_id == "kant" and r.individual_layer_enabled for r in rows)


def test_build_rows_normalises_zone_and_passes_nulls() -> None:
    rows = build_bond_affinity_trace_rows(
        [
            _bond("a", 0.2, zone=Zone.PERIPATOS, last_tick=9),
            _bond("b", 0.1, zone=None, last_tick=None),
        ],
        run_id="r",
        seed=1,
        individual_id="kant",
        tick=3,
        individual_layer_enabled=True,
    )
    by_other = {r.other_agent_id: r for r in rows}
    # Zone StrEnum -> underlying string for the TEXT column.
    assert by_other["a"].last_interaction_zone == Zone.PERIPATOS.value
    assert isinstance(by_other["a"].last_interaction_zone, str)
    assert by_other["a"].last_interaction_tick == 9
    # None recency passes straight through (nullable columns).
    assert by_other["b"].last_interaction_zone is None
    assert by_other["b"].last_interaction_tick is None


def test_rows_store_raw_only_no_threshold_derived_column() -> None:
    """The trace stores raw fields only — no near-miss / gate flag is baked in.

    Recompute-stable (ADR section 3.2): the read side recomputes the
    ``|affinity| < 0.45 ∧ ichigo_ichie_count >= 6`` gate, so a sub-threshold and a
    promotion-survivor bond are stored identically (only their raw values differ),
    and no column name encodes a threshold decision.
    """
    assert set(column_names()) == set(_EXPECTED_COLUMNS)
    derived_markers = ("near_miss", "is_near_miss", "gate", "promoted", "threshold")
    assert not any(
        marker in name for name in column_names() for marker in derived_markers
    )
    # A below-threshold and an above-threshold bond both yield a plain raw row.
    rows = build_bond_affinity_trace_rows(
        [_bond("sub", 0.44, count=7), _bond("sur", 0.46, count=7)],
        run_id="r",
        seed=1,
        individual_id="kant",
        tick=2,
        individual_layer_enabled=True,
    )
    assert {r.other_agent_id: r.affinity for r in rows} == {"sub": 0.44, "sur": 0.46}


def test_ddl_sql_is_schema_parameterised() -> None:
    sql = bond_affinity_trace_ddl_sql(METRICS_SCHEMA)
    assert f"{METRICS_SCHEMA}.{TABLE_NAME}" in sql
    assert "seed UBIGINT NOT NULL" in sql
    assert "affinity DOUBLE NOT NULL" in sql
    assert "CHECK (tick >= 0)" in sql
    other = bond_affinity_trace_ddl_sql("scratch")
    assert f"scratch.{TABLE_NAME}" in other


def test_module_source_has_no_schema_dot_literal() -> None:
    """The module never embeds a quoted schema-dot literal (CI grep gate)."""
    source = Path(bond_affinity_trace_ddl.__file__).read_text(encoding="utf-8")
    assert '"metrics.' not in source
    assert "'metrics." not in source
