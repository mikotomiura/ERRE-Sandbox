---
name: erre-workflow
description: >
  ERRE-Sandbox task workflow for Codex. Use when starting, designing, implementing,
  reviewing, or finishing repository work; when the user mentions /start-task,
  /add-feature, /fix-bug, /refactor, /reimagine, /review-changes, or /finish-task;
  or when .steering records, Codex setup, task plans, or implementation handoffs are needed.
---

# ERRE Workflow

This is the Codex-native replacement for the Claude slash-command workflow. Claude command
files in `.claude/commands/` are reference material only; Codex should execute the workflow
through normal tool use, `.steering/` records, skills, hooks, and custom agents.

## Quick Start

1. Read `AGENTS.md`, `docs/development-guidelines.md`, and the relevant domain skill.
2. Create or update `.steering/YYYYMMDD-task-name/` before implementation work:
   `requirement.md`, `design.md`, and `tasklist.md` are required.
3. For design-heavy work, keep implementation paused until a plan is accepted. If the task
   has multiple plausible designs, perform a reimagine pass before editing source files.
4. Implement in small steps, updating `tasklist.md` as work completes.
5. Verify with focused checks first, then the documented full checks when feasible.
6. Finish by reviewing the diff and recording any decisions or limitations.

Use subagents only when the user explicitly asks for delegation or parallel agent work.
When they do, prefer the project-scoped agents in `.codex/agents/`.

## Task Start

Create `.steering/YYYYMMDD-task-name/` with:

- `requirement.md`: background, goal, scope, out of scope, acceptance criteria.
- `design.md`: approach, changed areas, compatibility, test strategy, rollback.
- `tasklist.md`: checkboxes at roughly 30-minute granularity.
- `decisions.md`: only for meaningful tradeoffs or policy choices.
- `blockers.md`: only when blocked or carrying deferred risk.

Use the current local date in `YYYYMMDD`. Prefer a short kebab-case task name.

## Implementation Flows

- **Feature**: read existing patterns, document the design, implement narrowly, add tests or
  verification proportional to risk, update docs when behavior changes.
- **Bug fix**: reproduce or explain the failure, record root cause, add or identify a
  regression check when feasible, then make the smallest defensible fix.
- **Refactor**: establish current checks first, preserve behavior, change in small steps,
  and avoid mixing feature or bug-fix work into the same task.

For source edits under `src/erre_sandbox/`, always consider:

- `architecture-rules` for layer direction and GPL/cloud API constraints.
- `python-standards` for Python style.
- `error-handling` when async, retry, timeout, WebSocket, sqlite, or LLM fallback behavior changes.
- `test-standards` when adding or changing tests.

## Reimagine

Use this for architecture, public interfaces, difficult bugs, and designs with multiple
credible approaches:

1. Save the first plan as `design-v1.md`.
2. Re-read only `requirement.md` and produce a fresh alternative in `design.md`.
3. Compare the two in `design-comparison.md`.
4. Choose v1, v2, or a hybrid and record the reason in `decisions.md`.

Do not use reimagine after implementation has already created side effects that would need
manual rollback.

## Network Access Policy

The `.codex/config.toml` workspace_write sandbox defaults to `network_access = false`
(SH-3 ADR, 2026-05-13). Codex `web_search = "live"` is decoupled and stays enabled —
queries leave the box, but repo contents do not.

Do NOT toggle `network_access = true` without explicit per-session user approval.
If a task genuinely needs egress (e.g. `uv sync` for a fresh dependency), surface
the need to the user first and request a one-shot override via `--config
sandbox_workspace_write.network_access=true`. Do not commit a `true` value into
`.codex/config.toml`. See `AGENTS.md` "Network access policy" section.

## Review And Finish

Before final delivery:

- Run focused checks for touched areas.
- Run `uv run ruff check src tests`, `uv run ruff format --check src tests`,
  `uv run mypy src`, and `uv run pytest` when feasible.
- Review `git diff` for unrelated changes and do not revert user work.
- Update `tasklist.md` and `design.md` with what actually happened.
- Mention skipped checks or residual risk in the final response.

Do not commit unless the user asks. If committing, use `git-workflow`.
