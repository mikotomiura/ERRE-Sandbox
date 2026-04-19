# E2E シナリオ (M2 統合試験)

機械可読な定義は `src/erre_sandbox/integration/scenarios.py` に置き、
本ファイルは **人間向けナラティブ** として各シナリオのユースケース説明と
合格判定の観点を記す。

各シナリオの step 配列と actor / action / expect の詳細は Python 側の
`SCENARIO_*.steps` を読む。

---

## S1. SCENARIO_WALKING — Kant の Peripatetic 移行

### 目的
最小の「living agent」ループが正しく発火することを示す:
ワールドに登録 → 初回認知サイクル → ERRE モード遷移 → Godot 側 Avatar 移動観測。

### 前提条件
- T14 gateway が 127.0.0.1 の WS port で listen している
- `personas/kant.yaml` がロード可能
- Peripatos ゾーンが WorldRuntime に登録済み (既定)
- Godot 側 T17 peripatos シーンが ws_client を既に接続済み

### 時系列 (概要)

| t (s) | actor | action | 観測すべき |
|---|---|---|---|
| 0.0 | world | Kant を Peripatos に初期配置 | `AgentUpdateMsg` 1 件、`erre_mode=SHALLOW`、`zone=PERIPATOS` |
| 1.0 | gateway | heartbeat 送出 | `WorldTickMsg` 1 件が client に届く |
| 10.0 | cognition | 認知サイクル発火、歩行方向更新 | `MoveMsg` 1 件、`speed > 0`、`erre_mode=PERIPATETIC` へ遷移済 |
| 11.0 | godot | Avatar Tween 移動開始 | `animation=walk`、Avatar の位置が target 方向に前進 |

### 合格判定
- 上記 4 step 全てが order を保って観測される
- `M2_THRESHOLDS.latency_p50_ms_max` 以内で配送される
- `AgentState.arousal / valence / attention` が M2_THRESHOLDS の値域内

### Python 側参照
```python
from erre_sandbox.integration import SCENARIO_WALKING
# SCENARIO_WALKING.steps = 4 steps (t_s=0, 1, 10, 11)
```

---

## S2. SCENARIO_MEMORY_WRITE — 記憶の蓄積

### 目的
歩行中に発生する internal event が memory-store に正しく書き込まれ、
episodic と semantic の比率が期待通りであることを確認。

### 前提条件
- S1 (SCENARIO_WALKING) の終端状態から継続
- sqlite-vec DB は毎回 fresh (conftest.py の `memory_store` fixture で初期化)

### 時系列 (概要)

| t (s) | actor | action | 観測すべき |
|---|---|---|---|
| 0.0 | world | S1 終端状態で再開 | `erre_mode=PERIPATETIC` を維持 |
| 10.0 | cognition | 4 episodic + 1 semantic を書込 | sqlite-vec に 5 行増加、embedding prefix 正しく付与 |
| 11.0 | gateway | AgentUpdateMsg で要約反映 | `agent_state.memory_count` が 5 増える |

### 合格判定
- `MemoryEntry` 5 件、うち `kind=EPISODIC` が 4、`kind=SEMANTIC` が 1
- 全行の埋め込みに `search_document: ...` / `search_query: ...` の prefix が適用済み
  (memory-store Skill §embedding prefix 強制ルール)
- `M2_THRESHOLDS.memory_write_success_rate_min` (0.98) を超える成功率

### Python 側参照
```python
from erre_sandbox.integration import SCENARIO_MEMORY_WRITE
# SCENARIO_MEMORY_WRITE.steps = 3 steps (t_s=0, 10, 11)
```

---

## S3. SCENARIO_TICK_ROBUSTNESS — 回復性

### 目的
一時的な tick 抜け・disconnect/reconnect に対して、session 境界で
agent 状態と memory が矛盾なく継続することを確認。

### 前提条件
- S1 の初期状態から開始
- Godot client 側に強制 disconnect を誘発する hook がある

### 時系列 (概要)

| t (s) | actor | action | 観測すべき |
|---|---|---|---|
| 0.0 | world | 初期 AgentUpdateMsg | client 受信 1 件 |
| 2.0 | gateway | heartbeat を 1 つ drop | client 側 liveness alarm は発報しない (3x 耐性) |
| 10.0 | godot | WS 強制切断、5 秒後に再接続 | 新 `HandshakeMsg` 交換、session 別 instance、AgentState 再送 |
| 20.0 | cognition | 認知サイクル継続 | disconnect 前後で agent_id 同一、memory に矛盾なし |

### 合格判定
- disconnect 前後で `agent_id` が同一
- 再接続後の `HandshakeMsg` で `SCHEMA_VERSION` が一致する
- memory-store の同一 agent の行数が disconnect を跨いで monotonic に増加する
  (減っていない)
- `SessionPhase` が `CLOSING` → (new session) `AWAITING_HANDSHAKE` → `ACTIVE` を通る

### Python 側参照
```python
from erre_sandbox.integration import SCENARIO_TICK_ROBUSTNESS
# SCENARIO_TICK_ROBUSTNESS.steps = 4 steps (t_s=0, 2, 10, 20)
```

---

## 将来シナリオ (M4 以降、本タスク対象外)

| ID | 対象 M | 概要 |
|---|---|---|
| S_DIALOG | M4 | 2 体以上のエージェントが同じゾーンで対話 |
| S_REFLECTION | M4 | 記憶 evict → 反省生成 → semantic 昇格 |
| S_MODE_FSM | M5 | ERRE モード 6 種切替の FSM 実証 |
| S_MULTI_ZONE | M5 | zone transition (study → peripatos → chashitsu) |
| S_12H_STABILITY | M7 | 5-8 体 × 12 時間無停止 |

これらは各マイルストーンのキックオフタスク (`.steering/YYYYMMDD-mN-kickoff/`) で設計する。
