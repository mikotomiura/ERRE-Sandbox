# 設計 — m4-memory-semantic-layer (v1: 素直な既存 MemoryEntry 経路拡張)

> v1 は `/reimagine` のため後で `design-v1.md` に退避される。

## 実装アプローチ

既存 `MemoryStore.add(MemoryEntry, embedding)` と
`MemoryStore.get_by_id/list_by_agent/knn_ids` の経路が SEMANTIC kind を
既にサポートしているので、**`SemanticMemoryRecord` 自体を新しい API で
扱うのではなく**、既存 `MemoryEntry` への adapter 関数 2 本を memory モジュール
側に追加する方針。

- `to_memory_entry(record: SemanticMemoryRecord) -> MemoryEntry`:
  summary → content、origin_reflection_id → tags の JSON に詰める
  (`tags=[f"origin_reflection:{origin_reflection_id}"]`)
- `from_memory_entry(entry, embedding) -> SemanticMemoryRecord`: 逆変換

recall は `Retriever.retrieve` に `kinds=(SEMANTIC,)` を渡す薄いラッパー
`recall_semantic(agent_id, query_text, k)` を retrieval.py 側に追加。

## 変更対象

### 修正
- `src/erre_sandbox/memory/retrieval.py`:
  - `Retriever.recall_semantic(agent_id, query, *, k) -> list[SemanticMemoryRecord]`
    を追加、内部で `retrieve(..., kinds=(SEMANTIC,))` + `from_memory_entry`
- `src/erre_sandbox/memory/__init__.py`:
  - `to_memory_entry` / `from_memory_entry` を再エクスポート

### 新規
- `src/erre_sandbox/memory/semantic_adapter.py`:
  - `to_memory_entry` / `from_memory_entry`
- `tests/test_memory/test_semantic_layer.py`:
  - adapter 関数の round-trip
  - `Retriever.recall_semantic` の 3-agent 分離

## v1 の予想される問題点

- `origin_reflection_id` を `tags` に詰めるのは汚い (parse が必要)
- recall path が `Retriever` (query 文字列 → embedding) 前提なので、
  reflection 側が既に embedding を持っている場合に再埋め込みが無駄
- `SemanticMemoryRecord` が 2 等級市民のまま。M4 contract で定義した意味が薄れる
- `empty embedding` の semantic 書き込みは既存 `add(entry, embedding=None)` で
  可能だが、adapter の API 上は「なぜ空なのか」が unclear

## テスト戦略

- `test_semantic_adapter_round_trip`
- `test_retriever_recall_semantic_filters_to_agent`
- 既存 episodic 経路は変更なしのため regression なし

## ロールバック計画

- 2 モジュール追加 + retrieval.py 拡張のみ。revert 一発
- schema 変更なし、DB マイグレーション不要

## 設計判断の履歴

- 初回案 (v1)。`/reimagine` で v2 を再生成後、比較する。
