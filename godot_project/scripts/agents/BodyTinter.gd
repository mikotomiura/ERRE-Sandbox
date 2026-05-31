# BodyTinter — M5 godot-zone-visuals (humanoid-avatar: Node3D group)
#
# Attached to the ``Body`` Node3D under ``AgentAvatar.tscn``. The body is a
# group of MeshInstance3D children (Head / Torso / ArmL / ArmR / LegL / LegR)
# that all reference the same ``StandardMaterial3D`` sub-resource via
# ``material_override``. Because the material is ``resource_local_to_scene =
# true``, each packed-scene instance gets its own copy, so tweening the shared
# material's ``albedo_color`` tints every limb of one avatar at once without
# bleeding across other avatars.
#
# The previous (pre-humanoid) revision extended ``MeshInstance3D`` and tinted
# ``self.material_override`` directly. Swapping to Node3D lets Body act as a
# container while keeping the ``apply_mode`` contract that AgentController
# depends on.
class_name BodyTinter
extends Node3D

## Colour interpolation duration. Matches DialogBubble fade for visual rhythm.
const TINT_TWEEN_DURATION_SEC: float = 0.3
## Preload the theme dictionary rather than referencing it by ``class_name``.
## The parse-order issue described in AgentManager.gd judgement 4 still bites
## static-func call sites during the very first headless boot, so any
## cross-script symbol lookup must go through ``preload``.
const ERREModeTheme = preload("res://scripts/theme/ERREModeTheme.gd")

var _current_mode: String = ""
var _current_tween: Tween = null
var _shared_material: StandardMaterial3D = null


func _ready() -> void:
	# Resolve the scene-local shared material from any mesh child. All limbs
	# reference the same SubResource, so inspecting the first is sufficient.
	for child in get_children():
		if child is MeshInstance3D:
			var mat := (child as MeshInstance3D).material_override as StandardMaterial3D
			if mat != null:
				_shared_material = mat
				return
	push_warning(
		"[BodyTinter] no MeshInstance3D child with StandardMaterial3D override; tint disabled",
	)


func apply_mode(mode: String) -> void:
	if mode == "":
		return
	if mode == _current_mode:
		return
	if _shared_material == null:
		push_warning("[BodyTinter] shared material not resolved; skipping mode=%s" % mode)
		return
	var target_color: Color = ERREModeTheme.color_for(mode)
	if _current_tween != null and _current_tween.is_running():
		_current_tween.kill()
	_current_tween = create_tween()
	_current_tween.tween_property(
		_shared_material,
		"albedo_color",
		target_color,
		TINT_TWEEN_DURATION_SEC,
	)
	_current_mode = mode
	print(
		"[BodyTinter] mode=%s color=(%.2f, %.2f, %.2f)"
		% [mode, target_color.r, target_color.g, target_color.b]
	)
