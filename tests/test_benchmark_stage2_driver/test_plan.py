"""段 2 の呼び出しの計画 (``benchmark_stage2_plan``) の test.

- 呼び出しの数 (§G.1・§G-5・§C)、モデル・battery・再生の順 (§H)。
- 呼び出しの順は凍結の driver の順と同じ
  (凍結の r で、凍結の driver の予定表と key の列が一致)。
- seed と prompt は凍結の ``expected_sample`` / ``pg.expected`` と独立に照合する。
- §C の battery 検査は実 r で効く (Codex r1 H3: 本登録の r だけに違反を入れると落ちる)。
"""

from __future__ import annotations

import pytest
from scripts import benchmark_stage2_plan as pl
from scripts import benchmark_stage2_stats as st
from scripts import generalization_probe_battery as gbat
from scripts import generalization_probe_pilot_gate as gpg
from scripts import generalization_probe_scorer as gsc
from scripts import o_time_probe_battery as obat
from scripts import o_time_probe_pilot_gate as opg
from scripts import o_time_probe_scorer as osc
from scripts import skill_experience_battery as v3bat
from scripts import skill_experience_scorer as v3sc
from scripts import skill_lever_battery as v2bat
from scripts import skill_lever_scorer as v2sc

# ------------------------------------------------------------ 数と順


def test_pilot_call_counts_match_registration() -> None:
    counts = {b: len(pl.pilot_calls(b)) for b in st.BATTERIES}
    assert counts == {"v2": 3600, "v3": 3240, "G": 1836, "O_time": 1152}
    assert sum(counts.values()) == 9828


def test_pilot_arm_composition() -> None:
    def by_purpose(b: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for c in pl.pilot_calls(b):
            out[c.purpose] = out.get(c.purpose, 0) + 1
        return out

    assert by_purpose("v2") == {pl.P_C0: 720, pl.P_LEVER: 2880}
    assert by_purpose("v3") == {pl.P_C0: 360, pl.P_LEVER: 1440, pl.P_CONTROL: 1440}
    assert by_purpose("G") == {pl.P_LEVER: 1152, pl.P_MASKED: 576, pl.P_KNOW: 108}
    assert by_purpose("O_time") == {pl.P_LEVER: 576, pl.P_MASKED: 288, pl.P_M0: 288}


@pytest.mark.parametrize(
    ("battery", "per_rep"), [("v2", 300), ("v3", 270), ("G", 96), ("O_time", 48)]
)
def test_main_calls_per_replicate(battery: str, per_rep: int) -> None:
    r = st.SPECS[battery].r_step
    calls = pl.main_calls(battery, r)
    assert len(calls) == per_rep * r
    assert per_rep == st.SPECS[battery].calls_per_rep
    assert {c.replicate for c in calls} == set(pl.main_r(battery, r))


def test_main_calls_reject_registered_r_violations() -> None:
    with pytest.raises(ValueError, match="multiple"):
        pl.main_calls("G", 3)  # 2 巡 (6) の倍数でない
    with pytest.raises(ValueError, match="cap"):
        pl.main_calls("G", 42)  # 名前空間の上限 36


def test_replay_counts_and_seeds_are_the_old_r0() -> None:
    g, o = pl.replay_calls("G"), pl.replay_calls("O_time")
    assert (len(g), len(o)) == (96, 48)
    assert {c.replicate for c in (*g, *o)} == {0}
    for c in g:
        probe = {p.probe_id: p for p in gbat.probes()}[c.probe_id]
        assert (c.seed, pl.messages_sha256(c.messages_list())) == gsc.expected_sample(
            c.arm, 0, probe, 0
        )


def test_pilot_plan_order() -> None:
    segs = pl.pilot_plan()
    names = [(s.stage, s.battery, s.model) for s in segs]
    want = [(pl.STAGE_PILOT, b, m) for m in pl.MODELS for b in st.BATTERIES]
    want += [
        (pl.STAGE_REPLAY, "G", "qwen3:8b"),
        (pl.STAGE_REPLAY, "O_time", "qwen3:8b"),
    ]
    assert names == want
    assert pl.MODELS[:4] == ("qwen3:1.7b", "qwen3:4b-q4_K_M", "qwen3:8b", "qwen3:14b")


def test_main_plan_orders_batteries_by_cost_then_models() -> None:
    r = {"v2": 8, "G": 6, "O_time": 6}
    segs = pl.main_plan(r)
    order = pl.main_order(r)
    cost = {b: r[b] * st.SPECS[b].sec_per_rep() for b in r}
    assert order == sorted(r, key=lambda b: (cost[b], b))
    assert [(s.battery, s.model) for s in segs] == [
        (b, m) for b in order for m in pl.MODELS
    ]


# ---------------------------------------- 凍結の driver と同じ順 (凍結の r で)


def test_v2_order_matches_frozen_driver() -> None:
    from scripts import skill_lever_driver as drv

    keys = [
        (
            c.arm,
            c.replicate,
            [p.probe_id for p in v2bat.lever_probes()].index(c.probe_id),
            c.k,
        )
        for c in pl.v2_calls(range(v2sc.FROZEN_R))
    ]
    assert keys == drv.schedule()


def test_v3_order_matches_frozen_driver() -> None:
    from scripts import skill_experience_driver as drv

    keys = [
        (
            c.arm,
            c.replicate,
            [p.probe_id for p in v2bat.lever_probes()].index(c.probe_id),
            c.k,
        )
        for c in pl.v3_calls(range(v3sc.FROZEN_R))
    ]
    assert keys == drv.schedule()


def test_v2_rotation_phase_is_absolute_in_r() -> None:
    """block の巡回は r から数える.

    段 2 の pilot の始点でも、r を [0, R) に付け替えた凍結の順と同じ位相。
    """
    calls = [c for c in pl.v2_calls(pl.pilot_lever_r("v2")) if c.purpose == pl.P_LEVER]
    first = [c.arm for c in calls[:8]]
    assert first == [*v2bat.LEVER_ARMS, *v2bat.LEVER_ARMS[1:], v2bat.LEVER_ARMS[0]]


def test_g_order_matches_frozen_driver() -> None:
    from scripts import generalization_probe_driver as drv

    main = [
        (c.arm, c.replicate, c.probe_id, c.k)
        for c in pl.g_unit_calls(range(6), masked=False)
    ]
    assert main == list(drv.main_plan(6))
    old_pilot = [
        (c.arm, c.replicate, c.probe_id, c.k)
        for c in (
            *pl.g_know_calls(),
            *pl.g_unit_calls(
                range(gbat.PILOT_R0, gbat.PILOT_R0 + gbat.PILOT_R), masked=True
            ),
        )
    ]
    assert old_pilot == list(drv.pilot_plan())


def test_o_time_order_matches_frozen_driver() -> None:
    from scripts import o_time_probe_driver as drv

    main = [
        (c.arm, c.encoding, c.replicate, c.probe_id, c.k)
        for c in pl.o_lever_calls(range(6))
    ]
    assert main == list(drv.main_plan(6))
    aux = [
        (c.arm, c.encoding, c.replicate, c.probe_id, c.k)
        for c in pl.o_aux_calls(range(obat.PILOT_R0, obat.PILOT_R0 + obat.PILOT_R))
    ]
    assert aux == list(drv.pilot_plan())


# ---------------------------------------- seed と prompt は凍結の expected と一致


def _frozen_expected(c: pl.CallSpec) -> tuple[int, str]:
    qidx = {p.probe_id: i for i, p in enumerate(v2bat.lever_probes())}
    if c.battery == "v2":
        return v2sc.expected_sample(c.arm, c.replicate, qidx[c.probe_id], c.k)
    if c.battery == "v3":
        return v3sc.expected_sample(c.arm, c.replicate, qidx[c.probe_id], c.k)
    if c.battery == "G":
        if c.purpose in (pl.P_MASKED, pl.P_KNOW):
            return gpg.expected(c.arm, c.replicate, c.probe_id, c.k)
        probe = {p.probe_id: p for p in gbat.probes()}[c.probe_id]
        return gsc.expected_sample(c.arm, c.replicate, probe, c.k)
    if c.purpose in (pl.P_MASKED, pl.P_M0):
        return opg.expected(c.arm, c.encoding, c.replicate, c.probe_id, c.k)
    unit = obat.Unit(obat.ARM_FAMILY[c.arm], osc.room_index(c.probe_id), c.replicate)
    return osc.expected_sample(c.arm, c.encoding, unit, c.k)


@pytest.mark.parametrize("battery", st.BATTERIES)
def test_pilot_seed_and_prompt_match_frozen_expected(battery: str) -> None:
    for c in pl.pilot_calls(battery):
        assert (c.seed, pl.messages_sha256(c.messages_list())) == _frozen_expected(c), (
            c.key()
        )


@pytest.mark.parametrize("battery", st.BATTERIES)
def test_main_seed_and_prompt_match_frozen_expected(battery: str) -> None:
    for c in pl.main_calls(battery, st.SPECS[battery].r_step):
        assert (c.seed, pl.messages_sha256(c.messages_list())) == _frozen_expected(c), (
            c.key()
        )


def test_messages_sha_formula_matches_every_frozen_scorer() -> None:
    msgs = pl.pilot_calls("O_time")[0].messages_list()
    shas = {
        f(msgs)
        for f in (
            v2sc.messages_sha256,
            gsc.messages_sha256,
            osc.messages_sha256,
            pl.messages_sha256,
        )
    }
    assert len(shas) == 1


def test_calls_unique_within_battery_stage() -> None:
    for b in st.BATTERIES:
        keys = [c.key() for c in pl.pilot_calls(b)]
        assert len(set(keys)) == len(keys)


# ------------------------------------------------------------ body と digest


def test_body_has_exact_registered_options() -> None:
    c = pl.pilot_calls("v2")[0]
    body = pl.body_for(c, "llama3.1:8b")
    assert set(body) == pl.BODY_KEYS
    assert body["think"] is False
    assert body["stream"] is False
    assert body["options"] == {
        "seed": c.seed,
        "temperature": 0.7,
        "top_p": 0.8,
        "top_k": 20,
        "repeat_penalty": 1.0,
        "num_ctx": 4096,
        "num_predict": 32,
    }
    assert type(body["options"]["top_k"]) is int
    assert pl.frozen_decode_problems() == []


def test_plan_digest_is_deterministic_and_sensitive() -> None:
    segs = pl.pilot_plan()
    assert pl.plan_digest(segs) == pl.plan_digest(pl.pilot_plan())
    s0 = segs[0]
    c0 = s0.calls[0]
    bad = pl.CallSpec(**{**c0.__dict__, "seed": c0.seed + 1})
    changed = pl.Segment(s0.stage, s0.battery, s0.model, (bad, *s0.calls[1:]))
    assert pl.segment_digest(changed) != pl.segment_digest(s0)
    assert pl.plan_digest((changed, *segs[1:])) != pl.plan_digest(segs)
    other_model = pl.Segment(s0.stage, s0.battery, "gemma2:9b", s0.calls)
    assert pl.segment_digest(other_model) != pl.segment_digest(s0)


# ------------------------------------------------------------ §C の battery 検査 (実 r)


@pytest.mark.parametrize(
    ("battery", "r_main"), [("v2", 8), ("v3", 8), ("G", 36), ("O_time", 12)]
)
def test_battery_checks_pass_on_registered_r(battery: str, r_main: int) -> None:
    assert pl.violations(pl.battery_checks(battery, r_main)) == []


def _strip(rep: dict[str, list[str]], r0: int) -> dict[str, list[str]]:
    pre = f"[r0={r0}] "
    return {k: [x.removeprefix(pre) for x in v] for k, v in rep.items()}


def test_v2_v3_reports_equal_frozen_at_r0_zero() -> None:
    frozen = {
        k: v
        for k, v in v2bat.battery_report(4).items()
        if isinstance(v, list) and k != "actions"
    }
    assert _strip(pl.v2_report(range(4)), 0) == frozen
    frozen3 = {k: v for k, v in v3bat.battery_report(4).items() if isinstance(v, list)}
    assert _strip(pl.v3_report(range(4)), 0) == frozen3


def test_g_report_equals_frozen_where_defined() -> None:
    frozen = gbat.battery_report(6)
    mine = _strip(pl.g_report(range(6)), 0)
    for k in (*pl._G_FIXED_CHECKS, *pl._G_R_CHECKS):
        assert mine[k] == frozen[k], k
    assert (
        pl.g_masked_states([gbat.PILOT_R0], triples=(0,)) == gbat.check_masked_states()
    )


def test_o_report_equals_frozen_where_defined() -> None:
    frozen = obat.battery_report(6)
    mine = _strip(pl.o_report(range(6)), 0)
    for k in (*pl._O_FIXED_CHECKS, *pl._O_R_CHECKS):
        assert mine[k] == frozen[k], k
    assert pl.o_masked_states(obat.pilot_units()) == obat.check_masked_states()
    assert pl.o_m0_states(obat.pilot_units()) == obat.check_m0_states()


def test_shifted_evaluates_at_real_r_and_restores() -> None:
    orig = v2bat.layout
    with pl._shifted("v2", 1000):
        assert v2bat.layout(3).replicate == 1003
    assert v2bat.layout is orig
    orig_eo = obat.entry_order

    def boom() -> None:
        with pl._shifted("O_time", 312):
            assert obat.entry_order(0, 1, 2) == orig_eo(0, 1, 314)
            raise RuntimeError

    with pytest.raises(RuntimeError):
        boom()
    assert obat.entry_order is orig_eo


def test_violation_at_a_stage2_r_only_is_caught(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex r1 H3: 本登録の r (G の pilot 始点 24) だけで表示順を壊す.

    凍結の r では通り、本登録の r で落ちる。
    """
    orig = gbat.option_order

    def broken(fi: int, j: int, r: int) -> tuple[str, ...]:
        out = orig(fi, j, r)
        return (out[1], out[0], out[2]) if (r == 24 and fi == 0 and j == 0) else out

    monkeypatch.setattr(gbat, "option_order", broken)
    assert gbat.check_position_balance(6) == []  # 凍結の r [0, 6) では見えない
    assert pl.g_report(pl.pilot_lever_r("G"))["position_balance"]


def test_masked_violation_at_r24_only_is_caught(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orig = gbat.render_state

    def broken(arm: str, order: object, *, masked: bool = False) -> str:
        out = orig(arm, order, masked=masked)
        target = gbat.entry_order(gbat.ARM_FAMILY[arm], 3, 24)
        return out + " x" if masked and order == target else out

    monkeypatch.setattr(gbat, "render_state", broken)
    assert gbat.check_masked_states() == []  # 凍結は (つ組 0, r 50) だけ
    assert pl.g_masked_states(pl.pilot_aux_r("G"))
    assert pl.battery_checks("G")["pilot:masked_states"]


def test_m0_violation_at_r312_only_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    orig = obat.render_state

    def broken(arm: str, enc: str, unit: obat.Unit, mode: str = "main") -> str:
        out = orig(arm, enc, unit, mode)
        return out + "\nextra" if mode == "m0" and unit.replicate == 312 else out

    monkeypatch.setattr(obat, "render_state", broken)
    assert obat.check_m0_states() == []  # 凍結は r 300–305
    assert pl.battery_checks("O_time")["pilot:m0_states"]


def test_seed_namespaces_catch_overlap_with_used_and_between_stages() -> None:
    assert pl.seed_problems("G", {"pilot": pl.pilot_calls("G")}) == []
    old = pl.g_unit_calls(range(3), masked=False)  # 旧本走の r 0–2 と同じ seed
    assert any("used old_main" in p for p in pl.seed_problems("G", {"main": old}))
    dup = pl.o_lever_calls([312, 313, 314])
    assert any(
        "overlap" in p
        for p in pl.seed_problems(
            "O_time", {"pilot": pl.pilot_calls("O_time"), "main": dup}
        )
    )
    v2old = pl.v2_calls([2])
    assert any("used old" in p for p in pl.seed_problems("v2", {"pilot": v2old}))


def test_v2_v3_stage2_seeds_disjoint() -> None:
    stage = {
        "v2": {"pilot": pl.pilot_calls("v2"), "main": pl.main_calls("v2", 8)},
        "v3": {"pilot": pl.pilot_calls("v3"), "main": pl.main_calls("v3", 8)},
    }
    assert pl.cross_battery_seed_problems(stage) == []


def test_prompt_budget_sent_catches_long_prompt() -> None:
    c = pl.pilot_calls("v2")[0]
    long = pl.CallSpec(**{**c.__dict__, "messages": (("user", "x" * 3001),)})
    assert pl.prompt_budget_problems([long])
    assert pl.prompt_budget_problems(pl.pilot_calls("v2")) == []
