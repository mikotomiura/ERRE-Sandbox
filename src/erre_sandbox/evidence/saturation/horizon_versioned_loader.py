"""Horizon-reservation **compose** layer over the frozen versioned saturation scorer.

The frozen ``versioned_loader.score_versioned_saturation`` gates on a V2 guard
(``_v2_bounded_ttl``) that returns ``INCONCLUSIVE`` the moment **any** retention
channel is right-censored: its episode is still active at the individual's last
observed grid tick, so expiry was never observed. That is the conservative,
silent-PASS-avoiding behaviour the versioned ADR pre-registered (Codex U3 HIGH-3).
But a wall-governed GPU run (90-min ``wall_timeout``) *always* censors a few tail
channels, so the frozen verdict is pinned at INCONCLUSIVE even when the III-a
mechanism is plainly healthy on every other gate: a **measurement
observation-window** problem, not an intervention / data-volume / safety failure
(U6 seed 0: d_fp=495, retained_rate=0.945, V1/V3/V4/non-inf PASS, only V2 censored
4/36).

This module re-scores the **same** arm-tagged bundles, read-only, into a
*horizon-reserved* verdict. It **never touches** the frozen ``versioned_loader`` /
``versioned_constants`` / ``loader`` / ``constants`` files (``git diff`` over them
stays empty): it composes on the frozen public ``score_versioned_saturation`` for
**all** inherited metrics (d_fp, retained_rate, V1/V3/V4, non-inferiority,
``frozen_seed``, the OFF control gate) and only adds one new derivation: a
**Conditional V2 (CV2)** over the *evaluable subset* of retention episodes, plus a
gate / label / verdict that mirror the frozen ones with the CV2 substituted for V2.
The mirrors are pinned byte-for-byte against the frozen scorer by a truth-table
differential parity test (Codex U7 MED-2).

CV2 is an **explicitly conditional estimand**, not a relaxation of the frozen
universal V2 (Codex U7 HIGH-2). It does not silently launder partial exclusion:

* **admission rule** (result-independent, re-frozen in `.steering/.../decisions.md`
  DA-U7-3/DA-U7-7): a retention episode is ADMITTED iff the individual's row-derived
  observation grid extends **strictly past** ``t0 + H_SAFETY``
  (``last_grid_tick > t0 + H_SAFETY``; the strict ``>`` — Codex U7 HIGH-3 —
  guarantees a grid tick *after* the episode end, so a healthy episode's expiry is
  observable and a stale one is FAIL; an equality-active episode at
  ``last_grid_tick == t0 + H_SAFETY`` would still be censored, so it is EXCLUDED).
  Shorter follow-up is EXCLUDED (not evaluable). ``t0`` is the first *retained*
  cross-fp tick, so admission is conditional on a channel having retained, and is
  independent of the **post-t0** retention duration/outcome — but NOT of retention
  itself (Codex U7 HIGH-4); informative censoring (late ``t0`` is excluded more
  often) is a stated limitation.
* **CV2 status** (precedence): FAIL if any *admitted* episode is stale
  (``episode_end - t0 > H_SAFETY``): an observed safety violation always wins; else
  INCONCLUSIVE if the admitted set has fewer than ``RETAINED_CHANNEL_MIN`` distinct
  channels (this subsumes all-excluded and the "1 admitted PASS + N excluded
  unknown" trap — Codex U7 HIGH-2 — by reusing the existing breadth floor, **no new
  threshold**); else PASS. ``coverage = n_admitted / (n_admitted + n_excluded)`` is
  always reported so a thin evaluable subset is visible, never hidden.

**Well-definedness** (Codex U7 MED-1, proven from the rule alone, no kernel
dependence): an admitted non-stale episode has
``end <= t0 + H_SAFETY < last_grid_tick``, so a grid tick exists after ``end`` ->
expiry observed -> PASS; an admitted stale episode -> FAIL. So an admitted episode
is never CV2-censored. The ``STM_HORIZON <= H_SAFETY`` relation is a *separate*
cross-layer conformance check (test layer), not a correctness premise here.

The grid is the frozen scorer's **row-derived per-individual** tick set (ticks with
a saturation row; empty-floor ticks are absent), so the estimand is over the
observed (scored) window: its selectivity (a channel/individual going quiet shortens
the grid) is a stated limitation (Codex U7 HIGH-5); a true observation window from
the floor-input trace is a documented escalation, out of scope here.

Pure (no DuckDB) so the whole decision table is unit-testable on synthetic fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from erre_sandbox.evidence.saturation.constants import (
    ENGAGEMENT_MIN,
    MIN_ACTIVE_CHANNELS,
    N_SEEDS,
    THETA_HIGH,
    THETA_LOW,
    TRANSIENT_HIGH,
)
from erre_sandbox.evidence.saturation.versioned_constants import (
    CROSSFP_CHANNEL_MIN,
    H_SAFETY,
    MIN_D_FP,
    RETAINED_CHANNEL_MIN,
    RHO_RETAIN_MIN,
)

# Frozen pure helpers + public API, USE-only (Codex U7 HIGH-2 access strategy "A"):
# importing the frozen substrate/episode derivation guarantees CV2 reads the *same*
# substrate as the inherited metrics. These names are module-private but the import does
# not modify the frozen file (git diff stays empty); a smoke test pins the coupling so a
# future frozen rename fails loudly rather than silently.
from erre_sandbox.evidence.saturation.versioned_loader import (
    Arm,
    V2Status,
    Verdict,
    VersionedPartitionScore,
    VersionedSaturationLoaderError,
    VersionedSeedLabel,
    _build_substrate,
    _classify,
    _episode_containing,
    _episodes,
    score_versioned_saturation,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from erre_sandbox.evidence.saturation.trace_ddl import SaturationTraceRow
    from erre_sandbox.evidence.saturation.versioned_loader import ArmRunBundle

_Channel = tuple[str, str, str]
"""``(individual_id, axis, key)`` — the saturation channel identity in a partition."""


def _channel_id(ch: _Channel) -> str:
    """Stable ``individual|axis|key`` string for forensic channel lists."""
    return "|".join(ch)


# ---------------------------------------------------------------------------
# Public output dataclasses (mirror VersionedSaturationResult + CV2 forensic)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HorizonCV2Forensic:
    """Per-partition Conditional-V2 forensic (admission/exclusion + coverage)."""

    arm: Arm
    run_id: str
    source_run_id: str
    seed: int
    n_admitted_channels: int
    n_excluded_channels: int
    coverage: float | None  # n_admitted / (n_admitted + n_excluded); None if neither
    admitted_channels: tuple[str, ...]
    excluded_channels: tuple[str, ...]
    cv2_status: V2Status
    frozen_v2_status: V2Status


@dataclass(frozen=True, slots=True)
class HorizonVersionedPartitionScore:
    """Frozen versioned partition + the horizon-reserved CV2 override.

    ``base`` is the frozen :class:`VersionedPartitionScore` verbatim (its ``v2_status``
    is the **frozen** universal V2; its ``gate_pass`` / ``versioned_label`` are the
    frozen ones). ``cv2_status`` / ``gate_pass`` / ``versioned_label`` are the
    horizon-reserved overrides; ``cv2_forensic`` carries the admission/coverage detail.
    """

    base: VersionedPartitionScore
    cv2_status: V2Status
    cv2_forensic: HorizonCV2Forensic
    gate_pass: bool
    versioned_label: VersionedSeedLabel | None


@dataclass(frozen=True, slots=True)
class HorizonVersionedSaturationResult:
    """N=3 ON horizon verdict + OFF control + mechanised compound verdict."""

    on_verdict: Verdict
    off_control_complete: bool | None
    overall_verdict: Verdict  # OFF complete ∧ all ON gate_pass ∧ N=3 agree (DA-U6-4)
    on_partitions: list[HorizonVersionedPartitionScore] = field(default_factory=list)
    off_partitions: list[HorizonVersionedPartitionScore] = field(default_factory=list)
    notes: str = ""
    cv2_forensics: list[HorizonCV2Forensic] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Conditional V2 (the one new derivation) — strict reservation rule
# ---------------------------------------------------------------------------


def _conditional_v2(
    rows: Sequence[SaturationTraceRow],
) -> tuple[V2Status, list[_Channel], list[_Channel]]:
    """Re-derive CV2 over the evaluable subset (DA-U7-3/DA-U7-7).

    Admission: ``last_grid_tick > t0 + H_SAFETY`` (strict). Precedence: FAIL (any
    admitted stale) > INCONCLUSIVE (admitted breadth < ``RETAINED_CHANNEL_MIN``, incl.
    all-excluded) > PASS. Substrate/episodes/``t0`` come from the frozen pure helpers,
    so CV2 reads the byte-identical substrate the inherited metrics came from.
    """
    sub = _build_substrate(rows)
    r1 = _classify(sub)
    episodes_by_ch = {ch: _episodes(sub, ch) for ch in sub.mod}

    admitted: list[_Channel] = []
    excluded: list[_Channel] = []
    any_admitted_stale = False
    for ch, t0 in r1.first_ret_next.items():
        last_grid_tick = sub.grids[ch[0]][-1]
        if last_grid_tick > t0 + H_SAFETY:  # strict (Codex U7 HIGH-3)
            admitted.append(ch)
            episode = _episode_containing(episodes_by_ch[ch], t0)
            if episode is not None and episode[-1] - t0 > H_SAFETY:
                any_admitted_stale = True  # observed stale carry -> FAIL
        else:
            excluded.append(ch)  # insufficient follow-up -> not evaluable

    if any_admitted_stale:
        return "FAIL", admitted, excluded
    if len(admitted) < RETAINED_CHANNEL_MIN:
        # thin/empty evaluable subset is not conclusive (Codex U7 HIGH-2): subsumes
        # all-excluded and "1 admitted PASS + N excluded unknown".
        return "INCONCLUSIVE", admitted, excluded
    return "PASS", admitted, excluded


def _cv2_forensic(
    part: VersionedPartitionScore,
    cv2_status: V2Status,
    admitted: list[_Channel],
    excluded: list[_Channel],
) -> HorizonCV2Forensic:
    total = len(admitted) + len(excluded)
    return HorizonCV2Forensic(
        arm=part.arm,
        run_id=part.run_id,
        source_run_id=part.source_run_id,
        seed=part.seed,
        n_admitted_channels=len(admitted),
        n_excluded_channels=len(excluded),
        coverage=(len(admitted) / total) if total > 0 else None,
        admitted_channels=tuple(sorted(_channel_id(ch) for ch in admitted)),
        excluded_channels=tuple(sorted(_channel_id(ch) for ch in excluded)),
        cv2_status=cv2_status,
        frozen_v2_status=part.v2_status,
    )


# ---------------------------------------------------------------------------
# Gate / label / verdict mirrors (pinned to frozen by the parity test)
# ---------------------------------------------------------------------------


def _horizon_on_gate(part: VersionedPartitionScore, cv2_status: V2Status) -> bool:
    """Mirror frozen ``versioned_loader._on_gate`` with CV2 substituted for V2.

    Reads only the **public** fields of ``VersionedPartitionScore``. The truth-table
    differential parity test pins this against the frozen gate (feeding ``cv2_status =
    part.v2_status`` must reproduce ``part.gate_pass`` for every partition).
    """
    if not part.valid:
        return False
    f = part.frozen_seed
    return (
        f.engagement_rate >= ENGAGEMENT_MIN
        and f.n_active >= MIN_ACTIVE_CHANNELS
        and part.d_fp >= MIN_D_FP
        and part.n_crossfp_channels >= CROSSFP_CHANNEL_MIN
        and part.retained_rate is not None
        and part.retained_rate >= RHO_RETAIN_MIN
        and part.n_retained_channels >= RETAINED_CHANNEL_MIN
        and part.non_inferiority == "PASS"
        and f.transient_active_rate < TRANSIENT_HIGH
        and part.v1_pass
        and cv2_status == "PASS"
        and part.v4_pass
        and part.v3_status == "PASS"
    )


def _horizon_label(sat_frac: float | None, *, gate_pass: bool) -> VersionedSeedLabel:
    """Mirror frozen ``versioned_loader._versioned_label`` (sat_frac gap)."""
    if sat_frac is None or not gate_pass:
        return "INCONCLUSIVE"
    if sat_frac >= THETA_HIGH:
        return "SATURATED"
    if sat_frac <= THETA_LOW:
        return "NON-SATURATED"
    return "INCONCLUSIVE"


def _horizon_verdict(
    on_scores: list[HorizonVersionedPartitionScore],
) -> tuple[Verdict, str]:
    """Mirror frozen ``versioned_loader._on_verdict`` (exactly-N=3 distinct-seed)."""
    by_seed: dict[int, list[HorizonVersionedPartitionScore]] = {}
    for s in on_scores:
        by_seed.setdefault(s.base.seed, []).append(s)
    distinct = sorted(by_seed)
    if len(distinct) != N_SEEDS or any(len(by_seed[k]) != 1 for k in distinct):
        return "INCONCLUSIVE", (
            f"paired N={N_SEEDS} not met (ON distinct seeds={len(distinct)}, "
            "one partition per seed required)"
        )
    scores = [by_seed[k][0] for k in distinct]
    if not all(s.base.valid for s in scores):
        return "INCONCLUSIVE", "ON arm has an INVALID seed"
    labels = {s.versioned_label for s in scores}
    if labels == {"SATURATED"}:
        return "SATURATED", "ON seeds agree: SATURATED"
    if labels == {"NON-SATURATED"}:
        return "NON-SATURATED", "ON seeds agree: NON-SATURATED"
    return "INCONCLUSIVE", f"ON seed labels: {sorted(str(label) for label in labels)}"


def _overall_verdict(
    on_verdict: Verdict,
    on_scores: list[HorizonVersionedPartitionScore],
    *,
    off_control_complete: bool | None,
) -> Verdict:
    """Compound verdict (DA-U6-4, Codex U7 MED-3): mechanise the conjunction.

    ``OFF control_complete ∧ all ON gate_pass ∧ ON N=3 agree``. ``on_verdict`` already
    encodes the N=3 agreement (and a non-INCONCLUSIVE on_verdict implies all ON
    gate_pass), but the conjunction with OFF completeness and the explicit gate check is
    made loud here so the compound is a single binding field, not an inferred property.
    """
    if off_control_complete is not True:
        return "INCONCLUSIVE"
    if not on_scores or not all(s.gate_pass for s in on_scores):
        return "INCONCLUSIVE"
    return on_verdict


# ---------------------------------------------------------------------------
# Per-partition rows (replicate the frozen seed partitioning) + entry point
# ---------------------------------------------------------------------------


def _partition_rows(
    bundles: Sequence[ArmRunBundle],
) -> dict[tuple[Arm, str, str, int], list[SaturationTraceRow]]:
    """Group rows by ``(arm, run_id, source_run_id, seed)`` like the frozen scorer."""
    out: dict[tuple[Arm, str, str, int], list[SaturationTraceRow]] = {}
    for bundle in bundles:
        for r in bundle.rows:
            out.setdefault(
                (bundle.arm, bundle.run_id, bundle.source_run_id, r.seed), []
            ).append(r)
    return out


def _horizon_partition(
    part: VersionedPartitionScore,
    rows_by_key: Mapping[tuple[Arm, str, str, int], list[SaturationTraceRow]],
    *,
    is_on: bool,
) -> HorizonVersionedPartitionScore:
    """Overlay CV2 + horizon gate/label on one frozen partition."""
    if not part.valid:
        # An unmeasurable seed: inherit the frozen INVALID disposition; CV2 is moot.
        forensic = _cv2_forensic(part, part.v2_status, [], [])
        return HorizonVersionedPartitionScore(
            base=part,
            cv2_status=part.v2_status,
            cv2_forensic=forensic,
            gate_pass=False,
            versioned_label="INVALID" if is_on else None,
        )

    key = (part.arm, part.run_id, part.source_run_id, part.seed)
    rows = rows_by_key.get(key)
    if rows is None:  # pragma: no cover - defensive: frozen partition without rows
        raise VersionedSaturationLoaderError(
            f"horizon compose: no rows for partition {key} (frozen/compose drift)"
        )
    cv2_status, admitted, excluded = _conditional_v2(rows)
    forensic = _cv2_forensic(part, cv2_status, admitted, excluded)

    if not is_on:
        # OFF arm: control completeness is the frozen gate (V2 plays no role); pass it
        # through unchanged. CV2 forensic is recorded for audit only.
        return HorizonVersionedPartitionScore(
            base=part,
            cv2_status=cv2_status,
            cv2_forensic=forensic,
            gate_pass=False,
            versioned_label=None,
        )

    gate_pass = _horizon_on_gate(part, cv2_status)
    label = _horizon_label(part.frozen_seed.sat_frac, gate_pass=gate_pass)
    return HorizonVersionedPartitionScore(
        base=part,
        cv2_status=cv2_status,
        cv2_forensic=forensic,
        gate_pass=gate_pass,
        versioned_label=label,
    )


def score_horizon_versioned_saturation(
    bundles: Sequence[ArmRunBundle],
) -> HorizonVersionedSaturationResult:
    """Re-score arm-tagged bundles into the horizon-reserved (CV2) verdict (pure).

    Composes the frozen public ``score_versioned_saturation`` for all inherited metrics
    and the OFF control gate, then overlays the Conditional-V2 evaluable-subset layer on
    the ON arm (a different, explicitly-conditional estimand from the frozen universal
    V2, Codex U7 HIGH-2). The frozen files are never modified.
    """
    frozen = score_versioned_saturation(bundles)
    rows_by_key = _partition_rows(bundles)

    on_scores = [
        _horizon_partition(p, rows_by_key, is_on=True) for p in frozen.on_partitions
    ]
    off_scores = [
        _horizon_partition(p, rows_by_key, is_on=False) for p in frozen.off_partitions
    ]

    on_verdict, notes = _horizon_verdict(on_scores)
    overall = _overall_verdict(
        on_verdict, on_scores, off_control_complete=frozen.off_control_complete
    )
    forensics = [s.cv2_forensic for s in on_scores] + [
        s.cv2_forensic for s in off_scores
    ]
    return HorizonVersionedSaturationResult(
        on_verdict=on_verdict,
        off_control_complete=frozen.off_control_complete,
        overall_verdict=overall,
        on_partitions=on_scores,
        off_partitions=off_scores,
        notes=notes,
        cv2_forensics=forensics,
    )


__all__ = [
    "HorizonCV2Forensic",
    "HorizonVersionedPartitionScore",
    "HorizonVersionedSaturationResult",
    "score_horizon_versioned_saturation",
]
