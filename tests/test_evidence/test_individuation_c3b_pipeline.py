"""M11-C3b verdict pipeline: derive_preflight (B-2), GO integration, B-4/B-5.

GPU-free wiring proof. ``derive_preflight`` is unit-tested by dropping each piece
of machine-readable evidence (B-2 — the ADR §10 hard stop is executable, not a
hand-set bool). An end-to-end synthetic-DuckDB run with a deterministic
orthogonal **stub** encoder reaches GO, persists the panel sidecar (never the
DuckDB metrics table, B-4), and never imports ``sentence-transformers`` (B-5).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pytest

from erre_sandbox.evidence.capture_sidecar import (
    SidecarV1,
    sidecar_path_for,
    write_sidecar_atomic,
)
from erre_sandbox.evidence.eval_store import bootstrap_schema
from erre_sandbox.evidence.individuation.c3b_pipeline import (
    build_condition_run,
    derive_preflight,
    run_c3b_verdict_pipeline,
)
from erre_sandbox.evidence.individuation.centroid_panel_report import (
    centroid_panel_sidecar_path_for,
)
from erre_sandbox.evidence.individuation.layer1 import EmbeddingProvider
from erre_sandbox.evidence.individuation.models import MetricResult, Provenance
from erre_sandbox.evidence.individuation.policy import (
    AggregationLevel,
    MetricChannel,
    MetricStatus,
)
from erre_sandbox.evidence.individuation.report import (
    build_report,
    individuation_sidecar_path_for,
    write_individuation_sidecar_atomic,
)

_NOW = datetime(2026, 5, 28, 12, 0, tzinfo=UTC)
_MPNET = "sentence-transformers/all-mpnet-base-v2"
_E5 = "intfloat/multilingual-e5-large"
_BGE = "BAAI/bge-m3"
_PANEL_IDS = (_MPNET, _E5, _BGE)
_INDIVIDUALS = ("a_rikyu_001", "a_rikyu_002", "a_rikyu_003")

# Orthogonal per-individual vectors: within-individual floor collapses to 0.0
# (identical utterances) while every cross-individual distance is 1.0 -> a
# deterministic GO without depending on natural-language embedding geometry.
_IND_VECTORS = {
    "a_rikyu_001": [1.0, 0.0, 0.0, 0.0],
    "a_rikyu_002": [0.0, 1.0, 0.0, 0.0],
    "a_rikyu_003": [0.0, 0.0, 1.0, 0.0],
}


def _orthogonal_provider(model_id: str) -> EmbeddingProvider:
    def encoder(batch: Any) -> list[list[float]]:
        out: list[list[float]] = []
        for s in batch:
            vec = next(
                (v for ind, v in _IND_VECTORS.items() if ind in str(s)),
                [0.0, 0.0, 0.0, 1.0],
            )
            out.append(list(vec))
        return out

    def vendi_kernel(items: Any) -> np.ndarray:
        return np.eye(len(list(items)), dtype=float)

    return EmbeddingProvider(
        embedding_model_id=model_id, encoder=encoder, vendi_kernel=vendi_kernel
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


def _dialog_row(
    idx: int, run_id: str, agent: str, utt: str, *, layer_on: bool
) -> dict[str, Any]:
    return {
        "id": f"{run_id}-{agent}-{idx}",
        "run_id": run_id,
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
        "individual_layer_enabled": layer_on,
        "created_at": _NOW,
    }


def _burrows_row(individual: str, value: float) -> MetricResult:
    return MetricResult(
        run_id="r",
        individual_id=individual,
        base_persona_id="rikyu",
        aggregation_level=AggregationLevel.PER_INDIVIDUAL,
        tick=-1,
        metric_name="burrows_base_retention",
        channel=MetricChannel.UTTERANCE,
        status=MetricStatus.VALID,
        value=value,
        reason=None,
        provenance=Provenance(
            metric_schema_version="m10-0.1",
            source_table="raw_dialog.dialog",
            source_run_id="r",
            source_epoch_phase="autonomous",
            source_individual_layer_enabled=True,
            source_filter_hash="sfh",
            embedding_model_id=None,
        ),
        computed_at=_NOW,
    )


def _make_capture(
    tmp_path: Path, *, run_idx: int, layer_on: bool, utterances: int = 8
) -> Path:
    """One same-base 3-rikyu capture DuckDB + capture + individuation sidecars."""
    run_id = f"rikyu_natural_run{run_idx}"
    rows: list[dict[str, Any]] = []
    idx = 0
    for individual in _INDIVIDUALS:
        for u in range(utterances):
            idx += 1
            rows.append(
                _dialog_row(
                    idx, run_id, individual, f"{individual} tea {u}", layer_on=layer_on
                )
            )
    suffix = "on" if layer_on else "off"
    db = tmp_path / f"run{run_idx}_{suffix}.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    cols = ", ".join(_DIALOG_COLS)
    ph = ", ".join("?" for _ in _DIALOG_COLS)
    for r in rows:
        con.execute(
            f"INSERT INTO raw_dialog.dialog ({cols}) VALUES ({ph})",  # noqa: S608
            [r[c] for c in _DIALOG_COLS],
        )
    con.execute("CHECKPOINT")
    con.close()

    capture = SidecarV1(
        status="complete",
        stop_reason="complete",
        focal_target=len(rows),
        focal_observed=len(rows),
        total_rows=len(rows),
        wall_timeout_min=120.0,
        drain_completed=True,
        runtime_drain_timeout=False,
        git_sha="abc1234",
        captured_at="2026-05-28T12:00:00Z",
        persona="rikyu",
        condition="natural",
        run_idx=run_idx,
        duckdb_path=str(db),
        elapsed_seconds=1200.0,
    )
    write_sidecar_atomic(sidecar_path_for(db), capture)

    deltas = (1.0, 1.0, 1.0) if layer_on else (2.0, 2.0, 2.0)
    burrows = [_burrows_row(i, d) for i, d in zip(_INDIVIDUALS, deltas, strict=True)]
    write_individuation_sidecar_atomic(
        individuation_sidecar_path_for(db),
        build_report(run_id, burrows, computed_at=_NOW),
    )
    return db


def _full_pilot(tmp_path: Path, *, utterances: int = 8) -> list[Path]:
    return [
        _make_capture(tmp_path, run_idx=r, layer_on=on, utterances=utterances)
        for r in (0, 1)
        for on in (True, False)
    ]


# --- B-2: derive_preflight (drop each evidence) ----------------------------


def _floor_rows(
    individuals: tuple[str, ...],
    *,
    layer_on: bool,
    encoders: tuple[str, ...] = _PANEL_IDS,
) -> list[MetricResult]:
    return [
        MetricResult(
            run_id="r",
            individual_id=ind,
            base_persona_id="rikyu",
            aggregation_level=AggregationLevel.PER_INDIVIDUAL,
            tick=-1,
            metric_name="semantic_centroid_within_floor",
            channel=MetricChannel.UTTERANCE,
            status=MetricStatus.VALID,
            value=0.1,
            reason=None,
            provenance=Provenance(
                metric_schema_version="m10-0.1",
                source_table="raw_dialog.dialog",
                source_run_id="r",
                source_epoch_phase="autonomous",
                source_individual_layer_enabled=layer_on,
                source_filter_hash="sfh",
                embedding_model_id=enc,
            ),
            computed_at=_NOW,
        )
        for enc in encoders
        for ind in individuals
    ]


def _capture(*, status: str = "complete", elapsed: float | None = 1200.0) -> SidecarV1:
    return SidecarV1(
        status=status,  # type: ignore[arg-type]
        stop_reason="complete",
        focal_target=24,
        focal_observed=24,
        total_rows=24,
        wall_timeout_min=120.0,
        drain_completed=True,
        runtime_drain_timeout=False,
        git_sha="abc",
        captured_at="2026-05-28T12:00:00Z",
        persona="rikyu",
        condition="natural",
        run_idx=0,
        duckdb_path="x.duckdb",
        elapsed_seconds=elapsed,
    )


def test_preflight_ok_for_complete_evidence() -> None:
    rows = _floor_rows(_INDIVIDUALS, layer_on=True)
    assert derive_preflight(rows, _capture(), used_encoder_ids=_PANEL_IDS).ok


def test_preflight_fail_when_fewer_than_three_individuals() -> None:
    rows = _floor_rows(_INDIVIDUALS[:2], layer_on=True)
    res = derive_preflight(rows, _capture(), used_encoder_ids=_PANEL_IDS)
    assert not res.ok
    assert "distinct individual" in (res.reason or "")


def test_preflight_fail_when_condition_not_homogeneous() -> None:
    rows = _floor_rows(_INDIVIDUALS, layer_on=True)
    rows += _floor_rows(("a_rikyu_001",), layer_on=False)  # mixed flag
    res = derive_preflight(rows, _capture(), used_encoder_ids=_PANEL_IDS)
    assert not res.ok
    assert "homogeneous" in (res.reason or "")


def test_preflight_fail_when_e5_absent() -> None:
    rows = _floor_rows(_INDIVIDUALS, layer_on=True)
    res = derive_preflight(rows, _capture(), used_encoder_ids=(_MPNET, _BGE))
    assert not res.ok
    assert "primary encoder" in (res.reason or "")


def test_preflight_fail_when_mpnet_absent() -> None:
    rows = _floor_rows(_INDIVIDUALS, layer_on=True)
    res = derive_preflight(rows, _capture(), used_encoder_ids=(_E5, _BGE))
    assert not res.ok
    assert "primary encoder" in (res.reason or "")


def test_preflight_fail_when_elapsed_missing() -> None:
    rows = _floor_rows(_INDIVIDUALS, layer_on=True)
    res = derive_preflight(rows, _capture(elapsed=None), used_encoder_ids=_PANEL_IDS)
    assert not res.ok
    assert "elapsed" in (res.reason or "")


def test_preflight_fail_when_flag_off_not_complete() -> None:
    rows = _floor_rows(_INDIVIDUALS, layer_on=False)  # control
    res = derive_preflight(
        rows, _capture(status="partial"), used_encoder_ids=_PANEL_IDS
    )
    assert not res.ok
    assert "complete" in (res.reason or "")


def test_build_condition_run_derives_condition_from_rows() -> None:
    # individual_layer_enabled is taken from the rows' provenance, not a flag.
    rows = _floor_rows(_INDIVIDUALS, layer_on=True)
    run = build_condition_run(
        panel_rows=rows,
        capture=_capture(),
        burrows_rows=(),
        used_encoder_ids=_PANEL_IDS,
    )
    assert run.individual_layer_enabled is True
    assert run.preflight_ok is True
    assert run.seed == 0


# --- integration: GO end-to-end (B-4 panel-not-in-duckdb, B-5 no-download) ---


def test_pipeline_reaches_go_and_writes_panel_sidecars(tmp_path: Path) -> None:
    caps = _full_pilot(tmp_path)
    encoders = [_orthogonal_provider(mid) for mid in _PANEL_IDS]
    report = run_c3b_verdict_pipeline(
        caps, encoders=encoders, run_id="rikyu_pilot", computed_at=_NOW
    )
    assert report.verdict == "go", report.reason
    assert len(report.seeds) == 2
    for cap in caps:
        assert centroid_panel_sidecar_path_for(cap).exists()


def test_pipeline_does_not_write_panel_to_duckdb(tmp_path: Path) -> None:
    # B-4: the panel never touches metrics.individuation; the M10-0 write path
    # is untouched, so both write caveats are structurally impossible here.
    caps = _full_pilot(tmp_path)
    encoders = [_orthogonal_provider(mid) for mid in _PANEL_IDS]
    run_c3b_verdict_pipeline(
        caps, encoders=encoders, run_id="rikyu_pilot", computed_at=_NOW
    )
    for cap in caps:
        con = duckdb.connect(str(cap), read_only=True)
        try:
            count = con.execute("SELECT count(*) FROM metrics.individuation").fetchone()
        finally:
            con.close()
        assert count is not None
        assert count[0] == 0


def test_pipeline_never_builds_a_downloading_encoder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # B-5 (order-independent): the only production download entry is
    # build_embedding_provider; patch it to explode and prove the stub-injected
    # pipeline reaches a verdict without ever constructing a real encoder. (A
    # global sys.modules check is unreliable here — sibling suites legitimately
    # import sentence_transformers, polluting the module table.)
    from erre_sandbox.evidence.individuation import layer1

    def _boom(model_id: str) -> None:
        msg = f"build_embedding_provider({model_id!r}) would download a model"
        raise AssertionError(msg)

    monkeypatch.setattr(layer1, "build_embedding_provider", _boom)
    caps = _full_pilot(tmp_path)
    encoders = [_orthogonal_provider(mid) for mid in _PANEL_IDS]
    report = run_c3b_verdict_pipeline(
        caps, encoders=encoders, run_id="rikyu_pilot", computed_at=_NOW
    )
    assert report.verdict == "go", report.reason


def test_pipeline_degenerate_dyad_does_not_crash(tmp_path: Path) -> None:
    # B-4 caveat 2: too-few utterances -> degenerate within-floor (None-tagged
    # rows). v1's DuckDB write would collide; the sidecar path just lists them
    # and the scorer returns inconclusive without raising.
    caps = _full_pilot(tmp_path, utterances=3)
    encoders = [_orthogonal_provider(mid) for mid in _PANEL_IDS]
    report = run_c3b_verdict_pipeline(
        caps, encoders=encoders, run_id="rikyu_pilot", computed_at=_NOW
    )
    assert report.verdict == "inconclusive", report.reason


def test_pipeline_invalid_when_evidence_dropped(tmp_path: Path) -> None:
    # B-2 end-to-end: dropping a primary encoder (e5) -> preflight invalid, not
    # inconclusive (closes the "e5 absent looks like a sample shortfall" hatch).
    caps = _full_pilot(tmp_path)
    encoders = [_orthogonal_provider(mid) for mid in (_MPNET, _BGE)]  # no e5
    report = run_c3b_verdict_pipeline(
        caps, encoders=encoders, run_id="rikyu_pilot", computed_at=_NOW
    )
    assert report.verdict == "invalid", report.reason


@pytest.mark.eval
@pytest.mark.skipif(
    "ERRE_RUN_REAL_MPNET_TESTS" not in os.environ,
    reason="real encoder download avoided in base CI (ERRE_RUN_REAL_MPNET_TESTS=1)",
)
def test_pipeline_real_encoder_smoke(tmp_path: Path) -> None:
    pytest.importorskip("sentence_transformers")
    from erre_sandbox.evidence.individuation.layer1 import build_embedding_provider

    caps = _full_pilot(tmp_path)
    encoders = [build_embedding_provider(mid) for mid in (_MPNET, _E5)]
    report = run_c3b_verdict_pipeline(
        caps, encoders=encoders, run_id="rikyu_pilot", computed_at=_NOW
    )
    assert report.verdict in {"go", "reject", "inconclusive", "invalid"}
