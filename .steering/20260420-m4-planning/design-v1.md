# M4 設計 — v1 (初回案: MASTER-PLAN §5 直訳の素直な時系列積み上げ)

## 実装アプローチ

MASTER-PLAN §5 の M4 代表タスク 4 本を素直にこの順番で直列実行する:

1. **Step 1 — `personas-nietzsche-rikyu-yaml`**: Kant 以外の 2 体のペルソナ YAML を書く。
   content curation のみでコード変更なし。最もリスクが低いので最初。
2. **Step 2 — `memory-semantic-layer`**: 現状の `episodic_memory` に加えて
   `semantic_memory` テーブルを追加し、長期保存用の要約 layer を構築。
   `MemoryStore` に `upsert_semantic()` / `recall_semantic()` を追加。
3. **Step 3 — `cognition-reflection`**: 認知サイクルに reflection step を追加し、
   N tick ごとに episodic memory をまとめて semantic memory に格納する。
   `cognition/cycle.py` に `reflect()` メソッドを追加。
4. **Step 4 — `gateway-multi-agent-stream`**: Gateway と bootstrap を 1 agent 前提から
   N agent 前提に変える。`bootstrap.py` を拡張して `register_agent` を 3 回呼ぶ。
   gateway の WS broadcast を per-agent rooms に分岐。

各ステップ完了後に pytest 全グリーンを確認し、次のステップへ進む。
最後に live 検証で「3 体が peripatos で歩きながら reflection が発火して semantic memory
が積まれる」ことを手動視認し、M4 acceptance とする。

## 変更対象

### 修正するファイル (各ステップで逐次)
- `src/erre_sandbox/memory/store.py` — Step 2: `semantic_memory` CRUD 追加
- `src/erre_sandbox/cognition/cycle.py` — Step 3: `reflect()` 追加
- `src/erre_sandbox/bootstrap.py` — Step 4: 3 agent 対応
- `src/erre_sandbox/integration/gateway.py` — Step 4: per-agent broadcast
- `src/erre_sandbox/__main__.py` — Step 4: CLI で 3 agent 起動
- `godot_project/scripts/AgentController.gd` — Step 4: 3 agent 描画
- `docs/architecture.md` / `docs/functional-design.md` — 各ステップで追記

### 新規作成するファイル
- `personas/nietzsche.yaml` — Step 1
- `personas/rikyu.yaml` — Step 1
- `tests/test_memory/test_semantic_layer.py` — Step 2
- `tests/test_cognition/test_reflection.py` — Step 3
- `tests/test_integration/test_three_agent_walker.py` — Step 4

### 削除するファイル
- なし

## 影響範囲

- schemas: 既存 `ControlEnvelope` は agent_id field を既に持つので extension 不要
  (と想定、確認が必要)
- world tick: 既存 `WorldRuntime` は既に `register_agent` API を持つので
  multi-agent 対応は Step 4 で bootstrap から複数回呼ぶだけ
- memory schema: `semantic_memory` 追加で migration 必要
- Godot: 3 avatar が peripatos に同居するためシーン側の spawn 処理を増やす

## 既存パターンとの整合性

- M2 で確立した `bootstrap.py` composition root をそのまま拡張
- `MemoryStore` の idempotent `create_schema()` パターンに semantic_memory を追加
- `cognition/cycle.py` の step-by-step プロセス (perceive → plan → act)
  に reflect を挿入
- Contract-First は **Step 4 の手前** で改めて確認 (schemas.py の拡張要否判断)

## テスト戦略

- 単体テスト: 各ステップの新規モジュールにユニットテスト
- 統合テスト: Step 4 完了時に `test_three_agent_walker.py` で 3 agent + reflection + semantic memory
- E2E テスト: 各ステップの最後に `uv run pytest` 全グリーン、最後に live 視認

## ロールバック計画

各ステップが独立 PR なので、問題があれば該当 PR だけ revert。
Semantic memory migration は idempotent なので DB ファイル削除で戻せる。

---

**本 v1 案の位置付け**: MASTER-PLAN §5 を時系列に素直に積み上げたベースライン。
/reimagine で v2 を再生成し、比較を行う。
