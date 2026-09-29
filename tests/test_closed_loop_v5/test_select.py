"""凍結写像 (pilot prereg §6).

保守値・格子・候補順・選定規則・door-close・v4 の較正値。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from scripts import closed_loop_battery as v4
from scripts import closed_loop_v5_battery as bat
from scripts import closed_loop_v5_select as sel
from scripts import closed_loop_v5_sim as sim

from .conftest import first_option, meta_text, synth, to_lines

if TYPE_CHECKING:
    import pytest


def _measures(**over: Any) -> dict[str, dict[str, dict[str, Any]]]:
    m = sel.hypothetical_measures(0.3, 0.6)
    for key, val in over.items():
        mm, axis, field = key.split("__")
        m[mm] = {a: dict(v) for a, v in m[mm].items()}
        m[mm][axis][field] = val
    return m


def test_v4_calibration_constants_are_observed() -> None:
    lam, base = sel.v4_calibration()
    assert lam == sel.V4_LAM_DEV
    assert base == sel.V4_LOOP_BASE


def test_candidate_order() -> None:
    cands = sel.candidates()
    assert len(cands) == 12
    assert cands[0] == (8, 5, 4)
    calls = [v4.n_main_calls(*c) for c in cands]
    assert calls == sorted(calls)
    assert set(cands) == {
        (r, k, m) for r in (8, 12) for k in (5, 10) for m in (4, 6, 8)
    }


def test_conservative_values() -> None:
    m = {
        "oov_hi": 0.02,
        "bottom_hi": 0.15,
        "s_changed": {"lo": 0.1, "hi": 0.4},
        "eps": {"lo": 0.3, "hi": 0.7},
    }
    assert sel.conservative_values("B", m) == {
        "oov": 0.05,
        "bot_hi": 0.15,
        "s_changed": 0.4,
    }
    assert sel.conservative_values("C", m) == {"oov": 0.05, "bot_hi": 0.15, "eps": 0.3}
    m["oov_hi"] = 0.08
    m["bottom_hi"] = 0.01
    assert sel.conservative_values("C", m)["oov"] == 0.08
    assert sel.conservative_values("C", m)["bot_hi"] == 0.01  # 床なし (DP-6)


def test_grid() -> None:
    m = _measures()["4"]
    assert len(sel.dev_points("B", m["B"])) == 12
    assert len(sel.dev_points("C", m["C"])) == 24
    m_zero = {**m["C"], "bottom_hi": 0.0}
    assert len(sel.dev_points("C", m_zero)) == 12  # b = 0 は重複しない
    assert {d.bot for d in sel.dev_points("C", m["C"])} == {0.0, m["C"]["bottom_hi"]}
    assert {d.untried for d in sel.dev_points("B", m["B"])} == {sim.UNTRIED_UNIFORM}
    assert len(sel.probe_points()) == 48
    assert {p.k_rep for p in sel.probe_points()} == {0.0, 0.944}
    assert {p.base for p in sel.probe_points()} == {
        "measured",
        "uniform",
        "label_skew",
        "position_skew",
    }


def test_behaviour_uses_conservative_values() -> None:
    m = _measures()["6"]
    dps = sel.dev_points("C", m["C"])
    beh = sel.behaviour("C", m["C"], dps[0])
    assert (beh.eps, beh.rho, beh.s_same) == (0.6, 1.0, 0.96)
    assert beh.lam_dev == sel.V4_LAM_DEV  # 仮想の測定量の pilot 値は v4 と同じ
    b = sel.behaviour("B", m["B"], sel.dev_points("B", m["B"])[0])
    assert b.s_changed == 0.3
    c0 = next(d for d in dps if d.base_src == "v4_c0")
    assert sel.behaviour("C", m["C"], c0).base is None
    none_lam = dict(m["C"], lam_dev=None)
    pilot_lam = next(d for d in dps if d.lam_src == "pilot")
    assert sel.behaviour("C", none_lam, pilot_lam).lam_dev == 0.0


def _select(monkeypatch: pytest.MonkeyPatch, table, measures=None):
    """Evaluator.check を表引きに置き換える: (axis, R, K, M, tag) → 合否."""
    calls: list[tuple[str, int, int, int, str]] = []

    def fake(_self, axis, r, k, m, _n, tag):
        calls.append((axis, r, k, m, tag))
        ok = table.get((axis, r, k, m, tag), False)
        row = {
            "ok": ok,
            "pass_at_plant": 1.0,
            "no_go_at_zero": 1.0,
            "pass_at_tau": 0.0,
            "no_go_at_tau": 0.0,
        }
        return ok, [row]

    monkeypatch.setattr(sel.Evaluator, "check", fake)
    return sel.select(measures or _measures()), calls


def test_smallest_candidate_wins_and_tie_goes_to_b(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = {
        ("B", 8, 10, 4, "screen"): True,
        ("B", 8, 10, 4, "final"): True,
        ("C", 8, 10, 4, "screen"): True,
        ("C", 8, 10, 4, "final"): True,
        ("C", 12, 10, 8, "screen"): True,
        ("C", 12, 10, 8, "final"): True,
    }
    out, calls = _select(monkeypatch, table)
    assert out["status"] == sel.STATUS_CHOSEN
    assert out["chosen"] == {
        "axis": "B",
        "R": 8,
        "K": 10,
        "M": 4,
        "calls": v4.n_main_calls(8, 10, 4),
    }
    assert ("C", 8, 10, 4, "screen") not in calls


def test_final_failure_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    table = {
        ("B", 8, 5, 4, "screen"): True,
        ("B", 8, 5, 4, "final"): False,
        ("C", 8, 5, 4, "screen"): True,
        ("C", 8, 5, 4, "final"): True,
    }
    out, _ = _select(monkeypatch, table)
    assert out["chosen"]["axis"] == "C"
    assert out["final"][0]["ok"] is False


def test_door_close(monkeypatch: pytest.MonkeyPatch) -> None:
    out, calls = _select(monkeypatch, {})
    assert out["status"] == sel.STATUS_DOOR_CLOSE
    assert out["chosen"] is None
    assert len(calls) == 24  # 12 候補 × 2 軸、本確認なし
    assert all(c[4] == "screen" for c in calls)


def test_rejected_axis_is_skipped_per_m(monkeypatch: pytest.MonkeyPatch) -> None:
    m = _measures(**{"4__B__rejected_bottom": True})
    table = {("B", 8, 5, 4, "screen"): True, ("B", 8, 5, 4, "final"): True}
    out, calls = _select(monkeypatch, table, m)
    assert out["rejected_axes"]["4"] == ["B"]
    assert not any(c[0] == "B" and c[3] == 4 for c in calls)
    assert any(c[0] == "B" and c[3] == 6 for c in calls)
    assert out["status"] == sel.STATUS_DOOR_CLOSE


def test_measures_are_taken_from_the_candidate_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[int, float]] = []
    real = sel.behaviour

    def spy(axis, m, dp):
        beh = real(axis, m, dp)
        seen.append((axis, beh.eps if axis == "C" else beh.s_changed))
        return beh

    m = _measures(**{"6__C__eps": {"lo": 0.11, "hi": 0.9}})
    ev = sel.Evaluator(m, sel.Sims(curve=4, screen=4, final=4))
    monkeypatch.setattr(sel, "behaviour", spy)
    monkeypatch.setattr(sim, "simulate_dev", lambda *_a, **_k: None)
    dp = sel.dev_points("C", m["6"]["C"])[0]
    ev.dev("C", dp, 6, (0,), 4, "screen")
    ev.dev("C", dp, 4, (0,), 4, "screen")
    assert seen == [("C", 0.11), ("C", 0.6)]


def test_not_computed_pilot_is_not_mapped() -> None:
    out = sel.map_run(to_lines(synth(first_option, stop_after=10)), meta_text())
    assert out["mapping"] == {"status": sel.STATUS_NOT_MAPPED, "chosen": None}


def test_end_to_end_small_grid(monkeypatch: pytest.MonkeyPatch) -> None:
    """格子を 1 点・模擬回数を小さくして、合成 pilot → 写像まで通す (探索しない方策 →
    植えられず door-close).
    """
    monkeypatch.setattr(
        sel, "probe_points", lambda: [sim.ProbePoint("measured", 0.3, "flat", 0.0)]
    )
    real_dev = sel.dev_points
    monkeypatch.setattr(sel, "dev_points", lambda a, m: real_dev(a, m)[:1])
    monkeypatch.setattr(sel, "candidates", lambda: [(8, 5, 4)])

    def fixed_wrong(key, _st, _opts, _text):
        """表示順に依らない固定の誤答 (規則でない正準順で最初の label) を常に選ぶ =
        探索しない.
        """
        weather = v4.loop_signature(key.replicate, key.step)[0]
        rule = v4.rule(key.world)[weather]
        return next(o for o in v4.dev_omega(weather) if o != rule)

    out = sel.map_run(to_lines(synth(fixed_wrong)), meta_text(), sel.Sims(50, 50, 50))
    m = out["pilot"]["measures"]["4"]
    assert m["B"]["s_changed"]["rate"] == 1.0
    assert m["C"]["eps"]["rate"] == 0.0
    assert out["pilot"]["status"] == "computed"
    assert out["mapping"]["status"] == sel.STATUS_DOOR_CLOSE
    first = out["mapping"]["screening"][0]["first_violation"]
    assert first["reachable"] is False  # 規則を一度も選ばない → C = 0.6 を植えられない


def test_hypothetical_exploring_c_is_plantable() -> None:
    """ε = 1 の C は全 weather を発見し、C = 0.6 を植えられる (s = 1 の B
    は植えられない).
    """
    m = sel.hypothetical_measures(1.0, 1.0)
    ev = sel.Evaluator(m, sel.Sims(curve=200, screen=200, final=200))
    pp = sim.ProbePoint("uniform", 0.05, "flat", 0.0)
    c = ev.row("C", sel.dev_points("C", m["4"]["C"])[0], pp, 8, 5, 4, 200, "screen")
    b = ev.row("B", sel.dev_points("B", m["4"]["B"])[0], pp, 8, 5, 4, 200, "screen")
    assert c["reachable"]
    assert c["coverage"] > b["coverage"]


def test_dumps_is_deterministic() -> None:
    a = sel.dumps({"b": 0.1234567891, "a": [1.0, (2, 3)]})
    assert a == sel.dumps({"a": [1.0, (2, 3)], "b": 0.1234567891})
    assert "0.123457" in a


def test_rejected_axis_bookkeeping_has_all_m() -> None:
    assert set(bat.M_WINDOWS) == set(sel.M_CANDIDATES)
