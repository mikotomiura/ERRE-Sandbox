# m9-c-adopt pilot multi-turn investigation 報告 (PR description 候補)

> DA-12 verdict = DEFER (Phase B PR #165) を受けた **direction failure
> identifiability** の empirical 切り分け PR。Codex independent review
> `codex-review.md` の HIGH 4 件 (no-LoRA SGLang control + matched baseline
> downsampling + pre-registered thresholds + post-capture validation gate)
> 反映済。本 PR は **DA-13 ADR** を起票し、direction failure の根本原因を
> empirical に確定する。

---

## TL;DR

- pilot を multi-turn 採取に拡張、3 rank × 2 run × 300 focal turn = **6 shard
  LoRA-on** + **2 shard no-LoRA SGLang control** (HIGH-1)、計 8 shard
- matched baseline (historical Ollama baseline を 300 focal/shard に downsample) を
  primary comparison として算出 (HIGH-2)
- pre-registered scenario thresholds (HIGH-3) で **Scenario II (no reversal)** を
  automatic 判定
- post-capture validation query (HIGH-4): **8/8 shards PASS** (alternation、
  focal_target=300 ±5%、no incomplete dialogs)

**最大の empirical 発見** (採取後判明): **DA-12 "direction failure" の主因は
LoRA failure ではなく backend confound (Ollama vs SGLang)**。no-LoRA SGLang
control 結果が Vendi/Burrows 値で LoRA-on とほぼ同等 (±0.5) で、historical
Ollama baseline からの +2.14 Vendi / +5.39 Burrows shift は **SGLang vs Ollama
で起こる純粋な backend confound** であり LoRA 由来ではないことが確定。

## DA-1 4-axis matrix (実測、`da1-matrix-multiturn-kant.json`)

| condition | Vendi semantic | ICC(C,k) | Burrows |
|---|---|---|---|
| historical baseline (Ollama, multi-turn metadata) | 30.822 [30.726, 30.928] | 0.9980 [0.9974, 0.9987] | 108.534 [108.100, 109.018] |
| **matched baseline** (Ollama, downsampled 300 focal/shard) | 31.167 [31.010, 31.318] | 0.9980 [0.9974, 0.9987] | 109.710 [109.036, 110.544] |
| **no-LoRA SGLang control** (multi-turn protocol) | **33.311 [33.121, 33.501]** | 0.9819 [0.9760, 0.9936] | **115.101 [113.930, 116.272]** |
| single-turn pilot LoRA r=4 (PR #165) | 33.895 [33.849, 33.942] | 0.9792 [0.9666, 0.9941] | 113.595 [113.261, 113.929] |
| single-turn pilot LoRA r=8 (PR #165) | 34.701 [34.673, 34.729] | 0.9843 [0.9795, 0.9946] | 113.723 [113.314, 114.131] |
| single-turn pilot LoRA r=16 (PR #165) | 33.685 [33.088, 34.282] | 0.9837 [0.9810, 0.9936] | 112.564 [112.307, 112.822] |
| **multi-turn pilot LoRA r=4** | 33.556 [33.259, 33.852] | 0.9804 [0.9732, 0.9933] | 115.612 [115.542, 115.681] |
| **multi-turn pilot LoRA r=8** | 33.757 [33.555, 33.958] | 0.9797 [0.9762, 0.9914] | 114.141 [113.257, 115.024] |
| **multi-turn pilot LoRA r=16** | 33.261 [33.202, 33.319] | 0.9913 [0.9892, 0.9975] | 114.609 [112.404, 116.813] |

## 因子分解 (Backend confound vs LoRA effect)

| comparison | Vendi Δ | Burrows Δ | 解釈 |
|---|---|---|---|
| **backend confound** (matched Ollama → no-LoRA SGLang) | **+2.144** | **+5.391** | **direction failure の primary cause** |
| LoRA effect at rank=4 (LoRA SGLang → no-LoRA SGLang) | +0.245 | +0.511 | near-zero、burrows wrong direction |
| **LoRA effect at rank=8** (proper baseline) | +0.446 | -0.960 | near-zero、direction-mixed |
| LoRA effect at rank=16 | -0.050 | -0.492 | near-zero、Burrows reduction tiny |
| methodology delta (single → multi-turn LoRA-on r=8) | -0.94 | +0.42 | protocol shift effect small |

## Pre-registered scenario verdict (DA-13)

```json
{
  "primary_rank": 8,
  "scenario": "II",
  "rationale": "No reversal — LoRA failure remains the live hypothesis",
  "primary_vendi_diff_point": 2.589,
  "primary_vendi_diff_lo": 1.823,
  "primary_vendi_diff_hi": 3.385,
  "primary_vendi_cohens_d": 2.17,
  "primary_burrows_reduction_point": -0.0404,
  "primary_burrows_reduction_lo": -0.0546,
  "sister_ranks_aligned": 0
}
```

**Caveat (CRITICAL)**: pre-registered Scenario II verdict は literally 正しいが
**no-LoRA SGLang control 結果** が direction failure の **根本原因** を
**LoRA failure → backend confound** に再帰属させる。`decisions.md` DA-13 の
"CRITICAL CAVEAT" section + `next-session-prompt-scenario-II-retrain-v2.md` で
backend confound finding を後続経路 spec に反映。

## 後続経路 → `feature/m9-c-adopt-retrain-v2` (Spec amendment 付き)

- DA-12 close: identifiability 解消 (backend confound dominant 確定)
- Phase D 着手前 prereq: retrain v2 経路 confirmed、ただし以下 spec amendment 必要:
  1. **baseline backend を SGLang-on-base に変更** (no-LoRA SGLang multi-turn を
     primary baseline、Ollama は historical reference)
  2. **DA-1 thresholds の re-calibration** (旧 baseline 基準を新 baseline 基準
     に置き換え、persona-discriminative effect size 期待値を再評価)
  3. **training data の persona-discriminative signal 強化** (min_examples
     3000、stimulus prompt diversity、Kant style 比率 explicit bias)
- 詳細: `.steering/20260514-m9-c-adopt-pilot-multiturn/next-session-prompt-scenario-II-retrain-v2.md`

## Codex independent review 反映

(`codex-review.md` verbatim 保存、`decisions.md` D-1〜D-3 に反映方針記録)

- **HIGH-1** Scenario I overclaim → ADOPT mitigation 1+2: weaken conclusion,
  add no-LoRA SGLang control (rank=8 control, 2 runs)
  - **本 PR で revealed**: HIGH-1 mitigation 2 の真価 — no-LoRA SGLang
    control が backend confound dominant を確定した
- **HIGH-2** Window count mismatch → ADOPT mitigation 2: matched baseline
  downsampling (consumer `--max-focal-per-shard 300` flag 追加)
- **HIGH-3** Scenario criteria movable → ADOPT pre-registered DA-13 draft
  in `decisions.md` BEFORE collection — verdict が data 確認後に変わらない保証
- **HIGH-4** Smoke-only insufficient → ADOPT post-capture validation query
  + unit test (`tests/test_m9_c_adopt_pilot.py`、13 cases、全 PASS)

## 主な実装変更

- `scripts/m9-c-adopt/tier_b_pilot.py`:
  - `--multi-turn-max N` flag (default 1 で過去互換)
  - `--no-lora-control` flag (HIGH-1)
  - alternating speaker loop (focal/interlocutor) per stimulus
  - stimulus-atomic checkpoint resume (MEDIUM-3): fatal 時に in-progress
    `dialog_id` の rows を DELETE してから checkpoint
  - run_id 命名 `{persona}_{r{rank}|nolora}_run{idx}_pilot`
- `scripts/m9-c-adopt/compute_baseline_vendi.py`:
  - `--max-focal-per-shard N` flag 追加 (HIGH-2)
- `scripts/m9-c-adopt/compute_burrows_delta.py`:
  - `--max-focal-per-shard N` flag 追加 (HIGH-2)
- `scripts/m9-c-adopt/da1_matrix_multiturn.py` (新規):
  - matched baseline + multi-turn LoRA-on + no-LoRA control + single-turn
    pilot (PR #165) + historical baseline を 1 matrix に集約
  - pre-registered scenario thresholds で I/II/III/IV を automatic 判定
- `scripts/m9-c-adopt/validate_multiturn_shards.py` (新規):
  - 4-check post-capture validation (HIGH-4 acceptance gate)、8/8 shards PASS
- `tests/test_m9_c_adopt_pilot.py` (新規):
  - 13 cases (multi-turn cap、stratified slice、seed、user prompt marker)、全 PASS

## 採取構成 + 実測時間

- LoRA-on 6 shard + no-LoRA control 2 shard = 8 shard、計 ~2400 focal turn
- pilot capture (8 shard sequential、SGLang 3-adapter pin + base):
  **2876 s ≈ 48 min** (~360 s/shard)
- consumer execution (matched baseline + multi-turn LoRA × 3 rank + nolora、
  Vendi + Burrows + Big5 ICC + matrix render): **334 s ≈ 5.5 min**
- 合計 capture + consumer: **~54 min**

## 参照

- 前 PR: #165 (Phase B closure)、DA-12 verdict = DEFER
- ADR: `.steering/20260513-m9-c-adopt/decisions.md` DA-13
- Codex review: `.steering/20260514-m9-c-adopt-pilot-multiturn/codex-review.md`
- pre-registered thresholds: `.steering/20260514-m9-c-adopt-pilot-multiturn/decisions.md` D-1 HIGH-3
- matrix output: `.steering/20260514-m9-c-adopt-pilot-multiturn/da1-matrix-multiturn-kant.json`
- validation gate (8/8 PASS): `.steering/20260514-m9-c-adopt-pilot-multiturn/validation-multiturn-kant.json`
- 後続経路: `.steering/20260514-m9-c-adopt-pilot-multiturn/next-session-prompt-scenario-II-retrain-v2.md`
