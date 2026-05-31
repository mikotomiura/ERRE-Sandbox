"""DB11 sentinel poison-row test for metrics.individuation (A9, PR-2).

Plants a leak-sentinel value in a ``metrics.individuation`` row and asserts the
training-egress view never surfaces it — the view reads ``raw_dialog.dialog``
only, so individuation rows are structurally invisible to training export.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb

from erre_sandbox.contracts.eval_paths import SENTINEL_LEAK_PREFIX
from erre_sandbox.evidence.eval_store import (
    bootstrap_schema,
    connect_training_view,
    write_individuation_rows,
)
from erre_sandbox.evidence.individuation.models import MetricResult, Provenance
from erre_sandbox.evidence.individuation.policy import (
    INDIVIDUATION_SCHEMA_VERSION,
    RESERVED_POPULATION_ID,
    AggregationLevel,
    MetricChannel,
    MetricStatus,
)

_DIALOG_COLS = (
    "id",
    "run_id",
    "dialog_id",
    "tick",
    "turn_index",
    "speaker_agent_id",
    "speaker_persona_id",
    "addressee_agent_id",
    "addressee_persona_id",
    "utterance",
    "mode",
    "zone",
    "reasoning",
    "epoch_phase",
    "individual_layer_enabled",
    "created_at",
)


def _poison_row() -> MetricResult:
    """A degenerate vendi row whose reason carries the leak sentinel."""
    return MetricResult(
        run_id="run0",
        individual_id=RESERVED_POPULATION_ID,
        base_persona_id="kant",
        aggregation_level=AggregationLevel.POPULATION,
        tick=-1,
        metric_name="vendi_diversity",
        channel=MetricChannel.UTTERANCE,
        status=MetricStatus.DEGENERATE,
        value=None,
        reason=f"{SENTINEL_LEAK_PREFIX}VENDI_POISON",
        provenance=Provenance(
            metric_schema_version=INDIVIDUATION_SCHEMA_VERSION,
            source_table="raw_dialog.dialog",
            source_run_id="run0",
            source_epoch_phase="autonomous",
            source_individual_layer_enabled=False,
            source_filter_hash="deadbeef",
        ),
        computed_at=datetime.now(UTC),
    )


def test_individuation_poison_row_never_reaches_training_view(tmp_path: Path) -> None:
    db = tmp_path / "poison.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    # One clean raw_dialog row so iter_rows has something to yield.
    cols = ", ".join(_DIALOG_COLS)
    ph = ", ".join("?" for _ in _DIALOG_COLS)
    clean = {
        "id": "1",
        "run_id": "run0",
        "dialog_id": "d0",
        "tick": 0,
        "turn_index": 0,
        "speaker_agent_id": "a_kant_001",
        "speaker_persona_id": "kant",
        "addressee_agent_id": "a_x",
        "addressee_persona_id": "x",
        "utterance": "a clean utterance",
        "mode": "",
        "zone": "study",
        "reasoning": "",
        "epoch_phase": "autonomous",
        "individual_layer_enabled": False,
        "created_at": datetime.now(UTC),
    }
    con.execute(
        f"INSERT INTO raw_dialog.dialog ({cols}) VALUES ({ph})",  # noqa: S608  # static cols
        [clean[c] for c in _DIALOG_COLS],
    )
    # Plant the poison row in metrics.individuation.
    written = write_individuation_rows(con, [_poison_row()])
    assert written == 1
    con.execute("CHECKPOINT")
    con.close()

    # The training view reads raw_dialog only: the sentinel must not surface.
    relation = connect_training_view(db)
    try:
        rows = list(relation.iter_rows())
    finally:
        relation.close()
    assert rows  # the clean row is visible
    for row in rows:
        for value in row.values():
            assert not (
                isinstance(value, str) and value.startswith(SENTINEL_LEAK_PREFIX)
            )
