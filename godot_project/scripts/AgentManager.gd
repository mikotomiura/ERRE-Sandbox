# AgentManager — T17 godot-peripatos-scene (upgraded from T16 log stubs)
#
# Connects to EnvelopeRouter's four agent-scoped signals (T16 contract) and
# drives avatar lifecycle + behaviour. Key properties:
#
#   * AVATAR_SCENE is referenced via ``preload`` so MainScene.tscn does not
#     need an ``agent_avatar_scene`` export — T17 v2 design deliberately
#     avoids touching MainScene.tscn (closes T16 L5: manual-edit accumulation).
#   * Router is resolved as a plain ``Node`` and guarded by ``has_signal``
#     (T16 judgement 4: class_name cross-refs break the first headless boot
#     before .godot/ cache is populated).
#   * Each signal handler goes through ``_get_or_create_avatar`` so fixture
#     replays that start mid-stream (e.g. ``speech`` before ``agent_update``)
#     still work; the avatar is spawned lazily on first touch.
class_name AgentManager
extends Node3D

@export var router_path: NodePath

const _REQUIRED_SIGNALS: PackedStringArray = [
	"agent_updated",
	"speech_delivered",
	"move_issued",
	"animation_changed",
]

const AVATAR_SCENE: PackedScene = preload("res://scenes/agents/AgentAvatar.tscn")

var _avatars: Dictionary = {}  # agent_id (String) -> avatar Node


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


func _get_or_create_avatar(agent_id: String) -> Node:
	if agent_id == "":
		push_warning("[AgentManager] missing agent_id; ignoring envelope")
		return null
	if _avatars.has(agent_id):
		return _avatars[agent_id]
	var avatar := AVATAR_SCENE.instantiate()
	# Duck-typed contract: AVATAR_SCENE root is expected to expose ``set_agent_id``.
	if avatar.has_method("set_agent_id"):
		avatar.set_agent_id(agent_id)
	else:
		push_error("[AgentManager] avatar missing set_agent_id method; check scene attach")
		avatar.queue_free()
		return null
	add_child(avatar)
	_avatars[agent_id] = avatar
	print("[AgentManager] avatar spawned agent_id=%s" % agent_id)
	return avatar


func _on_agent_updated(agent_id: String, agent_state: Dictionary) -> void:
	var avatar := _get_or_create_avatar(agent_id)
	if avatar == null:
		return
	avatar.update_position_from_state(agent_state)


func _on_speech_delivered(agent_id: String, utterance: String, zone: String) -> void:
	var avatar := _get_or_create_avatar(agent_id)
	if avatar == null:
		return
	avatar.show_speech(utterance, zone)


func _on_move_issued(agent_id: String, target: Dictionary, speed: float) -> void:
	var avatar := _get_or_create_avatar(agent_id)
	if avatar == null:
		return
	avatar.set_move_target(target, speed)


func _on_animation_changed(agent_id: String, animation_name: String, _loop: bool) -> void:
	var avatar := _get_or_create_avatar(agent_id)
	if avatar == null:
		return
	avatar.set_animation(animation_name)
