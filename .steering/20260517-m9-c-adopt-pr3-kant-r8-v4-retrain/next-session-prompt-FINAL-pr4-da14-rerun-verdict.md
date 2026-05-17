# Next-session 開始プロンプト — PR-4 DA-14 rerun verdict (kant_r8_v4 local-path load)

**用途**: 新セッション最初に貼り付け (下の ``` で囲まれた部分のみ)

**前提**:
- PR-3 (`feature/m9-c-adopt-pr3-kant-r8-v4-retrain`、v4 forensic JSON
  commit) が **merged 済** であることが PR-4 起票の precondition。merge
  されていない場合は本 prompt 実行前に PR-3 を merge する
- v4 adapter (`data/lora/m9-c-adopt-v2/kant_r8_v4/adapter_model.safetensors`
  + `checkpoint-2000/` + `checkpoint-2500/`) が PR-4 session マシン
  (**G-GEAR 確定**: SGLang inference + Burrows compute で GPU 必須) に
  存在する必要あり (DP3-1 で HF Hub push 後送り判断のため、HF Hub からの
  auto download は使えない)
- PR-4 verdict 結果で PR-5 scope が分岐:
  - **ADOPT → PR-5 = HF Hub push** (DP3-1 後送り分の実施 +
    nietzsche / rikyu Plan B 展開準備、別 ADR で展開)
  - **REJECT → PR-5 = rank=16 spike retrain** (HF push skip、新 adapter
    `kant_r16_v1` 生成へ pivot、`.mean()` reduce 修正済の WeightedTrainer
    で rank capacity 仮説を切り分け)

**branch**: 新規 `feature/m9-c-adopt-pr4-da14-rerun-verdict` を **main** から切る
**scope**: SGLang 構成切替 → eval shard 4 runs 採取 → 4-encoder rescore +
Burrows + ICC + throughput → `aggregate_plan_b_axes.py` →
`da14_verdict_plan_b.py` → forensic JSON + verdict.md commit
**envelope**: ~3-4h (eval shard ~30 min/run × 4 + post-eval ~1-2h)
**Plan mode 任意**: 既存 pipeline (`run_plan_b_eval_sequence.sh` +
`run_plan_b_post_eval.sh`) の adapter 名 + checkpoint path 差し替えのみで
新たな設計判断なし。verdict 結果に基づく PR-5 起票時のみ Plan mode 必須

---

```
m9-c-adopt PR-4 (DA-14 rerun verdict、kant_r8_v4 local-path load) を実行する。
v4 forensic JSON は PR-3 で main に取り込み済、本 PR で v4 adapter
(local path) を SGLang に load して eval shard 採取 → DA-14 axes 計算 →
verdict 判定を行う。HuggingFace Hub upload は DP3-1 により本 PR scope 外
(PR-4 ADOPT 確定後の PR-5 で実施)。

## 目的 (本セッション、~3-4h envelope)

1. PR-3 (`feature/m9-c-adopt-pr3-kant-r8-v4-retrain`) merge 確認:
   `gh pr view <PR#> --json mergedAt,state` で MERGED 確認、未 merge なら
   user に確認
2. `feature/m9-c-adopt-pr4-da14-rerun-verdict` branch (main 派生) 作成
3. `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/` を 5 標準
   file で起票:
   - requirement.md: 「kant_r8_v4 adapter (PR-2 .mean() reduce 後 retrain)
     で DA-14 rerun verdict を計算、ADOPT/REJECT を確定」
   - design.md: SGLang 構成 (v3 から v4 adapter 名 + checkpoint-2000
     path への差し替え) + eval shard 採取 → post-eval pipeline 再実行
     経路 + DP3-1 由来の local-path load 制約
   - decisions.md: 本 PR は既存 pipeline の adapter 名差し替えのみで
     新規設計判断は基本的になし。verdict 結果が borderline (例: 4-of-4
     PASS but encoder 1 で direction discipline FAIL) 等の特殊 case で
     局所判断が発生した場合のみ追記
   - tasklist.md: 下記 step 4-10 を checkbox 化
   - blockers.md: 該当なしで起票

4. **SGLang 構成切替** (`scripts/m9-c-adopt/launch_sglang_plan_b.sh` を
   コピーして `launch_sglang_plan_b_v4.sh` を作成、または既存 file を
   in-place 編集):
   - `--lora-paths` を v4 best checkpoint に変更:
     旧: `kant_r8v3=/mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v3/checkpoint-1500`
     新: `kant_r8v4=/mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v4/checkpoint-2000`
   - 他の SGLang flag (`--quantization fp8` / `--max-total-tokens 2048` /
     `--disable-cuda-graph` / `--disable-piecewise-cuda-graph`) は v3 と
     同じ (Blackwell SM120 workaround + fp8 16GB VRAM 制約は v4 でも
     不変、reference `reference_qwen3_sglang_fp8_required` memory)
   - WSL2 から `nohup bash launch_sglang_plan_b_v4.sh > sglang-v4.log 2>&1 &`
     で起動、port 30000 で SGLang ready を確認 (~3-5 min)

5. **eval shard 4 runs 採取** (`run_plan_b_eval_sequence.sh` を v4 用に
   差し替え、または `run_plan_b_eval_sequence_v4.sh` 新規作成):
   - 出力 path を `data/eval/m9-c-adopt-plan-b-verdict-v4/` に変更
     (v3 verdict shard と並列共存させて baseline 対比可能に)
   - LoRA-on run0/run1 の `--adapter-name kant_r8v3` を `kant_r8v4` に
     変更、no-LoRA control 2 runs は変更不要 (adapter なし)
   - 出力 file 名を `kant_r8v4_run0_stim.duckdb` / `kant_r8v4_run1_stim.duckdb`
     に変更、no-LoRA は `kant_planb_nolora_run0_stim.duckdb` /
     `kant_planb_nolora_run1_stim.duckdb` を **再採取** (v3 と v4 で
     no-LoRA control は同一仕様だが、temporal control + same SGLang
     session で apples-to-apples 取得が forensic 一貫性に重要)
   - **重要**: v3 verdict shard (`data/eval/m9-c-adopt-plan-b-verdict/`)
     は **削除しない**、v4 verdict は別 path に並置
   - WSL2 で nohup 起動、~30 min/run × 4 = ~2h で完了

6. **post-eval pipeline 実行** (`run_plan_b_post_eval.sh` を v4 用に
   差し替え、または `run_plan_b_post_eval_v4.sh` 新規作成):
   - `SHARDS=data/eval/m9-c-adopt-plan-b-verdict-v4` に変更
   - `V2_SHARDS_GLOB`/`NOLORA_SHARDS_GLOB` を v4 path に変更
   - 全 output file 名 (validation, rescore × 4 encoder, Burrows × 2,
     ICC, axes JSON, verdict) を `*-v4-*` suffix で並列出力
   - 出力 base directory も `.steering/20260517-m9-c-adopt-pr4-da14-
     rerun-verdict/` に変更
   - ICC step の `--sglang-adapter kant_r8v3` を `kant_r8v4` に変更
   - 完了 ~1-2h (4-encoder rescore が bootstrap で重い、CPU 並列で
     run、GPU は ICC step のみで再利用)

7. **verdict 判定** (`da14-verdict-plan-b-kant-v4.json` + `.md` を確認):
   - 4 axes (Encoder agreement / Burrows reduction% / ICC(A,1) /
     Throughput pct) の PASS/FAIL を読み取る
   - **DA-14 thresholds は不変** (DA16-4 で確定、Plan B でも v3 と同一):
     Vendi natural d ≤ −0.5、Burrows reduction% ≥ 5pt + CI lower > 0、
     ICC ≥ 0.55、Throughput pct ≥ 70%
   - **encoder agreement axis** は 3-of-4 primary を 2+ axis PASS で
     direction discipline (sign 一致) も必要 (Plan B 固有 logic)

8. **v3 v4 forensic 対比表**を verdict.md に追記:
   - eval_loss: v3 0.18259 (best step 1500) → v4 0.18046 (best step 2000)、
     −0.00213 改善 (DA16-2 トレードオフ verbatim: eval examples は
     `sample_weight=1.0` + eval batch=1 で旧式 = 新式数値一致、直接
     比較可)
   - Per-encoder natural d の v3/v4 比較表
   - direction discipline の sign-flip 解消有無 (MPNet −, E5/lex5 + の v3
     pattern が v4 で converge するか)

9. **PR-5 用 next-session prompt を起票** (verdict 結果で分岐):

   - **ADOPT 経路 (4-of-4 PASS or encoder agreement clear):**
     - `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/next-
       session-prompt-FINAL-pr5-hf-push-adopt.md`
     - scope: DP3-1 で後送りした v4 adapter の HF Hub push (
       `mikotomiura/erre-kant-r8-v4-loraadapter` 想定 名前空間)、
       README 整備、別 ADR で nietzsche / rikyu Plan B 展開準備、
       envelope ~1-2h

   - **REJECT 経路 (1 以上の axis FAIL):**
     - `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/next-
       session-prompt-FINAL-pr5-rank16-spike-reject.md`
     - scope: rank=8 → rank=16 spike retrain (`.mean()` reduce 修正済の
       WeightedTrainer で rank capacity 仮説を切り分け)、SGLang 構成
       (`--max-lora-rank 8` → 16) の VRAM fit spike (fp8 16GB で rank=16
       が乗るか未検証、`launch_sglang_plan_b_v4.sh` 模倣で v5 launch
       script 新規)、新 adapter `kant_r16_v1` 生成、envelope ~6h

   - **borderline 経路** (例: encoder agreement 1-of-3 primary only や
     direction disagreement 残存) は ADOPT/REJECT を即決せず、本 session
     内で `decisions.md` に新規 DR を起票して user 確認 → 上記 2 経路の
     どちらか (または別 Plan C 候補) に分類して PR-5 起票

10. memory `project_plan_b_kant_phase_e_a6.md` 更新:
    - PR-4 verdict 結果 (ADOPT/REJECT) を反映
    - PR-5 scope (HF push or rank=16 spike) を反映
    - direction discipline の v3 v4 比較結果を per-encoder d 数値で記録
    - WeightedTrainer fix (PR-2 `.mean()` reduce) の効果が ADOPT 経路
      で確定 / REJECT 経路で capacity 仮説優先と切り分けが明確化したことを記録

## NOT in scope (本 PR-4)

- **HuggingFace Hub upload** (DP3-1 で PR-5 ADOPT 経路で実施)
- rank=16 spike retrain (PR-5 REJECT 経路 scope)
- nietzsche / rikyu Plan B 展開 (PR-4 ADOPT 後の別 ADR)
- v4 retrain の再実行 (PR-2 後の authoritative state、再実行で forensic
  連続性が壊れる)
- DA-14 thresholds 緩和 (DA16-4 で禁止、Plan B でも v3 と同 gate を不変)

## 最初に必ず Read する file (内面化必須)

1. `.steering/20260517-m9-c-adopt-pr3-kant-r8-v4-retrain/decisions.md`
   DP3-1 (HF push 後送り、PR-4 が local-path 依存になる前提)
2. `.steering/20260517-m9-c-adopt-da16-design/decisions.md` DA16-1〜
   DA16-4 (順序 + WeightedTrainer fix 方針 + thresholds 不変)
3. `.steering/20260516-m9-c-adopt-plan-b-eval-gen/decisions.md` DR-1
   (v3 verdict REJECT 内容、direction disagreement の per-encoder d 数値)
4. `data/lora/m9-c-adopt-v2/kant_r8_v4/train_metadata.json` (best
   step 2000 + eval_loss 0.18046、PR-4 で SGLang adapter として load)
5. `scripts/m9-c-adopt/launch_sglang_plan_b.sh` + `run_plan_b_eval_sequence.sh`
   + `run_plan_b_post_eval.sh` (本 PR で v4 用に差し替える対象)
6. `.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-verdict-plan-b-kant.md`
   (v3 verdict 内容、PR-4 で v4 verdict と並列比較)
7. memory `project_plan_b_kant_phase_e_a6.md` /
   `reference_qwen3_sglang_fp8_required` /
   `reference_g_gear_gpu_training_via_wsl` /
   `feedback_pre_push_ci_parity`
8. CLAUDE.md「Codex との連携」「Pre-push CI parity」「禁止事項」

## 留意点 (HIGH 違反防止)

- **v3 verdict shard を削除しない**: `data/eval/m9-c-adopt-plan-b-verdict/`
  は v3 baseline として残置、v4 verdict は `*-v4` directory + suffix で
  並列共存させる (forensic 完全性)
- **v4 adapter を再 retrain しない**: PR-2 直後生成の authoritative
  state、再実行で seed 軌道変動 + forensic 連続性破壊
- **HF Hub に v4 を push しない (本 PR scope では)**: DP3-1 で PR-5 ADOPT
  経路で実施。本 PR で push してしまうと REJECT 時の repo cleanup が必要
- **DA-14 thresholds 不変** (DA16-4): borderline でも threshold 移動禁止、
  PR-5 (REJECT 時 rank=16 / ADOPT 時 HF push) で別 axis を試す方が p-hacking
  回避の正攻法
- **v3 v4 train_loss + 学習軌道の直接比較は禁止** (DA16-2): step pace +
  best step 位置 + train_loss absolute value は weighted gradient で scale
  変動。v4 best_step=2000 vs v3 best_step=1500 の差は「収束遅れ」ではなく
  「weighted gradient で更に signal 抽出できた」と解釈
- **v3 v4 eval_loss 直接比較は OK** (DA16-2): eval examples は
  `sample_weight=1.0` + eval batch=1 で旧式 = 新式数値一致
- **Pre-push CI parity check 抜きでの push 禁止** (CLAUDE.md 禁止事項)

## 完了条件

- [ ] PR-3 merged 済確認 (gh pr view)
- [ ] `feature/m9-c-adopt-pr4-da14-rerun-verdict` branch (main 派生) 作成
- [ ] `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/` 5 標準 file
      起票
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
```

---

**実施推奨タイミング**: PR-3 merge 直後、~1 週間以内。PR-4 完了で PR-5
(verdict 結果で HF push or rank=16 spike) を起動できる。

**v4 adapter local-path load 確認 (本 PR-4 開始前)**:

```bash
# G-GEAR session で v4 adapter binary 存在確認 (PR-3 で commit していないため)
ls -la /mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v4/checkpoint-2000/
# 期待 file:
#   adapter_config.json / adapter_model.safetensors / optimizer.pt /
#   rng_state.pth / scheduler.pt / trainer_state.json / training_args.bin
```

もし checkpoint-2000 が **存在しない** (例: G-GEAR ディスク 故障 + rsync
backup なし) なら、retrain 再実行 (~3h GPU) が必要。ただし PR-2 後の seed
軌道とは厳密一致しない可能性 (deterministic 想定だが retrain 環境の
non-deterministic 要因が残る) ため、PR-4 を blocker 化して別 ADR で対応
判断する。

**PR 分割 graph (本 prompt 反映後)**:

```
DA-16 ADR (PR #186 merged)
  └→ PR-2 (.mean() reduce、PR #187 merged)
       └→ PR-3 (v4 forensic JSON commit、HF push なし、PR #xxx merged) ← 本 prompt の前段
            └→ PR-4 (DA-14 rerun verdict、local path load) ← **本 prompt**
                 ├→ ADOPT → PR-5 = HF Hub push (DP3-1 後送り分実施)
                 │            → nietzsche / rikyu Plan B 展開 (別 ADR)
                 └→ REJECT → PR-5 = rank=16 spike retrain (HF push skip)
```
