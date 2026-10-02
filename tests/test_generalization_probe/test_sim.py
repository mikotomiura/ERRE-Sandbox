"""見取り図の模擬と R の選定規則 (prereg §7).

本計算は CI で回さず、性質だけを小さな回数で pin する。
"""

from __future__ import annotations

import numpy as np
import pytest
from scripts import generalization_probe_battery as bat
from scripts import generalization_probe_scorer as sc
from scripts import generalization_probe_sim as sim

R = 6


def test_design_indices() -> None:
    dz = sim.design(R)
    assert dz.unit_family.size == 96
    u = 5  # r = 0, 族 0, つ組 5
    assert (dz.unit_r[u], dz.unit_family[u], dz.unit_triple[u]) == (0, 0, 5)
    assert dz.position0[u].tolist() == [5 % 3] * 3
    assert dz.w_idx[u, :, 0].tolist() == [0, 1, 2]  # arm 0 の w = 分類
    assert dz.w_idx[u, :, 1].tolist() == [1, 2, 0]  # 回転の w = 次の分類
    assert np.array_equal(dz.foil_idx[..., 0], dz.w_idx[..., 1])
    for fi in range(2):
        order = bat.option_order(fi, 5, 0)
        assert bat.family_actions(fi).index(order[0]) == dz.position0[u, 0]


def test_sim_calibration() -> None:
    nu = sim.Nuisance("uniform", 0.1, "indep")
    out = sim.simulate("homog_sd030", 0.5, R, nu, 600, 1)
    assert out["realized_C"] == pytest.approx(0.5, abs=0.02)


def test_crn_null_exact_zero() -> None:
    dz = sim.design(R)
    rng = np.random.default_rng(0)
    _, c = sim._verdicts_chunk("aon_cell", 0.0, dz, sim.FAVORABLE, 50, rng, None)
    assert np.all(c == 0.0)
    _, c_ind = sim._verdicts_chunk(
        "aon_cell", 0.0, dz, sim.Nuisance("uniform", 0.0, "indep"), 50, rng, None
    )
    assert not np.all(c_ind == 0.0)


def test_anti_coupling_is_more_variable() -> None:
    dz = sim.design(R)
    rng = np.random.default_rng(1)
    _, c_ind = sim._verdicts_chunk(
        "aon_cell", 0.0, dz, sim.Nuisance("uniform", 0.0, "indep"), 400, rng, None
    )
    _, c_anti = sim._verdicts_chunk(
        "aon_cell", 0.0, dz, sim.Nuisance("uniform", 0.0, "anti"), 400, rng, None
    )
    assert float(np.var(c_anti)) > float(np.var(c_ind))
    assert abs(float(np.mean(c_anti))) < 0.02


def test_item_pattern_exact_mean() -> None:
    rng = np.random.default_rng(1)
    vals = sim._exact_item_values(0.3, 5, rng, 0.0, 1.0)
    assert vals.shape == (5, 48)
    assert np.allclose(vals.mean(axis=1), 0.3)
    assert np.all((vals >= 0.0) & (vals <= 1.0))
    dz = sim.design(R)
    lam = sim.lam_array("reverse_1of6", 0.3, dz, sim.FAVORABLE, 3, rng)
    items = lam[:, : 2 * 8, :, 0].reshape(3, -1)
    assert np.all(np.sum(items == -1.0, axis=1) == 8)
    assert np.allclose(items.mean(axis=1), 0.3)


def test_aon_item_fixed_across_replicates() -> None:
    dz = sim.design(R)
    lam = sim.lam_array("aon_item", 0.5, dz, sim.FAVORABLE, 2, np.random.default_rng(2))
    first = lam[:, dz.unit_r == 0, :, 0]
    later = lam[:, dz.unit_r == 3, :, 0]
    assert np.array_equal(first, later)


def test_aon_arm_unit_shape() -> None:
    dz = sim.design(R)
    lam = sim.lam_array(
        "aon_arm_unit", 0.5, dz, sim.FAVORABLE, 200, np.random.default_rng(3)
    )
    assert np.array_equal(lam[:, :, 0, :], lam[:, :, 2, :])  # probe を通じて共通
    assert not np.array_equal(lam[..., 0], lam[..., 1])  # arm ごとに独立
    assert float(lam.mean()) == pytest.approx(0.5, abs=0.02)


def test_sparse_reach() -> None:
    dz = sim.design(R)
    lam = sim.lam_array(
        "sparse_1of3", 0.2, dz, sim.FAVORABLE, 1, np.random.default_rng(3)
    )
    assert np.all(lam[0][dz.probe_class != 0] == 0.0)
    assert np.allclose(lam[0][dz.probe_class == 0], 0.6)
    assert sim.reachable(
        "sparse_1of3", sim.Nuisance("uniform", 0.1, "crn")
    ) == pytest.approx(0.3)


def test_extremal_mean() -> None:
    dz = sim.design(R)
    rng = np.random.default_rng(4)
    lam = sim.lam_array("pass_extremal_0.6", sc.TAU, dz, sim.FAVORABLE, 400, rng)
    assert set(np.unique(lam).tolist()) == {-1.0, 0.6}
    assert float(lam.mean()) == pytest.approx(sc.TAU, abs=0.02)
    lam2 = sim.lam_array("no_go_extremal_0.0", sc.TAU, dz, sim.FAVORABLE, 400, rng)
    assert set(np.unique(lam2).tolist()) == {0.0, 1.0}
    assert float(lam2.mean()) == pytest.approx(sc.TAU, abs=0.02)


def test_logodds_calibration() -> None:
    dz = sim.design(R)
    beta = sim._beta_for(0.5, dz, 0.0)
    assert sim._expected_c_logodds(dz, beta, 0.0) == pytest.approx(0.5, abs=1e-6)
    out = sim.simulate(
        "logodds", 0.5, R, sim.Nuisance("label_skew", 0.0, "crn"), 400, 1
    )
    assert out["realized_C"] == pytest.approx(0.5, abs=0.03)


def test_sim_bottom_gate() -> None:
    out = sim.simulate(
        "aon_cell", 0.3, R, sim.Nuisance("uniform", 0.5, "indep"), 100, 1
    )
    assert out[sc.VERDICT_INVALID_BATTERY] == 1.0


def test_sim_power_and_null() -> None:
    hit = sim.simulate("homog_sd005", sc.DELTA_PLANT, R, sim.FAVORABLE, 200, 1)
    assert hit[sc.VERDICT_PASS] == 1.0
    null = sim.simulate("homog_sd005", 0.0, R, sim.FAVORABLE, 200, 1)
    assert null[sc.VERDICT_ABSENT] == 1.0


def test_pure_extremal_size_small() -> None:
    assert sim.pure_extremal_size(0.6, 96, 2000, 1, "pass") <= 0.05
    assert sim.pure_extremal_size(0.0, 96, 2000, 1, "no_go") <= 0.05


def test_size_threshold_is_exact_binomial() -> None:
    """MC の採否の閾値は二項分布の正確な上側確率で決める (Codex MEDIUM-9)."""
    x = sim.size_count_threshold(996)
    assert x == 595
    assert sim.binom_upper_tail(x + 1, 10_000, 0.05) * 996 <= 0.01
    assert sim.binom_upper_tail(x, 10_000, 0.05) * 996 > 0.01
    assert sim.mc_tolerance(996) == pytest.approx(595 / 10_000 - 0.05)
    assert sim.binom_upper_tail(0, 10, 0.5) == 1.0
    assert sim.binom_upper_tail(10, 10, 0.5) == pytest.approx(2**-10)


def test_boundary() -> None:
    rows = [{"target_C": 0.3, "pass": 0.5}, {"target_C": 0.35, "pass": 0.9}]
    assert sim.boundary(rows) == pytest.approx(0.3375)
    assert sim.boundary([{"target_C": 0.3, "pass": 0.5}]) is None


def test_select_is_r_main_when_it_passes() -> None:
    """選定 = R_MAIN (18) が 3 条件をすべて満たすときだけ.

    小さい R の合否は選定に使わない。
    """
    ok = {"power_ok": True, "no_go_ok": True, "size_ok": True}
    assert sim.R_MAIN == 18
    assert sim.R_CANDIDATES == (6, 12, 18)
    rows = [{"R": 6, **ok}, {"R": 18, **ok}]
    assert sim.select(rows) == {"selected_R": 18, "door_close": False}
    for flag in ("power_ok", "no_go_ok", "size_ok"):
        bad = [{"R": 6, **ok}, {"R": 18, **ok, flag: False}]
        assert sim.select(bad) == {"selected_R": None, "door_close": True}
    assert sim.select([{"R": 6, **ok}]) == {"selected_R": None, "door_close": True}


def test_most_favorable_requires_the_2tau_point() -> None:
    base = {
        "form": "homog_sd005",
        "base": "uniform",
        "bot": 0.0,
        "coupling": "crn",
        "R": 6,
    }
    assert sim.most_favorable_reaches([{**base, "target_C": 0.6, "pass": 0.9}])
    assert not sim.most_favorable_reaches([{**base, "target_C": 0.6, "pass": 0.7}])
    assert not sim.most_favorable_reaches([{**base, "target_C": 0.3, "pass": 0.9}])


def test_size_points_cover_forms() -> None:
    pts = sim.size_points()
    forms = {f for f, _, _ in pts}
    assert set(sim.FORMS) <= forms
    assert "aon_arm_unit" in forms
    assert "weak_null" in forms
    assert {f"pass_extremal_{m}" for m in sim.PASS_EXTREMAL_M} <= forms
    assert {f"no_go_extremal_{m}" for m in sim.NO_GO_EXTREMAL_M} <= forms
    assert len(sim.nuisance_grid()) == 18
    assert {nu.coupling for nu in sim.nuisance_grid()} == {"crn", "indep", "anti"}


def _fake_factory(overrides: dict[tuple[str, float], dict[str, float]]):
    def fake(
        form: str, target: float, r_count: int, nu: sim.Nuisance, n_sims: int, seed: int
    ) -> dict[str, float]:
        del r_count, nu, n_sims, seed
        out = {
            sc.VERDICT_PASS: 0.0,
            sc.VERDICT_ABSENT: 0.0,
            sc.VERDICT_UNDERPOWERED: 1.0,
            sc.VERDICT_INVALID_BATTERY: 0.0,
            "realized_C": target,
        }
        if target == sc.DELTA_PLANT:
            out[sc.VERDICT_PASS] = 0.9
        if target == 0.0 and form in sim.NO_GO_FORMS:
            out[sc.VERDICT_ABSENT] = 0.9
        out.update(overrides.get((form, target), {}))
        return out

    return fake


def test_evaluate_r_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sim, "pure_extremal_size", lambda *_: 0.0)
    monkeypatch.setattr(sim, "simulate", _fake_factory({}))
    res = sim.evaluate_r(R)
    assert (res["power_ok"], res["no_go_ok"], res["size_ok"]) == (True, True, True)
    assert res["n_size_checks"] == 996
    assert res["size_cap"] == pytest.approx(595 / 10_000)
    assert res["n_units"] == 96

    over = {sc.VERDICT_PASS: 0.0596}
    monkeypatch.setattr(sim, "simulate", _fake_factory({("aon_unit", sc.TAU): over}))
    assert sim.evaluate_r(R)["size_ok"] is False
    at_cap = {sc.VERDICT_PASS: 0.0595}
    monkeypatch.setattr(sim, "simulate", _fake_factory({("aon_unit", sc.TAU): at_cap}))
    assert sim.evaluate_r(R)["size_ok"] is True
    over_no_go = {sc.VERDICT_ABSENT: 0.07}
    monkeypatch.setattr(
        sim, "simulate", _fake_factory({("no_go_extremal_0.0", sc.TAU): over_no_go})
    )
    assert sim.evaluate_r(R)["size_ok"] is False
    low = {sc.VERDICT_PASS: 0.79}
    monkeypatch.setattr(
        sim, "simulate", _fake_factory({("logodds", sc.DELTA_PLANT): low})
    )
    assert sim.evaluate_r(R)["power_ok"] is False
    low_no_go = {sc.VERDICT_ABSENT: 0.79}
    monkeypatch.setattr(
        sim, "simulate", _fake_factory({("homog_sd030", 0.0): low_no_go})
    )
    assert sim.evaluate_r(R)["no_go_ok"] is False


def test_crn_shares_randomness_within_the_triple() -> None:
    """crn は族内の 2 arm とつ組の 3 probe で乱数を共有する.

    seed の共有の写し (Codex 2 回目 HIGH-1)。
    """
    dz = sim.design(R)
    base = np.broadcast_to(
        sim.base_probs(dz, "uniform")[None, :, :, None, :],
        (20, dz.unit_family.size, 3, 2, 4),
    )
    idx, _ = sim._draw(base, sim.FAVORABLE, np.random.default_rng(0), 20)
    assert np.all(idx == idx[:, :, :1, :1])
    idx_ind, _ = sim._draw(
        base, sim.Nuisance("uniform", 0.0, "indep"), np.random.default_rng(0), 20
    )
    assert not np.all(idx_ind == idx_ind[:, :, :1, :1])
