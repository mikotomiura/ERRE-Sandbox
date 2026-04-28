# 設計

> **Status: COMPLETED — PR #111 merged 2026-04-28 (main = 0ca6234).**
> 本 design は post-merge 補完 (codex addendum D1 で TEMPLATE 残置を指摘されたため)。
> 詳細な hybrid 採用根拠は `decisions.md` D1-D6、phase-by-phase 実装ログは
> `tasklist.md` を参照。

## 実装アプローチ

外部 reviewer (Codex) の 6 finding (F1 P1 timeout tick / F2-F3 verification 緑化 /
F5 ui→integration architecture / F6 byte limit / F4 deferred / Codex Additional
棄却) を `/reimagine` v1+v2+第3案 → hybrid 採用パターンで一括対応。

実装順序は TDD ベース (`/fix-bug` skill 準拠):

1. F1 regression test 3 件 (RED) → dialog.py + world/tick.py + schemas.py 実装 (GREEN)
2. F6 regression test (RED) → gateway.py byte check (GREEN)
3. F5 architecture invariant test (RED) → contracts/ 新設 + shim + ui import 切替 + SKILL 更新 (GREEN)
4. lint/format/mypy 緑化 (pyproject extend-exclude → ruff --fix → 手動 6 件 → format → mypy)
5. README narrow + F4 local 再現確認 → deferred 確定
6. code-reviewer (HIGH 1 + MEDIUM 2 + LOW 1 全対応)
7. decisions.md 起草 → conventional commits 5 分割 → push → PR #111

## 変更対象

### 修正するファイル
- `src/erre_sandbox/integration/dialog.py` — F1: `close_dialog` keyword-only `tick: int | None = None` 追加 + `_close_dialog_at` helper 抽出
- `src/erre_sandbox/world/tick.py:1247` — F1: exhausted close で `tick=world_tick` 渡す
- `src/erre_sandbox/schemas.py:1239` — F1: Protocol に optional 拡張 + docstring 注記
- `src/erre_sandbox/integration/gateway.py` — F6: byte length check 追加
- `src/erre_sandbox/integration/metrics.py` — F5: shim 化 (中身を contracts/thresholds.py に移動)
- `src/erre_sandbox/ui/dashboard/state.py:27` — F5: `from erre_sandbox.contracts import ...` に切替
- `pyproject.toml:80` — F3: extend-exclude 拡張 (`.steering`, `erre-sandbox-blender`)
- `README.md` (EN + JA 2 箇所) — F2: verification command を `ruff check src tests` に narrow
- `.claude/skills/architecture-rules/SKILL.md` — F5: テーブルに contracts/ 行追加、ui/ 依存先拡張
- `src/erre_sandbox/cognition/cycle.py:793,798` — mypy: isinstance narrowing
- `src/erre_sandbox/evidence/metrics.py` — mypy: dict generic 明示 + isinstance narrowing
- `src/erre_sandbox/memory/store.py:973,1084` — ruff: S608 noqa
- 17 ファイル (lint/format auto-fix)

### 新規作成するファイル
- `src/erre_sandbox/contracts/__init__.py` — F5: 新レイヤー (re-export)
- `src/erre_sandbox/contracts/thresholds.py` — F5: Thresholds + M2_THRESHOLDS 定義
- `tests/test_architecture/__init__.py` — 新規ディレクトリ
- `tests/test_architecture/test_layer_dependencies.py` — F5 architecture invariant 2 件
- 新規 regression test (test_dialog.py に F1×3、test_gateway.py に F6×2)

### 削除するファイル
なし (shim 経由で既存 import を保護)

## 影響範囲

- **Protocol 拡張 (F1)**: schemas.py:1239 の `M4 frozen` docstring と整合させるため
  "non-breaking optional extension" 注記。既存 caller (test_dialog.py の 5+ 箇所) は
  `tick=None` default で挙動変わらず
- **architecture refactor (F5)**: `integration/__init__.py` 経由 import (test_contract_snapshot.py /
  test_integration/conftest.py) は shim で互換維持、破壊なし
- **lint/format (17 files)**: 振る舞い不変、commit を分離 (`chore(lint)`) して他修正と混同しない
- **README narrow**: documented verification path のみ変更、CI 整備時 (別 task) に再評価

## 既存パターンとの整合性

- F1: `record_turn(turn)` が `turn.tick` を引数で受ける pattern と整合 (close も
  「イベント時刻を引数で受ける」形に統一)
- F1 helper: `_emit(envelope)` が internal helper として隣接配置されている既存スタイル踏襲
- F5 contracts/: `_OpenDialog` dataclass が `dialog.py` 内 (実装専用は配置先でローカル) と
  対比的に、Thresholds は複数レイヤー参照される契約値なので独立パッケージ昇格が妥当
- F5 shim: `integration/__init__.py` の sub-module 経由 re-export スタイルそのまま
- F6 byte check: `cognition.parse.MAX_RAW_PLAN_BYTES` が同じ 64K 上限で encode() check
  している既存 pattern (gateway.py:76 で言及) と整合
- TDD: `test-standards` SKILL 推奨 + `/fix-bug` の Step E 前 "回帰テストを先に追加"

## テスト戦略

- **単体テスト**:
  - F1: `test_close_dialog_uses_explicit_tick_when_provided` / `test_tick_timeout_close_emits_current_tick_not_last_activity` / `test_close_dialog_falls_back_to_last_activity_when_tick_omitted` (3 件)
  - F6: `test_oversize_multibyte_frame_rejected` (codex 指摘) + `test_frame_exactly_at_byte_limit_is_accepted` (code-reviewer M2 で追加)
  - F5: `test_ui_does_not_import_integration` + `test_contracts_layer_depends_only_on_schemas_and_pydantic` (architecture invariant)
- **統合テスト**: 既存 test_contract_snapshot.py + test_integration/conftest.py が shim 経由で
  pass することで integration 互換確認
- **E2E テスト**: 不要 (各 fix は単体テストで十分カバー)
- **検証 path**: `ruff check src tests` + `ruff format --check src tests` + `mypy src` + `pytest`
  で documented path 全 exit 0

## ロールバック計画

PR #111 全体 revert で原状回復:
```
git revert -m 1 0ca6234
```

各 commit を個別 revert することも可能 (5 commit を split したため):
- `fix(integration): timeout/exhausted close emits current tick` (F1)
- `fix(integration): enforce frame byte limit on multibyte payloads` (F6)
- `refactor(architecture): introduce contracts/ layer` (F5)
- `chore(lint): green the documented verification path` (F2/F3)
- `docs(steering): codex review followup task records` (steering)

ただし F5 を revert する場合は ui/dashboard/state.py の import path も戻す必要あり
(shim で互換性維持しているため、`integration/metrics.py` 経由でも動くが、
architecture invariant test が fail し続ける)。
