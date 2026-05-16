# 設計 — Plan B retrain prep + 採取 + kickoff

## 実装アプローチ

PR #180 の Plan B design (`.steering/20260517-m9-c-adopt-plan-b-design/
design.md`) を **執行する** session。新規設計判断はなく、既存 design の
§7 next-session handoff を実装するのが目的。

### 1. lexical-5gram kernel 実装 (~30 min)

**新規**: `src/erre_sandbox/evidence/tier_b/vendi_lexical_5gram.py`
- char 5-gram TF-IDF cosine kernel (sklearn `TfidfVectorizer(
  analyzer="char_wb", ngram_range=(5,5))` → cosine similarity)
- `make_tfidf_5gram_cosine_kernel() -> VendiKernel` factory
- `LEXICAL_5GRAM_KERNEL_NAME = "lexical_5gram"` constant
- 既存 `make_lexical_5gram_kernel` (Jaccard) と共存。Plan A P4b sensitivity
  panel は Jaccard 継続、Plan B D-2 primary は TF-IDF cosine

**vendi.py 拡張**:
- `_load_default_kernel(encoder_name=None, *, kernel_type="semantic")` に
  `kernel_type="lexical_5gram"` dispatch を追加
- 既存の `encoder_name or _DEFAULT_ENCODER_MODEL_ID` 行を保持 (regression
  test `test_load_default_kernel_signature_accepts_encoder_name` が source
  inspect している)

**`__init__.py` 拡張**: `make_tfidf_5gram_cosine_kernel` / 
`LEXICAL_5GRAM_KERNEL_NAME` を tier_b パッケージから再エクスポート

### 2. G-GEAR 採取 (~30 min smoke + ~3h main)

`g-gear-collection-runbook.md` §2-§5 をそのまま実行 — **ただし SGLang
起動 command は本セッションで empirical に確定した
`--quantization fp8 --max-total-tokens 2048 --max-running-requests 1
--disable-cuda-graph --disable-piecewise-cuda-graph` を採用** (DR-4 / blockers.md ブロッカー 1)。

- SGLang server: WSL2 内、base model `Qwen/Qwen3-8B`、fp8 quant 必須
  (BF16 では 16 GB VRAM に fit せず OOM)、Blackwell SM120 では
  piecewise CUDA graph も disable (sampler argmax kernel deadlock 回避)
  - LoRA は無効 (`--max-loras-per-batch` 不要)
- driver: Windows native `.venv`、`PYTHONUTF8=1`、SGLang host は WSL2 LAN IP
- dry-run: `--target-net 50 --max-attempts 200 --dry-run` で acceptance rate
  測定
- main: `--target-net 250 --max-attempts 800 --temperature 0.7
  --frequency-penalty 0.3 --presence-penalty 0.3
  --output data/eval/m9-c-adopt-plan-b/kant_de_monolog_run0.duckdb`
- `PLAN_B_MERGE_SHA` env に本 retrain PR の最終 commit SHA (manifest 埋め込み用)

### 3. corpus gate pre-check (~5 min)

`g-gear-collection-runbook.md` §6:
1. `train_kant_lora --dry-run --weighted` で `weight-audit.json` 生成
2. `audit_plan_b_corpus_stats.py --weight-audit ... --merge-sha ...
   --output plan-b-corpus-gate.json`
3. exit code 0 (4 axes 全 pass) を確認、fail なら driver 再採取か
   Phase E A-6 migration を `decisions.md` DI-α-FAIL として記録

### 4. retrain kickoff (background ~20h)

`g-gear-collection-runbook.md` §8 通り、WSL2 GPU 経路で:

```
wsl -d Ubuntu -- bash -c "
cd /mnt/c/ERRE-Sand_Box
PYTHONPATH=/mnt/c/ERRE-Sand_Box/src \
PYTHONUTF8=1 \
/root/erre-sandbox/.venv/bin/python -m erre_sandbox.training.train_kant_lora \
    --duckdb-glob '/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_*.duckdb \
                   /mnt/c/ERRE-Sand_Box/data/eval/m9-c-adopt-plan-b/kant_de_monolog_run*.duckdb' \
    --output-dir /mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v3 \
    --rank 8 --max-steps 2500 --eval-steps 250 \
    --weighted --plan-b-gate --lang-stratified-split -v
" > .steering/20260518-m9-c-adopt-plan-b-retrain/retrain-stdout.log 2>&1
```

本セッションは「retrain が順調に走り始めた」(初回 eval で `eval_loss <
initial`、~30 min) で停止。verdict 計算は次々セッション。

## 変更対象

### 新規作成するファイル
- `src/erre_sandbox/evidence/tier_b/vendi_lexical_5gram.py`
- `tests/test_evidence/test_tier_b/test_vendi_lexical_5gram.py`
- `.steering/20260518-m9-c-adopt-plan-b-retrain/{requirement,design,tasklist,blockers,decisions}.md`
- `data/eval/m9-c-adopt-plan-b/kant_de_monolog_run0.duckdb` + manifest
- `data/lora/m9-c-adopt-v2/kant_r8_v3/{weight-audit.json,plan-b-corpus-gate.json}`

### 修正するファイル
- `src/erre_sandbox/evidence/tier_b/vendi.py` (`_load_default_kernel` の
  kernel_type dispatch)
- `src/erre_sandbox/evidence/tier_b/__init__.py` (export 拡張)

### 削除するファイル
- なし

## 影響範囲

- `_load_default_kernel(kernel_type="semantic")` (default) で既存 callers
  byte-identical (Plan A `da1_matrix_multiturn.py` 等)
- `_load_default_kernel(kernel_type="lexical_5gram")` は Plan B 専用、本
  session で test に asserted
- training pipeline は本 PR で変更しない (PR #180 で確定済み)
- retrain artifact (`data/lora/m9-c-adopt-v2/kant_r8_v3/`) は overnight で
  生成、本 PR では「kickoff 完了 + 最初の eval ログ」のみ commit

## 既存パターンとの整合性

- `vendi.py:make_lexical_5gram_kernel` の Jaccard kernel pattern と同じ
  `VendiKernel = Callable[[Sequence[str]], np.ndarray]` 型を返却
- lazy import (sklearn は kernel call 時にのみ import) で base install を
  軽くする vendi.py の既存規約に follow
- `_load_default_kernel` の `from ... import ... # noqa: PLC0415` lazy
  import pattern を踏襲
- DA-11 manifest convention (`PLAN_B_MERGE_SHA` env → manifest emit) を
  collector 内で踏襲

## テスト戦略

### 単体テスト (新規 `test_vendi_lexical_5gram.py`)
- LEXICAL_5GRAM_KERNEL_NAME 定数
- diagonal == 1, 対称性
- 同一テキスト → similarity == 1
- 非共通テキスト → similarity == 0 or 低
- char 5-gram 以下の短入力 → fallback identity (ValueError handling)
- `compute_vendi(items, kernel=...)` 経由の round-trip
- `_load_default_kernel(kernel_type="lexical_5gram")` dispatch test

### 回帰テスト
- 既存 `test_vendi.py` 全 case
- 特に `test_load_default_kernel_signature_accepts_encoder_name` (source
  inspect で `encoder_name or _DEFAULT_ENCODER_MODEL_ID` を assert)

### 統合テスト
- G-GEAR 採取 + retrain は実機実行で in-situ 検証 (本 PR のテスト範囲外)

## ロールバック計画

- **lexical-5gram 実装が test fail**: `_load_default_kernel` の dispatch を
  revert (kernel_type kwarg を no-op に)、新モジュールは retain (次セッション
  で再修正)
- **acceptance rate < 25%**: persona prompt augmentation 強化 (Critique
  原文 paste、temperature 0.8 試行)。改善しない場合 driver の MEDIUM-2
  filter (addressee) を soften する判断は `decisions.md` に記録
- **corpus gate fail**: 再採取で de_mass を boost (de stim subset を再
  curate)。それでも fail なら Phase E A-6 (rank=16) migration を
  decisions.md DI-α-FAIL として記録
- **retrain で early stopping 即時 fire**: 別 PR で patience=3 +
  min_delta=0.01 に softening して再 retrain
- **retrain 中断 / SGLang crash**: HF Trainer の checkpoint resume で再開
