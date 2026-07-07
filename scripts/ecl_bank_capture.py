#!/usr/bin/env python
"""ECL B — bank golden capture/verify CLI (mock-only, Ollama-free, D-10).

Issue 005 (``loop/20260708-m13-b-code-impl/issues/005-annotation-golden.md``) of
the FROZEN ADR ``.steering/20260707-m13-b-impl-design/design-final.md`` (§I4
raw-row-only annotation / §I5 bank golden = small committed replay fixture,
cross-platform). D-10 (grill-goals.md) binds the whole 反復 bank Loop slice to
**mock-only** — this script never opens a live Ollama connection and never
imports ``OllamaChatClient``; every ``chat()`` call in this module is served by
a small deterministic in-process mock.

``--capture`` drives, for :data:`~erre_sandbox.integration.embodied.bank.BANK_K_GOLDEN`
frozen contexts:

1. Issue 001's :func:`~erre_sandbox.integration.embodied.bank_fixtures.run_provenance_pass`
   (one full-cycle pass per condition, mock inner chat, canonical builders — the
   frozen ``(system_prompt, user_prompt, sampling_on, sampling_off)`` bundle) to
   build the K :class:`~erre_sandbox.integration.embodied.bank_fixtures.FrozenContext`.
2. Issue 002's :func:`~erre_sandbox.integration.embodied.bank.run_bank_mloop`
   (bake-out, mock inner chat, zone bias off) over the K frozen contexts,
   ``m_draws=BANK_M_GOLDEN`` × 2 conditions each — the §I4 ``2·M·K`` call cap is
   asserted (fail-fast) against the record-mode client's ``inner_invocations``.

It then writes the **opaque raw-row annotation side file** (§I4:
``{frozen_ctx_id, condition, mc_index, pre_bias_destination_zone,
resolved_from}`` — the closed set exactly, never an aggregate) alongside the
bank-records replay fixture and a manifest, all serialised through
``handoff.canonical_dumps`` (6-decimal float quantisation, the cross-platform
``libm``-drift absorber, ``feedback_golden_crossplatform_float_drift``) and
``handoff.capture_env_pins``.

``--verify`` is the companion **Ollama-free** replay-verify (I5-G2/I5-G3): it
rebuilds the K frozen contexts *from the committed bank records themselves*
(every record already carries its context's ``system_prompt`` / ``user_prompt``
/ resolved sampling — no provenance pass, and therefore no chat call at all, is
needed to reconstruct them) and re-drives :func:`run_bank_mloop` through a
:class:`~erre_sandbox.integration.embodied.bank.BankRecordReplayClient` built in
**replay** mode (:meth:`~erre_sandbox.integration.embodied.bank.BankRecordReplayClient.for_replay`),
asserting ``inner_invocations == 0`` and a byte-identical re-render of every
artifact (reusing the committed ``env_pins`` so a fresh machine's package/
interpreter snapshot can never drift the manifest bytes).

Scope guard (§I9/§I4, binding, mirrors ``bank.py`` / ``bank_fixtures.py``). This
is a **construction** apparatus, **NOT a measurement line**. It computes no
``H(zone|ctx)`` / diversity / divergence / floor / verdict over the annotation
rows, and imports no ``evidence`` / ``spdm`` / ``runningness`` machinery, no
``math.log``, no ``collections.Counter``, no ``set()`` aggregation over zones,
no ``itertools.groupby``, and no ``numpy`` / ``pandas`` / ``scipy`` /
``statistics``. ``bank.py`` / ``bank_fixtures.py`` / ``handoff.py`` / ``loop.py``
are imported here, never modified.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, cast

import httpx

from erre_sandbox.inference.ollama_adapter import ChatResponse
from erre_sandbox.inference.sampling import ResolvedSampling
from erre_sandbox.integration.embodied import handoff
from erre_sandbox.integration.embodied.bank import (
    BANK_ANNOTATION_SCHEMA_VERSION,
    BANK_K_GOLDEN,
    BANK_M_GOLDEN,
    BankAnnotationRow,
    BankLlmCallRecord,
    BankRecordReplayClient,
    attach_bank_observables,
)
from erre_sandbox.integration.embodied.bank import run_bank_mloop as _run_bank_mloop
from erre_sandbox.integration.embodied.bank_fixtures import (
    BANK_LAMBDA_CTX,
    FrozenContext,
    build_competing_cue_substrate,
    run_provenance_pass,
)
from erre_sandbox.memory import EmbeddingClient, MemoryStore
from erre_sandbox.schemas import Zone

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.inference.ollama_adapter import ChatMessage
    from erre_sandbox.integration.embodied.bank import BankCondition

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUT_DIR = _REPO_ROOT / "experiments" / "20260708-m13-b-bank" / "artifacts"
_DEFAULT_RUN_ID = "ecl-bank-golden"
_FIXED_CLOCK: Final[datetime] = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

BANK_GOLDEN_MANIFEST_VERSION: Final[str] = "ecl-bank-golden-1"
"""This CLI's own manifest-shape version (independent of
:data:`~erre_sandbox.integration.embodied.bank.BANK_SCHEMA_VERSION` and
``handoff.MANIFEST_SCHEMA_VERSION``)."""

_RESOLVED_FROM_TAG: Final[str] = "pre_bias_direct_parse"
"""The annotation ``resolved_from`` provenance tag (§I4/``BankAnnotationRow``
docstring): every row's zone label is a direct pre-bias
``parse_llm_plan(...).destination_zone`` read, never a resolver decision."""


# --------------------------------------------------------------------------- #
# Ollama-free mocks (D-10 — mock-only, no live Ollama import anywhere here)
# --------------------------------------------------------------------------- #


def _mock_embedding() -> EmbeddingClient:
    """A constant-vector embedding — deterministic and Ollama-free."""
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


def _store_factory() -> MemoryStore:
    return MemoryStore(db_path=":memory:")


def _plan_json(zone: str | None) -> str:
    zone_field = f'"{zone}"' if zone is not None else "null"
    return (
        "{"
        '"thought": "which zone calls to me?", '
        '"utterance": "bank mock draw", '
        f'"destination_zone": {zone_field}, '
        '"animation": "walk"'
        "}"
    )


_PROVENANCE_PLAN_JSON: Final[str] = _plan_json(Zone.STUDY.value)
"""Fixed provenance-pass response content — the destination this call parses to
is never read downstream (only the rendered prompt/sampling the canonical
builders produced matters, §I1.3), so a single fixed content keeps the
provenance pass's own record deterministic without adding meaning."""

_MLOOP_PLAN_CONTENTS: Final[tuple[str, ...]] = (
    _plan_json(Zone.STUDY.value),
    _plan_json(Zone.GARDEN.value),
    _plan_json(None),
)
"""Bake-out M-loop mock content cycle — deterministic, round-robin. Includes one
unparseable-destination draw (``destination_zone: null``) so the golden fixture
exercises :class:`BankLlmCallRecord`'s ``pre_bias_destination_zone is None``
branch (§I5) alongside the two Z_comp zones, all schema-only — no meaning is
attached to which zone "wins" (construction, not measurement)."""


@dataclass
class _ProvenanceMockChat:
    """Ollama-free inner chat for the provenance pass — one fixed response."""

    content: str = _PROVENANCE_PLAN_JSON
    calls: int = 0

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        sampling: ResolvedSampling,
        model: str | None = None,
        options: dict[str, Any] | None = None,
        think: bool | None = None,
    ) -> ChatResponse:
        self.calls += 1
        return ChatResponse(
            content=self.content, model="bank-mock", eval_count=1, total_duration_ms=0.0
        )


@dataclass
class _MloopMockChat:
    """Ollama-free inner chat for the bake-out M-loop — deterministic round-robin."""

    contents: tuple[str, ...] = _MLOOP_PLAN_CONTENTS
    calls: int = field(default=0)

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        sampling: ResolvedSampling,
        model: str | None = None,
        options: dict[str, Any] | None = None,
        think: bool | None = None,
    ) -> ChatResponse:
        content = self.contents[self.calls % len(self.contents)]
        self.calls += 1
        return ChatResponse(
            content=content, model="bank-mock", eval_count=1, total_duration_ms=0.0
        )


# --------------------------------------------------------------------------- #
# Serialisation (own to this script — bank.py never grows a bulk (de)serialiser)
# --------------------------------------------------------------------------- #


def _bank_record_to_dict(record: BankLlmCallRecord) -> dict[str, Any]:
    return {
        "frozen_ctx_id": record.frozen_ctx_id,
        "condition": record.condition,
        "mc_index": record.mc_index,
        "system_prompt": record.system_prompt,
        "user_prompt": record.user_prompt,
        "sampling": record.sampling.model_dump(),
        "raw_response": record.raw_response,
        "pre_bias_destination_zone": (
            record.pre_bias_destination_zone.value
            if record.pre_bias_destination_zone is not None
            else None
        ),
    }


def _bank_record_from_dict(data: dict[str, Any]) -> BankLlmCallRecord:
    condition = data["condition"]
    if condition not in ("on", "off"):
        msg = f"invalid bank condition: {condition!r}"
        raise ValueError(msg)
    zone_value = data["pre_bias_destination_zone"]
    return BankLlmCallRecord(
        frozen_ctx_id=data["frozen_ctx_id"],
        condition=cast("BankCondition", condition),
        mc_index=data["mc_index"],
        system_prompt=data["system_prompt"],
        user_prompt=data["user_prompt"],
        sampling=ResolvedSampling.model_validate(data["sampling"]),
        raw_response=data["raw_response"],
        pre_bias_destination_zone=(
            Zone(zone_value) if zone_value is not None else None
        ),
    )


def _annotation_row_to_dict(row: BankAnnotationRow) -> dict[str, Any]:
    return {
        "frozen_ctx_id": row.frozen_ctx_id,
        "condition": row.condition,
        "mc_index": row.mc_index,
        "pre_bias_destination_zone": (
            row.pre_bias_destination_zone.value
            if row.pre_bias_destination_zone is not None
            else None
        ),
        "resolved_from": row.resolved_from,
    }


def _annotation_row_from_dict(data: dict[str, Any]) -> BankAnnotationRow:
    condition = data["condition"]
    if condition not in ("on", "off"):
        msg = f"invalid bank condition: {condition!r}"
        raise ValueError(msg)
    zone_value = data["pre_bias_destination_zone"]
    return BankAnnotationRow(
        frozen_ctx_id=data["frozen_ctx_id"],
        condition=cast("BankCondition", condition),
        mc_index=data["mc_index"],
        pre_bias_destination_zone=(
            Zone(zone_value) if zone_value is not None else None
        ),
        resolved_from=data["resolved_from"],
    )


def _records_to_jsonl(records: Sequence[BankLlmCallRecord]) -> str:
    return "".join(
        f"{handoff.canonical_dumps(_bank_record_to_dict(r))}\n" for r in records
    )


def _records_from_jsonl(text: str) -> tuple[BankLlmCallRecord, ...]:
    return tuple(
        _bank_record_from_dict(json.loads(line))
        for line in text.splitlines()
        if line.strip()
    )


def _annotation_to_jsonl(rows: Sequence[BankAnnotationRow]) -> str:
    return "".join(
        f"{handoff.canonical_dumps(_annotation_row_to_dict(r))}\n" for r in rows
    )


def _annotation_from_jsonl(text: str) -> tuple[BankAnnotationRow, ...]:
    return tuple(
        _annotation_row_from_dict(json.loads(line))
        for line in text.splitlines()
        if line.strip()
    )


def _bank_checksum(records: Sequence[BankLlmCallRecord]) -> str:
    """A sha256 integrity witness over the canonical-serialised record sequence.

    Mirrors ``loop.ecl_trace_checksum``'s shape (canonical-join-then-hash) but is
    computed here directly — this module never imports ``loop``'s checksum
    helper, which operates on ``EclTraceRow``, not :class:`BankLlmCallRecord`.
    An integrity/reproducibility witness over already-collected raw rows, never
    a statistic derived *from* the rows' content (§I4).
    """
    canonical = "\n".join(
        handoff.canonical_dumps(_bank_record_to_dict(r)) for r in records
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _frozen_contexts_from_records(
    records: Sequence[BankLlmCallRecord],
) -> tuple[FrozenContext, ...]:
    """Rebuild the K frozen contexts from the bank records alone (no chat call).

    Every :class:`BankLlmCallRecord` already carries its context's
    ``system_prompt`` / ``user_prompt`` / resolved ``sampling`` — the ``"on"``
    condition rows supply ``sampling_on``, the ``"off"`` rows supply
    ``sampling_off`` (§I3.3: the two conditions' prompts are byte-identical, so
    either supplies ``system_prompt``/``user_prompt``). This lets
    ``--verify`` re-drive :func:`run_bank_mloop` **without** re-running the
    provenance pass (and therefore without a single chat call) — the I5-G2
    "committed bank records のみ replay" contract.
    """
    by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        entry = by_id.setdefault(record.frozen_ctx_id, {})
        entry.setdefault("system_prompt", record.system_prompt)
        entry.setdefault("user_prompt", record.user_prompt)
        if record.condition == "on":
            entry["sampling_on"] = record.sampling
        else:
            entry["sampling_off"] = record.sampling
    contexts = [
        FrozenContext(
            frozen_ctx_id=ctx_id,
            system_prompt=entry["system_prompt"],
            user_prompt=entry["user_prompt"],
            sampling_on=entry["sampling_on"],
            sampling_off=entry["sampling_off"],
        )
        for ctx_id, entry in by_id.items()
    ]
    return tuple(sorted(contexts, key=lambda c: c.frozen_ctx_id))


# --------------------------------------------------------------------------- #
# manifest + rendering
# --------------------------------------------------------------------------- #


def _build_manifest(
    *,
    records: Sequence[BankLlmCallRecord],
    records_jsonl: str,
    annotation_jsonl: str,
    m_draws: int,
    k_contexts: int,
    seed: int,
    base_ts: datetime,
    context_ids: Sequence[str],
    env_pins: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "bank_golden_manifest_version": BANK_GOLDEN_MANIFEST_VERSION,
        "annotation_schema_version": BANK_ANNOTATION_SCHEMA_VERSION,
        "run": {
            "run_id": _DEFAULT_RUN_ID,
            "m_draws": m_draws,
            "k_contexts": k_contexts,
            "seed": seed,
            "base_ts": base_ts.isoformat(),
            "retrieval_now": base_ts.isoformat(),
            "context_ids": list(context_ids),
        },
        "env_pins": env_pins if env_pins is not None else handoff.capture_env_pins(),
        "artifacts": {
            "bank_records.jsonl": {"sha256": _sha256(records_jsonl)},
            "bank_annotation.jsonl": {"sha256": _sha256(annotation_jsonl)},
        },
        "bank_checksum": _bank_checksum(records),
        # Administrative call-count bookkeeping (mirrors handoff.build_manifest's
        # ``world_tick_count``/``cognition_ticks`` pattern) — a total row count,
        # never a per-zone aggregate (§I4).
        "call_cap": {"actual": len(records), "cap": 2 * m_draws * k_contexts},
    }
    return attach_bank_observables(manifest)


def render_bank_golden(
    *,
    records: Sequence[BankLlmCallRecord],
    annotation_rows: Sequence[BankAnnotationRow],
    m_draws: int,
    k_contexts: int,
    seed: int,
    base_ts: datetime,
    context_ids: Sequence[str],
    env_pins: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Render the three bank-golden artifacts as ``{filename: text}`` (pure)."""
    records_jsonl = _records_to_jsonl(records)
    annotation_jsonl = _annotation_to_jsonl(annotation_rows)
    manifest = _build_manifest(
        records=records,
        records_jsonl=records_jsonl,
        annotation_jsonl=annotation_jsonl,
        m_draws=m_draws,
        k_contexts=k_contexts,
        seed=seed,
        base_ts=base_ts,
        context_ids=context_ids,
        env_pins=env_pins,
    )
    return {
        "bank_records.jsonl": records_jsonl,
        "bank_annotation.jsonl": annotation_jsonl,
        "manifest.json": handoff.canonical_dumps(manifest) + "\n",
    }


def _write(out_dir: Path, rendered: dict[str, str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, text in rendered.items():
        (out_dir / filename).write_text(text, encoding="utf-8", newline="\n")


# --------------------------------------------------------------------------- #
# capture — mock construction verification run (I5-G4)
# --------------------------------------------------------------------------- #


async def _build_frozen_contexts(
    *, k: int, clock: datetime
) -> tuple[FrozenContext, ...]:
    """Build K frozen contexts via K independent mock provenance passes."""
    contexts: list[FrozenContext] = []
    for i in range(k):
        substrate = build_competing_cue_substrate(context_id=f"bank-golden-ctx-{i}")
        embedding = _mock_embedding()
        try:
            frozen = await run_provenance_pass(
                substrate=substrate,
                inner_chat=_ProvenanceMockChat(),
                store_factory=_store_factory,
                embedding=embedding,
                run_id=f"bank-golden-provenance-{i}",
                retrieval_now=clock,
                base_ts=clock,
                lambda_ctx=BANK_LAMBDA_CTX[0],
                seed=i,
            )
        finally:
            await embedding.close()
        contexts.append(frozen)
    return tuple(contexts)


async def capture(
    *,
    seed: int = 0,
    m_draws: int = BANK_M_GOLDEN,
    k_contexts: int = BANK_K_GOLDEN,
) -> dict[str, str]:
    """Drive one mock bank-golden construction run and render the artifacts.

    Ollama-free throughout (D-10): the provenance pass and the bake-out M-loop
    each get their own deterministic in-process mock chat client. Asserts the
    §I4 ``2·M·K`` call cap against the M-loop record-mode client's
    ``inner_invocations`` (fail-fast on overrun).
    """
    frozen_contexts = await _build_frozen_contexts(k=k_contexts, clock=_FIXED_CLOCK)
    context_ids = [ctx.frozen_ctx_id for ctx in frozen_contexts]

    llm_client = BankRecordReplayClient.for_record(_MloopMockChat())
    records = await _run_bank_mloop(
        llm=llm_client, frozen_contexts=frozen_contexts, m_draws=m_draws
    )

    cap = 2 * m_draws * k_contexts
    actual = llm_client.inner_invocations
    if actual > cap:
        msg = f"[bank-capture] M-loop call cap exceeded: {actual} > {cap} (§I4)"
        raise RuntimeError(msg)

    annotation_rows = tuple(
        BankAnnotationRow(
            frozen_ctx_id=record.frozen_ctx_id,
            condition=record.condition,
            mc_index=record.mc_index,
            pre_bias_destination_zone=record.pre_bias_destination_zone,
            resolved_from=_RESOLVED_FROM_TAG,
        )
        for record in records
    )

    return render_bank_golden(
        records=records,
        annotation_rows=annotation_rows,
        m_draws=m_draws,
        k_contexts=k_contexts,
        seed=seed,
        base_ts=_FIXED_CLOCK,
        context_ids=context_ids,
    )


# --------------------------------------------------------------------------- #
# verify — Ollama-free committed-bundle replay-verify (I5-G2/I5-G3)
# --------------------------------------------------------------------------- #


async def verify(artifact_dir: Path) -> bool:
    """Ollama-free replay-verify of a committed bank-golden artifact bundle.

    Rebuilds the K frozen contexts from the committed bank records alone (no
    provenance pass, no chat call), re-drives :func:`run_bank_mloop` through a
    **replay**-mode :class:`BankRecordReplayClient`, and asserts
    ``inner_invocations == 0`` plus byte-identical re-renders of every artifact
    (committed ``env_pins``/``run`` block reused, never a fresh snapshot).
    """
    manifest_text = (artifact_dir / "manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    records_text = (artifact_dir / "bank_records.jsonl").read_text(encoding="utf-8")
    annotation_text = (artifact_dir / "bank_annotation.jsonl").read_text(
        encoding="utf-8"
    )

    committed_records = _records_from_jsonl(records_text)
    committed_annotation = _annotation_from_jsonl(annotation_text)
    frozen_contexts = _frozen_contexts_from_records(committed_records)

    run_config = manifest["run"]
    m_draws = int(run_config["m_draws"])
    k_contexts = int(run_config["k_contexts"])

    ok = True
    replay_client = BankRecordReplayClient.for_replay(committed_records)
    replayed = await _run_bank_mloop(
        llm=replay_client, frozen_contexts=frozen_contexts, m_draws=m_draws
    )

    if replay_client.inner_invocations != 0:
        ok = False
        print(
            f"[verify] FAIL replay touched a live LLM "
            f"({replay_client.inner_invocations} calls)"
        )
    replayed_jsonl = _records_to_jsonl(replayed)
    if replayed_jsonl != records_text:
        ok = False
        print("[verify] FAIL bank_records.jsonl byte mismatch on replay")
    else:
        print(f"[verify] OK bank_checksum {_bank_checksum(replayed)}")

    rendered = render_bank_golden(
        records=replayed,
        annotation_rows=committed_annotation,
        m_draws=m_draws,
        k_contexts=k_contexts,
        seed=int(run_config["seed"]),
        base_ts=datetime.fromisoformat(run_config["base_ts"]),
        context_ids=list(run_config["context_ids"]),
        env_pins=manifest["env_pins"],
    )

    for name, committed_text in (
        ("bank_records.jsonl", records_text),
        ("bank_annotation.jsonl", annotation_text),
    ):
        expected_sha = manifest["artifacts"][name]["sha256"]
        actual_sha = _sha256(rendered[name])
        if actual_sha != expected_sha:
            ok = False
            print(f"[verify] FAIL {name} sha256 {actual_sha} != {expected_sha}")
        elif rendered[name] != committed_text:  # pragma: no cover - defensive
            ok = False
            print(f"[verify] FAIL {name} byte mismatch despite matching sha256")
        else:
            print(f"[verify] OK {name} byte-identical")

    if rendered["manifest.json"] != manifest_text:
        ok = False
        print("[verify] FAIL manifest.json byte mismatch on re-render")
    else:
        print("[verify] OK manifest.json byte-identical re-render")

    print("[verify] BANK GOLDEN OK" if ok else "[verify] BANK GOLDEN MISMATCH")
    return ok


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="ECL B bank golden capture/verify (mock-only)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--capture",
        action="store_true",
        help="drive one mock bank construction run and write the golden artifacts",
    )
    group.add_argument(
        "--verify",
        action="store_true",
        help="Ollama-free replay-verify a committed bank-golden artifact bundle",
    )
    parser.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT_DIR)
    parser.add_argument("--artifact-dir", type=Path, default=_DEFAULT_OUT_DIR)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--m-draws", type=int, default=BANK_M_GOLDEN)
    parser.add_argument("--k-contexts", type=int, default=BANK_K_GOLDEN)
    args = parser.parse_args(argv)

    if args.verify:
        ok = asyncio.run(verify(args.artifact_dir))
        return 0 if ok else 1

    rendered = asyncio.run(
        capture(seed=args.seed, m_draws=args.m_draws, k_contexts=args.k_contexts)
    )
    _write(args.out_dir, rendered)
    print(f"[capture] wrote {len(rendered)} artifacts to {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
