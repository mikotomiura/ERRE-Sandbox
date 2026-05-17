# タスクリスト — PR-4 kant_r8_v4 DA-14 rerun verdict

## 準備
- [x] PR #188 (PR-3) merged 済確認 (`gh pr list --head feature/m9-c-adopt-pr3-kant-r8-v4-retrain --state all --json mergedAt,state` → 2026-05-17T05:52:16Z MERGED)
- [x] main ブランチに切り替え + pull origin main (FF +12 file from PR-3)
- [x] `feature/m9-c-adopt-pr4-da14-rerun-verdict` branch 作成 (main 派生)
- [x] kant_r8_v4 adapter binary 存在確認
      (`C:/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v4/checkpoint-2000/`
       + `adapter_model.safetensors` 30.7 MB)

## .steering 起票
- [x] requirement.md 起票 (DP3-1 由来の local-path load 前提)
- [x] design.md 起票 (v3 pipeline 派生 + 差し替え 4 項目)
- [x] decisions.md 起票 (DP4-* は verdict 結果次第で追記、初期は番号予約のみ)
- [x] tasklist.md (本 file)
- [x] blockers.md 起票 (該当なしで template 形式)

## v4 pipeline scripts 作成
- [x] `scripts/m9-c-adopt/launch_sglang_plan_b_v4.sh` 新規
      (v3 から複製、`kant_r8v4=...kant_r8_v4/checkpoint-2000` に差し替え)
- [x] `scripts/m9-c-adopt/run_plan_b_eval_sequence_v4.sh` 新規
      (`--adapter-name kant_r8v4` + 出力 `data/eval/m9-c-adopt-plan-b-verdict-v4/`
       + 出力 file 名 `kant_r8v4_run{0,1}_stim.duckdb`、
       **Git Bash on Windows 経由起動 pattern に pivot**、WSL2 path
       解釈問題回避)
- [x] `scripts/m9-c-adopt/run_plan_b_post_eval_v4.sh` 新規
      (SHARDS=`data/eval/m9-c-adopt-plan-b-verdict-v4` +
       TASK=`.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict` +
       全 output `*-v4-*` suffix + `--sglang-adapter kant_r8v4`)

## SGLang launch + eval shard 採取
- [x] WSL2 で SGLang を v4 launch script で起動 (`kant_r8v4` adapter load 確認)
- [x] port 30000 ready 確認 (`/health` 200 OK at 15:00:22+09:00、~90 sec)
- [x] eval shard 4 runs 採取 (Git Bash on Windows nohup 起動)
- [x] 4 runs 完走確認 (~25 min 総時間、1.3 MB × 4 shard 生成、~6 min/run)
- [x] SGLang を v4 のまま保持 (post-eval ICC step で再利用、完了後 shutdown)

## post-eval pipeline 実行
- [x] `bash scripts/m9-c-adopt/run_plan_b_post_eval_v4.sh` 実行
      (~3 min、4-encoder rescore + Burrows × 2 + ICC + axes + verdict)
- [x] `da14-verdict-plan-b-kant-v4.{json,md}` 生成確認
- [x] post-eval pipeline 全 step PASS 確認 (validation × 2 + rescore × 4
      + Burrows × 2 + ICC × 1 + aggregate + verdict 全 PASS)

## verdict 判定 + v3 v4 forensic 対比
- [x] verdict.md の 4 axes 読み取り (Encoder agreement FAIL / Burrows
      reduction% FAIL `-1.5408%` / ICC(A,1) PASS `0.8768` /
      Throughput pct PASS `100.05%`)
- [x] v3 v4 forensic 対比表を verdict.md 末尾に追記
      (eval_loss `0.18259 → 0.18046` (−0.00213) / per-encoder natural d /
       direction discipline 部分解消 = E5-large `+0.48 → +0.20`)
- [x] **REJECT** 判定 (DA-16 候補 A outcome (ii) "direction converged but
      |d| 不足 → capacity 仮説、PR-5 rank=16 を推進" に該当)

## PR-5 用 next-session prompt 起票 (verdict 結果で分岐)
- [x] **REJECT 経路採用**: `next-session-prompt-FINAL-pr5-rank16-spike-reject.md`
      (rank=16 spike retrain + `--max-lora-rank 16` VRAM fit spike +
       新 adapter `kant_r16_v1` 生成、~6-8h envelope、Plan mode 必須 +
       `/reimagine` 適用検討)
- [N/A] ADOPT 経路 / borderline 経路は本 PR では発動せず

## レビュー
- [N/A] code-reviewer 起動 (本 PR は v3 pipeline script 派生のみで実装 diff
        ゼロ、Codex review で forensic 整合性を直接 verify する path を採用
        した経緯と同じ、重複削減)
- [SKIP] Codex independent review (WSL2 経由):
  - [x] codex-review-prompt.md 起票 (focal: (a) WeightedTrainer fix 部分
        効果の解釈妥当性 + (b) PR-5 経路選択論理性 + (c) Burrows +0.41 pt
        改善有意性 + (d) script 派生 forensic 一貫性 + (e) DA-14 thresholds
        不変遵守)
  - [DEFERRED] codex CLI が 401 Unauthorized で実行不能、blockers.md
        ブロッカー 1 で post-merge follow-up に defer (`codex-review.md` に
        defer 理由 + post-merge plan + 本 PR を Codex review なしで merge
        可能と判定する根拠を verbatim 保存)

## ドキュメント
- [x] PR-5 用 next-session prompt (REJECT 経路 1 案起票)
- [x] memory `project_plan_b_kant_phase_e_a6.md` 更新
      (PR-3 #188 merged 反映 + PR-4 verdict 結果 + PR-5 scope +
       direction discipline v3 v4 比較 + WeightedTrainer fix 効果 +
       Git Bash on Windows pivot の empirical 学習を pivot 知識として保存)

## CI parity + push
- [x] `pwsh scripts/dev/pre-push-check.ps1` で 4 段全 pass
      (`ruff format --check src tests` PASS / `ruff check src tests` PASS /
       `mypy src` PASS (84 files) / `pytest -q` 1513 passed + 47 skipped
       in 78.8s、本 PR は src/ 変更ゼロのため期待通り)
- [ ] git commit (HEREDOC で commit message、Co-Authored-By 付き)
- [ ] git push -u origin feature/m9-c-adopt-pr4-da14-rerun-verdict
- [ ] gh pr create --base main (PR description で v3 v4 forensic
      対比表 + verdict 結果 + PR-5 経路選択 + Codex review defer 明示)
- [ ] PR URL を user に返却

## 完了処理
- [ ] /finish-task 実行 (.steering 最終化 + 最終レビュー + commit 提案)
- [ ] 次セッションは PR-5 (rank=16 spike retrain、Plan mode 必須) を起動
