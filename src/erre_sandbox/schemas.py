"""Pydantic v2 data contract for ERRE-Sandbox (T05 schemas-freeze).

This module is the Contract-First boundary between MacBook (orchestrator + Godot
viewer) and G-GEAR (inference + simulation + memory). It defines the wire types
exchanged over WebSocket and the in-memory representations shared across layers.

Sections
--------
* §1 Protocol constants
* §2 Enums
* §3 Persona (static, YAML-loaded) — incl. ``AgentSpec`` (M4)
* §4 AgentState (dynamic, per-tick)
* §5 Observation (event, discriminated by ``event_type``)
* §6 Memory — incl. ``ReflectionEvent`` / ``SemanticMemoryRecord`` (M4)
* §7 ControlEnvelope (message, discriminated by ``kind``) — incl. ``Dialog*`` variants (M4)
* §7.5 DialogScheduler (Protocol, M4 foundation — interface only)
* §8 Public surface (``__all__``)

Design choices are recorded in ``.steering/20260418-schemas-freeze/decisions.md``
(M2) and ``.steering/20260420-m4-contracts-freeze/decisions.md`` (M4 foundation).
This module MUST NOT import any other ``erre_sandbox.*`` module
(see ``docs/repository-structure.md`` §4 and the ``architecture-rules`` skill).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Final, Literal, Protocol, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# §1 Protocol constants
# =============================================================================

SCHEMA_VERSION: Final[str] = "0.2.0-m4"
"""Semantic version of the wire contract.

Bumped whenever any on-wire model gains or loses a field, or a discriminator
value is added/removed. Consumed by ``HandshakeMsg`` for early mismatch
detection between MacBook / G-GEAR / Godot peers.

M4 bump (0.1.0-m2 → 0.2.0-m4): adds the AgentSpec / ReflectionEvent /
SemanticMemoryRecord primitives and the dialog_initiate / dialog_turn /
dialog_close ControlEnvelope variants required by the 3-agent milestone.
See ``.steering/20260420-m4-contracts-freeze/`` for the rationale.
"""


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


# =============================================================================
# §2 Enums
# =============================================================================


class Zone(StrEnum):
    """Five spatial zones of the world (see ``docs/glossary.md``)."""

    STUDY = "study"
    PERIPATOS = "peripatos"
    CHASHITSU = "chashitsu"
    AGORA = "agora"
    GARDEN = "garden"


class ERREModeName(StrEnum):
    """Eight ERRE cognitive modes (see ``persona-erre`` skill for semantics)."""

    PERIPATETIC = "peripatetic"
    CHASHITSU = "chashitsu"
    ZAZEN = "zazen"
    SHU_KATA = "shu_kata"
    HA_DEVIATE = "ha_deviate"
    RI_CREATE = "ri_create"
    DEEP_WORK = "deep_work"
    SHALLOW = "shallow"


class MemoryKind(StrEnum):
    """Four memory faculties of the agent (CoALA-inspired)."""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    RELATIONAL = "relational"


class HabitFlag(StrEnum):
    """Epistemic status of a cognitive habit attributed to a historical figure."""

    FACT = "fact"
    LEGEND = "legend"
    SPECULATIVE = "speculative"


class ShuhariStage(StrEnum):
    """Three stages of skill acquisition in Japanese arts (shu-ha-ri)."""

    SHU = "shu"
    HA = "ha"
    RI = "ri"


class PlutchikDimension(StrEnum):
    """Plutchik's eight primary emotions."""

    JOY = "joy"
    TRUST = "trust"
    FEAR = "fear"
    SURPRISE = "surprise"
    SADNESS = "sadness"
    DISGUST = "disgust"
    ANGER = "anger"
    ANTICIPATION = "anticipation"


# Convenience float ranges used repeatedly below.
_Unit = Annotated[float, Field(ge=0.0, le=1.0)]
_Signed = Annotated[float, Field(ge=-1.0, le=1.0)]


# =============================================================================
# §3 Persona (static, YAML-loaded)
# =============================================================================


class CognitiveHabit(BaseModel):
    """One recurring cognitive-behavioural pattern of a historical figure."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(..., description="Concrete habit, present tense.")
    source: str = Field(..., description="Citation key, e.g. 'kuehn2001'.")
    flag: HabitFlag = Field(..., description="fact / legend / speculative.")
    mechanism: str = Field(
        ...,
        description="Cognitive-neuroscience mechanism hypothesised to underlie it.",
    )
    trigger_zone: Zone | None = Field(
        default=None,
        description="Zone that typically activates this habit, if any.",
    )


class PersonalityTraits(BaseModel):
    """Static personality: Big Five + ERRE-specific Japanese aesthetic traits."""

    model_config = ConfigDict(extra="forbid")

    # Big Five (all [0, 1]).
    openness: _Unit = 0.5
    conscientiousness: _Unit = 0.5
    extraversion: _Unit = 0.5
    agreeableness: _Unit = 0.5
    neuroticism: _Unit = 0.5
    # ERRE-specific (docs/glossary.md).
    wabi: _Unit = Field(default=0.5, description="Acceptance of imperfection.")
    ma_sense: _Unit = Field(default=0.5, description="Tolerance of silence.")


class SamplingBase(BaseModel):
    """Absolute sampling parameters used as the persona's baseline."""

    model_config = ConfigDict(extra="forbid")

    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: _Unit = 0.9
    repeat_penalty: float = Field(default=1.0, ge=0.5, le=2.0)


class SamplingDelta(BaseModel):
    """Additive overrides applied on top of ``SamplingBase`` per ERRE mode.

    All fields default to ``0.0`` meaning "no override". The ``persona-erre``
    skill tabulates the canonical deltas per mode. Composition
    (``base + delta``) is the caller's responsibility; T11 / T12 must clamp
    the result back into ``SamplingBase``'s valid ranges.
    """

    model_config = ConfigDict(extra="forbid")

    temperature: float = Field(default=0.0, ge=-1.0, le=1.0)
    top_p: float = Field(default=0.0, ge=-1.0, le=1.0)
    repeat_penalty: float = Field(default=0.0, ge=-1.0, le=1.0)


class PersonaSpec(BaseModel):
    """Root schema for a persona YAML (one file per historical figure)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    persona_id: str = Field(..., description="kebab-case id, e.g. 'kant'.")
    display_name: str
    era: str = Field(..., description="Dates, e.g. '1724-1804'.")
    primary_corpus_refs: list[str] = Field(default_factory=list)
    personality: PersonalityTraits
    cognitive_habits: list[CognitiveHabit]
    preferred_zones: list[Zone]
    default_sampling: SamplingBase = Field(default_factory=SamplingBase)


class AgentSpec(BaseModel):
    """Boot-time minimal agent declaration (M4 foundation).

    Carries only the two values the composition root needs to instantiate an
    agent at startup: which persona YAML to load and where on the map to spawn
    it. Joined with :class:`PersonaSpec` (by ``persona_id``) and expanded into a
    full :class:`AgentState` by ``m4-multi-agent-orchestrator``.
    """

    model_config = ConfigDict(extra="forbid")

    persona_id: str = Field(
        ...,
        description="Must match a ``PersonaSpec.persona_id`` loaded from YAML.",
    )
    initial_zone: Zone


# =============================================================================
# §4 AgentState (dynamic, per-tick)
# =============================================================================


class Position(BaseModel):
    """3D position within the world, annotated with the containing zone."""

    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    z: float
    zone: Zone
    yaw: float = Field(default=0.0, description="Facing angle in radians.")
    pitch: float = Field(default=0.0, description="Head tilt in radians (bow, gaze).")


class Physical(BaseModel):
    """Long-timescale somatic state (CSDG HumanCondition adopted as skeleton).

    All fields move on a daily / half-life scale. Instantaneous affect lives in
    :class:`Cognitive` (``valence`` / ``arousal``) instead.
    """

    model_config = ConfigDict(extra="forbid")

    sleep_quality: _Unit = 0.7
    physical_energy: _Unit = 0.7
    mood_baseline: _Signed = 0.0
    cognitive_load: _Unit = 0.2
    emotional_conflict: _Unit = 0.0
    fatigue: _Unit = 0.0
    hunger: _Unit = 0.0
    breath_rate: _Unit = Field(
        default=0.25,
        description="Normalised respiration; varies during walk / zazen.",
    )


class Cognitive(BaseModel):
    """Short-timescale mental state (tick-level)."""

    model_config = ConfigDict(extra="forbid")

    # Russell circumplex (immediate affect).
    valence: _Signed = 0.0
    arousal: _Signed = 0.0
    # Plutchik dominant emotion, if any.
    dominant_emotion: PlutchikDimension | None = None
    # CSDG CharacterState-inspired drives.
    motivation: _Unit = 0.5
    stress: _Unit = 0.0
    curiosity: _Unit = 0.5
    # ERRE-specific cognitive facets.
    shuhari_stage: ShuhariStage = ShuhariStage.SHU
    dmn_activation: _Unit = Field(
        default=0.3,
        description="Default Mode Network activation proxy.",
    )
    active_goals: list[str] = Field(
        default_factory=list,
        max_length=10,
        description=(
            "Free-form short goal strings; promoted to a structured Goal type "
            "in M4 (this is a planned breaking change)."
        ),
    )


class ERREMode(BaseModel):
    """The agent's current ERRE mode with its sampling overrides."""

    model_config = ConfigDict(extra="forbid")

    name: ERREModeName
    dmn_bias: _Signed = 0.0
    sampling_overrides: SamplingDelta = Field(default_factory=SamplingDelta)
    entered_at_tick: int = Field(..., ge=0)
    zone_trigger: Zone | None = None


class RelationshipBond(BaseModel):
    """Per-other-agent relational state."""

    model_config = ConfigDict(extra="forbid")

    other_agent_id: str
    affinity: _Signed = 0.0
    familiarity: _Unit = 0.0
    ichigo_ichie_count: int = Field(default=0, ge=0)
    last_interaction_tick: int | None = Field(default=None, ge=0)


class AgentState(BaseModel):
    """Snapshot of an agent at a given tick.

    Static persona information (traits, cognitive habits) lives in
    :class:`PersonaSpec` and is joined at read time via ``persona_id``.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    agent_id: str
    persona_id: str
    tick: int = Field(..., ge=0)
    wall_clock: datetime = Field(default_factory=_utc_now)
    position: Position
    physical: Physical = Field(default_factory=Physical)
    cognitive: Cognitive = Field(default_factory=Cognitive)
    erre: ERREMode
    relationships: list[RelationshipBond] = Field(default_factory=list)


# =============================================================================
# §5 Observation (discriminated by ``event_type``)
# =============================================================================


class _ObservationBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tick: int = Field(..., ge=0)
    agent_id: str = Field(..., description="The observing agent.")
    wall_clock: datetime = Field(default_factory=_utc_now)


class PerceptionEvent(_ObservationBase):
    """Something the agent sees / hears / smells / feels."""

    event_type: Literal["perception"] = "perception"
    modality: Literal["sight", "sound", "smell", "touch", "proprioception"]
    source_agent_id: str | None = Field(
        default=None,
        description=(
            "``None`` when the source is environmental (weather, ambient sound, etc.)."
        ),
    )
    source_zone: Zone
    content: str
    intensity: _Unit = 0.5


class SpeechEvent(_ObservationBase):
    """An utterance heard (or spoken) by the agent."""

    event_type: Literal["speech"] = "speech"
    speaker_id: str
    utterance: str
    emotional_impact: _Signed = 0.0


class ZoneTransitionEvent(_ObservationBase):
    """The agent moved from one zone to another."""

    event_type: Literal["zone_transition"] = "zone_transition"
    from_zone: Zone
    to_zone: Zone


class ERREModeShiftEvent(_ObservationBase):
    """The agent's ERRE mode changed."""

    event_type: Literal["erre_mode_shift"] = "erre_mode_shift"
    previous: ERREModeName
    current: ERREModeName
    reason: Literal["scheduled", "zone", "fatigue", "external", "reflection"]


class InternalEvent(_ObservationBase):
    """A self-generated reflective prompt (peripatos / chashitsu entry etc.)."""

    event_type: Literal["internal"] = "internal"
    content: str
    importance_hint: _Unit = 0.5


Observation: TypeAlias = Annotated[
    PerceptionEvent
    | SpeechEvent
    | ZoneTransitionEvent
    | ERREModeShiftEvent
    | InternalEvent,
    Field(discriminator="event_type"),
]
"""Discriminated union of all observation event types."""


# =============================================================================
# §6 Memory
# =============================================================================


class MemoryEntry(BaseModel):
    """A single memory row in the agent's Memory Stream.

    Pure domain type: embedding vectors and search scores are the memory-store
    layer's concern (T10) and intentionally absent here so backends can be
    swapped (sqlite-vec → Qdrant) without breaking the wire contract.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    agent_id: str
    kind: MemoryKind
    content: str
    importance: _Unit
    created_at: datetime = Field(default_factory=_utc_now)
    last_recalled_at: datetime | None = None
    recall_count: int = Field(default=0, ge=0)
    source_observation_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class ReflectionEvent(BaseModel):
    """Snapshot of one reflection step (M4 foundation).

    The cognition cycle distils a window of recent episodic entries into a
    single summary at reflection-trigger time. This struct is the on-wire /
    in-process record of that event, independent of both the trigger policy
    (decided in ``m4-cognition-reflection``) and the semantic-memory storage
    backend (decided in ``m4-memory-semantic-layer``).
    """

    model_config = ConfigDict(extra="forbid")

    agent_id: str
    tick: int = Field(..., ge=0)
    summary_text: str = Field(
        ...,
        description="LLM-distilled reflection content; UTF-8, not length-capped here.",
    )
    src_episodic_ids: list[str] = Field(
        default_factory=list,
        description="Source ``MemoryEntry.id`` values folded into the summary.",
    )
    created_at: datetime = Field(default_factory=_utc_now)


class SemanticMemoryRecord(BaseModel):
    """Long-term semantic memory row distilled from reflection (M4 foundation).

    Minimal shape: the sqlite-vec schema (index configuration, embedding
    dimensionality, composite keys) is deferred to
    ``m4-memory-semantic-layer``. ``embedding`` is permitted to be empty so
    fixture files and unit tests can roundtrip without shipping a real vector.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    agent_id: str
    embedding: list[float] = Field(
        default_factory=list,
        description=(
            "Row-level vector. Expected non-empty at runtime; empty allowed for "
            "fixture payloads so contract tests do not pin a particular dim."
        ),
    )
    # TODO(m4-memory-semantic-layer): pin embedding dimensionality once the
    # sqlite-vec index schema chooses between multilingual-e5-small (384) and
    # ruri-v3-30m (256); add field_validator to reject wrong-length vectors.
    summary: str
    origin_reflection_id: str | None = Field(
        default=None,
        description="``ReflectionEvent`` this row was distilled from, if any.",
    )
    created_at: datetime = Field(default_factory=_utc_now)


# =============================================================================
# §7 ControlEnvelope (discriminated by ``kind``)
# =============================================================================


class _EnvelopeBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    tick: int = Field(..., ge=0)
    sent_at: datetime = Field(default_factory=_utc_now)


class HandshakeMsg(_EnvelopeBase):
    """First message exchanged on a new WebSocket connection."""

    kind: Literal["handshake"] = "handshake"
    peer: Literal["g-gear", "macbook", "godot"]
    capabilities: list[str] = Field(default_factory=list)


class AgentUpdateMsg(_EnvelopeBase):
    """Bulk snapshot of an agent (G-GEAR → MacBook)."""

    kind: Literal["agent_update"] = "agent_update"
    agent_state: AgentState


class SpeechMsg(_EnvelopeBase):
    """An agent uttered something (G-GEAR → MacBook → Godot speech bubble)."""

    kind: Literal["speech"] = "speech"
    agent_id: str
    utterance: str
    zone: Zone
    emotion: PlutchikDimension | None = None


class MoveMsg(_EnvelopeBase):
    """Locomotion intent for an agent (G-GEAR → MacBook → Godot nav)."""

    kind: Literal["move"] = "move"
    agent_id: str
    target: Position
    speed: float = Field(..., ge=0.0, description="Metres per second.")


class AnimationMsg(_EnvelopeBase):
    """Animation state change (walk / idle / sit_seiza / bow …)."""

    kind: Literal["animation"] = "animation"
    agent_id: str
    animation_name: str
    loop: bool = False


class WorldTickMsg(_EnvelopeBase):
    """Global clock pulse (G-GEAR → MacBook, heartbeat)."""

    kind: Literal["world_tick"] = "world_tick"
    wall_clock: datetime = Field(default_factory=_utc_now)
    active_agents: int = Field(..., ge=0)


class ErrorMsg(_EnvelopeBase):
    """Structured error for observability."""

    kind: Literal["error"] = "error"
    code: str
    detail: str


class DialogInitiateMsg(_EnvelopeBase):
    """An agent requests to start a dialog with another agent (M4 foundation).

    The scheduler decides whether to admit the request (backpressure, zone
    constraints, existing dialog state). Admission logic lives in
    ``m4-multi-agent-orchestrator``; this envelope only captures the intent.
    """

    kind: Literal["dialog_initiate"] = "dialog_initiate"
    initiator_agent_id: str
    target_agent_id: str
    zone: Zone


class DialogTurnMsg(_EnvelopeBase):
    """A single turn inside an ongoing dialog (M4 foundation).

    ``speaker_id`` and ``addressee_id`` are both carried so Godot can drive
    the correct animations (speech bubble / head-turn) without re-deriving
    orientation from world state.
    """

    kind: Literal["dialog_turn"] = "dialog_turn"
    dialog_id: str
    speaker_id: str
    addressee_id: str
    utterance: str


class DialogCloseMsg(_EnvelopeBase):
    """A dialog has ended (M4 foundation).

    ``reason`` is a closed literal set so the gateway and the scheduler can
    dispatch on it without string matching.
    """

    kind: Literal["dialog_close"] = "dialog_close"
    dialog_id: str
    reason: Literal["completed", "interrupted", "timeout"]


ControlEnvelope: TypeAlias = Annotated[
    HandshakeMsg
    | AgentUpdateMsg
    | SpeechMsg
    | MoveMsg
    | AnimationMsg
    | WorldTickMsg
    | ErrorMsg
    | DialogInitiateMsg
    | DialogTurnMsg
    | DialogCloseMsg,
    Field(discriminator="kind"),
]
"""Discriminated union of all WebSocket envelope kinds."""


# =============================================================================
# §7.5 DialogScheduler (interface only, M4 foundation)
# =============================================================================


class DialogScheduler(Protocol):
    """Interface for agent-to-agent dialog orchestration (M4 foundation).

    Contract-only: the concrete turn-taking policy, backpressure, and timeout
    handling is the responsibility of ``m4-multi-agent-orchestrator``. This
    Protocol is frozen here so that ``cognition`` and ``world`` can type-hint
    against it in parallel tasks without waiting for the implementation.

    Methods return envelope messages (or ``None``) so the gateway can
    broadcast them over WebSocket without an additional marshalling layer.
    """

    def schedule_initiate(
        self,
        initiator_id: str,
        target_id: str,
        zone: Zone,
        tick: int,
    ) -> DialogInitiateMsg | None:
        """Decide whether to admit a new dialog and emit the initiate envelope.

        ``None`` means the scheduler rejected the request (e.g. existing
        dialog, cooldown, zone mismatch). Non-``None`` is the envelope to
        broadcast.
        """
        ...

    def record_turn(self, turn: DialogTurnMsg) -> None:
        """Record a turn in the dialog's transcript for later close/replay."""
        ...

    def close_dialog(
        self,
        dialog_id: str,
        reason: Literal["completed", "interrupted", "timeout"],
    ) -> DialogCloseMsg:
        """Close an open dialog and emit the close envelope."""
        ...


# =============================================================================
# §8 Public surface
# =============================================================================

__all__ = [
    "SCHEMA_VERSION",
    "AgentSpec",
    "AgentState",
    "AgentUpdateMsg",
    "AnimationMsg",
    "Cognitive",
    "CognitiveHabit",
    "ControlEnvelope",
    "DialogCloseMsg",
    "DialogInitiateMsg",
    "DialogScheduler",
    "DialogTurnMsg",
    "ERREMode",
    "ERREModeName",
    "ERREModeShiftEvent",
    "ErrorMsg",
    "HabitFlag",
    "HandshakeMsg",
    "InternalEvent",
    "MemoryEntry",
    "MemoryKind",
    "MoveMsg",
    "Observation",
    "PerceptionEvent",
    "PersonaSpec",
    "PersonalityTraits",
    "Physical",
    "PlutchikDimension",
    "Position",
    "ReflectionEvent",
    "RelationshipBond",
    "SamplingBase",
    "SamplingDelta",
    "SemanticMemoryRecord",
    "ShuhariStage",
    "SpeechEvent",
    "SpeechMsg",
    "WorldTickMsg",
    "Zone",
    "ZoneTransitionEvent",
]
