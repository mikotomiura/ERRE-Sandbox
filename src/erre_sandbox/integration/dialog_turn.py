r"""LLM-backed :class:`~erre_sandbox.schemas.DialogTurnGenerator` implementation.

Mirrors the :class:`~erre_sandbox.cognition.reflection.Reflector` pattern: one
stateless class receives its dependencies through ``__init__`` and exposes a
single ``async`` entry point that **never raises** — every failure mode
collapses to ``return None`` so the caller (the orchestrator wiring in
``m5-orchestrator-integration``) can normalise to a ``DialogCloseMsg`` without
try/except noise at every call site.

Layer dependency (integration layer extension — see module-level note in
``integration/__init__.py``): this file imports from :mod:`erre_sandbox.inference`,
which the base integration layer forbids. The extension is scoped to this file
and mirrors the precedent set by ``integration/gateway.py`` (which imports from
``world`` / ``cognition``). Adding new files under ``integration/`` that import
from ``inference/`` requires the same kind of explicit justification.

Empirical parameters (``_DIALOG_NUM_PREDICT`` / ``_DIALOG_STOP`` / language
hints / anti-repeat instruction / 160-char hard cap) come from the M5 LLM
spike — see ``.steering/20260420-m5-llm-spike/decisions.md`` judgements 1, 2,
4, 5, 6. Changing any of them without re-running the spike is a regression
waiting to happen.

Hallucination patterns the M5 spike observed on qwen3:8b and how this module
reacts (decisions.md judgement 6):

1. **Language collapse** (~54% of Kant turns without hint) — the
   ``_DIALOG_LANG_HINT`` dict injects a per-persona sentence at the tail of
   the system prompt. Spike run-0 regression: 0%.
2. **Exact repetition across turns** (59% of sessions at 10-turn depth) — the
   ``_user_prompt`` builder appends an anti-repeat instruction starting at
   ``turn_index == 2``. Spike regression: 2/2 runs produced novel text.
3. **Near-paraphrase convergence** — same anti-repeat instruction partially
   mitigates; residual cases are treated as stylistic, not filtered.
4. **Terse collapse (<10 chars)** — allowed on the wire as a stylistic
   artefact (especially Rikyū in chashitsu/zazen); logged but not rejected.
5. **Multi-utterance in one response** (~2.5%) — ``_DIALOG_STOP=["\n\n"]`` cuts
   the stream server-side, and :func:`_sanitize_utterance` truncates at the
   first ``\\n\\n`` as belt-and-braces if the model ignored ``stop``.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Final

from erre_sandbox.inference import (
    ChatMessage,
    OllamaUnavailableError,
    compose_sampling,
)
from erre_sandbox.schemas import DialogTurnMsg

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from erre_sandbox.inference import OllamaChatClient
    from erre_sandbox.schemas import AgentState, PersonaSpec

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Spike-derived constants — do not tune without re-running the M5 LLM spike
# (.steering/20260420-m5-llm-spike/decisions.md).
# ---------------------------------------------------------------------------

_DIALOG_NUM_PREDICT: Final[int] = 120
"""Ollama ``num_predict`` budget. 120 lets Kant's English sentences complete
(spike measured max=118 chars) while staying well inside the 2.5s/turn latency
observed on G-GEAR (decisions.md judgement 1). 80 truncated English; 60
collapsed utterances to <15 chars."""

_DIALOG_STOP: Final[tuple[str, ...]] = ("\n\n",)
"""Server-side stop vocabulary. Pattern 5 (multi-utterance) was observed at
~2.5% of turns; this single sequence eliminates it without latency cost.
Additional tokens (names / quotes / stage directions) proved unnecessary when
``think=False`` + prompt instructions are in place (decisions.md judgement 2).

Immutable tuple rather than ``list`` so the constant cannot be mutated
in-place; the Ollama options dict receives a fresh ``list(_DIALOG_STOP)``."""

_DIALOG_MAX_CHARS: Final[int] = 160
"""Hard cap (in Unicode code points) on the post-sanitisation utterance. The
1.4x headroom over the spike's observed max (118) covers rare 150+ char
outbursts. The value is a single Latin-centric bound; Rikyū's Japanese
output typically lands well under it (spike median 15, max 35)."""

_CONTROL_CHAR_RE: Final[re.Pattern[str]] = re.compile(
    # ANSI CSI alternation listed FIRST so a full escape sequence is
    # consumed as one unit; otherwise the C0 class (which includes ESC =
    # 0x1b) would strip the lead byte alone and leave ``[31m`` behind.
    r"\x1b\[[0-9;]*[A-Za-z]|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]",
)
"""Strip ANSI CSI escape sequences and C0 control codes (except ``\\t``,
``\\n``, ``\\r``) before the utterance hits the WebSocket bus. Godot and the
Streamlit dashboard do not interpret ANSI codes, but stray bytes from a
misbehaving model would corrupt logs and ``RichTextLabel`` rendering."""

_DIALOG_LANG_HINT: Final[dict[str, str]] = {
    "kant": "Respond in English.",
    "rikyu": "日本語で応答せよ（古典的・侘び寂びの語彙を用いる）。",
    "nietzsche": "Respond in German, or in English with German-inflected phrasing.",
}
"""Per-persona language hint appended to the system prompt. Without this,
qwen3:8b produced classical-Japanese outputs even for Kant 54% of the time
(decisions.md judgement 5). Missing persona ids skip injection rather than
raising — new personas just default to the model's own language choice."""

_COMMON_PREFIX: Final[str] = (
    "You are an autonomous agent in ERRE-Sandbox, a 3D world with five zones "
    "(study / peripatos / chashitsu / agora / garden). You are engaged in a "
    "spoken dialog with another historical figure sharing your zone. Stay in "
    "character; speak as yourself, not about yourself."
)
"""Dialog-mode common prefix — distinct from the action-selection prefix in
:mod:`erre_sandbox.cognition.prompting` because dialog does not ask for a JSON
action envelope. Placed first so SGLang's RadixAttention (M7+) can share KV
across personas in dialog mode."""

_ANTI_REPEAT_INSTRUCTION: Final[str] = (
    "Respond in one utterance that does NOT repeat any phrase from the prior "
    "turns. Introduce a new thought."
)
"""Appended to the user prompt starting at ``turn_index == _ANTI_REPEAT_MIN_TURN``.
Spike showed vague instructions ('move forward') were ineffective; this
specific wording achieved 100% novelty over 2 runs (decisions.md judgement 4)."""

_ANTI_REPEAT_MIN_TURN: Final[int] = 2
"""Smallest ``turn_index`` at which the anti-repeat instruction is injected.
Turns 0 and 1 have nothing prior to repeat; the instruction adds noise without
benefit there, and the spike observed exact repetition emerging at turn 2."""

_UTTERANCE_ELLIPSIS: Final[str] = "…"


# ---------------------------------------------------------------------------
# Prompt builders — module-private because cognition/prompting.py is reserved
# for the action-selection path (which emits RESPONSE_SCHEMA_HINT JSON).
# Dialog prompts have no JSON contract and are not reusable by cognition.
# ---------------------------------------------------------------------------


def _format_habits(persona: PersonaSpec, *, limit: int = 3) -> str:
    habits = list(persona.cognitive_habits)[:limit]
    if not habits:
        return "(no habits recorded)"
    return "\n".join(f"- {h.description} [{h.flag.value}]" for h in habits)


def _format_transcript(transcript: Sequence[DialogTurnMsg]) -> str:
    if not transcript:
        return "(no turns yet — you speak first)"
    lines = [f"[{turn.speaker_id}] {turn.utterance}" for turn in transcript]
    return "\n".join(lines)


def _build_dialog_system_prompt(
    *,
    speaker_persona: PersonaSpec,
    speaker_state: AgentState,
    addressee_persona: PersonaSpec | None,
    addressee_state: AgentState,
) -> str:
    """Assemble the dialog system prompt.

    Order is load-bearing: common prefix first (RadixAttention), persona
    block, dialog context (addressee identity + zone + mode), language hint
    last. The language hint comes last on purpose — spike runs showed it
    needed to be the most recent directive in the system channel to overcome
    the CJK prior that transcripts from other personas create.
    """
    zone = speaker_state.position.zone.value
    mode = speaker_state.erre.name.value
    # Prefer addressee's display_name from the persona registry; fall back to
    # agent_id if the persona isn't loaded (e.g. test fixture with an
    # unregistered speaker). Never raise — missing persona must degrade, not
    # break.
    addressee_label = (
        addressee_persona.display_name
        if addressee_persona is not None
        else addressee_state.agent_id
    )
    persona_block = (
        f"Persona: {speaker_persona.display_name} ({speaker_persona.era}).\n"
        f"Cognitive habits:\n{_format_habits(speaker_persona)}"
    )
    dialog_context = (
        f"You are speaking with {addressee_label}. "
        f"Zone: {zone}. ERRE mode: {mode}. "
        "Keep each utterance concise: at most 80 Japanese characters "
        "or 160 Latin characters. Return ONLY the utterance text — no names, "
        "no quotation marks, no stage directions, no parentheticals, no JSON."
    )
    lang_hint = _DIALOG_LANG_HINT.get(speaker_persona.persona_id, "")
    parts = [_COMMON_PREFIX, persona_block, dialog_context]
    if lang_hint:
        parts.append(lang_hint)
    return "\n\n".join(parts)


def _build_dialog_user_prompt(
    *,
    transcript: Sequence[DialogTurnMsg],
    zone: str,
    erre_mode: str,
    turn_index: int,
) -> str:
    """Assemble the dialog user prompt.

    For ``turn_index >= 2`` the anti-repeat instruction is appended. Earlier
    turns get the bare transcript-plus-cue prompt — the spike showed the
    instruction to be unnecessary (turn 0/1 have no prior phrases to repeat)
    and occasionally counterproductive (redundant directive on the opener).
    """
    transcript_block = _format_transcript(transcript)
    body = (
        f"Dialog so far (oldest → newest):\n{transcript_block}\n\n"
        f"Current ERRE mode: {erre_mode}. Zone: {zone}.\n"
        "Your turn. Respond in one utterance."
    )
    if turn_index >= _ANTI_REPEAT_MIN_TURN:
        body = f"{body}\n\n{_ANTI_REPEAT_INSTRUCTION}"
    return body


def _build_dialog_messages(
    *,
    speaker_persona: PersonaSpec,
    speaker_state: AgentState,
    addressee_persona: PersonaSpec | None,
    addressee_state: AgentState,
    transcript: Sequence[DialogTurnMsg],
    turn_index: int,
) -> list[ChatMessage]:
    system = _build_dialog_system_prompt(
        speaker_persona=speaker_persona,
        speaker_state=speaker_state,
        addressee_persona=addressee_persona,
        addressee_state=addressee_state,
    )
    user = _build_dialog_user_prompt(
        transcript=transcript,
        zone=speaker_state.position.zone.value,
        erre_mode=speaker_state.erre.name.value,
        turn_index=turn_index,
    )
    return [
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content=user),
    ]


def _sanitize_utterance(raw: str) -> str | None:
    r"""Normalise an LLM response into a single-utterance line, or drop it.

    Steps:

    1. Strip outer whitespace.
    2. Cut at the first ``\\n\\n`` (pattern 5 belt-and-braces: ``stop`` on the
       wire should already have handled this, but a model that ignored the
       stop sequence must not leak a second utterance onto the bus).
    3. Strip C0 control codes (except ``\\t``, ``\\n``, ``\\r``) and ANSI CSI
       escape sequences. Defence in depth — qwen3 does not emit these, but
       stray bytes from a misbehaving model would corrupt downstream
       renderers (Godot ``RichTextLabel``, Streamlit dashboard logs).
    4. Collapse remaining whitespace runs to single spaces.
    5. ``None`` for empty output (pattern: empty string, all-whitespace,
       or a scrubbed-to-empty artefact after step 3).
    6. Hard-cap at :data:`_DIALOG_MAX_CHARS`; overflow appends ``…``.
    """
    if not raw:
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    # Pattern 5 defence (second utterance after blank line).
    first_utterance = stripped.split("\n\n", 1)[0].strip()
    if not first_utterance:
        return None
    scrubbed = _CONTROL_CHAR_RE.sub("", first_utterance)
    collapsed = " ".join(scrubbed.split())
    if not collapsed:
        return None
    if len(collapsed) <= _DIALOG_MAX_CHARS:
        return collapsed
    return collapsed[:_DIALOG_MAX_CHARS] + _UTTERANCE_ELLIPSIS


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class OllamaDialogTurnGenerator:
    """Concrete :class:`~erre_sandbox.schemas.DialogTurnGenerator` over Ollama.

    Dependencies are injected at construction:

    * ``llm`` — a live :class:`OllamaChatClient`. The generator does not own
      the client's lifecycle (matches :class:`Reflector`): the composition
      root creates it once and shares it across reflection + dialog paths.
    * ``personas`` — the persona registry the orchestrator already builds.
      Used to resolve ``addressee_state.persona_id`` to a
      :class:`PersonaSpec` so the prompt can call the other agent by name.
      Protocol ties our hands on what :meth:`generate_turn` receives (only
      ``addressee_state``, not ``addressee_persona``); this DI closes that
      gap without touching the frozen Protocol signature.

    All failure modes — Ollama unreachable / empty response / oversized
    utterance / split-utterance artefact — resolve to ``return None`` with a
    WARNING log, per the Protocol contract that callers treat ``None`` as a
    soft close. The same policy mirrors
    :meth:`erre_sandbox.cognition.reflection.Reflector.maybe_reflect`.
    """

    def __init__(
        self,
        *,
        llm: OllamaChatClient,
        personas: Mapping[str, PersonaSpec],
    ) -> None:
        self._llm = llm
        self._personas = personas

    async def generate_turn(
        self,
        *,
        dialog_id: str,
        speaker_state: AgentState,
        speaker_persona: PersonaSpec,
        addressee_state: AgentState,
        transcript: Sequence[DialogTurnMsg],
        world_tick: int,
    ) -> DialogTurnMsg | None:
        addressee_persona = self._personas.get(addressee_state.persona_id)
        turn_index = len(transcript)

        messages = _build_dialog_messages(
            speaker_persona=speaker_persona,
            speaker_state=speaker_state,
            addressee_persona=addressee_persona,
            addressee_state=addressee_state,
            transcript=transcript,
            turn_index=turn_index,
        )
        sampling = compose_sampling(
            speaker_persona.default_sampling,
            speaker_state.erre.sampling_overrides,
        )

        try:
            resp = await self._llm.chat(
                messages,
                sampling=sampling,
                options={
                    "num_predict": _DIALOG_NUM_PREDICT,
                    "stop": list(_DIALOG_STOP),
                },
                think=False,
            )
        except OllamaUnavailableError as exc:
            logger.warning(
                "Dialog LLM unavailable for speaker %s in dialog %s: %s — "
                "skipping turn",
                speaker_state.agent_id,
                dialog_id,
                exc,
            )
            return None

        utterance = _sanitize_utterance(resp.content)
        if utterance is None:
            logger.warning(
                "Dialog LLM produced unusable content for speaker %s "
                "in dialog %s (raw length=%d) — skipping turn",
                speaker_state.agent_id,
                dialog_id,
                len(resp.content),
            )
            return None

        return DialogTurnMsg(
            tick=world_tick,
            dialog_id=dialog_id,
            speaker_id=speaker_state.agent_id,
            addressee_id=addressee_state.agent_id,
            utterance=utterance,
            turn_index=turn_index,
        )


__all__ = ["OllamaDialogTurnGenerator"]
