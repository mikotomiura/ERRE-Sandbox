"""Issue 006 (M13 live-loop-closure): W-live correlation-id reachability witness.

Covers ``.steering/20260724-m13-live-loop-closure/design-final.md`` Issue
006's four Acceptance Criteria (as amended by the TASK-POST cross-review
fold-in, ``decisions.md`` "TASK-POST cross-review 採否"):

* AC1 -- a single correlation-id reaches all five ADR seams
  (``perturbation`` -> ``perception`` -> ``capture`` -> ``firing_summary`` ->
  ``same_tick_envelope_observed``), each boolean ``True``. The last two are
  TICK-LEVEL co-occurrence, not per-correlation causation (Codex TASK-POST
  HIGH-2 -- correlation-id never reaches the outbound wire protocol, grill
  G2) -- true here specifically because this drive injects exactly one
  perturbation per tick
  -> :func:`test_correlation_id_reaches_each_seam`.
* AC2 -- no double-send: the ledger's own per-kind envelope multiset equals
  the actual broadcast queue's per-kind multiset (HIGH-1, generalized to
  every envelope kind by Codex TASK-POST MED-1, not just ``MoveMsg``)
  -> :func:`test_no_double_send_boolean`.
* AC3 -- the eligible-tick / sign-inversion counts come from the
  **UNMODIFIED** ``two_phase_live.two_phase_firing_summary`` (reused, never
  re-implemented) -- but, since Codex TASK-POST HIGH-1, the full result is no
  longer embedded back into the witness verbatim (only its two plain int
  counts are)
  -> :func:`test_eligible_sign_inversion_count_reuses_firing_summary`.
* AC4 -- the summary carries an explicit ``verdict: None`` marker and no
  returned key names an effect/divergence/detectability/aha claim (honest,
  measurement non-reentrant)
  -> :func:`test_witness_emits_no_measurement`.

**W-live (binding, design-final.md DA-4/HIGH-2, honest framing)**: this
module's witness asserts REACHABILITY only -- "wiring reached each seam" --
never effect / caused / aha / divergence / detectability, and (Codex
TASK-POST HIGH-2) never claims uniform per-correlation causation past the
``capture`` seam -- the last two seams are tick-level co-occurrence. organ
(``two_phase_live.two_phase_firing_summary``) is imported and driven, never
modified; ``live_loop.py`` (Issue 003's composition root) is likewise driven
via its public API, never re-implemented here.

Ollama-free throughout -- every test drives Ollama-free record/spy chat
clients (the same ``_MockInnerChat`` idiom ``test_live_loop.py`` /
``test_two_phase_live.py`` establish; duplicated locally per those modules'
own note that test files are not a shared-code surface).
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, cast

import httpx

from erre_sandbox.erre.two_phase import TwoPhaseKnob
from erre_sandbox.integration.embodied import handoff, live_loop
from erre_sandbox.integration.embodied.live import ThinkOffChatClient
from erre_sandbox.integration.embodied.live_v1 import SamplingSpyChatClient
from erre_sandbox.integration.embodied.loop import RecordReplayChatClient
from erre_sandbox.integration.embodied.two_phase_live import (
    evaluation_seeded_agent_state,
    run_two_phase_capture,
    two_phase_firing_summary,
)
from erre_sandbox.integration.inbound import InboundSink
from erre_sandbox.memory import EmbeddingClient, MemoryStore
from erre_sandbox.schemas import WorldPerturbationMsg, Zone
from erre_sandbox.world import ManualClock

if TYPE_CHECKING:
    from erre_sandbox.inference.ollama_adapter import ChatResponse
    from erre_sandbox.integration.embodied.loop import RecordedLlmCall

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIVE_LOOP_SRC = (
    _REPO_ROOT / "src" / "erre_sandbox" / "integration" / "embodied" / "live_loop.py"
)

_FIXED_CLOCK = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

# Enough ticks for the EMA lambda to climb above 0 (mirrors
# test_two_phase_live.py's `_TEST_TICKS = 8`, "enough for movement so the EMA
# lambda climbs above 0" -- the same golden plan / mechanics, only the
# observation-injection channel differs here).
_N_TICKS: Final[int] = 8
_PHYSICS_TICKS: Final[int] = 2


# --------------------------------------------------------------------------- #
# Ollama-free fixtures (mirrors test_live_loop.py's idiom, not shared)
# --------------------------------------------------------------------------- #


def _mock_embedding() -> EmbeddingClient:
    """Constant-vector embedding (Ollama-free)."""
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


class _MockInnerChat:
    """Ollama-free inner chat that re-serves the golden plan every call."""

    def __init__(self) -> None:
        resp = handoff.golden_recorded_calls()[0].response
        assert resp is not None
        self._response = resp

    async def chat(self, *_args: Any, **_kwargs: Any) -> ChatResponse:
        return self._response


def _record_llm() -> RecordReplayChatClient:
    return RecordReplayChatClient(inner=ThinkOffChatClient(_MockInnerChat()))


def _perturbation(*, agent_id: str, tick: int) -> WorldPerturbationMsg:
    return WorldPerturbationMsg(
        tick=0,
        target_agent_id=agent_id,
        modality="sight",
        source_zone=Zone.STUDY,
        content=f"witness perturbation {tick}",
        intensity=0.4,
        correlation_id=f"witness-corr-{tick}",
    )


# --------------------------------------------------------------------------- #
# Drive helper: live_loop capture (knob-on, evaluation-seeded, per-tick corr-id)
# --------------------------------------------------------------------------- #


async def _drive_capture() -> tuple[
    live_loop.LiveLoopWorld, live_loop.LiveLoopCaptureResult
]:
    """Drive the closure root with one perturbation per tick (distinct corr-ids).

    ``evaluation_seeded_agent_state()`` + ``TwoPhaseKnob()`` mirrors
    ``test_two_phase_live.py``'s ``test_firing_evaluation_sign_inversion``
    recipe (the proven "EMA lambda climbs, evaluation-phase sign inversion
    fires" combination) -- only the observation-injection channel differs
    (inbound sink here vs. a fixed ``observation_factory`` there).
    """
    agent_state = evaluation_seeded_agent_state()
    persona = handoff.golden_persona()
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    try:
        handle = live_loop.build_live_loop_world(
            run_id="live-loop-witness-test",
            store=store,
            embedding=embedding,
            llm=_record_llm(),
            agent_state=agent_state,
            persona=persona,
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
            two_phase_knob=TwoPhaseKnob(),
            clock=ManualClock(start=0.0),
        )
        sink = InboundSink()
        for tick in range(_N_TICKS):
            sink.push(_perturbation(agent_id=agent_state.agent_id, tick=tick))
        # max_drain_per_tick=1: preloaded push order == tick order, so draining
        # exactly 1 per tick keeps a distinct corr-id on every single tick.
        capture = await live_loop.run_live_loop_capture(
            handle,
            inbound_sink=sink,
            n_cognition_ticks=_N_TICKS,
            physics_ticks_per_cognition=_PHYSICS_TICKS,
            max_drain_per_tick=1,
        )
    finally:
        await embedding.close()
        await store.close()
    return handle, capture


async def _spied_replay(
    *, recorded: list[RecordedLlmCall], knob: TwoPhaseKnob | None
) -> tuple[list[Any], str]:
    """Replay ``recorded`` committed decisions through a sampling spy (on/off).

    Mirrors ``test_two_phase_live.py``'s ``_spied_replay`` -- the same
    knob-on/knob-off spied-replay recipe ``two_phase_firing_summary`` is
    built for. ``n_cognition_ticks=len(recorded)`` (not a fixed constant) so
    this replays exactly as many ticks as ``recorded`` actually holds --
    callers driving a shorter/longer capture than ``_N_TICKS`` (e.g. the
    empty-perturbation negative control) still replay cleanly instead of
    exhausting the replay client early.
    """
    agent_state = evaluation_seeded_agent_state()
    persona = handoff.golden_persona()
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    spy = SamplingSpyChatClient(RecordReplayChatClient(recorded=recorded))
    try:
        result = await run_two_phase_capture(
            run_id="live-loop-witness-test",
            store=store,
            embedding=embedding,
            llm=cast("RecordReplayChatClient", spy),
            agent_state=agent_state,
            persona=persona,
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
            two_phase_knob=knob,
            n_cognition_ticks=len(recorded),
            physics_ticks_per_cognition=_PHYSICS_TICKS,
        )
    finally:
        await embedding.close()
        await store.close()
    return list(spy.sampled), result.checksum


async def _firing_summary_for(
    capture: live_loop.LiveLoopCaptureResult,
) -> dict[str, Any]:
    """Compute ``two_phase_firing_summary`` (UNMODIFIED, imported) for ``capture``.

    Reuses the committed decisions ``capture`` itself produced (round-tripped
    through JSONL, the same idiom ``test_two_phase_live.py`` uses) so the
    on/off spied replays cover the SAME committed decisions the live-loop
    drive actually served -- no re-implementation of the firing witness.
    """
    recorded = handoff.recorded_calls_from_jsonl(
        handoff.decisions_to_jsonl(capture.ecl.decisions)
    )
    on_sampling, on_ck = await _spied_replay(recorded=recorded, knob=TwoPhaseKnob())
    off_sampling, off_ck = await _spied_replay(recorded=recorded, knob=None)
    return two_phase_firing_summary(
        on_samplings=on_sampling,
        off_samplings=off_sampling,
        on_checksum=on_ck,
        off_checksum=off_ck,
        committed_call_samplings=[c.sampling for c in recorded],
    )


def _broadcast_envelope_kinds(handle: live_loop.LiveLoopWorld) -> list[str]:
    """Drain the world's broadcast queue and return each envelope's ``.kind``.

    Must be called exactly once per drive (draining empties the queue) --
    the real broadcast-path kind multiset :func:`wiring_reachability_summary`'s
    ``no_double_send`` check compares against the ledger's own reflection of
    ``result.envelopes`` (Codex TASK-POST MED-1: every kind, not just
    ``MoveMsg``).
    """
    drained = handle.world.drain_envelopes()
    return [env.kind for env in drained]


# --------------------------------------------------------------------------- #
# AC1 -- correlation-id reaches every seam
# --------------------------------------------------------------------------- #


async def test_correlation_id_reaches_each_seam() -> None:
    """AC1: every injected corr-id reaches all five ADR seams (到達性), True."""
    handle, capture = await _drive_capture()
    firing_summary = await _firing_summary_for(capture)
    broadcast_kinds = _broadcast_envelope_kinds(handle)

    summary = live_loop.wiring_reachability_summary(
        capture,
        firing_summary=firing_summary,
        broadcast_envelope_kinds=broadcast_kinds,
    )

    assert capture.injected, "sanity: perturbations were actually injected"
    assert len(capture.injected) == _N_TICKS
    for inj in capture.injected:
        seams = summary["per_correlation_id"][inj.correlation_id]
        assert seams["perturbation"] is True, inj.correlation_id
        assert seams["perception"] is True, inj.correlation_id
        assert seams["capture"] is True, inj.correlation_id
        # Codex TASK-POST HIGH-2: "firing_summary" / "same_tick_envelope_observed"
        # are tick-level co-occurrence, not per-correlation causation (see
        # wiring_reachability_summary's docstring) -- still True here because
        # this drive injects exactly one perturbation per tick (max_drain_per_tick=1).
        assert seams["firing_summary"] is True, inj.correlation_id
        assert seams["same_tick_envelope_observed"] is True, inj.correlation_id
        assert seams["all_seams_reached"] is True, inj.correlation_id

    assert summary["all_correlation_ids_reach_all_seams"] is True
    assert summary["perturbation_count"] == len(capture.injected)
    assert summary["target_agent_mismatch_count"] == 0


async def test_reachability_false_when_no_perturbation_injected() -> None:
    """Negative control: with zero injected perturbations, reachability is
    vacuously False (never a misleading trivial True), and the loop still
    completes end-to-end (no exception) -- honest boolean, not a fudge."""
    agent_state = evaluation_seeded_agent_state()
    persona = handoff.golden_persona()
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    try:
        handle = live_loop.build_live_loop_world(
            run_id="live-loop-witness-empty-test",
            store=store,
            embedding=embedding,
            llm=_record_llm(),
            agent_state=agent_state,
            persona=persona,
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
            two_phase_knob=TwoPhaseKnob(),
            clock=ManualClock(start=0.0),
        )
        capture = await live_loop.run_live_loop_capture(
            handle,
            inbound_sink=InboundSink(),
            n_cognition_ticks=2,
            physics_ticks_per_cognition=_PHYSICS_TICKS,
        )
    finally:
        await embedding.close()
        await store.close()

    assert capture.injected == ()
    firing_summary = await _firing_summary_for(capture)
    broadcast_kinds = _broadcast_envelope_kinds(handle)
    summary = live_loop.wiring_reachability_summary(
        capture,
        firing_summary=firing_summary,
        broadcast_envelope_kinds=broadcast_kinds,
    )
    assert summary["per_correlation_id"] == {}
    assert summary["all_correlation_ids_reach_all_seams"] is False
    assert summary["perturbation_count"] == 0


# --------------------------------------------------------------------------- #
# AC2 -- no double-send (HIGH-1)
# --------------------------------------------------------------------------- #


async def test_no_double_send_boolean() -> None:
    """AC2: no_double_send is True -- the ledger's per-kind envelope multiset
    matches the actual broadcast queue (Codex TASK-POST MED-1: every kind,
    not just MoveMsg), and the source never calls inject_envelope."""
    handle, capture = await _drive_capture()
    firing_summary = await _firing_summary_for(capture)
    broadcast_kinds = _broadcast_envelope_kinds(handle)

    summary = live_loop.wiring_reachability_summary(
        capture,
        firing_summary=firing_summary,
        broadcast_envelope_kinds=broadcast_kinds,
    )

    assert summary["no_double_send"] is True
    assert summary["envelope_kind_counts"]["move"] == broadcast_kinds.count("move")
    assert summary["envelope_kind_counts"]["move"] > 0, (
        "sanity: the golden plan produces a MoveMsg most/every tick"
    )
    # Multiset equality (Codex TASK-POST MED-1) covers every kind, not just
    # move -- pin the full comparison, not just the move slice.
    assert summary["envelope_kind_counts"] == dict(Counter(broadcast_kinds))

    # Structural pin (HIGH-1, mirrors test_live_loop.py::
    # test_single_move_broadcast_no_double_send): the closure root never
    # re-injects outbound -- checks for an actual CALL, not the bare
    # identifier (which legitimately appears in explanatory docstrings).
    src = _LIVE_LOOP_SRC.read_text(encoding="utf-8")
    assert "inject_envelope(" not in src, (
        "live_loop.py must never call inject_envelope (HIGH-1: double-send)"
    )


# --------------------------------------------------------------------------- #
# AC3 -- eligible / sign-inversion counts reuse two_phase_firing_summary
# --------------------------------------------------------------------------- #


async def test_eligible_sign_inversion_count_reuses_firing_summary() -> None:
    """AC3: the eligible-tick / witness-tick counts are read off the
    UNMODIFIED ``two_phase_firing_summary`` result (identity, not recompute)."""
    handle, capture = await _drive_capture()
    firing_summary = await _firing_summary_for(capture)
    broadcast_kinds = _broadcast_envelope_kinds(handle)

    summary = live_loop.wiring_reachability_summary(
        capture,
        firing_summary=firing_summary,
        broadcast_envelope_kinds=broadcast_kinds,
    )

    # Codex TASK-POST HIGH-1: the summary no longer embeds the full
    # two_phase_firing_summary result back verbatim (that per-tick sampling
    # detail is measurement detail this witness has no business re-exposing
    # under a reachability-only contract) -- pin the removal directly.
    assert "firing_summary_detail" not in summary
    # What DOES survive is exactly the two plain int counts this witness
    # actually needs, read straight off the caller-supplied firing_summary
    # (reuse, not recompute -- the counts could only match by construction
    # if this function is genuinely reading them off the same object).
    assert summary["eligible_tick_count"] == firing_summary["eligible_tick_count"]
    assert (
        summary["sign_inversion_witness_tick_count"]
        == firing_summary["witness_tick_count"]
    )

    # The proven recipe (evaluation_seeded_agent_state + TwoPhaseKnob(),
    # N=8 ticks) actually fires -- otherwise AC1's seam4 check would be
    # vacuous (no eligible tick to correlate against).
    assert firing_summary["evaluation_phase_sign_inversion_fired"] is True
    assert summary["eligible_tick_count"] >= 1
    assert summary["sign_inversion_witness_tick_count"] >= 1


# --------------------------------------------------------------------------- #
# AC4 -- verdict=None marker, no effect/divergence/detectability/aha key
# --------------------------------------------------------------------------- #

_FORBIDDEN_KEY_SUBSTRINGS: Final[tuple[str, ...]] = (
    "effect",
    "divergence",
    "detectability",
    "aha",
    "caused",
    "emergence",
)
"""Words forbidden as returned-dict KEYS (design-final.md §2, honest
framing). Checked against KEYS only, never prose values -- ``summary["note"]``
itself legitimately *negates* some of these words when explaining what is
NOT measured (the same convention ``two_phase_live.py`` /
``test_live_loop_golden.py`` use), so a text-value scan would
false-positive on that honest negation. (Prior to the Codex TASK-POST
HIGH-1 fold-in, this rationale also covered the now-removed
``firing_summary_detail`` payload's own ``note`` field for the same
reason.)"""


def _walk_keys(obj: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(key, str):
                keys.append(key)
            keys.extend(_walk_keys(value))
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            keys.extend(_walk_keys(item))
    return keys


async def test_witness_emits_no_measurement() -> None:
    """AC4: verdict=None marker; no effect/divergence/detectability/aha key
    anywhere in the (recursively-walked) summary structure -- honest,
    measurement non-reentrant."""
    handle, capture = await _drive_capture()
    firing_summary = await _firing_summary_for(capture)
    broadcast_kinds = _broadcast_envelope_kinds(handle)

    summary = live_loop.wiring_reachability_summary(
        capture,
        firing_summary=firing_summary,
        broadcast_envelope_kinds=broadcast_kinds,
    )

    assert summary["verdict"] is None
    # Codex TASK-POST HIGH-1: firing_summary_detail is no longer embedded at
    # all -- the walk below over `summary` therefore never touches
    # `firing_summary`'s own (separately-verdict-None) structure. Sanity
    # check the input directly instead, since it is no longer reachable
    # through `summary`.
    assert firing_summary["verdict"] is None

    all_keys = _walk_keys(summary)
    assert all_keys, "sanity: the summary is non-trivially nested"
    for key in all_keys:
        lowered = key.lower()
        for forbidden in _FORBIDDEN_KEY_SUBSTRINGS:
            assert forbidden not in lowered, (
                f"forbidden key substring {forbidden!r} found in key {key!r} "
                "(honest framing: reachability summary must not name an "
                "effect/causal claim)"
            )
