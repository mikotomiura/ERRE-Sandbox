"""Running-trace generator: deterministic no-LLM closed-loop agent policy.

This is the **single new part** the running-substrate ADR adds (design-final.md
§2/§4.2): a policy that drives the **real**
:func:`erre_sandbox.world.physics.step_kinematics` + a memory store around a
closed loop (move -> form memory -> retrieve -> move), producing a
:class:`~erre_sandbox.evidence.d0_substrate.stub.Trace3D` whose within-zone
memory geometry is a consequence of the agent's own history. The frozen
``quantize_trace`` / ``ladder`` readout then consumes the trace **unchanged**
(:mod:`running_ladder`).

**Primary policy = (P-A) terminal-anchored memory-preferential-return**
(design-final.md §1.1, DA-RUNIMPL-1). Two phases per arm, both frozen:

* **Phase A** (``formed_count < K_RETRIEVE`` = 8, *explore*): greedy
  minimum-graph-distance navigation toward the drawn ``terminal`` zone over
  the frozen :data:`~...constants.ADJACENCY`; once at ``terminal`` the agent
  stays and keeps forming memories there. ``dest = zone_centroid(next_zone) +
  discJitter(CELL_MICRO_RADIUS_M)``.
* **Phase B** (``>= K_RETRIEVE``, *forage*): retrieve the agent's own top-K
  memories through the **frozen retriever**, take their strength-weighted
  centroid, ``dest = centroid + discJitter(CELL_MICRO_RADIUS_M)``, then
  radially **reflect-clamp** into the terminal Voronoi cell (design-final.md
  §1.3 formula). This concentrates ``> K`` memories in the terminal zone (the
  arithmetic *necessary* condition for ``Δ_1 > 0``, design-final.md §0.1
  fact 1) while the two arms diverge from independent jitter substreams.

**Forensic control generators** (design-final.md §4, non-gating, all on the
*same* apparatus with only the generator swapped): ``memoryless`` (P-C: same
concentration with no preferential return -> R1 PASS ∧ running-ness gate FAIL
expected, §4.1), ``spontaneous`` (P-B = v1: terminal-agnostic
saturation-triggered explore/return, emergent dwelling -> R1 FAIL expected,
§4.2), and the policy-form variants ``no-reflect`` / ``uniform-centroid`` /
``top-1-centroid`` (§4.5) that expose whether the P-A functional-form DOFs
smuggle in the within-zone structure.

**Policy grammar freeze (design-final.md §5, binding, 6 items)** — pinned in
this docstring + ``tests/test_evidence/test_d0_running_policy.py``, frozen
before the sealed run (no post-hoc dial, DA-RUNIMPL-3):

1. **Allowed history features (closed list, nothing else)**: ``formed_count``;
   the frozen retriever's top-``K_RETRIEVE`` self memories; their
   strength-weighted centroid; ``here_zone`` + graph-distance to ``terminal``
   over the frozen ``ADJACENCY``; ``terminal`` (from ``draw_start_terminal``).
2. **feature -> action transform (functional form + constants)**: greedy
   explore / strength-weighted centroid / radial reflect-clamp, all with
   frozen constants; ``discJitter(R): r = R·sqrt(u), θ ~ U(0, 2π)``.
3. **start / scenario**: ``draw_start_terminal(seed)`` inherited verbatim;
   seed bank ``range(B)`` inherited (``stub.default_seed_bank``).
4. **tick / memory-formation schedule**: ``M_MEMORIES`` = 20 events/arm,
   1 memory per arrival, tick rate 30 Hz, ``created_at = _BASE_TS + t·1s``.
5. **no manual per-zone / per-affordance weight** — the transform carries no
   zone- or affordance-specific hand weight.
6. **no policy change after seeing a (blind or running) dry-run R1 result**
   (forking-paths seal).

**Determinism (design-final.md §2.4)**: every RNG is a named substream
``random.Random(f"run-seed-{seed}-{arm}-{stream}")`` with
``stream ∈ {micro, tie, ablate}`` (``ablate`` is drawn by :mod:`runningness`),
never the global RNG; integer tick counting; no wall-clock; the frozen
``_PROBE_NOW`` retrieval clock. A re-run with the same seed reproduces a
byte-identical :func:`~...stub.trace_checksum`.

**Honest reservation (design-final.md §2.3)**: physics arrival == target snap,
so the physics layer is close to "connect the dots"; the history-dependence
lives in the policy's *destination choice* (it reads the retrieval centroid),
not in the interpolation. Physics supplies embodied continuous motion +
determinism; the running-ness gate (:mod:`runningness`) measures the
policy-level history-dependence, not physics.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Literal

from erre_sandbox.evidence.d0_substrate import constants as _c
from erre_sandbox.evidence.d0_substrate.ladder import (
    _BASE_TS,
    _EMBED_DIM,
    _PROBE_NOW,
    _FixedUnitEmbedding,
)
from erre_sandbox.evidence.d0_substrate.running import constants as _rc
from erre_sandbox.evidence.d0_substrate.smoke import SmokeClock
from erre_sandbox.evidence.d0_substrate.stub import (
    Trace3D,
    TraceRow,
    _affordance_ids_near,
    draw_start_terminal,
)
from erre_sandbox.memory.retrieval import Retriever
from erre_sandbox.memory.store import MemoryStore
from erre_sandbox.schemas import (
    MemoryEntry,
    MemoryKind,
    MoveMsg,
    Position,
    SpatialContext,
    Zone,
)
from erre_sandbox.world.physics import Kinematics, apply_move_command, step_kinematics
from erre_sandbox.world.zones import locate_zone

if TYPE_CHECKING:
    from erre_sandbox.memory.retrieval import RankedMemory

PolicyForm = Literal[
    "P-A",
    "memoryless",
    "spontaneous",
    "no-reflect",
    "uniform-centroid",
    "top-1-centroid",
]
"""The primary policy (``P-A``) plus the frozen forensic-control generators
(design-final.md §4.1/§4.2/§4.5). ``memoryless`` = C-memoryless (P-C),
``spontaneous`` = C-spontaneous (P-B = v1)."""

_P_A_FAMILY: frozenset[PolicyForm] = frozenset(
    {"P-A", "no-reflect", "uniform-centroid", "top-1-centroid"}
)
"""Policies that share the P-A explore/forage skeleton and differ only in the
forage functional-form DOF (design-final.md §4.5)."""

_FORAGE_QUERY: Literal["d0 running forage prompt"] = "d0 running forage prompt"
"""Zone-vocabulary-free forage query. With the fixed-unit embedding cosine is
tied, so the query text never decides ranking — the spatial term does (mirrors
``ladder._zone_free_queries`` intent)."""

_AGENT_ID: Literal["d0-run"] = "d0-run"
_MAX_TRANSIT_TICKS: int = 100_000
"""Safety cap on the physics transit loop (a straight-line snap always
terminates well within this; the cap only guards against a pathological
non-finite target, which the frozen ``step_kinematics`` already clears)."""


@dataclass(frozen=True, slots=True)
class ForageRollout:
    """One forage event's decision trail (design-final.md §3/§4 input).

    ``retrieved_centroid`` is the strength-weighted centroid the policy read
    from history; ``terminal_centroid`` is the memoryless counterfactual
    baseline. Because the *same* jitter is added to both, the post-clamp
    transition distance reduces to ``||retrieved_centroid -
    terminal_centroid||`` — the running-ness ablation's ``δ`` (:mod:`runningness`).
    ``clamp_fired`` feeds the ``clamp_rate`` forensic (design-final.md §1.3/§4).
    """

    event_index: int
    retrieved_centroid: tuple[float, float]
    terminal_centroid: tuple[float, float]
    jitter: tuple[float, float]
    pre_clamp_dest: tuple[float, float]
    post_clamp_dest: tuple[float, float]
    clamp_fired: bool


@dataclass(frozen=True)
class RunningArmResult:
    """One arm's running trace + the forage rollouts + physics-tick metadata.

    ``physics_ticks`` is replay/determinism **metadata** (it is *not* a
    ``TraceRow`` field — ``TraceRow.tick_index`` is the memory-formation event
    index 0..M-1, design-final.md §6 / Codex LOW-1).
    """

    trace: Trace3D
    forage_rollouts: tuple[ForageRollout, ...]
    physics_ticks: int


def _graph_distances(target: Zone) -> dict[Zone, int]:
    """BFS hop distance from every zone to ``target`` over frozen ADJACENCY."""
    dist: dict[Zone, int] = {target: 0}
    frontier: list[Zone] = [target]
    while frontier:
        nxt: list[Zone] = []
        for zone in frontier:
            for neighbour in _c.ADJACENCY[zone]:
                if neighbour not in dist:
                    dist[neighbour] = dist[zone] + 1
                    nxt.append(neighbour)
        frontier = nxt
    return dist


def _greedy_next_zone(
    here: Zone, terminal: Zone, dist: dict[Zone, int], tie_rng: random.Random
) -> tuple[Zone, int]:
    """Greedy neighbour minimising graph distance to ``terminal``.

    Returns ``(next_zone, action_id)`` where ``action_id`` is the index into
    ``ADJACENCY[here]`` (design-final.md §2.2); staying at ``terminal`` yields
    ``(terminal, 0)``. ``tie_rng`` is consumed **only** when two neighbours
    tie, so single-shortest-path steps never perturb the substream.
    """
    if here == terminal:
        return here, 0
    options = _c.ADJACENCY[here]
    best_d = min(dist[nb] for nb in options)
    candidates = [i for i, nb in enumerate(options) if dist[nb] == best_d]
    idx = (
        candidates[0]
        if len(candidates) == 1
        else candidates[tie_rng.randrange(len(candidates))]
    )
    return options[idx], idx


def _disc_jitter(rng: random.Random) -> tuple[float, float]:
    """Area-preserving disc-uniform offset (byte-identical to ``stub.build_trace``)."""
    r = _c.CELL_MICRO_RADIUS_M * math.sqrt(rng.random())
    theta = rng.uniform(0.0, 2.0 * math.pi)
    return r * math.cos(theta), r * math.sin(theta)


def _reflect_clamp(
    dest_x: float, dest_z: float, terminal: Zone
) -> tuple[float, float, bool]:
    """Radially clamp a forage dest into the terminal Voronoi cell (§1.3).

    ``dest' = c + (dest − c)·min(1, ρ_max/‖dest − c‖)`` with
    ``ρ_max = CELL_MICRO_RADIUS_M``, fired only when ``locate_zone(dest) !=
    terminal``. Returns ``(x, z, clamp_fired)``; the clamped point is within
    ``ρ_max`` (< half the Voronoi boundary), so ``locate_zone`` agrees with
    ``terminal`` afterwards.
    """
    if locate_zone(dest_x, 0.0, dest_z) == terminal:
        return dest_x, dest_z, False
    cx, _cy, cz = _c.ZONE_CENTERS[terminal]
    dx = dest_x - cx
    dz = dest_z - cz
    norm = math.hypot(dx, dz)
    if norm == 0.0:
        return cx, cz, True
    scale = min(1.0, _c.CELL_MICRO_RADIUS_M / norm)
    return cx + dx * scale, cz + dz * scale, True


def _forage_centroid(
    ranked: list[RankedMemory], policy: PolicyForm, terminal_xz: tuple[float, float]
) -> tuple[float, float]:
    """Forage destination centroid for a P-A-family policy (design-final.md §4.5).

    ``P-A`` / ``no-reflect`` = strength-weighted centroid; ``uniform-centroid``
    = unweighted mean; ``top-1-centroid`` = the single strongest memory's
    position. Falls back to the terminal centroid if nothing located surfaces.
    """
    located = [r for r in ranked if r.entry.location is not None]
    if not located:
        return terminal_xz
    if policy == "top-1-centroid":
        loc = located[0].entry.location
        assert loc is not None  # narrowed by the located filter
        return loc.x, loc.z
    weights = (
        [1.0] * len(located)
        if policy == "uniform-centroid"
        else [r.strength for r in located]
    )
    total = sum(weights)
    if total <= 0.0:
        return terminal_xz
    cx = 0.0
    cz = 0.0
    for w, r in zip(weights, located, strict=True):
        loc = r.entry.location
        assert loc is not None  # narrowed by the located filter
        cx += w * loc.x
        cz += w * loc.z
    return cx / total, cz / total


def _transit(start: Position, dest: Position) -> tuple[Position, int]:
    """Real ``step_kinematics`` transit from ``start`` to ``dest`` (arrival snap).

    Drives the frozen physics with a fixed-``dt`` :class:`~...smoke.SmokeClock`
    (no wall-clock) until the destination is cleared. Returns the arrival
    position (== ``dest`` snapped, with ``locate_zone``-derived zone) and the
    physics-tick count (determinism metadata, not a ``TraceRow`` field).
    """
    kin = Kinematics(position=start, speed_mps=_rc.POLICY_SPEED_MPS)
    apply_move_command(
        kin,
        MoveMsg(tick=0, agent_id=_AGENT_ID, target=dest, speed=_rc.POLICY_SPEED_MPS),
    )
    clock = SmokeClock(1.0 / _rc.POLICY_TICK_HZ)
    ticks = 0
    while kin.destination is not None and ticks < _MAX_TRANSIT_TICKS:
        clock.advance()
        step_kinematics(kin, clock.dt_seconds)
        ticks += 1
    if kin.destination is not None:
        # Cap reached without snapping — never happens for a finite in-cell
        # target, but fail loudly rather than return a corrupt half-way position
        # (Codex LOW-2). A silent partial arrival would poison the trace.
        msg = f"physics transit did not converge within {_MAX_TRANSIT_TICKS} ticks"
        raise RuntimeError(msg)
    return kin.position, ticks


def _make_retriever(store: MemoryStore) -> Retriever:
    """Frozen retriever wired for the policy's own memory reads (§5 freeze 1)."""
    return Retriever(
        store,
        _FixedUnitEmbedding(),
        spatial_weight=1.0,
        spatial_gamma=_c.SPATIAL_GAMMA,
        spatial_coord_ref=_c.SPATIAL_COORD_REF,
        now_factory=_PROBE_NOW,
    )


def _spontaneous_dest(
    here: Zone,
    own: list[tuple[Zone, float, float]],
    jitter: tuple[float, float],
    tie_rng: random.Random,
) -> tuple[float, float, int]:
    """(P-B) terminal-agnostic saturation-triggered explore/return (§4.2).

    ``n_local >= K`` -> explore a random neighbour; ``>= 1`` -> return to the
    within-zone cluster centroid of own memories; ``0`` -> zone centroid. Same
    jitter radius / seed bank / schedule as P-A; the *only* difference is that
    dwelling is emergent, not anchored to ``terminal``.

    **Intentional RNG-schedule difference (code-reviewer MEDIUM-4)**: P-B has no
    ``formed_count < K`` explore phase, so it consumes ``tie_rng`` on a different
    schedule than P-A. This is by design — P-B is a *forensic control* measuring
    emergent (terminal-agnostic) dwelling, not an RNG-matched twin of P-A. Its
    own replay is still byte-deterministic under the same named substreams.
    """
    dx, dz = jitter
    local = [(x, z) for (zone, x, z) in own if zone == here]
    if len(local) >= _c.K_RETRIEVE:
        options = _c.ADJACENCY[here]
        idx = tie_rng.randrange(len(options))
        bcx, _bcy, bcz = _c.ZONE_CENTERS[options[idx]]
        return bcx + dx, bcz + dz, idx
    if local:
        ccx = sum(p[0] for p in local) / len(local)
        ccz = sum(p[1] for p in local) / len(local)
        return ccx + dx, ccz + dz, 0
    bcx, _bcy, bcz = _c.ZONE_CENTERS[here]
    return bcx + dx, bcz + dz, 0


async def generate_running_arm(  # noqa: PLR0915 — closed-loop policy orchestration (branchy generator)
    seed: int, arm: str, policy: PolicyForm = "P-A"
) -> RunningArmResult:
    """Generate one arm's running trace via the closed-loop policy (§2/§4).

    See the module docstring for the frozen policy grammar. ``policy`` selects
    the primary P-A or a frozen forensic-control generator; every branch shares
    the frozen constants, substreams, physics, and memory schedule.
    """
    start_zone, terminal_zone = draw_start_terminal(seed)
    dist = _graph_distances(terminal_zone)
    micro_rng = random.Random(f"run-seed-{seed}-{arm}-micro")  # noqa: S311
    tie_rng = random.Random(f"run-seed-{seed}-{arm}-tie")  # noqa: S311

    store = MemoryStore(":memory:", embed_dim=_EMBED_DIM)
    store.create_schema()
    embed_vec = [1.0] + [0.0] * (_EMBED_DIM - 1)
    retriever = _make_retriever(store)

    sx, sy, sz = _c.ZONE_CENTERS[start_zone]
    pos = Position(x=sx, y=sy, z=sz, zone=start_zone)
    terminal_xz = (_c.ZONE_CENTERS[terminal_zone][0], _c.ZONE_CENTERS[terminal_zone][2])

    rows: list[TraceRow] = []
    rollouts: list[ForageRollout] = []
    own: list[tuple[Zone, float, float]] = []
    total_ticks = 0

    # try/finally guarantees the in-memory store is closed even if a store.add /
    # retrieve raises mid-episode (code-reviewer HIGH-1) — no GC-deferred conn.
    try:
        for t in range(_c.M_MEMORIES):
            here_zone = pos.zone
            jitter = _disc_jitter(micro_rng)
            rollout: ForageRollout | None = None

            if policy == "spontaneous":
                dest_x, dest_z, action_id = _spontaneous_dest(
                    here_zone, own, jitter, tie_rng
                )
            elif t < _c.K_RETRIEVE:
                next_zone, action_id = _greedy_next_zone(
                    here_zone, terminal_zone, dist, tie_rng
                )
                bcx, _bcy, bcz = _c.ZONE_CENTERS[next_zone]
                dest_x, dest_z = bcx + jitter[0], bcz + jitter[1]
            elif policy == "memoryless":
                # C-memoryless (P-C): concentration with no preferential return.
                dest_x, dest_z = terminal_xz[0] + jitter[0], terminal_xz[1] + jitter[1]
                action_id = 0
                rollout = ForageRollout(
                    event_index=t,
                    retrieved_centroid=terminal_xz,
                    terminal_centroid=terminal_xz,
                    jitter=jitter,
                    pre_clamp_dest=(dest_x, dest_z),
                    post_clamp_dest=(dest_x, dest_z),
                    clamp_fired=False,
                )
            else:
                # P-A family forage: read own history, reflect-clamp into cell.
                ranked = await retriever.retrieve(
                    _AGENT_ID,
                    _FORAGE_QUERY,
                    k_agent=_c.K_RETRIEVE,
                    k_world=0,
                    current_location=pos,
                    mark_recalled=False,
                )
                centroid = _forage_centroid(ranked, policy, terminal_xz)
                pre_x, pre_z = centroid[0] + jitter[0], centroid[1] + jitter[1]
                if policy == "no-reflect":
                    dest_x, dest_z, clamp_fired = pre_x, pre_z, False
                else:
                    dest_x, dest_z, clamp_fired = _reflect_clamp(
                        pre_x, pre_z, terminal_zone
                    )
                action_id = 0
                rollout = ForageRollout(
                    event_index=t,
                    retrieved_centroid=centroid,
                    terminal_centroid=terminal_xz,
                    jitter=jitter,
                    pre_clamp_dest=(pre_x, pre_z),
                    post_clamp_dest=(dest_x, dest_z),
                    clamp_fired=clamp_fired,
                )

            dest_zone = locate_zone(dest_x, 0.0, dest_z)
            dest_pos = Position(x=dest_x, y=0.0, z=dest_z, zone=dest_zone)
            arrival, ticks = _transit(pos, dest_pos)
            total_ticks += ticks

            move_dx = arrival.x - pos.x
            move_dz = arrival.z - pos.z
            yaw = (
                math.atan2(move_dz, move_dx)
                if (move_dx != 0.0 or move_dz != 0.0)
                else 0.0
            )
            arr_zone = arrival.zone
            content = f"d0c{t:02d}"
            await store.add(
                MemoryEntry(
                    id=f"{content}-row",
                    agent_id=_AGENT_ID,
                    kind=MemoryKind.EPISODIC,
                    content=content,
                    importance=0.5,
                    created_at=_BASE_TS + timedelta(seconds=t),
                    location=SpatialContext(
                        zone=arr_zone, x=arrival.x, y=arrival.y, z=arrival.z
                    ),
                ),
                embedding=embed_vec,
            )
            rows.append(
                TraceRow(
                    tick_index=t,
                    seed=seed,
                    zone=arr_zone,
                    x=arrival.x,
                    y=arrival.y,
                    z=arrival.z,
                    yaw=yaw,
                    pitch=0.0,
                    action_id=action_id,
                    affordance_ids=_affordance_ids_near(arrival.x, arrival.z, arr_zone),
                )
            )
            if rollout is not None:
                rollouts.append(rollout)
            own.append((arr_zone, arrival.x, arrival.z))
            pos = arrival
    finally:
        await store.close()

    return RunningArmResult(
        trace=Trace3D(seed=seed, arm=arm, rows=tuple(rows)),
        forage_rollouts=tuple(rollouts),
        physics_ticks=total_ticks,
    )


async def build_seed_pair_running(
    seed: int, *, policy: PolicyForm = "P-A"
) -> tuple[Trace3D, Trace3D, Zone, Zone]:
    """Both arms' running traces + the shared ``(start, terminal)``.

    Same signature/contract as the frozen ``stub.build_seed_pair`` (plus the
    ``policy`` kwarg) so :mod:`running_ladder` can drive it exactly where the
    frozen ladder drives ``build_seed_pair`` — **without** monkeypatching the
    frozen module (design-final.md §2.1, Codex HIGH-3). The two arms share the
    drawn ``start``/``terminal`` and diverge from independent substreams.
    """
    start, terminal = draw_start_terminal(seed)
    arm_a = await generate_running_arm(seed, "A", policy)
    arm_b = await generate_running_arm(seed, "B", policy)
    return arm_a.trace, arm_b.trace, start, terminal


__all__ = [
    "ForageRollout",
    "PolicyForm",
    "RunningArmResult",
    "build_seed_pair_running",
    "generate_running_arm",
]
