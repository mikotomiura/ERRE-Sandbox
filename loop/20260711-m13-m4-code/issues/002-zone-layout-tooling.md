# Issue 002 (I2): export_zone_layout.py（純・非 GPL）+ zone_layout.json + drift/Zazen test + 純 GLB-JSON パーサ helper
verify_level: recheck   # AC4 下地 + 既存 33.33 drift 是正（read-only .tscn 例外的改変）= 決定性 witness 直結

## Goal
`contracts.geometry.ZONE_CENTERS`（SSOT authority）を配置権威座標の committed mirror（`zone_layout.json`）へ
snapshot する純 Python tool を作り、**環境（.tscn root / .glb 配置）の drift を 6桁 canonical exact で閉じる**
（既存 `Chashitsu.tscn` の手書き `33.33` → authority `33.333…` 是正含む）。Zone enum が厳密 5（Zazen 非含）を
assert。I3/I4 の fingerprint test が使う**純 GLB-JSON パーサ helper**（bpy 非依存 = 非 GPL）も本 issue で先行整備。

## Background
FROZEN ADR §6（配置権威座標 snapshot）+ §7（Zazen 非 zone）+ §1.3（純 GLB-JSON パーサ）。
Codex MEDIUM-3（tolerance でなく 6桁 canonical exact、既存 .tscn の 33.330000≠33.333333 drift を検出→是正）/
MEDIUM-4（非 GPL tool は erre-sandbox-blender/ 配下に置かない、scripts//tests/ 配置）反映済。
ZONE_CENTERS 実測: study=(-33.333…,0,-33.333…) / peripatos=(0,0,0) / chashitsu=(33.333…,0,-33.333…) /
agora=(0,0,33.333…) / garden=(33.333…,0,33.333…)。`_ZONE_OFFSET = WORLD_SIZE_M/3 = 33.3333…`。
handoff.py の canonical 規律（`CANONICAL_FLOAT_DECIMALS=6` + sort_keys + compact + allow_nan=False）を移植。設計 FROZEN。

## Scope
### In
- 新規 `scripts/export_zone_layout.py`（**純 Python・bpy 非依存・非 GPL、本体 Apache/MIT 側**）:
  `contracts.geometry.ZONE_CENTERS` を import し `godot_project/assets/environment/zone_layout.json`（committed、canonical）
  を生成。内容 = `{zone_name: [x,y,z]}`（5 zone）+ `world_size_m`。handoff canonical 規律で serialize
  （6桁量子化 + sort_keys + compact + allow_nan=False + trailing newline）。live WS（WorldLayoutMsg）は引き込まない。
- committed `godot_project/assets/environment/zone_layout.json`（生成物）。
- 新規 `tests/_glb_json.py`（純 GLB-JSON パーサ helper、leading-underscore で非収集、bpy 非依存）:
  committed `.glb` の glTF-JSON chunk を読み `{accessor.count, POSITION accessor.min/max, material 名, mesh_count}` を返す
  （binary buffer は decode しない）。**HIGH-1**: 非 identity node transform 検出で fail-closed。**HIGH-2**:
  `KHR_draco_mesh_compression`/`EXT_meshopt_compression`/external buffer URI/sparse-only POSITION を検出で fail-closed。
  （I3/I4 の fingerprint test がこれを使う。本 issue では helper + 単体 test のみ、実 .glb は I3 で供給）。
- 新規 `tests/test_integration/test_m4_zone_layout.py`:
  - `zone_layout.json` の各値 == `ZONE_CENTERS`（純 Python assert、6桁 canonical exact）。
  - 各 `godot_project/scenes/zones/<Zone>.tscn` の root transform 平行移動成分 == `ZONE_CENTERS[zone]`
    （.tscn を text parse、**6桁 canonical exact 比較**、tolerance 禁止）。
  - Zone enum 厳密 5（study/peripatos/chashitsu/agora/garden）+ Zazen 非含（`Zazen.tscn` は zone 列挙対象外）。
- **既存 `Chashitsu.tscn` の root transform 是正**（例外的改変、AC = MEDIUM-3）: `33.33` → authority 6桁
  （`33.333333`）。他 zone .tscn も drift があれば同様是正（study/agora/garden/peripatos は現状値を実測して判定）。
  **改変は root transform の平行移動成分のみ**（child mesh 相対座標・material 等は無改変）。
### Out
- geometry-nodes .glb build 本体（I3/I4、helper が読む .glb は I3 で供給）。viewer（I5）。measurement 一切。
  zone .tscn の root transform 以外の改変（child mesh / material / 追加ノード）は禁止。

## Allowed Files
- `scripts/export_zone_layout.py`（新規）
- `godot_project/assets/environment/zone_layout.json`（新規、生成物 committed）
- `tests/_glb_json.py`（新規、純パーサ helper）
- `tests/test_integration/test_m4_zone_layout.py`（新規）
- `godot_project/scenes/zones/*.tscn`（**root transform 平行移動成分の 6桁是正のみ**、drift 是正、他無改変）
- **無改変厳守**: contracts/geometry.py / handoff.py / MainScene.tscn / 凍結 apparatus

## Acceptance Criteria（AC↔test）
- I2-G1: `test_m4_zone_layout_matches_zone_centers` — zone_layout.json == ZONE_CENTERS（5 zone、6桁 canonical exact）。
- I2-G2: `test_m4_tscn_root_matches_authority` — 各 zone .tscn root transform == ZONE_CENTERS（6桁 exact、
  既存 chashitsu 33.33→33.333333 是正後に緑）。
- I2-G3: `test_m4_zone_enum_exactly_five_no_zazen` — Zone enum 厳密 5 + Zazen 非含。
- I2-G4: `test_m4_glb_json_parser_fail_closed` — 純パーサが 非 identity node transform / 圧縮 ext / external buffer /
  sparse-only を fail-closed（HIGH-1/HIGH-2、合成 minimal glTF-JSON で検証）。
- CI parity: `bash scripts/dev/pre-push-check.sh` 4 段 `ALL CHECKS PASSED`。

## Test Plan
`pytest -q tests/test_integration/test_m4_zone_layout.py` + pre-push 4 段。zone_layout.json は
`python scripts/export_zone_layout.py` で再生成 → committed と byte 一致も確認（idempotent）。.tscn は text parse で
`transform = Transform3D(...)` の末尾 3 要素（origin）を抽出。純パーサ fail-closed は合成 glТF-JSON dict で検証。

## Stop Conditions
- 全 AC 緑（Done）。
- .tscn root transform 是正が child mesh 相対座標を壊す → Stop（root のみ是正、child 無改変）。
- 既存 .tscn の drift が 6桁 exact で閉じない（別原因の座標 mismatch）→ 調査、HOW 越える判断なら Stop→ADR。
- 凍結 apparatus 改変を要する → Stop。budget 到達 → Stop。

## Dependencies
- I1（guard が本 issue の新規 .py を対象に含む。並行可だが guard 骨格 land 後が安全）。
- I3 は本 issue の `tests/_glb_json.py` に依存（helper を先行供給）。

## Status
TODO

## Execution Result
（完了時に記入）
