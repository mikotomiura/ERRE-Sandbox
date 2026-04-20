"""CLI wiring tests for :mod:`erre_sandbox.__main__`.

These stay argparse-only: no :func:`asyncio.run` is invoked. The
``bootstrap`` coroutine is exercised separately in ``test_bootstrap.py``
and by G-GEAR live evidence runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from erre_sandbox.__main__ import _build_parser, _resolve_agents
from erre_sandbox.schemas import AgentSpec, Zone

# ---------------------------------------------------------------------------
# --personas expansion
# ---------------------------------------------------------------------------


def test_resolve_agents_returns_empty_when_flag_absent() -> None:
    assert _resolve_agents(None, Path("personas")) == ()


def test_resolve_agents_returns_empty_when_flag_blank() -> None:
    assert _resolve_agents("   ", Path("personas")) == ()
    assert _resolve_agents(",,", Path("personas")) == ()


def test_resolve_agents_expands_kant_nietzsche_rikyu() -> None:
    specs = _resolve_agents("kant,nietzsche,rikyu", Path("personas"))
    assert len(specs) == 3
    assert [s.persona_id for s in specs] == ["kant", "nietzsche", "rikyu"]
    # Each spec's initial_zone is the persona's first preferred_zone.
    assert all(isinstance(s, AgentSpec) for s in specs)
    assert all(isinstance(s.initial_zone, Zone) for s in specs)


def test_resolve_agents_raises_system_exit_for_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="unknown_persona"):
        _resolve_agents("unknown_persona", tmp_path)


@pytest.mark.parametrize(
    "hostile",
    [
        "../etc/passwd",
        "/etc/passwd",
        "kant/../nietzsche",
        "Kant",  # uppercase rejected
        "_leading",  # must start with a letter
        "x" * 65,  # length cap
    ],
)
def test_resolve_agents_rejects_path_traversal_tokens(
    hostile: str,
    tmp_path: Path,
) -> None:
    """Defence in depth: CLI must reject any persona_id that could escape."""
    with pytest.raises(SystemExit, match="must match"):
        _resolve_agents(hostile, tmp_path)


def test_resolve_agents_strips_whitespace() -> None:
    specs = _resolve_agents(" kant , nietzsche ", Path("personas"))
    assert [s.persona_id for s in specs] == ["kant", "nietzsche"]


# ---------------------------------------------------------------------------
# _build_parser
# ---------------------------------------------------------------------------


def test_parser_personas_flag_defaults_to_none() -> None:
    args = _build_parser().parse_args([])
    assert args.personas is None
    assert args.personas_dir == "personas"


def test_parser_personas_flag_accepts_csv() -> None:
    args = _build_parser().parse_args(["--personas", "kant,nietzsche"])
    assert args.personas == "kant,nietzsche"


def test_parser_personas_dir_override(tmp_path: Path) -> None:
    target = str(tmp_path / "custom-personas")
    args = _build_parser().parse_args(["--personas-dir", target])
    assert args.personas_dir == target
