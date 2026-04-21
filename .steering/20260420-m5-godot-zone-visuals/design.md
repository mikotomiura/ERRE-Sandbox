# 設計 — m5-godot-zone-visuals (hybrid 採用版)

## 実装アプローチ

**Godot-native composition (v2 ベース) + scene-side material 複製 (v1 採用)** の
hybrid。視覚化の責務を AgentController 直下の小ノード + const-only script に
分散し、controller を肥大化させない。一方で material per-instance 化は scene
属性一発で済ませ、runtime コードを最小化する。

### 3 つの独立コンポーネント

1. **DialogBubble (Label3D + 専用 script)**
   - `AgentAvatar.tscn` に `$DialogBubble` Label3D を **直接追加** (packed scene
     分離はしない。ファイル数最小化のため)
   - `godot_project/scripts/agents/DialogBubble.gd` をその Label3D にアタッチ
   - 公開 API: `show(text: String, duration_s: float)` / `hide_now()`
   - 内部: Tween で modulate.a を 0→1 (0.3s fade-in) → 保持 → 1→0 (0.3s fade-out)、
     replace semantics (連続呼出しで前 Tween を kill)
   - SpeechBubble (既存) とは別 Label3D、z=+0.3m 程度ずらして重ならない配置
2. **BodyTinter (Body MeshInstance3D に attach する script)**
   - `godot_project/scripts/agents/BodyTinter.gd` を `$Body` にアタッチ
   - 公開 API: `apply_mode(mode: String)`
   - 内部: 0.3s Tween で `material_override.albedo_color` を遷移 (hard swap せず
     strobe 回避)。前 Tween は kill して replace
   - **material 複製は scene 側で完結** — `AgentAvatar.tscn` の Body
     `material_override` SubResource に `resource_local_to_scene = true` を付与し、
     BodyTinter 側で `.duplicate()` を呼ばない (v1 採用の簡潔さ)
3. **ERREModeTheme (const-only script)**
   - `godot_project/scripts/theme/ERREModeTheme.gd`
   - `class_name ERREModeTheme` を宣言 (static func 呼出しのみなので T16
     judgement 4 の cross-ref TYPE 問題には当たらない)
   - `const COLORS: Dictionary` に 8 mode → Color:
     peripatetic=淡黄 / chashitsu=淡緑 / zazen=淡青 / deep_work=白 /
     shallow=灰 / shu_kata=淡茶 / ha_deviate=淡橙 / ri_create=淡紫
   - `static func color_for(mode: String) -> Color`: 未知 mode は白 fallback +
     push_warning

### AgentController は調停のみ

```gdscript
@onready var _dialog_bubble: Node3D = $DialogBubble   # Label3D + DialogBubble.gd
@onready var _body_tinter: Node = $Body                # MeshInstance3D + BodyTinter.gd

const DEFAULT_DIALOG_DURATION_SEC: float = 4.0

func show_dialog_turn(utterance: String) -> void:
    _dialog_bubble.show(utterance, DEFAULT_DIALOG_DURATION_SEC)
    print("[AgentController] show_dialog_turn agent_id=%s len=%d" % [agent_id, utterance.length()])

func apply_erre_mode(mode: String) -> void:
    _body_tinter.apply_mode(mode)
    print("[AgentController] apply_erre_mode agent_id=%s mode=%s" % [agent_id, mode])
```

既存 `show_speech` / `set_move_target` / `set_animation` / `update_position_from_state`
は無変更。M4 互換を保つ。

### AgentManager の signal wiring (M5 scope を最小化)

- `dialog_turn_received` のみ新規 connect → `show_dialog_turn`
- `dialog_initiate_received` / `dialog_close_received` は **M5 では connect しない** (yagni)
  - bubble は Tween で自然消滅するので close signal に頼る必要なし
  - initiate の向き調整は M6 以降
- `agent_updated` handler を拡張: `agent_state.erre.name` を読んで
  `avatar.apply_erre_mode(name)` を呼ぶ (nil-safe、未知値なら ERREModeTheme が
  白 fallback)

### Zone MVP = plane + material のみ + 下敷き BaseTerrain

装飾オブジェクト (座布団 / 岩 / 灯篭等) は全て M6 以降へ deferral。

- `scenes/zones/BaseTerrain.tscn` (新規): 60×60 PlaneMesh + 中立土色
  (0.45, 0.42, 0.38) + roughness=0.9 at Y=-0.02。全 zone の下敷きとして
  MainScene 全体をカバー。**M4 live で観察された「avatar が void 上を歩く」
  違和感の対処**。ZONE_MAP の先頭に置き、他 zone より先に spawn させる
- `scenes/zones/Chashitsu.tscn`: PlaneMesh (30x30) + albedo_color(0.55, 0.42, 0.30) at Y=0
- `scenes/zones/Zazen.tscn`: PlaneMesh (30x30) + albedo_color(0.50, 0.50, 0.52) at Y=0
- 各 zone plane の root Node3D に transform を持たせ、Peripatos (40x4) の
  長手方向 X 軸と衝突しない Z 位置に配置: Chashitsu を Z=+15、Zazen を Z=-15
- `WorldManager.ZONE_MAP` に `base_terrain` / `chashitsu` / `zazen` の
  3 entry preload を追加 (base_terrain が dict 先頭 = spawn 順先頭)。
  MainScene.tscn は無変更 (T17 judgement 9)

### Peripatos.tscn の装飾物 retreat (M4 live 観察の #1 対処)

`scenes/zones/Peripatos.tscn` の以下を修正:

- **StartMarker / EndMarker を削除** — 歩行線 Z=0 上の 1.4×1.0×0.8 ボックスで、
  Tween 直動かしの AgentController では貫通が常態化。MVP で landmark 役は
  BaseTerrain の視覚分離で代替可能、acceptance 非依存なので削除
- **PostN0-N3 を Z=-3 に移動** (元 Z=-2) — Peripatos plane (Z=±2) の外側、
  BaseTerrain 上に立つ形に
- **PostS0-S1 を Z=+3 に移動** (元 Z=+2) — 同上
- StartMarker/EndMarker 用 SubResource (3_marker) は不要化するので
  削除、`5_markermat` は Post 用に残す

ロジック追加 (CharacterBody3D 化 / AABB clamp 等) は行わない。Python 側が
妥当な世界座標を送る前提を維持し、BaseTerrain による「最低限 void 上に
乗らない」保証のみで MVP の違和感を解消する。厳密な zone 境界強制は
Python 側 `world/zones.py` + `m5-world-zone-triggers` (G-GEAR) に委ねる。

## 変更対象

### 修正するファイル

- `godot_project/scripts/AgentController.gd`
  - `@onready var _dialog_bubble: Node3D = $DialogBubble`
  - `@onready var _body_tinter: Node = $Body`
  - `const DEFAULT_DIALOG_DURATION_SEC: float = 4.0`
  - `show_dialog_turn(utterance)` / `apply_erre_mode(mode)` の 2 調停 method 追加
  - 既存 method は無変更
- `godot_project/scripts/AgentManager.gd`
  - `_REQUIRED_SIGNALS` に `dialog_turn_received` を追加 (initiate/close は追加しない)
  - `_on_dialog_turn_received(dialog_id, speaker_id, addressee_id, utterance)` 追加
  - `_on_agent_updated` を拡張: erre.name nil-safe 取得 → `apply_erre_mode`
- `godot_project/scripts/WorldManager.gd`
  - `ZONE_MAP` に `"base_terrain"` (dict 先頭) / `"chashitsu"` / `"zazen"` の
    3 preload 追加
- `godot_project/scenes/zones/Peripatos.tscn`
  - StartMarker / EndMarker ノードと関連 SubResource("3_marker") を削除
  - PostN0-N3 を Z=-3、PostS0-S1 を Z=+3 に移動 (歩行線から退避)
- `godot_project/scripts/dev/FixturePlayer.gd`
  - `DEFAULT_PLAYLIST` に `dialog_initiate.json` / `dialog_turn.json` /
    `dialog_close.json` を末尾 3 件追加 (test_godot_dialog_bubble が replay
    するため必要。既存 7 kind の後ろに足すので order 的に後方互換)
- `tests/test_godot_ws_client.py`
  - `_EXPECTED_PLAYBACK_ORDER` に `dialog_initiate` / `dialog_turn` /
    `dialog_close` を末尾追加 (FixturePlayer.gd の DEFAULT_PLAYLIST 変更に同期)
- `godot_project/scenes/agents/AgentAvatar.tscn`
  - `$Body` の `material_override` SubResource に `resource_local_to_scene = true` 付与
  - `$Body` ノードに `script = ExtResource(BodyTinter.gd)` を attach
  - `$DialogBubble` Label3D を新規追加 (billboard / pixel_size=0.008 /
     outline_size=8 / transform offset=Vector3(0, 2.2, 0.3) / modulate=Color(1,1,1,0))
  - `$DialogBubble` ノードに `script = ExtResource(DialogBubble.gd)` を attach
  - 既存 `$SpeechBubble` は無変更

### 新規作成するファイル (7 件)

- `godot_project/scripts/agents/DialogBubble.gd`
  - `show(text, duration_s)` / `hide_now()`、Tween + Timer、replace semantics
- `godot_project/scripts/agents/BodyTinter.gd`
  - `apply_mode(mode)`、0.3s Tween で albedo_color 遷移、前 Tween kill
- `godot_project/scripts/theme/ERREModeTheme.gd`
  - `class_name ERREModeTheme`、`const COLORS`、`static func color_for(mode)`
- `godot_project/scenes/zones/BaseTerrain.tscn` — 60×60 PlaneMesh + 中立土色
  material at Y=-0.02 (全 zone の下敷き、#2 void 歩行違和感の対処)
- `godot_project/scenes/zones/Chashitsu.tscn` — 30×30 PlaneMesh + 木目色
  material at Z=+15
- `godot_project/scenes/zones/Zazen.tscn` — 30×30 PlaneMesh + 石畳色
  material at Z=-15
- `tests/test_godot_dialog_bubble.py` — fixture replay + 3 段 assertion
- `tests/test_godot_mode_tint.py` — fixture replay + 3 段 assertion

### 削除するファイル

- なし (全て additive)

### 新規 fixture (必要なら)

- 既存 `fixtures/control_envelope/dialog_turn.json` / `agent_update.json` を利用
- `agent_update.json` に `erre.name=chashitsu` が含まれているか確認し、無ければ
  test 専用 sub-fixture を tests 側で dict 合成 (fixtures/ の golden は触らない)

## 影響範囲

- **Python 側 (`src/erre_sandbox/`)**: 一切変更なし
- **MainScene.tscn**: 編集なし (ZONE_MAP 経由で zone 追加)
- **SpeechBubble の挙動**: 変更なし、dialog_turn とは別チャネル
- **3 avatar 同時 tint 干渉**: `resource_local_to_scene = true` で scene
  instantiate 時に material 複製される (v1 採用の最小コード)
- **既存 test_godot_peripatos の期待値**: ZONE_MAP に 2 entry 追加されるので
  boot log に `[WorldManager] zone spawned name=chashitsu` / `...=zazen` が増える。
  既存 assertion は substring match なので理論上は無回帰、事前確認する
- **30Hz 維持**: zone を plane + material のみに抑える (装飾ゼロ) ことで
  rendering cost は M4 比で 2 plane + 2 material 追加のみ
- **EnvelopeRouter signal 整合**: `dialog_turn_received` は既に EnvelopeRouter.gd:26
  で宣言済み。AgentManager の `_REQUIRED_SIGNALS` 追加で `has_signal` ガードは
  通過する
- **FixturePlayer.gd の playlist 拡張**: DEFAULT_PLAYLIST を 7 → 10 kind に
  拡張。test_godot_ws_client.py の `_EXPECTED_PLAYBACK_ORDER` も同期して拡張
  (連動必須、別コミットに分離しない)
- **`fixtures/control_envelope/` は無変更**: agent_update.json に既に
  `erre.name="peripatetic"` あり、dialog_turn.json も M4 から存在

## 既存パターンとの整合性

- **composition**: WorldManager (シーン管理) / EnvelopeRouter (signal 多重化)
  で既に採用されている責務分離思想を avatar 内部にも延伸
- **preload-based dependency**: `ERREModeTheme` は autoload ではなく preload、
  WorldManager.ZONE_MAP と同パターン
- **fixture-gated test**: `tests/test_godot_peripatos.py` の harness_result
  共有 fixture pattern を複製、stdout prefix assertion を踏襲
- **log prefix**: `[DialogBubble] ...` / `[BodyTinter] ...` / `[AgentController] ...`
  を 3 段にして、委譲チェーンを stdout から追える
- **class_name 宣言**: ERREModeTheme は static func 呼出しのみなので
  cross-ref TYPE annotation 問題 (T16 judgement 4) には当たらない。
  IDE 補完向上のため宣言する

## テスト戦略

### Godot fixture-gated 統合 (新規 2 本)

- **`tests/test_godot_dialog_bubble.py`**:
  - fixture `dialog_turn.json` を FixtureHarness に流す
  - stdout で以下 3 段の log を assert:
    1. `[AgentManager] avatar spawned agent_id=a_kant_001` (既存)
    2. `[AgentController] show_dialog_turn agent_id=a_kant_001 len=N` (新規)
    3. `[DialogBubble] show agent_id=a_kant_001 len=N` (新規)
  - 委譲チェーンが壊れた時にどの段で落ちたか特定できる
- **`tests/test_godot_mode_tint.py`**:
  - fixture `agent_update.json` の `erre.name` を確認 (無ければ test 内で
    dict 合成して FixtureHarness に渡せるか要確認、ダメなら fixture 追加を検討)
  - stdout で:
    1. `[AgentController] apply_erre_mode agent_id=... mode=chashitsu` (新規)
    2. `[BodyTinter] mode=chashitsu color=(0.7, 0.9, 0.7)` (新規)
  - Tween 完了の assert は fragile なので行わない。log のみ

### 既存 regression

- `uv run pytest -q` で 513 test → 515 test PASS (新規 2 本含む)
- `test_godot_peripatos.py` の zone spawned assertion が壊れないことを確認
  (ZONE_MAP に 2 entry 増えただけで Peripatos spawn の log 自体は出る)

### Live acceptance (M5 #5/#6)

- MacBook で `godot --editor` → MainScene → 60s 実行
- bubble 表示 / mode tint 変化 / 30Hz 維持 を mp4 録画
- FPS overlay (F3) で 30Hz を目視確認

## ロールバック計画

- **最速**: `git revert <merge-commit>` (PR 単位)
- **部分**: AgentManager の dialog_turn_received connect をコメントアウト
  → bubble は noop、M4 挙動
- **mode tint のみ**: `AgentController.apply_erre_mode` の中身をコメントアウト
  → tint は初期色固定、bubble は生きる
- **zone**: `WorldManager.ZONE_MAP` から 2 entry 削除 → zone 非表示
- **feature flag**: Python 側 `--disable-dialog-turn` (M5 plan 判断 6) で
  dialog_turn envelope 自体が送られなくなる。Godot 側は受動的に noop 化

Godot 側固有の flag は導入しない (起動 determinism 保持)。

## リスクと対策

- **リスク 1**: DialogBubble と SpeechBubble が別 Label3D でもカメラ角度に
  よって重なる
  - **対策**: z=+0.3m ずらす + live acceptance 録画で確認、必要なら座標再調整
- **リスク 2**: Tween による tint 遷移 (0.3s) が FSM 極短周期振動 (< 0.3s) 時に
  中間色で止まる
  - **対策**: `apply_mode` 内で前 Tween を kill してから新 Tween 開始 (replace)
    → 振動中も最新 mode の色が最終到達先になる
- **リスク 3**: `agent_update.json` fixture に `erre.name` が含まれていない
  可能性 (M4 schema では optional)
  - **対策**: fixture を確認して無ければ tests 内で dict を合成するか、
    test 専用の in-memory fixture を作る (golden は触らない)
- **リスク 4**: `resource_local_to_scene = true` を付けた material が
  既存 test_godot_peripatos の regression を起こす
  - **対策**: Peripatos は別 scene なので Body の material には影響しない、
    事前に手元で peripatos fixture を流して確認
- **リスク 5**: Chashitsu / Zazen の plane 配置が Peripatos と重なる
  - **対策**: Peripatos は `size=Vector2(40, 4)`、長手方向に走る。Chashitsu を
    Z=+15, Zazen を Z=-15 に配置して視覚的に重ならない位置を取る
    (MainScene で ZoneManager に transform を持たせない場合、WorldManager 側で
    spawn 後 translate。ただし WorldManager の MVP 改変は本 PR scope 外なので、
    各 zone scene 側の root Node3D に transform を持たせて対応)

## 設計判断の履歴

- 初回案 (design-v1.md) と再生成案 (v2) を比較 → `design-comparison.md`
- 採用: **hybrid** (v2 ベース + v1 の scene-side material 複製)
- 根拠 (ユーザー判断 2026-04-20):
  1. v2 の composition は AgentController 肥大化を止め、M6 以降の視覚機能
     追加に拡張性がある
  2. v1 の `resource_local_to_scene = true` は material 複製を scene 属性
     一発で済ませ、BodyTinter のコードを最小化できる
  3. dialog_initiate / dialog_close の connect は M5 acceptance には不要 (yagni)
  4. Zone 装飾ゼロは acceptance 受け入れ条件を最小で満たし、30Hz リスクを
     最小化 (構図工夫で録画品質は担保)
  5. 新規ファイル数 7 は v1 (4) と v2 (8) の中間、PR size として妥当
