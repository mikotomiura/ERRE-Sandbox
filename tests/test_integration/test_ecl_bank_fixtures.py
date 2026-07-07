"""ECL B — Issue 001 tests: competing-cue fixture + frozen-context provenance pass.

Issue ``loop/20260708-m13-b-code-impl/issues/001-competing-cue-provenance.md``
of the FROZEN ADR ``.steering/20260707-m13-b-impl-design/design-final.md``
(§I1 lever / §I3 frozen schema / §I7 T3 materiality). Ollama-free throughout —
every provenance-pass test drives a mock inner chat client through the
untouched :func:`~erre_sandbox.integration.embodied.loop.run_ecl_loop`.

Scope guard (§I9, mirrors ``test_ecl_v1_locomotion.py`` /
``test_ecl_live_capture.py``): this module tests *construction*, never
measurement — no ``H(zone|ctx)`` / diversity / divergence assertion appears
here (that boundary belongs to Issue 003's ast-guard, §I4).
"""

from __future__ import annotations

import ast
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from erre_sandbox.cognition import cycle as cognition_cycle
from erre_sandbox.inference.ollama_adapter import ChatResponse
from erre_sandbox.integration.embodied import bank_fixtures
from erre_sandbox.integration.embodied.bank_fixtures import (
    BANK_LAMBDA_CTX,
    BANK_NEUTRAL_ZONE,
    BANK_Z_COMP,
    ZONE_BIAS_ENV_VAR,
    build_competing_cue_substrate,
    run_provenance_pass,
)
from erre_sandbox.memory import EmbeddingClient, MemoryStore

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pytest

    from erre_sandbox.inference.ollama_adapter import ChatMessage
    from erre_sandbox.inference.sampling import ResolvedSampling

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BANK_FIXTURES_SRC = (
    _REPO_ROOT
    / "src"
    / "erre_sandbox"
    / "integration"
    / "embodied"
    / "bank_fixtures.py"
)

_FIXED_CLOCK = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

_PLAN_JSON = json.dumps(
    {
        "thought": "which zone calls to me?",
        "utterance": "どちらへ行こうか",
        "destination_zone": "study",
        "animation": "walk",
    }
)


# --------------------------------------------------------------------------- #
# Ollama-free fixtures (mirror test_ecl_live_capture.py / test_ecl_v1_locomotion.py)
# --------------------------------------------------------------------------- #


def _mock_embedding() -> EmbeddingClient:
    """Constant-vector embedding (Ollama-free)."""
    vec = [0.01] * EmbeddingClient.DEFAULT_DIM

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


@dataclass
class _MockInnerChat:
    """Ollama-free inner chat that re-serves a fixed plan every call."""

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


def _store_factory() -> MemoryStore:
    return MemoryStore(db_path=":memory:")


async def _run_pass(*, embedding: EmbeddingClient, inner: Any | None = None) -> Any:
    substrate = build_competing_cue_substrate()
    return await run_provenance_pass(
        substrate=substrate,
        inner_chat=inner or _MockInnerChat(),
        store_factory=_store_factory,
        embedding=embedding,
        run_id="bank-i1-test",
        retrieval_now=_FIXED_CLOCK,
        base_ts=_FIXED_CLOCK,
    )


# --------------------------------------------------------------------------- #
# I1-G1 — cue constants literal-pin (forking-paths seal)
# --------------------------------------------------------------------------- #


def test_bank_cue_constants_literal_pin() -> None:
    """Literal cue constants, no ``evidence.*`` import (§I1, forking-paths seal)."""
    assert BANK_Z_COMP == (bank_fixtures.Zone.STUDY, bank_fixtures.Zone.GARDEN)
    assert BANK_NEUTRAL_ZONE == bank_fixtures.Zone.AGORA
    assert BANK_LAMBDA_CTX == (0.4,)
    assert BANK_NEUTRAL_ZONE not in BANK_Z_COMP

    src = _BANK_FIXTURES_SRC.read_text(encoding="utf-8")
    assert "erre_sandbox.evidence" not in src

    tree = ast.parse(src)
    assigned_names = {
        node.target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    for name in ("BANK_Z_COMP", "BANK_NEUTRAL_ZONE", "BANK_LAMBDA_CTX"):
        assert name in assigned_names, (
            f"{name} must be a module-level AnnAssign literal"
        )


# --------------------------------------------------------------------------- #
# I1-G2 — canonical-inputs-only (T3 materiality criterion 1)
# --------------------------------------------------------------------------- #

_BANNED_PROMPT_SUBSTRINGS: tuple[str, ...] = (
    "Respond with a SINGLE JSON object",
    "Recent observations:",
    "Relevant memories:",
    "Decide what to do in the next ten seconds",
    "You are an autonomous agent living in ERRE-Sandbox",
)

_CANONICAL_SCHEMA_TYPES: tuple[str, ...] = (
    "AgentState",
    "PersonaSpec",
    "AffordanceEvent",
    "ZoneTransitionEvent",
    "MemoryEntry",
)


def test_bank_cue_canonical_inputs_only() -> None:
    """No hand-written prompt string; canonical types built via ``model_validate``
    only; the canonical builders are never called from this module (T3 criterion 1,
    §I7 — the organ alone renders the prompt)."""
    src = _BANK_FIXTURES_SRC.read_text(encoding="utf-8")
    tree = ast.parse(src)

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for banned in _BANNED_PROMPT_SUBSTRINGS:
                assert banned not in node.value, (
                    f"manual prompt string literal detected: {node.value!r}"
                )

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            called_name = (
                func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            )
            assert called_name not in {"build_system_prompt", "build_user_prompt"}, (
                "bank_fixtures.py must not render the prompt itself — only the "
                "live organ's canonical builder may"
            )
            # Canonical schema types must be constructed via ``.model_validate(``
            # (an ast.Attribute call), never a bare direct call (ast.Name call).
            if isinstance(func, ast.Name):
                assert func.id not in _CANONICAL_SCHEMA_TYPES, (
                    f"{func.id} must be constructed via .model_validate(...), "
                    "not called directly (T3 materiality criterion 1)"
                )


# --------------------------------------------------------------------------- #
# I1-G3 — structural symmetry (same salience/count, zone-only difference) +
# content-mirrored memory
# --------------------------------------------------------------------------- #


def test_bank_cue_symmetric() -> None:
    """Each Z_comp zone gets one structurally identical affordance +
    zone_transition cue and one content-mirrored memory (§I1.1/§I3.1)."""
    substrate = build_competing_cue_substrate()

    affordances = [o for o in substrate.observations if o.event_type == "affordance"]
    transitions = [
        o for o in substrate.observations if o.event_type == "zone_transition"
    ]
    assert len(affordances) == len(BANK_Z_COMP)
    assert len(transitions) == len(BANK_Z_COMP)
    assert {a.zone for a in affordances} == set(BANK_Z_COMP)
    assert {t.to_zone for t in transitions} == set(BANK_Z_COMP)
    assert all(t.from_zone == BANK_NEUTRAL_ZONE for t in transitions)
    # Same salience / same distance across every zone — only zone-derived
    # fields (prop_id / zone / to_zone) differ.
    assert len({a.salience for a in affordances}) == 1
    assert len({a.distance for a in affordances}) == 1
    assert len({a.prop_kind for a in affordances}) == 1

    assert len(substrate.memories) == len(BANK_Z_COMP)
    assert len({m.strength for m in substrate.memories}) == 1
    assert len({m.cosine_sim for m in substrate.memories}) == 1
    assert len({m.entry.kind for m in substrate.memories}) == 1
    assert len({m.entry.importance for m in substrate.memories}) == 1
    # Content mirrors the zone (distinct per zone, each mentions its own zone).
    assert len({m.entry.content for m in substrate.memories}) == len(BANK_Z_COMP)
    for zone, memory in zip(BANK_Z_COMP, substrate.memories, strict=True):
        assert zone.value in memory.entry.content


# --------------------------------------------------------------------------- #
# I1-G4 — provenance pass renders through the canonical builder (organ-owned)
# --------------------------------------------------------------------------- #


async def test_bank_provenance_pass_uses_canonical_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The rendered (system_prompt, user_prompt) are exactly what
    ``cognition.prompting.build_system_prompt`` / ``build_user_prompt`` produced
    *inside* the untouched cycle — proven by spying the organ's own call sites,
    not by re-deriving the prompt independently."""
    orig_system = cognition_cycle.build_system_prompt
    orig_user = cognition_cycle.build_user_prompt
    captured_system: list[str] = []
    captured_user: list[str] = []

    def spy_system(persona: Any, agent: Any) -> str:
        result = orig_system(persona, agent)
        captured_system.append(result)
        return result

    def spy_user(observations: Any, memories: Any, **kwargs: Any) -> str:
        result = orig_user(observations, memories, **kwargs)
        captured_user.append(result)
        return result

    monkeypatch.setattr(cognition_cycle, "build_system_prompt", spy_system)
    monkeypatch.setattr(cognition_cycle, "build_user_prompt", spy_user)

    embedding = _mock_embedding()
    try:
        frozen = await _run_pass(embedding=embedding)
    finally:
        await embedding.close()

    # One full-cycle pass per condition (T_on, T_off) => two canonical-builder
    # invocations of each, in order.
    assert len(captured_system) == 2
    assert len(captured_user) == 2
    assert frozen.system_prompt == captured_system[0]
    assert frozen.user_prompt == captured_user[0]


# --------------------------------------------------------------------------- #
# I1-G5 — zone bias pinned off (§I1.4, Codex 事実誤認 HIGH-1)
# --------------------------------------------------------------------------- #


def test_bank_zone_bias_pin_sets_and_restores() -> None:
    """``_pinned_zone_bias_off`` pins ``ERRE_ZONE_BIAS_P=0`` and restores the
    prior value on exit, even when the prior value would have caused a bias
    resample (hostile default simulation)."""
    prior = os.environ.get(ZONE_BIAS_ENV_VAR)
    os.environ[ZONE_BIAS_ENV_VAR] = "1.0"
    try:
        with bank_fixtures._pinned_zone_bias_off():  # sanctioned internal test
            assert os.environ[ZONE_BIAS_ENV_VAR] == "0"
        assert os.environ[ZONE_BIAS_ENV_VAR] == "1.0"
    finally:
        if prior is None:
            os.environ.pop(ZONE_BIAS_ENV_VAR, None)
        else:
            os.environ[ZONE_BIAS_ENV_VAR] = prior


async def test_bank_provenance_bias_off() -> None:
    """A full provenance pass succeeds (no internal ``bias_fired`` assertion
    fires) even when the ambient env var would otherwise enable a 100% bias
    resample — the pin, not persona luck, is what guarantees it."""
    prior = os.environ.get(ZONE_BIAS_ENV_VAR)
    os.environ[ZONE_BIAS_ENV_VAR] = "1.0"
    embedding = _mock_embedding()
    try:
        frozen = await _run_pass(embedding=embedding)
        assert frozen.frozen_ctx_id == "bank-ctx-0"
        # The ambient env var is restored to its hostile value right after the
        # pass (the pin only holds for the pass's own scope).
        assert os.environ.get(ZONE_BIAS_ENV_VAR) == "1.0"
    finally:
        await embedding.close()
        if prior is None:
            os.environ.pop(ZONE_BIAS_ENV_VAR, None)
        else:
            os.environ[ZONE_BIAS_ENV_VAR] = prior


# --------------------------------------------------------------------------- #
# I1-G6 — frozen context prompt identity across T_on/T_off (§I3.3)
# --------------------------------------------------------------------------- #


async def test_bank_frozen_context_prompt_identity() -> None:
    """T_on/T_off render byte-identical prompts; only sampling differs (§I3.3:
    λ never enters either canonical builder's output)."""
    substrate = build_competing_cue_substrate()
    embedding = _mock_embedding()
    try:
        agent_on = substrate.agent_state.model_copy(
            update={"locomotion": bank_fixtures.LocomotionState(lam=BANK_LAMBDA_CTX[0])}
        )
        agent_off = substrate.agent_state.model_copy(update={"locomotion": None})

        result_on = await bank_fixtures._run_condition(
            substrate=substrate,
            agent_state=agent_on,
            inner_chat=_MockInnerChat(),
            store_factory=_store_factory,
            embedding=embedding,
            run_id="bank-i1-g6-on",
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
            seed=0,
        )
        result_off = await bank_fixtures._run_condition(
            substrate=substrate,
            agent_state=agent_off,
            inner_chat=_MockInnerChat(),
            store_factory=_store_factory,
            embedding=embedding,
            run_id="bank-i1-g6-off",
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
            seed=0,
        )

        assert (
            result_on.decisions[0].call.system_prompt
            == result_off.decisions[0].call.system_prompt
        )
        assert (
            result_on.decisions[0].call.user_prompt
            == result_off.decisions[0].call.user_prompt
        )
        # sampling differs between the two conditions (the whole point of the
        # locomotion channel modulating something).
        assert (
            result_on.decisions[0].call.sampling
            != result_off.decisions[0].call.sampling
        )

        frozen = await _run_pass(embedding=embedding)
        assert frozen.system_prompt == result_on.decisions[0].call.system_prompt
        assert frozen.user_prompt == result_on.decisions[0].call.user_prompt
        assert frozen.sampling_on == result_on.decisions[0].call.sampling
        assert frozen.sampling_off == result_off.decisions[0].call.sampling
        assert frozen.sampling_on != frozen.sampling_off
    finally:
        await embedding.close()


# --------------------------------------------------------------------------- #
# I1-G7 — mirror memory content (§I1.1(d)) actually renders into the frozen
# prompt, symmetrically across Z_comp (via the canonical retriever→format_memories
# path, not a hand-written string)
# --------------------------------------------------------------------------- #


async def test_bank_frozen_prompt_contains_symmetric_mirror_memory() -> None:
    """Each Z_comp zone's mirror-memory content is present in the frozen prompt
    and structurally isomorphic across zones (§I1.1(d) — the lever's 4th
    dimension actually reaches the prompt). Boolean present/symmetric checks
    only; no distinct-zone count / diversity aggregation (§I4/§I9)."""
    substrate = build_competing_cue_substrate()
    embedding = _mock_embedding()
    try:
        frozen = await _run_pass(embedding=embedding)
    finally:
        await embedding.close()

    prompt = frozen.user_prompt

    # (a) present: every Z_comp zone's mirror content appears verbatim.
    for memory in substrate.memories:
        assert memory.entry.content in prompt, (
            f"mirror memory content missing from frozen prompt: "
            f"{memory.entry.content!r}"
        )
    # And each zone name is mentioned by its own mirror content.
    for zone, memory in zip(BANK_Z_COMP, substrate.memories, strict=True):
        assert zone.value in memory.entry.content
        assert zone.value in prompt

    # (b) symmetric: each zone's mirror content collapses to a byte-identical
    # template once its own zone token is neutralised — structural isomorphism,
    # zone name the only difference (§I1.1 symmetric construction). Pairwise
    # equality against the first template (a present/symmetric boolean, never a
    # distinct-zone count / diversity aggregation).
    normalised = [
        memory.entry.content.replace(zone.value, "<Z>")
        for zone, memory in zip(BANK_Z_COMP, substrate.memories, strict=True)
    ]
    for template in normalised[1:]:
        assert template == normalised[0], (
            "mirror memory contents are not structurally isomorphic across "
            "Z_comp (they differ by more than the zone token)"
        )
