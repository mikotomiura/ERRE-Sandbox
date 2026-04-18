# FixturePlayer — T16 godot-ws-client (developer-only)
#
# Replays the seven wire-contract specimens in
# ``fixtures/control_envelope/*.json`` against the ``EnvelopeRouter`` at
# ``PLAYBACK_INTERVAL_SEC`` intervals. Used by
# ``scenes/dev/FixtureHarness.tscn`` so the full signal graph can be
# exercised without a running G-GEAR gateway.
#
# Production scripts MUST NOT depend on this file (see ``dev/README.md``).
class_name FixturePlayer
extends Node

## Seconds between consecutive envelope emissions.
const PLAYBACK_INTERVAL_SEC: float = 0.5
## Seconds to wait after the last envelope before quitting.
const POST_PLAYBACK_GRACE_SEC: float = 2.0
## Defensive upper bound on fixture size. Developer-injected paths could point
## to an arbitrary file; dropping anything larger keeps harness runs bounded.
const MAX_FIXTURE_BYTES: int = 1_048_576
## Fixed playlist. Keep in sync with ``fixtures/control_envelope/README.md``.
const DEFAULT_PLAYLIST: PackedStringArray = [
	"handshake.json",
	"agent_update.json",
	"speech.json",
	"move.json",
	"animation.json",
	"world_tick.json",
	"error.json",
]
## Fallback search paths (project-local) if ``--fixture-dir`` is not provided.
const FALLBACK_CANDIDATES: PackedStringArray = [
	"res://../fixtures/control_envelope",
	"res://fixtures/control_envelope",
]

@export var router_path: NodePath
@export var websocket_client_path: NodePath

var _fixture_dir: String = ""
var _playback_index: int = 0
var _timer: Timer


func _ready() -> void:
	var router := _resolve_router()
	if router == null or not router.has_method("on_envelope_received"):
		push_error("[FixturePlayer] EnvelopeRouter not found at %s" % router_path)
		get_tree().quit(1)
		return
	_disable_websocket_client()

	_fixture_dir = _resolve_fixture_dir()
	if _fixture_dir == "":
		push_error(
			"[FixturePlayer] No fixture dir (pass --fixture-dir=<abs>). "
			+ "Fallback candidates not accessible either."
		)
		get_tree().quit(1)
		return
	print("[FixturePlayer] fixture_dir=%s" % _fixture_dir)

	_timer = Timer.new()
	_timer.one_shot = false
	_timer.wait_time = PLAYBACK_INTERVAL_SEC
	_timer.timeout.connect(_advance.bind(router))
	add_child(_timer)
	_timer.start()


# Router is typed as plain ``Node`` to avoid the class_name parse-order issue
# described in ``AgentManager.gd``.
func _resolve_router() -> Node:
	if router_path != NodePath(""):
		var node := get_node_or_null(router_path)
		if node != null:
			return node
	return get_tree().root.find_child("EnvelopeRouter", true, false)


func _disable_websocket_client() -> void:
	# The harness loads MainScene, which includes WebSocketClient; in fixture
	# mode we do not want it chattering at ws://g-gear.local:8000/stream.
	var ws_node: Node = null
	if websocket_client_path != NodePath(""):
		ws_node = get_node_or_null(websocket_client_path)
	if ws_node == null:
		ws_node = get_tree().root.find_child("WebSocketClient", true, false)
	if ws_node != null:
		ws_node.set_process(false)
		print("[FixturePlayer] WebSocketClient disabled for fixture run")


func _resolve_fixture_dir() -> String:
	# 1. --fixture-dir=<abs> (preferred: test runners inject this)
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with("--fixture-dir="):
			var value := arg.substr("--fixture-dir=".length())
			if DirAccess.dir_exists_absolute(value):
				return value
	# 2. res:// fallback (interactive runs from inside the Godot editor)
	for candidate: String in FALLBACK_CANDIDATES:
		var absolute := ProjectSettings.globalize_path(candidate)
		if DirAccess.dir_exists_absolute(absolute):
			return absolute
	return ""


func _advance(router: Node) -> void:
	if _playback_index >= DEFAULT_PLAYLIST.size():
		_timer.stop()
		print("[FixturePlayer] playlist complete, quitting")
		await get_tree().create_timer(POST_PLAYBACK_GRACE_SEC).timeout
		get_tree().quit()
		return

	var filename: String = DEFAULT_PLAYLIST[_playback_index]
	_playback_index += 1
	var path := _fixture_dir.path_join(filename)
	var envelope := _load_envelope(path)
	if envelope.is_empty():
		push_error("[FixturePlayer] failed to load %s" % path)
		return
	print("[FixturePlayer] dispatching %s kind=%s" % [filename, envelope.get("kind", "?")])
	router.on_envelope_received(envelope)


func _load_envelope(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		push_error("[FixturePlayer] FileAccess.open failed: %s" % path)
		return {}
	var size := file.get_length()
	if size > MAX_FIXTURE_BYTES:
		file.close()
		push_error(
			"[FixturePlayer] %s exceeds MAX_FIXTURE_BYTES (%d > %d)"
			% [path, size, MAX_FIXTURE_BYTES]
		)
		return {}
	var raw := file.get_as_text()
	file.close()
	var parsed: Variant = JSON.parse_string(raw)
	if parsed is Dictionary:
		return parsed
	push_error("[FixturePlayer] %s did not parse as a JSON dict" % path)
	return {}
