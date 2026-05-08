# 重要な設計判断 — m9-c-spike (Codex 11 回目 review HIGH 4 / MEDIUM 6 / LOW 3 全反映)

> 9 ADR (CS-1〜CS-9) を Codex `gpt-5.5 xhigh` independent review (198K tok、
> Verdict: ADOPT-WITH-CHANGES、`codex-review-m9-c-spike.md` verbatim 保存) 全
> 反映で起票。各 5 要素 (決定 / 根拠 / 棄却 / 影響 / re-open 条件)。

## CS-1 — SGLang version pin: `sglang==0.5.10.post1` (Codex HIGH-1 / MEDIUM-1)

- **決定**:
  - `sglang==0.5.10.post1` (PyPI 2026-04-08 latest stable、no v0.6 stable found)
  - launch args 固定:
    ```bash
    python -m sglang.launch_server \
      --model qwen/Qwen3-8B \
      --enable-lora \
      --max-loras-per-batch 3 \
      --max-lora-rank 8 \
      --max-loaded-loras 3 \
      --port 30000
    ```
  - CUDA build: G-GEAR の RTX 5060 Ti 16GB は CUDA 12.x、SGLang 0.5.10.post1
    の公式 wheel が CUDA 12.4 / 12.6 でビルドされている前提
- **根拠**:
  - Codex HIGH-1: "v0.3+ stable" は too vague、specific version pin 必須
  - Codex MEDIUM-1: PyPI latest = `0.5.10.post1` (2026-04-08)、v0.6 stable
    は web 検索で発見されず
  - SGLang docs (https://sgl-project.github.io/advanced_features/lora.html)
    は current release で multi-LoRA / dynamic load/unload / pinned adapters /
    overlap loading を documented
- **棄却**:
  - "v0.3+" / "v0.5+" 等 vague な指定 (Codex HIGH-1 で audit 不能)
  - SGLang nightly / dev branch (production reproducibility 欠落)
  - vLLM への即 fallback (DB3 の SGLang-first 方針と矛盾、HIGH-2 整合)
- **影響**:
  - `pyproject.toml` の `[inference]` extra に `sglang==0.5.10.post1` 固定
  - G-GEAR install 手順が CS-1 launch args を逐語使用
  - Phase K α 内で `--enable-lora` 起動確認 (failed なら CS-1 re-open)
- **re-open 条件**:
  - SGLang v0.6 stable が release され、v0.5.10.post1 で発見できない bug fix
    がある場合
  - G-GEAR で CUDA 12.x SGLang 0.5.10.post1 wheel install 失敗
  - launch args が pinned LoRA / max-loaded-loras 等で v0.5.10.post1 と
    incompatible

---

## CS-2 — SGLang adapter API: load/unload + internal client-state、`list_adapters()` 削除 (Codex HIGH-1)

- **決定**:
  - `SGLangChatClient` は `_loaded: dict[str, LoRAAdapterRef]` を内部 state
    として保持
  - `load_adapter(ref)` / `unload_adapter(name)` の HTTP response (2xx) で
    state update
  - `list_adapters()` は **削除** (current SGLang 0.5.10.post1 docs に該当
    endpoint なし、closed issue #12221 で confirm)
  - serialization: `LoRAAdapterRef.adapter_name` → SGLang `lora_name`、
    `weight_path` → `lora_path`、`pinned` → `pinned` (LOW-3 整合)
- **根拠**:
  - Codex HIGH-1: SGLang docs は `POST /load_lora_adapter` / `POST
    /unload_lora_adapter` のみ documented、`GET /list_lora_adapters` 該当なし
  - SGLang issue #12221 (closed): "no way to query loaded adapters" を report、
    docs はその後も list endpoint を加えていない
  - load/unload response payload に `loaded_adapters` field が含まれる
    (Codex HIGH-1 確認)、reconciliation 経路は十分
- **棄却**:
  - 想定の `GET /list_lora_adapters` (documented でない、HIGH-1 で fragile と
    判定)
  - `GET /v1/models` 流用 (verified version-dependent、CS-1 pin で確認後に
    CS-2 re-open)
- **影響**:
  - `src/erre_sandbox/inference/sglang_adapter.py` から `list_adapters()`
    method 削除、`loaded_adapters` property (client-side state) で置換
  - `tests/test_inference/test_sglang_adapter.py` で load → loaded_adapters →
    unload の state reconciliation を test
- **re-open 条件**:
  - SGLang upstream が `GET /list_lora_adapters` documented endpoint を追加
  - production で internal state と server actual state の divergence 発生
    (debugger / health check 用に server-side query が必要になった場合)

---

## CS-3 — Phase β 着手 gate: realized `min_examples` + contamination assertion (Codex HIGH-3)

- **決定**:
  - Phase β real training 着手前に `assert_phase_beta_ready()` で hard-fail
    gate を強制:
    1. `epoch_phase=evaluation` 行 → `EvaluationContaminationError`
    2. `individual_layer_enabled=True` 行 → `EvaluationContaminationError`
    3. `ALLOWED_RAW_DIALOG_KEYS` に `individual_layer_enabled` 未追加 →
       `BlockerNotResolvedError` (silent proceed 禁止、`m9-individual-layer-
       schema-add` follow-up 待ち)
    4. `len(build_examples(persona_id="kant"))` < `min_examples` →
       `InsufficientTrainingDataError`
  - `min_examples = 1000` (literature-based、Codex Prior art 3 参照、
    P-Tailor / BIG5-CHAT / Anthropic persona vector の survey)
- **根拠**:
  - Codex HIGH-3: "~2500 turn" は estimate のみ、build_examples が
    evaluation rows / non-Kant assistant rows / malformed contexts / empty
    utterances / future `individual_layer_enabled=true` rows を discard
  - Codex Prior art 3: 2500 turn は universal sufficient ではない、BIG5-CHAT
    は 100k dialogues、P-Tailor は curated trait-specific data
  - DB11 (PR #145): `individual_layer_enabled=false AND
    evaluation_epoch=false` の training enforcement は **必須**、silent skip
    は contamination prevention 違反
  - 1000 example は ERRE-Sandbox spike scope に対する **operational SLO**
    (literature constant ではない、CS-3 で operational decision として記録)
- **棄却**:
  - "~2500 turn" estimate を training sufficiency 判定に直接使う (HIGH-3 で
    discarded)
  - `individual_layer_enabled` absent を silent skip (HIGH-3 で blocker 化)
  - BIG5-CHAT 100k dialogues 必須 (overshoot、bounded spike scope と矛盾)
- **影響**:
  - `src/erre_sandbox/training/train_kant_lora.py` 入口に
    `assert_phase_beta_ready()` 必須
  - `blockers.md` に `m9-individual-layer-schema-add` を hard blocker 記録
  - `tests/test_training/` で 4 種類の hard-fail を test
- **re-open 条件**:
  - `min_examples=1000` で Phase β quality signal が得られない場合
    (M9-eval Tier B Vendi / Big5 ICC で persona-discriminative ではない)
  - `m9-individual-layer-schema-add` 完了後、DB11 enforcement が production
    で稼動した状態で `individual_layer_enabled` field の usage 体感が変わった
    場合

---

## CS-4 — VRAM budget: gradient_checkpointing + double quant + memory logging (Codex MEDIUM-3)

- **決定**:
  - `gradient_checkpointing=True` 強制
  - `bnb_4bit_use_double_quant=True` (nested quantization)
  - `batch_size=1`, `gradient_accumulation_steps=8`, `seq_length=2048`
    (initial config)
  - `nvidia-smi` peak memory logging を training entry point に組込
  - VRAM budget (実測前 estimate):

    | 項目 | VRAM |
    |---|---|
    | Qwen3-8B NF4 + double quant | ~5.0GB |
    | LoRA rank=8 adapter | ~50MB |
    | gradient (gc=True) | ~1.5GB |
    | optimizer state (LoRA params only) | ~0.2GB |
    | activation (seq=2048, batch=1) | ~1.5GB |
    | buffer | ~0.5GB |
    | **合計** | **~8.7GB** |
    | **headroom (16GB - 8.7)** | **~7.3GB** |
- **根拠**:
  - Codex MEDIUM-3: VRAM estimate is plausible but optimistic、実測必須
  - HF benchmark (https://huggingface.co/blog/4bit-transformers-bitsandbytes):
    7B 8-bit + GC at seq1024 → OOM、4-bit NF4 + GC → passes
  - TRL doc (https://huggingface.co/docs/trl/reducing_memory_usage):
    gradient_checkpointing は memory-positive、compute-negative (training
    time +20-30%)
  - double quant で base model VRAM ~10% 削減 (M9-B DB1 alternatives 参考)
- **棄却**:
  - `gradient_checkpointing=False` (8-bit でも seq1024 で OOM、Codex MEDIUM-3
    quote)
  - `bnb_4bit_use_double_quant=False` (10% headroom 損失、marginal 領域で
    意味なし)
  - `batch_size=2` (gradient memory ~2x、headroom 不足リスク)
  - `seq_length=4096` (activation memory ~2x、initial では risky)
- **影響**:
  - `src/erre_sandbox/training/train_kant_lora.py` の training config に
    上記固定
  - peak memory > 12GB 観測時は CS-4 re-open (実測値で revised config 起票)
  - Phase K β で実測値を CS-4 の amendment に追記
- **re-open 条件**:
  - 実測 peak memory > 12GB → batch / seq / accumulation 再調整
  - CUDA fragmentation で long-context generation が不安定 → seq_length 縮小
  - SGLang serving 時の base + 3 active adapters が VRAM budget を超過 →
    `--max-loaded-loras` 縮小

---

## CS-5 — rank=8 は continuity hypothesis、universal adequacy 主張せず (Codex MEDIUM-4)

- **決定**:
  - 本 spike では **rank=8** を使用 (M9-C-adopt の "rank=8 統一 spike" との
    continuity)
  - rank=8 が **universally adequate** という主張は **しない** (continuity
    hypothesis のみ)
  - rank sweep (4 / 8 / 16 / 32) は **M9-C-adopt 範囲**、本 spike では実施せず
- **根拠**:
  - Codex MEDIUM-4: LoRA Land (https://arxiv.org/abs/2405.00732) と P-Tailor
    (https://arxiv.org/abs/2406.12548) は LoRA を practical for specialization
    として支持するが、universal best rank は establish しない
  - M9-B DB2: M9-C-spike rank=8 / M9-C-adopt rank=8 統一 spike + rank sweep
  - rank=4 (v2 案) では adapter expressivity が不足する可能性、persona-
    conditional adaptation の確実性に懸念
- **棄却**:
  - rank=4 採用 (v2 案、M9-C-adopt 統一 spike continuity 失う)
  - rank=16 採用 (M9-C-adopt 統一 spike rank=8 と乖離)
  - rank sweep を本 spike 内 (scope creep、M9-C-adopt 領域)
- **影響**:
  - `src/erre_sandbox/training/train_kant_lora.py` の `LoraConfig` で `r=8`
  - SGLang launch args の `--max-lora-rank 8`
  - `decisions.md` CS-5 に「rank=8 は spike continuity hypothesis であり、
    universal adequacy 主張ではない」を明示
- **re-open 条件**:
  - Phase K β 実測で rank=8 が persona-conditional adaptation に明らかに
    不足 (Tier B Vendi / Big5 ICC で baseline と差異なし)
  - M9-C-adopt rank sweep 実施後、rank=8 が optimal でないと empirical 確認

---

## CS-6 — PEFT directory direct load 試験先行、conversion 失敗時のみ自前 (Codex MEDIUM-2)

- **決定**:
  - Phase K α 内で `peft.save_pretrained(<path>)` 出力 (`adapter_config.json`
    + `adapter_model.safetensors`) を SGLang `/load_lora_adapter` に **直接
    load** する compatibility test を最優先
  - 直接 load 通れば conversion script は **起草しない** (premature
    optimization 禁止)
  - 直接 load 失敗時のみ conversion script 起草、specific failure mode を
    CS-6 amendment に記録
- **根拠**:
  - Codex MEDIUM-2: SGLang docs は "adapters must follow PEFT format" と
    documented、PEFT `save_pretrained()` は SGLang が expect する format を
    直接 emit
  - HuggingFace PEFT doc (https://huggingface.co/docs/peft/v0.17.0/
    developer_guides/checkpoint): `adapter_model.safetensors` (or `.bin`) +
    `adapter_config.json` を 1 directory に
  - 自前 conversion は specific failure mode が判明するまで投資価値低い
- **棄却**:
  - 自前 conversion script を初手で起草 (premature optimization、HIGH 反映で
    discarded)
  - PEFT format ではなく vLLM-native format を base にする (DB3 SGLang-first
    と矛盾)
- **影響**:
  - `tests/test_inference/test_sglang_adapter.py` の Phase K α smoke test に
    PEFT direct load を含む
  - 失敗時は CS-6 amendment + conversion script 別タスク化 (Phase J 範囲外)
- **re-open 条件**:
  - Phase K α で PEFT direct load 失敗 (HTTP 4xx / format reject 確認)
  - Qwen3-8B specific target_modules (q_proj / k_proj / v_proj / o_proj) が
    SGLang LoRA loader と incompatible

---

## CS-7 — N=3 collapse 検出: SGLang `bench_serving` + 4 trigger condition (Codex HIGH-4)

- **決定**:
  - benchmark tool: SGLang `bench_serving` harness (https://docs.sglang.io/
    developer_guide/bench_serving)
  - baselines (3 種実測):
    - no-LoRA (base Qwen3-8B、`--enable-lora` なし)
    - single-LoRA Kant only
    - N=3 multi-LoRA (Kant + 2 mock pinned adapters)
  - 同一 prompts / 同一 sampling (`--seed 0` 等 deterministic)
  - server constraints: `--max-loras-per-batch 3 --max-lora-rank 8
    --max-loaded-loras 3 --max-concurrency 3`
  - metrics: TTFT p50/p95/p99 / ITL / e2e latency / output tokens/s /
    HTTP error rate / queue wait (if available)
  - **collapse trigger (any one of)**:
    - p95 e2e > 2x single-LoRA baseline
    - output tok/s < 70% baseline
    - adapter-misrouting (Kant prompt → Nietzsche/mock adapter response、
      sentinel で検出)
    - request timeout (1 件でも)
- **根拠**:
  - Codex HIGH-4: "no collapse" は subjective、benchmark contract 必須
  - SGLang `bench_serving` は throughput / TTFT / ITL / e2e latency / request
    rate / max concurrency / JSONL 出力を documented support
  - 2x p95 と 70% throughput は ERRE-Sandbox operational SLO (literature
    constant ではない、Codex 推奨 benchmark で baseline と相対比較)
- **棄却**:
  - 自前 async benchmark harness (Codex HIGH-4 で discarded、SGLang 公式 tool
    が同等以上を support)
  - "collapse なし" の subjective 判定 (HIGH-4 で discarded)
  - p95 1.5x / output 80% 等 lenient threshold (production headroom 不足)
- **影響**:
  - Phase K β G-GEAR 実走で `bench_serving` を 3 baseline で実行
  - 結果 (JSONL) を `data/eval/spike/m9-c-spike-bench/` に保存 (新規 path)
  - CS-7 amendment に実測値 (TTFT / ITL / e2e p50/p95/p99 / tok/s / error rate)
    を記録
  - 4 trigger のいずれか fire → DB3 vLLM fallback fire (CS-8 整合)
- **re-open 条件**:
  - 実測で 4 trigger threshold が tight すぎ (false positive 多発)
  - SGLang upstream の new release で bench_serving API が変更
  - production workload mix が spike benchmark と乖離 (mix を ADR amendment)

---

## CS-8 — DB3 fallback trigger: API failure / FSM regression 即時、latency は real adapter confirmation 必須 (Codex HIGH-2)

- **決定**:
  - **即時 fire (mock-LoRA でも fire)**:
    - SGLang `--enable-lora` 起動失敗
    - `/load_lora_adapter` が PEFT format 拒否 (HTTP 4xx/5xx)
    - M5 resonance / ERRE FSM が SGLang LoRA 経路で regression
  - **diagnostic 扱い (real Kant adapter で confirmation 必要)**:
    - adapter swap latency >500ms (cold/warm/pinned/unpinned/no-LoRA baseline
      と比較した repeated measurement)
    - N=3 throughput collapse の閾値未達 (CS-7 4 trigger)
  - mock-LoRA で観測された latency / collapse は **diagnostic**、real Kant
    rank=8 で confirmation 後に fire 判断
- **根拠**:
  - Codex HIGH-2: Mock-LoRA は API proof / format validation / FSM smoke 専用
    で、DB3 fallback latency に **equivalent ではない**
  - SGLang docs: overlap loading が adapter-load overhead を reduce する一方で
    batching fragmented 時 TTFT を悪化させる workload-dependent な現象あり
  - P-LoRA / ServerlessLoRA prior art (https://arxiv.org/abs/2512.20210 /
    https://arxiv.org/abs/2505.14468): adapter loading は cold-start /
    fragmentation issue、fixed constants ではない
- **棄却**:
  - mock-LoRA latency 単独で DB3 fallback fire (HIGH-2 で discarded)
  - real adapter confirmation なしで vLLM migration trigger (premature)
- **影響**:
  - Phase K α で API failure / format reject / FSM regression のみ即時 fire
    判断
  - Phase K β real Kant adapter で latency / N=3 collapse confirmation
  - `data/eval/spike/m9-c-spike-bench/` の JSONL に cold/warm/pinned/unpinned/
    no-LoRA baseline 全 5 condition の repeated measurement 記録
- **re-open 条件**:
  - production で adapter-misrouting (CS-7 trigger 3) が頻発、即時 fire
    threshold に格上げ必要
  - 500ms threshold が production SLO と乖離

---

## CS-9 — Mock-LoRA: PEFT default no-op + refusal guard + metadata sentinel + tools/spike/ 隔離 (Codex LOW-1 / LOW-2 / LOW-3)

- **決定**:
  - **配置**: `tools/spike/build_mock_lora.py` (`src/` 配下にしない、production
    code 外、誤運用リスク削減)
  - **初期化**: PEFT default `init_lora_weights="default"` (B=0 で identity
    transform、Kant adapter と base model 出力は同一)
  - **metadata sentinel** (output safetensors に embed):
    ```json
    {"mock": "true", "base_model": "qwen/Qwen3-8B", "rank": "8",
     "target_modules": "q_proj,k_proj,v_proj,o_proj",
     "init_lora_weights": "default", "git_sha": "<runtime>"}
    ```
  - **refusal guard** (`build_mock_lora()` 内):
    - `output_dir` が `src/` で始まる → ValueError
    - `output_dir` が "checkpoint" または "production" を含む → ValueError
  - **production loader 連携**: `SGLangChatClient.load_adapter()` が
    `mock=true` metadata を検出 → warning log (production block ではない、
    spike だけ load 可)
- **根拠**:
  - Codex LOW-1: `tools/spike/` 隔離 + metadata + refusal guard は誤運用 risk
    削減に有効
  - Codex LOW-2: PEFT default no-op (identity transform) は random A/B より
    safe、FSM smoke test を confuse しない
  - Codex LOW-3: SGLang naming は `lora_name` / `lora_path` / `pinned`、
    internal ERRE naming はその boundary で rename
- **棄却**:
  - random A/B init (LOW-2 で discarded、FSM smoke test confuse リスク)
  - HF hub borrow weight (base model family / rank ceiling / target_modules
    全一致が必要、自前 generate より control 弱い)
  - `src/erre_sandbox/training/build_mock_lora.py` 配置 (LOW-1 で discarded、
    production code 内に mock 混入リスク)
  - production loader での hard block (mock 経由 spike 自体不能になる)
- **影響**:
  - `tools/spike/build_mock_lora.py` 新設 (Phase J)
  - `tests/test_tools/test_build_mock_lora.py` で refusal guard / metadata /
    no-op assertion test (4 件)
  - Phase K α で mock-LoRA を SGLang load → identity transform 確認 (Kant
    prompt + mock = base model 出力)
- **re-open 条件**:
  - production で mock-LoRA が誤 load されて user-facing 影響 → hard block
    (warning から block に格上げ)
  - PEFT default が将来 non-identity init に変更 → CS-9 amendment

---

## CS-summary

- 本 ADR **9 件** で Codex `gpt-5.5 xhigh` **11 回目** review (2026-05-08
  m9-c-spike v1+v2+comparison v3 review、198K tok、ADOPT-WITH-CHANGES、
  HIGH 4 / MEDIUM 6 / LOW 3) 全件対応
- M9-B DB1-DB11 + 第3の道 ADR との衝突: 無し (CS-1〜CS-9 はすべて DB1-DB11
  refinement / continuity)
- M9-eval ME-1〜ME-15 (P4a Tier B 反映済) との衝突: 無し
- Phase α (Mock) / Phase β (Real) の 2 phase 設計を CS-3 で formal 化
- Codex 切出の認識補正:
  - HIGH-1: SGLang `list_adapters()` documented endpoint なし → API 削除
  - HIGH-2: Mock latency は decisive ではない → API failure / FSM のみ即時 fire
  - HIGH-3: "~2500 turn" → realized example 数 + contamination assertion
  - HIGH-4: "no collapse" → SGLang `bench_serving` + 4 trigger
- 直近 7 連続 (P3a-finalize / Phase 2 run0 / CLI partial-fix / run1 calibration
  / ME-9 trigger / P4a Tier B / m9-c-spike) で Claude solo 検出不能の HIGH を
  毎回切出した empirical 実績、本 spike も同質補正
