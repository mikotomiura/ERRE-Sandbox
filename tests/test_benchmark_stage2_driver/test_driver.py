"""判別性 gate 段 2 driver の test (FakeOllama = ``httpx.MockTransport``、GPU なし)."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from scripts import benchmark_stage2_driver as dr
from scripts import benchmark_stage2_plan as pl
from scripts import benchmark_stage2_stats as st

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Callable, Sequence

N_CALLS = 3  # 区切りごとの呼び出し数 (pilot_plan の区切りの先頭を切って使う)


def _template(model: str) -> str:
    return f"{{{{ .Prompt }}}} template of {model}"


def _reference() -> dict[str, Any]:
    return {
        "ollama_version": dr.OLLAMA_VERSION,
        "models": {
            m: {
                "model_digest": f"digest-{m}",
                "template_sha256": hashlib.sha256(_template(m).encode()).hexdigest(),
            }
            for m in pl.MODELS
        },
    }


@dataclass
class FakeClock:
    t: float = 0.0
    slept: list[float] = field(default_factory=list)

    def now(self) -> float:
        return self.t

    async def sleep(self, s: float) -> None:
        self.slept.append(s)
        self.t += s

    def clock(self) -> dr.Clock:
        return dr.Clock(now=self.now, sleep=self.sleep)


@dataclass
class FakeOllama:
    """``/api/version``・``/api/tags``・``/api/show``・``/api/chat``.

    chat は fail(model, body, n) が真なら 503.
    """

    clock: FakeClock
    version: str | Callable[[int], str] = dr.OLLAMA_VERSION
    digests: dict[str, str] = field(
        default_factory=lambda: {m: f"digest-{m}" for m in pl.MODELS}
    )
    fail: Callable[[str, dict[str, Any], int], bool] = lambda _m, _b, _n: False
    content: str = "A"
    chat_dt: float = 1.0
    chats: list[dict[str, Any]] = field(default_factory=list)
    n_version: int = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/version":
            self.n_version += 1
            v = self.version(self.n_version) if callable(self.version) else self.version
            return httpx.Response(200, json={"version": v})
        if path == "/api/tags":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": m, "model": m, "digest": d}
                        for m, d in self.digests.items()
                    ]
                },
            )
        if path == "/api/show":
            model = json.loads(request.content)["model"]
            return httpx.Response(200, json={"template": _template(model)})
        if path == "/api/chat":
            body = json.loads(request.content)
            n = len(self.chats)
            self.chats.append(body)
            self.clock.t += self.chat_dt
            if self.fail(body["model"], body, n):
                return httpx.Response(503, text="busy")
            return httpx.Response(
                200,
                json={
                    "model": body["model"],
                    "message": {"role": "assistant", "content": self.content},
                    "done_reason": "stop",
                    "prompt_eval_count": 17,
                    "eval_count": 2,
                },
            )
        return httpx.Response(404)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)


def _segs(
    models: Sequence[str] = ("qwen3:1.7b", "qwen3:8b"),
    batteries: Sequence[str] = ("v2", "G"),
    *,
    replay: bool = False,
    n: int = N_CALLS,
) -> tuple[pl.Segment, ...]:
    by_name = {s.name: s for s in pl.pilot_plan()}
    out = [
        pl.Segment(pl.STAGE_PILOT, b, m, by_name[f"pilot/{b}/{m}"].calls[:n])
        for m in models
        for b in batteries
    ]
    if replay:
        out += [
            pl.Segment(pl.STAGE_REPLAY, b, pl.REPLAY_MODEL, pl.replay_calls(b)[:n])
            for b in ("G", "O_time")
        ]
    return tuple(out)


def _run(
    tmp_path: pathlib.Path,
    fake: FakeOllama,
    segs: Sequence[pl.Segment],
    *,
    deadline_s: float | None = None,
    stage: str = pl.STAGE_PILOT,
) -> dict[str, Any]:
    return asyncio.run(
        dr.run_stage(
            stage,
            tmp_path / "run",
            segs,
            transport=fake.transport(),
            endpoint="http://fake",
            reference=_reference(),
            clock=fake.clock.clock(),
            deadline_s=deadline_s,
        )
    )


def _status(table: dict[str, Any]) -> dict[str, str]:
    return {k: v["status"] for k, v in table["segments"].items()}


def _adir(tmp_path: pathlib.Path, seg: pl.Segment, attempt: int) -> pathlib.Path:
    root = tmp_path / "run" / pl.STAGE_PILOT
    return dr.attempt_dir(dr.segment_dir(root, pl.STAGE_PILOT, seg), attempt)


def _rows(path: pathlib.Path) -> list[dict[str, Any]]:
    text = path.read_bytes().decode("ascii")
    assert text.endswith("\n")
    return [json.loads(line) for line in text.split("\n")[:-1]]


# ------------------------------------------------------------ 順・記録・公開


def test_runs_segments_in_order_and_publishes(tmp_path: pathlib.Path) -> None:
    clock = FakeClock()
    fake = FakeOllama(clock, content="A\n B")
    segs = _segs()
    table = _run(tmp_path, fake, segs)
    assert table["order"] == [s.name for s in segs]
    assert set(_status(table).values()) == {dr.S_COMPLETED}
    # 送った順 = 区切りの順 × 区切り内の呼び出しの順。body は plan と型まで一致
    want = [pl.body_for(c, s.model) for s in segs for c in s.calls]
    assert len(fake.chats) == len(want)
    assert all(dr.same(a, b) for a, b in zip(fake.chats, want, strict=True))
    stage_root = tmp_path / "run" / pl.STAGE_PILOT
    assert not (stage_root / dr.SEGMENTS_PARTIAL_NAME).exists()
    on_disk = json.loads((stage_root / dr.SEGMENTS_NAME).read_text(encoding="utf-8"))
    assert on_disk == table
    for seg in segs:
        adir = _adir(tmp_path, seg, 1)
        assert not (adir / dr.PARTIAL_NAME).exists()
        data = (adir / dr.RECORDS_NAME).read_bytes()
        entry = table["segments"][seg.name]
        assert entry["adopted_attempt"] == 1
        assert entry["records_sha256"] == hashlib.sha256(data).hexdigest()
        assert (
            entry["meta_sha256"]
            == hashlib.sha256((adir / dr.META_NAME).read_bytes()).hexdigest()
        )
        assert entry["segment_digest"] == pl.segment_digest(seg)
        assert entry["n_calls"] == len(seg.calls)
        rows = _rows(adir / dr.RECORDS_NAME)  # U+2028 と改行があっても 1 呼び出し 1 行
        assert len(rows) == len(seg.calls)
        for i, (row, spec) in enumerate(zip(rows, seg.calls, strict=True)):
            assert set(row) == dr.RECORD_KEYS
            assert row["call_index"] == i
            assert (row["arm"], row["replicate"], row["probe_id"], row["k"]) == (
                spec.arm,
                spec.replicate,
                spec.probe_id,
                spec.k,
            )
            assert row["seed"] == spec.seed
            assert row["prompt_sha256"] == pl.messages_sha256(spec.messages_list())
            assert row["raw"] == "A\n B"
            assert row["n_sends"] == 1
            assert row["prompt_eval_count"] == 17
        meta = json.loads((adir / dr.META_NAME).read_text(encoding="utf-8"))
        assert meta["template"] == _template(seg.model)
        assert meta["model_digest"] == f"digest-{seg.model}"
        assert meta["ollama_version"] == dr.OLLAMA_VERSION
        assert meta["request"]["options_without_seed"] == pl.DECODE
        assert meta["segment_digest"] == pl.segment_digest(seg)
        assert meta["plan_digest"] == pl.plan_digest(segs)
    acc = json.loads((stage_root / dr.ACCOUNTING_NAME).read_text(encoding="utf-8"))
    assert acc["sends"][dr.C_INITIAL] == len(want)
    assert acc["sends"][dr.C_RESEND] == 0


def test_record_lines_are_ascii_sorted(tmp_path: pathlib.Path) -> None:
    fake = FakeOllama(FakeClock(), content="日本")
    seg = _segs(models=("qwen3:8b",), batteries=("v2",))
    _run(tmp_path, fake, seg)
    for line in (
        (_adir(tmp_path, seg[0], 1) / dr.RECORDS_NAME)
        .read_text("ascii")
        .split("\n")[:-1]
    ):
        assert line == json.dumps(json.loads(line), ensure_ascii=True, sort_keys=True)


def test_refuses_non_empty_run_dir(tmp_path: pathlib.Path) -> None:
    (tmp_path / "run" / pl.STAGE_PILOT).mkdir(parents=True)
    (tmp_path / "run" / pl.STAGE_PILOT / "x").write_text("old", encoding="utf-8")
    fake = FakeOllama(FakeClock())
    with pytest.raises(dr.PreflightError):
        _run(tmp_path, fake, _segs())
    assert fake.chats == []


# ------------------------------------------------------------ 再送・再実行


def test_resend_resolves_within_three(tmp_path: pathlib.Path) -> None:
    clock = FakeClock()
    # 最初の呼び出しだけ 3 回失敗して 4 回目で返る
    fake = FakeOllama(clock, fail=lambda _m, _b, n: n < 3)
    segs = _segs(models=("qwen3:8b",), batteries=("v2",))
    table = _run(tmp_path, fake, segs)
    assert _status(table) == {segs[0].name: dr.S_COMPLETED}
    assert clock.slept == list(dr.BACKOFF_SCHEDULE_S)
    rows = _rows(_adir(tmp_path, segs[0], 1) / dr.RECORDS_NAME)
    assert [r["n_sends"] for r in rows] == [4, 1, 1]
    # 再送は同じ body
    assert all(dr.same(fake.chats[i], fake.chats[0]) for i in range(4))
    acc = json.loads(
        (tmp_path / "run" / pl.STAGE_PILOT / dr.ACCOUNTING_NAME).read_text("utf-8")
    )
    assert acc["sends"][dr.C_INITIAL] == 3
    assert acc["sends"][dr.C_RESEND] == 3
    attempts = _rows(_adir(tmp_path, segs[0], 1) / dr.ATTEMPTS_NAME)
    assert [a["outcome"] for a in attempts[:4]] == ["transport_failure"] * 3 + ["ok"]


def test_unresolved_segment_closes_and_next_runs_then_retry_replaces(
    tmp_path: pathlib.Path,
) -> None:
    clock = FakeClock()
    segs = _segs()
    bad = segs[0]
    n_bad = {"n": 0}

    def fail(model: str, body: dict[str, Any], _n: int) -> bool:
        # 区切り 0 (qwen3:1.7b・v2) の 2 呼び出し目を attempt-1 でだけ 4 回落とす
        if model == bad.model and dr.same(body, pl.body_for(bad.calls[1], model)):
            n_bad["n"] += 1
            return n_bad["n"] <= 4
        return False

    fake = FakeOllama(clock, fail=fail)
    table = _run(tmp_path, fake, segs)
    entry = table["segments"][bad.name]
    assert entry["status"] == dr.S_COMPLETED
    assert entry["adopted_attempt"] == 2
    assert entry["attempts_run"] == 2
    # 失敗の後も次の区切りへ進み、再実行は stage の最後
    sent_models = [(c["model"], c["options"]["seed"]) for c in fake.chats]
    first_other = sent_models.index((segs[1].model, segs[1].calls[0].seed))
    retry_start = len(fake.chats) - len(bad.calls)
    assert first_other < retry_start
    assert sent_models[retry_start:] == [(bad.model, c.seed) for c in bad.calls]
    # attempt-1 は公開されず、最後の行が raw = null
    a1 = _adir(tmp_path, bad, 1)
    assert not (a1 / dr.RECORDS_NAME).exists()
    rows1 = _rows(a1 / dr.PARTIAL_NAME)
    assert len(rows1) == 2
    assert rows1[-1]["raw"] is None
    assert rows1[-1]["n_sends"] == 4
    rows2 = _rows(_adir(tmp_path, bad, 2) / dr.RECORDS_NAME)
    assert [r["attempt"] for r in rows2] == [2] * len(bad.calls)
    assert (
        entry["records_sha256"]
        == hashlib.sha256(
            (_adir(tmp_path, bad, 2) / dr.RECORDS_NAME).read_bytes()
        ).hexdigest()
    )
    acc = json.loads(
        (tmp_path / "run" / pl.STAGE_PILOT / dr.ACCOUNTING_NAME).read_text("utf-8")
    )
    assert acc["sends"][dr.C_RETRY] == len(bad.calls)
    assert acc["sends"][dr.C_RESEND] == 3


def test_retry_only_once(tmp_path: pathlib.Path) -> None:
    clock = FakeClock()
    segs = _segs(models=("qwen3:8b",), batteries=("v2", "G"))
    fake = FakeOllama(
        clock, fail=lambda _m, b, _n: b["options"]["seed"] == segs[0].calls[0].seed
    )
    table = _run(tmp_path, fake, segs)
    entry = table["segments"][segs[0].name]
    assert entry["status"] == dr.S_TRANSPORT
    assert entry["adopted_attempt"] is None
    assert entry["records_sha256"] is None
    assert entry["attempts_run"] == 2
    seg_dir = dr.segment_dir(tmp_path / "run" / pl.STAGE_PILOT, pl.STAGE_PILOT, segs[0])
    assert sorted(p.name for p in seg_dir.iterdir()) == ["attempt-1", "attempt-2"]
    assert table["segments"][segs[1].name]["status"] == dr.S_COMPLETED


# ------------------------------------------------------------ 期限


def test_deadline_during_retry(tmp_path: pathlib.Path) -> None:
    clock = FakeClock()
    segs = _segs(models=("qwen3:8b",), batteries=("v2", "G"))
    target = segs[0].calls[0].seed
    fake = FakeOllama(
        clock,
        fail=lambda _m, b, _n: b["options"]["seed"] == target,
        chat_dt=1.0,
    )
    # attempt-1: 4 sends + backoff (5 + 30 + 120) = 159 s。
    # G の 3 呼び出し = 3 s → 162 s。
    # attempt-2 の最初の失敗の後の backoff (5 s) を期限の内に収めない
    table = _run(tmp_path, fake, segs, deadline_s=165.0)
    entry = table["segments"][segs[0].name]
    assert entry["status"] == dr.S_TIMEOUT
    assert entry["attempts_run"] == 2
    assert entry["adopted_attempt"] is None
    assert table["segments"][segs[1].name]["status"] == dr.S_COMPLETED


def test_deadline_mid_segment_then_not_started(tmp_path: pathlib.Path) -> None:
    clock = FakeClock()
    fake = FakeOllama(clock, chat_dt=10.0)
    segs = _segs()
    table = _run(tmp_path, fake, segs, deadline_s=45.0)  # 4 呼び出し目の途中で期限
    st_ = _status(table)
    assert st_[segs[0].name] == dr.S_COMPLETED
    assert st_[segs[1].name] == dr.S_TIMEOUT
    assert [st_[s.name] for s in segs[2:]] == [dr.S_NOT_STARTED] * 2
    assert not (_adir(tmp_path, segs[1], 1) / dr.RECORDS_NAME).exists()
    # 未着手の区切りの dir は作らない
    assert not dr.segment_dir(
        tmp_path / "run" / pl.STAGE_PILOT, pl.STAGE_PILOT, segs[2]
    ).exists()


def test_replay_runs_last_and_only_replay_can_be_left(tmp_path: pathlib.Path) -> None:
    clock = FakeClock()
    fake = FakeOllama(clock, chat_dt=10.0)
    segs = _segs(models=("qwen3:8b",), batteries=("v2",), replay=True)
    table = _run(tmp_path, fake, segs, deadline_s=float(10 * N_CALLS))
    st_ = _status(table)
    assert st_[segs[0].name] == dr.S_COMPLETED
    assert [st_[s.name] for s in segs[1:]] == [dr.S_NOT_STARTED] * 2
    # 再生は pilot の root の下の replay/ (DD-5)
    assert (
        dr.segment_dir(
            tmp_path / "run" / pl.STAGE_PILOT, pl.STAGE_PILOT, segs[1]
        ).parts[-3]
        == pl.STAGE_REPLAY
    )


def test_replay_accounted_separately(tmp_path: pathlib.Path) -> None:
    fake = FakeOllama(FakeClock())
    segs = _segs(models=("qwen3:8b",), batteries=("v2",), replay=True)
    table = _run(tmp_path, fake, segs)
    assert set(_status(table).values()) == {dr.S_COMPLETED}
    acc = json.loads(
        (tmp_path / "run" / pl.STAGE_PILOT / dr.ACCOUNTING_NAME).read_text("utf-8")
    )
    assert acc["sends"] == {
        dr.C_INITIAL: N_CALLS,
        dr.C_RESEND: 0,
        dr.C_RETRY: 0,
        dr.C_REPLAY: 2 * N_CALLS,
    }
    want_cost = N_CALLS * st.SPECS["v2"].sec_per_call
    assert acc["cost_8b_s"][dr.C_INITIAL] == str(want_cost)
    want_replay = N_CALLS * (
        st.SPECS["G"].sec_per_call + st.SPECS["O_time"].sec_per_call
    )
    assert acc["cost_8b_s"][dr.C_REPLAY] == str(want_replay)


# ------------------------------------------------------------ meta の違反


def test_digest_mismatch_invalidates_only_that_model(tmp_path: pathlib.Path) -> None:
    fake = FakeOllama(FakeClock())
    fake.digests["qwen3:1.7b"] = "other"
    segs = _segs()
    table = _run(tmp_path, fake, segs)
    st_ = _status(table)
    assert [st_[s.name] for s in segs if s.model == "qwen3:1.7b"] == [
        dr.S_INVALID_META
    ] * 2
    assert [st_[s.name] for s in segs if s.model == "qwen3:8b"] == [dr.S_COMPLETED] * 2
    assert all(c["model"] != "qwen3:1.7b" for c in fake.chats)
    # meta 違反は再実行しない
    assert table["segments"][segs[0].name]["attempts_run"] == 1
    assert (_adir(tmp_path, segs[0], 1) / dr.META_NAME).exists()


def test_version_mismatch_at_start_invalidates_all(tmp_path: pathlib.Path) -> None:
    fake = FakeOllama(FakeClock(), version="0.33.0")
    segs = _segs()
    table = _run(tmp_path, fake, segs)
    assert set(_status(table).values()) == {dr.S_INVALID_VERSION}
    assert fake.chats == []


def test_version_change_mid_run_invalidates_all(tmp_path: pathlib.Path) -> None:
    # 起動時と最初の区切りは 0.32.12、以後は違う版
    fake = FakeOllama(
        FakeClock(), version=lambda n: dr.OLLAMA_VERSION if n <= 2 else "0.33.0"
    )
    segs = _segs()
    table = _run(tmp_path, fake, segs)
    assert set(_status(table).values()) == {dr.S_INVALID_VERSION}
    assert all(v["adopted_attempt"] is None for v in table["segments"].values())
    # 違う版を見た後の区切りには送らない (区切り 0 の 3 呼び出しだけ)
    assert len(fake.chats) == N_CALLS
    assert table["segments"][segs[2].name]["attempts_run"] == 0


def test_meta_read_failure_is_transport_and_retried(tmp_path: pathlib.Path) -> None:
    fake = FakeOllama(FakeClock())
    segs = _segs(models=("qwen3:8b",), batteries=("v2", "G"))
    n_show = {"n": 0}
    inner = fake.handler

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/show":
            n_show["n"] += 1
            if n_show["n"] == 1:
                return httpx.Response(500)
        return inner(request)

    fake.handler = handler  # type: ignore[method-assign]
    table = _run(tmp_path, fake, segs)
    entry = table["segments"][segs[0].name]
    assert entry["status"] == dr.S_COMPLETED
    assert entry["adopted_attempt"] == 2
    assert not (_adir(tmp_path, segs[0], 1) / dr.META_NAME).exists()


def test_pilot_plan_shape_for_cli() -> None:
    segs = dr.plan_for(pl.STAGE_PILOT, None)
    assert len(segs) == len(pl.MODELS) * len(st.BATTERIES) + 2
    assert [s.stage for s in segs[-2:]] == [pl.STAGE_REPLAY] * 2


def test_main_plan_from_gate_file(tmp_path: pathlib.Path) -> None:
    gate = tmp_path / "gate.json"
    gate.write_text(
        json.dumps({"batteries": {"O_time": {"gate": st.GATE_GO, "R": 6}}}),
        encoding="utf-8",
    )
    segs = dr.plan_for(pl.STAGE_MAIN, gate)
    assert [s.model for s in segs] == list(pl.MODELS)
    assert {s.battery for s in segs} == {"O_time"}
    assert all(s.stage == pl.STAGE_MAIN for s in segs)


# ------------------------------------------------------------ 送信前の照合


def test_observer_rejects_body_not_in_plan() -> None:
    spec = pl.pilot_calls("v2")[0]
    inner = httpx.MockTransport(lambda _r: httpx.Response(200, json={}))
    obs = dr.ObservingTransport(inner)

    async def go(body: dict[str, Any], path: str = "/api/chat") -> None:
        async with httpx.AsyncClient(base_url="http://fake", transport=obs) as http:
            await http.post(path, json=body)

    obs.expected = (spec, "qwen3:8b")
    good = pl.body_for(spec, "qwen3:8b")
    asyncio.run(go(good))
    assert obs.n_chat == 1
    for mutate in (
        lambda b: b["options"].__setitem__("num_ctx", 4096.0),
        lambda b: b.__setitem__("think", 0),
        lambda b: b["options"].pop("top_k"),
        lambda b: b["options"].__setitem__("seed", b["options"]["seed"] + 1),
        lambda b: b.__setitem__("model", "qwen3:14b"),
        lambda b: b.__setitem__("extra", 1),
    ):
        bad = json.loads(json.dumps(good))
        mutate(bad)
        with pytest.raises(dr.SentBodyMismatchError):
            asyncio.run(go(bad))
    with pytest.raises(dr.SentBodyMismatchError):
        asyncio.run(go(good, "/api/generate"))
    with pytest.raises(dr.SentBodyMismatchError):
        asyncio.run(go({"model": "qwen3:8b"}, "/api/show"))  # meta の読み以外
    obs.expected = None
    with pytest.raises(dr.SentBodyMismatchError):
        asyncio.run(go(good))


def test_same_distinguishes_types() -> None:
    assert dr.same({"a": [1, 0.7]}, {"a": [1, 0.7]})
    assert not dr.same(False, 0)  # noqa: FBT003
    assert not dr.same(4096.0, 4096)
    assert not dr.same({"a": 1}, {"a": 1, "b": 2})
    assert not dr.same([1], [1, 1])


# ------------------------------------------------------------ 入口


def test_run_stage_rejects_foreign_segments(tmp_path: pathlib.Path) -> None:
    segs = _segs(models=("qwen3:8b",), batteries=("v2",), replay=True)
    with pytest.raises(ValueError, match="does not belong"):
        _run(tmp_path, FakeOllama(FakeClock()), segs, stage=pl.STAGE_MAIN)


def test_main_r_from_gate() -> None:
    gate = {
        "batteries": {
            "v3": {"gate": st.GATE_GO, "R": 8},
            "G": {"gate": st.GATE_STOP_POWER, "R": None},
        }
    }
    assert dr.main_r_from_gate(gate) == {"v3": 8}
    for bad in (
        {},
        {"batteries": {"G": {"gate": st.GATE_STOP_POWER}}},
        {"batteries": {"v3": {"gate": st.GATE_GO, "R": 8.0}}},
        {"batteries": {"v3": {"gate": st.GATE_GO, "R": True}}},
        {"batteries": {"x": {"gate": st.GATE_GO, "R": 8}}},
    ):
        with pytest.raises(dr.PreflightError):
            dr.main_r_from_gate(bad)


def test_main_requires_gate() -> None:
    with pytest.raises(dr.PreflightError):
        dr.plan_for(pl.STAGE_MAIN, None)
