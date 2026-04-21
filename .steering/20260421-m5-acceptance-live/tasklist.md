# タスクリスト — m5-acceptance-live

## 準備

- [x] `/start-task` で branch 作成 (`feature/m5-acceptance-live-evidence`)
- [x] requirement.md ドラフト + ユーザー承認
- [x] design.md に 7 項目 evidence 収集手順を記載
- [x] evidence ディレクトリ骨組み作成
      (`evidence/{logs,json,db-dumps,recordings}/`)

## Step 1: 環境プリフライト

- [x] `ollama list` で `qwen3:8b` + `nomic-embed-text` 存在確認
- [x] `nvidia-smi` で VRAM 余裕確認 (RTX 5060 Ti 16GB: 14.7 GB free)
- [x] `curl http://127.0.0.1:11434/api/tags` で Ollama 稼働確認
- [x] `uv sync --frozen` で依存同期
- [x] `uv run pytest -q` で baseline 回帰ゼロ確認 (658 passed 期待)

## Step 2: G-GEAR 側 evidence 収集

### #1 /health → schema_version=0.3.0-m5

- [x] `uv run erre-sandbox --personas kant,nietzsche,rikyu --db var/m5-live.db --log-level debug` を background 起動
- [x] 3 秒待機後 `curl http://127.0.0.1:8000/health` → `evidence/json/gateway-health-*.json`
- [x] HTTP 200 + `schema_version=0.3.0-m5` 確認

### #2 3-agent walking 60s

- [x] 起動後 90 秒以上 orchestrator を回し続ける
- [x] `agent_update` × 18+ (3 agents × 6+ cognition tick)
- [x] `MoveMsg` が各 agent から発火 (M4 同等以上)

### #3 ERRE mode FSM 遷移

- [x] `grep ERRE mode transition` で遷移ログ抽出 → `evidence/logs/erre-transitions-*.log`
- [x] `grep compose_sampling` で sampling 履歴抽出 → `evidence/logs/sampling-trace-*.log`
- [x] mode 遷移 ≥ 1 件 + 遷移後 tick の sampling delta シフトを確認

### #4 dialog_turn LLM 生成

- [x] `grep dialog_` で dialog 系ログ抽出 → `evidence/logs/dialog-trace-*.log`
- [x] initiate 1+ 件 / turn_index 0,1,2,... 単調増加 / close reason が timeout or exhausted
- [x] N ≥ 3 turn が 60 秒以内に生成されていること

### #7 Reflection 回帰なし

- [x] orchestrator 停止後 `sqlite3 var/m5-live.db` で semantic_memory dump
      → `evidence/db-dumps/semantic-memory-dump-*.txt`
- [x] 各 agent に row ≥ 1 + origin_reflection_id 非 NULL 件 ≥ 1

## Step 3: MacBook 側 evidence (user 作業待ち)

### #5 Godot dialog bubble

- [ ] MacBook で `godot_project/` を Godot 4.4 で開き、`ws://g-gear.local:8000/stream` 接続
- [ ] 60 秒以上録画 → `evidence/recordings/godot-dialog-*.mp4`
- [ ] dialog_turn_received 時に avatar 頭上に bubble 表示 / 30Hz 維持

### #6 Godot ERRE mode tint

- [ ] mode 切替タイミングで avatar material 色変化を確認
- [ ] 60 秒以上録画 → `evidence/recordings/godot-mode-tint-*.mp4`
- [ ] peripatos (淡黄) → chashitsu (淡緑) 等の遷移が目視可能

**注**: 本 task の PR は G-GEAR 側 5 項目 PASS で先行 merge する。MacBook 側 2 項目は
次セッションで user が追加録画。

## Step 4: acceptance.md 集約

- [x] 7 項目を 1 ファイル `acceptance.md` に PASS/FAIL 表で集約
- [x] FAIL 項目には root cause + 修正 PR 案 (または "deferred to M6+")
- [x] 総括 (M5 完了の可否、`v0.3.0-m5` タグ付与の user gate)

## Step 5: ドキュメント

- [x] `evidence/README.md` に evidence 配置と再現手順を記載
- [x] `var/m5-live.db` は dump 後に削除 or `.gitignore` 確認
- [x] `.gitignore` に `var/` が含まれていることを確認

## Step 6: 完了処理

- [ ] `git add` 対象ファイルを個別指定で stage
- [ ] `git commit` (Conventional Commits: `chore(steering): m5 live acceptance evidence (G-GEAR 5/7 PASS)`)
- [ ] `git push -u origin feature/m5-acceptance-live-evidence`
- [ ] `gh pr create` で PR 作成
- [ ] review → merge (user gate)
- [ ] **merge 後** (user 明示確認を受けてから): `v0.3.0-m5` タグ付与 (本 task では **打たない**)
- [ ] (optional) MacBook 側 #5 / #6 録画を follow-up commit で追加

## 制約・リマインダ

- **コード修正禁止**: FAIL 時は root cause を記録、修正は別 task
- **v0.3.0-m5 タグ auto 禁止**: user 明示確認を受けてから提案
- **rollback flag 全 ON**: `--disable-*` は使わない (M5 完全挙動の検証)
- **main 直 push 禁止**
- Live 録画ファイルが巨大な場合は git LFS 検討 (M4 acceptance で確立済であれば踏襲)
