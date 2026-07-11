# Issue 004 (I4): 残り 4 zone の geometry-nodes build（段階移行）+ committed .glb + fingerprint test
verify_level: recheck   # AC1 決定的 build を 5 zone 全体へ横展開 = 再現性 witness 直結

## Goal
I3 で確立した geometry-nodes 決定的 build pipeline を残り 4 zone（study / chashitsu / agora / garden）へ
反復適用し、5 zone すべての committed `.glb` + `.fingerprint.json` を揃え、全 zone の fingerprint test を緑にする。

## Background
FROZEN ADR §1.2（段階移行、全面書換しない）+ §9 I4 + §10 AC1。I3 の `export_peripatos.py` が template。
chashitsu は既存 `export_chashitsu.py`（primitive）があるが、§1.2 の裁量で geometry-nodes 版を新規追加
（既存 primitive builder は template として残す）。純パーサ helper = `tests/_glb_json.py`（I2）。
環境: Blender 5.1.2。設計 FROZEN。

## Scope
### In
- 新規 `erre-sandbox-blender/scripts/export_study.py` / `export_chashitsu_gn.py`（geometry-nodes 版、既存
  export_chashitsu.py と別名で共存 = §1.2 template 温存）/ `export_agora.py` / `export_garden.py`
  （各 SPDX header 必須、I3 の export_peripatos.py と同じ決定性契約 = seed-free + identity + 無圧縮）。
  - 各 zone は local content を原点中心（§2）。zone ごとの character（study=書斎、chashitsu=茶室、
    agora=広場、garden=庭）を index 駆動決定的 geometry で表現（visual quality は over-read 対象外、
    fingerprint は再現性 witness であって quality metric でない = §1.3 over-read guard）。
- committed `godot_project/assets/environment/<zone>_v1.glb`（4 zone）+ `<zone>_v1.fingerprint.json`（4 zone、canonical）。
- `tests/test_integration/test_m4_zone_glb_fingerprint.py` に残り 4 zone の fingerprint test を追記
  （I3 の peripatos test と同型、5 zone parametrize が望ましい）。
- run.sh に 4 zone の export + idempotency 手順を追記。
### Out
- viewer（I5）。headless dump（I6）。.glb の dev scene wiring（判断3 = decouple、defer）。measurement 一切。
  既存 `export_chashitsu.py`（primitive）の削除（template として温存、§1.2）。

## Allowed Files
- `erre-sandbox-blender/scripts/export_{study,chashitsu_gn,agora,garden}.py`（新規、SPDX header 必須）
- `erre-sandbox-blender/scripts/run.sh`（4 zone 追記）
- `godot_project/assets/environment/{study,chashitsu,agora,garden}_v1.glb`（新規、committed）
- `godot_project/assets/environment/{study,chashitsu,agora,garden}_v1.fingerprint.json`（新規、committed canonical）
- `tests/test_integration/test_m4_zone_glb_fingerprint.py`（4 zone 追記）
- **無改変厳守**: export_peripatos.py（I3 land 済）/ export_chashitsu.py（primitive template、温存）/ handoff.py /
  EclReplayPlayer.gd / 凍結 apparatus / MainScene.tscn / tests/_glb_json.py

## Acceptance Criteria（AC↔test）
- I4-G1: `test_m4_zone_glb_fingerprint.py` の 5 zone 全て（peripatos[I3] + study/chashitsu/agora/garden）が
  committed .glb ↔ committed fingerprint byte 一致。
- I4-G2: 4 zone 新規 export に SPDX header（I1-G5 の GPL boundary test で緑）。
- I4-G3（開発者手順、Blender 必須）: 各 export 再走で .glb byte 一致（idempotency、run.sh 記録）。
- CI parity: `bash scripts/dev/pre-push-check.sh` 4 段 `ALL CHECKS PASSED`。

## Test Plan
`pytest -q tests/test_integration/test_m4_zone_glb_fingerprint.py`（5 zone parametrize）+ pre-push 4 段。
.glb bake = 各 export script を `"$BLENDER_BIN" --background --python` で worktree 実走し committed .glb + fingerprint 生成。

## Stop Conditions
- 全 AC 緑（Done）。
- ある zone の geometry nodes が byte idempotent にならない → 禁止ノード混入を除去（§1.1）。
- Blender authoring が想定外に重く 4 zone 完走不能 → blockers.md 記録、user 裁定（未ビルド zone を明示 defer、
  AC1 はビルド済 zone に対して honest に緑、判断4 見直しタイミング）。HOW 越える設計変更なら Stop→ADR。
- 凍結 apparatus 改変を要する → Stop。budget 到達 → Stop。

## Dependencies
- I3（export_peripatos.py template + fingerprint test 骨格 + run.sh）。
- I2（tests/_glb_json.py パーサ）。I1（GPL/measurement guard）。

## Status
TODO

## Execution Result
（完了時に記入）
