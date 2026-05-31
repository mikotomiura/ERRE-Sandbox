"""Contract test for ``golden/stimulus/{kant,nietzsche,rikyu}.yaml``.

P2c で Pydantic v2 model に sync する前提の **軽量 contract** で、ここでは
PyYAML のみを使い形式適合・enum・id ユニーク性・件数を検証する。

Refs:
    - golden/stimulus/_schema.yaml (single-source-of-truth)
    - .steering/20260430-m9-eval-system/decisions.md ME-7
      (Option A 採択 + MCQ schema、Codex review 反映)
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN_DIR = REPO_ROOT / "golden" / "stimulus"

PERSONA_IDS: tuple[str, ...] = ("kant", "nietzsche", "rikyu")

ALLOWED_CATEGORIES: frozenset[str] = frozenset(
    {"wachsmuth", "tom_chashitsu", "roleeval", "moral_dilemma"}
)
ALLOWED_ZONES: frozenset[str] = frozenset(
    {"peripatos", "chashitsu", "agora", "garden", "study"}
)
ALLOWED_TOULMIN: frozenset[str] = frozenset(
    {"claim", "data", "warrant", "backing", "qualifier", "rebuttal"}
)
ALLOWED_TOM_AXES: frozenset[str] = frozenset(
    {"first_order", "second_order", "recursive_third_order"}
)
ALLOWED_MCQ_SUBCATEGORIES: frozenset[str] = frozenset(
    {"chronology", "works", "practice", "relationships", "material_term"}
)
ALLOWED_SOURCE_GRADES: frozenset[str] = frozenset({"fact", "secondary", "legend"})
ALLOWED_ETHICAL_AXES: frozenset[str] = frozenset(
    {
        "kant_categorical_imperative",
        "kant_duty_inclination",
        "nietzsche_master_slave",
        "nietzsche_eternal_recurrence",
        "nietzsche_will_to_power",
        "rikyu_wabi_calibration",
        "rikyu_authority_inversion",
        "rikyu_ma_silence",
        "shared_classical",
    }
)

EXPECTED_CATEGORY_COUNTS: dict[str, int] = {
    "wachsmuth": 30,
    "tom_chashitsu": 20,
    "roleeval": 10,
    "moral_dilemma": 10,
}

STIMULUS_ID_PATTERN = re.compile(
    r"^(wachsmuth|tom|roleeval|dilemma)_(kant|nietzsche|rikyu)_[0-9]{2}$"
)
SCHEMA_VERSION_EXPECTED = "0.1.0-m9eval-p2a"
TOTAL_COUNT_EXPECTED = 70


@pytest.fixture(scope="module")
def persona_yamls() -> dict[str, dict[str, Any]]:
    """Load all 3 persona stimulus YAMLs once per module."""
    out: dict[str, dict[str, Any]] = {}
    for persona_id in PERSONA_IDS:
        path = GOLDEN_DIR / f"{persona_id}.yaml"
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict), f"{path} must parse to a mapping at root"
        out[persona_id] = data
    return out


@pytest.mark.parametrize("persona_id", PERSONA_IDS)
def test_c1_root_keys(
    persona_yamls: dict[str, dict[str, Any]], persona_id: str
) -> None:
    """c1: root に required key 全部、schema_version / total_count strict 一致."""
    data = persona_yamls[persona_id]
    required = {
        "persona_id",
        "schema_version",
        "total_count",
        "category_counts",
        "stimuli",
    }
    assert required <= set(data.keys()), (
        f"missing root keys: {required - set(data.keys())}"
    )
    assert data["persona_id"] == persona_id
    assert data["schema_version"] == SCHEMA_VERSION_EXPECTED
    assert data["total_count"] == TOTAL_COUNT_EXPECTED
    assert data["category_counts"] == EXPECTED_CATEGORY_COUNTS
    assert isinstance(data["stimuli"], list)
    assert len(data["stimuli"]) == TOTAL_COUNT_EXPECTED


@pytest.mark.parametrize("persona_id", PERSONA_IDS)
def test_c2_category_counts(
    persona_yamls: dict[str, dict[str, Any]], persona_id: str
) -> None:
    """c2: category 分布が wachsmuth=30 / tom=20 / roleeval=10 / dilemma=10."""
    stimuli = persona_yamls[persona_id]["stimuli"]
    counts = Counter(s["category"] for s in stimuli)
    assert dict(counts) == EXPECTED_CATEGORY_COUNTS


@pytest.mark.parametrize("persona_id", PERSONA_IDS)
def test_c3_stimulus_id_unique(
    persona_yamls: dict[str, dict[str, Any]], persona_id: str
) -> None:
    """c3: stimulus_id が persona 内で重複なし."""
    stimuli = persona_yamls[persona_id]["stimuli"]
    ids = [s["stimulus_id"] for s in stimuli]
    duplicates = [item for item, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"duplicate stimulus_id in {persona_id}: {duplicates}"


@pytest.mark.parametrize("persona_id", PERSONA_IDS)
def test_c4_stimulus_id_pattern(
    persona_yamls: dict[str, dict[str, Any]], persona_id: str
) -> None:
    """c4: stimulus_id pattern 適合 + persona slug が一致."""
    stimuli = persona_yamls[persona_id]["stimuli"]
    for s in stimuli:
        sid = s["stimulus_id"]
        assert STIMULUS_ID_PATTERN.match(sid), f"id pattern mismatch: {sid}"
        assert sid.split("_")[1] == persona_id, (
            f"persona slug in id {sid} != {persona_id}"
        )


@pytest.mark.parametrize("persona_id", PERSONA_IDS)
def test_c5_category_enum(
    persona_yamls: dict[str, dict[str, Any]], persona_id: str
) -> None:
    """c5: 全 stimulus の category が enum 適合."""
    stimuli = persona_yamls[persona_id]["stimuli"]
    bad = [s for s in stimuli if s["category"] not in ALLOWED_CATEGORIES]
    assert not bad, (
        f"unknown categories in {persona_id}: {[s['stimulus_id'] for s in bad]}"
    )


@pytest.mark.parametrize("persona_id", PERSONA_IDS)
def test_c6_zone_enum(
    persona_yamls: dict[str, dict[str, Any]], persona_id: str
) -> None:
    """c6: expected_zone enum 適合."""
    stimuli = persona_yamls[persona_id]["stimuli"]
    bad = [s for s in stimuli if s["expected_zone"] not in ALLOWED_ZONES]
    assert not bad, f"unknown zones in {persona_id}: {[s['stimulus_id'] for s in bad]}"


@pytest.mark.parametrize("persona_id", PERSONA_IDS)
def test_c7_turn_count_range(
    persona_yamls: dict[str, dict[str, Any]], persona_id: str
) -> None:
    """c7: expected_turn_count が 1-3 の range."""
    stimuli = persona_yamls[persona_id]["stimuli"]
    for s in stimuli:
        tc = s["expected_turn_count"]
        assert isinstance(tc, int), f"turn_count not int in {s['stimulus_id']}"
        assert 1 <= tc <= 3, f"turn_count out of range in {s['stimulus_id']}: {tc}"


@pytest.mark.parametrize("persona_id", PERSONA_IDS)
def test_c8_roleeval_subcategory_balance(
    persona_yamls: dict[str, dict[str, Any]], persona_id: str
) -> None:
    """c8: roleeval 10 問が 5 種 subcategory を 2 問ずつ均等 (Codex MEDIUM-4)."""
    stimuli = persona_yamls[persona_id]["stimuli"]
    roleeval = [s for s in stimuli if s["category"] == "roleeval"]
    assert len(roleeval) == 10
    subcat_counts = Counter(s["mcq_subcategory"] for s in roleeval)
    expected = dict.fromkeys(ALLOWED_MCQ_SUBCATEGORIES, 2)
    assert dict(subcat_counts) == expected, (
        f"roleeval subcat imbalance in {persona_id}: {dict(subcat_counts)}"
    )


@pytest.mark.parametrize("persona_id", PERSONA_IDS)
def test_c9_roleeval_options_a_to_d(
    persona_yamls: dict[str, dict[str, Any]], persona_id: str
) -> None:
    """c9: roleeval item の options が A/B/C/D 完全保有 + correct_option ∈ A-D."""
    stimuli = persona_yamls[persona_id]["stimuli"]
    roleeval = [s for s in stimuli if s["category"] == "roleeval"]
    for s in roleeval:
        assert "options" in s, f"missing options: {s['stimulus_id']}"
        opts = s["options"]
        assert isinstance(opts, dict), f"options must be a mapping: {s['stimulus_id']}"
        assert set(opts.keys()) == {"A", "B", "C", "D"}, (
            f"options keys mismatch in {s['stimulus_id']}: {sorted(opts.keys())}"
        )
        for key, value in opts.items():
            assert isinstance(value, str), f"option {key} not str in {s['stimulus_id']}"
            assert value, f"option {key} empty in {s['stimulus_id']}"
        assert s["correct_option"] in {"A", "B", "C", "D"}, (
            f"invalid correct_option in {s['stimulus_id']}"
        )


@pytest.mark.parametrize("persona_id", PERSONA_IDS)
def test_c10_roleeval_source_grade_enum_and_legend_exclude(
    persona_yamls: dict[str, dict[str, Any]], persona_id: str
) -> None:
    """c10: source_grade enum + legend 由来は category_subscore_eligible=False.

    Codex MEDIUM-2 反映: legend grade item は stimulus 投入はするが factuality
    scoring から除外する契約。
    """
    stimuli = persona_yamls[persona_id]["stimuli"]
    roleeval = [s for s in stimuli if s["category"] == "roleeval"]
    for s in roleeval:
        grade = s["source_grade"]
        assert grade in ALLOWED_SOURCE_GRADES, (
            f"unknown source_grade in {s['stimulus_id']}: {grade}"
        )
        eligible = s["category_subscore_eligible"]
        assert isinstance(eligible, bool)
        if grade == "legend":
            assert eligible is False, (
                f"legend item must be scoring-excluded: {s['stimulus_id']}"
            )


@pytest.mark.parametrize("persona_id", PERSONA_IDS)
def test_c11_roleeval_present_in_prompt_balance(
    persona_yamls: dict[str, dict[str, Any]], persona_id: str
) -> None:
    """c11: present_in_persona_prompt true/false 比率が 4-6 / 4-6 (Codex MEDIUM-4)."""
    stimuli = persona_yamls[persona_id]["stimuli"]
    roleeval = [s for s in stimuli if s["category"] == "roleeval"]
    true_count = sum(1 for s in roleeval if s["present_in_persona_prompt"] is True)
    false_count = sum(1 for s in roleeval if s["present_in_persona_prompt"] is False)
    assert true_count + false_count == 10
    assert 4 <= true_count <= 6, (
        f"present_in_prompt true imbalance in {persona_id}: true={true_count}"
    )
    assert 4 <= false_count <= 6, (
        f"present_in_prompt false imbalance in {persona_id}: false={false_count}"
    )


@pytest.mark.parametrize("persona_id", PERSONA_IDS)
def test_c12_dilemma_ethical_axis_enum(
    persona_yamls: dict[str, dict[str, Any]], persona_id: str
) -> None:
    """c12: moral_dilemma の ethical_axis が enum 適合."""
    stimuli = persona_yamls[persona_id]["stimuli"]
    dilemmas = [s for s in stimuli if s["category"] == "moral_dilemma"]
    assert len(dilemmas) == 10
    for s in dilemmas:
        axis = s["ethical_axis"]
        assert axis in ALLOWED_ETHICAL_AXES, (
            f"unknown ethical_axis in {s['stimulus_id']}: {axis}"
        )


@pytest.mark.parametrize("persona_id", PERSONA_IDS)
def test_c13_wachsmuth_toulmin_target_enum(
    persona_yamls: dict[str, dict[str, Any]], persona_id: str
) -> None:
    """c13: wachsmuth の toulmin_target が enum 適合 + 配分が 30 件で fitting."""
    stimuli = persona_yamls[persona_id]["stimuli"]
    wachsmuth = [s for s in stimuli if s["category"] == "wachsmuth"]
    assert len(wachsmuth) == 30
    for s in wachsmuth:
        target = s["toulmin_target"]
        assert target in ALLOWED_TOULMIN, (
            f"unknown toulmin_target in {s['stimulus_id']}: {target}"
        )
    # 設計目安分布: claim 8 / data 6 / warrant 8 / backing 4 / qualifier 2 / rebuttal 2
    counts = Counter(s["toulmin_target"] for s in wachsmuth)
    assert sum(counts.values()) == 30


@pytest.mark.parametrize("persona_id", PERSONA_IDS)
def test_c14_tom_asymmetry_axis_enum(
    persona_yamls: dict[str, dict[str, Any]], persona_id: str
) -> None:
    """c14: tom_chashitsu の asymmetry_axis が enum 適合 + hidden_information 必須."""
    stimuli = persona_yamls[persona_id]["stimuli"]
    tom = [s for s in stimuli if s["category"] == "tom_chashitsu"]
    assert len(tom) == 20
    for s in tom:
        axis = s["asymmetry_axis"]
        assert axis in ALLOWED_TOM_AXES, (
            f"unknown asymmetry_axis in {s['stimulus_id']}: {axis}"
        )
        hidden = s.get("hidden_information")
        assert isinstance(hidden, str), (
            f"hidden_information not str in {s['stimulus_id']}"
        )
        assert hidden.strip(), f"hidden_information empty in {s['stimulus_id']}"


@pytest.mark.parametrize("persona_id", PERSONA_IDS)
def test_prompt_text_nonempty(
    persona_yamls: dict[str, dict[str, Any]], persona_id: str
) -> None:
    """c15 (補強): 全 stimulus の prompt_text が非空 (>=5 文字).

    日本語 MCQ stem (例 "汝の生年は何年か。" 9 文字) で完結する場合があるため、
    閾値は character-density を考慮して 5 文字に設定。完全空文字 / whitespace
    のみを排除することが本契約の本質。
    """
    stimuli = persona_yamls[persona_id]["stimuli"]
    for s in stimuli:
        text = s["prompt_text"]
        assert isinstance(text, str), f"prompt_text must be str: {s['stimulus_id']}"
        assert len(text.strip()) >= 5, (
            f"prompt_text too short in {s['stimulus_id']}: {len(text.strip())}"
        )


def test_schema_yaml_loads() -> None:
    """補強: golden/stimulus/_schema.yaml itself parses cleanly."""
    schema_path = GOLDEN_DIR / "_schema.yaml"
    with schema_path.open(encoding="utf-8") as f:
        schema = yaml.safe_load(f)
    assert isinstance(schema, dict)
    assert schema["schema_version"] == SCHEMA_VERSION_EXPECTED
    assert "contract_assertions" in schema
    assert "stimulus_common" in schema
    assert "stimulus_roleeval" in schema
