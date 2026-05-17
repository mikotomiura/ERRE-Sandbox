# Next-session 開始プロンプト — PR-5 rank=16 spike retrain (REJECT 経路、kant_r16_v1)

**用途**: 新セッション最初に貼り付け (下の ``` で囲まれた部分のみ)

**前提**:
- PR-4 (`feature/m9-c-adopt-pr4-da14-rerun-verdict`、v4 verdict =
  PHASE_E_A6 REJECT 確定) が **merged 済** であることが PR-5 起票の
  precondition。merge されていない場合は本 prompt 実行前に PR-4 を
  merge する
- DA-16 ADR の **outcome (ii)** "REJECT, direction converged but |d|
  不足 → capacity 仮説、PR-5 rank=16 を推進" 経路を採用
  (`.steering/20260517-m9-c-adopt-da16-design/decisions.md` DA16-1 verbatim)
- v4 verdict 数値根拠 (`.steering/20260517-m9-c-adopt-pr4-da14-rerun-
  verdict/da14-verdict-plan-b-kant-v4.md`):
  - WeightedTrainer fix は E5-large に部分的効果 (+0.48 → +0.20)、
    Blocker 2 実在 + 修正必要だったが、
  - rank=8 capacity 不足が支配的要因として残存 (MPNet |d| 不足、
    Burrows reduction% +0.41 pt 改善のみで依然 negative)
- v4 adapter (`data/lora/m9-c-adopt-v2/kant_r8_v4/`) は **HF Hub に push
  しない** (PR-3 DP3-1)、PR-5 = rank=16 spike pivot で v4 への HF push
  は今後も実施しない (rank=16 が ADOPT 確定したら kant_r16_v1 を push
  する別判断)

**branch**: 新規 `feature/m9-c-adopt-pr5-rank16-spike-retrain` を **main**
から切る
**scope**:
1. `--max-lora-rank 16` SGLang fp8 16GB VRAM fit spike (rank=16 が乗るか
   未検証、rank=8 で peak VRAM 10.09 GB だったので rank=16 で ~11-12 GB
   想定、fp8 quantization で 16GB に収まる見込み高)
2. rank=16 で kant retrain 実行 (`train_kant_lora.py` の `--lora-rank
   16` 経路、`.mean()` reduce 修正済の WeightedTrainer 経由、`kant_r16_v1`
   adapter 生成、~3-5h GPU envelope)
3. v4 と同経路の post-eval pipeline (4 eval shard 採取 + 4-encoder rescore
   + Burrows + ICC + axes + verdict) → `data/eval/m9-c-adopt-rank16-
   verdict/` + `.steering/20260517-m9-c-adopt-pr5-rank16-spike-retrain/`
4. v4 v5 forensic 対比表生成 (rank=8 v4 → rank=16 v5 で direction
   discipline 解消 + Burrows reduction% 改善のいずれが起きるか)
5. verdict ADOPT → kant_r16_v1 HF push + nietzsche / rikyu Plan B 展開準備、
   verdict REJECT → corpus tuning (Plan C) または Plan B 全体 retrospective
   ADR への移行
**envelope**: ~6-8h (rank=16 retrain ~3-5h + eval-sequence ~25 min + post-
eval pipeline ~3-5 min + Codex review + PR housekeeping)
**Plan mode 必須**: rank=16 spike は新規 hyperparameter (LoRA rank 拡大)
の introduction、VRAM fit が未検証、DA-16 候補 A から outcome (ii) 経路
への遷移で新規設計判断が複数発生する可能性 → 最初に Plan mode + Opus で
本 PR scope を確定する

---

```
m9-c-adopt PR-5 (rank=16 spike retrain、kant_r16_v1) を実行する。
PR-4 verdict = PHASE_E_A6 (REJECT) で WeightedTrainer fix のみでは
gate clear に至らず、DA-16 候補 A の outcome (ii) "rank=16 推進" に該当。
本 PR で rank=16 capacity expansion 単独効果を切り分ける。

## 目的 (本セッション、~6-8h envelope)

1. PR-4 (`feature/m9-c-adopt-pr4-da14-rerun-verdict`) merged 済確認
   (`gh pr view <PR#> --json mergedAt,state`)
2. `feature/m9-c-adopt-pr5-rank16-spike-retrain` branch (main 派生) 作成
3. `.steering/20260517-m9-c-adopt-pr5-rank16-spike-retrain/` を 5 標準
   file で起票 (Plan mode で requirement.md + design.md + decisions.md
   を確定してから実装)

4. **Plan mode で rank=16 設計判断を確定**:
   - rank=16 spike の hyperparameter (lora_alpha どうするか — rank=8 で
     alpha=16、rank=16 では alpha=32 が一般則だが PR-2 の reduce 式変更
     と相互作用で要検討)
   - VRAM 予算試算 (rank=8 で peak 10.09 GB、rank=16 で LoRA parameter 2x、
     gradient + optimizer state も 2x、fp8 16GB で 11-13 GB 想定、SGLang
     inference 時の `--max-lora-rank 16` で 1-2 GB 余裕あるか)
   - retrain corpus は v3/v4 と同じ (de_monolog + dialog、Plan B 設計を
     不変、capacity 切り分けに集中)
   - PR-5 verdict 4 outcome を decisions.md に pre-register:
     (i) ADOPT (全 axes PASS) → PR-6 = kant_r16_v1 HF push
     (ii) REJECT, direction converged + |d| 拡大 → Plan B 設計の他要素
          (lora target modules 拡張、corpus reweighting) へ移行
     (iii) REJECT, direction disagreement 残存 → Plan C 候補 (encoder
           swap、persona-encoder cross-evaluation) または Plan B 廃止
     (iv) eval_loss 上昇 (regression) → rank=16 + WeightedTrainer の
          相互作用、PR-2 を再評価

5. **SGLang launch script for rank=16 VRAM spike**:
   - `scripts/m9-c-adopt/launch_sglang_plan_b_v5.sh` 新規 (v4 から複製、
     `--max-lora-rank 8` → `16`、`kant_r16v1=...kant_r16_v1/checkpoint-best`
     に差し替え)
   - VRAM spike 用に rank=16 dummy adapter を別途用意するか、retrain
     完了後の checkpoint で初回 load + ready 確認

6. **rank=16 retrain 実行**:
   - `scripts/m9-c-adopt/train_plan_b_kant.sh` を rank=16 用に派生
     (`train_plan_b_kant_r16.sh`)、または既存 script の `--lora-rank` 引数
     を 16 に変更して invoke
   - 出力 path `data/lora/m9-c-adopt-v2/kant_r16_v1/` (v4 と並列、forensic
     完全性のため v4 directory は削除しない)
   - WeightedTrainer fix (PR-2 `.mean()` reduce) は v4 から引き継ぎ
   - eval examples `sample_weight=1.0` 経路で eval_loss は v3 v4 v5 全て
     直接比較可 (DA16-2 verbatim)
   - WSL2 GPU で ~3-5h、nohup で background 実行、checkpoint-best と
     train_metadata.json + plan-b-corpus-gate.json + weight-audit.json
     を生成 (forensic 4 file 揃える、PR-3 と同 schema)

7. **eval shard 採取 + post-eval pipeline 実行**:
   - `scripts/m9-c-adopt/launch_sglang_plan_b_v5.sh` で SGLang launch
     (`--max-lora-rank 16` + `kant_r16v1` adapter local-path load)
   - `scripts/m9-c-adopt/run_plan_b_eval_sequence_v5.sh` 新規派生 (
     adapter name `kant_r16v1`、出力 `data/eval/m9-c-adopt-rank16-verdict/`、
     no-LoRA control 2 runs も v5 session で再採取)
   - `scripts/m9-c-adopt/run_plan_b_post_eval_v5.sh` 新規派生 (`*-v5-*`
     suffix、出力 base directory を `.steering/20260517-m9-c-adopt-pr5-
     rank16-spike-retrain/`)

8. **v4 v5 forensic 対比表 + verdict 解釈**:
   - eval_loss v4 0.18046 → v5 X.XXXXX の Δ (rank 拡大での収束力)
   - per-encoder natural d の v4 v5 比較表 (rank 拡大で direction
     discipline が converge するか)
   - Burrows reduction% v4 −1.54% → v5 X.XX% の Δ (capacity 不足
     仮説の検証)
   - verdict 4 outcome のいずれかを decisions.md DR-1 と同じ format で
     記録、次 PR (PR-6) scope を pre-register

9. **PR-6 用 next-session prompt 起票** (verdict 結果で分岐):
   - ADOPT 経路: HF push (`mikotomiura/erre-kant-r16-v1-loraadapter`) +
     nietzsche / rikyu 展開準備
   - REJECT 経路: Plan C 候補 or Plan B 全体 retrospective ADR

10. memory `project_plan_b_kant_phase_e_a6.md` 更新:
    - PR-5 rank=16 spike 結果反映
    - WeightedTrainer fix と rank capacity の効果切り分け結論
    - 続 PR (PR-6) scope を反映

## NOT in scope (本 PR-5)

- **HuggingFace Hub upload** (PR-5 verdict ADOPT 経路で次 PR-6 = HF push、
  本 PR では skip)
- nietzsche / rikyu Plan B 展開 (PR-5 ADOPT 後の別 ADR、kant_r16_v1 が
  pre-registered の前例として確立してから)
- v4 / v3 adapter の再 retrain (v3 → PR #181、v4 → PR #187 直後、いずれも
  authoritative state)
- corpus tuning (de_monolog の再生成、Plan C 候補で別 ADR)
- DA-14 thresholds 緩和 (DA16-4 で禁止、v5 でも v3 v4 と同 gate を不変)
- lora_target_modules 拡張 (mlp 等の追加、別 PR scope)

## 最初に必ず Read する file (内面化必須)

1. `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/da14-verdict-
   plan-b-kant-v4.md` (v3 v4 forensic 対比表 + WeightedTrainer fix の
   部分効果 + PR-5 経路選択根拠)
2. `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/decisions.md`
   (DP4-* に PR-4 で記録した特殊判断、本 PR で参照)
3. `.steering/20260517-m9-c-adopt-da16-design/decisions.md` DA16-1〜
   DA16-4 (順序 + WeightedTrainer fix 方針 + thresholds 不変、本 PR でも
   DA16-4 を厳守)
4. `.steering/20260517-m9-c-adopt-pr3-kant-r8-v4-retrain/decisions.md`
   DP3-1 (HF push 後送り、rank=16 でも同 pattern 踏襲)
5. `.steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md`
   DR-4 (Blackwell SM120 piecewise-cuda-graph workaround、rank=16 でも不変)
   + DR-5 (VRAM 98% batch=1 制約、rank=16 で更に厳しくなる可能性、
   spike で確認)
6. `data/lora/m9-c-adopt-v2/kant_r8_v4/train_metadata.json` (v4 forensic
   schema reference、v5 で同 schema で揃える)
7. `scripts/m9-c-adopt/launch_sglang_plan_b_v4.sh` +
   `run_plan_b_eval_sequence_v4.sh` + `run_plan_b_post_eval_v4.sh`
   (本 PR-5 で v5 用に派生する parent)
8. memory `project_plan_b_kant_phase_e_a6.md` /
   `reference_qwen3_sglang_fp8_required` /
   `reference_g_gear_gpu_training_via_wsl` /
   `feedback_pre_push_ci_parity`
9. CLAUDE.md「Codex との連携」「Pre-push CI parity」「禁止事項」
10. `.steering/_template/` (Plan mode 開始時の 5 file template)

## 留意点 (HIGH 違反防止)

- **VRAM fit 未検証**: rank=16 spike で SGLang `--max-lora-rank 16` が
  fp8 16GB に乗らない可能性 (rank=8 で peak 10.09 GB だったが LoRA
  parameter 倍増)。Plan mode で VRAM 試算 + spike script を確定してから
  retrain 開始。乗らない場合の対応案を decisions.md に pre-register
  (max-total-tokens 削減 / mem-fraction-static 調整 / quantization
  さらに強化 等)
- **v4 v5 train_loss + 学習軌道は引き続き直接比較禁止** (DA16-2 で確定):
  WeightedTrainer 経由で gradient scale 変動。v5 train_loss trajectory は
  v5 内部での収束確認に限定
- **eval_loss は v3 v4 v5 全て直接比較可** (DA16-2): rank に依らず
  `sample_weight=1.0` + eval batch=1 で旧式 = 新式数値一致
- **v4 verdict shard / forensic を削除しない**: `data/eval/m9-c-adopt-
  plan-b-verdict-v4/` + `data/lora/m9-c-adopt-v2/kant_r8_v4/` は baseline
  として残置、v5 は別 path で並列共存
- **rank=16 でも DA-14 thresholds 不変** (DA16-4): borderline でも
  threshold 移動禁止、PR-5 REJECT 時は Plan C へ migrate する方が
  p-hacking 回避の正攻法
- **HF Hub に v5 を push しない (本 PR scope では)**: ADOPT 確定後の
  PR-6 で実施 (DP3-1 pattern 踏襲)
- **Pre-push CI parity check 抜きでの push 禁止** (CLAUDE.md 禁止事項)
- **Plan mode 必須** (CLAUDE.md 禁止事項): rank=16 spike は新規
  hyperparameter introduction、Plan mode 外で実装着手しない
- **/reimagine 検討対象**: rank=16 spike 設計は「rank 拡大 vs lora target
  modules 拡張 vs corpus 再 weighting」の複数候補ありうる設計、Plan mode
  内で `/reimagine` を発動して 1 発案で確定しないこと

## 完了条件

- [ ] PR-4 merged 済確認 (gh pr view)
- [ ] `feature/m9-c-adopt-pr5-rank16-spike-retrain` branch (main 派生)
- [ ] Plan mode で `.steering/20260517-m9-c-adopt-pr5-rank16-spike-
      retrain/` 5 標準 file 起票 (requirement.md + design.md + decisions.md
      は Plan mode で確定、`/reimagine` 適用検討)
- [ ] SGLang `--max-lora-rank 16` VRAM fit spike PASS
- [ ] rank=16 retrain 実行、`kant_r16_v1` adapter + forensic 4 JSON 生成
- [ ] eval shard 採取 (LoRA-on × 2 + no-LoRA × 2)、`data/eval/m9-c-adopt-
      rank16-verdict/` に出力
- [ ] post-eval pipeline 全 step PASS、`da14-verdict-plan-b-kant-v5.{json,md}`
      生成
- [ ] verdict 結果 ADOPT/REJECT 判定、v4 v5 forensic 対比表生成
- [ ] PR-6 用 next-session prompt 起票 (verdict 結果で ADOPT or REJECT 経路)
- [ ] memory `project_plan_b_kant_phase_e_a6.md` 更新
- [ ] `pre-push-check.ps1` 4 段全 pass
- [ ] commit + push + `gh pr create --base main`
- [ ] Codex independent review WSL2 経由、codex-review.md verbatim 保存、
      HIGH 反映 (特に rank=16 capacity expansion の効果解釈妥当性 +
      VRAM fit spike の論理性 + PR-6 経路選択の論理性)
```

---

**実施推奨タイミング**: PR-4 merge 直後、~1-2 週間以内。PR-5 完了で
PR-6 (verdict 結果で HF push or Plan C) を起動できる。

**rank=16 hyperparameter pre-spike checklist (Plan mode で確認)**:

```bash
# rank=8 v4 の VRAM peak (train_metadata.json 由来)
peak_vram_v4=10831553536  # 10.09 GB (PR-3 で commit 済)

# rank=16 想定 VRAM (LoRA parameter 倍増、optimizer state も倍増)
# 概算: 10.09 + (LoRA delta 1-2 GB) = 11-12 GB → fp8 16GB に余裕
# 実際は spike で測定、Plan mode で `--mem-fraction-static` 調整余地確認
```

**PR 分割 graph (本 prompt 反映後)**:

```
DA-16 ADR (PR #186 merged)
  └→ PR-2 (.mean() reduce、PR #187 merged)
       └→ PR-3 (v4 forensic JSON commit、PR #188 merged)
            └→ PR-4 (DA-14 rerun verdict、REJECT 確定) ← 本 prompt の前段
                 └→ PR-5 = rank=16 spike retrain ← **本 prompt**
                      ├→ ADOPT → PR-6 = kant_r16_v1 HF push +
                      │            nietzsche / rikyu 展開
                      └→ REJECT → PR-6 = Plan C 候補 (encoder swap /
                                  persona-encoder cross-eval) or
                                  Plan B retrospective ADR
```
