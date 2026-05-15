# タスクリスト — security-hardening-pre-m10-followup

Plan: `/Users/johnd/.claude/plans/steering-20260513-security-hardening-pr-peppy-forest.md`
Refs:
- 親 tasklist: `.steering/20260513-security-hardening-pre-m10/tasklist.md` (P4 + P5)
- 起点 prompt: `.steering/20260513-security-hardening-pre-m10/next-session-prompt-followup.md`

## P0 — Scaffold (完了)

- [x] [Mac] branch `feature/security-hardening-pre-m10-followup` 作成
- [x] [Mac] `requirement.md` 起草 (M10-0 gate 文脈 + PR #170 Refs)
- [x] [Mac] `design.md` 起草 (SH-1 / SH-2 ADR を親 task から引用、本 task は実装のみ)
- [x] [Mac] `decisions.md` 起草 (SH-1 / SH-2 verbatim 引用 + 開始時 fact-check 2 件記録)
- [x] [Mac] `blockers.md` 空起草 (実装中に発覚分を記録)

## P4 — SH-2 WS auth (~5h)

### P4a — protocol + Registry

- [ ] [Mac] `integration/protocol.py:L61` 直後 — `DEFAULT_ALLOWED_ORIGINS: Final[tuple[str, ...]] = ()` + `MAX_ACTIVE_SESSIONS: Final[int] = 8` constant 追加 + docstring
- [ ] [Mac] `integration/protocol.py` — `SessionCapExceededError(Exception)` 追加
- [ ] [Mac] `integration/gateway.py:L194-202` — `Registry.add()` を `reserve_slot(session_id, queue, *, subscribed_agents) / release_slot(session_id)` pair に置換 (~20 行)、cap 超過時 `SessionCapExceededError` raise
- [ ] [Mac] `Registry.__init__` に `max_sessions: int` 追加 (default = `protocol.MAX_ACTIVE_SESSIONS`)

### P4b — bootstrap + CLI

- [ ] [Mac] `bootstrap.py:L79-80` `BootConfig` — `ws_token: str | None = None` / `require_token: bool = False` / `allowed_origins: tuple[str, ...] = field(default_factory=tuple)` / `max_sessions: int = 8` field 追加 (~4 行)
- [ ] [Mac] `bootstrap.py` — `_resolve_ws_token(cfg: BootConfig) -> str | None` helper (file `var/secrets/ws_token` → env `ERRE_WS_TOKEN` → None)
- [ ] [Mac] `bootstrap.py` `bootstrap()` — `host=0.0.0.0` + `allowed_origins=()` + `require_token=False` の startup `RuntimeError` 実装
- [ ] [Mac] `__main__.py:L104` 直後 — `--ws-token` / `--require-token` (action=store_true) / `--allowed-origins` (comma list) / `--max-sessions` (type=int, default=8) flag 追加 (~15 行)

### P4c — gateway integration

- [ ] [Mac] `integration/gateway.py:L518-552` — `ws_observe()` の `accept()` (L545) 前に Origin/token/cap check 挿入 (subscribe parse error path L520-543 と同型)、close code 1008 (policy) / 1013 (try-again-later)
- [ ] [Mac] `finally` block で `registry.release_slot(session_id)` 確実呼出
- [ ] [Mac] `secrets.compare_digest` で token constant-time compare

### P4d — test + doc

- [ ] [Mac] `tests/test_integration/test_gateway.py` に `class TestWebSocketAuth` 追加 (6 ケース):
  - [ ] `test_token_missing_closes_with_1008`
  - [ ] `test_token_mismatch_closes_with_1008`
  - [ ] `test_token_match_continues`
  - [ ] `test_origin_rejected_closes_with_1008`
  - [ ] `test_session_cap_exceeded_closes_with_1013`
  - [ ] `test_back_compat_no_token_required_by_default`
- [ ] [Mac] `docs/architecture.md:L328` — 「認証なし (LAN 内前提)」 → 「shared-token (opt-in) + Origin allow-list + session cap=8 (LAN 内前提)」
- [ ] [Mac] `docs/development-guidelines.md` — `var/secrets/ws_token` rotate 運用ノート (新セクション)
- [ ] [Mac] `README.md` — `mkdir -p var/secrets && chmod 700 var/secrets` 初回 provisioning 手順
- [ ] [Mac] `uv run pytest tests/test_integration/test_gateway.py tests/test_integration/test_multi_agent_stream.py -q` 緑確認
- [ ] [Mac] Mac↔G-GEAR LAN smoke (手動、`require_token=False` で既存 rsync 不変を確認、`decisions.md` ADR addendum に手順記録)
- [ ] [Mac] **follow-up task 起票**: `feat/ws-token-enforce` (`require_token=True` default 化、Godot WS client patch 後) — 本 task では実装しない
- [ ] [Mac] commit: `feat(ws): shared-token + Origin + session cap (SH-2)`

## P5 — SH-1 hook + CI shell-bypass (~3h)

- [ ] [Mac] `.codex/hooks.json:L30` — matcher を `apply_patch|Edit|Write|exec_command|Bash` に拡張
- [ ] [Mac] `.codex/hooks/pre_tool_use_policy.py` — `shell_write_targets(command: str) -> dict[str, list[str]]` helper 追加 (~50 行、`direct_targets()` と `target_map()` の間)
  - deny pattern: sed -i / perl -pi / gsed -i / echo > / echo >> / tee / python -c open|write_text / heredoc redirect (`cat <<...>` / `python -c <<EOF`)
- [ ] [Mac] `.codex/hooks/pre_tool_use_policy.py` — `target_map()` を shell branch 拡張 (`tool_input.command` が shell command のとき `shell_write_targets` 経由)
- [ ] [Mac] `.codex/hooks/pre_tool_use_policy.py` — `.steering` completeness guard (L106-118) は impl_targets ベースなので shell 経路でも自動発火 (実装変更なし、確認のみ)
- [ ] [Mac] `.github/workflows/ci.yml:L137` 末尾 — `policy-grep-gate` job 追加 (~30 行):
  - banned import grep (openai/anthropic + bpy)
  - print 検査は `uv run ruff check --select T201 src/erre_sandbox` (ruff 再実行で exemption 尊重)
  - `.steering` completeness: `git diff --name-only origin/main..HEAD` が `src/erre_sandbox/**/*.py` を含むとき `.steering/[0-9]*` に最新 requirement/design/tasklist 全揃いを find で確認
- [ ] [Mac] `tests/test_codex_hooks/__init__.py` (空ファイル)
- [ ] [Mac] `tests/test_codex_hooks/test_shell_bypass_policy.py` — 5 red-team subprocess ケース:
  1. `sed -i 's/.../import openai/' src/erre_sandbox/inference/sglang_adapter.py`
  2. `echo "import bpy" >> src/erre_sandbox/world/tick.py`
  3. `tee src/erre_sandbox/x.py < /dev/null`
  4. `python -c "open('src/erre_sandbox/y.py','w').write('print(1)')"`
  5. `cat > src/erre_sandbox/z.py <<EOF\nimport anthropic\nEOF`
  各ケースで `subprocess.run` + stdin JSON payload、stdout JSON `permissionDecision == "deny"` を assert
- [ ] [Mac] `uv run pytest tests/test_codex_hooks -q` 緑確認
- [ ] [Mac] hook smoke (JSON match):
  ```bash
  echo '{"tool":"exec_command","tool_input":{"command":"sed -i s/x/y/ src/erre_sandbox/x.py"}}' \
    | uv run python .codex/hooks/pre_tool_use_policy.py \
    | jq -e '.hookSpecificOutput.permissionDecision == "deny"'
  ```
  Expected: jq exit 0 (match success) + JSON deny in stdout
- [ ] [Mac] commit: `feat(codex): hook + CI shell-bypass guard (SH-1)`

## P-MEDIUM — Codex 13th MEDIUM 反映 (~1h)

- [ ] [Mac] `src/erre_sandbox/world/tick.py:L801-810` 間 — `logger.warning("runtime backlog overflow: drops=%d maxsize=%d", self._envelope_overflow_count, self._envelopes.maxsize)` 1 行追加
- [ ] [Mac] `tests/test_world/test_runtime_lifecycle.py::TestWorldRuntimeEnvelopeQueue` に 4 ケース追加:
  - [ ] `test_envelope_queue_maxsize_minus_one_no_overflow`
  - [ ] `test_envelope_queue_maxsize_exact_no_overflow`
  - [ ] `test_envelope_queue_maxsize_plus_one_triggers_overflow`
  - [ ] `test_repeated_overflow_increments_count_monotonically`
  - [ ] `test_consume_result_path_also_drops_oldest`
  - [ ] `test_recv_envelope_cancel_path_releases_resources_cleanly`
  ※ Plan で 4 ケースと記載したが maxsize boundary は 3 sub-cases に分解して計 6 sub-test (実質 4 グループ)
- [ ] [Mac] `tests/test_cli/test_eval_run_golden.py` — `_resolve_memory_db_path` の docstring 内に TOCTOU race window 注記追加 (新テスト無し、コメントのみ)
- [ ] [Mac] commit: `feat(observability+tests): SH-5 logger.warning + SH-4/SH-5 coverage`

## P6 — Codex 14th independent review (~2h)

- [ ] [Mac] `.steering/20260515-security-hardening-pre-m10-followup/codex-review-prompt.md` 起草 (3 commits + ADR addendum + fact-check sheet を scope に)
- [ ] [Mac] `cat codex-review-prompt.md | codex exec --skip-git-repo-check` 実行 (`.codex/budget.json` の per_invocation_max 200K warn を予想)
- [ ] [Mac] 出力を `codex-review.md` に verbatim 保存
- [ ] [Mac] `.codex/budget.json` history に 14th run 追記
- [ ] [Mac] HIGH 全件反映 (実装 commit、PR description にも明記)
- [ ] [Mac] MEDIUM: `decisions.md` ADR addendum で採否記録
- [ ] [Mac] LOW: `blockers.md` defer 可、理由明記
- [ ] [Mac] HIGH 反映 commit (件数次第): `fix(security): Codex 14th HIGH 反映`

## P7 — Closure + PR 起票

- [ ] [Mac] CI gate 全緑: `uv run ruff check src tests` / `uv run ruff format --check src tests` / `uv run mypy src` / `uv run pytest -q -m "not godot and not eval and not spike and not training and not inference"`
- [ ] [Mac] 重点 test: gateway / world / cli / codex_hooks 全緑
- [ ] [Mac] `git diff --check` 緑
- [ ] [Mac] **M9 baseline 不可侵検証**: `git diff origin/main..HEAD -- data/eval/golden src/erre_sandbox/evidence` 空
- [ ] [Mac] `SCHEMA_VERSION = "0.10.0-m7h"` 不変確認
- [ ] [Mac] `git rm .steering/20260513-security-hardening-pre-m10/next-session-prompt.md` (P2 時点 stale、closure commit 同梱)
- [ ] [Mac] `idea_judgement*.md` と `_checksums_mac_received.txt` を本 task の commit に **含めない**
- [ ] [Mac] PR 作成: title = `feat(security): security-hardening-pre-m10-followup (SH-1 + SH-2 + MEDIUM 反映)`、description で
  - 親 PR #170 を Refs
  - `codex-review.md` (Codex 14th) link + verdict 引用
  - **M10-0 着手 gate の解除** を明示
  - HIGH 反映状況 + MEDIUM 採否

## Risk monitor

- Godot 4.4 native WS の Origin header 挙動: P4c (gateway 統合) 着手時に godot_project/ で empirical 確認
- `Registry.add()` deprecation cycle: 単一 caller なので mechanical 置換、test 影響なければ deprecation 不要 (置換のみ)
- Codex 14th が新 HIGH 切出時の scope 拡大: 親 task で HIGH 3 件反映の前例あり、Step 5 の 2h で +1-2h 吸収可能
- CI `policy-grep-gate` job の `git diff --name-only origin/main..HEAD`: GHA context で `origin/main` fetch が必要 (`actions/checkout@v4` の `fetch-depth: 0` 設定確認)

## Hours estimate

| Phase | Owner | Hours |
|---|---|---|
| P0 Scaffold | Claude (Mac) | 0.5 |
| P4 SH-2 WS auth | Claude (Mac) | 5 |
| P5 SH-1 hook+CI | Claude (Mac) | 3 |
| P-MEDIUM 反映 | Claude (Mac) | 1 |
| P6 Codex 14th | Claude (Mac) | 2 |
| P7 Closure + PR | Claude (Mac) | 1 |
| **Total** | | **~12.5h** (2-3 working days) |
