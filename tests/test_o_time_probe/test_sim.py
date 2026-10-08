"""見取り図の模擬と R の選定規則 (prereg §7).

本計算は CI で回さず、性質だけを小さな回数で pin する。
"""

from __future__ import annotations

import functools
from typing import Any

import numpy as np
import pytest
from scripts import o_time_probe_battery as bat
from scripts import o_time_probe_scorer as sc
from scripts import o_time_probe_sim as sim

R = 6


def test_design_indices() -> None:
    dz = sim.design(R)
    assert dz.unit_family.size == 72
    u = 8  # r = 0, 族 1, 部屋 2
    assert (dz.unit_family[u], dz.unit_room[u]) == (1, 2)
    assert dz.position0[u] == 2
    assert dz.a_side[u] == 2
    assert dz.b_side[u] == 0
    assert dz.w_idx[u].tolist() == [0, 2]  # fwd の w = B 側、bwd の w = A 側
    assert dz.foil_idx[u].tolist() == [2, 0]
    for k, unit in enumerate(bat.units(R)):
        order = bat.option_order(unit.family, unit.room, unit.replicate)
        assert bat.family_actions(unit.family).index(order[0]) == dz.position0[k]
        w, foil = bat.pointed(bat.FAMILIES[unit.family][0], unit.room)
        assert bat.family_actions(unit.family)[dz.w_idx[k, 0]] == w
        assert bat.family_actions(unit.family)[dz.foil_idx[k, 0]] == foil


def test_a_first_matches_layout() -> None:
    dz = sim.design(R)
    for k, unit in enumerate(bat.units(R)):
        order = bat.entry_order(unit.family, unit.room, unit.replicate)
        room = bat.ROOMS[unit.room]
        labels = [lab for rm, lab in order if rm == room]
        assert (labels[0] == bat.first_rule_label(unit.family, unit.room)) == bool(
            dz.a_first[k]
        )
    assert 0 < float(dz.a_first.mean()) < 1


def test_sim_calibration() -> None:
    nu = sim.Nuisance("uniform", 0.1, "indep")
    out = sim.simulate("homog_sd030", 0.5, R, nu, 600, 1)
    assert out["realized_C"] == pytest.approx(0.5, abs=0.02)


def test_crn_null_exact_zero() -> None:
    """crn では、効果ゼロのとき単位の 4 セルが同じ label を選ぶ.

    D が厳密に 0 (定理 1 の写し)。
    """
    dz = sim.design(R)
    rng = np.random.default_rng(0)
    _, c = sim._verdicts_chunk("aon_cell", 0.0, dz, sim.FAVORABLE, 50, rng, None)
    assert np.all(c == 0.0)
    _, c_ind = sim._verdicts_chunk(
        "aon_cell", 0.0, dz, sim.Nuisance("uniform", 0.0, "indep"), 50, rng, None
    )
    assert not np.all(c_ind == 0.0)


def test_crn_shares_randomness_within_the_unit() -> None:
    dz = sim.design(R)
    base = np.broadcast_to(
        sim.base_probs(dz, "uniform")[None, :, None, None, :],
        (20, dz.unit_family.size, 2, 2, 4),
    )
    idx, _ = sim._draw(base, sim.FAVORABLE, np.random.default_rng(0))
    assert np.all(idx == idx[:, :, :1, :1])
    idx_ind, _ = sim._draw(
        base, sim.Nuisance("uniform", 0.0, "indep"), np.random.default_rng(0)
    )
    assert not np.all(idx_ind == idx_ind[:, :, :1, :1])
    idx_anti, _ = sim._draw(
        base, sim.Nuisance("uniform", 0.0, "anti"), np.random.default_rng(0)
    )
    assert not np.all(idx_anti[..., 0] == idx_anti[..., 1])


def test_anti_coupling_null_is_centered_but_not_exact() -> None:
    """anti は効果ゼロで平均 0 付近だが、crn のような単位ごとの厳密な 0 ではない."""
    dz = sim.design(R)
    rng = np.random.default_rng(1)
    _, c_anti = sim._verdicts_chunk(
        "aon_cell", 0.0, dz, sim.Nuisance("uniform", 0.0, "anti"), 400, rng, None
    )
    assert float(np.var(c_anti)) > 0.0
    assert abs(float(np.mean(c_anti))) < 0.02


def test_item_pattern_exact_mean() -> None:
    rng = np.random.default_rng(1)
    vals = sim._exact_item_values(0.3, 5, rng, 0.0, 1.0)
    assert vals.shape == (5, 12)
    assert np.allclose(vals.mean(axis=1), 0.3)
    dz = sim.design(R)
    lam = sim.lam_array("reverse_1of6", 0.3, dz, sim.FAVORABLE, 3, rng)
    items = lam[:, :12, 0, 0]  # r = 0 の 12 単位 = 12 項目
    assert np.all(np.sum(items == -1.0, axis=1) == 2)
    assert np.allclose(items.mean(axis=1), 0.3)


def test_aon_item_fixed_across_replicates() -> None:
    dz = sim.design(R)
    lam = sim.lam_array("aon_item", 0.5, dz, sim.FAVORABLE, 2, np.random.default_rng(2))
    r0 = bat.units(R)[:12]
    assert all(u.replicate == 0 for u in r0)
    assert np.array_equal(lam[:, :12], lam[:, 36:48])


def test_aon_arm_unit_shape() -> None:
    dz = sim.design(R)
    lam = sim.lam_array(
        "aon_arm_unit", 0.5, dz, sim.FAVORABLE, 200, np.random.default_rng(3)
    )
    assert np.array_equal(lam[:, :, 0, :], lam[:, :, 1, :])  # 書き方を通じて共通
    assert not np.array_equal(lam[..., 0], lam[..., 1])  # arm ごとに独立
    assert float(lam.mean()) == pytest.approx(0.5, abs=0.02)


def test_sparse_reach() -> None:
    dz = sim.design(R)
    lam = sim.lam_array(
        "sparse_1of3", 0.2, dz, sim.FAVORABLE, 1, np.random.default_rng(3)
    )
    assert np.all(lam[0][dz.unit_room >= 2] == 0.0)
    assert np.allclose(lam[0][dz.unit_room < 2], 0.6)
    assert sim.reachable(
        "sparse_1of3", sim.Nuisance("uniform", 0.1, "crn"), R
    ) == pytest.approx(0.3)


def test_asc_only_and_chrono_only() -> None:
    dz = sim.design(R)
    rng = np.random.default_rng(4)
    lam = sim.lam_array("asc_only", 0.4, dz, sim.FAVORABLE, 1, rng)
    assert np.all(lam[0, :, 1, :] == 0.0)
    assert np.allclose(lam[0, :, 0, :], 0.8)
    lam_c = sim.lam_array("chrono_only", 0.4, dz, sim.FAVORABLE, 1, rng)
    assert np.allclose(lam_c[0].sum(axis=2), 0.8)  # 単位ごとにちょうど 1 arm
    assert np.allclose(lam_c[0, dz.a_first, :, 0], 0.8)
    assert sim.reachable("asc_only", sim.FAVORABLE, R) == 0.5
    assert sim.reachable("chrono_only", sim.FAVORABLE, R) == pytest.approx(0.5)
    out = sim.simulate("asc_only", 0.45, R, sim.FAVORABLE, 200, 1)
    assert out["realized_C"] == pytest.approx(0.45, abs=0.03)


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


def test_base_probs() -> None:
    dz = sim.design(R)
    p = sim.base_probs(dz, "label_skew")
    assert np.allclose(p.sum(axis=1), 1.0)
    assert np.allclose(p[np.arange(dz.unit_family.size), dz.a_side], 0.95 * 0.7)
    q = sim.base_probs(dz, "position_skew")
    assert np.allclose(q[np.arange(dz.unit_family.size), dz.position0], 0.95 * 0.7)


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
    assert sim.pure_extremal_size(0.6, 72, 2000, 1, "pass") <= 0.05
    assert sim.pure_extremal_size(0.0, 72, 2000, 1, "no_go") <= 0.05


def test_size_threshold_is_exact_binomial() -> None:
    x = sim.size_count_threshold(996)
    assert x == 595
    assert sim.binom_upper_tail(x + 1, 10_000, 0.05) * 996 <= 0.01
    assert sim.binom_upper_tail(x, 10_000, 0.05) * 996 > 0.01
    assert sim.mc_tolerance(996) == pytest.approx(595 / 10_000 - 0.05)
    assert sim.binom_upper_tail(0, 10, 0.5) == 1.0
    assert sim.binom_upper_tail(10, 10, 0.5) == pytest.approx(2**-10)


def test_boundary() -> None:
    assert sim.boundary([(0.3, 0.5), (0.35, 0.9)]) == pytest.approx(0.3375)
    assert sim.boundary([(0.3, 0.5)]) is None
    assert sim.boundary([(0.2, 0.9), (0.25, 0.5)], rising=False) == pytest.approx(
        0.2125
    )
    assert sim.boundary([(0.2, 0.7)], rising=False) is None


def test_select_is_the_largest_passing_candidate() -> None:
    ok = {
        "power_ok": True,
        "no_go_ok": True,
        "size_ok": True,
        "band_ok": True,
        "calibrated": True,
    }
    assert sim.R_CANDIDATES == (96, 192, 288)
    rows = [{"R": r, **ok} for r in sim.R_CANDIDATES]
    assert sim.select(rows) == {"selected_R": 288, "door_close": False}
    rows[-1]["band_ok"] = False
    assert sim.select(rows) == {"selected_R": 192, "door_close": False}
    for flag in ok:
        bad = [{"R": r, **ok, flag: False} for r in sim.R_CANDIDATES]
        assert sim.select(bad) == {"selected_R": None, "door_close": True}


def test_most_favorable_requires_the_2tau_point() -> None:
    base = {
        "form": "homog_sd005",
        "base": "uniform",
        "bot": 0.0,
        "coupling": "crn",
        "R": 24,
    }
    assert sim.most_favorable_reaches([{**base, "target_C": 0.6, "pass": 0.9}])
    assert not sim.most_favorable_reaches([{**base, "target_C": 0.6, "pass": 0.7}])
    assert not sim.most_favorable_reaches([{**base, "target_C": 0.3, "pass": 0.9}])
    assert not sim.most_favorable_reaches(
        [{**base, "coupling": "indep", "target_C": 0.6, "pass": 0.9}]
    )


def test_size_points_cover_forms() -> None:
    pts = sim.size_points()
    forms = {f for f, _, _ in pts}
    assert set(sim.FORMS) <= forms
    assert "weak_null" in forms
    assert {f"pass_extremal_{m}" for m in sim.PASS_EXTREMAL_M} <= forms
    assert {f"no_go_extremal_{m}" for m in sim.NO_GO_EXTREMAL_M} <= forms
    assert len(sim.nuisance_grid()) == 18
    assert len(pts) == 2 * len(sim.FORMS) + 1 + 8


def test_band_points() -> None:
    pts = sim.band_points()
    assert len(pts) == 2 * 4 * 2
    assert {t for _, t, _ in pts} == {0.25, 0.35}
    assert {nu.coupling for _, _, nu in pts} == {"crn"}
    assert {nu.base for _, _, nu in pts} == {"uniform", "position_skew"}
    assert {f for f, _, _ in pts} == {"homog_sd005", "homog_sd030"}


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
        if target == 0.35:
            out[sc.VERDICT_PASS] = 0.85
        if target == 0.25:
            out[sc.VERDICT_ABSENT] = 0.85
        out.update(overrides.get((form, target), {}))
        return out

    return fake


def _judge(
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[tuple[str, float], dict[str, float]],
) -> dict[str, Any]:
    """選定規則の 4 条件を、run を通さず judge_r に計画どおりの行を渡して計算する.

    速さのため。run の結線は test_run_output_shape で、二項の閾値そのものは
    test_size_threshold_is_exact_binomial で見る。
    """
    monkeypatch.setattr(
        sim, "size_count_threshold", functools.cache(sim.size_count_threshold)
    )
    fake = _fake_factory(overrides)
    rows = [
        {
            "kind": kind,
            "R": 24,
            "form": form,
            "target_C": target,
            "base": nu.base,
            "bot": nu.bot,
            "coupling": nu.coupling,
            "per_seed": [fake(form, target, 24, nu, n, s) for s in sim.SEEDS],
        }
        for kind, form, target, nu, n in sim.plan_r(24)
    ]
    return sim.judge_r(24, rows, {})


def test_judge_r_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    res = _judge(monkeypatch, {})
    assert (res["power_ok"], res["no_go_ok"], res["size_ok"], res["band_ok"]) == (
        True,
        True,
        True,
        True,
    )
    n_size = (2 * (len(sim.FORMS) - 1) * 18 + 2 * 6 + 18 + 8 * 18) * 2
    assert res["n_size_checks"] == n_size
    assert res["n_units"] == 288
    assert res["calls"] == 1152
    x = sim.size_count_threshold(n_size)
    over = {sc.VERDICT_PASS: (x + 1) / 10_000}
    assert _judge(monkeypatch, {("aon_unit", sc.TAU): over})["size_ok"] is False
    at_cap = {sc.VERDICT_PASS: x / 10_000}
    assert _judge(monkeypatch, {("aon_unit", sc.TAU): at_cap})["size_ok"] is True
    over_no_go = {sc.VERDICT_ABSENT: (x + 1) / 10_000}
    assert (
        _judge(monkeypatch, {("no_go_extremal_0.0", sc.TAU): over_no_go})["size_ok"]
        is False
    )
    low = {sc.VERDICT_PASS: 0.79}
    assert _judge(monkeypatch, {("logodds", sc.DELTA_PLANT): low})["power_ok"] is False
    low_no_go = {sc.VERDICT_ABSENT: 0.79}
    assert _judge(monkeypatch, {("homog_sd030", 0.0): low_no_go})["no_go_ok"] is False
    undecided = {sc.VERDICT_PASS: 0.79}
    assert _judge(monkeypatch, {("homog_sd005", 0.35): undecided})["band_ok"] is False
    edge = {sc.VERDICT_ABSENT: 0.8}
    assert _judge(monkeypatch, {("homog_sd030", 0.25): edge})["band_ok"] is True


def test_run_output_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sim, "pure_extremal_size", lambda *_: 0.0)
    monkeypatch.setattr(sim, "simulate", _fake_factory({}))
    out = sim.run([24, 48], workers=1)
    assert out["selection"] == {"selected_R": 48, "door_close": False}
    assert out["most_favorable_reaches"] is True
    assert set(out["boundaries"]) == {"R24", "R48"}
    assert out["R_run"] == [24, 48]
    assert out["params"]["R_candidates"] == [96, 192, 288]
    assert out["params"]["band_bases"] == ["uniform", "position_skew"]
    assert out["params"]["undecided_max"] == 0.2
    assert out["params"]["band_delta"] == 0.05
    assert set(out["target_sha256"]) == set(sc.certified_targets())


def test_item_values_stay_in_range() -> None:
    vals = sim._exact_item_values(0.3, 5, np.random.default_rng(1), 0.0, 1.0)
    assert np.all((vals >= 0.0) & (vals <= 1.0))


def test_chrono_only_is_calibrated_under_skewed_base() -> None:
    """片方の arm にだけ注入する形も、偏った base の下で目標の E[C] に較正する.

    Codex HIGH-3。

    セルの期待得点は g + L·m·(1 − g) で、凍結した並びの上の係数 F で注入量を決める。
    """
    for base in ("label_skew", "position_skew"):
        nu = sim.Nuisance(base, 0.0, "indep")
        dz = sim.design(R)
        f = sim.chrono_factor(dz, base)
        assert f != pytest.approx(0.5)  # 偏った base では 0.5 にならない
        out = sim.simulate("chrono_only", 0.3, R, nu, 2000, 3)
        assert out["realized_C"] == pytest.approx(0.3, abs=0.01)
        assert sim.reachable("chrono_only", nu, R) == pytest.approx(f)
    g = sim.base_gap(sim.design(R), "label_skew")
    assert np.allclose(g[:, 0], -g[:, 1])


def test_band_diag_points() -> None:
    pts = sim.band_diag_points()
    assert len(pts) == 2 * 2 * 2
    assert {nu.base for _, _, nu in pts} == {"label_skew"}
    assert {nu.coupling for _, _, nu in pts} == {"crn"}
    kinds = {k for k, *_ in sim.plan_r(24)}
    assert "band_diag" in kinds


def test_judge_r_calibration(monkeypatch: pytest.MonkeyPatch) -> None:
    res = _judge(monkeypatch, {})
    assert res["calibrated"] is True
    off = {"realized_C": sc.TAU + 0.02}
    assert _judge(monkeypatch, {("aon_unit", sc.TAU): off})["calibrated"] is False
    edge = {"realized_C": sc.TAU + 0.009}
    assert _judge(monkeypatch, {("aon_unit", sc.TAU): edge})["calibrated"] is True
