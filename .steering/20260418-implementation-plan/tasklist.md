# タスクリスト

実装順序と担当機は MASTER-PLAN.md §4.3 の依存グラフに従う。
各タスクは `.steering/[YYYYMMDD]-[task-name]/` ディレクトリを別途作成して
`/start-task` で着手、`/finish-task` で終了する。

## MVP (M2) — 20 タスク

### Phase S: セットアップ (両機並列)
- [ ] T01 `setup-g-gear` (G-GEAR, 1d)
- [ ] T02 `setup-macbook` (MacBook, 0.5d)
- [ ] T03 `pdf-extract-baseline` (MacBook, 0.5d) — pdftotext 化 + _pdf_derived/ 配置

### Phase C: Contract Freeze (MacBook 単独)
- [ ] T04 `pyproject-scaffold` (MacBook, 0.5d)
- [x] T05 `schemas-freeze` (MacBook, 1d) ★ Contract の核 — **CSDG 参照**: `csdg/schemas.py` の HumanCondition / CharacterState / DailyEvent 構造 (MASTER-PLAN.md §B.2)
- [x] T06 `persona-kant-yaml` (MacBook, 0.5d) — **CSDG 参照**: `prompts/System_Persona.md` のペルソナ項目階層
- [x] T07 `control-envelope-fixtures` (MacBook, 0.5d) — Godot と Python 両方から読む JSON
- [x] T08 `test-schemas` (MacBook, 0.5d) ★ Contract 凍結の境界

### Phase BG: モデル pull (G-GEAR バックグラウンド)
- [ ] T09 `model-pull-g-gear` (G-GEAR, 実時間 2-4h, 作業時間 0.5d)

### Phase P: Parallel Build (両機並列)

#### G-GEAR 側
- [ ] T10 `memory-store` (G-GEAR, 1.5d) — **CSDG 参照**: `csdg/engine/memory.py` + `ShortTermMemory` / `LongTermMemory` の 2 層構造 (MASTER-PLAN.md §B.2)
- [ ] T11 `inference-ollama-adapter` (G-GEAR, 1d) — **CSDG 参照**: `csdg/llm_client.py` のプロバイダー抽象化パターンのみ (API は書き直し)
- [ ] T12 `cognition-cycle-minimal` (G-GEAR, 1.5d) — **CSDG 参照**: `csdg/engine/state_transition.py` の半数式と HumanCondition 自動導出の 4 要素ロジックを流用 (MASTER-PLAN.md §B.3)
- [ ] T13 `world-tick-zones` (G-GEAR, 1d)
- [ ] T14 `gateway-fastapi-ws` (G-GEAR, 1d)

#### MacBook 側
- [x] T15 `godot-project-init` (MacBook, 0.5d)
- [x] T16 `godot-ws-client` (MacBook, 1d, PR #12) — WebSocket + Router (7 専用 signal) + Fixture 境界分離 + schema 同期ガード
- [x] T17 `godot-peripatos-scene` (MacBook, 1d) — Peripatos 3D (非対称 post / PlaneMesh 40×4m) + AgentAvatar + Tween 駆動移動 (Contract speed 利用) + ZONE_MAP + 106 tests pass
- [ ] T18 `ui-dashboard-minimal` (MacBook, 0.5d) — optional

### Phase I: Integration
- [ ] T19 `m2-integration-e2e` (両機, 1d)
- [ ] T20 `m2-acceptance` (両機, 0.5d) — `v0.1.0-m2` タグ付与

## 本番構築版 (M4 → M10-11)

各マイルストーンの直前に `.steering/YYYYMMDD-mN-kickoff/` を作成して詳細設計する。

### M4 — 3 体対話・反省・関係形成
- [ ] `cognition-reflection` — **CSDG 参照**: `csdg/engine/memory.py` の `_llm_extract_beliefs_and_themes()` を evict→extract パターンで転用
- [ ] `cognition-relationship`
- [ ] `memory-semantic-layer` — **CSDG 参照**: `LongTermMemory.beliefs` / `recurring_themes` / `turning_points` の蒸留構造
- [ ] `personas-nietzsche-rikyu-yaml`
- [ ] `gateway-multi-agent-stream`

### M5 — ERRE モード 6 種切替
- [ ] `erre-mode-fsm`
- [ ] `erre-sampling-override`
- [ ] `world-zone-triggers`
- [ ] `godot-zone-visuals`
- [ ] `pdf-docs-sync` (M5 完了後にドリフト検知)

### M7 — 5-8 体 × 12 時間安定運転
- [ ] `memory-decay-compression`
- [ ] `cognition-piano-parallel`
- [ ] `inference-sglang-migration` ★ SGLang 本番移行
- [ ] `observability-logging`
- [ ] `examples-walking-thinkers-12h`

### M9 — LoRA per persona (vLLM)
- [ ] `inference-vllm-adapter`
- [ ] `lora-training-pipeline`
- [ ] `lora-runtime-swap`

### M10-11 — 4 層評価 + 統計レポート
- [ ] `eval-layer1-spatial` (Ripley K, Kuramoto)
- [ ] `eval-layer2-semantic` (embedding drift) — **CSDG 参照**: `csdg/engine/critic.py` Layer 2 の統計的検証 (平均文長, trigram overlap, 疑問文比率)
- [ ] `eval-layer3-ritual` (反復 + 時空間規則 + 集合 + 非機能) — **CSDG 参照**: `csdg/engine/critic.py` Layer 1 の余韻テンプレート反復検出
- [ ] `eval-layer4-thirdparty` (LLM-as-judge + ICC) — **CSDG 参照**: `csdg/engine/critic.py` の 3 層 Critic + 重み合成 (0.40/0.35/0.25) + Veto + 逆推定一致スコア (MASTER-PLAN.md §B.2)
- [ ] `eval-statistics-bh-fdr`
- [ ] `docs-osf-preregistration`
- [ ] `docs-mkdocs-bilingual`

## 最初に着手するタスク

1. MacBook で `/start-task` → T02 `setup-macbook`
2. 並行して G-GEAR で `/start-task` → T01 `setup-g-gear`
3. T02 完了後に T03 → T04 → T05 (Contract Freeze)
4. T05 着手と同時に G-GEAR で T09 モデル pull をバックグラウンド
5. T08 完了後、両機並列で Phase P 突入

## 完了処理 (本計画タスク単体)

- [x] requirement.md / design.md / tasklist.md / decisions.md / MASTER-PLAN.md を配置
- [x] MEMORY.md に参照リンクを追記
- [ ] 初回 Git コミット (本計画ディレクトリの追加)
