# Issue 005 (I5): SocietyReplayViewer.gd + SocietyReplayScene.tscn（新規、dev-only、EclReplayPlayer 無改変）
verify_level: recheck   # AC2 causal wiring の実装（role split + trace pass-through echo）= 公開挙動直結

## Goal
golden の committed N体 substrate を「動く N体 society」として立ち上げる **dev-only viewer** を新規実装する:
motion 権威 = `ecl_trace.jsonl`（`(physics_tick_index, order_slot)` → 絶対座標 pass-through echo）、
speech/animation 駆動 = `envelope_stream.jsonl`（`(order_slot, agent_tick, seq)`、move は位置に使わない）。
**EclReplayPlayer.gd は無改変**（別責務 = envelope-only print、判断4）、production MainScene/WS graph は非接触。

## Background
FROZEN ADR §3（dev viewer + replay role split）+ §3.4（二モード）。Codex HIGH-3（Godot runtime float→str を
cross-machine byte witness にしない → motion は committed trace 値を pass-through echo、byte 比較は Python 側）/
MEDIUM-1（order_slot は一意 key でなく安定順序の一部、motion[physics_tick clock]と speech·anim[agent_tick clock]は
join しない、別 clock domain の独立系列）/ MEDIUM-2（role split binding）反映済。
golden 実測: 2 agents a_alpha(slot 0)/a_bravo(slot 1)、全 row zone=peripatos、physics_tick 20 / cognition 4。
ecl_trace row = {agent_id, physics_tick_index, agent_tick, order_slot, x, y, z, yaw, pitch, zone, ...}。
envelope_stream = {order_slot, agent_tick, seq, envelope:{kind, ...}}。ENVELOPE_STREAM_KINDS=(speech,move,animation)。
既存 `EclReplayPlayer.gd`（無改変参照）/ `dev/README.md`（production は dev/ を import しない、boot path 分離）/
`AgentAvatar.tscn` / `BaseTerrain.tscn` / 5 zone .tscn（read-only 参照）。設計 FROZEN。

## Scope
### In
- 新規 `godot_project/scripts/dev/SocietyReplayViewer.gd`（dev-only、GDScript）:
  - **motion/position 権威 = ecl_trace.jsonl**: 各 avatar（order_slot）を trace row の
    `(physics_tick_index, order_slot)` 系列の絶対座標 `(x,y,z)` + `yaw` に配置/補間。20 physics tick を
    時系列再生（interactive）または列 dump（headless）。**位置は committed trace 値を再計算せず pass-through echo**（HIGH-3）。
  - **speech/animation 駆動 = envelope_stream.jsonl**: `(order_slot, agent_tick, seq)` 順で speech ラベル
    （最小テキスト）/ animation 名を発火。**move は位置に使わない**（§3.3、speech/animation のみ駆動）。
  - **order_slot 単独 join 禁止**（MEDIUM-1）: motion（physics_tick clock）と speech·anim（agent_tick clock）は
    別 clock domain の独立系列として再生（join しない）。
  - **headless モード**（§3.4、CI 検証用）: `--headless` + CLI 引数（`--manifest --trace --stream --dump=<path>`）で
    per-(physics_tick_index, order_slot) の解決済み avatar transform（committed trace echo）+ 発火 envelope kind 列を
    `--dump=<path>` に出力。scene 実体化は最小（transform 解決のみ、描画不要）。dump schema = decisions.md 判断5:
    - motion 行: `{"kind":"placement","physics_tick_index":int,"order_slot":int,"x":f,"y":f,"z":f,"yaw":f,"zone":str}`
      （trace echo、float は committed 値をそのまま文字列化 = Godot 側で再フォーマットしない。Python test が正規化）。
    - envelope 行: `{"kind":"envelope","order_slot":int,"agent_tick":int,"seq":int,"envelope_kind":str}`
      （speech/animation のみ、move 除外）。
  - **interactive モード**（開発者観察用）: 時系列再生。dev-only。
  - denylist token（measurement）を import/identifier/dict-key/artifact filename に持たない（I1 guard 対象）。
- 新規 `godot_project/scenes/dev/SocietyReplayScene.tscn`（dev-only 全景 wrapper）:
  - 既存 `scenes/zones/*.tscn`（5 zone、**read-only 参照 = instance で合成**）+ `BaseTerrain.tscn` +
    N 体の primitive avatar（`AgentAvatar.tscn` 系）を order_slot 順に配置。
  - production `MainScene.tscn` とは別 boot path（dev/README.md 規約）。
### Out
- headless dump 検証 test + expected_placement.jsonl（I6）。5 zone load boolean test（I6）。
  EclReplayPlayer.gd / MainScene.tscn / WS graph の改変（無改変厳守）。既存 zone .tscn の改変（read-only、
  root transform 是正は I2 で完了済）。.glb の scene wiring（判断3 = decouple、primitive avatar/zone で足りる）。measurement 一切。

## Allowed Files
- `godot_project/scripts/dev/SocietyReplayViewer.gd`（新規）
- `godot_project/scenes/dev/SocietyReplayScene.tscn`（新規）
- `godot_project/scripts/dev/README.md`（新 viewer の boot path 記述追記、任意）
- **無改変厳守**: EclReplayPlayer.gd / MainScene.tscn / WorldManager/WebSocketClient/EnvelopeRouter/AgentManager /
  既存 scenes/zones/*.tscn / AgentAvatar.tscn / BaseTerrain.tscn / handoff.py / 凍結 apparatus

## Acceptance Criteria（AC↔test）
- I5-G1（本 issue の smoke、I6 で本検証）: `SocietyReplayViewer.gd` が headless（`GODOT_BIN --headless`）で
  golden を読み dump を出力できる（exit 0、dump ファイル生成）。role split（motion=trace / speech·anim=envelope、
  move 非位置）を実装。
- I5-G2: `SocietyReplayScene.tscn` が headless で load 可能（5 zone .tscn + BaseTerrain + 2 avatar 合成、parse エラーなし）。
- I5-G3: EclReplayPlayer.gd / MainScene.tscn byte 無改変（git diff 空）。
- I5-G4: 新規 .gd が I1 measurement guard（.gd text scan）に通る（denylist 非在）。
- CI parity: `bash scripts/dev/pre-push-check.sh` 4 段 `ALL CHECKS PASSED`（Godot 非依存 test は緑、Godot smoke は
  GODOT_BIN 有りで実走 / 無しで skip）。

## Test Plan
`GODOT_BIN` 設定下で headless smoke（viewer が golden を dump、scene が load）。実際の byte 一致検証は I6。
`_godot_helpers.py::resolve_godot()` パターンで Godot 解決、不在時 skip（既存慣習）。git diff で EclReplayPlayer.gd/
MainScene.tscn 無改変確認。

## Stop Conditions
- 全 AC 緑（Done）。
- role split が実装できず motion に envelope move を使いたくなる → Stop（§3.3 binding 違反、位置権威は trace のみ）。
- order_slot で motion と envelope を join したくなる → Stop（MEDIUM-1、別 clock domain 独立系列）。
- EclReplayPlayer.gd を改変しないと動かない → Stop（判断4 無改変、新規 viewer は別責務。改変が要れば superseding ADR）。
- Godot 4.6.2 で GDScript API が想定と違う → blockers.md、HOW 越える判断なら Stop→ADR。
- 凍結 apparatus / MainScene 改変を要する → Stop。budget 到達 → Stop。

## Dependencies
- なし（golden fixtures は committed 済、read-only 消費）。I6 が本 viewer を検証。
- I1（guard が .gd を対象に含む）。

## Status
done

## Execution Result
実装ファイル（Allowed Files のみ）:
- `godot_project/scripts/dev/SocietyReplayViewer.gd`（新規、dev-only、`extends SceneTree`、role split 実装）
- `godot_project/scenes/dev/SocietyReplayScene.tscn`（新規、dev-only 全景 wrapper、5 zone + BaseTerrain + 2 avatar 合成）
- `godot_project/scripts/dev/README.md`（新 viewer の boot path 追記）

AC 検証（GODOT_BIN = Godot 4.6.2 headless）:
- **I5-G1** headless dump smoke: exit 0、dump 生成。40 placement 行（physics_tick_index 昇順 → order_slot 昇順）+ 16 envelope 行（speech 8 + animation 8、move 8 は除外、order_slot→agent_tick→seq 昇順）。role split（motion=trace pass-through echo / speech·anim=envelope、move 非位置、join なし）実装。
- **I5-G2** scene load smoke: `SocietyReplayScene.tscn` を headless で `--quit-after 2` load、exit 0、parse エラー無し。
- **I5-G3** EclReplayPlayer.gd / MainScene.tscn: `git diff` 空（byte 無改変）。
- **I5-G4** `pytest -q tests/test_integration/test_m4_viz_measurement_guard.py` = 34 passed（新規 .gd が denylist text scan 通過）。
- 追加: 同一 golden 2 回 dump = byte 一致（決定性、I6 の本検証は別 issue）。

HOW 越え / Stop 抵触: 無し。EclReplayPlayer.gd / MainScene.tscn / 既存 zone .tscn / AgentAvatar.tscn / BaseTerrain.tscn は全て read-only 参照（無改変）。measurement 面ゼロ。
