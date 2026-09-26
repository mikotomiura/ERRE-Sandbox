"""Skill lever driver (mock transport のみ、実モデル不使用).

driver の判定に関わる行 (送った body の照合・meta の観測・呼び出し順・C0 gate・
再送と raw=null・再開しない) を pin し、出力が凍結 scorer (``evaluate_records``) で
読めることと、mock の lookup → PASS / 一様 → NO_GO (driver → scorer の結線) を
確かめる。
"""

from __future__ import annotations

import asyncio
import json
import random
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from scripts import skill_lever_battery as bat
from scripts import skill_lever_driver as drv
from scripts import skill_lever_scorer as sc
from scripts.stage_b_scorer import (
    VERDICT_ABSENT,
    VERDICT_INVALID_BATTERY,
    VERDICT_INVALID_SCORER,
    VERDICT_PASS,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    Policy = Callable[[drv.Key, dict[str, Any]], str]

CERT = (
    Path(__file__).resolve().parents[2]
    / "experiments"
    / "20260926-skill-lever-pilot"
    / "results"
    / "v2_mutation.json"
)
N_C0 = sc.FROZEN_R * 6 * sc.FROZEN_K  # 240
N_ALL = 5 * N_C0  # 1,200


# ------------------------------------------------------------------ mock


@lru_cache(maxsize=1)
def _key_of() -> dict[tuple[str, int], drv.Key]:
    """(prompt sha256, seed) → key。mock は送られた body だけから要求を知る."""
    out = {}
    for key in drv.schedule():
        seed, sha = sc.expected_sample(*key)
        out[(sha, seed)] = key
    return out


def _options_shown(body: dict[str, Any]) -> list[str]:
    last = body["messages"][-1]["content"].rsplit("\n", 1)[-1]
    return last.split(": ", 1)[1].split("、")


def lookup(key: drv.Key, body: dict[str, Any]) -> str:
    """規則を読むモデル: lever arm は自 arm の規則が指す選択肢、C0 は表示先頭."""
    arm, _, qi, _ = key
    if arm == bat.ARM_C0:
        return _options_shown(body)[0]
    return bat.lever_probes()[qi].pointed[arm]


def uniform(_key: drv.Key, body: dict[str, Any]) -> str:
    """規則を読まないモデル: 表示された 4 つから seed で一様に選ぶ (arm に依らない)."""
    return random.Random(body["options"]["seed"]).choice(_options_shown(body))


DIGEST = "sha256:" + "0" * 64


def env_response(request: httpx.Request, digests: list[str]) -> httpx.Response | None:
    """/api/version と /api/tags (preflight)。digests は tags ごとに先頭から消費."""
    if request.url.path == "/api/version":
        return httpx.Response(200, json={"version": "mock"})
    if request.url.path == "/api/tags":
        digest = digests.pop(0) if len(digests) > 1 else digests[0]
        models = [{"name": bat.MODEL, "model": bat.MODEL, "digest": digest}]
        return httpx.Response(200, json={"models": models})
    return None


class Ollama:
    """``httpx.MockTransport`` の handler。policy が content を返すか例外を投げる."""

    def __init__(self, policy: Policy, digests: tuple[str, ...] = (DIGEST,)) -> None:
        self.policy = policy
        self.bodies: list[dict[str, Any]] = []
        self.digests = list(digests)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        env = env_response(request, self.digests)
        if env is not None:
            return env
        body = json.loads(request.content)
        self.bodies.append(body)
        key = _key_of()[(sc.messages_sha256(body["messages"]), body["options"]["seed"])]
        content = self.policy(key, body)
        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "message": {"role": "assistant", "content": content},
                "done": True,
                "done_reason": "stop",
                "eval_count": 3,
                "prompt_eval_count": 10,
                "total_duration": 1000,
            },
        )


def do_run(run_dir: Path, policy: Policy) -> tuple[str, Ollama]:
    ollama = Ollama(policy)
    reason = asyncio.run(drv.run(run_dir, httpx.MockTransport(ollama), backoff_s=0.0))
    return reason, ollama


def records(run_dir: Path) -> list[sc.Sample]:
    return sc.load_records(
        (run_dir / "samples.jsonl").read_text(encoding="utf-8").splitlines()
    )


def evaluate(run_dir: Path) -> dict[str, Any]:
    lines = (run_dir / "samples.jsonl").read_text(encoding="utf-8").splitlines()
    meta = (run_dir / "meta.json").read_text(encoding="utf-8")
    return sc.evaluate_records(lines, meta, CERT)


@pytest.fixture(scope="module")
def lookup_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str, Ollama]:
    run_dir = tmp_path_factory.mktemp("lookup") / "run"
    reason, ollama = do_run(run_dir, lookup)
    return run_dir, reason, ollama


# ------------------------------------------------------------ 順序 (DR-2)


def test_schedule_is_the_frozen_grid_with_c0_first() -> None:
    keys = drv.schedule()
    assert len(keys) == N_ALL
    assert len(set(keys)) == N_ALL
    grid = {
        (arm, r, qi, k)
        for arm in bat.ALL_ARMS
        for r in range(sc.FROZEN_R)
        for qi in range(6)
        for k in range(sc.FROZEN_K)
    }
    assert set(keys) == grid
    assert all(k[0] == bat.ARM_C0 for k in keys[:N_C0])
    assert all(k[0] != bat.ARM_C0 for k in keys[N_C0:])


def test_lever_arms_rotate_evenly_over_slots() -> None:
    lever = drv.lever_schedule()
    slots = Counter((i % 4, key[0]) for i, key in enumerate(lever))
    assert set(slots.values()) == {len(lever) // 16}
    # 各 block は同じ (r, probe, k) の 4 arm
    for b in range(0, len(lever), 4):
        assert len({key[1:] for key in lever[b : b + 4]}) == 1
        assert {key[0] for key in lever[b : b + 4]} == set(bat.LEVER_ARMS)


def test_run_records_c0_before_lever_with_serial_call_index(
    lookup_run: tuple[Path, str, Ollama],
) -> None:
    run_dir, reason, ollama = lookup_run
    assert reason == drv.REASON_COMPLETED
    recs = records(run_dir)
    assert [s.call_index for s in recs] == list(range(N_ALL))
    c0 = [s.call_index for s in recs if s.arm == bat.ARM_C0]
    lever = [s.call_index for s in recs if s.arm != bat.ARM_C0]
    assert max(c0) < min(lever)
    assert len(ollama.bodies) == N_ALL


# -------------------------------------------------- body の照合と meta (DR-4/5)


def test_sent_bodies_equal_frozen_request(
    lookup_run: tuple[Path, str, Ollama],
) -> None:
    _, _, ollama = lookup_run
    want = sc.request_meta()
    for body, key in zip(ollama.bodies, drv.schedule(), strict=True):
        assert set(body) == {"model", "messages", "stream", "options", "think"}
        assert body["think"] is False
        assert drv.meta_of(body) == want
        seed, sha = sc.expected_sample(*key)
        assert type(body["options"]["seed"]) is int
        assert body["options"]["seed"] == seed
        assert sc.messages_sha256(body["messages"]) == sha


def test_records_match_expected_sample_and_parse(
    lookup_run: tuple[Path, str, Ollama],
) -> None:
    run_dir, _, _ = lookup_run
    qidx = {p.probe_id: i for i, p in enumerate(bat.lever_probes())}
    for s in records(run_dir):
        seed, sha = sc.expected_sample(s.arm, s.replicate, qidx[s.probe_id], s.k)
        assert (s.seed, s.prompt_sha256) == (seed, sha)
        assert s.parsed == sc.parse_choice(s.raw)


def test_meta_is_observed_and_matches_frozen(
    lookup_run: tuple[Path, str, Ollama],
) -> None:
    run_dir, _, _ = lookup_run
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    assert drv.meta_matches_frozen(meta)
    prov = json.loads((run_dir / "provenance.json").read_text(encoding="utf-8"))
    assert prov["meta_matches_frozen"] is True
    assert prov["exit_reason"] == drv.REASON_COMPLETED
    assert prov["n_samples"] == N_ALL


def test_meta_is_written_from_sent_values_not_constants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """送信前照合を外し温度をずらすと meta は送った値 0.71、判定 INVALID_SCORER."""
    monkeypatch.setattr(drv, "check_sent_body", lambda _body, _key: None)
    monkeypatch.setattr(
        drv,
        "SAMPLING",
        drv.ResolvedSampling(temperature=0.71, top_p=0.8, repeat_penalty=1.0),
    )
    reason, _ = do_run(tmp_path / "run", lookup)
    assert reason == drv.REASON_COMPLETED
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
        do_run(tmp_path / "run", lookup)
    # 1 件も送っていない (inner transport に届いていない)
    assert not (tmp_path / "run" / "samples.jsonl").read_text(encoding="utf-8")
    assert not (tmp_path / "run" / "meta.json").exists()
    prov = json.loads((tmp_path / "run" / "provenance.json").read_text("utf-8"))
    assert prov["exit_reason"] == drv.REASON_ABORTED
    assert "SentBodyMismatchError" in prov["error"]


def test_mismatch_is_detected_before_the_inner_transport() -> None:
    ollama = Ollama(lookup)
    observer = drv.ObservingTransport(httpx.MockTransport(ollama))
    observer.expected = (bat.ARM_A, 0, 0, 0)

    async def send() -> None:
        async with httpx.AsyncClient(
            base_url="http://mock", transport=observer
        ) as http:
            msgs, options = drv.request_for(
                (bat.ARM_A, 0, 0, 1)
            )  # k が違う → seed 違い
            llm = drv.OllamaChatClient(model=bat.MODEL, client=http)
            await llm.chat(msgs, sampling=drv.SAMPLING, options=options, think=False)

    with pytest.raises(drv.SentBodyMismatchError, match="seed"):
        asyncio.run(send())
    assert ollama.bodies == []


@pytest.mark.parametrize(
    ("path", "value", "fragment"),
    [
        (("options", "num_ctx"), 4096.0, "num_ctx"),
        (("options", "seed"), float(bat.sample_seed(0, 0, 0)), "seed"),
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
    key = (bat.ARM_A, 0, 0, 0)
    msgs, options = drv.request_for(key)
    body: dict[str, Any] = {
        "model": bat.MODEL,
        "messages": [m.model_dump() for m in msgs],
        "stream": False,
        "options": {**options, "temperature": 0.7, "top_p": 0.8, "repeat_penalty": 1.0},
        "think": False,
    }
    drv.check_sent_body(body, key)  # 凍結値そのものは通る
    target = body
    for p in path[:-1]:
        target = target[p]
    target[path[-1]] = value
    with pytest.raises(drv.SentBodyMismatchError, match=fragment):
        drv.check_sent_body(body, key)


def test_check_sent_body_rejects_missing_seed_and_other_prompt() -> None:
    key = (bat.ARM_A, 0, 0, 0)
    msgs, options = drv.request_for(key)
    base: dict[str, Any] = {
        "model": bat.MODEL,
        "messages": [m.model_dump() for m in msgs],
        "stream": False,
        "options": {**options, "temperature": 0.7, "top_p": 0.8, "repeat_penalty": 1.0},
        "think": False,
    }
    no_seed = json.loads(json.dumps(base))
    del no_seed["options"]["seed"]
    with pytest.raises(drv.SentBodyMismatchError, match="options keys"):
        drv.check_sent_body(no_seed, key)
    other = json.loads(json.dumps(base))
    other["messages"][1]["content"] += " "
    with pytest.raises(drv.SentBodyMismatchError, match="renderer"):
        drv.check_sent_body(other, key)
    no_think = json.loads(json.dumps(base))
    del no_think["think"]
    with pytest.raises(drv.SentBodyMismatchError, match="body keys"):
        drv.check_sent_body(no_think, key)


def test_observed_meta_requires_one_condition() -> None:
    key = (bat.ARM_A, 0, 0, 0)
    msgs, options = drv.request_for(key)
    a = {
        "model": bat.MODEL,
        "messages": [m.model_dump() for m in msgs],
        "stream": False,
        "options": {**options, "temperature": 0.7, "top_p": 0.8, "repeat_penalty": 1.0},
        "think": False,
    }
    b = json.loads(json.dumps(a))
    b["options"]["num_ctx"] = 4096.0
    assert drv.observed_meta([a, a]) == sc.request_meta()
    with pytest.raises(drv.SentBodyMismatchError, match="uniform"):
        drv.observed_meta([a, b])
    assert not drv.meta_matches_frozen({**sc.request_meta(), "think": 0})
    assert not drv.meta_matches_frozen({**sc.request_meta(), "num_ctx": 4096.0})


# ------------------------------------------------------------- C0 gate


def _c0_bottom(n_bottom: int) -> Policy:
    def policy(key: drv.Key, body: dict[str, Any]) -> str:
        arm, r, qi, k = key
        if arm == bat.ARM_C0 and (r * 6 + qi) * sc.FROZEN_K + k < n_bottom:
            return "わからない"
        return lookup(key, body)

    return policy


def test_c0_gate_at_the_limit_runs_lever(tmp_path: Path) -> None:
    reason, _ = do_run(tmp_path / "run", _c0_bottom(48))  # 48/240 = 0.2 = BOT_MAX
    assert reason == drv.REASON_COMPLETED
    assert len(records(tmp_path / "run")) == N_ALL


def test_c0_gate_blocks_lever(tmp_path: Path) -> None:
    reason, ollama = do_run(tmp_path / "run", _c0_bottom(49))
    assert reason == drv.REASON_C0_GATE
    recs = records(tmp_path / "run")
    assert len(recs) == N_C0
    assert all(s.arm == bat.ARM_C0 for s in recs)
    assert len(ollama.bodies) == N_C0
    rep = evaluate(tmp_path / "run")
    assert rep["verdict"] == VERDICT_INVALID_BATTERY
    assert rep["reasons"] == ["c0_bottom_rate"]
    assert drv.EXIT_CODES[reason] == 0


# ---------------------------------------------------- 再送と raw=null (DR-3)


def _failing(target: drv.Key, n_fail: int, exc: Callable[[], Exception]) -> Policy:
    count = Counter[drv.Key]()

    def policy(key: drv.Key, body: dict[str, Any]) -> str:
        if key == target and count[key] < n_fail:
            count[key] += 1
            raise exc()
        return lookup(key, body)

    return policy


TARGET: drv.Key = (bat.ARM_C0, 1, 2, 3)
TARGET_INDEX = drv.schedule().index(TARGET)


def _connect_error() -> Exception:
    return httpx.ConnectError("refused")


def test_resend_with_the_same_seed_recovers(tmp_path: Path) -> None:
    reason, ollama = do_run(tmp_path / "run", _failing(TARGET, 3, _connect_error))
    assert reason == drv.REASON_COMPLETED
    seed, _ = sc.expected_sample(*TARGET)
    sent = [b for b in ollama.bodies if b["options"]["seed"] == seed]
    # 同じ seed は全 arm で共有されるので C0 の送信だけを数える: 失敗 3 + 成功 1
    c0_sent = [b for b in sent if "経験" not in b["messages"][1]["content"]]
    assert len(c0_sent) == 4
    rec = records(tmp_path / "run")[TARGET_INDEX]
    assert rec.raw is not None
    assert rec.seed == seed
    attempts = [
        json.loads(line)
        for line in (tmp_path / "run" / "attempts.jsonl")
        .read_text("utf-8")
        .splitlines()
    ]
    mine = [a for a in attempts if a["call_index"] == TARGET_INDEX]
    assert [a["outcome"] for a in mine] == ["transport_failure"] * 3 + ["ok"]
    assert evaluate(tmp_path / "run")["verdict"] == VERDICT_PASS


@pytest.mark.parametrize(
    "exc",
    [
        _connect_error,
        lambda: httpx.ReadTimeout("slow"),
    ],
)
def test_unresolved_transport_failure_records_null_and_stops(
    tmp_path: Path, exc: Callable[[], Exception]
) -> None:
    reason, ollama = do_run(tmp_path / "run", _failing(TARGET, 4, exc))
    assert reason == drv.REASON_TRANSPORT
    recs = records(tmp_path / "run")
    assert len(recs) == TARGET_INDEX + 1
    assert recs[-1].raw is None
    assert recs[-1].parsed is None
    assert len(ollama.bodies) == TARGET_INDEX + 4
    rep = evaluate(tmp_path / "run")
    assert rep["status"] == sc.STATUS_NOT_COMPUTED
    assert rep["verdict"] is None
    assert drv.EXIT_CODES[reason] != 0


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


def test_other_exceptions_abort_without_a_null_row(tmp_path: Path) -> None:
    policy = _failing(TARGET, 1, lambda: ValueError("bug"))
    with pytest.raises(ValueError, match="bug"):
        do_run(tmp_path / "run", policy)
    recs = records(tmp_path / "run")
    assert len(recs) == TARGET_INDEX
    assert all(s.raw is not None for s in recs)
    prov = json.loads((tmp_path / "run" / "provenance.json").read_text("utf-8"))
    assert prov["exit_reason"] == drv.REASON_ABORTED


# ------------------------------------------------------------ 記録と結線


def test_raw_is_recorded_verbatim(tmp_path: Path) -> None:
    def padded(key: drv.Key, body: dict[str, Any]) -> str:
        return f"  **{lookup(key, body)}**\n"

    reason, _ = do_run(tmp_path / "run", padded)
    assert reason == drv.REASON_COMPLETED
    recs = records(tmp_path / "run")
    assert all(s.raw.startswith("  **") and s.raw.endswith("**\n") for s in recs)
    assert all(s.parsed is not None for s in recs)
    assert all(s.parsed == sc.parse_choice(s.raw) != s.raw for s in recs)


def test_run_refuses_a_non_empty_run_dir(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "samples.jsonl").write_text("partial\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        do_run(run_dir, lookup)
    assert (run_dir / "samples.jsonl").read_text(encoding="utf-8") == "partial\n"
    assert not (run_dir / "provenance.json").exists()


def test_lookup_model_passes_the_frozen_scorer(
    lookup_run: tuple[Path, str, Ollama],
) -> None:
    run_dir, _, _ = lookup_run
    rep = evaluate(run_dir)
    assert rep["verdict"] == VERDICT_PASS
    assert rep["C"] == 1.0
    assert "record_error" not in rep


def test_uniform_model_is_no_go(tmp_path: Path) -> None:
    reason, _ = do_run(tmp_path / "run", uniform)
    assert reason == drv.REASON_COMPLETED
    rep = evaluate(tmp_path / "run")
    assert rep["verdict"] == VERDICT_ABSENT


# ------------------------------------------------ review 反映 (preflight 等)


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

    def policy(key: drv.Key, body: dict[str, Any]) -> str:
        seen.append((run_dir / "meta.json").exists())
        return lookup(key, body)

    reason, _ = do_run(run_dir, policy)
    assert reason == drv.REASON_COMPLETED
    assert seen[0] is False
    assert all(seen[1:])
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    assert drv.meta_matches_frozen(meta)


def test_null_content_is_a_transport_failure_not_bottom(tmp_path: Path) -> None:
    def null_at_target(key: drv.Key, body: dict[str, Any]) -> str | None:
        return None if key == TARGET else lookup(key, body)

    reason, ollama = do_run(tmp_path / "run", null_at_target)
    assert reason == drv.REASON_TRANSPORT
    recs = records(tmp_path / "run")
    assert recs[-1].raw is None
    assert len(ollama.bodies) == TARGET_INDEX + 4
    assert evaluate(tmp_path / "run")["status"] == sc.STATUS_NOT_COMPUTED


def test_seed_and_prompt_are_recorded_from_the_sent_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """照合を外し seed +1・prompt をずらすと記録は送った値、判定は INVALID_SCORER."""
    original = drv.request_for

    def shifted(key: drv.Key) -> tuple[list[drv.ChatMessage], dict[str, Any]]:
        msgs, options = original(key)
        msgs[-1] = drv.ChatMessage(role="user", content=msgs[-1].content + " ")
        return msgs, {**options, "seed": options["seed"] + 1}

    monkeypatch.setattr(drv, "check_sent_body", lambda _body, _key: None)
    monkeypatch.setattr(drv, "request_for", shifted)
    ollama = Ollama(lambda _key, _body: "read_book")
    ollama_call = ollama.__call__

    def lenient(
        request: httpx.Request,
    ) -> httpx.Response:  # 逆引きできない要求にも答える
        if request.url.path == "/api/chat":
            body = json.loads(request.content)
            ollama.bodies.append(body)
            return httpx.Response(
                200,
                json={
                    "model": body["model"],
                    "message": {"role": "assistant", "content": "read_book"},
                    "eval_count": 1,
                },
            )
        return ollama_call(request)

    reason = asyncio.run(
        drv.run(tmp_path / "run", httpx.MockTransport(lenient), backoff_s=0.0)
    )
    assert reason == drv.REASON_COMPLETED
    recs = records(tmp_path / "run")
    for s, body in zip(recs, ollama.bodies, strict=True):
        assert s.seed == body["options"]["seed"]
        assert s.prompt_sha256 == sc.messages_sha256(body["messages"])
    key0 = drv.schedule()[0]
    assert recs[0].seed == sc.expected_sample(*key0)[0] + 1
    rep = evaluate(tmp_path / "run")
    assert rep["verdict"] == VERDICT_INVALID_SCORER
    assert rep["reasons"] == ["structure"]


def test_model_digest_change_aborts(tmp_path: Path) -> None:
    ollama = Ollama(lookup, digests=(DIGEST, "sha256:" + "1" * 64))
    reason = asyncio.run(
        drv.run(tmp_path / "run", httpx.MockTransport(ollama), backoff_s=0.0)
    )
    assert reason == drv.REASON_ABORTED
    prov = json.loads((tmp_path / "run" / "provenance.json").read_text("utf-8"))
    assert "digest changed" in prov["error"]
    assert prov["model_digest_start"] != prov["model_digest_end"]


@pytest.mark.parametrize(
    ("where", "extra"),
    [((), "format"), (("options",), "stop")],
)
def test_check_sent_body_rejects_extra_keys(where: tuple[str, ...], extra: str) -> None:
    key = (bat.ARM_A, 0, 0, 0)
    msgs, options = drv.request_for(key)
    body: dict[str, Any] = {
        "model": bat.MODEL,
        "messages": [m.model_dump() for m in msgs],
        "stream": False,
        "options": {**options, "temperature": 0.7, "top_p": 0.8, "repeat_penalty": 1.0},
        "think": False,
    }
    target = body
    for p in where:
        target = target[p]
    target[extra] = "json"
    with pytest.raises(drv.SentBodyMismatchError, match="keys"):
        drv.check_sent_body(body, key)


def test_non_chat_post_is_refused_before_sending() -> None:
    ollama = Ollama(lookup)
    observer = drv.ObservingTransport(httpx.MockTransport(ollama))

    async def send() -> None:
        async with httpx.AsyncClient(base_url="http://mock", transport=observer) as h:
            await h.post("/prefix/api/chat", json={})

    with pytest.raises(drv.SentBodyMismatchError, match="POST path"):
        asyncio.run(send())
    assert ollama.bodies == []


def test_driver_certification_detects_stale_or_failing(tmp_path: Path) -> None:
    good = {"target_sha256": drv.certified_files(), "all_killed": True}
    cert = tmp_path / "cert.json"
    cert.write_text(json.dumps(good), encoding="utf-8")
    assert drv.driver_certification_problems(cert) == []
    cert.write_text(json.dumps({**good, "all_killed": False}), encoding="utf-8")
    assert drv.driver_certification_problems(cert) == [
        "driver certification: not all KILLED"
    ]
    stale = {**good["target_sha256"], "skill_lever_driver.py": "0" * 64}
    cert.write_text(json.dumps({**good, "target_sha256": stale}), encoding="utf-8")
    assert len(drv.driver_certification_problems(cert)) == 1
    assert drv.driver_certification_problems(tmp_path / "missing.json")


def test_committed_driver_certification_is_current() -> None:
    """commit 済み driver_mutation.json が現在の driver・test と一致 (変異中は外す)."""
    assert drv.driver_certification_problems(drv.DRIVER_CERT) == []
