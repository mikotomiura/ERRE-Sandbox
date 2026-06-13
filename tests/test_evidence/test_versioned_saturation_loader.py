"""``score_versioned_saturation`` decision-table coverage (versioned-measurement ADR).

Synthetic-fixture, CPU-only — the reachability proof this task exists to produce: every
branch of the versioned verdict (PASS / FAIL / INCONCLUSIVE / INVALID) is reachable
**and** the trivial-pass / self-defeat traps are shown un-reachable, before any III-a or
GPU run. Fixtures build :class:`SaturationTraceRow` / :class:`HintEngagementTraceRow`
directly; ``floor_fingerprint_hash`` is tied to the floor value (``fp{round(floor,6)}``)
so a constant floor is a stable fingerprint and a changing floor is a fingerprint reset
(a cross-fp trial) — mirroring how the real reconcile drops a stale modulation on an
evidence change.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from erre_sandbox.evidence.hint_engagement.trace_ddl import HintEngagementTraceRow
from erre_sandbox.evidence.saturation.loader import score_saturation
from erre_sandbox.evidence.saturation.trace_ddl import SaturationTraceRow
from erre_sandbox.evidence.saturation.versioned_constants import (
    H_SAFETY,
    MIN_D_FP,
)
from erre_sandbox.evidence.saturation.versioned_loader import (
    ArmRunBundle,
    score_versioned_saturation,
)

_FloatOrFn = float | Callable[[int], float]


def _val(spec: _FloatOrFn, tick: int) -> float:
    return spec(tick) if callable(spec) else spec


def _chan(
    *,
    seed: int,
    key: str,
    run_id: str,
    floor: _FloatOrFn,
    mod: _FloatOrFn,
    ticks: Iterable[int] = range(10, 30),
    individual: str = "kant",
    axis: str = "self",
    layer: bool = True,
) -> list[SaturationTraceRow]:
    """One channel's rows over *ticks*; fingerprint tracks the floor value."""
    rows: list[SaturationTraceRow] = []
    for t in ticks:
        fv = _val(floor, t)
        mv = _val(mod, t)
        rows.append(
            SaturationTraceRow(
                run_id=run_id,
                seed=seed,
                individual_id=individual,
                axis=axis,
                key=key,
                tick=t,
                base_floor_value=fv,
                modulated_value=mv,
                floor_fingerprint_hash=f"fp{round(fv, 6)}",
                individual_layer_enabled=layer,
            )
        )
    return rows


def _floor_stepping(t: int) -> float:
    """A positive floor that changes every tick (cross-fp every step, sign constant)."""
    return 0.50 + 0.001 * t


def _on_pass_seed(
    seed: int, run_id: str, *, n: int = 6, carry_until: int = 18
) -> list[SaturationTraceRow]:
    """ON arm: n channels carry +0.10 across cross-fp until ``carry_until``.

    The modulation then re-grounds (offset 0) so the retention episode *expires* within
    the run (V2 observes expiry, not a right-censored tail).
    """
    rows: list[SaturationTraceRow] = []
    for i in range(n):
        rows += _chan(
            seed=seed,
            key=f"k{i}",
            run_id=run_id,
            floor=_floor_stepping,
            mod=lambda t, _c=carry_until: (
                _floor_stepping(t) + (0.10 if t <= _c else 0.0)
            ),
        )
    return rows


def _off_trial_seed(seed: int, run_id: str, *, n: int = 6) -> list[SaturationTraceRow]:
    """OFF arm: n channels with cross-fp *trials* (mag 0.10 even ticks) that drop.

    Each even tick re-applies a modulation; the next (odd) tick the fingerprint
    changed and the modulation is at the floor (magnitude 0) — the frozen reconcile's
    else-branch drop. So ``D_fp > 0`` but ``R == 0`` (control completeness).
    """
    rows: list[SaturationTraceRow] = []
    for i in range(n):
        rows += _chan(
            seed=seed,
            key=f"k{i}",
            run_id=run_id,
            floor=_floor_stepping,
            mod=lambda t: _floor_stepping(t) + (0.10 if t % 2 == 0 else 0.0),
        )
    return rows


def _adopted_hint(
    *,
    seed: int,
    run_id: str,
    tick: int,
    direction: str,
    individual: str = "kant",
    axis: str = "self",
    key: str = "k0",
) -> HintEngagementTraceRow:
    return HintEngagementTraceRow(
        run_id=run_id,
        seed=seed,
        individual_id=individual,
        tick=tick,
        llm_status="ok",
        exposed_entry_count=3,
        emitted=True,
        disposition="adopted",
        target_axis=axis,
        target_key=key,
        direction=direction,
        adopted_signed_step=0.05,
        individual_layer_enabled=True,
    )


def _not_emitted_hint(
    *, seed: int, run_id: str, tick: int, individual: str = "kant"
) -> HintEngagementTraceRow:
    return HintEngagementTraceRow(
        run_id=run_id,
        seed=seed,
        individual_id=individual,
        tick=tick,
        llm_status="ok",
        exposed_entry_count=3,
        emitted=False,
        disposition="not_emitted",
        target_axis=None,
        target_key=None,
        direction=None,
        adopted_signed_step=0.0,
        individual_layer_enabled=True,
    )


def _on_pass_hints(
    seed: int, run_id: str, *, carry_until: int = 18
) -> list[HintEngagementTraceRow]:
    """Cover every retention-episode tick (10..carry) with an adopted strengthen hint.

    Targets ``k0`` so it is joinable for that channel (others are covered-not-joinable);
    ``strengthen`` matches the retained direction (|mod| > |floor|) so cancel_rate == 0.
    """
    return [
        _adopted_hint(seed=seed, run_id=run_id, tick=t, direction="strengthen")
        for t in range(10, carry_until + 1)
    ]


def _on_bundle(seed: int) -> ArmRunBundle:
    run_id = "on"
    return ArmRunBundle(
        arm="ON",
        run_id=run_id,
        source_run_id=f"src{seed}",
        rows=_on_pass_seed(seed, run_id),
        hint_rows=_on_pass_hints(seed, run_id),
    )


def _off_bundle(seed: int) -> ArmRunBundle:
    run_id = "off"
    return ArmRunBundle(
        arm="OFF",
        run_id=run_id,
        source_run_id=f"src{seed}",
        rows=_off_trial_seed(seed, run_id),
        hint_rows=None,
    )


def _full_pass_bundles() -> list[ArmRunBundle]:
    """3 seeds × matched ON/OFF (shared source_run_id), V3 complete, V2 expiry."""
    bundles: list[ArmRunBundle] = []
    for seed in (1, 2, 3):
        bundles.append(_on_bundle(seed))
        bundles.append(_off_bundle(seed))
    return bundles


# ---------------------------------------------------------------------------
# OFF baseline + ON full PASS (reachability of PASS)
# ---------------------------------------------------------------------------


def test_off_baseline_control_complete() -> None:
    """OFF arm: cross-fp trials present (D_fp>0) but retention structurally 0."""
    result = score_versioned_saturation([_off_bundle(1)])
    part = result.off_partitions[0]
    assert part.d_fp > 0
    assert part.r_retained == 0
    assert part.n_retained_channels == 0
    assert part.retained_rate == 0.0
    assert part.control_complete is True
    assert result.off_control_complete is True


def test_on_full_pass_non_saturated() -> None:
    """ON arm with matched OFF: every gate branch + R-3 PASS -> conclusive verdict."""
    result = score_versioned_saturation(_full_pass_bundles())
    assert result.on_verdict == "NON-SATURATED"
    assert result.off_control_complete is True
    assert len(result.on_partitions) == 3
    for p in result.on_partitions:
        assert p.gate_pass is True
        assert p.versioned_label == "NON-SATURATED"
        assert p.d_fp >= MIN_D_FP
        assert p.retained_rate is not None
        assert p.retained_rate >= 0.50
        assert p.n_retained_channels >= 3
        assert p.n_crossfp_channels >= 5
        assert p.v1_pass
        assert p.v4_pass
        assert p.v2_status == "PASS"
        assert p.v3_status == "PASS"
        assert p.non_inferiority == "PASS"


# ---------------------------------------------------------------------------
# Trivial-pass reproofs (each must FAIL the gate)
# ---------------------------------------------------------------------------


def test_trivial_pass_d_fp_too_small() -> None:
    """A single cross-fp trial (D_fp small) cannot pass MIN_D_FP even at rate 1.0."""

    # 6 channels, each with exactly ONE cross-fp retained transition (ticks 10->11),
    # then constant fingerprint so no more trials: D_fp == 6 < MIN_D_FP(30), rate 1.0.
    def _mod(t: int) -> float:
        return _floor(t) + 0.10

    def _floor(t: int) -> float:
        return 0.50 + (
            0.001 if t >= 11 else 0.0
        )  # one fp change at 10->11, then stable

    rows: list[SaturationTraceRow] = []
    for i in range(6):
        rows += _chan(seed=1, key=f"k{i}", run_id="on", floor=_floor, mod=_mod)
    bundle = ArmRunBundle(
        arm="ON", run_id="on", source_run_id="s", rows=rows, hint_rows=None
    )
    part = score_versioned_saturation([bundle]).on_partitions[0]
    assert part.d_fp < MIN_D_FP
    assert part.retained_rate == 1.0
    assert part.gate_pass is False


def test_trivial_pass_single_channel_dominates() -> None:
    """One channel's many transitions cannot satisfy CROSSFP_CHANNEL_MIN breadth."""
    rows = _chan(
        seed=1,
        key="solo",
        run_id="on",
        ticks=range(10, 50),  # one long channel supplies > MIN_D_FP trials by itself
        floor=_floor_stepping,
        mod=lambda t: _floor_stepping(t) + 0.10,
    )
    bundle = ArmRunBundle(
        arm="ON", run_id="on", source_run_id="s", rows=rows, hint_rows=None
    )
    part = score_versioned_saturation([bundle]).on_partitions[0]
    assert part.d_fp >= MIN_D_FP  # the single channel alone supplies many trials
    assert part.n_crossfp_channels == 1
    assert part.gate_pass is False


def test_trivial_pass_few_retained_channels() -> None:
    """Only 2 channels retain (< RETAINED_CHANNEL_MIN=3) -> breadth gate fails."""
    rows: list[SaturationTraceRow] = []
    # 2 channels retain; 4 channels have cross-fp trials that always drop.
    for i in range(2):
        rows += _chan(
            seed=1,
            key=f"keep{i}",
            run_id="on",
            floor=_floor_stepping,
            mod=lambda t: _floor_stepping(t) + 0.10,
        )
    for i in range(4):
        rows += _chan(
            seed=1,
            key=f"drop{i}",
            run_id="on",
            floor=_floor_stepping,
            mod=lambda t: _floor_stepping(t) + (0.10 if t % 2 == 0 else 0.0),
        )
    bundle = ArmRunBundle(
        arm="ON", run_id="on", source_run_id="s", rows=rows, hint_rows=None
    )
    part = score_versioned_saturation([bundle]).on_partitions[0]
    assert part.n_retained_channels == 2
    assert part.gate_pass is False


def test_trivial_pass_disappearance_inflates_rate() -> None:
    """ON dropping hard channels (high disappearance) fails non-inferiority vs OFF."""
    # ON: 3 channels retain fully, 6 disappear right after warmup while siblings persist
    # (each contributes a T-gone with few denominator units -> disappearance > margin).
    on_rows: list[SaturationTraceRow] = []
    for i in range(3):
        on_rows += _chan(
            seed=1,
            key=f"keep{i}",
            run_id="on",
            floor=_floor_stepping,
            mod=lambda t: _floor_stepping(t) + 0.10,
        )
    for i in range(6):
        on_rows += _chan(
            seed=1,
            key=f"gone{i}",
            run_id="on",
            ticks=range(10, 12),  # vanish at tick 12 while siblings persist -> T-gone
            floor=_floor_stepping,
            mod=lambda t: _floor_stepping(t) + 0.10,
        )
    off_rows = _off_trial_seed(1, "off")
    on_b = ArmRunBundle(
        arm="ON", run_id="on", source_run_id="s", rows=on_rows, hint_rows=None
    )
    off_b = ArmRunBundle(
        arm="OFF", run_id="off", source_run_id="s", rows=off_rows, hint_rows=None
    )
    result = score_versioned_saturation([on_b, off_b])
    on_part = result.on_partitions[0]
    assert on_part.channel_disappearance_rate is not None
    assert on_part.channel_disappearance_rate > 0.0
    assert on_part.non_inferiority == "FAIL"
    assert on_part.gate_pass is False


# ---------------------------------------------------------------------------
# R-3 validity guards
# ---------------------------------------------------------------------------


def test_v1_cap_violation_fails() -> None:
    """A retained tick whose |mod-floor| exceeds the 0.15 cap -> V1 FAIL."""
    rows: list[SaturationTraceRow] = []
    for i in range(6):
        rows += _chan(
            seed=1,
            key=f"k{i}",
            run_id="on",
            floor=_floor_stepping,
            mod=lambda t: _floor_stepping(t) + 0.20,  # magnitude 0.20 > cap 0.15
        )
    bundle = ArmRunBundle(
        arm="ON", run_id="on", source_run_id="s", rows=rows, hint_rows=None
    )
    part = score_versioned_saturation([bundle]).on_partitions[0]
    assert part.v1_pass is False
    assert part.gate_pass is False


def test_v2_stale_beyond_h_safety_fails() -> None:
    """A retention episode persisting > H_SAFETY ticks past t0 -> V2 FAIL."""
    end = 10 + H_SAFETY + 12  # carry well past t0 + H_SAFETY, then expire (observed)
    rows: list[SaturationTraceRow] = []
    for i in range(6):
        rows += _chan(
            seed=1,
            key=f"k{i}",
            run_id="on",
            ticks=range(10, end + 4),
            floor=_floor_stepping,
            mod=lambda t, _e=end: _floor_stepping(t) + (0.10 if t <= _e else 0.0),
        )
    bundle = ArmRunBundle(
        arm="ON", run_id="on", source_run_id="s", rows=rows, hint_rows=None
    )
    part = score_versioned_saturation([bundle]).on_partitions[0]
    assert part.v2_status == "FAIL"
    assert part.gate_pass is False


def test_v2_right_censored_inconclusive() -> None:
    """An episode active at the last grid tick (expiry unobserved) -> INCONCLUSIVE."""
    rows: list[SaturationTraceRow] = []
    for i in range(6):
        rows += _chan(
            seed=1,
            key=f"k{i}",
            run_id="on",
            floor=_floor_stepping,
            mod=lambda t: _floor_stepping(t) + 0.10,  # never expires; runs to last tick
        )
    bundle = ArmRunBundle(
        arm="ON", run_id="on", source_run_id="s", rows=rows, hint_rows=None
    )
    part = score_versioned_saturation([bundle]).on_partitions[0]
    assert part.v2_status == "INCONCLUSIVE"
    assert part.gate_pass is False


def test_v4_retained_across_floor_flip_fails() -> None:
    """A modulation retained across a floor sign reversal (T-flip) -> V4 FAIL."""
    rows: list[SaturationTraceRow] = []
    for i in range(6):
        rows += _chan(
            seed=1,
            key=f"k{i}",
            run_id="on",
            floor=lambda t: 0.10 if t % 2 == 0 else -0.10,  # sign flips each tick
            mod=lambda t: (0.10 if t % 2 == 0 else -0.10) + 0.05,  # offset +0.05 kept
        )
    bundle = ArmRunBundle(
        arm="ON", run_id="on", source_run_id="s", rows=rows, hint_rows=None
    )
    part = score_versioned_saturation([bundle]).on_partitions[0]
    assert part.v4_pass is False
    assert part.gate_pass is False


def test_v3_cancel_high_fails() -> None:
    """Adopted hints opposing the retained direction at >= CANCEL_HIGH -> V3 FAIL."""
    rows = _on_pass_seed(1, "on")
    # weaken hints on k0 at every retention tick -> cancel_rate 1.0
    hints = [
        _adopted_hint(seed=1, run_id="on", tick=t, direction="weaken")
        for t in range(10, 19)
    ]
    bundle = ArmRunBundle(
        arm="ON", run_id="on", source_run_id="s", rows=rows, hint_rows=hints
    )
    part = score_versioned_saturation([bundle]).on_partitions[0]
    assert part.v3_status == "FAIL"
    assert part.cancel_rate == 1.0
    assert part.gate_pass is False


def test_v3_no_adopted_hint_inconclusive() -> None:
    """Retention episode covered by hint rows but no adopted hint -> INCONCLUSIVE."""
    rows = _on_pass_seed(1, "on")
    hints = [_not_emitted_hint(seed=1, run_id="on", tick=t) for t in range(10, 19)]
    bundle = ArmRunBundle(
        arm="ON", run_id="on", source_run_id="s", rows=rows, hint_rows=hints
    )
    part = score_versioned_saturation([bundle]).on_partitions[0]
    assert part.v3_status == "INCONCLUSIVE"
    assert part.cancel_rate is None
    assert part.gate_pass is False


def test_v3_join_impossible_invalid() -> None:
    """Retention present but the hint trace is wholly absent (empty) -> INVALID."""
    rows = _on_pass_seed(1, "on")
    bundle = ArmRunBundle(
        arm="ON", run_id="on", source_run_id="s", rows=rows, hint_rows=[]
    )
    part = score_versioned_saturation([bundle]).on_partitions[0]
    assert part.v3_status == "INVALID"
    assert part.valid is False
    assert part.invalid_reason == "v3_join_invalid"
    assert part.gate_pass is False


def test_v3_missing_relevant_tick_invalid() -> None:
    """A retention-episode tick with no hint row at all -> INVALID (coverage gap)."""
    rows = _on_pass_seed(1, "on")
    # cover ticks 10..18 except 14 -> the missing relevant tick makes the join INVALID.
    hints = [
        _adopted_hint(seed=1, run_id="on", tick=t, direction="strengthen")
        for t in range(10, 19)
        if t != 14
    ]
    bundle = ArmRunBundle(
        arm="ON", run_id="on", source_run_id="s", rows=rows, hint_rows=hints
    )
    part = score_versioned_saturation([bundle]).on_partitions[0]
    assert part.v3_status == "INVALID"
    assert part.gate_pass is False


def test_v3_not_evaluated_blocks_pass() -> None:
    """hint_rows=None -> V3 NOT_EVALUATED, which is never a silent PASS."""
    bundles = [
        ArmRunBundle(
            arm="ON",
            run_id="on",
            source_run_id="src1",
            rows=_on_pass_seed(1, "on"),
            hint_rows=None,
        ),
        _off_bundle(1),
    ]
    part = score_versioned_saturation(bundles).on_partitions[0]
    assert part.v3_status == "NOT_EVALUATED"
    assert part.gate_pass is False


def test_v3_first_hint_cancellation_detected() -> None:
    """Single-tick semantic catches the FIRST cancel (establishing would miss it).

    Only tick 11 (= t0, the first cross-fp retention) carries an adopted hint, opposing
    the retained direction. An establishing-direction definition needs a prior adopted
    hint and would drop this tick; the single-tick definition flags it.
    """
    rows = _on_pass_seed(1, "on")
    hints = [_not_emitted_hint(seed=1, run_id="on", tick=t) for t in range(10, 19)]
    hints = [h for h in hints if h.tick != 11]
    hints.append(_adopted_hint(seed=1, run_id="on", tick=11, direction="weaken"))
    bundle = ArmRunBundle(
        arm="ON", run_id="on", source_run_id="s", rows=rows, hint_rows=hints
    )
    part = score_versioned_saturation([bundle]).on_partitions[0]
    assert part.v3_status == "FAIL"
    assert part.cancel_rate == 1.0


# ---------------------------------------------------------------------------
# Partition isolation + N=3 binding
# ---------------------------------------------------------------------------


def test_arm_partition_no_crosstalk() -> None:
    """Same source_run_id ON/OFF do not merge: ON retains, OFF does not."""
    result = score_versioned_saturation([_on_bundle(1), _off_bundle(1)])
    on = result.on_partitions[0]
    off = result.off_partitions[0]
    assert on.source_run_id == off.source_run_id == "src1"
    assert on.r_retained > 0
    assert off.r_retained == 0


def test_exactly_three_on_seeds_bind() -> None:
    result = score_versioned_saturation(_full_pass_bundles())
    assert result.on_verdict == "NON-SATURATED"
    assert len(result.on_partitions) == 3


def test_four_on_seeds_do_not_bind() -> None:
    bundles = _full_pass_bundles()
    bundles.append(_on_bundle(4))
    bundles.append(_off_bundle(4))
    result = score_versioned_saturation(bundles)
    assert result.on_verdict == "INCONCLUSIVE"
    assert "paired N=3 not met" in result.notes


# ---------------------------------------------------------------------------
# Compose conformance (Codex MED-2) + frozen INVALID propagation + warmup (MED-1)
# ---------------------------------------------------------------------------


def test_compose_inherits_frozen_seedscore_fields() -> None:
    """The versioned partition's frozen_seed equals the frozen scorer's own output."""
    rows = _on_pass_seed(1, "on")
    bundle = ArmRunBundle(
        arm="ON",
        run_id="on",
        source_run_id="s",
        rows=rows,
        hint_rows=_on_pass_hints(1, "on"),
    )
    part = score_versioned_saturation([bundle]).on_partitions[0]
    frozen = score_saturation(rows).seeds[0]
    assert part.frozen_seed.sat_frac == frozen.sat_frac
    assert part.frozen_seed.engagement_rate == frozen.engagement_rate
    assert part.frozen_seed.n_active == frozen.n_active
    assert part.frozen_seed.transient_active_rate == frozen.transient_active_rate


def test_frozen_invalid_t_run_propagates() -> None:
    """A seed whose max tick < T_RUN_MIN (25) inherits the frozen INVALID label."""
    rows = _chan(
        seed=1,
        key="k0",
        run_id="on",
        ticks=range(10, 21),  # t_run = 20 < 25
        floor=_floor_stepping,
        mod=lambda t: _floor_stepping(t) + 0.10,
    )
    bundle = ArmRunBundle(
        arm="ON", run_id="on", source_run_id="s", rows=rows, hint_rows=None
    )
    part = score_versioned_saturation([bundle]).on_partitions[0]
    assert part.valid is False
    assert part.invalid_reason == "t_run_below_min"
    assert part.versioned_label == "INVALID"
    assert part.gate_pass is False


def test_frozen_invalid_provenance_propagates() -> None:
    rows = _chan(
        seed=1,
        key="k0",
        run_id="on",
        floor=_floor_stepping,
        mod=lambda t: _floor_stepping(t) + 0.10,
        layer=False,  # provenance False
    )
    bundle = ArmRunBundle(
        arm="ON", run_id="on", source_run_id="s", rows=rows, hint_rows=None
    )
    part = score_versioned_saturation([bundle]).on_partitions[0]
    assert part.valid is False
    assert part.invalid_reason == "provenance_false"


def test_pre_warmup_only_excluded() -> None:
    """A channel active only in the warmup window (tick < 10) is excluded."""
    # warmup ticks carry a modulation; post-warmup the run is empty for this channel,
    # so the seed has no post-warmup substrate. The frozen scorer marks it INVALID
    # (t_run < T_RUN_MIN) — the versioned layer never sees a pre-warmup retained tick.
    rows = _chan(
        seed=1,
        key="k0",
        run_id="on",
        ticks=range(9),
        floor=_floor_stepping,
        mod=lambda t: _floor_stepping(t) + 0.10,
    )
    bundle = ArmRunBundle(
        arm="ON", run_id="on", source_run_id="s", rows=rows, hint_rows=None
    )
    part = score_versioned_saturation([bundle]).on_partitions[0]
    assert part.d_fp == 0  # no post-warmup transition counted
    assert part.gate_pass is False
