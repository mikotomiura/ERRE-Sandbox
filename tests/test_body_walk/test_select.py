"""凍結写像 (pilot prereg §6).

保守値・pilot_low の式・格子・候補順・選定規則・door-close・窓・経験点・見取り図の入力。
"""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from typing import Any

import numpy as np
import pytest
from scripts import body_walk_battery as bat
from scripts import body_walk_select as sel
from scripts import body_walk_sim as sim
from scripts import closed_loop_battery as v4
from scripts import closed_loop_v5_sim as v5sim

from .conftest import first_option, meta_text, synth, to_lines


@lru_cache(maxsize=1)
def _report_text() -> str:
    from scripts import body_walk_pilot_scorer as ps

    rep = ps.evaluate_records(to_lines(synth()), meta_text())
    assert rep["status"] == ps.STATUS_COMPUTED
    return json.dumps(rep)


def _report() -> dict[str, Any]:
    return json.loads(_report_text())


def _measures(**over: Any) -> dict[str, dict[str, Any]]:
    """合成 pilot の測定量に、"<M>__<欄>" で上書きしたもの."""
    m = copy.deepcopy(_report()["measures"])
    for key, val in over.items():
        mm, name = key.split("__")
        m[mm][name] = val
    return m


def test_candidate_order() -> None:
    cands = sel.candidates()
    assert len(cands) == 12
    assert cands[0] == (8, 5, 4)
    calls = [v4.n_main_calls(*c) for c in cands]
    assert calls == sorted(calls)
    assert set(cands) == {
        (r, k, m) for r in (8, 12) for k in (5, 10) for m in (4, 6, 8)
    }
    assert set(bat.M_WINDOWS) == set(sel.M_CANDIDATES)


def test_conservative_values() -> None:
    m = {
        "oov_hi": 0.02,
        "bottom_hi": 0.15,
        "s_same": {"lo": 0.3, "hi": 0.55},
        "s_changed": {"lo": 0.1, "hi": 0.4},
    }
    assert sel.conservative_values(m) == {
        "s_same": 0.55,
        "s_changed": 0.4,
        "oov": 0.05,
        "bot_hi": 0.15,
    }
    m["oov_hi"] = 0.08
    m["bottom_hi"] = 0.01
    assert sel.conservative_values(m)["oov"] == 0.08
    assert sel.conservative_values(m)["bot_hi"] == 0.01  # 床なし (v5 DP-6)


def _low_measure(lo: float) -> dict[str, Any]:
    base = {
        "rain": {
            "read_book": 0.1,
            "walk_path": 0.2,
            "sit_quiet": 0.6,
            "talk_peer": 0.1,
        },
        "clear": {
            "walk_path": 0.4,
            "tend_moss": 0.05,
            "talk_peer": 0.25,
            "rest_eyes": 0.3,
        },
        "wind": {
            "tend_moss": 0.25,
            "read_book": 0.25,
            "rest_eyes": 0.25,
            "sit_quiet": 0.25,
        },
    }
    low = {
        "rain": {"label": "read_book", "lo": lo},
        "clear": {"label": "tend_moss", "lo": lo},
        "wind": {"label": "tend_moss", "lo": lo},
    }
    return {"base": base, "low_prior": low}


def test_pilot_low_formula() -> None:
    """ℓ = lo、他は p_a·(1 − lo)/(1 − p_ℓ) (DC-4)。lo = 0 なら ℓ の質量は 0."""
    got = sel.pilot_low(_low_measure(0.02))
    assert got["rain"]["read_book"] == 0.02
    assert got["rain"]["sit_quiet"] == pytest.approx(0.6 * 0.98 / 0.9)
    assert got["clear"]["tend_moss"] == 0.02
    assert got["clear"]["walk_path"] == pytest.approx(0.4 * 0.98 / 0.95)
    for probs in got.values():
        assert sum(probs.values()) == pytest.approx(1.0)
    zero = sel.pilot_low(_low_measure(0.0))
    assert zero["wind"]["tend_moss"] == 0.0
    assert zero["wind"]["read_book"] == pytest.approx(1 / 3)
    beh = sim.Behaviour(
        lam_dev=0.0,
        base=sim.base_table(zero),
        bot=0.0,
        oov=0.0,
        s_same=0.0,
        s_changed=0.0,
    )
    opts = v4.dev_omega("wind")
    assert sim.base_probs(beh, "wind", opts)[opts.index("tend_moss")] == 0.0


def test_pilot_low_uses_the_scorer_low_prior() -> None:
    m = _measures()["8"]
    got = sel.pilot_low(m)
    for wt, low in m["low_prior"].items():
        assert got[wt][low["label"]] == low["lo"]
        assert low["lo"] <= m["base"][wt][low["label"]]


def test_grid() -> None:
    m = _measures()["4"]
    dps = sel.dev_points(m)
    assert len(dps) == 18
    assert [d.kind for d in dps[:2]] == [sel.KIND_EMPIRICAL] * 2  # 経験点が先
    par = [d for d in dps if d.kind == sel.KIND_PARAMETRIC]
    assert len(par) == 16
    assert {d.coupled for d in par} == {True, False}
    assert {d.lam_src for d in par} == {"pilot", "v4"}
    assert {d.base_src for d in par} == {"pilot", "pilot_low"}
    assert {d.bot for d in dps} == {0.0, m["bottom_hi"]}
    assert len(sel.dev_points({**m, "bottom_hi": 0.0})) == 9  # b = 0 は重複しない
    assert len(sel.probe_points()) == 48
    assert {p.k_rep for p in sel.probe_points()} == {0.0, 0.944}


def test_behaviour_uses_conservative_values() -> None:
    m = _measures()["6"]
    cv = sel.conservative_values(m)
    par = [d for d in sel.dev_points(m) if d.kind == sel.KIND_PARAMETRIC]
    for dp in par:
        beh = sel.behaviour(m, dp)
        assert (beh.s_same, beh.s_changed, beh.oov) == (
            cv["s_same"],
            cv["s_changed"],
            cv["oov"],
        )
        assert beh.coupled is dp.coupled
        assert beh.bot == dp.bot
        want_lam = sel.V4_LAM_DEV if dp.lam_src == "v4" else m["lam_dev"]
        assert beh.lam_dev == want_lam
        probs = m["base"] if dp.base_src == "pilot" else sel.pilot_low(m)
        assert beh.base == sim.base_table(probs)
    none_lam = {**m, "lam_dev": None}
    pilot_lam = next(d for d in par if d.lam_src == "pilot")
    assert sel.behaviour(none_lam, pilot_lam).lam_dev == 0.0


def _select(
    monkeypatch: pytest.MonkeyPatch,
    table: dict[tuple[int, int, int, str], bool],
    measures: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[tuple[int, int, int, str]]]:
    """Evaluator.check を表引きに置き換える: (R, K, M, tag) → 合否."""
    calls: list[tuple[int, int, int, str]] = []

    def fake(
        _self: Any, r: int, k: int, m: int, _n: int, tag: str
    ) -> tuple[bool, list[dict[str, Any]]]:
        calls.append((r, k, m, tag))
        ok = table.get((r, k, m, tag), False)
        row = {
            "ok": ok,
            "pass_at_plant": 1.0,
            "no_go_at_zero": 1.0,
            "pass_at_tau": 0.0,
            "no_go_at_tau": 0.0,
        }
        return ok, [row]

    monkeypatch.setattr(sel.Evaluator, "check", fake)
    rep = _report()
    return sel.select(measures or rep["measures"], rep["chains"]), calls


def test_smallest_candidate_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    table = {
        (8, 10, 4, "screen"): True,
        (8, 10, 4, "final"): True,
        (12, 10, 8, "screen"): True,
        (12, 10, 8, "final"): True,
    }
    out, calls = _select(monkeypatch, table)
    assert out["status"] == sel.STATUS_CHOSEN
    assert out["chosen"] == {
        "R": 8,
        "K": 10,
        "M": 4,
        "calls": v4.n_main_calls(8, 10, 4),
    }
    assert (12, 10, 8, "screen") not in calls
    assert calls.index((8, 5, 4, "screen")) < calls.index((8, 10, 4, "screen"))


def test_final_failure_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    table = {
        (8, 5, 4, "screen"): True,
        (8, 5, 4, "final"): False,
        (8, 5, 6, "screen"): True,
        (8, 5, 6, "final"): True,
    }
    out, _ = _select(monkeypatch, table)
    assert out["chosen"]["M"] == 6
    assert out["final"][0]["ok"] is False


def test_door_close(monkeypatch: pytest.MonkeyPatch) -> None:
    out, calls = _select(monkeypatch, {})
    assert out["status"] == sel.STATUS_DOOR_CLOSE
    assert out["chosen"] is None
    assert len(calls) == 12  # 12 候補、本確認なし
    assert all(c[3] == "screen" for c in calls)


def test_rejected_m_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    m = _measures(**{"4__rejected_bottom": True})
    table = {(8, 5, 4, "screen"): True, (8, 5, 4, "final"): True}
    out, calls = _select(monkeypatch, table, m)
    assert out["rejected_bottom_M"] == [4]
    assert not any(c[2] == 4 for c in calls)
    assert any(c[2] == 6 for c in calls)
    assert out["status"] == sel.STATUS_DOOR_CLOSE
    assert "4" not in out["conservative_values"]


def test_measures_and_chains_are_taken_from_the_candidate_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[float] = []
    real = sel.behaviour

    def spy(m: Any, dp: Any) -> sim.Behaviour:
        beh = real(m, dp)
        seen.append(beh.s_same)
        return beh

    rep = _report()
    measures = _measures(**{"6__s_same": {"lo": 0.1, "hi": 0.11}})
    ev = sel.Evaluator(measures, rep["chains"], sel.Sims(curve=4, screen=4, final=4))
    monkeypatch.setattr(sel, "behaviour", spy)
    monkeypatch.setattr(sim, "simulate_dev", lambda *_a, **_k: None)
    dps = sel.dev_points(measures["6"])
    par = next(d for d in dps if d.kind == sel.KIND_PARAMETRIC)
    ev.dev(par, 6, (0,), 4, "screen")
    ev.dev(par, 4, (0,), 4, "screen")
    assert seen == [0.11, measures["4"]["s_same"]["hi"]]
    emp = ev.dev(dps[0], 6, (0, 1), 4, "screen")
    assert emp.steps == 72
    assert emp.succ.shape == (4, 2, 4, bat.N_DEV)


def test_not_computed_pilot_is_not_mapped() -> None:
    out = sel.map_run(to_lines(synth(stop_after=10)), meta_text())
    assert out["mapping"] == {"status": sel.STATUS_NOT_MAPPED, "chosen": None}
    bad_meta = json.dumps({**json.loads(meta_text()), "top_p": 0.8})
    out = sel.map_run(to_lines(synth()), bad_meta)
    assert out["mapping"]["status"] == sel.STATUS_NOT_MAPPED


def _fixed_wrong(key: bat.PilotKey, _st: v4.State, _opts: tuple[str, ...]) -> str:
    """表示順に依らない固定の誤答を常に選ぶ = 探索しない.

    誤答 = 規則でない、正準順で最初の label。
    """
    weather = v4.loop_signature(key.replicate, key.step)[0]
    rule = v4.rule(key.world)[weather]
    return next(o for o in v4.dev_omega(weather) if o != rule)


def test_end_to_end_small_grid(monkeypatch: pytest.MonkeyPatch) -> None:
    """格子を小さくして、合成 pilot → 写像まで通す.

    探索しない方策なので、植えられず door-close になる。
    """
    monkeypatch.setattr(
        sel, "probe_points", lambda: [v5sim.ProbePoint("measured", 0.3, "flat", 0.0)]
    )
    real_dev = sel.dev_points
    monkeypatch.setattr(sel, "dev_points", lambda m: real_dev(m)[:1])
    monkeypatch.setattr(sel, "candidates", lambda: [(8, 5, 4)])
    lines = to_lines(synth(policy=_fixed_wrong))
    out = sel.map_run(lines, meta_text(), sel.Sims(50, 50, 50))
    m = out["pilot"]["measures"]["4"]
    assert m["s_same"]["rate"] == 1.0
    assert out["pilot"]["status"] == "computed"
    assert out["mapping"]["status"] == sel.STATUS_DOOR_CLOSE
    first = out["mapping"]["screening"][0]["first_violation"]
    assert first["dev_point"]["kind"] == sel.KIND_EMPIRICAL
    assert first["reachable"] is False  # 規則を一度も選ばない → C = 0.6 を植えられない
    again = sel.map_run(lines, meta_text(), sel.Sims(50, 50, 50))
    assert sel.dumps(again) == sel.dumps(out)


def test_exploring_pilot_is_plantable_on_the_empirical_point() -> None:
    """経験点で C = 0.6 を植えられるかは、pilot の発見しだい.

    全 signature を発見した pilot では植えられ、探索しない pilot では植えられない。
    """
    pp = v5sim.ProbePoint("uniform", 0.05, "flat", 0.0)
    from scripts import body_walk_pilot_scorer as ps

    def rule_then_first(key: bat.PilotKey, _st: v4.State, opts: tuple[str, ...]) -> str:
        weather = v4.loop_signature(key.replicate, key.step)[0]
        return v4.rule(key.world)[weather] if key.step >= bat.N_DEV else opts[0]

    rows = {}
    for name, policy in (("explore", rule_then_first), ("stuck", _fixed_wrong)):
        rep = ps.evaluate_records(to_lines(synth(policy=policy)), meta_text())
        ev = sel.Evaluator(rep["measures"], rep["chains"], sel.Sims(200, 200, 200))
        dp = sel.dev_points(rep["measures"]["4"])[0]
        rows[name] = ev.row(dp, pp, 8, 5, 4, 200, "screen")
    assert rows["explore"]["reachable"]
    assert rows["explore"]["coverage"] == 1.0
    assert not rows["stuck"]["reachable"]


def test_hypothetical_behaviour() -> None:
    beh = sel.hypothetical_behaviour(0.5)
    assert (beh.s_same, beh.s_changed, beh.bot, beh.oov) == (0.5, 0.5, 0.0, 0.0)
    assert beh.lam_dev == sel.V4_LAM_DEV
    exponent = 0.7 / 1.3
    want = sim.tempered_table(sel.V4_LOOP_BASE, exponent)
    for (wt, got), (_, exp) in zip(beh.base, want, strict=True):
        assert dict(got) == pytest.approx(dict(exp)), wt
    assert sel.TABLE_ROWS == (0.0, 0.5, 0.9)


def test_decision_table_feeds_synthetic_pilots(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[int, str]] = []

    def fake_map_run(
        lines: list[str], meta: str, *_a: Any, **_k: Any
    ) -> dict[str, Any]:
        seen.append((len(lines), meta))
        return {"pilot": None, "mapping": {"status": "x"}}

    monkeypatch.setattr(sel, "map_run", fake_map_run)
    rows = sel.decision_table()
    assert [r["s"] for r in rows] == list(sel.TABLE_ROWS)
    assert all(n == len(bat.pilot_plan()) for n, _ in seen)
    assert all(json.loads(meta) == bat.request_meta_walk() for _, meta in seen)


def test_dumps_is_deterministic() -> None:
    a = sel.dumps({"b": 0.1234567891, "a": [1.0, (2, 3)], "c": np.float64(0.5)})
    assert a == sel.dumps({"a": [1.0, (2, 3)], "b": 0.1234567891, "c": 0.5})
    assert "0.123457" in a


def test_first_option_pilot_is_mapped(monkeypatch: pytest.MonkeyPatch) -> None:
    """computed の pilot なら写像を計算する (表示先頭の方策でも)."""
    monkeypatch.setattr(sel, "candidates", list)
    out = sel.map_run(to_lines(synth(policy=first_option)), meta_text())
    assert out["mapping"]["status"] == sel.STATUS_DOOR_CLOSE
    assert set(out["mapping"]["conservative_values"]) == {"4", "6", "8"}


def test_row_passes_the_dev_point_bot_and_the_candidate_r(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}
    real_curve, real_crit = v5sim.kappa_curve, v5sim.design_criteria

    def curve_spy(pp: Any, bot: float, dev: Any) -> Any:
        seen["curve"] = (bot, dev.succ.shape[1])
        return real_curve(pp, bot, dev)

    def crit_spy(pp: Any, bot: float, curve: Any, dev: Any, k: int, parts: Any) -> Any:
        seen["crit"] = (bot, dev.succ.shape[1], k, parts[0])
        return real_crit(pp, bot, curve, dev, k, parts)

    monkeypatch.setattr(v5sim, "kappa_curve", curve_spy)
    monkeypatch.setattr(v5sim, "design_criteria", crit_spy)
    rep = _report()
    m = _measures(**{"4__bottom_hi": 0.07})
    ev = sel.Evaluator(m, rep["chains"], sel.Sims(20, 20, 20))
    dp = next(d for d in sel.dev_points(m["4"]) if d.bot == 0.07)
    pp = v5sim.ProbePoint("uniform", 0.05, "flat", 0.0)
    ev.row(dp, pp, 8, 10, 4, 20, "screen")
    assert seen["curve"] == (0.07, len(sel.CURVE_R))
    assert seen["crit"] == (0.07, 8, 10, sel.SIM_TAG)
