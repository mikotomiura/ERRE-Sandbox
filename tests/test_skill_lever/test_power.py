"""OC 模擬 (prereg v2 §6).

植える効果と閾値の分離 (DB-1 の修正) と、模擬が判定と同じ式を通ること。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from scripts import skill_lever_scorer as sc
from scripts.stage_b_scorer import (
    VERDICT_ABSENT,
    VERDICT_INVALID_BATTERY,
    VERDICT_PASS,
    signflip_p,
)

_TABLE = (
    Path(__file__).resolve().parents[2]
    / "experiments"
    / "20260926-skill-lever-pilot"
    / "results"
    / "power_table.json"
)
_EASY = sc.Nuisance(base="uniform", bot=0.0, sd=0.05)
_N = 400


def test_plant_is_distinct_from_threshold() -> None:
    """δ_plant で PASS が多数派、τ ちょうどでは PASS はほぼ出ない.

    旧 §4 の ~0.5 頭打ち (植える効果 = 閾値) が無いことの pin。
    """
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


def test_pass_rate_increases_with_effect() -> None:
    nu = sc.Nuisance(base="label_skew", bot=0.1, sd=0.3)
    rates = [sc.simulate(nu, 4, 5, e, _N)[VERDICT_PASS] for e in (0.0, 0.3, 0.6, 0.8)]
    assert rates == sorted(rates)
    assert rates[0] == 0.0


def test_simulated_flip_p_matches_exact_signflip() -> None:
    """模擬の符号反転 p (全列挙の範囲) は判定で使う ``signflip_p`` と一致する."""
    rng = np.random.default_rng(0)
    x = rng.normal(0.1, 0.3, size=(5, 2 * sc.FROZEN_R))
    flips, exact = sc._flip_matrix(x.shape[1], rng)
    assert exact
    got = sc._flip_p(x, flips, exact)
    want = [signflip_p(row) for row in x]
    assert np.allclose(got, want)


def test_mixture_model_hits_the_target_effect() -> None:
    """効果モデル: sd=0・uniform なら E[C] = 指定した効果 (simplex 内の混合で植える)."""
    nu = sc.Nuisance(base="uniform", bot=0.1, sd=0.0)
    res = sc.simulate(nu, sc.FROZEN_R, 20, 0.45, 200)
    assert res[VERDICT_PASS] > 0.9  # 0.45 > τ、分散は多項だけ


@pytest.mark.skipif(not _TABLE.exists(), reason="power table not generated")
def test_frozen_design_is_the_power_table_choice() -> None:
    table = json.loads(_TABLE.read_text(encoding="utf-8"))
    assert table["chosen"] == {"R": sc.FROZEN_R, "K": sc.FROZEN_K}
    assert table["tau"] == pytest.approx(sc.TAU)
    assert table["delta_plant"] == pytest.approx(sc.DELTA_PLANT)
    final = [f for f in table["final"] if f["ok"]]
    assert final
    assert (final[-1]["R"], final[-1]["K"]) == (sc.FROZEN_R, sc.FROZEN_K)
    assert all(row["ok"] for row in final[-1]["rows"])
