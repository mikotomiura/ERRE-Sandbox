"""SGLang adapter swap latency — CS-8 5 condition measurement.

Hits a running SGLang server on localhost:30000 (CS-1 launch v5) and
records latency for the five conditions enumerated in
``.steering/20260508-m9-c-spike/decisions.md`` §CS-8:

* ``cold_load``     — server has never seen the adapter; first POST
                       triggers weight materialisation + paging
* ``warm_reload``   — adapter was unloaded then re-loaded immediately
* ``pinned``        — adapter loaded with ``pinned=true`` and a chat
                       round-trip is measured against it
* ``unpinned``      — adapter loaded without ``pinned`` and a chat
                       round-trip is measured against it
* ``no_lora``       — same prompt against the base model (no adapter
                       routing)

Results land in JSONL at the path given by ``--out``. Each line is a
single condition observation with millisecond-resolution timing.
Repeat invocation appends; tooling downstream rolls up by condition.

Invoked from G-GEAR Windows or WSL2 — both are fine because the SGLang
server is reachable on localhost. Reads no project state, writes only
to ``--out``; safe to interrupt and re-run.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

DEFAULT_BASE_URL = "http://localhost:30000"
DEFAULT_PROMPT = "純粋理性と実践理性の関係を、あなた自身の語り口で簡潔に。"


def _post(client: httpx.Client, path: str, payload: dict) -> tuple[int, float, dict]:
    t0 = time.perf_counter()
    response = client.post(path, json=payload, timeout=120.0)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {"raw": response.text}
    return response.status_code, elapsed_ms, body


def _chat(client: httpx.Client, *, model: str, prompt: str) -> tuple[int, float, dict]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 256,
        "temperature": 0.7,
    }
    return _post(client, "/v1/chat/completions", payload)


def _emit(out: Path, record: dict) -> None:
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def run(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    client = httpx.Client(base_url=args.base_url)
    try:
        # 0. Make sure the adapter is not currently loaded so cold_load
        #    measures a real cold path.
        _post(
            client,
            "/unload_lora_adapter",
            {"lora_name": args.adapter_name},
        )

        # 1. cold_load
        for trial in range(args.trials):
            status, elapsed, body = _post(
                client,
                "/load_lora_adapter",
                {
                    "lora_name": args.adapter_name,
                    "lora_path": args.adapter_path,
                },
            )
            _emit(
                out,
                {
                    "condition": "cold_load",
                    "trial": trial,
                    "status": status,
                    "elapsed_ms": elapsed,
                    "body": body,
                    "ts": time.time(),
                },
            )
            _post(
                client,
                "/unload_lora_adapter",
                {"lora_name": args.adapter_name},
            )

        # 2. warm_reload — unload + reload pair, no other state changes
        _post(
            client,
            "/load_lora_adapter",
            {
                "lora_name": args.adapter_name,
                "lora_path": args.adapter_path,
            },
        )
        for trial in range(args.trials):
            _post(
                client,
                "/unload_lora_adapter",
                {"lora_name": args.adapter_name},
            )
            status, elapsed, body = _post(
                client,
                "/load_lora_adapter",
                {
                    "lora_name": args.adapter_name,
                    "lora_path": args.adapter_path,
                },
            )
            _emit(
                out,
                {
                    "condition": "warm_reload",
                    "trial": trial,
                    "status": status,
                    "elapsed_ms": elapsed,
                    "body": body,
                    "ts": time.time(),
                },
            )

        # 3. pinned — chat round-trip against pinned adapter
        _post(
            client,
            "/unload_lora_adapter",
            {"lora_name": args.adapter_name},
        )
        _post(
            client,
            "/load_lora_adapter",
            {
                "lora_name": args.adapter_name,
                "lora_path": args.adapter_path,
                "pinned": True,
            },
        )
        for trial in range(args.trials):
            status, elapsed, body = _chat(
                client,
                model=args.adapter_name,
                prompt=args.prompt,
            )
            _emit(
                out,
                {
                    "condition": "pinned",
                    "trial": trial,
                    "status": status,
                    "elapsed_ms": elapsed,
                    "body_keys": list(body.keys()) if isinstance(body, dict) else None,
                    "ts": time.time(),
                },
            )

        # 4. unpinned — same chat against unpinned adapter
        _post(
            client,
            "/unload_lora_adapter",
            {"lora_name": args.adapter_name},
        )
        _post(
            client,
            "/load_lora_adapter",
            {
                "lora_name": args.adapter_name,
                "lora_path": args.adapter_path,
            },
        )
        for trial in range(args.trials):
            status, elapsed, body = _chat(
                client,
                model=args.adapter_name,
                prompt=args.prompt,
            )
            _emit(
                out,
                {
                    "condition": "unpinned",
                    "trial": trial,
                    "status": status,
                    "elapsed_ms": elapsed,
                    "body_keys": list(body.keys()) if isinstance(body, dict) else None,
                    "ts": time.time(),
                },
            )

        # 5. no_lora — base model only
        _post(
            client,
            "/unload_lora_adapter",
            {"lora_name": args.adapter_name},
        )
        for trial in range(args.trials):
            status, elapsed, body = _chat(
                client,
                model=args.base_model,
                prompt=args.prompt,
            )
            _emit(
                out,
                {
                    "condition": "no_lora",
                    "trial": trial,
                    "status": status,
                    "elapsed_ms": elapsed,
                    "body_keys": list(body.keys()) if isinstance(body, dict) else None,
                    "ts": time.time(),
                },
            )
    finally:
        client.close()

    # CLI surface — stdout print is the documented user feedback channel.
    print(f"measure_latency: wrote 5 conditions × {args.trials} trial(s) to {out}")  # noqa: T201
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="measure_latency.py",
        description="CS-8 adapter swap latency 5 condition measurement",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"SGLang server URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--adapter-name",
        default="kant_r8_real",
        help="lora_name used in load/unload (default: kant_r8_real)",
    )
    parser.add_argument(
        "--adapter-path",
        required=True,
        help="lora_path the server should resolve",
    )
    parser.add_argument(
        "--base-model",
        default="qwen3-8b",
        help="model name for no_lora baseline (default: qwen3-8b)",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="chat prompt for pinned/unpinned/no_lora conditions",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=3,
        help="repeats per condition (default: 3)",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="output JSONL path (appended)",
    )
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
