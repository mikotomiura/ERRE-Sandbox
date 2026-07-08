# Issue 003 (I3): spend/no-spend 境界の ast-guard（Codex HIGH-4 拡張封鎖）
verify_level: recheck   # spend 境界の機械保証 = safety-critical（§B5.2 binding 禁止の履行）

## Goal
bank module が「raw row のみ・集計禁止・adaptive top-up 禁止・call cap」を守ることを **AST + runtime で機械保証**
する。ECL v0/v1 の measurement 非再入 guard（`_measurement_guard.py`）を **superset 拡張**し、Codex HIGH-4 の
暗黙集計穴（Counter/set/目視で疑似 H）を封鎖する。**guard 自体が construction≠measurement の履行**。

## Background
FROZEN ADR §I4（spend ast-guard、Codex HIGH-4: AST guard に `math.log`/`collections.Counter`/`set`(over
zones)/`itertools.groupby`/`numpy`/`pandas`/`scipy`/`statistics` 追加、annotation opaque、B 側 test で
count/diversity assert 禁止、call cap、no-adaptive-topup）。既存 `tests/test_integration/_measurement_guard.py`
の 3-hole AST guard を base に。grill-goals.md D-6。**設計 FROZEN**。

## Scope
### In
- 新規 `tests/test_integration/_bank_spend_guard.py`（非 test helper、leading-underscore、pytest 非収集）:
  - `_measurement_guard.assert_no_measurement_surface_v1` を再利用（evidence/spdm/runningness/floor/landscape/
    verdict/divergence 継承）。
  - **追加 ban（HIGH-4）**: `math.log` / `collections.Counter` / `set`(over zones の集計文脈) / `itertools.groupby`
    / `numpy`/`pandas`/`scipy`/`statistics` の import + 呼出を AST で禁止（`assert_no_aggregation_surface`）。
  - `import-allowlist`: bank module（`bank.py`/`bank_fixtures.py`）が import してよい module 集合の**閉列挙**を
    主 guard（denylist 補助）。
  - call cap runtime helper: `max_llm_calls ≤ 2·M·K`、超過 fail-fast（`.codex/budget.json` 同型 cost ceiling）。
- 新規 `tests/test_integration/test_ecl_bank_spend_guard.py`。
### Out
- fixture/driver/golden 本体（I1/I2/I5）。continuity gate test（I6、guard helper は再利用される）。power
  apparatus（I4）。

## Allowed Files
- `tests/test_integration/_bank_spend_guard.py`（新規）
- `tests/test_integration/test_ecl_bank_spend_guard.py`（新規）
- **無改変厳守**: `_measurement_guard.py`（再利用のみ、v0/v1 guard は触らない）/ organ / bank.py / bank_fixtures.py

## Acceptance Criteria（AC↔test）
- I3-G1: `test_bank_no_measurement_computation` — `bank.py`/`bank_fixtures.py` に `math.log`/`Counter`/
  `set`(over zones)/`groupby`/`numpy`/`pandas`/`scipy`/`statistics` の import・呼出が非在（AST scan）
- I3-G2: `test_bank_llm_call_cap` — call cap helper が `2·M·K` 超過で fail-fast（境界値 test）
- I3-G3: `test_bank_no_adaptive_topup` — M/K が凍結 literal・annotation 非依存（AST で annotation を読む top-up
  分岐の非在を assert）
- I3-G4: `test_bank_annotation_opaque` — bank module + B 側 test が count/diversity/H/distinct-zone を計算・
  assert しない（AST scan、`_measurement_guard` の identifier ban 拡張）
- I3-G5: `test_bank_import_allowlist_guard` — bank module の import ∩ 禁止集合（`evidence.spdm`/`d0_substrate`/
  `es2_replay`/`memory_recomp_conformance`/`*runningness*`/`landscape_divergence`）= ∅、かつ allowlist 閉集合内
- CI parity: `bash scripts/dev/pre-push-check.sh` 4 段 `ALL CHECKS PASSED`

## Test Plan
`pytest -q tests/test_integration/test_ecl_bank_spend_guard.py` + pre-push 4 段。guard helper に **positive/
negative fixture**（禁止 pattern を含む合成 AST が確実に落ちる）を付けて guard の実効性を検証。docstring 内の
banned identifier 言及は substring-scan 対象外（既存 `_measurement_guard` の free-text 除外に倣う）。

## Stop Conditions
- 全 AC 緑（Done）。
- guard を通すために bank module が集計を隠蔽する必要が出た → Stop（§I4 spend 境界の実質破り）。
- `_measurement_guard.py`（v0/v1 guard）の改変が必要 → Stop（byte-invariance 契約逸脱→superseding ADR）。
- budget 到達 → Stop。

## Dependencies
- I2（scan 対象 `bank.py` が存在必要）、I1（`bank_fixtures.py`）。

## Status
DONE (2026-07-08、feat/m13-b-bank、commit 67f4d9a)

## Execution Result
subagent (Sonnet、fresh context) 実装 → 独立再実行済 (verify_level=recheck) + main が capture-script coverage
拡張。新規 `_bank_spend_guard.py`（`_measurement_guard` 3-hole guard を superset 拡張 = `assert_no_aggregation_
surface`[math.log/Counter/groupby/numpy/pandas/scipy/statistics 禁止 + **精密 set-over-zones 判定**: zone
attribute への set/Counter/len(set) 集計のみ ban、prompt-set dedup は許容] / import-allowlist[閉列挙主 +
SPDM 系 denylist 補、prefix-safe] / `assert_llm_call_cap`[2·M·K 境界 fail-fast] / no-adaptive-topup[while 非在
+ M/K 凍結 literal]）+ `test_ecl_bank_spend_guard.py`（48 test = 正例/負例両面 fixture）。
- I3-G1..G5 全緑（48 passed）。独立再実行 exit 0、mypy/ruff clean、tracked 無改変。
- **main 拡張**: scan 対象に `scripts/ecl_bank_capture.py`（I5 の annotation writer、§I4/D-6 の bank-module
  scan set）を追加 = 集計/measurement/annotation-opaque を capture CLI にも適用（import-allowlist は core
  module 限定 = CLI は argparse/json/handoff を正当 import）。capture script は全 guard を通過（docstring 言及は
  identifier/key/filename でないため誤検出なし）。
- guard 自体が construction≠measurement の履行（H/floor/verdict 非計算）。
