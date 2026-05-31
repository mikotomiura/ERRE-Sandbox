"""Contract-level guards for the ERRE-Sandbox wire schema (T08 test-schemas).

Two layers of introspection-based checks:

* **Layer 2 (meta-invariants)**: every public ``BaseModel`` in
  ``erre_sandbox.schemas.__all__`` must forbid unknown fields and, when
  it carries a ``schema_version`` field, default to the module's
  ``SCHEMA_VERSION`` constant. Discriminator values must agree with the
  JSON fixtures on disk.
* **Layer 3 (JSON Schema golden)**: ``TypeAdapter(X).json_schema()``
  output for ``AgentState``, ``PersonaSpec``, and ``ControlEnvelope`` is
  pinned to ``tests/schema_golden/<name>.schema.json``. Any drift (fields
  added, renamed, or re-typed) fails CI and prompts a schema_version
  bump + golden regeneration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, get_args

import pytest
from pydantic import BaseModel, TypeAdapter

from erre_sandbox import schemas
from erre_sandbox.schemas import (
    SCHEMA_VERSION,
    AgentState,
    ControlEnvelope,
    Observation,
    PersonaSpec,
)

SCHEMA_GOLDEN_DIR = Path(__file__).resolve().parent / "schema_golden"
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "control_envelope"


# ---------- Introspection helpers ---------------------------------------


def _public_basemodels() -> list[type[BaseModel]]:
    """Return every ``BaseModel`` subclass reachable from ``schemas.__all__``."""
    result: list[type[BaseModel]] = []
    for name in schemas.__all__:
        attr = getattr(schemas, name, None)
        if isinstance(attr, type) and issubclass(attr, BaseModel):
            result.append(attr)
    return result


def _union_members(alias: Any) -> tuple[type[BaseModel], ...]:
    """Extract Pydantic BaseModel members from an ``Annotated[Union[...], ...]``.

    Assumes Pydantic v2.x where the project's discriminated unions are
    ``Annotated[A | B | ..., Field(discriminator=...)]``. If a future
    Pydantic release wraps members in additional annotations, update
    ``get_args`` unwrapping here.
    """
    annotated_args = get_args(alias)
    if not annotated_args:
        msg = "expected Annotated alias"
        raise TypeError(msg)
    return get_args(annotated_args[0])


# ---------- Layer 2: meta-invariants ------------------------------------


@pytest.mark.parametrize(
    "model_cls",
    _public_basemodels(),
    ids=lambda c: c.__name__,
)
def test_public_basemodel_forbids_extra(model_cls: type[BaseModel]) -> None:
    """Every exported BaseModel must reject unknown fields."""
    assert model_cls.model_config.get("extra") == "forbid", (
        f"{model_cls.__name__} must set model_config.extra='forbid' "
        f"(see .claude/skills/architecture-rules)"
    )


@pytest.mark.parametrize(
    "model_cls",
    _public_basemodels(),
    ids=lambda c: c.__name__,
)
def test_schema_version_defaults_to_module_constant(
    model_cls: type[BaseModel],
) -> None:
    """When a model has ``schema_version``, its default must be SCHEMA_VERSION."""
    field = model_cls.model_fields.get("schema_version")
    if field is None:
        pytest.skip(f"{model_cls.__name__} has no schema_version field")
    assert field.default == SCHEMA_VERSION, (
        f"{model_cls.__name__}.schema_version default is {field.default!r} "
        f"but SCHEMA_VERSION is {SCHEMA_VERSION!r}"
    )


def test_control_envelope_kinds_match_fixtures() -> None:
    """Every ``ControlEnvelope`` discriminator value has a fixture and vice-versa."""
    assert FIXTURES_DIR.exists(), (
        f"fixtures directory missing: {FIXTURES_DIR} (expected from T07)"
    )
    union_kinds = frozenset(
        m.model_fields["kind"].default for m in _union_members(ControlEnvelope)
    )
    fixture_kinds = frozenset(p.stem for p in FIXTURES_DIR.glob("*.json"))
    assert union_kinds == fixture_kinds, (
        f"Schema kinds {sorted(union_kinds)} vs "
        f"fixture kinds {sorted(fixture_kinds)} must match."
    )


def test_observation_event_types_have_unique_discriminators() -> None:
    """Each Observation member declares a distinct ``event_type`` literal."""
    values = [m.model_fields["event_type"].default for m in _union_members(Observation)]
    assert len(values) == len(set(values)), (
        f"event_type literals must be unique, got {values}"
    )
    assert len(values) >= 5, f"expected >=5 Observation kinds, got {len(values)}"


# ---------- Layer 3: JSON Schema golden ---------------------------------


_GOLDEN_TARGETS: list[tuple[str, Any]] = [
    ("agent_state", AgentState),
    ("persona_spec", PersonaSpec),
    ("control_envelope", ControlEnvelope),
]


def _current_schema_text(target: Any) -> str:
    adapter: TypeAdapter[Any] = TypeAdapter(target)
    return (
        json.dumps(adapter.json_schema(), indent=2, sort_keys=True, ensure_ascii=False)
        + "\n"
    )


@pytest.mark.parametrize(
    ("name", "target"),
    _GOLDEN_TARGETS,
    ids=[name for name, _ in _GOLDEN_TARGETS],
)
def test_json_schema_matches_golden(name: str, target: Any) -> None:
    golden_path = SCHEMA_GOLDEN_DIR / f"{name}.schema.json"
    assert golden_path.exists(), (
        f"golden not found: {golden_path}. "
        f"See tests/schema_golden/README.md for regeneration."
    )
    current = _current_schema_text(target)
    golden = golden_path.read_text(encoding="utf-8")
    assert current == golden, (
        f"JSON Schema drift detected for {name}. "
        f"If this change is intentional, bump SCHEMA_VERSION and regenerate "
        f"the golden file (see tests/schema_golden/README.md)."
    )
