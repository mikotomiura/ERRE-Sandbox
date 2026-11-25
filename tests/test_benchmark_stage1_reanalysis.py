"""判別性 gate 段 1 の再解析 script の部品の test (実データの集計値は見ない)."""

from __future__ import annotations

import json
from collections import Counter
from typing import TYPE_CHECKING

import numpy as np
import pytest
from scripts import benchmark_stage1_reanalysis as s1
from scripts import o_time_probe_battery as obat
from scripts import o_time_probe_fixtures as ofx
from scripts import o_time_probe_scorer as osc

if TYPE_CHECKING:
    from pathlib import Path


def test_jsonl_lines_does_not_split_on_line_separators() -> None:
    sep = chr(0x2028) + chr(0x2029) + chr(0x85)
    text = '{"raw": "a' + sep + 'b"}\n{"raw": "c"}\n'
    lines = s1.jsonl_lines(text)
    assert len(lines) == 2
    assert sep in lines[0]


def test_verify_inputs_stops_on_mismatch(tmp_path: Path) -> None:
    (tmp_path / "a.jsonl").write_bytes(b"x\n")
    good = s1.sha256_file(tmp_path / "a.jsonl")
    assert s1.verify_inputs(tmp_path, {"a": ("a.jsonl", good)}) == {"a": good}
    with pytest.raises(s1.InputError):
        s1.verify_inputs(tmp_path, {"a": ("a.jsonl", "0" * 64)})
    with pytest.raises(s1.InputError):
        s1.verify_inputs(tmp_path, {"b": ("missing.jsonl", good)})


@pytest.mark.parametrize(
    ("p", "df", "want"),
    [
        (0.05, 3, 0.351846),
        (0.05, 7, 2.167350),
        (0.05, 17, 8.671760),
        (0.95, 10, 18.307038),
        (0.05, 100, 77.929465),
    ],
)
def test_chi2_ppf_matches_table(p: float, df: int, want: float) -> None:
    assert s1.chi2_ppf(p, df) == pytest.approx(want, abs=1e-5)


def test_r_needed_floor_and_formula() -> None:
    assert s1.r_needed(0.0, 0.15) == s1.R_FLOOR
    z = s1.z_sum()
    assert s1.r_needed(0.5, 0.1) == int(np.ceil(2 * 0.25 * z**2 / 0.01))


def test_noise_is_replicate_clustered() -> None:
    rep = np.array([[0.0, 1.0], [1.0, 1.0], [0.5, 0.5]])
    nz = s1.noise(rep)
    m = rep.mean(axis=1)
    assert nz["C"] == pytest.approx(m.mean())
    assert nz["sigma_rep"] == pytest.approx(m.std(ddof=1))
    assert nz["sigma_up"] > nz["sigma_rep"]


def test_o_time_bigger_digit_policy_cancels_only_when_pair_completed() -> None:
    """札の数が大きい行を選ぶ方策.

    書き方別の C は ±1、対を完成させた D は 0 (Codex r1 MEDIUM-1).
    """
    r_count = 6
    policy = ofx.digit_rank("max")
    choices: dict[tuple[str, str, int, int], list[str | None]] = {}
    for u in obat.units(r_count):
        for arm, enc in obat.unit_calls(u):
            choices[(arm, enc, u.room, u.replicate)] = [
                policy(ofx.context(arm, enc, u))
            ]
    d, cells = s1.o_time_units(choices, r_count)
    assert np.all(np.abs(d) < 1e-12)
    desc = osc.describe(choices, cells, r_count)
    assert sorted([desc["C_asc"], desc["C_ago"]]) == pytest.approx([-1.0, 1.0])


def _row(c: float, se: float, seconds: int, q: float = 1.0, bot: float = 0.0) -> dict:
    return {
        "noise": {"C": c, "se": se},
        "output_classes": {"q": q, "max_bot_rate": bot},
        "r_table": {f"{s1.DELTA_REF:.2f}": {"seconds_exact": [seconds, 1]}},
    }


H = 3600


def test_decide_rules_in_order() -> None:
    rows = {
        "ceil": _row(0.9, 0.03, H // 10),
        "lowq": _row(0.2, 0.01, H // 10, q=0.4),
        "bot": _row(0.2, 0.01, H // 10, bot=0.25),
        "both": _row(0.99, 0.01, H // 10, q=0.4),
        "cheap": _row(0.1, 0.01, H),
        "mid": _row(0.1, 0.01, 3 * H // 2),
        "dear": _row(0.1, 0.01, 2 * H),
    }
    out = s1.decide(rows)
    assert out["ceil"] == {"decision": s1.DECISION_HOLD, "reason": "ceiling"}
    assert out["lowq"]["reason"] == "validity"
    assert out["bot"]["reason"] == "validity"
    assert out["both"]["reason"] == "validity"  # validity が先
    assert out["cheap"]["decision"] == s1.DECISION_ADOPT
    assert out["mid"]["decision"] == s1.DECISION_ADOPT
    assert out["mid"]["cumulative_hours_8b"] == pytest.approx(2.5)
    assert out["dear"] == {
        "decision": s1.DECISION_HOLD,
        "reason": "cost",
        "cumulative_hours_8b_if_added": pytest.approx(4.5),
    }


def test_decide_boundaries() -> None:
    """⊥ = 0.2・q = 0.5 は通り、天井の上端 = 0.95 は保留する."""
    out = s1.decide(
        {
            "b": _row(0.1, 0.01, 1, bot=0.2),
            "q": _row(0.1, 0.01, 1, q=0.5),
            "c": _row(0.75, 0.1, 1),  # 0.75 + 1.96·0.1 = 0.946 < 0.95
            "d": _row(0.95, 0.0, 1),  # 上端ちょうど 0.95
        }
    )
    assert out["b"]["decision"] == s1.DECISION_ADOPT
    assert out["q"]["decision"] == s1.DECISION_ADOPT
    assert out["c"]["decision"] == s1.DECISION_ADOPT
    assert out["d"] == {"decision": s1.DECISION_HOLD, "reason": "ceiling"}


def test_decide_exact_budget_and_ties() -> None:
    """累計がちょうど 3 時間なら採る。同額は名前順 (Codex HIGH-3)."""
    out = s1.decide(
        {
            "z": _row(0.1, 0.01, H),
            "a": _row(0.1, 0.01, H),
            "m": _row(0.1, 0.01, H),
            "y": _row(0.1, 0.01, 1),
        }
    )
    # 順: y (1 秒) → a → m → z。y + a + m = 2 h + 1 s なので z は超える
    assert out["a"]["decision"] == s1.DECISION_ADOPT
    assert out["m"]["decision"] == s1.DECISION_ADOPT
    assert out["z"]["reason"] == "cost"
    out2 = s1.decide({n: _row(0.1, 0.01, H) for n in ("c", "b", "a")})
    assert all(v["decision"] == s1.DECISION_ADOPT for v in out2.values())
    assert out2["c"]["cumulative_hours_8b"] == 3.0


def test_cost_is_exact_rational() -> None:
    """Codex HIGH-3 の例: 4 battery の R で合計が正確に 10,800 秒."""
    calls = {"v2": (1200, 4), "v3": (2160, 8), "G": (1728, 18), "O_time": (13824, 288)}
    r = {"v2": 44, "v3": 40, "G": 117, "O_time": 156}
    total = sum(s1.cost_seconds(n, r[n], *calls[n]) for n in calls)
    assert total == s1.BUDGET_SECONDS


def test_r_cost_rounds_up_to_position_balance() -> None:
    assert s1.r_cost(2, 4) == 4
    assert s1.r_cost(4, 4) == 4
    assert s1.r_cost(5, 3) == 6
    assert s1.R_MULTIPLE == {"v2": 4, "v3": 4, "G": 3, "O_time": 3}


def test_decide_holds_nan_q_as_invalid() -> None:
    out = s1.decide({"x": _row(0.1, 0.01, 1, q=float("nan"))})
    assert out["x"]["reason"] == "validity"


@pytest.mark.parametrize("field", ["bot", "c", "se"])
def test_decide_stops_on_other_non_finite(field: str) -> None:
    row = _row(0.1, 0.01, 1)
    if field == "bot":
        row["output_classes"]["max_bot_rate"] = float("nan")
    elif field == "c":
        row["noise"]["C"] = float("nan")
    else:
        row["noise"]["se"] = float("inf")
    with pytest.raises(s1.InputError):
        s1.decide({"x": row})


def test_replicates_requires_exact_division() -> None:
    assert s1.replicates(288, 16) == 18
    for bad in (289, 16, 288.0, True):
        with pytest.raises(s1.InputError):
            s1.replicates(bad, 16)


def _o_time_lines(r_count: int) -> tuple[list[str], dict]:
    """部屋と replicate で D が変わる合成の記録 (+1 / −1)."""
    lines, want = [], {}
    n = 0
    for u in obat.units(r_count):
        sign = 1 if (u.room + u.replicate) % 2 == 0 or u.room == 5 else -1
        want[(u.replicate, u.family, u.room)] = float(sign)
        for arm, enc in obat.unit_calls(u):
            w, foil = obat.pointed(arm, u.room)
            pick = w if sign == 1 else foil
            rec = {
                "call_index": n,
                "arm": arm,
                "encoding": enc,
                "replicate": u.replicate,
                "probe_id": osc.probe_id(u.room),
                "k": 0,
                "seed": 0,
                "prompt_sha256": "x",
                "raw": pick,
                "parsed": pick,
            }
            lines.append(json.dumps(rec))
            n += 1
    return lines, want


def test_battery_o_time_units_and_items_follow_room_and_replicate() -> None:
    r_count = 3
    lines, want = _o_time_lines(r_count)
    bd = s1.battery_o_time(lines, r_count)
    units = obat.units(r_count)
    flat = [want[(u.replicate, u.family, u.room)] for u in units]
    assert bd.rep_units.reshape(-1).tolist() == flat
    for i in range(obat.N_ROOMS):
        exp = [
            float(np.mean([want[(r, f, i)] for f in range(2)])) for r in range(r_count)
        ]
        assert bd.items[f"room{i}"] == exp
    assert bd.total_calls == len(lines)


def test_output_classes_q_r() -> None:
    oc = s1.output_classes(
        {"A": Counter(w=6, foil=2, other=1, bot=1), "B": Counter(w=4, foil=4, oov=2)}
    )
    assert oc["q"] == pytest.approx(16 / 20)
    assert oc["r"] == pytest.approx(10 / 16)
    assert oc["per_arm"]["A"]["bot_rate"] == pytest.approx(0.1)
    assert oc["max_bot_rate"] == pytest.approx(0.1)
