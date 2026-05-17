# 設計 — PR-4 kant_r8_v4 DA-14 rerun verdict (local-path load)

## 実装アプローチ

v3 verdict (PR #184) で確立した pipeline (3 scripts:
`launch_sglang_plan_b.sh` / `run_plan_b_eval_sequence.sh` /
`run_plan_b_post_eval.sh`) を **v4 用に複製 + 最小差し替え** で再利用。
新規設計判断なし、変更点は以下 4 項目のみ:

1. **adapter 識別子**: `kant_r8v3` → `kant_r8v4`
2. **checkpoint path**: `kant_r8_v3/checkpoint-1500` →
   `kant_r8_v4/checkpoint-2000` (v4 best step)
3. **eval shard 出力 path**: `data/eval/m9-c-adopt-plan-b-verdict/` →
   `data/eval/m9-c-adopt-plan-b-verdict-v4/` (v3 と並列共存、forensic
   完全性のため v3 shard は **削除しない**)
4. **post-eval pipeline 出力 base directory**:
   `.steering/20260516-m9-c-adopt-plan-b-eval-gen/` →
   `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/`、全 file 名に
   `*-v4-*` suffix (`da14-verdict-plan-b-kant-v4.{json,md}` 等)

SGLang flag (`--quantization fp8` / `--max-total-tokens 2048` /
`--max-lora-rank 8` / `--disable-cuda-graph` /
`--disable-piecewise-cuda-graph` / `--mem-fraction-static 0.85`) は
v3 と同一 (Blackwell SM120 piecewise-cuda-graph workaround は
`.steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md` DR-4、fp8
16GB VRAM 制約は memory `reference_qwen3_sglang_fp8_required`、いずれも
v4 でも不変)。

## 変更対象

### 新規作成するファイル
- `scripts/m9-c-adopt/launch_sglang_plan_b_v4.sh` (v3 から複製、adapter
  identifier + checkpoint path のみ差し替え、~50 行)
- `scripts/m9-c-adopt/run_plan_b_eval_sequence_v4.sh` (v3 から複製、
  `--adapter-name kant_r8v4` + 出力 `data/eval/m9-c-adopt-plan-b-verdict-v4/`
  + 出力 file 名 `kant_r8v4_run{0,1}_stim.duckdb`、~80 行)
- `scripts/m9-c-adopt/run_plan_b_post_eval_v4.sh` (v3 から複製、SHARDS +
  GLOB を v4 path に + 全 output `*-v4-*` suffix + `--sglang-adapter
  kant_r8v4` + 出力 base directory を本 PR-4 steering directory に、
  ~130 行)
- `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/` (本 5 file)
- `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/codex-review-prompt.md`
  + `codex-review.md` (Codex review artefact)
- `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/next-session-prompt-FINAL-pr5-*.md`
  (verdict 結果で ADOPT 経路 = HF Hub push、または REJECT 経路 = rank=16
  spike retrain を生成)
- `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/sglang-v4.log`
  (SGLang launch log)
- `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/eval-sequence-v4.log`
  (eval shard 採取 log、aggregator が throughput parse に使用、本 PR で commit)
- `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/post-eval-pipeline-v4.log`
  (post-eval pipeline log、本 PR で commit)
- `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/validation-kant-r8v4.json`
  (LoRA-on shard validation)
- `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/validation-kant-planb-nolora-v4.json`
  (no-LoRA shard validation)
- `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/da14-rescore-{mpnet,e5large,lex5,bgem3}-plan-b-kant-v4.json`
  (4-encoder rescore)
- `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/tier-b-plan-b-kant-r8v4-burrows.json`
  + `tier-b-plan-b-kant-planb-nolora-v4-burrows.json` (Burrows per-condition)
- `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/tier-b-plan-b-kant-r8v4-icc.json`
  (LoRA-on ICC、no-LoRA ICC は DE-4 で skip)
- `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/da14-{burrows,icc,throughput}-plan-b-kant-v4.json`
  (axes aggregation 中間 file)
- `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/da14-verdict-plan-b-kant-v4.{json,md}`
  (本 PR の主 deliverable)

### 修正するファイル
- なし (v3 scripts は不変、v4 は新規 file で複製)

### 削除するファイル
- なし (v3 verdict shard `data/eval/m9-c-adopt-plan-b-verdict/` は
  baseline として残置)

### git 外で保持するファイル (本 PR で commit しない)
- `data/eval/m9-c-adopt-plan-b-verdict-v4/*.duckdb` (DE-3 で
  v3 と同様 git commit、~40 MB)。**ただし** 本 PR session の commit
  size 制約 (Codex review HIGH 検出能力) を踏まえ、本 PR で commit 候補
  に含めるかは pre-push 直前で再確認 (size > 50 MB なら LFS 検討、< 50 MB
  なら DE-3 踏襲)

## 影響範囲

### 直接の影響
- main の `scripts/m9-c-adopt/` に 3 file (launch / eval-sequence /
  post-eval の v4 派生) 追加
- main の `data/eval/m9-c-adopt-plan-b-verdict-v4/` に v4 eval shard
  4 file 追加 (DE-3 踏襲時、forensic 完全性のため v3 と並列共存)
- main の `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/` に
  20+ file 追加 (5 標準 file + Codex review × 2 + log × 3 + validation
  × 2 + rescore × 4 + Burrows × 2 + ICC × 1 + axes × 3 + verdict × 2 +
  PR-5 prompt × 1)
- verdict 結果が PR-5 scope を決定 (ADOPT → HF push / REJECT → rank=16)

### 間接の影響
- nietzsche / rikyu Plan B 展開は PR-4 ADOPT まで保留継続 (DA-16 DA16-1)
- PR-5 = HF push の場合、`mikotomiura/erre-kant-r8-v4-loraadapter`
  HF Hub repo が新規作成され Plan B v4 baseline として外部公開
- PR-5 = rank=16 の場合、`launch_sglang_plan_b_v5.sh` 模倣で
  `--max-lora-rank 16` VRAM fit spike が次 PR scope (fp8 16GB で rank=16
  が乗るか未検証)

### 互換性
- v3 verdict pipeline (4-encoder rescore、Burrows、ICC、aggregator、
  verdict) と完全 schema 互換 (同 invocation 形式、同 output JSON 構造)
- v4 verdict.md は v3 verdict.md と並列読み可能、追記の v3 v4 対比表
  のみ本 PR で新規

## 既存パターンとの整合性

- **DE-2 (Plan A/B verdict aggregator 分離)**: `da14_verdict_plan_b.py`
  は Plan A 用 `da15_verdict.py` と分離されており、v3/v4 で同一 script
  を使用 (引数の rescore/burrows/icc/throughput JSON path のみ差し替え)
- **DE-3 (eval shards git commit)**: ~40 MB × 4 = 想定だが v3 実測
  ~10 MB × 4 (実際は LoRA-on stim shard ~10 MB、no-LoRA stim shard
  ~10 MB)、v4 も同 scale 想定。LFS 不要、v3 と並列 commit
- **DE-4 (ICC は LoRA-on のみ)**: v3 で確立、v4 でも no-LoRA ICC は
  computation skip (gate 入力でない)
- **DE-5 (Throughput axis は eval-sequence.log から rate parse)**: v3 で
  確立、v4 でも `eval-sequence-v4.log` を `aggregate_plan_b_axes.py
  --eval-log` に渡す
- **DA16-2 (eval_loss は v3 v4 直接比較可、train_loss/学習軌道は不可)**:
  v4 verdict.md の対比表で eval_loss のみ数値比較、train_loss は v4
  内部の収束確認に限定

## テスト戦略

- 単体テスト: 該当なし (script 派生のみ、実装コード変更ゼロ)
- 統合テスト: 該当なし
- E2E テスト: post-eval pipeline 全 step PASS で実質的に E2E 担保
- **検証手段**:
  1. SGLang launch log で `Server started on http://0.0.0.0:30000` 確認
  2. 4 eval shard が ~10 MB × 4 で生成完了、validation step で
     focal-target 300 / persona kant の整合性確認
  3. 4-encoder rescore が `da14-rescore-{encoder}-plan-b-kant-v4.json`
     を生成、Plan B allowlist (`d2-encoder-allowlist-plan-b.json`) と
     SHA pinning 整合
  4. Burrows reduction% / ICC / Throughput pct を axes aggregator が
     parse 成功、`da14-verdict-plan-b-kant-v4.json` を生成
  5. verdict.md の verdict field が `ADOPT` (4-of-4 PASS or encoder
     agreement clear + 全 axes PASS) か `PHASE_E_A6` (1+ axis FAIL) で
     生成、`PASS_BY_LOWERING_GATE` 等の不正 token 出現なし (DA16-4
     thresholds 不変)
  6. v3 v4 forensic 対比表が verdict.md 末尾に追記され、eval_loss /
     per-encoder natural d / direction discipline sign-flip 解消有無を
     verbatim 表記
  7. Codex independent review で v3 v4 数値差の解釈妥当性 +
     direction discipline 評価 + PR-5 経路選択の論理性 (HIGH/MEDIUM/LOW)
  8. pre-push CI parity 4 段 (ruff format --check / ruff check /
     mypy src / pytest -q、本 PR は src/ 変更ゼロのため全 pass 想定、
     scripts/ + .steering/ + data/eval/ のみ変更)

## ロールバック計画

- v3 verdict shard `data/eval/m9-c-adopt-plan-b-verdict/` は本 PR で
  削除しないため、v4 verdict が誤っていた場合でも v3 baseline は
  独立に reference 可能
- v4 eval shard 採取は ~30 min/run × 4 で再現可能 (SGLang を v4 launch
  script で再起動 → eval-sequence script を再実行)
- post-eval pipeline は決定論的 (seed=42、bootstrap 数値も pinned)、
  万一 verdict 数値に疑義がある場合は eval shard 同じ state から
  pipeline 再実行で同一 verdict 再現可能
- v4 adapter binary 自体は local + 個別 backup (G-GEAR の WSL2
  `/root/erre-sandbox/.venv` 経路で生成されたものを Windows path
  `data/lora/m9-c-adopt-v2/kant_r8_v4/` に rsync 済、PR-3 で
  forensic JSON 4 file 取り込み済)
