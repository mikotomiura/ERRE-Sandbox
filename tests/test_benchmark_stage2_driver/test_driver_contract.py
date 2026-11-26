"""判別性 gate 段 2 driver の契約の test (段 3.5 で足したもの、GPU なし).

変異 harness (``scripts/benchmark_stage2_driver_mutation_check.py``) の
witness。既存の ``test_driver.py`` が捕まえなかった行 (template の違い・
再実行と再生の順・期限の後の meta の読みの失敗・公開前の検査・
入場集合の外のモデル・終了コード) を pin する。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from scripts import benchmark_stage2_driver as dr
from scripts import benchmark_stage2_plan as pl

from tests.test_benchmark_stage2_driver.test_driver import (
    FakeClock,
    FakeOllama,
    _min_gate,
    _run,
    _segs,
    _status,
)

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Callable, Sequence


def _wrap(
    fake: FakeOllama, inner_handler: Callable[[httpx.Request], httpx.Response | None]
) -> None:
    """FakeOllama の handler の前に差し込む (None を返せば元の handler)."""
    inner = fake.handler

    def handler(request: httpx.Request) -> httpx.Response:
        got = inner_handler(request)
        return inner(request) if got is None else got

    fake.handler = handler  # type: ignore[method-assign]


def test_template_mismatch_invalidates_only_that_model(tmp_path: pathlib.Path) -> None:
    fake = FakeOllama(FakeClock())

    def other_template(request: httpx.Request) -> httpx.Response | None:
        if (
            request.url.path == "/api/show"
            and json.loads(request.content)["model"] == "qwen3:1.7b"
        ):
            return httpx.Response(200, json={"template": "another template"})
        return None

    _wrap(fake, other_template)
    segs = _segs()
    table = _run(tmp_path, fake, segs)
    st_ = _status(table)
    assert [st_[s.name] for s in segs if s.model == "qwen3:1.7b"] == [
        dr.S_INVALID_META
    ] * 2
    assert [st_[s.name] for s in segs if s.model == "qwen3:8b"] == [dr.S_COMPLETED] * 2
    assert "template_sha256" in table["segments"][segs[0].name]["reason"]
    assert all(c["model"] != "qwen3:1.7b" for c in fake.chats)
    # meta 違反は再実行しない
    assert table["segments"][segs[0].name]["attempts_run"] == 1


def test_retry_runs_before_the_replay(tmp_path: pathlib.Path) -> None:
    """Pilot の通信の欠測の再実行 (attempt-2) を済ませてから再生を回す (H6)."""
    segs = _segs(models=("qwen3:8b",), batteries=("v2",), replay=True)
    bad = segs[0]
    n_bad = {"n": 0}

    def fail(model: str, body: dict[str, Any], _n: int) -> bool:
        if dr.same(body, pl.body_for(bad.calls[0], model)):
            n_bad["n"] += 1
            return n_bad["n"] <= 1 + dr.RESENDS
        return False

    fake = FakeOllama(FakeClock(), fail=fail)
    table = _run(tmp_path, fake, segs)
    assert set(_status(table).values()) == {dr.S_COMPLETED}
    assert table["segments"][bad.name]["adopted_attempt"] == 2
    n_first = 1 + dr.RESENDS  # attempt-1 は先頭の呼び出しで止まる
    want: Sequence[dict[str, Any]] = [
        *(pl.body_for(c, bad.model) for c in bad.calls),  # 再実行
        *(pl.body_for(c, s.model) for s in segs[1:] for c in s.calls),  # 再生
    ]
    got = fake.chats[n_first:]
    assert len(got) == len(want)
    assert all(dr.same(a, b) for a, b in zip(got, want, strict=True))


def test_meta_read_failure_after_the_deadline_is_a_timeout(
    tmp_path: pathlib.Path,
) -> None:
    """期限を過ぎた後の meta の読みの失敗は時間切れ (通信の欠測ではない、DD-5)."""
    clock = FakeClock()
    fake = FakeOllama(clock)
    segs = _segs(models=("qwen3:8b",), batteries=("v2", "G"))
    first_done = float(len(segs[0].calls))  # chat_dt = 1 秒

    def slow_show(request: httpx.Request) -> httpx.Response | None:
        if request.url.path == "/api/show" and clock.t >= first_done:
            clock.t += 100.0  # 区切り 1 の meta の読みが期限を越えて失敗する
            return httpx.Response(500)
        return None

    _wrap(fake, slow_show)
    table = _run(tmp_path, fake, segs, deadline_s=50.0)
    assert table["segments"][segs[0].name]["status"] == dr.S_COMPLETED
    entry = table["segments"][segs[1].name]
    assert entry["status"] == dr.S_TIMEOUT
    assert entry["attempts_run"] == 1


def _record(seg: pl.Segment, index: int, spec: pl.CallSpec) -> dict[str, Any]:
    return {
        "stage": seg.stage,
        "battery": seg.battery,
        "model": seg.model,
        "attempt": 1,
        "call_index": index,
        "purpose": spec.purpose,
        "arm": spec.arm,
        "encoding": spec.encoding,
        "replicate": spec.replicate,
        "probe_id": spec.probe_id,
        "k": spec.k,
        "seed": spec.seed,
        "prompt_sha256": pl.messages_sha256(spec.messages_list()),
        "raw": "A",
        "response_model": seg.model,
        "prompt_eval_count": 1,
        "eval_count": 1,
        "done_reason": "stop",
        "n_sends": 1,
    }


def test_publication_problems_check_bytes_rows_and_keys(
    tmp_path: pathlib.Path,
) -> None:
    seg = _segs(models=("qwen3:8b",), batteries=("v2",))[0]
    adir = tmp_path / "attempt-1"
    adir.mkdir()
    meta = b'{"m": 1}\n'
    (adir / dr.META_NAME).write_bytes(meta)
    lines = [dr.record_line(_record(seg, i, c)) for i, c in enumerate(seg.calls)]

    def problems(written: list[str], told: list[str], meta_bytes: bytes = meta) -> str:
        (adir / dr.PARTIAL_NAME).write_bytes(dr.records_bytes(written))
        return "; ".join(dr.publication_problems(adir, seg, 1, told, meta_bytes))

    assert problems(lines, lines) == ""
    assert "partial differs" in problems(lines, [*lines[:-1], lines[0]])
    assert "meta.json differs" in problems(lines, lines, b"{}\n")
    assert f"{len(lines) - 1} rows for {len(lines)} calls" in problems(
        lines[:-1], lines[:-1]
    )
    shifted = _record(seg, 1, seg.calls[1])
    shifted["seed"] += 1
    bad = [lines[0], dr.record_line(shifted), *lines[2:]]
    assert "row 1: key fields differ" in problems(bad, bad)
    swapped = [lines[1], lines[0], *lines[2:]]
    assert "row 0: key fields differ" in problems(swapped, swapped)
    null = _record(seg, 0, seg.calls[0])
    null["raw"] = None
    bad = [dr.record_line(null), *lines[1:]]
    assert "row 0: raw is not a string" in problems(bad, bad)


def test_plan_for_refuses_a_model_outside_the_entrants(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = tmp_path / "gate.json"
    gate.write_text(json.dumps(_min_gate({"O_time": 6})), encoding="utf-8")
    real = pl.main_plan
    # 入場集合を無視する plan (全 6 モデル) を渡しても、driver が本走の前に拒む
    monkeypatch.setattr(pl, "main_plan", lambda r, _models=None: real(r))
    with pytest.raises(dr.PreflightError, match="outside the pilot entrants"):
        dr.plan_for(pl.STAGE_MAIN, gate)


def test_main_exit_codes(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = ["--stage", pl.STAGE_PILOT, "--run-dir", str(tmp_path)]
    monkeypatch.setattr(dr, "plan_for", lambda _stage, _gate: ())

    def fake_run(statuses: Sequence[str]) -> Callable[..., Any]:
        async def run(*_a: object, **_k: object) -> dict[str, Any]:
            return {"segments": {str(i): {"status": s} for i, s in enumerate(statuses)}}

        return run

    monkeypatch.setattr(dr, "run_stage", fake_run([dr.S_COMPLETED] * 2))
    assert dr.main(args) == dr.EXIT_OK
    monkeypatch.setattr(dr, "run_stage", fake_run([dr.S_COMPLETED, dr.S_TRANSPORT]))
    assert dr.main(args) == dr.EXIT_INCOMPLETE

    def refuse(_stage: str, _gate: object) -> tuple[pl.Segment, ...]:
        msg = "no gate"
        raise dr.PreflightError(msg)

    monkeypatch.setattr(dr, "plan_for", refuse)
    assert dr.main(args) == dr.EXIT_REFUSED


def test_registered_run_constants() -> None:
    """§A.1・§H の値そのもの.

    ``test_driver.py`` は driver の定数から期待値を作るので、定数の誤りを捕まえない。
    """
    assert dr.RESENDS == 3
    assert dr.BACKOFF_SCHEDULE_S == (5.0, 30.0, 120.0)
    assert dr.MAX_ATTEMPTS == 2
    assert dr.DEADLINE_S == {pl.STAGE_PILOT: 12 * 3600.0, pl.STAGE_MAIN: 36 * 3600.0}
    assert dr.OLLAMA_VERSION == "0.32.12"
    models = json.loads(dr.MODELS_JSON.read_text(encoding="utf-8"))
    assert models["ollama_version"] == dr.OLLAMA_VERSION


def test_version_mismatch_at_start_touches_no_segment(tmp_path: pathlib.Path) -> None:
    fake = FakeOllama(FakeClock(), version="0.33.0")
    _run(tmp_path, fake, _segs())
    root = tmp_path / "run" / pl.STAGE_PILOT
    assert sorted(p.name for p in root.iterdir()) == sorted(
        [dr.SEGMENTS_NAME, dr.ACCOUNTING_NAME]
    )
    assert fake.n_version == 1  # 区切りの meta の読みもしない


def test_main_stage_rejects_a_replay_segment(tmp_path: pathlib.Path) -> None:
    main = pl.Segment(pl.STAGE_MAIN, "v2", "qwen3:8b", pl.main_calls("v2", 8)[:1])
    replay = pl.Segment(pl.STAGE_REPLAY, "G", pl.REPLAY_MODEL, pl.replay_calls("G")[:1])
    with pytest.raises(ValueError, match="does not belong"):
        _run(tmp_path, FakeOllama(FakeClock()), (main, replay), stage=pl.STAGE_MAIN)


def test_read_gate_refuses_an_r_without_three_entrants() -> None:
    gate = _min_gate({"v3": 8})
    dr.read_gate(gate)
    gate["batteries"]["G"]["R"] = 6  # NOT_QUALIFIED の battery に R
    with pytest.raises(dr.PreflightError, match="NOT_QUALIFIED with >= 3 entrants"):
        dr.read_gate(gate)


def test_last_resend_failing_after_the_deadline_is_a_timeout(
    tmp_path: pathlib.Path,
) -> None:
    """4 回目の送信が期限を越えて失敗したら時間切れ (通信の欠測の行を書かない)."""
    seg = _segs(models=("qwen3:8b",), batteries=("v2",))
    fake = FakeOllama(FakeClock(), fail=lambda _m, _b, _n: True)
    # 送信 1 秒 × 3 + backoff 155 秒 = 158 秒で 4 回目を送り、159 秒で失敗が返る
    table = _run(tmp_path, fake, seg, deadline_s=158.5)
    assert len(fake.chats) == 1 + dr.RESENDS
    entry = table["segments"][seg[0].name]
    assert entry["status"] == dr.S_TIMEOUT
    adir = dr.attempt_dir(
        dr.segment_dir(tmp_path / "run" / pl.STAGE_PILOT, pl.STAGE_PILOT, seg[0]), 1
    )
    assert (adir / dr.PARTIAL_NAME).read_bytes() == b""


def test_request_timeout_is_cut_at_the_deadline(tmp_path: pathlib.Path) -> None:
    """1 request の timeout は min(TIMEOUT_S, 期限の残り) (期限の後の応答を採らない)."""
    fake = FakeOllama(FakeClock(), chat_dt=10.0)
    seen: list[float] = []

    def record(request: httpx.Request) -> httpx.Response | None:
        if request.url.path == "/api/chat":
            seen.append(request.extensions["timeout"]["read"])
        return None

    _wrap(fake, record)
    _run(
        tmp_path, fake, _segs(models=("qwen3:8b",), batteries=("v2",)), deadline_s=100.0
    )
    assert seen == [100.0, 90.0, 80.0]


def test_read_gate_refuses_an_unregistered_battery() -> None:
    gate = _min_gate({"v3": 8})
    gate["batteries"]["v4"] = dict(gate["batteries"]["v2"])  # 登録の 4 battery の外
    with pytest.raises(dr.PreflightError, match="registered 4"):
        dr.read_gate(gate)
