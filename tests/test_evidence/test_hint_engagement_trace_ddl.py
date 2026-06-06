"""``swm_hint_engagement_trace`` DDL + row-builder coverage (instrument ADR §4).

CPU-only. Verifies the column-order single source, DDL idempotency, the four CHECK
invariants (補強 §5: not_emitted ⟺ all three target columns NULL; emitted ⟺ disposition
≠ not_emitted; a non-zero step ⟹ adopted), the flag-on conditional bootstrap (flag-off
leaves the table absent = byte-identical), and the carrier→row projection. Also guards
the CI eval-egress contract: the module composes its qualified name from
``METRICS_SCHEMA`` and never embeds a ``metrics``-dot schema literal.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from erre_sandbox.contracts.cognition_layers import WorldModelHintDisposition
from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.eval_store import bootstrap_schema
from erre_sandbox.evidence.hint_engagement.trace_ddl import (
    HINT_ENGAGEMENT_TRACE_COLUMN_COUNT,
    TABLE_NAME,
    HintEngagementTraceRow,
    bootstrap_hint_engagement_trace_schema,
    build_hint_engagement_trace_row,
    column_names,
    hint_engagement_trace_ddl_sql,
)

_EXPECTED_COLUMNS = (
    "run_id",
    "seed",
    "individual_id",
    "tick",
    "llm_status",
    "exposed_entry_count",
    "emitted",
    "disposition",
    "target_axis",
    "target_key",
    "direction",
    "adopted_signed_step",
    "individual_layer_enabled",
)


def _insert_sql() -> str:
    cols = column_names()
    return (
        f"INSERT INTO {METRICS_SCHEMA}.{TABLE_NAME} "  # noqa: S608 — static identifiers, test
        f"({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    )


def _con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute(f"CREATE SCHEMA {METRICS_SCHEMA}")
    bootstrap_hint_engagement_trace_schema(con, METRICS_SCHEMA)
    return con


def test_column_names_are_the_frozen_order() -> None:
    assert column_names() == _EXPECTED_COLUMNS
    assert len(_EXPECTED_COLUMNS) == HINT_ENGAGEMENT_TRACE_COLUMN_COUNT


def test_to_row_is_column_lockstep() -> None:
    row = HintEngagementTraceRow(
        run_id="r",
        seed=9980935715884061059,  # uint64 > 2^63-1
        individual_id="kant",
        tick=12,
        llm_status="ok",
        exposed_entry_count=4,
        emitted=True,
        disposition="adopted",
        target_axis="self",
        target_key="k",
        direction="weaken",
        adopted_signed_step=-0.03,
        individual_layer_enabled=True,
    )
    by_name = dict(zip(column_names(), row.to_row(), strict=True))
    assert by_name["seed"] == 9980935715884061059
    assert by_name["disposition"] == "adopted"
    assert by_name["adopted_signed_step"] == -0.03
    assert by_name["target_axis"] == "self"
    assert by_name["individual_layer_enabled"] is True


def test_ddl_idempotent_and_ubigint_accepts_uint64() -> None:
    con = _con()
    bootstrap_hint_engagement_trace_schema(
        con, METRICS_SCHEMA
    )  # idempotent (IF NOT EXISTS)
    big_seed = 2**64 - 1
    con.execute(
        _insert_sql(),
        (
            "r",
            big_seed,
            "kant",
            7,
            "ok",
            2,
            False,
            "not_emitted",
            None,
            None,
            None,
            0.0,
            True,
        ),
    )
    stored = con.execute(
        f"SELECT seed FROM {METRICS_SCHEMA}.{TABLE_NAME}"  # noqa: S608 — static identifiers
    ).fetchone()
    assert stored is not None
    assert stored[0] == big_seed


def test_flag_off_bootstrap_does_not_create_table(tmp_path: Path) -> None:
    """The base ``bootstrap_schema`` (flag-off) never creates the hint table.

    The table is created only by ``bootstrap_hint_engagement_trace_schema`` in the
    flag-on branch, so a flag-off run leaves the DuckDB byte-identical (no new table).
    This is the DDL-level proof of the flag-off invariant.
    """
    con = duckdb.connect(str(tmp_path / "flagoff.duckdb"))
    bootstrap_schema(con)
    present = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
        (TABLE_NAME,),
    ).fetchone()
    assert present is not None
    assert present[0] == 0


def test_ddl_sql_is_schema_parameterised() -> None:
    sql = hint_engagement_trace_ddl_sql(METRICS_SCHEMA)
    assert f"{METRICS_SCHEMA}.{TABLE_NAME}" in sql
    assert "seed UBIGINT NOT NULL" in sql
    other = hint_engagement_trace_ddl_sql("scratch")
    assert f"scratch.{TABLE_NAME}" in other


# --- CHECK invariants (補強 §5) ------------------------------------------------


def test_check_accepts_valid_dispositions() -> None:
    con = _con()
    rows = [
        # not_emitted: all three target columns NULL, step 0.
        ("r", 1, "kant", 5, "ok", 3, False, "not_emitted", None, None, None, 0.0, True),
        # adopted: targets set, non-zero step allowed.
        (
            "r",
            1,
            "kant",
            6,
            "ok",
            3,
            True,
            "adopted",
            "self",
            "k",
            "weaken",
            -0.03,
            True,
        ),
        # rejected: targets set, step 0.
        (
            "r",
            1,
            "kant",
            7,
            "ok",
            3,
            True,
            "rejected_citation",
            "env",
            "k",
            "strengthen",
            0.0,
            True,
        ),
    ]
    for row in rows:
        con.execute(_insert_sql(), row)
    count = con.execute(
        f"SELECT COUNT(*) FROM {METRICS_SCHEMA}.{TABLE_NAME}"  # noqa: S608
    ).fetchone()
    assert count is not None
    assert count[0] == 3


@pytest.mark.parametrize(
    "row",
    [
        pytest.param(
            (
                "r",
                1,
                "kant",
                8,
                "ok",
                3,
                False,
                "not_emitted",
                "self",
                None,
                None,
                0.0,
                True,
            ),
            id="not_emitted with a non-NULL target_axis",
        ),
        pytest.param(
            (
                "r",
                1,
                "kant",
                9,
                "ok",
                3,
                True,
                "not_emitted",
                None,
                None,
                None,
                0.0,
                True,
            ),
            id="emitted=True with disposition=not_emitted",
        ),
        pytest.param(
            (
                "r",
                1,
                "kant",
                10,
                "ok",
                3,
                False,
                "adopted",
                "self",
                "k",
                "weaken",
                -0.03,
                True,
            ),
            id="emitted=False with disposition=adopted",
        ),
        pytest.param(
            (
                "r",
                1,
                "kant",
                11,
                "ok",
                3,
                True,
                "rejected_no_effect",
                "self",
                "k",
                "weaken",
                -0.03,
                True,
            ),
            id="non-zero step with a non-adopted disposition",
        ),
        pytest.param(
            (
                "r",
                1,
                "kant",
                12,
                "ok",
                3,
                True,
                "adopted",
                "self",
                None,  # exactly one target column NULL on an emitted row
                "weaken",
                -0.03,
                True,
            ),
            id="emitted/adopted with a partial-NULL target triple (Codex MEDIUM)",
        ),
    ],
)
def test_check_rejects_invariant_violations(row: tuple[object, ...]) -> None:
    con = _con()
    with pytest.raises(duckdb.Error):
        con.execute(_insert_sql(), row)


# --- carrier -> row -----------------------------------------------------------


def _carrier(**overrides: object) -> WorldModelHintDisposition:
    base: dict[str, object] = {
        "llm_status": "ok",
        "emitted": True,
        "disposition": "adopted",
        "target_axis": "self",
        "target_key": "k",
        "direction": "weaken",
        "adopted_signed_step": -0.03,
        "exposed_entry_count": 4,
    }
    base.update(overrides)
    return WorldModelHintDisposition(**base)  # type: ignore[arg-type]


def test_build_row_projects_carrier_and_binds_provenance() -> None:
    carrier = _carrier()
    row = build_hint_engagement_trace_row(
        carrier,
        run_id="r",
        seed=42,
        individual_id="kant",
        tick=15,
        individual_layer_enabled=True,
    )
    assert row.run_id == "r"
    assert row.seed == 42
    assert row.individual_id == "kant"
    assert row.tick == 15
    assert row.disposition == "adopted"
    assert row.target_axis == "self"
    assert row.adopted_signed_step == -0.03
    assert row.individual_layer_enabled is True


def test_build_row_round_trips_through_duckdb() -> None:
    con = _con()
    row = build_hint_engagement_trace_row(
        _carrier(
            disposition="not_emitted",
            emitted=False,
            target_axis=None,
            target_key=None,
            direction=None,
            adopted_signed_step=0.0,
        ),
        run_id="r",
        seed=7,
        individual_id="rikyu",
        tick=20,
        individual_layer_enabled=True,
    )
    con.execute(_insert_sql(), row.to_row())
    stored = con.execute(
        f"SELECT disposition, target_axis FROM {METRICS_SCHEMA}.{TABLE_NAME}"  # noqa: S608
    ).fetchone()
    assert stored == ("not_emitted", None)
