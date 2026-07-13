# Issue 001 (K1): society_live.py — run_society_live_capture に self_other_enabled thread（additive）
verify_level: recheck   # AC は additive byte-identity + segment 注入配線の存在 = 再現性/配線契約直結

## Goal
`src/erre_sandbox/integration/embodied/society_live.py::run_society_live_capture`（L310）に
**keyword-only `self_other_enabled: bool = False`**（Codex LOW-2）を追加し、`run_society_loop`（L349）へ
そのまま pass-through する。`run_society_loop` は既に `self_other_enabled` param + injection wiring を landed 済み
（無改変）。unit test で「True → observer の recorded user_prompt(tick≥1) に self-other segment 実在 /
default False → 不在（Layer1 byte-identical）」を証明する。

## Background
FROZEN pre-register `.steering/20260713-m13-layer2-mirror-sim-live-run/design.md` seam 1。
`run_society_loop` の wiring（`_build_window_self_other_contexts` → `self_other_context=so_ctx.rendered`）は
PR #77 で landed。`build_user_prompt(self_other_context=...)`（cognition/prompting.py L340/L407）が
segment を user prompt 文字列に埋め込む → recorded user_prompt（handoff L502）に乗る。
segment framing = `_SELF_OTHER_FRAMING`（society.py L515）。window 0 は prior 無しで segment 無し（honest）。

## Scope
### In
- `society_live.py::run_society_live_capture`: keyword-only block 末尾に `self_other_enabled: bool = False` 追加、
  `run_society_loop(...)` 呼び出しに `self_other_enabled=self_other_enabled` を additive で渡す。
- `tests/test_integration/test_m4_society_live.py`: 追加 unit test（`_ScriptedInner` mock、N=3、≥2 tick）:
  - `test_self_other_enabled_injects_segment`: `self_other_enabled=True` で capture → ある observer の
    tick≥1 の recorded user_prompt に `_SELF_OTHER_FRAMING` が実在。
  - `test_self_other_default_off_no_segment`: default（False）で capture → どの recorded user_prompt にも
    `_SELF_OTHER_FRAMING` が不在（既存 Layer1 path byte-identical の witness）。
  - mock inner が異なる destination_zone を返すよう `_ScriptedInner` を per-agent 変化させ、observed line が
    non-vacuous になるようにする（segment body が空でない）。
### Out
- script CLI / env_pins 永続 / verify auto-detect（K2）。real Ollama 実走（real-run step）。
  existence-check test on committed golden（K3）。society.py / handoff.py / prompting.py の改変（無改変厳守）。

## Allowed Files
- `src/erre_sandbox/integration/embodied/society_live.py`（seam 1 のみ）
- `tests/test_integration/test_m4_society_live.py`（追加 test のみ）
- **無改変厳守**: society.py / handoff.py / cognition/prompting.py / loop.py / live.py /
  既存 golden（m4_society_live_golden / m2_society_selfother_golden / m2_society_golden）/ 凍結 evidence

## Acceptance Criteria（AC↔test）
- AC-K1-1: `pytest tests/test_integration/test_m4_society_live.py::test_self_other_enabled_injects_segment -q` = passed
  （True で segment 実在）
- AC-K1-2: `pytest tests/test_integration/test_m4_society_live.py::test_self_other_default_off_no_segment -q` = passed
  （default False で segment 不在 = Layer1 byte-identical）
- AC-K1-3: 既存 `test_m4_society_live.py` 全 test が緑維持（`test_record_replay_byte_parity` /
  `test_replay_no_inner_invocations` / `test_think_off_forced` 等、regression なし）
- AC-K1-4: `mypy src` + `ruff check src tests` green

## Test Plan
- `pytest tests/test_integration/test_m4_society_live.py -q` 全緑。
- 既存 M4 harness の byte-parity/think-off/measurement-guard test が unchanged で緑（additive default-off の証明）。

## Stop Conditions
- society.py / handoff.py / prompting.py を改変しないと AC が満たせない場合 → Stop（設計逸脱、superseding ADR）。
- default False で既存 test が byte 破壊されたら Stop（additive 前提の崩壊）。

## Dependencies
- なし（先頭 issue）。K2 が本 issue の society_live seam に依存（直列）。

## Status
- done（Sonnet 実装 → Haiku test-runner 独立再検証 5 段全緑 exit 0）

## Execution Result
- society_live.py `run_society_live_capture` に keyword-only `self_other_enabled: bool = False` 追加 →
  run_society_loop へ pass-through（additive、docstring 追記）。society.py 等 無改変（git diff で確認）。
- test_m4_society_live.py: `_capture` に optional `self_other_enabled` + per-agent 変化 `_ScriptedInner` +
  `test_self_other_enabled_injects_segment`（tick0 に framing 無 / tick≥1 に framing 有）+
  `test_self_other_default_off_no_segment`（全 call に framing 無 = Layer1 byte-identical）。
- 検証（Haiku 独立 recheck）: 対象 2 test passed / test_m4_society_live.py 15 passed / mypy 240 files clean /
  ruff check + format clean（全 exit 0）。full test_integration 537 passed（regression なし）。
