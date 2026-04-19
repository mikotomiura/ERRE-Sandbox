"""CLI entry point: ``python -m erre_sandbox`` or ``erre-sandbox``.

Keeps CLI parsing and ``asyncio.run`` bookkeeping here so that
:func:`erre_sandbox.bootstrap.bootstrap` stays argv-agnostic and
directly unit-testable.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from erre_sandbox.bootstrap import BootConfig, bootstrap


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="erre-sandbox",
        description="ERRE-Sandbox orchestrator (MVP: 1 Kant walker on peripatos).",
    )
    parser.add_argument("--host", default="0.0.0.0")  # noqa: S104 — LAN only
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", dest="db_path", default="var/kant.db")
    parser.add_argument("--chat-model", default="qwen3:8b")
    parser.add_argument("--embed-model", default="nomic-embed-text")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument(
        "--skip-health-check",
        dest="check_ollama",
        action="store_false",
        default=True,
        help="Skip Ollama /api/tags probe at startup (CI / offline tests).",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=("debug", "info", "warning", "error", "critical"),
    )
    return parser


def cli(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    cfg = BootConfig(
        host=args.host,
        port=args.port,
        db_path=args.db_path,
        chat_model=args.chat_model,
        embed_model=args.embed_model,
        ollama_url=args.ollama_url,
        check_ollama=args.check_ollama,
        log_level=args.log_level,
    )
    try:
        asyncio.run(bootstrap(cfg))
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(cli())
