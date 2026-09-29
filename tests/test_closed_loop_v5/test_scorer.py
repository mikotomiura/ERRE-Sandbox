"""較正 pilot の記録の検証と測定 (pilot prereg §3・§4).

測定量は、方策から答えが決まる合成 run と、手で数えられる最小の場面で pin する。
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from scripts import closed_loop_battery as v4
from scripts import closed_loop_v5_battery as bat
from scripts import closed_loop_v5_pilot_scorer as ps
from scripts.stage_b_battery import ACTIONS

from .conftest import first_option, meta_text, synth, to_lines


def _measure(policy, m: int = 8) -> dict:
    rep = ps.evaluate_records(to_lines(synth(policy)), meta_text())
    assert rep["status"] == ps.STATUS_COMPUTED, rep
    return rep["measures"][str(m)]


def _prev_or_first(memory: dict):
    def policy(key, _st, opts, _text):
        k = (
            key.axis,
            key.world,
            key.replicate,
            v4.loop_signature(key.replicate, key.step),
        )
        choice = memory.get(k, opts[0])
        memory[k] = choice
        return choice

    return policy


# ---------------------------------------------------------------- 検証


def test_complete_run_is_computed() -> None:
    rep = ps.evaluate_records(to_lines(synth(first_option)), meta_text())
    assert rep["status"] == ps.STATUS_COMPUTED
    assert set(rep["measures"]) == {"4", "6", "8"}
    assert set(rep["measures"]["4"]) == set(bat.AXES)


def test_incomplete_and_transport_failure_are_not_computed() -> None:
    recs = synth(first_option, stop_after=100)
    rep = ps.evaluate_records(to_lines(recs), meta_text())
    assert (rep["status"], rep["reasons"]) == (ps.STATUS_NOT_COMPUTED, ["incomplete"])
    assert "measures" not in rep
    failed = [*recs[:-1], replace(recs[-1], raw=None, parsed=None)]
    rep = ps.evaluate_records(to_lines(failed), meta_text())
    assert (rep["status"], rep["reasons"]) == (
        ps.STATUS_NOT_COMPUTED,
        ["transport_failure"],
    )


def test_records_after_transport_failure_are_invalid() -> None:
    recs = synth(first_option, stop_after=10)
    recs[5] = replace(recs[5], raw=None, parsed=None)
    rep = ps.evaluate_records(to_lines(recs), meta_text())
    assert rep["status"] == ps.STATUS_INVALID


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda r: [r[1], r[0], *r[2:]], "schedule"),
        (lambda r: [replace(r[0], seed=r[0].seed + 1), *r[1:]], "schedule"),
        (
            lambda r: [replace(r[0], axis="C" if r[0].axis == "B" else "B"), *r[1:]],
            "schedule",
        ),
        (
            lambda r: [
                replace(
                    r[0],
                    parsed="read_book" if r[0].parsed != "read_book" else "walk_path",
                ),
                *r[1:],
            ],
            "parse",
        ),
        (lambda r: [replace(r[0], prompt_sha256="0" * 64), *r[1:]], "chain_replay"),
    ],
)
def test_invalid_records(mutate, reason: str) -> None:
    recs = mutate(synth(first_option, stop_after=40))
    rep = ps.evaluate_records(to_lines(recs), meta_text())
    assert (rep["status"], rep["reasons"]) == (ps.STATUS_INVALID, [reason])


def test_chain_replay_catches_forged_choice() -> None:
    """記録の行動を (raw と parsed を揃えて) 書き換えると、後続の prompt
    が連鎖と合わない.
    """
    recs = synth(first_option)
    i = next(
        n
        for n, r in enumerate(recs)
        if r.parsed == v4.rule(r.world)[v4.loop_signature(r.replicate, r.step)[0]]
    )
    other = next(
        a
        for a in bat.dev_options(recs[i].axis, recs[i].replicate, recs[i].step)
        if a != recs[i].parsed
    )
    recs[i] = replace(recs[i], raw=other, parsed=other)
    assert ps.chain_violations(recs)


def test_record_schema_and_meta() -> None:
    lines = to_lines(synth(first_option, stop_after=3))
    bad = json.loads(lines[0])
    bad["step"] = "0"
    rep = ps.evaluate_records([json.dumps(bad), *lines[1:]], meta_text())
    assert rep["reasons"] == ["record_schema"]
    extra = json.loads(lines[0])
    extra["phase"] = "loop"
    assert ps.evaluate_records([json.dumps(extra)], meta_text())["reasons"] == [
        "record_schema"
    ]
    meta = json.loads(meta_text())
    meta["temperature"] = 0.8
    rep = ps.evaluate_records(lines, json.dumps(meta))
    assert rep["reasons"] == ["request_meta_mismatch"]
    assert ps.evaluate_records(lines, "[]")["reasons"] == ["record_schema"]


# ---------------------------------------------------------------- 測定


def test_wilson_known_values() -> None:
    lo, hi = ps.wilson(5, 10)
    assert (round(lo, 4), round(hi, 4)) == (0.2366, 0.7634)
    assert ps.wilson(0, 0) == (0.0, 1.0)
    assert round(ps.wilson(0, 16)[1], 4) == 0.1936


def test_tally_collapses_duplicates_and_takes_outer_bound() -> None:
    t = ps.Tally()
    rec = synth(first_option, stop_after=1)[0]
    t.add(rec, hit=True)
    t.add(rec, hit=False)
    assert (t.k, t.n) == (1, 1)
    # 1 cluster に 30 件 (全て 1)・呼び出し単位の上限は cluster 単位より狭い → 外側 =
    # cluster 単位
    t = ps.Tally()
    for i in range(30):
        t.add(replace(rec, prompt_sha256=f"{i:064d}"), hit=i < 15)
    lo, hi = t.bounds()
    assert (lo, hi) == (
        min(ps.wilson(15, 30)[0], ps.wilson(0.5, 1)[0]),
        max(ps.wilson(15, 30)[1], ps.wilson(0.5, 1)[1]),
    )


def test_first_option_policy() -> None:
    """表示先頭: B は周ごとに回転が変わるので再訪で前回と一致しない。C
    は回転が周で不変なので常に同じ.
    """
    m4 = _measure(first_option, 4)
    assert m4["B"]["s_changed"]["rate"] == 0.0
    assert m4["B"]["s_changed"]["n"] > 0
    assert m4["B"]["s_same"]["n"] == 0  # 4 周以内に回転の位相は戻らない
    assert m4["C"]["eps"]["rate"] == 0.0
    assert m4["C"]["s_same"]["rate"] == 1.0


def test_b_phase_return_is_same_prompt() -> None:
    """成功しない方策 (表示順で最初の規則でない label) では、B の 5 周目の prompt は 1
    周目と同一 (位相が戻る).
    """

    def never_succeed(key, _st, opts, _text):
        rule = v4.rule(key.world)[v4.loop_signature(key.replicate, key.step)[0]]
        return next(o for o in opts if o != rule)

    m4 = _measure(never_succeed, 4)
    assert m4["B"]["s_same"]["n"] == 0
    m8 = _measure(never_succeed, 8)
    assert m8["B"]["s_same"]["n"] > 0
    assert m8["B"]["s_same"]["rate"] == 1.0


def test_repeat_previous_policy() -> None:
    m = _measure(_prev_or_first({}), 8)
    assert m["B"]["s_changed"]["rate"] == 1.0
    assert m["C"]["eps"]["rate"] == 0.0
    assert m["C"]["rho"]["rate"] == 1.0


def test_explore_policy_sets_eps_one() -> None:
    def policy(key, st, opts, _text):
        sig = v4.loop_signature(key.replicate, key.step)
        untried = [o for o in opts if (sig, o) not in st.tried]
        return untried[0] if untried else opts[0]

    m = _measure(policy, 6)
    assert m["C"]["eps"]["rate"] == 1.0
    assert m["C"]["eps"]["lo"] < 1.0


def test_lambda_and_base() -> None:
    """同 weather の成功行があれば規則 (h_sw = 1)、無ければ表示先頭 (h0 < 1) → λ̂ = 1."""

    def policy(key, st, opts, _text):
        sig = v4.loop_signature(key.replicate, key.step)
        if any(s[0] == sig[0] for s in st.succeeded):
            return v4.rule(key.world)[sig[0]]
        return opts[0]

    m = _measure(policy, 4)
    for axis in bat.AXES:
        assert m[axis]["h_sw"]["rate"] == 1.0
        assert m[axis]["h0"]["rate"] < 1.0
        assert m[axis]["lam_dev"] == 1.0
        for wt, probs in m[axis]["base"].items():
            assert sum(probs.values()) == pytest.approx(1.0)
            assert list(probs) == list(v4.dev_omega(wt))


def test_base_counts_first_visits_without_same_weather_rows_once_per_prompt() -> None:
    """t = 0 は 4 世界の prompt が同一 (空状態・共有 seed) なので、base の数え上げは r
    ごとに 1 件.
    """
    recs = synth(first_option)
    c = ps.count_axis(recs, "B", 1)
    assert sum(sum(v.values()) for v in c.base.values()) == len(bat.PILOT_R)
    assert c.h0.n == len(bat.PILOT_R)
    assert sum(t.n for t in c.bottom.values()) == len(bat.PILOT_R) * len(v4.WORLDS)


def test_bottom_gate_boundary() -> None:
    """世界 A だけ t % 5 == 0 で ⊥: M = 4 の窓で 10/48 = 0.208 > 0.2 → 不採用。t % 6 ==
    0 なら 8/48 → 採用.
    """

    def make(mod: int):
        def policy(key, _st, opts, _text):
            if key.world == v4.WORLDS[0] and key.step % mod == 0:
                return "わからない"
            return opts[0]

        return policy

    m = _measure(make(5), 4)
    assert m["B"]["world_bottom_rates"][v4.WORLDS[0]] == pytest.approx(10 / 48)
    assert m["B"]["rejected_bottom"]
    assert m["C"]["rejected_bottom"]
    m = _measure(make(6), 4)
    assert m["B"]["world_bottom_rates"][v4.WORLDS[0]] == pytest.approx(8 / 48)
    assert not m["B"]["rejected_bottom"]
    assert m["B"]["bottom_hi"] == pytest.approx(ps.wilson(32, 192)[1])


def test_oov_rate() -> None:
    """表示に無い語彙内の label は Ω 外 (世界別の上限の最大).

    表示中から選ぶ方策では 0 件。
    """

    def policy(key, _st, opts, _text):
        if key.step % 4 == 0:
            return next(a for a in ACTIONS if a not in opts)
        return opts[0]

    m = _measure(policy, 4)
    for axis in bat.AXES:
        rate = m[axis]["world_oov"][v4.WORLDS[0]]["rate"]
        assert 0.1 < rate < 0.5
        assert m[axis]["oov_hi"] > rate
    m0 = _measure(first_option, 4)
    for axis in bat.AXES:
        x = m0[axis]["world_oov"][v4.WORLDS[0]]
        assert x["rate"] == 0.0
        assert m0[axis]["oov_hi"] == pytest.approx(ps.wilson(0, x["n"])[1])


def test_windows_restrict_steps() -> None:
    m = ps.measure(synth(first_option))
    n4 = m["4"]["B"]["world_bottom"][v4.WORLDS[0]]["n"]
    n8 = m["8"]["B"]["world_bottom"][v4.WORLDS[0]]["n"]
    assert (n4, n8) == (48 * len(bat.PILOT_R), 96 * len(bat.PILOT_R))


def test_duplicate_representative_is_first_call() -> None:
    """同じ prompt・seed の重複 (t = 0 の 4 世界) で応答が違うとき、代表は call_index
    の最初の 1 件.
    """

    def by_world(key, _st, opts, _text):
        if key.step == 0:
            return opts[v4.WORLDS.index(key.world)]
        return opts[0]

    recs = synth(by_world)
    c = ps.count_axis(recs, "B", 1)
    want: dict[str, dict[str, int]] = {}
    for r in bat.PILOT_R:
        w0 = v4.world_order(r)[0]
        opts = bat.dev_options("B", r, 0)
        label = opts[v4.WORLDS.index(w0)]
        weather = v4.loop_signature(r, 0)[0]
        want.setdefault(weather, {})
        want[weather][label] = want[weather].get(label, 0) + 1
    got = {wt: {a: n for a, n in v.items() if n} for wt, v in c.base.items()}
    assert {wt: v for wt, v in got.items() if v} == want


def test_base_smoothing() -> None:
    c = ps.AxisCounts()
    wt = "rain"
    om = v4.dev_omega(wt)
    c.base[wt][om[0]] = 3
    probs = ps.base_probs(c)
    assert probs[wt][om[0]] == pytest.approx(3.5 / 5.0)
    assert probs[wt][om[1]] == pytest.approx(0.5 / 5.0)
    assert probs["clear"][v4.dev_omega("clear")[0]] == pytest.approx(0.25)


def test_same_prompt_with_oov_response_falls_to_changed() -> None:
    """B で 1 周目に Ω 外、以後は表示中の固定の誤答.

    5 周目 (1 周目と同一 prompt) は模擬と同じく prompt 変化に数える。
    """

    def policy(key, _st, opts, _text):
        weather = v4.loop_signature(key.replicate, key.step)[0]
        if key.step < 12:
            return next(a for a in ACTIONS if a not in opts)
        rule = v4.rule(key.world)[weather]
        return next(o for o in v4.dev_omega(weather) if o != rule)

    m = ps.measure(synth(policy))
    n4, n5, n6 = (m[k]["B"]["s_changed"]["n"] for k in ("4", "6", "8"))
    assert m["8"]["B"]["s_changed"]["rate"] == 1.0
    assert n5 > n4  # 5 周目 (t 48..59) の訪問が prompt 変化に入る
    assert m["6"]["B"]["s_same"]["n"] > 0  # 6 周目は 2 周目と同一 prompt・応答は表示中
    assert n6 >= n5
