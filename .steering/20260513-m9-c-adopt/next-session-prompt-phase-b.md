# Next-session handoff prompt — M9-C-adopt Phase B (rank sweep on kant、`{4, 8, 16}` + conditional rank=32 tail-sweep)

**作成**: 2026-05-13 (PR #164 merge 直後、Phase A design scaffold 完遂)
**前提**: M9-C-adopt Phase A 完遂 (PR #164 で DA-1..DA-10 ADR + Codex HIGH 4 / MEDIUM 6 / LOW 3 全反映 + hybrid v3 確定)
**用途**: 新セッション (~20-30h、G-GEAR 必須、overnight × 2-3) の最初の prompt として貼り付け
**本セッションは Phase B = rank sweep on kant のみ。3 persona expansion (Phase C) は本 PR scope 外**

---

```
M9-C-adopt の **Phase B (kant rank sweep)** を実行する。Phase A
(PR #164 merged) で確定した DA-1 採用基準 (4 軸 intersection: Vendi
saturate floor + Big5 ICC(C,k) ≥ 0.6 point + CI lower bound + Burrows
Δ reduction ≥ 10% + bench throughput ≥ 70% baseline) で **kant の採用
rank を empirical 決定** する。本セッションは G-GEAR (WSL2 venv) で
overnight × 2-3 night の 18h compute、Mac master 側は code 補助 + Tier B
post-hoc 分析。

## 直近完了状態 (2026-05-13 時点)

- main HEAD = `8c3577b` (Merge PR #164、Phase A design scaffold)
- M9-C-adopt Phase A 完遂:
  - `.steering/20260513-m9-c-adopt/` 10 file (requirement / design v1 /
    v2-reimagine / comparison / codex-review-prompt / codex-review /
    design-final / decisions DA-1..DA-10 / blockers / tasklist)
  - Codex Verdict: **ADOPT-WITH-CHANGES** (HIGH 4 / MEDIUM 6 / LOW 3)、
    全反映済
- M9-C-spike 全 PR merged (#154/#155/#160/#161/#162/#163)
- artefact:
  - WSL2 venv (`/root/erre-sandbox/.venv`) に peft 0.19.1 /
    bitsandbytes 0.49.2 / accelerate 1.13.0 / sglang 0.5.10.post1 +
    cu128 torch 2.9.1 / transformers 5.3.0 install 済
  - `/root/erre-sandbox/checkpoints/kant_r8_real/` に既存 real Kant LoRA
    adapter (rank=8、30.7MB) — Phase B では rank=8 anchor として再利用
  - M9-eval Phase B+C golden baseline (PR #160、kant 含む 30 cell) で
    kant 5022 examples が抽出可能 (CS-3 dry-run verified)
  - `docs/runbooks/m9-c-adapter-swap-runbook.md` (DB8) 完成、`--max-lora-rank 8`
    pin
- Phase A 決定事項 (本セッションで enforce):
  - rank sweep `{4, 8, 16}` default (DA-1、HIGH-1 反映)
  - conditional rank=32 tail-sweep trigger 2 通り:
    1. rank=16 throughput PASS かつ Vendi/ICC/Burrows いずれか未達
    2. rank=8 → 16 で effect size delta > 0.5 (sharp gain)
  - **SGLang launch arg amendment**: `--max-lora-rank >= 16` 必須
    (CS-1 amendment 候補、本セッション内で実施)
  - 採用 rank 決定基準 (DA-1 4 軸 intersection):
    - Vendi semantic effect size point + bootstrap 95% CI lower bound > 0
      + direction "LoRA-on < no-LoRA"
    - Big5 ICC(C,k) ≥ 0.6 point + CI lower bound ≥ 0.6
    - Burrows Δ reduction ≥ 10% point + CI lower bound > 0
    - bench throughput ≥ 70% baseline (CS-7 amendment 実測 single_lora=34.64 tok/s)
    - smaller rank 優先
  - adapter manifest + sha256 (DA-10) を Phase B 出力で必ず生成
  - production loader manifest-grade integrity (DA-6) は Phase F、本セッションでは不要

## Phase B scope (本セッション)

### Step 0: pre-flight (本 PR 内、~30min Mac side)

- [ ] `git checkout -b feature/m9-c-adopt-phase-b-rank-sweep`
- [ ] **H-1 verification** (blockers.md hard blocker、Phase B-G 着手前必須):
  - kant の Tier B baseline (no LoRA) が `data/eval/m9-c-adopt-tier-b/baseline/kant_no_lora.duckdb`
    に揃っているか確認
  - 揃っていなければ M9-eval Phase B+C golden baseline shard
    (PR #160、`data/eval/phase-bc-golden/kant/run{0..4}/`) から
    `tier_b_bootstrap_pair.py` consumer で算出
  - 算出 metric: Vendi semantic kernel / Big5 ICC(C,k) / ICC(A,1)
    diagnostic / Burrows Δ
- [ ] **S-2 解消** (CS-1 amendment): `--max-lora-rank 8` → `--max-lora-rank 16`
  - `docs/runbooks/m9-c-adapter-swap-runbook.md` (DB8) §2 launch SOP v5
    の `--max-lora-rank` を 16 へ amendment、Phase B コミット内で
    runbook を update
  - 注意: M9-C-spike `decisions.md` CS-1 自体は immutable、本 PR は
    launch args の rank field のみ runbook level で update。CS-1 全体の
    amendment は本 PR の `decisions.md` に CS-1 amendment 2026-05-XX を
    追記 (rank pin の理由付き)

### Step 1: rank=4 training (G-GEAR overnight × 1、~2-3h)

- [ ] WSL2 venv で `python -m erre_sandbox.training.train_kant_lora
  --rank 4 --output /root/erre-sandbox/checkpoints/kant_r4_real/`
  (既存 CLI を `--rank` 引数 generic 化、または `train_persona_lora.py`
  へ rename)
- [ ] training data: `_collect_from_shards(persona_id="kant")` で
  5022 examples (CS-3 verified)
- [ ] `assert_phase_beta_ready(min_examples=1000)` PASS 確認
- [ ] training 中 VRAM peak `nvidia-smi --query-gpu=memory.used`
  per-step sampling、peak > 14GB で early abort (blockers.md S-3)
- [ ] training 完了後:
  - [ ] adapter directory に `adapter_config.json` +
    `adapter_model.safetensors` 揃い
  - [ ] sha256 計算 → `scripts/build_adapter_manifest.py` (新規候補) で
    `manifest.json` 生成 (DA-10 schema)
    ```json
    {
      "adapter_name": "kant_r4_real",
      "persona_id": "kant",
      "base_model": "Qwen/Qwen3-8B",
      "rank": 4,
      "target_modules": ["q_proj","k_proj","v_proj","o_proj"],
      "sha256_adapter_model": "...",
      "training_git_sha": "<HEAD sha>",
      "is_mock": false,
      "created_at": "<ISO8601>"
    }
    ```
  - [ ] `data/lora/m9-c-adopt/archive/rank_4/kant/` へ配置
    (`adapter_model.safetensors` + `adapter_config.json` + `manifest.json`)

### Step 2: rank=8 baseline re-confirm (~30min Mac side)

- [ ] 既存 `kant_r8_real` (PR #163) を `data/lora/m9-c-adopt/archive/rank_8/kant/`
  へコピー + manifest.json 生成
- [ ] SGLang `/load_lora_adapter` HTTP 200 確認 (`--max-lora-rank 16`
  で起動した SGLang server に rank=8 adapter load)
- [ ] chat round trip success
- [ ] 既存 K-β bench artefact (`data/eval/spike/m9-c-spike-bench/
  single_lora.jsonl`) を rank=8 baseline として再利用 (新規採取不要)

### Step 3: rank=16 training (G-GEAR overnight × 1、~2-3h)

- [ ] `python -m erre_sandbox.training.train_kant_lora --rank 16
  --output /root/erre-sandbox/checkpoints/kant_r16_real/`
- [ ] VRAM peak monitor 強化 (rank=16 で adapter ~60MB + activation 増、
  CS-4 8.7GB から ~9.5GB peak 想定、headroom 6.5GB)
- [ ] manifest.json + sha256 生成、`data/lora/m9-c-adopt/archive/rank_16/kant/`
- [ ] SGLang load + chat round trip 確認

### Step 4: 3 rank の Tier B 採取 (G-GEAR overnight × 1、~10h)

各 rank で stimulus 500 turn × 5 run = 2500 turn、3 rank で 7500 turn。
per-turn ~14s × 7500 = ~29h は超過するので、本セッションは **per-rank
500 turn × 3 run = 1500 turn (= 1 rank ~5.8h、3 rank で 17.4h)** に
縮める。Phase E で full 7500 turn を再採取。

- [ ] SGLang launch (`--enable-lora --max-lora-rank 16 --max-loras-per-batch 3
  --max-loaded-loras 3 --quantization fp8 --mem-fraction-static 0.85`)
- [ ] 3 adapter pinned load (`kant_r4_real` / `kant_r8_real` / `kant_r16_real`)
- [ ] serialized inference loop (asyncio-free、固定 prompt set)、
  各 rank 別 raw_dialog shard へ
  - [ ] `data/eval/m9-c-adopt-tier-b-pilot/kant_r4_run{0..2}_stim.duckdb`
  - [ ] `data/eval/m9-c-adopt-tier-b-pilot/kant_r8_run{0..2}_stim.duckdb`
  - [ ] `data/eval/m9-c-adopt-tier-b-pilot/kant_r16_run{0..2}_stim.duckdb`
- [ ] checkpoint resume protocol (per 100 turn save、resume CLI option)
- [ ] `epoch_phase=evaluation` で書き、後続 training 漏洩防止 (DB11 整合)

### Step 5: Tier B metric 算出 + DA-1 4 軸評価 (~1 day Mac side)

- [ ] `tier_b_bootstrap_pair.py` で 3 rank × 3 metric 算出
  - [ ] Vendi semantic effect size (Cohen's d) + bootstrap 95% CI
  - [ ] Big5 ICC(C,k) primary + ICC(A,1) diagnostic (MEDIUM-4 反映)
  - [ ] Burrows Δ reduction % + CI
- [ ] bench throughput per-rank (`bench_serving` で no_lora vs
  single_lora-rank{4,8,16}、CS-7 4 trigger)
- [ ] **DA-1 採用基準で kant の rank=X 決定**:
  1. 各 rank の Vendi point + CI lower bound + direction が PASS する
     smallest rank (saturate floor)
  2. ICC(C,k) ≥ 0.6 point + CI ≥ 0.6 を満たす min rank
  3. Burrows Δ reduction ≥ 10% + CI clear を満たす min rank
  4. bench throughput ≥ 70% baseline を満たす max rank ceiling
  5. 1+2+3 の intersection 上限 ≤ 4 の ceiling 内で smaller rank 採用
- [ ] **conditional rank=32 tail-sweep 判定** (DA-1 re-open trigger):
  - [ ] rank=16 throughput PASS かつ Vendi/ICC/Burrows いずれか未達 → tail-sweep fire
  - [ ] rank=8 → 16 で effect size delta > 0.5 → tail-sweep fire
  - [ ] fire 時: Step 6 へ、それ以外は Step 7 へ

### Step 6 (conditional): rank=32 tail-sweep (G-GEAR overnight × 1、~3h + pilot Tier B ~6h)

**tail-sweep 起動条件を満たした場合のみ実施**。条件未満たしなら skip。

- [ ] CS-1 launch arg amendment v2: `--max-lora-rank 32` (runbook 再 update)
- [ ] `python -m erre_sandbox.training.train_kant_lora --rank 32
  --output /root/erre-sandbox/checkpoints/kant_r32_real/`
- [ ] VRAM peak 警戒 (rank=32 で adapter ~200MB + activation 大幅増、
  CS-4 8.7GB から ~12-13GB peak 想定、headroom 3-4GB)、peak > 14GB で
  early abort、rank=32 評価打ち切り (rank=16 final)
- [ ] manifest + sha256 + `data/lora/m9-c-adopt/archive/rank_32/kant/`
- [ ] rank=32 pilot Tier B (stimulus 500 × 3 run = 1500 turn)
- [ ] DA-1 4 軸再評価で rank=32 を rank=16 と比較、smaller rank 優先

### Step 7: 採用 rank pin + 報告 + commit/PR (~1 day Mac side)

- [ ] **採用 rank 確定** (e.g. `kant_adopted_rank = 8` or 16)
- [ ] `decisions.md` に DA-1 amendment 2026-05-XX を追記 (実測値 verbatim
  保存):
  - 各 rank の Vendi / ICC / Burrows / throughput 実測値
  - 採用 rank の根拠 (4 軸 intersection 結果)
  - tail-sweep 実施有無 + 結果
- [ ] `tasklist.md` Phase B チェックボックスを完了 mark
- [ ] `blockers.md` S-2 (CS-1 amendment) を解消 mark、S-3 (VRAM)
  実測値 amendment
- [ ] `data/lora/m9-c-adopt/kant_r{adopted}_real/` を **production 採用**
  として copy + manifest.json 整理 (`is_mock=false`、`training_git_sha=<HEAD>`)
  - archive は `data/lora/m9-c-adopt/archive/rank_{4,8,16,(32)}/kant/`
    に retain
- [ ] Phase B 報告 (`.steering/20260513-m9-c-adopt/phase-b-report.md` 新規):
  - 実測 verbatim (rank × metric matrix)
  - 採用 rank + 根拠
  - VRAM 実測 peak
  - blockers.md S-3 amendment
  - Phase C (3 persona expansion) 着手前の dependency
- [ ] commit: `feat(adopt): m9-c-adopt — Phase B kant rank sweep
  完遂 + 採用 rank={X}`
- [ ] PR description: rank × metric 実測 table + DA-1 採用根拠 +
  tail-sweep 実施有無

## NOT in scope (本セッション)

- nietzsche / rikyu の training (Phase C scope)
- live inference path 統合 (`MultiBackendChatClient` 実装、Phase D scope)
- multi_lora_3 bench (Phase D scope)
- 8-mode FSM smoke (Phase E scope)
- Tier B **full** 7500 turn (Phase E scope、本セッションは pilot 1500
  turn × 3 rank)
- production safety / verdict (Phase F scope)

## 注意

- main 直 push 禁止 / 50% 超セッション継続禁止 (`/smart-compact`)
- GPL を `src/erre_sandbox/` に import 禁止
- 本セッションは **kant のみ scope**、3 persona expansion は別 PR
- SGLang server (`/root/erre-sandbox/`) launch 中の VRAM 占有に注意、
  training kick 前に SGLang stop (`pkill -f sglang.launch_server`)、
  完了後 re-launch
- `--max-lora-rank` の amendment は **必須** (rank=16 を実際に
  serving するため、HIGH-1 反映)
- VRAM peak > 14GB observe で early abort (S-3 mitigation)
- conditional rank=32 tail-sweep は **条件を満たした場合のみ** fire、
  default は skip

## 完了条件 (本セッション)

### pre-flight
- [ ] H-1 (kant baseline ICC) 揃い確認
- [ ] S-2 (CS-1 `--max-lora-rank 16` amendment) DB8 runbook update + decisions.md 追記

### training
- [ ] kant rank=4 train 完了、manifest + sha256
- [ ] kant rank=8 baseline confirm + manifest backfill
- [ ] kant rank=16 train 完了、manifest + sha256
- [ ] (conditional) kant rank=32 tail-sweep training 完了

### Tier B pilot
- [ ] 3 (or 4) rank × 1500 turn pilot 採取
- [ ] Vendi / ICC(C,k) / ICC(A,1) / Burrows Δ + bootstrap CI 算出
- [ ] CS-7 bench (no_lora / single_lora-rank{4,8,16,(32)})

### 採用 rank 決定
- [ ] DA-1 4 軸 intersection で kant の rank=X 確定
- [ ] `data/lora/m9-c-adopt/kant_r{X}_real/` を production 採用配置
- [ ] archive `data/lora/m9-c-adopt/archive/rank_{4,8,16,(32)}/kant/` retain

### tracking
- [ ] `decisions.md` に DA-1 amendment 2026-05-XX (実測値 verbatim)
- [ ] `tasklist.md` Phase B チェック完了
- [ ] `blockers.md` S-2 解消 + S-3 実測 amendment
- [ ] `phase-b-report.md` 起票

### PR
- [ ] branch `feature/m9-c-adopt-phase-b-rank-sweep` で PR 起票
- [ ] PR description に rank × metric matrix + DA-1 採用根拠 +
  tail-sweep 実施有無
- [ ] Mac master review 待ち
- [ ] Phase C (3 persona expansion) 着手前の next-session-prompt-phase-c.md
  起草 (本 PR には含めない、別 PR)

## 参照

- M9-C-adopt Phase A: `.steering/20260513-m9-c-adopt/` 全 file (特に
  `decisions.md` DA-1..DA-10、`design-final.md`、`tasklist.md` Phase B)
- M9-C-spike 設計: `.steering/20260508-m9-c-spike/decisions.md`
  (CS-1..CS-9 + 3 amendment 2026-05-13)
- DB8 runbook: `docs/runbooks/m9-c-adapter-swap-runbook.md` (Step 0 で
  `--max-lora-rank 16` update)
- training script: `src/erre_sandbox/training/train_kant_lora.py`
  (`--rank` 引数 generic 化候補)
- bench script: `bench_serving` (CS-7、`data/eval/spike/m9-c-spike-bench/`)
- Tier B framework: M9-eval-system `tier_b_bootstrap_pair.py` (本 PR
  改変対象外、consumer のみ)
- 既存 K-β bench artefact: `data/eval/spike/m9-c-spike-bench/single_lora.jsonl`
  (rank=8 baseline、再採取不要)
- adapter manifest 仕様: `.steering/20260513-m9-c-adopt/decisions.md`
  DA-10
- Codex review HIGH-1 引用 (rank sweep literature):
  - LoRA Land (https://arxiv.org/abs/2405.00732)
  - PLORA (https://openreview.net/pdf?id=azsnOWy9MZ)
  - P-React (https://aclanthology.org/2025.findings-acl.328.pdf)

まず Phase A の `.steering/20260513-m9-c-adopt/` 全 file を読み、DA-1
採用基準と blockers.md hard/soft を完全に内面化した上で、Step 0
pre-flight から実施する。

なお本セッションは **GPU training + Tier B 採取 + bench** を含むため
G-GEAR 実走必須。Mac master 側は WSL2 SSH 経由で監視 + Tier B post-hoc
分析を担当する分業可能。
```
