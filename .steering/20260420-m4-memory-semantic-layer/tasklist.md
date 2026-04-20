# タスクリスト — m4-memory-semantic-layer

## 準備
- [x] `.steering/20260420-m4-planning/design.md` §m4-memory-semantic-layer
- [x] `.steering/20260420-m4-contracts-freeze/` (SemanticMemoryRecord 凍結)
- [x] 既存 `memory/store.py` + `retrieval.py` + `test_memory/*` 読了

## 設計
- [x] `requirement.md` 記入
- [x] v1 (素直な adapter + tags JSON) を `design.md` に記入
- [x] v1 を `design-v1.md` に退避
- [x] 意図的リセット宣言
- [x] v2 (SemanticMemoryRecord 一次市民化) を `design.md` に再記入
- [x] `design-comparison.md` 作成 (12 観点)
- [x] 採用判断: **v2**

## 実装
- [x] `schemas.SemanticMemoryRecord` を store.py に import
- [x] `semantic_memory` CREATE TABLE に `origin_reflection_id TEXT` 追加
- [x] `_migrate_semantic_schema(conn)` 追加 (PRAGMA table_info → ALTER TABLE)
- [x] `MemoryStore.upsert_semantic(record)` 実装 (DELETE+INSERT on vec0)
- [x] `MemoryStore.recall_semantic(agent_id, q, *, k)` 実装
- [x] `_semantic_row_to_record(row, embedding)` ヘルパ追加
- [x] 既存 `add(MemoryEntry)` SEMANTIC 分岐に legacy path 注記コメント

## テスト
- [x] `tests/test_memory/conftest.py` に `make_semantic_record` factory
- [x] `tests/test_memory/test_semantic_layer.py` 13 件:
  - migration (idempotent / pre-M4 migrate / fresh DB)
  - upsert_semantic round-trip / idempotent / empty embedding /
    vector cleared / wrong-dim reject
  - recall_semantic agent-isolation / K 制限 / no-rows / NULL origin /
    wrong-dim reject

## 検証
- [x] `uv run pytest`: **407 passed / 20 skipped** (baseline 394 → +13)
- [x] `uv run ruff check` + `uv run ruff format --check` 全クリーン

## レビュー
- [x] `code-reviewer` subagent: HIGH ゼロ
- [x] MEDIUM 3 件 / LOW 3 件の対応:
  - (MEDIUM 2) legacy SEMANTIC add path の注記コメント追加
  - (LOW 1) `tmp_path` を `Path` 型にして `type: ignore` 削除
  - (LOW 2) recall_semantic のコメント修正 (O(k) の文言精度向上)
  - (MEDIUM 1) IN 句スケール問題 / (MEDIUM 3) bookkeeping reset /
    (LOW 3) RankedMemory dataclass 化は decisions.md D6/D8 で将来対応の根拠記録

## ドキュメント
- [x] `docs/architecture.md §Memory Stream` に M4 semantic layer の
      API + 列追加 + reflection 連携概要を追記

## 完了処理
- [x] `decisions.md` 作成 (D1-D10)
- [ ] commit: `feat(memory): m4 semantic layer — upsert_semantic / recall_semantic + origin_reflection_id`
- [ ] push + PR 作成 (branch: `feature/m4-memory-semantic-layer`)
- [ ] PR review → main merge

## 次のタスク (本 PR merge 後)
- `m4-gateway-multi-agent-stream` (#4, Axis A+C infra、並列可)
- `m4-cognition-reflection` (#5, #3 merge 後に着手、critical path)
