"""判別性 gate 段 2 の plan と stats の境界の test (段 3.5 で足したもの).

変異 harness (``scripts/benchmark_stage2_driver_mutation_check.py``) の witness。
凍結の ``tests/test_benchmark_stage2/test_stats.py`` が捕まえなかった境界
(予算ちょうど・L arm の ⊥ ちょうど 1/5・費用の順が名前の順と違う本走の順) を、
値そのもので pin する。``benchmark_stage2_stats`` は凍結物なので import だけ
(変異は harness の複製の中だけ)。
"""

from __future__ import annotations

import numpy as np
from scripts import benchmark_stage2_plan as pl
from scripts import benchmark_stage2_stats as st


def _mp(**kw: object) -> st.ModelPilot:
    base: dict[str, object] = {
        "lookup_ok": True,
        "bot_counts": (0, 0, 0, 0),
        "bot_n": 720,
        "know_ok": True,
        "control_counts": (0, 0, 0, 0),
        "envelope_ok": True,
    }
    base.update(kw)
    return st.ModelPilot(**base)  # type: ignore[arg-type]


def test_budget_boundary_is_inclusive() -> None:
    # v2 の R 216 は 216 × 50 秒 = 3 時間ちょうど (予算ちょうどは GO)
    assert st.SPECS["v2"].sec_per_rep() * 216 == st.BUDGET_SECONDS
    assert st.budget({"v2": 216}) == {"v2": st.GATE_GO}
    assert st.budget({"v2": 224}) == {"v2": st.GATE_HELD_COST}


def test_control_arm_bottom_boundary_is_inclusive() -> None:
    # L arm の ⊥ 144 / 720 = 1/5 ちょうどは通り、145 で落ちる (§A)
    assert st.qualify("v3", _mp(control_counts=(0, 0, 0, 144))) == st.ENTERED
    assert st.qualify("v3", _mp(control_counts=(0, 0, 0, 145))) == st.REASON_CONTROL


def test_main_order_is_by_cost_not_by_name() -> None:
    # 費用 (8B 換算の秒): O_time 6 × 625/24 = 156.25、v2 8 × 50 = 400、
    # G 36 × 125/6 = 750
    assert pl.main_order({"v2": 8, "G": 36, "O_time": 6}) == ["O_time", "v2", "G"]


def _decide(units: np.ndarray, k_tests: int) -> str:
    n = units.shape[1]
    halves = np.arange(n) % 2
    return st.decide_battery(
        units, k_tests, 3, halves, n_entered=units.shape[0]
    ).verdict


def test_decide_level_is_alpha_over_k() -> None:
    # 対差 0.3 の定数 × 80 単位: α/6 では下限 ≥ Δ_min、α/600 では届かない
    units = np.stack([np.full(80, 0.3), np.zeros(80), np.zeros(80)])
    assert _decide(units, 6) == st.VERDICT_ESTABLISHED
    assert _decide(units, 600) == st.VERDICT_INCONCLUSIVE


def test_decide_threshold_is_delta_min() -> None:
    # 対差 0.15 × 101 単位: 下限は 0 を越えるが Δ_min = 0.10 に届かない
    d = np.full(101, 0.15)
    assert 0.0 < st.lower_bound(d, -2.0, 2.0, st.ALPHA / 6) < st.DELTA_MIN
    units = np.stack([d, np.zeros(101), np.zeros(101)])
    assert _decide(units, 6) == st.VERDICT_INCONCLUSIVE


def test_equivalence_band_is_point_one() -> None:
    # 全モデルが同じ (対差 0) × 69 単位: 下限は −0.2 と −0.1 の間
    # (同等域 ±0.10 に入らない)
    lb = st.lower_bound(np.zeros(69), -2.0, 2.0, st.ALPHA / 6)
    assert -2 * st.EQUIV < lb < -st.EQUIV
    assert _decide(np.zeros((3, 69)), 6) == st.VERDICT_INCONCLUSIVE


def test_concentration_level_is_alpha_over_two_sum_m() -> None:
    # 0 × 62 単位: 各側 α/(2ΣM) では床と言えず、α/ΣM なら言えてしまう境目
    units = np.zeros((3, 62))
    assert st.concentration(units, 3) is None
    level = st.ALPHA / 3
    assert all(
        st.rejects_lower(u, st.FLOOR_BAND[0], -1.0, level)
        and st.rejects_upper(u, st.FLOOR_BAND[1], 1.0, level)
        for u in units
    )
    assert st.concentration(np.zeros((3, 400)), 3) == "floor"


def test_worst_pair_breaks_ties_to_the_first_pair() -> None:
    # (0, 1) と (1, 2) の対差の分散が同じ 1/3 (最大)。同点は番号の若い対
    u = np.array([[0.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 1.0], [0.0, 0.0, 0.0, 0.0]])
    assert st.worst_pair(u) == (0, 1)
