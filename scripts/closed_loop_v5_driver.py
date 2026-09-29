#!/usr/bin/env python
"""閉ループ v5 前段 — 較正 pilot の実走 driver (pilot prereg §2.3〜2.5 / §4 / §8)。

凍結 v5 battery の plan (``pilot_plan``)・seed (``pilot_seed``)・renderer (``loop_messages``) と、
凍結 v4 battery の状態更新 (``update``)、凍結 v2 の ``parse_choice``・``request_meta``、凍結 v5 pilot scorer の
連鎖 replay (``chain_violations``) と検証 (``validate``) をそのまま使い、``OllamaChatClient`` 経由で qwen3:8b を
**逐次** に呼ぶ。自由度は足さない。v4 driver (``scripts/closed_loop_driver.py``、判断 DR-1〜7) の運用を継承し、
自己完結のコピーとして置く (v4 driver は import しない。判定に関わる行を全て本ファイルに置き、driver 変異試験で
壊せるようにするため)。判断記録 = ``.steering/20260930-closed-loop-v5-calibration-driver/decisions.md``
(DV-1〜、実データを見る前に commit)。

* **閉ループ** (prereg §2.5)。送る body は、書き出した行を凍結 reader (``load_records``) で読み戻した Record の
  ``parsed`` から ``update`` で (軸, 世界, r) ごとの状態を進め、``loop_messages`` で描き直したもの。成否は記録しない。
* **送った body の照合**。``ObservingTransport`` が送信 **前** に wire body を読む。model / think / stream /
  options (値と型) を凍結値と照合し、送ろうとする body の候補 Record を同じ (軸, 世界, r) の記録済みの行に並べて
  **凍結 scorer の** ``chain_violations`` に通す。key は ``pilot_plan()[i]``、seed は ``pilot_seed(r, t)``。
  外れたら送らずに停止する (aborted)。
* **順序**。``pilot_plan()`` をそのまま上から呼ぶ (call_index = plan の位置)。⊥ では止まらない (⊥ gate は写像
  だけが判定する、DV-3)。
* **transport 失敗** = ``OllamaUnavailableError`` 全般と、応答の message.content が文字列でない場合。
  同じ seed・同じ messages で最大 3 回再送 (送信は計 4 回)。解けなければ ``raw = null`` の行を書いて停止する
  (⊥ にしない)。それ以外の例外は行を書かずに停止する。再開しない。
* **成功したときだけ公開する** (DV-1・DV-4)。記録は ``records.partial.jsonl`` に書き、次を全て満たしたときだけ
  最後に ``records.jsonl`` へ rename する。凍結 ``run.sh`` は冒頭の ``test -f records.jsonl`` で止まるので、
  公開されていない run は誰がどう叩いても写像まで進まない。

  - 全 plan 件を呼び終え、transport 失敗が無い (exit_reason = completed)。
  - 来歴の異常が無い (送った要求条件が 1 種類で凍結値と型まで一致・PINNED の sha256 が開始時と終了時で不変・
    model digest 不変・応答の model 名が凍結 model だけ)。
  - run.sh が照合する凍結 manifest (v2 → v4 → v5) が公開の時点でも OK。
  - partial と meta.json を run.sh と同じ reader で読み戻し、凍結 ``validate`` が ``("computed", [])``。

  公開は二相 (Codex MEDIUM-1): 未公開 (exit_reason = aborted・pending の注記) の provenance.json を書く →
  rename → 公開済み (completed・published) の provenance.json に書き直す。どこで kill されても、公開されない
  側か、公開条件を全て確かめた後の公開済みの側にしか倒れない。
* **meta.json は送った body の観測値から** (実走中に書く)・**来歴は provenance.json / attempts.jsonl**・
  **起動の前提** (driver certification・固定ファイルが HEAD と一致・凍結 v2 / v4 / v5 manifest が OK)・
  **preflight** (Ollama の応答・凍結 model の digest、run dir を作る前) は v4 と同じ。
* **やり直し** (DV-5)。公開されていない run のうち、provenance が無い・transport_failure・aborted の run だけ、
  records を開かずに user 裁定で退避してやり直せる (最大 2 回)。公開済みの run はやり直さない。

実行 (repo root から、GPU 実走は user 裁定の後)。run dir (``results/run``) と endpoint は固定で引数を取らない
(登録外の実走経路を閉じる)::

    uv run python scripts/closed_loop_v5_driver.py
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

from scripts import closed_loop_battery as v4  # noqa: E402
from scripts import closed_loop_v5_battery as bat  # noqa: E402
from scripts import closed_loop_v5_driver_mutation_check as mutation  # noqa: E402
from scripts import closed_loop_v5_pilot_scorer as ps  # noqa: E402
from scripts import skill_lever_battery as v2bat  # noqa: E402
from scripts.skill_lever_scorer import (  # noqa: E402
    messages_sha256,
    parse_choice,
    request_meta,
)

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
    _REPO_ROOT / "experiments" / "20260928-closed-loop-v5-calibration-pilot"
)
DEFAULT_RUN_DIR: Final[pathlib.Path] = _EXP_DIR / "results" / "run"
DEFAULT_ENDPOINT: Final[str] = "http://127.0.0.1:11434"
_MANIFEST: Final[pathlib.Path] = _EXP_DIR / "manifest.json"
RECORDS_NAME: Final[str] = "records.jsonl"  # 公開名 (凍結 run.sh が test -f で見る)
PARTIAL_NAME: Final[str] = "records.partial.jsonl"  # 実走中・未公開の記録
META_NAME: Final[str] = "meta.json"
# 二相の公開: rename の前に書く来歴の注記 (これが残っていれば、公開の前に中断した run)
PENDING_NOTE: Final[str] = (
    "publication pending (interrupted before the rename if this remains)"
)

RESENDS: Final[int] = 3  # 同じ seed での再送回数 (送信は初回と合わせて最大 4 回)
# 再送の待ち (秒)。attempt ごとに延ばす (Ollama の再起動・復帰を待つ。登録外・label と独立)
BACKOFF_SCHEDULE_S: Final[tuple[float, ...]] = (5.0, 30.0, 120.0)
TIMEOUT_S: Final[float] = 300.0  # モデルの再ロードで adapter 既定の 60 秒を超えうる

REASON_COMPLETED: Final[str] = "completed"
REASON_TRANSPORT: Final[str] = "transport_failure"
REASON_ABORTED: Final[str] = "aborted"
EXIT_CODES: Final[dict[str, int]] = {
    REASON_COMPLETED: 0,
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

Key = bat.PilotKey
Chain = tuple[str, str, int]  # (axis, world, replicate)


@functools.cache
def _plan() -> tuple[Key, ...]:
    """凍結 plan (``bat.pilot_plan()``) を 1 回だけ作る (tuple なので書き換えられない)."""
    return tuple(bat.pilot_plan())


def _chain_of(key: Key) -> Chain:
    return (key.axis, key.world, key.replicate)


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
    context: tuple[ps.Record, ...]


def check_sent_body(body: object, expected: Expected) -> None:
    """送信前の wire body を凍結値と凍結 scorer の連鎖 replay で照合する。外れたら ``SentBodyMismatchError``."""
    want_key = _plan()[expected.index]
    where = f"call {expected.index} {want_key}"
    if not isinstance(body, dict) or set(body) != BODY_KEYS:
        msg = f"{where}: body keys differ from {sorted(BODY_KEYS)}"
        raise SentBodyMismatchError(msg)
    msgs = body["messages"]
    if not isinstance(msgs, list) or not all(
        isinstance(m, dict)
        and set(m) == {"role", "content"}
        and all(type(v) is str for v in m.values())
        for m in msgs
    ):
        msg = f"{where}: messages are not a list of role / content strings"
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
        "seed": bat.pilot_seed(want_key.replicate, want_key.step),
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
        cand = ps.Record(
            call_index=expected.index,
            axis=want_key.axis,
            world=want_key.world,
            replicate=want_key.replicate,
            step=want_key.step,
            seed=opts["seed"],
            prompt_sha256=messages_sha256(body["messages"]),
            raw=None,
            parsed=None,
        )
        chain = ps.chain_violations([*expected.context, cand])
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


def _canonical(obj: object) -> str:
    """型まで区別する比較用の JSON (4096.0 と 4096、False と 0 を別物にする)."""
    return json.dumps(obj, sort_keys=True)


def meta_matches_frozen(meta: dict[str, Any]) -> bool:
    want = request_meta()
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
    records: list[ps.Record] = field(default_factory=list)
    # 組み立て側: 読み戻した記録から進める (軸, 世界, r) ごとの状態
    states: dict[Chain, v4.State] = field(default_factory=dict)
    # 照合側 (oracle の文脈): (軸, 世界, r) ごとの記録済みの行
    chains: dict[Chain, list[ps.Record]] = field(default_factory=dict)
    response_models: set[str] = field(default_factory=set)
    n_length: int = 0
    resends: int = 0
    meta_written: bool = False


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _join(error: str | None, more: str) -> str:
    """来歴の error 欄に理由を足す (先の理由を消さない)."""
    return more if error is None else f"{error}; {more}"


def _write_line(fh: TextIO, obj: dict[str, Any]) -> str:
    """1 行 1 JSON。ensure_ascii=True: U+2028 / U+2029 / U+0085 を escape し、凍結 reader の
    ``splitlines()`` で 1 記録が 2 行に割れないようにする (v4 DR-7).
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
        state.run_dir / META_NAME,
        meta_of(state.observer.sent[0]),
        exclusive=True,
    )
    state.meta_written = True


def request_for(
    key: Key, state: RunState
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """組み立て側: 送る messages と options (状態は読み戻した記録から進めた accumulator)."""
    st = state.states.get(_chain_of(key), v4.EMPTY_STATE)
    msgs = bat.loop_messages(st, key.world, key.replicate, key.step, key.axis)
    options = {
        "seed": bat.pilot_seed(key.replicate, key.step),
        "num_ctx": v2bat.NUM_CTX,
        "num_predict": v2bat.NUM_PREDICT,
    }
    return msgs, options


def oracle_context(key: Key, state: RunState) -> tuple[ps.Record, ...]:
    """照合側: 候補の前に並べる記録済みの行 (同じ (軸, 世界, r) の行)."""
    return tuple(state.chains.get(_chain_of(key), []))


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


def absorb(state: RunState, line: str) -> ps.Record:
    """書き出した行を、凍結 reader と同じ経路 (``splitlines`` → ``load_records``) で読み戻し、
    その Record の ``parsed`` から状態と oracle の文脈を進める。1 行が 1 記録にならなければ止まる.
    """
    rows = ps.load_records((line + "\n").splitlines())
    if len(rows) != 1:
        msg = f"written line does not read back as one record ({len(rows)})"
        raise RuntimeError(msg)
    rec = rows[0]
    state.records.append(rec)
    chain = (rec.axis, rec.world, rec.replicate)
    state.chains.setdefault(chain, []).append(rec)
    state.states[chain] = v4.update(
        state.states.get(chain, v4.EMPTY_STATE),
        rec.world,
        v4.loop_signature(rec.replicate, rec.step),
        rec.parsed,
    )
    return rec


async def run_calls(state: RunState, keys: Sequence[Key]) -> str | None:
    """Plan の keys を順に呼ぶ。transport 失敗が解けなければ raw=null を書いて REASON_TRANSPORT."""
    for index, key in enumerate(keys):
        raw, body = await call_with_resend(state, index, key)
        rec = ps.Record(
            call_index=index,
            axis=key.axis,
            world=key.world,
            replicate=key.replicate,
            step=key.step,
            seed=body["options"]["seed"],
            prompt_sha256=messages_sha256(body["messages"]),
            raw=raw,
            parsed=None if raw is None else parse_choice(raw),
        )
        line = _write_line(state.records_fh, dataclasses.asdict(rec))
        absorb(state, line)
        if (index + 1) % 100 == 0:
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


# ------------------------------------------------------------ 公開


def frozen_status(run_dir: pathlib.Path) -> tuple[str, list[str]]:
    """公開前の判定: partial と meta.json を run.sh と同じ reader で読み戻し、凍結 ``validate`` にかける.

    構造の検査だけ (label 由来の測定量は計算しない)。読めなければ ``unreadable``。
    """
    try:
        lines = (run_dir / PARTIAL_NAME).read_text(encoding="utf-8").splitlines()
        meta = json.loads((run_dir / META_NAME).read_text(encoding="utf-8"))
        records = ps.load_records(lines)
    except (OSError, ValueError) as exc:  # RecordError を含む
        return "unreadable", [f"{type(exc).__name__}: {exc}"]
    if not isinstance(meta, dict):
        return "unreadable", ["meta is not an object"]
    return ps.validate(records, meta)


def publish(run_dir: pathlib.Path) -> None:
    """Partial を公開名へ rename する (commit point)。公開名が既にあれば上書きしない."""
    final = run_dir / RECORDS_NAME
    if final.exists():
        msg = f"refusing to overwrite {final}"
        raise FileExistsError(msg)
    (run_dir / PARTIAL_NAME).rename(final)


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


# ------------------------------------------------------------ 起動の前提

# 実走前に commit 済みで HEAD と一致していなければならないファイル
PINNED: Final[tuple[str, ...]] = (
    "scripts/closed_loop_v5_driver.py",
    "scripts/closed_loop_v5_driver_mutation_check.py",
    "scripts/closed_loop_v5_battery.py",
    "scripts/closed_loop_v5_pilot_scorer.py",
    "scripts/closed_loop_v5_sim.py",
    "scripts/closed_loop_v5_select.py",
    "scripts/closed_loop_v5_manifest.py",
    "scripts/closed_loop_v5_mutation_check.py",
    "scripts/closed_loop_battery.py",
    "scripts/closed_loop_sim.py",
    "scripts/closed_loop_manifest.py",
    "scripts/skill_lever_battery.py",
    "scripts/skill_lever_scorer.py",
    "scripts/skill_lever_manifest.py",
    "scripts/stage_b_battery.py",
    "scripts/stage_b_scorer.py",
    "src/erre_sandbox/inference/ollama_adapter.py",
    "src/erre_sandbox/inference/sampling.py",
    "experiments/20260928-closed-loop-v5-calibration-pilot/manifest.json",
    "experiments/20260928-closed-loop-v5-calibration-pilot/prereg.md",
    "experiments/20260928-closed-loop-v5-calibration-pilot/run.sh",
    "experiments/20260928-closed-loop-v5-calibration-pilot/SEED",
    "experiments/20260928-closed-loop-v5-calibration-pilot/results/pilot_mutation.json",
    "experiments/20260928-closed-loop-v5-calibration-pilot/results/decision_table.json",
    "experiments/20260928-closed-loop-v5-calibration-pilot/results/driver_mutation.json",
    "experiments/20260927-closed-loop-divergence-pilot/manifest.json",
    "experiments/20260927-closed-loop-divergence-pilot/results/run/records.jsonl",
    "experiments/20260926-skill-lever-pilot/manifest.json",
)
DRIVER_CERT: Final[pathlib.Path] = _EXP_DIR / "results" / "driver_mutation.json"
_DRIVER_TESTS: Final[pathlib.Path] = _REPO_ROOT / "tests" / "test_closed_loop_v5_driver"
# 判定 (run.sh) が照合する凍結 manifest (同じ順)。実走前にも照合し、判定で拒否される run に GPU を使わない
MANIFEST_CHECKS: Final[tuple[str, ...]] = (
    "scripts/skill_lever_manifest.py",
    "scripts/closed_loop_manifest.py",
    "scripts/closed_loop_v5_manifest.py",
)
CERTIFIED_SCRIPTS: Final[tuple[str, ...]] = (
    "closed_loop_v5_driver.py",
    "closed_loop_v5_driver_mutation_check.py",
)


def pinned_sha256() -> dict[str, str | None]:
    """PINNED の現在の sha256 (実走の開始時と終了時に取り、変化を来歴の異常とする、Codex MEDIUM-2)."""
    return {rel: _sha256(_REPO_ROOT / rel) for rel in PINNED}


def certified_files() -> dict[str, str | None]:
    """Driver 変異試験の certification が結び付くファイルの sha256 (変異対象・harness・test)."""
    here = pathlib.Path(__file__).resolve().parent
    out = {name: _sha256(here / name) for name in CERTIFIED_SCRIPTS}
    for p in sorted(_DRIVER_TESTS.glob("*.py")):
        out[f"tests/{p.name}"] = _sha256(p)
    return out


def driver_certification_problems(cert: pathlib.Path) -> list[str]:
    """Driver の変異試験が全 KILLED で、記録 sha256 が現在の driver・harness・test と一致すること."""
    try:
        obj = json.loads(cert.read_text(encoding="utf-8"))
        recorded = obj["target_sha256"]
        all_killed = obj["all_killed"] is True
        rows = [(row["label"], row["status"]) for row in obj["mutants"]]
    except (OSError, ValueError, KeyError, TypeError):
        return [f"driver certification unreadable: {cert}"]
    problems = [] if all_killed else ["driver certification: not all KILLED"]
    registered = [(m.label, "KILLED") for m in mutation.MUTANTS]
    if rows != registered:
        problems.append(
            "driver certification: mutants differ from the registered set "
            "or are not all KILLED"
        )
    if recorded != certified_files():
        problems.append("driver certification sha256 differs from the current files")
    return problems


def manifest_problems() -> list[str]:
    """凍結 v2 / v4 / v5 manifest の検査 (run.sh と同じ script) が ``MANIFEST OK`` で終わること."""
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


@dataclass
class Outcome:
    """実走の終わりに来歴と公開を決める入力 (``_run_prepared`` が埋める)."""

    started: str
    pinned_start: dict[str, str | None]
    reason: str = REASON_ABORTED
    error: str | None = None
    digest_end: str | None = None
    state: RunState | None = None


async def _run_prepared(
    run_dir: pathlib.Path,
    http: httpx.AsyncClient,
    observer: ObservingTransport,
    env: dict[str, str],
    endpoint: str,
    backoff_s: float,
) -> str:
    out = Outcome(started=_now(), pinned_start=pinned_sha256())
    primary: BaseException | None = None
    try:
        llm = OllamaChatClient(model=v2bat.MODEL, client=http, timeout=TIMEOUT_S)
        with (
            (run_dir / PARTIAL_NAME).open("x", encoding="utf-8", newline="\n") as rf,
            (run_dir / "attempts.jsonl").open(
                "x", encoding="utf-8", newline="\n"
            ) as af,
        ):
            state = RunState(run_dir, rf, af, observer, llm, backoff_s)
            out.state = state
            stop = await run_calls(state, _plan())
        # 実走中に重みが差し替わっていないこと (tag の再 pull 等)。transport 失敗で止まった run は、
        # 終了時の preflight が失敗しても分類を変えない (Ollama が落ちたままなのは transport 失敗の続き)
        digest_end, final_error = await final_digest(http, backoff_s)
        out.digest_end = digest_end
        if final_error is not None:
            out.error = final_error
            if stop != REASON_TRANSPORT:
                stop = REASON_ABORTED
        elif digest_end != env["model_digest"]:
            out.error = f"model digest changed: {env['model_digest']} -> {digest_end}"
            stop = REASON_ABORTED
        out.reason = stop or REASON_COMPLETED
    except BaseException as exc:
        out.error = f"{type(exc).__name__}: {exc}"
        primary = exc
        raise
    finally:
        try:
            _finish(run_dir, observer, env, endpoint, out)
        except Exception as exc:
            if primary is None:
                raise
            # 元の例外を隠さない: 来歴・公開の失敗は注記として足す (Codex 2 回目 MEDIUM-2)
            primary.add_note(
                f"provenance / publication failed: {type(exc).__name__}: {exc}"
            )
    return out.reason


def _finish(
    run_dir: pathlib.Path,
    observer: ObservingTransport,
    env: dict[str, str],
    endpoint: str,
    out: Outcome,
) -> None:
    """来歴の異常・公開条件を判定し、provenance を書き、条件を満たせば公開する (二相).

    終了理由は ``out.reason`` に書き戻す。
    """
    reason, error, state = out.reason, out.error, out.state
    started, pinned_start, digest_end = out.started, out.pinned_start, out.digest_end
    meta_ok: bool | None = None
    meta_error: str | None = None
    if observer.sent:
        try:
            meta = observed_meta(observer.sent)
            written = json.loads((run_dir / META_NAME).read_text("utf-8"))
            same = _canonical(written) == _canonical(meta)
            meta_ok = meta_matches_frozen(meta) and same
        except (SentBodyMismatchError, OSError, ValueError) as exc:
            meta_ok = False
            meta_error = f"{type(exc).__name__}: {exc}"
    pinned_end = pinned_sha256()
    changed = sorted(p for p in PINNED if pinned_end[p] != pinned_start[p])
    models = set() if state is None else state.response_models
    anomalies: list[str] = []
    if observer.sent and meta_ok is not True:
        anomalies.append("sent request conditions differ from the frozen meta")
    if changed:
        anomalies.append(f"pinned files changed during the run: {changed}")
    if models - {v2bat.MODEL}:
        anomalies.append(f"unexpected response models {sorted(models)}")
    if anomalies and reason == REASON_COMPLETED:
        reason = REASON_ABORTED
        error = _join(error, "; ".join(anomalies))
    # 公開の条件 (続き): 判定 (run.sh) が照合する凍結 manifest が今も OK (Codex MEDIUM-2)
    at_publication: list[str] | None = None
    if reason == REASON_COMPLETED:
        at_publication = manifest_problems()
        if at_publication:
            reason = REASON_ABORTED
            error = _join(error, f"manifest at publication: {at_publication}")
    # 公開の最後の条件: 判定と同じ reader・凍結 validate で computed (DV-4)
    validation: dict[str, Any] | None = None
    if reason == REASON_COMPLETED:
        status, reasons = frozen_status(run_dir)
        validation = {"status": status, "reasons": reasons}
        if status != ps.STATUS_COMPUTED:
            reason = REASON_ABORTED
            error = _join(error, f"frozen validate: {status} {reasons}")
    publishable = reason == REASON_COMPLETED
    provenance = {
        "started_at": started,
        "finished_at": _now(),
        # 二相の 1 相目 (Codex MEDIUM-1): 公開する run も、rename が済むまでは未公開 (aborted) と書く
        "exit_reason": REASON_ABORTED if publishable else reason,
        "error": _join(error, PENDING_NOTE) if publishable else error,
        "anomalies": anomalies,
        "manifest_problems_at_publication": at_publication,
        "frozen_validate": validation,
        "publishable": publishable,
        "published": False,
        "n_records": 0 if state is None else len(state.records),
        "n_sent": len(observer.sent),
        "meta_matches_frozen": meta_ok,
        "meta_error": meta_error,
        "response_models": [] if state is None else sorted(state.response_models),
        "n_finish_length": 0 if state is None else state.n_length,
        "n_resends": 0 if state is None else state.resends,
        "ollama_version": env["ollama_version"],
        "model_digest_start": env["model_digest"],
        "model_digest_end": digest_end,
        "endpoint": endpoint,
        "pinned_sha256_start": pinned_start,
        "pinned_changed": changed,
        "manifest_sha256": _sha256(_MANIFEST),
        "git_head": _git("rev-parse", "HEAD"),
        "git_dirty": git_dirty(),
    }
    prov_path = run_dir / "provenance.json"
    write_json_durable(prov_path, provenance, exclusive=True)
    if publishable:
        # commit point: 未公開の来歴 → rename → 公開済みの来歴 (どこで kill されても未公開側に倒れる)
        try:
            publish(run_dir)
        except OSError as exc:
            reason = REASON_ABORTED
            provenance["error"] = _join(
                error, f"publication failed: {type(exc).__name__}: {exc}"
            )
        else:
            provenance.update(exit_reason=REASON_COMPLETED, error=error, published=True)
        provenance["finished_at"] = _now()
        try:
            write_json_durable(prov_path, provenance, exclusive=False)
        except OSError as exc:
            if not provenance["published"]:
                raise
            # 公開済み: 来歴は 1 相目 (pending) のまま残る。公開条件は rename の前に全て確かめてある (DV-5)
            _progress(
                "[driver] published, but the final provenance was not written: "
                f"{type(exc).__name__}: {exc}"
            )
    out.reason = reason


def main(argv: list[str] | None = None) -> int:
    """実走の入口。run dir と endpoint は固定 (登録外の実走経路を閉じる)."""
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
