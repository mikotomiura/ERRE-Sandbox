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
}
