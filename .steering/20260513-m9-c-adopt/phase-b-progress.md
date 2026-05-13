# Phase B 進捗 — m9-c-adopt rank sweep on kant (in-flight、2026-05-13 セッション 1)

> Phase A (PR #164 merged) → Phase B 第 1 セッション (2026-05-13 夜)。本 file
> は overnight 走行中の training を引き継ぐための **state pin**。次セッション
> で本 file を最初に Read し、in-flight 状態を回復してから残工程に進む。

---

## 現在の状態 (2026-05-13 22:48 JST 時点)

| Step | 内容 | 状態 |
|---|---|---|
| Step 0 | pre-flight (branch + CS-1 amendment + manifest scaffold) | **完了** (commit `0246768`) |
| Step 1 | rank=4 training (kant、G-GEAR overnight) | **running** (PID 838、background detached) |
| Step 2 | rank=8 baseline re-confirm + manifest backfill | **完了** (commit `8e7352b`) |
| Step 3 | rank=16 training | 未着手 (rank=4 完了後に kick) |
| Step 4-7 | Tier B pilot + metric + verdict + PR | 未着手 |

branch: `feature/m9-c-adopt-phase-b-rank-sweep` (origin に push 済、2 commit)

---

## rank=4 training in-flight 詳細

### 起動 invocation

```bash
# 経由: .steering/20260513-m9-c-adopt/phase-b-logs/kick_train.sh 4
MSYS_NO_PATHCONV=1 wsl -- bash /mnt/c/ERRE-Sand_Box/.steering/20260513-m9-c-adopt/phase-b-logs/kick_train.sh 4
```

実行された native command:

```bash
nohup /root/erre-sandbox/.venv/bin/python -m erre_sandbox.training.train_kant_lora \
  --persona kant \
  --rank 4 \
  --duckdb-glob '/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_*.duckdb' \
  --output-dir /root/erre-sandbox/checkpoints/kant_r4_real \
  -v \
  > /mnt/c/ERRE-Sand_Box/.steering/20260513-m9-c-adopt/phase-b-logs/train_kant_r4_real.log 2>&1 < /dev/null &
disown
```

### in-flight 計測 (起動から ~5min、PID 383 kill 前)

- PID: 838 (`/mnt/c/ERRE-Sand_Box/.steering/20260513-m9-c-adopt/phase-b-logs/kant_r4_real.pid`)
- elapsed: 04:55 (起動 22:43:51 JST)
- RSS: 4.7 GB (CPU 側、HF Hub cache 経由 model load 中)
- VRAM peak: **15.7 GB / 16.3 GB total** (bf16 model 全載 → NF4 quantize 過渡期、
  S-3 14GB threshold より上だが quantize 中の transient と判定、PR #163 K-β は
  完了時 peak 10.55 GB)
- GPU util: 20-87% 変動 (NF4 weight conversion バースト)
- log progress: `Loading weights: 4/399 [04:30<6:53:33, 62.82s/it]` (起動 5 分時点、
  ETA ~7h for weight load alone) ⚠ **異常遅延**
- 期待 total wall-clock: weight load 5-7h + training 2-3h = **~10h** (PR #163 K-β
  rank=8 と同等想定)

### 2026-05-13 23:28 JST incident — 重複 training process 検出 → PID 383 kill

ユーザー指摘「monitor だけで実 training しているか」「不要な裏側処理がないか」
診断中に発覚:

- **`pgrep -af train_kant_lora` で 2 プロセス検出**:
  - PID 383 (start 22:42、`Rl` running、ppid 302) — **私の最初の `nohup` 試行
    (PowerShell `$!` escape 失敗で `PID=` 空表示) で実は起動成功していた残骸**
  - PID 838 (start 22:43、`Sl` sleeping、ppid 830) — `kick_train.sh` 経由の正規
    起動、phase-b-progress.md に記録した process
- **両 process が同じ `--output-dir /root/erre-sandbox/checkpoints/kant_r4_real`
  に書く** = race condition / save_steps 衝突の危険 (training step 到達前に発覚)
- **GPU/CPU resource 競合** が Loading weights 異常遅延 (60s/it) の主原因と判定:
  - VRAM 15.7 GB = 2 × ~8 GB の bf16 model copy
  - GPU util は 1 process あたり 50% で頭打ち
- **PID 383 kill 実行** (`kill 383`):
  - VRAM 15987 → **10044 MiB** (5943 MiB 即時解放、PR #163 K-β peak 10.55 GB と整合)
  - PID 838 状態 `Sl` → `Rl` (resource 待ち解消、active running)
- **kill 後 30 秒で training 本体到達**:
  - log: `1%| | 29/2000 [05:52<3:28:56, 6.36s/it]`
  - **Loading weights は kill 時点で完了済み、training step に入っていた**
  - rate 13.7 → 10.9 → 8.9 → 7.4 → **6.36 s/step** に加速 (resource 単独利用効果)
  - VRAM 13.5 GB peak / GPU 89% sustained
  - 新 ETA: **~3.5h で training 完了** (起動から累計 ~4h、9h 短縮)

### 教訓 (再発防止)

1. `wsl -- bash -c "...nohup..."` を Bash tool 経由で実行する際、PowerShell が
   `$!` を空文字に置換することがある。**`PID=` が空表示でも実プロセスは起動済み**
   の可能性を疑う必要がある。
2. **kick 後は `pgrep -af` で重複起動を必ず check**。今回は kick の前に重複が
   無いか確認していなかった (最初の `nohup` 試行は失敗したと誤判定して 2 度目を
   kick)。
3. Bash tool / PowerShell の `$` escape 不安定対策として、launcher script を
   ファイルに書いて `wsl -- bash ./script.sh` で呼ぶパターンを採用 (実装済、
   `kick_train.sh`)。
4. **MSYS_NO_PATHCONV=1 prefix の有無で path mangling が変わる**。Bash tool
   (Git Bash 経由) では必須、PowerShell tool では不要。次セッションで rank=16
   kick 時に再徹底する。

### incident 後の正常 in-flight 計測 (2026-05-13 23:28 JST 時点)

- PID: 838 単独
- elapsed: 44:53 (kill 直後)
- VRAM: 13.5 GB peak (S-3 14GB threshold 近接、要 sustained monitor)
- GPU util: 89% sustained
- training progress: 29/2000 step (1.45%)、ETA 3:28:56
- 出力 directory: `/root/erre-sandbox/checkpoints/kant_r4_real/` (save_steps 500、
  step 500 到達で checkpoint-500 dir 生成想定)

### Phase B prompt の VRAM monitor 規定 (S-3 mitigation)

- `nvidia-smi --query-gpu=memory.used` per-step sampling、**peak > 14GB sustained**
  で early abort
- **transient peak (model load 中)** は許容、**training 開始後の sustained > 14GB**
  でのみ early abort 判断
- PR #163 K-β rank=8 は training 中 peak 10.55 GB、rank=4 は activation 同等 + adapter
  ~15MB のため training 中 peak は ~10.5 GB 想定 (S-3 invoke 不要)

---

## 次セッションの最優先 action

### 1. rank=4 training 完了確認

```bash
# WSL2 process state
MSYS_NO_PATHCONV=1 wsl -- bash -c "PID=\$(cat /mnt/c/ERRE-Sand_Box/.steering/20260513-m9-c-adopt/phase-b-logs/kant_r4_real.pid); ps -p \$PID -o pid,etime,stat,cmd --no-headers 2>&1; echo ---; tail -30 /mnt/c/ERRE-Sand_Box/.steering/20260513-m9-c-adopt/phase-b-logs/train_kant_r4_real.log | tr '\r' '\n' | tail -10; echo ---; ls /root/erre-sandbox/checkpoints/kant_r4_real/ 2>&1"
```

判定:

- process が **存在しない** + `adapter_model.safetensors` + `train_metadata.json`
  が `/root/erre-sandbox/checkpoints/kant_r4_real/` に揃う → **完了**
- process が **生きている** + log が最終 step 近辺 → **継続待ち**
- process が **存在しない** + adapter file 不在 → **fail**、log で原因切り分け

### 2. rank=4 完了時の archive + manifest 生成

```bash
MSYS_NO_PATHCONV=1 wsl -- bash -c "
  cp /root/erre-sandbox/checkpoints/kant_r4_real/adapter_config.json \
     /root/erre-sandbox/checkpoints/kant_r4_real/adapter_model.safetensors \
     /root/erre-sandbox/checkpoints/kant_r4_real/train_metadata.json \
     /mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt/archive/rank_4/kant/ && \
  cd /mnt/c/ERRE-Sand_Box && \
  /root/erre-sandbox/.venv/bin/python scripts/build_adapter_manifest.py \
    --adapter-dir data/lora/m9-c-adopt/archive/rank_4/kant \
    --persona-id kant --rank 4"
```

### 3. rank=16 training kick (Step 3)

rank=4 完了確認後:

```bash
MSYS_NO_PATHCONV=1 wsl -- bash /mnt/c/ERRE-Sand_Box/.steering/20260513-m9-c-adopt/phase-b-logs/kick_train.sh 16
```

注意点:

- VRAM peak 警戒 (rank=16 で activation 増、CS-4 fp8 serving 10.86GB を training
  時 NF4 + bf16 transient で再考)、peak > 14GB sustained で early abort
- training 中は SGLang server を起動しない (VRAM 占有衝突)

### 4. rank=16 完了後の archive + manifest

```bash
MSYS_NO_PATHCONV=1 wsl -- bash -c "
  cp /root/erre-sandbox/checkpoints/kant_r16_real/adapter_config.json \
     /root/erre-sandbox/checkpoints/kant_r16_real/adapter_model.safetensors \
     /root/erre-sandbox/checkpoints/kant_r16_real/train_metadata.json \
     /mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt/archive/rank_16/kant/ && \
  cd /mnt/c/ERRE-Sand_Box && \
  /root/erre-sandbox/.venv/bin/python scripts/build_adapter_manifest.py \
    --adapter-dir data/lora/m9-c-adopt/archive/rank_16/kant \
    --persona-id kant --rank 16"
```

### 5. Step 4 Tier B pilot 着手前

3 adapter 揃い (rank=4 / rank=8 既存 / rank=16) + manifest 3 件 + SGLang
`--max-lora-rank 16` で multi-pin load 確認 → Step 4 へ。Step 4 着手前に
本 progress.md を update し、3 rank の adapter sha256 + VRAM peak (training 中)
を verbatim 記録する。

---

## 既知の落とし穴

### MSYS path conversion

Bash tool (Git Bash on Windows) は `/mnt/c/...` を `C:/Program Files/Git/mnt/...`
に MSYS auto-translate する。WSL2 invocation には `MSYS_NO_PATHCONV=1` を必ず
prefix する。`kick_train.sh` は内部で `/mnt/c/` を直接使うが、Bash tool 経由で
呼ぶ際は `MSYS_NO_PATHCONV=1 wsl -- bash ...` の形を厳守。

### tqdm progress bar が tail で見えない

`Loading weights:` の進捗バーは `\r` で in-place update する。`tail` では古い
line しか見えないため、最新 state 確認は:

```bash
tr '\r' '\n' < /mnt/c/ERRE-Sand_Box/.steering/20260513-m9-c-adopt/phase-b-logs/train_kant_r4_real.log | tail -10
```

### training 中の SGLang stop 必須

`pkill -f sglang.launch_server`、VRAM `nvidia-smi` で 16GB total のうち 14GB+
free を確認。training は **16GB 中ほぼ全てを** model load 中に消費するため、
SGLang が同時に走っていると即 OOM。

### Loading weight rate ~62-87s/it

CPU 100% + GPU 20-87% で **hardware-limited**、stall ではない。PR #163 K-β
rank=8 と同等 throughput と判断。399 iter × ~60s = ~6.7h を model load に費やす。
Training 本体は per-step ~5s × 2000 step = ~3h。

---

## 関連ファイル

- 設計契約: `.steering/20260513-m9-c-adopt/design-final.md` (HIGH 4 反映後)
- ADR: `.steering/20260513-m9-c-adopt/decisions.md` (DA-1..DA-10 + DA-1 amendment 2026-05-13)
- blockers: `.steering/20260513-m9-c-adopt/blockers.md` (S-2 解消、H-1 partial verify)
- tasklist: `.steering/20260513-m9-c-adopt/tasklist.md` (Phase B Step 0-7 + 前提 verification 済 mark)
- DB8 runbook: `docs/runbooks/m9-c-adapter-swap-runbook.md` (§2 `--max-lora-rank 16` amendment 済)
- launcher: `.steering/20260513-m9-c-adopt/phase-b-logs/kick_train.sh`
- manifest builder: `scripts/build_adapter_manifest.py` (DA-10 schema)
- archive (rank=8 完了済): `data/lora/m9-c-adopt/archive/rank_8/kant/{manifest.json,adapter_config.json,train_metadata.json}`
