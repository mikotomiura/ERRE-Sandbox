# 重要な設計判断 — m9-eval ME-9 trigger 解釈タスク (旧称: cooldown-readjust-adr)

> **scope re-confirmation**: 本タスクのディレクトリ名は `20260507-m9-eval-
> cooldown-readjust-adr` (working title) だが、Codex 9 回目 review (Verdict:
> hybrid A/C) で **cooldown 再調整は不要** と確定したため、実際の scope は
> **ME-9 trigger basis 明示 (ADR amendment) + v2 prompt 擬陽性修正** に変更。
> ディレクトリ rename は git history を傷めるため避け、内容で明示。

## 判断 1: Verdict は hybrid A/C 採用 (Codex 9 回目 review、2026-05-07)

Codex `gpt-5.5 xhigh` review (`codex-review-trigger-interpretation.md` verbatim、
81,541 tok)。

### 解釈 A の妥当性 + 反証
- 妥当性: 強い。ADR の 65/h は run0 3-parallel 起点、run1 calibration は
  ADR 自身が "single" と明記 (decisions.md:586)、basis 混在
- 反証: 1.731× contention factor 自体が pilot 16 min vs run0 360 min の
  mixed effect、真値扱いは危険

### 解釈 B (cooldown 再調整) は **棄却**
- 文言上は B もあり得るが、empirical 1.625/1.596 min は v2 prompt expected
  table (1.87/min × wall) の **下限内** (-13% 〜 -15%)
- cooldown 過小なら focal/min が pilot 1.875 より **高い** はず、実際は低い
  → cooldown 過小の証拠ではなく、wall-duration 効果と prompt threshold
  擬陽性で説明可能

### 解釈 C の妥当性
- ADR と v2 prompt の rate basis (single vs parallel) が曖昧、文書内で矛盾
- single 期待値 (1.87/min ≈ 112/h) と trigger threshold (≤55/h, ≥80/h) を
  同じ scale で並べているのが擬陽性の構造的原因

### 採用: **C を採用、A を root-cause として記録、B は棄却**

## 判断 2: HIGH 3 件全反映 (Codex 2026-05-07)

### H1. ME-9 trigger の rate basis を分離 (single vs parallel-estimated)
- **採用**: ADR (`decisions.md` ME-9) に **Amendment 2026-05-07** ブロックを
  追記、rate basis 明示
- **変更内容**: 65/h は **3-parallel production rate basis** (run0 由来) と
  明記。single calibration では threshold ≠ 65/h。single rate を 1.5×-1.76×
  contention factor で parallel 換算した上で 65/h と比較する

### H2. v2 prompt B-1 の擬陽性 trigger
- **採用**: v2 prompt §ブロッカー予測 B-1 を refresh
- **変更内容**: 「observed focal/min ≤ 0.92 / ≥ 1.33」を削除し、以下に置換:
  - calibration phase (single rate basis): expected `~1.55-1.87/min`、
    range の外なら investigation
  - production phase (3-parallel rate basis): expected `~0.92-1.20/min`、
    ≤0.55-0.92 / ≥1.20-1.33 で trigger zone

### H3. run102 採取 (360 min single) を resume 必須
- **採用**: 本 PR merge 後、G-GEAR で run102 (wall=360 min single) を採取
- **変更内容**: v2 prompt §Phase A の resume 手順を追記、run102 で
  **run0 360 min 3-parallel と直接比較可能な single rate** を取得 →
  contention_factor を re-estimate

## 判断 3: MEDIUM 3 件の採否

### M1. v2 prompt §Phase A.4 期待値 table を saturation model に更新
- **採用**: linear `1.87/min × wall` は 600 min まで外挿で過剰
- **変更**: exponential asymptote `rate(wall) ≈ a + (1.87 - a) × exp(-wall/τ)`
  または `rate ≈ a + b/wall` で fit。3 点 (16/120/240 min) からは識別不能だが、
  どちらも **600 min single ≈ 1.55-1.59/min** で一致 → range で記述

### M2. 2D 関数 fit (wall × parallel) は現時点で不可
- **採用**: blockers.md に持ち越し
- **理由**: single sample = wall ∈ {16, 120, 240}、parallel sample = wall ∈
  {360} のみ。wall × parallel の interaction は run102 (single 360 min) +
  少なくとも 1 つの parallel × non-360 wall sample が必要

### M3. run100 → run101 の -1.8% rate decay は弱い signal
- **採用**: 単独では設計判断に使わない、run102/103/104 で trend 確認
- **変更**: blockers.md に「memory growth signal の検出力低、追加 sample 待ち」
  と記録

## 判断 4: LOW 1 件は無作為 (LOW のため defer 不要)

### L1. drain grace は今回問題なし
- run100/101 sidecar は drain_completed=true、runtime_drain_timeout=false
- `_RUNTIME_DRAIN_GRACE_S=60.0` は少なくとも wall=240 min では機能
- **記録のみ**: blockers.md W (監視中) に追加、wall=600 min で再確認

## Codex Q&A 簡易記録

| Q | Codex 回答 | 採用 |
|---|---|---|
| Q1 1.731× contention の妥当性 | B + provisional A、wall-aligned 再校正必要 | M2 反映 (run102 待ち) |
| Q2 wall-duration 関数形 | B/C hybrid、600 min single ≈ 1.55-1.59/min | M1 反映 (saturation model) |
| Q3 cooldown 再調整 | A、不要、wall-duration + prompt threshold で説明可能 | 棄却 (本 PR で cooldown 触らない) |
| Q4 ADR/v2 prompt 修正 | A + C、ADR amendment + v2 prompt refresh、cooldown 再調整 defer | H1 + H2 反映 |

## 変更後の実装サマリ

- **ADR (`.steering/20260430-m9-eval-system/decisions.md` ME-9)**: Amendment
  2026-05-07 ブロックを末尾に追記、rate basis (single vs parallel) を明示、
  trigger zone を context-dependent に再定義
- **v2 prompt (`g-gear-p3-launch-prompt-v2.md`)**: §Phase A.4 期待値 table を
  saturation model に更新、§ブロッカー予測 B-1 を rate basis 明示で書き直し、
  §Phase A 末尾に **run102 resume 手順** を追加
- **本タスク decisions.md / blockers.md / memory**: 上記反映
- **cooldown 再調整 child ADR**: **起票しない** (Codex Q3 棄却)、blockers.md に
  「Codex で再調整不要と判定済」と記録

## 関連参照

- Codex review: `codex-review-trigger-interpretation.md` (verbatim、Verdict
  hybrid A/C、HIGH 3 / MEDIUM 3 / LOW 1)
- Codex prompt: `codex-review-prompt-trigger-interpretation.md`
- 起点 ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9 (本 PR で
  amendment 追記)
- 直前 PR: PR #141 (run1 calibration v2 prompt、main=`60e1f6e`)
- v2 prompt: `.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md`
  (本 PR で修正)
- empirical sidecar (rsync 済): `data/eval/calibration/run1/kant_natural_run10[01].duckdb.capture.json`
