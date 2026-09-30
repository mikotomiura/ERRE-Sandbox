"""較正 pilot の記録の検証と測定 (pilot prereg §3・§4).

測定量は、方策から答えが決まる合成 run と、手で数えられる最小の場面で pin する。
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import pytest
from scripts import body_walk_battery as bat
from scripts import body_walk_pilot_scorer as ps
from scripts import closed_loop_battery as v4
from scripts.stage_b_battery import ACTIONS

from .conftest import behaviour, first_option, meta_text, synth, to_lines

N_LOOP = bat.n_loop_calls()


def _report(**kw: Any) -> dict[str, Any]:
    rep = ps.evaluate_records(to_lines(synth(**kw)), meta_text())
    assert rep["status"] == ps.STATUS_COMPUTED, rep
    return rep


def _alternate(*, avoid_rule: bool = False) -> Any:
    """(世界, r, signature) ごとに選択肢を 1 つずつ進める (直前と同じ label を選ばない).

    avoid_rule なら規則を除いた 3 択を巡回する
    (成功が起きず、状態 = prompt が変わらない)。
    """
    count: dict[tuple[str, int, Any], int] = {}

    def policy(key: bat.PilotKey, _st: v4.State, opts: tuple[str, ...]) -> str:
        sig = v4.loop_signature(key.replicate, key.step)
        k = (key.world, key.replicate, sig)
        n = count.get(k, 0)
        count[k] = n + 1
        rule = v4.rule(key.world)[sig[0]]
        pool = [o for o in opts if o != rule] if avoid_rule else list(opts)
        return pool[n % len(pool)]

    return policy


# ---------------------------------------------------------------- 検証


def test_complete_run_is_computed() -> None:
    rep = _report()
    assert set(rep["measures"]) == set(rep["chains"]) == {"4", "6", "8"}
    assert rep["determinism"]["replay_n"] == bat.n_replay_calls()


def test_incomplete_and_transport_failure_are_not_computed() -> None:
    recs = synth(stop_after=100)
    rep = ps.evaluate_records(to_lines(recs), meta_text())
    assert (rep["status"], rep["reasons"]) == (ps.STATUS_NOT_COMPUTED, ["incomplete"])
    assert "measures" not in rep
    failed = [*recs[:-1], replace(recs[-1], raw=None, parsed=None)]
    rep = ps.evaluate_records(to_lines(failed), meta_text())
    assert (rep["status"], rep["reasons"]) == (
        ps.STATUS_NOT_COMPUTED,
        ["transport_failure"],
    )


def test_replay_part_does_not_stop_the_measurement() -> None:
    """replay 部分の欠けや transport 失敗は止めない (決定性の n に出る)."""
    recs = synth()
    cut = ps.evaluate_records(to_lines(recs[: N_LOOP + 5]), meta_text())
    assert cut["status"] == ps.STATUS_COMPUTED
    assert cut["determinism"]["replay_n"] == 5
    failed = [*recs[:-1], replace(recs[-1], raw=None, parsed=None)]
    rep = ps.evaluate_records(to_lines(failed), meta_text())
    assert rep["status"] == ps.STATUS_COMPUTED
    assert rep["determinism"]["replay_n"] == bat.n_replay_calls() - 1


def test_records_after_transport_failure_are_invalid() -> None:
    recs = synth(stop_after=10)
    recs[5] = replace(recs[5], raw=None, parsed=None)
    rep = ps.evaluate_records(to_lines(recs), meta_text())
    assert (rep["status"], rep["reasons"]) == (ps.STATUS_INVALID, ["schedule"])


def _other(parsed: str | None) -> str:
    return "read_book" if parsed != "read_book" else "walk_path"


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda r: [r[1], r[0], *r[2:]], "schedule"),
        (lambda r: [replace(r[0], seed=r[0].seed + 1), *r[1:]], "schedule"),
        (lambda r: [replace(r[0], phase=bat.PHASE_REPLAY), *r[1:]], "schedule"),
        (lambda r: [replace(r[0], world=r[1].world), *r[1:]], "schedule"),
        (lambda r: [replace(r[0], parsed=_other(r[0].parsed)), *r[1:]], "parse"),
        (lambda r: [replace(r[0], prompt_sha256="0" * 64), *r[1:]], "chain_replay"),
        (lambda r: [*r[:-1], replace(r[-1], prompt_sha256="0" * 64)], "chain_replay"),
    ],
)
def test_invalid_records(mutate: Any, reason: str) -> None:
    recs = mutate(synth())
    rep = ps.evaluate_records(to_lines(recs), meta_text())
    assert (rep["status"], rep["reasons"]) == (ps.STATUS_INVALID, [reason])


def test_chain_replay_catches_forged_choice() -> None:
    """記録の行動を書き換えると、後続の prompt が連鎖と合わない.

    raw と parsed は揃えて書き換える。
    """
    recs = synth(policy=first_option)
    i = next(
        n
        for n, r in enumerate(recs)
        if r.parsed == v4.rule(r.world)[v4.loop_signature(r.replicate, r.step)[0]]
    )
    other = next(
        a
        for a in bat.dev_options(recs[i].replicate, recs[i].step)
        if a != recs[i].parsed
    )
    recs[i] = replace(recs[i], raw=other, parsed=other)
    assert ps.chain_violations(recs)


def test_record_schema() -> None:
    lines = to_lines(synth(stop_after=3))
    bad = json.loads(lines[0])
    bad["step"] = "0"
    rep = ps.evaluate_records([json.dumps(bad), *lines[1:]], meta_text())
    assert rep["reasons"] == ["record_schema"]
    extra = json.loads(lines[0])
    extra["axis"] = "W"
    assert ps.evaluate_records([json.dumps(extra)], meta_text())["reasons"] == [
        "record_schema"
    ]
    assert ps.evaluate_records(lines, "[]")["reasons"] == ["record_schema"]
    assert ps.evaluate_records(["{"], meta_text())["reasons"] == ["record_schema"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("temperature", 0.7),
        ("top_p", 0.95),
        ("repeat_penalty", 1.0),
        ("ollama_version", "0.32.13"),
        ("model_digest", "0" * 64),
        ("model_parameters", bat.MODEL_PARAMETERS.replace("20", "40")),
        ("think", True),
        ("think", 0),  # False == 0 を通さない (型まで一致)
        ("num_ctx", 4096.0),
        ("num_predict", 32.0),
    ],
)
def test_meta_mismatch_is_invalid(field: str, value: object) -> None:
    """要求条件と、実行時に観測する環境 (Codex HIGH-1) の一致を要求する."""
    lines = to_lines(synth(stop_after=3))
    meta = json.loads(meta_text())
    meta[field] = value
    rep = ps.evaluate_records(lines, json.dumps(meta))
    assert rep["reasons"] == ["request_meta_mismatch"]
    missing = json.loads(meta_text())
    del missing["model_parameters"]
    assert ps.evaluate_records(lines, json.dumps(missing))["reasons"] == [
        "request_meta_mismatch"
    ]


# ---------------------------------------------------------------- 測定


def test_wilson_and_outer_bounds() -> None:
    lo, hi = ps.wilson(5, 10)
    assert 0.23 < lo < 0.24
    assert 0.76 < hi < 0.77
    assert ps.wilson(0, 0) == (0.0, 1.0)
    t = ps.Tally()
    rec = synth(stop_after=1)[0]
    for n in range(20):
        t.add(replace(rec, world=v4.WORLDS[n % 2]), hit=n % 2 == 0)
    # cluster 単位 (2 cluster: 率 1.0 と 0.0) の区間は呼び出し単位より広い
    lo_a, hi_a = t.call_bounds()
    lo, hi = t.bounds()
    assert (lo, hi) == (
        min(lo_a, ps.wilson(1.0, 2)[0]),
        max(hi_a, ps.wilson(1.0, 2)[1]),
    )
    assert lo < lo_a
    assert hi > hi_a


def test_first_option_repeats_everywhere() -> None:
    """状態を読まず表示先頭を選ぶ方策.

    再訪は、同一 prompt でも prompt 変化でも前回と同じ。
    """
    m = _report(policy=first_option)["measures"]["8"]
    assert m["s_same"]["rate"] == 1.0
    assert m["s_changed"]["rate"] == 1.0
    assert m["s_same"]["n"] > 0
    assert m["s_changed"]["n"] > 0
    assert m["bottom_max"] == 0.0
    assert all(x["k"] == 0 for x in m["world_oov"].values())


def test_alternating_policy_never_repeats() -> None:
    changing = _report(policy=_alternate())["measures"]["8"]
    assert changing["s_changed"]["rate"] == 0.0
    assert changing["s_changed"]["n"] > 0
    # 成功が起きないと prompt は変わらず、再訪は全て同一 prompt になる
    frozen = _report(policy=_alternate(avoid_rule=True))["measures"]["8"]
    assert frozen["s_same"]["rate"] == 0.0
    assert frozen["s_same"]["n"] > 0
    assert frozen["s_changed"]["n"] == 0


def test_same_prompt_is_the_exact_rendered_prompt() -> None:
    """同一 prompt の判定 = 描画 prompt の sha の一致.

    成功が 1 つ増えると prompt 変化に移る。
    """
    recs = synth(policy=first_option)
    c = ps.count_window(recs, bat.N_DEV * 8)
    # 手で数え直す: 未成功・表示中・代表の再訪を、
    # 描画 sha が前の訪問と一致するかで分ける
    seen: dict[tuple[str, int, Any], set[str]] = {}
    rep: dict[tuple[str, int], int] = {}
    for x in recs:
        if x.phase == bat.PHASE_LOOP:
            rep.setdefault((x.prompt_sha256, x.seed), x.call_index)
    same = changed = 0
    states: dict[tuple[str, int], v4.State] = {}
    for x in recs:
        if x.phase != bat.PHASE_LOOP:
            continue
        st = states.get((x.world, x.replicate), v4.EMPTY_STATE)
        sig = v4.loop_signature(x.replicate, x.step)
        k = (x.world, x.replicate, sig)
        counted = rep[(x.prompt_sha256, x.seed)] == x.call_index
        if sig not in st.succeeded and counted and k in seen:
            if x.prompt_sha256 in seen[k]:
                same += 1
            else:
                changed += 1
        seen.setdefault(k, set()).add(x.prompt_sha256)
        states[(x.world, x.replicate)] = v4.update(st, x.world, sig, x.parsed)
    assert (c.s_same.n, c.s_changed.n) == (same, changed)


def test_duplicates_are_collapsed_but_world_rates_are_not() -> None:
    """t = 0 は各 r で 4 世界の prompt と seed が同一.

    挙動率は 1 件に畳み、世界別の ⊥・Ω 外は畳まない。
    """
    c = ps.count_window(synth(policy=first_option), 1)
    assert c.h0.n == len(bat.PILOT_R)
    assert c.h_sw.n == 0
    assert all(x.n == len(bat.PILOT_R) for x in c.bottom.values())
    assert all(x.n == len(bat.PILOT_R) for x in c.oov.values())


def test_denominators_partition_the_counted_visits() -> None:
    recs = synth()
    c = ps.count_window(recs, bat.N_DEV * 8)
    base_n = {next(iter(t.values())).n for t in c.base.values()}
    assert sum(base_n) == c.h0.n
    assert all(len({x.n for x in t.values()}) == 1 for t in c.base.values())
    counted = c.s_same.n + c.s_changed.n + c.h0.n + c.h_sw.n
    rep: dict[tuple[str, int], int] = {}
    for x in recs:
        if x.phase == bat.PHASE_LOOP:
            rep.setdefault((x.prompt_sha256, x.seed), x.call_index)
    states: dict[tuple[str, int], v4.State] = {}
    want = 0
    prev: dict[tuple[str, int, Any], str] = {}
    for x in recs:
        if x.phase != bat.PHASE_LOOP:
            continue
        st = states.get((x.world, x.replicate), v4.EMPTY_STATE)
        sig = v4.loop_signature(x.replicate, x.step)
        opts = bat.dev_options(x.replicate, x.step)
        k = (x.world, x.replicate, sig)
        if (
            sig not in st.succeeded
            and x.parsed in opts
            and rep[(x.prompt_sha256, x.seed)] == x.call_index
            and (k not in prev or prev[k] in opts)
        ):
            want += 1
        if x.parsed is not None:
            prev[k] = x.parsed
        states[(x.world, x.replicate)] = v4.update(st, x.world, sig, x.parsed)
    assert counted == want


def test_base_and_low_prior() -> None:
    m = _report()["measures"]["8"]
    for wt, probs in m["base"].items():
        assert abs(sum(probs.values()) - 1.0) < 1e-12
        low = m["low_prior"][wt]
        assert low["label"] == min(v4.dev_omega(wt), key=lambda a: probs[a])
        assert low["point"] == probs[low["label"]]
        tally = m["base_labels"][wt][low["label"]]
        assert (low["lo"], low["hi"]) == (tally["lo"], tally["hi"])
        assert low["lo"] <= tally["rate"] <= low["hi"]


def test_low_prior_ties_take_the_canonical_order() -> None:
    c = ps.Counts()
    low = ps.low_prior(c)
    for wt, x in low.items():
        assert x["label"] == v4.dev_omega(wt)[0]
        assert x["point"] == 0.25


def test_lam_dev() -> None:
    c = ps.Counts()
    assert ps.lam_dev(c) is None
    rec = synth(stop_after=1)[0]
    for hit in (True, False, False, False):
        c.h0.add(rec, hit)
    for hit in (True, True, True, False):
        c.h_sw.add(rec, hit)
    assert ps.lam_dev(c) == pytest.approx((0.75 - 0.25) / 0.75)
    c.h_sw = ps.Tally()
    c.h_sw.add(rec, hit=False)
    assert ps.lam_dev(c) == 0.0


def _bottom_for(world: str) -> Any:
    def policy(key: bat.PilotKey, _st: v4.State, opts: tuple[str, ...]) -> str | None:
        return None if key.world == world and key.step % 4 == 0 else opts[0]

    return policy


def test_bottom_gate_and_bounds() -> None:
    m = _report(policy=_bottom_for(v4.WORLDS[2]))["measures"]["4"]
    assert m["world_bottom_rates"][v4.WORLDS[2]] == 0.25
    assert m["world_bottom_rates"][v4.WORLDS[0]] == 0.0
    assert m["rejected_bottom"] is True
    assert m["bottom_hi"] == ps.wilson(12 * 12, 48 * 12)[1]


def test_oov_is_counted_per_world() -> None:
    def policy(key: bat.PilotKey, _st: v4.State, opts: tuple[str, ...]) -> str:
        if key.world == v4.WORLDS[1]:
            return next(a for a in ACTIONS if a not in opts)
        return opts[0]

    m = _report(policy=policy)["measures"]["8"]
    assert m["world_oov"][v4.WORLDS[1]]["rate"] == 1.0
    assert m["world_oov"][v4.WORLDS[0]]["rate"] == 0.0
    assert m["oov_hi"] == 1.0


def test_chains_are_the_end_states() -> None:
    recs = synth()
    ch = ps.chains(recs, 4)
    assert ch["steps"] == 48
    assert len(ch["succ"]) == len(bat.PILOT_R)
    for b, r in enumerate(bat.PILOT_R):
        for wi, w in enumerate(v4.WORLDS):
            st = v4.EMPTY_STATE
            n_bot = 0
            for x in recs:
                if (x.phase, x.world, x.replicate) == (
                    bat.PHASE_LOOP,
                    w,
                    r,
                ) and x.step < 48:
                    st = v4.update(st, w, v4.loop_signature(r, x.step), x.parsed)
                    n_bot += x.parsed is None
            assert ch["succ"][b][wi] == [int(s in st.succeeded) for s in ps.DEVS]
            assert ch["bot"][b][wi] == n_bot


def test_chains_count_bottoms() -> None:
    ch = ps.chains(synth(policy=_bottom_for(v4.WORLDS[2])), 4)
    wi = v4.WORLDS.index(v4.WORLDS[2])
    assert all(row[wi] == 12 for row in ch["bot"])
    assert all(row[0] == 0 for row in ch["bot"])


def test_determinism_rates() -> None:
    exact = _report()["determinism"]
    assert exact["in_run_identical_rate"] == 1.0
    assert exact["replay_identical_rate"] == 1.0
    assert exact["exact_cancellation"] is True
    assert exact["in_run_groups"] > 0
    noisy = _report(replay_flip=0.5)["determinism"]
    assert 0.0 < noisy["replay_identical_rate"] < 1.0
    assert noisy["exact_cancellation"] is False


def test_synthetic_behaviour_is_recovered_in_the_conservative_direction() -> None:
    """測った反復率は植えた値以上に出る (写像では保守側).

    記憶のない偶然の一致を含むため。
    """
    m = _report(beh=behaviour(s_same=0.3, s_changed=0.3))["measures"]["8"]
    assert m["s_same"]["rate"] >= 0.3
    assert m["s_changed"]["rate"] >= 0.3
    assert m["s_same"]["hi"] > m["s_same"]["rate"]


def _classify(
    x: ps.Record,
    st: v4.State,
    past: list[tuple[str, str]],
    opts: tuple[str, ...],
) -> tuple[str, bool]:
    """数える訪問 1 件の分類と的中.

    分類は初訪 (h0 / h_sw)・同一 prompt・prompt 変化・対象外 ("")。
    """
    sig = v4.loop_signature(x.replicate, x.step)
    cur = x.parsed
    if not past:
        weather_done = any(s[0] == sig[0] for s in st.succeeded)
        return ("h_sw" if weather_done else "h0"), cur == v4.rule(x.world)[sig[0]]
    same = [c for sha, c in past if sha == x.prompt_sha256]
    if same and same[-1] in opts:
        return "same", cur == same[-1]
    if past[-1][1] in opts:
        return "changed", cur == past[-1][1]
    return "", False


def _recount(recs: list[ps.Record], t_max: int) -> dict[str, tuple[int, int]]:
    """4 つの Tally を scorer と独立に数え直す: 名前 → (n, k).

    Tally は h0・h_sw・同一 prompt・prompt 変化。
    """
    rep: dict[tuple[str, int], int] = {}
    for x in recs:
        if x.phase == bat.PHASE_LOOP and x.step < t_max:
            rep.setdefault((x.prompt_sha256, x.seed), x.call_index)
    out = {name: [0, 0] for name in ("h0", "h_sw", "same", "changed")}
    states: dict[tuple[str, int], v4.State] = {}
    history: dict[tuple[str, int, Any], list[tuple[str, str]]] = {}
    for x in recs:
        if x.phase != bat.PHASE_LOOP or x.step >= t_max:
            continue
        st = states.get((x.world, x.replicate), v4.EMPTY_STATE)
        sig = v4.loop_signature(x.replicate, x.step)
        opts = bat.dev_options(x.replicate, x.step)
        k = (x.world, x.replicate, sig)
        past = history.get(k, [])
        cur = x.parsed
        if (
            sig not in st.succeeded
            and cur in opts
            and rep[(x.prompt_sha256, x.seed)] == x.call_index
        ):
            name, hit = _classify(x, st, past, opts)
            if name:
                out[name][0] += 1
                out[name][1] += int(hit)
        if cur is not None:
            history.setdefault(k, []).append((x.prompt_sha256, cur))
        states[(x.world, x.replicate)] = v4.update(st, x.world, sig, cur)
    return {name: (n, k) for name, (n, k) in out.items()}


@pytest.mark.parametrize("t_max", [48, 96])
def test_tallies_match_an_independent_recount(t_max: int) -> None:
    recs = synth(beh=behaviour(bot=0.05, oov=0.05))
    c = ps.count_window(recs, t_max)
    got = {
        "h0": (c.h0.n, c.h0.k),
        "h_sw": (c.h_sw.n, c.h_sw.k),
        "same": (c.s_same.n, c.s_same.k),
        "changed": (c.s_changed.n, c.s_changed.k),
    }
    assert got == _recount(recs, t_max)
    assert all(n > 0 for n, _ in got.values())


def test_base_probs_smoothing() -> None:
    c = ps.Counts()
    rec = synth(stop_after=1)[0]
    om = v4.dev_omega("rain")
    for a in (om[0], om[0], om[0], om[1]):
        for label, tally in c.base["rain"].items():
            tally.add(rec, a == label)
    probs = ps.base_probs(c)["rain"]
    assert probs[om[0]] == pytest.approx((3 + 0.5) / (4 + 2))
    assert probs[om[2]] == pytest.approx(0.5 / 6)
    assert ps.low_prior(c)["rain"]["label"] == om[2]
