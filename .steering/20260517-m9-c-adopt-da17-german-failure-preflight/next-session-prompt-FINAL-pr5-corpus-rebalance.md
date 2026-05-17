# Next-session 開始プロンプト — PR-5 = β corpus rebalance (rank=8 維持) + H8 pre-check

**用途**: 新セッション最初に貼り付け (下の ``` で囲まれた部分のみ)

**前提**:
- DA-17 ADR (PR-5 候補絞り込み、DA17-1〜DA17-7 + `/reimagine`) が
  **merged 済**
- DA-17 結論 = **PR-5 scope を β corpus rebalance 単独 (rank=8 維持)
  + H8 pre-check (seed-variance re-eval)** に確定
  (`.steering/20260517-m9-c-adopt-da17-german-failure-preflight/decisions.md`
  DA17-7 final 採用案)
- α (rank=16 spike) は **DEFERRED**
  (`.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/next-session-prompt-FINAL-pr5-rank16-spike-reject.md`
  に DEFERRED 注記、β failure with capacity evidence 時に α へ pivot)
- ε / γ / δ も DEFERRED (詳細は DA17-7)

**branch**: 新規 `feature/m9-c-adopt-pr5-corpus-rebalance` を **main**
から切る

**scope**:
1. **H8 pre-check** (mandatory): v4 adapter (`kant_r8_v4`) で **stim
   shard を 3 seed (0 / 100 / 1000) で再生成** + 4-encoder rescore +
   within-language d 再計算。bootstrap seed 変更 **のみ** ではなく
   **SGLang generation seed (sampling seed) を変更して utterance を
   再採取** することで真の eval generation noise を検証
2. β corpus rebalance retrain (rank=8 維持、新 adapter `kant_r8_v5_rebal`)
3. 同 verdict pipeline (4 eval shard + 4-encoder rescore + Burrows +
   ICC + axes + verdict)
4. v4 v5 forensic 対比表生成

**envelope**: ~9h (H8 ~2-3h で stim shard 3 × 再生成 + rescore、retrain
~3-5h、verdict ~3h)

**Plan mode 必須**: 本 PR-5 は corpus 設計変更を伴う高難度判断
(de_monolog coef / weight_max cap / ja mass cut の hyperparam tuning)。
Plan mode + Opus + `/reimagine` で 1 発案で確定しない。

---

```
m9-c-adopt PR-5 = β corpus rebalance (rank=8 維持) + H8 pre-check
を実行する。DA-17 ADR
(.steering/20260517-m9-c-adopt-da17-german-failure-preflight/decisions.md)
の DA17-7 final 採用案に従い、ja 38.9% silent sink (H4) + register
mismatch (H5) を corpus 側で isolated に解消する。α (rank=16 spike)
は DEFERRED、ε (prompt fix) も DEFERRED で本 PR-5 では β 単独実施。
事前に H8 (MPNet de Δ +1.50 が noise でないか) を 30min × 3 seed
spike で確認してから retrain に入る。

## 目的 (本セッション、~9h envelope)

1. DA-17 ADR (本 PR の prerequisite ADR) が main に merge 済確認
   (gh pr view <DA-17 PR 番号>)
2. `feature/m9-c-adopt-pr5-corpus-rebalance` branch (main 派生)
3. `.steering/20260517-m9-c-adopt-pr5-corpus-rebalance/` を 5 標準 file
   で起票 (Plan mode で requirement.md + design.md を確定してから
   実装開始):
   - requirement.md: "DA-17 H4/H5 を corpus 側で isolated に解消、
     PR-5 = β corpus rebalance (ja drop + de_monolog 強化、rank=8 維持)、
     pre-check = H8 seed-variance re-eval"
   - design.md: H8 pre-check 手順 + β corpus hyperparam 変更詳細 +
     retrain pipeline + verdict pipeline
   - decisions.md: DP5-1〜DP5-N を実装結果で確定
   - tasklist.md: 下記 step 4-12 を checkbox 化
   - blockers.md: 該当なしで起票

4. **H8 pre-check** (mandatory、retrain 前):
   - v4 adapter (`data/lora/m9-c-adopt-v2/kant_r8_v4/`) を local path
     で SGLang load
   - **stim shard を 3 seed で新規生成** (bootstrap seed 変更ではなく
     SGLang sampling seed = generation 段階の seed を変更して
     utterance を再採取):
     - seed=0: 新 LoRA-on shard `data/eval/h8-seed-check/kant_r8v4_seed0_run0_stim.duckdb`
       + matched no-LoRA shard `kant_planb_nolora_seed0_run0_stim.duckdb`
       (同 stim YAML、SGLang `--seed 0`)
     - seed=100: 同 seed100 (LoRA-on + no-LoRA pair)
     - seed=1000: 同 seed1000 (LoRA-on + no-LoRA pair)
     - その他 sampling params (temperature=0.60, top_p=0.85,
       repeat_penalty=1.12) は v4 verdict と同条件
   - 4-encoder rescore (**MPNet 必須**、E5/lex5/BGE-M3 optional)
   - **指標 = `mpnet_de_within_language_d`** = 各 seed の LoRA-on shard
     vs matched no-LoRA shard で `within_language.de.cohens_d`
     (rescore JSON の field、v4 verdict と同 bootstrap pipeline)
   - **判定基準** (verbatim、曖昧さ排除):
     - 3 seed 全てで `mpnet_de_within_language_d >= +1.0` → 再現 (β 続行)
     - 1 seed 以上で `mpnet_de_within_language_d <= +0.5` → noise
       確定 (β skip、本 PR-5 を「H8 棄却 ADR」に rescope、DA-18 で
       root cause 再検討)
     - **gray zone**: 3 seed が +0.5 〜 +1.0 範囲に入る場合は border-
       line、追加 seed (2000 / 3000 / 5000) を 1-2 件試行、それでも
       gray zone なら **β を保守的に続行** (eval noise が部分的に
       contribute するが root cause の一部) + DP5-1 に gray zone
       evidence を記録
   - 結果を `.steering/<dir>/decisions.md` DP5-1 に記録、HIGH 違反
     防止のため H8 結果見ずに retrain 開始しない

5. **β corpus rebalance build** (`scripts/m9-c-adopt/build_*` の改変):
   - `audit_de_en_mass` 目標 **0.85** (現 0.6010、+0.25pt)
   - **ja mass を 10% 以下** に (現 38.9% → ja_drop または severe down-
     weight; ja examples を training pool から explicit に exclude)
   - `de_monolog_coef` を **0.35 → 0.60** (Akademie-Ausgabe weight 倍増)
   - `weight_max` cap を **3.77 → 5.0** (上位 example の signal を強化)
   - その他 hyperparam (rank=8 / max_steps=2500 / save_steps=500 /
     learning_rate=2e-4 / WeightedTrainer .mean() fix) は v4 と同条件
   - new corpus build → audit JSON (`plan-b-corpus-gate.json`) で
     新 de_en_mass / n_eff / top_5_pct を確認、gate pass 確認

6. **β retrain** (`scripts/m9-c-adopt/train_plan_b_kant.sh` 経由):
   - WSL2 GPU (G-GEAR、`reference_g_gear_gpu_training_via_wsl`)
   - 新 adapter 名: `kant_r8_v5_rebal`
   - output dir: `data/lora/m9-c-adopt-v2/kant_r8_v5_rebal/`
   - 想定 wall-clock: ~3h (v4 と同 envelope、batch=1 + nf4)
   - eval_loss tracking、v4 (0.18046) との比較記録 (DA16-2 で v4 v5
     eval_loss は標準 CE として直接比較可能)

7. **β verdict pipeline** (v4 と同経路を踏襲):
   - SGLang launch (`scripts/m9-c-adopt/launch_sglang_plan_b_v4.sh` を
     v5 用に複製、adapter local path 切り替え)
   - eval shard 生成: `data/eval/m9-c-adopt-rank8-rebal-verdict/`
     - `kant_r8v5_run0_stim.duckdb`, `kant_r8v5_run1_stim.duckdb`
     - no-LoRA control は既存 v4 verdict `kant_planb_nolora_run*_stim.duckdb`
       を再利用 (同 base + 同 stim YAML なので比較可)
   - 4-encoder rescore (MPNet primary, E5/lex5 primary, BGE-M3 exploratory)
   - Burrows (`tier-b-plan-b-kant-r8v5-burrows.json`)
   - ICC + Throughput
   - aggregate: `aggregate_plan_b_axes.py` → `da14-verdict-plan-b-kant-v5.json`
     + `da14-verdict-plan-b-kant-v5.md`

8. **v4 v5 forensic 対比表** (PR-4 verdict.md と同 pattern):
   - eval_loss v4 vs v5
   - per-encoder natural d
   - within-language d (de / en)
   - Burrows reduction%
   - ICC + Throughput
   - 結論 (DA17-7 failure pivots に従う):
     - **ADOPT-clean**: kant 完了、PR-6 で HF Hub push + nietzsche /
       rikyu Plan B 展開検討
     - **ADOPT-marginal**: PR-6 で ε prompt fix spike start
     - **REJECT, de 改善あるが gate 未達**: PR-6 で α rank=16 を β
       corpus baseline 上で start
     - **REJECT, de 改善なし or en 悪化**: γ language-aware LoRA or
       δ Plan B retrospective へ shift

9. memory `project_plan_b_kant_phase_e_a6.md` 更新:
   - DA-17 ADR merged 反映
   - β corpus rebalance verdict (ADOPT or REJECT)
   - v5 eval_loss + per-language weighted mass (ja_mass の最終値)

## NOT in scope (本 PR-5)

- **α rank=16 spike** (DEFERRED、β failure 時の pivot)
- **ε prompt-side fix** (DEFERRED、β ADOPT-marginal 時の PR-6 spike)
- **γ language-aware LoRA** (DEFERRED、β / α / ε 全敗時の Plan C 候補)
- **nietzsche / rikyu Plan B 展開** (β ADOPT-clean 後)
- **DA-14 thresholds 緩和** (DA16-4 + DA17-7 binding)
- **WeightedTrainer 再修正** (PR-2 fix は frozen)
- **v3 / v4 adapter の再 retrain** (forensic 連続性破壊)

## 最初に必ず Read する file (内面化必須)

1. `.steering/20260517-m9-c-adopt-da17-german-failure-preflight/decisions.md`
   DA17-1〜DA17-7 全件 (本 PR-5 の prerequisite)
2. `.steering/20260517-m9-c-adopt-da17-german-failure-preflight/_da17_2_inspect.py`
   と `_da17_3_burrows.py` (ad-hoc 分析 script、本 PR-5 でも再利用可)
3. `.steering/20260517-m9-c-adopt-da16-design/decisions.md` DA16-1〜
   DA16-4 (順序判断 + WeightedTrainer fix 方針 + thresholds 不変)
4. `data/lora/m9-c-adopt-v2/kant_r8_v4/{train_metadata,weight-audit,plan-b-corpus-gate}.json`
   (v4 baseline forensic、v5 で比較)
5. `scripts/m9-c-adopt/build_*` (corpus build script、特に ja sample
   比率 + de_monolog coef を持つ部分。具体 file 名は session start
   時に file-finder で特定)
6. `scripts/m9-c-adopt/train_plan_b_kant.sh` + `launch_sglang_plan_b_v4.sh`
   (retrain + SGLang launch invocation)
7. `src/erre_sandbox/training/weighting.py` (WeightedExampleBuilder の
   `de_monolog_coef` / `weight_max` cap、変更対象)
8. memory `project_plan_b_kant_phase_e_a6.md` /
   `reference_g_gear_gpu_training_via_wsl` /
   `reference_qwen3_sglang_fp8_required`
9. CLAUDE.md「Plan mode 必須」「/reimagine 必須」「Codex との連携」
   「禁止事項」「Pre-push CI parity」

## 留意点 (HIGH 違反防止)

- **H8 pre-check を skip しない**: DA17-7 final 採用案の mandatory
  step、retrain 開始前に MPNet de Δ noise 確認必須。skip すると
  「結果が H8 由来か β 由来か切り分け不能」になる
- **β + ε / β + α 併用しない** (DA17-7 別案で reject 済): contribution
  切り分け不能、本 PR-5 では β 単独で実施
- **DA-14 thresholds 不変** (DA16-4 binding): 本 PR-5 でも閾値変更案は
  scope 外、提案あれば flag → reject
- **`/reimagine` 適用**: corpus hyperparam tuning (ja drop strategy、
  de_monolog coef 上げ幅、weight_max cap) は複数案ありうる、Plan mode
  内で `/reimagine` を発動して別案と比較
- **Plan mode 外で結論確定しない** (CLAUDE.md): β hyperparam の最終
  確定は Plan mode 内
- **Pre-push CI parity check** push 前に必ず実行 (CLAUDE.md +
  `feedback_pre_push_ci_parity.md`)
- **forensic JSON 連続性**: v3 / v4 / v5 で同 4-encoder + 同 stim YAML
  + 同 bootstrap n_resamples を厳守、threshold 改変なし
- **HuggingFace Hub push は ADOPT 確定後**: REJECT 時は repo 作成しない
  (DP3-1 と同方針)

## 完了条件

- [ ] DA-17 ADR merged 済確認
- [ ] `feature/m9-c-adopt-pr5-corpus-rebalance` branch (main 派生)
- [ ] Plan mode で `.steering/20260517-m9-c-adopt-pr5-corpus-rebalance/`
      5 標準 file 起票 + `/reimagine` 検討
- [ ] **H8 pre-check 完了** (MPNet de Δ × 3 seed)、結果を decisions.md
      DP5-1 に記録、H8 棄却なら本 PR-5 を rescope
- [ ] β corpus build + audit JSON (新 de_en_mass / ja_mass / n_eff /
      top_5_pct) → `decisions.md` DP5-2
- [ ] β retrain 完了 (kant_r8_v5_rebal adapter binary + eval_loss
      trajectory + checkpoint)
- [ ] β verdict pipeline 完了 (4 rescore + Burrows + ICC + verdict)
- [ ] v4 v5 forensic 対比表 → `decisions.md` DP5-3
- [ ] verdict 結論 (ADOPT-clean / ADOPT-marginal / REJECT) → `decisions.md`
      DP5-4 + next pivot 決定
- [ ] memory `project_plan_b_kant_phase_e_a6.md` 更新
- [ ] `pre-push-check.ps1` 4 段全 pass
- [ ] commit + push + `gh pr create --base main`
- [ ] Codex independent review WSL2 経由、HIGH 反映
      (特に H8 結果妥当性 + β corpus hyperparam 選択 + verdict
      解釈の論理性)。Codex CLI 401 時は PR description で defer 明示
```

---

**実施推奨タイミング**: DA-17 ADR merge 直後、~9h 連続枠でスタート可能
だが、H8 pre-check 後に retrain を始めるため 2 session に分割推奨
(H8 ~2h + retrain ~6h)。1 session 目で H8 + corpus build、2 session 目
で retrain + verdict が安全。

**Plan mode で押さえるべき判断**:

1. `/reimagine` 発動で β corpus hyperparam の別案 (ja drop の severity:
   total drop vs 10% cap vs 20% cap、de_monolog coef 0.60 vs 0.80 vs
   1.0、weight_max cap 5.0 vs 8.0 vs 10.0) を並列展開
2. 各案の expected ADOPT 確率 + eval_loss regression risk + Akademie
   over-fit risk を articulate
3. 採用案 (1 件) を decisions.md に記録 + 不採用案は defer reason 付き

**preflight ADR (DA-17) 経由で削減できた risk**:

- α rank=16 spike (~6-8h GPU) を実施した後で「言語別 effect は ja
  silent sink + register mismatch で rank 無関係」と判明する可能性を
  排除済
- corpus rebalance + rank=16 を同時実施して contribution 切り分け不能
  になる risk を排除済 (β 単独で先行)
- MPNet de Δ +1.50 が eval seed noise だった場合に β retrain 3-5h を
  無駄にする risk を H8 pre-check で削減

**PR 分割 graph (本 prompt 反映後)**:

```
DA-17 ADR (preflight、本 ADR)
  └→ **PR-5 = β corpus rebalance** ← 本 prompt
       ├→ H8 棄却 → 本 PR rescope (DA-18 root cause 再検討 ADR)
       ├→ ADOPT-clean → PR-6 = HF push + nietzsche/rikyu 展開検討
       ├→ ADOPT-marginal → PR-6 = ε prompt fix spike
       ├→ REJECT, de 改善 + gate 未達 → PR-6 = α rank=16 on β corpus
       └→ REJECT, de 改善なし or en 悪化 → PR-6 = γ or δ retrospective
```
