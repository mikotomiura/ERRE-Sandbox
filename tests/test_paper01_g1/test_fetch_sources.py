"""Unit tests for scripts/paper01_fetch_sources.py (Loop issue I-001).

The xlsx reader and the decision rule are pure stdlib, so these tests build
synthetic ``.xlsx`` bytes with ``zipfile`` rather than depending on the real
Cambridge / Ocsai downloads (which are network-dependent and, for Ocsai,
never redistributed). Tests that do assert against the real fetched files
``pytest.skip`` when those files are not present on disk yet.
"""

from __future__ import annotations

import dataclasses
import io
import urllib.error
import zipfile

import pytest
from scripts.paper01_fetch_sources import (
    CAMBRIDGE_EXPECTED_COLUMNS,
    CAMBRIDGE_SOURCES,
    DATA_MD_PATH,
    NOTICE_TEXT,
    RAW_DIR,
    CambridgeSource,
    _audit_ocsai,
    _build_cambridge_entry,
    cambridge_gold_label,
    evaluate_audit,
    exit_code_for,
    load_cambridge_table,
    sha256_hex,
)

_SST_XML_HEADER = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
)
_SHEET_XML_HEADER = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
)


def _shared_strings_xml(strings: list[str]) -> bytes:
    items = "".join(f"<si><t>{s}</t></si>" for s in strings)
    count = len(strings)
    xml = f'{_SST_XML_HEADER} count="{count}" uniqueCount="{count}">{items}</sst>'
    return xml.encode("utf-8")


def _row_xml(row_number: int, cells: dict[str, tuple[str, str]]) -> str:
    """Build one ``<row>`` XML element from col letter -> (kind, value)."""
    parts = []
    for col, (kind, value) in cells.items():
        ref = f"{col}{row_number}"
        if kind == "s":
            parts.append(f'<c r="{ref}" t="s"><v>{value}</v></c>')
        else:
            parts.append(f'<c r="{ref}"><v>{value}</v></c>')
    return f'<row r="{row_number}">{"".join(parts)}</row>'


def _build_xlsx(shared: list[str], rows_xml: list[str]) -> bytes:
    xml = f"{_SHEET_XML_HEADER}<sheetData>{''.join(rows_xml)}</sheetData></worksheet>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("xl/sharedStrings.xml", _shared_strings_xml(shared))
        zf.writestr("xl/worksheets/sheet1.xml", xml.encode("utf-8"))
    return buf.getvalue()


_HEADER_ROW = _row_xml(
    1,
    {
        "A": ("s", "0"),
        "B": ("s", "1"),
        "C": ("s", "2"),
        "D": ("s", "3"),
        "E": ("s", "4"),
        "F": ("s", "5"),
    },
)
_SHARED = [
    "id",
    "Responses",
    "rater1",
    "rater2",
    "rater3",
    "average",
    "apple",
    "banana",
    "cherry",
    "fig",
]


def _synthetic_cambridge_xlsx() -> bytes:
    """A 6-data-row synthetic workbook exercising every binarisation branch.

    row2 id=1 apple  rater=(1,1,1)      -> common
    row3 id=2 banana rater=(3,4,3)      -> good
    row4 id=3 cherry rater=(1,2,1)      -> excluded (contains 2)
    row5 id=4 (Responses cell omitted)  -> excluded (Responses missing)
    row6 id=5 fig (all rater cells omitted) -> excluded (no rater has a value)
    row7 id=6 fig (only rater1 present=1)   -> common (single present rater, ==1)
    """
    rows = [
        _HEADER_ROW,
        _row_xml(
            2,
            {
                "A": ("n", "1"),
                "B": ("s", "6"),
                "C": ("n", "1"),
                "D": ("n", "1"),
                "E": ("n", "1"),
            },
        ),
        _row_xml(
            3,
            {
                "A": ("n", "2"),
                "B": ("s", "7"),
                "C": ("n", "3"),
                "D": ("n", "4"),
                "E": ("n", "3"),
            },
        ),
        _row_xml(
            4,
            {
                "A": ("n", "3"),
                "B": ("s", "8"),
                "C": ("n", "1"),
                "D": ("n", "2"),
                "E": ("n", "1"),
            },
        ),
        _row_xml(5, {"A": ("n", "4"), "C": ("n", "1")}),
        _row_xml(6, {"A": ("n", "5"), "B": ("s", "9")}),
        _row_xml(7, {"A": ("n", "6"), "B": ("s", "9"), "C": ("n", "1")}),
    ]
    return _build_xlsx(_SHARED, rows)


# --- AC 001-2: xlsx reader row counts (synthetic, no real-file dependency) --


def test_xlsx_reader_row_counts() -> None:
    data = _synthetic_cambridge_xlsx()
    header, body = load_cambridge_table(data)
    assert header == list(CAMBRIDGE_EXPECTED_COLUMNS)
    assert len(body) == 6

    labels = [
        cambridge_gold_label(row, responses_idx=1, rater_idxs=[2, 3, 4]) for row in body
    ]
    assert labels == ["common", "good", None, None, None, "common"]


# --- AC 001-3: real Cambridge column names (skips if not fetched) -----------


def test_cambridge_columns() -> None:
    for source in CAMBRIDGE_SOURCES:
        path = RAW_DIR / source.filename
        if not path.exists():
            pytest.skip(
                f"{source.filename} not fetched; run paper01_fetch_sources.py first"
            )
        header, _body = load_cambridge_table(path.read_bytes())
        assert tuple(header) == CAMBRIDGE_EXPECTED_COLUMNS


# --- AC 001-1: raw files byte-match the pinned + documented SHA-256 --------


def test_cambridge_raw_files_hash_matches_manifest() -> None:
    manifest_missing = not DATA_MD_PATH.exists()
    any_present = False
    for source in CAMBRIDGE_SOURCES:
        path = RAW_DIR / source.filename
        if not path.exists():
            continue
        any_present = True
        assert sha256_hex(path.read_bytes()) == source.sha256
    if not any_present:
        pytest.skip(
            "Cambridge raw files not fetched; run paper01_fetch_sources.py first"
        )
    if manifest_missing:
        pytest.skip("experiments/20260907-paper01-g1/data.md not written yet")
    manifest_text = DATA_MD_PATH.read_text(encoding="utf-8")
    for source in CAMBRIDGE_SOURCES:
        assert source.sha256 in manifest_text


# --- AC 001-4: Ocsai fetch failure is recorded, not raised ------------------


def test_ocsai_unavailable_is_recorded_not_crash() -> None:
    def _raise(url: str) -> bytes:
        raise urllib.error.URLError(f"simulated network failure for {url}")

    result = _audit_ocsai(fetch=_raise)
    assert result["status"] == "source_unavailable"
    assert "simulated network failure" in result["error"]


# --- AC 001-5: the real judgment functions catch a deliberately broken audit


def test_count_mismatch_exits_nonzero() -> None:
    data = _synthetic_cambridge_xlsx()
    valid_source = CambridgeSource(
        key="synthetic",
        filename="synthetic.xlsx",
        sha256=sha256_hex(data),
        expected_rows=6,
        expected_good=1,
        expected_common=2,
    )
    good_entry = _build_cambridge_entry(
        valid_source, data, source_uri="https://example.invalid/synthetic.xlsx"
    )
    assert good_entry["row_count_match"] is True
    assert good_entry["gold_counts_match"] is True

    ok_audit = {
        "cambridge": {"synthetic": good_entry},
        "ocsai": {"status": "source_unavailable"},
    }
    assert evaluate_audit(ok_audit) == []
    assert exit_code_for(ok_audit) == 0

    # Deliberately break the pinned expectation (simulating upstream data drift)
    # and push it through the *real* decision functions -- not just a fixture
    # asserting its own fields.
    broken_source = dataclasses.replace(
        valid_source, expected_rows=999, expected_good=0
    )
    broken_entry = _build_cambridge_entry(
        broken_source, data, source_uri="https://example.invalid/synthetic.xlsx"
    )
    assert broken_entry["row_count_match"] is False
    assert broken_entry["gold_counts_match"] is False

    broken_audit = {
        "cambridge": {"synthetic": broken_entry},
        "ocsai": {"status": "source_unavailable"},
    }
    problems = evaluate_audit(broken_audit)
    assert problems
    assert any("row count" in p for p in problems)
    assert any("gold class counts" in p for p in problems)
    assert exit_code_for(broken_audit) == 1


# --- AC 001-6: NOTICE.md carries all four CC BY-NC-ND 4.0 attribution fields


def test_notice_has_attribution_fields() -> None:
    assert "Sun" in NOTICE_TEXT  # creator
    assert "©" in NOTICE_TEXT  # copyright notice
    assert (
        "creativecommons.org/licenses/by-nc-nd/4.0" in NOTICE_TEXT
    )  # license reference URI
    assert (
        "github.com/ghydsgaaa/Cambridge-AUT-dataset" in NOTICE_TEXT
    )  # original source URI


# --- AC 001-7: no undeclared dependency (pandas / openpyxl) ----------------


def test_no_undeclared_dependency_import() -> None:
    import ast
    from pathlib import Path

    import scripts.paper01_fetch_sources as module

    source_path = module.__file__
    assert source_path is not None
    tree = ast.parse(Path(source_path).read_text(encoding="utf-8"))

    banned = {"pandas", "openpyxl"}
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])

    assert not (found & banned), f"undeclared dependency imported: {found & banned}"
