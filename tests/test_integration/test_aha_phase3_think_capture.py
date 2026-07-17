"""Ollama-free tests for the aha Phase 3 think=True capture apparatus.

Pins the additive ``think_capture`` module (design-final in
``.steering/20260717-aha-phase3-think-true-live/``): thinking extraction (3 paths), the
``ThinkTraceClient`` wire contract (Codex H1), prompt-provenance preflight (H3),
transport-failure partial handling (Codex H5), the **no-replay_checksum + over-read
guard** invariants (Codex H2/H4), and the closed import denylist (Codex L2). No live
Ollama: a ``MockTransport`` returns synthetic ``/api/chat`` payloads.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from erre_sandbox.inference.sampling import ResolvedSampling
from erre_sandbox.integration.embodied import think_capture as tc
from erre_sandbox.integration.embodied.loop import RecordedLlmCall

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_DIR = _REPO_ROOT / "experiments" / "20260706-ecl-v0-live-capture" / "artifacts"
_SAMPLING = ResolvedSampling(temperature=0.7, top_p=0.9, repeat_penalty=1.1)

_FORBIDDEN_OUTPUT_KEYS = frozenset(
    {
        "marker_count",
        "marker_rate",
        "rate",
        "rank",
        "score",
        "success",
        "aha",
        "aha_proxy",
        "verdict",
        "floor",
        "pass",
        "fail",
        "pass_fail",
        "divergence",
        "landscape",
        "replay_checksum",
    }
)


def _call(
    i: int, *, system: str | None = None, user: str | None = None
) -> RecordedLlmCall:
    return RecordedLlmCall(
        system_prompt=system
        if system is not None
        else f"Persona: Immanuel Kant. tick {i}",
        user_prompt=user if user is not None else f"observe and decide {i}",
        sampling=_SAMPLING,
    )


def _mock_client(handler: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url="http://mock", transport=httpx.MockTransport(handler)
    )


def _payload(
    message: dict[str, Any], *, done_reason: str = "stop", eval_count: int = 12
) -> dict[str, Any]:
    return {"message": message, "done_reason": done_reason, "eval_count": eval_count}


def _all_keys(obj: Any) -> set[str]:
    """Every dict key appearing anywhere in a nested structure."""
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys |= _all_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            keys |= _all_keys(v)
    return keys


# --------------------------------------------------------------------------- #
# extract_thinking — 3 paths + edge cases (Codex M4)
# --------------------------------------------------------------------------- #


def test_extract_thinking_field() -> None:
    ex = tc.extract_thinking(
        {"thinking": "let me weigh the options", "content": "{}"}, "{}"
    )
    assert ex.source == "field"
    assert ex.parseable is True
    assert ex.key_present is True
    assert ex.char_count > 0
    assert ex.embedded_parse_status == "n/a"


def test_extract_thinking_embedded() -> None:
    content = (
        '<think>first generate, then evaluate</think>{"destination_zone": "garden"}'
    )
    ex = tc.extract_thinking({"content": content}, content)
    assert ex.source == "embedded"
    assert ex.parseable is True
    assert ex.key_present is False
    assert ex.embedded_parse_status == "ok"
    assert "generate" in ex.thinking


def test_extract_thinking_none() -> None:
    ex = tc.extract_thinking({"content": "just an answer"}, "just an answer")
    assert ex.source == "none"
    assert ex.parseable is False
    assert ex.char_count == 0


def test_extract_thinking_field_present_but_empty() -> None:
    ex = tc.extract_thinking({"thinking": "   ", "content": "answer"}, "answer")
    assert ex.key_present is True
    assert ex.source == "none"
    assert ex.parseable is False


def test_extract_thinking_embedded_parse_failure() -> None:
    content = "<think>opened but never closed"
    ex = tc.extract_thinking({"content": content}, content)
    assert ex.source == "none"
    assert ex.embedded_parse_status == "failed"
    assert ex.parseable is False


# --------------------------------------------------------------------------- #
# ThinkTraceClient wire contract (Codex H1) — request body + top-level parse
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_think_trace_client_request_body_and_parse() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(
            200,
            json=_payload(
                {"thinking": "reason", "content": "answer"},
                done_reason="length",
                eval_count=42,
            ),
        )

    client = tc.ThinkTraceClient(model="qwen3:8b", client=_mock_client(handler))
    try:
        raw = await client.capture(
            system_prompt="sys", user_prompt="usr", sampling=_SAMPLING, num_predict=999
        )
    finally:
        await client.close()

    # request body (Codex H1): stream False + think True + fixed options.
    assert seen["stream"] is False
    assert seen["think"] is True
    assert seen["model"] == "qwen3:8b"
    assert seen["messages"][0]["role"] == "system"
    assert seen["messages"][1]["role"] == "user"
    assert seen["options"]["temperature"] == pytest.approx(0.7)
    assert seen["options"]["num_predict"] == 999
    # top-level parse: done_reason -> finish_reason mapping.
    assert raw.content == "answer"
    assert raw.eval_count == 42
    assert raw.finish_reason == "length"
    assert raw.raw_message["thinking"] == "reason"


@pytest.mark.asyncio
async def test_think_trace_client_transport_error_on_http_500() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    client = tc.ThinkTraceClient(model="qwen3:8b", client=_mock_client(handler))
    try:
        with pytest.raises(tc.ThinkCaptureTransportError):
            await client.capture(
                system_prompt="s", user_prompt="u", sampling=_SAMPLING, num_predict=10
            )
    finally:
        await client.close()


# --------------------------------------------------------------------------- #
# run_think_capture — records + partial-on-transport-failure (Codex H5)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_run_think_capture_collects_records() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_payload({"thinking": "t", "content": "c"}))

    client = tc.ThinkTraceClient(model="m", client=_mock_client(handler))
    try:
        records = await tc.run_think_capture(
            prompts=[_call(0), _call(1), _call(2)], client=client, num_predict=64
        )
    finally:
        await client.close()

    assert len(records) == 3
    assert [r.source_index for r in records] == [0, 1, 2]
    for r in records:
        assert r.thinking_parseable is True
        assert r.system_prompt_sha256
        assert r.user_prompt_sha256
        assert r.source_call_sha256
        assert r.capture_sampling["think"] is True
        assert r.capture_sampling["num_predict"] == 64
        assert "temperature" in r.source_sampling


@pytest.mark.asyncio
async def test_run_think_capture_partial_on_transport_failure() -> None:
    state = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        if state["n"] == 2:
            return httpx.Response(503, text="down")
        return httpx.Response(200, json=_payload({"thinking": "t", "content": "c"}))

    client = tc.ThinkTraceClient(model="m", client=_mock_client(handler))
    try:
        with pytest.raises(tc.ThinkCapturePartialError) as excinfo:
            await tc.run_think_capture(
                prompts=[_call(0), _call(1), _call(2)], client=client, num_predict=64
            )
    finally:
        await client.close()
    err = excinfo.value
    assert err.index == 1
    assert len(err.records) == 1  # first prompt captured before the failure


# --------------------------------------------------------------------------- #
# Prompt-provenance preflight (Codex H3)
# --------------------------------------------------------------------------- #


def _read_source() -> tuple[str, dict[str, Any]]:
    decisions = (_SOURCE_DIR / "decisions.jsonl").read_text(encoding="utf-8")
    manifest = json.loads((_SOURCE_DIR / "manifest.json").read_text(encoding="utf-8"))
    return decisions, manifest


def test_validate_prompt_provenance_happy_path() -> None:
    decisions, manifest = _read_source()
    prov = tc.validate_prompt_provenance(decisions_text=decisions, manifest=manifest)
    assert prov.n_source_calls == tc.PHASE3_N_PROMPTS
    assert prov.persona == "kant"
    assert prov.source_manifest_checksum == manifest["replay_checksum"]
    block = prov.block()
    assert block["source_decisions_sha256"] == prov.source_decisions_sha256
    assert (
        "replay_checksum" not in block
    )  # Codex H2: source_manifest_checksum, not replay_checksum


def test_validate_prompt_provenance_rejects_wrong_n() -> None:
    decisions, manifest = _read_source()
    truncated = "\n".join(decisions.splitlines()[:5]) + "\n"
    # Drop the manifest integrity sha so the N-check is what fires.
    manifest2 = {**manifest, "artifacts": {}}
    with pytest.raises(tc.ProvenanceError):
        tc.validate_prompt_provenance(decisions_text=truncated, manifest=manifest2)


def test_validate_prompt_provenance_rejects_sha_mismatch() -> None:
    decisions, manifest = _read_source()
    bad = {**manifest, "artifacts": {"decisions.jsonl": {"sha256": "deadbeef"}}}
    with pytest.raises(tc.ProvenanceError):
        tc.validate_prompt_provenance(decisions_text=decisions, manifest=bad)


def test_validate_prompt_provenance_rejects_wrong_persona() -> None:
    decisions, _ = _read_source()
    lines = decisions.splitlines()
    first = json.loads(lines[0])
    first["call"]["system_prompt"] = "Persona: Somebody Else (fake)."
    lines[0] = json.dumps(first, ensure_ascii=False)
    mutated = "\n".join(lines) + "\n"
    with pytest.raises(tc.ProvenanceError):
        tc.validate_prompt_provenance(
            decisions_text=mutated, manifest={"artifacts": {}}
        )


def test_validate_prompt_provenance_rejects_empty_prompt() -> None:
    decisions, _ = _read_source()
    lines = decisions.splitlines()
    first = json.loads(lines[0])
    first["call"]["user_prompt"] = "   "
    lines[0] = json.dumps(first, ensure_ascii=False)
    mutated = "\n".join(lines) + "\n"
    with pytest.raises(tc.ProvenanceError):
        tc.validate_prompt_provenance(
            decisions_text=mutated, manifest={"artifacts": {}}
        )


# --------------------------------------------------------------------------- #
# Manifest: no Phase 3 replay_checksum (H2) + over-read guard (H4)
# --------------------------------------------------------------------------- #


def _records(n: int = 3) -> tuple[tc.ThinkCaptureRecord, ...]:
    out = []
    for i in range(n):
        raw = tc.RawThinkResponse(
            raw_message={"thinking": "t", "content": "c"},
            content="c",
            eval_count=1,
            done_reason="length" if i == 0 else "stop",
            finish_reason="length" if i == 0 else "stop",
        )
        out.append(
            tc._record_from_capture(
                source_index=i, call=_call(i), raw=raw, num_predict=64
            )
        )
    return tuple(out)


def test_manifest_has_no_replay_checksum_and_no_forbidden_keys() -> None:
    decisions, manifest = _read_source()
    prov = tc.validate_prompt_provenance(decisions_text=decisions, manifest=manifest)
    records = _records()
    env_pins = tc.build_phase3_env_pins(
        qwen3_model_digest="sha",
        ollama_version="0.21.0",
        vram_gb=11.0,
        uv_lock_sha256="x",
    )
    m = tc.build_phase3_manifest(provenance=prov, records=records, env_pins=env_pins)
    keys = _all_keys(m)
    assert "replay_checksum" not in keys  # Codex H2
    assert keys.isdisjoint(_FORBIDDEN_OUTPUT_KEYS)  # Codex H4 over-read guard
    # source_manifest_checksum is allowed: it is the ecl_v0 prompt-source checksum,
    # not a Phase 3 trace replay.
    assert (
        m["prompt_provenance"]["source_manifest_checksum"]
        == manifest["replay_checksum"]
    )
    assert (
        "not a Phase 3 trace replay" in m["nondeterminism_note"]
        or "NOT a" in m["nondeterminism_note"]
    )


def test_record_to_dict_has_no_forbidden_keys() -> None:
    for r in _records():
        assert _all_keys(r.to_dict()).isdisjoint(_FORBIDDEN_OUTPUT_KEYS)


def test_mechanical_counts_are_technical_only() -> None:
    records = _records(3)
    counts = tc.mechanical_counts(records)
    assert counts == {"total": 3, "thinking_parseable": 3, "finish_length": 1}
    assert set(counts).isdisjoint(_FORBIDDEN_OUTPUT_KEYS)


def test_records_to_jsonl_roundtrip() -> None:
    records = _records(2)
    text = tc.records_to_jsonl(records)
    lines = [json.loads(ln) for ln in text.splitlines() if ln.strip()]
    assert len(lines) == 2
    assert lines[0]["source_index"] == 0
    assert lines[0]["thinking_source"] == "field"


# --------------------------------------------------------------------------- #
# surface_reconsideration_markers — excerpt inventory only (Codex H4)
# --------------------------------------------------------------------------- #


def test_surface_markers_returns_excerpts_not_counts() -> None:
    thinking = "Let me go to garden. Wait, actually the study is better on reflection."
    excerpts = tc.surface_reconsideration_markers(thinking)
    assert isinstance(excerpts, tuple)
    assert len(excerpts) >= 1
    assert all(isinstance(e, str) for e in excerpts)


def test_surface_markers_empty_when_absent() -> None:
    assert tc.surface_reconsideration_markers("I will go to the garden now.") == ()


# --------------------------------------------------------------------------- #
# Scope guard — closed import denylist (Codex L2), exact modules only
# --------------------------------------------------------------------------- #

_DENY_SUBSTRINGS = ("evidence", "spdm", "runningness", "es2_replay")


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
            mods |= {f"{node.module}.{a.name}" for a in node.names}
    return mods


@pytest.mark.parametrize(
    "rel",
    [
        "src/erre_sandbox/integration/embodied/think_capture.py",
        "scripts/aha_phase3_think_capture.py",
    ],
)
def test_no_measurement_line_imports(rel: str) -> None:
    mods = _imported_modules(_REPO_ROOT / rel)
    for m in mods:
        assert not any(bad in m for bad in _DENY_SUBSTRINGS), (
            f"{rel} imports forbidden module {m}"
        )
    # handoff import IS allowed (design requires recorded_calls_from_jsonl) — Codex L2.
    assert any("handoff" in m for m in mods)
