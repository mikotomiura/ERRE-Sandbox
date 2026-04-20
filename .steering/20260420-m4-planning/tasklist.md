# タスクリスト — m4-planning

> **性質**: planning only (コード変更なし、docs + .steering のみ)
> M4 個別実装は本タスク merge 後に別タスクで着手する。

## 準備
- [x] `MASTER-PLAN.md §5` の M4 代表タスク 4 本を確認
- [x] `.steering/20260419-m2-integration-e2e-execution/known-gaps.md` の GAP-2〜5 確認
- [x] `.steering/20260419-m2-functional-closure/decisions.md` の M2 継承判断を確認
- [x] memory `project_implementation_plan.md` の Contract-First 成功記録を確認
- [x] memory `feedback_reimagine_trigger.md` / `feedback_reimagine_scope.md` 確認

## 設計
- [x] `requirement.md` 記入
- [x] v1 (素直な時系列積み上げ案) を `design.md` に記入
- [x] v1 を `design-v1.md` に退避
- [x] 意図的リセット宣言
- [x] v2 (Contract-First + 3 軸分解) を `design.md` に記入
- [x] `design-comparison.md` で両案比較
- [x] **採用判断**: v2 + hybrid (foundation 小型化) — ユーザー選択 (3)
- [x] `design.md` 末尾に設計判断履歴を追記

## M4 サブタスク定義 (本タスクで確定する一覧)

以下 6 本を M4 のサブタスクとして確定する。各サブタスクは別 `.steering/YYYYMMDD-*/`
ディレクトリで `/start-task` → `/add-feature` のワークフローで実施。

### 1. m4-contracts-freeze (Foundation、必須最初、直列) — 0.5-1 日
- **ゴール**: M4 の全 primitive を schemas.py + fixture + schema_version bump で凍結
- **対象**: `AgentSpec`, `BootConfig.agents: list`, `ReflectionEvent`,
  `SemanticMemoryRecord`, `DialogInitiateMsg`, `DialogTurnMsg`, `DialogCloseMsg`,
  `DialogScheduler` (Protocol interface のみ)
- **依存**: なし
- **検収**:
  - 新 fixture で WS 互換テスト PASS
  - 既存 346 テスト継続 PASS
  - `schema_version=0.2.0-m4` に bump
  - GDScript parser が新 variant を hard-error なく dispatch
- **ファイル**: `src/erre_sandbox/schemas.py`, `tests/fixtures/m4/`, `tests/test_schemas.py`,
  `godot_project/scripts/WebSocketClient.gd` (parser 追記)

### 2. m4-personas-nietzsche-rikyu-yaml (Axis A content、並列可) — 0.5 日
- **ゴール**: Nietzsche と Rikyu のペルソナ YAML を content curation として作成
- **依存**: `m4-contracts-freeze` (PersonaSpec schema 凍結を確認のみ)
- **検収**:
  - `PersonaSpec` validation PASS
  - persona loader で読み込める unit test 追加
  - ERRE mode / sampling override が kant.yaml と差分ある thought-life を反映
  - `/reimagine` 適用 (content curation も対象 / memory `feedback_reimagine_scope.md`)
- **ファイル**: `personas/nietzsche.yaml`, `personas/rikyu.yaml`,
  `tests/test_personas/test_load_all.py`

### 3. m4-memory-semantic-layer (Axis B infra、並列可) — 1-2 日
- **ゴール**: `semantic_memory` テーブル + CRUD + sqlite-vec index を追加
- **依存**: `m4-contracts-freeze` (`SemanticMemoryRecord` schema)
- **検収**:
  - 要約レコード N 件格納 → 類似検索で上位 K 件 recall できる unit test
  - `create_schema()` idempotent 性維持
  - 既存 episodic_memory 機能に回帰なし
- **ファイル**: `src/erre_sandbox/memory/store.py`, `tests/test_memory/test_semantic_layer.py`,
  `docs/architecture.md` §Memory 追記

### 4. m4-gateway-multi-agent-stream (Axis A+C infra、並列可) — 1-2 日
- **ゴール**: per-agent broadcast routing + DialogTurnMsg 配線 + session routing
- **依存**: `m4-contracts-freeze` (`DialogTurnMsg` etc.)
- **検収**:
  - N WS client が異なる agent_id でセッション確立
  - broadcast が per-agent に分離して届く
  - ControlEnvelope variant discrimination が正しく動く
  - 既存 handshake / session FSM 回帰なし
- **ファイル**: `src/erre_sandbox/integration/gateway.py`,
  `tests/test_integration/test_multi_agent_stream.py`, `docs/architecture.md` §Gateway 追記

### 5. m4-cognition-reflection (Axis B logic、直列: semantic-layer merge 後) — 1-2 日
- **ゴール**: cognition cycle に reflection step を追加、per-agent で semantic memory に要約格納
- **依存**: `m4-contracts-freeze` (`ReflectionEvent`) + `m4-memory-semantic-layer` (保存先)
- **検収**:
  - N tick (default 10) ごとに reflection が発火
  - `semantic_memory` に要約レコードが追加される
  - 後続 tick で `recall_semantic()` 経由で retrieval が起きる
  - fallback 経路 (LLM timeout 時) が維持される
- **ファイル**: `src/erre_sandbox/cognition/cycle.py`, `tests/test_cognition/test_reflection.py`,
  `docs/architecture.md` §Cognition 追記

### 6. m4-multi-agent-orchestrator (Integration、最後、全 merged 後) — 1-2 日
- **ゴール**: bootstrap を N-agent 対応 + DialogScheduler 実装 + live 検証
- **依存**: 上記 5 本すべて merged
- **検収**: M4 全体 acceptance 5 項目 (design.md 参照) すべて PASS
  - `gateway-health-*.json` (3 agent 起動 + `active_sessions`)
  - `cognition-ticks-*.log` (3 agent 10s 周期)
  - `semantic-memory-dump-*.txt` + `reflection-fired-*.log`
  - `dialog-trace-*.log` (1 往復以上)
  - `godot-3avatar-*.mp4` (60s 以上 30Hz)
- **ファイル**: `src/erre_sandbox/bootstrap.py`, `src/erre_sandbox/__main__.py`,
  `src/erre_sandbox/world/dialog_scheduler.py`, `godot_project/scripts/AgentController.gd`,
  `docs/architecture.md` §Composition Root, `docs/functional-design.md` §4 M4

## MASTER-PLAN 追記
- [x] `MASTER-PLAN.md §5` に M4 詳細セクション (上記 6 サブタスク + Contract 凍結対象
      + 依存グラフ + 検収条件) を追記
- [x] memory `project_implementation_plan.md` に M4 planning 完了を追記

## 完了処理
- [x] `decisions.md` を作成 (/reimagine 採用判断 + hybrid foundation 小型化の根拠)
- [x] commit (`docs(steering): M4 planning — 3-axis + Contract-First subtask 分解 + /reimagine`)
- [x] push + PR 作成 (branch: `chore/m4-planning`)
- [x] PR review → main merge
- [x] tag 発行なし (v0.1.1-m2 据置)

## 次セッションで着手する最初のタスク

**`m4-contracts-freeze`** — `.steering/[merge-date]-m4-contracts-freeze/`
(本 planning merge 直後に `/start-task m4-contracts-freeze` で開始)

## スコープ外 (M5 以降)
- ERRE モード 6 種切替
- SGLang / vLLM 移行
- LoRA per persona
- 4 層評価 + 統計レポート
