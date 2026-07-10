"""C-proper live capture harness — Ollama-free dry-run (capture → verify → verdict).

Exercises ``scripts.ecl_bank_cproper_capture`` end-to-end with a deterministic
in-process mock injected into the M-loop seam (``inner_chat``), so CI never needs a
live Ollama. Confirms: the powered-shaped bundle round-trips (replay
``inner_invocations == 0``, byte-identical records), the frozen scorer emits a
``verdict.json``, and the manifest pins ``think=False`` + a cost ceiling. The live
powered run itself (real qwen3:8b, M=300·K=8) is the separate human-gated spend.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts import ecl_bank_cproper_capture as cap

from erre_sandbox.inference.ollama_adapter import ChatResponse
from erre_sandbox.schemas import Zone

_PLAN_CYCLE = (
    Zone.STUDY.value,
    Zone.GARDEN.value,
    Zone.AGORA.value,
    None,  # exercises the pre_bias_destination_zone is None branch
    Zone.PERIPATOS.value,
)


def _plan_json(zone: str | None) -> str:
    zone_field = f'"{zone}"' if zone is not None else "null"
    return (
        '{"thought": "t", "utterance": "u", '
        f'"destination_zone": {zone_field}, "animation": "walk"}}'
    )


@dataclass
class _MloopMockChat:
    """Deterministic round-robin M-loop chat — Ollama-free."""

    calls: int = field(default=0)

    async def chat(self, *_args: Any, **_kwargs: Any) -> ChatResponse:
        content = _plan_json(_PLAN_CYCLE[self.calls % len(_PLAN_CYCLE)])
        self.calls += 1
        return ChatResponse(
            content=content, model="cproper-mock", eval_count=1, total_duration_ms=0.0
        )


def test_capture_verify_roundtrip_and_verdict(tmp_path: Path) -> None:
    rendered = asyncio.run(
        cap.capture(
            seed=0,
            m_draws=4,
            k_contexts=2,
            qwen3_model_digest="deadbeefdeadbeef",
            ollama_version="0.31.1",
            vram_gb=16.0,
            uv_lock_sha256="cafecafecafecafe",
            inner_chat=_MloopMockChat(),
        )
    )
    cap._write(tmp_path, rendered)

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    # think=False is load-bearing (H3) and must be pinned.
    assert manifest["env_pins"]["think"] is False
    assert manifest["cost_ceiling"]["max_llm_calls"] == 2 * 4 * 2
    assert manifest["run"]["m_draws"] == 4
    assert manifest["run"]["k_contexts"] == 2

    ok = asyncio.run(cap.verify(tmp_path))
    assert ok is True

    verdict = json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))
    # tiny M/K → not a real spend; scorer must still emit a well-formed verdict.
    assert verdict["scorer_schema_version"] == "ecl-cproper-scorer-1"
    assert verdict["verdict"] in {
        "INCONCLUSIVE",
        "NO_CHANNEL_CONFORMANCE",
        "INCONCLUSIVE_UNDERPOWERED",
        "CHANNEL_CONFORMANCE_DETECTED",
    }
    assert "seed" in verdict["thresholds"]


def test_verify_is_ollama_free_and_byte_identical(tmp_path: Path) -> None:
    rendered = asyncio.run(
        cap.capture(
            seed=0,
            m_draws=4,
            k_contexts=2,
            qwen3_model_digest="d",
            ollama_version="v",
            vram_gb=16.0,
            uv_lock_sha256="u",
            inner_chat=_MloopMockChat(),
        )
    )
    cap._write(tmp_path, rendered)
    records_before = (tmp_path / "bank_records.jsonl").read_text(encoding="utf-8")
    assert asyncio.run(cap.verify(tmp_path)) is True
    # verify re-renders byte-identically (no drift, no live call).
    records_after = (tmp_path / "bank_records.jsonl").read_text(encoding="utf-8")
    assert records_before == records_after
