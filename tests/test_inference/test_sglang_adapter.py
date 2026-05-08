"""Unit tests for :mod:`erre_sandbox.inference.sglang_adapter` (httpx-mocked).

m9-c-spike Phase H — exercises the OpenAI-compatible chat round trip and
the LoRA load/unload registry without booting an actual SGLang server. The
sglang Python package is intentionally NOT imported (the adapter only
speaks HTTP), so these tests run on the CI default install with no GPU
extras.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from erre_sandbox.inference.sampling import ResolvedSampling, compose_sampling
from erre_sandbox.inference.sglang_adapter import (
    LoRAAdapterRef,
    SGLangChatClient,
    SGLangUnavailableError,
)
from erre_sandbox.schemas import SamplingBase, SamplingDelta


def _ok_chat(
    captured: list[dict[str, Any]],
    *,
    path: str = SGLangChatClient.CHAT_PATH,
    model: str = "qwen/Qwen3-8B",
    content: str = "studied calmly.",
    finish_reason: str = "stop",
) -> httpx.MockTransport:
    """MockTransport: capture body and return a canned OpenAI-shaped response."""

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(
            {
                "url": request.url.path,
                "body": json.loads(request.content) if request.content else {},
            },
        )
        if request.url.path == path:
            return httpx.Response(
                httpx.codes.OK,
                json={
                    "id": "chatcmpl-test",
                    "object": "chat.completion",
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": content},
                            "finish_reason": finish_reason,
                        },
                    ],
                    "usage": {
                        "prompt_tokens": 64,
                        "completion_tokens": 21,
                        "total_tokens": 85,
                    },
                },
            )
        # Default OK for /load_lora_adapter / /unload_lora_adapter probes.
        return httpx.Response(httpx.codes.OK, json={"loaded_adapters": []})

    return httpx.MockTransport(handler)


def _make_client(
    transport: httpx.MockTransport,
    **kwargs: Any,
) -> SGLangChatClient:
    return SGLangChatClient(
        client=httpx.AsyncClient(
            base_url=SGLangChatClient.DEFAULT_ENDPOINT,
            transport=transport,
        ),
        **kwargs,
    )


def _default_sampling() -> ResolvedSampling:
    return compose_sampling(
        SamplingBase(temperature=0.7, top_p=0.9, repeat_penalty=1.0),
        SamplingDelta(),
    )


def _kant_ref(name: str = "kant_r8") -> LoRAAdapterRef:
    return LoRAAdapterRef(
        adapter_name=name,
        weight_path=Path("/var/lora") / name,
        rank=8,
    )


# ---------------------------------------------------------------------------
# 1. Chat round trip — OpenAI-compatible response shape parses into ChatResponse
# ---------------------------------------------------------------------------


async def test_chat_round_trip_parses_openai_shape() -> None:
    captured: list[dict[str, Any]] = []
    async with _make_client(_ok_chat(captured)) as llm:
        resp = await llm.chat(
            [],
            sampling=_default_sampling(),
        )

    assert resp.content == "studied calmly."
    assert resp.model == "qwen/Qwen3-8B"
    assert resp.eval_count == 21
    assert resp.prompt_eval_count == 64
    assert resp.total_duration_ms == pytest.approx(0.0)
    assert resp.finish_reason == "stop"

    body = captured[0]["body"]
    # OpenAI-compatible: sampling lives at the top level (NOT nested under
    # ``options`` like Ollama).
    assert body["temperature"] == pytest.approx(0.7)
    assert body["top_p"] == pytest.approx(0.9)
    assert body["repetition_penalty"] == pytest.approx(1.0)
    assert body["stream"] is False


# ---------------------------------------------------------------------------
# 2. load_adapter is idempotent — re-loading the same name keeps a single entry
# ---------------------------------------------------------------------------


async def test_load_adapter_is_idempotent() -> None:
    captured: list[dict[str, Any]] = []
    ref = _kant_ref()
    async with _make_client(_ok_chat(captured)) as llm:
        await llm.load_adapter(ref)
        await llm.load_adapter(ref)

    assert list(llm.loaded_adapters) == [ref.adapter_name]
    assert llm.loaded_adapters[ref.adapter_name] is ref
    # Both calls hit the load endpoint; the registry tolerates the second 2xx.
    load_calls = [c for c in captured if c["url"] == SGLangChatClient.LOAD_LORA_PATH]
    assert len(load_calls) == 2
    assert load_calls[0]["body"] == {
        "lora_name": "kant_r8",
        "lora_path": str(Path("/var/lora") / "kant_r8"),
        "pinned": False,
    }


# ---------------------------------------------------------------------------
# 3. unload_adapter is idempotent — unloading an unknown name does not raise
# ---------------------------------------------------------------------------


async def test_unload_adapter_unknown_name_is_idempotent() -> None:
    captured: list[dict[str, Any]] = []
    async with _make_client(_ok_chat(captured)) as llm:
        # No load happened yet; unload must NOT raise (CS-2 idempotent contract).
        await llm.unload_adapter("never_loaded")
        assert "never_loaded" not in llm.loaded_adapters

        # Real round-trip: load → unload → registry empty
        ref = _kant_ref()
        await llm.load_adapter(ref)
        assert ref.adapter_name in llm.loaded_adapters
        await llm.unload_adapter(ref.adapter_name)
        assert ref.adapter_name not in llm.loaded_adapters


# ---------------------------------------------------------------------------
# 4. loaded_adapters returns an immutable view of internal state (NO server query)
# ---------------------------------------------------------------------------


async def test_loaded_adapters_is_internal_state_only() -> None:
    captured: list[dict[str, Any]] = []
    ref = _kant_ref()
    async with _make_client(_ok_chat(captured)) as llm:
        await llm.load_adapter(ref)

        view = llm.loaded_adapters
        assert dict(view) == {ref.adapter_name: ref}

        # Caller cannot mutate the registry through the property.
        with pytest.raises(TypeError):
            view["sneaky"] = ref  # type: ignore[index]

        # Reading the property again does NOT cause a server round-trip.
        urls_before = [c["url"] for c in captured]
        _ = llm.loaded_adapters
        urls_after = [c["url"] for c in captured]
        assert urls_before == urls_after


# ---------------------------------------------------------------------------
# 5. chat with unknown adapter raises ValueError BEFORE any server round-trip
# ---------------------------------------------------------------------------


async def test_chat_with_unknown_adapter_raises_before_network() -> None:
    captured: list[dict[str, Any]] = []
    async with _make_client(_ok_chat(captured)) as llm:
        with pytest.raises(ValueError, match="not loaded"):
            await llm.chat([], sampling=_default_sampling(), adapter="nope")

    # Fail-fast: no chat request was sent.
    chat_calls = [c for c in captured if c["url"] == SGLangChatClient.CHAT_PATH]
    assert chat_calls == []


# ---------------------------------------------------------------------------
# 6. SGLang 5xx on load → SGLangUnavailableError + registry unchanged
# ---------------------------------------------------------------------------


async def test_load_adapter_5xx_does_not_mutate_registry() -> None:
    sensitive_body = "Traceback... CUDA_VISIBLE_DEVICES=0 /secret/path/model.bin"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == SGLangChatClient.LOAD_LORA_PATH:
            return httpx.Response(500, text=sensitive_body)
        return httpx.Response(httpx.codes.OK, json={})

    transport = httpx.MockTransport(handler)
    ref = _kant_ref()
    async with _make_client(transport) as llm:
        with pytest.raises(SGLangUnavailableError, match="HTTP 500") as exc_info:
            await llm.load_adapter(ref)
        # security review HIGH-2: server-side debug body MUST NOT leak into
        # the public exception message (paths / env / traces stay in DEBUG log).
        assert "CUDA_VISIBLE_DEVICES" not in str(exc_info.value)
        assert "/secret/path" not in str(exc_info.value)
        assert "Traceback" not in str(exc_info.value)
        # CS-2: registry stays consistent with server actual state on failure.
        assert ref.adapter_name not in llm.loaded_adapters


# ---------------------------------------------------------------------------
# 7. close() is idempotent on owned clients
# ---------------------------------------------------------------------------


async def test_close_is_idempotent() -> None:
    adapter = SGLangChatClient()
    assert adapter._owns_client is True
    await adapter.close()
    assert adapter._client.is_closed
    # Second call must be a no-op (guarded by ``is_closed`` check).
    await adapter.close()
    assert adapter._client.is_closed
