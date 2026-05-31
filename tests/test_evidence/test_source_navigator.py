"""Acceptance + honesty tests for the persona source navigator.

Covers the MVP acceptance (6 habits traceable, loud failure on unregistered
source) plus the Codex HIGH findings:

* HIGH-1: biographical sources are forced ``bibliographic_only``; no
  ``DocumentBodyRef`` (and so no ``kant_de.txt`` misuse) is ever produced.
* HIGH-2: ``PersonaSourceIndex`` enforces root-level referential integrity.

And the citation ≠ evidence guarantee: a :class:`BibliographicSource` cannot
be coerced into a :class:`DocumentBodyRef`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from erre_sandbox.evidence.source_navigator.bibliography import (
    SourceBibliographyMissingError,
)
from erre_sandbox.evidence.source_navigator.compiler import (
    compile_from_dir,
    compile_persona_index,
)
from erre_sandbox.evidence.source_navigator.models import (
    BibliographicSource,
    DocumentBodyRef,
    HabitNode,
    PersonaSourceIndex,
    SourceAvailability,
    SourceNode,
)
from erre_sandbox.evidence.source_navigator.render import render_json
from erre_sandbox.schemas import CognitiveHabit, HabitFlag, Zone

REPO_ROOT = Path(__file__).resolve().parents[2]
PERSONAS_DIR = REPO_ROOT / "personas"

if not hasattr(BibliographicSource, "model_fields"):  # pragma: no cover
    pytest.skip("pydantic v2 required", allow_module_level=True)


@pytest.fixture
def kant_index() -> PersonaSourceIndex:
    return compile_from_dir(PERSONAS_DIR, "kant")


# --------------------------------------------------------------------------
# MVP acceptance
# --------------------------------------------------------------------------


def test_all_six_habits_traceable(kant_index: PersonaSourceIndex) -> None:
    total = sum(len(habits) for habits in kant_index.habits_by_source.values())
    assert total == 6
    for habits in kant_index.habits_by_source.values():
        for habit in habits:
            assert habit.source_key
            assert isinstance(habit.flag, HabitFlag)
            assert habit.mechanism
            # trigger_zone may legitimately be None (the travel-range habit).


def test_source_distribution_matches_persona(kant_index: PersonaSourceIndex) -> None:
    counts = {k: len(v) for k, v in kant_index.habits_by_source.items()}
    assert counts == {"kuehn2001": 4, "heine1834": 1, "jachmann1804": 1}


def test_unregistered_source_is_loud_failure(make_persona_spec: Any) -> None:
    ghost = CognitiveHabit(
        description="cites a source that is not registered",
        source="ghost_ref_9999",
        flag=HabitFlag.FACT,
        mechanism="n/a",
        trigger_zone=Zone.STUDY,
    ).model_dump(mode="json")
    spec = make_persona_spec(cognitive_habits=[ghost])
    with pytest.raises(SourceBibliographyMissingError):
        compile_persona_index(spec)


# --------------------------------------------------------------------------
# HIGH-1 — no body / no kant_de.txt misuse
# --------------------------------------------------------------------------


def test_biographical_sources_forced_bibliographic_only(
    kant_index: PersonaSourceIndex,
) -> None:
    for node in kant_index.sources:
        assert node.availability is SourceAvailability.BIBLIOGRAPHIC_ONLY
        assert node.body is None


def test_no_node_carries_a_document_id(kant_index: PersonaSourceIndex) -> None:
    # bibliographic_only ⇒ no DocumentBodyRef ⇒ no document_id anywhere.
    assert all(node.body is None for node in kant_index.sources)


def test_bibliographic_only_with_body_is_rejected() -> None:
    citation = _citation("kuehn2001")
    body = DocumentBodyRef(
        document_id="corpus:kant:kuehn2001:de",
        corpus_path="raw/kant_de.txt",
        retrieval_url="https://example.invalid",
        retrieval_date="2026-05-25",
    )
    with pytest.raises(ValidationError):
        SourceNode(
            source_key="kuehn2001",
            citation=citation,
            availability=SourceAvailability.BIBLIOGRAPHIC_ONLY,
            body=body,
        )


# --------------------------------------------------------------------------
# citation ≠ evidence
# --------------------------------------------------------------------------


def test_citation_cannot_be_coerced_into_document_body_ref() -> None:
    citation = _citation("kuehn2001")
    with pytest.raises(ValidationError):
        DocumentBodyRef.model_validate(citation.model_dump())


def test_citation_has_no_document_id_field() -> None:
    assert "document_id" not in BibliographicSource.model_fields
    assert "body" not in BibliographicSource.model_fields
    assert "text" not in BibliographicSource.model_fields


# --------------------------------------------------------------------------
# HIGH-2 — root-level referential integrity
# --------------------------------------------------------------------------


def test_keyset_mismatch_rejected() -> None:
    with pytest.raises(ValidationError):
        PersonaSourceIndex(
            schema_version="x",
            persona_id="kant",
            source_digest="d",
            generated_by="t",
            sources=(_node("k1"),),
            habits_by_source={"k2": (_habit("k2"),)},
        )


def test_duplicate_source_key_rejected() -> None:
    with pytest.raises(ValidationError):
        PersonaSourceIndex(
            schema_version="x",
            persona_id="kant",
            source_digest="d",
            generated_by="t",
            sources=(_node("k1"), _node("k1")),
            habits_by_source={"k1": (_habit("k1"),)},
        )


def test_habit_in_wrong_bucket_rejected() -> None:
    with pytest.raises(ValidationError):
        PersonaSourceIndex(
            schema_version="x",
            persona_id="kant",
            source_digest="d",
            generated_by="t",
            sources=(_node("k1"),),
            habits_by_source={"k1": (_habit("k2"),)},
        )


def test_source_key_must_match_citation_key() -> None:
    with pytest.raises(ValidationError):
        SourceNode(
            source_key="k1",
            citation=_citation("other"),
            availability=SourceAvailability.BIBLIOGRAPHIC_ONLY,
            body=None,
        )


# --------------------------------------------------------------------------
# determinism
# --------------------------------------------------------------------------


def test_compile_is_deterministic() -> None:
    a = compile_from_dir(PERSONAS_DIR, "kant")
    b = compile_from_dir(PERSONAS_DIR, "kant")
    assert a.source_digest == b.source_digest
    assert render_json(a) == render_json(b)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _citation(source_key: str) -> BibliographicSource:
    return BibliographicSource(
        source_key=source_key,
        author="A",
        title="T",
        year=2000,
        work_pd_by_age=False,
        pd_basis="x",
        body_committable=False,
        body_absent_reason="r",
        metadata_verified=False,
        notes="n",
    )


def _node(source_key: str) -> SourceNode:
    return SourceNode(
        source_key=source_key,
        citation=_citation(source_key),
        availability=SourceAvailability.BIBLIOGRAPHIC_ONLY,
        body=None,
    )


def _habit(source_key: str) -> HabitNode:
    return HabitNode(
        description="d",
        flag=HabitFlag.FACT,
        mechanism="m",
        trigger_zone=None,
        source_key=source_key,
    )
