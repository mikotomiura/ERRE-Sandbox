"""Unit tests for the pure aggregation/verdict helpers in scripts/p3a_decide.py.

The script itself is exercised end-to-end during the P3a-decide finalization
session against real DuckDB pilots. These tests cover the lightweight
aggregation logic that drives the ME-4 ratio Edit, since the verdict branch
selection is decision-critical.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "p3a_decide.py"


@pytest.fixture(scope="module")
def p3a_decide():
    spec = importlib.util.spec_from_file_location("scripts_p3a_decide", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_block(
    persona: str,
    condition: str,
    burrows_width: float | None,
    mattr_width: float | None,
    n: int = 30,
) -> dict:
    metrics: dict = {}
    if burrows_width is not None:
        metrics["burrows_delta_per_utterance"] = {
            "point": 0.5,
            "lo": 0.5 - burrows_width / 2,
            "hi": 0.5 + burrows_width / 2,
            "width": burrows_width,
            "n": n,
            "n_resamples": 2000,
            "method": "percentile",
        }
    if mattr_width is not None:
        metrics["mattr_per_utterance"] = {
            "point": 0.7,
            "lo": 0.7 - mattr_width / 2,
            "hi": 0.7 + mattr_width / 2,
            "width": mattr_width,
            "n": n,
            "n_resamples": 2000,
            "method": "percentile",
        }
    return {
        "persona_id": persona,
        "condition": condition,
        "n_utterances": n,
        "metrics": metrics,
    }


def test_mean_widths_by_condition_aggregates_per_persona(p3a_decide):
    blocks = [
        _make_block("kant", "stimulus", 0.20, 0.10, n=198),
        _make_block("nietzsche", "stimulus", 0.30, 0.20, n=198),
        _make_block("rikyu", "stimulus", 0.40, 0.30, n=198),
        _make_block("kant", "natural", 0.50, 0.40, n=30),
        _make_block("nietzsche", "natural", 0.60, 0.50, n=30),
        _make_block("rikyu", "natural", 0.70, 0.60, n=30),
    ]
    summary = p3a_decide._mean_widths_by_condition(blocks)
    stim = summary["stimulus"]
    nat = summary["natural"]
    assert stim["burrows_delta_per_utterance"]["mean_width"] == pytest.approx(0.30)
    assert stim["mattr_per_utterance"]["mean_width"] == pytest.approx(0.20)
    assert stim["mean_combined_width"]["value"] == pytest.approx(0.25)
    assert nat["burrows_delta_per_utterance"]["mean_width"] == pytest.approx(0.60)
    assert nat["mattr_per_utterance"]["mean_width"] == pytest.approx(0.50)
    assert nat["mean_combined_width"]["value"] == pytest.approx(0.55)


def test_mean_widths_skips_missing_metrics(p3a_decide):
    blocks = [
        _make_block("kant", "stimulus", None, None),
        _make_block("kant", "natural", 0.5, 0.5),
    ]
    summary = p3a_decide._mean_widths_by_condition(blocks)
    assert "skipped" in summary["stimulus"]["burrows_delta_per_utterance"]
    assert "skipped" in summary["stimulus"]["mattr_per_utterance"]
    assert "skipped" in summary["stimulus"]["mean_combined_width"]
    assert summary["natural"]["mean_combined_width"]["value"] == pytest.approx(0.5)


def test_ratio_summary_within_tolerance_maintains_default(p3a_decide):
    by_condition = {
        "stimulus": {"mean_combined_width": {"value": 0.25, "n_metrics": 2}},
        "natural": {"mean_combined_width": {"value": 0.26, "n_metrics": 2}},
    }
    out = p3a_decide._ratio_summary(by_condition)
    assert out["verdict"].startswith("within_tolerance")
    assert out["abs_diff_from_unity_pct"] < 10.0
    assert out["deferred_metrics"] == ["vendi_score", "big5_icc"]


def test_ratio_summary_natural_wider_flags_alternative(p3a_decide):
    by_condition = {
        "stimulus": {"mean_combined_width": {"value": 0.20, "n_metrics": 2}},
        "natural": {"mean_combined_width": {"value": 0.40, "n_metrics": 2}},
    }
    out = p3a_decide._ratio_summary(by_condition)
    assert out["verdict"].startswith("natural_wider")
    assert out["width_ratio_natural_over_stimulus"] == pytest.approx(2.0)
    assert any("Pilot N is asymmetric" in c for c in out["caveats"])


def test_ratio_summary_stimulus_wider_flags_alternative(p3a_decide):
    by_condition = {
        "stimulus": {"mean_combined_width": {"value": 0.40, "n_metrics": 2}},
        "natural": {"mean_combined_width": {"value": 0.20, "n_metrics": 2}},
    }
    out = p3a_decide._ratio_summary(by_condition)
    assert out["verdict"].startswith("stimulus_wider")
    assert out["width_ratio_natural_over_stimulus"] == pytest.approx(0.5)


def test_ratio_summary_skipped_when_missing_value(p3a_decide):
    by_condition = {
        "stimulus": {"mean_combined_width": {"value": 0.25, "n_metrics": 2}},
        "natural": {"mean_combined_width": {"skipped": "no widths"}},
    }
    out = p3a_decide._ratio_summary(by_condition)
    assert "skipped" in out
    assert out["deferred_metrics"] == ["vendi_score", "big5_icc"]


def test_pilot_path_uses_persona_and_condition(p3a_decide):
    path = p3a_decide._pilot_path("kant", "natural")
    assert path.name == "kant_natural_run0.duckdb"
    path = p3a_decide._pilot_path("rikyu", "stimulus")
    assert path.name == "rikyu_stimulus_run0.duckdb"
