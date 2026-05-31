"""Tier B psychometric and diversity metrics for the M9 evaluation system.

The three Tier B sub-metric modules feed the DB9 quorum (M9-B
``decisions.md`` DB9): two-of-three of ``vendi_score`` /
``big5_stability_icc`` / ``burrows_delta_to_reference`` (Burrows lives in
``tier_a``) must move in the baseline-positive direction with the bootstrap
CI for LoRA adoption.

Sub-module layout:

* :mod:`vendi` — Vendi Score (Friedman & Dieng 2023). Default semantic
  kernel with a preregistered sensitivity panel for P4b (M9-eval ME-10).
* :mod:`ipip_neo` — IPIP-50 administering helper with anti-demand-
  characteristics design (M9-eval ME-12 / ME-13). English only in P4a;
  Japanese vendoring deferred to ``m9-eval-p4b-ja-ipip-vendoring``.
* :mod:`big5_icc` — McGraw-Wong ICC over per-window Big5 vectors. Dual
  consumer split: ``ICC(C,k)`` for ME-1 reliability fallback,
  ``ICC(A,1)`` for DB9 drift gate (M9-eval ME-11).

All public functions are pure post-hoc helpers over collected
``raw_dialog`` rows (DB6: never on the live inference path). Tier B is
eval-only; the DB11 ``individual_layer_enabled`` raw-schema enforcement
remains a separate required follow-up (see ``blockers.md``
``m9-individual-layer-schema-add``).

LIWC alternative honest framing (M9-B DB10 Option D): IPIP self-report
only — no LIWC equivalence claim, no external-lexicon Big5 inference.
Tier A ``empath_proxy`` is a separate psycholinguistic axis (ME-1 / DB10
Option D).
"""

from __future__ import annotations

from erre_sandbox.evidence.tier_b.big5_icc import (
    ME1_FALLBACK_LOWER_CI_THRESHOLD,
    ME1_FALLBACK_POINT_THRESHOLD,
    Big5ICCResult,
    TierBBootstrapPair,
    compute_big5_icc,
)
from erre_sandbox.evidence.tier_b.ipip_neo import (
    Big5Scores,
    DecoyItem,
    IPIPDiagnostic,
    IPIPItem,
    PersonaResponder,
    administer_ipip_neo,
    compute_ipip_diagnostic,
    get_default_decoys,
    get_ipip_50_items,
    render_item_prompt,
)
from erre_sandbox.evidence.tier_b.vendi import (
    DEFAULT_KERNEL_NAME,
    VendiKernel,
    VendiResult,
    compute_vendi,
    make_lexical_5gram_kernel,
    vendi_kernel_sensitivity_panel,
)
from erre_sandbox.evidence.tier_b.vendi_lexical_5gram import (
    LEXICAL_5GRAM_KERNEL_NAME,
    make_tfidf_5gram_cosine_kernel,
)

__all__ = [
    "DEFAULT_KERNEL_NAME",
    "LEXICAL_5GRAM_KERNEL_NAME",
    "ME1_FALLBACK_LOWER_CI_THRESHOLD",
    "ME1_FALLBACK_POINT_THRESHOLD",
    "Big5ICCResult",
    "Big5Scores",
    "DecoyItem",
    "IPIPDiagnostic",
    "IPIPItem",
    "PersonaResponder",
    "TierBBootstrapPair",
    "VendiKernel",
    "VendiResult",
    "administer_ipip_neo",
    "compute_big5_icc",
    "compute_ipip_diagnostic",
    "compute_vendi",
    "get_default_decoys",
    "get_ipip_50_items",
    "make_lexical_5gram_kernel",
    "make_tfidf_5gram_cosine_kernel",
    "render_item_prompt",
    "vendi_kernel_sensitivity_panel",
]
