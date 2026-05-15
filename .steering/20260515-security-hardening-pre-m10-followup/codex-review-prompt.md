# Codex 14th independent review — security-hardening-pre-m10-followup

You are reviewing 3 commits on branch `feature/security-hardening-pre-m10-followup` against `main` (commit `4884f9d` = PR #170 merge).
This branch closes the SH-1 (HIGH) + SH-2 (MEDIUM-elevated) findings the Codex 13th review *required* be resolved before M10-0 can begin — see `.steering/20260513-security-hardening-pre-m10/blockers.md` "M10-0 着手の go/no-go gate".

The implementation strategy is **mechanical execution of the SH-1 / SH-2 ADRs already approved in PR #170** (`.steering/20260513-security-hardening-pre-m10/decisions.md`), not new design work. The two implementation-level judgement calls (deny() exit code, T201 backstop method) are recorded as SH-FOLLOWUP-1 and SH-FOLLOWUP-2 in this task's `decisions.md`.

## Commits

```
69f3b48 feat(observability+tests): SH-5 logger.warning + SH-4/SH-5 coverage
b3bba97 feat(codex): hook + CI shell-bypass guard (SH-1)
e31562e feat(ws): shared-token + Origin + session cap (SH-2)
```

## Files changed (`git diff main..HEAD --stat`)

```
21 files changed, 1557 insertions(+), 14 deletions(-)
.codex/hooks.json                                  |   2 +-
.codex/hooks/pre_tool_use_policy.py                |  86 +++++++
.github/workflows/ci.yml                           |  83 +++++++
.steering/20260515-security-hardening-pre-m10-followup/  5 files = scaffold
README.md                                          |  30 +++
docs/architecture.md                               |   4 +-
docs/development-guidelines.md                     |  16 ++
src/erre_sandbox/__main__.py                       |  54 +++++
src/erre_sandbox/bootstrap.py                      | 105 +++++++++-
src/erre_sandbox/cli/eval_run_golden.py            |  14 ++
src/erre_sandbox/integration/gateway.py            | 193 +++++++++++++++-
src/erre_sandbox/integration/protocol.py           |  43 +++++
src/erre_sandbox/world/tick.py                     |  10 ++
tests/test_codex_hooks/__init__.py                 |   0
tests/test_codex_hooks/test_shell_bypass_policy.py | 189 ++++++++++++++
tests/test_integration/test_gateway.py             | 144 ++++++++++-
tests/test_world/test_runtime_lifecycle.py         | 135 ++++++++++
```

## Implementation summary

### SH-2 (commit `e31562e`) — WS 3-layer auth (token + Origin + cap)

- `integration/protocol.py:62`+ — `DEFAULT_ALLOWED_ORIGINS: Final[tuple[str, ...]] = ()` (empty = check disabled, Godot empty-Origin compat) + `MAX_ACTIVE_SESSIONS: Final[int] = 8` + `SessionCapExceededError(current, cap)`
- `integration/gateway.py` — new `WSAuthConfig` frozen dataclass (4 fields, all default-disabled). `Registry.__init__` accepts `max_sessions`; `reserve_slot` raises `SessionCapExceededError` atomically inside the event loop; `add()` kept as deprecated alias delegating to `reserve_slot` (cap-safe under tests since they stay below 8). `ws_observe` pre-accept gates: Origin allow-list (close 1008), shared-token via `secrets.compare_digest` (close 1008), session-cap pre-check (close 1013, fast path). Race-safe `reserve_slot` in ACTIVE phase: if a slot was filled between the pre-check and reserve, send in-band `session_cap_exceeded` ErrorMsg + close 1013.
- `bootstrap.py` — 4 BootConfig fields. `_resolve_ws_token`: explicit → env `ERRE_WS_TOKEN` → file `var/secrets/ws_token` → None. `_validate_ws_auth_config`: raises `RuntimeError` at startup when `host=="0.0.0.0"` AND no Origin allowlist AND not (`require_token=True` AND token present). Operator escape hatches printed in the message: `--allowed-origins`, `--require-token + var/secrets/ws_token`, or `--host=127.0.0.1`.
- `__main__.py` — 4 argparse flags `--ws-token / --require-token / --allowed-origins / --max-sessions`. comma-list parsing for origins.
- `tests/test_integration/test_gateway.py::TestWebSocketAuth` — 6 cases (back-compat default / token missing 1008 / token mismatch 1008 / token match continues / origin reject 1008 / cap exceeded 1013).
- Docs: `architecture.md:328` auth posture updated; `development-guidelines.md` token rotation runbook; `README.md` `var/secrets/` provisioning + opt-in flag examples.

### SH-1 (commit `b3bba97`) — Codex hook + CI shell-bypass guard

- `.codex/hooks.json:30` — matcher widens to `apply_patch|Edit|Write|exec_command|Bash`.
- `.codex/hooks/pre_tool_use_policy.py` — `shell_write_targets(command)` helper (7 regex patterns: sed -i / perl -pi / tee / cat>>HEREDOC / generic > / python -c open() / Path().write_text). `main()` pre-check: if shell command contains any `src/erre_sandbox/...` write target, return `deny(...)` immediately. `deny()` itself unchanged (Codex protocol JSON `permissionDecision="deny"` in stdout, exit 0 — see SH-FOLLOWUP-1 in this task's `decisions.md`).
- `.github/workflows/ci.yml` — new `policy-grep-gate` job (`fetch-depth: 0`, 5-min timeout). 3 steps: (a) banned-import grep for openai|anthropic|bpy; (b) `uv run ruff check --select T201 src/erre_sandbox` so the pyproject T201 exemption + per-line noqa are honoured naturally — see SH-FOLLOWUP-2 — preserving the existing `inference/ollama_adapter.py:145` CI-green baseline; (c) `.steering/[YYYYMMDD]-*/` completeness check (skipped when no `src/erre_sandbox/**/*.py` diff).
- `tests/test_codex_hooks/test_shell_bypass_policy.py` — 5 red-team subprocess cases (sed-in-place / echo>> / tee / python-c open() / cat heredoc) + 2 negative paths (grep / write to /tmp). Each asserts JSON `hookSpecificOutput.permissionDecision == "deny"`.

### Codex 13th MEDIUM (commit `69f3b48`)

- `world/tick.py:814` — `logger.warning("runtime backlog overflow: drops=%d maxsize=%d", ...)` added inside the overflow branch so out-of-band SRE log fires alongside the in-band ErrorMsg.
- `cli/eval_run_golden.py:_resolve_memory_db_path` — TOCTOU disclosure docstring added (no test; race window is theoretical given single-user /tmp + same-UID var/eval).
- `tests/test_world/test_runtime_lifecycle.py` — 7 new cases on `TestWorldRuntimeEnvelopeQueue`: maxsize-1 / maxsize / maxsize+1 boundary, monotonic overflow count across two bursts, `_consume_result` path also drops oldest (helper-shared), `logger.warning` emission via caplog, `recv_envelope` cancel cleanliness.

## Fact-check sheet (run on this branch)

```
$ git rev-parse --abbrev-ref HEAD
feature/security-hardening-pre-m10-followup

$ git log --oneline main..HEAD
69f3b48 feat(observability+tests): SH-5 logger.warning + SH-4/SH-5 coverage
b3bba97 feat(codex): hook + CI shell-bypass guard (SH-1)
e31562e feat(ws): shared-token + Origin + session cap (SH-2)

$ git diff main..HEAD -- data/eval/golden src/erre_sandbox/evidence
<empty>

$ git diff main..HEAD -- src/erre_sandbox/schemas.py
<empty>

$ grep -n '^SCHEMA_VERSION' src/erre_sandbox/schemas.py
44:SCHEMA_VERSION: Final[str] = "0.10.0-m7h"

$ uv run ruff check src tests
All checks passed!

$ uv run ruff format --check src tests
218 files already formatted

$ uv run mypy src
Success: no issues found in 82 source files

$ uv run pytest -q -m "not godot and not eval and not spike and not training and not inference"
1399 passed, 32 skipped, 54 deselected, 3 warnings in 4.71s
```

Test delta from PR #170 baseline (1378): +21 cases = 6 TestWebSocketAuth + 5 SH-1 red-team + 2 SH-1 negative + 1 MEDIUM observability caplog + 6 MEDIUM boundary/monotonic/_consume_result/cancel + 1 SH-2 back-compat default.

## Required review output format

Return ONE document with sections:

1. **Executive verdict** — one of: `ADOPT` / `ADOPT-WITH-CHANGES` / `BLOCK`. Quote 1–2 sentences.
2. **HIGH findings** (each numbered HIGH-N): file + line, severity rationale, recommended fix. HIGH ⇒ must be fixed before merge. Be specific — Claude will reflect each one in a follow-up commit.
3. **MEDIUM findings** (MEDIUM-N): may be deferred via `decisions.md` ADR addendum, but state your recommendation.
4. **LOW findings** (LOW-N): optional / nit / blockers.md candidates.
5. **META** — anything systemic about the implementation approach, the SH-FOLLOWUP-1/SH-FOLLOWUP-2 judgement calls, or the scope of the M10-0 gate. In particular, evaluate:
   - **META-1**: does this 3-commit set close the M10-0 go/no-go gate that META-1 of your 13th review (PR #170) flagged? If not, what is still missing?
   - **META-2**: did the SH-FOLLOWUP-1 decision (keep `deny()` returning exit 0 + JSON, do not migrate to exit 2) regress any property of the Codex hook protocol you can verify against the upstream Codex docs?
   - **META-3**: SH-FOLLOWUP-2 routed the SH-1 print backstop through `ruff check --select T201` instead of a literal grep. Confirm whether the `inference/ollama_adapter.py:145` raw `print()` is actually a legitimate gap (and thus the ruff-equivalent design is fine) or a real existing-violation we should burn down here.
6. **Fact-check sheet** — restate any of the commands in the sheet above whose output you re-ran or any new ones you ran independently. Quote the actual output.

## Scope-specific risks for you to evaluate

- **SH-2 startup gate**: is the `RuntimeError` on `host=0.0.0.0 + all gates off` going to break the user's existing daily LAN workflow in a way the runbook (`docs/development-guidelines.md`) does not adequately surface? Note: memory `feedback_crlf_canonical_for_md5.md` and the SH-2 ADR explicitly preserve `host=0.0.0.0` default; the gate's contract is "you must opt into ONE protection".
- **SH-2 reserve_slot atomicity**: `len(self._queues) >= self._max_sessions` followed by `self._queues[session_id] = queue` is atomic relative to other event-loop callers because Python's asyncio is single-threaded, but verify the pre-accept fast-path and the in-loop authoritative `reserve_slot` are wired correctly so the race window (between pre-check and reserve) is closed by `_send_error` + close 1013, not by a silent allow.
- **SH-1 shell regex coverage**: the 7 regex patterns in `shell_write_targets` aim for the 5 red-team cases plus generic `>`/`>>` redirects with file extensions. Identify obvious bypasses I missed (e.g., `python -c "exec(...)"` indirection, base64-encoded payloads, `xargs` chains).
- **SH-1 CI gate behaviour on PRs from forks**: `policy-grep-gate` uses `fetch-depth: 0` and `git diff origin/main...HEAD`. Does this work for fork PRs where `origin` resolves to the fork? Check the GitHub Actions behaviour.
- **MEDIUM logger.warning** placement: I added the log inside the existing `if self._envelopes.maxsize > 0 and self._envelopes.full()` branch, after the count was bumped but before the warning ErrorMsg was enqueued. Confirm there is no path where the count is bumped but the log is skipped, or vice versa.
- **MEDIUM test coverage**: `test_consume_result_path_uses_drop_oldest_helper` calls the private `_enqueue_with_drop_oldest` directly rather than constructing a `CycleResult` and driving `_consume_result`. Is the shared-helper proof sufficient, or do you want a higher-fidelity test that exercises the full envelope loop?

## Constraints (must be preserved)

- `data/eval/golden/` / `src/erre_sandbox/evidence/` unchanged (verified empty in fact-check sheet)
- `SCHEMA_VERSION = "0.10.0-m7h"` unchanged (verified)
- No new `ControlEnvelope` types; the gateway uses existing `ErrorMsg.code` with new string value `"session_cap_exceeded"` (lifecycle scope) — consistent with SH-5's `"runtime_backlog_overflow"`
- `require_token=False` default (back-compat)
- `host=0.0.0.0` default preserved
- `idea_judgement*.md` / `data/eval/golden/_checksums_mac_received.txt` deliberately excluded from these commits

## Self-tests to run if you have shell

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -q -m "not godot and not eval and not spike and not training and not inference"
uv run pytest tests/test_integration/test_gateway.py tests/test_codex_hooks tests/test_world/test_runtime_lifecycle.py -q

# Codex hook smoke (SH-FOLLOWUP-1 JSON match form)
echo '{"tool":"exec_command","tool_input":{"command":"sed -i s/x/y/ src/erre_sandbox/x.py"}}' \
  | uv run python .codex/hooks/pre_tool_use_policy.py \
  | jq -e '.hookSpecificOutput.permissionDecision == "deny"'
```

Return your review as plain text starting with the executive verdict. Brevity is welcome; depth is welcome too — pick what serves the gate decision.
