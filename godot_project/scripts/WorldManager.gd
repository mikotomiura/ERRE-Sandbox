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
# M7-ζ-1: day/night cycle targets. Live verification (2026-04-26) flagged
# the always-night SOLID COLOR background as an immersion blocker; this
# manager now drives the WorldEnvironment colour and DirectionalLight3D
# basis on a Timer (1 Hz) so the world wall-clock visibly cycles.
@onready var _world_environment: WorldEnvironment = $UILayer/Split/WorldView/WorldViewport/Environment
@onready var _directional_light: DirectionalLight3D = $UILayer/Split/WorldView/WorldViewport/Environment/DirectionalLight3D

# M6-B-2b: live overlay state for whether the WS connected and whether any
# world_tick has arrived. Combined by ``_refresh_overlay`` so "disconnected"
# is visible to the researcher — earlier sessions silently rendered an
# empty world when the gateway URL was misconfigured.
var _ws_connected: bool = false
var _last_tick: int = -1
var _last_active_agents: int = 0

# M7-ζ-1: full-day length in wall-clock seconds. Default 1800 (30 min) so a
# typical live run cycles dawn → noon → dusk → midnight at least once.
@export var day_cycle_seconds: float = 1800.0
var _day_phase_s: float = 0.0
var _day_timer: Timer = null
# Captured from the authored DirectionalLight3D position at boot (review M2)
# so we only spin the light's basis around its tscn-defined origin — if the
# scene moves the light, this code follows without code edit.
var _light_origin: Vector3 = Vector3.ZERO
# Palette keyed at midnight / dawn / noon / dusk. The day cycle linearly
# interpolates between adjacent keys so 1 Hz steps produce a smooth (not
# step-quantised) sky transition without per-frame work.
const _PALETTE_BG: Dictionary = {
	"midnight": Color(0.04, 0.06, 0.12, 1.0),
	"dawn":     Color(0.45, 0.32, 0.30, 1.0),
	"noon":     Color(0.55, 0.68, 0.82, 1.0),
	"dusk":     Color(0.42, 0.28, 0.24, 1.0),
}
const _PALETTE_AMB: Dictionary = {
	"midnight": 0.10,
	"dawn":     0.35,
	"noon":     0.65,
	"dusk":     0.32,
}


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
	_setup_day_cycle()
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


# ---- M7-ζ-1 day/night cycle ----


func _setup_day_cycle() -> void:
	# Disable gracefully when the SubViewport tree is missing (FixtureHarness
	# or unit-test scenes can omit the WorldEnvironment). The boot keeps
	# functioning, just without sky/light progression.
	if _world_environment == null or _directional_light == null:
		push_warning("[WorldManager] day/night targets missing; cycle disabled")
		return
	if day_cycle_seconds <= 0.0:
		push_warning("[WorldManager] day_cycle_seconds <= 0; cycle disabled")
		return
	# Capture the authored light position so phase paints rotate around the
	# tscn-defined origin (review M2 — was hard-coded to (0, 10, 0) before).
	_light_origin = _directional_light.position
	_day_timer = Timer.new()
	_day_timer.name = "DayCycleTimer"
	_day_timer.wait_time = 1.0
	_day_timer.autostart = true
	_day_timer.one_shot = false
	_day_timer.timeout.connect(_step_day_phase)
	add_child(_day_timer)
	# Boot at noon (phase π) so the first frame is not the worst-lit slice
	# (live observation: starting at midnight makes the world look broken on
	# entry).
	_day_phase_s = day_cycle_seconds * 0.5
	_paint_phase()


func _step_day_phase() -> void:
	if day_cycle_seconds <= 0.0:
		return
	_day_phase_s = fmod(_day_phase_s + 1.0, day_cycle_seconds)
	_paint_phase()


func _paint_phase() -> void:
	var phase: float = TAU * _day_phase_s / day_cycle_seconds
	if _directional_light != null:
		# Phase 0 puts the sun below the horizon (midnight); phase π places
		# it overhead (noon). The ``+ PI / 2.0`` offset rotates the X-axis
		# basis so the time-of-day semantics align with the palette: phase=0
		# midnight → π/2 dawn → π noon → 3π/2 dusk → 2π midnight.
		_directional_light.transform = Transform3D(
			Basis(Vector3.RIGHT, phase + PI / 2.0),
			_light_origin,
		)
	_apply_palette_for_phase(phase)


func _apply_palette_for_phase(phase: float) -> void:
	if _world_environment == null or _world_environment.environment == null:
		return
	var bg: Color
	var amb: float
	# Four equal-length quarters: midnight → dawn → noon → dusk → midnight.
	if phase < PI / 2.0:
		var t: float = phase / (PI / 2.0)
		bg = _PALETTE_BG["midnight"].lerp(_PALETTE_BG["dawn"], t)
		amb = lerp(float(_PALETTE_AMB["midnight"]), float(_PALETTE_AMB["dawn"]), t)
	elif phase < PI:
		var t: float = (phase - PI / 2.0) / (PI / 2.0)
		bg = _PALETTE_BG["dawn"].lerp(_PALETTE_BG["noon"], t)
		amb = lerp(float(_PALETTE_AMB["dawn"]), float(_PALETTE_AMB["noon"]), t)
	elif phase < 3.0 * PI / 2.0:
		var t: float = (phase - PI) / (PI / 2.0)
		bg = _PALETTE_BG["noon"].lerp(_PALETTE_BG["dusk"], t)
		amb = lerp(float(_PALETTE_AMB["noon"]), float(_PALETTE_AMB["dusk"]), t)
	else:
		var t: float = (phase - 3.0 * PI / 2.0) / (PI / 2.0)
		bg = _PALETTE_BG["dusk"].lerp(_PALETTE_BG["midnight"], t)
		amb = lerp(float(_PALETTE_AMB["dusk"]), float(_PALETTE_AMB["midnight"]), t)
	var env := _world_environment.environment
	env.background_color = bg
	env.ambient_light_color = bg.lightened(0.35)
	env.ambient_light_energy = amb
