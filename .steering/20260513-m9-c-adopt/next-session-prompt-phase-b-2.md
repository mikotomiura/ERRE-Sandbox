# Next-session handoff prompt — M9-C-adopt Phase B 第 2 セッション (rank=4 archive → rank=16 training → Tier B pilot → 採用 rank 確定)

**作成**: 2026-05-14 (Phase B 第 1 セッション: rank=4 overnight training 完走確認後)
**前提**: Phase B 第 1 セッションで Step 0/1/2 完了 (commit `0246768` / `8e7352b` / `487fb10` / `92786f2`)、rank=4 training は overnight で **正常完走** (実測 ~2.15h、peak_vram 10.51 GB、train_loss 0.2364)
**用途**: 新セッション最初の prompt として貼り付け。本セッションは Phase B 残工程 (Step 3-7) を一気通貫で実施
**branch**: `feature/m9-c-adopt-phase-b-rank-sweep` (origin push 済、4 commit)

---

```
M9-C-adopt の **Phase B 第 2 セッション** を実行する。第 1 セッション
(2026-05-13 夜) で Step 0 pre-flight + Step 1 rank=4 training overnight 走行 +
Step 2 rank=8 baseline archive を完遂し、rank=4 は overnight で正常完走済
(train_loss=0.2364、peak_vram=10.51GB、train_runtime=7733s)。本セッションは
**Step 3 (rank=4 archive + rank=16 training) → Step 4 (3 adapter multi-pin) →
Step 5 (Tier B pilot 採取 + metric 算出) → Step 6 (conditional rank=32 判定) →
Step 7 (採用 rank 確定 + PR 起票)** を実施する。

## 最初に必ず Read する file (内面化必須)

1. `.steering/20260513-m9-c-adopt/phase-b-progress.md` — in-flight 状態 +
   重複 training incident 教訓 + 既知の落とし穴 (MSYS_NO_PATHCONV / SGLang
   training 同時起動禁止 / tqdm `\r` tail 不可視 / Loading weight ~62s/it)
2. `.steering/20260513-m9-c-adopt/decisions.md` — DA-1 採用基準 (4 軸
   intersection) + DA-1 amendment 2026-05-13 (CS-1 `--max-lora-rank 16`) +
   DA-10 manifest schema + DA-6 hard block (.bin pickle refuse)
3. `.steering/20260513-m9-c-adopt/blockers.md` — H-1 / S-2 / S-3 の status
   (S-2 解消済、S-3 は rank=16 で要 sustained monitor)
4. `.steering/20260513-m9-c-adopt/tasklist.md` — Phase B 残 Step の
   チェックボックス (Step 3-7、AC-1 PASS 条件)
5. `.steering/20260513-m9-c-adopt/design-final.md` — HIGH 4 反映マッピング表
6. `scripts/build_adapter_manifest.py` — manifest 生成 CLI (DA-10 schema、
   CS-9/DA-6 hard block 込み)
7. `.steering/20260513-m9-c-adopt/phase-b-logs/kick_train.sh` — training
   launcher (rank=N を引数で受ける)

## 直近完了状態 (2026-05-14 朝 時点)

- branch: `feature/m9-c-adopt-phase-b-rank-sweep` (origin push 済、4 commit)
  - `0246768` Step 0 pre-flight (CS-1 amendment + manifest scaffold)
  - `8e7352b` Step 2 rank=8 archive + manifest backfill + gitignore policy
  - `487fb10` Phase B in-flight progress pin
  - `92786f2` Phase B incident record (重複 training kill → ETA 短縮)
- rank=4 training: **完走** (verified 2026-05-14 朝)
  - 場所: `/root/erre-sandbox/checkpoints/kant_r4_real/`
  - `adapter_model.safetensors` (15.4 MB、sha256 `b89a248695394a8d17c606d6509d46c268ba4e0efbb04641555af9a21e05f78d`)
  - `train_metadata.json` (peak_vram_bytes=10514916352、train_loss=0.23640、
    train_runtime=7733s、realised_examples=5022、quantization=nf4、
    target_modules=["q_proj","k_proj","v_proj","o_proj"])
  - `checkpoint-2000/` 到達 = 完了 mark
  - PID file (`phase-b-logs/kant_r4_real.pid`) は process 消滅で stale
    (削除して可)
- rank=8 baseline: archive 済 (`data/lora/m9-c-adopt/archive/rank_8/kant/`)、
  manifest.json 生成済 (PR #163 由来の既存 adapter を backfill)
- rank=16: 未着手
- Tier B baseline (no LoRA on kant golden shard): **未算出**
  (blockers.md H-1 partial verify、Step 5 で算出予定)

## Phase B 残 Scope (本セッション)

### Step 3a: rank=4 archive + manifest 生成 (~10min、Mac side or WSL2)

- [ ] WSL2 で archive copy:
  ```bash
  MSYS_NO_PATHCONV=1 wsl -- bash -c "
    mkdir -p /mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt/archive/rank_4/kant && \
    cp /root/erre-sandbox/checkpoints/kant_r4_real/adapter_config.json \
       /root/erre-sandbox/checkpoints/kant_r4_real/adapter_model.safetensors \
       /root/erre-sandbox/checkpoints/kant_r4_real/train_metadata.json \
       /root/erre-sandbox/checkpoints/kant_r4_real/chat_template.jinja \
       /mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt/archive/rank_4/kant/"
  ```
- [ ] manifest 生成 (DA-10 schema、`scripts/build_adapter_manifest.py`):
  ```bash
  MSYS_NO_PATHCONV=1 wsl -- bash -c "cd /mnt/c/ERRE-Sand_Box && \
    /root/erre-sandbox/.venv/bin/python scripts/build_adapter_manifest.py \
      --adapter-dir data/lora/m9-c-adopt/archive/rank_4/kant \
      --persona-id kant --rank 4"
  ```
- [ ] sha256 verification:
  - 期待値 `b89a248695394a8d17c606d6509d46c268ba4e0efbb04641555af9a21e05f78d`
  - manifest.json 内の `sha256_adapter_model` と一致確認
- [ ] gitignore 確認 (rank_8 と同じく `.safetensors` は除外、manifest.json
  + adapter_config.json + train_metadata.json のみ commit)

### Step 3b: rank=16 training kick (G-GEAR overnight、~3-4h 想定)

VRAM 警戒 (rank=4 で peak 10.51GB、rank=16 で adapter 4x + activation 増、
~11-13GB sustained 想定、headroom 3-5GB、S-3 14GB threshold で要 monitor)。
training 中は **SGLang server を必ず停止** (`pkill -f sglang.launch_server`)。

- [ ] SGLang 停止確認:
  ```bash
  wsl -- bash -c "pkill -f sglang.launch_server 2>/dev/null; sleep 2; nvidia-smi --query-gpu=memory.used --format=csv"
  ```
- [ ] VRAM free 確認 (`memory.used < 1000 MiB` 目安)
- [ ] kick (`kick_train.sh 16` 経由、第 1 セッション同じ pattern):
  ```bash
  MSYS_NO_PATHCONV=1 wsl -- bash /mnt/c/ERRE-Sand_Box/.steering/20260513-m9-c-adopt/phase-b-logs/kick_train.sh 16
  ```
- [ ] **kick 後すぐ `pgrep -af train_kant_lora` で重複起動が無いか確認**
  (incident 教訓: 5min 後の Loading weight ~62s/it が異常遅延なら重複疑い、
  古い PID を kill して resource 競合解消)
- [ ] in-flight monitor (per ~30min):
  - `tr '\r' '\n' < phase-b-logs/train_kant_r16_real.log | tail -10`
  - `nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv`
  - VRAM **sustained > 14GB** で early abort、rank=16 評価打ち切り
    (この場合 DA-1 採用基準は rank ∈ {4, 8} のみで判定)
- [ ] 完了確認 (期待: train_runtime ~3000-4000s、`checkpoint-2000/` +
  `adapter_model.safetensors` 揃い)

### Step 3c: rank=16 archive + manifest

- [ ] Step 3a と同 pattern で `data/lora/m9-c-adopt/archive/rank_16/kant/`
  へ copy + manifest 生成
- [ ] sha256 verbatim 記録 (phase-b-progress.md update)

### Step 4: 3 adapter SGLang multi-pin load + chat round trip (~30min)

- [ ] SGLang launch (DB8 runbook §2 v6、`--max-lora-rank 16` amendment 後):
  ```bash
  wsl -- bash -c "cd /root/erre-sandbox && nohup /root/erre-sandbox/.venv/bin/python -m sglang.launch_server \
    --model-path Qwen/Qwen3-8B --host 0.0.0.0 --port 30000 \
    --enable-lora --max-lora-rank 16 \
    --max-loras-per-batch 3 --max-loaded-loras 3 \
    --quantization fp8 --mem-fraction-static 0.85 \
    > /mnt/c/ERRE-Sand_Box/.steering/20260513-m9-c-adopt/phase-b-logs/sglang_multi_pin.log 2>&1 &"
  ```
- [ ] healthcheck: `curl http://localhost:30000/health` → 200
- [ ] 3 adapter load (POST `/load_lora_adapter`):
  - `kant_r4_real` ← `/root/erre-sandbox/checkpoints/kant_r4_real/` or archive
  - `kant_r8_real` ← `/root/erre-sandbox/checkpoints/kant_r8_real/`
  - `kant_r16_real` ← `/root/erre-sandbox/checkpoints/kant_r16_real/`
  - 各 HTTP 200 + `loaded_adapters` に 3 件並ぶ確認
- [ ] chat round trip (3 rank で 1 prompt ずつ、`lora_path` 指定):
  - prompt: 「Was ist die Bedingung der Möglichkeit der Erfahrung?」
  - response 取得 + 3 rank で **異なる出力** が来ることを目視確認
    (identity でないこと = adapter が効いていることの sanity)
- [ ] SGLang stop (Step 5 採取で再 launch するので一旦停止しても可)

### Step 5: Tier B pilot 採取 + metric 算出 + DA-1 4 軸評価 (~6h compute + ~2h 分析)

第 1 セッション prompt の Step 4-5 と同じ。**per-rank 500 turn × 3 run = 1500 turn**
で 3 rank で 4500 turn 採取 (per-turn ~14s × 4500 = ~17.5h は超過するので
**per-rank stimulus 300 turn × 2 run = 600 turn、3 rank で 1800 turn ~7h**
に縮める)。Phase E で full 7500 turn 再採取。

- [ ] **Tier B baseline (no LoRA) 算出** (H-1 解消):
  - kant golden baseline shard (`data/eval/golden/kant_stimulus_run{0..4}.duckdb`、
    PR #160 由来) から `tier_b_bootstrap_pair.py` consumer で Vendi /
    Big5 ICC(C,k) primary + ICC(A,1) diagnostic / Burrows Δ 算出
  - `.steering/20260513-m9-c-adopt/tier-b-baseline-kant.md` に point + bootstrap
    95% CI lower bound + direction を verbatim 保存
- [ ] SGLang re-launch (Step 4 同 launch args、3 adapter pinned)
- [ ] serialized inference loop (asyncio-free、固定 prompt set、stimulus prompts):
  - rank=4: 300 turn × 2 run = 600 turn → `data/eval/m9-c-adopt-tier-b-pilot/kant_r4_run{0,1}_stim.duckdb`
  - rank=8: 同上 → `kant_r8_run{0,1}_stim.duckdb`
  - rank=16: 同上 → `kant_r16_run{0,1}_stim.duckdb`
- [ ] checkpoint resume protocol (per 100 turn save、resume CLI option)
- [ ] `epoch_phase=evaluation` で書き、後続 training 漏洩防止 (DB11 整合)
- [ ] **CS-7 4 trigger 既存 bench** で no_lora / single_lora-rank{4,8,16}
  比較 (`scripts/bench_serving.py` or 既存 K-β bench):
  - p99 TTFT / ITL / e2e / output tok/s / error rate
  - 全 trigger NON-FIRE 確認 (FIRE なら該当 rank は採用候補から外す)
- [ ] **DA-1 4 軸採用基準で kant の rank=X 決定**:
  1. Vendi point + CI lower bound + direction "LoRA-on < no-LoRA" PASS の
     smallest rank (saturate floor)
  2. Big5 ICC(C,k) ≥ 0.6 point + CI lower bound ≥ 0.6 を満たす min rank
  3. Burrows Δ reduction ≥ 10% + CI clear を満たす min rank
  4. bench throughput ≥ 70% baseline (K-β 34.64 tok/s × 0.7 = 24.25 tok/s) を
     満たす max rank ceiling
  5. 1+2+3 intersection 上限 ≤ 4 ceiling 内で smaller rank 採用

### Step 6 (conditional): rank=32 tail-sweep 判定

**fire 条件 2 つ** (HIGH-1 反映、DA-1 re-open trigger):
- rank=16 throughput PASS かつ Vendi/ICC/Burrows いずれか未達
- rank=8 → 16 で effect size delta > 0.5 (sharp gain)

条件未満たしなら **skip** して Step 7 へ。fire 時は:
- [ ] CS-1 launch arg amendment v2: `--max-lora-rank 32` (runbook 再 update)
- [ ] rank=32 training (G-GEAR overnight、~6-8h 想定、VRAM peak 警戒)
- [ ] archive + manifest + pilot Tier B 600 turn 採取
- [ ] DA-1 4 軸再評価で rank=16 vs rank=32 比較

### Step 7: 採用 rank pin + 報告 + commit/PR (~半日 Mac side)

- [ ] **採用 rank 確定** (e.g. `kant_adopted_rank = 8` or 16)
- [ ] `decisions.md` に DA-1 amendment 2026-05-14 (実測値 verbatim):
  - 各 rank の Vendi / ICC / Burrows / throughput 実測値 table
  - 採用 rank の根拠 (4 軸 intersection 結果)
  - tail-sweep 実施有無 + 結果
- [ ] `tasklist.md` Phase B チェックボックス完了 mark
- [ ] `blockers.md` H-1 解消 (Tier B baseline 算出済) / S-2 解消確定 /
  S-3 実測値 amendment (rank=16 sustained peak)
- [ ] `data/lora/m9-c-adopt/kant_r{adopted}_real/` を **production 採用配置**
  (archive 内の同 rank 内容を copy、`is_mock=false`、`training_git_sha=<HEAD>`)
- [ ] `phase-b-progress.md` を Final state へ update (in-flight section を
  Final outcome section へ書き換え)
- [ ] **Phase B 報告書** (`.steering/20260513-m9-c-adopt/phase-b-report.md` 新規):
  - 実測 verbatim (rank × metric matrix)
  - 採用 rank + 根拠
  - VRAM 実測 peak (training / serving 両方)
  - blockers.md status 変動
  - Phase C (3 persona expansion) 着手前の dependency (training data 抽出
    contract、generic CLI 化案、AC-2 条件)
- [ ] commit: `feat(adopt): m9-c-adopt — Phase B kant rank sweep 完遂 + 採用 rank={X}`
- [ ] `gh pr create` (branch `feature/m9-c-adopt-phase-b-rank-sweep`)、
  PR description に:
  - rank × metric 実測 table
  - DA-1 採用根拠 (4 軸)
  - tail-sweep 実施有無
  - sha256 (rank=4 / rank=8 / rank=16 / (rank=32))
  - VRAM peak (training / serving)
  - 「next-session-prompt-phase-c.md は別 PR」明記
- [ ] Mac master review 待ち (auto-merge しない)
- [ ] Phase C 着手前の `next-session-prompt-phase-c.md` 起草 (本 PR scope 外、
  rank=X pin 後に別 PR で)

## NOT in scope (本セッション)

- nietzsche / rikyu の training (Phase C scope)
- `MultiBackendChatClient` 実装 / live path 統合 (Phase D scope)
- multi_lora_3 bench (Phase D scope)
- FSM smoke 24 cell (Phase E scope)
- Tier B **full** 7500 turn (Phase E scope、本セッションは pilot 600 turn × 3 rank)
- production loader / verdict report (Phase F scope)

## 注意 (incident 教訓 + 既知の落とし穴)

- **MSYS_NO_PATHCONV=1** prefix を Bash tool 経由の WSL2 invocation で必須
  (Git Bash の path mangling 回避)。PowerShell tool では不要
- **重複 training process 検出**: kick 後 `pgrep -af train_kant_lora` で
  必ず重複 check。Loading weight ~62s/it が異常遅延なら重複疑い、resource
  競合で training stall する (第 1 セッション incident で実証)
- **SGLang server は training 中必ず停止** (`pkill -f sglang.launch_server`)。
  VRAM 16GB 中 ~10-13GB を training が占有するため同時起動で即 OOM
- **tqdm `\r` progress bar は `tail` で見えない**。`tr '\r' '\n' | tail`
  で展開
- main 直 push 禁止 / 50% 超セッション継続禁止 (`/smart-compact`)
- GPL を `src/erre_sandbox/` に import 禁止
- 本セッションは **kant のみ scope**、3 persona expansion は別 PR
- VRAM peak **sustained > 14GB** で early abort (S-3 mitigation)。
  transient (model load 中の NF4 quantize 過渡) は許容
- conditional rank=32 tail-sweep は **条件を満たした場合のみ** fire、
  default は skip

## 完了条件 (本セッション = AC-1 PASS)

### archive + manifest
- [ ] kant rank=4: `data/lora/m9-c-adopt/archive/rank_4/kant/` + manifest.json + sha256
- [ ] kant rank=8: 既存 (第 1 セッション完遂)
- [ ] kant rank=16: train 完了 + archive + manifest + sha256
- [ ] (conditional) kant rank=32: tail-sweep fire 時のみ

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
- [ ] `blockers.md` H-1 / S-2 / S-3 status 更新
- [ ] `phase-b-progress.md` Final state へ書き換え
- [ ] `phase-b-report.md` 起票

### PR
- [ ] branch `feature/m9-c-adopt-phase-b-rank-sweep` で PR 起票
- [ ] PR description に rank × metric matrix + DA-1 採用根拠 + tail-sweep
  実施有無 + sha256 + VRAM peak
- [ ] Mac master review 待ち
- [ ] Phase C 着手前の `next-session-prompt-phase-c.md` 起草 (別 PR)

## 参照

- 第 1 セッション handoff: `.steering/20260513-m9-c-adopt/next-session-prompt-phase-b.md`
  (Phase B 全体設計、本 prompt は Step 3-7 に focus)
- in-flight state: `.steering/20260513-m9-c-adopt/phase-b-progress.md`
  (重複 training incident 記録 + 既知の落とし穴)
- ADR: `.steering/20260513-m9-c-adopt/decisions.md` (DA-1..DA-10 + DA-1
  amendment 2026-05-13)
- blockers: `.steering/20260513-m9-c-adopt/blockers.md`
- tasklist: `.steering/20260513-m9-c-adopt/tasklist.md` (Phase B Step 1-7
  + 前提 verification 済 mark)
- DB8 runbook: `docs/runbooks/m9-c-adapter-swap-runbook.md` (§2
  `--max-lora-rank 16` amendment 済)
- training script: `src/erre_sandbox/training/train_kant_lora.py` (`--persona`
  + `--rank` 受け付け済、Phase C で `train_persona_lora.py` rename 候補)
- manifest builder: `scripts/build_adapter_manifest.py` (DA-10 schema、
  hard block #2 .bin pickle refuse 込み)
- launcher: `.steering/20260513-m9-c-adopt/phase-b-logs/kick_train.sh`
- Tier B framework: M9-eval-system `tier_b_bootstrap_pair.py`
  (consumer のみ、本 PR 改変対象外)
- 既存 K-β bench artefact: `data/eval/spike/m9-c-spike-bench/single_lora.jsonl`
  (rank=8 baseline、再採取不要)
- Codex review HIGH-1 引用 (rank sweep literature):
  - LoRA Land (https://arxiv.org/abs/2405.00732)
  - PLORA (https://openreview.net/pdf?id=azsnOWy9MZ)
  - P-React (https://aclanthology.org/2025.findings-acl.328.pdf)

まず **`phase-b-progress.md`** を読み、第 1 セッションの incident 教訓と
in-flight 状態 (rank=4 完走確認済) を完全に内面化した上で、Step 3a の
rank=4 archive + manifest 生成から実施する。Step 3a/3b は短時間
(~10min) なので 1 session 内で連続実行。Step 3b の rank=16 training は
overnight 必要 (G-GEAR 実走必須)、kick 後の monitor 規定 (sustained
> 14GB で early abort) を厳守する。Step 5 の Tier B 採取・metric 算出は
Mac master 側でも post-hoc 可能。

なお本セッションは **GPU training + Tier B 採取 + bench** を含むため
G-GEAR 実走必須。コンテキスト使用率が 50% 超に達したら `/smart-compact`
で区切る。
```
