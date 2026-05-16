# V1 設計 — Plan B (Candidate C targeted hybrid retrain) by primary agent

> **status**: 初回案。本案は意図的に discard し、V2 を Task tool subagent
> dispatch で independent 生成。V1 / V2 / hybrid 採用判定は decisions.md
> DI-1 に記録。

## 実装アプローチ

### 1. de-focused monolog collector (Plan B-2 driver)

**問題**: 既存 5022 examples で de 比率 15.9%、その中の連続 2-turn Kant
pair は推定 ~40-60 examples。B-1 (cheap filter) では target 250+ 不足。
B-2 で新規 collector を実装し、de-biased stimulus + monolog/long-form
prompt + ≥60 token filter で 250-500 examples 採取する。

**driver の構造** (`scripts/m9-c-adopt/de_focused_monolog_collector.py`):
- `tier_b_pilot.py` の SGLang chat client + DuckDB sink を base に流用
- generation-side prompt の **de bias 強化**:
  - system_prompt に "Antworte ausschließlich auf Deutsch im monologischen
    Stil. Schreibe in langer reflexiver Form (≥60 Tokens), als sprächest du
    zu dir selbst." を追加 (existing system_prompt 末尾に append)
  - user_prompt は de-only stimulus battery
    (`golden/stimulus/kant_de_focused.yaml` 新規) を使用
- **monolog mode**: `addressee_persona_id=None` (no interlocutor)
- **single-turn**: `multi_turn_max=1` (DA-11 single-turn pattern)
- **token filter**: 採取後の post-filter で token_count < 60 を drop
- **temperature schedule**: temperature ∈ {0.6, 0.8, 1.0} × 3 cycle で
  diversity 確保 (同一 stimulus を 3 temperature 試行)

**stimulus 設計** (`golden/stimulus/kant_de_focused.yaml` 新規):
- 25-50 unique de stimuli、Kantian Critique topics:
  - kategorischer Imperativ / Pflicht / Autonomie
  - transzendentale Ästhetik / Dialektik / Logik
  - Vernunft vs. Verstand / Sinnlichkeit
  - Ding an sich / Erscheinung
  - Freiheit / praktische Vernunft
- 各 stimulus: `category` + `prompt_text` (de question) +
  `expected_turn_count=1` + `expected_zone=monolog`

**target volume**: ~25 stimuli × 10 cycles × 1 turn = 250 turns / run、
1 run。post-filter (≥60 token + de language confirm) で ~200-300 examples
を取得 (margin で 2 run 採取して 500 examples)。

### 2. 既存 5022 examples との weighted blend ratio

**判断**: 既存 5022 examples は **そのまま保持**、新規 ~250-500 を
追加。weight 計算は per-example 不変 (`compute_example_weight` は metadata
ベース)。語族 mass は post-collection の `weight-audit.json` で確認:

- 期待 de+en mass: (旧 de mass ≈ 0.211 / 既存 5022) ×
  (5022 / (5022 + 350)) + (新規 de mass ≈ 0.7 / 350) ×
  (350 / 5372) ≈ 0.197 + 0.046 ≈ 0.243 (raw mass、weight 計算前)
- weighted mass 後: de=1.4 × 0.243 ≈ 0.34 → de のみで 0.34、en 0.26
  維持なら de+en = 0.60 達成
- **gate**: post-collection audit で de+en ≥ 0.60 を機械的 check

**理由**: 既存 corpus を削除すると DA-12 / DA-14 baseline と
discontinuous になり regression test 不能。corpus capital は preserve。

### 3. achieved corpus stats gate (preregistered)

新規 audit script `scripts/m9-c-adopt/audit_achieved_corpus_stats.py`:
- 入力: training kickoff 前の `weight-audit.json`
- 出力: `audit-achieved-corpus-stats.json` + exit code
- gate (preregistered):
  1. `n_eff > 1500` (DA-14 fallback trigger、本 ADR で再確認)
  2. `top_5_pct_weight_share < 0.35` (同上)
  3. **`per_language_weighted_mass["de"] + ["en"] >= 0.60`** (Plan B 採用
     条件、新規 hard gate)
- 1 / 2 / 3 のいずれか fail → exit 5 (script abort、retrain 起動しない)
- 全 pass → exit 0 + audit JSON を `.steering/.../audit-achieved-corpus-
  stats.json` に保存

### 4. retrain hyperparams

- **rank=8 carry-over** (DA-12 provisional、K-β heritage)
- **LR / scheduler**: v2 baseline 不変 (cosine、warmup_ratio=0.03、
  learning_rate=1e-4)
- **max_steps=4000** (v2 baseline)
- **eval_steps=500** (v2 baseline)
- **target_modules=[q_proj, k_proj, v_proj, o_proj]**
- **lora_alpha=16、lora_dropout=0.05**
- **NF4 + double quant** (peft + bitsandbytes)
- **early stopping (新規)**: HuggingFace `EarlyStoppingCallback(
  early_stopping_patience=3)`、metric=`eval_loss`、mode=`min`。
  v2 retrain の eval_loss step 2000=0.166 → final=0.180 mild overfit が
  Plan B では避けられる

### 5. D-2 allowlist for Plan B verdict (HIGH-2 enforcement 継承)

`.steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist.json`
を新規追加。Plan A allowlist の継承 + encoder agreement axis:

- **primary**: multilingual-e5-large、BAAI/bge-m3
- **regression**: sentence-transformers/all-mpnet-base-v2 (DA-14 instrument)
- **exploratory** (Plan B 新規): `lexical-5gram` (encoder-free baseline)
- **encoder agreement axis** (Plan A の BGE-M3 sign flip 教訓): Plan B
  verdict は **少なくとも 2 of {MPNet, E5, BGE-M3, lexical-5gram} が
  同じ符号方向で d ≤ -0.5 + CI upper < 0** を要求

### 6. dataset.py 拡張 (language-stratified split option)

`_group_aware_stratified_split` に optional kw-only param を追加:

```python
def _group_aware_stratified_split(
    weighted_examples_by_shard: dict[str, list[dict[str, object]]],
    *,
    eval_split_fraction: float,
    seed: int,
    language_stratified: bool = False,  # 新規
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
```

**動作**:
- `language_stratified=False` (default): 既存動作 (source_shard_type のみ)
- `language_stratified=True`: stratum を `(source_shard_type, language)`
  の複合 key にし、language ごと independent shuffle + split

**目的**: de monolog re-cast は rare class (~5-7% of train) なので、
random split で eval に集中する可能性。language stratify で eval split に
de monolog が混入する確率を sample size に対し proportional に固定。
**eval split に monolog re-cast は含めない** (DA-14 spec の "eval split に
monolog re-cast は含めない" 制約は維持、本 option は **train 側の
stratification 拡張で eval contamination を間接的に防止**)。

`train_kant_lora.py` 側で `language_stratified=True` を渡す path を追加
(CLI flag `--language-stratified` 新規)。

### 7. G-GEAR 採取準備

`g-gear-runbook.md` 新規:
- WSL2 path 不通 (reference_wsl2_ollama_unreachable.md)、**Windows native +
  PYTHONUTF8=1** 経路 (Phase B 判断 8)
- 起動 steps:
  1. SGLang server 起動 (WSL2 経由、`/root/erre-sandbox/.venv` で
     `--max-loras-per-batch 1 --max-lora-rank 8 --max-running-requests 8`)
  2. `multi_pin_sanity.sh` で adapter pre-load (本 Plan B は LoRA-on
     ではなく **base model** 採取なので adapter load 不要、
     `--no-lora-control` mode を流用)
  3. driver 起動: `python scripts/m9-c-adopt/de_focused_monolog_collector.py
     --persona kant --turn-count 250 --cycle-count 10 --no-lora-control
     --output data/eval/m9-c-adopt-plan-b/kant_de_focused_run0.duckdb`
  4. 採取完了後 `validate_multiturn_shards.py` で smoke pass
- **shard naming**: `kant_de_focused_run<N>.duckdb`、本 PR merge SHA を
  manifest に埋め込む (DA-11)

## 変更対象

### 修正するファイル
- `src/erre_sandbox/training/dataset.py` — `_group_aware_stratified_split`
  に `language_stratified` kw-only param 追加 (optional layer)
- `src/erre_sandbox/training/train_kant_lora.py` — CLI flag
  `--language-stratified` + EarlyStoppingCallback 追加
- `golden/stimulus/_schema.yaml` — kant_de_focused.yaml 用 schema 追記
  (もし schema 制約があれば)

### 新規作成するファイル
- `scripts/m9-c-adopt/de_focused_monolog_collector.py` — Plan B-2 driver
- `scripts/m9-c-adopt/audit_achieved_corpus_stats.py` — corpus gate
- `golden/stimulus/kant_de_focused.yaml` — de-only stimulus battery
- `.steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist.json`
- `.steering/20260517-m9-c-adopt-plan-b-design/g-gear-runbook.md`
- `tests/test_scripts/test_de_focused_monolog_collector.py`
- `tests/test_scripts/test_audit_achieved_corpus_stats.py`
- `tests/test_training/test_dataset.py` 拡張 (language-stratified test 追加)

### 削除するファイル
- なし (DA-14 v2 adapter / shards / verdict は historical reference)

## 影響範囲

- **dataset.py**: optional param のため既存呼び出しは無変更で動作
- **train_kant_lora.py**: CLI flag 追加のみ、default off で動作不変
- **既存 5022 examples**: 保持、Plan B は新規 examples を append のみ
- **SGLang server**: 設定変更不要 (base model 採取のため)

## 既存パターンとの整合性

- `tier_b_pilot.py` の SGLang client + DuckDB sink パターン継承
- `validate_multiturn_shards.py` の shard validation pattern を Plan B
  shard にも適用
- DA-11 manifest convention (`data/lora/m9-c-adopt-v2/<adapter>/manifest.
  json` に encoder name / version / git SHA + merge SHA)
- DA-15 D-2 allowlist enforcement pattern (encoder revision pin)

## テスト戦略

### 単体テスト
- `test_de_focused_monolog_collector.py`:
  - `_build_de_focused_system_prompt` が de bias 文字列を含むか
  - `_filter_min_token` で 60 未満を drop するか
  - `classify_language` で生成出力が de label されるか (synthetic samples)
- `test_dataset.py` 拡張: `language_stratified=True` で stratum 内の
  language ratio が input ratio と一致するか
- `test_audit_achieved_corpus_stats.py`: gate 3 thresholds の境界値で
  exit code が正しいか

### 統合テスト
- 実 G-GEAR 採取は次セッション (本セッションは driver dry-run の smoke
  test のみ、`--turn-count 5 --cycle-count 1` で本物 SGLang 必要なし、
  mock SGLang で smoke)

### 回帰テスト
- 既存 `test_dataset.py` の全 case が `language_stratified=False` で
  pass (default 動作不変)
- 既存 `test_train_kant_lora.py` の全 case が pass (新 flag default off)

## ロールバック計画

- **achieved corpus gate fail**: audit script が exit 5 で abort、
  retrain 起動しない。`.steering/.../audit-achieved-corpus-stats.json` に
  fail 内容記録。decisions.md DI-α-FAIL として記録、ADR D-15 re-evaluate。
- **retrain 実行後 DA-14 rerun verdict fail**: 別 PR で記録、Phase E A-6
  rank=16 (Plan C) を dry-run evidence 付きで再評価 (本 ADR scope 外、
  新 ADR DA-16 候補)。
- **driver bug**: dataset.py / train_kant_lora.py の変更は default off
  なので revert 不要、driver のみ修正で対応。
