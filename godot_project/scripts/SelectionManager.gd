# SelectionManager — M6-B-1b click-to-focus for the xAI observatory.
#
# Lives in MainScene alongside the CameraRig. Listens for unhandled mouse
# clicks, does a single physics raycast against collision layer 2
# (reserved for AgentAvatar selection capsules — see the SelectionArea
# node in scenes/agents/AgentAvatar.tscn), and emits
# ``selected_agent_id`` carrying the ``AgentController.agent_id`` of
# whatever avatar the click landed on.
#
# Wiring pattern (set up in MainScene):
#   - camera_rig_path  -> ../CameraRig         (so we can ask for its Camera3D)
#   - Signal consumers: CameraRig.set_target_agent(node) + the FOLLOW mode
#                       switch, and ReasoningPanel.set_focused_agent(id).
#     Connections are authored in MainScene.tscn so this script stays a
#     single-purpose click→signal bridge.
extends Node

@export var camera_rig_path: NodePath

signal selected_agent_id(agent_id: String, agent_node: Node3D)

var _camera_rig: Node = null


func _ready() -> void:
	if camera_rig_path != NodePath(""):
		_camera_rig = get_node_or_null(camera_rig_path)
	if _camera_rig == null:
		push_warning("[SelectionManager] camera_rig_path not set; selection raycasts disabled")


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton):
		return
	var mb := event as InputEventMouseButton
	if mb.button_index != MOUSE_BUTTON_LEFT or not mb.pressed or mb.double_click:
		return
	var avatar := _pick_avatar_under_mouse(mb.position)
	if avatar == null:
		return
	var agent_id := _extract_agent_id(avatar)
	if agent_id == "":
		return
	selected_agent_id.emit(agent_id, avatar)
	# Auto-follow on click — the camera owns the actual mode switch so the
	# researcher's "press 1 then click" workflow still works.
	if _camera_rig != null:
		if _camera_rig.has_method("set_target_agent"):
			_camera_rig.set_target_agent(avatar)
		if _camera_rig.has_method("set_mode"):
			# Only promote from OVERVIEW (Mode value 0) — preserve an explicit
			# MIND_PEEK choice. Use get() with default so the call is safe when
			# a future rig replaces the exported ``mode`` property name.
			var current_mode: int = int(_camera_rig.get("mode")) if _camera_rig.get("mode") != null else 0
			if current_mode == 0:
				_camera_rig.set_mode(1)  # Mode.FOLLOW_AGENT


func _pick_avatar_under_mouse(screen_pos: Vector2) -> Node3D:
	var camera: Camera3D = _resolve_camera()
	if camera == null:
		return null
	var origin := camera.project_ray_origin(screen_pos)
	var direction := camera.project_ray_normal(screen_pos)
	var target := origin + direction * 1000.0
	var space := camera.get_world_3d().direct_space_state
	var query := PhysicsRayQueryParameters3D.create(origin, target, 2, [])
	query.collide_with_bodies = true
	query.collide_with_areas = false
	var hit: Dictionary = space.intersect_ray(query)
	if hit.is_empty():
		return null
	var collider: Node = hit.get("collider")
	if collider == null:
		return null
	# The collider is the SelectionArea StaticBody3D; walk up the tree to
	# the AgentAvatar root which is the first ancestor carrying ``agent_id``.
	var node: Node = collider
	while node != null:
		if node.has_method("get") and node.get("agent_id") != null and str(node.get("agent_id")) != "":
			return node as Node3D
		node = node.get_parent()
	return null


func _extract_agent_id(avatar: Node) -> String:
	var raw: Variant = avatar.get("agent_id")
	if raw == null:
		return ""
	return str(raw)


func _resolve_camera() -> Camera3D:
	if _camera_rig == null:
		return null
	# CameraRig authors a child Camera3D at _ready; prefer that, fall back
	# to the scene-tree default current camera so the manager still works
	# if a different rig is swapped in.
	for child in _camera_rig.get_children():
		if child is Camera3D:
			return child
	return get_viewport().get_camera_3d()
