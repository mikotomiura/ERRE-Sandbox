# 設計 — m9-c-spike (bounded Kant LoRA spike on SGLang)

> 詳細は `m9-c-spike-design-final.md` (Codex Verdict ADOPT-WITH-CHANGES、
> HIGH 4 全反映) を参照。本書はその summary + 実装ロードマップ。

## 実装アプローチ

**v3 hybrid (Phase α + Phase β)**。Phase α (Mock-LoRA) で API/format/FSM の
infrastructure proof を **data-independent に early ship**、Phase β (Real
Kant training) で adapter quality / latency / N=3 throughput を **P3 完了 +
DB11 follow-up trigger 後** に実走。

- Base model: `qwen/Qwen3-8B`
- Quantization: QLoRA NF4 + double quant (CS-4)
- Library: PEFT (CS-5、暫定、M9-C-adopt で final 選定)
- Adapter rank: 8 (CS-5 continuity hypothesis、universal adequacy 主張せず)
- Serving: SGLang `0.5.10.post1` `--enable-lora` + `/load_lora_adapter`
  (CS-1)
- Mock-LoRA: PEFT default no-op (identity transform)、`tools/spike/` 隔離 +
  refusal guard + metadata sentinel (CS-9)

## 変更対象

### 新規作成するファイル

#### `src/erre_sandbox/inference/sglang_adapter.py` (Phase H)

`SGLangChatClient` (multi-LoRA aware chat client)、`LoRAAdapterRef` dataclass、
`SGLangUnavailableError`、`load_adapter()` / `unload_adapter()` / `loaded_adapters`
property (`list_adapters()` は CS-2 で削除)。

#### `src/erre_sandbox/training/__init__.py` (Phase I)

LoRA fine-tuning pipeline package、DB5/DB6/DB11 contract docstring。

#### `src/erre_sandbox/training/prompt_builder.py` (Phase I)

raw_dialog → `TrainingExample` 変換、`epoch_phase != EVALUATION` filter。

#### `src/erre_sandbox/training/dataset.py` (Phase I)

HF `datasets.Dataset` adapter、SFTTrainer 互換。

#### `src/erre_sandbox/training/train_kant_lora.py` (Phase I)

CLI、QLoRA NF4 + double quant + gradient_checkpointing (CS-4)、rank=8 (CS-5)、
PEFT save_pretrained (CS-6)、peak memory logging。

#### `tools/spike/build_mock_lora.py` (Phase J)

PEFT default no-op identity LoRA、refusal guard (`src/` / "checkpoint" /
"production" prefix reject)、metadata sentinel (`mock=true` 等)。

#### tests (Phase H/I/J)

- `tests/test_inference/test_sglang_adapter.py` (6 mock + 1 integration)
- `tests/test_training/test_prompt_builder.py` (4 件)
- `tests/test_training/test_dataset.py` (2 件)
- `tests/test_training/test_train_kant_lora.py` (4 件、`assert_phase_beta_ready`
  hard-fail 4 種)
- `tests/test_tools/test_build_mock_lora.py` (4 件)

#### docs (Phase L)

- `docs/runbooks/m9-c-adapter-swap-runbook.md` (DB8 完了)

### 修正するファイル

#### `pyproject.toml` (Phase G)

- `[inference]` extra に `sglang==0.5.10.post1` 追加 (CS-1)
- `[training]` extra 新設: `peft>=0.4,<1` / `transformers>=4.45,<5` /
  `datasets>=3,<4` / `accelerate>=0.30,<1` / `bitsandbytes>=0.45,<1`

#### `decisions.md` (本 PR、Phase E 完了済)

CS-1〜CS-9 ADR、各 5 要素。Phase K β 実測完了後に CS-1 / CS-4 / CS-7 /
CS-8 amendment で実測値反映。

### 削除するファイル

なし。

## 影響範囲

### 即時影響 (本 PR scope)

- `.steering/20260508-m9-c-spike/` 一式 (本 PR で 11 file scaffold)
- `.steering/20260430-m9-b-lora-execution-plan/tasklist.md` の "M9-C-spike
  scaffold" sub-item を [x] (本 PR、blockers.md follow-up: 別 PR で更新可)

### 将来影響 (次セッション以降)

- `pyproject.toml` の dep 追加 (`uv sync` 必要)
- `src/erre_sandbox/inference/` への新規 module (live inference path との
  統合は本 spike scope 外、M9-C-adopt 範囲)
- `src/erre_sandbox/training/` 新設 (off-line training pipeline、live path
  と完全分離)
- `tools/spike/` 新設 (production code 外、誤運用リスク削減で隔離)
- M9-C-adopt 着手時に本 spike の DB8 runbook + CS-N 実測値を base に
  production wiring

### 影響を受けない箇所

- `src/erre_sandbox/inference/ollama_adapter.py` (既存、互換性 100% 維持)
- M9-eval-system Tier A/B/C / DB9 quorum logic (本 spike は eval 系と直交)
- Godot client 経路 (本 spike は server-side 完結)

## 既存パターンとの整合性

### `OllamaChatClient` API signature 雛形 (CS-2)

`SGLangChatClient.chat(messages, *, sampling, model=None, adapter=None) ->
ChatResponse` は `OllamaChatClient.chat(messages, *, sampling, model=None) ->
ChatResponse` を踏襲。`adapter` 引数のみ追加。

### `OllamaUnavailableError` 単一エラー型統合 pattern (CS-2)

`SGLangUnavailableError` を同様に単一型 (`error-handling` Skill 整合)、httpx
4xx/5xx / connection error 全件 wrap。

### DB5 training-egress contract (CS-3)

`connect_training_view()` の `RawTrainingRelation.iter_rows()` を消費、
`epoch_phase != EVALUATION` filter は consumer 側で `prompt_builder` 内に
encapsulate。

### `empath_proxy.py` proxy framing docstring 雛形 (M9-B DB10 / Codex P4a LOW-3)

`tier_b/` で確立済の proxy framing rigor を training/ docstring にも適用
(DB10 honest framing 整合: spike は non-authoritative、effectiveness proof は
M9-eval 完成後)。

### 既存 spike 構造 (`.steering/20260420-m5-llm-spike/`)

requirement / design / tasklist / decisions / blockers の 5 file 構造を踏襲、
本 spike では design 系列 4 file (v1 / v2 / comparison / final) と
codex-review 2 file (prompt / response verbatim) を追加。

## テスト戦略

### 単体テスト (Phase H/I/J、合計 ~20 件)

- `test_sglang_adapter.py`: chat round trip / load idempotent / unload idempotent
  / loaded_adapters internal state / SGLangUnavailableError / close idempotent
- `test_prompt_builder.py`: epoch_phase=evaluation filter / sort 確認 /
  persona assistant target / empty input
- `test_dataset.py`: HF Dataset shape / seed stability
- `test_train_kant_lora.py`: `assert_phase_beta_ready` 4 種 hard-fail
  (evaluation row / individual_layer_enabled=true / individual_layer_enabled
  absent / examples < min_examples)
- `test_build_mock_lora.py`: refusal guard `src/` / refusal guard "checkpoint"
  / metadata sentinel `mock=true` / PEFT default identity transform

### 統合テスト (Phase H、任意 1 件)

- SGLang docker container 起動 → `/load_lora_adapter` actual POST →
  state reconciliation。CI で skip default、手動実走時 enable

### G-GEAR 実走 (Phase K α / K β)

- Phase K α: mock-LoRA infrastructure proof (data 不要)
  - SGLang `--enable-lora` 起動成功 (CS-1 launch args)
  - PEFT direct load (CS-6)
  - Kant prompt + mock = base model 出力 (CS-9 identity)
  - M5 resonance / ERRE FSM smoke (8 mode 経路)
  - **DB3 即時 fire 判断** (API failure / FSM regression のみ、CS-8)

- Phase K β: real Kant training + bench (P3 + DB11 trigger)
  - `assert_phase_beta_ready()` 通過 (CS-3)
  - QLoRA NF4 + rank=8 train run (~2-4h)
  - peak memory logging (CS-4 amendment 用)
  - SGLang real Kant adapter load
  - 5 condition adapter swap latency 実測 (cold / warm / pinned / unpinned /
    no-LoRA、CS-8)
  - SGLang `bench_serving` で N=3 throughput 実測 (CS-7、3 baseline)
  - **DB3 fallback fire 最終判断** (CS-8 real adapter confirmation)

### E2E テスト

本 spike 内で完結する E2E はなし (live inference path 統合は M9-C-adopt 範囲)。
DB8 adapter swap runbook 起草が "operational E2E doc" として最終
deliverable。

## ロールバック計画

### 本 PR (本セッション scope = scaffold + Plan + Codex review + ADR)

- 本 PR は **code 変更ゼロ、`.steering/` のみ追加**。merge 後の rollback 必要性
  低い (内容は議論材料 / planning artifact)
- 万一 design に重大欠陥が発覚 → revert + design-final.md amendment + 別 PR で
  re-merge

### 次セッション以降 (実装 phase)

- Phase G `[training]` extra: `uv sync` 失敗時は extra 削除のみで復元可
- Phase H `sglang_adapter.py`: 既存 `ollama_adapter.py` には touch しない、
  新設 module を削除すれば復元可 (live inference は ollama 経路で継続)
- Phase I `training/`: 新設 module、削除で復元可
- Phase J `tools/spike/`: production code 外、削除で復元可
- Phase K α / K β: G-GEAR side script 実行のみ、Mac 側 code 変更なし
  (実測値の `decisions.md` amendment は別 PR で revert 可)

### 重大障害シナリオ

- **SGLang LoRA 経路 fundamental 破綻**: CS-8 即時 fire → DB3 vLLM fallback
  別タスク `m9-c-spike-vllm-fallback` 起票、本 spike は **DB8 runbook 起草
  まで** 継続 (vLLM 移行 design は別タスク)
- **Phase β real training で OOM**: CS-4 amendment + batch / seq / gradient
  accumulation 再調整、最悪 7B base に switch
- **`m9-individual-layer-schema-add` 完了見込みなし**: B-1 hard blocker
  解消なしで Phase β 着手不可、`assert_phase_beta_ready()` で hard-fail
  維持 (silent skip 禁止、CS-3)

## 関連 design artifact (本 spike 内)

- `m9-c-spike-design-v1.md` (infrastructure-first 起点)
- `m9-c-spike-design-v2.md` (`/reimagine` 後、fail-fast + multi-persona 起点)
- `m9-c-spike-design-comparison.md` (v3 hybrid 候補、8 軸比較)
- `m9-c-spike-design-final.md` (Codex Verdict ADOPT-WITH-CHANGES、HIGH 4 全反映)
- `codex-review-prompt-m9-c-spike.md` (Codex review prompt、prior art 8 件 +
  4 質問群)
- `codex-review-m9-c-spike.md` (Codex review verbatim、198K tok)
- `decisions.md` CS-1〜CS-9
- `blockers.md` (B-1/B-2 hard / S-1〜S-3 soft / D-1〜D-6 defer / U-1〜U-4
  uncertainty)
