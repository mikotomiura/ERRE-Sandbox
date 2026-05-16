"""Unit tests for ``scripts/m9-c-adopt/audit_plan_b_corpus_stats.py``.

Exercises the 4-axis Plan B gate (``n_eff`` / ``top_5_pct_weight_share`` /
``de_en_mass`` / ``de_mass``) boundary behavior and the JSON output shape.
The script lives under ``scripts/m9-c-adopt/`` which is not a Python
module path (hyphen in dirname), so it is loaded via ``importlib.util``.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_AUDIT_PATH = _REPO_ROOT / "scripts" / "m9-c-adopt" / "audit_plan_b_corpus_stats.py"


@pytest.fixture(scope="module")
def audit_module():
    spec = importlib.util.spec_from_file_location(
        "audit_plan_b_corpus_stats", _AUDIT_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["audit_plan_b_corpus_stats"] = module
    spec.loader.exec_module(module)
    return module


def _good_audit() -> dict[str, Any]:
    """An audit dict that passes all 4 gate axes."""
    return {
        "n_eff": 1800.0,
        "top_5_pct_weight_share": 0.20,
        "per_language_weighted_mass": {
            "de": 0.35,
            "en": 0.30,
            "ja": 0.25,
            "mixed": 0.10,
        },
    }


def test_audit_corpus_passes_when_all_thresholds_met(audit_module):
    result = audit_module.audit_corpus(
        _good_audit(),
        weight_audit_path="path/to/weight-audit.json",
        merge_sha="abc123",
    )
    assert result["plan_b_gate"] == "pass"
    assert result["failed_axes"] == []
    assert result["thresholds"]["n_eff_min"] == 1500.0
    assert result["thresholds"]["de_en_mass_min"] == 0.60
    assert result["thresholds"]["de_mass_min"] == 0.30
    assert result["achieved"]["n_eff"] == 1800.0
    assert result["achieved"]["de_en_mass"] == pytest.approx(0.65)
    assert result["achieved"]["de_mass"] == pytest.approx(0.35)
    assert result["merge_sha"] == "abc123"
    assert result["weight_audit_path"] == "path/to/weight-audit.json"
    assert result["schema_version"] == 1


@pytest.mark.parametrize(
    ("mutation", "expected_axis"),
    [
        ({"n_eff": 1499.0}, "n_eff"),
        ({"top_5_pct_weight_share": 0.36}, "top_5_pct"),
    ],
)
def test_axis_fails_when_below_threshold(audit_module, mutation, expected_axis):
    audit = _good_audit()
    audit.update(mutation)
    result = audit_module.audit_corpus(
        audit,
        weight_audit_path="x.json",
        merge_sha="sha",
    )
    assert result["plan_b_gate"] == "fail"
    assert expected_axis in result["failed_axes"]


def test_de_en_mass_axis_failure(audit_module):
    audit = _good_audit()
    audit["per_language_weighted_mass"] = {
        "de": 0.40,
        "en": 0.10,  # de+en = 0.50, below 0.60
        "ja": 0.40,
        "mixed": 0.10,
    }
    result = audit_module.audit_corpus(
        audit,
        weight_audit_path="x.json",
        merge_sha="sha",
    )
    assert result["plan_b_gate"] == "fail"
    assert "de_en_mass" in result["failed_axes"]
    # de alone is still >= 0.30, so de_mass axis should pass
    assert "de_mass" not in result["failed_axes"]


def test_de_mass_axis_failure_even_when_de_en_sum_passes(audit_module):
    """en free-rider: de+en >= 0.60 but de alone < 0.30 → de_mass fails."""
    audit = _good_audit()
    audit["per_language_weighted_mass"] = {
        "de": 0.20,  # < 0.30
        "en": 0.45,  # de+en = 0.65, passes de+en gate
        "ja": 0.25,
        "mixed": 0.10,
    }
    result = audit_module.audit_corpus(
        audit,
        weight_audit_path="x.json",
        merge_sha="sha",
    )
    assert result["plan_b_gate"] == "fail"
    assert "de_mass" in result["failed_axes"]
    assert "de_en_mass" not in result["failed_axes"]


def test_multiple_axes_fail_simultaneously(audit_module):
    audit = {
        "n_eff": 1000.0,
        "top_5_pct_weight_share": 0.40,
        "per_language_weighted_mass": {
            "de": 0.10,
            "en": 0.15,
            "ja": 0.65,
            "mixed": 0.10,
        },
    }
    result = audit_module.audit_corpus(
        audit,
        weight_audit_path="x.json",
        merge_sha="sha",
    )
    assert result["plan_b_gate"] == "fail"
    assert set(result["failed_axes"]) == {
        "n_eff",
        "top_5_pct",
        "de_en_mass",
        "de_mass",
    }


def test_threshold_overrides(audit_module):
    """Overriding thresholds via kwargs should change the verdict."""
    audit = {
        "n_eff": 1200.0,
        "top_5_pct_weight_share": 0.30,
        "per_language_weighted_mass": {"de": 0.25, "en": 0.30},
    }
    # default thresholds: n_eff 1500 → fail
    assert (
        audit_module.audit_corpus(
            audit, weight_audit_path="x.json", merge_sha="sha"
        )["plan_b_gate"]
        == "fail"
    )
    # relaxed thresholds → pass
    result = audit_module.audit_corpus(
        audit,
        weight_audit_path="x.json",
        merge_sha="sha",
        n_eff_min=1000.0,
        de_en_mass_min=0.50,
        de_mass_min=0.20,
    )
    assert result["plan_b_gate"] == "pass"


def test_main_writes_gate_json_and_exits_zero_on_pass(audit_module, tmp_path):
    weight_audit_path = tmp_path / "weight-audit.json"
    weight_audit_path.write_text(json.dumps(_good_audit()), encoding="utf-8")
    output_path = tmp_path / "plan-b-corpus-gate.json"

    exit_code = audit_module.main(
        [
            "--weight-audit",
            str(weight_audit_path),
            "--merge-sha",
            "deadbeef",
            "--output",
            str(output_path),
        ]
    )
    assert exit_code == 0
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["plan_b_gate"] == "pass"
    assert result["merge_sha"] == "deadbeef"


def test_main_exits_8_on_gate_fail(audit_module, tmp_path):
    failing = {
        "n_eff": 500.0,  # < 1500
        "top_5_pct_weight_share": 0.50,
        "per_language_weighted_mass": {"de": 0.1, "en": 0.1, "ja": 0.8},
    }
    weight_audit_path = tmp_path / "weight-audit.json"
    weight_audit_path.write_text(json.dumps(failing), encoding="utf-8")
    output_path = tmp_path / "plan-b-corpus-gate.json"

    exit_code = audit_module.main(
        [
            "--weight-audit",
            str(weight_audit_path),
            "--merge-sha",
            "deadbeef",
            "--output",
            str(output_path),
        ]
    )
    assert exit_code == audit_module.GATE_FAIL_EXIT_CODE
    assert exit_code == 8
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["plan_b_gate"] == "fail"


def test_main_returns_2_when_weight_audit_missing(audit_module, tmp_path):
    nonexistent = tmp_path / "does-not-exist.json"
    output_path = tmp_path / "plan-b-corpus-gate.json"
    exit_code = audit_module.main(
        [
            "--weight-audit",
            str(nonexistent),
            "--merge-sha",
            "deadbeef",
            "--output",
            str(output_path),
        ]
    )
    assert exit_code == 2
    assert not output_path.exists()
