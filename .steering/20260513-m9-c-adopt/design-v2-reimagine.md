# 設計 v2 — `/reimagine` で起こした再生成案 (brittle 前提 3 個破棄)

> CLAUDE.md 「高難度設計で `/reimagine` 必須」に従い、design.md v1 を一旦
> **意図的に破棄** し、ゼロから v2 を再生成する。v1 の 3 つの brittle 前提
> を全て破棄したらどうなるかを記述する。8 軸比較は `design-comparison.md`、
> 採用案 (hybrid v3) は `design-final.md`。
>
> **本 v2 は「全てを破棄」前提のため v1 と直接矛盾する箇所を含む**。
> Codex review で構造的バイアスを露出させる狙い。最終的に hybrid で
> どこを採用するかは Codex Verdict + comparison で決定する。

---

## 破棄する 3 つの brittle 前提

### Reim-1: 「SGLang-first」を破棄

**v1 の前提**: DB3 NON-FIRE と spike 8ms latency が SGLang を unconditional
best と暗示し、`MultiBackendChatClient` は Ollama fallback のみ。

**v2 の破棄**: vLLM v0.15+ の multi-LoRA runtime load (`VLLM_ALLOW_RUNTIME_
LORA_UPDATING`) を **first-class fallback** として `MultiBackendChatClient`
の 3 backend 目に組み込む。SGLang fragmentation behavior が未測 (P-LoRA /
ServerlessLoRA prior art で documented)、real workload (3 persona 同時 +
mixed length prompts + concurrent users) で degradation する可能性があり、
DB3 re-arm trigger を待たずに vLLM への自動 fallback path を保持する。

**v2 で変わること**:

- `MultiBackendChatClient` は 3 backend (Ollama / SGLang / vLLM)、
  health check で primary SGLang → secondary vLLM → tertiary Ollama
  (adapter なし degraded) の cascade
- vLLM 起動が WSL2 venv に inference dependency 追加 (`vllm>=0.15`)
  必要 → `pyproject.toml` `[inference]` extra が膨らむ
- bench protocol が 3 baseline (no_lora / SGLang single / vLLM single)
  + 3 multi_lora_3 (SGLang / vLLM / mock) に拡大、A-4 scope 1.5x
- DA-2 (live path) / DA-4 (bootstrap 失敗) / DA-5 (multi_lora_3 2 pass)
  が全て影響を受け、PR scope が現実的でない可能性

**Codex review で出てほしい指摘**:

- "SGLang spike 8ms latency は cold load の 60x margin だが、3 persona
  concurrent serving での **fragmentation behavior は未測** (P-LoRA /
  ServerlessLoRA prior art)、real workload で degradation する余地ある"
- "vLLM への late-binding を A-8 fallback でなく first-class option
  として残せ"
- **反対意見の期待**: "vLLM dual path は本 PR scope を broaden しすぎる、
  DB3 re-arm trigger 経由で足りる"

---

### Reim-2: 「sequential rank sweep (4/8/16/32)」を破棄

**v1 の前提**: 4 rank × 3 persona = 24h を G-GEAR overnight 3 night で
実行する受容性、Tier B Vendi saturate floor で empirical 決定。

**v2 の破棄**: rank sweep を **hypothesis-confirmation mode** に切り替え、
rank=8 を anchor として **rank=16 単点のみ追加** で saturate 確認。compute
budget が 24h → ~10h に短縮、Phase B 完了が早期化。empirical sweep を
広く実施せず literature shoulder (LoRA Land、P-Tailor で rank=4-16 が
common practice) に依拠する。

**v2 で変わること**:

- A-1 sweep 範囲 `rank ∈ {8, 16}` のみ (rank=4 / rank=32 は archival
  対象外、empirical 比較不能)
- DA-1 採用基準が "Vendi saturate floor" から "rank=8 hypothesis-confirm
  + rank=16 で marginal improvement なければ rank=8 final" に簡略化
- 棄却 rank archival 体制が縮小、後続研究 baseline 価値が減る
- compute budget 削減で Phase B → Phase C 移行が早まる (~14h 短縮)
- Tier B (A-6) で rank=4/32 が「未確認」のまま residual unknown

**Codex review で出てほしい指摘**:

- "rank sweep の compute cost / signal value ratio が poor、rank=8 を
  hypothesis-confirmation mode で進め、必要時のみ追加 sweep"
- "binary search は LoRA で uncommon、PEFT/unsloth default が powers-of-2
  のため非推奨"
- **反対意見の期待**: "M9-C-adopt は CS-5 closure phase、empirical sweep
  を skip すると U1 が closure できず M9-D に持ち越し"

---

### Reim-3: 「1 PR で 3 persona 同時 adopt」を破棄、stage gate に

**※ 本 reimagine は user 判断 (1 PR 3 persona 同時) で採用しない**。
ただし、reimagine プロセスの完全性のため記述し、Codex review でも問う。

**v1 の前提**: 3 persona を 1 PR で adopt 判定する大きすぎる scope、
失敗 blast radius 大。

**v2 の破棄**: stage gate 3 PR に分割:
- **Phase B**: kant 単独 adopt (single_lora live path)、live で 1 week
  soak
- **Phase C**: nietzsche 追加 (multi_lora_2)、soak
- **Phase D**: rikyu 追加 (multi_lora_3)

**v2 で変わること**:

- A-4 multi_lora_3 bench は Phase D まで後ろ倒し、A-6 Tier B も 3 phase
  に分散
- DB3 re-arm trigger は phase ごとに re-evaluate、early stop が可能
  (= kant でだけ adopt、nietzsche/rikyu 永続 defer も option)
- tasklist.md は Phase B-Z が大幅 expand、~6 week → ~10-12 week
- PR 数 3 倍、Codex review も 3 回独立必要 (cost 増)

**Codex review で出てほしい指摘**:

- "3 persona 同時 adopt は M9-eval-system 完成度 + LoRA-on Tier B の
  2 軸 risk を同時に受ける、stage gate で scope を絞れ"
- "single persona soak で観測される early-warning (memory leak、adapter
  swap latency drift) を 3 persona 環境で先取りすると attribution 困難"
- **反対意見の期待**: "user が 1 PR 同時を選択している、stage gate は
  scope creep + roadmap delay + PR overhead で net-negative"

---

## v2 採用時の design 全体への波及

仮に v2 (Reim-1 + Reim-2 のみ採用、Reim-3 は user 棄却) で進めた場合の
影響:

### A-1 (rank sweep)
- 範囲: `rank ∈ {8, 16}` のみ
- 採用基準: rank=8 hypothesis-confirm、rank=16 で marginal
  improvement (Vendi Δ < 0.05、ICC Δ < 0.02) → rank=8 final、
  otherwise rank=16 adopt
- 棄却 rank archival: rank=8 / rank=16 のみ、rank=4 / rank=32 は
  scope 外
- compute: 2 rank × 3 persona × ~2h = ~12h (G-GEAR overnight × 2)

### A-2 (3 persona expansion)
- 変化なし (Reim-3 不採用、3 persona simultaneous は v1 通り)

### A-3 (live inference path 統合)
- **大幅変更**: `MultiBackendChatClient` が 3 backend 対応
  - primary: SGLang
  - secondary: vLLM v0.15+ (新規追加)
  - tertiary: Ollama (degraded fallback)
- `ERRE_INFERENCE_BACKEND ∈ {ollama, sglang, vllm}` の 3 値
- bootstrap: SGLang fail → vLLM 起動試行、両方 fail → Ollama degraded
- `vllm` package install 必要、`pyproject.toml [inference]` 拡張

### A-4 (multi_lora_3 bench)
- bench protocol 拡張: SGLang multi_lora_3 + vLLM multi_lora_3 の
  2 backend で独立 bench、CS-7 4 trigger 両 backend で全 NON-FIRE
  必須
- mock-first / real-after は同じ、ただし 4 condition (no_lora /
  single_lora-sglang / multi_lora_3-sglang / multi_lora_3-vllm) ×
  2 pass (mock / real) = 8 jsonl artefact

### A-5 (FSM smoke)
- 変化なし、ただし backend ごとに 24 cell smoke が必要なら 48 cell
  に倍増 (DA-2 v2 で SGLang primary だけで足りるか議論)

### A-6 (Tier B validation)
- 試料 size 変化なし、SGLang primary backend で採取
- vLLM fallback path の Tier B は別途 sanity smoke (50 turn × 3
  persona = 150 turn) で simulating

### A-7 (production safety)
- mock-LoRA hard block + checksum 検証は SGLang / vLLM 両方で適用
- vLLM の adapter load 経路 (HF hub direct or local path) が
  SGLang と異なる場合、`_validate_production_path()` を backend-agnostic
  に拡張

### A-8 (採用判定基準)
- DB3 re-arm trigger を緩和: SGLang fail で **vLLM 自動 fallback** が
  primary path となり、Ollama fallback は緊急時のみ
- latency ceiling は backend ごとに分離 (SGLang p99 < 50ms、vLLM p99
  < 100ms、Ollama p99 < 1000ms)

---

## v2 の DA 影響表

| ADR | v1 | v2 (Reim-1 + Reim-2 採用時) |
|---|---|---|
| DA-1 | rank ∈ {4,8,16,32} sweep | rank ∈ {8, 16} hypothesis-confirm |
| DA-2 | feature flag {ollama, sglang} | feature flag {ollama, sglang, vllm} |
| DA-3 | 3 persona sequential | 同じ |
| DA-4 | 2 backend bootstrap | 3 backend bootstrap |
| DA-5 | mock-first / real-after 2 pass | SGLang / vLLM 両 backend で 2 pass = 4 jsonl |
| DA-6 | mock hard block (SGLang) | mock hard block (SGLang + vLLM) |
| DA-7 | FSM smoke 24 cell | 48 cell (backend × persona × mode) |
| DA-8 | Tier B 2-of-3 quorum | 同じ |
| DA-9 | marginal pass = ADOPT-WITH-CHANGES | 同じ |
| DA-10 | sha256 checksum | 同じ |

---

## v2 の trade-off

**v2 (Reim-1 + Reim-2 採用) の利点**:

- vLLM first-class で SGLang single-vendor risk 低減
- rank sweep compute 削減で Phase B → C 早期化 ~14h
- DB3 re-arm trigger を待たない proactive fallback

**v2 の欠点**:

- `MultiBackendChatClient` complexity 1.5-2x (3 backend health check、
  dispatch logic、test surface)
- vLLM install 必要 (CUDA 12.x、`pyproject.toml [inference]` 拡張)
- A-4 bench 2 backend 化で artefact / time が 2x
- empirical rank sweep を skip すると CS-5 closure が不完全

**v1 (本 plan default) の利点**:

- scope tight、PR 完了が予測可能
- SGLang spike 8ms latency / DB3 NON-FIRE 実証済 = 単一 backend で十分
- empirical rank sweep で U1 closure が完全
- compute 24h で許容範囲

**v1 の欠点**:

- SGLang single-vendor risk (upstream regression、fragmentation)
- rank sweep 24h compute は marginal value の可能性
- DB3 re-arm trigger 24h sustained 監視が phase G まで実装されない

---

## v3 hybrid 採用方針 (design-final.md で確定)

Codex review 待ちだが、初期候補 hybrid:

- **Reim-1 (vLLM first-class)**: **採用しない** (本 PR scope tight 優先、
  DB3 re-arm trigger で足りる、Codex MEDIUM 反対意見と整合)
- **Reim-2 (rank sweep 縮減)**: **部分採用** (rank ∈ {4, 8, 16} の 3 値
  に縮める案、rank=32 を VRAM headroom 圧迫 risk で除外、compute 18h)
- **Reim-3 (stage gate)**: **採用しない** (user 判断、1 PR 同時で進める)

最終 hybrid v3 は Codex review 後の `design-final.md` で確定。HIGH
finding 反映 + MEDIUM 採否を `decisions.md` で trace。
