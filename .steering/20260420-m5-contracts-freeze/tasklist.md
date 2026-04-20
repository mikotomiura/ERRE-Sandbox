# タスクリスト — m5-contracts-freeze

## 準備

- [x] `.steering/20260420-m5-planning/design.md` §Schema 0.3.0-m5 追加内容 を再読
- [x] `.steering/20260420-m5-llm-spike/decisions.md` 判断 4-7 を再読 (contract 側に
      追加要求が無いことを最終確認)
- [x] 既存 `schemas.py` / `fixtures/control_envelope/*` / `tests/schema_golden/*` /
      `tests/conftest.py` を把握
- [x] `feature/m5-contracts-freeze` branch を作成

## 実装 (v2 TDD 順序)

### Step A: 再生成スクリプト作成 (fixture + golden 更新の基盤)

- [x] `scripts/` ディレクトリ新設
- [x] `scripts/regen_schema_artifacts.py` を作成 (idempotent、adapter validation 込み)

### Step B: TDD 赤フェーズ (test 先行)

- [x] `tests/test_schemas_m5.py` を新規作成し、16 test を書く (parametrize 展開含む)
- [x] `uv run pytest tests/test_schemas_m5.py` で赤 (ImportError for Protocols) を確認

### Step C: TDD 緑フェーズ (schemas.py 編集)

- [x] `SCHEMA_VERSION` を `"0.3.0-m5"` に更新 + 2 段構成 docstring
- [x] `Cognitive` に `dialog_turn_budget: int = Field(default=6, ge=0)` を追加
- [x] `DialogTurnMsg` に `turn_index: int = Field(..., ge=0)` を追加
- [x] `DialogCloseMsg.reason` literal に `"exhausted"` を追加
- [x] `ERREModeTransitionPolicy` Protocol 追加
- [x] `DialogTurnGenerator` Protocol 追加
- [x] `__all__` に 2 Protocol を追加
- [x] `InMemoryDialogScheduler.close_dialog` の Literal にも `"exhausted"` を追加
- [x] `uv run pytest tests/test_schemas_m5.py` 全緑 (16 PASS)

### Step D: fixture / golden 再生成 (スクリプト実行)

- [x] `uv run python scripts/regen_schema_artifacts.py` を実行
- [x] 冪等性確認 (2 回目実行で no changes)

### Step E: conftest.py 更新

- [x] `tests/conftest.py::_build_dialog_turn` に `turn_index=0` default pop 追加

### Step F: 既存 test への最小影響吸収

- [x] Grep で `DialogTurnMsg(` 直接構築を洗い出し、5 箇所 (test_dialog.py x2 /
      test_multi_agent_stream.py x3) に `turn_index=0` を明示付与
- [x] `test_schemas.py::test_schema_version_is_m4` を
      `test_schema_version_is_current_milestone` にリネーム + 0.3.0-m5 に更新
- [x] `test_schemas.py::_dialog_envelope_cases` の dialog_turn ケースに turn_index 追加
- [x] `personas/{kant,nietzsche,rikyu}.yaml` の schema_version を 0.3.0-m5 に
- [x] `tests/fixtures/m4/agent_spec_3agents.json` の schema_version を 0.3.0-m5 に

## テスト

- [x] `uv run pytest -q` で 513 passed, 26 skipped, 0 failures (元 525 test + 本 task で増加)
- [x] `uv run ruff check src tests scripts` PASS (tick.py:477 pre-existing PLW2901 は
      noqa で明示的許容、判断 4 参照)
- [x] `uv run ruff format --check src tests scripts` PASS (95 files)
- [x] `uv run mypy src/erre_sandbox` PASS (0 errors in 38 files)

## レビュー

- [x] `code-reviewer` sub-agent で schema diff をレビュー
  - HIGH: なし
  - MEDIUM 1: turn_index required の M4 breaking を docstring で明示 → 対応済 (判断 2)
  - MEDIUM 2: regen script に adapter validation 追加 → 対応済 (判断 3)
  - LOW: tick.py refactor / parametrize type: ignore → 受容 (判断 4)

## ドキュメント

- [x] `docs/functional-design.md` の M5 記述を「ドラフト」から「contract 凍結済み」に更新
- [x] 用語追加は不要 (既存用語のみ使用)

## 完了処理

- [x] design.md / design-v1.md / design-comparison.md / decisions.md / tasklist.md
      / requirement.md の最終化
- [x] `decisions.md` 作成 (reimagine 採用 + 2 件の MEDIUM 対応 + 1 件の LOW 対応)
- [ ] `git commit` (Conventional Commits: `feat(schemas): bump to 0.3.0-m5 for M5 FSM + dialog_turn`)
- [ ] `git push -u origin feature/m5-contracts-freeze`
- [ ] PR 作成 → review → merge

## 制約・リマインダ

- `main` 直 push 禁止 (必ず `feature/m5-contracts-freeze` 経由)
- 既存 525 test に回帰なし
- 新 field / Protocol は additive のみ、既存 field の削除・リネームなし
- Protocol は interface-only (具象実装は後続 sub-task)
