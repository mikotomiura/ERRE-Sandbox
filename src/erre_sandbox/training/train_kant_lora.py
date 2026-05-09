"""Phase β real Kant LoRA training + 4-種 hard-fail gate (CS-3..CS-6).

Two public functions:

* :func:`assert_phase_beta_ready` — the 4-種 hard-fail gate. Pure Python
  + ``RawTrainingRelation`` Protocol consumer; no GPU-stack imports. The
  dependency injection signature (``relation: RawTrainingRelation``) lets
  the test suite exercise every failure mode without booting DuckDB or
  the allow-list lockstep check inside ``_DuckDBRawTrainingRelation``.
* :func:`train_kant_lora` — Phase β CLI entry. peft / transformers /
  accelerate / bitsandbytes / datasets are imported **lazily inside the
  function body** so the rest of ``erre_sandbox.training`` (and the
  ``assert_phase_beta_ready`` test suite) can be imported on a CI
  install with no ``[training]`` extras. The function is a deliberate
  no-op skeleton until blockers B-1 / B-2 clear; the inner training
  loop will be implemented in a follow-up Phase β PR after
  ``m9-individual-layer-schema-add`` lands and the M9-eval P3 golden
  capture completes (see ``.steering/20260508-m9-c-spike/blockers.md``).

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

from typing import TYPE_CHECKING, Final

from erre_sandbox.contracts.eval_paths import INDIVIDUAL_LAYER_ENABLED_KEY
from erre_sandbox.training.dataset import build_examples
from erre_sandbox.training.exceptions import (
    BlockerNotResolvedError,
    EvaluationContaminationError,
    InsufficientTrainingDataError,
)

if TYPE_CHECKING:
    from pathlib import Path

    from erre_sandbox.contracts.eval_paths import RawTrainingRelation


DEFAULT_MIN_EXAMPLES: Final[int] = 1000
"""Operational SLO for Phase β realised example count (CS-3).

Derived from P-Tailor / Anthropic persona vector / BIG5-CHAT prior art
(see ``.steering/20260508-m9-c-spike/decisions.md`` CS-3 ``棄却``).
Adjust per-spike scope only — production training thresholds belong in
M9-C-adopt scope, not this spike.
"""

_EVALUATION_PHASE_VALUE: Final[str] = "evaluation"


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
    #    realised-count check below sees the post-filter dataset. Use
    #    case-insensitive comparison so an upstream casing change
    #    ("Evaluation"/"EVALUATION") cannot sneak rows past the gate
    #    (CS-3 / security review MEDIUM-2).
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
        # Truthy check (not ``is True``) so non-bool truthy values (1,
        # "true", etc. that DuckDB may surface for a non-strict BOOLEAN
        # column) also trip the contamination guard
        # (CS-3 / security review MEDIUM-3).
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


def train_kant_lora(
    db_path: Path,
    output_dir: Path,
    *,
    base_model: str = "Qwen/Qwen3-8B",
    lora_rank: int = 8,
    min_examples: int = DEFAULT_MIN_EXAMPLES,
) -> None:
    """Phase β real Kant LoRA training entry (CS-4 / CS-5 / CS-6, skeleton).

    This function is the **production caller** that wraps
    :func:`assert_phase_beta_ready` around a real DuckDB-backed
    :class:`RawTrainingRelation`. It is intentionally a no-op skeleton in
    this PR — the actual peft / transformers / bitsandbytes loop will
    land in a follow-up Phase β PR once blockers B-1 and B-2 clear.

    Args:
        db_path: DuckDB file produced by the M9-eval P3 golden capture.
        output_dir: Where PEFT will save the adapter
            (``adapter_config.json`` + ``adapter_model.safetensors``).
            CS-6: this directory is loaded directly by SGLang via
            ``POST /load_lora_adapter``; no conversion script needed
            until / unless that direct-load path fails.
        base_model: HuggingFace base model id. Default ``Qwen/Qwen3-8B``
            matches CS-1 / CS-5 (rank=8 continuity hypothesis).
        lora_rank: LoRA rank. CS-5 fixes this at 8 for the spike;
            sweeping is M9-C-adopt scope.
        min_examples: Threshold passed through to
            :func:`assert_phase_beta_ready`.

    Raises:
        EvaluationContaminationError / BlockerNotResolvedError /
        InsufficientTrainingDataError: From the gate.
        NotImplementedError: Always raised in this PR. The skeleton is
            here so callers can wire ``train_kant_lora()`` invocations
            in CLI entry points and integration tests; the inner loop
            ships in a follow-up Phase β PR (B-1 / B-2 解消後).
    """
    # Lazy imports — keep peft / transformers / accelerate /
    # bitsandbytes / datasets out of module import so the rest of
    # erre_sandbox.training (and the gate test suite) imports clean on
    # the CI default install with no [training] extras.
    from erre_sandbox.evidence.eval_store import (  # noqa: PLC0415
        connect_training_view,
    )

    relation = connect_training_view(db_path)
    realised = assert_phase_beta_ready(
        relation,
        persona_id="kant",
        min_examples=min_examples,
        individual_layer_enabled_required=True,
    )
    raise NotImplementedError(
        "train_kant_lora skeleton — gate cleared with"
        f" {realised} examples for base_model={base_model!r}, rank={lora_rank},"
        f" output_dir={output_dir!s}, but the inner peft / transformers /"
        " bitsandbytes loop is deliberately deferred to a Phase β follow-up"
        " PR (blockers B-1 + B-2 must clear first; see"
        " .steering/20260508-m9-c-spike/blockers.md).",
    )


__all__ = [
    "DEFAULT_MIN_EXAMPLES",
    "assert_phase_beta_ready",
    "train_kant_lora",
]
