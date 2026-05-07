# ブロッカー — m9-eval ME-9 trigger 解釈タスク

## 解消済 (本タスクで対応)

### B-1. v2 prompt §ブロッカー予測 B-1 の擬陽性 trigger
- **解消**: ME-9 Amendment 2026-05-07 で trigger zone を context-aware (single
  vs parallel) に再定義、v2 prompt §A.4 / §B-1 を refresh + §B-1b で resume
  手順追加。Codex 9 回目 review (Verdict: hybrid A/C、81K tok) で擬陽性確定。

### B-2. ADR (`decisions.md` ME-9) の rate basis ambiguity
- **解消**: Amendment 2026-05-07 ブロックで明示。旧 re-open 条件 (≤55/h /
  ≥80/h、parallel 起点) は context-dependent table に上書き。

## 棄却 (Codex 9 回目 review で否定された方針)

### REJ-1. cooldown 再調整 child ADR (`COOLDOWN_TICKS_EVAL` の値変更)
- **棄却理由**: Codex Q3 採用 A、cooldown 過小の証拠なし。run100/101 の
  1.625/1.596 /min は pilot 1.875 /min より **低い** ため、cooldown 過小 (=
  rate が高すぎ) ではなく **wall-duration 効果 (memory pressure 累積)** で
  説明可能
- **記録**: 本タスクの当初 working title `cooldown-readjust-adr` は誤称、
  実 scope は trigger basis 明示。child ADR は **起票しない**

## 持ち越し (本タスク外)

### D-1. run102/103/104 (kant single calibration、wall=360/480/600 min) の採取
- 本 PR merge 後、G-GEAR で v2 prompt §B-1b の resume 手順に従って実行
- 想定所要: 360+480+600 = 1440 min ≈ 24h、overnight×1
- 目的:
  - run102 (360 min single) で **run0 360 min 3-parallel と直接比較**、
    contention_factor を wall-aligned で再校正 (Codex H3 必須指定)
  - run103/104 で saturation model fit 精度向上 (3 点 fit → 5 点 fit)
- **trigger**: 採取後 single rate central range (1.55-1.87 /min) 外で v2
  §B-1 trigger zone 該当なら停止 + Codex review 起動

### D-2. run2-4 (production natural、3-parallel × wall=600 min default) の実走
- D-1 完了後、§Phase A 結果解析で wall budget 確定 → §Phase C 実行
- 想定所要: 24-48h (wall budget 次第)、kant drain timeout fallback あり

### D-3. p3_decide.py の Mac 側再実行
- production 30 cell + calibration 5 cell の rsync 受信後
- target ratio (Burrows / MATTR) 確定、ME-4 stage 3 close 候補

### D-4. v2 prompt v3 化の検討
- 本 PR では v2 内で §A.4 / §B-1 修正 + §B-1b 追加。「v3」を別途切り出すかは
  defer
- defer 理由: in-place 修正で十分機能、v3 起票は重複コスト

## 監視中 (まだ起票されていない潜在課題)

### W-1. 2D 関数 fit (wall × parallel) (Codex M2)
- 現時点 sample: single ∈ {16, 120, 240}、parallel ∈ {360}
- run102 (single 360) 採取で **wall-aligned single vs parallel** 比較が
  最初に可能になる
- それでも parallel × non-360 wall sample が無いので 2D 関数の interaction
  は当面取れない
- **対応**: run2-4 で複数 wall 観測が出れば残差解析で interaction 推定可能

### W-2. memory growth signal の検出力 (Codex M3)
- run100 → run101: rate が 1.625 → 1.596 /min (-1.8%)
- cell-to-cell variance と未分離、単独では設計判断に使わない
- **対応**: run102/103/104 完了後、5 点 trend で memory pressure signal を
  分離評価

### W-3. drain grace 60s の wall=600 適合性 (Codex L1)
- run100 (wall=120) / run101 (wall=240) では `drain_completed=true` /
  `runtime_drain_timeout=false` を確認済
- wall=600 min での累積 memory pressure 下での drain 時間は未測定
- **対応**: run104 (wall=600 single) で sidecar `drain_completed` /
  `runtime_drain_timeout` field を再確認、false / true なら drain grace
  90s+ 検討

### W-4. ADR Amendment 形式の運用慣習化
- ME-4 partial close 構造、ME-9 amendment と、ADR 末尾追記による re-define
  パターンが 2 例目
- 第 3 例が出たら ADR template を整理する候補
- **対応**: development-guidelines.md に ADR Amendment 慣習を documenting
  する別タスク
