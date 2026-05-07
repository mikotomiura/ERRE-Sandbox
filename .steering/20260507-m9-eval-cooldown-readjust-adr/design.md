# 設計 — m9-eval ME-9 trigger 解釈 (旧称: cooldown-readjust-adr)

> **status**: APPROVED + Codex 9 回目 review 反映済 (2026-05-07)
> Verdict: hybrid A/C (C 採用、A を root-cause、B 棄却)
> 採否記録: `decisions.md` (本タスク内)

## 実装アプローチ

Codex Q3 で **cooldown 再調整は不要** と確定した結果、本タスクの scope は
当初想定 (cooldown re-adjust ADR 起票) から **trigger zone wording 修正 +
saturation model 反映** に変更:

1. **ADR (`.steering/20260430-m9-eval-system/decisions.md` ME-9)** に
   "Amendment 2026-05-07" ブロックを追記、rate basis (single calibration vs
   3-parallel production) を context-aware に分離した trigger zone table を
   定義。旧 `≤55/h or ≥80/h` を上書き
2. **v2 prompt (`g-gear-p3-launch-prompt-v2.md`)** の §Phase A.4 期待値
   table を linear から saturation model に更新、§ブロッカー予測 B-1 を
   rate basis 明示で書き直し、新 §B-1b として run102/103/104 resume 手順を
   追加
3. **本タスク内 docs** (decisions.md / blockers.md / memory) で経緯記録、
   cooldown 再調整 child ADR は「Codex 棄却」として blockers.md に明示

CLI コード改修ゼロ、テスト変更ゼロ、prompt + ADR 文書修正のみで完結。

## 変更対象

### 修正するファイル
- `.steering/20260430-m9-eval-system/decisions.md` — ME-9 末尾に Amendment
  2026-05-07 ブロック追記 (~50 行、re-open 条件 table 上書き含む)
- `.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md` —
  §Phase A.4 期待値 table を saturation model に更新、§ブロッカー予測 B-1
  を rate basis 明示で書き直し + §B-1b run102 resume 手順追加
- `.codex/budget.json` — 今回 81,541 tok 追加 (history append)

### 新規作成するファイル
- `.steering/20260507-m9-eval-cooldown-readjust-adr/requirement.md` (起票済)
- `.steering/20260507-m9-eval-cooldown-readjust-adr/decisions.md` (起票済)
- `.steering/20260507-m9-eval-cooldown-readjust-adr/design.md` (本ファイル)
- `.steering/20260507-m9-eval-cooldown-readjust-adr/blockers.md`
- `.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-prompt-trigger-interpretation.md` (起票済)
- `.steering/20260507-m9-eval-cooldown-readjust-adr/codex-review-trigger-interpretation.md` (Codex 出力 verbatim 保存済)
- `data/eval/calibration/run1/kant_natural_run10[01].duckdb.capture.json` (rsync 受信済、本 PR でも commit 対象外 ← `.gitignore` で `.duckdb*` は除外確認)
- `~/.claude/projects/-Users-johnd-ERRE-Sand-Box/memory/project_m9_eval_me9_trigger_interpretation.md` (memory 起票)

### 削除するファイル
なし。

## 影響範囲

- **ME-9 ADR**: 旧 re-open 条件 (≤55/h / ≥80/h trigger) は Amendment で
  context-aware に上書き。後方互換性 = 旧 wording は git history で参照可、
  新運用は Amendment 優先
- **v2 prompt**: §Phase A.4 / §ブロッカー予測 B-1 の数値が変わる、§B-1b 新規
  追加 (resume 手順) 。v2 prompt は legacy reference の v1 と並存、active は v2
- **後続 G-GEAR セッション**: 本 PR merge 後、§B-1b の resume 手順で
  run102/103/104 採取を継続。run100/101 はそのまま使う (再採取不要)
- **Codex review 通算**: 本 PR で 9 回目、累計 budget today = 257,734 tok
  (1M/day budget 余裕)

## 既存パターンとの整合性

- ADR Amendment block は既存 ADR (例: ME-4 の partial close 構造、
  `.steering/20260430-m9-eval-system/decisions.md` 内) のパターンを踏襲、
  本 ADR (ME-9) も末尾に追記方式
- v2 prompt の修正は P3a-rerun-v2 (`g-gear-p3a-rerun-prompt-v2.md`、PR #133)
  で validated された v1 → v2 並存パターン (本ケースは v2 内修正)
- Codex review verbatim 保存 + budget.json history append は前回 PR #140 /
  #141 で確立したパターン

## テスト戦略

- 単体テスト: 不要 (prompt 文書 + ADR 修正のみ)
- 統合テスト: 不要 (実走は次の G-GEAR セッション、本 PR では実施しない)
- markdownlint: 修正後の v2 prompt + decisions.md ME-9 で MD022/MD032 警告
  ゼロを確認 (新規追記節の前後 blank line 確保)
- 内容 review: Codex 9 回目 review verbatim を起点に、HIGH 3 全反映を decisions.md
  で trace 可能にする

## ロールバック計画

- 単一 PR (squash merge 想定)、revert で完全復元
- ADR Amendment は append-only なので、revert で旧 re-open 条件に戻る
- v2 prompt §Phase A.4 / §B-1 / §B-1b の修正は merge 前の v2 prompt
  (PR #141 時点) と diff で復元可能
- run1 calibration の既採取 sidecar (run100/101) は本 PR で `.gitignore`
  対象 (DuckDB / sidecar)、commit 対象外 ← Mac 側で保持、G-GEAR 側で再現可能

## Codex review HIGH 3 件全反映の trace

| Codex H | 反映先 | 検証 |
|---|---|---|
| H1 (rate basis 分離) | ME-9 Amendment table + v2 §B-1 table | trigger zone が context-dependent |
| H2 (B-1 擬陽性) | v2 §A.4 saturation model + §B-1 wording 書き直し | run100/101 が central zone 内 |
| H3 (run102 採取必須) | v2 §B-1b resume 手順追加 | 後続 G-GEAR で実行可能 |

## Codex review MEDIUM 3 件採否

- M1 (saturation model): 採用、v2 §A.4 で表反映
- M2 (2D fit 不可): 採用、blockers.md W-1 監視中
- M3 (run100→101 -1.8% は弱い signal): 採用、blockers.md W-2 監視中

## Codex review LOW 1 件

- L1 (drain grace 60s OK): 記録のみ、blockers.md W-3 監視中 (wall=600 で再確認)

## 関連参照

- Codex review: `codex-review-trigger-interpretation.md` (verbatim、81,541 tok)
- 起点 ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9 (本 PR で
  Amendment 追記)
- 直前 PR: PR #141 (run1 calibration v2 prompt、main=`60e1f6e`)
- v2 prompt: `.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md`
  (本 PR で §A.4 / §B-1 / §B-1b 修正)
- empirical sidecar (rsync 済): `data/eval/calibration/run1/kant_natural_run10[01].duckdb.capture.json`
