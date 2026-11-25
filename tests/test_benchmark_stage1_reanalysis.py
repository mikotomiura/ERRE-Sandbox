"""判別性 gate 段 1 の再解析 script の部品の test (実データの集計値は見ない)."""

from __future__ import annotations

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


def _row(c: float, se: float, hours: float, q: float = 1.0, bot: float = 0.0) -> dict:
    return {
        "noise": {"C": c, "se": se},
        "output_classes": {"q": q, "max_bot_rate": bot},
        "r_table": {f"{s1.DELTA_REF:.2f}": {"hours": hours}},
    }


def test_decide_rules_in_order() -> None:
    rows = {
        "ceil": _row(0.9, 0.03, 0.1),
        "lowq": _row(0.2, 0.01, 0.1, q=0.4),
        "bot": _row(0.2, 0.01, 0.1, bot=0.25),
        "cheap": _row(0.1, 0.01, 1.0),
        "mid": _row(0.1, 0.01, 1.5),
        "dear": _row(0.1, 0.01, 2.0),
    }
    out = s1.decide(rows)
    assert out["ceil"] == {"decision": s1.DECISION_HOLD, "reason": "ceiling"}
    assert out["lowq"]["reason"] == "validity"
    assert out["bot"]["reason"] == "validity"
    assert out["cheap"]["decision"] == s1.DECISION_ADOPT
    assert out["mid"]["decision"] == s1.DECISION_ADOPT
    assert out["mid"]["cumulative_hours"] == pytest.approx(2.5)
    assert out["dear"] == {
        "decision": s1.DECISION_HOLD,
        "reason": "cost",
        "cumulative_hours_if_added": pytest.approx(4.5),
    }


def test_decide_holds_nan_q_as_invalid() -> None:
    out = s1.decide({"x": _row(0.1, 0.01, 0.1, q=float("nan"))})
    assert out["x"]["reason"] == "validity"


def test_output_classes_q_r() -> None:
    oc = s1.output_classes(
        {"A": Counter(w=6, foil=2, other=1, bot=1), "B": Counter(w=4, foil=4, oov=2)}
    )
    assert oc["q"] == pytest.approx(16 / 20)
    assert oc["r"] == pytest.approx(10 / 16)
    assert oc["per_arm"]["A"]["bot_rate"] == pytest.approx(0.1)
    assert oc["max_bot_rate"] == pytest.approx(0.1)
