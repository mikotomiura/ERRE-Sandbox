# Issue 003 (K3): committed Layer2-on golden の existence-check + replay-verify test + honest 記録
verify_level: recheck   # AC は committed real golden の存在/byte 契約直結

## Goal
real-run で bake 済みの `tests/fixtures/m2_layer2_live_golden/` に対し、Ollama-free の existence-check +
replay-verify test を実装する。**acceptance は非意味論 boolean のみ**（Codex HIGH-1）: self-other segment の
**構造 boolean 存在**（Codex MEDIUM-1）+ decision 数 = 36 + verify() byte-parity + inner_invocations==0。
Godot placement replay parametrize に m2_layer2 case を追加（G-GEAR は Godot 不在で skip）。honest finding を
記録（think=False 縮退・rendering collapse は non-gating human memo「semantic uptake not assessed」明記）。

## Background
FROZEN pre-register Axis B + acceptance（HIGH-1）+ decisions.md（HIGH-1 / MEDIUM-1）。segment framing =
`_SELF_OTHER_FRAMING`、observed line = `- <agent_id>: …`。window 0 は segment 無し、window 1..H-1 は
各 observer に framing 有り + observed agent set == `sorted(all_agents) - {observer}` + 自己行/未来行が無い。
**effect-magnitude / delta / divergence / score は一切計算しない**（over-read 境界）。

## Scope
### In
- 新規 `tests/test_integration/test_m2_layer2_live.py`（Ollama-free、committed golden を読む）:
  - `test_self_other_segment_structural_presence`（MEDIUM-1、構造 boolean）: decisions.jsonl の
    user_prompt を per-(agent, agent_tick) で読み、(a) window 0 = 全 observer に framing 無し /
    (b) window≥1 = 各 observer に framing 有り / (c) 各 observer の observed agent set ==
    `sorted(all_agents)-{observer}` / (d) 自己行・未来 window 行が無い、を boolean で assert。
  - `test_all_calls_decodable_and_count`: 全 recorded call decode 可（`society_recorded_calls_from_jsonl`）+
    decision 数 = N(3)×horizon(12) = 36。plan schema が構造 parse される（内容評価しない）。
  - `test_layer2_golden_replay_byte_parity`: `verify()`（script）で committed golden を replay → True +
    全 replay client `inner_invocations==0`。
  - `test_layer2_golden_self_other_enabled_pin`: manifest env_pins["self_other_enabled"] is True（MEDIUM-3、bool）。
- `tests/test_integration/test_m4_society_replay.py`: `_GOLDEN_CASES` に m2_layer2 case（n_agents=3、
  expected rows は golden から算出）を追加（Godot-gated、G-GEAR skip / MacBook 実行）。
- honest finding: `.steering/20260713-m13-layer2-mirror-sim-live-run/findings.md` +
  `experiments/20260713-m13-layer2-live/` に honest 記録（(1)-(4) boolean 結果 + think=False 縮退/collapse は
  「semantic uptake not assessed」明記の non-gating memo、verdict/magnitude 非 emit、LOW-3 語彙制限）。
### Out
- real Ollama 実走（real-run step で完了済み前提）。measurement（floor/verdict/scorer/magnitude/divergence）。
  multi-zone rendering fix（別 scoping、deferred）。society.py / handoff.py の改変。

## Allowed Files
- `tests/test_integration/test_m2_layer2_live.py`（新規）
- `tests/test_integration/test_m4_society_replay.py`（parametrize 追加のみ）
- `tests/fixtures/m2_layer2_live_golden/`（real-run bake 済み、read のみ）
- `.steering/20260713-m13-layer2-mirror-sim-live-run/findings.md`（新規）
- `experiments/20260713-m13-layer2-live/`（honest 記録）
- **無改変厳守**: society.py / handoff.py / society_live.py / 既存 golden / 凍結 evidence

## Acceptance Criteria（AC↔test）
- AC-K3-1: `pytest tests/test_integration/test_m2_layer2_live.py::test_self_other_segment_structural_presence -q` = passed
  （構造 boolean existence、非意味論）
- AC-K3-2: `pytest tests/test_integration/test_m2_layer2_live.py::test_all_calls_decodable_and_count -q` = passed
  （decode + 数=36 + 構造 parse）
- AC-K3-3: `pytest tests/test_integration/test_m2_layer2_live.py::test_layer2_golden_replay_byte_parity -q` = passed
  （verify() True + inner_invocations==0）
- AC-K3-4: `pytest tests/test_integration/test_m2_layer2_live.py::test_layer2_golden_self_other_enabled_pin -q` = passed
- AC-K3-5: honest finding 記録済み（非意味論 boolean acceptance + non-gating memo、verdict/magnitude 非 emit）
- AC-K3-6: `mypy src` + `ruff check src tests scripts` green

## Test Plan
- `pytest tests/test_integration/test_m2_layer2_live.py -q` 全緑。
- WSL byte-parity は real-run step で別途実測（本 issue は Ollama-free CI test のみ）。

## Stop Conditions
- committed golden が未 bake（real-run step 未完了）なら本 issue は blocked（real-run 待ち）。
- existence-check が effect-magnitude を読む実装に倒れたら Stop（over-read、HIGH-1 違反）。
- real golden が window≥1 で segment 不在（配線が real で発火しない）なら → honest finding として記録し、
  acceptance の扱いを user 裁定（tune せず、think=False 縮退の可能性を non-gating memo に）。

## Dependencies
- K2（002）: script の Layer2-on capture/verify 経路が landed。
- real-run step: `tests/fixtures/m2_layer2_live_golden/` が bake 済み（G-GEAR spend、非 Loop human-run）。

## Status
- done（Sonnet test 実装 → 客観 recheck 4 passed + Godot parametrize 12 passed / findings.md はオーケストレータ authoring）

## Execution Result
- 新規 `tests/test_integration/test_m2_layer2_live.py`（4 test 全緑、Ollama-free）:
  structural presence（tick0 framing 無 / tick≥1 framing 有 + observed set==others + no self-line、magnitude 非読取）/
  all_calls_decodable_and_count（decode + 36 + 構造 parse）/ replay byte-parity（verify() True, inner_invocations=0）/
  self_other_enabled_pin（env_pins bool True）。
- `test_m4_society_replay.py` に m2_layer2 case 追加（720 placement / 72 envelope rows / slots [0,1,2]、Godot-gated）。
  本機で Godot 解決され placement byte-identical PASS（12 passed）。
- honest finding = `findings.md`（over-read guard、非意味論 boolean acceptance + rendering collapse は non-gating memo）。
- real 実測 = `experiments/20260713-m13-layer2-live/results.md`。Win/WSL byte-parity PASS。
