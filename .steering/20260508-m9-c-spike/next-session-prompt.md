# Next-session handoff prompt — m9-c-spike post K-α retry

**作成**: 2026-05-09 (PR #155 K-α WSL2 retry merge 直後の context-rotation)
**前セッション成果**: PR #155 merge (origin/main HEAD = `ac40411`)
**用途**: 新セッション (G-GEAR、Auto mode 推奨、Opus) の最初の prompt
として貼り付け

---

```
m9-c-spike PR #155 (K-α WSL2 retry) を 2026-05-09 に merge 完了 (origin/main HEAD = ac40411)。
本セッションは「次に何をやるか」を decide してから実施するハンドオフセッション。

## 直近完了状態 (前セッション)
- Phase K-α retry on WSL2 — Steps 2-5 全 PASS、DB3 #1 retracted
- WSL2 + Ubuntu 22.04 LTS + CUDA toolkit 12.9 + uv venv (sglang 0.5.10.post1 / 190 packages)
  が G-GEAR 上で動作確認済 (再起動後も保持)
- mock_kant_r8 LoRA は /root/erre-sandbox/checkpoints/ + Windows checkpoints/ 両方に在る
- SGLang launch v5 invocation 確定: scratch_kalpha/step2_launch.sh 参照
  (--quantization fp8 / --lora-target-modules q_proj k_proj v_proj o_proj /
   --mem-fraction-static 0.85 / --max-total-tokens 2048 /
   --disable-cuda-graph / --max-running-requests 1)
- K-α 報告 + amendment 仕様: .steering/20260508-m9-c-spike/k-alpha-report.md

## 次タスク 3 候補 (前セッション末で整理)

A. M9-eval P3 採取の進捗確認 (G-GEAR、最有力)
   - data/eval/golden/ に kant/nietzsche/rikyu × stimulus run0-4 (.duckdb 完了形) と
     natural run0 (.duckdb.tmp、進行中?) が untracked で在る (本日 11:00 時点)
   - Phase K-β B-2 (min_examples=1000 gate) の直接 unblock 経路
   - 着手前に必須:
       1. nvidia-smi で GPU 占有状況 (run が動いていれば干渉禁止)
       2. ollama / python の process 一覧 (動いている run と PID を特定)
       3. .tmp ファイルの mtime 確認 (生きている run か stale か)
   - .steering/20260430-m9-eval-system/ + .steering/20260507-m9-eval-cooldown-readjust-adr/
     の tasklist + decisions を参照

B. B-1 (m9-individual-layer-schema-add) の起票 + 実装
   - eval_paths.py::ALLOWED_RAW_DIALOG_KEYS に individual_layer_enabled 追加
   - eval_store.py::_RAW_DIALOG_DDL_COLUMNS に同 field 追加 + bootstrap DDL
   - connect_training_view() 入口 assert + CI grep gate
   - Phase K-β B-1 unblock 経路、GPU 不要、Mac でも可
   - .steering/20260508-m9-c-spike/blockers.md §B-1 参照

C. K-α 8-mode FSM smoke 拡張 PR
   - 残り 7 mode (peripatetic/chashitsu/zazen/shu_kata/ha_deviate/ri_create/shallow)
   - WSL2 SGLang stack 再起動して回す (~30-60 min)
   - K-β unblock に直接寄与しないので value 低
   - 推奨度低

## 最初にやること

1. 上記 3 候補のどれに着手するかを user に質問せず、まず候補 A の status check
   (nvidia-smi + process 一覧 + data/eval/golden/ mtime) を実施
2. 実態が判明したら 3 候補を再評価し user に推奨を 2-3 文で提示 → user の選択待ち
3. 着手後は CLAUDE.md / 該当 Skill / start-task workflow に従う

## 参照すべき memory / docs
- MEMORY.md (auto-loaded)
- .claude/memory/reference_g_gear_host.md — WSL2 配置 + SGLang launch v5 invocation
- .steering/20260508-m9-c-spike/k-alpha-report.md — Mac side ADR adopt 待ち項目
- .steering/20260508-m9-c-spike/blockers.md — B-1 / B-2 詳細
- .steering/20260430-m9-eval-system/tasklist.md — P3 採取の Hardware allocation 表

## 注意
- main 直 push 禁止 / 50% 超セッション継続禁止 (/smart-compact)
- GPL を src/erre_sandbox/ に import 禁止 (CLAUDE.md)
- 候補 A 着手の場合、既に走っている run があれば最優先で「干渉しない」
- 候補 B 着手の場合、Mac 側との分担を意識 (master is Mac)
- 着手前に context 30% 超なら start-task → /clear → execute の handoff を検討

まず候補 A の status check から始めて。
```
