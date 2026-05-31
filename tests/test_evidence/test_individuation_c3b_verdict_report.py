"""M11-C3b sidecar contracts (B-3): panel + verdict report roundtrips.

No GPU / model / DuckDB: the verdict sidecar is built from hand-constructed
scorer dataclasses so its JSON schema, the bge-m3 exploratory (gated=False)
provenance, the encoder SHA + lib pin, and emit→read roundtrip equality are
pinned offline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from erre_sandbox.evidence.individuation.c3b_verdict import (
    AxisOutcome,
    AxisResult,
    EncoderGate,
    SeedResult,
    Verdict,
    VerdictReport,
)
from erre_sandbox.evidence.individuation.c3b_verdict_report import (
    LIB_PINS,
    c3b_verdict_sidecar_path_for,
    from_verdict_report,
    read_c3b_verdict_sidecar,
    write_c3b_verdict_sidecar_atomic,
)
from erre_sandbox.evidence.individuation.centroid_panel_report import (
    build_centroid_panel_report,
    centroid_panel_sidecar_path_for,
    read_centroid_panel_sidecar,
    write_centroid_panel_sidecar_atomic,
)
from erre_sandbox.evidence.individuation.models import MetricResult, Provenance
from erre_sandbox.evidence.individuation.policy import (
    DYAD_SEP,
    AggregationLevel,
    MetricChannel,
    MetricStatus,
)

_NOW = datetime(2026, 5, 28, 12, 0, tzinfo=UTC)
_MPNET = "sentence-transformers/all-mpnet-base-v2"
_E5 = "intfloat/multilingual-e5-large"
_BGE = "BAAI/bge-m3"


def _centroid_row(encoder: str, dyad: str, value: float) -> MetricResult:
    return MetricResult(
        run_id="run0",
        individual_id=dyad,
        base_persona_id=f"rikyu{DYAD_SEP}rikyu",
        aggregation_level=AggregationLevel.PER_DYAD,
        tick=-1,
        metric_name="semantic_centroid_distance",
        channel=MetricChannel.UTTERANCE,
        status=MetricStatus.VALID,
        value=value,
        reason=None,
        provenance=Provenance(
            metric_schema_version="m10-0.1",
            source_table="raw_dialog.dialog",
            source_run_id="run0",
            source_epoch_phase="autonomous",
            source_individual_layer_enabled=True,
            source_filter_hash="sfh",
            embedding_model_id=encoder,
        ),
        computed_at=_NOW,
    )


def _go_verdict_report() -> VerdictReport:
    primary_gates = (
        EncoderGate(
            _MPNET, AxisOutcome.PASS, "ok", 0.30, 0.30, 0.10, direction_positive=True
        ),
        EncoderGate(
            _E5, AxisOutcome.PASS, "ok", 0.28, 0.25, 0.09, direction_positive=True
        ),
    )
    # bge-m3 collapses but is exploratory -> recorded, not gated.
    exploratory = (
        EncoderGate(
            _BGE,
            AxisOutcome.FAIL,
            "direction collapse",
            0.05,
            0.05,
            0.1,
            direction_positive=False,
        ),
    )
    seed0 = SeedResult(
        seed=0,
        valid=True,
        centroid=AxisResult(AxisOutcome.PASS, "both primaries pass"),
        burrows=AxisResult(AxisOutcome.PASS, "delta <= 4.0"),
        throughput=AxisResult(AxisOutcome.PASS, ">= 70%"),
        encoder_gates=primary_gates,
        exploratory_gates=exploratory,
    )
    seed1 = SeedResult(seed=1, valid=False, invalid_reason=None, encoder_gates=())
    return VerdictReport(
        run_id="rikyu_same_base_pilot",
        verdict=Verdict.GO,
        reason="all hard axes pass in 2/2 seeds",
        seeds=(seed0, seed1),
    )


# --- panel sidecar ---------------------------------------------------------


def test_panel_sidecar_roundtrip(tmp_path: Path) -> None:
    rows = [_centroid_row(_MPNET, f"a{DYAD_SEP}b", 0.3)]
    report = build_centroid_panel_report(
        "run0", rows, (_MPNET, _E5, _BGE), computed_at=_NOW
    )
    path = centroid_panel_sidecar_path_for(tmp_path / "cap.duckdb")
    write_centroid_panel_sidecar_atomic(path, report)
    assert path.name == "cap.duckdb.centroid_panel.json"
    assert read_centroid_panel_sidecar(path) == report


# --- verdict sidecar (B-3) -------------------------------------------------


def test_verdict_sidecar_roundtrip(tmp_path: Path) -> None:
    report = from_verdict_report(_go_verdict_report(), computed_at=_NOW)
    path = c3b_verdict_sidecar_path_for(tmp_path / "pilot")
    write_c3b_verdict_sidecar_atomic(path, report)
    assert path.name == "pilot.c3b_verdict.json"
    assert read_c3b_verdict_sidecar(path) == report


def test_verdict_sidecar_records_bge_m3_exploratory_ungated() -> None:
    report = from_verdict_report(_go_verdict_report(), computed_at=_NOW)
    by_id = {e.model_id: e for e in report.encoder_panel}
    assert by_id[_MPNET].gated is True
    assert by_id[_E5].gated is True
    assert by_id[_BGE].gated is False
    assert by_id[_BGE].role == "exploratory"
    # bge-m3 gate is recorded in the seed evidence, but ungated.
    seed0 = next(s for s in report.seeds if s.seed == 0)
    bge_gate = next(g for g in seed0.exploratory_gates if g.encoder_id == _BGE)
    assert bge_gate.gated is False
    assert seed0.encoder_gates
    assert all(g.gated for g in seed0.encoder_gates)


def test_verdict_sidecar_carries_sha_and_lib_pins() -> None:
    report = from_verdict_report(_go_verdict_report(), computed_at=_NOW)
    by_id = {e.model_id: e for e in report.encoder_panel}
    assert by_id[_MPNET].revision_sha == "e8c3b32edf5434bc2275fc9bab85f82640a19130"
    assert by_id[_E5].revision_sha == "3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3"
    assert by_id[_BGE].revision_sha == "5617a9f61b028005a4858fdac845db406aefb181"
    assert report.lib_pins == LIB_PINS
    assert report.lib_pins["sentence_transformers"] == "3.4.1"


def test_all_four_verdict_states_serialise(tmp_path: Path) -> None:
    for i, verdict in enumerate(Verdict):
        base = _go_verdict_report()
        report = from_verdict_report(
            VerdictReport(
                run_id=base.run_id,
                verdict=verdict,
                reason=f"{verdict.value} reason",
                seeds=base.seeds,
            ),
            computed_at=_NOW,
        )
        path = c3b_verdict_sidecar_path_for(tmp_path / f"v{i}")
        write_c3b_verdict_sidecar_atomic(path, report)
        assert read_c3b_verdict_sidecar(path).verdict == verdict.value
