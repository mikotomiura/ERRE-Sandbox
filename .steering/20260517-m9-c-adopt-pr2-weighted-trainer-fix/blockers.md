# ブロッカー記録 — PR-2 WeightedTrainer Blocker 2 fix

(本 PR 進行中に発生したブロッカーをここに記録。完走時にブロッカーが
なければ「該当なし」のまま finalise する。)

## 該当なし (記録時点で進行中ブロッカーなし)

DA-16 ADR で固まった `.mean()` reduce 方針 + test 5 件構成を実装する
だけの単純 PR のため、ADR 段階の不確実性は decisions.md に記録済。

本 PR 実装中に発見された Blocker 候補:

- (未発生)

## 持ち越し参照

- DA-16 ADR で確定済の **Blocker 2 (sample weight collapse)** は本 PR
  実装で解消。発生当時の症状記録は `.steering/20260518-m9-c-adopt-plan-
  b-retrain/blockers.md` ブロッカー 2 を参照
- PR-3 (kant_r8_v4 retrain) 以降の potential Blocker は次 PR 起票時に
  ハンドオフする
