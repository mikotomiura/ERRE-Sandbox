"""One-shot envelope stream probe for M4 live validation.

Connects to ``ws://127.0.0.1:8000/ws/observe`` (no subscribe filter = broadcast)
and appends every incoming envelope as a JSON line to the supplied log path.
Exits cleanly after ``--duration`` seconds.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import sys
import time
from pathlib import Path

import websockets


SCHEMA_VERSION = "0.2.0-m4"


def _client_handshake() -> str:
    from datetime import datetime, timezone

    return json.dumps(
        {
            "schema_version": SCHEMA_VERSION,
            "tick": 0,
            "sent_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "kind": "handshake",
            "peer": "macbook",
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


async def tail(url: str, out_path: Path, duration_s: float) -> int:
    count = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
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
                        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
                    except json.JSONDecodeError:
                        fh.write(msg + "\n")
                    count += 1
            finally:
                ka.cancel()
                with contextlib.suppress(BaseException):
                    await ka
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="ws://127.0.0.1:8000/ws/observe")
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out_path = Path(args.out)
    started = time.time()
    count = asyncio.run(tail(args.url, out_path, args.duration))
    elapsed = time.time() - started
    print(
        json.dumps(
            {
                "url": args.url,
                "out": str(out_path),
                "duration_s": args.duration,
                "elapsed_s": round(elapsed, 2),
                "envelope_count": count,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
