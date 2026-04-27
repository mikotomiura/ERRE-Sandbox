"""ζ-3 live acceptance — 4 numeric gates from envelope log.

Computed gates:
  1. MoveMsg.speed histogram — expected 3 modes 0.91 / 1.105 / 1.625
  2. cognition_tick_count per persona (reasoning_trace envelopes,
     persona_id stamp from ζ-2)
  3. proximity events / pair-distance close-encounter timeline
     (computed from agent_update.kinematics.position; raw Proximity
     envelopes are not on the wire — δ stayed in-memory only.)
  4. collapse check — XZ pair-distance < 0.4 m for ≥ 2 consecutive
     world_tick samples should be 0 occurrences (separation force).

Output: JSON next to run-01.jsonl, plus a short stdout summary.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path


def _persona_from_agent_id(agent_id: str) -> str:
    if not agent_id:
        return "unknown"
    return agent_id.removeprefix("a_").rsplit("_", 1)[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--journal", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--collapse-threshold-m",
        type=float,
        default=0.4,
        help="XZ pair-distance treated as collapse (m). Default 0.4 m matches _SEP_PUSH_M.",
    )
    args = parser.parse_args()

    journal_path = Path(args.journal)
    out_path = Path(args.out)

    move_speeds: Counter[float] = Counter()
    move_speed_by_persona: dict[str, Counter[float]] = defaultdict(Counter)
    reasoning_per_persona: Counter[str] = Counter()
    speech_per_persona: Counter[str] = Counter()
    move_per_persona: Counter[str] = Counter()
    agent_positions: dict[str, list[tuple[int, float, float]]] = defaultdict(list)
    last_tick_seen: int = -1

    with journal_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                env = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = env.get("kind")
            if kind == "move":
                speed = env.get("speed")
                if isinstance(speed, (int, float)):
                    rounded = round(float(speed), 6)
                    move_speeds[rounded] += 1
                    persona = _persona_from_agent_id(env.get("agent_id", ""))
                    move_speed_by_persona[persona][rounded] += 1
                    move_per_persona[persona] += 1
            elif kind == "reasoning_trace":
                trace = env.get("trace") or {}
                persona = trace.get("persona_id") or _persona_from_agent_id(
                    trace.get("agent_id", "")
                )
                reasoning_per_persona[persona] += 1
            elif kind == "speech":
                persona = _persona_from_agent_id(env.get("agent_id", ""))
                speech_per_persona[persona] += 1
            elif kind == "agent_update":
                state = env.get("agent_state") or {}
                pos = state.get("position") or {}
                tick = env.get("tick")
                if (
                    isinstance(pos, dict)
                    and "x" in pos
                    and "z" in pos
                    and isinstance(tick, int)
                ):
                    aid = state.get("agent_id") or env.get("agent_id")
                    if aid:
                        agent_positions[aid].append(
                            (tick, float(pos["x"]), float(pos["z"]))
                        )
                        last_tick_seen = max(last_tick_seen, tick)
            elif kind == "world_tick":
                t = env.get("tick")
                if isinstance(t, int):
                    last_tick_seen = max(last_tick_seen, t)

    # Build per-tick agent position map (use latest position seen at-or-before each tick).
    agents = sorted(agent_positions.keys())
    pair_distances_below_threshold: list[dict] = []
    pair_min_distance: dict[str, float] = {}
    pair_distance_runs: dict[str, int] = defaultdict(int)
    pair_distance_max_run: dict[str, int] = defaultdict(int)

    if len(agents) >= 2:
        # forward-fill: for each tick from min..last_tick_seen, use latest position
        # observed at-or-before the tick.
        cursors = {a: 0 for a in agents}
        latest = {a: None for a in agents}
        for tick in range(last_tick_seen + 1):
            for a in agents:
                samples = agent_positions[a]
                while (
                    cursors[a] < len(samples) and samples[cursors[a]][0] <= tick
                ):
                    latest[a] = (samples[cursors[a]][1], samples[cursors[a]][2])
                    cursors[a] += 1
            # Skip ticks before all 3 agents have at least one sample.
            if any(latest[a] is None for a in agents):
                continue
            for i in range(len(agents)):
                for j in range(i + 1, len(agents)):
                    a, b = agents[i], agents[j]
                    pa, pb = latest[a], latest[b]
                    dx = pa[0] - pb[0]
                    dz = pa[1] - pb[1]
                    dist = math.sqrt(dx * dx + dz * dz)
                    pair_key = f"{a}<>{b}"
                    pair_min_distance[pair_key] = min(
                        pair_min_distance.get(pair_key, math.inf), dist
                    )
                    if dist < args.collapse_threshold_m:
                        pair_distance_runs[pair_key] += 1
                        pair_distance_max_run[pair_key] = max(
                            pair_distance_max_run[pair_key],
                            pair_distance_runs[pair_key],
                        )
                        pair_distances_below_threshold.append(
                            {
                                "tick": tick,
                                "pair": pair_key,
                                "distance_m": round(dist, 4),
                            }
                        )
                    else:
                        pair_distance_runs[pair_key] = 0

    # Identify the 3 expected speed modes.
    expected_modes = {
        "rikyu": 0.91,
        "kant": 1.105,
        "nietzsche": 1.625,
    }

    # Per-persona dominant speed (mode of their move speeds).
    persona_dominant_speed: dict[str, float | None] = {}
    persona_speed_match: dict[str, bool] = {}
    for persona, hist in move_speed_by_persona.items():
        if not hist:
            persona_dominant_speed[persona] = None
            persona_speed_match[persona] = False
            continue
        dominant, _ = hist.most_common(1)[0]
        persona_dominant_speed[persona] = dominant
        expected = expected_modes.get(persona)
        persona_speed_match[persona] = (
            expected is not None and abs(dominant - expected) < 0.01
        )

    # Cognition ratio sanity: nietzsche > kant ≈ rikyu (loose).
    cog_n = reasoning_per_persona.get("nietzsche", 0)
    cog_k = reasoning_per_persona.get("kant", 0)
    cog_r = reasoning_per_persona.get("rikyu", 0)
    cognition_ordering_ok = cog_n > cog_k and cog_n > cog_r

    summary = {
        "schema": "zeta_live_analysis_v1",
        "journal": str(journal_path),
        "last_tick_seen": last_tick_seen,
        "move_speed_histogram": dict(
            sorted(((str(k), v) for k, v in move_speeds.items()), key=lambda kv: float(kv[0]))
        ),
        "move_speed_by_persona": {
            persona: dict(
                sorted(((str(k), v) for k, v in hist.items()), key=lambda kv: float(kv[0]))
            )
            for persona, hist in move_speed_by_persona.items()
        },
        "persona_dominant_speed": persona_dominant_speed,
        "persona_speed_match_expected": persona_speed_match,
        "expected_modes": expected_modes,
        "reasoning_trace_per_persona": dict(reasoning_per_persona),
        "speech_per_persona": dict(speech_per_persona),
        "move_per_persona": dict(move_per_persona),
        "cognition_ordering_ok_nietzsche_max": cognition_ordering_ok,
        "pair_min_distance_m": {
            k: round(v, 4) for k, v in pair_min_distance.items()
        },
        "pair_distance_max_consecutive_run_below_threshold": dict(
            pair_distance_max_run
        ),
        "pair_distance_below_threshold_count_total": sum(
            1 for _ in pair_distances_below_threshold
        ),
        "pair_distance_below_threshold_first_5": pair_distances_below_threshold[:5],
        "collapse_threshold_m": args.collapse_threshold_m,
        "agents_observed": agents,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    sys.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
