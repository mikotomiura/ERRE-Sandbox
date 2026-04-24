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
##
## ``base_terrain`` is deliberately first so its 100x100 plane (Slice β,
## grown from the original 60 m) spawns underneath the named zones — it
## addresses the M4-live observation that avatars whose position drifts
## outside a zone plane appeared to walk on the void
## (m5-godot-zone-visuals design §Zone MVP + Peripatos retreat).
const ZONE_MAP: Dictionary = {
	"base_terrain": preload("res://scenes/zones/BaseTerrain.tscn"),
	"peripatos": preload("res://scenes/zones/Peripatos.tscn"),
	"chashitsu": preload("res://scenes/zones/Chashitsu.tscn"),
	"zazen": preload("res://scenes/zones/Zazen.tscn"),
	"study": preload("res://scenes/zones/Study.tscn"),
	"agora": preload("res://scenes/zones/Agora.tscn"),
	"garden": preload("res://scenes/zones/Garden.tscn"),
}

@onready var _debug_overlay: Label = $UILayer/DebugOverlay
# Typed as Node (not EnvelopeRouter) to side-step class_name resolution during
# the first headless boot — see AgentManager.gd for the full rationale.
@onready var _envelope_router: Node = $EnvelopeRouter
@onready var _websocket_client: Node = $WebSocketClient
# M6-B-2b: 3D content (ZoneManager / Camera / avatars) moved into a
# SubViewport so the ReasoningPanel sidebar lives outside the world frame
# via HBoxContainer split. Path is long but stable — the next refactor
# should introduce a WorldViewport scene so this path stays short again.
@onready var _zone_manager: Node = $UILayer/Split/WorldView/WorldViewport/ZoneManager

# M6-B-2b: live overlay state for whether the WS connected and whether any
# world_tick has arrived. Combined by ``_refresh_overlay`` so "disconnected"
# is visible to the researcher — earlier sessions silently rendered an
# empty world when the gateway URL was misconfigured.
var _ws_connected: bool = false
var _last_tick: int = -1
var _last_active_agents: int = 0


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

	if _websocket_client and _websocket_client.has_signal("connection_status_changed"):
		_websocket_client.connection_status_changed.connect(_on_connection_status_changed)

	_spawn_initial_zones()
	_refresh_overlay()


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
	_last_tick = tick
	_last_active_agents = active_agents
	_refresh_overlay(wall_clock)


func _on_connection_status_changed(connected: bool) -> void:
	_ws_connected = connected
	_refresh_overlay()


func _refresh_overlay(wall_clock: String = "") -> void:
	if _debug_overlay == null:
		return
	var status := "WS connected" if _ws_connected else "WS disconnected"
	if _last_tick < 0:
		_debug_overlay.text = "[%s]  awaiting first tick…  (1/2/3 cam, WASD pan, drag orbit)" % status
	else:
		_debug_overlay.text = (
			"[%s]  tick=%d  agents=%d  clock=%s"
			% [status, _last_tick, _last_active_agents, wall_clock]
		)


func _on_error_reported(code: String, detail: String) -> void:
	# ``error`` envelopes carry structured gateway-side anomalies (ErrorMsg in
	# schemas.py §7), not Godot engine failures. Use push_warning so stderr is
	# not polluted with ``ERROR:`` lines that existing boot tests guard against.
	push_warning("[WorldManager] gateway error code=%s detail=%s" % [code, detail])
	print("[WorldManager] error_reported code=%s detail=%s" % [code, detail])
