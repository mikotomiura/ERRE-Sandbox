# Issue 004 (I4): power apparatus（categorical multinomial MDE, doc-only pre-run）+ power worksheet
verify_level: recheck   # named 閾値の pre-registration + ratification gate 直結（tune-to-pass 封鎖）

## Goal
T_on vs T_off の 5-way zone 分布シフトを **categorical multinomial power**（ES-4 Phase 0 型）で **doc-only
pre-run** 立証する power apparatus と、**検定法・最悪/代表 base distribution・K context pooling を明記した
power worksheet** を成果物として作る。worksheet が named 閾値（M_min/K/δ_min/H_min/ρ）を proposal から確定する。
**assumed base distribution のみで動く a-priori 計算 = bank annotation を一切読まない**（measurement でない）。

## Background
FROZEN ADR §I6（数値は非 binding proposal、power worksheet を FROZEN 条件化。proposal: M_min≥300 draw/(ctx,
condition) / K≥8 / δ_min=0.10 TV distance / power≥0.8 / H_min=0.5bit / ρ=0.5。**(i) H_min/ρ は empirical gate
目標であって B の保証でない** — 未達→line-close）。DA-BIMPL-6（Codex/user が数値を精査・ratify）。grill-goals.md
D-7。**設計 FROZEN**。

## Scope
### In
- 新規 `src/erre_sandbox/integration/embodied/bank_power.py`（bank measurement path 外の独立 module。**assumed
  distribution のみ**で a-priori MDE 計算。bank driver が import しない・annotation side-file を読まない）:
  - `categorical_multinomial_power(*, base_dist, delta_tv, m_draws, k_contexts, pooling)` — 5-way multinomial の
    a-priori power（worst-case collapse を含む assumed dist に対する MDE / power）。scipy/statistics 使用可
    （**assumed dist のみ**、real bank data 非依存ゆえ spend guard 対象外）。
  - named 閾値定数（proposal を worksheet 出力として確定）。
- 新規 `experiments/20260708-m13-b-bank/power_worksheet.md`（reproducibility-discipline 準拠）:
  - **検定法**（categorical 5-way multinomial power）。
  - **最悪・代表 base distribution**（H(zone|ctx)≈0 collapse を含む worst-case + 代表 near-uniform）。
  - **K context の pooling 仮定**（有無を明記）。
  - named 閾値（M_min/K/δ_min/H_min/ρ）の導出と proposal からの確定値。
  - **(i) H_min/ρ = empirical gate 目標、B は保証しない**（H(zone|ctx)≈0 なら分子消失で power 死 = 壁1&4 再来）を
    honest 明記。
- 新規 `tests/test_integration/test_ecl_bank_power.py`。
### Out
- 実 bank data に対する検定（C-proper AUTHORIZE 後のみ、本タスク非対象）。fixture/driver/golden（I1/I2/I5）。

## Allowed Files
- `src/erre_sandbox/integration/embodied/bank_power.py`（新規）
- `experiments/20260708-m13-b-bank/power_worksheet.md`（新規）
- `tests/test_integration/test_ecl_bank_power.py`（新規）

## Acceptance Criteria（AC↔test）
- I4-G1: `test_bank_power_worksheet_present` — worksheet doc が存在し、検定法 / worst-case+代表 base distribution
  / K pooling 仮定 / named 閾値（M_min/K/δ_min/H_min/ρ）を全て含む（grep で section 存在 assert）
- I4-G2: `test_bank_power_categorical_multinomial` — `categorical_multinomial_power` が assumed near-uniform dist
  で proposal 閾値（δ_min=0.10 TV, M_min≥300, K≥8）が power≥0.8 を満たすことを a-priori に返す（数値 sanity）
- I4-G3: `test_bank_power_collapse_kills_power` — worst-case collapse dist（H≈0）では power が閾値未達に落ちる
  （(i) 従属 = 壁1&4 再来を機械的に示す honest test）
- I4-G4: `test_bank_power_isolated_from_annotation` — `bank_power.py` が annotation side-file を読まず bank
  driver の measurement path を import しない（独立 = assumed dist のみ、AST/import scan）
- CI parity: `bash scripts/dev/pre-push-check.sh` 4 段 `ALL CHECKS PASSED`

## Test Plan
`pytest -q tests/test_integration/test_ecl_bank_power.py` + pre-push 4 段。power 計算は assumed dist の a-priori
（seed 固定・決定的）。scipy は extras 依存でなければそのまま、extras なら 3 点セット（lazy import + mypy ignore +
`pytest.importorskip`）。

## Ratification Gate（DA-BIMPL-6）
worksheet 出力の named 閾値は **Codex/user が ratify** してから FROZEN。実装完了後、統合前に閾値が proposal と
material に乖離していれば TASK-POST /cross-review + user 裁定に諮る（本 issue の Done は装置 buildable +
worksheet 存在、閾値 ratify は統合ゲート）。

## Stop Conditions
- 全 AC 緑（Done）+ worksheet 存在。
- power 計算が real bank annotation を読む必要が出た → Stop（doc-only pre-run 逸脱 = measurement 再入）。
- 閾値を「power が出る」よう恣意調整 → Stop（tune-to-pass）。
- budget 到達 → Stop。

## Dependencies
- なし（doc-only、I1-I3 と並行可）。ただし annotation raw-row 型の参照が要る場合は I2 の型定義を read-only 参照。

## Status
DONE (2026-07-08、feat/m13-b-bank、commit 2efe407)。**閾値 ratify (DA-BIMPL-6) は統合ゲート持ち越し**。

## Execution Result
subagent (Sonnet、fresh context) 実装 → 独立再実行済 (verify_level=recheck)。
新規 `bank_power.py`（`categorical_multinomial_power` = a-priori 5-way multinomial power。**MC-calibrated null
critical value ゆえ scipy 不要** = pure numpy+stdlib、extras 3 点セット回避。assumed base distribution のみで
MDE/power 計算、real bank data 非依存・bank driver 非 import・annotation 非読取）+ `power_worksheet.md`（検定法 /
worst-case(degenerate)+代表(near-uniform) dist / K-pooling 仮定 / named 閾値導出 / (i) H_min/ρ empirical gate
honest section / construction≠measurement scope guard / seed+1 コマンド repro）+ `test_ecl_bank_power.py`（5 test）。
- I4-G1..G4 全緑（5 passed）。I4-G3 collapse test = δ_tv=0.01（δ_min の 1/10）で power≈0.18<0.8 = (i) 従属を機械
  的に示す。honest 副観測（literally-degenerate base 単独では rare cell の比例感度で power を殺さない nuance）を
  worksheet に隠さず記録。
- named 閾値 = §I6 proposal と**乖離ゼロ**（M_min=300/K=8/δ_min=0.10/power≥0.8/H_min=0.5bit/ρ=0.5、a-priori
  計算が proposal を validate、tune-to-pass 不要）。ratify は統合 /cross-review + user 裁定へ。
- 独立再実行 exit 0（5 passed）。tracked 無改変。pre-push 4 段 ALL PASS（3418 passed）。Stop 非該当。
  construction≠measurement（floor/landscape/verdict/divergence 非計算、a-priori 装置 buildability のみ）。
