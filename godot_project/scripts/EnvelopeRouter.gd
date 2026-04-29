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

# M9-A hotfix: spatial trigger kinds for zone_pulse_requested gating.
# Defense-in-depth — cognition cycle already sets zone=null for non-spatial
# kinds, but the renderer guards against malformed / future payloads that
# accidentally carry a zone for a non-spatial kind. Mirrors the same const
# in BoundaryLayer.gd so the whitelist lives in two enforcement points.
const SPATIAL_TRIGGER_KINDS: PackedStringArray = [
	"zone_transition",
	"affordance",
	"proximity",
]

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
			# M9-A hotfix: ``trigger_event`` carries explicit JSON ``null`` for
			# zone/ref_id when the winning kind is non-spatial (temporal /
			# biorhythm / internal / speech / perception / erre_mode_shift).
			# ``Dictionary.get(key, default)`` returns the actual ``null`` —
			# default kicks in only on missing keys — so we route through
			# ``Variant`` and coerce. Empty result + spatial-kind whitelist
			# together gate the pulse signal.
			var trigger: Variant = trace.get("trigger_event")
			if trigger is Dictionary:
				var kind_value: Variant = trigger.get("kind")
				var zone_value: Variant = trigger.get("zone")
				var trigger_kind: String = (
					"" if kind_value == null else str(kind_value)
				)
				var trigger_zone: String = (
					"" if zone_value == null else str(zone_value)
				)
				if (
					SPATIAL_TRIGGER_KINDS.has(trigger_kind)
					and not trigger_zone.is_empty()
				):
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
