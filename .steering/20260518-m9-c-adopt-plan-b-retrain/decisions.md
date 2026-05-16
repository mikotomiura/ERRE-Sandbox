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

## DR-5: WeightedTrainer.compute_loss から ``labels`` を pop し HF 内部 CE 重複計算を停止

- **判断日時**: 2026-05-18
- **背景**: v2 retrain (DI-7) で step time が初期 5.35 s/it → 定常 ~13–14 s/it
  に劣化、4000 steps を 8h envelope に収められず 16h19m を要した。
  `src/erre_sandbox/training/train_kant_lora.py:WeightedTrainer.compute_loss`
  (L1690–1704) を読むと、`labels` を `inputs` に残したまま `model(**inputs)`
  を呼んでおり、HF CausalLM が内部で cross-entropy loss を計算する。本実装は
  続けて `compute_weighted_causal_lm_loss(outputs.logits, inputs["labels"],
  weights)` で同じ logits/labels に対して weighted CE を再計算しているため、
  内部 loss は完全に discard されている。
- **副作用の見積もり**:
  - Qwen3-8B vocab=151936 で内部 CE が確保する `shift_logits` 中間 tensor は
    seq=128 / bf16 換算で micro-batch 当たり ~38 MB
  - grad_accum=8 → train step 当たり ~300 MB / eval 1 pass (503 examples) →
    ~19 GB に達する余剰 intermediate
  - DI-7 時点 VRAM 15973/16311 MiB (free 78 MiB) で allocator slow path に
    落ちた仮説と整合
- **選択肢**:
  - A: `inputs.pop("labels")` で labels を取り出してから `model(**inputs)` を
    呼び、`compute_weighted_causal_lm_loss` には local の `labels` を渡す
  - B: `model.forward()` を override して内部 CE を抑止
  - C: `Trainer` の `compute_loss_func` API (Transformers 4.46+) に切替
- **採用**: A
- **理由**:
  1. 3 行 diff、loss 数式・autograd graph・gradient は不変 (`compute_weighted_
     causal_lm_loss` は Codex HIGH-C verbatim、入力 tensors は同じ)
  2. HF CausalLM の `forward(..., labels=None)` は `output.loss=None` で返るが
     `output.logits` は変わらない → `compute_weighted_causal_lm_loss` への
     入力に副作用なし
  3. B は GPL-3.0 risk と保守コスト、C は subclass パターン全廃で diff 過大
- **トレードオフ**:
  - HF Trainer の `prediction_step` は `compute_loss(model, inputs,
    return_outputs=True)` を呼ぶため、`return_outputs=True` 経路でも
    `(weighted_loss, outputs)` を返せる必要があるが、新 compute_loss は
    引き続き同じ tuple を返すため API contract は不変
- **影響範囲**:
  - `_run_trainer_weighted` の `WeightedTrainer` 内 compute_loss のみ
  - 既存 `tests/test_training/test_weighted_trainer.py` は `compute_weighted_
    causal_lm_loss` の pure function を直接呼ぶため、本パッチに対する
    regression を起こさない (45 件 PASS 実測)
  - DA-14 thresholds / weighting 数式 / DA-15 corpus gate / eval criteria は
    一切変更しない
- **未確定**: 実 runtime 改善幅は本セッションで未測定。G-GEAR で
  `--weighted --max-steps 50 --save-steps 100000 --eval-steps 100000` の
  前後比較が必要。
- **見直しタイミング**: Plan B retrain benchmark 後、改善幅が想定下限
  (数%) を下回り Plan B envelope に収まらない場合、R-3 (NF4+LoRA backward
  slow path 仮説) の再評価。

## DR-6: TrainingArguments に `prediction_loss_only=True` を明示 (副パッチ)

- **判断日時**: 2026-05-18
- **背景**: HF Trainer の eval は default `prediction_loss_only=False`。
  `compute_metrics=None` のときは Trainer 実装によって logits accumulation を
  内部で抑制している可能性もあるが、明示的に True を立てれば short-circuit
  経路が確実に取られる。Plan B `EarlyStoppingCallback(metric_for_best_model="eval_loss")` は eval_loss のみを参照するため、副作用なし。
- **採用**: TrainingArguments の eval_kwargs に `prediction_loss_only=True`
  を追加 (`per_device_eval_batch_size=1` と同 dict)
- **理由**:
  1. DR-5 と独立に効く可能性のある eval-side の小最適化
  2. 1 行追加、revert コストは最小
  3. eval_loss は引き続き `metrics["eval_loss"]` で取得可能、`train_metadata.json` への記録経路・EarlyStoppingCallback 経路に副作用なし
  4. Transformers 4.57.6 (AGENTS.md) で `prediction_loss_only` は安定 API
- **控えめな見積もり**:
  - HF Trainer の version / 実装次第で `compute_metrics=None` 時には既に同等
    動作の可能性もあり、**「必ず eval 30–50% 改善」とは想定しない**
  - 効果は short eval benchmark (主パッチ単独 vs 主+副パッチ) で確認
- **トレードオフ**: 将来 compute_metrics (BLEU / perplexity 等) を導入する
  時には `False` に戻す必要があるが、その時点で revisit。
- **影響範囲**: TrainingArguments の eval_kwargs dict のみ。final
  `trainer.evaluate()` は不変、eval_loss 記録の信頼性を優先。
- **見直しタイミング**: short benchmark で差が見えない場合、別 PR で
  `prediction_loss_only` 行のみ revert (主パッチは維持)。

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
