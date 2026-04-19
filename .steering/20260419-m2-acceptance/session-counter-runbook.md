# Session Counter Runbook — ACC-SESSION-COUNTER (GAP-3)

## 目的

MacBook から G-GEAR gateway の `/health` エンドポイントの `active_sessions`
counter を probe し、Godot クライアント接続の **silent failure を検出** する。

T19 ライブ検証では「接続したはずだが gateway 側で session が成立していない」
可能性が排除できず、本 runbook で再現可能な監視手順として定着させる。

## 前提

| 項目 | 値 |
|---|---|
| G-GEAR gateway IP | `192.168.3.85` (環境による。`ip addr` で確認) |
| Gateway port | `8000` |
| Gateway schema_version | `0.1.0-m2` |
| Probe 元 | MacBook Air M4 (もしくは同 LAN 内の任意ホスト) |
| 必要ツール | `curl`, `jq` (macOS 標準外なら `brew install jq`) |

## One-liner (単発 probe)

```console
$ curl -s http://192.168.3.85:8000/health | jq .active_sessions
0
```

期待値:

| Godot 接続状態 | `active_sessions` |
|---|---|
| Godot 未起動 | `0` |
| Godot 起動・WS 接続中 | `1` 以上 |
| Godot 複数起動中 | 起動インスタンス数と一致 |

`0` のままで Godot 側コンソールが `[WS] connected` を出している場合 →
**silent failure** の疑いあり。gateway の server log で
`HandshakeMsg received` / `session ACTIVE` を確認すべき。

## 1Hz polling ループ

### macOS shell loop (watch 相当)

```bash
while true; do
  date +%H:%M:%S
  curl -s http://192.168.3.85:8000/health | jq -c '{sessions: .active_sessions, status}'
  sleep 1
done
```

出力例:

```
15:12:04
{"sessions":0,"status":"ok"}
15:12:05
{"sessions":0,"status":"ok"}
15:12:06
{"sessions":1,"status":"ok"}  ← Godot 接続成立
15:12:07
{"sessions":1,"status":"ok"}
```

### `watch` コマンドが使える環境

```bash
watch -n 1 'curl -s http://192.168.3.85:8000/health | jq'
```

## トラブルシュート

| 症状 | 疑い | 対処 |
|---|---|---|
| `curl: Failed to connect` | LAN 疎通・FW | `ping 192.168.3.85` / G-GEAR 側 uvicorn が `0.0.0.0:8000` で listen しているか確認 |
| `active_sessions: 0` なのに Godot は `[WS] connected` | handshake 未到達 | Gateway ログで `AWAITING_HANDSHAKE → ACTIVE` 遷移を確認。Godot 側で `_send_client_handshake()` が呼ばれているか |
| `schema_version` 不一致 | バージョン齟齬 | MacBook 側 `godot_project/scripts/WebSocketClient.gd` の schema 期待値を確認 |
| `status: "degraded"` | gateway 内部エラー | `logs/gateway.log` を確認 |

## 本 runbook の位置付け

- T20 `ACC-SESSION-COUNTER` の runbook 本体
- GAP-3 (known-gaps.md) の解消エビデンス
- M4 full-stack orchestrator 完成後は「接続 OK + envelope 受信 OK」を
  セットで検証するため、本 runbook は **前段の必須チェック** として継続運用

## 参照

- T19 MacBook 検証記録: `.steering/20260419-m2-integration-e2e-execution/macbook-verification.md`
- Gateway `/health` 実装: `src/erre_sandbox/integration/gateway.py`
- GAP-3 詳細: `.steering/20260419-m2-integration-e2e-execution/known-gaps.md#gap-3`
