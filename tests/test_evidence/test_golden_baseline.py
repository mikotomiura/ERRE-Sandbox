"""Tests for ``erre_sandbox.evidence.golden_baseline`` (m9-eval-system P2c).

The driver is the only golden-baseline component that depends on the live
:class:`InMemoryDialogScheduler`. These tests verify the contract layers
specified in ``design-final.md`` §"Orchestrator" and ``decisions.md`` ME-5
/ ME-7:

1. **Public-API only** — the driver opens / drives / closes one dialog
   per stimulus through ``schedule_initiate`` / ``record_turn`` /
   ``close_dialog`` (Codex HIGH-4: there is no input queue surface).
2. **Synthetic 4th persona isolation** (LOW-2) — production loader
   rejects unknown personas; the test fixture is reachable only via
   ``load_synthetic_fixture``.
3. **Reproducible seed manifest** (ME-5) — every committed seed in
   ``golden/seeds.json`` round-trips through ``derive_seed`` on both
   the Mac and G-GEAR.
4. **MCQ option seeded shuffle** (ME-7 §1) — same ``(seed_root,
   stimulus_id)`` always produces the same permutation; cross-cell
   seeds are independent.
5. **Cycle-1-only primary scoring** (ME-7 §2) — cycle 2/3 outcomes
   are scored=False with reason=cycle_not_first; legend +
   category_subscore_eligible=False also produce documented exclusion.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from erre_sandbox.evidence.golden_baseline import (
    DEFAULT_PERSONAS,
    DEFAULT_RUN_COUNT,
    DEFAULT_SALT,
    GoldenBaselineDriver,
    assert_seed_manifest_consistent,
    build_seed_manifest,
    derive_seed,
    load_seed_manifest,
    load_stimulus_battery,
    load_synthetic_fixture,
    shuffled_mcq_options,
    shuffled_mcq_order,
)
from erre_sandbox.integration.dialog import InMemoryDialogScheduler

if TYPE_CHECKING:
    from collections.abc import Callable

    from erre_sandbox.schemas import ControlEnvelope, DialogTurnMsg

REPO_ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "synthetic_4th_mcq.yaml"


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_collector() -> tuple[
    list[ControlEnvelope],
    list[DialogTurnMsg],
    Callable[..., None],
    Callable[..., None],
]:
    envelopes: list[ControlEnvelope] = []
    turns: list[DialogTurnMsg] = []

    def envelope_sink(env: ControlEnvelope) -> None:
        envelopes.append(env)

    def turn_sink(turn: DialogTurnMsg) -> None:
        turns.append(turn)

    return envelopes, turns, envelope_sink, turn_sink


def _make_scheduler() -> tuple[
    InMemoryDialogScheduler, list[ControlEnvelope], list[DialogTurnMsg]
]:
    envelopes, turns, env_sink, turn_sink = _make_collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=env_sink,
        turn_sink=turn_sink,
        golden_baseline_mode=True,
    )
    return scheduler, envelopes, turns


def _stub_text_inference(
    *,
    persona_id: str,
    stimulus: dict[str, Any],
    cycle_idx: int,
    turn_index: int,
    prior_turns: tuple[DialogTurnMsg, ...],
    mcq_shuffled_options: dict[str, str] | None,
) -> str:
    """Lightweight inference stub: deterministic text per cell, ignores MCQ scoring."""
    del prior_turns, mcq_shuffled_options
    return (
        f"[{persona_id}|{stimulus.get('stimulus_id', 'na')}|cycle={cycle_idx}|"
        f"turn={turn_index}]"
    )


def _make_perfect_mcq_inference(seed_root: int) -> Callable[..., str]:
    """MCQ inference that always returns the post-shuffle correct label."""

    def inference(
        *,
        persona_id: str,
        stimulus: dict[str, Any],
        cycle_idx: int,
        turn_index: int,
        prior_turns: tuple[DialogTurnMsg, ...],
        mcq_shuffled_options: dict[str, str] | None,
    ) -> str:
        del persona_id, cycle_idx, turn_index, prior_turns, mcq_shuffled_options
        if stimulus.get("category") == "roleeval":
            order = shuffled_mcq_order(seed_root, str(stimulus["stimulus_id"]))
            correct_raw = stimulus["correct_option"]
            return ["A", "B", "C", "D"][order.index(correct_raw)]
        return "non-mcq reply"

    return inference


# ---------------------------------------------------------------------------
# 1. derive_seed / seed manifest stability (ME-5)
# ---------------------------------------------------------------------------


def test_derive_seed_matches_blake2b_definition() -> None:
    """``derive_seed`` is exactly the ME-5 verbatim formula."""
    persona_id = "kant"
    run_idx = 2
    salt = "m9-eval-v1"
    expected_key = f"{salt}|{persona_id}|{run_idx}".encode()
    expected_seed = int.from_bytes(
        hashlib.blake2b(expected_key, digest_size=8).digest(), "big"
    )
    assert derive_seed(persona_id, run_idx, salt) == expected_seed


def test_derive_seed_deterministic_across_calls() -> None:
    """Same inputs → identical uint64; different run_idx → different seed."""
    a = derive_seed("kant", 0)
    b = derive_seed("kant", 0)
    c = derive_seed("kant", 1)
    assert a == b
    assert a != c


def test_derive_seed_returns_uint64_range() -> None:
    """``derive_seed`` output is in the ``[0, 2**64)`` range for PCG64."""
    seed = derive_seed("nietzsche", 4)
    assert 0 <= seed < 2**64


def test_seed_manifest_committed_file_matches_python() -> None:
    """Committed seeds.json matches a fresh derive_seed call (Mac/G-GEAR identical)."""
    manifest = load_seed_manifest()
    assert manifest["schema_version"] == "0.1.0-m9eval-p2c"
    assert manifest["salt"] == DEFAULT_SALT
    assert manifest["personas"] == list(DEFAULT_PERSONAS)
    assert manifest["run_count"] == DEFAULT_RUN_COUNT
    expected_rows = DEFAULT_RUN_COUNT * len(DEFAULT_PERSONAS)
    assert len(manifest["seeds"]) == expected_rows
    # The consistency check raises AssertionError on any mismatch.
    assert_seed_manifest_consistent(manifest)


def test_seed_manifest_round_trip(tmp_path: Path) -> None:
    """Build → write → load round-trip preserves every row."""
    from erre_sandbox.evidence.golden_baseline import write_seed_manifest

    out = tmp_path / "seeds.json"
    written = write_seed_manifest(out)
    loaded = load_seed_manifest(out)
    assert loaded == written
    assert_seed_manifest_consistent(loaded)


def test_build_seed_manifest_run_count_param() -> None:
    """``build_seed_manifest`` honours custom ``run_count``."""
    manifest = build_seed_manifest(run_count=2)
    assert manifest["run_count"] == 2
    assert len(manifest["seeds"]) == 2 * len(DEFAULT_PERSONAS)


def test_seed_manifest_is_stable_in_committed_file() -> None:
    """Concrete sentinel: the committed kant/run_idx=0 seed is the canonical value.

    Catches accidental ``DEFAULT_SALT`` / formula changes that would
    shift the entire manifest. The number is the blake2b digest of
    ``b"m9-eval-v1|kant|0"`` taken as big-endian uint64.
    """
    assert derive_seed("kant", 0, DEFAULT_SALT) == int.from_bytes(
        hashlib.blake2b(b"m9-eval-v1|kant|0", digest_size=8).digest(), "big"
    )
    manifest = load_seed_manifest()
    kant_run0 = next(
        row
        for row in manifest["seeds"]
        if row["persona_id"] == "kant" and row["run_idx"] == 0
    )
    assert kant_run0["seed"] == derive_seed("kant", 0, DEFAULT_SALT)


# ---------------------------------------------------------------------------
# 2. MCQ option seeded shuffle (ME-7 §1)
# ---------------------------------------------------------------------------


def test_mcq_seeded_shuffle_deterministic_same_inputs() -> None:
    """Same ``(seed_root, stimulus_id)`` → same permutation."""
    a = shuffled_mcq_order(seed_root=1234, stimulus_id="roleeval_kant_01")
    b = shuffled_mcq_order(seed_root=1234, stimulus_id="roleeval_kant_01")
    assert a == b
    # And it is in fact a permutation of A/B/C/D.
    assert sorted(a) == ["A", "B", "C", "D"]


def test_mcq_seeded_shuffle_independent_per_cell() -> None:
    """Different ``stimulus_id`` under the same root yield independent streams.

    Two random permutations of 4 elements collide with probability 1/24,
    so a single pair could coincide by chance. Across 10 distinct
    ``stimulus_id`` values, the probability that **all** match is
    ``(1/24)**9`` — vanishingly small. The assertion is that the set of
    permutations spans more than one value.
    """
    seen = {
        tuple(shuffled_mcq_order(seed_root=1234, stimulus_id=f"roleeval_kant_{i:02d}"))
        for i in range(1, 11)
    }
    assert len(seen) > 1


def test_mcq_seeded_shuffle_different_seed_root_diverges() -> None:
    """Different ``seed_root`` produces an independent stream for the same cell."""
    a = shuffled_mcq_order(seed_root=1234, stimulus_id="roleeval_kant_01")
    b = shuffled_mcq_order(seed_root=5678, stimulus_id="roleeval_kant_01")
    assert a != b


def test_shuffled_mcq_options_remap_preserves_text() -> None:
    """Applying the shuffle remap reads each raw option's text under its new label."""
    raw = {"A": "ta", "B": "tb", "C": "tc", "D": "td"}
    order = shuffled_mcq_order(seed_root=42, stimulus_id="x")
    remapped = shuffled_mcq_options(raw, order)
    assert set(remapped.keys()) == {"A", "B", "C", "D"}
    # Every raw text shows up exactly once in the remapped dict.
    assert sorted(remapped.values()) == sorted(raw.values())
    # Position i of `order` names the raw label that becomes new label i.
    for i, raw_label in enumerate(order):
        new_label = ["A", "B", "C", "D"][i]
        assert remapped[new_label] == raw[raw_label]


# ---------------------------------------------------------------------------
# 3. Synthetic 4th persona isolation (LOW-2)
# ---------------------------------------------------------------------------


def test_load_stimulus_battery_rejects_unknown_persona() -> None:
    """Production loader rejects ``synthetic_4th`` (or any non-default persona)."""
    with pytest.raises(ValueError, match="not part of the production"):
        load_stimulus_battery("synthetic_4th")
    with pytest.raises(ValueError, match="not part of the production"):
        load_stimulus_battery("plato")


def test_load_synthetic_fixture_accessible_only_via_helper() -> None:
    """Synthetic 4th MCQ fixture loads through ``load_synthetic_fixture`` only."""
    stimuli = load_synthetic_fixture(SYNTHETIC_FIXTURE_PATH)
    # Three MCQs, all roleeval.
    assert len(stimuli) == 3
    assert all(s["category"] == "roleeval" for s in stimuli)
    # Every item is marked fictional + scored=False so the aggregator
    # cannot accidentally include them.
    assert all(s.get("fictional") is True for s in stimuli)
    assert all(s.get("scored") is False for s in stimuli)


def test_synthetic_fixture_is_outside_production_golden_dir() -> None:
    """The fixture must not live under ``golden/stimulus/`` (LOW-2 isolation rule)."""
    assert "tests/fixtures" in str(SYNTHETIC_FIXTURE_PATH).replace("\\", "/")
    production_dir = REPO_ROOT / "golden" / "stimulus"
    # No persona file under production_dir mentions "synthetic_4th".
    for yaml_path in production_dir.glob("*.yaml"):
        if yaml_path.name == "_schema.yaml":
            continue
        text = yaml_path.read_text(encoding="utf-8")
        assert "synthetic_4th" not in text, (
            f"{yaml_path.name} mentions synthetic_4th — should be in tests/fixtures"
        )


# ---------------------------------------------------------------------------
# 4. Driver public-API only (Codex HIGH-4) — full cycle dry-runs
# ---------------------------------------------------------------------------


def test_driver_requires_golden_baseline_mode_true() -> None:
    """Driver construction asserts the scheduler is in golden mode."""
    _envelopes, _turns, env_sink, turn_sink = _make_collector()
    scheduler = InMemoryDialogScheduler(
        envelope_sink=env_sink,
        turn_sink=turn_sink,
        golden_baseline_mode=False,
    )
    with pytest.raises(ValueError, match="golden_baseline_mode=True"):
        GoldenBaselineDriver(
            scheduler=scheduler,
            inference_fn=_stub_text_inference,
            seed_root=derive_seed("kant", 0),
        )


def test_one_stimulus_cycle_dryrun() -> None:
    """1 synthetic stimulus + mock LLM exercises schedule → record × N → close."""
    scheduler, envelopes, turns = _make_scheduler()
    driver = GoldenBaselineDriver(
        scheduler=scheduler,
        inference_fn=_stub_text_inference,
        seed_root=derive_seed("kant", 0),
        cycle_count=1,
    )
    stim = {
        "stimulus_id": "wachsmuth_kant_dry",
        "category": "wachsmuth",
        "prompt_text": "Test claim.",
        "expected_zone": "study",
        "expected_turn_count": 2,
    }
    outcomes = driver.run_persona("kant", stimuli=[stim])
    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.category == "wachsmuth"
    assert outcome.cycle_idx == 1
    assert outcome.turn_count == 2
    assert outcome.mcq is None
    # Two turns recorded → two DialogTurnMsg via the turn_sink.
    assert len(turns) == 2
    assert [t.turn_index for t in turns] == [0, 1]
    # Initiator speaks first, alternation on.
    assert turns[0].speaker_id == "kant"
    assert turns[1].speaker_id == "interlocutor"
    # Envelopes: 1 initiate + 2 close (open + close) — exactly one open and
    # one close per stimulus.
    assert sum(1 for e in envelopes if e.kind == "dialog_initiate") == 1
    assert sum(1 for e in envelopes if e.kind == "dialog_close") == 1
    # Scheduler is empty after the run — close_dialog actually closed it.
    assert scheduler.open_count == 0


def test_70_stimulus_battery_drives_cleanly_through_three_cycles() -> None:
    """Full Kant battery (70 stim x 3 cycles = 210 dialogs) flows without queue."""
    scheduler, envelopes, turns = _make_scheduler()
    seed = derive_seed("kant", 0)
    driver = GoldenBaselineDriver(
        scheduler=scheduler,
        inference_fn=_stub_text_inference,
        seed_root=seed,
        cycle_count=3,
    )
    outcomes = driver.run_persona("kant")  # loads production YAML
    # 70 stimulus × 3 cycles = 210 outcomes, one per dialog.
    assert len(outcomes) == 210
    # 70 × 3 = 210 dialog opens, scheduler must end empty (every dialog closed).
    open_envelopes = sum(1 for e in envelopes if e.kind == "dialog_initiate")
    close_envelopes = sum(1 for e in envelopes if e.kind == "dialog_close")
    assert open_envelopes == 210
    assert close_envelopes == 210
    assert scheduler.open_count == 0
    # Every outcome's category is one of the 4 known buckets.
    seen_categories = {o.category for o in outcomes}
    assert seen_categories <= {
        "wachsmuth",
        "tom_chashitsu",
        "roleeval",
        "moral_dilemma",
    }
    # MCQ outcomes only exist for the roleeval items: 10 stim × 3 cycles = 30.
    mcq_outcomes = [o for o in outcomes if o.mcq is not None]
    assert len(mcq_outcomes) == 30
    # Sink-collected turns: production YAML mixes expected_turn_count 1-2,
    # so the turn count must equal the sum across outcomes.
    assert len(turns) == sum(o.turn_count for o in outcomes)


def test_natural_phase_toggle_restores_zone_guard() -> None:
    """``enable_natural_phase`` flips the public attribute back to False."""
    scheduler, _envelopes, _turns = _make_scheduler()
    driver = GoldenBaselineDriver(
        scheduler=scheduler,
        inference_fn=_stub_text_inference,
        seed_root=derive_seed("kant", 0),
    )
    assert scheduler.golden_baseline_mode is True
    driver.enable_natural_phase()
    assert scheduler.golden_baseline_mode is False


# ---------------------------------------------------------------------------
# 5. MCQ scoring protocol (ME-7 §2)
# ---------------------------------------------------------------------------


def _mcq_stimulus(
    *,
    stimulus_id: str = "roleeval_kant_test",
    correct_option: str = "B",
    source_grade: str = "fact",
    category_subscore_eligible: bool = True,
) -> dict[str, Any]:
    return {
        "stimulus_id": stimulus_id,
        "category": "roleeval",
        "mcq_subcategory": "chronology",
        "prompt_text": "test prompt",
        "options": {
            "A": "option_a_text",
            "B": "option_b_text",
            "C": "option_c_text",
            "D": "option_d_text",
        },
        "correct_option": correct_option,
        "source_ref": "fixture:test",
        "source_grade": source_grade,
        "category_subscore_eligible": category_subscore_eligible,
        "present_in_persona_prompt": False,
        "expected_zone": "study",
        "expected_turn_count": 1,
    }


def test_cycle_1_only_scoring_excludes_repeats() -> None:
    """Cycle 1 outcome is scored; cycle 2 / cycle 3 outcomes are excluded."""
    scheduler, _envelopes, _turns = _make_scheduler()
    seed = derive_seed("kant", 0)
    driver = GoldenBaselineDriver(
        scheduler=scheduler,
        inference_fn=_make_perfect_mcq_inference(seed),
        seed_root=seed,
        cycle_count=3,
    )
    stim = _mcq_stimulus()
    outcomes = driver.run_persona("kant", stimuli=[stim])
    assert len(outcomes) == 3
    # Cycle 1: scored, correct (perfect mock).
    c1 = outcomes[0]
    assert c1.cycle_idx == 1
    assert c1.mcq is not None
    assert c1.mcq.scored is True
    assert c1.mcq.is_correct is True
    assert c1.mcq.scored_excluded_reason is None
    # Cycle 2 / Cycle 3: excluded with reason cycle_not_first.
    for cyc in (outcomes[1], outcomes[2]):
        assert cyc.mcq is not None
        assert cyc.mcq.scored is False
        assert cyc.mcq.scored_excluded_reason == "cycle_not_first"
        assert cyc.mcq.is_correct is None


def test_legend_source_grade_excluded_from_scoring() -> None:
    """``source_grade=legend`` in cycle 1 is still excluded."""
    scheduler, _envelopes, _turns = _make_scheduler()
    seed = derive_seed("rikyu", 0)
    driver = GoldenBaselineDriver(
        scheduler=scheduler,
        inference_fn=_make_perfect_mcq_inference(seed),
        seed_root=seed,
        cycle_count=1,
    )
    stim = _mcq_stimulus(
        stimulus_id="roleeval_rikyu_legend",
        source_grade="legend",
        category_subscore_eligible=False,
    )
    outcomes = driver.run_persona("rikyu", stimuli=[stim])
    assert outcomes[0].mcq is not None
    assert outcomes[0].mcq.scored is False
    # cycle 1 + legend → reason is legend_source_grade (cycle gate passes
    # so the next clause fires).
    assert outcomes[0].mcq.scored_excluded_reason == "legend_source_grade"


def test_category_subscore_eligible_false_excluded() -> None:
    """``category_subscore_eligible=False`` (with non-legend grade) is also excluded."""
    scheduler, _envelopes, _turns = _make_scheduler()
    seed = derive_seed("kant", 0)
    driver = GoldenBaselineDriver(
        scheduler=scheduler,
        inference_fn=_make_perfect_mcq_inference(seed),
        seed_root=seed,
        cycle_count=1,
    )
    stim = _mcq_stimulus(
        stimulus_id="roleeval_kant_excluded",
        source_grade="secondary",
        category_subscore_eligible=False,
    )
    outcomes = driver.run_persona("kant", stimuli=[stim])
    assert outcomes[0].mcq is not None
    assert outcomes[0].mcq.scored is False
    assert outcomes[0].mcq.scored_excluded_reason == "category_subscore_excluded"


def test_off_format_reply_counts_as_incorrect_when_scored() -> None:
    """Reply not starting with A/B/C/D records scored=True, is_correct=False."""

    def garbage_inference(
        *,
        persona_id: str,
        stimulus: dict[str, Any],
        cycle_idx: int,
        turn_index: int,
        prior_turns: tuple[DialogTurnMsg, ...],
        mcq_shuffled_options: dict[str, str] | None,
    ) -> str:
        del (
            persona_id,
            stimulus,
            cycle_idx,
            turn_index,
            prior_turns,
            mcq_shuffled_options,
        )
        return "I prefer not to answer."

    scheduler, _envelopes, _turns = _make_scheduler()
    driver = GoldenBaselineDriver(
        scheduler=scheduler,
        inference_fn=garbage_inference,
        seed_root=derive_seed("kant", 0),
        cycle_count=1,
    )
    outcome = driver.run_persona("kant", stimuli=[_mcq_stimulus()])[0]
    assert outcome.mcq is not None
    assert outcome.mcq.scored is True
    assert outcome.mcq.response_option is None
    assert outcome.mcq.is_correct is False


def test_perfect_mock_yields_correct_post_shuffle_label() -> None:
    """Perfect-mock returns the post-shuffle label; driver records is_correct=True."""
    scheduler, _envelopes, _turns = _make_scheduler()
    seed = derive_seed("nietzsche", 0)
    driver = GoldenBaselineDriver(
        scheduler=scheduler,
        inference_fn=_make_perfect_mcq_inference(seed),
        seed_root=seed,
        cycle_count=1,
    )
    # Use the synthetic 4th MCQ fixture as a tightly-scoped test set.
    stimuli = load_synthetic_fixture(SYNTHETIC_FIXTURE_PATH)
    outcomes = driver.run_persona("kant", stimuli=stimuli)
    # The fixture has 2 fact + 1 legend; perfect mock answers the
    # shuffled-correct label for all 3, but legend is scored=False.
    fact_outcomes = [o for o in outcomes if o.mcq is not None and o.mcq.scored]
    excluded_outcomes = [o for o in outcomes if o.mcq is not None and not o.mcq.scored]
    assert len(fact_outcomes) == 2
    assert len(excluded_outcomes) == 1
    assert all(o.mcq.is_correct is True for o in fact_outcomes)
    assert excluded_outcomes[0].mcq.scored_excluded_reason in (
        "legend_source_grade",
        "category_subscore_excluded",
    )
