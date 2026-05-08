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

### ✅ D-1. run102/103/104 (kant single calibration、wall=360/480/600 min) の採取 — **解消済 2026-05-08**

- G-GEAR で v2 prompt §B-1b の resume 手順実行、5 cell 全完了 (2026-05-08
  18:49)
- 5-cell empirical rates: 1.625 → 1.596 → 1.592 → 1.571 → 1.552 /min
  (saturation 単調減少、漸近線へ収束)
- focal_per_min_single mean = 1.5870 (95% CI [1.5527, 1.6213])
- **wall-aligned contention factor = 1.502** (run102 360 min single ÷ run0
  360 min 3-parallel)、§B.3 default 1.76× より −14.7%
- **run2-4 wall_budget 確定 = 600 min** for production 3-parallel
- 全 5 cell が single calibration central zone (1.55-1.87 /min) 内、Codex 9th
  hybrid A/C verdict (cooldown 再調整不要) を **5 cell 実測値で confirmation
  済**
- Mac 受領: HTTP rsync 経由 10 file (5 duckdb + 5 sidecar) pull + md5 10/10
  一致 + DuckDB read_only sanity 5/5 OK (status=partial / drain_completed=true)
- 反映先: M9-eval `decisions.md` ME-9 **Amendment 2026-05-08** + 本タスク
  `decisions.md` lock-step update 2026-05-08 + W-2 / W-3 解消方向追記

### D-2. run2-4 (production natural、3-parallel × wall=600 min default) の実走
- D-1 完了後、§Phase A 結果解析で wall budget 確定 → §Phase C 実行
- 想定所要: 24-48h (wall budget 次第)、kant drain timeout fallback あり
- **trigger**: D-1 確定 (2026-05-08) で fire 可、Phase B+C launch prompt 起草
  (本タスク Phase D、handoff §4) 後に G-GEAR 投入

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

### ✅ W-2. memory growth signal の検出力 (Codex M3) — **解消済 2026-05-08**
- run100 → run101 → run102 → run103 → run104: 1.625 → 1.596 → 1.592 → 1.571
  → 1.552 /min
- 単調減少 + 1-step diff が逐次小さくなる典型 saturation pattern を 5 点で
  確認、cell-to-cell variance ではなく **wall-duration accumulation** が
  dominant signal と判明
- empirical resolved、5 点 trend が saturation curve に fit (Codex M1 saturation
  model 適合)

### ✅ W-3. drain grace 60s の wall=600 適合性 (Codex L1) — **解消済 2026-05-08**
- run104 (wall=600 single) sidecar で `drain_completed=true` /
  `runtime_drain_timeout=false` 確認済 (Mac DuckDB sanity 経路、5/5 cells)
- drain grace 60s は wall=600 min × single でも sufficient と empirical 確定
- 3-parallel × wall=600 での drain は run2-4 production で要再確認 (W-3'
  として持ち越しの可能性)

### W-4. ADR Amendment 形式の運用慣習化
- ME-4 partial close 構造、ME-9 amendment と、ADR 末尾追記による re-define
  パターンが 2 例目
- 第 3 例が出たら ADR template を整理する候補
- **対応**: development-guidelines.md に ADR Amendment 慣習を documenting
  する別タスク
