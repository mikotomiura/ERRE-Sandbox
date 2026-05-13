# 設計 — m9-c-adopt Phase A (design v1: 3 persona simultaneous 1 PR adopt)

> 本 file は **v1 (初回案)** を保持する。`/reimagine` で起こす v2 を
> `design-v2-reimagine.md` に独立記述、8 軸比較を `design-comparison.md`
> に、Codex HIGH 反映後の最終案を `design-final.md` に保持する。

## 実装アプローチ

M9-C-adopt は M9-C-spike (PR #154/#155/#160/#161/#162/#163) の technical
PoC を前提に、**3 persona (kant/nietzsche/rikyu) を 1 PR で同時 adopt 判定**
する production-grade integration phase。Phase A (本 PR) は **設計のみ、
code 変更ゼロ**、Phase B-G で実装 + 訓練 + 実走。

採用方針: **infrastructure-already-proven + production-defense-first**

- M9-C-spike で SGLang adapter swap (8ms cold) / multi-LoRA serving /
  CS-7 4 trigger NON-FIRE / PEFT direct load が verified なので、
  Phase B 以降は infrastructure proof を繰り返さず **adoption quality
  empirical 確認** に集中
- `OllamaChatClient` 既存 live path は frozen 保持し、`SGLangChatClient`
  injection は **feature flag + parallel rollout** で defensive rollout
  (CS-8 防衛継続、U3 fp8 acceptance closure までは Ollama fallback 保持)
- mock 経由の API/format proof と real adapter 経由の quality proof を
  **2 pass** で分離 (DA-5、A-4 mock-first / A-4b real-after-A2)

8 topic ごとの設計を以下に詳述する。

---

### A-1: rank sweep (CS-5 / D-2 / U-1 closure)

**問題定義**

CS-5 で `rank=8` は "continuity hypothesis" 留保、universal adequacy
未主張。LoRA Land (arxiv:2405.00732) / P-Tailor (arxiv:2406.12548) は
universal best rank を establish しない。rank が低すぎると expressivity
不足、高すぎると overfit + VRAM 浪費。M9-C-adopt の最初の empirical 判定
となる。

**採用 approach**

- sweep 範囲: `rank ∈ {4, 8, 16, 32}` (PEFT/unsloth standard powers-of-2)
- 順序: G-GEAR single GPU 制約より sequential 必須。
  `rank=8` (既存 `kant_r8_real` を base 再利用、anchor) → `rank=4`
  (smaller、quick fail signal) → `rank=16` → `rank=32` (extreme、
  VRAM headroom 圧迫リスク)。anchor anchored sweep で early continuity
  確認 + 両側 extreme sample
- compute budget: 4 rank × 3 persona × ~2h training = ~24h
  (G-GEAR overnight × 3)
- **採用 rank 決定基準** (DA-1 で formal 化):
  1. **Vendi semantic score** (ME-10 default kernel `all-mpnet-base-v2`):
     baseline (no LoRA) との persona-discriminative gap が monotonic に
     improve しない rank で saturate と判定 → smallest saturated rank
  2. **Big5 ICC(C,k)** (ME-11 consistency notation): persona traits の
     stability ICC ≥ 0.6 (psychometrics literature shoulder、
     Anthropic persona vector / P-Tailor 整合) を満たす最小 rank
  3. **bench throughput floor**: single_lora baseline (CS-7 amendment
     2026-05-13: 34.64 tok/s) の 70% (= 24.25 tok/s) を切らない最大 rank
  - 3 基準の **intersection** (Vendi saturate floor ≤ rank ≤
    throughput ceiling) を採用 rank とする。複数該当時は VRAM 効率最大
    (= smaller rank) を選ぶ
- **棄却 rank archival**: `data/lora/m9-c-adopt/archive/rank_{4,8,16,32}/
  {persona}/` に全 sweep 結果 (adapter weights + Tier B JSONL + bench
  JSONL) を retain、後続研究 baseline として保持。production loader は
  採用 rank のみ load

**代替案と棄却理由**

- **binary search** (rank=8 → 16 → 12 → 14): 中間 rank は LoRA standard
  practice で uncommon、PEFT/unsloth default が powers-of-2 のみ、
  literature comparison が困難
- **parallel sweep**: single GPU で不可能、multi-GPU は scope 外
- **rank=64 含む**: VRAM 不足リスク高 (CS-4 estimate ~8.7GB base、
  rank=64 で +200MB adapter + activation 増加)、cost-benefit poor
- **rank=8 固定** (empirical sweep skip): CS-5 留保が adopt phase で
  closure 必要、empirical 未確認のまま production wiring は CS-5 の
  re-open 条件を未満たす

**risk / unknowns**

- rank=32 が VRAM headroom (16-8.7=7.3GB) を圧迫し OOM の可能性 →
  早期中断 protocol を Phase B で実装、CS-4 amendment で記録
- Tier B Vendi が rank 4/8/16/32 全て同等な signal を返す = LoRA 自体が
  persona-discriminative ではない可能性 → CS-5 re-open + DB3 re-arm 検討
  (A-8 DB3 re-arm trigger 条件と整合)

---

### A-2: 3 persona expansion (D-3 closure)

**問題定義**

M9-C-spike は Kant 1 persona only (D-3 defer)。Nietzsche / Rikyu の
training data 抽出 protocol が未確立、persona-specific tuning 要件未確定。

**採用 approach**

- 訓練順序: **kant → nietzsche → rikyu の sequential** (G-GEAR single
  GPU 強制、CS-4 VRAM 制約)
- training data 抽出 (M9-eval Phase B+C golden baseline、PR #160 共有):
  - **kant**: 既存 5022 examples (PR #163 dry-run verified) を base、
    rank sweep 用に再利用
  - **nietzsche / rikyu**: M9-eval Phase B+C で 3 persona × 5 run ×
    500 turn の golden baseline が既に存在 (PR #160)。同一 schema
    (`raw_dialog` table、`epoch_phase != EVALUATION` filter、
    `individual_layer_enabled=false`) で `_collect_from_shards()`
    経由抽出 (training contract DB5 / DB11 整合)
  - 各 persona で `assert_phase_beta_ready(min_examples=1000)`
    (CS-3 gate) 通過確認
- **persona-specific sampling override**: 既存 `personas/{kant,nietzsche,
  rikyu}.yaml` の `default_sampling` (e.g. kant T=0.60 top_p=0.85 /
  nietzsche T=0.85 top_p=0.80 / rikyu T=0.45 top_p=0.78) を **保持**。
  LoRA adapter は persona の表層 (vocabulary / 句法) を学習し、sampling
  override は ERRE mode-conditional micro adjust を担当する役割分離
  (CS-5 amendment 不要)
- **重要 dependency**: M9-eval Phase B+C golden baseline (PR #160) が
  3 persona 揃っている **前提**。kant 以外の Tier B baseline ICC が
  未計算なら、A-6 開始前に backfill が必須 → blockers.md hard blocker
  (H-1)

**代替案と棄却理由**

- **parallel multi-LoRA training** (1 GPU で 2 adapter): VRAM 不足、
  accelerate `--multi_gpu` も single GPU 環境で機能しない
- **nietzsche / rikyu を rank=8 固定で先行** (A-1 sweep 結果を待たず):
  adopted rank と nietzsche/rikyu rank の divergence を後で正規化する
  コスト高、A-1 完了後に着手する方が clean
- **per-persona sampling override の LoRA への absorb** (YAML 廃止):
  mode-conditional sampling delta が persona ごとに変わると ERRE FSM
  の semantic を broken、API contract regression

**risk / unknowns**

- **rikyu Japanese tokenizer 未実装** (M9-eval ME-* で記録)。Burrows
  Δ が rikyu で N/A になる場合、DB9 quorum は 2-of-3 のうち 2 metric
  (Vendi + Big5 ICC) のみで判定するか、tokenizer 実装を A-6 前に block
  か → blockers.md soft blocker (S-1)、DA-8 で fallback rule pin
- nietzsche の training data が 1000 examples を下回るリスク
  (M9-eval P3 採取 quality 次第) → 早期 dry-run で確認、不足なら
  synthetic augmentation か stimulus run 追加

---

### A-3: live inference path 統合 (D-5 closure)

**問題定義**

現状 `src/erre_sandbox/cognition/cycle.py:46-50` は `OllamaChatClient`
のみ import / inject。`SGLangChatClient` は spike で実装済
(`sglang_adapter.py`、OpenAI compatible `/v1/chat/completions` +
LoRA load/unload) だが live path 未統合。U3 (fp8 acceptance) が closure
まで防衛的 rollout 必要。

**採用 approach**: **feature flag + parallel rollout** (CS-8 防衛継続)

- 切替方式:
  - 環境変数 `ERRE_INFERENCE_BACKEND ∈ {ollama, sglang}` (default
    `ollama` 当面、A-8 verdict 後に `sglang` へ flip)
  - `CognitionCycle.__init__` の `llm` 引数を
    `OllamaChatClient | SGLangChatClient | MultiBackendChatClient`
    Union として受け入れ、bootstrap 側で env 読みして dispatch
  - 既存 `OllamaChatClient` API は frozen、`SGLangChatClient` は
    spike で同形に作られている (`chat()` signature 一致、`ChatMessage`
    / `ChatResponse` 共有)
- **fallback path**: SGLang unreachable (`SGLangUnavailableError`) →
  Ollama に degrade。具体的には `MultiBackendChatClient` wrapper を
  `inference/server.py` に新設、`chat()` 内で SGLang failure 検出時に
  Ollama に switch、ただし **adapter なし** (base Ollama model =
  qwen3:8b)。degraded mode は metric flag (`degraded_to_ollama=True`)
  を `CycleResult` に追加 (既存 `llm_fell_back` と並列)
- **CognitionCycle への config injection point**:
  - 既存 `__init__(llm=...)` 引数の **型を expand** するだけ。
    adapter routing (どの persona がどの LoRA を使うか) は
    `CognitionCycle.step(persona=...)` から `persona.persona_id` を
    読み、`MultiBackendChatClient` 内で `self._adapter_for_persona(
    persona_id)` を resolve。adapter name は `f"{persona_id}_r{rank}_real"`
    規約
  - persona → adapter mapping は `inference/server.py` の bootstrap で
    1 度だけ `load_adapter()` を呼び、`SGLangChatClient._loaded`
    registry に pinned で常駐
- 既存 `ollama_adapter.py` のシグネチャ変更ゼロ (regression リスク最小化)

**代替案と棄却理由**

- **hard switch** (Ollama 削除): U3 fp8 acceptance が未確認、M9-eval
  judge LLM が fp8 base を reject する可能性、防衛的 rollout が CS-8
  整合
- **per-call backend choice** (request-level routing): code complexity
  増、bootstrap 一回決定で十分
- **separate cognition cycle implementations** (`CognitionCycleSGLang`
  vs `Ollama`): code 重複大、Liskov 違反リスク

**risk / unknowns**

- `MultiBackendChatClient` の semantic divergence: Ollama vs SGLang で
  `temperature` / `top_p` clamp 挙動差異 (sampling.py で composer は
  同一だが、server-side 解釈は実装依存)。spike で 2.5% throughput 差
  を観測したが、output token distribution の差は未測定 → A-3 完了後に
  diff 観測テスト 1 件追加 (1 prompt × 100 sample で KL divergence < 0.1)
- bootstrap 順序: Ollama (sidecar process) と SGLang server (WSL2) は
  独立 process。両方起動失敗時に default backend がどちらかを
  fail-fast すべきか warn して 1 backend で続けるか → DA-4 で決定

---

### A-4: multi_lora_3 bench (CS-7 defer 解消)

**問題定義**

CS-7 amendment 2026-05-13 で **N=3 multi_lora_3 condition は
M9-C-adopt scope** と defer。spike では single_lora vs no_lora の 2
baseline のみ実測 (single_lora=34.64 tok/s / no_lora=35.54 tok/s、
ratio 0.975)。3 adapter 同時運用の throughput floor 未測。

**採用 approach**: **mock-first / real-after-A2 の 2 pass** (DA-5)

- **A-4a (mock-first、Phase D)**:
  - `tools/spike/build_mock_lora.py` (CS-9 refusal guard 付き、
    `init_lora_weights=True` で identity transform) を **再利用**
  - `mock_nietzsche_r8` / `mock_rikyu_r8` を生成、metadata sentinel
    に `{"mock": "true", "persona": "nietzsche|rikyu"}` 追加
  - 配置: `tools/spike/output/mock_{nietzsche,rikyu}_r8/` (production
    loader は `data/lora/m9-c-adopt/` 配下のみ load する path filter、
    CS-9 amendment / DA-6)
  - bench protocol: CS-7 4 trigger 踏襲 (`bench_serving`、
    num_prompts=16、random in/out=256/256、seed=0)
  - 3 adapter pinned load: `kant_r{adopted}_real` + `mock_nietzsche_r8`
    + `mock_rikyu_r8`
  - condition 順: no_lora → single_lora → multi_lora_3 で同一 prompt set
- **A-4b (real-after-A2、Phase E)**:
  - real 3 adapter (`kant_r{X}_real` + `nietzsche_r{X}_real` +
    `rikyu_r{X}_real`) で post-bench
  - mock pass で NON-FIRE / real pass で FIRE が観測されたら mock 識別
    ロジックを CS-7 trigger に追加 (DA-5 re-open 条件)
- **結果 jsonl**: `data/eval/spike/m9-c-adopt-bench/{no_lora,
  single_lora,multi_lora_3-mock,multi_lora_3-real}.jsonl`
- **CS-7 trigger 評価** (全 NON-FIRE で AC-4 PASS):
  - p95 e2e > 2x baseline → FIRE
  - output tok/s < 70% baseline → FIRE
  - adapter-misrouting (kant prompt → mock response、sentinel 検出) → FIRE
  - timeout 1 件でも → FIRE

**代替案と棄却理由**

- **mock 3 個ではなく real adapter 3 個で N=3 bench 1 pass**:
  nietzsche / rikyu の real adapter は A-1 + A-2 完了後にしか存在しない、
  scope 内で **再 A-4** が必要。CS-7 のシリアル防御 (mock = API/format
  proof、real = quality proof) を保つため mock-first / real-after の
  2 pass が clean (DA-5)
- **bench harness 自作**: CS-7 で SGLang `bench_serving` 採用済、不要

**risk / unknowns**

- mock-LoRA で multi_lora_3 が NON-FIRE でも real 3 で FIRE する可能性
  (= mock の identity transform が contention を underestimate)。
  A-6 で real 3 adapter での post-bench を追加することで mitigate
  (= A-4b、DA-5)

---

### A-5: M5 resonance / 8-mode FSM smoke (D-5 full closure)

**問題定義**

D-5 で defer。spike は M5 resonance / ERRE FSM 統合範囲外。adopt で
8 mode (peripatetic / chashitsu / zazen / shu_kata / ha_deviate /
ri_create / deep_work / shallow) の AnimationTree state machine が
SGLang LoRA 経路で regression していないか確認必要。

**採用 approach**

- カバレッジ: **8 mode × 3 persona = 24 cell 完全**
- protocol:
  - 各 cell で `CognitionCycle.step()` を 1 turn 実行、SGLang backend
    + real LoRA adapter (A-1 で決まる rank、A-2 で揃う 3 persona)
  - input observation は cell ごとに固定 (e.g. peripatetic =
    `ZoneTransitionEvent(to_zone=PERIPATOS)`、zazen =
    `BiorhythmEvent(signal="stress", level_now=0.4)` 等、K-α
    `step5_fsm_smoke.py` パターン踏襲)
  - 観察: `AgentState.erre.name` 遷移 / `AnimationMsg.animation_name`
    出力 / `ERREModeShiftEvent.reason` 一致
- **pass 基準**:
  - 8 mode 全てで state transition valid (= persona expected mode に
    到達、未定義状態 / Pydantic ValidationError 0 件)
  - regression assertion: Ollama baseline (no LoRA) で同一 input →
    同一 final mode (= LoRA は mode FSM を perturbate していない)
  - exit_code 0 で 24/24 cell PASS
  - **reason field は pass 基準から除外** (DA-7、LoRA wording drift
    容認)
- artefact: `data/eval/spike/m9-c-adopt-fsm-smoke/{persona}_{mode}.json`

**代替案と棄却理由**

- **8 mode × 1 persona (kant) のみ**: persona 差を確認できない、3
  persona expand の整合性 risk
- **end-to-end Godot up smoke**: scope creep、godot_project 起動は test
  infra 別 PR
- **reason field 一致 strict pass**: LLM 出力ヒューリスティック、
  LoRA-on で false positive regression、user-facing 影響なしのため緩める

**risk / unknowns**

- LoRA が ERRE FSM transition reason field の semantic を drift させる
  可能性 (LLM 出力の wording 変化が `_infer_shift_reason()` を misclassify)
  → reason field を pass 基準から外し、final mode 一致のみで判定 (DA-7)
- 8 mode × 3 persona の cell ごとの input observation を hard-code する
  test fixture 必要、共通化は Phase E で実装

---

### A-6: Tier B empirical validation (U-1 / U-2 closure)

**問題定義**

U1 / U2 closure には Tier B Vendi / Big5 ICC で persona-discriminative
threshold を empirical 決定する必要。Phase B+C golden baseline (PR #160)
は no-LoRA。adopt 判定には LoRA-on の Tier B が必須。

**採用 approach**

- **試料 size**: stimulus 500 turn × 5 run × 3 persona = 7500 turn
  - per-turn latency ~14s (CS-7 amendment 実測) × 7500 = ~29h、
    G-GEAR overnight × 3 night
  - parallel 3-persona は VRAM 不足 (CS-4 + 3 adapter で 16GB 食い切る)、
    sequential
- protocol:
  - SGLang launch (`--enable-lora --max-loras-per-batch 3
    --max-loaded-loras 3`)
  - 3 adapter pinned load (A-2 完了後の real adapter)
  - `assert_phase_beta_ready()` で raw_dialog table sanity 確認
    (DB11 contamination assert は eval-only path で違うが、A-6 出力
    raw_dialog は `epoch_phase=evaluation` で書き、後続 training への
    漏洩を防ぐ — CS-3 / DB11 整合)
  - serialized inference loop で 7500 turn 採取 → DuckDB shard 化
- **評価指標**:
  - **Vendi semantic kernel** (ME-10 default `all-mpnet-base-v2`)、
    persona-conditional kernel + 200-turn window
  - **Big5 ICC(C,k)** (ME-14 primary `cluster_only` BootstrapPair)
  - **IPIP-NEO-120 trait scores** (persona expected trait と LoRA-on
    の Spearman 相関)
- **persona-discriminative threshold**: **本 PR では framework のみ
  確定**、empirical threshold は P4b で決定 (CS-5 re-open path 兼用)
  - framework: DB9 quorum 2-of-3 を踏襲、各 metric の
    "persona-discriminative" 判定は:
    - **Vendi**: LoRA-on Vendi < no-LoRA Vendi (= adapter が
      persona-conditional な狭めを inducing)、effect size ≥ 0.3
      (Cohen's d、literature shoulder)
    - **Big5 ICC**: 該当 persona の expected trait
      (e.g. kant の conscientiousness=0.98) で ICC(C,k) ≥ 0.6
    - **Burrows Δ**: persona corpus (kant primary refs) との average
      Δ が baseline より 10% 以上 reduce
- output: `data/eval/m9-c-adopt-tier-b/{persona}_run{0..4}_stim.duckdb`、
  Tier B 算出は M9-eval-system `tier_b_bootstrap_pair.py` 経由

**代替案と棄却理由**

- **試料縮小** (stimulus 200 turn × 3 run × 3 persona = 1800 turn):
  Vendi 200-turn window の minimum cycle に届かない、CI width 過大化
  (ME-3 経験)
- **並列 persona inference**: VRAM 制約で不可能
- **threshold をこの PR で empirical pin**: rank sweep 結果と循環依存、
  framework のみ確定が安全

**risk / unknowns**

- 29h 内に G-GEAR が thermal throttling / WSL2 process crash →
  checkpoint resume protocol (per 500 turn save、resume CLI option)
  を A-6 implementation で必須化
- rikyu Japanese tokenizer 未実装で Burrows Δ N/A の場合、quorum は
  2-of-2 (Vendi + ICC) で代用 (rikyu 限定の DB9 quorum exception、
  DA-8 で formal 化)
- Vendi threshold (effect size ≥ 0.3) が marginal pass を許容しすぎる
  場合 → DA-9 で ADOPT-WITH-CHANGES retrain path を pin

---

### A-7: production safety (CS-9 amendment)

**問題定義**

spike CS-9 で mock-LoRA `tools/spike/` 隔離 + metadata sentinel +
refusal guard を確定したが、**production loader への misroute hard block**
は warning level のみ。adopt 後の live path で誤 load されるとユーザー
影響大。

**採用 approach**

- **mock-LoRA hard block** (CS-9 amendment、DA-6):
  - `inference/server.py` bootstrap で `load_adapter(ref)` 呼び出し前に
    `_validate_production_path(ref.weight_path)` check
  - rule: `ref.weight_path` が `data/lora/m9-c-adopt/` 配下でない、
    または `is_mock=True` (metadata sentinel) → `ProductionLoaderRejectError`
    で fail-fast
  - spike code path (`tools/spike/`) からの直接 load は
    `SGLangChatClient.load_adapter()` 直叩きで可能 (= dev path 確保)、
    ただし `inference/server.py` 経由は block
- **adapter pinning policy** (DA-3 補完):
  - 3 persona 全 pinned 推奨 (VRAM 余裕、CS-4 estimate で base 8.7GB
    + adapter 3 × ~30MB = ~8.8GB、headroom 7GB)
  - SGLang `--max-loaded-loras 3` + `pinned=True` で boot 時 pin
- **model checksum 検証** (DA-10):
  - `adapter_model.safetensors` の sha256 を `data/lora/m9-c-adopt/
    {adapter_name}/checksum.sha256` に記録
  - `load_adapter()` 前に file system 上の sha256 を再計算 + match 確認、
    mismatch → `AdapterIntegrityError`
  - checksum 生成は A-2 training 後の post-step (CI で `pre-commit`
    hook 候補だが scope 外)
- audit log: 全 load 操作を `logs/inference/adapter_load_audit.jsonl`
  に記録 (timestamp / adapter_name / sha256 / outcome)

**代替案と棄却理由**

- **production loader での hard block を warning のままにする** (CS-9
  status quo): user-facing 影響リスク残存、CS-9 re-open trigger
- **adapter 動的 unpin** (idle 時に unload): CS-7 collapse 検出ロジック
  複雑化、N=3 で contention 無いと spike 実証済 (CS-7 amendment 2.5%)
- **production / spike 同一 loader**: 誤運用 risk 大、dev workflow が
  production loader に sneak in する可能性

**risk / unknowns**

- sha256 計算が cold load latency に追加 ~50-100ms (30MB の hash)、
  500ms ceiling 内だが間接的に CS-8 threshold (実測 8ms cold) を
  圧迫 → A-6 で warm latency 再測、threshold tight すぎなら DA に re-open
- production / spike dichotomy が dev workflow を阻害する場合 → policy
  緩和 + audit log で代替 (DA-6 re-open 条件)

---

### A-8: 採用判定基準 (DA-N で formal 化)

**問題定義**

spike CS-7 / CS-8 / CS-5 amendment で操作的 SLO は record 済だが、
**adopt 判定の formal quorum 規則** が未確定。A-8 verdict 出力には
3 quorum (Tier B / bench / latency) + DB3 re-arm trigger の formal
specification が必要。

**採用 approach**

- **Tier B quorum** (DA-8): **2-of-3 metric (Vendi + ICC + Burrows Δ)
  PASS で adopt-quality 通過** (DB9 quorum 踏襲、ME-14 primary
  `cluster_only` BootstrapPair 参照)
  - rikyu Burrows N/A 時は 2-of-2 (Vendi + ICC) を quorum とする
    (DA-8 例外、kant/nietzsche は 3-of-3 維持)
- **bench quorum** (DA-2 / DA-5):
  - 3 baseline × 4 CS-7 trigger 全 NON-FIRE 必須 (no_lora / single_lora
    / multi_lora_3)
  - throughput floor: `multi_lora_3 ≥ 0.7 × single_lora ≥ 0.7 × no_lora`
  - p95 e2e: `multi_lora_3 ≤ 2.0 × no_lora`
  - error rate: 全 condition で HTTP timeout 0 件
- **latency ceiling** (CS-8 amendment 候補):
  - **adapter swap p99 < 50ms** (実測 cold 10ms の 5x ceiling、spike
    60x margin を 5x まで tighten)
  - chat round-trip p99 < 15s (実測 ~7.2s の 2x ceiling)
- **DB3 vLLM re-arm trigger**:
  - SGLang launch fail 3 連続 (op log で観測) OR
  - adapter load p99 > 500ms 24h sustained (= CS-8 元 threshold 復活) OR
  - Tier B quorum 0-of-3 (= LoRA 効果無し → vLLM serving 経路の方が
    良い可能性)
- **FSM smoke** (A-5 直結): 24/24 cell PASS
- **marginal pass** (DA-9): effect size 0.3 ≤ d < 0.5 (marginal) かつ
  ICC 0.6 ≤ ICC < 0.7 の場合は **ADOPT-WITH-CHANGES verdict**
  (re-train で larger min_examples + rank=adopted を再試行、または
  stimulus prompt diversity 改善)

**代替案と棄却理由**

- **3-of-3 strict quorum**: Burrows / rikyu の N/A 等 edge case で
  adopt 永続的阻害
- **1-of-3 weak quorum**: spurious adopt risk、後続 M9-D で巻き戻し
- **throughput floor 80%** (CS-7 tight): real adapter で marginal、
  70% は spike 実測 97.5% から 2 stddev 程度の頭で operational
- **marginal を strict reject**: re-train cost が high で iteration
  困難
- **marginal も無条件 adopt**: M9-D で巻き戻しリスク

**risk / unknowns**

- Tier B quorum が "marginal pass" (e.g. effect size ~0.3 borderline)
  でも adopt するか / re-train を強制するか → DA-9 で operational
  stance を pin
- DB3 re-arm trigger の 24h sustained 条件 monitoring 実装が Phase G
  scope (production-like soak で初めて可能)

---

## 変更対象

### 修正するファイル (Phase A、本 PR)

- なし (`.steering/` + `docs/` のみ変更可、code 変更ゼロ)

### 新規作成するファイル (Phase A、本 PR、すべて `.steering/20260513-m9-c-adopt/` 配下)

- `requirement.md` — 背景 / ゴール / scope / 受入条件 AC-1..AC-6
- `design.md` (本 file) — v1 案 8 topic 詳細
- `design-v2-reimagine.md` — `/reimagine` v2 案、brittle 前提 3 個破棄
- `design-comparison.md` — 8 軸比較表、v1 / v2 / hybrid 採否
- `codex-review-prompt.md` — Codex independent review 依頼書
- `codex-review.md` — Codex 出力 verbatim 保存
- `design-final.md` — Codex HIGH 反映後最終案、HIGH 反映マッピング表
- `decisions.md` — DA-1..DA-10 ADR、各 5 要素
- `blockers.md` — hard / soft / defer / uncertainty 4 区分
- `tasklist.md` — Phase A-G + H-Z roadmap

### 削除するファイル

- なし

### Phase B-G で変更予定 (本 PR では touch しない、参考までに列挙)

- **Phase B**: `src/erre_sandbox/training/train_kant_lora.py` →
  generic `train_persona_lora.py` 化 (CLI に `--persona kant|nietzsche|rikyu`
  + `--rank 4|8|16|32`)
- **Phase D**: `src/erre_sandbox/inference/server.py` (新規、
  `MultiBackendChatClient` wrapper) / `src/erre_sandbox/cognition/cycle.py`
  (L46-50 import + L228 型 Union)
- **Phase E**: `tests/test_inference/test_multi_lora_3_real.py` /
  `tests/test_cognition/test_fsm_smoke_lora.py` 新規
- **Phase F**: `inference/server.py` の `_validate_production_path()` +
  `AdapterIntegrityError` raise

## 影響範囲

本 Phase A は `.steering/20260513-m9-c-adopt/` 配下 10 file 新設のみ。
code / test / config / runbook 全て unchanged。

Phase B-G の影響範囲 (参考):
- code: `src/erre_sandbox/inference/server.py` (新規) /
  `cognition/cycle.py` (touched L46-50, L228) / `training/` 拡張
- tests: `tests/test_inference/` + `tests/test_cognition/` 拡張
- data: `data/lora/m9-c-adopt/` + `data/eval/spike/m9-c-adopt-bench/`
  + `data/eval/m9-c-adopt-tier-b/` 新規
- docs: `docs/runbooks/m9-c-adopt-live-bootstrap.md` (DA-4 関連、
  新規候補)

## 既存パターンとの整合性

- **CS-1..CS-9 + 3 amendment**: 全 ADR 整合、矛盾 0
- **DB1..DB11 + 第3の道 ADR**: M9-B consumer 側として消費のみ、
  upstream 改変なし
- **ME-1..ME-15**: M9-eval-system framework consumer、Tier B
  threshold は P4b 完了後に DA-11+ で empirical pin
- **既存 inference pattern**: `OllamaChatClient` API frozen、
  `SGLangChatClient` は spike で同形に作られている (
  `chat()` signature 一致、`ChatMessage` / `ChatResponse` 共有)
- **既存 sampling**: `compose_sampling()` は唯一の合法的構成パス、
  LoRA adapter routing と直交 (CS-5 整合)
- **mock-LoRA 隔離**: `tools/spike/` 隔離、metadata sentinel、refusal
  guard を CS-9 から継承、production loader hard block で強化 (DA-6)

## テスト戦略

- **Phase A (本 PR)**: code 変更ゼロのため test suite 実行なし。
  代わりに以下の人手 verification:
  1. scaffold 完全性 (10 file 存在、template + Phase A 専用)
  2. requirement.md AC-1..AC-6 measurable
  3. design.md / v2 / comparison consistency (8 topic 全て触れられる)
  4. Codex verbatim (要約 / 改変なし)
  5. HIGH 全反映 (design-final.md + DA-N 内で trace)
  6. decisions.md 5 要素全 sub-bullet 埋まる
- **Phase D**: pytest 新規 5 file (multi_backend / live cycle / FSM
  smoke / production loader / checksum)、ruff / mypy / pytest 全 PASS、
  CI 4/4 green
- **Phase E**: G-GEAR 実走 29h + 24 cell FSM smoke、artefact JSONL/
  DuckDB shard sanity check

## ロールバック計画

本 PR (Phase A) は code 変更ゼロのため、ロールバックは branch close
のみ。`.steering/20260513-m9-c-adopt/` は別 PR で別途扱うか、本 PR
revert で消す。

Phase B-G のロールバック計画:
- **Phase D**: `ERRE_INFERENCE_BACKEND=ollama` (default) で SGLang 経路
  bypass、`MultiBackendChatClient` は wrapper のため `OllamaChatClient`
  直接利用に戻すこと可能
- **Phase G**: 1 week soak で error rate > 0.1% なら default を `ollama`
  に戻す revert
- **DA-N**: 各 ADR に re-open 条件、empirical 観測で trigger fire 時に
  別 PR で amendment
