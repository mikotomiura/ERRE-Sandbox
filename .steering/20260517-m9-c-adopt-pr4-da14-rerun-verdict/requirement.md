# PR-4 — kant_r8_v4 DA-14 rerun verdict (local-path load)

## 背景

PR #186 (DA-16 ADR、2026-05-17 merge) で確定した順序 **候補 A**
(WeightedTrainer Blocker 2 fix → kant_r8_v4 retrain → DA-14 rerun verdict)
の第 3 段。PR #187 (PR-2、2026-05-17 merge) で
`compute_weighted_causal_lm_loss` の reduce 式を `(l*w).mean()` に変更、
PR #188 (PR-3、2026-05-17 merge) で v4 forensic JSON 4 file (eval_loss
`0.18046` @ best step 2000、v3 `0.18259` @ best step 1500 から
**−0.00213 改善**) を main に取り込み済。

本 PR-4 は v4 adapter を SGLang に **local path 経由** (PR-3 DP3-1 で
HF push 後送り、HF Hub からの auto download は使えない) で load し、
PR-2 fix が DA-14 axes (style/diversity gate) に与える影響を verdict
として確定する。

v3 verdict (PR #184 merged) は **PHASE_E_A6** (REJECT) で direction
disagreement (MPNet −0.5264 / E5-large +0.4781 / lex5 +0.1805) が
WeightedTrainer Blocker 2 由来 (training 中に weight が無効化) と仮説。
本 PR-4 verdict で fix 後 direction が converge するか (ADOPT 経路)
あるいは rank=8 capacity 不足が支配的か (REJECT → PR-5 rank=16 spike)
を切り分ける。

## ゴール

- kant_r8_v4 adapter (checkpoint-2000) で DA-14 rerun verdict 4 axes
  (Encoder agreement / Burrows reduction% / ICC(A,1) / Throughput pct)
  を計算、`da14-verdict-plan-b-kant-v4.{json,md}` を生成
- v3 v4 forensic 対比表を verdict.md に追記 (eval_loss / per-encoder
  natural d / direction discipline sign-flip 解消有無)
- ADOPT/REJECT 判定 + PR-5 conditional next-session prompt (HF push
  or rank=16 spike) を起票
- pre-push CI parity 4 段全 pass、Codex independent review HIGH 反映
- memory `project_plan_b_kant_phase_e_a6.md` を PR-4 verdict 反映で更新

## スコープ

### 含むもの
- v4 用 SGLang launch script (`launch_sglang_plan_b_v4.sh`)、eval-sequence
  script (`run_plan_b_eval_sequence_v4.sh`)、post-eval pipeline script
  (`run_plan_b_post_eval_v4.sh`) を v3 script から派生 (adapter name +
  checkpoint path + output path 差し替えのみ)
- eval shard 4 runs 採取 (LoRA-on × 2 + no-LoRA × 2、~30 min/run × 4)
  → `data/eval/m9-c-adopt-plan-b-verdict-v4/` (v3 verdict shard と並置)
- post-eval pipeline (validation, 4-encoder rescore, Burrows × 2,
  ICC × 1 LoRA-on, axes aggregation, verdict) → 全 output を
  `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/` に `*-v4-*`
  suffix で保存
- v3 v4 forensic 対比表 (eval_loss / per-encoder d / direction discipline)
  を verdict.md に追記
- PR-5 conditional next-session prompt 2 案起票 (ADOPT 経路 + REJECT 経路)
- Codex independent review (WSL2 経由、PR-3 と同経路)
- pre-push CI parity check (4 段)
- memory `project_plan_b_kant_phase_e_a6.md` 更新

### 含まないもの
- **HuggingFace Hub upload** (DP3-1 で PR-5 ADOPT 経路で実施)
- rank=16 spike retrain (PR-5 REJECT 経路 scope)
- nietzsche / rikyu Plan B 展開 (PR-4 ADOPT 後の別 ADR)
- v4 retrain の再実行 (PR-2 後の authoritative state、再実行で seed
  軌道変動 + forensic 連続性破壊)
- DA-14 thresholds 緩和 (DA16-4 で禁止、Plan B でも v3 と同 gate を不変)
- v3 verdict shard 削除 (forensic 完全性のため `data/eval/m9-c-adopt-
  plan-b-verdict/` は残置)

## 受け入れ条件

- [x] PR #188 (PR-3) merged 済確認 (gh pr view、2026-05-17T05:52:16Z MERGED)
- [x] `feature/m9-c-adopt-pr4-da14-rerun-verdict` branch (main 派生) 作成
- [ ] `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/` 5 標準 file
      起票 (本 file 含む)
- [ ] SGLang を v4 adapter (checkpoint-2000) で launch、port 30000 ready
- [ ] eval shard 4 runs 採取 (v4 LoRA-on × 2 + no-LoRA × 2)、
      `data/eval/m9-c-adopt-plan-b-verdict-v4/` に出力
- [ ] post-eval pipeline 全 step PASS、`da14-verdict-plan-b-kant-v4.{json,md}`
      生成
- [ ] verdict 結果 ADOPT/REJECT 判定、v3 v4 forensic 対比表生成
- [ ] PR-5 用 next-session prompt 起票 (verdict 結果で ADOPT or REJECT 経路
      のいずれか)
- [ ] memory `project_plan_b_kant_phase_e_a6.md` 更新
- [ ] `pre-push-check.ps1` 4 段全 pass
- [ ] commit + push + `gh pr create --base main`
- [ ] Codex independent review WSL2 経由、codex-review.md verbatim 保存、
      HIGH 反映 (特に v3 v4 verdict 数値差の解釈妥当性 + direction
      discipline 評価 + PR-5 経路選択の論理性)

## 関連ドキュメント

- `.steering/20260517-m9-c-adopt-pr3-kant-r8-v4-retrain/decisions.md`
  DP3-1 (HF push 後送り、PR-4 が local-path 依存になる前提)
- `.steering/20260517-m9-c-adopt-da16-design/decisions.md` DA16-1〜
  DA16-4 (順序 + WeightedTrainer fix 方針 + thresholds 不変)
- `.steering/20260516-m9-c-adopt-plan-b-eval-gen/decisions.md` DR-1
  (v3 verdict REJECT 内容、direction disagreement の per-encoder d 数値)
- `.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-verdict-plan-b-kant.md`
  (v3 verdict 内容、PR-4 で v4 verdict と並列比較)
- `data/lora/m9-c-adopt-v2/kant_r8_v4/train_metadata.json` (best
  step 2000 + eval_loss 0.18046、v4 adapter local-path load)
- `scripts/m9-c-adopt/launch_sglang_plan_b.sh` + `run_plan_b_eval_sequence.sh`
  + `run_plan_b_post_eval.sh` (本 PR で v4 用に派生する parent)
- memory `project_plan_b_kant_phase_e_a6.md` / `reference_qwen3_sglang_fp8_required`
  / `reference_g_gear_gpu_training_via_wsl` / `feedback_pre_push_ci_parity`
- CLAUDE.md「Codex との連携」「Pre-push CI parity」「禁止事項」
