"""Unit tests for :mod:`erre_sandbox.training.weighting` (m9-c-adopt retrain v2).

Covers the three public surfaces (compute_example_weight, normalise_weights_to_mean_one,
emit_weight_audit) without importing any GPU stack. Maps to the 5 case suite
specified in ``.steering/20260514-m9-c-adopt-retrain-v2-impl/tasklist.md``.

DA-14 / Codex HIGH-C references:
* coefficients (0.35/0.20/0.15/0.30) are heuristic, not empirical (HIGH-C #3)
* weights normalised to mean=1.0 on the train split (HIGH-C #2)
* audit emits per-language weighted mass / top 5% share / N_eff (HIGH-A #2)
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from erre_sandbox.training.weighting import (
    WEIGHT_CLAMP_MAX,
    WEIGHT_CLAMP_MIN,
    compute_example_weight,
    emit_weight_audit,
    normalise_weights_to_mean_one,
)

# ---------------------------------------------------------------------------
# compute_example_weight (3 tests)
# ---------------------------------------------------------------------------


def test_compute_example_weight_clamp_range_upper() -> None:
    """Raw values above 3.0 are clamped to WEIGHT_CLAMP_MAX (HIGH-C clamp guard).

    Construct a metadata dict that drives every factor to its max so the
    weighted sum exceeds 3.0 by a wide margin. The function must clip,
    not panic, so gradient variance stays bounded.
    """
    metadata = {
        "language": "de",  # 1.4 * 0.35 = 0.49
        "token_count": 200,  # 2.0 * 0.20 = 0.40
        "has_addressee": False,  # 1.5 * 0.15 = 0.225 (monolog bonus)
        "marker_density_per_100_tokens": 50.0,  # 25.0 * 0.30 = 7.5 (way above clamp)
    }
    weight = compute_example_weight(metadata)
    assert weight == WEIGHT_CLAMP_MAX == 3.0


def test_compute_example_weight_kantian_de_120tok_monolog_max_marker() -> None:
    """High-signal Kant utterance lands at the upper clamp (HIGH-C verbatim spec).

    Mirrors the design-final §3.2 narrative: German, ≥120 tokens, monolog,
    high marker density → raw exceeds 3.0 and clamps to WEIGHT_CLAMP_MAX.
    """
    metadata = {
        "language": "de",
        "token_count": 120,
        "has_addressee": False,
        "marker_density_per_100_tokens": 20.0,
    }
    # raw = 1.4*0.35 + 2.0*0.20 + 1.5*0.15 + 10.0*0.30 = 0.49+0.40+0.225+3.0 = 4.115
    # clamped → 3.0
    weight = compute_example_weight(metadata)
    assert weight == WEIGHT_CLAMP_MAX


def test_compute_example_weight_ja_short_dialog_zero_marker() -> None:
    """Low-signal ja short-dialog row gets the formula's natural minimum.

    PR-5 β rebalance (DA-17 ADR / DP5-2 採用案 A1) で
    ``_LANG_FACTORS["ja"]`` を 0.2 → 0.05 に変更したため、本 fixture の
    practical minimum は ``0.05*0.35 + 0.3*0.20 + 1.0*0.15 + 0.2*0.30
    = 0.0175 + 0.06 + 0.15 + 0.06 = 0.2875`` に下がる。但し
    ``monolog_bonus`` (=1.0 for dialog) と ``marker_factor`` (=0.2 floor)
    が下支えするため、依然 ``WEIGHT_CLAMP_MIN=0.1`` には到達しない。
    (旧仕様 (`_LANG_FACTORS["ja"]=0.2`) の expected 0.34 は本 test の
    fixture を更新して新仕様 0.2875 に追随済)。
    """
    metadata = {
        "language": "ja",
        "token_count": 10,
        "has_addressee": True,
        "marker_density_per_100_tokens": 0.0,
    }
    # raw = 0.05*0.35 + 0.3*0.20 + 1.0*0.15 + 0.2*0.30
    #     = 0.0175 + 0.06 + 0.15 + 0.06 = 0.2875 (PR-5 β rebalance、A1)
    weight = compute_example_weight(metadata)
    assert math.isclose(weight, 0.2875, abs_tol=1e-9)
    # Sanity-check the practical minimum is above the absolute floor — the
    # clamp lower bound is structural defence, not an expected operating point.
    assert weight > WEIGHT_CLAMP_MIN


# ---------------------------------------------------------------------------
# normalise_weights_to_mean_one (1 test)
# ---------------------------------------------------------------------------


def test_normalise_weights_to_mean_one_preserves_relative_order() -> None:
    """Normalisation rescales to mean=1.0 without changing pairwise ratios.

    HIGH-C #2: without normalisation the formula silently shifts effective
    LR because the corpus-wide mean of the unnormalised weights is not 1.0.
    """
    raw = [0.5, 1.0, 1.5, 2.5]
    normalised = normalise_weights_to_mean_one(raw)
    # mean of normalised is exactly 1.0
    assert math.isclose(sum(normalised) / len(normalised), 1.0, abs_tol=1e-12)
    # pairwise ratios are preserved
    for a_raw, a_norm in zip(raw, normalised, strict=True):
        assert math.isclose(a_norm / a_raw, normalised[0] / raw[0], abs_tol=1e-9)
    # relative order preserved
    assert sorted(normalised) == normalised


# ---------------------------------------------------------------------------
# emit_weight_audit (1 test)
# ---------------------------------------------------------------------------


def test_emit_weight_audit_reports_lang_mass_and_n_eff(tmp_path: Path) -> None:
    """Audit emits per-language weighted mass, top 5% share, and N_eff.

    HIGH-A #2 acceptance criteria: audit must be inspectable before the
    training kickoff so a pathological distribution (ja-heavy / top-5%
    concentrated) can trip the Candidate C fallback before VRAM is touched.
    """
    weights = [1.0, 2.0, 3.0, 0.5, 0.5, 0.5, 0.5]  # mean=1.143, top1 = 3.0
    metadata = [
        {
            "language": "de",
            "token_count": 100,
            "has_addressee": False,
            "marker_density_per_100_tokens": 5.0,
        },
        {
            "language": "de",
            "token_count": 100,
            "has_addressee": False,
            "marker_density_per_100_tokens": 5.0,
        },
        {
            "language": "en",
            "token_count": 80,
            "has_addressee": True,
            "marker_density_per_100_tokens": 2.0,
        },
        {
            "language": "ja",
            "token_count": 20,
            "has_addressee": True,
            "marker_density_per_100_tokens": 0.0,
        },
        {
            "language": "ja",
            "token_count": 20,
            "has_addressee": True,
            "marker_density_per_100_tokens": 0.0,
        },
        {
            "language": "ja",
            "token_count": 20,
            "has_addressee": True,
            "marker_density_per_100_tokens": 0.0,
        },
        {
            "language": "mixed",
            "token_count": 50,
            "has_addressee": True,
            "marker_density_per_100_tokens": 1.0,
        },
    ]
    output_path = tmp_path / "weight-audit.json"
    audit = emit_weight_audit(weights, metadata, output_path=output_path)

    # 1) file written + round-trips to identical dict
    assert output_path.exists()
    on_disk = json.loads(output_path.read_text(encoding="utf-8"))
    assert on_disk == audit

    # 2) per-language weighted mass keys (all four classes present)
    lang_mass = audit["per_language_weighted_mass"]
    assert set(lang_mass.keys()) == {"de", "en", "ja", "mixed"}
    total = sum(weights)
    # de mass = (1.0 + 2.0) / total
    assert math.isclose(lang_mass["de"], 3.0 / total, abs_tol=1e-9)
    # ja mass = (0.5 * 3) / total
    assert math.isclose(lang_mass["ja"], 1.5 / total, abs_tol=1e-9)

    # 3) top 5% share — at 7 examples the top 5% is 1 example (ceil-style)
    # top1 weight 3.0 → share = 3.0 / total
    assert math.isclose(audit["top_5_pct_weight_share"], 3.0 / total, abs_tol=1e-9)

    # 4) N_eff = (Σw)² / Σw²
    n_eff_expected = (sum(weights) ** 2) / sum(w * w for w in weights)
    assert math.isclose(audit["n_eff"], n_eff_expected, abs_tol=1e-9)

    # 5) bucket histogram present
    assert "bucket_histogram" in audit
    assert isinstance(audit["bucket_histogram"], dict)
    # at least one bucket has a positive count
    assert sum(audit["bucket_histogram"].values()) == len(weights)

    # 6) descriptive stats present
    assert "weight_min" in audit
    assert "weight_p50" in audit
    assert "weight_p90" in audit
    assert "weight_max" in audit
    assert audit["weight_max"] == 3.0
    assert audit["weight_min"] == 0.5

    # 7) n_examples present
    assert audit["n_examples"] == len(weights)


def test_emit_weight_audit_rejects_length_mismatch(tmp_path: Path) -> None:
    """Weights / metadata length mismatch is a programming bug.

    Mismatched lengths cannot arise from correct upstream code, so
    ``emit_weight_audit`` raises rather than silently truncating.
    """
    output_path = tmp_path / "weight-audit.json"
    with pytest.raises(ValueError, match="length"):
        emit_weight_audit(
            [1.0, 2.0],
            [
                {
                    "language": "de",
                    "token_count": 100,
                    "has_addressee": False,
                    "marker_density_per_100_tokens": 1.0,
                }
            ],
            output_path=output_path,
        )


def _minimal_audit_input() -> tuple[list[float], list[dict[str, object]]]:
    """Return a 3-row weight/metadata pair sufficient for emit_weight_audit."""
    weights = [1.0, 2.0, 0.5]
    metadata: list[dict[str, object]] = [
        {
            "language": "de",
            "token_count": 100,
            "has_addressee": False,
            "marker_density_per_100_tokens": 5.0,
        },
        {
            "language": "en",
            "token_count": 80,
            "has_addressee": True,
            "marker_density_per_100_tokens": 2.0,
        },
        {
            "language": "ja",
            "token_count": 20,
            "has_addressee": True,
            "marker_density_per_100_tokens": 0.0,
        },
    ]
    return weights, metadata


def test_emit_weight_audit_persists_extra_fields_into_json(
    tmp_path: Path,
) -> None:
    """DEP1-3 fix (PR-7 follow-up, 2026-05-18): ``extra`` kwarg merges
    caller-supplied provenance fields (e.g. ``da18_hybrid``) into both
    the returned dict and the on-disk JSON.

    The merged JSON preserves all standard audit fields *and* exposes
    every extra key so a downstream reader (DA18-7 Gate 1 provenance
    binding) sees a single self-contained artefact.
    """
    weights, metadata = _minimal_audit_input()
    output_path = tmp_path / "weight-audit.json"
    da18_hybrid = {
        "ja_drop_ratio": 0.05,
        "ja_drop_seed": 42,
        "ja_pre_drop_count": 100,
        "ja_post_drop_count": 5,
        "en_booster_source": None,
        "en_booster_rows_total": 0,
        "en_booster_kant_count": 0,
        "en_booster_en_kept": 0,
    }
    another_provenance = {"label": "test-provenance-key", "id": 17}

    audit = emit_weight_audit(
        weights,
        metadata,
        output_path=output_path,
        extra={
            "da18_hybrid": da18_hybrid,
            "another_provenance": another_provenance,
        },
    )

    # Returned dict contains both standard fields and extras.
    assert audit["n_examples"] == len(weights)
    assert audit["da18_hybrid"] == da18_hybrid
    assert audit["another_provenance"] == another_provenance

    # On-disk JSON round-trips to the same content.
    on_disk = json.loads(output_path.read_text(encoding="utf-8"))
    assert on_disk == audit
    assert on_disk["da18_hybrid"] == da18_hybrid
    assert on_disk["another_provenance"] == another_provenance
    # Standard fields remain intact (representative spot-check).
    assert on_disk["weight_mean"] == audit["weight_mean"]
    assert on_disk["per_language_weighted_mass"] == audit["per_language_weighted_mass"]


def test_emit_weight_audit_extra_none_leaves_standard_fields_intact(
    tmp_path: Path,
) -> None:
    """DEP1-3 no-op invariant: ``extra=None`` (default) emits only the
    standard audit schema — no ``da18_hybrid`` / extras leak in.

    Existing callers that do not exercise the DA-18 path (v3/v4 retrain,
    nietzsche/rikyu, default weighted runs) must observe unchanged
    ``weight-audit.json`` content.
    """
    weights, metadata = _minimal_audit_input()
    output_path = tmp_path / "weight-audit.json"

    audit = emit_weight_audit(weights, metadata, output_path=output_path)

    # No extras present in returned dict.
    assert "da18_hybrid" not in audit
    # Standard schema keys are all present (representative subset).
    for key in (
        "n_examples",
        "weight_min",
        "weight_max",
        "weight_mean",
        "n_eff",
        "top_5_pct_weight_share",
        "per_language_weighted_mass",
        "bucket_histogram",
    ):
        assert key in audit, f"standard audit field {key!r} must remain present"

    # On-disk JSON matches: no extras smuggled in.
    on_disk = json.loads(output_path.read_text(encoding="utf-8"))
    assert on_disk == audit
    assert "da18_hybrid" not in on_disk
