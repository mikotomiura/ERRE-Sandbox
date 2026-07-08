"""ECL B — bake-out M-loop bank driver (zone bias off + pre-bias readout).

Issue 002 (``loop/20260708-m13-b-code-impl/issues/002-bank-driver-mloop.md``) of
the FROZEN ADR ``.steering/20260707-m13-b-impl-design/design-final.md`` (§I1.4
bake-out / §I5 determinism / §I2 continuity-gate type invariants). Consumes
Issue 001's :class:`~erre_sandbox.integration.embodied.bank_fixtures.FrozenContext`
(a byte-immutable ``(system_prompt, user_prompt, sampling_on, sampling_off)``
bundle) and drives it through ``chat()`` **directly** — never through
:func:`~erre_sandbox.integration.embodied.loop.run_ecl_loop` — ``m_draws`` times
per ``(frozen_ctx, condition)`` pair. This is the **bake-out M-sampling loop**
(§I1.4): full cognition-cycle machinery (retriever / store / world_model /
zone-bias resample) never runs inside it.

Pieces this module owns:

* :class:`BankLlmCallRecord` — the bank-only Plane 2 record (§I5, Codex 事実誤認
  HIGH-2): ``{frozen_ctx_id, condition, mc_index, system_prompt, user_prompt,
  sampling, raw_response, pre_bias_destination_zone}``, the §I5 8-field closed
  set exactly. **Never** ``loop.EclDecisionRecord`` — that full-cycle record
  carries ``bias_fired`` / ``move_decision`` / envelope provenance that bake-out
  calls structurally cannot produce (there is no cognition cycle to produce
  them), so reusing it would silently fabricate fields. ``pre_bias_destination_zone``
  is a **direct** ``parse_llm_plan(raw_response).destination_zone`` read — the
  zone the LLM asked for, before any ``_bias_target_zone`` resample the live
  cycle would otherwise apply (Codex 事実誤認 HIGH-1: the bake-out path never
  runs ``_bias_target_zone`` at all, so this is not just "pin the resample off",
  it structurally cannot fire).
* :func:`run_bank_mloop` — the bake-out driver: for each ``frozen_ctx`` in
  ``frozen_contexts`` and each ``condition`` in ``("on", "off")``, calls
  ``llm.chat([system, user], sampling=<frozen sampling>)`` exactly ``m_draws``
  times, direct-parsing each raw response into a :class:`BankLlmCallRecord`.
  Pins :data:`~erre_sandbox.integration.embodied.bank_fixtures.ZONE_BIAS_ENV_VAR`
  to ``"0"`` for the duration (belt-and-suspenders — §I1.4's zone-bias/lever
  confound removal — even though the bake-out path never constructs a
  ``CognitionCycle`` and so never reads that env var itself). Never imports or
  calls ``memory.Retriever`` / ``memory.MemoryStore`` — retrieve-count=0 is
  therefore **structural**, not merely observed (§I2.2).
* :class:`BankRecordReplayClient` — a thin bank-axis wrapper over
  :class:`~erre_sandbox.integration.embodied.loop.RecordReplayChatClient`
  (the :class:`~erre_sandbox.integration.embodied.live_v1.SamplingSpyChatClient`
  wrapper precedent: delegate every method, add nothing to the wrapped
  client's own record/replay contract). :meth:`BankRecordReplayClient.for_record`
  wraps a fresh inner chat client in record mode;
  :meth:`BankRecordReplayClient.for_replay` rebuilds a replay-mode inner
  client from a prior run's
  :class:`BankLlmCallRecord` tuple (:func:`bank_records_to_recorded_calls`) so a
  second :func:`run_bank_mloop` drive over the *same* ``frozen_contexts`` /
  ``m_draws`` reproduces the identical record tuple with
  ``inner_invocations == 0`` (§I5 Plane 2 record-M, mc-index label).
* :func:`bank_order_slots` / :func:`bank_sort_key` — the total order
  ``(order_slot, frozen_ctx_id, condition, mc_index, seq)`` (§I5, a superset of
  ``handoff.py``'s ``(order_slot, agent_tick, seq)``). ``order_slot`` is the
  0-based rank of ``frozen_ctx_id`` among the run's contexts sorted by id
  (mirrors ``loop.run_ecl_loop``'s ``sorted([agent_id]).index(agent_id)``);
  ``condition`` ranks ``"on"`` before ``"off"`` (the ADR's own "T_on/T_off"
  reading order); ``seq`` is a literal ``0`` — the bake-out loop issues exactly
  one ``chat()`` call per ``(ctx, condition, mc_index)`` triple, so ``seq`` only
  exists to keep this key a superset of ``handoff.py``'s, not because more than
  one call can ever share a triple today.
* :data:`BANK_M_GOLDEN` / :data:`BANK_K_GOLDEN` — tiny pinned construction/golden
  constants (never the powered ``M_min``/``K`` proposal of §I6, which is
  C-proper).
* :data:`BANK_SCHEMA_VERSION` / :func:`build_bank_manifest_overlay` /
  :func:`attach_bank_observables` — a bank-only manifest overlay
  (``handoff.MANIFEST_SCHEMA_VERSION`` untouched, ``live_v1.attach_live_v1_observables``
  overlay precedent: a fresh non-mutating dict merge).
* :class:`BankAnnotationRow` / :data:`BANK_ANNOTATION_SCHEMA_VERSION` — the
  opaque raw-row **type** the Issue 005 annotation writer will emit
  (``{frozen_ctx_id, condition, mc_index, pre_bias_destination_zone,
  resolved_from}``). Defined here for the schema contract only; this module
  never constructs, writes, or reads a bulk sequence of these rows, and
  computes no aggregate over them (§I4 — that boundary belongs to Issue 005).

Scope guard (§I9/§I4, binding, mirrors ``bank_fixtures.py`` / ``live.py`` /
``live_v1.py`` / ``loop.py``). This is a **construction** apparatus, **NOT a
measurement line**. It computes no ``H(zone|ctx)`` / count / diversity /
divergence / floor / verdict, and imports no ``evidence`` / ``spdm`` /
``runningness`` machinery, no ``math.log``, no ``collections.Counter``, no
``set()`` aggregation over zones, no ``itertools.groupby``, and no
``numpy`` / ``pandas`` / ``scipy`` / ``statistics``. ``organ`` modules
(``cognition/cycle.py`` / ``cognition/parse.py`` / ``integration/embodied/loop.py``
/ ``integration/embodied/handoff.py`` / ``integration/embodied/live.py`` /
``integration/embodied/live_v1.py``) and ``bank_fixtures.py`` are imported here,
never modified.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Literal

from erre_sandbox.cognition import parse_llm_plan
from erre_sandbox.inference.ollama_adapter import ChatMessage, ChatResponse
from erre_sandbox.integration.embodied.bank_fixtures import (
    ZONE_BIAS_ENV_VAR,
    FrozenContext,
)
from erre_sandbox.integration.embodied.loop import (
    RecordedLlmCall,
    RecordReplayChatClient,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.inference.sampling import ResolvedSampling
    from erre_sandbox.schemas import Zone

# --------------------------------------------------------------------------- #
# Bank-only condition axis + total-order tie-break (§I5)
# --------------------------------------------------------------------------- #

BankCondition = Literal["on", "off"]
"""``"on"`` = T_on (``sampling_on``, λ_ctx-modulated); ``"off"`` = T_off
(``sampling_off``, unmodulated). Never a bare ``str`` (§I3.3)."""

_CONDITIONS: Final[tuple[BankCondition, ...]] = ("on", "off")
"""Bake-out iteration order — also the tie-break rank order (§I5): T_on before
T_off, the ADR's own reading order for the condition pair."""

_CONDITION_RANK: Final[dict[BankCondition, int]] = {"on": 0, "off": 1}


def bank_order_slots(frozen_contexts: Sequence[FrozenContext]) -> dict[str, int]:
    """The 0-based rank of each ``frozen_ctx_id`` among ``frozen_contexts``.

    Sorted by id (§I5 ``order_slot``, mirrors ``loop.run_ecl_loop``'s
    ``sorted([agent_id]).index(agent_id)`` single-agent precedent generalised
    to K contexts).
    """
    ordered = sorted(frozen_contexts, key=lambda c: c.frozen_ctx_id)
    return {ctx.frozen_ctx_id: slot for slot, ctx in enumerate(ordered)}


def bank_sort_key(
    record: BankLlmCallRecord, order_slots: dict[str, int]
) -> tuple[int, str, int, int, int]:
    """The total order ``(order_slot, frozen_ctx_id, condition, mc_index, seq)``.

    A superset of ``handoff.py:576``'s ``(order_slot, agent_tick, seq)``;
    ``seq`` is a literal ``0`` (see module docstring).
    """
    return (
        order_slots[record.frozen_ctx_id],
        record.frozen_ctx_id,
        _CONDITION_RANK[record.condition],
        record.mc_index,
        0,
    )


# --------------------------------------------------------------------------- #
# BankLlmCallRecord — bank-only Plane 2 record (§I5, Codex 事実誤認 HIGH-2)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class BankLlmCallRecord:
    """One bake-out ``chat()`` call — the bank Plane 2 replay unit (§I5).

    The §I5 8-field closed set exactly. **Never** ``loop.EclDecisionRecord``
    (Codex 事実誤認 HIGH-2, I2-G2): that full-cycle record's ``bias_fired`` /
    ``move_decision`` / ``envelope_provenance`` fields describe a
    ``CognitionCycle`` step this bake-out call never runs.

    ``pre_bias_destination_zone`` is the **pre-bias** parsed zone
    (``parse_llm_plan(raw_response).destination_zone``, or ``None`` when the
    response fails to parse or names no destination) — never a post-bias zone,
    because no bias resample runs on this path at all (§I1.4).
    """

    frozen_ctx_id: str
    condition: BankCondition
    mc_index: int
    system_prompt: str
    user_prompt: str
    sampling: ResolvedSampling
    raw_response: str
    pre_bias_destination_zone: Zone | None


# --------------------------------------------------------------------------- #
# Pinned construction/golden constants (§I5/§I6 — never the powered proposal)
# --------------------------------------------------------------------------- #

BANK_M_GOLDEN: Final[int] = 4
"""Tiny pinned draws-per-``(ctx, condition)`` count for construction shakedown
and the Issue 005 golden bake — **not** the §I6 powered ``M_min ~ 300``
proposal (non-binding, C-proper). Keeps the committed replay fixture small."""

BANK_K_GOLDEN: Final[int] = 2
"""Tiny pinned frozen-context count for construction shakedown and the golden
bake — **not** the §I6 powered ``K ~ 8`` proposal (non-binding, C-proper)."""


# --------------------------------------------------------------------------- #
# Zone-bias pin (§I1.4 belt-and-suspenders — mirrors bank_fixtures pin/restore)
# --------------------------------------------------------------------------- #


def _pin_zone_bias_off() -> str | None:
    """Pin ``bank_fixtures.ZONE_BIAS_ENV_VAR`` to ``"0"``.

    Returns the prior value (or ``None``) so the caller can restore it. A
    local duplicate of ``bank_fixtures._pinned_zone_bias_off``'s pin/restore
    pair (not a context manager here, so ``run_bank_mloop`` can wrap it around
    its own ``try/finally`` alongside the ``m_draws`` loop) —
    belt-and-suspenders (§I1.4): the bake-out loop never constructs a
    ``CognitionCycle`` and so never reads this env var itself, but pinning it
    keeps the invariant visible and testable at the driver boundary (I2-G5).
    """
    prior = os.environ.get(ZONE_BIAS_ENV_VAR)
    os.environ[ZONE_BIAS_ENV_VAR] = "0"
    return prior


def _restore_zone_bias(prior: str | None) -> None:
    if prior is None:
        os.environ.pop(ZONE_BIAS_ENV_VAR, None)
    else:
        os.environ[ZONE_BIAS_ENV_VAR] = prior


# --------------------------------------------------------------------------- #
# The bake-out M-loop driver (§I1.4/§I5)
# --------------------------------------------------------------------------- #


async def run_bank_mloop(
    *,
    llm: Any,
    frozen_contexts: Sequence[FrozenContext],
    m_draws: int = BANK_M_GOLDEN,
) -> tuple[BankLlmCallRecord, ...]:
    """Drive the bake-out M-sampling loop over ``frozen_contexts`` (§I1.4).

    Iterates ``frozen_contexts`` **sorted by** ``frozen_ctx_id`` (never the
    caller-supplied order — TASK-POST /cross-review HIGH/H2, both reviewers:
    an unsorted input previously desynced the actual ``chat()`` call order
    from the :func:`bank_sort_key` order :func:`bank_records_to_recorded_calls`
    assumes, so a subsequent replay silently paired one context's raw
    response with another context's record). This makes the bake-out call
    order equal to :func:`bank_order_slots` rank order *unconditionally*, not
    merely "by construction when the caller happens to pass sorted input".

    For each ``frozen_ctx`` (in that sorted order) and each condition in
    ``("on", "off")``, calls ``llm.chat([system, user], sampling=<frozen
    sampling>, think=False)`` exactly ``m_draws`` times — ``think=False`` is
    forced explicitly (TASK-POST /cross-review HIGH/H3, code-reviewer): the
    provenance pass (``bank_fixtures.run_provenance_pass`` via
    ``live.ThinkOffChatClient``) already forces ``think=False``, and without a
    matching forward here a real backend's default-thinking-on sampling
    regime would silently diverge from the frozen context's provenance regime
    (``reference_qwen3_ollama_gotchas`` / ECL v0: ``think=False`` is
    load-bearing). The frozen ``(system_prompt, user_prompt)`` pair is
    byte-identical across every draw of a ``(ctx, condition)`` pair (§I2.4
    frozen-string invariant; the sampling seed is the only thing that can vary
    a real backend's output). ``llm`` is any duck-typed chat client (a plain
    mock, or a :class:`BankRecordReplayClient`) — this function never inspects
    its type and never touches ``memory.Retriever`` / ``memory.MemoryStore``
    (retrieve-count=0 is therefore structural, not observed, §I2.2).

    Pins :data:`~erre_sandbox.integration.embodied.bank_fixtures.ZONE_BIAS_ENV_VAR`
    to ``"0"`` for the whole drive and restores the prior value afterward
    (I2-G5). Returns the records already sorted by :func:`bank_sort_key`
    (I2-G3) — the bake-out iteration order and the sorted order coincide by
    construction (T_on before T_off, ascending ``mc_index``, contexts visited
    in sorted rank order), so the sort is a determinism-proving no-op rather
    than a reordering.
    """
    order_slots = bank_order_slots(frozen_contexts)
    prior = _pin_zone_bias_off()
    try:
        records: list[BankLlmCallRecord] = []
        for ctx in sorted(frozen_contexts, key=lambda c: c.frozen_ctx_id):
            messages = (
                ChatMessage(role="system", content=ctx.system_prompt),
                ChatMessage(role="user", content=ctx.user_prompt),
            )
            for condition in _CONDITIONS:
                sampling = ctx.sampling_on if condition == "on" else ctx.sampling_off
                for mc_index in range(m_draws):
                    response = await llm.chat(messages, sampling=sampling, think=False)
                    plan = parse_llm_plan(response.content)
                    records.append(
                        BankLlmCallRecord(
                            frozen_ctx_id=ctx.frozen_ctx_id,
                            condition=condition,
                            mc_index=mc_index,
                            system_prompt=ctx.system_prompt,
                            user_prompt=ctx.user_prompt,
                            sampling=sampling,
                            raw_response=response.content,
                            pre_bias_destination_zone=(
                                plan.destination_zone if plan is not None else None
                            ),
                        )
                    )
    finally:
        _restore_zone_bias(prior)
    return tuple(sorted(records, key=lambda r: bank_sort_key(r, order_slots)))


# --------------------------------------------------------------------------- #
# BankRecordReplayClient — bank-axis record/replay wrapper (§I5, live_v1 precedent)
# --------------------------------------------------------------------------- #

_BANK_REPLAY_MODEL: Final[str] = "bank-replay"
"""Placeholder ``ChatResponse.model`` tag used to rebuild a replay stream from
a prior :class:`BankLlmCallRecord` tuple (:func:`bank_records_to_recorded_calls`).
``BankLlmCallRecord`` does not carry a ``model`` field (§I5 8-field closed set),
so this is a fixed, inert value — nothing downstream reads it; only
``.content`` (the ``raw_response``) is re-parsed on replay."""


def bank_records_to_recorded_calls(
    records: Sequence[BankLlmCallRecord],
) -> tuple[RecordedLlmCall, ...]:
    """Rebuild a Plane 2 replay stream from a prior record run's bank records.

    ``records`` must be supplied in the exact ``chat()`` call order of the
    original :func:`run_bank_mloop` drive (which, by construction, equals
    :func:`bank_sort_key` order — see :func:`run_bank_mloop`'s docstring), so a
    :class:`~erre_sandbox.integration.embodied.loop.RecordReplayChatClient`
    built from this stream serves the ``mc_index``-th ``(ctx, condition)`` draw
    back to the ``mc_index``-th call of a re-drive over the same
    ``frozen_contexts`` / ``m_draws``. Every rebuilt call is tagged ``outcome="ok"``
    (bake-out draws never see an ``OllamaUnavailableError`` outcome; parsing a
    ``None``-plan response is a valid ``ok`` call whose
    ``pre_bias_destination_zone`` is ``None``, not a ``raised`` call).
    """
    return tuple(
        RecordedLlmCall(
            system_prompt=r.system_prompt,
            user_prompt=r.user_prompt,
            sampling=r.sampling,
            response=ChatResponse(
                content=r.raw_response,
                model=_BANK_REPLAY_MODEL,
                eval_count=0,
                total_duration_ms=0.0,
            ),
            outcome="ok",
        )
        for r in records
    )


class BankRecordReplayClient:
    """Bank-axis wrapper over ``loop.RecordReplayChatClient`` (§I5).

    Follows the ``live_v1.SamplingSpyChatClient`` wrapper idiom: delegate every
    method/property to the wrapped client, add nothing to its record/replay
    contract. The bank axis's own tagging (``frozen_ctx_id`` / ``condition`` /
    ``mc_index``) lives in :func:`run_bank_mloop`'s deterministic iteration
    order, not in this client — a plain :class:`RecordedLlmCall` has no room
    for those fields, and this wrapper's only job is to give the bake-out
    driver's ``llm`` argument a bank-specific type identity distinct from the
    full-cycle ECL harness (Codex 事実誤認 HIGH-2: nothing here ever touches
    ``loop.EclDecisionRecord``).

    * :meth:`for_record` — wraps a fresh inner chat client in record mode.
    * :meth:`for_replay` — rebuilds a replay-mode inner client from a prior
      run's :class:`BankLlmCallRecord` tuple (:func:`bank_records_to_recorded_calls`).
      ``inner_invocations`` stays ``0`` through a full replay drive (I2-G4).
    """

    def __init__(self, inner: RecordReplayChatClient) -> None:
        self._inner = inner

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        sampling: ResolvedSampling,
        model: str | None = None,
        options: dict[str, Any] | None = None,
        think: bool | None = None,
    ) -> ChatResponse:
        return await self._inner.chat(
            messages,
            sampling=sampling,
            model=model,
            options=options,
            think=think,
        )

    @property
    def used(self) -> tuple[RecordedLlmCall, ...]:
        """Delegate to the wrapped client (record order == replay-service order)."""
        return self._inner.used

    @property
    def inner_invocations(self) -> int:
        """Delegate: ``0`` in replay mode (the I2-G4 witness)."""
        return self._inner.inner_invocations

    @property
    def is_replay(self) -> bool:
        """Delegate to the wrapped client's replay flag."""
        return self._inner.is_replay

    @classmethod
    def for_record(cls, inner_chat: Any) -> BankRecordReplayClient:
        """Build a record-mode client wrapping ``inner_chat`` (mock or real)."""
        return cls(RecordReplayChatClient(inner=inner_chat))

    @classmethod
    def for_replay(cls, records: Sequence[BankLlmCallRecord]) -> BankRecordReplayClient:
        """Build a replay-mode client that re-serves ``records`` in call order."""
        return cls(
            RecordReplayChatClient(recorded=bank_records_to_recorded_calls(records))
        )


# --------------------------------------------------------------------------- #
# Bank manifest overlay (§I5 schema-version bump, live_v1 attach precedent)
# --------------------------------------------------------------------------- #

BANK_SCHEMA_VERSION: Final[str] = "ecl-bank-1"
"""The bank driver's own manifest-overlay schema version (§I5 trace schema
version bump). ``handoff.MANIFEST_SCHEMA_VERSION`` (``"ecl-v0-handoff-2"``) is
never touched — this is an independent overlay key, not a replacement."""


def build_bank_manifest_overlay() -> dict[str, Any]:
    """Return the bank ``observables``-style overlay block (a fresh dict)."""
    return {"bank_schema_version": BANK_SCHEMA_VERSION}


def attach_bank_observables(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return ``manifest`` with the bank overlay attached (non-mutating).

    ``handoff.build_manifest`` (untouched) has no ``bank`` field; this is the
    bank driver's own overlay seam, mirroring
    ``live_v1.attach_live_v1_observables``.
    """
    overlaid = dict(manifest)
    overlaid["bank"] = build_bank_manifest_overlay()
    return overlaid


# --------------------------------------------------------------------------- #
# Opaque annotation raw-row type (§I4 — type only; Issue 005 owns the writer)
# --------------------------------------------------------------------------- #

BANK_ANNOTATION_SCHEMA_VERSION: Final[str] = "ecl-bank-annotation-1"
"""Schema version for the Issue 005 annotation side-file (independent of
:data:`BANK_SCHEMA_VERSION` and of ``handoff.MANIFEST_SCHEMA_VERSION``)."""


@dataclass(frozen=True, slots=True)
class BankAnnotationRow:
    """One opaque raw annotation row's **type** (§I4 — V4a/V4b-style raw row).

    ``{frozen_ctx_id, condition, mc_index, pre_bias_destination_zone,
    resolved_from}`` — no ``H(zone|ctx)`` / count / diversity / divergence
    field, and this module never constructs, writes, or aggregates a sequence
    of these (that writer is Issue 005's scope). ``resolved_from`` documents
    how the row's zone label was derived — a fixed provenance tag (e.g.
    ``"pre_bias_direct_parse"``), never a resolver decision (there is no
    ``cognition.embodiment.resolve_destination`` call on this path, §I1.1).
    """

    frozen_ctx_id: str
    condition: BankCondition
    mc_index: int
    pre_bias_destination_zone: Zone | None
    resolved_from: str | None


__all__ = [
    "BANK_ANNOTATION_SCHEMA_VERSION",
    "BANK_K_GOLDEN",
    "BANK_M_GOLDEN",
    "BANK_SCHEMA_VERSION",
    "BankAnnotationRow",
    "BankCondition",
    "BankLlmCallRecord",
    "BankRecordReplayClient",
    "attach_bank_observables",
    "bank_order_slots",
    "bank_records_to_recorded_calls",
    "bank_sort_key",
    "build_bank_manifest_overlay",
    "run_bank_mloop",
]
