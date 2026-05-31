"""Cross-cutting integration for M10-0 individuation PR-3.

End-to-end: seed a synthetic ``raw_dialog.dialog`` over several runs, run
``compute_individuation`` per run (stub embedding provider — no MPNet), build
per-run reports, and correlate across runs. Covers three things the unit tests
cannot:

* **computed path** — with en language + a synthetic Burrows reference injected
  and the real ``personas/`` dir (so ``zone`` resolves its preferred zones),
  burrows + zone are both valid and non-constant across >= 3 observation units,
  so the matrix is actually computed (user review #1/#3).
* **real-golden shape** — the default (ja) resolver leaves only ``zone`` valid,
  so the report is ``insufficient`` — the *normal* outcome, asserted to not be
  a failure.
* **recompute idempotency** — compute -> ``write_individuation_rows`` -> recompute
  -> rewrite leaves no duplicate natural keys (full-run replace), and
  ``correlate_individuation`` is deterministic across repeats.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from erre_sandbox.evidence.eval_store import (
    bootstrap_schema,
    connect_analysis_view,
    write_individuation_rows,
)
from erre_sandbox.evidence.individuation.correlation import (
    CorrelationStatus,
    correlate_individuation,
)
from erre_sandbox.evidence.individuation.layer1 import stub_embedding_provider
from erre_sandbox.evidence.individuation.report import build_report
from erre_sandbox.evidence.individuation.runner import (
    IndividuationContext,
    compute_individuation,
)
from erre_sandbox.evidence.tier_a.burrows import BurrowsReference

_NOW = datetime(2026, 5, 26, tzinfo=UTC)
_PERSONAS_DIR = Path(__file__).resolve().parents[2] / "personas"

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

# Burrows texts with well-separated deltas (empirically ~2.7 / 14.5 / 38.3 / 44.5
# against the synthetic en reference) so the burrows column is non-constant.
_BURROWS_TEXTS = (
    "the of and " + " ".join(["alpha"] * 20),
    "the the of and " + " ".join(["beta"] * 6),
    "the the the the the of and study",
    "the of and the of and the of and",
)
# Zone triples giving fractions 1.0 / 0.333 / 0.0 / 0.667 (kant preferred =
# {study, peripatos, agora}) so the zone column is non-constant.
_ZONE_TRIPLES = (
    ("study", "peripatos", "agora"),
    ("study", "garden", "garden"),
    ("garden", "chashitsu", "garden"),
    ("study", "agora", "garden"),
)


def _row(
    run_id: str, agent: str, idx: int, utterance: str, zone: str
) -> dict[str, Any]:
    return {
        "id": f"{run_id}-{agent}-{idx}",
        "run_id": run_id,
        "dialog_id": "d0",
        "tick": idx,
        "turn_index": 0,
        "speaker_agent_id": agent,
        "speaker_persona_id": "kant",
        "addressee_agent_id": "a_other",
        "addressee_persona_id": "other",
        "utterance": utterance,
        "mode": "",
        "zone": zone,
        "reasoning": "",
        "epoch_phase": "autonomous",
        "individual_layer_enabled": False,
        "created_at": _NOW,
    }


def _seed_db(tmp_path: Path, *, n_runs: int, utterance_lang: str) -> Path:
    """One individual (base 'kant') per run, 3 rows each (burrows text + zones).

    ``utterance_lang='en'`` uses the burrows texts; ``'ja'`` uses Japanese so
    burrows short-circuits unsupported (real-golden shape).
    """
    rows: list[dict[str, Any]] = []
    for i in range(n_runs):
        run_id = f"run{i}"
        agent = f"a_kant_{i}"
        if utterance_lang == "en":
            head = _BURROWS_TEXTS[i % len(_BURROWS_TEXTS)]
        else:
            head = "これは日本語の発話である"
        zones = _ZONE_TRIPLES[i % len(_ZONE_TRIPLES)]
        rows.append(_row(run_id, agent, 0, head, zones[0]))
        rows.append(_row(run_id, agent, 1, "", zones[1]))
        rows.append(_row(run_id, agent, 2, "", zones[2]))

    db = tmp_path / "runs.duckdb"
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


def _en_ctx() -> IndividuationContext:
    ref = BurrowsReference(
        language="en",
        function_words=("the", "of", "and"),
        background_mean=(0.05, 0.04, 0.03),
        background_std=(0.02, 0.02, 0.02),
        profile_freq=(0.06, 0.03, 0.02),
    )
    return IndividuationContext(
        personas_dir=_PERSONAS_DIR,
        provider=stub_embedding_provider(),
        computed_at=_NOW,
        language_resolver=lambda _w: "en",
        burrows_reference_provider=lambda _p, _l: ref,
    )


def _ja_ctx() -> IndividuationContext:
    # Default language resolver -> 'ja' -> burrows unsupported (real-golden shape).
    return IndividuationContext(
        personas_dir=_PERSONAS_DIR,
        provider=stub_embedding_provider(),
        computed_at=_NOW,
    )


def _reports(db: Path, ctx: IndividuationContext, n_runs: int) -> list[Any]:
    reports: list[Any] = []
    view = connect_analysis_view(db)
    try:
        for i in range(n_runs):
            run_id = f"run{i}"
            results = compute_individuation(view, run_id=run_id, ctx=ctx)
            reports.append(build_report(run_id, results, computed_at=_NOW))
    finally:
        view.close()
    return reports


def test_multi_run_compute_then_correlate_is_computed(tmp_path: Path) -> None:
    db = _seed_db(tmp_path, n_runs=4, utterance_lang="en")
    reports = _reports(db, _en_ctx(), 4)
    report = correlate_individuation(reports, computed_at=_NOW)

    assert report.correlation_status is CorrelationStatus.COMPUTED
    assert report.n_observation_units == 4
    # burrows + zone are the per_individual valid pair.
    assert report.metrics_in_matrix == (
        "burrows_base_retention",
        "zone_behavior_consistency",
    )
    assert len(report.pairs) == 1
    assert report.pairs[0].n_observations == 4
    # vendi (population) is present-and-valid but the wrong observation unit.
    excluded = {e.metric_name: e.reason for e in report.excluded_metrics}
    assert excluded.get("vendi_diversity") == "wrong_observation_unit"


def test_real_golden_shape_is_insufficient_not_failure(tmp_path: Path) -> None:
    # ja utterances -> burrows unsupported; only zone valid -> 1 metric column.
    db = _seed_db(tmp_path, n_runs=4, utterance_lang="ja")
    reports = _reports(db, _ja_ctx(), 4)
    report = correlate_individuation(reports, computed_at=_NOW)

    # Insufficient is the NORMAL outcome here, asserted explicitly (not an error).
    assert report.correlation_status is CorrelationStatus.INSUFFICIENT
    assert report.pairs == ()
    assert report.insufficient_reason is not None
    # zone is the lone surviving valid metric; burrows had no valid cell.
    excluded = {e.metric_name: e.reason for e in report.excluded_metrics}
    assert excluded.get("burrows_base_retention") == "no_valid_values"


def test_recompute_write_idempotent_full_run_replace(tmp_path: Path) -> None:
    db = _seed_db(tmp_path, n_runs=4, utterance_lang="en")
    ctx = _en_ctx()

    # Compute twice (deterministic) against the read-only view, collecting the
    # full flat result list each time.
    first: list[Any] = []
    second: list[Any] = []
    view = connect_analysis_view(db)
    try:
        for i in range(4):
            first.extend(compute_individuation(view, run_id=f"run{i}", ctx=ctx))
        for i in range(4):
            second.extend(compute_individuation(view, run_id=f"run{i}", ctx=ctx))
    finally:
        view.close()
    assert [r.to_row() for r in first] == [r.to_row() for r in second]

    # Write, then re-write the recomputed rows: full-run replace must keep the
    # row count stable (no duplicate natural keys).
    con = duckdb.connect(str(db), read_only=False)
    try:
        n1 = write_individuation_rows(con, first)
        n2 = write_individuation_rows(con, second)
        assert n1 == n2 == len(first)
        (total,) = con.execute("SELECT count(*) FROM metrics.individuation").fetchone()
        (distinct,) = con.execute(
            "SELECT count(*) FROM (SELECT DISTINCT run_id, individual_id,"
            " metric_name, channel, aggregation_level, tick, source_filter_hash"
            " FROM metrics.individuation)"
        ).fetchone()
    finally:
        con.close()
    assert total == len(first)
    assert distinct == total  # every row has a unique natural key


def test_correlate_is_deterministic(tmp_path: Path) -> None:
    db = _seed_db(tmp_path, n_runs=4, utterance_lang="en")
    reports = _reports(db, _en_ctx(), 4)
    a = correlate_individuation(reports, computed_at=_NOW)
    b = correlate_individuation(reports, computed_at=_NOW)
    assert a.to_sidecar_dict() == b.to_sidecar_dict()
