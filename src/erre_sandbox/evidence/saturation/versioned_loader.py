"""Versioned **shadow** scorer for the SWM saturation trace (versioned-measurement ADR).

The frozen :func:`erre_sandbox.evidence.saturation.loader.score_saturation` gates on
``drop_rate``, which counts every fingerprint change as a drop regardless of whether
the modulation survived. A III-a layer that carries a modulation across a fingerprint
change (its whole purpose) therefore can never lift ``drop_rate``, so the frozen verdict
is pinned at INCONCLUSIVE even when the intervention works — a measurement self-defeat
(the inverse of S3.A④ / M11-C3b "the instrument cannot show its target").

This module re-scores the **same** trace, read-only, into a *versioned* verdict that
measures retention-across-fingerprint-change instead. It **never touches** the frozen
scorer / ``constants`` / ``trace_ddl``: it imports the frozen public
``score_saturation`` and reuses its public :class:`SeedScore` fields
(``sat_frac`` / ``engagement_rate`` / ``n_active`` / ``transient_active_rate`` /
``valid``) verbatim — the §3 "saturation evaluation is inherited unchanged" clause — and
only adds the versioned retention layer (R-1 metrics + R-3 V1-V4 guards + arm gate). So
``git diff -- <frozen files>`` stays empty and the frozen saturation statistics cannot
diverge (Codex MED-2: byte-identical is the file guarantee; this compose is the
behaviour guarantee for the inherited stats).

Design (frozen ADR conformance, `.steering/20260613-versioned-scorer-impl/design.md`):

* **arm partition** (ADR §5.1, Codex HIGH-2): input is arm-tagged :class:`ArmRunBundle`;
  the compute partition key is ``(arm, run_id, source_run_id, seed)`` so a replay that
  re-applies one captured ``source_run_id`` to both arms never merges. The
  disappearance non-inferiority pairing key is ``(source_run_id, seed)``.
* **R-1** (ADR §2): per channel, classify each grid-adjacent transition into clean
  cross-fp (T-fp) / floor-sign-flip (T-flip) / disappearance (T-gone) and measure
  ``retained_across_fp_change_rate`` + distinct-channel breadth + disappearance rate.
* **R-3** (ADR §4): V1 cap/range over all retention-episode ticks; V2 bounded-TTL
  three-state (right-censored = INCONCLUSIVE, never a silent PASS, Codex HIGH-3); V4
  evidence-grounding (a modulation retained across a floor-sign flip = FAIL); V3
  single-tick cancel rate against the hint trace (Codex HIGH-1).
* **gate** (ADR §3): the frozen §3.0 branches with ``drop_rate`` swapped for the
  versioned metrics; ON arm only, OFF arm checks control completeness (ADR §5.1).

Pure (no DuckDB dependency) so the whole decision table is unit-testable on synthetic
fixtures — the reachability proof this task exists to produce.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final, Literal

from erre_sandbox.evidence.saturation.constants import (
    ENGAGEMENT_MIN,
    EPSILON_MOD,
    MAX_TOTAL_MODULATION,
    MIN_ACTIVE_CHANNELS,
    N_SEEDS,
    T_WARMUP,
    THETA_HIGH,
    THETA_LOW,
    TRANSIENT_HIGH,
)
from erre_sandbox.evidence.saturation.loader import score_saturation
from erre_sandbox.evidence.saturation.versioned_constants import (
    CANCEL_HIGH,
    CROSSFP_CHANNEL_MIN,
    DISAPPEAR_MARGIN,
    H_SAFETY,
    MIN_D_FP,
    RETAINED_CHANNEL_MIN,
    RHO_RETAIN_MIN,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from erre_sandbox.evidence.hint_engagement.trace_ddl import HintEngagementTraceRow
    from erre_sandbox.evidence.saturation.loader import SeedScore
    from erre_sandbox.evidence.saturation.trace_ddl import SaturationTraceRow

Arm = Literal["ON", "OFF"]
VersionedSeedLabel = Literal["SATURATED", "NON-SATURATED", "INCONCLUSIVE", "INVALID"]
Verdict = Literal["SATURATED", "NON-SATURATED", "INCONCLUSIVE"]
V2Status = Literal["PASS", "FAIL", "INCONCLUSIVE"]
NonInferiority = Literal["PASS", "FAIL", "INCONCLUSIVE", "NO_PAIR"]
V3Status = Literal["PASS", "FAIL", "INCONCLUSIVE", "INVALID", "NOT_EVALUATED"]

_CAP_TOL: Final[float] = 1e-9
"""Float slack for the V1 cap/range check (fixtures use exact values; safety only)."""

_Channel = tuple[str, str, str]
"""``(individual_id, axis, key)`` — the saturation channel identity in a partition."""


class VersionedSaturationLoaderError(RuntimeError):
    """Raised on a structurally broken compose (non-homogeneous partition) — loud."""


# ---------------------------------------------------------------------------
# Public input / output dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ArmRunBundle:
    """One arm-tagged run's saturation rows (+ optional hint rows for V3).

    The caller (a separate CLI/orchestrator task) tags each run with its ``arm`` and a
    ``source_run_id`` pairing key: for a deterministic replay (ADR §5.2) the ON and OFF
    bundles share one ``source_run_id``; for a live paired run (ADR §5.3) it may equal
    ``run_id``. ``hint_rows`` is ``None`` when the V3 join is not wired for this run
    (V3 -> NOT_EVALUATED, never a silent PASS).
    """

    arm: Arm
    run_id: str
    source_run_id: str
    rows: Sequence[SaturationTraceRow]
    hint_rows: Sequence[HintEngagementTraceRow] | None = None


@dataclass(frozen=True, slots=True)
class VersionedPartitionScore:
    """Per-``(arm, run_id, source_run_id, seed)`` versioned diagnostics (ADR §2-§5)."""

    arm: Arm
    run_id: str
    source_run_id: str
    seed: int
    frozen_seed: SeedScore  # composition field (Codex MED-2): inherited §3.0 stats
    valid: bool
    invalid_reason: str | None
    d_fp: int
    r_retained: int
    retained_rate: float | None
    n_retained_channels: int
    n_crossfp_channels: int
    channel_disappearance_rate: float | None
    v1_pass: bool
    v2_status: V2Status
    v4_pass: bool
    v3_status: V3Status
    cancel_rate: float | None
    non_inferiority: NonInferiority | None  # ON arm only (None on OFF)
    gate_pass: bool  # ON arm scientific gate (always False on OFF)
    versioned_label: VersionedSeedLabel | None  # ON arm only
    control_complete: bool | None  # OFF arm only (None on ON)


@dataclass(frozen=True, slots=True)
class VersionedSaturationResult:
    """N=3 ON-arm versioned verdict + OFF-arm control state (ADR §3 / §5 / §6)."""

    on_verdict: Verdict
    off_control_complete: bool | None  # None when no OFF arm supplied
    on_partitions: list[VersionedPartitionScore] = field(default_factory=list)
    off_partitions: list[VersionedPartitionScore] = field(default_factory=list)
    notes: str = ""


# ---------------------------------------------------------------------------
# Pure substrate + transition classification
# ---------------------------------------------------------------------------


def _sign(x: float) -> int:
    """Sign of *x*: +1 / -1 / 0."""
    if x > 0.0:
        return 1
    if x < 0.0:
        return -1
    return 0


@dataclass(slots=True)
class _Substrate:
    """Per-channel post-warmup tick maps + per-individual tick grids, one partition."""

    mod: dict[_Channel, dict[int, float]]
    floor: dict[_Channel, dict[int, float]]
    fp: dict[_Channel, dict[int, str]]
    grids: dict[str, list[int]]
    gidx: dict[str, dict[int, int]]


def _build_substrate(rows: Sequence[SaturationTraceRow]) -> _Substrate:
    """Project the post-warmup (``tick >= T_WARMUP``) rows into the versioned substrate.

    Mirrors the frozen ``_build_substrate`` warmup exclusion (Codex MED-1) but is a
    versioned-only re-build keyed within a single ``(arm, run_id, source_run_id, seed)``
    partition (HIGH-4: the frozen seed-only substrate is never reused for partitioning).
    """
    mod: dict[_Channel, dict[int, float]] = {}
    floor: dict[_Channel, dict[int, float]] = {}
    fp: dict[_Channel, dict[int, str]] = {}
    ind_ticks: dict[str, set[int]] = {}
    for r in rows:
        if r.tick < T_WARMUP:
            continue
        ch: _Channel = (r.individual_id, r.axis, r.key)
        mod.setdefault(ch, {})[r.tick] = r.modulated_value
        floor.setdefault(ch, {})[r.tick] = r.base_floor_value
        fp.setdefault(ch, {})[r.tick] = r.floor_fingerprint_hash
        ind_ticks.setdefault(r.individual_id, set()).add(r.tick)
    grids = {ind: sorted(ticks) for ind, ticks in ind_ticks.items()}
    gidx = {ind: {t: i for i, t in enumerate(g)} for ind, g in grids.items()}
    return _Substrate(mod=mod, floor=floor, fp=fp, grids=grids, gidx=gidx)


@dataclass(slots=True)
class _R1:
    """R-1 transition tallies + the per-channel facts V2/V4 need (ADR §2.1-2.3)."""

    d_fp: int
    r_retained: int
    retained_rate: float | None
    n_retained_channels: int
    n_crossfp_channels: int
    disappearance_rate: float | None
    first_ret_next: dict[
        _Channel, int
    ]  # first cross-fp retention next-tick per channel
    tflip: list[tuple[_Channel, int, int]]  # (channel, prev, next) floor-sign flips


def _classify(sub: _Substrate) -> _R1:
    """Classify each grid-adjacent transition: T-fp / T-flip / T-gone (ADR §2.1)."""
    d_fp = 0
    r_retained = 0
    t_gone = 0
    denom = 0
    crossfp_channels: set[_Channel] = set()
    retained_channels: set[_Channel] = set()
    first_ret_next: dict[_Channel, int] = {}
    tflip: list[tuple[_Channel, int, int]] = []
    for ch, mod_by in sub.mod.items():
        grid = sub.grids[ch[0]]
        gi = sub.gidx[ch[0]]
        floor_by = sub.floor[ch]
        fp_by = sub.fp[ch]
        for prev in sorted(mod_by):
            if abs(mod_by[prev] - floor_by[prev]) < EPSILON_MOD:
                continue
            i = gi[prev]
            if i + 1 >= len(grid):
                continue  # no next step for this individual -> not a denominator unit
            next_t = grid[i + 1]
            denom += 1
            if next_t not in mod_by:
                t_gone += 1  # (T-gone) channel disappeared while individual stepped
                continue
            if fp_by[next_t] == fp_by[prev]:
                continue  # fingerprint stable -> not a cross-fp trial
            if _sign(floor_by[next_t]) != _sign(floor_by[prev]):
                tflip.append((ch, prev, next_t))  # (T-flip) floor sign reversed
                continue
            # (T-fp) clean cross-fp trial
            d_fp += 1
            crossfp_channels.add(ch)
            mag_next = abs(mod_by[next_t] - floor_by[next_t])
            off_prev = _sign(mod_by[prev] - floor_by[prev])
            off_next = _sign(mod_by[next_t] - floor_by[next_t])
            if mag_next >= EPSILON_MOD and off_next == off_prev:
                r_retained += 1
                retained_channels.add(ch)
                if ch not in first_ret_next or next_t < first_ret_next[ch]:
                    first_ret_next[ch] = next_t
    return _R1(
        d_fp=d_fp,
        r_retained=r_retained,
        retained_rate=r_retained / d_fp if d_fp > 0 else None,
        n_retained_channels=len(retained_channels),
        n_crossfp_channels=len(crossfp_channels),
        disappearance_rate=t_gone / denom if denom > 0 else None,
        first_ret_next=first_ret_next,
        tflip=tflip,
    )


def _episodes(sub: _Substrate, ch: _Channel) -> list[list[int]]:
    """Maximal grid-adjacent runs of same-sign-offset, mag>=EPSILON ticks (§4.1)."""
    mod_by = sub.mod[ch]
    floor_by = sub.floor[ch]
    gi = sub.gidx[ch[0]]
    episodes: list[list[int]] = []
    cur: list[int] = []
    for t in sorted(mod_by):
        if abs(mod_by[t] - floor_by[t]) < EPSILON_MOD:
            if cur:
                episodes.append(cur)
            cur = []
            continue
        off = _sign(mod_by[t] - floor_by[t])
        if cur:
            last = cur[-1]
            adjacent = gi[t] == gi[last] + 1
            same_sign = off == _sign(mod_by[last] - floor_by[last])
            if adjacent and same_sign:
                cur.append(t)
            else:
                episodes.append(cur)
                cur = [t]
        else:
            cur = [t]
    if cur:
        episodes.append(cur)
    return episodes


# ---------------------------------------------------------------------------
# R-3 validity guards (ADR §4)
# ---------------------------------------------------------------------------


def _v1_cap_range(
    sub: _Substrate, episodes_by_ch: dict[_Channel, list[list[int]]]
) -> bool:
    """V1 (ADR §4): cap/range over **all retention-episode ticks** (Codex HIGH-3)."""
    for ch, episodes in episodes_by_ch.items():
        floor_by = sub.floor[ch]
        mod_by = sub.mod[ch]
        for episode in episodes:
            for t in episode:
                f = floor_by[t]
                m = mod_by[t]
                if abs(m - f) > MAX_TOTAL_MODULATION + _CAP_TOL:
                    return False
                if m < -1.0 - _CAP_TOL or m > 1.0 + _CAP_TOL:
                    return False
    return True


def _v2_bounded_ttl(
    sub: _Substrate,
    episodes_by_ch: dict[_Channel, list[list[int]]],
    first_ret_next: dict[_Channel, int],
) -> V2Status:
    """V2 (ADR §4, Codex HIGH-3): bounded-TTL three-state from first cross-fp retention.

    For each channel, ``t0`` is the first cross-fp retention tick. The retention episode
    containing ``t0`` is measured: if it persists past ``t0 + H_SAFETY`` it is stale
    (FAIL); if it is still active at the individual's last grid tick within the window
    (no tick observed past it) it is right-censored (INCONCLUSIVE — expiry unobserved,
    never a silent PASS); otherwise the expiry was observed within the window (PASS).
    """
    any_right_censored = False
    for ch, t0 in first_ret_next.items():
        gi = sub.gidx[ch[0]]
        grid = sub.grids[ch[0]]
        episode = _episode_containing(episodes_by_ch[ch], t0)
        if episode is None:
            continue  # defensive: t0 is always in some episode by construction
        end = episode[-1]
        if end - t0 > H_SAFETY:
            return "FAIL"
        if gi[end] + 1 < len(grid):
            continue  # a later grid tick exists -> expiry was observed -> PASS
        any_right_censored = (
            True  # episode reaches the last grid tick: expiry unobserved
        )
    return "INCONCLUSIVE" if any_right_censored else "PASS"


def _episode_containing(episodes: list[list[int]], tick: int) -> list[int] | None:
    """The episode whose tick set contains *tick* (or None)."""
    for episode in episodes:
        if tick in episode:
            return episode
    return None


def _v4_evidence_grounding(
    sub: _Substrate, tflip: list[tuple[_Channel, int, int]]
) -> bool:
    """V4 (ADR §4): a modulation retained across a floor-sign flip (T-flip) is FAIL."""
    for ch, prev, next_t in tflip:
        mod_by = sub.mod[ch]
        floor_by = sub.floor[ch]
        mag_next = abs(mod_by[next_t] - floor_by[next_t])
        off_prev = _sign(mod_by[prev] - floor_by[prev])
        off_next = _sign(mod_by[next_t] - floor_by[next_t])
        if mag_next >= EPSILON_MOD and off_next == off_prev:
            return False
    return True


def _build_hint_index(
    hint_rows: Sequence[HintEngagementTraceRow],
) -> tuple[set[tuple[str, int]], dict[tuple[str, str, str, int], str]]:
    """Index hint rows: ``covered`` (ind, tick) set + adopted-direction lookup."""
    covered: set[tuple[str, int]] = set()
    adopted: dict[tuple[str, str, str, int], str] = {}
    for h in hint_rows:
        covered.add((h.individual_id, h.tick))
        if (
            h.disposition == "adopted"
            and h.target_axis is not None
            and h.target_key is not None
            and h.direction is not None
        ):
            adopted[(h.individual_id, h.target_axis, h.target_key, h.tick)] = (
                h.direction
            )
    return covered, adopted


def _count_v3_cancels(
    sub: _Substrate,
    episodes_by_ch: dict[_Channel, list[list[int]]],
    covered: set[tuple[str, int]],
    adopted: dict[tuple[str, str, str, int], str],
) -> tuple[int, int] | None:
    """Tally ``(joinable, cancel)`` over retention ticks, or None on a coverage gap."""
    joinable = 0
    cancel = 0
    for ch, episodes in episodes_by_ch.items():
        ind, axis, key = ch
        mod_by = sub.mod[ch]
        floor_by = sub.floor[ch]
        for episode in episodes:
            for t in episode:
                if (ind, t) not in covered:
                    return None  # relevant tick: hint row missing (INVALID, HIGH-1)
                hint_direction = adopted.get((ind, axis, key, t))
                if hint_direction is None:
                    continue  # covered, but no adopted hint targeting this channel
                joinable += 1
                retained_direction = (
                    "strengthen" if abs(mod_by[t]) > abs(floor_by[t]) else "weaken"
                )
                if hint_direction != retained_direction:
                    cancel += 1
    return joinable, cancel


def _v3_cancel(
    sub: _Substrate,
    episodes_by_ch: dict[_Channel, list[list[int]]],
    hint_rows: Sequence[HintEngagementTraceRow] | None,
) -> tuple[V3Status, float | None]:
    """V3 (ADR §4, Codex HIGH-1): single-tick cancel rate against the hint trace.

    ``retained_direction = "strengthen" if |modulated| > |floor| else "weaken"`` is the
    realised direction of the carried modulation (magnitude increase/decrease, the
    actual ``strengthen``/``weaken`` definition — never the offset sign across ticks).
    ``cancel`` is when the **current tick's** adopted hint ``direction`` opposes it. The
    denominator is **every adopted hint tick** in a retention episode for the channel.
    A retention-episode tick with no hint row at all (incomplete coverage) is INVALID,
    distinct from a tick that merely had no adopted hint.
    """
    if hint_rows is None:
        return "NOT_EVALUATED", None
    covered, adopted = _build_hint_index(hint_rows)
    tally = _count_v3_cancels(sub, episodes_by_ch, covered, adopted)
    if tally is None:
        return "INVALID", None
    joinable, cancel = tally
    if joinable == 0:
        return "INCONCLUSIVE", None
    rate = cancel / joinable
    return ("FAIL" if rate >= CANCEL_HIGH else "PASS"), rate


# ---------------------------------------------------------------------------
# Per-partition intrinsic scoring
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _Intrinsic:
    """Per-partition metrics before the arm-pairing (non-inferiority/verdict) layer."""

    arm: Arm
    run_id: str
    source_run_id: str
    seed: int
    frozen_seed: SeedScore
    valid: bool
    invalid_reason: str | None
    r1: _R1
    v1_pass: bool
    v2_status: V2Status
    v4_pass: bool
    v3_status: V3Status
    cancel_rate: float | None


def _score_partition(
    bundle: ArmRunBundle,
    seed: int,
    rows: Sequence[SaturationTraceRow],
    hint_rows: Sequence[HintEngagementTraceRow] | None,
) -> _Intrinsic:
    """Score one ``(arm, run_id, source_run_id, seed)`` partition (intrinsic)."""
    frozen = score_saturation(rows)
    if len(frozen.seeds) != 1:
        raise VersionedSaturationLoaderError(
            f"non-homogeneous partition: arm={bundle.arm} run_id={bundle.run_id} "
            f"seed={seed} produced {len(frozen.seeds)} frozen seeds (expected 1)"
        )
    frozen_seed = frozen.seeds[0]
    if frozen_seed.seed != seed:
        raise VersionedSaturationLoaderError(
            f"partition seed mismatch: keyed {seed}, frozen scored {frozen_seed.seed}"
        )

    sub = _build_substrate(rows)
    r1 = _classify(sub)

    if not frozen_seed.valid:
        # Inherit the frozen INVALID disposition (provenance / NaN / t_run) verbatim;
        # the versioned guards are moot on an unmeasurable seed.
        return _Intrinsic(
            arm=bundle.arm,
            run_id=bundle.run_id,
            source_run_id=bundle.source_run_id,
            seed=seed,
            frozen_seed=frozen_seed,
            valid=False,
            invalid_reason=frozen_seed.invalid_reason,
            r1=r1,
            v1_pass=False,
            v2_status="INCONCLUSIVE",
            v4_pass=False,
            v3_status="NOT_EVALUATED",
            cancel_rate=None,
        )

    episodes_by_ch = {ch: _episodes(sub, ch) for ch in sub.mod}
    v1_pass = _v1_cap_range(sub, episodes_by_ch)
    v2_status = _v2_bounded_ttl(sub, episodes_by_ch, r1.first_ret_next)
    v4_pass = _v4_evidence_grounding(sub, r1.tflip)
    v3_status, cancel_rate = _v3_cancel(sub, episodes_by_ch, hint_rows)

    v3_invalid = v3_status == "INVALID"
    return _Intrinsic(
        arm=bundle.arm,
        run_id=bundle.run_id,
        source_run_id=bundle.source_run_id,
        seed=seed,
        frozen_seed=frozen_seed,
        valid=not v3_invalid,
        invalid_reason="v3_join_invalid" if v3_invalid else None,
        r1=r1,
        v1_pass=v1_pass,
        v2_status=v2_status,
        v4_pass=v4_pass,
        v3_status=v3_status,
        cancel_rate=cancel_rate,
    )


# ---------------------------------------------------------------------------
# Arm-pairing + gate + verdict
# ---------------------------------------------------------------------------


def _versioned_label(sat_frac: float | None, *, gate_pass: bool) -> VersionedSeedLabel:
    """Mirror the frozen ``_label_seed`` (sat_frac gap = INCONCLUSIVE)."""
    if sat_frac is None or not gate_pass:
        return "INCONCLUSIVE"
    if sat_frac >= THETA_HIGH:
        return "SATURATED"
    if sat_frac <= THETA_LOW:
        return "NON-SATURATED"
    return "INCONCLUSIVE"


def _on_gate(intr: _Intrinsic, non_inferiority: NonInferiority) -> bool:
    """ON-arm scientific gate (ADR §3): frozen §3.0 branches, drop_rate -> versioned."""
    if not intr.valid:
        return False
    f = intr.frozen_seed
    r1 = intr.r1
    return (
        f.engagement_rate >= ENGAGEMENT_MIN
        and f.n_active >= MIN_ACTIVE_CHANNELS
        and r1.d_fp >= MIN_D_FP
        and r1.n_crossfp_channels >= CROSSFP_CHANNEL_MIN
        and r1.retained_rate is not None
        and r1.retained_rate >= RHO_RETAIN_MIN
        and r1.n_retained_channels >= RETAINED_CHANNEL_MIN
        and non_inferiority == "PASS"
        and f.transient_active_rate < TRANSIENT_HIGH
        and intr.v1_pass
        and intr.v2_status == "PASS"
        and intr.v4_pass
        and intr.v3_status == "PASS"
    )


def _non_inferiority(
    on: _Intrinsic, off_by_pair: Mapping[tuple[str, int], _Intrinsic]
) -> NonInferiority:
    """Disappearance non-inferiority vs the paired OFF arm (ADR §3)."""
    paired = off_by_pair.get((on.source_run_id, on.seed))
    if paired is None:
        return "NO_PAIR"
    on_disp = on.r1.disappearance_rate or 0.0
    off_disp = paired.r1.disappearance_rate or 0.0
    return "PASS" if on_disp <= off_disp + DISAPPEAR_MARGIN else "FAIL"


def _make_on_score(
    intr: _Intrinsic, non_inferiority: NonInferiority
) -> VersionedPartitionScore:
    gate_pass = _on_gate(intr, non_inferiority)
    label: VersionedSeedLabel = (
        _versioned_label(intr.frozen_seed.sat_frac, gate_pass=gate_pass)
        if intr.valid
        else "INVALID"
    )
    return _partition_score(
        intr,
        non_inferiority=non_inferiority,
        gate_pass=gate_pass,
        versioned_label=label,
        control_complete=None,
    )


def _make_off_score(intr: _Intrinsic) -> VersionedPartitionScore:
    # OFF control completeness (ADR §5.1): primary invariant R == 0 ∧ no retained
    # channel (Codex LOW-1); retained_rate == 0.0 is the derived consistency check.
    control_complete = (
        intr.valid
        and intr.r1.d_fp > 0
        and intr.r1.r_retained == 0
        and intr.r1.n_retained_channels == 0
        and (intr.r1.retained_rate == 0.0 or intr.r1.retained_rate is None)
    )
    return _partition_score(
        intr,
        non_inferiority=None,
        gate_pass=False,
        versioned_label=None,
        control_complete=control_complete,
    )


def _partition_score(
    intr: _Intrinsic,
    *,
    non_inferiority: NonInferiority | None,
    gate_pass: bool,
    versioned_label: VersionedSeedLabel | None,
    control_complete: bool | None,
) -> VersionedPartitionScore:
    r1 = intr.r1
    return VersionedPartitionScore(
        arm=intr.arm,
        run_id=intr.run_id,
        source_run_id=intr.source_run_id,
        seed=intr.seed,
        frozen_seed=intr.frozen_seed,
        valid=intr.valid,
        invalid_reason=intr.invalid_reason,
        d_fp=r1.d_fp,
        r_retained=r1.r_retained,
        retained_rate=r1.retained_rate,
        n_retained_channels=r1.n_retained_channels,
        n_crossfp_channels=r1.n_crossfp_channels,
        channel_disappearance_rate=r1.disappearance_rate,
        v1_pass=intr.v1_pass,
        v2_status=intr.v2_status,
        v4_pass=intr.v4_pass,
        v3_status=intr.v3_status,
        cancel_rate=intr.cancel_rate,
        non_inferiority=non_inferiority,
        gate_pass=gate_pass,
        versioned_label=versioned_label,
        control_complete=control_complete,
    )


def _on_verdict(on_scores: list[VersionedPartitionScore]) -> tuple[Verdict, str]:
    """Exactly-N=3 distinct-seed agreement over ON partitions (frozen 同型)."""
    by_seed: dict[int, list[VersionedPartitionScore]] = {}
    for s in on_scores:
        by_seed.setdefault(s.seed, []).append(s)
    distinct = sorted(by_seed)
    if len(distinct) != N_SEEDS or any(len(by_seed[k]) != 1 for k in distinct):
        return "INCONCLUSIVE", (
            f"paired N={N_SEEDS} not met (ON distinct seeds={len(distinct)}, "
            "one partition per seed required)"
        )
    scores = [by_seed[k][0] for k in distinct]
    if not all(s.valid for s in scores):
        return "INCONCLUSIVE", "ON arm has an INVALID seed"
    labels = {s.versioned_label for s in scores}
    if labels == {"SATURATED"}:
        return "SATURATED", "ON seeds agree: SATURATED"
    if labels == {"NON-SATURATED"}:
        return "NON-SATURATED", "ON seeds agree: NON-SATURATED"
    return "INCONCLUSIVE", f"ON seed labels: {sorted(str(label) for label in labels)}"


def score_versioned_saturation(
    bundles: Sequence[ArmRunBundle],
) -> VersionedSaturationResult:
    """Re-score arm-tagged bundles into the versioned verdict (pure, ADR §2-§6).

    Each bundle is partitioned by ``seed`` (within its ``(arm, run_id, source_run_id)``
    identity); each partition is scored by composing the frozen public
    ``score_saturation`` for the inherited §3.0 statistics and overlaying the versioned
    retention layer. The ON arm applies the scientific gate (ADR §3) and binds a verdict
    only on exactly ``N_SEEDS`` agreeing distinct seeds (frozen exactly-3); the OFF arm
    checks control completeness (ADR §5.1); disappearance non-inferiority pairs ON/OFF
    on ``(source_run_id, seed)``.
    """
    intrinsics: list[_Intrinsic] = []
    for bundle in bundles:
        by_seed: dict[int, list[SaturationTraceRow]] = {}
        for r in bundle.rows:
            by_seed.setdefault(r.seed, []).append(r)
        hint_by_seed: dict[int, list[HintEngagementTraceRow]] = {}
        if bundle.hint_rows is not None:
            for h in bundle.hint_rows:
                hint_by_seed.setdefault(h.seed, []).append(h)
        for seed in sorted(by_seed):
            hint_rows = None if bundle.hint_rows is None else hint_by_seed.get(seed, [])
            intrinsics.append(_score_partition(bundle, seed, by_seed[seed], hint_rows))

    on = [x for x in intrinsics if x.arm == "ON"]
    off = [x for x in intrinsics if x.arm == "OFF"]
    off_by_pair: dict[tuple[str, int], _Intrinsic] = {
        (x.source_run_id, x.seed): x for x in off
    }

    on_scores = [_make_on_score(x, _non_inferiority(x, off_by_pair)) for x in on]
    off_scores = [_make_off_score(x) for x in off]

    verdict, notes = _on_verdict(on_scores)
    off_control_complete = (
        all(s.control_complete for s in off_scores) if off_scores else None
    )
    return VersionedSaturationResult(
        on_verdict=verdict,
        off_control_complete=off_control_complete,
        on_partitions=on_scores,
        off_partitions=off_scores,
        notes=notes,
    )


__all__ = [
    "ArmRunBundle",
    "VersionedPartitionScore",
    "VersionedSaturationLoaderError",
    "VersionedSaturationResult",
    "score_versioned_saturation",
]
