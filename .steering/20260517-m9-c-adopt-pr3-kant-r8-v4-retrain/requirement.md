# PR-3 — kant_r8_v4 forensic JSON commit (HF push 後送り)

## 背景

PR #186 (DA-16 ADR、2026-05-17 merge) で確定した順序 **候補 A** (WeightedTrainer
Blocker 2 fix → kant_r8_v4 retrain 先行) の第 2 段。PR #187 (PR-2、
`feature/m9-c-adopt-pr2-weighted-trainer-fix`、2026-05-17 merge) で
`compute_weighted_causal_lm_loss` の reduce 式を `.mean()` に変更、batch=1 +
grad_accum 構成で weight が gradient magnitude に直接乗るように修正。

PR-2 push 直後 (2026-05-17 同 session 内) に user authorisation で kant_r8_v4
retrain を WSL2 GPU で実行、`data/lora/m9-c-adopt-v2/kant_r8_v4/` に
artefact が生成完了:

- **adapter_model.safetensors** (30.7 MB)
- **train_metadata.json** (best `eval_loss=0.18046` @ step 2000、v3 best
  `0.18259` @ step 1500 から **−0.00213 改善**、Codex HIGH-1 反映で eval_loss は
  v3 v4 間で直接比較可能)
- **plan-b-corpus-gate.json** (DA-14 corpus gate pass: `de_en_mass=0.6010` /
  `n_eff=4358` / `top_5_pct=0.1249`)
- **weight-audit.json** (weight 分布、`weight_mean=1.0000`、`weight_max=3.77`)
- **adapter_config.json** (LoRA r=8, alpha=16, q/k/v/o_proj target)
- **checkpoint-2000** (best step) + **checkpoint-2500** (final)
- peak VRAM: **10.09 GB**、wall-clock: **2h52m**

本 PR-3 の役割は **forensic 数値のみ main に取り込む** こと。adapter binary は
DV-3 方針 (`.steering/20260516-m9-c-adopt-plan-b-eval-gen/decisions.md`) に
従い git 外で local + HuggingFace Hub に保管。**HuggingFace Hub upload は
PR-4 verdict ADOPT 確定後の PR-5 で実施** (DP3-1 で確定、REJECT 時の無駄
upload 回避 + HF Hub repo organisation を ADOPT 版に集中させる目的)。

## ゴール

- v4 retrain forensic 数値 (4 JSON file) を main に commit、PR-4 で v4
  adapter を local path 経由で load し DA-14 rerun verdict を計算できる
  状態にする
- DP3-1 (HF push 後送り) を decisions.md に記録、PR-4 verdict ADOPT
  確定後の PR-5 で「DP3-1 後送り分の HF push を実施」と明示
- PR-4 用 next-session prompt を起票、PR-5 を verdict 分岐型
  (ADOPT→HF push / REJECT→rank=16 spike retrain) で併記
- pre-push CI parity 4 段全 pass、Codex independent review HIGH 反映

## スコープ

### 含むもの
- `data/lora/m9-c-adopt-v2/kant_r8_v4/{adapter_config,plan-b-corpus-gate,
  train_metadata,weight-audit}.json` の 4 file を git commit (v3 構成と
  同一、~10 KB total)
- `.steering/20260517-m9-c-adopt-pr3-kant-r8-v4-retrain/` 5 標準 file
  起票 (本 file 含む)
- Codex independent review (WSL2 経由、PR-2 と同経路)
- PR-4 用 next-session prompt + PR-5 conditional prompt 起票
- pre-push CI parity check (4 段)
- memory `project_plan_b_kant_phase_e_a6.md` 更新

### 含まないもの
- **HuggingFace Hub upload** (DP3-1 で PR-4 ADOPT 後の PR-5 に後送り)
- kant_r8_v4 retrain の **再実行** (既存 artefact が PR-2 直後生成の
  authoritative state、再実行で seed 軌道が変動し forensic 連続性が
  壊れる)
- DA-14 rerun verdict 計算 (PR-4 scope)
- rank=16 spike retrain (PR-5 REJECT 経路 scope)
- nietzsche / rikyu Plan B 展開 (PR-4 ADOPT 後の別 ADR)

## 受け入れ条件

- [ ] PR #187 (PR-2) merged 済確認 (gh pr view)
- [ ] `feature/m9-c-adopt-pr3-kant-r8-v4-retrain` branch (main 派生) 作成
- [ ] `.steering/20260517-m9-c-adopt-pr3-kant-r8-v4-retrain/` 5 標準 file
      起票 (DP3-1 が main 設計判断)
- [ ] forensic JSON 4 file (v3 と同構成) を git commit (forensic
      JSON 単独 ~7 KB、Codex review + .steering 5 file 込みで commit
      全体 ~28 KB、Codex LOW-1 反映で wording 精緻化)
- [ ] `.gitignore` で binary 除外確認 (adapter_model.safetensors /
      checkpoint-* / tokenizer.json / chat_template.jinja / README.md)
- [ ] Codex independent review WSL2 経由、codex-review.md verbatim 保存、
      HIGH 反映、特に DP3-1 妥当性 (REJECT 時 cleanup vs PR-4 local
      path 依存リスク) を verify
- [ ] PR-4 (DA-14 rerun verdict) + PR-5 conditional (ADOPT→HF push /
      REJECT→rank=16) 用 next-session prompt 起票
- [ ] `pre-push-check.ps1` 4 段全 pass
- [ ] commit + push + `gh pr create --base main`
- [ ] memory `project_plan_b_kant_phase_e_a6.md` を PR-3 push で update

## 関連ドキュメント

- `.steering/20260517-m9-c-adopt-da16-design/decisions.md` DA16-1〜DA16-4
- `.steering/20260517-m9-c-adopt-pr2-weighted-trainer-fix/decisions.md`
  DP2-1〜DP2-5
- `.steering/20260516-m9-c-adopt-plan-b-eval-gen/decisions.md` DR-1
  (kant Plan B v3 verdict REJECT) + DV-3 (forensic JSON のみ commit)
- `.steering/20260513-m9-c-adopt/decisions.md` 横断 ADR
- memory `project_plan_b_kant_phase_e_a6.md` / `feedback_pre_push_ci_parity.md`
- CLAUDE.md「Codex との連携」「Pre-push CI parity」「禁止事項」
