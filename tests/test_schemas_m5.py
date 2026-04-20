"""Contract tests frozen by ``m5-contracts-freeze`` (schema 0.3.0-m5).

Each ``test_*`` documents one concrete clause of the M5 wire contract:

* ``SCHEMA_VERSION == "0.3.0-m5"``
* ``Cognitive.dialog_turn_budget`` default = 6, ``ge=0``
* ``DialogTurnMsg.turn_index`` required, ``ge=0``
* ``DialogCloseMsg.reason`` literal includes ``"exhausted"``
* ``ERREModeTransitionPolicy`` / ``DialogTurnGenerator`` Protocols are
  importable from ``erre_sandbox.schemas``

Writing these tests **before** editing ``schemas.py`` was a deliberate
choice of the v2 design (see
``.steering/20260420-m5-contracts-freeze/design.md``). Future milestones
should add a sibling ``test_schemas_m{N}.py`` rather than growing this file.

Protocol shape checks are intentionally minimal (``get_type_hints`` on a few
key parameters). Full behavioural coverage lives in the concrete sub-task
test suites (``test_erre/``, ``test_integration/test_dialog_turn.py``).
"""

from __future__ import annotations

import inspect
from typing import get_args, get_type_hints

import pytest
from pydantic import ValidationError

from erre_sandbox.schemas import (
    SCHEMA_VERSION,
    Cognitive,
    DialogCloseMsg,
    DialogTurnGenerator,
    DialogTurnMsg,
    ERREModeName,
    ERREModeTransitionPolicy,
)

# ---------- §1 SCHEMA_VERSION ------------------------------------------------


def test_schema_version_is_m5() -> None:
    assert SCHEMA_VERSION == "0.3.0-m5"


# ---------- §4 Cognitive.dialog_turn_budget ---------------------------------


def test_cognitive_dialog_turn_budget_default_is_six() -> None:
    cognitive = Cognitive()
    assert cognitive.dialog_turn_budget == 6


def test_cognitive_dialog_turn_budget_accepts_zero() -> None:
    cognitive = Cognitive(dialog_turn_budget=0)
    assert cognitive.dialog_turn_budget == 0


def test_cognitive_dialog_turn_budget_rejects_negative() -> None:
    with pytest.raises(ValidationError):
        Cognitive(dialog_turn_budget=-1)


# ---------- §7 DialogTurnMsg.turn_index --------------------------------------


def _base_dialog_turn_kwargs() -> dict[str, object]:
    return {
        "tick": 1,
        "dialog_id": "d_test_0001",
        "speaker_id": "a_kant_001",
        "addressee_id": "a_rikyu_001",
        "utterance": "...",
    }


def test_dialog_turn_accepts_zero_turn_index() -> None:
    msg = DialogTurnMsg(turn_index=0, **_base_dialog_turn_kwargs())
    assert msg.turn_index == 0


def test_dialog_turn_rejects_missing_turn_index() -> None:
    with pytest.raises(ValidationError):
        DialogTurnMsg(**_base_dialog_turn_kwargs())


def test_dialog_turn_rejects_negative_turn_index() -> None:
    with pytest.raises(ValidationError):
        DialogTurnMsg(turn_index=-1, **_base_dialog_turn_kwargs())


# ---------- §7 DialogCloseMsg.reason literal --------------------------------


def _base_dialog_close_kwargs() -> dict[str, object]:
    return {"tick": 1, "dialog_id": "d_test_0001"}


@pytest.mark.parametrize(
    "reason",
    ["completed", "interrupted", "timeout", "exhausted"],
)
def test_dialog_close_accepts_known_reasons(reason: str) -> None:
    msg = DialogCloseMsg(reason=reason, **_base_dialog_close_kwargs())  # type: ignore[arg-type]
    assert msg.reason == reason


def test_dialog_close_rejects_unknown_reason() -> None:
    with pytest.raises(ValidationError):
        DialogCloseMsg(reason="abandoned", **_base_dialog_close_kwargs())  # type: ignore[arg-type]


# ---------- §7.5 Protocol imports and shape ---------------------------------


def test_erre_mode_transition_policy_is_protocol() -> None:
    # Protocols are classes at runtime; membership of typing.Protocol is
    # indicated by the ``_is_protocol`` attribute that ``typing`` sets.
    assert inspect.isclass(ERREModeTransitionPolicy)
    assert getattr(ERREModeTransitionPolicy, "_is_protocol", False) is True


def test_dialog_turn_generator_is_protocol() -> None:
    assert inspect.isclass(DialogTurnGenerator)
    assert getattr(DialogTurnGenerator, "_is_protocol", False) is True


def test_erre_mode_transition_policy_next_mode_signature() -> None:
    method = ERREModeTransitionPolicy.next_mode
    sig = inspect.signature(method)
    # keyword-only parameters expected: current / zone / observations / tick
    expected_params = {"current", "zone", "observations", "tick"}
    actual_params = set(sig.parameters) - {"self"}
    assert expected_params.issubset(actual_params)
    hints = get_type_hints(method)
    return_hint = hints.get("return")
    assert return_hint is not None
    # Both ``Union[ERREModeName, None]`` and ``ERREModeName | None`` resolve
    # the same way; it suffices that ERREModeName appears among the args.
    args = get_args(return_hint)
    assert ERREModeName in args


def test_dialog_turn_generator_generate_turn_signature() -> None:
    method = DialogTurnGenerator.generate_turn
    assert inspect.iscoroutinefunction(method), (
        "generate_turn must be async so callers can await the LLM call."
    )
    sig = inspect.signature(method)
    expected_params = {
        "dialog_id",
        "speaker_state",
        "speaker_persona",
        "addressee_state",
        "transcript",
        "world_tick",
    }
    actual_params = set(sig.parameters) - {"self"}
    assert expected_params.issubset(actual_params)
    hints = get_type_hints(method)
    return_hint = hints.get("return")
    assert return_hint is not None
    args = get_args(return_hint)
    assert DialogTurnMsg in args
