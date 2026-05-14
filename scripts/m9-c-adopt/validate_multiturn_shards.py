r"""Post-capture validation query for multi-turn pilot shards.

Codex HIGH-4 reflection (m9-c-adopt-pilot-multiturn investigation,
2026-05-14): DA-13 publish precondition. Runs 4 SQL checks against each
shard in --shards-glob and aggregates pass/fail into a JSON artefact:

  Check 1: speaker_persona_id × turn_index distribution (alternation)
  Check 2: focal count ≈ focal target (within ±5%)
  Check 3: incomplete dialog detection (max-min+1 != count(*))
  Check 4: focal-only consumer simulation count

Exit 0 if all shards PASS, 1 if any FAIL.

Usage::

    python scripts/m9-c-adopt/validate_multiturn_shards.py \\
        --persona kant --focal-target 300 \\
        --shards-glob "data/eval/m9-c-adopt-tier-b-pilot-multiturn/*.duckdb" \\
        --output .steering/20260514-m9-c-adopt-pilot-multiturn/validation-multiturn-kant.json
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

import duckdb


def _validate_shard(path: Path, persona_id: str, focal_target: int) -> dict:
    con = duckdb.connect(str(path), read_only=True)
    try:
        # Check 1: distribution
        dist_rows = con.execute(
            "SELECT speaker_persona_id, turn_index, count(*) FROM raw_dialog.dialog"
            " GROUP BY 1, 2 ORDER BY 1, 2"
        ).fetchall()
        dist = [
            {
                "speaker_persona_id": str(r[0]),
                "turn_index": int(r[1]),
                "count": int(r[2]),
            }
            for r in dist_rows
        ]
        # focal speaker should ONLY appear on even turn_index (0, 2, ...)
        # interlocutor (_stimulus) should ONLY appear on odd (1, 3, ...)
        check1_violations = []
        for entry in dist:
            sp = entry["speaker_persona_id"]
            ti = entry["turn_index"]
            if sp == persona_id and ti % 2 != 0:
                check1_violations.append(f"focal on odd turn_index={ti}")
            if sp != persona_id and ti % 2 == 0:
                check1_violations.append(f"non-focal {sp!r} on even turn_index={ti}")
        check1_pass = len(check1_violations) == 0

        # Check 2: focal count vs target
        focal_count = int(
            con.execute(
                "SELECT count(*) FROM raw_dialog.dialog WHERE speaker_persona_id = ?",
                (persona_id,),
            ).fetchone()[0]
        )
        focal_lower = int(focal_target * 0.95)
        focal_upper = int(focal_target * 1.05)
        check2_pass = focal_lower <= focal_count <= focal_upper

        # Check 3: incomplete dialog (turn_index gaps within a dialog_id)
        incomplete_rows = con.execute(
            "SELECT dialog_id, min(turn_index), max(turn_index), count(*)"
            " FROM raw_dialog.dialog"
            " GROUP BY dialog_id"
            " HAVING max(turn_index) - min(turn_index) + 1 != count(*)"
        ).fetchall()
        check3_pass = len(incomplete_rows) == 0
        check3_violations = [
            {
                "dialog_id": str(r[0]),
                "min_t": int(r[1]),
                "max_t": int(r[2]),
                "count": int(r[3]),
            }
            for r in incomplete_rows
        ]

        # Check 4: focal-only consumer simulation
        non_focal_count = int(
            con.execute(
                "SELECT count(*) FROM raw_dialog.dialog WHERE speaker_persona_id != ?",
                (persona_id,),
            ).fetchone()[0]
        )
        total_count = int(
            con.execute("SELECT count(*) FROM raw_dialog.dialog").fetchone()[0]
        )
        # Consumer SELECT WHERE speaker_persona_id = persona — non-focal rows
        # are excluded; we just record the count for transparency.

        all_pass = check1_pass and check2_pass and check3_pass
        return {
            "shard": path.name,
            "all_pass": all_pass,
            "checks": {
                "1_alternation": {
                    "pass": check1_pass,
                    "violations": check1_violations,
                    "distribution": dist,
                },
                "2_focal_count": {
                    "pass": check2_pass,
                    "focal_count": focal_count,
                    "target": focal_target,
                    "tolerance_band": [focal_lower, focal_upper],
                },
                "3_incomplete_dialog": {
                    "pass": check3_pass,
                    "violations": check3_violations,
                },
                "4_focal_only_consumer": {
                    "focal_count": focal_count,
                    "non_focal_count": non_focal_count,
                    "total_count": total_count,
                },
            },
        }
    finally:
        con.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--persona", required=True)
    p.add_argument("--focal-target", type=int, required=True)
    p.add_argument("--shards-glob", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    shards = sorted(Path(s) for s in glob.glob(args.shards_glob))
    if not shards:
        print(f"ERROR: no shards matched {args.shards_glob}", file=sys.stderr)
        return 2

    results = [
        _validate_shard(shard, args.persona, args.focal_target) for shard in shards
    ]
    all_pass = all(r["all_pass"] for r in results)
    payload = {
        "persona": args.persona,
        "focal_target": args.focal_target,
        "shard_count": len(shards),
        "all_shards_pass": all_pass,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        f"{'PASS' if all_pass else 'FAIL'}: {sum(1 for r in results if r['all_pass'])}"
        f"/{len(results)} shards passed all 3 checks → {args.output}"
    )
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
