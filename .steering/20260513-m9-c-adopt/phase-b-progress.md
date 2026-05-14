# Phase B 進捗 — m9-c-adopt rank sweep on kant (in-flight、第 2 セッション update 2026-05-14)

> Phase A (PR #164 merged) → Phase B 第 1 セッション (2026-05-13 夜) → 第 2
> セッション (2026-05-14 朝 〜)。本 file は in-flight 状態を引き継ぐための
> **state pin**。Step 3a (rank=4 archive) 完了、Step 3b (rank=16 training)
> 走行中。

---

## 現在の状態 (2026-05-14 第 2 セッション 進捗、Step 3a+3b+3c+4 完了時点)

| Step | 内容 | 状態 |
|---|---|---|
| Step 0 | pre-flight (branch + CS-1 amendment + manifest scaffold) | **完了** (commit `0246768`) |
| Step 1 | rank=4 training (kant、G-GEAR overnight) | **完走** (train_loss=0.2364、peak_vram=10.51GB、train_runtime=7733s、sha256 `b89a248695...`) |
| Step 2 | rank=8 baseline re-confirm + manifest backfill | **完了** (commit `8e7352b`、sha256 `cd8c6e5f...`) |
| Step 3a | rank=4 archive + manifest | **完了 (2026-05-14)** sha256 `b89a248695...` ✅ phase 1 verbatim 一致 |
| Step 3b | rank=16 training | **完走 (2026-05-14)** train_loss=0.1993、peak_vram_bytes=10.63GB、train_runtime=7424s (~2.06h) |
| Step 3c | rank=16 archive + manifest | **完了 (2026-05-14)** sha256 `9532b438f3...` |
| Step 4 | 3 adapter multi-pin load + chat sanity | **完了 (2026-05-14)** 3 rank で異なる出力 (adapter routing 確認) |
| Step 5-7 | Tier B pilot / verdict / PR | **次セッションに handoff** (`next-session-prompt-phase-b-3.md`) |

branch: `feature/m9-c-adopt-phase-b-rank-sweep` (origin に push 済、4 commit、Step 3a/3c/4 + 進捗 update は本セッションで追加 commit 予定)

---

## 第 2 セッション完了サマリ (2026-05-14)

### Step 3b 完走 (rank=16)

- elapsed: 起動 07:22 UTC → 完走 09:27 UTC (~2.06h)
- train_runtime=7424s、train_loss=0.1993 (rank=4 0.2364 から improvement)
- realised_examples=5022、quantization=nf4、target_modules=q/k/v/o_proj
- peak_vram_bytes (training metadata): 10630824960 = 10.14 GB
- nvidia-smi peak sustained: ~14016 MiB (driver + overhead 込み、operational margin 健全)
- S-3 watch threshold は 14000 → 14300 MiB に amendment (上記 plateau に operational margin +280 MiB)

### Step 3c — rank=16 archive

- 場所: `data/lora/m9-c-adopt/archive/rank_16/kant/`
- manifest:
  - `sha256_adapter_model=9532b438f34da8e87ebb4a71707da4ab22c4ed790959c177c7ea8fc373c0ac38`
  - `rank=16`、`training_git_sha=92786f28383c5e45336bc59170717488f45f2185`
  - その他 base_model / target_modules / is_mock は DA-10 schema 準拠
- adapter_model.safetensors サイズ: 61.4 MB (rank=4 15.4 MB の 4 倍、rank ratio 整合)

### Step 4 — multi-pin sanity (SGLang `--max-lora-rank 16`)

- launch args (DB8 runbook §2 v6、ninja symlink workaround 適用):
  ```
  --model-path Qwen/Qwen3-8B --enable-lora --lora-target-modules q_proj k_proj v_proj o_proj
  --max-lora-rank 16 --max-loras-per-batch 3 --max-loaded-loras 3
  --quantization fp8 --mem-fraction-static 0.85 --max-total-tokens 2048
  --disable-cuda-graph --max-running-requests 1
  ```
- POST /load_lora_adapter × 3 全 200 OK、`loaded_adapters` map 累積:
  ```json
  {"kant_r4_real": "...", "kant_r8_real": "...", "kant_r16_real": "..."}
  ```
- POST /v1/chat/completions × 3 で同一 prompt "Was ist die Bedingung der Möglichkeit der Erfahrung?"
  に対し **3 rank で異なる出力**: rank=4 は 3 条件分解 (sensibility/understanding/transcendental
  unity of apperception)、rank=8 は a priori/a posteriori 軸、rank=16 はより直接的構造
  → adapter routing が機能していることの sanity 確認
- artefact: `.steering/20260513-m9-c-adopt/phase-b-logs/multi_pin_artifacts/{load,chat}_kant_r{4,8,16}_real.json`

### ninja 不在 incident (Step 4 中)

- SGLang JIT compile (fp8 token_ids resolve kernel) で `ninja` CLI を subprocess で
  invoke、PATH 未通過で `FileNotFoundError`
- 解決: `ln -sf /root/erre-sandbox/.venv/bin/ninja /usr/local/bin/ninja` で system PATH へ
  symlink。spike 時は PATH 設定が異なっていた模様
- 教訓: SGLang fp8 + inference path は ninja CLI runtime 依存、PATH に必要

### 既知の落とし穴 amendment (本セッション追加)

- **Bash tool 経由の `wsl -- bash -c "..."` で PATH に `(` 含有時 syntax error**:
  `bash -c "export PATH=...:\$PATH && ..."` パターンは Windows-side PATH の "Program Files (x86)"
  パーレン含有で bash parsing fail。symlink で system PATH 採用 or PATH explicitly セット
- **WSL2 idle shutdown 対策**: Bash tool `run_in_background=true` で wsl.exe を pinned することで
  WSL2 alive 保持。nohup + disown は WSL2 死亡時に効かない (本セッション Step 3b 第 1 試行で失敗)

---

## 第 2 セッション update (2026-05-14)

### rank=4 archive 完了 (Step 3a)

- **archive 場所**: `data/lora/m9-c-adopt/archive/rank_4/kant/`
- **manifest 内容**:
  - `adapter_name=kant_r4_real`、`persona_id=kant`、`base_model=Qwen/Qwen3-8B`、`rank=4`
  - `target_modules=[q_proj,k_proj,v_proj,o_proj]`
  - `sha256_adapter_model=b89a248695394a8d17c606d6509d46c268ba4e0efbb04641555af9a21e05f78d` ✅ phase 1 verbatim と一致
  - `training_git_sha=92786f28383c5e45336bc59170717488f45f2185`
  - `is_mock=false`、`created_at=2026-05-13T22:19:11Z`
- **gitignore**: `.safetensors` + `chat_template.jinja` 除外、`manifest.json` + `adapter_config.json` + `train_metadata.json` のみ commit 対象 (rank_8 と同 policy)

### rank=16 training kick (Step 3b、in-flight)

- **起動方式**: Bash tool `run_in_background=true` で wsl.exe を pinned (nohup +
  disown は WSL2 idle shutdown で前回失敗。本 session では Bash bg task が
  wsl.exe を抱える間 WSL2 alive 維持)
- **kick 時刻**: 2026-05-14 07:22 UTC (Bash bg id `b4swoljve`)
- **invocation**:
  ```bash
  MSYS_NO_PATHCONV=1 wsl -- bash -c "/root/erre-sandbox/.venv/bin/python -m erre_sandbox.training.train_kant_lora \
    --persona kant --rank 16 --duckdb-glob '/mnt/c/ERRE-Sand_Box/data/eval/golden/kant_*.duckdb' \
    --output-dir /root/erre-sandbox/checkpoints/kant_r16_real -v \
    > /mnt/c/ERRE-Sand_Box/.steering/20260513-m9-c-adopt/phase-b-logs/train_kant_r16_real.log 2>&1"
  ```
- **kick 後 sanity** (~30s 経過):
  - PID 360 (python 単独、重複なし) ✅
  - Loading weights 1.2s/it (rank=4 第 1 セッション の 62s/it 異常遅延と対照、resource 単独利用)
  - VRAM 6.7 GB / GPU util 4% (model load 開始)
- **VRAM 警戒 Monitor**: `phase-b-logs/watch_r16.sh` で `nvidia-smi` per-60s sampling、
  log error/completion marker grep。当初 threshold 14000 MiB streak=3 で第 1 fire
  (2026-05-14 08:45 JST 時点 1332/2000 step / 14014-14020 MiB sustained / GPU 87-93% /
  temp 64-66°C)。S-3 早期 abort 規定の主旨は OOM 予防、実測 14016 MiB は total 16311 MiB
  に対し 2.3 GB headroom 健全 → **continue 判断**、threshold を 14300 MiB に amendment
  (rank=16 training の sustained plateau ~14016 MiB 上に operational margin +280 MiB)。
  Monitor `bht62jtxf` 停止 → `b6sxeyjgo` (threshold 14300) で再起動

### S-3 実測 amendment (2026-05-14)

- rank=16 training sustained VRAM plateau: **~14016 MiB** (training step ~1300 で観察)
- total VRAM: 16311 MiB → headroom ~2.3 GB
- S-3 当初 threshold 14000 MiB は precautionary、実際 OOM 余地は十分 (PR #163 K-β
  rank=8 は serving 中 fp8 10.86 GB peak、training は activation 増で +3 GB は妥当)
- watch_r16.sh threshold を **14300 MiB** に amendment、blockers.md S-3 status は
  「fire 継続だが non-blocking、rank=16 評価続行」に update 必要 (Step 7 で実施)
- **既知の落とし穴 (再発防止)**:
  - Bash tool 経由の WSL invocation で `>` redirect は `bash -c "..."` 内 (WSL 側) で行う。Git Bash 側だと `/mnt/c/...` が解釈できず redirect fail
  - WSL2 idle shutdown 対策として nohup + disown ではなく Bash bg task で wsl.exe を pinned

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
