# ReasoningPanel — M6-B-2 xAI side panel for the Research Observatory.
#
# Subscribes to ``EnvelopeRouter`` and renders the most recent
# :class:`ReasoningTrace` + :class:`ReflectionEvent` for a single focused
# agent. Acts as the primary "why did this agent decide that" surface for
# the researcher.
#
# Display contract:
#   * Title line        — ``agent_id`` + current ERRE mode.
#   * Salient           — what the LLM flagged as most attention-grabbing.
#   * Decision          — the one-sentence rationale.
#   * Next intent       — forward-looking plan for the coming ticks.
#   * Latest reflection — collapsible summary of the most recent
#                         :class:`ReflectionEvent` (from M4 Reflector,
#                         wired over the wire in M6-A-4).
#
# Focus selection is intentionally simple in this first cut: the panel
# locks onto the first ``reasoning_trace`` it ever sees and sticks with
# that agent unless ``set_focused_agent`` is called. A future
# SelectionManager (M6-B-1 follow-up) can drive ``set_focused_agent`` from
# avatar click events.
extends Control

# M7-ζ-1: route all user-facing labels through the locale dict so the
# JP/EN flip (and the future ``tr()`` migration) needs only the dict edit.
const Strings = preload("res://scripts/i18n/Strings.gd")

# 2026-04-28 godot-viewport-layout (v2.1, codex review). The panel lives on
# the right side of an ``HSplitContainer`` and toggles between two widths:
# expanded shows the full content, collapsed hides the body and only the
# header (with the toggle button) remains visible as a 60-pixel strip.
const PANEL_EXPANDED_WIDTH := 340
const PANEL_COLLAPSED_WIDTH := 60

@export var router_path: NodePath

var _focused_agent: String = ""
# M7-ζ-2: most-recently observed persona_id for the focused agent — sourced
# from ``ReasoningTrace.persona_id`` (M7-ζ-2 wire) or ``AgentUpdate.persona_id``
# (always carried). Cached so the title + summary do not flicker between
# resolved and "(persona unknown)" when the two streams interleave.
var _focused_persona_id: String = ""
var _title_label: Label
var _mode_label: Label
var _persona_summary_label: Label
var _salient_label: Label
var _decision_label: Label
var _intent_label: Label
var _reflection_label: Label
var _relationships_label: Label
var _last_reflection_tick: int = -1
# M7-ζ-2: keep up to ``_RECENT_REFLECTIONS_CAP`` of the most-recent reflection
# events in tick-descending order. ``_last_reflection_tick`` still stamps the
# newest seen tick so out-of-order replays do not regress to an older summary
# (the cap-based dedupe already filters duplicates by exact tick).
const _RECENT_REFLECTIONS_CAP: int = 3
var _recent_reflections: Array[Dictionary] = []
# M7-ζ-1: multi-agent selector. ``_known_agents`` mirrors the OptionButton
# items 1..N (item 0 stays the placeholder) so SelectionManager click-focus
# and selector changes can sync without iterating the OptionButton each
# update. ``_syncing_selector`` is a re-entry guard so set_focused_agent →
# selector.select() does not re-trigger ``item_selected`` and recurse.
var _agent_selector: OptionButton
var _known_agents: Array[String] = []
var _syncing_selector: bool = false

# 2026-04-28 godot-viewport-layout (v2.1). HSplitContainer-driven collapse:
# ``_split`` is the parent ``HSplitContainer`` (resolved in ``_ready``).
# ``_last_expanded_offset`` remembers the latest splitter position the user
# dragged to while expanded, so collapse → expand restores the chosen width
# instead of snapping back to the default ``-PANEL_EXPANDED_WIDTH`` (codex
# review MEDIUM-5).
var _split: HSplitContainer
var _collapsed: bool = false
var _last_expanded_offset: int = -PANEL_EXPANDED_WIDTH
var _collapse_button: Button
var _body_container: VBoxContainer


func _ready() -> void:
	_build_tree()
	_split = get_parent() as HSplitContainer
	if _split != null:
		if _split.has_signal("dragged"):
			_split.dragged.connect(_on_split_dragged)
		# Defer the initial offset until after the first layout frame:
		# ``clamp_split_offset`` reads ``dragger_positions`` which the engine
		# only fills in once the children have been measured.
		call_deferred("_apply_initial_split_offset")
	var router := _resolve_router()
	if router == null:
		push_error("[ReasoningPanel] EnvelopeRouter not found at %s" % router_path)
		return
	for signal_name in [
		"reasoning_trace_received",
		"reflection_event_received",
		"agent_updated",
	]:
		if not router.has_signal(signal_name):
			push_error("[ReasoningPanel] router missing signal: %s" % signal_name)
			return
	router.reasoning_trace_received.connect(_on_reasoning_trace_received)
	router.reflection_event_received.connect(_on_reflection_event_received)
	router.agent_updated.connect(_on_agent_updated)


func _resolve_router() -> Node:
	if router_path != NodePath(""):
		var node := get_node_or_null(router_path)
		if node != null:
			return node
	return get_tree().root.find_child("EnvelopeRouter", true, false)


func _build_tree() -> void:
	# 2026-04-28 godot-viewport-layout (v2.1). The panel now sits inside an
	# ``HSplitContainer``; the expanded width matches the parent container's
	# minimum, while the collapsed state hides ``_body_container`` and only
	# leaves the toggle button visible.
	custom_minimum_size = Vector2(PANEL_EXPANDED_WIDTH, 0)

	var bg := ColorRect.new()
	bg.color = Color(0.06, 0.07, 0.10, 1.0)
	bg.anchor_right = 1.0
	bg.anchor_bottom = 1.0
	bg.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(bg)

	var margin := MarginContainer.new()
	margin.anchor_right = 1.0
	margin.anchor_bottom = 1.0
	margin.add_theme_constant_override("margin_left", 12)
	margin.add_theme_constant_override("margin_right", 12)
	margin.add_theme_constant_override("margin_top", 12)
	margin.add_theme_constant_override("margin_bottom", 12)
	add_child(margin)

	# Outer container holds the always-visible Header and the collapsible
	# Body, in that order. Header is added first so it survives when Body is
	# hidden during the collapsed state (codex HIGH-3).
	var outer := VBoxContainer.new()
	outer.add_theme_constant_override("separation", 8)
	margin.add_child(outer)

	_build_header(outer)

	_body_container = VBoxContainer.new()
	_body_container.add_theme_constant_override("separation", 10)
	_body_container.size_flags_vertical = Control.SIZE_EXPAND_FILL
	outer.add_child(_body_container)

	# Existing children below are now appended to ``_body_container`` so the
	# whole content can be hidden in one toggle without losing layout.
	# ALIAS: ``vbox`` and ``_body_container`` reference the same node; the
	# alias keeps the diff small for the existing ``vbox.add_child(...)``
	# calls. Future refactors can drop ``vbox`` and reference the field
	# directly.
	var vbox := _body_container

	# M7-ζ-1: agent selector at the top. Lives inside the vbox so it scrolls
	# with the panel content. Boots disabled with the placeholder item;
	# becomes selectable as soon as ``_on_agent_updated`` registers an id.
	_agent_selector = OptionButton.new()
	_agent_selector.add_item(Strings.LABELS["SELECTOR_PROMPT"])
	_agent_selector.disabled = true
	_agent_selector.item_selected.connect(_on_agent_selector_item_selected)
	vbox.add_child(_agent_selector)

	_title_label = _make_label(vbox, Strings.LABELS["PANEL_TITLE"], 18, Color(0.9, 0.92, 0.95, 1.0))
	_mode_label = _make_label(vbox, Strings.LABELS["AGENT_NONE"], 12, Color(0.65, 0.75, 0.9, 1.0))
	# M7-ζ-2: 1-line persona personality summary, sized between mode and
	# section headers. Hidden until a trace / update gives us a persona_id.
	_persona_summary_label = _make_label(
		vbox, Strings.LABELS["PERSONA_SUMMARY_UNKNOWN"], 11, Color(0.75, 0.78, 0.85, 1.0),
	)
	vbox.add_child(_make_divider())

	_make_label(vbox, Strings.LABELS["SALIENT"], 11, Color(0.8, 0.7, 0.4, 1.0))
	_salient_label = _make_label(vbox, Strings.LABELS["VALUE_DASH"], 14, Color(0.95, 0.95, 0.95, 1.0))

	_make_label(vbox, Strings.LABELS["DECISION"], 11, Color(0.8, 0.5, 0.5, 1.0))
	_decision_label = _make_label(vbox, Strings.LABELS["VALUE_DASH"], 14, Color(0.95, 0.95, 0.95, 1.0))

	_make_label(vbox, Strings.LABELS["NEXT_INTENT"], 11, Color(0.4, 0.8, 0.6, 1.0))
	_intent_label = _make_label(vbox, Strings.LABELS["VALUE_DASH"], 14, Color(0.95, 0.95, 0.95, 1.0))

	vbox.add_child(_make_divider())

	_make_label(vbox, Strings.LABELS["LATEST_REFLECTION"], 11, Color(0.6, 0.7, 0.9, 1.0))
	_reflection_label = _make_label(vbox, Strings.LABELS["REFLECTION_NONE"], 13, Color(0.85, 0.85, 0.9, 1.0))

	vbox.add_child(_make_divider())

	# Slice γ — Relationships block. Shows the focused agent's top-2 bonds
	# (by |affinity|, ties broken by last_interaction_tick descending) so the
	# researcher can read partner-specific affinity drift without opening the
	# DB. Header colour mirrors the SALIENT block's amber to keep the
	# affective surfaces visually coherent.
	_make_label(vbox, Strings.LABELS["RELATIONSHIPS"], 11, Color(0.85, 0.65, 0.45, 1.0))
	_relationships_label = _make_label(
		vbox, Strings.LABELS["RELATIONSHIPS_NONE"], 13, Color(0.92, 0.88, 0.82, 1.0),
	)


func _make_label(parent: Node, text: String, size: int, col: Color) -> Label:
	var lbl := Label.new()
	lbl.text = text
	lbl.add_theme_font_size_override("font_size", size)
	lbl.add_theme_color_override("font_color", col)
	lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	parent.add_child(lbl)
	return lbl


func _make_divider() -> HSeparator:
	var sep := HSeparator.new()
	sep.add_theme_constant_override("separation", 6)
	return sep


# ---- Focus API ----


func set_focused_agent(agent_id: String, _agent_node: Node3D = null) -> void:
	# Second arg is ignored; accepting it lets the panel bind directly to
	# SelectionManager.selected_agent_id(agent_id, agent_node) without an
	# adapter node in MainScene. A future version can use the node to show
	# per-agent persona colouring.
	if agent_id == _focused_agent:
		return
	_focused_agent = agent_id
	_focused_persona_id = ""
	_salient_label.text = Strings.LABELS["VALUE_DASH"]
	_decision_label.text = Strings.LABELS["VALUE_DASH"]
	_intent_label.text = Strings.LABELS["VALUE_DASH"]
	_reflection_label.text = Strings.LABELS["REFLECTION_NONE"]
	_relationships_label.text = Strings.LABELS["RELATIONSHIPS_NONE"]
	_persona_summary_label.text = Strings.LABELS["PERSONA_SUMMARY_UNKNOWN"]
	_last_reflection_tick = -1
	_recent_reflections.clear()
	if agent_id != "":
		_title_label.text = Strings.LABELS["PANEL_TITLE_FOR_AGENT"] % agent_id
	else:
		_title_label.text = Strings.LABELS["PANEL_TITLE"]
	_mode_label.text = Strings.LABELS["AGENT_WAITING"]
	_sync_selector_to_focus(agent_id)


func _apply_persona_to_title(agent_id: String, persona_id: String) -> void:
	# M7-ζ-2: upgrade the bare ``Reasoning Panel — <agent_id>`` title to
	# ``Reasoning Panel — <agent_id> (<display_name>)`` and surface the
	# 1-line personality summary the moment either ``ReasoningTrace.persona_id``
	# or ``AgentUpdate.persona_id`` resolves it. Re-entry safe: if the same
	# persona_id arrives again the labels are already correct.
	if agent_id == "" or persona_id == "":
		return
	if persona_id == _focused_persona_id:
		return
	_focused_persona_id = persona_id
	_title_label.text = Strings.LABELS["PANEL_TITLE_FOR_AGENT_PERSONA"] % [
		agent_id, _persona_display_name(persona_id),
	]
	_persona_summary_label.text = _persona_summary(persona_id)


func _persona_display_name(persona_id: String) -> String:
	if persona_id == "":
		return Strings.LABELS["PERSONA_NAME_UNKNOWN"]
	var key := "PERSONA_NAME_%s" % persona_id.to_upper()
	if Strings.LABELS.has(key):
		return Strings.LABELS[key]
	return Strings.LABELS["PERSONA_NAME_UNKNOWN"]


func _persona_summary(persona_id: String) -> String:
	if persona_id == "":
		return Strings.LABELS["PERSONA_SUMMARY_UNKNOWN"]
	var key := "PERSONA_SUMMARY_%s" % persona_id.to_upper()
	if Strings.LABELS.has(key):
		return Strings.LABELS[key]
	return Strings.LABELS["PERSONA_SUMMARY_UNKNOWN"]


# ---- EnvelopeRouter signal handlers ----


func _on_reasoning_trace_received(agent_id: String, tick: int, trace: Dictionary) -> void:
	# Auto-focus on the first agent we ever see so the panel is useful
	# without a separate selection flow. A later SelectionManager can call
	# ``set_focused_agent`` to override.
	if _focused_agent == "":
		set_focused_agent(agent_id)
	if agent_id != _focused_agent:
		return
	var mode: String = trace.get("mode", "")
	_mode_label.text = Strings.LABELS["AGENT_MODE_TICK"] % [mode, tick]
	_salient_label.text = _coalesce(trace.get("salient"), Strings.LABELS["VALUE_DASH"])
	_decision_label.text = _coalesce(trace.get("decision"), Strings.LABELS["VALUE_DASH"])
	_intent_label.text = _coalesce(trace.get("next_intent"), Strings.LABELS["VALUE_DASH"])
	# M7-ζ-2: persona_id is optional on the wire (None for pre-0.9.0-m7z
	# producers). Only upgrade the title when the field resolves to a
	# non-empty string.
	var persona_value: Variant = trace.get("persona_id")
	if persona_value != null and str(persona_value) != "":
		_apply_persona_to_title(agent_id, str(persona_value))


func _on_reflection_event_received(
	agent_id: String,
	tick: int,
	summary_text: String,
	_event: Dictionary,
) -> void:
	if _focused_agent == "":
		set_focused_agent(agent_id)
	if agent_id != _focused_agent:
		return
	# M7-ζ-2: keep last 3 reflections (tick desc) so the researcher can read
	# short-term reflection cadence without opening the journal. Out-of-order
	# replays are still filtered: a tick already in the cache is ignored, and
	# entries older than the smallest currently held tick are dropped once
	# the cache is at cap.
	for entry: Dictionary in _recent_reflections:
		if int(entry.get("tick", -1)) == tick:
			return
	if (
		_recent_reflections.size() >= _RECENT_REFLECTIONS_CAP
		and tick < int(_recent_reflections[-1].get("tick", -1))
	):
		return
	var rendered: String = (
		summary_text if summary_text != ""
		else Strings.LABELS["REFLECTION_EMPTY_SUMMARY"]
	)
	_recent_reflections.append({"tick": tick, "summary": rendered})
	_recent_reflections.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return int(a.get("tick", -1)) > int(b.get("tick", -1))
	)
	while _recent_reflections.size() > _RECENT_REFLECTIONS_CAP:
		_recent_reflections.pop_back()
	if tick > _last_reflection_tick:
		_last_reflection_tick = tick
	_reflection_label.text = _format_recent_reflections()


func _format_recent_reflections() -> String:
	if _recent_reflections.is_empty():
		return Strings.LABELS["REFLECTION_NONE"]
	var lines: Array[String] = []
	for entry_value: Variant in _recent_reflections:
		var entry: Dictionary = entry_value
		lines.append(
			Strings.LABELS["REFLECTION_LINE"] % [
				int(entry.get("tick", 0)),
				str(entry.get("summary", "")),
			],
		)
	return "\n".join(lines)


func _coalesce(value: Variant, fallback: String) -> String:
	if value == null:
		return fallback
	if value is String and value == "":
		return fallback
	return str(value)


func _on_agent_updated(agent_id: String, agent_state: Dictionary) -> void:
	# Slice γ — render the focused agent's relationship bonds. Auto-focus
	# mirrors ``_on_reasoning_trace_received`` so the panel becomes useful
	# even when the run only emits ``agent_update`` envelopes (e.g. before
	# the first reasoning_trace tick).
	# M7-ζ-1: register every agent we see into the selector so the researcher
	# can switch focus without clicking the avatar (live verification C4:
	# "ほかの agent たちの Reasoning パネルも見れるように").
	_register_agent_in_selector(agent_id)
	if _focused_agent == "":
		set_focused_agent(agent_id)
	if agent_id != _focused_agent:
		return
	# M7-ζ-2: agent_update always carries persona_id (it's a required field
	# on AgentState), so this is the more reliable resolver of the two —
	# the trace stream's persona_id is optional and only fires on ticks
	# where the LLM produced narrative fields.
	var persona_value: Variant = agent_state.get("persona_id")
	if persona_value != null and str(persona_value) != "":
		_apply_persona_to_title(agent_id, str(persona_value))
	var raw: Variant = agent_state.get("relationships", [])
	if not (raw is Array):
		return
	_relationships_label.text = _format_relationships(raw)


# ---- M7-ζ-1 selector helpers ----


func _register_agent_in_selector(agent_id: String) -> void:
	if agent_id == "" or _agent_selector == null:
		return
	if _known_agents.has(agent_id):
		return
	_known_agents.append(agent_id)
	_agent_selector.add_item(agent_id)
	if _agent_selector.disabled:
		_agent_selector.disabled = false
	# If the SelectionManager focused this agent before any update arrived,
	# the selector has been stuck on the placeholder. Sync it now.
	if agent_id == _focused_agent:
		_sync_selector_to_focus(agent_id)


func _on_agent_selector_item_selected(idx: int) -> void:
	if _syncing_selector:
		return
	# Item 0 is the placeholder ``SELECTOR_PROMPT``; agent items start at 1.
	if idx <= 0 or idx > _known_agents.size():
		return
	var agent_id := _known_agents[idx - 1]
	if agent_id == _focused_agent:
		return
	set_focused_agent(agent_id)


func _sync_selector_to_focus(agent_id: String) -> void:
	if _agent_selector == null:
		return
	var target_idx: int = 0
	if agent_id != "":
		var found := _known_agents.find(agent_id)
		if found >= 0:
			target_idx = found + 1
	if _agent_selector.selected == target_idx:
		return
	_syncing_selector = true
	_agent_selector.select(target_idx)
	_syncing_selector = false


func _format_relationships(bonds: Array) -> String:
	# Render the top 2 bonds as one line each. M7γ format was:
	#   ``<persona> affinity ±0.NN (N turns, last @ tick T)``
	# M7δ extends the trailing parenthetical with ``last in <zone>`` when
	# the bond carries a ``last_interaction_zone`` (the new bond field
	# added in C1). The full format is now:
	#   ``<persona> affinity ±0.NN (N turns, last in <zone> @ tick T)``
	# Falls back to the M7γ shape when the field is missing or null so
	# pre-δ replay logs / fixtures still render.
	#
	# Ranking key: ``|affinity|`` desc, ties broken by ``last_interaction_tick``
	# desc — the most affectively distinct bonds float to the top, matching
	# the researcher's observability priority (Slice γ design D5 / R4 +
	# Slice δ Axis 5).
	if bonds.is_empty():
		return Strings.LABELS["RELATIONSHIPS_NONE"]
	var ranked: Array = []
	for raw_bond: Variant in bonds:
		if not (raw_bond is Dictionary):
			continue
		var bond: Dictionary = raw_bond
		var other_id: String = str(bond.get("other_agent_id", ""))
		if other_id == "":
			continue
		var affinity: float = float(bond.get("affinity", 0.0))
		var turns: int = int(bond.get("ichigo_ichie_count", 0))
		var last_tick_value: Variant = bond.get("last_interaction_tick")
		var last_zone_value: Variant = bond.get("last_interaction_zone")
		var belief_kind_value: Variant = bond.get("latest_belief_kind")
		ranked.append({
			"other_id": other_id,
			"persona": _persona_from_agent_id(other_id),
			"affinity": affinity,
			"turns": turns,
			"last_tick": last_tick_value,
			"last_zone": last_zone_value,
			"belief_kind": belief_kind_value,
			"abs_affinity": abs(affinity),
		})
	if ranked.is_empty():
		return Strings.LABELS["RELATIONSHIPS_NONE"]
	ranked.sort_custom(_compare_relationship_rank)
	var lines: Array[String] = []
	for entry_value: Variant in ranked.slice(0, 2):
		var entry: Dictionary = entry_value
		var last_tick: Variant = entry.get("last_tick")
		var last_zone: Variant = entry.get("last_zone")
		var tail: String
		if last_tick != null:
			if last_zone != null and str(last_zone) != "":
				tail = Strings.LABELS["BOND_LAST_IN_ZONE"] % [str(last_zone), int(last_tick)]
			else:
				tail = Strings.LABELS["BOND_LAST_TICK"] % int(last_tick)
		else:
			tail = Strings.LABELS["BOND_NO_TICK"]
		# M7-ζ-2: prefix with the belief icon when the bond has been promoted
		# (RelationshipBond.latest_belief_kind set by apply_belief_promotion).
		# Pre-0.9.0-m7z bonds have ``null`` here and fall through to BOND_LINE
		# so old replay logs / fixtures still render.
		var belief_icon: String = _belief_icon(entry.get("belief_kind"))
		if belief_icon != "":
			lines.append(
				Strings.LABELS["BOND_LINE_WITH_BELIEF"] % [
					belief_icon,
					entry.get("persona", ""),
					entry.get("affinity", 0.0),
					entry.get("turns", 0),
					tail,
				]
			)
		else:
			lines.append(
				Strings.LABELS["BOND_LINE"] % [
					entry.get("persona", ""),
					entry.get("affinity", 0.0),
					entry.get("turns", 0),
					tail,
				]
			)
	return "\n".join(lines)


func _belief_icon(belief_kind: Variant) -> String:
	# Empty string when the bond has no belief promotion yet — the caller
	# falls back to the icon-less BOND_LINE in that case.
	if belief_kind == null:
		return ""
	var kind := str(belief_kind)
	if kind == "":
		return ""
	var key := "BELIEF_ICON_%s" % kind.to_upper()
	if Strings.LABELS.has(key):
		return Strings.LABELS[key]
	return ""


func _compare_relationship_rank(a: Dictionary, b: Dictionary) -> bool:
	var a_abs: float = float(a.get("abs_affinity", 0.0))
	var b_abs: float = float(b.get("abs_affinity", 0.0))
	if a_abs != b_abs:
		return a_abs > b_abs
	# Tie-break: most-recently interacted bond wins. ``null`` last_tick
	# (never interacted) sorts after any concrete tick.
	var a_tick: Variant = a.get("last_tick")
	var b_tick: Variant = b.get("last_tick")
	if a_tick == null and b_tick == null:
		return false
	if a_tick == null:
		return false
	if b_tick == null:
		return true
	return int(a_tick) > int(b_tick)


func _persona_from_agent_id(agent_id: String) -> String:
	# Agent IDs typically look like ``agent.kant.0001`` — surface only the
	# middle persona segment for the relationships block so the line stays
	# scannable. Falls back to the raw id when the dotted layout breaks.
	var parts := agent_id.split(".")
	if parts.size() >= 2 and parts[1] != "":
		return parts[1]
	return agent_id


# ---- 2026-04-28 godot-viewport-layout (v2.1, codex review) ----


func _build_header(parent: Node) -> void:
	# Header contains the collapse/expand toggle button. Lives outside
	# ``_body_container`` so it stays visible when the body is hidden
	# (codex HIGH-3 + LOW-6: button must not be added to the panel root).
	var header := HBoxContainer.new()
	header.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(header)

	_collapse_button = Button.new()
	_collapse_button.text = "▶"
	_collapse_button.tooltip_text = "Collapse / expand reasoning panel"
	_collapse_button.focus_mode = Control.FOCUS_NONE
	_collapse_button.pressed.connect(_toggle_collapse)
	header.add_child(_collapse_button)


func _toggle_collapse() -> void:
	# Two-stage collapse (codex HIGH-3): hide the body so the 60px-wide strip
	# does not show squashed labels, *and* shrink ``custom_minimum_size`` so
	# the parent ``HSplitContainer`` can actually narrow the panel that far.
	# Persistence (codex MEDIUM-5): expand restores the last user-dragged
	# splitter offset rather than the hard-coded default.
	_collapsed = not _collapsed
	if _body_container != null:
		_body_container.visible = not _collapsed
	if _collapse_button != null:
		_collapse_button.text = "◀" if _collapsed else "▶"
	var target_min_width := PANEL_COLLAPSED_WIDTH if _collapsed else PANEL_EXPANDED_WIDTH
	custom_minimum_size = Vector2(target_min_width, 0)
	if _split != null:
		var target_offset: int = -PANEL_COLLAPSED_WIDTH if _collapsed else _last_expanded_offset
		_apply_split_offset(target_offset)


func _on_split_dragged(offset: int) -> void:
	# Persist the splitter position only while expanded so the next collapse
	# round-trip restores the user's chosen width (codex MEDIUM-5).
	if not _collapsed:
		_last_expanded_offset = offset


func _apply_initial_split_offset() -> void:
	# Deferred from ``_ready`` so the parent ``HSplitContainer`` has had a
	# chance to compute ``dragger_positions`` before we clamp.
	if _split == null:
		return
	_apply_split_offset(_last_expanded_offset)


func _apply_split_offset(offset: int) -> void:
	# 2026-04-28 codex review HIGH-1 + code-reviewer HIGH: Godot 4.6 added
	# ``split_offsets`` (PackedInt32Array, one entry per dragger) as the
	# canonical replacement for the singular ``split_offset``. We try the
	# array form first so a future deprecation does not break us, and fall
	# back to ``split_offset`` for older runtimes (4.4/4.5) that ship in
	# CI / the user's developer machine. ``clamp_split_offset`` exists in
	# both API generations so it is always safe to call last.
	if _split == null:
		return
	if "split_offsets" in _split:
		_split.split_offsets = PackedInt32Array([offset])
	else:
		_split.split_offset = offset
	_split.clamp_split_offset()
