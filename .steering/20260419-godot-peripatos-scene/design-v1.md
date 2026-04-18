# T17 godot-peripatos-scene — 設計 (v1 初回案)

> **⚠️ この v1 は `/reimagine` の破壊対象**。requirement.md 運用メモの承認通り、
> 初回案 (v1) を意図的に素直 / 凡庸に書いた上で、`/reimagine` でゼロから
> 再生成した v2 と比較し、採用案を確定する。

## 実装アプローチ

### 全体方針 (素直案: patterns.md §3/§4 をそのまま踏襲)

- `scripts/AgentController.gd` を **patterns.md §3 のコードほぼそのまま**コピー
  - `class_name AgentController` を宣言
  - `extends CharacterBody3D`
  - `ANIMATION_MAP` 定数 (walk / sit / bow / idle / speak / reflect)
  - `_target_position` + `_move_speed = 2.0` (patterns.md ハードコード値)
  - `_physics_process()` で lerp + look_at + move_and_slide
  - `update_from_envelope(payload: Dictionary)` で position / animation / speech 分岐
  - `set_animation(action)` で `AnimationTree` 経由の state_machine.travel()
  - `_show_speech(text)` で 5 秒タイマ

- `scripts/AgentManager.gd` を **patterns.md §4 に書き換え**
  - T16 の 4 個の `print()` stub handler を avatar 実操作に置換
  - `const AgentAvatarScene := preload("res://scenes/agents/AgentAvatar.tscn")`
  - `_agents: Dictionary = {}` で agent_id → AgentController
  - `get_or_create_agent(agent_id) -> AgentController` (型は class_name で)
  - `_on_agent_updated` / `_on_speech_delivered` / `_on_move_issued` /
    `_on_animation_changed` を avatar.update_from_envelope や直接メソッド呼び出しで実装

- `scenes/agents/AgentAvatar.tscn` を patterns.md §3 ノード構造で新規作成:
  ```
  AgentAvatar (CharacterBody3D) + AgentController.gd
  ├── CollisionShape3D (CapsuleShape3D)
  ├── MeshInstance3D (CapsuleMesh)
  ├── AnimationPlayer (空クリップ、名前のみ登録)
  ├── AnimationTree (AnimationNodeStateMachine ルート)
  └── SpeechBubble (Label3D)
  ```

- `scenes/zones/Peripatos.tscn` を新規作成:
  ```
  Peripatos (Node3D)
  ├── Ground (MeshInstance3D with PlaneMesh 40m x 8m)
  ├── BoundaryNorth (MeshInstance3D with BoxMesh 40x0.3x0.3)
  ├── BoundarySouth (MeshInstance3D with BoxMesh 40x0.3x0.3)
  └── Light (OmniLight3D)
  ```

- `scripts/WorldManager.gd` 拡張:
  ```gdscript
  const ZONE_MAP: Dictionary = {
      "peripatos": preload("res://scenes/zones/Peripatos.tscn"),
  }

  func _ready() -> void:
      # ... existing ...
      var peripatos_instance := ZONE_MAP["peripatos"].instantiate()
      $ZoneManager.add_child(peripatos_instance)
  ```

- `scenes/MainScene.tscn` 修正:
  - `load_steps=6` → `load_steps=7` (ext_resource 1 件追加: AgentAvatar.tscn)
  - AgentManager ノードに `agent_avatar_scene = ExtResource("5_agentavatar")` 追加

### fixture 再生時の予想フロー

1. `FixturePlayer` が `handshake.json` → `EnvelopeRouter` → (T17 範囲外、log のみ)
2. `agent_update.json` → `EnvelopeRouter.agent_updated.emit(agent_id, agent_state)` →
   `AgentManager._on_agent_updated(agent_id, agent_state)` →
   `get_or_create_agent(agent_id)` で avatar instance → log:
   `[AgentManager] Created agent: a_kant_001`
3. `speech.json` → Router → AgentManager → `avatar._show_speech("Der...")` →
   Label3D 表示 (5s)
4. `move.json` → Router → AgentManager → `avatar._target_position = Vector3(18, 0, -3.2)`
5. `animation.json` → Router → AgentManager → `avatar.set_animation("walk")` →
   AnimationTree state_machine.travel("Walking") (ただし空クリップなので実視覚なし)

### 移動制御

- `AgentController._physics_process()` 内で `global_position.distance_to(_target_position) > 0.1`
  の間 lerp
- `velocity = direction * _move_speed` (patterns.md ハードコード `_move_speed = 2.0`)
- `move_and_slide()` で CharacterBody3D の物理を使う

### `class_name` 方針

- `AgentController` に `class_name AgentController` を**宣言する** (patterns.md 通り)
- `AgentManager.gd` から `get_or_create_agent() -> AgentController` の型注釈で参照
- これで IDE 補完 + 型安全性が向上する (patterns.md §4 のテンプレ通り)

## 変更対象

### 新規作成するファイル

- `godot_project/scenes/zones/Peripatos.tscn` — PlaneMesh + 境界 + light
- `godot_project/scenes/agents/AgentAvatar.tscn` — patterns.md §3 ノード構造
- `godot_project/scripts/AgentController.gd` (~70 行) — patterns.md §3 コピー
- `tests/test_godot_peripatos.py` (~100 行) — headless fixture 再生検証

### 修正するファイル

- `godot_project/scripts/AgentManager.gd` — 4 stub handler を patterns.md §4 に書き換え
- `godot_project/scripts/WorldManager.gd` — ZONE_MAP + peripatos instance
- `godot_project/scenes/MainScene.tscn` — ext_resource 追加 + load_steps 7 に更新
- `tests/test_godot_project.py` — `test_required_project_files_exist` に新 3 ファイル追加

### 削除するファイル

- なし

### 変更なし (参照のみ)

- `scripts/EnvelopeRouter.gd` / `WebSocketClient.gd` / `scripts/dev/FixturePlayer.gd`
- `scenes/dev/FixtureHarness.tscn`
- `fixtures/control_envelope/*.json`
- `src/erre_sandbox/schemas.py`

## 影響範囲

impact-analyzer 結果に基づく:

- **HIGH 局所**: MainScene.tscn 手動編集 (load_steps=6→7、ext_resource id 重複回避)
  — T16 判断 9 の L5 と二重蓄積になる
- **MEDIUM**: `class_name AgentController` cross-script 参照で
  T16 判断 4 の parse 失敗が再発する可能性
- **MEDIUM**: FixtureHarness 経由で avatar が実 instance される。AgentController._ready()
  の依存ノード (AnimationTree 等) が無ければ push_error → `test_godot_ws_client.py`
  の `rc == 0` assert で検出
- **LOW**: Godot 4.6.2 GL Compatibility での PlaneMesh / OmniLight3D API 安定性 (機械検出可)

## 既存パターンとの整合性

- **patterns.md §3 (AgentController.gd) をそのまま採用** — 定数 / 関数名 / 変数名すべて踏襲
- **patterns.md §4 (AgentManager.gd) をそのまま採用** — `const AgentAvatarScene := preload(...)`
  + `_agents: Dictionary` + `get_or_create_agent()` の完全コピー
- **patterns.md §2 (MainScene 階層)** は T15 で既に準拠済み、T17 は `agent_avatar_scene` export 追加のみ
- **ゾーン座標指針** は peripatos = (-20, 0, 0)〜(20, 0, 0) を採用
- **T16 判断 1 (Router の 7 専用 signal)** を維持、AgentManager は `has_signal` duck typing
  のまま (signal connect 箇所は変更なし、handler 本体のみ書き換え)

## テスト戦略

### 新設 `tests/test_godot_peripatos.py` (~100 行)

- `_resolve_godot()` (既存 `tests/_godot_helpers.py` から import)
- 起動: `godot --headless res://scenes/dev/FixtureHarness.tscn -- --fixture-dir=<abs>`
  (test_godot_ws_client.py と同じコマンド)
- assertions:
  1. **exit 0**
  2. **stdout に `[AgentManager] Created agent: a_kant_001`** が現れる
  3. `[AgentController] ... animation=walk` 等の想定ログ
  4. `"Unknown kind"` / `"ERROR:"` が現れない

### `tests/test_godot_project.py` 拡張

- `test_required_project_files_exist` に 3 追加:
  - `scenes/zones/Peripatos.tscn`
  - `scenes/agents/AgentAvatar.tscn`
  - `scripts/AgentController.gd`

### 既存テストの不破壊

- `test_godot_ws_client.py` は AgentManager の print 行を直接 assert していないため
  書き換えで壊れない
- `test_envelope_kind_sync.py` は EnvelopeRouter のみ見るため T17 は無関係

### TDD 非適用

- GDScript のランタイム挙動 / 3D 描画は headless 統合テストで代替
- visual check (エディタで開いて Peripatos + Kant avatar が描画) は手動

## 関連する Skill

- `godot-gdscript` — patterns.md §2/§3/§4/§5、ゾーン座標指針
- `architecture-rules` — `godot_project/` に .py 不混入、`ui/` → `schemas.py` のみ (T17 は ui/ 触らない)
- `test-standards` — `tests/test_godot_peripatos.py` の skip 判断
- `git-workflow` — feat(godot): T17 ... + Refs: .steering/20260419-godot-peripatos-scene/

## ロールバック計画

- T17 は新規 3 ファイル + 修正 3 ファイルが主体
- 問題時の戻し方:
  1. `git reset --hard origin/main` で T17 branch を破棄
  2. MainScene.tscn 単独の誤編集は `git checkout origin/main -- godot_project/scenes/MainScene.tscn`
  3. AgentManager.gd / WorldManager.gd は git checkout で個別復旧可能

## 初回案 (v1) の自覚的弱点

破壊と構築の材料として、v1 自身が持つ弱点を明示する。

| # | 弱点 | 深刻度 |
|---|---|---|
| V1-W1 | **AnimationTree を採用**しているが、アニメクリップが**一つも存在しない**。state_machine.travel("Walking") が空ノードに対して呼ばれ、実視覚効果がないどころか push_error のリスク。AnimationPlayer 単体 + `has_animation()` ガードで十分 | 中-高 |
| V1-W2 | **`_move_speed = 2.0` をハードコード**しているが、`move.json` には `speed: 1.3` が入っている。envelope が持つ実データを捨てており、Contract の意図を無視 | 中 |
| V1-W3 | **`class_name AgentController` を宣言**し、AgentManager から型注釈として参照している。T16 判断 4 で確認した通り `.godot/` cache 未生成の初回 headless boot で parse 失敗が再発する | 高 |
| V1-W4 | **MainScene.tscn を手動編集** (load_steps=6→7)。T16 L5 「次回エディタで canonical 化」が未消化のまま、さらに手動編集を重ねる。ID 割当ミスリスク | 中 |
| V1-W5 | **Peripatos.tscn が「単なる path + 地面 + 境界」** で、peripatos = 歩行路 / DMN 活性化 の視覚的メタファー (道の曲線、樹影、歩幅のリズムを誘発する要素) が皆無。MVP だが「素人草案」の形式美 | 低-中 |
| V1-W6 | **AgentController._physics_process()** で毎フレーム lerp + move_and_slide を呼ぶが、**target に到達後も continue**。停止判定は `distance > 0.1` の範囲外だけで、idle 状態への遷移もなく `velocity = ZERO` を設定するだけ | 中 |
| V1-W7 | **ZONE_MAP を WorldManager 内 Dictionary** としたが、**1 エントリ (peripatos のみ)** の時点で Dictionary を持ち出すのは premature abstraction。4 ゾーン追加時 (M5) まで単純な preload 変数で十分 | 低 |
| V1-W8 | **test_godot_peripatos.py** が test_godot_ws_client.py と同じ FixtureHarness で起動するため、同じ headless テストが 2 件走って CI 時間が倍増する。テスト間の責務分離ではなく、test_godot_ws_client.py に assertion を追加するだけで済む可能性 | 低 |

**この v1 を意図的に破壊して v2 を再生成し、並べて比較して採用案を決める。**

## 次のステップ

1. `/reimagine` を起動 → 本 design.md を `design-v1.md` に退避
2. ゼロから再生成した v2 を新 design.md に書く
3. `design-comparison.md` で v1/v2 を並置、採用案を決定
4. 採用版 design.md に基づき Step D (tasklist) に進む
