# 重要な設計判断 — Plan B retrain prep + 採取 + kickoff

> 本 file は本セッション固有の session-local decisions を記録する。
> 横断 ADR は `.steering/20260513-m9-c-adopt/decisions.md`、Plan B design
> 判断は `.steering/20260517-m9-c-adopt-plan-b-design/decisions.md` DI-1〜DI-8
> を参照。

## DR-1: `_load_default_kernel` への kernel_type dispatch (既存 signature 互換性維持)

- **判断日時**: 2026-05-18
- **背景**: Plan B design DI-6 で「lexical-5gram 実装は next-session scope」
  と決まり、本セッションで `vendi.py:_load_default_kernel` を拡張する必要が
  生じた。既存 regression test
  `test_load_default_kernel_signature_accepts_encoder_name` は source 内に
  `encoder_name or _DEFAULT_ENCODER_MODEL_ID` 文字列があることを assert する。
- **選択肢**:
  - A: `_load_default_kernel(encoder_name=None, *, kernel_type="semantic")`
    として kwarg 追加、kernel_type==`"lexical_5gram"` で dispatch
  - B: 別関数 `_load_lexical_5gram_kernel()` を tier_b/vendi_lexical_5gram.py
    に置き、consumer 側 (da1_matrix_multiturn.py) で encoder_name に応じて
    dispatch
  - C: `_load_default_kernel` を高階化 (factory pattern)
- **採用**: A
- **理由**:
  1. Plan B design §1.5 で明文化された `vendi.py:_load_default_kernel(
     kernel_type=...) から dispatch` 方針に合致
  2. 既存 source 内の `encoder_name or _DEFAULT_ENCODER_MODEL_ID` 行を
     保持できる (regression test green-keep)
  3. kwarg-only にすることで positional callers (Plan A pipeline) を不変
     のまま、新 dispatch path を opt-in にできる
- **トレードオフ**: kernel_type に追加値 (例: byte-pair) を足す時に signature
  が肥大化するリスク。将来 3 以上に分岐するなら C (factory) を再考。
- **影響範囲**: vendi.py + vendi_lexical_5gram.py + 既存 test 不変、新規
  test 1 件追加。
- **見直しタイミング**: 次の Plan (C 等) で別 kernel family が追加される時。

## DR-2: 既存 `make_lexical_5gram_kernel` (Jaccard) と新 `vendi_lexical_5gram.py` (TF-IDF cosine) を共存

- **判断日時**: 2026-05-18
- **背景**: `vendi.py` には既に `make_lexical_5gram_kernel` (P4b sensitivity
  panel で使う Jaccard kernel) が実装されている。Plan B D-2 allowlist の
  `lexical_5gram` primary は char 5-gram **cosine** kernel と書かれている。
  Jaccard と cosine では数値性質が異なる (Jaccard は集合の overlap、cosine
  は TF-IDF weighting 込みの内積)。
- **選択肢**:
  - A: Jaccard を deprecate して cosine に統一
  - B: 別モジュール `vendi_lexical_5gram.py` に cosine を分離、Jaccard は
    P4b sensitivity panel 用に retain
- **採用**: B
- **理由**:
  1. P4b sensitivity panel は既存 baseline でレポート済み (`test_vendi_
     kernel_sensitivity_panel_shape_matches_weights` が依拠)
  2. d2-encoder-allowlist-plan-b.json の `implementation_module` が
     `erre_sandbox.evidence.tier_b.vendi_lexical_5gram` と明示 pre-register
     されている
  3. Plan A の P4b 連続性 (`hybrid-X-Y` kernel name) を破壊しない
- **トレードオフ**: 「lexical_5gram」という名前で 2 つの kernel が存在する
  混乱の余地。本 file で明示分離することで future reader が混乱しない。
- **影響範囲**: `make_lexical_5gram_kernel` (Jaccard) は P4b panel 専用、
  Plan B verdict 計算では使わない。`make_tfidf_5gram_cosine_kernel`
  (新) が Plan B D-2 primary。
- **見直しタイミング**: Plan B verdict 完了後、Jaccard を deprecate するか
  retain するか別 PR で再評価。

## DR-4: SGLang 起動 invocation を `--quantization fp8 --max-total-tokens 2048 --max-running-requests 1 --disable-cuda-graph --disable-piecewise-cuda-graph` に確定 (Blackwell SM120 + Qwen3-8B + 16 GB VRAM)

- **判断日時**: 2026-05-16 (本セッション、SGLang 起動 blocker 解決後)
- **背景**: Plan B next-session prompt に従って
  `python -m sglang.launch_server --model-path Qwen/Qwen3-8B --host 0.0.0.0
  --port 30000 --mem-fraction-static 0.85 --chunked-prefill-size 8192
  --max-running-requests 8 --disable-cuda-graph` で起動 → BF16 で OOM
  sigquit。fp8 quant + max-total-tokens 2048 + max-running-requests 1
  追加で起動成功するも、Qwen3-8B サンプリング (argmax CUDA kernel) が
  hang → watchdog timeout 300s で再 sigquit。
- **試したこと**:
  1. K-α launch v5 invocation (`--quantization fp8 --max-total-tokens 2048
     --max-running-requests 1 --disable-cuda-graph`) → server up + chat
     warmup OK だが driver chat 時に sampler argmax CUDA kernel deadlock
  2. `--disable-piecewise-cuda-graph` を追加 → ready 後 micro smoke
     (3 net、8 attempts、60.9s elapsed、acceptance 37.5%、~7.5s/attempt
     throughput) PASS、driver chat も問題なし
- **採用**: SGLang launch invocation を以下に確定:
  ```
  PYTHONUTF8=1 python -m sglang.launch_server \
      --model-path Qwen/Qwen3-8B \
      --host 0.0.0.0 --port 30000 \
      --quantization fp8 \
      --mem-fraction-static 0.85 \
      --max-total-tokens 2048 \
      --max-running-requests 1 \
      --disable-cuda-graph \
      --disable-piecewise-cuda-graph
  ```
- **理由**:
  1. Qwen3-8B BF16 ≈ 16 GB は 16 GB VRAM に静的に fit せず → fp8 必須
  2. RTX 5060 Ti = Blackwell SM120 で SGLang 0.5.10.post1 の piecewise
     CUDA graph capture が sampler.argmax を deadlock させる
     (`scheduler.py:1361 event_loop_overlap` → `forward_batch_generation`
     → `sample` → `forward (sampler.py:107)` → `argmax` CUDA kernel が
     hang して watchdog timeout) → `--disable-piecewise-cuda-graph` で
     回避
  3. throughput ~7.5s/attempt は dry-run smoke の許容範囲 (50 net @
     37.5% acceptance ≈ 17 min、250 net main collection ≈ ~83 min、当初
     runbook 想定 3h より速い)
- **トレードオフ**:
  - CUDA graphs disable で peak throughput はやや低下するが、Blackwell
    + fp8 経路の安定性が確保できるので採取は完走可能
  - Codex review 等で「全 CUDA graph optimisation disable は必要か」と
    指摘される可能性あり。具体的には piecewise だけ disable で十分かは
    今回時間制約で個別検証していない (`--disable-piecewise-cuda-graph`
    + cuda-graph enable の組み合わせは未試行)。次セッションで `+`
    cuda-graph enable + piecewise disable を benchmark する余地あり。
- **影響範囲**:
  - 本セッションの dry-run smoke + main collection + 次回 retrain serving
    起動コマンド (Plan B 採取は base model なので LoRA enable は不要)
  - `g-gear-collection-runbook.md` §2 の SGLang launch command も同
    invocation を採用 (Plan B / future plan で再利用)
  - memory `reference_qwen3_sglang_fp8_required.md` を作成、project 横断
    で参照可能に
- **見直しタイミング**: 
  - SGLang 0.5.11+ release で Blackwell piecewise CUDA graph が修正された時
  - GPU が交換された時 (Blackwell 以外なら従来 v5 invocation で十分)

## DR-3: lexical-5gram の短入力 (char_wb 5-gram empty vocab) fallback は identity

- **判断日時**: 2026-05-18
- **背景**: `TfidfVectorizer(analyzer="char_wb", ngram_range=(5,5))` は全
  入力が 5 文字未満で edge-pad 後も 5-gram を産まない時に空 vocabulary で
  `ValueError("empty vocabulary")` を raise する。
- **選択肢**:
  - A: ValueError を propagate (caller 責任)
  - B: empty vocab を try/except で受け identity 行列を返す (no similarity
    signal とみなす)
  - C: zeros 行列を返す (`_check_kernel` の diagonal=1 assert で失格)
- **採用**: B
- **理由**:
  1. `compute_vendi` 経由で呼ばれた時に identity 行列なら score=N とみなされ
     る ("each item is fully distinct") のが意味的に整合
  2. 採取された focal turn は通常 ≥60 token (filter 済み) なので boundary
     case は test fixture でしか触れない
  3. C は `_check_kernel` で diagonal!=1 で失格になる
- **トレードオフ**: 「全 sample が短い → score=N で diversity 最大」は誤解
  招くが、Plan B では token>=60 filter があるので production では到達不能
- **影響範囲**: 新 test `test_short_inputs_below_5_chars_fallback_identity`
  でこの挙動を明文化、production では filter で除外される旨を docstring に記載
