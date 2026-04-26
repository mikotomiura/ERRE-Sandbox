"""SQLite snapshot summariser for the M7 Slice δ live acceptance bundle.

Exists because γ's ad-hoc ``run-01.db_summary.json`` covered only
``relational_memory`` / ``dialog_turns`` row counts — δ adds three new
surface fields (``semantic_memory.belief_kind`` / ``.confidence`` /
``RelationshipBond.last_interaction_zone``) that the live acceptance
gate must observe end-to-end. This script reads the run's SQLite DB
after the orchestrator exits and emits a JSON summary that maps to the
acceptance gates documented in
``.steering/20260426-m7-slice-delta/observation.md`` "Live G-GEAR run
(pending)".

Note: ``RelationshipBond.last_interaction_zone`` is in-memory only
(AgentState-resident, not DB-backed — see C1 commit message). To verify
that field the run journal (``run-01.jsonl``) is the source of truth;
this script flags whether any ``agent_update`` envelope in the journal
carries a non-null ``last_interaction_zone`` on a bond.

Usage::

    uv run python .steering/20260426-m7-slice-delta/evidence/_db_summary_m7d.py \\
        --db var/run-delta.db \\
        --journal .steering/20260426-m7-slice-delta/run-01-delta/run-01.jsonl \\
        --out .steering/20260426-m7-slice-delta/run-01-delta/run-01.db_summary.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def _row_to_dict(row: sqlite3.Row) -> dict[str, object]:
    return {k: row[k] for k in row.keys()}


def summarise_db(db_path: Path) -> dict[str, object]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    out: dict[str, object] = {}

    # Counts across the four memory tables + dialog_turns.
    table_counts: dict[str, int] = {}
    for table in (
        "episodic_memory",
        "semantic_memory",
        "procedural_memory",
        "relational_memory",
        "dialog_turns",
    ):
        try:
            n = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]  # noqa: S608 — table set is closed
        except sqlite3.OperationalError:
            n = -1  # table missing
        table_counts[table] = int(n)
    out["table_counts"] = table_counts

    # δ acceptance: semantic_memory rows with belief_kind populated.
    try:
        belief_rows = conn.execute(
            "SELECT id, agent_id, belief_kind, confidence, content "
            "FROM semantic_memory WHERE belief_kind IS NOT NULL "
            "ORDER BY agent_id, id"
        ).fetchall()
        out["belief_promotions"] = [
            {
                "id": r["id"],
                "agent_id": r["agent_id"],
                "belief_kind": r["belief_kind"],
                "confidence": float(r["confidence"]),
                "content": r["content"],
            }
            for r in belief_rows
        ]
    except sqlite3.OperationalError as exc:
        out["belief_promotions_error"] = str(exc)

    # Sample dialog turns (mirror γ db_summary shape).
    try:
        turn_rows = conn.execute(
            "SELECT speaker_persona_id AS speaker, "
            "addressee_persona_id AS addressee, "
            "turn_index, utterance "
            "FROM dialog_turns ORDER BY tick, turn_index LIMIT 10"
        ).fetchall()
        out["sample_dialog_turns"] = [_row_to_dict(r) for r in turn_rows]
    except sqlite3.OperationalError as exc:
        out["sample_dialog_turns_error"] = str(exc)

    conn.close()
    return out


def summarise_journal(journal_path: Path) -> dict[str, object]:
    """Inspect agent_update envelopes for δ-specific fields the DB cannot show.

    ``RelationshipBond.last_interaction_zone`` and
    ``Physical.emotional_conflict`` live on AgentState (per-tick in-memory,
    snapshot to ``agent_update`` envelopes), not in any SQLite table.
    """
    if not journal_path.exists():
        return {"journal_error": f"journal not found at {journal_path}"}

    bonds_with_zone = 0
    bonds_total = 0
    max_emotional_conflict = 0.0
    affinity_signs: dict[str, int] = {"positive": 0, "zero": 0, "negative": 0}
    last_zone_examples: list[dict[str, object]] = []
    with journal_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                env = json.loads(line)
            except json.JSONDecodeError:
                continue
            if env.get("kind") != "agent_update":
                continue
            state = env.get("agent_state") or {}
            physical = state.get("physical") or {}
            ec = float(physical.get("emotional_conflict", 0.0))
            max_emotional_conflict = max(max_emotional_conflict, ec)
            for bond in state.get("relationships") or []:
                bonds_total += 1
                aff = float(bond.get("affinity", 0.0))
                if aff > 0:
                    affinity_signs["positive"] += 1
                elif aff < 0:
                    affinity_signs["negative"] += 1
                else:
                    affinity_signs["zero"] += 1
                zone = bond.get("last_interaction_zone")
                if zone:
                    bonds_with_zone += 1
                    if len(last_zone_examples) < 5:
                        last_zone_examples.append(
                            {
                                "agent_id": state.get("agent_id"),
                                "other_agent_id": bond.get("other_agent_id"),
                                "affinity": aff,
                                "last_interaction_zone": zone,
                                "ichigo_ichie_count": bond.get("ichigo_ichie_count"),
                            }
                        )
    return {
        "bonds_total_observed": bonds_total,
        "bonds_with_last_interaction_zone": bonds_with_zone,
        "max_emotional_conflict_observed": round(max_emotional_conflict, 4),
        "affinity_sign_distribution": affinity_signs,
        "last_zone_examples": last_zone_examples,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--journal", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    db_path = Path(args.db)
    journal_path = Path(args.journal)
    out_path = Path(args.out)

    summary: dict[str, object] = {"db": summarise_db(db_path)}
    summary["journal"] = summarise_journal(journal_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
