# 設計案比較 — m5-world-zone-triggers

## v1 (初回案) の要旨

FSM を `world/tick.py::_on_cognition_tick` の末尾に直接フックする。
`WorldRuntime.__init__` に `erre_policy` 引数と `attach_erre_policy` メソッドを
追加、`DialogScheduler` の注入パターンを踏襲。observations は `_step_one` 消費前
に snapshot を取り、`_consume_result` の後で FSM 呼び出し。mode 更新時は
`rt.state.erre` を `model_copy` で置換し、`ERREModeShiftEvent` を
`rt.pending` に emit (次 tick 以降で trace)。**`world/ → erre/` の layer 依存を
新規許可**として architecture-rules に追加。

## v2 (再生成案) の要旨

FSM を `cognition/cycle.py::CognitionCycle.step()` 内に内包する。mode 遷移は
cognitive な判断なので cognition 層が自然な owner という思想。world/tick.py は
**完全無変更**。`CognitionCycle.__init__` に `erre_policy` 引数を追加、
既存の `reflector` 注入パターンを踏襲。`step()` 内の episodic write 直後に
`_maybe_apply_erre_fsm` helper を呼び、`agent_state.erre` を更新して
`CycleResult.agent_state` で返却。world 側の `_consume_result` が既存ロジックで
自動適用。**`cognition/ → erre/` の layer 依存のみ追加**、`world/ → erre/`
は発生しない。

## 主要な差異

| 観点 | v1 (world hook) | v2 (cognition 内包) |
|---|---|---|
| **FSM の所属** | world 層 | cognition 層 |
| **呼出箇所** | `world/tick.py::_on_cognition_tick` 末尾 | `CognitionCycle.step()` 内、episodic write 直後 |
| **world/tick.py の変更** | 大きい (constructor + attach method + obs snapshot + FSM step + state update) | **無変更** |
| **cognition/cycle.py の変更** | なし | 中程度 (constructor + helper + step 内呼出) |
| **layer 依存追加** | `world/ → erre/` を許可 | `cognition/ → erre/` を許可 |
| **mode 更新経路** | `rt.state.erre = model_copy(...)` (直接書込) | `CycleResult.agent_state` 経由 (既存 `_consume_result` で自動適用) |
| **ERREModeShiftEvent emit 先** | `rt.pending` に追加 (次 tick へ) | `observations` リストに追記 or `envelopes` に追加 or 廃棄 (decisions で決定) |
| **観測の snapshot** | `_step_one` 消費前に list(rt.pending) で capture | `CognitionCycle.step()` が受け取る observations を直接渡す (シンプル) |
| **bootstrap 側 wiring** | `runtime.attach_erre_policy(policy)` | `CognitionCycle(..., erre_policy=policy)` |
| **既存 test 影響** | `tests/test_world/*` に新 test 追加、既存挙動 default 維持 | `tests/test_cognition/*` に新 test 追加、既存挙動 default 維持 |
| **sampling 適用までの遅延** | 1 cognition tick 遅延 (mode 変わってから次 tick で使う) | 同 tick 内で使える (episodic write 後 FSM、その後の処理で新 mode 参照可) |
| **意味論的な "ERRE mode" の位置づけ** | world (runtime) が mode を決める印象 | cognition (認知層) が mode を決める印象 |
| **将来の拡張性** | 別のリスナーを world に生やす設計になりやすい | CognitionCycle が cognition 関連決定の responsibility hub になる |

## 評価 (各案の長所・短所)

### v1 の長所
- `DialogScheduler` と同じ attach パターンで integration テスト時のセットアップが
  規則的
- `world/tick.py` が FSM 呼出しを明示的に行うので「いつ mode が遷移するか」を
  runtime view で追跡しやすい
- world runtime の責務が広がるだけで、cognition の signature に変化なし
  (cognition の API 互換性を重視)
- observation snapshot を一度 capture する pattern は他の runtime-level decision
  にも応用可能 (policy API を増やす時に再利用)

### v1 の短所
- **layer 変更が重い**: `world/ → erre/` は現行 architecture-rules 表で world の
  依存先を増やす方向性で、層責務の曖昧化に寄与しうる
- world/tick.py が 50+ 行規模の変更 (constructor 拡張 + attach + snapshot + FSM
  step + state update + envelope emit 判断)、diff が広くレビュー負荷
- ERRE mode は "どんな認知モードか" のメタ情報で、世界の時計 loop ではなく
  cognition の判断と見なす方が直感的
- mode 変更が `_step_one` 後のため、同 tick 内の LLM 呼出しが新 mode の sampling
  を使えない (1-tick 遅延)

### v2 の長所
- **architectural purity**: ERRE mode は認知状態 → cognition 層が owner 。
  `cognition/ → erre/` は `world/ → erre/` より自然
- **world/tick.py が完全無変更** → merge の blast radius が小さく、 regression
  リスク極小
- `CognitionCycle.step()` が既に受け取っている observations を直接 FSM に渡せるので
  snapshot 取得のオーバーヘッドなし
- mode 更新が `CycleResult.agent_state` を通るので、world が状態を書き換える
  2 本目の経路を増やさない (state update の single source of truth)
- mode 変更が同 tick 内で効く (episodic write → FSM → 後続の LLM 呼出しが新 mode
  の sampling を見られる)
- `reflector` 注入パターンと 1:1 対称、保守性が高い

### v2 の短所
- `CognitionCycle` の責務が「認知 cycle 実行」+「mode 遷移判定」に広がる
  (ただし元々 "cognition" なので妥当と解釈可能)
- `ERREModeShiftEvent` をどこに emit するか (observations 追記 / envelopes
  追加 / 破棄) の細かい決定が必要 (decisions.md で確定)
- cognition が erre に依存するので、循環参照にならないよう erre は cognition を
  import しないことを再確認する必要 (現状 erre は schemas のみ依存なので OK)

## 推奨案

**v2 (cognition 層内包) を採用**

### 理由

1. **architectural purity が v2 の方が高い**: ERRE mode は認知状態なので
   cognition 層が owner。`cognition/ → erre/` は `world/ → erre/` より受容しやすく、
   architecture-rules の拡張として自然
2. **world/tick.py 無変更の価値が大きい**: M4 で安定した tick 実装に手を入れずに
   FSM wiring を実現できる。regression リスクが最小
3. **mode 変更が同 tick 内で有効**: v1 の 1-tick 遅延は sampling_overrides の
   効きが遅れる実害がある (downstream `m5-erre-sampling-override-live` と整合を
   取りやすいのは v2)
4. **reflector 注入パターンとの対称性**: `CognitionCycle(reflector=..., erre_policy=...)`
   の形は cognition の dependency graph を統一的に表現できる
5. **`m5-orchestrator-integration` の wiring が簡単**: bootstrap で
   `CognitionCycle(erre_policy=DefaultERREModePolicy())` と 1 行足すだけ。
   WorldRuntime の constructor はそのまま

### v2 採用後の細部判断 (decisions.md で最終化)

- **ERREModeShiftEvent の扱い**: `CycleResult` を拡張せず、observations に
  追記しない。mode 遷移自体は `agent_state.erre` の変化として Godot に伝わる
  (`AgentUpdateMsg` 経由)。memory/reflection が mode 遷移を学習する必要が生じた
  時に追加 (今後の M6+)。これで CycleResult シグネチャ unchanged
- **mode 遷移のログ**: `CognitionCycle` 内で `logger.info` は出さない (tick loop
  で 10 秒毎にログが増える) → debug level に留める
- **下位層 (erre) が cognition へ逆依存しないことの再確認**: `erre/fsm.py` の
  import は `schemas` のみ。これは維持
