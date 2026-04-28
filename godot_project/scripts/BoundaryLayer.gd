# BoundaryLayer — M6-B-4 xAI zone boundary wireframe.
#
# Draws a cyan rectangular outline on the ground plane for every zone defined
# in ``zone_rects``. Intended to give the researcher an at-a-glance view of
# where an agent currently is and where event boundaries (zone_transition,
# affordance radii) are being evaluated.
#
# Rendering strategy: a single :class:`ImmediateMesh` owned by one
# :class:`MeshInstance3D`. Every outline is four connected lines drawn with
# :class:`RenderingServer`-primitive ``PRIMITIVE_LINE_STRIP`` surfaces — no
# per-zone MeshInstance so the scene tree stays flat.
#
# Toggle with the ``toggle_boundary`` action (``B`` by default). The node
# starts visible because the first-run researcher benefits more from seeing
# the boundaries than from a clean view.
#
# Slice γ — when an EnvelopeRouter is wired in (see ``router_path``), the
# layer subscribes to ``world_layout_received`` and replaces ``zone_rects`` /
# ``prop_coords`` centres with the server-authored coordinates carried in
# the on-connect ``WorldLayoutMsg``. The hard-coded values below remain as a
# pre-connect default so FixtureHarness / offline boots still render.
extends Node3D

@export var router_path: NodePath
@export var line_color: Color = Color(0.2, 0.9, 1.0, 0.9)
@export var line_height: float = 0.05

# M9-A event-boundary-observability. Pulse colour for the violet flash on
# the originating zone; chosen to be distinguishable from the cyan default
# zone outline (0.2, 0.9, 1.0), the yellow affordance ring (0.95, 0.75, 0.2),
# and the cyan proximity ring (0.25, 0.75, 0.95). Codex HIGH 5 → per-zone
# material instances let pulse_zone tween a single zone without repainting
# the rest.
@export var pulse_color: Color = Color(0.55, 0.4, 0.85, 1.0)
@export var pulse_duration: float = 0.6
@export var selection_manager_path: NodePath

# M7 B2 — event boundary overlays. Yellow circles around static world props
# show where ``AffordanceEvent`` fires (2 m radius). A single cyan circle at
# world origin shows the 5 m ``ProximityEvent`` scale — per-agent proximity
# circles are deferred to Slice γ when the layer gains agent position
# awareness (right now BoundaryLayer is static).
@export var affordance_color: Color = Color(0.95, 0.75, 0.2, 0.85)
@export var affordance_radius: float = 2.0
@export var proximity_color: Color = Color(0.25, 0.75, 0.95, 0.6)
@export var proximity_threshold: float = 5.0
@export var circle_segments: int = 48

# Zone rectangles (centre_x, centre_z, size_x, size_z). Centres mirror
# :data:`ZONE_CENTERS` in ``src/erre_sandbox/world/zones.py`` after the
# Slice β rescale (``WORLD_SIZE_M = 100`` → centres at
# ``±WORLD_SIZE_M / 3`` ≈ ±33.33 m). Slice γ replaces these centres at
# runtime via ``WorldLayoutMsg``; the ``sx`` / ``sz`` sizes stay
# Godot-authored because the wire schema only carries centres (the visual
# rectangle dimensions are presentation, not world ground truth).
@export var zone_rects: Array = [
	# Study — NW quadrant (Kant's preferred locus).
	{"name": "study", "cx": -33.33, "cz": -33.33, "sx": 18.0, "sz": 18.0},
	# Peripatos — centre corridor (cross-agent thoroughfare).
	{"name": "peripatos", "cx": 0.0, "cz": 0.0, "sx": 30.0, "sz": 30.0},
	# Chashitsu — NE quadrant (Rikyū's tea-room locus).
	{"name": "chashitsu", "cx": 33.33, "cz": -33.33, "sx": 20.0, "sz": 20.0},
	# Agora — S axis (public gathering locus).
	{"name": "agora", "cx": 0.0, "cz": 33.33, "sx": 24.0, "sz": 24.0},
	# Garden — SE quadrant (roji approach).
	{"name": "garden", "cx": 33.33, "cz": 33.33, "sx": 22.0, "sz": 22.0},
]

# M7 B2 + Slice β: prop coordinates mirrored from
# ``ZONE_PROPS[Zone.CHASHITSU]`` at the post-rescale chashitsu centre
# (``_ZONE_OFFSET ± 0.5`` with ``_ZONE_OFFSET = WORLD_SIZE_M / 3``). Slice γ
# overrides this list when ``WorldLayoutMsg`` arrives; the hard-coded values
# remain as the pre-connect default.
@export var prop_coords: Array = [
	{"name": "chawan_01", "cx": 32.83, "cz": -32.83},
	{"name": "chawan_02", "cx": 33.83, "cz": -33.83},
]

var _affordance_instance: MeshInstance3D
var _affordance_mesh: ImmediateMesh
var _affordance_material: StandardMaterial3D
var _proximity_instance: MeshInstance3D
var _proximity_mesh: ImmediateMesh
var _proximity_material: StandardMaterial3D
# M9-A: per-zone mesh / material so ``pulse_zone`` can tween one zone's
# albedo without repainting the rest (Codex HIGH 5). Keyed by
# ``zone["name"]``; rebuilt on every ``_redraw`` so a ``WorldLayoutMsg``
# that introduces or drops zones stays consistent.
var _zone_instances: Dictionary = {}
var _zone_meshes: Dictionary = {}
var _zone_materials: Dictionary = {}
# M9-A: zero-or-one active pulse Tween per zone. Re-triggering a pulse on
# the same zone before the previous finishes kills and replaces — bounded
# memory and no race when 3 agents fire spatial events into the same
# tick.
var _active_tweens: Dictionary = {}
# M9-A: only spatial trigger kinds drive a zone pulse; non-spatial kinds
# (temporal / biorhythm / internal / speech / perception / erre_mode_shift)
# never reach this set even though they may carry a non-empty zone for
# context purposes.
const _SPATIAL_TRIGGER_KINDS: Array[String] = [
	"zone_transition",
	"affordance",
	"proximity",
]
# M9-A: focus filter — pulses fire only for the user-selected agent so 3-
# agent live runs don't strobe the whole world. ``""`` until the user
# selects, in which case all spatial triggers pulse (single-agent live
# default behaviour).
var _focused_agent_id: String = ""
# Cached ``{zone_name: {"sx": float, "sz": float}}`` derived from the
# Godot-authored ``zone_rects`` defaults. Used to fill the size dimensions
# when ``_on_world_layout_received`` reconstructs ``zone_rects`` from a
# centres-only ``WorldLayoutMsg``.
var _default_zone_sizes: Dictionary = {}


func _ready() -> void:
	_default_zone_sizes = _build_default_zone_sizes(zone_rects)
	# M9-A: per-zone instances are created lazily by ``_redraw`` so that
	# ``WorldLayoutMsg``-driven zone-set changes propagate cleanly.
	# M7 B2 — affordance overlay (yellow) owns its own mesh instance so the
	# three surface sets never share state; changing the zone-rect palette
	# later would otherwise repaint the affordance circles too.
	_affordance_material = _make_unshaded_material(affordance_color)
	_affordance_mesh = ImmediateMesh.new()
	_affordance_instance = MeshInstance3D.new()
	_affordance_instance.mesh = _affordance_mesh
	_affordance_instance.material_override = _affordance_material
	add_child(_affordance_instance)
	# M7 B2 — proximity scale legend (cyan) mirrors the AffordanceEvent
	# instance pattern. One static 5 m circle at world origin is the MVP
	# here — per-agent dynamic proximity circles are Slice γ scope when
	# BoundaryLayer gains agent position awareness.
	_proximity_material = _make_unshaded_material(proximity_color)
	_proximity_mesh = ImmediateMesh.new()
	_proximity_instance = MeshInstance3D.new()
	_proximity_instance.mesh = _proximity_mesh
	_proximity_instance.material_override = _proximity_material
	add_child(_proximity_instance)
	_redraw()
	# DEBUG: confirm per-zone material map is populated with expected keys.
	print("[BoundaryLayer.DEBUG] _ready: _zone_materials.keys()=%s" % [_zone_materials.keys()])
	_wire_router()


func _make_unshaded_material(color: Color) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_color = color
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.no_depth_test = true
	return mat


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("toggle_boundary"):
		visible = not visible


func _redraw() -> void:
	# M9-A: rebuild per-zone instances. zone_rects is the source of truth;
	# zones absent from the new list have their instance / mesh / material
	# / pending tween freed so the scene tree never leaks across a
	# ``WorldLayoutMsg`` swap.
	var current_names: Dictionary = {}
	for zone: Dictionary in zone_rects:
		var name_value: Variant = zone.get("name", "")
		if not (name_value is String) or name_value == "":
			continue
		current_names[name_value] = true
		_ensure_zone_instance(name_value)
		var mesh: ImmediateMesh = _zone_meshes[name_value]
		var material: StandardMaterial3D = _zone_materials[name_value]
		mesh.clear_surfaces()
		var cx: float = zone.get("cx", 0.0)
		var cz: float = zone.get("cz", 0.0)
		var sx: float = zone.get("sx", 1.0)
		var sz: float = zone.get("sz", 1.0)
		var y := line_height
		var p1 := Vector3(cx - sx * 0.5, y, cz - sz * 0.5)
		var p2 := Vector3(cx + sx * 0.5, y, cz - sz * 0.5)
		var p3 := Vector3(cx + sx * 0.5, y, cz + sz * 0.5)
		var p4 := Vector3(cx - sx * 0.5, y, cz + sz * 0.5)
		mesh.surface_begin(Mesh.PRIMITIVE_LINE_STRIP, material)
		mesh.surface_add_vertex(p1)
		mesh.surface_add_vertex(p2)
		mesh.surface_add_vertex(p3)
		mesh.surface_add_vertex(p4)
		mesh.surface_add_vertex(p1)
		mesh.surface_end()
	# Drop zones that disappeared from zone_rects.
	var stale: Array = []
	for existing in _zone_instances.keys():
		if not current_names.has(existing):
			stale.append(existing)
	for name_to_drop in stale:
		_drop_zone_instance(name_to_drop)
	# M7 B2 — affordance circles per prop (2 m yellow).
	_affordance_mesh.clear_surfaces()
	for prop: Dictionary in prop_coords:
		var cx: float = prop.get("cx", 0.0)
		var cz: float = prop.get("cz", 0.0)
		_draw_circle(_affordance_mesh, _affordance_material, cx, cz, affordance_radius)
	# M7 B2 — proximity scale legend (single 5 m cyan circle at origin).
	# Slice γ replaces this with per-agent dynamic circles when the layer
	# gains agent tracking; until then, the static legend gives the
	# researcher a ground-truth size reference for the 5 m threshold.
	_proximity_mesh.clear_surfaces()
	_draw_circle(_proximity_mesh, _proximity_material, 0.0, 0.0, proximity_threshold)


func _draw_circle(
	mesh: ImmediateMesh,
	material: StandardMaterial3D,
	cx: float,
	cz: float,
	radius: float,
) -> void:
	# Approximate a circle on the XZ plane with ``circle_segments`` line
	# segments. Closed loop: the first vertex is repeated at the end so the
	# LINE_STRIP primitive produces a continuous ring rather than a C-shape.
	var y := line_height
	mesh.surface_begin(Mesh.PRIMITIVE_LINE_STRIP, material)
	for i in circle_segments + 1:
		var theta := TAU * float(i) / float(circle_segments)
		var px := cx + cos(theta) * radius
		var pz := cz + sin(theta) * radius
		mesh.surface_add_vertex(Vector3(px, y, pz))
	mesh.surface_end()


# ---- M9-A — per-zone instance lifecycle + pulse ----


func _ensure_zone_instance(zone_name: String) -> void:
	if _zone_instances.has(zone_name):
		return
	var material: StandardMaterial3D = _make_unshaded_material(line_color)
	var mesh := ImmediateMesh.new()
	var instance := MeshInstance3D.new()
	instance.mesh = mesh
	instance.material_override = material
	add_child(instance)
	_zone_instances[zone_name] = instance
	_zone_meshes[zone_name] = mesh
	_zone_materials[zone_name] = material


func _drop_zone_instance(zone_name: String) -> void:
	var pending: Tween = _active_tweens.get(zone_name)
	if pending != null and pending.is_valid():
		pending.kill()
	_active_tweens.erase(zone_name)
	var instance: MeshInstance3D = _zone_instances.get(zone_name)
	if instance != null:
		instance.queue_free()
	_zone_instances.erase(zone_name)
	_zone_meshes.erase(zone_name)
	_zone_materials.erase(zone_name)


## Pulse a single zone's outline to ``pulse_color`` then back to
## ``line_color`` over ``duration`` seconds (M9-A).
##
## Re-triggering on the same zone before the previous pulse finishes
## kills the old tween and starts fresh, so back-to-back trigger events
## remain visually crisp instead of compounding into a long fade. Unknown
## ``zone_name`` is a quiet no-op (additive wire compatibility for future
## zone enums).
func pulse_zone(zone_name: String, duration: float = -1.0) -> void:
	var material: StandardMaterial3D = _zone_materials.get(zone_name)
	if material == null:
		# DEBUG: lookup mismatch — zone name not in our material map.
		print("[BoundaryLayer.DEBUG] pulse_zone NO MATERIAL for zone=%s, available_keys=%s" % [zone_name, _zone_materials.keys()])
		return
	var d: float = pulse_duration if duration < 0.0 else duration
	var pending: Tween = _active_tweens.get(zone_name)
	if pending != null and pending.is_valid():
		pending.kill()
	# DEBUG: confirm the tween actually starts. If this prints but no visual
	# change occurs, the bug is in shading / line width / camera.
	print("[BoundaryLayer.DEBUG] pulse_zone START zone=%s duration=%.2fs pulse_color=%s line_color=%s" % [zone_name, d, pulse_color, line_color])
	material.albedo_color = pulse_color
	var tween := create_tween()
	tween.tween_property(material, "albedo_color", line_color, d)
	_active_tweens[zone_name] = tween


# ---- Slice γ — WorldLayoutMsg consumer ----


func _wire_router() -> void:
	var router := _resolve_router()
	if router == null:
		# DEBUG: BoundaryLayer is alive but no router → no pulse possible.
		print("[BoundaryLayer.DEBUG] _wire_router: NO ROUTER FOUND")
		return
	print("[BoundaryLayer.DEBUG] _wire_router: router=%s has_zone_pulse_requested=%s" % [router.name, router.has_signal("zone_pulse_requested")])
	if not router.has_signal("world_layout_received"):
		push_warning("[BoundaryLayer] router lacks world_layout_received signal")
		return
	router.world_layout_received.connect(_on_world_layout_received)
	# M9-A: zone_pulse_requested is additive on EnvelopeRouter; older
	# routers without it stay functional with WorldLayoutMsg only.
	if router.has_signal("zone_pulse_requested"):
		router.zone_pulse_requested.connect(_on_zone_pulse_requested)
		print("[BoundaryLayer.DEBUG] connected zone_pulse_requested")
	else:
		print("[BoundaryLayer.DEBUG] router does NOT have zone_pulse_requested signal — pulse path is broken")
	# Selection-driven focus filter.
	var selector := _resolve_selection_manager()
	if selector != null and selector.has_signal("selected_agent_id"):
		selector.selected_agent_id.connect(_on_agent_selected)
		print("[BoundaryLayer.DEBUG] connected to SelectionManager")
	else:
		print("[BoundaryLayer.DEBUG] SelectionManager not found / no signal — focus filter inactive (all pulses fire as fallback)")


func _resolve_selection_manager() -> Node:
	if selection_manager_path != NodePath(""):
		var node := get_node_or_null(selection_manager_path)
		if node != null:
			return node
	return get_tree().root.find_child("SelectionManager", true, false)


func _on_agent_selected(agent_id: String, _agent_node: Node3D) -> void:
	if agent_id == _focused_agent_id:
		return
	_focused_agent_id = agent_id
	# Clear any in-flight pulse so a previous-agent's tween doesn't bleed
	# into the new focus context.
	for zone_name in _active_tweens.keys():
		var pending: Tween = _active_tweens[zone_name]
		if pending != null and pending.is_valid():
			pending.kill()
		var material: StandardMaterial3D = _zone_materials.get(zone_name)
		if material != null:
			material.albedo_color = line_color
	_active_tweens.clear()


func _on_zone_pulse_requested(
	agent_id: String, kind: String, zone: String, _tick: int,
) -> void:
	# DEBUG: log every incoming pulse request before any filter.
	print("[BoundaryLayer.DEBUG] _on_zone_pulse_requested agent=%s kind=%s zone=%s focused=%s" % [agent_id, kind, zone, _focused_agent_id])
	if kind not in _SPATIAL_TRIGGER_KINDS:
		print("[BoundaryLayer.DEBUG] DROP: kind=%s not in spatial set" % kind)
		return
	# Empty focus = single-agent fallback (pulse for every agent). Set
	# focus = strict match (no pulses for other agents).
	if _focused_agent_id != "" and agent_id != _focused_agent_id:
		print("[BoundaryLayer.DEBUG] DROP: focused=%s != incoming=%s (focus filter)" % [_focused_agent_id, agent_id])
		return
	pulse_zone(zone)


func _resolve_router() -> Node:
	if router_path != NodePath(""):
		var node := get_node_or_null(router_path)
		if node != null:
			return node
	return get_tree().root.find_child("EnvelopeRouter", true, false)


func _build_default_zone_sizes(rects: Array) -> Dictionary:
	var sizes: Dictionary = {}
	for zone: Dictionary in rects:
		var name_value: Variant = zone.get("name", "")
		if not (name_value is String) or name_value == "":
			continue
		sizes[name_value] = {
			"sx": float(zone.get("sx", 1.0)),
			"sz": float(zone.get("sz", 1.0)),
		}
	return sizes


func _on_world_layout_received(zones: Array, props: Array) -> void:
	# Slice γ — replace ``zone_rects`` centres with the on-connect
	# ``WorldLayoutMsg`` payload. The wire schema only carries centres, so
	# the rectangle sizes fall back to the Godot-authored
	# ``_default_zone_sizes`` (presentation-only). An unknown zone name is
	# skipped with a warning rather than dropped silently.
	var new_rects: Array = []
	for entry_value: Variant in zones:
		if not (entry_value is Dictionary):
			continue
		var entry: Dictionary = entry_value
		var zone_name: String = str(entry.get("zone", ""))
		if zone_name == "":
			continue
		var defaults: Dictionary = _default_zone_sizes.get(
			zone_name, {"sx": 18.0, "sz": 18.0}
		)
		new_rects.append({
			"name": zone_name,
			"cx": float(entry.get("x", 0.0)),
			"cz": float(entry.get("z", 0.0)),
			"sx": float(defaults.get("sx", 18.0)),
			"sz": float(defaults.get("sz", 18.0)),
		})
	# Asymmetric on purpose: zones keep the Godot-authored defaults when the
	# envelope carries no rows, because every γ run has 5 fixed zones and an
	# empty list is structurally a malformed payload — falling back to the
	# defaults keeps the wireframe usable rather than disappearing the
	# whole world. Props (below) take the opposite policy because zero
	# props is a legitimate layout state.
	if not new_rects.is_empty():
		zone_rects = new_rects

	var new_props: Array = []
	for prop_value: Variant in props:
		if not (prop_value is Dictionary):
			continue
		var prop_entry: Dictionary = prop_value
		var prop_id: String = str(prop_entry.get("prop_id", ""))
		if prop_id == "":
			continue
		new_props.append({
			"name": prop_id,
			"cx": float(prop_entry.get("x", 0.0)),
			"cz": float(prop_entry.get("z", 0.0)),
		})
	# An empty ``props`` array is a legitimate envelope (zones may declare
	# no props) — overwrite ``prop_coords`` so a fresh connection cannot
	# inherit a stale chashitsu tea-bowl pair after the layout shrinks.
	prop_coords = new_props
	_redraw()
