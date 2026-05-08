"""ChatML prompt construction for Kant LoRA training (m9-c-spike Phase I, CS-6).

This module assembles ChatML-formatted training strings from a persona id
plus a target utterance. The output text is what ``datasets.Dataset.from_list``
ingests and what PEFT ``save_pretrained()`` ultimately specialises the
adapter on.

Scope boundary:

* Persona system prompts are static module constants (currently only
  ``KANT_SYSTEM_PROMPT``). The full mapping from ``personas/kant.yaml``
  PersonaSpec → ChatML system message is intentionally **not** wired in
  this PR; Phase β real training lives behind blockers B-1 / B-2 and the
  YAML → spec → system_prompt build is a Phase K β scope item. Keeping
  the prompt as a module constant lets the gate test suite verify ChatML
  shape without booting the persona-loader machinery.
* The two helpers here (:data:`KANT_SYSTEM_PROMPT` /
  :func:`build_chatml_prompt`) consume only ``str`` inputs and return
  ``str`` — no I/O, no peft / transformers imports.
"""

from __future__ import annotations

from typing import Final

# ChatML special tokens (Qwen3 / Llama-3 / Mistral style — matches the
# tokenizer SGLang serves under the [inference] extras stack).
_IM_START: Final[str] = "<|im_start|>"
_IM_END: Final[str] = "<|im_end|>"

KANT_SYSTEM_PROMPT: Final[str] = (
    "You are Immanuel Kant (1724-1804), the Königsberg philosopher who "
    "wrote the Critique of Pure Reason. Reason in your characteristic "
    "deliberate, methodical style: examine premises, distinguish "
    "phenomenon from noumenon, and prefer transcendental analysis over "
    "rhetorical flourish. Maintain your daily routine of a 15:30 walk on "
    "the Linden-Allee for 60-75 minutes, midday dinner 13:00-16:00 with "
    "4-9 invited guests, and morning writing 05:00-07:00."
)
"""Static Kant system prompt used by :func:`build_chatml_prompt`.

Derived from the cognitive habits in ``personas/kant.yaml`` (see
``persona-erre`` skill). Phase β real training may replace this with a
YAML-driven build (PersonaSpec → system prompt) once blockers B-1 / B-2
clear and the persona-loader integration ships.
"""

_SUPPORTED_PERSONA_IDS: Final[frozenset[str]] = frozenset({"kant"})


def build_chatml_prompt(
    persona_id: str,
    utterance: str,
    addressee_persona_id: str | None = None,
) -> str:
    """Build a single ChatML training example.

    The returned string is the verbatim text PEFT consumes via
    ``datasets.Dataset.from_list([{"text": text}, ...])`` (CS-6: PEFT
    save_pretrained directly emits the SGLang-loadable adapter format).

    Layout (Qwen3 ChatML):

    .. code-block:: text

        <|im_start|>system
        {persona system prompt}<|im_end|>
        <|im_start|>user
        ({addressee_persona_id} addressed you.)<|im_end|>
        <|im_start|>assistant
        {utterance}<|im_end|>

    Args:
        persona_id: Persona to specialise on. Currently only ``"kant"``
            is supported; passing anything else raises ``ValueError``
            (Phase β supplemental personas live in M9-C-adopt scope, not
            this spike).
        utterance: The persona's actual utterance — what the LoRA
            should learn to emit. Must be non-empty after stripping;
            empty inputs raise ``ValueError`` so the dataset filter in
            :func:`erre_sandbox.training.dataset.build_examples` cannot
            silently include shape-empty turns.
        addressee_persona_id: When set, an addressee-context line is
            inserted in the user role so the LoRA learns to condition on
            who is being addressed. ``None`` (default) omits the user
            turn entirely — the LoRA then learns the persona's
            unconditional voice, suitable for monologue / writing-window
            data.

    Raises:
        ValueError: ``persona_id`` is not supported, or ``utterance`` is
            empty after stripping whitespace.
    """
    if persona_id not in _SUPPORTED_PERSONA_IDS:
        raise ValueError(
            f"unsupported persona_id {persona_id!r}; the m9-c-spike LoRA "
            f"pipeline currently handles {sorted(_SUPPORTED_PERSONA_IDS)} "
            f"only — multi-persona expansion is M9-C-adopt scope",
        )
    cleaned = utterance.strip()
    if not cleaned:
        raise ValueError(
            "utterance is empty after whitespace strip; the dataset filter "
            "in build_examples() should drop these rows before they reach "
            "build_chatml_prompt()",
        )
    parts: list[str] = [
        f"{_IM_START}system\n{KANT_SYSTEM_PROMPT}{_IM_END}",
    ]
    if addressee_persona_id is not None:
        parts.append(
            f"{_IM_START}user\nYou are addressed by {addressee_persona_id}.{_IM_END}",
        )
    parts.append(f"{_IM_START}assistant\n{cleaned}{_IM_END}")
    return "\n".join(parts)


__all__ = [
    "KANT_SYSTEM_PROMPT",
    "build_chatml_prompt",
]
