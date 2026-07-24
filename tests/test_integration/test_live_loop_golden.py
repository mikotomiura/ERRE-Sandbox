"""Issue 004 (M13 live-loop-closure): Plane G — capture -> unmodified
``run_two_phase_capture`` replay byte-parity golden.

Covers ``.steering/20260724-m13-live-loop-closure/design-final.md``
Issue 004's four Acceptance Criteria:

* AC1 -- a live_loop capture replayed through the **unmodified**
  ``run_two_phase_capture`` reproduces a byte-identical
  ``ecl_trace_checksum``, touching neither the LLM nor the embedding
  channel a second time
  -> :func:`test_capture_replay_checksum_byte_parity`.
* AC2 -- the emitted floats this golden depends on (the per-tick sampling
  triple + the running ``locomotion.lam``) are stable at the 6-decimal
  quantisation boundary
  -> :func:`test_quantised_floats_stable`.
* AC3 -- the committed golden fixture (``tests/fixtures/live_loop_golden/``)
  is reproduced byte-for-byte by a fresh re-bake
  -> :func:`test_golden_fixture_deterministic`.
* AC4 -- this golden's role is pinned as a **regression guard**, never a
  closure witness (design-final.md MEDIUM-3)
  -> :func:`test_golden_role_is_regression_guard`.

**W-golden vs. W-live (binding, MEDIUM-3, honest framing)**: this module
proves the closure root's capture is a *faithful, re-derivable* input to the
untouched sibling driver -- organ-path non-destructiveness / deterministic
reconstructability. It does **not** prove "the live loop closed"; that is
W-live's job (a later issue). No floor / verdict / divergence / magnitude /
detectability / aha-proxy statistic is computed or asserted anywhere in this
module -- only exact-match / boolean / structural checks (mirrors
``test_live_loop.py``'s scope guard).

Ollama-free throughout -- both the LLM and the embedding channel run behind
record/replay wrappers over ``httpx.MockTransport`` (the same idiom
``test_live_loop.py`` / ``test_traversal_live.py`` establish; duplicated
locally per those modules' own note that test files are not a shared-code
surface). Organ (``run_two_phase_capture``, ``cognition/cycle.py``,
``world/tick.py``) is imported and driven, never modified.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, cast

import httpx

from erre_sandbox.erre.two_phase import TwoPhaseKnob
from erre_sandbox.integration.embodied import handoff, live_loop
from erre_sandbox.integration.embodied.live import ThinkOffChatClient
from erre_sandbox.integration.embodied.loop import RecordReplayChatClient
from erre_sandbox.integration.embodied.traversal_live import EmbeddingRecordReplayClient
from erre_sandbox.integration.embodied.two_phase_live import (
    evaluation_seeded_agent_state,
    quantise_sampling,
    run_two_phase_capture,
)
from erre_sandbox.integration.inbound import InboundSink
from erre_sandbox.memory import EmbeddingClient, MemoryStore
from erre_sandbox.schemas import WorldPerturbationMsg, Zone

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.inference.ollama_adapter import ChatResponse
    from erre_sandbox.integration.embodied.loop import EclRunResult, RecordedLlmCall
    from erre_sandbox.integration.embodied.traversal_live import RecordedEmbeddingCall

from erre_sandbox.world import ManualClock

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "live_loop_golden"

_FIXED_CLOCK = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

# Sealed-shape constants -- deliberately small (this is a regression guard's
# reference case, not a sealed-run horizon; I7's real-qwen3 live run is a
# separate, spend-gated issue).
_RUN_ID: Final[str] = "live-loop-golden-i4"
_SEED: Final[int] = 0
_N_TICKS: Final[int] = 4
_PHYSICS_TICKS: Final[int] = 4


# --------------------------------------------------------------------------- #
# AC4 -- role marker (regression guard, never a closure witness, MEDIUM-3)
# --------------------------------------------------------------------------- #

GOLDEN_ROLE_NOTE: Final[str] = (
    "regression guard: capture replayed through the UNMODIFIED "
    "run_two_phase_capture reproduces a byte-identical ecl_trace_checksum "
    "(organ-path non-destructiveness / deterministic reconstructability). "
    "This is NOT a witness that the live loop closed -- that is W-live's "
    "job (a later issue), never this module's."
)
"""The FROZEN role text (design-final.md MEDIUM-3). Single source of truth:
the committed fixture's ``manifest.json["role"]`` field must equal this
string verbatim (see :func:`test_golden_role_is_regression_guard`)."""

_FORBIDDEN_OVERCLAIM_SUBSTRINGS: Final[tuple[str, ...]] = (
    "caused",
    "effect",
    "emergence",
    "closure proof",
)
"""Words the ADR (design-final.md §2) forbids reading as "the loop closed" /
"aha happened here" -- checked against :data:`GOLDEN_ROLE_NOTE` only (not
this module's free-form prose, which legitimately *negates* these words when
explaining what is NOT claimed, the same way the organ modules' own
docstrings do)."""


# --------------------------------------------------------------------------- #
# Ollama-free fixtures (mirrors test_live_loop.py's idiom, not shared)
# --------------------------------------------------------------------------- #


def _mock_embedding() -> EmbeddingClient:
    """Constant-vector embedding backend (Ollama-free)."""
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


def _perturbation(*, agent_id: str, tick: int) -> WorldPerturbationMsg:
    return WorldPerturbationMsg(
        tick=0,
        target_agent_id=agent_id,
        modality="sight",
        source_zone=Zone.STUDY,
        content=f"live-loop golden perturbation {tick}",
        intensity=0.4,
        correlation_id=f"golden-corr-{tick}",
    )


def _final_lam(handle: live_loop.LiveLoopWorld) -> float:
    """The seeded agent's running ``locomotion.lam`` after the drive completes.

    Reads the same private ``WorldRuntime._agents`` seam
    ``two_phase_live.run_two_phase_capture`` itself reads
    (``two_phase_live.py:265``) -- ``tests/**`` has ``SLF001`` disabled
    (``pyproject.toml``), so no ``noqa`` is needed here.
    """
    state = handle.world._agents[handle.agent_id].state
    assert state.locomotion is not None, (
        "evaluation_seeded_agent_state always arms locomotion"
    )
    return state.locomotion.lam


# --------------------------------------------------------------------------- #
# Capture (record) / replay builders
# --------------------------------------------------------------------------- #


async def _run_capture() -> tuple[
    live_loop.LiveLoopWorld,
    live_loop.LiveLoopCaptureResult,
    EmbeddingRecordReplayClient,
]:
    """Drive the closure root (I3) with record-mode LLM + embedding wrappers.

    Returns the handle (so callers can inspect ``handle.llm.used`` /
    ``handle.world``'s post-drive agent state), the capture result, and the
    embedding wrapper (so callers can read its ``.used`` recorded stream --
    closing it does not clear that in-memory list).
    """
    agent_state = evaluation_seeded_agent_state()
    persona = handoff.golden_persona()
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding_wrapper = EmbeddingRecordReplayClient(inner=_mock_embedding())
    llm = RecordReplayChatClient(inner=ThinkOffChatClient(_MockInnerChat()))
    try:
        handle = live_loop.build_live_loop_world(
            run_id=_RUN_ID,
            store=store,
            embedding=cast("EmbeddingClient", embedding_wrapper),
            llm=llm,
            agent_state=agent_state,
            persona=persona,
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
            two_phase_knob=TwoPhaseKnob(),
            seed=_SEED,
            clock=ManualClock(start=0.0),
        )
        sink = InboundSink()
        for tick in range(_N_TICKS):
            sink.push(_perturbation(agent_id=agent_state.agent_id, tick=tick))
        # max_drain_per_tick=1: the sink is preloaded with all N perturbations
        # up front (push order == tick order), so draining exactly 1 per tick
        # keeps tick alignment 1:1 with the perturbation index (mirrors
        # test_live_loop.py's AC1 fidelity test).
        capture = await live_loop.run_live_loop_capture(
            handle,
            inbound_sink=sink,
            n_cognition_ticks=_N_TICKS,
            physics_ticks_per_cognition=_PHYSICS_TICKS,
            max_drain_per_tick=1,
        )
    finally:
        await embedding_wrapper.close()
        await store.close()
    return handle, capture, embedding_wrapper


async def _run_replay(
    *,
    capture: live_loop.LiveLoopCaptureResult,
    llm_used: Sequence[RecordedLlmCall],
    embedding_used: Sequence[RecordedEmbeddingCall],
) -> tuple[EclRunResult, RecordReplayChatClient, EmbeddingRecordReplayClient]:
    """Replay ``capture`` through the UNMODIFIED ``run_two_phase_capture``.

    Pure re-use: ``capture.observation_factory()`` (I3) rebuilds the fixed
    per-tick observation feed, and both record streams are replayed --
    zero touches of either the LLM or the embedding backend (AC1/AC4-
    equivalent witness).
    """
    agent_state = evaluation_seeded_agent_state()
    persona = handoff.golden_persona()
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    replay_llm = RecordReplayChatClient(recorded=llm_used)
    replay_embedding = EmbeddingRecordReplayClient(recorded=embedding_used)
    try:
        result = await run_two_phase_capture(
            run_id=_RUN_ID,
            store=store,
            embedding=cast("EmbeddingClient", replay_embedding),
            llm=replay_llm,
            agent_state=agent_state,
            persona=persona,
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
            two_phase_knob=TwoPhaseKnob(),
            seed=_SEED,
            n_cognition_ticks=_N_TICKS,
            physics_ticks_per_cognition=_PHYSICS_TICKS,
            observation_factory=capture.observation_factory(),
        )
    finally:
        await replay_embedding.close()
        await store.close()
    return result, replay_llm, replay_embedding


def _render_fixture(
    *, capture: live_loop.LiveLoopCaptureResult, replay_checksum: str
) -> dict[str, str]:
    """Render the golden fixture's three files from a capture (+ its replay).

    Reuses ``handoff.decisions_to_jsonl`` / ``handoff.trace_rows_to_jsonl`` /
    ``handoff.canonical_dumps`` (the existing canonicalisation this package's
    other golden tests already depend on) so this fixture's byte-stability
    rests on the SAME 6-decimal-quantised canonical JSON rules
    (``feedback_golden_crossplatform_float_drift``), never a bespoke one.
    """
    decisions_jsonl = handoff.decisions_to_jsonl(capture.ecl.decisions)
    ecl_trace_jsonl = handoff.trace_rows_to_jsonl(capture.ecl.rows)
    manifest = {
        "run_id": _RUN_ID,
        "seed": _SEED,
        "n_cognition_ticks": _N_TICKS,
        "physics_ticks_per_cognition": _PHYSICS_TICKS,
        "capture_checksum": capture.checksum,
        "replay_checksum": replay_checksum,
        "decisions_sha256": hashlib.sha256(decisions_jsonl.encode("utf-8")).hexdigest(),
        "ecl_trace_sha256": hashlib.sha256(ecl_trace_jsonl.encode("utf-8")).hexdigest(),
        "role": GOLDEN_ROLE_NOTE,
        "verdict": None,
        "note": (
            "Issue 004 (Plane G) regression golden -- Ollama-free capture "
            "(closure root, I3) replayed through the unmodified "
            "run_two_phase_capture (organ). Proves organ-path "
            "reconstructability, never that the live loop closed."
        ),
    }
    manifest_text = handoff.canonical_dumps(manifest) + "\n"
    return {
        "decisions.jsonl": decisions_jsonl,
        "ecl_trace.jsonl": ecl_trace_jsonl,
        "manifest.json": manifest_text,
    }


# --------------------------------------------------------------------------- #
# AC1 -- capture -> unmodified run_two_phase_capture replay, byte-parity
# --------------------------------------------------------------------------- #


async def test_capture_replay_checksum_byte_parity() -> None:
    """AC1: replaying a live_loop capture through the UNMODIFIED
    ``run_two_phase_capture`` reproduces the SAME ``ecl_trace_checksum``
    byte-for-byte, with zero inner LLM/embedding calls on the replay side."""
    handle, capture, embedding_wrapper = await _run_capture()
    replay, replay_llm, replay_embedding = await _run_replay(
        capture=capture,
        llm_used=handle.llm.used,
        embedding_used=embedding_wrapper.used,
    )

    assert replay_llm.inner_invocations == 0, "replay must never touch a live LLM"
    assert replay_embedding.inner_invocations == 0, (
        "replay must never touch a live embedding backend"
    )
    assert replay.checksum == capture.checksum, (
        "W-golden regression guard: replaying the capture through the "
        "UNMODIFIED run_two_phase_capture must reproduce the SAME "
        "ecl_trace_checksum byte-for-byte"
    )
    assert handoff.decisions_to_jsonl(replay.decisions) == (
        handoff.decisions_to_jsonl(capture.ecl.decisions)
    )
    assert replay.rows == capture.ecl.rows


# --------------------------------------------------------------------------- #
# AC2 -- quantised-float stability (sampling triple + locomotion.lam)
# --------------------------------------------------------------------------- #


async def test_quantised_floats_stable() -> None:
    """AC2: the per-tick sampling triple (temperature/top_p/repeat_penalty)
    and the running ``locomotion.lam`` are stable at the 6-decimal
    quantisation boundary -- a second quantisation pass is a no-op, and two
    independent capture runs over the SAME inputs land on identical
    quantised values (``feedback_golden_crossplatform_float_drift``'s rule,
    exercised here rather than merely asserted)."""
    handle_a, capture_a, _emb_a = await _run_capture()
    handle_b, capture_b, _emb_b = await _run_capture()

    assert capture_a.checksum == capture_b.checksum, (
        "two independent capture runs over identical inputs must be "
        "byte-identical before their quantised floats can be compared"
    )

    triples_a = [quantise_sampling(c.sampling) for c in handle_a.llm.used]
    triples_b = [quantise_sampling(c.sampling) for c in handle_b.llm.used]
    assert triples_a == triples_b
    assert len(triples_a) == _N_TICKS
    for triple in triples_a:
        # Idempotent at the quantisation boundary: a second round-trip is a no-op.
        assert tuple(round(v, 6) for v in triple) == triple

    lam_a = _final_lam(handle_a)
    lam_b = _final_lam(handle_b)
    assert lam_a == lam_b
    assert round(lam_a, 6) == round(round(lam_a, 6), 6)


# --------------------------------------------------------------------------- #
# AC3 -- golden fixture is fixed (re-bake reproduces the same SHA)
# --------------------------------------------------------------------------- #


async def test_golden_fixture_deterministic() -> None:
    """AC3: re-baking this golden from scratch reproduces the committed
    fixture (``tests/fixtures/live_loop_golden/``) byte-for-byte -- the
    fixture is a deterministic function of the (fixed) capture inputs, not a
    stale/frozen one-off copy."""
    handle, capture, embedding_wrapper = await _run_capture()
    replay, _replay_llm, _replay_embedding = await _run_replay(
        capture=capture,
        llm_used=handle.llm.used,
        embedding_used=embedding_wrapper.used,
    )
    assert replay.checksum == capture.checksum

    rendered = _render_fixture(capture=capture, replay_checksum=replay.checksum)
    for name, text in rendered.items():
        committed = (_FIXTURE_DIR / name).read_text(encoding="utf-8")
        assert text == committed, f"{name} byte mismatch -- golden fixture drifted"


# --------------------------------------------------------------------------- #
# AC4 -- role = regression guard, never closure witness (MEDIUM-3)
# --------------------------------------------------------------------------- #


def test_golden_role_is_regression_guard() -> None:
    """AC4: the golden's role marker pins regression-guard framing
    (design-final.md MEDIUM-3) -- W-golden proves organ-path
    reconstructability, never "the loop closed" (that is W-live's job,
    a later issue)."""
    lowered = GOLDEN_ROLE_NOTE.lower()
    assert "regression guard" in lowered
    for forbidden in _FORBIDDEN_OVERCLAIM_SUBSTRINGS:
        assert forbidden not in lowered, f"over-claim substring found: {forbidden!r}"

    manifest = json.loads((_FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["role"] == GOLDEN_ROLE_NOTE
    assert manifest["verdict"] is None
