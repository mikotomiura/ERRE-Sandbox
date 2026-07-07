"""ECL v1 — locomotion→sampling channel live-activation apparatus tests.

FROZEN ADR ``.steering/20260707-ecl-v1-adr/design-final.md`` (§B/§C/§E/§F/§G),
Phase 1 issues ``loop/20260707-ecl-v1-phase1/issues/{001,002,003}.md``.

Ollama-free throughout: every test drives a *record* run through a mock inner
chat that re-serves the golden plan, then *replays* the captured Plane 2 with
:class:`~erre_sandbox.integration.embodied.loop.RecordReplayChatClient` (no live
LLM). The I3 sealed live run (real ``qwen3:8b`` + committed artifact + WSL
byte-equality) is a separate human-gated session; these tests prove the
apparatus + the Ollama-free replay-verify + the V4a/V4b sampling-spy mechanism
in memory, with no committed bundle dependency.

Scope guard (§F/§G, binding — mirrors ``test_ecl_live_golden.py``). This is a
*construction* apparatus, **NOT a measurement line**. It imports no ``evidence``
/ ``spdm`` / ``runningness`` machinery and computes/emits no floor / landscape /
final statistic — :func:`test_v1_measurement_guard` AST-scans ``live_v1.py`` /
``scripts/ecl_v1_live_capture.py`` / this module with the enhanced 3-hole guard
(Codex HIGH-2).
"""

from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import httpx
import pytest

from erre_sandbox.erre.locomotion_sampling import (
    DEFAULT_LOCO_ALPHA,
    DEFAULT_LOCO_GAIN_P,
    DEFAULT_LOCO_GAIN_T,
)
from erre_sandbox.inference.ollama_adapter import ChatMessage, ChatResponse
from erre_sandbox.inference.sampling import ResolvedSampling, compose_sampling
from erre_sandbox.integration.embodied import handoff, live
from erre_sandbox.integration.embodied.live_v1 import (
    ECL_V1_LOCO_LAM0,
    SamplingSpyChatClient,
    build_live_v1_env_pins,
    locomotion_seeded_agent_state,
    run_live_capture_v1,
)
from erre_sandbox.integration.embodied.loop import (
    RecordedLlmCall,
    RecordReplayChatClient,
    run_ecl_loop,
)
from erre_sandbox.memory import EmbeddingClient, MemoryStore
from erre_sandbox.schemas import LocomotionState, SamplingBase, SamplingDelta

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.integration.embodied.loop import EclRunResult
    from erre_sandbox.schemas import AgentState

_THIS_FILE = Path(__file__)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIVE_V1_SRC = (
    _REPO_ROOT / "src" / "erre_sandbox" / "integration" / "embodied" / "live_v1.py"
)
_V1_SCRIPT_SRC = _REPO_ROOT / "scripts" / "ecl_v1_live_capture.py"

_FIXED_CLOCK = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
_TEST_TICKS = 8  # smaller than the sealed run's 32; enough for movement + centroid


# --------------------------------------------------------------------------- #
# Ollama-free fixtures (mirror test_ecl_live_golden.py)
# --------------------------------------------------------------------------- #


def _mock_embedding() -> EmbeddingClient:
    """Constant-vector embedding (Ollama-free)."""
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


class _MockInnerChat:
    """Ollama-free inner chat that re-serves the golden plan every call."""

    def __init__(self) -> None:
        resp = handoff.golden_recorded_calls()[0].response
        assert resp is not None
        self._response = resp

    async def chat(self, *_args: Any, **_kwargs: Any) -> ChatResponse:
        return self._response


async def _record(
    *,
    capture: Any,
    agent_state: AgentState | None,
    n_ticks: int = _TEST_TICKS,
) -> EclRunResult:
    """Drive one record-mode run through ``capture`` (v0 or v1 harness)."""
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    inner = _MockInnerChat()
    try:
        kwargs: dict[str, Any] = {
            "inner_chat": inner,
            "store": store,
            "embedding": embedding,
            "run_id": "ecl-v1-test",
            "persona": handoff.golden_persona(),
            "retrieval_now": _FIXED_CLOCK,
            "base_ts": _FIXED_CLOCK,
            "n_cognition_ticks": n_ticks,
        }
        if capture is live.run_live_capture:
            # v0 harness requires an explicit agent_state.
            assert agent_state is not None
            kwargs["agent_state"] = agent_state
        else:
            kwargs["agent_state"] = agent_state  # v1: None → seeded factory
        return await capture(**kwargs)
    finally:
        await embedding.close()
        await store.close()


async def _replay(
    *,
    recorded: Sequence[RecordedLlmCall],
    agent_state: AgentState,
    spy: bool = False,
    n_ticks: int = _TEST_TICKS,
) -> tuple[EclRunResult, RecordReplayChatClient | SamplingSpyChatClient]:
    """Replay a recorded Plane 2 (optionally through the sampling-spy)."""
    store = MemoryStore(db_path=":memory:")
    store.create_schema()
    embedding = _mock_embedding()
    inner = RecordReplayChatClient(recorded=recorded)
    llm: RecordReplayChatClient | SamplingSpyChatClient = (
        SamplingSpyChatClient(inner) if spy else inner
    )
    try:
        result = await run_ecl_loop(
            run_id="ecl-v1-test",
            store=store,
            embedding=embedding,
            llm=cast("RecordReplayChatClient", llm),
            agent_state=agent_state,
            persona=handoff.golden_persona(),
            retrieval_now=_FIXED_CLOCK,
            base_ts=_FIXED_CLOCK,
            n_cognition_ticks=n_ticks,
        )
    finally:
        await embedding.close()
        await store.close()
    return result, llm


def _q(s: ResolvedSampling) -> tuple[float, float, float]:
    """6-decimal quantised sampling triple (the cross-platform comparison unit)."""
    return (
        round(s.temperature, 6),
        round(s.top_p, 6),
        round(s.repeat_penalty, 6),
    )


# --------------------------------------------------------------------------- #
# I1 — apparatus core (live_v1.py)
# --------------------------------------------------------------------------- #


def test_v1_lam0_literal_pin() -> None:
    """AC1: λ₀ is a literal 0.0 and ``live_v1.py`` imports no ``evidence`` (§C)."""
    assert ECL_V1_LOCO_LAM0 == 0.0
    assert isinstance(ECL_V1_LOCO_LAM0, float)
    src = _LIVE_V1_SRC.read_text(encoding="utf-8")
    assert "erre_sandbox.evidence" not in src
    # The literal must appear in source, not a re-exported apparatus constant.
    tree = ast.parse(src)
    assigned = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "ECL_V1_LOCO_LAM0"
    ]
    assert len(assigned) == 1
    value = assigned[0].value
    assert isinstance(value, ast.Constant)
    assert value.value == 0.0


def test_v1_seeded_factory() -> None:
    """AC2: seeded state arms locomotion at λ₀; golden stays locomotion-null (§B)."""
    seeded = locomotion_seeded_agent_state()
    golden = handoff.golden_agent_state()
    assert seeded.locomotion == LocomotionState(lam=ECL_V1_LOCO_LAM0)
    assert golden.locomotion is None, "golden_agent_state must stay locomotion-null"
    # Every field except locomotion (and the nondeterministic wall_clock) matches.
    exclude = {"locomotion", "wall_clock"}
    assert seeded.model_dump(exclude=exclude) == golden.model_dump(exclude=exclude)


async def test_v1_sampling_spy_captures() -> None:
    """AC3: the spy records each chat's ``sampling`` and delegates to the inner."""
    sampling = compose_sampling(SamplingBase(), SamplingDelta())
    response = ChatResponse(
        content="{}",
        model="qwen3:8b",
        eval_count=0,
        prompt_eval_count=0,
        total_duration_ms=0.0,
    )
    recorded = [
        RecordedLlmCall(
            system_prompt="s",
            user_prompt="u",
            sampling=sampling,
            response=response,
            outcome="ok",
        )
    ]
    inner = RecordReplayChatClient(recorded=recorded)
    spy = SamplingSpyChatClient(inner)

    assert spy.is_replay is True
    returned = await spy.chat(
        [ChatMessage(role="user", content="u")], sampling=sampling
    )

    assert returned is response
    assert spy.sampled == (sampling,)
    assert spy.inner_invocations == 0  # replay: no live LLM
    assert len(spy.used) == 1  # delegated to the inner replay client


async def test_v1_run_capture_flag_off_byte_invariance() -> None:
    """AC4: v1 harness with a locomotion-null state == the v0 harness, byte-for-byte.

    ``run_live_capture_v1`` only parameterises ``agent_state``; driven with the
    locomotion-null golden it must reproduce ``live.run_live_capture`` exactly
    (organ untouched, §H flag-off invariance). Driven with the seeded state it
    must instead differ in the recorded per-tick ``call.sampling`` while the
    geometry checksum is unperturbed (the activation has an effect but adds no
    new determinism source)."""
    golden = handoff.golden_agent_state()

    r_v0 = await _record(capture=live.run_live_capture, agent_state=golden)
    r_v1_off = await _record(capture=run_live_capture_v1, agent_state=golden)
    r_v1_on = await _record(capture=run_live_capture_v1, agent_state=None)

    # Flag-off: v1 (locomotion=None) is byte-identical to v0.
    assert r_v1_off.checksum == r_v0.checksum
    assert handoff.decisions_to_jsonl(r_v1_off.decisions) == handoff.decisions_to_jsonl(
        r_v0.decisions
    )

    # Flag-on: geometry checksum unperturbed (no new determinism source, §E) …
    assert r_v1_on.checksum == r_v0.checksum
    # … but the recorded per-tick sampling is modulated by λ, so decisions differ.
    assert handoff.decisions_to_jsonl(r_v1_on.decisions) != handoff.decisions_to_jsonl(
        r_v0.decisions
    )


def test_v1_env_pins_structure() -> None:
    """AC5: env pins carry base/gains/α/λ₀ + decisions SHA, not a single resolved
    sampling (Codex MEDIUM-3)."""
    pins = build_live_v1_env_pins(
        qwen3_model_digest="digest",
        ollama_version="0.0.0",
        vram_gb=16.0,
        uv_lock_sha256="lockhash",
        base_sampling=SamplingBase(),
        decisions_sha256="deadbeef",
        base_env_pins={},
    )
    assert "resolved_sampling" not in pins, "v1 sampling is per-tick, not single"
    assert pins["base_sampling"] == SamplingBase().model_dump(mode="json")
    assert pins["locomotion_gains"] == {
        "gain_t": DEFAULT_LOCO_GAIN_T,
        "gain_p": DEFAULT_LOCO_GAIN_P,
        "alpha": DEFAULT_LOCO_ALPHA,
    }
    assert pins["locomotion_lam0"] == ECL_V1_LOCO_LAM0
    assert pins["decisions_sha256"] == "deadbeef"
    assert pins["think"] is False


# --------------------------------------------------------------------------- #
# I2 — enhanced measurement-line non-re-entry guard (Codex HIGH-2, §G)
# --------------------------------------------------------------------------- #

_BANNED_IMPORT_PREFIX = ("erre_sandbox.evidence",)
_BANNED_IMPORT_SUB = ("spdm", "runningness")
_BANNED_IDENTIFIER_SUB = (
    "floor",
    "landscape",
    "verdict",
    "jaccard",
    "divergence",
    "r_min",
)
# Exact ES-3 measurement output names (§G, Codex LOW-2: exact, not substring, so a
# legit "schema_conformance" key or a bare "verdict": None marker does not collide).
_BANNED_MEASUREMENT_KEY_EXACT = frozenset(
    {
        "d_loco",
        "evaluate_verdict",
        "es3verdict",
        "amplitude",
        "headroom",
        "floor",
        "landscape",
        "divergence",
    }
)


def _guard_imports(node: ast.AST) -> None:
    """Hole 1 + classic import guard (every v1 file)."""
    if isinstance(node, ast.ImportFrom) and node.module is not None:
        assert not node.module.startswith(_BANNED_IMPORT_PREFIX), node.module
        assert not any(s in node.module for s in _BANNED_IMPORT_SUB), node.module
        if node.module == "erre_sandbox":  # hole 1: from erre_sandbox import evidence
            for alias in node.names:
                assert not alias.name.startswith("evidence"), alias.name
    if isinstance(node, ast.Import):
        for alias in node.names:
            assert not alias.name.startswith(_BANNED_IMPORT_PREFIX), alias.name
            assert not any(s in alias.name for s in _BANNED_IMPORT_SUB), alias.name


def _guard_identifiers(node: ast.AST) -> None:
    """Banned-identifier guard (every v1 file), mirrors the v0 guard."""
    names: list[str] = []
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
        names.append(node.id)
    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        names.append(node.target.id)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        names.append(node.name)
    elif isinstance(node, ast.arg):
        names.append(node.arg)
    for name in names:
        low = name.lower()
        assert not any(tok in low for tok in _BANNED_IDENTIFIER_SUB), name


def _guard_dynamic_import(node: ast.AST) -> None:
    """Hole 2: a dynamic ``importlib.import_module``/``__import__`` string constant."""
    if not isinstance(node, ast.Call):
        return
    func = node.func
    is_dynamic_import = (
        isinstance(func, ast.Attribute) and func.attr == "import_module"
    ) or (isinstance(func, ast.Name) and func.id == "__import__")
    if not is_dynamic_import:
        return
    for arg in node.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            low = arg.value.lower()
            assert not low.startswith(_BANNED_IMPORT_PREFIX), arg.value
            assert not any(s in low for s in _BANNED_IMPORT_SUB), arg.value


def _guard_keys_and_filenames(node: ast.AST) -> None:
    """Hole 3: a measurement name as a dict **key** (exact) or a ``.json`` filename."""
    if isinstance(node, ast.Dict):
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                assert key.value.lower() not in _BANNED_MEASUREMENT_KEY_EXACT, key.value
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        low = node.value.lower()
        if low.endswith((".json", ".jsonl")):
            stem = low.rsplit(".", 1)[0]
            assert stem not in _BANNED_MEASUREMENT_KEY_EXACT, node.value
            assert not any(tok in stem for tok in _BANNED_IDENTIFIER_SUB), node.value


def _assert_no_measurement_surface_v1(tree: ast.Module, *, scan_strings: bool) -> None:
    """The enhanced 3-hole guard (Codex HIGH-2), superset of the v0 guard.

    Always (every v1 file): banned imports (incl. hole 1 —
    ``from erre_sandbox import evidence``) and banned identifiers.

    ``scan_strings`` (apparatus files only, never the test module which legitimately
    defines the banned lists): hole 2 — a dynamic
    ``importlib.import_module("erre_sandbox.evidence…")`` string constant; hole 3 —
    a measurement name used as a dict **key** (exact) or a ``.json``/``.jsonl``
    **filename** carrying a banned token. Free-text docstrings are never
    substring-scanned, so a scope-guard note that merely *mentions* ``evidence`` /
    ``spdm`` / ``divergence`` does not self-trip.
    """
    for node in ast.walk(tree):
        _guard_imports(node)
        _guard_identifiers(node)
        if scan_strings:
            _guard_dynamic_import(node)
            _guard_keys_and_filenames(node)


def test_v1_measurement_guard() -> None:
    """AC2: no measurement import/identifier/key/filename in any v1 file (§G)."""
    for path, scan_strings in (
        (_LIVE_V1_SRC, True),
        (_V1_SCRIPT_SRC, True),
        (_THIS_FILE, False),
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        _assert_no_measurement_surface_v1(tree, scan_strings=scan_strings)


def test_v1_guard_catches_from_import() -> None:
    """AC3: hole 1 — ``from erre_sandbox import evidence`` is caught."""
    tree = ast.parse("from erre_sandbox import evidence\n")
    with pytest.raises(AssertionError):
        _assert_no_measurement_surface_v1(tree, scan_strings=False)


def test_v1_guard_catches_importlib() -> None:
    """AC4: hole 2 — a dynamic evidence import string constant is caught."""
    src = (
        "import importlib\n"
        'mod = importlib.import_module("erre_sandbox.evidence.es3_locomotion")\n'
    )
    tree = ast.parse(src)
    with pytest.raises(AssertionError):
        _assert_no_measurement_surface_v1(tree, scan_strings=True)


def test_v1_guard_catches_banned_key() -> None:
    """AC5: hole 3 — a banned measurement name used as a dict key / filename."""
    key_tree = ast.parse('annotation = {"d_loco": 1.0}\n')
    with pytest.raises(AssertionError):
        _assert_no_measurement_surface_v1(key_tree, scan_strings=True)
    file_tree = ast.parse('path = "landscape.jsonl"\n')
    with pytest.raises(AssertionError):
        _assert_no_measurement_surface_v1(file_tree, scan_strings=True)


def test_v1_guard_allows_legit_keys() -> None:
    """AC5: legit schema words + a bare ``verdict: None`` marker are not caught."""
    src = (
        'annotation = {"schema_conformance": 1, "sampling_note": 2, "verdict": None}\n'
        'path = "envelope_stream.jsonl"\n'
    )
    tree = ast.parse(src)
    _assert_no_measurement_surface_v1(tree, scan_strings=True)  # must not raise


# --------------------------------------------------------------------------- #
# I4 — Ollama-free replay-verify (V2/V3) + V4a/V4b spy + V5 annotation
# --------------------------------------------------------------------------- #


async def _record_seeded_recorded() -> tuple[EclRunResult, list[RecordedLlmCall]]:
    """Record one seeded run and reconstruct its Plane 2 through the serialiser.

    Round-tripping the recorded stream through
    ``decisions_to_jsonl`` → ``recorded_calls_from_jsonl`` exercises the
    cross-machine reproducibility contract (V3a mechanism) rather than reusing the
    in-memory ``EclRunResult.replay_calls()`` directly."""
    result = await _record(capture=run_live_capture_v1, agent_state=None)
    recorded = handoff.recorded_calls_from_jsonl(
        handoff.decisions_to_jsonl(result.decisions)
    )
    return result, recorded


async def test_v1_replay_deterministic_seeded() -> None:
    """AC1: seeded replay reproduces the capture checksum, Ollama-free."""
    recorded_result, recorded = await _record_seeded_recorded()
    seeded = locomotion_seeded_agent_state()

    r1, llm1 = await _replay(recorded=recorded, agent_state=seeded)
    r2, _llm2 = await _replay(recorded=recorded, agent_state=seeded)

    assert llm1.inner_invocations == 0, "replay must never touch a live LLM"
    assert r1.checksum == recorded_result.checksum, "V2: replay reproduces capture"
    assert r1.checksum == r2.checksum, "V3a mechanism: replay is deterministic"


async def test_v1_v4a_lambda_advances() -> None:
    """AC2/V4a: the seeded spied replay's per-tick sampling has >1 distinct value."""
    _result, recorded = await _record_seeded_recorded()
    _r, llm = await _replay(
        recorded=recorded, agent_state=locomotion_seeded_agent_state(), spy=True
    )
    assert isinstance(llm, SamplingSpyChatClient)
    distinct = {_q(s) for s in llm.sampled}
    assert len(distinct) > 1, "λ must actually advance and modulate the sampling"


async def test_v1_v4b_sampling_modulated() -> None:
    """AC3/V4b: seeded vs locomotion-null spied replays disagree on >=1 tick, and
    both replays' geometry checksum matches (unperturbed kinematics)."""
    _result, recorded = await _record_seeded_recorded()

    r_seeded, spy_seeded = await _replay(
        recorded=recorded, agent_state=locomotion_seeded_agent_state(), spy=True
    )
    r_null, spy_null = await _replay(
        recorded=recorded, agent_state=handoff.golden_agent_state(), spy=True
    )
    assert isinstance(spy_seeded, SamplingSpyChatClient)
    assert isinstance(spy_null, SamplingSpyChatClient)

    seeded_sampling = [_q(s) for s in spy_seeded.sampled]
    null_sampling = [_q(s) for s in spy_null.sampled]
    modulated = sum(
        1
        for seeded_tick, null_tick in zip(seeded_sampling, null_sampling, strict=True)
        if seeded_tick != null_tick
    )
    assert modulated >= 1, "the channel must actually modulate at least one tick"
    assert r_seeded.checksum == r_null.checksum, "geometry checksum must be unperturbed"


async def test_v1_v4b_decisions_call_sampling_identical() -> None:
    """AC4: the recorded ``call.sampling`` is identical across the seeded and null
    replays — the reason the sampling-spy is mandatory (Codex HIGH-1). Comparing
    ``result.decisions[*].call.sampling`` would silently pass."""
    _result, recorded = await _record_seeded_recorded()

    r_seeded, _ = await _replay(
        recorded=recorded, agent_state=locomotion_seeded_agent_state()
    )
    r_null, _ = await _replay(
        recorded=recorded, agent_state=handoff.golden_agent_state()
    )

    seeded_call = [_q(d.call.sampling) for d in r_seeded.decisions]
    null_call = [_q(d.call.sampling) for d in r_null.decisions]
    assert seeded_call == null_call, (
        "recorded call.sampling is identical across replays — a call.sampling "
        "comparison is a silent fail, so V4b must use the sampling-spy"
    )


async def test_v1_v5_parsed_history_dependent_action() -> None:
    """AC5/V5: >=1 tick parsed a plan that drove a history-dependent move."""
    result = await _record(capture=run_live_capture_v1, agent_state=None)
    count = sum(
        1
        for d in result.decisions
        if d.llm_status == "ok"
        and d.plan is not None
        and d.move_decision is not None
        and d.move_decision.resolved_from == "memory_centroid"
    )
    assert count >= 1, (
        "at least one parsed, history-dependent move (first-contact proof)"
    )


def test_v1_experiments_scaffold() -> None:
    """AC6: the experiments scaffold exists and repro.sh drives the --verify path."""
    exp = _REPO_ROOT / "experiments" / "20260707-ecl-v1-locomotion"
    for name in ("run.sh", "repro.sh", "env.md"):
        assert (exp / name).exists(), f"missing experiments scaffold file: {name}"
    repro = (exp / "repro.sh").read_text(encoding="utf-8")
    assert "--verify" in repro
    assert "ecl_v1_live_capture" in repro
