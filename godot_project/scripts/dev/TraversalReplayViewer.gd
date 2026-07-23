# TraversalReplayViewer — M13 traversal rendering dev viewer (developer-only)
#
# Plays back the committed aha-traversal golden as a single agent walking the
# pre-registered 5-leg itinerary (peripatos -> agora -> garden -> chashitsu ->
# study -> peripatos) across the 5-zone world.
#
# HONEST FRAMING (FROZEN ADR .steering/20260723-m13-godot-traversal-rendering/
# design-final.md §0, binding): what this shows is a SCRIPTED GOLDEN TRAVERSAL
# REPLAY — a recorded walk being played back. It is NOT emergence, NOT an "aha",
# NOT an effect, and nothing here is measured. The golden it replays was produced
# by a scripted traversal harness following a pre-registered itinerary, and this
# viewer only renders those recorded coordinates.
#
# Separate dev script from SocietyReplayViewer.gd (ADR §2 DA-2): this task has a
# different identity, dump schema, input contract and route witness, so the M4
# society viewer stays byte-unchanged rather than being taught a second mode.
# Stage/motion mechanics are a scoped copy of it (Codex LOW-1); a shared
# abstraction is deferred until a third viewer exists.
#
# Input contract (ADR §3): NOT the raw 5.1 MB 30 Hz ecl_trace.jsonl, but the
# keyframe stream scripts/aha_traversal_render_derive.py decimates out of it
# under the pinned sampling rules. Each keyframe's pose is an echo of a raw trace
# row (never recomputed, Codex HIGH-3 — a Godot runtime float->str is not a
# cross-machine byte witness; the Python test canonicalises and compares), and
# the viewer lerp-interpolates between keyframes for display only.
#
# Two modes:
#   * headless (CI witness): --dump=<abs> present -> echo the keyframe series to
#     the dump path as JSONL and quit. No scene is instantiated.
#   * interactive (developer observation): no --dump -> instantiate
#     scenes/dev/TraversalReplayScene.tscn and drive the single avatar along the
#     keyframe series (looping). Falls back to printing the resolved timeline
#     when no rendering server is available.
#
# Boot path (headless dump)::
#
#   godot --headless --path godot_project \
#     --script res://scripts/dev/TraversalReplayViewer.gd \
#     -- --keyframes=<abs>/render_keyframes.jsonl --dump=<abs>/keyframe_dump.jsonl
#
# Production scripts (WebSocketClient.gd / EnvelopeRouter.gd / AgentManager.gd /
# MainScene.tscn) MUST NOT depend on this file. It is a pure file replay: no
# WebSocket is opened, the gateway is never contacted, no LLM is called. It is
# construction, not measurement — the keyframe dump is a reproducibility echo.
class_name TraversalReplayViewer
extends SceneTree

## Defensive upper bound on any developer-injected input file. Independent of
## SocietyReplayViewer's own bound (that file is untouched by this task); the
## derived keyframe stream is ~58 KB, two orders of magnitude under this.
const MAX_INPUT_BYTES: int = 4_194_304
## Interactive playback rate: committed physics ticks advanced per real second.
## The golden spans 10000 ticks of a 30 Hz record, so this replays the whole
## itinerary in well under a minute. Dev-only observation cadence, never a witness.
const PLAYBACK_TICKS_PER_SEC: float = 240.0
## The single agent this golden records (one order_slot).
const AVATAR_NODE_NAME: String = "Avatar0"
## Shown in the 3D view so the replay can never be read as emergence (ADR §0).
const HONEST_TITLE: String = "scripted golden traversal replay (recorded walk, replayed)"

# --- interactive playback state (only used in the no-``--dump`` visual mode) --- #
var _interactive_playing: bool = false
## Ascending keyframe series: [{"physics_tick_index": int, "origin": Vector3,
## "yaw": float, "zone": String}] — committed pose echoes, never recomputed.
var _track: Array = []
var _avatar: Node3D = null
var _zone_label: Label3D = null
var _first_tick: int = 0
var _last_tick: int = 0
var _play_clock: float = 0.0
var _last_usec: int = 0


func _initialize() -> void:
	var keyframes_path := _cmdline_value("--keyframes=")
	var dump_path := _cmdline_value("--dump=")

	if keyframes_path == "":
		push_error(
			"[TraversalReplayViewer] pass --keyframes=<abs> (derive it with "
			+ "scripts/aha_traversal_render_derive.py --emit); add --dump=<abs> "
			+ "for the headless dump"
		)
		quit(1)
		return

	var keyframes := _resolve_keyframes(keyframes_path)
	if keyframes.is_empty():
		push_error("[TraversalReplayViewer] empty / unreadable keyframes: %s" % keyframes_path)
		quit(1)
		return

	if dump_path != "":
		if not _write_dump(dump_path, keyframes):
			quit(1)
			return
		print(
			"[TraversalReplayViewer] dumped %d keyframe(s) -> %s"
			% [keyframes.size(), dump_path]
		)
		quit(0)
		return

	if _setup_interactive_scene(keyframes):
		return  # keep the main loop running; process_frame drives the playback
	_print_interactive(keyframes)
	quit(0)


# --------------------------------------------------------------------------- #
# Keyframe input — echoed pass-through, never recomputed (Codex HIGH-3).
# --------------------------------------------------------------------------- #
func _resolve_keyframes(path: String) -> Array:
	var rows := _load_jsonl(path)
	var out: Array = []
	for row: Dictionary in rows:
		# Pass-through echo: read the derived value, do NOT reformat / recompute.
		out.append(
			{
				"kind": "keyframe",
				"physics_tick_index": int(row.get("physics_tick_index", 0)),
				"agent_tick": int(row.get("agent_tick", 0)),
				"order_slot": int(row.get("order_slot", 0)),
				"x": row.get("x", 0.0),
				"y": row.get("y", 0.0),
				"z": row.get("z", 0.0),
				"yaw": row.get("yaw", 0.0),
				"zone": String(row.get("zone", "")),
			}
		)
	out.sort_custom(_keyframe_before)
	return out


# Dump order: physics_tick_index ascending (a single agent, one row per tick).
func _keyframe_before(a: Dictionary, b: Dictionary) -> bool:
	return int(a.get("physics_tick_index", 0)) < int(b.get("physics_tick_index", 0))


# --------------------------------------------------------------------------- #
# Headless dump — one JSON object per line, ascending physics tick.
# --------------------------------------------------------------------------- #
func _write_dump(path: String, keyframes: Array) -> bool:
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		push_error("[TraversalReplayViewer] FileAccess.open (write) failed: %s" % path)
		return false
	for entry: Dictionary in keyframes:
		file.store_line(JSON.stringify(entry))
	file.close()
	return true


# Minimal developer-observation replay: print the resolved timeline. The rich
# 3D scene is scenes/dev/TraversalReplayScene.tscn (opened interactively).
func _print_interactive(keyframes: Array) -> void:
	print("[TraversalReplayViewer] %s" % HONEST_TITLE)
	for entry: Dictionary in keyframes:
		print(
			"[TraversalReplayViewer] ptick=%d atick=%d pos=(%s, %s, %s) yaw=%s zone=%s"
			% [
				entry["physics_tick_index"],
				entry["agent_tick"],
				entry["x"],
				entry["y"],
				entry["z"],
				entry["yaw"],
				entry["zone"],
			]
		)


# --------------------------------------------------------------------------- #
# Interactive playback: instantiate the traversal scene and walk the avatar
# along the committed keyframe series (motion authority = the echoed poses).
# --------------------------------------------------------------------------- #
func _setup_interactive_scene(keyframes: Array) -> bool:
	var packed := load("res://scenes/dev/TraversalReplayScene.tscn") as PackedScene
	if packed == null:
		return false
	var scene := packed.instantiate()
	if scene == null:
		return false
	root.add_child(scene)

	# Dev-only visual fidelity (never a witness — the machine byte comparison is
	# the headless dump path, which does NOT instantiate this scene).
	_add_sky_and_sun(scene)
	_wire_zone_geometry(scene)
	_frame_camera(scene)
	_add_title_panel(scene)

	for entry: Dictionary in keyframes:
		_track.append(
			{
				"physics_tick_index": int(entry["physics_tick_index"]),
				"origin": Vector3(float(entry["x"]), float(entry["y"]), float(entry["z"])),
				"yaw": float(entry["yaw"]),
				"zone": String(entry["zone"]),
			}
		)
	_first_tick = int(_track[0]["physics_tick_index"])
	_last_tick = int(_track[_track.size() - 1]["physics_tick_index"])

	_avatar = scene.get_node_or_null(AVATAR_NODE_NAME) as Node3D
	if _avatar == null:
		return false
	_tint_avatar(_avatar)
	_zone_label = _add_avatar_label(_avatar)
	_add_route_decals(scene)

	_interactive_playing = true
	_last_usec = Time.get_ticks_usec()
	process_frame.connect(_on_playback_frame)
	print(
		"[TraversalReplayViewer] interactive playback: %d keyframes over %d physics ticks (loop) — %s"
		% [_track.size(), _last_tick - _first_tick + 1, HONEST_TITLE]
	)
	return true


# Per-frame playback on the physics clock, looping over the committed span.
# Position/heading are interpolated between the two bracketing keyframes — an
# on-screen convenience only; the byte witness is the un-interpolated echo.
func _on_playback_frame() -> void:
	if not _interactive_playing:
		return
	var now := Time.get_ticks_usec()
	var delta := float(now - _last_usec) / 1_000_000.0
	_last_usec = now
	var span := float(_last_tick - _first_tick)
	if span <= 0.0:
		return
	_play_clock += delta * PLAYBACK_TICKS_PER_SEC
	while _play_clock > span:
		_play_clock -= span

	var clock := float(_first_tick) + _play_clock
	var hi := 1
	while hi < _track.size() - 1 and float(_track[hi]["physics_tick_index"]) < clock:
		hi += 1
	var a: Dictionary = _track[hi - 1]
	var b: Dictionary = _track[hi]
	var a_tick := float(a["physics_tick_index"])
	var b_tick := float(b["physics_tick_index"])
	var frac := 0.0 if b_tick <= a_tick else clampf((clock - a_tick) / (b_tick - a_tick), 0.0, 1.0)

	_avatar.position = (a["origin"] as Vector3).lerp(b["origin"] as Vector3, frac)
	_avatar.rotation.y = lerp_angle(float(a["yaw"]), float(b["yaw"]), frac)
	if _zone_label != null:
		_zone_label.text = String(a["zone"])


# --------------------------------------------------------------------------- #
# Dev-only visual fidelity helpers (interactive mode only; never touched by the
# headless dump witness path). Committed assets only, no measurement surface.
# --------------------------------------------------------------------------- #
func _avatar_colour() -> Color:
	return Color(1.0, 0.72, 0.32)


func _find_mesh_instances(n: Node) -> Array:
	var out: Array = []
	if n is MeshInstance3D:
		out.append(n)
	for c: Node in n.get_children():
		out.append_array(_find_mesh_instances(c))
	return out


func _tint_avatar(node: Node3D) -> void:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = _avatar_colour()
	mat.roughness = 0.55
	for mesh: MeshInstance3D in _find_mesh_instances(node):
		mesh.material_override = mat


# An always-on billboard above the avatar naming the zone it is currently in
# (the committed label echoed for display; the route check recomputes the zone
# from the position in Python and never reads this string).
func _add_avatar_label(node: Node3D) -> Label3D:
	var label := Label3D.new()
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	label.fixed_size = true
	label.position = Vector3(0.0, 2.8, 0.0)
	label.pixel_size = 0.0009
	label.font_size = 38
	label.outline_size = 11
	label.outline_modulate = Color(0, 0, 0, 0.9)
	label.modulate = _avatar_colour()
	label.text = ""
	node.add_child(label)
	return label


# Lay a soft decal at each keyframe position so the whole recorded route is
# drawn on the ground — the itinerary becomes legible as one continuous path.
func _add_route_decals(scene: Node) -> void:
	var dot := _make_dot_texture()
	for entry: Dictionary in _track:
		var origin: Vector3 = entry["origin"]
		var decal := Decal.new()
		decal.texture_albedo = dot
		decal.modulate = _avatar_colour()
		decal.albedo_mix = 1.0
		decal.size = Vector3(0.9, 2.0, 0.9)
		decal.position = Vector3(origin.x, 0.05, origin.z)
		decal.normal_fade = 0.6
		scene.add_child(decal)


func _make_dot_texture() -> Texture2D:
	var size := 48
	var img := Image.create(size, size, false, Image.FORMAT_RGBA8)
	var centre := Vector2(float(size) * 0.5, float(size) * 0.5)
	var radius := float(size) * 0.5
	for y: int in size:
		for x: int in size:
			var d := Vector2(float(x), float(y)).distance_to(centre) / radius
			var a := clampf(1.0 - d, 0.0, 1.0)
			img.set_pixel(x, y, Color(1.0, 1.0, 1.0, a * a))
	return ImageTexture.create_from_image(img)


func _frame_camera(scene: Node) -> void:
	# Replace the static DevCamera with the mouse-driven free-look orbit camera
	# (drag = orbit, wheel = zoom, WASD = pan) so the whole 100 m world is walkable.
	var old := scene.get_node_or_null("DevCamera") as Camera3D
	if old != null:
		old.queue_free()
	var cam: Camera3D = load("res://scripts/dev/OrbitCameraController.gd").new()
	cam.name = "DevOrbitCamera"
	cam.fov = 55.0
	scene.add_child(cam)
	cam.make_current()


func _add_sky_and_sun(scene: Node) -> void:
	var sky_mat := ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color(0.32, 0.52, 0.85)
	sky_mat.sky_horizon_color = Color(0.78, 0.82, 0.86)
	sky_mat.ground_horizon_color = Color(0.72, 0.69, 0.62)
	sky_mat.ground_bottom_color = Color(0.4, 0.37, 0.33)
	sky_mat.sun_angle_max = 10.0
	var sky := Sky.new()
	sky.sky_material = sky_mat
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 1.0
	env.tonemap_mode = Environment.TONE_MAPPER_ACES
	env.tonemap_exposure = 1.05
	env.adjustment_enabled = true
	env.adjustment_contrast = 1.12
	env.adjustment_saturation = 1.12
	env.volumetric_fog_enabled = true
	env.volumetric_fog_density = 0.018
	env.volumetric_fog_emission = Color(0.06, 0.07, 0.09)
	var world_env := WorldEnvironment.new()
	world_env.environment = env
	scene.add_child(world_env)
	var sun := scene.get_node_or_null("DevLight") as DirectionalLight3D
	if sun == null:
		sun = DirectionalLight3D.new()
		scene.add_child(sun)
	sun.rotation = Vector3(deg_to_rad(-38.0), deg_to_rad(-42.0), 0.0)
	sun.light_energy = 1.35
	sun.light_color = Color(1.0, 0.93, 0.78)
	sun.shadow_enabled = true
	sun.sky_mode = DirectionalLight3D.SKY_MODE_LIGHT_AND_SKY


func _zone_accent_colour(zone: String) -> Color:
	match zone:
		"study":
			return Color(1.0, 0.9, 0.72)  # warm lamplight
		"peripatos":
			return Color(0.95, 0.95, 0.9)  # bright noon
		"chashitsu":
			return Color(1.0, 0.78, 0.55)  # warm sunset
		"agora":
			return Color(0.82, 0.88, 1.0)  # cool bright marble
		"garden":
			return Color(0.8, 1.0, 0.82)  # soft green morning
		_:
			return Color(1.0, 1.0, 1.0)


# Load each committed geometry-nodes <zone>_v1.glb at its ZONE_CENTERS (from the
# committed zone_layout.json) via GLTFDocument at runtime — no editor import
# step, no .tscn change. The .glb assets are reused as-is (they are produced by
# the separate GPL-licensed Blender package; nothing is baked here).
func _wire_zone_geometry(scene: Node) -> void:
	var layout := _load_json_dict("res://assets/environment/zone_layout.json")
	var zones: PackedStringArray = ["study", "peripatos", "chashitsu", "agora", "garden"]
	for zone: String in zones:
		var centre := Vector3.ZERO
		var arr: Array = layout.get(zone, [])
		if arr.size() == 3:
			centre = Vector3(float(arr[0]), float(arr[1]), float(arr[2]))
		var content := _load_glb("res://assets/environment/%s_v1.glb" % zone)
		if content != null:
			content.position = centre
			scene.add_child(content)
		var placeholder := scene.get_node_or_null(zone.capitalize()) as Node3D
		if placeholder != null:
			placeholder.visible = false
		var accent := SpotLight3D.new()
		accent.position = centre + Vector3(0.0, 15.0, 0.0)
		accent.rotation = Vector3(deg_to_rad(-90.0), 0.0, 0.0)
		accent.light_color = _zone_accent_colour(zone)
		accent.light_energy = 2.4
		accent.spot_range = 42.0
		accent.spot_angle = 44.0
		accent.shadow_enabled = false
		scene.add_child(accent)


func _load_glb(res_path: String) -> Node3D:
	var abs_path := ProjectSettings.globalize_path(res_path)
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	var err := doc.append_from_file(abs_path, state)
	if err != OK:
		push_warning("[TraversalReplayViewer] glb load failed (%d): %s" % [err, res_path])
		return null
	return doc.generate_scene(state) as Node3D


# A 2D overlay stating, in the view itself, exactly what is being shown — so a
# screenshot can never travel without its framing (ADR §0 / AC6).
func _add_title_panel(scene: Node) -> void:
	var lines: PackedStringArray = [
		"[b]%s[/b]" % HONEST_TITLE,
		"",
		"itinerary: peripatos → agora → garden → chashitsu → study → peripatos",
		"source: committed aha traversal golden (offline replay, no LLM, no gateway)",
	]
	var rich := RichTextLabel.new()
	rich.bbcode_enabled = true
	rich.fit_content = true
	rich.scroll_active = false
	rich.custom_minimum_size = Vector2(560.0, 0.0)
	rich.text = "\n".join(lines)

	var panel := PanelContainer.new()
	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 12)
	margin.add_theme_constant_override("margin_right", 12)
	margin.add_theme_constant_override("margin_top", 8)
	margin.add_theme_constant_override("margin_bottom", 8)
	margin.add_child(rich)
	panel.add_child(margin)
	panel.position = Vector2(16.0, 16.0)

	var layer := CanvasLayer.new()
	layer.add_child(panel)
	scene.add_child(layer)


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
			push_warning("[TraversalReplayViewer] non-object line skipped")
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
		push_error("[TraversalReplayViewer] FileAccess.open failed: %s" % path)
		return ""
	var size := file.get_length()
	if size > MAX_INPUT_BYTES:
		file.close()
		push_error(
			"[TraversalReplayViewer] %s exceeds MAX_INPUT_BYTES (%d > %d)"
			% [path, size, MAX_INPUT_BYTES]
		)
		return ""
	var raw := file.get_as_text()
	file.close()
	return raw
