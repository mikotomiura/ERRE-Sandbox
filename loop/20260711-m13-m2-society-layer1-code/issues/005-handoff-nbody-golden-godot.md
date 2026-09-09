# Issue 005 (I5): handoff N体 schema version bump（2 経路 byte 契約）+ Godot EclReplayPlayer bounded 拡張 + committed N体 golden
verify_level: recheck   # Codex HIGH-2 (N=1 byte 2 経路二分) + cross-platform golden (WSL byte 実測) 直結

## Goal
`handoff.py` の `MANIFEST_SCHEMA_VERSION` を **versioned additive** で M2 版へ bump（例 `m2-society-1`）し、
agent_id/order_slot/pair-order を version-pin。**N=1 byte 不変を 2 経路に二分**（Codex HIGH-2）:
(1) legacy path = `run_ecl_loop` + 既存 golden **完全 byte unchanged**、(2) M2 path = 新 schema N=1 を
canonical projection/adapter で legacy-equivalent 確認。Godot `EclReplayPlayer.gd` を N体 order_slot 順
offline playback に bounded 拡張。committed N体 golden を bake し **WSL byte 一致実測**（必須）。

## Background
FROZEN ADR §M7（handoff N体 schema、2 経路二分、Godot bounded 拡張、full Blender は M4 残置）/§M9.1
（legacy_byte_unchanged / n1_canonical_equivalent / handoff_manifest_pins）/ DA-M2IMPL-7 / Codex HIGH-2。
§M2 確証: `MANIFEST_SCHEMA_VERSION="ecl-v0-handoff-2"`（L79）、envelope stream は既に
`sorted({r.agent_id for r in result.rows})` → order_slot enumerate（L553/664）= N体前方互換、全順序
`(order_slot, agent_tick, seq)`（L576）、`CANONICAL_FLOAT_DECIMALS=6`（L105）。user 裁定: Godot .gd を
G-GEAR で編集（DG-5）。`feedback_golden_crossplatform_float_drift`: Windows bake golden は Linux CI で
libm 1-ULP drift → 6 桁量子化 + WSL byte 一致実測。設計 FROZEN。

## Scope
### In
- `integration/embodied/handoff.py`: `MANIFEST_SCHEMA_VERSION` を M2 版へ **additive bump**（agent_id/order_slot/
  pair-order を version-pin）。envelope 順序ロジック（sorted(agent_id)→order_slot、`(order_slot, agent_tick,
  seq)` sort）は **既存を再利用**（L553/576/664）。legacy 成果物への影響ゼロ（society は別 driver 経由）。
- `godot_project/**/EclReplayPlayer.gd`（dev-only、本番 WS 非接触）: N体 trace を order_slot 順に offline 再生
  する bounded 拡張。full Blender skinned-humanoid は M4 残置（GPL 分離、触れない）。
- `tests/fixtures/m2_society_golden/`（committed N体 golden、Windows bake → **WSL byte 一致実測**後 commit）。
- `tests/test_integration/test_m2_society.py`（本 issue 分を追記）。
### Out
- spend ast-guard（I6）。event-log checksum 定義（I3、済）。per-pair substream（I4、済）。tick sorted（I1、済）。
- **full Blender / geometry nodes 3D 可視化**（M4 残置、GPL 分離、DG-4）。**measurement 一切**。

## Allowed Files
- `src/erre_sandbox/integration/embodied/handoff.py`（SCHEMA_VERSION additive bump + pin、envelope ロジック再利用）
- `godot_project/`（`EclReplayPlayer.gd` の N体 bounded 拡張のみ、godot-gdscript skill 準拠、Python 混入禁止）
- `tests/fixtures/m2_society_golden/`（committed N体 golden、新規）
- `tests/test_integration/test_m2_society.py`（本 issue 分）
- **無改変厳守**: `loop.py`（run_ecl_loop）/ 既存 ECL v0/v1 committed golden/handoff fixture / `evidence/**` /
  `bank*.py`

## Acceptance Criteria（AC↔test）
- I5-G1: `test_m2_society_legacy_byte_unchanged` — `run_ecl_loop` + 既存 ECL v0/v1 committed golden/handoff
  fixture が **完全 byte unchanged**（society driver は legacy path に触れない、Codex HIGH-2 legacy path）。
- I5-G2: `test_m2_society_n1_canonical_equivalent`（handoff 軸）— society N=1 の新 schema（`m2-society-1`）出力が
  canonical projection/adapter 経由で legacy と **意味等価**（schema version 違いの raw byte 一致は要求しない、
  Codex HIGH-2 M2 path、I2-G1 を handoff manifest 層で補完）。
- I5-G3: `test_m2_society_handoff_manifest_pins` — M2 版 SCHEMA_VERSION / coord / tick 二軸（physics/agent）/
  determinism checklist（agent_id/order_slot/pair-order）を pin。
- I5-G4: `test_m2_society_golden_matches_committed` — committed N体 golden（`tests/fixtures/m2_society_golden/`）
  と society N体 run（同一 seed, 記録済 Plane2）の byte 一致。**WSL byte 一致を実測済**（6 桁量子化、
  feedback_golden_crossplatform_float_drift、実測ログを Execution Result に記載）。
- I5-G5: I1-I4 の test 群 + 既存回帰 緑維持。
- CI parity: `bash scripts/dev/pre-push-check.sh` 4 段 `ALL CHECKS PASSED`（+ **WSL でも pre-push 4 段 実測**、
  golden の cross-platform byte 一致を Linux 側で確認）。

## Test Plan
`pytest -q tests/test_integration/test_m2_society.py` + 既存 golden/handoff 回帰 + pre-push 4 段（Windows）+
**WSL で golden byte 一致 + pre-push 4 段 実測**。golden bake は mock LLM（決定的 raw response）で live 非依存。
Godot .gd はテキスト編集（Godot runtime 不要）、構文健全性は目視 + 既存 .gd パターン踏襲で確認。

## Stop Conditions
- 全 AC 緑（Done）。
- legacy golden の byte が動く → Stop（Codex HIGH-2 legacy path 違反、society が legacy に触れている）。
- 新 schema N=1 と legacy の raw byte 一致を要求してしまう → Stop（schema version 違い = 原理矛盾、DA-M2IMPL-7）。
- Windows bake golden が WSL で byte 不一致 → 6 桁量子化を見直し（float drift）。恒久不一致なら Stop→調査。
- Godot 拡張が本番 WS/production render path に触れる → Stop（dev-only 逸脱）。full Blender 3D に手を出す → Stop
  （M4 残置・GPL 分離 逸脱、DG-4）。
- 凍結 apparatus / run_ecl_loop 改変を要する → Stop（superseding ADR）。budget 到達 → Stop。

## Dependencies
- I3（event-log 全体を handoff manifest/envelope が serialize）。I2（society driver）。I4 と並列可。

## Status
DONE（2026-07-11、feat/m13-m2-layer1、commit fc58459）

## Execution Result
subagent（Sonnet）Windows 側実装 → test-runner(Haiku) Windows 独立検証（7/7 exit 0、3549 passed）→
**orchestrator が WSL byte 一致実測** → verdict=DONE。
- `handoff.py`: `M2_MANIFEST_SCHEMA_VERSION="m2-society-1"` additive（legacy 不変）+ render_society_golden 等。
  handoff は society を実行時 import せず Protocol 型（TYPE_CHECKING）で分離（良い architecture）。
- `EclReplayPlayer.gd`: N体 playback 既存前方互換、`_print_summary` のみ追加（dev-only、Python 混入なし）。
- `tests/fixtures/m2_society_golden/`（4 artifact、N=2 dialog 発火、m2-society-1）。6 桁量子化は既存
  canonical_dumps 継承。bake 決定的（2 回 byte 一致）。2 経路二分（legacy byte unchanged / M2 canonical-equiv）。
- **DG-2 WSL byte 一致実測 = PASS**（orchestrator 実施）: WSL Ubuntu-22.04 / Python 3.11.15 / uv core
  venv（`$HOME/.venv-erre-wsl`）で `test_m2_society.py` **17 passed** + `golden_matches_committed` 緑 =
  Windows bake の committed golden が Linux bake と **byte 一致**（6 桁量子化が libm 1-ULP drift 封鎖）。
  ECL byte 不変 + handoff 回帰も WSL 12 passed。
- **独立検証（Windows）**: test_m2_society 17 / ecl_handoff 8（legacy 不変）/ integration 回帰 200 / test_world
  158 passed、mypy/ruff/format clean。既存 ECL v0 golden unchanged 確認。
- cross-review 付託: n1_canonical_equivalent は observation factory ラベル差（"m2 society forage step"）を明示
  注入して legacy byte 一致（driver ラベル差で schema 非等価でない、over-read でない）。
