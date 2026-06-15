"""Replay source assembler coverage (U5, Codex HIGH-3 fail-fast).

CPU-only synthetic DuckDB. Verifies the happy-path canonical assembly and every
structural rejection the replay's determinism + fidelity depend on: duplicate natural
key, non-exactly-one run_id/seed, ``individual_layer_enabled=False`` provenance, and a
floor/hint ``(individual_id, tick)`` census mismatch.
"""

from __future__ import annotations

import duckdb
import pytest

from erre_sandbox.contracts.cognition_layers import (
    SubjectiveWorldModel,
    WorldModelEntry,
)
from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.hint_engagement.trace_ddl import (
    TABLE_NAME as HINT_TABLE,
)
from erre_sandbox.evidence.hint_engagement.trace_ddl import (
    HintEngagementTraceRow,
    bootstrap_hint_engagement_trace_schema,
)
from erre_sandbox.evidence.hint_engagement.trace_ddl import (
    column_names as hint_columns,
)
from erre_sandbox.evidence.saturation.floor_input_trace_ddl import (
    TABLE_NAME as FLOOR_TABLE,
)
from erre_sandbox.evidence.saturation.floor_input_trace_ddl import (
    FloorInputTraceRow,
    bootstrap_floor_input_trace_schema,
)
from erre_sandbox.evidence.saturation.floor_input_trace_ddl import (
    column_names as floor_columns,
)
from erre_sandbox.evidence.saturation.replay_source import (
    ReplaySourceError,
    assemble_replay_source,
)

_RUN = "rikyu_natural_run0"
_SEED = 123456789


def _floor_json(value: float) -> str:
    return SubjectiveWorldModel(
        entries=[
            WorldModelEntry(
                axis="env",
                key="agora",
                value=value,
                confidence=0.6,
                cited_memory_ids=("m1",),
                last_updated_tick=5,
            )
        ]
    ).model_dump_json()


def _floor_row(ind: str, tick: int, *, enabled: bool = True) -> FloorInputTraceRow:
    return FloorInputTraceRow(
        run_id=_RUN,
        seed=_SEED,
        individual_id=ind,
        tick=tick,
        floor_swm_json=_floor_json(0.5 + 0.001 * tick),
        individual_layer_enabled=enabled,
    )


def _hint_row(ind: str, tick: int, *, enabled: bool = True) -> HintEngagementTraceRow:
    return HintEngagementTraceRow(
        run_id=_RUN,
        seed=_SEED,
        individual_id=ind,
        tick=tick,
        llm_status="ok",
        exposed_entry_count=1,
        emitted=True,
        disposition="adopted",
        target_axis="env",
        target_key="agora",
        direction="strengthen",
        adopted_signed_step=0.05,
        individual_layer_enabled=enabled,
    )


def _make_source(
    floor_rows: list[FloorInputTraceRow],
    hint_rows: list[HintEngagementTraceRow],
) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute(f"CREATE SCHEMA {METRICS_SCHEMA}")
    bootstrap_floor_input_trace_schema(con, METRICS_SCHEMA)
    bootstrap_hint_engagement_trace_schema(con, METRICS_SCHEMA)
    fcols = floor_columns()
    finsert = (
        f"INSERT INTO {METRICS_SCHEMA}.{FLOOR_TABLE} "  # noqa: S608 — static identifiers, test
        f"({', '.join(fcols)}) VALUES ({', '.join('?' for _ in fcols)})"
    )
    for r in floor_rows:
        con.execute(finsert, r.to_row())
    hcols = hint_columns()
    hinsert = (
        f"INSERT INTO {METRICS_SCHEMA}.{HINT_TABLE} "  # noqa: S608 — static identifiers, test
        f"({', '.join(hcols)}) VALUES ({', '.join('?' for _ in hcols)})"
    )
    for r in hint_rows:
        con.execute(hinsert, r.to_row())
    return con


def test_assembles_canonically_sorted_stream() -> None:
    # Inserted out of order: must come back sorted by (individual_id, tick).
    floor_rows = [
        _floor_row("rikyu", 11),
        _floor_row("kant", 10),
        _floor_row("kant", 9),
    ]
    hint_rows = [_hint_row("kant", 9), _hint_row("rikyu", 11), _hint_row("kant", 10)]
    con = _make_source(floor_rows, hint_rows)
    source = assemble_replay_source(con)
    assert source.run_id == _RUN
    assert source.seed == _SEED
    assert [(t.individual_id, t.tick) for t in source.ticks] == [
        ("kant", 9),
        ("kant", 10),
        ("rikyu", 11),
    ]
    # Floor + disposition round-trip into contracts types.
    assert source.ticks[0].floor.entries[0].axis == "env"
    assert source.ticks[0].source_disposition.disposition == "adopted"


def test_rejects_floor_duplicate_natural_key() -> None:
    con = _make_source(
        [_floor_row("kant", 10), _floor_row("kant", 10)],
        [_hint_row("kant", 10)],
    )
    with pytest.raises(ReplaySourceError, match="duplicate floor natural key"):
        assemble_replay_source(con)


def test_rejects_provenance_false_rows() -> None:
    con = _make_source(
        [_floor_row("kant", 10, enabled=False)],
        [_hint_row("kant", 10)],
    )
    with pytest.raises(ReplaySourceError, match="individual_layer_enabled=False"):
        assemble_replay_source(con)


def test_rejects_census_mismatch() -> None:
    # Floor has (kant, 11) with no matching hint row -> census mismatch.
    con = _make_source(
        [_floor_row("kant", 10), _floor_row("kant", 11)],
        [_hint_row("kant", 10)],
    )
    with pytest.raises(ReplaySourceError, match="census mismatch"):
        assemble_replay_source(con)


def test_rejects_non_exactly_one_seed() -> None:
    other = FloorInputTraceRow(
        run_id=_RUN,
        seed=_SEED + 1,  # second seed in the same capture
        individual_id="kant",
        tick=11,
        floor_swm_json=_floor_json(0.5),
        individual_layer_enabled=True,
    )
    con = _make_source(
        [_floor_row("kant", 10), other],
        [_hint_row("kant", 10), _hint_row("kant", 11)],
    )
    with pytest.raises(ReplaySourceError, match="seed is not exactly-one"):
        assemble_replay_source(con)


def test_rejects_empty_floor() -> None:
    con = _make_source([], [_hint_row("kant", 10)])
    with pytest.raises(ReplaySourceError, match="no floor-input rows"):
        assemble_replay_source(con)
