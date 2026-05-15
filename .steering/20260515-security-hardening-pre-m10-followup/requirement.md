# security-hardening-pre-m10-followup

Refs:
- 親タスク: `.steering/20260513-security-hardening-pre-m10/` (PR #170, main=`4884f9d`)
- 起点プロンプト: `.steering/20260513-security-hardening-pre-m10/next-session-prompt-followup.md`
- 承認 Plan: `/Users/johnd/.claude/plans/steering-20260513-security-hardening-pr-peppy-forest.md`

## 背景

PR #170 (`feat(security): security-hardening-pre-m10 P0-P3 partial`) で SH-3/SH-4/SH-5 を消化済。Codex 13th independent review (`codex-review.md` META-1) は `P4/P5 を defer したまま M10-0 に進む判断は不可。特に SH-1 は元 HIGH で、未対応のまま "pre-M10 hardening complete" とは言えない` と判定した。

本タスクは **M10-0 (Individual layer schema + persona_id) 着手の go/no-go gate** として、deferred な以下 2 件を消化する:

| Section | ADR | 概要 | 工数 |
|---|---|---|---|
| §1 | SH-1 | Codex hook + CI shell-bypass policy gate | ~3h |
| §2 | SH-2 | WS shared-token + Origin allow-list + session cap | ~5h |

加えて Codex 13th MEDIUM (overflow observability + test coverage gaps) を同梱消化する (~1h)。

## ゴール

1. **SH-2 WS auth** (3-layer independent: token + Origin + cap=8) を `require_token=False` default で実装
2. **SH-1 shell-bypass guard** (Codex hook matcher 拡張 + CI policy-grep-gate job) を実装
3. Codex 13th MEDIUM 反映: runtime overflow `logger.warning` 追加、4 boundary tests、TOCTOU docstring
4. Codex 14th independent review で closure (HIGH 全件反映)
5. PR description で **M10-0 着手 gate 解除** を明示

## スコープ

### 含むもの
- `integration/protocol.py` / `gateway.py` / `bootstrap.py` / `__main__.py` の WS auth 統合
- `.codex/hooks.json` / `pre_tool_use_policy.py` / `.github/workflows/ci.yml` の shell-bypass guard
- `tests/test_integration/test_gateway.py` 6 ケース追加 (TestWebSocketAuth)
- `tests/test_codex_hooks/` 新規 directory + 5 red-team ケース
- `tests/test_world/test_runtime_lifecycle.py` 4 boundary ケース追加
- `world/tick.py` `_enqueue_with_drop_oldest` に `logger.warning` 1 行追加
- `tests/test_cli/test_eval_run_golden.py` の TOCTOU docstring 追記 (新テスト追加なし)
- Doc: `docs/architecture.md:328` / `docs/development-guidelines.md` / `README.md`
- `.steering/20260513-security-hardening-pre-m10/next-session-prompt.md` の `git rm` (P2 時点 stale)

### 含まないもの
- `feat/ws-token-enforce` (`require_token=True` default 化、Godot WS client patch 後の別 task)
- M10-0 task scaffold (本 task の close + Codex 14th green verdict 後)
- `idea_judgement.md` / `idea_judgement_2.md` の処理 (ユーザー方針で別 task)
- `data/eval/golden/_checksums_mac_received.txt` (eval/ 領域、別 task)
- 新 ADR の起票 (SH-1 / SH-2 ADR は親 task で確定済、本 task では ADR addendum のみ)

## 受け入れ条件

- [ ] `uv run ruff check src tests` / `uv run ruff format --check src tests` / `uv run mypy src` 全緑
- [ ] `uv run pytest -q -m "not godot and not eval and not spike and not training and not inference"` 全緑
- [ ] `tests/test_codex_hooks/` の 5 red-team ケース全 PASS
- [ ] `tests/test_integration/test_gateway.py::TestWebSocketAuth` の 6 ケース全 PASS
- [ ] `tests/test_world/test_runtime_lifecycle.py::TestWorldRuntimeEnvelopeQueue` の追加 4 ケース全 PASS
- [ ] `git diff origin/main..HEAD -- data/eval/golden src/erre_sandbox/evidence` 空
- [ ] `src/erre_sandbox/schemas.py:44` `SCHEMA_VERSION = "0.10.0-m7h"` 不変
- [ ] Codex hook smoke (JSON match): `... | jq -e '.hookSpecificOutput.permissionDecision == "deny"'` exit 0
- [ ] `docs/architecture.md:328` 認証ポリシー UPDATE 済
- [ ] `README.md` に `var/secrets/` provisioning 手順
- [ ] Codex 14th review verdict ADOPT または ADOPT-WITH-CHANGES (HIGH 全件反映)
- [ ] PR description に親 PR #170 Refs + M10-0 gate 解除明示

## 関連ドキュメント

- `.steering/20260513-security-hardening-pre-m10/decisions.md` (SH-1 / SH-2 / SH-5 ADR)
- `.steering/20260513-security-hardening-pre-m10/design-final.md` (P4/P5 DEFERRED section)
- `.steering/20260513-security-hardening-pre-m10/codex-review.md` (Codex 13th 出力)
- `.steering/20260513-security-hardening-pre-m10/blockers.md` (M10-0 gate)
- `docs/architecture.md:328` (認証ポリシー)
- `docs/development-guidelines.md` (token rotate 運用ノート追加先)
