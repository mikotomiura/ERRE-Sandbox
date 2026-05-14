# Next-session handoff prompt — M9-C-adopt Phase B 第 3 セッション (Tier B pilot 採取 → 採用 rank 確定 → PR 起票)

**作成**: 2026-05-14 (Phase B 第 2 セッション: Step 3a+3b+3c+4 完遂後)
**前提**: 第 2 セッションで rank=4 archive (sha256 `b89a248695...`)、rank=16 training 完走 (train_loss=0.1993、train_runtime=7424s、sha256 `9532b438f3...`)、rank=16 archive、3 adapter multi-pin sanity 全 PASS。
**用途**: 新セッション最初の prompt として貼り付け。本セッションは Phase B 残工程 Step 5 (Tier B pilot 採取 + DA-1 4 軸評価) → Step 6 (conditional rank=32 判定) → Step 7 (採用 rank 確定 + 報告 + PR) を実施。
**branch**: `feature/m9-c-adopt-phase-b-rank-sweep` (origin push 済)

---

```
M9-C-adopt の **Phase B 第 3 セッション** を実行する。第 2 セッション
(2026-05-14 朝) で Step 3a (rank=4 archive)、Step 3b (rank=16 training 完走、
train_loss=0.1993、train_runtime=7424s)、Step 3c (rank=16 archive、sha256
`9532b438f3...`)、Step 4 (3 adapter SGLang multi-pin load + chat round trip で
3 rank が異なる出力 = adapter routing 確認) を完遂した。本セッションは
**Step 5 (Tier B pilot 採取 + metric 算出 + DA-1 4 軸評価) → Step 6
(conditional rank=32 tail-sweep 判定) → Step 7 (採用 rank 確定 + 報告 +
PR 起票)** を実施する。

## 最初に必ず Read する file (内面化必須)

1. `.steering/20260513-m9-c-adopt/phase-b-progress.md` — 第 2 セッション完了
   サマリ + 既知の落とし穴 (ninja symlink workaround / WSL2 idle shutdown 対策 /
   Bash PATH 内 `(` syntax error)
2. `.steering/20260513-m9-c-adopt/decisions.md` — DA-1 4 軸採用基準 + DA-1
   amendment 2026-05-13 + DA-8 Tier B 3 条件 AND + DA-9 marginal pass retrain
   path
3. `.steering/20260513-m9-c-adopt/blockers.md` — H-1 / S-2 / S-3 status
   (S-2 解消済、S-3 sustained 14016 MiB observed、threshold 14300 MiB に
   amendment 済)
4. `.steering/20260513-m9-c-adopt/tasklist.md` — Phase B Step 5-7 残
5. `.steering/20260513-m9-c-adopt/phase-b-logs/multi_pin_artifacts/` —
   Step 4 sanity 出力 (rank=4/8/16 で異なる出力を verbatim 保管)
6. `src/erre_sandbox/cli/eval_run_golden.py` — stimulus 採取 CLI (Ollama
   default、SGLang backend 追加 or 別 driver 新規必要)
7. `src/erre_sandbox/evidence/tier_b/{vendi,big5_icc,ipip_neo}.py` — Tier B
   metric pure helper
8. `src/erre_sandbox/evidence/tier_a/burrows.py` — Burrows Δ helper
9. `data/eval/golden/kant_stimulus_run{0..4}.duckdb` — H-1 baseline shard
   (no-LoRA、Tier B baseline 算出元)

## 直近完了状態 (第 2 セッション終了時、2026-05-14)

- branch: `feature/m9-c-adopt-phase-b-rank-sweep` (origin push 済)
  - 第 1 セッション 4 commit + 第 2 セッション追加 commit (Phase B Step 3a/3b/3c/4 +
    progress.md update + watch_r16.sh + multi_pin_sanity.sh + multi_pin_artifacts/)
- 3 archive 揃い:
  - `data/lora/m9-c-adopt/archive/rank_4/kant/`  sha256 `b89a248695394a8d17c606d6509d46c268ba4e0efbb04641555af9a21e05f78d`
  - `data/lora/m9-c-adopt/archive/rank_8/kant/`  sha256 `cd8c6e5f6bea4b20d3c8b496a64e04513fda8f4ebf89cfa2dc0028ab12d01716`
  - `data/lora/m9-c-adopt/archive/rank_16/kant/` sha256 `9532b438f34da8e87ebb4a71707da4ab22c4ed790959c177c7ea8fc373c0ac38`
- training metadata (各 rank の checkpoints dir 内 `train_metadata.json`):
  - rank=4 : peak_vram=10.51GB、loss=0.2364、runtime=7733s、5022 examples
  - rank=8 : (PR #163 由来、再採取せず)
  - rank=16: peak_vram=10.14GB、loss=0.1993、runtime=7424s、5022 examples
- multi-pin sanity (Step 4) PASS: 3 adapter 同時 load + 異なる出力で routing 確認

## Phase B 残 Scope (本セッション)

### Step 5: Tier B pilot 採取 + metric 算出 + DA-1 4 軸評価 (~6h compute + ~2h 分析)

#### 5a: Tier B no-LoRA baseline 算出 (~1h、Mac master でも可)

H-1 (kant baseline ICC 未算出) を解消する。kant golden stimulus shard
(`data/eval/golden/kant_stimulus_run{0..4}.duckdb` 5 shard、PR #160 由来) から
no-LoRA baseline metric を算出:

- [ ] Vendi semantic effect size 算出 (`erre_sandbox.evidence.tier_b.vendi.compute_vendi`)、
  effect size は LoRA-off baseline single value
- [ ] Big5 ICC(C,k) primary + ICC(A,1) diagnostic 算出
  (`compute_big5_icc`)、per-window Big5 vector が必要 = IPIP-NEO administering
  per window (既存 raw_dialog から後付け Big5 自己申告 inference 必要、
  M9-eval framework consumer 経由)
- [ ] Burrows Δ baseline 算出 (`erre_sandbox.evidence.tier_a.burrows`)、
  author corpus 比 (Kant 著作 corpus、M9-eval P4a で確立済)
- [ ] 結果を `.steering/20260513-m9-c-adopt/tier-b-baseline-kant.md` に
  verbatim 保存 (point + bootstrap 95% CI lower bound + direction)

#### 5b: SGLang re-launch + 3 adapter pinned (~10min)

第 2 セッション Step 4 と同 launch args:

```bash
# 事前: ninja symlink (一度実施で永続) — 第 2 セッションで /usr/local/bin/ninja symlink 済
MSYS_NO_PATHCONV=1 wsl -- bash -c "ls -la /usr/local/bin/ninja"
# 期待: lrwxrwxrwx -> /root/erre-sandbox/.venv/bin/ninja

# launch (Bash bg で WSL2 alive 保持)
MSYS_NO_PATHCONV=1 wsl -- bash -c "cd /root/erre-sandbox && /root/erre-sandbox/.venv/bin/python -m sglang.launch_server \
  --model-path Qwen/Qwen3-8B --host 0.0.0.0 --port 30000 \
  --enable-lora --lora-target-modules q_proj k_proj v_proj o_proj \
  --max-lora-rank 16 --max-loras-per-batch 3 --max-loaded-loras 3 \
  --quantization fp8 --mem-fraction-static 0.85 --max-total-tokens 2048 \
  --disable-cuda-graph --max-running-requests 1 \
  > /mnt/c/ERRE-Sand_Box/.steering/20260513-m9-c-adopt/phase-b-logs/sglang_pilot.log 2>&1"
# Bash tool: run_in_background=true で wsl.exe を pinned
```

health check (~3-5 min):
```bash
until curl -sf http://localhost:30000/health > /dev/null 2>&1; do sleep 15; done; echo "ready"
```

3 adapter load (Step 4 同 pattern、`multi_pin_sanity.sh` 流用可能):
- POST `/load_lora_adapter` で `kant_r4_real`, `kant_r8_real`, `kant_r16_real`

#### 5c: serialized inference loop 採取 (~7h compute、checkpoint resume 必要)

prompt set: kant stimulus YAML (M9-eval P3 由来、`data/golden/stimulus/kant.yaml` 候補)
or 既存 `eval_run_golden` CLI の stimulus condition 流用。

scope (Phase B pilot、Phase E full ではない):
- per-rank: 300 turn × 2 run = 600 turn (full 500×5=2500 turn は Phase E に defer)
- 3 rank で 1800 turn total
- per-turn ~14s 想定、~7h compute

implementation 選択:
- **A 案** (推奨、低コスト): `eval_run_golden` CLI を fork or extend し
  `--inference-backend sglang --lora-adapter kant_r{rank}_real` を追加
- **B 案** (新規 driver): `scripts/m9-c-adopt-tier-b-pilot.py` 新規、
  HTTP API 経由 で per-prompt serialized loop

書き先: `data/eval/m9-c-adopt-tier-b-pilot/kant_r{4,8,16}_run{0,1}_stim.duckdb`
- `epoch_phase=evaluation` で書き、後続 training 漏洩防止 (DB11)
- checkpoint resume protocol (per 100 turn flush、resume CLI option)

#### 5d: Tier B metric 算出 (per-rank、~1h analysis)

各 LoRA-on shard で:
- Vendi semantic point + 95% CI lower bound + direction (LoRA-on < no-LoRA)
- Big5 ICC(C,k) point + CI + direction、ICC(A,1) diagnostic
- Burrows Δ reduction % + CI + direction

`erre_sandbox.evidence.bootstrap_ci.bootstrap` ヘルパで bootstrap 95% CI 算出。
3 値 (point / CI lower / direction) を 3 rank × 3 metric matrix に整理。

#### 5e: CS-7 4 trigger 既存 bench (~30min)

`scripts/m9-c-spike/run_bench_serving.sh` 流用、no_lora / single_lora-r{4,8,16}
の 4 condition で:
- p99 TTFT / ITL / e2e / output tok/s / error rate
- 4 trigger 全 NON-FIRE 確認 (FIRE rank は採用候補から外す)
- ベース throughput baseline: PR #163 K-β single_lora 34.64 tok/s × 0.7 = 24.25 tok/s

#### 5f: DA-1 4 軸 intersection で kant 採用 rank 決定

1. Vendi: point + CI lower bound + direction "LoRA-on < no-LoRA" PASS の smallest rank
2. Big5 ICC(C,k) ≥ 0.6 point + CI lower bound ≥ 0.6 を満たす min rank
3. Burrows Δ reduction ≥ 10% point + CI lower bound > 0 を満たす min rank
4. bench throughput ≥ 24.25 tok/s を満たす max rank ceiling
5. 1∩2∩3 ⊆ 4 ceiling 内で smaller rank 採用

3 軸全達成の smallest rank が確定 → DA-1 4 軸 PASS。
1+ 軸が CI lower bound 未達 + point だけ達成 → DA-9 marginal pass retrain path
(別 PR `feature/m9-c-adopt-retrain-v2` で min_examples 1000→3000 + stimulus
prompt diversity 改善)。

### Step 6 (conditional): rank=32 tail-sweep 判定

fire 条件 2 件 (DA-1 HIGH-1):
- rank=16 throughput PASS かつ Vendi/ICC/Burrows いずれか未達
- rank=8 → 16 で effect size delta > 0.5

fire 時のみ:
- [ ] CS-1 launch arg amendment v2: `--max-lora-rank 32` (runbook DB8 §2 v7
  へ update)
- [ ] rank=32 training (G-GEAR overnight、~3h 想定、rank=4/8/16 と同 runtime
  scale)
- [ ] archive + manifest (allow_tail_sweep=True、`build_adapter_manifest.py`
  に `--allow-tail-sweep` flag)
- [ ] pilot Tier B 600 turn 採取 + metric 算出
- [ ] DA-1 4 軸再評価で rank=16 vs rank=32 比較

skip 条件 (default 想定):
- rank=16 で 3 軸全達成 → skip
- rank=8 → 16 で sharp gain ではない → skip

### Step 7: 採用 rank 確定 + 報告 + commit/PR (~半日 Mac side でも可)

- [ ] 採用 rank 確定 (e.g. `kant_adopted_rank = 8` or 16)
- [ ] `decisions.md` に DA-1 amendment 2026-05-14 (実測値 verbatim):
  - 各 rank の Vendi / ICC(C,k) / ICC(A,1) / Burrows Δ / throughput 実測値 matrix
  - 採用 rank の根拠 (4 軸 intersection 結果)
  - tail-sweep 実施有無 + (実施時) 結果
- [ ] `tasklist.md` Phase B チェックボックス完了 mark
- [ ] `blockers.md` 更新:
  - H-1 解消 (kant baseline Tier B 算出済)
  - S-3 実測値 amendment (rank=16 sustained 14016 MiB、threshold 14300 MiB)
  - rank=32 tail-sweep 実施有無を記録
- [ ] `data/lora/m9-c-adopt/kant_r{adopted}_real/` を production 採用配置
  (archive 内同 rank を copy、`is_mock=false`、`training_git_sha=<HEAD>`)
- [ ] `phase-b-progress.md` Final state へ update (in-flight section → Final
  outcome section)
- [ ] `phase-b-report.md` 起票 (新規):
  - rank × metric 実測 table
  - 採用 rank + 根拠
  - VRAM 実測 peak (training: rank=4 10.51GB / rank=16 10.14GB metadata,
    nvidia-smi sustained ~14016MiB / serving: fp8 ~10.86GB peak)
  - blockers.md status 変動
  - Phase C 着手前 dependency (training data 抽出 contract、generic CLI 化案、
    AC-2 条件、nietzsche/rikyu baseline shard verification)
- [ ] commit: `feat(adopt): m9-c-adopt — Phase B kant rank sweep 完遂 + 採用 rank={X}`
- [ ] `gh pr create` (branch `feature/m9-c-adopt-phase-b-rank-sweep`)、
  PR description:
  - rank × metric 実測 table
  - DA-1 採用根拠 (4 軸 intersection 結果)
  - tail-sweep 実施有無
  - 3 (or 4) sha256
  - VRAM peak (training / serving)
  - 「next-session-prompt-phase-c.md は別 PR」明記
- [ ] Mac master review 待ち (auto-merge しない)
- [ ] Phase C 着手前の `next-session-prompt-phase-c.md` 起草 (本 PR scope 外、
  rank=X pin 後に別 PR で)

## NOT in scope (本セッション)

- nietzsche / rikyu の training (Phase C scope、別 PR)
- `MultiBackendChatClient` 実装 / live path 統合 (Phase D scope)
- multi_lora_3 real-after stress bench (Phase D/E scope)
- FSM smoke 24 cell (Phase E scope)
- Tier B **full** 7500 turn (Phase E scope、本セッションは pilot 1800 turn)
- production loader / verdict report (Phase F scope)

## 注意 (incident 教訓 + 既知の落とし穴、本 prompt 用 amendment)

- **ninja CLI 不在 → SGLang fp8 JIT compile 失敗**: 第 2 セッション Step 4 で
  発覚。`ln -sf /root/erre-sandbox/.venv/bin/ninja /usr/local/bin/ninja` で
  symlink (一度実施で永続)。本セッションでも事前 verify:
  ```
  MSYS_NO_PATHCONV=1 wsl -- bash -c "ls -la /usr/local/bin/ninja && /usr/local/bin/ninja --version"
  ```
- **WSL2 idle shutdown 対策**: Bash bg task (`run_in_background=true`) で
  wsl.exe を pinned することで WSL2 alive 保持。`nohup ... & disown` は
  WSL2 死亡時に効かない (第 2 セッション Step 3b 第 1 試行で失敗、第 1 セッション
  rank=4 が overnight 完走したのは user が WSL 端末を別途維持していた偶然)
- **Bash tool 経由の `wsl -- bash -c "..."` で PATH に `(` 含有時 syntax error**:
  Git Bash 側で PATH expansion 時 "Program Files (x86)" のパレンが bash parse fail。
  symlink で system PATH 採用 or PATH を explicit string で渡す
- **redirect は WSL 内 bash 経由必須**: `wsl -- cmd > /mnt/c/...` だと Git Bash
  側 redirect が `/mnt/c/...` を解釈できず fail。`wsl -- bash -c "cmd > /mnt/c/..."`
  パターン厳守
- **MSYS_NO_PATHCONV=1** prefix を Bash tool 経由の WSL2 invocation で必須
  (Git Bash の path mangling 回避)。PowerShell tool では不要
- **重複 training process 検出**: training kick 後は `pgrep -af train_kant_lora`
  で重複 check を必ず実施 (第 1 セッション rank=4 incident 教訓)
- **SGLang server は training 中必ず停止**: VRAM 占有衝突で即 OOM
- **tqdm `\r` progress bar は `tail` で見えない**: `tr '\r' '\n' | tail` で展開
- main 直 push 禁止 / 50% 超セッション継続禁止 (`/smart-compact`)
- GPL を `src/erre_sandbox/` に import 禁止
- 本セッションは **kant のみ scope**、3 persona expansion は Phase C 別 PR
- VRAM peak **sustained > 14300 MiB** で early abort (第 2 セッション S-3
  amendment 後 threshold)。transient (model load / NF4 quantize 過渡) は許容
- conditional rank=32 tail-sweep は **条件を満たした場合のみ** fire、default skip

## 完了条件 (本セッション = AC-1 PASS)

### Tier B pilot
- [ ] kant no-LoRA baseline metric 算出 (H-1 解消)
- [ ] 3 (or 4) rank × 600 turn pilot 採取
- [ ] Vendi / ICC(C,k) / ICC(A,1) / Burrows Δ + bootstrap 95% CI 算出
- [ ] CS-7 bench (no_lora / single_lora-rank{4,8,16,(32)}) 全 trigger NON-FIRE

### 採用 rank 決定
- [ ] DA-1 4 軸 intersection で kant の rank=X 確定
- [ ] `data/lora/m9-c-adopt/kant_r{X}_real/` を production 採用配置
- [ ] archive `data/lora/m9-c-adopt/archive/rank_{4,8,16,(32)}/kant/` retain

### tracking
- [ ] `decisions.md` に DA-1 amendment 2026-05-14 (実測値 verbatim)
- [ ] `tasklist.md` Phase B チェック完了 mark
- [ ] `blockers.md` H-1 / S-3 status 更新
- [ ] `phase-b-progress.md` Final state へ書き換え
- [ ] `phase-b-report.md` 起票

### PR
- [ ] branch `feature/m9-c-adopt-phase-b-rank-sweep` で PR 起票
- [ ] PR description に rank × metric matrix + DA-1 採用根拠 + tail-sweep
  実施有無 + sha256 + VRAM peak
- [ ] Mac master review 待ち
- [ ] Phase C 着手前の `next-session-prompt-phase-c.md` 起草 (別 PR)

## 参照

- 第 2 セッション handoff (前 prompt): `.steering/20260513-m9-c-adopt/next-session-prompt-phase-b-2.md`
- in-flight state: `.steering/20260513-m9-c-adopt/phase-b-progress.md`
  (第 2 セッション完了サマリ + 既知の落とし穴)
- ADR: `.steering/20260513-m9-c-adopt/decisions.md` (DA-1..DA-10 + DA-1
  amendment 2026-05-13)
- blockers: `.steering/20260513-m9-c-adopt/blockers.md`
- tasklist: `.steering/20260513-m9-c-adopt/tasklist.md`
- DB8 runbook: `docs/runbooks/m9-c-adapter-swap-runbook.md` (§2
  `--max-lora-rank 16` amendment 済)
- Tier B framework: `src/erre_sandbox/evidence/tier_b/` (vendi/big5_icc/ipip_neo)
- Burrows Δ: `src/erre_sandbox/evidence/tier_a/burrows.py`
- bootstrap CI: `src/erre_sandbox/evidence/bootstrap_ci.py`
- stimulus 採取 CLI: `src/erre_sandbox/cli/eval_run_golden.py`
- 既存 K-β bench: `data/eval/spike/m9-c-spike-bench/single_lora.jsonl`
  (rank=8 baseline、再採取不要)
- multi-pin sanity 出力: `.steering/20260513-m9-c-adopt/phase-b-logs/multi_pin_artifacts/`
- Codex review HIGH-1 引用 (rank sweep literature):
  - LoRA Land (https://arxiv.org/abs/2405.00732)
  - PLORA (https://openreview.net/pdf?id=azsnOWy9MZ)
  - P-React (https://aclanthology.org/2025.findings-acl.328.pdf)

まず **`phase-b-progress.md`** を読み、第 2 セッションで揃った 3 archive +
manifest + multi-pin sanity 結果を完全に内面化した上で、Step 5a (Tier B
no-LoRA baseline 算出) から実施する。Step 5b/5c の SGLang re-launch + 1800 turn
採取は G-GEAR 実走必須。Step 5d-5f の metric 算出 + DA-1 4 軸評価 + bench は
Mac master 側でも post-hoc 可能。コンテキスト使用率 50% 超で `/smart-compact`
で区切る。

なお、本セッションが完了すれば PR が起票され、Phase C (3 persona expansion)
着手準備に入る。
```
