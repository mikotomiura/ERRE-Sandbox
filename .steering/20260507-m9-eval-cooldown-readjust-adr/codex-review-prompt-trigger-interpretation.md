# Codex Independent Review Prompt — m9-eval ME-9 trigger interpretation (run1 cell 100/101)

> **target model**: `gpt-5.5 xhigh`
> **mode**: read-only independent review、trigger 解釈 fact-check
> **scope**: rate basis 不整合 + cooldown 過小判定の妥当性 + 必要な follow-up
> **output 期待**: 解釈 A/B/C のいずれが正しいか + 4 specific questions 回答

---

## 0. Repository orientation

ERRE-Sandbox (`/Users/johnd/ERRE-Sand Box`)、main = `60e1f6e` (PR #141 merged)。
本タスク (`20260507-m9-eval-cooldown-readjust-adr`) は M9-eval Phase 2 run1
calibration 実行中に **ME-9 trigger** が発火し、その解釈に rate basis 不整合
が浮上したため、Claude 単独判断のバイアスを避ける Codex 9 回目 review。

## 1. 背景と empirical data

### 1.1 PR #141 で merged された v2 prompt

`.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md` の §Phase A
で **kant only × 5 wall sequential** (run_idx=100..104、wall=120/240/360/480/600 min)
を G-GEAR で実行開始。同 prompt の §ブロッカー予測 B-1 で:

> run1 で observed focal/min が 0.92 (≤55/h) または ≥1.33 (≥80/h) を観測した
> 場合 → **C 案 (Codex review/child ADR 起票)**

との trigger zone を明記。

### 1.2 ADR (権威 source) の trigger zone wording

`.steering/20260430-m9-eval-system/decisions.md:646`:

> run1 calibration で 120-min 単位 focal/hour rate が 65 を大きく外れる
> (例: ≤55 / ≥80) → COOLDOWN_TICKS_EVAL や cognition_period の再調整 ADR
> 起票 (本 ADR の child)

**注意**: ADR の 65/h 起点 = **run0 incident で観測された 3-parallel rate** に
由来 (`.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.md`
の Codex H1 計算 `65 × 8 × 0.85 = 442` で 500 未達と算出した時の根拠)。
しかし「run1 calibration で」と前置きしている → rate basis (parallel vs
single) が **明示的に区別されていない ambiguity**。

### 1.3 observed empirical (今回の run1 calibration)

| cell | wall (min) | focal | rate (/min) | rate (/h) | sidecar status |
|---|---|---|---|---|---|
| run100 | 120 | 195 | **1.625** | **97.5** | partial / wall_timeout / drain_completed=true |
| run101 | 240 | 383 | **1.596** | **95.75** | partial / wall_timeout / drain_completed=true |

両 cell とも `focal_target=2000` (= turn_count) なので early stop ではなく
wall-limited stop 確実。`runtime_drain_timeout=false` なので drain 健全。

### 1.4 historical empirical baselines

| context | persona | wall (min) | focal | rate (/min) | rate (/h) |
|---|---|---|---|---|---|
| pilot single (P3a-fix-v2、`data/eval/pilot/_summary.json`) | kant | 16 | 30 | **1.875** | 112.5 |
| pilot single | nietzsche | 16 | 30 | 1.875 | 112.5 |
| pilot single | rikyu | 16 | 30 | 1.875 | 112.5 |
| run0 incident (3-parallel、`blockers.md` active incident) | kant | 360 | 381 | 1.058 | 63.5 |
| run0 incident | nietzsche | 360 | 390 | 1.083 | 65.0 |
| run0 incident | rikyu | 360 | 399 | 1.108 | 66.5 |

### 1.5 重要: rate の wall-duration 依存性が浮上

```
pilot single  (wall=16  min): 1.875 /min
run100 single (wall=120 min): 1.625 /min  (-13.3% from pilot)
run101 single (wall=240 min): 1.596 /min  (-15.0% from pilot、-1.8% from run100)
```

**single rate が wall duration に対して非単調ではないが、明らかに減衰**。
memory pressure 累積 (sqlite memory store growth、cognition reflection
buffer growth) が cognition tick latency を伸ばしている可能性大。

contention factor の従来仮定:
```
contention_factor (v2 prompt 仮定) = pilot_single (1.875) / run0_parallel_mean (1.083) = 1.731
```

しかし wall duration を揃えていない比較なので **mixed effect**:
- 効果 1: 3-parallel contention (Ollama queue + GPU memory)
- 効果 2: wall duration (memory pressure 累積)

run100 (120 min single) で 1.625 → 仮に同 wall で 3-parallel すると
1.625 / 1.731 = 0.939 /min ≈ 56.3/h。run0 (360 min × 3-parallel) は 1.083/min
≈ 65/h。これらの差 (0.939 vs 1.083) は contention_factor の ambiguity の幅。

## 2. 3 つの可能な解釈

### 解釈 A: ADR の 65/h は parallel rate basis、single calibration に直接 apply は設計欠陥

- ADR の 65/h は **run0 (3-parallel × 360 min)** で観測された値そのもの
- run1 calibration が single なので、observed 1.6/min を直接 65/h trigger に
  applied すべきではなかった
- 1.731× contention 換算で parallel rate ≈ 0.92-0.94/min ≈ 55-56/h →
  trigger zone (≤55) **下限ぎりぎりに該当**するが、cooldown 過剰の証拠ではない
- **Action**: v2 prompt の trigger zone wording を rate basis 明示で修正、
  run1 resume (run_idx=102/103/104 を採取して contention_factor 補正)

### 解釈 B: ADR の 65/h は single calibration 用、96/h 観測は cooldown 過小

- ADR は「**run1 calibration で**」と前置き、本来 single rate を意味
- 96/h 観測は cooldown が過小 (turn 間の time が短すぎ、memory growth 不十分)
  → focal/min が高めに出る
- **Action**: child ADR (`m9-eval-cooldown-readjust-adr`) 起票、
  `COOLDOWN_TICKS_EVAL=5` を 7-10 等に拡張、run1 やり直し

### 解釈 C: ADR の rate basis が ambiguous spec、wording 不明確に起因した擬陽性

- ADR / v2 prompt とも rate basis (single vs parallel) を明示していない
- empirical では single 1.6/min が parallel 補正で run0 と整合
- **Action**: ADR 文言修正 + v2 prompt trigger zone wording 明示
  (例: "single calibration では 1.62 ± 0.20 /min が default zone"、
  "3-parallel production では 0.92 ± 0.15 /min が default zone")、
  run1 resume

## 3. 投げる 4 specific questions

### Q1. 1.731× contention factor の wall duration confound
pilot single (16 min) と run0 parallel (360 min) を比較した contention_factor
は wall duration を揃えていない。run100 single (120 min) で 1.625/min を
基準にすると、parallel 換算は 1.625 / 1.731 = **0.938/min ≈ 56/h**。これは
run0 の 65/h と 13% 乖離。

**選択肢**:
- (A) wall duration を揃えた contention_factor は **約 1.50** (= 1.625 / 1.083)
- (B) 1.731 は pilot 16 min vs run0 360 min の mixed effect、本来は wall=120
  pair で再校正すべき
- (C) memory pressure non-linearity が大きく、線形補正自体が破綻

run2-4 wall budget 計算で contention_factor をどの値で fix すべきか。

### Q2. wall duration 効果の関数形
single rate decay:
- 16 min: 1.875
- 120 min: 1.625 (-13.3%)
- 240 min: 1.596 (-15.0%)

**選択肢**:
- (A) linear decay (`rate = 1.875 - 0.0024 × wall_min`) → 600 min で 0.43/min
  は明らかに過剰
- (B) exponential approach to asymptote (`rate = a + (1.875 - a) × exp(-wall/τ)`)
  → fit (a≈1.55, τ≈100) なら 600 min で ≈ 1.55/min
- (C) linear in 1/wall (`rate = a + b/wall`) → fit で 600 min で ≈ 1.58/min
- (D) memory pressure 累積で predictor 不能、empirical ベースのみ (要 600 min sample)

run2-4 (3-parallel × 600 min) の予測 rate はどれが妥当か。

### Q3. cooldown 再調整の必要性
解釈 B が正しいなら `COOLDOWN_TICKS_EVAL=5` を増やす必要。しかし pilot
(`P3a-fix-v2 cooldown=5`) で 1.875/min が観測されており、本 calibration
(同 cooldown=5) で 1.6/min に低下したのは **wall duration 効果** で説明可能。

**選択肢**:
- (A) cooldown 再調整不要 (解釈 A or C)、wall duration 効果のみ
- (B) cooldown 再調整必要 (解釈 B)、wall=120 で 1.625 は pilot 1.875 から
  -13% 低下、これは memory growth でなく cooldown 不足
- (C) data 不足、run_idx=102 (wall=360) を採取して cooldown vs wall 効果を
  分離

### Q4. ADR / v2 prompt wording 修正の必要性
解釈 A/B/C いずれでも ADR の trigger zone wording に rate basis ambiguity が
残る。本 PR (m9-eval-cooldown-readjust-adr) で:

**選択肢**:
- (A) ADR (`decisions.md` ME-9) を amendment block で rate basis 明示 +
  v2 prompt §ブロッカー予測 B-1 を refresh
- (B) child ADR (cooldown 再調整) で rate basis を redefine、v2 prompt は
  v3 を別 PR で起票
- (C) wording 修正のみで本 PR 完結 (cooldown 再調整は別タスク defer)

## 4. その他、独立 review してほしい点

- 6 個の sidecar (run100/101 actual + pilot 3 baseline + run0 3 incident) を
  比較して、`focal_per_min(wall, parallel?)` の 2 次元関数を fit できるか
- `_RUNTIME_DRAIN_GRACE_S = 60.0` (PR #140 で raise) が今回の wall=240 cell で
  drain_completed=true を確保できているか確認 (sidecar の field 値は true、
  問題なし)
- v2 prompt §Phase A.4 の期待値 table (1.87/min × wall = focal) は pilot
  baseline がそのまま 600 min まで線形と仮定。これは Q2 の関数形検討で見直し
  必要
- run100/101 の `focal_per_min` 差 (1.625 → 1.596 = -1.8%) は memory growth
  の signal として検出力あるか、あるいは cell-to-cell variance に埋もれる
  程度か

## 5. 守ってほしい制約

- **read-only**: 編集なし、テスト実行なし
- **scope 厳守**: 本タスクは trigger 解釈 fact-check + necessary follow-up
  判定。CLI コード改修は scope 外
- ADR 文言の amendment は提案レベルまで、実際の文書修正は本 review 後
- 出力は **markdown 単一ファイル**、Verdict + interpretation 採用 + Q1-Q4
  回答 + その他 review 点

## 6. 報告フォーマット (必須)

```markdown
## Verdict
- 解釈 [A / B / C / hybrid] を推奨
- 一文で判定理由

## Interpretation analysis
- 解釈 A の妥当性 + 反証
- 解釈 B の妥当性 + 反証
- 解釈 C の妥当性 + 反証
- 採用解釈 + その根拠

## 4 questions への回答
### Q1: [選択肢 + 理由]
### Q2: [選択肢 + 関数形提案]
### Q3: [選択肢 + 必要なら追加 sample 提案]
### Q4: [選択肢 + ADR/v2 prompt 修正方針]

## HIGH (本タスクで必反映)
### H1. ...

## MEDIUM (採否は実装側判断、decisions.md 記録)
### M1. ...

## LOW (持ち越し可、blockers.md 記録)
### L1. ...

## Out-of-scope notes
```
