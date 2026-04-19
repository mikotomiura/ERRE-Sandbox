# ACC-SESSION-COUNTER — Evidence 集

MacBook (probe) → G-GEAR gateway (`192.168.3.85:8000/health`) への LAN 側 probe と、
G-GEAR (probe) → gateway (`localhost:8000/health`) への localhost 側 probe を併記する
1Hz polling ログ。T20 M2 Acceptance の ACC-SESSION-COUNTER (GAP-3) 実測 evidence。

## ログ一覧

| 区分 | ファイル | 期間 | 観測 | 用途 |
|---|---|---|---|---|
| ベースライン | `session-counter-20260419-201315.log` | 120s | `sessions=0` 連続 (Godot 未起動) | gateway 静止時の counter 振る舞い確認 |
| ベースライン | `session-counter-20260419-201618.log` | 180s | `sessions=0` 連続 (Godot 未起動) | 同上 (長時間版) |
| 接続 (名前解決失敗) | `session-counter-connected-20260419-203405.log` | 15s | 空レスポンス (`g-gear.local` 失敗) | `.local` mDNS 不可のため直接 IP 指定に切替 |
| 接続 | `session-counter-connected-20260419-203430.log` | 5s | `sessions=1` 連続 (Godot Play 中) | 0→1 遷移の成立確認 |
| 切断直後 (graceful なし) | `session-counter-disconnected-20260419-203652.log` | 5s | `sessions=1` 継続 (Godot 停止直後) | gateway 側 close 検知遅延の観察 (ghost session) |
| 切断後遅延 / 再接続混在 | `session-counter-disconnect-delayed-20260419-203709.log` | 90s | `0` に落ちる瞬間あり → 再接続で `1` に戻る fluctuation | Godot 自動再接続ロジックが動いていた痕跡 |
| **G-GEAR 側 cycle** | `session-counter-g-gear-cycle-20260419-203900.log` | **180s 4 完全サイクル** | `1→0→1` を 4 回、disconnect から reconnect まで毎回 **5s で定常** (20:39-20:42) | G-GEAR `localhost` 側観測による auto-reconnect 強力補強 evidence |
| **定着 evidence** | `session-counter-settled-20260419-205304.log` | **90s 全て `sessions=0`** | Godot (Play + Editor) を `SIGTERM` で全停止後 | **ACC-SESSION-COUNTER の定着確認本体** |

## 観察要点

### 正常動作

- **0→1 遷移**: `connected-20260419-203430.log` で Godot 起動後 1 秒以内に `0→1` (5s 連続 `1`)
- **1→0 定着**: `settled-20260419-205304.log` で Godot 全停止後 **90s 連続 `0`**、再接続なしを確認

### 注意事項

- **graceful 停止ルート必須**: `disconnected-20260419-203652.log` では Godot Editor の Play Stop 非経由 (ユーザー側操作不在)
  のため gateway 側に ghost session が残留。WebSocket close frame が届かない場合は
  keepalive timeout 待ちになる
- **自動再接続の挙動**: `disconnect-delayed-20260419-203709.log` で `0→1→0→1...` の fluctuation を観測。
  Godot の Play プロセスが裏で走ったまま (PID 85003) だと `WebSocketClient.gd` の
  auto-reconnect が gateway を継続ノック → counter が揺れる。
  「完全停止」の判定には **`ps aux | grep godot` で Godot/Play プロセスの不在確認** が必要
- **G-GEAR 側 localhost cycle 観測** (`session-counter-g-gear-cycle-20260419-203900.log`):
  20:39-20:42 の 180s で `1→0→1` 遷移を **4 完全サイクル** 観測。`1→0` 発生後
  常に **5 秒後** に `0→1` に戻り、再接続タイミングが極めて一定。
  ログ分布は 180 サンプル中 `sessions=1` が 164 (91.1%) / `sessions=0` が 16 (8.9%) で、
  auto-reconnect の定常性を裏付ける。本 probe は G-GEAR 側 `localhost` 観測のため
  LAN 経路や Firewall の影響を排除しており、**MacBook 側 probe と観測側相補** となる

### 今回の定着手順 (再現可)

1. Godot Editor / Play Scene のプロセス PID を特定: `ps aux | grep -i godot`
2. `SIGTERM` で停止: `kill <PID>` (SIGKILL は close frame が飛ばずゴースト化しうるため非推奨)
3. 1-2 秒後に `ps aux | grep -i godot` で不在確認
4. `/health` を 1Hz で 60-90s probe → `sessions=0` 連続を確認

今回は `settled-20260419-205304.log` の通り 90 連続 `0` が観測され
**sessions=0 の定着** を evidence 化済。

## ACC-SESSION-COUNTER 格上げ内容

T20 acceptance-checklist.md の本 ACC の評価は、runbook のみから:

- runbook: `session-counter-runbook.md`
- 実測 evidence: `evidence/session-counter-settled-20260419-205304.log` (0 定着 90s)
- 補強 evidence: `evidence/session-counter-connected-20260419-203430.log` (1 成立 5s)

の **runbook + 実測 evidence** に格上げ。

## 参照

- Runbook: `.steering/20260419-m2-acceptance/session-counter-runbook.md`
- Acceptance checklist: `.steering/20260419-m2-acceptance/acceptance-checklist.md`
- GAP-3 定義: `.steering/20260419-m2-integration-e2e-execution/known-gaps.md#gap-3`
- Gateway `/health` 実装: `src/erre_sandbox/integration/gateway.py`
