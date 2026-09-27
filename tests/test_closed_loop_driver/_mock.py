"""閉ループ driver の test 用 mock Ollama (mock transport のみ、実モデル不使用).

mock は **送られた body の文面だけ** から答える (世界名・plan・状態を知らない)。
閉ループでは body を事前に計算できないので、v3 のように (prompt sha, seed) から key を
逆引きしない。呼び出しの識別には「これまでに正常に答えた回数」= call_index を使う
(driver は call_index の順に 1 件ずつ送り、再送は同じ call_index の中で起こる)。
"""

from __future__ import annotations

import asyncio
import json
import random
import re
from typing import TYPE_CHECKING, Any

import httpx
from scripts import closed_loop_driver as drv
from scripts import closed_loop_scorer as sc
from scripts import skill_lever_battery as v2bat
from scripts.stage_b_battery import ACTIONS

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    Policy = Callable[[int, dict[str, Any]], str | None]

DIGEST = "sha256:" + "0" * 64
BOTTOM = "わからない"
N_PLAN = len(sc.frozen_plan())  # 2,808
N_C0 = sc.n_c0()  # 240

_SITUATION = re.compile(r"状況: 天候=(.+?)、時刻=(.+?)、同伴=(.+?)。")
_SUCCESS = re.compile(r"^条件: (\S+) / (\S+) / (\S+) → 行動: (\S+) \(成功あり\)$")
_TRIED = re.compile(r"^条件: (\S+) / (\S+) / (\S+) → 試した: (\S+)$")


# ---------------------------------------------------------- 文面の読み取り


def user_text(body: dict[str, Any]) -> str:
    return body["messages"][-1]["content"]


def shown(body: dict[str, Any]) -> list[str]:
    """表示された選択肢 (最後の行の「: 」の後を「、」で区切る)."""
    return user_text(body).rsplit("\n", 1)[-1].split(": ", 1)[1].split("、")


def situation(body: dict[str, Any]) -> tuple[str, str, str]:
    m = _SITUATION.search(user_text(body))
    assert m is not None
    return m.group(1), m.group(2), m.group(3)


def success_rows(body: dict[str, Any]) -> list[tuple[tuple[str, str, str], str]]:
    lines = user_text(body).splitlines()
    return [
        ((m.group(1), m.group(2), m.group(3)), m.group(4))
        for line in lines
        if (m := _SUCCESS.match(line))
    ]


def tried(body: dict[str, Any]) -> dict[tuple[str, str, str], list[str]]:
    out = {}
    for line in user_text(body).splitlines():
        if m := _TRIED.match(line):
            out[(m.group(1), m.group(2), m.group(3))] = m.group(4).split("、")
    return out


# ------------------------------------------------------------- policies


def follow_success(_index: int, body: dict[str, Any]) -> str:
    """同じ weather の成功行に従い、無ければこの状況でまだ試していない表示肢を試す."""
    sig = situation(body)
    opts = shown(body)
    for row_sig, label in success_rows(body):
        if row_sig[0] == sig[0] and label in opts:
            return label
    done = tried(body).get(sig, [])
    return next((o for o in opts if o not in done), opts[0])


def first_shown(_index: int, body: dict[str, Any]) -> str:
    """状態を読まない: 常に表示の先頭."""
    return shown(body)[0]


def varying(_index: int, body: dict[str, Any]) -> str:
    """連鎖を分岐させる: 表示肢・Ω 外・⊥・装飾付きを、body に決定的な乱数で混ぜる."""
    seed = body["options"]["seed"]
    sha = drv.messages_sha256(body["messages"])
    rng = random.Random(f"{seed}-{sha}")
    opts = shown(body)
    u = rng.random()
    if u < 0.6:
        return rng.choice(opts)
    if u < 0.7:
        return rng.choice([a for a in ACTIONS if a not in opts])
    if u < 0.8:
        return BOTTOM
    return f"  **{rng.choice(opts)}**\n"


def c0_bottom(n_bottom: int, *, skip: int = 0) -> Policy:
    """C0 区間の call_index が [skip, skip + n_bottom) の呼び出しだけ ⊥."""

    def policy(index: int, body: dict[str, Any]) -> str:
        if index < N_C0 and skip <= index < skip + n_bottom:
            return BOTTOM
        return follow_success(index, body)

    return policy


def failing(
    target: int, n_fail: int, exc: Callable[[], Exception], base: Policy = first_shown
) -> Policy:
    """call_index = target の最初の n_fail 回の送信で例外を投げる."""
    count = {"n": 0}

    def policy(index: int, body: dict[str, Any]) -> str | None:
        if index == target and count["n"] < n_fail:
            count["n"] += 1
            raise exc()
        return base(index, body)

    return policy


# ---------------------------------------------------------------- mock


def env_response(
    request: httpx.Request, digests: list[str], *, down: bool = False
) -> httpx.Response | None:
    """preflight の応答。digests は tags ごとに消費、down なら接続失敗."""
    if request.url.path in ("/api/version", "/api/tags") and down:
        raise httpx.ConnectError("refused", request=request)
    if request.url.path == "/api/version":
        return httpx.Response(200, json={"version": "mock"})
    if request.url.path == "/api/tags":
        digest = digests.pop(0) if len(digests) > 1 else digests[0]
        models = [{"name": v2bat.MODEL, "model": v2bat.MODEL, "digest": digest}]
        return httpx.Response(200, json={"models": models})
    return None


def chat_response(content: str | None, model: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": model,
            "message": {"role": "assistant", "content": content},
            "done": True,
            "done_reason": "stop",
            "eval_count": 3,
            "prompt_eval_count": 10,
            "total_duration": 1000,
        },
    )


class Ollama:
    """``httpx.MockTransport`` の handler。policy が content を返すか例外を投げる."""

    def __init__(
        self,
        policy: Policy,
        digests: tuple[str, ...] = (DIGEST,),
        model: str | None = None,
        preflight_down: frozenset[int] = frozenset(),
    ) -> None:
        self.policy = policy
        self.bodies: list[dict[str, Any]] = []  # 届いた chat body (再送を含む)
        self.answered: list[dict[str, Any]] = []  # 正常に答えた body (call_index 順)
        self.digests = list(digests)
        self.model = model
        self.preflight_down = (
            preflight_down  # 何回目の /api/version を落とすか (0 始まり)
        )
        self.n_version = -1

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            self.n_version += 1
        down = self.n_version in self.preflight_down
        env = env_response(request, self.digests, down=down)
        if env is not None:
            return env
        body = json.loads(request.content)
        self.bodies.append(body)
        content = self.policy(len(self.answered), body)
        if isinstance(content, str):
            self.answered.append(body)
        return chat_response(content, self.model or body["model"])


def do_run(run_dir: Path, policy: Policy, **kwargs: Any) -> tuple[str, Ollama]:
    ollama = Ollama(policy, **kwargs)
    reason = asyncio.run(drv.run(run_dir, httpx.MockTransport(ollama), backoff_s=0.0))
    return reason, ollama


def records(run_dir: Path) -> list[sc.Record]:
    return sc.load_records(
        (run_dir / "records.jsonl").read_text(encoding="utf-8").splitlines()
    )


CERT = drv._EXP_DIR / "results" / "v4_mutation.json"


def evaluate(run_dir: Path) -> dict[str, Any]:
    lines = (run_dir / "records.jsonl").read_text(encoding="utf-8").splitlines()
    meta = (run_dir / "meta.json").read_text(encoding="utf-8")
    return sc.evaluate_records(lines, meta, CERT)


def provenance(run_dir: Path) -> dict[str, Any]:
    return json.loads((run_dir / "provenance.json").read_text(encoding="utf-8"))
