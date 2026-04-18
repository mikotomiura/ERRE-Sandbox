"""Pydantic v2 schemas for agent state, memory, and control envelope.

This module is the bottom layer of the ERRE-Sandbox dependency graph: it must
not import any other ``erre_sandbox.*`` module (see
``docs/repository-structure.md`` §4 and ``architecture-rules`` Skill).

The actual ``AgentState`` / ``MemoryEntry`` / ``ControlEnvelope`` definitions
land in T05 ``schemas-freeze``. This file exists so that T04 establishes the
strict-mypy boundary before freeze begins.
"""

from __future__ import annotations
