"""ECL B — Issue 006 (I6): continuity-gate 4 機械 test + T3 materiality desk-audit test.

Issue ``loop/20260708-m13-b-code-impl/issues/006-continuity-gate-t3.md`` of the
FROZEN ADR ``.steering/20260707-m13-b-impl-design/design-final.md`` (§I2
continuity-gate 4 machine test / §I5 provenance vs M-loop call-count boundary /
§I7 T3 materiality criterion 1-4). This is the **last** bank issue: the four
continuity-gate tests prove ``lever ⊥ SPDM-landscape channel`` structurally
(value-independent), and the desk-audit presence test proves the honest-teeth
close path (§I7 criterion 4) is on record, not merely promised.

Scope guard (§I9, mirrors ``test_ecl_bank_driver.py`` / ``test_ecl_bank_fixtures.py``
/ ``test_ecl_bank_spend_guard.py``). This module is a **verification layer**:
it computes no ``H(zone|ctx)`` / floor / divergence itself. Every assertion here
is boolean/count(call-count determinism) or AST/grep presence — never a
diversity/entropy aggregate over the records it observes.
"""

from __future__ import annotations

import ast
import dataclasses
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

import httpx

from erre_sandbox.inference.ollama_adapter import ChatResponse
from erre_sandbox.inference.sampling import ResolvedSampling
from erre_sandbox.integration.embodied import bank
from erre_sandbox.integration.embodied.bank import (
    BANK_K_GOLDEN,
    BANK_M_GOLDEN,
    run_bank_mloop,
)
from erre_sandbox.integration.embodied.bank_fixtures import (
    FrozenContext,
    build_competing_cue_substrate,
    run_provenance_pass,
)
from erre_sandbox.memory import EmbeddingClient, MemoryStore
from erre_sandbox.memory.retrieval import Retriever
from tests.test_integration._bank_spend_guard import (
    assert_bank_import_allowlist,
    assert_bank_no_measurement_surface,
    assert_no_aggregation_surface,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.inference.ollama_adapter import ChatMessage

_THIS_FILE = Path(__file__)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_BANK_SRC = _REPO_ROOT / "src" / "erre_sandbox" / "integration" / "embodied" / "bank.py"
_BANK_FIXTURES_SRC = (
    _REPO_ROOT
    / "src"
    / "erre_sandbox"
    / "integration"
    / "embodied"
    / "bank_fixtures.py"
)
_BANK_FILES = (_BANK_SRC, _BANK_FIXTURES_SRC)
_DESK_AUDIT_DOC = (
    _REPO_ROOT / "experiments" / "20260708-m13-b-bank" / "t3_materiality_desk_audit.md"
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


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Shared Ollama-free fixtures (mirrors test_ecl_bank_fixtures.py / driver.py)
# --------------------------------------------------------------------------- #


def _mock_embedding() -> EmbeddingClient:
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
            content=self.content, model="qwen3:8b", eval_count=1, total_duration_ms=0.0
        )


@dataclass
class _CyclingChat:
    """Ollama-free bank-axis chat client: re-serves ``contents`` round-robin."""

    contents: tuple[str, ...]
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
        content = self.contents[len(self.calls) % len(self.contents)]
        self.calls.append(
            {
                "messages": tuple(messages),
                "sampling": sampling,
                "model": model,
                "options": options,
                "think": think,
            }
        )
        return ChatResponse(
            content=content, model="qwen3:8b", eval_count=1, total_duration_ms=0.0
        )


def _store_factory() -> MemoryStore:
    return MemoryStore(db_path=":memory:")


def _sampling(temperature: float) -> ResolvedSampling:
    return ResolvedSampling(temperature=temperature, top_p=0.9, repeat_penalty=1.1)


def _frozen_ctx(ctx_id: str) -> FrozenContext:
    return FrozenContext(
        frozen_ctx_id=ctx_id,
        system_prompt=f"system-prompt-{ctx_id}",
        user_prompt=f"user-prompt-{ctx_id}",
        sampling_on=_sampling(0.7),
        sampling_off=_sampling(0.5),
    )


# --------------------------------------------------------------------------- #
# Retriever / MemoryStore call-count spy (§I2.2/§I5, boolean/count only —
# never a diversity/entropy aggregate over what is retrieved)
# --------------------------------------------------------------------------- #


@dataclass
class _RetrieveSpy:
    """Counts ``Retriever.retrieve`` and store read-method calls process-wide.

    Monkeypatches the shared ``Retriever``/``MemoryStore`` *classes* (not a
    particular instance) for the duration of the ``with`` block — both
    ``run_bank_mloop`` (Issue 002, structurally never constructs either) and
    ``run_provenance_pass`` (Issue 001, constructs a fresh ``Retriever`` per
    condition inside the untouched ``run_ecl_loop``) are observed identically,
    so the M-loop's zero and the provenance pass's non-zero count are both
    measured by the same instrument (§I2.2 boundary-by-test-name, not by
    instrument).
    """

    retrieve_call_count: int = 0
    store_read_count: int = 0
    _orig_retrieve: Any = None
    _orig_list_by_agent: Any = None
    _orig_list_world_scope: Any = None

    def __enter__(self) -> Self:
        self._orig_retrieve = Retriever.retrieve
        self._orig_list_by_agent = MemoryStore.list_by_agent
        self._orig_list_world_scope = MemoryStore.list_world_scope

        spy = self
        orig_retrieve = self._orig_retrieve
        orig_list_by_agent = self._orig_list_by_agent
        orig_list_world_scope = self._orig_list_world_scope

        async def spy_retrieve(self: Retriever, *args: Any, **kwargs: Any) -> Any:
            spy.retrieve_call_count += 1
            return await orig_retrieve(self, *args, **kwargs)

        async def spy_list_by_agent(
            self: MemoryStore, *args: Any, **kwargs: Any
        ) -> Any:
            spy.store_read_count += 1
            return await orig_list_by_agent(self, *args, **kwargs)

        async def spy_list_world_scope(
            self: MemoryStore, *args: Any, **kwargs: Any
        ) -> Any:
            spy.store_read_count += 1
            return await orig_list_world_scope(self, *args, **kwargs)

        Retriever.retrieve = spy_retrieve  # type: ignore[method-assign]
        MemoryStore.list_by_agent = spy_list_by_agent  # type: ignore[method-assign]
        MemoryStore.list_world_scope = spy_list_world_scope  # type: ignore[method-assign]
        return self

    def __exit__(self, *_exc: object) -> None:
        Retriever.retrieve = self._orig_retrieve  # type: ignore[method-assign]
        MemoryStore.list_by_agent = self._orig_list_by_agent  # type: ignore[method-assign]
        MemoryStore.list_world_scope = self._orig_list_world_scope  # type: ignore[method-assign]


# --------------------------------------------------------------------------- #
# I6-G1 — import-allowlist (reuses I3's _bank_spend_guard helper)
# --------------------------------------------------------------------------- #


def test_bank_import_allowlist() -> None:
    """AC I6-G1: bank module import ⊆ closed allowlist ∧ ∩ SPDM-系 module = ∅
    (§I2.1, allowlist-primary/denylist-secondary, I3's guard reused unmodified)."""
    for path in _BANK_FILES:
        assert_bank_import_allowlist(_parse(path))
    # Belt-and-suspenders: the shared measurement-surface guard (evidence/spdm/
    # runningness/landscape/divergence identifiers) also carries no hit here.
    for path in _BANK_FILES:
        assert_bank_no_measurement_surface(_parse(path), scan_strings=True)


# --------------------------------------------------------------------------- #
# I6-G2 — M-loop retrieve-count=0 (bake-out, structural)
# --------------------------------------------------------------------------- #


async def test_bank_mloop_retrieve_count_zero() -> None:
    """AC I6-G2: driving ``run_bank_mloop`` under the retriever/store spy yields
    ``retrieve_call_count == 0 ∧ store_read_count == 0`` — bake-out never
    constructs a ``Retriever``/touches ``MemoryStore`` at all (§I2.2 structural,
    not merely observed-empty)."""
    contexts = (_frozen_ctx("bank-ctx-0"), _frozen_ctx("bank-ctx-1"))
    chat = _CyclingChat(contents=(_PLAN_JSON,))

    with _RetrieveSpy() as spy:
        records = await run_bank_mloop(
            llm=chat, frozen_contexts=contexts, m_draws=BANK_M_GOLDEN
        )

    assert len(records) == len(contexts) * 2 * BANK_M_GOLDEN
    assert spy.retrieve_call_count == 0
    assert spy.store_read_count == 0


# --------------------------------------------------------------------------- #
# I6-G3 — provenance pass retrieve-count scales structurally with K (separate
# audit, boundary fixed by test name — never conflated with the M-loop's zero)
# --------------------------------------------------------------------------- #


async def test_bank_provenance_retrieve_count_one() -> None:
    """AC I6-G3: ``run_provenance_pass`` (canonical-builder-driven, §I1.3) is a
    *separate* audit from the M-loop's structural zero (§I6-G2): each
    provenance pass contributes a fixed, deterministic, non-zero retrieve
    count (the canonical organ's own ``cycle._retrieve_safely`` prompt-memory
    read + ``embodiment.resolve_destination`` centroid read, once per
    condition), and driving ``K = BANK_K_GOLDEN`` independent contexts through
    it scales that per-context count exactly linearly — ``retrieve-count ==
    per_context_count * K`` (§I5 "1×K" reading: a fixed per-context constant,
    never zero, never K-independent drift). Boundary with I6-G2 is fixed by
    test name, not by a shared instrument state (a fresh spy per test)."""
    embedding = _mock_embedding()
    try:
        with _RetrieveSpy() as spy_one:
            substrate_one = build_competing_cue_substrate(context_id="bank-ctx-single")
            await run_provenance_pass(
                substrate=substrate_one,
                inner_chat=_MockInnerChat(),
                store_factory=_store_factory,
                embedding=embedding,
                run_id="i6-g3-baseline",
                retrieval_now=_FIXED_CLOCK,
                base_ts=_FIXED_CLOCK,
            )
        per_context_count = spy_one.retrieve_call_count
        assert per_context_count > 0, (
            "provenance pass must be a non-M-loop, non-zero retrieve channel "
            "(§I2.2 boundary: this audit is structurally distinct from I6-G2)"
        )

        with _RetrieveSpy() as spy_k:
            for i in range(BANK_K_GOLDEN):
                substrate = build_competing_cue_substrate(context_id=f"bank-ctx-{i}")
                await run_provenance_pass(
                    substrate=substrate,
                    inner_chat=_MockInnerChat(),
                    store_factory=_store_factory,
                    embedding=embedding,
                    run_id=f"i6-g3-k{i}",
                    retrieval_now=_FIXED_CLOCK,
                    base_ts=_FIXED_CLOCK,
                )
        assert spy_k.retrieve_call_count == per_context_count * BANK_K_GOLDEN
    finally:
        await embedding.close()


# --------------------------------------------------------------------------- #
# I6-G4 — arity=1 / divergence-free (readout type + measurement-path absence)
# --------------------------------------------------------------------------- #

_DIVERGENCE_SHAPED_TOKENS: tuple[str, ...] = (
    "divergence",
    "kl_",
    "_kl",
    "js_",
    "_js",
    "kullback",
    "jensen",
    "paired_distribution",
    "paireddistribution",
)


def _identifier_tokens(tree: ast.Module) -> list[str]:
    """Every ``Name``/``Attribute``/``FunctionDef``/``arg``/``AnnAssign``
    identifier the module defines or references (mirrors ``_measurement_guard``'s
    identifier-walk — never a bare string-constant body)."""
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Attribute):
            names.append(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.arg):
            names.append(node.arg)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.append(node.target.id)
    return names


def test_bank_arity_one_divergence_free() -> None:
    """AC I6-G4: (a) the lever readout's conceptual signature is per-context
    single sample-list → scalar (arity=1), type-asserted via
    ``BankLlmCallRecord``'s grouping key — a single record names exactly one
    ``frozen_ctx_id``/``condition`` pair, never two (no cross-context/paired
    field exists on the record type, so no arity-2 paired-distribution shape
    can even be constructed); (b) no ``*_divergence``/KL/JS/paired-distribution
    identifier appears anywhere in the bank measurement path (§I2.3, superset
    grep on top of the shared ``assert_bank_no_measurement_surface`` guard,
    which already bans the ``divergence`` substring — this test additionally
    bans KL/JS/paired-distribution spellings the shared guard does not name)."""
    # (a) arity=1 type assert: BankLlmCallRecord is a single-(ctx,condition,
    # mc_index) row — grouping by (frozen_ctx_id, condition) yields a flat
    # sample list (mc_index-indexed), never a tuple-of-two-contexts row.
    field_names = {f.name for f in dataclasses.fields(bank.BankLlmCallRecord)}
    context_identifying_fields = {
        name
        for name in field_names
        if "ctx" in name.lower() or "context" in name.lower()
    }
    assert context_identifying_fields == {"frozen_ctx_id"}, (
        "BankLlmCallRecord must name exactly one context per row (arity=1); "
        "a second context-identifying field would be the arity=2 paired-"
        "distribution shape §I2.3 forbids"
    )

    # (b) divergence-free superset grep: no KL/JS/paired-distribution spelling
    # anywhere in the bank measurement path (bank.py / bank_fixtures.py), on
    # top of the shared guard's existing "divergence" substring ban.
    for path in _BANK_FILES:
        tree = _parse(path)
        assert_bank_no_measurement_surface(tree, scan_strings=True)
        for token in _identifier_tokens(tree):
            low = token.lower()
            assert not any(banned in low for banned in _DIVERGENCE_SHAPED_TOKENS), (
                f"{path.name}: divergence-shaped identifier {token!r} (§I2.3)"
            )


# --------------------------------------------------------------------------- #
# I6-G5 — frozen-string (continuity-gate explicit restatement of §I2.4)
# --------------------------------------------------------------------------- #


async def test_bank_frozen_string() -> None:
    """AC I6-G5: each context's chat() prompt is byte-identical across the
    whole M pass — only ``sampling`` varies by condition, never by draw
    (§I2.4, continuity-gate restatement; a determinism duplicate of the I2
    bonus test is intentional per the issue's Test Plan)."""
    ctx = _frozen_ctx("bank-ctx-0")
    chat = _CyclingChat(contents=(_PLAN_JSON,))

    records = await run_bank_mloop(
        llm=chat, frozen_contexts=(ctx,), m_draws=BANK_M_GOLDEN
    )

    system_prompts = {r.system_prompt for r in records}
    user_prompts = {r.user_prompt for r in records}
    assert system_prompts == {ctx.system_prompt}
    assert user_prompts == {ctx.user_prompt}

    on_samplings = {r.sampling for r in records if r.condition == "on"}
    off_samplings = {r.sampling for r in records if r.condition == "off"}
    assert on_samplings == {ctx.sampling_on}
    assert off_samplings == {ctx.sampling_off}
    assert ctx.sampling_on != ctx.sampling_off


# --------------------------------------------------------------------------- #
# I6-G6 — T3 materiality desk-audit doc presence (§I7, criterion 4 honest teeth)
# --------------------------------------------------------------------------- #

_REQUIRED_DESK_AUDIT_SECTIONS: tuple[str, ...] = (
    "invariant",
    "criterion 1",
    "criterion 2",
    "criterion 3",
    "criterion 4",
    "sign-off",
)

_REQUIRED_INVARIANT_MARKERS: tuple[str, ...] = (
    "(i)",
    "(ii)",
    "(iii)",
    "(iv)",
    "(v)",
)

_REQUIRED_HONEST_TEETH_MARKERS: tuple[str, ...] = (
    "stimulus",
    "T3 fail",
    "line-close",
    "arc-close",
)


def test_bank_t3_desk_audit_present() -> None:
    """AC I6-G6: the desk-audit doc exists and contains the invariant mapping
    (i)-(v), criterion 1-4 sections (including the criterion-4 honest teeth:
    stimulus judgement -> T3 fail -> line-close -> arc-close), and a
    user/reviewer sign-off section (§I7). Presence/section-grep only — this
    test never adjudicates whether a candidate *is* a stimulus (that judgement
    is the human desk-audit gate itself, §I7 criterion 4)."""
    assert _DESK_AUDIT_DOC.exists(), f"missing desk-audit doc: {_DESK_AUDIT_DOC}"
    text = _DESK_AUDIT_DOC.read_text(encoding="utf-8")
    low = text.lower()

    for section in _REQUIRED_DESK_AUDIT_SECTIONS:
        assert section in low, f"desk-audit doc missing section marker: {section!r}"
    for marker in _REQUIRED_INVARIANT_MARKERS:
        assert marker in text, f"desk-audit doc missing invariant marker: {marker!r}"
    for marker in _REQUIRED_HONEST_TEETH_MARKERS:
        assert marker.lower() in low, (
            f"desk-audit doc missing honest-teeth marker: {marker!r}"
        )
    assert "REFUSED" in text, (
        "desk-audit doc should reference the REFUSED candidate contrast (§I7)"
    )


# --------------------------------------------------------------------------- #
# Self-scan (mirrors test_ecl_bank_spend_guard.py / test_ecl_v1_locomotion.py):
# this test module itself computes no aggregation/divergence surface.
#
# NOTE: the full ``assert_bank_no_measurement_surface`` guard bans any
# identifier merely *containing* the substring "divergence" — which this
# module's own AC-mandated test name (``test_bank_arity_one_divergence_free``,
# fixed by the issue's Acceptance Criteria) and ``_DIVERGENCE_SHAPED_TOKENS``
# constant legitimately do (they *assert the absence* of divergence, they
# never compute one). So this self-scan uses the narrower aggregation-surface
# guard (Counter/set-over-zone/groupby/numpy/pandas/scipy/statistics) instead
# of the full identifier-substring guard — the same "a scope-guard note that
# merely mentions a banned token does not self-trip" convention
# ``_measurement_guard`` documents for docstrings, extended here to this
# module's own AC-mandated identifiers.
# --------------------------------------------------------------------------- #


def test_bank_continuity_module_self_scan() -> None:
    assert_no_aggregation_surface(_parse(_THIS_FILE))


__all__: list[str] = []
