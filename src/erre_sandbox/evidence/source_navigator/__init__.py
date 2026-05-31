"""Persona source navigator (Corpus2Skill-style, local, non-cloud).

Compile-time tool that links a persona's ``cognitive_habits`` to their
cited sources and emits a depth-2 hierarchical index (markdown + JSON).
**Not connected to the runtime cognition tick.**

Layer dependency: ``schemas`` + ``pydantic`` + ``pyyaml`` + stdlib only.
No heavy ML dependency, no cloud LLM API. Generated artefacts live under
``data/corpus_index/<persona>/`` and must never feed M9-eval / LoRA
training data.
"""

from __future__ import annotations

from erre_sandbox.evidence.source_navigator.bibliography import (
    BIBLIO_REQUIRED_KEYS,
    SourceBibliographyMissingError,
    SourceBibliographySchemaError,
    lookup_source,
    registered_source_keys,
)
from erre_sandbox.evidence.source_navigator.compiler import (
    SOURCE_NAVIGATOR_SCHEMA_VERSION,
    compile_from_dir,
    compile_persona_index,
    load_persona_spec,
)
from erre_sandbox.evidence.source_navigator.models import (
    BibliographicSource,
    DocumentBodyRef,
    HabitNode,
    PersonaSourceIndex,
    SourceAvailability,
    SourceNode,
)
from erre_sandbox.evidence.source_navigator.render import (
    render_json,
    render_markdown,
)

__all__ = [
    "BIBLIO_REQUIRED_KEYS",
    "SOURCE_NAVIGATOR_SCHEMA_VERSION",
    "BibliographicSource",
    "DocumentBodyRef",
    "HabitNode",
    "PersonaSourceIndex",
    "SourceAvailability",
    "SourceBibliographyMissingError",
    "SourceBibliographySchemaError",
    "SourceNode",
    "compile_from_dir",
    "compile_persona_index",
    "load_persona_spec",
    "lookup_source",
    "registered_source_keys",
    "render_json",
    "render_markdown",
]
