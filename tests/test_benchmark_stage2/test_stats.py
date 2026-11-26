"""判別性 gate 段 2 の stats (prereg §B〜§G)。

既知解 (有界の厳密な例)・単調性・帰無での被覆・判定表の各枝・split-half・資格・
R の範囲 (旧記録と交わらない) を pin する。
"""

from __future__ import annotations

import math
from fractions import Fraction

import numpy as np
import pytest
from scripts import benchmark_stage2_stats as st
from scripts import generalization_probe_battery as gbat
from scripts import o_time_probe_battery as obat
from scripts import skill_lever_battery as v2bat

# ------------------------------------------------------------ e-value の既知解


def test_lambda_grid_is_frozen_geometric() -> None:
    assert st.N_LAMBDA == 12
    assert st.LAMBDA_C[0] == pytest.approx(0.98)
    assert np.allclose(st.LAMBDA_C[1:] / st.LAMBDA_C[:-1], 0.7)
    assert np.all(st.LAMBDA_C < 1.0)


def test_log_e_exact_single_unit() -> None:
    # x = 0、m = 0.5、lo = −2: 因子 = 1 + c_j (0 − 0.5) / 2.5 = 1 − c_j / 5
    v, c = st.support(np.array([0.0]))
    want = math.log(np.mean(1.0 - st.LAMBDA_C / 5.0))
    assert float(st.log_e_lower(v, c, 0.5, -2.0)) == pytest.approx(want, abs=1e-14)


def test_log_e_exact_two_units() -> None:
    x = np.array([1.0, -1.0, 1.0])
    m, lo = 0.2, -2.0
    lam = st.LAMBDA_C / (m - lo)
    want = math.log(np.mean((1 + lam * 0.8) ** 2 * (1 - lam * 1.2)))
    v, c = st.support(x)
    assert float(st.log_e_lower(v, c, m, lo)) == pytest.approx(want, abs=1e-13)


def test_upper_mirrors_lower() -> None:
    rng = np.random.default_rng(0)
    x = rng.uniform(-1, 1, 50)
    v, c = st.support(x)
    vn, cn = st.support(-x)
    assert float(st.log_e_upper(v, c, 0.3, 1.0)) == pytest.approx(
        float(st.log_e_lower(vn, cn, -0.3, -1.0)), abs=1e-12
    )


def test_log_e_rejects_bad_support() -> None:
    v, c = st.support(np.array([-3.0, 0.0]))
    with pytest.raises(ValueError, match="lower bound"):
        st.log_e_lower(v, c, 0.0, -2.0)
    with pytest.raises(ValueError, match="exceed"):
        st.log_e_lower(v, c, -2.0, -2.0)


def test_batch_counts_match_single() -> None:
    rng = np.random.default_rng(1)
    vals = np.arange(-4, 5) / 2.0
    counts = rng.integers(0, 30, size=(5, vals.size)).astype(float)
    batch = st.log_e_lower(vals, counts, 0.1, -2.0)
    for i in range(5):
        assert float(batch[i]) == pytest.approx(
            float(st.log_e_lower(vals, counts[i], 0.1, -2.0))
        )


# ------------------------------------------------------------ 単調性と区間


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_e_value_nonincreasing_in_m(seed: int) -> None:
    rng = np.random.default_rng(seed)
    x = np.clip(rng.normal(0.2, 0.7, 200), -2, 2)
    v, c = st.support(x)
    ms = np.linspace(-1.99, 1.99, 400)
    e = np.array([float(st.log_e_lower(v, c, m, -2.0)) for m in ms])
    assert np.all(np.diff(e) <= 1e-12)


def test_lower_bound_is_the_test_inversion() -> None:
    rng = np.random.default_rng(3)
    x = np.clip(rng.normal(0.3, 0.4, 400), -2, 2)
    level = 0.05 / 30
    lb = st.lower_bound(x, -2.0, 2.0, level)
    assert st.rejects_lower(x, lb - 1e-6, -2.0, level)
    assert not st.rejects_lower(x, lb + 1e-6, -2.0, level)
    assert lb < x.mean()


def test_lower_bound_returns_lo_when_nothing_rejects() -> None:
    assert st.lower_bound(np.array([-2.0, -2.0]), -2.0, 2.0, 0.05) == -2.0


def test_upper_bound_mirrors() -> None:
    rng = np.random.default_rng(4)
    x = rng.uniform(-1, 1, 300)
    assert st.upper_bound(x, -1.0, 1.0, 0.01) == pytest.approx(
        -st.lower_bound(-x, -1.0, 1.0, 0.01), abs=1e-9
    )


# ------------------------------------------------------------ 帰無での被覆 (定理の確認)


@pytest.mark.parametrize(
    ("name", "draw"),
    [
        # 有界の非対称な二点 {−2, 0.5} (平均 0)
        ("two_point", lambda rng, n: np.where(rng.random(n) < 0.2, -2.0, 0.5)),
        # 異質な平均 (半分 +0.5、半分 −0.5 の単位平均。平均 0)
        (
            "heterogeneous",
            lambda rng, n: np.clip(
                np.where(np.arange(n) % 2 == 0, 0.5, -0.5) + rng.uniform(-1.4, 1.4, n),
                -2,
                2,
            ),
        ),
    ],
)
def test_null_coverage(name: str, draw) -> None:
    # 帰無の境界 (真の平均 0) で、水準 0.1 の片側検定の棄却率 ≤ 0.1 (MC の 3 SE の余裕)
    rng = np.random.default_rng(20261126)
    n_sims, n, level = 3000, 60, 0.1
    rej = sum(st.rejects_lower(draw(rng, n), 0.0, -2.0, level) for _ in range(n_sims))
    assert rej / n_sims <= level + 3 * math.sqrt(level * (1 - level) / n_sims), name


def test_power_reaches_on_clear_difference() -> None:
    x = np.full(400, 0.5)
    assert st.rejects_lower(x, st.DELTA_MIN, -2.0, st.ALPHA / 120)


# ------------------------------------------------------------ 判定表の各枝


def _units(cs: list[float], n: int = 400) -> np.ndarray:
    return np.array([np.full(n, c) for c in cs])


def _halves(n: int = 400) -> np.ndarray:
    return np.arange(n) % 2


def test_branch_invalid_and_not_computed() -> None:
    u = _units([0.3, 0.3, 0.3])
    assert (
        st.decide_battery(u, 6, 3, _halves(), invalid=True, n_entered=3).verdict
        == st.VERDICT_INVALID
    )
    assert (
        st.decide_battery(u, 6, 3, _halves(), not_computed=True, n_entered=3).verdict
        == st.VERDICT_NOT_COMPUTED
    )


def test_branch_not_qualified() -> None:
    assert (
        st.decide_battery(_units([0.3, 0.5]), 2, 2, _halves(), n_entered=2).verdict
        == st.VERDICT_NOT_QUALIFIED
    )


def test_branch_established_names_the_pair() -> None:
    d = st.decide_battery(_units([0.3, 0.3, 0.8]), 6, 3, _halves(), n_entered=3)
    assert d.verdict == st.VERDICT_ESTABLISHED
    assert set(d.established) == {(2, 0), (2, 1)}


def test_branch_negative() -> None:
    d = st.decide_battery(_units([0.3, 0.3, 0.3]), 6, 3, _halves(), n_entered=3)
    assert d.verdict == st.VERDICT_NEGATIVE
    assert d.established == ()


def test_branch_inconclusive_small_n() -> None:
    d = st.decide_battery(_units([0.3, 0.3, 0.8], n=5), 6, 3, _halves(5), n_entered=3)
    assert d.verdict == st.VERDICT_INCONCLUSIVE


def test_split_half_blocks_establishment() -> None:
    # 差が片方の半分にだけある: 下限は Δ_min を超えても、split-half で再現しない
    n = 2000
    hi = np.where(np.arange(n) % 2 == 0, 1.0, 0.3)
    u = np.array([np.full(n, 0.3), np.full(n, 0.3), hi])
    d = st.decide_battery(u, 6, 3, np.arange(n) % 2, n_entered=3)
    assert d.verdict != st.VERDICT_ESTABLISHED


def test_floor_concentration_blocks_establishment() -> None:
    # 全モデルが床の帯の内: 対差 0.15 の下限が Δ_min を超えても (1) にしない
    n = 20000
    u = _units([-0.07, -0.07, 0.08], n=n)
    d = st.decide_battery(u, 6, 3, _halves(n), n_entered=3)
    assert d.concentration == "floor"
    assert d.verdict != st.VERDICT_ESTABLISHED


def test_ceiling_concentration() -> None:
    n = 20000
    d = st.decide_battery(
        _units([0.95, 0.95, 0.97], n=n), 6, 3, _halves(n), n_entered=3
    )
    assert d.concentration == "ceiling"
    assert d.verdict == st.VERDICT_NEGATIVE


def test_classify_vectorized_branches() -> None:
    est = np.array([[True, False], [False, False], [False, False], [True, False]])
    rep = np.array([[True, True], [True, True], [True, True], [True, True]])
    eq = np.array([[False, False], [True, True], [True, False], [True, True]])
    conc = np.array([False, False, False, True])
    out = st.classify(est, rep, eq, conc)
    assert list(out) == [
        st.VERDICT_ESTABLISHED,
        st.VERDICT_NEGATIVE,
        st.VERDICT_INCONCLUSIVE,
        st.VERDICT_NEGATIVE,
    ]


def test_sensitivity_condition() -> None:
    n = 400
    # target − foil の差は 0.75。上位 (2) の対の外のセルが残ると、
    # 不利な割当で差が残らない
    tf = np.zeros((3, n, 3))
    tf[:, :, 2] = 4
    tf[0, :, 0], tf[1, :, 0] = 1, 1
    tf[0, :, 1], tf[1, :, 1] = 1, 1
    tf[2, :, 0] = 3  # C = 0.75、残り 1 セル
    units = (tf[:, :, 0] - tf[:, :, 1]) / tf[:, :, 2]
    d = st.decide_battery(units, 6, 3, _halves(n), cell_counts=tf, n_entered=3)
    assert d.verdict == st.VERDICT_ESTABLISHED
    # 上位の残り 1 を −1 → 0.5、下位の残り 2 を +1 → 0.5: 差 0 で残らない
    assert d.sensitivity_ok == ()
    tf2 = tf.copy()
    tf2[0, :, 1], tf2[1, :, 1] = 3, 3  # 下位は残り 0 (C = −0.5)
    units2 = (tf2[:, :, 0] - tf2[:, :, 1]) / tf2[:, :, 2]
    d2 = st.decide_battery(units2, 6, 3, _halves(n), cell_counts=tf2, n_entered=3)
    assert (2, 0) in d2.sensitivity_ok


def test_n_tests_counts_qualified_batteries_only() -> None:
    assert st.n_tests({"v2": 6, "v3": 2, "G": 5, "O_time": 3}) == 30 + 20 + 6


# ------------------------------------------------------------ 資格 (§A)


def _mp(**kw) -> st.ModelPilot:
    base = {
        "lookup_ok": True,
        "bot_counts": (0, 0, 0, 0),
        "bot_n": 720,
        "know_ok": True,
        "control_counts": (0, 0, 0, 0),
        "envelope_ok": True,
    }
    base.update(kw)
    return st.ModelPilot(**base)


def test_qualify_order() -> None:
    bad = (720, 0, 0, 0)
    assert st.qualify("v2", _mp(lookup_ok=False, bot_counts=bad)) == st.REASON_LOOKUP
    assert st.qualify("v2", _mp(bot_counts=(145, 145, 0, 0, 0))) == st.REASON_PARSE
    assert st.qualify("v2", _mp(bot_counts=(54, 0, 0, 0, 0))) == st.REASON_PARSE
    assert st.qualify("G", _mp(know_ok=False, envelope_ok=False)) == st.REASON_KNOW
    assert st.qualify("v3", _mp(control_counts=(0, 0, 0, 145))) == st.REASON_CONTROL
    assert st.qualify("v3", _mp(control_counts=None)) == st.REASON_CONTROL
    assert st.qualify("O_time", _mp(envelope_ok=False)) == st.REASON_ENVELOPE
    assert (
        st.qualify("v2", _mp(bot_counts=(0,) * 5, know_ok=False, envelope_ok=False))
        == st.ENTERED
    )
    assert st.qualify("G", _mp()) == st.ENTERED


def test_parse_rule_exact_boundary() -> None:
    """Codex r4 HIGH-1: 族内差 54/720 = 3/40 ちょうどは厳密な < で落ちる.

    率の浮動小数点の差で比べると通っていた。
    """
    counts = (92, 38, 38, 38, 0)
    assert 92 / 720 - 38 / 720 < 0.075  # 率の差で比べると誤って通る
    ok, _ = st.parse_rule(counts, 720)
    assert not ok
    assert st.qualify("v2", _mp(bot_counts=counts)) == st.REASON_PARSE
    ok2, env = st.parse_rule((91, 38, 38, 38, 0), 720)
    assert ok2
    assert env == st.Fraction(91, 720) + st.Fraction(1, 20)
    assert st.parse_rule((144, 144, 144, 144), 720) == (True, st.Fraction(1, 5))
    assert not st.parse_rule((145, 145, 145, 145), 720)[0]


def test_parse_rule_constants_bound_to_frozen_tau() -> None:
    assert st.Fraction(st.TAU).limit_denominator(1000) / 4 == st.BOT_FAMILY_GAP_FR
    assert st.Fraction(1, 5) == st.BOT_MAX_FR


def test_qualify_checks_arm_count() -> None:
    with pytest.raises(ValueError, match="arm の数"):
        st.qualify("v2", _mp(bot_counts=(0, 0, 0, 0)))  # C0 が落ちている
    with pytest.raises(ValueError, match="arm の数"):
        st.qualify("G", _mp(bot_counts=(0, 0, 0, 0, 0)))


def test_envelope_exceeded_exact_boundary() -> None:
    """Reviewer MEDIUM-1: v2・R 16・pilot 90/720 → 168/960 ちょうどは残す."""
    _, env = st.parse_rule((90, 90, 0, 0, 0), 720)
    assert env == st.Fraction(7, 40)
    assert not st.envelope_exceeded((168, 0, 0, 0, 0), 960, env)
    assert st.envelope_exceeded((169, 0, 0, 0, 0), 960, env)


def test_sim_uses_stats_parse_rule() -> None:
    import numpy as np
    from scripts import benchmark_stage2_sim as sim

    k = np.array([92, 38, 38, 38, 0])
    assert sim.qualify_arms(k, 720) == st.parse_rule([92, 38, 38, 38, 0], 720)


# ------------------------------------------------ r の範囲・seed の分離 (§C)


@pytest.mark.parametrize("name", st.BATTERIES)
def test_registered_ranges_pass(name: str) -> None:
    spec = st.SPECS[name]
    pilot = range(spec.pilot_r0, spec.pilot_r0 + st.R_PILOT)
    assert st.check_r_range(spec, pilot, main=False) == []
    r_max = st.r_candidates(spec)[-1]
    assert (
        st.check_r_range(spec, range(spec.main_r0, spec.main_r0 + r_max), main=True)
        == []
    )


def test_r_range_violations() -> None:
    g = st.SPECS["G"]
    assert st.check_r_range(g, range(60, 60 + 42), main=True)  # 上限 36 超
    assert st.check_r_range(g, range(61, 61 + 12), main=True)  # 始点
    assert st.check_r_range(g, range(60, 60 + 9), main=True)  # 6 の倍数でない
    assert st.check_r_range(g, range(10, 22), main=False)  # 旧記録と交わる


def test_main_r_caps_from_seed_namespace() -> None:
    # G: 10⁶ 刻みの名前空間で r < 100。O_time: 10⁷ 刻みで r < 1000
    assert st.SPECS["G"].main_r0 + st.SPECS["G"].main_r_cap <= 96
    assert st.SPECS["O_time"].main_r0 + st.SPECS["O_time"].main_r_cap <= 996
    with pytest.raises(ValueError, match="out of range"):
        gbat.sample_seed("fam0", 100, 0, 0)
    with pytest.raises(ValueError, match="out of range"):
        obat.sample_seed("fam0", 1000, 0, 0)


def _seeds(name: str, rs: range) -> set[int]:
    if name in ("v2", "v3"):
        return {
            v2bat.sample_seed(r, qi, k)
            for r in rs
            for qi in range(6)
            for k in range(10)
        }
    if name == "G":
        return {
            gbat.sample_seed(ns, r, j, 0)
            for ns in ("fam0", "fam1", "pilot_fam0", "pilot_fam1")
            for r in rs
            for j in range(gbat.N_TRIPLES)
        }
    return {
        obat.sample_seed(ns, r, i, 0)
        for ns in obat.SEED_NS
        for r in rs
        for i in range(obat.N_ROOMS)
    }


@pytest.mark.parametrize("name", st.BATTERIES)
def test_new_seeds_disjoint_from_used(name: str) -> None:
    spec = st.SPECS[name]
    used = set().union(*(_seeds(name, r) for r in st.USED_R[name]))
    pilot = _seeds(name, range(spec.pilot_r0, spec.pilot_r0 + st.R_PILOT))
    main = _seeds(name, range(spec.main_r0, spec.main_r0 + st.r_candidates(spec)[-1]))
    assert not used & pilot
    assert not used & main
    assert not pilot & main


def test_v2_v3_ranges_do_not_collide() -> None:
    v2, v3 = st.SPECS["v2"], st.SPECS["v3"]
    r2 = set(range(v2.pilot_r0, v2.pilot_r0 + 12)) | set(
        range(v2.main_r0, v2.main_r0 + st.r_candidates(v2)[-1])
    )
    r3 = set(range(v3.pilot_r0, v3.pilot_r0 + 12)) | set(
        range(v3.main_r0, v3.main_r0 + st.r_candidates(v3)[-1])
    )
    assert not r2 & r3
    assert not r2 & set(range(8))


@pytest.mark.parametrize("name", st.BATTERIES)
def test_strata_balanced_in_main(name: str) -> None:
    # 本走の各層 (項目 × 回転) に同数の単位が入る (= 表示位置の均衡)
    spec = st.SPECS[name]
    r_main = st.r_candidates(spec)[0]
    s = st.strata(spec, range(spec.main_r0, spec.main_r0 + r_main))
    counts = np.bincount(s)
    assert len(set(counts[counts > 0].tolist())) == 1
    assert (counts > 0).sum() == st._items_per_rep(spec) * spec.cycle


def test_v2_strata_follow_the_frozen_layout() -> None:
    # v2 の層の回転 = 凍結の layout の (r + probe) mod 4 の巡回
    spec = st.SPECS["v2"]
    s = st.strata(spec, [2001])
    probe0 = v2bat.lever_probes()[2]
    lay = v2bat.layout(2001)
    shift = probe0.omega.index(lay.option_order[probe0.probe_id][0])
    assert s[2 * 10] == 2 * 4 + shift


def test_half_labels_alternate_blocks() -> None:
    spec = st.SPECS["G"]
    h = st.half_labels(spec, range(60, 72))
    per = spec.units_per_rep
    assert list(h[::per]) == [0, 0, 0, 1, 1, 1, 0, 0, 0, 1, 1, 1]


# ------------------------------------------------------------ R の選定・予算 (§G)


def test_sigma_up_ratio_df11() -> None:
    assert st.sigma_up_ratio() == pytest.approx(1.55, abs=0.01)


def test_binom_accept_max_exact() -> None:
    # Bin(2000, 0.05): P(X > x) ≤ 0.01 の最小の x
    # 参照は有理数の正確な算術 (実装の逐次の浮動小数とは別の計算)
    x = st.binom_accept_max(2000, 0.05, 1)
    p, q = Fraction(1, 20), Fraction(19, 20)

    def tail(t: int) -> Fraction:
        return 1 - sum(
            math.comb(2000, i) * p**i * q ** (2000 - i) for i in range(t + 1)
        )

    assert tail(x) <= Fraction(1, 100) < tail(x - 1)


def test_r_candidates_respect_caps() -> None:
    assert st.r_candidates(st.SPECS["G"])[-1] == 36
    o = st.r_candidates(st.SPECS["O_time"])
    assert o[-1] <= 672
    assert all(r % 6 == 0 for r in o)
    v2 = st.r_candidates(st.SPECS["v2"])
    assert all(r % 8 == 0 for r in v2)
    assert v2[-1] * st.SPECS["v2"].sec_per_rep() <= st.BUDGET_SECONDS


def test_select_r_on_quiet_pilot() -> None:
    spec = st.SPECS["O_time"]
    rng = np.random.default_rng(5)
    n = st.R_PILOT * spec.units_per_rep
    pilot = np.stack([np.clip(rng.normal(0.1, 0.15, n), -1, 1) for _ in range(3)])
    r, rows = st.select_r(spec, pilot, 30)
    assert r is not None
    assert rows[-1].ok
    assert rows[-1].r == r
    assert all(not row.ok for row in rows[:-1])


def test_select_r_stop_power_on_noisy_pilot() -> None:
    spec = st.SPECS["G"]
    rng = np.random.default_rng(6)
    n = st.R_PILOT * spec.units_per_rep
    pilot = np.stack([np.where(rng.random(n) < 0.5, 1.0, -1.0) for _ in range(3)])
    r, rows = st.select_r(spec, pilot, 120)
    assert r is None
    assert len(rows) == len(st.r_candidates(spec))


def test_worst_pair_is_max_variance() -> None:
    u = np.array([[0.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 1.0], [0.0, 0.1, 0.0, 0.1]])
    assert st.worst_pair(u) == (0, 1)


def test_budget_cheapest_first() -> None:
    sec = {n: st.SPECS[n].sec_per_rep() for n in st.BATTERIES}
    # O_time を予算を超える R にすると、それだけが保留になる
    r_ot = int(Fraction(st.BUDGET_SECONDS) / sec["O_time"]) + 6
    out = st.budget({"v2": 8, "v3": 8, "G": 12, "O_time": r_ot})
    assert out == {
        "v2": st.GATE_GO,
        "v3": st.GATE_GO,
        "G": st.GATE_GO,
        "O_time": st.GATE_HELD_COST,
    }


def test_shift_calibrates_both_targets_on_asymmetric_pilot() -> None:
    # Codex r1 HIGH-3 の例: 対差が −2・+2・1/6 を 1/8・1/8・3/4 の割合で取る (平均 1/8)
    spec = st.SPECS["G"]
    n = st.R_PILOT * spec.units_per_rep
    base = np.array([-2.0] * 1 + [2.0] * 1 + [1.0 / 6.0] * 6)
    diff = np.tile(base, n // base.size)
    st_p = st.strata(spec, range(spec.pilot_r0, spec.pilot_r0 + st.R_PILOT))
    st_m = st.strata(spec, range(spec.main_r0, spec.main_r0 + 24))
    e = (diff - diff.mean()) * st.sigma_up_ratio()
    # 素朴な移動 (b = 目標) では clip で 0.10 の行がずれる
    naive = st.expected_clipped_mean(e, st_p, st_m, st.DELTA_MIN)
    assert abs(naive - st.DELTA_MIN) > 0.01
    for target in (st.PLAN_GAP, st.DELTA_MIN):
        b = st.solve_shift(e, st_p, st_m, target)
        assert b is not None
        assert st.expected_clipped_mean(e, st_p, st_m, b) == pytest.approx(
            target, abs=1e-9
        )


def test_spike_row_reports_both_directions() -> None:
    spec = st.SPECS["O_time"]
    rng = np.random.default_rng(11)
    n = st.R_PILOT * spec.units_per_rep
    diff = np.clip(rng.normal(0.0, 0.3, n), -2, 2)
    row = st.spike_power(spec, diff, 30, 24, np.random.default_rng(1), n_sims=200)
    assert row.power == min(row.power_by_direction)
    assert len(row.shifts) == 4
    assert row.calibration_err <= st.CALIB_TOL


def test_binom_upper_clopper_pearson() -> None:
    # k = 0: 上限 = 1 − 0.05^(1/n)
    assert st.binom_upper(0, 2000) == pytest.approx(1 - 0.05 ** (1 / 2000), rel=1e-6)
    u = st.binom_upper(10, 100)
    cdf = sum(math.comb(100, i) * u**i * (1 - u) ** (100 - i) for i in range(11))
    assert cdf == pytest.approx(0.05, abs=1e-6)


def test_spike_row_audit_values_recompute_the_decision() -> None:
    spec = st.SPECS["G"]
    rng = np.random.default_rng(12)
    n = st.R_PILOT * spec.units_per_rep
    diff = np.clip(rng.normal(0.05, 0.4, n), -2, 2)
    row = st.spike_power(spec, diff, 60, 24, np.random.default_rng(2), n_sims=200)
    targets = (st.PLAN_GAP, st.DELTA_MIN, st.PLAN_GAP, st.DELTA_MIN)
    calib = max(abs(m - t) for m, t in zip(row.realized_means, targets, strict=True))
    assert calib == pytest.approx(row.calibration_err, abs=1e-15)
    assert max(row.rejects_by_direction) == row.size_rejects
    ok = (
        row.power - 2 * row.power_mcse >= st.POWER
        and row.size_rejects <= row.size_accept_max
        and row.calibration_err <= st.CALIB_TOL
    )
    assert ok == row.ok


def test_spike_reports_descriptive_values() -> None:
    spec = st.SPECS["O_time"]
    rng = np.random.default_rng(13)
    n = st.R_PILOT * spec.units_per_rep
    diff = np.clip(rng.normal(0.0, 0.2, n), -2, 2)
    row = st.spike_power(spec, diff, 30, 48, np.random.default_rng(3), n_sims=200)
    assert row.power_mcse == pytest.approx(math.sqrt(row.power * (1 - row.power) / 200))
    assert row.sd_after_clip > 0
    assert row.sd_before_inflation > 0
    assert row.p_pair_equiv_at_zero is not None
    assert 0.0 <= row.p_pair_equiv_at_zero <= 1.0


def test_spike_negative_all_counts_every_pair() -> None:
    """Codex r4 MEDIUM-2: battery の P((2)) は全順序対を数える (一対の率以下になる)."""
    spec = st.SPECS["O_time"]
    n = st.R_PILOT * spec.units_per_rep
    rng = np.random.default_rng(21)
    quiet = rng.normal(0.0, 0.05, (3, n))
    p_quiet = st.spike_negative_all(spec, quiet, 6, 48, np.random.default_rng(1), 100)
    assert p_quiet > 0.9
    noisy = quiet.copy()
    noisy[2] = np.clip(rng.normal(0.0, 0.9, n), -1, 1)  # 3 本目だけ雑音が大きい
    p_noisy = st.spike_negative_all(spec, noisy, 6, 48, np.random.default_rng(1), 100)
    assert p_noisy < p_quiet
    # 雑音の小さい 2 本の一対だけを見れば高いままで、一対の率は battery の率ではない
    pair = st.spike_negative_all(spec, noisy[:2], 6, 48, np.random.default_rng(1), 100)
    assert pair > p_noisy


def test_negative_on_subset_label() -> None:
    """Codex r4 HIGH-3: pilot 4 本・報告 3 本 (K = 12・ΣM = 4) の (2) は部分集合."""
    u = _units([0.3, 0.3, 0.3])
    d = st.decide_battery(u, 12, 4, _halves(), n_entered=4)
    assert d.verdict == st.VERDICT_NEGATIVE_SUBSET
    assert d.n_excluded == 1
    d2 = st.decide_battery(u, 6, 3, _halves(), n_entered=3)
    assert d2.verdict == st.VERDICT_NEGATIVE
    assert d2.n_excluded == 0


def test_decide_battery_requires_consistent_entrants() -> None:
    u = _units([0.3, 0.3, 0.3])
    with pytest.raises(TypeError):
        st.decide_battery(u, 12, 4, _halves())  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="整合"):
        st.decide_battery(u, 6, 3, _halves(), n_entered=4)  # K < 4·3
    with pytest.raises(ValueError, match="部分集合"):
        st.decide_battery(u, 6, 3, _halves(), n_entered=2)


def test_replicate_lower_bounds_average_within_replicate() -> None:
    u = np.array([np.tile([0.5, 0.3], 40), np.tile([0.1, 0.1], 40)])
    lb = st.replicate_lower_bounds(u, 2, 2)
    assert set(lb) == {"0-1", "1-0"}
    assert lb["0-1"] < 0.3
    assert lb["0-1"] > lb["1-0"]
