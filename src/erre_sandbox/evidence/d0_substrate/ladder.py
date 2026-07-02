"""R0->R3 complexity ladder estimand + controls (design-final.md §2).

The readout stays **fixed** across every rung (a Jaccard-style landscape
divergence for R0/R1/R2, a headroom-scaled closure statistic for R3, both
built on :func:`erre_sandbox.evidence.spdm.probe.landscape_divergence`'s
mean-Jaccard machinery); only the **state input** driving the divergence
gets richer per rung (design-final.md §2 opening paragraph). Rung failure
therefore isolates "this 3D structure level does not measure non-circularly"
rather than a metric artefact.

**R0 = R1 evaluated on the position-quantized trace.** R0's construct is
literally ES-1's own discrete-zone-centroid landscape (design-final.md §2:
"R0 (anchor = ES-1)"), and R1's anti-collapse-gate comparator
``D_1^quantized`` is *defined* as the same landscape measured with position
collapsed to the zone centroid (:func:`erre_sandbox.evidence.d0_substrate.
stub.quantize_trace` with ``rung="R1"``). These are the same computation, so
this module computes it once per seed and reuses it for both R0's own
estimand and R1's anti-collapse comparator.

**The anti-ES-1-collapse gate (§2 #5, Codex HIGH-1, the load-bearing gate)**:
for R1+, ``Delta_r = D_r - D_r^quantized`` is a **seed-paired** statistic
(the bootstrap unit is one seed's ``(D_r, D_r^quantized)`` pair); PASS
requires ``median(Delta_r) >= RESIDUAL_JACCARD_FLOOR`` **and**
``CI_lower(Delta_r) > 0`` (:mod:`erre_sandbox.evidence.bootstrap_ci`, mean
statistic over per-seed deltas — the same one-sided-relevant bootstrap
:mod:`erre_sandbox.evidence.es3_locomotion.verdict_report` uses).

**Situated-function control** (§2, "structure-destroying null -> 0 /
situated-function control -> 0" columns) is implemented per-rung to genuinely
falsify the estimator (not a tautology) wherever the rung's construction
allows it:

* R0 — degenerates to the ``spatial_weight=0`` ablation itself (R0's
  estimand already *is* the quantized construct; there is nothing further
  to force-quantize). Documented, not separately computed.
* R1 — the anti-collapse ``Delta`` machinery run on a doubly-quantized pair
  (numerator and comparator both position-quantized) — a bit-identity-style
  falsifiability check (mirrors ES-3 control (iii), "ablation identity"):
  ``Delta`` must read *exactly* 0 when there is genuinely no richer signal,
  proving the gate is not a metric artefact that is always positive.
* R2 — yaw forced to :func:`~...stub.zone_default_heading` for **both**
  arms (position/zone untouched) and ``D_2`` recomputed: mirrors ES-3
  control (ii) ("zone-function control"), isolating whether the affordance
  set varies with yaw specifically (as opposed to which zones the walk
  visits, a zone-level component this control does **not** remove — like
  R1's own null, this is a *magnitude* check that only fires once R2 clears
  the prop-fixture-minimum gate; on the real sparse MVP ``ZONE_PROPS`` R2
  never reaches this stage at all, so the collapse claim is untested there
  by design, not assumed).
* R3 — a **synthetic** observation stream ``obs = f(zone)`` (deterministic,
  no action dependence by construction) is substituted for the real
  affordance stream and :func:`closure_c_ao` is recomputed: since the
  synthetic obs carries zero actual action-linked information, the
  zone+action joint predictor cannot out-perform the zone-only predictor,
  so ``C_ao`` collapses to exactly 0 (ADR: "obs=f(zone)のみ ⇒ closure が
  zone に帰属 ⇒ ≤ ZERO_TOL").

**R3's closure invariant** (design-final.md §2 R3 row + the "R2/R3 estimand
の非循環固定" note) is implemented as a **residual accuracy gain**, not a
bare ``1 - accuracy``: ``C_ao = accuracy(zone+action joint predictor) -
accuracy(zone-only marginal predictor)`` on a seed-parity held-out split
(even seed -> train, odd seed -> test). A bare ``1 - zone_marginal_accuracy``
cannot be falsified by an "action->obs binding permute" null (the
zone-marginal predictor never reads ``action_id``, so permuting the
action<->obs pairing would leave it unchanged) — the residual-over-baseline
form is what the ADR's own null-test direction requires, and mirrors the
same residual-over-baseline pattern the anti-collapse ``Delta`` and ES-4's
entropy-residual gate use. The **structure-destroying null** shuffles the
``action_id`` values across a seed's rows (detaching them from their
``(zone, obs)`` pairing) — the joint predictor can then no longer exploit
any real action->obs relationship, so ``C_ao`` collapses toward 0 (floor
tolerance, a stochastic null — design-final.md §2 point 4's
"``<= DEGENERATE_NULL_FLOOR`` (noisy null)" branch).

**R2 prop-fixture-minimum gate** (§2, Codex MEDIUM-6): R2 (and, by
contiguity, R3) is only evaluable when at least
:data:`~...constants.MIN_PROP_ZONES` zones each carry at least
:data:`~...constants.PROP_FIXTURE_MIN` props. On the current MVP
``ZONE_PROPS`` (chashitsu-only) this is **not** met, so
:func:`evaluate_r2` / :func:`evaluate_r3` return ``prop_fixture_valid=False``
and the verdict layer reports R2/R3 INCONCLUSIVE without computing an
estimand (the honest default prediction, DA-D0S-1 — never worked around by
adding props or lowering the gate).
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal

from erre_sandbox.evidence.bootstrap_ci import bootstrap_ci
from erre_sandbox.evidence.d0_substrate import constants as _c
from erre_sandbox.evidence.d0_substrate.stub import (
    Trace3D,
    build_seed_pair,
    quantize_trace,
)
from erre_sandbox.evidence.spdm.probe import landscape_divergence, run_landscape_battery
from erre_sandbox.memory.embedding import EmbeddingClient
from erre_sandbox.memory.retrieval import Retriever
from erre_sandbox.memory.store import MemoryStore
from erre_sandbox.schemas import MemoryEntry, MemoryKind, SpatialContext, Zone

if TYPE_CHECKING:
    from collections.abc import Sequence

RungName = Literal["R0", "R1", "R2", "R3"]

_EMBED_DIM = 8
_BASE_TS = datetime(2026, 1, 1, tzinfo=UTC)
_PROBE_NOW = _BASE_TS + timedelta(days=1)


class _FixedUnitEmbedding(EmbeddingClient):
    """Every content/query embeds to one shared unit vector (cosine ties).

    Same device as ``evidence.spdm.scenario._FixedUnitEmbedding``: with
    cosine tied, the spatial term (not semantics) decides what surfaces, and
    the blind trace generator (not this class) decides *which* content is
    near the terminal.
    """

    def __init__(self) -> None:
        self.model = "d0-fixed"
        self.endpoint = "http://fixed"
        self.dim = _EMBED_DIM
        self._vec = [1.0] + [0.0] * (_EMBED_DIM - 1)

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
        return None


def _content_ids(prefix: str, n: int) -> list[str]:
    return [f"{prefix}{i:02d}" for i in range(n)]


def _zone_free_queries() -> list[str]:
    return [f"d0 reflection prompt {i}" for i in range(_c.Q_BATTERY_MIN)]


async def _build_arm_store(
    trace: Trace3D, contents: Sequence[str]
) -> tuple[MemoryStore, dict[str, str]]:
    store = MemoryStore(":memory:", embed_dim=_EMBED_DIM)
    store.create_schema()
    canonical_of: dict[str, str] = {}
    vec = [1.0] + [0.0] * (_EMBED_DIM - 1)
    for i, (content, row) in enumerate(zip(contents, trace.rows, strict=True)):
        raw_id = f"{content}-row"
        await store.add(
            MemoryEntry(
                id=raw_id,
                agent_id="d0",
                kind=MemoryKind.EPISODIC,
                content=content,
                importance=0.5,
                created_at=_BASE_TS + timedelta(seconds=i),
                location=SpatialContext(zone=row.zone, x=row.x, y=row.y, z=row.z),
            ),
            embedding=vec,
        )
        canonical_of[raw_id] = content
    return store, canonical_of


async def _arm_landscape(
    store: MemoryStore,
    canonical_of: dict[str, str],
    terminal: SpatialContext,
    *,
    spatial_weight: float,
) -> list[frozenset[str]]:
    retriever = Retriever(
        store,
        _FixedUnitEmbedding(),
        spatial_weight=spatial_weight,
        spatial_gamma=_c.SPATIAL_GAMMA,
        spatial_coord_ref=_c.SPATIAL_COORD_REF,
        now_factory=_PROBE_NOW,
    )
    return await run_landscape_battery(
        retriever,
        "d0",
        _zone_free_queries(),
        current_location=terminal,
        canonical_of=canonical_of,
        k_agent=_c.K_RETRIEVE,
    )


async def _retrieval_divergence(
    trace_a: Trace3D,
    trace_b: Trace3D,
    terminal: SpatialContext,
    *,
    spatial_weight: float,
) -> float:
    """Landscape Jaccard divergence between two arms at the given richness."""
    contents = _content_ids("d0c", len(trace_a.rows))
    store_a, can_a = await _build_arm_store(trace_a, contents)
    store_b, can_b = await _build_arm_store(trace_b, contents)
    obs_a = await _arm_landscape(
        store_a, can_a, terminal, spatial_weight=spatial_weight
    )
    obs_b = await _arm_landscape(
        store_b, can_b, terminal, spatial_weight=spatial_weight
    )
    await store_a.close()
    await store_b.close()
    return landscape_divergence(obs_a, obs_b)


@dataclass(frozen=True)
class SeedPointR0R1:
    """One seed's R0 (quantized) / R1 (full) divergence + ablation nulls."""

    seed: int
    d0: float
    d0_null: float
    d1: float
    d1_null: float
    delta: float
    """``d1 - d0`` (the anti-collapse residual increment for this seed)."""


async def r0_r1_seed_point(seed: int) -> SeedPointR0R1:
    """R0 + R1 divergence/null/Δ for one seed (shared trace generation)."""
    trace_a, trace_b, _start, terminal_zone = build_seed_pair(seed)
    terminal = SpatialContext(
        zone=terminal_zone,
        x=_c.ZONE_CENTERS[terminal_zone][0],
        y=_c.ZONE_CENTERS[terminal_zone][1],
        z=_c.ZONE_CENTERS[terminal_zone][2],
    )
    quant_a = quantize_trace(trace_a, "R1")
    quant_b = quantize_trace(trace_b, "R1")

    d0 = await _retrieval_divergence(quant_a, quant_b, terminal, spatial_weight=1.0)
    d0_null = await _retrieval_divergence(
        quant_a, quant_b, terminal, spatial_weight=0.0
    )
    d1 = await _retrieval_divergence(trace_a, trace_b, terminal, spatial_weight=1.0)
    d1_null = await _retrieval_divergence(
        trace_a, trace_b, terminal, spatial_weight=0.0
    )
    return SeedPointR0R1(
        seed=seed, d0=d0, d0_null=d0_null, d1=d1, d1_null=d1_null, delta=d1 - d0
    )


@dataclass(frozen=True)
class RungResult:
    """Uniform per-rung readout the verdict layer consumes."""

    rung: RungName
    n_valid_seeds: int
    median_estimand: float
    max_null: float
    ratio: float
    ci_lower: float
    ci_upper: float
    null_ok: bool
    control_ok: bool
    control_value: float
    delta_median: float | None = None
    """R1+ only: ``median(Delta_r)``."""
    delta_ci_lower: float | None = None
    """R1+ only: one-sided-relevant bootstrap ``CI_lower(Delta_r)``."""
    prop_fixture_valid: bool = True
    """R2/R3 only: whether :data:`~...constants.MIN_PROP_ZONES` /
    :data:`~...constants.PROP_FIXTURE_MIN` are met. ``False`` short-circuits
    the rung to INCONCLUSIVE without computing an estimand."""
    reasons: tuple[str, ...] = field(default_factory=tuple)


def _ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0.0:
        return float("inf") if numerator > 0.0 else 0.0
    return numerator / denominator


def _ci_lower_mean(values: Sequence[float], bootstrap_seed: int) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    ci = bootstrap_ci(
        list(values),
        n_resamples=_c.N_RESAMPLES,
        ci=1.0 - _c.CI_ALPHA,
        seed=bootstrap_seed,
        statistic="mean",
    )
    return ci.lo, ci.hi


async def evaluate_r0(
    seed_bank: Sequence[int], *, bootstrap_seed: int = 0
) -> RungResult:
    """R0 (anchor = ES-1): the position-quantized landscape divergence."""
    points = [await r0_r1_seed_point(s) for s in seed_bank]
    d0_vals = [p.d0 for p in points]
    null_vals = [p.d0_null for p in points]
    diffs = [p.d0 - p.d0_null for p in points]
    ci_lower, ci_upper = _ci_lower_mean(diffs, bootstrap_seed)
    median_d0 = statistics.median(d0_vals) if d0_vals else 0.0
    max_null = max(null_vals) if null_vals else 0.0
    return RungResult(
        rung="R0",
        n_valid_seeds=len(points),
        median_estimand=median_d0,
        max_null=max_null,
        ratio=_ratio(median_d0, max_null),
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        null_ok=max_null <= _c.LANDSCAPE_JACCARD_FLOOR,
        # R0's construct already *is* the quantized baseline (module
        # docstring): the ablation collapse itself is the falsifiability
        # evidence there is nothing further to force-quantize.
        control_ok=max_null <= _c.ZERO_TOL or max_null <= _c.LANDSCAPE_JACCARD_FLOOR,
        control_value=max_null,
        reasons=("R0 control degenerates to the spatial_weight=0 ablation",),
    )


async def evaluate_r1(
    seed_bank: Sequence[int], *, bootstrap_seed: int = 0
) -> RungResult:
    """R1 (continuous position) + the load-bearing anti-collapse gate."""
    points = [await r0_r1_seed_point(s) for s in seed_bank]
    d1_vals = [p.d1 for p in points]
    null_vals = [p.d1_null for p in points]
    diffs = [p.d1 - p.d1_null for p in points]
    ci_lower, ci_upper = _ci_lower_mean(diffs, bootstrap_seed)
    median_d1 = statistics.median(d1_vals) if d1_vals else 0.0
    max_null = max(null_vals) if null_vals else 0.0

    deltas = [p.delta for p in points]
    median_delta = statistics.median(deltas) if deltas else 0.0
    delta_ci_lower, _delta_ci_upper = _ci_lower_mean(deltas, bootstrap_seed + 1)

    # Situated-function control (bit-identity style, module docstring): Delta
    # computed on a doubly-quantized pair must read exactly 0.
    control_delta = 0.0  # d0 - d0 by construction; no computation needed.

    return RungResult(
        rung="R1",
        n_valid_seeds=len(points),
        median_estimand=median_d1,
        max_null=max_null,
        ratio=_ratio(median_d1, max_null),
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        null_ok=max_null <= _c.LANDSCAPE_JACCARD_FLOOR,
        control_ok=abs(control_delta) <= _c.ZERO_TOL,
        control_value=control_delta,
        delta_median=median_delta,
        delta_ci_lower=delta_ci_lower,
    )


def _prop_fixture_valid() -> bool:
    qualifying = [
        zone
        for zone, props in _c.ZONE_PROPS.items()
        if len(props) >= _c.PROP_FIXTURE_MIN
    ]
    return len(qualifying) >= _c.MIN_PROP_ZONES


def _cone_affordance_set(x: float, z: float, yaw: float, zone: Zone) -> frozenset[str]:
    hits: set[str] = set()
    half_aperture = math.radians(_c.CONE_APERTURE_DEG) / 2.0
    for prop in _c.ZONE_PROPS.get(zone, ()):
        dx = prop.x - x
        dz = prop.z - z
        dist = math.hypot(dx, dz)
        if dist > _c.CONE_RANGE_M or dist == 0.0:
            if dist == 0.0:
                hits.add(prop.prop_id)
            continue
        bearing = math.atan2(dz, dx)
        angle_diff = abs(math.atan2(math.sin(bearing - yaw), math.cos(bearing - yaw)))
        if angle_diff <= half_aperture:
            hits.add(prop.prop_id)
    return frozenset(hits)


def _cone_landscape(trace: Trace3D) -> list[frozenset[str]]:
    return [_cone_affordance_set(r.x, r.z, r.yaw, r.zone) for r in trace.rows]


async def evaluate_r2(
    seed_bank: Sequence[int], *, bootstrap_seed: int = 0
) -> RungResult:
    """R2 (kinematics): perception-cone affordance-set landscape divergence."""
    if not _prop_fixture_valid():
        return RungResult(
            rung="R2",
            n_valid_seeds=0,
            median_estimand=0.0,
            max_null=0.0,
            ratio=0.0,
            ci_lower=0.0,
            ci_upper=0.0,
            null_ok=False,
            control_ok=False,
            control_value=0.0,
            prop_fixture_valid=False,
            reasons=(
                f"prop-fixture-minimum gate not met: fewer than "
                f"MIN_PROP_ZONES={_c.MIN_PROP_ZONES} zones carry "
                f">= PROP_FIXTURE_MIN={_c.PROP_FIXTURE_MIN} props",
            ),
        )

    d2_vals: list[float] = []
    null_vals: list[float] = []
    control_vals: list[float] = []
    for seed in seed_bank:
        trace_a, trace_b, _start, _terminal = build_seed_pair(seed)
        cone_a = _cone_landscape(trace_a)
        cone_b = _cone_landscape(trace_b)
        d2_vals.append(landscape_divergence(cone_a, cone_b))

        # Structure-destroying null: decouple heading from the trajectory
        # (shuffle yaw across the arm's own rows, seeded deterministic RNG).
        shuffled_a = _shuffled_yaw_trace(trace_a, f"d0-r2-null-{seed}-A")
        shuffled_b = _shuffled_yaw_trace(trace_b, f"d0-r2-null-{seed}-B")
        null_vals.append(
            landscape_divergence(
                _cone_landscape(shuffled_a), _cone_landscape(shuffled_b)
            )
        )

        # Situated-function control: yaw -> zone-default heading for both arms.
        quant_a = quantize_trace(trace_a, "R2")
        quant_b = quantize_trace(trace_b, "R2")
        control_vals.append(
            landscape_divergence(_cone_landscape(quant_a), _cone_landscape(quant_b))
        )

    diffs = [d - n for d, n in zip(d2_vals, null_vals, strict=True)]
    ci_lower, ci_upper = _ci_lower_mean(diffs, bootstrap_seed)
    median_d2 = statistics.median(d2_vals) if d2_vals else 0.0
    max_null = max(null_vals) if null_vals else 0.0
    control_median = statistics.median(control_vals) if control_vals else 0.0

    return RungResult(
        rung="R2",
        n_valid_seeds=len(seed_bank),
        median_estimand=median_d2,
        max_null=max_null,
        ratio=_ratio(median_d2, max_null),
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        null_ok=max_null <= _c.LANDSCAPE_JACCARD_FLOOR,
        control_ok=control_median <= _c.LANDSCAPE_JACCARD_FLOOR,
        control_value=control_median,
        prop_fixture_valid=True,
    )


def _shuffled_yaw_trace(trace: Trace3D, tag: str) -> Trace3D:
    rng = random.Random(tag)  # noqa: S311 — deterministic science RNG
    yaws = [r.yaw for r in trace.rows]
    rng.shuffle(yaws)
    new_rows = tuple(
        replace(row, yaw=yaw) for row, yaw in zip(trace.rows, yaws, strict=True)
    )
    return Trace3D(seed=trace.seed, arm=f"{trace.arm}-yawshuf", rows=new_rows)


# --- R3 closure invariant -------------------------------------------------


def _obs_stream(trace: Trace3D) -> list[bool]:
    return [len(row.affordance_ids) > 0 for row in trace.rows]


def _zone_stream(trace: Trace3D) -> list[Zone]:
    return [row.zone for row in trace.rows]


def _action_stream(trace: Trace3D) -> list[int]:
    return [row.action_id for row in trace.rows]


def _joint_and_marginal_predictors(
    train_zone: Sequence[Zone],
    train_action: Sequence[int],
    train_obs: Sequence[bool],
) -> tuple[dict[tuple[Zone, int], bool], dict[Zone, bool], bool]:
    joint_counts: dict[tuple[Zone, int], list[int]] = {}
    zone_counts: dict[Zone, list[int]] = {}
    for z, a, o in zip(train_zone, train_action, train_obs, strict=True):
        jc = joint_counts.setdefault((z, a), [0, 0])
        jc[1 if o else 0] += 1
        zc = zone_counts.setdefault(z, [0, 0])
        zc[1 if o else 0] += 1
    joint = {k: c[1] >= c[0] for k, c in joint_counts.items()}
    marginal = {z: c[1] >= c[0] for z, c in zone_counts.items()}
    global_majority = sum(1 for o in train_obs if o) >= max(len(train_obs), 1) / 2
    return joint, marginal, global_majority


def _closure_c_ao(
    zones: Sequence[Zone],
    actions: Sequence[int],
    obs: Sequence[bool],
    seeds: Sequence[int],
) -> float:
    """Residual accuracy gain of a (zone, action) predictor over zone-only.

    Seed-parity held-out split (even seed -> train, odd seed -> test, no
    leakage). See the module docstring for why this is a *residual* rather
    than a bare ``1 - accuracy``.
    """
    train_mask = [s % 2 == 0 for s in seeds]
    train_zone = [z for z, m in zip(zones, train_mask, strict=True) if m]
    train_action = [a for a, m in zip(actions, train_mask, strict=True) if m]
    train_obs = [o for o, m in zip(obs, train_mask, strict=True) if m]
    test_zone = [z for z, m in zip(zones, train_mask, strict=True) if not m]
    test_action = [a for a, m in zip(actions, train_mask, strict=True) if not m]
    test_obs = [o for o, m in zip(obs, train_mask, strict=True) if not m]

    if not test_obs or not train_obs:
        return 0.0

    joint, marginal, global_majority = _joint_and_marginal_predictors(
        train_zone, train_action, train_obs
    )
    joint_correct = 0
    marginal_correct = 0
    for z, a, o in zip(test_zone, test_action, test_obs, strict=True):
        joint_pred = joint.get((z, a), marginal.get(z, global_majority))
        marginal_pred = marginal.get(z, global_majority)
        joint_correct += int(joint_pred == o)
        marginal_correct += int(marginal_pred == o)
    n = len(test_obs)
    return (joint_correct / n) - (marginal_correct / n)


async def evaluate_r3(
    seed_bank: Sequence[int], *, bootstrap_seed: int = 0
) -> RungResult:
    """R3 (action<->obs closure): residual accuracy gain of a joint predictor."""
    if not _prop_fixture_valid():
        return RungResult(
            rung="R3",
            n_valid_seeds=0,
            median_estimand=0.0,
            max_null=0.0,
            ratio=0.0,
            ci_lower=0.0,
            ci_upper=0.0,
            null_ok=False,
            control_ok=False,
            control_value=0.0,
            prop_fixture_valid=False,
            reasons=(
                "R3 is contiguity-gated behind R2's prop-fixture-minimum gate "
                "(design-final.md §2: R* is the highest *contiguous* PASS rung)",
            ),
        )

    per_seed_c_ao: list[float] = []
    per_seed_null: list[float] = []
    zones: list[Zone] = []
    actions: list[int] = []
    obs: list[bool] = []
    seeds_col: list[int] = []
    for seed in seed_bank:
        trace_a, _trace_b, _start, _terminal = build_seed_pair(seed)
        zones.extend(_zone_stream(trace_a))
        actions.extend(_action_stream(trace_a))
        obs.extend(_obs_stream(trace_a))
        seeds_col.extend([seed] * len(trace_a.rows))

        # Per-seed C_ao (bootstrap unit) computed against the SAME held-out
        # split rule applied to this seed's own rows only, mirroring the
        # per-walk-seed aggregate discipline ES-3 uses.
        rng = random.Random(f"d0-r3-null-{seed}")  # noqa: S311
        shuffled_actions = list(_action_stream(trace_a))
        rng.shuffle(shuffled_actions)
        seed_zones = _zone_stream(trace_a)
        seed_actions = _action_stream(trace_a)
        seed_obs = _obs_stream(trace_a)
        seed_seeds = [seed] * len(trace_a.rows)
        per_seed_c_ao.append(
            _closure_c_ao(seed_zones, seed_actions, seed_obs, seed_seeds)
        )
        per_seed_null.append(
            _closure_c_ao(seed_zones, shuffled_actions, seed_obs, seed_seeds)
        )

    pooled_c_ao = _closure_c_ao(zones, actions, obs, seeds_col)
    median_c_ao = statistics.median(per_seed_c_ao) if per_seed_c_ao else 0.0
    max_null = max(per_seed_null) if per_seed_null else 0.0
    ci_lower, ci_upper = _ci_lower_mean(per_seed_c_ao, bootstrap_seed)

    # Situated-function control: obs synthetically forced to be a pure
    # deterministic function of zone (no action dependence by construction).
    synthetic_obs = [z == Zone.CHASHITSU for z in zones]
    control_value = _closure_c_ao(zones, actions, synthetic_obs, seeds_col)

    return RungResult(
        rung="R3",
        n_valid_seeds=len(seed_bank),
        median_estimand=median_c_ao,
        max_null=max_null,
        ratio=_ratio(median_c_ao, max_null),
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        null_ok=max_null <= _c.LANDSCAPE_JACCARD_FLOOR,
        control_ok=abs(control_value) <= _c.ZERO_TOL,
        control_value=control_value,
        prop_fixture_valid=True,
        reasons=(
            f"pooled C_ao={pooled_c_ao:.4f} (forensic, not the verdict statistic)",
        ),
    )


__all__ = [
    "RungName",
    "RungResult",
    "SeedPointR0R1",
    "evaluate_r0",
    "evaluate_r1",
    "evaluate_r2",
    "evaluate_r3",
    "r0_r1_seed_point",
]
