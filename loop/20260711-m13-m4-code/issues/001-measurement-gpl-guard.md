# Issue 001 (I1): AC5 measurement-zero guard（.py AST + .gd text）+ GPL/SPDX boundary guard
verify_level: recheck   # measurement 非再入 + GPL 境界の機械保証 = 最重要 anti-over-read（LOW-2 = 最初の issue に）

## Goal
M4 の全新規コード（`.py` export scripts + `.gd` viewer + 新規 test + `scripts/`/`tests/` の非 GPL tool）が
**measurement 器官を import も emit もしない**こと（AC5）と、**GPL 境界が破れていない**こと（bpy は
erre-sandbox-blender/ + SPDX header のみ、src/ に import bpy 非在）を機械保証する。construction であって
measurement でないの hard gate。**LOW-2 反映 = guard を最初の issue に置く**（後続 issue が最初から guard 下）。

## Background
FROZEN M4 impl-design ADR §5（AC5 measurement-zero guard）+ §8（SPDX GPL header）+ §10 AC5 + §11 不可侵。
M2 `test_m2_society_spend_guard.py`（landed 先例、`_measurement_guard.py` の hole-1/2/3）を踏襲/拡張。
Codex HIGH-1（executable AST 限定・docstring 除外で自己 trip 回避）/ MEDIUM-2（denylist を guard 種別で分割、
false positive 抑制）/ LOW-2（guard を最初の issue に）反映済。設計 FROZEN。

## Scope
### In
- 新規 `tests/test_integration/test_m4_viz_measurement_guard.py`:
  - **対象**: 本 Loop の全新規コード = `scripts/export_zone_layout.py`（+ 純 GLB-JSON パーサ helper）/
    `erre-sandbox-blender/scripts/export_*.py`（新規 zone exporter）/ `godot_project/scripts/dev/SocietyReplayViewer.gd` /
    新規 test 群。
  - **denylist（scoping HIGH-1 全幅、狭めない）**: `evidence`（evidence/**）, `spdm`, `runningness`, `floor`,
    `landscape`, `verdict`（`cli/*_verdict.py` 含む）, `scorer`, `bank_scorer`/`bank*.py`, `D_*` 統計,
    aggregation surface（numpy/pandas/scipy/statistics/`Counter`/`groupby`/`math.log`）。
  - **`.py`（export scripts + tool）**: `ast` guard（**executable AST のみ走査、docstring/comment 非走査** = HIGH-1）。
    import denylist + identifier ban + aggregation ban。**bpy import は許可**（GPL 側の正当依存、denylist 対象外、
    GPL 境界は別 test で管理）。
  - **MEDIUM-2 = denylist を guard 種別で分割**: `floor`/`divergence`/`verdict`/`scorer` は **identifier substring ban**
    （executable AST の Name/arg/def 位置）。`D_*`（統計）/`bank*`/`landscape`/`evidence`/`spdm`/`runningness` は
    **import module path segment + CLI/artifact filename** を主軸（identifier 全面禁止は false positive が強い）。
    `_measurement_guard.py` の hole-1/2/3（ImportFrom(erre_sandbox)→evidence / dynamic import 文字列 / dict-key·filename exact）踏襲。
  - **`.gd`（GDScript）**: Python `ast` で parse 不可 → **正規表現/テキスト scan**（denylist token の import/identifier/
    dict-key/`.json`·`.jsonl` filename としての非在）。M2 の handoff-scan と同型 belt-and-suspenders。
  - **emit guard**: dump/artifact の dict key・出力ファイル名に denylist token 非在（hole-3 = key/filename exact scan 相当）。
  - **self-scan**: guard test 自身も denylist import を持たない（M2 の I6-G5 同型）。
  - **負 fixture**: denylist import/identifier を仕込んだ合成 src/gd を guard が必ず trip（実効性 witness、vacuous でない）。
- 新規 `tests/test_architecture/test_m4_gpl_spdx_boundary.py`（既存 `tests/test_architecture/` 拡張でも可）:
  - `erre-sandbox-blender/**/*.py` の全ファイルが先頭付近に `SPDX-License-Identifier: GPL-3.0-or-later` を持つ（純テキスト scan、bpy 不要）。
  - `src/erre_sandbox/**/*.py` に `import bpy` / `from bpy` が非在（AST or テキスト、GPL を本体に引き込まない）。
  - `scripts/export_zone_layout.py` / `tests/` の GLB-JSON パーサが bpy 非依存（import bpy 非在、非 GPL 確認）。
### Out
- export_zone_layout.py / zone_layout.json 本体（I2）。geometry-nodes .glb build（I3/I4）。viewer 実装（I5）。
  **measurement 一切**（本 issue はその非在を証明する側）。既存 `export_chashitsu.py` の SPDX 是正は I3
  （chashitsu geometry-nodes 化と同時）だが、本 issue の GPL boundary test は既存ファイルにも適用される
  → **I3 未完なら export_chashitsu.py の SPDX 欠で本 test が fail する可能性**。対処: 本 issue で
  export_chashitsu.py に SPDX header 行のみ追記（挙動不変、§8「既存 header 欠を是正」）。

## Allowed Files
- `tests/test_integration/test_m4_viz_measurement_guard.py`（新規）
- `tests/test_architecture/test_m4_gpl_spdx_boundary.py`（新規、既存拡張可）
- `erre-sandbox-blender/scripts/export_chashitsu.py`（**SPDX header 行の追記のみ**、挙動不変、§8 是正）
- **無改変厳守**: handoff.py / EclReplayPlayer.gd / society.py / committed golden / evidence/** / bank*.py / MainScene.tscn

## Acceptance Criteria（AC↔test）
- I1-G1: `test_m4_viz_no_measurement_import_or_emit` — 本 Loop 新規 .py の executable AST に denylist import/
  identifier/aggregation 非在（executable 限定・docstring 除外、HIGH-1）。
- I1-G2: `test_m4_viz_gdscript_no_measurement` — 新規 .gd の text scan で denylist token（import/identifier/
  dict-key/artifact filename）非在。
- I1-G3: `test_m4_viz_guard_catches_negative_fixture` — denylist を仕込んだ合成 .py/.gd を guard が trip（実効性）。
- I1-G4: `test_m4_viz_guard_docstring_not_flagged` — docstring/comment 内の denylist 語を flag しない（HIGH-1 自己矛盾回避）。
- I1-G5: `test_m4_gpl_header_present` — erre-sandbox-blender/**/*.py 全てに SPDX GPL header（export_chashitsu.py 是正含む）。
- I1-G6: `test_m4_no_bpy_in_core` — src/erre_sandbox/** に import bpy 非在 + scripts//tests/ の GLB パーサ bpy 非依存。
- CI parity: `bash scripts/dev/pre-push-check.sh` 4 段 `ALL CHECKS PASSED`。

## Test Plan
`pytest -q tests/test_integration/test_m4_viz_measurement_guard.py tests/test_architecture/test_m4_gpl_spdx_boundary.py`
+ pre-push 4 段。guard は `ast` で .py を parse し executable node のみ検査（docstring node 除外）、.gd は正規表現。
denylist/allowlist は明示リストで pin。負 fixture は inline 合成文字列を parse。

## Stop Conditions
- 全 AC 緑（Done）。
- guard が docstring/正当な非 GPL コードを誤検出して緑にできない → AST 限定/allowlist を見直し（HIGH-1）。
- 新規コードに真の measurement 計算が実在して guard が真に fail → Stop（measurement 再入 = binding 違反、除去。除去不能なら superseding ADR）。
- GPL boundary test が既存 src/ の import bpy を検出 → Stop（重大違反、該当を erre-sandbox-blender/ へ分離）。
- 凍結 apparatus 改変を要する → Stop（superseding ADR）。budget 到達 → Stop。

## Dependencies
- なし（最初の issue、LOW-2）。ただし後続 I2-I6 の新規ファイルが増えるたび guard 対象に含める（本 issue は
  guard 骨格 + 既存/自身を対象。後続 issue の final 統合時に guard が全新規ファイルを走査することを I6 で再確認）。

## Status
TODO

## Execution Result
（完了時に記入。PR 本文になる）
