# DialogBubble — M5 godot-zone-visuals
#
# Attached to the ``DialogBubble`` Label3D under ``AgentAvatar.tscn``. Owns a
# single-channel bubble whose visibility is a Tween on ``modulate.a``: fade-in,
# sustain, fade-out. A new ``show()`` during an active fade kills the current
# Tween and replaces it (design.md §Concurrency semantics) — LLM turn cadence
# (>> 0.3s) means this is rarely triggered but the guard keeps the visual
# state deterministic.
#
# This is a sibling of the existing ``SpeechBubble`` Label3D; both can be
# active simultaneously because they live on separate nodes with a small
# z-offset, avoiding the last-wins collision that would occur if a single
# bubble handled both channels.
class_name DialogBubble
extends Label3D

const FADE_IN_SEC: float = 0.3
const FADE_OUT_SEC: float = 0.3

var _current_tween: Tween = null


func _ready() -> void:
	modulate.a = 0.0
	visible = false


func show_for(utterance: String, duration_s: float) -> void:
	# ``show`` is a Node method; using ``show_for`` avoids the shadow.
	if _current_tween != null and _current_tween.is_running():
		_current_tween.kill()
	text = utterance
	visible = true
	modulate.a = 0.0
	var sustain_s: float = max(duration_s - FADE_IN_SEC - FADE_OUT_SEC, 0.0)
	_current_tween = create_tween()
	_current_tween.tween_property(self, "modulate:a", 1.0, FADE_IN_SEC)
	if sustain_s > 0.0:
		_current_tween.tween_interval(sustain_s)
	_current_tween.tween_property(self, "modulate:a", 0.0, FADE_OUT_SEC)
	_current_tween.tween_callback(_on_fade_complete)
	var parent_id: String = ""
	var parent := get_parent()
	if parent != null and "agent_id" in parent:
		parent_id = str(parent.agent_id)
	print("[DialogBubble] show agent_id=%s len=%d" % [parent_id, utterance.length()])


func hide_now() -> void:
	if _current_tween != null and _current_tween.is_running():
		_current_tween.kill()
	modulate.a = 0.0
	visible = false


func _on_fade_complete() -> void:
	visible = false
