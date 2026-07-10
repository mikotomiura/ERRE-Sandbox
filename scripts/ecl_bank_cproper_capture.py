#!/usr/bin/env python
"""M13 C-proper — powered bank sealed-run capture/verify CLI (real qwen3:8b).

This is the **measurement spend** apparatus that C-design #2
(``AUTHORIZE_C_PROPER``) authorised: it drives the FROZEN B bank apparatus
(``run_provenance_pass`` + ``run_bank_mloop``) with a **live** qwen3:8b at powered
scale (``M=300 × K=8``, ``think=False``) and writes the raw-row annotation, the
bank-records replay fixture, and a manifest — then, under ``--verify``, replays
the committed bundle Ollama-free (``inner_invocations == 0``, byte-identical
re-render) and applies the frozen C-proper scorer to emit ``verdict.json``.

Distinct from ``scripts/ecl_bank_capture.py`` (the **mock-only, D-10 FROZEN**
golden construction CLI, unmodified read-only). The design split (``design-final``
§B/§S0): the **provenance pass stays a deterministic mock** — the frozen context's
``(system_prompt, user_prompt, sampling_on/off)`` render deterministically from the
substrate and never read the provenance LLM's content
(``ecl_bank_capture.py`` §_PROVENANCE_PLAN_JSON) — so the **only** real spend is the
M-loop's measured draws. This keeps the K frozen contexts reproducible while the
M draws are the actual measurement.

The B apparatus (``bank.py`` / ``bank_fixtures.py`` / ``bank_power.py``) and the
mock CLI are imported/read only, never modified. Every artifact is serialised
through ``handoff.canonical_dumps`` (6-decimal float quantisation, the
cross-platform ``libm``-drift absorber) so a Windows bake and a WSL replay hash
byte-identically (``feedback_golden_crossplatform_float_drift``).
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

from erre_sandbox.inference.ollama_adapter import ChatResponse, OllamaChatClient
from erre_sandbox.inference.sampling import ResolvedSampling
from erre_sandbox.integration.embodied import handoff
from erre_sandbox.integration.embodied.bank import (
    BANK_ANNOTATION_SCHEMA_VERSION,
    BankAnnotationRow,
    BankLlmCallRecord,
    BankRecordReplayClient,
    attach_bank_observables,
    run_bank_mloop,
)
from erre_sandbox.integration.embodied.bank_fixtures import (
    BANK_LAMBDA_CTX,
    FrozenContext,
    build_competing_cue_substrate,
    run_provenance_pass,
)
from erre_sandbox.integration.embodied.bank_power import K_MIN, M_MIN
from erre_sandbox.integration.embodied.bank_scorer import (
    score_bank_annotation,
    verdict_to_dict,
)
from erre_sandbox.memory import EmbeddingClient, MemoryStore
from erre_sandbox.schemas import Zone

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.inference.ollama_adapter import ChatMessage
    from erre_sandbox.integration.embodied.bank import BankCondition

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUT_DIR = _REPO_ROOT / "experiments" / "20260710-m13-c-proper" / "artifacts"
_DEFAULT_RUN_ID = "ecl-cproper"
_FIXED_CLOCK: Final[datetime] = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
_LIVE_MODEL: Final[str] = "qwen3:8b"

CPROPER_MANIFEST_VERSION: Final[str] = "ecl-cproper-1"
_RESOLVED_FROM_TAG: Final[str] = "pre_bias_direct_parse"

# Deterministic provenance-pass content — the destination it parses to is never
# read downstream (§S0), so a fixed value keeps the provenance record
# deterministic without attaching meaning.
_PROVENANCE_PLAN_JSON: Final[str] = json.dumps(
    {
        "thought": "which zone calls to me?",
        "utterance": "bank provenance pass",
        "destination_zone": Zone.STUDY.value,
        "animation": "walk",
    }
)


# --------------------------------------------------------------------------- #
# Provenance mock (Ollama-free — only the M-loop spends)
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


def _store_factory() -> MemoryStore:
    return MemoryStore(db_path=":memory:")


@dataclass
class _ProvenanceMockChat:
    content: str = _PROVENANCE_PLAN_JSON
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
        self.calls += 1
        return ChatResponse(
            content=self.content,
            model="bank-provenance-mock",
            eval_count=1,
            total_duration_ms=0.0,
        )


# --------------------------------------------------------------------------- #
# Serialisation (self-contained, mirrors ecl_bank_capture's own serialisers)
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


def _annotation_dicts_from_jsonl(text: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _bank_checksum(records: Sequence[BankLlmCallRecord]) -> str:
    canonical = "\n".join(
        handoff.canonical_dumps(_bank_record_to_dict(r)) for r in records
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _row_keys(
    items: Sequence[BankLlmCallRecord] | Sequence[BankAnnotationRow],
) -> list[tuple[str, str, int]]:
    return [(i.frozen_ctx_id, i.condition, i.mc_index) for i in items]


def _frozen_contexts_from_records(
    records: Sequence[BankLlmCallRecord],
) -> tuple[FrozenContext, ...]:
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
    env_pins: dict[str, Any],
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "cproper_manifest_version": CPROPER_MANIFEST_VERSION,
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
        "env_pins": env_pins,
        "artifacts": {
            "bank_records.jsonl": {"sha256": _sha256(records_jsonl)},
            "bank_annotation.jsonl": {"sha256": _sha256(annotation_jsonl)},
        },
        "bank_checksum": _bank_checksum(records),
        "call_cap": {"actual": len(records), "cap": 2 * m_draws * k_contexts},
        # Cost ceiling (arc §4.2 item 3): the powered spend is bounded a priori at
        # 2·M·K real qwen3 draws; overrun is a fail-fast, never a silent top-up.
        "cost_ceiling": {
            "max_llm_calls": 2 * m_draws * k_contexts,
            "model": _LIVE_MODEL,
        },
    }
    return attach_bank_observables(manifest)


def _render(
    *,
    records: Sequence[BankLlmCallRecord],
    annotation_rows: Sequence[BankAnnotationRow],
    m_draws: int,
    k_contexts: int,
    seed: int,
    base_ts: datetime,
    context_ids: Sequence[str],
    env_pins: dict[str, Any],
) -> dict[str, str]:
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


def _env_pins(
    *, qwen3_model_digest: str, ollama_version: str, vram_gb: float, uv_lock_sha256: str
) -> dict[str, Any]:
    """Manifest env pins — think=False is load-bearing (H3) and pinned explicitly."""
    pins = handoff.capture_env_pins()
    pins.update(
        {
            "model": _LIVE_MODEL,
            "think": False,
            "qwen3_model_digest": qwen3_model_digest,
            "ollama_version": ollama_version,
            "vram_gb": vram_gb,
            "uv_lock_sha256": uv_lock_sha256,
        }
    )
    return pins


# --------------------------------------------------------------------------- #
# capture — powered live sealed run (the R-budget=1 spend)
# --------------------------------------------------------------------------- #


async def _build_frozen_contexts(*, k: int) -> tuple[FrozenContext, ...]:
    contexts: list[FrozenContext] = []
    for i in range(k):
        substrate = build_competing_cue_substrate(context_id=f"cproper-ctx-{i}")
        embedding = _mock_embedding()
        try:
            frozen = await run_provenance_pass(
                substrate=substrate,
                inner_chat=_ProvenanceMockChat(),
                store_factory=_store_factory,
                embedding=embedding,
                run_id=f"cproper-provenance-{i}",
                retrieval_now=_FIXED_CLOCK,
                base_ts=_FIXED_CLOCK,
                lambda_ctx=BANK_LAMBDA_CTX[0],
                seed=i,
            )
        finally:
            await embedding.close()
        contexts.append(frozen)
    return tuple(contexts)


async def capture(
    *,
    seed: int,
    m_draws: int,
    k_contexts: int,
    qwen3_model_digest: str,
    ollama_version: str,
    vram_gb: float,
    uv_lock_sha256: str,
    inner_chat: Any | None = None,
) -> dict[str, str]:
    """Drive one powered live bank sealed run (provenance mock, M-loop live qwen3).

    ``inner_chat`` is the M-loop chat client. It defaults to a real
    :class:`OllamaChatClient` (the sole live piece; ``--capture`` uses this). Tests
    and Ollama-free dry-runs inject a deterministic mock — the seam never changes
    the live path.
    """
    frozen_contexts = await _build_frozen_contexts(k=k_contexts)
    context_ids = [ctx.frozen_ctx_id for ctx in frozen_contexts]

    inner = (
        inner_chat if inner_chat is not None else OllamaChatClient(model=_LIVE_MODEL)
    )
    llm_client = BankRecordReplayClient.for_record(inner)
    try:
        records = await run_bank_mloop(
            llm=llm_client, frozen_contexts=frozen_contexts, m_draws=m_draws
        )
    finally:
        close = getattr(inner, "close", None)
        if callable(close):
            await close()

    cap = 2 * m_draws * k_contexts
    actual = llm_client.inner_invocations
    if actual > cap:
        msg = f"[cproper-capture] M-loop call cap exceeded: {actual} > {cap} (cost ceiling)"
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

    env_pins = _env_pins(
        qwen3_model_digest=qwen3_model_digest,
        ollama_version=ollama_version,
        vram_gb=vram_gb,
        uv_lock_sha256=uv_lock_sha256,
    )
    return _render(
        records=records,
        annotation_rows=annotation_rows,
        m_draws=m_draws,
        k_contexts=k_contexts,
        seed=seed,
        base_ts=_FIXED_CLOCK,
        context_ids=context_ids,
        env_pins=env_pins,
    )


# --------------------------------------------------------------------------- #
# verify — Ollama-free replay-verify + frozen scorer → verdict.json
# --------------------------------------------------------------------------- #


async def verify(artifact_dir: Path) -> bool:
    """Replay-verify the committed bundle (Ollama-free) then apply the scorer."""
    manifest_text = (artifact_dir / "manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    records_text = (artifact_dir / "bank_records.jsonl").read_text(encoding="utf-8")
    annotation_text = (artifact_dir / "bank_annotation.jsonl").read_text(
        encoding="utf-8"
    )

    committed_records = _records_from_jsonl(records_text)
    frozen_contexts = _frozen_contexts_from_records(committed_records)
    run_config = manifest["run"]
    m_draws = int(run_config["m_draws"])

    ok = True
    replay_client = BankRecordReplayClient.for_replay(committed_records)
    replayed = await run_bank_mloop(
        llm=replay_client, frozen_contexts=frozen_contexts, m_draws=m_draws
    )
    if replay_client.inner_invocations != 0:
        ok = False
        print(
            f"[verify] FAIL replay touched a live LLM ({replay_client.inner_invocations})"
        )
    replayed_jsonl = _records_to_jsonl(replayed)
    if replayed_jsonl != records_text:
        ok = False
        print("[verify] FAIL bank_records.jsonl byte mismatch on replay")
    else:
        print(f"[verify] OK bank_checksum {_bank_checksum(replayed)}")

    annotation_dicts = _annotation_dicts_from_jsonl(annotation_text)
    # row-by-row key alignment between records and annotation (never an aggregate)
    committed_annotation_keys = [
        (str(d["frozen_ctx_id"]), str(d["condition"]), int(d["mc_index"]))
        for d in annotation_dicts
    ]
    if _row_keys(committed_records) != committed_annotation_keys:
        ok = False
        print("[verify] FAIL records / annotation row-by-row key misalignment")
    else:
        print("[verify] OK records / annotation row-by-row key alignment")

    # frozen scorer application (§CB4.4 verdict) — one-shot, forking-paths seal.
    verdict = score_bank_annotation(annotation_rows=annotation_dicts, manifest=manifest)
    verdict_dict = verdict_to_dict(verdict)
    verdict_text = handoff.canonical_dumps(verdict_dict) + "\n"
    (artifact_dir / "verdict.json").write_text(
        verdict_text, encoding="utf-8", newline="\n"
    )
    print(f"[verify] VERDICT {verdict.verdict}")
    print(f"[verify] reason: {'; '.join(verdict.reason)}")

    print("[verify] CPROPER OK" if ok else "[verify] CPROPER MISMATCH")
    return ok


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="M13 C-proper powered bank sealed-run capture/verify (live qwen3:8b)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--capture", action="store_true", help="powered live sealed run")
    group.add_argument(
        "--verify", action="store_true", help="Ollama-free replay + scorer"
    )
    parser.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT_DIR)
    parser.add_argument("--artifact-dir", type=Path, default=_DEFAULT_OUT_DIR)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--m-draws", type=int, default=M_MIN)
    parser.add_argument("--k-contexts", type=int, default=K_MIN)
    parser.add_argument("--qwen3-model-digest", default="unknown")
    parser.add_argument("--ollama-version", default="unknown")
    parser.add_argument("--vram-gb", type=float, default=0.0)
    parser.add_argument("--uv-lock-sha256", default="unknown")
    args = parser.parse_args(argv)

    if args.verify:
        ok = asyncio.run(verify(args.artifact_dir))
        return 0 if ok else 1

    rendered = asyncio.run(
        capture(
            seed=args.seed,
            m_draws=args.m_draws,
            k_contexts=args.k_contexts,
            qwen3_model_digest=args.qwen3_model_digest,
            ollama_version=args.ollama_version,
            vram_gb=args.vram_gb,
            uv_lock_sha256=args.uv_lock_sha256,
        )
    )
    _write(args.out_dir, rendered)
    print(f"[capture] wrote {len(rendered)} artifacts to {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
