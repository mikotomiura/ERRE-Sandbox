# タスクリスト — m9-c-spike (bounded Kant LoRA spike on SGLang)

## 本セッション (Plan + scaffold + Codex review)

### Phase A — scaffold + requirement.md

- [x] `mkdir -p .steering/20260508-m9-c-spike/`
- [x] `cp .steering/_template/{requirement,design,tasklist,decisions,blockers}.md
  .steering/20260508-m9-c-spike/`
- [x] `requirement.md` 5 項目 (背景 / ゴール / scope / scope外 / 受入条件) +
  運用メモ (`/reimagine`: Yes)

### Phase B — design-v1.md (infrastructure-first)

- [x] `m9-c-spike-design-v1.md` 起草
- [x] SGLang adapter API skeleton (`SGLangChatClient` + LoRA load/unload)
- [x] training/ module skeleton (`prompt_builder.py` / `dataset.py` /
  `train_kant_lora.py`)
- [x] VRAM 予算試算 (RTX 5060 Ti 16GB)
- [x] Test plan

### Phase C — `/reimagine` v2 + comparison

- [x] `m9-c-spike-design-v2.md` (fail-fast + multi-persona 起点)
- [x] `m9-c-spike-design-comparison.md` (8 軸比較 + hybrid v3 候補)

### Phase D — Codex independent review

- [x] `codex-review-prompt-m9-c-spike.md` 起票 (prior art 8 件 + 質問群 4 群)
- [x] `cat ... | codex exec --skip-git-repo-check` 実行 (198K tok)
- [x] `codex-review-m9-c-spike.md` verbatim 保存 (要約禁止)
- [x] Verdict 取得 (ADOPT-WITH-CHANGES、HIGH 4 / MEDIUM 6 / LOW 3)

### Phase E — design-final + decisions.md ADR

- [x] `m9-c-spike-design-final.md` 起草、HIGH 4 全反映マッピング表
- [x] `decisions.md` に CS-1〜CS-9 ADR 起票、各 5 要素

### Phase F — tasklist + blockers + design.md populate (本書 + Codex MEDIUM-6)

- [x] `tasklist.md` (本書) populate (Phase A-L 全 sub-items)
- [x] `blockers.md` populate (hard blocker / soft blocker / defer)
- [x] `design.md` populate (Codex MEDIUM-6 反映、design-final.md summary 貼付済)

## 次セッション以降 (実装 + tests + G-GEAR 実走)

### Phase G — pyproject.toml `[training]` extras

- [ ] `[training]` extra 新設、SGLang は既存 `[inference]` に依存追加:
  - `sglang==0.5.10.post1` (CS-1、`[inference]`)
  - `peft>=0.4,<1` (`[training]`)
  - `transformers>=4.45,<5` (`[training]`、既存条件と整合)
  - `datasets>=3,<4` (`[training]`)
  - `accelerate>=0.30,<1` (`[training]`)
  - `bitsandbytes>=0.45,<1` (`[training]`)
- [ ] `mypy.ini` の external module ignore に必要に応じて追加
- [ ] `uv sync --extra training` 動作確認 (Mac CPU で peft import が通るか)

### Phase H — `sglang_adapter.py` 新設 + tests

- [ ] `src/erre_sandbox/inference/sglang_adapter.py` 新設
  - `SGLangChatClient` class (`OllamaChatClient` API signature 雛形踏襲)
  - `LoRAAdapterRef` dataclass (CS-2 / CS-9 整合、SGLang naming)
  - `SGLangUnavailableError` (`OllamaUnavailableError` と symmetric)
  - `load_adapter()` / `unload_adapter()` (CS-2: internal client-state)
  - `loaded_adapters` property (`list_adapters()` は CS-2 で削除)
  - lazy `httpx.AsyncClient` (close idempotent)
- [ ] `tests/test_inference/test_sglang_adapter.py` 新設 (6 mock + 1 integration):
  - chat round trip (httpx mock)
  - load_adapter idempotent + state reconciliation
  - unload_adapter idempotent
  - loaded_adapters property は internal state 由来
  - SGLangUnavailableError on 4xx/5xx
  - close idempotent
  - integration: SGLang docker container で actual /load_lora_adapter (任意)

### Phase I — `training/` module + Phase β gate + tests ✅ 完了

- [x] `src/erre_sandbox/training/__init__.py` 新設 (LoRA fine-tuning pipeline、
  DB5/DB6/DB11 contract docstring)
- [x] `src/erre_sandbox/training/prompt_builder.py` 新設
- [x] `src/erre_sandbox/training/dataset.py` 新設 (HF datasets adapter)
- [x] `src/erre_sandbox/training/train_kant_lora.py` 新設 (CLI):
  - [x] `assert_phase_beta_ready()` hard-fail gate (CS-3、4 種類) — 既存
  - [x] inner loop (2026-05-13 本 PR): QLoRA NF4 + double quant +
    gradient_checkpointing (CS-4) / rank=8 LoRA (CS-5) / PEFT
    `save_pretrained()` 出力 (CS-6 整合) / peak memory logging
  - [x] argparse `__main__` CLI (2026-05-13 本 PR): `--duckdb-glob /
    --db-path / --output-dir / --rank / --quantization / --batch-size /
    --gradient-accumulation / --max-seq-length / --max-steps /
    --learning-rate / --save-steps / --min-examples / --seed / --dry-run`
  - [x] exit code mapping (CS-3): 0=success / 2=contamination /
    3=blocker / 4=insufficient / 5=operator error
  - [x] shard 集約 (multi-DuckDB → 単一 aggregate gate path)
  - [x] `TrainRunSummary` dataclass + `train_metadata.json` audit trail
- [x] `tests/test_training/test_prompt_builder.py` (4 件、既存)
- [x] `tests/test_training/test_dataset.py` (2 件、既存)
- [x] `tests/test_training/test_train_kant_lora.py` (10 件、既存)
- [x] `tests/test_training/test_train_kant_lora_cli.py` (13 件、2026-05-13 本 PR):
  - lazy-import 規律 (GPU stack 未 import)
  - argparse surface (help / missing / mutual exclusive / glob no-match)
  - dry-run rc (success / contamination / insufficient / quantization)
  - shard aggregation (multi-shard PASS / contaminated shard fail-fast / empty paths)
  - subprocess `python -m` smoke
- [x] real-data dry-run smoke (kant 10 cells / 11,761 rows / 5,022 examples /
  CS-3 threshold 5.02x margin、log `.steering/20260508-m9-c-spike/
  k-beta-dry-run.log`)

### Phase J — `tools/spike/build_mock_lora.py` + tests

- [ ] `tools/spike/build_mock_lora.py` 新設 (CS-9):
  - PEFT default `init_lora_weights="default"` (no-op identity)
  - metadata sentinel embed (`mock=true`, base_model, rank, target_modules,
    init_lora_weights, git_sha)
  - refusal guard (`src/` prefix / "checkpoint" / "production" 含むパス reject)
- [ ] `tests/test_tools/test_build_mock_lora.py` (4 件):
  - refusal guard `src/` prefix → ValueError
  - refusal guard "checkpoint" 含む → ValueError
  - metadata sentinel `mock=true` 確認
  - PEFT default init で B=0 の identity transform assertion

### Phase K α — G-GEAR mock-LoRA infrastructure proof (data 不要、即実行)

**Status (2026-05-09)**: Step 1 ✅ / Steps 2-5 ⏸️ DEFERRED (DB3 fire #1
fired on **install-side platform compat**, not CUDA runtime). See
`.steering/20260508-m9-c-spike/k-alpha-report.md` for full diagnostic.
Recommendations require Mac-side ADR re-open (CS-1 amendment).

- [x] mock-LoRA build (`uv run python -m tools.spike.build_mock_lora
  --output-dir checkpoints/mock_kant_r8`) — 2026-05-09 (after fixing
  `init_lora_weights="default"` → `True` kwarg bug, see report Step 1)
- [ ] G-GEAR で `sglang==0.5.10.post1` install (CUDA 12.x) — **BLOCKED**:
  `sglang-kernel==0.4.1` ships only manylinux wheels; no native Windows
  wheel exists. WSL2 / Docker not installed on G-GEAR. Pending CS-1
  amendment (Linux execution boundary).
- [ ] CS-1 launch args で SGLang 起動確認 — **BLOCKED on previous item**.
- [ ] `/load_lora_adapter` で mock を load (PEFT direct load test、CS-6) —
  **DEFERRED** (artefact ready, awaiting live SGLang server).
- [ ] mock load 経由で chat round trip (Kant prompt + mock = base model 出力、
  CS-9 identity transform 確認) — **DEFERRED**.
- [ ] M5 resonance / ERRE FSM smoke test (SGLang LoRA 経路で 8 mode の
  AnimationTree state を循環確認) — **DEFERRED**.
- [x] **DB3 fallback 判断 (CS-8 即時 fire)**:
  - SGLang 起動失敗 → **FIRED #1** (install-side platform incompat, NOT CUDA
    runtime). Recommendation: amend CS-1 boundary, do NOT yet fire vLLM
    fallback (vLLM has the same Linux constraint).
  - PEFT format 拒否 → not exercised (Step 3 deferred)
  - FSM regression → not exercised (Step 5 deferred)
  - latency / N=3 collapse は **diagnostic** (Phase K β real adapter で
    confirmation 後に判断)

### Phase K β — G-GEAR real Kant training (P3 + DB11 follow-up trigger) ✅ 完了 (2026-05-13)

**Trigger 解消**: B-1/B-2/B-3 すべて解消、PR #162 で実装が main に landed。

- [x] `assert_phase_beta_ready()` gate 通過確認 (CS-3、4 種 hard-fail clear、PR #162 dry-run + 本 PR 実 train で 2 重確認)
- [x] Kant rank=8 PEFT QLoRA NF4 train run (実時間 **2.07h**、CS-4 config、peak VRAM **9.83 GB**、train_loss 3.488→0.128)
- [x] checkpoint export (`adapter_config.json` 1042B + `adapter_model.safetensors` 30.7MB + `train_metadata.json` audit trail)
- [x] SGLang `/load_lora_adapter` で real Kant adapter load (CS-6 PEFT direct load 成功、HTTP 200、`success: true`)
- [x] adapter swap latency 5 condition 実測 (CS-8):
  - cold_load median **8.2 ms**、warm_reload median **7.7 ms** (500ms threshold の 60x margin)
  - pinned/unpinned/no_lora の chat latency は全 condition ~7100-7200ms で同等、adapter routing オーバーヘッド観測されず
- [x] SGLang `bench_serving` 実測 (CS-7、2 baseline、num-prompts=16):
  - no_lora: output 35.54 tok/s、mean E2E 27,501ms、P99 E2E 46,897ms
  - single_lora (Kant): output 34.64 tok/s、mean E2E 28,225ms、P99 E2E 48,110ms
  - multi_lora_3: M9-C-adopt scope へ defer (single adapter routing 2.5% で contention リスク低)
- [x] CS-7 4 trigger 全 NON-FIRE: p95 e2e ratio 1.026 / output 0.975 / timeout 0 件 / misrouting N/A
- [x] **DB3 fallback fire 最終判断** (CS-8): **NOT FIRED**、SGLang-first 確定、vLLM defer 継続 (D-1)
- [x] `data/eval/spike/m9-c-spike-bench/` に JSONL 結果保存:
  - `k-beta-swap-latency.jsonl` (5 condition × 3 trial)
  - `single_lora.jsonl` / `no_lora.jsonl` (bench_serving)

### Phase L — adapter swap runbook (DB8) + PR ✅ 完了 (2026-05-13)

- [x] `docs/runbooks/m9-c-adapter-swap-runbook.md` 起票完了 (DB8 deliverable):
  - SGLang launch SOP (CS-1 launch args、`scripts/m9-c-spike/launch_sglang.sh`)
  - PEFT directory 構造と `/load_lora_adapter` payload 例 (CS-6)
  - 5 condition latency 実測値 (CS-8 amendment 2026-05-13)
  - bench_serving 実測値 (CS-7 amendment 2026-05-13)
  - DB3 fallback fire 判断履歴 (2026-05-09 K-α #1 + 2026-05-13 K-β confirmation)
- [x] `decisions.md` CS-7 + CS-8 amendment 2026-05-13 起票 (CS-3 amendment 2026-05-13 は PR #162 で起票済)
- [ ] M9-B `tasklist.md` の "M9-C-spike 完了後 runbook" sub-item を [x] (M9-B 側 PR で対応)
- [ ] commit + push + `gh pr create` (本 PR、S-9 で実施)
- [ ] 1356+ 全 tests no regression、CI 4/4 green (本 PR は実装変更なし、tests/test_training/ 29/29 PASS は PR #162 から継続)

## ドキュメント

- [ ] `docs/architecture.md` §2 (G-GEAR VRAM、qwen3:8b、SGLang) に CS-1
  version pin + LoRA 経路を追記 (Phase L 内)
- [ ] `docs/glossary.md` に "QLoRA NF4 / double quant / gradient_checkpointing /
  PEFT / SGLang / `/load_lora_adapter` / pinned adapter / overlap loading"
  等 LoRA 用語を追加 (Phase L 内、optional)

## 完了処理

- [x] design-final.md 確定 (本セッション Phase E)
- [x] decisions.md CS-1〜CS-9 起票 (本セッション Phase E)
- [x] design.md populate (Codex MEDIUM-6、Phase F、本セッション)
- [ ] PR description (Phase L、次セッション以降):
  - `codex-review-m9-c-spike.md` link
  - HIGH 4 反映マッピング表
  - 5 deliverable 状態 (Phase K α / K β 完了)
  - DB3 fallback fire/non-fire 結論
  - DB8 adapter swap runbook link
