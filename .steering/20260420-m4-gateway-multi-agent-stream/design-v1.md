# 設計 — m4-gateway-multi-agent-stream (v1: broadcast + capabilities 拡張のみ)

> v1 は /reimagine で退避される初回案。

## 実装アプローチ

既存の `Registry.fan_out` は全 session に全 envelope を押す仕組みで動いている。
M4 は 3 agent 規模 × 少数 viewer (Godot MacBook 1 台 + debug monitor 数台)
なので、帯域は大きな問題にならない。

最小変更で受け入れ条件を満たすため:
- `_SERVER_CAPABILITIES` に dialog_* 3 kinds を追加 (7 → 10)
- `HandshakeMsg.capabilities` に dialog_* が含まれる fixtures 更新
  (fixtures/control_envelope/handshake.json は PR #43 で既に更新済)
- 購読フィルタは **導入しない**。クライアントが全 envelope を受け取って
  自前でフィルタ (GDScript 側は agent_id で dispatch 済、routing 不要)

## 変更対象

### 修正
- `src/erre_sandbox/integration/gateway.py`:
  - `_SERVER_CAPABILITIES` に `dialog_initiate`, `dialog_turn`,
    `dialog_close` を追加
- `tests/test_integration/test_multi_agent_stream.py` (新規):
  - 3 client broadcast、dialog_turn の全員配信を検証
- `docs/architecture.md §Gateway`:
  - capability 10 種を記載、routing 方式は broadcast のまま

## 影響範囲

- Registry / ws_observe 無変更
- 既存 single-client test 全件 PASS
- Godot 側の EnvelopeRouter は PR #43 で既に dialog_* 対応済

## v1 の予想される問題点

- 将来 N agent = 10 / viewer = 20 のとき帯域が O(N × M)
- 特定 agent のみを watch したい debug monitor UI が書けない
- dialog_turn で unrelated agent への配信はセキュリティ上は無害だが
  "最小権限" 原則に反する (LAN-only 前提なら実害なし)

## テスト戦略

- `test_capabilities_include_dialog`: server handshake capabilities
  が dialog_* 3 種を含む
- `test_dialog_turn_reaches_all_clients`: 3 client 接続、runtime が
  DialogTurnMsg を emit、3 client すべて受信
- `test_capability_advertisement_count_matches_10`: 総 10 kinds

## ロールバック計画

- 1 行定数変更なので revert コストゼロ

## 設計判断の履歴

- 初回案 (v1)。/reimagine で v2 を再生成後、比較する。
