"""M4 society-scope live-capture harness tests (design-final.md, Issue 001).

``integration/embodied/society_live.py`` is Ollama-free and testable end-to-end
with one mock inner chat client per agent — the actual live Ollama capture is
Issue 004. These tests pin:

* **AC1-G1** ``test_record_replay_byte_parity`` — a 3-agent record-mode run,
  rendered via ``handoff.render_society_golden``, replays byte-identically
  (all four rendered artifacts + ``replay_checksum`` + ``event_log_checksum``).
* **AC1-G2** ``test_replay_no_inner_invocations`` — every replay client's
  ``inner_invocations == 0``.
* **AC1-G3** ``test_think_off_forced`` — each agent's inner chat client is
  called with ``think=False`` regardless of what the cognition cycle passed.
* **AC1-G4** ``test_society_live_measurement_guard`` — ``society_live.py``
  imports no ``evidence``/``spdm``/``runningness`` machinery and defines no
  floor/verdict/scorer/divergence output identifier.
* **AC1-G5** ``test_observables_are_annotation`` — ``SOCIETY_LIVE_OBSERVABLES``
  is a frozen string/None literal (no statistical computation code), and its
  manifest overlay renders under the ``annotations`` key with no
  ``verdict``/``passed``/``score``/``floor`` key at any nesting level
  (Codex HIGH-6/§L3). This test asserts existence/type/canonical rendering
  only — no value-based pass/fail/threshold on any annotation value.
* **AC1-G6** ``test_fixed_constructors_fingerprint`` — the fixed
  agent_states/personas/observation_factory constructors produce a
  deterministic, byte-stable canonical JSON fingerprint that
  ``build_society_live_env_pins`` pins into the manifest's ``env_pins`` block
  (Codex HIGH-4/M2).
* ``test_decision_projection_fully_quantised`` — regression test for the
  判断3 superseding ADR
  (``.steering/20260712-m13-m4-society-enrichment/decisions.md``, Codex M-d):
  every float in ``society._decision_projection``'s output is quantised to 6
  decimals, including floats embedded as text inside ``envelope_provenance``'s
  pre-serialised JSON strings (the field that silently broke society.py's own
  §M4.4 "every float in the projection is quantised" invariant and caused the
  Win/Linux ``event_log_checksum`` drift this ADR fixes).
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from erre_sandbox.cognition.embodiment import K_ECL
from erre_sandbox.inference.ollama_adapter import ChatMessage, ChatResponse
from erre_sandbox.inference.sampling import ResolvedSampling
from erre_sandbox.integration.embodied import handoff, society
from erre_sandbox.integration.embodied import society_live as society_live_module
from erre_sandbox.integration.embodied.loop import DEFAULT_PHYSICS_TICKS_PER_COGNITION
from erre_sandbox.integration.embodied.society import (
    _SELF_OTHER_FRAMING,
    run_society_loop,
)
from erre_sandbox.integration.embodied.society_live import (
    KANT_AGENT_ID,
    NIETZSCHE_AGENT_ID,
    RIKYU_AGENT_ID,
    SOCIETY_LIVE_AGENT_IDS,
    SOCIETY_LIVE_N_COGNITION_TICKS,
    SOCIETY_LIVE_OBSERVABLES,
    SOCIETY_LIVE_RUN_ID,
    apply_self_other_env_pin,
    attach_society_live_observables,
    build_society_live_env_pins,
    fixed_constructor_fingerprint,
    run_society_live_capture,
    society_live_agent_states,
    society_live_observation_factories,
    society_live_personas,
)
from erre_sandbox.memory import EmbeddingClient, MemoryStore

if TYPE_CHECKING:
    from collections.abc import Sequence

_FIXED = datetime(2026, 1, 1, tzinfo=UTC)
_PLAN_JSON = json.dumps(
    {
        "thought": "walk the peripatos",
        "utterance": "散歩へ",
        "destination_zone": "peripatos",
        "animation": "walk",
    }
)
_N_TICKS = 3
_PHYSICS_TICKS = 4


@dataclass
class _ScriptedInner:
    """Mock inner chat client returning a fixed ``ChatResponse``, call-recording."""

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


def _embed_client() -> EmbeddingClient:
    import httpx

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


def _run_config() -> dict[str, Any]:
    return {
        "seed": 0,
        "physics_ticks_per_cognition": _PHYSICS_TICKS,
        "k_ecl": K_ECL,
        "base_ts": _FIXED.isoformat(),
        "retrieval_now": _FIXED.isoformat(),
    }


async def _capture(
    inner_chats: dict[str, _ScriptedInner] | None = None,
    *,
    self_other_enabled: bool = False,
) -> tuple[Any, dict[str, _ScriptedInner]]:
    agent_states = society_live_agent_states()
    personas = society_live_personas()
    inners = inner_chats or {
        agent_id: _ScriptedInner() for agent_id in SOCIETY_LIVE_AGENT_IDS
    }
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _embed_client()
    try:
        result = await run_society_live_capture(
            inner_chats=inners,
            store=store,
            embedding=embedding,
            run_id=SOCIETY_LIVE_RUN_ID,
            agent_states=agent_states,
            personas=personas,
            retrieval_now=_FIXED,
            base_ts=_FIXED,
            n_cognition_ticks=_N_TICKS,
            physics_ticks_per_cognition=_PHYSICS_TICKS,
            observation_factories=society_live_observation_factories(),
            self_other_enabled=self_other_enabled,
        )
        return result, inners
    finally:
        await embedding.close()
        await store.close()


async def _replay(result: Any) -> Any:
    agent_states = society_live_agent_states()
    personas = society_live_personas()
    replay_clients = result.replay_clients()
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _embed_client()
    try:
        return (
            await run_society_loop(
                run_id=SOCIETY_LIVE_RUN_ID,
                store=store,
                embedding=embedding,
                llms=replay_clients,
                agent_states=agent_states,
                personas=personas,
                retrieval_now=_FIXED,
                base_ts=_FIXED,
                n_cognition_ticks=_N_TICKS,
                physics_ticks_per_cognition=_PHYSICS_TICKS,
                observation_factories=society_live_observation_factories(),
            ),
            replay_clients,
        )
    finally:
        await embedding.close()
        await store.close()


# --------------------------------------------------------------------------- #
# AC1-G1 — record -> replay byte parity (all rendered artifacts + checksums)
# --------------------------------------------------------------------------- #


async def test_record_replay_byte_parity() -> None:
    recorded, _inners = await _capture()
    rendered = handoff.render_society_golden(
        recorded, run_config=_run_config(), env_pins={"pinned": "test"}
    )

    replayed, _replay_clients = await _replay(recorded)
    rendered_replayed = handoff.render_society_golden(
        replayed, run_config=_run_config(), env_pins={"pinned": "test"}
    )

    assert rendered == rendered_replayed
    assert recorded.checksum == replayed.checksum
    assert recorded.event_log_checksum == replayed.event_log_checksum


# --------------------------------------------------------------------------- #
# 判断3 (superseding ADR, Codex M-d) — decision projection is fully quantised,
# including floats embedded as text inside envelope_provenance JSON strings.
# --------------------------------------------------------------------------- #

_LONG_DECIMAL_FLOAT_RE = re.compile(r"-?\d+\.\d{7,}")
"""Matches a decimal literal with more than 6 fractional digits — the shape a
full-precision (un-quantised) float renders as in JSON text. Used to scan
*inside* ``envelope_provenance``'s pre-serialised JSON strings, where a raw
float is invisible to a recursive Python-object walk (it is just characters
in a ``str`` until re-parsed)."""


def _assert_no_unquantised_floats(obj: Any) -> None:
    """Recursively assert every float in ``obj`` is already 6-decimal quantised.

    ``bool`` is excluded first (it is an ``int`` subclass, never a ``float``,
    and must never be rounded — Codex H3). Any ``envelope_provenance`` list is
    additionally scanned as raw text for a longer-than-6-decimal literal,
    since those entries are pre-serialised JSON strings whose embedded floats
    a plain Python-object walk cannot see.
    """
    if isinstance(obj, bool):
        return
    if isinstance(obj, float):
        assert obj == round(obj, 6), f"un-quantised float found: {obj!r}"
        return
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "envelope_provenance" and isinstance(value, list):
                for env_json in value:
                    assert isinstance(env_json, str)
                    match = _LONG_DECIMAL_FLOAT_RE.search(env_json)
                    assert match is None, (
                        f"long-decimal literal {match.group() if match else ''!r} "
                        f"survives in envelope_provenance JSON text: {env_json!r}"
                    )
                    _assert_no_unquantised_floats(json.loads(env_json))
                continue
            _assert_no_unquantised_floats(value)
        return
    if isinstance(obj, (list, tuple)):
        for item in obj:
            _assert_no_unquantised_floats(item)


async def test_decision_projection_fully_quantised() -> None:
    recorded, _inners = await _capture()
    assert recorded.decisions
    for agent_decisions in recorded.decisions.values():
        assert agent_decisions
        for decision in agent_decisions:
            projection = society._decision_projection(decision)
            assert projection["envelope_provenance"], "no envelope_provenance to scan"
            _assert_no_unquantised_floats(projection)


# --------------------------------------------------------------------------- #
# AC1-G2 — replay clients never touch a live LLM
# --------------------------------------------------------------------------- #


async def test_replay_no_inner_invocations() -> None:
    recorded, _inners = await _capture()
    _replayed, replay_clients = await _replay(recorded)

    assert replay_clients
    for client in replay_clients.values():
        assert client.inner_invocations == 0


# --------------------------------------------------------------------------- #
# AC1-G3 — ThinkOffChatClient forces think=False on every agent's inner
# --------------------------------------------------------------------------- #


async def test_think_off_forced() -> None:
    inners = {agent_id: _ScriptedInner() for agent_id in SOCIETY_LIVE_AGENT_IDS}
    _recorded, used_inners = await _capture(inner_chats=inners)

    assert used_inners is inners
    for agent_id, inner in inners.items():
        assert inner.calls, f"inner for {agent_id} was never called"
        assert all(call["think"] is False for call in inner.calls), agent_id


# --------------------------------------------------------------------------- #
# Issue 001 (K1) — society_live.py::run_society_live_capture threads
# ``self_other_enabled`` through to ``run_society_loop`` (additive, default
# ``False``). This is a *construction* wiring test — it proves the causal
# path (segment present when on / absent when off), never a floor/verdict.
# --------------------------------------------------------------------------- #

_KANT_PLAN_JSON = json.dumps(
    {
        "thought": "consider the categorical imperative",
        "utterance": "定言命法を考える",
        "destination_zone": "peripatos",
        "animation": "walk",
    }
)
_NIETZSCHE_PLAN_JSON = json.dumps(
    {
        "thought": "compose amidst the mountains",
        "utterance": "山にて思索す",
        "destination_zone": "agora",
        "animation": "walk",
    }
)
_RIKYU_PLAN_JSON = json.dumps(
    {
        "thought": "prepare the tea ceremony",
        "utterance": "茶の湯を整える",
        "destination_zone": "garden",
        "animation": "walk",
    }
)


def _per_agent_scripted_inners() -> dict[str, _ScriptedInner]:
    """Distinct per-agent scripted plans (different ``destination_zone``/
    ``utterance``) so a tick>=1 self-other segment is genuinely non-vacuous
    (an observed bullet body, not just the bare framing header)."""
    return {
        KANT_AGENT_ID: _ScriptedInner(content=_KANT_PLAN_JSON),
        NIETZSCHE_AGENT_ID: _ScriptedInner(content=_NIETZSCHE_PLAN_JSON),
        RIKYU_AGENT_ID: _ScriptedInner(content=_RIKYU_PLAN_JSON),
    }


def _call_text(call: dict[str, Any]) -> str:
    """Concatenate every recorded ``ChatMessage``'s content for one call."""
    return "\n".join(message.content for message in call["messages"])


async def test_self_other_enabled_injects_segment() -> None:
    inners = _per_agent_scripted_inners()
    _recorded, used_inners = await _capture(inner_chats=inners, self_other_enabled=True)

    # Window 0 (each agent's first call) has no prior window — honest: the
    # framing must be absent regardless of ``self_other_enabled``.
    for agent_id, inner in used_inners.items():
        assert inner.calls, f"inner for {agent_id} was never called"
        assert _SELF_OTHER_FRAMING not in _call_text(inner.calls[0]), agent_id

    # Some tick>=1 call across the roster must carry the framing — the
    # segment actually rides an existing cognition call (no new LLM call).
    injected = [
        (agent_id, tick)
        for agent_id, inner in used_inners.items()
        for tick, call in enumerate(inner.calls)
        if tick >= 1 and _SELF_OTHER_FRAMING in _call_text(call)
    ]
    assert injected, "no self-other framing found in any tick>=1 call"


async def test_self_other_default_off_no_segment() -> None:
    inners = _per_agent_scripted_inners()
    _recorded, used_inners = await _capture(inner_chats=inners)  # default False

    for agent_id, inner in used_inners.items():
        assert inner.calls, f"inner for {agent_id} was never called"
        for call in inner.calls:
            assert _SELF_OTHER_FRAMING not in _call_text(call), agent_id


# --------------------------------------------------------------------------- #
# Issue 002 (K2) — shared write-when-True env-pin seam (code-review MEDIUM):
# ``apply_self_other_env_pin`` is the single seam both the CLI ``capture()``
# (live-Ollama, CI-unreached) and the mock-bundle renderer call, so the
# write-only-when-True witness discipline is CI-covered by this focused unit
# test rather than only by the live path.
# --------------------------------------------------------------------------- #


def test_apply_self_other_env_pin() -> None:
    on: dict[str, Any] = {}
    apply_self_other_env_pin(on, self_other_enabled=True)
    assert on["self_other_enabled"] is True

    off: dict[str, Any] = {}
    apply_self_other_env_pin(off, self_other_enabled=False)
    assert "self_other_enabled" not in off  # absence, never a False literal

    # Codex MEDIUM (cross-review): False also *removes* a stale/re-used key, so
    # a lingering true/false cannot weaken the absence == Layer2-off invariant.
    stale: dict[str, Any] = {"self_other_enabled": True, "other": 1}
    apply_self_other_env_pin(stale, self_other_enabled=False)
    assert "self_other_enabled" not in stale
    assert stale == {"other": 1}


# --------------------------------------------------------------------------- #
# AC1-G4 — measurement-line non-re-entry (import / output guard)
# --------------------------------------------------------------------------- #

_SOCIETY_LIVE_TREE = ast.parse(
    Path(society_live_module.__file__).read_text(encoding="utf-8")
)


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


def _assert_no_gate_keys(tree: ast.Module) -> None:
    """§L3: no ``verdict``/``passed``/``score``/``floor`` string key literal."""
    banned_keys = {"verdict", "passed", "score", "floor"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert node.value.lower() not in banned_keys, node.value


def test_society_live_measurement_guard() -> None:
    """``society_live.py`` imports no measurement machinery and defines no
    floor/landscape/verdict output identifier or gate key literal (design
    §F, mirrors the ``loop.py``/``handoff.py``/``live.py`` guards)."""
    _assert_no_measurement_imports(_SOCIETY_LIVE_TREE)
    _assert_no_measurement_output_identifiers(_SOCIETY_LIVE_TREE)
    _assert_no_gate_keys(_SOCIETY_LIVE_TREE)


# --------------------------------------------------------------------------- #
# AC1-G5 — observables are a frozen annotation literal, not computed
# --------------------------------------------------------------------------- #


def _find_assigned_dict(tree: ast.Module, name: str) -> ast.Dict:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            and isinstance(node.value, ast.Dict)
        ):
            return node.value
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == name
                    and isinstance(node.value, ast.Dict)
                ):
                    return node.value
    msg = f"no dict literal assignment found for {name!r}"
    raise AssertionError(msg)


def test_observables_are_annotation() -> None:
    """``SOCIETY_LIVE_OBSERVABLES`` is a frozen literal: every value is a
    ``str``/``None``/f-string constant, never a call or computed expression —
    i.e. no statistical computation code backs it (HIGH-6: this test checks
    existence/type/canonical rendering only, never a value-based
    pass/fail/threshold on the annotation content itself)."""
    dict_node = _find_assigned_dict(_SOCIETY_LIVE_TREE, "SOCIETY_LIVE_OBSERVABLES")
    for value_node in dict_node.values:
        assert isinstance(value_node, (ast.Constant, ast.JoinedStr)), ast.dump(
            value_node
        )

    for key in ("O1", "O2", "O3a", "O3b", "O4_distinct_zones", "O_multi_agent_speech"):
        assert key in SOCIETY_LIVE_OBSERVABLES
        assert isinstance(SOCIETY_LIVE_OBSERVABLES[key], str)
        assert SOCIETY_LIVE_OBSERVABLES[key]
    assert SOCIETY_LIVE_OBSERVABLES["done_formula"] == "O1∧O2∧O3a∧O3b"

    manifest: dict[str, Any] = {"schema_version": "x"}
    overlaid = attach_society_live_observables(manifest)
    assert "annotations" in overlaid
    assert "annotations" not in manifest  # non-mutating
    annotations = overlaid["annotations"]
    for banned in ("verdict", "passed", "score", "floor"):
        assert banned not in annotations


# --------------------------------------------------------------------------- #
# AC1-G6 — fixed-constructor canonical fingerprint (HIGH-4/M2)
# --------------------------------------------------------------------------- #


def test_fixed_constructors_fingerprint() -> None:
    # Construct 4 times with a ~10ms sleep between each: a system-clock-luck
    # regression (wall_clock leaking from schemas.py's `default_factory=_utc_now`
    # into the fixed constructors) would only coincidentally pass a bare 2-call
    # comparison on a coarse-resolution clock (observed on Windows, ~15ms tick)
    # — it reliably fails on a microsecond-resolution clock (Linux/WSL/CI) or
    # across a real inter-call gap. All 4 fingerprints must be identical.
    fingerprints: list[dict[str, str]] = []
    for _ in range(4):
        agent_states = society_live_agent_states()
        personas = society_live_personas()
        fingerprints.append(
            fixed_constructor_fingerprint(agent_states=agent_states, personas=personas)
        )
        time.sleep(0.01)

    fp_a = fingerprints[0]
    for fp in fingerprints[1:]:
        assert fp == fp_a
    assert set(fp_a) == {
        "agent_states_sha256",
        "personas_sha256",
        "observation_factories_sha256",
    }
    for digest in fp_a.values():
        assert isinstance(digest, str)
        assert len(digest) == 64  # SHA-256 hex

    env_pins = build_society_live_env_pins(
        qwen3_model_digest="sha256:deadbeef",
        ollama_version="0.5.1",
        vram_gb=16.0,
        uv_lock_sha256="abc123",
        resolved_sampling=ResolvedSampling(
            temperature=0.7, top_p=0.9, repeat_penalty=1.1
        ),
        agent_states=society_live_agent_states(),
        personas=society_live_personas(),
        base_env_pins={"python": "3.11.9", "packages": {}, "godot": "4.6"},
    )
    assert env_pins["fixed_constructor_fingerprint"] == fp_a
    assert env_pins["think"] is False
    assert env_pins["run_id"] == SOCIETY_LIVE_RUN_ID
    assert env_pins["n_cognition_ticks"] == SOCIETY_LIVE_N_COGNITION_TICKS


# --------------------------------------------------------------------------- #
# Sanity — the harness itself drives every agent and the horizon is pinned
# --------------------------------------------------------------------------- #


async def test_society_live_capture_drives_every_agent() -> None:
    recorded, inners = await _capture()
    assert set(recorded.decisions) == set(SOCIETY_LIVE_AGENT_IDS)
    for agent_id in SOCIETY_LIVE_AGENT_IDS:
        assert len(recorded.decisions[agent_id]) == _N_TICKS
        assert inners[agent_id].calls
    assert SOCIETY_LIVE_N_COGNITION_TICKS == 12
    assert DEFAULT_PHYSICS_TICKS_PER_COGNITION > 0


# --------------------------------------------------------------------------- #
# Issue 002 (I2): scripts/m4_society_live_capture.py — --capture/--verify CLI
# + R3 per-agent from-jsonl decoder (design-final.md §B/§R3, handoff.py
# untouched). The script lives outside the ``erre_sandbox`` package (it is a
# CLI, not a library module), so it is loaded via ``importlib`` from its file
# path — the same idiom ``tests/test_evidence/test_p3a_decide.py`` uses for
# ``scripts/p3a_decide.py``.
# --------------------------------------------------------------------------- #

_M4_SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "m4_society_live_capture.py"
)


def _load_m4_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "scripts_m4_society_live_capture", _M4_SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_m4 = _load_m4_module()


async def _capture_full_horizon(
    inner_chats: dict[str, _ScriptedInner] | None = None,
    *,
    self_other_enabled: bool = False,
) -> tuple[Any, dict[str, _ScriptedInner]]:
    """Same shape as ``_capture`` but at the pinned 12-tick horizon.

    I2's ``--verify`` structural-completeness check (Codex M1) asserts the
    replayed run has exactly ``SOCIETY_LIVE_N_COGNITION_TICKS`` decisions per
    agent, so a mock bundle exercising the full ``verify()`` round trip needs
    that horizon — ``_capture``'s ``_N_TICKS=3`` stays untouched for I1's own
    (faster) tests. ``self_other_enabled`` (default ``False``, unchanged
    existing callers) threads straight through to
    :func:`run_society_live_capture` (Issue 002/I2's Layer2-on mock bundle
    path).
    """
    agent_states = society_live_agent_states()
    personas = society_live_personas()
    inners = inner_chats or {
        agent_id: _ScriptedInner() for agent_id in SOCIETY_LIVE_AGENT_IDS
    }
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _embed_client()
    try:
        result = await run_society_live_capture(
            inner_chats=inners,
            store=store,
            embedding=embedding,
            run_id=SOCIETY_LIVE_RUN_ID,
            agent_states=agent_states,
            personas=personas,
            retrieval_now=_FIXED,
            base_ts=_FIXED,
            n_cognition_ticks=SOCIETY_LIVE_N_COGNITION_TICKS,
            physics_ticks_per_cognition=_PHYSICS_TICKS,
            observation_factories=society_live_observation_factories(),
            self_other_enabled=self_other_enabled,
        )
        return result, inners
    finally:
        await embedding.close()
        await store.close()


def _render_mock_bundle(
    recorded: Any, *, self_other_enabled: bool = False
) -> dict[str, str]:
    """Render a mock-captured bundle the same way ``m4_society_live_capture.py``'s
    ``capture()`` would (Ollama-free — this is the ``_ScriptedInner``-driven
    in-memory result, not a live run). ``self_other_enabled`` (default
    ``False``, unchanged existing callers) mirrors the script's own
    capture()-seam discipline: the ``env_pins["self_other_enabled"]`` key is
    injected **only when True** (Codex MEDIUM-2) so the default-False path
    stays byte-identical to the existing M4 golden."""
    resolved_sampling = recorded.decisions[SOCIETY_LIVE_AGENT_IDS[0]][0].call.sampling
    env_pins = build_society_live_env_pins(
        qwen3_model_digest="sha256:mock",
        ollama_version="0.0.0-mock",
        vram_gb=0.0,
        uv_lock_sha256="mock",
        resolved_sampling=resolved_sampling,
        agent_states=society_live_agent_states(),
        personas=society_live_personas(),
        run_id=SOCIETY_LIVE_RUN_ID,
        n_cognition_ticks=SOCIETY_LIVE_N_COGNITION_TICKS,
        seed=0,
        base_env_pins={"python": "3.11.9", "packages": {}, "godot": "4.6"},
    )
    env_pins["captured_event_log_checksum"] = recorded.event_log_checksum
    # env_pins["fixed_constructor_fingerprint"] is already set by
    # build_society_live_env_pins() above — society_live.py's fixed
    # constructors pin a fixed wall_clock, so the fingerprint is
    # deterministic across calls (no CLI-side correction needed).
    # Same shared write-when-True seam ``capture()`` uses (code-review
    # MEDIUM: one seam, so this renderer cannot drift from the script).
    apply_self_other_env_pin(env_pins, self_other_enabled=self_other_enabled)
    rendered = handoff.render_society_golden(
        recorded, run_config=_run_config(), env_pins=env_pins
    )
    manifest = json.loads(rendered["manifest.json"])
    rendered["manifest.json"] = (
        handoff.canonical_dumps(attach_society_live_observables(manifest)) + "\n"
    )
    return rendered


def _write_bundle(out_dir: Path, rendered: dict[str, str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, text in rendered.items():
        (out_dir / filename).write_text(text, encoding="utf-8", newline="\n")


# --------------------------------------------------------------------------- #
# AC2-G1 — mock bundle round trip: verify() True, inner_invocations==0 for
# every replay client, checksum/SHA/manifest re-render all byte-identical.
# --------------------------------------------------------------------------- #


async def test_verify_roundtrip_mock_bundle(tmp_path: Path) -> None:
    recorded, _inners = await _capture_full_horizon()
    rendered = _render_mock_bundle(recorded)
    _write_bundle(tmp_path, rendered)

    ok = await _m4.verify(tmp_path)

    assert ok is True


# --------------------------------------------------------------------------- #
# Issue 002 (K2) — verify() auto-detects self_other_enabled from the
# committed manifest's env_pins (Codex MEDIUM-2/MEDIUM-3): a Layer2-on bundle
# replays True with zero live-LLM touches, and a poisoned non-bool value
# fails closed rather than silently coercing truthy.
# --------------------------------------------------------------------------- #


async def test_verify_roundtrip_selfother_bundle(tmp_path: Path) -> None:
    recorded, _inners = await _capture_full_horizon(self_other_enabled=True)
    rendered = _render_mock_bundle(recorded, self_other_enabled=True)
    _write_bundle(tmp_path, rendered)

    manifest = json.loads(rendered["manifest.json"])
    assert manifest["env_pins"]["self_other_enabled"] is True  # fixture precondition

    ok = await _m4.verify(tmp_path)

    assert ok is True


async def test_verify_rejects_nonbool_self_other(tmp_path: Path) -> None:
    recorded, _inners = await _capture_full_horizon()
    rendered = dict(_render_mock_bundle(recorded))
    manifest = json.loads(rendered["manifest.json"])
    manifest["env_pins"]["self_other_enabled"] = "true"  # poisoned: string, not bool
    rendered["manifest.json"] = handoff.canonical_dumps(manifest) + "\n"
    _write_bundle(tmp_path, rendered)

    ok = await _m4.verify(tmp_path)

    assert ok is False


# --------------------------------------------------------------------------- #
# AC2-G2 — R3 decoder fail-closed (Codex HIGH-1): duplicate (agent,tick) /
# unknown agent / order_slot inconsistent-with-roster / insufficient rows.
# --------------------------------------------------------------------------- #


async def test_decoder_fail_closed() -> None:
    recorded, _inners = await _capture()
    lines = handoff.build_society_decisions_stream(recorded)
    assert lines, "fixture precondition: at least one decision row"

    def _to_text(entries: list[dict[str, Any]]) -> str:
        return "\n".join(json.dumps(e) for e in entries) + "\n"

    # Sanity: the unmodified stream decodes cleanly (no expected_agent_ids).
    decoded = _m4.society_recorded_calls_from_jsonl(_to_text(lines))
    assert set(decoded) == set(SOCIETY_LIVE_AGENT_IDS)

    # Duplicate (agent_id, agent_tick) pair.
    duplicated = [*lines, lines[0]]
    with pytest.raises(ValueError, match="duplicate"):
        _m4.society_recorded_calls_from_jsonl(_to_text(duplicated))

    # Unknown agent_id relative to an explicit expected roster.
    with pytest.raises(ValueError, match="unknown agent_id"):
        _m4.society_recorded_calls_from_jsonl(
            _to_text(lines),
            expected_agent_ids=(KANT_AGENT_ID, NIETZSCHE_AGENT_ID),
        )

    # order_slot inconsistent with the sorted(agent_ids) roster.
    tampered_slot = [dict(e) for e in lines]
    tampered_slot[0] = {**tampered_slot[0], "order_slot": 99}
    with pytest.raises(ValueError, match="order_slot"):
        _m4.society_recorded_calls_from_jsonl(_to_text(tampered_slot))

    # Missing rows: an entire expected agent absent from the stream.
    missing_agent = [e for e in lines if e["agent_id"] != RIKYU_AGENT_ID]
    with pytest.raises(ValueError, match="missing agent_id"):
        _m4.society_recorded_calls_from_jsonl(
            _to_text(missing_agent), expected_agent_ids=SOCIETY_LIVE_AGENT_IDS
        )

    # Insufficient rows: one agent has a tick-slot gap (present overall, but
    # missing one agent_tick another agent reported).
    tick_gap = [
        e
        for e in lines
        if not (e["agent_id"] == RIKYU_AGENT_ID and e["decision"]["agent_tick"] == 0)
    ]
    with pytest.raises(ValueError, match="insufficient rows"):
        _m4.society_recorded_calls_from_jsonl(_to_text(tick_gap))


# --------------------------------------------------------------------------- #
# AC2-G3 — anti-vacuous-pass (Codex HIGH-5): a 1-byte manifest.json
# corruption must fail verify(), never vacuously pass.
# --------------------------------------------------------------------------- #


async def test_verify_anti_vacuous(tmp_path: Path) -> None:
    recorded, _inners = await _capture_full_horizon()
    rendered = _render_mock_bundle(recorded)
    _write_bundle(tmp_path, rendered)

    manifest_path = tmp_path / "manifest.json"
    original = manifest_path.read_text(encoding="utf-8")
    corrupted = original.rstrip("\n") + " \n"  # still valid JSON, 1 byte added
    assert corrupted != original
    json.loads(corrupted)  # precondition: still parses
    manifest_path.write_text(corrupted, encoding="utf-8", newline="\n")

    ok = await _m4.verify(tmp_path)

    assert ok is False


# --------------------------------------------------------------------------- #
# AC2-G4 — structural completeness (Codex M1, fail-closed): agent drift /
# horizon shortfall both fail verify() (never a raise, never a silent pass).
# --------------------------------------------------------------------------- #


async def test_verify_structural_completeness(tmp_path: Path) -> None:
    # horizon 不足 — a structurally valid (uniform tick count across all 3
    # agents) bundle whose horizon is below the pinned 12-tick constant.
    short_dir = tmp_path / "short_horizon"
    recorded_short, _inners = await _capture()  # _N_TICKS == 3, all agents uniform
    rendered_short = _render_mock_bundle(recorded_short)
    _write_bundle(short_dir, rendered_short)
    assert await _m4.verify(short_dir) is False

    # agent 欠落 — manifest.run.agent_ids drifted to drop one pinned agent
    # while decisions.jsonl itself stays fully valid for all three.
    missing_dir = tmp_path / "missing_agent"
    recorded_full, _inners = await _capture_full_horizon()
    rendered_full = dict(_render_mock_bundle(recorded_full))
    manifest = json.loads(rendered_full["manifest.json"])
    manifest["run"]["agent_ids"] = [
        agent_id
        for agent_id in manifest["run"]["agent_ids"]
        if agent_id != RIKYU_AGENT_ID
    ]
    rendered_full["manifest.json"] = json.dumps(manifest) + "\n"
    _write_bundle(missing_dir, rendered_full)
    assert await _m4.verify(missing_dir) is False


# --------------------------------------------------------------------------- #
# AC2-G5 — measurement-line non-re-entry guard on the CLI script itself.
# --------------------------------------------------------------------------- #

_M4_SCRIPT_TREE = ast.parse(_M4_SCRIPT.read_text(encoding="utf-8"))


def test_m4_capture_measurement_guard() -> None:
    """``m4_society_live_capture.py`` imports no measurement machinery and
    defines no floor/landscape/verdict output identifier or gate key literal
    (design §F, mirrors the ``society_live.py``/``handoff.py`` guards)."""
    _assert_no_measurement_imports(_M4_SCRIPT_TREE)
    _assert_no_measurement_output_identifiers(_M4_SCRIPT_TREE)
    _assert_no_gate_keys(_M4_SCRIPT_TREE)
