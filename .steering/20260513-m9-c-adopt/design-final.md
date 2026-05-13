# 設計最終案 (design-final) — m9-c-adopt Phase A (Codex HIGH 4 / MEDIUM 6 / LOW 3 反映)

> Codex `gpt-5.5 xhigh` independent review (Verdict: **ADOPT-WITH-CHANGES**、
> `codex-review.md` verbatim 保存) を全反映した hybrid v3。HIGH 4 件は必須
> 反映、MEDIUM 6 件は DA-N で trace、LOW 3 件は blockers.md / tasklist.md
> で deferred / 追記対応。本 file は design.md (v1) + design-v2-reimagine.md
> + design-comparison.md を override する **最終契約**。

## HIGH 反映マッピング表

| Codex finding | 反映先 | 対応 |
|---|---|---|
| **HIGH-1**: rank=32 permanent exclusion is risky; need conditional tail-sweep trigger + `--max-lora-rank >= 16` launch arg fix | DA-1 / A-1 / requirement.md AC-1 / tasklist.md Phase B / blockers.md S-2 | rank=32 を conditional re-open trigger 付きで除外、SGLang launch arg `--max-lora-rank >= 16` を contract に追加 |
| **HIGH-2**: Tier B provisional thresholds must include bootstrap CI lower bound + baseline direction + ME-11 ICC consumer split | DA-8 / DA-9 / A-6 / A-8 / requirement.md AC-1, AC-6 | point threshold + CI lower bound 同時 PASS、direction 検証必須、marginal pass は ADOPT-WITH-CHANGES、final pin は P4b/P4c 後 |
| **HIGH-3**: SGLang multi_lora_3 needs real stress pass with churn diagnostic (TTFT/ITL/e2e p99 + queue wait + misrouting + timeout + memory growth) | DA-5 / A-4b / A-8 / tasklist.md Phase E | A-4b real-after pass で churn diagnostic 追加、CS-7 拡張 metric (queue wait / memory growth) を実装 |
| **HIGH-4**: Production loader needs manifest-grade integrity (signed/immutable manifest + path traversal/symlink/.bin/base model/rank/target modules checks) | DA-6 / DA-10 / A-7 | `_validate_production_path()` → `_validate_adapter_manifest()` に格上げ、manifest = {adapter_name / persona_id / base_model / rank / target_modules / sha256 / training_git_sha / mock_flag}、audit log は prompt 内容を redact |

## MEDIUM trace 表

| Codex finding | 反映先 | 対応 |
|---|---|---|
| **MEDIUM-1**: vLLM はlate-bound、Phase A に first-class 入れない | DA-2 | vLLM 現状 evidence と re-arm trigger を DA-2 に記録、Phase D skeleton 不要 |
| **MEDIUM-2**: rikyu 2-of-2 fallback は named limitation 扱い | DA-8 / blockers.md H-2 | rikyu `Burrows=N/A(tokenizer-unimplemented)` を decisions.md に明記、tokenizer 実装 hard blocker 追加 |
| **MEDIUM-3**: requirement.md AC-1 が rank scope と不整合 | requirement.md AC-1 修正済 | rank `{4, 8, 16}` に統一、HIGH-1 tail-sweep trigger 反映 |
| **MEDIUM-4**: Big5 metric semantics に ME-11 alignment 必要 | DA-8 / A-6 | ICC(C,k) は stability/reliability metric と明記、persona-fit は ICC(A,1) を diagnostic として併報告 (DA-9 final verdict 前) |
| **MEDIUM-5**: persona-specific sampling は compose_sampling() 規約 regression assertion 必須 | DA-3 / A-3 / tasklist.md Phase D | Phase D/E で `compose_sampling()` 通過 assertion 追加、SGLang options で temperature/top_p/repeat_penalty を override 禁止 |
| **MEDIUM-6**: min_examples=1000 は SLO 止まり、Tier B 通過必須 | DA-3 / A-2 / A-6 | Phase C で min_examples PASS = training kick 許可のみ、persona signal proof は A-6 Tier B 必須を明記 (BIG5-CHAT 100k 規模との対比) |

## LOW trace 表

| Codex finding | 反映先 | 対応 |
|---|---|---|
| **LOW-1**: audit log rotation / retention / redaction 規約 | tasklist.md Phase F、`docs/runbooks/m9-c-adopt-audit-log.md` (新規候補) | audit log rotation policy + redaction (no raw prompt / no persona prompt content) を Phase F で実装 |
| **LOW-2**: checksum latency measurement (block しない) | tasklist.md Phase F | Phase F で sha256 cold load latency 測定、CS-8 latency trace 継続 |
| **LOW-3**: Japanese tokenizer implementation note | blockers.md H-2 (hard) / soft note | fugashi/MeCab を pragmatic 第一候補、Sudachi を後続比較選択肢として記録 |

---

## 最終 hybrid v3 (HIGH 4 反映後)

### A-1: rank sweep (HIGH-1 + MEDIUM-3 反映)

- **sweep 範囲**: `default rank ∈ {4, 8, 16}`、compute 18h (G-GEAR overnight × 2-3)
- **rank=32 conditional re-open trigger** (HIGH-1):
  - Phase B で rank=16 が **throughput 基準 PASS** (≥ 70% baseline) **かつ** Vendi / ICC / Burrows のいずれか 1+ が threshold 未達 (= signal saturate していない兆候) → rank=32 tail-sweep を起動
  - または Phase B 観察で PLORA-like rank sensitivity (rank=8→16 で sharp gain) 発生 → rank=32 tail-sweep
  - tail-sweep は VRAM peak monitor (`nvidia-smi` per-step) + early abort threshold (peak > 14GB で kill)
- **SGLang launch arg fix** (HIGH-1): rank=16 を実際に serving するために
  ```bash
  python -m sglang.launch_server \
    --model qwen/Qwen3-8B \
    --enable-lora \
    --max-loras-per-batch 3 \
    --max-lora-rank 16 \
    --max-loaded-loras 3 \
    --port 30000
  ```
  CS-1 の `--max-lora-rank 8` から `--max-lora-rank 16` への amendment が
  必須 (CS-1 amendment 候補、本 PR では DA-1 で記録)。tail-sweep rank=32
  fire 時は `--max-lora-rank 32` に再 amendment
- **採用 rank 決定基準** (HIGH-2 反映): Vendi saturate floor ∩ Big5
  ICC(C,k) ≥ 0.6 (point threshold + bootstrap CI lower bound ≥ 0.6 同時)
  ∩ Burrows Δ reduction ≥ 10% (CI 同時 PASS) ∩ bench throughput ≥ 70%
  baseline の 4 軸 intersection、smaller rank 優先

### A-2: 3 persona expansion (MEDIUM-5 + MEDIUM-6 反映)

- 訓練順序: kant → nietzsche → rikyu sequential
- `assert_phase_beta_ready(min_examples=1000)` PASS は **training kick
  許可のみ** (MEDIUM-6)、persona signal proof は A-6 Tier B 必須
- BIG5-CHAT 100,000 dialogue 対比で、ERRE の 1000 examples は SLO 止まり、
  Tier B Vendi / ICC で persona-discriminative signal を独立に validate
- persona-specific sampling: YAML `default_sampling` 保持、Phase D/E で
  `compose_sampling()` 通過 assertion 追加 (MEDIUM-5)、SGLang options
  で temperature/top_p/repeat_penalty override 禁止

### A-3: live inference path 統合 (MEDIUM-1 + MEDIUM-5 反映)

- 切替: `ERRE_INFERENCE_BACKEND ∈ {ollama, sglang}` feature flag、
  default `ollama` (A-8 verdict 後 flip)
- `MultiBackendChatClient` は 2 backend (Ollama / SGLang)、vLLM は
  DA-2 に late-binding 記録のみ (MEDIUM-1)
- fallback: SGLang unreachable → Ollama degraded mode (adapter なし、
  `degraded_to_ollama=True` flag)
- **compose_sampling() 規約 assertion** (MEDIUM-5): Phase D で
  `MultiBackendChatClient.chat()` 内に `assert isinstance(sampling, ResolvedSampling)`
  + SGLang JSON payload に temperature/top_p/repeat_penalty を SGLang
  options 経由で override しないことを test で固定

### A-4: multi_lora_3 bench (HIGH-3 反映)

- **A-4a (mock-first、Phase D)**: CS-7 4 trigger NON-FIRE 必須 (現状維持)
- **A-4b (real-after、Phase E)**: HIGH-3 churn diagnostic を追加
  - **steady-state metric** (CS-7 拡張): TTFT p50/p95/p99 / ITL p50/p95/p99 / e2e p99 / output tok/s / error rate
  - **churn diagnostic** (新規、HIGH-3): queue wait p99 / adapter-misrouting count (kant prompt → nietzsche/rikyu response 検出) / timeout count / **memory growth** (G-GEAR `nvidia-smi --query-gpu=memory.used` per-minute sampling)
  - 7500 prompt × 3 condition (no_lora / single_lora / multi_lora_3) を **長時間 stress mode** (持続 1h+) で実施、cold start collapse 含む
  - 結果: `data/eval/spike/m9-c-adopt-bench/multi_lora_3-real-stress.jsonl` + `memory_growth.jsonl`
- **CS-7 4 trigger** + 新規 trigger:
  - queue wait p99 > 30s → FIRE (新規 HIGH-3)
  - memory growth > 500MB / 1h sustained → FIRE (新規 HIGH-3)
- **PASS 基準**: 4 既存 + 2 新規 trigger 全 NON-FIRE で AC-4 PASS

### A-5: M5 resonance / FSM smoke (変化なし)

- 8 mode × 3 persona = 24 cell、`AgentState.erre.name == expected` のみ pass、reason field 除外 (DA-7)

### A-6: Tier B empirical validation (HIGH-2 + MEDIUM-4 反映)

- 試料: stimulus 500 turn × 5 run × 3 persona = 7500 turn
- 評価指標:
  - **Vendi semantic** (ME-10): effect size (Cohen's d) point estimate + bootstrap 95% CI (`tier_b_bootstrap_pair.py` primary `cluster_only`)
  - **Big5 ICC(C,k)** (MEDIUM-4): stability/reliability metric として明記、persona-fit には **ICC(A,1)** (absolute agreement) を diagnostic として併報告
  - **Burrows Δ reduction**: persona corpus との average Δ baseline 比 % reduction + bootstrap 95% CI
  - **IPIP-NEO-120 trait scores**: persona expected trait と Spearman 相関 (diagnostic、quorum には含めない)
- **Provisional threshold + CI gate** (HIGH-2):
  - Vendi effect size d ≥ 0.3 **AND** bootstrap CI lower bound > 0 (= LoRA-on Vendi が baseline より統計的に narrower) **AND** direction = "LoRA-on < no-LoRA Vendi" (= persona-conditional)
  - Big5 ICC(C,k) ≥ 0.6 **AND** CI lower bound ≥ 0.6、direction = positive vs baseline
  - Burrows Δ reduction ≥ 10% **AND** CI lower bound > 0、direction = "LoRA-on Δ < no-LoRA Δ"
- **final threshold pin** (HIGH-2 後段): provisional pin は本 PR の **screen**、final empirical pin は P4b/P4c 完了後の DA-11+ で tighten

### A-7: production safety (HIGH-4 反映)

- **manifest-grade integrity** (HIGH-4):
  - `_validate_production_path()` → `_validate_adapter_manifest()` に格上げ
  - manifest (immutable local file `data/lora/m9-c-adopt/{adapter_name}/manifest.json`):
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
  - hard block 条件 (HIGH-4 拡張):
    1. path traversal / symlink escape (`Path.resolve()` で chroot 外検出)
    2. `adapter_model.safetensors` 不在 OR `.bin` pickle fallback 検出 → reject
    3. manifest `base_model != "Qwen/Qwen3-8B"` → reject
    4. manifest `rank not in {4, 8, 16}` (HIGH-1 tail-sweep fire 時は `{4, 8, 16, 32}`) → reject
    5. manifest `target_modules` が CS-1 amendment と不整合 → reject
    6. sha256 mismatch (実 file vs manifest 記録) → `AdapterIntegrityError`
    7. `is_mock=True` (manifest 内) → `ProductionLoaderRejectError`
- **audit log redaction** (LOW-1):
  - `logs/inference/adapter_load_audit.jsonl` に記録、ただし prompt
    内容 / persona prompt 内容は redact (manifest id + adapter_name +
    sha256 + outcome のみ)
  - rotation: daily 50MB、retention: 30 day (LOW-1 reflected in
    Phase F)

### A-8: 採用判定基準 (HIGH-2 + MEDIUM-1 + MEDIUM-4 反映)

- **Tier B quorum** (HIGH-2):
  - 2-of-3 metric PASS for kant/nietzsche、rikyu は 2-of-2 (MEDIUM-2 limitation 扱い)
  - 各 metric は point threshold + bootstrap CI lower bound + direction の 3 条件 AND
  - ICC(C,k) primary + ICC(A,1) diagnostic 併報告 (MEDIUM-4)
- **bench quorum**: CS-7 4 既存 + 2 新規 trigger 全 NON-FIRE on multi_lora_3 vs single_lora vs no_lora (HIGH-3)
- **latency ceiling**: adapter swap p99 < 50ms / chat round-trip p99 < 15s
- **DB3 vLLM re-arm** (MEDIUM-1):
  - SGLang launch fail 3 連続 OR
  - adapter load p99 > 500ms 24h sustained OR
  - Tier B quorum 0-of-3 OR
  - multi_lora_3 memory growth > 500MB/1h sustained (HIGH-3)
- **marginal pass** (HIGH-2 + DA-9): point threshold PASS だが CI lower bound NOT cleared → ADOPT-WITH-CHANGES (retrain path)
- **FSM smoke**: 24/24 cell PASS

---

## 全 ADR 一覧 (DA-1..DA-10、各 5 要素は decisions.md 参照)

- **DA-1**: rank sweep `{4, 8, 16}` + conditional rank=32 tail-sweep + `--max-lora-rank >= 16` (HIGH-1)
- **DA-2**: live path feature flag + Ollama fallback、vLLM は late-binding only (MEDIUM-1)
- **DA-3**: 3 persona sequential 訓練、`assert_phase_beta_ready()` PASS は training kick 許可のみ (MEDIUM-6)
- **DA-4**: 両 backend 失敗 → fail-fast、片方 → warn + 稼働 backend で続行
- **DA-5**: multi_lora_3 bench mock-first / real-after、real-after に churn diagnostic 追加 (HIGH-3)
- **DA-6**: production loader manifest-grade integrity hard block (HIGH-4)
- **DA-7**: FSM smoke pass 基準 = final mode 一致のみ、reason field 除外
- **DA-8**: Tier B quorum 2-of-3 (kant/nietzsche) / 2-of-2 (rikyu)、各 metric は point + CI + direction の 3 条件 AND (HIGH-2 + MEDIUM-2 + MEDIUM-4)
- **DA-9**: marginal pass (CI lower bound NOT cleared) は ADOPT-WITH-CHANGES retrain path (HIGH-2)
- **DA-10**: adapter manifest + sha256 checksum + `AdapterIntegrityError` (HIGH-4)

---

## Phase B-G 着手前の Codex HIGH 反映確認 checklist

- [ ] CS-1 amendment 候補で `--max-lora-rank >= 16` を runbook DB8 に追記 (HIGH-1)
- [ ] `tier_b_bootstrap_pair.py` の primary `cluster_only` output に CI lower bound + direction を expose (HIGH-2、M9-eval-system 改造ではなく既存 framework 利用、本 PR scope 外)
- [ ] A-4b bench harness で memory growth サンプリング + queue wait + churn diagnostic 拡張 (HIGH-3)
- [ ] `inference/server.py` の `_validate_adapter_manifest()` skeleton + manifest schema を design に明示 (HIGH-4)

---

## 既存 CS-* との整合性確認

- **CS-1**: `--max-lora-rank` を 8 → 16 へ amendment が本 PR で確定 (DA-1)。CS-1 自体は SGLang version pin (0.5.10.post1) と launch args 全体の規約、本 PR は rank arg のみ修正、CS-1 の immutability は破らない (amendment trace)
- **CS-3**: `min_examples=1000` SLO は保持、Tier B 必須化を MEDIUM-6 反映で明文化 (CS-3 amendment ではなく consumer 側で運用)
- **CS-5**: continuity hypothesis を rank sweep で empirical 検証する方針継続、rank=32 conditional re-open trigger で U1 closure を保つ (HIGH-1)
- **CS-7**: 4 trigger は維持、A-4b で 2 trigger 追加 (queue wait / memory growth)
- **CS-8**: adapter swap p99 < 50ms (実測 8ms の 5x ceiling、本 PR で tighten) を A-8 で pin
- **CS-9**: mock-LoRA 隔離を hard block + manifest に格上げ (HIGH-4)
