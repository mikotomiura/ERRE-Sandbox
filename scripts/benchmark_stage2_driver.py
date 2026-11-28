"""判別性 gate 段 2 — battery を知らない汎用の実行器 (driver).

規則の SSOT は ``experiments/20261126-benchmark-stage2-discriminability/prereg.md`` (第 1 段 PILOT-FROZEN)。
設計 = ``.steering/20261126-benchmark-stage2-driver/design-final.md`` (案 B、DD-1)・decisions DD-4 (Codex r1)・DD-5。

* 呼び出しの中身は ``benchmark_stage2_plan`` の ``Segment`` / ``CallSpec`` だけから作る。本 module は battery を知らない。
* 送信前に wire の body を ``pl.body_for(spec, model)`` と型まで照合する (``ObservingTransport``)。POST は
  ``/api/chat`` と ``/api/show`` だけ。
* 記録は parse しない (読み手が凍結の parse で読む)。1 行 = 1 呼び出し、``ensure_ascii=True, sort_keys=True``、LF。
* 区切り (stage, battery, model) ごとに ``attempt-<n>/{records.partial.jsonl → records.jsonl, meta.json, attempts.jsonl}``。
  状態は ``<run>/<stage>/segments.json`` に確定する (途中は ``segments.partial.json``)。読み手は ``adopted_attempt`` だけを読む。
* 通信の欠測 (同じ body で初回 + 3 回の再送で解けない) はその区切りを ``not_computed_transport`` で閉じて次へ進み、
  stage の最後 (pilot は再生の前) に 1 回だけ再実行する (attempt-2、全記録の置き換え)。meta の違反は再実行しない。
* 期限 (stage 共通の実時間) は request の timeout・backoff・再実行にも適用する。
* 再開しない (空でない ``<run>/<stage>`` を拒否)。
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import pathlib
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from fractions import Fraction
from typing import TYPE_CHECKING, Any, Final, TextIO

import httpx
from scripts import benchmark_stage2_manifest_main as mm
from scripts import benchmark_stage2_plan as pl
from scripts import benchmark_stage2_stats as st

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence

_REPO_ROOT: Final[pathlib.Path] = pathlib.Path(__file__).resolve().parent.parent
EXP: Final[pathlib.Path] = (
    _REPO_ROOT / "experiments" / "20261126-benchmark-stage2-discriminability"
)
MODELS_JSON: Final[pathlib.Path] = EXP / "results" / "models.json"
DEFAULT_ENDPOINT: Final[str] = "http://127.0.0.1:11434"

OLLAMA_VERSION: Final[str] = "0.32.12"  # §A.1 (results/models.json と同じ)
RESENDS: Final[int] = 3  # 同じ body の再送 (送信は初回と合わせて最大 4 回、§H)
BACKOFF_SCHEDULE_S: Final[tuple[float, ...]] = (5.0, 30.0, 120.0)
TIMEOUT_S: Final[float] = 300.0  # 1 request (モデルの再ロードで 60 秒を超えうる)
DEADLINE_S: Final[dict[str, float]] = {
    pl.STAGE_PILOT: 12 * 3600.0,  # §H: pilot の実時間の停止
    pl.STAGE_MAIN: 36 * 3600.0,  # §H: 本走の実時間の停止
}
MAX_ATTEMPTS: Final[int] = 2  # 初回 + モデル単位の再実行 1 回

CHAT_PATH: Final[str] = "/api/chat"
SHOW_PATH: Final[str] = "/api/show"

RECORDS_NAME: Final[str] = "records.jsonl"
PARTIAL_NAME: Final[str] = "records.partial.jsonl"
META_NAME: Final[str] = "meta.json"
ATTEMPTS_NAME: Final[str] = "attempts.jsonl"
SEGMENTS_NAME: Final[str] = "segments.json"
SEGMENTS_PARTIAL_NAME: Final[str] = "segments.partial.json"
ACCOUNTING_NAME: Final[str] = "accounting.json"

# 区切りの状態 (segments.json)
S_COMPLETED: Final[str] = "completed"
S_TRANSPORT: Final[str] = "not_computed_transport"
S_TIMEOUT: Final[str] = "not_computed_timeout"
S_NOT_STARTED: Final[str] = "not_started"
S_INVALID_META: Final[str] = "invalid_meta"
S_INVALID_VERSION: Final[str] = "invalid_version"
STATUSES: Final[frozenset[str]] = frozenset(
    {
        S_COMPLETED,
        S_TRANSPORT,
        S_TIMEOUT,
        S_NOT_STARTED,
        S_INVALID_META,
        S_INVALID_VERSION,
    }
)

RECORD_KEYS: Final[frozenset[str]] = frozenset(
    {
        "stage",
        "battery",
        "model",
        "attempt",
        "call_index",
        "purpose",
        "arm",
        "encoding",
        "replicate",
        "probe_id",
        "k",
        "seed",
        "prompt_sha256",
        "raw",
        "response_model",
        "prompt_eval_count",
        "eval_count",
        "done_reason",
        "n_sends",
    }
)

# 送信の分類 (accounting.json、Codex r1 M3)
C_INITIAL: Final[str] = "initial"  # attempt-1 の各呼び出しの初回
C_RESEND: Final[str] = "resend"  # attempt-1 の再送
C_RETRY: Final[str] = "retry"  # attempt-2 (モデル単位の再実行) の全送信
C_REPLAY: Final[str] = "replay"  # 再生の区切りの全送信
CATEGORIES: Final[tuple[str, ...]] = (C_INITIAL, C_RESEND, C_RETRY, C_REPLAY)

EXIT_OK: Final[int] = 0  # 全区切りが completed
EXIT_INCOMPLETE: Final[int] = 3  # 走り終えたが completed でない区切りがある
EXIT_REFUSED: Final[int] = 2  # 起動の前提 (run dir・Ollama・gate) が満たされない


# ------------------------------------------------------------ 送信前の照合


class SentBodyMismatchError(RuntimeError):
    """送ろうとした body が plan と違う (driver の誤り。run を止める)."""


class PreflightError(RuntimeError):
    """起動の前提が満たされない (chat を 1 件も送らずに止まる)."""


def same(got: object, want: object) -> bool:
    """JSON の値として型まで一致 (False と 0、4096.0 と 4096 を区別する。dict は key の集合まで)."""
    if type(got) is not type(want):
        return False
    if isinstance(want, dict):
        assert isinstance(got, dict)
        return set(got) == set(want) and all(same(got[k], want[k]) for k in want)
    if isinstance(want, list):
        assert isinstance(got, list)
        return len(got) == len(want) and all(
            same(a, b) for a, b in zip(got, want, strict=True)
        )
    return got == want


class ObservingTransport(httpx.AsyncBaseTransport):
    """inner transport を包み、POST の body を送信前に照合して数える."""

    def __init__(self, inner: httpx.AsyncBaseTransport) -> None:
        self.inner = inner
        self.expected: tuple[pl.CallSpec, str] | None = None
        self.allow_show = False
        self.last_sent: dict[str, Any] | None = None
        self.n_chat = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            path = request.url.path
            if path == SHOW_PATH:
                if not self.allow_show:
                    msg = "unexpected /api/show outside the meta read"
                    raise SentBodyMismatchError(msg)
            elif path != CHAT_PATH:
                msg = f"unexpected POST path {path!r}"
                raise SentBodyMismatchError(msg)
            else:
                if self.expected is None:
                    msg = "chat request without an expected call"
                    raise SentBodyMismatchError(msg)
                spec, model = self.expected
                body = json.loads(request.content)
                if not same(body, pl.body_for(spec, model)):
                    msg = f"sent body differs from the plan: {model} {spec.key()}"
                    raise SentBodyMismatchError(msg)
                self.last_sent = body
                self.n_chat += 1
        elif request.method != "GET":
            msg = f"unexpected method {request.method!r}"
            raise SentBodyMismatchError(msg)
        return await self.inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self.inner.aclose()


# ------------------------------------------------------------ 期限と時計


class DeadlineReachedError(Exception):
    """stage 共通の期限に当たった (その区切りは not_computed_timeout)."""


@dataclass
class Clock:
    """単調時計と sleep (test で差し替える)."""

    now: Callable[[], float] = time.monotonic
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep


@dataclass
class Deadline:
    clock: Clock
    at: float

    def remaining(self) -> float:
        return self.at - self.clock.now()

    def check(self) -> float:
        left = self.remaining()
        if left <= 0:
            raise DeadlineReachedError
        return left


# ------------------------------------------------------------ 書き出し


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def record_line(obj: Mapping[str, Any]) -> str:
    """1 行 1 JSON。ensure_ascii=True で改行・U+2028 などを escape し、1 記録を必ず 1 行にする."""
    return json.dumps(dict(obj), ensure_ascii=True, sort_keys=True)


def _write_line(fh: TextIO, line: str) -> None:
    fh.write(line + "\n")
    fh.flush()
    os.fsync(fh.fileno())


def json_text(obj: object) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def write_json_durable(path: pathlib.Path, obj: object, *, exclusive: bool) -> bytes:
    """Temp → flush → fsync → replace。exclusive なら既存を上書きしない。書いた bytes を返す."""
    if exclusive and path.exists():
        msg = f"refusing to overwrite {path}"
        raise FileExistsError(msg)
    data = json_text(obj).encode("utf-8")
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(path)
    return data


def model_dirname(model: str) -> str:
    return model.replace(":", "_")


def segment_dir(
    stage_root: pathlib.Path, run_stage: str, seg: pl.Segment
) -> pathlib.Path:
    """``<run>/<stage>/<battery>/<model>``。stage と違う区切り (pilot の中の再生) は ``<seg.stage>/`` を挟む (DD-5)."""
    base = stage_root if seg.stage == run_stage else stage_root / seg.stage
    return base / seg.battery / model_dirname(seg.model)


def attempt_dir(seg_dir: pathlib.Path, attempt: int) -> pathlib.Path:
    return seg_dir / f"attempt-{attempt}"


def records_bytes(lines: Sequence[str]) -> bytes:
    return "".join(line + "\n" for line in lines).encode("ascii")


def prepare_stage_root(stage_root: pathlib.Path) -> None:
    """再開しない: 空でない ``<run>/<stage>`` では起動しない."""
    if stage_root.exists() and any(stage_root.iterdir()):
        msg = f"refusing to reuse a non-empty run dir {stage_root} (no resume)"
        raise PreflightError(msg)
    stage_root.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------ Ollama


@dataclass(frozen=True)
class Reply:
    content: str
    model: object
    done_reason: object
    prompt_eval_count: object
    eval_count: object


class TransportFailure(Exception):  # noqa: N818 — 再送の対象 (分類の名前)
    """1 回の送信が答えを返さなかった."""


async def send_chat(
    http: httpx.AsyncClient, body: dict[str, Any], timeout: float
) -> Reply:
    """1 回送る。transport 失敗は ``TransportFailure`` (それ以外の例外はそのまま上げる)."""
    try:
        response = await http.post(CHAT_PATH, json=body, timeout=timeout)
    except httpx.HTTPError as exc:
        msg = f"{type(exc).__name__}: {exc}"
        raise TransportFailure(msg) from exc
    if response.status_code != httpx.codes.OK:
        msg = f"HTTP {response.status_code}"
        raise TransportFailure(msg)
    try:
        payload = response.json()
    except ValueError as exc:
        msg = "non-JSON response"
        raise TransportFailure(msg) from exc
    message = payload.get("message") if isinstance(payload, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        msg = f"message.content is {type(content).__name__}, not a string"
        raise TransportFailure(msg)
    assert isinstance(payload, dict)
    return Reply(
        content,
        payload.get("model"),
        payload.get("done_reason"),
        payload.get("prompt_eval_count"),
        payload.get("eval_count"),
    )


def _ok_json(response: httpx.Response) -> object:
    if response.status_code != httpx.codes.OK:
        msg = f"{response.request.url.path} returned HTTP {response.status_code}"
        raise TransportFailure(msg)
    try:
        return response.json()
    except ValueError as exc:
        msg = f"{response.request.url.path} returned non-JSON"
        raise TransportFailure(msg) from exc


async def read_version(http: httpx.AsyncClient, timeout: float) -> str:
    try:
        payload = _ok_json(await http.get("/api/version", timeout=timeout))
    except httpx.HTTPError as exc:
        msg = f"{type(exc).__name__}: {exc}"
        raise TransportFailure(msg) from exc
    version = payload.get("version") if isinstance(payload, dict) else None
    if not isinstance(version, str) or not version:
        msg = "/api/version has no version"
        raise TransportFailure(msg)
    return version


def model_digest(tags: object, model: str) -> str | None:
    if not isinstance(tags, dict):
        return None
    for m in tags.get("models", []) or []:
        if isinstance(m, dict) and model in (m.get("name"), m.get("model")):
            digest = m.get("digest")
            return digest if isinstance(digest, str) and digest else None
    return None


@dataclass(frozen=True)
class Observed:
    ollama_version: str
    model_digest: str | None
    template: str | None

    @property
    def template_sha256(self) -> str | None:
        return None if self.template is None else sha256_text(self.template)


async def read_observed(
    http: httpx.AsyncClient, observer: ObservingTransport, model: str, timeout: float
) -> Observed:
    """区切りの開始時の同定: Ollama の版・``/api/tags`` の digest・``/api/show`` の template 全文."""
    version = await read_version(http, timeout)
    observer.allow_show = True
    try:
        tags = _ok_json(await http.get("/api/tags", timeout=timeout))
        show = _ok_json(
            await http.post(SHOW_PATH, json={"model": model}, timeout=timeout)
        )
    except httpx.HTTPError as exc:
        msg = f"{type(exc).__name__}: {exc}"
        raise TransportFailure(msg) from exc
    finally:
        observer.allow_show = False
    template = show.get("template") if isinstance(show, dict) else None
    return Observed(
        version,
        model_digest(tags, model),
        template if isinstance(template, str) else None,
    )


def load_reference(path: pathlib.Path = MODELS_JSON) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def meta_problems(obs: Observed, model: str, reference: Mapping[str, Any]) -> list[str]:
    """§A.1・§F-1: digest と template の sha が ``results/models.json`` と同じ (版は run 全体で別に見る)."""
    ref = reference.get("models", {}).get(model)
    if not isinstance(ref, dict):
        return [f"{model}: not in models.json"]
    out = []
    if obs.model_digest != ref.get("model_digest"):
        out.append(f"{model}: model_digest {obs.model_digest!r} differs")
    if obs.template_sha256 != ref.get("template_sha256"):
        out.append(f"{model}: template_sha256 {obs.template_sha256!r} differs")
    return out


def meta_for(
    seg: pl.Segment,
    attempt: int,
    obs: Observed,
    seg_digest: str,
    plan_digest: str,
) -> dict[str, Any]:
    """meta.json (区切りの attempt ごと、§A.1・DD-2)."""
    template_sha = obs.template_sha256
    return {
        "stage": seg.stage,
        "battery": seg.battery,
        "model": seg.model,
        "attempt": attempt,
        "n_calls": len(seg.calls),
        "ollama_version": obs.ollama_version,
        "model_digest": obs.model_digest,
        "template": obs.template,
        "template_sha256": template_sha,
        # DD-2: (template の sha, 区切りの digest) の組の sha
        "template_segment_sha256": sha256_bytes(
            json.dumps([template_sha, seg_digest], ensure_ascii=True).encode("ascii")
        ),
        "request": {
            "think": pl.THINK,
            "stream": False,
            "options_without_seed": dict(pl.DECODE),
        },
        "segment_digest": seg_digest,
        "plan_digest": plan_digest,
        "started_at": _now_iso(),
    }


# ------------------------------------------------------------ 実行


@dataclass
class SegmentState:
    status: str = S_NOT_STARTED
    reason: str | None = None
    adopted_attempt: int | None = None
    records_sha256: str | None = None
    meta_sha256: str | None = None
    attempts_run: int = 0

    def as_json(self, seg: pl.Segment, seg_digest: str) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "adopted_attempt": self.adopted_attempt,
            "records_sha256": self.records_sha256,
            "meta_sha256": self.meta_sha256,
            "n_calls": len(seg.calls),
            "segment_digest": seg_digest,
            "attempts_run": self.attempts_run,
        }


@dataclass
class Accounting:
    sends: dict[str, int] = field(default_factory=lambda: dict.fromkeys(CATEGORIES, 0))
    cost_8b_s: dict[str, Fraction] = field(
        default_factory=lambda: dict.fromkeys(CATEGORIES, Fraction(0))
    )

    def add(self, category: str, battery: str) -> None:
        self.sends[category] += 1
        self.cost_8b_s[category] += st.SPECS[battery].sec_per_call

    def as_json(self, stage: str, elapsed_s: float) -> dict[str, Any]:
        total = sum(self.cost_8b_s.values(), Fraction(0))
        return {
            "stage": stage,
            "sends": dict(self.sends),
            "sends_total": sum(self.sends.values()),
            "cost_8b_s": {k: str(v) for k, v in self.cost_8b_s.items()},
            "cost_8b_s_float": {k: float(v) for k, v in self.cost_8b_s.items()},
            "cost_8b_s_total": str(total),
            "cost_8b_h_total_float": float(total) / 3600.0,
            "elapsed_wall_s": elapsed_s,
        }


@dataclass
class Runner:
    run_stage: str
    stage_root: pathlib.Path
    segments: tuple[pl.Segment, ...]
    http: httpx.AsyncClient
    observer: ObservingTransport
    reference: Mapping[str, Any]
    deadline: Deadline
    clock: Clock
    timeout_s: float = TIMEOUT_S
    backoff_scale: float = 1.0
    states: dict[str, SegmentState] = field(default_factory=dict)
    digests: dict[str, str] = field(default_factory=dict)
    plan_digest: str = ""
    accounting: Accounting = field(default_factory=Accounting)
    versions_seen: set[str] = field(default_factory=set)
    started: float = 0.0

    def __post_init__(self) -> None:
        names = [s.name for s in self.segments]
        if len(set(names)) != len(names):
            msg = "segment names are not unique"
            raise ValueError(msg)
        self.digests = {s.name: pl.segment_digest(s) for s in self.segments}
        self.plan_digest = pl.plan_digest(self.segments)
        self.states = {s.name: SegmentState() for s in self.segments}

    # ---------------------------------------------------------- 状態表

    def table(self) -> dict[str, Any]:
        return {
            "run_stage": self.run_stage,
            "plan_digest": self.plan_digest,
            "expected_ollama_version": OLLAMA_VERSION,
            "segments": {
                s.name: self.states[s.name].as_json(s, self.digests[s.name])
                for s in self.segments
            },
            "order": [s.name for s in self.segments],
        }

    def save_partial(self) -> None:
        write_json_durable(
            self.stage_root / SEGMENTS_PARTIAL_NAME, self.table(), exclusive=False
        )

    def finish(self) -> dict[str, Any]:
        if any(v != OLLAMA_VERSION for v in self.versions_seen):
            seen = ", ".join(sorted(self.versions_seen))
            for state in self.states.values():
                state.status = S_INVALID_VERSION
                state.reason = f"Ollama version {seen} != {OLLAMA_VERSION} (§A.1)"
                state.adopted_attempt = None
        table = self.table()
        write_json_durable(self.stage_root / SEGMENTS_NAME, table, exclusive=True)
        (self.stage_root / SEGMENTS_PARTIAL_NAME).unlink(missing_ok=True)
        write_json_durable(
            self.stage_root / ACCOUNTING_NAME,
            self.accounting.as_json(self.run_stage, self.clock.now() - self.started),
            exclusive=True,
        )
        return table

    # ---------------------------------------------------------- 1 呼び出し

    def _category(self, seg: pl.Segment, attempt: int, send: int) -> str:
        if seg.stage == pl.STAGE_REPLAY:
            return C_REPLAY
        if attempt > 1:
            return C_RETRY
        return C_INITIAL if send == 0 else C_RESEND

    async def call_with_resend(
        self,
        seg: pl.Segment,
        attempt: int,
        index: int,
        spec: pl.CallSpec,
        attempts_fh: TextIO,
    ) -> tuple[Reply | None, int]:
        """同じ body を最大 1 + RESENDS 回送る。(応答 または None, 送信数)。期限は ``DeadlineReachedError``."""
        body = pl.body_for(spec, seg.model)
        self.observer.expected = (spec, seg.model)
        try:
            for send in range(1 + RESENDS):
                left = self.deadline.check()
                row: dict[str, Any] = {
                    "call_index": index,
                    "send": send,
                    "at": _now_iso(),
                }
                self.accounting.add(self._category(seg, attempt, send), seg.battery)
                try:
                    reply = await send_chat(self.http, body, min(self.timeout_s, left))
                except TransportFailure as exc:
                    row.update(outcome="transport_failure", error=str(exc))
                    _write_line(attempts_fh, record_line(row))
                    if self.deadline.remaining() <= 0:
                        raise DeadlineReachedError from exc
                    if send < RESENDS:
                        wait = BACKOFF_SCHEDULE_S[send] * self.backoff_scale
                        if wait >= self.deadline.remaining():
                            raise DeadlineReachedError from exc
                        await self.clock.sleep(wait)
                    continue
                row.update(
                    outcome="ok", model=reply.model, done_reason=reply.done_reason
                )
                _write_line(attempts_fh, record_line(row))
                return reply, send + 1
            return None, 1 + RESENDS
        finally:
            self.observer.expected = None

    def _row(
        self,
        seg: pl.Segment,
        attempt: int,
        index: int,
        spec: pl.CallSpec,
        reply: Reply | None,
        n_sends: int,
    ) -> dict[str, Any]:
        sent = self.observer.last_sent
        assert sent is not None
        return {
            "stage": seg.stage,
            "battery": seg.battery,
            "model": seg.model,
            "attempt": attempt,
            "call_index": index,
            "purpose": spec.purpose,
            "arm": spec.arm,
            "encoding": spec.encoding,
            "replicate": spec.replicate,
            "probe_id": spec.probe_id,
            "k": spec.k,
            "seed": sent["options"]["seed"],
            "prompt_sha256": pl.messages_sha256(sent["messages"]),
            "raw": None if reply is None else reply.content,
            "response_model": None if reply is None else reply.model,
            "prompt_eval_count": None if reply is None else reply.prompt_eval_count,
            "eval_count": None if reply is None else reply.eval_count,
            "done_reason": None if reply is None else reply.done_reason,
            "n_sends": n_sends,
        }

    # ---------------------------------------------------------- 1 区切り

    async def run_segment(self, seg: pl.Segment, attempt: int) -> None:
        state = self.states[seg.name]
        state.attempts_run = attempt
        state.adopted_attempt = None
        state.records_sha256 = state.meta_sha256 = None
        adir = attempt_dir(segment_dir(self.stage_root, self.run_stage, seg), attempt)
        adir.mkdir(parents=True, exist_ok=False)
        try:
            left = self.deadline.check()
            obs = await read_observed(
                self.http, self.observer, seg.model, min(self.timeout_s, left)
            )
        except DeadlineReachedError:
            state.status, state.reason = (
                S_TIMEOUT,
                f"attempt {attempt}: deadline before meta",
            )
            return
        except TransportFailure as exc:
            # 期限を過ぎた後の失敗 (timeout を期限で切った) は時間切れに数える
            state.status = S_TIMEOUT if self.deadline.remaining() <= 0 else S_TRANSPORT
            state.reason = f"attempt {attempt}: meta read: {exc}"
            return
        self.versions_seen.add(obs.ollama_version)
        meta = meta_for(seg, attempt, obs, self.digests[seg.name], self.plan_digest)
        meta_bytes = write_json_durable(adir / META_NAME, meta, exclusive=True)
        if obs.ollama_version != OLLAMA_VERSION:
            state.status = S_INVALID_VERSION
            state.reason = f"Ollama version {obs.ollama_version} != {OLLAMA_VERSION}"
            return
        problems = meta_problems(obs, seg.model, self.reference)
        if problems:
            state.status, state.reason = S_INVALID_META, "; ".join(problems)
            return
        lines: list[str] = []
        with (
            (adir / PARTIAL_NAME).open("x", encoding="ascii", newline="\n") as rec_fh,
            (adir / ATTEMPTS_NAME).open("x", encoding="ascii", newline="\n") as att_fh,
        ):
            for index, spec in enumerate(seg.calls):
                try:
                    reply, n_sends = await self.call_with_resend(
                        seg, attempt, index, spec, att_fh
                    )
                except DeadlineReachedError:
                    state.status = S_TIMEOUT
                    state.reason = f"attempt {attempt}: deadline at call {index}"
                    return
                line = record_line(self._row(seg, attempt, index, spec, reply, n_sends))
                _write_line(rec_fh, line)
                lines.append(line)
                if reply is None:
                    state.status = S_TRANSPORT
                    state.reason = (
                        f"attempt {attempt}: call {index} unresolved after "
                        f"{1 + RESENDS} sends"
                    )
                    return
        problems = publication_problems(adir, seg, attempt, lines, meta_bytes)
        if problems:
            msg = f"{seg.name}: publication check failed: " + "; ".join(problems)
            raise RuntimeError(msg)
        publish(adir)
        state.status, state.reason = S_COMPLETED, None
        state.adopted_attempt = attempt
        state.records_sha256 = sha256_bytes(records_bytes(lines))
        state.meta_sha256 = sha256_bytes(meta_bytes)

    async def run(self) -> dict[str, Any]:
        """§H の順: stage の区切り → 通信の欠測の再実行 (1 回) → 再生 (pilot の枠の最後)."""
        self.started = self.clock.now()
        main_segs = [s for s in self.segments if s.stage != pl.STAGE_REPLAY]
        replay_segs = [s for s in self.segments if s.stage == pl.STAGE_REPLAY]
        self.save_partial()
        try:
            await self._run_list(main_segs, attempt=1)
            retry = [s for s in main_segs if self.states[s.name].status == S_TRANSPORT]
            for seg in retry:
                why = self._stop_reason()
                if why is not None:
                    state = self.states[seg.name]
                    state.reason = f"{state.reason}; retry not started ({why})"
                    continue
                await self.run_segment(seg, attempt=MAX_ATTEMPTS)
                self.save_partial()
            await self._run_list(replay_segs, attempt=1)
        finally:
            self.save_partial()
        return self.finish()

    def _stop_reason(self) -> str | None:
        """新しい区切り (再実行を含む) を始めない理由。版の違いを見たら全区切りが invalid_version なので送らない."""
        if self.deadline.remaining() <= 0:
            return "deadline"
        if any(v != OLLAMA_VERSION for v in self.versions_seen):
            return "Ollama version mismatch seen"
        return None

    async def _run_list(self, segs: Sequence[pl.Segment], attempt: int) -> None:
        for seg in segs:
            why = self._stop_reason()
            if why is not None:
                self.states[seg.name].reason = f"{why} before start"
                continue  # S_NOT_STARTED のまま (版の違いは finish で invalid_version)
            await self.run_segment(seg, attempt)
            self.save_partial()


# ------------------------------------------------------------ 公開


def publication_problems(
    adir: pathlib.Path,
    seg: pl.Segment,
    attempt: int,
    lines: Sequence[str],
    meta_bytes: bytes,
) -> list[str]:
    """公開前: partial と meta.json が書いた bytes と同じで、LF で割った各行が区切りの呼び出しと順に一致する."""
    out: list[str] = []
    partial = (adir / PARTIAL_NAME).read_bytes()
    if partial != records_bytes(lines):
        out.append("partial differs from what this run wrote")
    if (adir / META_NAME).read_bytes() != meta_bytes:
        out.append("meta.json differs from what this run wrote")
    rows = partial.decode("ascii").split("\n")
    if rows[-1] != "":
        out.append("records do not end with LF")
    rows = rows[:-1]
    if len(rows) != len(seg.calls):
        out.append(f"{len(rows)} rows for {len(seg.calls)} calls")
        return out
    for index, (text, spec) in enumerate(zip(rows, seg.calls, strict=True)):
        row = json.loads(text)
        if set(row) != RECORD_KEYS:
            out.append(f"row {index}: keys differ")
            continue
        want = {
            "stage": seg.stage,
            "battery": seg.battery,
            "model": seg.model,
            "attempt": attempt,
            "call_index": index,
            "purpose": spec.purpose,
            "arm": spec.arm,
            "encoding": spec.encoding,
            "replicate": spec.replicate,
            "probe_id": spec.probe_id,
            "k": spec.k,
            "seed": spec.seed,
            "prompt_sha256": pl.messages_sha256(spec.messages_list()),
        }
        if not all(same(row[k], v) for k, v in want.items()):
            out.append(f"row {index}: key fields differ from the plan")
        if not isinstance(row["raw"], str):
            out.append(f"row {index}: raw is not a string")
    return out


def publish(adir: pathlib.Path) -> None:
    """Partial を公開名へ rename (commit point)。公開名が既にあれば上書きしない."""
    final = adir / RECORDS_NAME
    if final.exists():
        msg = f"refusing to overwrite {final}"
        raise FileExistsError(msg)
    (adir / PARTIAL_NAME).rename(final)


# ------------------------------------------------------------ 入口


async def run_stage(
    run_stage_name: str,
    run_dir: pathlib.Path,
    segments: Sequence[pl.Segment],
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    endpoint: str = DEFAULT_ENDPOINT,
    reference: Mapping[str, Any] | None = None,
    clock: Clock | None = None,
    deadline_s: float | None = None,
    backoff_scale: float = 1.0,
    timeout_s: float = TIMEOUT_S,
) -> dict[str, Any]:
    """1 stage を回して ``segments.json`` の中身を返す。segments は引数で受ける (test は小さい plan を渡す)."""
    if run_stage_name not in DEADLINE_S:
        msg = f"unknown stage {run_stage_name!r}"
        raise ValueError(msg)
    for seg in segments:
        if seg.stage not in (run_stage_name, pl.STAGE_REPLAY) or (
            seg.stage == pl.STAGE_REPLAY and run_stage_name != pl.STAGE_PILOT
        ):
            msg = f"segment {seg.name} does not belong to stage {run_stage_name}"
            raise ValueError(msg)
    clock = clock or Clock()
    stage_root = run_dir / run_stage_name
    prepare_stage_root(stage_root)
    observer = ObservingTransport(transport or httpx.AsyncHTTPTransport())
    async with httpx.AsyncClient(
        base_url=endpoint, transport=observer, timeout=timeout_s
    ) as http:
        try:
            version = await read_version(http, timeout_s)
        except TransportFailure as exc:
            msg = f"Ollama is not reachable: {exc}"
            raise PreflightError(msg) from exc
        runner = Runner(
            run_stage=run_stage_name,
            stage_root=stage_root,
            segments=tuple(segments),
            http=http,
            observer=observer,
            reference=reference if reference is not None else load_reference(),
            deadline=Deadline(
                clock,
                clock.now()
                + (DEADLINE_S[run_stage_name] if deadline_s is None else deadline_s),
            ),
            clock=clock,
            timeout_s=timeout_s,
            backoff_scale=backoff_scale,
        )
        if version != OLLAMA_VERSION:
            # §A.1: 版を混ぜない。chat を 1 件も送らず、全区切りを invalid_version で閉じる
            runner.started = clock.now()
            runner.versions_seen.add(version)
            for state in runner.states.values():
                state.reason = "not run"
            return runner.finish()
        return await runner.run()


GATE_SCHEMA: Final[str] = (
    "benchmark_stage2_pilot_gate/1"  # benchmark_stage2_pilot_gate.SCHEMA
)
GATE_NOT_QUALIFIED: Final[str] = st.VERDICT_NOT_QUALIFIED
GATE_NOT_COMPUTED: Final[str] = st.VERDICT_NOT_COMPUTED


@dataclass(frozen=True)
class MainGate:
    """gate.json (H5) から本走が使う値。entrants は battery ごとの pilot の入場集合 (§A.1 の順)."""

    r_by_battery: dict[str, int]  # GO の battery だけ
    entrants: dict[str, tuple[str, ...]]  # 全 battery
    k_tests: int
    sum_m: int


def _gate_error(msg: str) -> PreflightError:
    return PreflightError(f"gate.json: {msg}")


def read_gate(gate: Mapping[str, Any], models_json_sha256: str) -> MainGate:
    """gate.json の契約 (H5) を検査して読む。K・ΣM・予算の判定は入場数と R から再計算して照合する.

    入場は models の status、envelope は保存の ⊥ の数から復元して照合する (DD-12 H1)。
    ``models_json_sha256`` は本走が使う models.json の sha (gate が同じ models.json から作られたか、M1)。
    """
    if gate.get("schema") != GATE_SCHEMA or gate.get("status") != "OK":
        raise _gate_error("schema or status is not an OK pilot gate")
    inputs = gate.get("inputs")
    if (
        not isinstance(inputs, dict)
        or inputs.get("models_json_sha256") != models_json_sha256
    ):
        raise _gate_error("models_json_sha256 differs from the models.json in use")
    batteries = gate.get("batteries")
    if not isinstance(batteries, dict) or set(batteries) != set(st.BATTERIES):
        raise _gate_error("batteries differ from the registered 4")
    entrants: dict[str, tuple[str, ...]] = {}
    r_all: dict[str, int] = {}
    labels: dict[str, str] = {}
    for name in st.BATTERIES:
        entry = batteries[name]
        if not isinstance(entry, dict):
            raise _gate_error(f"{name}: entry is not an object")
        models = entry.get("models")
        if not isinstance(models, dict):
            raise _gate_error(f"{name}: models is not an object")
        ent = entry.get("entrants")
        entered = [
            m
            for m in pl.MODELS
            if isinstance(models.get(m), dict) and models[m].get("status") == st.ENTERED
        ]
        if ent != entered or not _same_int(entry.get("n_entered"), len(entered)):
            raise _gate_error(f"{name}: entrants differ from the entered models")
        entrants[name] = tuple(entered)
        label = entry.get("gate")
        r = entry.get("R")
        qualified = len(ent) >= st.MIN_ENTRANTS
        if label in (st.GATE_GO, st.GATE_HELD_COST):
            if (
                not qualified
                or type(r) is not int
                or r not in st.r_candidates(st.SPECS[name])
            ):
                raise _gate_error(f"{name}: R {r!r} is not a registered candidate")
            r_all[name] = r
            labels[name] = label
        elif label == st.GATE_STOP_POWER:
            if not qualified or r is not None:
                raise _gate_error(f"{name}: STOP_POWER needs >= 3 entrants and no R")
        elif label in (GATE_NOT_QUALIFIED, GATE_NOT_COMPUTED):
            if qualified or r is not None:
                raise _gate_error(f"{name}: {label} with >= 3 entrants or an R")
        else:
            raise _gate_error(f"{name}: unknown gate {label!r}")
        for m in entered:
            env = models[m].get("envelope")
            counts = models[m].get("bot_counts")
            n_bot = models[m].get("bot_n")
            if (
                not isinstance(env, dict)
                or type(env.get("numerator")) is not int
                or type(env.get("denominator")) is not int
                or env["denominator"] <= 0
            ):
                raise _gate_error(f"{name}/{m}: envelope is not an integer fraction")
            # ⊥ の数: 登録の arm の数の [0, bot_n] の整数・入場なら parse の規則を通る (DD-12 H1)
            if not isinstance(counts, list):
                raise _gate_error(f"{name}/{m}: bot_counts is not a list")
            if len(counts) != st.N_ARMS[name]:
                raise _gate_error(f"{name}/{m}: bot_counts differ from the arms")
            if type(n_bot) is not int or n_bot <= 0:
                raise _gate_error(f"{name}/{m}: bot_n is not a positive integer")
            if not all(type(k) is int for k in counts):
                raise _gate_error(f"{name}/{m}: bot_counts are not integers")
            if not all(0 <= k <= n_bot for k in counts):
                raise _gate_error(f"{name}/{m}: bot_counts are outside [0, bot_n]")
            parse_ok, want_env = st.parse_rule(counts, n_bot)
            if not parse_ok:
                raise _gate_error(f"{name}/{m}: entered but fails the parse rule")
            if Fraction(env["numerator"], env["denominator"]) != want_env:
                raise _gate_error(f"{name}/{m}: envelope differs from the bot counts")
    n_entered = {b: len(e) for b, e in entrants.items()}
    k_tests = st.n_tests(n_entered)
    sum_m = sum(n for n in n_entered.values() if n >= st.MIN_ENTRANTS)
    if not _same_int(gate.get("K"), k_tests) or not _same_int(gate.get("sum_M"), sum_m):
        raise _gate_error("K or sum_M differs from the entrants")
    if st.budget(r_all) != labels:
        raise _gate_error("GO / HELD_COST differ from the budget rule")
    r_go = {b: r for b, r in r_all.items() if labels[b] == st.GATE_GO}
    if not r_go:
        raise _gate_error("no GO battery")
    return MainGate(r_go, entrants, k_tests, sum_m)


def _same_int(got: object, want: int) -> bool:
    return type(got) is int and got == want


def main_r_from_gate(
    gate: Mapping[str, Any], models_json_sha256: str
) -> dict[str, int]:
    """gate.json から本走の R (GO の battery だけ)."""
    return read_gate(gate, models_json_sha256).r_by_battery


def plan_for(
    stage: str,
    gate_path: pathlib.Path | None,
    models_path: pathlib.Path = MODELS_JSON,
    *,
    root: pathlib.Path = _REPO_ROOT,
    models_bytes: bytes | None = None,
) -> tuple[pl.Segment, ...]:
    """区切りの plan。本走は gate.json を、本走が照合に使う models.json の sha と結んで読む.

    本走は送信の前に第 2 段の封印 ``manifest_main.json`` を照合し (DD-12 H2)、実 R の
    ``battery_checks`` を計算し直して記録と一致することを要求する。``models_bytes`` を渡すと
    ``models_path`` を読まずにその bytes を照合する (CLI は送信にも同じ bytes を使う)。
    """
    if stage == pl.STAGE_PILOT:
        return pl.pilot_plan()
    if gate_path is None:
        msg = "--stage main requires --gate"
        raise PreflightError(msg)
    gate_bytes = gate_path.read_bytes()
    if models_bytes is None:
        models_bytes = models_path.read_bytes()
    models_sha = sha256_bytes(models_bytes)
    gate = read_gate(json.loads(gate_bytes.decode("utf-8")), models_sha)
    try:
        rec = mm.require(root, gate_bytes=gate_bytes, models_sha=models_sha)
    except mm.ManifestError as exc:
        msg = f"manifest_main: {exc}"
        raise PreflightError(msg) from exc
    recorded = {b: e["checks"] for b, e in rec["battery_checks"].items()}
    if {b: pl.battery_checks(b, r) for b, r in gate.r_by_battery.items()} != recorded:
        msg = "manifest_main: battery_checks differ from the recomputation"
        raise PreflightError(msg)
    segs = pl.main_plan(gate.r_by_battery, gate.entrants)
    # 報告集合 ⊆ 入場集合: 本走は pilot の入場モデルだけを回す
    if any(s.model not in gate.entrants[s.battery] for s in segs):
        msg = "main plan has a model outside the pilot entrants"
        raise PreflightError(msg)
    return segs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stage", choices=(pl.STAGE_PILOT, pl.STAGE_MAIN), required=True)
    ap.add_argument("--run-dir", type=pathlib.Path, required=True)
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    ap.add_argument("--gate", type=pathlib.Path, default=None)
    args = ap.parse_args(argv)
    try:
        # models.json は 1 回だけ読み、照合 (plan_for) と送信時の参照 (run_stage) に同じ bytes を使う
        try:
            models_bytes = MODELS_JSON.read_bytes()
        except OSError as exc:
            msg = f"models.json: {exc}"
            raise PreflightError(msg) from exc
        segments = plan_for(args.stage, args.gate, models_bytes=models_bytes)
        table = asyncio.run(
            run_stage(
                args.stage,
                args.run_dir,
                segments,
                endpoint=args.endpoint,
                reference=json.loads(models_bytes.decode("utf-8")),
            )
        )
    except PreflightError as exc:
        print(f"[driver] refused: {exc}", file=sys.stderr)  # noqa: T201
        return EXIT_REFUSED
    statuses = [v["status"] for v in table["segments"].values()]
    print(  # noqa: T201
        "[driver] "
        + ", ".join(f"{s}={statuses.count(s)}" for s in sorted(set(statuses)))
    )
    return EXIT_OK if all(s == S_COMPLETED for s in statuses) else EXIT_INCOMPLETE


if __name__ == "__main__":
    raise SystemExit(main())
