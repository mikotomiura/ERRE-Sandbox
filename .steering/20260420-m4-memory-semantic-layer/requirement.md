# m4-memory-semantic-layer

## 背景

M4 planning (`.steering/20260420-m4-planning/`) で確定したサブタスク #3。
Critical Path (`contracts-freeze → memory-semantic-layer → cognition-reflection
→ orchestrator`) の真ん中の工程で、後続 `m4-cognition-reflection` (#5) が
reflection 要約の保存先として前提にする。

### 既存状態

- `src/erre_sandbox/memory/store.py` は M2 T10 時点で 4-faculty の
  table を既に持ち、`semantic_memory` テーブルも空の placeholder として
  作成されている (idempotent CREATE TABLE IF NOT EXISTS)。
- `MemoryStore.add(entry: MemoryEntry, embedding)` は SEMANTIC kind も
  受け付け、`semantic_memory` + `vec_embeddings` 双方に書ける。
- `Retriever.DEFAULT_KINDS = (EPISODIC, SEMANTIC)` なので retrieval path も
  既に semantic を含む。

### M4 foundation (PR #43 merged) で追加された新規型

`SemanticMemoryRecord` (schemas.py §6):
- `id: str`
- `agent_id: str`
- `embedding: list[float]` (空許容、M4 foundation の TODO コメント参照)
- `summary: str`
- `origin_reflection_id: str | None` ← **既存 MemoryEntry には無い field**
- `created_at: datetime`

また `ReflectionEvent` (schemas.py §6) が reflection → semantic の橋渡しに使われる:
- `agent_id, tick, summary_text, src_episodic_ids, created_at`

### ギャップ

- `origin_reflection_id` を保存する列が `semantic_memory` テーブルに無い
- `SemanticMemoryRecord` を直接受け渡す API (既存 API は `MemoryEntry`) が無い
- reflection 出力 (ReflectionEvent) から semantic_memory への蒸留 upsert 経路が無い
- semantic のみに絞った recall (KNN) API が無く、`Retriever.retrieve` の
  EPISODIC+SEMANTIC ミックスに依存している

## ゴール

`SemanticMemoryRecord` schema を一次シチズンとして扱える store API
(`upsert_semantic` / `recall_semantic`) を追加し、cognition-reflection タスクが
reflection → semantic_memory の蒸留を迷いなく配線できる状態にする。

既存の episodic memory 経路と generic `MemoryStore.add(MemoryEntry)` API は
破壊せず、`schema_version=0.2.0-m4` の範囲内で additive に拡張する。

## スコープ

### 含むもの

- `src/erre_sandbox/memory/store.py`:
  - `semantic_memory` テーブルに `origin_reflection_id TEXT` 列を追加
    (CREATE TABLE IF NOT EXISTS に default null 列として)
  - `MemoryStore.upsert_semantic(record: SemanticMemoryRecord) -> str`
    - 同 `id` で既存行があれば置換 (upsert セマンティクス)
    - embedding が空 `[]` なら vec_embeddings に書かない (M4 foundation で
      empty-embedding を許容した方針を踏襲)
    - embedding が非空かつ `len != embed_dim` なら ValueError
  - `MemoryStore.recall_semantic(agent_id, query_embedding, *, k)
     -> list[tuple[SemanticMemoryRecord, float]]`
    - 指定 agent_id の semantic_memory 行に限定した KNN
    - (record, L2 distance) のペアを距離昇順で返す
    - `query_embedding` の次元不一致は ValueError
  - `SemanticMemoryRecord` ↔ row 変換ヘルパー
    (既存の `_row_to_memory_entry` とは別関数)
- `tests/test_memory/test_semantic_layer.py` 新規:
  - round-trip (upsert → recall で summary / origin_reflection_id が保存)
  - 同 id で 2 回 upsert して置換 (idempotent + overwrite)
  - 複数 agent で書き、recall_semantic が特定 agent のみ返す
  - 空 embedding で upsert しても vec_embeddings には書かれない
  - 非空かつ次元違反で ValueError
  - K > 候補数のとき利用可能な件数だけ返す
- `tests/test_memory/conftest.py`:
  - `make_semantic_record` factory を追加 (既存 `make_entry` と併存)
  - 必要なら `unit_embedding` を再利用
- `docs/architecture.md §Memory`:
  - M4 semantic layer の新 API (`upsert_semantic` / `recall_semantic`) と
    `origin_reflection_id` 列の記述を追加

### 含まないもの (個別タスク / 後続)

- reflection 発火条件・LLM extract 本体 → `m4-cognition-reflection` (#5)
- N-agent gateway routing → `m4-gateway-multi-agent-stream` (#4)
- embedding 次元の固定 (現状 768-d / nomic-embed-text 前提)
  → ruri-v3-30m / multilingual-e5-small へ差し替えるなら別タスク
- `Retriever` の semantic-only モード追加 → 必要があれば本 PR 内だが、
  まずは `recall_semantic` を store 直叩きで提供し retriever 拡張は
  cognition-reflection タスクで必要性確認してから検討
- sqlite-vec の高度な index tuning (HNSW 相当) → 現状は線形 KNN で十分
  (agent あたり数百行想定)
- 既存 DB ファイル (var/kant.db) の in-place migration → 本 PR では
  `ALTER TABLE ADD COLUMN` のみ追加し、実行時に idempotent に適用できるよう
  `create_schema()` に保守列追加処理を入れる (詳細は design.md で確定)

## 受け入れ条件

- [ ] `semantic_memory` テーブルに `origin_reflection_id TEXT` 列が追加される
      (`create_schema()` 呼び出し後に `PRAGMA table_info(semantic_memory)` で確認可能)
- [ ] `MemoryStore.upsert_semantic(record)` が 10 件連続で呼べ、
      すべて `recall_semantic` で検索可能
- [ ] 同 id で 2 回 upsert すると 2 回目が勝つ (summary が置換される)
- [ ] `recall_semantic(agent_a, q, k=5)` は agent_b のレコードを返さない
- [ ] 空 embedding の record も upsert できる (vec_embeddings は書かれない)
- [ ] 空でない embedding の次元が store 設定と違うと ValueError
- [ ] 既存 `tests/test_memory/` の全テスト継続 PASS (no regression)
- [ ] `uv run pytest` 全件 PASS (baseline 394 → ≥ 400)
- [ ] `ruff check` / `ruff format --check` クリーン
- [ ] `code-reviewer` HIGH ゼロ
- [ ] `docs/architecture.md §Memory` に M4 追加記述が入る

## 関連ドキュメント

- `.steering/20260420-m4-planning/design.md` §m4-memory-semantic-layer
- `.steering/20260420-m4-contracts-freeze/` (PersonaSpec/SemanticMemoryRecord
  凍結の前提)
- `.steering/20260418-memory-store/design.md` (M2 T10 の既存設計)
- `docs/architecture.md` §Memory
- `src/erre_sandbox/memory/store.py` / `retrieval.py`
- `src/erre_sandbox/schemas.py` §6 (`ReflectionEvent`, `SemanticMemoryRecord`)
- `.claude/skills/test-standards/SKILL.md`

## 運用メモ

- 破壊と構築 (`/reimagine`) 適用: **Yes**
- 理由: 公開 API (`upsert_semantic` / `recall_semantic`) の形状、
  `origin_reflection_id` の保存方式 (列追加 vs tags JSON 利用)、
  既存 `MemoryEntry` 経路との関係 (統合 vs 並行) に複数案があり、
  初回案への確証バイアスで選んでしまうと後続タスクの調整コストが上がる。
  memory `feedback_reimagine_trigger.md` の「設計タスクでは必ず適用」に該当。
