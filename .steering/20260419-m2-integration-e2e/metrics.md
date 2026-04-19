# 受け入れメトリクス (M2 integration)

機械可読な数値定義は `src/erre_sandbox/integration/metrics.py` の
`Thresholds` / `M2_THRESHOLDS` を参照する。本ファイルは **閾値の根拠** と
**測定方法** を人間向けに説明する rational 文書。

## 1. 現在の閾値一覧 (M2_THRESHOLDS)

| フィールド | 値 | 単位 | 根拠 |
|---|---|---|---|
| `latency_p50_ms_max` | 100 | ms | LAN 内 WS の典型的往復時間 (10-30ms) + runtime scheduler 粒度 (数十 ms) を見込み、余裕を持たせた値 |
| `latency_p95_ms_max` | 250 | ms | p50 の 2.5x。異常点は tail 側にしか出ないので厳しめに設定 |
| `tick_jitter_sigma_max` | 0.20 | 比率 (dimensionless) | ManualClock と異なり RealClock の揺らぎは発生。20% 以内なら human perception 的に違和感なし |
| `memory_write_success_rate_min` | 0.98 | 比率 | sqlite-vec の write は基本成功するため、失敗は import error レベルの異常 |
| `arousal_min` / `arousal_max` | 0.0 / 1.0 | schemas.py `_Unit` | `schemas.py` の `_Unit` 型制約と同一 |
| `valence_min` / `valence_max` | -1.0 / 1.0 | schemas.py 型制約 | 同上 |
| `attention_min` / `attention_max` | 0.0 / 1.0 | schemas.py `_Unit` | 同上 |

## 2. 測定方法

### 2.1 latency

- **定義**: envelope が `WorldRuntime._envelopes` に put されてから、
  client (pytest 側の WS stub) が受信するまでの経過時間 (ms)
- **収集**: T19 実行フェーズで、`time.monotonic()` を両端で取得して diff を記録。
  ログに JSON で 1 envelope 1 行記録、scenario 終了後に集計。
- **集計**: numpy で `np.percentile(latencies, [50, 95])`

### 2.2 tick_jitter_sigma

- **定義**: `WorldTickMsg` の受信間隔 `Δt_i` の列 (i=1..N) について
  σ / μ を計算した比率 (dimensionless)
- **収集**: scenario 実行中の全 `WorldTickMsg` の `sent_at` を列挙
- **合格**: σ / μ ≤ 0.20 (20%)

### 2.3 memory_write_success_rate

- **定義**: `MemoryStore.insert()` の attempt 数に対する success 数の比率
- **収集**: ログの `memory.insert.attempt` と `memory.insert.success` を集計
- **合格**: 成功率 ≥ 0.98

### 2.4 AgentState 値域

- **定義**: scenario 実行中に観測された `AgentUpdateMsg` の
  `agent_state.arousal / valence / attention` が全件閾値範囲内
- **合格**: 逸脱 0 件 (schemas.py の Pydantic 検証で本来は invalid になるが、
  二重確認として試験でも見る)

## 3. 調整履歴 (T19 実行フェーズ以降に追記)

| 日付 | フィールド | 旧値 | 新値 | 根拠 |
|---|---|---|---|---|
| 2026-04-19 | 初期値 | — | 上表の M2_THRESHOLDS | T19 設計フェーズで D6 として策定 |

**運用ルール**:
- 閾値変更時は `decisions.md` D6 に実測値と判断を追記する
- `integration/metrics.py` の値を変更する PR は必ず本ファイルの「調整履歴」を更新する
- `test_contract_snapshot.py::test_m2_thresholds_values` で固定値を検証しているため、
  変更は CI で自動検出される (意図的変更なら該当 test も同 PR で更新)

## 4. 未採用の候補メトリクス

T19 実行時に追加検討すべき候補 (本タスクでは採用せず):

- **cognition cycle LLM latency**: Ollama `/api/chat` の p50/p95
  (llm-inference Skill の監視責務と重複するため、本 Skill では扱わない)
- **VRAM 使用率**: `nvidia-smi` 出力の経時観測
  (llm-inference Skill 領域)
- **WS connection churn**: 接続/切断の頻度
  (M7 の 12 時間安定運転時に扱う)

## 5. 参照

- `src/erre_sandbox/integration/metrics.py`
- `src/erre_sandbox/schemas.py` §4 AgentState
- `.steering/20260419-world-tick-zones/design.md` §tick jitter 観点
- `.steering/20260418-memory-store/` §sqlite-vec write の retry 戦略
