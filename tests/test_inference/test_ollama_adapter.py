"""Unit tests for :mod:`erre_sandbox.inference.ollama_adapter` (httpx-mocked)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from erre_sandbox.inference.ollama_adapter import (
    ChatMessage,
    ChatResponse,
    OllamaChatClient,
    OllamaUnavailableError,
)
from erre_sandbox.inference.sampling import ResolvedSampling, compose_sampling
from erre_sandbox.schemas import SamplingBase, SamplingDelta


def _ok_response(
    captured: list[dict[str, Any]],
    *,
    model: str = "qwen3:8b",
    content: str = "walked quietly.",
    done_reason: str = "stop",
) -> httpx.MockTransport:
    """MockTransport: capture request body and return a canned chat response."""

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(
            httpx.codes.OK,
            json={
                "model": model,
                "message": {"role": "assistant", "content": content},
                "done": True,
                "done_reason": done_reason,
                "total_duration": 1_500_000_000,  # 1500 ms in nanoseconds
                "eval_count": 42,
                "prompt_eval_count": 128,
            },
        )

    return httpx.MockTransport(handler)


def _raising_transport(exc: Exception) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
        raise exc

    return httpx.MockTransport(handler)


def _make_client(
    transport: httpx.MockTransport,
    **kwargs: Any,
) -> OllamaChatClient:
    return OllamaChatClient(
        client=httpx.AsyncClient(
            base_url=OllamaChatClient.DEFAULT_ENDPOINT,
            transport=transport,
        ),
        **kwargs,
    )


def _default_sampling() -> ResolvedSampling:
    return compose_sampling(
        SamplingBase(temperature=0.7, top_p=0.9, repeat_penalty=1.0),
        SamplingDelta(),
    )


def _system_user() -> list[ChatMessage]:
    return [
        ChatMessage(role="system", content="You are Kant."),
        ChatMessage(role="user", content="Describe today's walk."),
    ]


async def test_chat_returns_chat_response() -> None:
    captured: list[dict[str, Any]] = []
    async with _make_client(_ok_response(captured)) as llm:
        resp = await llm.chat(_system_user(), sampling=_default_sampling())

    assert isinstance(resp, ChatResponse)
    assert resp.content == "walked quietly."
    assert resp.model == "qwen3:8b"
    assert resp.eval_count == 42
    assert resp.prompt_eval_count == 128
    assert resp.total_duration_ms == pytest.approx(1500.0)
    assert resp.finish_reason == "stop"


async def test_chat_sends_sampling_and_messages() -> None:
    captured: list[dict[str, Any]] = []
    sampling = compose_sampling(
        SamplingBase(temperature=0.6, top_p=0.85, repeat_penalty=1.12),
        SamplingDelta(temperature=0.3, top_p=0.05, repeat_penalty=-0.1),
    )
    async with _make_client(_ok_response(captured)) as llm:
        await llm.chat(_system_user(), sampling=sampling)

    body = captured[0]
    assert body["model"] == "qwen3:8b"
    assert body["stream"] is False
    assert body["messages"] == [
        {"role": "system", "content": "You are Kant."},
        {"role": "user", "content": "Describe today's walk."},
    ]
    # Regression guard: ``think`` must NOT leak into the default wire shape.
    # Callers that omit ``think=`` (cognition cycle, Reflector) rely on
    # qwen3 thinking staying on; an unguarded ``"think": False`` would
    # silently suppress it for every M2/M4 code path.
    assert "think" not in body
    options = body["options"]
    assert options["temperature"] == pytest.approx(0.9)
    assert options["top_p"] == pytest.approx(0.9)
    assert options["repeat_penalty"] == pytest.approx(1.02)


async def test_chat_merges_extra_options_but_sampling_wins() -> None:
    captured: list[dict[str, Any]] = []
    async with _make_client(_ok_response(captured)) as llm:
        await llm.chat(
            _system_user(),
            sampling=_default_sampling(),
            options={
                "num_predict": 256,
                "stop": ["</s>"],
                "temperature": 1.99,  # must be ignored — sampling is authoritative
            },
        )

    options = captured[0]["options"]
    assert options["num_predict"] == 256
    assert options["stop"] == ["</s>"]
    assert options["temperature"] == pytest.approx(0.7)


async def test_chat_respects_model_override() -> None:
    captured: list[dict[str, Any]] = []
    async with _make_client(_ok_response(captured)) as llm:
        await llm.chat(
            _system_user(),
            sampling=_default_sampling(),
            model="foo:tiny",
        )

    assert captured[0]["model"] == "foo:tiny"


async def test_chat_length_finish_reason() -> None:
    captured: list[dict[str, Any]] = []
    transport = _ok_response(captured, done_reason="length")
    async with _make_client(transport) as llm:
        resp = await llm.chat(_system_user(), sampling=_default_sampling())
    assert resp.finish_reason == "length"


async def test_chat_unreachable_raises() -> None:
    transport = _raising_transport(httpx.ConnectError("refused"))
    async with _make_client(transport) as llm:
        with pytest.raises(OllamaUnavailableError, match="unreachable"):
            await llm.chat(_system_user(), sampling=_default_sampling())


async def test_chat_timeout_raises() -> None:
    transport = _raising_transport(httpx.ConnectTimeout("slow"))
    async with _make_client(transport) as llm:
        with pytest.raises(OllamaUnavailableError, match="timeout"):
            await llm.chat(_system_user(), sampling=_default_sampling())


async def test_chat_non_200_raises() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    transport = httpx.MockTransport(handler)
    async with _make_client(transport) as llm:
        with pytest.raises(OllamaUnavailableError, match="HTTP 500"):
            await llm.chat(_system_user(), sampling=_default_sampling())


async def test_chat_missing_message_raises() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            httpx.codes.OK,
            json={"model": "qwen3:8b", "done": True},
        )

    transport = httpx.MockTransport(handler)
    async with _make_client(transport) as llm:
        with pytest.raises(OllamaUnavailableError, match=r"missing 'message\.content'"):
            await llm.chat(_system_user(), sampling=_default_sampling())


async def test_chat_malformed_json_raises() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            httpx.codes.OK,
            text="<html>not json</html>",
        )

    transport = httpx.MockTransport(handler)
    async with _make_client(transport) as llm:
        with pytest.raises(OllamaUnavailableError, match="non-JSON"):
            await llm.chat(_system_user(), sampling=_default_sampling())


async def test_chat_non_object_json_raises() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(httpx.codes.OK, json=["list", "not", "object"])

    transport = httpx.MockTransport(handler)
    async with _make_client(transport) as llm:
        with pytest.raises(OllamaUnavailableError, match="non-object JSON"):
            await llm.chat(_system_user(), sampling=_default_sampling())


async def test_async_with_closes_owned_client() -> None:
    """When the adapter constructs its own client, ``async with`` closes it."""
    adapter = OllamaChatClient()
    internal = adapter._client
    assert adapter._owns_client is True
    assert not internal.is_closed
    async with adapter:
        pass  # no request — we only validate the ownership/close contract
    assert internal.is_closed


async def test_injected_client_not_closed_by_adapter() -> None:
    """When a caller-owned client is passed, the adapter MUST NOT close it."""
    captured: list[dict[str, Any]] = []
    injected = httpx.AsyncClient(
        base_url=OllamaChatClient.DEFAULT_ENDPOINT,
        transport=_ok_response(captured),
    )
    adapter = OllamaChatClient(client=injected)
    async with adapter:
        await adapter.chat(_system_user(), sampling=_default_sampling())
    assert not injected.is_closed
    await injected.aclose()


async def test_chat_think_false_sets_top_level_flag() -> None:
    """``think=False`` must be emitted at the body top level (not inside options).

    Required by qwen3 thinking-model handling — see
    ``.steering/20260420-m5-llm-spike/decisions.md`` judgement 1.
    """
    captured: list[dict[str, Any]] = []
    async with _make_client(_ok_response(captured)) as llm:
        await llm.chat(_system_user(), sampling=_default_sampling(), think=False)

    body = captured[0]
    assert body["think"] is False
    assert "think" not in body["options"]


async def test_chat_think_true_sets_top_level_flag() -> None:
    captured: list[dict[str, Any]] = []
    async with _make_client(_ok_response(captured)) as llm:
        await llm.chat(_system_user(), sampling=_default_sampling(), think=True)

    body = captured[0]
    assert body["think"] is True
    assert "think" not in body["options"]


async def test_chat_think_none_omits_key() -> None:
    """Explicit ``think=None`` (same as default) must omit the key entirely."""
    captured: list[dict[str, Any]] = []
    async with _make_client(_ok_response(captured)) as llm:
        await llm.chat(_system_user(), sampling=_default_sampling(), think=None)

    assert "think" not in captured[0]


async def test_close_is_idempotent() -> None:
    """Repeated ``close()`` calls on an owned adapter must not raise."""
    adapter = OllamaChatClient()
    await adapter.close()
    assert adapter._client.is_closed
    # Second call — guarded by ``is_closed`` — must be a no-op.
    await adapter.close()
    assert adapter._client.is_closed
