"""閉ループの模擬 (prereg v4 §6).

逐次参照との一致・閉形式・植え付け・λ 版・γ・選定基準。
"""

from __future__ import annotations

import numpy as np
import pytest
from scripts import closed_loop_battery as bat
from scripts import closed_loop_sim as sim
from scripts.stage_b_battery import dev_signatures

DEVS = dev_signatures()


def _reference_dev(
    cfg: sim.Config, kappa: float, n: int, r_count: int, seed: int
) -> tuple[np.ndarray, np.ndarray]:
    """vectorize 版と同じ乱数列・同じ結合規則で、逐次参照 (``dev_choice_reference``)
    を回す.

    返り値 = (終点の成功集合 (N, R, W, 12), 各ステップで選んだ行動の番号 (N, R, W, T)、
    ⊥ は −1)。
    """
    rng = np.random.default_rng(seed)
    states = {
        (i, r, w): bat.EMPTY_STATE
        for i in range(n)
        for r in range(r_count)
        for w in bat.WORLDS
    }
    steps = bat.n_steps(cfg.m)
    picks = np.full((n, r_count, len(bat.WORLDS), steps), -1)
    for t in range(steps):
        u = rng.random((n, r_count, len(bat.WORLDS), 4))
        new = {}
        for i in range(n):
            for r in range(r_count):
                for wi, w in enumerate(bat.WORLDS):
                    st = states[(i, r, w)]
                    # 結合は描画した状態ブロック (= prompt) の同一性で決める (状況部は
                    # 4 世界で共通)
                    src = wi
                    mine = bat.render_state(st, w, r, cfg.renderer)
                    for j in range(wi):
                        o = states[(i, r, bat.WORLDS[j])]
                        if bat.render_state(o, bat.WORLDS[j], r, cfg.renderer) == mine:
                            src = j
                            break
                    uu = sim.Uniforms(*u[i, r, src])
                    choice = sim.dev_choice_reference(cfg, kappa, st, w, r, t, uu)
                    real = choice if choice in bat.ACTIONS else None
                    if real is not None:
                        picks[i, r, wi, t] = bat.ACTIONS.index(real)
                    new[(i, r, w)] = bat.update(st, w, bat.loop_signature(r, t), real)
        states = new
    out = np.zeros((n, r_count, len(bat.WORLDS), 12), dtype=bool)
    for (i, r, w), st in states.items():
        for s in st.succeeded:
            out[i, r, bat.WORLDS.index(w), DEVS.index(s)] = True
    return out, picks


@pytest.mark.parametrize(
    ("renderer", "lam", "kappa", "bot"),
    [
        (bat.RENDERER_R1, "flat", 0.7, 0.1),
        (bat.RENDERER_R1, "graded", 0.9, 0.0),
        (bat.RENDERER_R1PLUS, "graded", 0.6, 0.1),
        (bat.RENDERER_R1PLUS, "flat", 0.0, 0.0),
    ],
)
def test_vectorized_dev_matches_reference(
    renderer: str, lam: str, kappa: float, bot: float
) -> None:
    cfg = sim.Config(base="measured", bot=bot, sd=0.3, lam=lam, renderer=renderer, m=3)
    got = sim.simulate_dev(cfg, kappa, 3, 2, np.random.default_rng(11), record=True)
    want_succ, want_picks = _reference_dev(cfg, kappa, 3, 2, 11)
    assert np.array_equal(got.succ, want_succ)
    assert np.array_equal(got.picks, want_picks)  # 行動列そのものが一致する


def test_state_keys_follow_prompt_identity() -> None:
    """key の一致 ⇔ 描画した状態ブロックの一致 (成功行の label は世界ごとに違う)."""
    devs = bat.dev_signatures()
    cases = [
        (bat.EMPTY_STATE, bat.EMPTY_STATE),
        (
            bat.State(succeeded=frozenset({devs[0]})),
            bat.State(succeeded=frozenset({devs[0]})),
        ),
        (bat.State(tried=frozenset({(devs[1], "read_book")})), bat.EMPTY_STATE),
        (
            bat.State(tried=frozenset({(devs[1], "tend_moss")})),
            bat.State(tried=frozenset({(devs[1], "tend_moss")})),
        ),
    ]
    for renderer in bat.RENDERERS:
        for s0, s1 in cases:
            succ = np.zeros((1, 1, 2, 12), dtype=bool)
            tried = np.zeros((1, 1, 2, 12, 6), dtype=bool)
            for wi, st in enumerate((s0, s1)):
                for sg in st.succeeded:
                    succ[0, 0, wi, devs.index(sg)] = True
                for sg, act in st.tried:
                    tried[0, 0, wi, devs.index(sg), bat.ACTIONS.index(act)] = True
            keys = sim._state_keys(
                succ, tried if renderer == bat.RENDERER_R1PLUS else None
            )
            same_key = bool(np.all(keys[0, 0, 0] == keys[0, 0, 1]))
            same_prompt = bat.render_state(s0, "A", 0, renderer) == bat.render_state(
                s1, "A_rot", 0, renderer
            )
            assert same_key == same_prompt, (renderer, s0, s1)


def test_out_of_omega_is_tried_but_never_success() -> None:
    """Ω 外 (確率 1) では成功は増えず、試行は Ω_dev 外の語彙 label になる.

    (battery と同じ扱い)
    """
    cfg = sim.Config(
        base="uniform",
        bot=0.0,
        sd=0.05,
        lam="flat",
        renderer=bat.RENDERER_R1PLUS,
        m=3,
        oov=1.0,
    )
    dev = sim.simulate_dev(cfg, 0.0, 5, 2, np.random.default_rng(3), record=True)
    assert not dev.succ.any()
    assert dev.picks is not None
    assert (dev.picks >= 0).all()  # 全ステップで行動した (⊥ でない)
    for r in range(2):
        for t in range(bat.n_steps(3)):
            opts = bat.dev_options(r, t)
            acts = {bat.ACTIONS[a] for a in dev.picks[:, r, :, t].ravel()}
            assert acts.isdisjoint(opts)


def test_identical_states_share_uniforms() -> None:
    keys = np.zeros((1, 1, 4, 1), dtype=np.int64)
    keys[0, 0, 2, 0] = 7
    u = np.arange(4, dtype=float).reshape(1, 1, 4, 1)
    got = sim._coupled(u, keys)[0, 0, :, 0]
    assert got.tolist() == [0.0, 0.0, 2.0, 0.0]


def test_clipped_parts_match_monte_carlo() -> None:
    rng = np.random.default_rng(3)
    z = rng.standard_normal(400_000)
    for mean, sd in ((0.0, 0.5), (0.4, 0.3), (0.9, 0.5), (-0.2, 0.05), (0.6, 0.0)):
        e = np.clip(mean + sd * z, -1.0, 1.0)
        ep, em = sim.clipped_parts(mean, sd)
        assert ep == pytest.approx(np.maximum(e, 0).mean(), abs=3e-3)
        assert em == pytest.approx(np.maximum(-e, 0).mean(), abs=3e-3)


def test_expected_c_at_kappa_zero_is_zero() -> None:
    for base in sim.BASES:
        cfg = sim.Config(
            base=base, bot=0.1, sd=0.5, lam="graded", renderer=bat.RENDERER_R1PLUS, m=3
        )
        dev = sim.simulate_dev(cfg, 0.0, 200, 8, np.random.default_rng(1))
        assert np.abs(sim.expected_units(cfg, 0.0, dev)).max() < 1e-12


def test_expected_c_matches_sampled_mean() -> None:
    cfg = sim.Config(
        base="measured",
        bot=0.1,
        sd=0.3,
        lam="graded",
        renderer=bat.RENDERER_R1PLUS,
        m=4,
    )
    dev = sim.simulate_dev(cfg, 0.8, 4000, 8, np.random.default_rng(sim.SIM_SEED))
    ec = sim.expected_units(cfg, 0.8, dev).mean()
    got = sim.simulate_verdicts(cfg, 0.8, 8, 5, 4000)["mean_C"]
    assert got == pytest.approx(ec, abs=0.01)
    # κ = 0・sd = 0.5: 対称な攪乱 (e < 0 は foil) なので E[C] = 0、抽選の平均も 0 付近
    null = sim.Config(
        base="measured", bot=0.1, sd=0.5, lam="flat", renderer=bat.RENDERER_R1PLUS, m=3
    )
    assert abs(sim.simulate_verdicts(null, 0.0, 8, 5, 2000)["mean_C"]) < 0.01


def test_lambda_versions_and_graded_is_lower() -> None:
    assert sim.lam_table("graded") == {0: 0.0, 1: 0.5, 2: 0.75, 3: 0.75, 4: 1.0}
    assert sim.lam_table("flat") == {0: 0.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0}
    out = {}
    for lam in sim.LAMBDA_VERSIONS:
        cfg = sim.Config(
            base="uniform", bot=0.0, sd=0.05, lam=lam, renderer=bat.RENDERER_R1, m=3
        )
        dev = sim.simulate_dev(cfg, 1.0, 400, 8, np.random.default_rng(2))
        out[lam] = sim.expected_units(cfg, 1.0, dev).mean()
    assert out["graded"] < out["flat"]


def test_r1plus_avoidance_raises_coverage_and_gamma_factor() -> None:
    covs = {}
    for ren, gf in (
        (bat.RENDERER_R1, 1.0),
        (bat.RENDERER_R1PLUS, 0.0),
        (bat.RENDERER_R1PLUS, 1.0),
    ):
        cfg = sim.Config(
            base="measured",
            bot=0.0,
            sd=0.05,
            lam="flat",
            renderer=ren,
            m=3,
            gamma_factor=gf,
        )
        dev = sim.simulate_dev(cfg, 1.0, 400, 8, np.random.default_rng(4))
        covs[(ren, gf)] = sim.weather_coverage(dev.succ).mean()
    assert covs[(bat.RENDERER_R1PLUS, 1.0)] > covs[(bat.RENDERER_R1, 1.0)] + 0.1
    assert covs[(bat.RENDERER_R1PLUS, 0.0)] == pytest.approx(
        covs[(bat.RENDERER_R1, 1.0)], abs=0.05
    )


def test_measured_base_fixates_under_r1() -> None:
    """実測 base・R1 では、完全な reader (κ = 1) でも E[C] が 2τ に届かない

    (探索の事実を
    pin).
    """
    cfg = sim.Config(
        base="measured", bot=0.1, sd=0.05, lam="flat", renderer=bat.RENDERER_R1, m=4
    )
    dev = sim.simulate_dev(cfg, 1.0, 1000, 8, np.random.default_rng(5))
    assert sim.expected_units(cfg, 1.0, dev).mean() < sim.DELTA_PLANT


def test_curve_solve_interpolates_and_detects_unreachable() -> None:
    cfg = sim.Config(
        base="uniform", bot=0.0, sd=0.0, lam="flat", renderer=bat.RENDERER_R1, m=3
    )
    per_r = np.tile(np.linspace(0.0, 0.5, len(sim.KAPPA_GRID))[:, None], (1, bat.R_MAX))
    curve = sim.KappaCurve(cfg=cfg, per_r=per_r, coverage=np.zeros(len(sim.KAPPA_GRID)))
    assert curve.solve(0.0, 8) == 0.0
    assert curve.solve(0.25, 8) == pytest.approx(0.5)
    assert curve.solve(0.6, 8) is None


def test_null_is_no_go_and_plant_is_pass() -> None:
    cfg = sim.Config(
        base="uniform", bot=0.0, sd=0.05, lam="flat", renderer=bat.RENDERER_R1PLUS, m=3
    )
    assert sim.simulate_verdicts(cfg, 0.0, 8, 5, 500)["NO_GO_EFFECT_ABSENT"] > 0.95
    assert sim.simulate_verdicts(cfg, 1.0, 8, 5, 500)["PASS"] > 0.95


def test_pipeline_gates_each_stage() -> None:
    ok_w = np.zeros((1, 4))
    assert sim.pipeline_gates(np.array([0.0]), ok_w, ok_w).tolist() == [True]
    assert sim.pipeline_gates(np.array([0.21]), ok_w, ok_w).tolist() == [False]
    loop = ok_w.copy()
    loop[0, 2] = 0.21
    assert sim.pipeline_gates(np.array([0.0]), loop, ok_w).tolist() == [False]
    probe = ok_w.copy()
    probe[0, 0] = 0.08  # 族内差 ≥ τ/4
    assert sim.pipeline_gates(np.array([0.0]), ok_w, probe).tolist() == [False]


def test_constants_are_pinned() -> None:
    assert sim.OOV == 0.05
    assert sim.SKEW == 0.7
    assert sim.KAPPA_GRID[0] == 0.0
    assert sim.KAPPA_GRID[-1] == 1.0
    assert len(sim.KAPPA_GRID) == 26
    assert pytest.approx(0.6) == sim.DELTA_PLANT


def test_bottom_gates_act_in_simulation() -> None:
    cfg = sim.Config(
        base="uniform", bot=0.3, sd=0.05, lam="flat", renderer=bat.RENDERER_R1PLUS, m=3
    )
    assert sim.simulate_verdicts(cfg, 1.0, 8, 5, 200)["INVALID_TASK_BATTERY"] == 1.0


def test_size_cap_rule() -> None:
    assert sim.size_cap(0.05, 10_000) == pytest.approx(
        0.05 + 3 * np.sqrt(0.05 * 0.95 / 10_000)
    )
    assert sim.size_cap(0.3, 2_000) == pytest.approx(
        0.05 + 3 * np.sqrt(0.05 * 0.95 / 2_000)
    )
    assert sim.size_cap(0.5, 10_000) == pytest.approx(0.075)


def test_criteria_requires_reachability_planting_and_all_four() -> None:
    good = sim.Criteria(0.3, 0.6, 0.31, 0.59, 0.9, 0.9, 0.04, 0.04, 0.0565)
    assert good.ok
    assert not sim.Criteria(0.3, None, None, None, 0.9, 0.9, 0.04, 0.04, 0.0565).ok
    assert not sim.Criteria(0.3, 0.6, 0.33, 0.59, 0.9, 0.9, 0.04, 0.04, 0.0565).ok
    assert not sim.Criteria(0.3, 0.6, 0.31, 0.57, 0.9, 0.9, 0.04, 0.04, 0.0565).ok
    assert not sim.Criteria(0.3, 0.6, 0.31, 0.59, 0.79, 0.9, 0.04, 0.04, 0.0565).ok
    assert not sim.Criteria(0.3, 0.6, 0.31, 0.59, 0.9, 0.79, 0.04, 0.04, 0.0565).ok
    assert not sim.Criteria(0.3, 0.6, 0.31, 0.59, 0.9, 0.9, 0.06, 0.04, 0.0565).ok
    assert not sim.Criteria(0.3, 0.6, 0.31, 0.59, 0.9, 0.9, 0.04, 0.06, 0.0565).ok
    # κ が解けていない (None) なら、realized の値があっても合格にしない
    assert not sim.Criteria(None, 0.6, 0.31, 0.59, 0.9, 0.9, 0.04, 0.04, 0.0565).ok
    assert sim.PLANT_TOL == 0.02


def test_unreachable_plant_fails_design() -> None:
    cfg = sim.Config(
        base="uniform", bot=0.0, sd=0.0, lam="flat", renderer=bat.RENDERER_R1, m=3
    )
    per_r = np.tile(np.linspace(0.0, 0.5, len(sim.KAPPA_GRID))[:, None], (1, bat.R_MAX))
    curve = sim.KappaCurve(cfg=cfg, per_r=per_r, coverage=np.zeros(len(sim.KAPPA_GRID)))
    crit = sim.design_criteria(cfg, curve, 8, 5, 10)
    assert not crit.reachable
    assert not crit.ok
