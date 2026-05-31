"""Tier A psycholinguistic metrics for the M9 evaluation system.

The five Tier A metrics are pure post-hoc functions over collected
``raw_dialog`` rows (DB6: never on the live inference path). Sub-module
layout:

* :mod:`burrows` — z-scored function-word L1 (Manhattan) Delta, in
  the canonical R-stylo formulation.
* :mod:`mattr` — Moving Average Type-Token Ratio (window 100).
* :mod:`nli` — DeBERTa-v3-base-mnli zero-shot contradiction.
* :mod:`novelty` — MPNet semantic novelty (cosine distance to running
  prior centroid).
* :mod:`empath_proxy` — Empath secondary diagnostic. Used as a Tier A
  psycholinguistic axis only; not a Big5 estimator (ME-1 / DB10).

Each metric exposes a single pure ``compute_*`` function plus an
optional injection point (``scorer`` / ``encoder`` / ``analyzer``) so
unit tests can stub the heavy ML model. The default loader for the
heavy path lives behind a lazy import — installing the project without
``[eval]`` extras must not pull ``sentence-transformers`` or
``transformers`` into resolution.
"""

from __future__ import annotations

from erre_sandbox.evidence.tier_a.burrows import (
    BurrowsLanguageMismatchError,
    BurrowsReference,
    compute_burrows_delta,
    tokenise_ja,
)
from erre_sandbox.evidence.tier_a.empath_proxy import compute_empath_proxy
from erre_sandbox.evidence.tier_a.mattr import compute_mattr
from erre_sandbox.evidence.tier_a.nli import compute_nli_contradiction
from erre_sandbox.evidence.tier_a.novelty import compute_semantic_novelty

__all__ = [
    "BurrowsLanguageMismatchError",
    "BurrowsReference",
    "compute_burrows_delta",
    "compute_empath_proxy",
    "compute_mattr",
    "compute_nli_contradiction",
    "compute_semantic_novelty",
    "tokenise_ja",
]
