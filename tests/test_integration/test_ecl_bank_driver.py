"""ECL B — Issue 002 tests: bake-out M-loop bank driver + BankLlmCallRecord.

Issue ``loop/20260708-m13-b-code-impl/issues/002-bank-driver-mloop.md`` of the
FROZEN ADR ``.steering/20260707-m13-b-impl-design/design-final.md`` (§I1.4
bake-out / §I5 determinism / §I2 continuity-gate). Ollama-free throughout —
every test drives :func:`~erre_sandbox.integration.embodied.bank.run_bank_mloop`
with a mock chat client, never a live Ollama.

Scope guard (§I9, mirrors ``test_ecl_bank_fixtures.py``): this module tests
*construction*, never measurement — no ``H(zone|ctx)`` / diversity /
divergence assertion appears here (that boundary belongs to a later issue's
ast-guard, §I4).
"""

from __future__ import annotations

import ast
import contextlib
import dataclasses
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from erre_sandbox.cognition import parse_llm_plan
from erre_sandbox.inference.ollama_adapter import ChatResponse
from erre_sandbox.inference.sampling import ResolvedSampling
from erre_sandbox.integration.embodied import bank
from erre_sandbox.integration.embodied.bank import (
    BANK_M_GOLDEN,
    BankLlmCallRecord,
    BankRecordReplayClient,
    bank_order_slots,
    bank_sort_key,
    run_bank_mloop,
)
from erre_sandbox.integration.embodied.bank_fixtures import (
    ZONE_BIAS_ENV_VAR,
    FrozenContext,
)
from erre_sandbox.schemas import Zone

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.inference.ollama_adapter import ChatMessage

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BANK_SRC = _REPO_ROOT / "src" / "erre_sandbox" / "integration" / "embodied" / "bank.py"


def _plan_json(destination_zone: str | None) -> str:
    zone_field = f'"{destination_zone}"' if destination_zone is not None else "null"
    return (
        "{"
        '"thought": "which zone calls to me?", '
        '"utterance": "test", '
        f'"destination_zone": {zone_field}, '
        '"animation": "walk"'
        "}"
    )


def _sampling(temperature: float) -> ResolvedSampling:
    return ResolvedSampling(temperature=temperature, top_p=0.9, repeat_penalty=1.1)


def _frozen_ctx(
    ctx_id: str, *, temp_on: float = 0.7, temp_off: float = 0.5
) -> FrozenContext:
    return FrozenContext(
        frozen_ctx_id=ctx_id,
        system_prompt=f"system-prompt-{ctx_id}",
        user_prompt=f"user-prompt-{ctx_id}",
        sampling_on=_sampling(temp_on),
        sampling_off=_sampling(temp_off),
    )


@dataclass
class _CyclingChat:
    """Ollama-free chat client: re-serves ``contents`` round-robin, records calls."""

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
                "zone_bias_env": os.environ.get(ZONE_BIAS_ENV_VAR),
            }
        )
        return ChatResponse(
            content=content, model="qwen3:8b", eval_count=1, total_duration_ms=0.0
        )


# --------------------------------------------------------------------------- #
# I2-G1 — pre-bias readout = parse_llm_plan(raw).destination_zone
# --------------------------------------------------------------------------- #


async def test_bank_mloop_pre_bias_readout() -> None:
    """``pre_bias_destination_zone`` matches a direct ``parse_llm_plan`` read,
    including the ``None`` case (unparseable / no destination), for every draw."""
    contents = (
        _plan_json("study"),
        _plan_json("garden"),
        _plan_json(None),
        "not json at all",
    )
    chat = _CyclingChat(contents=contents)
    ctx = _frozen_ctx("bank-ctx-0")

    records = await run_bank_mloop(llm=chat, frozen_contexts=(ctx,), m_draws=4)

    assert len(records) == 8  # 4 draws x 2 conditions
    for record in records:
        # ``_CyclingChat`` selects content by global call count mod len(contents);
        # each condition's mc_index range restarts the same content sequence
        # (4 draws == len(contents)), so mc_index alone predicts the content.
        expected_content = contents[record.mc_index % len(contents)]
        expected_plan = parse_llm_plan(expected_content)
        expected_zone = (
            expected_plan.destination_zone if expected_plan is not None else None
        )
        assert record.raw_response == expected_content
        assert record.pre_bias_destination_zone == expected_zone
    # Concretely: the four content slots exercise study / garden / None / unparseable.
    on_records = sorted(
        (r for r in records if r.condition == "on"), key=lambda r: r.mc_index
    )
    assert [r.pre_bias_destination_zone for r in on_records] == [
        Zone.STUDY,
        Zone.GARDEN,
        None,
        None,
    ]


# --------------------------------------------------------------------------- #
# I2-G2 — BankLlmCallRecord 8-field closed set, no EclDecisionRecord
# --------------------------------------------------------------------------- #


def test_bank_llm_call_record_schema() -> None:
    """``BankLlmCallRecord`` is exactly the §I5 8-field closed set, and
    ``bank.py`` never imports/constructs ``loop.EclDecisionRecord``."""
    field_names = {f.name for f in dataclasses.fields(BankLlmCallRecord)}
    assert field_names == {
        "frozen_ctx_id",
        "condition",
        "mc_index",
        "system_prompt",
        "user_prompt",
        "sampling",
        "raw_response",
        "pre_bias_destination_zone",
    }
    assert dataclasses.is_dataclass(BankLlmCallRecord)
    assert BankLlmCallRecord.__dataclass_params__.frozen is True  # type: ignore[attr-defined]

    src = _BANK_SRC.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                assert alias.name != "EclDecisionRecord", (
                    "bank.py must not import loop.EclDecisionRecord "
                    "(Codex 事実誤認 HIGH-2)"
                )
        if isinstance(node, ast.Name):
            assert node.id != "EclDecisionRecord"
        if isinstance(node, ast.Attribute):
            assert node.attr != "EclDecisionRecord"


# --------------------------------------------------------------------------- #
# I2-G3 — mc_index 0..M-1 per (ctx, condition), total-order sorted
# --------------------------------------------------------------------------- #


async def test_bank_record_m_mc_index() -> None:
    """Each ``(ctx, condition)`` yields ``m_draws`` records labelled
    ``mc_index`` 0..M-1, and the returned tuple is already sorted by
    :func:`bank_sort_key`."""
    m_draws = 3
    contexts = (_frozen_ctx("bank-ctx-b"), _frozen_ctx("bank-ctx-a"))
    chat = _CyclingChat(contents=(_plan_json("study"),))

    records = await run_bank_mloop(llm=chat, frozen_contexts=contexts, m_draws=m_draws)

    assert len(records) == len(contexts) * 2 * m_draws
    for ctx in contexts:
        for condition in ("on", "off"):
            subset = [
                r
                for r in records
                if r.frozen_ctx_id == ctx.frozen_ctx_id and r.condition == condition
            ]
            assert [r.mc_index for r in subset] == list(range(m_draws))

    order_slots = bank_order_slots(contexts)
    assert records == tuple(
        sorted(records, key=lambda r: bank_sort_key(r, order_slots))
    )
    # bank-ctx-a sorts before bank-ctx-b (order_slot rank), even though
    # bank-ctx-b was listed first in ``contexts``.
    assert order_slots["bank-ctx-a"] < order_slots["bank-ctx-b"]
    assert records[0].frozen_ctx_id == "bank-ctx-a"


# --------------------------------------------------------------------------- #
# I2-G4 — record -> replay roundtrip, inner_invocations == 0, byte match
# --------------------------------------------------------------------------- #


async def test_bank_replay_roundtrip() -> None:
    """Record K×M×2 via a record-mode :class:`BankRecordReplayClient`, then
    replay the same drive from the recorded tuple: identical records,
    ``inner_invocations == 0``."""
    contexts = (_frozen_ctx("bank-ctx-0"), _frozen_ctx("bank-ctx-1"))
    m_draws = 2
    contents = (_plan_json("study"), _plan_json("garden"), _plan_json(None))
    record_client = BankRecordReplayClient.for_record(_CyclingChat(contents=contents))

    recorded = await run_bank_mloop(
        llm=record_client, frozen_contexts=contexts, m_draws=m_draws
    )
    assert len(recorded) == len(contexts) * 2 * m_draws
    assert record_client.is_replay is False
    assert record_client.inner_invocations == len(recorded)

    replay_client = BankRecordReplayClient.for_replay(recorded)
    replayed = await run_bank_mloop(
        llm=replay_client, frozen_contexts=contexts, m_draws=m_draws
    )

    assert replay_client.is_replay is True
    assert replay_client.inner_invocations == 0
    assert replayed == recorded


# --------------------------------------------------------------------------- #
# I2-G5 — ERRE_ZONE_BIAS_P pinned to "0" for the drive, restored after
# --------------------------------------------------------------------------- #


async def test_bank_zone_bias_pinned_off() -> None:
    """``run_bank_mloop`` pins ``ERRE_ZONE_BIAS_P=0`` for its whole drive
    (every ``chat()`` call observes ``"0"``) and restores the prior hostile
    value afterward."""
    prior = os.environ.get(ZONE_BIAS_ENV_VAR)
    os.environ[ZONE_BIAS_ENV_VAR] = "1.0"
    try:
        chat = _CyclingChat(contents=(_plan_json("study"),))
        ctx = _frozen_ctx("bank-ctx-0")

        await run_bank_mloop(llm=chat, frozen_contexts=(ctx,), m_draws=2)

        assert len(chat.calls) == 4
        assert all(call["zone_bias_env"] == "0" for call in chat.calls)
        assert os.environ.get(ZONE_BIAS_ENV_VAR) == "1.0"
    finally:
        if prior is None:
            os.environ.pop(ZONE_BIAS_ENV_VAR, None)
        else:
            os.environ[ZONE_BIAS_ENV_VAR] = prior


async def test_bank_zone_bias_restored_on_exception() -> None:
    """The pin restores the prior env var even if a ``chat()`` call raises."""

    @dataclass
    class _RaisingChat:
        async def chat(self, *_args: Any, **_kwargs: Any) -> ChatResponse:
            raise RuntimeError("boom")

    prior = os.environ.get(ZONE_BIAS_ENV_VAR)
    os.environ[ZONE_BIAS_ENV_VAR] = "0.5"
    try:
        ctx = _frozen_ctx("bank-ctx-0")
        with contextlib.suppress(RuntimeError):
            await run_bank_mloop(llm=_RaisingChat(), frozen_contexts=(ctx,), m_draws=1)
        assert os.environ.get(ZONE_BIAS_ENV_VAR) == "0.5"
    finally:
        if prior is None:
            os.environ.pop(ZONE_BIAS_ENV_VAR, None)
        else:
            os.environ[ZONE_BIAS_ENV_VAR] = prior


# --------------------------------------------------------------------------- #
# Bonus — frozen-string invariant (§I2.4): prompt byte-identical across draws
# --------------------------------------------------------------------------- #


async def test_bank_mloop_prompt_frozen_across_draws() -> None:
    """Every draw of a ``(ctx, condition)`` pair sees the byte-identical
    ``(system_prompt, user_prompt)`` — only ``sampling`` differs by condition,
    never by draw (§I2.4 frozen-string invariant)."""
    ctx = _frozen_ctx("bank-ctx-0")
    chat = _CyclingChat(contents=(_plan_json("study"),))

    records = await run_bank_mloop(
        llm=chat, frozen_contexts=(ctx,), m_draws=BANK_M_GOLDEN
    )

    assert len({r.system_prompt for r in records}) == 1
    assert len({r.user_prompt for r in records}) == 1
    assert next(iter({r.system_prompt for r in records})) == ctx.system_prompt
    on_samplings = {r.sampling for r in records if r.condition == "on"}
    off_samplings = {r.sampling for r in records if r.condition == "off"}
    assert on_samplings == {ctx.sampling_on}
    assert off_samplings == {ctx.sampling_off}


# --------------------------------------------------------------------------- #
# Bonus — bank manifest overlay (§I5 schema-version bump, live_v1 precedent)
# --------------------------------------------------------------------------- #


def test_bank_manifest_overlay_non_mutating() -> None:
    base = {"manifest_version": "ecl-v0-handoff-2"}
    overlaid = bank.attach_bank_observables(base)
    assert "bank" not in base
    assert overlaid["bank"] == {"bank_schema_version": bank.BANK_SCHEMA_VERSION}
    assert overlaid["manifest_version"] == "ecl-v0-handoff-2"


# --------------------------------------------------------------------------- #
# Bonus — BankAnnotationRow type-only closed set (§I4, writer deferred)
# --------------------------------------------------------------------------- #


def test_bank_annotation_row_schema_type_only() -> None:
    field_names = {f.name for f in dataclasses.fields(bank.BankAnnotationRow)}
    assert field_names == {
        "frozen_ctx_id",
        "condition",
        "mc_index",
        "pre_bias_destination_zone",
        "resolved_from",
    }
    assert bank.BankAnnotationRow.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
