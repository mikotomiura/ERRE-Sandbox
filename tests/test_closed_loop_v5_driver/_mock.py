"""閉ループ v5 driver の test 用 mock Ollama (mock transport のみ、実モデル不使用).

mock は **送られた body の文面と seed だけ** から答える
(世界名・軸・plan・状態を知らない)。
閉ループでは body を事前に計算できない。そこで呼び出しの識別には、
「これまでに正常に答えた回数」= call_index を使う
(driver は call_index の順に 1 件ずつ送り、再送は同じ call_index の中で起こる)。
"""

from __future__ import annotations

import asyncio
import json
import random
from typing import TYPE_CHECKING, Any

import httpx
from scripts import closed_loop_v5_battery as bat
from scripts import closed_loop_v5_driver as drv
from scripts import closed_loop_v5_pilot_scorer as ps
from scripts import skill_lever_battery as v2bat
from scripts.skill_lever_scorer import messages_sha256
from scripts.stage_b_battery import ACTIONS

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    Policy = Callable[[int, dict[str, Any]], str | None]

DIGEST = "sha256:" + "0" * 64
BOTTOM = "わからない"
FULL_PLAN = tuple(bat.pilot_plan())
N_PLAN = len(FULL_PLAN)  # 3,072
N_SHORT = 48  # 短縮 run: r = 12 の t = 0..5 (両軸・4 世界)
SEPARATORS = ("\u2028", "\u2029", "\u0085")


# ---------------------------------------------------------- 文面の読み取り


def user_text(body: dict[str, Any]) -> str:
    return body["messages"][-1]["content"]


def shown(body: dict[str, Any]) -> list[str]:
    """表示された選択肢 (最後の行の「: 」の後を「、」で区切る)."""
    return user_text(body).rsplit("\n", 1)[-1].split(": ", 1)[1].split("、")


# ------------------------------------------------------------- policies


def first_shown(_index: int, body: dict[str, Any]) -> str:
    """状態を読まない: 常に表示の先頭."""
    return shown(body)[0]


def varying(_index: int, body: dict[str, Any]) -> str:
    """連鎖を分岐させる mock.

    表示肢・Ω 外・⊥・装飾付き・行区切り付きを、body に決定的な乱数で混ぜる。
    """
    seed = body["options"]["seed"]
    rng = random.Random(f"{seed}-{messages_sha256(body['messages'])}")
    opts = shown(body)
    u = rng.random()
    if u < 0.55:
        return rng.choice(opts)
    if u < 0.65:
        return rng.choice([a for a in ACTIONS if a not in opts])
    if u < 0.75:
        return BOTTOM
    if u < 0.85:
        return f"  **{rng.choice(opts)}**\n"
    return rng.choice(opts) + rng.choice(SEPARATORS)


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


def connect_error() -> Exception:
    return httpx.ConnectError("refused")


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
        # 何回目の /api/version を落とすか (0 始まり。0 = 開始時の preflight)
        self.preflight_down = preflight_down
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


# ------------------------------------------------------------- 出力の読み取り


def lines_of(path: Path) -> list[str]:
    """凍結 reader と同じ読み方 (``read_text().splitlines()``)."""
    return path.read_text(encoding="utf-8").splitlines()


def published(run_dir: Path) -> list[ps.Record]:
    return ps.load_records(lines_of(run_dir / drv.RECORDS_NAME))


def partial(run_dir: Path) -> list[ps.Record]:
    return ps.load_records(lines_of(run_dir / drv.PARTIAL_NAME))


def evaluate(records_path: Path, run_dir: Path) -> dict[str, Any]:
    """凍結 ``evaluate_records`` (run.sh の写像が最初に呼ぶ検証と測定)."""
    meta = (run_dir / drv.META_NAME).read_text(encoding="utf-8")
    return ps.evaluate_records(lines_of(records_path), meta)


def provenance(run_dir: Path) -> dict[str, Any]:
    return json.loads((run_dir / "provenance.json").read_text(encoding="utf-8"))
