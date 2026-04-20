# M4 Planning (3-agent 拡張 + reflection + semantic memory + multi-agent gateway)

## 背景

v0.1.1-m2 で MVP (1-Kant walker full-stack) が完了し、GAP-1 (WorldRuntime ↔ Gateway 実配線)
も T21 で解消した。次マイルストーン **M4** は MASTER-PLAN §5 で以下のゴールを持つ:

> **M4**: 3 体対話・反省・関係形成
> 代表タスク: `cognition-reflection`, `memory-semantic-layer`,
> `personas-nietzsche-rikyu-yaml`, `gateway-multi-agent-stream`
> 備考: 認証なし継続 (LAN 前提)

M4 は複数の相互依存タスクを含み、単純な時系列積み上げだと後半で API 不整合・
orchestrator 再設計の手戻りが発生するリスクが高い。MVP (M2) と同様に
**Contract-First** 志向で先に interface を凍結し、並列実装を可能にする
**全体計画の策定 (M4 planning)** が本タスクの責務。

## ゴール

M4 全体を以下の粒度で確定する:

1. **サブタスク分割**: 4-6 個の `.steering/YYYYMMDD-*/` 単位に分解
2. **依存グラフ**: Critical Path と並列実行可能な区間を明示
3. **契約 (Contract) 凍結対象**: M4 全体で先に凍結すべき schema / API の特定
4. **検収条件**: M4 全体と各サブタスクの受け入れ条件
5. **最初の着手タスク**: planning merge 直後に `/start-task` で開くもの
6. **破壊と構築の結果**: `/reimagine` で初回案を破棄し再生成案と比較、採用案決定
7. **documentation の更新方針**: `docs/functional-design.md` §4 / `architecture.md` への反映計画

本タスクは **planning only** (コード変更なし、docs + .steering のみ)。
M4 の個別実装は別タスクで実施する。

## スコープ

### 含むもの
- M4 全体の範囲定義と受け入れ条件
- `/reimagine` 適用 (必須: 設計判断を伴うため)
- サブタスク分解と依存グラフ作成
- 契約凍結対象の特定 (schema + API)
- 最初に着手するサブタスクの確定
- MASTER-PLAN §5 への M4 詳細計画の追記
- `docs/functional-design.md` / `docs/architecture.md` に対する M4 追記予告
  (実際の更新は個別サブタスクで実施)

### 含まないもの
- M4 個別サブタスクの実装 (別タスクで実施)
- 契約 (schema / API) の具体的な差分記述 (初期タスクで凍結)
- persona YAML の本体記述 (`personas-nietzsche-rikyu-yaml` サブタスクで実施)
- reflection algorithm の具体設計 (`cognition-reflection` サブタスクで実施)
- semantic memory layer の DB schema 決定 (`memory-semantic-layer` サブタスクで実施)
- multi-agent gateway の WS protocol 拡張 (`gateway-multi-agent-stream` サブタスクで実施)
- M5 以降 (ERRE モード FSM / SGLang / LoRA) の詳細

## 受け入れ条件

- [ ] `design.md` に `/reimagine` 2 案比較と採用案 (または hybrid) が記述されている
- [ ] M4 サブタスク一覧が `tasklist.md` に 4-6 個で列挙されている
  (各タスクはゴール / 依存 / 検収条件を含む)
- [ ] 依存グラフ (Critical Path) が ASCII or Mermaid で明記されている
- [ ] Contract-First で先に凍結すべき schema / API が 1-2 行で列挙されている
- [ ] M4 全体の検収条件が MVP §4.4 と同形式で 4-6 項目定義されている
- [ ] 最初に着手するサブタスク名と `.steering/` ディレクトリ名が確定している
- [ ] `MASTER-PLAN.md §5` に M4 の詳細計画セクションが追記されている
- [ ] `decisions.md` に `/reimagine` 採択判断の根拠が記述されている
- [ ] PR が作成され、main に merge されている (tag 付与なし、v0.1.1-m2 据置)

## 関連ドキュメント

- `.steering/20260418-implementation-plan/MASTER-PLAN.md` §5 (本計画を追記する場所)
- `.steering/20260418-implementation-plan/MASTER-PLAN.md` §4 (MVP 計画の参照形式)
- `.steering/20260419-m2-integration-e2e-execution/known-gaps.md`
  (M4 kickoff で対処すべき残存 GAP 一覧)
- `.steering/20260419-m2-functional-closure/decisions.md` (M2 closeout での設計判断、M4 への継承点)
- `docs/functional-design.md` §4 (MVP 定義、M4 で拡張する要件の参照元)
- `docs/architecture.md` §Gateway / §Cognition / §Memory (M4 で触る層の現状)
- `personas/kant.yaml` (M4 で 3 体化するペルソナのベースライン)
- memory: `project_t19_known_gaps.md` (GAP-2/3/4/5 の M4 での扱い方針)
- memory: `feedback_reimagine_trigger.md` (M4 のような設計タスクでは必ず `/reimagine` 適用)
- memory: `feedback_reimagine_scope.md` (content curation も対象)

## 運用メモ

- 破壊と構築 (`/reimagine`) 適用: **Yes**
- 理由: M4 はアーキテクチャ判断 (multi-agent orchestrator 構造 / reflection 発火条件 /
  semantic memory の分離方針) + 複数案が自然に生じる設計であり、
  memory `feedback_reimagine_trigger.md` の適用対象そのもの。
- タスク種類: その他 (planning only、コード変更なし)。個別実装は `/add-feature`
  で別タスクに着手予定。
