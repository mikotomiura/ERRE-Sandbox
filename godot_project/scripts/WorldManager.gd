## MainScene root controller for ERRE-Sandbox.
##
## Owns the boot log and the DebugOverlay label; later phases wire up the
## WebSocketClient -> AgentManager data flow through this node.
##
# Handoff plan (not part of the API docs):
#   * T16 godot-ws-client       -- attach WebSocketClient.gd to $WebSocketClient
#                                  and route envelope_received signals here
#   * T17 godot-peripatos-scene -- instance Peripatos.tscn under $ZoneManager
#   * M5 zone expansion         -- add Chashitsu / Agora / Garden scenes
class_name WorldManager
extends Node3D

@onready var _debug_overlay: Label = $UILayer/DebugOverlay


func _ready() -> void:
    print("[WorldManager] ERRE-Sandbox booted (tick 0, T15 scaffolded handoff)")
    if _debug_overlay:
        _debug_overlay.text = "ERRE-Sandbox -- T15 init (boot OK)"
    else:
        push_warning("[WorldManager] DebugOverlay not found; MainScene tree changed?")
