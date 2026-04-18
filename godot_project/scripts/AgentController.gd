# AgentController — T17 godot-peripatos-scene
#
# Attached to ``scenes/agents/AgentAvatar.tscn``. One instance per agent,
# spawned by ``AgentManager`` in response to ``EnvelopeRouter.agent_updated``.
# Responsibilities:
#   1. Hold the agent_id and keep the Node name in sync for predictable paths
#   2. Apply absolute position updates from AgentState snapshots
#   3. Drive movement via a Tween whose duration uses the envelope's ``speed``
#      (so the Contract's speed is honoured, not discarded — see T17 v2 design,
#      V1-W2 resolution)
#   4. Record animation state and log the change (AnimationPlayer/Tree are
#      intentionally absent until M4 imports glTF clips)
#   5. Surface speech as a Label3D above the avatar (no auto-hide in T17)
#
# NOTE on ``class_name``: declaring it is safe (EnvelopeRouter / AgentManager /
# WorldManager / WebSocketClient all do). What T16 decisions.md judgement 4
# forbade is **using** a class_name as a cross-script TYPE annotation before the
# ``.godot/`` cache is populated. AgentManager sticks to ``Node`` + duck typing
# via ``has_method`` when holding AgentController references, so declaring
# class_name here is harmless and helps IDE autocompletion.
class_name AgentController
extends Node3D

## Minimum effective speed in m/s. Prevents a zero/negative envelope speed from
## producing an infinite or negative Tween duration.
const MIN_EFFECTIVE_SPEED: float = 0.01
## Below this distance a ``set_move_target`` call is considered a no-op.
const ARRIVAL_EPSILON: float = 0.01
## Upper bound on a single Tween's duration. A bogus (distance, speed) pair
## from the gateway could otherwise queue a multi-day animation that pins
## memory for the rest of the session (security review MEDIUM #2).
const MAX_TWEEN_DURATION: float = 30.0

@export var agent_id: String = ""

@onready var _body: MeshInstance3D = $Body
@onready var _speech_bubble: Label3D = $SpeechBubble

var _current_animation: String = "idle"
var _current_tween: Tween = null


func set_agent_id(new_id: String) -> void:
	agent_id = new_id
	name = new_id  # enables ``AgentManager/<agent_id>`` path lookups


func update_position_from_state(agent_state: Dictionary) -> void:
	var pos: Dictionary = agent_state.get("position", {})
	if pos.is_empty():
		return
	var dest := Vector3(
		float(pos.get("x", 0.0)),
		float(pos.get("y", 0.0)),
		float(pos.get("z", 0.0)),
	)
	# ``float("nan")`` / ``float("inf")`` slip through JSON.parse when the
	# gateway uses ``allow_nan=True`` defaults; a NaN in Transform3D corrupts
	# AABB culling for the whole scene tree (security review MEDIUM #1).
	if not dest.is_finite():
		push_warning(
			"[AgentController] non-finite position for agent_id=%s; ignoring" % agent_id
		)
		return
	global_position = dest
	var tick: int = int(agent_state.get("tick", -1))
	print(
		"[AgentController] agent_update agent_id=%s tick=%d pos=(%.2f, %.2f, %.2f)"
		% [agent_id, tick, dest.x, dest.y, dest.z]
	)


func set_move_target(target: Dictionary, speed: float) -> void:
	var dest := Vector3(
		float(target.get("x", 0.0)),
		float(target.get("y", 0.0)),
		float(target.get("z", 0.0)),
	)
	# Guard against NaN / inf slipping in from a permissive JSON encoder
	# (security review MEDIUM #1).
	if not dest.is_finite():
		push_warning(
			"[AgentController] non-finite move target for agent_id=%s; ignoring" % agent_id
		)
		return
	var distance := global_position.distance_to(dest)
	if distance < ARRIVAL_EPSILON:
		return
	if _current_tween != null and _current_tween.is_running():
		_current_tween.kill()
	var effective_speed: float = max(speed, MIN_EFFECTIVE_SPEED)
	var duration: float = min(distance / effective_speed, MAX_TWEEN_DURATION)
	# Look along the ground plane so a ``dest`` directly above/below the avatar
	# cannot produce a vertical-pitched look_at (code review MEDIUM #2).
	var horizontal_dest := Vector3(dest.x, global_position.y, dest.z)
	if not global_position.is_equal_approx(horizontal_dest):
		look_at(horizontal_dest, Vector3.UP)
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
	# Length is logged instead of the full utterance to keep stdout compact
	# during regression runs (test assertions only check prefix + zone).
	print(
		"[AgentController] speech agent_id=%s zone=%s len=%d"
		% [agent_id, zone, utterance.length()]
	)
