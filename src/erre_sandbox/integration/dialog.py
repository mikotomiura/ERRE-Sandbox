"""In-memory implementation of the M4 :class:`DialogScheduler` Protocol.

Responsibility: admission-control and lifecycle tracking for agent-to-agent
dialogs. The scheduler *also* owns the envelope emission path — when it
admits an initiate or closes a dialog, it calls the injected ``sink``
callable with the corresponding :class:`ControlEnvelope`, so callers do not
need to route the return value back into the gateway's queue themselves.

Design rationale (see
``.steering/20260420-m4-multi-agent-orchestrator/design.md`` §v2):

* The Protocol is frozen at M4 foundation and says ``schedule_initiate``
  returns ``DialogInitiateMsg | None``; we keep that return contract but
  the authoritative delivery path is the sink. Callers that build on the
  Protocol API only get a signal of "was this admitted"; they MUST NOT
  put the returned envelope onto a queue themselves — doing so would
  duplicate the envelope delivered via the sink.
* ``tick()`` is an extension method (not part of the Protocol) that drives
  proximity-based auto-firing: two agents sharing a reflective zone after
  the pair's cooldown has elapsed get a probabilistic initiate.
* All randomness flows through an injected :class:`~random.Random` so the
  auto-fire path is deterministic under test.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from random import Random
from typing import TYPE_CHECKING, ClassVar, Final

from erre_sandbox.schemas import (
    AgentView,
    DialogCloseMsg,
    DialogInitiateMsg,
    DialogTurnMsg,
    Zone,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Sequence
    from typing import Literal

    from erre_sandbox.schemas import ControlEnvelope

logger = logging.getLogger(__name__)


@dataclass
class _OpenDialog:
    """In-flight dialog state carried by the scheduler's ``_open`` map."""

    dialog_id: str
    initiator: str
    target: str
    zone: Zone
    opened_tick: int
    last_activity_tick: int
    turns: list[DialogTurnMsg] = field(default_factory=list)


_REFLECTIVE_ZONES: Final[frozenset[Zone]] = frozenset(
    {Zone.PERIPATOS, Zone.CHASHITSU, Zone.AGORA, Zone.GARDEN},
)
"""Zones where proximity-based dialog admission is allowed.

``Zone.STUDY`` is intentionally excluded — the M2 persona-erre model treats
the study as a private deep-work space where interrupting speech is
culturally inappropriate.
"""


def _pair_key(a: str, b: str) -> frozenset[str]:
    """Order-agnostic dialog pair identity used as a dict key."""
    return frozenset({a, b})


class InMemoryDialogScheduler:
    """Default :class:`DialogScheduler` implementation for MVP multi-agent runs.

    State lives entirely in memory; there is no persistence because M4
    scoped dialog history to the transient layer (semantic summaries come
    from the Reflector on a different path). If a future milestone wants
    cross-run dialog transcripts, subclass and override ``record_turn`` /
    ``close_dialog`` to also write to sqlite.
    """

    COOLDOWN_TICKS: ClassVar[int] = 30
    """Ticks that must elapse after a close before the same pair may reopen."""

    TIMEOUT_TICKS: ClassVar[int] = 6
    """Inactivity window after which an open dialog is auto-closed."""

    AUTO_FIRE_PROB_PER_TICK: ClassVar[float] = 0.25
    """Probability that a qualifying co-located pair is admitted on a tick.

    Keeps dialog from firing every single cognition tick when two agents
    happen to share a zone; the RNG is injected so tests can force the
    probability to 1.0 or 0.0 deterministically.
    """

    def __init__(
        self,
        *,
        envelope_sink: Callable[[ControlEnvelope], None],
        rng: Random | None = None,
    ) -> None:
        self._sink = envelope_sink
        self._rng = rng if rng is not None else Random()  # noqa: S311 — non-crypto
        self._open: dict[str, _OpenDialog] = {}
        self._pair_to_id: dict[frozenset[str], str] = {}
        # Bounded by C(N, 2) for N agents — M4 targets N≤3 so this cannot
        # grow beyond a few entries. If a future milestone scales to N>100
        # agents, cap this to an LRU dict or prune by stale age from
        # ``tick()``; for now the memory footprint is irrelevant.
        self._last_close_tick: dict[frozenset[str], int] = {}

    # ------------------------------------------------------------------
    # Protocol methods (frozen in schemas.py §7.5)
    # ------------------------------------------------------------------

    def schedule_initiate(
        self,
        initiator_id: str,
        target_id: str,
        zone: Zone,
        tick: int,
    ) -> DialogInitiateMsg | None:
        """Admit or reject a new dialog.

        Returns the :class:`DialogInitiateMsg` on admission for callers that
        rely on the Protocol signature, BUT the envelope is already on the
        way to consumers via the injected sink at the moment this method
        returns. Callers must not forward the return value onto the same
        envelope queue — see module docstring.
        """
        if initiator_id == target_id:
            return None
        if zone not in _REFLECTIVE_ZONES:
            return None
        key = _pair_key(initiator_id, target_id)
        if key in self._pair_to_id:
            return None
        last_close = self._last_close_tick.get(key)
        if last_close is not None and tick - last_close < self.COOLDOWN_TICKS:
            return None

        dialog_id = _allocate_dialog_id()
        self._open[dialog_id] = _OpenDialog(
            dialog_id=dialog_id,
            initiator=initiator_id,
            target=target_id,
            zone=zone,
            opened_tick=tick,
            last_activity_tick=tick,
        )
        self._pair_to_id[key] = dialog_id
        envelope = DialogInitiateMsg(
            tick=tick,
            initiator_agent_id=initiator_id,
            target_agent_id=target_id,
            zone=zone,
        )
        self._emit(envelope)
        return envelope

    def record_turn(self, turn: DialogTurnMsg) -> None:
        """Attach ``turn`` to its dialog's transcript.

        Raises ``KeyError`` when the dialog is not open — this surfaces bugs
        (agents speaking into a closed dialog) rather than silently dropping.
        """
        dialog = self._open.get(turn.dialog_id)
        if dialog is None:
            raise KeyError(
                f"record_turn called for unknown dialog_id={turn.dialog_id!r}",
            )
        dialog.turns.append(turn)
        dialog.last_activity_tick = turn.tick

    def close_dialog(
        self,
        dialog_id: str,
        reason: Literal["completed", "interrupted", "timeout"],
    ) -> DialogCloseMsg:
        """Close ``dialog_id`` and emit the envelope via the sink.

        Raises ``KeyError`` when the id is not currently open.
        """
        dialog = self._open.pop(dialog_id, None)
        if dialog is None:
            raise KeyError(f"close_dialog called for unknown dialog_id={dialog_id!r}")
        key = _pair_key(dialog.initiator, dialog.target)
        self._pair_to_id.pop(key, None)
        self._last_close_tick[key] = dialog.last_activity_tick
        envelope = DialogCloseMsg(
            tick=dialog.last_activity_tick,
            dialog_id=dialog_id,
            reason=reason,
        )
        self._emit(envelope)
        return envelope

    # ------------------------------------------------------------------
    # Protocol-external extensions
    # ------------------------------------------------------------------

    def tick(self, world_tick: int, agents: Sequence[AgentView]) -> None:
        """Drive proximity-based admission + timeout close in one step.

        Called by ``WorldRuntime._on_cognition_tick`` after per-agent
        cognition has run. Order:

        1. close any dialogs whose last_activity_tick is older than TIMEOUT
        2. for each co-located pair in reflective zones, probabilistically
           admit (if not already open and past cooldown)
        """
        self._close_timed_out(world_tick)
        for a, b in _iter_colocated_pairs(agents):
            if a.zone not in _REFLECTIVE_ZONES:
                continue
            key = _pair_key(a.agent_id, b.agent_id)
            if key in self._pair_to_id:
                continue
            last_close = self._last_close_tick.get(key)
            if last_close is not None and world_tick - last_close < self.COOLDOWN_TICKS:
                continue
            if self._rng.random() > self.AUTO_FIRE_PROB_PER_TICK:
                continue
            self.schedule_initiate(a.agent_id, b.agent_id, a.zone, world_tick)

    def get_dialog_id(self, agent_a: str, agent_b: str) -> str | None:
        """Return the open dialog id for the (a, b) pair if any, else None."""
        return self._pair_to_id.get(_pair_key(agent_a, agent_b))

    @property
    def open_count(self) -> int:
        return len(self._open)

    def transcript_of(self, dialog_id: str) -> list[DialogTurnMsg]:
        dialog = self._open.get(dialog_id)
        return list(dialog.turns) if dialog is not None else []

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _close_timed_out(self, world_tick: int) -> None:
        expired: list[str] = [
            did
            for did, d in self._open.items()
            if world_tick - d.last_activity_tick >= self.TIMEOUT_TICKS
        ]
        for did in expired:
            self.close_dialog(did, reason="timeout")

    def _emit(self, envelope: ControlEnvelope) -> None:
        try:
            self._sink(envelope)
        except Exception:
            # We refuse to let a sink failure desync scheduler state — log and
            # continue. The sink is the gateway's responsibility; if it is
            # broken that is a gateway-layer bug, not ours.
            logger.exception(
                "Dialog scheduler sink raised for envelope kind=%s",
                envelope.kind,
            )


# ---------------------------------------------------------------------------
# Module-private helpers
# ---------------------------------------------------------------------------


def _allocate_dialog_id() -> str:
    return f"d_{uuid.uuid4().hex[:8]}"


def _iter_colocated_pairs(
    agents: Iterable[AgentView],
) -> Iterator[tuple[AgentView, AgentView]]:
    """Yield (a, b) pairs of distinct agents sharing the same zone.

    Each unordered pair is yielded exactly once with a stable ``a.agent_id``
    < ``b.agent_id`` ordering, so callers can use the first entry as the
    canonical initiator without extra sorting.
    """
    sorted_agents = sorted(agents, key=lambda v: v.agent_id)
    for i, a in enumerate(sorted_agents):
        for b in sorted_agents[i + 1 :]:
            if a.zone == b.zone:
                yield a, b


__all__ = [
    # Re-exported from :mod:`erre_sandbox.schemas` for import ergonomics in
    # callers that already reach into this module for the scheduler.
    "AgentView",
    "InMemoryDialogScheduler",
]
