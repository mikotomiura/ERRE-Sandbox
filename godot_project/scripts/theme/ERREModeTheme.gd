# ERREModeTheme — M5 godot-zone-visuals
#
# Single source of truth for the eight ERRE-mode avatar tint colours. Kept as a
# const-only ``class_name`` rather than an autoload so ``project.godot`` stays
# untouched; consumers call ``ERREModeTheme.color_for(mode)`` statically.
#
# Static-only usage means the T16 judgement 4 concern (cross-ref TYPE
# annotations before the ``.godot/`` cache is populated) does not apply —
# ``static func`` resolution does not require the class_name to exist in the
# TYPE lattice at parse time.
#
# Palette rationale (M5 planning §judgement 5 / design.md §Godot 視覚化):
#   * peripatetic  — pale yellow  (sun / walking)
#   * chashitsu    — pale green   (tea-room / tatami)
#   * zazen        — pale blue    (meditation / breath)
#   * deep_work    — near-white   (intense focus)
#   * shallow      — neutral grey (low-engagement default)
#   * shu_kata     — pale brown   (守: tradition)
#   * ha_deviate   — pale orange  (破: breaking frame)
#   * ri_create    — pale purple  (離: original creation)
class_name ERREModeTheme
extends Object

const COLORS: Dictionary = {
	"peripatetic": Color(0.95, 0.90, 0.55),
	"chashitsu": Color(0.70, 0.88, 0.70),
	"zazen": Color(0.65, 0.75, 0.92),
	"deep_work": Color(0.98, 0.98, 0.98),
	"shallow": Color(0.62, 0.62, 0.62),
	"shu_kata": Color(0.80, 0.65, 0.48),
	"ha_deviate": Color(0.98, 0.72, 0.40),
	"ri_create": Color(0.82, 0.65, 0.92),
}

## White fallback for any unknown ERRE mode. Emits a warning so typos in the
## gateway-side ``agent_state.erre.name`` are surfaced during development
## without crashing the avatar.
const FALLBACK_COLOR: Color = Color(1.0, 1.0, 1.0)


static func color_for(mode: String) -> Color:
	if COLORS.has(mode):
		return COLORS[mode]
	push_warning("[ERREModeTheme] unknown mode=%s; falling back to white" % mode)
	return FALLBACK_COLOR
