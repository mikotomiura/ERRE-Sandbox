"""登録 nuisance 方策 (prereg v3 §2.5、scoping DE-3 / DE-9) を合成 fixture で pin する.

* outcome-blind 方策 (成否欄を読まない) は、族内 2 状態が成否欄以外 byte 一致し
decoding seed を共有する
  ので、**各単位で d が厳密に 0** になる (定理の射程)。
* 成否を読むが weather と結び付けない方策は定理の範囲外。ここで個別に C を計算して pin
する
  (偽 PASS を作るものが無いこと)。近傍方策は C = −1 (保守側)。
* 陽性対照: weather が一致する成功行の label → C = 1。

方策は表示された選択肢 Ω_q の中から決定的に選ぶ。同点は表示順 (outcome-blind) で破る。
"""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import TYPE_CHECKING

import numpy as np
import pytest
from scripts import skill_experience_battery as bat
from scripts import skill_experience_scorer as sc
from scripts import skill_lever_battery as v2
from scripts.stage_b_scorer import VERDICT_ABSENT, VERDICT_PASS

from tests.test_skill_experience.test_scorer import build, cert, run  # noqa: F401

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    Score = Callable[[list[bat.Row], v2.LeverProbe, str], float]


def _options(r: int, p: v2.LeverProbe) -> tuple[str, ...]:
    return v2.layout(r).option_order[p.probe_id]


def by_score(score: Score) -> Callable[[str, int, v2.LeverProbe, int], str]:
    """選択肢ごとの score の最大 (同点は表示順)。C0 は表示先頭。"""

    def policy(arm: str, r: int, p: v2.LeverProbe, _k: int) -> str:
        opts = _options(r, p)
        if arm == bat.ARM_C0:
            return opts[0]
        rows = bat.state_rows(arm, v2.layout(r))
        best = max(range(len(opts)), key=lambda i: (score(rows, p, opts[i]), -i))
        return opts[best]

    return policy


def _succ(rows: list[bat.Row]) -> list[bat.Row]:
    return [x for x in rows if x.success]


def _count(labels: list[str], opt: str) -> float:
    return float(Counter(labels)[opt])


def _rate(rows: list[bat.Row], _p: v2.LeverProbe, o: str) -> float:
    ts = [x for x in rows if x.action == o]
    return sum(x.success for x in ts) / len(ts) if ts else -1.0


def _first(rows: list[bat.Row], _p: v2.LeverProbe, o: str) -> float:
    s = [x.action for x in _succ(rows)]
    return -s.index(o) if o in s else -1e9


def _last(rows: list[bat.Row], _p: v2.LeverProbe, o: str) -> float:
    s = [x.action for x in _succ(rows)]
    return max(i for i, a in enumerate(s) if a == o) if o in s else -1e9


def _adjacent(offset: int) -> Score:
    def score(rows: list[bat.Row], _p: v2.LeverProbe, o: str) -> float:
        labels = [
            rows[i + offset].action
            for i, x in enumerate(rows)
            if x.success and 0 <= i + offset < len(rows)
        ]
        return _count(labels, o)

    return score


def _neighbour(rows: list[bat.Row], p: v2.LeverProbe, o: str) -> float:
    """weather を無視し、時刻・同伴が probe と一致する signature の成功行."""
    labels = [x.action for x in _succ(rows) if x.signature[1:] == p.signature[1:]]
    return _count(labels, o)


def _weather_match(rows: list[bat.Row], p: v2.LeverProbe, o: str) -> float:
    """陽性対照: weather が probe と一致する成功行 (= 成否集計が示す規則)."""
    labels = [x.action for x in _succ(rows) if x.signature[0] == p.signature[0]]
    return _count(labels, o)


OUTCOME_READING: dict[str, Score] = {
    "success_count": lambda rows, _p, o: _count([x.action for x in _succ(rows)], o),
    "fewest_failures": lambda rows, _p, o: (
        -_count([x.action for x in rows if not x.success], o)
    ),
    "success_rate": _rate,
    "first_success": _first,
    "last_success": _last,
    "after_success": _adjacent(1),
    "before_success": _adjacent(-1),
}

# 凍結 R で計算した C (DE-9 の転記値を信用せず、ここで pin する)。直前・直後の行は、
# 同点を表示順で破る
# この定義で ±1/12 (DE-9 の |C| ≤ 0.004 は Ω 外を除いた分布という別定義)。いずれも τ
# から遠い。
PINNED_C: dict[str, float] = {
    "success_count": 0.0,
    "fewest_failures": 0.0,
    "success_rate": 0.0,
    "first_success": 0.0,
    "last_success": 0.0,
    "after_success": -1.0 / 12.0,
    "before_success": 1.0 / 12.0,
}


def _units(samples: list[sc.Sample], arms: tuple[str, ...]) -> np.ndarray:
    choices: dict[tuple[str, int, str], list[str | None]] = {}
    for s in samples:
        choices.setdefault((s.arm, s.replicate, s.probe_id), []).append(s.parsed)
    from scripts.skill_lever_scorer import family_units

    return family_units(sc.component_scores(choices, arms, sc.FROZEN_R))


# ---- outcome-blind: 各単位で厳密に 0 (定理)


def _masked_prompt(arm: str, r: int, p: v2.LeverProbe) -> str:
    return bat.mask_outcomes(bat.render_messages(arm, p, v2.layout(r))[1]["content"])


def _hash_policy(salt: str) -> Callable[[str, int, v2.LeverProbe, int], str]:
    """成否欄を消した prompt と seed だけの任意関数 (outcome-blind の一般形)."""

    def policy(arm: str, r: int, p: v2.LeverProbe, k: int) -> str:
        opts = _options(r, p)
        if arm == bat.ARM_C0:
            return opts[0]
        h = hashlib.sha256(f"{salt}|{k}|{_masked_prompt(arm, r, p)}".encode()).digest()
        return opts[h[0] % len(opts)]

    return policy


def _priming(arm: str, r: int, p: v2.LeverProbe, _k: int) -> str:
    opts = _options(r, p)
    if arm == bat.ARM_C0:
        return opts[0]
    labels = [x.action for x in bat.state_rows(arm, v2.layout(r))]
    return max(opts, key=lambda o: (labels.count(o), -opts.index(o)))


def _recency(arm: str, r: int, p: v2.LeverProbe, _k: int) -> str:
    opts = _options(r, p)
    if arm == bat.ARM_C0:
        return opts[0]
    labels = [x.action for x in bat.state_rows(arm, v2.layout(r)) if x.action in opts]
    return labels[-1] if labels else opts[0]


def _first_row(arm: str, r: int, p: v2.LeverProbe, _k: int) -> str:
    opts = _options(r, p)
    if arm == bat.ARM_C0:
        return opts[0]
    labels = [x.action for x in bat.state_rows(arm, v2.layout(r)) if x.action in opts]
    return labels[0] if labels else opts[0]


OUTCOME_BLIND = {
    "priming": _priming,
    "recency": _recency,
    "first_row": _first_row,
    "position": lambda _a, r, p, _k: _options(r, p)[0],
    "hash_a": _hash_policy("a"),
    "hash_b": _hash_policy("b"),
    "hash_c": _hash_policy("c"),
}


@pytest.mark.parametrize("name", sorted(OUTCOME_BLIND))
def test_outcome_blind_policy_cancels_in_every_unit(name: str, cert: Path) -> None:  # noqa: F811
    samples = build(OUTCOME_BLIND[name])
    d = _units(samples, bat.JUDGE_ARMS)
    assert np.all(d == 0.0)
    rep = run(samples, cert)
    assert rep["C"] == 0.0
    assert rep["verdict"] == VERDICT_ABSENT


def test_outcome_blind_policy_sees_identical_family_prompts() -> None:
    """定理の前提: 族内 2 arm の成否欄を消した prompt が全 r・全 probe で一致する."""
    for r in range(sc.FROZEN_R):
        for p in v2.lever_probes():
            for a, b in bat.JUDGE_FAMILIES:
                assert _masked_prompt(a, r, p) == _masked_prompt(b, r, p)


# ---- 成否を読むが weather と結び付けない方策 (定理の範囲外、個別に pin)


@pytest.mark.parametrize("name", sorted(OUTCOME_READING))
def test_outcome_reading_weather_unbound_policy(name: str, cert: Path) -> None:  # noqa: F811
    rep = run(build(by_score(OUTCOME_READING[name])), cert)
    assert rep["C"] == pytest.approx(PINNED_C[name], abs=1e-12)
    assert abs(rep["C"]) <= sc.TAU / 3
    assert rep["verdict"] == VERDICT_ABSENT


def test_neighbour_policy_is_conservative(cert: Path) -> None:  # noqa: F811
    """時刻・同伴が一致する近傍の成功行は foil を指す → C = −1 (PASS を作れない側)."""
    rep = run(build(by_score(_neighbour)), cert)
    assert rep["C"] == pytest.approx(-1.0)
    assert rep["verdict"] == VERDICT_ABSENT


def test_weather_matched_success_is_the_positive_control(cert: Path) -> None:  # noqa: F811
    rep = run(build(by_score(_weather_match)), cert)
    assert rep["C"] == pytest.approx(1.0)
    assert rep["verdict"] == VERDICT_PASS
    assert rep["control"]["verdict"] == VERDICT_PASS


def test_label_presence_reads_control_but_not_judge(cert: Path) -> None:  # noqa: F811
    """「状態に出た label のうち、選択肢と一致するもの」で選ぶ方策:
    対照 (失敗行は filler) では w と foil の両方が出るので C は規則に届かず、
    判定族では相殺される."""
    rep = run(build(_priming), cert)
    assert rep["C"] == 0.0
    assert rep["control"]["C"] == pytest.approx(0.0, abs=1e-12)
