# Issue 006 (I6): headless placement dump 検証 test（Python canonicalizer 比較）+ expected_placement.jsonl + 5 zone load
verify_level: recheck   # AC2/AC3/AC4 の機械検証（決定的再生 + 網羅）= 最終 gate、公開挙動直結

## Goal
I5 の `SocietyReplayViewer.gd` が golden の N体 substrate を **order_slot 順・trace 通りに決定的再生**することを
headless dump の byte 比較で機械検証する（AC2 causal wiring / AC3 再現性）。dev scene が **5 zone を load**
することを boolean 検証する（AC4）。committed `expected_placement.jsonl` を Python 側で golden から生成し、
Godot dump を handoff canonicalizer で正規化してから byte 比較（HIGH-3 = Godot float→str を witness にしない）。

## Background
FROZEN ADR §4（決定的再生の検証法）+ §10 AC2/AC3/AC4。Codex HIGH-3（witness は committed trace の
pass-through echo、Python が正規化・比較）反映済。canonicalizer = handoff.py の `canonical_dumps`
（6桁量子化 + sort_keys + compact + allow_nan=False）。golden = tests/fixtures/m2_society_golden/
（2 agents a_alpha/a_bravo、slot 0/1、physics_tick 20、cognition 4、全 zone=peripatos）。
dump schema = decisions.md 判断5（placement 行 + envelope 行）。既存 `_godot_helpers.py::resolve_godot()` で
Godot 解決（GODOT_BIN、不在時 skip）。設計 FROZEN。

## Scope
### In
- 新規 committed `tests/fixtures/m2_society_golden/expected_placement.jsonl`:
  - golden の `ecl_trace.jsonl` から導出した per-(physics_tick_index, order_slot) 解決位置列（placement 行）+
    `envelope_stream.jsonl` 由来の per-(order_slot, agent_tick, seq) 発火 kind 列（envelope 行、speech/animation のみ）を、
    handoff canonical 規律で serialize。**生成は Python 側**（Godot 非依存、ecl_trace + envelope_stream から決定的導出）。
  - 生成ロジックは test module 内 helper（or scripts/）に置き、committed expected と再生成が byte 一致（idempotent）を確認。
- 新規 `tests/test_integration/test_m4_society_replay.py`（既存 `_godot_helpers.py` 経由で Godot headless 起動）:
  - **AC2 `test_headless_dump_matches_expected`**: viewer を headless 起動
    （`--headless ... --dump=<tmp>`）→ dump を handoff `canonical_dumps` で正規化 → committed
    `expected_placement.jsonl` と byte 一致。N=2 avatar を order_slot 順・trace 通り位置に解決していることを確認。
    live WS/LLM 非接触（offline golden のみ）。
  - **AC3 `test_dump_deterministic`**: 同一 golden で 2 回起動 → 2 dump が byte 一致（正規化後）+ committed
    expected と一致。
  - **AC4 `test_scene_loads_five_zones`**: `SocietyReplayScene.tscn` を headless load → 5 zone .tscn が load される
    （Zazen 非含）。boolean（load 成否 + zone ノード数 = 5）。
  - Godot 不在時 skip（`resolve_godot()` None → `pytest.skip`、既存慣習）。**local pre-push は GODOT_BIN 有りで実走**。
- expected_placement.jsonl 生成の純 Python helper（Godot 非依存）が I1 measurement guard に通る（denylist 非在）。
### Out
- viewer / scene 本体（I5、read-only 使用）。.glb build（I3/I4）。measurement 一切（placement byte 比較は
  再現性 witness であって metric/floor/verdict でない = handoff ecl_trace_checksum と同格、over-read 厳禁）。

## Allowed Files
- `tests/fixtures/m2_society_golden/expected_placement.jsonl`（新規、committed）
- `tests/test_integration/test_m4_society_replay.py`（新規）
- （生成 helper が test 外なら）`scripts/gen_expected_placement.py`（新規、純 Python・非 GPL、任意）
- **無改変厳守**: SocietyReplayViewer.gd/SocietyReplayScene.tscn（I5、read-only）/ golden の他 4 artifact
  （manifest/ecl_trace/decisions/envelope_stream、read-only）/ handoff.py / EclReplayPlayer.gd / 凍結 apparatus

## Acceptance Criteria（AC↔test）
- I6-G1: `test_headless_dump_matches_expected` — headless dump（正規化後）== committed expected_placement.jsonl
  byte 一致（N=2 avatar order_slot 順・trace 通り、offline、AC2）。
- I6-G2: `test_dump_deterministic` — 同一 golden 2 回起動で dump byte 一致（AC3）。
- I6-G3: `test_scene_loads_five_zones` — dev scene が 5 zone .tscn load + Zazen 非含（AC4 boolean）。
- I6-G4: expected_placement.jsonl が golden から Python 側で再生成して byte 一致（idempotent、決定的導出）。
- I6-G5: 本 Loop 全新規ファイル（I1-I5）が I1 measurement/GPL guard を最終統合で通る（guard が全新規コードを走査）。
- CI parity: `bash scripts/dev/pre-push-check.sh` 4 段 `ALL CHECKS PASSED` + **WSL byte 一致実測**
  （feedback_golden_crossplatform_float_drift 踏襲、placement dump/expected の cross-platform 決定性）。

## Test Plan
`pytest -q tests/test_integration/test_m4_society_replay.py` + pre-push 4 段 + WSL 実走で expected/dump byte 一致。
Godot headless = `resolve_godot()` → `--headless --path godot_project --script res://scripts/dev/SocietyReplayViewer.gd
-- --manifest=... --trace=... --stream=... --dump=<tmp>`。dump 正規化 = handoff `canonical_dumps`。

## Stop Conditions
- 全 AC 緑（Done）。
- dump が expected と byte 一致しない → 原因診断（role split 誤り / order_slot 誤 assign / float 再フォーマット）。
  Godot 側で float を再計算していたら pass-through echo へ修正（HIGH-3）。HOW 越える判断なら Stop→ADR。
- cross-platform（WSL）で byte 不一致 → 6桁量子化が dump/expected 両方に効いているか確認（Godot echo の
  文字列表現が量子化前値を持ち込んでいないか）。閉じない構造的 drift なら Stop→ADR。
- placement 比較を metric/floor/verdict に接続したくなる → Stop（over-read 禁止、再現性 witness のみ）。
- 凍結 apparatus / golden 他 artifact 改変を要する → Stop（superseding ADR）。budget 到達 → Stop。

## Dependencies
- I5（SocietyReplayViewer.gd + SocietyReplayScene.tscn）。
- I1（guard、最終統合で全新規ファイル走査）。golden fixtures（committed 済）。

## Status
done

## Execution Result
- 新規 committed `tests/fixtures/m2_society_golden/expected_placement.jsonl`（56 行 = 40 placement + 16 envelope、
  golden ecl_trace + envelope_stream から純 Python 導出、handoff `canonical_dumps` で serialize、trailing newline）。
- 新規 `tests/test_integration/test_m4_society_replay.py`（Godot headless = `_godot_helpers.resolve_godot()`、
  不在時 skip）。生成 helper `build_expected_placement` を test module 内に置き guard スキャン対象化（scripts/ 生成器は不作成）。
- GODOT_BIN 有りで **実走**（skip でなく）:
  - I6-G1 `test_headless_dump_matches_expected` PASSED（正規化 dump == committed expected byte 一致、N=2 order_slot 順・trace 通り、offline）。
  - I6-G2 `test_dump_deterministic` PASSED（同一 golden 2 回 dump byte 一致 + committed 一致）。
  - I6-G3 `test_scene_loads_five_zones` PASSED（SocietyReplayScene.tscn headless load、zone ノード数=5、Zazen 非含）。
  - I6-G4 `test_expected_placement_idempotent` PASSED（golden から再生成→committed と byte 一致）。
- I6-G5: `test_m4_viz_measurement_guard.py` + `test_m4_gpl_spdx_boundary.py` = 36 passed（新規 test module も guard glob で走査、measurement/GPL 表面なし）。
- HIGH-3 遵守: witness = committed trace 値の pass-through echo、Python 側 `canonical_dumps`（6桁量子化 + sort_keys + compact）で
  dump/expected 両方を正規化してから比較（Godot runtime float→str を byte witness にしない）。Godot は float 0.0/yaw を "0.0" で emit、
  正規化後 byte 一致を実測確認。dump は expected と **byte 一致**（role split 誤り / order_slot 誤 assign / float 再フォーマット なし）。
- `ruff format --check` / `ruff check` = clean、`mypy src` = Success（src 無改変）。
- 無改変厳守: SocietyReplayViewer.gd / SocietyReplayScene.tscn / golden 他 4 artifact / handoff.py / EclReplayPlayer.gd（全 read-only 使用）。
- Stop 抵触なし（HOW 越えなし、over-read なし = placement 比較は再現性 witness に留めた）。
- WSL cross-platform byte 実測は統合 step（pre-push 4 段 + WSL）へ持ち越し（expected は既に量子化済 committed trace 由来ゆえ platform 非依存、構造的に決定的）。
