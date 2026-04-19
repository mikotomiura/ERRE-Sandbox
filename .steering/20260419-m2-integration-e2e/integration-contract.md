# Integration Contract (T14 gateway 向け)

機械可読な契約は以下の 2 層に分散している:

- **On-wire message types**: `src/erre_sandbox/schemas.py` §7 `ControlEnvelope`
  (T05 で凍結済み、変更は schema_version bump 必須)
- **Session lifecycle / operational params**: `src/erre_sandbox/integration/protocol.py`

本ファイルは T14 実装者 (将来の G-GEAR セッション) が
「なぜこの契約なのか」「どう実装すべきか」を読める形で説明する rational 文書。

---

## 1. WebSocket エンドポイント

### 1.1 URL パターン

```
GET /ws/observe
```

- 認証なし (ローカル LAN 内前提、予算ゼロ制約の一部)
- Query param: `agent_id` (任意、指定があればそのエージェントのみ subscribe)
- Query param: `since_tick` (任意、指定があれば過去 envelope を逐次再送)

### 1.2 HTTP → WS アップグレード時のヘッダ

アップグレードレスポンスに以下を付与:

```
X-Erre-Schema-Version: 0.1.0-m2
```

定数: `integration.protocol.SCHEMA_VERSION_HEADER`
値は `schemas.SCHEMA_VERSION` と一致させる。

### 1.3 対応するメッセージ型

`ControlEnvelope` の 7 種 (discriminator `kind`):

| kind | 方向 | 送出条件 |
|---|---|---|
| `handshake` | ↔ | 接続直後の交換 (5 秒以内) |
| `agent_update` | → | エージェント状態の bulk snapshot |
| `speech` | → | エージェント発話 |
| `move` | → | 移動指示 (Godot 側で Tween 駆動) |
| `animation` | → | アニメーション切替 |
| `world_tick` | → | heartbeat (1 秒に 1 回) |
| `error` | → | 構造化エラー応答 |

`→` は gateway → client、`↔` は双方向。M2 では client → gateway の pub は
`HandshakeMsg` のみ。

---

## 2. セッションライフサイクル

### 2.1 フェーズ遷移

```
  accept WS upgrade
        │
        ▼
  AWAITING_HANDSHAKE ──(client HandshakeMsg)──▶ ACTIVE ──(client close OR error)──▶ CLOSING ─▶ closed
        │                                                              ▲
        │ timeout > HANDSHAKE_TIMEOUT_S (5s)                          IDLE > IDLE_DISCONNECT_S (60s)
        ▼                                                              │
     ErrorMsg "handshake_timeout" → close                              │
                                                                       ▼
                                                                  ErrorMsg "idle_disconnect" → close
```

後退は起きない (reconnect は新 session として扱う)。
定数: `integration.protocol.SessionPhase`、`HANDSHAKE_TIMEOUT_S`、`IDLE_DISCONNECT_S`。

### 2.2 Handshake 交換

**Server → Client** (accept 直後):
```json
{
  "kind": "handshake",
  "schema_version": "0.1.0-m2",
  "tick": 0,
  "sent_at": "2026-04-19T10:00:00Z",
  "peer": "g-gear",
  "capabilities": ["agent_update", "speech", "move", "animation", "world_tick"]
}
```

**Client → Server** (5 秒以内):
```json
{
  "kind": "handshake",
  "schema_version": "0.1.0-m2",
  "tick": 0,
  "sent_at": "2026-04-19T10:00:00Z",
  "peer": "godot",
  "capabilities": []
}
```

`schema_version` が一致しない場合:
→ `ErrorMsg code="schema_mismatch"` を送信、session を `CLOSING` に遷移、close。

### 2.3 Active フェーズの流量

- `WorldTickMsg` が 1 秒に 1 回 (`HEARTBEAT_INTERVAL_S = 1.0`)
- `AgentUpdateMsg` は cognition cycle ごと (10 秒に 1 回のオーダー)
- `MoveMsg` / `SpeechMsg` / `AnimationMsg` はイベント駆動 (burst あり)

per-client backlog が `MAX_ENVELOPE_BACKLOG` (256) を超えた場合、
古い方から drop し `ErrorMsg code="backlog_overflow"` を警告として送出
(close はしない)。

---

## 3. エラー応答戦略

`ErrorMsg` の `code` として以下を標準化:

| code | 意味 | close するか |
|---|---|---|
| `handshake_timeout` | 5 秒以内に client Handshake 未受信 | Yes |
| `schema_mismatch` | schema_version 不一致 | Yes |
| `idle_disconnect` | 60 秒無通信 | Yes |
| `backlog_overflow` | per-client queue 超過 | No (警告) |
| `invalid_envelope` | client からの envelope が `ControlEnvelope` に parse 不能 | No (一回だけ送信、以後同内容で連発しない) |
| `internal_error` | gateway 内部例外 (詳細は `detail` に) | Yes |

### Python 側実装例 (T14 用の下地)

```python
from erre_sandbox.schemas import ErrorMsg

async def send_error(ws, code: str, detail: str) -> None:
    msg = ErrorMsg(
        tick=current_tick,
        code=code,
        detail=detail,
    )
    await ws.send_text(msg.model_dump_json())
```

---

## 4. Backpressure と Fair Scheduling

T14 実装上の推奨:

- per-client に `asyncio.Queue(maxsize=MAX_ENVELOPE_BACKLOG)` を持つ
- `WorldRuntime._envelopes` から pull した envelope を全 client の queue に fan-out
- client への書き込みは `asyncio.gather(return_exceptions=True)` で並列、
  個別 client の slow failure が他に波及しない
- close した client は queue ごと破棄

本タスクではこれらを実装しない。T14 設計フェーズで採用可否を判断。

---

## 5. T14 実装者への FAQ

### Q1. FastAPI の `WebSocket` と `websockets` どちらを使う?

A1. FastAPI 同梱の `starlette.websockets.WebSocket` を第一候補とする
(既存依存で済む)。もし独自の WS ハンドリングが必要なら `websockets` ライブラリも検討可。

### Q2. `HandshakeMsg.tick` は何を入れる?

A2. `tick=0` を固定値で入れる (handshake は tick 0 のイベントとして扱う)。
accept 時点での `WorldRuntime.current_tick` を入れる案もあるが、client 側の
シンプルさを優先。

### Q3. 未解決事項 (T14 実装時に判断)

- [ ] `WorldRuntime._envelopes` への複数 gateway subscriber の実装方式
  (fan-out strategy)
- [ ] `agent_id` query param 指定時の filtering 実装
- [ ] `since_tick` による replay 機能 (Postpone to T14 or later)
- [ ] TLS 対応 (M10 以降)
- [ ] 複数インスタンスでのロードバランシング (M9 以降)

---

## 6. 参照

- `src/erre_sandbox/schemas.py` §7 ControlEnvelope
- `src/erre_sandbox/integration/protocol.py`
- `.steering/20260418-schemas-freeze/decisions.md`
- `.steering/20260419-world-tick-zones/design.md` (envelope queue の実装)
- `.steering/20260419-m2-integration-e2e/decisions.md` D3
