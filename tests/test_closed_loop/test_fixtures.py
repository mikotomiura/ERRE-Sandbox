"""相殺の定理と fixture 表 (prereg v4 §2.5、ADR §3.1、user 裁定 DU-1)."""

from __future__ import annotations

import numpy as np
import pytest
from scripts import closed_loop_battery as bat
from scripts import closed_loop_sim as sim

CFG = sim.Config(
    base="measured", bot=0.1, sd=0.05, lam="flat", renderer=bat.RENDERER_R1PLUS, m=3
)


@pytest.mark.parametrize("name", sorted(sim.STATE_BLIND))
@pytest.mark.parametrize("renderer", bat.RENDERERS)
def test_state_blind_policies_cancel_exactly_per_unit(name: str, renderer: str) -> None:
    """状況・選択肢・seed だけの方策は、族内でループの行動列が一致し、全単位で d = 0
    (厳密).
    """
    cfg = sim.Config(
        base="measured", bot=0.1, sd=0.05, lam="flat", renderer=renderer, m=3
    )
    res = sim.run_fixture(
        sim.STATE_BLIND[name],
        mode="L",
        cfg=cfg,
        kappa=0.0,
        rho=1.0,
        r_count=4,
        k=5,
        n_iter=3,
        seed=7,
    )
    assert res.units == [0.0] * len(res.units)


def test_positive_control_lookup_is_large() -> None:
    res = sim.run_fixture(
        sim.POSITIVE_CONTROL[1],
        mode="P",
        cfg=CFG,
        kappa=1.0,
        rho=1.0,
        r_count=4,
        k=5,
        n_iter=5,
        seed=7,
    )
    assert np.mean(res.units) > 0.5


def test_neighbor_fixture_points_to_the_foil() -> None:
    """近傍 (時刻・同伴が一致、weather を無視) は構造上 foil を指す (DU-1 の根拠、
    負の寄与).
    """
    res = sim.run_fixture(
        sim.FIXTURES["F8_neighbor"],
        mode="P",
        cfg=CFG,
        kappa=1.0,
        rho=1.0,
        r_count=4,
        k=5,
        n_iter=5,
        seed=7,
    )
    assert np.mean(res.units) < -0.2


def test_fixture_views_read_state_text_labels() -> None:
    devs = bat.dev_signatures()
    st = bat.State(
        succeeded=frozenset({devs[0]}),
        tried=frozenset({(devs[0], "read_book"), (devs[0], "walk_path")}),
    )
    v = sim.make_view(
        st,
        "A",
        0,
        bat.RENDERER_R1PLUS,
        devs[1],
        ("read_book", "walk_path", "sit_quiet", "talk_peer"),
        None,
        1,
        "loop",
    )
    assert v.labels == ["read_book", "read_book", "walk_path"]
    assert v.n_lines == 2
    assert sim.f_most(v) == "read_book"
    assert sim.f_last(v) == "walk_path"
    assert sim.f_least_tried(v) == "sit_quiet"
    assert sim.f_most_tried(v) == "read_book"
    assert sim.f_count(v) == "sit_quiet"
    assert sim.f_nonempty(v) == "read_book"


def _row(fixture: str, mean: float, se: float = 0.0) -> dict[str, object]:
    return {"fixture": fixture, "mean": mean, "se": se}


def test_fixture_gate_is_positive_side_only() -> None:
    ok, worst, flagged = sim.fixture_gate([_row("F1", 0.03, 0.005), _row("F8", -0.9)])
    assert ok
    assert worst["fixture"] == "F1"
    assert flagged == []
    ok, _, flagged = sim.fixture_gate([_row("F1", 0.07, 0.002), _row("F8", -0.9)])
    assert ok  # 0.076: 列挙されるが硬い gate (0.15) は通る
    assert flagged == ["F1"]
    ok, _, flagged = sim.fixture_gate([_row("F3", 0.14, 0.004), _row("F1", 0.08)])
    assert not ok  # 0.152 ≥ 0.15
    assert flagged == ["F1", "F3"]
    ok, _, flagged = sim.fixture_gate(
        [_row("F1", 0.01), _row(sim.POSITIVE_CONTROL[0], 0.9)]
    )
    assert ok  # 陽性対照は gate の対象外
    assert flagged == []
    assert pytest.approx(0.075) == sim.FIXTURE_GATE
    assert pytest.approx(0.15) == sim.FIXTURE_HARD


def test_fixture_registry() -> None:
    assert set(sim.FIXTURES) == {
        "F1_most_label",
        "F2_first_row",
        "F3_last_row",
        "F4_line_count",
        "F5_nonempty",
        "F6_label_x_position",
        "F7_repeat_previous",
        "F8_neighbor",
        "F9_hash_a",
        "F10_hash_b",
        "F11_hash_c",
        "F12_least_tried",
        "F13_most_tried",
    }
    assert {"F12_least_tried", "F13_most_tried"} == sim.R1PLUS_ONLY
