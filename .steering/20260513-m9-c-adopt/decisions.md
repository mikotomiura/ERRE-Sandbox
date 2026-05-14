# 重要な設計判断 — m9-c-adopt Phase A (Codex 12 回目 review HIGH 4 / MEDIUM 6 / LOW 3 全反映)

> 10 ADR (DA-1〜DA-10) を Codex `gpt-5.5 xhigh` independent review (Verdict:
> **ADOPT-WITH-CHANGES**、`codex-review.md` verbatim 保存) 全反映で起票。
> 各 5 要素 (決定 / 根拠 / 棄却 / 影響 / re-open 条件)。

---

## DA-1 — Rank sweep 範囲 `{4, 8, 16}` + conditional rank=32 tail-sweep + `--max-lora-rank >= 16` (Codex HIGH-1 / MEDIUM-3 反映)

- **判断日時**: 2026-05-13
- **背景**: CS-5 留保 (rank=8 continuity hypothesis) を adopt phase で
  empirical closure する必要。v1 では rank ∈ {4, 8, 16, 32} の 24h sweep
  を提案、v2 reimagine では {8, 16} hypothesis-confirm のみで 10h、
  comparison で {4, 8, 16} (18h) を hybrid 候補。Codex HIGH-1 が rank=32
  permanent exclusion を risky と判定、conditional tail-sweep trigger +
  SGLang launch arg `--max-lora-rank >= 16` を要求。
- **決定**:
  - default sweep: `rank ∈ {4, 8, 16}`、compute 18h (G-GEAR overnight × 2-3)
  - **conditional rank=32 tail-sweep trigger** (HIGH-1):
    1. Phase B で rank=16 が **throughput PASS** だが **Vendi / ICC /
       Burrows のいずれか 1+ が threshold 未達** (= signal saturate
       未達) → rank=32 tail-sweep 起動
    2. または rank=8→16 で sharp gain (PLORA-like rank sensitivity)
       観察 → rank=32 tail-sweep 起動
    3. tail-sweep の VRAM peak monitor (`nvidia-smi`) + early abort
       (peak > 14GB で kill)
  - **SGLang launch arg amendment** (HIGH-1): CS-1 の `--max-lora-rank 8`
    を `--max-lora-rank 16` (rank=32 fire 時は `--max-lora-rank 32`) に
    amendment、`docs/runbooks/m9-c-adapter-swap-runbook.md` (DB8) に
    Phase B 開始時の amendment 手順を記載
  - **採用基準** (4 軸 intersection、HIGH-2 反映):
    - Vendi semantic effect size (Cohen's d) point + bootstrap CI lower
      bound > 0、direction = "LoRA-on < no-LoRA"
    - Big5 ICC(C,k) ≥ 0.6 point + CI lower bound ≥ 0.6
    - Burrows Δ reduction ≥ 10% point + CI lower bound > 0
    - bench throughput ≥ 70% baseline ceiling
    - smaller rank 優先
- **根拠**:
  - **HIGH-1** (Codex): "PLORA's Qwen2.5-7B sweep found task-dependent
    optima including rank 32, and P-React reports rank-sensitive
    personality modeling" → rank=32 permanent exclusion は risky
  - LoRA Land (arxiv:2405.00732) は rank=8 を 310 model で採用、
    practical anchor として有効
  - PLORA (openreview:azsnOWy9MZ) で Qwen2.5-7B では task-dependent
    optima rank=16/32 観察
  - P-React (aclanthology:2025.findings-acl.328) で personality modeling
    の rank sensitivity 報告
  - SGLang docs (sgl-project.github.io/advanced_features/lora.html):
    `--max-lora-rank` が serving 時の rank ceiling、rank=16 を実際に
    serving するには amendment 必須
- **棄却**:
  - **rank ∈ {4, 8, 16, 32} 全 sweep** (v1): 24h compute、rank=32 は
    VRAM headroom 圧迫 + cost-benefit poor、conditional re-open で
    十分 (HIGH-1)
  - **rank ∈ {8, 16} hypothesis-confirm のみ** (v2 reimagine): CS-5
    closure 不完全、rank=4 を見ない (smaller adapter で持続性能を
    取れる持続テスト不足)
  - **binary search** (rank=8 → 16 → 12 → 14): PEFT/unsloth default が
    powers-of-2、literature 比較不能
- **影響**:
  - `requirement.md` AC-1 修正済 (rank `{4, 8, 16}` + conditional + arg)
  - `design-final.md` A-1 / 既存 CS-* との整合性確認
  - `docs/runbooks/m9-c-adapter-swap-runbook.md` (DB8) に Phase B 着手
    前 `--max-lora-rank` amendment 手順を別 PR で追加
  - Phase B compute budget: 18h (G-GEAR overnight × 2-3)、tail-sweep
    fire 時 +6h
- **re-open 条件**:
  - rank=8 / 16 全て Tier B persona-discriminative でない (= LoRA 自体
    が機能しない) → CS-5 re-open + DB3 re-arm 検討
  - rank=16 throughput PASS だが Vendi/ICC/Burrows のいずれか未達 →
    rank=32 tail-sweep fire
  - rank=8 → 16 で sharp gain (effect size delta > 0.5) → rank=32
    tail-sweep fire

---

### DA-1 amendment 2026-05-13 (M9-C-adopt Phase B 着手時、CS-1 `--max-lora-rank` pin 拡張)

- **amendment 日時**: 2026-05-13 (Phase B 着手時、Codex HIGH-1 反映実施)
- **背景**: DA-1 で rank ∈ {4, 8, 16} default sweep + conditional rank=32
  tail-sweep を確定したが、M9-C-spike CS-1 で pin した `--max-lora-rank 8`
  では SGLang server が rank=16 adapter を runtime で reject する。
  DA-1 影響欄に "CS-1 amendment 候補" と記載していた事項を本 amendment で
  正式化する。
- **amendment 内容**:
  1. SGLang launch SOP の `--max-lora-rank` 値を **8 → 16** に拡張
     (`docs/runbooks/m9-c-adapter-swap-runbook.md` §2 launch v5 invocation
     + 既知の落とし穴 を本 PR で update 済)
  2. CS-1 amendment record は本 ADR 内に記録、M9-C-spike `decisions.md`
     (`.steering/20260508-m9-c-spike/decisions.md` CS-1) は immutable
     として保持
  3. conditional rank=32 tail-sweep fire 時は再 amendment v2 で
     `--max-lora-rank 32` に拡張 (Phase B Step 6 内で別途 record)
- **根拠**: SGLang docs (sgl-project.github.io/advanced_features/lora.html)
  で `--max-lora-rank` が serving 時 rank ceiling、CS-6 (`/load_lora_adapter`
  PEFT format compatibility) を満たすには事前 launch args 整合性必須
- **影響**:
  - Phase B Step 1+3 で rank=4 / rank=16 を rank=16-cap SGLang server に
    load する経路が valid 化
  - DB8 runbook (`docs/runbooks/m9-c-adapter-swap-runbook.md`) §2 を本 PR
    で update
  - production loader manifest (DA-6 / DA-10) の rank field は `{4, 8, 16}`
    accept (tail-sweep fire 時は `{4, 8, 16, 32}`)、`_validate_adapter_manifest()`
    実装で integrate (Phase F)
- **S-2 解消**: 本 amendment + DB8 runbook update により blockers.md S-2
  (CS-1 amendment) は解消

---

## DA-2 — Live path 切替方式: feature flag + Ollama fallback、vLLM は late-binding only (Codex MEDIUM-1 反映)

- **判断日時**: 2026-05-13
- **背景**: 現状 `cognition/cycle.py:46-50` は `OllamaChatClient` のみ
  inject。SGLang spike で `SGLangChatClient` 実装済だが live path 未統合。
  U3 (fp8 serving acceptance) closure までは防衛的 rollout 必要。
  v2 reimagine で vLLM v0.15+ を first-class secondary に追加する案を
  考えたが、Codex MEDIUM-1 が "vLLM dynamic updating is security-sensitive
  and has live issues such as load success not affecting output" を
  指摘、Phase D skeleton 不要と判定。
- **決定**:
  - `ERRE_INFERENCE_BACKEND ∈ {ollama, sglang}` feature flag、default
    `ollama` (A-8 verdict 後に `sglang` flip)
  - `MultiBackendChatClient` wrapper を `inference/server.py` に新設、
    2 backend (Ollama / SGLang) のみ。vLLM は **本 PR では skeleton
    残さず**、DB3 re-arm trigger 経由で別 PR migration
  - fallback: SGLang unreachable → Ollama degraded mode (adapter なし、
    `degraded_to_ollama=True` flag を `CycleResult` に追加)
  - vLLM 現状 evidence + re-arm trigger を本 ADR 内に記録 (MEDIUM-1):
    - vLLM v0.15+ `VLLM_ALLOW_RUNTIME_LORA_UPDATING` (docs.vllm.ai/en/
      v0.15.0/features/lora/) で multi-LoRA runtime load 対応
    - 既知 issue: vllm/issues/18372 で "load success but output
      unaffected" 報告、security-sensitive
    - re-arm trigger: DB3 (SGLang launch fail 3 連続 OR adapter load
      p99 > 500ms 24h sustained OR Tier B quorum 0-of-3 OR memory
      growth > 500MB/1h sustained)
- **根拠**:
  - **MEDIUM-1** (Codex): "vLLM current docs support LoRA and runtime
    loading, but dynamic updating is security-sensitive and has live
    issues such as load success not affecting output. Record current
    vLLM evidence and re-arm triggers in DA-2, but do not add a Phase D
    skeleton."
  - spike CS-8 防衛継続 (mock latency 単独で hard switch は HIGH-2
    で discarded)
  - SGLangChatClient と OllamaChatClient は spike で同形 API (`chat()`
    signature 一致、ChatMessage/ChatResponse 共有) で wrap が cheap
- **棄却**:
  - **vLLM first-class secondary** (v2 Reim-1): security-sensitive +
    本 PR scope tight 優先 (MEDIUM-1)
  - **hard switch** (Ollama 削除): U3 fp8 acceptance 未確認、防衛欠落
  - **per-call routing** (request-level): complexity 過剰、bootstrap
    一回決定で十分
- **影響**:
  - Phase D: `inference/server.py` 新設 (`MultiBackendChatClient`)、
    `cognition/cycle.py:46-50` の import 拡張 (Union 型)
  - `pyproject.toml [inference]` は `sglang==0.5.10.post1` のみ追加 (CS-1
    継承)、vLLM 不要
- **re-open 条件**:
  - SGLang 1 week soak で stable (error rate < 0.1%) → hard switch +
    Ollama 削除を別 PR で検討
  - DB3 re-arm trigger fire → vLLM migration を別 PR で評価

---

## DA-3 — 3 persona expansion 訓練順序: kant → nietzsche → rikyu sequential、min_examples=1000 は SLO 止まり (Codex MEDIUM-5 / MEDIUM-6 反映)

- **判断日時**: 2026-05-13
- **背景**: spike Kant 1 persona only (D-3 defer)。Nietzsche / Rikyu の
  training data 抽出 protocol が未確立。MEDIUM-6 で "min_examples=1000
  remains an SLO, not a quality proof. BIG5-CHAT uses 100,000-dialogue
  setup." と指摘、Tier B 必須化を明文化要求。MEDIUM-5 で persona-specific
  sampling override の compose_sampling() 規約 regression assertion 必須
  と指摘。
- **決定**:
  - 訓練順序: kant → nietzsche → rikyu sequential (G-GEAR single GPU)
  - training data: M9-eval Phase B+C golden baseline (PR #160) から
    `_collect_from_shards()` 経由抽出、各 persona で
    `assert_phase_beta_ready(min_examples=1000)` PASS が **training kick
    許可のみ** (MEDIUM-6)
  - **Tier B 必須化** (MEDIUM-6): persona signal proof は A-6 Tier B で
    独立に validate、min_examples PASS = quality proof ではない。
    BIG5-CHAT 100,000-dialogue 対比で ERRE 1000 examples は SLO 止まり
  - persona-specific sampling override: YAML `default_sampling`
    (kant T=0.60 / nietzsche T=0.85 / rikyu T=0.45) 保持
  - **compose_sampling() regression assertion** (MEDIUM-5): Phase D で
    `MultiBackendChatClient.chat()` 内に `assert isinstance(sampling,
    ResolvedSampling)` 追加、SGLang JSON payload で temperature /
    top_p / repeat_penalty を SGLang options 経由で override 禁止 (test
    で固定)
- **根拠**:
  - **MEDIUM-6** (Codex): "BIG5-CHAT uses a much larger 100,000-dialogue
    setup" → 1000 examples は practical 最低限、persona signal proof
    には不足
  - **MEDIUM-5** (Codex): "Keeping YAML `default_sampling` separate
    from LoRA is the right design" + assertion 必須
  - CS-3 (operational SLO 1000 examples)、CS-5 (continuity hypothesis)、
    CS-4 (single GPU sequential 制約)
  - M9-eval PR #160 で 3 persona × 5 run × 500 turn = 7500 turn が
    golden baseline で揃い済
- **棄却**:
  - **parallel multi-LoRA training**: VRAM 不足、accelerate `--multi_gpu`
    機能不能 (single GPU)
  - **min_examples=1000 = quality gate**: MEDIUM-6 で却下、SLO 止まり
  - **per-persona sampling override の LoRA absorb**: ERRE FSM
    mode-conditional delta が persona ごとに変わると semantic broken
- **影響**:
  - Phase B-C: `training/train_kant_lora.py` を generic 化
    (`train_persona_lora.py`、`--persona kant|nietzsche|rikyu`)
  - Phase D: `tests/test_inference/test_compose_sampling_regression.py`
    新規 (compose_sampling 通過 assertion)
  - Phase E: 各 persona の A-6 Tier B で persona signal proof 必須
- **re-open 条件**:
  - nietzsche / rikyu training data < 1000 examples (M9-eval P3 採取
    quality 問題) → synthetic augmentation か stimulus run 追加
  - persona-specific tuning (different rank per persona) が empirical
    に必要 → DA-1 rank sweep 結果から re-open

---

## DA-4 — Multi-backend bootstrap 失敗時の挙動: 両方 fail → fail-fast、片方 fail → warn + 続行

- **判断日時**: 2026-05-13
- **背景**: Ollama (sidecar process) と SGLang server (WSL2) は独立
  process、bootstrap 順序と失敗時の挙動が未確定。
- **決定**:
  - 両 backend (Ollama + SGLang) 起動失敗 → fail-fast (`bootstrap rc=1`)
  - 片方失敗 → warn (`logger.warning`) して稼働 backend で続行、
    `degraded_to_ollama=True` flag を `CycleResult` に記録
- **根拠**:
  - spike CS-8 で API failure は即時 fire 整合、user-facing 影響を
    観測可能 (degraded mode flag が CycleResult で metric counts)
  - defensive rollout (DA-2) と整合: SGLang fail で Ollama に degrade
    する path がない = fail-fast、両方ある = warn + continue
- **棄却**:
  - **1 backend 失敗で fail-fast**: overly strict、defensive rollout
    に矛盾
  - **両 backend 失敗で silent warn**: no LLM の状態を user に隠す、
    cognition cycle 全 turn fail で原因不明 user 体験
- **影響**:
  - Phase D: `inference/server.py` bootstrap path + health check timing
  - `docs/runbooks/m9-c-adopt-live-bootstrap.md` (新規候補) で bootstrap
    手順を文書化
- **re-open 条件**:
  - ユーザーから degraded mode の semantic に苦情 (e.g. "Ollama
    fallback 中" UI 表示要求) → flag を UI/UX で expose
  - 片方 fail → warn が user-facing で見えにくい → notification 機構を
    追加検討

---

## DA-5 — Multi_lora_3 bench: mock-first + real-after の 2 pass、real-after に churn diagnostic 追加 (Codex HIGH-3 反映)

- **判断日時**: 2026-05-13
- **背景**: CS-7 amendment で N=3 multi_lora_3 は M9-C-adopt scope と
  defer。spike で single_lora vs no_lora のみ実測。Codex HIGH-3 が
  "mock-first + real-after benchmark is necessary but not enough if it
  only runs a short CS-7 harness" + churn diagnostic 必要と指摘。
- **決定**:
  - **A-4a (mock-first、Phase D)**: CS-7 4 trigger NON-FIRE 必須 (現状
    維持)。mock_nietzsche_r8 + mock_rikyu_r8 を `tools/spike/build_mock_lora.py`
    で生成
  - **A-4b (real-after、Phase E)**: HIGH-3 churn diagnostic 追加
    - **steady-state metric** (CS-7 拡張): TTFT p50/p95/p99 / ITL
      p50/p95/p99 / e2e p99 / output tok/s / error rate
    - **churn diagnostic** (新規、HIGH-3):
      - queue wait p99 (SGLang `/get_server_info` 経由 or proxy
        timing)
      - adapter-misrouting count (kant prompt → nietzsche/rikyu
        response 検出、persona sentinel 検査)
      - timeout count
      - **memory growth** (G-GEAR `nvidia-smi --query-gpu=memory.used`
        per-minute sampling、長時間 1h+ stress mode)
    - 結果: `data/eval/spike/m9-c-adopt-bench/multi_lora_3-real-stress.jsonl`
      + `memory_growth.jsonl`
  - **CS-7 4 既存 trigger + 2 新規 trigger 全 NON-FIRE** で AC-4 PASS:
    - p95 e2e > 2x baseline → FIRE
    - output tok/s < 70% baseline → FIRE
    - adapter-misrouting → FIRE
    - timeout 1 件 → FIRE
    - **queue wait p99 > 30s → FIRE** (新規 HIGH-3)
    - **memory growth > 500MB / 1h sustained → FIRE** (新規 HIGH-3)
- **根拠**:
  - **HIGH-3** (Codex): "P-LoRA, S-LoRA, and dLoRA all treat adapter
    churn, heterogeneous ranks, batching, and memory fragmentation as
    first-class serving problems. A mock-first + real-after benchmark
    is necessary but not enough if it only runs a short CS-7 harness."
  - SGLang docs warn: "overlap loading can reduce multi-adapter prefill
    batching and increase TTFT"
  - 引用: arxiv:2512.20210 (P-LoRA)、arxiv:2311.03285 (S-LoRA)、
    osdi24-wu-bingyang (dLoRA)
- **棄却**:
  - **real-only 1 pass**: A-1 + A-2 完了まで scope 開始 block、mock-LoRA
    の API/format proof 価値が捨てられる
  - **mock-only**: real workload で contention behavior 未測 (HIGH-3
    根拠)
  - **CS-7 4 trigger のみ**: HIGH-3 で不十分判定、churn diagnostic 必要
- **影響**:
  - Phase D: A-4a mock bench harness (CS-7 4 trigger 既存利用)
  - Phase E: A-4b real bench harness + 2 新規 trigger + memory growth
    sampling (1h+ stress mode)、`scripts/bench_multi_lora_stress.py`
    新規候補
  - `data/eval/spike/m9-c-adopt-bench/` 配下に追加 jsonl artefact
- **re-open 条件**:
  - mock pass NON-FIRE / real pass FIRE 観察 → mock 識別ロジックを
    CS-7 trigger に追加
  - SGLang upstream で fragmentation 改善 (e.g. 0.6+ 新 scheduling) →
    threshold tighten 再評価

---

## DA-6 — Production loader manifest-grade integrity hard block (Codex HIGH-4 反映)

- **判断日時**: 2026-05-13
- **背景**: spike CS-9 で mock-LoRA `tools/spike/` 隔離 + metadata sentinel
  + refusal guard を確定したが、production loader misroute hard block は
  warning level のみ。Codex HIGH-4 が "weight_path in
  data/lora/m9-c-adopt/ plus is_mock=True is not enough for production
  safety. It must reject path traversal, symlink escape, missing PEFT
  config, .bin pickle fallback, wrong base model, wrong rank, wrong
  target modules, and checksum mismatch." と指摘、manifest-grade
  integrity を要求。
- **決定**:
  - `_validate_production_path()` → `_validate_adapter_manifest()` に
    格上げ (HIGH-4)
  - manifest (immutable local file `data/lora/m9-c-adopt/{adapter_name}/
    manifest.json`):
    ```json
    {
      "adapter_name": "kant_r8_real",
      "persona_id": "kant",
      "base_model": "Qwen/Qwen3-8B",
      "rank": 8,
      "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
      "sha256_adapter_model": "abc123...",
      "training_git_sha": "c1e118c",
      "is_mock": false,
      "created_at": "2026-05-14T09:30:00Z"
    }
    ```
  - **hard block 条件** (HIGH-4 拡張、7 件):
    1. path traversal / symlink escape (`Path.resolve()` で chroot 外
       検出)
    2. `adapter_model.safetensors` 不在 OR `.bin` pickle fallback 検出
    3. manifest `base_model != "Qwen/Qwen3-8B"`
    4. manifest `rank not in {4, 8, 16}` (HIGH-1 tail-sweep fire 時は
       `{4, 8, 16, 32}`)
    5. manifest `target_modules` が CS-1 amendment と不整合
    6. sha256 mismatch (実 file vs manifest 記録) → `AdapterIntegrityError`
    7. manifest `is_mock=True` → `ProductionLoaderRejectError`
  - audit log: `logs/inference/adapter_load_audit.jsonl` に記録、prompt
    内容 / persona prompt 内容は redact (LOW-1 反映)。記録: timestamp /
    manifest_id (adapter_name + sha256) / outcome (load / reject /
    integrity_fail) / backend (sglang / vllm)
  - audit log rotation: daily 50MB、retention 30 day (LOW-1)
- **根拠**:
  - **HIGH-4** (Codex): "Use a signed or at least immutable local
    manifest containing adapter name, persona id, base model, rank,
    target modules, sha256 for adapter_model.safetensors, training git
    sha, and mock flag."
  - 引用: HF PEFT checkpoint docs / safetensors security (
    github.com/huggingface/safetensors)
  - safetensors adoption は `.bin` pickle security risk のため (PEFT
    default safetensors)
  - **LOW-1** (Codex): audit log redaction + rotation 必要
- **棄却**:
  - **path filter + is_mock のみ** (CS-9 status quo): HIGH-4 で不十分
    判定、user-facing misroute risk 残存
  - **manifest なし path-only check**: base model / rank / target
    modules の整合性チェック不能
- **影響**:
  - Phase A-2 / A-7 / A-8 設計に反映 (manifest schema を design-final.md
    に明示)
  - Phase B-C: training 後 post-step で manifest.json 生成 (PEFT
    `save_pretrained()` 後に hook)
  - Phase F: `inference/server.py` `_validate_adapter_manifest()` 実装、
    `AdapterIntegrityError` / `ProductionLoaderRejectError` 例外定義
  - `tests/test_inference/test_production_loader.py` 新規、7 件 reject
    case 全 cover
- **re-open 条件**:
  - production / spike dichotomy が dev workflow を阻害 → policy 緩和 +
    audit log で代替 (e.g. `--allow-mock` dev flag)
  - manifest 改竄検出 needed → manifest 自体に署名 (GPG / cosign) 追加

---

## DA-7 — FSM smoke pass 基準: final mode 一致のみ、reason field 除外

- **判断日時**: 2026-05-13
- **背景**: D-5 (M5 統合 adopt scope)。`_infer_shift_reason()` は LLM
  出力ヒューリスティック、reason field 一致を pass 基準にすると LoRA-on
  で false positive regression。
- **決定**:
  - 8 mode × 3 persona × 1 turn smoke の pass 判定は
    `AgentState.erre.name == expected` のみ
  - `ERREModeShiftEvent.reason` は LoRA で wording drift 可能で除外
  - regression assertion: Ollama baseline (no LoRA) で同一 input → 同一
    final mode (= LoRA は mode FSM を perturbate していない)
  - artefact: `data/eval/spike/m9-c-adopt-fsm-smoke/{persona}_{mode}.json`
- **根拠**:
  - K-α `step5_fsm_smoke.py` パターン踏襲、reason 一致 strict は false
    positive 発生
  - user-facing で reason field を観察する downstream (audit / xAI
    panel) は M9-C-adopt scope では未実装、strict pass 必要なし
- **棄却**:
  - **reason 一致 strict**: false regression、LoRA wording drift で
    無関係に fail
  - **final mode + reason の両方 lenient pass**: regression を見落とす
  - **persona 1 (kant) のみ**: 3 persona 整合性確認不能
- **影響**:
  - Phase E: `tests/test_cognition/test_fsm_smoke_lora.py` 新規 24 cell
  - artefact `data/eval/spike/m9-c-adopt-fsm-smoke/{persona}_{mode}.json`
- **re-open 条件**:
  - production で reason field に依存する downstream (audit / xAI
    panel) ができた場合は strict pass に戻す

---

## DA-8 — Tier B quorum: 2-of-3 (kant/nietzsche) / 2-of-2 (rikyu)、各 metric は point + CI + direction の 3 条件 AND (Codex HIGH-2 / MEDIUM-2 / MEDIUM-4 反映)

- **判断日時**: 2026-05-13
- **背景**: spike CS-5 留保 (rank=8 continuity hypothesis、Tier B で
  empirical 確認)。Codex HIGH-2 が "point thresholds produce
  ADOPT-WITH-CHANGES unless the CI lower bound also clears the threshold
  and all metric directionality is positive versus no-LoRA baseline" と
  指摘。MEDIUM-2 が "rikyu 2-of-2 fallback is acceptable only as a named
  limitation"、MEDIUM-4 が "If Phase E uses ICC(C,k), say it is a
  stability/reliability metric. If adoption wants LoRA persona-fit rather
  than response consistency, also report ICC(A,1) or another
  absolute-agreement measure as diagnostic before DA-9 final verdict" と
  指摘。
- **決定**:
  - **quorum 規則**:
    - kant / nietzsche: 2-of-3 (Vendi + ICC + Burrows Δ)
    - rikyu: 2-of-2 (Vendi + ICC)、Burrows N/A は **named limitation**
      (`Burrows=N/A(tokenizer-unimplemented)`、MEDIUM-2 反映)
  - **各 metric は 3 条件 AND** (HIGH-2 反映):
    1. point threshold 達成
    2. bootstrap 95% CI lower bound が threshold 以上
    3. direction が baseline (no LoRA) と persona-discriminative
       方向 (Vendi: LoRA-on < no-LoRA / ICC: positive / Burrows Δ:
       reduction)
  - **provisional threshold** (HIGH-2 後段で final tightened):
    - Vendi semantic effect size (Cohen's d) ≥ 0.3 (literature small
      shoulder、final pin は P4b/P4c 後)
    - Big5 **ICC(C,k)** ≥ 0.6 (ME-11 stability/reliability metric、
      MEDIUM-4 で明示)
    - Big5 **ICC(A,1)** を diagnostic として併報告 (MEDIUM-4)、persona-fit
      評価で `>= 0.5` (literature shoulder) を target
    - Burrows Δ reduction ≥ 10% (Burrows 1987 / Eder 2016 で 5-15%
      shoulder)
- **根拠**:
  - **HIGH-2** (Codex): "Cohen-style effect-size rules make 0.3 a
    small-to-marginal effect, not a robust persona-discriminative
    shoulder. Koo & Li place ICC 0.6 in 'moderate' reliability, but
    ME-11 already says adoption drift needs absolute-agreement
    semantics" → point + CI + direction の 3 条件 AND 必要
  - **MEDIUM-2** (Codex): rikyu Japanese Burrows N/A は named limitation
    扱い、blocker 化必要
  - **MEDIUM-4** (Codex): ICC(C,k) = stability/reliability、persona-fit
    に ICC(A,1) を diagnostic 併報告
  - 引用: arxiv:2410.16491 (BIG5-CHAT)、pubmed:27330520 (Koo & Li ICC
    guideline)、lakens.github.io statistical_inferences/06-effectsize
  - ME-11 (M9-eval-system) で ICC(C,k) consistency / ICC(A,1) absolute
    agreement の区別を既定
- **棄却**:
  - **point threshold のみ** (HIGH-2 で却下): CI lower bound + direction
    なしでは marginal pass の認定が緩すぎる
  - **3-of-3 strict quorum** (rikyu): Burrows N/A で adopt 永続的阻害
  - **1-of-3 weak quorum**: spurious adopt risk、M9-D で巻き戻し
- **影響**:
  - Phase E: `tier_b_bootstrap_pair.py` consumer (本 PR 改変対象外、
    既存 framework 利用) の output に point + CI lower bound +
    direction の 3 値を確認、必要に応じて consumer 側で組み立て
  - `tests/test_eval/test_tier_b_quorum_persona_conditional.py` 新規
    候補 (persona ごとの quorum count)
  - rikyu `Burrows=N/A(tokenizer-unimplemented)` を blockers.md H-2
    に記録
- **re-open 条件**:
  - rikyu Japanese tokenizer 完成 (`m9-eval-corpus-rikyu-tokenizer`
    完了) → 2-of-3 復活
  - P4b/P4c empirical pin 完了 → provisional threshold を tightened
    pin (DA-11+ で別 ADR)
  - ICC(A,1) diagnostic が ICC(C,k) と乖離 → quorum metric の置換
    検討

---

## DA-9 — Marginal pass の取り扱い: CI lower bound NOT cleared → ADOPT-WITH-CHANGES retrain path (Codex HIGH-2 反映)

- **判断日時**: 2026-05-13
- **背景**: HIGH-2 で point threshold + CI lower bound + direction の
  3 条件 AND を求められ、point は PASS だが CI lower bound が threshold
  未達のケースの operational stance 必要。
- **決定**:
  - **marginal pass 判定**: 3 条件のうち point + direction PASS だが
    CI lower bound が threshold 未達 (e.g. d point=0.35 だが CI
    lower=0.15) → **ADOPT-WITH-CHANGES verdict**
  - retrain path: 別 PR `feature/m9-c-adopt-retrain-v2` で
    - min_examples を 1000 → 3000 に増 (BIG5-CHAT 1/30 規模に近づける)
    - rank を adopted rank で固定
    - stimulus prompt diversity 改善 (M9-eval P3 で新規 prompt 群追加)
  - retrain 後 Tier B 再評価で CI lower bound clear → ADOPT 確定
- **根拠**:
  - **HIGH-2** (Codex): "point thresholds produce ADOPT-WITH-CHANGES
    unless the CI lower bound also clears the threshold and all metric
    directionality is positive versus no-LoRA baseline"
  - spurious adopt を避けつつ scope 不能を起こさない operational stance
- **棄却**:
  - **strict reject** (3 条件全 PASS でなければ REJECT): retrain cost
    high で iteration 困難
  - **marginal も無条件 adopt**: M9-D で巻き戻しリスク
- **影響**:
  - A-8 verdict 判定の precondition
  - ADOPT-WITH-CHANGES 経路は別 PR `feature/m9-c-adopt-retrain-v2` 起票
    必要
  - Phase F の A-8 verdict report に marginal pass 該当 metric を明示
- **re-open 条件**:
  - retrain cycle が 2 回連続で marginal → CS-5 / DB3 re-arm 検討
  - literature update / Vendi sensitivity panel (ME-10) で effect size
    shoulder の再定義 → DA-8 threshold 修正

---

## DA-11 — Phase B Tier B consumer scope narrowing (Phase B 第 3 セッション 2026-05-14、本 session のみ運用、3 第 4 セッションで closure)

- **判断日時**: 2026-05-14 (Phase B 第 3 セッション着手時)
- **背景**: handoff prompt (`next-session-prompt-phase-b-3.md`) の Step 5
  scope は Tier B baseline 算出 (Vendi + Big5 ICC + Burrows Δ) +
  per-rank pilot 採取 (1800 turn) + per-rank metric + bench + DA-1 4 軸
  intersection を本セッション内で完遂と想定。実装着手時に以下のギャップを発見:
  1. **Big5 ICC consumer 未実装**: `compute_big5_icc` ヘルパは存在するが
     DuckDB shard → per-window IPIP-50 administering → ICC の orchestrator
     script が未整備。LLM-backed `PersonaResponder` 実装も別途必要 (no-LoRA
     baseline は Ollama 経由、LoRA-on は SGLang 経由でルーティング切替)
  2. **Big5 ICC 計算規模**: 50 IPIP question × 25 window × 5 run × 4
     condition (no-LoRA + 3 rank) = ~25,000 inference @ ~3-5s/inf =
     **~25-35h compute budget**、本セッションスコープ大幅超過
  3. **Burrows Δ 言語不一致**: kant 発話は de/en/ja 混合 (sample 確認済)
     一方 Burrows reference は de のみ (kant_de.txt)。English Kant
     reference (Cambridge Edition) は M9-eval-system 別 PR scope で未整備
  4. **SGLang LoRA pilot driver 未実装**: 既存 `eval_run_golden` CLI は
     Ollama only、SGLang LoRA adapter ルーティング未対応
- **決定**:
  - **本セッションは以下に scope narrowing**:
    1. **G-GEAR foundational work** を先行: SGLang LoRA pilot driver 新規
       実装 (`scripts/m9-c-adopt/tier_b_pilot.py`)、smoke test、full
       1800-turn pilot 採取 (3 rank × 2 run × 300 turn)
    2. **Vendi lexical-5gram baseline** (no-LoRA) を本セッション中に算出 +
       semantic kernel は Mac post-hoc
    3. **CS-7 per-rank single_lora bench** (rank=4/8/16) を本セッション中
       に実走、no_lora baseline は PR #163 K-β 値 (24.25 tok/s threshold)
       継続利用
    4. **DA-1 採用判定 provisional** (Vendi lexical + throughput + Step 4
       multi_pin qualitative の 2.5 軸) で provisional rank 候補を選定し、
       最終確定は Phase B 第 4 セッションへ defer
  - **Phase B 第 4 セッション scope**:
    1. Big5 ICC consumer 実装 (`scripts/m9-c-adopt/compute_baseline_big5_icc.py`
       + per-rank consumer)、no-LoRA baseline + per-rank LoRA-on の
       full administering compute (~25-35h、Mac master + remote G-GEAR
       split 想定)
    2. Burrows Δ 言語処理判断 (langdetect routing / English ref vendoring
       / N/A fallback の 3 案から選定)
    3. semantic kernel Vendi 再算出 (Mac master 側で MPNet cache 整備)
    4. DA-1 4 軸 intersection で **final** 採用 rank 確定
    5. 採用 rank の production placement + manifest backfill + PR 起票
  - **本セッションは PR 起票しない**: pilot data + baseline + bench + scope
    narrowing 記録の commit + push のみ、PR は Phase B 第 4 セッション
    完了時に統合 PR で起票
- **根拠**:
  - 発見した consumer ギャップ + IPIP-50 compute scale を closure するには
    1 セッションでは不可能 (実装 + ~25-35h compute)
  - SGLang LoRA pilot driver は **G-GEAR でしか書けない / 動かせない**
    foundational piece、本セッションで完遂するのが最も effective
  - Phase A の DA-1 採用基準 (4 軸 intersection、point + CI + direction の
    3 条件 AND) を **緩める** のではなく、 **完遂タイミング** を 1 PR 後に
    ずらす方が ADR との整合性 (HIGH-2 / DA-9 marginal pass の意味) を保つ
  - user feedback (`feedback_batch_integration_over_per_session_sync`) と
    整合: multi-session の中間 PR を増やすより全 phase 完了後に統合 PR で
    一括同期する方を user は好む
- **棄却**:
  - **本セッション内に IPIP-50 administering 強行**: ~25-35h compute は
    G-GEAR 単独では非現実的 (SGLang server + Ollama 混在で VRAM
    contention)、品質も劣化リスク
  - **DA-1 採用基準を 4 軸 → 2 軸 (Vendi + throughput) に恒久的に緩める**:
    Phase A で HIGH-2 (point + CI + direction の 3 条件 AND) を反映した
    ADR の意味が失われる、M9-D で巻き戻し risk
  - **本 session で本 PR を起票 (incomplete data で)**: Mac master review
    判定が provisional になり、後続 PR で final adoption を起票し直す
    overhead が二度手間、user feedback と矛盾
- **影響**:
  - `tasklist.md` Phase B Step 5-7 を本 ADR に従い再構成 (Step 5a 部分達成、
    Step 5b/c/e 完遂、Step 5d/f/Step 6/Step 7 は Phase B 第 4 セッション)
  - `next-session-prompt-phase-b-4.md` 新規起草 (本セッション末尾で)
  - `tier-b-baseline-kant.md` 新規 (Vendi lexical 結果 + Big5/Burrows
    defer 内容明記)
  - `phase-b-progress.md` を本 session 進捗で update
  - DA-1 採用基準 + 4 軸 intersection は **そのまま維持** (DA-11 は
    timing narrowing であり criterion narrowing ではない)
- **re-open 条件**:
  - Phase B 第 4 セッションで Big5 ICC consumer + Burrows 言語処理 +
    semantic Vendi 揃い、DA-1 4 軸 intersection で final 採用 rank 確定
    → DA-11 close
  - IPIP-50 compute が実測で予想より高速 / 軽い (e.g. < 5h) → DA-11 を
    Phase B 第 4 セッションでより縮約 (1 PR 内で baseline + per-rank
    consumer + DA-1 final を完遂)
  - rank=32 tail-sweep fire 条件が provisional Vendi lexical で既に明確に
    判定可能 (e.g. rank=8 → 16 で sharp gain あるいは saturate) →
    Phase B 第 4 セッションの最初に rank=32 training kick (Step 6 earlier
    fire)

---

## DA-10 — Adapter manifest + sha256 checksum + 例外定義 (Codex HIGH-4 + LOW-2 反映)

- **判断日時**: 2026-05-13
- **背景**: spike CS-9 で adapter integrity 検証 deferred。Codex HIGH-4
  で manifest-grade integrity 要求、LOW-2 で checksum latency measurement
  追加要求。
- **決定**:
  - **manifest schema** (DA-6 参照): `data/lora/m9-c-adopt/{adapter_name}/
    manifest.json`、immutable
  - **sha256 checksum**:
    - `adapter_model.safetensors` の sha256 を manifest に記録
    - `load_adapter()` 前に file system 上の sha256 を再計算
    - mismatch → `AdapterIntegrityError`
  - **例外定義**:
    - `AdapterIntegrityError`: sha256 mismatch、manifest 不在、
      manifest 構造異常 (Pydantic ValidationError)
    - `ProductionLoaderRejectError`: hard block 条件のいずれか fire
      (DA-6 の 7 件)
  - **checksum latency measurement** (LOW-2): Phase F で sha256 cold
    load latency を A-8 latency monitoring に追加、CS-8 trace 継続
    (実測 ~50-100ms 推定、500ms ceiling 内だが間接的に CS-8 tighten
    した 50ms threshold を圧迫する可能性 → Phase F で実測値次第で
    re-open)
- **根拠**:
  - **HIGH-4** (Codex): "define AdapterIntegrityError and
    ProductionLoaderRejectError against the manifest contract, not ad
    hoc filesystem inspection"
  - **LOW-2** (Codex): "Hashing adapter_model.safetensors is correct;
    just add the cold-load measurement to Phase F so CS-8 latency
    remains traceable"
  - 引用: github.com/huggingface/safetensors (security adoption)
- **棄却**:
  - **checksum 無し** (silent corruption risk)
  - **md5** (collision risk)
  - **CI-only check** (runtime tampering 検出不可)
- **影響**:
  - Phase B-C: training 後 post-step で manifest.json + sha256 生成
    (`scripts/build_adapter_manifest.py` 新規候補)
  - Phase F: `inference/server.py` `_validate_adapter_manifest()` 実装、
    例外定義
  - `tests/test_inference/test_adapter_manifest.py` 新規、manifest
    validation + sha256 mismatch + 例外 raise を test
  - CS-8 amendment 候補: Phase F の cold load latency 実測値で `< 50ms`
    threshold を sha256 込みで再評価
- **re-open 条件**:
  - checksum 計算が warm load latency を SLO 違反させる (= 50ms
    threshold 超過) → blake2 / sha1 への変更検討
  - manifest 改竄検出 needed → manifest 自体に署名 (GPG / cosign 等)
    追加 (DA-6 re-open と連動)

---

## DA-12 — Phase B 第 4 セッション DA-1 verdict = DEFER (pilot 3-of-4 軸未達、direction failure、Phase E A-6 multi-turn full Tier B へ持ち越し)

- **判断日時**: 2026-05-14 (Phase B 第 4 セッション完了時)
- **背景**: Phase B 第 4 セッションで Big5 ICC consumer (`scripts/m9-c-adopt/compute_big5_icc.py`)
  + Burrows Option A consumer (`scripts/m9-c-adopt/compute_burrows_delta.py`)
  + Vendi semantic 再算出を完遂し、DA-1 4 軸 intersection で final 採用
  rank を確定する scope だった。実測 matrix (`da1-matrix-kant.json`):

  | rank | Vendi semantic | ICC(C,k) | Burrows Δ | throughput | axes PASS |
  |---|---|---|---|---|---|
  | baseline | 30.822 [30.726, 30.928] | 0.9980 [0.9974, 0.9987] | 108.534 [108.10, 109.02] | K-β 34.64 (threshold 24.25) | -- |
  | rank=4 | 33.895 [33.85, 33.94] | 0.9792 [0.967, 0.994] | 113.595 [113.26, 113.93] | 33.82 tok/s | **2/4** (V:FAIL, I:PASS, B:FAIL, T:PASS) |
  | rank=8 | 34.701 [34.67, 34.73] | 0.9843 [0.980, 0.995] | 113.723 [113.31, 114.13] | 33.77 tok/s | **2/4** (V:FAIL, I:PASS, B:FAIL, T:PASS) |
  | rank=16 | 33.685 [33.09, 34.28] | 0.9837 [0.981, 0.994] | 112.564 [112.31, 112.82] | 33.72 tok/s | **2/4** (V:FAIL, I:PASS, B:FAIL, T:PASS) |

  Cohen's d (Vendi rank vs baseline): +2.13 〜 +3.00 (positive = LoRA-on >
  baseline → DA-1 axis 1 direction "LoRA-on < no-LoRA" に **逆方向**).
  Burrows reduction: -3.7% 〜 -4.8% (negative = LoRA-on Burrows > baseline →
  DA-1 axis 3 direction "reduction" に **逆方向**).

- **決定**:
  - **DA-1 verdict = DEFER** (4 軸全達成の smallest rank なし、3 軸達成も
    なし、2 軸達成 (ICC + throughput) で direction failure on Vendi semantic
    + Burrows Δ across all 3 ranks)
  - **production adoption しない**: `data/lora/m9-c-adopt/kant_r{X}_real/`
    への production placement は本 PR 内では実施せず、archive
    (`data/lora/m9-c-adopt/archive/rank_{4,8,16}/kant/`) のみ commit 済。
  - **rank=32 tail-sweep NOT fire**: DA-1 HIGH-1 の fire 条件
    "rank=16 throughput PASS + Vendi/ICC/Burrows いずれか未達 (= signal
    saturate 未達)" は **本質的には scaling signal 問題** の場合に有効。
    本セッションの未達は **direction failure** であり、rank scaling では
    direction inversion を解消できない (rank=32 でも同じ pilot
    methodology を踏襲する限り同じ direction を得る公算が高い)。
  - **provisional rank=8 retained as Phase E protocol carry-over**: K-β
    heritage (PR #163 single_lora baseline) + best ICC stability in pilot
    (0.9843) + throughput parity + smaller-rank-preferred の DA-1 spirit
    に従い、Phase E A-6 (full 7500-turn multi-turn Tier B) で rank=8 を
    primary 評価対象とする。rank=4 / rank=16 も archive 経由で再評価可能。
  - **DA-9 retrain path 開放を Phase D blocker 化**: feature/m9-c-adopt-retrain-v2 別 PR を
    Phase D 着手前の prereq として明示。retrain v2 内容 (DA-9 ベース):
    - min_examples を 1000 → 3000 に増 (DA-3 MEDIUM-6 BIG5-CHAT 1/30 規模)
    - rank=8 (provisional carry-over) で固定
    - stimulus prompt diversity 改善 (M9-eval P3 で新規 prompt 群追加)
    - 追加検討事項: training data の per-turn token length 分布、persona
      自己言及比率、対話 vs 独白比率 (現状の pilot single-turn 出力に
      Kant 様 style が不足する根本原因の調査軸)

- **direction failure の解釈** (本 ADR の hot decision):
  方法論的 confound (methodology) と LoRA 機能不全 (LoRA failure) の
  identifiability に対する判断:

  - **Pilot single-turn vs baseline multi-turn confound (方法論側)**:
    - baseline 5 shards は M9-eval P3 由来の 5 run × ~504 turn = ~2520
      turn の **multi-turn dialog** (focal kant が dialogue 内で
      alternating turn 発話)
    - pilot 6 shards は本 PR で新規実装の `tier_b_pilot.py` 単発 stim →
      kant 1-turn = 300 turn/run × 6 = 1800 turn の **single-turn** 採取
    - single-turn 設計は DA-11 scope narrowing で確定 ("multi-turn は
      Phase E A-6 7500-turn の scope")。pilot ↔ baseline 比較は per-utterance
      level での language/lexical/semantic 特性が **prompt context の長短
      で構造的に異なる**
    - その結果、Vendi (window 内 diversity) も Burrows (per-utterance
      function-word distribution) も pilot は baseline より系統的に高い
      値を取る方向 bias を持つ
  - **LoRA failure の独立可能性**:
    - ICC(C,k) は base model も LoRA-on も > 0.97 で stable 揺るぎなし →
      LoRA が **IPIP-50 self-report** に persona shift を与えていない事実
      も同時に観察される (MEDIUM-4 で「ICC(C,k) は consistency であり
      persona-fit ではない」と明示済)
    - ICC(A,1) は baseline 0.953 → LoRA-on 0.90-0.92 とわずかに下落 →
      LoRA は absolute Big5 vector を **わずかに** 動かしているが、その
      shift は **persona-discriminative shoulder には到達しない** 振幅
    - per-window Big5 mean は baseline / 全 rank で類似 (E~3.0/A~3.4/
      C~3.3/N~3.0/O~3.0) → LoRA が IPIP self-report の neutral midpoint
      応答を実質的に shift していない疑い
  - **identifiability 不能**: 上記 2 因子は pilot data 単独では切り分け
    不可能。Phase E A-6 multi-turn full Tier B で同条件比較すれば
    confound 因子を解消可能 → **本 ADR は明示的に judgment を Phase E
    へ defer**

- **根拠**:
  - **Codex P4a HIGH-2** spirit: point + CI + direction の 3 条件 AND を
    満たさない rank を ADOPT すると M9-D で巻き戻し risk
  - **DA-9 marginal pass**: point + direction PASS で CI 未達のケース
    を retrain path に流す。本 ADR は **direction も未達** なので
    DA-9 strict marginal とは別カテゴリ (direction failure) として扱う
    (ただし mitigation path は DA-9 retrain v2 を流用)
  - **DA-11 spirit**: pilot で identifiability 限界に達したら timing
    narrowing で Phase E に持ち越す (DA-11 criterion narrowing ではなく
    timing narrowing と整合)
  - **user feedback `feedback_batch_integration_over_per_session_sync`**:
    multi-session 中間 PR を増やすより全 phase 完了後の統合 PR で
    一括同期。本 PR は Phase B (pilot infra + DA-12 verdict) の自然な
    closure mark になり、Phase D / E は別 PR が適切
- **棄却**:
  - **strict REJECT (DB3 re-arm 即発)**: ICC + throughput が PASS で
    あり LoRA 自体が機能していないわけではない。DB3 re-arm は overkill
  - **rank=8 hard-ADOPT (2/4 axes)**: HIGH-2 で却下した「point + CI
    で marginal pass を緩める」と同じ罠。direction failure は更に
    厳しく扱う必要
  - **rank=32 tail-sweep fire**: scaling では direction を変えられない
    (上記)
  - **本セッション内に Phase E A-6 7500-turn 追加**: 本 PR scope tight、
    Phase E は別 PR が dependency 整理として正しい
- **影響**:
  - `data/lora/m9-c-adopt/kant_r{X}_real/` への production placement は
    **本 PR scope 外** (archive のみ commit、`is_mock=false` 状態)
  - Phase D (live path 統合 / `MultiBackendChatClient` 等) は本 ADR
    DEFER 状態では fire できない → **Phase D 着手前に feature/m9-c-adopt-retrain-v2 PR が
    merge 必須**、retrain v2 → Phase E A-6 → Phase D の依存順
  - `blockers.md` H-1 (Tier B persona-discriminative) は **partial verify**
    (ICC + throughput) で持ち越し
  - `phase-b-report.md` 新規 (本 PR)、`phase-b-progress.md` Final state
    へ書き換え
- **re-open 条件**:
  - feature/m9-c-adopt-retrain-v2 merge + Phase E A-6 multi-turn full
    Tier B 完遂 → DA-1 4 軸 intersection 再評価 → ADOPT / REJECT / 別案
  - methodology confound 確認のため pilot multi-turn 採取の小 PR が
    先に立ち上がる場合: DA-12 を early close (direction が baseline と
    align すれば DA-1 ADOPT、しなければ DA-9 retrain v2 経路で同じ結末)
  - 別 persona (nietzsche / rikyu) の training が始まり同じ direction
    failure を再現 → MEDIUM-4 LIWC alternative honest framing で
    ICC(A,1) を primary に昇格する検討 (DA-8 amendment 候補)
- **trace**:
  - matrix artefact: `.steering/20260513-m9-c-adopt/da1-matrix-kant.json`
  - inputs: `tier-b-baseline-kant-{vendi-semantic,icc,burrows}.json` + per-rank pilot 同 series
  - script: `scripts/m9-c-adopt/da1_matrix.py` (本 PR で新規)
  - HEAD: 19afb26c4940dd7859ba4331d39189dd79d6df59

---

## DA-13 — DA-12 identifiability empirical follow-up (multi-turn pilot investigation 第 1 セッション 2026-05-14)

> **STATUS**: 採取前 preregister (HIGH-3 反映、`.steering/20260514-m9-c-adopt-pilot-multiturn/decisions.md`
> D-1 にて Codex review 4 HIGH 反映 in full)。採取完了後、本 ADR の "verdict"
> + "後続経路" 行を埋め込み、commit する。

- **判断日時**: 2026-05-14 (`feature/m9-c-adopt-pilot-multiturn-investigation`
  PR 起票時 = 採取前 preregister、verdict 確定時 = 採取完了後 commit)
- **背景**: DA-12 verdict = DEFER で identifiability 不能と認定された 2 因子
  ((a) pilot single-turn vs baseline multi-turn methodology confound、(b)
  LoRA failure on IPIP self-report neutral midpoint) を **multi-turn pilot
  data で empirical に切り分ける**。Codex independent review (verbatim
  `.steering/20260514-m9-c-adopt-pilot-multiturn/codex-review.md`) で
  MODIFY before implementation verdict + HIGH 4 件を反映:
  - **HIGH-1**: 単 protocol change だけでは methodology dominant とまで言えない
    → rank=8 no-LoRA SGLang control 追加、primary comparison は matched baseline
    に切替、Scenario I 結論を「historical baseline-like no-prior multi-turn
    sampling is sufficient to reverse the pilot direction」に弱める
  - **HIGH-2**: pilot 6 windows vs baseline 25 windows の不公平 → matched
    baseline downsampling (`--max-focal-per-shard 300`)
  - **HIGH-3**: scenario criteria を **採取前** preregister (本 ADR 内)
  - **HIGH-4**: post-capture validation query (`validate_multiturn_shards.py`)
    を DA-13 publish acceptance gate に

### 採取前 preregister (HIGH-3、本 ADR 内で固定)

**primary comparison**: rank=8 multi-turn LoRA-on vs **matched baseline**
(historical baseline shard 5 本を `--max-focal-per-shard 300` で downsample、
window-size=100 で 15 windows = pilot multi-turn 18 windows に近い)

**Scenario thresholds**:

| シナリオ | 判定 criterion | 結論 |
|---|---|---|
| **I (reversal confirmed)** | Vendi Δ point < 0 AND CI upper < 0 AND Cohen's d < -0.5 AND Burrows reduction point > 5% AND CI lower > 0 AND >= 1 sister rank in same direction (Vendi + Burrows 両軸) | historical baseline-like no-prior multi-turn sampling protocol が pilot direction を反転させるのに十分 → methodology confound が dominant な候補 |
| **II (no reversal)** | Vendi point >= matched baseline OR CI spans 0 OR Burrows reduction <= 0 OR CI spans 0 | LoRA failure が live hypothesis のまま、retrain v2 必要 |
| **III (mixed)** | Vendi / Burrows の片方のみ reverse、または rank-mixed direction、または thresholds 部分 clear | 両因子寄与、retrain v2 + multi-turn protocol fix の combination 必要 |
| **IV (no information gain)** | 採取 fail (>= 1 shard で focal_observed < 0.9 × focal_target) OR 全 rank で CI width > 1.5× single-turn pilot CI width | identifiability 不能のまま、Phase E A-6 7500-turn が唯一の closure path |

**Acceptance gate (HIGH-4)**: `validate_multiturn_shards.py` の 4 check
(speaker alternation, focal count tolerance band ±5%, no incomplete dialogs,
focal-only consumer simulation) 全 8 shard PASS = DA-13 publish 可能。

### 採取後 commit (verdict 確定 2026-05-14)

**pre-registered verdict = Scenario II (no reversal — LoRA failure remains the
live hypothesis)** per `da1-matrix-multiturn-kant.json` automatic 判定:

| key | value |
|---|---|
| primary_rank | 8 |
| scenario | **II** |
| primary_vendi_diff_point | +2.589 (LoRA r=8 multi-turn 33.757 vs matched 31.167) |
| primary_vendi_diff_lo / hi | [+1.823, +3.385] (CI spans positive, NOT reversal) |
| primary_vendi_cohens_d | +2.17 (positive = wrong direction for DA-1) |
| primary_burrows_reduction_point | -4.04% (negative = wrong direction) |
| primary_burrows_reduction_lo | -5.46% |
| sister_ranks_aligned | 0/2 |

### CRITICAL CAVEAT (採取後発見、Codex HIGH-1 mitigation 2 の真価)

pre-registered Scenario II verdict は literally 正しいが、**no-LoRA SGLang
control 結果** が DA-12 direction failure の **根本原因** を再帰属させる:

| comparison | Vendi Δ | Burrows Δ | 解釈 |
|---|---|---|---|
| **backend confound** (matched Ollama → no-LoRA SGLang、両者 no-LoRA) | **+2.144** | **+5.391** | **direction failure の primary cause** |
| **LoRA effect at rank=8** (LoRA-on SGLang ↔ no-LoRA SGLang、同 protocol) | +0.446 | -0.960 | **near-zero、direction-neutral** |
| LoRA effect at rank=4 | +0.245 | +0.511 | near-zero、burrows wrong direction |
| LoRA effect at rank=16 | -0.050 | -0.492 | near-zero、both barely correct direction |

つまり **DA-12 の direction failure は LoRA failure ではなく "Ollama baseline vs
SGLang pilot" の backend confound が dominant**。LoRA 自体は Vendi/Burrows を
ほとんど動かしていない (rank=16 で Burrows -0.5% reduction が出ている程度)。

literal pre-registered verdict = Scenario II は維持するが、**実際の interpretation
は Scenario III の variant** (methodology confound = backend 主因 + LoRA effect
proper baseline 比で near-zero) として扱う:

1. **DA-12 の "LoRA が IPIP self-report neutral midpoint を shift しない"** は
   ICC(A,1) の数値 (0.90-0.92) から re-affirmed (本 PR multi-turn LoRA-on は
   0.89-0.99 で historical pilot と同 magnitude)
2. **DA-12 の "pilot single-turn vs baseline multi-turn methodology confound"**
   は **正しい因子** だが、それは **backend (Ollama vs SGLang) 起因**であり、
   single-turn vs multi-turn 単独では direction failure を引き起こさない
   (multi-turn pilot LoRA-on でも Vendi 33.3-33.8 で baseline 31.2 より高い)
3. **本来の "LoRA persona-discriminative effect" は proper baseline (no-LoRA
   SGLang) と比較すれば near-zero**。これが本 PR の最大の empirical 発見

### 後続経路: **Scenario II + Backend Confound Discovery → retrain v2 with proper SGLang baseline**

- DA-12 status: **close** (identifiability 解消)
  - "direction failure" 主因 = backend confound (NOT LoRA failure)
  - "LoRA persona-fit weak" = re-confirmed (proper baseline で near-zero effect)
- Phase D 着手前 prereq: **feature/m9-c-adopt-retrain-v2** 経路 confirmed、ただし spec amendment:
  - DA-9 retrain v2 spec を amend: **baseline は SGLang-on-base (no-LoRA SGLang
    multi-turn) を使う**、Ollama baseline は ローカル apples-to-oranges
    として除外
  - 加えて training data の persona discriminative signal 強化 (min_examples
    1000 → 3000 + stimulus prompt diversity + multi-turn dialog 比率 up)
- `next-session-prompt-scenario-II-retrain-v2.md` 起草 (本 PR 内、backend
  confound finding を spec に反映)

- **採用**: **Scenario II (literal) + Backend Confound Discovery (interpretation)**
- **根拠**:
  - **Codex HIGH** 4 件反映で identifiability 切り分けの operational risk を
    閉じた (no-LoRA control + matched baseline + preregister + validation gate)
  - DA-9 / DA-12 spirit と整合: marginal pass / direction failure の意味を
    弱めず、後続 PR で確定経路を明示
- **棄却**:
  - 全 8 shard 単 protocol change のみ (Codex HIGH-1 で却下): scenario I の
    結論強度が weak
  - matched baseline なし (HIGH-2 で却下): windowing/coverage confound が
    primary comparison に混入
  - post-hoc threshold movement (HIGH-3 で却下): cherry-pick risk
- **影響**:
  - Phase D 着手前 prereq 順序は DA-13 verdict 確定後に固定
  - `blockers.md` U-6 status は本 ADR で **closure / partial closure / 維持**
    のいずれかに update
  - DA-12 自体は immutable record として残し、本 ADR で empirical follow-up
- **re-open 条件**:
  - retrain v2 / Phase E A-6 の結果が DA-13 verdict と矛盾 → DA-14 起票
  - post-hoc threshold 緩めるニーズが発生 → DA-14 起票で正式化
- **trace**:
  - matrix artefact: `.steering/20260514-m9-c-adopt-pilot-multiturn/da1-matrix-multiturn-kant.json`
  - validation gate: `.steering/20260514-m9-c-adopt-pilot-multiturn/validation-multiturn-kant.json`
    (8/8 shards PASS、focal_target 300 ±5%、speaker alternation、no incomplete dialogs)
  - codex review: `.steering/20260514-m9-c-adopt-pilot-multiturn/codex-review.md`
    (MODIFY before implementation verdict + HIGH 1-4 全反映)
  - investigation decisions: `.steering/20260514-m9-c-adopt-pilot-multiturn/decisions.md`
  - scripts (新規 / 拡張):
    - `tier_b_pilot.py` (`--multi-turn-max` + `--no-lora-control` + atomic
      stimulus-level resume)
    - `compute_baseline_vendi.py` + `compute_burrows_delta.py`
      (`--max-focal-per-shard` flag、matched baseline downsampling 用)
    - `da1_matrix_multiturn.py` (新規、scenario verdict automatic)
    - `validate_multiturn_shards.py` (新規、HIGH-4 acceptance gate)
  - test: `tests/test_m9_c_adopt_pilot.py` (13 cases、focal/total turn count +
    stratified slice + seed + user prompt marker)
  - HEAD: (採取完了後、final commit SHA を埋め込み)
