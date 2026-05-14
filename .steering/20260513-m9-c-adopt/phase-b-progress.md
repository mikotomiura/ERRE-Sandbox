# Phase B 進捗 — m9-c-adopt rank sweep on kant (FINAL, 2026-05-14)

> Phase A (PR #164 merged) → Phase B 第 1〜4 セッション完遂。本 file は
> Phase B closure summary。詳細は `phase-b-report.md` (PR description 候補)、
> ADR は `decisions.md` (DA-11 第 3 セッション narrowing + DA-12 第 4
> セッション verdict)。

---

## 最終状態 (2026-05-14 第 4 セッション完了時点、DA-12 verdict = DEFER)

| Step | 内容 | 状態 |
|---|---|---|
| Step 0 | pre-flight (branch + CS-1 amendment + manifest scaffold) | **完了** (`0246768`) |
| Step 1 | rank=4 training (kant、G-GEAR overnight) | **完了** sha256 `b89a248695...`、peak_vram 10.51 GB |
| Step 2 | rank=8 baseline re-confirm + manifest backfill | **完了** sha256 `cd8c6e5f...` (PR #163 K-β verbatim) |
| Step 3a | rank=4 archive + manifest | **完了** |
| Step 3b | rank=16 training | **完了** train_loss=0.1993、peak_vram_bytes 10.14 GB |
| Step 3c | rank=16 archive + manifest | **完了** sha256 `9532b438f3...` |
| Step 4 | 3 adapter multi-pin load + chat sanity | **完了** 3 rank で異なる出力 (adapter routing 確認) |
| Step 5a (narrowed) | Vendi lexical-5gram baseline | **完了** point=75.77 / CI=[75.19, 76.37] |
| Step 5a' (第 4) | Vendi **semantic** baseline (MPNet) | **完了** point=30.822 / CI=[30.73, 30.93] |
| Step 5b | SGLang re-launch + 3 adapter pinned | **完了** (第 3 + 第 4 セッション共通) |
| Step 5c | Tier B pilot 1800 turn 採取 | **完了** 6 shard |
| Step 5d (第 4) | per-rank Big5 ICC + Burrows + Vendi semantic | **完了** 3 metric × 3 rank、artefacts in `tier-b-*-kant-r{4,8,16}-*.json` |
| Step 5e (partial) | CS-7 4 trigger bench (rank=4/8/16 single_lora) | **完了**、no_lora は PR #163 K-β 値継続 |
| Step 5f (第 4) | DA-1 4 軸 intersection final | **完了 (verdict = DEFER)** 全 rank 2/4 axes PASS only (ICC + throughput)、Vendi + Burrows direction failure |
| Step 6 (第 4) | conditional rank=32 tail-sweep | **NOT fire** — direction failure は scaling では解消不能 (DA-12) |
| Step 7 (本 PR) | DA-12 ADR 起票 + phase-b-report 起票 + blockers/tasklist 更新 + commit/PR | **本セッション内で完遂** |

branch: `feature/m9-c-adopt-phase-b-rank-sweep` (origin push 済、本 PR の
本コミットを最後に Phase B closure)

---

## DA-1 4-axis matrix (実測)

| rank | Vendi semantic | ICC(C,k) | Burrows Δ | throughput | axes PASS |
|---|---|---|---|---|---|
| no-LoRA baseline | 30.822 [30.726, 30.928] | 0.9980 [0.9974, 0.9987] | 108.534 [108.10, 109.02] | K-β 34.64 / threshold 24.25 | — |
| 4 | 33.895 [33.85, 33.94] | 0.9792 [0.967, 0.994] | 113.595 [113.26, 113.93] | 33.82 (PASS) | **2/4** (V:FAIL B:FAIL) |
| 8 | 34.701 [34.67, 34.73] | 0.9843 [0.980, 0.995] | 113.723 [113.31, 114.13] | 33.77 (PASS) | **2/4** (V:FAIL B:FAIL) |
| 16 | 33.685 [33.09, 34.28] | 0.9837 [0.981, 0.994] | 112.564 [112.31, 112.82] | 33.72 (PASS) | **2/4** (V:FAIL B:FAIL) |

matrix artefact: `da1-matrix-kant.json`

## 採用 rank 確定

**確定なし** (DA-12 verdict = DEFER)。`data/lora/m9-c-adopt/kant_r{X}_real/`
への production placement は本 PR scope 外、archive (`data/lora/m9-c-adopt/
archive/rank_{4,8,16}/kant/`) のみ commit 済。Phase E A-6 multi-turn full
Tier B (別 PR、retrain v2 が prereq) で final verdict を確定する。

## 第 4 セッション完遂サマリ

### Step 5d (Big5 ICC consumer 実装) — 完遂

- `scripts/m9-c-adopt/compute_big5_icc.py` 新規 (DuckDB shard × IPIP-50 ×
  LLM-backed responder)
- Ollama (Windows native venv 経由) + SGLang (WSL2) 2 responder switch
- T=0 deterministic で trivial ICC=1.0 を観察 → T=0.7 + per-call seed
  mutation を導入 (`decisions.md` DA-12 hot decision に root cause + 修正
  明示)
- Big5 ICC baseline = ICC(C,k) 0.998 [0.997, 0.999]、per-rank LoRA-on
  ICC(C,k) 0.979〜0.984 (全 rank DA-1 axis 2 PASS)

### Burrows Δ Option A — 完遂

- `scripts/m9-c-adopt/compute_burrows_delta.py` 新規
- `langdetect` (pure Python、deterministic seed=0、confidence ≥ 0.85) で
  per-utterance routing、de のみ filter、en/ja は named limitation で drop
- de_fraction baseline 0.369 / pilot 0.49 (pilot は single-turn で German
  stimulus に対し German response する率が高い)
- baseline Burrows point = 108.534 [108.10, 109.02]、per-rank LoRA-on
  112.56〜113.72 (全 rank direction failure on DA-1 axis 3)

### semantic Vendi 再算出 — 完遂

- `compute_baseline_vendi.py --kernel semantic` で MPNet cosine kernel
- baseline point = 30.822 [30.726, 30.928]、per-rank LoRA-on 33.69〜34.70
  (全 rank direction failure on DA-1 axis 1、Cohen's d +2.13〜+3.00)
- 第 3 セッション lexical Vendi で観察済の direction failure を semantic
  でも再現 → kernel artifact ではなく pilot methodology または LoRA
  失敗の signal

### DA-1 final verdict — 完遂

- `scripts/m9-c-adopt/da1_matrix.py` 新規で 4 軸 intersection matrix +
  PASS/FAIL judgment + Cohen's d diagnostic
- 全 rank 2/4 axes PASS only (ICC + throughput)、Vendi + Burrows
  direction failure → DA-12 DEFER verdict

### DA-12 ADR 起票

`decisions.md` に DA-12 (Phase B 第 4 セッション DA-1 verdict = DEFER)
を追記。内容:
- pilot verdict = DEFER (production 採用なし、provisional rank=8 carry-over)
- tail-sweep rank=32 NOT fire (direction failure は scaling では解消不能)
- DA-9 retrain v2 path 開放 + Phase D 着手前 prereq 化
- direction failure の 2 因子 identifiability 不能 (pilot methodology
  confound + LoRA が IPIP self-report neutral midpoint を shift しない)

### dependency 追加 (本 PR)

- `langdetect` (Windows native venv のみ install、`[eval]` extras 追加
  検討は別 PR)
- `sentence-transformers` を Windows native venv に install (uv pip
  経由)。WSL2 venv は未 install

### 既知の落とし穴 amendment (本セッション追加)

- **WSL2 → Windows-native Ollama 不通**:
  `reference_wsl2_ollama_unreachable.md` 既知。Ollama responder は
  Windows-side `.venv/Scripts/python.exe` から走らせる必要
- **T=0 ICC trivial 1.0 artifact**: deterministic + no context conditioning
  では IPIP self-report が固定値、全 window で per-dim sd=0.0、ICC=1.0
  を取る。T=0.7 + per-call seed mutation で admin-level stochasticity
  を導入。kant persona default T と整合
- **SGLang VRAM 圧迫**: `--mem-fraction-static 0.85` + 3 LoRA adapter pin で
  VRAM ~15.8 GB peak (16.3 GB total、~500 MiB free)。本 session 内では
  問題なかったが、Phase E full Tier B で同時 inference が増える場合は
  `--mem-fraction-static 0.80` への amendment 検討

---

## blockers.md status (第 4 セッション完了時)

- **S-2** (CS-1 amendment): 解消済 (Phase A)
- **S-3** (training VRAM): partial (rank=16 amendment 済、rank=32 fire なし)
- **H-1** (Tier B persona-discriminative): partial verify (ICC + throughput
  PASS、Vendi + Burrows direction failure → Phase E A-6 へ持ち越し)
- **H-2** (rikyu Japanese Burrows N/A): unchanged
- **U-6** (pilot single-turn methodology confound): **新規 fire** (DA-12
  identifiability 不能)

---

## Phase D 着手前 dependency

DA-12 に従い以下の順で別 PR が prereq:

1. **feature/m9-c-adopt-retrain-v2** (別 PR): min_examples 1000 → 3000、
   stimulus prompt diversity 改善、rank=8 固定再 training
2. **Phase E A-6** (別 PR): multi-turn full 7500-turn Tier B 採取 + 再
   DA-1 4 軸 intersection 評価
3. methodology confound 切り分けの場合: pilot multi-turn 採取の小 PR
4. **Phase D** (`MultiBackendChatClient` 実装 + live path 統合): 上記
   1-3 のいずれかが ADOPT 判定 完遂後

## 関連ファイル

- 設計契約: `design-final.md` (HIGH 4 反映後)
- ADR: `decisions.md` (DA-1..DA-12)
- blockers: `blockers.md` (S-3 amendment + H-1 partial verify + U-6 新規)
- tasklist: `tasklist.md` (Phase B 全 step 完了 mark)
- 報告: `phase-b-report.md` (本 PR description 候補)
- consumer scripts: `scripts/m9-c-adopt/compute_big5_icc.py` /
  `compute_burrows_delta.py` / `da1_matrix.py` / `compute_baseline_vendi.py` /
  `tier_b_pilot.py` / `bench_per_rank.sh`
- DB8 runbook: `docs/runbooks/m9-c-adapter-swap-runbook.md` (§2
  `--max-lora-rank 16` amendment 維持)
- archive: `data/lora/m9-c-adopt/archive/rank_{4,8,16}/kant/{manifest.json,
  adapter_config.json,train_metadata.json}` (3 rank 揃い)
- pilot shards: `data/eval/m9-c-adopt-tier-b-pilot/kant_r{4,8,16}_run{0,1}_stim.duckdb` (6 shard)
- bench: `data/eval/m9-c-adopt-bench/single_lora-r{4,8,16}.jsonl`
