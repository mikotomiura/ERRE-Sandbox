"""aha!/DMN-ECN Phase 3 — think=True reasoning-trace capture apparatus (additive).

Implements the Phase 2 *二相捕捉 regime* (`.steering/20260713-aha-phase2-door-scoping/
design-final.md` §(b)) as an **additive, construction-only** apparatus. It replays the
committed ECL v0 organ prompts (kant, N=32, deterministic ``think=False`` provenance)
against a real ``qwen3:8b`` with **``think=True``** and raw-records the reasoning trace
so a human can descriptively observe whether a generation↔evaluation two-phase structure
*exists* — an **existence observation, never a verdict**.

Why a separate path (design-final §Decision / Codex M2): the frozen
:class:`~erre_sandbox.inference.ollama_adapter.ChatResponse` is ``extra="forbid"`` +
``frozen=True`` and extracts only ``message.content`` — it has **no field for**
``message.thinking``. Routing ``think=True`` through the organ chat path would silently
drop the trace; widening ``ChatResponse`` would modify the frozen organ. So this module
owns a **design-copied** minimal ``/api/chat`` client (:class:`ThinkTraceClient`)
that is *not* imported from ``ollama_adapter`` (the same "design-copy, not import" idiom
``loop.py`` uses for ``trace_checksum``). ``handoff`` is imported read-only for
``recorded_calls_from_jsonl`` / ``canonical_dumps`` / ``capture_env_pins``.

Determinism (design-final §決定性 / §(b) principle 3, Codex H2): ``think=True`` is
non-deterministic, so this apparatus emits **no ``replay_checksum``** and performs **no
byte-parity verification**. The deterministic layer is the *prompt provenance* (the
committed ECL v0 ``decisions.jsonl``, pinned by its source manifest checksum + JSONL
sha256); the non-determinism is confined to the raw trace content.

Scope guard (design-final §Guard, binding, mirrors ``loop.py`` / ``live.py``): this is a
**construction** apparatus, **NOT a measurement line — verdict は holding**. It imports
no ``evidence`` / ``spdm`` / ``runningness`` machinery and computes/emits **no** floor /
landscape / verdict / score / divergence / aha-proxy / pass-fail statistic. The only
counts it emits are the **mechanical technical tallies** (``thinking_parseable`` /
``finish_length`` / ``total``) that answer the §(b) technical-verification question "did
``think=True`` yield parseable traces at all" — never a gate (Codex H4).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Literal, Self, TypeGuard

import httpx

from erre_sandbox.integration.embodied import handoff

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.inference.sampling import ResolvedSampling
    from erre_sandbox.integration.embodied.loop import RecordedLlmCall

# --------------------------------------------------------------------------- #
# Pre-registered protocol constants (design-final §Decision, sealed-run-before)
# --------------------------------------------------------------------------- #

PHASE3_N_PROMPTS: Final[int] = 32
"""Prompt count sourced from the committed ECL v0 run (kant, N=32 cognition ticks).

The provenance layer is fixed before the sealed run; a mismatch is a preflight Stop
(:func:`validate_prompt_provenance`), never tuned to pass."""

PHASE3_PERSONA: Final[str] = "kant"
"""Sole persona (grill 判断1): the ECL v0 golden's single agent."""

PHASE3_PERSONA_DISPLAY: Final[str] = "Immanuel Kant"
"""Display name the source system prompts must contain (preflight persona check, H3)."""

PHASE3_SOURCE_ARTIFACT: Final[str] = (
    "experiments/20260706-ecl-v0-live-capture/artifacts"
)
"""Committed ECL v0 bundle = the deterministic prompt provenance (design-v2)."""

PHASE3_THINK: Final[bool] = True
"""This regime is the ``think=True`` door side (Phase 2 §(a)). Fixed, not a knob."""

PHASE3_THINK_NUM_PREDICT: Final[int] = 2048
"""Response-token budget for the ``think=True`` capture calls.

``think`` consumes the budget (memory ``reference_qwen3_ollama_gotchas``), so this is
set generously to reduce truncation dominating the observation (Codex L1).
``finish_reason == 'length'`` occurrences are recorded as a **mechanical** count (not a
gate); if truncation is pervasive, a *separate* run with a larger budget is the
follow-up, never a silent bump.
"""

PHASE3_REQUESTED_SEED_METADATA: Final[int] = 0
"""Recorded as *metadata only* (Codex M3 / TASK-POST LOW-1): **not sent to Ollama
options**; ``think=True`` is non-deterministic, so this is **not a reproducibility
guarantee** — documents the requested seed for the record only."""

MANIFEST_SCHEMA: Final[str] = "aha-phase3-think-capture/v1"
CAPTURE_KIND: Final[str] = "prompt-replay think=True capture, not live-loop execution"
"""Narrows the claim (Codex M1): the observed traces are ``think=True`` responses to
embodied-organ-*derived* prompts, **not** live-loop embodied behaviour."""

NONDETERMINISM_NOTE: Final[str] = (
    "think=True traces are raw-recorded, NOT byte-verified; this manifest carries no "
    "Phase 3 replay_checksum by design (二相捕捉 regime §(b) principle 3). "
    "prompt_provenance.source_manifest_checksum is the ECL v0 prompt-source checksum, "
    "NOT a Phase 3 trace replay guarantee."
)
"""Codex H2: make the absence of a Phase 3 ``replay_checksum`` explicit and disambiguate
the source checksum so nothing reads as a trace-reproduction guarantee."""

RECONSIDERATION_MARKERS: Final[tuple[str, ...]] = (
    "wait",
    "actually",
    "hmm",
    "let me reconsider",
    "on second thought",
    "hold on",
    "but wait",
    "no, ",
    "rather,",
    "reconsider",
)
"""Substrings whose occurrences :func:`surface_reconsideration_markers` returns as
*illustrative excerpts* (§(b) principle 4 (ii): 出現有無 + 例示). Raw material
for the human memo — **never** a count/rate/score/threshold/aha-proxy (Codex H4)."""


class ThinkCaptureTransportError(RuntimeError):
    """Ollama ``/api/chat`` was unreachable / errored / malformed during capture.

    Distinct from an *empty / unparseable thinking* outcome (which is a valid recorded
    trace, exit 0 + observation note): a transport failure is a nonzero-exit partial
    diagnostic (Codex H5). ``ThinkTraceClient`` raises this; :func:`run_think_capture`
    wraps it in :class:`ThinkCapturePartialError` carrying the records captured so far.
    """


class ThinkCapturePartialError(RuntimeError):
    """A transport failure interrupted the run; carries partial records (Codex H5)."""

    def __init__(
        self, records: tuple[ThinkCaptureRecord, ...], index: int, cause: Exception
    ) -> None:
        super().__init__(
            f"think=True capture failed at prompt index {index}/"
            f"{len(records)} captured: {cause!r}"
        )
        self.records = records
        self.index = index
        self.cause = cause


class ProvenanceError(RuntimeError):
    """The committed prompt provenance failed preflight validation (Codex H3).

    A structural Stop *before* any live call — the "we observed the real organ prompts"
    claim would be false if N / persona / fields / source integrity are wrong.
    """


# --------------------------------------------------------------------------- #
# Raw wire response + thinking extraction (design-copied from ollama_adapter, M2)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class RawThinkResponse:
    """The raw ``/api/chat`` message surface :class:`ThinkTraceClient` returns.

    Deliberately *not* an ``ollama_adapter.ChatResponse`` (which drops
    ``message.thinking``): carries the whole ``message`` dict plus the top-level fields
    the trace needs. ``finish_reason`` is the normalised name (``done_reason`` is the
    raw Ollama key, Codex H1).
    """

    raw_message: dict[str, Any]
    content: str
    eval_count: int
    done_reason: str
    finish_reason: Literal["stop", "length"]


@dataclass(frozen=True, slots=True)
class ThinkingExtraction:
    """Result of :func:`extract_thinking` — mechanical facts only, never a gate (M4)."""

    thinking: str
    source: Literal["field", "embedded", "none"]
    key_present: bool
    char_count: int
    embedded_parse_status: Literal["n/a", "ok", "failed"]
    parseable: bool


_THINK_OPEN: Final[str] = "<think>"
_THINK_CLOSE: Final[str] = "</think>"


def _extract_embedded_think(
    content: str,
) -> tuple[str | None, Literal["n/a", "ok", "failed"]]:
    """Extract a ``<think>...</think>`` block embedded in ``content`` (old-Ollama path).

    Returns ``(text, "ok")`` for a well-formed block, ``(None, "failed")`` when an
    opening ``<think>`` has no matching close, and ``(None, "n/a")`` when there is none.
    """
    open_i = content.find(_THINK_OPEN)
    if open_i < 0:
        return None, "n/a"
    close_i = content.find(_THINK_CLOSE, open_i + len(_THINK_OPEN))
    if close_i < 0:
        return None, "failed"
    return content[open_i + len(_THINK_OPEN) : close_i].strip(), "ok"


def extract_thinking(raw_message: dict[str, Any], content: str) -> ThinkingExtraction:
    """Extract the trace, preferring ``message.thinking`` then embedded ``<think>``.

    Distinguishes (Codex M4) *field present & non-empty* / *field absent* / *field
    present but empty* / *embedded parse failure* via ``source`` + ``key_present`` +
    ``embedded_parse_status``. ``parseable`` is a **mechanical** boolean (a thinking
    segment was extractable), **not** a quality judgement — it feeds the §(b)
    technical-verification tally, never a gate.
    """
    key_present = "thinking" in raw_message
    field_val = raw_message.get("thinking")
    if isinstance(field_val, str) and field_val.strip():
        text = field_val.strip()
        return ThinkingExtraction(
            thinking=text,
            source="field",
            key_present=True,
            char_count=len(text),
            embedded_parse_status="n/a",
            parseable=True,
        )
    embedded, status = _extract_embedded_think(content)
    if embedded is not None:
        return ThinkingExtraction(
            thinking=embedded,
            source="embedded",
            key_present=key_present,
            char_count=len(embedded),
            embedded_parse_status="ok",
            parseable=True,
        )
    return ThinkingExtraction(
        thinking="",
        source="none",
        key_present=key_present,
        char_count=0,
        embedded_parse_status=status,
        parseable=False,
    )


# --------------------------------------------------------------------------- #
# ThinkTraceClient — additive think=True /api/chat client (organ untouched)
# --------------------------------------------------------------------------- #


class ThinkTraceClient:
    """Minimal ``/api/chat`` client that issues ``think=True`` and returns raw message.

    Design-copied from
    :class:`~erre_sandbox.inference.ollama_adapter.OllamaChatClient`'s wire logic (Codex
    M2 — *not* imported, because ``ChatResponse`` cannot carry ``message.thinking``).
    Request body is fixed to ``{model, messages, stream:false, think:true, options:{
    temperature, top_p, repeat_penalty, num_predict}}`` (Codex H1); the response is
    parsed from the top-level ``message`` / ``eval_count`` / ``done_reason``. Takes an
    optional client so tests can inject a mock transport (Ollama-free).
    """

    DEFAULT_ENDPOINT: Final[str] = "http://127.0.0.1:11434"
    DEFAULT_TIMEOUT_SECONDS: Final[float] = 180.0
    CHAT_PATH: Final[str] = "/api/chat"

    def __init__(
        self,
        *,
        model: str,
        endpoint: str | None = None,
        timeout: float | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        self.endpoint = (endpoint or self.DEFAULT_ENDPOINT).rstrip("/")
        self._timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT_SECONDS
        self._client: httpx.AsyncClient = client or httpx.AsyncClient(
            base_url=self.endpoint, timeout=self._timeout
        )
        self._owns_client = client is None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_client and not self._client.is_closed:
            await self._client.aclose()

    def _build_body(
        self,
        system_prompt: str,
        user_prompt: str,
        sampling: ResolvedSampling,
        num_predict: int,
        model: str | None,
    ) -> dict[str, Any]:
        return {
            "model": model or self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "think": True,
            "options": {
                "temperature": sampling.temperature,
                "top_p": sampling.top_p,
                "repeat_penalty": sampling.repeat_penalty,
                "num_predict": num_predict,
            },
        }

    async def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.post(self.CHAT_PATH, json=body)
        except httpx.HTTPError as exc:
            raise ThinkCaptureTransportError(
                f"Ollama {self.CHAT_PATH} unreachable at {self.endpoint}: {exc!r}"
            ) from exc
        if response.status_code != httpx.codes.OK:
            raise ThinkCaptureTransportError(
                f"Ollama {self.CHAT_PATH} returned HTTP {response.status_code}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ThinkCaptureTransportError(
                f"Ollama {self.CHAT_PATH} returned non-JSON payload: {exc!r}"
            ) from exc
        if not isinstance(payload, dict):
            raise ThinkCaptureTransportError(
                f"Ollama {self.CHAT_PATH} returned non-object JSON: {payload!r}"
            )
        return payload

    @staticmethod
    def _parse(payload: dict[str, Any]) -> RawThinkResponse:
        message = payload.get("message")
        if not isinstance(message, dict):
            raise ThinkCaptureTransportError(
                "Ollama /api/chat payload missing 'message' "
                f"(top-level keys: {sorted(payload.keys())})"
            )
        # Normalise every top-level conversion to ThinkCaptureTransportError so a
        # malformed payload (e.g. non-int eval_count) stays inside the transport-failure
        # partial-diagnostic contract instead of escaping run_think_capture (Codex
        # TASK-POST MEDIUM-2).
        try:
            eval_count = int(payload.get("eval_count", 0))
        except (TypeError, ValueError) as exc:
            raise ThinkCaptureTransportError(
                f"Ollama /api/chat eval_count not an int: {payload.get('eval_count')!r}"
            ) from exc
        done_reason = str(payload.get("done_reason", "stop"))
        finish_reason: Literal["stop", "length"] = (
            "length" if done_reason == "length" else "stop"
        )
        return RawThinkResponse(
            raw_message=message,
            content=str(message.get("content", "")),
            eval_count=eval_count,
            done_reason=done_reason,
            finish_reason=finish_reason,
        )

    async def capture(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        sampling: ResolvedSampling,
        num_predict: int,
        model: str | None = None,
    ) -> RawThinkResponse:
        """Issue one ``think=True`` chat call and return the raw message surface."""
        body = self._build_body(
            system_prompt, user_prompt, sampling, num_predict, model
        )
        payload = await self._post(body)
        return self._parse(payload)


# --------------------------------------------------------------------------- #
# Per-prompt capture record (raw + mechanical technical facts, no verdict)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ThinkCaptureRecord:
    """One prompt's ``think=True`` capture — raw trace + provenance + mechanical facts.

    Carries **no** score / verdict / floor / pass-fail / aha-proxy field (design-final
    §Guard, Codex H4); ``thinking_parseable`` and the counts are mechanical technical
    facts for the §(b) technical verification, not gates.
    """

    source_index: int
    system_prompt_sha256: str
    user_prompt_sha256: str
    source_call_sha256: str
    source_sampling: dict[str, Any]
    capture_sampling: dict[str, Any]
    thinking: str
    content: str
    thinking_present: bool
    thinking_key_present: bool
    thinking_char_count: int
    thinking_source: Literal["field", "embedded", "none"]
    embedded_parse_status: Literal["n/a", "ok", "failed"]
    thinking_parseable: bool
    raw_message_keys: tuple[str, ...]
    eval_count: int
    finish_reason: Literal["stop", "length"]
    done_reason: str

    def to_dict(self) -> dict[str, Any]:
        """A canonical-serialisable projection (list, not tuple, for JSON)."""
        return {
            "source_index": self.source_index,
            "system_prompt_sha256": self.system_prompt_sha256,
            "user_prompt_sha256": self.user_prompt_sha256,
            "source_call_sha256": self.source_call_sha256,
            "source_sampling": self.source_sampling,
            "capture_sampling": self.capture_sampling,
            "thinking": self.thinking,
            "content": self.content,
            "thinking_present": self.thinking_present,
            "thinking_key_present": self.thinking_key_present,
            "thinking_char_count": self.thinking_char_count,
            "thinking_source": self.thinking_source,
            "embedded_parse_status": self.embedded_parse_status,
            "thinking_parseable": self.thinking_parseable,
            "raw_message_keys": list(self.raw_message_keys),
            "eval_count": self.eval_count,
            "finish_reason": self.finish_reason,
            "done_reason": self.done_reason,
        }


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_sha256_hex(value: object) -> TypeGuard[str]:
    """True iff ``value`` is a 64-char lowercase-hex string (a SHA-256 digest)."""
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))


def _source_call_fingerprint(call: RecordedLlmCall) -> str:
    """Stable hash of a source call's prompt+sampling (provenance linkage, Codex H3)."""
    projection = {
        "system_prompt": call.system_prompt,
        "user_prompt": call.user_prompt,
        "sampling": call.sampling.model_dump(mode="json"),
    }
    return _sha256(handoff.canonical_dumps(projection))


def _record_from_capture(
    *, source_index: int, call: RecordedLlmCall, raw: RawThinkResponse, num_predict: int
) -> ThinkCaptureRecord:
    extraction = extract_thinking(raw.raw_message, raw.content)
    return ThinkCaptureRecord(
        source_index=source_index,
        system_prompt_sha256=_sha256(call.system_prompt),
        user_prompt_sha256=_sha256(call.user_prompt),
        source_call_sha256=_source_call_fingerprint(call),
        source_sampling=call.sampling.model_dump(mode="json"),
        capture_sampling={
            "think": PHASE3_THINK,
            "num_predict": num_predict,
            "requested_seed_metadata": PHASE3_REQUESTED_SEED_METADATA,
            "temperature": call.sampling.temperature,
            "top_p": call.sampling.top_p,
            "repeat_penalty": call.sampling.repeat_penalty,
        },
        thinking=extraction.thinking,
        content=raw.content,
        thinking_present=extraction.source != "none",
        thinking_key_present=extraction.key_present,
        thinking_char_count=extraction.char_count,
        thinking_source=extraction.source,
        embedded_parse_status=extraction.embedded_parse_status,
        thinking_parseable=extraction.parseable,
        raw_message_keys=tuple(sorted(raw.raw_message.keys())),
        eval_count=raw.eval_count,
        finish_reason=raw.finish_reason,
        done_reason=raw.done_reason,
    )


async def run_think_capture(
    *,
    prompts: Sequence[RecordedLlmCall],
    client: ThinkTraceClient,
    num_predict: int = PHASE3_THINK_NUM_PREDICT,
) -> tuple[ThinkCaptureRecord, ...]:
    """Issue ``think=True`` for each committed prompt and collect the raw traces.

    A flat loop, pure with respect to the injected ``client`` (real
    :class:`ThinkTraceClient` for the sealed run, a ``MockTransport``-backed one in
    tests). An *empty / unparseable* thinking outcome is a valid recorded trace (the run
    continues, exit 0 + note). A **transport failure** (Codex H5) aborts and is
    re-raised as :class:`ThinkCapturePartialError` carrying the records captured so far
    so the CLI can write a partial diagnostic and exit nonzero.
    """
    records: list[ThinkCaptureRecord] = []
    for idx, call in enumerate(prompts):
        try:
            raw = await client.capture(
                system_prompt=call.system_prompt,
                user_prompt=call.user_prompt,
                sampling=call.sampling,
                num_predict=num_predict,
            )
        except ThinkCaptureTransportError as exc:
            raise ThinkCapturePartialError(tuple(records), idx, exc) from exc
        records.append(
            _record_from_capture(
                source_index=idx, call=call, raw=raw, num_predict=num_predict
            )
        )
    return tuple(records)


# --------------------------------------------------------------------------- #
# Prompt provenance preflight (Codex H3) + descriptive observation (Codex H4)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class PromptProvenance:
    """Validated committed-prompt provenance (design-v2 deterministic layer)."""

    calls: tuple[RecordedLlmCall, ...]
    source_artifact: str
    source_manifest_checksum: str
    source_decisions_sha256: str
    n_source_calls: int
    persona: str = PHASE3_PERSONA

    def block(self) -> dict[str, Any]:
        """The ``prompt_provenance`` block (Codex H2/H3 — source, not trace)."""
        return {
            "source_artifact": self.source_artifact,
            "source_manifest_checksum": self.source_manifest_checksum,
            "source_decisions_sha256": self.source_decisions_sha256,
            "n_source_calls": self.n_source_calls,
            "persona": self.persona,
        }


def validate_prompt_provenance(
    *,
    decisions_text: str,
    manifest: dict[str, Any],
    source_artifact: str = PHASE3_SOURCE_ARTIFACT,
    n_expected: int = PHASE3_N_PROMPTS,
    persona_display: str = PHASE3_PERSONA_DISPLAY,
) -> PromptProvenance:
    """Preflight-validate the committed ECL v0 prompts before any live call (Codex H3).

    Raises :class:`ProvenanceError` (a structural Stop, *before* spend, Codex TASK-POST
    HIGH-1) when: the source manifest's ``replay_checksum`` is absent or not a 64-hex
    digest; its ``artifacts.decisions.jsonl.sha256`` is absent or does not match the
    committed ``decisions.jsonl`` sha256 (integrity); the record count is not
    ``n_expected``; **any** call lacks a non-empty system/user prompt or does not name
    the pinned persona (checked on every call, not just the first). On success returns
    the reconstructed calls plus the provenance block for the manifest.
    """
    replay_checksum = manifest.get("replay_checksum")
    if not _is_sha256_hex(replay_checksum):
        raise ProvenanceError(
            f"source manifest replay_checksum missing/not-64hex: {replay_checksum!r}"
        )
    committed_sha = _sha256(decisions_text)
    recorded_sha = (
        manifest.get("artifacts", {}).get("decisions.jsonl", {}).get("sha256")
    )
    if not isinstance(recorded_sha, str):
        raise ProvenanceError(
            "source manifest missing artifacts.decisions.jsonl.sha256"
        )
    if committed_sha != recorded_sha:
        raise ProvenanceError(
            f"source decisions.jsonl sha256 {committed_sha} != "
            f"manifest artifact sha256 {recorded_sha}"
        )
    calls = tuple(handoff.recorded_calls_from_jsonl(decisions_text))
    if len(calls) != n_expected:
        raise ProvenanceError(f"source has {len(calls)} calls, expected N={n_expected}")
    for i, call in enumerate(calls):
        if not call.system_prompt.strip() or not call.user_prompt.strip():
            raise ProvenanceError(f"source call {i} has an empty system/user prompt")
        if persona_display not in call.system_prompt:
            raise ProvenanceError(
                f"source call {i} persona check failed: {persona_display!r} absent"
            )
    return PromptProvenance(
        calls=calls,
        source_artifact=source_artifact,
        source_manifest_checksum=replay_checksum,
        source_decisions_sha256=committed_sha,
        n_source_calls=len(calls),
    )


def surface_reconsideration_markers(
    thinking: str, *, context_chars: int = 60
) -> tuple[str, ...]:
    """Return illustrative *excerpts* around reconsideration-marker occurrences.

    §(b) principle 4 (ii) descriptive raw material for the human memo — an **excerpt
    inventory**, deliberately **not** a count/rate/rank/score/threshold/aha-proxy
    (Codex H4). Callers surface these excerpts and, at most, the boolean *presence*
    (出現有無); they must not emit the inventory length as a metric or gate.
    """
    excerpts: list[str] = []
    low = thinking.lower()
    for marker in RECONSIDERATION_MARKERS:
        start = 0
        while True:
            i = low.find(marker, start)
            if i < 0:
                break
            lo = max(0, i - context_chars)
            hi = min(len(thinking), i + len(marker) + context_chars)
            excerpts.append(re.sub(r"\s+", " ", thinking[lo:hi]).strip())
            start = i + len(marker)
    return tuple(excerpts)


def mechanical_counts(records: Sequence[ThinkCaptureRecord]) -> dict[str, int]:
    """Mechanical technical tallies only (Codex H4/L1) — never a verdict/score/gate.

    Answers the §(b) technical-verification question "did ``think=True`` yield parseable
    traces at all": ``thinking_parseable`` (extractable count), ``finish_length``
    (truncation diagnostic, Codex L1), ``total``. No rate / rank / marker / aha-proxy.
    """
    return {
        "total": len(records),
        "thinking_parseable": sum(1 for r in records if r.thinking_parseable),
        "finish_length": sum(1 for r in records if r.finish_reason == "length"),
    }


# --------------------------------------------------------------------------- #
# Manifest (no Phase 3 replay_checksum by design, Codex H2)
# --------------------------------------------------------------------------- #


def build_phase3_env_pins(
    *,
    qwen3_model_digest: str,
    ollama_version: str,
    vram_gb: float,
    uv_lock_sha256: str,
    model: str = "qwen3:8b",
    base_env_pins: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Env pins for the sealed think=True run (mirrors ``live.build_live_env_pins``).

    ``base_env_pins`` defaults to a fresh :func:`~...handoff.capture_env_pins` snapshot.
    """
    pins: dict[str, Any] = dict(
        base_env_pins if base_env_pins is not None else handoff.capture_env_pins()
    )
    pins["model"] = model
    pins["qwen3_model_digest"] = qwen3_model_digest
    pins["ollama_version"] = ollama_version
    pins["vram_gb"] = vram_gb
    pins["uv_lock_sha256"] = uv_lock_sha256
    pins["think"] = PHASE3_THINK
    return pins


def build_phase3_manifest(
    *,
    provenance: PromptProvenance,
    records: Sequence[ThinkCaptureRecord],
    env_pins: dict[str, Any],
    num_predict: int = PHASE3_THINK_NUM_PREDICT,
) -> dict[str, Any]:
    """Assemble the Phase 3 manifest.

    Carries **no** top-level ``replay_checksum`` (Codex H2): ``think=True`` is
    non-deterministic and this apparatus does no byte-parity verification. The
    deterministic layer is captured by ``prompt_provenance`` (source checksum + JSONL
    sha256). The counts block is mechanical technical facts only (Codex H4).
    """
    return {
        "schema": MANIFEST_SCHEMA,
        "capture_kind": CAPTURE_KIND,
        "nondeterminism_note": NONDETERMINISM_NOTE,
        "phase": "aha-dmn-ecn-phase3-think-true-live",
        "persona": PHASE3_PERSONA,
        "n_prompts": len(records),
        "think": PHASE3_THINK,
        "num_predict": num_predict,
        "requested_seed_metadata": PHASE3_REQUESTED_SEED_METADATA,
        "prompt_provenance": provenance.block(),
        "env_pins": env_pins,
        "mechanical_technical_counts": mechanical_counts(records),
        "over_read_guard": (
            "existence observation only; no verdict/scorer/floor/aha-proxy; two-phase "
            "existence is a non-gating human memo (design-final §Acceptance)"
        ),
    }


def records_to_jsonl(records: Sequence[ThinkCaptureRecord]) -> str:
    """Canonical JSONL of the per-prompt records (one object per line, trailing NL)."""
    return "".join(f"{handoff.canonical_dumps(r.to_dict())}\n" for r in records)


__all__ = [
    "CAPTURE_KIND",
    "MANIFEST_SCHEMA",
    "NONDETERMINISM_NOTE",
    "PHASE3_N_PROMPTS",
    "PHASE3_PERSONA",
    "PHASE3_PERSONA_DISPLAY",
    "PHASE3_REQUESTED_SEED_METADATA",
    "PHASE3_SOURCE_ARTIFACT",
    "PHASE3_THINK",
    "PHASE3_THINK_NUM_PREDICT",
    "RECONSIDERATION_MARKERS",
    "PromptProvenance",
    "ProvenanceError",
    "RawThinkResponse",
    "ThinkCapturePartialError",
    "ThinkCaptureRecord",
    "ThinkCaptureTransportError",
    "ThinkTraceClient",
    "ThinkingExtraction",
    "build_phase3_env_pins",
    "build_phase3_manifest",
    "extract_thinking",
    "mechanical_counts",
    "records_to_jsonl",
    "run_think_capture",
    "surface_reconsideration_markers",
    "validate_prompt_provenance",
]
