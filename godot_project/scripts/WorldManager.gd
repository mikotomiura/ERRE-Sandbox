## MainScene root controller for ERRE-Sandbox.
##
## Owns the boot log, the DebugOverlay label, wires global
## ``EnvelopeRouter`` signals (``world_ticked`` / ``error_reported``) to the
## overlay, and spawns the zones listed in ``ZONE_MAP`` under
## ``$ZoneManager`` on boot.
##
# Handoff plan (not part of the API docs):
#   * T16 godot-ws-client       -- DONE: WebSocketClient + EnvelopeRouter +
#                                  AgentManager wired in MainScene.tscn; this
#                                  manager subscribes to router world/error
#                                  signals.
#   * T17 godot-peripatos-scene -- DONE: ZONE_MAP + _spawn_initial_zones()
#                                  instantiate Peripatos under $ZoneManager.
#   * M5 world-zone-triggers    -- extend ZONE_MAP with Chashitsu / Agora /
#                                  Garden / Study scenes (key = Zone literal
#                                  from schemas.py §2).
class_name WorldManager
extends Node3D

## Zones that spawn on boot. Keys MUST match ``schemas.py`` ``Zone`` literals
## so gateway-issued ``move.target.zone`` strings resolve to an existing node.
## Add new scenes here rather than editing MainScene.tscn; keeping the zone
## list in code lets the editor-less workflow stay clean (T16 judgement 9 +
## T17 v2 design §Avatar 構造).
const ZONE_MAP: Dictionary = {
	"peripatos": preload("res://scenes/zones/Peripatos.tscn"),
	# M5 additions will go here: study / chashitsu / agora / garden.
}

@onready var _debug_overlay: Label = $UILayer/DebugOverlay
# Typed as Node (not EnvelopeRouter) to side-step class_name resolution during
# the first headless boot — see AgentManager.gd for the full rationale.
@onready var _envelope_router: Node = $EnvelopeRouter
@onready var _zone_manager: Node = $ZoneManager


func _ready() -> void:
	print("[WorldManager] ERRE-Sandbox booted (tick 0, T17 peripatos online)")
	if _debug_overlay:
		_debug_overlay.text = "ERRE-Sandbox -- T17 wired (boot OK)"
	else:
		push_warning("[WorldManager] DebugOverlay not found; MainScene tree changed?")

	if _envelope_router:
		_envelope_router.world_ticked.connect(_on_world_ticked)
		_envelope_router.error_reported.connect(_on_error_reported)
	else:
		push_error("[WorldManager] EnvelopeRouter not found under MainScene")

	_spawn_initial_zones()


func _spawn_initial_zones() -> void:
	if _zone_manager == null:
		push_error("[WorldManager] ZoneManager not found; cannot spawn zones")
		return
	for zone_name: String in ZONE_MAP.keys():
		var scene: PackedScene = ZONE_MAP[zone_name]
		var zone_instance := scene.instantiate()
		# Capitalise so the node path reads ``ZoneManager/Peripatos`` while the
		# key stays lowercase to match the Zone literal.
		zone_instance.name = zone_name.capitalize()
		_zone_manager.add_child(zone_instance)
		print("[WorldManager] zone spawned name=%s" % zone_name)


func _on_world_ticked(wall_clock: String, tick: int, active_agents: int) -> void:
	print(
		"[WorldManager] world_ticked wall_clock=%s tick=%d active_agents=%d"
		% [wall_clock, tick, active_agents]
	)
	if _debug_overlay:
		_debug_overlay.text = "tick=%d agents=%d clock=%s" % [tick, active_agents, wall_clock]


func _on_error_reported(code: String, detail: String) -> void:
	# ``error`` envelopes carry structured gateway-side anomalies (ErrorMsg in
	# schemas.py §7), not Godot engine failures. Use push_warning so stderr is
	# not polluted with ``ERROR:`` lines that existing boot tests guard against.
	push_warning("[WorldManager] gateway error code=%s detail=%s" % [code, detail])
	print("[WorldManager] error_reported code=%s detail=%s" % [code, detail])
