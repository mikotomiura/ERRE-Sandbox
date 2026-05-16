"""Plan B (Candidate C hybrid retrain) achieved-corpus-stats gate.

Promoted from ``scripts/m9-c-adopt/audit_plan_b_corpus_stats.py`` into the
package so the gate logic lives next to the other DA-14 fallback triggers
(``InsufficientEffectiveSampleSizeError`` / ``WeightConcentrationError``).
The script form is a thin wrapper around :func:`audit_corpus` for the
G-GEAR collection runbook; the same function is invoked from
``train_kant_lora._handle_weighted_path`` when ``--plan-b-gate`` is set
(:ref:`design.md §1.3`).

Threshold rationale (``.steering/20260517-m9-c-adopt-plan-b-design/
decisions.md`` DI-3):

* ``n_eff >= 1500`` — existing DA-14 fallback target (1000 trigger, 1500
  goal), promoted to a hard floor under Plan B
* ``top_5_pct_weight_share <= 0.35`` — existing DA-14 goal, hard ceiling
  under Plan B
* ``de_en_mass >= 0.60`` — new Plan B axis; NOT a retroactive promotion
  of the DI-5 soft warning (which addressed v2 corpus shape pre-Plan B)
  but a forward-looking gate on the Plan B re-collected corpus
* ``de_mass >= 0.30`` — new Plan B axis, prevents an en free-rider from
  satisfying ``de_en_mass`` while leaving per-language signal undisturbed
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Final

# ---------------------------------------------------------------------------
# Thresholds (preregistered, design.md §1.3) — module-level constants only
# ---------------------------------------------------------------------------

N_EFF_MIN: Final[float] = 1500.0
TOP_5_PCT_MAX: Final[float] = 0.35
DE_EN_MASS_MIN: Final[float] = 0.60
DE_MASS_MIN: Final[float] = 0.30
GATE_FAIL_EXIT_CODE: Final[int] = 8
GATE_SCHEMA_VERSION: Final[int] = 1


def audit_corpus(
    weight_audit: dict[str, Any],
    *,
    weight_audit_path: str,
    merge_sha: str,
    n_eff_min: float = N_EFF_MIN,
    top_5_pct_max: float = TOP_5_PCT_MAX,
    de_en_mass_min: float = DE_EN_MASS_MIN,
    de_mass_min: float = DE_MASS_MIN,
) -> dict[str, Any]:
    """Apply the 4-axis Plan B gate to a parsed weight-audit dict.

    Pure function — IO and ``argparse`` plumbing live in the wrapper
    script. Returns the gate-verdict dict matching the
    ``plan-b-corpus-gate.json`` schema in ``design.md`` §1.3.

    Threshold kwargs are **deliberately retained on this pure function**
    so tests can exercise boundary behaviour without monkey-patching
    module-level constants. The production wrapper
    (``scripts/m9-c-adopt/audit_plan_b_corpus_stats.py``) and the
    ``train_kant_lora`` ``--plan-b-gate`` path BOTH bind the production
    constants here; neither exposes the kwargs as CLI flags (Codex
    review HIGH-2, design.md §1.3 — preregistered gates must not have
    an operator-facing way to move thresholds post-hoc).
    """
    n_eff = float(weight_audit.get("n_eff", 0.0))
    top_5 = float(weight_audit.get("top_5_pct_weight_share", 1.0))
    lang_mass_obj = weight_audit.get("per_language_weighted_mass", {})
    if not isinstance(lang_mass_obj, dict):
        lang_mass_obj = {}
    de_mass = float(lang_mass_obj.get("de", 0.0))
    en_mass = float(lang_mass_obj.get("en", 0.0))
    de_en_mass = de_mass + en_mass

    failed_axes: list[str] = []
    if n_eff < n_eff_min:
        failed_axes.append("n_eff")
    if top_5 > top_5_pct_max:
        failed_axes.append("top_5_pct")
    if de_en_mass < de_en_mass_min:
        failed_axes.append("de_en_mass")
    if de_mass < de_mass_min:
        failed_axes.append("de_mass")

    return {
        "schema_version": GATE_SCHEMA_VERSION,
        "plan_b_gate": "pass" if not failed_axes else "fail",
        "thresholds": {
            "n_eff_min": n_eff_min,
            "top_5_pct_max": top_5_pct_max,
            "de_en_mass_min": de_en_mass_min,
            "de_mass_min": de_mass_min,
        },
        "achieved": {
            "n_eff": n_eff,
            "top_5_pct_weight_share": top_5,
            "de_en_mass": de_en_mass,
            "de_mass": de_mass,
            "en_mass": en_mass,
        },
        "failed_axes": failed_axes,
        "weight_audit_path": weight_audit_path,
        "merge_sha": merge_sha,
        "captured_at_utc": datetime.now(UTC).isoformat(),
    }


__all__ = [
    "DE_EN_MASS_MIN",
    "DE_MASS_MIN",
    "GATE_FAIL_EXIT_CODE",
    "GATE_SCHEMA_VERSION",
    "N_EFF_MIN",
    "TOP_5_PCT_MAX",
    "audit_corpus",
]
