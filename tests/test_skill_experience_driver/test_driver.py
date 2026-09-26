"""経験由来 Skill driver (mock transport のみ、実モデル不使用).

driver の判定に関わる行 (送った body の照合・meta の観測・呼び出し順・C0 gate・
再送と raw=null・再開しない・起動の前提) を pin し、出力が凍結 v3 scorer
(``evaluate_records``) で読めることと、driver → scorer の結線 (mock の成否集計どおり →
PASS / 一様 → NO_GO / 判定は一様・対照は抽出 → 対照の claim 分岐) を確かめる。
"""

from __future__ import annotations

import ast
import asyncio
import json
import random
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from scripts import skill_experience_battery as bat
from scripts import skill_experience_driver as drv
from scripts import skill_experience_scorer as sc
from scripts import skill_lever_battery as v2bat
from scripts.skill_lever_scorer import load_records, messages_sha256
from scripts.stage_b_scorer import (
    VERDICT_ABSENT,
    VERDICT_INVALID_BATTERY,
    VERDICT_INVALID_SCORER,
    VERDICT_PASS,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    Policy = Callable[[drv.Key, dict[str, Any]], str | None]

_ROOT = Path(__file__).resolve().parents[2]
CERT = (
    _ROOT
    / "experiments"
    / "20260926-experience-skill-pilot"
    / "results"
    / "v3_mutation.json"
)
N_PROBES = 6
N_C0 = sc.FROZEN_R * N_PROBES * sc.FROZEN_K  # 240
N_STATE = len(bat.STATE_ARMS) * N_C0  # 1,920
N_ALL = N_C0 + N_STATE  # 2,160


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


def extract(key: drv.Key, body: dict[str, Any]) -> str:
    """成否集計を読むモデル: 状態 arm は自 arm の規則が指す選択肢、C0 は表示先頭."""
    arm, _, qi, _ = key
    if arm == bat.ARM_C0:
        return _options_shown(body)[0]
    return v2bat.lever_probes()[qi].pointed[bat.POINTS_AS[arm]]


def uniform(_key: drv.Key, body: dict[str, Any]) -> str:
    """成否を読まないモデル: 表示された 4 つから seed で一様に選ぶ (arm に依らない)."""
    return random.Random(body["options"]["seed"]).choice(_options_shown(body))


def judge_uniform_control_extract(key: drv.Key, body: dict[str, Any]) -> str:
    return extract(key, body) if key[0] in bat.CONTROL_ARMS else uniform(key, body)


def judge_extract_control_uniform(key: drv.Key, body: dict[str, Any]) -> str:
    return uniform(key, body) if key[0] in bat.CONTROL_ARMS else extract(key, body)


def judge_uniform_control_filler(key: drv.Key, body: dict[str, Any]) -> str:
    return bat.FILLERS[0] if key[0] in bat.CONTROL_ARMS else uniform(key, body)


DIGEST = "sha256:" + "0" * 64


def env_response(request: httpx.Request, digests: list[str]) -> httpx.Response | None:
    """/api/version と /api/tags (preflight)。digests は tags ごとに先頭から消費."""
    if request.url.path == "/api/version":
        return httpx.Response(200, json={"version": "mock"})
    if request.url.path == "/api/tags":
        digest = digests.pop(0) if len(digests) > 1 else digests[0]
        models = [{"name": v2bat.MODEL, "model": v2bat.MODEL, "digest": digest}]
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
        key = _key_of()[(messages_sha256(body["messages"]), body["options"]["seed"])]
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
    return load_records(
        (run_dir / "samples.jsonl").read_text(encoding="utf-8").splitlines()
    )


def evaluate(run_dir: Path) -> dict[str, Any]:
    lines = (run_dir / "samples.jsonl").read_text(encoding="utf-8").splitlines()
    meta = (run_dir / "meta.json").read_text(encoding="utf-8")
    return sc.evaluate_records(lines, meta, CERT)


def body_for(key: drv.Key) -> dict[str, Any]:
    msgs, options = drv.request_for(key)
    return {
        "model": v2bat.MODEL,
        "messages": [m.model_dump() for m in msgs],
        "stream": False,
        "options": {**options, "temperature": 0.7, "top_p": 0.8, "repeat_penalty": 1.0},
        "think": False,
    }


@pytest.fixture(scope="module")
def extract_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str, Ollama]:
    run_dir = tmp_path_factory.mktemp("extract") / "run"
    reason, ollama = do_run(run_dir, extract)
    return run_dir, reason, ollama


# ------------------------------------------------------------ 順序 (§2.4)


def test_schedule_is_the_frozen_grid_with_c0_first() -> None:
    keys = drv.schedule()
    assert len(keys) == N_ALL
    assert len(set(keys)) == N_ALL
    qidx = {p.probe_id: i for i, p in enumerate(v2bat.lever_probes())}
    grid = {(arm, r, qidx[p], k) for arm, r, p, k in sc.grid(bat.ALL_ARMS)}
    assert set(keys) == grid
    assert all(k[0] == bat.ARM_C0 for k in keys[:N_C0])
    assert all(k[0] != bat.ARM_C0 for k in keys[N_C0:])
    # C0 は (r, probe, k) の辞書順
    assert keys[:N_C0] == sorted(keys[:N_C0])


def test_schedule_agrees_with_the_scorer_call_rank() -> None:
    ranks = [sc.call_rank(*key) for key in drv.schedule()]
    assert ranks == sorted(ranks)
    assert len(set(ranks)) == N_ALL


def test_state_arms_rotate_evenly_over_slots() -> None:
    """巡回は scorer の式を写さず独立に書き直して照合する (同語反復にしない)."""
    state = drv.state_schedule()
    n_arm = len(bat.STATE_ARMS)
    assert len(state) == N_STATE
    for b in range(N_C0):
        block = state[b * n_arm : (b + 1) * n_arm]
        r, rest = divmod(b, N_PROBES * sc.FROZEN_K)
        qi, k = divmod(rest, sc.FROZEN_K)
        assert {key[1:] for key in block} == {(r, qi, k)}
        want = [bat.STATE_ARMS[(b + j) % n_arm] for j in range(n_arm)]
        assert [key[0] for key in block] == want
    slots = Counter((i % n_arm, key[0]) for i, key in enumerate(state))
    assert len(slots) == n_arm * n_arm
    assert set(slots.values()) == {N_C0 // n_arm}  # 各 arm が各 slot に 30 回


def test_run_records_c0_before_state_with_serial_call_index(
    extract_run: tuple[Path, str, Ollama],
) -> None:
    run_dir, reason, ollama = extract_run
    assert reason == drv.REASON_COMPLETED
    recs = records(run_dir)
    assert [s.call_index for s in recs] == list(range(N_ALL))
    c0 = [s.call_index for s in recs if s.arm == bat.ARM_C0]
    state = [s.call_index for s in recs if s.arm != bat.ARM_C0]
    assert max(c0) < min(state)
    assert len(ollama.bodies) == N_ALL
    assert Counter(s.arm for s in recs) == dict.fromkeys(bat.ALL_ARMS, N_C0)


# ---------------------------------------------------------- body の照合と meta


def test_sent_bodies_equal_frozen_request(
    extract_run: tuple[Path, str, Ollama],
) -> None:
    _, _, ollama = extract_run
    want = sc.request_meta()
    for body, key in zip(ollama.bodies, drv.schedule(), strict=True):
        assert set(body) == {"model", "messages", "stream", "options", "think"}
        assert body["think"] is False
        assert drv.meta_of(body) == want
        seed, sha = sc.expected_sample(*key)
        assert type(body["options"]["seed"]) is int
        assert body["options"]["seed"] == seed
        assert messages_sha256(body["messages"]) == sha


def test_records_match_expected_sample_and_parse(
    extract_run: tuple[Path, str, Ollama],
) -> None:
    run_dir, _, _ = extract_run
    qidx = {p.probe_id: i for i, p in enumerate(v2bat.lever_probes())}
    for s in records(run_dir):
        seed, sha = sc.expected_sample(s.arm, s.replicate, qidx[s.probe_id], s.k)
        assert (s.seed, s.prompt_sha256) == (seed, sha)
        assert s.parsed == sc.parse_choice(s.raw)


def test_meta_is_observed_and_matches_frozen(
    extract_run: tuple[Path, str, Ollama],
) -> None:
    run_dir, _, _ = extract_run
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    assert drv.meta_matches_frozen(meta)
    prov = json.loads((run_dir / "provenance.json").read_text(encoding="utf-8"))
    assert prov["meta_matches_frozen"] is True
    assert prov["exit_reason"] == drv.REASON_COMPLETED
    assert prov["n_samples"] == N_ALL


def test_meta_is_written_from_sent_values_not_constants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """送信前照合を外し温度をずらすと meta は送った値 0.71、判定 INVALID_SCORER.

    記録は揃うが、来歴の異常 (要求条件が凍結値と違う) なので exit_reason は aborted.
    """
    monkeypatch.setattr(drv, "check_sent_body", lambda _body, _key: None)
    monkeypatch.setattr(
        drv,
        "SAMPLING",
        drv.ResolvedSampling(temperature=0.71, top_p=0.8, repeat_penalty=1.0),
    )
    reason, _ = do_run(tmp_path / "run", extract)
    assert reason == drv.REASON_ABORTED
    prov = json.loads((tmp_path / "run" / "provenance.json").read_text("utf-8"))
    assert prov["meta_matches_frozen"] is False
    assert "frozen meta" in prov["error"]
    assert len(records(tmp_path / "run")) == N_ALL
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
        do_run(tmp_path / "run", extract)
    assert not (tmp_path / "run" / "samples.jsonl").read_text(encoding="utf-8")
    assert not (tmp_path / "run" / "meta.json").exists()
    prov = json.loads((tmp_path / "run" / "provenance.json").read_text("utf-8"))
    assert prov["exit_reason"] == drv.REASON_ABORTED
    assert "SentBodyMismatchError" in prov["error"]


def test_mismatch_is_detected_before_the_inner_transport() -> None:
    ollama = Ollama(extract)
    observer = drv.ObservingTransport(httpx.MockTransport(ollama))
    observer.expected = (bat.ARM_A, 0, 0, 0)

    async def send() -> None:
        async with httpx.AsyncClient(
            base_url="http://mock", transport=observer
        ) as http:
            msgs, options = drv.request_for((bat.ARM_A, 0, 0, 1))  # k 違い → seed 違い
            llm = drv.OllamaChatClient(model=v2bat.MODEL, client=http)
            await llm.chat(msgs, sampling=drv.SAMPLING, options=options, think=False)

    with pytest.raises(drv.SentBodyMismatchError, match="seed"):
        asyncio.run(send())
    assert ollama.bodies == []


@pytest.mark.parametrize(
    ("path", "value", "fragment"),
    [
        (("options", "num_ctx"), 4096.0, "num_ctx"),
        (("options", "seed"), float(v2bat.sample_seed(0, 0, 0)), "seed"),
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
    body = body_for(key)
    drv.check_sent_body(body, key)  # 凍結値そのものは通る
    target = body
    for p in path[:-1]:
        target = target[p]
    target[path[-1]] = value
    with pytest.raises(drv.SentBodyMismatchError, match=fragment):
        drv.check_sent_body(body, key)


def test_check_sent_body_rejects_missing_seed_and_other_prompt() -> None:
    key = ("L_B", 3, 2, 1)
    base = body_for(key)
    drv.check_sent_body(base, key)
    no_seed = json.loads(json.dumps(base))
    del no_seed["options"]["seed"]
    with pytest.raises(drv.SentBodyMismatchError, match="options keys"):
        drv.check_sent_body(no_seed, key)
    other = json.loads(json.dumps(base))
    other["messages"][1]["content"] += " "
    with pytest.raises(drv.SentBodyMismatchError, match="renderer"):
        drv.check_sent_body(other, key)
    # 判定 arm の状態を対照 arm の key で送る (seed は同じ、prompt だけ違う)
    judge = body_for(("B", 3, 2, 1))
    with pytest.raises(drv.SentBodyMismatchError, match="renderer"):
        drv.check_sent_body(judge, key)
    no_think = json.loads(json.dumps(base))
    del no_think["think"]
    with pytest.raises(drv.SentBodyMismatchError, match="body keys"):
        drv.check_sent_body(no_think, key)


def test_request_uses_the_v3_renderer_not_v2() -> None:
    for key in (("A", 0, 0, 0), ("L_A_rot", 7, 5, 4), (bat.ARM_C0, 2, 3, 1)):
        body = body_for(key)
        assert messages_sha256(body["messages"]) == sc.expected_sample(*key)[1]
    state = body_for(("A", 0, 0, 0))["messages"][1]["content"]
    assert state.count(bat.OUTCOME_FAILURE) == 24
    assert state.count(bat.OUTCOME_SUCCESS) == 12


def test_observed_meta_requires_one_condition() -> None:
    a = body_for((bat.ARM_A, 0, 0, 0))
    b = json.loads(json.dumps(a))
    b["options"]["num_ctx"] = 4096.0
    assert drv.observed_meta([a, a]) == sc.request_meta()
    with pytest.raises(drv.SentBodyMismatchError, match="uniform"):
        drv.observed_meta([a, b])
    assert not drv.meta_matches_frozen({**sc.request_meta(), "think": 0})
    assert not drv.meta_matches_frozen({**sc.request_meta(), "num_ctx": 4096.0})


@pytest.mark.parametrize(
    ("where", "extra"),
    [((), "format"), (("options",), "stop")],
)
def test_check_sent_body_rejects_extra_keys(where: tuple[str, ...], extra: str) -> None:
    key = (bat.ARM_A, 0, 0, 0)
    body = body_for(key)
    target = body
    for p in where:
        target = target[p]
    target[extra] = "json"
    with pytest.raises(drv.SentBodyMismatchError, match="keys"):
        drv.check_sent_body(body, key)


def test_non_chat_post_is_refused_before_sending() -> None:
    ollama = Ollama(extract)
    observer = drv.ObservingTransport(httpx.MockTransport(ollama))

    async def send() -> None:
        async with httpx.AsyncClient(base_url="http://mock", transport=observer) as h:
            await h.post("/prefix/api/chat", json={})

    with pytest.raises(drv.SentBodyMismatchError, match="POST path"):
        asyncio.run(send())
    assert ollama.bodies == []


# ------------------------------------------------------------- C0 gate


def _c0_bottom(n_bottom: int) -> Policy:
    """C0 の先頭 n_bottom 呼び出し ((r, probe, k) 辞書順) だけ ⊥ を答える."""

    def policy(key: drv.Key, body: dict[str, Any]) -> str:
        arm, r, qi, k = key
        if arm == bat.ARM_C0 and (r * N_PROBES + qi) * sc.FROZEN_K + k < n_bottom:
            return "わからない"
        return extract(key, body)

    return policy


def test_c0_gate_at_the_limit_runs_state_arms(tmp_path: Path) -> None:
    reason, _ = do_run(tmp_path / "run", _c0_bottom(48))  # 48/240 = 0.2 = BOT_MAX
    assert reason == drv.REASON_COMPLETED
    assert len(records(tmp_path / "run")) == N_ALL
    prov = json.loads((tmp_path / "run" / "provenance.json").read_text("utf-8"))
    assert prov["c0_bottom_rate_driver"] == pytest.approx(0.2)


def test_c0_gate_blocks_state_arms(tmp_path: Path) -> None:
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


def test_c0_gate_counts_the_last_replicate(tmp_path: Path) -> None:
    """⊥ を最後の replicate にだけ置く: R 全体で数えないと gate が効かない."""

    def late(key: drv.Key, body: dict[str, Any]) -> str:
        arm, r, qi, k = key
        if arm == bat.ARM_C0 and r == sc.FROZEN_R - 1 and qi * sc.FROZEN_K + k < 30:
            return "わからない"
        if arm == bat.ARM_C0 and r == sc.FROZEN_R - 2 and qi * sc.FROZEN_K + k < 19:
            return "わからない"
        return extract(key, body)

    reason, ollama = do_run(tmp_path / "run", late)  # 49/240 > 0.2
    assert reason == drv.REASON_C0_GATE
    assert len(ollama.bodies) == N_C0


# ---------------------------------------------------- 再送と raw=null


def _failing(target: drv.Key, n_fail: int, exc: Callable[[], Exception]) -> Policy:
    count = Counter[drv.Key]()

    def policy(key: drv.Key, body: dict[str, Any]) -> str:
        if key == target and count[key] < n_fail:
            count[key] += 1
            raise exc()
        return extract(key, body)

    return policy


TARGET: drv.Key = (bat.ARM_C0, 1, 2, 3)
TARGET_INDEX = drv.schedule().index(TARGET)


def _connect_error() -> Exception:
    return httpx.ConnectError("refused")


def test_resend_with_the_same_seed_recovers(tmp_path: Path) -> None:
    reason, ollama = do_run(tmp_path / "run", _failing(TARGET, 3, _connect_error))
    assert reason == drv.REASON_COMPLETED
    seed, sha = sc.expected_sample(*TARGET)
    sent = [
        b
        for b in ollama.bodies
        if b["options"]["seed"] == seed and messages_sha256(b["messages"]) == sha
    ]
    assert len(sent) == 4  # 失敗 3 + 成功 1、全て同じ seed と prompt
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


def test_null_content_is_a_transport_failure_not_bottom(tmp_path: Path) -> None:
    def null_at_target(key: drv.Key, body: dict[str, Any]) -> str | None:
        return None if key == TARGET else extract(key, body)

    reason, ollama = do_run(tmp_path / "run", null_at_target)
    assert reason == drv.REASON_TRANSPORT
    recs = records(tmp_path / "run")
    assert recs[-1].raw is None
    assert len(ollama.bodies) == TARGET_INDEX + 4
    assert evaluate(tmp_path / "run")["status"] == sc.STATUS_NOT_COMPUTED


# ------------------------------------------------------------ 記録


def test_raw_is_recorded_verbatim(tmp_path: Path) -> None:
    def padded(key: drv.Key, body: dict[str, Any]) -> str:
        return f"  **{extract(key, body)}**\n"

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
        do_run(run_dir, extract)
    assert (run_dir / "samples.jsonl").read_text(encoding="utf-8") == "partial\n"
    assert not (run_dir / "provenance.json").exists()


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
    bodies: list[dict[str, Any]] = []

    def lenient(
        request: httpx.Request,
    ) -> httpx.Response:  # 逆引きできない要求にも答える
        env = env_response(request, [DIGEST])
        if env is not None:
            return env
        body = json.loads(request.content)
        bodies.append(body)
        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "message": {"role": "assistant", "content": "read_book"},
                "eval_count": 1,
            },
        )

    reason = asyncio.run(
        drv.run(tmp_path / "run", httpx.MockTransport(lenient), backoff_s=0.0)
    )
    assert reason == drv.REASON_COMPLETED
    recs = records(tmp_path / "run")
    for s, body in zip(recs, bodies, strict=True):
        assert s.seed == body["options"]["seed"]
        assert s.prompt_sha256 == messages_sha256(body["messages"])
    key0 = drv.schedule()[0]
    assert recs[0].seed == sc.expected_sample(*key0)[0] + 1
    rep = evaluate(tmp_path / "run")
    assert rep["verdict"] == VERDICT_INVALID_SCORER
    assert rep["reasons"] == ["structure"]


# ------------------------------------------------------ driver → scorer の結線


def test_extracting_model_passes_the_frozen_scorer(
    extract_run: tuple[Path, str, Ollama],
) -> None:
    run_dir, _, _ = extract_run
    rep = evaluate(run_dir)
    assert "record_error" not in rep
    assert rep["structure_violations"] == []
    assert rep["verdict"] == VERDICT_PASS
    assert rep["C"] == 1.0
    assert rep["control"]["verdict"] == VERDICT_PASS
    assert rep["claim_branch"] == sc.CLAIM_PASS


def test_uniform_model_is_no_go(tmp_path: Path) -> None:
    reason, _ = do_run(tmp_path / "run", uniform)
    assert reason == drv.REASON_COMPLETED
    rep = evaluate(tmp_path / "run")
    assert rep["verdict"] == VERDICT_ABSENT
    assert rep["control"]["verdict"] == VERDICT_ABSENT
    assert rep["claim_branch"] == sc.CLAIM_NO_GO_NARROW


def test_judge_uniform_control_extracting_is_the_control_claim(tmp_path: Path) -> None:
    reason, _ = do_run(tmp_path / "run", judge_uniform_control_extract)
    assert reason == drv.REASON_COMPLETED
    rep = evaluate(tmp_path / "run")
    assert rep["verdict"] == VERDICT_ABSENT
    assert rep["control"]["verdict"] == VERDICT_PASS
    assert rep["claim_branch"] == sc.CLAIM_NO_GO_CONTROL_PASS


def test_control_does_not_change_the_judge_verdict(tmp_path: Path) -> None:
    reason, _ = do_run(tmp_path / "run", judge_extract_control_uniform)
    assert reason == drv.REASON_COMPLETED
    rep = evaluate(tmp_path / "run")
    assert rep["verdict"] == VERDICT_PASS
    assert rep["C"] == 1.0
    assert rep["control"]["verdict"] == VERDICT_ABSENT


def test_filler_answers_are_recorded_and_gate_only_the_control(tmp_path: Path) -> None:
    reason, _ = do_run(tmp_path / "run", judge_uniform_control_filler)
    assert reason == drv.REASON_COMPLETED
    recs = records(tmp_path / "run")
    ctrl = [s for s in recs if s.arm in bat.CONTROL_ARMS]
    assert all(s.raw == bat.FILLERS[0] and s.parsed is None for s in ctrl)
    rep = evaluate(tmp_path / "run")
    assert rep["verdict"] == VERDICT_ABSENT
    assert rep["control"]["verdict"] == VERDICT_INVALID_BATTERY
    assert rep["claim_branch"] == sc.CLAIM_NO_GO_NARROW


# ------------------------------------------------ preflight・digest・meta 早期書き


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
        return extract(key, body)

    reason, _ = do_run(run_dir, policy)
    assert reason == drv.REASON_COMPLETED
    assert seen[0] is False
    assert all(seen[1:])
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    assert drv.meta_matches_frozen(meta)


def test_model_digest_change_aborts(tmp_path: Path) -> None:
    ollama = Ollama(extract, digests=(DIGEST, "sha256:" + "1" * 64))
    reason = asyncio.run(
        drv.run(tmp_path / "run", httpx.MockTransport(ollama), backoff_s=0.0)
    )
    assert reason == drv.REASON_ABORTED
    prov = json.loads((tmp_path / "run" / "provenance.json").read_text("utf-8"))
    assert "digest changed" in prov["error"]
    assert prov["model_digest_start"] != prov["model_digest_end"]


# ------------------------------------------------------ 起動の前提と import 制限


def test_driver_does_not_import_the_v2_driver() -> None:
    tree = ast.parse(Path(drv.__file__).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
    assert not any("skill_lever_driver" in n for n in names)
    local = {n for n in names if n.startswith(("scripts", "erre_sandbox"))}
    assert local == {
        "scripts",
        "scripts.skill_experience_battery",
        "scripts.skill_experience_scorer",
        "scripts.skill_lever_battery",
        "scripts.skill_lever_scorer",
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
    code = drv.main(["--run-dir", str(tmp_path / "run")])
    assert code == drv.EXIT_CODES[drv.REASON_ABORTED]
    assert called == []
    assert not (tmp_path / "run").exists()


def test_driver_certification_detects_stale_or_failing(tmp_path: Path) -> None:
    good = {"target_sha256": drv.certified_files(), "all_killed": True}
    cert = tmp_path / "cert.json"
    cert.write_text(json.dumps(good), encoding="utf-8")
    assert drv.driver_certification_problems(cert) == []
    cert.write_text(json.dumps({**good, "all_killed": False}), encoding="utf-8")
    assert drv.driver_certification_problems(cert) == [
        "driver certification: not all KILLED"
    ]
    stale = {**good["target_sha256"], "skill_experience_driver.py": "0" * 64}
    cert.write_text(json.dumps({**good, "target_sha256": stale}), encoding="utf-8")
    assert len(drv.driver_certification_problems(cert)) == 1
    assert drv.driver_certification_problems(tmp_path / "missing.json")
    assert set(good["target_sha256"]) == {
        "skill_experience_driver.py",
        "skill_experience_describe.py",
        "skill_experience_run_gate.py",
        "skill_experience_driver_mutation_check.py",
        "tests/__init__.py",
        "tests/conftest.py",
        "tests/test_driver.py",
        "tests/test_describe.py",
        "tests/test_run_gate.py",
    }
    assert None not in good["target_sha256"].values()


# ------------------------------------------------------ 来歴の異常は aborted


def _mock_response(content: str, model: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": model,
            "message": {"role": "assistant", "content": content},
            "done": True,
            "done_reason": "stop",
            "eval_count": 3,
            "prompt_eval_count": 10,
        },
    )


def test_unexpected_response_model_aborts(tmp_path: Path) -> None:
    ollama = Ollama(extract)

    def other_model(request: httpx.Request) -> httpx.Response:
        resp = ollama(request)
        if request.url.path != "/api/chat":
            return resp
        return _mock_response(resp.json()["message"]["content"], "qwen3:4b")

    reason = asyncio.run(
        drv.run(tmp_path / "run", httpx.MockTransport(other_model), backoff_s=0.0)
    )
    assert reason == drv.REASON_ABORTED
    prov = json.loads((tmp_path / "run" / "provenance.json").read_text("utf-8"))
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
    reason, _ = do_run(tmp_path / "run", extract)
    assert reason == drv.REASON_ABORTED
    prov = json.loads((tmp_path / "run" / "provenance.json").read_text("utf-8"))
    assert prov["driver_sha256_start"] != prov["driver_sha256_end"]
    assert "driver file changed" in prov["error"]


def test_chat_without_an_expected_key_is_refused() -> None:
    ollama = Ollama(extract)
    observer = drv.ObservingTransport(httpx.MockTransport(ollama))

    async def send() -> None:
        async with httpx.AsyncClient(base_url="http://mock", transport=observer) as h:
            await h.post("/api/chat", json=body_for((bat.ARM_A, 0, 0, 0)))

    with pytest.raises(drv.SentBodyMismatchError, match="expected key"):
        asyncio.run(send())
    assert ollama.bodies == []


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
        "scripts/skill_experience_driver.py",
        "scripts/skill_experience_describe.py",
        "scripts/skill_experience_run_gate.py",
        "scripts/skill_experience_evaluate.py",
        "experiments/20260926-experience-skill-pilot/run.sh",
        "experiments/20260926-experience-skill-pilot/prereg.md",
        "experiments/20260926-experience-skill-pilot/manifest.json",
        "experiments/20260926-experience-skill-pilot/results/driver_mutation.json",
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
