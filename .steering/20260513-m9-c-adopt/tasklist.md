# タスクリスト — m9-c-adopt (3 persona LoRA adopt judgment on SGLang live path)

> Codex HIGH 4 / MEDIUM 6 / LOW 3 反映後の hybrid v3。Phase A は **本セッション**、
> Phase B-G は次セッション以降の実装/訓練/実走。Phase H-Z は M9-D / M10 への
> placeholder。

---

## 本セッション (Phase A: 設計のみ、code 変更ゼロ)

### Phase A — scaffold + requirement + design + Codex review + ADR + PR

- [x] `mkdir .steering/20260513-m9-c-adopt/`
- [x] `cp .steering/_template/{requirement,design,tasklist,decisions,blockers}.md .steering/20260513-m9-c-adopt/`
- [x] `requirement.md` 5 section (背景 / ゴール / scope-in / scope-out / 受入条件 AC-1..AC-6) + 運用メモ
- [x] `design.md` v1 起草 (3 persona simultaneous 1 PR + SGLang-only + 4 rank sweep)
- [x] `design-v2-reimagine.md` (`/reimagine` で brittle 前提 3 個破棄: vLLM first-class / rank sweep 縮減 / stage gate)
- [x] `design-comparison.md` 8 軸比較 + hybrid v3 候補 (SGLang-only + rank {4,8,16} + provisional Tier B pin)
- [x] `codex-review-prompt.md` 起票 (prior art 6 件 + COQ 4 件 + 報告 format)
- [x] `cat codex-review-prompt.md | codex exec --skip-git-repo-check` 実行
- [x] `codex-review.md` verbatim 保存
- [x] Codex Verdict 取得 (**ADOPT-WITH-CHANGES**、HIGH 4 / MEDIUM 6 / LOW 3)
- [x] `requirement.md` AC-1 修正 (rank `{4,8,16}` + conditional rank=32 tail-sweep + `--max-lora-rank >= 16`、MEDIUM-3 反映)
- [x] `design-final.md` 起草 (HIGH 4 全反映マッピング表 + MEDIUM 6 trace + LOW 3 trace)
- [x] `decisions.md` に DA-1..DA-10 ADR 起票、各 5 要素 (決定 / 根拠 / 棄却 / 影響 / re-open 条件)
- [x] `blockers.md` populate (hard H-1/H-2、soft S-1/S-2/S-3、defer D-1..D-5、uncertainty U-1..U-5)
- [x] `tasklist.md` (本書) populate (Phase A-G + H-Z placeholder)
- [ ] PowerShell `Get-ChildItem .steering/20260513-m9-c-adopt/` で 10 file (5 template-derived + 5 Phase A 専用) 存在確認
- [ ] `git add .steering/20260513-m9-c-adopt/` + commit (feat(adopt): m9-c-adopt — Phase A design scaffold (DA-1..DA-10 ADR))
- [ ] `git push -u origin feature/m9-c-adopt-design`
- [ ] `gh pr create` で PR 起票 (PR description: code 変更ゼロ明示 + Codex Verdict + HIGH 反映マッピング表 + COQ 4 件 verdict)
- [ ] Mac master review 待ち (auto-merge しない)
- [ ] Phase B 着手前の next-session-prompt-phase-b.md 起草 (本 PR には含めず、別 PR)

---

## 次セッション以降 (実装 + 訓練 + 実走)

### Phase B — A-1 rank sweep (kant のみ、`{4, 8, 16}` + conditional rank=32)

- [x] **前提 verification** (2026-05-13 Phase B Step 0):
  - [x] H-1 (kant baseline shard 揃い) — `data/eval/golden/kant_{natural,stimulus}_run{0..4}.duckdb` 10 shard 確認、Tier B baseline ICC 算出は Step 5 で実施
  - [x] S-2 (CS-1 `--max-lora-rank >= 16` amendment) 実施 — DB8 runbook §2 update + `decisions.md` DA-1 amendment 2026-05-13 追記、M9-C-spike `decisions.md` CS-1 は immutable 保持
  - [x] CS-3 4-種 hard-fail gate dry-run PASS (kant 5022 examples、10 shard、PR #163 parity)
  - [x] `scripts/build_adapter_manifest.py` 起草 (DA-10 schema、CS-9/DA-6 hard block #2 (.bin pickle refuse) 込み)
- [x] kant rank=8 baseline 再 confirm (`kant_r8_real` 既存、Phase B 第 2 セッション)
- [x] kant rank=4 train (G-GEAR overnight、Phase B 第 1 セッション、sha256 `b89a248695...`)
- [x] kant rank=16 train (overnight、第 2 セッション、sha256 `9532b438f3...`)
- [x] 各 adapter で SGLang `/load_lora_adapter` HTTP 200 確認 + chat round trip success (第 2 セッション Step 4)
- [x] VRAM peak per-step `nvidia-smi --query-gpu=memory.used` sampling、peak > 14GB で early abort (S-3 mitigation; 実測 14016 MiB sustained で threshold 14300 MiB に amendment)
- [x] adapter manifest.json + sha256 生成 (DA-10、3 archive `rank_{4,8,16}/kant/manifest.json` 揃い)
- **DA-11 narrowing 適用 (Phase B 第 3 セッション 2026-05-14)**:
  - [x] **Step 5a (narrowed)**: Vendi lexical-5gram baseline 算出 (point=75.77 / CI=[75.19, 76.37])、semantic Vendi は Mac post-hoc へ defer
  - [x] **Step 5b**: SGLang re-launch + 3 adapter pinned (`/v1/models` 経由 adapter check)
  - [x] **Step 5c**: SGLang LoRA Tier B pilot driver 新規実装 + 1800 turn 採取 (3 rank × 2 run × 300 turn、6 shard、~21 min)
  - [x] **Step 5e (partial)**: CS-7 per-rank single_lora bench (rank=4/8/16)、no_lora は PR #163 K-β 値継続使用
- **Phase B 第 4 セッション完遂 (2026-05-14、DA-12 verdict = DEFER)**:
  - [x] **Step 5d (Big5 ICC)**: `scripts/m9-c-adopt/compute_big5_icc.py` 新規実装 + Ollama (Windows native) responder + SGLang (WSL2) responder switch。Ollama no-LoRA baseline ICC(C,k)=0.998 [0.997, 0.999]、per-rank LoRA-on ICC(C,k) 0.979〜0.984 (全 rank PASS DA-1 axis 2)。T=0 trivial 1.0 artifact 回避のため T=0.7 + per-call seed mutation を導入 (`decisions.md` DA-12 hot decision)
  - [x] **Burrows Δ Option A**: `scripts/m9-c-adopt/compute_burrows_delta.py` 新規実装、langdetect deterministic (seed=0) + confidence 0.85 + de utterances only filter。baseline point=108.534 [108.10, 109.02]、per-rank LoRA-on 112.56〜113.72 (全 rank direction failure on DA-1 axis 3)
  - [x] **Vendi semantic 再算出**: `compute_baseline_vendi.py --kernel semantic` (MPNet)。baseline point=30.822 [30.726, 30.928]、per-rank LoRA-on 33.69〜34.70 (全 rank direction failure on DA-1 axis 1、Cohen's d +2.13〜+3.00)
  - [x] **Step 5f (DA-1 4 軸 intersection)**: `scripts/m9-c-adopt/da1_matrix.py` 新規実装で matrix 集約。**全 rank 2/4 軸 PASS (ICC + throughput)、direction failure on Vendi + Burrows**
  - [x] **DA-12 ADR 起票**: pilot verdict = DEFER、production placement なし、provisional rank=8 carry-over、tail-sweep rank=32 NOT fire、DA-9 retrain v2 path 開放
- [x] **Step 6 conditional rank=32 tail-sweep 判定**: **NOT fire** — direction failure は rank scaling では解消不能 (pilot single-turn methodology confound + LoRA が IPIP self-report neutral midpoint を shift しない 2 因子の identifiability 不能)、DA-9 retrain v2 path で対応
- [x] **AC-1 PASS** (Phase B 完遂: rank training + archive + manifest 揃い + VRAM headroom 健全 + pilot infra + 全 metric 算出 + DA-12 verdict 記録)。production rank 採用は Phase E A-6 multi-turn full Tier B へ持ち越し

### Phase C — A-2 3 persona expansion (adopted rank で nietzsche / rikyu 訓練)

- [ ] `training/train_kant_lora.py` を generic 化 (`train_persona_lora.py`、`--persona kant|nietzsche|rikyu`)
- [ ] nietzsche training data 抽出: `_collect_from_shards()` で `epoch_phase != EVALUATION` + `individual_layer_enabled=false`
- [ ] nietzsche `assert_phase_beta_ready(min_examples=1000)` PASS 確認 (training kick 許可のみ、MEDIUM-6)
- [ ] nietzsche train (G-GEAR overnight) → `data/lora/m9-c-adopt/nietzsche_r{X}_real/`
- [ ] nietzsche manifest.json + sha256 (DA-10)
- [ ] rikyu training data 抽出 + min_examples PASS 確認
- [ ] rikyu train (G-GEAR overnight) → `data/lora/m9-c-adopt/rikyu_r{X}_real/`
- [ ] rikyu manifest.json + sha256
- [ ] 3 adapter SGLang multi-adapter pin で同時 load 成功 (`--max-loaded-loras 3 --max-loras-per-batch 3`)
- [ ] **AC-2 PASS** (3 persona adapter 揃い + multi-pin load 成功)

### Phase D — A-3 live path 統合 + A-4a mock multi_lora_3 bench

- [ ] `src/erre_sandbox/inference/server.py` (新規) `MultiBackendChatClient` 実装
  - [ ] 2 backend (Ollama / SGLang)
  - [ ] `ERRE_INFERENCE_BACKEND ∈ {ollama, sglang}` feature flag (default `ollama`)
  - [ ] fallback: SGLang unreachable → Ollama degraded mode (`degraded_to_ollama=True`)
  - [ ] DA-4 bootstrap 失敗時挙動: 両方 fail → rc=1、片方 fail → warn + 続行
- [ ] `cognition/cycle.py:46-50` の import 拡張 (Union 型 `OllamaChatClient | SGLangChatClient | MultiBackendChatClient`)
- [ ] persona → adapter mapping (DA-3): `f"{persona_id}_r{rank}_real"` 規約
- [ ] **compose_sampling() regression assertion** (MEDIUM-5): `tests/test_inference/test_compose_sampling_regression.py` 新規、SGLang options で temperature/top_p/repeat_penalty override 禁止 test
- [ ] mock_nietzsche_r8 + mock_rikyu_r8 を `tools/spike/build_mock_lora.py` で生成 (`init_lora_weights=True`、identity transform)
- [ ] A-4a mock-first bench (CS-7 4 trigger 既存):
  - [ ] no_lora / single_lora-mock / multi_lora_3-mock の 3 condition
  - [ ] `data/eval/spike/m9-c-adopt-bench/multi_lora_3-mock.jsonl`
  - [ ] CS-7 4 trigger 全 NON-FIRE
- [ ] `tests/test_inference/test_multi_backend.py` 新規 (feature flag / fallback / DA-4)
- [ ] ruff / mypy / pytest 全 PASS、CI 4/4 green
- [ ] **AC-3 PASS** (feature flag 切替 + Ollama fallback 動作)
- [ ] **AC-4 PASS (mock)** (multi_lora_3 mock で CS-7 4 trigger NON-FIRE)

### Phase E — A-4b real stress bench + A-5 FSM smoke + A-6 Tier B validation

- [ ] **A-4b real-after stress bench** (HIGH-3 churn diagnostic):
  - [ ] `scripts/bench_multi_lora_stress.py` (新規候補) で 1h+ 持続 stress mode
  - [ ] no_lora / single_lora-real / multi_lora_3-real の 3 condition
  - [ ] steady-state metric: TTFT / ITL / e2e p99 / output tok/s / error rate (CS-7 既存)
  - [ ] churn diagnostic: queue wait p99 + adapter-misrouting count + timeout count + **memory growth** (per-minute `nvidia-smi` sampling)
  - [ ] CS-7 4 既存 + 2 新規 trigger (queue wait p99 > 30s / memory growth > 500MB/1h) 全 NON-FIRE
  - [ ] `data/eval/spike/m9-c-adopt-bench/multi_lora_3-real-stress.jsonl` + `memory_growth.jsonl`
- [ ] **A-5 FSM smoke 24 cell** (8 mode × 3 persona × 1 turn):
  - [ ] `tests/test_cognition/test_fsm_smoke_lora.py` 新規
  - [ ] 各 cell で `CognitionCycle.step()` 1 turn、`AgentState.erre.name == expected` のみ pass (DA-7、reason field 除外)
  - [ ] Ollama baseline (no LoRA) で同一 input → 同一 final mode regression assertion
  - [ ] `data/eval/spike/m9-c-adopt-fsm-smoke/{persona}_{mode}.json`
  - [ ] 24/24 PASS
- [ ] **A-6 Tier B empirical validation** (HIGH-2 反映):
  - [ ] stimulus 500 turn × 5 run × 3 persona = 7500 turn 採取 (~29h G-GEAR overnight × 3)
  - [ ] checkpoint resume protocol (per 500 turn save、resume CLI option)
  - [ ] `data/eval/m9-c-adopt-tier-b/{persona}_run{0..4}_stim.duckdb`
  - [ ] `tier_b_bootstrap_pair.py` 経由で Vendi + ICC(C,k) + ICC(A,1) (diagnostic、MEDIUM-4) + Burrows Δ + IPIP-NEO-120 (diagnostic) 算出
  - [ ] 各 metric: point + bootstrap 95% CI lower bound + direction の 3 値 expose
  - [ ] rikyu Burrows N/A 確認 (H-2 limitation 扱い、DA-8 2-of-2 fallback)
- [ ] **AC-4 PASS (real)** (multi_lora_3 real で CS-7 拡張 NON-FIRE)
- [ ] **AC-5 PASS** (FSM smoke 24/24)

### Phase F — A-7 production safety + A-8 採用判定 verdict

- [ ] `inference/server.py` `_validate_adapter_manifest()` 実装 (DA-6、HIGH-4 反映)
  - [ ] hard block 7 条件 (path traversal / symlink / .bin pickle / base model / rank / target modules / sha256 mismatch / is_mock)
  - [ ] `AdapterIntegrityError` / `ProductionLoaderRejectError` 例外定義
- [ ] `tests/test_inference/test_production_loader.py` 新規、7 件 reject case 全 cover
- [ ] **audit log** (DA-6 + LOW-1):
  - [ ] `logs/inference/adapter_load_audit.jsonl` redaction (prompt 内容 / persona prompt 内容 redact)
  - [ ] rotation: daily 50MB、retention: 30 day
  - [ ] `docs/runbooks/m9-c-adopt-audit-log.md` (新規候補)
- [ ] **checksum latency measurement** (LOW-2): sha256 cold load latency 実測、CS-8 trace 継続。50ms threshold 圧迫なら CS-8 amendment
- [ ] **A-8 verdict report** 起草 (`docs/runbooks/m9-c-adopt-verdict.md` 候補 or `.steering/20260513-m9-c-adopt/verdict-report.md`):
  - [ ] Tier B quorum 評価 (DA-8 3 条件 AND)
    - [ ] kant: 2-of-3 (Vendi + ICC + Burrows)
    - [ ] nietzsche: 2-of-3
    - [ ] rikyu: 2-of-2 (Vendi + ICC、Burrows N/A limitation 扱い)
  - [ ] bench quorum 評価 (CS-7 拡張 6 trigger 全 NON-FIRE on multi_lora_3 vs single vs no_lora)
  - [ ] latency ceiling 評価 (adapter swap p99 < 50ms / chat round-trip p99 < 15s)
  - [ ] FSM smoke 24/24 PASS 確認
  - [ ] **verdict 確定**: ADOPT / ADOPT-WITH-CHANGES (DA-9 marginal pass retrain path) / REJECT
  - [ ] DB3 re-arm trigger 監視 status report
- [ ] **AC-6 PASS** (Tier B quorum 通過 + A-8 verdict 確定)

### Phase G — live cutover + 1 week soak

- [ ] `ERRE_INFERENCE_BACKEND` default を `sglang` に flip (verdict = ADOPT 時)
- [ ] 1 week soak (G-GEAR 常時稼働 production-like)
- [ ] monitor:
  - [ ] error rate < 0.1%
  - [ ] Ollama fallback rate < 1%
  - [ ] memory growth < 500MB/1h sustained
  - [ ] adapter swap p99 < 50ms
  - [ ] user-facing regression 0 件 (`degraded_to_ollama=True` flag 監視)
- [ ] DB3 re-arm trigger 監視 dashboard (Grafana / Prometheus 候補、scope 次第)
- [ ] 1 week 後の Phase G report 起草
- [ ] **hard switch 検討** (1 week stable なら Ollama 削除を別 PR で評価、DA-2 re-open)

---

## Phase H-Z (placeholder、M9-D / M10 接続)

- **Phase H**: M9-D Tier C judge LLM integration (M9-eval-system ME-* 完成後、D-4 trigger)
- **Phase I**: 4 persona 目以降の追加 (Confucius / Socrates、M10-A 範囲、D-2 trigger)
- **Phase J**: vLLM v0.15+ への optional migration evaluation (DB3 re-arm trigger 起動時、D-3 trigger)
- **Phase K**: PEFT vs unsloth final 選定 (D-1 closure)
- **Phase L**: SGLang 0.6+ upgrade (D-5 trigger)
- **Phase M**: rikyu Japanese tokenizer 実装 (H-2 解消、`m9-eval-corpus-rikyu-tokenizer` 別 PR)
- **Phase N**: Tier B final threshold pin (P4b/P4c 完了後の DA-11+、U-2 closure)
- **Phase Z**: M11 multi-agent concurrent inference (asyncio.gather + multi-adapter routing)

---

## チェックリスト (Phase A 完了確認、本セッション scope)

- [x] 10 file scaffold 完了
- [x] requirement.md AC-1..AC-6 measurable + HIGH-1/HIGH-2 反映
- [x] design.md / v2 / comparison consistency
- [x] codex-review.md verbatim 保存 (要約 / 改変 0 件)
- [x] design-final.md に HIGH 4 全反映 + MEDIUM 6 trace + LOW 3 trace
- [x] decisions.md DA-1..DA-10 各 5 要素埋まる
- [x] blockers.md 4 区分 (hard H-1/H-2、soft S-1/S-2/S-3、defer D-1..D-5、uncertainty U-1..U-5)
- [x] tasklist.md (本書) Phase A-G + H-Z populate
- [ ] commit + push + PR
- [ ] PR description に Codex Verdict + HIGH 反映マッピング表 + "code 変更ゼロ" 明示
