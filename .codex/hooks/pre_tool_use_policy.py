#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from _erre_common import emit_json, latest_task, read_payload, relative_path, repo_root, task_status

IMPL_PREFIX = "src/erre_sandbox/"

# SH-1 — shell-write detection. These regex patterns flag the canonical
# ways a shell command can write to a file on disk so the hook can reject
# any write that targets ``src/erre_sandbox/``. The matcher in
# ``.codex/hooks.json`` widens to ``exec_command|Bash`` so this path now
# fires for tool calls that previously bypassed the ``apply_patch|Edit|
# Write`` filter. False negatives are acceptable since the CI
# ``policy-grep-gate`` job is a second backstop; false positives only
# fire on shell commands that target ``src/erre_sandbox/`` so the user
# can re-issue via Edit/Write.
SHELL_WRITE_PATTERNS: list[re.Pattern[str]] = [
    # sed -i / gsed -i [-i.bak] [-e ...] PATH (in-place edit)
    re.compile(
        r"\b(?:g?sed)\s+-i(?:\s+(?:''|\.\w+))?"
        r"(?:[^|;]*?\s+-e\s+(?:'[^']*'|\"[^\"]*\"|\S+))?"
        r"[^|;]*?\s(?P<path>[\w./-]+\.\w+)\b",
    ),
    # perl -pi / -pie -e ... PATH
    re.compile(
        r"\bperl\s+-pi(?:e)?(?:[^|;]*?\s+-e\s+(?:'[^']*'|\"[^\"]*\"))?"
        r"[^|;]*?\s(?P<path>[\w./-]+\.\w+)\b",
    ),
    # tee [-a] PATH (write or append)
    re.compile(r"\btee\b(?:\s+-a)?\s+(?P<path>[\w./-]+\.\w+)\b"),
    # cat > PATH << EOF (heredoc redirect)
    re.compile(r"\bcat\s+>>?\s*(?P<path>[\w./-]+\.\w+)\s*<<"),
    # Generic shell redirect ``> PATH.ext`` or ``>> PATH.ext`` — catches
    # echo / printf / dd / generic pipelines. The ``\.\w+`` tail keeps
    # this from matching ``> /dev/null`` and the like.
    re.compile(r"(?<![<>])>>?\s*(?P<path>[\w./-]+\.\w+)\b"),
    # python -c "...open('PATH', 'w'|'a'|'wb'|'ab'...).write(...)..."
    re.compile(
        r"python3?\s+-c\s+['\"][^'\"]*?open\s*\(\s*"
        r"['\"](?P<path>[^'\"]+)['\"]\s*,\s*['\"][wa]b?\+?",
    ),
    # python -c "...Path('PATH').write_(text|bytes)..."
    re.compile(
        r"python3?\s+-c\s+['\"][^'\"]*?Path\s*\(\s*"
        r"['\"](?P<path>[^'\"]+)['\"]\s*\)\s*\.\s*write_(?:text|bytes)",
    ),
]


def shell_write_targets(command: str) -> list[str]:
    """Return paths a shell command would write to (best-effort regex).

    The hook treats any returned path that lies under ``IMPL_PREFIX`` as
    a violation (see :func:`main`). Returning a path outside ``IMPL_PREFIX``
    is harmless because :func:`is_impl_path` filters it out at the call
    site; the caller never reads content from this helper, only the path
    list.
    """
    targets: list[str] = []
    seen: set[str] = set()
    for pattern in SHELL_WRITE_PATTERNS:
        for match in pattern.finditer(command):
            path = match.group("path")
            if path and path not in seen:
                seen.add(path)
                targets.append(path)
    return targets


BANNED_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "cloud LLM API imports are forbidden in src/erre_sandbox",
        re.compile(r"^\s*(?:import\s+(?:openai|anthropic)\b|from\s+(?:openai|anthropic)\b)"),
    ),
    (
        "bpy imports are forbidden in src/erre_sandbox because Blender/GPL code is isolated",
        re.compile(r"^\s*(?:import\s+bpy\b|from\s+bpy\b)"),
    ),
    (
        "print() is forbidden in src/erre_sandbox; use logging instead",
        re.compile(r"^\s*print\s*\("),
    ),
]


def deny(reason: str) -> int:
    emit_json(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
    )
    return 0


def patch_targets(command: str) -> dict[str, list[str]]:
    targets: dict[str, list[str]] = {}
    current: str | None = None
    for line in command.splitlines():
        for marker in ("*** Add File: ", "*** Update File: ", "*** Delete File: "):
            if line.startswith(marker):
                current = line[len(marker) :].strip()
                targets.setdefault(current, [])
                break
        else:
            if current and line.startswith("+") and not line.startswith("+++"):
                targets[current].append(line[1:])
    return targets


def direct_targets(tool_input: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for key in ("file_path", "path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            content = tool_input.get("new_string") or tool_input.get("content") or ""
            if isinstance(content, str):
                result[value] = content.splitlines()
    edits = tool_input.get("edits")
    target = tool_input.get("file_path") or tool_input.get("path")
    if isinstance(edits, list) and isinstance(target, str):
        lines: list[str] = []
        for edit in edits:
            if isinstance(edit, dict) and isinstance(edit.get("new_string"), str):
                lines.extend(edit["new_string"].splitlines())
        result[target] = lines
    return result


def target_map(payload: dict[str, Any]) -> dict[str, list[str]]:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return {}
    command = tool_input.get("command")
    if isinstance(command, str) and "*** Begin Patch" in command:
        return patch_targets(command)
    return direct_targets(tool_input)


def is_impl_path(path: str) -> bool:
    return path.startswith(IMPL_PREFIX)


def check_banned(path: str, lines: list[str]) -> str | None:
    if not path.endswith(".py") or not is_impl_path(path):
        return None
    for line in lines:
        for label, pattern in BANNED_PATTERNS:
            if pattern.search(line):
                return f"{label}: {path}: {line.strip()}"
    return None


def main() -> int:
    payload = read_payload()
    root = repo_root(payload)
    # SH-1: shell-write bypass guard. The PreToolUse matcher in
    # ``.codex/hooks.json`` widens to ``exec_command|Bash`` so this branch
    # is now reachable for shell tool calls. Any shell command that writes
    # into ``src/erre_sandbox/`` is rejected regardless of the would-be
    # content — the change must go through Edit/Write/apply_patch so the
    # same policy guards (banned imports, ``.steering`` completeness,
    # diff review trail) apply uniformly.
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        command = tool_input.get("command")
        if isinstance(command, str) and "*** Begin Patch" not in command:
            impl_shell_targets: list[str] = []
            for raw_path in shell_write_targets(command):
                rel = relative_path(root, raw_path)
                if is_impl_path(rel):
                    impl_shell_targets.append(rel)
            if impl_shell_targets:
                preview = ", ".join(sorted(set(impl_shell_targets))[:3])
                return deny(
                    "SH-1: shell-write into src/erre_sandbox/ is forbidden; "
                    "use Edit/Write/apply_patch tools so the same policy "
                    f"guards apply. Detected target(s): {preview}"
                )
    normalized = {
        relative_path(root, path): lines for path, lines in target_map(payload).items()
    }
    if not normalized:
        return 0
    impl_targets = [path for path in normalized if is_impl_path(path)]
    if impl_targets:
        status = task_status(latest_task(root))
        if status["task"] is None:
            return deny(
                "Implementation edits require a recent .steering/YYYYMMDD-task directory "
                "with requirement.md, design.md, and tasklist.md."
            )
        if status["missing"]:
            return deny(
                f"Implementation edits require complete steering files; missing: "
                f"{', '.join(status['missing'])}."
            )
    for path, lines in normalized.items():
        violation = check_banned(path, lines)
        if violation:
            return deny(violation)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
