"""Contract tests for the source bibliography registry loader.

Mirrors the discipline of the reference-corpus loader: the registry is the
registered set (unknown key → loud failure), every entry must carry exactly
the required keys, and the metadata is honest (unverified, conservative
body-committability).
"""

from __future__ import annotations

from typing import Any

import pytest

from erre_sandbox.evidence.source_navigator.bibliography import (
    BIBLIO_REQUIRED_KEYS,
    SourceBibliographyMissingError,
    SourceBibliographySchemaError,
    _parse_entries,
    lookup_source,
    registered_source_keys,
)
from erre_sandbox.evidence.source_navigator.models import BibliographicSource


def _valid_entry(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "source_key": "x2000",
        "author": "Some Author",
        "title": "Some Title",
        "year": 2000,
        "work_pd_by_age": False,
        "pd_basis": "in copyright",
        "body_committable": False,
        "body_absent_reason": "in_copyright_license",
        "metadata_verified": False,
        "notes": "test entry",
    }
    base.update(overrides)
    return base


def test_required_keys_match_model_fields() -> None:
    assert set(BibliographicSource.model_fields) == BIBLIO_REQUIRED_KEYS


def test_registered_keys_are_the_three_biographical_sources() -> None:
    assert registered_source_keys() == frozenset(
        {"kuehn2001", "heine1834", "jachmann1804"},
    )


def test_lookup_returns_honest_unverified_metadata() -> None:
    src = lookup_source("kuehn2001")
    # DA-SN-4: maintainer-entered, not auto-verified.
    assert src.metadata_verified is False
    # DA-SN-10: in-copyright work is never body-committable.
    assert src.body_committable is False
    assert src.work_pd_by_age is False


def test_pd_by_age_source_is_still_not_body_committable() -> None:
    # DA-SN-10: PD by age does not make a specific edition body committable.
    src = lookup_source("heine1834")
    assert src.work_pd_by_age is True
    assert src.body_committable is False


def test_lookup_unregistered_is_loud_failure() -> None:
    with pytest.raises(SourceBibliographyMissingError):
        lookup_source("does_not_exist_9999")


def test_missing_key_raises_schema_error() -> None:
    bad = _valid_entry()
    del bad["author"]
    with pytest.raises(SourceBibliographySchemaError):
        _parse_entries({"schema_version": "0.1.0-test", "entries": [bad]})


def test_unexpected_key_raises_schema_error() -> None:
    with pytest.raises(SourceBibliographySchemaError):
        _parse_entries(
            {"schema_version": "0.1.0-test", "entries": [_valid_entry(surprise="nope")]}
        )


def test_duplicate_source_key_raises_schema_error() -> None:
    entry = _valid_entry()
    with pytest.raises(SourceBibliographySchemaError):
        _parse_entries(
            {"schema_version": "0.1.0-test", "entries": [entry, dict(entry)]}
        )


def test_non_mapping_top_level_raises() -> None:
    with pytest.raises(SourceBibliographySchemaError):
        _parse_entries([1, 2, 3])


def test_missing_schema_version_raises() -> None:
    with pytest.raises(SourceBibliographySchemaError):
        _parse_entries({"entries": [_valid_entry()]})


def test_missing_entries_list_raises() -> None:
    with pytest.raises(SourceBibliographySchemaError):
        _parse_entries({"schema_version": "x"})


def test_parse_valid_entry_roundtrips() -> None:
    out = _parse_entries({"schema_version": "0.1.0-test", "entries": [_valid_entry()]})
    assert len(out) == 1
    assert out[0].source_key == "x2000"
