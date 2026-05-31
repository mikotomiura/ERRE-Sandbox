"""Unit tests for :mod:`erre_sandbox.memory.embedding` (httpx-mocked)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from erre_sandbox.memory.embedding import (
    DOC_PREFIX,
    QUERY_PREFIX,
    EmbeddingClient,
    EmbeddingUnavailableError,
)


def _ok_handler(
    vector: list[float],
    captured: list[dict[str, Any]],
) -> httpx.MockTransport:
    """MockTransport: capture request body and return ``vector`` for every call."""

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"embeddings": [vector]})

    return httpx.MockTransport(handler)


def _err_handler(exc: Exception) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
        raise exc

    return httpx.MockTransport(handler)


async def _make_client(transport: httpx.MockTransport) -> EmbeddingClient:
    return EmbeddingClient(
        client=httpx.AsyncClient(
            base_url=EmbeddingClient.DEFAULT_ENDPOINT,
            transport=transport,
        ),
    )


async def test_embed_returns_expected_dim() -> None:
    vec = [0.1] * 768
    captured: list[dict[str, Any]] = []
    async with await _make_client(_ok_handler(vec, captured)) as client:
        out = await client.embed("hello")
    assert len(out) == 768
    assert out[0] == pytest.approx(0.1)
    assert captured[0]["input"] == ["hello"]


async def test_embed_query_prepends_prefix() -> None:
    vec = [0.0] * 768
    captured: list[dict[str, Any]] = []
    async with await _make_client(_ok_handler(vec, captured)) as client:
        await client.embed_query("散歩について")
    assert captured[0]["input"] == [QUERY_PREFIX + "散歩について"]


async def test_embed_document_prepends_prefix() -> None:
    vec = [0.0] * 768
    captured: list[dict[str, Any]] = []
    async with await _make_client(_ok_handler(vec, captured)) as client:
        await client.embed_document("peripatos の定義")
    assert captured[0]["input"] == [DOC_PREFIX + "peripatos の定義"]


async def test_embed_many_dispatches_by_kind() -> None:
    vec = [0.0] * 768
    captured: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured.append(body)
        return httpx.Response(
            200,
            json={"embeddings": [vec for _ in body["input"]]},
        )

    transport = httpx.MockTransport(handler)
    async with await _make_client(transport) as client:
        await client.embed_many(["a", "b"], kind="query")
        await client.embed_many(["c"], kind="document")
    assert captured[0]["input"] == [QUERY_PREFIX + "a", QUERY_PREFIX + "b"]
    assert captured[1]["input"] == [DOC_PREFIX + "c"]


async def test_embed_unreachable_raises() -> None:
    transport = _err_handler(httpx.ConnectError("refused"))
    async with await _make_client(transport) as client:
        with pytest.raises(EmbeddingUnavailableError, match="unreachable"):
            await client.embed_query("x")


async def test_embed_non_200_raises() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    transport = httpx.MockTransport(handler)
    async with await _make_client(transport) as client:
        with pytest.raises(EmbeddingUnavailableError, match="HTTP 500"):
            await client.embed_query("x")


async def test_embed_malformed_payload_raises() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"not_embeddings": []})

    transport = httpx.MockTransport(handler)
    async with await _make_client(transport) as client:
        with pytest.raises(EmbeddingUnavailableError, match="missing 'embeddings'"):
            await client.embed_query("x")
