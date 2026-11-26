"""判別性 gate 段 2 の見取り図と fixture の差の点検 (prereg §I)."""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
from scripts import benchmark_stage2_sim as sm
from scripts import benchmark_stage2_stats as st

_REPO_ROOT = Path(__file__).resolve().parents[2]
SKETCH = (
    _REPO_ROOT
    / "experiments/20261126-benchmark-stage2-discriminability/results/sketch.json"
)


@pytest.mark.parametrize("battery", st.BATTERIES)
@pytest.mark.parametrize("shape", ["one_diff_2dmin", "all_equal", "floor_one"])
def test_batch_flags_match_decide_battery(battery: str, shape: str) -> None:
    """見取り図の (N,) 本まとめた判定が、stats の 1 本ずつの判定と一致する."""
    rng = np.random.default_rng(7)
    r_main = sm.R_GRID[battery][0]
    c = sm.shapes()[shape]["C"]
    num = sm.generate(battery, c, [], 0.2, 0.3, "indep", r_main, rng, 6)
    m = len(c)
    k, sum_m = 4 * m * (m - 1), 4 * m
    fl = sm.batch_flags(battery, num, k, sum_m, r_main)
    verdict = st.classify(fl["est"], fl["rep"], fl["equiv"], fl["concentrated"])
    spec = st.SPECS[battery]
    halves = st.half_labels(spec, range(spec.main_r0, spec.main_r0 + r_main))
    n_p = sm.PAIRS_PER_UNIT[battery]
    for i in range(num.shape[0]):
        d = st.decide_battery(num[i] / n_p, k, sum_m, halves, n_entered=m)
        assert d.verdict == verdict[i]


@pytest.mark.parametrize("coupling", ["crn", "indep"])
def test_generator_hits_the_target_mean(coupling: str) -> None:
    rng = np.random.default_rng(8)
    c = [0.0, 0.3, -0.4, 0.97]
    num = sm.generate("G", c, [1], 0.2, 0.3, coupling, 36, rng, 400)
    real = num.mean(axis=(0, 2)) / sm.PAIRS_PER_UNIT["G"]
    assert np.allclose(real, c, atol=0.01)


def test_generator_bounds() -> None:
    num = sm.generate(
        "v2", [0.5, -0.5, 1.0], [], 0.3, 1.0, "crn", 8, np.random.default_rng(9), 50
    )
    assert num.min() >= -2
    assert num.max() <= 2


def test_shapes_cover_the_registered_forms() -> None:
    names = set(sm.shapes())
    for need in (
        "all_equal",
        "one_diff_boundary",
        "one_diff_2dmin",
        "monotone",
        "family",
        "ties",
        "zero_rate",
        "floor_all",
        "ceiling_all",
        "select_3",
        "select_5",
    ):
        assert need in names


def test_point_reports_rates() -> None:
    r = sm.point(
        "O_time",
        sm.shapes()["one_diff_2dmin"],
        sm.NOISE[0],
        12,
        np.random.default_rng(1),
        50,
    )
    assert r["P1"] + r["P2"] + r["P3"] == pytest.approx(1.0)
    assert r["negative_size_applies"]


def test_fixture_diffs_lists_large_pairs() -> None:
    fx = sm.fixture_diffs()
    v3 = fx["batteries"]["v3"]["pairs_over_delta_min"]
    assert {
        "high": "outcome_blind",
        "low": "nearest_neighbor_ignoring_weather",
        "diff": 1.0,
    } in v3
    g = fx["batteries"]["G"]
    assert g["source"]["sha256"]
    assert g["max_abs_C"] < st.DELTA_MIN
    assert fx["batteries"]["O_time"]["max_abs_C"] == 0.0


def test_committed_sketch_is_not_door_close() -> None:
    sk = json.loads(SKETCH.read_text(encoding="utf-8"))
    assert sk["door_close_any"] is False
    assert sk["size_ok"] is True
    n_rows = sum(len(v) for v in sm.R_GRID.values()) * len(sm.shapes()) * len(sm.NOISE)
    assert len(sk["rows"]) == n_rows


def test_drop_rows_use_pilot_k_and_reported_set() -> None:
    sh = sm.shapes()
    r = sm.point("v2", sh["drop_diff"], sm.NOISE[0], 8, np.random.default_rng(2), 50)
    # pilot の入場 4 本で K を決める (4·3 + 3·6·5 = 102)、判定は残りの 3 本
    assert r["K"] == 102
    assert r["sum_M"] == 4 + 18
    assert r["reported_models"] == 3
    # 残りの 3 本は同じ C: 誤った否定は報告集合で数える (外したモデルの対を数えない)
    assert not r["negative_size_applies"]
    r2 = sm.point("G", sh["drop_to_2"], sm.NOISE[0], 12, np.random.default_rng(3), 20)
    assert r2["P_not_qualified"] == 1.0
    assert r2["P1_pair"] is None
    assert r2["P1_pair"] is None
    assert r2["P1"] == 0.0


def test_k_is_maximal_for_the_pilot_entrants() -> None:
    r = sm.point(
        "O_time", sm.shapes()["select_3"], sm.NOISE[0], 12, np.random.default_rng(4), 20
    )
    assert r["K"] == 3 * 2 + 90
    assert r["sum_M"] == 21


def test_detection_prob_is_exact() -> None:
    assert sm.detection_prob(2000, 146, 0.15) > 0.999
    assert sm.detection_prob(2000, 146, 0.05) < 0.01


def test_lookup_3_limits_all_batteries() -> None:
    r = sm.point(
        "G", sm.shapes()["lookup_3"], sm.NOISE[0], 12, np.random.default_rng(5), 20
    )
    assert r["K"] == 3 * 2 + 3 * 3 * 2
    assert r["sum_M"] == 12


def test_rule_rows_apply_registered_rules_per_trial() -> None:
    sh = sm.shapes()["rule_bot_all"]
    r = sm.point("O_time", sh, sm.NOISE[0], 12, np.random.default_rng(6), 200)
    tot = r["P1"] + r["P2"] + r["P3"] + r["P_not_qualified"]
    assert tot == pytest.approx(1.0)
    # ⊥ 0.18 の 6 本: pilot の入場と本走の除外が試行ごとに揺れる
    assert 0 < r["mean_entered"] < 6
    assert r["reported_models"] <= r["mean_entered"]


def test_generate_bot_scales_the_mean() -> None:
    num, frac = sm.generate_bot(
        "v2", [0.5, 0.5], [0.0, 0.2], 0.0, 0.0, "crn", 16, np.random.default_rng(7), 300
    )
    real = num.mean(axis=(0, 2)) / sm.PAIRS_PER_UNIT["v2"]
    assert real[0] == pytest.approx(0.5, abs=0.01)
    assert real[1] == pytest.approx(0.4, abs=0.01)
    assert frac[:, 1].mean() == pytest.approx(0.2, abs=0.01)


def test_pair_power_is_undefined_without_a_true_difference() -> None:
    r = sm.point(
        "v2", sm.shapes()["all_equal"], sm.NOISE[0], 8, np.random.default_rng(8), 20
    )
    assert r["P1_pair"] is None


def test_qualify_arms_uses_the_arm_maximum() -> None:
    # Codex r3 HIGH-1: 族の両 arm が 32/144、他方の族が 20/144。族内差 0。
    # 集約 52/288 = 0.181 は通るが、arm 別の最大 32/144 = 0.222 で落ちる
    ok, _ = sm.qualify_arms(np.array([32, 32, 20, 20]), 144)
    assert not ok
    assert Fraction(52, 288) <= Fraction(1, 5)
    ok2, env = sm.qualify_arms(np.array([20, 20, 20, 20]), 144)
    assert ok2
    assert env == Fraction(20, 144) + Fraction(1, 20)


def test_qualify_arms_family_gap() -> None:
    ok, _ = sm.qualify_arms(np.array([0, 11, 0, 0]), 144)  # 11/144 = 0.0764 ≥ 0.075
    assert not ok
    ok2, _ = sm.qualify_arms(np.array([0, 10, 0, 0]), 144)
    assert ok2


def test_envelope_boundary_is_exact() -> None:
    # Codex r3 LOW-2: pilot 207/1440、本走 186/960 は差がちょうど 1/20 で合格
    _, env = sm.qualify_arms(np.array([207, 207, 207, 207]), 1440)
    assert Fraction(186, 960) <= env


def test_rule_rows_record_the_k_used() -> None:
    r = sm.point(
        "O_time",
        sm.shapes()["rule_bot_all"],
        sm.NOISE[0],
        12,
        np.random.default_rng(9),
        200,
    )
    used = sum(r["K_counts"].values())
    assert used + round(r["P_not_qualified"] * 200) == 200
    assert r["max_calibration_err"] < 0.02
