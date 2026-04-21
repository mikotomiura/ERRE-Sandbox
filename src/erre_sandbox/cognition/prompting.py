"""Pure string-building for the cognition cycle's LLM messages.

Split into three stages (persona-erre skill §ルール 3):

* ``_COMMON_PREFIX`` — shared across every agent / tick. Placed first so
  SGLang's RadixAttention (M7+) can reuse its KV cache across personas.
* ``build_system_prompt`` — persona-specific + current-state tail.
* ``build_user_prompt`` — observations + retrieved memories + the JSON
  response contract consumed by :func:`cognition.parse.parse_llm_plan`.

All three are side-effect-free and deterministic for a fixed input.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.memory import RankedMemory
    from erre_sandbox.schemas import AgentState, Observation, PersonaSpec


_COMMON_PREFIX: Final[str] = (
    "You are an autonomous agent living in ERRE-Sandbox, a 3D world with "
    "five zones (study / peripatos / chashitsu / agora / garden). Each tick "
    "represents ten seconds of wall-clock time. Respond in character, "
    "following the cognitive habits of the persona described below. "
    "The ``utterance`` field MUST be written in Japanese (日本語) so the "
    "researcher observing the 3D scene can read it at a glance — "
    "original-language key terms (Kant のドイツ語/ラテン語, Nietzsche の"
    "ドイツ語など) may appear parenthetically inside the Japanese sentence. "
    "Keep utterances under 80 Japanese characters."
)

RESPONSE_SCHEMA_HINT: Final[str] = (
    "Respond with a SINGLE JSON object matching this schema (all deltas in "
    "[-1.0, 1.0], importance_hint in [0.0, 1.0]; use null for optional fields "
    "you intentionally skip). The last three keys (salient / decision / "
    "next_intent) are the reasoning trace shown to the researcher observing "
    "you — keep each under 80 characters of natural Japanese and be honest "
    "about why you act; leave them null only if genuinely not applicable:\n"
    "{\n"
    '  "thought": "internal monologue",\n'
    '  "utterance": "speech bubble text or null",\n'
    '  "destination_zone": "study|peripatos|chashitsu|agora|garden|null",\n'
    '  "animation": "walk|idle|sit_seiza|bow|null",\n'
    '  "valence_delta": 0.0,\n'
    '  "arousal_delta": 0.0,\n'
    '  "motivation_delta": 0.0,\n'
    '  "importance_hint": 0.5,\n'
    '  "salient": "what you found most salient this tick or null",\n'
    '  "decision": "the one-sentence reason for your action or null",\n'
    '  "next_intent": "what you plan to do next or null"\n'
    "}\n"
    "Return ONLY the JSON object. No prose outside the braces."
)


def _format_habit_line(habit_description: str, flag: str) -> str:
    return f"- {habit_description} [{flag}]"


def _format_persona_block(persona: PersonaSpec) -> str:
    habits = "\n".join(
        _format_habit_line(h.description, h.flag.value)
        for h in persona.cognitive_habits
    )
    zones = ", ".join(z.value for z in persona.preferred_zones)
    return (
        f"Persona: {persona.display_name} ({persona.era}).\n"
        f"Preferred zones: {zones}.\n"
        f"Cognitive habits (fact / legend / speculative):\n{habits}"
    )


def _format_state_tail(agent: AgentState) -> str:
    zone = agent.position.zone.value
    erre_mode = agent.erre.name.value
    cog = agent.cognitive
    phy = agent.physical
    return (
        f"Current tick: {agent.tick}.\n"
        f"Location: {zone}. ERRE mode: {erre_mode}.\n"
        f"Physical — sleep_quality={phy.sleep_quality:.2f}, "
        f"physical_energy={phy.physical_energy:.2f}, "
        f"fatigue={phy.fatigue:.2f}, cognitive_load={phy.cognitive_load:.2f}.\n"
        f"Cognitive — valence={cog.valence:.2f}, arousal={cog.arousal:.2f}, "
        f"motivation={cog.motivation:.2f}, stress={cog.stress:.2f}."
    )


def build_system_prompt(persona: PersonaSpec, agent: AgentState) -> str:
    """Assemble the system prompt in three stages (common / persona / tail).

    Ordering is load-bearing: the common prefix comes first so downstream
    KV caches can share it across personas (MVP Ollama does not exploit
    this, but SGLang at M7 will).
    """
    return "\n\n".join(
        [
            _COMMON_PREFIX,
            _format_persona_block(persona),
            _format_state_tail(agent),
        ],
    )


def _one_line(text: str, limit: int = 160) -> str:
    single = " ".join(text.split())
    if len(single) <= limit:
        return single
    return single[: limit - 1] + "…"


def format_memories(memories: Sequence[RankedMemory], max_items: int = 8) -> str:
    """Render *memories* as a bullet list sorted by strength (high first)."""
    if not memories:
        return "(no relevant memories)"
    ranked = sorted(memories, key=lambda m: m.strength, reverse=True)[:max_items]
    lines: list[str] = []
    for m in ranked:
        kind = m.entry.kind.value
        body = _one_line(m.entry.content)
        lines.append(f"- [{kind} strength={m.strength:.2f}] {body}")
    return "\n".join(lines)


def _observation_line(obs: Observation) -> str:  # noqa: PLR0911 — discriminator dispatch
    if obs.event_type == "perception":
        return _one_line(
            f"[perception] {obs.content} (intensity={obs.intensity:.2f})",
        )
    if obs.event_type == "speech":
        return _one_line(f"[speech by {obs.speaker_id}] {obs.utterance}")
    if obs.event_type == "zone_transition":
        frm = obs.from_zone.value
        to = obs.to_zone.value
        return f"[zone_transition] {frm} -> {to}"
    if obs.event_type == "erre_mode_shift":
        prev = obs.previous.value
        curr = obs.current.value
        return f"[erre_mode_shift] {prev} -> {curr} ({obs.reason})"
    if obs.event_type == "internal":
        return _one_line(
            f"[internal hint={obs.importance_hint:.2f}] {obs.content}",
        )
    if obs.event_type == "affordance":
        return _one_line(
            f"[affordance] {obs.prop_kind}#{obs.prop_id} in {obs.zone.value} "
            f"(distance={obs.distance:.1f}m, salience={obs.salience:.2f})",
        )
    if obs.event_type == "proximity":
        return (
            f"[proximity {obs.crossing}] other={obs.other_agent_id} "
            f"{obs.distance_prev:.1f}m -> {obs.distance_now:.1f}m"
        )
    if obs.event_type == "temporal":
        return f"[temporal] {obs.period_prev.value} -> {obs.period_now.value}"
    if obs.event_type == "biorhythm":
        return (
            f"[biorhythm {obs.signal}:{obs.threshold_crossed}] "
            f"{obs.level_prev:.2f} -> {obs.level_now:.2f}"
        )
    return "[unknown] (unformatted)"


def build_user_prompt(
    observations: Sequence[Observation],
    memories: Sequence[RankedMemory],
    recent_limit: int = 5,
) -> str:
    """Build the user message: recent observations + memories + JSON contract."""
    recent = list(observations)[-recent_limit:]
    obs_block = (
        "\n".join(_observation_line(o) for o in recent)
        if recent
        else "(nothing happened)"
    )
    mem_block = format_memories(memories)
    return (
        "Recent observations:\n"
        f"{obs_block}\n\n"
        "Relevant memories:\n"
        f"{mem_block}\n\n"
        "Decide what to do in the next ten seconds.\n\n"
        f"{RESPONSE_SCHEMA_HINT}"
    )


__all__ = [
    "RESPONSE_SCHEMA_HINT",
    "build_system_prompt",
    "build_user_prompt",
    "format_memories",
]
