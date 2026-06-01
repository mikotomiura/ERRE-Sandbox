"""M11-C3b P-1a: same-base launcher + DuckDB stitching + elapsed coverage.

Verifies the preflight launcher seam **offline** (no Ollama / SGLang health
check, no real inference — MED-3): the roster builder, the ordinal-aware
initial state (byte-identical at ordinal 1), the registration loop against a
stub runtime, the loader stitching of three same-base individuals into
per_individual / per_dyad scopes, and the measured-elapsed plumbing
(CaptureResult + sidecar). The real same-base run is M11-C3b-exec (GPU).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import duckdb
import pytest

from erre_sandbox.cli.eval_run_golden import (
    _NATURAL_AGORA_POSITIONS,
    _NATURAL_AGORA_SEATS,
    CaptureResult,
    _initial_state_for_natural,
    _load_persona,
    _register_natural_roster,
    build_natural_roster,
)
from erre_sandbox.evidence.capture_sidecar import (
    SidecarV1,
    read_sidecar,
    write_sidecar_atomic,
)
from erre_sandbox.evidence.eval_store import bootstrap_schema, connect_analysis_view
from erre_sandbox.evidence.golden_baseline import DEFAULT_PERSONAS
from erre_sandbox.evidence.individuation.layer1 import stub_embedding_provider
from erre_sandbox.evidence.individuation.loader import load_individual_windows
from erre_sandbox.evidence.individuation.policy import AggregationLevel, MetricStatus
from erre_sandbox.evidence.individuation.runner import (
    IndividuationContext,
    _per_dyad_metrics,
)

if TYPE_CHECKING:
    from erre_sandbox.schemas import AgentState, PersonaSpec

_PERSONAS_DIR = Path("personas")


# ---------------------------------------------------------------------------
# build_natural_roster
# ---------------------------------------------------------------------------


def test_default_roster_is_one_per_persona() -> None:
    """No same_base_count -> historical one-per-persona roster (byte-identical)."""
    assert build_natural_roster("rikyu") == tuple((pid, 1) for pid in DEFAULT_PERSONAS)


def test_same_base_roster_enumerates_ordinals() -> None:
    assert build_natural_roster("rikyu", same_base_count=3) == (
        ("rikyu", 1),
        ("rikyu", 2),
        ("rikyu", 3),
    )


@pytest.mark.parametrize("bad", [0, -1])
def test_same_base_roster_rejects_non_positive(bad: int) -> None:
    with pytest.raises(ValueError, match="must be >= 1"):
        build_natural_roster("rikyu", same_base_count=bad)


def test_same_base_roster_rejects_more_than_seats() -> None:
    too_many = len(_NATURAL_AGORA_SEATS) + 1
    with pytest.raises(ValueError, match="distinct AGORA seats"):
        build_natural_roster("rikyu", same_base_count=too_many)


# ---------------------------------------------------------------------------
# _initial_state_for_natural (ordinal + seat)
# ---------------------------------------------------------------------------


def test_ordinal_one_is_byte_identical_legacy_id() -> None:
    """ordinal=1 + default seat reproduces the historical a_<persona>_001 shape."""
    spec = _load_persona(_PERSONAS_DIR, "rikyu")
    state = _initial_state_for_natural(spec)
    assert state.agent_id == "a_rikyu_001"
    seat = _NATURAL_AGORA_POSITIONS["rikyu"]
    assert (state.position.x, state.position.y, state.position.z) == seat


def test_ordinals_yield_distinct_ids_and_seats() -> None:
    spec = _load_persona(_PERSONAS_DIR, "rikyu")
    states = [
        _initial_state_for_natural(spec, ordinal=n, seat=_NATURAL_AGORA_SEATS[n - 1])
        for n in (1, 2, 3)
    ]
    ids = [s.agent_id for s in states]
    assert ids == ["a_rikyu_001", "a_rikyu_002", "a_rikyu_003"]
    seats = [(s.position.x, s.position.y, s.position.z) for s in states]
    assert len(set(seats)) == 3  # three non-overlapping AGORA seats
    assert all(s.persona_id == "rikyu" for s in states)


# ---------------------------------------------------------------------------
# _register_natural_roster (offline, stub runtime — no inference)
# ---------------------------------------------------------------------------


class _StubRuntime:
    """Records register_agent calls; no cognition stack, no inference."""

    def __init__(self) -> None:
        self.registered: list[tuple[str, str]] = []
        self.seats: dict[str, tuple[float, float, float]] = {}

    def register_agent(self, state: AgentState, persona: PersonaSpec) -> None:
        assert persona.persona_id == state.persona_id
        self.registered.append((state.agent_id, state.persona_id))
        self.seats[state.agent_id] = (
            state.position.x,
            state.position.y,
            state.position.z,
        )


def _persona_specs() -> dict[str, PersonaSpec]:
    return {pid: _load_persona(_PERSONAS_DIR, pid) for pid in DEFAULT_PERSONAS}


def test_register_same_base_three_distinct_individuals() -> None:
    runtime = _StubRuntime()
    roster = build_natural_roster("rikyu", same_base_count=3)
    _register_natural_roster(runtime, roster, _persona_specs(), same_base=True)  # type: ignore[arg-type]

    assert runtime.registered == [
        ("a_rikyu_001", "rikyu"),
        ("a_rikyu_002", "rikyu"),
        ("a_rikyu_003", "rikyu"),
    ]
    # individual_id distinct + seats distinct (proximity pairs can auto-fire).
    assert len({aid for aid, _ in runtime.registered}) == 3
    assert len(set(runtime.seats.values())) == 3


def test_register_default_roster_byte_identical() -> None:
    """Default roster registers a_<pid>_001 per persona at the persona seat."""
    runtime = _StubRuntime()
    roster = build_natural_roster("rikyu")  # same_base_count=None
    _register_natural_roster(runtime, roster, _persona_specs(), same_base=False)  # type: ignore[arg-type]

    assert runtime.registered == [
        ("a_kant_001", "kant"),
        ("a_nietzsche_001", "nietzsche"),
        ("a_rikyu_001", "rikyu"),
    ]
    for pid in DEFAULT_PERSONAS:
        assert runtime.seats[f"a_{pid}_001"] == _NATURAL_AGORA_POSITIONS[pid]


# ---------------------------------------------------------------------------
# DuckDB individual_id row stitching (loader -> per_individual / per_dyad)
# ---------------------------------------------------------------------------

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


def _dialog_row(agent_id: str, tick: int, utterance: str) -> dict[str, Any]:
    return {
        "id": f"{agent_id}:{tick}",
        "run_id": "rikyu_natural_run0",
        "dialog_id": "d0",
        "tick": tick,
        "turn_index": 0,
        "speaker_agent_id": agent_id,
        "speaker_persona_id": "rikyu",
        "addressee_agent_id": "a_rikyu_002",
        "addressee_persona_id": "rikyu",
        "utterance": utterance,
        "mode": "",
        "zone": "agora",
        "reasoning": "",
        "epoch_phase": "autonomous",
        "individual_layer_enabled": False,
        "created_at": datetime.now(UTC),
    }


def _make_same_base_db(tmp_path: Path) -> Path:
    db = tmp_path / "same_base.duckdb"
    con = duckdb.connect(str(db), read_only=False)
    bootstrap_schema(con)
    cols = ", ".join(_DIALOG_COLS)
    ph = ", ".join("?" for _ in _DIALOG_COLS)
    rows = [
        _dialog_row("a_rikyu_001", 1, "the kettle hums quietly"),
        _dialog_row("a_rikyu_001", 2, "I attend to the bowl"),
        _dialog_row("a_rikyu_002", 1, "the guest arrives at dusk"),
        _dialog_row("a_rikyu_002", 2, "we share a measured silence"),
        _dialog_row("a_rikyu_003", 1, "ash settles in the brazier"),
        _dialog_row("a_rikyu_003", 2, "a single flower in the alcove"),
    ]
    for r in rows:
        con.execute(
            f"INSERT INTO raw_dialog.dialog ({cols}) VALUES ({ph})",  # noqa: S608  # static column list
            [r[c] for c in _DIALOG_COLS],
        )
    con.execute("CHECKPOINT")
    con.close()
    return db


def test_loader_stitches_three_same_base_individuals(tmp_path: Path) -> None:
    db = _make_same_base_db(tmp_path)
    with connect_analysis_view(db) as view:
        loaded = list(load_individual_windows(view, run_id="rikyu_natural_run0"))

    assert len(loaded) == 1
    run = loaded[0]
    # per_individual: three distinct individual_ids, all base rikyu.
    ids = sorted(w.individual_id for w in run.windows)
    assert ids == ["a_rikyu_001", "a_rikyu_002", "a_rikyu_003"]
    assert all(w.base_persona_id == "rikyu" for w in run.windows)
    # base_groups: one same-base group with the three sorted members.
    assert run.base_groups == (
        ("rikyu", ("a_rikyu_001", "a_rikyu_002", "a_rikyu_003")),
    )


def test_loader_feeds_three_dyads_to_per_dyad(tmp_path: Path) -> None:
    """C(3,2)=3 dyads -> three valid centroid rows (stub encoder, offline)."""
    db = _make_same_base_db(tmp_path)
    ctx = IndividuationContext(
        personas_dir=_PERSONAS_DIR,
        provider=stub_embedding_provider(),
        computed_at=datetime.now(UTC),
    )
    with connect_analysis_view(db) as view:
        loaded = next(iter(load_individual_windows(view, run_id="rikyu_natural_run0")))
    by_id = {w.individual_id: w for w in loaded.windows}
    base, members = loaded.base_groups[0]

    # no trace windows here → SWM Jaccard takes the stub fallback; this test only
    # asserts the centroid dyad rows (M10-A S3 added the trace_windows parameter).
    rows = _per_dyad_metrics(base, members, by_id, ctx, {})
    centroid_rows = [r for r in rows if r.metric_name == "semantic_centroid_distance"]
    assert len(centroid_rows) == 3  # C(3,2)
    assert all(r.aggregation_level is AggregationLevel.PER_DYAD for r in centroid_rows)
    assert all(r.status is MetricStatus.VALID for r in centroid_rows)
    # distinct dyad ids
    assert len({r.individual_id for r in centroid_rows}) == 3


# ---------------------------------------------------------------------------
# elapsed plumbing (CaptureResult + sidecar)
# ---------------------------------------------------------------------------


def test_capture_result_elapsed_defaults_none() -> None:
    result = CaptureResult(
        run_id="r", output_path=Path("x.duckdb"), total_rows=0, focal_rows=0
    )
    assert result.elapsed_seconds is None


def test_sidecar_round_trips_elapsed(tmp_path: Path) -> None:
    path = tmp_path / "cell.duckdb.sidecar.json"
    payload = SidecarV1(
        status="complete",
        stop_reason="complete",
        focal_target=24,
        focal_observed=24,
        total_rows=48,
        wall_timeout_min=120.0,
        drain_completed=True,
        runtime_drain_timeout=False,
        git_sha="abc1234",
        captured_at="2026-05-28T00:00:00Z",
        persona="rikyu",
        condition="natural",
        run_idx=0,
        duckdb_path=str(tmp_path / "cell.duckdb"),
        elapsed_seconds=312.5,
    )
    write_sidecar_atomic(path, payload)
    loaded = read_sidecar(path)
    assert loaded.elapsed_seconds == 312.5


def test_sidecar_without_elapsed_validates() -> None:
    """Older sidecars (no elapsed_seconds) still validate -> default None."""
    payload = SidecarV1(
        status="complete",
        stop_reason="complete",
        focal_target=1,
        focal_observed=1,
        total_rows=1,
        wall_timeout_min=120.0,
        drain_completed=True,
        runtime_drain_timeout=False,
        git_sha="abc1234",
        captured_at="2026-05-28T00:00:00Z",
        persona="rikyu",
        condition="natural",
        run_idx=0,
        duckdb_path="x.duckdb",
    )
    assert payload.elapsed_seconds is None
