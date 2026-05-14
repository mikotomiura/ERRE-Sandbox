# Phase B 報告 — m9-c-adopt rank sweep on kant (final, 2026-05-14)

> Phase B 第 1〜4 セッション完了後の **PR description 候補 + 最終評価**.
> DA-12 (decisions.md) と整合。`data/lora/m9-c-adopt/kant_r{X}_real/`
> への production placement は **DEFER** (Phase E A-6 multi-turn full
> Tier B で再評価)。

---

## TL;DR

- Phase B 第 1〜4 セッションで rank ∈ {4, 8, 16} の **training (peak_vram
  10.51-10.63 GB) + 採取 + manifest backfill** を完遂、3 rank × 2 run
  × 300 turn = 1800 turn pilot を採取。
- DA-1 4 軸 intersection で final 採用 rank を確定する scope だったが、
  **2-of-4 軸のみ PASS (ICC + throughput)、Vendi semantic + Burrows Δ
  は全 rank で direction failure** (LoRA-on が baseline より値が高い、
  DA-1 hypothesis "LoRA-on < no-LoRA" に逆方向)。
- direction failure の原因として **pilot single-turn vs baseline
  multi-turn の方法論 confound** と **LoRA が IPIP self-report neutral
  midpoint を有意に shift しない** の 2 因子が identifiability 不能
  (DA-12 hot decision)。
- DA-1 verdict = **DEFER**: production 採用しない、provisional rank=8
  carry-over、tail-sweep rank=32 NOT fire、DA-9 retrain v2 path 開放
  + Phase D 着手前 prereq 化。

## DA-1 4-axis matrix (実測)

| rank | Vendi semantic | ICC(C,k) | Burrows Δ | throughput tok/s | axes PASS |
|---|---|---|---|---|---|
| no-LoRA baseline | 30.822 [30.726, 30.928] | 0.9980 [0.9974, 0.9987] | 108.534 [108.10, 109.02] | K-β 34.64 / threshold 24.25 | — |
| 4 | 33.895 [33.85, 33.94] | 0.9792 [0.967, 0.994] | 113.595 [113.26, 113.93] | 33.82 (PASS) | **2/4** (V:FAIL B:FAIL) |
| 8 | 34.701 [34.67, 34.73] | 0.9843 [0.980, 0.995] | 113.723 [113.31, 114.13] | 33.77 (PASS) | **2/4** (V:FAIL B:FAIL) |
| 16 | 33.685 [33.09, 34.28] | 0.9837 [0.981, 0.994] | 112.564 [112.31, 112.82] | 33.72 (PASS) | **2/4** (V:FAIL B:FAIL) |

artefact: `da1-matrix-kant.json` (root for full per-rank tables)

### Per-rank diagnostic effect sizes

| rank | Vendi Cohen's d (LoRA-on vs baseline) | Burrows reduction |
|---|---|---|
| 4 | +2.366 (positive = wrong direction) | -4.66% (negative = wrong direction) |
| 8 | +2.995 | -4.78% |
| 16 | +2.131 | -3.71% |

DA-1 axis 1 wants d < 0 (LoRA-on Vendi < baseline Vendi). All ranks d > 0.
DA-1 axis 3 wants reduction ≥ +10%. All ranks reduction < 0 (i.e. Burrows
distance increased rather than decreased).

## 採用 rank 確定

**確定なし** (DA-12 ADR DEFER)。`data/lora/m9-c-adopt/kant_r{X}_real/`
への production placement は本 PR scope 外。archive は全 rank 揃い済:

| rank | archive path | sha256_adapter_model | training_git_sha |
|---|---|---|---|
| 4 | `data/lora/m9-c-adopt/archive/rank_4/kant/` | `b89a248695394a8d17c606d6509d46c268ba4e0efbb04641555af9a21e05f78d` | `92786f28383c5e45336bc59170717488f45f2185` |
| 8 | `data/lora/m9-c-adopt/archive/rank_8/kant/` | `cd8c6e5f...` (PR #163 K-β 由来 verbatim 一致) | (K-β baseline、PR #163 で確定) |
| 16 | `data/lora/m9-c-adopt/archive/rank_16/kant/` | `9532b438f34da8e87ebb4a71707da4ab22c4ed790959c177c7ea8fc373c0ac38` | `92786f28383c5e45336bc59170717488f45f2185` |

provisional carry-over (Phase E A-6 primary 評価対象): **rank=8** (K-β
heritage + pilot で best ICC stability + smaller rank preferred)。

## VRAM 実測 peak

| 局面 | rank=4 | rank=8 | rank=16 |
|---|---|---|---|
| training metadata `peak_vram_bytes` | 10.51 GB | (PR #163 計測値 10.55 GB) | 10.14 GB |
| training nvidia-smi sustained | ~13.5 GB | (PR #163) | ~14.0 GB |
| serving (SGLang fp8 multi-pin 3 adapter) | 9.09 GB (model) + 0.14 GB KV + adapter ~80 MB ×3 | 同左 | 同左 |
| ICC consumer 時 SGLang max | 10.5 GB (1 adapter active 経由 multi-pin) | 同左 | 同左 |

S-3 (training VRAM watch) は rank=16 plateau ~14016 MiB sustained で
threshold を 14000 → 14300 MiB に amendment 済 (Phase B 第 2 セッション
incident)。tail-sweep rank=32 fire なしのため S-3 再 amendment 不要。

## blockers.md 連動 (本 PR で更新)

- **S-2** (CS-1 `--max-lora-rank 8 → 16` amendment): 解消 (Phase A
  DA-1 amendment + DB8 runbook §2 update 済)
- **S-3** (training VRAM threshold): partial — rank=16 amendment 済
  (14000 → 14300 MiB)。rank=32 fire なし、tail-sweep 再 amendment 不要
- **H-1** (Tier B persona-discriminative): **partial verify**
  (ICC + throughput PASS、Vendi + Burrows direction failure、DA-12
  DEFER)。Phase E A-6 で final verdict
- **H-2** (rikyu Japanese Burrows N/A): unchanged (DA-8 named limitation)

## Phase D 着手前 dependency

DA-12 に従い、以下の順で別 PR が prereq:

1. **feature/m9-c-adopt-retrain-v2** (別 PR): kant の min_examples
   1000 → 3000、stimulus prompt diversity 改善、rank=8 固定再 training
2. **Phase E A-6** (別 PR): multi-turn full 7500-turn Tier B 採取 + 再
   DA-1 4 軸 intersection 評価
3. methodology confound 切り分けが先行で必要なら: pilot multi-turn 採取の
   小 PR (DA-12 re-open 第 2 経路)
4. Phase D (`MultiBackendChatClient` 実装 + live path 統合): 上記 1-3 の
   いずれかが ADOPT 判定 完遂後

## 第 4 セッション完了サマリ (本 PR scope)

### 新規実装 (本 PR)

- `scripts/m9-c-adopt/compute_big5_icc.py`: DuckDB shard × IPIP-50 ×
  LLM-backed responder (Ollama / SGLang switchable) → `compute_big5_icc` →
  hierarchical bootstrap CI。T=0.7 で per-call seed mutation 経由 admin-
  level stochasticity を導入 (T=0 では responder deterministic で ICC が
  trivially 1.0 になる artifact を回避、judgment は `decisions.md` DA-12
  内に記録済 hot decision)
- `scripts/m9-c-adopt/compute_burrows_delta.py`: Option A 言語自動判定
  経路 (langdetect deterministic seed=0、`--lang-confidence 0.85`)、
  de utterances のみ filter、en/ja は named limitation で drop
- `scripts/m9-c-adopt/da1_matrix.py`: 4 軸 intersection matrix renderer +
  PASS/FAIL judgment + Cohen's d diagnostic

### 採取 / 計算

- `tier-b-baseline-kant-vendi-semantic.json`: 5 shards × 5 windows = 25
  total windows、point=30.822 [30.726, 30.928] (MPNet cosine kernel)
- `tier-b-baseline-kant-icc.json`: Ollama qwen3:8b @ T=0.7 think=false、
  ICC(C,k)=0.998 [0.997, 0.999]、ICC(A,1)=0.953 [0.940, 0.969]
- `tier-b-baseline-kant-burrows.json`: 5 shards、de_fraction=0.369、
  point=108.534 [108.10, 109.02]
- per-rank pilot Vendi/ICC/Burrows artefacts × rank ∈ {4, 8, 16}: all in
  `.steering/20260513-m9-c-adopt/tier-b-{pilot,icc}-kant-r{X}-*.json`
- `da1-matrix-kant.json`: 全 input + 全 axes PASS/FAIL judgment 集約

### dependency 追加

- `langdetect` (pure Python、Windows native venv にのみ install、
  `[eval]` extras 追加検討は別 PR で)
- `sentence-transformers` を Windows native venv に install (`uv pip install`
  経由)。WSL2 venv は未 install、Mac master 経由でも可

### incident / 教訓

- **WSL2 → Windows-native Ollama 不通** (`reference_wsl2_ollama_unreachable.md`):
  Ollama responder は Windows native Python から走らせる必要があった。
  ICC consumer は SGLang (WSL2) / Ollama (Windows native) の 2 経路を
  switch する設計だが、Ollama 経路は Windows-side execute pattern に切替済。
- **T=0 ICC trivial 1.0 artifact**: 初期実装で temperature=0.0 で
  baseline ICC を走らせ、全 window で per-dim sd=0.0 → ICC=1.0 を観察。
  Salecha 2024 anti-demand-characteristics は context conditioning のみ
  指定で sampling は規定なし。本 PR では T=0.7 (kant persona default
  sampling と整合) + per-call seed mutation を採用して admin-level
  stochasticity を導入。
- **pilot single-turn methodological confound**: Phase B 第 3 セッション
  時点で lexical Vendi 直接観察済の anomaly (LoRA-on > baseline) が、
  semantic Vendi でも Burrows でも同じ direction で再現。DA-12 hot
  decision で「LoRA failure 単独 vs methodology confound 単独 vs 両者」
  を切り分け不能と認定し Phase E に持ち越し。

### scope narrowing と sequence

- Phase A 設計時の DA-1 採用基準 (4 軸 intersection、point + CI +
  direction の 3 条件 AND) は **そのまま維持** (DA-12 は timing
  narrowing であり criterion narrowing ではない、DA-11 と同 spirit)
- 本 PR は **Phase B pilot infrastructure + 全 metric 算出 + DA-12 verdict
  記録** で完結。production rank 採用は Phase E に持ち越し、Phase D は
  retrain v2 merge 後

## 参照

- ADR: `decisions.md` DA-1 / DA-8 / DA-9 / DA-11 / DA-12 (本 PR で追加)
- 結果: `.steering/20260513-m9-c-adopt/tier-b-*.json` + `da1-matrix-kant.json`
- 算出 scripts: `scripts/m9-c-adopt/compute_big5_icc.py` /
  `compute_burrows_delta.py` / `da1_matrix.py` (本 PR で新規) /
  `compute_baseline_vendi.py` / `tier_b_pilot.py` / `bench_per_rank.sh`
  (前 PR で新規)
- 設定: `pyproject.toml` (langdetect 追加検討は別 PR)
- DB8 runbook `--max-lora-rank 16` amendment 維持
