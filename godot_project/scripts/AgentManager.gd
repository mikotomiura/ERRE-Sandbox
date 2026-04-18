# AgentManager — T16 godot-ws-client
#
# Subscribes to EnvelopeRouter signals that concern a specific agent and
# reacts to them. In T16 every handler is a log stub: the scope is limited
# to proving the signal wiring works end to end via fixtures. T17
# ``godot-peripatos-scene`` replaces these stubs with real avatar
# instantiation + movement + animation, reusing the same signal surface.
#
# NOTE: Router is resolved as a plain ``Node`` rather than through the
# ``EnvelopeRouter`` class_name. Godot's global class registry is populated
# after an editor pass, but headless boots without a pre-warmed ``.godot/``
# cache fail to resolve the class_name during parse. ``has_signal`` gates
# each connection so a wrong node fails loudly instead of crashing.
class_name AgentManager
extends Node3D

@export var router_path: NodePath

const _REQUIRED_SIGNALS: PackedStringArray = [
	"agent_updated",
	"speech_delivered",
	"move_issued",
	"animation_changed",
]


func _ready() -> void:
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
	if router_path != NodePath(""):
		var node := get_node_or_null(router_path)
		if node != null:
			return node
	return get_tree().root.find_child("EnvelopeRouter", true, false)


func _on_agent_updated(agent_id: String, agent_state: Dictionary) -> void:
	var tick: int = int(agent_state.get("tick", -1))
	print("[AgentManager] agent_updated agent_id=%s tick=%d" % [agent_id, tick])


func _on_speech_delivered(agent_id: String, utterance: String, zone: String) -> void:
	print(
		"[AgentManager] speech_delivered agent_id=%s zone=%s utterance=%s"
		% [agent_id, zone, utterance]
	)


func _on_move_issued(agent_id: String, target: Dictionary, speed: float) -> void:
	print(
		"[AgentManager] move_issued agent_id=%s target_zone=%s speed=%.2f"
		% [agent_id, String(target.get("zone", "")), speed]
	)


func _on_animation_changed(agent_id: String, animation_name: String, loop: bool) -> void:
	print(
		"[AgentManager] animation_changed agent_id=%s name=%s loop=%s"
		% [agent_id, animation_name, str(loop)]
	)
