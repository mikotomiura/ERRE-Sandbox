"""閉ループ v5 較正 pilot の driver (mock transport のみ、実モデル不使用).

driver の判定に関わる行を pin する。
- 閉ループの状態更新 ((軸, 世界, r) ごと)
- 送った body の照合 (凍結 scorer の連鎖 replay を oracle にする)
- 呼び出し順・再送と raw=null・再開しない
- 記録・meta の観測・来歴
- 成功したときだけ公開する (凍結 validate を公開条件に含む)

期待値は test 側で、凍結 renderer (``loop_messages``) と凍結更新 (``update``) から
独自に畳み直す (driver のコードを使わない)。
driver の出力は、凍結 ``evaluate_records`` で ``computed`` になることを確かめる。
"""

from __future__ import annotations

import asyncio
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import httpx
import pytest
from scripts import closed_loop_battery as v4
from scripts import closed_loop_v5_battery as bat
from scripts import closed_loop_v5_driver as drv
from scripts import closed_loop_v5_pilot_scorer as ps
from scripts import skill_lever_battery as v2bat
from scripts.skill_lever_scorer import messages_sha256, parse_choice, request_meta

from tests.test_closed_loop_v5_driver._mock import (
    BOTTOM,
    DIGEST,
    FULL_PLAN,
    N_PLAN,
    N_SHORT,
    SEPARATORS,
    Ollama,
    chat_response,
    connect_error,
    do_run,
    env_response,
    evaluate,
    failing,
    first_shown,
    lines_of,
    partial,
    provenance,
    published,
)

Run = tuple[Path, str, Ollama]


def expected_bodies(recs: list[ps.Record]) -> list[list[dict[str, str]]]:
    """test 側で独自に畳み直した、各呼び出しの messages (driver のコードを使わない)."""
    states: dict[tuple[str, str, int], v4.State] = {}
    out: list[list[dict[str, str]]] = []
    for key, rec in zip(FULL_PLAN, recs, strict=False):
        chain = (key.axis, key.world, key.replicate)
        st = states.get(chain, v4.EMPTY_STATE)
        out.append(bat.loop_messages(st, key.world, key.replicate, key.step, key.axis))
        states[chain] = v4.update(
            st, key.world, v4.loop_signature(key.replicate, key.step), rec.parsed
        )
    return out


def _not_published(run_dir: Path) -> None:
    """公開されていないこと (公開名が無い) を最初に見る.

    変異 harness は、この assert の文で失敗の理由を照合する。
    """
    assert not (run_dir / drv.RECORDS_NAME).exists(), "records.jsonl was published"
    assert provenance(run_dir)["publishable"] is False


# ------------------------------------------------------ 順序と閉ループ (full run)


def test_run_follows_the_frozen_plan(varying_run: Run) -> None:
    run_dir, reason, _ = varying_run
    assert reason == drv.REASON_COMPLETED
    recs = published(run_dir)
    assert len(recs) == N_PLAN == 3072
    assert [r.call_index for r in recs] == list(range(N_PLAN))
    assert [r.key() for r in recs] == list(FULL_PLAN)


def test_every_call_is_sent_once(varying_run: Run) -> None:
    """応答をキャッシュ・省略しない: 送信数 = plan.

    両軸・4 世界が seed を共有しても、1 件ずつ送る。
    """
    _, _, ollama = varying_run
    assert len(ollama.bodies) == N_PLAN
    assert len(ollama.answered) == N_PLAN


def test_sent_bodies_follow_the_chain(varying_run: Run) -> None:
    """送った messages・seed が、記録の parsed から畳み直した期待値と一致."""
    run_dir, _, ollama = varying_run
    recs = published(run_dir)
    for body, want, key, rec in zip(
        ollama.answered, expected_bodies(recs), FULL_PLAN, recs, strict=True
    ):
        assert body["messages"] == want
        assert type(body["options"]["seed"]) is int
        assert body["options"]["seed"] == bat.pilot_seed(key.replicate, key.step)
        assert rec.seed == body["options"]["seed"]
        assert rec.prompt_sha256 == messages_sha256(want)


def test_explore_sentence_only_in_axis_c(varying_run: Run) -> None:
    _, _, ollama = varying_run
    for body, key in zip(ollama.answered, FULL_PLAN, strict=True):
        assert body["messages"][0]["content"] == v2bat.SYSTEM_PROMPT
        n = body["messages"][1]["content"].count(bat.EXPLORE_SENTENCE)
        assert n == (1 if key.axis == bat.AXIS_C else 0)


def test_chains_actually_differ(varying_run: Run) -> None:
    """mock の応答で連鎖が分岐する (状態が軸・世界・r ごとに違う body になる)."""
    run_dir, _, ollama = varying_run
    recs = published(run_dir)
    last = {
        (r.axis, r.world, r.replicate): messages_sha256(body["messages"])
        for body, r in zip(ollama.answered, recs, strict=True)
        if r.step == bat.PILOT_T - 1
    }
    assert len(last) == len(bat.AXES) * len(v4.WORLDS) * len(bat.PILOT_R)
    assert len(set(last.values())) == len(last)
    parsed = Counter(r.parsed for r in recs)
    assert parsed[None] > 0  # ⊥ を含む
    oov = sum(
        r.parsed is not None
        and r.parsed not in bat.dev_options(r.axis, r.replicate, r.step)
        for r in recs
    )
    assert oov > 0  # Ω 外 (試行には数え、成功にしない) を含む
    # 共通乱数: 同じ (r, t) の 8 呼び出し (両軸・4 世界) は同じ seed
    seeds: dict[tuple[int, int], set[int]] = {}
    for r in recs:
        seeds.setdefault((r.replicate, r.step), set()).add(r.seed)
    assert all(len(s) == 1 for s in seeds.values())


def test_published_records_are_computed_by_the_frozen_scorer(varying_run: Run) -> None:
    run_dir, _, _ = varying_run
    assert not (run_dir / drv.PARTIAL_NAME).exists()
    rep = evaluate(run_dir / drv.RECORDS_NAME, run_dir)
    assert rep["status"] == ps.STATUS_COMPUTED
    assert rep["reasons"] == []
    assert set(rep["measures"]) == {"4", "6", "8"}
    prov = provenance(run_dir)
    assert prov["publishable"] is True
    assert prov["published"] is True
    assert prov["frozen_validate"] == {"status": ps.STATUS_COMPUTED, "reasons": []}
    assert prov["manifest_problems_at_publication"] == []
    assert prov["exit_reason"] == drv.REASON_COMPLETED
    assert prov["error"] is None
    assert prov["anomalies"] == []
    assert prov["pinned_changed"] == []
    assert prov["n_records"] == prov["n_sent"] == N_PLAN


def test_line_separators_in_raw_do_not_split_a_record(varying_run: Run) -> None:
    """U+2028 / U+2029 / U+0085 は escape: 凍結 reader の splitlines で割れない."""
    run_dir, _, _ = varying_run
    assert len(lines_of(run_dir / drv.RECORDS_NAME)) == N_PLAN
    recs = published(run_dir)
    for sep in SEPARATORS:
        assert any(r.raw is not None and r.raw.endswith(sep) for r in recs)


def test_raw_is_recorded_verbatim(varying_run: Run) -> None:
    run_dir, _, _ = varying_run
    recs = published(run_dir)
    padded = [r for r in recs if r.raw is not None and r.raw.startswith("  **")]
    assert padded
    assert all(r.raw.endswith("**\n") and r.parsed is not None for r in padded)
    assert all(r.parsed == parse_choice(r.raw) for r in recs if r.raw is not None)
    assert any(r.raw == BOTTOM and r.parsed is None for r in recs)


def test_state_advances_from_the_written_record() -> None:
    """absorb は書き出した行を読み戻し、parsed (raw でない) から状態を進める.

    状態は (軸, 世界, r) ごと。
    """
    sig = v4.loop_signature(13, 0)
    # 世界を取り違えると成否が変わる世界を選ぶ (規則が v4.WORLDS[0] と違う)
    key = next(
        k
        for k in FULL_PLAN
        if k.axis == bat.AXIS_C
        and k.replicate == 13
        and v4.rule(k.world)[sig[0]] != v4.rule(v4.WORLDS[0])[sig[0]]
    )
    label = v4.rule(key.world)[sig[0]]
    rec = ps.Record(
        call_index=0,
        axis=key.axis,
        world=key.world,
        replicate=key.replicate,
        step=0,
        seed=1,
        prompt_sha256="x",
        raw=f"  **{label}**",
        parsed=label,
    )
    state = drv.RunState(Path(), None, None, None, None, 0.0)  # type: ignore[arg-type]
    out = drv.absorb(state, json.dumps(drv.dataclasses.asdict(rec)))
    assert out == rec
    chain = (key.axis, key.world, key.replicate)
    st = state.states[chain]
    assert st == v4.update(v4.EMPTY_STATE, key.world, sig, label)
    assert sig in st.succeeded
    assert state.chains[chain] == [rec]
    assert state.records == [rec]
    # 軸・世界・replicate を跨いで持ち越さない
    assert set(state.states) == {chain}


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


def _at(axis: str, step: int, world: str | None = None) -> tuple[int, bat.PilotKey]:
    return next(
        (i, k)
        for i, k in enumerate(FULL_PLAN)
        if k.axis == axis and k.step == step and (world is None or k.world == world)
    )


def _record(i: int, key: bat.PilotKey, msgs: Any, parsed: str | None) -> ps.Record:
    return ps.Record(
        i, key.axis, key.world, key.replicate, key.step,
        bat.pilot_seed(key.replicate, key.step), messages_sha256(msgs),
        parsed or BOTTOM, parsed,
    )  # fmt: skip


def _empty_body(key: bat.PilotKey, axis: str | None = None) -> dict[str, Any]:
    msgs = bat.loop_messages(
        v4.EMPTY_STATE, key.world, key.replicate, key.step, axis or key.axis
    )
    return _body(msgs, bat.pilot_seed(key.replicate, key.step))


def test_check_accepts_the_frozen_body() -> None:
    i, key = _at(bat.AXIS_B, 0)
    drv.check_sent_body(_empty_body(key), drv.Expected(i, ()))


def test_check_rejects_a_body_from_the_wrong_state() -> None:
    """t = 1 を、t = 0 の結果を反映しない (空の) 状態で描くと連鎖 replay が拒否する."""
    i0, key0 = _at(bat.AXIS_C, 0)
    i1, key1 = _at(bat.AXIS_C, 1, key0.world)
    sig = v4.loop_signature(key0.replicate, 0)
    label = v4.rule(key0.world)[sig[0]]  # t = 0 で成功した
    rec0 = _record(i0, key0, _empty_body(key0)["messages"], label)
    good_state = v4.update(v4.EMPTY_STATE, key0.world, sig, label)
    good = bat.loop_messages(good_state, key1.world, key1.replicate, 1, key1.axis)
    seed1 = bat.pilot_seed(key1.replicate, 1)
    drv.check_sent_body(_body(good, seed1), drv.Expected(i1, (rec0,)))
    with pytest.raises(drv.SentBodyMismatchError, match="chain replay"):
        drv.check_sent_body(_empty_body(key1), drv.Expected(i1, (rec0,)))
    # 文脈を渡さない (記録済みの行を見ない) と、正しい body も拒否される
    with pytest.raises(drv.SentBodyMismatchError, match="chain replay"):
        drv.check_sent_body(_body(good, seed1), drv.Expected(i1, ()))


def test_check_rejects_the_other_axis_body() -> None:
    """同じ (世界, r, t)・同じ seed でも、軸を取り違えた body は拒否する.

    軸で違うのは、指示文の有無と表示順。
    """
    for axis, other in ((bat.AXIS_B, bat.AXIS_C), (bat.AXIS_C, bat.AXIS_B)):
        for step in (0, 13):
            i, key = _at(axis, step)
            ctx = tuple(
                _record(j, k, _empty_body(k)["messages"], None)
                for j, k in enumerate(FULL_PLAN)
                if (k.axis, k.world, k.replicate) == (axis, key.world, key.replicate)
                and k.step < step
            )
            drv.check_sent_body(_empty_body(key), drv.Expected(i, ctx))
            with pytest.raises(drv.SentBodyMismatchError, match="chain replay"):
                drv.check_sent_body(_empty_body(key, other), drv.Expected(i, ctx))


def test_check_rejects_state_shared_across_axes() -> None:
    """軸 C の t = 1 を、軸 B の t = 0 の結果で進めた状態で描くと拒否する.

    状態は軸ごとに持つ。
    """
    i_b, key_b = _at(bat.AXIS_B, 0)
    i_c, key_c = _at(bat.AXIS_C, 0, key_b.world)
    i1, key1 = _at(bat.AXIS_C, 1, key_b.world)
    sig = v4.loop_signature(key_b.replicate, 0)
    label = v4.rule(key_b.world)[sig[0]]
    rec_b = _record(i_b, key_b, _empty_body(key_b)["messages"], label)  # B は成功
    rec_c = _record(i_c, key_c, _empty_body(key_c)["messages"], None)  # C は ⊥
    shared = v4.update(v4.EMPTY_STATE, key_b.world, sig, label)
    body = _body(
        bat.loop_messages(shared, key1.world, key1.replicate, 1, key1.axis),
        bat.pilot_seed(key1.replicate, 1),
    )
    with pytest.raises(drv.SentBodyMismatchError, match="chain replay"):
        drv.check_sent_body(body, drv.Expected(i1, (rec_b, rec_c)))
    drv.check_sent_body(_empty_body(key1), drv.Expected(i1, (rec_b, rec_c)))


@pytest.mark.parametrize(
    ("path", "value", "fragment"),
    [
        (("options", "num_ctx"), 4096.0, "num_ctx"),
        (("options", "seed"), None, "seed"),
        (("options", "seed"), "shift", "seed"),
        (("options", "temperature"), 0.9, "temperature"),
        (("options", "top_p"), 0.9, "top_p"),
        (("options", "repeat_penalty"), 1.1, "repeat_penalty"),
        (("options", "num_predict"), 64, "num_predict"),
        (("think",), 0, "think"),
        (("think",), None, "think"),
        (("model",), "qwen3:4b", "model"),
        (("stream",), True, "stream"),
    ],
)
def test_check_sent_body_rejects_value_and_type(
    path: tuple[str, ...], value: object, fragment: str
) -> None:
    i, key = _at(bat.AXIS_B, 0)
    body = _empty_body(key)
    seed = bat.pilot_seed(key.replicate, key.step)
    if value is None and path[-1] == "seed":
        value = float(seed)
    if value == "shift":
        value = seed + 1
    target = body
    for p in path[:-1]:
        target = target[p]
    target[path[-1]] = value
    with pytest.raises(drv.SentBodyMismatchError, match=fragment):
        drv.check_sent_body(body, drv.Expected(i, ()))


@pytest.mark.parametrize(
    "messages",
    [
        None,
        "text",
        [["user", "x"]],
        [{"role": "user"}],
        [{"role": "user", "content": 1}],
    ],
)
def test_check_sent_body_rejects_malformed_messages(messages: object) -> None:
    """messages が role / content の文字列の list でなければ照合で止める.

    sha を取る前に止める (TypeError にしない)。
    """
    i, key = _at(bat.AXIS_B, 0)
    body = _empty_body(key)
    body["messages"] = messages
    with pytest.raises(drv.SentBodyMismatchError, match="messages"):
        drv.check_sent_body(body, drv.Expected(i, ()))


@pytest.mark.parametrize(("where", "extra"), [((), "format"), (("options",), "stop")])
def test_check_sent_body_rejects_extra_keys(where: tuple[str, ...], extra: str) -> None:
    i, key = _at(bat.AXIS_B, 0)
    body = _empty_body(key)
    target = body
    for p in where:
        target = target[p]
    target[extra] = "json"
    with pytest.raises(drv.SentBodyMismatchError, match="keys"):
        drv.check_sent_body(body, drv.Expected(i, ()))


def test_check_uses_the_plan_position_not_the_driver_key() -> None:
    """index が指す plan の key で照合する (同じ seed でも、別の軸の位置で送れない)."""
    first = FULL_PLAN[0]
    i, _ = _at(bat.AXIS_C if first.axis == bat.AXIS_B else bat.AXIS_B, 0)
    body = _empty_body(first)
    drv.check_sent_body(body, drv.Expected(0, ()))
    with pytest.raises(drv.SentBodyMismatchError):
        drv.check_sent_body(body, drv.Expected(i, ()))


def test_mismatch_is_detected_before_the_inner_transport() -> None:
    ollama = Ollama(first_shown)
    observer = drv.ObservingTransport(httpx.MockTransport(ollama))
    i, key = _at(bat.AXIS_B, 0)
    observer.expected = drv.Expected(i, ())

    async def send() -> None:
        async with httpx.AsyncClient(base_url="http://mock", transport=observer) as h:
            msgs = _empty_body(key)["messages"]
            llm = drv.OllamaChatClient(model=v2bat.MODEL, client=h)
            await llm.chat(
                [drv.ChatMessage(**m) for m in msgs],
                sampling=drv.SAMPLING,
                options={
                    "seed": bat.pilot_seed(key.replicate, key.step) + 1,
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
            await h.post("/api/chat", json=_empty_body(FULL_PLAN[0]))

    with pytest.raises(drv.SentBodyMismatchError, match="expected call"):
        asyncio.run(send())
    assert ollama.bodies == []


def test_observed_meta_requires_one_condition() -> None:
    a = _empty_body(FULL_PLAN[0])
    b = json.loads(json.dumps(a))
    b["options"]["num_ctx"] = 4096.0
    assert drv.observed_meta([a, a]) == request_meta()
    with pytest.raises(drv.SentBodyMismatchError, match="uniform"):
        drv.observed_meta([a, b])
    assert drv.meta_matches_frozen(request_meta())
    assert not drv.meta_matches_frozen({**request_meta(), "think": 0})
    assert not drv.meta_matches_frozen({**request_meta(), "num_ctx": 4096.0})
    assert not drv.meta_matches_frozen({**request_meta(), "extra": 1})


# ---------------------------------------------------- 再送と raw=null

TARGET = 21  # 短縮 plan の中 (r = 12, t = 2, 軸 C の 2 番目の世界)


def test_resend_with_the_same_seed_recovers(
    tmp_path: Path, short_plan: tuple[object, ...]
) -> None:
    reason, ollama = do_run(tmp_path / "run", failing(TARGET, 3, connect_error))
    assert reason != drv.REASON_TRANSPORT
    target = ollama.answered[TARGET]
    same = [b for b in ollama.bodies if b == target]
    assert len(same) == 4  # 失敗 3 + 成功 1、全て同じ seed と messages
    assert len(ollama.bodies) == N_SHORT + 3
    attempts = [
        json.loads(line)
        for line in (tmp_path / "run" / "attempts.jsonl")
        .read_text("utf-8")
        .splitlines()
    ]
    mine = [a for a in attempts if a["call_index"] == TARGET]
    assert [a["outcome"] for a in mine] == ["transport_failure"] * 3 + ["ok"]
    assert provenance(tmp_path / "run")["n_resends"] == 3
    recs = partial(tmp_path / "run")
    assert len(recs) == len(short_plan)
    assert all(r.raw is not None for r in recs)
    assert ps.chain_violations(recs) == []


@pytest.mark.parametrize("target", [0, TARGET])
def test_unresolved_transport_failure_records_null_and_stops(
    tmp_path: Path, target: int
) -> None:
    """再送 3 回で解けなければ raw=null を書いて止まる.

    公開しない。凍結 evaluate は not_computed。
    """
    run_dir = tmp_path / "run"
    reason, ollama = do_run(run_dir, failing(target, 4, connect_error))
    _not_published(run_dir)
    assert reason == drv.REASON_TRANSPORT
    recs = partial(run_dir)
    assert len(recs) == target + 1
    assert recs[-1].raw is None
    assert recs[-1].parsed is None
    assert all(r.raw is not None for r in recs[:-1])
    assert len(ollama.bodies) == target + 4
    assert provenance(run_dir)["frozen_validate"] is None
    rep = evaluate(run_dir / drv.PARTIAL_NAME, run_dir)
    assert rep["status"] == ps.STATUS_NOT_COMPUTED
    assert rep["reasons"] == ["transport_failure"]
    assert drv.EXIT_CODES[reason] != 0


def test_read_timeout_is_a_transport_failure(tmp_path: Path) -> None:
    reason, _ = do_run(
        tmp_path / "run", failing(3, 4, lambda: httpx.ReadTimeout("slow"))
    )
    assert reason == drv.REASON_TRANSPORT
    assert len(partial(tmp_path / "run")) == 4


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
    recs = partial(tmp_path / "run")
    assert len(recs) == 1
    assert recs[0].raw is None


def test_null_content_is_a_transport_failure_not_bottom(tmp_path: Path) -> None:
    def null_at(index: int, body: dict[str, Any]) -> str | None:
        return None if index == TARGET else first_shown(index, body)

    reason, ollama = do_run(tmp_path / "run", null_at)
    assert reason == drv.REASON_TRANSPORT
    recs = partial(tmp_path / "run")
    assert len(recs) == TARGET + 1
    assert recs[-1].raw is None
    assert len(ollama.bodies) == TARGET + 4


def test_other_exceptions_abort_without_a_null_row(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    with pytest.raises(ValueError, match="bug"):
        do_run(run_dir, failing(TARGET, 1, lambda: ValueError("bug")))
    recs = partial(run_dir)
    assert len(recs) == TARGET
    assert all(r.raw is not None for r in recs)
    assert provenance(run_dir)["exit_reason"] == drv.REASON_ABORTED
    _not_published(run_dir)


def test_run_refuses_a_non_empty_run_dir(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / drv.PARTIAL_NAME).write_text("partial\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        do_run(run_dir, first_shown)
    assert (run_dir / drv.PARTIAL_NAME).read_text(encoding="utf-8") == "partial\n"
    assert not (run_dir / "provenance.json").exists()


# ------------------------------------------------------------ 公開


def test_incomplete_run_is_not_published(
    tmp_path: Path, short_plan: tuple[object, ...]
) -> None:
    """全件を呼び終えても、凍結 validate が computed でなければ公開しない.

    ここでは件数不足 (短縮 plan) で not_computed になる。
    """
    run_dir = tmp_path / "run"
    reason, _ = do_run(run_dir, first_shown)
    _not_published(run_dir)
    assert reason == drv.REASON_ABORTED
    prov = provenance(run_dir)
    assert prov["frozen_validate"] == {
        "status": ps.STATUS_NOT_COMPUTED,
        "reasons": ["incomplete"],
    }
    assert prov["error"].startswith("frozen validate")
    assert prov["anomalies"] == []
    assert prov["manifest_problems_at_publication"] == []
    assert len(partial(run_dir)) == len(short_plan)


def _copy_run(src: Path, dst: Path) -> Path:
    dst.mkdir()
    shutil.copyfile(src / drv.RECORDS_NAME, dst / drv.PARTIAL_NAME)
    shutil.copyfile(src / drv.META_NAME, dst / drv.META_NAME)
    return dst


def test_frozen_status_reads_the_partial_like_the_judge(
    varying_run: Run, tmp_path: Path
) -> None:
    """公開条件の凍結 validate は、判定と同じ reader で partial を読む.

    1 行の parsed・1 行の欠け・meta の値・読めない記録で computed でなくなる。
    """
    src, _, _ = varying_run
    ok = _copy_run(src, tmp_path / "ok")
    assert drv.frozen_status(ok) == (ps.STATUS_COMPUTED, [])

    bad_parse = _copy_run(src, tmp_path / "parse")
    lines = lines_of(bad_parse / drv.PARTIAL_NAME)
    obj = json.loads(lines[100])
    obj["parsed"] = next(a for a in bat.ACTIONS if a != obj["parsed"])
    lines[100] = json.dumps(obj, ensure_ascii=True, sort_keys=True)
    (bad_parse / drv.PARTIAL_NAME).write_text("\n".join(lines) + "\n", "utf-8")
    assert drv.frozen_status(bad_parse) == (ps.STATUS_INVALID, ["parse"])

    short = _copy_run(src, tmp_path / "short")
    lines = lines_of(short / drv.PARTIAL_NAME)
    (short / drv.PARTIAL_NAME).write_text("\n".join(lines[:-1]) + "\n", "utf-8")
    assert drv.frozen_status(short) == (ps.STATUS_NOT_COMPUTED, ["incomplete"])

    meta = _copy_run(src, tmp_path / "meta")
    (meta / drv.META_NAME).write_text(
        json.dumps({**request_meta(), "num_ctx": 2048}), "utf-8"
    )
    assert drv.frozen_status(meta) == (ps.STATUS_INVALID, ["request_meta_mismatch"])

    split = _copy_run(src, tmp_path / "split")
    text = (split / drv.PARTIAL_NAME).read_text("utf-8")
    (split / drv.PARTIAL_NAME).write_text(text.replace("\\u2028", "\u2028"), "utf-8")
    assert drv.frozen_status(split)[0] == "unreadable"

    missing = tmp_path / "missing"
    missing.mkdir()
    assert drv.frozen_status(missing)[0] == "unreadable"


def test_publish_refuses_to_overwrite(tmp_path: Path) -> None:
    (tmp_path / drv.PARTIAL_NAME).write_text("new\n", encoding="utf-8")
    (tmp_path / drv.RECORDS_NAME).write_text("old\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        drv.publish(tmp_path)
    assert (tmp_path / drv.RECORDS_NAME).read_text(encoding="utf-8") == "old\n"
    (tmp_path / drv.RECORDS_NAME).unlink()
    drv.publish(tmp_path)
    assert (tmp_path / drv.RECORDS_NAME).read_text(encoding="utf-8") == "new\n"
    assert not (tmp_path / drv.PARTIAL_NAME).exists()


@pytest.mark.usefixtures("short_run")
def test_publication_is_two_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """公開は二相 (Codex MEDIUM-1)。陽性対照を兼ねる.

    異常の無い run は公開される。rename の時点の来歴は未公開 (aborted・pending)。
    rename の後に公開済み (completed・published) へ書き直す。
    """
    seen: list[dict[str, Any]] = []
    original = drv.publish

    def spy(run_dir: Path) -> None:
        seen.append(provenance(run_dir))
        original(run_dir)

    monkeypatch.setattr(drv, "publish", spy)
    run_dir = tmp_path / "run"
    reason, _ = do_run(run_dir, first_shown)
    assert reason == drv.REASON_COMPLETED
    assert len(seen) == 1
    before = seen[0]
    assert before["exit_reason"] == drv.REASON_ABORTED
    assert before["publishable"] is True
    assert before["published"] is False
    assert before["error"] == drv.PENDING_NOTE
    after = provenance(run_dir)
    assert after["exit_reason"] == drv.REASON_COMPLETED
    assert after["published"] is True
    assert after["error"] is None
    assert (run_dir / drv.RECORDS_NAME).exists()
    assert not (run_dir / drv.PARTIAL_NAME).exists()


@pytest.mark.usefixtures("short_run")
def test_publication_failure_is_recorded_as_aborted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(_run_dir: Path) -> None:
        msg = "disk full"
        raise OSError(msg)

    monkeypatch.setattr(drv, "publish", fail)
    run_dir = tmp_path / "run"
    reason, _ = do_run(run_dir, first_shown)
    assert reason == drv.REASON_ABORTED
    prov = provenance(run_dir)
    assert prov["exit_reason"] == drv.REASON_ABORTED
    assert prov["published"] is False
    assert "publication failed: OSError: disk full" in prov["error"]
    assert not (run_dir / drv.RECORDS_NAME).exists()


@pytest.mark.usefixtures("short_run")
def test_final_provenance_failure_keeps_a_published_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rename の後に 2 相目の来歴が書けなくても、公開済み (completed) を覆さない.

    来歴は 1 相目 (aborted・pending) のまま残る。
    DV-5 の「rename と 2 相目の間で kill された run」と同じ状態。
    """
    original = drv.write_json_durable

    def failing_rewrite(path: Path, obj: object, *, exclusive: bool) -> None:
        if path.name == "provenance.json" and not exclusive:
            msg = "disk full"
            raise OSError(msg)
        original(path, obj, exclusive=exclusive)

    monkeypatch.setattr(drv, "write_json_durable", failing_rewrite)
    run_dir = tmp_path / "run"
    reason, _ = do_run(run_dir, first_shown)
    assert reason == drv.REASON_COMPLETED
    assert (run_dir / drv.RECORDS_NAME).exists()
    prov = provenance(run_dir)
    assert prov["published"] is False
    assert prov["exit_reason"] == drv.REASON_ABORTED
    assert prov["error"] == drv.PENDING_NOTE


@pytest.mark.usefixtures("short_plan")
def test_provenance_failure_keeps_the_original_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """非 transport 例外で止まった後に来歴が書けなくても、元の例外を隠さない.

    来歴の失敗は、元の例外に注記として足す。
    """

    original = drv.write_json_durable

    def no_provenance(path: Path, obj: object, *, exclusive: bool) -> None:
        if path.name == "provenance.json":
            msg = "disk full"
            raise OSError(msg)
        original(path, obj, exclusive=exclusive)

    monkeypatch.setattr(drv, "write_json_durable", no_provenance)
    with pytest.raises(ValueError, match="bug") as info:
        do_run(tmp_path / "run", failing(3, 1, lambda: ValueError("bug")))
    assert any(
        "provenance / publication failed: OSError: disk full" in note
        for note in getattr(info.value, "__notes__", [])
    )


@pytest.mark.usefixtures("short_run")
def test_manifest_failure_at_publication_blocks_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run.sh が照合する凍結 manifest が、公開の時点で OK でなければ公開しない.

    Codex MEDIUM-2。
    """
    monkeypatch.setattr(drv, "manifest_problems", lambda: ["boom"])
    run_dir = tmp_path / "run"
    reason, _ = do_run(run_dir, first_shown)
    _not_published(run_dir)
    assert reason == drv.REASON_ABORTED
    prov = provenance(run_dir)
    assert prov["manifest_problems_at_publication"] == ["boom"]
    assert "manifest at publication" in prov["error"]
    assert prov["frozen_validate"] is None


def test_complete_run_with_an_anomaly_is_not_published(tmp_path: Path) -> None:
    """Full plan で、来歴の異常だけで公開しない (Codex HIGH-1).

    この run は、凍結 validate なら computed になる。
    """
    run_dir = tmp_path / "run"
    reason, _ = do_run(run_dir, first_shown, model="qwen3:4b")
    _not_published(run_dir)
    assert reason == drv.REASON_ABORTED
    prov = provenance(run_dir)
    assert "unexpected response models" in prov["error"]
    assert prov["n_records"] == N_PLAN
    assert prov["frozen_validate"] is None
    assert drv.frozen_status(run_dir) == (ps.STATUS_COMPUTED, [])


# --------------------------------------------------- meta・provenance・preflight


def test_meta_is_observed_and_matches_frozen(varying_run: Run) -> None:
    run_dir, _, _ = varying_run
    meta = json.loads((run_dir / drv.META_NAME).read_text(encoding="utf-8"))
    assert drv.meta_matches_frozen(meta)
    prov = provenance(run_dir)
    assert prov["meta_matches_frozen"] is True
    assert prov["response_models"] == [v2bat.MODEL]
    assert prov["endpoint"] == drv.DEFAULT_ENDPOINT
    assert prov["model_digest_start"] == prov["model_digest_end"] == DIGEST
    assert prov["pinned_changed"] == []
    assert set(prov["pinned_sha256_start"]) == set(drv.PINNED)


@pytest.mark.usefixtures("short_run")
def test_meta_is_written_from_sent_values_not_constants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """照合を外し温度をずらす.

    meta は送った値 0.71、aborted、公開しない、判定は invalid。
    """
    monkeypatch.setattr(drv, "check_sent_body", lambda _body, _exp: None)
    monkeypatch.setattr(
        drv,
        "SAMPLING",
        drv.ResolvedSampling(temperature=0.71, top_p=0.8, repeat_penalty=1.0),
    )
    run_dir = tmp_path / "run"
    reason, _ = do_run(run_dir, first_shown)
    _not_published(run_dir)
    assert reason == drv.REASON_ABORTED
    prov = provenance(run_dir)
    assert prov["meta_matches_frozen"] is False
    assert "frozen meta" in prov["error"]
    assert prov["frozen_validate"] is None
    meta = json.loads((run_dir / drv.META_NAME).read_text(encoding="utf-8"))
    assert meta["temperature"] == 0.71
    rep = evaluate(run_dir / drv.PARTIAL_NAME, run_dir)
    assert rep["status"] == ps.STATUS_INVALID
    assert rep["reasons"] == ["request_meta_mismatch"]


@pytest.mark.usefixtures("short_run")
@pytest.mark.parametrize(
    "change", [{"temperature": 0.9}, {"num_ctx": 4096.0}, {"think": 0}]
)
def test_meta_file_changed_during_the_run_is_an_anomaly(
    tmp_path: Path, change: dict[str, Any]
) -> None:
    """meta.json は送った値の記録.

    実走中に書き換わったら (送った値と違えば) 公開しない。
    """
    run_dir = tmp_path / "run"

    def policy(index: int, body: dict[str, Any]) -> str:
        if index == 5:
            (run_dir / drv.META_NAME).write_text(
                json.dumps({**request_meta(), **change}), encoding="utf-8"
            )
        return first_shown(index, body)

    reason, _ = do_run(run_dir, policy)
    _not_published(run_dir)
    assert reason == drv.REASON_ABORTED
    prov = provenance(run_dir)
    assert prov["meta_matches_frozen"] is False
    assert "frozen meta" in prov["error"]


def test_shifted_sampling_aborts_before_sending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        drv,
        "SAMPLING",
        drv.ResolvedSampling(temperature=0.71, top_p=0.8, repeat_penalty=1.0),
    )
    run_dir = tmp_path / "run"
    with pytest.raises(drv.SentBodyMismatchError, match="temperature"):
        do_run(run_dir, first_shown)
    assert not (run_dir / drv.PARTIAL_NAME).read_text(encoding="utf-8")
    assert not (run_dir / drv.META_NAME).exists()
    prov = provenance(run_dir)
    assert prov["exit_reason"] == drv.REASON_ABORTED
    assert "SentBodyMismatchError" in prov["error"]
    _not_published(run_dir)


@pytest.mark.usefixtures("short_plan")
def test_seed_and_prompt_are_recorded_from_the_sent_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """照合を外し、adapter が組んだ body の seed を +1・prompt をずらす.

    記録は送った値 (描き直した値でも凍結値でもない) になり、判定は invalid (schedule)。
    """
    build = drv.OllamaChatClient._build_body

    def shifted(self: Any, *args: Any) -> dict[str, Any]:
        body = build(self, *args)
        body["messages"][-1]["content"] += " "
        body["options"]["seed"] += 1
        return body

    monkeypatch.setattr(drv, "check_sent_body", lambda _body, _exp: None)
    monkeypatch.setattr(drv.OllamaChatClient, "_build_body", shifted)
    run_dir = tmp_path / "run"
    reason, ollama = do_run(run_dir, first_shown)
    _not_published(run_dir)
    assert reason == drv.REASON_ABORTED
    recs = partial(run_dir)
    for rec, body in zip(recs, ollama.answered, strict=True):
        assert rec.seed == body["options"]["seed"]
        assert rec.prompt_sha256 == messages_sha256(body["messages"])
        assert body["messages"][-1]["content"].endswith(" ")
    assert recs[0].seed == bat.pilot_seed(FULL_PLAN[0].replicate, 0) + 1
    rep = evaluate(run_dir / drv.PARTIAL_NAME, run_dir)
    assert rep["status"] == ps.STATUS_INVALID
    assert rep["reasons"] == ["schedule"]
    assert provenance(run_dir)["frozen_validate"] == {
        "status": ps.STATUS_INVALID,
        "reasons": ["schedule"],
    }


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
        seen.append((run_dir / drv.META_NAME).exists())
        if index == 3:
            raise ValueError("stop here")
        return first_shown(index, body)

    with pytest.raises(ValueError, match="stop here"):
        do_run(run_dir, policy)
    assert seen[0] is False
    assert all(seen[1:])
    meta = json.loads((run_dir / drv.META_NAME).read_text(encoding="utf-8"))
    assert drv.meta_matches_frozen(meta)


@pytest.mark.usefixtures("short_run")
def test_model_digest_change_aborts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    reason, _ = do_run(run_dir, first_shown, digests=(DIGEST, "sha256:" + "1" * 64))
    _not_published(run_dir)
    assert reason == drv.REASON_ABORTED
    prov = provenance(run_dir)
    assert "digest changed" in prov["error"]
    assert prov["model_digest_start"] != prov["model_digest_end"]
    assert prov["frozen_validate"] is None


def test_final_preflight_is_resent(tmp_path: Path) -> None:
    """終了時の digest 再確認は再送する: 1 回落ちても digest が取れる."""
    run_dir = tmp_path / "run"
    reason, _ = do_run(
        run_dir, failing(3, 4, connect_error), preflight_down=frozenset({1})
    )
    assert reason == drv.REASON_TRANSPORT
    prov = provenance(run_dir)
    assert prov["model_digest_end"] == DIGEST
    assert prov["error"] is None


@pytest.mark.usefixtures("short_run")
def test_final_preflight_failure_aborts_a_finished_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    down = frozenset(range(1, 1 + 1 + drv.RESENDS))
    reason, _ = do_run(run_dir, first_shown, preflight_down=down)
    _not_published(run_dir)
    assert reason == drv.REASON_ABORTED
    prov = provenance(run_dir)
    assert "final preflight failed" in prov["error"]
    assert prov["model_digest_end"] is None
    assert prov["frozen_validate"] is None


def test_final_preflight_failure_keeps_a_transport_failure(tmp_path: Path) -> None:
    """Ollama が落ちたままでも、transport 失敗で止まった run は transport_failure."""
    down = frozenset(range(1, 1 + 1 + drv.RESENDS))
    run_dir = tmp_path / "run"
    reason, _ = do_run(run_dir, failing(3, 4, connect_error), preflight_down=down)
    assert reason == drv.REASON_TRANSPORT
    prov = provenance(run_dir)
    assert prov["exit_reason"] == drv.REASON_TRANSPORT
    assert "final preflight failed" in prov["error"]


@pytest.mark.usefixtures("short_run")
def test_unexpected_response_model_aborts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    reason, _ = do_run(run_dir, first_shown, model="qwen3:4b")
    _not_published(run_dir)
    assert reason == drv.REASON_ABORTED
    prov = provenance(run_dir)
    assert prov["response_models"] == ["qwen3:4b"]
    assert "response models" in prov["error"]
    assert prov["frozen_validate"] is None


@pytest.mark.usefixtures("short_run")
@pytest.mark.parametrize(
    "changed",
    [
        "scripts/closed_loop_v5_driver.py",
        "scripts/closed_loop_v5_pilot_scorer.py",
        "experiments/20260928-closed-loop-v5-calibration-pilot/run.sh",
    ],
)
def test_pinned_file_change_during_the_run_aborts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed: str,
) -> None:
    """実走中に driver・凍結物が書き換わった run は公開しない.

    開始時と終了時の PINNED の sha256 を比べる。
    """
    target = (drv._REPO_ROOT / changed).resolve()
    calls = iter(("a" * 64, "b" * 64))
    original = drv._sha256

    def sha(path: Path) -> str | None:
        if Path(path).resolve() == target:
            return next(calls)
        return original(path)

    monkeypatch.setattr(drv, "_sha256", sha)
    run_dir = tmp_path / "run"
    reason, _ = do_run(run_dir, first_shown)
    _not_published(run_dir)
    assert reason == drv.REASON_ABORTED
    prov = provenance(run_dir)
    assert prov["pinned_changed"] == [changed]
    assert prov["pinned_sha256_start"][changed] == "a" * 64
    assert "pinned files changed during the run" in prov["error"]
    assert prov["frozen_validate"] is None


def test_chat_response_helper_round_trips() -> None:
    resp = chat_response("read_book", v2bat.MODEL)
    assert resp.json()["message"]["content"] == "read_book"
