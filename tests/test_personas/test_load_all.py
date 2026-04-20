"""Cross-persona tests for every ``personas/*.yaml`` file.

Per-persona behavioural tests for Kant remain in
``tests/test_persona_kant.py`` (kept unchanged to preserve the M2
regression signal; renamed from ``tests/test_personas.py`` to avoid a
Python module-name collision with this new ``tests/test_personas/``
package). This module adds invariants that hold across **all** personas
currently shipped in the repository — primarily enforcement of
M4-foundation differentiation: sampling triples must be unique, every
habit must carry a non-empty mechanism, and persona-specific zone rules
(Rikyū's chashitsu bias, Nietzsche's agora avoidance) are asserted here
so any future drift fails CI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from erre_sandbox.schemas import SCHEMA_VERSION, HabitFlag, PersonaSpec, Zone

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PERSONA_DIR = REPO_ROOT / "personas"
PERSONA_PATHS: list[Path] = sorted(PERSONA_DIR.glob("*.yaml"))


def _load(path: Path) -> PersonaSpec:
    data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path.name} must parse to a mapping"
    return PersonaSpec.model_validate(data)


# Parametrized tests below call ``_load(path)`` directly rather than going
# through the ``personas`` fixture so each parametrize case shows up with
# its own YAML filename in the pytest ids, making failures easier to
# triage. The extra YAML re-parse is negligible (sub-ms per file) and
# isolates one test's YAML-corruption failure from the others.
@pytest.fixture(scope="module")
def personas() -> dict[str, PersonaSpec]:
    return {p.stem: _load(p) for p in PERSONA_PATHS}


# ---------- structural invariants ---------------------------------------


def test_persona_dir_has_at_least_three_personas() -> None:
    """M4 acceptance needs kant / nietzsche / rikyu at minimum."""
    stems = {p.stem for p in PERSONA_PATHS}
    assert {"kant", "nietzsche", "rikyu"} <= stems, (
        f"missing personas: expected {{kant, nietzsche, rikyu}} ⊆ {stems}"
    )


@pytest.mark.parametrize(
    "persona_path",
    PERSONA_PATHS,
    ids=lambda p: p.stem,
)
def test_persona_yaml_validates(persona_path: Path) -> None:
    """Every YAML in personas/ round-trips through PersonaSpec."""
    spec = _load(persona_path)
    assert spec.persona_id == persona_path.stem
    assert spec.schema_version == SCHEMA_VERSION


@pytest.mark.parametrize(
    "persona_path",
    PERSONA_PATHS,
    ids=lambda p: p.stem,
)
def test_persona_has_enough_habits_with_required_fields(persona_path: Path) -> None:
    spec = _load(persona_path)
    assert len(spec.cognitive_habits) >= 4, (
        f"{persona_path.name} has {len(spec.cognitive_habits)} habits; "
        f"expected >= 4 per persona-erre skill guidance"
    )
    for habit in spec.cognitive_habits:
        assert habit.description.strip(), (
            f"{persona_path.name}: empty description on a habit"
        )
        assert habit.source.strip(), f"{persona_path.name}: empty source"
        assert habit.mechanism.strip(), (
            f"{persona_path.name}: mechanism must be non-empty — it is the "
            f"cognitive-neuroscience grounding required by ERRE"
        )
        assert isinstance(habit.flag, HabitFlag)


# ---------- differentiation invariants (M4 foundation) ------------------


def test_sampling_triples_are_unique(personas: dict[str, PersonaSpec]) -> None:
    """M4 relies on each persona having a distinct sampling fingerprint so
    dialog observation can attribute style to persona, not to noise.
    """
    triples = {
        pid: (
            spec.default_sampling.temperature,
            spec.default_sampling.top_p,
            spec.default_sampling.repeat_penalty,
        )
        for pid, spec in personas.items()
    }
    assert len(set(triples.values())) == len(triples), (
        f"default_sampling tuples must be unique across personas, got {triples}"
    )


def test_preferred_zones_differ_from_kant(personas: dict[str, PersonaSpec]) -> None:
    """At least one preferred_zones set must disagree with Kant's.

    This is a structural guard — if a future persona drift accidentally
    copied Kant's zone list wholesale, dialog differentiation collapses.
    """
    kant_zones = set(personas["kant"].preferred_zones)
    for pid, spec in personas.items():
        if pid == "kant":
            continue
        assert set(spec.preferred_zones) != kant_zones, (
            f"{pid}.preferred_zones equals kant's {kant_zones}; "
            f"differentiate per the planning design doc"
        )


# ---------- persona-specific invariants ---------------------------------


def test_nietzsche_avoids_agora(personas: dict[str, PersonaSpec]) -> None:
    """Nietzsche's post-1879 withdrawal from public gatherings is encoded in
    the persona: agora must not appear in preferred_zones.
    """
    nietzsche = personas["nietzsche"]
    assert Zone.AGORA not in nietzsche.preferred_zones, (
        "Nietzsche.preferred_zones must exclude agora (Safranski 2002 ch. 7)"
    )


def test_nietzsche_uses_peripatos(personas: dict[str, PersonaSpec]) -> None:
    """The altitudinal migration + Sils Maria habit anchors Nietzsche to
    peripatos, even though the mechanism differs from Kant's.
    """
    nietzsche = personas["nietzsche"]
    assert Zone.PERIPATOS in nietzsche.preferred_zones


def test_rikyu_primary_zone_is_chashitsu(personas: dict[str, PersonaSpec]) -> None:
    """Rikyū's entire cognitive signature is chashitsu-centred; the zone
    must lead the preferred_zones list.
    """
    rikyu = personas["rikyu"]
    assert rikyu.preferred_zones[0] is Zone.CHASHITSU, (
        f"Rikyū's preferred_zones must start with chashitsu, got "
        f"{[z.value for z in rikyu.preferred_zones]}"
    )


def test_rikyu_excludes_peripatos(personas: dict[str, PersonaSpec]) -> None:
    """Rikyū's roji walking is deliberately slow (convergent), not peripatos-
    style DMN activation. The zone must not appear in preferred_zones.
    """
    rikyu = personas["rikyu"]
    assert Zone.PERIPATOS not in rikyu.preferred_zones, (
        "Rikyū's garden roji walk is a convergent preparation, not peripatos; "
        "see design-v2 mechanism for habit #5"
    )


# ---------- flag distribution -------------------------------------------


@pytest.mark.parametrize(
    "persona_path",
    PERSONA_PATHS,
    ids=lambda p: p.stem,
)
def test_persona_has_at_least_two_flag_tiers(persona_path: Path) -> None:
    """A persona with all habits flagged as ``fact`` is under-explored; one
    with all habits flagged as ``speculative`` is over-extrapolated. Require
    at least two distinct flag values.
    """
    spec = _load(persona_path)
    flags = {h.flag for h in spec.cognitive_habits}
    assert len(flags) >= 2, (
        f"{persona_path.name} uses only {flags}; expected >= 2 flag tiers"
    )
