"""凍結模擬 (pilot prereg §5).

逐次参照との完全一致 (描画した prompt の一致で結合・同一 prompt の記憶)、
同一 prompt の key が描画状態そのもの、
結合の両端、経験点の復元抽出、合成 pilot の決定性、probe 段の再利用。
"""

from __future__ import annotations

import itertools

import numpy as np
import pytest
from scripts import body_walk_battery as bat
from scripts import body_walk_sim as sim
from scripts import closed_loop_battery as v4
from scripts import closed_loop_sim as v4sim
from scripts import closed_loop_v5_select as v5sel
from scripts import closed_loop_v5_sim as v5sim
from scripts.stage_b_battery import ACTIONS

from .conftest import behaviour

DEVS = sim.DEVS
UNIFORM = sim.base_table(
    {wt: dict.fromkeys(v4.dev_omega(wt), 0.25) for wt in ("rain", "clear", "wind")}
)


@pytest.mark.parametrize(
    "kw",
    [
        {},
        {"bot": 0.1, "oov": 0.05},
        {"s_same": 1.0, "s_changed": 0.0, "lam_dev": 0.0},
        {"s_same": 0.0, "s_changed": 1.0, "base": UNIFORM},
        {"coupled": False, "bot": 0.1, "oov": 0.05},
        {"coupled": False, "s_same": 0.9, "s_changed": 0.2},
        # ⊥ の訪問の後に同じ成功集合で再訪する場面: 記憶は ⊥ でない訪問だけで更新する
        {"bot": 0.3, "s_same": 1.0, "s_changed": 0.0, "lam_dev": 0.0},
    ],
)
def test_vectorized_matches_reference(kw: dict[str, object]) -> None:
    beh = behaviour(**kw)
    r_values = (16, 21)
    m = 4
    succ, picks = sim.simulate_dev_reference(
        beh, m, r_values, 3, np.random.default_rng(11)
    )
    dev = sim.simulate_dev(beh, m, r_values, 3, np.random.default_rng(11), record=True)
    assert dev.picks is not None
    np.testing.assert_array_equal(dev.picks, picks)
    np.testing.assert_array_equal(dev.succ, succ)
    assert dev.steps == bat.N_DEV * m


def test_same_prompt_key_is_the_rendered_state() -> None:
    """同じ (世界, r, t mod 12) の描画は、成功集合 (bitmask) だけで決まる.

    R1・周で不変の表示順の下で。
    """
    rng = np.random.default_rng(5)
    for w in v4.WORLDS:
        for _ in range(30):
            a = frozenset(s for s in DEVS if rng.random() < 0.4)
            b = frozenset(s for s in DEVS if rng.random() < 0.4)
            t = int(rng.integers(0, bat.PILOT_T))
            same_msgs = bat.loop_messages(
                v4.State(succeeded=a), w, 16, t
            ) == bat.loop_messages(v4.State(succeeded=b), w, 16, t + bat.N_DEV)
            mask_a = sum(1 << j for j, s in enumerate(DEVS) if s in a)
            mask_b = sum(1 << j for j, s in enumerate(DEVS) if s in b)
            assert same_msgs == (mask_a == mask_b)


def test_full_repetition_freezes_the_state() -> None:
    """s_same = s_changed = 1・λ_dev = 0 なら、成功は 1 周目から増えない.

    2 周目以降は前回を繰り返すため。
    """
    beh = behaviour(s_same=1.0, s_changed=1.0, lam_dev=0.0)
    one = sim.simulate_dev(beh, 1, (16, 17), 40, np.random.default_rng(3))
    four = sim.simulate_dev(beh, 4, (16, 17), 40, np.random.default_rng(3), record=True)
    np.testing.assert_array_equal(one.succ, four.succ)
    loose = sim.simulate_dev(
        behaviour(s_same=0.0, s_changed=0.0, lam_dev=0.0),
        4,
        (16, 17),
        40,
        np.random.default_rng(3),
    )
    assert loose.succ.sum() > four.succ.sum()


def test_coupling_ends() -> None:
    """結合の両端.

    coupled: t = 0 は 4 世界の prompt が同一なので同じ選択。
    independent: 世界ごとに独立。
    """
    kw = {"base": UNIFORM, "bot": 0.0, "oov": 0.0}
    tied = sim.simulate_dev(
        behaviour(**kw), 1, (16,), 200, np.random.default_rng(2), record=True
    )
    free = sim.simulate_dev(
        behaviour(coupled=False, **kw),
        1,
        (16,),
        200,
        np.random.default_rng(2),
        record=True,
    )
    assert tied.picks is not None
    assert free.picks is not None
    t0_tied = tied.picks[:, 0, :, 0]
    t0_free = free.picks[:, 0, :, 0]
    assert np.all(t0_tied == t0_tied[:, :1])
    assert np.any(t0_free != t0_free[:, :1])


def test_reference_branches() -> None:
    beh = behaviour(bot=0.5, oov=0.5, s_same=0.5, s_changed=0.5, lam_dev=0.5)
    w, r, t = v4.WORLDS[0], 16, 0
    sig = v4.loop_signature(r, t)
    opts = bat.dev_options(r, t)
    rule = v4.rule(w)[sig[0]]
    other = next(o for o in opts if o != rule)
    u = [0.9] * sim.N_U
    empty = v4.EMPTY_STATE
    assert (
        sim.dev_choice_reference(beh, empty, w, r, t, None, None, [0.1, *u[1:]]) is None
    )
    done = v4.State(succeeded=frozenset({sig}))
    assert sim.dev_choice_reference(beh, done, w, r, t, None, None, u) == rule
    rep = list(u)
    rep[sim.U_REP] = 0.1
    assert sim.dev_choice_reference(beh, empty, w, r, t, None, other, rep) == other
    assert sim.dev_choice_reference(beh, empty, w, r, t, other, None, rep) == other
    oov = list(u)
    oov[sim.U_OOV] = 0.1
    got = sim.dev_choice_reference(beh, empty, w, r, t, None, None, oov)
    assert got in ACTIONS
    assert got not in opts


def test_empirical_dev_resamples_whole_blocks() -> None:
    n_b = len(bat.PILOT_R)
    succ = [
        [[int((b + wi + j) % 3 == 0) for j in range(bat.N_DEV)] for wi in range(4)]
        for b in range(n_b)
    ]
    bot = [[b * 10 + wi for wi in range(4)] for b in range(n_b)]
    ch = {"steps": 48, "succ": succ, "bot": bot}
    dev = sim.empirical_dev(ch, 8, 50, np.random.default_rng(1))
    assert dev.succ.shape == (50, 8, 4, bat.N_DEV)
    assert dev.steps == 48
    arr = np.asarray(succ, dtype=bool)
    for i, j in itertools.product(range(50), range(8)):
        b = dev.loop_bot[i, j, 0] // 10
        np.testing.assert_array_equal(
            dev.succ[i, j], arr[b]
        )  # 4 世界がまとめて同じ block
        assert list(dev.loop_bot[i, j]) == bot[b]
    assert len({int(x) // 10 for x in dev.loop_bot[..., 0].ravel()}) > 1


def test_synthetic_records_are_a_deterministic_model() -> None:
    recs = sim.synthetic_records(behaviour())
    assert recs == sim.synthetic_records(behaviour())
    assert recs != sim.synthetic_records(behaviour(), tag="other")
    groups: dict[tuple[str, int], set[str]] = {}
    for x in recs:
        groups.setdefault((x["prompt_sha256"], x["seed"]), set()).add(x["raw"])
    assert all(len(v) == 1 for v in groups.values())
    assert [(x["phase"], x["world"], x["replicate"], x["step"]) for x in recs] == [
        (k.phase, k.world, k.replicate, k.step) for k in bat.pilot_plan()
    ]


def test_tempered_table() -> None:
    same = dict(dict(sim.tempered_table(v5sel.V4_LOOP_BASE, 1.0))["rain"])
    assert same == pytest.approx(v5sel.V4_LOOP_BASE["rain"])
    flat = dict(dict(sim.tempered_table(v5sel.V4_LOOP_BASE, 0.0))["clear"])
    assert set(flat.values()) == {0.25}
    half = dict(dict(sim.tempered_table(v5sel.V4_LOOP_BASE, 0.5))["rain"])
    assert sum(half.values()) == pytest.approx(1.0)
    assert max(half.values()) < max(v5sel.V4_LOOP_BASE["rain"].values())


def test_probe_stage_on_empirical_ends() -> None:
    """経験点の DevResult は v5 の probe 段にそのまま渡る.

    全成功なら 2τ を植えられ、成功なしなら植えられない。
    """
    pp = v5sim.ProbePoint("uniform", 0.05, "flat", 0.0)
    full = {
        "steps": 96,
        "succ": [[[1] * bat.N_DEV] * 4] * 12,
        "bot": [[0] * 4] * 12,
    }
    none = {**full, "succ": [[[0] * bat.N_DEV] * 4] * 12}
    for ch, reachable in ((full, True), (none, False)):
        curve_dev = sim.empirical_dev(ch, 12, 50, np.random.default_rng(0))
        curve = v5sim.kappa_curve(pp, 0.0, curve_dev)
        dev = sim.empirical_dev(ch, 8, 50, np.random.default_rng(1))
        crit = v5sim.design_criteria(pp, 0.0, curve, dev, 5, ("t",))
        assert isinstance(crit, v4sim.Criteria)
        assert crit.reachable is reachable
