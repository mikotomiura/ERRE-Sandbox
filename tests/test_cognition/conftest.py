"""Fixtures for cognition-cycle tests.

Provides mock-backed :class:`OllamaChatClient` / :class:`EmbeddingClient`
instances constructed with :class:`httpx.MockTransport` so tests never
touch a real Ollama server. The real :class:`MemoryStore` and
:class:`Retriever` are used in-memory so the integration tests exercise
the full cognition → memory → embedding contract.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from erre_sandbox.inference.ollama_adapter import OllamaChatClient
from erre_sandbox.memory import EmbeddingClient, MemoryStore, Retriever
from erre_sandbox.schemas import (
    InternalEvent,
    PerceptionEvent,
    SpeechEvent,
    Zone,
    ZoneTransitionEvent,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

DEFAULT_PLAN: dict[str, Any] = {
    "thought": "I will take my daily walk along the peripatos.",
    "utterance": "今日も散歩へ出よう。",
    "destination_zone": "peripatos",
    "animation": "walk",
    "valence_delta": 0.1,
    "arousal_delta": 0.05,
    "motivation_delta": 0.2,
    "importance_hint": 0.6,
}


def _chat_handler(
    content: str, captured: list[dict[str, Any]] | None = None
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(json.loads(request.content))
        return httpx.Response(
            httpx.codes.OK,
            json={
                "model": "qwen3:8b",
                "message": {"role": "assistant", "content": content},
                "done": True,
                "done_reason": "stop",
                "total_duration": 800_000_000,
                "eval_count": 32,
                "prompt_eval_count": 64,
            },
        )

    return handler


def _embed_handler() -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        inputs = body.get("input") or []
        count = len(inputs) if isinstance(inputs, list) else 1
        vec = [0.01] * EmbeddingClient.DEFAULT_DIM
        return httpx.Response(
            httpx.codes.OK,
            json={"embeddings": [vec for _ in range(count)]},
        )

    return handler


def _raising_handler(
    exc: Exception,
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
        raise exc

    return handler


def _make_chat_client(
    content: str = "",
    captured: list[dict[str, Any]] | None = None,
    *,
    raise_exc: Exception | None = None,
) -> OllamaChatClient:
    plan_content = content or json.dumps(DEFAULT_PLAN)
    handler = (
        _raising_handler(raise_exc)
        if raise_exc is not None
        else _chat_handler(plan_content, captured)
    )
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(
        base_url=OllamaChatClient.DEFAULT_ENDPOINT,
        transport=transport,
    )
    return OllamaChatClient(client=client)


def _make_embedding_client(
    *,
    raise_exc: Exception | None = None,
) -> EmbeddingClient:
    handler = _raising_handler(raise_exc) if raise_exc is not None else _embed_handler()
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(
        base_url=EmbeddingClient.DEFAULT_ENDPOINT,
        transport=transport,
    )
    return EmbeddingClient(client=client)


@pytest.fixture
def make_chat_client() -> Callable[..., OllamaChatClient]:
    """Factory for a MockTransport-backed :class:`OllamaChatClient`."""
    return _make_chat_client


@pytest.fixture
def make_embedding_client() -> Callable[..., EmbeddingClient]:
    return _make_embedding_client


@pytest.fixture
async def cognition_store() -> AsyncIterator[MemoryStore]:
    s = MemoryStore(db_path=":memory:")
    s.create_schema()
    try:
        yield s
    finally:
        await s.close()


@pytest.fixture
async def cognition_retriever(
    cognition_store: MemoryStore,
    make_embedding_client: Callable[[], EmbeddingClient],
) -> AsyncIterator[Retriever]:
    emb = make_embedding_client()
    try:
        yield Retriever(cognition_store, emb)
    finally:
        await emb.close()


# ---------- Observation factories ---------------------------------------


@pytest.fixture
def perception_event() -> PerceptionEvent:
    return PerceptionEvent(
        tick=1,
        agent_id="a_kant_001",
        modality="sight",
        source_zone=Zone.STUDY,
        content="library shelves",
        intensity=0.4,
    )


@pytest.fixture
def speech_event() -> SpeechEvent:
    return SpeechEvent(
        tick=1,
        agent_id="a_kant_001",
        speaker_id="a_other_001",
        utterance="guten Tag",
        emotional_impact=0.2,
    )


@pytest.fixture
def zone_entry_event() -> ZoneTransitionEvent:
    return ZoneTransitionEvent(
        tick=1,
        agent_id="a_kant_001",
        from_zone=Zone.STUDY,
        to_zone=Zone.PERIPATOS,
    )


@pytest.fixture
def internal_event() -> InternalEvent:
    return InternalEvent(
        tick=1,
        agent_id="a_kant_001",
        content="time for reflection",
        importance_hint=0.7,
    )
