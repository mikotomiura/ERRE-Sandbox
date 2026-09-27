#!/usr/bin/env python
"""閉ループ分散 pilot — 実走 driver (prereg v4 §2.2〜2.4 / §4 / §8)。

凍結 v4 battery の renderer (``loop_messages`` / ``probe_messages`` / ``c0_messages``)・成否の更新 (``update``) と、
凍結 v4 scorer の呼び出し plan (``frozen_plan``)・seed (``expected_seed``)・``parse_choice``・連鎖 replay
(``chain_violations``) をそのまま使い、``OllamaChatClient`` 経由で qwen3:8b を **逐次** に呼ぶ。自由度は足さない。
v3 driver (``scripts/skill_experience_driver.py``、判断 DE-R0〜R9) の運用を継承し、閉ループ用の自己完結コピー
として置く (v3 driver は import しない。判定に関わる行を全て本ファイルに置き、driver 変異試験で壊せるように
するため。判断記録 = ``.steering/20260928-closed-loop-pilot-run/decisions.md`` DR-1〜、データを見る前に commit):

* **閉ループ** (prereg v4 §2.4 の driver 要件)。prompt t+1 は outcome t に依存するので body を事前計算できない。
  driver は、書き出した行を厳密 reader (``record_from_json``) で読み戻した Record の ``parsed`` から
  ``bat.update`` で (世界, r) ごとの状態を進め、``loop_messages`` で次の body を作る。成否は記録しない
  (scorer が連鎖 replay で導出する)。
* **送った body の照合** (DR-1)。``ObservingTransport`` が送信 **前** に wire body を読み、model / think / stream /
  options (値と型) を凍結値と照合する。さらに、送ろうとする body から候補 Record を作り、記録済みの同じ
  (世界, r) の loop 行に並べて **凍結 scorer の** ``chain_violations`` に通す。key は ``frozen_plan()[i]``、
  seed は ``expected_seed``。判定で拒否される body は送れない。外れたら送らずに停止する (aborted)。
* **順序** (prereg v4 §2.4)。``frozen_plan()`` をそのまま上から呼ぶ (call_index = plan の位置)。C0 の 240 件
  → C0 ⊥ 率 > ``BOT_MAX`` なら状態側を走らせず停止 (DR-4) → ループ段・probe 段・replay。ループ段の ⊥ では
  止まらない (DR-3、判定は evaluate だけが行う)。
* **replay** は、元の呼び出しで送った messages と同じ seed をそのまま送る (描き直さない)。
* **transport 失敗** = ``OllamaUnavailableError`` 全般と、応答の message.content が文字列でない場合。
  同じ seed・同じ messages で最大 3 回再送 (送信は計 4 回)。解けなければ ``raw = null`` の行を書いて停止する
  (⊥ にしない)。それ以外の例外は行を書かずに停止する。
* **再開しない**・**meta.json は送った body の観測値から**・**来歴は provenance.json / attempts.jsonl**・
  **起動の前提** (driver certification・固定ファイルが HEAD と一致・凍結 v2 / v3 / v4 manifest が OK)・
  **preflight** (Ollama の応答・凍結 model の digest、run dir を作る前)・**来歴の異常は aborted** は v3 と同じ。
* **判定の読み方**。``provenance.json`` が無い、または ``exit_reason`` が completed / c0_gate 以外の run は
  not_computed。``scripts/closed_loop_run_gate.py`` が機械的に検査し、``scripts/closed_loop_judge.py`` が
  run.sh の前に必ず通す (不合格なら run.sh を呼ばない)。
* **やり直し** (DR-6)。provenance が無い・transport_failure・aborted の run だけ、records を開かずに
  user 裁定で退避してやり直せる (最大 2 回)。completed / c0_gate の run はやり直さない。

実行 (repo root から、GPU 実走は user 裁定の後)。run dir (``results/run``) と endpoint は固定で引数を取らない
(登録外の実走経路を閉じる、DR-6 / DR-7)::

    uv run python scripts/closed_loop_driver.py
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import functools
import hashlib
import json
import os
import pathlib
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final, TextIO

import httpx

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import closed_loop_battery as bat  # noqa: E402
from scripts import closed_loop_scorer as sc  # noqa: E402
from scripts import skill_lever_battery as v2bat  # noqa: E402
from scripts.skill_lever_scorer import bottom_rates, messages_sha256  # noqa: E402

from erre_sandbox.inference.ollama_adapter import (  # noqa: E402
    ChatMessage,
    ChatResponse,
    OllamaChatClient,
    OllamaUnavailableError,
)
from erre_sandbox.inference.sampling import ResolvedSampling  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Sequence

_EXP_DIR: Final[pathlib.Path] = (
    _REPO_ROOT / "experiments" / "20260927-closed-loop-divergence-pilot"
)
DEFAULT_RUN_DIR: Final[pathlib.Path] = _EXP_DIR / "results" / "run"
DEFAULT_ENDPOINT: Final[str] = "http://127.0.0.1:11434"
_MANIFEST: Final[pathlib.Path] = _EXP_DIR / "manifest.json"
RECORDS_NAME: Final[str] = "records.jsonl"

RESENDS: Final[int] = 3  # 同じ seed での再送回数 (送信は初回と合わせて最大 4 回)
# 再送の待ち (秒)。attempt ごとに延ばす (Ollama の再起動・復帰を待つ。登録外・label と独立、DR-7)
BACKOFF_SCHEDULE_S: Final[tuple[float, ...]] = (5.0, 30.0, 120.0)
TIMEOUT_S: Final[float] = 300.0  # モデルの再ロードで adapter 既定の 60 秒を超えうる

REASON_COMPLETED: Final[str] = "completed"
REASON_C0_GATE: Final[str] = "c0_gate"
REASON_TRANSPORT: Final[str] = "transport_failure"
REASON_ABORTED: Final[str] = "aborted"
EXIT_CODES: Final[dict[str, int]] = {
    REASON_COMPLETED: 0,
    REASON_C0_GATE: 0,  # 凍結 rule どおりの停止 (判定は INVALID_TASK_BATTERY)
    REASON_TRANSPORT: 3,
    REASON_ABORTED: 4,
}

# 送る要求 (凍結 v2 battery の定数から。送った値は ObservingTransport が照合する)
SAMPLING: Final[ResolvedSampling] = ResolvedSampling(
    temperature=v2bat.TEMPERATURE,
    top_p=v2bat.TOP_P,
    repeat_penalty=v2bat.REPEAT_PENALTY,
)
BODY_KEYS: Final[frozenset[str]] = frozenset(
    {"model", "messages", "stream", "options", "think"}
)
OPTION_KEYS: Final[frozenset[str]] = frozenset(
    {"seed", "num_ctx", "num_predict", "temperature", "top_p", "repeat_penalty"}
)

Key = bat.PlanKey
Slot = tuple[str, str, int, int | None, str | None, int | None]  # PlanKey の of 以外
Chain = tuple[str, int]  # (world, replicate)


def slot(key: Key) -> Slot:
    """呼び出しの識別 (replay は ``of`` を除いた自分の欄)."""
    return (key.phase, key.world, key.replicate, key.step, key.probe_id, key.k)


@functools.cache
def _plan() -> tuple[Key, ...]:
    """凍結 plan (``sc.frozen_plan()``) を 1 回だけ作る (tuple なので書き換えられない)."""
    return tuple(sc.frozen_plan())


@functools.cache
def _qidx(probe_id: str) -> int:
    return [p.probe_id for p in v2bat.lever_probes()].index(probe_id)


# ------------------------------------------------------ 送った body の照合


class SentBodyMismatchError(RuntimeError):
    """送ろうとした body が凍結要求と違う。httpx 例外でないので adapter に包まれず、再送もされない."""


def _exact(got: object, want: object) -> bool:
    """型まで一致 (False == 0、4096.0 == 4096 を通さない)."""
    return type(got) is type(want) and got == want


@dataclass(frozen=True)
class Expected:
    """送信前照合の入力: plan 上の位置と、連鎖 replay に並べる記録済みの行 (oracle の文脈)."""

    index: int
    context: tuple[sc.Record, ...]


def check_sent_body(body: object, expected: Expected) -> None:
    """送信前の wire body を凍結値と凍結 scorer の連鎖 replay で照合する。外れたら ``SentBodyMismatchError``."""
    want_key = _plan()[expected.index]
    where = f"call {expected.index} {slot(want_key)}"
    if not isinstance(body, dict) or set(body) != BODY_KEYS:
        msg = f"{where}: body keys differ from {sorted(BODY_KEYS)}"
        raise SentBodyMismatchError(msg)
    problems: list[str] = []
    if not _exact(body["model"], v2bat.MODEL):
        problems.append(f"model={body['model']!r}")
    if not _exact(body["think"], v2bat.THINK):
        problems.append(f"think={body['think']!r}")
    if not _exact(body["stream"], False):
        problems.append(f"stream={body['stream']!r}")
    opts = body["options"]
    if not isinstance(opts, dict) or set(opts) != OPTION_KEYS:
        msg = f"{where}: options keys differ from {sorted(OPTION_KEYS)}"
        raise SentBodyMismatchError(msg)
    want = {
        "seed": sc.expected_seed(want_key),
        "num_ctx": v2bat.NUM_CTX,
        "num_predict": v2bat.NUM_PREDICT,
        "temperature": v2bat.TEMPERATURE,
        "top_p": v2bat.TOP_P,
        "repeat_penalty": v2bat.REPEAT_PENALTY,
    }
    problems.extend(
        f"options.{name}={opts[name]!r} (want {value!r})"
        for name, value in want.items()
        if not _exact(opts[name], value)
    )
    if not problems:
        cand = sc.Record(
            call_index=expected.index,
            phase=want_key.phase,
            world=want_key.world,
            replicate=want_key.replicate,
            step=want_key.step,
            probe_id=want_key.probe_id,
            k=want_key.k,
            seed=opts["seed"],
            prompt_sha256=messages_sha256(body["messages"]),
            raw=None,
            parsed=None,
        )
        chain = sc.chain_violations([*expected.context, cand])
        if chain:
            problems.append(f"messages differ from the frozen chain replay: {chain}")
    if problems:
        msg = f"{where}: " + "; ".join(problems)
        raise SentBodyMismatchError(msg)


def meta_of(body: dict[str, Any]) -> dict[str, Any]:
    """送った body 1 つから ``request_meta()`` と同じ形の要求条件を読む."""
    opts = body["options"]
    return {
        "model": body["model"],
        "think": body["think"],
        "temperature": opts["temperature"],
        "top_p": opts["top_p"],
        "repeat_penalty": opts["repeat_penalty"],
        "num_ctx": opts["num_ctx"],
        "num_predict": opts["num_predict"],
    }


def observed_meta(bodies: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """送った全 body の要求条件が 1 種類 (値と型) であることを確かめ、その値を返す."""
    metas = {json.dumps(meta_of(b), sort_keys=True) for b in bodies}
    if len(metas) != 1:
        msg = f"sent request conditions are not uniform across the run: {sorted(metas)}"
        raise SentBodyMismatchError(msg)
    return json.loads(next(iter(metas)))


def meta_matches_frozen(meta: dict[str, Any]) -> bool:
    want = sc.request_meta()
    return set(meta) == set(want) and all(_exact(meta[n], v) for n, v in want.items())


class ObservingTransport(httpx.AsyncBaseTransport):
    """inner transport を包み、POST の body を送信前に照合・記録する.

    POST は /api/chat 以外を通さない (prefix 付き endpoint 等で照合をすり抜けない)。
    """

    def __init__(self, inner: httpx.AsyncBaseTransport) -> None:
        self.inner = inner
        self.expected: Expected | None = None
        self.sent: list[dict[str, Any]] = []
        self.last_content_type: str | None = None

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        is_post = request.method == "POST"
        if is_post:
            if request.url.path != "/api/chat":
                msg = f"unexpected POST path {request.url.path!r}"
                raise SentBodyMismatchError(msg)
            if self.expected is None:
                msg = "chat request without an expected call"
                raise SentBodyMismatchError(msg)
            body = json.loads(request.content)
            check_sent_body(body, self.expected)
            self.sent.append(body)
            self.last_content_type = None
        response = await self.inner.handle_async_request(request)
        if is_post:
            await response.aread()
            self.last_content_type = _content_type(response)
        return response

    async def aclose(self) -> None:
        await self.inner.aclose()


def _content_type(response: httpx.Response) -> str | None:
    """応答 JSON 上の message.content の型 (adapter は str() するので null が "None" になる)."""
    try:
        payload = response.json()
        return type(payload["message"]["content"]).__name__
    except (ValueError, KeyError, TypeError):
        return None


# ------------------------------------------------------------ preflight


class PreflightError(RuntimeError):
    """Ollama / model が使えない。run dir を作る前に止まる (ラベルを 1 件も観測しない)."""


def _model_digest(tags: object) -> str | None:
    if not isinstance(tags, dict):
        return None
    for m in tags.get("models", []):
        if isinstance(m, dict) and v2bat.MODEL in (m.get("name"), m.get("model")):
            digest = m.get("digest")
            return digest if isinstance(digest, str) and digest else None
    return None


async def preflight(http: httpx.AsyncClient) -> dict[str, str]:
    """/api/version が応答し、/api/tags に凍結 model があり digest が取れること."""
    try:
        version = (await http.get("/api/version")).json()["version"]
        digest = _model_digest((await http.get("/api/tags")).json())
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        msg = f"Ollama is not reachable: {type(exc).__name__}: {exc}"
        raise PreflightError(msg) from exc
    if digest is None:
        msg = f"model {v2bat.MODEL!r} is not available (no digest in /api/tags)"
        raise PreflightError(msg)
    return {"ollama_version": str(version), "model_digest": digest}


# ------------------------------------------------------------------- run


@dataclass
class RunState:
    run_dir: pathlib.Path
    records_fh: TextIO
    attempts_fh: TextIO
    observer: ObservingTransport
    llm: OllamaChatClient
    backoff_scale: float
    records: list[sc.Record] = field(default_factory=list)
    # 組み立て側: 読み戻した記録から進める (世界, r) ごとの状態
    states: dict[Chain, bat.State] = field(default_factory=dict)
    # 照合側 (oracle の文脈): 記録済みの loop 行と、呼び出しごとの記録
    loops: dict[Chain, list[sc.Record]] = field(default_factory=dict)
    by_slot: dict[Slot, sc.Record] = field(default_factory=dict)
    # replay 用: 元の呼び出しで送った messages
    sent_messages: dict[Slot, list[dict[str, str]]] = field(default_factory=dict)
    response_models: set[str] = field(default_factory=set)
    n_length: int = 0
    resends: int = 0
    meta_written: bool = False


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _write_line(fh: TextIO, obj: dict[str, Any]) -> str:
    """1 行 1 JSON。ensure_ascii=True: U+2028 / U+2029 / U+0085 を escape し、凍結 evaluate の
    ``splitlines()`` で 1 記録が 2 行に割れないようにする (DR-7、CR HIGH).
    """
    line = json.dumps(obj, ensure_ascii=True, sort_keys=True)
    fh.write(line + "\n")
    fh.flush()
    os.fsync(fh.fileno())
    return line


def write_json_durable(path: pathlib.Path, obj: object, *, exclusive: bool) -> None:
    """Temp → flush → fsync → replace。exclusive なら既存ファイルを上書きしない."""
    if exclusive and path.exists():
        msg = f"refusing to overwrite {path}"
        raise FileExistsError(msg)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(path)


def _ensure_meta(state: RunState) -> None:
    """最初に照合を通って送った body の要求条件で meta.json を書く (kill されても残る)."""
    if state.meta_written or not state.observer.sent:
        return
    write_json_durable(
        state.run_dir / "meta.json",
        meta_of(state.observer.sent[0]),
        exclusive=True,
    )
    state.meta_written = True


def _chain_of(key: Key) -> Chain:
    return (key.world, key.replicate)


def request_for(
    key: Key, state: RunState
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """組み立て側: 送る messages と options (状態は読み戻した記録から進めた accumulator)."""
    if key.phase == bat.PHASE_REPLAY:
        assert key.of is not None
        msgs = state.sent_messages[slot(key.of)]
    elif key.phase == bat.PHASE_C0:
        assert key.probe_id is not None
        msgs = bat.c0_messages(key.replicate, _qidx(key.probe_id))
    elif key.phase == bat.PHASE_LOOP:
        assert key.step is not None
        st = state.states.get(_chain_of(key), bat.EMPTY_STATE)
        msgs = bat.loop_messages(
            st, key.world, key.replicate, key.step, sc.FROZEN_RENDERER
        )
    else:
        assert key.probe_id is not None
        st = state.states.get(_chain_of(key), bat.EMPTY_STATE)
        msgs = bat.probe_messages(
            st, key.world, key.replicate, _qidx(key.probe_id), sc.FROZEN_RENDERER
        )
    options = {
        "seed": sc.expected_seed(key),
        "num_ctx": v2bat.NUM_CTX,
        "num_predict": v2bat.NUM_PREDICT,
    }
    return msgs, options


def oracle_context(key: Key, state: RunState) -> tuple[sc.Record, ...]:
    """照合側: 候補の前に並べる記録済みの行 (同じ (世界, r) の loop 行 + replay の元の行)."""
    if key.phase == bat.PHASE_C0:
        return ()
    target = key.of if key.phase == bat.PHASE_REPLAY else key
    assert target is not None
    rows = list(state.loops.get(_chain_of(target), []))
    if key.phase == bat.PHASE_REPLAY and target.phase != bat.PHASE_LOOP:
        rows.append(state.by_slot[slot(target)])
    return tuple(rows)


async def call_with_resend(
    state: RunState, index: int, key: Key
) -> tuple[str | None, dict[str, Any]]:
    """同じ要求を最大 1 + RESENDS 回送る。返り値 = (content または None, 最後に送った body).

    ``OllamaUnavailableError`` と、応答の message.content が文字列でない (adapter が str() で
    "None" 等にしてしまう) 場合を transport 失敗として再送する。
    """
    msgs, options = request_for(key, state)
    messages = [ChatMessage(**m) for m in msgs]
    state.observer.expected = Expected(index, oracle_context(key, state))
    for attempt in range(1 + RESENDS):
        row: dict[str, Any] = {"call_index": index, "attempt": attempt, "at": _now()}
        resp: ChatResponse | None
        try:
            resp = await state.llm.chat(
                messages, sampling=SAMPLING, options=dict(options), think=v2bat.THINK
            )
        except OllamaUnavailableError as exc:
            row.update(outcome="transport_failure", error=str(exc))
            resp = None
        else:
            ctype = state.observer.last_content_type
            row.update(
                model=resp.model,
                eval_count=resp.eval_count,
                prompt_eval_count=resp.prompt_eval_count,
                finish_reason=resp.finish_reason,
                content_type=ctype,
            )
            if ctype != "str":
                row.update(outcome="transport_failure", error="non-string content")
                resp = None
            else:
                row.update(outcome="ok")
        _ensure_meta(state)
        _write_line(state.attempts_fh, row)
        if resp is not None:
            state.response_models.add(resp.model)
            state.n_length += resp.finish_reason == "length"
            return resp.content, state.observer.sent[-1]
        if attempt < RESENDS:
            state.resends += 1
            await asyncio.sleep(BACKOFF_SCHEDULE_S[attempt] * state.backoff_scale)
    return None, state.observer.sent[-1]


def absorb(state: RunState, line: str, body: dict[str, Any]) -> sc.Record:
    """書き出した行を、凍結 evaluate と同じ経路 (``splitlines`` → ``load_records``) で読み戻し、
    その Record から状態と oracle の文脈を進める。1 行が 1 記録にならなければ止まる.
    """
    rows = sc.load_records((line + "\n").splitlines())
    if len(rows) != 1:
        msg = f"written line does not read back as one record ({len(rows)})"
        raise RuntimeError(msg)
    rec = rows[0]
    state.records.append(rec)
    state.by_slot[slot(rec.key())] = rec
    if rec.phase != bat.PHASE_REPLAY:
        state.sent_messages[slot(rec.key())] = body["messages"]
    if rec.phase == bat.PHASE_LOOP:
        assert rec.step is not None
        chain = (rec.world, rec.replicate)
        state.loops.setdefault(chain, []).append(rec)
        state.states[chain] = bat.update(
            state.states.get(chain, bat.EMPTY_STATE),
            rec.world,
            bat.loop_signature(rec.replicate, rec.step),
            rec.parsed,
        )
    return rec


async def run_calls(state: RunState, start: int, keys: Sequence[Key]) -> str | None:
    """plan[start:] の keys を順に呼ぶ。transport 失敗が解けなければ raw=null を書いて REASON_TRANSPORT."""
    for offset, key in enumerate(keys):
        index = start + offset
        raw, body = await call_with_resend(state, index, key)
        rec = sc.Record(
            call_index=index,
            phase=key.phase,
            world=key.world,
            replicate=key.replicate,
            step=key.step,
            probe_id=key.probe_id,
            k=key.k,
            seed=body["options"]["seed"],
            prompt_sha256=messages_sha256(body["messages"]),
            raw=raw,
            parsed=None if raw is None else sc.parse_choice(raw),
        )
        line = _write_line(state.records_fh, dataclasses.asdict(rec))
        absorb(state, line, body)
        if (index + 1) % 50 == 0:
            _progress(f"[driver] {index + 1} calls ({_now()})")
        if raw is None:
            return REASON_TRANSPORT
    return None


def _progress(line: str) -> None:
    """進捗表示。stdout が使えない (detached 起動で閉じたハンドル等) ことで run を止めない."""
    try:
        print(line, flush=True)
    except (OSError, ValueError):
        pass


def c0_bottom_rate(records: Sequence[sc.Record]) -> float:
    """判定と同じ式 (``probe_choices`` → ``bottom_rates``) で C0 の ⊥ 率 (C0 の全 key が揃っている前提).

    phase の filter は防御にすぎない (``bottom_rates`` は C0 の key しか読まないので、外しても値は同じ)。
    """
    c0 = [x for x in records if x.phase == bat.PHASE_C0]
    return float(bottom_rates(sc.probe_choices(c0), (bat.ARM_C0,), sc.FROZEN_R)[0])


def prepare_run_dir(run_dir: pathlib.Path) -> None:
    """再開しない: 既に何かがある dir では起動しない."""
    if run_dir.exists() and any(run_dir.iterdir()):
        msg = f"run dir is not empty (no resume): {run_dir}"
        raise FileExistsError(msg)
    run_dir.mkdir(parents=True, exist_ok=True)


def _sha256(path: pathlib.Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _git(*args: str) -> str | None:
    """Git の stdout。実行できなければ None (「clean」に畳まない)."""
    try:
        proc = subprocess.run(  # noqa: S603
            ["git", *args],  # noqa: S607
            cwd=str(_REPO_ROOT),
            capture_output=True,
            encoding="utf-8",
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return proc.stdout.strip()


def git_dirty() -> bool | None:
    """作業木に未 commit の変更 (untracked を含む) があるか。git が使えなければ None."""
    out = _git("status", "--porcelain")
    return None if out is None else bool(out)


# 実走前に commit 済みで HEAD と一致していなければならないファイル
PINNED: Final[tuple[str, ...]] = (
    "scripts/closed_loop_driver.py",
    "scripts/closed_loop_describe.py",
    "scripts/closed_loop_run_gate.py",
    "scripts/closed_loop_driver_mutation_check.py",
    "scripts/closed_loop_judge.py",
    "scripts/closed_loop_evaluate.py",
    "scripts/closed_loop_manifest.py",
    "scripts/closed_loop_battery.py",
    "scripts/closed_loop_scorer.py",
    "scripts/closed_loop_sim.py",
    "scripts/skill_lever_manifest.py",
    "scripts/skill_experience_manifest.py",
    "scripts/skill_lever_battery.py",
    "scripts/skill_lever_scorer.py",
    "scripts/stage_b_battery.py",
    "scripts/stage_b_scorer.py",
    "src/erre_sandbox/inference/ollama_adapter.py",
    "src/erre_sandbox/inference/sampling.py",
    "experiments/20260927-closed-loop-divergence-pilot/manifest.json",
    "experiments/20260927-closed-loop-divergence-pilot/prereg.md",
    "experiments/20260927-closed-loop-divergence-pilot/run.sh",
    "experiments/20260927-closed-loop-divergence-pilot/SEED",
    "experiments/20260927-closed-loop-divergence-pilot/results/v4_mutation.json",
    "experiments/20260926-skill-lever-pilot/manifest.json",
    "experiments/20260926-experience-skill-pilot/manifest.json",
    "experiments/20260927-closed-loop-divergence-pilot/results/driver_mutation.json",
)
DRIVER_CERT: Final[pathlib.Path] = _EXP_DIR / "results" / "driver_mutation.json"
_DRIVER_TESTS: Final[pathlib.Path] = _REPO_ROOT / "tests" / "test_closed_loop_driver"
# 判定 (run.sh) が照合する凍結 manifest と、v4 manifest が import する v3 の凍結。実走前にも照合し、
# 判定で拒否される run に GPU を使わない
MANIFEST_CHECKS: Final[tuple[str, ...]] = (
    "scripts/skill_lever_manifest.py",
    "scripts/skill_experience_manifest.py",
    "scripts/closed_loop_manifest.py",
)


CERTIFIED_SCRIPTS: Final[tuple[str, ...]] = (
    "closed_loop_driver.py",
    "closed_loop_describe.py",
    "closed_loop_run_gate.py",
    "closed_loop_driver_mutation_check.py",
    "closed_loop_judge.py",
)


def certified_files() -> dict[str, str | None]:
    """Driver 変異試験の certification が結び付くファイルの sha256 (変異対象・harness・test)."""
    here = pathlib.Path(__file__).resolve().parent
    out = {name: _sha256(here / name) for name in CERTIFIED_SCRIPTS}
    for p in sorted(_DRIVER_TESTS.glob("*.py")):
        out[f"tests/{p.name}"] = _sha256(p)
    return out


def driver_certification_problems(cert: pathlib.Path) -> list[str]:
    """Driver の変異試験が全 KILLED で、記録 sha256 が現在の driver・test と一致すること."""
    try:
        obj = json.loads(cert.read_text(encoding="utf-8"))
        recorded = obj["target_sha256"]
        all_killed = obj["all_killed"] is True
    except (OSError, ValueError, KeyError, TypeError):
        return [f"driver certification unreadable: {cert}"]
    problems = [] if all_killed else ["driver certification: not all KILLED"]
    if recorded != certified_files():
        problems.append("driver certification sha256 differs from the current files")
    return problems


def manifest_problems() -> list[str]:
    """凍結 v2 / v3 / v4 manifest の検査 (run.sh と同じ script) が ``MANIFEST OK`` で終わること."""
    problems: list[str] = []
    env = dict(os.environ, PYTHONUTF8="1")
    for script in MANIFEST_CHECKS:
        try:
            proc = subprocess.run(  # noqa: S603
                [sys.executable, script, "--verify"],
                cwd=str(_REPO_ROOT),
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                check=False,
            )
        except OSError as exc:
            problems.append(f"{script} could not run: {exc}")
            continue
        lines = (proc.stdout or "").strip().splitlines()
        if proc.returncode != 0 or not lines or lines[-1] != "MANIFEST OK":
            problems.append(f"{script} --verify did not end with MANIFEST OK")
    return problems


def launch_problems() -> list[str]:
    """実走 (main) の前提: driver が certified、固定ファイルが HEAD と一致、凍結 manifest が OK."""
    problems = driver_certification_problems(DRIVER_CERT)
    for rel in PINNED:
        if _git("ls-files", "--error-unmatch", rel) is None:
            problems.append(f"not tracked by git: {rel}")
    if _git("diff", "--quiet", "HEAD", "--", *PINNED) is None:
        problems.append("pinned files differ from HEAD (or git unavailable)")
    problems.extend(manifest_problems())
    return problems


async def final_digest(
    http: httpx.AsyncClient, backoff_scale: float
) -> tuple[str | None, str | None]:
    """終了時の digest (再送 RESENDS 回・同じ backoff)。返り値 = (digest, 失敗の説明)."""
    error: str | None = None
    for attempt in range(1 + RESENDS):
        try:
            return (await preflight(http))["model_digest"], None
        except PreflightError as exc:
            error = f"final preflight failed: {exc}"
        if attempt < RESENDS:
            await asyncio.sleep(BACKOFF_SCHEDULE_S[attempt] * backoff_scale)
    return None, error


async def run(
    run_dir: pathlib.Path,
    transport: httpx.AsyncBaseTransport,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    backoff_s: float = 1.0,
) -> str:
    """1 run を実行し、終了理由を返す.

    preflight は run dir を作る前 (失敗しても何も書かない)。非 transport の例外は provenance を
    書いてから再送出する。``backoff_s`` は再送の待ち ``BACKOFF_SCHEDULE_S`` に掛ける倍率 (test は 0)。
    """
    observer = ObservingTransport(transport)
    async with httpx.AsyncClient(
        base_url=endpoint, transport=observer, timeout=TIMEOUT_S
    ) as http:
        env = await preflight(http)
        prepare_run_dir(run_dir)
        return await _run_prepared(run_dir, http, observer, env, endpoint, backoff_s)


async def _run_prepared(
    run_dir: pathlib.Path,
    http: httpx.AsyncClient,
    observer: ObservingTransport,
    env: dict[str, str],
    endpoint: str,
    backoff_s: float,
) -> str:
    started = _now()
    driver_sha_start = _sha256(pathlib.Path(__file__))
    reason = REASON_ABORTED
    c0_rate: float | None = None
    state: RunState | None = None
    error: str | None = None
    digest_end: str | None = None
    plan = _plan()
    n_c0 = sc.n_c0()
    try:
        if any(k.phase != bat.PHASE_C0 for k in plan[:n_c0]):
            msg = "frozen plan does not start with the C0 calls"
            raise RuntimeError(msg)
        llm = OllamaChatClient(model=v2bat.MODEL, client=http, timeout=TIMEOUT_S)
        with (
            (run_dir / RECORDS_NAME).open("x", encoding="utf-8", newline="\n") as rf,
            (run_dir / "attempts.jsonl").open(
                "x", encoding="utf-8", newline="\n"
            ) as af,
        ):
            state = RunState(run_dir, rf, af, observer, llm, backoff_s)
            stop = await run_calls(state, 0, plan[:n_c0])
            if stop is None:
                c0_rate = c0_bottom_rate(state.records)
                if c0_rate > sc.BOT_MAX:
                    stop = REASON_C0_GATE
            if stop is None:
                stop = await run_calls(state, n_c0, plan[n_c0:])
        # 実走中に重みが差し替わっていないこと (tag の再 pull 等)。transport 失敗で止まった run は、
        # 終了時の preflight が失敗しても分類を変えない (Ollama が落ちたままなのは transport 失敗の続き)
        digest_end, final_error = await final_digest(http, backoff_s)
        if final_error is not None:
            error = final_error
            if stop != REASON_TRANSPORT:
                stop = REASON_ABORTED
        elif digest_end != env["model_digest"]:
            error = f"model digest changed: {env['model_digest']} -> {digest_end}"
            stop = REASON_ABORTED
        reason = stop or REASON_COMPLETED
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        meta_ok: bool | None = None
        meta_error: str | None = None
        if observer.sent:
            try:
                meta = observed_meta(observer.sent)
                written = json.loads((run_dir / "meta.json").read_text("utf-8"))
                meta_ok = meta_matches_frozen(meta) and written == meta
            except (SentBodyMismatchError, OSError, ValueError) as exc:
                meta_ok = False
                meta_error = f"{type(exc).__name__}: {exc}"
        driver_sha_end = _sha256(pathlib.Path(__file__))
        models = set() if state is None else state.response_models
        anomalies: list[str] = []
        if observer.sent and meta_ok is not True:
            anomalies.append("sent request conditions differ from the frozen meta")
        if driver_sha_end != driver_sha_start:
            anomalies.append("driver file changed during the run")
        if models - {v2bat.MODEL}:
            anomalies.append(f"unexpected response models {sorted(models)}")
        if anomalies and reason in (REASON_COMPLETED, REASON_C0_GATE):
            reason = REASON_ABORTED
            error = "; ".join(anomalies)
        provenance = {
            "started_at": started,
            "finished_at": _now(),
            "exit_reason": reason,
            "error": error,
            "n_records": 0 if state is None else len(state.records),
            "n_sent": len(observer.sent),
            "c0_bottom_rate_driver": c0_rate,
            "meta_matches_frozen": meta_ok,
            "meta_error": meta_error,
            "response_models": [] if state is None else sorted(state.response_models),
            "n_finish_length": 0 if state is None else state.n_length,
            "n_resends": 0 if state is None else state.resends,
            "ollama_version": env["ollama_version"],
            "model_digest_start": env["model_digest"],
            "model_digest_end": digest_end,
            "endpoint": endpoint,
            "driver_sha256_start": driver_sha_start,
            "driver_sha256_end": driver_sha_end,
            "manifest_sha256": _sha256(_MANIFEST),
            "git_head": _git("rev-parse", "HEAD"),
            "git_dirty": git_dirty(),
        }
        write_json_durable(run_dir / "provenance.json", provenance, exclusive=True)
    return reason


def main(argv: list[str] | None = None) -> int:
    """実走の入口。run dir と endpoint は固定 (登録外の実走経路を閉じる、DR-6 / DR-7)."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args(argv)
    problems = launch_problems()
    if problems:
        for p in problems:
            _progress(f"[driver] refuse to launch: {p}")
        return EXIT_CODES[REASON_ABORTED]
    try:
        reason = asyncio.run(run(DEFAULT_RUN_DIR, httpx.AsyncHTTPTransport()))
    except Exception as exc:  # noqa: BLE001 — 終了理由は provenance.json に書いてある
        _progress(f"[driver] aborted: {type(exc).__name__}: {exc}")
        return EXIT_CODES[REASON_ABORTED]
    _progress(f"[driver] exit_reason={reason}")
    return EXIT_CODES[reason]


if __name__ == "__main__":
    sys.exit(main())
