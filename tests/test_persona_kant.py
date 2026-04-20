"""Tests for persona YAML files under ``personas/``.

Validates that ``personas/kant.yaml`` (T06) loads cleanly into
``PersonaSpec`` and satisfies the invariants promised by the design
document. Full behavioural tests for persona consumption belong in
T11 / T12.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from erre_sandbox.schemas import SCHEMA_VERSION, HabitFlag, PersonaSpec, Zone

REPO_ROOT = Path(__file__).resolve().parent.parent
KANT_YAML = REPO_ROOT / "personas" / "kant.yaml"


@pytest.fixture(scope="module")
def kant_raw() -> dict[str, Any]:
    with KANT_YAML.open(encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
    assert isinstance(loaded, dict), "kant.yaml must parse to a mapping"
    return loaded


@pytest.fixture(scope="module")
def kant(kant_raw: dict[str, Any]) -> PersonaSpec:
    return PersonaSpec.model_validate(kant_raw)


def test_kant_yaml_loads_into_persona_spec(kant: PersonaSpec) -> None:
    assert kant.persona_id == "kant"
    assert kant.display_name == "Immanuel Kant"
    assert kant.era == "1724-1804"
    assert kant.schema_version == SCHEMA_VERSION


def test_kant_personality_reflects_biographical_profile(kant: PersonaSpec) -> None:
    # Kuehn 2001 consensus: very high conscientiousness + broad openness.
    assert kant.personality.conscientiousness >= 0.85
    assert kant.personality.openness >= 0.80
    # ma_sense high due to enforced silence on return leg / nasal breathing rule.
    assert kant.personality.ma_sense >= 0.60


def test_kant_has_enough_habits_all_four_required_fields(kant: PersonaSpec) -> None:
    assert len(kant.cognitive_habits) >= 5
    for habit in kant.cognitive_habits:
        assert habit.description.strip(), "description must be non-empty"
        assert habit.source.strip(), "source must be non-empty"
        assert habit.mechanism.strip(), "mechanism must be non-empty"
        assert isinstance(habit.flag, HabitFlag)


def test_kant_has_walk_habit_linked_to_peripatos(kant: PersonaSpec) -> None:
    walk_habits = [h for h in kant.cognitive_habits if "walk" in h.description.lower()]
    assert walk_habits, "at least one habit should mention walking"
    assert any(h.trigger_zone is Zone.PERIPATOS for h in walk_habits)


def test_kant_flag_distribution_is_three_tier_template(kant: PersonaSpec) -> None:
    flags = {h.flag for h in kant.cognitive_habits}
    assert HabitFlag.FACT in flags
    assert HabitFlag.LEGEND in flags
    # speculative is intentionally present as a 3-tier template example;
    # future personas may lack it, but Kant's YAML is the reference template.
    assert HabitFlag.SPECULATIVE in flags


def test_kant_trigger_zones_use_zone_enum(kant: PersonaSpec) -> None:
    non_null_triggers = [
        h.trigger_zone for h in kant.cognitive_habits if h.trigger_zone is not None
    ]
    # At least 4 of the 6 habits should be zone-anchored (design aims for 5/6).
    assert len(non_null_triggers) >= 4
    for zone in non_null_triggers:
        assert isinstance(zone, Zone)


def test_kant_preferred_zones_include_peripatos(kant: PersonaSpec) -> None:
    # peripatos (the daily walk) is the single most defining Kant zone;
    # study carries the writing / lecturing work. Both must be present.
    assert Zone.PERIPATOS in kant.preferred_zones
    assert Zone.STUDY in kant.preferred_zones


def test_kant_sampling_reflects_analytic_precision(kant: PersonaSpec) -> None:
    # Lower than the deep_work base of 0.7 to express Kant's analytic style.
    assert kant.default_sampling.temperature <= 0.70
    assert kant.default_sampling.top_p <= 0.90
    # Mild repetition penalty; not aggressive enough to break terminology.
    assert 1.0 < kant.default_sampling.repeat_penalty <= 1.20


def test_kant_primary_corpus_refs_have_no_orphans(kant: PersonaSpec) -> None:
    """Kant YAML follows the lean-refs design: every declared corpus ref
    is cited by at least one habit source. Future personas may relax this
    (e.g. refs used only for personality tuning); this test is Kant-specific.
    """
    cited_sources = {h.source for h in kant.cognitive_habits}
    orphans = set(kant.primary_corpus_refs) - cited_sources
    assert not orphans, f"declared refs not used in habits: {orphans}"


def test_extra_forbid_rejects_unknown_top_level_field(
    kant_raw: dict[str, Any],
) -> None:
    tampered = {**kant_raw, "not_in_schema": "anything"}
    with pytest.raises(ValidationError):
        PersonaSpec.model_validate(tampered)
