"""判別性 gate 段 2 — 登録方策 (fixture) の再計算の test (prereg §I.3・§J、Codex r1 M1).

* v2・v3 の移植した方策は、tests の原本と段 2 の実 r の全セルで同じ label を返す
  (原本が test 関数の中にある v2 の recency・position は、
  原本の 1 行をここに写して比べる)。
* 比べた方策どうしが実 r で別の label を選ぶセルがある (一致の検査が空でない)。
* 凍結の R (r ∈ [0, R)) で各 prereg の表の値を再現し、
  G・O_time は凍結の ``policy_c`` と一致する。
* 段 2 の実 r で陽性対照 ±1・v3 の近傍 −1・直前 > 0 > 直後。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import numpy as np
import pytest
from scripts import benchmark_stage2_fixtures as fxm
from scripts import benchmark_stage2_records as rd
from scripts import benchmark_stage2_stats as st
from scripts import benchmark_stage2_units as un
from scripts import generalization_probe_fixtures as gfx
from scripts import o_time_probe_fixtures as ofx
from scripts import skill_experience_scorer as v3sc
from scripts import skill_lever_battery as v2bat
from scripts import skill_lever_scorer as v2sc

from tests.test_skill_experience import test_nuisance as v3orig
from tests.test_skill_lever import test_scorer as v2orig

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Callable

# 段 2 の本走の r (pilot の gate が選んだ R、DD-9)
V2_R = list(range(rd.MAIN_R0["v2"], rd.MAIN_R0["v2"] + 32))
V3_R = list(range(rd.MAIN_R0["v3"], rd.MAIN_R0["v3"] + 80))
_PROBES = {p.probe_id: p for p in v2bat.lever_probes()}


def _orig_recency(arm: str, r: int, p: v2bat.LeverProbe, k: int) -> str:
    """``test_recency_only_is_not_pass`` の内側の方策の写し."""
    if arm == v2bat.ARM_C0:
        return p.omega[k % 4]
    return v2bat.state_entries(arm, v2bat.layout(r))[-1][1]


def _orig_position(_arm: str, r: int, p: v2bat.LeverProbe, _k: int) -> str:
    """``test_position_only_is_not_pass`` の内側の方策の写し."""
    return v2bat.layout(r).option_order[p.probe_id][0]


V2_ORIGINAL: dict[str, Callable[..., str]] = {
    "priming": v2orig.priming_only,
    "uniform_null": v2orig.uniform_null,
    "positive_control_rule_lookup": v2orig.lookup,
    "recency_last_entry": _orig_recency,
    "position": _orig_position,
}
V3_ORIGINAL: dict[str, Callable[..., str]] = {
    **{f"outcome_blind/{k}": v for k, v in v3orig.OUTCOME_BLIND.items()},
    **{k: v3orig.by_score(v) for k, v in v3orig.OUTCOME_READING.items()},
    "nearest_neighbor_ignoring_weather": v3orig.by_score(v3orig._neighbour),
    "positive_control_weather_match": v3orig.by_score(v3orig._weather_match),
}


def _cells(
    battery: str, r_list: list[int], arms: tuple[str, ...]
) -> list[tuple[Any, ...]]:
    k = v2sc.FROZEN_K if battery == "v2" else v3sc.FROZEN_K
    return [
        (arm, r, p.probe_id, kk)
        for arm in arms
        for r in r_list
        for p in v2bat.lever_probes()
        for kk in range(k)
    ]


def _choose(battery: str, name: str) -> Callable[[tuple[Any, ...]], str | None]:
    return {p.name: p.choose for p in fxm.policies(battery)}[name]


@pytest.mark.parametrize(
    ("battery", "table", "r_list"),
    [("v2", V2_ORIGINAL, V2_R), ("v3", V3_ORIGINAL, V3_R)],
    ids=["v2", "v3"],
)
def test_ported_policies_match_the_originals_on_stage2_r(
    battery: str, table: dict[str, Callable[..., str]], r_list: list[int]
) -> None:
    names = {p.name for p in fxm.policies(battery)}
    assert set(table) <= names
    cells = _cells(battery, r_list, (*v2bat.LEVER_ARMS, v2bat.ARM_C0))
    for name, orig in table.items():
        mine = _choose(battery, name)
        for key in cells:
            arm, r, pid, k = key
            assert mine(key) == orig(arm, r, _PROBES[pid], k), (name, key)


def test_every_registered_policy_has_an_original_or_a_definition() -> None:
    """原本の無い方策は v2 の label_prior だけ (DD-10)."""
    v2 = {p.name for p in fxm.policies("v2")}
    assert v2 - set(V2_ORIGINAL) == {"label_prior[asc]", "label_prior[desc]"}
    assert {p.name for p in fxm.policies("v3")} == set(V3_ORIGINAL)


@pytest.mark.parametrize(
    ("battery", "a", "b"),
    [
        ("v3", "first_success", "last_success"),
        ("v3", "before_success", "after_success"),
        ("v3", "success_count", "nearest_neighbor_ignoring_weather"),
        ("v3", "outcome_blind/priming", "outcome_blind/recency"),
        ("v2", "uniform_null", "label_prior[asc]"),
        ("v2", "label_prior[asc]", "label_prior[desc]"),
        ("v2", "priming", "recency_last_entry"),
        ("v2", "position", "uniform_null"),
    ],
)
def test_compared_policies_choose_different_labels_on_stage2_r(
    battery: str, a: str, b: str
) -> None:
    r_list = V2_R if battery == "v2" else V3_R
    cells = _cells(battery, r_list, v2bat.LEVER_ARMS)
    ca, cb = _choose(battery, a), _choose(battery, b)
    assert any(ca(k) != cb(k) for k in cells)


def test_label_prior_prefers_a_fixed_label() -> None:
    asc = _choose("v2", "label_prior[asc]")
    top = sorted(v2bat.ACTIONS)
    for key in _cells("v2", V2_R[:4], v2bat.LEVER_ARMS):
        opts = v2bat.layout(key[1]).option_order[key[2]]
        assert asc(key) == next(x for x in top if x in opts)


# ------------------------------------------------------------ 凍結の R の値の再現


def _c(battery: str, r_list: list[int]) -> dict[str, float]:
    return {
        p.name: fxm.policy_c(battery, p.choose, r_list) for p in fxm.policies(battery)
    }


def test_v2_reproduces_the_frozen_table() -> None:
    c = _c("v2", list(range(v2sc.FROZEN_R)))
    assert c.pop("positive_control_rule_lookup") == pytest.approx(1.0)
    assert all(abs(v) < 1e-12 for v in c.values())


def test_v3_reproduces_pinned_c() -> None:
    c = _c("v3", list(range(v3sc.FROZEN_R)))
    for name, want in v3orig.PINNED_C.items():
        assert c[name] == pytest.approx(want, abs=1e-12)
    assert c["nearest_neighbor_ignoring_weather"] == pytest.approx(-1.0)
    assert c["positive_control_weather_match"] == pytest.approx(1.0)
    for name in v3orig.OUTCOME_BLIND:
        assert c[f"outcome_blind/{name}"] == 0.0


def test_o_time_matches_the_frozen_policy_c() -> None:
    r_count = 6
    frozen = {n: f for n, (_, f) in ofx.registered_policies().items()}
    frozen.update(ofx.positive_controls())
    mine = _c("O_time", list(range(r_count)))
    assert set(mine) == set(frozen)
    for name, f in frozen.items():
        assert mine[name] == pytest.approx(ofx.policy_c(f, r_count)["C"], abs=1e-12)


def test_g_matches_the_frozen_policy_c() -> None:
    r_count = 3
    frozen = {n: f for n, (_, f) in gfx.registered_policies().items()}
    frozen.update(gfx.positive_controls())
    mine = _c("G", list(range(r_count)))
    assert set(mine) == set(frozen)
    for name, f in frozen.items():
        assert mine[name] == pytest.approx(gfx.policy_c(f, r_count), abs=1e-12)


# ------------------------------------------------------------ 段 2 の実 r


def test_controls_and_signs_on_stage2_r() -> None:
    v2 = _c("v2", V2_R)
    assert v2["positive_control_rule_lookup"] == pytest.approx(1.0)
    v3 = _c("v3", V3_R)
    assert v3["positive_control_weather_match"] == pytest.approx(1.0)
    assert v3["nearest_neighbor_ignoring_weather"] == pytest.approx(-1.0)
    assert v3["before_success"] > 0 > v3["after_success"]
    o_r = list(range(rd.MAIN_R0["O_time"], rd.MAIN_R0["O_time"] + 138))
    o = _c("O_time", o_r)
    assert o["follow_newer"] == pytest.approx(1.0)
    assert o["follow_older"] == pytest.approx(-1.0)
    g_r = list(range(rd.MAIN_R0["G"], rd.MAIN_R0["G"] + 6))
    g = {
        p.name: fxm.policy_c("G", p.choose, g_r)
        for p in fxm.policies("G")
        if p.positive_control
    }
    assert g["oracle_latent"] == pytest.approx(1.0)


def test_policy_units_use_the_scorer_units() -> None:
    r_list = V3_R[:8]
    choose = _choose("v3", "nearest_neighbor_ignoring_weather")
    u = fxm.policy_units("v3", choose, r_list)
    assert u.shape == (len(r_list) * un.UNITS_PER_REP["v3"],)
    assert np.all(u == -1.0)


# ------------------------------------------------------------ 対・出力


def test_pairs_and_over_delta_min() -> None:
    cs = {"a": 0.3, "b": 0.0, "c": 0.15, "pc": 1.0}
    del cs["pc"]
    assert fxm.pairs(cs) == [
        {"a": "a", "b": "b", "diff": 0.3},
        {"a": "a", "b": "c", "diff": 0.15},
        {"a": "b", "b": "c", "diff": -0.15},
    ]
    assert fxm.over_delta_min(cs) == [
        {"high": "a", "low": "b", "diff": 0.3},
        {"high": "a", "low": "c", "diff": 0.15},
        {"high": "c", "low": "b", "diff": 0.15},
    ]
    assert fxm.over_delta_min({"a": 0.1, "b": 0.0}) == []  # ちょうど Δ_min は超えない


@pytest.fixture(scope="module")
def real_diffs() -> dict[str, Any]:
    return json.loads(fxm.compute_text(fxm.GATE_JSON))


def test_real_gate_diffs(real_diffs: dict[str, Any]) -> None:
    b = real_diffs["batteries"]
    assert b["G"] == {"status": fxm.NOT_SELECTED, "gate": st.GATE_STOP_POWER}
    assert (b["v2"]["R"], b["v3"]["R"], b["O_time"]["R"]) == (32, 80, 138)
    assert b["v2"]["nuisance_pairs_over_delta_min"] == []
    assert b["O_time"]["nuisance_pairs_over_delta_min"] == []
    over = b["v3"]["nuisance_pairs_over_delta_min"]
    lows = {q["low"] for q in over}
    assert "nearest_neighbor_ignoring_weather" in lows
    assert {"high": "before_success", "low": "after_success"} in [
        {"high": q["high"], "low": q["low"]} for q in over
    ]
    # 陽性対照は対に入らない
    pcs = {n for n, v in b["v3"]["policies"].items() if v["positive_control"]}
    assert not any(q["a"] in pcs or q["b"] in pcs for q in b["v3"]["nuisance_pairs"])
    n = len(b["v3"]["policies"]) - len(pcs)
    assert len(b["v3"]["nuisance_pairs"]) == n * (n - 1) // 2


def test_cli_writes_once_and_checks(tmp_path: pathlib.Path) -> None:
    out = tmp_path / "fdm.json"
    assert fxm.main(["--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == fxm.compute_text(fxm.GATE_JSON)
    assert fxm.main(["--out", str(out)]) == 2
    assert fxm.main(["--out", str(out), "--check"]) == 0
    out.write_bytes(out.read_bytes() + b" ")
    assert fxm.main(["--out", str(out), "--check"]) == 3
