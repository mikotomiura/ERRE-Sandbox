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
## Default sustain time for a dialog_turn bubble (matches spike's ~4s
## readability window; fade in/out is 0.3s each inside DialogBubble.gd).
const DEFAULT_DIALOG_DURATION_SEC: float = 4.0

## Radius (m) of the per-agent visual offset ring. Two avatars whose server-
## side positions collapse to the same zone-spawn coordinate would otherwise
## render perfectly co-located; the offset spreads them around a small circle
## so the user can visually distinguish them. The offset is purely visual —
## ``set_move_target`` / ``update_position_from_state`` apply it to both ends
## of the tween so the relative distance and duration are unchanged, and the
## server's proximity / dialog-auto-fire logic (which reasons over the
## unmodified position) is unaffected.
const VISUAL_OFFSET_RADIUS_M: float = 0.6

@export var agent_id: String = ""

@onready var _body: Node3D = $Body
@onready var _speech_bubble: Label3D = $SpeechBubble
@onready var _dialog_bubble: Label3D = $DialogBubble

var _current_animation: String = "idle"
var _current_tween: Tween = null
var _current_erre_mode: String = ""
var _visual_offset: Vector3 = Vector3.ZERO


func set_agent_id(new_id: String) -> void:
	agent_id = new_id
	name = new_id  # enables ``AgentManager/<agent_id>`` path lookups
	# Deterministic per-agent offset on a horizontal ring. ``String.hash()``
	# returns a stable 32-bit integer so the same agent_id always lands on the
	# same azimuth across runs, which keeps recordings reproducible.
	var azimuth: float = float(new_id.hash() % 360) * (PI / 180.0)
	_visual_offset = Vector3(
		cos(azimuth) * VISUAL_OFFSET_RADIUS_M,
		0.0,
		sin(azimuth) * VISUAL_OFFSET_RADIUS_M,
	)


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
	global_position = dest + _visual_offset
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
	# Apply the per-agent visual offset to the destination. ``global_position``
	# already carries the offset (set on update_position_from_state), so the
	# tween's start and end are both shifted by the same vector — distance and
	# duration are unchanged, the visual stays in sync with server-tracked state.
	var visual_dest: Vector3 = dest + _visual_offset
	var distance := global_position.distance_to(visual_dest)
	if distance < ARRIVAL_EPSILON:
		return
	if _current_tween != null and _current_tween.is_running():
		_current_tween.kill()
	var effective_speed: float = max(speed, MIN_EFFECTIVE_SPEED)
	var duration: float = min(distance / effective_speed, MAX_TWEEN_DURATION)
	# Look along the ground plane so a ``dest`` directly above/below the avatar
	# cannot produce a vertical-pitched look_at (code review MEDIUM #2).
	var horizontal_dest := Vector3(visual_dest.x, global_position.y, visual_dest.z)
	if not global_position.is_equal_approx(horizontal_dest):
		look_at(horizontal_dest, Vector3.UP)
	_current_tween = create_tween()
	_current_tween.tween_property(self, "global_position", visual_dest, duration)
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


func show_dialog_turn(utterance: String) -> void:
	# Delegates to the DialogBubble child so the controller stays a thin
	# coordinator — fade Tween, text, and auto-hide live on the bubble itself
	# (design.md §composition). The log prefix mirrors the other per-action
	# lines so fixture-replay tests can assert the delegation chain.
	_dialog_bubble.show_for(utterance, DEFAULT_DIALOG_DURATION_SEC)
	print(
		"[AgentController] show_dialog_turn agent_id=%s len=%d"
		% [agent_id, utterance.length()]
	)


func apply_erre_mode(mode: String) -> void:
	# Delegates tint to the Body's BodyTinter script. Idempotent on unchanged
	# modes so successive ``agent_update`` envelopes carrying the same mode
	# don't start redundant tweens.
	if mode == "":
		return
	if mode == _current_erre_mode:
		return
	_current_erre_mode = mode
	if _body.has_method("apply_mode"):
		_body.apply_mode(mode)
	else:
		push_warning(
			"[AgentController] Body missing apply_mode; BodyTinter not attached?"
		)
	print(
		"[AgentController] apply_erre_mode agent_id=%s mode=%s"
		% [agent_id, mode]
	)
