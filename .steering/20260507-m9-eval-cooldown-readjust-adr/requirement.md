# m9-eval-cooldown-readjust-adr (working title、Codex Verdict で再 scope 予定)

> **status**: PROVISIONAL (Codex 9 回目 review 待ち、Verdict 後に re-scope)
>
> 起点: 2026-05-07、PR #141 merged 直後の G-GEAR run1 calibration が cell 100/101
> 完了時点で **ME-9 trigger** に該当し、G-GEAR Claude が正規 STOP。

## 背景

### empirical 観測 (今回の run1 calibration)

| cell | wall (min) | focal | rate (/min) | rate (/h) | sidecar |
|---|---|---|---|---|---|
| run100 | 120 | 195 | **1.625** | **97.5** | partial / wall_timeout / drain_completed=true |
| run101 | 240 | 383 | **1.596** | **95.75** | partial / wall_timeout / drain_completed=true |

両 cell とも `focal_target=2000` で wall-limited stop 確実、`runtime_drain_timeout=false`
で drain 健全。md5 検証済 (`16945c60...` / `d082570a...`)、Mac 側
`data/eval/calibration/run1/` に展開済。

### trigger 解釈問題

ADR (`decisions.md` ME-9, line 646):

> run1 calibration で 120-min 単位 focal/hour rate が 65 を大きく外れる
> (例: ≤55 / ≥80) → COOLDOWN_TICKS_EVAL や cognition_period の再調整 ADR
> 起票 (本 ADR の child)

しかし 65/h 起点は **run0 incident の 3-parallel rate** 由来 (Codex H1 の
`65 × 8 × 0.85 = 442` 計算)。run1 calibration は **kant single** で実行した
ため observation の rate basis が違う:

- 観測 single rate ≈ 1.6/min ≈ 96/h → ADR trigger ≥80/h **該当**
- 1.731× contention 換算 (pilot 1.875 / run0_mean 1.083) で parallel ≈
  0.92/min ≈ 56/h → ADR trigger ≤55/h **境界ぎりぎり**

つまり **rate basis (single vs parallel) の解釈次第で trigger 判定が反転**する。

### wall duration 効果も浮上 (Codex review への追加 finding)

```
pilot single  (wall=16  min): 1.875/min
run100 single (wall=120 min): 1.625/min  (-13.3%)
run101 single (wall=240 min): 1.596/min  (-15.0%, run100 から -1.8%)
```

memory pressure 累積 (sqlite store growth、cognition reflection buffer growth)
の signal の可能性大。これは contention_factor の wall-duration confound でも
あり、本質的な cooldown 過小と区別する必要あり。

## ゴール (provisional、Codex Verdict 後に確定)

- 解釈 A 採用なら: v2 prompt rate basis 明示修正 + run1 resume
- 解釈 B 採用なら: COOLDOWN_TICKS_EVAL 再調整 ADR (cooldown 過小修正)
- 解釈 C 採用なら: ADR amendment + v2 prompt wording 統一
- いずれにせよ ADR / v2 prompt / next G-GEAR action plan を一意に確定し、PR 起こす

## スコープ

### 含むもの (provisional)
- Codex 9 回目 review verbatim 保存
- 採用解釈に基づく ADR amendment / v2 prompt 修正 / child ADR 起票のいずれか
- run1 resume vs 中止 vs cooldown 再調整やり直しの判断
- run2-4 wall budget 計算式の更新 (wall duration 効果反映)

### 含まないもの (provisional)
- run1 / run2-4 の実走 (本タスクは Mac 側 planning、実走は次の G-GEAR タスク)
- Tier B/C metric 計算 (P3 完了後)
- vLLM / SGLang / LoRA (M9-B 系統)

## 受け入れ条件 (provisional)

- [ ] Codex 9 回目 review verbatim 保存 (`codex-review-trigger-interpretation.md`)
- [ ] Verdict (採用解釈 A/B/C/hybrid) を decisions.md に記録、根拠付き
- [ ] HIGH 全反映、MEDIUM 採否を decisions.md に記録、LOW は blockers.md
  持ち越し可
- [ ] 採用解釈に応じた成果物が確定:
  - 解釈 A: v2 prompt v3 起票 (rate basis 明示) + G-GEAR resume 手順
  - 解釈 B: child ADR (cooldown 再調整) + COOLDOWN_TICKS_EVAL 候補値
  - 解釈 C: ADR (`decisions.md` ME-9) amendment + v2 prompt 修正
- [ ] markdownlint MD022/MD032 警告ゼロ
- [ ] memory entry 起票、MEMORY.md インデックス更新
- [ ] PR description で trigger 解釈経緯 + Codex Verdict + 採用根拠を明示

## 関連ドキュメント

- 起点 ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9 (本タスクで
  amendment 対象になる可能性)
- 直前 PR: PR #141 (run1 calibration v2 prompt、main=`60e1f6e`)
- v2 prompt: `.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md`
  (本タスクで修正対象になる可能性)
- Codex review prompt: `codex-review-prompt-trigger-interpretation.md` (本タスク内)
- empirical sidecar (rsync 済): `data/eval/calibration/run1/kant_natural_run10[01].duckdb.capture.json`

## 運用メモ

- タスク種別: **その他** (ADR amendment / wording fix / child ADR、いずれも
  Codex Verdict 後に確定)
- 破壊と構築 (`/reimagine`) 適用: **既に Codex review 9 回目で多角化中**、
  再起動不要
- 着手前 Codex review **実施中** (bh9w5fz0c、completion 待ち)
