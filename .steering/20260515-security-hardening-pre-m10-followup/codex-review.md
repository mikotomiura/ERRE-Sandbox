**Executive Verdict — BLOCK**

This branch does not yet close the M10-0 go/no-go gate. The core SH-1/SH-2 machinery is mostly present, but SH-2 currently breaks the preserved Godot LAN workflow: the default `0.0.0.0` startup path raises, while the documented Origin allow-list escape hatch rejects the current empty-Origin Godot client.

**HIGH Findings**

HIGH-1: `src/erre_sandbox/bootstrap.py:163`, `src/erre_sandbox/integration/gateway.py:618`, `src/erre_sandbox/__main__.py:246`, `godot_project/scripts/WebSocketClient.gd:55`

Severity: existing Mac/G-GEAR Godot LAN workflow has no working unauthenticated `0.0.0.0` path. `BootConfig()` fails startup; `--allowed-origins=...` starts the server but rejects Godot because the current client sends no `Origin`; `--require-token` requires a Godot client patch not in this branch; `--host=127.0.0.1` breaks LAN.

Recommended fix: either patch Godot in this branch to send the chosen protection, preferably `x-erre-token`, and update the runbook to recommend `--require-token`; or add an explicit, noisy `--allow-unauthenticated-lan` escape hatch and record the ADR amendment. Add regression tests for default startup validation and empty-Origin client behavior.

HIGH-2: `.github/workflows/ci.yml:159`

Severity: the CI banned-import gate misses valid Python syntax such as `import openai, os` because the regex requires whitespace after `openai|anthropic`. That means the final SH-1 merge backstop can allow a forbidden cloud LLM import.

Recommended fix: replace grep with a tiny AST scanner over `src/erre_sandbox/**/*.py` that rejects `ast.Import` / `ast.ImportFrom` roots `openai`, `anthropic`, and `bpy`. Add a self-test case for comma imports.

**MEDIUM Findings**

MEDIUM-1: `.codex/hooks/pre_tool_use_policy.py:21`

The shell-write detector misses obvious write paths: `cp /tmp/x.py src/erre_sandbox/x.py`, `dd ... of=src/...`, Python heredocs, and absolute paths containing the workspace space (`ERRE-Sand Box`). Keep it as UX guardrail, but broaden the patterns or use a shell parser/backstop tests so common writes are denied.

MEDIUM-2: `.github/workflows/ci.yml:195`

The `.steering` CI check only verifies that the latest historical `.steering/YYYYMMDD-*` directory is complete. A future PR can modify `src/erre_sandbox` without adding/updating task records and still pass if any existing latest directory is complete. Require a changed complete `.steering` dir in `git diff origin/main...HEAD`, or tie it to an explicit task reference.

MEDIUM-3: `src/erre_sandbox/bootstrap.py:165`

`require_token=True` with no resolved token can still pass startup if `allowed_origins` is non-empty, then every WS connection fails closed at runtime. Fail fast whenever `cfg.require_token and not token`, independent of Origin.

**LOW Findings**

LOW-1: `.steering/20260515-security-hardening-pre-m10-followup/decisions.md:108`

The manual LAN smoke snippet is stale: `--check-ollama false` is not the CLI flag, `--personas study/peripatos` is not a valid persona list, and the curl path is `/observe` instead of `/ws/observe`. Fix before someone uses it as a runbook.

LOW-2: `tests/test_world/test_runtime_lifecycle.py:225`

The `_consume_result` coverage proves the shared helper, not the full result-consumption path. Acceptable for this branch, but add one higher-fidelity `CycleResult` test when touching runtime lifecycle again.

**META**

META-1: No, the 3 commits do not close the M10-0 gate until HIGH-1 and HIGH-2 are fixed. The active-session race is handled correctly, and SH-5 logging is sound, but the LAN workflow regression is a gate failure.

META-2: SH-FOLLOWUP-1 is fine. OpenAI’s Codex hook docs explicitly support `PreToolUse` denial via stdout JSON with `hookSpecificOutput.permissionDecision = "deny"` and also list exit code `2` as an alternative. Keeping `deny()` as exit 0 + JSON does not regress the protocol. Source: https://developers.openai.com/codex/hooks

META-3: `src/erre_sandbox/inference/ollama_adapter.py:145` is inside a docstring example, not executable code. It is not a real T201 violation. The ruff-based SH-FOLLOWUP-2 design is correct; literal grep would be a false positive.

META-4: `policy-grep-gate` should work for fork PRs with the current checkout shape. GitHub documents `pull_request` workflows as running in the base repo context, with `actions/checkout` using the PR merge ref by default; `fetch-depth: 0` fetches all history/branches. Source: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows and https://github.com/actions/checkout

META-5: `reserve_slot()` is atomic for asyncio callers because it has no `await` between the length check and assignment. The race between pre-check and authoritative reserve is closed by `session_cap_exceeded` + close 1013. Remaining risk: pending pre-handshake sockets are not capped, only ACTIVE sessions.

META-6: `logger.warning` placement is correct. The drop count is incremented in the same overflow branch before the warning at `world/tick.py:814`; I found no count-bumped/log-skipped path.

**Fact-Check Sheet**

Re-ran:

```text
git rev-parse --abbrev-ref HEAD && git rev-parse --short main
feature/security-hardening-pre-m10-followup
4884f9d
```

```text
git log --oneline main..HEAD
69f3b48 feat(observability+tests): SH-5 logger.warning + SH-4/SH-5 coverage
b3bba97 feat(codex): hook + CI shell-bypass guard (SH-1)
e31562e feat(ws): shared-token + Origin + session cap (SH-2)
```

```text
UV_CACHE_DIR=/tmp/erre-uv-cache uv run ruff check src tests
All checks passed!
```

```text
UV_CACHE_DIR=/tmp/erre-uv-cache uv run ruff format --check src tests
218 files already formatted
```

```text
UV_CACHE_DIR=/tmp/erre-uv-cache uv run mypy src
Success: no issues found in 82 source files
```

```text
UV_CACHE_DIR=/tmp/erre-uv-cache uv run pytest -q -m "not godot and not eval and not spike and not training and not inference"
1399 passed, 32 skipped, 54 deselected, 3 warnings in 4.77s
```

```text
UV_CACHE_DIR=/tmp/erre-uv-cache uv run pytest tests/test_integration/test_gateway.py tests/test_codex_hooks tests/test_world/test_runtime_lifecycle.py -q
55 passed in 1.27s
```

```text
Hook smoke, JSON deny form:
true
```

New checks:

```text
Allowed-origin server with no Origin header:
session ... rejected origin '' (allowed=('http://mac.local',))
no-origin-close=1008
```

```text
CI grep variant:
import openai, os    # not matched
import openai as client
from openai import OpenAI
```
