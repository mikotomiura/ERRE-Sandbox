# m9-c-spike — bounded Kant LoRA spike on SGLang

## 背景

M9-B execution prerequisite (M9-B `decisions.md` 第3の道 ADR、PR #127 merged
2026-04-30):

> bounded, non-authoritative single-persona Kant LoRA spike を SGLang 上で
> M9-eval-system と並行実施する。adoption 判断は評価系完成後の post-spike
> re-eval まで保留。

評価系構築中 (M9-eval-system 進行中、現在 P3 golden baseline calibration が
G-GEAR run1 overnight×2 で走行中) に **LoRA 学習・adapter swap・runtime
技術リスクを早期検出** することが目的。本 spike が成功 (technical PoC 成立)
することで、M9-C-adopt (LoRA 本採用) の前提条件が片づく。

直近 PR #148 (M9-eval P4a Tier B、2026-05-08) で DB9 quorum offensive gate
arbiter が完成、Tier B 3 sub-metric (Vendi / Big5 ICC / Burrows Δ) で LoRA
採用判定 quorum logic が機能する状態になった。だが M9-eval-system 完成
(Tier C P6 含む) はまだ先。本 spike は M9-eval-system と **時間的に並行**
実施可能 (non-authoritative 故に evaluation 系の完成を待たない)。

## ゴール

本タスクは **2 phase** に分かれる:

### 本 PR (本セッション) scope = Plan + scaffold + Codex review まで

1. `.steering/20260508-m9-c-spike/` の **scaffold 全 11 file** 配置完了
2. `m9-c-spike-design-v1.md` (infrastructure-first 案) → `/reimagine` で
   v2 (代替戦略) → `m9-c-spike-design-comparison.md` で hybrid v3 確定
3. Codex `gpt-5.5 xhigh` independent review 実行、`codex-review-m9-c-spike.md`
   verbatim 保存、HIGH 全反映を `m9-c-spike-design-final.md` に明示
4. `decisions.md` に新規 ADR (CS-1〜CS-N) 起票、各 5 要素
5. `tasklist.md` に Phase G-J (実装 phase) sub-items 列挙
6. `blockers.md` に P3 golden baseline 完了 dependency + SGLang version pin +
   VRAM 予算実測 defer 事項記録

### 次セッション以降 scope = 実装 + tests + G-GEAR 実走

- `pyproject.toml` に `[training]` extra 追加 (peft / transformers / datasets /
  accelerate / bitsandbytes)
- `src/erre_sandbox/inference/sglang_adapter.py` 新設 (LoRA load/unload
  method 含む)
- `src/erre_sandbox/training/` module 新設 (prompt_builder / dataset /
  train_kant_lora)
- mock test + integration test (ruff / mypy / pytest 全 PASS、CI 4/4 green)
- G-GEAR 実走 (P3 golden baseline 採取完了後): training run + adapter load +
  **adapter swap latency / N=3 throughput / FSM regression** 実測
- DB8 adapter swap runbook 起草 (実測値込み)

## スコープ

### 含むもの

- **Kant 1 persona** spike (LoRA fine-tune + SGLang serving + adapter swap)
- 既存 dialog_turn (`epoch_phase != EVALUATION` の `AUTONOMOUS` /
  `Q_AND_A` 行) を training data
- **SGLang `--enable-lora` + `/load_lora_adapter` REST endpoint** 動作確認
- adapter swap latency / throughput / FSM regression の **実測** (G-GEAR)
- DB3 vLLM fallback 判定材料の生成 (>500ms latency / N=3 collapse / FSM
  regression が trigger)
- Technical PoC + Quality signal **両方** (Codex 確認済 user 確定)

### 含まないもの

- **LoRA 採用判定** (M9-C-adopt 範囲、DB9 quorum 通過必須)
- **3 persona 展開** (Nietzsche / Rikyū)、本 spike は Kant 1 のみ
- **Tier C judge LLM** (M9-eval P6 範囲)
- **M9-eval P3 golden baseline 採取自体** (G-GEAR run1 calibration → run2-4
  での実走、別タスク)
- **Burrows reference corpus 整備** (Tier A 既存範囲、blockers.md defer)
- **persona refactor / philosopher_seed** (M10-A 範囲、認知深化 PR #144)
- **DB11 contamination assert 実装** (`m9-individual-layer-schema-add` 別タスク)
- **vLLM full migration 実装** (DB3 fallback fire 時のみ別タスク化)
- **PEFT vs unsloth final 選定** (M9-C-adopt 範囲、本 spike では PEFT 暫定)

## 受け入れ条件

### 本 PR (本セッション) 受け入れ条件

- [ ] `.steering/20260508-m9-c-spike/` 11 file scaffold 完了
- [ ] `m9-c-spike-design-v1.md` / `-design-v2.md` / `-design-comparison.md` /
      `-design-final.md` 全 verbatim 保存
- [ ] `codex-review-prompt-m9-c-spike.md` 起票、`codex-review-m9-c-spike.md`
      verbatim 保存 (要約禁止)
- [ ] Codex Verdict (期待: ADOPT-WITH-CHANGES)、HIGH 全反映マッピング表を
      `m9-c-spike-design-final.md` に明示
- [ ] `decisions.md` に CS-1〜CS-N ADR、各 5 要素 (決定 / 根拠 / 棄却 /
      影響 / re-open 条件)
- [ ] `tasklist.md` に Phase G-J 実装 sub-items 列挙、本 PR sub-items は [x]
- [ ] `blockers.md` に dependency + defer 記録 (P3 golden baseline / SGLang
      version pin / VRAM 実測)
- [ ] PR description に `codex-review-m9-c-spike.md` link + design-final.md
      link

### 次セッション以降 (実装 phase) 受け入れ条件

- ruff / ruff format / mypy / pytest 全 PASS、CI 4/4 green
- 既存 1356+ tests no regression
- SGLang adapter mock test (load_adapter / unload_adapter / chat with adapter)
- training data extraction test (raw_dialog → prompt/completion 形式、
  `epoch_phase != EVALUATION` filter)
- adapter format conversion test (PEFT safetensors → SGLang weight)
- G-GEAR 実走 (P3 完了後): adapter swap latency <500ms 確認 (>500ms は
  DB3 fallback fire)、N=3 throughput collapse なし、FSM regression なし
- `decisions.md` CS-N に **実測値** を反映 (latency / cold start / throughput)
- DB8 adapter swap runbook を `docs/` に commit (M9-B `tasklist.md` の
  該当 sub-item を [x])

## 関連ドキュメント

- `.steering/20260430-m9-b-lora-execution-plan/decisions.md` DB1-DB11 +
  第3の道 ADR
- `.steering/20260430-m9-b-lora-execution-plan/design-final.md`
- `.steering/20260420-m5-llm-spike/` (spike 系 .steering 構造の前例)
- `.steering/20260430-m9-eval-system/codex-review-p4a.md` (Codex review
  prompt 構造の前例)
- `docs/architecture.md` §2 (G-GEAR VRAM、qwen3:8b)
- `src/erre_sandbox/inference/ollama_adapter.py` (`OllamaChatClient` API
  雛形)
- `src/erre_sandbox/evidence/eval_store.py::connect_training_view` (DB5 entry)
- `src/erre_sandbox/schemas.py::EpochPhase` (L254)

## 運用メモ

- **破壊と構築 (`/reimagine`) 適用**: **Yes** (user 確定)
- **理由**: アーキテクチャ判断 (SGLang vs vLLM、PEFT vs unsloth、training
  data 戦略) と複数案ありうる設計、CLAUDE.md 規約で 3 関門必須
- **Codex 必須**: 同上、CLAUDE.md `gpt-5.5 xhigh` independent review 必須
- **本セッション scope**: Plan + scaffold + Codex review **まで** (実装は
  次セッション)
- **data dependency**: M9-eval P3 golden baseline 採取完了 (G-GEAR run1
  overnight×2 + run2-4) が前提、本 PR では code path のみ起草
- **Mac 単独作業**: G-GEAR run1 calibration への影響なし
  (`data/eval/calibration/` には touch しない、code path も独立)
