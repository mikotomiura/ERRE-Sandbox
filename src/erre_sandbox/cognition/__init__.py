"""Cognition layer — 1-tick CoALA + ERRE pipeline on top of memory + inference.

Public surface:

* :class:`CognitionCycle` / :class:`CycleResult` / :class:`CognitionError` —
  orchestrator
* :class:`LLMPlan` / :func:`parse_llm_plan` — LLM output contract
* :class:`StateUpdateConfig` / :func:`advance_physical` /
  :func:`apply_llm_delta` — pure CSDG half-step math
* :func:`estimate_importance` — event-type-based MVP importance heuristic
* :func:`build_system_prompt` / :func:`build_user_prompt` /
  :func:`format_memories` — pure prompt assembly

Layer dependency (see ``architecture-rules`` skill):

* allowed: ``erre_sandbox.schemas``, ``erre_sandbox.memory``,
  ``erre_sandbox.inference``, same-package siblings
* forbidden: ``world``, ``ui``
"""

from erre_sandbox.cognition.cycle import (
    BiasFiredEvent,
    CognitionCycle,
    CognitionError,
    CycleResult,
)
from erre_sandbox.cognition.importance import estimate_importance
from erre_sandbox.cognition.parse import LLMPlan, parse_llm_plan
from erre_sandbox.cognition.prompting import (
    RESPONSE_SCHEMA_HINT,
    build_system_prompt,
    build_user_prompt,
    format_memories,
)
from erre_sandbox.cognition.reflection import (
    DEFAULT_REFLECTIVE_ZONES,
    ReflectionPolicy,
    Reflector,
    build_reflection_messages,
)
from erre_sandbox.cognition.state import (
    DEFAULT_CONFIG,
    StateUpdateConfig,
    advance_physical,
    apply_llm_delta,
)

__all__ = [
    "DEFAULT_CONFIG",
    "DEFAULT_REFLECTIVE_ZONES",
    "RESPONSE_SCHEMA_HINT",
    "BiasFiredEvent",
    "CognitionCycle",
    "CognitionError",
    "CycleResult",
    "LLMPlan",
    "ReflectionPolicy",
    "Reflector",
    "StateUpdateConfig",
    "advance_physical",
    "apply_llm_delta",
    "build_reflection_messages",
    "build_system_prompt",
    "build_user_prompt",
    "estimate_importance",
    "format_memories",
    "parse_llm_plan",
]
