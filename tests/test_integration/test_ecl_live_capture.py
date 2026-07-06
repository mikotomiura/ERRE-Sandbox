"""ECL v0 live-capture apparatus tests (M13, Issue 001).

The apparatus (``integration/embodied/live.py``) is Ollama-free and testable
end-to-end with a mock inner chat client — the actual live Ollama capture is
Issue 003. These tests pin:

* **I1-G1/I1-G2** :class:`~erre_sandbox.integration.embodied.live.ThinkOffChatClient`
  forces ``think=False`` and forwards everything else unchanged.
* **I1-G3/I1-G4** :func:`~erre_sandbox.integration.embodied.live.run_live_capture`
  records with a mock inner and replays byte-identically from the captured
  decisions alone (``inner_invocations == 0``).
* **I2-G1** pre-registered protocol constants (D-1/D-2/D-4/D-5).
* **I2-G2** the live env-pin helper populates the manifest with qwen3
  digest / Ollama version / VRAM / uv.lock hash / ``think:false`` / resolved
  sampling.
* **I2-G3** the manifest observables overlay pre-registers O1-O5 +
  ``done_formula`` + ``o5_min_ticks`` as sealed-run-before constants.
* **I2-G4** measurement-line non-re-entry (import / output-identifier guard,
  mirrors the existing ``loop.py`` / ``handoff.py`` guards).
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from erre_sandbox.inference.ollama_adapter import ChatMessage, ChatResponse
from erre_sandbox.inference.sampling import ResolvedSampling
from erre_sandbox.integration.embodied import handoff
from erre_sandbox.integration.embodied import live as ecl_live
from erre_sandbox.integration.embodied.live import (
    LIVE_DONE_FORMULA,
    LIVE_EMBEDDING_MODE,
    LIVE_N_COGNITION_TICKS,
    LIVE_O5_MIN_TICKS,
    LIVE_PERSONA_ID,
    ThinkOffChatClient,
    attach_live_observables,
    build_live_env_pins,
    run_live_capture,
)
from erre_sandbox.integration.embodied.loop import (
    replay_client_from,
    run_ecl_loop,
)
from erre_sandbox.memory import EmbeddingClient, MemoryStore

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from erre_sandbox.schemas import AgentState, PersonaSpec

_FIXED = datetime(2026, 1, 1, tzinfo=UTC)
_PLAN_JSON = json.dumps(
    {
        "thought": "walk the peripatos",
        "utterance": "散歩へ",
        "destination_zone": "peripatos",
        "animation": "walk",
    }
)
_SAMPLING = ResolvedSampling(temperature=0.7, top_p=0.9, repeat_penalty=1.1)


def _embed_client() -> EmbeddingClient:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        inputs = body.get("input") or []
        count = len(inputs) if isinstance(inputs, list) else 1
        vec = [0.01] * EmbeddingClient.DEFAULT_DIM
        return httpx.Response(httpx.codes.OK, json={"embeddings": [vec] * count})

    return EmbeddingClient(
        client=httpx.AsyncClient(
            base_url=EmbeddingClient.DEFAULT_ENDPOINT,
            transport=httpx.MockTransport(handler),
        )
    )


@dataclass
class _RequestCapturingInner:
    """Mock inner chat client that records the exact kwargs it was called with."""

    content: str = _PLAN_JSON
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        sampling: ResolvedSampling,
        model: str | None = None,
        options: dict[str, Any] | None = None,
        think: bool | None = None,
    ) -> ChatResponse:
        self.calls.append(
            {
                "messages": messages,
                "sampling": sampling,
                "model": model,
                "options": options,
                "think": think,
            }
        )
        return ChatResponse(
            content=self.content,
            model="qwen3:8b",
            eval_count=1,
            total_duration_ms=0.0,
        )


# --------------------------------------------------------------------------- #
# I1-G1 — ThinkOffChatClient forces think=False
# --------------------------------------------------------------------------- #


async def test_think_off_chat_client_forces_think_false() -> None:
    inner = _RequestCapturingInner()
    client = ThinkOffChatClient(inner)
    messages = [ChatMessage(role="user", content="hello")]

    await client.chat(messages, sampling=_SAMPLING, think=None)
    await client.chat(messages, sampling=_SAMPLING, think=True)

    assert len(inner.calls) == 2
    assert inner.calls[0]["think"] is False
    assert inner.calls[1]["think"] is False


# --------------------------------------------------------------------------- #
# I1-G2 — passthrough of everything else + ChatResponse passthrough
# --------------------------------------------------------------------------- #


async def test_think_off_chat_client_passthrough() -> None:
    inner = _RequestCapturingInner(content="verbatim response")
    client = ThinkOffChatClient(inner)
    messages = [
        ChatMessage(role="system", content="sys"),
        ChatMessage(role="user", content="usr"),
    ]
    options = {"num_predict": 128}

    response = await client.chat(
        messages, sampling=_SAMPLING, model="qwen3:8b", options=options, think=None
    )

    call = inner.calls[0]
    assert call["messages"] is messages
    assert call["sampling"] is _SAMPLING
    assert call["model"] == "qwen3:8b"
    assert call["options"] is options
    assert response.content == "verbatim response"
    assert response.model == "qwen3:8b"


# --------------------------------------------------------------------------- #
# I1-G3 — harness records with a mock inner (live-independent)
# --------------------------------------------------------------------------- #


async def _capture(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
    *,
    inner: Any | None = None,
    n_cognition_ticks: int = 4,
) -> Any:
    inner = inner or _RequestCapturingInner()
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _embed_client()
    try:
        return await run_live_capture(
            inner_chat=inner,
            store=store,
            embedding=embedding,
            run_id="r-live",
            agent_state=make_agent_state(),
            persona=make_persona_spec(),
            retrieval_now=_FIXED,
            base_ts=_FIXED,
            n_cognition_ticks=n_cognition_ticks,
        )
    finally:
        await embedding.close()
        await store.close()


async def test_live_capture_harness_records_with_mock_inner(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    inner = _RequestCapturingInner()
    result = await _capture(make_agent_state, make_persona_spec, inner=inner)

    assert result.rows, "live capture produced no trace rows"
    assert len(result.decisions) == 4
    for decision in result.decisions:
        assert decision.plan is not None
        assert decision.llm_status == "ok"
        assert decision.call.raw_response == _PLAN_JSON
    assert result.checksum
    # The mock inner actually saw every action-LLM call, each forced think=False
    # by the ThinkOffChatClient the harness wraps it in.
    assert len(inner.calls) == 4
    assert all(call["think"] is False for call in inner.calls)


# --------------------------------------------------------------------------- #
# I1-G4 — replay-from-decisions roundtrip (byte-identical, no live LLM)
# --------------------------------------------------------------------------- #


async def test_live_capture_replay_roundtrip_mock(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    recorded = await _capture(make_agent_state, make_persona_spec)

    replay_llm = replay_client_from(recorded)
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _embed_client()
    try:
        replayed = await run_ecl_loop(
            run_id="r-live",
            store=store,
            embedding=embedding,
            llm=replay_llm,
            agent_state=make_agent_state(),
            persona=make_persona_spec(),
            retrieval_now=_FIXED,
            base_ts=_FIXED,
            n_cognition_ticks=4,
        )
    finally:
        await embedding.close()
        await store.close()

    assert replay_llm.inner_invocations == 0
    assert replayed.checksum == recorded.checksum


# --------------------------------------------------------------------------- #
# I2-G1 — pre-registered protocol constants
# --------------------------------------------------------------------------- #


def test_live_capture_protocol_constants() -> None:
    assert LIVE_N_COGNITION_TICKS == 32
    assert LIVE_PERSONA_ID == "kant"
    assert LIVE_EMBEDDING_MODE == "mock"
    assert LIVE_O5_MIN_TICKS == 1
    assert LIVE_DONE_FORMULA == "O1∧O2∧O3a∧O3b"


# --------------------------------------------------------------------------- #
# I2-G2 — manifest env pins (qwen3 digest / Ollama version / VRAM / uv.lock /
# think:false / resolved sampling)
# --------------------------------------------------------------------------- #


async def test_live_manifest_pins_env(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    result = await _capture(make_agent_state, make_persona_spec)
    resolved_sampling = result.decisions[0].call.sampling

    env_pins = build_live_env_pins(
        qwen3_model_digest="sha256:deadbeef",
        ollama_version="0.5.1",
        vram_gb=16.0,
        uv_lock_sha256="abc123",
        resolved_sampling=resolved_sampling,
        base_env_pins={"python": "3.11.9", "packages": {}, "godot": "4.6"},
    )
    trace_jsonl = handoff.trace_rows_to_jsonl(result.rows)
    decisions_jsonl = handoff.decisions_to_jsonl(result.decisions)
    envelope_jsonl = handoff.envelope_stream_to_jsonl(
        handoff.build_envelope_stream(result)
    )
    manifest = handoff.build_manifest(
        result,
        run_config=handoff.golden_run_config(),
        trace_jsonl=trace_jsonl,
        decisions_jsonl=decisions_jsonl,
        envelope_jsonl=envelope_jsonl,
        env_pins=env_pins,
    )

    pins = manifest["env_pins"]
    assert pins["qwen3_model_digest"] == "sha256:deadbeef"
    assert pins["ollama_version"] == "0.5.1"
    assert pins["vram_gb"] == 16.0
    assert pins["uv_lock_sha256"] == "abc123"
    assert pins["think"] is False
    pinned_sampling = pins["resolved_sampling"]
    assert pinned_sampling["temperature"] == resolved_sampling.temperature
    assert pinned_sampling["top_p"] == resolved_sampling.top_p
    assert pinned_sampling["repeat_penalty"] == resolved_sampling.repeat_penalty


# --------------------------------------------------------------------------- #
# I2-G3 — manifest observables overlay pre-registers O1-O5 (tune-to-pass closed)
# --------------------------------------------------------------------------- #


async def test_live_manifest_observables_preregistered(
    make_agent_state: Callable[..., AgentState],
    make_persona_spec: Callable[..., PersonaSpec],
) -> None:
    result = await _capture(make_agent_state, make_persona_spec)
    trace_jsonl = handoff.trace_rows_to_jsonl(result.rows)
    decisions_jsonl = handoff.decisions_to_jsonl(result.decisions)
    envelope_jsonl = handoff.envelope_stream_to_jsonl(
        handoff.build_envelope_stream(result)
    )
    manifest = handoff.build_manifest(
        result,
        run_config=handoff.golden_run_config(),
        trace_jsonl=trace_jsonl,
        decisions_jsonl=decisions_jsonl,
        envelope_jsonl=envelope_jsonl,
    )

    overlaid = attach_live_observables(manifest)

    observables = overlaid["observables"]
    for key in ("O1", "O2", "O3a", "O3b", "O4", "O5"):
        assert key in observables
        assert isinstance(observables[key], str)
        assert observables[key]
    assert observables["done_formula"] == "O1∧O2∧O3a∧O3b"
    assert observables["o5_min_ticks"] == 1
    # Non-mutating: the original manifest dict is untouched.
    assert "observables" not in manifest


# --------------------------------------------------------------------------- #
# I2-G4 — measurement-line non-re-entry (import / output guard)
# --------------------------------------------------------------------------- #


_LIVE_TREE = ast.parse(Path(ecl_live.__file__).read_text(encoding="utf-8"))


def _assert_no_measurement_imports(tree: ast.Module) -> None:
    banned_prefix = ("erre_sandbox.evidence",)
    banned_sub = ("spdm", "runningness")
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            assert not node.module.startswith(banned_prefix), node.module
            assert not any(s in node.module for s in banned_sub), node.module
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(banned_prefix), alias.name
                assert not any(s in alias.name for s in banned_sub), alias.name


def _stored_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
        return [node.id]
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [node.target.id]
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [node.name]
    if isinstance(node, ast.arg):
        return [node.arg]
    return []


def _assert_no_measurement_output_identifiers(tree: ast.Module) -> None:
    banned_ident = ("floor", "landscape", "verdict", "jaccard", "divergence", "r_min")
    for node in ast.walk(tree):
        for name in _stored_names(node):
            low = name.lower()
            assert not any(tok in low for tok in banned_ident), name


def test_live_capture_measurement_guard() -> None:
    """``live.py`` imports no measurement machinery and defines no floor /
    landscape / verdict output identifier (design §論点4, mirrors the
    ``loop.py`` / ``handoff.py`` guards)."""
    _assert_no_measurement_imports(_LIVE_TREE)
    _assert_no_measurement_output_identifiers(_LIVE_TREE)
