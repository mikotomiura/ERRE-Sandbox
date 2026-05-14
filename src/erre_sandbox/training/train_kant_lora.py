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
from typing import TYPE_CHECKING, Any, Final, Literal, cast

from erre_sandbox.contracts.eval_paths import INDIVIDUAL_LAYER_ENABLED_KEY
from erre_sandbox.training.dataset import build_examples, build_weighted_examples
from erre_sandbox.training.example_features import classify_shard
from erre_sandbox.training.exceptions import (
    BlockerNotResolvedError,
    EvaluationContaminationError,
    InsufficientEffectiveSampleSizeError,
    InsufficientTrainingDataError,
    WeightConcentrationError,
)
from erre_sandbox.training.weighting import (
    compute_example_weight,
    emit_weight_audit,
    normalise_weights_to_mean_one,
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

DEFAULT_EVAL_SPLIT_FRACTION: Final[float] = 0.10
"""Group-aware validation split fraction for retrain v2 (Codex HIGH-A #1)."""

DEFAULT_SYNTHETIC_MONOLOG_HARD_CAP: Final[int] = 500
"""Hard upper bound on synthetic monolog rows (Codex MEDIUM-3).

The spec target is ~150-300; the hard cap is a defensive ceiling that fires
if the Kant-N-Kant pattern detector finds more pairs than expected (e.g.
because the natural shards became larger after a future P3+ collection).
Excess pairs are subsampled with seed-stable RNG, preserving determinism.
"""

DA14_N_EFF_FALLBACK_TRIGGER: Final[float] = 1000.0
"""Audit threshold below which the Candidate C fallback fires (DA-14)."""

DA14_TOP_5_PCT_FALLBACK_TRIGGER: Final[float] = 0.50
"""Top-5% weight mass concentration above which the Candidate C fallback fires."""

DA14_DE_EN_SOFT_WARNING_THRESHOLD: Final[float] = 0.60
"""Combined de+en weighted-mass below which a soft warning is logged."""

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

    Retrain v2 additions (DA-14): ``weighted``, ``weight_audit_path``,
    ``synthetic_monolog_n``, ``eval_split_size``, ``train_dialog_ids_n``,
    ``eval_dialog_ids_n``, ``eval_loss``. All default to None/0/False so
    the K-β baseline path remains shape-compatible with this struct.
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
    weighted: bool = False
    weight_audit_path: str | None = None
    synthetic_monolog_n: int = 0
    eval_split_size: int = 0
    train_dialog_ids_n: int = 0
    eval_dialog_ids_n: int = 0
    eval_loss: float | None = None

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
            "weighted": self.weighted,
            "weight_audit_path": self.weight_audit_path,
            "synthetic_monolog_n": self.synthetic_monolog_n,
            "eval_split_size": self.eval_split_size,
            "train_dialog_ids_n": self.train_dialog_ids_n,
            "eval_dialog_ids_n": self.eval_dialog_ids_n,
            "eval_loss": self.eval_loss,
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
# Retrain v2 data prep — group-aware split, monolog re-cast, audit
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class WeightedSplitResult:
    """Output of :func:`_collect_from_shards_weighted` (DA-14 retrain v2).

    Carries everything :func:`_execute_training_run_weighted` needs to drive
    the WeightedTrainer loop: ChatML payloads, normalised weights, weight
    metadata for the audit, the eval split, and a structured audit dict
    that the pre-training fallback trigger consumes.
    """

    train_examples: list[
        dict[str, object]
    ]  # {"text", "sample_weight", "weight_metadata"}
    eval_examples: list[dict[str, object]]
    shard_stats: list[_DuckDBShardStat]
    realised_examples: int
    synthetic_monolog_n: int
    train_dialog_ids: set[tuple[str, str]]  # (source_shard, dialog_id)
    eval_dialog_ids: set[tuple[str, str]]
    audit: dict[str, object]


def _get_git_sha() -> str:
    """Return the current git HEAD short SHA, or ``"unknown"`` on failure.

    Used to stamp ``synthesised_at_commit`` into synthetic monolog
    metadata (Codex MEDIUM-3 provenance). Subprocess is the cheapest
    pure-stdlib way to read the SHA without taking a GitPython dependency.
    """
    import subprocess  # noqa: PLC0415 — only used by this helper

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607 — static command
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        return "unknown"
    return result.stdout.strip() or "unknown"


def _make_synthetic_monologs(  # noqa: C901, PLR0912, PLR0915 — sequential pattern scan, complexity tracks the spec
    all_rows_by_shard: dict[str, list[dict[str, object]]],
    train_group_keys: set[tuple[str, str]],
    *,
    persona_id: str,
    use_real_tokenizer: bool,
    hard_cap: int,
    seed: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Detect Kant-N-Kant patterns and emit synthetic monolog rows (Codex MEDIUM-3).

    For each natural shard in ``all_rows_by_shard``, walk the rows in
    ``(dialog_id, turn_index)`` order looking for the pattern

        speaker_persona_id sequence: kant → (anyone-not-kant) → kant

    over three consecutive turn_index values ``(k, k+1, k+2)``. When the
    middle row's group key is in ``train_group_keys`` (Codex MEDIUM-3:
    monolog re-cast must derive from training-side rows only), concatenate
    the two Kant utterances into a single synthetic monolog with
    ``addressee=None`` and a ``_mono`` dialog_id suffix.

    Args:
        all_rows_by_shard: Mapping of ``source_shard_basename -> [raw_row]``.
            Only natural shards (source_shard_type == "natural") are
            scanned; stimulus shards are excluded because stim turns are
            scripted prompts, not Kant authoring.
        train_group_keys: Set of ``(source_shard, dialog_id)`` tuples that
            belong to the training side of the group-aware split. Synthetic
            rows are only emitted for dialogs in this set.
        persona_id: Persona id (currently always ``"kant"``).
        use_real_tokenizer: Forwarded to :func:`build_weighted_examples`
            so token counts match the trainer's view.
        hard_cap: Subsample to this many rows if the detector finds more.
            Subsampling uses ``numpy.random.default_rng(seed)``.
        seed: Reproducibility seed for the subsample step.

    Returns:
        A tuple of (synthetic_examples, synthetic_metadata). The example
        list is shaped like :func:`build_weighted_examples`'s output but
        with ``weight_metadata.synthetic_source_dialog_id`` /
        ``synthetic_source_turn_indices`` / ``synthesised_at_commit`` fields
        attached and ``dialog_id`` set to ``"<orig>_mono"``.
    """
    import numpy as np  # noqa: PLC0415

    from erre_sandbox.training.prompt_builder import (  # noqa: PLC0415
        build_chatml_prompt,
    )

    git_sha = _get_git_sha()
    candidates: list[dict[str, object]] = []
    for shard_basename, rows in all_rows_by_shard.items():
        try:
            shard_type, _ = classify_shard(Path(shard_basename))
        except ValueError:
            _LOGGER.warning(
                "monolog re-cast: skipping unrecognised shard %r",
                shard_basename,
            )
            continue
        if shard_type != "natural":
            continue
        # Group rows by dialog_id, then sort by turn_index for sequence scan
        by_dialog: dict[str, list[dict[str, object]]] = {}
        for row in rows:
            d_id = str(row.get("dialog_id", ""))
            by_dialog.setdefault(d_id, []).append(row)
        for dialog_id, dlg_rows in by_dialog.items():
            group_key = (shard_basename, dialog_id)
            if group_key not in train_group_keys:
                continue
            try:
                dlg_rows.sort(key=lambda r: int(cast("int", r.get("turn_index", -1))))
            except (TypeError, ValueError):
                continue
            for i in range(len(dlg_rows) - 2):
                a, b, c = dlg_rows[i], dlg_rows[i + 1], dlg_rows[i + 2]
                if (
                    a.get("speaker_persona_id") == persona_id
                    and b.get("speaker_persona_id") != persona_id
                    and c.get("speaker_persona_id") == persona_id
                ):
                    a_utt = str(a.get("utterance", "")).strip()
                    c_utt = str(c.get("utterance", "")).strip()
                    if not a_utt or not c_utt:
                        continue
                    try:
                        a_idx = int(cast("int", a.get("turn_index", -1)))
                        c_idx = int(cast("int", c.get("turn_index", -1)))
                    except (TypeError, ValueError):
                        continue
                    candidates.append(
                        {
                            "source_shard": shard_basename,
                            "source_shard_type": shard_type,
                            "orig_dialog_id": dialog_id,
                            "turn_indices": [a_idx, c_idx],
                            "combined_utterance": f"{a_utt} {c_utt}",
                        }
                    )

    if len(candidates) > hard_cap:
        rng = np.random.default_rng(seed)
        indices = rng.choice(len(candidates), size=hard_cap, replace=False)
        candidates = [candidates[i] for i in sorted(indices)]

    from erre_sandbox.training.example_features import (  # noqa: PLC0415
        extract_example_metadata,
    )

    synthetic_examples: list[dict[str, object]] = []
    synthetic_metadata_only: list[dict[str, object]] = []
    for c in candidates:
        new_dialog_id = f"{c['orig_dialog_id']}_mono"
        synthetic_row = {
            "utterance": c["combined_utterance"],
            "addressee_persona_id": None,
            "speaker_persona_id": persona_id,
            "dialog_id": new_dialog_id,
            "turn_index": -1,  # synthetic; not a real turn position
            "epoch_phase": "training",
        }
        text = build_chatml_prompt(
            persona_id=persona_id,
            utterance=str(c["combined_utterance"]),
            addressee_persona_id=None,
        )
        metadata = extract_example_metadata(
            synthetic_row,
            source_shard=str(c["source_shard"]),
            source_shard_type=str(c["source_shard_type"]),
            use_real_tokenizer=use_real_tokenizer,
        )
        metadata["synthetic_source_dialog_id"] = c["orig_dialog_id"]
        metadata["synthetic_source_turn_indices"] = c["turn_indices"]
        metadata["synthesised_at_commit"] = git_sha
        metadata["is_synthetic_monolog"] = True
        synthetic_examples.append({"text": text, "weight_metadata": metadata})
        synthetic_metadata_only.append(metadata)
    return synthetic_examples, synthetic_metadata_only


def _collect_from_shards_weighted(  # noqa: C901 — orchestrator stays linear for spec readability
    db_paths: Sequence[Path],
    *,
    persona_id: str,
    min_examples: int,
    individual_layer_enabled_required: bool = True,
    seed: int = 42,
    eval_split_fraction: float = DEFAULT_EVAL_SPLIT_FRACTION,
    synthetic_monolog_hard_cap: int = DEFAULT_SYNTHETIC_MONOLOG_HARD_CAP,
    use_real_tokenizer: bool = False,
) -> WeightedSplitResult:
    """Retrain v2 corpus loader: group-aware split + monolog re-cast + audit.

    Pipeline:

    1. Per shard: load raw_dialog rows; classify shard type
       (natural/stimulus); build weighted examples (filter chain identical
       to :func:`build_examples`).
    2. Aggregate, run :func:`assert_phase_beta_ready` (CS-3 gate).
    3. Group examples by ``(source_shard, dialog_id)``; perform a
       stratified 90/10 random split (``numpy.random.default_rng(seed)``;
       stratification by ``source_shard_type`` so the train/eval ratio is
       preserved within natural and within stimulus).
    4. Scan natural shards for Kant-N-Kant patterns; emit synthetic
       monolog rows from training-side dialogs only (Codex MEDIUM-3).
    5. Compute raw weights for the train split (base + synthetic),
       normalise to mean=1.0 (HIGH-C #2), and emit the audit dict
       (HIGH-A #2).
    6. Hard-fail if ``train_dialog_ids ∩ eval_dialog_ids`` is non-empty.
    """
    from erre_sandbox.evidence.eval_store import (  # noqa: PLC0415
        connect_training_view,
    )

    all_rows_by_shard: dict[str, list[dict[str, object]]] = {}
    weighted_examples_by_shard: dict[str, list[dict[str, object]]] = {}
    shard_stats: list[_DuckDBShardStat] = []
    aggregated_rows: list[dict[str, object]] = []
    for shard_path in db_paths:
        relation = connect_training_view(shard_path)
        try:
            shard_rows = [dict(row) for row in relation.iter_rows()]
        finally:
            close = getattr(relation, "close", None)
            if callable(close):
                close()
        shard_basename = Path(shard_path).name
        try:
            shard_type, _run = classify_shard(Path(shard_path))
        except ValueError:
            shard_type = "unknown"
        shard_w_examples = build_weighted_examples(
            shard_rows,
            persona_id=persona_id,
            source_shard=shard_basename,
            source_shard_type=shard_type,
            use_real_tokenizer=use_real_tokenizer,
        )
        all_rows_by_shard[shard_basename] = shard_rows
        weighted_examples_by_shard[shard_basename] = shard_w_examples
        shard_stats.append(
            _DuckDBShardStat(
                path=Path(shard_path),
                raw_rows=len(shard_rows),
                persona_examples=len(shard_w_examples),
            ),
        )
        aggregated_rows.extend(shard_rows)

    # Gate (CS-3, applied to aggregate) — reuse the same _AggregateRelation
    # shape as the K-β path so contamination / SLO checks behave identically.
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

    # Group-aware stratified split
    train_group_keys, eval_group_keys = _group_aware_stratified_split(
        weighted_examples_by_shard,
        eval_split_fraction=eval_split_fraction,
        seed=seed,
    )

    if train_group_keys & eval_group_keys:
        raise RuntimeError(
            "_collect_from_shards_weighted: train and eval group keys overlap"
            f" ({len(train_group_keys & eval_group_keys)} shared); aborting"
            " before training to prevent contamination",
        )

    base_train: list[dict[str, object]] = []
    eval_examples: list[dict[str, object]] = []
    for shard_basename, examples in weighted_examples_by_shard.items():
        for ex in examples:
            metadata = ex["weight_metadata"]
            assert isinstance(metadata, dict)
            group_key = (shard_basename, str(metadata["dialog_id"]))
            if group_key in eval_group_keys:
                eval_examples.append(ex)
            else:
                base_train.append(ex)

    synthetic_examples, _synthetic_meta = _make_synthetic_monologs(
        all_rows_by_shard,
        train_group_keys,
        persona_id=persona_id,
        use_real_tokenizer=use_real_tokenizer,
        hard_cap=synthetic_monolog_hard_cap,
        seed=seed,
    )

    train_examples_unweighted = base_train + synthetic_examples
    raw_weights = [
        compute_example_weight(ex["weight_metadata"])  # type: ignore[arg-type]
        for ex in train_examples_unweighted
    ]
    normalised = normalise_weights_to_mean_one(raw_weights)
    train_examples: list[dict[str, object]] = []
    train_metadata_list: list[dict[str, object]] = []
    for ex, w in zip(train_examples_unweighted, normalised, strict=True):
        # weight metadata kept as-is for audit; sample_weight is added so
        # WeightedTrainer can pop it during compute_loss.
        train_examples.append(
            {
                "text": ex["text"],
                "sample_weight": float(w),
                "weight_metadata": ex["weight_metadata"],
            }
        )
        train_metadata_list.append(cast("dict[str, object]", ex["weight_metadata"]))

    # Eval examples carry sample_weight=1.0 so the WeightedTrainer's
    # compute_loss reduces to a standard (un-weighted) mean over the eval
    # batch (design.md S-5).
    for ex in eval_examples:
        ex["sample_weight"] = 1.0

    # Compute audit (written to disk in _pre_training_audit; this struct
    # mirrors what the JSON file will contain so the caller can apply
    # fallback-trigger checks without round-tripping through disk).
    audit_struct: dict[str, object] = {
        "n_train": len(train_examples),
        "n_eval": len(eval_examples),
        "synthetic_monolog_n": len(synthetic_examples),
        "weights": normalised,
        "metadata": train_metadata_list,
    }
    return WeightedSplitResult(
        train_examples=train_examples,
        eval_examples=eval_examples,
        shard_stats=shard_stats,
        realised_examples=realised,
        synthetic_monolog_n=len(synthetic_examples),
        train_dialog_ids=train_group_keys,
        eval_dialog_ids=eval_group_keys,
        audit=audit_struct,
    )


def _group_aware_stratified_split(
    weighted_examples_by_shard: dict[str, list[dict[str, object]]],
    *,
    eval_split_fraction: float,
    seed: int,
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """Stratified random split of dialog groups (Codex HIGH-A #1 + MEDIUM-2).

    Splits ``(source_shard, dialog_id)`` group keys into train and eval
    sets, stratified by ``source_shard_type`` ("natural" / "stimulus") so
    the eval split keeps the natural-vs-stimulus ratio of the corpus.
    """
    import numpy as np  # noqa: PLC0415

    rng = np.random.default_rng(seed)
    by_stratum: dict[str, list[tuple[str, str]]] = {}
    for shard_basename, examples in weighted_examples_by_shard.items():
        seen: set[tuple[str, str]] = set()
        for ex in examples:
            metadata = ex["weight_metadata"]
            assert isinstance(metadata, dict)
            stratum = str(metadata["source_shard_type"])
            group_key = (shard_basename, str(metadata["dialog_id"]))
            if group_key in seen:
                continue
            seen.add(group_key)
            by_stratum.setdefault(stratum, []).append(group_key)

    train_keys: set[tuple[str, str]] = set()
    eval_keys: set[tuple[str, str]] = set()
    for stratum, keys in by_stratum.items():
        keys_arr = np.array(keys, dtype=object)
        if len(keys_arr) == 0:
            continue
        rng.shuffle(keys_arr)
        n_eval = max(1, round(eval_split_fraction * len(keys_arr)))
        # Ensure at least one train key remains
        n_eval = min(n_eval, len(keys_arr) - 1) if len(keys_arr) > 1 else 0
        for i, k in enumerate(keys_arr):
            tup_raw = k.tolist() if hasattr(k, "tolist") else list(k)
            tup: tuple[str, str] = (str(tup_raw[0]), str(tup_raw[1]))
            if i < n_eval:
                eval_keys.add(tup)
            else:
                train_keys.add(tup)
        _LOGGER.info(
            "split stratum=%s n_train=%d n_eval=%d",
            stratum,
            len(keys_arr) - n_eval,
            n_eval,
        )
    return train_keys, eval_keys


def _audit_de_en_mass(audit: dict[str, object]) -> float:
    """Extract de+en combined weighted mass from an audit dict.

    Encapsulates the nested ``audit["per_language_weighted_mass"]["de"|"en"]``
    access so the type narrowing happens in one place rather than every
    summary-building site.
    """
    lang_mass_obj = audit.get("per_language_weighted_mass", {})
    if not isinstance(lang_mass_obj, dict):
        return 0.0
    de = float(cast("float", lang_mass_obj.get("de", 0.0)))
    en = float(cast("float", lang_mass_obj.get("en", 0.0)))
    return de + en


def _pre_training_audit(
    weighted_split: WeightedSplitResult,
    *,
    output_dir: Path,
) -> tuple[Path, dict[str, object]]:
    """Materialise weight-audit.json and apply DA-14 fallback triggers.

    Returns ``(audit_path, audit_dict)``. Raises
    :class:`InsufficientEffectiveSampleSizeError` (exit 6) or
    :class:`WeightConcentrationError` (exit 7) when the audit breaches
    the DA-14 thresholds. A soft warning is logged when de+en weighted
    mass falls below 60% (training continues).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    audit_path = output_dir / "weight-audit.json"
    audit = emit_weight_audit(
        weights=weighted_split.audit["weights"],  # type: ignore[arg-type]
        metadata=weighted_split.audit["metadata"],  # type: ignore[arg-type]
        output_path=audit_path,
    )

    n_eff = float(audit.get("n_eff", 0.0))  # type: ignore[arg-type]
    top_5_share = float(audit.get("top_5_pct_weight_share", 0.0))  # type: ignore[arg-type]
    lang_mass = audit.get("per_language_weighted_mass", {})
    assert isinstance(lang_mass, dict)
    de_en_mass = float(lang_mass.get("de", 0.0)) + float(lang_mass.get("en", 0.0))

    _LOGGER.info(
        "weight audit: n_eff=%.1f top_5%%=%.3f de+en=%.3f synthetic_n=%d",
        n_eff,
        top_5_share,
        de_en_mass,
        weighted_split.synthetic_monolog_n,
    )

    if n_eff < DA14_N_EFF_FALLBACK_TRIGGER:
        raise InsufficientEffectiveSampleSizeError(
            f"pre-training audit: N_eff={n_eff:.1f} < DA-14 fallback trigger"
            f" {DA14_N_EFF_FALLBACK_TRIGGER:.0f}; STOP and escalate to Candidate C"
            f" (targeted +2500 de/en/≥60 hybrid collection)",
        )
    if top_5_share >= DA14_TOP_5_PCT_FALLBACK_TRIGGER:
        raise WeightConcentrationError(
            f"pre-training audit: top 5% weight share={top_5_share:.3f}"
            f" >= DA-14 fallback trigger {DA14_TOP_5_PCT_FALLBACK_TRIGGER:.2f};"
            f" STOP and escalate to Candidate C",
        )
    if de_en_mass < DA14_DE_EN_SOFT_WARNING_THRESHOLD:
        _LOGGER.warning(
            "pre-training audit: de+en weighted mass=%.3f below soft warning"
            " threshold %.2f; continuing training but flag in train_metadata",
            de_en_mass,
            DA14_DE_EN_SOFT_WARNING_THRESHOLD,
        )
    return audit_path, audit


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
    weighted: bool = False,
    use_real_tokenizer_for_weights: bool = True,
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
        weighted: Retrain v2 path (DA-14). When ``True``, the corpus is
            split via :func:`_collect_from_shards_weighted` (group-aware
            90/10 stratified), monolog re-cast is applied to training
            groups, per-example sample weights are computed and
            normalised, and a ``weight-audit.json`` is emitted. Pre-
            training fallback triggers (N_eff < 1000 / top-5%% concentration
            >= 50%) raise distinct exceptions mapped to exit codes 6 / 7.
        use_real_tokenizer_for_weights: Forwarded to weight-metadata
            extraction. Defaults to ``True`` so production weights reflect
            the actual Qwen3-8B tokenisation (Codex MEDIUM-1 caveat).
            Tests / dry-runs may set this to ``False`` for determinism.

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

    if weighted:
        return _run_weighted_path(
            resolved_paths=resolved_paths,
            output_dir_path=output_dir_path,
            base_model=base_model,
            persona_id=persona_id,
            lora_rank=lora_rank,
            quantization=quantization,
            batch_size=batch_size,
            gradient_accumulation_steps=gradient_accumulation_steps,
            max_seq_length=max_seq_length,
            max_steps=max_steps,
            learning_rate=learning_rate,
            save_steps=save_steps,
            min_examples=min_examples,
            target_modules=target_modules,
            seed=seed,
            dry_run=dry_run,
            use_real_tokenizer_for_weights=use_real_tokenizer_for_weights,
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


def _run_weighted_path(
    *,
    resolved_paths: list[Path],
    output_dir_path: Path,
    base_model: str,
    persona_id: str,
    lora_rank: int,
    quantization: Quantization,
    batch_size: int,
    gradient_accumulation_steps: int,
    max_seq_length: int,
    max_steps: int,
    learning_rate: float,
    save_steps: int,
    min_examples: int,
    target_modules: Sequence[str],
    seed: int,
    dry_run: bool,
    use_real_tokenizer_for_weights: bool,
) -> TrainRunSummary:
    """DA-14 retrain v2 weighted path (signal-driven + monolog re-cast + audit).

    Encapsulates the new pipeline so :func:`train_kant_lora`'s K-β path
    remains untouched. Always builds ``output_dir_path`` (the audit JSON
    must be inspectable even on dry-run).
    """
    output_dir_path.mkdir(parents=True, exist_ok=True)

    split = _collect_from_shards_weighted(
        resolved_paths,
        persona_id=persona_id,
        min_examples=min_examples,
        seed=seed,
        use_real_tokenizer=use_real_tokenizer_for_weights,
    )

    audit_path, audit = _pre_training_audit(split, output_dir=output_dir_path)

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
        realised_examples=split.realised_examples,
        output_dir=str(output_dir_path),
        db_paths=[str(p) for p in resolved_paths],
        shard_stats=[
            {
                "path": str(s.path),
                "raw_rows": s.raw_rows,
                "persona_examples": s.persona_examples,
            }
            for s in split.shard_stats
        ],
        training_executed=False,
        metadata={
            "target_modules": list(target_modules),
            "seed": seed,
            "audit_n_eff": audit.get("n_eff"),
            "audit_top_5_pct": audit.get("top_5_pct_weight_share"),
            "audit_de_en_mass": _audit_de_en_mass(audit),
        },
        weighted=True,
        weight_audit_path=str(audit_path),
        synthetic_monolog_n=split.synthetic_monolog_n,
        eval_split_size=len(split.eval_examples),
        train_dialog_ids_n=len(split.train_dialog_ids),
        eval_dialog_ids_n=len(split.eval_dialog_ids),
    )

    if dry_run:
        _LOGGER.info(
            "train_kant_lora dry-run (weighted): gate cleared with %d examples,"
            " %d synthetic monologs, %d eval rows; GPU stack not imported",
            split.realised_examples,
            split.synthetic_monolog_n,
            len(split.eval_examples),
        )
        return summary

    _execute_training_run_weighted(
        split=split,
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
# Retrain v2 GPU pipeline (WeightedTrainer + sample_weight collator)
# ---------------------------------------------------------------------------


def _run_trainer_weighted(
    *,
    model: Any,
    tokenizer: Any,
    train_examples: list[dict[str, object]],
    eval_examples: list[dict[str, object]],
    output_dir_path: Path,
    quantization: Quantization,
    batch_size: int,
    gradient_accumulation_steps: int,
    max_seq_length: int,
    max_steps: int,
    learning_rate: float,
    save_steps: int,
    seed: int,
) -> tuple[int, float | None, float | None]:
    """Drive the HF Trainer loop with per-example sample weights (DA-14).

    Returns ``(peak_vram_bytes, train_loss, eval_loss)``. The WeightedTrainer
    class is defined inside this function so ``transformers.Trainer`` import
    stays lazy (the gate-only path must remain installable without
    ``[training]`` extras — Codex HIGH-B guard).
    """
    import torch  # noqa: PLC0415
    from datasets import Dataset  # noqa: PLC0415
    from transformers import (  # noqa: PLC0415
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
        set_seed,
    )

    from erre_sandbox.training.weighting import (  # noqa: PLC0415
        compute_weighted_causal_lm_loss,
    )

    set_seed(seed)

    def _to_text_only(rows: list[dict[str, object]]) -> Dataset:
        """Strip weight_metadata so HF Dataset only carries text + sample_weight."""
        return Dataset.from_list(
            [{"text": r["text"], "sample_weight": r["sample_weight"]} for r in rows],
        )

    train_dataset = _to_text_only(train_examples)
    eval_dataset = _to_text_only(eval_examples) if eval_examples else None

    def _tokenize(batch: dict[str, list[Any]]) -> dict[str, list[Any]]:
        encoded = tokenizer(
            batch["text"],
            truncation=True,
            max_length=max_seq_length,
            padding=False,
        )
        encoded["labels"] = [list(ids) for ids in encoded["input_ids"]]
        encoded["sample_weight"] = list(batch["sample_weight"])
        return encoded

    tokenized_train = train_dataset.map(
        _tokenize,
        batched=True,
        remove_columns=train_dataset.column_names,
    )
    tokenized_eval = (
        eval_dataset.map(
            _tokenize,
            batched=True,
            remove_columns=eval_dataset.column_names,
        )
        if eval_dataset is not None
        else None
    )

    base_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    def _weighted_collator(features: list[dict[str, Any]]) -> dict[str, Any]:
        weights = [f.pop("sample_weight") for f in features]
        batch = base_collator(features)
        batch["sample_weight"] = torch.tensor(weights, dtype=torch.float32)
        return batch

    class WeightedTrainer(Trainer):  # type: ignore[misc,unused-ignore]
        """HF Trainer with per-example sample-weight aware compute_loss (HIGH-C)."""

        def compute_loss(  # type: ignore[no-untyped-def]
            self,
            model,
            inputs,
            return_outputs=False,  # noqa: FBT002
            num_items_in_batch=None,  # noqa: ARG002 — required for HF Trainer compat
        ):
            weights = inputs.pop("sample_weight")
            outputs = model(**inputs)
            weighted_loss = compute_weighted_causal_lm_loss(
                outputs.logits,
                inputs["labels"],
                weights,
            )
            return (weighted_loss, outputs) if return_outputs else weighted_loss

    eval_kwargs: dict[str, Any] = {}
    if tokenized_eval is not None:
        eval_kwargs = {
            "eval_strategy": "steps",
            "eval_steps": save_steps,
            "per_device_eval_batch_size": 1,  # HIGH-B guard: eval batch=1, loss-only
        }

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
        remove_unused_columns=False,  # keep sample_weight column
        **eval_kwargs,
    )

    trainer = WeightedTrainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_train,
        eval_dataset=tokenized_eval,
        data_collator=_weighted_collator,
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

    eval_loss: float | None = None
    if tokenized_eval is not None:
        try:
            metrics = trainer.evaluate()
        except (RuntimeError, ValueError) as exc:
            _LOGGER.warning("final evaluate() failed: %s", exc)
            metrics = {}
        eval_loss = float(metrics["eval_loss"]) if "eval_loss" in metrics else None

    trainer.model.save_pretrained(str(output_dir_path))
    tokenizer.save_pretrained(str(output_dir_path))
    return peak_vram, train_loss, eval_loss


def _execute_training_run_weighted(
    *,
    split: WeightedSplitResult,
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
    """Run the full GPU-side weighted pipeline and update ``summary`` in place."""
    tokenizer, model = _load_quantised_model(base_model, quantization)
    model = _apply_lora(
        model,
        lora_rank=lora_rank,
        quantization=quantization,
        target_modules=target_modules,
    )

    peak_vram, train_loss, eval_loss = _run_trainer_weighted(
        model=model,
        tokenizer=tokenizer,
        train_examples=split.train_examples,
        eval_examples=split.eval_examples,
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
    summary.eval_loss = eval_loss

    metadata_path = output_dir_path / "train_metadata.json"
    metadata_path.write_text(
        json.dumps(summary.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    _LOGGER.info(
        "train_kant_lora (weighted) completed: persona=%s rank=%d quant=%s"
        " realised=%d synthetic_n=%d peak_vram=%.2fGB train_loss=%s"
        " eval_loss=%s output=%s",
        summary.persona_id,
        lora_rank,
        quantization,
        summary.realised_examples,
        summary.synthetic_monolog_n,
        peak_vram / (1024**3) if peak_vram else 0.0,
        train_loss,
        eval_loss,
        output_dir_path,
    )

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
            " When combined with --weighted, the pre-training audit is still"
            " emitted to output_dir/weight-audit.json so the fallback trigger"
            " can be evaluated before the 3-5h training kickoff."
        ),
    )
    parser.add_argument(
        "--weighted",
        dest="weighted",
        action="store_true",
        help=(
            "Enable the DA-14 retrain v2 signal-driven path: per-example"
            " sample weights, group-aware 90/10 stratified split, monolog"
            " re-cast from training-side natural shards, and a pre-training"
            " audit. Falls back via exit code 6 (N_eff < 1000) or 7"
            " (top-5%% weight share >= 50%%) -- escalate to Candidate C."
        ),
    )
    parser.add_argument(
        "--no-real-tokenizer-for-weights",
        dest="no_real_tokenizer_for_weights",
        action="store_true",
        help=(
            "Use the whitespace × 1.3 token-count proxy instead of Qwen3-8B"
            " for weight metadata. Faster and deterministic for tests, but"
            " production runs should NOT pass this (Codex MEDIUM-1 caveat)."
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


def main(argv: Sequence[str] | None = None) -> int:  # noqa: PLR0911 — distinct exit-code paths
    """Argparse-driven CLI entry point. Returns a POSIX exit code.

    The default exit codes follow ``decisions.md`` CS-3 / DA-14 — each
    gate error has a distinct rc so wrapping shell scripts can branch:

    * 0 — success (training run completed or dry-run gate cleared)
    * 2 — :class:`EvaluationContaminationError`
    * 3 — :class:`BlockerNotResolvedError`
    * 4 — :class:`InsufficientTrainingDataError`
    * 5 — other ``ValueError`` / ``FileNotFoundError`` (operator error)
    * 6 — :class:`InsufficientEffectiveSampleSizeError` (DA-14 fallback)
    * 7 — :class:`WeightConcentrationError` (DA-14 fallback)
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
            weighted=args.weighted,
            use_real_tokenizer_for_weights=not args.no_real_tokenizer_for_weights,
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
    except InsufficientEffectiveSampleSizeError as exc:
        _LOGGER.error("audit N_eff fallback: %s", exc)  # noqa: TRY400
        return 6
    except WeightConcentrationError as exc:
        _LOGGER.error("audit top-5%% fallback: %s", exc)  # noqa: TRY400
        return 7
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
