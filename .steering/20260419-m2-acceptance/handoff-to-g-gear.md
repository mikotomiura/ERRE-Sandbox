# G-GEAR 側セッションへの引き継ぎ — T20 M2 Acceptance 完了後

本セッション (MacBook 側) で T20 M2 closeout の docs / steering 記録を完了した。
G-GEAR 側で **"両機" タスクの実機部分** を完遂することで T20 が formally closeout となる。

## MacBook 側で完了済 (commit `8167076`)

- [x] `docs/architecture.md` §Gateway に `_NullRuntime` debug-only 注意書き追加 (GAP-5 解消)
- [x] `.steering/20260419-m2-acceptance/session-counter-runbook.md` 新設 (GAP-3 解消: runbook 策定)
- [x] `.steering/20260419-m2-acceptance/acceptance-checklist.md` 新設 (5 ACC 全 PASS + GAP matrix + closeout 宣言)
- [x] `.steering/20260419-m2-acceptance/{requirement,design,tasklist,decisions}.md` 完備
- [x] `known-gaps.md` サマリ表に解消状態列を追加、GAP-3/5 を "✅ 解消 (T20)" にマーキング
- [x] `MASTER-PLAN.md` §4.4 に T20 closeout note + GAP-1 依存項目に `(GAP-1 → M4 待ち)` notation
- [x] `uv run pytest` 335 PASS / 17 skipped (baseline, コード変更ゼロ)
- [x] `git push origin feature/t19-macbook-godot-integration` (G-GEAR が pull 可能な状態)

## G-GEAR 側で実施すべき項目

### 1. ブランチ同期

- [ ] `git fetch origin && git checkout feature/t19-macbook-godot-integration && git pull`
- [ ] `8167076 docs(steering): T20 M2 acceptance closeout ...` が取り込まれていることを確認
- [ ] `.steering/20260419-m2-acceptance/` ディレクトリが存在することを確認

### 2. ACC-SESSION-COUNTER 実測 (optional evidence 強化) — ✅ MacBook 側で実施済 (2026-04-19 20:53 JST)

本タスクは MacBook 側で既に実施済。acceptance-checklist.md の ACC-SESSION-COUNTER は
「runbook + 実測」に格上げ完了。evidence は `.steering/20260419-m2-acceptance/evidence/`
配下 (特に `session-counter-settled-20260419-205304.log` が定着 90s ログ)。
以下 2a-2d の手順は G-GEAR 側でも独立再現する場合の参考として残す。

#### 2a. G-GEAR 側で gateway 起動

```powershell
# G-GEAR (Windows/WSL2)
cd ~/ERRE-Sand Box  # もしくは実パス
uv run python -m erre_sandbox.integration.gateway --host 0.0.0.0 --port 8000 &
```

- [ ] `curl http://localhost:8000/health` で `{"schema_version":"0.1.0-m2","status":"ok","active_sessions":0}` 確認
- [ ] Windows Firewall で port 8000 inbound が許可されていること確認

#### 2b. MacBook 側 (別ターミナル / 別端末) で 1Hz probe ループ

```bash
# MacBook
while true; do
  date +%H:%M:%S
  curl -s http://192.168.3.85:8000/health | jq -c '{sessions: .active_sessions, status}'
  sleep 1
done
```

- [ ] Godot 未起動の状態で `active_sessions: 0` が連続出力されることを確認

#### 2c. MacBook 側で Godot 起動して接続

- [ ] `godot_project/scenes/MainScene.tscn` を Play
- [ ] MacBook probe ループで `active_sessions: 0 → 1` に遷移することを視認
- [ ] Godot を停止して `1 → 0` の戻りも確認
- [ ] 実測ログ (日時 + 遷移タイムスタンプ) を抜粋保存

#### 2d. acceptance-checklist.md に実測 evidence を追記

- [ ] G-GEAR 側 (もしくは MacBook 側でも可) で
      `.steering/20260419-m2-acceptance/acceptance-checklist.md` の
      ACC-SESSION-COUNTER 行 Evidence に `session-counter-measured-{日付}.log` 等の
      実測ログ参照を追記
- [ ] 備考を「runbook 策定のみ」→「runbook + 実測 evidence 取得 (active_sessions 0→1→0 遷移確認済)」に更新

### 3. disconnect/reconnect 実機確認 (T19 保留項目)

- [ ] G-GEAR 側で gateway を停止 (`Stop-Process -Id $(Get-Content logs/gateway.pid) -Force` や
      foreground Ctrl+C)
- [ ] MacBook 側 Godot コンソールで `[WS] disconnected` が出ること確認
- [ ] 5 秒以内に `[WS] reconnecting` / 再接続試行ログが出ること確認
- [ ] G-GEAR 側で gateway を再起動
- [ ] MacBook 側 Godot が自動再接続し新 HandshakeMsg を送出することを確認
- [ ] 結果を `.steering/20260419-m2-acceptance/acceptance-checklist.md` の備考欄に追記
      (MVP 検収条件 "WS 切断で 3 秒以内自動再接続" の evidence として使える)

### 4. commit + push

上記 2d / 3 の記録を追加したら:

- [ ] `git add .steering/20260419-m2-acceptance/`
- [ ] `git commit -m "docs(steering): T20 ACC-SESSION-COUNTER 実測 + disconnect/reconnect 検証 evidence 追加"`
- [ ] `git push origin feature/t19-macbook-godot-integration`

### 5. PR 作成 → main merge → tag (運用判断)

本 T20 closeout を `main` に反映するフロー。G-GEAR / MacBook どちらからでも可。

- [ ] `gh pr create` で PR 作成
  - Title: `T19-T20 M2 closeout: MacBook live integration + acceptance checklist`
  - Body: T19 と T20 の commit をまとめた成果サマリ
- [ ] CI / レビューを通過したら main merge
- [ ] main 更新後に `git tag -a v0.1.0-m2 -m "ERRE-Sandbox M2: contract-layer integration complete (GAP-1 deferred to M4)"`
- [ ] `git push origin v0.1.0-m2`

### 6. スコープ外 (M4 以降に繰越)

以下は T20 では対応しない。M4 `gateway-multi-agent-stream` 以降で実施:

- GAP-1 full-stack orchestrator 実装 (`src/erre_sandbox/main.py` or `runtime.py`)
- ACC-SCENARIO-WALKING の Avatar 視覚移動実測
- 30Hz 描画 + WorldTickMsg 流量の実測
- GAP-2 Godot live 自動 E2E テスト → M7 検討
- GAP-4 Godot 4.6 diff 削減 → 対応しない

## 参照

- T20 acceptance checklist: `.steering/20260419-m2-acceptance/acceptance-checklist.md`
- T20 session counter runbook: `.steering/20260419-m2-acceptance/session-counter-runbook.md`
- T20 decisions (closeout only とした判断): `.steering/20260419-m2-acceptance/decisions.md`
- T19 実施記録: `.steering/20260419-m2-integration-e2e-execution/`
- MASTER-PLAN M4 セクション: `.steering/20260418-implementation-plan/MASTER-PLAN.md` §5
