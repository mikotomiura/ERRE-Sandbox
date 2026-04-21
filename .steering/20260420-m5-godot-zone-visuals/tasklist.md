# タスクリスト — m5-godot-zone-visuals

## 準備

- [x] docs/repository-structure.md を Read
- [x] .claude/skills/godot-gdscript/SKILL.md を Read
- [x] file-finder / impact-analyzer で既存パターン・影響範囲調査
- [x] design.md (hybrid 採用版) 確定、impact-analyzer 発見事項 (FixturePlayer 拡張)
      と M4 live 違和感対処 (BaseTerrain + Peripatos 装飾 retreat) を取り込み済
- [ ] `feature/m5-godot-zone-visuals` branch を切る

## 実装 — Phase 1: 基盤 (ERREModeTheme + material 複製)

- [ ] `godot_project/scripts/theme/` ディレクトリ新設
- [ ] `godot_project/scripts/theme/ERREModeTheme.gd` を新規作成
  - `class_name ERREModeTheme`
  - `const COLORS: Dictionary` に 8 mode → Color:
    peripatetic=Color(0.95, 0.90, 0.55) / chashitsu=Color(0.70, 0.88, 0.70) /
    zazen=Color(0.65, 0.75, 0.92) / deep_work=Color(0.98, 0.98, 0.98) /
    shallow=Color(0.62, 0.62, 0.62) / shu_kata=Color(0.80, 0.65, 0.48) /
    ha_deviate=Color(0.98, 0.72, 0.40) / ri_create=Color(0.82, 0.65, 0.92)
  - `static func color_for(mode: String) -> Color` with white fallback + push_warning
- [ ] `godot_project/scenes/agents/AgentAvatar.tscn` の Body material_override に
      `resource_local_to_scene = true` を付与 (scene 側複製)

## 実装 — Phase 2: BodyTinter + DialogBubble

- [ ] `godot_project/scripts/agents/` ディレクトリ新設
- [ ] `godot_project/scripts/agents/BodyTinter.gd` を新規作成
  - `extends MeshInstance3D`, `class_name BodyTinter`
  - `const TINT_TWEEN_DURATION_SEC: float = 0.3`
  - `var _current_mode: String = ""`、`var _current_tween: Tween = null`
  - `func apply_mode(mode: String) -> void`:
    - 同じ mode なら no-op
    - 前 Tween を kill
    - `var target_color := ERREModeTheme.color_for(mode)`
    - Tween で `material_override:albedo_color` を target_color へ遷移
    - `print("[BodyTinter] mode=%s color=(%.2f, %.2f, %.2f)" % ...)`
- [ ] `godot_project/scripts/agents/DialogBubble.gd` を新規作成
  - `extends Label3D`, `class_name DialogBubble`
  - `const FADE_IN_SEC: float = 0.3`, `const FADE_OUT_SEC: float = 0.3`
  - `var _current_tween: Tween = null`
  - `func show(text: String, duration_s: float) -> void`:
    - 前 Tween を kill、text 設定、visible=true
    - Tween で modulate.a を 0→1 (fade_in) → sustain (duration_s) → 1→0 (fade_out) → visible=false
    - `print("[DialogBubble] show agent_id=%s len=%d" % ...)` (agent_id は親から取得)
  - `func hide_now() -> void`: 前 Tween kill、modulate.a=0、visible=false
- [ ] `AgentAvatar.tscn` の `$Body` ノードに `script = ExtResource(BodyTinter.gd)` 付与
- [ ] `AgentAvatar.tscn` に新規子ノード `DialogBubble` (Label3D) 追加
  - transform=Vector3(0, 2.2, 0.3) (SpeechBubble 横)、billboard=1、pixel_size=0.008、
    outline_size=8、modulate=Color(1,1,1,0)、visible=false
  - `script = ExtResource(DialogBubble.gd)` 付与

## 実装 — Phase 3: AgentController 調停 + AgentManager wiring

- [ ] `godot_project/scripts/AgentController.gd` を修正
  - `@onready var _dialog_bubble: Node3D = $DialogBubble` 追加
  - `@onready var _body_tinter: Node = $Body` (BodyTinter) 追加
  - `const DEFAULT_DIALOG_DURATION_SEC: float = 4.0` 追加
  - `func show_dialog_turn(utterance: String) -> void` 追加:
    - `_dialog_bubble.show(utterance, DEFAULT_DIALOG_DURATION_SEC)`
    - `print("[AgentController] show_dialog_turn agent_id=%s len=%d" % ...)`
  - `func apply_erre_mode(mode: String) -> void` 追加:
    - `_body_tinter.apply_mode(mode)`
    - `print("[AgentController] apply_erre_mode agent_id=%s mode=%s" % ...)`
- [ ] `godot_project/scripts/AgentManager.gd` を修正
  - `_REQUIRED_SIGNALS` に `"dialog_turn_received"` を追加
  - `router.dialog_turn_received.connect(_on_dialog_turn_received)` を `_ready` に追加
  - `func _on_dialog_turn_received(dialog_id, speaker_id, addressee_id, utterance) -> void`:
    - `_get_or_create_avatar(speaker_id)` で lookup
    - `avatar.show_dialog_turn(utterance)` を呼ぶ
  - `_on_agent_updated` の拡張: `agent_state.get("erre", {}).get("name", "")` を
    取って非空なら `avatar.apply_erre_mode(mode)`

## 実装 — Phase 4: Zone シーン (BaseTerrain + Chashitsu + Zazen)

- [ ] `godot_project/scenes/zones/BaseTerrain.tscn` を新規作成
  - PlaneMesh 60×60、StandardMaterial3D albedo_color(0.45, 0.42, 0.38) roughness=0.9
  - root Node3D の transform translation y=-0.02
- [ ] `godot_project/scenes/zones/Chashitsu.tscn` を新規作成
  - PlaneMesh 30×30、StandardMaterial3D albedo_color(0.55, 0.42, 0.30) roughness=0.85
  - root Node3D の transform translation z=+15, y=0
- [ ] `godot_project/scenes/zones/Zazen.tscn` を新規作成
  - PlaneMesh 30×30、StandardMaterial3D albedo_color(0.50, 0.50, 0.52) roughness=0.85
  - root Node3D の transform translation z=-15, y=0
- [ ] `godot_project/scripts/WorldManager.gd` の `ZONE_MAP` に 3 entry 追加
  - `"base_terrain"` を dict 先頭 (最初に spawn)、`"chashitsu"` / `"zazen"` を続けて追加

## 実装 — Phase 5: Peripatos 装飾 retreat (M4 live 違和感対処)

- [ ] `godot_project/scenes/zones/Peripatos.tscn` を修正
  - StartMarker, EndMarker ノード削除
  - 不要になる SubResource("3_marker") BoxMesh を削除
  - PostN0-N3 の transform Z=-2 → Z=-3 に変更
  - PostS0-S1 の transform Z=+2 → Z=+3 に変更
  - Light / Ground / PostN*-PostS* / material は維持

## 実装 — Phase 6: FixturePlayer 拡張

- [ ] `godot_project/scripts/dev/FixturePlayer.gd` の `DEFAULT_PLAYLIST` を拡張
  - 末尾に `dialog_initiate.json`, `dialog_turn.json`, `dialog_close.json` の 3 件追加
- [ ] `tests/test_godot_ws_client.py` の `_EXPECTED_PLAYBACK_ORDER` を同期
  - 末尾に `dialog_initiate`, `dialog_turn`, `dialog_close` を追加

## テスト

- [ ] `tests/test_godot_dialog_bubble.py` を新規作成
  - harness_result fixture (共有、test_godot_peripatos.py 準拠)
  - `test_dialog_turn_dispatched_to_speaker`: stdout に
    `[AgentController] show_dialog_turn agent_id=a_kant_001 len=...` を assert
  - `test_dialog_bubble_invoked`: stdout に
    `[DialogBubble] show agent_id=a_kant_001 len=...` を assert
  - `test_no_unknown_kind_warning`: `"Unknown kind"` が無いこと
- [ ] `tests/test_godot_mode_tint.py` を新規作成
  - harness_result fixture (共有)
  - `test_apply_erre_mode_from_agent_update`: stdout に
    `[AgentController] apply_erre_mode agent_id=a_kant_001 mode=peripatetic` を assert
  - `test_body_tinter_applied`: stdout に `[BodyTinter] mode=peripatetic color=(...)` を assert
- [ ] `uv run pytest tests/test_godot_dialog_bubble.py tests/test_godot_mode_tint.py -v`
      で新規 test PASS
- [ ] `uv run pytest -q` で既存 513 test + 新規 = 全 PASS (Godot 未 install 環境は skip)
- [ ] `uv run ruff check tests/` / `uv run ruff format --check tests/` PASS
- [ ] Godot editor で MainScene を 30s 手動再生、30Hz / bubble / tint を目視確認

## レビュー

- [ ] `code-reviewer` sub-agent を起動して GDScript + .tscn diff をレビュー
- [ ] HIGH 指摘は必ず対応、MEDIUM はユーザー判断、LOW は blockers.md に記録
- [ ] `security-checker` は外部入力無しのため起動しない (本 PR は外部 input 非依存)

## ドキュメント

- [ ] `docs/functional-design.md` の M5 視覚化節を「M5 で実装」から
      「M5-MacBook 側実装完了」に更新 (軽微)
- [ ] `docs/glossary.md` の用語追加は不要 (新規固有用語なし)

## 完了処理

- [ ] `decisions.md` を作成 (hybrid 採用、BaseTerrain 追加、Peripatos retreat
      の 3 判断を記録)
- [ ] tasklist.md 全項目チェック
- [ ] `git commit` (Conventional Commits: `feat(godot): add M5 dialog bubble,
      ERRE mode tint, and zone visuals (Chashitsu/Zazen/BaseTerrain)`)
- [ ] `git push -u origin feature/m5-godot-zone-visuals`
- [ ] PR 作成 → self-review → merge
- [ ] MEMORY.md に M5 視覚化完了の参照追加 (必要なら、軽微なら skip)

## 制約・リマインダ

- Python 側 (`src/erre_sandbox/`) は一切触らない (G-GEAR 並列作業と干渉しないため)
- `main` 直 push 禁止、feature branch + PR 必須
- 既存 513 test に regression 起こさない (test_godot_peripatos の期待値確認)
- `.tscn` の手動編集は最小限、WorldManager.ZONE_MAP 経由で zone 追加
- GPL ライブラリ import は Godot 側には関係なし
- material_override の per-instance 化は scene 側 `resource_local_to_scene=true`
  で完結 (BodyTinter で duplicate しない)
