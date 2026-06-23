"""Deterministic end-to-end apparatus test for the M13-ES1 SPDM probe.

Builds the full apparatus through the **real** retrieval path (the production
``Retriever`` + ``MemoryStore``, not a re-implemented stub),
so it exercises the SPDM spatial term, the ``location`` round-trip, the
canonical-content-id metric (Codex HIGH-2), the ``mark_recalled=False`` battery
(Codex HIGH-3), and the frozen verdict together — not a re-implemented stub.

Two same-base "individuals" form the *same* logical contents (same canonical ids,
same embeddings, same created_at order) at *different* formation locations (the only
difference between path-A and path-B). With the spatial term ON, which memories
surface near a matched terminal location diverges; with it OFF the landscape
collapses to identity — the falsifiable signature the Gate-2 verdict reads.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal

import pytest

from erre_sandbox.evidence.spdm import constants as c
from erre_sandbox.evidence.spdm.probe import (
    SeedResult,
    jaccard_distance,
    landscape_divergence,
    run_landscape_battery,
)
from erre_sandbox.evidence.spdm.verdict_report import Gate1Result, evaluate_gate2
from erre_sandbox.memory.embedding import EmbeddingClient
from erre_sandbox.memory.retrieval import Retriever
from erre_sandbox.memory.store import MemoryStore
from erre_sandbox.schemas import MemoryEntry, MemoryKind, Position, SpatialContext, Zone

if TYPE_CHECKING:
    from collections.abc import Sequence

_DIM = 8
_TERMINAL = Position(x=0.0, y=0.0, z=0.0, zone=Zone.STUDY)
_BASE_TS = datetime(2026, 1, 1, tzinfo=UTC)


class _FixedEmbedding(EmbeddingClient):
    """All contents + queries share one unit vector ⇒ cosine ties ⇒ the spatial
    term (not semantics) decides which memories surface. Zone-free query strings are
    accepted but ignored (the vector is fixed)."""

    def __init__(self) -> None:
        self.model = "fake"
        self.endpoint = "http://fake"
        self.dim = _DIM
        self._vec = [1.0] + [0.0] * (_DIM - 1)

    async def embed(self, _text: str) -> list[float]:
        return list(self._vec)

    async def embed_query(self, _text: str) -> list[float]:
        return list(self._vec)

    async def embed_document(self, _text: str) -> list[float]:
        return list(self._vec)

    async def embed_many(
        self,
        texts: Sequence[str],
        *,
        kind: Literal["query", "document"],  # noqa: ARG002
    ) -> list[list[float]]:
        return [list(self._vec) for _ in texts]

    async def close(self) -> None:
        pass


def _zone_free_queries() -> list[str]:
    # Q_BATTERY_MIN zone-vocabulary-free queries (Codex HIGH-3): no zone token.
    return [f"reflection prompt {i}" for i in range(c.Q_BATTERY_MIN)]


async def _build_arm(
    contents: Sequence[str],
    distances: Sequence[float],
) -> tuple[MemoryStore, dict[str, str]]:
    """One arm: M memories whose canonical id == content string, placed at the given
    distance from the terminal along +x. Returns the store and the raw-id→canonical map.
    """
    store = MemoryStore(":memory:", embed_dim=_DIM)
    store.create_schema()
    canonical_of: dict[str, str] = {}
    vec = [1.0] + [0.0] * (_DIM - 1)
    for i, (content, dist) in enumerate(zip(contents, distances, strict=True)):
        raw_id = f"{content}-row"
        loc = SpatialContext(zone=Zone.STUDY, x=float(dist), y=0.0, z=0.0)
        await store.add(
            MemoryEntry(
                id=raw_id,
                agent_id="spdm",
                kind=MemoryKind.EPISODIC,
                content=content,
                importance=0.5,
                created_at=_BASE_TS + timedelta(seconds=i),
                location=loc,
            ),
            embedding=vec,
        )
        canonical_of[raw_id] = content  # canonical content id (Codex HIGH-2)
    return store, canonical_of


async def _arm_landscape(
    store: MemoryStore,
    canonical_of: dict[str, str],
    *,
    spatial_weight: float,
) -> list[frozenset[str]]:
    retriever = Retriever(
        store,
        _FixedEmbedding(),
        spatial_weight=spatial_weight,
        spatial_gamma=c.SPATIAL_GAMMA,
        spatial_coord_ref=c.SPATIAL_COORD_REF,
        now_factory=_BASE_TS + timedelta(days=1),
    )
    return await run_landscape_battery(
        retriever,
        "spdm",
        _zone_free_queries(),
        current_location=_TERMINAL,
        canonical_of=canonical_of,
    )


def _contents() -> list[str]:
    return [f"c{i:02d}" for i in range(c.M_MEMORIES)]


def _near_far(near_indices: set[int]) -> list[float]:
    """Distance vector: near indices at 0.2, far indices at 6.0 (well separated under
    gamma=0.5 ⇒ near prox ≈ 0.90, far prox ≈ 0.05)."""
    return [0.2 if i in near_indices else 6.0 for i in range(c.M_MEMORIES)]


async def _seed_result(seed: int) -> SeedResult:
    """One deterministic apparatus instantiation.

    path-A binds the first half of contents near the terminal, path-B the second
    half — the only difference is *where* the same contents were formed.
    """
    contents = _contents()
    half = c.M_MEMORIES // 2
    # Rotate the near-set by seed so each seed is a distinct (deterministic) instance.
    rot = seed % half
    a_near = {(i + rot) % c.M_MEMORIES for i in range(half)}
    b_near = set(range(c.M_MEMORIES)) - a_near

    store_a, can_a = await _build_arm(contents, _near_far(a_near))
    store_b, can_b = await _build_arm(contents, _near_far(b_near))

    # OBS (= ②-ON): same contents, different formation location, spatial ON.
    obs_a = await _arm_landscape(store_a, can_a, spatial_weight=1.0)
    obs_b = await _arm_landscape(store_b, can_b, spatial_weight=1.0)
    d_obs = landscape_divergence(obs_a, obs_b)

    # ④ (= ②-OFF): spatial weight 0 ⇒ content-only floor (must collapse).
    off_a = await _arm_landscape(store_a, can_a, spatial_weight=0.0)
    off_b = await _arm_landscape(store_b, can_b, spatial_weight=0.0)
    d_w0 = landscape_divergence(off_a, off_b)

    # ① path-label permutation: destroy the A/B path structure by giving *both*
    # arms the same (a_near) location assignment ⇒ landscape identical ⇒ noise floor.
    store_p, can_p = await _build_arm(contents, _near_far(a_near))
    perm_a = await _arm_landscape(store_a, can_a, spatial_weight=1.0)
    perm_b = await _arm_landscape(store_p, can_p, spatial_weight=1.0)
    d_perm = landscape_divergence(perm_a, perm_b)

    # ③ same-location/different-content: same locations, disjoint contents.
    alt_contents = [f"x{i:02d}" for i in range(c.M_MEMORIES)]
    store_c, can_c = await _build_arm(alt_contents, _near_far(a_near))
    sl_on_a = await _arm_landscape(store_a, can_a, spatial_weight=1.0)
    sl_on_b = await _arm_landscape(store_c, can_c, spatial_weight=1.0)
    d_sl_on = landscape_divergence(sl_on_a, sl_on_b)
    sl_off_a = await _arm_landscape(store_a, can_a, spatial_weight=0.0)
    sl_off_b = await _arm_landscape(store_c, can_c, spatial_weight=0.0)
    d_sl_off = landscape_divergence(sl_off_a, sl_off_b)

    for s in (store_a, store_b, store_p, store_c):
        await s.close()

    return SeedResult(
        seed=seed,
        d_obs=d_obs,
        d_null_permutation=d_perm,
        d_null_w0=d_w0,
        d_control_same_loc_on=d_sl_on,
        d_control_same_loc_off=d_sl_off,
    )


# ---------------------------------------------------------------------------
# metric primitives
# ---------------------------------------------------------------------------


def test_jaccard_distance_bounds() -> None:
    assert jaccard_distance(frozenset(), frozenset()) == 0.0
    assert jaccard_distance(frozenset("ab"), frozenset("ab")) == 0.0
    assert jaccard_distance(frozenset("ab"), frozenset("cd")) == 1.0
    assert jaccard_distance(frozenset("ab"), frozenset("bc")) == pytest.approx(2 / 3)


def test_landscape_divergence_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="arm length mismatch"):
        landscape_divergence([frozenset("a")], [frozenset("a"), frozenset("b")])


# ---------------------------------------------------------------------------
# apparatus integration: the real Retriever path
# ---------------------------------------------------------------------------


async def test_w0_ablation_collapses_to_identity() -> None:
    """Codex HIGH-2: with the spatial term OFF, the two arms' landscapes are
    identical on the canonical-id key (same contents) ⇒ divergence 0."""
    contents = _contents()
    store_a, can_a = await _build_arm(contents, _near_far(set(range(10))))
    store_b, can_b = await _build_arm(contents, _near_far(set(range(10, 20))))
    off_a = await _arm_landscape(store_a, can_a, spatial_weight=0.0)
    off_b = await _arm_landscape(store_b, can_b, spatial_weight=0.0)
    assert landscape_divergence(off_a, off_b) == 0.0
    await store_a.close()
    await store_b.close()


async def test_spatial_on_produces_divergence() -> None:
    """With the spatial term ON, path-A vs path-B surface different memories."""
    result = await _seed_result(seed=0)
    assert result.d_obs > c.DEGENERATE_NULL_FLOOR
    assert result.d_null_w0 <= c.DEGENERATE_NULL_FLOOR  # collapse
    assert result.d_null_permutation <= c.DEGENERATE_NULL_FLOOR  # path structure gone


async def test_full_apparatus_yields_go_verdict() -> None:
    """End-to-end: a strong path-distinct fixture clears every frozen GO condition."""
    seeds = [await _seed_result(seed=i) for i in range(c.N_SEED)]
    gate1 = Gate1Result(
        single_query_distance=seeds[0].d_obs,
        location_shuffle_null=seeds[0].d_null_permutation,
        ablation_w0_distance=seeds[0].d_null_w0,
        zone_free_distance=seeds[0].d_obs,
        zone_free_null=seeds[0].d_null_permutation,
    )
    assert gate1.passed
    verdict = evaluate_gate2(seeds, gate1, n_queries=c.Q_BATTERY_MIN)
    assert verdict.verdict == "GO", verdict.reasons
    assert verdict.ratio >= c.R_MIN
    assert verdict.ci_lower > 0.0
    assert verdict.median_d_obs >= c.DEGENERATE_NULL_FLOOR
    assert verdict.positive_control_ratio >= c.POSITIVE_CONTROL_RATIO_MIN


async def test_apparatus_reproducible() -> None:
    """Deterministic: the same seed yields byte-identical divergences."""
    a = await _seed_result(seed=3)
    b = await _seed_result(seed=3)
    assert (a.d_obs, a.d_null_w0, a.d_null_permutation) == (
        b.d_obs,
        b.d_null_w0,
        b.d_null_permutation,
    )
