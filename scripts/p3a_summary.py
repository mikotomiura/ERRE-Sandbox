"""Generate ``data/eval/pilot/_summary.json`` from P3a DuckDB captures.

Read-only over each ``data/eval/pilot/<persona>_<condition>_run<idx>.duckdb``
file produced by :mod:`erre_sandbox.cli.eval_run_golden`. The summary is the
hand-off artefact the Mac session reads in ``P3a-decide`` to compute
bootstrap CI width and update the ``ME-4`` ratio ADR; the live DuckDB files
themselves are .gitignored, so this JSON is the only commit-tracked
provenance of the pilot capture.

Usage::

    uv run python scripts/p3a_summary.py
    # → writes data/eval/pilot/_summary.json

The script discovers files by the ``<persona>_<condition>_run<idx>.duckdb``
filename glob (the ``run_id`` column inside each file is also asserted
to match, so a misnamed file is rejected loudly).
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any, Final

import duckdb

_PILOT_DIR: Final[Path] = Path("data/eval/pilot")
_SUMMARY_PATH: Final[Path] = _PILOT_DIR / "_summary.json"
_FILENAME_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<persona>[a-z]+)_(?P<condition>stimulus|natural)_run(?P<idx>\d+)\.duckdb$",
)


def _scalar_int(
    con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None
) -> int:
    """``SELECT`` an aggregate that always returns one row; coerce to ``int``."""
    cursor = con.execute(sql, params) if params is not None else con.execute(sql)
    row = cursor.fetchone()
    if row is None:
        msg = f"expected one row from {sql!r}, got None"
        raise RuntimeError(msg)
    return int(row[0])


def _summarize_one(db_path: Path) -> dict[str, Any]:
    """Return a single per-cell summary block for ``db_path``."""
    m = _FILENAME_RE.match(db_path.name)
    if m is None:
        msg = (
            f"unexpected filename {db_path.name!r}; "
            "cannot derive (persona, condition, run_idx)"
        )
        raise ValueError(msg)
    persona = m["persona"]
    condition = m["condition"]
    run_idx = int(m["idx"])
    expected_run_id = f"{persona}_{condition}_run{run_idx}"

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        run_ids = [
            row[0]
            for row in con.execute(
                "SELECT DISTINCT run_id FROM raw_dialog.dialog ORDER BY run_id"
            ).fetchall()
        ]
        total_rows = _scalar_int(con, "SELECT COUNT(*) FROM raw_dialog.dialog")
        focal_rows = _scalar_int(
            con,
            "SELECT COUNT(*) FROM raw_dialog.dialog WHERE speaker_persona_id = ?",
            [persona],
        )
        dialog_count = _scalar_int(
            con, "SELECT COUNT(DISTINCT dialog_id) FROM raw_dialog.dialog"
        )
        speaker_breakdown = dict(
            con.execute(
                "SELECT speaker_persona_id, COUNT(*) FROM raw_dialog.dialog"
                " GROUP BY speaker_persona_id ORDER BY speaker_persona_id"
            ).fetchall()
        )
        # utterance length stats — empty strings are kept (count toward 0-len)
        # so "0 chars" rows do not silently drop out of the median.
        utt_lens = [
            len(row[0] or "")
            for row in con.execute("SELECT utterance FROM raw_dialog.dialog").fetchall()
        ]
    finally:
        con.close()

    if total_rows > 0 and (len(run_ids) != 1 or run_ids[0] != expected_run_id):
        msg = (
            f"run_id mismatch in {db_path.name}: file has {run_ids!r},"
            f" expected exactly [{expected_run_id!r}]"
        )
        raise ValueError(msg)

    return {
        "file": db_path.name,
        "persona_id": persona,
        "condition": condition,
        "run_idx": run_idx,
        "run_id": expected_run_id,
        "total_rows": total_rows,
        "focal_rows": focal_rows,
        "dialog_count": dialog_count,
        "speaker_persona_breakdown": {
            str(k): int(v) for k, v in speaker_breakdown.items()
        },
        "utterance_chars_mean": (
            round(statistics.fmean(utt_lens), 2) if utt_lens else None
        ),
        "utterance_chars_median": (
            round(statistics.median(utt_lens), 2) if utt_lens else None
        ),
        "utterance_chars_max": max(utt_lens) if utt_lens else None,
    }


def main() -> int:
    if not _PILOT_DIR.is_dir():
        print(f"pilot directory not found: {_PILOT_DIR}", file=sys.stderr)  # noqa: T201
        return 1

    db_paths = sorted(
        p for p in _PILOT_DIR.glob("*.duckdb") if not p.name.endswith(".tmp")
    )
    if not db_paths:
        print(f"no DuckDB files found under {_PILOT_DIR}", file=sys.stderr)  # noqa: T201
        return 1

    cells = [_summarize_one(p) for p in db_paths]
    payload: dict[str, Any] = {
        "schema": "p3a_summary/v1",
        "pilot_dir": str(_PILOT_DIR).replace("\\", "/"),
        "cell_count": len(cells),
        "cells": cells,
    }
    _SUMMARY_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {_SUMMARY_PATH} ({len(cells)} cells)")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
