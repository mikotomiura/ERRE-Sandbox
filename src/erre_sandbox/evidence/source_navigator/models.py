"""Pydantic models for the persona source-navigator index.

These models encode the **citation ≠ evidence** discipline structurally:

* :class:`BibliographicSource` is a *citation*. It deliberately carries no
  ``text`` / ``body`` / ``document_id`` field, so there is nothing on it
  that a consumer could mistake for an evidence body.
* :class:`DocumentBodyRef` is the **only** type that carries a
  ``document_id``; it is constructed solely from a committed corpus
  provenance entry with a real ``corpus_path``. A :class:`BibliographicSource`
  cannot be coerced into a :class:`DocumentBodyRef` (disjoint required
  fields), so a generated summary or a bare citation can never stand in
  for a document.
* :class:`SourceNode` ties the two together under a
  :class:`SourceAvailability` state; its validator forbids a
  ``bibliographic_only`` source from carrying a body.
* :class:`PersonaSourceIndex` adds root-level referential integrity:
  the depth-1 source set must match the depth-2 bucket
  set, source keys are unique, and every habit sits in the bucket whose
  key it names.

The guarantee is *not* "mypy rejects the assignment"; it is "distinct
Pydantic models + validators + negative tests make the misuse
unrepresentable". The negative tests live in
``tests/test_evidence/test_source_navigator.py``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

# HabitFlag / Zone are used in Pydantic field annotations and must be
# importable at runtime (Pydantic resolves annotations when building the
# model), so they cannot move into a TYPE_CHECKING block.
from erre_sandbox.schemas import HabitFlag, Zone  # noqa: TC001


class SourceAvailability(StrEnum):
    """How well a habit's cited source is backed in the committed repo.

    ``unregistered`` is intentionally **not** a member: an unknown source
    key raises ``SourceBibliographyMissingError`` (loud failure) and never
    becomes a node.
    """

    BODY_PRESENT = "body_present"
    """A raw document body is committed with a corpus provenance entry.

    MVP produces no instances of this (the corpus provenance registry is
    ``(persona_id, language)``-keyed and has no mapping for biographical
    source keys like ``kuehn2001``). Kept as a forward-compatible state so
    that :class:`DocumentBodyRef` — the sole holder of ``document_id`` —
    exists and anchors the citation/evidence type split.
    """

    BIBLIOGRAPHIC_ONLY = "bibliographic_only"
    """A citation is registered, but no raw body is committed.

    The honest state for ``kuehn2001`` / ``heine1834`` / ``jachmann1804``.
    """


class BibliographicSource(BaseModel):
    """A citation. **Never** an evidence body.

    Carries no ``text`` / ``body`` / ``document_id`` field by design, so a
    citation cannot be mistaken for a document. ``work_pd_by_age`` /
    ``pd_basis`` / ``body_committable`` are kept separate:
    a work being public-domain by age does not make a *specific edition*
    body committable, so ``body_committable`` stays conservative.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_key: str
    author: str
    title: str
    year: int | None
    work_pd_by_age: bool
    pd_basis: str
    body_committable: bool
    body_absent_reason: str
    metadata_verified: bool
    notes: str


class DocumentBodyRef(BaseModel):
    """The only type that carries a ``document_id`` (= real evidence).

    Constructed solely from a committed corpus provenance entry that has a
    non-empty ``corpus_path``. No code path builds one from a
    :class:`BibliographicSource`; the required fields are disjoint.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str
    corpus_path: str
    retrieval_url: str
    retrieval_date: str


class SourceNode(BaseModel):
    """One cited source plus its availability state (depth-1 node)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_key: str
    citation: BibliographicSource
    availability: SourceAvailability
    body: DocumentBodyRef | None = None

    @model_validator(mode="after")
    def _body_matches_availability(self) -> Self:
        if self.availability is SourceAvailability.BODY_PRESENT and self.body is None:
            msg = f"source {self.source_key!r}: BODY_PRESENT requires a body"
            raise ValueError(msg)
        if (
            self.availability is SourceAvailability.BIBLIOGRAPHIC_ONLY
            and self.body is not None
        ):
            msg = f"source {self.source_key!r}: bibliographic_only forbids a body"
            raise ValueError(msg)
        if self.source_key != self.citation.source_key:
            msg = (
                f"source_key {self.source_key!r} != citation.source_key"
                f" {self.citation.source_key!r}"
            )
            raise ValueError(msg)
        return self


class HabitNode(BaseModel):
    """One cognitive habit referencing a source key (depth-2 leaf)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    description: str
    flag: HabitFlag
    mechanism: str
    trigger_zone: Zone | None
    source_key: str


class PersonaSourceIndex(BaseModel):
    """Depth-2 hierarchical index for one persona (root artefact).

    Deterministic by construction: no wall-clock timestamp. Freshness is
    pinned by ``source_digest`` (a hash of the inputs) so ``--check`` is
    stable across runs at the same input state.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    persona_id: str
    source_digest: str
    generated_by: str
    sources: tuple[SourceNode, ...]
    habits_by_source: dict[str, tuple[HabitNode, ...]]

    @model_validator(mode="after")
    def _referential_integrity(self) -> Self:
        source_keys = [node.source_key for node in self.sources]
        if len(source_keys) != len(set(source_keys)):
            msg = f"duplicate source_key in sources: {source_keys}"
            raise ValueError(msg)
        if set(source_keys) != set(self.habits_by_source):
            msg = (
                "sources key set must equal habits_by_source key set:"
                f" {sorted(set(source_keys))} != {sorted(self.habits_by_source)}"
            )
            raise ValueError(msg)
        for bucket_key, habits in self.habits_by_source.items():
            for habit in habits:
                if habit.source_key != bucket_key:
                    msg = (
                        f"habit in bucket {bucket_key!r} has source_key"
                        f" {habit.source_key!r}"
                    )
                    raise ValueError(msg)
        return self


__all__ = [
    "BibliographicSource",
    "DocumentBodyRef",
    "HabitNode",
    "PersonaSourceIndex",
    "SourceAvailability",
    "SourceNode",
]
