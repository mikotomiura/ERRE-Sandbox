## [1]. [HIGH] Schema bump plan misses real version consumers
- **Where**: design.md “Schema 層” / `godot_project/scripts/WebSocketClient.gd:28`
- **Problem**: The repo has `SCHEMA_VERSION`, not `_FROZEN_VERSION` or `SCHEMA_VERSION_HISTORY`, and Godot hard-codes `CLIENT_SCHEMA_VERSION`. With strict `HandshakeMsg` matching in `gateway.py`, bumping only Python will make live Godot reconnect fail.
- **Recommendation**: Update `SCHEMA_VERSION`, version docstring, all version-pinned tests/fixtures, and `CLIENT_SCHEMA_VERSION` in the same schema commit. Add a test that Godot’s client constant matches Python `SCHEMA_VERSION`.

## [2]. [HIGH] New nested model can silently escape `extra="forbid"` coverage
- **Where**: design.md “TriggerEventTag”; `src/erre_sandbox/schemas.py:835`
- **Problem**: Pydantic v2 defaults nested `BaseModel` extras to ignore unless `ConfigDict(extra="forbid")` is set. If `TriggerEventTag` is not exported via `__all__`, the existing public-model guard will not catch it.
- **Recommendation**: Define `model_config = ConfigDict(extra="forbid")`, add `TriggerEventTag` to `__all__`, and test unknown nested keys fail validation.

## [3]. [HIGH] Commit order cannot keep CI green
- **Where**: design.md “実装順序”
- **Problem**: Commit 1 changes schema shape/version but defers golden and envelope fixture rebake to commit 3. Existing `test_schema_contract.py` and `test_envelope_fixtures.py` will fail immediately.
- **Recommendation**: Move JSON schema golden regeneration, `fixtures/control_envelope/*.json`, version-pinned tests, and Godot client version into the schema commit, or drop the “each commit CI green” claim.

## [4]. [HIGH] Pulse signal is not synchronized to the focused panel agent
- **Where**: design.md “Godot 層”; `EnvelopeRouter.gd:91`, `ReasoningPanel.gd:294`
- **Problem**: `zone_pulse_requested(zone, tick)` lacks `agent_id`, while `ReasoningPanel` filters by `_focused_agent`. In 3-agent live runs, the world can pulse a zone for a non-focused trace while the panel displays another agent’s reasoning.
- **Recommendation**: Include `agent_id` and probably `kind` in the pulse signal, then gate pulses through the same focus/selection state as the panel, or explicitly design the pulse as global and label it that way.

## [5]. [HIGH] BoundaryLayer cannot pulse one zone with the current material model
- **Where**: `godot_project/scripts/BoundaryLayer.gd:92-175`
- **Problem**: All zone rectangles share `_material`; tweening `line_color` or material color will repaint every zone, not the selected zone. Overlapping tweens from 3 agents can also race on the same material.
- **Recommendation**: Redesign pulse state as per-zone color/material, or redraw the ImmediateMesh from a `{zone: color}` map. Track and kill/reuse one active tween per zone.

## [6]. [MEDIUM] `summary` is carrying too much API meaning
- **Where**: design.md “summary≤60chars”
- **Problem**: A free-text summary is not a stable event reference, and cognition-generated natural language couples backend logic to UI/i18n. LLM-derived text would also violate the stated scope.
- **Recommendation**: Add structured fields such as `ref_id`/`subject_id` plus deterministic `summary_key` or backend-generated terse text. Format localized display text in Godot `Strings.gd`.

## [7]. [MEDIUM] Non-spatial triggers may create false boundary pulses
- **Where**: design.md “EnvelopeRouter … trace.trigger_event.zone 非空”
- **Problem**: If temporal, biorhythm, speech, or internal triggers get `current_zone`, the BoundaryLayer will pulse a spatial boundary for an event that is not spatial. That weakens the meaning of “boundary observability.”
- **Recommendation**: Define per-kind zone semantics. Only emit pulse for `zone_transition`, `affordance`, and explicitly justified `proximity`; leave `zone=None` for non-spatial triggers.

## [8]. [MEDIUM] Simultaneous strong events are underspecified
- **Where**: design.md “リスク #3”
- **Problem**: The design says one trigger wins, then suggests compound summaries as a workaround, but does not define wire semantics for dropped strong events. `kind=zone_transition` with a summary mentioning biorhythm creates mismatched structured vs text meaning.
- **Recommendation**: Either keep strict single-winner semantics and document discarded candidates, or add `secondary_kinds`/`secondary_count` so the UI can signal “+N more” without overloading summary.

## [9]. [MEDIUM] Unicode and visual-width truncation are not solved by `max_length=60`
- **Where**: design.md “summary 上限 60 chars”; `ReasoningPanel.gd:211`
- **Problem**: Pydantic `max_length` counts string length, not 320px visual width; Japanese full-width text or emoji can still overflow. Naive Python/Godot slicing can also split grapheme clusters.
- **Recommendation**: Keep schema max length as validation only, and let Godot 4.4 handle one-line display with overrun ellipsis/clip settings. Add tests or fixture screenshots with Japanese text and emoji.

## [10]. [LOW] `unknown` and excluded event kinds need a sharper contract
- **Where**: design.md “trigger kind 8 種”; `cognition/cycle.py:544`
- **Problem**: The design excludes `erre_mode_shift` as having no source, but `cycle.py` creates `ERREModeShiftEvent` and appends it to observations. `unknown` is also not tied to a clear producer path.
- **Recommendation**: Decide explicitly: ignore mode-shift and perception, map them to their underlying trigger, or include them as first-class kinds. Remove `unknown` unless a producer can intentionally emit it.

VERDICT: BLOCK

There are multiple pre-implementation contract and runtime design issues that will cause handshake failures, CI breakage, or misleading multi-agent UI behavior. Fix the HIGH items before implementation; the MEDIUM items can be folded into `design-final.md` as tighter semantics and tests.