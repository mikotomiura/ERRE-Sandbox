"""Phase 2 run0 wall-timeout rescue verify (ME-9 確定アクション #1).

Verifies that the `*_natural_run0.duckdb.tmp` survivors from the
2026-05-06 Phase 2 wall-timeout incident remain readable as DuckDB and
that their (focal, total) counts match the values recorded in the Mac
side incident report (blockers.md ME-9 active incident block).

Usage (CWD = repo root):

    uv run python scripts/p3_run0_rescue_verify.py
    uv run python scripts/p3_run0_rescue_verify.py --out path/to/report.json

The script is non-destructive: it only opens DuckDB files in read-only
mode and writes a single JSON report. It does NOT rename `.tmp` to
`.duckdb`, does NOT relaunch capture, and does NOT touch the source
files. See `.steering/20260430-m9-eval-system/g-gear-rescue-verify-prompt.md`
for the full procedure (Step 1-5) and Codex H4 rescue caveats.
"""

from __future__ import annotations

import argparse
import datetime
import json
import socket
from pathlib import Path

import duckdb

EXPECTED = {
    "kant": {"focal": 381, "total": 1158},
    "nietzsche": {"focal": 390, "total": 1169},
    "rikyu": {"focal": 399, "total": 1182},
}

SEARCH_BASES = ("data/eval/golden", "data/eval/phase2")
MEMORY_GLOB = "data/eval/_natural_memory/p3*_natural_*_run0.sqlite"


def collect_candidates() -> list[tuple[str, Path]]:
    candidates: list[tuple[str, Path]] = []
    for base in SEARCH_BASES:
        for persona in EXPECTED:
            for suffix in (".duckdb.tmp", ".duckdb"):
                p = Path(base) / f"{persona}_natural_run0{suffix}"
                if p.exists():
                    candidates.append((persona, p))
    return candidates


def verify_cell(persona: str, path: Path) -> dict:
    info: dict = {
        "persona": persona,
        "path": path.as_posix(),
        "size_bytes": path.stat().st_size,
        "wal_exists": path.with_suffix(path.suffix + ".wal").exists(),
        "expected_focal": EXPECTED[persona]["focal"],
        "expected_total": EXPECTED[persona]["total"],
    }
    try:
        con = duckdb.connect(str(path), read_only=True)
        total = con.execute("SELECT COUNT(*) FROM raw_dialog.dialog").fetchone()[0]
        focal = con.execute(
            "SELECT COUNT(*) FROM raw_dialog.dialog WHERE speaker_persona_id = ?",
            [persona],
        ).fetchone()[0]
        max_tick = con.execute("SELECT MAX(tick) FROM raw_dialog.dialog").fetchone()[0]
        run_ids = con.execute("SELECT DISTINCT run_id FROM raw_dialog.dialog").fetchall()
        dc = con.execute(
            "SELECT COUNT(DISTINCT dialog_id) FROM raw_dialog.dialog"
        ).fetchone()[0]
        zones = con.execute(
            "SELECT zone, COUNT(*) FROM raw_dialog.dialog "
            "GROUP BY zone ORDER BY 2 DESC"
        ).fetchall()
        con.close()
        info.update(
            {
                "read_ok": True,
                "actual_total": total,
                "actual_focal": focal,
                "dialog_count": dc,
                "max_tick": max_tick,
                "run_ids": [r[0] for r in run_ids],
                "zones": [list(z) for z in zones],
                "focal_match": focal == EXPECTED[persona]["focal"],
                "total_match": total == EXPECTED[persona]["total"],
            }
        )
    except Exception as exc:  # noqa: BLE001
        info.update({"read_ok": False, "error": f"{type(exc).__name__}: {exc!s}"})
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_out = Path(
        "data/eval/partial-stash-2026-05-06/p3_run0_rescue_report.json"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=default_out,
        help=f"output JSON path (default: {default_out.as_posix()})",
    )
    args = parser.parse_args()

    candidates = collect_candidates()
    print(f"=== {len(candidates)} candidate file(s) ===")

    report: dict = {
        "verified_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "host": socket.gethostname(),
        "cells": [],
    }

    for persona, path in candidates:
        info = verify_cell(persona, path)
        report["cells"].append(info)
        print(json.dumps(info, ensure_ascii=False, indent=2))

    print("\n=== memory sqlite ===")
    report["memory_sqlite"] = []
    for mp in sorted(Path().glob(MEMORY_GLOB)):
        info = {"path": mp.as_posix(), "size_bytes": mp.stat().st_size}
        report["memory_sqlite"].append(info)
        print(json.dumps(info, ensure_ascii=False))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n=== report saved: {args.out.as_posix()} ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
