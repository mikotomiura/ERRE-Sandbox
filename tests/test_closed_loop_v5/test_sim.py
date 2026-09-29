"""凍結 v5 模擬 (pilot prereg §5).

逐次参照との完全一致 (描画した prompt の一致で結合・同一 prompt の記憶)、
κ に依らない dev 段、閉形式と抽選の一致、k_rep、植え付け、seed の決定性。
"""

from __future__ import annotations

import numpy as np
import pytest
from scripts import closed_loop_battery as v4
from scripts import closed_loop_sim as v4sim
from scripts import closed_loop_v5_battery as bat
from scripts import closed_loop_v5_select as sel
from scripts import closed_loop_v5_sim as sim
from scripts.stage_b_battery import ACTIONS

DEVS = sim.DEVS


def _beh(axis: str, **kw: object) -> sim.Behaviour:
    base = {
        "axis": axis,
        "lam_dev": 0.4,
        "base": sim.base_table(sel.V4_LOOP_BASE),
        "bot": 0.1,
        "oov": 0.05,
        "s_changed": 0.5,
        "s_same": 0.9,
        "eps": 0.5,
        "rho": 0.9,
    }
    base.update(kw)
    return sim.Behaviour(**base)  # type: ignore[arg-type]


def _reference(
    beh: sim.Behaviour, m: int, r_values: tuple[int, ...], n: int, seed: int
) -> tuple[np.ndarray, np.ndarray]:
    """vectorize 版と同じ乱数列で逐次参照を回す。結合と「同一 prompt」は描画した
    messages の完全一致で判定する.
    """
    rng = np.random.default_rng(seed)
    worlds = v4.WORLDS
    rr = len(r_values)
    steps = bat.N_DEV * m
    states = {
        (i, r, w): v4.EMPTY_STATE for i in range(n) for r in r_values for w in worlds
    }
    last: dict[tuple[int, int, str, object], str] = {}
    hist: dict[tuple[int, int, str, object], list[tuple[object, str]]] = {}
    picks = np.full((n, rr, len(worlds), steps), -1)
    for t in range(steps):
        u = rng.random((n, rr, len(worlds), sim.N_U))
        new = {}
        for i in range(n):
            for ri, r in enumerate(r_values):
                sig = v4.loop_signature(r, t)
                msgs_of = {
                    w: bat.loop_messages(states[(i, r, w)], w, r, t, beh.axis)
                    for w in worlds
                }
                for wi, w in enumerate(worlds):
                    st = states[(i, r, w)]
                    src = next(
                        j for j in range(wi + 1) if msgs_of[worlds[j]] == msgs_of[w]
                    )
                    key = (i, r, w, sig)
                    same = [c for mm, c in hist.get(key, []) if mm == msgs_of[w]]
                    choice = sim.dev_choice_reference(
                        beh,
                        st,
                        w,
                        r,
                        t,
                        last.get(key),
                        same[-1] if same else None,
                        u[i, ri, src],
                    )
                    if choice is not None:
                        picks[i, ri, wi, t] = ACTIONS.index(choice)
                        last[key] = choice
                        hist.setdefault(key, []).append((msgs_of[w], choice))
                    new[(i, r, w)] = v4.update(st, w, sig, choice)
        states = new
    succ = np.zeros((n, rr, len(worlds), bat.N_DEV), dtype=bool)
    for (i, r, w), st in states.items():
        for s in st.succeeded:
            succ[i, r_values.index(r), worlds.index(w), DEVS.index(s)] = True
    return succ, picks


@pytest.mark.parametrize(
    ("axis", "kw"),
    [
        ("B", {}),
        ("B", {"s_changed": 0.0, "s_same": 1.0, "base": None}),
        ("C", {}),
        ("C", {"untried": sim.UNTRIED_BASE, "rho": 1.0, "eps": 0.3}),
    ],
)
def test_vectorized_matches_reference(axis: str, kw: dict[str, object]) -> None:
    beh = _beh(axis, **kw)
    r_values = (0, 5)
    m = 6  # B は 5 周目に回転の位相が戻る
    succ, picks = _reference(beh, m, r_values, 3, 11)
    dev = sim.simulate_dev(beh, m, r_values, 3, np.random.default_rng(11), record=True)
    assert dev.picks is not None
    np.testing.assert_array_equal(dev.picks, picks)
    np.testing.assert_array_equal(dev.succ, succ)


def test_same_prompt_memory_is_used_in_b() -> None:
    """B で s_changed = 0・s_same = 1 なら、5 周目以降は 1
    周目の同じ位相の選択を繰り返す (成功が無い限り).
    """
    beh = _beh("B", s_changed=0.0, s_same=1.0, bot=0.0, oov=0.0, lam_dev=0.0)
    dev = sim.simulate_dev(beh, 8, (0,), 50, np.random.default_rng(3), record=True)
    assert dev.picks is not None
    first, fifth = dev.picks[..., :12], dev.picks[..., 48:60]
    unsucc = ~dev.succ[:, :, :, :].any(-1)
    same = (first == fifth).all(-1)
    assert same[unsucc].all()


def test_dev_does_not_depend_on_probe_parameters() -> None:
    """κ・probe の攪乱は dev 段に入らない (dev 段は Behaviour と乱数だけの関数)."""
    beh = _beh("C")
    a = sim.simulate_dev(beh, 4, (0, 1), 20, np.random.default_rng(1))
    b = sim.simulate_dev(beh, 4, (0, 1), 20, np.random.default_rng(1))
    np.testing.assert_array_equal(a.succ, b.succ)
    pp = sim.ProbePoint("measured", 0.3, "flat", 0.0)
    curve = sim.kappa_curve(pp, 0.1, a)
    assert curve.expected_c(2)[0] == pytest.approx(0.0, abs=0.02)


def test_closed_form_matches_draws() -> None:
    beh = _beh("B", s_changed=0.0)
    dev = sim.simulate_dev(beh, 4, tuple(range(8)), 400, np.random.default_rng(2))
    for k_rep in (0.0, 0.944):
        pp = sim.ProbePoint("measured", 0.3, "graded", k_rep)
        curve = sim.kappa_curve(pp, 0.1, dev)
        kappa = 0.8
        exp_c = float(np.interp(kappa, v4sim.KAPPA_GRID, curve.expected_c(8)))
        out = sim.simulate_verdicts(pp, 0.1, kappa, 5, dev, np.random.default_rng(4))
        assert out["mean_C"] == pytest.approx(exp_c, abs=0.02)


def test_k_rep_repeats_first_draw() -> None:
    p = np.array([[0.25, 0.25, 0.25, 0.25]] * 2000)
    rng = np.random.default_rng(0)
    full = sim._repeat_draws(p, 10, 1.0, rng)
    assert (full.max(-1) == 10).all()
    indep = sim._repeat_draws(p, 10, 0.0, rng)
    assert (indep.max(-1) < 10).mean() > 0.99
    assert full.sum(-1).tolist() == [10] * 2000


def test_point_seed_is_canonical() -> None:
    a = sim.point_seed("B", {"x": 1, "y": 2.0}, 8)
    b = sim.point_seed("B", {"y": 2.0, "x": 1}, 8)
    assert a == b
    assert a != sim.point_seed("C", {"x": 1, "y": 2.0}, 8)
    assert 0 <= a < 2**64


def test_explore_eps_raises_untried_rate() -> None:
    """C で ε = 1 なら、未試行が残る限り試行済みを選ばない."""
    beh = _beh("C", eps=1.0, rho=1.0, bot=0.0, oov=0.0)
    dev = sim.simulate_dev(beh, 4, (0,), 30, np.random.default_rng(5))
    assert v4sim.weather_coverage(dev.succ).mean() == pytest.approx(1.0)


def test_untried_modes_differ() -> None:
    a = sim.simulate_dev(
        _beh("C", untried=sim.UNTRIED_UNIFORM), 4, (0, 1), 200, np.random.default_rng(6)
    )
    b = sim.simulate_dev(
        _beh("C", untried=sim.UNTRIED_BASE), 4, (0, 1), 200, np.random.default_rng(6)
    )
    assert not np.array_equal(a.succ, b.succ)


@pytest.mark.parametrize("base", ["measured", "uniform", "label_skew", "position_skew"])
def test_expected_units_equals_v4(base: str) -> None:
    dev = sim.simulate_dev(_beh("B"), 4, tuple(range(12)), 50, np.random.default_rng(9))
    for sd, lam, kappa in (
        (0.05, "flat", 0.3),
        (0.5, "graded", 0.96),
        (0.3, "flat", 0.0),
    ):
        cfg = v4sim.Config(
            base=base, bot=0.1, sd=sd, lam=lam, renderer=v4.RENDERER_R1PLUS, m=4
        )
        np.testing.assert_allclose(
            sim.expected_units(cfg, kappa, dev),
            v4sim.expected_units(cfg, kappa, dev),
            rtol=0,
            atol=1e-12,
        )


def _exploring_dev(bot: float = 0.0) -> v4sim.DevResult:
    beh = _beh("C", eps=1.0, rho=1.0, bot=bot, oov=0.0, lam_dev=0.0)
    return sim.simulate_dev(beh, 4, tuple(range(8)), 300, np.random.default_rng(12))


def test_verdict_directions_and_planting() -> None:
    """全 weather を発見する dev 段で、C = 2τ なら PASS、κ = 0 なら NO_GO が大半."""
    dev = _exploring_dev()
    pp = sim.ProbePoint("uniform", 0.05, "flat", 0.0)
    curve = sim.kappa_curve(pp, 0.0, dev)
    crit = sim.design_criteria(pp, 0.0, curve, dev, 5, ("t",))
    assert crit.reachable
    assert crit.realized_plant == pytest.approx(0.6, abs=0.03)
    assert crit.realized_tau == pytest.approx(0.3, abs=0.03)
    assert crit.pass_at_plant > 0.9
    assert crit.no_go_at_zero > 0.9


def test_bottom_gate_in_verdicts() -> None:
    """⊥ 率 0.3 は ⊥ gate (0.2) を越え、ほぼ全て INVALID_TASK_BATTERY."""
    dev = _exploring_dev(bot=0.3)
    pp = sim.ProbePoint("uniform", 0.05, "flat", 0.0)
    out = sim.simulate_verdicts(pp, 0.3, 0.5, 5, dev, np.random.default_rng(1))
    assert out["INVALID_TASK_BATTERY"] > 0.95
    assert dev.loop_bot.sum() > 0
