# Godot GDScript — パターン集

---

## パターン 1: WebSocket クライアント完全実装

```gdscript
# godot_project/scripts/WebSocketClient.gd
class_name WebSocketClient
extends Node

## WebSocket URL for G-GEAR gateway
const WS_URL: String = "ws://g-gear.local:8000/stream"
## Reconnect delay in seconds
const RECONNECT_DELAY: float = 5.0

var _ws: WebSocketPeer = WebSocketPeer.new()
var _connected: bool = false
var _reconnect_timer: float = 0.0
var _should_reconnect: bool = false

signal envelope_received(envelope: Dictionary)
signal connection_status_changed(connected: bool)


func _ready() -> void:
    _connect_to_server()


func _connect_to_server() -> void:
    _should_reconnect = false
    var err := _ws.connect_to_url(WS_URL)
    if err != OK:
        push_warning("[WS] Connection attempt failed: %s" % error_string(err))
        _should_reconnect = true
        _reconnect_timer = RECONNECT_DELAY


func _process(delta: float) -> void:
    if _should_reconnect:
        _reconnect_timer -= delta
        if _reconnect_timer <= 0.0:
            _connect_to_server()
        return

    _ws.poll()
    var state := _ws.get_ready_state()

    match state:
        WebSocketPeer.STATE_OPEN:
            if not _connected:
                _connected = true
                print("[WS] Connected to %s" % WS_URL)
                connection_status_changed.emit(true)
            _consume_packets()

        WebSocketPeer.STATE_CLOSING:
            pass  # wait

        WebSocketPeer.STATE_CLOSED:
            if _connected:
                _connected = false
                var code := _ws.get_close_code()
                var reason := _ws.get_close_reason()
                print("[WS] Disconnected: code=%d reason=%s" % [code, reason])
                connection_status_changed.emit(false)
            _should_reconnect = true
            _reconnect_timer = RECONNECT_DELAY


func _consume_packets() -> void:
    while _ws.get_available_packet_count() > 0:
        var raw := _ws.get_packet().get_string_from_utf8()
        var parsed: Variant = JSON.parse_string(raw)
        if parsed is Dictionary:
            envelope_received.emit(parsed)
        else:
            push_warning("[WS] Malformed message (not JSON dict): %s" % raw.left(200))
```

**なぜ**: `_process()` で毎フレーム poll する設計は Godot 4.4 ��推奨パターン。
再接続ロジックを `_should_reconnect` フラグで管理することで、
タイマーノードを追加せずに処理できる。

---

## パターン 2: シーンノード階層 (MainScene)

```
MainScene (Node3D)
├── Environment (WorldEnvironment)
│   └── DirectionalLight3D
├── Camera3D
├── ZoneManager (Node3D)
│   ├── Study (Node3D)         ← Study.tscn のインスタンス
│   ├── Peripatos (Node3D)     ← Peripatos.tscn のインスタンス
│   ├── Chashitsu (Node3D)     ← Chashitsu.tscn のインスタンス
│   ├── Agora (Node3D)         ← Agora.tscn のインスタンス
│   └── Garden (Node3D)        ← Garden.tscn のインスタンス
├── AgentManager (Node3D)
│   └── (エージェントアバターは動的に追加)
├── WebSocketClient (Node)     ← WebSocketClient.gd
├── UILayer (CanvasLayer)
│   ├── SpeechBubbleContainer
│   └── DebugOverlay
└── WorldManager.gd            ← ルートスクリプト
```

---

## パターン 3: エージェントアバターのシーン構造

```
AgentAvatar.tscn (CharacterBody3D)
├── CollisionShape3D
├── MeshInstance3D              ← スキンメッシュ (glTF インポート)
├── AnimationPlayer             ← walking/sitting/bowing アニメーション
├── AnimationTree               ← ステートマシン
├── SpeechBubble (Label3D)      ← 発話表示
└── AgentController.gd          ← 制御スクリプト
```

```gdscript
# godot_project/scripts/AgentController.gd
class_name AgentController
extends CharacterBody3D

@export var agent_id: String = ""
@onready var anim_tree: AnimationTree = $AnimationTree
@onready var speech_bubble: Label3D = $SpeechBubble

const ANIMATION_MAP: Dictionary = {
    "walk": "Walking",
    "sit": "Sitting",
    "bow": "Bowing",
    "idle": "Idle",
    "speak": "Speaking",
    "reflect": "Meditating",
}

var _target_position: Vector3 = Vector3.ZERO
var _move_speed: float = 2.0


func update_from_envelope(payload: Dictionary) -> void:
    """Update agent state from ControlEnvelope payload."""
    if payload.has("position"):
        var pos: Array = payload["position"]
        _target_position = Vector3(pos[0], pos[1], pos[2])

    if payload.has("animation"):
        set_animation(payload["animation"])

    if payload.has("speech_bubble"):
        _show_speech(payload["speech_bubble"])


func set_animation(action: String) -> void:
    var anim_name: String = ANIMATION_MAP.get(action, "Idle")
    var state_machine: AnimationNodeStateMachinePlayback = anim_tree.get(
        "parameters/playback"
    )
    if state_machine.get_current_node() != anim_name:
        state_machine.travel(anim_name)


func _show_speech(text: Variant) -> void:
    if text is String and text != "":
        speech_bubble.text = text
        speech_bubble.visible = true
        await get_tree().create_timer(5.0).timeout
        speech_bubble.visible = false
    else:
        speech_bubble.visible = false


func _physics_process(delta: float) -> void:
    if global_position.distance_to(_target_position) > 0.1:
        var direction := (_target_position - global_position).normalized()
        velocity = direction * _move_speed
        look_at(_target_position, Vector3.UP)
        move_and_slide()
    else:
        velocity = Vector3.ZERO
```

---

## パターン 4: AgentManager (動的エージェント管理)

```gdscript
# godot_project/scripts/AgentManager.gd
class_name AgentManager
extends Node3D

const AgentAvatarScene := preload("res://scenes/agents/AgentAvatar.tscn")

var _agents: Dictionary = {}  # agent_id -> AgentController


func get_or_create_agent(agent_id: String) -> AgentController:
    """Get existing agent or create new one."""
    if _agents.has(agent_id):
        return _agents[agent_id]

    var avatar: AgentController = AgentAvatarScene.instantiate()
    avatar.agent_id = agent_id
    avatar.name = agent_id
    add_child(avatar)
    _agents[agent_id] = avatar
    print("[AgentManager] Created agent: %s" % agent_id)
    return avatar


func handle_envelope(envelope: Dictionary) -> void:
    """Route envelope to the correct agent."""
    var agent_id: String = envelope.get("agent_id", "")
    if agent_id == "":
        push_warning("[AgentManager] Envelope missing agent_id")
        return

    var agent := get_or_create_agent(agent_id)
    agent.update_from_envelope(envelope)
```

---

## パターン 5: AnimationTree ステートマシン設定手順

Godot エディタでの設定手順:

1. AgentAvatar シーンに `AnimationPlayer` を追加
2. `.glb` からインポートしたアニメーションクリップを `AnimationPlayer` に登録:
   - `Idle` (デフォルト、ループ)
   - `Walking` (ループ)
   - `Sitting` (ループ)
   - `Bowing` (ワンショット → Idle に自動遷移)
   - `Speaking` (ループ)
   - `Meditating` (ループ)
3. `AnimationTree` を追加し、`AnimationNodeStateMachine` をルートに設定
4. 各アニメーション間の遷移を定義:
   ```
   Idle <-> Walking
   Idle <-> Sitting
   Idle <-> Speaking
   Idle <-> Meditating
   Idle -> Bowing -> Idle (自動遷移)
   Walking -> Sitting (peripatos -> chashitsu 遷移)
   ```
5. `AnimationTree.active = true` を設定

**命名規約**: アニメーション名は英語 PascalCase。
Python 側の action 値 (snake_case) との対応は `ANIMATION_MAP` 辞書で管理する。

---

## ゾーン座標の設計指針

| ゾーン | 中心座標 (目安) | 特徴 |
|---|---|---|
| study | (0, 0, 0) | 中央、書斎・デフォルト位置 |
| peripatos | (-20, 0, 0) ~ (20, 0, 0) | 東西に延びる歩行路 |
| chashitsu | (15, 0, 15) | 北東、狭い空間 |
| agora | (0, 0, -15) | 南側、広い広場 |
| garden | (-15, 0, 15) | 北西、自然空間 |

ゾーン間の移動はナビメッシュ (NavigationMesh) で経路探索する。
