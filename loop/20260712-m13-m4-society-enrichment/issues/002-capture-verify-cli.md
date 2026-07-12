# Issue 002 (I2): scripts/m4_society_live_capture.py — --capture/--verify CLI + R3 decoder（handoff.py 無改変）
verify_level: recheck   # AC1/AC5 verify = 再現性契約 + anti-vacuous-pass（vacuous 抜けは致命）

## Goal
`scripts/ecl_v0_live_capture.py` を **society scope に design-copy** した新規
`scripts/m4_society_live_capture.py` を実装する。`--capture`（G-GEAR real Ollama、遅延 import、
here-untested）+ `--verify`（Ollama-free、CI/WSL 可、mock bundle で完全 pytest 化）。中核 = **R3 =
society decisions.jsonl から per-agent recorded call を復元する decoder**（Codex HIGH-2 の委譲方式）。

## Background
FROZEN design-final §B / §R3。ECL verify（`scripts/ecl_v0_live_capture.py::verify`）の O3a/O3b +
manifest 自身の再 render byte 一致（anti-vacuous-pass、Codex HIGH-1）を society peer に 1:1 mirror。
society decisions.jsonl 1 行 = `{order_slot, agent_id, decision:{...}}`（handoff.py:738
`build_society_decisions_stream`）で `decision` は flat `decision_to_dict` 出力そのもの。
`handoff.recorded_calls_from_jsonl`（:585）は各行 `json.loads(line)["call"]` を読む flat decoder。

## Scope
### In
- 新規 `scripts/m4_society_live_capture.py`（`ecl_v0_live_capture.py` design-copy、import 副作用なし）:
  - **R3 decoder（純 helper、script 内、handoff.py 無改変、Codex HIGH-1/HIGH-2）**:
    `society_recorded_calls_from_jsonl(text) -> dict[str, list[RecordedLlmCall]]`:
    - JSONL **物理行順** を一次順序に per-agent group（`agent_id` で束ね、行内順序保持）。
    - 各 agent の行の `entry["decision"]`（= flat decision dict）を `canonical_dumps` で flat 行に再直列化 →
      **既存 `handoff.recorded_calls_from_jsonl` に委譲**（schema drift 回避、HIGH-2）。
    - **fail-closed 検証（HIGH-1）**: `order_slot` は agent order 整合検証のみ（`agent_id→expected_slot`
      = `sorted(agent_ids).index` 一致 / tick ごと slot 完備 / 未知 agent / 重複 (agent_id, agent_tick) / 行数）。
      不整合は raise。
  - `--capture`（real Ollama、遅延 import `OllamaChatClient(model=LIVE_MODEL)`、mock embedding）:
    society_live の固定 constructor（agent_states/personas/observation_factories）→ `run_society_live_capture`
    → `render_society_golden(result, run_config, env_pins)` + `attach_society_live_observables` → 4 成果物 +
    `build_expected_placement` で `expected_placement.jsonl` 導出。**fixture write は `newline="\n"` 明示（M4）**。
  - `--verify`（Ollama-free）:
    - committed `decisions.jsonl` → `society_recorded_calls_from_jsonl` → `llms={aid: RecordReplayChatClient(recorded=...)}`
      （**exact 3 agent key、inner 無 → live fallback 不能、HIGH-3**）→ society_live の固定 constructor で
      `run_society_loop` replay 駆動。
    - **全 client `inner_invocations==0`**、`replay_checksum`/`event_log_checksum` 一致、全成果物 SHA-256。
    - **manifest 自身の再 render byte 一致（HIGH-5）**: `render_society_golden` + `attach_society_live_observables` +
      `canonical_dumps`、**committed env_pins/run 再利用**（fresh capture しない）。
    - **structural completeness（M1、fail-closed）**: expected 3 agent / horizon 12 / 各 agent decision count /
      各 agent call count を invariant 検証。
    - **constructor fingerprint assert（HIGH-4）**: committed manifest env_pins の fingerprint == 固定 constructor 再計算値。
- `tests/test_integration/test_m4_society_live.py` に I2 分を追加（mock-captured bundle で `--verify` 完全 test）:
  - mock bundle（`_ScriptedInner` capture 相当）を tmp に render → `verify()` = True。
  - decoder fail-closed test（重複 slot / 未知 agent / 行数不足 → raise）。
  - anti-vacuous: manifest を 1 byte 改竄 → `verify()` = False（vacuous pass しない）。
  - `m4_society_live_capture.py` の import-lint AST assert（denylist 非在）。
### Out
- real Ollama 実走（I4、`--capture` の live 分岐は import-lazy・here-untested）。viewer/test parametrize（I3）。
  handoff.py / society.py / society_live.py の改変（I1 で確定、無改変）。

## Allowed Files
- `scripts/m4_society_live_capture.py`（新規）
- `tests/test_integration/test_m4_society_live.py`（I1 と共有、I2 分追記）
- **無改変厳守**: handoff.py / society.py / society_live.py / ecl_v0_live_capture.py / 既存 m2_society_golden / 凍結 evidence

## Acceptance Criteria（AC↔test）
- AC2-G1: `...::test_verify_roundtrip_mock_bundle` = passed（mock bundle を render → `verify()` True、
  全 client inner_invocations==0、checksum/SHA/manifest 再 render 一致）。
- AC2-G2: `...::test_decoder_fail_closed` = passed（重複 (agent,tick) / 未知 agent / order_slot 不整合 / 行数不足 → raise）。
- AC2-G3: `...::test_verify_anti_vacuous` = passed（manifest 改竄 → `verify()` False）。
- AC2-G4: `...::test_verify_structural_completeness` = passed（agent 欠落 / horizon 不足 → fail）。
- AC2-G5: `...::test_m4_capture_measurement_guard` = passed（`m4_society_live_capture.py` AST denylist 非在）。
- CI parity: `mypy src`（script は tests から import される範囲）緑 + ruff 緑。

## Test Plan
mock capture bundle = I1 の `_ScriptedInner` で 3 agent を `run_society_live_capture` → `render_society_golden` →
tmp write。`verify(tmp_dir)` を driver に呼び True。改竄・fail-closed は tmp bundle を破壊して False/raise を確認。
`--capture` の live 分岐は遅延 import ゆえ本 test では触らない（I4 で real 実走）。

## Stop Conditions
- 全 AC 緑（Done）。
- decoder を既存 `recorded_calls_from_jsonl` に委譲できず再実装が要る → 委譲方式（HIGH-2）を再検討、
  handoff.py を触りたくなったら Stop（無改変厳守、要れば superseding ADR）。
- verify が live fallback を持たざるを得ない → Stop（HIGH-3、Ollama-free 破綻）。
- manifest 再 render が committed と一致しない構造的理由（env_pins に非決定値混入）→ blockers.md（env_pins から除外）。
- HOW 越え → Stop → superseding ADR。budget 到達 → Stop。

## Dependencies
- **I1**（`society_live.py` の `run_society_live_capture` / 固定 constructor / observables / env_pins が前件）。

## Status
done

## Execution Result

全 AC 緑（2026-07-12）:

- AC2-G1 `test_verify_roundtrip_mock_bundle` = passed
- AC2-G2 `test_decoder_fail_closed` = passed
- AC2-G3 `test_verify_anti_vacuous` = passed
- AC2-G4 `test_verify_structural_completeness` = passed
- AC2-G5 `test_m4_capture_measurement_guard` = passed
- I1 の既存 7 test も無壊: `test_record_replay_byte_parity` /
  `test_replay_no_inner_invocations` / `test_think_off_forced` /
  `test_society_live_measurement_guard` / `test_observables_are_annotation` /
  `test_society_live_capture_drives_every_agent` は毎回緑。
  `test_fixed_constructors_fingerprint` のみ既存フレーキー（下記 B1 参照、
  I2 の変更が原因ではなく I1 landed 時から存在するバグ）。
- `mypy src` = 240 files success（scripts/ 単体は既存 ecl_v0_live_capture.py
  と同型の import-untyped skip のみ、CI は `mypy src` のみ対象）。
- `ruff check` / `ruff format --check`（scripts/m4_society_live_capture.py +
  tests/test_integration/test_m4_society_live.py 個別指定）= 緑。
- `pytest tests/test_integration -q -m "not godot"` = 510 passed（回帰なし）。

新規発見（B1、`.steering/20260712-m13-m4-society-enrichment/blockers.md` 参照）:
`society_live.fixed_constructor_fingerprint` の `agent_states_sha256`/
`observation_factories_sha256` が `wall_clock: datetime =
Field(default_factory=_utc_now)`（`AgentState`/`PerceptionEvent` 系）混入で
非決定的（I1 既存バグ、society_live.py 無改変につき本 issue では未修正）。
`scripts/m4_society_live_capture.py` 側で
`_corrected_fixed_constructor_fingerprint`（wall_clock 除外の自前再計算に
2 サブフィールドを上書き）を追加し、capture/verify 双方で一貫させることで
CLI 内は決定的にした。

Codex 反映点: HIGH-1（order_slot はグローバル順序でなく agent-order 整合検証
のみ）/ HIGH-2（decoder は `handoff.recorded_calls_from_jsonl` に委譲、
再実装なし）/ HIGH-3（`--verify` の `llms` keys は exact 3 agent、decoder の
`expected_agent_ids` fail-closed で live fallback 不能）/ HIGH-4（constructor
fingerprint assert、上記 B1 補正込み）/ HIGH-5（manifest 自身の再 render
byte 一致、committed env_pins/run 再利用）/ M1（structural completeness
fail-closed）/ M4（`newline="\n"` 明示）。

binding 逸脱なし: handoff.py / society.py / society_live.py /
ecl_v0_live_capture.py / 既存 m2_society_golden 無改変。R-budget=0
（verdict/scorer/floor/divergence 非計算、AC2-G5 で AST guard 済）。
`--capture` の live 分岐は import-lazy・here-untested（I4 で real 実走）。
