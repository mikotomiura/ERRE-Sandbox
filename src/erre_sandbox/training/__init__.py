"""LoRA fine-tuning pipeline for the m9-c-spike (Kant rank=8 bounded run).

Public surface (m9-c-spike Phase I, decisions.md CS-3 / CS-4 / CS-5 / CS-6):

* :class:`BlockerNotResolvedError` — raised when the DB11 follow-up (B-1)
  has not landed and the training-view schema lacks the
  ``individual_layer_enabled`` column. Phase β cannot proceed silently.
* :class:`InsufficientTrainingDataError` — raised when realised Kant
  example count falls below the literature-derived ``min_examples``
  threshold (CS-3, currently 1000).
* :data:`EvaluationContaminationError` — re-export of the contracts-layer
  error, returned for ``epoch_phase=evaluation`` rows or
  ``individual_layer_enabled=True`` rows that surface through the
  training-egress view.
* :func:`build_chatml_prompt` — assemble a ChatML-formatted training
  string from a persona id + utterance pair (CS-6: PEFT default save
  expects ChatML when ``task_type=CAUSAL_LM``).
* :func:`build_examples` — raw_dialog rows → ``[{"text": chatml}, ...]``
  list ready for HuggingFace ``datasets.Dataset.from_list``.
* :func:`assert_phase_beta_ready` — 4-種 hard-fail gate (CS-3) that must
  pass before :func:`train_kant_lora` is permitted to consume real data.
* :func:`train_kant_lora` — Phase K β CLI entry. peft / transformers /
  accelerate / bitsandbytes / datasets are imported lazily inside the
  function body so module import stays free of GPU-stack dependencies.

Layer dependency (architecture-rules skill):

* allowed: ``erre_sandbox.contracts``, ``erre_sandbox.evidence`` (only
  ``connect_training_view`` for production callers), ``pydantic``,
  stdlib, ``[training]`` extras (lazy)
* forbidden: ``erre_sandbox.inference``, ``memory``, ``cognition``,
  ``world``, ``ui``, GPL libraries (peft / transformers / etc. are
  Apache-2.0 / MIT — confirmed)

Phase β (real Kant training) only fires after blockers B-1
(``m9-individual-layer-schema-add``) and B-2 (M9-eval P3 採取) clear; the
gate function ships in this PR but ``train_kant_lora()`` is a deliberate
no-op skeleton until both blockers resolve.
"""

from erre_sandbox.training.dataset import build_examples
from erre_sandbox.training.exceptions import (
    BlockerNotResolvedError,
    EvaluationContaminationError,
    InsufficientTrainingDataError,
)
from erre_sandbox.training.prompt_builder import (
    KANT_SYSTEM_PROMPT,
    build_chatml_prompt,
)
from erre_sandbox.training.train_kant_lora import (
    assert_phase_beta_ready,
    train_kant_lora,
)

__all__ = [
    "KANT_SYSTEM_PROMPT",
    "BlockerNotResolvedError",
    "EvaluationContaminationError",
    "InsufficientTrainingDataError",
    "assert_phase_beta_ready",
    "build_chatml_prompt",
    "build_examples",
    "train_kant_lora",
]
