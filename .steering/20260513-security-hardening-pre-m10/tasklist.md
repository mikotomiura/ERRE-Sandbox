# タスクリスト — security-hardening-pre-m10

Plan: `/Users/johnd/.claude/plans/agile-chasing-sifakis.md`
Design-final: `design-final.md` (= `design.md` v1 を SH-0 prosess で昇格)

## P0 — Scaffold (完了)

- [x] [Mac] branch `feature/security-hardening-pre-m10` 作成
- [x] [Mac] `requirement.md` 起草 (`codex_issue.md` 6 finding 統合、Path A 採用)
- [x] [Mac] `design.md` v1 起草 (5 finding 詳細化、再利用パターン明示)
- [x] [Mac] `decisions.md` ADR SH-0〜SH-5 起草 (SH-0 で /reimagine 代替プロセス明示)
- [x] [Mac] `design-final.md` = design.md v1 昇格 (SH-0 判定)

## P1 — §3 Codex network split (SH-3、~0.5h) — 完了

- [x] [Mac] `.codex/config.toml:10` — `network_access = true` → `false`
- [x] [Mac] `.codex/config.toml:4` — `web_search = "live"` 据置を確認
- [x] [Mac] `AGENTS.md` — "Network access policy" section 追加
  (SGLang v0.3+ multi-LoRA 発見実績 citation、per-session 明示承認運用)
- [x] [Mac] `.agents/skills/erre-workflow/SKILL.md` — 同ノート追加
- [x] [Mac] commit: `chore(codex): network_access=false split (SH-3)`

## P2 — §4 `--memory-db` guard (SH-4、~2h) — 完了

- [x] [Mac] `cli/eval_run_golden.py` — `ALLOWED_MEMORY_DB_PREFIX_STRINGS` + `_ALLOWED_MEMORY_DB_TMP_BASENAME_PREFIXES` constant 追加
  (`/tmp/p3a_natural_` / `/tmp/erre-` / `var/eval/`)
- [x] [Mac] `cli/eval_run_golden.py:711-775` 近傍 — `_resolve_memory_db_path()` helper 追加 + macOS `/tmp` → `/private/tmp` symlink 正規化対応
  (symlink reject / prefix check / overwrite gate)
- [x] [Mac] `cli/eval_run_golden.py:1029-1030` — unconditional unlink を helper 経由に
- [x] [Mac] `cli/eval_run_golden.py:1269-1292` — `--overwrite-memory-db` flag 追加
- [x] [Mac] `capture_natural()` signature — `overwrite_memory_db: bool = False` 追加 + caller `main()` で wire
- [x] [Mac] `tests/test_cli/test_eval_run_golden.py` — 5 red-team ケース追加
  (symlink / prefix / exists / overwrite / default auto-unlink)
- [x] [Mac] `uv run pytest tests/test_cli/test_eval_run_golden.py -q -m eval` → 27 passed
- [x] [Mac] 全 CI 緑確認 (`ruff check / format --check / mypy / pytest 1341 passed`)
- [x] [Mac] commit: `feat(cli): eval --memory-db symlink+prefix+overwrite guard (SH-4)`

## P3 — §5 bounded envelope queue + warning (SH-5、~3h) — 完了

- [x] [Mac] `world/tick.py:386` — `_envelopes` を 2-queue 分割
  (`_heartbeat_envelopes` maxsize=1 + `_envelopes` maxsize=1024)
- [x] [Mac] `world/tick.py:715-732` `inject_envelope()` — drop-oldest + ErrorMsg
  `runtime_backlog_overflow` warning (gateway L208-261 同型、`_enqueue_with_drop_oldest` 経由)
- [x] [Mac] `world/tick.py:1283-1296` heartbeat 経路 — coalesce 化 (put_nowait → QueueFull → drain → put_nowait)
- [x] [Mac] `world/tick.py:1366` `_consume_result` — `_enqueue_with_drop_oldest` 経由
- [x] [Mac] `world/tick.py:719-757` `recv_envelope` — 2-queue race-merge (main 優先 + heartbeat coalesce-requeue / Codex 13th HIGH-1 反映後)
- [x] [Mac] `_make_error` helper の location 確定: tick.py 内に私的 `_make_runtime_error`
  を定義 (architecture-rules: world → integration 逆向き依存を回避)
- [x] [Mac] `tests/test_world/test_runtime_lifecycle.py` — 3 ケース追加
  (overflow warning / heartbeat coalesce / recv mixed-ready preserves heartbeat)
- [x] [Mac] 既存 `runtime.drain_envelopes()` caller audit + `test_heartbeat_emits_world_tick_msgs_periodically`
  を coalesce 仕様に合わせて mechanical 調整 (`== 5` → `== 1`)
- [x] [Mac] `integration/protocol.py:52` MAX_ENVELOPE_BACKLOG docstring を「runtime も bounded」に更新
- [x] [Mac] `uv run pytest tests/test_world tests/test_integration/test_gateway.py tests/test_integration/test_multi_agent_stream.py -q` → 182 passed
- [x] [Mac] commit: `feat(world): bounded envelope queue + warning (SH-5)` (`9061173`)

## P4 — §2 WS auth (SH-2、~5h) — **DEFERRED post-PR** (Codex 13th HIGH-5)

Rationale: 本 branch は P0-P3 partial hardening として close。Codex 13th が
META-1 で「P4/P5 defer のまま M10-0 進めるのは不可」と判定したため、後続
follow-up task で実装。M10-0 着手の前提条件として `blockers.md` に記録。

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

## P5 — §1 hook + CI shell-bypass (SH-1、~3h) — **DEFERRED post-PR** (Codex 13th HIGH-5)

Rationale: P4 と同じく M10-0 着手の前提条件として `blockers.md` に記録、後続
follow-up task で実装。SH-1 ADR は本 branch で起草済 (`decisions.md`) なので
follow-up でゼロから設計し直す必要なし。


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

## P6 — Codex 13th independent review (~2h) — 完了

- [x] [Mac] `codex-review-prompt.md` 起草 (4 commits + 5 ADR + fact-check sheet)
- [x] [Mac] `cat codex-review-prompt.md | codex exec --skip-git-repo-check` 実行
  (261,690 tokens、`per_invocation_max=200K` を 61K overrun、warn policy 通り)
- [x] [Mac] 出力を `codex-review.md` に verbatim 保存
- [x] [Mac] HIGH 反映:
  - HIGH-1 `recv_envelope`: heartbeat coalesce-requeue + `asyncio.gather(return_exceptions=True)` で cancel 後 await
  - HIGH-3 `_resolve_memory_db_path` default: `os.path.lexists` + `is_symlink` で broken symlink を検出
  - HIGH-5 scope correction: tasklist (P0-P3 = 完了 / P4-P5 = defer)、design-final 更新、blockers M10-0 go/no-go
- [x] [Mac] MEDIUM: HIGH-2 (recv vs drain asymmetry) は docstring + regression test、
  HIGH-4 (web_search/network_access split) は ADOPT、test coverage / observability は decisions.md に MEDIUM addendum
- [x] [Mac] LOW: ADOPT (commit messages / naming / typing 問題なし)
- [x] [Mac] HIGH/MEDIUM 反映 commit

## P7 — Closure (partial: P0-P3 / P4-P5 deferred)

- [ ] [Mac] CI gate 全緑: `uv run ruff check src tests` / `uv run ruff format --check src tests`
  / `uv run mypy src` / `uv run pytest -q -m "not godot and not eval and not spike and not training and not inference"`
- [ ] [Mac] 重点 test: gateway / world / cli 全緑 (codex_hooks は P5 と同時 defer)
- [ ] [Mac] `git diff --check` 緑
- [ ] [Mac] **M9 baseline 不可侵検証**: `git diff origin/main..HEAD -- data/eval/golden src/erre_sandbox/evidence` 空であること
- [ ] [Mac] requirement.md 受け入れ条件のうち §3/§4/§5 (= SH-3/SH-4/SH-5) を [x] 化、§1/§2 は defer 注記
- [ ] [Mac] `idea_judgement.md` (root) を移管しない (M10-0 task で別途 scaffold 時に処理)
- [ ] [Mac] PR 作成: title = `feat(security): security-hardening-pre-m10 P0-P3 partial (HIGH§1/§2 deferred)`、
  description で `codex-review.md` リンク + HIGH-1/HIGH-3/HIGH-5 反映状況 + P4/P5 defer 理由を明記
- [ ] [Mac] **follow-up task scaffold** (post-merge): `security-hardening-pre-m10-followup` で SH-1 + SH-2 を実装、
  M10-0 着手の go/no-go gate として位置付け (`blockers.md` 参照)

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
