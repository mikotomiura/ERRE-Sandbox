# Issue 006 (I6): spend 非漂流 ast-guard（allowlist import + 計算/分布生成 禁止 + call cap）+ no-measurement test
verify_level: recheck   # measurement 非再入の機械保証 = 最重要 anti-over-read + Codex HIGH-1/HIGH-4 直結

## Goal
society module + tests の spend 漂流を **AST guard で機械保証**する（measurement 非再入の hard gate）。
allowlist import（evidence.spdm/d0_substrate/es2_replay/memory_recomp/*runningness*/landscape_divergence が ∅）+
**計算・出力・分布生成の禁止**（Counter/groupby/numpy/scipy/statistics の統計 API・zone/bin/category 集計・
floor/divergence/verdict 生成）。**AST guard は production executable に限定・docstring 除外**（Codex HIGH-1）。
**`set` blanket ban は撤回、`sorted(set(...))` は allow**（Codex HIGH-4）。gating CI = replay/mock only、
live cap は non-gating（Codex LOW-9）。**construction であって measurement でない**の機械的証明。

## Background
FROZEN ADR §M8（spend 非漂流 ast-guard、B impl-design §I4 同型）/§M9.3 / DA-M2IMPL-8 / Codex HIGH-1
（token guard × docstring 衝突 → production executable AST 限定、禁止対象を計算・出力・分布生成に寄せる）/
HIGH-4（`set` blanket ban が handoff の `sorted({r.agent_id ...})` と衝突 → 撤回、集計・分布生成に限定、
`sorted(set(...))` allow）/ LOW-9（gating = replay/mock only、live local qwen3 = manual/non-gating shakedown、
cap = tiny pinned 定数、超過 fail-fast）。§M9 の docstring 義務（"NOT a structural-floor verdict; verdict は
holding"）は token guard 対象外（executable AST 限定ゆえ自己矛盾しない）。設計 FROZEN。

## Scope
### In
- 新規 `tests/test_integration/test_m2_society_spend_guard.py`:
  - **allowlist import guard**: society module（+ 本 loop の tests）の import ∩ {`evidence.spdm` /
    `evidence.d0_substrate` / `evidence.es2_replay` / `evidence.memory_recomp_conformance` / `*runningness*` /
    `landscape_divergence`} = ∅。allowlist（society が import してよい閉列挙）を主、denylist を補助。
  - **計算/分布生成 禁止（executable AST 限定・docstring/comment/test 名/guard-test 自身を除外、HIGH-1）**:
    `numpy`/`pandas`/`scipy`/`statistics` の統計 API call / `collections.Counter` / `itertools.groupby` /
    zone/bin/category に対する分布 count / `compute_*floor*` 型関数 / verdict・scorer object 生成 の非在。
    H(zone|·) / MDE / KL/JS / paired-distribution divergence / CI / bootstrap を計算しない。
  - **`sorted(set(...))` は明示 allow**（HIGH-4、canonicalization 用）。裸の非 sorted `set`/`values()`
    iteration が checksum 経路にある禁止は I4 discovery guard へ委譲（本 guard は集計・分布生成のみ）。
  - **llm call cap**: gating test は replay/mock only（real LLM 非依存）。live local qwen3 は manual/non-gating
    shakedown に限定、cap = tiny pinned 定数（例 `max_llm_calls ≤ N_agents · shakedown_ticks`、超過 fail-fast、
    `.codex/budget.json` 同型 cost ceiling）。**powered run なし（R-budget=0）**。
- 必要なら society.py に guard 対象の明示 allowlist コメント/定数（executable でない、guard が読む）。
### Out
- society driver 本体（I2）。event-log checksum（I3）。pair substream/discovery guard（I4、裸 set/values は I4）。
  handoff/golden（I5）。Layer2。**measurement 一切**（本 issue はその非在を証明する側）。

## Allowed Files
- `tests/test_integration/test_m2_society_spend_guard.py`（新規）
- `src/erre_sandbox/integration/embodied/society.py`（guard allowlist 定数/コメントの追記のみ、挙動不変）
- **無改変厳守**: `loop.py` / `handoff.py` / committed golden / `evidence/**` / `bank*.py`

## Acceptance Criteria（AC↔test）
- I6-G1: `test_m2_society_no_measurement_computation` — society module executable AST に evidence/spdm import 非在
  + Counter/groupby/numpy/scipy/statistics/分布生成 非在 + floor/divergence/verdict 計算・生成 非在
  （**executable AST 限定・docstring 除外**、Codex HIGH-1。docstring の "NOT a structural-floor verdict" 文字列は
  guard 対象外を明示的に確認）。
- I6-G2: `test_m2_society_llm_call_cap` — gating path が replay/mock only（real LLM 非依存）、live cap 定数が
  tiny pinned literal で超過 fail-fast（gating では発火せず、non-gating shakedown 用、Codex LOW-9）。
- I6-G3: `test_m2_society_sorted_set_allowed` — guard が `sorted(set(...))` を **誤検出しない**（handoff の
  `sorted({r.agent_id ...})` 既存規律 + canonicalization と整合、Codex HIGH-4）。
- I6-G4: `test_m2_society_docstring_not_flagged` — docstring/comment 内の禁止語（"divergence"/"floor"/"verdict"
  等）を guard が flag しない（executable AST 限定の自己矛盾回避、Codex HIGH-1）。
- I6-G5: I1-I5 の全 test 群 + 既存回帰 緑維持（society module 完成形を guard）。
- CI parity: `bash scripts/dev/pre-push-check.sh` 4 段 `ALL CHECKS PASSED`。

## Test Plan
`pytest -q tests/test_integration/test_m2_society_spend_guard.py` + I1-I5 回帰 + pre-push 4 段。guard は
`ast` module で society.py を parse し executable node のみ検査（docstring node を除外）。allowlist/denylist は
明示リストで pin。live cap は定数 assert（実 LLM は起動しない）。

## Stop Conditions
- 全 AC 緑（Done）。
- guard が docstring/`sorted(set(...))`/canonicalization を誤検出して緑にできない → Stop（HIGH-1/HIGH-4 の
  scope 明確化に反する実装、AST 限定/allow list を見直し）。
- society module に measurement 計算（Counter/divergence/floor）が実在して guard が真に fail → Stop（それは
  measurement 再入 = binding 違反、該当コードを除去。除去不能なら superseding ADR）。
- live LLM を gating で起動しないと通らない設計 → Stop（§M8 LOW-9 逸脱）。
- 凍結 apparatus 改変を要する → Stop（superseding ADR）。budget 到達 → Stop。

## Dependencies
- I2（society module を guard 対象にする）。実運用は I3/I4/I5 land 後に society 完成形を guard（loop 最終）。

## Status
DONE（2026-07-11、feat/m13-m2-layer1、commit 468ccb9）

## Execution Result
subagent（Sonnet）実装 → test-runner(Haiku) 独立再検証（recheck、7/7 exit 0）→ verdict=DONE。
- 新規 `tests/test_integration/test_m2_society_spend_guard.py`（guard ロジック inline、society.py 無改変）:
  allowlist import guard + 計算/分布生成 禁止（numpy/pandas/scipy/statistics/Counter/groupby/math.log/
  floor·divergence·verdict·scorer identifier 非在、executable AST 限定・docstring 除外 [HIGH-1]、
  `sorted(set(...))` allow [HIGH-4]）+ llm call cap（gating=replay/mock、non-gating shakedown 用）。
- **実効性 witness**: 負例 fixture（evidence import 7 種 / aggregation 19 種）を guard が検出 + negative
  control（verdict identifier は検出）で盲目でないことも実証（vacuous でない）。
- society.py executable AST に measurement 計算 0（4 出現は全 docstring "NOT a structural-floor verdict"）。
- **独立検証**: spend_guard 31 / test_m2_society 17 / integration 回帰 200 / test_world 158 passed、
  mypy(239 clean)/ruff/format、7/7 exit 0。society.py 含む src 無改変（test 追加のみ）。
