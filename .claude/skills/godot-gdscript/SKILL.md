---
name: godot-gdscript
description: >
  Godot 4.4 / GDScript のコーディング規約と WebSocket 通信パターン。
  godot_project/ 配下の .gd スクリプト・.tscn シーンを作成・修正する時に必須参照。
  AgentController.gd / WorldManager.gd / WebSocket クライアントを書く時、
  AnimationTree / AnimationPlayer のステートマシンを設定する時、
  5 ゾーン (study/peripatos/chashitsu/agora/garden) のシーンを作成する時に自動召喚される。
  ControlEnvelope JSON の受信・パース処理を書く時、
  ui/godot_bridge.py (Python 側) を変更する時にも参照すること。
  godot_project/ 内に Python コードを置くことは禁止 (WebSocket で疎結合)。
allowed-tools: Read, Grep, Glob
---

# Godot GDScript

## このスキルの目的

ERRE-Sandbox の 3D 表現は Godot 4.4 が担う。G-GEAR (Python 側) と Godot は
WebSocket で完全に分離されており、Godot 側は受信した ControlEnvelope JSON を
3D シーンに反映する責務のみを持つ。この分離を維持しつつ、
GDScript のコーディング規約と通信パターンを統一する。

## 適用範囲

### 適用するもの
- `godot_project/scripts/` 配下のすべての `.gd` ファイル
- `godot_project/scenes/` 配下のすべての `.tscn` ファイル
- `src/erre_sandbox/ui/godot_bridge.py` (Python 側 WebSocket ブリッジ)

### 適用しないもの
- `src/erre_sandbox/` の他の Python コード (→ `python-standards` Skill)
- Blender アセット制作 (→ `blender-pipeline` Skill)

## ルール 1: 命名規則 (Godot 標準準拠)

| 対象 | 規則 | 例 |
|---|---|---|
| GDScript ファイル | PascalCase | `AgentController.gd`, `WorldManager.gd` |
| シーンファイル | PascalCase | `MainScene.tscn`, `Peripatos.tscn` |
| 変数・関数 | snake_case | `agent_id`, `_on_message_received()` |
| 定数 | UPPER_SNAKE_CASE | `WS_URL`, `RECONNECT_DELAY` |
| シグナル | snake_case | `agent_updated`, `connection_lost` |
| ノード名 | PascalCase | `AgentAvatar`, `ZoneManager` |

```gdscript
# ✅ 良い例
class_name AgentController
extends CharacterBody3D

const WS_URL: String = "ws://g-gear.local:8000/stream"
var agent_id: String = ""
signal agent_updated(agent_id: String, position: Vector3)

func _on_message_received(data: Dictionary) -> void:
    pass
```

```gdscript
# ❌ 悪い例
class_name agentController    # PascalCase でない
var AgentId: String = ""      # 変数は snake_case
signal AgentUpdated           # シグナルは snake_case
```

## ルール 2: WebSocket 通信パターン

Godot は `ws://g-gear.local:8000/stream` から ControlEnvelope JSON を受信する。
自動再接続を必ず実装する (5 秒間隔)。

```gdscript
# ✅ 良い例 — WebSocket クライアント with 自動再接続
class_name WebSocketClient
extends Node

const WS_URL: String = "ws://g-gear.local:8000/stream"
const RECONNECT_DELAY: float = 5.0

var _ws: WebSocketPeer = WebSocketPeer.new()
var _connected: bool = false

signal envelope_received(envelope: Dictionary)
signal connection_status_changed(connected: bool)

func _ready() -> void:
    _connect_to_server()

func _connect_to_server() -> void:
    var err := _ws.connect_to_url(WS_URL)
    if err != OK:
        push_warning("WebSocket connection failed, retrying in %ss" % RECONNECT_DELAY)
        _schedule_reconnect()

func _process(_delta: float) -> void:
    _ws.poll()
    var state := _ws.get_ready_state()

    if state == WebSocketPeer.STATE_OPEN:
        if not _connected:
            _connected = true
            connection_status_changed.emit(true)
        while _ws.get_available_packet_count() > 0:
            var raw := _ws.get_packet().get_string_from_utf8()
            var parsed: Variant = JSON.parse_string(raw)
            if parsed is Dictionary:
                envelope_received.emit(parsed)

    elif state == WebSocketPeer.STATE_CLOSED:
        if _connected:
            _connected = false
            connection_status_changed.emit(false)
            _schedule_reconnect()

func _schedule_reconnect() -> void:
    await get_tree().create_timer(RECONNECT_DELAY).timeout
    _connect_to_server()
```

```gdscript
# ❌ 悪い例 — 再接続なし
func _ready() -> void:
    var ws := WebSocketPeer.new()
    ws.connect_to_url("ws://g-gear.local:8000/stream")
    # 切断されたら終わり
```

## ルール 3: ControlEnvelope の処理

ControlEnvelope は `kind` フィールドでメッセージ種別を識別する。

```gdscript
# ✅ 良い例 — kind で分岐
func _on_envelope_received(envelope: Dictionary) -> void:
    var kind: String = envelope.get("kind", "")
    match kind:
        "agent_state":
            _update_agent(envelope)
        "agent_move":
            _move_agent(envelope)
        "speech_bubble":
            _show_speech(envelope)
        "mode_change":
            _change_mode(envelope)
        _:
            push_warning("Unknown envelope kind: %s" % kind)
```

```gdscript
# ❌ 悪い例 — kind チェックなし
func _on_envelope_received(envelope: Dictionary) -> void:
    _update_agent(envelope)  # kind が何であっても agent 更新してしまう
```

## ルール 4: 5 ゾーンのシーン構造

各ゾーンは独立したシーン (.tscn) として作成し、MainScene から参照する。

```
godot_project/scenes/
├── MainScene.tscn          # ルートシーン
├── zones/
│   ├── Study.tscn          # 書斎ゾーン
│   ├── Peripatos.tscn      # 歩行路ゾーン
│   ├── Chashitsu.tscn      # 茶室ゾーン
│   ├── Agora.tscn          # 広場ゾーン
│   └── Garden.tscn         # 庭園ゾーン
└── agents/
    └── AgentAvatar.tscn    # エージェントアバターのプレハブ
```

```gdscript
# ✅ 良い例 — ゾーン名は schemas.py の Literal と一致させる
const ZONE_MAP: Dictionary = {
    "study": preload("res://scenes/zones/Study.tscn"),
    "peripatos": preload("res://scenes/zones/Peripatos.tscn"),
    "chashitsu": preload("res://scenes/zones/Chashitsu.tscn"),
    "agora": preload("res://scenes/zones/Agora.tscn"),
    "garden": preload("res://scenes/zones/Garden.tscn"),
}
```

## ルール 5: アニメーションステートマシン

エージェントのアニメーションは AnimationTree + AnimationPlayer で管理する。
アニメーション名は Python 側の action 値と対応させる。

```gdscript
# ✅ 良い例 — AnimationTree でステート切り替え
@onready var anim_tree: AnimationTree = $AnimationTree

const ANIMATION_MAP: Dictionary = {
    "walk": "Walking",
    "sit": "Sitting",
    "bow": "Bowing",
    "idle": "Idle",
    "speak": "Speaking",
    "reflect": "Meditating",
}

func set_animation(action: String) -> void:
    var anim_name: String = ANIMATION_MAP.get(action, "Idle")
    var state_machine: AnimationNodeStateMachinePlayback = anim_tree.get(
        "parameters/playback"
    )
    state_machine.travel(anim_name)
```

## ルール 6: godot_project/ 内に Python コードを置かない (絶対禁止)

```
# ❌ 絶対禁止 — godot_project/ に .py ファイルを置く
godot_project/scripts/websocket_handler.py   # GDScript で書くこと

# ✅ 正しい配置
godot_project/scripts/WebSocketClient.gd     # Godot 側は GDScript
src/erre_sandbox/ui/godot_bridge.py          # Python 側は ui/ に配置
```

Python 側と Godot 側の通信は **WebSocket のみ** で行う。
`ui/godot_bridge.py` は `schemas.py` のみに依存する (architecture-rules 参照)。

## チェックリスト

- [ ] GDScript ファイル名が PascalCase か
- [ ] 変数・関数が snake_case、定数が UPPER_SNAKE_CASE か
- [ ] WebSocket クライアントに自動再接続 (5 秒間隔) があるか
- [ ] ControlEnvelope の `kind` フィールドで分岐しているか
- [ ] ゾーン名が `study/peripatos/chashitsu/agora/garden` と一致しているか
- [ ] アニメーション名が Python 側の action 値と対応しているか
- [ ] `godot_project/` 内に `.py` ファイルがないか
- [ ] `ui/godot_bridge.py` が `schemas.py` のみに依存しているか

## 補足資料

- `patterns.md` — WebSocket クライアント完全実装、シーンノード階層、アニメーション設定

## 関連する他の Skill

- `architecture-rules` — `ui/` → `schemas.py` のみ依存、`godot_project/` に Python 禁止
- `error-handling` — WebSocket 再接続パターン (Python 側)
- `python-standards` — `ui/godot_bridge.py` のコーディング規約
- `blender-pipeline` — .glb アセットの制作ルールとエクスポート手順
- `persona-erre` — ERRE モード・ゾーン対応 (mode_change envelope の意味)
