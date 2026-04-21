# BodyTinter — M5 godot-zone-visuals
#
# Attached to the ``Body`` MeshInstance3D under ``AgentAvatar.tscn``. Owns the
# avatar's ERRE-mode colour by animating ``material_override.albedo_color``
# with a short Tween so FSM oscillations around the 0.3s boundary do not read
# as a strobe (design.md §Tint transition). The material itself is made
# scene-local via ``resource_local_to_scene = true`` in the packed scene, so
# this script does not need to ``.duplicate()`` at runtime.
class_name BodyTinter
extends MeshInstance3D

## Colour interpolation duration. Matches DialogBubble fade for visual rhythm.
const TINT_TWEEN_DURATION_SEC: float = 0.3
## Preload the theme dictionary rather than referencing it by ``class_name``.
## The parse-order issue described in AgentManager.gd judgement 4 still bites
## static-func call sites during the very first headless boot, so any
## cross-script symbol lookup must go through ``preload``.
const ERREModeTheme = preload("res://scripts/theme/ERREModeTheme.gd")

var _current_mode: String = ""
var _current_tween: Tween = null


func apply_mode(mode: String) -> void:
	if mode == "":
		return
	if mode == _current_mode:
		return
	var target_color: Color = ERREModeTheme.color_for(mode)
	var material: StandardMaterial3D = material_override as StandardMaterial3D
	if material == null:
		push_warning("[BodyTinter] material_override is not StandardMaterial3D; skipping mode=%s" % mode)
		return
	if _current_tween != null and _current_tween.is_running():
		_current_tween.kill()
	_current_tween = create_tween()
	_current_tween.tween_property(
		material,
		"albedo_color",
		target_color,
		TINT_TWEEN_DURATION_SEC,
	)
	_current_mode = mode
	print(
		"[BodyTinter] mode=%s color=(%.2f, %.2f, %.2f)"
		% [mode, target_color.r, target_color.g, target_color.b]
	)
