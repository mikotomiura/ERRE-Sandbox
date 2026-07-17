"""aha!/DMN-ECN Phase 4b — committed sealed-run bundle replay-verify (CI leg).

Replays the *committed* run-2 artifacts
(``experiments/20260717-aha-phase4b-construction-validation-live/artifacts/``) with
no live Ollama, so CI reproduces the sealed run's V2/V3a on Linux and confirms the
firing witness survives on the committed bundle (mirrors
``test_ecl_v1_live_golden.py``). The in-memory apparatus mechanics live in
``test_two_phase_live.py``; this module is the committed-bundle reproducibility gate.

Scope guard (design-final §7, binding). Construction validation only: it asserts
reproducibility (checksum byte-match, ``inner_invocations == 0``) and the boolean
firing witness (evaluation-phase sign inversion), never a floor / verdict /
divergence / magnitude / detectability statistic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, cast

import httpx

from erre_sandbox.erre.two_phase import TwoPhaseKnob
from erre_sandbox.integration.embodied import handoff
from erre_sandbox.integration.embodied.live_v1 import SamplingSpyChatClient
from erre_sandbox.integration.embodied.loop import RecordReplayChatClient
from erre_sandbox.integration.embodied.two_phase_live import (
    evaluation_seeded_agent_state,
    run_two_phase_capture,
    two_phase_firing_summary,
)
from erre_sandbox.memory import EmbeddingClient, MemoryStore

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.erre.two_phase import TwoPhaseKnob as _Knob
    from erre_sandbox.inference.sampling import ResolvedSampling
    from erre_sandbox.integration.embodied.loop import EclRunResult, RecordedLlmCall
    from erre_sandbox.schemas import AgentState

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ARTIFACT_DIR = (
    _REPO_ROOT
    / "experiments"
    / "20260717-aha-phase4b-construction-validation-live"
    / "artifacts"
)


def _mock_embedding() -> EmbeddingClient:
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


def _load_bundle() -> tuple[dict[str, object], list[RecordedLlmCall]]:
    manifest = json.loads((_ARTIFACT_DIR / "manifest.json").read_text(encoding="utf-8"))
    decisions_text = (_ARTIFACT_DIR / "decisions.jsonl").read_text(encoding="utf-8")
    recorded = handoff.recorded_calls_from_jsonl(decisions_text)
    return manifest, recorded


async def _replay(
    *,
    recorded: Sequence[RecordedLlmCall],
    run_config: dict[str, object],
    agent_state: AgentState,
    two_phase_knob: _Knob | None,
    spy: bool,
) -> tuple[EclRunResult, RecordReplayChatClient | SamplingSpyChatClient]:
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    from datetime import datetime

    inner = RecordReplayChatClient(recorded=recorded)
    llm: RecordReplayChatClient | SamplingSpyChatClient = (
        SamplingSpyChatClient(inner) if spy else inner
    )
    try:
        result = await run_two_phase_capture(
            run_id=str(run_config["run_id"]),
            store=store,
            embedding=embedding,
            llm=cast("RecordReplayChatClient", llm),
            agent_state=agent_state,
            persona=handoff.golden_persona(),
            retrieval_now=datetime.fromisoformat(str(run_config["retrieval_now"])),
            base_ts=datetime.fromisoformat(str(run_config["base_ts"])),
            two_phase_knob=two_phase_knob,
            seed=int(cast("int", run_config["seed"])),
            n_cognition_ticks=int(cast("int", run_config["cognition_ticks"])),
            physics_ticks_per_cognition=int(
                cast("int", run_config["physics_ticks_per_cognition"])
            ),
            k_ecl=int(cast("int", run_config["k_ecl"])),
        )
    finally:
        await embedding.close()
        await store.close()
    return result, llm


async def test_committed_bundle_replays_deterministically() -> None:
    """V2/V3a: the committed decisions replay to the committed checksum, no live LLM."""
    manifest, recorded = _load_bundle()
    run_config = cast("dict[str, object]", manifest["run"])
    result, llm = await _replay(
        recorded=recorded,
        run_config=run_config,
        agent_state=evaluation_seeded_agent_state(),
        two_phase_knob=TwoPhaseKnob(),
        spy=False,
    )
    assert llm.inner_invocations == 0, "replay must never touch a live LLM"
    assert result.checksum == manifest["replay_checksum"], (
        "committed decisions must replay to the committed replay_checksum"
    )


async def test_committed_bundle_firing_witness() -> None:
    """The committed run-2 bundle carries the evaluation-phase firing witness."""
    manifest, recorded = _load_bundle()
    run_config = cast("dict[str, object]", manifest["run"])
    on_result, on_spy = await _replay(
        recorded=recorded,
        run_config=run_config,
        agent_state=evaluation_seeded_agent_state(),
        two_phase_knob=TwoPhaseKnob(),
        spy=True,
    )
    off_result, off_spy = await _replay(
        recorded=recorded,
        run_config=run_config,
        agent_state=evaluation_seeded_agent_state(),
        two_phase_knob=None,
        spy=True,
    )
    assert isinstance(on_spy, SamplingSpyChatClient)
    assert isinstance(off_spy, SamplingSpyChatClient)
    on_sampling: tuple[ResolvedSampling, ...] = on_spy.sampled
    off_sampling: tuple[ResolvedSampling, ...] = off_spy.sampled
    assert len(on_sampling) == len(recorded)

    summary = two_phase_firing_summary(
        on_samplings=on_sampling,
        off_samplings=off_sampling,
        on_checksum=on_result.checksum,
        off_checksum=off_result.checksum,
        committed_call_samplings=[c.sampling for c in recorded],
    )
    assert summary["evaluation_phase_sign_inversion_fired"] is True
    assert summary["witness_tick_count"] >= 1
    assert summary["checksums_match"] is True
    assert summary["record_knob_on_pinned"] is True, "the committed record ran knob-on"
    assert summary["fail_mode"] is None
    assert summary["verdict"] is None


def test_committed_manifest_knob_on_and_gate_free() -> None:
    """The committed manifest pins knob-on + carries no measurement gate."""
    manifest, _recorded = _load_bundle()
    env_pins = cast("dict[str, object]", manifest["env_pins"])
    assert env_pins["two_phase_knob"] == "on"
    assert env_pins["think"] is False
    observables = cast("dict[str, object]", manifest["observables"])
    assert observables["verdict"] is None
    # The committed firing annotation is a side file, outside the manifest SHA set.
    committed = json.loads(
        (_ARTIFACT_DIR / "two_phase_firing_annotation.json").read_text(encoding="utf-8")
    )
    assert committed["verdict"] is None
    assert committed["hard_gate"] is False
    assert committed["evaluation_phase_sign_inversion_fired"] is True
    assert "two_phase_firing_annotation.json" not in manifest["artifacts"], (
        "the firing annotation must not be in the manifest SHA set (side file)"
    )
