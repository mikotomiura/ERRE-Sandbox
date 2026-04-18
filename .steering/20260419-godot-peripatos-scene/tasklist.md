# T17 godot-peripatos-scene — タスクリスト

採用設計 (v2) に基づく。各タスク **30 分以内** を目安に粒度分割。

## Step A/B/C ✓ (完了済)
- [x] implementation-workflow Skill Read (T16 session で実施)
- [x] docs (architecture / development-guidelines / repository-structure) Read
- [x] requirement.md Read
- [x] file-finder で既存 Godot 資産 + patterns.md §3/§4 テンプレ取得
- [x] impact-analyzer で MainScene / AgentManager 変更影響分析
- [x] design.md v1 初回案作成 (8 弱点明示)
- [x] /reimagine で v2 再生成
- [x] design-comparison.md で比較 → **v2 採用確定**

## Step D (本ステップ) ✓
- [x] tasklist.md を v2 設計に即して分解

## Step E: 実装

### E-1: Peripatos scene 新規作成
- [ ] `godot_project/scenes/zones/Peripatos.tscn` を作成
      - [ ] Node3D ルート (name=Peripatos)
      - [ ] Ground (MeshInstance3D + PlaneMesh 40×4m) + StandardMaterial3D (淡色)
      - [ ] StartMarker (位置 -20, 0.5, 0) + EndMarker (位置 +20, 0.5, 0) BoxMesh
      - [ ] Post0..5 (-16, -8, 0, +8, +16 × 南北 z=±2) BoxMesh 計 6 本
      - [ ] OmniLight3D (位置 0, 10, 0、omni_range=30)

### E-2: AgentAvatar scene 新規作成
- [ ] `godot_project/scenes/agents/AgentAvatar.tscn` を作成
      - [ ] Node3D ルート (AgentAvatar)
      - [ ] Body (MeshInstance3D + CapsuleMesh 高 1.8m)
      - [ ] Facing (MeshInstance3D + BoxMesh、local +Z で前方指示、位置 0, 1.0, 0.3)
      - [ ] SpeechBubble (Label3D、visible=false 初期、位置 0, 2.2, 0、
            billboard=Y)
      - [ ] ext_resource で AgentController.gd を attach

### E-3: AgentController.gd 新規作成
- [ ] `godot_project/scripts/AgentController.gd` を作成 (v2 design 参照)
      - [ ] `extends Node3D` (class_name なし)
      - [ ] `@export agent_id` + `@onready _body` + `@onready _speech_bubble`
      - [ ] `_current_animation: String = "idle"` / `_current_tween: Tween = null`
      - [ ] `set_agent_id(new_id)` — agent_id + name を同期
      - [ ] `update_position_from_state(agent_state)` — position から Vector3 セット
      - [ ] `set_move_target(target, speed)` — Tween 駆動、speed 使用、
            `max(speed, 0.01)` guard、`look_at` 前処理
      - [ ] `set_animation(animation_name)` — _current_animation 保持 + print
      - [ ] `show_speech(utterance, zone)` — Label3D.text / visible + print

### E-4: AgentManager.gd 書き換え
- [ ] `const AVATAR_SCENE := preload("res://scenes/agents/AgentAvatar.tscn")`
- [ ] `var _avatars: Dictionary = {}`
- [ ] `_get_or_create_avatar(agent_id) -> Node` + `[AgentManager] avatar spawned` ログ
- [ ] `_on_agent_updated` → `_get_or_create_avatar` + `update_position_from_state`
- [ ] `_on_speech_delivered` → `avatar.show_speech`
- [ ] `_on_move_issued` → `avatar.set_move_target`
- [ ] `_on_animation_changed` → `avatar.set_animation`
- [ ] `_REQUIRED_SIGNALS` と `_resolve_router` は **不変** (T16 判断 4 維持)

### E-5: WorldManager.gd 拡張
- [ ] `const ZONE_MAP: Dictionary = { "peripatos": preload(...) }` (M5 コメント付き)
- [ ] `_ready()` 末尾で `_spawn_initial_zones()` 呼び出し
- [ ] `_spawn_initial_zones()` — ZoneManager 配下に全 ZONE_MAP エントリ instance
      + `[WorldManager] zone spawned name=<name>` ログ
- [ ] 既存 router signal connect (T16) は不変

### E-6: tests 拡張
- [ ] `tests/test_godot_project.py` の `test_required_project_files_exist` に
      3 ファイル assertion 追加
- [ ] `tests/test_godot_peripatos.py` を新規作成
      - [ ] `@pytest.fixture(scope="module") def harness_result`
      - [ ] 6 assertion:
            (1) zone spawned / (2) avatar spawned / (3) speech reaches avatar /
            (4) move uses envelope speed=1.30 / (5) animation set walk /
            (6) no errors, rc==0

### E-7: tasklist 更新
- [ ] 実装完了タスクを順次チェック

## Step F: テストと検証
- [ ] `uv run pytest tests/test_envelope_kind_sync.py -v` (T16 ガード維持確認)
- [ ] `uv run pytest tests/test_godot_project.py -v` (拡張後も通る)
- [ ] `uv run pytest tests/test_godot_ws_client.py -v` (T16 契約不変、通る)
- [ ] `uv run pytest tests/test_godot_peripatos.py -v` (新規、全 6 pass)
- [ ] `uv run pytest tests/` 全体緑 (100+ pass のベース維持)
- [ ] `uv run ruff check .` / `uv run ruff format --check .` 緑
- [ ] `uv run mypy src tests` 緑

## Step G: code-reviewer
- [ ] `code-reviewer` サブエージェント起動
- [ ] HIGH → 必ず修正 / MEDIUM → ユーザー確認 / LOW → blockers.md

## Step H: security-checker (評価)
- [ ] envelope の Vector3 変換 (NaN / inf / 巨大値) の安全性確認
- [ ] Tween duration=0/負値の crash 可能性
- [ ] `security-checker` 軽量起動 (200 行以内のレポート依頼)

## Step I: ドキュメント更新
- [ ] `docs/functional-design.md` 更新判断
- [ ] `docs/glossary.md` 更新判断 ("AgentAvatar" / "ZONE_MAP" 追加か)
- [ ] `.steering/_setup-progress.md` Phase 8 に T17 エントリ追加
- [ ] `.steering/20260418-implementation-plan/tasklist.md` の T17 を `[x]` に

## Step J: コミットと PR
- [ ] 単一 feat コミット: `feat(godot): T17 godot-peripatos-scene — Peripatos
      3D + Avatar Tween 移動 + Contract speed 利用`
- [ ] `Co-Authored-By: Claude Opus 4.7 (1M context)` + `Refs:` 付与
- [ ] `git push -u origin feature/godot-peripatos-scene`
- [ ] `gh pr create` で PR 作成

## 完了処理
- [ ] decisions.md 作成 (設計判断 6+ 件)
- [ ] blockers.md 作成 (LOW 懸案: speech auto-hide / エディタ canonical 化)
- [ ] `/finish-task` で最終化

## ブロッカー候補 (発生時に blockers.md へ)
- AVATAR_SCENE.instantiate() の戻り値型ミスマッチ → has_method ガード
- Tween 挙動が headless --quit-after で期待と異なる
- FixtureHarness 経由で Peripatos 実例が test_godot_ws_client.py 既存 assertion
  に影響
- SpeechBubble Label3D 初期 visible 設定が headless で ERROR 出す可能性
