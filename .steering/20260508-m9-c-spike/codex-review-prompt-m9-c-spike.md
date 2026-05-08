# Codex independent review request — m9-c-spike (bounded Kant LoRA spike on SGLang)

## 役割

あなたは ERRE-Sandbox プロジェクトの **independent reviewer**。Claude が起草
した m9-c-spike 設計案 (v1 + v2 + comparison v3) を **同一モデル 1 発生成の
構造的バイアス** から救出するために招かれている。Verdict + 優先度付き finding
+ web-search-based prior art 引用で reply してほしい。要約禁止、verbatim 保存
される。

## 報告フォーマット (厳守)

1. **Verdict**: 一行 — `APPROVE` / `ADOPT-WITH-CHANGES` / `REJECT`
2. **HIGH** finding (must reflect before merge): `[HIGH-N] title` +
   ≥3 行 rationale + 引用 (URL or paper)
3. **MEDIUM** finding (decisions.md ADR 反映): `[MEDIUM-N]`
4. **LOW** finding (blockers.md defer 可): `[LOW-N]`
5. **Prior art summary** (web search 必須): 下記 §「Prior art 必須調査」全件
6. **Closing note**: v3 hybrid を採用すべきか / v1 / v2 / 別案

## Mission の再掲

`src/erre_sandbox/inference/sglang_adapter.py` 新設 + `src/erre_sandbox/training/`
module 新設で、Kant 1 persona の bounded LoRA spike を実行可能にする。本 spike
は **non-authoritative** (M9-B `decisions.md` 第3の道 ADR、PR #127 merged)、
評価系構築中に LoRA 学習・adapter swap・runtime 技術リスクを早期検出する目的。

5 deliverable:

1. SGLang LoRA endpoint 動作確認 (`--enable-lora` + `/load_lora_adapter`)
2. **adapter swap latency** 実測 (>500ms は DB3 vLLM fallback fire)
3. **N=3 同時 request throughput** 実測
4. M5 resonance / ERRE FSM regression 確認
5. adapter swap runbook (DB8) 起草 (本 spike 完了後)

## 必読 reference files (本 prompt の review 対象)

### Claude 設計案 (3 件)

- `.steering/20260508-m9-c-spike/m9-c-spike-design-v1.md` (infrastructure-first
  + Kant 1 persona)
- `.steering/20260508-m9-c-spike/m9-c-spike-design-v2.md` (fail-fast +
  multi-persona)
- `.steering/20260508-m9-c-spike/m9-c-spike-design-comparison.md` (v3 hybrid:
  Phase α mock-LoRA + Phase β Kant 1 rank=8)
- `.steering/20260508-m9-c-spike/requirement.md`

### ADR 制約 (絶対遵守)

- `.steering/20260430-m9-b-lora-execution-plan/decisions.md` DB1-DB11 +
  第3の道 ADR (M9-B)
- `.steering/20260430-m9-eval-system/decisions.md` ME-1〜ME-15 (M9-eval)
- `.steering/20260430-m9-eval-system/codex-review-p4a.md` (前回 Codex review、
  HIGH 4 / MEDIUM 5 / LOW 3 全反映済)

### 既存 infrastructure (流用先)

- `src/erre_sandbox/inference/ollama_adapter.py` —
  `OllamaChatClient.chat(messages, *, sampling, model=None) -> ChatResponse`
  API 雛形、`OllamaUnavailableError` の単一エラー型統合 pattern
- `src/erre_sandbox/evidence/eval_store.py::connect_training_view` —
  `RawTrainingRelation` 経由で raw_dialog rows を `ALLOWED_RAW_DIALOG_KEYS`
  projection で取得 (DB5 contract)
- `src/erre_sandbox/contracts/eval_paths.py::ALLOWED_RAW_DIALOG_KEYS` — DB5
  allow-list (現状 `individual_layer_enabled` 未追加、DB11 follow-up は別タスク)
- `src/erre_sandbox/schemas.py::EpochPhase` (L254、enum: AUTONOMOUS /
  Q_AND_A / EVALUATION) — training-eligible 判定の正しい field 名
- 既存 spike 前例: `.steering/20260420-m5-llm-spike/`

## v3 hybrid の要点 (review 対象)

| 項目 | v3 commitment |
|---|---|
| Phase 構造 | Phase α (mock-LoRA infrastructure proof、data-independent、即実行可) + Phase β (P3 golden baseline 完了 trigger で Kant 1 persona real training) |
| Spike scope | Kant 1 persona (M9-B 第3の道 ADR 逐語)、3 persona batch は M9-C-adopt territory に defer |
| Base model | qwen3:8b |
| Quantization | QLoRA NF4 (DB1 default) |
| Library | PEFT (DB2 暫定、final は M9-C-adopt) |
| Adapter rank | rank=8 (M9-C-adopt 統一 spike continuity) |
| Serving | SGLang `--enable-lora` + `/load_lora_adapter` REST (DB3) |
| Mock-LoRA | random-init or HF hub borrow weight、`tools/spike/build_mock_lora.py` に隔離 |
| Training data minimum (Phase β) | P3 golden baseline 完了後の Kant 部分 ~2500 turn |
| Adapter swap latency target | <500ms (>500ms は DB3 re-open / vLLM fallback) |
| VRAM 予算 (G-GEAR RTX 5060 Ti 16GB) | training peak ~9.7-10.2GB、headroom ~5.8GB |
| code module 配置 | `inference/sglang_adapter.py` 新設、`training/` 新設、`tools/spike/build_mock_lora.py` 隔離 |

## Prior art 必須調査 (web search 強制、verbatim 引用)

以下 8 件全件で literature 引用を伴う finding を出してほしい。1 件でも skip
したら REJECT 扱い。

1. **SGLang `--enable-lora` 最新 stability** (v0.3+ multi-LoRA / dynamic
   load/unload / pinned adapters / overlap loading)
   - v0.3 / v0.4 / v0.5 / v0.6 のうち current released の changelog 確認
   - `/load_lora_adapter` / `/unload_lora_adapter` / `/list_lora_adapters`
     REST endpoint の actual path / payload schema
   - SGLang v0.3+ がドキュメントしているのは確かに **multi-LoRA stable** か
     (Codex P4a HIGH-3 で確認済の認識を verify)

2. **PEFT QLoRA NF4 vs 8-bit on consumer 16GB GPU**
   - bitsandbytes NF4 vs int8 の VRAM benchmark
   - gradient_checkpointing 採用での VRAM 削減効果 (training time trade-off)
   - Qwen3-8B + LoRA rank=8 での typical training VRAM peak

3. **LoRA training minimum data size for persona-conditional adaptation**
   (2024-2026 prior art)
   - rank=4 vs rank=8 で何 example が adequate か
   - persona-conditional fine-tune の literature (Salecha 2024、Anthropic
     persona vector research、Huang et al.、Tan et al. 等)
   - ~2500 turn (Kant 部分) で sufficient か

4. **SGLang vs vLLM v0.6+ multi-LoRA performance comparison**
   - throughput / latency / cold start の benchmark (2024-2026)
   - DB3 v1/v2 が stale だった事実を踏まえ、current state を再確認
   - vLLM `--enable-lora` の status

5. **LoRA adapter format conversion (PEFT safetensors → SGLang weight format)**
   - PEFT 標準 safetensors を SGLang `--lora-paths` が直接受付するか
   - 変換 script が必要なら、existing tooling (例: `lora_adapter_converter`
     等) があるか
   - undocumented なら自前 conversion の妥当性

6. **Mock-LoRA random-init weight が SGLang `/load_lora_adapter` で受付されるか**
   - PEFT format validation の strictness
   - random init で base model の generation が破綻しないか (sanity)
   - mock-LoRA を infrastructure proof tool として使う prior art

7. **adapter swap latency threshold 500ms の operations 根拠**
   - production LLM serving での adapter swap latency budget
   - SGLang documented swap latency benchmark
   - >500ms threshold が DB3 fallback fire 条件として適切か

8. **N=3 同時 request collapse 検出 protocol**
   - throughput / latency p99 / queue depth の measurement framework
   - SGLang `--max-running-requests` での N=3 設定の典型 pattern
   - collapse 判定の operational definition

## review で必ず check してほしい質問群

### Phase α (Mock-LoRA) 関連

- Q-α1: random-init or HF hub borrow weight が SGLang format validation を
  pass するか
- Q-α2: mock-LoRA を `tools/spike/` に隔離する設計の妥当性 (production code
  外、誤起動防止)
- Q-α3: Phase α が data-independent に **deliverable 1-4 全件** を early ship
  できるか (latency / throughput / FSM regression の判定条件)
- Q-α4: Phase α で >500ms latency が観測されたら直ちに DB3 vLLM fallback fire
  すべきか、それとも Phase β real training 後に再判定か

### Phase β (Real training) 関連

- Q-β1: rank=8 が persona-conditional adaptation に sufficient か (prior art
  2024-2026)
- Q-β2: Kant ~2500 turn (P3 golden baseline 完了後) で sufficient training
  data か、もっと必要か
- Q-β3: training/serving 同 G-GEAR で run する dual-machine workflow の
  adapter format 共有が clean か
- Q-β4: gradient_checkpointing 採用で VRAM 9.7-10.2GB → 7.5-8GB 削減の
  trade-off 妥当性

### SGLang serving 関連

- Q-S1: SGLang `--enable-lora` + `/load_lora_adapter` の current released
  version で multi-LoRA stable か (v0.5 / v0.6 等 specific version pin)
- Q-S2: PEFT safetensors → SGLang weight format conversion path の
  documented 有無
- Q-S3: SGLang `--max-running-requests` で N=3 の throughput collapse 検出
  protocol
- Q-S4: pinned adapters の M5 resonance / ERRE FSM 経路への影響

### VRAM 関連

- Q-V1: RTX 5060 Ti 16GB で QLoRA NF4 8B + rank=8 + training gradient ~9.7-10.2GB
  の予算妥当性 (実測ベンチマーク)
- Q-V2: gradient_checkpointing で 7.5-8GB に下げる trade-off (training time
  +20-30%)
- Q-V3: 5.8GB headroom が CUDA fragmentation / long-context generation の
  overhead を吸収できるか

### 設計全体

- Q-G1: v3 (Phase α + Phase β) が v1 (full real spike) + v2 (mock + 3 persona)
  の structural bias を残していないか (independent reviewer 視点)
- Q-G2: M9-B 第3の道 ADR の "bounded, non-authoritative single-persona Kant
  LoRA spike" との整合 (Phase α 追加が ADR 文言を逸脱しないか)
- Q-G3: DB3 fallback 条件 trigger (>500ms latency / N=3 collapse / FSM
  regression) のうち single vs composite で fire するか
- Q-G4: M9-eval P3 golden baseline 完了見込みが大幅遅延した場合の Phase β
  contingency plan
- Q-G5: 本 spike 完了後の DB8 adapter swap runbook 起草 timing と内容

## 出力先

verdict + finding は **そのまま raw text** で reply。Claude が
`.steering/20260508-m9-c-spike/codex-review-m9-c-spike.md` に **verbatim 保存**
する (要約禁止)。

## 工数 expectation

- web search 8 件全件 + finding 起票で **30-45 分**、token 予算 ~150K-200K
  程度を想定 (`.codex/budget.json` の per-invocation max 200K 内)

## 最後に

直近 6 連続の Codex review (P3a-finalize / Phase 2 run0 / CLI partial-fix /
run1 calibration / ME-9 trigger / P4a Tier B) で Claude solo 検出不能の HIGH
を毎回切り出してきた empirical 実績がある。本 review でも同質の補正を期待
する。Adopt-with-changes が default expected verdict。
