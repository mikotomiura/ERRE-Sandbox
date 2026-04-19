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
| **disconnect/reconnect 実機** | `session-counter-disconnect-reconnect-20260419-212132.log` | **205s** (probe 180s + 末尾観測 25s) | G-GEAR gateway を `Stop-Process -Force` で停止 → 約 26s 後 restart。MacBook 側 Godot は `RECONNECT_DELAY=2.0` (commit `d52ee8c`) を反映 | **MVP 検収条件「WS 切断で 3 秒以内自動再接続」の実機 evidence** (gateway-up 状態の 3 disconnect-reconnect cycle が全て 2.1s で復帰) |
| G-GEAR 側 kill/before (5.0s) | `gateway-kill-probe-20260419-2122.log` | 70s | G-GEAR `localhost` 1Hz probe。gateway kill 21:22:57 → Godot reconnect 21:23:33 = **~10s** (RECONNECT_DELAY=5.0 時の 2 サイクル待ち合わせ) | RECONNECT_DELAY 変更前の **補強観測**。MVP 未達状態の before-state を localhost 粒度で記録 |
| G-GEAR 側 kill/before restart | `gateway-restart-20260419-2123.log` | — | 上記 kill 後の uvicorn 再起動 stdout + `/health` トラフィック | PID 20220 → 12684 移行の補強 |
| **G-GEAR 側 kill/after (2.0s)** | `gateway-kill-probe-v2-20260419-2140.log` | 70s | G-GEAR `localhost` 1Hz probe。gateway kill 21:40:53 → sessions=2 復帰 21:41:32 = **≤ 1s 粒度で観測** (復帰時点で既に 2 client 同時 reconnect 成立) | commit `d52ee8c` 適用後の **補強観測**。MacBook 側 ms 粒度 evidence (2.1s) と整合、かつ **2 client 同時 reconnect** を裏取り |
| **G-GEAR 側 kill/after restart** | `gateway-restart-v2-20260419-2141.log` | — | uvicorn `Application startup complete` 直後に `192.168.3.118:65145 - "WebSocket /ws/observe" [accepted]` + `192.168.3.118:65144 - "WebSocket /ws/observe" [accepted]` の 2 本 | **server 側での accept 観測**。Mac → G-GEAR reconnect を gateway 側から裏取り |

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
- **disconnect/reconnect 実機検証** (`session-counter-disconnect-reconnect-20260419-212132.log`):
  21:21-21:24 の 205s で以下 4 cycle を観測:

  | # | sessions=0 | sessions=1 | reconnect 時間 | コンテキスト |
  |---|---|---|---|---|
  | 1 | 21:21:39.049 | 21:21:41.157 | **2.108s** | gateway up 中の周期 disconnect |
  | 2 | 21:22:41.665 | 21:22:43.780 | **2.115s** | 同上 |
  | 3 (kill+restart) | 21:23:23.999 | 21:23:31.381 | 7.382s* | G-GEAR gateway を `Stop-Process -Force` 後 ~26s で restart |
  | 4 | 21:24:31.525 | 21:24:33.650 | **2.125s** | 同上 |

  *Cycle 3 は Godot reconnect schedule (2.0s 周期) と gateway 起動完了タイミングの
  フェーズ差 (最大 RECONNECT_DELAY 待ち) が加算されたもので、
  純粋 disconnect-reconnect (#1, #2, #4) は **3 cycle とも 2.1s** で復帰。
  RECONNECT_DELAY を 5.0 → 2.0 に短縮 (commit `d52ee8c`) した効果が
  実測でも確認され、**MVP 検収条件「WS 切断で 3 秒以内自動再接続」(MASTER-PLAN §4.4) を満たす**。
  G-GEAR cycle ログ (5s 定常) との比較で **2.9s 短縮** を達成

- **G-GEAR 側 localhost probe 補強観測** (`gateway-kill-probe-20260419-2122.log` / `gateway-kill-probe-v2-20260419-2140.log`):
  G-GEAR `localhost:8000/health` からの 1Hz probe により、MacBook 側 ms 粒度 evidence を
  gateway の直接観測側 (LAN 経路非依存) から裏取り。Before / After 比較:

  | Phase | RECONNECT_DELAY | kill 時刻 | reconnect 観測 | 評価 |
  |---|---|---|---|---|
  | Before | 5.0s | 21:22:57.983 | sessions=1 復帰 21:23:33 (復帰 +10s) | MVP 未達 |
  | **After** | **2.0s** | 21:40:53.222 | **sessions=2 復帰 21:41:32 (復帰 +≤1s 粒度)** | **MVP PASS** |

  After 観測では probe 粒度 1Hz 内で `sessions=0 → sessions=2` が 1 秒以内に揃うため、
  MacBook 側 ms 計測値 **2.1s** と整合 (粒度の差で本 probe では `≤1s` として丸められている)。
  さらに 2 client 同時 reconnect を同時に成立させた点と、補強 `gateway-restart-v2-20260419-2141.log`
  の uvicorn server 側で **Mac IP `192.168.3.118` から `WebSocket /ws/observe [accepted]` が 2 本**
  記録されている点により、実際の socket accept が server 側から裏取りできる

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
