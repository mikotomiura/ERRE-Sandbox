# タスクリスト — security-hardening-pre-m10

Plan: `/Users/johnd/.claude/plans/agile-chasing-sifakis.md`
Design-final: `design-final.md` (= `design.md` v1 を SH-0 prosess で昇格)

## P0 — Scaffold (完了)

- [x] [Mac] branch `feature/security-hardening-pre-m10` 作成
- [x] [Mac] `requirement.md` 起草 (`codex_issue.md` 6 finding 統合、Path A 採用)
- [x] [Mac] `design.md` v1 起草 (5 finding 詳細化、再利用パターン明示)
- [x] [Mac] `decisions.md` ADR SH-0〜SH-5 起草 (SH-0 で /reimagine 代替プロセス明示)
- [x] [Mac] `design-final.md` = design.md v1 昇格 (SH-0 判定)

## P1 — §3 Codex network split (SH-3、~0.5h)

- [ ] [Mac] `.codex/config.toml:10` — `network_access = true` → `false`
- [ ] [Mac] `.codex/config.toml:4` — `web_search = "live"` 据置を確認
- [ ] [Mac] `AGENTS.md` — "Network access policy" section 追加
  (SGLang v0.3+ multi-LoRA 発見実績 citation、per-session 明示承認運用)
- [ ] [Mac] `.agents/skills/erre-workflow/SKILL.md` — 同ノート追加
- [ ] [Mac] commit: `chore(codex): network_access=false split (SH-3)`

## P2 — §4 `--memory-db` guard (SH-4、~2h)

- [ ] [Mac] `cli/eval_run_golden.py` — `ALLOWED_MEMORY_DB_PREFIXES` constant 追加
  (`/tmp/p3a_natural_` / `/tmp/erre-` / `var/eval/`)
- [ ] [Mac] `cli/eval_run_golden.py:711-775` 近傍 — `_resolve_memory_db_path()` helper 追加
  (symlink reject / prefix check / overwrite gate)
- [ ] [Mac] `cli/eval_run_golden.py:1029-1030` — unconditional unlink を helper 経由に
- [ ] [Mac] `cli/eval_run_golden.py:1269-1292` — `--overwrite-memory-db` flag 追加
- [ ] [Mac] `tests/test_cli/test_eval_run_golden.py` — 4 red-team ケース追加
  (symlink / prefix / exists / overwrite)
- [ ] [Mac] `uv run pytest tests/test_cli/test_eval_run_golden.py -q` 緑確認
- [ ] [Mac] commit: `feat(cli): eval --memory-db symlink+prefix+overwrite guard (SH-4)`

## P3 — §5 bounded envelope queue + warning (SH-5、~3h)

- [ ] [Mac] `world/tick.py:386` — `_envelopes` を 2-queue 分割
  (`_heartbeat_envelopes` maxsize=1 + `_envelopes` maxsize=1024)
- [ ] [Mac] `world/tick.py:722` `inject_envelope()` — drop-oldest + ErrorMsg
  `runtime_backlog_overflow` warning (gateway L208-258 同型)
- [ ] [Mac] `world/tick.py:1271` heartbeat 経路 — coalesce 化 (drain 旧 → push 新)
- [ ] [Mac] `world/tick.py:1340` `_consume_result` — drop-oldest + warning
- [ ] [Mac] `world/tick.py` `recv_envelope` — 2-queue race-merge (main 優先)
- [ ] [Mac] `_make_error` helper の location 確定 (内部 vs 共通 utility 昇格、
  Codex 13th review で再判断)
- [ ] [Mac] `tests/test_world/test_runtime_lifecycle.py` — 2 ケース追加
  (overflow warning / heartbeat coalesce)
- [ ] [Mac] 既存 `runtime.drain_envelopes()` caller test の audit (mechanical 調整)
- [ ] [Mac] `uv run pytest tests/test_world -q` 緑確認
- [ ] [Mac] commit: `feat(world): bounded envelope queue + warning (SH-5)`

## P4 — §2 WS auth (SH-2、~5h)

### P4a — protocol + Registry

- [ ] [Mac] `integration/protocol.py:52` 近傍 — `DEFAULT_ALLOWED_ORIGINS` + `MAX_ACTIVE_SESSIONS=8` constant 追加
- [ ] [Mac] `integration/protocol.py` — `SessionCapExceededError` exception 追加
- [ ] [Mac] `integration/gateway.py:194-202` — `Registry.add()` を `reserve_slot()` / `release_slot()` pair に置換

### P4b — bootstrap + CLI

- [ ] [Mac] `bootstrap.py:70-71` `BootConfig` — `ws_token` / `require_token` / `allowed_origins` / `max_sessions` field 追加
- [ ] [Mac] `bootstrap.py` — `_resolve_ws_token()` helper (file → env → None)
- [ ] [Mac] `__main__.py:73-74` — `--ws-token` / `--require-token` / `--allowed-origins` / `--max-sessions` flag 追加
- [ ] [Mac] `host=0.0.0.0` + empty origin + `require_token=False` の startup error 実装

### P4c — gateway integration

- [ ] [Mac] `integration/gateway.py:518-552` — `accept()` 前に Origin/token/cap check 挿入
  (subscribe parse error path L532-543 と同型)
- [ ] [Mac] `finally` で `registry.release_slot(session_id)` 確実呼出

### P4d — test + doc

- [ ] [Mac] `tests/test_integration/test_gateway.py` — 6 ケース追加
- [ ] [Mac] `docs/architecture.md:330` — 認証ポリシー更新
- [ ] [Mac] `docs/development-guidelines.md` — token rotate 運用ノート
- [ ] [Mac] `README.md` — `var/secrets/` provisioning 手順
- [ ] [Mac] `uv run pytest tests/test_integration/test_gateway.py tests/test_integration/test_multi_agent_stream.py -q` 緑確認
- [ ] [Mac] Mac↔G-GEAR LAN smoke (手動、`require_token=False` 確認、decisions.md に手順記録)
- [ ] [Mac] **follow-up task 起票**: `feat/ws-token-enforce` (`require_token=True` default 化、Godot WS client patch 後)
- [ ] [Mac] commit: `feat(ws): shared-token + Origin + session cap (SH-2)`

## P5 — §1 hook + CI shell-bypass (SH-1、~3h)

- [ ] [Mac] `.codex/hooks.json:28-39` — matcher を `apply_patch|Edit|Write|exec_command|Bash` に拡張
- [ ] [Mac] `.codex/hooks/pre_tool_use_policy.py` — `shell_write_targets(command)` helper 追加
  (sed/echo/tee/python-c/heredoc deny pattern)
- [ ] [Mac] `.codex/hooks/pre_tool_use_policy.py` — shell 経路で `.steering` completeness guard 発火
- [ ] [Mac] `.github/workflows/ci.yml` — `policy-grep-gate` job 追加
  (banned import + ruff T201 backstop + `.steering` completeness)
- [ ] [Mac] `tests/test_codex_hooks/__init__.py` + `test_shell_bypass_policy.py` 5 ケース
- [ ] [Mac] `uv run pytest tests/test_codex_hooks -q` 緑確認
- [ ] [Mac] hook smoke: `echo '{"tool":"exec_command","tool_input":{"command":"sed -i s/x/y/ src/erre_sandbox/x.py"}}' | uv run python .codex/hooks/pre_tool_use_policy.py`
  → exit 2 + deny message
- [ ] [Mac] commit: `feat(codex): hook + CI shell-bypass guard (SH-1)`

## P6 — Codex 13th independent review (~2h)

- [ ] [Mac] `codex-review-prompt.md` 起草 (5 ADR + design-final.md + 検証コマンドを scope に)
- [ ] [Mac] `cat codex-review-prompt.md | codex exec --skip-git-repo-check` 実行
- [ ] [Mac] 出力を `codex-review.md` に **verbatim 保存** (要約しない)
- [ ] [Mac] HIGH 全件: `design-final.md` に反映、commit/PR description にも明記
- [ ] [Mac] MEDIUM: `decisions.md` に採否を ADR addendum 形式で記録
- [ ] [Mac] LOW: `blockers.md` に defer 可、理由明記
- [ ] [Mac] HIGH/MEDIUM 反映 commit (必要に応じ複数 commit)

## P7 — Closure

- [ ] [Mac] CI gate 全緑: `uv run ruff check src tests` / `uv run ruff format --check src tests`
  / `uv run mypy src` / `uv run pytest -q -m "not godot and not eval and not spike and not training and not inference"`
- [ ] [Mac] 重点 test: gateway / world / cli / codex_hooks 全緑
- [ ] [Mac] `git diff --check` 緑
- [ ] [Mac] **M9 baseline 不可侵検証**: `git diff origin/main..HEAD -- data/eval/golden src/erre_sandbox/evidence` 空であること
- [ ] [Mac] requirement.md 受け入れ条件 9 件全 [x] 化
- [ ] [Mac] `idea_judgement.md` (root) を移管しない (M10-0 task で別途 scaffold 時に処理)
- [ ] [Mac] PR 作成: title = `feat(security): codex_issue.md §1-§5 統合消化 (M10 pre-hardening)`、
  description で `codex-review.md` リンク + HIGH/MEDIUM 反映状況を明記

## Risk monitor

- Godot 4.4 native WS の Origin header 挙動: P4c 着手時に godot_project/ で empirical 確認
- `_make_error` helper の location 判断: P3 着手時に gateway 内部 vs 共通 utility を判断、
  Codex 13th review が closure 判定
- `recv_envelope` 2-queue race-merge の CancelledError 吸収: P3 実装時に audit

## Hours estimate

| Phase | Owner | Hours |
|---|---|---|
| P0 (完了) | Claude (Mac) | 1.5 |
| P1 §3 | Claude (Mac) | 0.5 |
| P2 §4 | Claude (Mac) | 2 |
| P3 §5 | Claude (Mac) | 3 |
| P4 §2 | Claude (Mac) | 5 |
| P5 §1 | Claude (Mac) | 3 |
| P6 Codex 13th | Claude (Mac) | 2 |
| P7 Closure | Claude (Mac) | 1 |
| **Total** | | **~18h** (2-3 working days) |
