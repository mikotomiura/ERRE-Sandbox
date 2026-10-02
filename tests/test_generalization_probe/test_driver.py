"""候補 G (汎化 probe) の実走 driver の test (偽の Ollama のみ、実モデル不使用).

偽の Ollama (``FakeOllama``) は、送られた body の文面と seed だけから答える
(plan・段・arm を知らない)。呼び出しの識別は「これまでに正常に答えた回数」
= call_index (driver は plan の順に 1 件ずつ送り、再送は同じ call_index の
中で起こる)。

full run は session fixture で 1 回ずつ走らせる。pilot (684) は tmp の root の
凍結配置に書き、pilot 判定の CLI と provenance の照合に使う。本走は 1,728。
manifest の照合 (1 回 16 秒) は偽の出力に差し替え、出力の解釈は
``test_manifest_problems_require_the_exact_ok_line`` で pin する。
"""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json
import random
import shutil
import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from scripts import generalization_probe_battery as bat
from scripts import generalization_probe_driver as drv
from scripts import generalization_probe_driver_mutation_check as harness
from scripts import generalization_probe_manifest as man
from scripts import generalization_probe_pilot_gate as pg
from scripts import generalization_probe_scorer as sc

if TYPE_CHECKING:
    from collections.abc import Callable

    Policy = Callable[[int, dict[str, Any]], object]

_ROOT = Path(__file__).resolve().parents[2]
R_MAIN = man.sim.R_MAIN
DIGEST = "sha256:" + "0" * 64
OTHER_DIGEST = "sha256:" + "1" * 64
VERSION = "0.0-mock"
TEMPLATE = "{{ .System }}|{{ .Prompt }}"
OBSERVED = {
    "model_digest": DIGEST,
    "ollama_version": VERSION,
    "template_sha256": hashlib.sha256(TEMPLATE.encode("utf-8")).hexdigest(),
}
BOTTOM = "わからない"
# 行区切り文字 (source に実文字を置かない: memory feedback_write_tool_unicode_escape)
SEPARATORS = (chr(0x2028), chr(0x2029), chr(0x85))
N_PILOT = 684
N_MAIN = 1728


# ---------------------------------------------------------- 文面の読み取り


def user_text(body: dict[str, Any]) -> str:
    return body["messages"][-1]["content"]


def shown(body: dict[str, Any]) -> list[str]:
    """表示された選択肢 (最後の行の「: 」の後を「、」で区切る)."""
    return user_text(body).rsplit("\n", 1)[-1].split(": ", 1)[1].split("、")


def know_key(body: dict[str, Any]) -> str | None:
    text = user_text(body)
    head = "生き物: "
    return text.split("\n", 1)[0].removeprefix(head) if text.startswith(head) else None


# ------------------------------------------------------------- policies


def first_shown(_index: int, body: dict[str, Any]) -> str:
    """知識確認は正答、それ以外は常に表示の先頭 (状態を読まない)."""
    key = know_key(body)
    return bat.key_class(key) if key is not None else shown(body)[0]


def varying(_index: int, body: dict[str, Any]) -> str:
    """表示肢・Ω 外・⊥・装飾付き・行区切り付きを、body に決定的な乱数で混ぜる.

    ⊥ は seed だけで決める (族内の 2 arm は seed を共有するので、⊥ 率が族内で
    そろい envelope を通る)。
    """
    seed = body["options"]["seed"]
    rng = random.Random(f"{seed}-{sc.messages_sha256(body['messages'])}")
    key = know_key(body)
    if key is not None:
        cls = bat.key_class(key)
        return rng.choice(
            [cls, cls.capitalize(), f" {cls}.\n", cls + rng.choice(SEPARATORS)]
        )
    if random.Random(seed).random() < 0.05:
        return BOTTOM
    opts = shown(body)
    u = rng.random()
    if u < 0.6:
        return rng.choice(opts)
    if u < 0.7:
        return rng.choice([a for a in bat.ACTIONS if a not in opts])
    if u < 0.85:
        return f"  **{rng.choice(opts)}**\n"
    return rng.choice(opts) + rng.choice(SEPARATORS)


def failing(
    target: int, n_fail: int, make: Callable[[], object], base: Policy = first_shown
) -> Policy:
    """call_index = target の最初の n_fail 回の送信で make() を返す (例外は投げる)."""
    count = {"n": 0}

    def policy(index: int, body: dict[str, Any]) -> object:
        if index == target and count["n"] < n_fail:
            count["n"] += 1
            out = make()
            if isinstance(out, BaseException):
                raise out
            return out
        return base(index, body)

    return policy


def connect_error() -> Exception:
    return httpx.ConnectError("refused")


# ---------------------------------------------------------------- mock


def chat_response(content: object, model: str, done: str = "stop") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": model,
            "message": {"role": "assistant", "content": content},
            "done": True,
            "done_reason": done,
        },
    )


class FakeOllama:
    """``httpx.MockTransport`` の handler.

    policy は content (str / None) か応答を返すか、例外を投げる。
    """

    def __init__(
        self,
        policy: Policy,
        *,
        digests: tuple[str, ...] = (DIGEST,),
        templates: tuple[str, ...] = (TEMPLATE,),
        model: str | None = None,
        down: frozenset[int] = frozenset(),
    ) -> None:
        self.policy = policy
        self.bodies: list[dict[str, Any]] = []  # 届いた chat body (再送を含む)
        self.answered: list[dict[str, Any]] = []  # 正常に答えた body (call_index 順)
        self.digests = list(digests)  # /api/tags ごとに消費 (最後の 1 つは使い続ける)
        self.templates = list(templates)
        self.model = model
        self.down = down  # 何回目の /api/version を落とすか (0 = 開始時)
        self.n_version = -1

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/version":
            self.n_version += 1
            if self.n_version in self.down:
                raise httpx.ConnectError("refused", request=request)
            return httpx.Response(200, json={"version": VERSION})
        if path == "/api/tags":
            digest = self.digests.pop(0) if len(self.digests) > 1 else self.digests[0]
            model = {"name": bat.MODEL, "model": bat.MODEL, "digest": digest}
            return httpx.Response(200, json={"models": [model]})
        if path == "/api/show":
            if json.loads(request.content).get("model") != bat.MODEL:
                return httpx.Response(404, json={"error": "model not found"})
            t = self.templates.pop(0) if len(self.templates) > 1 else self.templates[0]
            return httpx.Response(200, json={"template": t})
        body = json.loads(request.content)
        self.bodies.append(body)
        content = self.policy(len(self.answered), body)
        if isinstance(content, httpx.Response):
            return content
        done = "stop"
        if isinstance(content, tuple):
            content, done = content
        if isinstance(content, str):
            self.answered.append(body)
        return chat_response(content, self.model or body["model"], done)


def do_run(stage: drv.Stage, policy: Policy, **kwargs: Any) -> tuple[str, FakeOllama]:
    ollama = FakeOllama(policy, **kwargs)
    reason = asyncio.run(drv.run(stage, httpx.MockTransport(ollama), backoff_s=0.0))
    return reason, ollama


def ok_manifest(stage_name: str) -> tuple[int, str]:
    return 0, f"x\nMANIFEST OK (stage {stage_name})\n"


def short_stage(run_dir: Path, lo: int = 104, hi: int = 116) -> drv.Stage:
    """Pilot の plan の一部 (KNOW 4 + masked 8) を grid とする短縮段.

    来歴・公開の test を軽く回す。
    """
    stage = drv.pilot_stage(run_dir)
    plan = stage.plan[lo:hi]
    return dataclasses.replace(stage, plan=plan, grid=frozenset(plan))


_REAL_RUN_MANIFEST = drv._run_manifest


@pytest.fixture(autouse=True)
def _fake_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(drv, "_run_manifest", ok_manifest)
    # 実の results/ と実の Ollama に触れないことを構造で保証する (code-reviewer LOW)
    monkeypatch.setattr(drv, "PILOT_DIR", tmp_path / "blocked" / "pilot")
    monkeypatch.setattr(drv, "RUN_DIR", tmp_path / "blocked" / "run")

    def no_real_transport(*_a: object, **_k: object) -> object:
        msg = "the real Ollama transport was used"
        raise AssertionError(msg)

    monkeypatch.setattr(drv.httpx, "AsyncHTTPTransport", no_real_transport)


# ------------------------------------------------------------- 出力の読み取り


def lines_of(path: Path) -> list[str]:
    """凍結 reader と同じ読み方 (``read_text().splitlines()``)."""
    return path.read_text(encoding="utf-8").splitlines()


def records(path: Path) -> list[sc.Sample]:
    return sc.load_records(lines_of(path))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def provenance(run_dir: Path) -> dict[str, Any]:
    return read_json(run_dir / drv.PROVENANCE_NAME)


PUBLISHED = "records.jsonl was published"


def assert_not_published(run_dir: Path) -> None:
    assert not (run_dir / drv.RECORDS_NAME).exists(), PUBLISHED
    prov = provenance(run_dir)
    assert prov["published"] is False
    for key in ("driver_sha256", "records_sha256", "meta_sha256"):
        assert key not in prov


# ---------------------------------------------------------------- fixtures


@pytest.fixture(scope="session")
def pilot_run(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, Path, str, FakeOllama]:
    """Pilot の全 run (684、混ぜる policy).

    run dir は tmp の root の凍結配置 (provenance の照合に使う)。
    """
    root = tmp_path_factory.mktemp("root")
    run_dir = root / man.EXP / "results" / "pilot"
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(drv, "_run_manifest", ok_manifest)
        reason, ollama = do_run(drv.pilot_stage(run_dir), varying)
    return root, run_dir, reason, ollama


@pytest.fixture(scope="session")
def main_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str, FakeOllama]:
    """本走の全 run (1,728、混ぜる policy、参照する observed = pilot の偽の環境)."""
    run_dir = tmp_path_factory.mktemp("main") / "run"
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(drv, "_run_manifest", ok_manifest)
        reason, ollama = do_run(drv.main_stage(run_dir, R_MAIN, OBSERVED), varying)
    return run_dir, reason, ollama


# ---------------------------------------------------------------- plan


def _pairs_alternate(plan: tuple[drv.Key, ...], arm_of: Callable[[str], str]) -> None:
    """2 件ずつが族内の 2 arm で、(r, probe, k) が同じ."""
    assert len(plan) % 2 == 0
    for a, b in zip(plan[::2], plan[1::2], strict=True):
        assert (arm_of(a[0]), arm_of(b[0])) in bat.FAMILIES
        assert a[1:] == b[1:]


def _unit_order(
    plan: tuple[drv.Key, ...], arm_of: Callable[[str], str]
) -> list[tuple[int, int, int]]:
    out: list[tuple[int, int, int]] = []
    probes = {p.probe_id: p for p in bat.probes()}
    for arm, r, pid, _k in plan:
        u = (r, bat.ARM_FAMILY[arm_of(arm)], probes[pid].triple)
        if not out or out[-1] != u:
            out.append(u)
    return out


def test_pilot_plan_is_the_frozen_grid_in_order() -> None:
    plan = drv.pilot_plan()
    assert len(plan) == N_PILOT == len(pg.pilot_grid())
    assert len(set(plan)) == len(plan)
    assert set(plan) == pg.pilot_grid()
    know = plan[:108]
    assert know == tuple(
        (pg.ARM_KNOW, 0, pg.know_probe_id(i), k) for i in range(36) for k in range(3)
    )
    masked = plan[108:]
    arm_of = pg.MASKED_ARMS.__getitem__
    _pairs_alternate(masked, arm_of)
    rs = range(bat.PILOT_R0, bat.PILOT_R0 + bat.PILOT_R)
    want = [(r, f, j) for r in rs for f in range(2) for j in range(bat.N_TRIPLES)]
    assert _unit_order(masked, arm_of) == want
    for i in range(0, len(masked), 6):
        unit = masked[i : i + 6]
        triple = [
            p.probe_id for p in bat.triple_probes(_unit_order(unit, arm_of)[0][2])
        ]
        assert [k[2] for k in unit[::2]] == triple


def test_main_plan_is_the_frozen_grid_in_order() -> None:
    plan = drv.main_plan(R_MAIN)
    assert len(plan) == N_MAIN
    assert set(plan) == sc.grid(R_MAIN, 1)
    assert len(set(plan)) == len(plan)
    _pairs_alternate(plan, str)
    assert _unit_order(plan, str) == [
        (u.replicate, u.family, u.triple) for u in bat.units(R_MAIN)
    ]


# ------------------------------------------------------------- 予定表


def test_every_planned_body_passes_the_frozen_checks(tmp_path: Path) -> None:
    pilot = drv.pilot_stage(tmp_path)
    assert drv.schedule_violations(pilot, drv.build_schedule(pilot), OBSERVED) == []
    main = drv.main_stage(tmp_path, R_MAIN, OBSERVED)
    assert drv.schedule_violations(main, drv.build_schedule(main), OBSERVED) == []


def _shift_request(stage: drv.Stage, index: int, how: str) -> drv.Stage:
    target = stage.plan[index]

    def request(key: drv.Key) -> tuple[list[dict[str, str]], int]:
        msgs, seed = stage.request(key)
        if key != target:
            return msgs, seed
        if how == "seed":
            return msgs, seed + 1
        arm, r, pid, _ = key
        lever = pg.MASKED_ARMS[arm]
        probe = {p.probe_id: p for p in bat.probes()}[pid]
        return bat.render_messages(lever, probe, r), seed  # masked でない状態

    return dataclasses.replace(stage, request=request)


@pytest.mark.parametrize(
    "how",
    [
        "seed",
        "unmasked",
        "duplicate",
        "missing",
        "float_option",
        "stream",
        "no_options",
    ],
)
def test_bad_schedule_makes_no_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, how: str
) -> None:
    """凍結済みの検査を通らない予定表: run dir を作らず、1 回も呼ばない (DD-1)."""
    run_dir = tmp_path / "run"
    stage = drv.pilot_stage(run_dir)
    if how in ("seed", "unmasked"):
        stage = _shift_request(stage, 400, how)
    elif how == "duplicate":
        stage = dataclasses.replace(stage, plan=(*stage.plan[:-1], stage.plan[0]))
    elif how == "missing":
        stage = dataclasses.replace(stage, plan=stage.plan[:-1])
    elif how == "float_option":
        monkeypatch.setitem(drv.FIXED_OPTIONS, "num_ctx", float(bat.NUM_CTX))
    else:
        real = drv.body_for
        target = stage.plan[500]

        def body_for(st: drv.Stage, key: drv.Key) -> dict[str, Any]:
            body = real(st, key)
            if key != target:
                return body
            if how == "stream":
                return {**body, "stream": True}
            return {k: v for k, v in body.items() if k != "options"}

        monkeypatch.setattr(drv, "body_for", body_for)
    ollama = FakeOllama(first_shown)
    with pytest.raises(drv.ScheduleError):
        asyncio.run(drv.run(stage, httpx.MockTransport(ollama), backoff_s=0.0))
    assert ollama.bodies == []
    assert not run_dir.exists()


def test_schedule_checks_meta_against_the_frozen_values(tmp_path: Path) -> None:
    pilot = drv.pilot_stage(tmp_path)
    schedule = drv.build_schedule(pilot)
    assert "schedule: meta: observed environment is missing or malformed" in (
        drv.schedule_violations(pilot, schedule, {**OBSERVED, "template_sha256": ""})
    )
    other = {**OBSERVED, "model_digest": OTHER_DIGEST}
    main = drv.main_stage(tmp_path, R_MAIN, other)
    assert "schedule: meta: observed environment differs from the pilot" in (
        drv.schedule_violations(main, drv.build_schedule(main), OBSERVED)
    )
    assert drv.schedule_violations(pilot, (), OBSERVED) != []
    assert drv.schedule_violations(pilot, schedule[:-1], OBSERVED) == [
        "schedule: bodies do not match the plan"
    ]
    assert drv.meta_for(schedule, OBSERVED) == {
        "request": sc.request_meta(),
        "observed": OBSERVED,
    }


def test_schedule_rejects_a_wrong_fixed_option(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """送る値が凍結値と違えば拒否する (driver の定数の誤りも、scorer の request で)."""
    pilot = drv.pilot_stage(tmp_path)
    monkeypatch.setitem(drv.FIXED_OPTIONS, "num_predict", bat.NUM_PREDICT + 1)
    out = drv.schedule_violations(pilot, drv.build_schedule(pilot), OBSERVED)
    assert "schedule: request conditions differ from the frozen values" in out


# ------------------------------------------------------- 送る直前の照合


def _body(stage: drv.Stage, index: int) -> dict[str, Any]:
    return drv.body_for(stage, stage.plan[index])


def _variants(body: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    opts = body["options"]
    msgs = body["messages"]
    return [
        ("model", {**body, "model": "qwen3:14b"}),
        ("think", {**body, "think": 0}),
        ("stream", {**body, "stream": 0}),
        ("num_ctx_float", {**body, "options": {**opts, "num_ctx": 4096.0}}),
        ("temperature", {**body, "options": {**opts, "temperature": 0.75}}),
        ("seed_float", {**body, "options": {**opts, "seed": float(opts["seed"])}}),
        ("seed_other", {**body, "options": {**opts, "seed": opts["seed"] + 1}}),
        ("extra_key", {**body, "keep_alive": 0}),
        ("extra_option", {**body, "options": {**opts, "top_k": 20}}),
        (
            "missing_option",
            {**body, "options": {k: v for k, v in opts.items() if k != "top_p"}},
        ),
        (
            "prompt",
            {
                **body,
                "messages": [msgs[0], {**msgs[1], "content": msgs[1]["content"] + " "}],
            },
        ),
        (
            "messages_extra_field",
            {**body, "messages": [{**msgs[0], "name": "x"}, msgs[1]]},
        ),
        (
            "messages_not_str",
            {**body, "messages": [{**msgs[0], "content": 1}, msgs[1]]},
        ),
        ("messages_not_list", {**body, "messages": 5}),
        ("not_a_dict", []),  # type: ignore[list-item]
    ]


@pytest.mark.parametrize("stage_name", ["pilot", "main"])
def test_check_sent_body_rejects_value_and_type(
    tmp_path: Path, stage_name: str
) -> None:
    stage = (
        drv.pilot_stage(tmp_path)
        if stage_name == "pilot"
        else drv.main_stage(tmp_path, R_MAIN, OBSERVED)
    )
    for index in (0, 300):
        body = _body(stage, index)
        drv.check_sent_body(stage, index, body)
        for name, bad in _variants(body):
            with pytest.raises(drv.SentBodyMismatchError):
                drv.check_sent_body(stage, index, bad)
            assert name


def test_check_uses_the_plan_position(tmp_path: Path) -> None:
    stage = drv.pilot_stage(tmp_path)
    drv.check_sent_body(stage, 200, _body(stage, 200))
    with pytest.raises(drv.SentBodyMismatchError):
        drv.check_sent_body(stage, 201, _body(stage, 200))


async def _post(observer: drv.ObservingTransport, path: str, body: object) -> None:
    async with httpx.AsyncClient(base_url="http://x", transport=observer) as http:
        await http.post(path, json=body)


def test_observer_refuses_before_the_inner_transport(tmp_path: Path) -> None:
    stage = drv.pilot_stage(tmp_path)
    ollama = FakeOllama(first_shown)
    observer = drv.ObservingTransport(httpx.MockTransport(ollama), stage)
    good = _body(stage, 3)
    with pytest.raises(drv.SentBodyMismatchError, match="without an expected call"):
        asyncio.run(_post(observer, drv.CHAT_PATH, good))
    observer.expected = 3
    with pytest.raises(drv.SentBodyMismatchError):
        asyncio.run(_post(observer, drv.CHAT_PATH, _variants(good)[6][1]))
    with pytest.raises(drv.SentBodyMismatchError, match="unexpected POST path"):
        asyncio.run(_post(observer, "/api/generate", good))
    with pytest.raises(drv.SentBodyMismatchError, match="unexpected POST path"):
        asyncio.run(_post(observer, drv.SHOW_PATH, {"model": bat.MODEL}))
    assert ollama.bodies == []
    asyncio.run(_post(observer, drv.CHAT_PATH, good))
    assert ollama.bodies == [good]
    assert observer.sent == {3: [good]}


def test_show_is_allowed_only_while_reading_observed(tmp_path: Path) -> None:
    stage = drv.pilot_stage(tmp_path)
    ollama = FakeOllama(first_shown)
    observer = drv.ObservingTransport(httpx.MockTransport(ollama), stage)

    async def read() -> dict[str, str]:
        async with httpx.AsyncClient(base_url="http://x", transport=observer) as http:
            return await drv.read_observed(http, observer)

    assert asyncio.run(read()) == OBSERVED
    assert observer.allow_show is False
    with pytest.raises(drv.SentBodyMismatchError, match="unexpected POST path"):
        asyncio.run(_post(observer, drv.SHOW_PATH, {"model": bat.MODEL}))


def test_shifted_body_is_refused_before_sending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """送る経路で body がずれたら、送らずに止まる (null の行も公開もしない)."""
    real = drv.send_chat

    async def shifted(http: httpx.AsyncClient, body: dict[str, Any]) -> drv.Reply:
        opts = {**body["options"], "seed": body["options"]["seed"] + 1}
        return await real(http, {**body, "options": opts})

    monkeypatch.setattr(drv, "send_chat", shifted)
    run_dir = tmp_path / "run"
    ollama = FakeOllama(first_shown)
    with pytest.raises(drv.SentBodyMismatchError):
        asyncio.run(
            drv.run(
                drv.pilot_stage(run_dir), httpx.MockTransport(ollama), backoff_s=0.0
            )
        )
    assert ollama.bodies == []
    assert lines_of(run_dir / drv.PARTIAL_NAME) == []
    assert_not_published(run_dir)
    assert provenance(run_dir)["exit_reason"] == drv.REASON_ABORTED


# ------------------------------------------------------------ 再送と raw = null


def test_resend_with_the_same_seed_recovers(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    reason, ollama = do_run(short_stage(run_dir), failing(5, 3, connect_error))
    assert reason == drv.REASON_COMPLETED
    sent = [b for b in ollama.bodies if b == ollama.answered[5]]
    assert len(sent) == 4
    assert records(run_dir / drv.RECORDS_NAME)[5].raw == first_shown(
        5, ollama.answered[5]
    )
    assert provenance(run_dir)["n_resends"] == 3
    attempts = [json.loads(x) for x in lines_of(run_dir / drv.ATTEMPTS_NAME)]
    assert [a["outcome"] for a in attempts if a["call_index"] == 5] == [
        "transport_failure",
        "transport_failure",
        "transport_failure",
        "ok",
    ]


def test_unresolved_transport_failure_records_null_and_stops(tmp_path: Path) -> None:
    """解けない transport 失敗: raw = null の行を書いて止まり、公開しない.

    凍結 pilot 判定は partial を not_computed と判定する (DD-3)。
    """
    run_dir = tmp_path / "run"
    reason, ollama = do_run(drv.pilot_stage(run_dir), failing(5, 99, connect_error))
    assert_not_published(run_dir)
    assert reason == drv.REASON_TRANSPORT
    rows = records(run_dir / drv.PARTIAL_NAME)
    assert len(rows) == 6
    assert rows[-1].raw is None
    assert rows[-1].parsed is None
    assert all(r.raw is not None for r in rows[:-1])
    # 再送 3 回 (literal: 定数の変異を捕まえる)
    assert len(ollama.bodies) == 5 + 1 + 3, "resent more or fewer than 3 times"
    prov = provenance(run_dir)
    assert prov["exit_reason"] == drv.REASON_TRANSPORT
    assert prov["status"] == sc.STATUS_NOT_COMPUTED
    meta = read_json(run_dir / drv.META_NAME)
    judged = pg.decide_pilot(rows, meta, certified=True, selected_r=R_MAIN)
    assert judged["status"] == pg.STATUS_NOT_COMPUTED


def test_null_content_is_a_transport_failure_not_bottom(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    reason, _ = do_run(short_stage(run_dir), failing(2, 99, lambda: None))
    assert_not_published(run_dir)
    assert reason == drv.REASON_TRANSPORT
    assert records(run_dir / drv.PARTIAL_NAME)[-1].raw is None
    attempts = [json.loads(x) for x in lines_of(run_dir / drv.ATTEMPTS_NAME)]
    outcomes = [a["outcome"] for a in attempts if a["call_index"] == 2]
    assert outcomes == ["transport_failure"] * 4


@pytest.mark.parametrize(
    "make",
    [
        lambda: httpx.Response(500, json={"message": {"content": "sort_cards"}}),
        lambda: httpx.Response(200, content=b"not json"),
        lambda: httpx.Response(200, json={"model": bat.MODEL}),
        lambda: httpx.Response(200, json=["x"]),
        lambda: httpx.ReadTimeout("slow"),
    ],
    ids=["http500", "non_json", "no_message", "non_object", "timeout"],
)
def test_failed_responses_are_resent(
    tmp_path: Path, make: Callable[[], object]
) -> None:
    run_dir = tmp_path / "run"
    reason, ollama = do_run(short_stage(run_dir), failing(2, 2, make))
    assert reason == drv.REASON_COMPLETED
    assert len(ollama.bodies) == 12 + 2
    attempts = [json.loads(x) for x in lines_of(run_dir / drv.ATTEMPTS_NAME)]
    assert [a["outcome"] for a in attempts if a["call_index"] == 2] == [
        "transport_failure",
        "transport_failure",
        "ok",
    ]


def test_other_exceptions_abort_without_a_null_row(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    with pytest.raises(ValueError, match="boom"):
        do_run(short_stage(run_dir), failing(3, 1, lambda: ValueError("boom")))
    assert_not_published(run_dir)
    rows = records(run_dir / drv.PARTIAL_NAME)
    assert len(rows) == 3
    assert all(r.raw is not None for r in rows)
    assert provenance(run_dir)["exit_reason"] == drv.REASON_ABORTED


# ---------------------------------------------------------------- 記録


def test_complete_pilot_run_is_published_and_computed(
    pilot_run: tuple[Path, Path, str, FakeOllama],
) -> None:
    _root, run_dir, reason, _ = pilot_run
    assert (run_dir / drv.RECORDS_NAME).exists(), "the complete run was not published"
    assert reason == drv.REASON_COMPLETED
    assert not (run_dir / drv.PARTIAL_NAME).exists()
    rows = records(run_dir / drv.RECORDS_NAME)
    assert len(rows) == N_PILOT
    assert pg.structure_violations(rows) == []
    meta = read_json(run_dir / drv.META_NAME)
    assert sc.meta_violations(meta) == []
    assert meta == {"request": sc.request_meta(), "observed": OBSERVED}
    prov = provenance(run_dir)
    assert prov["exit_reason"] == drv.REASON_COMPLETED
    assert prov["published"] is True
    assert prov["n_records"] == N_PILOT, "n_records differs from the plan"
    assert prov["anomalies"] == []
    assert prov["status"] is None


def test_records_follow_the_schema_and_the_plan(
    pilot_run: tuple[Path, Path, str, FakeOllama],
) -> None:
    _root, run_dir, _, ollama = pilot_run
    plan = drv.pilot_plan()
    for i, line in enumerate(lines_of(run_dir / drv.RECORDS_NAME)):
        obj = json.loads(line)
        assert set(obj) == set(sc._FIELDS)
        assert obj["call_index"] == i
        assert (obj["arm"], obj["replicate"], obj["probe_id"], obj["k"]) == plan[i]
        sent = ollama.answered[i]
        assert obj["seed"] == sent["options"]["seed"]
        assert obj["prompt_sha256"] == sc.messages_sha256(sent["messages"])


def test_raw_is_recorded_verbatim(
    pilot_run: tuple[Path, Path, str, FakeOllama],
) -> None:
    _root, run_dir, _, ollama = pilot_run
    rows = records(run_dir / drv.RECORDS_NAME)
    for i, row in enumerate(rows):
        assert row.raw == varying(i, ollama.answered[i]), "raw is not recorded verbatim"
    assert any(row.raw is not None and row.raw != row.raw.strip() for row in rows)


def test_parse_follows_the_arm(pilot_run: tuple[Path, Path, str, FakeOllama]) -> None:
    """知識確認は分類名 (parse_class)、masked は行動 label (parse_choice)."""
    _root, run_dir, _, _ = pilot_run
    rows = records(run_dir / drv.RECORDS_NAME)
    know = [r for r in rows if r.arm == pg.ARM_KNOW]
    assert len(know) == 108
    assert all(r.raw is not None and r.parsed == pg.parse_class(r.raw) for r in know)
    assert {r.parsed for r in know} == set(bat.CLASSES)
    masked = [r for r in rows if r.arm != pg.ARM_KNOW]
    assert all(r.raw is not None and r.parsed == sc.parse_choice(r.raw) for r in masked)
    assert None in {r.parsed for r in masked}


def test_line_separators_in_raw_do_not_split_a_record(
    pilot_run: tuple[Path, Path, str, FakeOllama],
) -> None:
    _root, run_dir, _, _ = pilot_run
    path = run_dir / drv.RECORDS_NAME
    rows = records(path)
    assert len(lines_of(path)) == N_PILOT
    for sep in SEPARATORS:
        assert any(r.raw is not None and sep in r.raw for r in rows)
    data = path.read_bytes()
    for sep in SEPARATORS:
        assert sep.encode("utf-8") not in data


def test_written_files_use_lf(pilot_run: tuple[Path, Path, str, FakeOllama]) -> None:
    _root, run_dir, _, _ = pilot_run
    for name in (
        drv.RECORDS_NAME,
        drv.ATTEMPTS_NAME,
        drv.META_NAME,
        drv.PROVENANCE_NAME,
    ):
        assert b"\r" not in (run_dir / name).read_bytes()


def test_pilot_gate_cli_and_provenance_contract(
    pilot_run: tuple[Path, Path, str, FakeOllama],
) -> None:
    """凍結 pilot 判定の CLI が gate を書き、第 2 段の照合が provenance を受け入れる."""
    root, run_dir, _, _ = pilot_run
    for rel in (man.CERT, man.SKETCH):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_ROOT / rel, root / rel)
    (root / man.DRIVER).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(drv.__file__), root / man.DRIVER)
    gate_path = root / man.PILOT_GATE
    assert (
        pg.main(
            [
                "--records",
                str(root / man.PILOT_RECORDS),
                "--meta",
                str(root / man.PILOT_META),
                "--cert",
                str(root / man.CERT),
                "--sketch",
                str(root / man.SKETCH),
                "--out",
                str(gate_path),
            ]
        )
        == 0
    )
    gate = read_json(gate_path)
    assert gate["decision"] == pg.DECISION_GO
    assert gate["R"] == R_MAIN
    prov = provenance(run_dir)
    assert prov["driver_sha256"] == man.sha256(Path(drv.__file__))
    assert prov["records_sha256"] == man.sha256(run_dir / drv.RECORDS_NAME)
    assert prov["meta_sha256"] == man.sha256(run_dir / drv.META_NAME)
    assert man.pilot_gate_violations(gate, prov, R_MAIN, root) == []


def test_main_run_is_computed_by_the_frozen_scorer(
    main_run: tuple[Path, str, FakeOllama],
) -> None:
    run_dir, reason, _ = main_run
    assert (run_dir / drv.RECORDS_NAME).exists(), "the complete run was not published"
    assert reason == drv.REASON_COMPLETED
    rows = records(run_dir / drv.RECORDS_NAME)
    assert len(rows) == N_MAIN
    assert sc.structure_violations(rows, R_MAIN, 1) == []
    meta = read_json(run_dir / drv.META_NAME)
    assert sc.meta_violations(meta, OBSERVED) == []
    result = sc.evaluate(
        rows,
        meta,
        certified=True,
        r_count=R_MAIN,
        pilot_max_bottom=0.1,
        reference_observed=OBSERVED,
    )
    assert result["status"] == sc.STATUS_COMPUTED
    assert result["verdict"] != sc.VERDICT_INVALID_SCORER


def test_main_refuses_an_observed_environment_different_from_the_pilot(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    other = {**OBSERVED, "template_sha256": "f" * 64}
    ollama = FakeOllama(first_shown)
    with pytest.raises(drv.PreflightError, match="differs from the pilot gate"):
        asyncio.run(
            drv.run(
                drv.main_stage(run_dir, R_MAIN, other),
                httpx.MockTransport(ollama),
                backoff_s=0.0,
            )
        )
    assert ollama.bodies == []
    assert not run_dir.exists()


# ---------------------------------------------------------------- 公開


def _write_partial(run_dir: Path, rows: list[sc.Sample], meta: object) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(vars(r), sort_keys=True) + "\n" for r in rows)
    (run_dir / drv.PARTIAL_NAME).write_text(text, encoding="utf-8", newline="\n")
    (run_dir / drv.META_NAME).write_text(json.dumps(meta), encoding="utf-8")


def _complete_rows(stage: drv.Stage) -> list[sc.Sample]:
    out = []
    for i, body in enumerate(drv.build_schedule(stage)):
        cand = drv.skeleton(i, stage.plan[i], body)
        raw = first_shown(i, body)
        out.append(
            dataclasses.replace(cand, raw=raw, parsed=stage.parse(cand.arm, raw))
        )
    return out


def test_publication_problems_check_completeness_and_structure(tmp_path: Path) -> None:
    stage = short_stage(tmp_path)
    rows = _complete_rows(stage)
    meta = drv.meta_for(drv.build_schedule(stage), OBSERVED)
    _write_partial(tmp_path, rows, meta)
    assert drv.publication_problems(stage) == []
    _write_partial(tmp_path, rows[:-1], meta)
    assert "records do not cover the frozen grid" in drv.publication_problems(stage)
    _write_partial(tmp_path, [*rows, rows[0]], meta)
    assert "records do not cover the frozen grid" in drv.publication_problems(stage)
    null = [*rows[:-1], dataclasses.replace(rows[-1], raw=None, parsed=None)]
    _write_partial(tmp_path, null, meta)
    assert "a transport failure is recorded" in drv.publication_problems(stage)
    wrong = [*rows[:-1], dataclasses.replace(rows[-1], seed=rows[-1].seed + 1)]
    _write_partial(tmp_path, wrong, meta)
    assert pg.structure_violations(wrong)[0] in drv.publication_problems(stage)
    _write_partial(tmp_path, rows, {**meta, "observed": {}})
    assert "meta: observed environment is missing or malformed" in (
        drv.publication_problems(stage)
    )


def test_publication_problems_read_like_the_judge(tmp_path: Path) -> None:
    """判定と同じ reader (``splitlines``) で読む: 行区切り文字で割れる記録は読めない."""
    stage = short_stage(tmp_path)
    rows = _complete_rows(stage)
    rows[0] = dataclasses.replace(rows[0], raw=rows[0].raw + SEPARATORS[0])
    meta = drv.meta_for(drv.build_schedule(stage), OBSERVED)
    tmp_path.mkdir(parents=True, exist_ok=True)
    text = "".join(
        json.dumps(vars(r), sort_keys=True, ensure_ascii=False) + "\n" for r in rows
    )
    (tmp_path / drv.PARTIAL_NAME).write_text(text, encoding="utf-8", newline="\n")
    (tmp_path / drv.META_NAME).write_text(json.dumps(meta), encoding="utf-8")
    out = drv.publication_problems(stage)
    assert len(out) == 1
    assert out[0].startswith("unreadable: RecordError")
    (tmp_path / drv.META_NAME).unlink()
    assert drv.publication_problems(stage)[0].startswith("unreadable")


def test_publication_problems_read_the_written_meta(tmp_path: Path) -> None:
    stage = drv.main_stage(tmp_path, R_MAIN, OBSERVED)
    stage = dataclasses.replace(
        stage, plan=stage.plan[:6], grid=frozenset(stage.plan[:6])
    )
    rows = _complete_rows(stage)
    meta = drv.meta_for(drv.build_schedule(stage), OBSERVED)
    _write_partial(tmp_path, rows, meta)
    assert drv.publication_problems(stage) == []
    other = {**meta, "observed": {**OBSERVED, "ollama_version": "other"}}
    _write_partial(tmp_path, rows, other)
    assert "meta: observed environment differs from the pilot" in (
        drv.publication_problems(stage)
    )


def test_publication_is_two_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """rename の前の来歴は未公開で 3 項目を持たない (DD-5).

    rename の後は公開済みで、3 項目が現在のファイルと一致する。
    """
    run_dir = tmp_path / "run"
    seen: dict[str, Any] = {}
    real = drv.publish

    def spy(path: Path) -> None:
        seen.update(provenance(path))
        real(path)

    monkeypatch.setattr(drv, "publish", spy)
    reason, _ = do_run(short_stage(run_dir), first_shown)
    assert seen, "publish was not called"
    assert seen["exit_reason"] == drv.REASON_ABORTED
    assert drv.PENDING_NOTE in seen["error"]
    assert seen["published"] is False
    assert seen["publishable"] is True
    for key in ("driver_sha256", "records_sha256", "meta_sha256"):
        assert key not in seen
    assert reason == drv.REASON_COMPLETED
    prov = provenance(run_dir)
    assert prov["exit_reason"] == drv.REASON_COMPLETED
    assert prov["published"] is True
    assert prov["error"] is None
    assert prov["driver_sha256"] == man.sha256(Path(drv.__file__))
    assert prov["driver_sha256"] == drv._DRIVER_SHA
    assert prov["records_sha256"] == man.sha256(run_dir / drv.RECORDS_NAME)
    assert prov["meta_sha256"] == man.sha256(run_dir / drv.META_NAME)


def _swap_before_finish(
    monkeypatch: pytest.MonkeyPatch, run_dir: Path, what: str
) -> None:
    """最後の呼び出しの後 (終了時の observed を読む間) に差し替える.

    partial か meta を、別の正しい中身にする。
    """
    real = drv.final_observed

    async def swapped(*args: Any) -> tuple[dict[str, str] | None, str | None]:
        if what == "records":
            path = run_dir / drv.PARTIAL_NAME
            rows = records(path)
            last = rows[-1]
            assert last.raw is not None
            rows[-1] = dataclasses.replace(last, raw=last.raw + " ")  # parse は同じ
            text = "".join(json.dumps(vars(r), sort_keys=True) + "\n" for r in rows)
            path.write_text(text, encoding="utf-8", newline="\n")
        else:
            meta = read_json(run_dir / drv.META_NAME)
            meta["observed"]["model_digest"] = OTHER_DIGEST
            (run_dir / drv.META_NAME).write_text(
                drv.json_text(meta), encoding="utf-8", newline="\n"
            )
        return await real(*args)

    monkeypatch.setattr(drv, "final_observed", swapped)


@pytest.mark.parametrize("what", ["records", "meta"])
def test_swapped_files_are_not_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, what: str
) -> None:
    """別の run の記録・meta への差し替えは公開しない (Codex HIGH-1).

    差し替えた中身は凍結の検査を通る。
    """
    run_dir = tmp_path / "run"
    _swap_before_finish(monkeypatch, run_dir, what)
    reason, _ = do_run(short_stage(run_dir), first_shown)
    assert_not_published(run_dir)
    assert reason == drv.REASON_ABORTED
    name = drv.PARTIAL_NAME if what == "records" else drv.META_NAME
    assert provenance(run_dir)["read_back_problems"] == [
        f"{name} differs from what this run wrote"
    ]


def test_files_changed_after_the_rename_are_not_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """rename の後に差し替わったら、来歴に 3 項目を書かない (第 2 段が拒否する)."""
    real = drv.publish

    def publish_then_touch(path: Path) -> None:
        real(path)
        with (path / drv.RECORDS_NAME).open("a", encoding="utf-8", newline="\n") as fh:
            fh.write("\n")

    monkeypatch.setattr(drv, "publish", publish_then_touch)
    run_dir = tmp_path / "run"
    reason, _ = do_run(short_stage(run_dir), first_shown)
    assert reason == drv.REASON_ABORTED
    prov = provenance(run_dir)
    assert prov["published"] is False
    assert "changed after the read-back" in prov["error"]
    for key in ("driver_sha256", "records_sha256", "meta_sha256"):
        assert key not in prov
    # 公開名からも退ける (残すと凍結 run.sh の test -f を通る、code-reviewer LOW)
    assert not (run_dir / drv.RECORDS_NAME).exists(), PUBLISHED
    assert (run_dir / drv.REJECTED_NAME).exists()


@pytest.mark.parametrize("what", ["records", "meta"])
def test_provenance_hashes_are_the_written_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, what: str
) -> None:
    """来歴の records・meta の sha256 は、この run が書いた bytes から取る.

    rename の後の照合を通った直後に差し替わっても、来歴は差し替え後に
    結び付かない (code-reviewer 再レビューの MEDIUM)。
    """
    run_dir = tmp_path / "run"
    name = drv.RECORDS_NAME if what == "records" else drv.META_NAME
    real = drv.binding_problems
    before: list[bytes] = []

    def check_then_touch(
        rdir: Path, records_name: str, records: bytes, meta: bytes
    ) -> list[str]:
        out = real(rdir, records_name, records, meta)
        if records_name == drv.RECORDS_NAME and out == []:
            path = rdir / name
            before.append(path.read_bytes())
            with path.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write("\n")
        return out

    monkeypatch.setattr(drv, "binding_problems", check_then_touch)
    reason, _ = do_run(short_stage(run_dir), first_shown)
    assert reason == drv.REASON_COMPLETED
    prov = provenance(run_dir)
    key = "records_sha256" if what == "records" else "meta_sha256"
    assert prov[key] == hashlib.sha256(before[0]).hexdigest()
    assert prov[key] != man.sha256(run_dir / name)


def test_pinned_change_during_the_manifest_check_blocks_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """固定ファイルは公開時の manifest の照合の後に比べる (Codex HIGH-2).

    照合の間の差し替えも捕まえる。
    """
    checked = {"manifest": False}

    def manifest(stage_name: str) -> tuple[int, str]:
        checked["manifest"] = True
        return ok_manifest(stage_name)

    monkeypatch.setattr(drv, "_run_manifest", manifest)
    monkeypatch.setattr(
        drv, "pinned_sha256", lambda _s: {"a": "2" if checked["manifest"] else "1"}
    )
    run_dir = tmp_path / "run"
    reason, _ = do_run(short_stage(run_dir), first_shown)
    assert_not_published(run_dir)
    assert reason == drv.REASON_ABORTED
    assert provenance(run_dir)["pinned_changed"] == ["a"]


def test_pinned_change_during_the_read_back_blocks_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """固定ファイルは読み戻しの後にも比べる (読み戻しの間の差し替えも捕まえる)."""
    read = {"back": False}
    real = drv.publication_problems

    def read_back(stage: drv.Stage) -> list[str]:
        read["back"] = True
        return real(stage)

    monkeypatch.setattr(drv, "publication_problems", read_back)
    monkeypatch.setattr(
        drv, "pinned_sha256", lambda _s: {"a": "2" if read["back"] else "1"}
    )
    run_dir = tmp_path / "run"
    reason, _ = do_run(short_stage(run_dir), first_shown)
    assert_not_published(run_dir)
    assert reason == drv.REASON_ABORTED
    assert provenance(run_dir)["pinned_changed"] == ["a"]


@pytest.mark.parametrize(("start", "published"), [("launch", False), ("now", True)])
def test_run_compares_with_the_pinned_values_taken_at_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, start: str, *, published: bool
) -> None:
    monkeypatch.setattr(drv, "pinned_sha256", lambda _s: {"a": "now"})
    run_dir = tmp_path / "run"
    ollama = FakeOllama(first_shown)
    asyncio.run(
        drv.run(
            short_stage(run_dir),
            httpx.MockTransport(ollama),
            backoff_s=0.0,
            pinned_start={"a": start},
        )
    )
    assert (run_dir / drv.RECORDS_NAME).exists() is published
    assert provenance(run_dir)["pinned_changed"] == ([] if published else ["a"])


def test_driver_swap_is_detected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ディスクの driver が実行中と違えば、起動を拒否し公開もしない (Codex HIGH-2)."""
    monkeypatch.setattr(drv, "_DRIVER_SHA", "0" * 64)
    run_dir = tmp_path / "run"
    reason, _ = do_run(short_stage(run_dir), first_shown)
    assert_not_published(run_dir)
    assert reason == drv.REASON_ABORTED
    swapped = "the driver on disk differs from the running driver"
    assert swapped in provenance(run_dir)["anomalies"]
    monkeypatch.setattr(drv, "certification_problems", lambda _p: [])
    monkeypatch.setattr(drv, "manifest_problems", lambda _s: [])
    monkeypatch.setattr(drv, "_git", lambda *_a: "")
    assert drv.launch_problems("pilot") == [swapped]


def test_provenance_binds_the_running_driver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """来歴の driver_sha256 は import した driver の値 (Codex HIGH-2).

    公開の後にディスクを読み直さない。
    """
    copy = tmp_path / "driver.py"
    shutil.copyfile(Path(drv.__file__), copy)
    monkeypatch.setattr(drv, "_DRIVER_PATH", copy)
    real = drv.publish

    def publish_then_swap(path: Path) -> None:
        real(path)
        copy.write_text("# swapped\n", encoding="utf-8")

    monkeypatch.setattr(drv, "publish", publish_then_swap)
    run_dir = tmp_path / "run"
    reason, _ = do_run(short_stage(run_dir), first_shown)
    assert reason == drv.REASON_COMPLETED
    assert provenance(run_dir)["driver_sha256"] == drv._DRIVER_SHA
    assert man.sha256(Path(drv.__file__)) == drv._DRIVER_SHA


def test_finish_length_is_counted(tmp_path: Path) -> None:
    def policy(index: int, body: dict[str, Any]) -> object:
        out = first_shown(index, body)
        return (out, "length") if index in (1, 4) else out

    run_dir = tmp_path / "run"
    reason, _ = do_run(short_stage(run_dir), policy)
    assert reason == drv.REASON_COMPLETED
    assert provenance(run_dir)["n_finish_length"] == 2


def test_publication_failure_is_recorded_as_aborted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_run_dir: Path) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(drv, "publish", broken)
    run_dir = tmp_path / "run"
    reason, _ = do_run(short_stage(run_dir), first_shown)
    assert_not_published(run_dir)
    assert reason == drv.REASON_ABORTED
    assert "publication failed: OSError: disk full" in provenance(run_dir)["error"]


def test_final_provenance_failure_keeps_records_but_aborts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = drv.write_json_durable

    def flaky(path: Path, obj: object, *, exclusive: bool) -> None:
        if path.name == drv.PROVENANCE_NAME and not exclusive:
            raise OSError("readonly")
        real(path, obj, exclusive=exclusive)

    monkeypatch.setattr(drv, "write_json_durable", flaky)
    run_dir = tmp_path / "run"
    reason, _ = do_run(short_stage(run_dir), first_shown)
    # 来歴に 3 項目が無く第 2 段に使えないので、completed で終えない
    assert reason == drv.REASON_ABORTED
    assert (run_dir / drv.RECORDS_NAME).exists()
    prov = provenance(run_dir)
    assert prov["published"] is False
    assert "driver_sha256" not in prov


def test_provenance_failure_keeps_the_original_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(path: Path, obj: object, *, exclusive: bool) -> None:
        if path.name == drv.PROVENANCE_NAME:
            raise OSError("readonly")
        drv_write(path, obj, exclusive=exclusive)

    drv_write = drv.write_json_durable
    monkeypatch.setattr(drv, "write_json_durable", broken)
    run_dir = tmp_path / "run"
    with pytest.raises(ValueError, match="boom") as info:
        do_run(short_stage(run_dir), failing(3, 1, lambda: ValueError("boom")))
    assert any("provenance / publication failed" in n for n in info.value.__notes__)


def test_manifest_failure_at_publication_blocks_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(drv, "_run_manifest", lambda _s: (1, "MANIFEST MISMATCH (1)\n"))
    run_dir = tmp_path / "run"
    reason, _ = do_run(short_stage(run_dir), first_shown)
    assert_not_published(run_dir)
    assert reason == drv.REASON_ABORTED
    assert provenance(run_dir)["manifest_problems_at_publication"]


def test_read_back_failure_blocks_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(drv, "publication_problems", lambda _stage: ["broken"])
    run_dir = tmp_path / "run"
    reason, _ = do_run(short_stage(run_dir), first_shown)
    assert_not_published(run_dir)
    assert reason == drv.REASON_ABORTED
    assert provenance(run_dir)["read_back_problems"] == ["broken"]


# ---------------------------------------------------------------- 来歴の異常


def test_unexpected_response_model_blocks_publication(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    reason, _ = do_run(short_stage(run_dir), first_shown, model="qwen3:14b")
    assert_not_published(run_dir)
    assert reason == drv.REASON_ABORTED
    assert any(
        "unexpected response models" in a for a in provenance(run_dir)["anomalies"]
    )


@pytest.mark.parametrize("what", ["digest", "template"])
def test_observed_change_during_the_run_blocks_publication(
    tmp_path: Path, what: str
) -> None:
    run_dir = tmp_path / "run"
    kwargs: dict[str, Any] = (
        {"digests": (DIGEST, OTHER_DIGEST)}
        if what == "digest"
        else {"templates": (TEMPLATE, TEMPLATE + " ")}
    )
    reason, _ = do_run(short_stage(run_dir), first_shown, **kwargs)
    assert_not_published(run_dir)
    assert reason == drv.REASON_ABORTED
    prov = provenance(run_dir)
    assert prov["observed_start"] == OBSERVED
    assert prov["observed_end"] != OBSERVED
    assert any("observed environment changed" in a for a in prov["anomalies"])


def test_pinned_file_change_during_the_run_blocks_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = iter([{"a": "1", "b": "1"}, {"a": "1", "b": "2"}])
    monkeypatch.setattr(drv, "pinned_sha256", lambda _stage: next(calls))
    run_dir = tmp_path / "run"
    reason, _ = do_run(short_stage(run_dir), first_shown)
    assert_not_published(run_dir)
    assert reason == drv.REASON_ABORTED
    assert provenance(run_dir)["pinned_changed"] == ["b"]


def test_final_observed_failure_aborts_a_finished_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    reason, _ = do_run(short_stage(run_dir), first_shown, down=frozenset({1, 2, 3, 4}))
    assert_not_published(run_dir)
    assert reason == drv.REASON_ABORTED
    assert "final observed failed" in provenance(run_dir)["error"]


def test_final_observed_failure_keeps_a_transport_failure(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    reason, _ = do_run(
        short_stage(run_dir),
        failing(2, 99, connect_error),
        down=frozenset({1, 2, 3, 4}),
    )
    assert reason == drv.REASON_TRANSPORT


def test_final_observed_is_resent(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    reason, _ = do_run(short_stage(run_dir), first_shown, down=frozenset({1, 2, 3}))
    assert reason == drv.REASON_COMPLETED
    assert provenance(run_dir)["observed_end"] == OBSERVED


# ---------------------------------------------------------------- 運用の保護


def test_run_refuses_a_non_empty_run_dir(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "old.txt").write_text("x", encoding="utf-8")
    ollama = FakeOllama(first_shown)
    with pytest.raises(FileExistsError, match="no resume"):
        asyncio.run(
            drv.run(
                drv.pilot_stage(run_dir), httpx.MockTransport(ollama), backoff_s=0.0
            )
        )
    assert ollama.bodies == []
    assert sorted(p.name for p in run_dir.iterdir()) == ["old.txt"]


def test_preflight_failure_writes_nothing(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    ollama = FakeOllama(first_shown, down=frozenset({0}))
    with pytest.raises(drv.PreflightError):
        asyncio.run(
            drv.run(
                drv.pilot_stage(run_dir), httpx.MockTransport(ollama), backoff_s=0.0
            )
        )
    assert not run_dir.exists()


def _show_only(response: httpx.Response) -> Callable[[httpx.Request], httpx.Response]:
    base = FakeOllama(first_shown)

    def handler(request: httpx.Request) -> httpx.Response:
        return response if request.url.path == drv.SHOW_PATH else base(request)

    return handler


@pytest.mark.parametrize(
    "handler",
    [
        _show_only(httpx.Response(404, json={"template": TEMPLATE})),
        lambda r: (
            httpx.Response(200, json={"models": [{"name": "other", "digest": DIGEST}]})
            if r.url.path == "/api/tags"
            else FakeOllama(first_shown)(r)
        ),
        _show_only(httpx.Response(200, json={"modelfile": "x"})),
        _show_only(httpx.Response(200, json={"template": None})),
        lambda r: (
            httpx.Response(200, json={"models": []})
            if r.url.path == "/api/tags"
            else FakeOllama(first_shown)(r)
        ),
        lambda r: (
            httpx.Response(200, json={"version": ""})
            if r.url.path == "/api/version"
            else FakeOllama(first_shown)(r)
        ),
    ],
    ids=[
        "show_404",
        "other_model",
        "no_template",
        "null_template",
        "no_model",
        "no_version",
    ],
)
def test_preflight_requires_the_environment_identity(
    tmp_path: Path, handler: Callable[[httpx.Request], httpx.Response]
) -> None:
    run_dir = tmp_path / "run"
    with pytest.raises(drv.PreflightError):
        asyncio.run(
            drv.run(
                drv.pilot_stage(run_dir), httpx.MockTransport(handler), backoff_s=0.0
            )
        )
    assert not run_dir.exists()


def test_meta_is_on_disk_before_the_first_call(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    seen: list[object] = []

    def policy(index: int, body: dict[str, Any]) -> str:
        if index == 0 and not seen:
            seen.append(read_json(run_dir / drv.META_NAME))
        return first_shown(index, body)

    do_run(short_stage(run_dir), policy)
    assert seen == [{"request": sc.request_meta(), "observed": OBSERVED}]


@pytest.mark.parametrize(
    "argv",
    [
        ["--stage", "pilot", "--run-dir", "x"],
        ["--stage", "pilot", "--endpoint", "http://x"],
        ["--stage", "other"],
        [],
    ],
)
def test_main_takes_only_the_stage(argv: list[str]) -> None:
    with pytest.raises(SystemExit):
        drv.main(argv)


def test_main_refuses_to_launch_without_touching_the_run_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    pilot_dir = tmp_path / "pilot"
    monkeypatch.setattr(drv, "PILOT_DIR", pilot_dir)
    monkeypatch.setattr(drv, "launch_problems", lambda _stage: ["not certified"])
    # transport の封鎖 (autouse) が main を例外で止めると、拒否が外れても見逃す。
    # この test では transport を作れるようにして、run に届いたかを記録で見る
    monkeypatch.setattr(drv.httpx, "AsyncHTTPTransport", lambda: "transport")

    called: list[object] = []

    def no_run(*a: object, **_k: object) -> str:
        called.append(a)  # main は例外を握るので、呼ばれたことを記録で見る
        raise RuntimeError

    monkeypatch.setattr(drv, "run", no_run)
    assert drv.main(["--stage", "pilot"]) == drv.EXIT_CODES[drv.REASON_ABORTED]
    assert called == []
    assert not pilot_dir.exists()
    assert "[driver] refuse to launch: not certified" in capsys.readouterr().out


def test_main_runs_the_stage_and_returns_the_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[drv.Stage] = []
    pinned: list[object] = []

    async def fake_run(stage: drv.Stage, _transport: object, **kw: object) -> str:
        seen.append(stage)
        pinned.append(kw.get("pinned_start"))
        return drv.REASON_TRANSPORT

    launched = {"done": False}

    def launch(_stage: str) -> list[str]:
        launched["done"] = True
        return []

    monkeypatch.setattr(
        drv, "pinned_sha256", lambda s: {"stage": s, "after_launch": launched["done"]}
    )
    monkeypatch.setattr(drv, "launch_problems", launch)
    # run を差し替えたので、transport は作るだけ (autouse の封鎖をこの test だけ外す)
    monkeypatch.setattr(drv.httpx, "AsyncHTTPTransport", lambda: "transport")
    monkeypatch.setattr(drv, "run", fake_run)
    monkeypatch.setattr(drv, "PILOT_DIR", tmp_path / "pilot")
    assert drv.main(["--stage", "pilot"]) == drv.EXIT_CODES[drv.REASON_TRANSPORT]
    assert seen[0].name == drv.STAGE_PILOT
    assert seen[0].run_dir == tmp_path / "pilot"
    gate = tmp_path / "gate.json"
    gate.write_text(
        json.dumps({"decision": "GO", "R": R_MAIN, "observed": OBSERVED}),
        encoding="utf-8",
    )
    monkeypatch.setattr(drv, "GATE_PATH", gate)
    monkeypatch.setattr(drv, "RUN_DIR", tmp_path / "run")
    launched["done"] = False
    assert drv.main(["--stage", "main"]) == drv.EXIT_CODES[drv.REASON_TRANSPORT]
    assert seen[1].name == drv.STAGE_MAIN
    assert seen[1].run_dir == tmp_path / "run"
    assert seen[1].reference_observed == OBSERVED
    assert seen[1].plan == drv.main_plan(R_MAIN)
    # 固定ファイルの sha256 は起動の検査の前に取って run に渡す (Codex HIGH-2)
    assert pinned == [
        {"stage": "pilot", "after_launch": False},
        {"stage": "main", "after_launch": False},
    ]


# ---------------------------------------------------------------- 起動の前提


@pytest.mark.parametrize(
    ("stage", "result", "ok"),
    [
        ("pilot", (0, "a\nMANIFEST OK (stage pilot)\n"), True),
        ("pilot", (1, "MANIFEST OK (stage pilot)\n"), False),
        ("pilot", (0, "MANIFEST OK (stage main)\n"), False),
        ("pilot", (0, "MANIFEST OK (stage pilot)\nlater\n"), False),
        ("pilot", (0, ""), False),
        ("pilot", (0, "MANIFEST BOUND, NOT FROZEN (draft, stage pilot)\n"), False),
        ("pilot", (0, "MANIFEST OK\n"), False),
        ("main", (0, "MANIFEST OK (stage main)\n"), True),
        ("main", (0, "MANIFEST OK (stage pilot)\n"), False),
        # 末尾の空白・空行を消さない (Codex LOW-5)
        ("pilot", (0, "MANIFEST OK (stage pilot) \n"), False),
        ("pilot", (0, "MANIFEST OK (stage pilot)\n\n"), False),
    ],
)
def test_manifest_problems_require_the_exact_ok_line(
    monkeypatch: pytest.MonkeyPatch, stage: str, result: tuple[int, str], *, ok: bool
) -> None:
    monkeypatch.setattr(drv, "_run_manifest", lambda _stage: result)
    assert (drv.manifest_problems(stage) == []) is ok


def test_manifest_problems_report_a_failure_to_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(_stage: str) -> tuple[int, str]:
        raise OSError("no python")

    monkeypatch.setattr(drv, "_run_manifest", broken)
    assert drv.manifest_problems("main") != []


def test_launch_problems_combine_certification_git_manifest_and_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(drv, "certification_problems", lambda _p: ["cert"])
    monkeypatch.setattr(drv, "_git", lambda *_a: "ok")
    monkeypatch.setattr(drv, "manifest_problems", lambda s: [f"manifest {s}"])
    monkeypatch.setattr(drv, "gate_problems", lambda _p: ["gate"])
    assert drv.launch_problems("pilot") == ["cert", "manifest pilot"]
    assert drv.launch_problems("main") == ["cert", "manifest main", "gate"]


def test_launch_problems_check_git_tracking_and_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(drv, "certification_problems", lambda _p: [])
    monkeypatch.setattr(drv, "manifest_problems", lambda _s: [])
    monkeypatch.setattr(drv, "_git", lambda *_a: "")
    assert drv.launch_problems("pilot") == []
    untracked = man.DRIVER

    def git(*args: str) -> str | None:
        if args[0] == "ls-files" and args[-1] == untracked:
            return None
        return ""

    monkeypatch.setattr(drv, "_git", git)
    assert drv.launch_problems("pilot") == [f"not tracked by git: {untracked}"]

    def dirty(*args: str) -> str | None:
        return None if args[0] == "diff" else ""

    monkeypatch.setattr(drv, "_git", dirty)
    assert drv.launch_problems("pilot") == [
        "pinned files differ from HEAD (or git unavailable)"
    ]


def test_certification_problems_use_the_manifest_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cert = tmp_path / "cert.json"
    assert drv.certification_problems(cert) == [
        f"driver certification unreadable: {cert}"
    ]
    cert.write_text('{"all_killed": true}', encoding="utf-8")
    seen: list[object] = []

    def contract(obj: object, root: Path) -> list[str]:
        seen.append((obj, root))
        return ["contract"]

    monkeypatch.setattr(man, "driver_certification_violations", contract)
    assert drv.certification_problems(cert) == ["contract"]
    assert seen == [({"all_killed": True}, _ROOT)]


@pytest.mark.parametrize(
    ("gate", "ok"),
    [
        ({"decision": "GO", "R": 18, "observed": OBSERVED}, True),
        ({"decision": "STOP", "R": 18, "observed": OBSERVED}, False),
        ({"decision": "GO", "R": "18", "observed": OBSERVED}, False),
        ({"decision": "GO", "R": True, "observed": OBSERVED}, False),
        ({"decision": "GO", "R": 18}, False),
        (["GO"], False),
        (None, False),
    ],
)
def test_gate_problems_require_go_r_and_observed(
    tmp_path: Path, gate: object, *, ok: bool
) -> None:
    path = tmp_path / "gate.json"
    if gate is not None:
        path.write_text(json.dumps(gate), encoding="utf-8")
    assert (drv.gate_problems(path) == []) is ok


def test_pinned_covers_the_frozen_files_and_the_driver_evidence() -> None:
    pilot = drv.pinned("pilot")
    assert set(man.FROZEN_FILES) <= set(pilot)
    driver = {
        man.MANIFEST,
        man.DRIVER,
        man.DRIVER_HARNESS,
        man.DRIVER_TEST,
        man.DRIVER_CERT,
    }
    assert driver <= set(pilot)
    assert man.PILOT_RECORDS not in pilot
    main = drv.pinned("main")
    assert set(man.MAIN_EVIDENCE) | {man.MANIFEST_MAIN} <= set(main)
    assert len(set(main)) == len(main)


def test_sha256_reports_an_unreadable_file_as_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """読めないファイルは例外にせず None (開始時と違えば変化に数える)."""
    path = tmp_path / "x.txt"
    path.write_text("x", encoding="utf-8")
    assert drv._sha256(path) == hashlib.sha256(b"x").hexdigest()
    assert drv._sha256(tmp_path / "missing") is None

    def unreadable(_self: Path) -> bytes:
        raise PermissionError("locked")

    monkeypatch.setattr(Path, "read_bytes", unreadable)
    assert drv._sha256(path) is None


def test_pinned_sha256_reads_the_current_files() -> None:
    got = drv.pinned_sha256("pilot")
    assert got[man.PREREG] == man.sha256(_ROOT / man.PREREG)
    assert set(got) == set(drv.pinned("pilot"))


@pytest.mark.parametrize("stage", ["pilot", "main"])
def test_run_manifest_calls_the_frozen_check_like_run_sh(
    monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    """manifest の照合は run.sh と同じ script・環境変数 (PYTHONHASHSEED) で呼ぶ."""
    seen: dict[str, Any] = {}

    def fake(args: list[str], **kw: Any) -> types.SimpleNamespace:
        seen.update(args=args, **kw)
        return types.SimpleNamespace(returncode=0, stdout="x\n")

    monkeypatch.setattr(drv.subprocess, "run", fake)
    assert _REAL_RUN_MANIFEST(stage) == (0, "x\n")
    assert seen["args"] == [sys.executable, man.SELF, "--verify", "--stage", stage]
    assert seen["cwd"] == str(drv._REPO_ROOT)
    seed = (_ROOT / man.EXP / "SEED").read_text(encoding="utf-8").strip()
    assert seen["env"]["PYTHONHASHSEED"] == seed
    assert seen["env"]["PYTHONUTF8"] == "1"


def test_git_reports_a_failure_as_none() -> None:
    """git が失敗したら None (「clean」・「追跡済み」に畳まない).

    test の他の箇所は _git を差し替えるので、実物で pin する。
    """
    assert drv._git("ls-files", "--error-unmatch", "no/such/file.py") is None
    assert (drv._git("--version") or "").startswith("git version")


# ---------------------------------------------------------------- harness の判定器


_PYTEST_OUTPUT = (
    "____ test_a ____",
    "    def test_a():",
    "E   assert 1 == 2",
    "____ ERROR at setup of test_b ____",
    "E   ScheduleError: boom",
    "_ test_c[long-id] _",
    "E   AssertionError: raw is not recorded verbatim",
    "____ ERROR at teardown of test_d ____",
    "E   OSError: teardown boom",
    "FAILED tests/x.py::test_a - assert 1 == 2",
    "ERROR tests/x.py::test_b - ScheduleError: boom",
    "FAILED tests/x.py::test_c[long-id] - AssertionError",
    "ERROR tests/x.py::test_d - OSError: teardown boom",
)


def test_harness_reads_failures_kinds_and_reasons() -> None:
    failed, kinds, collect = harness.parse_output("\n".join(_PYTEST_OUTPUT))
    assert set(failed) == {"test_a", "test_b", "test_c", "test_d"}
    assert kinds == {
        "test_a": "FAILED",
        "test_b": "ERROR",
        "test_c": "FAILED",
        "test_d": "ERROR",
    }
    # teardown の節は、その test の節に集め、直前の test の節に混ぜない
    assert "teardown boom" in failed["test_d"]
    assert "teardown boom" not in failed["test_c"]
    assert "E   ScheduleError: boom" in failed["test_b"]
    assert "raw is not recorded verbatim" in failed["test_c"]
    assert collect is False
    assert harness.parse_output("ERROR collecting tests/x.py")[2] is True


def test_harness_status_separates_wrong_reasons() -> None:
    """判定は 3 通り: SURVIVED / 理由が違う / KILLED.

    理由が違う = WRONG_REASON・COLLECTION_ERROR・TIMEOUT。
    """
    plain = harness.Mutant("x", "o", "n", frozenset({"test_a"}), "why")
    reasoned = harness.Mutant(
        "y", "o", "n", frozenset({"test_b"}), "why", raised="ScheduleError"
    )
    hit_a = {"test_a": "FAILED t::test_a\nE   assert 1 == 2\n"}
    assert harness.status_of(plain, 0, {}, {}, collect=False) == "SURVIVED"
    assert harness.status_of(plain, -1, {}, {}, collect=False) == "TIMEOUT"
    assert harness.status_of(plain, 1, {}, {}, collect=False) == "COLLECTION_ERROR"
    assert (
        harness.status_of(plain, 1, hit_a, {"test_a": "FAILED"}, collect=True)
        == "COLLECTION_ERROR"
    )
    assert (
        harness.status_of(plain, 1, hit_a, {"test_a": "FAILED"}, collect=False)
        == "KILLED"
    )
    # 期待 test が fixture の setup の ERROR だけで落ちた: 理由の文が無ければ数えない
    assert (
        harness.status_of(plain, 1, hit_a, {"test_a": "ERROR"}, collect=False)
        == "WRONG_REASON"
    )
    other = {"test_z": "FAILED t::test_z\nE   assert 0\n"}
    assert (
        harness.status_of(plain, 1, other, {"test_z": "FAILED"}, collect=False)
        == "WRONG_REASON"
    )
    hit_b = {"test_b": "ERROR t::test_b\nE   ScheduleError: boom\n"}
    assert (
        harness.status_of(reasoned, 1, hit_b, {"test_b": "ERROR"}, collect=False)
        == "KILLED"
    )
    # 理由の文がソース行にだけ出て、例外行 (E) には無い
    source_only = {"test_b": "ERROR t::test_b\n    raise ScheduleError\nE   KeyError\n"}
    assert (
        harness.status_of(reasoned, 1, source_only, {"test_b": "ERROR"}, collect=False)
        == "WRONG_REASON"
    )


def test_harness_registry_satisfies_the_manifest_contract() -> None:
    assert man.mutant_want(harness.MUTANTS) is not None
    assert man.meta_want(harness.META_CASES) is not None
    names = {n for n in globals() if n.startswith("test_")}
    expected = {t for m in harness.MUTANTS for t in m.expect}
    expected |= {t for c in harness.META_CASES for t in c[-1]}
    assert expected <= names


# ---------------------------------------------------------------- certification


@pytest.fixture
def committed_cert() -> dict[str, Any]:
    return read_json(_ROOT / man.DRIVER_CERT)


def test_committed_driver_certification_is_current(
    committed_cert: dict[str, Any],
) -> None:
    """commit した driver の certification が manifest の契約を満たす."""
    assert man.driver_certification_violations(committed_cert, _ROOT) == []
