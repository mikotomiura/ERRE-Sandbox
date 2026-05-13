# Codex independent review request — m9-c-adopt Phase A (3 persona LoRA adopt judgment on SGLang live path)

## 役割

あなたは ERRE-Sandbox プロジェクトの **independent reviewer**。Claude が
起草した m9-c-adopt Phase A 設計案 (v1 + v2 reimagine + comparison +
hybrid v3 候補) を **同一モデル 1 発生成の構造的バイアス** から救出する
ために招かれている。Verdict + 優先度付き finding + web-search-based prior
art 引用で reply してほしい。要約禁止、verbatim 保存される。

## 報告フォーマット (厳守)

1. **Verdict**: 一行 — `APPROVE` / `ADOPT-WITH-CHANGES` / `REJECT`
2. **HIGH** finding (must reflect before merge): `[HIGH-N] title` +
   ≥3 行 rationale + 引用 (URL or paper)
3. **MEDIUM** finding (decisions.md ADR 反映): `[MEDIUM-N]`
4. **LOW** finding (blockers.md defer 可): `[LOW-N]`
5. **Prior art summary** (web search 必須): 下記 §「Prior art 必須調査」全件
6. **Closing note**: hybrid v3 を採用すべきか / v1 / v2 / 別案、各 Critical
   Open Question (Tier B provisional pin / vLLM first-class / rikyu
   Burrows N/A fallback / rank=32 除外 4 件) への verdict

## Mission の再掲

M9-C-spike (PR #154 / #155 / #160 / #161 / #162 / #163、Phase K-α + K-β
完遂、CS-1..CS-9 + 3 amendment 2026-05-13) が SGLang adapter swap 8ms
cold latency / CS-7 4 trigger NON-FIRE / PEFT direct load / DB3 NON-FIRE
を empirical 実証した。本 PR (Phase A) は M9-C-adopt の **設計のみ、code
変更ゼロ** を起こし、5 つの未解決 open question (U1: rank=8 universal
adequacy / U2: min_examples=1000 quality signal / U3: fp8 serving
acceptance / U4: 3 persona expansion / U5: 8-mode FSM regression) を
empirical に閉じる Phase B-G を tasklist で定義する。

8 deliverable (本セッション完了条件):

1. `requirement.md` — 5 section (背景 / ゴール / scope-in / scope-out
   / 受入条件 AC-1..AC-6)
2. `design.md` v1 — 8 topic (A-1..A-8) 詳細
3. `design-v2-reimagine.md` — `/reimagine` 3 brittle 前提破棄
4. `design-comparison.md` — 8 軸比較 + hybrid v3 候補
5. `codex-review-prompt.md` (本 file)
6. `codex-review.md` — Codex 出力 verbatim
7. `design-final.md` — Codex HIGH 反映後最終案
8. `decisions.md` — DA-1..DA-10 ADR、各 5 要素

## 必読 reference files (本 prompt の review 対象)

### Claude 設計案 (3 件)

- `.steering/20260513-m9-c-adopt/design.md` (v1: 3 persona simultaneous
  1 PR + SGLang-only + 4 rank sweep)
- `.steering/20260513-m9-c-adopt/design-v2-reimagine.md` (Reim-1 vLLM
  first-class / Reim-2 rank sweep 縮減 / Reim-3 stage gate)
- `.steering/20260513-m9-c-adopt/design-comparison.md` (8 軸比較 +
  hybrid v3 候補: SGLang-only + rank {4,8,16} + provisional Tier B
  threshold pin + 1 PR 同時 3 persona)
- `.steering/20260513-m9-c-adopt/requirement.md` (AC-1..AC-6)

### ADR 制約 (絶対遵守、改変不可)

- `.steering/20260508-m9-c-spike/decisions.md` CS-1〜CS-9 + 3 amendment
  2026-05-13 (本 PR の **前提**、矛盾は HIGH 扱い)
- `.steering/20260508-m9-c-spike/blockers.md` D-1..D-6 (本 PR の依存)
- `.steering/20260430-m9-b-lora-execution-plan/decisions.md` DB1-DB11
  + 第3の道 ADR (本 PR は consumer)
- `.steering/20260430-m9-eval-system/decisions.md` ME-1〜ME-15 (本 PR
  は Tier B framework consumer)
- `.steering/20260508-m9-c-spike/codex-review-m9-c-spike.md` (前回
  Codex review verbatim、HIGH 4 / MEDIUM 6 / LOW 3 全反映済、style
  reference)

### 既存 infrastructure (流用先)

- `src/erre_sandbox/inference/sglang_adapter.py` — `SGLangChatClient`
  Phase H spike で実装済、OpenAI compatible
  `/v1/chat/completions` + LoRA load/unload、`_loaded` registry
- `src/erre_sandbox/inference/ollama_adapter.py` —
  `OllamaChatClient.chat(messages, *, sampling, model=None) ->
  ChatResponse` API 雛形、`OllamaUnavailableError` の単一エラー型
- `src/erre_sandbox/inference/sampling.py::compose_sampling` —
  `SamplingBase + SamplingDelta → ResolvedSampling` (唯一の合法的
  構成パス)
- `src/erre_sandbox/cognition/cycle.py:46-50` — `OllamaChatClient`
  injection point (Phase D で Union 型に拡張、本 PR では touch しない)
- `personas/{kant,nietzsche,rikyu}.yaml` — `default_sampling`
  persona ごと differentiated
- `tools/spike/build_mock_lora.py` — mock adapter builder (CS-9
  refusal guard 付き、`init_lora_weights=True` で identity transform)
- `docs/runbooks/m9-c-adapter-swap-runbook.md` (DB8) — adapter swap
  runbook (実測値込み)

## hybrid v3 の要点 (review 対象)

| 項目 | hybrid v3 commitment |
|---|---|
| backend 採用 | SGLang only + Ollama fallback (DB3 re-arm trigger 経由で vLLM 復活) |
| rank sweep 範囲 | rank ∈ {4, 8, 16} (rank=32 除外、VRAM headroom 圧迫リスク) |
| sweep 順序 | sequential (G-GEAR single GPU)、rank=8 anchor → rank=4 → rank=16 |
| 採用 rank 決定 | Vendi saturate floor ∩ ICC ≥ 0.6 ∩ throughput ≥ 70% baseline ceiling、smaller rank 優先 |
| 3 persona expansion | kant → nietzsche → rikyu sequential、`assert_phase_beta_ready(min_examples=1000)` gate per persona |
| persona-specific sampling | YAML `default_sampling` 保持 (LoRA は表層、sampling は ERRE mode-conditional micro adjust) |
| live path 切替 | `ERRE_INFERENCE_BACKEND ∈ {ollama, sglang}` feature flag (default `ollama`、A-8 verdict 後 flip) |
| `MultiBackendChatClient` | `inference/server.py` 新設、SGLang primary + Ollama fallback (adapter なし degraded mode) |
| multi_lora_3 bench | mock-first (Phase D) + real-after (Phase E) の 2 pass、CS-7 4 trigger 全 NON-FIRE 必須 |
| FSM smoke | 8 mode × 3 persona = 24 cell、`AgentState.erre.name == expected` のみ pass、`reason` field 除外 |
| Tier B 試料 | stimulus 500 turn × 5 run × 3 persona = 7500 turn (~29h G-GEAR) |
| Tier B threshold (provisional pin) | Vendi d ≥ 0.3 / ICC ≥ 0.6 / Burrows reduction ≥ 10%、rikyu は 2-of-2 fallback |
| marginal pass | 0.3 ≤ d < 0.5 かつ 0.6 ≤ ICC < 0.7 → ADOPT-WITH-CHANGES (retrain path、DA-9) |
| production loader | hard block (`ProductionLoaderRejectError` on weight_path NOT IN data/lora/m9-c-adopt/ OR is_mock=True) + checksum (sha256 + `AdapterIntegrityError`) + audit log |
| adapter pinning | 3 persona 全 pinned (VRAM peak ~8.8GB、headroom 7GB) |
| DB3 vLLM re-arm | SGLang launch fail 3 連続 OR adapter load p99 > 500ms 24h sustained OR Tier B quorum 0-of-3 |
| compute budget | Phase B 18h + Phase C 6-8h + Phase D 4-8h + Phase E 29h + Phase F 1 day = ~47h G-GEAR (overnight × 5-6) |
| PR scope | 1 PR で 3 persona simultaneous adopt 判定 (user 判断、stage gate 棄却) |

## Critical Open Questions (4 件、必ず Verdict + 理由を出してほしい)

### COQ-1: rank=32 除外の妥当性 (HIGH/MEDIUM 判定)

- v1: rank ∈ {4, 8, 16, 32} 全 sweep、24h compute
- v3 hybrid: rank=32 を除外、{4, 8, 16} で 18h compute
- 除外理由: VRAM headroom 7.3GB を rank=32 adapter ~200MB + activation
  増で圧迫、CS-4 budget 超過リスク、cost-benefit poor (LoRA Land /
  P-Tailor で rank=32 は uncommon、rank=4-16 が common practice)
- **問う**: literature shoulder と整合か、それとも rank=32 を含めるべきか

### COQ-2: provisional Tier B threshold pin の operational soundness (HIGH/MEDIUM 判定)

- 提案 pin 値:
  - Vendi semantic effect size (Cohen's d) ≥ 0.3 (literature small
    shoulder)
  - Big5 ICC(C,k) ≥ 0.6 (ME-11 fallback shoulder)
  - Burrows Δ reduction ≥ 10% (Burrows 1987 / Eder 2016 で 5-15% が
    discriminative shoulder)
- marginal pass (0.3 ≤ d < 0.5 / 0.6 ≤ ICC < 0.7) は ADOPT-WITH-CHANGES
  (retrain path、DA-9)
- 代替: framework のみ確定、empirical threshold は P4b 完了後の DA-11+
  で pin
- **問う**: provisional pin が persona-discriminative shoulder として
  operational か、それとも P4b empirical pin まで defer すべきか
- 引用必須: persona-conditional LLM 評価 literature (BIG5-CHAT、
  P-Tailor、Anthropic persona vector survey)

### COQ-3: vLLM late-binding option 保持 (MEDIUM 判定)

- v1 / v3 hybrid: vLLM は DB3 re-arm trigger 経由でのみ migration、
  本 PR では skeleton 残さない
- v2 reimagine (Reim-1): vLLM v0.15+ を first-class secondary に追加
  (`MultiBackendChatClient` 3 backend)
- **問う**: SGLang single-vendor risk を accept する判断が DB3 re-arm
  trigger だけで十分か、本 PR で vLLM path skeleton を残す価値があるか
- 引用必須: vLLM v0.15+ multi-LoRA runtime load の current stability
  (`VLLM_ALLOW_RUNTIME_LORA_UPDATING`)

### COQ-4: rikyu Burrows N/A の 2-of-2 fallback structural anomaly (MEDIUM 判定)

- v3 hybrid (DA-8): rikyu Japanese tokenizer 未実装で Burrows Δ N/A
  の場合、rikyu 限定で quorum = 2-of-2 (Vendi + ICC) を許容
- 代替: tokenizer 実装を hard blocker 化、rikyu の adopt 永続 block
- **問う**: persona ごとに quorum 数を変えるのは structural anomaly か、
  ME-* で同種 limitation 扱いは前例として有効か

## Prior art 必須調査 (web search 強制、verbatim 引用)

以下 6 件全件で literature 引用を伴う finding を出してほしい。1 件でも
skip したら REJECT 扱い。

1. **LoRA rank sweep best practice on Qwen-class 8B models** (2025-2026
   timeframe)
   - rank ∈ {4, 8, 16, 32} の published comparisons
   - rank=32 を含む / 含まない の operational decision rationale
   - 引用: LoRA Land (arxiv:2405.00732) / P-Tailor (arxiv:2406.12548) /
     other 2025-2026 surveys

2. **Persona-conditional LLM evaluation thresholds** (Vendi / Big5 ICC /
   Burrows Δ)
   - persona-discriminative shoulder (effect size、ICC、Δ reduction)
     の literature shoulder
   - BIG5-CHAT (arxiv:2410.16491 等) / Anthropic persona vector
     (anthropic.com/research/persona-vectors) / P-Tailor 等の
     concrete threshold value
   - small effect / medium effect / large effect の operational
     boundary

3. **SGLang multi-LoRA fragmentation behavior** (concurrent serving)
   - 2026 timeframe で SGLang 0.5+ の fragmentation report / GitHub
     issues (`sgl-project/sglang` の closed/open issues)
   - P-LoRA / ServerlessLoRA / DLoRA prior art の fragmentation
     analysis
   - SGLang 0.5.10.post1 で 3-adapter serving が production stable か

4. **vLLM v0.15+ multi-LoRA runtime load stability** (`VLLM_ALLOW_RUNTIME_
   LORA_UPDATING`)
   - vLLM v0.15 / v0.16 changelog で multi-LoRA / runtime updating の
     stability status
   - SGLang との feature parity / divergence (adapter pinning、
     `max-loaded-loras`、TTFT)

5. **Japanese tokenizer for stylometric analysis** (Burrows Δ on Japanese)
   - Japanese-aware tokenizer (`fugashi` / `sudachi` / `mecab`) の
     Burrows Δ への適用 prior art
   - 2025-2026 timeframe で Japanese stylometry survey
   - rikyu 等 1 persona Japanese corpus での Burrows Δ feasibility

6. **Production LoRA loader safety hard block** (HuggingFace Hub
   integration patterns)
   - HF Hub / PEFT loader での `is_mock` sentinel + path filter の
     production hardening pattern
   - 2025-2026 timeframe で adapter checksum / audit log の OSS pattern
   - `safetensors` + sha256 の adoption rate

## review 要件

- **HIGH** = M9-C-spike CS-N と矛盾するもの / persona-discriminative
  threshold が literature と乖離するもの / production safety にユーザー
  影響を起こすもの / Phase B-G の手戻りで >1 week 失うもの → 全反映
  必須
- **MEDIUM** = ADR (DA-N) で採否を記録すべきもの / Codex MEDIUM 反映
  例 (M9-eval-system / M9-C-spike) と整合 → DA-N で trace、本 PR 反映可
- **LOW** = blockers.md で defer 可、本 PR 反映不要

## 報告長 / 様式

- 全体 800-2000 行を許容 (M9-C-spike review が 198K tok だった、本回
  も同等規模で OK)
- HIGH / MEDIUM / LOW の各 finding に **必ず literature URL or DOI**
  を入れる
- prior art summary は web search 結果の verbatim quote を含めてよい
- closing note で `hybrid v3 を採用すべきか / v1 / v2 / 別案` の
  verdict + 4 COQ への answer を 1 paragraph で要約

## 期待される Verdict

`ADOPT-WITH-CHANGES` (HIGH 3-5 件、MEDIUM 5-7 件、LOW 2-3 件) を期待
する。spike review が HIGH 4 / MEDIUM 6 / LOW 3 だったので同等規模。

------------------------------------------------------------

Verdict (1 行) から始めてください。
