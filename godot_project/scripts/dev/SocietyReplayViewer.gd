# SocietyReplayViewer — M4 situated-3D dev viewer (developer-only)
#
# Stands the committed N-body society substrate up as a "moving N-body society"
# for offline developer observation. It is a SEPARATE dev script from
# ``EclReplayPlayer.gd`` (which stays byte-unchanged, judgement 4): that player
# only prints the envelope stream, whereas this viewer resolves per-avatar
# placement from the physics trace (M4 impl-design ADR §3, design-final-ref.md).
#
# Replay role split (§3.3, Codex MEDIUM-2 binding):
#   * motion / position authority = ``ecl_trace.jsonl`` — each avatar (order_slot)
#     is placed at the committed absolute ``(x, y, z)`` + ``yaw`` of its
#     ``(physics_tick_index, order_slot)`` row. The trace value is echoed
#     pass-through, NEVER recomputed (Codex HIGH-3: a Godot runtime float→str is
#     not a cross-machine byte witness; the Python test canonicalises + compares).
#   * speech / animation firing = ``envelope_stream.jsonl`` — the ``move`` kind is
#     NOT used for position (§3.3); only ``speech`` / ``animation`` fire here.
#   * ``order_slot`` is a stable-order component, not a join key (MEDIUM-1): the
#     motion series (physics_tick clock, 20 ticks) and the speech·animation series
#     (agent_tick clock, 4 ticks) are independent clock domains and are NOT joined.
#
# Two modes (§3.4):
#   * headless (CI witness): ``--dump=<abs>`` present → resolve placements +
#     fired envelope kinds and write them to the dump path as JSONL, then quit.
#     Scene instantiation is minimal (transform resolution only, no rendering).
#   * interactive (developer observation): no ``--dump`` → print the resolved
#     timeline and quit (the full-scene wrapper is ``scenes/dev/SocietyReplayScene.tscn``).
#
# It extends ``SceneTree`` so it runs as a standalone headless smoke without a
# scene, e.g.::
#
#   godot --headless --path godot_project \
#     --script res://scripts/dev/SocietyReplayViewer.gd \
#     -- --manifest=<abs>/manifest.json --trace=<abs>/ecl_trace.jsonl \
#        --stream=<abs>/envelope_stream.jsonl --dump=<abs>/placement_dump.jsonl
#
# Production scripts (``WebSocketClient.gd`` / ``EnvelopeRouter.gd`` /
# ``AgentManager.gd`` / ``MainScene.tscn``) MUST NOT depend on this file, and it
# never opens the production WebSocket — the real gateway is never contacted
# (see ``dev/README.md``). It is construction, not measurement: the placement
# dump is a reproducibility echo, never a metric / floor / verdict.
class_name SocietyReplayViewer
extends SceneTree

## Defensive upper bound on any developer-injected input file.
const MAX_INPUT_BYTES: int = 4_194_304
## Envelope kinds this viewer fires (speech / animation only — ``move`` is a
## motive record, not a position authority, §3.3).
const FIRING_KINDS: PackedStringArray = ["speech", "animation"]


func _initialize() -> void:
	var manifest_path := _cmdline_value("--manifest=")
	var trace_path := _cmdline_value("--trace=")
	var stream_path := _cmdline_value("--stream=")
	var dump_path := _cmdline_value("--dump=")

	if manifest_path == "" or trace_path == "" or stream_path == "":
		push_error(
			"[SocietyReplayViewer] pass --manifest=<abs> --trace=<abs> --stream=<abs> "
			+ "(committed m2_society_golden artifacts); add --dump=<abs> for headless dump"
		)
		quit(1)
		return

	var manifest := _load_json_dict(manifest_path)
	if manifest.is_empty():
		push_error("[SocietyReplayViewer] failed to load manifest: %s" % manifest_path)
		quit(1)
		return

	# Motion authority (physics_tick clock domain).
	var placements := _resolve_placements(trace_path)
	if placements.is_empty():
		push_error("[SocietyReplayViewer] empty / unreadable trace: %s" % trace_path)
		quit(1)
		return

	# Speech / animation firing (agent_tick clock domain) — a SEPARATE series,
	# not joined with the placements above (MEDIUM-1).
	var firings := _resolve_firings(stream_path)

	if dump_path != "":
		if not _write_dump(dump_path, placements, firings):
			quit(1)
			return
		print(
			"[SocietyReplayViewer] dumped %d placement + %d envelope row(s) -> %s"
			% [placements.size(), firings.size(), dump_path]
		)
		quit(0)
		return

	_print_interactive(manifest, placements, firings)
	quit(0)


# --------------------------------------------------------------------------- #
# Motion authority — ecl_trace.jsonl → per-(physics_tick_index, order_slot)
# absolute placement, echoed pass-through (never recomputed, HIGH-3).
# --------------------------------------------------------------------------- #
func _resolve_placements(path: String) -> Array:
	var rows := _load_jsonl(path)
	var out: Array = []
	for row: Dictionary in rows:
		# Pass-through echo: read the committed value, do NOT reformat / recompute.
		out.append(
			{
				"kind": "placement",
				"physics_tick_index": int(row.get("physics_tick_index", 0)),
				"order_slot": int(row.get("order_slot", 0)),
				"x": row.get("x", 0.0),
				"y": row.get("y", 0.0),
				"z": row.get("z", 0.0),
				"yaw": row.get("yaw", 0.0),
				"zone": String(row.get("zone", "")),
			}
		)
	out.sort_custom(_placement_before)
	return out


# --------------------------------------------------------------------------- #
# Speech / animation firing — envelope_stream.jsonl, ``move`` excluded (§3.3).
# --------------------------------------------------------------------------- #
func _resolve_firings(path: String) -> Array:
	var rows := _load_jsonl(path)
	var out: Array = []
	for row: Dictionary in rows:
		var envelope: Dictionary = row.get("envelope", {})
		var kind := String(envelope.get("kind", ""))
		if not FIRING_KINDS.has(kind):
			continue
		out.append(
			{
				"kind": "envelope",
				"order_slot": int(row.get("order_slot", 0)),
				"agent_tick": int(row.get("agent_tick", 0)),
				"seq": int(row.get("seq", 0)),
				"envelope_kind": kind,
			}
		)
	out.sort_custom(_firing_before)
	return out


# Placement order (§3.4 dump schema): physics_tick_index asc, then order_slot asc.
func _placement_before(a: Dictionary, b: Dictionary) -> bool:
	var a_tick := int(a.get("physics_tick_index", 0))
	var b_tick := int(b.get("physics_tick_index", 0))
	if a_tick != b_tick:
		return a_tick < b_tick
	return int(a.get("order_slot", 0)) < int(b.get("order_slot", 0))


# Firing order (§3.4 dump schema): order_slot asc, agent_tick asc, seq asc.
func _firing_before(a: Dictionary, b: Dictionary) -> bool:
	var a_slot := int(a.get("order_slot", 0))
	var b_slot := int(b.get("order_slot", 0))
	if a_slot != b_slot:
		return a_slot < b_slot
	var a_tick := int(a.get("agent_tick", 0))
	var b_tick := int(b.get("agent_tick", 0))
	if a_tick != b_tick:
		return a_tick < b_tick
	return int(a.get("seq", 0)) < int(b.get("seq", 0))


# --------------------------------------------------------------------------- #
# Headless dump — placements first, then envelope firings (each JSON per line).
# --------------------------------------------------------------------------- #
func _write_dump(path: String, placements: Array, firings: Array) -> bool:
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		push_error("[SocietyReplayViewer] FileAccess.open (write) failed: %s" % path)
		return false
	for entry: Dictionary in placements:
		file.store_line(JSON.stringify(entry))
	for entry: Dictionary in firings:
		file.store_line(JSON.stringify(entry))
	file.close()
	return true


# Minimal developer-observation replay: print the resolved timeline. The rich
# 3D scene is ``scenes/dev/SocietyReplayScene.tscn`` (opened interactively).
func _print_interactive(manifest: Dictionary, placements: Array, firings: Array) -> void:
	var run: Dictionary = manifest.get("run", {})
	print(
		"[SocietyReplayViewer] run_id=%s agents=%s ticks=%s"
		% [
			run.get("run_id", "?"),
			run.get("agent_ids", []),
			run.get("world_tick_count", "?"),
		]
	)
	for entry: Dictionary in placements:
		print(
			"[SocietyReplayViewer] ptick=%d slot=%d pos=(%s, %s, %s) yaw=%s zone=%s"
			% [
				entry["physics_tick_index"],
				entry["order_slot"],
				entry["x"],
				entry["y"],
				entry["z"],
				entry["yaw"],
				entry["zone"],
			]
		)
	for entry: Dictionary in firings:
		print(
			"[SocietyReplayViewer] slot=%d atick=%d seq=%d fire=%s"
			% [
				entry["order_slot"],
				entry["agent_tick"],
				entry["seq"],
				entry["envelope_kind"],
			]
		)


# --------------------------------------------------------------------------- #
# IO helpers (EclReplayPlayer.gd conventions: bounded read, JSON.parse_string).
# --------------------------------------------------------------------------- #
func _cmdline_value(prefix: String) -> String:
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with(prefix):
			return arg.substr(prefix.length())
	return ""


func _load_jsonl(path: String) -> Array:
	var text := _read_bounded(path)
	if text == "":
		return []
	var rows: Array = []
	for line: String in text.split("\n", false):
		var trimmed := line.strip_edges()
		if trimmed == "":
			continue
		var parsed: Variant = JSON.parse_string(trimmed)
		if parsed is Dictionary:
			rows.append(parsed)
		else:
			push_warning("[SocietyReplayViewer] non-object line skipped")
	return rows


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
		push_error("[SocietyReplayViewer] FileAccess.open failed: %s" % path)
		return ""
	var size := file.get_length()
	if size > MAX_INPUT_BYTES:
		file.close()
		push_error(
			"[SocietyReplayViewer] %s exceeds MAX_INPUT_BYTES (%d > %d)"
			% [path, size, MAX_INPUT_BYTES]
		)
		return ""
	var raw := file.get_as_text()
	file.close()
	return raw
