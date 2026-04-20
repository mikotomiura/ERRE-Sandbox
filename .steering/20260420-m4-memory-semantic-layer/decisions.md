# Decisions — m4-memory-semantic-layer

## D1. `/reimagine` 適用

### 判断
適用した (v1 → v2 の意図的再構築)。

### 履歴
1. `requirement.md` 記入後、`design.md` に v1 (素直な adapter 経路 = MemoryEntry
   経由 + `tags` JSON に `origin_reflection_id` を埋め込む) を記入
2. v1 を `design-v1.md` に退避
3. 意図的リセット宣言: 「v1 の adapter + tags JSON は踏襲しない」
4. `requirement.md` のみを立脚点に v2 (SemanticMemoryRecord 一次市民化 +
   schema 列追加 + store 直叩き API) を生成
5. `design-comparison.md` で 12 観点比較
6. auto-mode 委任に基づき **v2** を採用

### 根拠
memory `feedback_reimagine_trigger.md` の設計タスク必須適用規定。公開 API
(`upsert_semantic` / `recall_semantic`) の形状、`origin_reflection_id` の
保存方式 (列 vs tags JSON)、既存 `MemoryEntry` 経路との関係 (統合 vs 並行) に
複数案があり、確証バイアスを排除する価値が高い。

---

## D2. 採用案: **v2 (SemanticMemoryRecord 一次市民化)**

### 構成
- `semantic_memory` テーブルに `origin_reflection_id TEXT` 列を追加
  (nullable、idempotent な `create_schema()` 経路で既存 DB にも ALTER TABLE 適用)
- `MemoryStore.upsert_semantic(record)` / `recall_semantic(agent_id, q, k)`
  を直接 SQL で提供
- 既存 `MemoryStore.add(MemoryEntry)` / `Retriever.retrieve` の SEMANTIC 分岐は
  **無変更** (regression ゼロ)
- recall 戻り値: `list[tuple[SemanticMemoryRecord, float]]` (distance 含む)

### 理由
1. **Contract-First 精神**: foundation で凍結した `SemanticMemoryRecord` を
   store 層でも一次市民として扱う (v1 は 2 等級化して矛盾)
2. **cognition-reflection (#5) の PR が小さくなる**: 呼び出し側は
   `await store.upsert_semantic(record)` のみ書けばよい
3. **regression 安全性**: 既存経路無変更
4. **distance 取得**: 将来の reflection dedup / embedding 品質評価に
   distance が必要
5. **schema 変更コスト極小**: `ALTER TABLE ADD COLUMN` は nullable で
   既存データを壊さない

---

## D3. `origin_reflection_id` の保存方式: 専用列 (not tags JSON)

### 判断
`semantic_memory.origin_reflection_id TEXT` 列として独立保存。
`MemoryEntry.tags` JSON への埋め込み (v1) は採用しない。

### 理由
- 列なら `SELECT WHERE origin_reflection_id = ?` が直接書ける (audit / dedup)
- tags JSON はパーサが必要で schema contract が storage で暗黙に変形される
- `SemanticMemoryRecord` が wire 型として持つ field をそのまま列にするのが
  最もデータモデルが揃う (schema と実装の ISA 原則)

---

## D4. DB マイグレーション: idempotent ALTER TABLE

### 判断
`create_schema()` に以下を組み込む:
1. 新規 DB: `CREATE TABLE IF NOT EXISTS semantic_memory (... , origin_reflection_id TEXT)`
2. 既存 DB: `PRAGMA table_info(semantic_memory)` で列の有無を確認、
   無ければ `ALTER TABLE semantic_memory ADD COLUMN origin_reflection_id TEXT`

### 理由
- Alembic を導入しない方針 (個人プロジェクト、マイグレーション頻度小)
- `create_schema()` が既に idempotent (M2 の T10 で確立) なのでその延長
- ALTER TABLE ADD COLUMN は SQLite で O(1)、既存データ無破壊
- 起動時に毎回自動適用されるので、ユーザーが migration コマンドを覚える必要なし

### テスト
- `test_create_schema_adds_origin_reflection_id_column` (新規 DB)
- `test_create_schema_is_idempotent_with_origin_reflection_id` (2 回呼び)
- `test_create_schema_migrates_pre_m4_db` (手書きで pre-M4 テーブル作成 → migrate)

---

## D5. vec0 の upsert: DELETE + INSERT (not INSERT OR REPLACE)

### 判断
`vec_embeddings` (sqlite-vec の vec0 virtual table) への upsert は
`DELETE FROM ... WHERE memory_id = ?` → `INSERT INTO ... VALUES (?, ?)` の
2 文で実装。

### 理由
- vec0 は `INSERT OR REPLACE` を **サポートしない** (PRIMARY KEY UNIQUE
  制約が先に発火し OperationalError で失敗)
- DELETE + INSERT を outer `with conn:` 内に置くことで原子性を担保
- 空 embedding 時は DELETE のみ実行 (prior vector の掃除も兼ねる)

### 根拠データ
本タスクの実装中に最初 `INSERT OR REPLACE` で実装したところ、
`sqlite3.OperationalError: UNIQUE constraint failed on vec_embeddings
primary key` で失敗。sqlite-vec の issue tracker でも同様の報告あり。

### テスト
- `test_upsert_semantic_is_idempotent_on_id` が同一 id の 2 回 upsert を
  カバー
- `test_upsert_semantic_replaces_stale_vector_when_embedding_cleared` が
  embedding を消すパターンをカバー

---

## D6. 内部 bookkeeping 列のデフォルト: `importance=1.0`, `recall_count=0`, `tags='[]'`

### 判断
`upsert_semantic` が `semantic_memory` テーブルに書くとき、
`SemanticMemoryRecord` の wire field に無い内部列に以下のデフォルトを入れる:
- `importance = 1.0` (reflection-derived レコードは最高重要度を前提)
- `recall_count = 0` (新規)
- `tags = '[]'` (空 JSON 配列)
- `last_recalled_at = NULL`

### 理由
- wire 型 (`SemanticMemoryRecord`) に importance/recall_count/tags を
  含めないという foundation の設計判断 (M4 D3 で最小 primitive 化) を尊重
- storage 層で default を吐くのは「wire と storage の分離」の正統
- 毎回 upsert で default に戻ることは現時点で問題ない
  (retention policy が未実装、recall_count は mark_recalled で上書きされる)

### 将来の変更
もし retention policy が recall_count を保持したい場合は、
`INSERT ... ON CONFLICT(id) DO UPDATE SET content=excluded.content,
origin_reflection_id=excluded.origin_reflection_id` に書き換えて
bookkeeping 列を保存できる。本 PR では過剰実装を避ける。

---

## D7. 空 embedding の扱い: vec_embeddings には書かない

### 判断
`record.embedding == []` の場合、`semantic_memory` には書くが
`vec_embeddings` には一切書かない (かつ prior 行があれば DELETE)。
`recall_semantic` ではそのレコードは検索対象外。

### 理由
- M4 foundation の SemanticMemoryRecord で `embedding` を
  `Field(default_factory=list)` にし、空許容を明示的に契約したため
- "embedding 無し" を "recall されない" と解釈するのは自然
  (LLM 要約はあるが埋め込みはまだの中間状態)
- 後続で `embedding` を attach する場合は同 id で再 upsert すればよい

### テスト
- `test_upsert_semantic_with_empty_embedding_skips_vec_table`
- `test_upsert_semantic_replaces_stale_vector_when_embedding_cleared`

---

## D8. recall_semantic の戻り値: `list[tuple[SemanticMemoryRecord, float]]`

### 判断
`list[tuple[SemanticMemoryRecord, float]]` で返す (tuple = record + L2 distance)。
`RankedMemory` 風の dataclass は本 PR では導入しない。

### 理由
- 現時点で呼び出し側 (cognition-reflection) は未実装。必要になった時点で
  dataclass に昇格するのが YAGNI 的に適切
- 既存 `knn_ids` も `list[tuple[str, float]]` を返しており、API シグネチャの
  一貫性が保てる
- distance を含めることで、cognition 側が閾値判定や dedup に使える

---

## D9. legacy `add(MemoryEntry(kind=SEMANTIC))` パスの扱い

### 判断
既存の `add(MemoryEntry, embedding)` の SEMANTIC 分岐は無変更で残す。
`origin_reflection_id` は NULL のまま。`_semantic_row_to_record` は
NULL → None に map する。

### 理由
- M2 の `tests/test_memory/test_store.py` に 4-kind round-trip テストがあり
  破壊したくない
- 旧パスは reflection-derived 以外 (manual seed, test data) の SEMANTIC
  書き込みに使われる可能性がある
- 新旧パスが同じテーブルに書けるが、列 shape は互換なので混在 OK

### ドキュメント
`store.py` の該当分岐に「legacy MemoryEntry path: origin_reflection_id
is NULL by default」の注記コメントを追記済。

---

## D10. `Retriever` の semantic-only モード追加は本 PR では見送り

### 判断
`recall_semantic` は `MemoryStore` 直叩きでのみ提供。
`Retriever.recall_semantic(query_str, k)` 風のラッパーは本 PR では追加しない。

### 理由
- 呼び出し側 (cognition-reflection) が query 文字列ではなく
  事前計算した embedding を渡すケースが想定される (efficiency の問題)
- 必要性は #5 (m4-cognition-reflection) の設計時に判断する
- 今 Retriever を拡張すると、decay-weighted ranking が semantic に
  intended か unintended か曖昧になる (後で必要性を見極めて追加が安全)

---

## 参照

- `requirement.md`, `design.md`, `design-v1.md`, `design-comparison.md`
- memory `feedback_reimagine_trigger.md`
- `.steering/20260420-m4-contracts-freeze/` (foundation の SemanticMemoryRecord)
- `.steering/20260418-memory-store/design.md` (M2 T10 の 4-faculty 設計)
- `src/erre_sandbox/memory/store.py` / `retrieval.py`
