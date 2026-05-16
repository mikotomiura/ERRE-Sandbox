# 設計 — DA-15 Phase 1 implementation (Plan A = Vendi kernel swap)

## 実装アプローチ

Plan A は **measurement-side swap**: 既存 v2 + no-LoRA pilot の generation
出力 (duckdb shards) はそのまま、Vendi semantic kernel の encoder を MPNet
から multilingual encoder (multilingual-e5-large, bge-m3) に差し替えて
rescore する。

DA-14 thresholds は不変 (HIGH-3 遵守): 新 metric
`vendi_semantic_v2_encoder_swap` を versioned 起こし、point ≤ -0.5 + CI
upper < 0 + balanced 条件維持。MPNet `vendi_semantic` は historical record
として併報告し、"DA-14 fail のまま DA-15 pass" を明示。

### Plan A eligibility gate (Codex HIGH-2)

shared Claude-arm 盲点 (= multilingual-e5 / bge-m3 は retrieval-trained で
style discriminator でない) を対応するため、以下を必須化:

1. **calibration panel** (`da15_calibration_panel.py`):
   - Kant Critique 邦訳 (Aozora Bunko 由来) 100 文 + control text (Heidegger
     関連、邦訳 + 英訳) 100 文
   - 各 candidate encoder で cosine similarity から binary classifier
     (logistic regression on pairwise cosine features) を fit
   - **AUC ≥ 0.75 pass gate**: fail した encoder は primary gate 除外
2. **balanced bootstrap** (`rescore_vendi_alt_kernel.py`):
   - language-balanced: de/en/ja 内で independent resampling
   - token-length-balanced: 各 length quartile 内で independent resampling
3. **within-language d 併報告**: d_de, d_en, d_ja を verdict に記載

### Apples-to-apples の維持

v2 と no-LoRA baseline を **同 encoder + 同 revision + 同 normalization** で
rescore。v2 shards = `data/eval/m9-c-adopt-tier-b-pilot-multiturn-v2/
kant_r8v2_run{0,1}_stim.duckdb`、no-LoRA shards = `data/eval/m9-c-adopt-tier-
b-pilot-multiturn/kant_nolora_run{0,1}_stim.duckdb` (3 windows/shard × 2 shard
= 6 windows × 100 turns / encoder)。

## 変更対象

### 修正するファイル

- `src/erre_sandbox/evidence/tier_b/vendi.py` — `_load_default_kernel(
  encoder_name: str | None = None)`。MPNet default は維持。HF model id を
  渡せるように。
- `scripts/m9-c-adopt/compute_baseline_vendi.py` — `--encoder` CLI 引数
  追加 (default `sentence-transformers/all-mpnet-base-v2`)、kernel_name と
  encoder_model 出力 field に伝播。
- `tests/test_evidence/test_tier_b/test_vendi.py` — encoder parameterisation
  の unit test 追加。MPNet default 不変の regression を保つ。
- `scripts/m9-c-adopt/da1_matrix_multiturn.py` — comparator note を
  "no-LoRA SGLang baseline (DA-14 authoritative)" に切替 (note 改訂のみ、
  output JSON の comparator label は既に DA-14 verdict 経由で no-LoRA 利用)。

### 新規作成するファイル

- `scripts/m9-c-adopt/da15_calibration_panel.py` — Kant + Heidegger control
  corpus を読み込み、各 encoder で cosine similarity の AUC を計算。
  AUC ≥ 0.75 を pass 基準。出力: `.steering/20260516-m9-c-adopt-da15-impl/
  da15-calibration-{encoder}.json`。
- `scripts/m9-c-adopt/rescore_vendi_alt_kernel.py` — v2 + no-LoRA duckdb
  shards を読み込み、指定 encoder で Vendi 再 score。bootstrap CI on
  cohens_d (seed=42)。balanced bootstrap (language / token length) + within-
  language d を計算。出力: `.steering/20260516-m9-c-adopt-da15-impl/
  da15-rescore-{encoder}-kant.json`。
- `data/calibration/kant_heidegger_corpus.json` — calibration test corpus
  (sentences with labels {kant, control} + language tag {de, en, ja})。
- `.steering/20260516-m9-c-adopt-da15-impl/da15-verdict-kant.json` — 最終
  verdict (per-encoder d、balanced d、within-lang d、AUC、ICC PASS 状態、
  ADOPT/REJECT 判定)。
- `.steering/20260516-m9-c-adopt-da15-impl/da15-verdict-kant.md` — verdict
  文書 (Burrows named limitation 必須記載)。
- `.steering/20260516-m9-c-adopt-da15-impl/codex-review-prompt.md` +
  `codex-review.md`。

### 削除するファイル

なし (DA-14 artefact は全 historical reference として保持)。

## 影響範囲

- **vendi.py encoder parameterisation**: 既存 callers (Tier A novelty 含む)
  は引数を渡さない限り MPNet default 動作維持。backward-compatible。
- **compute_baseline_vendi.py**: 既存 invocation は default で動く。
- **calibration / rescore scripts は新規**: 既存 pipeline には影響なし。

## 既存パターンとの整合性

- **HF revision pin convention**: `.steering/20260513-m9-c-adopt/decisions.md`
  DA-11 で確立した manifest 慣例 (encoder name / version / git SHA を埋め込む)
  を踏襲。本 PR では `decisions.md` D-2 に encoder name + HF revision SHA +
  transformers/sentence-transformers version + commit SHA を pre-registration
  として固定。
- **bootstrap_ci utility**: `erre_sandbox.evidence.bootstrap_ci.
  hierarchical_bootstrap_ci` を再利用 (rescore script で CI 計算)。
- **versioned metric naming**: DA-14 thresholds は不変、metric name を
  `vendi_semantic_v2_encoder_swap` に変更して identifiability を確保。

## テスト戦略

### 単体テスト

- `_load_default_kernel(encoder_name="sentence-transformers/all-mpnet-base-v2")`
  が従来の MPNet と等価な kernel を返すこと (regression、回帰防止)
- `_load_default_kernel(encoder_name="intfloat/multilingual-e5-large")` が
  正しく HF model を load (test 環境では mock + structure 検証のみ、CI が
  ML extras を持たない場合に備える)
- MPNet default 引数で従来の test_vendi_default_encoder_model_id 仕様が
  保持されること
- `compute_baseline_vendi.py --encoder` 引数 parsing の sanity (--help 出力)

### 統合テスト

- 既存 v2 multi-turn pilot 出力を MPNet default で rescore し、DA-14 verdict
  数値 (v2 mean 33.183 / no-LoRA mean 33.311 / d -0.18) が **再現** されること
- (Compute requirement あり、CI では skip)

### 回帰テスト

- 既存 `test_vendi_default_encoder_model_id_is_all_mpnet_base_v2` が pass

## ロールバック計画

- **Plan A fail (両 candidate encoder で AUC < 0.75 or balanced d > -0.5)**:
  multilingual-e5 / bge-m3 不採用を `decisions.md` D-α-FAIL として記録。
  MPNet default 維持、Phase 2 (Plan B) へ別 PR で起票。
  vendi.py / compute_baseline_vendi.py の encoder parameterisation は
  backward-compat なので merge 維持。
- **Plan A pass で kant ADOPT**: Burrows axis FAIL は named limitation で
  documented (Codex LOW-1)。Phase 2 を起動するか、reference corpus work を
  起動するかは別途決定。
