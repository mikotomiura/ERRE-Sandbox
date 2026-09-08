"""Fetch external corpora for the paper01 G1 external audit (Loop issue I-001).

Fetches the two Cambridge-AUT-dataset ``.xlsx`` files (redistributed unmodified
under CC BY-NC-ND 4.0) and the three Ocsai ``main2`` ``.jsonl`` splits
(fetched-and-measured only, never redistributed), verifies their SHA-256
against the values pinned in ``.steering/20260907-paper01-g1-external-audit/
gate0-record.md`` and ``design-final.md`` Sec.3.1, computes shape/gold-class
counts, and writes a machine-checkable audit to
``experiments/20260907-paper01-g1/data/source-audit.json``.

Stdlib + numpy only (Stop condition S6: no ``pandas`` / ``openpyxl``). The
``.xlsx`` reader parses the OOXML package directly with ``zipfile`` +
``xml.etree.ElementTree``.

Exit codes:
    0 -- all pinned counts matched (Ocsai unreachable is also a 0-exit, with
         ``ocsai.status == "source_unavailable"`` recorded instead of crashing).
    1 -- Cambridge unreachable, or any pinned count/hash mismatched (data
         drifted upstream; the expected values are never adjusted to match).

Run directly: ``python scripts/paper01_fetch_sources.py``.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
DATA_DIR: Final[Path] = REPO_ROOT / "experiments" / "20260907-paper01-g1" / "data"
RAW_DIR: Final[Path] = DATA_DIR / "raw"
AUDIT_PATH: Final[Path] = DATA_DIR / "source-audit.json"
NOTICE_PATH: Final[Path] = RAW_DIR / "NOTICE.md"
DATA_MD_PATH: Final[Path] = (
    REPO_ROOT / "experiments" / "20260907-paper01-g1" / "data.md"
)

CAMBRIDGE_BASE: Final[str] = (
    "https://raw.githubusercontent.com/ghydsgaaa/Cambridge-AUT-dataset/main/data/"
)
OCSAI_BASE: Final[str] = (
    "https://raw.githubusercontent.com/massivetexts/ocsai/main/data/ocsai1/"
)

CAMBRIDGE_LICENSE: Final[str] = "CC BY-NC-ND 4.0"
OCSAI_LICENSE: Final[str] = (
    "repo MIT (massivetexts/ocsai); underlying MOTES corpus provenance is a"
    " grey zone -- see data.md"
)

CAMBRIDGE_EXPECTED_COLUMNS: Final[tuple[str, ...]] = (
    "id",
    "Responses",
    "rater1",
    "rater2",
    "rater3",
    "average",
)


@dataclass(frozen=True, slots=True)
class CambridgeSource:
    """One pinned Cambridge-AUT-dataset ``.xlsx`` file."""

    key: str
    filename: str
    sha256: str
    expected_rows: int
    expected_good: int
    expected_common: int


@dataclass(frozen=True, slots=True)
class OcsaiSource:
    """One pinned Ocsai ``main2`` ``.jsonl`` split."""

    split: str
    filename: str
    sha256: str


# SHA-256 pinned in .steering/20260907-paper01-g1-external-audit/gate0-record.md
# and design-final.md Sec.3.1. Expected row / gold-class counts pinned in the
# same gate0-record.md table. Never edit these to match a bad run -- a
# mismatch means upstream data drifted and I-001 must stop and report (issue
# 001.md Stop Conditions).
CAMBRIDGE_SOURCES: Final[tuple[CambridgeSource, ...]] = (
    CambridgeSource(
        key="bowl",
        filename="bowl AUT dataset.xlsx",
        sha256="f8caa57cdebe1d8f19257c88e56c5346415f5289897efaa10f4150508341ac2d",
        expected_rows=3380,
        expected_good=32,
        expected_common=2082,
    ),
    CambridgeSource(
        key="paperclip",
        filename="paperclip AUT dataset.xlsx",
        sha256="69e75792d0caa20363bf49a5dd57bbac731f2a19159a6b04753b0617999d7a96",
        expected_rows=3650,
        expected_good=47,
        expected_common=2047,
    ),
)

OCSAI_SOURCES: Final[tuple[OcsaiSource, ...]] = (
    OcsaiSource(
        split="train",
        filename="finetune-gt_main2_prepared_train.jsonl",
        sha256="7b2ed8fb8a1b3c98dbb86428c222c5806870ab73a280d6e664aee137bf05ddfd",
    ),
    OcsaiSource(
        split="val",
        filename="finetune-gt_main2_prepared_val.jsonl",
        sha256="a40bc78a5275ad274baeac7f410f7c1beb37e7913b138f5ef5fcfee8e15ccd9b",
    ),
    OcsaiSource(
        split="test",
        filename="finetune-gt_main2_prepared_test.jsonl",
        sha256="bab9bf8fc28c27113a7d4d55e8f718edbad02214d14d53d98e8c78f07b3a4068",
    ),
)

EXPECTED_OCSAI_TOTAL_ROWS: Final[int] = 20121
EXPECTED_OCSAI_POOL_GOOD: Final[int] = 733
EXPECTED_OCSAI_POOL_COMMON: Final[int] = 2003
EXPECTED_OCSAI_DISTINCT_OBJECTS: Final[int] = 21
EXPECTED_OCSAI_PARSE_FAILURES: Final[int] = 0


class CambridgeUnavailableError(RuntimeError):
    """Raised when a Cambridge source cannot be fetched at all (Stop S1)."""


# --- generic fetch / hashing -------------------------------------------------


def sha256_hex(data: bytes) -> str:
    """Return the lowercase hex SHA-256 digest of ``data``."""
    return hashlib.sha256(data).hexdigest()


def fetch_bytes(url: str, *, timeout: float = 60.0) -> bytes:
    """Fetch ``url`` and return the raw response bytes.

    Every caller in this module passes a URL built from the fixed
    ``CAMBRIDGE_BASE`` / ``OCSAI_BASE`` https allowlist above -- never
    user-supplied input.
    """
    headers = {"User-Agent": "erre-sandbox-paper01-fetch/1.0"}
    request = urllib.request.Request(url, headers=headers)  # noqa: S310
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read()


# --- minimal stdlib .xlsx reader ---------------------------------------------

_XLSX_NS: Final[str] = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_CELL_REF_RE: Final[re.Pattern[str]] = re.compile(r"([A-Z]+)(\d+)")


def _column_letters_to_index(letters: str) -> int:
    index = 0
    for char in letters:
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def _load_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        raw = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(raw)  # noqa: S314 -- trusted package we just downloaded/wrote ourselves
    return [
        "".join(t.text or "" for t in si.iter(f"{_XLSX_NS}t"))
        for si in root.findall(f"{_XLSX_NS}si")
    ]


def read_xlsx_sheet1_rows(data: bytes) -> list[list[str]]:
    """Parse ``sheet1.xml`` of an ``.xlsx`` package into rows of cell text.

    Every row (including the header row) is returned as a list of strings,
    one per column, padded with ``""`` for cells Excel omitted (blank
    cells). Numeric cells are returned as their raw ``<v>`` text (e.g.
    ``"3.0"`` or ``"3"``); shared-string / inline-string cells are resolved
    to their text.
    """
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        shared = _load_shared_strings(zf)
        sheet_xml = zf.read("xl/worksheets/sheet1.xml")
    root = ET.fromstring(sheet_xml)  # noqa: S314 -- trusted package we just downloaded/wrote ourselves
    sheet_data = root.find(f"{_XLSX_NS}sheetData")
    if sheet_data is None:
        return []

    parsed_rows: list[dict[int, str]] = []
    max_col = -1
    for row_el in sheet_data.findall(f"{_XLSX_NS}row"):
        cell_map: dict[int, str] = {}
        for c_el in row_el.findall(f"{_XLSX_NS}c"):
            match = _CELL_REF_RE.match(c_el.get("r", ""))
            if match is None:
                continue
            col_index = _column_letters_to_index(match.group(1))
            max_col = max(max_col, col_index)
            cell_map[col_index] = _cell_text(c_el, shared)
        parsed_rows.append(cell_map)

    width = max_col + 1
    return [[cell_map.get(i, "") for i in range(width)] for cell_map in parsed_rows]


def _cell_text(c_el: ET.Element, shared: Sequence[str]) -> str:
    cell_type = c_el.get("t")
    if cell_type == "s":
        v_el = c_el.find(f"{_XLSX_NS}v")
        if v_el is None or not v_el.text:
            return ""
        return shared[int(v_el.text)]
    if cell_type == "inlineStr":
        is_el = c_el.find(f"{_XLSX_NS}is")
        if is_el is None:
            return ""
        return "".join(t.text or "" for t in is_el.iter(f"{_XLSX_NS}t"))
    v_el = c_el.find(f"{_XLSX_NS}v")
    return v_el.text if v_el is not None and v_el.text is not None else ""


def load_cambridge_table(data: bytes) -> tuple[list[str], list[list[str]]]:
    """Return ``(header_row, data_rows)`` for a Cambridge-AUT-dataset ``.xlsx`` file."""
    rows = read_xlsx_sheet1_rows(data)
    if not rows:
        return [], []
    header, *body = rows
    return header, body


# --- Cambridge gold binarisation (design-final.md Sec.3.3) -------------------


def _header_index(header: Sequence[str], name: str) -> int | None:
    try:
        return list(header).index(name)
    except ValueError:
        return None


_CAMBRIDGE_COMMON_RATING: Final[float] = 1.0
_CAMBRIDGE_GOOD_MIN_RATING: Final[float] = 3.0


def cambridge_gold_label(
    row: Sequence[str], *, responses_idx: int, rater_idxs: Sequence[int]
) -> str | None:
    """Binarise one Cambridge row per design-final.md Sec.3.3.

    common: every rater that has a value scored exactly 1.
    good: every rater that has a value scored 3 or higher.
    Everything else (a 0, a 2, a band-crossing mix, or a missing
    ``Responses`` cell) is excluded (``None``).
    """
    responses = row[responses_idx] if responses_idx < len(row) else ""
    if not responses.strip():
        return None

    values: list[float] = []
    for idx in rater_idxs:
        raw = row[idx] if idx < len(row) else ""
        if raw == "":
            continue
        try:
            values.append(float(raw))
        except ValueError:
            continue
    if not values:
        return None
    if all(v == _CAMBRIDGE_COMMON_RATING for v in values):
        return "common"
    if all(v >= _CAMBRIDGE_GOOD_MIN_RATING for v in values):
        return "good"
    return None


def ensure_cambridge_raw(
    source: CambridgeSource,
    *,
    fetch: Callable[[str], bytes] = fetch_bytes,
    force_download: bool = False,
) -> bytes:
    """Return raw bytes for ``source``; download byte-exact if not already on disk."""
    dest = RAW_DIR / source.filename
    if dest.exists() and not force_download:
        return dest.read_bytes()
    url = CAMBRIDGE_BASE + urllib.parse.quote(source.filename)
    data = fetch(url)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return data


def _build_cambridge_entry(
    source: CambridgeSource,
    data: bytes,
    *,
    source_uri: str,
) -> dict[str, Any]:
    digest = sha256_hex(data)
    header, body = load_cambridge_table(data)
    responses_idx = _header_index(header, "Responses")
    rater_idxs = [
        idx
        for idx in (_header_index(header, f"rater{n}") for n in (1, 2, 3))
        if idx is not None
    ]

    if responses_idx is None or not rater_idxs:
        good = common = 0
    else:
        labels = [
            cambridge_gold_label(
                row, responses_idx=responses_idx, rater_idxs=rater_idxs
            )
            for row in body
        ]
        good = sum(1 for label in labels if label == "good")
        common = sum(1 for label in labels if label == "common")

    return {
        "filename": source.filename,
        "sha256": digest,
        "sha256_expected": source.sha256,
        "sha256_match": digest == source.sha256,
        "rows": len(body),
        "rows_expected": source.expected_rows,
        "row_count_match": len(body) == source.expected_rows,
        "columns": header,
        "columns_expected": list(CAMBRIDGE_EXPECTED_COLUMNS),
        "columns_match": header == list(CAMBRIDGE_EXPECTED_COLUMNS),
        "gold_good": good,
        "gold_common": common,
        "gold_good_expected": source.expected_good,
        "gold_common_expected": source.expected_common,
        "gold_counts_match": (
            good == source.expected_good and common == source.expected_common
        ),
        "license": CAMBRIDGE_LICENSE,
        "source_uri": source_uri,
    }


def _audit_one_cambridge(
    source: CambridgeSource,
    *,
    fetch: Callable[[str], bytes] = fetch_bytes,
    force_download: bool = False,
) -> dict[str, Any]:
    try:
        data = ensure_cambridge_raw(source, fetch=fetch, force_download=force_download)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise CambridgeUnavailableError(f"{source.filename}: {exc}") from exc
    source_uri = CAMBRIDGE_BASE + urllib.parse.quote(source.filename)
    return _build_cambridge_entry(source, data, source_uri=source_uri)


# --- Ocsai (fetch-and-measure only, never redistributed) ---------------------

_OCSAI_PROMPT_PREFIX: Final[str] = "AUT Prompt:"
_OCSAI_PROMPT_SUFFIX: Final[str] = "\nScore:\n"
_OCSAI_RESPONSE_MARKER: Final[str] = "\nResponse:"


def parse_ocsai_prompt(prompt: str, completion: str) -> tuple[str, str, int] | None:
    r"""Parse one ``{prompt, completion}`` record into ``(object, response, score)``.

    Returns ``None`` if the fixed ``AUT Prompt:<object>\nResponse:<text>\nScore:``
    template (design-final.md Sec.3) does not match, or ``completion`` is not
    an integer.
    """
    if not (
        prompt.startswith(_OCSAI_PROMPT_PREFIX)
        and prompt.endswith(_OCSAI_PROMPT_SUFFIX)
    ):
        return None
    middle = prompt[len(_OCSAI_PROMPT_PREFIX) : -len(_OCSAI_PROMPT_SUFFIX)]
    marker_idx = middle.find(_OCSAI_RESPONSE_MARKER)
    if marker_idx < 0:
        return None
    object_name = middle[:marker_idx]
    response = middle[marker_idx + len(_OCSAI_RESPONSE_MARKER) :]
    try:
        score = int(completion.strip())
    except ValueError:
        return None
    return object_name, response, score


_OCSAI_COMMON_SCORE: Final[int] = 10
_OCSAI_GOOD_MIN_SCORE: Final[int] = 40


def ocsai_gold_label(score: int) -> str | None:
    """Binarise one Ocsai score (encoded 1-50) per design-final.md Sec.3.3."""
    if score == _OCSAI_COMMON_SCORE:
        return "common"
    if score >= _OCSAI_GOOD_MIN_SCORE:
        return "good"
    return None


def _parse_ocsai_bytes(data: bytes) -> tuple[list[tuple[str, str, int]], int]:
    records: list[tuple[str, str, int]] = []
    failures = 0
    for line in data.decode("utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            failures += 1
            continue
        parsed = parse_ocsai_prompt(obj.get("prompt", ""), obj.get("completion", ""))
        if parsed is None:
            failures += 1
            continue
        records.append(parsed)
    return records, failures


def _fetch_ocsai_splits(
    *, fetch: Callable[[str], bytes] = fetch_bytes
) -> dict[str, bytes]:
    """Fetch all three Ocsai splits into memory. Never written to the repo tree."""
    return {
        source.split: fetch(OCSAI_BASE + source.filename) for source in OCSAI_SOURCES
    }


def _build_ocsai_entry(splits_data: dict[str, bytes]) -> dict[str, Any]:
    splits_report: dict[str, Any] = {}
    all_records: list[tuple[str, str, int]] = []
    total_failures = 0
    for source in OCSAI_SOURCES:
        raw = splits_data[source.split]
        digest = sha256_hex(raw)
        records, failures = _parse_ocsai_bytes(raw)
        all_records.extend(records)
        total_failures += failures
        n_lines = sum(1 for line in raw.decode("utf-8").splitlines() if line.strip())
        splits_report[source.split] = {
            "filename": source.filename,
            "sha256": digest,
            "sha256_expected": source.sha256,
            "sha256_match": digest == source.sha256,
            "rows": n_lines,
        }

    totals: Counter[str] = Counter()
    goods: Counter[str] = Counter()
    commons: Counter[str] = Counter()
    for object_name, _response, score in all_records:
        totals[object_name] += 1
        label = ocsai_gold_label(score)
        if label == "good":
            goods[object_name] += 1
        elif label == "common":
            commons[object_name] += 1

    distinct_objects = sorted(totals)
    by_object = {
        name: {"total": totals[name], "good": goods[name], "common": commons[name]}
        for name in distinct_objects
    }
    good_total = sum(goods.values())
    common_total = sum(commons.values())

    return {
        "status": "ok",
        "splits": splits_report,
        "total_rows": len(all_records),
        "total_rows_expected": EXPECTED_OCSAI_TOTAL_ROWS,
        "row_count_match": len(all_records) == EXPECTED_OCSAI_TOTAL_ROWS,
        "parse_failures": total_failures,
        "parse_failures_expected": EXPECTED_OCSAI_PARSE_FAILURES,
        "parse_failures_match": total_failures == EXPECTED_OCSAI_PARSE_FAILURES,
        "distinct_objects": len(distinct_objects),
        "distinct_objects_expected": EXPECTED_OCSAI_DISTINCT_OBJECTS,
        "distinct_objects_match": len(distinct_objects)
        == EXPECTED_OCSAI_DISTINCT_OBJECTS,
        "gold_pool_good": good_total,
        "gold_pool_common": common_total,
        "gold_pool_good_expected": EXPECTED_OCSAI_POOL_GOOD,
        "gold_pool_common_expected": EXPECTED_OCSAI_POOL_COMMON,
        "gold_counts_match": (
            good_total == EXPECTED_OCSAI_POOL_GOOD
            and common_total == EXPECTED_OCSAI_POOL_COMMON
        ),
        "by_object": by_object,
        "license": OCSAI_LICENSE,
        "source_uris": [OCSAI_BASE + source.filename for source in OCSAI_SOURCES],
    }


def _audit_ocsai(*, fetch: Callable[[str], bytes] = fetch_bytes) -> dict[str, Any]:
    """Build the Ocsai audit, or record ``source_unavailable`` (never crash, exit 0)."""
    try:
        splits_data = _fetch_ocsai_splits(fetch=fetch)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"status": "source_unavailable", "error": str(exc)}
    return _build_ocsai_entry(splits_data)


# --- NOTICE.md (CC BY-NC-ND 4.0 Sec.3(a) attribution) -------------------------

NOTICE_TEXT: Final[str] = (
    # Kept byte-identical to the committed
    # experiments/20260907-paper01-g1/data/raw/NOTICE.md, pinned by
    # test_notice_text_matches_committed_notice_file. Codex TASK-POST
    # MEDIUM-4 (2026-09-08): re-running this script used to silently revert
    # the corrected CC BY-NC-ND 4.0 Sec.3(a) creator attribution.
    "# NOTICE -- Cambridge-AUT-dataset attribution (CC BY-NC-ND 4.0)\n"
    "\n"
    "This directory redistributes the following two files unmodified,\n"
    "byte-for-byte, from the Cambridge-AUT-dataset repository, under the\n"
    "scope permitted by CC BY-NC-ND 4.0 Sec.2(a)(1)(A). The four elements\n"
    "below satisfy the Sec.3(a) attribution requirement.\n"
    "\n"
    "- `bowl AUT dataset.xlsx`\n"
    "- `paperclip AUT dataset.xlsx`\n"
    "\n"
    "## Creator (作成者)\n"
    "\n"
    "Luning Sun, Hongyi Gu, Rebecca Myers, Zheng Yuan\n"
    "\n"
    "(Verified 2026-09-08 against the dataset repository's own README, which\n"
    "names the four authors in full. An earlier revision of this file guessed\n"
    'the initials as "Y. Sun, X. Gu, S. M. Myers, D. Yuan" -- that was wrong,\n'
    "and under Sec.3(a) the creator attribution is a licence condition, not a\n"
    "courtesy, so it is corrected here.)\n"
    "\n"
    "## Copyright notice (著作権表示)\n"
    "\n"
    "© Luning Sun, Hongyi Gu, Rebecca Myers, Zheng Yuan. Cite as:\n"
    "Sun, L., Gu, H., Myers, R., & Yuan, Z. A New Dataset and Method for\n"
    "Creativity Assessment Using the Alternate Uses Task. In: Intelligent\n"
    "Computers, Algorithms, and Applications (BenchCouncil IC 2023, Revised\n"
    "Selected Papers), CCIS vol. 2036, pp. 125-138, Springer Singapore, 2024.\n"
    "DOI: 10.1007/978-981-97-0065-3_9\n"
    "(The conference IC 2023 was held in 2023; the CCIS Revised Selected\n"
    "Papers volume carries 2024 -- both years appear in the record.)\n"
    "\n"
    "## License reference URI (ライセンス参照 URI)\n"
    "\n"
    "https://creativecommons.org/licenses/by-nc-nd/4.0/\n"
    "\n"
    "## Original source URI (原典 URI)\n"
    "\n"
    "https://github.com/ghydsgaaa/Cambridge-AUT-dataset\n"
    "(raw file base: https://raw.githubusercontent.com/ghydsgaaa/Cambridge-AUT-dataset/main/data/)\n"
)


def write_notice(path: Path = NOTICE_PATH) -> None:
    """Write the static CC BY-NC-ND 4.0 attribution NOTICE (no network needed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(NOTICE_TEXT, encoding="utf-8")


# --- decision rule (the real judgment path AC 001-5 pins) --------------------


def _evaluate_cambridge(audit: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for key, entry in audit["cambridge"].items():
        if not entry["sha256_match"]:
            problems.append(f"cambridge/{key}: sha256 mismatch")
        if not entry["row_count_match"]:
            problems.append(
                f"cambridge/{key}: row count mismatch"
                f" (got {entry['rows']}, expected {entry['rows_expected']})"
            )
        if not entry["columns_match"]:
            problems.append(f"cambridge/{key}: columns mismatch")
        if not entry["gold_counts_match"]:
            problems.append(f"cambridge/{key}: gold class counts mismatch")
    return problems


def _evaluate_ocsai(audit: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    ocsai = audit["ocsai"]
    if ocsai["status"] == "ok":
        for split, entry in ocsai["splits"].items():
            if not entry["sha256_match"]:
                problems.append(f"ocsai/{split}: sha256 mismatch")
        if not ocsai["row_count_match"]:
            problems.append("ocsai: total row count mismatch")
        if not ocsai["distinct_objects_match"]:
            problems.append("ocsai: distinct object count mismatch")
        if not ocsai["parse_failures_match"]:
            problems.append("ocsai: parse failure count mismatch")
        if not ocsai["gold_counts_match"]:
            problems.append("ocsai: gold pool class counts mismatch")
    elif ocsai["status"] != "source_unavailable":
        problems.append(f"ocsai: unexpected status {ocsai['status']!r}")
    return problems


def evaluate_audit(audit: dict[str, Any]) -> list[str]:
    """Return mismatch descriptions for ``audit``; ``[]`` means every pin held."""
    return _evaluate_cambridge(audit) + _evaluate_ocsai(audit)


def exit_code_for(audit: dict[str, Any]) -> int:
    """Return the exit code for ``audit``: 0 clean, 1 a pinned count/hash drifted."""
    return 1 if evaluate_audit(audit) else 0


# --- top-level orchestration --------------------------------------------------


def build_audit(
    *,
    fetch: Callable[[str], bytes] = fetch_bytes,
    force_download: bool = False,
) -> dict[str, Any]:
    """Fetch both corpora and assemble the audit dict.

    May raise ``CambridgeUnavailableError``.
    """
    cambridge = {
        source.key: _audit_one_cambridge(
            source, fetch=fetch, force_download=force_download
        )
        for source in CAMBRIDGE_SOURCES
    }
    ocsai = _audit_ocsai(fetch=fetch)
    audit: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "cambridge": cambridge,
        "ocsai": ocsai,
    }
    audit["mismatches"] = evaluate_audit(audit)
    if audit["mismatches"]:
        audit["overall_status"] = "mismatch"
    elif ocsai["status"] == "source_unavailable":
        audit["overall_status"] = "ocsai_unavailable"
    else:
        audit["overall_status"] = "ok"
    return audit


def main() -> int:
    """Fetch, audit, and report; return the process exit code (see module docstring)."""
    write_notice()

    try:
        audit = build_audit()
    except CambridgeUnavailableError as exc:
        sys.stderr.write(f"[paper01-fetch] Cambridge source unavailable: {exc}\n")
        return 1

    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if audit["mismatches"]:
        sys.stderr.write(
            "[paper01-fetch] mismatch against gate0-record.md pinned values:\n"
        )
        for problem in audit["mismatches"]:
            sys.stderr.write(f"  - {problem}\n")
        return 1

    status = audit["overall_status"]
    sys.stdout.write(
        f"[paper01-fetch] audit written to {AUDIT_PATH} (status={status})\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
