"""CLI entry point: ``python -m erre_sandbox`` or ``erre-sandbox``.

Keeps CLI parsing and ``asyncio.run`` bookkeeping here so that
:func:`erre_sandbox.bootstrap.bootstrap` stays argv-agnostic and
directly unit-testable.

As of M8 (L6-D1) the CLI supports sub-commands. The default sub-command is
``run`` (boot the orchestrator) so invocations without an explicit
sub-command keep working. The new ``export-log`` sub-command streams the
sqlite ``dialog_turns`` table as JSONL — see
``.steering/20260425-m8-episodic-log-pipeline/`` for the rationale.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path
from typing import Final

from erre_sandbox.bootstrap import BootConfig, bootstrap
from erre_sandbox.cli import baseline_metrics, export_log, scaling_metrics
from erre_sandbox.integration import protocol
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


_SUBCOMMANDS: Final[frozenset[str]] = frozenset(
    {"export-log", "baseline-metrics", "scaling-metrics"},
)
"""Sub-command tokens that divert dispatch away from the default ``run`` path.

Kept as an explicit set so the argv-0 dispatch in :func:`cli` stays a
readable ``in`` check rather than a mystery list of magic strings. Adding
a new sub-command means (a) listing the token here and (b) wiring its
register/run pair in :func:`cli`.
"""


def _build_run_parser() -> argparse.ArgumentParser:
    """Parser for the default ``run`` path (boot the orchestrator).

    Split from the sub-command parsers to avoid argparse's prefix-matching
    between root-level ``--personas`` and the ``export-log`` sub-command's
    ``--persona`` (observed 2026-04-24 when both lived on the root parser).
    """
    parser = argparse.ArgumentParser(
        prog="erre-sandbox",
        description=(
            "ERRE-Sandbox orchestrator. Runs one Kant walker on the peripatos "
            "by default; pass --personas for the M4 3-agent configuration. "
            "Use ``erre-sandbox export-log --help`` for the M8 L6-D1 log "
            "export sub-command."
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
    # SH-2 — WS connection-time auth gates. All three default to disabled
    # for back-compat (Mac↔G-GEAR LAN, no Origin / no token). ``bootstrap``
    # refuses to start with ``host=0.0.0.0`` plus all three gates off so a
    # bare ``--host=0.0.0.0`` cannot silently expose the server.
    parser.add_argument(
        "--ws-token",
        dest="ws_token",
        default=None,
        help=(
            "Explicit shared token for the WS endpoint. For tests only; "
            "production should populate var/secrets/ws_token (chmod 700) "
            "or the ERRE_WS_TOKEN env var so the token does not leak into "
            "shell history."
        ),
    )
    parser.add_argument(
        "--require-token",
        dest="require_token",
        action="store_true",
        default=False,
        help=(
            "Require x-erre-token header on every WS connection. Off by "
            "default (back-compat). Pair with --ws-token, ERRE_WS_TOKEN, "
            "or var/secrets/ws_token to provide the expected value."
        ),
    )
    parser.add_argument(
        "--allowed-origins",
        dest="allowed_origins",
        default="",
        help=(
            "Comma-separated Origin allow-list. Empty (default) disables "
            "the Origin check entirely so Godot's native WS client (which "
            "sends no Origin header) keeps working."
        ),
    )
    parser.add_argument(
        "--max-sessions",
        dest="max_sessions",
        type=int,
        default=protocol.MAX_ACTIVE_SESSIONS,
        help=(
            "Cap on simultaneous WS sessions. Overflow connections receive "
            "close code 1013 (Try Again Later). Default 8."
        ),
    )
    parser.add_argument(
        "--allow-unauthenticated-lan",
        dest="allow_unauthenticated_lan",
        action="store_true",
        default=False,
        help=(
            "Codex 14th HIGH-1 escape hatch: explicit opt-in to the pre-SH-2 "
            "LAN dev posture (host=0.0.0.0, no Origin, no token). Bypasses "
            "the bootstrap RuntimeError gate but logs a loud warning on "
            "every startup. Use only on a trusted LAN until the Godot WS "
            "client patch enables --require-token by default "
            "(see feat/ws-token-enforce follow-up task)."
        ),
    )
    return parser


def _build_subcommand_parser() -> argparse.ArgumentParser:
    """Parser for explicit sub-commands (``export-log`` etc)."""
    parser = argparse.ArgumentParser(
        prog="erre-sandbox",
        description=(
            "ERRE-Sandbox sub-commands (M8+). See ``erre-sandbox --help`` "
            "for the default orchestrator-run options."
        ),
    )
    subparsers = parser.add_subparsers(
        dest="subcommand",
        required=True,
        metavar="{export-log,baseline-metrics,scaling-metrics}",
    )
    export_log.register(subparsers)
    baseline_metrics.register(subparsers)
    scaling_metrics.register(subparsers)
    return parser


# Keep the legacy name for backwards compatibility with tests that import it.
_build_parser = _build_run_parser


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
    # argv dispatch: if the first positional token is a known sub-command
    # name we route to a dedicated sub-command parser. Otherwise we keep
    # the pre-M8 behaviour (boot the orchestrator directly). Using two
    # separate parsers instead of argparse sub-parsers avoids prefix-match
    # ambiguity between root ``--personas`` and export-log's ``--persona``.
    effective_argv = list(sys.argv[1:]) if argv is None else list(argv)
    if effective_argv and effective_argv[0] in _SUBCOMMANDS:
        args = _build_subcommand_parser().parse_args(effective_argv)
        if args.subcommand == "export-log":
            return export_log.run(args)
        if args.subcommand == "baseline-metrics":
            return baseline_metrics.run(args)
        if args.subcommand == "scaling-metrics":
            return scaling_metrics.run(args)
        msg = f"unknown subcommand: {args.subcommand!r}"  # pragma: no cover
        raise SystemExit(msg)

    args = _build_run_parser().parse_args(effective_argv)
    personas_dir = Path(args.personas_dir)
    agents = _resolve_agents(args.personas, personas_dir)
    allowed_origins = tuple(
        token.strip() for token in args.allowed_origins.split(",") if token.strip()
    )
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
        ws_token=args.ws_token,
        require_token=args.require_token,
        allowed_origins=allowed_origins,
        max_sessions=args.max_sessions,
        allow_unauthenticated_lan=args.allow_unauthenticated_lan,
    )
    try:
        asyncio.run(bootstrap(cfg))
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(cli())
