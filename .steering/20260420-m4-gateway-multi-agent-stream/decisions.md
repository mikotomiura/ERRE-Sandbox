# Decisions — m4-gateway-multi-agent-stream

## D1. `/reimagine` 適用

### 判断
適用 (v1 → v2 の意図的再構築)。

### 履歴
1. `requirement.md` 記入後、v1 (broadcast 維持 + capability 追加のみ) を
   `design.md` に記入
2. v1 を `design-v1.md` に退避、意図的リセット
3. requirement.md のみを立脚点に v2 (URL query param ベースの
   server-side agent_id 購読フィルタ) を再構築
4. `design-comparison.md` で 10 観点比較
5. 採用: **v2**

### 根拠
planning 検収条件「broadcast が per-agent に分離して届く」を v1 では
物理的に満たせない。routing 方式は複数案 (broadcast / URL query / URL path /
HandshakeMsg field) があり、memory `feedback_reimagine_trigger.md` 規定対象。

---

## D2. 採用案: **v2 (URL query param `?subscribe=`)**

### 構成
- `/ws/observe?subscribe=kant,nietzsche` の URL query param で購読申告
- 未指定 / 空 / `*` → broadcast (M2 後方互換)
- server 側 `Registry.fan_out` が `_envelope_target_agents(env)` と
  突合してフィルタ

### 理由
1. planning 検収適合
2. schema (`SCHEMA_VERSION=0.2.0-m4`) を触らない = foundation 凍結維持
3. `?subscribe=` 未指定で既存 broadcast を維持 = 100% 後方互換
4. 帯域 O(N×M) → O(購読幅) に絞れる
5. debug monitor UI (`?subscribe=kant`) が自然に書ける
6. routing table が `_envelope_target_agents` の pure function として
   単体テスト可能

---

## D3. routing table の明細

### 判断
envelope kind ごとの routing 対象 agent_id を以下のように定める:

| kind | routing agent_id(s) |
|---|---|
| `handshake` | broadcast (None) |
| `agent_update` | `{agent_state.agent_id}` |
| `speech` / `move` / `animation` | `{agent_id}` |
| `world_tick` | broadcast (None) |
| `error` | broadcast (None) |
| `dialog_initiate` | `{initiator_agent_id, target_agent_id}` |
| `dialog_turn` | `{speaker_id, addressee_id}` |
| `dialog_close` | broadcast (None) — participants 追跡なし、UI cleanup 用 |

### 理由
- dialog_close は metadata のみ (dialog_id + reason) で、participants を
  wire に持たない。gateway 側で dialog_id → participants の map を
  維持するのは #6 の DialogScheduler の責務で、本タスクの scope 外
- UI 側 (Godot) は dialog_close を受けてローカルの dialog state を
  cleanup する必要があるため、購読漏れで UI が stuck する方が害大

### exhaustiveness guard
`test_every_advertised_kind_has_explicit_routing` が
`_SERVER_CAPABILITIES` の全 10 kinds に対して routing が明示されていることを
検証。新 kind 追加時に自動的にテスト失敗で検出される。

---

## D4. DoS 対策: 4 層の入力検証

### 判断
`?subscribe=` の入力検証を以下 4 段階で実施:
1. `MAX_SUBSCRIBE_RAW_LENGTH` = `32 * (64 + 1) + 1 = 2081` chars で
   raw 全体の O(1) pre-check (split 前)
2. `MAX_SUBSCRIBE_ITEMS = 32` で items 数制限
3. `MAX_SUBSCRIBE_ID_LENGTH = 64` で 1 item 長制限
4. 正規表現 `[A-Za-z0-9_-]+` で slug 形式強制
   (制御文字・ログインジェクション・パス区切り・zero-width unicode 対策)

### 理由
- security-checker MEDIUM 指摘「制御文字による log injection」への対応
- security-checker MEDIUM 指摘「split 前の事前長チェック」への対応
- persona_id は PersonaSpec で slug 形式と定義されているため、
  slug 正規表現は wire contract と一貫性がある

---

## D5. WebSocket accept ordering: invalid_subscribe でも accept 後に送信

### 判断
`?subscribe=` が不正な場合、`ws.accept()` → `send_error(invalid_subscribe)` →
`ws.close()` の順で処理。

### 理由
- WebSocket 仕様上、application-level frame (ErrorMsg) を送るには upgrade
  (accept) が完了している必要がある
- valid / invalid 両方とも accept を通るため、timing-based oracle で
  subscribe 内容を推測されない
- security-checker LOW 指摘「accept-then-error パターンの timing 漏洩有無」は
  設計上正しいと結論

### コメント追加
`gateway.py:ws_observe` の invalid_subscribe 分岐に以下のコメントを追記:
> WebSocket spec requires accept() before we can send any application
> frame, so the ErrorMsg path mirrors the valid flow: upgrade first,
> surface the error, then close. This intentionally gives the peer no
> timing-based oracle between a valid and an invalid subscribe.

---

## D6. Godot URL 変更は本 PR では行わない

### 判断
`godot_project/scripts/WebSocketClient.gd` の `ws_url` (現在
`ws://g-gear.local:8000/ws/observe`) に `?subscribe=` を付けない。

### 理由
- サーバ側 `?subscribe=` 未指定は broadcast (M2 同等) のため Godot は無変更で動く
- Godot が特定 agent だけを描画する UI は `m4-multi-agent-orchestrator` (#6)
  の責務。#4 のスコープは server 側 routing だけ
- Godot 側で subscribe 指定が必要になったら、URL パラメタ化を
  `@export` 経由で簡単に追加できる (設計上 future-proof)

---

## D7. handshake.json fixture は PR #43 で dialog_* を含めて更新済

### 判断
本 PR では `fixtures/control_envelope/handshake.json` を再度変更しない。

### 理由
- PR #43 (m4-contracts-freeze) の D8 で `capabilities` に dialog_* 3 種を
  既に追加済み
- test_envelope_fixtures.py が capabilities と `_SERVER_CAPABILITIES` の
  同期を暗黙に保証 (fixture が 10 kinds を含むため、server が 10 を
  advertise することと整合)

---

## D8. code-reviewer MEDIUM 2 (test 変数シャドーイング) への対応

### 判断
`test_subscribe_multi_agent_receives_both` の set comprehension で
`env1` がループ変数として再束縛されていた問題を修正:

```python
# before (shadowing)
assert {env1.agent_id for env1 in (env1, env2)} == {"kant", "nietzsche"}

# after (explicit)
assert isinstance(env1, SpeechMsg)
assert isinstance(env2, SpeechMsg)
assert {env1.agent_id, env2.agent_id} == {"kant", "nietzsche"}
```

### 理由
偶然正しく動作していたが可読性が悪い。set comprehension を削除し
直接 tuple で書くことで mypy narrowing も働く。

---

## D9. SUBSCRIBE_QUERY_PARAM 設計 — HandshakeMsg フィールド追加を見送った

### 判断
`HandshakeMsg` に `subscribed_agents: list[str]` field を追加する案は採用せず、
URL query param 経由にする。

### 理由
- foundation で凍結した schema を触らない (SCHEMA_VERSION bump を避ける)
- subscription は transport-level の関心事 (= routing) であり、
  application-level の wire contract ではない。URL レイヤーが自然
- HandshakeMsg に追加すると、その field を **他 peer (Godot)** が送信/処理する
  必要が出て、Godot 側の変更も誘発 (scope 膨張)
- 将来 HTTP ベースの replay API 等で同じ subscribe 指定が欲しくなったら、
  同じ `?subscribe=` が使える (URL はより汎用的)

---

## D10. `_envelope_target_agents` を pure function として分離

### 判断
routing ロジックを `Registry.fan_out` の中に埋め込まず、独立関数として
定義。`fan_out` は filter 判定だけに集中。

### 理由
- 単体テスト可能 (`TestEnvelopeTargetAgents` の 10 メソッド)
- exhaustiveness テスト (`test_every_advertised_kind_has_explicit_routing`)
  で capability list drift を機械的に捕まえる
- 将来 routing rule が増えたとき (e.g. dialog_close participants 追跡)
  関数を拡張するだけで fan_out は無変更

---

## 参照

- `requirement.md`, `design.md`, `design-v1.md`, `design-comparison.md`
- memory `feedback_reimagine_trigger.md`
- `.steering/20260420-m4-contracts-freeze/` (Dialog* variants 凍結)
- `.steering/20260419-gateway-fastapi-ws/design.md` (T14 元設計)
- `src/erre_sandbox/integration/gateway.py` / `protocol.py`
