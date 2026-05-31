"""Loader for the biographical source bibliography registry.

Mirrors the provenance-checked loader pattern of
:mod:`erre_sandbox.evidence.reference_corpus.loader`:

1. ``_bibliography.yaml`` is the **registered set** — a habit ``source``
   key only resolves if it has an entry here. An unknown key raises
   :class:`SourceBibliographyMissingError` (loud failure; no silent skip).
2. Every entry must carry exactly :data:`BIBLIO_REQUIRED_KEYS`; a missing
   key raises :class:`SourceBibliographySchemaError` on first load.
3. Parsing is cached per process (``functools.lru_cache``).

This module only *constructs* :class:`BibliographicSource` objects from
disk. Classifying a source's availability (``bibliographic_only`` vs
``body_present``) lives in :mod:`.compiler` — the same single-responsibility
split as the reference-corpus loader not computing Burrows Delta.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Final

import yaml

from erre_sandbox.evidence.source_navigator.models import BibliographicSource

_HERE: Final = Path(__file__).resolve().parent
_BIBLIOGRAPHY_PATH: Final = _HERE / "_bibliography.yaml"

BIBLIO_REQUIRED_KEYS: Final[frozenset[str]] = frozenset(
    {
        "source_key",
        "author",
        "title",
        "year",
        "work_pd_by_age",
        "pd_basis",
        "body_committable",
        "body_absent_reason",
        "metadata_verified",
        "notes",
    },
)
"""Every entry under ``_bibliography.yaml`` ``entries`` must carry these keys
verbatim. Missing keys raise :class:`SourceBibliographySchemaError` — the
registry is exhaustive, not best-effort (mirrors ME-6's stance for the
reference corpus)."""


class SourceBibliographyMissingError(KeyError):
    """Raised when a requested ``source_key`` is not registered.

    A habit citing an unregistered key is treated as a defect (typo /
    forgotten registration), surfaced loudly so the index never silently
    drops a habit's provenance trace.
    """


class SourceBibliographySchemaError(ValueError):
    """Raised when ``_bibliography.yaml`` is structurally broken.

    Examples: top-level is not a mapping, no ``entries`` list, an entry is
    not a mapping, or an entry is missing one of
    :data:`BIBLIO_REQUIRED_KEYS`.
    """


@lru_cache(maxsize=1)
def _load_raw() -> tuple[BibliographicSource, ...]:
    """Parse ``_bibliography.yaml`` once per process into frozen models."""
    text = _BIBLIOGRAPHY_PATH.read_text(encoding="utf-8")
    return _parse_entries(yaml.safe_load(text))


def _parse_entries(parsed: object) -> tuple[BibliographicSource, ...]:
    """Validate already-parsed YAML into frozen :class:`BibliographicSource`.

    Split out from :func:`_load_raw` so the schema-error paths can be
    unit-tested without writing temp files.
    """
    if not isinstance(parsed, dict):
        msg = (
            "_bibliography.yaml top-level must be a mapping, got"
            f" {type(parsed).__name__}"
        )
        raise SourceBibliographySchemaError(msg)
    if not isinstance(parsed.get("schema_version"), str):
        msg = "_bibliography.yaml must carry a string 'schema_version' at top level"
        raise SourceBibliographySchemaError(msg)
    entries = parsed.get("entries")
    if not isinstance(entries, list):
        msg = "_bibliography.yaml must have an 'entries' list at top level"
        raise SourceBibliographySchemaError(msg)
    out: list[BibliographicSource] = []
    seen: set[str] = set()
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            msg = f"_bibliography.yaml entries[{idx}] must be a mapping"
            raise SourceBibliographySchemaError(msg)
        missing = BIBLIO_REQUIRED_KEYS - set(entry.keys())
        if missing:
            msg = f"_bibliography.yaml entries[{idx}] missing keys: {sorted(missing)}"
            raise SourceBibliographySchemaError(msg)
        extra = set(entry.keys()) - BIBLIO_REQUIRED_KEYS
        if extra:
            msg = (
                f"_bibliography.yaml entries[{idx}] has unexpected keys:"
                f" {sorted(extra)}"
            )
            raise SourceBibliographySchemaError(msg)
        try:
            source = BibliographicSource.model_validate(entry)
        except ValueError as exc:  # pydantic ValidationError is a ValueError
            msg = f"_bibliography.yaml entries[{idx}] failed validation: {exc}"
            raise SourceBibliographySchemaError(msg) from exc
        if source.source_key in seen:
            msg = f"_bibliography.yaml duplicate source_key: {source.source_key!r}"
            raise SourceBibliographySchemaError(msg)
        seen.add(source.source_key)
        out.append(source)
    return tuple(out)


def registered_source_keys() -> frozenset[str]:
    """Return the set of registered ``source_key`` values."""
    return frozenset(source.source_key for source in _load_raw())


def lookup_source(source_key: str) -> BibliographicSource:
    """Return the :class:`BibliographicSource` for ``source_key`` or raise.

    Raises:
        SourceBibliographyMissingError: ``source_key`` is not registered.
        SourceBibliographySchemaError: ``_bibliography.yaml`` is broken.
    """
    for source in _load_raw():
        if source.source_key == source_key:
            return source
    msg = (
        f"no bibliography entry registered for source_key={source_key!r}"
        " — see evidence/source_navigator/_bibliography.yaml"
    )
    raise SourceBibliographyMissingError(msg)


__all__ = [
    "BIBLIO_REQUIRED_KEYS",
    "SourceBibliographyMissingError",
    "SourceBibliographySchemaError",
    "lookup_source",
    "registered_source_keys",
]
