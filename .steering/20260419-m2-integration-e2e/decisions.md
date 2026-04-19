# 設計判断 (T19 設計フェーズ)

本タスクでの設計判断を、根拠とともに記録する。

---

## D1. 契約の Single Source of Truth を Python モジュールに置く

### 判断
`src/erre_sandbox/integration/` を新設し、WS プロトコル定数・シナリオ・メトリクス閾値・
T20 acceptance チェックリストを Python の型付き定数として凍結する。
Markdown 文書 (`scenarios.md` / `integration-contract.md` / `metrics.md` /
`t20-acceptance-checklist.md`) は rational と人間向けナラティブに特化させる二層構造とする。

### 根拠
- T05 schemas-freeze が `src/erre_sandbox/schemas.py` で Contract を Pydantic 凍結した
  のと**同じパターン**を integration 層でも踏襲することで、プロジェクト全体の一貫性が保たれる
- 契約違反を mypy + pytest で機械検出できる
- T14 gateway 実装者が `from erre_sandbox.integration import Thresholds, SCENARIO_WALKING`
  で即消費可能
- 契約ドリフト検出 (test_contract_snapshot.py) が T14 完成を待たず今日から CI で稼働

### 却下した代替案
- **v1 案** (Markdown 中心): 契約ドリフトが人力レビュー依存、T05 との非対称が問題
- **AsyncAPI yaml**: 新規依存 (学習コスト)、既存プロジェクトに馴染まない

---

## D2. `integration/` は新レイヤーとして `schemas.py` のみに依存する

### 判断
`architecture-rules` Skill のレイヤー表に `integration/` を追加する。
初期依存は **`schemas.py` のみ**。T14 gateway 実装時に `world/` / `cognition/` /
`memory/` の import を追加することを許容する (gateway は top 層)。

新しい依存表 (本タスクで提案、architecture-rules Skill に後日反映予定):

| モジュール | 依存先 | 依存禁止 |
|---|---|---|
| `integration/` (contract 層) | `schemas.py` のみ | `inference/`, `memory/`, `cognition/`, `world/`, `ui/` |
| `integration/gateway.py` (T14 追加予定) | `schemas.py`, `world/`, `cognition/`, `memory/` | `ui/` |

### 根拠
- 本タスクで作る contract / scenarios / metrics / acceptance は純粋なデータ定義であり、
  他モジュールへの依存は不要
- gateway 実装時の依存拡張は T14 の別タスクで再度 `architecture-rules` 確認を行う
- `ui/` への依存は避ける (MacBook 側の WS クライアントなので Python 側 gateway は知るべきでない)

### 却下した代替案
- **`ui/` 配下に配置**: `ui/` は WS クライアント側 (MacBook)。gateway は WS サーバ側 (G-GEAR) なので役割が逆
- **`erre/` 配下**: `erre/` は ERRE DSL 向け。integration contract とは責務が異なる

---

## D3. WS メッセージ型は schemas.py の `ControlEnvelope` を再利用し、重複定義しない

### 判断
`integration/contract.py` は新規作成しない。
WS メッセージ型 (`HandshakeMsg` / `AgentUpdateMsg` / `SpeechMsg` / `MoveMsg` /
`AnimationMsg` / `WorldTickMsg` / `ErrorMsg` および `ControlEnvelope` union) は
既に `schemas.py` §7 で凍結されているため、これらを再利用する。

integration/ 側で新たに追加するのは **プロトコル運用ルール** のみ:
- `integration/protocol.py` に session lifecycle 定数 (heartbeat interval,
  handshake timeout, idle disconnect) と `SessionPhase` StrEnum を置く

### 根拠
- Contract の重複は保守コストを倍加させる (T05 と integration で型定義がズレるリスク)
- schemas.py の `ControlEnvelope` は既に discriminated union として完成している
- 「足りない情報」 = 運用パラメータ (timing / session state) であり、型ではない

### 却下した代替案
- **integration/contract.py で再定義**: schemas.py と二重管理、絶対 NG
- **schemas.py に session lifecycle を追加**: schemas は「on-wire 型のみ」の責務に限定。
  運用パラメータは別ファイルに

---

## D4. `test_contract_snapshot.py` は常時 ON、他 skeleton は全件 skip

### 判断
`tests/test_integration/test_contract_snapshot.py` は `@pytest.mark.skip` を付けず
**今日から CI で稼働**させる。内容は `ControlEnvelope` と `Thresholds` の
`model_json_schema()` の正規化 JSON を固定 snapshot として比較する。

他の skeleton テスト (walking / memory_write / tick_robustness) は
ファイル冒頭の `pytestmark = pytest.mark.skip(reason="T19 実行フェーズ待ち (T14 完成後に点灯)")`
で全件 skip。

### 根拠
- 契約スナップショットは**今日から価値を出せる** (T14 完成を待たず、schemas.py の不用意な変更をガード)
- シナリオテストは T14 の gateway 実装がないと走らせられない (依存注入が困難)
- 常時 ON の 1 件があることで「test_integration は機能する」ことを示せる

### 却下した代替案
- **全件 skip**: 契約ドリフト検出機会を失う
- **シナリオテストも未完成のまま ON**: CI が赤になる / 偽陰性発生

---

## D5. シナリオは Kant × Peripatos 単体に限定、ERRE モード 2 種のみ扱う

### 判断
本タスクの skeleton シナリオは以下 3 種に限定:

1. **S_WALKING**: Kant 起動 → Peripatos 入室 → ERRE モード `SHALLOW` から
   `PERIPATETIC` への遷移 → Godot 側 Avatar 移動観測
2. **S_MEMORY_WRITE**: S_WALKING に加え、歩行中の internal event で episodic
   4 件 + semantic 1 件の memory 書込みを確認
3. **S_TICK_ROBUSTNESS**: tick 抜け (1 tick drop 相当) → heartbeat 継続 →
   disconnect → reconnect で `HandshakeMsg` 再送

### 根拠
- M2 スコープは「1 体エージェント × 1 ゾーン」 (MASTER-PLAN §6)
- Peripatos は T17 で Godot シーンが完成している唯一のゾーン
- ERRE モード 8 種のうち M2 で意味があるのは `SHALLOW` / `PERIPATETIC` の 2 種
  (歩行中の認知モード差)
- M4 以降で拡張するシナリオ (S_DIALOG / S_REFLECTION / S_MULTI_AGENT) は
  本タスク対象外

### 却下した代替案
- **ERRE モード 8 種を全部シナリオ化**: M2 スコープ外、過設計
- **複数ゾーン**: chashitsu / agora / garden の Godot シーンは未実装 (T17 は Peripatos のみ)

---

## D6. メトリクス閾値は保守的に設定、実測後に decisions.md で調整ログ化

### 判断
`integration/metrics.py` の初期閾値は以下を採用:

| メトリクス | 初期閾値 | 根拠 |
|---|---|---|
| p50 tick→WS latency | ≤ 100 ms | tick 頻度 0.1 Hz (cognition) / 1 Hz (heartbeat) / 30 Hz (physics) を考慮した余裕値 |
| p95 tick→WS latency | ≤ 250 ms | p50 の 2.5x。LAN 内なので厳しめ |
| tick jitter σ | ≤ 20% | ManualClock でない実時間のブレの許容幅 |
| memory 書込み成功率 | ≥ 98% | sqlite-vec への write は基本成功、失敗は import error レベル |
| AgentState.arousal | 0.0 ≤ x ≤ 1.0 | schemas.py の `_Unit` 型制約と一致 |
| AgentState.valence | -1.0 ≤ x ≤ 1.0 | 同上 |
| AgentState.attention | 0.0 ≤ x ≤ 1.0 | 同上 |

T19 実行フェーズで実測後、`decisions.md` の D6 に実測値と調整を追記する運用。

### 根拠
- 実測前の厳しすぎる閾値は T19 実行フェーズで慢性赤化の原因になる
- 実測後に「妥当な範囲でできるだけ厳しく」調整するほうが健全
- AgentState の値域は schemas.py の制約と同期させることで矛盾を避ける

### 却下した代替案
- **実測ベースを待って閾値を決める**: 本タスクは設計フェーズのみなので先に保守的な値を置く
- **AgentState 値域を緩く取る**: schemas.py と矛盾するので不可

---

## D7. T20 acceptance checklist は Python リストと Markdown runbook の二層で管理

### 判断
- `src/erre_sandbox/integration/acceptance.py` に `AcceptanceItem` dataclass +
  `ACCEPTANCE_CHECKLIST: tuple[AcceptanceItem, ...]` を置く
- 各 `AcceptanceItem` は `id: str, description: str, category: str, verification: str`
- `.steering/.../t20-acceptance-checklist.md` は runbook 形式で人間向け手順 (operator 視点)

### 根拠
- Python リストなら pytest で parametrize して自動化できる将来性がある
- Markdown runbook はタグ付け時の手動確認に使う
- Python と Markdown の同期は `AcceptanceItem.id` による相互参照で担保

### 却下した代替案
- **Markdown のみ**: 機械可読性なし、将来の自動化に不利
- **Python のみ**: 手動 MVP タグ付け時の可読性が悪い
