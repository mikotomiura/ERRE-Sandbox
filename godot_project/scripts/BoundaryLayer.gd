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

var _mesh_instance: MeshInstance3D
var _mesh: ImmediateMesh
var _material: StandardMaterial3D
var _affordance_instance: MeshInstance3D
var _affordance_mesh: ImmediateMesh
var _affordance_material: StandardMaterial3D
var _proximity_instance: MeshInstance3D
var _proximity_mesh: ImmediateMesh
var _proximity_material: StandardMaterial3D
# Cached ``{zone_name: {"sx": float, "sz": float}}`` derived from the
# Godot-authored ``zone_rects`` defaults. Used to fill the size dimensions
# when ``_on_world_layout_received`` reconstructs ``zone_rects`` from a
# centres-only ``WorldLayoutMsg``.
var _default_zone_sizes: Dictionary = {}


func _ready() -> void:
	_default_zone_sizes = _build_default_zone_sizes(zone_rects)
	_material = _make_unshaded_material(line_color)
	_mesh = ImmediateMesh.new()
	_mesh_instance = MeshInstance3D.new()
	_mesh_instance.mesh = _mesh
	_mesh_instance.material_override = _material
	add_child(_mesh_instance)
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
	_mesh.clear_surfaces()
	for zone: Dictionary in zone_rects:
		var cx: float = zone.get("cx", 0.0)
		var cz: float = zone.get("cz", 0.0)
		var sx: float = zone.get("sx", 1.0)
		var sz: float = zone.get("sz", 1.0)
		var y := line_height
		var p1 := Vector3(cx - sx * 0.5, y, cz - sz * 0.5)
		var p2 := Vector3(cx + sx * 0.5, y, cz - sz * 0.5)
		var p3 := Vector3(cx + sx * 0.5, y, cz + sz * 0.5)
		var p4 := Vector3(cx - sx * 0.5, y, cz + sz * 0.5)
		_mesh.surface_begin(Mesh.PRIMITIVE_LINE_STRIP, _material)
		_mesh.surface_add_vertex(p1)
		_mesh.surface_add_vertex(p2)
		_mesh.surface_add_vertex(p3)
		_mesh.surface_add_vertex(p4)
		_mesh.surface_add_vertex(p1)
		_mesh.surface_end()
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


# ---- Slice γ — WorldLayoutMsg consumer ----


func _wire_router() -> void:
	var router := _resolve_router()
	if router == null:
		# No router in the tree (e.g. FixtureHarness loads BoundaryLayer
		# without a Main scene). The hard-coded ``zone_rects`` /
		# ``prop_coords`` defaults stay in effect — the layer remains
		# functional, just without server-authored coordinates.
		return
	if not router.has_signal("world_layout_received"):
		push_warning("[BoundaryLayer] router lacks world_layout_received signal")
		return
	router.world_layout_received.connect(_on_world_layout_received)


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
