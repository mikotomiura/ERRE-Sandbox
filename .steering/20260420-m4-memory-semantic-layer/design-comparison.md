# 設計案比較 — m4-memory-semantic-layer

## v1 (素直な adapter 経路) の要旨

`SemanticMemoryRecord` を `MemoryEntry` に変換する adapter 関数を追加し、
既存 `MemoryStore.add` / `Retriever.retrieve` を経由して semantic 層を実現。
`origin_reflection_id` は `tags` JSON に
`"origin_reflection:<id>"` 形式で詰める。`Retriever.recall_semantic` は
`kinds=(SEMANTIC,)` でラップする。

## v2 (SemanticMemoryRecord 一次市民化) の要旨

`MemoryStore.upsert_semantic(record)` と
`MemoryStore.recall_semantic(agent_id, query_embedding, k)` を直接 SQL で
提供。`semantic_memory` テーブルに `origin_reflection_id TEXT` 列を追加
(idempotent な `create_schema()` で新規/既存 DB の両方に適用)。
embedding は record に inline、recall は事前計算された query_embedding を受ける。

## 主要な差異

| 観点 | v1 | v2 |
|---|---|---|
| `SemanticMemoryRecord` 地位 | 2 等級 (adapter 経由) | 1 等級 (直接受け渡し) |
| `origin_reflection_id` 保存 | tags JSON エンコード | DB 列として保存 |
| Schema 変更 | なし | `semantic_memory` に列追加 (idempotent) |
| Recall 入力 | query 文字列 (再埋め込み必須) | query_embedding 直接 |
| Recall 戻り値 | list[SemanticMemoryRecord] | list[(record, distance)] — 距離含む |
| Upsert 冪等性 | 明示されない (既存 add は INSERT、重複で UNIQUE violation) | `INSERT OR REPLACE` |
| reflection 連携 | 呼び出し側で MemoryEntry 変換が必要 | Pydantic 型のまま渡せる |
| 実装量 | 2 モジュール + Retriever 拡張 (~60 行) | store.py 拡張 ~80 行 + test 180 行 |
| 回帰リスク | Retriever 変更で EPISODIC+SEMANTIC 経路に影響可能 | 既存 add 分岐無変更、回帰低 |
| DB マイグレーション | 不要 | `ALTER TABLE ADD COLUMN` 1 回 (idempotent) |
| 再埋め込みコスト | 発生 (Retriever 経由で query 文字列を再度 embed) | ゼロ (呼び出し側が埋め込み制御) |

## 評価

### v1 の長所
- 実装が最小、store.py に触らない
- DB マイグレーションゼロ
- `Retriever.retrieve` の既存ランキング (decay / recall_boost) を
  semantic にも自動適用できる

### v1 の短所
- `origin_reflection_id` を tags JSON に埋めるのは汚い。parsing が必要で、
  schema contract (foundation で定義した意味) が storage で暗黙に変形される
- reflection が既に embedding を持つのに Retriever 経由で再埋め込みする無駄
- distance/similarity を上位層に渡せない (debug 困難)
- SemanticMemoryRecord が schemas.py 上では一次市民なのに storage では
  MemoryEntry にダウンキャストされる — contract と実装が乖離

### v2 の長所
- foundation で凍結した `SemanticMemoryRecord` を store レイヤーでも
  一次市民として扱える (contract と実装が整合)
- `origin_reflection_id` が DB 列になることで、将来の reflection 履歴追跡
  や監査クエリが素直に書ける
- distance を戻り値に含めるため、cognition-reflection 側で閾値判定や
  ランキング融合 (episodic と組み合わせ) の柔軟性がある
- `INSERT OR REPLACE` で idempotent upsert を明示的にサポート
- 既存 `MemoryStore.add` / `Retriever.retrieve` を無変更に保てる

### v2 の短所
- schema 変更を伴う (ALTER TABLE の idempotent 適用ロジックが必要)
- テストコード量が多い (9 件、180 行想定)
- Retriever の decay-weighted ランキングを使わないため、
  recall_semantic では「距離のみ」でソート (recency / importance は cognition
  側で必要なら後追い) — ただしこれは feature、意図的な責任分離

## 推奨案

**v2 (SemanticMemoryRecord 一次市民化) を採用**

### 理由

1. **Contract-First の精神に合致**: foundation で凍結した
   `SemanticMemoryRecord` を 2 等級市民に格下げする v1 は、M4 Contract-First
   の意図 (schema を凍結 → 実装が contract に従う) と逆行する。v2 は
   schema と実装が同じ抽象レベルで揃う

2. **cognition-reflection タスクが綺麗になる**: #5 の実装者は
   `await store.upsert_semantic(SemanticMemoryRecord(...))` だけを書けばよく、
   adapter や tags エンコードを意識しない。これは #5 の PR 範囲を小さくする

3. **regression 安全性が高い**: v1 は Retriever に semantic-only path を
   追加するため、既存の EPISODIC+SEMANTIC ミックスと干渉するリスクがある。
   v2 は既存経路を一切触らない

4. **distance 取得の下地**: 将来 embedding モデルを変えた時の recall 品質
   評価、あるいは reflection の重複排除 (同じ summary を何度も入れない)
   を実装するには distance が必要。v1 では Retriever の strength に
   埋もれてしまう

5. **schema 変更のコストは極小**: `ALTER TABLE ADD COLUMN` は nullable なので
   既存データを壊さない。`create_schema()` の idempotent 性は M2 で
   既に確立されたパターンを踏襲

### 採用判断

本タスクは memory `feedback_reimagine_trigger.md` に従い /reimagine を適用。
v1 vs v2 の 12 観点比較の結果、**v2 (一次市民化)** を採用する。
詳細は `decisions.md` に記録。
