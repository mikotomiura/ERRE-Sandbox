# Codex independent review prompt — PR-3 kant_r8_v4 forensic JSON commit (artifact-only)

**Scope**: artefact-only PR、実装 diff ゼロ。forensic JSON 4 file
(adapter_config / plan-b-corpus-gate / train_metadata / weight-audit) を
git に取り込み、HuggingFace Hub upload は PR-4 verdict ADOPT 確定後の
PR-5 に後送り (DP3-1)。

**Context**:
- PR #186 (DA-16 ADR、2026-05-17 merge): 候補 A 採用 (WeightedTrainer
  Blocker 2 fix → kant_r8_v4 retrain 先行)
- PR #187 (PR-2、2026-05-17 merge): `compute_weighted_causal_lm_loss` の
  reduce 式を `(l*w)/sum(w)` → `(l*w).mean()` に変更
- 2026-05-17 同 session 内で PR-2 push 直後に kant_r8_v4 retrain を WSL2
  GPU で実行、`data/lora/m9-c-adopt-v2/kant_r8_v4/` に artefact 生成完了
- **best**: `eval_loss=0.18046` @ step 2000 (v3 best 0.18259 @ step 1500
  から −0.00213 改善)
- peak VRAM: 10.09 GB、wall-clock: 2h52m

**Review focal points (HIGH/MEDIUM/LOW で報告)**:

## (a) forensic 一貫性 — train_metadata.json schema 整合性

- `data/lora/m9-c-adopt-v2/kant_r8_v4/train_metadata.json` と
  `data/lora/m9-c-adopt-v2/kant_r8_v3/train_metadata.json` を diff し、
  key set 完全一致 (新規 field 追加なし / 既存 field 削除なし) か
- v4 の主要数値 (`eval_loss=0.18046319484710693`、`best step` 経路は
  `metadata.eval_loss_at_each_checkpoint` ではなく `train_metadata.json`
  本体 + `checkpoint-2000/trainer_state.json` の組合せで判定、本 PR の
  PR description 主張と整合) が v3 と同じ schema (`weighted=true`、
  `lora_rank=8`、`max_steps=2500`、`quantization=nf4`、`seed=42`、
  `gradient_accumulation_steps=8`、`batch_size=1`) で記録されているか
- `metadata.audit_*` (de_en_mass / n_eff / top_5_pct) と
  `plan-b-corpus-gate.json` の対応する数値が一致しているか

## (b) v3 v4 eval_loss 直接比較の妥当性 (DA-16 codex-review HIGH-1 反映 verify)

- DA-16 ADR DA16-2 のトレードオフ verbatim 引用:
  > 「**eval_loss は比較可能** (Codex review HIGH-1 指摘で修正): eval
  > examples は `sample_weight=1.0` (`train_kant_lora.py:761-765`)、
  > eval batch=1 (`per_device_eval_batch_size=1`、DR-6) のため
  > 旧式 `(l[0]*1.0)/1.0 = l[0]` と新式 `(l[0]*1.0).mean() = l[0]` が
  > 数値一致する。」
- 本 PR の v4 `eval_loss=0.18046` を v3 `eval_loss=0.18259` と直接比較
  して `−0.00213 改善` と主張することが妥当か (eval pipeline で sample
  weight 適用経路 + eval batch 構成が v3 と同一であることを再確認)
- もし weighted=true 経路で eval にも weight が乗ると数値が scale 変動
  する場合、本 PR description の対比表は要修正

## (c) DP3-1 (HF push 後送り判断) の妥当性

- `decisions.md` DP3-1 verbatim 引用:
  > 「verdict 結果に依存する公開行為 (HF push) は確定後」
  > 「REJECT 時の cleanup コストゼロ」
  > 「PR-4 verdict 計算は local path 経由で adapter を load する必要あり」
- 以下のリスクが妥当に評価されているか:
  - PR-4 session マシン (G-GEAR 想定) に `adapter_model.safetensors`
    が存在することへの **single point of failure** (G-GEAR ディスク
    故障で local binary 喪失すると PR-4 verdict 計算が blocked)
  - HF Hub に v4 を push しないことで「外部研究者が v4 retrain を
    再現できない」 (本プロジェクトは個人 closed dev のため低リスク
    だが、本来 v3 が public な reason との一貫性)
  - **v3 と v4 で HF Hub push の有無が非対称** になることが結果解釈時に
    混乱を生まないか (DP3-1 は「v3 残置は当時の workflow の path-
    dependence、意図的設計ではない」と説明)
- 代替案として PR-3 内で push する案 (案 B、廃案) のトレードオフ
  (REJECT 時 cleanup) と比較して、現方針 (案 A 採用) が論理的に
  優位か

## (d) `.gitignore` で binary 機械除外の整合性

- `git check-ignore -v data/lora/m9-c-adopt-v2/kant_r8_v4/{adapter_model.
  safetensors,checkpoint-2000/optimizer.pt,checkpoint-2500/optimizer.pt,
  tokenizer.json,chat_template.jinja,README.md}` で全 binary が
  `.gitignore` の既存 pattern (v3 PR #181 時に追加された
  `data/lora/**/adapter_model.safetensors` 等) で除外されているか
- 想定 commit size は `git diff --cached --stat` で **~10 KB 以下**
  (forensic JSON 4 file + .steering 5 file)、実際の staged 状態で
  binary が混入していないか
- v3 で git に commit されている file 集合 (`adapter_config.json` /
  `plan-b-corpus-gate.json` / `train_metadata.json` /
  `weight-audit.json` の 4 file) と本 PR の v4 staged 集合が完全一致
  しているか (v3 と v4 の forensic file 構成を symmetric に保つこと
  は schema 整合性主張の前提)

**報告フォーマット (verbatim 保存)**:

- 各 focal point ごとに HIGH / MEDIUM / LOW を分類して列挙
- HIGH 0 件なら "Verdict: ADOPT-AS-IS"
- HIGH ≥ 1 件なら "Verdict: ADOPT-WITH-CHANGES" + 反映必須事項
- MEDIUM/LOW は採否を本 session で決定 (採用なら decisions.md 追記、
  不採用なら blockers.md に defer 理由付記)

**参照ファイル (Codex に Read させる)**:

- `.steering/20260517-m9-c-adopt-pr3-kant-r8-v4-retrain/requirement.md`
- `.steering/20260517-m9-c-adopt-pr3-kant-r8-v4-retrain/design.md`
- `.steering/20260517-m9-c-adopt-pr3-kant-r8-v4-retrain/decisions.md`
- `.steering/20260517-m9-c-adopt-da16-design/decisions.md` DA16-1〜DA16-4
- `.steering/20260516-m9-c-adopt-plan-b-eval-gen/decisions.md` DR-1 + DV-3
- `data/lora/m9-c-adopt-v2/kant_r8_v4/train_metadata.json`
- `data/lora/m9-c-adopt-v2/kant_r8_v3/train_metadata.json`
- `data/lora/m9-c-adopt-v2/kant_r8_v4/plan-b-corpus-gate.json`
- `data/lora/m9-c-adopt-v2/kant_r8_v4/weight-audit.json`
- `data/lora/m9-c-adopt-v2/kant_r8_v4/adapter_config.json`
- `.gitignore` (74-81 行: `data/lora/**/*` 系 pattern)
