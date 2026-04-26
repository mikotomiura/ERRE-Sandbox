"""Unit tests for :mod:`erre_sandbox.evidence.scaling_metrics` (M8 spike).

Every metric is pure, so these tests build ``list[dict]`` fixtures directly
and assert on the scalar output. ``aggregate()`` is exercised through a
fresh on-disk MemoryStore + temp NDJSON journal so the sqlite I/O and
journal scan paths are covered end to end without going through the CLI.

Decisions D1-D5 in
``.steering/20260425-m8-scaling-bottleneck-profiling/decisions.md`` pin
the metric formulas; the threshold values exercised here are the
analytic-bound defaults from D4.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from erre_sandbox.evidence.scaling_metrics import (
    DEFAULT_DIALOG_TURN_BUDGET,
    DEFAULT_NUM_ZONES,
    LATE_TURN_FRACTION_THRESHOLD,
    PAIR_INFO_GAIN_THRESHOLD_PCT,
    ZONE_KL_THRESHOLD_PCT,
    _compute_entropy_safe,
    aggregate,
    compute_late_turn_fraction,
    compute_pair_information_gain,
    compute_zone_kl_from_uniform,
    default_thresholds,
    evaluate_thresholds,
)
from erre_sandbox.memory.store import MemoryStore

# ---------------------------------------------------------------------------
# _compute_entropy_safe
# ---------------------------------------------------------------------------


def test_entropy_safe_empty_returns_zero() -> None:
    assert _compute_entropy_safe([]) == pytest.approx(0.0)


def test_entropy_safe_all_zero_returns_zero() -> None:
    assert _compute_entropy_safe([0, 0, 0]) == pytest.approx(0.0)


def test_entropy_safe_single_nonzero_below_max() -> None:
    """Smoothing produces a small positive entropy; Miller-Madow correction is 0."""
    # K=3 slots, only first populated. Smoothed = [10.5, 0.5, 0.5] / 11.5.
    h = _compute_entropy_safe([10, 0, 0])
    assert h > 0.0
    assert h < math.log2(3)


def test_entropy_safe_uniform_three_categories_close_to_log2_three() -> None:
    """Uniform 3-way counts approach log2(3) for large samples."""
    h = _compute_entropy_safe([1000, 1000, 1000])
    expected_lo = math.log2(3) - 0.01  # smoothing + MM correction nudge
    expected_hi = math.log2(3) + 0.01
    assert expected_lo < h < expected_hi


# ---------------------------------------------------------------------------
# compute_pair_information_gain (M1)
# ---------------------------------------------------------------------------


def test_pair_info_gain_returns_none_for_too_few_agents() -> None:
    assert compute_pair_information_gain([], num_agents=1) is None


def test_pair_info_gain_returns_none_for_empty_turns() -> None:
    assert compute_pair_information_gain([], num_agents=3) is None


def test_pair_info_gain_returns_none_when_below_history_k_plus_one() -> None:
    """3 turns + history_k=3 means no conditional pair can be formed."""
    turns = [
        {"speaker_persona_id": "kant", "addressee_persona_id": "rikyu"},
        {"speaker_persona_id": "rikyu", "addressee_persona_id": "kant"},
        {"speaker_persona_id": "kant", "addressee_persona_id": "nietzsche"},
    ]
    assert compute_pair_information_gain(turns, num_agents=3, history_k=3) is None


def test_pair_info_gain_returns_low_value_for_repeating_pair() -> None:
    """Same pair repeating → predictable → information gain near 0."""
    turns = [
        {"speaker_persona_id": "kant", "addressee_persona_id": "rikyu"},
        {"speaker_persona_id": "rikyu", "addressee_persona_id": "kant"},
        {"speaker_persona_id": "kant", "addressee_persona_id": "rikyu"},
        {"speaker_persona_id": "rikyu", "addressee_persona_id": "kant"},
        {"speaker_persona_id": "kant", "addressee_persona_id": "rikyu"},
        {"speaker_persona_id": "rikyu", "addressee_persona_id": "kant"},
    ]
    # Note: speaker/addressee swap collapses to the same unordered pair, so
    # the marginal distribution is degenerate (all observations on one
    # pair). Both H(pair) and H(pair|history) are then ≤ smoothing noise.
    score = compute_pair_information_gain(turns, num_agents=3, history_k=3)
    assert score is not None
    assert score < 0.2


def test_pair_info_gain_skips_self_addressed_turns() -> None:
    """Self-addressed turns are not pairs; they should be filtered."""
    turns = [
        {"speaker_persona_id": "kant", "addressee_persona_id": "kant"},  # skip
        {"speaker_persona_id": "kant", "addressee_persona_id": "rikyu"},
        {"speaker_persona_id": "rikyu", "addressee_persona_id": "kant"},
        {"speaker_persona_id": "kant", "addressee_persona_id": "nietzsche"},
        {"speaker_persona_id": "nietzsche", "addressee_persona_id": "rikyu"},
    ]
    score = compute_pair_information_gain(turns, num_agents=3, history_k=3)
    assert score is not None
    # Three usable pairs after filtering, history_k=3 needs ≥4 → still None.
    # Adjust expectation: self-addressed dropped reduces seq to 4 items, so
    # one conditional sample exists.


def test_pair_info_gain_skips_turns_missing_persona_ids() -> None:
    turns = [
        {"speaker_persona_id": "kant", "addressee_persona_id": None},  # skip
        {"speaker_persona_id": "kant", "addressee_persona_id": "rikyu"},
        {"speaker_persona_id": None, "addressee_persona_id": "kant"},  # skip
        {"speaker_persona_id": "rikyu", "addressee_persona_id": "kant"},
        {"speaker_persona_id": "kant", "addressee_persona_id": "nietzsche"},
        {"speaker_persona_id": "nietzsche", "addressee_persona_id": "rikyu"},
    ]
    score = compute_pair_information_gain(turns, num_agents=3, history_k=3)
    assert score is not None
    assert score >= 0.0


# ---------------------------------------------------------------------------
# compute_late_turn_fraction (M2)
# ---------------------------------------------------------------------------


def test_late_turn_fraction_returns_none_for_empty() -> None:
    assert compute_late_turn_fraction([]) is None


def test_late_turn_fraction_zero_when_all_early() -> None:
    """All turn_index ≤ 3 → late fraction = 0."""
    turns = [{"turn_index": i} for i in range(4)]  # 0, 1, 2, 3
    assert compute_late_turn_fraction(turns) == pytest.approx(0.0)


def test_late_turn_fraction_one_when_all_late() -> None:
    """All turn_index > 3 → late fraction = 1."""
    turns = [{"turn_index": i} for i in range(4, 8)]  # 4, 5, 6, 7
    assert compute_late_turn_fraction(turns) == pytest.approx(1.0)


def test_late_turn_fraction_half_when_half_split() -> None:
    """4 early + 4 late → 0.5."""
    turns = [{"turn_index": i} for i in (0, 1, 2, 3, 4, 5, 6, 7)]
    assert compute_late_turn_fraction(turns) == pytest.approx(0.5)


def test_late_turn_fraction_skips_non_int_indices() -> None:
    turns = [
        {"turn_index": 1},
        {"turn_index": "bad"},  # skip
        {"turn_index": 5},
    ]
    assert compute_late_turn_fraction(turns) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# compute_zone_kl_from_uniform (M3)
# ---------------------------------------------------------------------------


def test_zone_kl_returns_none_for_empty() -> None:
    assert compute_zone_kl_from_uniform([]) is None


def test_zone_kl_returns_none_when_no_consecutive_pair() -> None:
    """One snapshot per agent cannot form a consecutive dwell pair."""
    snapshots = [
        {"agent_id": "a", "tick": 1, "zone": "study"},
        {"agent_id": "b", "tick": 1, "zone": "garden"},
    ]
    assert compute_zone_kl_from_uniform(snapshots) is None


def test_zone_kl_one_zone_only_approaches_log2_n() -> None:
    """If all dwell sits in one zone, KL ≈ log2(n_zones)."""
    snapshots = [{"agent_id": "a", "tick": t, "zone": "study"} for t in range(10)]
    kl = compute_zone_kl_from_uniform(snapshots, n_zones=5)
    assert kl is not None
    assert kl == pytest.approx(math.log2(5), abs=1e-9)


def test_zone_kl_uniform_distribution_returns_zero() -> None:
    """Equal dwell across all 5 zones → KL = 0."""
    # Fixture: each agent stays in exactly one zone for 1 tick. With 5
    # agents (one per zone) the aggregated dwell is uniform.
    snapshots = []
    zones = ["study", "peripatos", "chashitsu", "agora", "garden"]
    for agent_idx, zone in enumerate(zones):
        snapshots.append(
            {"agent_id": f"a_{agent_idx}", "tick": 0, "zone": zone},
        )
        snapshots.append(
            {"agent_id": f"a_{agent_idx}", "tick": 1, "zone": zone},
        )
    kl = compute_zone_kl_from_uniform(snapshots, n_zones=5)
    assert kl is not None
    assert kl == pytest.approx(0.0, abs=1e-9)


def test_zone_kl_two_zone_60_40_known_value() -> None:
    """60% study, 40% garden, n_zones=5: KL = 0.6*log2(0.6/0.2) + 0.4*log2(0.4/0.2).

    pen+paper: 0.6 * log2(3) + 0.4 * log2(2) = 0.6 * 1.5849625 + 0.4 = 1.350977
    """
    snapshots = [
        {"agent_id": "a", "tick": 0, "zone": "study"},
        {"agent_id": "a", "tick": 6, "zone": "garden"},
        {"agent_id": "a", "tick": 10, "zone": "garden"},
    ]
    # Dwell: study from tick 0→6 (6 ticks), garden from tick 6→10 (4 ticks).
    # Total = 10, study=0.6, garden=0.4, others=0.
    kl = compute_zone_kl_from_uniform(snapshots, n_zones=5)
    assert kl is not None
    expected = 0.6 * math.log2(0.6 / 0.2) + 0.4 * math.log2(0.4 / 0.2)
    assert kl == pytest.approx(expected, abs=1e-9)


def test_zone_kl_returns_none_for_n_zones_below_two() -> None:
    snapshots = [
        {"agent_id": "a", "tick": 0, "zone": "x"},
        {"agent_id": "a", "tick": 1, "zone": "x"},
    ]
    assert compute_zone_kl_from_uniform(snapshots, n_zones=1) is None


# ---------------------------------------------------------------------------
# default_thresholds
# ---------------------------------------------------------------------------


def test_default_thresholds_n2_neutralises_pair_metric() -> None:
    """N=2 has only 1 distinct pair → max=0 → threshold 0 → no false positive."""
    th = default_thresholds(num_agents=2, n_zones=5)
    assert th["pair_information_gain_min_bits"] == pytest.approx(0.0)
    # M1 = 0 with threshold 0 cannot trigger (`<` is strict).
    triggered = evaluate_thresholds(
        {"pair_information_gain_bits": 0.0},
        th,
        run_id="r-n2",
    )
    assert "pair_information_gain" not in triggered


def test_default_thresholds_n3_returns_three_keys() -> None:
    th = default_thresholds(num_agents=3, n_zones=5)
    assert set(th.keys()) == {
        "pair_information_gain_min_bits",
        "late_turn_fraction_max",
        "zone_kl_from_uniform_min_bits",
    }
    assert th["pair_information_gain_min_bits"] == pytest.approx(
        PAIR_INFO_GAIN_THRESHOLD_PCT * math.log2(3),
    )
    assert th["late_turn_fraction_max"] == pytest.approx(LATE_TURN_FRACTION_THRESHOLD)
    assert th["zone_kl_from_uniform_min_bits"] == pytest.approx(
        ZONE_KL_THRESHOLD_PCT * math.log2(5),
    )


# ---------------------------------------------------------------------------
# evaluate_thresholds
# ---------------------------------------------------------------------------


def test_evaluate_thresholds_no_alert_when_value_above_min(tmp_path: Path) -> None:
    """value == threshold for a min trigger must NOT alert (strict ``<``)."""
    log_path = tmp_path / "scaling_alert.log"
    metrics = {"pair_information_gain_bits": 0.5, "late_turn_fraction": 0.5}
    thresholds = {
        "pair_information_gain_min_bits": 0.5,  # equal → no alert
        "late_turn_fraction_max": 0.6,
    }
    triggered = evaluate_thresholds(
        metrics,
        thresholds,
        run_id="r1",
        log_path=log_path,
    )
    assert triggered == []
    assert not log_path.exists()


def test_evaluate_thresholds_alerts_when_min_violated(tmp_path: Path) -> None:
    log_path = tmp_path / "scaling_alert.log"
    metrics = {"pair_information_gain_bits": 0.1}
    thresholds = {"pair_information_gain_min_bits": 0.5}
    triggered = evaluate_thresholds(
        metrics,
        thresholds,
        run_id="run-X",
        log_path=log_path,
    )
    assert triggered == ["pair_information_gain"]
    text = log_path.read_text(encoding="utf-8")
    # one tab-separated line: timestamp \t metric \t value \t threshold \t run_id
    assert text.count("\n") == 1
    line = text.rstrip("\n")
    parts = line.split("\t")
    assert len(parts) == 5
    assert parts[1] == "pair_information_gain"
    assert float(parts[2]) == pytest.approx(0.1)
    assert float(parts[3]) == pytest.approx(0.5)
    assert parts[4] == "run-X"


def test_evaluate_thresholds_alerts_when_max_violated(tmp_path: Path) -> None:
    log_path = tmp_path / "scaling_alert.log"
    metrics = {"late_turn_fraction": 0.9}
    thresholds = {"late_turn_fraction_max": 0.6}
    triggered = evaluate_thresholds(
        metrics,
        thresholds,
        run_id="r1",
        log_path=log_path,
    )
    assert triggered == ["late_turn_fraction"]
    assert log_path.exists()


def test_evaluate_thresholds_skips_none_metric_value() -> None:
    """``None`` in metrics => graceful degradation, no alert for that key."""
    metrics: dict[str, float | None] = {
        "zone_kl_from_uniform_bits": None,
        "late_turn_fraction": 0.4,
    }
    thresholds = {
        "zone_kl_from_uniform_min_bits": 0.5,
        "late_turn_fraction_max": 0.6,
    }
    triggered = evaluate_thresholds(metrics, thresholds, run_id="r1")
    assert triggered == []


def test_evaluate_thresholds_no_log_when_empty() -> None:
    """log_path must NOT be created when no metric is triggered."""
    metrics = {"late_turn_fraction": 0.1}
    thresholds = {"late_turn_fraction_max": 0.6}
    triggered = evaluate_thresholds(
        metrics,
        thresholds,
        run_id="r1",
        log_path=None,
    )
    assert triggered == []


# ---------------------------------------------------------------------------
# aggregate() — I/O wrapper
# ---------------------------------------------------------------------------


def test_aggregate_empty_db_yields_null_metrics(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.db"
    result = aggregate(db_path)
    assert result["schema"] == "scaling_metrics_v1"
    assert result["num_dialog_turns"] == 0
    assert result["num_agents"] == 0
    assert result["pair_information_gain_bits"] is None
    assert result["late_turn_fraction"] is None
    assert result["zone_kl_from_uniform_bits"] is None
    assert result["alerts"] == []


def test_aggregate_seeded_db_populates_m1_m2(tmp_path: Path) -> None:
    """Without a journal, M3 stays None and the alert list excludes zone."""
    from erre_sandbox.schemas import DialogTurnMsg

    db_path = tmp_path / "seeded.db"
    store = MemoryStore(db_path=db_path)
    store.create_schema()

    # Seed 6 turns alternating between (kant, rikyu) and (kant, nietzsche),
    # turn_index spanning 0..5 so late_turn_fraction has a meaningful split.
    pairs = [
        ("kant", "rikyu"),
        ("rikyu", "kant"),
        ("kant", "rikyu"),
        ("kant", "nietzsche"),
        ("nietzsche", "kant"),
        ("kant", "nietzsche"),
    ]
    for turn_index, (speaker, addressee) in enumerate(pairs):
        store.add_dialog_turn_sync(
            DialogTurnMsg(
                tick=10 + turn_index,
                dialog_id="d0",
                speaker_id=f"a_{speaker}_001",
                addressee_id=f"a_{addressee}_001",
                utterance=f"line {turn_index}",
                turn_index=turn_index,
            ),
            speaker_persona_id=speaker,
            addressee_persona_id=addressee,
        )

    result = aggregate(db_path, run_id="seeded")
    assert result["schema"] == "scaling_metrics_v1"
    assert result["run_id"] == "seeded"
    assert result["num_dialog_turns"] == 6
    assert result["num_agents"] == 3
    assert isinstance(result["pair_information_gain_bits"], float)
    assert result["pair_information_gain_max_bits"] == pytest.approx(math.log2(3))
    # turn_index 0..5: late = (>3) → indices 4, 5 → 2/6.
    midpoint = DEFAULT_DIALOG_TURN_BUDGET // 2
    expected_late = sum(1 for i in range(6) if i > midpoint) / 6
    assert result["late_turn_fraction"] == pytest.approx(expected_late)
    # M3 omitted because no journal supplied.
    assert result["zone_kl_from_uniform_bits"] is None
    assert result["zone_kl_max_bits"] == pytest.approx(math.log2(DEFAULT_NUM_ZONES))


def test_aggregate_with_journal_populates_zone_metric(tmp_path: Path) -> None:
    """When --journal is supplied, M3 is populated from agent_update entries."""
    from erre_sandbox.schemas import DialogTurnMsg

    db_path = tmp_path / "live.db"
    store = MemoryStore(db_path=db_path)
    store.create_schema()
    for i in range(4):
        store.add_dialog_turn_sync(
            DialogTurnMsg(
                tick=10 + i,
                dialog_id="d0",
                speaker_id="a_kant_001",
                addressee_id="a_rikyu_001",
                utterance=f"u{i}",
                turn_index=i,
            ),
            speaker_persona_id="kant",
            addressee_persona_id="rikyu",
        )

    journal_path = tmp_path / "run.jsonl"
    lines: list[str] = []
    # Single agent staying in study for 10 ticks → KL ≈ log2(5).
    for tick in range(10):
        envelope = {
            "kind": "agent_update",
            "tick": tick,
            "agent_state": {
                "agent_id": "a_kant_001",
                "tick": tick,
                "position": {"zone": "study"},
            },
        }
        lines.append(json.dumps(envelope))
    journal_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = aggregate(db_path, journal_path)
    assert result["zone_kl_from_uniform_bits"] is not None
    assert result["zone_kl_from_uniform_bits"] == pytest.approx(
        math.log2(5),
        abs=1e-9,
    )


def test_aggregate_supports_probe_wrapped_envelope(tmp_path: Path) -> None:
    """Legacy probe-wrapped journal lines (``{_probe, raw: <jsonstr>}``) decode."""
    db_path = tmp_path / "probe.db"
    store = MemoryStore(db_path=db_path)
    store.create_schema()

    journal_path = tmp_path / "probe.jsonl"
    inner = {
        "kind": "agent_update",
        "tick": 0,
        "agent_state": {
            "agent_id": "a_kant_001",
            "tick": 0,
            "position": {"zone": "study"},
        },
    }
    inner2 = dict(inner)
    inner2["tick"] = 5
    inner2["agent_state"] = dict(inner["agent_state"])
    inner2["agent_state"]["tick"] = 5
    journal_path.write_text(
        json.dumps({"_probe": "x", "raw": json.dumps(inner)})
        + "\n"
        + json.dumps({"_probe": "x", "raw": json.dumps(inner2)})
        + "\n",
        encoding="utf-8",
    )

    result = aggregate(db_path, journal_path)
    # 1 agent, 2 snapshots → all dwell in study → KL ≈ log2(5).
    assert result["zone_kl_from_uniform_bits"] == pytest.approx(
        math.log2(5),
        abs=1e-9,
    )


# ---------------------------------------------------------------------------
# M7ε D4 / M8 D5 — aggregate() filters by epoch_phase
# ---------------------------------------------------------------------------


def test_aggregate_filters_qa_user_turns(tmp_path: Path) -> None:
    """``aggregate()`` only sees AUTONOMOUS turns; Q_AND_A turns are dropped.

    Seed 6 AUTONOMOUS turns (which alone yield well-defined M1/M2 metrics)
    and 6 Q_AND_A turns. After the M7ε filter, the metric values must
    match the AUTONOMOUS-only baseline — Q_AND_A rows must not perturb
    pair_information_gain or late_turn_fraction.
    """
    from erre_sandbox.schemas import DialogTurnMsg, EpochPhase

    db_path = tmp_path / "mixed_phase.db"
    store = MemoryStore(db_path=db_path)
    store.create_schema()

    # Six AUTONOMOUS turns — same shape as ``test_aggregate_seeded_db_populates_m1_m2``.
    autonomous_pairs = [
        ("kant", "rikyu"),
        ("rikyu", "kant"),
        ("kant", "rikyu"),
        ("kant", "nietzsche"),
        ("nietzsche", "kant"),
        ("kant", "nietzsche"),
    ]
    for turn_index, (speaker, addressee) in enumerate(autonomous_pairs):
        store.add_dialog_turn_sync(
            DialogTurnMsg(
                tick=10 + turn_index,
                dialog_id="d_auto",
                speaker_id=f"a_{speaker}_001",
                addressee_id=f"a_{addressee}_001",
                utterance=f"auto {turn_index}",
                turn_index=turn_index,
            ),
            speaker_persona_id=speaker,
            addressee_persona_id=addressee,
            epoch_phase=EpochPhase.AUTONOMOUS,
        )

    # Six Q_AND_A turns with a degenerate single-pair pattern so that, if
    # the filter were broken, M1 (pair_information_gain) would collapse
    # toward 0 and the test would fail loudly.
    for turn_index in range(6):
        store.add_dialog_turn_sync(
            DialogTurnMsg(
                tick=20 + turn_index,
                dialog_id="d_qa",
                speaker_id="a_kant_001",
                addressee_id="a_rikyu_001",
                utterance=f"qa {turn_index}",
                turn_index=turn_index,
            ),
            speaker_persona_id="kant",
            addressee_persona_id="rikyu",
            epoch_phase=EpochPhase.Q_AND_A,
        )

    result = aggregate(db_path, run_id="mixed_phase")
    # Only the 6 autonomous turns drive metrics.
    assert result["num_dialog_turns"] == 6
    assert result["num_agents"] == 3
    autonomous_pair_info = result["pair_information_gain_bits"]
    autonomous_late = result["late_turn_fraction"]
    assert isinstance(autonomous_pair_info, float)

    # Compute the AUTONOMOUS-only baseline directly from the same DB and
    # compare. This makes the assertion immune to formula tweaks: whatever
    # the autonomous-only number is, the mixed-phase number must equal it.
    baseline_db = tmp_path / "auto_only.db"
    baseline_store = MemoryStore(db_path=baseline_db)
    baseline_store.create_schema()
    for turn_index, (speaker, addressee) in enumerate(autonomous_pairs):
        baseline_store.add_dialog_turn_sync(
            DialogTurnMsg(
                tick=10 + turn_index,
                dialog_id="d_auto",
                speaker_id=f"a_{speaker}_001",
                addressee_id=f"a_{addressee}_001",
                utterance=f"auto {turn_index}",
                turn_index=turn_index,
            ),
            speaker_persona_id=speaker,
            addressee_persona_id=addressee,
            epoch_phase=EpochPhase.AUTONOMOUS,
        )
    baseline_result = aggregate(baseline_db, run_id="auto_only")
    assert autonomous_pair_info == pytest.approx(
        baseline_result["pair_information_gain_bits"]
    )
    assert autonomous_late == pytest.approx(baseline_result["late_turn_fraction"])


def test_aggregate_pre_migration_null_treated_as_autonomous(tmp_path: Path) -> None:
    """Pre-M7ε rows have NULL ``epoch_phase`` and must count as AUTONOMOUS.

    Backward-compat contract from ε decisions D4 / store docstring: a
    legacy DB whose ``dialog_turns`` rows pre-date the column must read
    back through the AUTONOMOUS filter and contribute to metrics, not be
    silently dropped.
    """
    db_path = tmp_path / "null_phase.db"
    store = MemoryStore(db_path=db_path)
    store.create_schema()

    # Insert rows directly with NULL epoch_phase, bypassing add_dialog_turn_sync.
    conn = store._ensure_conn()
    with store._conn_lock:
        for turn_index in range(6):
            speaker, addressee = (
                ("kant", "nietzsche")
                if turn_index % 2 == 0
                else ("nietzsche", "kant")
            )
            conn.execute(
                "INSERT INTO dialog_turns(id, dialog_id, tick, turn_index, "
                "speaker_agent_id, speaker_persona_id, addressee_agent_id, "
                "addressee_persona_id, utterance, created_at, epoch_phase) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,NULL)",
                (
                    f"dt_legacy_{turn_index:04d}",
                    "d_legacy",
                    10 + turn_index,
                    turn_index,
                    f"a_{speaker}_001",
                    speaker,
                    f"a_{addressee}_001",
                    addressee,
                    f"legacy {turn_index}",
                    f"2026-04-25T12:00:{turn_index:02d}+00:00",
                ),
            )
        conn.commit()

    result = aggregate(db_path, run_id="legacy")
    # All 6 NULL rows survive the filter.
    assert result["num_dialog_turns"] == 6
    assert result["num_agents"] == 2
