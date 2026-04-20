# 設計 — m4-memory-semantic-layer (v2: SemanticMemoryRecord を一次市民化)

> **位置付け**: v2 は `/reimagine` で v1 を破棄した後、requirement.md のみを
> 立脚点に再構築した案。

## 実装アプローチ

requirement.md の受け入れ条件を満たす最短経路は、
`SemanticMemoryRecord` を **store 側の一次シチズン** として扱い、
`MemoryStore.upsert_semantic` / `MemoryStore.recall_semantic` を
**直接 SQL で** 提供することである。`MemoryEntry` 経由のアダプタに寄せると、
`origin_reflection_id` を `tags` JSON にエンコードする副作用や、
Retriever 経由で query 文字列から再埋め込みする無駄が発生する。

cognition-reflection (#5) が呼ぶ側から見た自然な形は:

```python
# reflection が自分で LLM 要約 + embedding を計算
record = SemanticMemoryRecord(
    id=..., agent_id=..., embedding=vec, summary=..., origin_reflection_id=rf.id,
)
await store.upsert_semantic(record)

# 後続の cognition tick で recall
hits = await store.recall_semantic(agent_id, q_vec, k=5)
```

embedding は record に既にあるため recall 側も外から注入した `query_embedding`
を受ける。query 文字列 → embedding の変換は呼び出し側の責務 (= embedding
コンポーネントが使える cognition / retriever) に残す。

## 変更対象

### 修正
- `src/erre_sandbox/memory/store.py`:
  - `create_schema()` に **`origin_reflection_id TEXT` 列を追加** する
    ロジックを組み込む:
    - 新規 DB: `CREATE TABLE IF NOT EXISTS semantic_memory (..., origin_reflection_id TEXT)`
    - 既存 DB: `PRAGMA table_info(semantic_memory)` で列の有無を確認し、
      無ければ `ALTER TABLE semantic_memory ADD COLUMN origin_reflection_id TEXT`
    - 両方とも idempotent (複数回 `create_schema()` を呼んでも安全)
  - 新メソッド `upsert_semantic(record: SemanticMemoryRecord) -> str`:
    - `INSERT OR REPLACE INTO semantic_memory (...)` で id 衝突時は置換
    - embedding が非空のとき:
      - 次元一致を検証、ValueError で早期失敗
      - `INSERT OR REPLACE INTO vec_embeddings (memory_id, embedding)` も実行
    - embedding が空のとき: vec_embeddings には書かない
    - importance / recall_count / tags は storage 保守用のデフォルト
      (importance=1.0、recall_count=0、tags='[]')。これらは
      `SemanticMemoryRecord` の wire 表現には現れず、
      内部 bookkeeping として隠蔽される
  - 新メソッド `recall_semantic(agent_id, query_embedding, *, k)
     -> list[tuple[SemanticMemoryRecord, float]]`:
    - query_embedding の次元検証 → ValueError
    - 当該 agent の semantic_memory 行を `list_semantic_ids_for_agent` で取得
    - `knn_ids(query_embedding, k=k, candidate_ids=...)` で距離計算
    - 上位 k 件の row を再読込して `SemanticMemoryRecord` に構築
    - `(record, distance)` ペアのリストを距離昇順で返す
  - 内部 helper `_semantic_row_to_record(row, embedding) -> SemanticMemoryRecord`
    を追加 (既存 `_row_to_memory_entry` とは独立)
  - 既存の `add(entry, embedding)` の SEMANTIC 分岐は **無変更**
    (regression 防止、M2 test の invariants を維持)
- `src/erre_sandbox/memory/__init__.py`:
  - `MemoryStore` は既に export 済。追加エクスポートなし
  (`SemanticMemoryRecord` は schemas から import する側の責務)

### 新規
- `tests/test_memory/test_semantic_layer.py`:
  - `test_upsert_semantic_round_trip`: 1 件書いて recall で summary /
    origin_reflection_id が一致
  - `test_upsert_semantic_is_idempotent_on_id`: 同 id を 2 回書くと
    2 回目が勝ち、KNN のヒットも重複なし
  - `test_recall_semantic_isolates_per_agent`: 3 agent のレコードを混在させ、
    recall_semantic(agent_a) が agent_b/c を返さない
  - `test_upsert_semantic_with_empty_embedding_skips_vec_table`: 空 embedding
    で upsert、`get_embedding` が None を返す
  - `test_upsert_semantic_rejects_wrong_dim`: 非空で dim 違反 → ValueError
  - `test_recall_semantic_rejects_wrong_query_dim`: query 次元違反 → ValueError
  - `test_recall_semantic_respects_k`: K が候補数より大きい場合、利用可能な
    件数だけ返す
  - `test_recall_semantic_preserves_origin_reflection_id`: None と非 None
    両方が正しく round-trip
  - `test_create_schema_is_idempotent_with_origin_reflection_id`:
    `create_schema()` を 2 回呼んでも migration が重複適用されないこと
- `tests/test_memory/conftest.py`:
  - `make_semantic_record(**overrides) -> SemanticMemoryRecord` factory を追加

### ドキュメント
- `docs/architecture.md §Memory`:
  - M4 foundation で追加された `SemanticMemoryRecord` が semantic_memory
    テーブルに `origin_reflection_id` 列として保存される旨を追記
  - `upsert_semantic` / `recall_semantic` の API サマリ
  - reflection → semantic の書き込み経路の図示 (1-2 行)

## 影響範囲

- 既存 `MemoryStore.add(MemoryEntry, embedding)` の SEMANTIC 分岐は未変更。
  `tests/test_memory/test_store.py` の全テストは継続 PASS
- `Retriever.retrieve` の EPISODIC+SEMANTIC ミックスも既存動作のまま
- DB マイグレーション: `create_schema()` の idempotent ALTER TABLE 方式により、
  既存の var/kant.db も再起動時に自動で `origin_reflection_id` 列が追加される
- schema_version bump なし (wire schema は foundation で既に `0.2.0-m4`)
- ファイル変更: store.py (+約 80 行)、conftest.py (+約 15 行)、
  test_semantic_layer.py (+約 180 行、新規)

## 既存パターンとの整合性

- `asyncio.to_thread` パターンを踏襲 (同期 sqlite 呼び出しのラップ)
- embedding 次元検証は既存 `add()` と同じ ValueError メッセージ形式
  (`f"Embedding dim {len(x)} != store dim {self._embed_dim}"`)
- `INSERT OR REPLACE` は SQLite 標準。アトミック (`with conn:` 内で
  memory_id 衝突時に vec_embeddings も一緒に置換)
- helper 関数 `_dt_to_text` / `_text_to_dt` 既存を再利用

## テスト戦略

### 単体テスト (`tests/test_memory/test_semantic_layer.py`)
- 上記 9 件で API を網羅
- `unit_embedding` fixture (既存、768-d) を再利用
- `unit_embedding_alt` fixture を新規 (別方向のベクトルで KNN 結果を差別化)

### 既存テストの回帰
- `test_store.py` の 4-kind round-trip は無変更
- `test_retrieval.py` の Retriever (EPISODIC+SEMANTIC) は無変更
- `test_embedding.py` / `test_embedding_prefix.py` は無関係

### 本 PR の不変条件テストが生き続けるかの assertion
- `test_create_schema_is_idempotent_with_origin_reflection_id`
  で新 ALTER TABLE パスが 2 重適用されない

## ロールバック計画

- PR revert 一発で戻る
- DB マイグレーション: `ALTER TABLE ADD COLUMN` は SQLite で逆向きが無いが、
  `origin_reflection_id` は nullable で existing データに影響しないので、
  revert 後に列が残っても既存の動作に支障なし (保守列として dormant)
- 既存 M2 DB (var/kant.db) への影響: 新列が追加されるのみ、データ損失なし

## schema_version bump の要否

不要。本 PR は wire schema (`schemas.py`) を変更しない。
`SemanticMemoryRecord` / `ReflectionEvent` は foundation (PR #43) で
`0.2.0-m4` として凍結済みで、本 PR は storage 層の配線のみ。

## Out of scope (再掲)

- reflection 発火条件・LLM extract 本体 → `m4-cognition-reflection` (#5)
- embedding 次元の変更 (768-d → 384-d 等) → 別タスク
- sqlite-vec の HNSW / IVF index tuning → ペルソナ数 <10 で不要
- `Retriever` 側の semantic-only ラッパー → 必要性は cognition-reflection の
  実装で判断、本 PR では store 直叩きで十分

## 設計判断の履歴

- v1 (`design-v1.md`) は adapter 関数 + tags JSON エンコード経路を採用
  (SemanticMemoryRecord を 2 等級市民化)
- `/reimagine` で v2 (本ファイル) を再構築: store の直接 API + schema 列追加
- `design-comparison.md` で 2 案を詳細比較
- **採用**: v2 (一次市民化)
- 根拠:
  1. `origin_reflection_id` を列に持つ方が tags JSON 経由より読み書きが直接
  2. reflection 側が既に embedding を持っているため、query 文字列 → 再埋め込み
     を強制する v1 は無駄
  3. SemanticMemoryRecord が M4 foundation で一次市民として凍結されたのに
     store 内部で MemoryEntry に潰すのは contract の意図と矛盾
  4. 既存 `MemoryStore.add` / Retriever は無変更で保てる (regression 安全)
  5. 後続 `m4-cognition-reflection` (#5) は store 直叩きで writer/reader 両方
     が自然に書ける
- 詳細根拠は `decisions.md`
