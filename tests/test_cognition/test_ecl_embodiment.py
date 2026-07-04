"""Tests for ``erre_sandbox.cognition.embodiment`` (M13 ECL v0, Issue 002).

The ECL v0 organ core resolves an LLM-selected ``destination_zone`` (a zone tag,
never coordinates) into a concrete within-zone target derived from the agent's
own memory history. These tests pin the binding contract (design-final.md
§論点2 / §論点4):

* **AC1** policy-grammar freeze — the resolver reads only the closed feature set,
  the LLM cannot inject coordinates/weights, ``k_world=0`` keeps cross-agent
  memory out of the centroid (Codex HIGH-2).
* **AC2/AC3** continuity gate — an *exact* (ε-free) causal-wiring oracle:
  memory→geometry→movement is asserted alive (positive, both clamp branches) and
  the ablation of that edge collapses to ``default_spawn`` (negative + fallbacks).
  This is a **construction** check, **NOT a structural-floor verdict; verdict は
  holding** — no statistic / floor / landscape number is computed anywhere.
* **AC4** the resolved target is history-dependent (≠ ``default_spawn``).
* **AC5** measurement-line non-re-entry — an import/output guard (not a word ban)
  proving the module touches no ``evidence`` / ``spdm`` / ``runningness`` machinery
  and defines no floor/landscape/verdict output identifier.
"""

from __future__ import annotations

import ast
import inspect
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from erre_sandbox.cognition import embodiment
from erre_sandbox.cognition.embodiment import (
    K_ECL,
    EclDestination,
    EclRecordMode,
    resolve_destination,
    strength_weighted_centroid,
)
from erre_sandbox.contracts import geometry
from erre_sandbox.memory.retrieval import RankedMemory, Retriever
from erre_sandbox.schemas import MemoryEntry, MemoryKind, Position, SpatialContext, Zone

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from erre_sandbox.memory import EmbeddingClient, MemoryStore

_FIXED_NOW = datetime(2026, 1, 1, tzinfo=UTC)
"""Fixed retrieval clock so ``age_days == 0`` ⇒ ``strength == importance`` exactly
(all seeded memories share ``created_at == _FIXED_NOW``)."""

_EMBED_DIM = 768
"""Matches ``MemoryStore`` default ``embed_dim`` and the conftest embed mock, whose
constant vector makes cosine similarity a tied ``1.0`` for every candidate."""

_EMBED = [0.01] * _EMBED_DIM
_QUERY = "forage"

_SRC = Path(embodiment.__file__)
_MODULE_TREE = ast.parse(_SRC.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #


@pytest.fixture
async def make_retriever(
    cognition_store: MemoryStore,
    make_embedding_client: Callable[[], EmbeddingClient],
) -> AsyncIterator[Callable[[], Retriever]]:
    """Build fixed-clock retrievers over the shared in-memory store.

    The fixed ``now_factory`` + tied cosine give ``strength == importance``, so a
    single-memory centroid equals that memory's location and a multi-memory one
    is a clean importance-weighted mean — an exact (not ε-ball) oracle target.
    """
    clients: list[EmbeddingClient] = []

    def _build() -> Retriever:
        emb = make_embedding_client()
        clients.append(emb)
        return Retriever(cognition_store, emb, now_factory=_FIXED_NOW)

    yield _build
    for c in clients:
        await c.close()


async def _seed(
    store: MemoryStore,
    *,
    agent_id: str,
    mem_id: str,
    x: float,
    z: float,
    zone: Zone,
    importance: float,
    with_location: bool = True,
) -> None:
    location = SpatialContext(zone=zone, x=x, y=0.0, z=z) if with_location else None
    await store.add(
        MemoryEntry(
            id=mem_id,
            agent_id=agent_id,
            kind=MemoryKind.EPISODIC,
            content="obs",
            importance=importance,
            created_at=_FIXED_NOW,
            location=location,
        ),
        embedding=_EMBED,
    )


def _rm(x: float, z: float, strength: float, mem_id: str = "m") -> RankedMemory:
    """A synthetic ranked memory at ``(x, z)`` with an exact ``strength`` weight."""
    entry = MemoryEntry(
        id=mem_id,
        agent_id="a",
        kind=MemoryKind.EPISODIC,
        content="c",
        importance=0.5,
        created_at=_FIXED_NOW,
        location=SpatialContext(zone=Zone.STUDY, x=x, y=0.0, z=z),
    )
    return RankedMemory(entry=entry, strength=strength, cosine_sim=1.0)


class _StubRetriever:
    """Retriever fake returning a fixed ranked list (records the kwargs it saw)."""

    def __init__(self, ranked: list[RankedMemory]) -> None:
        self._ranked = ranked
        self.calls: list[dict[str, object]] = []

    async def retrieve(
        self,
        agent_id: str,
        query: str,
        *,
        k_agent: int = 8,
        k_world: int = 3,
        current_location: SpatialContext | Position | None = None,  # noqa: ARG002
        mark_recalled: bool = True,
    ) -> list[RankedMemory]:
        self.calls.append(
            {
                "agent_id": agent_id,
                "query": query,
                "k_agent": k_agent,
                "k_world": k_world,
                "mark_recalled": mark_recalled,
            }
        )
        return list(self._ranked)


class _SpyRetriever:
    """Wraps a real retriever, capturing the kwargs the resolver passes."""

    def __init__(self, inner: Retriever) -> None:
        self._inner = inner
        self.calls: list[dict[str, object]] = []

    async def retrieve(
        self,
        agent_id: str,
        query: str,
        *,
        k_agent: int = 8,
        k_world: int = 3,
        current_location: SpatialContext | Position | None = None,
        mark_recalled: bool = True,
    ) -> list[RankedMemory]:
        self.calls.append(
            {"k_agent": k_agent, "k_world": k_world, "mark_recalled": mark_recalled}
        )
        return await self._inner.retrieve(
            agent_id,
            query,
            k_agent=k_agent,
            k_world=k_world,
            current_location=current_location,
            mark_recalled=mark_recalled,
        )


# --------------------------------------------------------------------------- #
# AC1 — policy grammar freeze
# --------------------------------------------------------------------------- #


class TestPolicyGrammarFrozen:
    """AC1: closed feature set, no LLM coordinate injection, k_world=0."""

    def test_signature_admits_only_a_zone_tag_from_the_llm(self) -> None:
        # The LLM's entire discretion is ``destination_zone: Zone``. The resolver
        # exposes no coordinate/weight parameter, so a plan cannot inject a raw
        # target. Freezing the parameter set makes a future coordinate param a
        # visible contract break.
        sig = inspect.signature(resolve_destination)
        assert set(sig.parameters) == {
            "retriever",
            "agent_id",
            "query",
            "here",
            "destination_zone",
            "micro_rng",
            "k_ecl",
        }
        assert sig.parameters["destination_zone"].annotation == "Zone"
        # No parameter smuggles a free coordinate / weight the LLM could steer.
        banned = ("target", "coord", "weight", "dest_x", "dest_z", "centroid")
        for name in sig.parameters:
            assert not any(tok in name.lower() for tok in banned), name

    @pytest.mark.asyncio
    async def test_ecl_v0_policy_grammar_frozen(
        self,
        cognition_store: MemoryStore,
        make_retriever: Callable[[], Retriever],
    ) -> None:
        # Self memory (agent a1) inside STUDY + a *world-scope* memory (agent a2)
        # far away in GARDEN. With k_world=0 the world memory must never enter the
        # centroid — the "self memory only" claim (Codex HIGH-2).
        sx, _sy, sz = geometry.ZONE_CENTERS[Zone.STUDY]
        gx, _gy, gz = geometry.ZONE_CENTERS[Zone.GARDEN]
        await _seed(
            cognition_store,
            agent_id="a1",
            mem_id="self",
            x=sx + 2.0,
            z=sz - 3.0,
            zone=Zone.STUDY,
            importance=0.8,
        )
        await _seed(
            cognition_store,
            agent_id="a2",
            mem_id="world",
            x=gx,
            z=gz,
            zone=Zone.GARDEN,
            importance=0.9,
        )
        spy = _SpyRetriever(make_retriever())
        here = geometry.default_spawn(Zone.STUDY)
        res = await resolve_destination(
            spy,
            agent_id="a1",
            query=_QUERY,
            here=here,
            destination_zone=Zone.STUDY,
            micro_rng=random.Random("grammar"),
        )
        # The resolver passes the binding retrieval kwargs (k_world=0 keeps
        # cross-agent memory out; mark_recalled=False avoids a measurement-order
        # recall artefact; k_agent=K_ECL is the frozen top-k).
        assert spy.calls == [{"k_agent": K_ECL, "k_world": 0, "mark_recalled": False}]
        # Only the self memory shaped the destination.
        assert res.provenance == ("self",)
        assert "world" not in res.provenance
        assert res.centroid == (sx + 2.0, sz - 3.0)


# --------------------------------------------------------------------------- #
# AC2 — continuity positive control (exact oracle, both clamp branches)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
class TestContinuityPositiveControl:
    """AC2: exact (ε-free) causal wiring, clamp-fired and not-fired branches."""

    async def _resolve_single(
        self,
        store: MemoryStore,
        make_retriever: Callable[[], Retriever],
        *,
        mem_x: float,
        mem_z: float,
        mem_zone: Zone,
        destination_zone: Zone,
    ) -> tuple[EclDestination, tuple[float, float]]:
        await _seed(
            store,
            agent_id="a1",
            mem_id="only",
            x=mem_x,
            z=mem_z,
            zone=mem_zone,
            importance=0.8,
        )
        retr = make_retriever()
        here = geometry.default_spawn(destination_zone)
        # Independent oracle: re-derive the centroid straight from the raw
        # retrieval strength with the *same* arithmetic the resolver uses
        # (``w·p / w``) — bit-exact, and it collapses if the memory→centroid edge
        # is mis-wired to a constant.
        ranked = await retr.retrieve(
            "a1",
            _QUERY,
            k_agent=K_ECL,
            k_world=0,
            current_location=here,
            mark_recalled=False,
        )
        assert len(ranked) == 1
        w = ranked[0].strength
        loc = ranked[0].entry.location
        assert loc is not None
        expected_centroid = (w * loc.x / w, w * loc.z / w)
        res = await resolve_destination(
            retr,
            agent_id="a1",
            query=_QUERY,
            here=here,
            destination_zone=destination_zone,
            micro_rng=random.Random("pinned"),
        )
        return res, expected_centroid

    def _assert_exact_transform(
        self, res: EclDestination, destination_zone: Zone
    ) -> None:
        # Re-run the frozen transform (centroid + jitter, THEN reflect_clamp) and
        # demand *exact* equality — no ε-ball to tune the gate open (Codex HIGH-3).
        exp_pre = (
            res.centroid[0] + res.jitter[0],
            res.centroid[1] + res.jitter[1],
        )
        assert res.pre_clamp == exp_pre
        exp_x, exp_z, exp_fired = geometry.reflect_clamp(*exp_pre, destination_zone)
        assert (res.post_clamp[0], res.post_clamp[1], res.clamp_fired) == (
            exp_x,
            exp_z,
            exp_fired,
        )
        assert (res.target.x, res.target.z) == (res.post_clamp[0], res.post_clamp[1])
        assert res.target.zone is geometry.locate_zone(res.target.x, 0.0, res.target.z)
        assert res.resolved_from == "memory_centroid"
        spawn = geometry.default_spawn(destination_zone)
        assert (res.target.x, res.target.z) != (spawn.x, spawn.z)

    async def test_ecl_v0_continuity_positive_control_clamp_not_fired(
        self,
        cognition_store: MemoryStore,
        make_retriever: Callable[[], Retriever],
    ) -> None:
        # Memory sits inside STUDY's cell ⇒ centroid+jitter stays inside ⇒ no clamp.
        sx, _sy, sz = geometry.ZONE_CENTERS[Zone.STUDY]
        res, expected_centroid = await self._resolve_single(
            cognition_store,
            make_retriever,
            mem_x=sx + 2.0,
            mem_z=sz - 3.0,
            mem_zone=Zone.STUDY,
            destination_zone=Zone.STUDY,
        )
        assert res.centroid == expected_centroid
        assert res.clamp_fired is False
        self._assert_exact_transform(res, Zone.STUDY)

    async def test_ecl_v0_continuity_positive_control_clamp_fired(
        self,
        cognition_store: MemoryStore,
        make_retriever: Callable[[], Retriever],
    ) -> None:
        # Memory sits at GARDEN's centre but the LLM chose STUDY ⇒ centroid+jitter
        # lands outside STUDY's cell ⇒ reflect_clamp fires and pulls it back in.
        gx, _gy, gz = geometry.ZONE_CENTERS[Zone.GARDEN]
        res, expected_centroid = await self._resolve_single(
            cognition_store,
            make_retriever,
            mem_x=gx,
            mem_z=gz,
            mem_zone=Zone.GARDEN,
            destination_zone=Zone.STUDY,
        )
        assert res.centroid == expected_centroid
        assert res.clamp_fired is True
        assert geometry.locate_zone(res.target.x, 0.0, res.target.z) is Zone.STUDY
        self._assert_exact_transform(res, Zone.STUDY)


# --------------------------------------------------------------------------- #
# AC3 — continuity negative control + fallbacks
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
class TestContinuityNegativeControl:
    """AC3: cut the memory→geometry edge ⇒ target collapses to default_spawn."""

    async def test_ecl_v0_continuity_negative_control(
        self,
        cognition_store: MemoryStore,
        make_retriever: Callable[[], Retriever],
    ) -> None:
        spawn = geometry.default_spawn(Zone.STUDY)
        here = geometry.default_spawn(Zone.STUDY)
        # Empty retrieval severs the memory→geometry edge.
        empty = await resolve_destination(
            _StubRetriever([]),
            agent_id="a1",
            query=_QUERY,
            here=here,
            destination_zone=Zone.STUDY,
            micro_rng=random.Random("neg"),
        )
        assert empty.resolved_from == "spawn"
        assert (empty.target.x, empty.target.y, empty.target.z) == (
            spawn.x,
            spawn.y,
            spawn.z,
        )
        assert empty.target.zone is Zone.STUDY
        assert empty.provenance == ()
        assert empty.jitter == (0.0, 0.0)
        assert empty.clamp_fired is False

        # The same tick *with* memory resolves elsewhere — the ablation bites.
        sx, _sy, sz = geometry.ZONE_CENTERS[Zone.STUDY]
        await _seed(
            cognition_store,
            agent_id="a1",
            mem_id="only",
            x=sx + 4.0,
            z=sz + 4.0,
            zone=Zone.STUDY,
            importance=0.8,
        )
        with_memory = await resolve_destination(
            make_retriever(),
            agent_id="a1",
            query=_QUERY,
            here=here,
            destination_zone=Zone.STUDY,
            micro_rng=random.Random("neg"),
        )
        assert (with_memory.target.x, with_memory.target.z) != (
            empty.target.x,
            empty.target.z,
        )

    async def test_ecl_v0_fallback_no_located_location_none(
        self,
        cognition_store: MemoryStore,
        make_retriever: Callable[[], Retriever],
    ) -> None:
        # A retrieved memory with location=None is not "located" ⇒ spawn fallback.
        await _seed(
            cognition_store,
            agent_id="a1",
            mem_id="unlocated",
            x=0.0,
            z=0.0,
            zone=Zone.STUDY,
            importance=0.8,
            with_location=False,
        )
        res = await resolve_destination(
            make_retriever(),
            agent_id="a1",
            query=_QUERY,
            here=geometry.default_spawn(Zone.AGORA),
            destination_zone=Zone.AGORA,
            micro_rng=random.Random("none"),
        )
        spawn = geometry.default_spawn(Zone.AGORA)
        assert res.resolved_from == "spawn"
        assert (res.target.x, res.target.z) == (spawn.x, spawn.z)
        assert res.provenance == ()

    async def test_ecl_v0_fallback_total_weight_non_positive(self) -> None:
        # Located memory but zero total weight ⇒ spawn fallback (no division blow-up).
        stub = _StubRetriever([_rm(5.0, 5.0, strength=0.0, mem_id="zero")])
        res = await resolve_destination(
            stub,
            agent_id="a1",
            query=_QUERY,
            here=geometry.default_spawn(Zone.GARDEN),
            destination_zone=Zone.GARDEN,
            micro_rng=random.Random("zero"),
        )
        spawn = geometry.default_spawn(Zone.GARDEN)
        assert res.resolved_from == "spawn"
        assert (res.target.x, res.target.z) == (spawn.x, spawn.z)


# --------------------------------------------------------------------------- #
# AC4 — history-dependent move target
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_ecl_v0_move_msg_history_dependent(
    cognition_store: MemoryStore,
    make_retriever: Callable[[], Retriever],
) -> None:
    sx, _sy, sz = geometry.ZONE_CENTERS[Zone.STUDY]
    await _seed(
        cognition_store,
        agent_id="a1",
        mem_id="only",
        x=sx + 5.0,
        z=sz - 5.0,
        zone=Zone.STUDY,
        importance=0.7,
    )
    res = await resolve_destination(
        make_retriever(),
        agent_id="a1",
        query=_QUERY,
        here=geometry.default_spawn(Zone.STUDY),
        destination_zone=Zone.STUDY,
        micro_rng=random.Random("hist"),
    )
    spawn = geometry.default_spawn(Zone.STUDY)
    assert res.resolved_from == "memory_centroid"
    assert (res.target.x, res.target.z) != (spawn.x, spawn.z)


# --------------------------------------------------------------------------- #
# strength_weighted_centroid — exact math (supports AC2)
# --------------------------------------------------------------------------- #


class TestStrengthWeightedCentroid:
    """The centroid helper is an exact importance-weighted mean with a fallback."""

    def test_empty_returns_none(self) -> None:
        assert strength_weighted_centroid([]) is None

    def test_zero_total_weight_returns_none(self) -> None:
        assert strength_weighted_centroid([_rm(1.0, 1.0, 0.0)]) is None

    def test_non_positive_total_returns_none(self) -> None:
        assert (
            strength_weighted_centroid([_rm(1.0, 1.0, -1.0), _rm(2.0, 2.0, 1.0)])
            is None
        )

    def test_weighted_mean_is_exact(self) -> None:
        centroid = strength_weighted_centroid(
            [_rm(0.0, 0.0, 1.0, "a"), _rm(4.0, 8.0, 3.0, "b")]
        )
        assert centroid == (
            (1.0 * 0.0 + 3.0 * 4.0) / 4.0,
            (1.0 * 0.0 + 3.0 * 8.0) / 4.0,
        )


# --------------------------------------------------------------------------- #
# EclRecordMode — lightweight deterministic config
# --------------------------------------------------------------------------- #


class TestEclRecordMode:
    """The config carries only determinism handles, no trace/manifest types."""

    def _mode(self) -> EclRecordMode:
        return EclRecordMode(run_id="r0", retrieval_now=_FIXED_NOW, base_ts=_FIXED_NOW)

    def test_defaults(self) -> None:
        mode = self._mode()
        assert mode.k_ecl == K_ECL
        assert mode.reflection_disabled is True
        assert mode.move_decision_sink is None

    def test_named_substreams_are_deterministic_and_distinct(self) -> None:
        mode = self._mode()
        a1 = mode.substream("agent", "micro").random()
        a2 = self._mode().substream("agent", "micro").random()
        assert a1 == a2  # same run_id/agent/stream ⇒ byte-identical
        tie = mode.substream("agent", "tie").random()
        assert a1 != tie  # different stream ⇒ different sequence

    def test_deterministic_ids_and_timestamps(self) -> None:
        mode = self._mode()
        assert mode.memory_id("agent", 7) == "ecl-agent-0007"
        assert mode.memory_created_at(0) == _FIXED_NOW
        assert (mode.memory_created_at(5) - _FIXED_NOW).total_seconds() == 5.0


# --------------------------------------------------------------------------- #
# AC5 — measurement-line non-re-entry (import / output guard, not a word ban)
# --------------------------------------------------------------------------- #


class TestNoMeasurementReentry:
    """AC5: the module imports no measurement machinery and defines no floor/
    landscape/verdict output identifier (docstrings may still *name* them)."""

    def test_no_measurement_imports(self) -> None:
        banned_prefix = ("erre_sandbox.evidence",)
        banned_sub = ("spdm", "runningness")
        for node in ast.walk(_MODULE_TREE):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                assert not node.module.startswith(banned_prefix), node.module
                assert not any(s in node.module for s in banned_sub), node.module
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(banned_prefix), alias.name
                    assert not any(s in alias.name for s in banned_sub), alias.name

    def test_no_measurement_output_identifiers(self) -> None:
        # Identifier-level guard (Codex TASK-PRE LOW): the docstring's "NOT a
        # structural-floor verdict" must not false-positive, so we inspect defined
        # names — not source text — for measurement-output tokens.
        banned = ("floor", "landscape", "verdict", "jaccard", "divergence", "r_min")
        for node in ast.walk(_MODULE_TREE):
            names: list[str] = []
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                names.append(node.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names.append(node.target.id)
            elif isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                names.append(node.name)
            elif isinstance(node, ast.arg):
                names.append(node.arg)
            for name in names:
                low = name.lower()
                assert not any(tok in low for tok in banned), name
