"""Structural checks on ``docs/references.md`` for Loop issue I-010.

I-010 appends a new bibliography row ([32], the Cambridge AUT dataset paper)
to the central citation SSOT and deliberately does *not* re-register the
Ocsai citation ([22] already exists with the same DOI). These tests parse
the table mechanically -- rather than merely asserting the file exists --
and are exercised against both the real file and hand-built broken inputs,
per the ``citation-ssot`` skill's append-only / no-duplicate-key rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

_REFERENCES_PATH = Path(__file__).resolve().parents[2] / "docs" / "references.md"

# A data row looks like ``| [12] | DOI:... | ... | ... | ... | active |``.
# The header row uses the literal text ``[n]`` (no digits) and the
# separator row is all dashes, so neither matches this pattern.
_ROW_RE = re.compile(r"^\|\s*\[(\d+)\]\s*\|(.*)\|\s*$")


@dataclass(frozen=True)
class ReferenceRow:
    """One parsed data row of the references table."""

    number: int
    key: str
    status: str


def parse_reference_rows(markdown: str) -> list[ReferenceRow]:
    """Extract the ``[n] | key | ... | status`` data rows from a references.md body.

    Only lines whose first cell is a literal ``[<digits>]`` are treated as
    data; the header (``[n]``) and the ``|---|---|`` separator do not match
    and are silently skipped.
    """
    rows: list[ReferenceRow] = []
    for line in markdown.splitlines():
        match = _ROW_RE.match(line.strip())
        if match is None:
            continue
        number = int(match.group(1))
        cells = [cell.strip() for cell in match.group(2).split("|")]
        if len(cells) < 5:
            raise ValueError(f"reference row has too few columns: {line!r}")
        rows.append(ReferenceRow(number=number, key=cells[0], status=cells[-1]))
    return rows


def validate_append_only_numbering(rows: list[ReferenceRow]) -> None:
    """Assert ``[n]`` IDs form a contiguous ``1..len(rows)`` sequence.

    This is the machine-checkable half of the citation-ssot append-only
    rule: ``[n]`` is a permanent ID that must match display order with no
    gaps, no duplicates, and no renumbering.
    """
    numbers = [row.number for row in rows]
    expected = list(range(1, len(rows) + 1))
    if numbers != expected:
        raise ValueError(
            f"reference numbering is not a contiguous 1..N sequence: {numbers!r}"
        )


def validate_no_duplicate_keys(rows: list[ReferenceRow]) -> None:
    """Assert the DOI/arXiv/URL dedup key (citation-ssot rule 4) is unique."""
    seen: dict[str, int] = {}
    for row in rows:
        if row.key in seen:
            prior, current = seen[row.key], row.number
            raise ValueError(f"duplicate key {row.key!r}: [{prior}] and [{current}]")
        seen[row.key] = row.number


# --- real-file checks -------------------------------------------------


def _read_references() -> str:
    return _REFERENCES_PATH.read_text(encoding="utf-8")


def test_references_numbering_is_append_only() -> None:
    """The live SSOT must have no gaps/duplicates/renumbering in [n]."""
    rows = parse_reference_rows(_read_references())
    assert len(rows) >= 32, "expected I-010 to have appended entry [32]"
    validate_append_only_numbering(rows)


def test_references_has_no_duplicate_keys() -> None:
    """No two rows (across the whole SSOT) may share a DOI/arXiv/URL key."""
    rows = parse_reference_rows(_read_references())
    validate_no_duplicate_keys(rows)


def test_entry_32_is_the_cambridge_aut_dataset_paper() -> None:
    """I-010 registers the Cambridge AUT dataset citation as a new entry [32]."""
    rows = parse_reference_rows(_read_references())
    row_32 = next(row for row in rows if row.number == 32)
    assert row_32.key == "DOI:10.1007/978-981-97-0065-3_9"
    assert row_32.status == "active"


def test_ocsai_citation_is_reused_not_duplicated() -> None:
    """The Ocsai citation (same DOI as existing [22]) must not get a new number."""
    rows = parse_reference_rows(_read_references())
    ocsai_doi = "DOI:10.1016/j.tsc.2023.101356"
    matches = [row for row in rows if row.key == ocsai_doi]
    assert len(matches) == 1, "Ocsai DOI must appear exactly once (reused as [22])"
    assert matches[0].number == 22


def test_license_and_motes_provenance_are_documented() -> None:
    """AC 010-3: licences and the Ocsai/MOTES provenance grey zone are recorded."""
    text = _read_references()
    assert "CC BY-NC-ND 4.0" in text
    assert "MOTES" in text
    assert "MIT" in text


# --- mutation tests: the validators must reject broken input ----------

_GOOD_MARKDOWN = """
| [n] | key (DOI/arXiv/URL) | title | src | usage | status |
|---|---|---|---|---|---|
| [1] | DOI:a | A | 2020 | x | active |
| [2] | DOI:b | B | 2021 | x | active |
| [3] | DOI:c | C | 2022 | x | active |
"""


def test_parser_accepts_a_well_formed_sequence() -> None:
    rows = parse_reference_rows(_GOOD_MARKDOWN)
    assert [row.number for row in rows] == [1, 2, 3]
    validate_append_only_numbering(rows)
    validate_no_duplicate_keys(rows)


def test_gap_in_numbering_is_detected() -> None:
    broken = _GOOD_MARKDOWN.replace("| [3] |", "| [4] |")
    rows = parse_reference_rows(broken)
    with pytest.raises(ValueError, match="not a contiguous"):
        validate_append_only_numbering(rows)


def test_duplicate_number_is_detected() -> None:
    broken = _GOOD_MARKDOWN.replace("| [3] |", "| [2] |")
    rows = parse_reference_rows(broken)
    with pytest.raises(ValueError, match="not a contiguous"):
        validate_append_only_numbering(rows)


def test_duplicate_key_is_detected() -> None:
    broken = _GOOD_MARKDOWN.replace("DOI:c", "DOI:a")
    rows = parse_reference_rows(broken)
    with pytest.raises(ValueError, match="duplicate key"):
        validate_no_duplicate_keys(rows)


def test_out_of_order_numbering_is_detected() -> None:
    """[n] must match display order too -- a silent reorder is still a violation."""
    broken = (
        "| [n] | key | title | src | usage | status |\n"
        "|---|---|---|---|---|---|\n"
        "| [2] | DOI:b | B | 2021 | x | active |\n"
        "| [1] | DOI:a | A | 2020 | x | active |\n"
    )
    rows = parse_reference_rows(broken)
    with pytest.raises(ValueError, match="not a contiguous"):
        validate_append_only_numbering(rows)
