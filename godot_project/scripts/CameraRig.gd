# CameraRig — M6-B-1 interactive camera for the xAI observatory.
#
# Owns a single Camera3D child positioned relative to a pivot. Three modes
# (OVERVIEW / FOLLOW_AGENT / MIND_PEEK) share the same orbital transform but
# differ in how the pivot is chosen and which input is consumed:
#
#   * OVERVIEW     — pivot is stationary in world space, WASD pans it.
#                    Best for "researcher looking at the whole world".
#   * FOLLOW_AGENT — pivot tracks ``target_agent.global_position``; WASD
#                    is ignored. Best for "follow Kant as he walks".
#   * MIND_PEEK    — same tracking as FOLLOW_AGENT plus a closer default
#                    distance; the ReasoningPanel owns the side UI.
#
# Mouse drag (right or middle button) orbits; the wheel zooms. Hotkeys 1/2/3
# switch modes; the matching input_map actions are declared in
# project.godot under ``[input]``. The rig boots in OVERVIEW so a first-run
# user with no selection still sees a stable framing.
#
# Design note: the class avoids ``class_name`` on purpose so the initial
# headless boot before ``.godot/`` is populated does not fail resolution
# (T16 judgement 4 — same pattern used by EnvelopeRouter).
extends Node3D

enum Mode { OVERVIEW, FOLLOW_AGENT, MIND_PEEK, TOP_DOWN }

@export var mode: Mode = Mode.OVERVIEW
@export var orbit_speed: float = 0.006
@export var zoom_speed: float = 2.5
@export var pan_speed: float = 12.0
@export var min_distance: float = 3.0
@export var max_distance: float = 100.0
@export var default_distance_overview: float = 28.0
@export var default_distance_follow: float = 14.0
@export var default_distance_mind_peek: float = 6.0
@export var default_distance_top_down: float = 65.0

# M7 α-cam2 + Slice β: discrete zoom presets hot-keyed to `-` and `=` so a
# researcher can jump the camera distance without spinning the mouse wheel
# for several seconds. Values span the sweep from mind-peek close-up to
# the new 100 m world overview (the ``100`` step was added with
# ``WORLD_SIZE_M`` so the researcher can frame the whole terrain in one
# keystroke).
@export var zoom_steps: Array[float] = [3.0, 8.0, 15.0, 30.0, 60.0, 100.0]

signal mode_changed(new_mode: int)

var _camera: Camera3D
var _target_agent: Node3D = null
var _yaw: float = 0.0
var _pitch: float = -0.95
var _distance: float = 28.0
var _pivot: Vector3 = Vector3.ZERO
var _dragging: bool = false


func _ready() -> void:
	_camera = _ensure_camera()
	_camera.current = true
	_distance = default_distance_overview
	_apply_transform()


func _ensure_camera() -> Camera3D:
	# If a Camera3D was authored as a child (scene-level), reuse it; otherwise
	# create one at runtime so the rig works when dropped into a scene that
	# did not pre-author the child.
	for child in get_children():
		if child is Camera3D:
			return child
	var cam := Camera3D.new()
	cam.name = "Camera3D"
	add_child(cam)
	return cam


func _unhandled_input(event: InputEvent) -> void:
	# Mode switching — single-shot actions, so handle on just_pressed.
	if event.is_action_pressed("cam_overview"):
		set_mode(Mode.OVERVIEW)
		return
	if event.is_action_pressed("cam_follow"):
		set_mode(Mode.FOLLOW_AGENT)
		return
	if event.is_action_pressed("cam_mind_peek"):
		set_mode(Mode.MIND_PEEK)
		return
	# M7 α-cam1: hotkey 0 → true overhead preset. Pitch stops one hair shy of
	# straight down (-1.5 rad ≈ -86°) to stay inside the same gimbal-safe
	# clamp the mouse orbit uses; a full -π/2 would align the camera forward
	# axis with Vector3.UP and wreck the look_at basis.
	if event.is_action_pressed("cam_top_down"):
		set_mode(Mode.TOP_DOWN)
		return
	# M7 α-cam2: discrete zoom steps — faster for "zoom all the way in/out"
	# than spinning the wheel, and gives researchers a reproducible distance
	# for live-recording reruns.
	if event.is_action_pressed("cam_zoom_in"):
		_zoom_step(-1)
		return
	if event.is_action_pressed("cam_zoom_out"):
		_zoom_step(1)
		return
	# Drag gate — hold right-or-middle mouse button to orbit.
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_RIGHT or mb.button_index == MOUSE_BUTTON_MIDDLE:
			_dragging = mb.pressed
		elif mb.pressed:
			if mb.button_index == MOUSE_BUTTON_WHEEL_UP:
				_zoom(-zoom_speed)
			elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
				_zoom(zoom_speed)
	# Orbit on mouse motion while dragging.
	elif event is InputEventMouseMotion and _dragging:
		var mm := event as InputEventMouseMotion
		_yaw -= mm.relative.x * orbit_speed
		_pitch -= mm.relative.y * orbit_speed
		_pitch = clamp(_pitch, -1.5, -0.05)
		_apply_transform()


func _process(delta: float) -> void:
	# WASD panning is OVERVIEW-only — in agent-follow modes the pivot is
	# pinned to the target so WASD would fight the follow each frame.
	if mode == Mode.OVERVIEW:
		var pan := Vector3.ZERO
		if Input.is_action_pressed("cam_pan_forward"):
			pan.z -= 1.0
		if Input.is_action_pressed("cam_pan_back"):
			pan.z += 1.0
		if Input.is_action_pressed("cam_pan_left"):
			pan.x -= 1.0
		if Input.is_action_pressed("cam_pan_right"):
			pan.x += 1.0
		if pan != Vector3.ZERO:
			# Rotate the pan vector by yaw so "forward" is screen-relative.
			var yaw_basis := Basis(Vector3.UP, _yaw)
			_pivot += yaw_basis * pan.normalized() * pan_speed * delta
			_apply_transform()
	elif _target_agent != null and is_instance_valid(_target_agent):
		# Follow modes: pull the pivot toward the agent each frame.
		var target_pos := _target_agent.global_position
		if _pivot.distance_squared_to(target_pos) > 0.0001:
			_pivot = _pivot.lerp(target_pos, clamp(delta * 6.0, 0.0, 1.0))
			_apply_transform()


func _zoom(delta: float) -> void:
	_distance = clamp(_distance + delta, min_distance, max_distance)
	_apply_transform()


func _zoom_step(direction: int) -> void:
	# direction: -1 = step closer, +1 = step farther. Snap the current
	# _distance to the nearest declared step first, then move by ``direction``
	# one notch, so a mouse-wheel sweep that landed between two presets still
	# has a defined "next step" instead of no-oping.
	if zoom_steps.is_empty():
		return
	var current_step: int = 0
	var best_delta: float = INF
	for i in zoom_steps.size():
		var step_value: float = zoom_steps[i]
		var dd: float = abs(_distance - step_value)
		if dd < best_delta:
			best_delta = dd
			current_step = i
	var next_step: int = clamp(current_step + direction, 0, zoom_steps.size() - 1)
	_distance = zoom_steps[next_step]
	_apply_transform()


func _apply_transform() -> void:
	# Spherical-to-cartesian for the camera offset around the pivot.
	var offset := Vector3(
		cos(_pitch) * sin(_yaw),
		sin(-_pitch),
		cos(_pitch) * cos(_yaw),
	) * _distance
	global_position = _pivot
	if _camera != null:
		_camera.position = offset
		_camera.look_at(_pivot, Vector3.UP)


# ---- Public API consumed by SelectionManager / observatory UI ----


func set_mode(new_mode: Mode) -> void:
	if new_mode == mode:
		return
	mode = new_mode
	match mode:
		Mode.OVERVIEW:
			_distance = default_distance_overview
		Mode.FOLLOW_AGENT:
			_distance = default_distance_follow
		Mode.MIND_PEEK:
			_distance = default_distance_mind_peek
		Mode.TOP_DOWN:
			# Near-vertical pitch + high altitude = "look straight down at
			# the whole stage". Pivot is left untouched so toggling TOP_DOWN
			# from OVERVIEW keeps the researcher centred where they were.
			_pitch = -1.5
			_distance = default_distance_top_down
	_apply_transform()
	mode_changed.emit(int(mode))


func set_target_agent(agent_node: Node3D) -> void:
	# Follow a specific avatar. Accepts ``null`` to release the follow lock
	# without changing modes (the pivot freezes at its last position).
	_target_agent = agent_node
	if agent_node != null and is_instance_valid(agent_node):
		_pivot = agent_node.global_position
		_apply_transform()


func focus_on_world_origin() -> void:
	# Convenience for "reset to a known safe view" — researchers use this
	# after zooming into an empty zone and losing their bearings.
	_pivot = Vector3.ZERO
	_yaw = 0.0
	_pitch = -0.95
	_distance = default_distance_overview
	_apply_transform()
