# Godot WS keepalive — 60s idle_disconnect ループ解消

## 背景

ζ-3 live G-GEAR run-01-zeta (2026-04-28、observation.md "Reconnect-loop
investigation") で発見された pre-existing gateway/client mismatch:

```
[WorldManager] error_reported code=idle_disconnect detail=no client frame for 60.0s
[WS] disconnected: code=1000 reason=
[WS] connecting to ws://g-gear.local:8000/ws/observe
```

- Gateway (`gateway.py:414`): `asyncio.timeout(IDLE_DISCONNECT_S = 60.0)`
  で client→server frame を待ち、タイムアウトで `idle_disconnect`
  ErrorMsg + WS close
- Gateway L407 コメント: "For M2 clients may only meaningfully send
  HandshakeMsg" — client は handshake 後何も送らない設計
- `WebSocketClient.gd` も `send_text` 呼び出しは handshake (L75) のみ、
  heartbeat / keepalive 未実装
- 結果: 60s ごとに切断 → 2s reconnect → handshake 再送 周期ループ
  (live UX で reconnect 直後 panel 状態が一瞬 reset)

ζ-3 PR #107 と独立な pre-existing issue。M2/T14 期から残っていた未実装
feature。`protocol.HEARTBEAT_INTERVAL_S = 1.0` は server→client 用と
思われ、client 側 keepalive には未使用。

## ゴール

Godot client が gateway 60s idle timeout を発火させず継続接続を維持。
1800s+ live observation で reconnect 0 件。

## スコープ

### 含むもの
- `WebSocketClient.gd` に keepalive frame 送信 path 追加
  (e.g., `HEARTBEAT_INTERVAL_S * 1.5` cadence で空 ping or
  `client_heartbeat` kind を新設)
- 必要なら `schemas.py` に `ClientHeartbeatMsg` を additive で追加
  (SCHEMA_VERSION bump 検討、wire 仕様変更のため)
- Gateway 側で keepalive frame を ack せず受け流す

### 含まないもの
- Gateway 側 timeout 値の緩和 (60s rule は意図的)
- mDNS / DNS 周りの再試行戦略
- Godot 側 reconnect logic 変更 (RECONNECT_DELAY=2.0 維持)

## 受け入れ条件

- [ ] 1800s live で `idle_disconnect` 0 件
- [ ] Reconnect 0 件 (Godot debug console)
- [ ] schema 影響なし or 必要な bump を `schemas.py` L44-49 docstring
      規約通り適用
- [ ] 既存 ε / δ / ζ run の数値再現性
- [ ] /reimagine v1+v2 並列 (heartbeat kind / 周期 / payload で複数案)

## 関連ドキュメント

- `.steering/20260426-m7-slice-zeta-live-resonance/run-01-zeta/observation.md`
  §"Reconnect-loop investigation (2026-04-28)"
- `src/erre_sandbox/integration/gateway.py:414`
- `src/erre_sandbox/integration/protocol.py:29,45`
- `godot_project/scripts/WebSocketClient.gd`
