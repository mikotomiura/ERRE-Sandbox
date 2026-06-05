"""``score_saturation`` decision-table coverage (saturation ADR section 3.1-3.5).

Synthetic-fixture, CPU-only. Each test drives one branch of the 3-way verdict so
the frozen ADR section 3.0 thresholds are exercised without a real Ollama run
(that is a separate downstream task). The fixtures build
:class:`SaturationTraceRow` directly; ``floor_fingerprint_hash`` is tied to the
floor value (``fp{round(floor,6)}``) so a constant floor yields a stable
fingerprint (no drop) and a changing floor yields a fingerprint reset (drop a) —
mirroring how the real reconcile drops a stale modulation on an evidence change.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

import duckdb
import pytest

from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.saturation.loader import (
    SaturationLoaderError,
    read_saturation_trace_rows,
    score_saturation,
)
from erre_sandbox.evidence.saturation.trace_ddl import (
    TABLE_NAME,
    SaturationTraceRow,
    bootstrap_saturation_trace_schema,
    column_names,
)

_FULL_TICKS = range(10, 30)  # post-warmup; T_run = 29 (>= 25), terminal = [25, 29]
_FloatOrFn = float | Callable[[int], float]


def _val(spec: _FloatOrFn, tick: int) -> float:
    return spec(tick) if callable(spec) else spec


def _channel(
    *,
    seed: int,
    key: str,
    ticks: Iterable[int] = _FULL_TICKS,
    floor: _FloatOrFn,
    mod: _FloatOrFn,
    individual: str = "kant",
    axis: str = "self",
    run_id: str = "r",
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


def _saturated_seed(seed: int, *, n: int = 6) -> list[SaturationTraceRow]:
    """n channels pinned at the cap (floor 0.5, modulated 0.65 -> magnitude 0.15)."""
    rows: list[SaturationTraceRow] = []
    for i in range(n):
        rows += _channel(seed=seed, key=f"k{i}", floor=0.5, mod=0.65)
    return rows


def _non_saturated_seed(seed: int, *, n: int = 6) -> list[SaturationTraceRow]:
    """n active channels with headroom (magnitude 0.05, cap_distance 0.10 > eta)."""
    rows: list[SaturationTraceRow] = []
    for i in range(n):
        rows += _channel(seed=seed, key=f"k{i}", floor=0.5, mod=0.55)
    return rows


# ---------------------------------------------------------------------------
# SATURATED / NON-SATURATED
# ---------------------------------------------------------------------------


def test_saturated_verdict_three_agreeing_seeds() -> None:
    rows = _saturated_seed(1) + _saturated_seed(2) + _saturated_seed(3)
    result = score_saturation(rows)
    assert result.verdict == "SATURATED"
    assert result.n_valid_seeds == 3
    assert result.median_sat_frac == 1.0
    assert all(s.label == "SATURATED" for s in result.seeds)
    assert all(s.gate_pass for s in result.seeds)


def test_non_saturated_verdict_headroom() -> None:
    rows = _non_saturated_seed(1) + _non_saturated_seed(2) + _non_saturated_seed(3)
    result = score_saturation(rows)
    assert result.verdict == "NON-SATURATED"
    assert result.median_sat_frac == 0.0
    assert all(s.n_active == 6 and s.n_saturated == 0 for s in result.seeds)


# ---------------------------------------------------------------------------
# INCONCLUSIVE — gate failures
# ---------------------------------------------------------------------------


def test_inconclusive_high_drop_churn() -> None:
    """Floor changes every tick -> fingerprint reset each step -> drop_rate ~ 1.0."""

    def _churn_seed(seed: int) -> list[SaturationTraceRow]:
        rows: list[SaturationTraceRow] = []
        for i in range(6):
            rows += _channel(
                seed=seed,
                key=f"k{i}",
                floor=lambda t: 0.40 + 0.001 * t,  # distinct each tick -> fp resets
                mod=lambda t: 0.45 + 0.001 * t,  # magnitude 0.05 (active)
            )
        return rows

    result = score_saturation(_churn_seed(1) + _churn_seed(2) + _churn_seed(3))
    assert result.verdict == "INCONCLUSIVE"
    for s in result.seeds:
        assert s.drop_rate >= 0.50
        assert not s.gate_pass


def test_inconclusive_high_transient_survivor_bias() -> None:
    """Most active channels vanish before the terminal window (survivor bias)."""

    def _transient_seed(seed: int) -> list[SaturationTraceRow]:
        rows: list[SaturationTraceRow] = []
        # 2 persistent (span the terminal window) keep the individual grid alive.
        for i in range(2):
            rows += _channel(seed=seed, key=f"persist{i}", floor=0.5, mod=0.55)
        # 4 transient: active early, absent from the terminal window.
        for i in range(4):
            rows += _channel(
                seed=seed, key=f"trans{i}", ticks=range(10, 21), floor=0.5, mod=0.55
            )
        return rows

    result = score_saturation(
        _transient_seed(1) + _transient_seed(2) + _transient_seed(3)
    )
    assert result.verdict == "INCONCLUSIVE"
    for s in result.seeds:
        assert s.n_transient_active == 4
        assert s.transient_active_rate >= 0.50
        assert s.drop_rate < 0.50  # transient gate fails, not the drop gate
        assert not s.gate_pass


def test_inconclusive_low_engagement() -> None:
    """Fewer than min_active_channels active -> engagement gate fails."""

    def _sparse_seed(seed: int) -> list[SaturationTraceRow]:
        rows: list[SaturationTraceRow] = []
        for i in range(3):  # 3 active < MIN_ACTIVE_CHANNELS (5)
            rows += _channel(seed=seed, key=f"act{i}", floor=0.5, mod=0.65)
        for i in range(3):  # inactive (magnitude 0)
            rows += _channel(seed=seed, key=f"idle{i}", floor=0.5, mod=0.5)
        return rows

    result = score_saturation(_sparse_seed(1) + _sparse_seed(2) + _sparse_seed(3))
    assert result.verdict == "INCONCLUSIVE"
    for s in result.seeds:
        assert s.n_active == 3
        assert not s.gate_pass


def test_inconclusive_n3_label_mismatch() -> None:
    rows = _saturated_seed(1) + _non_saturated_seed(2) + _saturated_seed(3)
    result = score_saturation(rows)
    assert result.verdict == "INCONCLUSIVE"
    assert result.n_valid_seeds == 3
    labels = sorted({s.label for s in result.seeds})
    assert labels == ["NON-SATURATED", "SATURATED"]


# ---------------------------------------------------------------------------
# Paired N=3 exactness (Codex HIGH-2): bind only when exactly 3 seeds, all valid
# ---------------------------------------------------------------------------


def test_four_agreeing_seeds_do_not_bind() -> None:
    """A 4th agreeing seed must NOT bind (>= N would be a forking-paths risk)."""
    rows = (
        _saturated_seed(1)
        + _saturated_seed(2)
        + _saturated_seed(3)
        + _saturated_seed(4)
    )
    result = score_saturation(rows)
    assert result.verdict == "INCONCLUSIVE"
    assert result.n_valid_seeds == 4
    assert "paired N=3 not met" in result.notes


def test_three_valid_one_invalid_does_not_bind() -> None:
    """3 valid + 1 INVALID seed (4 seeds total) -> not exactly N -> INCONCLUSIVE."""
    rows = (
        _saturated_seed(1)
        + _saturated_seed(2)
        + _saturated_seed(3)
        + _channel(seed=4, key="k0", ticks=range(10, 21), floor=0.5, mod=0.65)
    )
    result = score_saturation(rows)
    assert result.verdict == "INCONCLUSIVE"
    assert result.n_valid_seeds == 3  # the short seed is INVALID, excluded
    assert "paired N=3 not met" in result.notes


# ---------------------------------------------------------------------------
# INVALID seeds
# ---------------------------------------------------------------------------


def test_run_invalid_t_run_below_min() -> None:
    """A seed whose max tick < T_RUN_MIN (25) is INVALID and excluded."""
    rows = [
        *_channel(seed=1, key="k0", ticks=range(10, 21), floor=0.5, mod=0.65),
    ]
    result = score_saturation(rows)
    seed1 = result.seeds[0]
    assert seed1.label == "INVALID"
    assert seed1.invalid_reason == "t_run_below_min"
    assert not seed1.valid
    # Only 1 (INVALID) seed -> insufficient valid seeds -> INCONCLUSIVE.
    assert result.verdict == "INCONCLUSIVE"
    assert result.n_valid_seeds == 0


def test_seed_invalid_provenance_false() -> None:
    rows = _channel(seed=1, key="k0", floor=0.5, mod=0.65, layer=False)
    result = score_saturation(rows)
    assert result.seeds[0].label == "INVALID"
    assert result.seeds[0].invalid_reason == "provenance_false"


def test_seed_invalid_nan_value() -> None:
    rows = _channel(seed=1, key="k0", floor=0.5, mod=float("nan"))
    result = score_saturation(rows)
    assert result.seeds[0].label == "INVALID"
    assert result.seeds[0].invalid_reason == "nan_value"


# ---------------------------------------------------------------------------
# MED-1 boundary-floor + HIGH-1 two-sided slope
# ---------------------------------------------------------------------------


def test_boundary_floor_not_underestimated() -> None:
    """floor=0.92, modulated=1.0 -> room_eff=0.08, cap_distance=0 -> SATURATED.

    Naive ``0.15 - magnitude`` would read cap_distance 0.07 (> eta) and miss this
    saturation; the signed ``room_eff`` (ADR section 2.2) catches it. The channel is
    also counted as boundary-floor (|floor| > 0.85).
    """

    def _boundary_seed(seed: int) -> list[SaturationTraceRow]:
        rows: list[SaturationTraceRow] = []
        for i in range(6):
            rows += _channel(seed=seed, key=f"b{i}", floor=0.92, mod=1.0)
        return rows

    result = score_saturation(_boundary_seed(1) + _boundary_seed(2) + _boundary_seed(3))
    assert result.verdict == "SATURATED"
    for s in result.seeds:
        assert s.n_saturated == 6
        assert s.n_boundary_floor == 6


def test_two_sided_flat_rejects_negative_slope_exit() -> None:
    """A channel leaving the cap (steep negative terminal slope) is NOT saturated.

    Magnitude decays 0.15 -> 0.03 across the terminal window (slope ~ -0.03 <
    -slope_tol), so even though early terminal ticks sit at the cap the two-sided
    flat test rejects it and it is logged as terminal_exit (HIGH-1).
    """
    # magnitude(t) decreasing over the terminal window; constant floor keeps fp stable.
    decay = {25: 0.15, 26: 0.12, 27: 0.09, 28: 0.06, 29: 0.03}

    def _exit_channel(seed: int, key: str) -> list[SaturationTraceRow]:
        def _mod(t: int) -> float:
            mag = decay.get(t, 0.15)  # pre-terminal pinned at the cap
            return 0.5 + mag

        return _channel(seed=seed, key=key, floor=0.5, mod=_mod)

    def _exit_seed(seed: int) -> list[SaturationTraceRow]:
        rows: list[SaturationTraceRow] = []
        for i in range(6):
            rows += _exit_channel(seed, f"e{i}")
        return rows

    result = score_saturation(_exit_seed(1) + _exit_seed(2) + _exit_seed(3))
    for s in result.seeds:
        assert s.n_terminal_exit == 6
        assert s.n_saturated == 0
    # No saturated channels, gates pass -> sat_frac 0 -> NON-SATURATED.
    assert result.verdict == "NON-SATURATED"


def test_drop_b_counted_when_sibling_persists() -> None:
    """drop(b): a channel that disappears while a sibling persists IS counted.

    The per-individual grid stays alive on the sibling's rows (DA-IMPL-6), so the
    vanished channel's last active tick registers a drop. (The bounded limitation —
    a total-SWM-collapse tick where *no* row exists — is documented on
    ``_drop_rate`` and not reachable from synthetic rows here.)
    """

    def _sibling_seed(seed: int) -> list[SaturationTraceRow]:
        # 5 persistent channels keep the grid alive across 10..29.
        rows: list[SaturationTraceRow] = []
        for i in range(5):
            rows += _channel(seed=seed, key=f"keep{i}", floor=0.5, mod=0.55)
        # 1 channel active early then gone -> drop(b) at its last active tick.
        rows += _channel(
            seed=seed, key="gone", ticks=range(10, 21), floor=0.5, mod=0.55
        )
        return rows

    result = score_saturation(_sibling_seed(1) + _sibling_seed(2) + _sibling_seed(3))
    for s in result.seeds:
        assert s.drop_rate > 0.0  # the disappearance was counted as a drop


# ---------------------------------------------------------------------------
# Integrity + DuckDB round-trip
# ---------------------------------------------------------------------------


def test_duplicate_key_raises_loud() -> None:
    row = _channel(seed=1, key="k0", ticks=[10], floor=0.5, mod=0.65)[0]
    with pytest.raises(SaturationLoaderError, match="duplicate"):
        score_saturation([row, row])


def test_duckdb_round_trip_scores_saturated() -> None:
    """Rows written through the DDL + read back by the loader score identically."""
    rows = _saturated_seed(1) + _saturated_seed(2) + _saturated_seed(3)
    con = duckdb.connect(":memory:")
    con.execute(f"CREATE SCHEMA {METRICS_SCHEMA}")
    bootstrap_saturation_trace_schema(con, METRICS_SCHEMA)
    cols = column_names()
    insert_sql = (
        f"INSERT INTO {METRICS_SCHEMA}.{TABLE_NAME} "  # noqa: S608 — static identifiers, test
        f"({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    )
    for row in rows:
        con.execute(insert_sql, row.to_row())
    read_back = read_saturation_trace_rows(con)
    assert len(read_back) == len(rows)
    assert score_saturation(read_back).verdict == "SATURATED"
