# PerturbationTrigger — M13 live-loop-closure Issue 005 (developer-only).
#
# Fires exactly one bounded ``world_perturbation`` frame at
# ``WebSocketClient.send_perturbation`` when the developer presses
# ``TRIGGER_KEY``, so a human observer can exercise the inbound seam
# end-to-end (Godot -> gateway inbound sink -> PerceptionEvent) without
# scripting a client. This is the single inbound UI trigger scoped by
# ``.steering/20260724-m13-live-loop-closure/design-final.md`` Allowed
# Files — not a general inbound-authoring UI. The stimulus payload is
# fixed/dev-labeled: never derived from live state, never a knob/mode/
# destination override.
#
# HONEST FRAMING (design-final.md §2, binding): this is WIRING, not aha /
# emergence / effect. Pressing the key sends one bounded world stimulus;
# nothing here is measured.
#
# Inbound-only (LOW-2): ``WebSocketClient`` never receives ``world_perturbation``
# back over the wire, and ``EnvelopeRouter.gd`` has no matching branch for it
# (``tests/test_integration/test_inbound_gdscript_contract.py::
# test_router_does_not_receive_inbound_kind`` pins this).
#
# Production scripts (WebSocketClient.gd / EnvelopeRouter.gd / AgentManager.gd /
# MainScene.tscn) MUST NOT depend on this file (dev/README.md).
class_name PerturbationTrigger
extends Node

## Keyboard key that fires the dev perturbation. Chosen to avoid the WASD
## orbit-camera bindings (OrbitCameraController.gd) and Godot's default UI
## actions.
const TRIGGER_KEY: Key = KEY_P

## Fixed dev-only stimulus. Field names mirror ``WorldPerturbationMsg``
## (schemas.py §7.x): bounded, deterministic, never derived from live state.
## DEV_TARGET_AGENT_ID is a placeholder id for isolated dev probing only —
## when wiring this trigger up against a real running session, replace it
## with an agent_id that actually exists in that session's live agent
## registry (a mismatching target_agent_id is bounded-verified and dropped
## server-side, never injected — see live_loop.py's run_live_loop_capture).
const DEV_TARGET_AGENT_ID: String = "dev-probe"
const DEV_MODALITY: String = "sight"
const DEV_SOURCE_ZONE: String = "agora"
const DEV_CONTENT: String = "dev perturbation trigger (Issue 005 inbound UI)"
const DEV_INTENSITY: float = 0.5

@export var websocket_client_path: NodePath

var _ws_client: Node = null


func _ready() -> void:
	if websocket_client_path != NodePath(""):
		_ws_client = get_node_or_null(websocket_client_path)
	if _ws_client == null:
		_ws_client = get_tree().root.find_child("WebSocketClient", true, false)
	if _ws_client == null:
		push_warning("[PerturbationTrigger] WebSocketClient not found; trigger disabled")


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey):
		return
	var key_event := event as InputEventKey
	if key_event.keycode != TRIGGER_KEY or not key_event.pressed or key_event.is_echo():
		return
	_fire()


func _fire() -> void:
	if _ws_client == null or not _ws_client.has_method("send_perturbation"):
		push_warning("[PerturbationTrigger] WebSocketClient.send_perturbation unavailable")
		return
	_ws_client.send_perturbation(
		DEV_TARGET_AGENT_ID, DEV_MODALITY, DEV_SOURCE_ZONE, DEV_CONTENT, DEV_INTENSITY,
	)
	print("[PerturbationTrigger] fired dev world_perturbation (key=%s)" % TRIGGER_KEY)
