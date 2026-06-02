"""Golden tests for the M10-A two-layer cognition scaffold.

Covers, for ``src/erre_sandbox/contracts/cognition_layers.py``:

* valid minimal construction of every model,
* invalid boundary rejection (extra fields, bounds, enums, ``cited_memory_ids``
  >= 1, ``entries`` <= 50, ``arc_segments`` <= 5, ``end_tick`` >= ``start_tick``,
  ``lora_adapter_id`` only ``None``),
* deep immutability of :class:`PhilosopherBase` (frozen field + frozen nested
  members + hashability),
* the ``PersonaSpec`` -> ``PhilosopherBase`` projection for the three bundled
  personas with no aliasing back to the source spec,
* the feature flag defaulting *off*.

The no-wiring import audit (``cognition_layers`` must not import cognition /
world / inference / memory) is covered by
``tests/test_architecture/test_layer_dependencies.py::
test_contracts_layer_depends_only_on_schemas_and_pydantic``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from erre_sandbox.bootstrap import _load_persona_yaml
from erre_sandbox.contracts.cognition_layers import (
    ArcSegment,
    DevelopmentState,
    FrozenCognitiveHabit,
    FrozenSamplingParam,
    IndividualLayerConfig,
    IndividualProfile,
    NarrativeArc,
    PersonalityDrift,
    PhilosopherBase,
    PromotedEvidenceUnit,
    SubjectiveWorldModel,
    WorldModelEntry,
    WorldModelSnapshot,
    WorldModelUpdateHint,
)
from erre_sandbox.schemas import HabitFlag, Zone

REPO_PERSONAS = Path("personas")
BUNDLED_PERSONAS = ("kant", "nietzsche", "rikyu")


def _base() -> PhilosopherBase:
    return PhilosopherBase(
        persona_id="kant",
        display_name="Immanuel Kant",
        era="1724-1804",
        cognitive_habits=(
            FrozenCognitiveHabit(
                description="walks at the same hour",
                source="kuehn2001",
                flag=HabitFlag.FACT,
                mechanism="circadian regularity",
                trigger_zone=Zone.PERIPATOS,
            ),
        ),
    )


# ---------------------------------------------------------------------------
# valid construction
# ---------------------------------------------------------------------------


def test_all_models_construct_minimally() -> None:
    assert _base().lora_adapter_id is None
    assert SubjectiveWorldModel().entries == []
    assert DevelopmentState().stage == "S1_seed"
    assert PersonalityDrift().openness == 0.0
    entry = WorldModelEntry(
        axis="concept",
        key="categorical_imperative",
        value=0.4,
        confidence=0.8,
        cited_memory_ids=("m1",),
        last_updated_tick=10,
    )
    assert entry.decay_half_life_ticks == 1000
    arc = NarrativeArc(
        synthesized_at_tick=5,
        arc_segments=[
            ArcSegment(
                segment_label="early study",
                start_tick=0,
                end_tick=5,
                cited_memory_ids=("m1", "m2"),
            ),
        ],
        coherence_score=0.6,
        last_episodic_pointer="ep-42",
    )
    assert arc.arc_segments[0].summary is None
    profile = IndividualProfile(individual_id="ind-1", base_persona_id="kant")
    # M11-C1 (DA-M11C1-6): the three carried fields are read-model `... | None`,
    # defaulting to None ("not yet present") rather than fabricating an empty/seed
    # default. world_model is no longer an always-present empty SubjectiveWorldModel.
    assert profile.world_model is None
    assert profile.development_state is None
    assert profile.narrative_arc is None
    hint = WorldModelUpdateHint(
        axis="self",
        key="discipline",
        direction="strengthen",
        cited_memory_ids=("m9",),
    )
    assert hint.direction == "strengthen"


# ---------------------------------------------------------------------------
# WorldModelSnapshot (M11-C1 read-model)
# ---------------------------------------------------------------------------


def _swm(value: float) -> SubjectiveWorldModel:
    return SubjectiveWorldModel(
        entries=[
            WorldModelEntry(
                axis="concept",
                key="categorical_imperative",
                value=value,
                confidence=0.8,
                cited_memory_ids=("m1",),
                last_updated_tick=10,
            ),
        ],
    )


def test_world_model_snapshot_holds_floor_and_modulated() -> None:
    snap = WorldModelSnapshot(base_floor=_swm(0.4), modulated=_swm(0.5))
    assert snap.base_floor.entries[0].value == 0.4
    assert snap.modulated.entries[0].value == 0.5


def test_world_model_snapshot_is_frozen() -> None:
    snap = WorldModelSnapshot(base_floor=_swm(0.4), modulated=_swm(0.4))
    with pytest.raises(ValidationError):
        snap.base_floor = _swm(0.9)


def test_world_model_snapshot_forbids_extra() -> None:
    with pytest.raises(ValidationError):
        WorldModelSnapshot(
            base_floor=_swm(0.4),
            modulated=_swm(0.4),
            surprise="x",  # type: ignore[call-arg]
        )


def test_individual_profile_accepts_world_model_snapshot() -> None:
    """The read-model field accepts a WorldModelSnapshot (type 是正, DA-M11C1-6)."""
    snap = WorldModelSnapshot(base_floor=_swm(0.4), modulated=_swm(0.5))
    profile = IndividualProfile(
        individual_id="ind-1",
        base_persona_id="kant",
        world_model=snap,
        development_state=DevelopmentState(stage="S2_exploring"),
    )
    assert profile.world_model is snap
    assert profile.development_state is not None
    assert profile.development_state.stage == "S2_exploring"


# ---------------------------------------------------------------------------
# deep immutability of PhilosopherBase
# ---------------------------------------------------------------------------


def test_base_is_frozen_at_top_level() -> None:
    base = _base()
    with pytest.raises(ValidationError):
        base.persona_id = "nietzsche"


def test_base_nested_habit_is_frozen() -> None:
    base = _base()
    with pytest.raises(ValidationError):
        base.cognitive_habits[0].description = "mutated"


def test_base_nested_sampling_is_frozen() -> None:
    base = _base()
    with pytest.raises(ValidationError):
        base.default_sampling.temperature = 1.9


def test_base_collections_are_tuples() -> None:
    base = _base()
    assert isinstance(base.cognitive_habits, tuple)
    assert isinstance(base.preferred_zones, tuple)
    assert isinstance(base.primary_corpus_refs, tuple)


def test_base_is_hashable() -> None:
    # A frozen base with only hashable members must be set-insertable
    # (a list field would have broken this).
    assert len({_base(), _base()}) == 1


def test_lora_adapter_id_rejects_non_none() -> None:
    habit = FrozenCognitiveHabit(
        description="walks at the same hour",
        source="kuehn2001",
        flag=HabitFlag.FACT,
        mechanism="circadian regularity",
    )
    with pytest.raises(ValidationError):
        PhilosopherBase(
            persona_id="kant",
            display_name="Immanuel Kant",
            era="1724-1804",
            cognitive_habits=(habit,),
            lora_adapter_id="kant_r8",
        )


def test_base_requires_at_least_one_habit() -> None:
    with pytest.raises(ValidationError):
        PhilosopherBase(
            persona_id="kant",
            display_name="Immanuel Kant",
            era="1724-1804",
            cognitive_habits=(),
        )


# ---------------------------------------------------------------------------
# PersonaSpec -> PhilosopherBase projection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("persona_id", BUNDLED_PERSONAS)
def test_from_persona_spec_loads_bundled_personas(persona_id: str) -> None:
    spec = _load_persona_yaml(REPO_PERSONAS, persona_id)
    base = PhilosopherBase.from_persona_spec(spec)
    assert base.persona_id == spec.persona_id == persona_id
    assert base.era == spec.era
    assert base.display_name == spec.display_name
    assert len(base.cognitive_habits) == len(spec.cognitive_habits)
    assert tuple(base.preferred_zones) == tuple(spec.preferred_zones)
    assert base.lora_adapter_id is None
    assert isinstance(base.default_sampling, FrozenSamplingParam)
    assert base.default_sampling.temperature == spec.default_sampling.temperature
    assert all(isinstance(h, FrozenCognitiveHabit) for h in base.cognitive_habits)


def test_from_persona_spec_is_deep_copy_not_alias() -> None:
    spec = _load_persona_yaml(REPO_PERSONAS, "kant")
    base = PhilosopherBase.from_persona_spec(spec)
    original = base.cognitive_habits[0].description
    # Mutating the (mutable) source spec must not bleed into the frozen base.
    spec.cognitive_habits[0].description = "TAMPERED"
    assert base.cognitive_habits[0].description == original


# ---------------------------------------------------------------------------
# bounded / enum invalid boundaries
# ---------------------------------------------------------------------------


def test_extra_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        IndividualProfile(
            individual_id="ind-1",
            base_persona_id="kant",
            surprise="x",  # type: ignore[call-arg]
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"value": 1.5},
        {"value": -1.5},
        {"confidence": 1.2},
        {"confidence": -0.1},
        {"last_updated_tick": -1},
        {"decay_half_life_ticks": 0},
        {"cited_memory_ids": ()},
        {"axis": "relational"},
    ],
)
def test_world_model_entry_rejects_bad_values(kwargs: dict[str, object]) -> None:
    base_kwargs: dict[str, object] = {
        "axis": "env",
        "key": "peripatos",
        "value": 0.2,
        "confidence": 0.5,
        "cited_memory_ids": ("m1",),
        "last_updated_tick": 3,
    }
    base_kwargs.update(kwargs)
    with pytest.raises(ValidationError):
        WorldModelEntry(**base_kwargs)  # type: ignore[arg-type]


def test_subjective_world_model_caps_at_50() -> None:
    entries = [
        WorldModelEntry(
            axis="env",
            key=f"k{i}",
            value=0.0,
            confidence=0.5,
            cited_memory_ids=("m1",),
            last_updated_tick=0,
        )
        for i in range(51)
    ]
    with pytest.raises(ValidationError):
        SubjectiveWorldModel(entries=entries)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"stage": "S4_articulation"},
        {"maturity_score": 1.1},
        {"maturity_score": -0.1},
        {"transition_evidence": {"s2": -1}},
    ],
)
def test_development_state_rejects_bad_values(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        DevelopmentState(**kwargs)  # type: ignore[arg-type]


def test_arc_segment_rejects_end_before_start() -> None:
    with pytest.raises(ValidationError):
        ArcSegment(
            segment_label="bad",
            start_tick=10,
            end_tick=5,
            cited_memory_ids=("m1",),
        )


def test_arc_segment_rejects_empty_citation_and_long_summary() -> None:
    with pytest.raises(ValidationError):
        ArcSegment(
            segment_label="x",
            start_tick=0,
            end_tick=1,
            cited_memory_ids=(),
        )
    with pytest.raises(ValidationError):
        ArcSegment(
            segment_label="x",
            start_tick=0,
            end_tick=1,
            cited_memory_ids=("m1",),
            summary="z" * 501,
        )


def test_narrative_arc_caps_segments_and_bounds_coherence() -> None:
    seg = ArcSegment(
        segment_label="s",
        start_tick=0,
        end_tick=1,
        cited_memory_ids=("m1",),
    )
    with pytest.raises(ValidationError):
        NarrativeArc(
            synthesized_at_tick=0,
            arc_segments=[seg] * 6,
            coherence_score=0.5,
            last_episodic_pointer="ep",
        )
    with pytest.raises(ValidationError):
        NarrativeArc(
            synthesized_at_tick=0,
            arc_segments=[seg],
            coherence_score=1.5,
            last_episodic_pointer="ep",
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"direction": "invent"},
        {"axis": "relational"},
        {"cited_memory_ids": ()},
    ],
)
def test_world_model_update_hint_rejects_bad_values(
    kwargs: dict[str, object],
) -> None:
    base_kwargs: dict[str, object] = {
        "axis": "norm",
        "key": "duty",
        "direction": "weaken",
        "cited_memory_ids": ("m1",),
    }
    base_kwargs.update(kwargs)
    with pytest.raises(ValidationError):
        WorldModelUpdateHint(**base_kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "axis",
    [
        "openness",
        "conscientiousness",
        "extraversion",
        "agreeableness",
        "neuroticism",
    ],
)
def test_personality_drift_bounds(axis: str) -> None:
    with pytest.raises(ValidationError):
        PersonalityDrift(**{axis: 0.2})  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        PersonalityDrift(**{axis: -0.2})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# feature flag
# ---------------------------------------------------------------------------


def test_individual_layer_flag_defaults_off() -> None:
    assert IndividualLayerConfig().enabled is False


def test_individual_layer_flag_is_frozen() -> None:
    cfg = IndividualLayerConfig()
    with pytest.raises(ValidationError):
        cfg.enabled = True


# ---------------------------------------------------------------------------
# PromotedEvidenceUnit (M10-A 段B — H2 conformance substrate)
# ---------------------------------------------------------------------------


def test_promoted_evidence_unit_minimal_and_optional_defaults() -> None:
    unit = PromotedEvidenceUnit(
        other_agent_id="a_kant_001",
        confidence=0.8,
        affinity=-0.4,
        familiarity=0.5,
    )
    assert unit.belief_kind is None
    assert unit.last_interaction_zone is None
    assert unit.last_interaction_tick is None


def test_promoted_evidence_unit_zone_coerces_from_value() -> None:
    unit = PromotedEvidenceUnit(
        other_agent_id="o",
        confidence=0.5,
        affinity=0.1,
        familiarity=0.2,
        last_interaction_zone="study",  # type: ignore[arg-type]  # coerces to Zone
        last_interaction_tick=7,
    )
    assert unit.last_interaction_zone is Zone.STUDY


def test_promoted_evidence_unit_is_frozen() -> None:
    unit = PromotedEvidenceUnit(
        other_agent_id="o", confidence=0.5, affinity=0.1, familiarity=0.2
    )
    with pytest.raises(ValidationError):
        unit.affinity = 0.9


def test_promoted_evidence_unit_forbids_extra_and_abbreviated_keys() -> None:
    # the abbreviated key ``other`` (instead of ``other_agent_id``) is rejected
    # (extra=forbid) — the canonical-name discipline (DA-SB-2) is schema-enforced.
    with pytest.raises(ValidationError):
        PromotedEvidenceUnit(
            other="o",  # type: ignore[call-arg]
            confidence=0.5,
            affinity=0.1,
            familiarity=0.2,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("affinity", 1.5),
        ("affinity", -1.5),
        ("confidence", 1.5),
        ("confidence", -0.1),
        ("familiarity", 1.5),
        ("last_interaction_tick", -1),
        ("other_agent_id", ""),
    ],
)
def test_promoted_evidence_unit_bounds(field: str, value: object) -> None:
    kwargs: dict[str, object] = {
        "other_agent_id": "o",
        "confidence": 0.5,
        "affinity": 0.1,
        "familiarity": 0.2,
    }
    kwargs[field] = value
    with pytest.raises(ValidationError):
        PromotedEvidenceUnit(**kwargs)  # type: ignore[arg-type]
