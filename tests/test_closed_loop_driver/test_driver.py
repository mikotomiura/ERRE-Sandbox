"""閉ループ driver (mock transport のみ、実モデル不使用).

driver の判定に関わる行を pin する。対象は次のとおり。
- 閉ループの状態更新
- 送った body の照合 (凍結 scorer の連鎖 replay を oracle にする)
- 呼び出し順・C0 gate
- 再送と raw=null・再開しない
- meta の観測・来歴・起動の前提

あわせて、出力が凍結 v4 scorer (``evaluate_records``) で schema / schedule / parse /
chain の違反を出さないこと、
driver → scorer の結線 (成功行に従う → PASS、表示先頭 → NO_GO) を確かめる。
"""

from __future__ import annotations

import ast
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import httpx
import pytest
from scripts import closed_loop_battery as bat
from scripts import closed_loop_driver as drv
from scripts import closed_loop_scorer as sc
from scripts import skill_lever_battery as v2bat
from scripts.skill_lever_scorer import messages_sha256
from scripts.stage_b_scorer import (
    VERDICT_ABSENT,
    VERDICT_INVALID_BATTERY,
    VERDICT_INVALID_SCORER,
    VERDICT_PASS,
)

from tests.test_closed_loop_driver._mock import (
    BOTTOM,
    DIGEST,
    N_C0,
    N_PLAN,
    Ollama,
    c0_bottom,
    chat_response,
    do_run,
    env_response,
    evaluate,
    failing,
    first_shown,
    provenance,
    records,
)

Run = tuple[Path, str, Ollama]
PLAN = sc.frozen_plan()


def _slot(key: bat.PlanKey) -> tuple[Any, ...]:
    return (key.phase, key.world, key.replicate, key.step, key.probe_id, key.k)


def _qidx(probe_id: str) -> int:
    return [p.probe_id for p in v2bat.lever_probes()].index(probe_id)


def expected_bodies(recs: list[sc.Record]) -> list[list[dict[str, str]]]:
    """test 側で独自に畳み直した、各呼び出しの messages (driver のコードを使わない)."""
    states: dict[tuple[str, int], bat.State] = {}
    out: list[list[dict[str, str]]] = []
    by_slot: dict[tuple[Any, ...], list[dict[str, str]]] = {}
    for key, rec in zip(PLAN, recs, strict=False):
        chain = (key.world, key.replicate)
        st = states.get(chain, bat.EMPTY_STATE)
        if key.phase == bat.PHASE_C0:
            msgs = bat.c0_messages(key.replicate, _qidx(key.probe_id or ""))
        elif key.phase == bat.PHASE_LOOP:
            msgs = bat.loop_messages(
                st, key.world, key.replicate, key.step or 0, "R1plus"
            )
            states[chain] = bat.update(
                st,
                key.world,
                bat.loop_signature(key.replicate, key.step or 0),
                rec.parsed,
            )
        elif key.phase == bat.PHASE_PROBE:
            msgs = bat.probe_messages(
                st, key.world, key.replicate, _qidx(key.probe_id or ""), "R1plus"
            )
        else:
            assert key.of is not None
            msgs = by_slot[_slot(key.of)]
        by_slot[_slot(key)] = msgs
        out.append(msgs)
    return out


# ------------------------------------------------------ 順序と閉ループ


def test_run_follows_the_frozen_plan(varying_run: Run) -> None:
    run_dir, reason, _ = varying_run
    assert reason == drv.REASON_COMPLETED
    recs = records(run_dir)
    assert len(recs) == N_PLAN == 2808
    assert [r.call_index for r in recs] == list(range(N_PLAN))
    assert [_slot(r.key()) for r in recs] == [_slot(k) for k in PLAN]
    assert all(r.phase == bat.PHASE_C0 for r in recs[:N_C0])
    assert recs[N_C0].phase == bat.PHASE_LOOP
    assert all(r.phase == bat.PHASE_REPLAY for r in recs[-72:])


def test_every_call_is_sent(varying_run: Run) -> None:
    """応答をキャッシュ・省略しない (決定性 (i) の偽 1.0 を防ぐ): 送信数 = plan."""
    _, _, ollama = varying_run
    assert len(ollama.bodies) == N_PLAN
    assert len(ollama.answered) == N_PLAN


def test_sent_bodies_follow_the_chain(varying_run: Run) -> None:
    """送った messages・seed が、記録の parsed から畳み直した期待値と一致."""
    run_dir, _, ollama = varying_run
    recs = records(run_dir)
    for body, want, key, rec in zip(
        ollama.answered, expected_bodies(recs), PLAN, recs, strict=True
    ):
        assert body["messages"] == want
        assert type(body["options"]["seed"]) is int
        assert body["options"]["seed"] == sc.expected_seed(key) == rec.seed
        assert rec.prompt_sha256 == messages_sha256(want)


def test_chains_actually_differ_across_worlds(varying_run: Run) -> None:
    """mock の応答で連鎖が分岐する (状態が世界ごと・r ごとに違う body になる)."""
    run_dir, _, ollama = varying_run
    recs = records(run_dir)
    last = {}
    for body, rec in zip(ollama.answered, recs, strict=True):
        if rec.phase == bat.PHASE_LOOP and rec.step == 47:
            last[(rec.world, rec.replicate)] = messages_sha256(body["messages"])
    assert len(last) == len(bat.WORLDS) * sc.FROZEN_R
    assert len(set(last.values())) == len(last)
    parsed = Counter(r.parsed for r in recs if r.phase == bat.PHASE_LOOP)
    assert parsed[None] > 0  # ⊥ を含む
    oov = sum(
        r.parsed is not None
        and r.parsed not in bat.dev_options(r.replicate, r.step or 0)
        for r in recs
        if r.phase == bat.PHASE_LOOP
    )
    assert oov > 0  # Ω 外 (試行には数え、成功にしない) を含む


def test_outputs_pass_the_frozen_scorer_checks(varying_run: Run) -> None:
    run_dir, _, _ = varying_run
    rep = evaluate(run_dir)
    assert "record_error" not in rep
    assert rep["schedule_violations"] == []
    assert rep["parse_violations"] == []
    assert rep["chain_violations"] == []
    assert rep["verdict"] != VERDICT_INVALID_SCORER


def test_replay_resends_the_original_body_and_seed(varying_run: Run) -> None:
    run_dir, _, ollama = varying_run
    recs = records(run_dir)
    index = {_slot(k): i for i, k in enumerate(PLAN) if k.phase != bat.PHASE_REPLAY}
    n = 0
    for i, key in enumerate(PLAN):
        if key.phase != bat.PHASE_REPLAY:
            continue
        assert key.of is not None
        j = index[_slot(key.of)]
        assert ollama.answered[i]["messages"] == ollama.answered[j]["messages"]
        assert ollama.answered[i]["options"] == ollama.answered[j]["options"]
        assert recs[i].prompt_sha256 == recs[j].prompt_sha256
        n += 1
    assert n == 72


def test_raw_is_recorded_verbatim(varying_run: Run) -> None:
    run_dir, _, _ = varying_run
    recs = records(run_dir)
    padded = [r for r in recs if r.raw is not None and r.raw.startswith("  **")]
    assert padded
    assert all(r.raw.endswith("**\n") and r.parsed is not None for r in padded)
    assert all(r.parsed == sc.parse_choice(r.raw) for r in recs if r.raw is not None)
    assert any(r.raw == BOTTOM and r.parsed is None for r in recs)


def test_line_separators_in_raw_do_not_split_a_record(tmp_path: Path) -> None:
    """U+2028 / U+2029 / U+0085 は escape: 凍結 evaluate の splitlines で割れない."""
    seps = (" ", " ", "")

    def policy(index: int, body: dict[str, Any]) -> str:
        return first_shown(index, body) + seps[index % 3]

    reason, _ = do_run(tmp_path / "run", policy)
    assert reason == drv.REASON_COMPLETED
    text = (tmp_path / "run" / "records.jsonl").read_text(encoding="utf-8")
    assert len(text.splitlines()) == N_PLAN
    recs = records(tmp_path / "run")
    assert all(r.raw is not None and r.raw[-1] in seps for r in recs)
    assert evaluate(tmp_path / "run")["verdict"] != VERDICT_INVALID_SCORER


def test_state_advances_from_the_written_record() -> None:
    """absorb は書き出した行を読み戻し、parsed (raw でない) から loop の状態を進める."""
    key = next(k for k in PLAN if k.phase == bat.PHASE_LOOP and k.replicate == 1)
    sig = bat.loop_signature(key.replicate, 0)
    label = bat.rule(key.world)[sig[0]]
    rec = sc.Record(
        call_index=0,
        phase=key.phase,
        world=key.world,
        replicate=key.replicate,
        step=0,
        probe_id=None,
        k=None,
        seed=1,
        prompt_sha256="x",
        raw=f"  **{label}**",
        parsed=label,
    )
    state = drv.RunState(Path(), None, None, None, None, 0.0)  # type: ignore[arg-type]
    line = json.dumps(drv.dataclasses.asdict(rec))
    out = drv.absorb(state, line, {"messages": []})
    assert out == rec
    st = state.states[(key.world, key.replicate)]
    assert st == bat.update(bat.EMPTY_STATE, key.world, sig, label)
    assert sig in st.succeeded
    assert state.loops[(key.world, key.replicate)] == [rec]
    other = (key.world, 0)
    assert other not in state.states  # replicate を跨いで持ち越さない


# ---------------------------------------------------------- 送信前照合


def _body(msgs: list[dict[str, str]], seed: int) -> dict[str, Any]:
    return {
        "model": v2bat.MODEL,
        "messages": msgs,
        "stream": False,
        "options": {
            "seed": seed,
            "num_ctx": v2bat.NUM_CTX,
            "num_predict": v2bat.NUM_PREDICT,
            "temperature": v2bat.TEMPERATURE,
            "top_p": v2bat.TOP_P,
            "repeat_penalty": v2bat.REPEAT_PENALTY,
        },
        "think": False,
    }


def _first_loop(step: int = 0) -> tuple[int, bat.PlanKey]:
    return next(
        (i, k)
        for i, k in enumerate(PLAN)
        if k.phase == bat.PHASE_LOOP and k.step == step
    )


def test_check_accepts_the_frozen_body() -> None:
    i, key = _first_loop()
    msgs = bat.loop_messages(bat.EMPTY_STATE, key.world, key.replicate, 0, "R1plus")
    drv.check_sent_body(_body(msgs, sc.expected_seed(key)), drv.Expected(i, ()))


def test_check_rejects_a_body_from_the_wrong_state() -> None:
    """t = 1 を、t = 0 の結果を反映しない (空の) 状態で描くと連鎖 replay が拒否する."""
    i0, key0 = _first_loop(0)
    i1, key1 = next(
        (i, k)
        for i, k in enumerate(PLAN)
        if k.phase == bat.PHASE_LOOP and k.step == 1 and k.world == key0.world
    )
    sig = bat.loop_signature(key0.replicate, 0)
    label = bat.rule(key0.world)[sig[0]]  # t = 0 で成功した
    msgs0 = bat.loop_messages(bat.EMPTY_STATE, key0.world, key0.replicate, 0, "R1plus")
    rec0 = sc.Record(
        i0, key0.phase, key0.world, key0.replicate, 0, None, None,
        sc.expected_seed(key0), messages_sha256(msgs0), label, label,
    )  # fmt: skip
    good_state = bat.update(bat.EMPTY_STATE, key0.world, sig, label)
    good = bat.loop_messages(good_state, key1.world, key1.replicate, 1, "R1plus")
    drv.check_sent_body(_body(good, sc.expected_seed(key1)), drv.Expected(i1, (rec0,)))
    stale = bat.loop_messages(bat.EMPTY_STATE, key1.world, key1.replicate, 1, "R1plus")
    with pytest.raises(drv.SentBodyMismatchError, match="chain replay"):
        drv.check_sent_body(
            _body(stale, sc.expected_seed(key1)), drv.Expected(i1, (rec0,))
        )
    # 文脈を渡さない (記録済みの行を見ない) と、正しい body も拒否される
    with pytest.raises(drv.SentBodyMismatchError, match="chain replay"):
        drv.check_sent_body(_body(good, sc.expected_seed(key1)), drv.Expected(i1, ()))


def test_check_rejects_a_probe_before_its_loop() -> None:
    i, key = next((i, k) for i, k in enumerate(PLAN) if k.phase == bat.PHASE_PROBE)
    msgs = bat.probe_messages(
        bat.EMPTY_STATE, key.world, key.replicate, _qidx(key.probe_id or ""), "R1plus"
    )
    with pytest.raises(drv.SentBodyMismatchError, match="chain replay"):
        drv.check_sent_body(_body(msgs, sc.expected_seed(key)), drv.Expected(i, ()))


@pytest.mark.parametrize(
    ("path", "value", "fragment"),
    [
        (("options", "num_ctx"), 4096.0, "num_ctx"),
        (("options", "seed"), None, "seed"),
        (("options", "seed"), "shift", "seed"),
        (("options", "temperature"), 0.9, "temperature"),
        (("think",), 0, "think"),
        (("think",), None, "think"),
        (("model",), "qwen3:4b", "model"),
        (("stream",), True, "stream"),
    ],
)
def test_check_sent_body_rejects_value_and_type(
    path: tuple[str, ...], value: object, fragment: str
) -> None:
    i, key = _first_loop()
    msgs = bat.loop_messages(bat.EMPTY_STATE, key.world, key.replicate, 0, "R1plus")
    body = _body(msgs, sc.expected_seed(key))
    if value is None and path[-1] == "seed":
        value = float(sc.expected_seed(key))
    if value == "shift":
        value = sc.expected_seed(key) + 1
    target = body
    for p in path[:-1]:
        target = target[p]
    target[path[-1]] = value
    with pytest.raises(drv.SentBodyMismatchError, match=fragment):
        drv.check_sent_body(body, drv.Expected(i, ()))


@pytest.mark.parametrize(("where", "extra"), [((), "format"), (("options",), "stop")])
def test_check_sent_body_rejects_extra_keys(where: tuple[str, ...], extra: str) -> None:
    i, key = _first_loop()
    msgs = bat.loop_messages(bat.EMPTY_STATE, key.world, key.replicate, 0, "R1plus")
    body = _body(msgs, sc.expected_seed(key))
    target = body
    for p in where:
        target = target[p]
    target[extra] = "json"
    with pytest.raises(drv.SentBodyMismatchError, match="keys"):
        drv.check_sent_body(body, drv.Expected(i, ()))


def test_check_uses_the_plan_position_not_the_driver_key() -> None:
    """index が指す plan の key で照合する (C0 の body を loop の位置で送れない)."""
    i, _ = _first_loop()
    c0 = PLAN[0]
    body = _body(bat.c0_messages(0, 0), sc.expected_seed(c0))
    drv.check_sent_body(body, drv.Expected(0, ()))
    with pytest.raises(drv.SentBodyMismatchError):
        drv.check_sent_body(body, drv.Expected(i, ()))


def test_mismatch_is_detected_before_the_inner_transport() -> None:
    ollama = Ollama(first_shown)
    observer = drv.ObservingTransport(httpx.MockTransport(ollama))
    i, key = _first_loop()
    observer.expected = drv.Expected(i, ())

    async def send() -> None:
        async with httpx.AsyncClient(base_url="http://mock", transport=observer) as h:
            msgs = bat.loop_messages(
                bat.EMPTY_STATE, key.world, key.replicate, 0, "R1plus"
            )
            llm = drv.OllamaChatClient(model=v2bat.MODEL, client=h)
            await llm.chat(
                [drv.ChatMessage(**m) for m in msgs],
                sampling=drv.SAMPLING,
                options={
                    "seed": sc.expected_seed(key) + 1,
                    "num_ctx": 4096,
                    "num_predict": 32,
                },
                think=False,
            )

    with pytest.raises(drv.SentBodyMismatchError, match="seed"):
        asyncio.run(send())
    assert ollama.bodies == []


def test_non_chat_post_is_refused_before_sending() -> None:
    ollama = Ollama(first_shown)
    observer = drv.ObservingTransport(httpx.MockTransport(ollama))

    async def send() -> None:
        async with httpx.AsyncClient(base_url="http://mock", transport=observer) as h:
            await h.post("/prefix/api/chat", json={})

    with pytest.raises(drv.SentBodyMismatchError, match="POST path"):
        asyncio.run(send())
    assert ollama.bodies == []


def test_chat_without_an_expected_call_is_refused() -> None:
    ollama = Ollama(first_shown)
    observer = drv.ObservingTransport(httpx.MockTransport(ollama))

    async def send() -> None:
        async with httpx.AsyncClient(base_url="http://mock", transport=observer) as h:
            await h.post("/api/chat", json=_body(bat.c0_messages(0, 0), 1))

    with pytest.raises(drv.SentBodyMismatchError, match="expected call"):
        asyncio.run(send())
    assert ollama.bodies == []


def test_observed_meta_requires_one_condition() -> None:
    a = _body(bat.c0_messages(0, 0), 1)
    b = json.loads(json.dumps(a))
    b["options"]["num_ctx"] = 4096.0
    assert drv.observed_meta([a, a]) == sc.request_meta()
    with pytest.raises(drv.SentBodyMismatchError, match="uniform"):
        drv.observed_meta([a, b])
    assert not drv.meta_matches_frozen({**sc.request_meta(), "think": 0})
    assert not drv.meta_matches_frozen({**sc.request_meta(), "num_ctx": 4096.0})


# ------------------------------------------------------------- C0 gate


def test_c0_gate_at_the_limit_runs_the_state_side(tmp_path: Path) -> None:
    reason, _ = do_run(tmp_path / "run", c0_bottom(48))  # 48/240 = 0.2 = BOT_MAX
    assert reason == drv.REASON_COMPLETED
    assert len(records(tmp_path / "run")) == N_PLAN
    assert provenance(tmp_path / "run")["c0_bottom_rate_driver"] == pytest.approx(0.2)


def test_c0_gate_blocks_the_state_side(tmp_path: Path) -> None:
    reason, ollama = do_run(tmp_path / "run", c0_bottom(49))
    assert reason == drv.REASON_C0_GATE
    recs = records(tmp_path / "run")
    assert len(recs) == N_C0
    assert all(r.phase == bat.PHASE_C0 for r in recs)
    assert len(ollama.bodies) == N_C0
    rep = evaluate(tmp_path / "run")
    assert rep["verdict"] == VERDICT_INVALID_BATTERY
    assert rep["reasons"] == ["c0_bottom_rate"]
    assert drv.EXIT_CODES[reason] == 0


def test_c0_gate_counts_the_last_replicate(tmp_path: Path) -> None:
    """⊥ を C0 の末尾 49 件 (最後の replicate) に置く: R 全体で数えないと効かない."""
    reason, ollama = do_run(tmp_path / "run", c0_bottom(49, skip=N_C0 - 49))
    assert reason == drv.REASON_C0_GATE
    assert len(ollama.bodies) == N_C0


# ---------------------------------------------------- 再送と raw=null


def _connect_error() -> Exception:
    return httpx.ConnectError("refused")


LOOP_TARGET = next(
    i for i, k in enumerate(PLAN) if k.phase == bat.PHASE_LOOP and k.step == 5
)
REPLAY_TARGET = next(i for i, k in enumerate(PLAN) if k.phase == bat.PHASE_REPLAY) + 3


def test_resend_with_the_same_seed_recovers(tmp_path: Path) -> None:
    reason, ollama = do_run(tmp_path / "run", failing(LOOP_TARGET, 3, _connect_error))
    assert reason == drv.REASON_COMPLETED
    target = ollama.answered[LOOP_TARGET]
    same = [b for b in ollama.bodies if b == target]
    assert len(same) == 4  # 失敗 3 + 成功 1、全て同じ seed と messages
    assert len(ollama.bodies) == N_PLAN + 3
    attempts = [
        json.loads(line)
        for line in (tmp_path / "run" / "attempts.jsonl")
        .read_text("utf-8")
        .splitlines()
    ]
    mine = [a for a in attempts if a["call_index"] == LOOP_TARGET]
    assert [a["outcome"] for a in mine] == ["transport_failure"] * 3 + ["ok"]
    assert provenance(tmp_path / "run")["n_resends"] == 3
    assert evaluate(tmp_path / "run")["chain_violations"] == []


@pytest.mark.parametrize("target", [LOOP_TARGET, REPLAY_TARGET])
def test_unresolved_transport_failure_records_null_and_stops(
    tmp_path: Path, target: int
) -> None:
    reason, ollama = do_run(tmp_path / "run", failing(target, 4, _connect_error))
    assert reason == drv.REASON_TRANSPORT
    recs = records(tmp_path / "run")
    assert len(recs) == target + 1
    assert recs[-1].raw is None
    assert recs[-1].parsed is None
    assert all(r.raw is not None for r in recs[:-1])
    assert len(ollama.bodies) == target + 4
    rep = evaluate(tmp_path / "run")
    assert rep["status"] == sc.STATUS_NOT_COMPUTED
    assert rep["verdict"] is None
    assert rep["reasons"] == ["transport_failure"]
    assert drv.EXIT_CODES[reason] != 0


def test_read_timeout_is_a_transport_failure(tmp_path: Path) -> None:
    reason, _ = do_run(
        tmp_path / "run", failing(3, 4, lambda: httpx.ReadTimeout("slow"))
    )
    assert reason == drv.REASON_TRANSPORT
    assert len(records(tmp_path / "run")) == 4


def test_non_json_payload_counts_as_transport_failure(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        env = env_response(request, [DIGEST])
        if env is not None:
            return env
        return httpx.Response(200, text="not json")

    reason = asyncio.run(
        drv.run(tmp_path / "run", httpx.MockTransport(handler), backoff_s=0.0)
    )
    assert reason == drv.REASON_TRANSPORT
    recs = records(tmp_path / "run")
    assert len(recs) == 1
    assert recs[0].raw is None


def test_null_content_is_a_transport_failure_not_bottom(tmp_path: Path) -> None:
    def null_at(index: int, body: dict[str, Any]) -> str | None:
        return None if index == LOOP_TARGET else first_shown(index, body)

    reason, ollama = do_run(tmp_path / "run", null_at)
    assert reason == drv.REASON_TRANSPORT
    recs = records(tmp_path / "run")
    assert len(recs) == LOOP_TARGET + 1
    assert recs[-1].raw is None
    assert len(ollama.bodies) == LOOP_TARGET + 4


def test_other_exceptions_abort_without_a_null_row(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="bug"):
        do_run(tmp_path / "run", failing(LOOP_TARGET, 1, lambda: ValueError("bug")))
    recs = records(tmp_path / "run")
    assert len(recs) == LOOP_TARGET
    assert all(r.raw is not None for r in recs)
    assert provenance(tmp_path / "run")["exit_reason"] == drv.REASON_ABORTED


def test_run_refuses_a_non_empty_run_dir(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "records.jsonl").write_text("partial\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        do_run(run_dir, first_shown)
    assert (run_dir / "records.jsonl").read_text(encoding="utf-8") == "partial\n"
    assert not (run_dir / "provenance.json").exists()


# ------------------------------------------------------ driver → scorer の結線


def test_following_success_rows_is_pass_with_coverage_and_flagged_note(
    follow_run: Run,
) -> None:
    run_dir, reason, _ = follow_run
    assert reason == drv.REASON_COMPLETED
    rep = evaluate(run_dir)
    assert rep["chain_violations"] == []
    assert rep["verdict"] == VERDICT_PASS
    assert rep["C"] == 1.0
    assert rep["claim_branch"] == sc.CLAIM_PASS
    cov = rep["coverage"]
    assert cov["weather_coverage"] == 1.0
    text = rep["claim_text"]
    assert "weather coverage = 1.000" in text
    assert (
        f"発見した weather = {cov['discovered_weathers']} / {cov['possible_weathers']}"
        in text
    )
    assert "signature coverage" in text
    assert sc.FLAGGED_NOTE in text


def test_first_shown_is_no_go(first_run: Run) -> None:
    run_dir, reason, _ = first_run
    assert reason == drv.REASON_COMPLETED
    rep = evaluate(run_dir)
    assert rep["verdict"] == VERDICT_ABSENT
    assert rep["C"] == 0.0
    assert rep["claim_branch"] in (sc.CLAIM_NO_GO_EXPLORATION, sc.CLAIM_NO_GO_LOOKUP)


# --------------------------------------------------- meta・provenance・preflight


def test_meta_is_observed_and_matches_frozen(first_run: Run) -> None:
    run_dir, _, _ = first_run
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    assert drv.meta_matches_frozen(meta)
    prov = provenance(run_dir)
    assert prov["meta_matches_frozen"] is True
    assert prov["exit_reason"] == drv.REASON_COMPLETED
    assert prov["n_records"] == prov["n_sent"] == N_PLAN
    assert prov["response_models"] == [v2bat.MODEL]


def test_meta_is_written_from_sent_values_not_constants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """照合を外し温度をずらす: meta は送った値 0.71、aborted、判定 INVALID_SCORER."""
    monkeypatch.setattr(drv, "check_sent_body", lambda _body, _exp: None)
    monkeypatch.setattr(
        drv,
        "SAMPLING",
        drv.ResolvedSampling(temperature=0.71, top_p=0.8, repeat_penalty=1.0),
    )
    reason, _ = do_run(tmp_path / "run", first_shown)
    assert reason == drv.REASON_ABORTED
    prov = provenance(tmp_path / "run")
    assert prov["meta_matches_frozen"] is False
    assert "frozen meta" in prov["error"]
    meta = json.loads((tmp_path / "run" / "meta.json").read_text(encoding="utf-8"))
    assert meta["temperature"] == 0.71
    rep = evaluate(tmp_path / "run")
    assert rep["verdict"] == VERDICT_INVALID_SCORER
    assert rep["reasons"] == ["request_meta_mismatch"]


def test_shifted_sampling_aborts_before_sending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        drv,
        "SAMPLING",
        drv.ResolvedSampling(temperature=0.71, top_p=0.8, repeat_penalty=1.0),
    )
    with pytest.raises(drv.SentBodyMismatchError, match="temperature"):
        do_run(tmp_path / "run", first_shown)
    assert not (tmp_path / "run" / "records.jsonl").read_text(encoding="utf-8")
    assert not (tmp_path / "run" / "meta.json").exists()
    prov = provenance(tmp_path / "run")
    assert prov["exit_reason"] == drv.REASON_ABORTED
    assert "SentBodyMismatchError" in prov["error"]


def test_seed_and_prompt_are_recorded_from_the_sent_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """照合を外し seed +1・prompt をずらすと、記録は送った値、判定は INVALID_SCORER."""
    original = drv.request_for

    def shifted(key: bat.PlanKey, state: drv.RunState) -> tuple[Any, Any]:
        msgs, options = original(key, state)
        msgs = [*msgs[:-1], {**msgs[-1], "content": msgs[-1]["content"] + " "}]
        return msgs, {**options, "seed": options["seed"] + 1}

    monkeypatch.setattr(drv, "check_sent_body", lambda _body, _exp: None)
    monkeypatch.setattr(drv, "request_for", shifted)
    reason, ollama = do_run(tmp_path / "run", first_shown)
    assert reason == drv.REASON_COMPLETED
    recs = records(tmp_path / "run")
    for rec, body in zip(recs, ollama.answered, strict=True):
        assert rec.seed == body["options"]["seed"]
        assert rec.prompt_sha256 == messages_sha256(body["messages"])
    assert recs[0].seed == sc.expected_seed(PLAN[0]) + 1
    rep = evaluate(tmp_path / "run")
    assert rep["verdict"] == VERDICT_INVALID_SCORER
    assert rep["reasons"] == ["schedule"]


def test_preflight_failure_writes_nothing(tmp_path: Path) -> None:
    def no_model(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": []})
        return httpx.Response(200, json={"version": "mock"})

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    for handler in (no_model, down):
        with pytest.raises(drv.PreflightError):
            asyncio.run(drv.run(tmp_path / "run", httpx.MockTransport(handler)))
        assert not (tmp_path / "run").exists()


def test_meta_is_on_disk_while_the_run_is_going(tmp_path: Path) -> None:
    """kill されても meta.json が残る: 2 件目の呼び出しの時点で書かれている."""
    run_dir = tmp_path / "run"
    seen: list[bool] = []

    def policy(index: int, body: dict[str, Any]) -> str | None:
        seen.append((run_dir / "meta.json").exists())
        if index == 3:
            raise ValueError("stop here")
        return first_shown(index, body)

    with pytest.raises(ValueError, match="stop here"):
        do_run(run_dir, policy)
    assert seen[0] is False
    assert all(seen[1:])
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    assert drv.meta_matches_frozen(meta)


def test_model_digest_change_aborts(tmp_path: Path) -> None:
    reason, _ = do_run(
        tmp_path / "run", c0_bottom(49), digests=(DIGEST, "sha256:" + "1" * 64)
    )
    assert reason == drv.REASON_ABORTED
    prov = provenance(tmp_path / "run")
    assert "digest changed" in prov["error"]
    assert prov["model_digest_start"] != prov["model_digest_end"]


def test_final_preflight_is_resent(tmp_path: Path) -> None:
    """終了時の digest 再確認は再送する: 1 回落ちても c0_gate のまま."""
    reason, _ = do_run(tmp_path / "run", c0_bottom(49), preflight_down=frozenset({1}))
    assert reason == drv.REASON_C0_GATE


def test_final_preflight_failure_aborts_a_finished_run(tmp_path: Path) -> None:
    down = frozenset(range(1, 1 + 1 + drv.RESENDS))
    reason, _ = do_run(tmp_path / "run", c0_bottom(49), preflight_down=down)
    assert reason == drv.REASON_ABORTED
    prov = provenance(tmp_path / "run")
    assert "final preflight failed" in prov["error"]
    assert prov["model_digest_end"] is None


def test_final_preflight_failure_keeps_a_transport_failure(tmp_path: Path) -> None:
    """Ollama が落ちたままでも、transport 失敗で止まった run は transport_failure."""
    down = frozenset(range(1, 1 + 1 + drv.RESENDS))
    reason, _ = do_run(
        tmp_path / "run", failing(3, 4, _connect_error), preflight_down=down
    )
    assert reason == drv.REASON_TRANSPORT
    prov = provenance(tmp_path / "run")
    assert prov["exit_reason"] == drv.REASON_TRANSPORT
    assert "final preflight failed" in prov["error"]


def test_unexpected_response_model_aborts(tmp_path: Path) -> None:
    reason, _ = do_run(tmp_path / "run", c0_bottom(49), model="qwen3:4b")
    assert reason == drv.REASON_ABORTED
    prov = provenance(tmp_path / "run")
    assert prov["response_models"] == ["qwen3:4b"]
    assert "response models" in prov["error"]


def test_driver_change_during_the_run_aborts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = iter(("a" * 64, "b" * 64))
    original = drv._sha256

    def sha(path: Path) -> str | None:
        if Path(path) == Path(drv.__file__):
            return next(calls)
        return original(path)

    monkeypatch.setattr(drv, "_sha256", sha)
    reason, _ = do_run(tmp_path / "run", c0_bottom(49))
    assert reason == drv.REASON_ABORTED
    prov = provenance(tmp_path / "run")
    assert prov["driver_sha256_start"] != prov["driver_sha256_end"]
    assert "driver file changed" in prov["error"]


def test_chat_response_helper_round_trips() -> None:
    resp = chat_response("read_book", v2bat.MODEL)
    assert resp.json()["message"]["content"] == "read_book"


# ------------------------------------------------------ 起動の前提と import 制限


def test_driver_does_not_import_other_drivers() -> None:
    tree = ast.parse(Path(drv.__file__).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
    assert not any("_driver" in n for n in names)
    local = {n for n in names if n.startswith(("scripts", "erre_sandbox"))}
    assert local == {
        "scripts",
        "scripts.closed_loop_battery",
        "scripts.closed_loop_scorer",
        "scripts.skill_lever_battery",
        "scripts.skill_lever_scorer",
        "scripts.skill_lever_scorer.bottom_rates",
        "scripts.skill_lever_scorer.messages_sha256",
        "erre_sandbox.inference.ollama_adapter",
        "erre_sandbox.inference.ollama_adapter.ChatMessage",
        "erre_sandbox.inference.ollama_adapter.ChatResponse",
        "erre_sandbox.inference.ollama_adapter.OllamaChatClient",
        "erre_sandbox.inference.ollama_adapter.OllamaUnavailableError",
        "erre_sandbox.inference.sampling",
        "erre_sandbox.inference.sampling.ResolvedSampling",
    }


def _script(tmp_path: Path, name: str, body: str) -> str:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return str(path)


def test_manifest_problems_require_manifest_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ok = _script(tmp_path, "ok.py", "print('checking')\nprint('MANIFEST OK')\n")
    bad = _script(
        tmp_path, "bad.py", "print('MANIFEST MISMATCH (1)')\nraise SystemExit(1)\n"
    )
    silent = _script(tmp_path, "silent.py", "print('MANIFEST OK')\nprint('x')\n")
    crash = _script(tmp_path, "crash.py", "print('MANIFEST OK')\nraise SystemExit(2)\n")
    monkeypatch.setattr(drv, "MANIFEST_CHECKS", (ok,))
    assert drv.manifest_problems() == []
    for script in (bad, silent, crash):
        monkeypatch.setattr(drv, "MANIFEST_CHECKS", (ok, script))
        assert len(drv.manifest_problems()) == 1
    monkeypatch.setattr(drv, "MANIFEST_CHECKS", (str(tmp_path / "missing.py"),))
    assert len(drv.manifest_problems()) == 1


def test_committed_manifests_pass_the_launch_check() -> None:
    assert drv.MANIFEST_CHECKS == (
        "scripts/skill_lever_manifest.py",
        "scripts/skill_experience_manifest.py",
        "scripts/closed_loop_manifest.py",
    )
    assert sys.executable
    assert drv.manifest_problems() == []


def test_launch_problems_include_manifest_and_certification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(drv, "manifest_problems", lambda: ["manifest boom"])
    monkeypatch.setattr(drv, "DRIVER_CERT", tmp_path / "missing.json")
    problems = drv.launch_problems()
    assert "manifest boom" in problems
    assert any("driver certification unreadable" in p for p in problems)


def test_main_refuses_to_launch_without_touching_the_run_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called: list[object] = []

    async def must_not_run(*args: object, **_kwargs: object) -> str:
        called.append(args)  # 実 endpoint には繋がない (変異で起動拒否が外れても安全)
        return drv.REASON_ABORTED

    monkeypatch.setattr(drv, "launch_problems", lambda: ["nope"])
    monkeypatch.setattr(drv, "run", must_not_run)
    monkeypatch.setattr(drv, "DEFAULT_RUN_DIR", tmp_path / "run")
    code = drv.main([])
    assert code == drv.EXIT_CODES[drv.REASON_ABORTED]
    assert called == []
    assert not (tmp_path / "run").exists()


def test_main_takes_no_run_dir_or_endpoint() -> None:
    """登録外の実走経路を閉じる (DR-6 / DR-7): run dir と endpoint は固定."""
    for extra in (["--run-dir", "x"], ["--endpoint", "http://example"]):
        with pytest.raises(SystemExit):
            drv.main(extra)


def test_driver_certification_detects_stale_or_failing(tmp_path: Path) -> None:
    good = {"target_sha256": drv.certified_files(), "all_killed": True}
    cert = tmp_path / "cert.json"
    cert.write_text(json.dumps(good), encoding="utf-8")
    assert drv.driver_certification_problems(cert) == []
    cert.write_text(json.dumps({**good, "all_killed": False}), encoding="utf-8")
    assert drv.driver_certification_problems(cert) == [
        "driver certification: not all KILLED"
    ]
    stale = {**good["target_sha256"], "closed_loop_driver.py": "0" * 64}
    cert.write_text(json.dumps({**good, "target_sha256": stale}), encoding="utf-8")
    assert len(drv.driver_certification_problems(cert)) == 1
    assert drv.driver_certification_problems(tmp_path / "missing.json")
    assert set(good["target_sha256"]) == {
        "closed_loop_driver.py",
        "closed_loop_describe.py",
        "closed_loop_run_gate.py",
        "closed_loop_driver_mutation_check.py",
        "closed_loop_judge.py",
        "tests/__init__.py",
        "tests/_mock.py",
        "tests/conftest.py",
        "tests/test_driver.py",
        "tests/test_describe.py",
        "tests/test_judge.py",
        "tests/test_run_gate.py",
    }
    assert None not in good["target_sha256"].values()


def test_launch_problems_check_git_tracking_and_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(drv, "manifest_problems", list)
    monkeypatch.setattr(drv, "driver_certification_problems", lambda _p: [])
    monkeypatch.setattr(drv, "_git", lambda *_a: "")
    assert drv.launch_problems() == []
    monkeypatch.setattr(drv, "_git", lambda *_a: None)
    problems = drv.launch_problems()
    assert sum(p.startswith("not tracked by git") for p in problems) == len(drv.PINNED)
    assert any("differ from HEAD" in p for p in problems)

    def untracked_only(*args: str) -> str | None:
        return None if args[0] == "ls-files" else ""

    monkeypatch.setattr(drv, "_git", untracked_only)
    assert not any("HEAD" in p for p in drv.launch_problems())

    def diff_only(*args: str) -> str | None:
        return None if args[0] == "diff" else ""

    monkeypatch.setattr(drv, "_git", diff_only)
    assert drv.launch_problems() == [
        "pinned files differ from HEAD (or git unavailable)"
    ]


def test_pinned_covers_the_judgement_path() -> None:
    must = {
        "scripts/closed_loop_driver.py",
        "scripts/closed_loop_describe.py",
        "scripts/closed_loop_run_gate.py",
        "scripts/closed_loop_judge.py",
        "scripts/closed_loop_evaluate.py",
        "scripts/closed_loop_scorer.py",
        "scripts/closed_loop_battery.py",
        "experiments/20260927-closed-loop-divergence-pilot/run.sh",
        "experiments/20260927-closed-loop-divergence-pilot/prereg.md",
        "experiments/20260927-closed-loop-divergence-pilot/manifest.json",
        "experiments/20260927-closed-loop-divergence-pilot/results/v4_mutation.json",
        "experiments/20260927-closed-loop-divergence-pilot/results/driver_mutation.json",
    }
    assert must <= set(drv.PINNED)
    root = Path(drv.__file__).resolve().parents[1]
    missing = [
        p for p in drv.PINNED if not (root / p).exists() and "driver_mutation" not in p
    ]
    assert missing == []


def test_committed_driver_certification_is_current() -> None:
    """commit 済み driver_mutation.json が現在の driver・test と一致 (変異中は外す)."""
    assert drv.driver_certification_problems(drv.DRIVER_CERT) == []
