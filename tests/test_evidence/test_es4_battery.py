"""Contract the frozen M13-ES4 battery / reference data files against the schema.

Sizes, id uniqueness, enum membership, common-use keying and adversarial label
consistency (``design-final.md`` §6 / §2.2b). The data files are a frozen
pre-registration; this is their structural regression pin.
"""

from __future__ import annotations

from erre_sandbox.evidence.es4_actuator import constants as _c
from erre_sandbox.evidence.es4_actuator.battery import (
    SCHEMA_VERSION,
    load_adversarial_labeled,
    load_aut_battery,
    load_common_uses,
    load_rat_battery,
)


def test_aut_battery_structure() -> None:
    aut = load_aut_battery()
    assert len(aut.items) == _c.N_AUT
    assert sum(1 for it in aut.items if it.stratum == "classic") == _c.N_AUT_CLASSIC
    assert sum(1 for it in aut.items if it.stratum == "novel") == _c.N_AUT_NOVEL
    ids = [it.object_id for it in aut.items]
    assert len(set(ids)) == len(ids)
    assert "{object}" in aut.prompt_template


def test_aut_prompt_substitution() -> None:
    aut = load_aut_battery()
    item = next(it for it in aut.items if it.object_id == "brick")
    assert aut.prompt_for(item) == "List as many unusual uses as you can for a brick."
    assert "{object}" not in aut.prompt_for(item)


def test_rat_battery_structure() -> None:
    rat = load_rat_battery()
    assert len(rat.items) == _c.N_RAT
    ids = [it.item_id for it in rat.items]
    assert len(set(ids)) == len(ids)
    for it in rat.items:
        assert len(it.cues) == 3
        assert it.answer


def test_common_uses_keyed_to_aut_with_exact_curated_count() -> None:
    common = load_common_uses()
    aut_ids = {it.object_id for it in load_aut_battery().items}
    assert set(common) == aut_ids
    for object_id, uses in common.items():
        assert len(uses) == _c.N_CURATED, object_id


def test_adversarial_labeled_set_valid_and_balanced() -> None:
    items = load_adversarial_labeled()
    assert len(items) >= 120  # design-final §4.1 (>=120 strings)
    pos = [it for it in items if it.label == "appropriate"]
    neg = [it for it in items if it.label == "inappropriate"]
    assert pos
    assert neg
    categories = {it.category for it in items}
    assert {
        "good",
        "garbage",
        "word_salad",
        "plausible_off_task",
        "common_use_only",
        "object_mismatch",
        "metaphor_only",
    } <= categories


def test_adversarial_label_matches_category() -> None:
    for it in load_adversarial_labeled():
        expected = (
            "appropriate"
            if it.category in {"good", "common_use_only"}
            else "inappropriate"
        )
        assert it.label == expected, (it.category, it.text)


def test_battery_schema_version() -> None:
    assert SCHEMA_VERSION == "0.1.0-m13es4"
