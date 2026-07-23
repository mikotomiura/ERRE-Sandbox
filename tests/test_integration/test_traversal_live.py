"""M13 aha-substrate-embodiment traversal harness — Issue 001 W1 test.

FROZEN ADR ``.steering/20260723-m13-aha-substrate-embodiment/design-final.md``
(construction-only, organ 無改変, Option A). Ollama-free throughout: the
scripted traversal chat client never touches a live LLM.

Scope guard (design-final.md §Guard, binding, mirrors
``test_two_phase_live.py``). This is a *construction* apparatus test, **NOT a
measurement line**. It asserts only the exact-match physical visit sequence
(W1) — no effect / divergence / floor / verdict statistic.
"""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import UTC, datetime
from itertools import pairwise, zip_longest
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from scripts.aha_traversal_live_capture import (
    _embedding_calls_from_jsonl,
    _embedding_calls_to_jsonl,
)
from scripts.aha_traversal_live_capture import verify as _script_verify

from erre_sandbox.erre.two_phase import TwoPhaseKnob
from erre_sandbox.inference.ollama_adapter import OllamaChatClient
from erre_sandbox.integration.embodied import handoff
from erre_sandbox.integration.embodied.live import ThinkOffChatClient
from erre_sandbox.integration.embodied.loop import (
    EclRunResult,
    EclTraceRow,
    RecordReplayChatClient,
    run_ecl_loop,
)
from erre_sandbox.integration.embodied.traversal_live import (
    TRAVERSAL_EXPECTED_INCOMING_LAMBDA,
    TRAVERSAL_EXPECTED_MOVE_TICKS,
    TRAVERSAL_EXPECTED_POSITIVE_LAMBDA_TICKS,
    TRAVERSAL_EXPECTED_ROUTE,
    TRAVERSAL_HORIZON,
    TRAVERSAL_ITINERARY,
    TRAVERSAL_PHYSICS_TICKS_PER_COGNITION,
    TRAVERSAL_START_ZONE,
    EmbeddingRecordReplayClient,
    EmbeddingReplayError,
    RecordedEmbeddingCall,
    ScriptedTraversalChatClient,
    TraversalScriptError,
    expected_lambda_sequence_checksum,
    extract_visit_sequence,
    run_traversal_capture,
    run_traversal_replay_spy,
    traversal_channel_exercise_summary,
    traversal_firing_summary,
    traversal_generation_seed_agent_state,
    traversal_observation_factory,
    traversal_seed_agent_state,
)
from erre_sandbox.integration.embodied.two_phase_live import (
    quantise_sampling,
    run_two_phase_capture,
)
from erre_sandbox.memory import EmbeddingClient, MemoryStore
from erre_sandbox.memory.embedding import DOC_PREFIX
from erre_sandbox.schemas import ERREModeName, LocomotionState, Zone
from tests.test_integration._measurement_guard import assert_no_measurement_surface_v1

_FIXED_CLOCK = datetime(2026, 1, 1, tzinfo=UTC)
_THIS_FILE = Path(__file__)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_SRC = (
    _REPO_ROOT
    / "src"
    / "erre_sandbox"
    / "integration"
    / "embodied"
    / "traversal_live.py"
)
_SCRIPT_SRC = _REPO_ROOT / "scripts" / "aha_traversal_live_capture.py"
_GOLDEN_DIR = _REPO_ROOT / "tests" / "fixtures" / "aha_traversal_golden"

# Traversal-specific exact-match extension over the shared v1 guard (M1, mirrors
# test_two_phase_live.py's ``_PHASE4B_BANNED_EXACT``): the shared guard already
# bans "floor"/"verdict"/"divergence" as identifier substrings; this adds the
# remaining tokens the coordinator's review flagged (effect / aha proxy /
# detectability) as exact-match so legitimate names (e.g. "effective",
# "affect") do not false-trip.
_TRAVERSAL_BANNED_EXACT = frozenset(
    {
        "effect",
        "effect_size",
        "detectability",
        "aha_proxy",
        "aha_score",
        "magnitude",
        "score",
    }
)


def _mock_embedding() -> EmbeddingClient:
    """Constant-vector embedding (Ollama-free), mirrors test_two_phase_live.py."""
    vec = [handoff.GOLDEN_EMBED_VALUE] * EmbeddingClient.DEFAULT_DIM

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        inputs = body.get("input") or []
        count = len(inputs) if isinstance(inputs, list) else 1
        return httpx.Response(httpx.codes.OK, json={"embeddings": [vec] * count})

    return EmbeddingClient(
        client=httpx.AsyncClient(
            base_url=EmbeddingClient.DEFAULT_ENDPOINT,
            transport=httpx.MockTransport(handler),
        )
    )


def test_traversal_seed_starts_at_peripatos_with_locomotion_armed() -> None:
    """The traversal seed relocates the golden agent to peripatos, λ armed at 0."""
    seed = traversal_seed_agent_state()
    assert seed.position.zone == TRAVERSAL_START_ZONE
    assert seed.position.x == 0.0
    assert seed.position.y == 0.0
    assert seed.position.z == 0.0
    assert seed.locomotion == LocomotionState(lam=0.0)
    golden = handoff.golden_agent_state()
    exclude = {"position", "locomotion", "wall_clock"}
    assert seed.model_dump(exclude=exclude) == golden.model_dump(exclude=exclude)


async def test_traversal_route_replay_fidelity() -> None:
    """W1: the recorded per-tick (end-of-cognition-tick) physical visit
    sequence exact-matches the frozen itinerary (peripatos -> agora -> garden
    -> chashitsu -> study -> peripatos). LOW-1 review: this is a claim about
    ``extract_visit_sequence``'s **end-of-tick sampling**, not the raw 30 Hz
    continuous trace — the golden's ``garden<->chashitsu`` /
    ``chashitsu<->study`` legs transiently re-enter peripatos mid-tick (a
    Voronoi triple-point artefact, see ``traversal_live.py``'s module
    docstring "calibration finding"), so "each leg crosses its boundary
    exactly once" is only true of the sampled visit sequence, not every
    physics row."""
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    try:
        result = await run_traversal_capture(
            run_id="i1-w1-route-replay",
            store=store,
            embedding=embedding,
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
        )
    finally:
        await embedding.close()
        await store.close()

    visited = extract_visit_sequence(result)
    assert visited == TRAVERSAL_EXPECTED_ROUTE

    # Adjacent entries in the (end-of-tick-sampled) visit sequence are always
    # distinct — no leg collapses / no leg repeats in what W1 actually
    # samples (LOW-1: not a claim about the raw continuous physics trace).
    for prev_zone, next_zone in pairwise(visited):
        assert prev_zone != next_zone

    # Plane 2 provenance: each cognition tick's committed plan requested
    # exactly the itinerary's destination for that tick (the scripted
    # planner served the frozen schedule, not an ad hoc one).
    assert len(result.decisions) == TRAVERSAL_HORIZON
    for tick, decision in enumerate(result.decisions):
        assert decision.plan is not None
        assert decision.llm_status == "ok"
        assert decision.plan.destination_zone == TRAVERSAL_ITINERARY[tick]


async def test_traversal_route_replay_is_deterministic() -> None:
    """Two independent runs of the same scripted itinerary reproduce the same
    checksum and visit sequence — the fidelity contract (record/replay
    determinism), not an effect-size claim."""

    async def _run() -> tuple[str, tuple[object, ...]]:
        store = MemoryStore(db_path=":memory:")
        store.create_schema()
        embedding = _mock_embedding()
        try:
            result = await run_traversal_capture(
                run_id="i1-w1-determinism",
                store=store,
                embedding=embedding,
                retrieval_now=_FIXED_CLOCK,
                base_ts=_FIXED_CLOCK,
            )
        finally:
            await embedding.close()
            await store.close()
        return result.checksum, extract_visit_sequence(result)

    checksum_a, visited_a = await _run()
    checksum_b, visited_b = await _run()
    assert checksum_a == checksum_b
    assert visited_a == visited_b == TRAVERSAL_EXPECTED_ROUTE


# --------------------------------------------------------------------------- #
# M1 — measurement-line non-re-entry guard (executable, mirrors test_two_phase_live.py)
# --------------------------------------------------------------------------- #


def _assert_no_traversal_measurement_surface(tree: ast.Module) -> None:
    """Traversal-specific exact-match extension over the shared v1 guard (M1)."""
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.append(node.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.append(node.target.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.arg):
            names.append(node.arg)
        for name in names:
            assert name.lower() not in _TRAVERSAL_BANNED_EXACT, name
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    assert key.value.lower() not in _TRAVERSAL_BANNED_EXACT, key.value


def test_traversal_measurement_guard() -> None:
    """No measurement import/identifier/key in the traversal apparatus, the I3
    capture script, or this test module (M1 + I3 LOW-1) — the shared ECL v1
    **full 3-hole** AST guard (imports / dynamic import / dict-key+filename)
    plus the traversal-specific exact-match extension above. Binding: I2/I3
    extend this same module (and I3 adds the capture script + committed
    golden), so emit (effect/divergence/floor/verdict/aha-proxy) surface
    creeping in later is caught here, not just asserted in prose.

    ``_SCRIPT_SRC`` scans with ``scan_strings=True`` (TASK-POST review,
    guard-coverage restoration): mirrors ``test_two_phase_live.py``'s own
    ``(_SCRIPT_SRC, True)`` precedent this module's docstring already claims
    to follow. ``scan_strings=False`` would leave hole-2 (a dynamic
    ``importlib.import_module("erre_sandbox.evidence...")`` string constant)
    and hole-3 (a banned dict key, or a ``.json``/``.jsonl`` filename stem
    carrying a banned token) unchecked on the ONE file in this bundle that
    actually **emits** side files (manifest / firing / channel-exercise /
    embedding-record annotations) — the widest emit surface here, so it gets
    the strictest scan, not the loosest. ``_THIS_FILE`` (this test module)
    stays ``False``: it legitimately imports/references the banned-word
    constants themselves to build the guard, which hole-2/hole-3 would
    false-trip on.
    """
    for path, scan_strings in (
        (_MODULE_SRC, True),
        (_SCRIPT_SRC, True),
        (_THIS_FILE, False),
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert_no_measurement_surface_v1(tree, scan_strings=scan_strings)
        _assert_no_traversal_measurement_surface(tree)


# --------------------------------------------------------------------------- #
# M2 — frozen-value literal pin (tune-to-pass closure, executable not prose)
# --------------------------------------------------------------------------- #


def test_traversal_frozen_values_pinned() -> None:
    """M2: hardcoded literals independent of the module's own constants.

    ``visited == TRAVERSAL_EXPECTED_ROUTE`` elsewhere in this file is
    circular with respect to itinerary edits (both sides derive from
    ``TRAVERSAL_ITINERARY``); this test pins the ADR's frozen values as bare
    literals so a drift in the *module* constants (not just the itinerary
    shape) fails here independently of any run — the executable form of
    I1-G2's "drift-zero" requirement (ADR HIGH-1 tune-to-pass closure)."""
    assert TRAVERSAL_EXPECTED_ROUTE == (
        Zone.PERIPATOS,
        Zone.AGORA,
        Zone.GARDEN,
        Zone.CHASHITSU,
        Zone.STUDY,
        Zone.PERIPATOS,
    )
    assert TRAVERSAL_HORIZON == 5
    assert TRAVERSAL_PHYSICS_TICKS_PER_COGNITION == 2000


# --------------------------------------------------------------------------- #
# M3 — embodiment-witness teeth: an insufficient physics budget must mismatch
# --------------------------------------------------------------------------- #

_KNOWN_UNDERSHOOT_PHYSICS_TICKS_PER_COGNITION = 500
"""A known-insufficient ``physics_ticks_per_cognition`` (M3 review note).

Empirically confirmed (not tuned to pass, tuned to FAIL-as-expected): at 500
the ``garden->chashitsu`` leg's ~66.7 m straight-line travel never completes
within one cognition tick's physics window (500 * 1.3 m/s / 30 Hz ≈ 21.7 m of
travel, well short), so :func:`extract_visit_sequence` reports the agent still
in ``peripatos`` for ticks 2-4 instead of ``chashitsu``/``study``/``peripatos``.
1000 was checked first (the value considered during I1 calibration) but the
*production* driver (waypoint-marker-driven scripted client + the real
``resolve_destination`` memory-centroid path) reaches every leg at 1000 — this
constant is the value actually confirmed insufficient with the real code path,
pinned literally so this regression is not re-derived from a live run's
success/failure."""


async def test_traversal_undershoot_fails_route() -> None:
    """M3: an insufficient physics budget makes the visit sequence MISMATCH.

    Proves ``extract_visit_sequence``'s end-of-tick sampling is a genuine
    embodiment witness, not a tautological echo of the scripted plan: with too
    few physics ticks the agent never actually arrives, so the recorded route
    diverges from :data:`TRAVERSAL_EXPECTED_ROUTE`."""
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    try:
        result = await run_traversal_capture(
            run_id="i1-w1-undershoot",
            store=store,
            embedding=embedding,
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
            physics_ticks_per_cognition=_KNOWN_UNDERSHOOT_PHYSICS_TICKS_PER_COGNITION,
        )
    finally:
        await embedding.close()
        await store.close()

    visited = extract_visit_sequence(result)
    assert visited != TRAVERSAL_EXPECTED_ROUTE
    # The scripted plan still requested the full itinerary every tick (Plane 2
    # provenance is knob-independent of physical arrival) — only the *physical*
    # visit sequence undershoots.
    assert len(result.decisions) == TRAVERSAL_HORIZON
    for tick, decision in enumerate(result.decisions):
        assert decision.plan is not None
        assert decision.plan.destination_zone == TRAVERSAL_ITINERARY[tick]


# --------------------------------------------------------------------------- #
# LOW-4 — extract_visit_sequence must fail loudly on a silently-dropped tick
# --------------------------------------------------------------------------- #


def _fake_row(agent_tick: int, zone: Zone) -> EclTraceRow:
    """Minimal synthetic :class:`EclTraceRow` (LOW-4 gap-detection unit test)."""
    return EclTraceRow(
        run_id="fake",
        agent_id="a_fake",
        physics_tick_index=agent_tick,
        agent_tick=agent_tick,
        order_slot=0,
        x=0.0,
        y=0.0,
        z=0.0,
        yaw=0.0,
        pitch=0.0,
        zone=zone,
        resolved_from=None,
        move_centroid=None,
        move_provenance=None,
        move_jitter=None,
        move_pre_clamp=None,
        move_post_clamp=None,
        move_clamp_fired=None,
    )


def test_extract_visit_sequence_detects_missing_tick_rows() -> None:
    """LOW-4: a cognition tick with zero physics rows fails loudly, not silently.

    Synthesises an :class:`EclRunResult` whose ``agent_tick=2`` window
    contributed no rows (simulating a driver bug / a zero-length physics
    loop) and asserts :func:`extract_visit_sequence` raises rather than
    quietly returning a shorter, gap-collapsed sequence.
    """
    rows = (
        _fake_row(0, Zone.AGORA),
        _fake_row(1, Zone.GARDEN),
        # agent_tick=2 deliberately absent — the leg it would represent.
        _fake_row(3, Zone.STUDY),
    )
    fake_result = EclRunResult(
        run_id="fake", rows=rows, decisions=(), checksum="deadbeef"
    )
    with pytest.raises(TraversalScriptError, match=r"\[2\]"):
        extract_visit_sequence(fake_result)


def test_extract_visit_sequence_empty_rows_returns_start_only() -> None:
    """Boundary case: zero rows total (e.g. ``n_cognition_ticks=0``) returns
    just ``(start_zone,)`` rather than raising — there is no gap to detect
    when nothing was ever recorded."""
    fake_result = EclRunResult(
        run_id="fake", rows=(), decisions=(), checksum="deadbeef"
    )
    assert extract_visit_sequence(fake_result) == (TRAVERSAL_START_ZONE,)


# --------------------------------------------------------------------------- #
# I2 W2 — λ update-path: exact tick series, cross-checked against the spy
# --------------------------------------------------------------------------- #


async def test_traversal_lambda_update_path() -> None:
    """I2-G1: ``expected_move_ticks`` / ``expected_positive_lambda_ticks``
    byte-pin, cross-checked against the SamplingSpy's actual eligible ticks
    (operational proxy agreement — a run-confirmed, not desk-assumed, series).

    Literal values observed from an actual run (coordinator review requirement
    — no desk assumption): every one of the 5 legs is a move
    (``move_t=[1,1,1,1,1]``); tick 0's chat call reads the traversal seed's
    ``λ=0.0`` (the all-zero ablation identity — no knob effect there yet),
    ticks 1-4 read the λ folded from ticks 0-3's moves, all >0. No "sustained"
    / effect-size language — exact tick indices and an exact float tuple only.

    **Scope (M-1 review, over-read guard)**: this witnesses the λ→sampling
    *wiring* and its *tick-timing* (tick 0 never fires, tick 1 is the earliest
    possible fire) — it does **not** witness physical arrival. That is W1's
    job (``test_traversal_undershoot_fails_route``); a green result here says
    only "the plan requested a move and λ's sampling-visibility timing matches
    the pure fold", never "the agent walked there".
    """
    assert TRAVERSAL_EXPECTED_MOVE_TICKS == (0, 1, 2, 3, 4)
    assert TRAVERSAL_EXPECTED_POSITIVE_LAMBDA_TICKS == (1, 2, 3, 4)
    assert (
        pytest.approx((0.0, 0.3, 0.51, 0.657, 0.7599))
        == TRAVERSAL_EXPECTED_INCOMING_LAMBDA
    )

    summary = await traversal_firing_summary(
        store_factory=lambda: MemoryStore(db_path=":memory:"),
        embedding_factory=_mock_embedding,
        retrieval_now=_FIXED_CLOCK,
        base_ts=_FIXED_CLOCK,
    )
    # The spy's OWN eligibility (knob-on sampling != knob-off sampling per
    # tick) is the operational λ>0 proxy — recomputed here from the summary's
    # per-tick fields (the summary itself exposes only the aggregate count).
    eligible_from_spy = tuple(
        row["agent_tick"]
        for row in summary["per_tick"]
        if row["knob_on_sampling"] != row["knob_off_sampling"]
    )
    assert eligible_from_spy == TRAVERSAL_EXPECTED_POSITIVE_LAMBDA_TICKS
    assert summary["eligible_tick_count"] == len(
        TRAVERSAL_EXPECTED_POSITIVE_LAMBDA_TICKS
    )


def test_traversal_lambda_sequence_checksum_pinned() -> None:
    """LOW-1: ``expected_lambda_sequence_checksum`` byte-pinned (the ADR's
    alternative "quantized λ sequence checksum" W2 witness option, made
    executable rather than left as an unused/untested export). A drift in
    :data:`TRAVERSAL_EXPECTED_INCOMING_LAMBDA` (or its 6-decimal quantisation)
    changes this hash — exact byte-pin, no tolerance, unlike the
    ``pytest.approx`` float-tuple check above."""
    assert (
        expected_lambda_sequence_checksum()
        == "648163682b65adf72666ebb87d8a5f7edc6f26a4dfb520c1e74d109bf29eb2ad"
    )


# --------------------------------------------------------------------------- #
# I2 W3 — knob algebra on the earned-λ traversal (sign confirmation only)
# --------------------------------------------------------------------------- #


async def test_traversal_knob_algebra() -> None:
    """I2-G2: evaluation λ>0 tick sign-inverts, generation control knob-on≡off,
    record-knob-on pin.

    **Sign confirmation only** (Codex LOW-3, honest framing): this asserts a
    boolean knob-on-vs-knob-off recomposed-sampling comparison on the
    traversal's *earned* (not seeded) λ — it is NOT a claim that "aha" or any
    generation quality / behavioural difference occurred. The bias's
    detectability (whether it changes zone/behaviour/aha) remains the frozen,
    unmeasured second link (door② UNMET, door CLOSED, R-budget=0).
    """
    summary = await traversal_firing_summary(
        store_factory=lambda: MemoryStore(db_path=":memory:"),
        embedding_factory=_mock_embedding,
        retrieval_now=_FIXED_CLOCK,
        base_ts=_FIXED_CLOCK,
    )
    assert summary["evaluation_phase_sign_inversion_fired"] is True
    assert summary["witness_tick_count"] >= 1
    assert summary["eligible_tick_count"] >= 1
    assert summary["checksums_match"] is True, "knob modulates sampling, never geometry"
    assert summary["fail_mode"] is None
    assert summary["record_knob_on_pinned"] is True

    # Generation-phase control: the SAME committed (evaluation-recorded, knob-on)
    # decisions replayed under a peripatetic (GENERATION) seed → knob-on ≡
    # knob-off, since two_phase_delta(GENERATION) ≡ locomotion_delta (ES-3).
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    try:
        record_result = await run_traversal_capture(
            run_id="i2-w3-gen-control-record",
            store=store,
            embedding=embedding,
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
            agent_state=traversal_seed_agent_state(),
            two_phase_knob=TwoPhaseKnob(),
        )
    finally:
        await embedding.close()
        await store.close()
    recorded = record_result.replay_calls()

    gen_seed = traversal_generation_seed_agent_state()
    assert gen_seed.erre.name == ERREModeName.PERIPATETIC

    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    try:
        gen_on_sampling, _ = await run_traversal_replay_spy(
            recorded=recorded,
            agent_state=gen_seed,
            two_phase_knob=TwoPhaseKnob(),
            store=store,
            embedding=embedding,
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
        )
    finally:
        await embedding.close()
        await store.close()

    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    try:
        gen_off_sampling, _ = await run_traversal_replay_spy(
            recorded=recorded,
            agent_state=gen_seed,
            two_phase_knob=None,
            store=store,
            embedding=embedding,
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
        )
    finally:
        await embedding.close()
        await store.close()

    gen_on_q = [quantise_sampling(s) for s in gen_on_sampling]
    gen_off_q = [quantise_sampling(s) for s in gen_off_sampling]
    assert gen_on_q == gen_off_q, (
        "generation phase must not invert (two_phase_delta≡locomotion_delta)"
    )
    # M-2 review (vacuous-green guard): the equality above would ALSO hold
    # trivially if λ stayed 0 throughout this replay (0==0 regardless of
    # phase) — that would prove nothing about phase-conditionality. Directly
    # confirm the generation-control replay actually reached λ>0 on the same
    # tick indices W2 pins (TRAVERSAL_EXPECTED_POSITIVE_LAMBDA_TICKS): each
    # such tick's knob-on sampling differs from the λ=0 tick-0 baseline (λ
    # genuinely moved the composed sampling here), while still equalling
    # knob-off (the phase-conditional identity holds AT that non-trivial λ,
    # not just trivially at λ=0). Together: "a λ>0 generation tick exists and
    # does not sign-invert" — non-vacuous phase-conditionality, not merely
    # "both sides happened to be zero".
    assert len(TRAVERSAL_EXPECTED_POSITIVE_LAMBDA_TICKS) >= 1
    for tick in TRAVERSAL_EXPECTED_POSITIVE_LAMBDA_TICKS:
        assert gen_on_q[tick] != gen_on_q[0], (
            f"tick {tick} generation-phase sampling equals the λ=0 tick-0 "
            "baseline — the phase-conditionality control would be vacuous "
            "(λ never left 0 in this replay)"
        )


async def test_traversal_firing_summary_is_boolean_count_only() -> None:
    """I2-G3: the firing summary carries no effect/divergence/floor/aha/verdict
    statistic — pure boolean/count, ``verdict=None``, ``hard_gate=False``, a
    side file (outside any checksum/SHA/Done set this module defines)."""
    summary = await traversal_firing_summary(
        store_factory=lambda: MemoryStore(db_path=":memory:"),
        embedding_factory=_mock_embedding,
        retrieval_now=_FIXED_CLOCK,
        base_ts=_FIXED_CLOCK,
    )
    assert summary["verdict"] is None
    assert summary["hard_gate"] is False
    for key in summary:
        assert key.lower() not in _TRAVERSAL_BANNED_EXACT, key
    assert isinstance(summary["witness_tick_count"], int)
    assert isinstance(summary["eligible_tick_count"], int)
    assert isinstance(summary["evaluation_phase_sign_inversion_fired"], bool)
    assert isinstance(summary["checksums_match"], bool)


# --------------------------------------------------------------------------- #
# I3 W4 — reproducibility: committed golden + two-layer fidelity anchor
# --------------------------------------------------------------------------- #


async def test_traversal_golden_matches(tmp_path: Path) -> None:
    """I3-G1: the committed golden replay-verifies byte-identical.

    Ollama-free: replays the committed ``decisions.jsonl`` (the JSONL text on
    disk, through the same projection/re-quantisation boundary
    ``scripts/aha_traversal_live_capture.py --verify`` uses) → byte-matches
    the committed ``replay_checksum`` + every artifact SHA-256 + the manifest
    re-render, and re-confirms the W1 route witness. See
    ``scripts.aha_traversal_live_capture.verify`` for the full check list.

    **Hermeticity (M-1 review)**: ``verify()`` writes a firing-annotation side
    file as a matter of course; passing ``annotation_dir=tmp_path`` keeps that
    write out of the **committed** ``tests/fixtures/aha_traversal_golden/``
    directory — a test must never mutate a shared committed fixture (float
    drift there would dirty ``git status`` and could break a
    ``git diff --exit-code``-style CI step). This is asserted directly below
    (a before/after byte snapshot of every committed file), not merely relied
    upon by convention — and it is self-contained (no cross-test execution-order
    dependency, unlike a separate ``git status`` sentinel test would be).

    **Staleness (MEDIUM-2 review)**: hermeticity alone does not prove the
    *committed* ``traversal_firing_annotation.json`` is still correct — only
    that this test's own freshly-generated copy (in ``tmp_path``) never
    overwrote it. Directly byte-compares the freshly-generated annotation
    against the committed one, so a stale committed annotation (regenerated
    upstream but never re-committed) fails loudly here instead of silently
    drifting.
    """
    before = {
        p.name: p.read_bytes() for p in sorted(_GOLDEN_DIR.iterdir()) if p.is_file()
    }

    ok = await _script_verify(_GOLDEN_DIR, annotation_dir=tmp_path)
    assert ok is True
    generated_annotation = tmp_path / "traversal_firing_annotation.json"
    assert generated_annotation.exists()
    committed_annotation = _GOLDEN_DIR / "traversal_firing_annotation.json"
    assert generated_annotation.read_bytes() == committed_annotation.read_bytes(), (
        "committed traversal_firing_annotation.json is stale — regenerate "
        "via `python scripts/aha_traversal_live_capture.py --verify` and "
        "re-commit"
    )

    after = {
        p.name: p.read_bytes() for p in sorted(_GOLDEN_DIR.iterdir()) if p.is_file()
    }
    assert after == before, (
        "verify() must not mutate the committed golden directory "
        f"(changed/added/removed: {set(after) ^ set(before)} plus any byte diff "
        "among shared filenames)"
    )


async def test_traversal_fidelity_anchor_a_matches_run_ecl_loop() -> None:
    """I3-G2 anchor A: ``run_two_phase_capture(knob=None)`` ≡ ``run_ecl_loop``
    — the sibling driver's own fidelity contract (already covered generically
    by ``test_two_phase_live.py``'s ``test_fidelity_default_params`` etc.),
    re-confirmed here specifically for the TRAVERSAL's own inputs (peripatos
    seed + a fresh :class:`ScriptedTraversalChatClient` + the waypoint
    ``observation_factory``) — a combination those existing tests never
    exercise, so this closes the "did my traversal-specific composition
    silently diverge from the documented single-line-differs contract" gap.
    """
    seed_state = traversal_seed_agent_state()
    persona = handoff.golden_persona()

    store_a = MemoryStore(db_path=":memory:")
    store_a.create_schema()
    embedding_a = _mock_embedding()
    try:
        ref = await run_ecl_loop(
            run_id="i3-w4-anchor-a",
            store=store_a,
            embedding=embedding_a,
            llm=RecordReplayChatClient(
                inner=ThinkOffChatClient(ScriptedTraversalChatClient())
            ),
            agent_state=seed_state,
            persona=persona,
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
            n_cognition_ticks=TRAVERSAL_HORIZON,
            physics_ticks_per_cognition=TRAVERSAL_PHYSICS_TICKS_PER_COGNITION,
            observation_factory=traversal_observation_factory(seed_state.agent_id),
        )
    finally:
        await embedding_a.close()
        await store_a.close()

    store_b = MemoryStore(db_path=":memory:")
    store_b.create_schema()
    embedding_b = _mock_embedding()
    try:
        sib = await run_traversal_capture(
            run_id="i3-w4-anchor-a",
            store=store_b,
            embedding=embedding_b,
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
            agent_state=seed_state,
            two_phase_knob=None,
        )
    finally:
        await embedding_b.close()
        await store_b.close()

    assert ref.checksum == sib.checksum
    assert handoff.decisions_to_jsonl(ref.decisions) == handoff.decisions_to_jsonl(
        sib.decisions
    )
    assert ref.rows == sib.rows


_ANCHOR_B_ALLOWLIST_SUFFIXES: tuple[str, ...] = (
    "call.sampling.temperature",
    "call.sampling.top_p",
    "call.sampling.repeat_penalty",
)
"""Leaf paths a knob-on/knob-off decision diff is allowed to touch (I3-G2
anchor B). ``ResolvedSampling`` has exactly these three fields (``inference/\
sampling.py``), so this is the *complete* sampling surface, not a partial
guess."""


def _diff_leaf_paths(a: Any, b: Any, path: str = "") -> list[str]:
    """Recursively collect dotted leaf paths where two JSON-like trees differ.

    Dict keys sorted for determinism; list elements diffed positionally
    (``zip_longest``, ``None``-padded — the two decision lists are asserted
    equal-length by the caller before this is used, so padding never
    actually engages). A leaf is any point where the values are not
    dict/dict or list/list and compare unequal.
    """
    if isinstance(a, dict) and isinstance(b, dict):
        paths: list[str] = []
        for key in sorted(set(a) | set(b)):
            sub = f"{path}.{key}" if path else str(key)
            paths.extend(_diff_leaf_paths(a.get(key), b.get(key), sub))
        return paths
    if isinstance(a, list) and isinstance(b, list):
        paths = []
        for i, (av, bv) in enumerate(zip_longest(a, b)):
            sub = f"{path}[{i}]"
            paths.extend(_diff_leaf_paths(av, bv, sub))
        return paths
    if a != b:
        return [path]
    return []


async def test_traversal_fidelity_anchor_b_knob_diff_confined_to_sampling() -> None:
    """I3-G2 anchor B: toggling the knob (on vs off) on the SAME scripted
    plan/obs changes ONLY the sampling fields (:data:`_ANCHOR_B_ALLOWLIST_SUFFIXES`)
    — every other decision leaf (route/geometry/plan/envelope provenance) is
    byte-identical. A diff leaking outside the allowlist would mean the
    traversal driver's composition diverged from the organ's own behaviour (a
    genuine construction bug — "complicated drift", not a knob modulation),
    the fail mode ``test_traversal_undershoot_fails_route``'s sibling W4
    witness is designed to catch.

    Both runs share the **same** ``run_id`` (``EclRecordMode.substream`` keys
    its micro/tie RNG by ``f"ecl-{run_id}-{agent_id}-{stream}"`` — a different
    ``run_id`` would draw a different jitter sequence and make the geometry
    checksum diverge for a reason unrelated to the knob, defeating this
    anchor; mirrors ``test_two_phase_live.py``'s ``_drive_two_phase`` helper's
    single hardcoded ``run_id`` across its on/off comparisons).
    """
    seed_state = traversal_seed_agent_state()

    store_on = MemoryStore(db_path=":memory:")
    store_on.create_schema()
    embedding_on = _mock_embedding()
    try:
        on_result = await run_traversal_capture(
            run_id="i3-w4-anchor-b",
            store=store_on,
            embedding=embedding_on,
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
            agent_state=seed_state,
            two_phase_knob=TwoPhaseKnob(),
        )
    finally:
        await embedding_on.close()
        await store_on.close()

    store_off = MemoryStore(db_path=":memory:")
    store_off.create_schema()
    embedding_off = _mock_embedding()
    try:
        off_result = await run_traversal_capture(
            run_id="i3-w4-anchor-b",
            store=store_off,
            embedding=embedding_off,
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
            agent_state=seed_state,
            two_phase_knob=None,
        )
    finally:
        await embedding_off.close()
        await store_off.close()

    assert on_result.checksum == off_result.checksum, "geometry must be knob-invariant"

    on_dicts = [handoff.decision_to_dict(d) for d in on_result.decisions]
    off_dicts = [handoff.decision_to_dict(d) for d in off_result.decisions]
    assert len(on_dicts) == len(off_dicts)

    leaked: list[str] = []
    any_allowlisted_diff = False
    for tick, (on_d, off_d) in enumerate(zip(on_dicts, off_dicts, strict=True)):
        for diff_path in _diff_leaf_paths(on_d, off_d):
            if diff_path.endswith(_ANCHOR_B_ALLOWLIST_SUFFIXES):
                any_allowlisted_diff = True
            else:
                leaked.append(f"tick {tick}: {diff_path}")
    assert leaked == [], (
        f"knob-on/off diff leaked outside the sampling allowlist: {leaked}"
    )
    # Non-vacuous: at least one allowlisted field actually differs somewhere —
    # otherwise this test would pass even if the knob silently did nothing.
    assert any_allowlisted_diff, "knob-on/off produced zero diff anywhere (vacuous)"


# --------------------------------------------------------------------------- #
# I4 — real-mode channel exercise (mock-based unit, CI target; real Ollama is
# NEVER touched here — the sealed run is a separate, human-gated session).
# --------------------------------------------------------------------------- #

_FAKE_REAL_DESTINATIONS: tuple[Zone | None, ...] = (
    Zone.AGORA,
    None,
    Zone.GARDEN,
    None,
    Zone.CHASHITSU,
)
"""A deterministic-but-unscripted destination cycle for the mock real-LLM
(I4-G2 unit test): includes ``None`` (stay-put) ticks, and never follows
:data:`TRAVERSAL_ITINERARY` — proving the new ``inner_chat`` injection point
does not require a scripted client, only *some* duck-typed chat client."""


def _mock_real_chat_client() -> OllamaChatClient:
    """An :class:`OllamaChatClient` wired to an in-process ``httpx.MockTransport``
    that cycles through :data:`_FAKE_REAL_DESTINATIONS` — a stand-in for a
    genuinely unscripted qwen3 response (LOW-2 review: unscripted RESPONSE,
    not an unscripted stimulus — the harness still injects the same
    waypoint marker a scripted run would, this mock just answers it however
    it pleases instead of echoing it), never touching a real Ollama server.
    Mirrors this module's/``test_two_phase_live.py``'s ``_mock_embedding``
    idiom, applied to the chat channel instead."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        del request  # cycles through canned responses, never inspects the request
        i = calls["n"] % len(_FAKE_REAL_DESTINATIONS)
        calls["n"] += 1
        dest = _FAKE_REAL_DESTINATIONS[i]
        content = json.dumps(
            {
                "thought": f"mock unscripted-response tick {i}",
                "utterance": None,
                "destination_zone": dest.value if dest is not None else None,
                "animation": "walk" if dest is not None else "idle",
            }
        )
        return httpx.Response(
            httpx.codes.OK,
            json={
                "message": {"content": content},
                "model": "qwen3:8b-mock",
                "eval_count": 1,
                "prompt_eval_count": 1,
                "total_duration": 0,
                "done_reason": "stop",
            },
        )

    return OllamaChatClient(
        client=httpx.AsyncClient(
            base_url=OllamaChatClient.DEFAULT_ENDPOINT,
            transport=httpx.MockTransport(handler),
        )
    )


def _fake_real_vector(text: str) -> list[float]:
    """A deterministic, text-**varying** 768d vector (I4 unit test).

    Unlike this module's constant-vector ``_mock_embedding`` (I1-I3, always
    the same vector regardless of input — adequate there since the mock
    stands in for "an embedding backend exists", never for "genuinely
    semantic retrieval"), this derives from ``sha256(text)`` so DIFFERENT
    texts get DIFFERENT vectors — proving :class:`EmbeddingRecordReplayClient`
    genuinely records/replays *varying*, not merely constant, data. No
    randomisation (``hash()`` would be process-salted); fully reproducible.
    """
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [digest[i % len(digest)] / 255.0 for i in range(EmbeddingClient.DEFAULT_DIM)]


def _mock_real_embedding_client() -> EmbeddingClient:
    """An :class:`EmbeddingClient` wired to ``httpx.MockTransport`` returning
    :func:`_fake_real_vector` per input text — a stand-in for a genuinely
    varying (real nomic-embed-text) backend, never touching real Ollama."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        inputs = body.get("input") or []
        texts = inputs if isinstance(inputs, list) else [inputs]
        vectors = [_fake_real_vector(str(t)) for t in texts]
        return httpx.Response(httpx.codes.OK, json={"embeddings": vectors})

    return EmbeddingClient(
        client=httpx.AsyncClient(
            base_url=EmbeddingClient.DEFAULT_ENDPOINT,
            transport=httpx.MockTransport(handler),
        )
    )


async def test_traversal_real_mode_replay_determinism() -> None:
    """I4-G2: real-mode (mocked) record→replay is byte-deterministic on BOTH
    Plane 1 channels (LLM + embedding) — real Ollama is never touched by this
    test (``httpx.MockTransport`` throughout); only the record/replay
    machinery is under test.

    Uses the new ``run_traversal_capture(inner_chat=...)`` injection point
    (I4) with a genuinely unscripted mock chat client (never
    :class:`ScriptedTraversalChatClient`) + a genuinely varying mock
    embedding wrapped in :class:`EmbeddingRecordReplayClient` (record mode)
    — the real-mode composition ``real_capture`` uses, minus the live
    endpoints.
    """
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    real_chat = _mock_real_chat_client()
    embedding_wrapper = EmbeddingRecordReplayClient(inner=_mock_real_embedding_client())
    seed_state = traversal_seed_agent_state()
    try:
        record_result = await run_traversal_capture(
            run_id="i4-real-mode-determinism",
            store=store,
            embedding=cast("EmbeddingClient", embedding_wrapper),
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
            agent_state=seed_state,
            two_phase_knob=TwoPhaseKnob(),
            inner_chat=real_chat,
        )
    finally:
        await embedding_wrapper.close()
        await real_chat.close()
        await store.close()

    # Record mode genuinely called the (mock) backend on both channels.
    assert embedding_wrapper.inner_invocations > 0
    recorded_embedding = embedding_wrapper.used
    recorded_llm = record_result.replay_calls()

    replay_store = MemoryStore(db_path=":memory:")
    replay_store.create_schema()
    replay_llm = RecordReplayChatClient(recorded=recorded_llm)
    replay_embedding = EmbeddingRecordReplayClient(recorded=recorded_embedding)
    try:
        replay_result = await run_two_phase_capture(
            run_id="i4-real-mode-determinism",
            store=replay_store,
            embedding=cast("EmbeddingClient", replay_embedding),
            llm=replay_llm,
            agent_state=seed_state,
            persona=handoff.golden_persona(),
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
            two_phase_knob=TwoPhaseKnob(),
            n_cognition_ticks=TRAVERSAL_HORIZON,
            physics_ticks_per_cognition=TRAVERSAL_PHYSICS_TICKS_PER_COGNITION,
            observation_factory=traversal_observation_factory(seed_state.agent_id),
        )
    finally:
        await replay_embedding.close()
        await replay_store.close()

    # Replay never touches either "backend" (AC4-equivalent witness, both channels).
    assert replay_llm.inner_invocations == 0
    assert replay_embedding.inner_invocations == 0
    # Byte determinism (I4-G2): record and replay reproduce the identical run.
    assert record_result.checksum == replay_result.checksum
    assert handoff.decisions_to_jsonl(
        record_result.decisions
    ) == handoff.decisions_to_jsonl(replay_result.decisions)
    assert record_result.rows == replay_result.rows


async def test_embedding_record_replay_client_record_then_replay() -> None:
    """Record → replay round-trip: replay serves the quantised vector,
    ``inner_invocations`` stays 0, and exhausting the replay stream raises."""

    class _FakeInner:
        def __init__(self) -> None:
            self.calls = 0

        async def embed_document(self, text: str) -> list[float]:
            del text  # fixed return regardless of input; only call count matters here
            self.calls += 1
            return [0.123_456_789, 0.987_654_321]

        async def close(self) -> None:
            return None

    inner = _FakeInner()
    record_client = EmbeddingRecordReplayClient(inner=inner)
    vec = await record_client.embed_document("hello")
    assert vec == [0.123457, 0.987654]  # 6-decimal quantised
    assert inner.calls == 1
    assert record_client.inner_invocations == 1
    assert record_client.is_replay is False

    replay_client = EmbeddingRecordReplayClient(recorded=record_client.used)
    replay_vec = await replay_client.embed_document("hello")
    assert replay_vec == vec
    assert replay_client.inner_invocations == 0
    assert replay_client.is_replay is True
    assert inner.calls == 1, "replay must never touch the inner client again"

    with pytest.raises(EmbeddingReplayError):
        await replay_client.embed_document("hello again")


async def test_embedding_record_replay_client_embed_many_record_then_replay() -> None:
    """M-1 review (forward-risk completion): ``embed_many`` — the one real
    ``EmbeddingClient`` surface method the record/replay wrapper previously
    lacked (``cognition/cycle.py``'s M11-A individual-layer coherence path
    calls it; the traversal driver itself never enables that layer, so this
    was unreachable-but-silently-so before — now it is tested, not merely
    inert) — records one call per text but ONE inner round-trip for the whole
    batch, and replays deterministically without touching the inner client.
    """
    record_client = EmbeddingRecordReplayClient(inner=_mock_real_embedding_client())
    texts = ["waypoint alpha", "waypoint beta", "waypoint gamma"]
    vectors = await record_client.embed_many(texts, kind="document")
    assert len(vectors) == 3
    assert record_client.inner_invocations == 1, (
        "one HTTP round-trip for the whole batch"
    )
    assert len(record_client.used) == 3, "one recorded call per text"
    # embed_many prepends DOC_PREFIX before the text ever reaches the wire
    # (memory.embedding.EmbeddingClient.embed_many, unmodified) — the expected
    # vector must be derived from the SAME prefixed text the mock transport saw.
    expected = [[round(v, 6) for v in _fake_real_vector(DOC_PREFIX + t)] for t in texts]
    assert vectors == expected

    replay_client = EmbeddingRecordReplayClient(recorded=record_client.used)
    replay_vectors = await replay_client.embed_many(texts, kind="document")
    assert replay_vectors == vectors
    assert replay_client.inner_invocations == 0
    assert replay_client.is_replay is True

    with pytest.raises(EmbeddingReplayError):
        await replay_client.embed_many(["one more text"], kind="document")


async def test_embedding_record_replay_client_record_mode_needs_inner() -> None:
    """A record-mode client with neither ``inner`` nor ``recorded`` fails loudly."""
    client = EmbeddingRecordReplayClient()
    with pytest.raises(EmbeddingReplayError):
        await client.embed_document("anything")


def test_embedding_calls_jsonl_round_trip_is_byte_deterministic() -> None:
    """LOW-1 review (real-spend safety): the script's I4 real-mode
    serialization pair — ``_embedding_calls_to_jsonl`` /
    ``_embedding_calls_from_jsonl`` — round-trips a
    :class:`RecordedEmbeddingCall` list byte-deterministically. No test
    exercised these before (real Ollama is never touched here — pure
    serialize/parse over synthetic calls); this catches a serialization bug
    before it would surface mid a ratified real-spend session.
    """
    calls = (
        RecordedEmbeddingCall(
            kind="embed_query", text="peripatos", vector=(0.1, 0.2, 0.300001)
        ),
        RecordedEmbeddingCall(
            kind="embed_document",
            text="waypoint 1: proceed to agora",
            vector=(-0.5, 0.999999, 0.0),
        ),
        RecordedEmbeddingCall(kind="embed", text="", vector=()),
    )

    jsonl_a = _embedding_calls_to_jsonl(calls)
    parsed = tuple(_embedding_calls_from_jsonl(jsonl_a))
    assert parsed == calls

    # Byte-deterministic re-render: parsing then re-serialising the SAME
    # calls reproduces the identical JSONL text (canonical_dumps discipline).
    jsonl_b = _embedding_calls_to_jsonl(parsed)
    assert jsonl_b == jsonl_a

    # Empty input round-trips to an empty string, not a spurious line.
    assert _embedding_calls_to_jsonl(()) == ""
    assert _embedding_calls_from_jsonl("") == []


# --------------------------------------------------------------------------- #
# I4 — channel-exercise witness (honest count annotation, non-gate)
# --------------------------------------------------------------------------- #


def test_traversal_channel_exercise_summary_is_non_gate() -> None:
    """I4-G4: the channel-exercise summary is a plain count annotation — no
    ``>=K`` threshold, ``verdict=None``, ``hard_gate=False`` — and honestly
    reports a settled (zero-move) run rather than hiding it."""
    settled_rows = tuple(_fake_row(t, Zone.PERIPATOS) for t in range(3))
    settled_result = EclRunResult(
        run_id="fake", rows=settled_rows, decisions=(), checksum="deadbeef"
    )
    summary = traversal_channel_exercise_summary(settled_result)
    assert summary["hard_gate"] is False
    assert summary["verdict"] is None
    assert summary["settled_no_movement"] is True
    assert summary["move_tick_count"] == 0
    assert summary["distinct_zone_count"] == 1
    for key in summary:
        assert key.lower() not in _TRAVERSAL_BANNED_EXACT, key

    moved_rows = (
        _fake_row(0, Zone.PERIPATOS),
        _fake_row(1, Zone.AGORA),
        _fake_row(2, Zone.AGORA),
    )
    moved_result = EclRunResult(
        run_id="fake", rows=moved_rows, decisions=(), checksum="deadbeef"
    )
    moved_summary = traversal_channel_exercise_summary(moved_result)
    assert moved_summary["settled_no_movement"] is False
    assert moved_summary["move_tick_count"] == 1
    assert moved_summary["distinct_zone_count"] == 2


def test_real_mode_experiments_scaffold_exists_and_is_honest() -> None:
    """I4: the experiments scaffold exists (env.md / run.ps1 / repro.ps1 /
    repro.sh) — the binding artifact a diagnostic-only "code path exists"
    claim must not skip — and honestly documents the BLOCKED (spend-ratify
    pending) status rather than fabricating a real-run artifact bundle."""
    exp = _REPO_ROOT / "experiments" / "20260723-aha-traversal-real"
    for name in ("env.md", "run.ps1", "repro.ps1", "repro.sh"):
        assert (exp / name).exists(), f"missing experiments scaffold: {name}"
    env_text = (exp / "env.md").read_text(encoding="utf-8")
    assert "BLOCKED" in env_text
    assert "spend ratify" in env_text
    # No fabricated real-run artifact bundle committed alongside the scaffold.
    assert not (exp / "artifacts" / "manifest.json").exists()
