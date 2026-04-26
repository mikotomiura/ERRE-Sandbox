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
# M7-ζ-1: multi-agent selector. ``_known_agents`` mirrors the OptionButton
# items 1..N (item 0 stays the placeholder) so SelectionManager click-focus
# and selector changes can sync without iterating the OptionButton each
# update. ``_syncing_selector`` is a re-entry guard so set_focused_agent →
# selector.select() does not re-trigger ``item_selected`` and recurse.
var _agent_selector: OptionButton
var _known_agents: Array[String] = []
var _syncing_selector: bool = false


func _ready() -> void:
	_build_tree()
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
	# M6-B-2b: MainScene now hosts the panel inside an ``HBoxContainer`` split,
	# so positioning is handled by the parent container. We only set the
	# minimum width here to stay defensive when the scene is reused in a
	# non-HBox context (e.g. the FixtureHarness or a future inspector mode).
	custom_minimum_size = Vector2(320, 0)

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

	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 10)
	margin.add_child(vbox)

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
	# Reflection events can arrive out of order after a reconnect; keep the
	# latest by tick so we never regress to an older summary.
	if tick < _last_reflection_tick:
		return
	_last_reflection_tick = tick
	_reflection_label.text = summary_text if summary_text != "" else Strings.LABELS["REFLECTION_EMPTY_SUMMARY"]


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
		ranked.append({
			"other_id": other_id,
			"persona": _persona_from_agent_id(other_id),
			"affinity": affinity,
			"turns": turns,
			"last_tick": last_tick_value,
			"last_zone": last_zone_value,
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
		lines.append(
			Strings.LABELS["BOND_LINE"] % [
				entry.get("persona", ""),
				entry.get("affinity", 0.0),
				entry.get("turns", 0),
				tail,
			]
		)
	return "\n".join(lines)


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
