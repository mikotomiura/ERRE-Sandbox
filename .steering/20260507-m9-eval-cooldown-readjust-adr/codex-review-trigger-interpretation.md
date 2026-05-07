## Verdict
- 解釈 **hybrid A/C** を推奨
- 判定理由: **65/h trigger は run0 3-parallel 起点なのに、v2 prompt では single calibration rate に直接適用され、run100/101 が期待値 table 内なのに擬陽性 trigger になっている**ため。

## Interpretation analysis
- 解釈 A の妥当性: 強い。ME-9 ADR の根拠は run0 3-parallel `≈65/h` で、ADR も run0 観測を根拠にしている。`run1` は [ME-9 ADR](/Users/johnd/ERRE-Sand%20Box/.steering/20260430-m9-eval-system/decisions.md:586) で single と明記されるため、basis 混在がある。
- 解釈 A の反証: `1.731` 補正自体が pilot 16 min vs run0 360 min の mixed effect。A の補正値をそのまま真値扱いするのは危険。
- 解釈 B の妥当性: 文言上はあり得る。ADR は [run1 calibration trigger](/Users/johnd/ERRE-Sand%20Box/.steering/20260430-m9-eval-system/decisions.md:646) と書き、v2 prompt B-1 も [observed focal/min](/Users/johnd/ERRE-Sand%20Box/.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:458) に直接 threshold を置いている。
- 解釈 B の反証: 実測 1.625/1.596 min は v2 の [期待値 table](/Users/johnd/ERRE-Sand%20Box/.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md:178) の下限内。cooldown 過小なら「期待 single より高い」はずだが、実際は pilot 1.875/min より低い。
- 解釈 C の妥当性: 最も妥当。ADR と v2 prompt の rate basis が曖昧で、single 期待値と trigger threshold が同じ文書内で矛盾している。
- 採用解釈: **C を採用、A を root-cause として記録、B は棄却**。

## 4 questions への回答
### Q1: B + provisional A
`1.731` は wall-duration confound を含む mixed effect。run100/101 基準では factor は `1.50` / `1.47` 付近だが、これはまだ wall-aligned ではない。run102 の 360 min single を取り、run0 360 min 3-parallel と比較して再推定すべき。run2-4 計算では central `~1.5`、安全側 bound `1.73-1.76` の bracket を保持。

### Q2: B/C hybrid
linear decay は不適切。3 点 fit では exponential asymptote と `a + b/wall` を識別できないが、どちらも 600 min single を `~1.55-1.59/min` と見るのが妥当。3-parallel は factor `~1.5` なら `~1.03-1.06/min`、factor `1.73` なら `~0.90-0.92/min`。前者が central、後者は conservative budget bound。

### Q3: A
cooldown 再調整は不要。run100/run101 は `COOLDOWN_TICKS_EVAL=5` の失敗証拠ではなく、wall-duration 効果と prompt threshold 擬陽性で説明できる。run102 は採取すべきだが、目的は cooldown 変更ではなく wall effect / contention factor 分離。

### Q4: A + C
実作業は A: ME-9 ADR amendment block で rate basis 明示、v2 prompt B-1 refresh。PR の結論は C: wording 修正のみで完結し、cooldown 再調整は defer。

## HIGH (本タスクで必反映)
### H1. ME-9 trigger の rate basis を分離
single calibration rate と 3-parallel production-estimated rate を別 threshold にする。`≤55/h / ≥80/h` を single observed rate に直接適用しない。

### H2. v2 prompt B-1 は擬陽性 trigger
run100 `195/120=1.625`、run101 `383/240=1.596` は expected table の下限内。B-1 の `≥1.33/min` trigger は single calibration 期待値と矛盾する。

### H3. run102 を採取してから factor を確定
360 min single が run0 360 min parallel と比較可能な最初の有効点。run102 なしで `1.50` か `1.73` を固定しない。

## MEDIUM (採否は実装側判断、decisions.md 記録)
### M1. Phase A.4 の線形期待値は saturation model に更新
`1.87/min × wall` は 600 min までの外挿として強すぎる。暫定 single 600 min は `~1.55-1.59/min` の range で扱う。

### M2. 2D 関数 fit は現時点では不可
single は 16/120/240 min、parallel は 360 min だけなので wall effect と parallel effect の interaction を識別できない。

### M3. run100→101 の -1.8% は弱い signal
memory growth の方向性とは整合するが、cell-to-cell variance と未分離。単独では設計判断に使わない。

## LOW (持ち越し可、blockers.md 記録)
### L1. drain grace は今回問題なし
run100/101 sidecar は `drain_completed=true`、`runtime_drain_timeout=false`。`_RUNTIME_DRAIN_GRACE_S=60.0` は少なくとも 240 min cell では機能している。

## Out-of-scope notes
- read-only review のため編集なし、テスト実行なし。
- DuckDB 本体は再集計せず、sidecar / summary / steering records の fact-check に限定。