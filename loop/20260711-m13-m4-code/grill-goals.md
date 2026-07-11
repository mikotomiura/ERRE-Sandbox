# grill-goals — M13 M4 situated 3D 可視化 実コード（construction）

> grilling skill 実起動（2026-07-11、main checkout、タスクにつき 1 回）の出力。HOW は M4 impl-design ADR
> （`.steering/20260711-m13-m4-impl-design/design-final.md` §1-12）で AC/test 名まで凍結済（PR #74 merged）。
> 本 grill は「凍結契約を実コードに落とす際に残る非 HOW 判断分岐」を閉じ、検証可能ゴールを確定した。
> 判断分岐 = `.steering/20260711-m13-m4-code/decisions.md` 判断 1-5 に記録（Gate0 Godot 導入 / Blender pin /
> .glb↔viewer decouple / 5 zone / expected_placement schema）。

## 環境（Gate 0 解決済）
- Blender 5.1.2（`C:/Program Files/Blender Foundation/Blender 5.1/blender.exe`）— .glb bake 用（AC1a、開発者手順）
- Godot 4.6.2（`GODOT_BIN` 永続化）— headless placement dump 用（AC2/AC3、既存 `test_godot_project.py` 4 passed で検証）

## 検証可能ゴール（Done = 各 test が exit code 0 + pre-push 4 段 pass）

| AC | test（Done 判定） | issue |
|---|---|---|
| **AC5 measurement 面ゼロ** | `test_m4_viz_measurement_guard.py`（.py AST + .gd text、denylist 全幅 import/emit 非在 + 負 fixture trip + self-scan）+ `test_m4_gpl_spdx_boundary.py`（GPL header + src/ に import bpy 非在） | I1 |
| **AC4 下地（layout/zone 列挙）** | `test_m4_zone_layout.py`（zone_layout.json == ZONE_CENTERS 6桁 exact + 各 .tscn root transform == ZONE_CENTERS 6桁 exact〔既存 33.33→33.333… 是正含む〕+ Zone enum 厳密 5 + Zazen 非含） | I2 |
| **AC1 決定的 build（pipeline 証明）** | `test_m4_zone_glb_fingerprint.py::test_peripatos_fingerprint`（committed peripatos_v1.glb を純 GLB-JSON パーサで読み fp 再計算 → committed fingerprint と byte 一致 + 非 identity node transform / 圧縮 ext / external buffer を fail-closed）+ 同一機 idempotency 手順（run.sh、Blender 5.1.2 pin） | I3 |
| **AC1 決定的 build（残り zone）** | `test_m4_zone_glb_fingerprint.py`（残り 4 zone も committed .glb ↔ committed fingerprint byte 一致） | I4 |
| **AC2 causal wiring** | `test_m4_society_replay.py::test_headless_dump_matches_expected`（viewer headless dump が N=2 avatar を order_slot 順・trace 通り位置に解決、Python canonicalizer 正規化後 `expected_placement.jsonl` と byte 一致、offline・LLM 非接触） | I5(viewer) / I6(test) |
| **AC3 再現性** | `test_m4_society_replay.py::test_dump_deterministic`（同一 golden 2 回起動で dump byte 一致） | I6 |
| **AC4 boolean 網羅** | `test_m4_society_replay.py::test_scene_loads_five_zones`（dev scene 合成が 5 zone .tscn を load、Zazen 非含） | I6 |

## grill で閉じた非 HOW 判断分岐（decisions.md 参照）
- **判断3**: .glb（AC1）と dev-viewer（AC2/AC3/AC4）を decouple。dev scene は既存 primitive zone .tscn を
  read-only 合成、.glb は committed asset + fingerprint。.glb の scene wiring は 段階移行 defer。
- **判断4**: geometry-nodes .glb は 5 zone 全て（I3=peripatos で決定性契約確立 → I4=残り 4 反復）。
- **判断5**: expected_placement.jsonl schema = motion 行（kind=placement、ecl_trace echo）+ envelope 行
  （kind=envelope、envelope_stream の speech/animation echo）を canonical JSONL。Godot は echo、Python が正規化・比較。

## 不可侵（binding、全 issue 共通）
- construction ≠ measurement（floor/verdict/scorer/landscape/D_* 非計算・非測定、R-budget=0、holding 不可侵、
  over-read 禁止、firing⇔detectability 混同禁止、fingerprint/placement checksum は再現性 witness で metric でない）。
- GPL 分離（bpy は erre-sandbox-blender/ + SPDX のみ、src/ に import bpy 禁止、Godot は GDScript、非 GPL tool は scripts//tests/）。
- read-only: golden fixtures / handoff.py / EclReplayPlayer.gd / society.py / organ / 凍結 apparatus / MainScene.tscn /
  既存 zone .tscn（root transform 是正 = I2 の AC、それ以外改変禁止）。reasoning-trace door 保全のまま touch しない。
- HOW 契約を覆さない（design-final §1-12）。HOW を越える判断が出たら Stop → superseding ADR。
