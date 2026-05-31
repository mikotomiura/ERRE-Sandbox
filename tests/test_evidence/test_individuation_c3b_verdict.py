"""M11-C3b verdict scorer precedence coverage (P1b, synthetic fixtures).

No GPU / model / DuckDB: every input is a hand-built :class:`MetricResult` so
the four-state precedence (invalid > REJECT > inconclusive > GO) and each hard
axis (per-encoder centroid gate, encoder agreement, Burrows, throughput) is
pinned against the frozen ADR thresholds. This is the "GO 基準後出し封じ" guard
(PR-21 lesson) made executable.
"""

from __future__ import annotations

from datetime import UTC, datetime

from erre_sandbox.evidence.individuation.c3b_verdict import (
    PRIMARY_ENCODER_IDS as PRIMARIES,
)
from erre_sandbox.evidence.individuation.c3b_verdict import (
    ConditionRun,
    Verdict,
    VerdictExperiment,
    score_c3b_verdict,
)
from erre_sandbox.evidence.individuation.models import MetricResult, Provenance
from erre_sandbox.evidence.individuation.policy import (
    DYAD_SEP,
    AggregationLevel,
    MetricChannel,
    MetricStatus,
)

_NOW = datetime(2026, 5, 28, tzinfo=UTC)
_INDIVIDUALS = ("a_rikyu_001", "a_rikyu_002", "a_rikyu_003")
_DYADS = (
    f"a_rikyu_001{DYAD_SEP}a_rikyu_002",
    f"a_rikyu_001{DYAD_SEP}a_rikyu_003",
    f"a_rikyu_002{DYAD_SEP}a_rikyu_003",
)


def _prov(model_id: str | None, sfh: str) -> Provenance:
    return Provenance(
        metric_schema_version="m10-0.1",
        source_table="raw_dialog.dialog",
        source_run_id="run0",
        source_epoch_phase="autonomous",
        source_individual_layer_enabled=True,
        source_filter_hash=sfh,
        embedding_model_id=model_id,
    )


def _centroid(encoder: str, dyad: str, value: float | None) -> MetricResult:
    valid = value is not None
    return MetricResult(
        run_id="run0",
        individual_id=dyad,
        base_persona_id=f"rikyu{DYAD_SEP}rikyu",
        aggregation_level=AggregationLevel.PER_DYAD,
        tick=-1,
        metric_name="semantic_centroid_distance",
        channel=MetricChannel.UTTERANCE,
        status=MetricStatus.VALID if valid else MetricStatus.DEGENERATE,
        value=value,
        reason=None if valid else "degenerate dyad",
        provenance=_prov(encoder if valid else None, dyad),
        computed_at=_NOW,
    )


def _floor(encoder: str, individual: str, value: float | None) -> MetricResult:
    valid = value is not None
    return MetricResult(
        run_id="run0",
        individual_id=individual,
        base_persona_id="rikyu",
        aggregation_level=AggregationLevel.PER_INDIVIDUAL,
        tick=-1,
        metric_name="semantic_centroid_within_floor",
        channel=MetricChannel.UTTERANCE,
        status=MetricStatus.VALID if valid else MetricStatus.DEGENERATE,
        value=value,
        reason=None if valid else "degenerate floor",
        provenance=_prov(encoder if valid else None, individual),
        computed_at=_NOW,
    )


def _burrows(individual: str, value: float | None) -> MetricResult:
    valid = value is not None
    return MetricResult(
        run_id="run0",
        individual_id=individual,
        base_persona_id="rikyu",
        aggregation_level=AggregationLevel.PER_INDIVIDUAL,
        tick=-1,
        metric_name="burrows_base_retention",
        channel=MetricChannel.UTTERANCE,
        status=MetricStatus.VALID if valid else MetricStatus.UNSUPPORTED,
        value=value,
        reason=None if valid else "ja adapter unfired",
        provenance=_prov(None, individual),
        computed_at=_NOW,
    )


def _encoder_panel(
    encoder: str, *, cross: tuple[float | None, ...], floor: float
) -> list[MetricResult]:
    rows = [_centroid(encoder, d, c) for d, c in zip(_DYADS, cross, strict=True)]
    rows += [_floor(encoder, i, floor) for i in _INDIVIDUALS]
    return rows


def _good_panel(
    *, cross: tuple[float | None, ...] = (0.30, 0.30, 0.30), floor: float = 0.10
) -> tuple[MetricResult, ...]:
    rows: list[MetricResult] = []
    for e in PRIMARIES:
        rows += _encoder_panel(e, cross=cross, floor=floor)
    return tuple(rows)


def _good_burrows(
    deltas: tuple[float | None, ...] = (1.0, 1.0, 1.0),
) -> tuple[MetricResult, ...]:
    return tuple(_burrows(i, d) for i, d in zip(_INDIVIDUALS, deltas, strict=True))


def _treatment(seed: int, **kw: object) -> ConditionRun:
    return ConditionRun(
        seed=seed,
        individual_layer_enabled=True,
        preflight_ok=bool(kw.get("preflight", True)),
        capture_status=str(kw.get("status", "complete")),
        focal_rows=int(kw.get("focal", 24)),  # type: ignore[arg-type]
        elapsed_seconds=kw.get("elapsed", 1200.0),  # type: ignore[arg-type]
        panel_rows=kw.get("panel", _good_panel()),  # type: ignore[arg-type]
        burrows_rows=kw.get("burrows", _good_burrows()),  # type: ignore[arg-type]
    )


def _control(seed: int, **kw: object) -> ConditionRun:
    return ConditionRun(
        seed=seed,
        individual_layer_enabled=False,
        preflight_ok=bool(kw.get("preflight", True)),
        capture_status=str(kw.get("status", "complete")),
        focal_rows=int(kw.get("focal", 24)),  # type: ignore[arg-type]
        elapsed_seconds=kw.get("elapsed", 1200.0),  # type: ignore[arg-type]
        panel_rows=(),
        burrows_rows=kw.get("burrows", _good_burrows((2.0, 2.0, 2.0))),  # type: ignore[arg-type]
    )


def _experiment(*runs: ConditionRun) -> VerdictExperiment:
    return VerdictExperiment(run_id="run0", runs=tuple(runs))


# --- GO --------------------------------------------------------------------


def test_go_when_all_axes_pass_in_both_seeds() -> None:
    report = score_c3b_verdict(
        _experiment(_treatment(0), _control(0), _treatment(1), _control(1))
    )
    assert report.verdict is Verdict.GO, report.reason


# --- REJECT (each §5.4 trigger) --------------------------------------------


def test_reject_on_direction_collapse() -> None:
    # cross median <= floor -> direction collapse (§5.4.1).
    bad = _good_panel(cross=(0.05, 0.05, 0.05), floor=0.10)
    report = score_c3b_verdict(
        _experiment(_treatment(0, panel=bad), _control(0), _treatment(1), _control(1))
    )
    assert report.verdict is Verdict.REJECT
    assert "direction collapse" in report.reason


def test_reject_on_gate_margin_miss() -> None:
    # direction positive (0.12 > 0.10) but below 1.5x floor (0.15) -> gate miss.
    bad = _good_panel(cross=(0.12, 0.12, 0.12), floor=0.10)
    report = score_c3b_verdict(
        _experiment(_treatment(0, panel=bad), _control(0), _treatment(1), _control(1))
    )
    assert report.verdict is Verdict.REJECT
    assert "gate miss" in report.reason


def test_reject_on_backstop_miss() -> None:
    # median ok but min dyad below 0.02 absolute backstop.
    bad = _good_panel(cross=(0.30, 0.30, 0.01), floor=0.10)
    report = score_c3b_verdict(
        _experiment(_treatment(0, panel=bad), _control(0), _treatment(1), _control(1))
    )
    assert report.verdict is Verdict.REJECT


def test_reject_on_burrows_above_absolute_max() -> None:
    bad = _good_burrows((5.0, 1.0, 1.0))  # 5.0 > 4.0
    report = score_c3b_verdict(
        _experiment(_treatment(0, burrows=bad), _control(0), _treatment(1), _control(1))
    )
    assert report.verdict is Verdict.REJECT
    assert "4.0" in report.reason


def test_reject_on_burrows_worse_than_control() -> None:
    # treatment delta 3.0 <= 4.0 but > flag-off control 2.0 -> control-ratio fail.
    report = score_c3b_verdict(
        _experiment(
            _treatment(0, burrows=_good_burrows((3.0, 1.0, 1.0))),
            _control(0, burrows=_good_burrows((2.0, 2.0, 2.0))),
            _treatment(1),
            _control(1),
        )
    )
    assert report.verdict is Verdict.REJECT


def test_reject_on_throughput_below_70pct() -> None:
    # treatment elapsed huge -> throughput < 0.70 x control.
    report = score_c3b_verdict(
        _experiment(
            _treatment(0, elapsed=4000.0),
            _control(0, elapsed=1200.0),
            _treatment(1),
            _control(1),
        )
    )
    assert report.verdict is Verdict.REJECT
    assert "throughput" in report.reason


# --- inconclusive ----------------------------------------------------------


def test_inconclusive_when_only_one_seed() -> None:
    report = score_c3b_verdict(_experiment(_treatment(0), _control(0)))
    assert report.verdict is Verdict.INCONCLUSIVE
    assert "seed" in report.reason


def test_inconclusive_on_degenerate_dyad() -> None:
    # One dyad degenerate -> encoder INSUFFICIENT -> inconclusive (no hard fail).
    short = _good_panel(cross=(0.30, 0.30, None), floor=0.10)
    report = score_c3b_verdict(
        _experiment(_treatment(0, panel=short), _control(0), _treatment(1), _control(1))
    )
    assert report.verdict is Verdict.INCONCLUSIVE


def test_inconclusive_when_all_burrows_unsupported() -> None:
    unsupported = _good_burrows((None, None, None))
    report = score_c3b_verdict(
        _experiment(
            _treatment(0, burrows=unsupported),
            _control(0),
            _treatment(1),
            _control(1),
        )
    )
    assert report.verdict is Verdict.INCONCLUSIVE


# --- invalid ---------------------------------------------------------------


def test_invalid_when_preflight_not_satisfied() -> None:
    report = score_c3b_verdict(
        _experiment(
            _treatment(0, preflight=False), _control(0), _treatment(1), _control(1)
        )
    )
    assert report.verdict is Verdict.INVALID
    assert "preflight" in report.reason


def test_invalid_when_flag_off_not_complete() -> None:
    # flag-off reference must be status=complete to be a throughput denominator.
    report = score_c3b_verdict(
        _experiment(
            _treatment(0), _control(0, status="partial"), _treatment(1), _control(1)
        )
    )
    assert report.verdict is Verdict.INVALID


def test_invalid_when_treatment_elapsed_missing() -> None:
    report = score_c3b_verdict(
        _experiment(
            _treatment(0, elapsed=None), _control(0), _treatment(1), _control(1)
        )
    )
    assert report.verdict is Verdict.INVALID


# --- precedence (invalid > REJECT > inconclusive > GO) ----------------------


def test_invalid_takes_precedence_over_reject() -> None:
    # seed 0 invalid (preflight) AND seed 1 has a hard fail -> invalid wins.
    bad = _good_panel(cross=(0.05, 0.05, 0.05), floor=0.10)
    report = score_c3b_verdict(
        _experiment(
            _treatment(0, preflight=False),
            _control(0),
            _treatment(1, panel=bad),
            _control(1),
        )
    )
    assert report.verdict is Verdict.INVALID


def test_reject_takes_precedence_over_inconclusive() -> None:
    # seed 0 hard fail, seed 1 sample shortfall -> REJECT wins.
    bad = _good_panel(cross=(0.05, 0.05, 0.05), floor=0.10)
    short = _good_panel(cross=(0.30, 0.30, None), floor=0.10)
    report = score_c3b_verdict(
        _experiment(
            _treatment(0, panel=bad),
            _control(0),
            _treatment(1, panel=short),
            _control(1),
        )
    )
    assert report.verdict is Verdict.REJECT


def test_single_encoder_only_is_insufficient_not_go() -> None:
    # Only mpnet rows present (e5 missing) -> e5 gate INSUFFICIENT -> inconclusive.
    mpnet_only = tuple(
        _encoder_panel(PRIMARIES[0], cross=(0.30, 0.30, 0.30), floor=0.10)
    )
    report = score_c3b_verdict(
        _experiment(
            _treatment(0, panel=mpnet_only),
            _control(0),
            _treatment(1, panel=mpnet_only),
            _control(1),
        )
    )
    assert report.verdict is Verdict.INCONCLUSIVE


# --- B-1: exact 2x2 seed/condition matrix (DA-M11C3b-exec-2) ----------------


def test_invalid_on_illegal_seed_value() -> None:
    # {0, 2} passes a naive count==2 check but seed 2 violates the frozen
    # run_idx {0,1} binding (ADR §6) -> matrix protocol violation -> invalid.
    report = score_c3b_verdict(
        _experiment(_treatment(0), _control(0), _treatment(2), _control(2))
    )
    assert report.verdict is Verdict.INVALID
    assert "illegal seed value" in report.reason
    assert report.seeds == ()  # never reached axis scoring


def test_invalid_on_duplicate_seed_condition() -> None:
    # Two flag-on runs for seed 0 would silently overwrite in a dict; the
    # matrix validator refuses the duplicate instead.
    report = score_c3b_verdict(
        _experiment(_treatment(0), _treatment(0), _control(0), _control(1))
    )
    assert report.verdict is Verdict.INVALID
    assert "duplicate" in report.reason


def test_invalid_on_incomplete_pair() -> None:
    # seed 1 has only flag-on (no flag-off) -> half pair -> invalid.
    report = score_c3b_verdict(_experiment(_treatment(0), _control(0), _treatment(1)))
    assert report.verdict is Verdict.INVALID
    assert "missing flag-off" in report.reason


def test_well_formed_single_seed_is_inconclusive_not_invalid() -> None:
    # The B-1 boundary: a well-formed but incomplete grid (only seed 0's
    # on/off pair) is a sample shortfall (re-capture seed 1), NOT a protocol
    # violation. Distinguishes {0,2} (invalid) from "seed 1 not captured yet".
    report = score_c3b_verdict(_experiment(_treatment(0), _control(0)))
    assert report.verdict is Verdict.INCONCLUSIVE
    assert report.verdict is not Verdict.INVALID


# --- bge-m3 exploratory: recorded, never gated (ADR §5.1) -------------------


def test_bge_m3_exploratory_recorded_but_not_gated() -> None:
    # Panel carries both primaries (passing) + a bge-m3 whose direction
    # *collapses*. The verdict must stay GO: bge-m3 is reported, not gated.
    panel = list(_good_panel())
    panel += _encoder_panel("BAAI/bge-m3", cross=(0.05, 0.05, 0.05), floor=0.10)
    report = score_c3b_verdict(
        _experiment(
            _treatment(0, panel=tuple(panel)),
            _control(0),
            _treatment(1, panel=tuple(panel)),
            _control(1),
        )
    )
    assert report.verdict is Verdict.GO, report.reason
    seed0 = next(s for s in report.seeds if s.seed == 0)
    bge = next(g for g in seed0.exploratory_gates if g.encoder_id == "BAAI/bge-m3")
    assert bge.direction_positive is False  # collapsed, but recorded only
