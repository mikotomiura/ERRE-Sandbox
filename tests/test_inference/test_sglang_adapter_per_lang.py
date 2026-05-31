"""PR-14 per-language routing tests for ``erre_sandbox.inference.sglang_adapter``.

DPN14-1.1 (Stage 1 multi-LoRA dispatch) requires :meth:`SGLangChatClient.chat`
to demand an explicit adapter intent on every call so per-stimulus routing
in :mod:`scripts.m9_c_adopt.tier_b_pilot` cannot regress to an implicit
``None → base`` fallback. The three cases below pin the contract:

1. ``adapter="kant_de_lora_seed44_v1"`` dispatches to the registered de LoRA
2. ``adapter="kant_en_lora_seed44_v1"`` dispatches to the registered en LoRA
3. Any name that is neither :data:`NO_LORA_SENTINEL` nor loaded raises
   :class:`ValueError` before any network round-trip

Mocking strategy mirrors ``test_sglang_adapter.py`` (httpx.MockTransport with
captured bodies) so the suite stays CPU-only and runs on the default install
without SGLang / CUDA extras.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from erre_sandbox.inference.sampling import compose_sampling
from erre_sandbox.inference.sglang_adapter import (
    NO_LORA_SENTINEL,
    LoRAAdapterRef,
    SGLangChatClient,
)
from erre_sandbox.schemas import SamplingBase, SamplingDelta


def _ok_handler(captured: list[dict[str, Any]]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(
            {
                "url": request.url.path,
                "body": json.loads(request.content) if request.content else {},
            },
        )
        if request.url.path == SGLangChatClient.CHAT_PATH:
            return httpx.Response(
                httpx.codes.OK,
                json={
                    "id": "chatcmpl-pr14",
                    "object": "chat.completion",
                    "model": "qwen/Qwen3-8B",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "ok"},
                            "finish_reason": "stop",
                        },
                    ],
                    "usage": {
                        "prompt_tokens": 8,
                        "completion_tokens": 2,
                        "total_tokens": 10,
                    },
                },
            )
        return httpx.Response(httpx.codes.OK, json={"loaded_adapters": []})

    return httpx.MockTransport(handler)


def _make_client(transport: httpx.MockTransport) -> SGLangChatClient:
    return SGLangChatClient(
        client=httpx.AsyncClient(
            base_url=SGLangChatClient.DEFAULT_ENDPOINT,
            transport=transport,
        ),
    )


def _ref(name: str) -> LoRAAdapterRef:
    return LoRAAdapterRef(
        adapter_name=name,
        weight_path=Path("/var/lora") / name,
        rank=16,
    )


def _sampling() -> Any:
    return compose_sampling(
        SamplingBase(temperature=0.6, top_p=0.95, repeat_penalty=1.0),
        SamplingDelta(),
    )


async def test_de_adapter_literal_routes_to_de_lora() -> None:
    """`adapter="kant_de_lora_seed44_v1"` → body.lora_path == that literal."""
    captured: list[dict[str, Any]] = []
    de_name = "kant_de_lora_seed44_v1"
    en_name = "kant_en_lora_seed44_v1"
    async with _make_client(_ok_handler(captured)) as llm:
        await llm.load_adapter(_ref(de_name))
        await llm.load_adapter(_ref(en_name))
        resp = await llm.chat([], sampling=_sampling(), adapter=de_name)

    assert resp.content == "ok"
    chat_calls = [c for c in captured if c["url"] == SGLangChatClient.CHAT_PATH]
    assert len(chat_calls) == 1
    assert chat_calls[0]["body"]["lora_path"] == de_name


async def test_en_adapter_literal_routes_to_en_lora() -> None:
    """`adapter="kant_en_lora_seed44_v1"` → body.lora_path == that literal."""
    captured: list[dict[str, Any]] = []
    de_name = "kant_de_lora_seed44_v1"
    en_name = "kant_en_lora_seed44_v1"
    async with _make_client(_ok_handler(captured)) as llm:
        await llm.load_adapter(_ref(de_name))
        await llm.load_adapter(_ref(en_name))
        resp = await llm.chat([], sampling=_sampling(), adapter=en_name)

    assert resp.content == "ok"
    chat_calls = [c for c in captured if c["url"] == SGLangChatClient.CHAT_PATH]
    assert len(chat_calls) == 1
    assert chat_calls[0]["body"]["lora_path"] == en_name


async def test_invalid_adapter_literal_raises_before_network() -> None:
    """Anything that is neither NO_LORA_SENTINEL nor a loaded adapter → ValueError.

    Uses ``"kant_fr_lora_seed44_v1"`` as a stand-in for an unsupported language
    literal — the validation is name-equality against :attr:`loaded_adapters`
    + the explicit base-model sentinel, so the error path is identical for any
    unknown name. The assertion that no chat request was sent guards the
    fail-fast contract (CS-2: adapter routing is the client's responsibility).
    """
    captured: list[dict[str, Any]] = []
    async with _make_client(_ok_handler(captured)) as llm:
        await llm.load_adapter(_ref("kant_de_lora_seed44_v1"))
        await llm.load_adapter(_ref("kant_en_lora_seed44_v1"))
        with pytest.raises(ValueError, match="not loaded") as exc_info:
            await llm.chat(
                [],
                sampling=_sampling(),
                adapter="kant_fr_lora_seed44_v1",
            )

    # The error message must point operators at NO_LORA_SENTINEL so the
    # base-model opt-out is discoverable from the failure itself.
    assert NO_LORA_SENTINEL in str(exc_info.value)
    chat_calls = [c for c in captured if c["url"] == SGLangChatClient.CHAT_PATH]
    assert chat_calls == []
