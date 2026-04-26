"""Composition root for the ERRE-Sandbox 1-Kant walker orchestrator.

This module is the sole wiring point between the contract-level gateway
(``integration.gateway``) and the real ``WorldRuntime`` + cognition +
memory + inference stack. It closes GAP-1 (`_NullRuntime` dependency) so
that MASTER-PLAN §4.4 MVP functional criteria can be PASS'd.

Design rationale: see ``.steering/20260419-m2-functional-closure/design.md``.
The hybrid approach keeps composition in a single module (testable via
:func:`bootstrap`) while the CLI shell lives in ``__main__.py``.
"""

from __future__ import annotations

import asyncio
import logging
import re
import signal
import sqlite3
import uuid
from contextlib import AsyncExitStack, suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast

import uvicorn
import yaml

from erre_sandbox.cognition import BiasFiredEvent, CognitionCycle
from erre_sandbox.cognition.relational import compute_affinity_delta
from erre_sandbox.erre import ZONE_TO_DEFAULT_ERRE_MODE, DefaultERREModePolicy
from erre_sandbox.inference import OllamaChatClient
from erre_sandbox.integration.dialog import InMemoryDialogScheduler
from erre_sandbox.integration.dialog_turn import OllamaDialogTurnGenerator
from erre_sandbox.integration.gateway import make_app
from erre_sandbox.memory import EmbeddingClient, MemoryStore, Retriever
from erre_sandbox.schemas import (
    AgentSpec,
    AgentState,
    DialogTurnMsg,
    ERREMode,
    ERREModeName,
    MemoryEntry,
    MemoryKind,
    PersonaSpec,
    Position,
    Zone,
)
from erre_sandbox.world import WorldRuntime

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BootConfig:
    """Immutable orchestrator configuration.

    Instantiated once by ``__main__.cli`` from argparse, then passed into
    :func:`bootstrap`. Kept frozen so tests cannot mutate it across awaits.

    ``agents`` is the M4-foundation extension: an empty tuple keeps the
    M2 single-Kant flow working unchanged. N-agent boot wiring is the
    responsibility of ``m4-multi-agent-orchestrator``.
    """

    host: str = "0.0.0.0"  # noqa: S104 — LAN only by design
    port: int = 8000
    db_path: str = "var/kant.db"
    chat_model: str = "qwen3:8b"
    embed_model: str = "nomic-embed-text"
    ollama_url: str = "http://127.0.0.1:11434"
    check_ollama: bool = True
    log_level: str = "info"
    personas_dir: Path = field(default_factory=lambda: Path("personas"))
    agents: tuple[AgentSpec, ...] = ()

    def __post_init__(self) -> None:
        """Fill ``agents`` with the 1-Kant default when the caller omitted it.

        Keeping the default inside the config (rather than branching inside
        :func:`bootstrap`) means the orchestrator body stays a single
        ``for spec in cfg.agents`` loop and both CI and live paths exercise
        the same code. ``object.__setattr__`` is the idiomatic escape hatch
        for mutating a ``frozen=True`` dataclass during init.
        """
        if not self.agents:
            default = (AgentSpec(persona_id="kant", initial_zone=Zone.PERIPATOS),)
            object.__setattr__(self, "agents", default)


_PERSONA_ID_RE: Final[re.Pattern[str]] = re.compile(r"\A[a-z][a-z0-9_-]{0,63}\Z")
"""Path-traversal guard for ``persona_id``; mirrors the CLI-side regex."""


def _load_persona_yaml(personas_dir: Path, persona_id: str) -> PersonaSpec:
    """Load ``personas/<persona_id>.yaml`` into a :class:`PersonaSpec`.

    Raises ``FileNotFoundError`` with a friendly message when the file is
    absent — orchestrator startup fails loudly rather than surfacing an
    opaque stack trace several levels deep.

    ``persona_id`` is validated against :data:`_PERSONA_ID_RE` so that the
    derived path cannot escape ``personas_dir`` (defence in depth: the CLI
    already validates, but callers could construct :class:`BootConfig`
    programmatically).
    """
    if not _PERSONA_ID_RE.fullmatch(persona_id):
        msg = (
            f"persona_id {persona_id!r} is not a safe YAML filename "
            f"(required: {_PERSONA_ID_RE.pattern})"
        )
        raise ValueError(msg)
    path = personas_dir / f"{persona_id}.yaml"
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Persona YAML not found at {path!s}. "
            "Check cwd or pass --personas-dir pointing at the repository's "
            "personas/ directory.",
        ) from exc
    data = yaml.safe_load(raw)
    return PersonaSpec.model_validate(data)


def _load_persona_registry(cfg: BootConfig) -> dict[str, PersonaSpec]:
    """Load every persona referenced by ``cfg.agents`` into a ``{id: spec}`` dict.

    The dict is passed to :class:`OllamaDialogTurnGenerator` so the generator
    can resolve the addressee's ``display_name`` when building prompts
    (see ``.steering/20260421-m5-dialog-turn-generator/decisions.md`` §4).
    Duplicate ``persona_id`` entries in ``cfg.agents`` collapse to a single
    registry entry — the registry is keyed by id, not by agent instance.

    The same YAML will be re-read in ``bootstrap()``'s agent registration
    loop, but that is intentional: personas are tiny (<10 KB) and the two
    reads live in different phases (bootstrap wiring vs. per-agent init).
    The dedup happens here so the registration loop can stay a simple
    ``for spec in cfg.agents`` without caring about duplicates.
    """
    registry: dict[str, PersonaSpec] = {}
    for spec in cfg.agents:
        if spec.persona_id in registry:
            continue
        registry[spec.persona_id] = _load_persona_yaml(
            cfg.personas_dir,
            spec.persona_id,
        )
    return registry


def _build_initial_state(spec: AgentSpec, persona: PersonaSpec) -> AgentState:
    """Expand an :class:`AgentSpec` into the initial :class:`AgentState`.

    ``agent_id`` is derived as ``a_<persona_id>_001``. A future milestone
    can make this CLI-configurable if we need multiple instances of the
    same persona (unlikely for M4).

    Destination is set on the first cognition tick (10s after launch); until
    then the avatar stands still. This is acceptable for MVP — MASTER-PLAN
    §4.4 #4 requires 30Hz rendering, and WorldTickMsg heartbeats emit at 1Hz
    while physics ticks update ``position`` at 30Hz once the agent has a plan.

    ``ZONE_TO_DEFAULT_ERRE_MODE`` is owned by :mod:`erre_sandbox.erre` as of
    M5; this composition root only picks the spawn-time default. Subsequent
    transitions are driven by :class:`~erre_sandbox.erre.DefaultERREModePolicy`
    once the world-zone trigger sub-task wires it into the tick loop.
    """
    _ = persona  # future hook: persona-specific spawn biases
    agent_id = f"a_{spec.persona_id}_001"
    erre_name = ZONE_TO_DEFAULT_ERRE_MODE.get(
        spec.initial_zone,
        ERREModeName.DEEP_WORK,
    )
    return AgentState(
        agent_id=agent_id,
        persona_id=spec.persona_id,
        tick=0,
        position=Position(x=0.0, y=0.0, z=0.0, zone=spec.initial_zone),
        erre=ERREMode(name=erre_name, entered_at_tick=0),
    )


def _make_relational_sink(
    *,
    runtime: WorldRuntime,
    memory: MemoryStore,
    persona_registry: dict[str, PersonaSpec],
) -> Callable[[DialogTurnMsg], None]:
    """Build the M7γ per-turn relational-hook sink.

    Returned callable runs synchronously from
    :class:`InMemoryDialogScheduler.record_turn`: it inserts a
    :class:`MemoryEntry` of kind ``RELATIONAL`` for the speaker and applies
    a :func:`compute_affinity_delta` adjustment to *both* sides'
    :class:`RelationshipBond.affinity` so the dialog turn shows up
    symmetrically in agent state.

    Sink failures are swallowed inside ``record_turn`` (see
    ``integration/dialog.py:197``); we log warnings here so operators can
    still see them in the journal, but never raise.
    """

    def _persist_relational_event(turn: DialogTurnMsg) -> None:
        speaker_persona_id = runtime.agent_persona_id(turn.speaker_id)
        speaker_persona = (
            persona_registry.get(speaker_persona_id)
            if speaker_persona_id is not None
            else None
        )
        if speaker_persona is None:
            logger.warning(
                "[bootstrap] relational sink skipped: unresolved speaker "
                "persona for dialog_id=%s speaker=%s",
                turn.dialog_id,
                turn.speaker_id,
            )
            return
        addressee_persona_id = runtime.agent_persona_id(turn.addressee_id)
        addressee_persona = (
            persona_registry.get(addressee_persona_id)
            if addressee_persona_id is not None
            else None
        )
        # M7δ: each side computes its own delta from its own ``prev``
        # (RelationshipBond.affinity at this instant) and from the
        # respective perspective. The semi-formula is asymmetric in
        # ``persona`` (decay/weight follow the perspective-holder's traits)
        # so we cannot share a single delta across sides as M7γ did.
        speaker_prev = runtime.get_bond_affinity(turn.speaker_id, turn.addressee_id)
        delta_speaker = compute_affinity_delta(
            turn,
            recent_transcript=(),
            persona=speaker_persona,
            prev=speaker_prev,
            addressee_persona=addressee_persona,
        )
        if addressee_persona is not None:
            addressee_prev = runtime.get_bond_affinity(
                turn.addressee_id,
                turn.speaker_id,
            )
            delta_addressee = compute_affinity_delta(
                turn,
                recent_transcript=(),
                persona=addressee_persona,
                prev=addressee_prev,
                addressee_persona=speaker_persona,
            )
        else:
            # Defensive: addressee persona unresolved → fall back to the
            # speaker-side delta to keep the bidirectional contract.
            delta_addressee = delta_speaker
        relational_entry = MemoryEntry(
            id=str(uuid.uuid4()),
            agent_id=turn.speaker_id,
            kind=MemoryKind.RELATIONAL,
            content=f"Spoke to {turn.addressee_id}: {turn.utterance}",
            importance=0.5,
            tags=[
                f"dialog:{turn.dialog_id}",
                f"addressee:{turn.addressee_id}",
                f"turn_index:{turn.turn_index}",
            ],
        )
        try:
            memory._add_sync(relational_entry, None)  # noqa: SLF001 — internal sync hook
        except sqlite3.OperationalError as exc:
            logger.warning(
                "[bootstrap] relational memory INSERT failed for "
                "dialog_id=%s tick=%d: %s",
                turn.dialog_id,
                turn.tick,
                exc,
            )
            return
        # Bidirectional bond mutation: each side feels the dialog turn
        # through its own perspective-derived delta.
        runtime.apply_affinity_delta(
            agent_id=turn.speaker_id,
            other_agent_id=turn.addressee_id,
            delta=delta_speaker,
            tick=turn.tick,
        )
        runtime.apply_affinity_delta(
            agent_id=turn.addressee_id,
            other_agent_id=turn.speaker_id,
            delta=delta_addressee,
            tick=turn.tick,
        )

    return _persist_relational_event


async def bootstrap(cfg: BootConfig) -> None:  # noqa: PLR0915 — composition root inherently long
    """Construct the full stack and supervise runtime + uvicorn.

    Resource lifecycle is structured via :class:`AsyncExitStack` so any
    exception during construction (or later during ``TaskGroup``) still
    invokes every ``close`` in LIFO order. OS signals (SIGINT / SIGTERM) are
    caught explicitly; without this the ``uvicorn.Server`` default handler
    intercepts Ctrl-C but the ``WorldRuntime`` task keeps running, which is
    the class of silent failure that T19 spent hours debugging.
    """
    logging.basicConfig(
        level=cfg.log_level.upper(),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        # force=True なので、既に handler が登録済 (e.g. pytest caplog) でも
        # bootstrap 呼び出しで root ロガー設定を上書きする。
        force=True,
    )

    async with AsyncExitStack() as stack:
        memory = MemoryStore(db_path=cfg.db_path)
        # Ensure the sqlite schema exists before any cognition tick runs. Without this
        # the first `Retriever.retrieve(...)` call raises
        # `sqlite3.OperationalError: no such table: episodic_memory`. `create_schema`
        # uses `CREATE TABLE IF NOT EXISTS`, so it is safe to call on every startup.
        memory.create_schema()
        stack.push_async_callback(memory.close)

        embedding = EmbeddingClient(model=cfg.embed_model, endpoint=cfg.ollama_url)
        stack.push_async_callback(embedding.close)

        inference = OllamaChatClient(model=cfg.chat_model, endpoint=cfg.ollama_url)
        stack.push_async_callback(inference.close)

        if cfg.check_ollama:
            logger.info(
                "[bootstrap] health_check %s (model=%s)",
                cfg.ollama_url,
                cfg.chat_model,
            )
            await inference.health_check()

        retriever = Retriever(memory, embedding)

        # M8 baseline-quality-metric: persist every ``bias.fired`` firing
        # into sqlite ``bias_events`` so the post-hoc ``baseline-metrics``
        # CLI can compute the bias_fired_rate metric offline. The closure
        # references ``runtime`` by name — Python resolves it lazily at
        # call time, and by that time the ``runtime = WorldRuntime(...)``
        # assignment below has run, so the lookup succeeds. Sink exceptions
        # are caught inside ``_bias_target_zone`` (decisions D5).
        def _persist_bias_event(event: BiasFiredEvent) -> None:
            persona_id = runtime.agent_persona_id(event.agent_id)
            if persona_id is None:
                logger.warning(
                    "[bootstrap] bias_event sink skipped: unresolved persona "
                    "for agent=%s tick=%d",
                    event.agent_id,
                    event.tick,
                )
                return
            memory.add_bias_event_sync(
                tick=event.tick,
                agent_id=event.agent_id,
                persona_id=persona_id,
                from_zone=event.from_zone,
                to_zone=event.to_zone,
                bias_p=event.bias_p,
            )

        cycle = CognitionCycle(
            retriever=retriever,
            store=memory,
            embedding=embedding,
            llm=inference,
            erre_policy=DefaultERREModePolicy(),
            bias_sink=_persist_bias_event,
        )
        runtime = WorldRuntime(cycle=cycle)

        # M8 L6-D1: per-turn sink persists every recorded dialog turn into
        # sqlite ``dialog_turns`` for later LoRA-training export. The closure
        # resolves ``agent_id → persona_id`` via ``runtime.agent_persona_id``
        # so the wire schema stays untouched (decisions D2). Sink failures
        # are caught inside ``InMemoryDialogScheduler.record_turn`` so a
        # transient sqlite glitch cannot tear down the live loop.
        def _persist_dialog_turn(turn: DialogTurnMsg) -> None:
            speaker_pid = runtime.agent_persona_id(turn.speaker_id)
            addressee_pid = runtime.agent_persona_id(turn.addressee_id)
            if speaker_pid is None or addressee_pid is None:
                logger.warning(
                    "[bootstrap] dialog_turn sink skipped: unresolved persona for "
                    "dialog_id=%s speaker=%s(%s) addressee=%s(%s)",
                    turn.dialog_id,
                    turn.speaker_id,
                    speaker_pid,
                    turn.addressee_id,
                    addressee_pid,
                )
                return
            memory.add_dialog_turn_sync(
                turn,
                speaker_persona_id=speaker_pid,
                addressee_persona_id=addressee_pid,
            )

        # M7γ Commit 2: relational hook chain. After the M8 dialog-turn
        # persistence, append a per-turn relational-memory INSERT and a
        # bidirectional :class:`RelationshipBond` affinity update.
        persona_registry = _load_persona_registry(cfg)
        _persist_relational_event = _make_relational_sink(
            runtime=runtime,
            memory=memory,
            persona_registry=persona_registry,
        )

        def _chained_turn_sink(turn: DialogTurnMsg) -> None:
            """Run M8 dialog-turn persistence first, then γ relational hook."""
            _persist_dialog_turn(turn)
            _persist_relational_event(turn)

        # The scheduler's envelope sink writes directly into the runtime's
        # fan-out queue so dialog envelopes interleave with agent_update /
        # speech / move without a second delivery path (see design.md §v2).
        scheduler = InMemoryDialogScheduler(
            envelope_sink=runtime.inject_envelope,
            turn_sink=_chained_turn_sink,
        )
        runtime.attach_dialog_scheduler(scheduler)

        # Dialog turn generator wiring: built from the pre-loaded persona
        # registry so the generator can resolve the addressee's display_name
        # at prompt-build time.
        dialog_generator = OllamaDialogTurnGenerator(
            llm=inference,
            personas=persona_registry,
        )
        runtime.attach_dialog_generator(dialog_generator)
        logger.info(
            "[bootstrap] dialog_turn wired (%d personas in registry)",
            len(persona_registry),
        )

        for spec in cfg.agents:
            persona = _load_persona_yaml(cfg.personas_dir, spec.persona_id)
            state = _build_initial_state(spec, persona)
            runtime.register_agent(state, persona)
            logger.info(
                "[bootstrap] registered agent %s (persona=%s zone=%s)",
                state.agent_id,
                spec.persona_id,
                spec.initial_zone.value,
            )

        app = make_app(runtime=runtime)
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host=cfg.host,
                port=cfg.port,
                log_level=cfg.log_level,
                lifespan="on",
            ),
        )
        # Disable uvicorn's own signal handler — we handle SIGINT/SIGTERM below.
        # Depends on uvicorn's private contract; verified against the version
        # pinned in pyproject.toml (>=0.30,<1). Re-verify on any uvicorn bump.
        cast("object", server).install_signal_handlers = lambda: None  # type: ignore[attr-defined]

        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with suppress(NotImplementedError):
                loop.add_signal_handler(sig, stop_event.set)

        logger.info(
            "[bootstrap] starting (host=%s port=%s db=%s)",
            cfg.host,
            cfg.port,
            cfg.db_path,
        )
        await _supervise(runtime, server, stop_event)
        logger.info("[bootstrap] shutdown complete")


async def _supervise(
    runtime: WorldRuntime,
    server: uvicorn.Server,
    stop_event: asyncio.Event,
) -> None:
    """Run runtime + server concurrently; stop both when any signals done.

    Uses ``asyncio.wait(FIRST_COMPLETED)`` rather than ``TaskGroup`` so that
    a runtime exception propagates after graceful uvicorn shutdown instead
    of being wrapped in ``ExceptionGroup`` (which is noisier at the CLI).
    """
    runtime_task = asyncio.create_task(runtime.run(), name="world-runtime")
    server_task = asyncio.create_task(server.serve(), name="uvicorn")
    stop_task = asyncio.create_task(stop_event.wait(), name="signal-wait")

    done, pending = await asyncio.wait(
        {runtime_task, server_task, stop_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Trigger graceful shutdown of both tasks regardless of who finished first.
    server.should_exit = True
    runtime.stop()

    # The stop_task is a pure ``stop_event.wait()`` — if we didn't exit via
    # signal, it will never complete, so cancel it explicitly before awaiting.
    if not stop_task.done():
        stop_task.cancel()

    awaitables: list[Awaitable[object]] = list(pending)
    for task in awaitables:
        try:
            await task
        except asyncio.CancelledError:
            # Expected: we cancelled runtime_task via runtime.stop() above,
            # or stop_task via the explicit cancel() just above.
            pass
        except Exception:
            # Unexpected: log so operators can debug instead of swallowing
            # the failure silently (T19 ghost session class of bugs).
            logger.exception(
                "pending task %s raised during shutdown",
                getattr(task, "get_name", lambda: "?")(),
            )

    # Re-raise the first task exception (if any) so the CLI exits non-zero.
    for task in done:
        if task is stop_task:
            continue
        exc = task.exception()
        if exc is not None:
            raise exc


__all__ = ["BootConfig", "bootstrap"]
