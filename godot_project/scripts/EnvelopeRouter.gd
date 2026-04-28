# EnvelopeRouter — T16 godot-ws-client (M4: dialog variants added)
#
# Receives raw ControlEnvelope Dictionaries (emitted by WebSocketClient.gd or
# FixturePlayer.gd) and re-emits them as typed signals keyed by the envelope's
# ``kind`` field.
#
# The kinds below MUST match ``src/erre_sandbox/schemas.py`` §7 exactly.
# ``tests/test_envelope_kind_sync.py`` parses this file's match block and
# fails the CI build if drift is detected. Keep each match arm on its own
# line as ``"kind_name":`` so the regex extractor finds it cleanly.
#
# M4 foundation adds ``dialog_initiate`` / ``dialog_turn`` / ``dialog_close``.
# Dispatch is implemented here but the concrete 3-avatar routing / animation
# hook-up is deferred to ``m4-multi-agent-orchestrator`` (consumer side).
class_name EnvelopeRouter
extends Node

signal handshake_received(peer: String, capabilities: Array)
signal agent_updated(agent_id: String, agent_state: Dictionary)
signal speech_delivered(agent_id: String, utterance: String, zone: String)
signal move_issued(agent_id: String, target: Dictionary, speed: float)
signal animation_changed(agent_id: String, animation_name: String, loop: bool)
signal world_ticked(wall_clock: String, tick: int, active_agents: int)
signal error_reported(code: String, detail: String)
signal dialog_initiate_received(initiator_agent_id: String, target_agent_id: String, zone: String)
signal dialog_turn_received(dialog_id: String, speaker_id: String, addressee_id: String, utterance: String)
signal dialog_close_received(dialog_id: String, reason: String)
signal reasoning_trace_received(agent_id: String, tick: int, trace: Dictionary)
signal reflection_event_received(agent_id: String, tick: int, summary_text: String, event: Dictionary)
signal world_layout_received(zones: Array, props: Array)
## M9-A event-boundary-observability. Emitted **only** for spatial trigger
## kinds (zone_transition / affordance / proximity) when ReasoningTrace
## carries a ``trigger_event`` with a non-empty ``zone``. The
## ``BoundaryLayer`` consumes this to pulse the originating zone for the
## currently-focused agent (filter logic lives in the consumer).
signal zone_pulse_requested(agent_id: String, kind: String, zone: String, tick: int)


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
		"dialog_initiate":
			dialog_initiate_received.emit(
				envelope.get("initiator_agent_id", ""),
				envelope.get("target_agent_id", ""),
				envelope.get("zone", ""),
			)
		"dialog_turn":
			dialog_turn_received.emit(
				envelope.get("dialog_id", ""),
				envelope.get("speaker_id", ""),
				envelope.get("addressee_id", ""),
				envelope.get("utterance", ""),
			)
		"dialog_close":
			dialog_close_received.emit(
				envelope.get("dialog_id", ""),
				envelope.get("reason", ""),
			)
		"reasoning_trace":
			var trace: Dictionary = envelope.get("trace", {})
			var rt_tick: int = int(envelope.get("tick", 0))
			var rt_agent: String = trace.get("agent_id", "")
			reasoning_trace_received.emit(rt_agent, rt_tick, trace)
			# M9-A: spatial-kind triggers also emit a zone pulse request.
			# Non-spatial kinds (temporal/biorhythm/internal/speech/perception/
			# erre_mode_shift) leave ``zone`` null per cognition cycle, so the
			# null guard below short-circuits without a kind whitelist here —
			# BoundaryLayer additionally filters by spatial-kind set + focus.
			var trigger: Variant = trace.get("trigger_event")
			if trigger is Dictionary:
				var trigger_zone: String = trigger.get("zone", "")
				var trigger_kind: String = trigger.get("kind", "")
				if not trigger_zone.is_empty() and not trigger_kind.is_empty():
					zone_pulse_requested.emit(
						rt_agent, trigger_kind, trigger_zone, rt_tick,
					)
		"reflection_event":
			var event: Dictionary = envelope.get("event", {})
			reflection_event_received.emit(
				event.get("agent_id", ""),
				int(envelope.get("tick", 0)),
				event.get("summary_text", ""),
				event,
			)
		"world_layout":
			world_layout_received.emit(
				envelope.get("zones", []),
				envelope.get("props", []),
			)
		_:
			push_warning("[EnvelopeRouter] Unknown kind: %s" % kind)
