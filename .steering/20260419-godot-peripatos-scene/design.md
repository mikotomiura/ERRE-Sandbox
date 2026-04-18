# T17 godot-peripatos-scene — 設計 (v2 再生成案)

## 実装アプローチ

### 中核アイデア: **Tween 駆動移動 × preload 直接参照 × テスト束ね**

要件を分解すると 2 つの責務:
(a) peripatos を 3D で描画
(b) Router signal → avatar の 3D 表現接続

この 2 つを「**最小運動単位の動く絵**」に還元する。v2 は以下 3 原則で再構成:

1. **Tween ベースの移動制御**
   - envelope の `speed` を `duration = distance / speed` に変換
   - `_physics_process` の毎フレーム lerp を廃止 (idle 時の無駄処理ゼロ)
   - `create_tween().tween_property(self, "global_position", target, duration)` の
     一行で直線移動 + 自動停止

2. **AgentAvatarScene を `preload()` で直接参照 → MainScene.tscn 編集不要**
   - AgentManager.gd 内で `const AVATAR_SCENE := preload("res://scenes/agents/AgentAvatar.tscn")`
   - `@export var agent_avatar_scene: PackedScene` を使わないため
     **MainScene.tscn の変更が 0 行**になる
   - T16 L5 (手動編集二重蓄積) の懸案を完全解消

3. **テスト共有**: `tests/test_godot_peripatos.py` に module-scoped fixture で
   FixtureHarness subprocess 結果を共有。単一 subprocess 呼び出しで複数
   assertion を走らせ、CI 時間増を抑制

### データフロー (fixture 再生時)

```
handshake.json → EnvelopeRouter.handshake_received → (副作用なし)
agent_update.json → EnvelopeRouter.agent_updated(agent_id="a_kant_001", agent_state)
    → AgentManager.get_or_create_avatar(agent_id)
        → AVATAR_SCENE.instantiate() → ZoneManager/Peripatos への add_child
        → log: "[AgentManager] avatar spawned agent_id=a_kant_001"
speech.json → EnvelopeRouter.speech_delivered(agent_id, utterance, zone)
    → AgentManager の 1 行: avatar._show_speech(utterance)
        → Label3D.text = utterance, visible = true
        → log: "[AgentController] speech zone=peripatos len=N"
move.json → EnvelopeRouter.move_issued(agent_id, target, speed)
    → AgentManager: avatar._set_move_target(target, speed)
        → create_tween() で duration = distance / speed の線形補間
        → log: "[AgentController] move target=(18.0, 0.0, -3.2) speed=1.30"
animation.json → EnvelopeRouter.animation_changed(agent_id, name, loop)
    → AgentManager: avatar._set_animation(name)
        → _current_animation = name, log: "[AgentController] animation=walk"
```

### Avatar 構造 (`scenes/agents/AgentAvatar.tscn`)

```
AgentAvatar (Node3D)                  ← CharacterBody3D ではなく Node3D (物理不要)
├── Body (MeshInstance3D)             ← CapsuleMesh (高 1.8m、胴体の代わり)
├── Facing (MeshInstance3D)           ← 前方を指す薄い BoxMesh (向き表示)
├── SpeechBubble (Label3D)            ← visible=false、位置 (0, 2.2, 0)
└── AgentController.gd                ← attach
```

**設計判断**:
- **Node3D ルート**: CharacterBody3D を使わない。衝突判定 / 物理応答は T17 不要、
  Tween で移動するので CharacterBody3D の move_and_slide も不要。
- **AnimationPlayer / AnimationTree なし**: T17 はアニメクリップを持たないため、
  両者を scene に含めない。`_current_animation: String` を controller 内で保持し、
  ログ出力するのみ。M4 で glTF + AnimationPlayer を追加する際は scene 編集で差し込み。
- **Facing indicator**: CapsuleMesh は回転方向が視認しにくいので、前方 (local +Z)
  に小さな薄 BoxMesh を置いて向きを示す。

### AgentController.gd (約 75 行)

```gdscript
# godot_project/scripts/AgentController.gd
# No class_name to avoid T16 judgement 4 (cross-script parse order).
extends Node3D

@export var agent_id: String = ""

@onready var _body: MeshInstance3D = $Body
@onready var _speech_bubble: Label3D = $SpeechBubble

var _current_animation: String = "idle"
var _current_tween: Tween = null


func set_agent_id(new_id: String) -> void:
    agent_id = new_id
    name = new_id   # Makes the node path predictable: ZoneManager/Peripatos/a_kant_001


func update_position_from_state(agent_state: Dictionary) -> void:
    var pos: Dictionary = agent_state.get("position", {})
    if pos.is_empty():
        return
    var dest := Vector3(
        float(pos.get("x", 0.0)),
        float(pos.get("y", 0.0)),
        float(pos.get("z", 0.0)),
    )
    global_position = dest


func set_move_target(target: Dictionary, speed: float) -> void:
    var dest := Vector3(
        float(target.get("x", 0.0)),
        float(target.get("y", 0.0)),
        float(target.get("z", 0.0)),
    )
    var distance := global_position.distance_to(dest)
    if distance < 0.01:
        return
    if _current_tween != null and _current_tween.is_running():
        _current_tween.kill()
    var effective_speed := max(speed, 0.01)  # guard against divide-by-zero
    var duration := distance / effective_speed
    look_at(dest, Vector3.UP)
    _current_tween = create_tween()
    _current_tween.tween_property(self, "global_position", dest, duration)
    print(
        "[AgentController] move agent_id=%s target=(%.2f, %.2f, %.2f) speed=%.2f"
        % [agent_id, dest.x, dest.y, dest.z, speed]
    )


func set_animation(animation_name: String) -> void:
    _current_animation = animation_name
    print("[AgentController] animation agent_id=%s name=%s" % [agent_id, animation_name])


func show_speech(utterance: String, zone: String) -> void:
    _speech_bubble.text = utterance
    _speech_bubble.visible = true
    print(
        "[AgentController] speech agent_id=%s zone=%s len=%d"
        % [agent_id, zone, utterance.length()]
    )
```

**ポイント**:
- `class_name` なし (T16 判断 4 踏襲)
- `_physics_process` なし (Tween が駆動)
- Speech は `await` タイマなし (headless テストでのハング回避、auto-hide は M5)
- `effective_speed := max(speed, 0.01)` で envelope の speed=0 等の極端値ガード

### AgentManager.gd (書き換え)

```gdscript
# godot_project/scripts/AgentManager.gd
# T16 の has_signal duck typing + 4 signal connect を維持。
# T17 で print-only から avatar 実操作に handler 本体を書き換え。

extends Node3D

@export var router_path: NodePath

const _REQUIRED_SIGNALS: PackedStringArray = [
    "agent_updated",
    "speech_delivered",
    "move_issued",
    "animation_changed",
]

# Direct preload; no @export PackedScene → NO MainScene.tscn edit needed.
const AVATAR_SCENE := preload("res://scenes/agents/AgentAvatar.tscn")

var _avatars: Dictionary = {}  # agent_id (String) -> AgentController (Node3D)


func _ready() -> void:
    # ... (existing router resolution and has_signal checks stay identical to T16)
    var router := _resolve_router()
    if router == null:
        push_error("[AgentManager] EnvelopeRouter not found at %s" % router_path)
        return
    for signal_name: String in _REQUIRED_SIGNALS:
        if not router.has_signal(signal_name):
            push_error("[AgentManager] router missing signal: %s" % signal_name)
            return
    router.agent_updated.connect(_on_agent_updated)
    router.speech_delivered.connect(_on_speech_delivered)
    router.move_issued.connect(_on_move_issued)
    router.animation_changed.connect(_on_animation_changed)


func _resolve_router() -> Node:
    # unchanged from T16
    ...


func _get_or_create_avatar(agent_id: String) -> Node:
    if _avatars.has(agent_id):
        return _avatars[agent_id]
    var avatar := AVATAR_SCENE.instantiate()
    avatar.set_agent_id(agent_id)
    add_child(avatar)
    _avatars[agent_id] = avatar
    print("[AgentManager] avatar spawned agent_id=%s" % agent_id)
    return avatar


func _on_agent_updated(agent_id: String, agent_state: Dictionary) -> void:
    var avatar := _get_or_create_avatar(agent_id)
    avatar.update_position_from_state(agent_state)


func _on_speech_delivered(agent_id: String, utterance: String, zone: String) -> void:
    var avatar := _get_or_create_avatar(agent_id)
    avatar.show_speech(utterance, zone)


func _on_move_issued(agent_id: String, target: Dictionary, speed: float) -> void:
    var avatar := _get_or_create_avatar(agent_id)
    avatar.set_move_target(target, speed)


func _on_animation_changed(agent_id: String, animation_name: String, loop: bool) -> void:
    var avatar := _get_or_create_avatar(agent_id)
    avatar.set_animation(animation_name)
```

### WorldManager.gd (ZONE_MAP 追加)

```gdscript
# 既存コードはそのまま、以下を追加:
const ZONE_MAP: Dictionary = {
    # M5 world-zone-triggers でこの dict に study / chashitsu / agora / garden が加わる。
    "peripatos": preload("res://scenes/zones/Peripatos.tscn"),
}

# _ready() の末尾に追加:
func _ready() -> void:
    # ... (T16 の router connect がある)
    _spawn_initial_zones()


func _spawn_initial_zones() -> void:
    var zone_manager: Node = get_node_or_null("ZoneManager")
    if zone_manager == null:
        push_error("[WorldManager] ZoneManager not found")
        return
    for zone_name: String in ZONE_MAP.keys():
        var zone_instance := ZONE_MAP[zone_name].instantiate()
        zone_instance.name = zone_name.capitalize()  # ZoneManager/Peripatos
        zone_manager.add_child(zone_instance)
        print("[WorldManager] zone spawned name=%s" % zone_name)
```

### Peripatos.tscn 構造

```
Peripatos (Node3D)
├── Ground (MeshInstance3D + PlaneMesh 40m × 4m)   ← 歩行路らしい細長い形
├── StartMarker (MeshInstance3D + BoxMesh)         ← 西端 (-20, 0.5, 0)
├── EndMarker (MeshInstance3D + BoxMesh)           ← 東端 (+20, 0.5, 0)
├── Post0..5 (MeshInstance3D + BoxMesh)            ← 南北に計 6 本の散点
└── Light (OmniLight3D, omni_range = 30, 位置 (0, 10, 0))
```

**設計判断**:
- PlaneMesh の横幅を 4m に絞ることで「path」感を強調 (v1 の 8m だと広場に見える)
- 境界 box を連続 wall ではなく 6 本の離散 post に (歩行の開放感を保ちつつ境界感は残す)
- **Post 配置は北側 4 本 (-16/-8/0/+8)、南側 2 本 (-8/+8) の非対称**:
  - 北側はより細かく置いて「仕切り感」を出し、南側は抜け感を残す
  - peripatos は Kant のケーニヒスベルクの散歩道メタファー (南北に川 / 街が広がる
    非対称環境) を連想させるため
  - M5 以降で視覚効果を加える際も、この asymmetry が視線誘導のベースになる
- Start/End marker で「西端 → 東端」の方向性を視覚化 (Kant が歩く方向)

## 変更対象

### 新規作成するファイル

- `godot_project/scenes/zones/Peripatos.tscn` — Node3D + PlaneMesh + 境界 post 群 + light
- `godot_project/scenes/agents/AgentAvatar.tscn` — Node3D + CapsuleMesh Body + Facing BoxMesh + Label3D
- `godot_project/scripts/AgentController.gd` — Tween 駆動移動 + speech + animation ログ (約 75 行)
- `tests/test_godot_peripatos.py` — module-scoped fixture で subprocess 共有 + avatar アサート (約 120 行)

### 修正するファイル

- `godot_project/scripts/AgentManager.gd` — handler 本体を 4 箇所書き換え (preload で AVATAR_SCENE 参照、_avatars dict、get_or_create_avatar)
- `godot_project/scripts/WorldManager.gd` — ZONE_MAP 定数 + _spawn_initial_zones()
- `tests/test_godot_project.py` — `test_required_project_files_exist` に 3 ファイル assertion 追加

### 変更なし (v2 の重要な改善点)

- **`godot_project/scenes/MainScene.tscn` を一切触らない** (V1-W4 完全解消、T16 L5 二重蓄積回避)
- `godot_project/scenes/dev/FixtureHarness.tscn` (MainScene を instance するだけなので自動追従)
- `godot_project/scripts/EnvelopeRouter.gd` / `WebSocketClient.gd` / `scripts/dev/FixturePlayer.gd`
- `fixtures/control_envelope/*.json`
- `src/erre_sandbox/schemas.py`
- `tests/test_godot_ws_client.py` (T16 で確立した既存 assertion を壊さない)
- `tests/test_envelope_kind_sync.py`

## 影響範囲

- **HIGH → LOW 改善**: MainScene.tscn 編集不要化により、手動編集リスク / L5 二重蓄積が**解消**
- **MEDIUM → 解消**: class_name cross-ref 懸念 — AgentController に `class_name` を
  宣言しない方針で T16 判断 4 を完全踏襲
- **MEDIUM**: FixtureHarness 経由で avatar が実 instance される。AgentController._ready()
  が minimal (`@onready` 2 つと print) で push_error を出しにくい。`test_godot_ws_client.py`
  の既存 assertion (`"Unknown kind" not in combined` / rc == 0) は維持
- **LOW**: Godot 4.6.2 GL Compatibility での PlaneMesh / OmniLight3D API — 安定

## 既存パターンとの整合性

- **T16 判断 1 (Router の 7 専用 signal)** — AgentManager の signal connect と
  4 ハンドラ名を維持 (handler 本体のみ書き換え)
- **T16 判断 4 (class_name cross-ref 回避)** — AgentController に class_name 宣言なし、
  AgentManager は `Node` 型で受けて `has_method()` は不要 (AVATAR_SCENE.instantiate()
  が返す型は自前 scene なので duck typing 不要、直接メソッド呼び出し OK)
- **T16 判断 9 (MainScene.tscn 手動編集の記録)** — T17 は**該当なし** (編集しないため)
- **T15 判断 3 (MainScene 階層 patterns.md §2 準拠)** — ZoneManager / AgentManager
  ノードの階層は不変
- **patterns.md §3 (AgentAvatar 構造)** — 一部逸脱 (CharacterBody3D → Node3D、
  AnimationPlayer 除去)。理由は本 design §Avatar 構造に明記
- **patterns.md §4 (AgentManager 動的管理)** — 基本コンセプト (preload +
  `_agents: Dictionary` + get_or_create) は採用、型注釈のみ T16 判断 4 で調整

## テスト戦略

### 新設 `tests/test_godot_peripatos.py`

**module-scoped fixture で subprocess を共有**:

```python
@pytest.fixture(scope="module")
def harness_result() -> subprocess.CompletedProcess[str] | None:
    godot = resolve_godot()
    if godot is None:
        return None
    return subprocess.run(...)  # 既存 test_godot_ws_client と同じコマンド


def test_avatar_spawned(harness_result) -> None:
    if harness_result is None:
        pytest.skip("Godot not installed")
    combined = harness_result.stdout + harness_result.stderr
    assert "[AgentManager] avatar spawned agent_id=a_kant_001" in combined


def test_move_uses_envelope_speed(harness_result) -> None:
    # fixture の speed=1.3 が log に現れる
    assert "speed=1.30" in combined


def test_speech_reaches_avatar(harness_result) -> None:
    assert "[AgentController] speech agent_id=a_kant_001 zone=peripatos" in combined


def test_animation_set(harness_result) -> None:
    assert "[AgentController] animation agent_id=a_kant_001 name=walk" in combined


def test_zone_spawned_on_boot(harness_result) -> None:
    assert "[WorldManager] zone spawned name=peripatos" in combined


def test_no_errors(harness_result) -> None:
    assert "ERROR:" not in harness_result.stderr
    assert harness_result.returncode == 0
```

**単一 subprocess / 6 assertion** でアバター + ゾーン + speed + 順序を検証 (V1-W8 解消)。

### `tests/test_godot_project.py` 拡張

既存の `test_required_project_files_exist` に追加:
```python
assert (GODOT_PROJECT / "scenes" / "zones" / "Peripatos.tscn").is_file()
assert (GODOT_PROJECT / "scenes" / "agents" / "AgentAvatar.tscn").is_file()
assert (GODOT_PROJECT / "scripts" / "AgentController.gd").is_file()
```

### 既存テスト不破壊

- `test_godot_ws_client.py` は AgentManager の print 行を assert していないため書き換えで壊れない
- `test_envelope_kind_sync.py` は EnvelopeRouter のみ参照、T17 影響なし

### TDD 非適用

- GDScript ランタイム / 3D 描画 は headless 統合テストで代替
- visual check は手動 (Godot エディタで Peripatos と avatar を表示確認)

## 関連する Skill

- `godot-gdscript` — patterns.md §2/§3 (一部逸脱を本設計で正当化)、§4 (基本コンセプト採用)、
  ゾーン座標指針 (peripatos -20〜+20 東西 40m)
- `architecture-rules` — `godot_project/` に .py 不混入
- `test-standards` — module-scoped fixture での subprocess 共有 / skip 判断
- `git-workflow` — feat(godot): T17 ... + Refs: .steering/20260419-godot-peripatos-scene/

## ロールバック計画

T17 は新規 3 ファイル + 修正 2 ファイルが主体 (MainScene.tscn 不変)。問題時:

1. `git reset --hard origin/main` で T17 branch を破棄
2. AgentManager.gd 単独リバート: `git checkout origin/main -- godot_project/scripts/AgentManager.gd`
3. WorldManager.gd 単独リバート: 同様
4. 新規 3 ファイル削除で元状態に戻る

## v2 設計の着眼点 (v1 の弱点への対処)

| v1 弱点 | v2 での対処 | 効果 |
|---|---|---|
| V1-W1 AnimationTree 空クリップで push_error リスク | **AnimationPlayer/Tree を完全除去**、`_current_animation: String` + print のみ | crash リスク解消、scene サイズ減 |
| V1-W2 `_move_speed=2.0` ハードコードで envelope speed を無視 | `set_move_target(target, speed)` で **envelope の speed を duration 計算に使用** | Contract 準拠、fixture の speed=1.3 がログに反映 |
| V1-W3 `class_name AgentController` で cross-ref parse 失敗再発 | **class_name 宣言なし、型注釈は Node** | T16 判断 4 完全踏襲 |
| V1-W4 MainScene.tscn 手動編集で L5 二重蓄積 | **AgentManager が preload 直接参照、MainScene 変更 0 行** | L5 懸案解消、手動編集リスク完全排除 |
| V1-W5 Peripatos が単なる path で peripatos らしさ皆無 | 境界を **6 本 post に離散化** + **Start/End marker で方向性** + path 幅を 4m に絞る | 歩行路のメタファーが視覚化 |
| V1-W6 `_physics_process` で lerp 継続、idle 判定ゆるい | **Tween 駆動** で移動時のみアクティブ、到達後自動停止 | 無駄処理ゼロ、stop 判定明確 |
| V1-W7 ZONE_MAP Dictionary は 1 エントリで過剰抽象 | Dictionary を **明示コメント付き**で採用し M5 拡張への宣言にする | 後続タスクへの意図明示、M5 で差分 0 |
| V1-W8 test_godot_peripatos.py が test_godot_ws_client.py と subprocess 重複 | **module-scoped fixture** で subprocess 共有、6 assertion を単一プロセスで | CI 時間増を抑制、テスト責務も明確 |

## 次のステップ

1. ~~`design-comparison.md` を作成して v1 と v2 を並置~~ ✓
2. ~~ユーザーに採用案 (v1 / v2 / ハイブリッド) を確認~~ ✓
3. ~~採用案を design.md に確定~~ ✓ (本ファイルが確定版)
4. tasklist.md へ (Step D)

## 設計判断の履歴

- **2026-04-19**: 初回案 (design-v1.md) と再生成案 (v2) を `design-comparison.md`
  で並置比較
- **採用**: **v2 (再生成案) をフル採用**
- **根拠 (ユーザー判断)**:
  - V1 致命 4 件 (W1 AnimationTree empty / W2 speed 無視 / W3 class_name
    cross-ref / W4 MainScene L5 二重蓄積) を**すべて構造で解消**
  - T16 判断 4 (class_name 回避) / 判断 9 (手動編集記録) を **再現せず不要化**
    — MainScene.tscn 不変で L5 懸案を完全排除、class_name 宣言なしで parse 安定
  - Contract-First 思想の徹底: envelope の `speed` を移動 duration 計算に使用
  - patterns.md §3 逸脱 (CharacterBody3D → Node3D / AnimationPlayer 除去) は
    T17 primitive 段階での合理的選択として本 design.md で明示
  - テスト設計 (module-scoped fixture) で CI 時間増を抑えつつ 6 assertion を
    単一 subprocess で実行
  - ハイブリッド H1/H2/H3 はいずれも v2 の構造的改善を損なうため非採用
