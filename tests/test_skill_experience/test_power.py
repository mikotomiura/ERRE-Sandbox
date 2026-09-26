"""OC 模擬 (prereg v3 §6): clip 後の期待値で定義した真の C・sd=0.5 の size
規則・頭打ちが無いこと."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from scripts import skill_experience_scorer as sc
from scripts import skill_lever_scorer as v2sc
from scripts.stage_b_scorer import VERDICT_ABSENT, VERDICT_INVALID_BATTERY, VERDICT_PASS

_TABLE = (
    Path(__file__).resolve().parents[2]
    / "experiments"
    / "20260926-experience-skill-pilot"
    / "results"
    / "power_table.json"
)
_EASY = sc.Nuisance(base="uniform", bot=0.0, sd=0.05)
_N = 400


def _mc_mean_c(nominal: float, sd: float, bot: float, n: int = 400_000) -> float:
    rng = np.random.default_rng(1)
    live = 1.0 - bot
    lam = np.clip((nominal + sd * rng.standard_normal(n)) / live, -1.0, 1.0)
    return float(live * lam.mean())


@pytest.mark.parametrize(
    ("sd", "bot"), [(0.0, 0.0), (0.05, 0.1), (0.3, 0.0), (0.5, 0.0), (0.5, 0.1)]
)
def test_clipped_effect_matches_monte_carlo(sd: float, bot: float) -> None:
    for mu in (-0.4, 0.0, 0.33, 0.72, 1.2):
        assert sc.clipped_effect(mu, sd, bot) == pytest.approx(
            _mc_mean_c(mu, sd, bot), abs=3e-3
        )


def test_nominal_effect_inverts_clipping() -> None:
    for sd in (0.05, 0.3, 0.5):
        for bot in (0.0, 0.1):
            for c in (0.0, sc.TAU, sc.DELTA_PLANT):
                mu = sc.nominal_effect(c, sd, bot)
                assert sc.clipped_effect(mu, sd, bot) == pytest.approx(c, abs=1e-9)
    # sd=0.5・b=0.1 では τ を植えるのに名目 0.33 程度が要る (名目値 = 真の C ではない)
    assert sc.nominal_effect(sc.TAU, 0.5, 0.1) == pytest.approx(0.3306, abs=1e-3)
    assert sc.nominal_effect(sc.DELTA_PLANT, 0.5, 0.1) == pytest.approx(
        0.7234, abs=1e-3
    )


def test_simulation_plants_the_clipped_expectation() -> None:
    """sd=0.5 でも、植えた真の C = τ のとき PASS と NO_GO がほぼ対称になる
    (名目値で植えると NO_GO 側に偏る)."""
    nu = sc.Nuisance(base="uniform", bot=0.1, sd=0.5)
    res = sc.simulate(nu, 8, 10, sc.TAU, 4_000)
    assert abs(res[VERDICT_PASS] - res[VERDICT_ABSENT]) < 0.03
    nominal = v2sc.simulate(nu, 8, 10, sc.TAU, 4_000)
    assert nominal[VERDICT_ABSENT] - nominal[VERDICT_PASS] > 0.03


def test_plant_is_distinct_from_threshold() -> None:
    at_plant = sc.simulate(_EASY, sc.FROZEN_R, sc.FROZEN_K, sc.DELTA_PLANT, _N)
    at_tau = sc.simulate(_EASY, sc.FROZEN_R, sc.FROZEN_K, sc.TAU, _N)
    assert at_plant[VERDICT_PASS] >= sc.POWER_TARGET
    assert at_tau[VERDICT_PASS] <= 0.12


def test_null_reaches_no_go() -> None:
    at_zero = sc.simulate(_EASY, sc.FROZEN_R, sc.FROZEN_K, 0.0, _N)
    assert at_zero[VERDICT_ABSENT] >= sc.POWER_TARGET
    assert at_zero[VERDICT_PASS] == 0.0


def test_simulation_applies_bottom_gate() -> None:
    heavy = sc.Nuisance(base="uniform", bot=0.3, sd=0.05)
    res = sc.simulate(heavy, sc.FROZEN_R, sc.FROZEN_K, sc.DELTA_PLANT, _N)
    assert res[VERDICT_INVALID_BATTERY] > 0.9


def test_no_power_plateau_at_wide_spread() -> None:
    """sd=0.5 でも R を増やすと P(PASS | δ_plant) が単調に上がり 0.8 を超える (DB-1
    型の天井が無い)."""
    nu = sc.Nuisance(base="label_skew", bot=0.1, sd=0.5)
    rates = [
        sc.simulate(nu, r, 5, sc.DELTA_PLANT, 1_000)[VERDICT_PASS] for r in (4, 8, 12)
    ]
    assert rates == sorted(rates)
    assert rates[-1] > sc.POWER_TARGET


def test_size_cap_depends_on_spread() -> None:
    assert sc.size_cap(0.05, 10_000) == pytest.approx(sc.ALPHA + sc.mc_margin(10_000))
    assert sc.size_cap(0.3, 10_000) == pytest.approx(sc.ALPHA + sc.mc_margin(10_000))
    assert sc.size_cap(0.5, 10_000) == pytest.approx(1.5 * sc.ALPHA)


def test_criteria_ok_requires_all_four() -> None:
    good = sc.Criteria(0.9, 0.9, 0.05, 0.05, 0.0565)
    assert good.ok
    for bad in (
        sc.Criteria(0.7, 0.9, 0.05, 0.05, 0.0565),
        sc.Criteria(0.9, 0.7, 0.05, 0.05, 0.0565),
        sc.Criteria(0.9, 0.9, 0.06, 0.05, 0.0565),
        sc.Criteria(0.9, 0.9, 0.05, 0.06, 0.0565),
    ):
        assert not bad.ok


def test_frozen_design_is_the_power_table_choice() -> None:
    """凍結物の power 表が存在し、選定 (R, K) が scorer の凍結値と一致する (無ければ
    skip でなく fail)."""
    assert _TABLE.is_file()
    table = json.loads(_TABLE.read_text(encoding="utf-8"))
    assert table["chosen"] == {"R": sc.FROZEN_R, "K": sc.FROZEN_K}
    assert table["tau"] == pytest.approx(sc.TAU)
    assert table["effect_definition"] == "clipped_expectation"
    final = [f for f in table["final"] if f["ok"]]
    assert final
    assert (final[-1]["R"], final[-1]["K"]) == (sc.FROZEN_R, sc.FROZEN_K)
    rows = final[-1]["rows"]
    assert len(rows) == 18
    assert all(row["ok"] for row in rows)
    assert {row["nuisance"]["sd"] for row in rows} == {0.05, 0.3, 0.5}
