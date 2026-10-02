#!/usr/bin/env python
"""候補 G (汎化 probe) — null pilot と本走の実走 driver (prereg §4・§8.1・§9.2・§9.4).

凍結物 (battery の renderer・seed・定数、pilot 判定と scorer の parse・構造の検査・meta の検査、manifest の
照合) を import だけして、qwen3:8b を **逐次** に呼ぶ。自由度は足さない。判断記録 =
``.steering/20261002-generalization-probe-driver/decisions.md`` (DD-1〜、実データを見る前に commit)。

* **段** (``Stage``)。pilot と本走は同じ経路を通り、段ごとに plan・body の組み立て・parse・凍結済みの構造の検査・
  grid・参照する observed だけを差し替える (DD-1)。pilot = KNOW 108 → masked の単位 576、本走 = lever の単位
  (R = pilot の機械判定の R)。単位の順は (r, 族, つ組)、単位の中ではつ組の probe ごとに族内の 2 arm を交互に呼ぶ
  (prereg §4)。KNOW を先に置くのは §8.2 の判定の順に合わせたため (DD-4)。
* **予定表の事前検査** (DD-1)。候補 G は開ループで、どの呼び出しの body も plan のキーだけで決まる。全件の body を
  最初に作り、骨格の記録 (raw = null) を凍結済みの構造の検査・grid の完全性に、meta を凍結済みの ``meta_violations``
  に通す。外れたら run dir を作らず、モデルを 1 回も呼ばずに止まる (``ScheduleError``)。
* **送る直前の照合**。``ObservingTransport`` が wire の body を読み、key の集合・値と型 (False と 0、4096.0 と 4096 を
  区別する)・その位置のキーでの凍結済みの構造の検査 (seed と prompt) を照合する。外れたら送らずに止まる
  (``SentBodyMismatchError``)。POST は ``/api/chat`` と、observed を読む間の ``/api/show`` だけを通す。
* **通信は httpx を直接使う** (DD-2)。transport 失敗 = ``httpx.HTTPError`` 全般・HTTP が 200 でない・JSON でない・
  ``message.content`` が無いか文字列でない。同じ body (同じ seed) で再送を 3 回まで行う。解けなければ raw = null の
  行を書いて止まる (⊥ にしない)。それ以外の例外は行を書かずに止まる。再開しない。
* **observed** = ``/api/version`` の版・``/api/tags`` の凍結 model の digest・``/api/show`` の chat template の sha256。
  開始時に読んで meta.json に書き、終了時に読み直す。変わっていれば異常。本走は開始時の値が pilot の機械判定の
  observed と違えば、run dir を作らずに止まる。
* **成功したときだけ公開する** (v5 の DV-1・DV-4 を継ぐ、DD-3)。記録は ``records.partial.jsonl`` に書き、次を全て
  満たしたときだけ ``records.jsonl`` へ rename する。凍結 ``run.sh`` は ``test -f records.jsonl`` で止まるので、
  公開されていない run は判定まで進まない。transport 失敗の run も公開しない (やり直しは user の裁定)。

  - 全件に答えがあり、transport 失敗が無い。
  - 来歴の異常が無い (応答の model 名・observed が開始時と同じ)。
  - その段の manifest の照合が、公開の時点でも ``MANIFEST OK (stage <段>)``。
  - partial と meta.json を判定と同じ reader で読み戻し、凍結済みの構造の検査・meta の検査・完全性を通る。
  - partial と meta.json の bytes が、この run が書いた行と meta に一致する (別の run の記録・meta を混ぜない、
    Codex HIGH-1)。
  - 固定ファイルの sha256 が起動時と同じで、ディスクの driver が実行中の driver と同じ。公開時の manifest の照合と
    読み戻しの **後** に比べる (Codex HIGH-2)。

  来歴 (provenance.json) は二相: 未公開 (aborted・pending の注記) で書く → rename → 公開済みに書き直す。
  第 2 段が照合する 3 項目 (``driver_sha256``・``records_sha256``・``meta_sha256``) は、公開済みの来歴にだけ書く
  (途中で kill されたら 3 項目の無い来歴が残り、第 2 段が拒否する。DD-5)。3 項目は、実行中に保持した値 (import した
  driver の sha256・この run が書いた行と meta の bytes の sha256) から書き、rename の後のファイルが同じ bytes である
  ことを確かめてから書く。transport 失敗の run の来歴には ``status: not_computed`` を書く (prereg §4、DD-3)。
* **起動の前提** (``launch_problems``): driver の certification が manifest の契約を満たす・ディスクの driver が
  実行中の driver と同じ・固定ファイルが git で追跡され HEAD と一致・その段の manifest の照合が
  ``MANIFEST OK (stage <段>)``。本走は pilot の機械判定が GO。固定ファイルの sha256 は起動の検査の前に取り、
  実走の終わりに比べる。

実行 (repo root から、GPU 実走は user 裁定の後)。run dir と endpoint は固定で、引数は段だけ::

    uv run python scripts/generalization_probe_driver.py --stage pilot
    uv run python scripts/generalization_probe_driver.py --stage main
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final, TextIO

import httpx

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import generalization_probe_battery as bat  # noqa: E402
from scripts import generalization_probe_manifest as man  # noqa: E402
from scripts import generalization_probe_pilot_gate as pg  # noqa: E402
from scripts import generalization_probe_scorer as sc  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

STAGE_PILOT: Final[str] = "pilot"
STAGE_MAIN: Final[str] = "main"
# 実行中の driver: import した時点の bytes の sha256 (来歴の driver_sha256 はこの値から書く、Codex HIGH-2)
_DRIVER_PATH: pathlib.Path = pathlib.Path(__file__).resolve()
_DRIVER_SHA: str = hashlib.sha256(_DRIVER_PATH.read_bytes()).hexdigest()
SEED_PATH: Final[pathlib.Path] = _REPO_ROOT / man.EXP / "SEED"
PILOT_DIR: Final[pathlib.Path] = _REPO_ROOT / man.EXP / "results" / "pilot"
RUN_DIR: Final[pathlib.Path] = _REPO_ROOT / man.EXP / "results" / "run"
GATE_PATH: Final[pathlib.Path] = _REPO_ROOT / man.PILOT_GATE
DRIVER_CERT: Final[pathlib.Path] = _REPO_ROOT / man.DRIVER_CERT
DEFAULT_ENDPOINT: Final[str] = "http://127.0.0.1:11434"
RECORDS_NAME: Final[str] = "records.jsonl"  # 公開名 (凍結 run.sh が test -f で見る)
PARTIAL_NAME: Final[str] = "records.partial.jsonl"  # 実走中・未公開の記録
META_NAME: Final[str] = "meta.json"
PROVENANCE_NAME: Final[str] = "provenance.json"
ATTEMPTS_NAME: Final[str] = "attempts.jsonl"
# rename の後の照合に落ちた記録を退ける名前 (公開名に残すと、凍結 run.sh の test -f を通ってしまう)
REJECTED_NAME: Final[str] = "records.rejected.jsonl"
# 二相の公開: rename の前に書く来歴の注記 (これが残っていれば、公開の前に中断した run)
PENDING_NOTE: Final[str] = (
    "publication pending (interrupted before the rename if this remains)"
)

RESENDS: Final[int] = 3  # 同じ seed での再送回数 (送信は初回と合わせて最大 4 回)
# 再送の待ち (秒)。attempt ごとに延ばす (Ollama の再起動・復帰を待つ。登録外・label と独立)
BACKOFF_SCHEDULE_S: Final[tuple[float, ...]] = (5.0, 30.0, 120.0)
TIMEOUT_S: Final[float] = 300.0  # モデルの再ロードで 60 秒を超えうる

REASON_COMPLETED: Final[str] = "completed"
REASON_TRANSPORT: Final[str] = "transport_failure"
REASON_ABORTED: Final[str] = "aborted"
EXIT_CODES: Final[dict[str, int]] = {
    REASON_COMPLETED: 0,
    REASON_TRANSPORT: 3,
    REASON_ABORTED: 4,
}

CHAT_PATH: Final[str] = "/api/chat"
SHOW_PATH: Final[str] = "/api/show"
BODY_KEYS: Final[frozenset[str]] = frozenset(
    {"model", "messages", "stream", "think", "options"}
)
OPTION_KEYS: Final[frozenset[str]] = frozenset(
    {"seed", "num_ctx", "num_predict", "temperature", "top_p", "repeat_penalty"}
)
# 送る値 (凍結 battery の定数)。seed 以外は全呼び出しで同じ
FIXED_OPTIONS: Final[dict[str, object]] = {
    "num_ctx": bat.NUM_CTX,
    "num_predict": bat.NUM_PREDICT,
    "temperature": bat.TEMPERATURE,
    "top_p": bat.TOP_P,
    "repeat_penalty": bat.REPEAT_PENALTY,
}

Key = tuple[str, int, str, int]  # (arm, replicate, probe_id, k) = 凍結 grid の要素
_MASKED_OF: Final[dict[str, str]] = {lever: m for m, lever in pg.MASKED_ARMS.items()}
_PROBES: Final[dict[str, bat.Probe]] = {p.probe_id: p for p in bat.probes()}


# ------------------------------------------------------------------- 段


@dataclass(frozen=True)
class Stage:
    """pilot と本走で差し替える部分 (DD-1)。経路 (事前検査・照合・再送・記録・公開) は共通."""

    name: str
    run_dir: pathlib.Path
    plan: tuple[Key, ...]
    grid: frozenset[Key]
    request: Callable[[Key], tuple[list[dict[str, str]], int]]  # → (messages, seed)
    parse: Callable[[str, str], str | None]  # (arm, raw) → parsed
    structure: Callable[[Sequence[sc.Sample]], list[str]]  # 凍結済みの構造の検査
    reference_observed: dict[str, str] | None = None


def unit_keys(rs: range, k_count: int, arm_name: Callable[[str], str]) -> list[Key]:
    """単位の順 (r, 族, つ組) に、つ組の probe ごとに族内の 2 arm を交互に並べる (prereg §4)."""
    out: list[Key] = []
    for r in rs:
        for family in bat.FAMILIES:
            for j in range(bat.N_TRIPLES):
                for p in bat.triple_probes(j):
                    for k in range(k_count):
                        out.extend((arm_name(arm), r, p.probe_id, k) for arm in family)
    return out


def pilot_plan() -> tuple[Key, ...]:
    """KNOW (key 番号 × 試行) → masked の単位 (r ∈ [PILOT_R0, PILOT_R0 + PILOT_R))."""
    know = [
        (pg.ARM_KNOW, 0, pg.know_probe_id(i), k)
        for i in range(len(bat.all_keys()))
        for k in range(bat.KNOW_K)
    ]
    rs = range(bat.PILOT_R0, bat.PILOT_R0 + bat.PILOT_R)
    return (*know, *unit_keys(rs, pg.PILOT_K, _MASKED_OF.__getitem__))


def main_plan(r_count: int) -> tuple[Key, ...]:
    return tuple(unit_keys(range(r_count), sc.FROZEN_K, str))


def pilot_request(key: Key) -> tuple[list[dict[str, str]], int]:
    arm, r, probe_id, k = key
    if arm == pg.ARM_KNOW:
        i = int(probe_id[1:])
        return bat.render_know_messages(i, k), bat.sample_seed("know", 0, i, k)
    lever = pg.MASKED_ARMS[arm]
    probe = _PROBES[probe_id]
    ns = f"pilot_fam{bat.ARM_FAMILY[lever]}"
    return (
        bat.render_messages(lever, probe, r, masked=True),
        bat.sample_seed(ns, r, probe.triple, k),
    )


def main_request(key: Key) -> tuple[list[dict[str, str]], int]:
    arm, r, probe_id, k = key
    probe = _PROBES[probe_id]
    ns = f"fam{bat.ARM_FAMILY[arm]}"
    return bat.render_messages(arm, probe, r), bat.sample_seed(ns, r, probe.triple, k)


def pilot_parse(arm: str, raw: str) -> str | None:
    """KNOW は分類名、masked は行動 label (凍結 pilot 判定の re-parse と同じ関数)."""
    return pg.parse_class(raw) if arm == pg.ARM_KNOW else sc.parse_choice(raw)


def main_parse(_arm: str, raw: str) -> str | None:
    return sc.parse_choice(raw)


def pilot_stage(run_dir: pathlib.Path) -> Stage:
    return Stage(
        name=STAGE_PILOT,
        run_dir=run_dir,
        plan=pilot_plan(),
        grid=frozenset(pg.pilot_grid()),
        request=pilot_request,
        parse=pilot_parse,
        structure=pg.structure_violations,
    )


def main_stage(
    run_dir: pathlib.Path, r_count: int, reference_observed: dict[str, str]
) -> Stage:
    def structure(samples: Sequence[sc.Sample]) -> list[str]:
        return sc.structure_violations(samples, r_count, sc.FROZEN_K)

    return Stage(
        name=STAGE_MAIN,
        run_dir=run_dir,
        plan=main_plan(r_count),
        grid=frozenset(sc.grid(r_count, sc.FROZEN_K)),
        request=main_request,
        parse=main_parse,
        structure=structure,
        reference_observed=dict(reference_observed),
    )


# ------------------------------------------------------- body と予定表


class ScheduleError(RuntimeError):
    """予定表が凍結済みの検査を通らない。モデルを 1 回も呼ばずに止まる (DD-1)."""


class SentBodyMismatchError(RuntimeError):
    """送ろうとした body が凍結値と違う。httpx 例外でないので再送されない."""


def body_for(stage: Stage, key: Key) -> dict[str, Any]:
    messages, seed = stage.request(key)
    return {
        "model": bat.MODEL,
        "messages": messages,
        "stream": False,
        "think": bat.THINK,
        "options": {"seed": seed, **FIXED_OPTIONS},
    }


def request_of(body: dict[str, Any]) -> dict[str, Any]:
    """Body から ``sc.request_meta()`` と同じ形の要求条件を読む."""
    opts = body["options"]
    return {
        "model": body["model"],
        "think": body["think"],
        "options": {
            "temperature": opts["temperature"],
            "top_p": opts["top_p"],
            "repeat_penalty": opts["repeat_penalty"],
            "num_ctx": opts["num_ctx"],
            "num_predict": opts["num_predict"],
        },
    }


def _exact(got: object, want: object) -> bool:
    """型まで一致 (False == 0、4096.0 == 4096 を通さない)."""
    return type(got) is type(want) and got == want


def _canonical(obj: object) -> str:
    """型まで区別する比較用の JSON (4096.0 と 4096、False と 0 を別物にする)."""
    return json.dumps(obj, sort_keys=True)


def shape_problems(body: object) -> list[str]:
    """Body の形と、seed 以外の値 (key の集合・型・凍結値)."""
    if not isinstance(body, dict) or set(body) != BODY_KEYS:
        return [f"body keys differ from {sorted(BODY_KEYS)}"]
    msgs = body["messages"]
    if not isinstance(msgs, list) or not all(
        isinstance(m, dict)
        and set(m) == {"role", "content"}
        and all(type(v) is str for v in m.values())
        for m in msgs
    ):
        return ["messages are not a list of role / content strings"]
    opts = body["options"]
    if not isinstance(opts, dict) or set(opts) != OPTION_KEYS:
        return [f"options keys differ from {sorted(OPTION_KEYS)}"]
    problems = [
        f"{name}={body[name]!r}"
        for name, want in (
            ("model", bat.MODEL),
            ("think", bat.THINK),
            ("stream", False),
        )
        if not _exact(body[name], want)
    ]
    problems.extend(
        f"options.{name}={opts[name]!r} (want {want!r})"
        for name, want in FIXED_OPTIONS.items()
        if not _exact(opts[name], want)
    )
    if type(opts["seed"]) is not int:
        problems.append(f"options.seed={opts['seed']!r} is not an int")
    return problems


def skeleton(index: int, key: Key, body: dict[str, Any]) -> sc.Sample:
    """送る body の候補記録 (raw = null)。seed と prompt は body から読む."""
    arm, r, probe_id, k = key
    return sc.Sample(
        call_index=index,
        arm=arm,
        replicate=r,
        probe_id=probe_id,
        k=k,
        seed=body["options"]["seed"],
        prompt_sha256=sc.messages_sha256(body["messages"]),
        raw=None,
        parsed=None,
    )


def build_schedule(stage: Stage) -> tuple[dict[str, Any], ...]:
    """plan の位置ごとの body (呼び出しの前に全部作る)."""
    return tuple(body_for(stage, key) for key in stage.plan)


def meta_for(
    schedule: Sequence[dict[str, Any]], observed: dict[str, str]
) -> dict[str, Any]:
    """meta.json = {"request": 予定表の要求条件, "observed": 開始時の observed} (prereg §4)."""
    return {"request": request_of(schedule[0]), "observed": dict(observed)}


def schedule_violations(
    stage: Stage, schedule: Sequence[dict[str, Any]], observed: dict[str, str]
) -> list[str]:
    """予定表全体と meta を、呼び出しの前に凍結済みの検査に通す (DD-1)."""
    out: list[str] = []
    if len(set(stage.plan)) != len(stage.plan) or set(stage.plan) != stage.grid:
        out.append("schedule: plan keys differ from the frozen grid")
    if not schedule or len(schedule) != len(stage.plan):
        out.append("schedule: bodies do not match the plan")
    for i, body in enumerate(schedule):
        out.extend(f"schedule: call {i}: {p}" for p in shape_problems(body))
    if out:
        return out
    cands = [
        skeleton(i, key, body)
        for i, (key, body) in enumerate(zip(stage.plan, schedule, strict=True))
    ]
    out.extend(f"schedule: {p}" for p in stage.structure(cands))
    meta = meta_for(schedule, observed)
    if _canonical(meta["request"]) != _canonical(sc.request_meta()):
        out.append("schedule: request conditions differ from the frozen values")
    out.extend(
        f"schedule: {p}" for p in sc.meta_violations(meta, stage.reference_observed)
    )
    return out


def check_sent_body(stage: Stage, index: int, body: object) -> None:
    """送信前の wire body を、plan の位置 index のキーで凍結値と凍結済みの構造の検査に照合する."""
    key = stage.plan[index]
    where = f"call {index} {key}"
    problems = shape_problems(body)
    if not problems:
        assert isinstance(body, dict)
        problems = stage.structure([skeleton(index, key, body)])
    if problems:
        msg = f"{where}: " + "; ".join(problems)
        raise SentBodyMismatchError(msg)


class ObservingTransport(httpx.AsyncBaseTransport):
    """inner transport を包み、POST の body を送信前に照合・記録する."""

    def __init__(self, inner: httpx.AsyncBaseTransport, stage: Stage) -> None:
        self.inner = inner
        self.stage = stage
        self.expected: int | None = None
        self.allow_show = False
        self.sent: dict[int, list[dict[str, Any]]] = {}

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            path = request.url.path
            if path == SHOW_PATH and self.allow_show:
                pass
            elif path != CHAT_PATH:
                msg = f"unexpected POST path {path!r}"
                raise SentBodyMismatchError(msg)
            else:
                if self.expected is None:
                    msg = "chat request without an expected call"
                    raise SentBodyMismatchError(msg)
                body = json.loads(request.content)
                check_sent_body(self.stage, self.expected, body)
                self.sent.setdefault(self.expected, []).append(body)
        return await self.inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self.inner.aclose()

    def n_sent(self) -> int:
        return sum(len(v) for v in self.sent.values())


# ------------------------------------------------------------ observed


class PreflightError(RuntimeError):
    """Ollama / model / 環境の同定が使えない。run dir を作る前に止まる (label を 1 件も観測しない)."""


def _json_of(response: httpx.Response) -> object:
    if response.status_code != httpx.codes.OK:
        msg = f"{response.request.url.path} returned HTTP {response.status_code}"
        raise PreflightError(msg)
    return response.json()


def _model_digest(tags: object) -> str | None:
    if not isinstance(tags, dict):
        return None
    for m in tags.get("models", []):
        if isinstance(m, dict) and bat.MODEL in (m.get("name"), m.get("model")):
            digest = m.get("digest")
            return digest if isinstance(digest, str) and digest else None
    return None


async def read_observed(
    http: httpx.AsyncClient, observer: ObservingTransport
) -> dict[str, str]:
    """実行環境の同定 (prereg §4): Ollama の版・凍結 model の digest・chat template の sha256."""
    observer.allow_show = True
    try:
        version = _json_of(await http.get("/api/version"))["version"]  # type: ignore[index]
        digest = _model_digest(_json_of(await http.get("/api/tags")))
        show = _json_of(await http.post(SHOW_PATH, json={"model": bat.MODEL}))
        template = show["template"]  # type: ignore[index]
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        msg = f"Ollama is not reachable: {type(exc).__name__}: {exc}"
        raise PreflightError(msg) from exc
    finally:
        observer.allow_show = False
    if not isinstance(version, str) or not version:
        msg = "Ollama version is missing"
        raise PreflightError(msg)
    if digest is None:
        msg = f"model {bat.MODEL!r} is not available (no digest in /api/tags)"
        raise PreflightError(msg)
    if not isinstance(template, str):
        msg = f"model {bat.MODEL!r} has no chat template in /api/show"
        raise PreflightError(msg)
    return {
        "model_digest": digest,
        "ollama_version": version,
        "template_sha256": hashlib.sha256(template.encode("utf-8")).hexdigest(),
    }


# ------------------------------------------------------------------- run


class TransportFailure(Exception):  # noqa: N818 — 再送の対象 (例外ではなく分類の名前)
    """1 回の送信が答えを返さなかった (再送する)."""


@dataclass(frozen=True)
class Reply:
    content: str
    model: object
    done_reason: object


async def send_chat(http: httpx.AsyncClient, body: dict[str, Any]) -> Reply:
    """1 回送る。transport 失敗は ``TransportFailure`` (それ以外の例外はそのまま上げる)."""
    try:
        response = await http.post(CHAT_PATH, json=body)
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
    return Reply(content, payload.get("model"), payload.get("done_reason"))


@dataclass
class RunState:
    stage: Stage
    http: httpx.AsyncClient
    observer: ObservingTransport
    records_fh: TextIO
    attempts_fh: TextIO
    backoff_scale: float
    records: list[sc.Sample] = field(default_factory=list)
    lines: list[str] = field(
        default_factory=list
    )  # 書いた記録の行 (公開する bytes の正本)
    response_models: set[str] = field(default_factory=set)
    n_length: int = 0
    resends: int = 0


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _join(error: str | None, more: str) -> str:
    """来歴の error 欄に理由を足す (先の理由を消さない)."""
    return more if error is None else f"{error}; {more}"


def _write_line(fh: TextIO, obj: dict[str, Any]) -> str:
    """1 行 1 JSON。ensure_ascii=True: U+2028 / U+2029 / U+0085 を escape し、凍結 reader の
    ``splitlines()`` で 1 記録が 2 行に割れないようにする.
    """
    line = json.dumps(obj, ensure_ascii=True, sort_keys=True)
    fh.write(line + "\n")
    fh.flush()
    os.fsync(fh.fileno())
    return line


def json_text(obj: object) -> str:
    """JSON ファイルの中身 (meta.json の bytes は、この文字列の UTF-8 と一致しなければならない)."""
    return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def write_json_durable(path: pathlib.Path, obj: object, *, exclusive: bool) -> None:
    """Temp → flush → fsync → replace。exclusive なら既存ファイルを上書きしない."""
    if exclusive and path.exists():
        msg = f"refusing to overwrite {path}"
        raise FileExistsError(msg)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(json_text(obj))
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(path)


async def call_with_resend(
    state: RunState, index: int, body: dict[str, Any]
) -> str | None:
    """同じ body を最大 1 + RESENDS 回送る。返り値 = content または None (解けない transport 失敗)."""
    state.observer.expected = index
    for attempt in range(1 + RESENDS):
        row: dict[str, Any] = {"call_index": index, "attempt": attempt, "at": _now()}
        reply: Reply | None
        try:
            reply = await send_chat(state.http, body)
        except TransportFailure as exc:
            row.update(outcome="transport_failure", error=str(exc))
            reply = None
        else:
            row.update(outcome="ok", model=reply.model, done_reason=reply.done_reason)
        _write_line(state.attempts_fh, row)
        if reply is not None:
            state.response_models.add(str(reply.model))
            state.n_length += reply.done_reason == "length"
            return reply.content
        if attempt < RESENDS:
            state.resends += 1
            await asyncio.sleep(BACKOFF_SCHEDULE_S[attempt] * state.backoff_scale)
    return None


def absorb(state: RunState, line: str, want: sc.Sample) -> None:
    """書いた行を、判定と同じ reader (``splitlines`` → ``load_records``) で読み戻す。1 記録で、書いた値と同じ."""
    rows = sc.load_records((line + "\n").splitlines())
    if rows != [want]:
        msg = f"written line does not read back as the record ({len(rows)} rows)"
        raise RuntimeError(msg)
    state.records.append(rows[0])
    state.lines.append(line)


async def run_calls(state: RunState, schedule: Sequence[dict[str, Any]]) -> str | None:
    """予定表を plan の順に呼ぶ。transport 失敗が解けなければ raw = null を書いて REASON_TRANSPORT."""
    for index, key in enumerate(state.stage.plan):
        raw = await call_with_resend(state, index, schedule[index])
        sent = state.observer.sent[index][-1]  # 送った body (照合を通ったもの)
        arm, r, probe_id, k = key
        rec = sc.Sample(
            call_index=index,
            arm=arm,
            replicate=r,
            probe_id=probe_id,
            k=k,
            seed=sent["options"]["seed"],
            prompt_sha256=sc.messages_sha256(sent["messages"]),
            raw=raw,
            parsed=None if raw is None else state.stage.parse(arm, raw),
        )
        line = _write_line(state.records_fh, vars(rec))
        absorb(state, line, rec)
        if (index + 1) % 100 == 0:
            _progress(f"[driver] {index + 1} calls ({_now()})")
        if raw is None:
            return REASON_TRANSPORT
    return None


def _progress(line: str) -> None:
    """進捗表示。stdout が使えない (detached 起動で閉じたハンドル等) ことで run を止めない."""
    try:
        print(line, flush=True)  # noqa: T201
    except (OSError, ValueError):
        pass


# ------------------------------------------------------------ 公開


def publication_problems(stage: Stage) -> list[str]:
    """公開前の判定: partial と meta.json を判定と同じ reader で読み戻し、凍結済みの検査にかける.

    構造・meta・完全性だけを見る (label から計算する量は見ない)。
    """
    try:
        lines = (stage.run_dir / PARTIAL_NAME).read_text(encoding="utf-8").splitlines()
        samples = sc.load_records(lines)
        meta = json.loads((stage.run_dir / META_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # RecordError を含む
        return [f"unreadable: {type(exc).__name__}: {exc}"]
    out = list(stage.structure(samples))
    out.extend(sc.meta_violations(meta, stage.reference_observed))
    keys = {(s.arm, s.replicate, s.probe_id, s.k) for s in samples}
    if len(samples) != len(stage.grid) or keys != stage.grid:
        out.append("records do not cover the frozen grid")
    if any(s.raw is None for s in samples):
        out.append("a transport failure is recorded")
    return out


def records_bytes(lines: Sequence[str]) -> bytes:
    """この run が書いた記録の bytes (partial と公開名のファイルは、これと一致しなければならない)."""
    return "".join(line + "\n" for line in lines).encode("utf-8")


def binding_problems(
    run_dir: pathlib.Path, records_name: str, records: bytes, meta: bytes
) -> list[str]:
    """ディスクの記録と meta.json が、この run が書いた bytes と一致すること (Codex HIGH-1).

    構造の検査だけでは、同じ grid の別の run の記録・別の observed の meta への差し替えを見抜けない。
    """
    out: list[str] = []
    for rel, want in ((records_name, records), (META_NAME, meta)):
        path = run_dir / rel
        if not path.is_file() or path.read_bytes() != want:
            out.append(f"{rel} differs from what this run wrote")
    return out


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
    """ファイルの sha256。無い・読めないなら None (例外で来歴を書けなくしない。変化として異常に数える)."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    except OSError:
        return None


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


def pinned(stage_name: str) -> tuple[str, ...]:
    """実走の前に commit 済みで HEAD と一致していなければならないファイル (manifest の list から作る)."""
    files = (
        *man.FROZEN_FILES,
        man.MANIFEST,
        man.DRIVER,
        man.DRIVER_HARNESS,
        man.DRIVER_TEST,
        man.DRIVER_CERT,
    )
    if stage_name == STAGE_MAIN:
        files = (*files, *man.MAIN_EVIDENCE, man.MANIFEST_MAIN)
    return tuple(dict.fromkeys(files))


def pinned_sha256(stage_name: str) -> dict[str, str | None]:
    """固定ファイルの現在の sha256 (実走の開始時と終了時に取り、変化を来歴の異常とする)."""
    return {rel: _sha256(_REPO_ROOT / rel) for rel in pinned(stage_name)}


def _run_manifest(stage_name: str) -> tuple[int, str]:
    """凍結 manifest の照合 (run.sh と同じ script・同じ環境変数) を呼ぶ。返り値 = (exit code, stdout)."""
    seed = SEED_PATH.read_text(encoding="utf-8").strip()
    env = dict(os.environ, PYTHONUTF8="1", PYTHONHASHSEED=seed)
    proc = subprocess.run(  # noqa: S603
        [sys.executable, man.SELF, "--verify", "--stage", stage_name],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    return proc.returncode, proc.stdout or ""


def manifest_problems(stage_name: str) -> list[str]:
    """その段の manifest の照合が exit 0 で、最後の行がちょうど ``MANIFEST OK (stage <段>)``."""
    try:
        code, out = _run_manifest(stage_name)
    except OSError as exc:
        return [f"manifest --verify --stage {stage_name} could not run: {exc}"]
    lines = out.splitlines()  # 末尾の空白・空行を消さない (Codex LOW-5)
    want = f"MANIFEST OK (stage {stage_name})"
    if code != 0 or not lines or lines[-1] != want:
        return [f"manifest --verify --stage {stage_name} did not end with {want}"]
    return []


def certification_problems(cert: pathlib.Path) -> list[str]:
    """Driver の certification が manifest の契約 (第 1 段で封印) を満たすこと."""
    try:
        obj = json.loads(cert.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [f"driver certification unreadable: {cert}"]
    return man.driver_certification_violations(obj, _REPO_ROOT)


def gate_problems(gate_path: pathlib.Path) -> list[str]:
    """本走の前提: pilot の機械判定が GO で、R と observed を持つ."""
    try:
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [f"pilot gate unreadable: {gate_path}"]
    if not isinstance(gate, dict) or gate.get("decision") != pg.DECISION_GO:
        return ["pilot gate did not decide GO"]
    if type(gate.get("R")) is not int or not isinstance(gate.get("observed"), dict):
        return ["pilot gate has no R or observed"]
    return []


def launch_problems(stage_name: str) -> list[str]:
    """実走の前提: driver が certified・固定ファイルが HEAD と一致・その段の manifest が OK (本走は gate も)."""
    problems = certification_problems(DRIVER_CERT)
    if _sha256(_DRIVER_PATH) != _DRIVER_SHA:
        problems.append("the driver on disk differs from the running driver")
    files = pinned(stage_name)
    for rel in files:
        if _git("ls-files", "--error-unmatch", rel) is None:
            problems.append(f"not tracked by git: {rel}")
    if _git("diff", "--quiet", "HEAD", "--", *files) is None:
        problems.append("pinned files differ from HEAD (or git unavailable)")
    problems.extend(manifest_problems(stage_name))
    if stage_name == STAGE_MAIN:
        problems.extend(gate_problems(GATE_PATH))
    return problems


# ------------------------------------------------------------------- 実行


async def final_observed(
    http: httpx.AsyncClient, observer: ObservingTransport, backoff_scale: float
) -> tuple[dict[str, str] | None, str | None]:
    """終了時の observed (再送 RESENDS 回・同じ backoff)。返り値 = (observed, 失敗の説明)."""
    error: str | None = None
    for attempt in range(1 + RESENDS):
        try:
            return await read_observed(http, observer), None
        except PreflightError as exc:
            error = f"final observed failed: {exc}"
        if attempt < RESENDS:
            await asyncio.sleep(BACKOFF_SCHEDULE_S[attempt] * backoff_scale)
    return None, error


async def run(
    stage: Stage,
    transport: httpx.AsyncBaseTransport,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    backoff_s: float = 1.0,
    pinned_start: dict[str, str | None] | None = None,
) -> str:
    """1 run を実行し、終了理由を返す.

    preflight (observed)・本走の observed の照合・予定表の事前検査は run dir を作る前 (失敗しても何も書かない)。
    非 transport の例外は来歴を書いてから再送出する。``backoff_s`` は再送の待ちに掛ける倍率 (test は 0)。
    ``pinned_start`` は起動の検査の前に取った固定ファイルの sha256 (``main`` が渡す。無ければ実走の開始時に取る)。
    """
    observer = ObservingTransport(transport, stage)
    async with httpx.AsyncClient(
        base_url=endpoint, transport=observer, timeout=TIMEOUT_S
    ) as http:
        observed = await read_observed(http, observer)
        ref = stage.reference_observed
        if ref is not None and observed != ref:
            msg = (
                f"observed environment differs from the pilot gate: {observed} != {ref}"
            )
            raise PreflightError(msg)
        schedule = build_schedule(stage)
        problems = schedule_violations(stage, schedule, observed)
        if problems:
            raise ScheduleError("; ".join(problems[:5]))
        prepare_run_dir(stage.run_dir)
        meta = meta_for(schedule, observed)
        write_json_durable(stage.run_dir / META_NAME, meta, exclusive=True)
        out = Outcome(
            started=_now(),
            pinned_start=dict(
                pinned_sha256(stage.name) if pinned_start is None else pinned_start
            ),
            observed_start=observed,
            meta_bytes=json_text(meta).encode("utf-8"),
        )
        return await _run_prepared(stage, schedule, http, observer, out, backoff_s)


@dataclass
class Outcome:
    """実走の終わりに来歴と公開を決める入力 (``run`` と ``_run_prepared`` が埋める)."""

    started: str
    pinned_start: dict[str, str | None]
    observed_start: dict[str, str]
    meta_bytes: bytes  # この run が書いた meta.json の bytes (公開の照合と来歴の正本)
    reason: str = REASON_ABORTED
    error: str | None = None
    observed_end: dict[str, str] | None = None
    state: RunState | None = None


async def _run_prepared(
    stage: Stage,
    schedule: Sequence[dict[str, Any]],
    http: httpx.AsyncClient,
    observer: ObservingTransport,
    out: Outcome,
    backoff_s: float,
) -> str:
    primary: BaseException | None = None
    try:
        with (
            (stage.run_dir / PARTIAL_NAME).open(
                "x", encoding="utf-8", newline="\n"
            ) as rf,
            (stage.run_dir / ATTEMPTS_NAME).open(
                "x", encoding="utf-8", newline="\n"
            ) as af,
        ):
            state = RunState(stage, http, observer, rf, af, backoff_s)
            out.state = state
            stop = await run_calls(state, schedule)
        # 実走中に環境が差し替わっていないこと (tag の再 pull・template の変更等)。transport 失敗で止まった
        # run は、終了時の読み取りが失敗しても分類を変えない (Ollama が落ちたままなのは transport 失敗の続き)
        observed_end, final_error = await final_observed(http, observer, backoff_s)
        out.observed_end = observed_end
        if final_error is not None:
            out.error = final_error
            if stop != REASON_TRANSPORT:
                stop = REASON_ABORTED
        out.reason = stop or REASON_COMPLETED
    except BaseException as exc:
        out.error = f"{type(exc).__name__}: {exc}"
        primary = exc
        raise
    finally:
        try:
            _finish(stage, observer, out)
        except Exception as exc:
            if primary is None:
                raise
            # 元の例外を隠さない: 来歴・公開の失敗は注記として足す
            primary.add_note(
                f"provenance / publication failed: {type(exc).__name__}: {exc}"
            )
    return out.reason


def _run_anomalies(out: Outcome) -> list[str]:
    """実走中の来歴の異常 (公開を止める): 応答の model・observed の変化."""
    models = set() if out.state is None else out.state.response_models
    anomalies: list[str] = []
    if models - {bat.MODEL}:
        anomalies.append(f"unexpected response models {sorted(models)}")
    if out.observed_end is not None and out.observed_end != out.observed_start:
        anomalies.append(
            f"observed environment changed: {out.observed_start} -> {out.observed_end}"
        )
    return anomalies


def _file_anomalies(stage: Stage, out: Outcome) -> tuple[list[str], list[str]]:
    """固定ファイルと driver の異常。返り値 = (異常, 起動時から変わった固定ファイル).

    公開時の manifest の照合と読み戻しの **後** に呼ぶ (照合の間の差し替えも捕まえる、Codex HIGH-2)。
    """
    pinned_end = pinned_sha256(stage.name)
    changed = sorted(p for p in pinned_end if pinned_end[p] != out.pinned_start.get(p))
    anomalies: list[str] = []
    if changed:
        anomalies.append(f"pinned files changed during the run: {changed}")
    if _sha256(_DRIVER_PATH) != _DRIVER_SHA:
        anomalies.append("the driver on disk differs from the running driver")
    return anomalies, changed


def _finish(stage: Stage, observer: ObservingTransport, out: Outcome) -> None:  # noqa: C901, PLR0912, PLR0915
    """来歴の異常・公開条件を判定し、来歴を書き、条件を満たせば公開する (二相).

    終了理由は ``out.reason`` に書き戻す。
    """
    reason, error, state = out.reason, out.error, out.state
    anomalies = _run_anomalies(out)
    if anomalies and reason == REASON_COMPLETED:
        reason = REASON_ABORTED
        error = _join(error, "; ".join(anomalies))
    # 公開の条件 (続き): 判定 (run.sh) が照合するその段の manifest が今も OK
    at_publication: list[str] | None = None
    if reason == REASON_COMPLETED:
        at_publication = manifest_problems(stage.name)
        if at_publication:
            reason = REASON_ABORTED
            error = _join(error, f"manifest at publication: {at_publication}")
    # 公開の最後の条件: 判定と同じ reader・凍結済みの検査で読み戻せ、bytes がこの run の書いたものと同じ
    written = records_bytes([] if state is None else state.lines)
    read_back: list[str] | None = None
    if reason == REASON_COMPLETED:
        read_back = publication_problems(stage) + binding_problems(
            stage.run_dir, PARTIAL_NAME, written, out.meta_bytes
        )
        if read_back:
            reason = REASON_ABORTED
            error = _join(error, f"read-back: {read_back}")
    late, changed = _file_anomalies(stage, out)
    anomalies += late
    if late and reason == REASON_COMPLETED:
        reason = REASON_ABORTED
        error = _join(error, "; ".join(late))
    publishable = reason == REASON_COMPLETED
    provenance: dict[str, Any] = {
        "stage": stage.name,
        "started_at": out.started,
        "finished_at": _now(),
        # 二相の 1 相目: 公開する run も、rename が済むまでは未公開 (aborted) と書く
        "exit_reason": REASON_ABORTED if publishable else reason,
        # transport 失敗の run は計算しない (prereg §4、DD-3)。判定に渡さないので driver が書く
        "status": sc.STATUS_NOT_COMPUTED if reason == REASON_TRANSPORT else None,
        "error": _join(error, PENDING_NOTE) if publishable else error,
        "anomalies": anomalies,
        "manifest_problems_at_publication": at_publication,
        "read_back_problems": read_back,
        "publishable": publishable,
        "published": False,
        "n_records": 0 if state is None else len(state.records),
        "n_sent": observer.n_sent(),
        "response_models": [] if state is None else sorted(state.response_models),
        "n_finish_length": 0 if state is None else state.n_length,
        "n_resends": 0 if state is None else state.resends,
        "observed_start": out.observed_start,
        "observed_end": out.observed_end,
        "pinned_sha256_start": out.pinned_start,
        "pinned_changed": changed,
        "git_head": _git("rev-parse", "HEAD"),
        "git_dirty": git_dirty(),
    }
    prov_path = stage.run_dir / PROVENANCE_NAME
    write_json_durable(prov_path, provenance, exclusive=True)
    if publishable:
        # commit point: 未公開の来歴 → rename → 公開済みの来歴 (どこで kill されても未公開側に倒れる)
        try:
            publish(stage.run_dir)
        except OSError as exc:
            reason = REASON_ABORTED
            provenance["error"] = _join(
                error, f"publication failed: {type(exc).__name__}: {exc}"
            )
        else:
            after = binding_problems(
                stage.run_dir, RECORDS_NAME, written, out.meta_bytes
            )
            if after:
                # rename の後に差し替わった: 3 項目を書かず (第 2 段が拒否する)、公開名からも退ける
                # (公開名に残すと run.sh が書き換えられた記録から gate を計算する、code-reviewer LOW)
                reason = REASON_ABORTED
                provenance["error"] = _join(
                    error, f"changed after the read-back: {after}"
                )
                try:
                    (stage.run_dir / RECORDS_NAME).rename(stage.run_dir / REJECTED_NAME)
                except OSError as exc:
                    provenance["error"] = _join(
                        provenance["error"], f"could not withdraw: {exc}"
                    )
            else:
                # 第 2 段が照合する 3 項目は、公開済みの来歴にだけ、保持した値から書く (DD-5、Codex HIGH-1・2)
                provenance.update(
                    exit_reason=REASON_COMPLETED,
                    error=error,
                    published=True,
                    driver_sha256=_DRIVER_SHA,
                    records_sha256=hashlib.sha256(written).hexdigest(),
                    meta_sha256=hashlib.sha256(out.meta_bytes).hexdigest(),
                )
        provenance["finished_at"] = _now()
        try:
            write_json_durable(prov_path, provenance, exclusive=False)
        except OSError as exc:
            if not provenance["published"]:
                raise
            # 公開済みでも、来歴は 1 相目 (3 項目なし) のまま残り、第 2 段が拒否する (DD-5)。
            # 第 2 段に使えない run なので completed で終えない (code-reviewer LOW)
            reason = REASON_ABORTED
            _progress(
                "[driver] published, but the final provenance was not written: "
                f"{type(exc).__name__}: {exc}"
            )
    out.reason = reason


def stage_from_gate(run_dir: pathlib.Path, gate_path: pathlib.Path) -> Stage:
    """本走の段: R と参照する observed は pilot の機械判定 (GO) から読む."""
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    return main_stage(run_dir, gate["R"], gate["observed"])


def main(argv: list[str] | None = None) -> int:
    """実走の入口。run dir と endpoint は固定 (登録外の実走経路を閉じる)."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", choices=(STAGE_PILOT, STAGE_MAIN), required=True)
    args = ap.parse_args(argv)
    # 固定ファイルの sha256 は起動の検査の **前** に取り、実走の終わりに比べる (起動の検査の間の
    # 差し替えも捕まえる。Codex HIGH-2・code-reviewer LOW)
    pinned_start = pinned_sha256(args.stage)
    problems = launch_problems(args.stage)
    if problems:
        for p in problems:
            _progress(f"[driver] refuse to launch: {p}")
        return EXIT_CODES[REASON_ABORTED]
    try:
        stage = (
            pilot_stage(PILOT_DIR)
            if args.stage == STAGE_PILOT
            else stage_from_gate(RUN_DIR, GATE_PATH)
        )
        reason = asyncio.run(
            run(stage, httpx.AsyncHTTPTransport(), pinned_start=pinned_start)
        )
    except Exception as exc:  # noqa: BLE001 — 終了理由は provenance.json に書いてある
        _progress(f"[driver] aborted: {type(exc).__name__}: {exc}")
        _progress(traceback.format_exc())  # detached で走らせても原因を追えるように
        return EXIT_CODES[REASON_ABORTED]
    _progress(f"[driver] exit_reason={reason}")
    return EXIT_CODES[reason]


if __name__ == "__main__":
    sys.exit(main())
