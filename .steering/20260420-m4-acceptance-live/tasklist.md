# タスクリスト — M4 Live Validation

## 準備 (完了)
- [x] handoff を読む (M4 完了後に削除: 内容は本タスクの requirement / design / acceptance に吸収済)
- [x] live-checklist `.steering/20260420-m4-multi-agent-orchestrator/live-checklist.md` の 5 項目を把握

## Step 0: Git 同期 (完了)
- [x] `git fetch --all --prune` で M4 系ブランチを取得
- [x] `git pull --ff-only` で main を `1b7be32` に進める
- [x] `git checkout -b feature/m4-acceptance-live-evidence` で branch 作成

## Step 2: 環境プリフライト (完了)
- [x] `ollama list` で `qwen3:8b` / `nomic-embed-text` を確認
- [x] `nvidia-smi` で GPU 状態確認 (RTX 5060 Ti 16 GB)
- [x] `uv sync --frozen` 成功
- [x] `uv run pytest -q` baseline 確認 (497 passed / 26 skipped、0 failures)
- [x] handoff 期待値 503/20 との差分 6 件を Godot skip として説明

## Step 3: evidence ディレクトリ (完了)
- [x] `mkdir -p .steering/20260420-m4-acceptance-live/evidence/`
- [x] WS probe スクリプト `evidence/_stream_probe.py` 作成 (handshake + keep-alive)

## Step 4: 5 項目 evidence 収集
- [x] **#1** `/health` — `evidence/gateway-health-*.json` (schema_version=0.2.0-m4)
- [x] **#2** 3-agent walking 60s — `evidence/cognition-ticks-20260420T155354.log`
- [x] **#3** Reflection + semantic_memory — `evidence/semantic-memory-dump-20260420T155606.txt`
- [x] **#4** Dialog — `evidence/dialog-trace-20260420T161518.log` (initiate × 1 + close × 4)
- [x] **#5** Godot 3-avatar 30Hz — `evidence/godot-3avatar-20260420-1625.mp4` (MacBook commit `22841d5`, operator が fps 28-32 目視確認)

## Step 5: acceptance.md まとめ (完了)
- [x] `acceptance.md` に 5 項目の PASS/PENDING を表形式で記載
- [x] FAIL 無し (ただし #5 は PENDING)

## Step 6: FAIL 時の扱い (該当なし)
- 5 項目中 1-4 は PASS、#5 は PENDING のみ

## Step 7: commit + PR
- [x] evidence #1-#4 commit (G-GEAR local `b3b22cc`)
- [x] evidence #5 commit (MacBook `22841d5`、main merged via PR #50)
- [x] acceptance/README/tasklist の全 PASS 反映 commit
- [ ] `git push -u origin feature/m4-acceptance-live-evidence`
- [ ] `gh pr create` で PR 作成

## Step 8: v0.2.0-m4 タグ (pending、ユーザー判断)
- [ ] PR merge 後、ユーザーに `v0.2.0-m4` タグ付与の是非を確認

## Gateway / DB のクリーンアップ
- [ ] Gateway プロセスの最終停止 (MacBook #5 完了後)
- [ ] `var/m4-live.db` と `var/m4-live.db.phase1-backup` の削除
