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
#   * interactive (developer observation): no ``--dump`` → instantiate
#     ``scenes/dev/SocietyReplayScene.tscn`` and drive each avatar along its
#     physics-clock trace (looping), with a billboarded speech/animation label
#     advanced on the SEPARATE agent-tick clock. Falls back to printing the
#     resolved timeline when no rendering server is available (headless).
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
## Interactive playback rate: committed physics ticks advanced per real second
## (the 20-tick trace loops). Dev-only observation cadence, never a witness.
const PLAYBACK_TICKS_PER_SEC: float = 3.0

# --- interactive playback state (only used in the no-``--dump`` visual mode) --- #
var _interactive_playing: bool = false
## order_slot -> {physics_tick_index -> {"origin": Vector3, "yaw": float}} (motion
## authority, physics_tick clock; committed trace echo, never recomputed HIGH-3).
var _tracks: Dictionary = {}
var _avatar_nodes: Dictionary = {}   ## order_slot -> Node3D (scene avatar)
var _avatar_labels: Dictionary = {}  ## order_slot -> Label3D (speech/animation)
## order_slot -> Array[{"agent_tick": int, "text": String}] on the agent_tick
## clock — a SEPARATE series, NOT joined with the motion tracks above (MEDIUM-1).
var _label_series: Dictionary = {}
var _max_tick: int = 0
var _ticks_per_cog: int = 5
var _play_clock: float = 0.0
var _last_usec: int = 0


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

	# Interactive (developer observation, §3.4): open the whole-view scene and
	# drive each avatar along its physics-clock trace, with speech/animation
	# labels advanced on the SEPARATE agent-tick clock (§3.3 role split). Falls
	# back to the printed timeline if the scene cannot be instantiated (e.g. a
	# ``--headless`` interactive run with no rendering server).
	if _setup_interactive_scene(manifest, placements, stream_path):
		return  # keep the main loop running; process_frame drives the playback
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
# Interactive playback (§3.4): instantiate the whole-view scene and drive the
# avatars. Motion authority stays the committed trace echo (physics clock);
# speech/animation labels run on the independent agent-tick clock (§3.3).
# --------------------------------------------------------------------------- #
func _setup_interactive_scene(
	manifest: Dictionary, placements: Array, stream_path: String
) -> bool:
	var packed := load("res://scenes/dev/SocietyReplayScene.tscn") as PackedScene
	if packed == null:
		return false
	var scene := packed.instantiate()
	if scene == null:
		return false
	root.add_child(scene)

	# Dev-only visual fidelity (never a witness — the machine byte comparison is
	# the headless dump path, which does NOT instantiate this scene): a procedural
	# sky + sun, the committed geometry-nodes .glb loaded at each zone centre, and
	# a camera framed on the peripatos origin where this golden's agents walk.
	_add_sky_and_sun(scene)
	_wire_zone_geometry(scene)
	_frame_camera(scene)
	_add_dialog_panel(scene, stream_path)

	var run: Dictionary = manifest.get("run", {})
	_ticks_per_cog = maxi(1, int(run.get("physics_ticks_per_cognition", 5)))

	# Per-slot motion tracks (physics clock) from the committed trace echo.
	for entry: Dictionary in placements:
		var slot := int(entry["order_slot"])
		var tick := int(entry["physics_tick_index"])
		_max_tick = maxi(_max_tick, tick)
		if not _tracks.has(slot):
			_tracks[slot] = {}
		_tracks[slot][tick] = {
			"origin": Vector3(float(entry["x"]), float(entry["y"]), float(entry["z"])),
			"yaw": float(entry["yaw"]),
		}

	# Resolve avatar nodes + give each a distinct colour and a readable, always-on
	# billboard label showing the current speech / animation.
	var run_ids: Array = manifest.get("run", {}).get("agent_ids", [])
	for slot: int in _tracks.keys():
		var node := scene.get_node_or_null("Avatar%d" % slot) as Node3D
		if node == null:
			continue
		_avatar_nodes[slot] = node
		_tint_avatar(node, slot)
		_add_avatar_prop(node, slot)
		var who := String(run_ids[slot]) if slot < run_ids.size() else "slot %d" % slot
		var label := Label3D.new()
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		label.no_depth_test = true
		label.fixed_size = true
		label.position = Vector3(0.0, 2.6, 0.0)
		label.pixel_size = 0.0009
		label.font_size = 38
		label.outline_size = 11
		label.outline_modulate = Color(0, 0, 0, 0.9)
		label.modulate = _slot_colour(slot)
		label.text = who
		node.add_child(label)
		_avatar_labels[slot] = label
		# A name tag pinned above the speech line so agents stay identifiable.
		var tag := Label3D.new()
		tag.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		tag.no_depth_test = true
		tag.fixed_size = true
		tag.position = Vector3(0.0, 3.0, 0.0)
		tag.pixel_size = 0.0009
		tag.font_size = 30
		tag.outline_size = 8
		tag.outline_modulate = Color(0, 0, 0, 0.85)
		tag.modulate = _slot_colour(slot)
		tag.text = who
		node.add_child(tag)

	_add_trace_decals(scene)
	_label_series = _resolve_label_series(stream_path)
	if _avatar_nodes.is_empty():
		return false

	_interactive_playing = true
	_last_usec = Time.get_ticks_usec()
	process_frame.connect(_on_playback_frame)
	print(
		"[SocietyReplayViewer] interactive playback: %d avatar(s), %d physics ticks (loop)"
		% [_avatar_nodes.size(), _max_tick + 1]
	)
	return true


# Speech/animation label text on the agent-tick clock (independent series, §3.3).
# Kept SEPARATE from the dumped firing entries so the headless dump schema (§4
# byte witness) is untouched.
func _resolve_label_series(path: String) -> Dictionary:
	var rows := _load_jsonl(path)
	var out: Dictionary = {}
	for row: Dictionary in rows:
		var envelope: Dictionary = row.get("envelope", {})
		var kind := String(envelope.get("kind", ""))
		if not FIRING_KINDS.has(kind):
			continue
		var slot := int(row.get("order_slot", 0))
		var text := ""
		if kind == "speech":
			text = String(envelope.get("utterance", ""))
		else:
			text = "* " + String(envelope.get("animation_name", ""))
		if not out.has(slot):
			out[slot] = []
		out[slot].append({"agent_tick": int(row.get("agent_tick", 0)), "text": text})
	return out


# Per-frame playback tick (physics clock), looping over [0, _max_tick]. Position
# is interpolated between the two bracketing committed trace rows; the label is
# advanced on the derived agent-tick clock (physics // physics_ticks_per_cognition)
# — the two series are NOT joined, only rendered on the same avatar (MEDIUM-1).
func _on_playback_frame() -> void:
	if not _interactive_playing:
		return
	var now := Time.get_ticks_usec()
	var delta := float(now - _last_usec) / 1_000_000.0
	_last_usec = now
	var span := float(_max_tick)
	if span <= 0.0:
		return
	_play_clock += delta * PLAYBACK_TICKS_PER_SEC
	while _play_clock > span:
		_play_clock -= span
	var lo := int(_play_clock)
	var frac := _play_clock - float(lo)
	var hi := mini(lo + 1, _max_tick)
	var agent_tick := lo / _ticks_per_cog
	for slot: int in _avatar_nodes.keys():
		var track: Dictionary = _tracks[slot]
		if not track.has(lo):
			continue
		var a: Dictionary = track[lo]
		var b: Dictionary = track[hi] if track.has(hi) else a
		var node: Node3D = _avatar_nodes[slot]
		node.position = (a["origin"] as Vector3).lerp(b["origin"] as Vector3, frac)
		node.rotation.y = lerp_angle(float(a["yaw"]), float(b["yaw"]), frac)
		_update_label(slot, agent_tick)


func _update_label(slot: int, agent_tick: int) -> void:
	if not _avatar_labels.has(slot):
		return
	var series: Array = _label_series.get(slot, [])
	var text := ""
	for item: Dictionary in series:
		if int(item["agent_tick"]) <= agent_tick:
			text = String(item["text"])
	(_avatar_labels[slot] as Label3D).text = text


# --------------------------------------------------------------------------- #
# Dev-only visual fidelity helpers (interactive mode only; never touched by the
# headless dump witness path). Committed assets only, no measurement surface.
# --------------------------------------------------------------------------- #
func _slot_colour(slot: int) -> Color:
	var palette: Array = [
		Color(1.0, 0.55, 0.25),  # slot 0 — warm
		Color(0.35, 0.65, 1.0),  # slot 1 — cool
		Color(0.5, 0.85, 0.4),
		Color(0.9, 0.5, 0.9),
	]
	return palette[slot % palette.size()]


func _find_mesh_instances(n: Node) -> Array:
	var out: Array = []
	if n is MeshInstance3D:
		out.append(n)
	for c: Node in n.get_children():
		out.append_array(_find_mesh_instances(c))
	return out


func _tint_avatar(node: Node3D, slot: int) -> void:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = _slot_colour(slot)
	mat.roughness = 0.55
	for mesh: MeshInstance3D in _find_mesh_instances(node):
		mesh.material_override = mat


# A1 — a small floating identity prop above each avatar (distinct primitive per
# slot: sphere / cone / box / cylinder), colour-matched. Keeps the silhouette but
# adds a symbolic marker so agents read apart at a glance (stylized convention).
func _add_avatar_prop(node: Node3D, slot: int) -> void:
	var meshes: Array = [SphereMesh.new(), CylinderMesh.new(), BoxMesh.new(), TorusMesh.new()]
	var mesh: Mesh = meshes[slot % meshes.size()]
	var mat := StandardMaterial3D.new()
	mat.albedo_color = _slot_colour(slot)
	mat.emission_enabled = true
	mat.emission = _slot_colour(slot)
	mat.emission_energy_multiplier = 0.6
	var marker := MeshInstance3D.new()
	marker.mesh = mesh
	marker.material_override = mat
	marker.scale = Vector3(0.35, 0.35, 0.35)
	marker.position = Vector3(0.0, 2.4, 0.0)
	node.add_child(marker)


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


# C1 — lay a soft coloured decal at each committed trace position so each agent's
# recorded path is drawn on the ground (projection-mapping "trace on surface").
func _add_trace_decals(scene: Node) -> void:
	var dot := _make_dot_texture()
	for slot: int in _tracks.keys():
		var track: Dictionary = _tracks[slot]
		var ticks: Array = track.keys()
		ticks.sort()
		for tick: int in ticks:
			var origin: Vector3 = track[tick]["origin"]
			var decal := Decal.new()
			decal.texture_albedo = dot
			decal.modulate = _slot_colour(slot)
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
	# Replace the static DevCamera with a mouse-driven free-look orbit camera
	# (drag = orbit, wheel = zoom, WASD = pan) framed on the peripatos origin.
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
	# B1 — ACES tonemap + a touch of contrast/saturation for a less flat image.
	env.tonemap_mode = Environment.TONE_MAPPER_ACES
	env.tonemap_exposure = 1.05
	env.adjustment_enabled = true
	env.adjustment_contrast = 1.12
	env.adjustment_saturation = 1.12
	# B3 — light volumetric fog for depth/atmosphere (cheap; static density).
	env.volumetric_fog_enabled = true
	env.volumetric_fog_density = 0.018
	env.volumetric_fog_emission = Color(0.06, 0.07, 0.09)
	var world_env := WorldEnvironment.new()
	world_env.environment = env
	scene.add_child(world_env)
	# B2 — turn the existing dev light into a warm late-afternoon sun (long soft
	# shadows) that the procedural sky renders as a sun disk.
	var sun := scene.get_node_or_null("DevLight") as DirectionalLight3D
	if sun == null:
		sun = DirectionalLight3D.new()
		scene.add_child(sun)
	sun.rotation = Vector3(deg_to_rad(-38.0), deg_to_rad(-42.0), 0.0)
	sun.light_energy = 1.35
	sun.light_color = Color(1.0, 0.93, 0.78)
	sun.shadow_enabled = true
	sun.sky_mode = DirectionalLight3D.SKY_MODE_LIGHT_AND_SKY


# Load each committed geometry-nodes ``<zone>_v1.glb`` at its ZONE_CENTERS (from
# the committed ``zone_layout.json``) via GLTFDocument at runtime — no editor
# import step, no ``.tscn`` change (so the headless scene-load test is untouched).
# The primitive zone placeholders are hidden to reveal the geometry-nodes content.
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
		# B2 — a soft downward accent light per zone gives each world its own mood.
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
		push_warning("[SocietyReplayViewer] glb load failed (%d): %s" % [err, res_path])
		return null
	return doc.generate_scene(state) as Node3D


# A 2D overlay panel that lists the full speech transcript (envelope_stream, in
# (order_slot, agent_tick, seq) order) so the concrete conversation is readable
# alongside the 3D view. Speech only — ``move`` is not a conversation turn (§3.3).
func _add_dialog_panel(scene: Node, stream_path: String) -> void:
	var rows := _load_jsonl(stream_path)
	var entries: Array = []
	for row: Dictionary in rows:
		var envelope: Dictionary = row.get("envelope", {})
		if String(envelope.get("kind", "")) != "speech":
			continue
		entries.append(
			{
				"order_slot": int(row.get("order_slot", 0)),
				"agent_tick": int(row.get("agent_tick", 0)),
				"seq": int(row.get("seq", 0)),
				"who": String(envelope.get("agent_id", "")),
				"utterance": String(envelope.get("utterance", "")),
			}
		)
	entries.sort_custom(_firing_before)

	var lines: PackedStringArray = ["[b]会話ログ[/b]  (envelope_stream / speech)", ""]
	for e: Dictionary in entries:
		var colour := _slot_colour(int(e["order_slot"])).to_html(false)
		lines.append(
			"[color=#%s]%s[/color]  t%d: %s"
			% [colour, e["who"], int(e["agent_tick"]), e["utterance"]]
		)

	var rich := RichTextLabel.new()
	rich.bbcode_enabled = true
	rich.fit_content = true
	rich.scroll_active = false
	rich.custom_minimum_size = Vector2(440.0, 0.0)
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
