## MainScene root controller for ERRE-Sandbox.
##
## Owns the boot log, the DebugOverlay label, and wires global
## ``EnvelopeRouter`` signals (``world_ticked`` / ``error_reported``) to
## the overlay so humans watching the headless run see progress.
##
# Handoff plan (not part of the API docs):
#   * T16 godot-ws-client       -- DONE: WebSocketClient + EnvelopeRouter +
#                                  AgentManager wired in MainScene.tscn; this
#                                  manager subscribes to router world/error
#                                  signals.
#   * T17 godot-peripatos-scene -- instance Peripatos.tscn under $ZoneManager
#   * M5 zone expansion         -- add Chashitsu / Agora / Garden scenes
class_name WorldManager
extends Node3D

@onready var _debug_overlay: Label = $UILayer/DebugOverlay
# Typed as Node (not EnvelopeRouter) to side-step class_name resolution during
# the first headless boot — see AgentManager.gd for the full rationale.
@onready var _envelope_router: Node = $EnvelopeRouter


func _ready() -> void:
	print("[WorldManager] ERRE-Sandbox booted (tick 0, T16 wired handoff)")
	if _debug_overlay:
		_debug_overlay.text = "ERRE-Sandbox -- T16 wired (boot OK)"
	else:
		push_warning("[WorldManager] DebugOverlay not found; MainScene tree changed?")

	if _envelope_router:
		_envelope_router.world_ticked.connect(_on_world_ticked)
		_envelope_router.error_reported.connect(_on_error_reported)
	else:
		push_error("[WorldManager] EnvelopeRouter not found under MainScene")


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
