# 設計 — m4-gateway-multi-agent-stream (v2: server-side agent_id 購読フィルタ)

> v2 は /reimagine で v1 を破棄し、requirement.md のみを立脚点に再構築した案。

## 実装アプローチ

planning design.md §「per-agent gateway routing 方式 (broadcast filter vs
explicit subscription)」は本タスクで決定すると明記されており、
検収条件も「broadcast が per-agent に分離して届く」と書かれている。
これは単なる capability 拡張ではなく、**server-side filtering** の導入を
意図している。

schema (`SCHEMA_VERSION=0.2.0-m4`) は foundation で凍結済みのため、
サブスクリプションを wire type に追加せず、**URL クエリパラメタ**
(`/ws/observe?subscribe=kant,nietzsche`) で表現する。これにより:

1. `HandshakeMsg` スキーマを触らない (schema 変更なし、互換性維持)
2. 空 or 未指定なら全購読 (= broadcast 後方互換)
3. 特定 agent のみ購読する debug monitor / dev viewer が自然に書ける
4. Godot の既存 WS URL に `?subscribe=*` を付けるだけで済む

routing 判定は `_envelope_target_agents(env) -> frozenset[str] | None` で:
- `agent_update` / `speech` / `move` / `animation`: それぞれの `agent_id`
- `dialog_initiate`: `{initiator_agent_id, target_agent_id}`
- `dialog_turn`: `{speaker_id, addressee_id}`
- `dialog_close`: **broadcast** (metadata のみ、dialog_id から participants
  を逆引きする register を持たない — UI cleanup に必要なので全員受信)
- `world_tick` / `error` / `handshake`: **broadcast**

`Registry.fan_out(env)` は各 session の購読 set と routing target を突合し、
一致するか broadcast 対象なら push、そうでなければ skip。

## 変更対象

### 修正
- `src/erre_sandbox/integration/gateway.py`:
  - `_SERVER_CAPABILITIES` に `dialog_initiate` / `dialog_turn` /
    `dialog_close` を追加 (7 → 10 kinds)
  - `Registry.add` のシグネチャを `(session_id, queue, subscribed_agents)`
    に拡張 (`subscribed_agents: frozenset[str] | None = None`; None = broadcast)
  - `Registry._subscriptions: dict[str, frozenset[str] | None]` を追加
  - `Registry.fan_out(env)` に routing 判定を組み込み
  - `_envelope_target_agents(env) -> frozenset[str] | None` helper 追加
  - `ws_observe` で `ws.query_params.get("subscribe")` を parse:
    - 未指定 or 空 → `None` (broadcast)
    - `*` → `None` (broadcast, 明示)
    - `"kant,nietzsche"` → `frozenset({"kant", "nietzsche"})`
    - persona_id 検証は不要 (unknown id は届かないだけ、DoS 耐性あり)
  - `Registry.add` で `subscribed_agents` も渡す
  - `health` endpoint に `subscriptions` 集計を任意で追加
    (デバッグ便利だが本 PR では必須ではない)
- `src/erre_sandbox/integration/protocol.py`:
  - `MAX_SUBSCRIBE_ITEMS: int = 32` (DoS 防止) を追加
  - `SUBSCRIBE_DELIMITER: str = ","`

### 新規
- `tests/test_integration/test_multi_agent_stream.py`:
  - **capabilities**: handshake capabilities に dialog_* 3 種含む
  - **broadcast**: `?subscribe=` 未指定 → 全 envelope 受信 (後方互換)
  - **wildcard**: `?subscribe=*` → broadcast と同等
  - **single filter**: `?subscribe=kant` → kant 関連のみ
  - **multi filter**: `?subscribe=kant,nietzsche` → 両者の envelope
  - **isolation**: 3 client (kant / nietzsche / rikyu) で speech_kant を
    emit、kant subscriber のみ受信、nietzsche/rikyu は無視
  - **dialog routing**: DialogTurnMsg(speaker=kant, addressee=nietzsche)
    を emit、両者の subscriber が受信、rikyu は受信しない
  - **dialog_close broadcast**: DialogCloseMsg は全 subscriber が受信
  - **world_tick broadcast**: WorldTickMsg は全員受信
  - **invalid subscribe**: `?subscribe=` に MAX_SUBSCRIBE_ITEMS 超の値 →
    ErrorMsg "invalid_subscribe" で即 close
  - **variant discrimination**: dialog_* を含む全 10 variant が
    正しくパースされる

### ドキュメント
- `docs/architecture.md §Gateway`:
  - Subscription 方式 (URL query param) を記載
  - Routing table (どの envelope がどの agent_id で route されるか)
  - Capability 10 種への拡張

## envelope → 対象 agent_id の明細

| kind | routing agent_id(s) | broadcast? |
|---|---|---|
| `handshake` | — | ✅ broadcast |
| `agent_update` | `{agent_state.agent_id}` | — |
| `speech` | `{agent_id}` | — |
| `move` | `{agent_id}` | — |
| `animation` | `{agent_id}` | — |
| `world_tick` | — | ✅ broadcast |
| `error` | — | ✅ broadcast |
| `dialog_initiate` | `{initiator_agent_id, target_agent_id}` | — |
| `dialog_turn` | `{speaker_id, addressee_id}` | — |
| `dialog_close` | — | ✅ broadcast (participants 追跡なし、UI cleanup 用) |

## 影響範囲

- `Registry` のシグネチャ変更 (破壊的変更だが private な internal class、
  既存 test は `Registry` を直接 mock せず WS 経由で叩いているので regression なし)
- 既存 single-client test (broadcast 動作) は `?subscribe=` 未指定で継続 PASS
- Godot `WebSocketClient.gd` の URL はデフォルトで broadcast 維持。
  明示的に subscribe したい場合は future PR で URL 拡張
  (本タスクでは server 側のみ、Godot 側の能動的な subscribe は含めない)

## 既存パターンとの整合性

- `Registry.fan_out` の back-pressure / oldest-drop 戦略は維持
- `ws_observe` の phase machine (AWAITING_HANDSHAKE → ACTIVE → CLOSING)
  は無変更、購読読み取りは accept 直後の AWAITING_HANDSHAKE 内で処理
- URL query param の読み取りは FastAPI 標準 (`ws.query_params`)、追加依存なし
- `_parse_envelope` / `_send` / `_send_error` は無変更

## テスト戦略

### 単体テスト
- `_envelope_target_agents` の 10 variant × routing マトリクス
- `Registry.fan_out` の filter ロジック (mock queue で behaviour 検証)

### 統合テスト
- 上記 10 シナリオ (capabilities / broadcast / wildcard / single / multi /
  isolation / dialog routing / dialog_close broadcast / world_tick broadcast /
  invalid subscribe / variant discrimination)
- 既存 `test_gateway.py` の 11 件は `?subscribe=` 未指定で通ることを確認
  (= 既存期待値は broadcast モード)

## ロールバック計画

- PR revert 一発で完全復元
- subscribe 未指定で broadcast 維持のため、運用中の既存 Godot/curl は
  revert 後も継続動作

## Out of scope

- DialogScheduler 本体 → m4-multi-agent-orchestrator (#6)
- Godot 側での URL subscribe パラメタ設定 → #6 または future PR
- dialog_close の participant 追跡 (gateway-local dialog registry) → 必要性が
  出た時点で別 PR
- Per-viewer capability negotiation (client declared capabilities の尊重) →
  LAN-only の現状では過剰
- 認証・認可 → scope 外継続

## 設計判断の履歴

- 初回案 (`design-v1.md`) は broadcast 継続 + capability 定数追加のみの最小版
- `/reimagine` で v1 を破棄、v2 (URL query param ベースの server-side 購読)
  を再構築
- `design-comparison.md` で 2 案を詳細比較
- **採用: v2**
- 根拠:
  1. planning 検収条件「broadcast が per-agent に分離して届く」は server-side
     filter を要求しており、v1 ではこの要件を満たせない
  2. URL query param なら schema を触らず後方互換を維持できる
  3. 3 agent × 少数 viewer の現状でも、dialog envelope が unrelated agent
     に届くのは "最小知識" 原則に反する
  4. future の debug monitor (e.g. 特定 agent のみ watch) 実装が自然
  5. routing ロジック (`_envelope_target_agents`) を明示した方が
     後続 #6 で DialogScheduler が dialog_close participants を track
     したくなったとき、拡張点が明確
- 詳細根拠は `decisions.md`
