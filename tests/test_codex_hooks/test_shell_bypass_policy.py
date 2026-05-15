"""SH-1 red-team tests for the ``pre_tool_use_policy.py`` Codex hook.

The hook gates ``exec_command`` / ``Bash`` tool calls that would write into
``src/erre_sandbox/`` via shell redirects, ``sed -i``, ``tee``, heredocs,
or inline Python literals. Each case below invokes the hook as a fresh
subprocess with a synthetic Codex-style payload on stdin and asserts the
hook emits the JSON ``permissionDecision="deny"`` envelope (the canonical
Codex hook protocol; the helper-level ``deny()`` returns exit 0 with the
structured stdout so downstream telemetry stays parseable).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / ".codex" / "hooks" / "pre_tool_use_policy.py"


def _invoke_hook(payload: dict[str, Any]) -> dict[str, Any]:
    """Run the hook as a fresh subprocess and parse its JSON stdout.

    The hook contract is ``exit 0`` + JSON ``permissionDecision`` envelope
    in stdout (Codex protocol). The subprocess is run with the project
    repo root as CWD so ``repo_root`` / ``latest_task`` resolve to the
    live ``.steering/`` tree and the SH-1 guard fires on its own merit
    rather than via the ``.steering`` completeness fallback.
    """
    result = subprocess.run(  # noqa: S603 — fixed argv to the in-repo hook
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(REPO_ROOT),
        check=False,
    )
    assert result.returncode == 0, (
        f"hook returncode={result.returncode}\n"
        f"stderr={result.stderr}\nstdout={result.stdout}"
    )
    stdout = result.stdout.strip()
    if not stdout:
        # Allow path: ``main()`` returns 0 without writing to stdout when no
        # rule fires. Tests checking benign commands should see this branch.
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover — diagnostic only
        pytest.fail(f"hook stdout not JSON: {stdout!r} (err={exc})")


def _assert_deny(envelope: dict[str, Any], *, contains: str) -> None:
    """Helper: assert the hook envelope is a deny mentioning ``contains``."""
    hook_output = envelope.get("hookSpecificOutput", {})
    assert hook_output.get("permissionDecision") == "deny", envelope
    reason = hook_output.get("permissionDecisionReason", "")
    assert contains in reason, (
        f"expected deny reason to mention {contains!r}, got {reason!r}"
    )


# ---------------------------------------------------------------------------
# Red-team: 5 canonical shell-write techniques the hook must block.
# ---------------------------------------------------------------------------


def test_sed_in_place_into_impl_is_denied() -> None:
    """``sed -i`` rewriting an impl file is denied (in-place edit bypass)."""
    payload = {
        "tool": "exec_command",
        "tool_input": {
            "command": (
                "sed -i 's/from typing/from typing\\nimport openai/' "
                "src/erre_sandbox/inference/sglang_adapter.py"
            ),
        },
        "cwd": str(REPO_ROOT),
    }
    envelope = _invoke_hook(payload)
    _assert_deny(envelope, contains="SH-1")


def test_echo_append_into_impl_is_denied() -> None:
    """``echo "..." >> PATH`` redirected into an impl file is denied."""
    payload = {
        "tool": "exec_command",
        "tool_input": {
            "command": ('echo "import bpy" >> src/erre_sandbox/world/tick.py'),
        },
        "cwd": str(REPO_ROOT),
    }
    envelope = _invoke_hook(payload)
    _assert_deny(envelope, contains="SH-1")


def test_tee_into_impl_is_denied() -> None:
    """``tee PATH`` writing to an impl file is denied (even with empty stdin)."""
    payload = {
        "tool": "exec_command",
        "tool_input": {
            "command": "tee src/erre_sandbox/x.py < /dev/null",
        },
        "cwd": str(REPO_ROOT),
    }
    envelope = _invoke_hook(payload)
    _assert_deny(envelope, contains="SH-1")


def test_python_dash_c_open_write_into_impl_is_denied() -> None:
    """``python -c "open(PATH, 'w').write(...)"`` is denied."""
    payload = {
        "tool": "exec_command",
        "tool_input": {
            "command": (
                "python -c \"open('src/erre_sandbox/y.py','w').write('print(1)')\""
            ),
        },
        "cwd": str(REPO_ROOT),
    }
    envelope = _invoke_hook(payload)
    _assert_deny(envelope, contains="SH-1")


def test_cat_heredoc_into_impl_is_denied() -> None:
    """``cat > PATH << EOF ... EOF`` heredoc into an impl file is denied."""
    payload = {
        "tool": "exec_command",
        "tool_input": {
            "command": ("cat > src/erre_sandbox/z.py <<EOF\nimport anthropic\nEOF"),
        },
        "cwd": str(REPO_ROOT),
    }
    envelope = _invoke_hook(payload)
    _assert_deny(envelope, contains="SH-1")


# ---------------------------------------------------------------------------
# Negative path: benign shell commands must NOT be denied by the SH-1 gate.
# ---------------------------------------------------------------------------


def test_grep_into_impl_is_allowed() -> None:
    """Read-only ``grep src/erre_sandbox/...`` does not match write patterns."""
    payload = {
        "tool": "exec_command",
        "tool_input": {
            "command": "grep -rn 'WorldRuntime' src/erre_sandbox/world",
        },
        "cwd": str(REPO_ROOT),
    }
    envelope = _invoke_hook(payload)
    # No write into impl → empty target_map → main() returns 0 with empty
    # stdout. JSON parse of an empty stdout raises — handle that fall-back.
    hook_output = envelope.get("hookSpecificOutput") if envelope else None
    if hook_output is not None:
        # If the hook emitted anything, it must NOT be a deny for SH-1.
        decision = hook_output.get("permissionDecision")
        if decision == "deny":
            reason = hook_output.get("permissionDecisionReason", "")
            assert "SH-1" not in reason, (
                "grep read-only command must not trip the SH-1 shell-write guard"
            )


def test_shell_write_outside_impl_is_allowed() -> None:
    """Writing to /tmp or var/ via shell is allowed (not in src/erre_sandbox/)."""
    payload = {
        "tool": "exec_command",
        "tool_input": {
            "command": 'echo "junk" > /tmp/scratch.txt',
        },
        "cwd": str(REPO_ROOT),
    }
    envelope = _invoke_hook(payload)
    hook_output = envelope.get("hookSpecificOutput") if envelope else None
    if hook_output is not None:
        decision = hook_output.get("permissionDecision")
        if decision == "deny":
            reason = hook_output.get("permissionDecisionReason", "")
            assert "SH-1" not in reason, (
                "shell-write to /tmp must not trip the SH-1 src/erre_sandbox/ guard"
            )
