"""Compile a persona YAML into a :class:`PersonaSourceIndex`.

The compiler is the only place that *classifies* a source's availability.
For the MVP every biographical source is forced to ``bibliographic_only``:
the corpus provenance registry is ``(persona_id,
language)``-keyed and has no mapping from a biographical ``source`` key
(``kuehn2001`` etc.) to a committed ``corpus_path``, so no
:class:`DocumentBodyRef` is ever built here. ``body_present`` may only be
enabled in a future iteration once provenance gains an explicit
``source_key -> corpus_path`` mapping.

An unregistered ``source`` key raises
:class:`~erre_sandbox.evidence.source_navigator.bibliography.SourceBibliographyMissingError`
(loud failure) rather than silently dropping the habit.

Output is deterministic: no wall-clock timestamp. ``source_digest`` is a
SHA-256 over the canonical JSON of the inputs (persona id, habits, and the
cited bibliography entries), so re-running on the same inputs yields a
byte-identical index — which is what makes ``--check`` meaningful.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import TYPE_CHECKING, Final

import yaml

from erre_sandbox.evidence.source_navigator.bibliography import lookup_source
from erre_sandbox.evidence.source_navigator.models import (
    HabitNode,
    PersonaSourceIndex,
    SourceAvailability,
    SourceNode,
)
from erre_sandbox.schemas import PersonaSpec

if TYPE_CHECKING:
    from pathlib import Path

SOURCE_NAVIGATOR_SCHEMA_VERSION: Final[str] = "0.1.0-m10-0"
_GENERATED_BY: Final[str] = "erre_sandbox.evidence.source_navigator.compiler"


def load_persona_spec(personas_dir: Path, persona_id: str) -> PersonaSpec:
    """Load and validate ``<personas_dir>/<persona_id>.yaml`` into a spec.

    Reuses the canonical :class:`PersonaSpec` model so the navigator reads
    the same validated structure the runtime does.
    """
    path = personas_dir / f"{persona_id}.yaml"
    raw = path.read_text(encoding="utf-8")
    return PersonaSpec.model_validate(yaml.safe_load(raw))


def _compute_source_digest(
    persona_id: str,
    habit_dumps: list[dict[str, object]],
    citation_dumps: list[dict[str, object]],
) -> str:
    payload: dict[str, object] = {
        "persona_id": persona_id,
        "habits": habit_dumps,
        "citations": citation_dumps,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compile_persona_index(spec: PersonaSpec) -> PersonaSourceIndex:
    """Build the depth-2 source index for a loaded persona spec."""
    # Single-pass group-by: habit nodes keep their YAML order within each
    # source bucket; sources / JSON keys are sorted at serialise time.
    buckets: dict[str, list[HabitNode]] = defaultdict(list)
    for habit in spec.cognitive_habits:
        buckets[habit.source].append(
            HabitNode(
                description=habit.description,
                flag=habit.flag,
                mechanism=habit.mechanism,
                trigger_zone=habit.trigger_zone,
                source_key=habit.source,
            ),
        )

    sources: list[SourceNode] = []
    habits_by_source: dict[str, tuple[HabitNode, ...]] = {}
    citation_dumps: list[dict[str, object]] = []
    for key in sorted(buckets):
        citation = lookup_source(key)  # loud failure if unregistered
        sources.append(
            SourceNode(
                source_key=key,
                citation=citation,
                # HIGH-1: biographical sources are forced bibliographic_only.
                availability=SourceAvailability.BIBLIOGRAPHIC_ONLY,
                body=None,
            ),
        )
        citation_dumps.append(citation.model_dump(mode="json"))
        habits_by_source[key] = tuple(buckets[key])

    # Digest inputs are sorted so a semantically-neutral habit reorder in the
    # YAML does not change the digest (citation_dumps are already key-sorted).
    habit_dumps: list[dict[str, object]] = sorted(
        (
            {
                "description": habit.description,
                "source": habit.source,
                "flag": habit.flag.value,
                "mechanism": habit.mechanism,
                "trigger_zone": (
                    habit.trigger_zone.value if habit.trigger_zone is not None else None
                ),
            }
            for habit in spec.cognitive_habits
        ),
        key=lambda dump: (str(dump["source"]), str(dump["description"])),
    )
    digest = _compute_source_digest(spec.persona_id, habit_dumps, citation_dumps)

    return PersonaSourceIndex(
        schema_version=SOURCE_NAVIGATOR_SCHEMA_VERSION,
        persona_id=spec.persona_id,
        source_digest=digest,
        generated_by=_GENERATED_BY,
        sources=tuple(sources),
        habits_by_source=habits_by_source,
    )


def compile_from_dir(personas_dir: Path, persona_id: str) -> PersonaSourceIndex:
    """Convenience: load ``<personas_dir>/<persona_id>.yaml`` then compile."""
    return compile_persona_index(load_persona_spec(personas_dir, persona_id))


__all__ = [
    "SOURCE_NAVIGATOR_SCHEMA_VERSION",
    "compile_from_dir",
    "compile_persona_index",
    "load_persona_spec",
]
