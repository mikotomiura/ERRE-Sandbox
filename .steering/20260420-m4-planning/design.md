# M4 設計 — v2 (再生成案: 3 軸分解 + Contract-First 凍結 + 並列実装)

## 実装アプローチ

M4 のゴール「3 体対話・反省・関係形成」は **単一の時系列層で積み上げられる性質ではなく、
3 つの独立した軸を同時に導入する必要がある**。素直な層積み上げは dialog / reflection
が cross-cutting concern であることを無視する。

M4 を以下の **3 軸** に分解し、各軸の境界を契約 (Contract) で先に凍結する。
凍結後は各軸を並列実装し、最後に 1 本の integration タスクで合流させる。
これは M2 で実証された Contract-First の成功パターンを M4 に再適用したもの。

### 3 つの独立軸

| Axis | 名前 | 性質 |
|---|---|---|
| **A** | Multiplicity (1 → N) | 1-agent 前提を N-agent 前提に拡張する軸。bootstrap + gateway + Godot が対象 |
| **B** | Temporality (tick → reflective) | tick-driven cognition に per-agent reflection を挿入する軸。cognition + memory が対象 |
| **C** | Sociality (isolated → dialogical) | agent 間の対話を発火・受信する軸。schemas + world + cognition + gateway の全層に跨る cross-cutting |

### Contract 凍結対象 (M4 foundation — 小型化方針)

Foundation が肥大化すると個別タスクで "schema 追加待ち" が発生しうるため、
凍結対象は **後続タスクが並列実行するために必須な最小 primitive** に絞る。
interface-only 凍結 (実装は個別タスクで) や、既存 struct への field 追加で吸収できる
ものは独立 primitive にしない。

| Axis | 凍結対象 | 粒度 | 凍結形式 |
|---|---|---|---|
| A | `AgentSpec` (persona_id + initial_zone の最小 fields) | struct | Pydantic class 完成形 |
| A | `BootConfig.agents: list[AgentSpec]` | field 追加 | 既存 BootConfig 拡張、別 API (`register_agents`) は作らない |
| B | `ReflectionEvent` | struct | 最小 fields (agent_id, tick, summary_text, src_episodic_ids) |
| B | `SemanticMemoryRecord` | struct | 最小 fields (id, agent_id, embedding, summary, origin_reflection_id) |
| C | `DialogInitiateMsg`, `DialogTurnMsg`, `DialogCloseMsg` | ControlEnvelope variant | Pydantic class 完成形 |
| C | `DialogScheduler` | **interface only** | Protocol 宣言のみ、具体実装は `m4-multi-agent-orchestrator` タスクで |

**schema_version bump**: `0.1.0-m2` → `0.2.0-m4` (breaking changes を明示、fixture 刷新)

凍結しないもの (個別タスクで決める):
- reflection 発火条件 (N tick? importance 閾値?) → `m4-cognition-reflection` で
- semantic_memory の sqlite schema 詳細 (index 構成、embedding dim 等) → `m4-memory-semantic-layer` で
- DialogScheduler 本体 (turn-taking policy) → `m4-multi-agent-orchestrator` で
- per-agent gateway routing 方式 (broadcast filter? explicit subscription?) → `m4-gateway-multi-agent-stream` で

全 primitive を **最初のサブタスク `m4-contracts-freeze`** で凍結し、
`tests/fixtures/m4/` に新 fixture を生成する。M4 個別タスクは凍結された contract の
上で並列実装する。

## サブタスク分解 (6 本)

1. **`m4-contracts-freeze`** (Foundation、直列、必須最初) — 0.5-1 日
   - schemas.py 拡張 + fixture 生成 + schema_version bump
   - 検収: 新 fixture で WS 互換テスト PASS、既存 346 テスト継続 PASS、
     GDScript parser が新 variant を hard-error なく受信

2. **`m4-personas-nietzsche-rikyu-yaml`** (Axis A content、並列可) — 0.5 日
   - `personas/nietzsche.yaml`, `personas/rikyu.yaml` 新規作成
   - 検収: `PersonaSpec` validation PASS、persona loader で読み込める unit test、
     ERRE mode / sampling override が kant.yaml と差分ある thought-life を反映

3. **`m4-memory-semantic-layer`** (Axis B infra、並列可) — 1-2 日
   - `semantic_memory` テーブル + `upsert_semantic()` / `recall_semantic()` CRUD
   - embedding column 含む、sqlite-vec への index 設定
   - 検収: 要約レコード N 件格納 → 類似検索で上位 K 件 recall できる unit test

4. **`m4-gateway-multi-agent-stream`** (Axis A+C infra、並列可、B と独立) — 1-2 日
   - per-agent broadcast routing、agent_id フィルタ、DialogTurnMsg 配線
   - 検収: N WS client が異なる agent_id でセッション確立、broadcast が per-agent
     に分離して届く、ControlEnvelope の variant discrimination が動く

5. **`m4-cognition-reflection`** (Axis B logic、直列: semantic-layer 後) — 1-2 日
   - N tick ごとに reflection を発火 (default N=10、peripatos 滞在時)
   - episodic memory の summarization → semantic_memory 保存の実装
   - 検収: N tick で per-agent reflection が発火、semantic_memory row が追加され
     後続 tick で recall_semantic() 経由で retrieval される

6. **`m4-multi-agent-orchestrator`** (Integration、最後、必須全 merged) — 1-2 日
   - bootstrap を `register_agents([kant, nietzsche, rikyu])` に拡張
   - DialogScheduler 実装 (turn-taking の発火ロジック、world/tick に組込)
   - 検収: M4 全体 acceptance (下記 5 項目) すべて PASS

## 依存グラフ

```
                  [m4-contracts-freeze]  ← foundation, 他 5 本の前提
                        │
     ┌──────────┬───────┴───────┬──────────────┐
     ↓          ↓               ↓              ↓
 personas   memory-         gateway-        (並列実行)
  -n-r-     semantic-       multi-agent-
  yaml      layer           stream
                │
                ↓
          cognition-
          reflection   (直列、semantic-layer 後)
                │
                └──→ [m4-multi-agent-orchestrator] ←── 全 5 本 merged
                           │
                           ↓
                   [M4 acceptance live 検証]
```

**Critical Path**: `contracts-freeze → memory-semantic-layer → cognition-reflection → orchestrator`
= 約 4-7 日。並列 3 本 (personas / gateway / semantic-layer) が Critical Path を後押ししない。

## M4 全体の検収条件 (MVP §4.4 と同形式)

1. **起動**: `uv run erre-sandbox --personas kant,nietzsche,rikyu` で 3 agent 起動、
   `/health` で `schema_version=0.2.0-m4`, `active_sessions` counter が正しい
   (evidence: `gateway-health-*.json`)
2. **3 agent walking**: 3 avatar が peripatos で同時に歩き、10s 周期で各 agent の
   cognition tick が回る (evidence: `cognition-ticks-*.log` per-agent)
3. **Reflection**: 各 agent について N tick ごとに reflection が発火し
   `semantic_memory` にレコード追加、後続 tick で recall される
   (evidence: `semantic-memory-dump-*.txt` + `reflection-fired-*.log`)
4. **Dialog**: DialogInitiateMsg が発火して他 agent が DialogTurnMsg を 1 往復以上返す
   (evidence: `dialog-trace-*.log`, ControlEnvelope sequence)
5. **Godot 3-avatar 30Hz**: MacBook Godot で 3 avatar が描画され 60s 以上 30Hz を維持
   (evidence: `godot-3avatar-*.mp4`)

## 変更対象

### 本 planning タスクで変更するファイル (planning only)
- `.steering/20260420-m4-planning/design.md` — 本ファイル
- `.steering/20260420-m4-planning/tasklist.md` — サブタスク一覧
- `.steering/20260420-m4-planning/decisions.md` — 採用根拠
- `.steering/20260418-implementation-plan/MASTER-PLAN.md` — §5 に M4 詳細追記

### 本 planning タスクでは変更しないファイル (個別サブタスクで実施)
- `src/` 配下のコード一切 (Axis A/B/C の実装は個別サブタスクに委譲)
- `docs/functional-design.md`, `docs/architecture.md` (個別サブタスクで追記)
- `personas/*.yaml` (content は persona サブタスクで)

## 影響範囲

- 本タスクは planning only のためコード影響なし
- M4 全体として schema_version bump を伴う → `0.1.0-m2` fixture と
  `0.2.0-m4` fixture が混在する期間あり
- M2 との back-compat は不要 (M4 merge 後は古い fixture を削除)
- MacBook / G-GEAR 両機構成を継続 (Contract 凍結後に両機並列実行可能)

## 既存パターンとの整合性

- **Contract-First**: M2 で確立、M4 に再適用。memory / feedback で繰り返し正当化されている
- **`.steering/YYYYMMDD-*/` 単位**: 既存慣習のまま
- **`/reimagine` 必須**: memory `feedback_reimagine_trigger.md` 準拠
- **bootstrap.py composition root**: M2 で導入した構造を拡張 (破棄せず継承)
- **MemoryStore の create_schema idempotent パターン**: `semantic_memory` 追加時も踏襲

## テスト戦略

- 本 planning タスクはコード変更なし → pytest 現状維持 (346 PASS)
- 個別サブタスクは各々 unit + integration テストを持つ
- M4 全体 acceptance は live 検証 (上記検収条件 5 項目)

## ロールバック計画

本 planning タスクは docs のみ。問題あれば PR revert で即戻せる。
個別サブタスク段階でのロールバックは各 PR 単位で行う
(Contract-First の利点: 個別 PR revert で contract が壊れない限り並列タスクに波及しない)。

## M4 初手に着手するタスク

**`m4-contracts-freeze`** (`.steering/[merge-date]-m4-contracts-freeze/`)

理由: 他の 5 本すべての依存元。これを先に凍結しないと並列実装できない。

## ドキュメント更新方針

- 本タスク内: MASTER-PLAN §5 に M4 詳細計画セクションを追記
- 個別サブタスク内: 該当する `docs/architecture.md` / `functional-design.md`
  セクションを個別タスクで更新
  - contracts-freeze → `docs/architecture.md` §Schemas
  - memory-semantic-layer → §Memory
  - cognition-reflection → §Cognition
  - gateway-multi-agent-stream → §Gateway
  - multi-agent-orchestrator → §Composition Root + `docs/functional-design.md` §4 M4

---

**本 v2 案の位置付け**: M2 の Contract-First 成功パターンを M4 に再適用し、
3 軸 (Multiplicity / Temporality / Sociality) を並列実装可能にする再設計。

## 設計判断の履歴

- 初回案 (`design-v1.md`) は MASTER-PLAN §5 の 4 タスクを時系列に直列積み上げる案
- `/reimagine` で再生成案 v2 (Contract-First + 3 軸分解 + 並列実装) を生成
- `design-comparison.md` で両案の長短を比較
- **採用**: **v2 + hybrid (foundation 小型化)**
- 根拠:
  1. M2 Contract-First が実証済み (MVP 10 日完了、並列稼働が機能した実績)
  2. dialog (Axis C) の cross-cutting 性を v1 は隠しており、後半の scope creep リスク
     が高い → v2 で foundation 凍結時に顕在化させる
  3. 2 拠点構成 (MacBook / G-GEAR) を並列活用でき、5-7 日短縮の可能性
  4. schema を後から変えるコストは前倒しコストの 3-5 倍 (M2 T19 live 検証で実体験)
  5. hybrid 要素 (foundation を最小 primitive に絞る + DialogScheduler は interface only)
     で v2 短所を緩和
