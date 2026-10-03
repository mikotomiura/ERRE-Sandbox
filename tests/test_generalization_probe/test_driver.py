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
import importlib.machinery
import importlib.util
import json
import os
import py_compile
import random
import shutil
import subprocess
import sys
import sysconfig
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
_REAL_INTERPRETER = drv.interpreter_problems


@pytest.fixture(autouse=True)
def _fake_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(drv, "_run_manifest", ok_manifest)
    # test の process は run.sh と同じ設定 (PYTHONHASHSEED・PYTHONUTF8) で
    # 起動しているとは限らない。
    # 実物は _REAL_INTERPRETER で単体の test が使う
    monkeypatch.setattr(drv, "interpreter_problems", lambda *_a, **_k: [])
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


# 入力ごとに item を分ける (変異の証拠が、どの入力で落ちたかを
# 名指せるように、Codex 3 回目 MEDIUM-1)
_VARIANT_NAMES = (
    "model",
    "think",
    "stream",
    "num_ctx_float",
    "temperature",
    "seed_float",
    "seed_other",
    "extra_key",
    "extra_option",
    "missing_option",
    "prompt",
    "messages_extra_field",
    "messages_not_str",
    "messages_not_list",
    "not_a_dict",
)


def test_variant_names_are_the_variants(tmp_path: Path) -> None:
    body = _body(drv.pilot_stage(tmp_path), 0)
    assert [name for name, _ in _variants(body)] == list(_VARIANT_NAMES)


@pytest.mark.parametrize("variant", _VARIANT_NAMES)
@pytest.mark.parametrize("stage_name", ["pilot", "main"])
def test_check_sent_body_rejects_value_and_type(
    tmp_path: Path, stage_name: str, variant: str
) -> None:
    stage = (
        drv.pilot_stage(tmp_path)
        if stage_name == "pilot"
        else drv.main_stage(tmp_path, R_MAIN, OBSERVED)
    )
    for index in (0, 300):
        body = _body(stage, index)
        drv.check_sent_body(stage, index, body)
        bad = dict(_variants(body))[variant]
        with pytest.raises(drv.SentBodyMismatchError):
            drv.check_sent_body(stage, index, bad)


def test_check_uses_the_plan_position(tmp_path: Path) -> None:
    stage = drv.pilot_stage(tmp_path)
    drv.check_sent_body(stage, 200, _body(stage, 200))
    with pytest.raises(drv.SentBodyMismatchError):
        drv.check_sent_body(stage, 201, _body(stage, 200))


async def _post(observer: drv.ObservingTransport, path: str, body: object) -> None:
    async with httpx.AsyncClient(base_url="http://x", transport=observer) as http:
        await http.post(path, json=body)


@pytest.mark.parametrize(
    "case", ["no_expected", "mismatch", "generate_path", "show_path"]
)
def test_observer_refuses_before_the_inner_transport(tmp_path: Path, case: str) -> None:
    """拒否は内側の transport の前 (何も送らない)。拒否の後も、期待した body は通る."""
    stage = drv.pilot_stage(tmp_path)
    ollama = FakeOllama(first_shown)
    observer = drv.ObservingTransport(httpx.MockTransport(ollama), stage)
    good = _body(stage, 3)
    path, body, match = {
        "no_expected": (drv.CHAT_PATH, good, "without an expected call"),
        "mismatch": (drv.CHAT_PATH, dict(_variants(good))["seed_other"], None),
        "generate_path": ("/api/generate", good, "unexpected POST path"),
        "show_path": (drv.SHOW_PATH, {"model": bat.MODEL}, "unexpected POST path"),
    }[case]
    if case != "no_expected":
        observer.expected = 3
    with pytest.raises(drv.SentBodyMismatchError, match=match):
        asyncio.run(_post(observer, path, body))
    assert ollama.bodies == []
    observer.expected = 3
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


def test_interrupted_transport_failure_keeps_not_computed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """raw = null を書いた後、終了時の observed の取得中に中断しても not_computed.

    status は終了理由からでなく、raw = null の行を書いた事実から決める
    (Codex 再 review MEDIUM-2)。
    """

    async def interrupted(*_a: object, **_k: object) -> object:
        raise asyncio.CancelledError

    monkeypatch.setattr(drv, "final_observed", interrupted)
    run_dir = tmp_path / "run"
    with pytest.raises(asyncio.CancelledError):
        do_run(short_stage(run_dir), failing(2, 99, connect_error))
    assert_not_published(run_dir)
    assert records(run_dir / drv.PARTIAL_NAME)[-1].raw is None
    prov = provenance(run_dir)
    assert prov["exit_reason"] == drv.REASON_ABORTED
    assert prov["status"] == sc.STATUS_NOT_COMPUTED, "not_computed was lost"


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
    # error が None でも assert で落ちるように (変異の判定は assert の行を見る、BL-3)
    assert drv.PENDING_NOTE in (seen["error"] or ""), "the pending note is missing"
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
            raise OSError(
                "readonly (second phase)"
            )  # 二相目 (公開済みへの書き直し) だけ
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
    # test の通常 import は検証した起動ではない (実行したコードの照合は別の test)
    monkeypatch.setattr(drv, "executed_problems", lambda *_a, **_k: [])
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
        # 最後の行は LF だけで切る。LF 以外の区切り文字は行の中身に残る
        # (Codex 再 review LOW-1)。CRLF は subprocess の text mode が LF に直すので、
        # 届いた CR は行の中身
        ("pilot", (0, "MANIFEST OK (stage pilot)" + chr(0x1C)), False),
        ("pilot", (0, "MANIFEST OK (stage pilot)" + chr(0x85) + "\n"), False),
        ("pilot", (0, "MANIFEST OK (stage pilot)" + chr(0x2028)), False),
        ("pilot", (0, "MANIFEST OK (stage pilot)" + chr(13) + "\n"), False),
        ("pilot", (0, "a\nMANIFEST OK (stage pilot)"), True),
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
    monkeypatch.setattr(drv, "interpreter_problems", lambda: ["interpreter"])
    monkeypatch.setattr(drv, "manifest_problems", lambda s: [f"manifest {s}"])
    monkeypatch.setattr(drv, "gate_problems", lambda _p: ["gate"])
    assert drv.launch_problems("pilot") == ["cert", "interpreter", "manifest pilot"]
    assert drv.launch_problems("main") == [
        "cert",
        "interpreter",
        "manifest main",
        "gate",
    ]


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
    """manifest の照合は、run.sh と同じ封印済みの main・引数を、この process の中で呼ぶ.

    子プロセスを起動しない (Codex 4 回目 HIGH-1)。出力と exit code を返す。run.sh と同じ
    hash seed・UTF-8 mode は interpreter_problems が起動の前提にする。
    """
    calls: list[object] = []

    def frozen_main(argv: list[str]) -> int:
        calls.append(argv)
        sys.stdout.write(f"x\nMANIFEST OK (stage {stage})\n")
        return 0

    def child(*args: object, **_kw: object) -> types.SimpleNamespace:
        calls.append(("subprocess", args))
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(drv.man, "main", frozen_main)
    monkeypatch.setattr(drv.subprocess, "run", child)
    assert _REAL_RUN_MANIFEST(stage) == (0, f"x\nMANIFEST OK (stage {stage})\n")
    assert calls == [["--verify", "--stage", stage]], (
        "not called once, in this process, with the stage's arguments"
    )


def test_run_manifest_folds_an_exception_into_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """照合の例外は exit 1 と、その型と文の行に畳む.

    起動・公開のどちらでも拒否になる。
    """

    def broken(_argv: list[str]) -> int:
        sys.stdout.write("partial\n")
        msg = "the frozen check exploded"
        raise RuntimeError(msg)

    monkeypatch.setattr(drv.man, "main", broken)
    assert _REAL_RUN_MANIFEST("pilot") == (
        1,
        "partial\nmanifest check raised: RuntimeError: the frozen check exploded\n",
    )

    def exits(_argv: list[str]) -> int:
        raise SystemExit(2)

    # SystemExit も畳む (公開の時点で来歴を書く経路を抜けない、code-reviewer LOW-5)
    monkeypatch.setattr(drv.man, "main", exits)
    assert _REAL_RUN_MANIFEST("pilot") == (1, "manifest check raised: SystemExit: 2\n")
    monkeypatch.setattr(drv.man, "main", broken)
    monkeypatch.setattr(drv, "_run_manifest", _REAL_RUN_MANIFEST)
    assert drv.manifest_problems("pilot") == [
        "manifest --verify --stage pilot did not end with MANIFEST OK (stage pilot)"
    ]


def test_interpreter_problems_require_the_run_sh_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """起動の前提: run.sh と同じ PYTHONHASHSEED (= SEED)・UTF-8 mode・-E/-I でない.

    decisions DF-5・code-reviewer MEDIUM-3。
    """
    seed = tmp_path / "SEED"
    seed.write_text("20261001\n", encoding="utf-8")
    ok = {"PYTHONHASHSEED": "20261001"}
    good = types.SimpleNamespace(utf8_mode=1, ignore_environment=0)
    assert _REAL_INTERPRETER(seed, ok, good) == []
    wrong_seed = "not launched like run.sh: PYTHONHASHSEED must be the SEED (20261001)"
    assert _REAL_INTERPRETER(seed, {}, good) == [wrong_seed]
    assert _REAL_INTERPRETER(seed, {"PYTHONHASHSEED": "20261002"}, good) == [wrong_seed]
    no_utf8 = types.SimpleNamespace(utf8_mode=0, ignore_environment=0)
    assert _REAL_INTERPRETER(seed, ok, no_utf8) == [
        "not launched like run.sh: PYTHONUTF8 must be 1"
    ]
    # -E/-I の起動では Python が PYTHONHASHSEED を読まない (os.environ には残る)
    isolated = types.SimpleNamespace(utf8_mode=1, ignore_environment=1)
    assert _REAL_INTERPRETER(seed, ok, isolated) == [
        "not launched like run.sh: -E/-I ignores PYTHONHASHSEED and PYTHONPATH"
    ]
    missing = _REAL_INTERPRETER(tmp_path / "no_seed", ok, good)
    assert len(missing) == 1, missing
    assert missing[0].startswith("SEED unreadable: "), missing
    # 既定は SEED_PATH・os.environ・sys.flags
    real = (_ROOT / man.EXP / "SEED").read_text(encoding="utf-8").strip()
    monkeypatch.setenv("PYTHONHASHSEED", real)
    utf8 = (
        []
        if sys.flags.utf8_mode == 1
        else ["not launched like run.sh: PYTHONUTF8 must be 1"]
    )
    assert _REAL_INTERPRETER() == utf8


def test_git_reports_a_failure_as_none() -> None:
    """git が失敗したら None (「clean」・「追跡済み」に畳まない).

    test の他の箇所は _git を差し替えるので、実物で pin する。
    """
    assert drv._git("ls-files", "--error-unmatch", "no/such/file.py") is None
    assert (drv._git("--version") or "").startswith("git version")


# ------------------------------ 実行したコードの同定 (Codex 再 review HIGH-1)

_SAMPLE = b"X = 1\n\n\ndef f() -> int:\n    return 41\n"


def test_compiles_to_compares_the_program() -> None:
    """code object の等値: 定数・入れ子の関数まで比べ、ファイル名は比べない.

    bytes の一致ではない。
    """
    code = compile(_SAMPLE, "a.py", "exec", dont_inherit=True)
    assert drv._compiles_to(code, _SAMPLE, Path("b.py"))
    assert not drv._compiles_to(code, _SAMPLE.replace(b"41", b"42"), Path("a.py"))
    assert not drv._compiles_to(code, _SAMPLE.replace(b"X = 1", b"X = 2"), Path("a.py"))
    assert not drv._compiles_to(code, b"def (:\n", Path("a.py"))
    # 末尾のコメントだけの差は同じプログラム (主張は「コンパイル結果が同じ」、DU-3)
    assert drv._compiles_to(code, _SAMPLE + b"# note\n", Path("a.py"))


def test_imported_driver_runs_its_bytes() -> None:
    """import した driver は、起動時に読んだ bytes のコンパイル結果.

    来歴の sha256 は、その bytes の sha256。
    """
    assert drv._DRIVER_RUNS_ITS_BYTES is True
    assert (
        hashlib.sha256(Path(drv.__file__).read_bytes()).hexdigest() == drv._DRIVER_SHA
    )


def test_pinned_finder_runs_the_bytes_it_read(tmp_path: Path) -> None:
    """find_spec で 1 回だけ読んだ bytes を実行する.

    後でファイルが替わっても読み直さず、pyc も書かない。
    """
    package = "gp_driver_pinned_pkg"
    (tmp_path / package).mkdir()
    path = tmp_path / package / "mod_a.py"
    first, second = b'VALUE = "A"\n', b'VALUE = "B"\n'
    path.write_bytes(first)
    finder = drv._PinnedFinder(tmp_path, package)
    spec = finder.find_spec(f"{package}.mod_a")
    assert spec is not None
    assert isinstance(spec.loader, drv._PinnedLoader)
    path.write_bytes(second)  # 読んだ後・実行の前の差し替え
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.VALUE == "A", "the loader read the file again"
    assert spec.loader.pinned_sha256 == hashlib.sha256(first).hexdigest()
    assert module.__file__ == str(path)
    assert not (tmp_path / package / "__pycache__").exists()
    # sha256 は渡された bytes から取る (ディスクを読み直さない)
    loader = drv._PinnedLoader(path, first)
    assert loader.pinned_sha256 == hashlib.sha256(first).hexdigest(), "hashed the disk"
    # 対象は <package>.<name> のファイルだけ
    assert finder.find_spec("other_pkg.mod_a") is None
    assert finder.find_spec(f"{package}.missing") is None
    assert finder.find_spec(f"{package}.sub.mod_a") is None


def test_pinned_finder_makes_the_package_a_namespace(tmp_path: Path) -> None:
    """package 自体は root/<package> だけを探す名前空間.

    ``__init__.py`` を実行しない (Codex 3 回目 MEDIUM-2)。
    """
    package = "gp_driver_namespace_pkg"
    (tmp_path / package).mkdir()
    (tmp_path / package / "__init__.py").write_text(
        "RAN = True\nraise RuntimeError('the package initializer ran')\n",
        encoding="utf-8",
    )
    spec = drv._PinnedFinder(tmp_path, package).find_spec(package)
    assert spec is not None
    assert spec.origin is None
    assert spec.loader is None
    assert list(spec.submodule_search_locations or ()) == [str(tmp_path / package)]
    # module_from_spec が名前空間の loader (CPython の NamespaceLoader) を
    # spec に入れる。
    # その exec_module は何もしない (__init__.py を読まない)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert not hasattr(module, "RAN"), "the package initializer ran"
    assert module.__file__ is None
    assert list(module.__path__) == [str(tmp_path / package)]


def _module(loader: object) -> types.ModuleType:
    module = types.ModuleType("fake")
    module.__spec__ = importlib.machinery.ModuleSpec("fake", loader)  # type: ignore[arg-type]
    return module


_BATTERY = "scripts/generalization_probe_battery.py"


def _customize(directory: Path, name: str) -> Path:
    """``directory`` に site の customization の module を置く (返り値 = その file)."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.py"
    path.write_text("RAN = True\n", encoding="utf-8")
    return path


def test_executed_problems_check_driver_modules_and_pins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """実行中のコードの照合.

    driver の検証・driver の固定値・モジュールの loader・固定ファイル・bytes。
    """
    start = {man.DRIVER: drv._DRIVER_SHA, _BATTERY: hashlib.sha256(b"A").hexdigest()}
    # 手元のレジストリに依らない (既定の接続は下で確かめる)
    monkeypatch.setattr(drv, "_registry_paths", lambda _paths: [])

    def problems(
        modules: dict[str, object], pinned: dict[str, str] | None = None
    ) -> list[str]:
        return drv.executed_problems(
            drv.STAGE_PILOT, pinned or start, modules, paths=[], environ={}
        )

    pinned_a = _module(drv._PinnedLoader(Path(_BATTERY), b"A"))
    assert (
        problems(
            {"scripts.generalization_probe_battery": pinned_a, "json": _module(None)}
        )
        == []
    )
    assert problems({"scripts.generalization_probe_battery": _module(object())}) == [
        "not run from the bytes it was hashed by: scripts.generalization_probe_battery"
    ]
    assert problems(
        {"scripts.not_pinned": _module(drv._PinnedLoader(Path("x"), b"A"))}
    ) == ["run but not pinned: scripts/not_pinned.py"]
    pinned_b = _module(drv._PinnedLoader(Path(_BATTERY), b"B"))
    assert problems({"scripts.generalization_probe_battery": pinned_b}) == [
        f"run bytes differ from the pinned file at start-up: {_BATTERY}"
    ]
    assert problems({}, {**start, man.DRIVER: "0" * 64}) == [
        "the driver on disk changed between start-up and the launch checks"
    ]
    # その他のモジュールは環境の中 (走査、Codex 3 回目 MEDIUM-2)
    shadow = types.ModuleType("numpy")
    shadow.__file__ = str(_ROOT / "scripts" / "numpy.py")
    assert drv.executed_problems(
        drv.STAGE_PILOT, start, {"numpy": shadow}, (), paths=[], environ={}
    ) == [
        f"run outside the pinned files and the environment: numpy ({shadow.__file__})"
    ]
    # 起動時に site が実行しうる customization も (Codex 4 回目 HIGH-2)
    site = _customize(tmp_path / "site", "sitecustomize")
    assert drv.executed_problems(
        drv.STAGE_PILOT, start, {}, (), paths=[str(tmp_path / "site")], environ={}
    ) == [f"startup code outside the environment: sitecustomize ({site})"]
    # PYTHONPATH も (code-reviewer HIGH-2)
    pythonpath = str(tmp_path / "pp")
    assert drv.executed_problems(
        drv.STAGE_PILOT, start, {}, (), paths=[], environ={"PYTHONPATH": pythonpath}
    ) == [f"startup code outside the environment: PYTHONPATH ({pythonpath})"]
    # 既定の接続: getpath がレジストリから足した entry (sys.path を渡す、
    # Codex 5 回目 HIGH-1) と、site の user site (Codex 5 回目 LOW-2)
    seen: list[object] = []
    reg_entry = str(tmp_path / "reg")

    def registry(paths: object) -> list[str]:
        seen.append(paths)
        return [reg_entry]

    monkeypatch.setattr(drv, "_registry_paths", registry)
    search = [str(tmp_path / "search")]
    assert drv.executed_problems(
        drv.STAGE_PILOT, start, {}, (), paths=search, environ={}
    ) == [f"startup code outside the environment: registry ({reg_entry})"]
    assert seen == [search]
    # 渡した entry はそのまま使い、レジストリを読まない
    other = str(tmp_path / "other")
    assert drv.executed_problems(
        drv.STAGE_PILOT, start, {}, (), paths=search, environ={}, registry=[other]
    ) == [f"startup code outside the environment: registry ({other})"]
    assert seen == [search]
    # -E/-I の起動では getpath がレジストリ・PYTHONPATH を読まないので見ない
    # (起動の前提が別に拒否する)
    flags = {name: getattr(sys.flags, name) for name in sys.flags.__match_args__}
    with monkeypatch.context() as mp:
        mp.setattr(
            sys, "flags", types.SimpleNamespace(**{**flags, "ignore_environment": 1})
        )
        isolated = drv.executed_problems(
            drv.STAGE_PILOT, start, {}, (), paths=search, environ={"PYTHONPATH": other}
        )
    assert isolated == []
    assert seen == [search]
    monkeypatch.setattr(drv, "_registry_paths", lambda _paths: [])
    user_dir = tmp_path / "user_site"
    user_dir.mkdir()
    user_pth = user_dir / "a.pth"
    user_pth.write_text("import os\n", encoding="utf-8")
    fake_site = types.SimpleNamespace(
        ENABLE_USER_SITE=True, getusersitepackages=lambda: str(user_dir)
    )
    with monkeypatch.context() as mp:
        mp.setitem(sys.modules, "site", fake_site)
        assert drv.executed_problems(
            drv.STAGE_PILOT, start, {}, (), paths=[], environ={}
        ) == [f"startup code outside the environment: {user_pth}"]
    monkeypatch.setattr(drv, "_DRIVER_RUNS_ITS_BYTES", False)
    assert problems({}) == [
        "the running driver is not the compilation of the driver bytes it hashed"
    ]


# ------------------------------ 環境と固定ファイルの外のコード (Codex 3 回目 MEDIUM-2)


def test_environment_roots_are_the_prefixes_that_do_not_hold_the_repo() -> None:
    roots = drv._environment_roots()
    assert drv._norm(sys.prefix) in roots
    assert drv._norm(sys.base_prefix) in roots
    assert not drv._in_environment(str(_ROOT / "scripts" / "x.py"), roots)
    # repo を含む prefix は環境に数えない (venv を repo root そのものに作った場合など)
    inside_base = os.path.join(sys.base_prefix, "Lib", "repo")  # noqa: PTH118
    held = drv._environment_roots(inside_base)
    assert drv._norm(sys.base_prefix) not in held
    if drv._norm(sys.prefix) != drv._norm(sys.base_prefix):
        assert drv._norm(sys.prefix) in held


def test_environment_roots_count_all_four_prefixes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """4 つの prefix (exec・base を含む) を全て環境に数える.

    Codex 4 回目 LOW-2。
    """
    names = ("prefix", "exec_prefix", "base_prefix", "base_exec_prefix")
    for name in names:
        (tmp_path / name).mkdir()
        monkeypatch.setattr(sys, name, str(tmp_path / name))
    roots = drv._environment_roots(str(tmp_path / "repo"))
    assert sorted(roots) == sorted(drv._norm(str(tmp_path / n)) for n in names)


def _dir_link(link: Path, target: Path) -> None:
    """dir への link (POSIX は symlink、Windows は権限の要らない junction)."""
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


def test_in_environment_resolves_links(tmp_path: Path) -> None:
    """所在は link を解決してから比べる (Codex 4 回目 LOW-2).

    環境の中の link の先が外なら外、外の link の先が環境の中なら中。
    """
    env, out = tmp_path / "env", tmp_path / "out"
    for d in (env, out):
        d.mkdir()
        (d / "m.py").write_text("", encoding="utf-8")
    roots = (drv._norm(str(env)),)
    _dir_link(env / "to_out", out)
    _dir_link(tmp_path / "to_env", env)
    assert not drv._in_environment(str(env / "to_out" / "m.py"), roots)
    assert drv._in_environment(str(tmp_path / "to_env" / "m.py"), roots)


def test_startup_problems_find_customization_outside_the_environment(
    tmp_path: Path,
) -> None:
    """site が起動時に実行しうる customization の所在 (Codex 4 回目 HIGH-2).

    import に失敗したものは sys.modules に残らないので、所在で見る。
    """
    env = tmp_path / "env"
    roots = (drv._norm(str(env)),)
    phrase = "startup code outside the environment"
    _customize(env / "lib", "sitecustomize")
    assert drv.startup_problems([str(env / "lib")], roots, None) == []
    # PYTHONPATH の entry は名前に依らず見る (site の .pth の import 行が同名の
    # module を読みうる、code-reviewer HIGH-2)。空の entry は cwd
    inside_pp = str(env / "pp")
    assert drv.startup_problems([], roots, None, inside_pp) == []
    outside_pp = str(tmp_path / "pp")
    assert drv.startup_problems(
        [], roots, None, os.pathsep.join([inside_pp, outside_pp])
    ) == [f"{phrase}: PYTHONPATH ({outside_pp})"]
    assert drv.startup_problems([], roots, None, os.pathsep.join([inside_pp, ""])) == [
        f"{phrase}: PYTHONPATH (.)"
    ]
    assert drv.startup_problems([], roots, None, "") == []
    # getpath がレジストリから足した entry も、名前に依らず見る
    # (Codex 5 回目 HIGH-1)。空は cwd
    assert drv.startup_problems([], roots, None, None, [inside_pp]) == []
    assert drv.startup_problems([], roots, None, None, [inside_pp, outside_pp]) == [
        f"{phrase}: registry ({outside_pp})"
    ]
    assert drv.startup_problems([], roots, None, None, [""]) == [
        f"{phrase}: registry (.)"
    ]
    outside = _customize(tmp_path / "out", "sitecustomize")
    # 環境の中のものが前にあって、外のものが実行されなかったとしても拒否する (安全側)。
    # 文字列でない entry は飛ばす
    assert drv.startup_problems(
        [str(env / "lib"), 5, str(tmp_path / "out")], roots, None
    ) == [f"{phrase}: sitecustomize ({outside})"]
    user = _customize(tmp_path / "user", "usercustomize")
    assert drv.startup_problems([str(tmp_path / "user")], roots, None) == [
        f"{phrase}: usercustomize ({user})"
    ]
    # user site が有効なら、その .pth も (環境の外のとき)
    site_dir = tmp_path / "user_site"
    site_dir.mkdir()
    pth = site_dir / "a.pth"
    pth.write_text("import os\n", encoding="utf-8")
    assert drv.startup_problems([], roots, str(site_dir)) == [f"{phrase}: {pth}"]
    assert drv.startup_problems([], roots, None) == []
    assert drv.startup_problems([], (drv._norm(str(tmp_path)),), str(site_dir)) == []


def test_user_site_reads_the_site_module(tmp_path: Path) -> None:
    """user site は、site が有効にしたときだけ数える (code-reviewer LOW-7).

    site を import せず、渡された (既定は sys.modules の) site module から読む。
    """
    enabled = types.SimpleNamespace(
        ENABLE_USER_SITE=True, getusersitepackages=lambda: str(tmp_path)
    )
    disabled = types.SimpleNamespace(
        ENABLE_USER_SITE=False, getusersitepackages=lambda: str(tmp_path)
    )
    assert drv._user_site(enabled) == str(tmp_path)
    assert drv._user_site(disabled) is None
    assert drv._user_site(types.SimpleNamespace(ENABLE_USER_SITE=None)) is None


# getpath が読む key (CPython 3.11 の Modules/getpath.py の WINREG_KEY =
# f'SOFTWARE\\Python\\PythonCore\\{PYWINVER}\\PythonPath'、PYWINVER = sys.winver)。
# driver の定数から作らず、原文から独立に組む (code-reviewer MEDIUM)
_GETPATH_KEY = chr(92).join(
    ["SOFTWARE", "Python", "PythonCore", getattr(sys, "winver", ""), "PythonPath"]
)


class _FakeRegistry:
    """getpath が読む winreg の API (OpenKeyEx・EnumKey・QueryValue・CloseKey) の偽物.

    ``keys`` = {hive: (キー自身の既定値, [子キーの既定値 (OSError なら読めない)])}。
    getpath の key (``_GETPATH_KEY``) だけを開ける。
    """

    HKEY_CURRENT_USER = "HKCU"
    HKEY_LOCAL_MACHINE = "HKLM"

    def __init__(self, keys: dict[str, tuple[str, list[str | OSError]]]) -> None:
        self.keys = keys
        self.opened: list[tuple[str, str]] = []
        self.closed: list[str] = []

    def OpenKeyEx(self, hive: str, name: str) -> str:  # noqa: N802 — winreg の名前
        self.opened.append((hive, name))
        if hive not in self.keys or name != _GETPATH_KEY:
            raise FileNotFoundError(name)
        return hive

    def EnumKey(self, key: str, i: int) -> str:  # noqa: N802
        if i >= len(self.keys[key][1]):
            raise OSError("no more")
        return str(i)

    def QueryValue(self, key: str, sub: str | None) -> str:  # noqa: N802
        if sub is None:
            return self.keys[key][0]
        value = self.keys[key][1][int(sub)]
        if isinstance(value, OSError):
            raise value
        return value

    def CloseKey(self, key: str) -> None:  # noqa: N802
        self.closed.append(key)


def test_registry_paths_follow_getpath(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """getpath がレジストリから検索パスに足す entry (Codex 5 回目 HIGH-1).

    decisions DG-4。子キーの既定値は常に (HKCU・HKLM とも、読めない子キーの後も
    読む)。キー自身の既定値は、stdlib が見つからないときだけ足されるので、空でない
    entry が sys.path にあるときだけ。既定は Windows の winreg。
    """
    a, b, c, own_on, own_off = (str(tmp_path / n) for n in ("a", "b", "c", "on", "off"))
    sep = ";"  # getpath の DELIM (Windows)。os.pathsep ではない
    reg = _FakeRegistry(
        {
            "HKCU": (
                f"{own_off}{sep}{own_on}{sep}",
                [OSError("denied"), f"{a}{sep}{b}"],
            ),
            "HKLM": ("", [c]),
        }
    )
    assert drv._registry_paths([own_on, ""], reg) == [a, b, own_on, c]
    assert reg.closed == ["HKCU", "HKLM"]
    assert reg.opened == [("HKCU", _GETPATH_KEY), ("HKLM", _GETPATH_KEY)]
    # key が無い hive は飛ばす。キー自身の既定値は sys.path に無ければ数えない
    only_lm = _FakeRegistry({"HKLM": (own_off, [])})
    assert drv._registry_paths([own_on], only_lm) == []
    assert drv._registry_paths([], _FakeRegistry({})) == []
    # 既定 (reg を渡さない) は、Windows なら winreg を読む (Windows 以外は読まない)。
    # sys.platform の差し替えは呼び出しの間だけ
    monkeypatch.setitem(sys.modules, "winreg", _FakeRegistry({"HKLM": ("", [a])}))
    with monkeypatch.context() as mp:
        mp.setattr(sys, "platform", "win32")
        on_windows = drv._registry_paths([])
    with monkeypatch.context() as mp:
        mp.setattr(sys, "platform", "linux")
        elsewhere = drv._registry_paths([])
    assert (on_windows, elsewhere) == ([a], [])


def test_in_environment_compares_whole_path_components(tmp_path: Path) -> None:
    env = tmp_path / "env"
    (env / "lib").mkdir(parents=True)
    roots = (drv._norm(str(env)),)
    assert drv._in_environment(str(env / "lib" / "m.py"), roots)
    assert drv._in_environment(str(env), roots)
    assert not drv._in_environment(str(tmp_path / "env2" / "m.py"), roots)
    assert not drv._in_environment(str(tmp_path / "m.py"), roots)
    # 比べられない組 (別ドライブ・相対と絶対) は外
    assert not drv._under("relative", roots[0])


def _file_spec(name: str, path: Path) -> importlib.machinery.ModuleSpec:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    return spec


class _Finder:
    def __init__(self, specs: dict[str, object]) -> None:
        self.specs = specs
        self.asked: list[str] = []

    def find_spec(
        self, name: str, _path: object = None, _target: object = None
    ) -> object:
        self.asked.append(name)
        return self.specs.get(name)


def _gate_finders(tmp_path: Path) -> tuple[tuple[str, ...], dict[str, object]]:
    env, repo = tmp_path / "env", tmp_path / "repo"
    namespace = importlib.machinery.ModuleSpec("ns", None, is_package=True)
    namespace.submodule_search_locations = [str(repo / "ns")]
    # portion が環境の中と外にある名前空間
    # (先頭だけ見ると通ってしまう、Codex 4 回目 LOW-2)
    mixed = importlib.machinery.ModuleSpec("ns_mixed", None, is_package=True)
    mixed.submodule_search_locations = [str(env / "ns_mixed"), str(repo / "ns_mixed")]
    specs: dict[str, object] = {
        "inside": _file_spec("inside", env / "inside.py"),
        "builtin_like": importlib.machinery.ModuleSpec(
            "builtin_like", None, origin="built-in"
        ),
        "numpy": _file_spec("numpy", repo / "scripts" / "numpy.py"),
        "ns": namespace,
        "ns_mixed": mixed,
        "scripts.extra": _file_spec("scripts.extra", repo / "scripts" / "extra.py"),
    }
    return (drv._norm(str(env)),), specs


def test_launch_gate_passes_the_environment(tmp_path: Path) -> None:
    roots, specs = _gate_finders(tmp_path)
    first, second = (
        _Finder({"later": None}),
        _Finder({**specs, "later": specs["inside"]}),
    )
    gate = drv._LaunchGate(roots, [first, second])
    assert gate.find_spec("inside") is specs["inside"]
    assert gate.find_spec("builtin_like") is specs["builtin_like"]  # 所在の無い spec
    assert gate.find_spec("later") is specs["inside"]  # 前の finder が None なら次へ
    assert gate.find_spec("missing") is None
    # 門は自分自身に尋ねない (sys.meta_path に自分が居ても再帰しない)
    selfish = drv._LaunchGate(roots, [])
    selfish.finders = [selfish, second]
    assert selfish.find_spec("inside") is specs["inside"]


@pytest.mark.parametrize("name", ["numpy", "ns", "ns_mixed", "scripts.extra"])
def test_launch_gate_refuses_code_outside_the_environment(
    tmp_path: Path, name: str
) -> None:
    """所在が環境の外なら ImportError (Codex 3 回目 MEDIUM-2).

    所在 = file の origin・package の探索場所。
    """
    roots, specs = _gate_finders(tmp_path)
    gate = drv._LaunchGate(roots, [_Finder(specs)])
    with pytest.raises(
        ImportError, match="outside the pinned files and the environment"
    ):
        gate.find_spec(name)


def _namespace(path: list[str], file: str | None = None) -> types.ModuleType:
    module = types.ModuleType("scripts")
    module.__path__ = path
    module.__file__ = file
    return module


def test_outside_problems_require_the_environment_and_the_scripts_namespace(
    tmp_path: Path,
) -> None:
    env = tmp_path / "env"
    roots = (drv._norm(str(env)),)
    scripts_dir = str(_ROOT / "scripts")
    in_env = types.ModuleType("in_env")
    in_env.__file__ = str(env / "in_env.py")
    no_location = types.ModuleType("no_location")
    good = {
        "__main__": types.ModuleType(
            "__main__"
        ),  # driver 自身 (code object で照合済み)
        "scripts": _namespace([scripts_dir]),
        "scripts.anything": types.ModuleType(
            "scripts.anything"
        ),  # 固定ファイルの照合が見る
        "in_env": in_env,
        "no_location": no_location,
    }
    assert drv.outside_problems(good, roots) == []
    shadow = types.ModuleType("numpy")
    shadow.__file__ = str(tmp_path / "scripts" / "numpy.py")
    by_spec = types.ModuleType("by_spec")
    by_spec.__spec__ = _file_spec("by_spec", tmp_path / "by_spec.py")
    outside = "run outside the pinned files and the environment"
    assert drv.outside_problems({**good, "numpy": shadow}, roots) == [
        f"{outside}: numpy ({shadow.__file__})"
    ]
    assert drv.outside_problems({**good, "by_spec": by_spec}, roots) == [
        f"{outside}: by_spec ({tmp_path / 'by_spec.py'})"
    ]
    by_path = types.ModuleType("by_path")  # spec も file も無い package (探索場所だけ)
    by_path.__path__ = [str(tmp_path / "by_path")]
    assert drv.outside_problems({**good, "by_path": by_path}, roots) == [
        f"{outside}: by_path ({tmp_path / 'by_path'})"
    ]
    # 探索場所が環境の中と外にある package は、全ての所在を見る (Codex 4 回目 LOW-2)
    mixed = types.ModuleType("mixed")
    mixed.__path__ = [str(env / "mixed"), str(tmp_path / "mixed")]
    assert drv.outside_problems({**good, "mixed": mixed}, roots) == [
        f"{outside}: mixed ({tmp_path / 'mixed'})"
    ]
    initialized = _namespace([scripts_dir], file=str(_ROOT / "scripts" / "__init__.py"))
    elsewhere = _namespace([scripts_dir, str(tmp_path)])
    for module in (initialized, elsewhere):
        assert drv.outside_problems({**good, "scripts": module}, roots) == [
            "scripts is not the namespace of the pinned files"
        ]


def test_main_checks_the_executed_code_after_the_launch_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """main は起動の検査の **後** に実行中のコードを照合し、問題があれば起動しない.

    後に置くのは、certification の検査が import する harness も含めるため。
    """
    order: list[str] = []
    start = {"pinned": "at start"}
    seen: list[object] = []

    def launch(_stage: str) -> list[str]:
        order.append("launch")
        return []

    def executed(stage: str, pinned: object, *_a: object) -> list[str]:
        order.append("executed")
        seen.append((stage, pinned))
        return ["code differs"]

    called: list[object] = []

    def no_run(*a: object, **_k: object) -> str:
        called.append(a)
        raise RuntimeError

    monkeypatch.setattr(drv, "pinned_sha256", lambda _s: start)
    monkeypatch.setattr(drv, "launch_problems", launch)
    monkeypatch.setattr(drv, "executed_problems", executed)
    monkeypatch.setattr(drv.httpx, "AsyncHTTPTransport", lambda: "transport")
    monkeypatch.setattr(drv, "run", no_run)
    monkeypatch.setattr(drv, "PILOT_DIR", tmp_path / "pilot")
    assert drv.main(["--stage", "pilot"]) == drv.EXIT_CODES[drv.REASON_ABORTED]
    assert order == ["launch", "executed"], (
        "checked the executed code before the launch checks"
    )
    assert seen == [("pilot", start)]
    assert called == []
    assert "[driver] refuse to launch: code differs" in capsys.readouterr().out


# 起動の通し: 起動の閉包を tmp に写し、endpoint を到達しない port に、transport を
# 接続しない MockTransport に置き換えて (独立の 2 重、Codex 3 回目 BL-1)、__main__ で
# 起動させる。certification・SEED が無く git の外なので、3 重に起動を拒否される
# (拒否を外す変異でも実の Ollama に届かない)
_UNREACHABLE = "http://127.0.0.1:9"
_EXECUTED_PHRASES = (
    "not the compilation of the driver bytes",
    "changed between start-up and the launch checks",
    "not run from the bytes it was hashed by",
    "run but not pinned",
    "run bytes differ from the pinned file",
    "outside the pinned files and the environment",
    "scripts is not the namespace of the pinned files",
    "startup code outside the environment",
)
_MARK = "UNPINNED CODE RAN"
_RUN_AS_MAIN = (
    "import importlib, pathlib, sys\n"
    "a, b, pre = sys.argv[1], sys.argv[2], sys.argv[3:]\n"
    "sys.path.insert(0, str(pathlib.Path(b).resolve().parent.parent))\n"
    "for name in pre:\n"
    "    importlib.import_module(name)\n"
    "sys.argv = [b, '--stage', 'pilot']\n"
    "g = {'__name__': '__main__', '__file__': b}\n"
    "exec(compile(pathlib.Path(a).read_bytes(), b, 'exec'), g)\n"
)


def _replace_once(path: Path, old: str, new: str) -> None:
    """bytes のまま 1 回だけ置換する (Codex 3 回目 BL-1).

    改行などの他の bytes を変えない。
    """
    data, before, after = path.read_bytes(), old.encode("utf-8"), new.encode("utf-8")
    assert data.count(before) == 1, f"anchor not unique: {old}"
    path.write_bytes(data.replace(before, after))


def _launch_copy(root: Path) -> Path:
    """起動の閉包 (scripts の G のファイルと stage_b_scorer) を root/scripts に写す.

    返り値 = 写した driver。
    """
    src = Path(drv.__file__).resolve().parent
    (root / "scripts").mkdir()
    for pattern in ("generalization_probe_*.py", "stage_b_scorer.py"):
        for f in src.glob(pattern):
            shutil.copy2(f, root / "scripts" / f.name)
    driver = root / "scripts" / Path(drv.__file__).name
    _replace_once(
        driver,
        f'DEFAULT_ENDPOINT: Final[str] = "{drv.DEFAULT_ENDPOINT}"',
        f'DEFAULT_ENDPOINT: Final[str] = "{_UNREACHABLE}"',
    )
    _replace_once(
        driver,
        "httpx.AsyncHTTPTransport()",
        "httpx.MockTransport(lambda request: httpx.Response(599))",
    )
    return driver


def _run_copy(
    root: Path, *args: str, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = dict(
        os.environ,
        PYTHONUTF8="1",
        PYTHONDONTWRITEBYTECODE="1",
        GIT_DIR=str(root / "no-git"),
        **(extra_env or {}),
    )
    return subprocess.run(  # noqa: S603
        [sys.executable, *args],
        cwd=str(root),
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )


def test_command_line_launch_runs_repo_code_from_hashed_bytes(tmp_path: Path) -> None:
    """__main__ で起動すると、repo のモジュールは finder が読んだ bytes から実行される.

    実行中のコードの照合に問題が出ない。
    """
    driver = _launch_copy(tmp_path)
    proc = _run_copy(tmp_path, str(driver), "--stage", "pilot")
    out = proc.stdout + proc.stderr
    assert proc.returncode == drv.EXIT_CODES[drv.REASON_ABORTED], out
    assert "[driver] refuse to launch: driver certification unreadable" in out
    for phrase in _EXECUTED_PHRASES:
        assert phrase not in out, out
    assert not (tmp_path / man.EXP).exists()


def test_command_line_launch_refuses_code_that_is_not_its_bytes(tmp_path: Path) -> None:
    """起動の窓の差し替えの再現.

    A のコードを __file__ = B で実行し、repo のモジュールを先に通常 import する。
    driver は「自分の bytes のコンパイル結果でない」で、先に読まれたモジュールは
    「hash した bytes から実行していない」で拒否する。
    """
    driver = _launch_copy(tmp_path)
    running = tmp_path / "running_driver.py"
    running.write_bytes(driver.read_bytes())
    _replace_once(
        driver, "TIMEOUT_S: Final[float] = 300.0", "TIMEOUT_S: Final[float] = 301.0"
    )
    proc = _run_copy(
        tmp_path,
        "-c",
        _RUN_AS_MAIN,
        str(running),
        str(driver),
        "scripts.generalization_probe_battery",
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == drv.EXIT_CODES[drv.REASON_ABORTED], out
    assert (
        "[driver] refuse to launch: the running driver is not the compilation of the "
        "driver bytes it hashed" in out
    ), out
    assert (
        "[driver] refuse to launch: not run from the bytes it was hashed by: "
        "scripts.generalization_probe_battery" in out
    ), out
    assert not (tmp_path / man.EXP).exists()


def _print_mark(path: Path) -> None:
    path.write_text(f"print({_MARK!r})\n", encoding="utf-8")


def test_command_line_launch_does_not_run_a_scripts_initializer(tmp_path: Path) -> None:
    """未追跡の ``scripts/__init__.py`` は実行されない.

    scripts は名前空間 (Codex 3 回目 MEDIUM-2)。
    """
    driver = _launch_copy(tmp_path)
    _print_mark(tmp_path / "scripts" / "__init__.py")
    proc = _run_copy(tmp_path, str(driver), "--stage", "pilot")
    out = proc.stdout + proc.stderr
    assert _MARK not in out, out
    assert proc.returncode == drv.EXIT_CODES[drv.REASON_ABORTED], out
    assert "[driver] refuse to launch: driver certification unreadable" in out
    for phrase in _EXECUTED_PHRASES:
        assert phrase not in out, out


def test_command_line_launch_refuses_to_import_a_shadow(tmp_path: Path) -> None:
    """``scripts/`` に置いた ``numpy.py`` は、門が import させない.

    起動の sys.path[0] が scripts/ なので、置けば numpy を横取りする。
    """
    driver = _launch_copy(tmp_path)
    _print_mark(tmp_path / "scripts" / "numpy.py")
    proc = _run_copy(tmp_path, str(driver), "--stage", "pilot")
    out = proc.stdout + proc.stderr
    assert _MARK not in out, out
    assert proc.returncode == 1, out
    assert (
        "ImportError: refusing to import code outside the pinned files and the "
        "environment: numpy" in out
    ), out
    assert not (tmp_path / man.EXP).exists()


def test_command_line_launch_refuses_code_imported_before_the_gate(
    tmp_path: Path,
) -> None:
    """門より前に取り込まれた環境の外のコードは、走査が起動を拒否する.

    例: 起動時の sitecustomize。
    """
    driver = _launch_copy(tmp_path)
    site = tmp_path / "site"
    site.mkdir()
    _print_mark(site / "sitecustomize.py")
    proc = _run_copy(
        tmp_path, str(driver), "--stage", "pilot", extra_env={"PYTHONPATH": str(site)}
    )
    out = proc.stdout + proc.stderr
    assert _MARK in out, "the fixture did not run before the gate"
    assert proc.returncode == drv.EXIT_CODES[drv.REASON_ABORTED], out
    assert (
        "[driver] refuse to launch: run outside the pinned files and the environment: "
        "sitecustomize" in out
    ), out
    assert not (tmp_path / man.EXP).exists()


def test_command_line_launch_refuses_a_startup_customization_that_failed(
    tmp_path: Path,
) -> None:
    """副作用の後で import に失敗した sitecustomize は sys.modules に残らない.

    走査では見えないので、所在で起動を拒否する (Codex 4 回目 HIGH-2)。
    """
    driver = _launch_copy(tmp_path)
    site = tmp_path / "site"
    site.mkdir()
    (site / "sitecustomize.py").write_text(
        f"print({_MARK!r})\nimport gp_driver_module_that_is_not_installed\n",
        encoding="utf-8",
    )
    proc = _run_copy(
        tmp_path, str(driver), "--stage", "pilot", extra_env={"PYTHONPATH": str(site)}
    )
    out = proc.stdout + proc.stderr
    assert _MARK in out, "the fixture did not run before the gate"
    assert (
        "run outside the pinned files and the environment: sitecustomize" not in out
    ), "the failed customization stayed in sys.modules (the fixture does not reproduce)"
    assert proc.returncode == drv.EXIT_CODES[drv.REASON_ABORTED], out
    assert (
        "[driver] refuse to launch: startup code outside the environment: "
        "sitecustomize" in out
    ), out
    assert not (tmp_path / man.EXP).exists()


def test_command_line_launch_refuses_a_pythonpath_shadow(tmp_path: Path) -> None:
    """PYTHONPATH の影は、名前に依らず起動を拒否する (code-reviewer HIGH-2).

    venv の ``_virtualenv.pth`` の import 行は、site-packages より前にある PYTHONPATH の
    ``_virtualenv.py`` を site の時点で実行する。import に失敗すると
    sys.modules に残らない。
    """
    driver = _launch_copy(tmp_path)
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "_virtualenv.py").write_text(
        f"print({_MARK!r})\nimport gp_driver_module_that_is_not_installed\n",
        encoding="utf-8",
    )
    proc = _run_copy(
        tmp_path,
        str(driver),
        "--stage",
        "pilot",
        extra_env={"PYTHONPATH": str(shadow)},
    )
    out = proc.stdout + proc.stderr
    venv_pth = Path(sysconfig.get_paths()["purelib"]) / "_virtualenv.pth"
    if venv_pth.is_file():  # uv・virtualenv の venv (今の CI と手元)
        assert _MARK in out, "the shadow did not run before the gate"
        assert (
            "run outside the pinned files and the environment: _virtualenv" not in out
        )
    assert proc.returncode == drv.EXIT_CODES[drv.REASON_ABORTED], out
    assert (
        "[driver] refuse to launch: startup code outside the environment: "
        f"PYTHONPATH ({shadow})" in out
    ), out
    assert not (tmp_path / man.EXP).exists()


# ---------------------------------------------------------------- harness の判定器


# 証拠の記録は、harness を plugin として読み込ませた実の pytest に書かせて確かめる
# (Codex 3 回目 MEDIUM-1・LOW-1)。file 名は test_driver.py (assert 文の判定が見る名前)
_PROBE_TESTS = """
import pytest


@pytest.fixture
def broken():
    raise KeyError("fixture")


@pytest.fixture
def bad_teardown():
    yield
    raise OSError("teardown boom")


def test_assert():
    assert 1 == 2


def test_multi_line_assert():
    assert [] == [
        "x"
    ]


def test_raise_assertion():
    raise AssertionError("the real Ollama transport was used")


@pytest.mark.parametrize("v", ["a] - b", "ok"])
def test_param(v):
    assert v == "ok"


def test_setup(broken):
    pass


def test_teardown(bad_teardown):
    pass


def helper():
    raise ValueError("inner")


def test_chain():
    try:
        helper()
    except ValueError as exc:
        raise RuntimeError("outer") from exc


def test_did_not_raise():
    with pytest.raises(KeyError):
        pass


def test_tab_assert():
    assert<TAB>1 == 2
"""


def _probe_run(probe: Path, out: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    """Probe の test を、harness を plugin として読み込ませた実の pytest で走らせる."""
    env = dict(
        os.environ,
        PYTHONUTF8="1",
        PYTHONDONTWRITEBYTECODE="1",
        **{harness._WITNESS_ENV: str(out)},
    )
    return subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            harness._PLUGIN,
            "--rootdir",
            str(probe),
            *extra,
            str(probe / "test_driver.py"),
        ],
        cwd=str(_ROOT),
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )


def test_harness_plugin_records_items_phases_and_chains(tmp_path: Path) -> None:
    probe = tmp_path / "probe"
    probe.mkdir()
    # assert の後のタブは chr(9) で組む (Codex 4 回目 BL-2)
    (probe / "test_driver.py").write_text(
        _PROBE_TESTS.replace("<TAB>", chr(9)), encoding="utf-8"
    )
    out = tmp_path / "records.jsonl"
    proc = _probe_run(probe, out)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    records = harness.read_records(out)
    rows = {
        (r["function"], r["param"], r["when"]): r
        for r in records
        if r["when"] != harness._FINISH
    }
    # session の終わりの記録 (Codex 4 回目 MEDIUM-2)。選ばれた item が全て走りきり、
    # 打ち切りが無い (Codex 5 回目 MEDIUM-1)
    finish = [r for r in records if r["when"] == harness._FINISH]
    assert len(finish) == 1, finish
    assert finish[0]["exitstatus"] == 1
    assert finish[0]["collected"] == 10  # probe の test の数
    assert (finish[0]["items"], finish[0]["ran"], finish[0]["stopped"]) == (
        10,
        10,
        False,
    )
    assert harness.finished_with_failures(proc.returncode, records)
    # --maxfail で打ち切った run は、exit 1 と session の終わりの記録があっても、
    # 最後まで走った run に数えない (Codex 5 回目 MEDIUM-1)
    cut_out = tmp_path / "cut.jsonl"
    cut = _probe_run(probe, cut_out, "--maxfail=1")
    cut_records = harness.read_records(cut_out)
    cut_finish = [r for r in cut_records if r["when"] == harness._FINISH]
    assert cut.returncode == 1, cut.stdout + cut.stderr
    assert [r["exitstatus"] for r in cut_finish] == [1]
    assert (cut_finish[0]["items"], cut_finish[0]["ran"]) == (10, 1)
    assert cut_finish[0]["stopped"] is True
    assert not harness.finished_with_failures(cut.returncode, cut_records)
    # 本番の run は 1 件を --deselect する: 数えるのは deselect の後の item
    # (code-reviewer LOW)
    kept_out = tmp_path / "kept.jsonl"
    # (nodeid は rootdir = probe からの相対、harness の _DESELECT と同じ形)
    kept = _probe_run(probe, kept_out, "--deselect", "test_driver.py::test_assert")
    kept_records = harness.read_records(kept_out)
    kept_finish = [r for r in kept_records if r["when"] == harness._FINISH]
    assert [(r["items"], r["ran"]) for r in kept_finish] == [(9, 9)], kept.stdout
    assert harness.finished_with_failures(kept.returncode, kept_records)
    assert set(rows) == {
        ("test_assert", None, "call"),
        ("test_multi_line_assert", None, "call"),
        ("test_raise_assertion", None, "call"),
        ("test_param", "a] - b", "call"),
        ("test_setup", None, "setup"),
        ("test_teardown", None, "teardown"),
        ("test_chain", None, "call"),
        ("test_did_not_raise", None, "call"),
        ("test_tab_assert", None, "call"),
    }
    assert rows["test_tab_assert", None, "call"]["assert_stmt"] is True
    assert rows["test_assert", None, "call"]["assert_stmt"] is True
    assert rows["test_multi_line_assert", None, "call"]["assert_stmt"] is True
    assert rows["test_param", "a] - b", "call"]["assert_stmt"] is True
    raised = rows["test_raise_assertion", None, "call"]
    assert raised["assert_stmt"] is False
    assert raised["chain"][0]["type"] == "builtins.AssertionError"
    setup = rows["test_setup", None, "setup"]["chain"]
    assert [(c["type"], c["text"]) for c in setup] == [
        ("builtins.KeyError", "'fixture'")
    ]
    teardown = rows["test_teardown", None, "teardown"]["chain"]
    assert teardown[0]["text"] == "teardown boom"
    chain = rows["test_chain", None, "call"]["chain"]
    assert [c["type"] for c in chain] == [
        "builtins.RuntimeError",
        "builtins.ValueError",
    ]
    assert ["test_driver.py", "helper"] in chain[1]["frames"]
    assert ["test_driver.py", "helper"] not in chain[0]["frames"]
    did_not = rows["test_did_not_raise", None, "call"]
    assert did_not["assert_stmt"] is False
    assert did_not["chain"][0]["type"].endswith(".Failed")
    assert did_not["chain"][0]["text"] == "DID NOT RAISE <class 'KeyError'>"


def _rec(
    function: str,
    *chain: tuple[str, str, tuple[tuple[str, str], ...]],
    when: str = "call",
    param: str | None = None,
    assert_stmt: bool = False,
) -> dict[str, Any]:
    links = [
        {"type": t, "text": x, "frames": [list(f) for f in fr]} for t, x, fr in chain
    ]
    return {
        "function": function,
        "param": param,
        "when": when,
        "assert_stmt": assert_stmt,
        "chain": links,
    }


_DRV = harness._DRIVER_FILE
_TEST_DRIVER = harness._TEST_FILE
_DECODE = ("json.decoder.JSONDecodeError", "Expecting value", ((_DRV, "_json_of"),))


def test_harness_witness_needs_the_item_phase_and_one_exception() -> None:
    """証拠は、期待 test の記録で照合する (Codex 3 回目 MEDIUM-1).

    その item・段の、同じ 1 つの例外で、型・文・経由が揃うこと。
    """
    asserted = frozenset({"test_a"})
    plain = harness.Witness(assert_stmt=True)
    hit = _rec(
        "test_a", ("builtins.AssertionError", "assert 1 == 2", ()), assert_stmt=True
    )
    assert harness.witnessed(plain, asserted, [hit]) is not None
    # assert 文でない (NameError・封鎖の raise AssertionError)・setup・
    # 別の test は数えない
    for miss in (
        _rec("test_a", ("builtins.NameError", "name 'observed' is not defined", ())),
        _rec(
            "test_a",
            ("builtins.AssertionError", "the real Ollama transport was used", ()),
        ),
        _rec(
            "test_a",
            ("builtins.AssertionError", "x", ()),
            when="setup",
            assert_stmt=True,
        ),
        _rec("test_z", ("builtins.AssertionError", "x", ()), assert_stmt=True),
    ):
        assert harness.witnessed(plain, asserted, [miss]) is None, miss
    expect = frozenset({"test_failed_responses_are_resent"})
    t8 = harness.Witness(item="non_json", exc="JSONDecodeError", via="_json_of")
    good = _rec("test_failed_responses_are_resent", _DECODE, param="non_json")
    assert harness.witnessed(t8, expect, [good]) == {
        "function": "test_failed_responses_are_resent",
        "param": "non_json",
        "when": "call",
        "type": "json.decoder.JSONDecodeError",
        "text": "Expecting value",
    }
    for miss in (
        # 別の parameter・teardown の段
        _rec("test_failed_responses_are_resent", _DECODE, param="http500"),
        _rec(
            "test_failed_responses_are_resent",
            _DECODE,
            param="non_json",
            when="teardown",
        ),
        # driver のその関数を通っていない (test の json.loads で出た)
        _rec(
            "test_failed_responses_are_resent",
            (
                "json.decoder.JSONDecodeError",
                "Expecting value",
                ((_TEST_DRIVER, "test_x"),),
            ),
            param="non_json",
        ),
        # 型と経由が別の例外に分かれている
        _rec(
            "test_failed_responses_are_resent",
            ("builtins.RuntimeError", "outer", ((_DRV, "_json_of"),)),
            ("json.decoder.JSONDecodeError", "Expecting value", ()),
            param="non_json",
        ),
        # 型名の末尾が一致するだけの別の型
        _rec(
            "test_failed_responses_are_resent",
            ("x.NotJSONDecodeError", "Expecting value", ((_DRV, "_json_of"),)),
            param="non_json",
        ),
    ):
        assert harness.witnessed(t8, expect, [miss]) is None, miss
    # chain の 2 つ目の例外でも、同じ 1 つの例外で全てが揃えば数える
    caused = _rec(
        "test_failed_responses_are_resent",
        ("builtins.RuntimeError", "outer", ()),
        _DECODE,
        param="non_json",
    )
    assert harness.witnessed(t8, expect, [caused]) is not None


def test_harness_status_separates_wrong_reasons() -> None:
    """判定は 3 通り: SURVIVED / 理由が違う / KILLED.

    理由が違う = WRONG_REASON・COLLECTION_ERROR・TIMEOUT・ABNORMAL_EXIT・
    NO_FAILURE_RECORD。
    """
    mut = harness.Mutant("x", "o", "n", frozenset({"test_a"}), "why")
    done = {
        "when": harness._FINISH,
        "exitstatus": 1,
        "collected": 3,
        "failed": 1,
        "items": 3,
        "ran": 3,
        "stopped": False,
    }
    hit = [
        _rec("test_a", ("builtins.AssertionError", "assert 0", ()), assert_stmt=True),
        done,
    ]
    miss = [_rec("test_a", ("builtins.TypeError", "unrelated", ())), done]
    assert harness.status_of(mut, 0, set(), [], collect=False) == "SURVIVED"
    assert harness.status_of(mut, -1, set(), [], collect=False) == "TIMEOUT"
    assert (
        harness.status_of(mut, 1, set(), [done], collect=False) == "NO_FAILURE_RECORD"
    )
    assert (
        harness.status_of(mut, 1, {"test_a"}, hit, collect=True) == "COLLECTION_ERROR"
    )
    assert harness.status_of(mut, 1, {"test_a"}, hit, collect=False) == "KILLED"
    assert harness.status_of(mut, 1, {"test_a"}, miss, collect=False) == "WRONG_REASON"
    # pytest が test の失敗 (exit 1) で最後まで走っていない run の記録は、証拠に数えない
    # (INTERNALERROR・中断・使い方の誤り・test 無し、Codex 4 回目 MEDIUM-2)
    for code in (2, 3, 4, 5):
        crashed = [*hit[:1], {**done, "exitstatus": code}]
        assert (
            harness.status_of(mut, code, {"test_a"}, crashed, collect=False)
            == "ABNORMAL_EXIT"
        ), code
        assert (
            harness.status_of(mut, code, {"test_a"}, hit, collect=False)
            == "ABNORMAL_EXIT"
        ), code
    # session の終わりの記録が無い・2 つある・exitstatus が違う・打ち切った・
    # 走りきっていない item がある・数が無い (Codex 5 回目 MEDIUM-1)
    for records in (
        hit[:1],
        [*hit, done],
        [*hit[:1], {**done, "exitstatus": 3}],
        [*hit[:1], {**done, "stopped": True}],
        [*hit[:1], {**done, "ran": 2}],
        [*hit[:1], {**done, "items": None, "ran": None}],
    ):
        assert (
            harness.status_of(mut, 1, {"test_a"}, records, collect=False)
            == "ABNORMAL_EXIT"
        ), records


def test_harness_runs_the_tests_with_an_empty_bytecode_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """各 run に、空の bytecode の置き場所を渡し、書き込みも止める.

    Codex 4 回目 MEDIUM-1。継いだ PYTHONPYCACHEPREFIX は上書きし、
    計測を変える env (PYTEST_ADDOPTS 等) は渡さない。
    plugin と記録の置き場所も渡す。
    """
    seen: list[dict[str, object]] = []

    def fake_run(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        cache = Path(kw["env"]["PYTHONPYCACHEPREFIX"])
        seen.append(
            {
                "cmd": cmd,
                "env": kw["env"],
                "cache": cache,
                "empty": cache.is_dir() and not any(cache.iterdir()),
            }
        )
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(harness.subprocess, "run", fake_run)
    inherited = {
        "X": "1",
        "PYTHONPYCACHEPREFIX": str(tmp_path / "old_cache"),
        "PYTEST_ADDOPTS": "-x",
        "PYTEST_PLUGINS": "other_plugin",
    }
    assert harness._run_tests(inherited, tmp_path) == (0, set(), False, [])
    assert harness._run_tests(inherited, tmp_path) == (0, set(), False, [])
    first, second = seen
    assert first["empty"] is True, "ran with a bytecode cache that was not empty"
    assert first["cache"] != second["cache"], "reused the bytecode cache of a run"
    for run in seen:
        cache = run["cache"]
        assert isinstance(cache, Path)
        assert not cache.exists(), "left the bytecode cache behind"
    cmd = first["cmd"]
    assert isinstance(cmd, list)
    assert cmd[cmd.index(harness._PLUGIN) - 1] == "-p"
    env = first["env"]
    assert isinstance(env, dict)
    assert env["X"] == "1"
    assert harness._WITNESS_ENV in env
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert env["PYTHONPYCACHEPREFIX"] != inherited["PYTHONPYCACHEPREFIX"]
    assert "PYTEST_ADDOPTS" not in env
    assert "PYTEST_PLUGINS" not in env


def test_harness_does_not_run_a_stale_pyc(tmp_path: Path) -> None:
    """同じ長さ・同じ mtime の source に書き換えても、前の source の pyc で走らない.

    前タスクの DI-3 (w9 の run が w8 の pyc で走った) の再現。まず、cache を渡さない
    通常の起動では
    前の pyc で走ることを確かめる (fixture が穴を再現していること)。
    """
    (tmp_path / "scripts").mkdir()
    harness_file = Path(harness.__file__)
    shutil.copy2(harness_file, tmp_path / "scripts" / harness_file.name)
    module = tmp_path / "scripts" / "gp_stale_probe.py"
    module.write_text("VALUE = 1\n", encoding="utf-8")
    # pyc は __pycache__ の標準の位置に置く (cache_from_source は、harness が渡す
    # PYTHONPYCACHEPREFIX の下では prefix の下を指す)
    tag = sys.implementation.cache_tag
    cfile = module.parent / "__pycache__" / f"{module.stem}.{tag}.pyc"
    # SOURCE_DATE_EPOCH があると既定は hash の pyc になるので、mtime の pyc を明示する
    py_compile.compile(
        str(module),
        cfile=str(cfile),
        doraise=True,
        invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP,
    )
    before = module.stat()
    module.write_text("VALUE = 2\n", encoding="utf-8")
    os.utime(module, ns=(before.st_atime_ns, before.st_mtime_ns))
    env = {k: v for k, v in os.environ.items() if k not in harness._DROPPED_ENV}
    env.pop("PYTHONPYCACHEPREFIX", None)
    env.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    plain = subprocess.run(
        [
            sys.executable,
            "-c",
            "from scripts import gp_stale_probe as m; print(m.VALUE)",
        ],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    assert plain.stdout.strip() == "1", "the fixture does not reproduce a stale pyc"
    test = tmp_path / harness._TEST_REL
    test.parent.mkdir(parents=True)
    test.write_text(
        "from scripts import gp_stale_probe\n\n\n"
        "def test_value():\n"
        "    assert gp_stale_probe.VALUE == 2\n",
        encoding="utf-8",
    )
    code, failed, collect, records = harness._run_tests(env, tmp_path)
    assert (code, failed, collect) == (0, set(), False), records


def test_harness_summary_drops_local_paths_and_addresses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """certification の証拠の要約に、手元の path・address を残さない (汎用の規則).

    消すもの: home の path・tmp のユーザー名・メモリの address。照合は元の文で行う
    (security-checker MEDIUM)。backslash は chr(92) で組む。実の tmp・home・ユーザー名の
    置き換えは外して決定的に照合する (ubuntu の /tmp も消すため、code-reviewer HIGH-1)。
    """
    monkeypatch.setattr(harness, "_local_names", list)
    monkeypatch.setattr(harness, "_local_user", str)
    bs = chr(92)
    windows = f"C:{bs}{bs}Users{bs}{bs}someone{bs}{bs}AppData"
    texts = {
        "WindowsPath('C:/Users/someone/AppData/Local/Temp/pytest-of-someone/x')": (
            "WindowsPath('<home>/AppData/Local/Temp/pytest-of-<user>/x')"
        ),
        f"No such file: '{windows}'": f"No such file: '<home>{bs}{bs}AppData'",
        "PosixPath('/home/someone/x') /tmp/pytest-of-someone/y": (
            "PosixPath('<home>/x') /tmp/pytest-of-<user>/y"
        ),
        "<function f at 0x000002B9328DB060>": "<function f at 0x?>",
        "records.jsonl was published": "records.jsonl was published",
        # Codex 4 回目 LOW-1: 空白入りの名前・UNC・/root。比較の数値の 0x は残す
        "C:/Users/Jane Doe/AppData/x": "<home>/AppData/x",
        f"{bs}{bs}server{bs}Users{bs}alice{bs}x": f"{bs}{bs}server<home>{bs}x",
        "/root/x": "<home>/x",
        "expected 0xdead, got 0xbeef": "expected 0xdead, got 0xbeef",
        # address は object の repr の中だけ (Codex 5 回目 LOW-1)
        "expected at 0xdead, got at 0xbeef": "expected at 0xdead, got at 0xbeef",
        # repr の address は 8 桁以上: code・frame・weakref (2 つ)・pytest が後ろを
        # 省いたもの・`` at 0x`` ごと省かれた残り (code-reviewer HIGH)
        '<code object <module> at 0x000001F2A3B4C5D0, file "a.py", line 1>': (
            '<code object <module> at 0x?, file "a.py", line 1>'
        ),
        "<frame at 0x7f3b2c1d0e10, file 'x.py', line 3, code f>": (
            "<frame at 0x?, file 'x.py', line 3, code f>"
        ),
        "<weakref at 0x000001F2A3B4C5D0; to 'Foo' at 0x000001F2A3B4C5E0>": (
            "<weakref at 0x?; to 'Foo' at 0x?>"
        ),
        "_PinnedLoader object at 0x000001F2A3B4...": "_PinnedLoader object at 0x?...",
        "u...00195CF8963E0>, structure=": "u...?>, structure=",
        # 名前の後に区切り文字が無ければ、行の残りを消さない (code-reviewer LOW-8)
        "expected /home/alice got X; more": "expected <home> got X; more",
    }
    for raw, want in texts.items():
        assert harness.redact(raw) == want, raw
    record = _rec("test_a", ("builtins.AssertionError", next(iter(texts)), ()))
    summary = harness._summary(record, record["chain"][0])
    assert "someone" not in str(summary["text"])


_BS = chr(92)


@pytest.mark.parametrize(
    ("tmp", "home", "user"),
    [
        ("/tmp", "/home/runner", "runner"),  # noqa: S108 — 置き換えの入力の文字列
        (
            _BS.join(["C:", "Users", "Jane Doe", "AppData", "Local", "Temp"]),
            _BS.join(["C:", "Users", "Jane Doe"]),
            "Jane Doe",
        ),
    ],
    ids=["posix", "windows"],
)
def test_harness_summary_drops_the_local_names(
    monkeypatch: pytest.MonkeyPatch, tmp: str, home: str, user: str
) -> None:
    """手元の実の tmp・home・ユーザー名は、区切り・大文字小文字を問わず消える.

    実名は固定値に差し替えて確かめる (code-reviewer HIGH-1)。
    """
    monkeypatch.setattr(harness, "_tmp_dir", lambda: tmp)
    monkeypatch.setattr(harness, "_home_dir", lambda: home)
    monkeypatch.setattr(harness.getpass, "getuser", lambda: user)
    for path in (tmp, home):
        for form in (
            path,
            path.replace(_BS, "/"),
            path.replace(_BS, _BS + _BS),
            path.upper(),
        ):
            got = harness.redact(
                f"No such file: '{form}{_BS}x' (custom-{user}) AppData"
            )
            assert path.lower() not in got.lower(), got
            assert user.lower() not in got.lower(), got
            assert got.endswith(") AppData"), got
    # 実の tmp・home は path の要素の終わりでだけ置き換える
    # (/home/ann で /home/annette を割らない、Codex 5 回目 LOW-1)。
    # 割らなかった home は汎用の規則が消す
    assert "<tmp>dir" not in harness.redact(f"{tmp}dir/x")
    assert harness.redact(f"{home}ette/x") == "<home>/x"
    # 区切りでない記号 (括弧・カンマ等) の前でも、実の home はそこで終わる
    assert harness.redact(f"registry ({home}), then {home}, x") == (
        "registry (<home>), then <home>, x"
    )
    # ユーザー名は英数字の境界の内側だけ
    # (AppData の data を消さない、code-reviewer LOW-8)
    monkeypatch.setattr(harness.getpass, "getuser", lambda: "data")
    assert harness.redact("AppData and data") == "AppData and <user>"
    # 短すぎる名前・取れない名前は消さない
    monkeypatch.setattr(harness.getpass, "getuser", lambda: "ab")
    assert harness.redact("ab cd") == "ab cd"

    def no_home() -> str:
        msg = "Could not determine home directory."
        raise RuntimeError(msg)

    monkeypatch.setattr(harness, "_home_dir", no_home)
    assert dict(harness._local_names()).get(tmp) == "<tmp>"  # home が無くても落ちない


def _parametrized_tests() -> set[str]:
    return {
        name
        for name, obj in globals().items()
        if name.startswith("test_")
        and any(m.name == "parametrize" for m in getattr(obj, "pytestmark", []))
    }


def test_harness_witnesses_name_what_they_match() -> None:
    """理由の文のある証拠は、型か文を持つ.

    item は、名指す相手の test がある形で登録する。
    """
    parametrized = _parametrized_tests()
    assert "test_failed_responses_are_resent" in parametrized
    for m in harness.MUTANTS:
        w = m.witness
        assert w.when in harness._PHASES, m.label
        if w.assert_stmt:
            continue
        assert w.exc is not None or w.text is not None, m.label
        # item を名指すなら parametrize の test、名指さないなら
        # parametrize でない test を期待する
        if w.item is not None:
            assert m.expect & parametrized, m.label
        else:
            assert m.expect - parametrized, m.label


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
