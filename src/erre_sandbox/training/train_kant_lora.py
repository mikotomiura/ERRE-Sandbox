"""Phase β real Kant LoRA training + 4-種 hard-fail gate (CS-3..CS-6).

Three public surfaces:

* :func:`assert_phase_beta_ready` — pure-Python 4-種 hard-fail gate.
  Imports no GPU stack so the test suite + ``--dry-run`` CLI path stay
  installable on the CI default profile (no ``[training]`` extras).
* :func:`train_kant_lora` — Phase β CLI entry. Aggregates rows from one
  or more golden DuckDB files via :func:`connect_training_view`, runs
  the gate, then performs QLoRA NF4 + double quant + gradient
  checkpointing + rank=8 LoRA training on Qwen3-8B (CS-4 / CS-5 / CS-6).
  peft / transformers / accelerate / bitsandbytes / datasets are
  imported **lazily inside the function body** so module import stays
  free of the ``[training]`` extras.
* :func:`main` — argparse ``__main__`` wrapper invoked by
  ``python -m erre_sandbox.training.train_kant_lora …``. Operator
  override flags are accepted for every CS-4 default; the gate
  (CS-3) is always run before any GPU stack import so a bad config
  fails before VRAM is touched.

Hard-fail order (CS-3, must match :func:`build_examples` filter order):

1. ``epoch_phase == "evaluation"`` row present → :class:`EvaluationContaminationError`
2. ``individual_layer_enabled`` column absent in ``relation.columns`` →
   :class:`BlockerNotResolvedError` (B-1 not landed; silent skip is forbidden)
3. ``individual_layer_enabled is True`` row present →
   :class:`EvaluationContaminationError`
4. ``len(build_examples(rows, persona_id=persona_id)) < min_examples`` →
   :class:`InsufficientTrainingDataError`

The gate is order-sensitive: contamination detection runs **before** the
realised-count check, so a flood of ``epoch_phase=evaluation`` rows
cannot silently dilute the threshold count in step 4.

Post-B-1 (m9-individual-layer-schema-add landed) status: hard-fail #2
no longer fires on production schemas because
:func:`erre_sandbox.evidence.eval_store.bootstrap_schema` materialises
``individual_layer_enabled`` as ``BOOLEAN NOT NULL DEFAULT FALSE`` and
``_DuckDBRawTrainingRelation.__init__`` runs a construction-time
aggregate assert (Codex HIGH-2) that rejects ``epoch_phase=evaluation``
rows and truthy / NULL ``individual_layer_enabled`` rows before any
caller can iterate them. Hard-fail #2 still fires when callers pass a
mock relation with ``with_individual_layer_column=False``
(``tests/test_training/conftest.py``), so the regression test
``test_individual_layer_column_absent_raises_blocker_not_resolved``
keeps the contract layer hot — see :class:`BlockerNotResolvedError`
docstring for the rationale.
"""

from __future__ import annotations

import argparse
import glob as _glob
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal

from erre_sandbox.contracts.eval_paths import INDIVIDUAL_LAYER_ENABLED_KEY
from erre_sandbox.training.dataset import build_examples
from erre_sandbox.training.exceptions import (
    BlockerNotResolvedError,
    EvaluationContaminationError,
    InsufficientTrainingDataError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.contracts.eval_paths import RawTrainingRelation


_LOGGER: Final = logging.getLogger(__name__)


DEFAULT_MIN_EXAMPLES: Final[int] = 1000
"""Operational SLO for Phase β realised example count (CS-3).

Derived from P-Tailor / Anthropic persona vector / BIG5-CHAT prior art
(see ``.steering/20260508-m9-c-spike/decisions.md`` CS-3 ``棄却``).
Adjust per-spike scope only — production training thresholds belong in
M9-C-adopt scope, not this spike.
"""

DEFAULT_BASE_MODEL: Final[str] = "Qwen/Qwen3-8B"
DEFAULT_LORA_RANK: Final[int] = 8
DEFAULT_BATCH_SIZE: Final[int] = 1
DEFAULT_GRADIENT_ACCUMULATION: Final[int] = 8
DEFAULT_MAX_SEQ_LENGTH: Final[int] = 2048
DEFAULT_MAX_STEPS: Final[int] = 2000
DEFAULT_LEARNING_RATE: Final[float] = 2e-4
DEFAULT_SAVE_STEPS: Final[int] = 500
DEFAULT_TARGET_MODULES: Final[tuple[str, ...]] = (
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
)
"""LoRA target modules (CS-9 / CS-5). Qwen3-8B attention projections."""

Quantization = Literal["nf4", "fp4", "none"]

_EVALUATION_PHASE_VALUE: Final[str] = "evaluation"


@dataclass(frozen=True, slots=True)
class _DuckDBShardStat:
    path: Path
    raw_rows: int
    persona_examples: int


@dataclass(slots=True)
class TrainRunSummary:
    """Audit trail returned by :func:`train_kant_lora` (also written to disk).

    The CLI ``--dry-run`` path returns the same shape with
    ``training_executed=False`` — letting downstream automation key off a
    single object regardless of whether the GPU loop actually ran.
    """

    persona_id: str
    base_model: str
    lora_rank: int
    quantization: Quantization
    batch_size: int
    gradient_accumulation_steps: int
    max_seq_length: int
    max_steps: int
    learning_rate: float
    save_steps: int
    min_examples_threshold: int
    realised_examples: int
    output_dir: str
    db_paths: list[str]
    shard_stats: list[dict[str, object]]
    training_executed: bool
    peak_vram_bytes: int = 0
    train_loss: float | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "persona_id": self.persona_id,
            "base_model": self.base_model,
            "lora_rank": self.lora_rank,
            "quantization": self.quantization,
            "batch_size": self.batch_size,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "max_seq_length": self.max_seq_length,
            "max_steps": self.max_steps,
            "learning_rate": self.learning_rate,
            "save_steps": self.save_steps,
            "min_examples_threshold": self.min_examples_threshold,
            "realised_examples": self.realised_examples,
            "output_dir": self.output_dir,
            "db_paths": list(self.db_paths),
            "shard_stats": list(self.shard_stats),
            "training_executed": self.training_executed,
            "peak_vram_bytes": self.peak_vram_bytes,
            "train_loss": self.train_loss,
            "metadata": dict(self.metadata),
        }


def assert_phase_beta_ready(
    relation: RawTrainingRelation,
    *,
    persona_id: str = "kant",
    min_examples: int = DEFAULT_MIN_EXAMPLES,
    individual_layer_enabled_required: bool = True,
) -> int:
    """4-種 hard-fail gate for Phase β real Kant training (CS-3).

    Run this **before** consuming the relation for actual training. The
    function materialises every row once and applies the four checks in
    order; each check raises a distinct exception type so the test
    suite (and any future debugger) can pinpoint which contract was
    breached.

    Args:
        relation: A constrained training-egress view (typically the
            output of :func:`erre_sandbox.evidence.eval_store.connect_training_view`).
            Tests pass a hand-built Protocol-conforming mock so the
            allow-list lockstep check inside ``_DuckDBRawTrainingRelation``
            does not interfere with the synthetic ``individual_layer_enabled``
            scenarios.
        persona_id: Which persona's examples are counted. The same value
            must reach :func:`build_examples` so the gate count matches
            the dataset count exactly.
        min_examples: Operational threshold. Defaults to
            :data:`DEFAULT_MIN_EXAMPLES`. Lowering this is a CS-3
            amendment, not a knob to twist silently.
        individual_layer_enabled_required: When ``True`` (default), the
            gate enforces the DB11 enforcement contract — column must
            exist, no row may have it set to ``True``. Always ``True``
            in production after B-1 (m9-individual-layer-schema-add)
            lands, since :func:`bootstrap_schema` always materialises
            the column. Tests pass ``False`` only when fabricating
            pre-B-1 schema scenarios via the conftest mock fixture
            ``make_relation(with_individual_layer_column=False)``.

    Returns:
        The realised Kant example count (``len(build_examples(..))``).
        Callers can log this to verify the gate threshold was cleared
        with non-trivial margin.

    Raises:
        EvaluationContaminationError: ``epoch_phase=evaluation`` row, or
            ``individual_layer_enabled=True`` row, surfaced through the
            relation.
        BlockerNotResolvedError: ``individual_layer_enabled`` column is
            absent from ``relation.columns``; blocker B-1
            (``m9-individual-layer-schema-add``) has not landed.
        InsufficientTrainingDataError: Realised example count is below
            ``min_examples``.
    """
    raw_rows: list[dict[str, object]] = [dict(row) for row in relation.iter_rows()]

    # 1) epoch_phase=evaluation contamination — must run first so the
    #    realised-count check below sees the post-filter dataset.
    eval_rows = [
        r
        for r in raw_rows
        if str(r.get("epoch_phase", "")).strip().lower() == _EVALUATION_PHASE_VALUE
    ]
    if eval_rows:
        raise EvaluationContaminationError(
            f"assert_phase_beta_ready: {len(eval_rows)} row(s) carry"
            f" epoch_phase~={_EVALUATION_PHASE_VALUE!r} (case-insensitive);"
            f" the training-view must filter these out before training can"
            f" run (CS-3 sentinel)",
        )

    # 2 + 3) individual_layer_enabled enforcement (DB11 / blocker B-1)
    if individual_layer_enabled_required:
        if INDIVIDUAL_LAYER_ENABLED_KEY not in relation.columns:
            raise BlockerNotResolvedError(
                f"assert_phase_beta_ready: training-view schema does not"
                f" expose {INDIVIDUAL_LAYER_ENABLED_KEY!r} column."
                f" Blocker B-1 (m9-individual-layer-schema-add) has not"
                f" landed — Phase β cannot proceed without DB11"
                f" enforcement (CS-3 silent-skip ban).",
            )
        ind_rows = [
            r for r in raw_rows if bool(r.get(INDIVIDUAL_LAYER_ENABLED_KEY, False))
        ]
        if ind_rows:
            raise EvaluationContaminationError(
                f"assert_phase_beta_ready: {len(ind_rows)} row(s) have"
                f" truthy {INDIVIDUAL_LAYER_ENABLED_KEY}; these are flagged for"
                f" individual evaluation and must not enter training"
                f" (CS-3 / DB11)",
            )

    # 4) realised Kant example count vs literature-based threshold
    examples = build_examples(raw_rows, persona_id=persona_id)
    realised = len(examples)
    if realised < min_examples:
        raise InsufficientTrainingDataError(
            f"assert_phase_beta_ready: realised {persona_id!r} example count"
            f" {realised} is below the Phase β threshold {min_examples};"
            f" gather more dialog turns via M9-eval P3 (blocker B-2) or"
            f" record a CS-3 amendment to lower the threshold.",
        )
    return realised


# ---------------------------------------------------------------------------
# Shard aggregation (gate-only path, no GPU imports)
# ---------------------------------------------------------------------------


def _collect_from_shards(
    db_paths: Sequence[Path],
    *,
    persona_id: str,
    min_examples: int,
    individual_layer_enabled_required: bool = True,
) -> tuple[list[dict[str, str]], list[_DuckDBShardStat], int]:
    """Aggregate raw_dialog rows across multiple DuckDB shards and gate them.

    Each shard is opened individually via :func:`connect_training_view`,
    which means the loader-level aggregate assert (Codex HIGH-2) fires
    per-shard *before* the rows can pollute the in-memory aggregate.
    After all shards are drained, the aggregate goes through
    :func:`assert_phase_beta_ready` so threshold #4 is applied to the
    full corpus (the per-shard count is usually far below
    ``min_examples`` and would otherwise hard-fail every shard).

    Returns:
        Tuple of (built ChatML examples, per-shard stats, realised count).
    """
    from erre_sandbox.evidence.eval_store import (  # noqa: PLC0415
        connect_training_view,
    )

    aggregated_rows: list[dict[str, object]] = []
    shard_stats: list[_DuckDBShardStat] = []
    for shard_path in db_paths:
        relation = connect_training_view(shard_path)
        try:
            shard_rows = [dict(row) for row in relation.iter_rows()]
        finally:
            close = getattr(relation, "close", None)
            if callable(close):
                close()
        shard_examples = build_examples(shard_rows, persona_id=persona_id)
        shard_stats.append(
            _DuckDBShardStat(
                path=Path(shard_path),
                raw_rows=len(shard_rows),
                persona_examples=len(shard_examples),
            ),
        )
        aggregated_rows.extend(shard_rows)

    # Build a transient ``RawTrainingRelation``-compatible view over the
    # aggregate so ``assert_phase_beta_ready`` exercises the same code
    # path as a single-shard run. Mirrors the conftest ``FakeRawTrainingRelation``
    # shape but lives here (production code; the testing conftest is not
    # importable at runtime).
    from erre_sandbox.contracts.eval_paths import RAW_DIALOG_SCHEMA  # noqa: PLC0415

    columns: tuple[str, ...] = (
        tuple(aggregated_rows[0].keys()) if aggregated_rows else ()
    )

    class _AggregateRelation:
        schema_name = RAW_DIALOG_SCHEMA

        def __init__(self, rows: list[dict[str, object]]) -> None:
            self._rows = rows

        @property
        def columns(self) -> tuple[str, ...]:
            return columns

        def row_count(self) -> int:
            return len(self._rows)

        def iter_rows(self) -> Any:
            yield from self._rows

    realised = assert_phase_beta_ready(
        _AggregateRelation(aggregated_rows),
        persona_id=persona_id,
        min_examples=min_examples,
        individual_layer_enabled_required=individual_layer_enabled_required,
    )
    examples = build_examples(aggregated_rows, persona_id=persona_id)
    return examples, shard_stats, realised


# ---------------------------------------------------------------------------
# Training entry — lazy GPU-stack imports kept inside the function body
# ---------------------------------------------------------------------------


def train_kant_lora(
    db_paths: Sequence[Path | str],
    output_dir: Path | str,
    *,
    base_model: str = DEFAULT_BASE_MODEL,
    persona_id: str = "kant",
    lora_rank: int = DEFAULT_LORA_RANK,
    quantization: Quantization = "nf4",
    batch_size: int = DEFAULT_BATCH_SIZE,
    gradient_accumulation_steps: int = DEFAULT_GRADIENT_ACCUMULATION,
    max_seq_length: int = DEFAULT_MAX_SEQ_LENGTH,
    max_steps: int = DEFAULT_MAX_STEPS,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    save_steps: int = DEFAULT_SAVE_STEPS,
    min_examples: int = DEFAULT_MIN_EXAMPLES,
    target_modules: Sequence[str] = DEFAULT_TARGET_MODULES,
    seed: int = 42,
    dry_run: bool = False,
) -> TrainRunSummary:
    """Phase β real Kant LoRA training entry (CS-4 / CS-5 / CS-6).

    Pipeline:

    1. Resolve ``db_paths`` (sequence of golden DuckDB files) and open
       each via :func:`connect_training_view` (loader-level aggregate
       assert fires per-shard).
    2. Run :func:`assert_phase_beta_ready` on the aggregate so threshold
       #4 sees the full corpus.
    3. If ``dry_run=True``, return the summary now — no GPU import, no
       file written into ``output_dir``.
    4. Otherwise: build a HuggingFace ``Dataset`` from the ChatML
       examples, load the tokenizer + 4-bit quantised base model, attach
       a rank=``lora_rank`` LoRA, then drive a ``Trainer`` loop with
       gradient checkpointing + paged 8-bit AdamW.
    5. Save adapter (``adapter_config.json`` + ``adapter_model.safetensors``)
       + tokenizer + ``train_metadata.json`` audit trail to
       ``output_dir``. CS-6: SGLang ``/load_lora_adapter`` consumes this
       directory directly.

    Args:
        db_paths: One or more DuckDB files produced by M9-eval P3 (golden
            cells). Each shard's loader-level assert runs before the
            in-memory aggregate is gated, so a contaminated shard fails
            fast.
        output_dir: PEFT adapter destination. CS-6: also the path
            SGLang loads.
        base_model: HuggingFace base model id. Default ``Qwen/Qwen3-8B``.
        persona_id: Persona to specialise on (``build_examples`` filter).
        lora_rank: LoRA rank (CS-5 fixes at 8 for the spike).
        quantization: ``"nf4"`` (CS-4 default) / ``"fp4"`` / ``"none"``.
            ``"none"`` is intended for diagnostic CPU smoke runs, not for
            G-GEAR (VRAM budget would not fit a full-precision Qwen3-8B).
        batch_size: Per-device train batch size. CS-4 default 1; values
            > 1 log a warning because VRAM headroom may not absorb them.
        gradient_accumulation_steps: HF Trainer gradient accumulation.
            CS-4 default 8 — paired with ``batch_size=1`` to reach an
            effective batch of 8 without VRAM cost.
        max_seq_length: Token sequence cap during tokenisation. CS-4
            default 2048 — activation memory scales roughly linearly.
        max_steps: HF Trainer ``max_steps`` (training stops at this
            step count; supersedes ``num_train_epochs``).
        learning_rate: AdamW peak learning rate (cosine schedule with
            warmup_ratio=0.03).
        save_steps: Checkpoint cadence (HF Trainer ``save_steps``);
            ``save_total_limit=2`` keeps the last two on disk.
        min_examples: CS-3 gate threshold (default 1000).
        target_modules: LoRA injection targets (Qwen3-8B attention
            projections).
        seed: Reproducibility seed for HF Trainer / random init.
        dry_run: When ``True``, only the gate runs and the function
            returns immediately with ``training_executed=False``. No
            GPU-stack import is performed.

    Returns:
        :class:`TrainRunSummary` describing what ran (or what would have
        run, when ``dry_run=True``). The same struct is JSON-serialised
        to ``output_dir/train_metadata.json`` for the audit trail.

    Raises:
        EvaluationContaminationError / BlockerNotResolvedError /
            InsufficientTrainingDataError: From the gate (CS-3).
        FileNotFoundError: ``db_paths`` is empty after glob expansion.
        ValueError: ``quantization`` is not one of the accepted values.
    """
    if quantization not in {"nf4", "fp4", "none"}:
        raise ValueError(
            f"quantization must be 'nf4'/'fp4'/'none', got {quantization!r}",
        )

    resolved_paths: list[Path] = [Path(p) for p in db_paths]
    if not resolved_paths:
        raise FileNotFoundError(
            "train_kant_lora: db_paths is empty — pass at least one"
            " DuckDB file (or expand --duckdb-glob before calling)",
        )

    output_dir_path = Path(output_dir)
    if not dry_run:
        output_dir_path.mkdir(parents=True, exist_ok=True)

    if base_model != DEFAULT_BASE_MODEL:
        # ``trust_remote_code=True`` is the documented contract for Qwen
        # and similar models that ship custom modeling code in the
        # HuggingFace hub. Spike scope: warn loudly if the operator
        # swaps the base model so an arbitrary repo cannot quietly load
        # remote Python (security review LOW). M9-C-adopt should add an
        # allow-list / signature check rather than rely on the warning.
        _LOGGER.warning(
            "train_kant_lora: --base-model=%r differs from CS-5 default"
            " %r and will be loaded with trust_remote_code=True;"
            " confirm the repository is trusted before re-running.",
            base_model,
            DEFAULT_BASE_MODEL,
        )

    if (
        batch_size > DEFAULT_BATCH_SIZE
        or gradient_accumulation_steps < DEFAULT_GRADIENT_ACCUMULATION
    ):
        # CS-4 amendment territory — log so the run is auditable but do
        # not refuse (operator override is the documented escape hatch).
        _LOGGER.warning(
            "train_kant_lora: batch=%d / grad_accum=%d exceed CS-4 defaults"
            " (%d / %d); VRAM peak may exceed the 12GB safety margin",
            batch_size,
            gradient_accumulation_steps,
            DEFAULT_BATCH_SIZE,
            DEFAULT_GRADIENT_ACCUMULATION,
        )

    examples, shard_stats, realised = _collect_from_shards(
        resolved_paths,
        persona_id=persona_id,
        min_examples=min_examples,
    )

    summary = TrainRunSummary(
        persona_id=persona_id,
        base_model=base_model,
        lora_rank=lora_rank,
        quantization=quantization,
        batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        max_seq_length=max_seq_length,
        max_steps=max_steps,
        learning_rate=learning_rate,
        save_steps=save_steps,
        min_examples_threshold=min_examples,
        realised_examples=realised,
        output_dir=str(output_dir_path),
        db_paths=[str(p) for p in resolved_paths],
        shard_stats=[
            {
                "path": str(s.path),
                "raw_rows": s.raw_rows,
                "persona_examples": s.persona_examples,
            }
            for s in shard_stats
        ],
        training_executed=False,
        metadata={
            "target_modules": list(target_modules),
            "seed": seed,
        },
    )

    if dry_run:
        _LOGGER.info(
            "train_kant_lora dry-run: gate cleared with %d examples across"
            " %d shard(s); GPU stack not imported",
            realised,
            len(shard_stats),
        )
        return summary

    _execute_training_run(
        examples=examples,
        output_dir_path=output_dir_path,
        summary=summary,
        base_model=base_model,
        lora_rank=lora_rank,
        quantization=quantization,
        batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        max_seq_length=max_seq_length,
        max_steps=max_steps,
        learning_rate=learning_rate,
        save_steps=save_steps,
        target_modules=target_modules,
        seed=seed,
    )

    return summary


# ---------------------------------------------------------------------------
# GPU-stack inner helpers — every import is local so the gate-only path
# above stays installable with no [training] extras. Splitting these
# helpers out keeps the orchestrator (``train_kant_lora``) below the
# C901 / PLR0912 / PLR0915 thresholds without dropping any CS-4 / CS-6
# step.
# ---------------------------------------------------------------------------


def _load_quantised_model(
    base_model: str,
    quantization: Quantization,
) -> tuple[Any, Any]:
    """Load the tokenizer + base model with the CS-4 quantisation config.

    Lazy-imports ``torch`` / ``transformers`` / ``bitsandbytes`` so the
    gate-only path stays free of the ``[training]`` extras.
    """
    import torch  # noqa: PLC0415
    from transformers import (  # noqa: PLC0415
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
    )

    tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call,unused-ignore]
        base_model,
        trust_remote_code=True,
        use_fast=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    load_kwargs: dict[str, object] = {
        "torch_dtype": torch.bfloat16,
        "device_map": "auto",
    }
    if quantization in {"nf4", "fp4"}:
        bnb_config = BitsAndBytesConfig(  # type: ignore[no-untyped-call,unused-ignore]
            load_in_4bit=True,
            bnb_4bit_quant_type=quantization,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        load_kwargs["quantization_config"] = bnb_config

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        trust_remote_code=True,
        **load_kwargs,
    )
    return tokenizer, model


def _apply_lora(
    model: Any,
    *,
    lora_rank: int,
    quantization: Quantization,
    target_modules: Sequence[str],
) -> Any:
    """Attach a rank=``lora_rank`` LoRA adapter to ``model`` (CS-5 / CS-9)."""
    from peft import (  # noqa: PLC0415
        LoraConfig,
        get_peft_model,
        prepare_model_for_kbit_training,
    )

    if quantization in {"nf4", "fp4"}:
        model = prepare_model_for_kbit_training(  # type: ignore[no-untyped-call,unused-ignore]
            model,
            use_gradient_checkpointing=True,
        )
    else:
        model.gradient_checkpointing_enable()
    model.config.use_cache = False

    lora_config = LoraConfig(
        r=lora_rank,
        lora_alpha=lora_rank * 2,
        target_modules=list(target_modules),
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    peft_model: Any = get_peft_model(model, lora_config)
    if hasattr(peft_model, "print_trainable_parameters"):
        peft_model.print_trainable_parameters()
    return peft_model


def _run_trainer(
    *,
    model: Any,
    tokenizer: Any,
    examples: list[dict[str, str]],
    output_dir_path: Path,
    quantization: Quantization,
    batch_size: int,
    gradient_accumulation_steps: int,
    max_seq_length: int,
    max_steps: int,
    learning_rate: float,
    save_steps: int,
    seed: int,
) -> tuple[int, float | None]:
    """Drive the HF Trainer loop + save adapter.

    Returns ``(peak_vram_bytes, train_loss)`` so the caller can stamp
    them into :class:`TrainRunSummary` without re-importing torch.
    """
    import torch  # noqa: PLC0415
    from datasets import Dataset  # noqa: PLC0415
    from transformers import (  # noqa: PLC0415
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
        set_seed,
    )

    set_seed(seed)

    dataset = Dataset.from_list(examples)

    def _tokenize(batch: dict[str, list[str]]) -> dict[str, list[list[int]]]:
        encoded = tokenizer(
            batch["text"],
            truncation=True,
            max_length=max_seq_length,
            padding=False,
        )
        encoded["labels"] = [list(ids) for ids in encoded["input_ids"]]
        return encoded

    tokenized = dataset.map(
        _tokenize,
        batched=True,
        remove_columns=dataset.column_names,
    )

    training_args = TrainingArguments(
        output_dir=str(output_dir_path),
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        learning_rate=learning_rate,
        max_steps=max_steps,
        save_steps=save_steps,
        save_total_limit=2,
        logging_steps=10,
        bf16=True,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        optim=("paged_adamw_8bit" if quantization in {"nf4", "fp4"} else "adamw_torch"),
        report_to=[],
        seed=seed,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
    )

    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized,
        data_collator=collator,
    )

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()

    train_result = trainer.train()
    peak_vram = (
        int(torch.cuda.max_memory_allocated()) if torch.cuda.is_available() else 0
    )
    train_loss = (
        float(train_result.training_loss)
        if train_result is not None and hasattr(train_result, "training_loss")
        else None
    )

    trainer.model.save_pretrained(str(output_dir_path))
    tokenizer.save_pretrained(str(output_dir_path))
    return peak_vram, train_loss


def _execute_training_run(
    *,
    examples: list[dict[str, str]],
    output_dir_path: Path,
    summary: TrainRunSummary,
    base_model: str,
    lora_rank: int,
    quantization: Quantization,
    batch_size: int,
    gradient_accumulation_steps: int,
    max_seq_length: int,
    max_steps: int,
    learning_rate: float,
    save_steps: int,
    target_modules: Sequence[str],
    seed: int,
) -> None:
    """Run the full GPU-side pipeline and update ``summary`` in place.

    Split out of :func:`train_kant_lora` so the orchestrator stays
    below the cyclomatic-complexity thresholds without scattering the
    CS-4 / CS-5 / CS-6 steps.
    """
    tokenizer, model = _load_quantised_model(base_model, quantization)
    model = _apply_lora(
        model,
        lora_rank=lora_rank,
        quantization=quantization,
        target_modules=target_modules,
    )

    peak_vram, train_loss = _run_trainer(
        model=model,
        tokenizer=tokenizer,
        examples=examples,
        output_dir_path=output_dir_path,
        quantization=quantization,
        batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        max_seq_length=max_seq_length,
        max_steps=max_steps,
        learning_rate=learning_rate,
        save_steps=save_steps,
        seed=seed,
    )

    summary.training_executed = True
    summary.peak_vram_bytes = peak_vram
    summary.train_loss = train_loss

    # Audit trail: same shape as the dry-run return value, persisted so
    # the SGLang load step has a single file to consult.
    metadata_path = output_dir_path / "train_metadata.json"
    metadata_path.write_text(
        json.dumps(summary.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    _LOGGER.info(
        "train_kant_lora completed: persona=%s rank=%d quant=%s realised=%d"
        " peak_vram=%.2fGB train_loss=%s output=%s",
        summary.persona_id,
        lora_rank,
        quantization,
        summary.realised_examples,
        peak_vram / (1024**3) if peak_vram else 0.0,
        train_loss,
        output_dir_path,
    )

    # Touch ``HF_HUB_DISABLE_TELEMETRY`` deterministically so a later
    # SGLang load picks up the same hub cache the trainer used (a prior
    # incident saw ``transformers`` defaults stake out an incompatible
    # cache layout when the env var was left unset).
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m erre_sandbox.training.train_kant_lora",
        description=(
            "Phase β real Kant LoRA training entry"
            " (m9-c-spike CS-3/CS-4/CS-5/CS-6). Use --dry-run to exercise"
            " the gate without importing the GPU stack."
        ),
    )
    parser.add_argument(
        "--persona",
        dest="persona",
        default="kant",
        help="Persona id (default: kant - the only persona supported in this spike)",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--duckdb-glob",
        dest="duckdb_glob",
        help="Glob pattern resolving to one or more golden DuckDB files",
    )
    source.add_argument(
        "--db-path",
        dest="db_path",
        action="append",
        type=Path,
        help=(
            "Explicit DuckDB path (repeatable). Use this when shells fail"
            " to expand globs (Windows PowerShell)."
        ),
    )
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        type=Path,
        required=True,
        help="PEFT adapter output directory (also consumed by SGLang)",
    )
    parser.add_argument(
        "--base-model",
        dest="base_model",
        default=DEFAULT_BASE_MODEL,
        help=f"HuggingFace base model id (default: {DEFAULT_BASE_MODEL})",
    )
    parser.add_argument(
        "--rank",
        dest="rank",
        type=int,
        default=DEFAULT_LORA_RANK,
        help=f"LoRA rank (default: {DEFAULT_LORA_RANK}, CS-5)",
    )
    parser.add_argument(
        "--quantization",
        dest="quantization",
        choices=["nf4", "fp4", "none"],
        default="nf4",
        help="4-bit quantisation type (default: nf4, CS-4)",
    )
    parser.add_argument(
        "--batch-size",
        dest="batch_size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Per-device train batch size (default: {DEFAULT_BATCH_SIZE}, CS-4)",
    )
    parser.add_argument(
        "--gradient-accumulation",
        dest="gradient_accumulation",
        type=int,
        default=DEFAULT_GRADIENT_ACCUMULATION,
        help=(
            f"Gradient accumulation steps (default:"
            f" {DEFAULT_GRADIENT_ACCUMULATION}, CS-4)"
        ),
    )
    parser.add_argument(
        "--max-seq-length",
        dest="max_seq_length",
        type=int,
        default=DEFAULT_MAX_SEQ_LENGTH,
        help=f"Token sequence cap (default: {DEFAULT_MAX_SEQ_LENGTH}, CS-4)",
    )
    parser.add_argument(
        "--max-steps",
        dest="max_steps",
        type=int,
        default=DEFAULT_MAX_STEPS,
        help=f"HF Trainer max_steps (default: {DEFAULT_MAX_STEPS})",
    )
    parser.add_argument(
        "--learning-rate",
        dest="learning_rate",
        type=float,
        default=DEFAULT_LEARNING_RATE,
        help=f"AdamW peak LR (default: {DEFAULT_LEARNING_RATE})",
    )
    parser.add_argument(
        "--save-steps",
        dest="save_steps",
        type=int,
        default=DEFAULT_SAVE_STEPS,
        help=f"Checkpoint cadence (default: {DEFAULT_SAVE_STEPS})",
    )
    parser.add_argument(
        "--min-examples",
        dest="min_examples",
        type=int,
        default=DEFAULT_MIN_EXAMPLES,
        help=f"CS-3 gate threshold (default: {DEFAULT_MIN_EXAMPLES})",
    )
    parser.add_argument(
        "--seed",
        dest="seed",
        type=int,
        default=42,
        help="Reproducibility seed",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help=(
            "Run the gate only, then exit. No GPU stack import, no files"
            " written to output_dir. Useful for B-1/B-2 trigger verification."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help="Enable INFO-level logging on stderr",
    )
    return parser


def _resolve_paths(
    duckdb_glob: str | None,
    db_path: list[Path] | None,
) -> list[Path]:
    if db_path:
        return sorted(db_path)
    if duckdb_glob is None:  # pragma: no cover — argparse exclusive group prevents this
        raise FileNotFoundError(
            "train_kant_lora: neither --duckdb-glob nor --db-path supplied",
        )
    # ``Path.glob`` would require splitting the pattern from its anchor
    # which conflates ``data/eval/golden/kant_*.duckdb`` (anchored, common
    # case here) with ``**/kant_*.duckdb`` (unanchored); ``_glob.glob``
    # is the unambiguous tool for the CLI surface.
    matches = sorted(Path(p) for p in _glob.glob(duckdb_glob, recursive=True))  # noqa: PTH207
    if not matches:
        raise FileNotFoundError(
            f"train_kant_lora: --duckdb-glob {duckdb_glob!r} matched no files",
        )
    return matches


def main(argv: Sequence[str] | None = None) -> int:
    """Argparse-driven CLI entry point. Returns a POSIX exit code.

    The default exit codes follow ``decisions.md`` CS-3 — each gate
    error has a distinct rc so wrapping shell scripts can branch:

    * 0 — success (training run completed or dry-run gate cleared)
    * 2 — :class:`EvaluationContaminationError`
    * 3 — :class:`BlockerNotResolvedError`
    * 4 — :class:`InsufficientTrainingDataError`
    * 5 — other ``ValueError`` / ``FileNotFoundError`` (operator error)
    * 1 — unexpected exception (re-raised to surface stack trace)
    """
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )

    try:
        db_paths = _resolve_paths(args.duckdb_glob, args.db_path)
        summary = train_kant_lora(
            db_paths,
            args.output_dir,
            base_model=args.base_model,
            persona_id=args.persona,
            lora_rank=args.rank,
            quantization=args.quantization,
            batch_size=args.batch_size,
            gradient_accumulation_steps=args.gradient_accumulation,
            max_seq_length=args.max_seq_length,
            max_steps=args.max_steps,
            learning_rate=args.learning_rate,
            save_steps=args.save_steps,
            min_examples=args.min_examples,
            seed=args.seed,
            dry_run=args.dry_run,
        )
    except EvaluationContaminationError as exc:
        _LOGGER.error("contamination: %s", exc)  # noqa: TRY400  # rc mapping
        return 2
    except BlockerNotResolvedError as exc:
        _LOGGER.error("blocker not resolved: %s", exc)  # noqa: TRY400  # rc mapping
        return 3
    except InsufficientTrainingDataError as exc:
        _LOGGER.error("insufficient data: %s", exc)  # noqa: TRY400  # rc mapping
        return 4
    except (ValueError, FileNotFoundError) as exc:
        _LOGGER.error("operator error: %s", exc)  # noqa: TRY400  # rc mapping
        return 5

    # Emit a stable single-line summary on stdout so wrapping shell
    # captures can grep it without scraping log noise. ``print`` is the
    # right tool here (log noise is on stderr by design); T201 is
    # ``logging-only`` advisory and does not apply to CLI surface code.
    print(json.dumps(summary.to_dict(), sort_keys=True))  # noqa: T201
    return 0


__all__ = [
    "DEFAULT_BASE_MODEL",
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_GRADIENT_ACCUMULATION",
    "DEFAULT_LEARNING_RATE",
    "DEFAULT_LORA_RANK",
    "DEFAULT_MAX_SEQ_LENGTH",
    "DEFAULT_MAX_STEPS",
    "DEFAULT_MIN_EXAMPLES",
    "DEFAULT_SAVE_STEPS",
    "DEFAULT_TARGET_MODULES",
    "TrainRunSummary",
    "assert_phase_beta_ready",
    "main",
    "train_kant_lora",
]


if __name__ == "__main__":  # pragma: no cover — exercised via subprocess in tests
    sys.exit(main())
