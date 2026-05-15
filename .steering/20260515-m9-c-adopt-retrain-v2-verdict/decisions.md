# 重要な設計判断 — m9-c-adopt retrain v2 training execution + verdict

> 本 file は本 PR 内の session-local decisions を記録する。
> 横断的 ADR (DA-1 ~ DA-15) は `.steering/20260513-m9-c-adopt/decisions.md` に
> 追記する (immutable append convention)。
> 本 task の前段 implementation 経緯は
> `.steering/20260514-m9-c-adopt-retrain-v2-impl/decisions.md` (DI-1 ~ DI-4) 参照。

## DI-5: Real-tokenizer pre-training audit 結果

- **判断日時**: 2026-05-15 15:08 JST
- **CLI**: `python -m erre_sandbox.training.train_kant_lora --duckdb-glob
  "data/eval/golden/kant_*.duckdb" --output-dir data/lora/m9-c-adopt-v2/kant_r8_v2/
  --rank 8 --max-steps 4000 --weighted --dry-run -v`
  (`--no-real-tokenizer-for-weights` **不指定** → real Qwen3-8B tokenizer)
- **結果** (`data/lora/m9-c-adopt-v2/kant_r8_v2/weight-audit.json`):
  - realised_examples = 5022 (n_examples in audit = 5019、Δ3 は synthetic dedup)
  - synthetic_monolog_n = 500 (hard_cap、proxy と同一 deterministic subsample)
  - eval_split_size = 503
  - train_dialog_ids = 2562, eval_dialog_ids = 285 (disjoint hard-fail assert PASS)
  - **N_eff = 3886.4** ✅ (DA-14 fallback trigger 1000、target 1500 を大きく超過)
  - **top 5% weight share = 0.139** ✅ (DA-14 fallback trigger 0.50、target 0.35)
  - **de+en weighted mass = 0.489** ⚠️ (soft warning < 0.60、blocker ではない)
  - per-language: ja=0.498, en=0.278, de=0.211, mixed=0.013
  - split stratum: natural n_train=753 / n_eval=84, stimulus n_train=1809 / n_eval=201
- **proxy 比較** (DI-4 whitespace × 1.3 → real Qwen3-8B):
  - N_eff: 3560.9 → 3886.4 (+9.1%、real tokenizer の方が高く出る)
  - top 5%: 0.154 → 0.139 (-9.7%、real tokenizer の方が低い = 健全方向)
  - de+en: 0.501 → 0.489 (-2.4%、ほぼ同等、soft warning は persist)
  - 解釈: real tokenizer のほうが Japanese 長 token を正しく細分化するため
    seq_length 分布の bucket 配分が変わり、N_eff / top 5% が改善方向にずれた。
    Codex MEDIUM-1 の懸念 (proxy × 1.3 が real から ±10-20% ずれる) は
    実測通りで上限内に収まった。
- **判定**: **training continue**。Candidate C escalate は不要。
  de+en soft warning は DA-14 4 軸 REJECT 確定時のみ Candidate C 検討。

## DI-6: Phase 3 SGLang adapter registration plan (備忘)

- **背景**: 前回 multi-turn pilot (`.steering/20260514-m9-c-adopt-pilot-multiturn/`)
  は SGLang サーバーを WSL2 Linux 上で `/root/erre-sandbox/.venv/bin/python -m
  sglang.launch_server ...` で起動し、adapter は dynamic load API
  (`POST /load_lora_adapter`) で名前 `kant_r{rank}_real` で登録していた。
- **本 task の新 adapter**: `data/lora/m9-c-adopt-v2/kant_r8_v2/`
  - WSL path equivalent: `/mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v2`
- **計画**:
  1. SGLang を `--max-lora-rank 8` で WSL から起動 (port 30000)
  2. `curl POST /load_lora_adapter -d '{"lora_name":"kant_r8_v2","lora_path":
     "/mnt/c/ERRE-Sand_Box/data/lora/m9-c-adopt-v2/kant_r8_v2"}'` で登録
  3. tier_b_pilot.py を `--rank 8 --adapter-name kant_r8_v2` で 2 run 採取
  4. validate_multiturn_shards.py で 2/2 PASS 確認
  5. run_consumers.sh 相当を新 shard で実行 (vendi/burrows/icc)
- **注意**: tier_b_pilot.py の CLI には `--max-focal-per-shard` も `--adapter <path>`
  も存在しない (prompt の args は historical で誤り)。実 CLI は
  `--turn-count 300 --cycle-count 6 --multi-turn-max 6 --adapter-name <name>` で、
  これは前回 multi-turn pilot の baseline capture と apples-to-apples。

## DI-7: Training step time が想定の 2.5x、8h envelope で打ち切り計画

- **判断日時**: 2026-05-15 17:17 JST (training 1h58m 経過、step 500/4000 到達)
- **観測**: step time が初期 5.35s/it → 14.23s/it に上昇 (2.66x)。
  ETA = 4000 × 14.23 ≈ 15h49m (envelope 8h を大幅超過)。
- **原因仮説**:
  - VRAM 15973 MiB / 16311 MiB (98%、free 78 MiB)。allocator 圧迫で
    forward/backward kernel が slow path に落ちている可能性。
  - bitsandbytes NF4 quantisation + LoRA backward の peak は step 数に対し
    monotonic に大きくならないはずなので、最初の数 step だけ高速で残りが
    slow という挙動は activation checkpointing / gradient accum でも説明可。
- **convergence 状態**: loss 27.66 → ~1.8 in 500 steps (健全な収束)。
  abort trigger "training >7h かつ **収束兆候なし** → kill" は満たさない
  (収束兆候 active)。
- **計画**:
  1. **8h envelope 厳守**: 23:19 JST までに training を kill (checkpoint で停止)。
  2. 直近 checkpoint (例 step-2000 or step-2500) を採用して Phase 3 へ。
  3. trainer の save_steps=500 でも actual save は eval 後なので、checkpoint-N
     が存在するのは「step N+α 完了時点」。
- **トレードオフ**:
  - 4000 steps を完走しないと max_steps と LR schedule の整合性が失われ、
    LR は cosine decay schedule で訓練終了に向けて減衰する想定が崩れる
    (step 2000 時点では LR がまだ peak の 50% 程度残っている可能性)。
  - しかし step 500 時点で loss 1.8 まで下がっており、step 2000 時点では
    さらに refine された adapter が得られると期待できる。Phase E A-6 で
    full Tier B 7500-turn 評価する時に十分な signal が出るかは verdict 待ち。
- **代替案 (REJECT 時)**: max_steps=2000 + LR schedule を切り直して
  別 PR で再 training を検討。本 PR で確定したことは "current configuration
  で 8h envelope 内に 4000 steps 完走不可" という事実のみ。
- **実績** (2026-05-16 07:38 JST 完了): elapsed 16h19m で **全 4000 steps 完走**。
  SIGINT (23:22) は eval phase 中で trainer に届かず無視された。
  Phase 3-4 は最終 adapter (root: byte-identical to checkpoint-4000) を使用。
  - train_loss = 1.316、**eval_loss = 0.180** (step 500=0.191 → step 2000=0.166 → final=0.180、
    軽微な over-fit 兆候はあるが eval_loss 自体は健全)
  - peak_vram = 10.62GB (12GB safety margin 内)

## D-1: DA-14 ADOPT/REJECT verdict

- **判断日時**: 2026-05-16 07:58 JST
- **artefact**: `.steering/20260515-m9-c-adopt-retrain-v2-verdict/da14-verdict-v2-kant.json`
- **comparator**: no-LoRA SGLang baseline (DA-14 authoritative、
  `.steering/20260514-m9-c-adopt-pilot-multiturn/` 由来)

- **per-axis 数値** (vs no-LoRA SGLang baseline、各 n=6 windows):
  - **Axis 1 (Vendi semantic Cohen's d ≤ -0.5、CI upper < 0)**: **FAIL**
    - v2 mean = 33.1829, no-LoRA mean = 33.3109, diff = -0.1280
    - Cohen's d = **-0.1788** (target ≤ -0.5、correct direction but insufficient magnitude)
    - diff 95% CI = [-0.8540, +0.6212] (CI crosses zero → not significant)
  - **Axis 2 (Burrows reduction ≥ 5%、CI lower > 0)**: **FAIL**
    - v2 mean = 114.6078, no-LoRA mean = 115.1009
    - reduction = **+0.428%** (target ≥ 5%、correct direction but tiny)
    - reduction 95% CI = [-1.874%, +2.469%] (CI crosses zero)
  - **Axis 3 (ICC(A,1) ≥ 0.55、CI lower ≥ 0.50)**: **PASS**
    - v2 ICC(A,1) = **0.9129**, CI [0.8808, 0.9692]
    - no-LoRA ICC(A,1) = 0.9061 (両方とも threshold を大きく超過)
  - **Axis 4 (throughput ≥ 70%)**: **PASS**
    - v2 rate = 0.82 focal/s, no-LoRA = 0.83 focal/s, **98.8%** of baseline

- **quorum 判定** (kant 2-of-3 primary):
  - primary axes (Vendi/Burrows/ICC): **1 / 3** (ICC のみ PASS)
  - 2-of-3 quorum 未達 → 不合格

- **verdict**: **REJECT**

- **directional improvement vs prior LoRA (DA-11 single-turn r=8、PR #165)**:
  - Vendi: 34.7010 → 33.1829 (-1.52、prior +1.39 wrong → v2 -0.13 correct、
    **方向は反転**したが magnitude 不足)
  - Burrows: 113.7227 → 114.6078 (+0.89、prior -1.38 → v2 -0.49、わずかに後退)
  - DA-14 thresholds は absolute magnitude を要求するため、reversal だけでは不十分

- **next**: DA-15 ADR 起票で以下のいずれか (or 組合せ) を escalate:
  1. **Vendi kernel swap**: sentence-transformers/all-mpnet-base-v2 が persona
     shift に対し過剰に invariant な可能性。Ada-002 / multilingual-e5 / RoBERTa
     等の別 embedding kernel を試す
  2. **Candidate C targeted hybrid**: de+en weighted mass 0.489 (target 0.60)
     を補強するため、ドイツ語哲学語彙を重視した合成 monolog の追加採取
  3. **Longer training / rank拡大**: max_steps を 4000 → 8000、または rank=16
     で signal magnitude 増大を試す (今回は GPU 16h で 4000 steps、rank=16 では
     32h 想定)

- **HIGH-3 post-hoc threshold movement 禁止**: DA-14 thresholds を緩めて
  ADOPT に書き換える行為は禁止。DA-15 ADR が正路。

- **matrix script gap note**: `scripts/m9-c-adopt/da1_matrix_multiturn.py` は
  matched HISTORICAL Ollama baseline と比較するため (DA-11 era logic)、
  output の `scenario II` 判定は DA-14 criteria と一致しない。本 D-1 では
  no-LoRA SGLang baseline で再計算した DA-14 verdict を採用。matrix script
  の更新は別 PR (DA-15 ADR 起票時に同梱推奨)。
