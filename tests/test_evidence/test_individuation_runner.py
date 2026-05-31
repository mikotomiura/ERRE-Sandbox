"""Runner orchestration coverage (M10-0 individuation PR-2).

Asserts scope coverage (per_individual / per_dyad / population, no run scope),
the three Layer 2 pins per individual, determinism with a fixed clock + stub
provider, and that injected language/reference + N>=2 same-base individuals
drive the burrows + centroid valid branches.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from erre_sandbox.evidence.eval_store import bootstrap_schema, connect_analysis_view
from erre_sandbox.evidence.individuation.layer1 import stub_embedding_provider
from erre_sandbox.evidence.individuation.policy import (
    RESERVED_POPULATION_ID,
    AggregationLevel,
    MetricStatus,
)
from erre_sandbox.evidence.individuation.runner import (
    IndividuationContext,
    compute_individuation,
)
from erre_sandbox.evidence.tier_a.burrows import BurrowsReference

_NOW = datetime(2026, 5, 26, tzinfo=UTC)
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


def _row(idx: int, agent: str, persona: str, utt: str, zone: str) -> dict[str, Any]:
    return {
        "id": f"{agent}-{idx}",
        "run_id": "run0",
        "dialog_id": "d0",
        "tick": idx,
        "turn_index": 0,
        "speaker_agent_id": agent,
        "speaker_persona_id": persona,
        "addressee_agent_id": "a_other",
        "addressee_persona_id": "other",
        "utterance": utt,
        "mode": "",
        "zone": zone,
        "reasoning": "",
        "epoch_phase": "autonomous",
        "individual_layer_enabled": False,
        "created_at": _NOW,
    }


def _make_run(tmp_path: Path) -> Path:
    """Two individuals sharing base 'kant' (so centroid is a real N>=2 dyad)."""
    rows = [
        _row(1, "a_kant_001", "kant", "the of and study", "study"),
        _row(2, "a_kant_001", "kant", "more text here please", "study"),
        _row(3, "a_kant_002", "kant", "different individual speaks now", "agora"),
        _row(4, "a_kant_002", "kant", "yet another utterance entirely", "garden"),
    ]
    db = tmp_path / "run.duckdb"
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


def _ctx(personas_dir: Path) -> IndividuationContext:
    return IndividuationContext(
        personas_dir=personas_dir,
        provider=stub_embedding_provider(),
        computed_at=_NOW,
    )


def _run(db: Path, ctx: IndividuationContext) -> list[Any]:
    view = connect_analysis_view(db)
    try:
        return compute_individuation(view, run_id="run0", ctx=ctx)
    finally:
        view.close()


def test_scope_coverage_and_no_run_scope(tmp_path: Path) -> None:
    db = _make_run(tmp_path)
    results = _run(db, _ctx(tmp_path))
    levels = {r.aggregation_level for r in results}
    assert AggregationLevel.PER_INDIVIDUAL in levels
    assert AggregationLevel.PER_DYAD in levels
    assert AggregationLevel.POPULATION in levels
    assert AggregationLevel.RUN not in levels


def test_cite_belief_three_pins_per_individual(tmp_path: Path) -> None:
    db = _make_run(tmp_path)
    results = _run(db, _ctx(tmp_path))
    pins = [r for r in results if r.metric_name.startswith("cite_belief_discipline.")]
    # 3 pins x 2 individuals
    assert len(pins) == 6
    assert all(r.status is MetricStatus.UNSUPPORTED for r in pins)


def test_centroid_valid_for_same_base_n2(tmp_path: Path) -> None:
    db = _make_run(tmp_path)
    results = _run(db, _ctx(tmp_path))
    centroids = [r for r in results if r.metric_name == "semantic_centroid_distance"]
    assert len(centroids) == 1  # one sorted pair within base 'kant'
    assert centroids[0].status is MetricStatus.VALID
    assert centroids[0].aggregation_level is AggregationLevel.PER_DYAD


def test_population_vendi_uses_reserved_id(tmp_path: Path) -> None:
    db = _make_run(tmp_path)
    results = _run(db, _ctx(tmp_path))
    vendi = [r for r in results if r.metric_name == "vendi_diversity"]
    assert len(vendi) == 1
    assert vendi[0].individual_id == RESERVED_POPULATION_ID
    assert vendi[0].base_persona_id == "kant"
    assert vendi[0].status is MetricStatus.VALID


def test_burrows_valid_with_injected_language_and_reference(tmp_path: Path) -> None:
    ref = BurrowsReference(
        language="en",
        function_words=("the", "of", "and"),
        background_mean=(0.05, 0.04, 0.03),
        background_std=(0.02, 0.02, 0.02),
        profile_freq=(0.06, 0.03, 0.02),
    )
    ctx = IndividuationContext(
        personas_dir=tmp_path,
        provider=stub_embedding_provider(),
        computed_at=_NOW,
        language_resolver=lambda _w: "en",
        burrows_reference_provider=lambda _p, _l: ref,
    )
    db = _make_run(tmp_path)
    results = _run(db, ctx)
    burrows = [r for r in results if r.metric_name == "burrows_base_retention"]
    assert burrows  # at least one
    assert any(r.status is MetricStatus.VALID for r in burrows)


def _make_rikyu_run(tmp_path: Path) -> Path:
    """One individual on base 'rikyu' speaking particle-rich classical ja.

    Drives the M11-C3a ja Burrows path end-to-end: the default resolver
    returns 'ja', the default reference provider loads the committed
    rikyu/ja reference, and the runner pre-tokenises with tokenise_ja.
    """
    rows = [
        _row(1, "a_rikyu_001", "rikyu", "茶の湯の道は心にありて", "chashitsu"),
        _row(2, "a_rikyu_001", "rikyu", "花は野にあるやうに生けよと", "chashitsu"),
    ]
    db = tmp_path / "rikyu_run.duckdb"
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


def test_burrows_ja_valid_via_runtime_tokenizer(tmp_path: Path) -> None:
    # M11-C3a: with base 'rikyu', the default ja resolver + the committed
    # rikyu/ja reference drive a valid Burrows delta through the shared
    # tokenise_ja adapter — no SudachiPy, no injected provider.
    db = _make_rikyu_run(tmp_path)
    results = _run(db, _ctx(tmp_path))
    burrows = [
        r
        for r in results
        if r.metric_name == "burrows_base_retention" and r.base_persona_id == "rikyu"
    ]
    assert burrows
    # A valid ja Burrows row with a finite, non-negative L1 delta proves the
    # tokenise_ja adapter produced particle matches against the reference
    # (not just a fold-to-NaN / unsupported short-circuit).
    valid = [r for r in burrows if r.status is MetricStatus.VALID]
    assert valid
    assert all(r.value is not None and r.value >= 0.0 for r in valid)


def test_determinism(tmp_path: Path) -> None:
    db = _make_run(tmp_path)
    a = _run(db, _ctx(tmp_path))
    b = _run(db, _ctx(tmp_path))
    assert [r.to_row() for r in a] == [r.to_row() for r in b]
