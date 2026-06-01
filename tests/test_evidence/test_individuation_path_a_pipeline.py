"""M10-A S3.5 path(a) assembly coverage (synthetic DuckDB, CPU, stub provider).

Drives the thin assembly (``compute_individuation`` + ``load_individual_state_windows``
→ :class:`PathARunInput`) on a hand-built same-base 3-individual run, then scores a
full 3-seed experiment end-to-end. No GPU / model: ``world_model_overlap_jaccard`` /
``belief_variance`` are ``embedding_required=False`` and the centroid uses the stub
provider. Confirms the BLK-1 finding survives the real wiring (differentiated SWM →
④ INVALID → experiment INVALID, never GO).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import duckdb

from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.eval_store import bootstrap_schema, connect_analysis_view
from erre_sandbox.evidence.individuation.layer1 import stub_embedding_provider
from erre_sandbox.evidence.individuation.path_a_gate import (
    PathAVerdict,
    score_path_a_gate,
)
from erre_sandbox.evidence.individuation.path_a_pipeline import (
    PathAExperiment,
    assemble_path_a_run_from_view,
)
from erre_sandbox.evidence.individuation.runner import IndividuationContext
from erre_sandbox.evidence.individuation.trace_ddl import (
    TABLE_NAME,
    bootstrap_individual_state_trace_schema,
    column_names,
)

if TYPE_CHECKING:
    from pathlib import Path

_NOW = datetime(2026, 6, 1, tzinfo=UTC)
_IDS = ("a_rikyu_001", "a_rikyu_002", "a_rikyu_003")
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

# differentiated SWM (spike B) + >= 2 belief classes per individual.
_SWM = {
    _IDS[0]: [["self", "rd"], ["env", "agora"], ["env", "study"]],
    _IDS[1]: [["self", "rd"], ["env", "peripatos"], ["env", "agora"]],
    _IDS[2]: [["self", "rd"], ["env", "chashitsu"], ["env", "garden"]],
}
_BELIEFS = {
    _IDS[0]: ["trust", "wary"],
    _IDS[1]: ["trust", "trust", "wary"],
    _IDS[2]: ["trust", "wary", "wary"],
}


def _dialog_row(agent: str, run_id: str) -> dict[str, Any]:
    return {
        "id": f"{run_id}-{agent}-1",
        "run_id": run_id,
        "dialog_id": "d0",
        "tick": 1,
        "turn_index": 0,
        "speaker_agent_id": agent,
        "speaker_persona_id": "rikyu",
        "addressee_agent_id": "a_other",
        "addressee_persona_id": "other",
        "utterance": "the of and study here please",
        "mode": "",
        "zone": "study",
        "reasoning": "",
        "epoch_phase": "evaluation",
        "individual_layer_enabled": True,
        "created_at": _NOW,
    }


def _build_db(path: Path, run_id: str) -> None:
    con = duckdb.connect(str(path), read_only=False)
    bootstrap_schema(con)
    bootstrap_individual_state_trace_schema(con, METRICS_SCHEMA)
    cols = ", ".join(_DIALOG_COLS)
    ph = ", ".join("?" for _ in _DIALOG_COLS)
    tcols = ", ".join(column_names())
    tph = ", ".join("?" for _ in column_names())
    for agent in _IDS:
        row = _dialog_row(agent, run_id)
        con.execute(
            f"INSERT INTO raw_dialog.dialog ({cols}) VALUES ({ph})",  # noqa: S608
            [row[c] for c in _DIALOG_COLS],
        )
        con.execute(
            f"INSERT INTO {METRICS_SCHEMA}.{TABLE_NAME} ({tcols}) VALUES ({tph})",  # noqa: S608
            (
                run_id,
                agent,
                1,
                None,
                None,
                json.dumps(_BELIEFS[agent]),
                0,
                json.dumps(_SWM[agent]),
            ),
        )
    con.execute("CHECKPOINT")
    con.close()


def _ctx(path: Path) -> IndividuationContext:
    return IndividuationContext(
        personas_dir=path.parent, provider=stub_embedding_provider(), computed_at=_NOW
    )


def test_assemble_run_from_view_well_formed(tmp_path: Path) -> None:
    db = tmp_path / "run0.duckdb"
    _build_db(db, "run0")
    view = connect_analysis_view(db)
    try:
        run_input = assemble_path_a_run_from_view(
            view, run_id="run0", run_idx=0, ctx=_ctx(db)
        )
    finally:
        view.close()
    assert run_input.run_idx == 0
    assert run_input.base_persona_id == "rikyu"
    assert len(run_input.individuals) == 3
    assert {i.individual_id for i in run_input.individuals} == set(_IDS)
    # SWM + belief substrate populated from the trace.
    assert all(i.world_model_keys is not None for i in run_input.individuals)
    assert all(i.belief_classes is not None for i in run_input.individuals)
    # 3 per-individual belief_variance + 3 per-dyad jaccard rows.
    assert len(run_input.belief_variance_rows) == 3
    assert len(run_input.jaccard_rows) == 3


def test_full_experiment_blk1_invalid(tmp_path: Path) -> None:
    """End-to-end: differentiated SWM through the real wiring → INVALID, never GO."""
    runs = []
    for idx in range(3):
        db = tmp_path / f"run{idx}.duckdb"
        _build_db(db, f"run{idx}")
        view = connect_analysis_view(db)
        try:
            runs.append(
                assemble_path_a_run_from_view(
                    view, run_id=f"run{idx}", run_idx=idx, ctx=_ctx(db)
                )
            )
        finally:
            view.close()
    report = score_path_a_gate(PathAExperiment(run_id="pilot", runs=tuple(runs)))
    assert report.verdict is PathAVerdict.INVALID
    assert report.verdict is not PathAVerdict.GO
