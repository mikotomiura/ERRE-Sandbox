"""Training-layer exceptions for the m9-c-spike Phase β gate (CS-3).

Three error types govern the 4-種 hard-fail flow in
:func:`erre_sandbox.training.train_kant_lora.assert_phase_beta_ready`:

* :class:`EvaluationContaminationError` — re-exported from the
  contracts layer so callers in ``erre_sandbox.training`` and the
  test suite import a single canonical class. Defining a parallel type
  inside ``training`` would split the sentinel CI test set in two and
  is therefore explicitly forbidden by CS-3.
* :class:`BlockerNotResolvedError` — raised when the schema enforcement
  follow-up (DB11 / blocker B-1 ``m9-individual-layer-schema-add``)
  has not landed. The error message names the blocker so a silent skip
  is structurally impossible.
* :class:`InsufficientTrainingDataError` — raised when the realised
  per-persona example count (``len(build_examples(...))``) falls below
  the literature-derived ``min_examples`` threshold. Operational SLO
  (CS-3), not a literature constant — adjust per-spike scope only.
"""

from __future__ import annotations

from erre_sandbox.contracts.eval_paths import EvaluationContaminationError


class BlockerNotResolvedError(RuntimeError):
    """Phase β prerequisite blocker is still open (CS-3).

    Raised by :func:`assert_phase_beta_ready` when the training-view
    schema does not expose the ``individual_layer_enabled`` column. The
    column is added by the ``m9-individual-layer-schema-add`` follow-up
    (M9-eval-system blocker B-1 / DB11 enforcement); attempting to run
    Phase β real Kant training before that lands risks training on rows
    flagged for individual evaluation, which is a contamination class
    breach.

    Catching this exception without resolving the named blocker is a
    contract bug. The message includes the blocker task name so an
    accidental ``except`` clause cannot silently bypass the gate.

    Post-B-1 status (Codex LOW-1): once the schema-contract update has
    landed, the production ``connect_training_view()`` path will never
    raise this — :func:`erre_sandbox.evidence.eval_store.bootstrap_schema`
    materialises the column on every fresh DuckDB file. The Type and
    its regression test (``with_individual_layer_column=False`` mock
    fixture in ``tests/test_training/conftest.py``) are deliberately
    retained as a defence layer for non-bootstrap snapshots, legacy
    DuckDB artifacts produced before B-1 merged, and any future
    non-DuckDB :class:`RawTrainingRelation` implementations that might
    ship without the column. Removing this Type is a contract change,
    not a cleanup.
    """


class InsufficientTrainingDataError(ValueError):
    """Realised Kant example count falls below the gate threshold (CS-3).

    Raised by :func:`assert_phase_beta_ready` when
    ``len(build_examples(rows, persona_id="kant"))`` is below
    ``min_examples`` (default 1000, an operational SLO derived from
    P-Tailor / Anthropic persona vector / BIG5-CHAT prior art — see
    decisions.md CS-3 棄却).

    Recovery is data-driven, not code-driven: gather more dialog turns
    via the M9-eval P3 golden capture pipeline (blocker B-2) until the
    realised count clears the threshold. Lowering ``min_examples`` is a
    spike-scope override only and must be recorded as a CS-3 amendment.
    """


class InsufficientEffectiveSampleSizeError(ValueError):
    """Weighted training corpus N_eff falls below the Candidate C trigger (DA-14).

    Raised by the pre-training audit in
    :func:`erre_sandbox.training.train_kant_lora._pre_training_audit` when
    ``N_eff = (Σw)² / Σw² < 1000``. At that threshold the effective
    sample size is too small for stable LoRA training even with the
    signal-driven weighting — the variance of per-example contributions
    has overwhelmed the corpus.

    Recovery: STOP the run, record the audit in ``decisions.md`` D-1,
    and escalate to Candidate C (targeted +2500 de/en/≥60 hybrid
    collection) in a separate PR — Codex HIGH-A fallback path.

    The exception is mapped to CLI exit code **6** by
    :func:`erre_sandbox.training.train_kant_lora.main`.
    """


class WeightConcentrationError(ValueError):
    """Weighted training corpus top-5% mass concentration breaches DA-14.

    Raised by the pre-training audit in
    :func:`erre_sandbox.training.train_kant_lora._pre_training_audit` when
    ``top_5_pct_weight_share >= 0.50``. At that share the gradient is
    structurally dominated by ~5% of the corpus — equivalent to training
    on a few-hundred-example LoRA with the rest of the corpus along for
    the ride, defeating the signal-driven weighting's diversity intent.

    Recovery: STOP the run, record the audit in ``decisions.md`` D-1,
    and escalate to Candidate C (Codex HIGH-A fallback path).

    The exception is mapped to CLI exit code **7** by
    :func:`erre_sandbox.training.train_kant_lora.main`.
    """


__all__ = [
    "BlockerNotResolvedError",
    "EvaluationContaminationError",
    "InsufficientEffectiveSampleSizeError",
    "InsufficientTrainingDataError",
    "WeightConcentrationError",
]
