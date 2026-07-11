# Issue 003 (I3): geometry-nodes peripatos build（seed-free）+ fingerprint sidecar + SPDX + 同一機 idempotency
verify_level: recheck   # AC1 決定的 build pipeline の確立（1 zone で全決定性契約を証明）= 再現性 witness 直結

## Goal
**1 zone（peripatos = golden agent の移動 zone）で geometry-nodes 決定的 build pipeline の全契約を確立**する:
seed-free 純関数 geometry nodes + node transform=identity + 圧縮/external buffer 禁止 fail-closed +
fingerprint sidecar（6桁量子化）+ SPDX header + 同一機 byte idempotency 手順（run.sh、Blender 5.1.2 pin）。
I4 が残り 4 zone にこの pipeline を反復適用する土台。

## Background
FROZEN ADR §1（geometry nodes ノードグラフ、seed-free）+ §1.3（決定性契約・二層 witness）+ §2（.glb 粒度）+
§8（SPDX header）。Codex HIGH-1（accessor min/max = mesh-local → node transform=identity 強制 + パーサ
fail-closed）/ HIGH-2（圧縮/external buffer 禁止 fail-closed）反映済。既存 `export_chashitsu.py` は bpy.ops
primitive（geometry-nodes 未使用）+ SPDX 行欠 = §8 是正対象（是正は I1 で SPDX 行追記済のはず、本 issue は
chashitsu geometry-nodes 化はしない = §1.2 段階移行裁量）。純 GLB-JSON パーサ helper = I2 の `tests/_glb_json.py`。
環境: Blender 5.1.2（`BLENDER_BIN`）。設計 FROZEN。

## Scope
### In
- 新規 `erre-sandbox-blender/scripts/export_peripatos.py`（GPL-3.0、**SPDX header 必須**、`blender --background --python`）:
  - **seed-free 決定的 geometry nodes**（§1.1）: 禁止 = `Distribute Points on Faces`/seed 未固定 `Random Value`/
    時間依存。許可 = 決定的プリミティブ（Mesh Grid/Cube/Cylinder/Mesh Line）+ `Instance on Points`（点源 Grid/Mesh Line）+
    `Transform`/`Set Position`（index・固定数式駆動）+ `Realize Instances`。植生/prop の散らしは **index 駆動の決定的格子**。
  - peripatos = 歩行路 zone。local content を**原点 (0,0,0) 中心**に格納（§2、full ground は含めない = BaseTerrain 別維持）。
  - **node transform=identity binding**（HIGH-1）: 全 mesh node の transform=identity（`export_apply=True` +
    object 原点正規化）。export 契約でこれを保証（accessor-local bbox = asset bbox）。
  - **圧縮/external buffer 禁止**（HIGH-2）: `KHR_draco_mesh_compression`/`EXT_meshopt_compression`/external buffer URI/
    sparse-only POSITION を出さない（GLB は自己完結）。export で明示的に無圧縮。
  - 出力: staging `erre-sandbox-blender/exports/peripatos_v1.glb`（git-ignored）+ Godot copy
    `godot_project/assets/environment/peripatos_v1.glb`（committed data）。
  - fingerprint sidecar 生成: `godot_project/assets/environment/peripatos_v1.fingerprint.json`（committed、canonical
    = 6桁量子化 + sort_keys + compact + allow_nan=False）。内容 = `{mesh_count, total_vertex_count,
    bbox:{min:[x,y,z],max:[x,y,z]}, materials:[sorted names]}`。fingerprint 生成は export script が bpy で
    scene から算出（GPL 側）or committed .glb を純パーサで読んで生成（非 GPL）— **どちらでも可だが committed
    fingerprint と純パーサ再計算が byte 一致することが AC**（I4 fingerprint test で検証）。
- 新規 `erre-sandbox-blender/scripts/run.sh`（or 既存拡張）: Blender 5.1.2 pin + export コマンド + 同一機
  idempotency 手順（再走 .glb byte 一致）を記録。reproducibility-discipline 準拠。
- 本 issue の fingerprint test（peripatos のみ）: `tests/test_integration/test_m4_zone_glb_fingerprint.py::test_peripatos_fingerprint`
  = committed `peripatos_v1.glb` を `tests/_glb_json.py` で読み fp 再計算 → committed
  `peripatos_v1.fingerprint.json` と byte 一致（CI、Blender 不要）。非 identity/圧縮/external を fail-closed。
### Out
- 残り 4 zone（study/chashitsu/agora/garden）の build（I4）。既存 chashitsu の geometry-nodes 化（§1.2 段階移行、
  本 spike ではしない）。.glb の dev scene wiring（判断3 = decouple、defer）。viewer（I5）。measurement 一切。

## Allowed Files
- `erre-sandbox-blender/scripts/export_peripatos.py`（新規、SPDX header 必須）
- `erre-sandbox-blender/scripts/run.sh`（新規 or 既存拡張、Blender 5.1.2 pin + idempotency 手順）
- `godot_project/assets/environment/peripatos_v1.glb`（新規、committed data）
- `godot_project/assets/environment/peripatos_v1.fingerprint.json`（新規、committed canonical）
- `tests/test_integration/test_m4_zone_glb_fingerprint.py`（新規、peripatos test。I4 が残り zone を追記）
- `.gitignore`（erre-sandbox-blender/exports/ が既に ignored か確認、なければ追記）
- **無改変厳守**: handoff.py / EclReplayPlayer.gd / society.py / 凍結 apparatus / MainScene.tscn / tests/_glb_json.py（I2 の helper、read-only 使用）

## Acceptance Criteria（AC↔test）
- I3-G1: `test_peripatos_fingerprint` — committed peripatos_v1.glb を純パーサで読み fp 再計算 → committed
  fingerprint と byte 一致。
- I3-G2: パーサ fail-closed 経路（非 identity node transform / 圧縮 ext / external buffer）が本物の peripatos_v1.glb で
  発火しない（= export が identity + 無圧縮を守っている証拠）。I2-G4 の合成 fail-closed と対。
- I3-G3（開発者手順、Blender 必須、非 CI gate）: `export_peripatos.py` 再走で .glb byte 一致（同一機 idempotency）。
  run.sh に手順 + Blender 5.1.2 pin を記録。
- I3-G4: `export_peripatos.py` に SPDX GPL header（I1-G5 の GPL boundary test で緑）。
- CI parity: `bash scripts/dev/pre-push-check.sh` 4 段 `ALL CHECKS PASSED`（fingerprint test は Blender 不要で緑）。

## Test Plan
`pytest -q tests/test_integration/test_m4_zone_glb_fingerprint.py -k peripatos` + pre-push 4 段。
.glb bake = `"$BLENDER_BIN" --background --python erre-sandbox-blender/scripts/export_peripatos.py`（開発者手順、
worktree で 1 回実走して committed .glb + fingerprint を生成）。idempotency = 2 回 bake して byte 一致を実測（run.sh 記録）。

## Stop Conditions
- 全 AC 緑（Done）。
- geometry nodes が seed-free で byte idempotent にならない（cross-run drift）→ 禁止ノード混入を除去（§1.1）。
- export が identity transform / 無圧縮を守れず fingerprint witness が成立しない → export 契約を修正（HIGH-1/HIGH-2）。
- Blender 5.1.2 で geometry nodes API が想定と違う → blockers.md 記録、HOW 越える設計変更なら Stop→superseding ADR。
- 純パーサ helper（I2）が未 land → I2 依存待ち。凍結 apparatus 改変を要する → Stop。budget 到達 → Stop。

## Dependencies
- I2（`tests/_glb_json.py` 純パーサ helper を使用）。
- I1（SPDX/measurement guard が本 issue の export_peripatos.py を対象に含む）。

## Status
TODO

## Execution Result
（完了時に記入）
