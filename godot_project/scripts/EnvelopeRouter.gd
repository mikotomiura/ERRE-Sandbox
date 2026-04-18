# EnvelopeRouter — T16 godot-ws-client
#
# Receives raw ControlEnvelope Dictionaries (emitted by WebSocketClient.gd or
# FixturePlayer.gd) and re-emits them as one of seven typed signals keyed by
# the envelope's ``kind`` field.
#
# The seven kinds below MUST match ``src/erre_sandbox/schemas.py`` §7 exactly.
# ``tests/test_envelope_kind_sync.py`` parses this file's match block and
# fails the CI build if drift is detected. Keep each match arm on its own
# line as ``"kind_name":`` so the regex extractor finds it cleanly.
class_name EnvelopeRouter
extends Node

signal handshake_received(peer: String, capabilities: Array)
signal agent_updated(agent_id: String, agent_state: Dictionary)
signal speech_delivered(agent_id: String, utterance: String, zone: String)
signal move_issued(agent_id: String, target: Dictionary, speed: float)
signal animation_changed(agent_id: String, animation_name: String, loop: bool)
signal world_ticked(wall_clock: String, tick: int, active_agents: int)
signal error_reported(code: String, detail: String)


func on_envelope_received(envelope: Dictionary) -> void:
	var kind: String = envelope.get("kind", "")
	match kind:
		"handshake":
			handshake_received.emit(
				envelope.get("peer", ""),
				envelope.get("capabilities", []),
			)
		"agent_update":
			var agent_state: Dictionary = envelope.get("agent_state", {})
			agent_updated.emit(agent_state.get("agent_id", ""), agent_state)
		"speech":
			speech_delivered.emit(
				envelope.get("agent_id", ""),
				envelope.get("utterance", ""),
				envelope.get("zone", ""),
			)
		"move":
			move_issued.emit(
				envelope.get("agent_id", ""),
				envelope.get("target", {}),
				float(envelope.get("speed", 0.0)),
			)
		"animation":
			animation_changed.emit(
				envelope.get("agent_id", ""),
				envelope.get("animation_name", ""),
				bool(envelope.get("loop", false)),
			)
		"world_tick":
			world_ticked.emit(
				envelope.get("wall_clock", ""),
				int(envelope.get("tick", 0)),
				int(envelope.get("active_agents", 0)),
			)
		"error":
			error_reported.emit(
				envelope.get("code", ""),
				envelope.get("detail", ""),
			)
		_:
			push_warning("[EnvelopeRouter] Unknown kind: %s" % kind)
