"""Unit tests for :mod:`erre_sandbox.cognition.parse`."""

from __future__ import annotations

import json

from erre_sandbox.cognition.parse import LLMPlan, parse_llm_plan
from erre_sandbox.schemas import Zone


def _plan_json(**overrides: object) -> str:
    body: dict[str, object] = {
        "thought": "just walk",
        "utterance": None,
        "destination_zone": None,
        "animation": None,
        "valence_delta": 0.0,
        "arousal_delta": 0.0,
        "motivation_delta": 0.0,
        "importance_hint": 0.5,
    }
    body.update(overrides)
    return json.dumps(body)


def test_parse_valid_json() -> None:
    plan = parse_llm_plan(_plan_json(thought="peripatos today"))
    assert plan is not None
    assert isinstance(plan, LLMPlan)
    assert plan.thought == "peripatos today"


def test_parse_extracts_code_fenced_json() -> None:
    wrapped = "Here is the plan:\n```json\n" + _plan_json() + "\n```\n"
    plan = parse_llm_plan(wrapped)
    assert plan is not None


def test_parse_extracts_plain_fence() -> None:
    wrapped = "```\n" + _plan_json() + "\n```"
    plan = parse_llm_plan(wrapped)
    assert plan is not None


def test_parse_returns_none_on_invalid_json() -> None:
    assert parse_llm_plan("not a JSON object") is None
    assert parse_llm_plan("{ broken json") is None


def test_parse_rejects_non_object() -> None:
    assert parse_llm_plan("[1, 2, 3]") is None


def test_parse_clamps_oversized_valence_delta() -> None:
    # valence_delta outside [-1, 1] fails Pydantic validation → None.
    assert parse_llm_plan(_plan_json(valence_delta=1.5)) is None


def test_parse_rejects_unknown_fields() -> None:
    # extra="forbid" — spurious fields cause None.
    body = json.loads(_plan_json())
    body["extra_field"] = "nope"
    assert parse_llm_plan(json.dumps(body)) is None


def test_parse_accepts_valid_zone() -> None:
    plan = parse_llm_plan(_plan_json(destination_zone="peripatos"))
    assert plan is not None
    assert plan.destination_zone is Zone.PERIPATOS


def test_parse_rejects_invalid_zone() -> None:
    assert parse_llm_plan(_plan_json(destination_zone="moon")) is None


def test_parse_handles_nested_quoted_braces() -> None:
    # The utterance contains a ``{`` which must not fool the brace balancer.
    plan = parse_llm_plan(_plan_json(utterance="I think {therefore}"))
    assert plan is not None
    assert plan.utterance == "I think {therefore}"


def test_parse_rejects_oversized_input() -> None:
    """Security M1: inputs past MAX_RAW_PLAN_BYTES are refused early."""
    from erre_sandbox.cognition.parse import MAX_RAW_PLAN_BYTES

    huge = "a" * (MAX_RAW_PLAN_BYTES + 1) + _plan_json()
    assert parse_llm_plan(huge) is None


# ---------- M10-C: world_model_update_hint (additive, backward-compatible) --


def test_parse_world_model_update_hint_absent_defaults_none() -> None:
    """Existing flag-off output (no hint key) still parses, hint defaults None."""
    plan = parse_llm_plan(_plan_json())
    assert plan is not None
    assert plan.world_model_update_hint is None


def test_parse_world_model_update_hint_null_is_accepted() -> None:
    plan = parse_llm_plan(_plan_json(world_model_update_hint=None))
    assert plan is not None
    assert plan.world_model_update_hint is None


def test_parse_world_model_update_hint_well_formed() -> None:
    hint = {
        "axis": "env",
        "key": "agora",
        "direction": "strengthen",
        "cited_memory_ids": ["belief_kant__nietzsche"],
    }
    plan = parse_llm_plan(_plan_json(world_model_update_hint=hint))
    assert plan is not None
    assert plan.world_model_update_hint is not None
    assert plan.world_model_update_hint.axis == "env"
    assert plan.world_model_update_hint.direction == "strengthen"
    assert plan.world_model_update_hint.cited_memory_ids == ("belief_kant__nietzsche",)


def test_parse_rejects_hint_with_bad_direction() -> None:
    hint = {
        "axis": "env",
        "key": "agora",
        "direction": "obliterate",  # not in the closed 3-value set
        "cited_memory_ids": ["belief_kant__nietzsche"],
    }
    assert parse_llm_plan(_plan_json(world_model_update_hint=hint)) is None


def test_parse_rejects_hint_with_empty_citations() -> None:
    hint = {
        "axis": "env",
        "key": "agora",
        "direction": "strengthen",
        "cited_memory_ids": [],  # min_length=1 — a cite is mandatory
    }
    assert parse_llm_plan(_plan_json(world_model_update_hint=hint)) is None


def test_parse_rejects_hint_with_extra_field() -> None:
    hint = {
        "axis": "env",
        "key": "agora",
        "direction": "strengthen",
        "cited_memory_ids": ["belief_kant__nietzsche"],
        "value": 0.9,  # free-form value blob — extra="forbid" rejects it
    }
    assert parse_llm_plan(_plan_json(world_model_update_hint=hint)) is None
