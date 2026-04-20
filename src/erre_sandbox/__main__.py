"""CLI entry point: ``python -m erre_sandbox`` or ``erre-sandbox``.

Keeps CLI parsing and ``asyncio.run`` bookkeeping here so that
:func:`erre_sandbox.bootstrap.bootstrap` stays argv-agnostic and
directly unit-testable.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path
from typing import Final

from erre_sandbox.bootstrap import BootConfig, bootstrap
from erre_sandbox.schemas import AgentSpec, PersonaSpec

try:
    import yaml
except ImportError:  # pragma: no cover — yaml is a hard dependency at runtime
    yaml = None  # type: ignore[assignment]


_PERSONA_ID_RE: Final[re.Pattern[str]] = re.compile(r"\A[a-z][a-z0-9_-]{0,63}\Z")
"""Allowed shape for a ``persona_id`` token passed on the CLI.

Tokens are joined with ``personas_dir`` to build a file path, so anything
containing ``..`` / ``/`` / null bytes / leading dots would allow reading
files outside the personas directory. This regex (lowercase alnum plus
``_`` and ``-``, leading letter, ≤64 chars) matches the existing persona
YAML filenames (``kant.yaml``, ``nietzsche.yaml``, ``rikyu.yaml``) and
forbids the rest.
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="erre-sandbox",
        description=(
            "ERRE-Sandbox orchestrator. Runs one Kant walker on the peripatos "
            "by default; pass --personas for the M4 3-agent configuration."
        ),
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
    parser.add_argument(
        "--personas-dir",
        default="personas",
        help="Directory containing <persona_id>.yaml files (default: personas/).",
    )
    parser.add_argument(
        "--personas",
        default=None,
        help=(
            "Comma-separated persona_ids to boot as parallel agents, e.g. "
            "'kant,nietzsche,rikyu'. Each persona's first preferred_zone is "
            "used as its initial_zone. Omit for the default 1-Kant config."
        ),
    )
    return parser


def _resolve_agents(
    personas_arg: str | None, personas_dir: Path
) -> tuple[AgentSpec, ...]:
    """Expand the ``--personas`` CLI value into a tuple of :class:`AgentSpec`.

    Returns an empty tuple when the argument is absent so
    :class:`BootConfig.__post_init__` can supply the 1-Kant default.
    Each referenced persona YAML must exist and parse; loud failure here
    is preferable to a confusing error mid-startup.
    """
    if personas_arg is None:
        return ()
    if yaml is None:
        msg = "PyYAML is required for --personas resolution but is not installed"
        raise RuntimeError(msg)
    ids = [token.strip() for token in personas_arg.split(",") if token.strip()]
    if not ids:
        return ()
    specs: list[AgentSpec] = []
    for pid in ids:
        if not _PERSONA_ID_RE.fullmatch(pid):
            # Reject anything that could escape ``personas_dir``. Accepting
            # path separators or ``..`` here would let CLI invokers load
            # arbitrary YAML files.
            raise SystemExit(
                f"--personas rejected {pid!r}: must match "
                f"{_PERSONA_ID_RE.pattern} (lowercase, alnum + _ -, ≤64 chars)",
            )
        path = personas_dir / f"{pid}.yaml"
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise SystemExit(
                f"--personas referenced {pid!r} but {path!s} does not exist",
            ) from exc
        persona = PersonaSpec.model_validate(yaml.safe_load(raw))
        if not persona.preferred_zones:
            raise SystemExit(
                f"Persona {pid!r} has no preferred_zones; cannot infer initial_zone",
            )
        specs.append(
            AgentSpec(persona_id=pid, initial_zone=persona.preferred_zones[0]),
        )
    return tuple(specs)


def cli(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    personas_dir = Path(args.personas_dir)
    agents = _resolve_agents(args.personas, personas_dir)
    cfg = BootConfig(
        host=args.host,
        port=args.port,
        db_path=args.db_path,
        chat_model=args.chat_model,
        embed_model=args.embed_model,
        ollama_url=args.ollama_url,
        check_ollama=args.check_ollama,
        log_level=args.log_level,
        personas_dir=personas_dir,
        agents=agents,
    )
    try:
        asyncio.run(bootstrap(cfg))
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(cli())
