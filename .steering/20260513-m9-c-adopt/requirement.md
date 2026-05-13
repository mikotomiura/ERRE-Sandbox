# m9-c-adopt — Phase A design scaffold (3 persona LoRA adopt judgment on SGLang live path)

## 背景

M9-C-spike (PR #154 / #155 / #160 / #161 / #162 / #163、Phase K-α + K-β
完遂) で、bounded Kant LoRA on SGLang の technical PoC が完了した。
本 spike の verified empirical 実測は以下:

- **SGLang 0.5.10.post1 + WSL2 execution boundary** (G-GEAR RTX 5060 Ti
  16GB、native Windows NOT supported)
- **adapter swap latency** cold/warm median **8ms** (CS-8 amendment、500ms
  threshold の **60x margin**)
- **CS-7 4 trigger 全 NON-FIRE**: single_lora vs no_lora で throughput
  2.5% 差、p95 e2e 1.026x (single_lora_throughput=34.64 tok/s、
  no_lora=35.54 tok/s)
- **real Kant LoRA adapter** (`kant_r8_real`、30.7MB) が PEFT direct load
  確認、conversion script 不要 (CS-6 acceptance)
- **kant training data 5022 examples** が `min_examples=1000` の 5.02x
  margin で確保 (CS-3 dry-run 検証、`.steering/20260508-m9-c-spike/
  k-beta-dry-run.log`)
- **DB3 vLLM fallback NON-FIRE** 確定 (SGLang-first 採用)

しかし、M9-C-spike は本質的に "Kant 1 persona / mock benchmark /
single_lora 比較" に **bounded scope**。production-grade live inference
path への統合判断 (DB9 quorum + Tier B persona-discriminative threshold +
live cycle wiring) は spike scope の外で defer されており、5 つの
**adopt-side open question** が未解決のまま残る:

- **U1: rank=8 universal adequacy** (CS-5 留保、`continuity hypothesis`
  のみ。rank sweep 4/8/16/32 で empirical 決定が必要)
- **U2: min_examples=1000 quality signal** (CS-3 で operational SLO 確定
  したが Tier B Vendi / Big5 ICC で persona-discriminative signal が
  返るか未測)
- **U3: fp8 serving acceptance** (K-α serving は fp8 base 強制、M9-eval
  P6 judge LLM が fp8 base の output を accept するか未検証)
- **U4: 3 persona expansion** (D-3 defer、Nietzsche / Rikyu の training
  data 抽出 + persona-specific tuning 要件未確定)
- **U5: 8-mode FSM regression** (D-5 部分解消、K-α は deep_work mode
  smoke のみ。残り 7 mode で AnimationTree state machine が SGLang LoRA
  経路で regression していないか確認必要)

M9-C-adopt はこれら 5 open question を **empirical** に閉じ、現状
`OllamaChatClient` 経由の live path
(`src/erre_sandbox/cognition/cycle.py:46-50`) を `SGLangChatClient`
+ LoRA adapter routing へ swap する **production adopt 判定** を下す
phase。本 PR (Phase A) は **設計のみ** を起こし、Phase B 以降の実装
work item を tasklist で固定する。

直近完了状態 (2026-05-13 時点):
- main HEAD = `c1e118c` (Merge PR #163)
- M9-C-spike 全 PR merged (#154 / #155 / #160 / #161 / #162 / #163)
- WSL2 venv に peft 0.19.1 / bitsandbytes 0.49.2 / accelerate 1.13.0
  install 済 (B-3 解消)
- `/root/erre-sandbox/checkpoints/kant_r8_real/` に real Kant LoRA
  adapter (rank=8、30.7MB)
- `data/eval/spike/m9-c-spike-bench/{k-beta-swap-latency,single_lora,
  no_lora}.jsonl` artefact 揃い済
- `docs/runbooks/m9-c-adapter-swap-runbook.md` (DB8) 完成
- M9-C-spike `decisions.md` CS-3 / CS-7 / CS-8 amendment 2026-05-13 で
  実測値全 verbatim 反映済

## ゴール

本タスクは **本 PR (Phase A) と次セッション以降 (Phase B-G)** に分かれる:

### 本 PR (Phase A) scope = 設計のみ、code 変更ゼロ

1. `.steering/20260513-m9-c-adopt/` の **scaffold 全 10 file** 配置完了
2. `design.md` v1 (3 persona simultaneous 1 PR 採用案) → `/reimagine` で
   v2 (vLLM first-class fallback + rank=8 hypothesis-confirm) →
   `design-comparison.md` で 8 軸比較 → hybrid `design-final.md` 確定
3. Codex `gpt-5.5 xhigh` independent review 実行 (in-session、`.codex/
   budget.json` 1M daily 内、想定 ~200k token)、`codex-review.md`
   verbatim 保存、HIGH 全反映を `design-final.md` に明示
4. `decisions.md` に **DA-1〜DA-10** ADR 起票、各 5 要素 (決定 / 根拠
   / 棄却 / 影響 / re-open 条件)
5. `tasklist.md` に Phase A-G + H-Z placeholder roadmap
6. `blockers.md` に hard / soft / defer / uncertainty 4 区分で記録
7. `feature/m9-c-adopt-design` ブランチで PR 起票、PR description で
   Codex Verdict + HIGH 反映マッピング表 + "code 変更ゼロ" 明示

### 次セッション以降 (Phase B-G) scope = 実装 + 訓練 + 実走

- **Phase B** (~24h G-GEAR overnight × 3): rank sweep 4 値 × kant
- **Phase C** (~6-8h G-GEAR sequential): adopted rank で
  nietzsche_r{X}_real / rikyu_r{X}_real 訓練
- **Phase D** (1-2 day Mac + 4h G-GEAR bench): live path 統合
  (`MultiBackendChatClient` 新設)、mock multi_lora_3 bench
- **Phase E** (~29h G-GEAR 3 night + 1 day Mac): FSM smoke + Tier B
  validation + real multi_lora_3 post-bench
- **Phase F** (1 day Mac): production safety + A-8 verdict report
- **Phase G** (1 week soak + 半日 code): `ERRE_INFERENCE_BACKEND`
  default を `sglang` に flip

## スコープ

### 含むもの (8 topic、A-1..A-8)

- **A-1: rank sweep** (CS-5 / D-2 / U-1 closure): default `rank ∈ {4, 8, 16}`
  の sequential sweep (Codex HIGH-1 反映で rank=32 は conditional
  tail-sweep trigger 経由)、Tier B Vendi + Big5 ICC + bench throughput
  の 3 軸 intersection で採用 rank 決定 (Codex HIGH-2 反映で bootstrap CI
  lower bound + baseline direction 必須)
- **A-2: 3 persona expansion** (D-3 closure): kant → nietzsche → rikyu
  sequential 訓練、persona-specific sampling override は YAML 既存定義
  保持 (CS-5 整合)
- **A-3: live inference path 統合** (D-5 closure): `MultiBackendChatClient`
  wrapper を `inference/server.py` に新設、`ERRE_INFERENCE_BACKEND ∈
  {ollama, sglang}` feature flag、Ollama fallback degraded mode
- **A-4: multi_lora_3 bench** (CS-7 defer 解消): mock_nietzsche_r8 +
  mock_rikyu_r8 を `tools/spike/build_mock_lora.py` で生成、CS-7 4
  trigger 全 NON-FIRE 確認 (mock-first / real-after-A2 の 2 pass、
  DA-5)
- **A-5: M5 resonance / 8-mode FSM smoke** (D-5 full closure): 8 mode
  × 3 persona = 24 cell smoke、`AgentState.erre.name == expected`
  のみ pass 基準 (reason field は LoRA wording drift 容認、DA-7)
- **A-6: Tier B empirical validation** (U-1 / U-2 closure): stimulus
  500 turn × 5 run × 3 persona = 7500 turn (~29h G-GEAR)、Vendi
  semantic kernel + Big5 ICC(C,k) + IPIP-NEO-120
- **A-7: production safety** (CS-9 amendment): mock-LoRA hard block
  (`ProductionLoaderRejectError`)、adapter pinning policy (3 persona
  全 pinned)、`adapter_model.safetensors` の sha256 checksum 検証
  (`AdapterIntegrityError`)
- **A-8: 採用判定基準 formal 化** (DB9 quorum + CS-7/CS-8 ceiling): Tier B
  2-of-3 quorum + bench CS-7 全 NON-FIRE + latency p99 ceiling + DB3
  vLLM re-arm trigger、ADOPT / ADOPT-WITH-CHANGES / REJECT verdict
  framework

### 含まないもの

- M9-eval-system 改造 (Tier C P6 judge LLM 内部実装は ME-1..ME-15 に
  閉じる、本 PR は consume side のみ)
- M9-B 再設計 (DB1-DB11 + 第3の道 ADR は immutable、本 PR は consumer
  side で adopt 判定のみ)
- M5 resonance 内部改造 (FSM transition 行列 / `_infer_shift_reason()`
  の touch 禁止、A-5 は LoRA-on で existing FSM が regression しないか
  の **観察** のみ)
- vLLM full migration (DB3 NON-FIRE 確定後の "future option"、defer
  継続。Reim-1 で first-class fallback option として `MultiBackendChatClient`
  3 backend 目に組み込む可否のみ Codex に問う)
- PEFT vs unsloth final 選定 (D-2 defer 継続、rank sweep 結果で再判定)
- 4 persona 目以降 (Confucius / Socrates 等、M10 範囲)
- Phase B-G の **実装 / 訓練 / 実走** (本 PR は設計のみ、code 変更ゼロ)
- Tier B persona-discriminative threshold の empirical pin (framework
  のみ確定、threshold は P4b 完了後の DA-11+ で pin。Codex に provisional
  pin の可否を問う)

## 受け入れ条件

- [ ] **AC-1**: rank sweep (default `rank ∈ {4, 8, 16}`、Codex HIGH-1
  反映で rank=32 は conditional tail-sweep trigger 経由) で training を
  完遂し、Tier B Vendi 飽和 floor + Big5 ICC(C,k) ≥ 0.6 (Codex HIGH-2
  反映で bootstrap CI lower bound + baseline direction 同時 PASS 必須)
  + bench throughput ≥ 70% baseline の 3 軸 intersection で採用 rank
  が empirical に決定される (Phase B 完了条件、DA-1)。SGLang launch
  arg `--max-lora-rank >= 16` (Codex HIGH-1 fix) で rank=16 を実際に
  serving できる契約
- [ ] **AC-2**: 3 persona LoRA adapter (`kant_r{採用}_real` /
  `nietzsche_r{採用}_real` / `rikyu_r{採用}_real`) が `data/lora/
  m9-c-adopt/` に揃い、SGLang multi-adapter pin で同時 load 可能
  (Phase C 完了条件、DA-3)
- [ ] **AC-3**: live inference path で `SGLangChatClient` injection が
  feature flag (`ERRE_INFERENCE_BACKEND={ollama|sglang}`) 経由で
  切替可能、Ollama fallback 健全 (SGLang unreachable で degraded mode、
  adapter なしで継続、`degraded_to_ollama=True` flag が `CycleResult`
  に記録) (Phase D 完了条件、DA-2 / DA-4)
- [ ] **AC-4**: multi_lora_3 bench で CS-7 4 trigger 全 NON-FIRE
  (single_lora baseline の 70% throughput floor 保持、p95 e2e < 2x
  baseline、adapter-misrouting 0 件、timeout 0 件) (mock-first
  Phase D + real-after Phase E の 2 pass、DA-5)
- [ ] **AC-5**: 8-mode FSM smoke で 8 mode × 3 persona = 24 cell 全てで
  valid state transition 観察、regression 無し
  (`AgentState.erre.name == expected`、reason field 除外、
  Phase E 完了条件、DA-7)
- [ ] **AC-6**: Tier B 3 metric (Vendi semantic + Big5 ICC + Burrows Δ)
  で **2-of-3 quorum 通過**、A-8 verdict 確定 (ADOPT / ADOPT-WITH-CHANGES
  / REJECT)。rikyu Burrows N/A 時は 2-of-2 (DA-8)
  (Phase E + F 完了条件、DA-8 / DA-9)

## 関連ドキュメント

- `.steering/20260508-m9-c-spike/decisions.md` (CS-1..CS-9 + 3
  amendment 2026-05-13)
- `.steering/20260508-m9-c-spike/blockers.md` (D-1..D-6)
- `.steering/20260508-m9-c-spike/k-alpha-report.md` (CS-1 amendment
  cascade)
- `.steering/20260430-m9-b-lora-execution-plan/design-final.md`
  (DB1-DB11 + 第3の道 ADR)
- `.steering/20260430-m9-eval-system/decisions.md` (ME-1..ME-15、
  特に ME-10/ME-11/ME-12/ME-13/ME-14)
- `docs/runbooks/m9-c-adapter-swap-runbook.md` (DB8)
- `personas/kant.yaml` / `personas/nietzsche.yaml` / `personas/rikyu.yaml`
- `src/erre_sandbox/inference/sglang_adapter.py` (Phase H spike で実装済、
  本 PR では touch しない)
- `src/erre_sandbox/inference/ollama_adapter.py` (現状 live path、
  本 PR では touch しない)
- `src/erre_sandbox/cognition/cycle.py:46-50` (`OllamaChatClient`
  injection point、Phase D で swap、本 PR では touch しない)

## 運用メモ

- **Plan mode**: 本 Phase A は Plan + /reimagine 必須 (CLAUDE.md 厳守)
- **Codex review**: 本セッション中に `codex exec --skip-git-repo-check`
  で実行 (.codex/budget.json 1M daily 内、想定 ~200k token)
- **Phase A スコープ単発 PR**: 設計のみ、code 変更ゼロ、`.steering/`
  + `docs/` のみ変更可
- **3 persona scope**: 1 PR で 3 persona 同時 adopt 判定 (user 判断、
  stage gate は採用しない、Reim-3 で議論したが棄却)
- **`/reimagine` 必須**: design v1 → v2 (brittle 前提 3 個破棄) →
  comparison → final の hybrid (CLAUDE.md 高難度設計判定)
