# OrbitCameraController — developer-only free-look camera for the M4 society
# replay viewer (SocietyReplayViewer.gd interactive mode). Drag with the left
# mouse button to orbit, scroll to zoom, WASD to pan the focus point. It is a
# dev observation control only — it touches no production scene, no WebSocket,
# and carries no measurement surface (construction, not measurement).
extends Camera3D

var focus: Vector3 = Vector3(0.0, 1.0, 0.0)
var distance: float = 16.0
var yaw: float = 0.6
var pitch: float = 0.5

var _dragging: bool = false


func _ready() -> void:
	_apply()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_LEFT:
			_dragging = mb.pressed
		elif mb.button_index == MOUSE_BUTTON_WHEEL_UP and mb.pressed:
			distance = maxf(3.0, distance - 1.5)
			_apply()
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN and mb.pressed:
			distance = minf(160.0, distance + 1.5)
			_apply()
	elif event is InputEventMouseMotion and _dragging:
		var mm := event as InputEventMouseMotion
		yaw -= mm.relative.x * 0.01
		pitch = clampf(pitch - mm.relative.y * 0.01, -1.4, 1.4)
		_apply()


func _process(delta: float) -> void:
	var move := Vector3.ZERO
	if Input.is_key_pressed(KEY_W):
		move.z -= 1.0
	if Input.is_key_pressed(KEY_S):
		move.z += 1.0
	if Input.is_key_pressed(KEY_A):
		move.x -= 1.0
	if Input.is_key_pressed(KEY_D):
		move.x += 1.0
	if move != Vector3.ZERO:
		focus += Basis(Vector3.UP, yaw) * move * delta * distance * 0.6
		_apply()


func _apply() -> void:
	var offset := Vector3(
		sin(yaw) * cos(pitch),
		sin(pitch),
		cos(yaw) * cos(pitch),
	)
	position = focus + offset * distance
	look_at(focus, Vector3.UP)
