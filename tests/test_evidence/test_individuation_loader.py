"""WP5 loader coverage (M10-0 individuation PR-2).

Asserts per-individual windowing + ordering, deterministic
``source_filter_hash`` (and its sensitivity to content), the epoch-homogeneity
loud failure, and the contamination re-assert at the row boundary.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest

from erre_sandbox.contracts.eval_paths import (
    ALLOWED_RAW_DIALOG_KEYS,
    SENTINEL_LEAK_PREFIX,
    EvaluationContaminationError,
)
from erre_sandbox.evidence.eval_store import bootstrap_schema, connect_analysis_view
from erre_sandbox.evidence.individuation.loader import (
    _PROJECTION,
    IndividuationLoaderError,
    load_individual_windows,
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


def _row(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "x",
        "run_id": "run0",
        "dialog_id": "d0",
        "tick": 0,
        "turn_index": 0,
        "speaker_agent_id": "a_kant_001",
        "speaker_persona_id": "kant",
        "addressee_agent_id": "a_nietzsche_001",
        "addressee_persona_id": "nietzsche",
        "utterance": "hello",
        "mode": "",
        "zone": "study",
        "reasoning": "",
        "epoch_phase": "autonomous",
        "individual_layer_enabled": False,
        "created_at": datetime.now(UTC),
    }
    base.update(over)
    return base


def _make_db(
    tmp_path: Path, rows: list[dict[str, Any]], name: str = "golden.duckdb"
) -> Path:
    db = tmp_path / name
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    cols = ", ".join(_DIALOG_COLS)
    ph = ", ".join("?" for _ in _DIALOG_COLS)
    for r in rows:
        con.execute(
            f"INSERT INTO raw_dialog.dialog ({cols}) VALUES ({ph})",  # noqa: S608  # static column list
            [r[c] for c in _DIALOG_COLS],
        )
    con.execute("CHECKPOINT")
    con.close()
    return db


def test_projection_is_subset_of_allowlist() -> None:
    """Loader must only project allow-listed raw_dialog columns."""
    assert set(_PROJECTION) <= ALLOWED_RAW_DIALOG_KEYS


def test_windows_group_by_individual_and_order(tmp_path: Path) -> None:
    rows = [
        _row(
            id="1",
            speaker_agent_id="a_kant_001",
            speaker_persona_id="kant",
            tick=2,
            turn_index=0,
            utterance="second",
        ),
        _row(
            id="2",
            speaker_agent_id="a_kant_001",
            speaker_persona_id="kant",
            tick=1,
            turn_index=0,
            utterance="first",
        ),
        _row(
            id="3",
            speaker_agent_id="a_nz_001",
            speaker_persona_id="nietzsche",
            tick=1,
            turn_index=0,
            utterance="nz",
        ),
    ]
    db = _make_db(tmp_path, rows)
    view = connect_analysis_view(db)
    try:
        loaded = list(load_individual_windows(view))
    finally:
        view.close()

    assert len(loaded) == 1
    run = loaded[0]
    assert run.run_id == "run0"
    by_id = {w.individual_id: w for w in run.windows}
    assert set(by_id) == {"a_kant_001", "a_nz_001"}
    kant = by_id["a_kant_001"]
    assert kant.base_persona_id == "kant"
    # ordered by (tick, turn_index): first then second
    assert kant.utterances == ("first", "second")
    assert kant.ticks == (1, 2)
    # base_groups: each base maps to its individuals
    bg = dict(run.base_groups)
    assert bg["kant"] == ("a_kant_001",)
    assert bg["nietzsche"] == ("a_nz_001",)


def test_source_filter_hash_deterministic_and_content_sensitive(tmp_path: Path) -> None:
    rows = [_row(id="1", tick=1), _row(id="2", tick=5)]
    db = _make_db(tmp_path, rows)
    view = connect_analysis_view(db)
    try:
        h1 = next(iter(load_individual_windows(view))).windows[0].source_filter_hash
        h2 = next(iter(load_individual_windows(view))).windows[0].source_filter_hash
    finally:
        view.close()
    assert h1 == h2  # deterministic across loads

    # A different tick range perturbs the hash.
    db2 = _make_db(
        tmp_path, [_row(id="1", tick=1), _row(id="2", tick=999)], name="golden2.duckdb"
    )
    view2 = connect_analysis_view(db2)
    try:
        h3 = next(iter(load_individual_windows(view2))).windows[0].source_filter_hash
    finally:
        view2.close()
    assert h3 != h1


def test_mixed_epoch_raises(tmp_path: Path) -> None:
    rows = [
        _row(id="1", tick=1, epoch_phase="autonomous"),
        _row(id="2", tick=2, epoch_phase="evaluation"),
    ]
    db = _make_db(tmp_path, rows)
    view = connect_analysis_view(db)
    try:
        with pytest.raises(IndividuationLoaderError, match="epoch"):
            list(load_individual_windows(view))
    finally:
        view.close()


def test_sentinel_value_in_row_raises(tmp_path: Path) -> None:
    """A planted leak sentinel value trips the contamination re-assert."""
    rows = [_row(id="1", utterance=f"{SENTINEL_LEAK_PREFIX}BURROWS_4_2")]
    db = _make_db(tmp_path, rows)
    view = connect_analysis_view(db)
    try:
        with pytest.raises(EvaluationContaminationError):
            list(load_individual_windows(view))
    finally:
        view.close()


def test_run_id_filter(tmp_path: Path) -> None:
    rows = [
        _row(id="1", run_id="run0"),
        _row(id="2", run_id="run1", speaker_agent_id="a_kant_001"),
    ]
    db = _make_db(tmp_path, rows)
    view = connect_analysis_view(db)
    try:
        loaded = list(load_individual_windows(view, run_id="run1"))
    finally:
        view.close()
    assert [r.run_id for r in loaded] == ["run1"]
