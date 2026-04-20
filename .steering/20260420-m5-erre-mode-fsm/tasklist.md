# タスクリスト — m5-erre-mode-fsm

## 準備

- [x] `.steering/20260420-m5-planning/design.md` §3 新軸 M 軸 を再読
- [x] `.steering/20260420-m5-contracts-freeze/design.md` で Protocol freeze を確認
- [x] `.claude/skills/persona-erre/SKILL.md` §ルール 5 を読み Zone→Mode 正準表を把握
- [x] 既存 `bootstrap.py::_ZONE_TO_DEFAULT_ERRE_MODE` の現在位置と値を把握
- [x] `feature/m5-erre-mode-fsm` branch を作成

## 設計 (/reimagine)

- [x] `design.md` に v1 初回案を記入 (priority ordering / backwards scan)
- [x] `design.md` を `design-v1.md` に退避
- [x] v2 案をゼロから生成 (latest-signal-wins / single pass / match dispatch / DI)
- [x] `design-comparison.md` で 2 案を比較
- [x] v2 採用確定 → design.md 最終化 + 採用判断履歴記録

## 実装

### Step A: パッケージ骨格

- [x] `src/erre_sandbox/erre/__init__.py` を FSM 用に刷新 (placeholder docstring 置換)
- [x] `src/erre_sandbox/erre/fsm.py` 新規作成
- [x] `_ZONE_TO_DEFAULT_ERRE_MODE` を `erre/fsm.py::ZONE_TO_DEFAULT_ERRE_MODE` へ移植

### Step B: TDD (test を先に書く)

- [x] `tests/test_erre/__init__.py` 新規作成
- [x] `tests/test_erre/test_fsm.py` 赤状態で 31 test 記述
- [x] `uv run pytest tests/test_erre/` で赤状態確認 (ImportError)

### Step C: 緑化

- [x] `DefaultERREModePolicy` + 3 pure handler + 2 canonical map 実装
- [x] `uv run pytest tests/test_erre/` で全緑 (31 PASS)

### Step D: bootstrap 統合

- [x] `src/erre_sandbox/bootstrap.py` の `_ZONE_TO_DEFAULT_ERRE_MODE` 削除
- [x] `from erre_sandbox.erre import ZONE_TO_DEFAULT_ERRE_MODE` に置換
- [x] 既存 bootstrap test 全 PASS 確認

## テスト

- [x] `uv run pytest -q` → 544 passed, 26 skipped, 0 failures
- [x] `uv run ruff check src tests` PASS
- [x] `uv run ruff format --check src tests` PASS
- [x] `uv run mypy src/erre_sandbox` → 0 errors

## レビュー

- [x] `code-reviewer`: HIGH なし / MEDIUM 2 対応 (constant extract + docstring note)
      / LOW 1 対応 (type: ignore comment) / LOW 2 は decisions.md で受容
- [x] `impact-analyzer`: HIGH (world → erre layer 依存) は判断 4 で次タスクへ委譲

## ドキュメント

- [x] `docs/architecture.md` L135: `_ZONE_TO_DEFAULT_ERRE_MODE` 参照を
      `erre_sandbox.erre.ZONE_TO_DEFAULT_ERRE_MODE` に更新
- [x] `docs/functional-design.md` L156: 未来形「置換する」を具体 task / class 名に更新
- [x] `decisions.md` に 5 件の判断を記録 (v2 採用 / docstring 上書き / match 初導入 /
      layer 依存先送り / reviewer MEDIUM/LOW 反映)

## 完了処理

- [x] design.md / design-v1.md / design-comparison.md / decisions.md / tasklist.md
      / requirement.md の最終チェック
- [ ] `git commit` (Conventional Commits:
      `feat(erre): concrete ERREModeTransitionPolicy with event-driven FSM`)
- [ ] `git push -u origin feature/m5-erre-mode-fsm`
- [ ] PR 作成 → review → merge

## 制約・リマインダ

- `main` 直 push 禁止
- `erre/` は `schemas` のみ import (architecture-rules)
- Pydantic BaseModel は不要 (plain class)
- GPL 依存を追加しない
- 既存 513 test に回帰なし
