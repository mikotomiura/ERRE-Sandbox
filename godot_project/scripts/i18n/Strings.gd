# Strings — UI locale dictionary (M7-ζ-1 Live Resonance).
#
# All ReasoningPanel / DebugOverlay user-facing strings live in a single
# const dict so the JP <-> EN swap (or future ``tr()`` migration) needs
# only one file edit. We do **not** introduce a Godot ``.csv``
# localisation pipeline because the live-resonance scope is ≤15 labels —
# translation tooling cost would dwarf it. When the project does adopt
# full i18n (post-M11), this dict becomes the seed for the locale CSV
# and consumer call-sites swap to ``tr()`` mechanically.
#
# Live-verification context: 2026-04-22 issue "LATEST REFLECTION 内の
# 文字が英語なので日本語に" — see
# ``.steering/20260426-m7-slice-zeta-live-resonance/requirement.md``
# §"軸 C の根本原因" C6.
extends RefCounted

const LABELS: Dictionary = {
	# Reasoning panel — section headers
	"SALIENT": "気づき",
	"DECISION": "判断",
	"NEXT_INTENT": "次の意図",
	"LATEST_REFLECTION": "最新の反省",
	"RELATIONSHIPS": "関係性",
	# Reasoning panel — title & status
	"PANEL_TITLE": "Reasoning Panel",
	"PANEL_TITLE_FOR_AGENT": "Reasoning Panel — %s",
	# ``PANEL_TITLE_FOR_AGENT_PERSONA`` is consumed in PR-ζ-2 once
	# ReasoningTrace.persona_id lands on the wire. Living here so the locale
	# dict stays the single source of truth across slices.
	"PANEL_TITLE_FOR_AGENT_PERSONA": "Reasoning Panel — %s (%s)",
	"AGENT_NONE": "(エージェント未選択)",
	"AGENT_WAITING": "(トレース待ち)",
	"AGENT_MODE_TICK": "モード: %s   |   tick: %d",
	# Reasoning panel — empty / fallback states
	"REFLECTION_NONE": "(まだなし)",
	"REFLECTION_EMPTY_SUMMARY": "(空の要約)",
	"RELATIONSHIPS_NONE": "(対話なし)",
	"VALUE_DASH": "—",
	# Agent selector
	"SELECTOR_PROMPT": "(エージェント選択)",
	# Reasoning panel — relationship bond formatting (M7-ζ-1 review M1).
	# ``BOND_LINE`` consumes ``[persona, affinity, ichigo_ichie_count, tail]``;
	# ``tail`` is one of ``BOND_LAST_IN_ZONE`` / ``BOND_LAST_TICK`` /
	# ``BOND_NO_TICK`` depending on which fields the bond carries.
	"BOND_LINE": "%s  親和度 %+.2f  (%d 回, %s)",
	"BOND_LAST_IN_ZONE": "前回 %s @ tick %d",
	"BOND_LAST_TICK": "前回 @ tick %d",
	"BOND_NO_TICK": "tick 履歴なし",
	# Persona content (M7-ζ-2). display_name + 1-line personality summary
	# kept client-side per Plan A judgment: avoids expanding the wire just
	# to carry static persona text. Lookup key shape: ``PERSONA_NAME_<id>``
	# (id upper-cased). Fall back to ``*_UNKNOWN`` when the trace arrives
	# from a persona this client release does not know about.
	"PERSONA_NAME_KANT": "Immanuel Kant",
	"PERSONA_SUMMARY_KANT": "勤勉・低神経症 — 規律のリズムが思考を貫く",
	"PERSONA_NAME_NIETZSCHE": "Friedrich Nietzsche",
	"PERSONA_SUMMARY_NIETZSCHE": "高エネルギー・突発バースト — 散策で思考が爆発する",
	"PERSONA_NAME_RIKYU": "千利休",
	"PERSONA_SUMMARY_RIKYU": "静謐・侘び寂び — 沈黙と所作に意味を宿す",
	"PERSONA_NAME_UNKNOWN": "(未知のペルソナ)",
	"PERSONA_SUMMARY_UNKNOWN": "—",
	# Belief icons (M7-ζ-2). Surfaced as a prefix on the bond row when
	# RelationshipBond.latest_belief_kind is non-null. Glyphs are universal
	# but kept here so the JP/EN flip can swap them out later.
	"BELIEF_ICON_TRUST": "◯",
	"BELIEF_ICON_CLASH": "✕",
	"BELIEF_ICON_WARY": "△",
	"BELIEF_ICON_CURIOUS": "？",
	"BELIEF_ICON_AMBIVALENT": "◇",
	# ``BOND_LINE_WITH_BELIEF`` consumes [icon, persona, affinity, turns, tail].
	"BOND_LINE_WITH_BELIEF": "%s %s  親和度 %+.2f  (%d 回, %s)",
	# Reflection list (M7-ζ-2). Up to last 3 reflections kept on screen,
	# newest first, so the researcher can read short reflection cadence
	# without opening the journal. ``REFLECTION_LINE`` consumes [tick, text].
	"REFLECTION_LINE": "tick %d: %s",
	# Trigger event tag (M9-A). Surfaces "this trace was triggered by X" as
	# a 1-line panel header above SALIENT, plus a violet zone pulse on the
	# BoundaryLayer when the trigger is spatial. ``TRIGGER`` is the section
	# header; the per-kind labels expose the discriminator vocabulary so the
	# eventual EN flip can rename them in one place.
	"TRIGGER": "気づきの起点",
	"TRIGGER_NONE": "—",
	# Trigger kind icons. Glyphs match the design-final.md mapping; the
	# panel composes "<icon> <kind label> @ <zone> (<ref>)" via
	# ``format_trigger`` below.
	"TRIGGER_ICON_ZONE_TRANSITION": "→",
	"TRIGGER_ICON_AFFORDANCE": "◇",
	"TRIGGER_ICON_PROXIMITY": "◯",
	"TRIGGER_ICON_TEMPORAL": "◔",
	"TRIGGER_ICON_BIORHYTHM": "♥",
	"TRIGGER_ICON_ERRE_MODE_SHIFT": "✦",
	"TRIGGER_ICON_INTERNAL": "✎",
	"TRIGGER_ICON_SPEECH": "💬",
	"TRIGGER_ICON_PERCEPTION": "👁",
	# Per-kind one-word JP labels for the panel inline text.
	"TRIGGER_KIND_ZONE_TRANSITION": "ゾーン移動",
	"TRIGGER_KIND_AFFORDANCE": "アフォーダンス",
	"TRIGGER_KIND_PROXIMITY": "接近",
	"TRIGGER_KIND_TEMPORAL": "時間帯",
	"TRIGGER_KIND_BIORHYTHM": "生体リズム",
	"TRIGGER_KIND_ERRE_MODE_SHIFT": "ERRE モード遷移",
	"TRIGGER_KIND_INTERNAL": "内的事象",
	"TRIGGER_KIND_SPEECH": "発話",
	"TRIGGER_KIND_PERCEPTION": "知覚",
	# Format strings for the panel trigger row. ``TRIGGER_LINE_WITH_REF``
	# consumes [icon, kind_label, zone_label, ref_id]; ``TRIGGER_LINE_NO_REF``
	# drops the trailing parens; ``TRIGGER_LINE_NO_ZONE`` is for non-spatial
	# kinds. Keep these short enough that the panel never wraps at 13pt /
	# 320px (~28 fullwidth chars).
	"TRIGGER_LINE_WITH_REF": "%s %s @ %s (%s)",
	"TRIGGER_LINE_NO_REF": "%s %s @ %s",
	"TRIGGER_LINE_NO_ZONE": "%s %s",
}


## Format a trigger event into the panel's 1-line display string (M9-A).
##
## Composes from (kind, zone, ref_id) — backend stays free of i18n. Falls
## back gracefully when zone or ref_id are empty, and the icon/label dicts
## return ``"?"`` for kinds the client release doesn't recognise (additive
## wire compatibility for future kinds).
static func format_trigger(kind: String, zone: String, ref_id: String) -> String:
	if kind.is_empty():
		return LABELS["TRIGGER_NONE"]
	var upper := kind.to_upper()
	var icon: String = LABELS.get("TRIGGER_ICON_%s" % upper, "?")
	var kind_label: String = LABELS.get("TRIGGER_KIND_%s" % upper, kind)
	if zone.is_empty():
		return LABELS["TRIGGER_LINE_NO_ZONE"] % [icon, kind_label]
	if ref_id.is_empty():
		return LABELS["TRIGGER_LINE_NO_REF"] % [icon, kind_label, zone]
	return LABELS["TRIGGER_LINE_WITH_REF"] % [icon, kind_label, zone, ref_id]
