"""Condition-axis resolution + injectable generation seam for M13-ES4 (§1 / §7).

Turns the frozen battery (:mod:`battery`) and the §5 constants into the
per-generation **requests** the GPU backend will run, *without* running any LLM
here. Generation is a single injectable seam — :data:`InferenceFn`, the same
shape ``golden_baseline.GoldenBaselineDriver`` uses — so Session 1 exercises the
whole apparatus under deterministic mocks and Session 2 swaps in the real SGLang
backend with no apparatus change.

Condition axis (``design-final.md`` §1):

* **A0** — λ=0 (null / ablation): ``loco_delta`` is the all-zero delta, so the
  resolved sampling is **bit-identical** to the ``loco_delta=None`` path.
* **A1** — λ ∈ [0.4, 0.6] (mid reach, loco temp ~+0.15).
* **A2** — λ ∈ [0.85, 1.0] (full reach, loco temp ~+0.30). dose-response primary.
* **M2** — a **distribution-matched** temperature control: a seed-shuffled copy of
  the A2 resolved-temperature multiset, applied as a fixed override (no live λ).
  Used for the (b) TOST equivalence (§2.4, Codex M-1).
* **F** — base + 0.8 over-heat, outside the actuator reach (forensic only, §2.5).

The actuator is the frozen ES-3 pure function with ``gain_p = 0`` (ES-4's
temperature-only actuator, Codex HIGH-1): ``locomotion_delta(LocomotionState(λ),
gain_t=0.3, gain_p=0)`` → ``compose_sampling(base, neutral, loco_delta)``. The
``mode_delta`` is the **neutral** (study, mode_delta=0) static delta, so locomotion
is the only temperature mover. The λ *distribution* per band is drawn from the
**reused ES-3 blind-walk generator** (``es3_locomotion.scenario``, read-only) so
the dose magnitudes are not designer knobs.

Seeds (``golden_baseline.derive_seed`` extended to persona × item × seed_idx):
A0/A1/A2 share **common seeds** per (persona, item) for the cluster-level paired
contrast (Codex HIGH-8). M2 uses **independent seeds** (§2.4 "独立 seed", a
disjoint offset) and the reference construction (:mod:`reference`) uses a third
disjoint ``REF_SEEDS`` range, so no verdict / control / reference generation ever
shares a seed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

from erre_sandbox.erre.locomotion_sampling import locomotion_delta
from erre_sandbox.evidence.es4_actuator import constants as _c
from erre_sandbox.evidence.es4_actuator.battery import (
    AutBattery,
    RatBattery,
    load_aut_battery,
    load_rat_battery,
)
from erre_sandbox.evidence.golden_baseline import derive_seed
from erre_sandbox.inference.sampling import ResolvedSampling, compose_sampling
from erre_sandbox.schemas import LocomotionState, SamplingBase, SamplingDelta

if TYPE_CHECKING:
    from collections.abc import Sequence

Condition = Literal["A0", "A1", "A2", "M2", "F", "REF"]
"""Generation conditions. A0/A1/A2/M2/F are verdict conditions (§1); ``REF`` is
the held-out reference-construction generation (:mod:`reference`, §2.2b) — it is
never returned by :func:`_aut_conditions` so it cannot enter the verdict."""

Phase = Literal["phase0", "phase1"]

ES4_SALT: Final[str] = "m13-es4-v1"
"""blake2b salt for ES-4 seed derivation (distinct from the m9 golden salt so the
seed streams never collide)."""

_NEUTRAL_DELTA: Final[SamplingDelta] = SamplingDelta()
"""mode = neutral (study, mode_delta = 0): locomotion is the only temperature
mover (§5 mode row)."""

# Disjoint seed-index offsets so verdict / M2 / reference generations never share
# a SGLang sampling seed (holdout discipline, §2.2b / §2.4).
_M2_SEED_OFFSET: Final[int] = 1_000
_REF_SEED_OFFSET: Final[int] = 1_000_000


def derive_unit_seed(persona_id: str, item_id: str, seed_idx: int) -> int:
    """Common per-generation SGLang seed for ``(persona, item, seed_idx)``.

    Condition-independent: A0/A1/A2 at the same ``seed_idx`` share this seed
    (common-seed pairing, §4.2). M2 and the reference use disjoint offsets via
    :func:`derive_m2_seed` / :func:`derive_ref_seed`.
    """
    return derive_seed(f"{persona_id}|{item_id}", seed_idx, salt=ES4_SALT)


def derive_m2_seed(persona_id: str, item_id: str, seed_idx: int) -> int:
    """Independent M2 seed (§2.4 "独立 seed"), disjoint from the verdict seeds."""
    return derive_seed(
        f"{persona_id}|{item_id}", _M2_SEED_OFFSET + seed_idx, salt=ES4_SALT
    )


def derive_ref_seed(object_id: str, ref_idx: int) -> int:
    """Held-out reference seed (§2.2b), disjoint from every verdict / M2 seed."""
    return derive_seed(f"ref|{object_id}", _REF_SEED_OFFSET + ref_idx, salt=ES4_SALT)


# --- λ band pool (reused ES-3 blind-walk generator, read-only) -----------------


def _blind_walk_lambda_pool() -> tuple[float, ...]:
    """All EMA λ values the frozen ES-3 blind walk produces over its seed bank.

    Imported lazily (read-only) so the dose-distribution per band is the genuine
    locomotion-history distribution, not a designer-chosen shape (§1).
    """
    from erre_sandbox.evidence.es3_locomotion import constants as _es3c  # noqa: PLC0415
    from erre_sandbox.evidence.es3_locomotion.scenario import (  # noqa: PLC0415
        default_seed_bank,
        ema_lambda,
        trajectory,
    )

    pool: list[float] = []
    for seed in default_seed_bank():
        walk = trajectory(seed)
        pool.extend(ema_lambda(walk.moves, _es3c.ALPHA))
    return tuple(pool)


def band_lambda_pool(band: tuple[float, float]) -> tuple[float, ...]:
    """Blind-walk λ values falling inside ``[lo, hi]`` (the dose band)."""
    lo, hi = band
    pool = tuple(x for x in _blind_walk_lambda_pool() if lo <= x <= hi)
    if not pool:  # pragma: no cover — bands are chosen to be populated
        raise ValueError(f"empty λ pool for band {band}")
    return pool


def lambda_for(
    band: tuple[float, float], persona_id: str, item_id: str, seed_idx: int
) -> float:
    """Deterministic λ in ``band`` for ``(persona, item, seed_idx)``.

    Picks from the blind-walk band pool by a derived index, so the per-condition
    dose is reproducible and drawn from the real locomotion distribution.
    """
    pool = band_lambda_pool(band)
    idx = derive_unit_seed(persona_id, item_id, seed_idx) % len(pool)
    return pool[idx]


# --- temperature resolution ---------------------------------------------------


def resolve_lambda_sampling(base: SamplingBase, lam: float) -> ResolvedSampling:
    """``compose_sampling(base, neutral, loco(λ, gain_t, gain_p=0))`` (§1)."""
    loco = locomotion_delta(
        LocomotionState(lam=lam), gain_t=_c.LOCO_GAIN_T, gain_p=_c.LOCO_GAIN_P
    )
    return compose_sampling(base, _NEUTRAL_DELTA, loco)


def resolve_fixed_temperature(
    base: SamplingBase, target_temperature: float
) -> ResolvedSampling:
    """Resolve a fixed-override temperature (M2 / F) through the clamp invariant.

    Built via the same ``compose_sampling`` path (so top_p / repeat_penalty stay
    at base, matching ``gain_p=0``) by deriving the temperature delta the override
    needs.
    """
    delta = SamplingDelta(temperature=target_temperature - base.temperature)
    return compose_sampling(base, _NEUTRAL_DELTA, delta)


# --- generation requests ------------------------------------------------------


@dataclass(frozen=True)
class GenerationRequest:
    """One unit of work the GPU backend will run (the injectable seam's input).

    ``lam`` is the λ that produced the temperature for the λ-driven conditions
    (A0/A1/A2); it is ``None`` for the fixed-override conditions (M2/F).
    """

    persona_id: str
    task: Literal["aut", "rat"]
    item_id: str
    condition: Condition
    seed: int
    seed_idx: int
    resolved: ResolvedSampling
    prompt: str
    num_predict: int
    lam: float | None


InferenceFn = Callable[[GenerationRequest], str]
"""Injectable generation seam: a request → the model's raw response text.

Session 1 passes deterministic mocks; Session 2 passes the real SGLang fp8
qwen3:8b backend (persona system prompt + think-suppression handled inside the
implementation, keyed off ``request.persona_id`` / ``request.resolved``)."""


@dataclass(frozen=True)
class Generation:
    """A request paired with the (mock or real) response text."""

    request: GenerationRequest
    response: str


def _aut_conditions(phase: Phase) -> tuple[Condition, ...]:
    return ("A0", "A1", "A2", "M2", "F") if phase == "phase1" else ("A0", "A1", "A2")


def _seed_count(condition: Condition, phase: Phase) -> int:
    if phase == "phase0":
        return _c.N_SEED_PHASE0
    return _c.N_SEED_PHASE1 // 2 if condition == "F" else _c.N_SEED_PHASE1


def _a2_temperature(
    base: SamplingBase, persona_id: str, item_id: str, seed_idx: int
) -> float:
    lam = lambda_for(_c.LAMBDA_BAND_A2, persona_id, item_id, seed_idx)
    return resolve_lambda_sampling(base, lam).temperature


def _m2_shuffled_temperatures(
    base: SamplingBase, persona_id: str, item_id: str, n_seed: int
) -> list[float]:
    """The A2 resolved-temperature multiset, seed-shuffled (distribution-matched).

    A deterministic derangement-free permutation keyed by (persona, item) so M2's
    temperature distribution equals A2's exactly (pre-flight multiset assert),
    while decoupling each seed's temperature from its A2 partner.
    """
    a2 = [_a2_temperature(base, persona_id, item_id, i) for i in range(n_seed)]
    order = sorted(
        range(n_seed),
        key=lambda i: derive_seed(f"m2shuf|{persona_id}|{item_id}", i, salt=ES4_SALT),
    )
    return [a2[j] for j in order]


def _build_aut_request(
    base: SamplingBase,
    persona_id: str,
    aut: AutBattery,
    item_idx: int,
    condition: Condition,
    seed_idx: int,
    m2_temps: Sequence[float] | None,
) -> GenerationRequest:
    item = aut.items[item_idx]
    prompt = aut.prompt_for(item)
    common_seed = derive_unit_seed(persona_id, item.object_id, seed_idx)
    lam: float | None
    if condition == "A0":
        lam = _c.LAMBDA_A0
        resolved = resolve_lambda_sampling(base, lam)
        seed = common_seed
    elif condition == "A1":
        lam = lambda_for(_c.LAMBDA_BAND_A1, persona_id, item.object_id, seed_idx)
        resolved = resolve_lambda_sampling(base, lam)
        seed = common_seed
    elif condition == "A2":
        lam = lambda_for(_c.LAMBDA_BAND_A2, persona_id, item.object_id, seed_idx)
        resolved = resolve_lambda_sampling(base, lam)
        seed = common_seed
    elif condition == "M2":
        assert m2_temps is not None
        lam = None
        resolved = resolve_fixed_temperature(base, m2_temps[seed_idx])
        seed = derive_m2_seed(persona_id, item.object_id, seed_idx)
    else:  # "F"
        lam = None
        resolved = resolve_fixed_temperature(base, base.temperature + _c.F_TEMP_DELTA)
        seed = common_seed
    return GenerationRequest(
        persona_id=persona_id,
        task="aut",
        item_id=item.object_id,
        condition=condition,
        seed=seed,
        seed_idx=seed_idx,
        resolved=resolved,
        prompt=prompt,
        num_predict=_c.NUM_PREDICT_AUT,
        lam=lam,
    )


def build_aut_requests(
    phase: Phase, aut: AutBattery | None = None
) -> list[GenerationRequest]:
    """All AUT (divergent) generation requests for ``phase``.

    Persona × AUT item × condition × seed. A0/A1/A2 share common seeds per
    (persona, item); M2 is the distribution-matched fixed override on independent
    seeds; F is the forensic over-heat.
    """
    aut = aut if aut is not None else load_aut_battery()
    requests: list[GenerationRequest] = []
    for persona_id, base in _c.PERSONA_ROSTER:
        for item_idx in range(len(aut.items)):
            item = aut.items[item_idx]
            for condition in _aut_conditions(phase):
                n_seed = _seed_count(condition, phase)
                m2_temps = (
                    _m2_shuffled_temperatures(base, persona_id, item.object_id, n_seed)
                    if condition == "M2"
                    else None
                )
                requests.extend(
                    _build_aut_request(
                        base, persona_id, aut, item_idx, condition, seed_idx, m2_temps
                    )
                    for seed_idx in range(n_seed)
                )
    return requests


def _rat_prompt(cues: tuple[str, str, str]) -> str:
    a, b, c = cues
    return (
        "What single common English word is associated with all three of these "
        f"words: {a}, {b}, {c}? Answer with one word only."
    )


def build_rat_requests(
    phase: Phase, rat: RatBattery | None = None
) -> list[GenerationRequest]:
    """All RAT (convergent supporting) requests for ``phase`` ({A0, A2} only)."""
    rat = rat if rat is not None else load_rat_battery()
    requests: list[GenerationRequest] = []
    conditions: tuple[Condition, ...] = ("A0", "A2")
    n_seed = _c.N_SEED_PHASE0 if phase == "phase0" else _c.N_SEED_PHASE1
    for persona_id, base in _c.PERSONA_ROSTER:
        for item in rat.items:
            for condition in conditions:
                for seed_idx in range(n_seed):
                    if condition == "A0":
                        lam = _c.LAMBDA_A0
                        resolved = resolve_lambda_sampling(base, lam)
                    else:
                        lam = lambda_for(
                            _c.LAMBDA_BAND_A2, persona_id, item.item_id, seed_idx
                        )
                        resolved = resolve_lambda_sampling(base, lam)
                    requests.append(
                        GenerationRequest(
                            persona_id=persona_id,
                            task="rat",
                            item_id=item.item_id,
                            condition=condition,
                            seed=derive_unit_seed(persona_id, item.item_id, seed_idx),
                            seed_idx=seed_idx,
                            resolved=resolved,
                            prompt=_rat_prompt(item.cues),
                            num_predict=_c.NUM_PREDICT_RAT,
                            lam=lam,
                        )
                    )
    return requests


def generate(
    requests: Sequence[GenerationRequest], inference_fn: InferenceFn
) -> list[Generation]:
    """Run each request through the injectable seam → ``Generation`` records.

    The seam is the *only* place an LLM is touched; a mock makes the entire
    pipeline deterministic (Session 1). Session 2 passes the real backend.
    """
    return [Generation(request=r, response=inference_fn(r)) for r in requests]


__all__ = [
    "ES4_SALT",
    "Condition",
    "Generation",
    "GenerationRequest",
    "InferenceFn",
    "Phase",
    "band_lambda_pool",
    "build_aut_requests",
    "build_rat_requests",
    "derive_m2_seed",
    "derive_ref_seed",
    "derive_unit_seed",
    "generate",
    "lambda_for",
    "resolve_fixed_temperature",
    "resolve_lambda_sampling",
]
