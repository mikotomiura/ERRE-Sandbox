# M4 planning — 設計案比較 (v1 初回案 vs v2 再生成案)

## v1 (初回案) の要旨

MASTER-PLAN §5 に列挙された M4 代表タスク 4 本を素直にこの順番で **直列実行** する:
personas → memory-semantic → cognition-reflection → gateway-multi-agent。
各ステップ完了後に pytest 全グリーンを確認して次へ。最後に live 検証。
タスク分解は「層単位 (persona / memory / cognition / gateway)」で切る。

## v2 (再生成案) の要旨

M4 を **3 つの独立軸** (Multiplicity / Temporality / Sociality) に分解し、
`m4-contracts-freeze` を foundation として schemas.py + ControlEnvelope 変形体を
**最初に全部凍結** する。凍結後は 3 本 (personas / memory-semantic / gateway-multi-agent)
を **並列実行** し、cognition-reflection は memory-semantic 後に合流、
最後に `m4-multi-agent-orchestrator` で integration。
M2 で実証された **Contract-First** 成功パターンを再適用する。

## 主要な差異

| 観点 | v1 | v2 |
|---|---|---|
| 実行モデル | 直列 (4 steps, waterfall) | Contract-First + 並列 (1 foundation + 3 parallel + 1 serial + 1 integration) |
| タスク数 | 4 本 | 6 本 (contracts-freeze + orchestrator を明示) |
| タスク分解軸 | 層 (persona / memory / cognition / gateway) | 軸 (Multiplicity / Temporality / Sociality) + Foundation / Integration |
| schema_version | 未言及 (M2 の 0.1.0-m2 継続想定?) | `0.2.0-m4` に bump (foundation で明示凍結) |
| Contract 凍結 | 暗黙、Step 4 手前で "改めて確認" | 明示、Step 1 (`m4-contracts-freeze`) で全 primitive を凍結 |
| dialog (社会性) | gateway-multi-agent-stream に暗黙に含める | Axis C として独立識別、schemas + world + cognition + gateway 全層に跨る cross-cutting と認識 |
| DialogScheduler | 未設計 (gateway 責務?) | world/tick に明示配置、turn-taking ロジックを分離 |
| Critical Path | 4 ステップ全部 (約 3-7 日) | 4 本 (contracts → memory-semantic → cognition-reflection → orchestrator, 4-7 日) |
| 並列実行余地 | なし (全直列) | 3 本 (personas / memory-semantic / gateway-multi-agent) が初期並列可能 |
| live 検収条件 | 手動視認のみの言及 | 5 項目を MVP §4.4 形式で明示 |
| 最初の着手タスク | personas-nietzsche-rikyu-yaml | m4-contracts-freeze |
| 手戻りリスク | 後半で schemas 拡張が必要になった場合に前半 3 step 全部の再修正が発生しうる | foundation で凍結するので並列タスク間で契約ずれが発生しない |
| MacBook / G-GEAR 活用 | 暗黙 (1 機で直列想定) | foundation 後に両機並列実行可能 |

## 評価

### v1 の長所
- シンプル、認知負荷が低い
- MASTER-PLAN §5 の 4 代表タスク名をそのまま使えるので mapping が明快
- 各ステップが前のステップのコードに依拠するので確実性が高い
- 小回りが効く (早期に 1 体分の reflection 実装を試せる)

### v1 の短所
- dialog (社会性) が gateway-multi-agent-stream に潜在化、schemas + world への
  波及が見えにくい → 後半で scope creep が発生しうる
- Contract-First の恩恵を放棄 (M2 での成功パターンを活かしていない)
- 並列実行の機会を逃す (2 拠点構成の意味が薄れる)
- multi-agent orchestrator 拡張を明示タスク化していない (bootstrap 拡張は step 4 の末尾に押し込まれている)
- schema_version bump の判断が後回し

### v2 の長所
- Contract-First で後半の API 不整合リスクを最初に消す (M2 成功パターンの再適用)
- 3 軸分解によって dialog の cross-cutting 性を可視化、設計上の見落としを減らす
- 並列実行で 5-7 日短縮の可能性 (2 拠点を活用)
- multi-agent orchestrator を明示タスク化することで integration の責務が明確
- MVP §4.4 形式の検収条件 5 項目を明示し、receipt が明確

### v2 の短所
- foundation (contracts-freeze) で全 primitive を前倒し設計する必要 → M4 全体の
  schema を 1-2 日で決める集中負荷が発生
- 個別機能の実装中に "やはり schema 追加" となった場合は foundation の patch PR が必要
- タスク数が 4 → 6 に増える (管理コスト微増)
- 小回りが効きにくい (1 体分だけで試したい時も foundation を先に)

## 推奨案

**v2 を採用する。ただし contracts-freeze の粒度は "最小限で足りる primitive に絞る"**
(= ハイブリッド要素: foundation を小さく保つ)

### 根拠
1. **M2 Contract-First が成功した** — 10 日で MVP 完了、並列稼働が効いた実績。
   同じパターンを M4 に持ち込む正当性が既に検証済み (memory `project_implementation_plan.md`
   の "Why" 記述)。
2. **Dialog (Axis C) の cross-cutting 性を v1 は隠している** — 本来 schemas + world +
   cognition + gateway の全層に影響する機能が gateway-multi-agent-stream の 1 タスク内に
   押し込まれており、実装中に scope creep が発生する可能性が極めて高い。v2 はこれを
   Axis C として明示してから分解する。
3. **2 拠点構成の価値** — MacBook (Godot / docs マスター) と G-GEAR (inference 実機) の
   両機並列稼働が可能な構成。v1 は直列前提で両機並列の利点を活かさない。
4. **手戻りコスト非対称性** — schema を後から変えるコストは、前倒しで決めるコストより
   通常 3-5 倍高い (M2 でも T19 live で contract 非互換が発覚した経験がある)。
   foundation でまとめて凍結する方が合理的。
5. **hybrid 要素 (foundation の小型化)** は v2 短所への緩和策 — Contract 凍結対象を
   "最小限で足りる primitive" に絞れば、後続タスクで schema 追加が必要になった
   際の patch PR 負担が最小化される。具体的には:
   - `AgentSpec` (必須: bootstrap に渡せる形)
   - `ReflectionEvent` (必須: cognition → memory へ渡る)
   - `SemanticMemoryRecord` (必須: store の型)
   - `DialogTurnMsg` / `DialogInitiateMsg` / `DialogCloseMsg` (必須: ControlEnvelope variant)
   - `DialogScheduler` は **interface のみ** 凍結、実装は orchestrator タスクで完成
   - `register_agents()` API は `BootConfig.agents: list` で吸収 (別 API は定義しない)

## 次のアクション

1. `design.md` は v2 の内容のまま (上書き不要)
2. v2 末尾に「設計判断の履歴」を追記
3. `tasklist.md` に 6 サブタスクを列挙
4. `decisions.md` に採用根拠を記録
5. `MASTER-PLAN.md §5` に M4 詳細セクションを追記
