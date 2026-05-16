# 設計 — Plan B (Candidate C targeted hybrid retrain) — hybrid 採用版

> `design-v1.md` (primary agent V1) と `design-v2.md` (Task tool subagent
> independent reimagine V2) の hybrid。採用判定根拠は `decisions.md`
> DI-1 / DI-2 / DI-3。本 file は実装の **single source of truth**。

## 0. Framing

Plan A の per-language signal (within-de d=-0.72 MPNet / within-en d=-0.58
E5) は本物だが global 6-window bootstrap が noise floor を超えなかった、
という Codex MEDIUM-2 整合仮説に **per-language の SNR を上げる介入**
で投資する。retrain の corpus shape を「de-monolog 集中、長文、marker
dense」に bend、評価面では encoder panel disagreement を ADOPT 不寄与化。
**Burrows axis 5% を主目標**、Vendi v2-encoder-swap を secondary、ICC を
3 軸目の anchor とする (V2 framing 採用)。

## 1. 実装アプローチ

### 1.1 de-focused monolog collector

**採取単位**: stimulus → focal turn の **single-turn long-form monolog**
(monolog-as-stimulus-response、V2 §1.1 採用)。

理由 (V2 §1.4): system-prompt-driven self-reflection は persona の
referent が **自分自身** に偏り (e.g. "Ich bin Kant..."), Burrows function-
word axis を artefact で歪める。stimulus-response 形は referent が
argument 内容に向くので、Critique-of-Pure-Reason 風 transcendental
argumentation を 1st-person で叙述する形に自然。LISA stylometry の
"content-bleached style channel" 仮説と整合。

**driver**: `scripts/m9-c-adopt/de_focused_monolog_collector.py`、
`tier_b_pilot.py` を base に流用:

- SGLang chat client + DuckDB sink を継承
- multi-turn alternation は捨て、`addressee_persona_id=None` /
  `expected_turn_count=1` 固定
- **新 helper `_build_de_monolog_system_prompt`** (既存 `_build_system_
  prompt` を fork、上書きしない):
  - "Answer in **German**, even if the stimulus is in English."
  - "Write a single self-addressed monolog of 80–160 German words
    (≈ 100–200 Qwen3 tokens). Do not address an interlocutor."
  - "Use Critique-of-Pure-Reason register: transcendental, a priori,
    an sich, kategorischer Imperativ, where the topic permits."
- サンプリング: `temperature=0.7`、`max_tokens=320`、`frequency_penalty=0.3`、
  `presence_penalty=0.3` (R-2 loop mitigation)
- **stimulus subset**: 既存 `golden/stimulus/kant.yaml` から de prompt +
  expected_zone ∈ {study, peripatos} を抽出 (~30 stim)、新規 battery は
  作らない (V2 §1.2 ②、corpus capital を絞る)。moral_dilemma / tom /
  roleeval は exclude (R-4 persona drift mitigation)
- **post-hoc filter (hard gate)** (V2 §1.2 ③):
  - `classify_language(utterance) == "de"`
  - `estimate_token_count(utterance) >= 60`
  - `marker_density_per_100_tokens >= 1.0` (Cambridge anchor の 50% floor)
  - **trigram loop detector**: 同一 trigram 出現 ≥4 回で reject (R-2)
- **target**: net 250 examples (margin で max_attempts=800、acceptance
  rate ~31% 想定)。dry-run mode で acceptance 事前測定可。
- **shard 物理削除**: filter で reject された row は DuckDB から
  `DELETE`、resume state も filter 後の `completed_turns` で更新

### 1.2 既存 5022-example blend ratio

既存 corpus は **保持**、新 shard `kant_de_monolog_run0.duckdb` を
`kant_*.duckdb` glob に append のみ (V2 §1.3 採用)。weighting.py の
language=de 1.4 + length≥60 1.5 + monolog 1.5 + marker dense ≥1.0 が
自動的に新 row の weight を clamp 後 ~3.0 に押し上げ、新規 250 examples
の effective contribution は ~750-equivalent。**weighting.py の
coefficient は不変** (D-2 portability 維持、HIGH-3 grey-zone 回避)。

### 1.3 Achieved corpus stats gate (preregistered、4 axes)

`scripts/m9-c-adopt/audit_plan_b_corpus_stats.py` 新規 (V2 §2.2-2.4 採用):

- 入力: `weight-audit.json` (既存 `_pre_training_audit` の出力)
- 出力: `data/lora/m9-c-adopt-v2/kant_r8_v3/plan-b-corpus-gate.json`

**thresholds (preregistered)**:
1. `n_eff >= 1500` (既存 DA-14 fallback trigger は 1000、本 PR は 1500
   を **hard gate** に固定)
2. `top_5_pct_weight_share <= 0.35` (同上)
3. `per_language_weighted_mass["de"] + ["en"] >= 0.60` (Plan B 新規
   hard gate、Codex MEDIUM-1 違反ではない: DI-5 数値を retroactive 移動
   せず、Plan B 起動後の **新 axis** として起こす)
4. **`per_language_weighted_mass["de"] >= 0.30`** (V2 §8 minority opinion
   採用、Plan B 新規 hard gate、en free-rider 防止)

**JSON shape** (V2 §2.3 採用):
```json
{
  "schema_version": 1,
  "plan_b_gate": "pass" | "fail",
  "thresholds": {
    "n_eff_min": 1500.0,
    "top_5_pct_max": 0.35,
    "de_en_mass_min": 0.60,
    "de_mass_min": 0.30
  },
  "achieved": { "n_eff": ..., "top_5_pct_weight_share": ...,
                "de_en_mass": ..., "de_mass": ... },
  "failed_axes": [...],
  "weight_audit_path": "...",
  "merge_sha": "<本 PR merge SHA>",
  "captured_at_utc": "..."
}
```

**abort behavior**: `PlanBCorpusGateError` (新 exception、`exceptions.py`
追加、exit code 8) を raise。kill 前に `plan-b-corpus-gate.json` を必ず
emit (forensic 必須)。

**pipeline 内位置**: `train_kant_lora._pre_training_audit` 直後、かつ
GPU stack import の直前。`--plan-b-gate` CLI flag (default False) で
hard gate 昇格を切り替え、未指定の K-β / v2 baseline path は動作不変。

### 1.4 retrain hyperparams (v2 baseline からの delta)

V2 §3 採用 (empirically tied to v2 overfit envelope):

| param | v2 baseline | Plan B |
|---|---|---|
| rank | 8 | **8** (DA-12 carry-over) |
| lora_alpha / dropout | 16 / 0.05 | **16 / 0.05** |
| target_modules | q/k/v/o_proj | **q/k/v/o_proj** |
| max_steps | 4000 | **2500** (step 2000 overfit + 3 eval window margin) |
| learning_rate | 2e-4 | **2e-4** |
| scheduler / warmup | cosine / 0.03 | **cosine / 0.03** |
| eval_steps / save_steps | 500 / 500 | **250 / 250** (10 eval window) |
| early stopping | なし | **`EarlyStoppingCallback(patience=2, threshold=0.005)`** on `eval_loss` |
| quantization | NF4 + double quant | **NF4 + double quant** |
| batch / grad_accum / max_seq_length | 1 / 8 / 2048 | **1 / 8 / 2048** |

実装: `--plan-b-gate` flag 立ち時に `EarlyStoppingCallback` attach、
TrainingArguments に `metric_for_best_model="eval_loss"` +
`greater_is_better=False`。

### 1.5 D-2 allowlist for Plan B verdict (4-encoder agreement axis)

`.steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json`
(V2 §5 採用、HIGH-2 enforcement 機構継承):

| encoder | role | rationale |
|---|---|---|
| `intfloat/multilingual-e5-large` | primary | en 軸検出器 (d_en=-0.58) |
| `sentence-transformers/all-mpnet-base-v2` | primary | de 軸最強検出器 (d_de=-0.72)、DA-14 baseline で再昇格 |
| `lexical_5gram` | primary | retrieval-trained でない independent kernel |
| `BAAI/bge-m3` | exploratory | Plan A natural d sign flip、報告 obligatory だが ADOPT 不寄与 |

**encoder agreement axis** (V2 §5.3 採用、BGE-M3 sign flip 教訓
generalisation):

- Plan B ADOPT は **3 primary encoder のうち 2 以上**で:
  - natural d ≤ -0.5 AND CI upper < 0
  - lang-balanced d ≤ -0.5 (DA-15 Plan A の bootstrap method 継承)
  - length-balanced d ≤ -0.5
  - **符号一致** (3 とも negative、disagreement 時は除外)
- 1 encoder が retrieval artefact で flip しても majority direction
  discipline で ADOPT 判定が腐らない

**Burrows axis (5%)**: encoder 非依存なので D-2 allowlist 対象外、
DA-14 threshold 不変。Plan B は de monolog 集中で **Burrows axis 主目標
達成** を狙う設計、v2 で +0.43% だった Burrows を 5% に押し上げる
ことが de-mass increase で初めて現実的になる。

**lexical-5gram 実装の scope 分割** (本 hybrid 独自の調整):
- 本 PR scope: D-2 allowlist に **module path を pre-register のみ**
  (`erre_sandbox.evidence.tier_b.vendi_lexical_5gram`)
- 実装 (`vendi_lexical_5gram.py`、~50 LOC、char 5-gram cosine kernel) は
  **retrain 実行 session (次回)** に scope。
- 理由: retrain 実行前に verdict 計算は走らないため、本 PR で実装しても
  blocker にならない。本 PR scope tightening (design + driver + 採取準備)
  を維持。

### 1.6 language-stratified split option (`stratify_by_language`)

V2 §4 採用、補正: 既存 `_group_aware_stratified_split` は
`src/erre_sandbox/training/train_kant_lora.py` 内にある (next-session
prompt の "dataset.py 拡張" は naming のみで、function 本体は
train_kant_lora.py に集約済)。

**signature**:
```python
def _group_aware_stratified_split(
    weighted_examples_by_shard: dict[str, list[dict[str, object]]],
    *,
    eval_split_fraction: float,
    seed: int,
    stratify_by_language: bool = False,  # ← 新 kw-only flag
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
```

- `False` (default): 既存動作 (source_shard_type のみで stratify)
- `True`: stratum key を `(source_shard_type, language)` に拡張、
  各 stratum で独立 90/10 random split

**plug-in**: `_collect_from_shards_weighted` に
`stratify_by_language=use_lang_stratify` を CLI 経由で渡す。CLI flag
`--lang-stratified-split` (default False)。Plan B run で立てる。

**eval contamination semantics** (V2 §4.3): 新規 de-monolog shard の
dialog_id namespace (`de_mono_{stim_id}_{cycle}`) は natural / stimulus
shard と物理的衝突しないので、既存 group-aware split で leak-safe。
language stratification を on にしても eval 側に de-monolog が 10%
混入するため、eval_loss が de-monolog distribution を代表し、
early stopping signal が Plan-B-relevant 方向に sharpened される利点。

### 1.7 G-GEAR 採取準備

`.steering/20260517-m9-c-adopt-plan-b-design/g-gear-collection-runbook.md`
(V1 §7 + V2 §6 採用):

- WSL2 経由は Windows native Ollama unreachable (memory
  `reference_wsl2_ollama_unreachable.md`)、Phase B 判断 8 の
  **Windows native + PYTHONUTF8=1** 経路
- SGLang は WSL2 で起動 (`/root/erre-sandbox/.venv/bin/python -m
  sglang.launch_server`)、driver は Windows 側 .venv で起動 (両方とも
  network 越しに動作)
- 起動 steps:
  1. SGLang server start (`--max-loras-per-batch 1 --max-lora-rank 8`、
     ただし Plan B 採取は **base model**)
  2. driver smoke test: `--dry-run --turn-count 50 --cycle-count 1` で
     acceptance rate 測定
  3. main run: `--target-net 250 --max-attempts 800
     --output data/eval/m9-c-adopt-plan-b/kant_de_focused_run0.duckdb
     --no-lora-control`
  4. `validate_multiturn_shards.py` で smoke pass (turn_index=0 のみで
     alternation trivial pass)
  5. `audit_plan_b_corpus_stats.py` で gate pre-check
- **shard naming**: `kant_de_focused_run<N>.duckdb`、manifest に
  本 PR merge SHA + 採取時刻 + acceptance rate + 採取 stim id list

## 2. 変更対象

### 修正するファイル
- `src/erre_sandbox/training/train_kant_lora.py`
  - `_group_aware_stratified_split` に `stratify_by_language` kw-only flag
  - `--plan-b-gate` CLI flag (default False)
  - `--lang-stratified-split` CLI flag (default False)
  - `EarlyStoppingCallback` attach (Plan B mode のみ)
  - `PlanBCorpusGateError` raise wiring (Plan B mode のみ)
- `src/erre_sandbox/training/exceptions.py`
  - `PlanBCorpusGateError` 追加 (exit code 8)
- `src/erre_sandbox/training/dataset.py`
  - 変更なし (function 本体は train_kant_lora.py に集約済のため、
    本 PR では dataset.py 拡張は不要。要件側の "dataset.py 拡張" は
    naming のみで、実装は train_kant_lora.py で完結)

### 新規作成するファイル
- `scripts/m9-c-adopt/de_focused_monolog_collector.py` (~350 LOC)
- `scripts/m9-c-adopt/audit_plan_b_corpus_stats.py` (~120 LOC)
- `.steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json`
- `.steering/20260517-m9-c-adopt-plan-b-design/g-gear-collection-runbook.md`
- `tests/test_training/test_dataset_lang_stratified.py` (~80 LOC)
- `tests/test_scripts/test_de_focused_monolog_collector.py` (~120 LOC)
- `tests/test_scripts/test_audit_plan_b_corpus_stats.py` (~60 LOC)

### 削除するファイル
- なし (DA-14/15 artifact は historical record)

### 次セッション scope (本 PR 含まず)
- `src/erre_sandbox/evidence/tier_b/vendi_lexical_5gram.py` (~50 LOC、
  char 5-gram cosine kernel)
- retrain 実行 (~20h G-GEAR overnight)
- DA-14 rerun verdict 計算 + Plan B verdict 文書化

## 3. 影響範囲

- **train_kant_lora.py**: CLI flag 追加のみ、default off で動作不変
- **dataset.py / build_weighted_examples**: 変更なし
- **既存 5022 examples**: 保持、Plan B は新規 examples を append のみ
- **SGLang server**: 設定変更不要 (base model 採取)
- **既存 test suite**: regression に注意、`--plan-b-gate` 未指定で
  K-β / v2 baseline path が byte-identical (golden test)

## 4. 既存パターンとの整合性

- `tier_b_pilot.py` の SGLang client + DuckDB sink パターン継承
- `validate_multiturn_shards.py` の shard validation pattern を継承
- DA-11 manifest convention (`manifest.json` に encoder name / version /
  git SHA + merge SHA)
- DA-15 D-2 allowlist enforcement pattern (encoder revision pin)
- 既存 group-aware split との直交軸として language stratification を拡張

## 5. テスト戦略

### 単体テスト
- `test_de_focused_monolog_collector.py`:
  - `_build_de_monolog_system_prompt` が de bias 文字列を含む
  - post-hoc filter: de detect / length ≥60 / marker density ≥1.0 /
    trigram loop detector の各 boundary
- `test_dataset_lang_stratified.py`:
  - `stratify_by_language=False` で既存 split byte-identical
  - `stratify_by_language=True` で seed=42 deterministic
  - 各 stratum (de/en/ja/mixed × natural/stimulus) の n_eval が
    `round(0.1 * n_keys)` と一致
  - train ∩ eval = ∅
- `test_audit_plan_b_corpus_stats.py`:
  - 4 gate (n_eff / top_5 / de_en_mass / de_mass) の境界値で
    exit code が正しい
  - `plan-b-corpus-gate.json` shape が schema 通り
  - `failed_axes` が複数 fail 時に正しく enumerate される

### 統合テスト
- 実 G-GEAR 採取は次セッション。本 PR は driver の dry-run smoke のみ
  (mock SGLang で 5 turn 採取して shard schema を検証)。

### 回帰テスト
- 既存 `test_train_kant_lora.py` / `test_dataset.py` 全 case が
  `--plan-b-gate` 未指定 / `--lang-stratified-split` 未指定で pass

## 6. ロールバック計画

- **collector で 250 net 達成不能**: 採取結果を
  `data/eval/plan-b-rejected/` に隔離、retrain は v2 baseline で再実行
  (Phase E A-6 へ migrate)。decisions.md DI-α-FAIL として記録、
  ADR D-15 re-evaluate。
- **retrain で early stopping が即時 fire**: 別 PR で patience=3 +
  min_delta=0.01 に softening して再 retrain。
- **DA-14 rerun verdict fail**: kant について Phase E A-6 で rank=16
  (Plan C) を dry-run evidence 付きで再評価 (本 ADR scope 外、
  新 ADR DA-16 候補)。本 PR の collector + lexical-5gram は corpus
  capital として retain。
- **本 PR の Plan B design に critical defect が見つかる**: revert は
  default off の CLI flag のため安全、driver / audit script は別
  branch で hotfix。

## 7. 次セッション handoff (retrain 実行)

1. `feature/m9-c-adopt-plan-b-driver` merge → main
2. `vendi_lexical_5gram.py` 実装 (~50 LOC、~30min)
3. `de_focused_monolog_collector.py` で 250 net 採取 (~3h)
4. `audit_plan_b_corpus_stats.py` で gate pre-check
5. `train_kant_lora.py --plan-b-gate --lang-stratified-split
   --max-steps 2500 --eval-steps 250 ...` で retrain (~20h)
6. DA-14 rerun (Vendi MPNet/E5/BGE-M3 + lexical-5gram + Burrows +
   ICC) verdict 計算 (~2h、4 encoder × 2 baseline × CI bootstrap)
7. Plan B verdict 文書化、kant ADOPT or Phase E A-6 移行判定
