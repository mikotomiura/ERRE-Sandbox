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

Retrain v2 addition: :func:`build_weighted_examples` augments the same
filter chain with per-example weight metadata (language, token_count,
has_addressee, marker_density_per_100_tokens) required by
:func:`erre_sandbox.training.weighting.compute_example_weight`. The plain
:func:`build_examples` path is preserved for the K-β baseline / dry-run /
gate-only callers that have no need for weighting metadata.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from erre_sandbox.training.example_features import extract_example_metadata
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


def build_weighted_examples(
    rows: Iterable[Mapping[str, object]],
    *,
    persona_id: str = "kant",
    source_shard: str,
    source_shard_type: str,
    use_real_tokenizer: bool = False,
) -> list[dict[str, object]]:
    """Materialise raw_dialog rows into a weighted-training example list.

    Each output element carries the ChatML ``"text"`` payload plus a
    ``"weight_metadata"`` dict that
    :func:`erre_sandbox.training.weighting.compute_example_weight` consumes
    to produce the per-example raw weight (clamped to ``[0.1, 3.0]``).

    The filter chain is identical to :func:`build_examples` so the gate
    count, the un-weighted example count, and the weighted example count
    agree exactly. Adding weight metadata is a *strictly additive* change:
    callers that do not need weighting can ignore the extra field.

    Args:
        rows: Raw_dialog rows. Same shape as :func:`build_examples`.
        persona_id: Filter key (defaults to ``"kant"``).
        source_shard: Basename of the source DuckDB shard for provenance
            (e.g. ``"kant_natural_run0.duckdb"``). Stamped into the
            weight metadata so the group-aware split in
            :func:`erre_sandbox.training.train_kant_lora` can stratify
            by shard type.
        source_shard_type: ``"natural"`` or ``"stimulus"``. Pre-computed
            via :func:`erre_sandbox.training.example_features.classify_shard`
            (caller's responsibility — the analyse-side classifier is the
            single source of truth).
        use_real_tokenizer: Forwarded to
            :func:`erre_sandbox.training.example_features.estimate_token_count`.
            ``False`` keeps the call deterministic and free of the
            ``[training]`` extras (recommended for unit tests). ``True``
            is the production path — the weight metadata then reflects
            the actual Qwen3-8B tokenisation, which is what the trainer
            will see (Codex MEDIUM-1: production training must use the
            real tokenizer or the weights drift from what training
            actually does).

    Returns:
        A list of dicts shaped as
        ``{"text": chatml_str, "weight_metadata": {...}}``. The list may
        be empty if every row was filtered out.

    Raises:
        ValueError: ``persona_id`` is not supported, propagated from
            :func:`build_chatml_prompt`.
    """
    examples: list[dict[str, object]] = []
    for row in rows:
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
        weight_metadata = extract_example_metadata(
            row,
            source_shard=source_shard,
            source_shard_type=source_shard_type,
            use_real_tokenizer=use_real_tokenizer,
        )
        examples.append({"text": text, "weight_metadata": weight_metadata})
    return examples


__all__ = ["build_examples", "build_weighted_examples"]
