# EclReplayPlayer — ECL v0 handoff replay (developer-only)
#
# Offline-replays a G-GEAR-generated ECL v0 embodiment handoff: reads
# ``manifest.json`` + ``envelope_stream.jsonl`` (design-final.md §論点5), sorts
# the wrapped envelopes by ``(order_slot, agent_tick, seq)`` and dispatches each
# ``ControlEnvelope`` (speech / move / animation) in that deterministic order.
#
# It extends ``SceneTree`` so it runs as a standalone headless smoke without a
# scene, e.g.::
#
#   godot --headless --path godot_project \
#     --script res://scripts/dev/EclReplayPlayer.gd \
#     -- --manifest=<abs>/manifest.json --stream=<abs>/envelope_stream.jsonl
#
# This is the bounded dev extension named in the handoff spec (Codex HIGH-1): the
# production ``FixturePlayer.gd`` only replays the fixed control_envelope
# playlist, so ECL stream replay lives here, in a SEPARATE file. Production
# scripts (``WebSocketClient.gd`` / ``EnvelopeRouter.gd`` / ``AgentManager.gd``)
# MUST NOT depend on this file, and it never opens the production WebSocket — the
# real gateway is never contacted (see ``dev/README.md``). Full-session
# visualisation is Milestone 4 (out of scope).
class_name EclReplayPlayer
extends SceneTree

## Defensive upper bound on stream size (developer-injected paths are arbitrary).
const MAX_STREAM_BYTES: int = 4_194_304
## ControlEnvelope kinds this dev player replays (handoff spec §論点5 item 4).
const REPLAYABLE_KINDS: PackedStringArray = ["speech", "move", "animation"]


func _initialize() -> void:
	var manifest_path := _cmdline_value("--manifest=")
	var stream_path := _cmdline_value("--stream=")
	if manifest_path == "" or stream_path == "":
		push_error(
			"[EclReplayPlayer] pass --manifest=<abs> and --stream=<abs> "
			+ "(handoff artifacts from scripts/ecl_v0_golden.py --bake)"
		)
		quit(1)
		return

	var manifest := _load_json_dict(manifest_path)
	if manifest.is_empty():
		push_error("[EclReplayPlayer] failed to load manifest: %s" % manifest_path)
		quit(1)
		return
	print(
		"[EclReplayPlayer] manifest_version=%s schema_version=%s run_id=%s"
		% [
			manifest.get("manifest_version", "?"),
			manifest.get("schema_version", "?"),
			manifest.get("run", {}).get("run_id", "?"),
		]
	)

	var entries := _load_stream(stream_path)
	if entries.is_empty():
		push_error("[EclReplayPlayer] empty / unreadable stream: %s" % stream_path)
		quit(1)
		return

	# Deterministic replay order (design §論点5): (order_slot, agent_tick, seq).
	entries.sort_custom(_order_before)

	var replayed := 0
	for entry: Dictionary in entries:
		var envelope: Dictionary = entry.get("envelope", {})
		var kind := String(envelope.get("kind", ""))
		if not REPLAYABLE_KINDS.has(kind):
			push_warning("[EclReplayPlayer] skipping non-replayable kind: %s" % kind)
			continue
		_replay_envelope(entry, envelope, kind)
		replayed += 1

	print("[EclReplayPlayer] replayed %d envelopes, quitting" % replayed)
	quit(0)


# Kind-based branch (schemas.py §7 / godot-gdscript Skill ルール 3). Dev smoke:
# each kind is logged in order; no production node graph is touched.
func _replay_envelope(entry: Dictionary, envelope: Dictionary, kind: String) -> void:
	var agent_id := String(envelope.get("agent_id", ""))
	var order_slot := int(entry.get("order_slot", 0))
	var agent_tick := int(entry.get("agent_tick", 0))
	match kind:
		"speech":
			print(
				"[EclReplayPlayer] slot=%d tick=%d speech %s: %s"
				% [order_slot, agent_tick, agent_id, envelope.get("utterance", "")]
			)
		"move":
			var target: Dictionary = envelope.get("target", {})
			print(
				"[EclReplayPlayer] slot=%d tick=%d move %s -> (%s, %s, %s) zone=%s"
				% [
					order_slot,
					agent_tick,
					agent_id,
					target.get("x", 0.0),
					target.get("y", 0.0),
					target.get("z", 0.0),
					target.get("zone", "?"),
				]
			)
		"animation":
			print(
				"[EclReplayPlayer] slot=%d tick=%d animation %s: %s"
				% [order_slot, agent_tick, agent_id, envelope.get("animation_name", "")]
			)


# Stable strict-weak ordering by (order_slot, agent_tick, seq) for sort_custom.
func _order_before(a: Dictionary, b: Dictionary) -> bool:
	var a_slot := int(a.get("order_slot", 0))
	var b_slot := int(b.get("order_slot", 0))
	if a_slot != b_slot:
		return a_slot < b_slot
	var a_tick := int(a.get("agent_tick", 0))
	var b_tick := int(b.get("agent_tick", 0))
	if a_tick != b_tick:
		return a_tick < b_tick
	return int(a.get("seq", 0)) < int(b.get("seq", 0))


func _cmdline_value(prefix: String) -> String:
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with(prefix):
			return arg.substr(prefix.length())
	return ""


func _load_stream(path: String) -> Array:
	var text := _read_bounded(path)
	if text == "":
		return []
	var entries: Array = []
	for line: String in text.split("\n", false):
		var trimmed := line.strip_edges()
		if trimmed == "":
			continue
		var parsed: Variant = JSON.parse_string(trimmed)
		if parsed is Dictionary:
			entries.append(parsed)
		else:
			push_warning("[EclReplayPlayer] non-object stream line skipped")
	return entries


func _load_json_dict(path: String) -> Dictionary:
	var text := _read_bounded(path)
	if text == "":
		return {}
	var parsed: Variant = JSON.parse_string(text)
	if parsed is Dictionary:
		return parsed
	return {}


func _read_bounded(path: String) -> String:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		push_error("[EclReplayPlayer] FileAccess.open failed: %s" % path)
		return ""
	var size := file.get_length()
	if size > MAX_STREAM_BYTES:
		file.close()
		push_error(
			"[EclReplayPlayer] %s exceeds MAX_STREAM_BYTES (%d > %d)"
			% [path, size, MAX_STREAM_BYTES]
		)
		return ""
	var raw := file.get_as_text()
	file.close()
	return raw
