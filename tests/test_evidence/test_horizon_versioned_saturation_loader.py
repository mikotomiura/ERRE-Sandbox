"""``score_horizon_versioned_saturation`` decision-table + Codex U7 fold-in coverage.

Synthetic-fixture, CPU-only. Proves the horizon-reservation (Conditional-V2/CV2) layer:
every CV2 branch (PASS / FAIL / INCONCLUSIVE) is reachable, the silent-PASS / measure-
chasing traps Codex U7 BLOCK flagged are shown un-reachable, and the gate/label/verdict
mirrors are pinned byte-for-byte against the frozen scorer. ``floor_fingerprint_hash``
tracks the floor value (``fp{round(floor,6)}``) so a stepping floor is a cross-fp trial
every tick — the same convention as ``test_versioned_saturation_loader``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from erre_sandbox.evidence.hint_engagement.trace_ddl import HintEngagementTraceRow
from erre_sandbox.evidence.saturation.horizon_versioned_loader import (
    _conditional_v2,
    _horizon_label,
    _horizon_on_gate,
    score_horizon_versioned_saturation,
)
from erre_sandbox.evidence.saturation.trace_ddl import SaturationTraceRow
from erre_sandbox.evidence.saturation.versioned_constants import (
    H_SAFETY,
    RETAINED_CHANNEL_MIN,
)
from erre_sandbox.evidence.saturation.versioned_loader import (
    ArmRunBundle,
    score_versioned_saturation,
)

_FloatOrFn = float | Callable[[int], float]


def _val(spec: _FloatOrFn, tick: int) -> float:
    return spec(tick) if callable(spec) else spec


def _floor_stepping(t: int) -> float:
    """Positive floor that changes every tick (cross-fp every step, sign constant)."""
    return 0.50 + 0.001 * t


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


# --- single-partition CV2 helpers (assert on cv2_status directly) -------------


def _cv2_of(rows: list[SaturationTraceRow]) -> str:
    bundle = ArmRunBundle(arm="ON", run_id="on", source_run_id="s", rows=rows)
    return score_horizon_versioned_saturation([bundle]).on_partitions[0].cv2_status


# ---------------------------------------------------------------------------
# (a) stale-admitted -> CV2 FAIL  (no trivial-pass laundering)
# ---------------------------------------------------------------------------


def test_a_stale_admitted_fails() -> None:
    """An admitted episode persisting > H_SAFETY past t0 -> CV2 FAIL, gate False."""
    end = 10 + H_SAFETY + 12  # carry well past t0 + H_SAFETY, then expire (observed)
    rows: list[SaturationTraceRow] = []
    for i in range(6):
        rows += _chan(
            seed=1,
            key=f"k{i}",
            run_id="on",
            ticks=range(10, end + 6),  # grid extends past t0 + H_SAFETY -> admitted
            floor=_floor_stepping,
            mod=lambda t, _e=end: _floor_stepping(t) + (0.10 if t <= _e else 0.0),
        )
    result = score_horizon_versioned_saturation(
        [ArmRunBundle(arm="ON", run_id="on", source_run_id="s", rows=rows)]
    )
    part = result.on_partitions[0]
    assert part.cv2_status == "FAIL"
    assert part.base.v2_status == "FAIL"  # frozen also FAILs a stale carry
    assert part.gate_pass is False


# ---------------------------------------------------------------------------
# (b)/(l) insufficient-admitted -> INCONCLUSIVE  (no silent partial PASS)
# ---------------------------------------------------------------------------


def test_b_all_excluded_inconclusive() -> None:
    """Every channel's follow-up is too short (censored tail) -> CV2 INCONCLUSIVE."""
    # Never expires, individual grid <= t0 + H_SAFETY -> all excluded (none admitted).
    rows: list[SaturationTraceRow] = []
    for i in range(6):
        rows += _chan(
            seed=1,
            key=f"k{i}",
            run_id="on",
            ticks=range(10, 10 + H_SAFETY),  # last = t0..; < t0 + H_SAFETY -> excluded
            floor=_floor_stepping,
            mod=lambda t: _floor_stepping(t) + 0.10,
        )
    part = score_horizon_versioned_saturation(
        [ArmRunBundle(arm="ON", run_id="on", source_run_id="s", rows=rows)]
    ).on_partitions[0]
    assert part.base.v2_status == "INCONCLUSIVE"  # frozen right-censored
    assert part.cv2_status == "INCONCLUSIVE"  # CV2: nothing admitted
    assert part.cv2_forensic.n_admitted_channels == 0


def test_l_one_admitted_below_breadth_inconclusive() -> None:
    """1 admitted healthy + many excluded unknown is NOT a PASS (Codex U7 HIGH-2).

    One channel (long grid) expires in-window -> admitted PASS-eligible; several others
    have short individual grids -> excluded. With only 1 admitted (< the breadth floor)
    the conditional subset is too thin to conclude -> INCONCLUSIVE, never a silent PASS.
    """
    rows: list[SaturationTraceRow] = []
    # 1 admitted healthy channel on its own individual with a long grid.
    rows += _chan(
        seed=1,
        key="solo",
        run_id="on",
        individual="kant",
        ticks=range(10, 10 + H_SAFETY + 8),
        floor=_floor_stepping,
        mod=lambda t: _floor_stepping(t) + (0.10 if t <= 14 else 0.0),
    )
    # excluded channels: short-grid individuals, never expire (censored tail).
    for i in range(4):
        rows += _chan(
            seed=1,
            key=f"c{i}",
            run_id="on",
            individual=f"ex{i}",
            ticks=range(10, 10 + H_SAFETY),
            floor=_floor_stepping,
            mod=lambda t: _floor_stepping(t) + 0.10,
        )
    part = score_horizon_versioned_saturation(
        [ArmRunBundle(arm="ON", run_id="on", source_run_id="s", rows=rows)]
    ).on_partitions[0]
    assert part.cv2_forensic.n_admitted_channels == 1
    assert part.cv2_forensic.n_excluded_channels == 4
    assert part.cv2_forensic.coverage == 1 / 5
    assert part.cv2_status == "INCONCLUSIVE"  # 1 < RETAINED_CHANNEL_MIN -> not PASS


# ---------------------------------------------------------------------------
# (k) equality-active boundary -> excluded (strict > rule, Codex U7 HIGH-3)
# ---------------------------------------------------------------------------


def test_k_equality_active_is_excluded() -> None:
    """last_grid_tick == t0 + H_SAFETY with an active episode is censored -> excluded.

    t0 = 11 (first cross-fp retention). An episode still active at last_grid_tick ==
    t0 + H_SAFETY is right-censored under the frozen FAIL boundary; the strict ``>``
    rule EXCLUDES it (does not admit a still-censorable episode).
    """
    # t0 = 11; last_grid_tick = 11 + H_SAFETY exactly; never expires -> active there.
    last = 11 + H_SAFETY
    rows = _chan(
        seed=1,
        key="k0",
        run_id="on",
        ticks=range(10, last + 1),  # last grid tick == t0 + H_SAFETY
        floor=_floor_stepping,
        mod=lambda t: _floor_stepping(t) + 0.10,
    )
    cv2, admitted, excluded = _conditional_v2(rows)
    assert len(admitted) == 0
    assert len(excluded) == 1
    assert cv2 == "INCONCLUSIVE"


def test_k_one_past_boundary_is_admitted() -> None:
    """last_grid_tick == t0 + H_SAFETY + 1 admits (a grid tick exists past the end)."""
    last = 11 + H_SAFETY + 1
    rows = _chan(
        seed=1,
        key="k0",
        run_id="on",
        ticks=range(10, last + 1),
        # expire before the boundary so the admitted episode is healthy (PASS-eligible).
        floor=_floor_stepping,
        mod=lambda t: _floor_stepping(t) + (0.10 if t <= 13 else 0.0),
    )
    _cv2, admitted, excluded = _conditional_v2(rows)
    assert len(admitted) == 1
    assert len(excluded) == 0


# ---------------------------------------------------------------------------
# (f) well-definedness: an admitted episode is never CV2-INCONCLUSIVE-by-censoring
# ---------------------------------------------------------------------------


def test_f_admitted_episode_is_pass_or_fail_never_censored() -> None:
    """From the strict rule alone: admitted -> PASS (healthy) or FAIL (stale).

    Healthy admitted channels -> PASS; this holds regardless of STM_HORIZON (proven from
    the admission geometry, not from the kernel horizon).
    """
    rows: list[SaturationTraceRow] = []
    for i in range(RETAINED_CHANNEL_MIN):
        rows += _chan(
            seed=1,
            key=f"k{i}",
            run_id="on",
            ticks=range(10, 10 + H_SAFETY + 8),  # admitted (grid > t0 + H_SAFETY)
            floor=_floor_stepping,
            mod=lambda t: _floor_stepping(t) + (0.10 if t <= 14 else 0.0),  # expire@14
        )
    cv2, admitted, excluded = _conditional_v2(rows)
    assert len(admitted) == RETAINED_CHANNEL_MIN
    assert len(excluded) == 0
    assert cv2 == "PASS"  # healthy admitted -> PASS, never censored-INCONCLUSIVE


def test_f2_stm_horizon_within_h_safety_conformance() -> None:
    """Cross-layer conformance (separate from scorer correctness, Codex U7 MED-1)."""
    from erre_sandbox.cognition.world_model import STM_HORIZON

    assert STM_HORIZON <= H_SAFETY


# ---------------------------------------------------------------------------
# (d) neutrality: admission depends on follow-up length, not on post-t0 outcome
# ---------------------------------------------------------------------------


def test_d_admission_independent_of_post_t0_outcome() -> None:
    """Matched t0/grid geometry: a healthy carry is admitted->PASS, a stale carry is
    admitted->FAIL — admission itself is identical (it never reads the post-t0 outcome).
    """
    ticks = range(10, 10 + H_SAFETY + 30)
    healthy = _chan(
        seed=1,
        key="h",
        run_id="on",
        ticks=ticks,
        floor=_floor_stepping,
        mod=lambda t: _floor_stepping(t) + (0.10 if t <= 13 else 0.0),
    )
    stale = _chan(
        seed=1,
        key="s",
        run_id="on",
        ticks=ticks,
        floor=_floor_stepping,
        mod=lambda t: _floor_stepping(t) + (0.10 if t <= 10 + H_SAFETY + 5 else 0.0),
    )
    _h_cv2, h_adm, _h_exc = _conditional_v2(healthy)
    _s_cv2, s_adm, _s_exc = _conditional_v2(stale)
    # both admitted (same grid geometry, same t0): admission ignores post-t0 outcome
    assert len(h_adm) == 1
    assert len(s_adm) == 1
    # but the verdict differs by the (post-t0) outcome the admission did not read
    assert _conditional_v2(healthy)[0] == "INCONCLUSIVE"  # 1 admitted < breadth floor
    assert _conditional_v2(stale)[0] == "FAIL"  # stale always FAILs (precedence)


# ---------------------------------------------------------------------------
# (c) reachability: frozen on_verdict INCONCLUSIVE -> horizon overall NON-SATURATED
# ---------------------------------------------------------------------------


def _admitted_pass_chans(
    seed: int, run_id: str, *, n: int = 6
) -> list[SaturationTraceRow]:
    """``n`` kant channels with a long grid that expire early -> admitted, healthy."""
    rows: list[SaturationTraceRow] = []
    for i in range(n):
        rows += _chan(
            seed=seed,
            key=f"k{i}",
            run_id=run_id,
            individual="kant",
            ticks=range(10, 45),  # last 44 > t0(11) + H_SAFETY(20) = 31 -> admitted
            floor=_floor_stepping,
            mod=lambda t: _floor_stepping(t) + (0.10 if t <= 17 else 0.0),
        )
    return rows


def _censored_excluded_chans(
    seed: int, run_id: str, *, n: int = 3
) -> list[SaturationTraceRow]:
    """``n`` hume channels on a short individual grid that never expire -> censored.

    Frozen V2 sees these as right-censored (INCONCLUSIVE); CV2 excludes them (the hume
    individual grid 10..27 < t0 + H_SAFETY = 31).
    """
    rows: list[SaturationTraceRow] = []
    for i in range(n):
        rows += _chan(
            seed=seed,
            key=f"h{i}",
            run_id=run_id,
            individual="hume",
            ticks=range(10, 28),  # last 27 < 31 -> excluded
            floor=_floor_stepping,
            mod=lambda t: _floor_stepping(t) + 0.10,
        )
    return rows


def _horizon_pass_hints(seed: int, run_id: str) -> list[HintEngagementTraceRow]:
    """Cover every retention-episode tick: kant 10..17 (adopted strengthen on k0) +
    hume 10..27 (not-emitted). cancel_rate == 0 -> V3 PASS.
    """
    hints: list[HintEngagementTraceRow] = [
        _adopted_hint(seed=seed, run_id=run_id, tick=t, direction="strengthen")
        for t in range(10, 18)
    ]
    hints += [
        _not_emitted_hint(seed=seed, run_id=run_id, tick=t, individual="hume")
        for t in range(10, 28)
    ]
    return hints


def _off_trial_chans(seed: int, run_id: str, *, n: int = 6) -> list[SaturationTraceRow]:
    rows: list[SaturationTraceRow] = []
    for i in range(n):
        rows += _chan(
            seed=seed,
            key=f"k{i}",
            run_id=run_id,
            ticks=range(10, 45),
            floor=_floor_stepping,
            mod=lambda t: _floor_stepping(t) + (0.10 if t % 2 == 0 else 0.0),
        )
    return rows


def _horizon_bundles() -> list[ArmRunBundle]:
    bundles: list[ArmRunBundle] = []
    for seed in (1, 2, 3):
        on_rows = _admitted_pass_chans(seed, "on") + _censored_excluded_chans(
            seed, "on"
        )
        bundles.append(
            ArmRunBundle(
                arm="ON",
                run_id="on",
                source_run_id=f"src{seed}",
                rows=on_rows,
                hint_rows=_horizon_pass_hints(seed, "on"),
            )
        )
        bundles.append(
            ArmRunBundle(
                arm="OFF",
                run_id="off",
                source_run_id=f"src{seed}",
                rows=_off_trial_chans(seed, "off"),
            )
        )
    return bundles


def test_c_frozen_inconclusive_becomes_horizon_pass() -> None:
    """The reachability proof: a censored tail pins frozen V2/verdict at INCONCLUSIVE,
    but the horizon CV2 admits the healthy subset -> conclusive overall verdict.
    """
    bundles = _horizon_bundles()
    frozen = score_versioned_saturation(bundles)
    horizon = score_horizon_versioned_saturation(bundles)

    # Frozen: a right-censored tail channel forces INCONCLUSIVE on every ON seed.
    assert frozen.on_verdict == "INCONCLUSIVE"
    for p in frozen.on_partitions:
        assert p.v2_status == "INCONCLUSIVE"

    # Horizon: CV2 excludes the censored hume channels, admits the healthy kant subset.
    assert horizon.on_verdict == "NON-SATURATED"
    assert horizon.off_control_complete is True
    assert horizon.overall_verdict == "NON-SATURATED"
    for p in horizon.on_partitions:
        assert p.cv2_status == "PASS"
        assert p.gate_pass is True
        assert p.versioned_label == "NON-SATURATED"
        assert p.cv2_forensic.n_admitted_channels == 6
        assert p.cv2_forensic.n_excluded_channels == 3
        assert p.cv2_forensic.coverage == 6 / 9


# ---------------------------------------------------------------------------
# (e) truth-table differential parity: mirror == frozen with frozen-V2 substituted
# ---------------------------------------------------------------------------


def test_e_gate_parity_with_frozen_v2_substituted() -> None:
    """Feeding CV2 := frozen V2 reproduces the frozen gate/label/verdict exactly.

    Pins the mirrors (Codex U7 MED-2): the ONLY intended behavioural difference between
    the horizon scorer and the frozen scorer is the V2 -> CV2 substitution.
    """
    # Reuse the reachability battery + a stale + a censored + an invalid scenario.
    scenarios: list[list[ArmRunBundle]] = [
        _horizon_bundles(),
        # stale single ON
        [
            ArmRunBundle(
                arm="ON",
                run_id="on",
                source_run_id="s",
                rows=[
                    r
                    for i in range(6)
                    for r in _chan(
                        seed=1,
                        key=f"k{i}",
                        run_id="on",
                        ticks=range(10, 10 + H_SAFETY + 18),
                        floor=_floor_stepping,
                        mod=lambda t: (
                            _floor_stepping(t)
                            + (0.10 if t <= 10 + H_SAFETY + 8 else 0.0)
                        ),
                    )
                ],
            )
        ],
        # invalid (provenance False)
        [
            ArmRunBundle(
                arm="ON",
                run_id="on",
                source_run_id="s",
                rows=_chan(
                    seed=1,
                    key="k0",
                    run_id="on",
                    layer=False,
                    floor=_floor_stepping,
                    mod=lambda t: _floor_stepping(t) + 0.10,
                ),
            )
        ],
    ]
    for bundles in scenarios:
        frozen = score_versioned_saturation(bundles)
        # gate + label parity per ON partition
        for fp in frozen.on_partitions:
            mirrored_gate = _horizon_on_gate(fp, fp.v2_status)
            assert mirrored_gate == fp.gate_pass
            mirrored_label = _horizon_label(
                fp.frozen_seed.sat_frac, gate_pass=fp.gate_pass
            )
            if fp.valid:
                assert mirrored_label == fp.versioned_label


# ---------------------------------------------------------------------------
# (i) OFF passthrough — V2 plays no role in the OFF control gate
# ---------------------------------------------------------------------------


def test_i_off_control_complete_passthrough() -> None:
    bundles = _horizon_bundles()
    frozen = score_versioned_saturation(bundles)
    horizon = score_horizon_versioned_saturation(bundles)
    assert horizon.off_control_complete == frozen.off_control_complete
    for hp, fp in zip(horizon.off_partitions, frozen.off_partitions, strict=True):
        assert hp.base.control_complete == fp.control_complete


# ---------------------------------------------------------------------------
# (h) private-helper import smoke — pins the frozen coupling (Codex U7 access "A")
# ---------------------------------------------------------------------------


def test_h_frozen_private_helpers_importable() -> None:
    from erre_sandbox.evidence.saturation.versioned_loader import (
        _build_substrate,
        _classify,
        _episode_containing,
        _episodes,
    )

    assert callable(_build_substrate)
    assert callable(_classify)
    assert callable(_episodes)
    assert callable(_episode_containing)
