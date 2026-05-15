# 設計 — security-hardening-pre-m10-followup

Refs:
- 親 decisions.md SH-1 / SH-2 (verbatim 引用は `decisions.md` 参照)
- 承認 Plan: `/Users/johnd/.claude/plans/steering-20260513-security-hardening-pr-peppy-forest.md`

## 実装アプローチ

親タスク (PR #170) で確定した **SH-1 + SH-2 ADR をゼロから設計し直さず、そのまま実装** する。/reimagine も skip 妥当 (alternatives 列挙 + ユーザー選択は親 task で完了)。

事前 fact-check (本 task 開始時、Explore 3 並列 + Read) で 2 点を確定:
- **`deny()` exit code 解釈**: 現状 `pre_tool_use_policy.py:37` は **exit 0 + JSON `permissionDecision:"deny"`** (Codex 公式 protocol)。`deny()` 関数は無変更、smoke test を JSON match に修正。
- **T201 backstop 設計**: `inference/ollama_adapter.py:145` に既存 raw print() があり CI green の運用実績。CI `policy-grep-gate` の print 検査は **`ruff check --select T201 src/erre_sandbox` 再実行** で ruff exemption を尊重する (grep ではない)。

## 変更対象

### 修正するファイル

#### SH-2 WS auth (commit 1)
- `src/erre_sandbox/integration/protocol.py` — L61 直後に `DEFAULT_ALLOWED_ORIGINS`/`MAX_ACTIVE_SESSIONS`/`SessionCapExceededError` 追加
- `src/erre_sandbox/integration/gateway.py` — L194-202 `Registry.add()` を `reserve_slot`/`release_slot` pair に置換 (caller 1 箇所)、L545 `accept()` 前に Origin/token/cap check
- `src/erre_sandbox/bootstrap.py` — L79-80 `BootConfig` に 4 field + `_resolve_ws_token` helper、`host=0.0.0.0` + `allowed_origins=()` + `require_token=False` で startup RuntimeError
- `src/erre_sandbox/__main__.py` — L104 直後に 4 argparse flag
- `tests/test_integration/test_gateway.py` — `class TestWebSocketAuth` (6 ケース)
- `docs/architecture.md:328` — 認証ポリシー UPDATE
- `docs/development-guidelines.md` — token rotate 運用ノート (新セクション)
- `README.md` — `mkdir -p var/secrets && chmod 700 var/secrets` 初回 provisioning

#### SH-1 hook + CI (commit 2)
- `.codex/hooks.json` — L30 matcher `apply_patch|Edit|Write` → `apply_patch|Edit|Write|exec_command|Bash`
- `.codex/hooks/pre_tool_use_policy.py` — `shell_write_targets(command)` helper (~50 行)、`target_map()` 分岐拡張、`.steering` completeness guard は impl_targets ベースなので自動発火
- `.github/workflows/ci.yml` — L137 末尾に `policy-grep-gate` job (~30 行)
- `tests/test_codex_hooks/__init__.py` (空)
- `tests/test_codex_hooks/test_shell_bypass_policy.py` (5 red-team ケース、subprocess + JSON stdout match)

#### Codex 13th MEDIUM 反映 (commit 3)
- `src/erre_sandbox/world/tick.py` — L801-810 間に `logger.warning("runtime backlog overflow: drops=%d maxsize=%d", ...)` 1 行追加
- `tests/test_world/test_runtime_lifecycle.py` — 4 boundary ケース追加 (maxsize boundary / monotonic overflow count / _consume_result drop-oldest / recv_envelope cancel path)
- `tests/test_cli/test_eval_run_golden.py` — `_resolve_memory_db_path` docstring に TOCTOU race window 注記 (新テスト無し)

### 新規作成するファイル
- `tests/test_codex_hooks/__init__.py`
- `tests/test_codex_hooks/test_shell_bypass_policy.py`
- `.steering/20260515-security-hardening-pre-m10-followup/codex-review-prompt.md` (Codex 14th 入力、Step 5 で起草)
- `.steering/20260515-security-hardening-pre-m10-followup/codex-review.md` (Codex 14th verbatim 出力)

### 削除するファイル
- `.steering/20260513-security-hardening-pre-m10/next-session-prompt.md` (P2 時点 stale、Step 6 closure commit で `git rm`)

## 影響範囲

| 領域 | 影響 | 対処 |
|---|---|---|
| Mac↔G-GEAR LAN rsync workflow | `require_token=False` default で **無影響** | tasklist の手動 smoke 検証 |
| Godot 4.4 WS client | Origin/token 未対応の場合、loopback 経由は変更なし | empty Origin 受容の if-branch を audit |
| M9-eval golden baseline | **完全に触らない** | `git diff origin/main..HEAD -- data/eval/golden src/erre_sandbox/evidence` で検証 |
| existing pytest suite | gateway / tick / cli signature 互換維持 | Registry.add は単一 caller なので mechanical 置換 |
| schema 互換 | `SCHEMA_VERSION` 不変、`ErrorMsg.code` `"runtime_backlog_overflow"` 流用 | schema bump 回避 |
| Codex hook の existing user workflow | shell 経由の `.steering` deny が新規発火 | red-team test 5 ケースで pattern 妥当性担保 |

## 既存パターンとの整合性

- WS auth Origin/token check: `gateway.py:520-543` subscribe parse error path (reject-before-accept) と同型
- WS session cap reject: `gateway.py:208-258` `Registry.fan_out` drop-oldest pattern と差別化 (cap は close 1013 hard fail、backlog は warning drop)
- `protocol.py:52` `MAX_ENVELOPE_BACKLOG: Final[int]` の constant 配置順序に揃える
- `BootConfig` (frozen dataclass): 既存 `agents: tuple[AgentSpec, ...]` field と同 grouping
- argparse: `__main__.py` の既存 `dest`/`type`/`default` style 踏襲
- Codex hook: `BANNED_PATTERNS` / `is_impl_path` / `task_status` 既存 API を変更しない (新 helper のみ追加)
- CI: `eval-egress-grep-gate` (L83-137) と同型 `runs-on`/`timeout-minutes`/`needs` 構造

## テスト戦略

### 単体テスト
- WS auth: 6 ケース (token miss/mismatch/match、origin reject、session cap close 1013、back-compat default)
- Shell-bypass hook: 5 red-team ケース (sed/echo/tee/python-c/heredoc)
- Runtime queue boundary: 4 ケース (maxsize-1/maxsize/maxsize+1 + monotonic + _consume_result + cancel)

### 統合テスト
- 既存 `test_gateway.py` `test_fan_out_drops_oldest_*` が green 維持
- 既存 `test_multi_agent_stream.py` が token=None default で green (no auth-related assertions)

### E2E
- **Mac↔G-GEAR LAN smoke**: 手動 (`require_token=False` で既存 rsync workflow 不変を確認、手順は `decisions.md` ADR addendum)
- **Codex hook smoke** (JSON match):
  ```bash
  echo '{"tool":"exec_command","tool_input":{"command":"sed -i s/x/y/ src/erre_sandbox/x.py"}}' \
    | uv run python .codex/hooks/pre_tool_use_policy.py \
    | jq -e '.hookSpecificOutput.permissionDecision == "deny"'
  ```

## ロールバック計画

- SH-2 (commit 1): `bootstrap.py` の 4 field 削除 + `gateway.py` の auth gate コメントアウト + `Registry.add` 復元
- SH-1 (commit 2): `.codex/hooks.json` matcher を `apply_patch|Edit|Write` に戻す + `policy-grep-gate` job 削除
- MEDIUM (commit 3): `logger.warning` 1 行削除 + 4 boundary tests revert

各 commit は独立 revert 可能。一括 PR を merge 後に問題発生時は **finding 単位で revert PR** を出す方針 (親 task と同じ)。

## Codex 14th review (Step 5)

PR #170 と同じ pattern:
1. `codex-review-prompt.md` 起草 (P4 / P5 / MEDIUM 反映を scope、4 commits 一括 review)
2. `cat codex-review-prompt.md | codex exec --skip-git-repo-check`
3. 出力を `codex-review.md` に verbatim 保存 + `.codex/budget.json` history 更新
4. HIGH 全件: 実装に反映、commit/PR description に明記
5. MEDIUM: `decisions.md` ADR addendum で採否記録
6. LOW: `blockers.md` defer 可
