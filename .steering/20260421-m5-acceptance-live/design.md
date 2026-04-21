# 設計 — m5-acceptance-live

## 実装アプローチ

コード変更なしの **live 検証 + evidence 収集** タスク。`.steering/20260420-m4-acceptance-live/`
で確立した手順を 7 項目に拡張して踏襲する。

### 実行責務の分担

| 役割 | 実行機 | 担当項目 |
|---|---|---|
| **backend** | G-GEAR (本作業ディレクトリ) | #1 health / #2 walking / #3 FSM / #4 dialog / #7 reflection |
| **viewer** | MacBook + Godot | #5 dialog bubble / #6 ERRE mode tint |

G-GEAR 側で `uv run erre-sandbox --personas kant,nietzsche,rikyu` を起動、MacBook 側で
Godot viewer を立ち上げて `ws://g-gear.local:8000/stream` に接続する。本 task の主要
evidence 収集は G-GEAR 側で行い、MacBook 側の録画 2 件は user 作業として待機する。

### 実行ポリシー

- **rollback flag 全 ON**: `--disable-*` 系フラグは使わない (M5 完全挙動の検証)
- **`--skip-health-check` 不使用**: Ollama 稼働前提、startup で失敗するなら環境不備として即中断
- **DB path 分離**: `var/m5-live.db` を使い、M4 の `var/m4-live.db` と混ざらないようにする
- **evidence タイムスタンプ**: ファイル名に `*-YYYYMMDD-HHMMSS.{log,json,txt,mp4}` を付与
- **log level**: `--log-level debug` で ERRE 遷移 / sampling / dialog turn を詳細化

## 変更対象

### 修正するファイル

なし (コード変更なし、live 検証のみ)。

### 新規作成するファイル

- `.steering/20260421-m5-acceptance-live/acceptance.md` — 7 項目 PASS/FAIL 表 + 総括
- `.steering/20260421-m5-acceptance-live/evidence/logs/cognition-ticks-*.log`
- `.steering/20260421-m5-acceptance-live/evidence/logs/erre-transitions-*.log`
- `.steering/20260421-m5-acceptance-live/evidence/logs/sampling-trace-*.log`
- `.steering/20260421-m5-acceptance-live/evidence/logs/dialog-trace-*.log`
- `.steering/20260421-m5-acceptance-live/evidence/json/gateway-health-*.json`
- `.steering/20260421-m5-acceptance-live/evidence/db-dumps/semantic-memory-dump-*.txt`
- `.steering/20260421-m5-acceptance-live/evidence/recordings/godot-dialog-*.mp4` (MacBook 側)
- `.steering/20260421-m5-acceptance-live/evidence/recordings/godot-mode-tint-*.mp4` (MacBook 側)
- `.steering/20260421-m5-acceptance-live/README.md` — evidence 配置と再現手順

### 削除するファイル

なし。`var/m5-live.db` は dump 後に削除 or `.gitignore` で除外確認。

## 影響範囲

- コードは無変更なので回帰リスクゼロ
- 本 task merge 後、ユーザー確認を経て `v0.3.0-m5` タグを付与 (auto では打たない)
- タグ付与後に `m5-cleanup-rollback-flags` タスクで 3 flag と `_ZERO_MODE_DELTAS` を除去

## 既存パターンとの整合性

- `.steering/20260420-m4-acceptance-live/` の 5 項目手順を 7 項目に拡張
  - `acceptance.md` フォーマット踏襲
  - `evidence/{logs,json,db-dumps,recordings}/` ディレクトリ命名踏襲
  - FAIL 時の root cause 記録ポリシー踏襲
- `.steering/20260420-m5-planning/design.md` §Live Acceptance 7 項目の PASS 基準を
  そのまま採用

## テスト戦略

### baseline pytest (Step 1 で実行)

Live 検証前に `uv run pytest -q` で 658 passed / 0 failed を確認 (回帰なし)。
Live 中の失敗が本 PR merge 後の main で再現しないケースを切り分けるため。

### evidence 収集手順

#### #1 `/health`
```bash
# G-GEAR ターミナル A: orchestrator 起動 (background)
uv run erre-sandbox --personas kant,nietzsche,rikyu --db var/m5-live.db \
    --log-level debug \
    > evidence/logs/cognition-ticks-$(date +%Y%m%d-%H%M%S).log 2>&1 &

sleep 3
# ターミナル B: health probe
curl -s http://127.0.0.1:8000/health | tee evidence/json/gateway-health-$(date +%Y%m%d-%H%M%S).json
# PASS 基準: schema_version=0.3.0-m5 / HTTP 200 / active_sessions ≥ 0
```

#### #2 3-agent walking 60s
上記 cognition-ticks-*.log を 90s 以上回し続け、以下を確認:
```bash
grep -c "agent_update" evidence/logs/cognition-ticks-*.log   # ≥ 18 (3 agents × 6+ ticks)
grep -c "MoveMsg\|\"kind\": \"move\"" evidence/logs/cognition-ticks-*.log
```

#### #3 ERRE mode FSM 遷移
```bash
grep -E "ERRE mode transition|erre.*mode|FSM" evidence/logs/cognition-ticks-*.log \
    > evidence/logs/erre-transitions-$(date +%Y%m%d-%H%M%S).log
grep -E "compose_sampling|temperature|sampling_overrides" evidence/logs/cognition-ticks-*.log \
    > evidence/logs/sampling-trace-$(date +%Y%m%d-%H%M%S).log
# PASS 基準: ≥1 回の mode 遷移ログ + 遷移後 tick の sampling が delta 分シフト
```

#### #4 dialog_turn LLM 生成
```bash
grep -E "dialog_initiate|DialogTurnMsg|generate_turn|dialog_close" evidence/logs/cognition-ticks-*.log \
    > evidence/logs/dialog-trace-$(date +%Y%m%d-%H%M%S).log
# PASS 基準: initiate 後 turn_index 0, 1, 2, ... 単調増加 / N≥3 turn / close reason ∈ {timeout, exhausted}
```

#### #5, #6 Godot 録画 — **MacBook 側作業**
- MacBook で `godot_project/` を Godot 4.4 で開き、`ws://g-gear.local:8000/stream` に接続
- 60s 以上録画 (OBS / QuickTime screen recording)
- 成果物を `evidence/recordings/godot-dialog-*.mp4` / `godot-mode-tint-*.mp4` に配置
- user から録画を受け取ったら acceptance.md の該当行を PASS/FAIL 判定

#### #7 Reflection 回帰なし
```bash
sqlite3 var/m5-live.db \
    "SELECT agent_id, COUNT(*) AS rows, COUNT(origin_reflection_id) AS with_origin FROM semantic_memory GROUP BY agent_id;" \
    > evidence/db-dumps/semantic-memory-dump-$(date +%Y%m%d-%H%M%S).txt
# PASS 基準: 各 agent に row ≥ 1 + origin_reflection_id 非 NULL が 1 件以上
```

## ロールバック計画

- 本 task はコード変更なし、rollback 不要
- Live 検証で FAIL が出た場合、修正は別 task (`m5-fix-<item>-<date>`) に切り出す
- evidence 収集中に G-GEAR が crash した場合、DB (`var/m5-live.db`) を削除して再試行

## 関連する Skill

- `implementation-workflow` — 本 task は live 検証なので実装ステップは軽量
- `llm-inference` — Ollama 状態確認、VRAM 監視のコマンド参照
- `error-handling` — Live 中の Ollama 接続切れ / timeout 判定
