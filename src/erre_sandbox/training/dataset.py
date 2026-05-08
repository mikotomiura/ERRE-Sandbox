"""raw_dialog → training-example list adapter (m9-c-spike Phase I, CS-3 / CS-6).

This module sits between :class:`RawTrainingRelation` (the egress contract,
``erre_sandbox.contracts.eval_paths``) and :func:`build_chatml_prompt` (the
ChatML formatter). It applies the persona / epoch_phase / empty-utterance
filters that determine which rows are eligible to specialise the LoRA on.

The signature returns a plain ``list[dict[str, str]]`` so the downstream
``datasets.Dataset.from_list`` call in :func:`train_kant_lora` does not need
a custom adapter — the HuggingFace contract is just ``{"text": str}``.

Filter order (mirrors :func:`assert_phase_beta_ready` so the gate count and
the dataset count agree exactly):

1. ``epoch_phase == "evaluation"`` rows are dropped (CS-3 sentinel).
2. ``speaker_persona_id != persona_id`` rows are dropped (only the persona's
   own utterances become assistant targets; other personas remain context if
   the caller asks for an addressee, but raw_dialog egress only exposes the
   speaker side, so non-Kant rows are simply not training material in this
   spike).
3. ``utterance`` rows that are empty after ``str.strip()`` are dropped
   (PEFT and SGLang both reject empty assistant messages).

The function deliberately does NOT import ``peft`` / ``transformers`` /
``datasets`` — keeping this layer pure-Python lets the dataset tests run on
the CI default install with no GPU extras.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from erre_sandbox.training.prompt_builder import build_chatml_prompt

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


_EVALUATION_PHASE_VALUE = "evaluation"


def build_examples(
    rows: Iterable[Mapping[str, object]],
    *,
    persona_id: str = "kant",
) -> list[dict[str, str]]:
    """Materialise raw_dialog rows into a HuggingFace-compatible example list.

    Args:
        rows: An iterable of raw_dialog row dicts. In production this is the
            output of :meth:`RawTrainingRelation.iter_rows`; in tests it is
            a hand-built list of plain dicts.
        persona_id: Which persona's utterances become assistant targets.
            Defaults to ``"kant"`` for the m9-c-spike. Non-matching speaker
            rows are silently dropped — contamination control is handled by
            :func:`assert_phase_beta_ready` *before* this function runs, so
            empty output here just means insufficient data, not contamination.

    Returns:
        A list of ``{"text": chatml_string}`` dicts. The list may be empty
        if every row was filtered out.

    Raises:
        ValueError: When ``persona_id`` is not a supported persona for the
            spike (currently only ``"kant"``); the unsupported case is
            propagated from :func:`build_chatml_prompt`.
    """
    examples: list[dict[str, str]] = []
    for row in rows:
        # CS-3 belt-and-braces: even though assert_phase_beta_ready raises on
        # any evaluation row, double-filter here so a caller that forgot to
        # gate cannot silently train on contaminated data. Case-insensitive
        # match so upstream casing variation ("Evaluation"/"EVALUATION") is
        # also dropped (security review MEDIUM-2).
        if str(row.get("epoch_phase", "")).strip().lower() == _EVALUATION_PHASE_VALUE:
            continue
        if row.get("speaker_persona_id") != persona_id:
            continue
        utterance = row.get("utterance")
        if not isinstance(utterance, str) or not utterance.strip():
            continue
        addressee_obj = row.get("addressee_persona_id")
        addressee = (
            addressee_obj
            if isinstance(addressee_obj, str) and addressee_obj.strip()
            else None
        )
        text = build_chatml_prompt(
            persona_id=persona_id,
            utterance=utterance,
            addressee_persona_id=addressee,
        )
        examples.append({"text": text})
    return examples


__all__ = ["build_examples"]
