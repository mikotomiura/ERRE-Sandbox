"""M11-C3b multi-encoder centroid panel coverage (P1b).

Exercises :func:`compute_centroid_panel` on a same-base 3-rikyu DuckDB run with
three stub encoders (distinct model ids), asserting per-encoder centroid
(per_dyad) + within-floor (per_individual) rows are emitted and tagged with the
right ``embedding_model_id`` (so they stay distinct under the HIGH-2 natural
key). A real-encoder smoke (``build_embedding_provider``) is importorskip- +
opt-in-gated to keep base CI free of model downloads.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest

from erre_sandbox.evidence.eval_store import bootstrap_schema, connect_analysis_view
from erre_sandbox.evidence.individuation.centroid_panel import compute_centroid_panel
from erre_sandbox.evidence.individuation.layer1 import stub_embedding_provider
from erre_sandbox.evidence.individuation.policy import (
    AggregationLevel,
    MetricStatus,
)

_NOW = datetime(2026, 5, 28, tzinfo=UTC)
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

_STUB_IDS = (
    "sentence-transformers/all-mpnet-base-v2",
    "intfloat/multilingual-e5-large",
    "BAAI/bge-m3",
)


def _row(idx: int, agent: str, utt: str) -> dict[str, Any]:
    return {
        "id": f"{agent}-{idx}",
        "run_id": "run0",
        "dialog_id": "d0",
        "tick": idx,
        "turn_index": 0,
        "speaker_agent_id": agent,
        "speaker_persona_id": "rikyu",
        "addressee_agent_id": "a_other",
        "addressee_persona_id": "other",
        "utterance": utt,
        "mode": "",
        "zone": "chashitsu",
        "reasoning": "",
        "epoch_phase": "autonomous",
        "individual_layer_enabled": True,
        "created_at": _NOW,
    }


def _make_run(tmp_path: Path) -> Path:
    """Three same-base rikyu individuals, 8 utterances each (within-floor valid)."""
    rows: list[dict[str, Any]] = []
    idx = 0
    for individual in ("a_rikyu_001", "a_rikyu_002", "a_rikyu_003"):
        for u in range(8):
            idx += 1
            rows.append(
                _row(idx, individual, f"{individual} reflects on tea utterance {u}")
            )
    db = tmp_path / "panel.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    cols = ", ".join(_DIALOG_COLS)
    ph = ", ".join("?" for _ in _DIALOG_COLS)
    for r in rows:
        con.execute(
            f"INSERT INTO raw_dialog.dialog ({cols}) VALUES ({ph})",  # noqa: S608  # static cols
            [r[c] for c in _DIALOG_COLS],
        )
    con.execute("CHECKPOINT")
    con.close()
    return db


def _panel(db: Path) -> list[Any]:
    encoders = [stub_embedding_provider(mid) for mid in _STUB_IDS]
    view = connect_analysis_view(db)
    try:
        return compute_centroid_panel(
            view, encoders=encoders, computed_at=_NOW, run_id="run0"
        )
    finally:
        view.close()


def test_panel_emits_centroid_and_floor_per_encoder(tmp_path: Path) -> None:
    rows = _panel(_make_run(tmp_path))
    centroids = [r for r in rows if r.metric_name == "semantic_centroid_distance"]
    floors = [r for r in rows if r.metric_name == "semantic_centroid_within_floor"]
    # 3 dyads (C(3,2)) x 3 encoders, 3 individuals x 3 encoders.
    assert len(centroids) == 9
    assert len(floors) == 9
    assert all(r.aggregation_level is AggregationLevel.PER_DYAD for r in centroids)
    assert all(r.aggregation_level is AggregationLevel.PER_INDIVIDUAL for r in floors)


def test_panel_rows_are_valid_and_tagged(tmp_path: Path) -> None:
    rows = _panel(_make_run(tmp_path))
    assert all(r.status is MetricStatus.VALID for r in rows)
    tagged = {r.provenance.embedding_model_id for r in rows}
    assert tagged == set(_STUB_IDS)


def test_panel_each_encoder_has_full_dyad_and_floor_set(tmp_path: Path) -> None:
    rows = _panel(_make_run(tmp_path))
    for mid in _STUB_IDS:
        per_encoder = [r for r in rows if r.provenance.embedding_model_id == mid]
        centroids = [
            r for r in per_encoder if r.metric_name == "semantic_centroid_distance"
        ]
        floors = [
            r for r in per_encoder if r.metric_name == "semantic_centroid_within_floor"
        ]
        assert len(centroids) == 3, mid
        assert len(floors) == 3, mid


def test_panel_natural_keys_distinct_across_encoders(tmp_path: Path) -> None:
    # The whole point of HIGH-2: same (dyad, metric) but different encoder must
    # produce distinct natural keys. embedding_model_id is the discriminator.
    rows = _panel(_make_run(tmp_path))
    keys = {
        (
            r.run_id,
            r.individual_id,
            r.metric_name,
            r.channel.value,
            r.aggregation_level.value,
            r.tick,
            r.provenance.source_filter_hash,
            r.provenance.embedding_model_id,
        )
        for r in rows
    }
    assert len(keys) == len(rows)  # no collisions


# --- real-encoder smoke (gated) --------------------------------------------

_RUN_REAL_MPNET = os.environ.get("ERRE_RUN_REAL_MPNET_TESTS") == "1"


@pytest.mark.eval
@pytest.mark.skipif(
    not _RUN_REAL_MPNET,
    reason=(
        "MPNet (~440MB) download avoided in base CI;"
        " set ERRE_RUN_REAL_MPNET_TESTS=1 to opt-in"
    ),
)
def test_panel_runs_with_real_mpnet_encoder(tmp_path: Path) -> None:
    pytest.importorskip("sentence_transformers")
    from erre_sandbox.evidence.individuation.layer1 import build_embedding_provider
    from erre_sandbox.evidence.tier_b.vendi import DEFAULT_ENCODER_MODEL_ID

    db = _make_run(tmp_path)
    view = connect_analysis_view(db)
    try:
        rows = compute_centroid_panel(
            view,
            encoders=[build_embedding_provider(DEFAULT_ENCODER_MODEL_ID)],
            computed_at=_NOW,
            run_id="run0",
        )
    finally:
        view.close()
    centroids = [r for r in rows if r.metric_name == "semantic_centroid_distance"]
    assert len(centroids) == 3
    assert all(r.status is MetricStatus.VALID for r in centroids)
    assert all(
        r.provenance.embedding_model_id == DEFAULT_ENCODER_MODEL_ID for r in centroids
    )
