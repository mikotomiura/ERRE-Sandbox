# タスクリスト — m4-personas-nietzsche-rikyu-yaml

## 準備
- [x] `.steering/20260420-m4-planning/design.md` §本タスク行を確認
- [x] `.steering/20260420-m4-contracts-freeze/` (schema 凍結の前提) を確認
- [x] `.claude/skills/persona-erre/SKILL.md` 読了
- [x] `personas/kant.yaml` を参照、構造・コメント方針を把握

## 設計
- [x] `requirement.md` 記入
- [x] v1 (哲学史トポス駆動) を `design.md` に記入
- [x] v1 を `design-v1.md` に退避
- [x] 意図的リセット宣言
- [x] v2 (身体制御-駆動 cognition) を `design.md` に再記入
- [x] `design-comparison.md` 作成 (11 観点)
- [x] 採用判断: **v2 ベース + v1 canon 語彙ハイブリッド**
- [x] `design.md` 末尾に設計判断履歴追記

## 実装
- [x] `personas/nietzsche.yaml` 新規作成 (6 habits / sampling 0.85-0.80-0.95)
- [x] `personas/rikyu.yaml` 新規作成 (6 habits / sampling 0.45-0.78-1.25)
- [x] `tests/test_personas/__init__.py` (空 package marker)
- [x] `tests/test_personas/test_load_all.py` 新規 (cross-persona invariants)
- [x] `tests/test_personas.py` → `tests/test_persona_kant.py` にリネーム
      (パッケージ名衝突回避、内容無変更)

## 検証
- [x] `uv run pytest`: 394 passed / 20 skipped (baseline 378 → +16)
- [x] `uv run ruff check` 対象ファイル全クリーン
- [x] `uv run ruff format --check` 3 files already formatted
- [x] PersonaSpec validation 手動確認 (python -c ... で両 YAML を load)

## レビュー
- [x] `code-reviewer` subagent: HIGH ゼロ、MEDIUM 3 件を解消
  - (1) nietzsche の `kaufmann1974` orphan ref を habit #3 に割り当て
  - (2) test_load_all.py docstring のリネーム反映
  - (3) fixture と parametrize の二重 load 設計意図をコメント化

## ドキュメント
- 本タスクでは `docs/architecture.md` を更新しない。
  3 体統合に伴う docs 加筆は `m4-multi-agent-orchestrator` で一括実施
  (m4-contracts-freeze D6 相当の scope 管理方針)

## 完了処理
- [x] `decisions.md` 作成 (D1-D7)
- [ ] commit: `feat(personas): add nietzsche + rikyu YAMLs (m4 axis A content)`
- [ ] push + PR 作成 (branch: `feature/m4-personas-nietzsche-rikyu-yaml`)
- [ ] PR review → main merge

## 次のタスク (本 PR merge 後)
- `m4-memory-semantic-layer` (#3, critical path)
- `m4-gateway-multi-agent-stream` (#4, 並列可)
