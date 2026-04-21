"""One-shot envelope stream probe for the M6 Research Observatory live check.

Connects to ``ws://<gateway>:8000/ws/observe``, performs the 0.4.0-m6
handshake (advertises the two new consumer capabilities reasoning_trace /
reflection_event), and appends every incoming envelope as a JSON line to
the supplied log path. Exits cleanly after ``--duration`` seconds.

Separate from the M4 / M5 probes because the handshake capabilities
differ: M6 consumers must advertise the new envelope kinds so the gateway
is confident the researcher's viewer speaks the bumped schema.

Usage::

    uv run python .steering/20260421-m6-observatory/evidence/_stream_probe_m6.py \
        --url ws://g-gear.local:8000/ws/observe \
        --duration 120 \
        --out .steering/20260421-m6-observatory/evidence/logs/live-$(date -u +%Y%m%d-%H%M%S).jsonl

After the probe exits, summarise counts per envelope kind with
``jq`` or the M6 acceptance helper that lives alongside this script.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import websockets


SCHEMA_VERSION = "0.4.0-m6"


def _client_handshake() -> str:
    return json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            "tick": 0,
            "sent_at": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "kind": "handshake",
            "peer": "macbook-m6-probe",
            "capabilities": [
                "handshake",
                "agent_update",
                "speech",
                "move",
                "animation",
                "world_tick",
                "error",
                "dialog_initiate",
                "dialog_turn",
                "dialog_close",
                # M6 additions — producer may gate routing on these
                "reasoning_trace",
                "reflection_event",
            ],
        }
    )


async def _keepalive(ws, deadline: float, interval_s: float) -> None:
    while time.monotonic() < deadline:
        try:
            await asyncio.sleep(interval_s)
        except asyncio.CancelledError:
            return
        if time.monotonic() >= deadline:
            return
        try:
            await ws.send(_client_handshake())
        except Exception:
            return


async def tail(url: str, out_path: Path, duration_s: float) -> dict[str, int]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    async with websockets.connect(url, max_size=None) as ws:
        server_hs = await asyncio.wait_for(ws.recv(), timeout=5.0)
        await ws.send(_client_handshake())
        deadline = time.monotonic() + duration_s
        ka = asyncio.create_task(_keepalive(ws, deadline, 30.0))
        with out_path.open("w", encoding="utf-8") as fh:
            fh.write(
                json.dumps({"_probe": "server_handshake", "raw": server_hs}) + "\n"
            )
            try:
                while time.monotonic() < deadline:
                    remaining = deadline - time.monotonic()
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=remaining)
                    except asyncio.TimeoutError:
                        break
                    try:
                        obj = json.loads(msg)
                        kind = obj.get("kind", "?")
                        counts[kind] = counts.get(kind, 0) + 1
                        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
                    except json.JSONDecodeError:
                        fh.write(msg + "\n")
            finally:
                ka.cancel()
                with contextlib.suppress(BaseException):
                    await ka
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="ws://g-gear.local:8000/ws/observe")
    parser.add_argument("--duration", type=float, default=120.0)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out_path = Path(args.out)
    started = time.time()
    counts = asyncio.run(tail(args.url, out_path, args.duration))
    elapsed = time.time() - started
    total = sum(counts.values())
    summary = {
        "url": args.url,
        "out": str(out_path),
        "duration_s": args.duration,
        "elapsed_s": round(elapsed, 2),
        "envelope_total": total,
        "envelope_per_kind": counts,
    }
    # Print human summary and a machine-readable line on stdout.
    print(json.dumps(summary, ensure_ascii=False))
    summary_path = out_path.with_suffix(out_path.suffix + ".summary.json")
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
