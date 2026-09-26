#!/usr/bin/env python
"""経験由来 Skill pilot — 実走 driver (prereg v3 §2.3 / §2.4 / §4 / §8)。

凍結 v3 battery の renderer と凍結 v3 scorer の ``expected_sample`` / 呼び出し順 (``call_block`` /
``block_arm_order``) / ``parse_choice`` をそのまま使い、``OllamaChatClient`` 経由で qwen3:8b を **逐次** に
呼ぶ。自由度は足さない。v2 driver (``scripts/skill_lever_driver.py``、判断 DR-1〜12) の運用をそのまま
継承し、v3 の arm 数・R・順序に合わせた自己完結のコピーとして置く (v2 driver は import しない。判定に
関わる行を全て本ファイルに置き、v3 の driver 変異試験で壊せるようにするため。判断記録 =
``.steering/20260927-experience-skill-pilot-run/decisions.md`` DE-R1〜、データを見る前に commit):

* **再開しない**。``--run-dir`` が非空なら起動を拒否する。落ちた run はそのまま残し、判定側で
  ``not_computed`` になる。やり直しは下の DE-R7 の条件でだけ、旧 dir を退避して call_index 0 から全件。
* **順序** (prereg v3 §2.4)。C0 の全 240 呼び出し ((r, probe, k) の辞書順) → C0 ⊥ 率 > ``BOT_MAX`` なら
  状態 arm を走らせず停止 → 状態 8 arm は (r, probe, k) の block ごとに ``block_arm_order(call_block(...))``
  の順で呼ぶ。``call_index`` は run 全体の通し番号。
* **transport 失敗** = ``OllamaUnavailableError`` 全般と、応答の message.content が文字列でない場合。
  同じ seed で最大 3 回再送 (送信は計 4 回)。解けなければ ``raw = null`` の行を書いて停止する (⊥ にしない)。
  それ以外の例外は行を書かずに停止する。
* **送った body の観測**。``ObservingTransport`` が送信 **前** に wire body を読み、model / think / stream /
  options (値と型) / messages の sha256 を凍結値と照合する。外れたら送らずに停止する。記録の ``seed`` /
  ``prompt_sha256`` は送った body から取る。
* **meta.json** は送った body の観測値から組み立てる (凍結定数を写さない)。
* **来歴** は ``provenance.json`` と ``attempts.jsonl`` に分ける。判定には使わない。
* **起動の前提**。``main`` は driver の変異 certification (``results/driver_mutation.json``) が現在の driver・
  test と一致し、固定ファイルが commit 済みで HEAD と一致し、凍結 v2 / v3 manifest の検査が通らなければ
  起動しない。preflight (Ollama の応答・凍結 model の digest) は run dir を作る前に行う。実走後に digest が
  変わっていれば ``aborted``。
* **来歴の異常は aborted**。送った要求条件が凍結値と違う・実走中に driver が変わった・凍結 model 以外の名前で
  応答した場合は、記録が揃っていても ``exit_reason = aborted`` にする。
* **判定の読み方**。``provenance.json`` が無い、または ``exit_reason`` が completed / c0_gate 以外の run は、
  run.sh の出力に関わらず not_computed として扱い verdict を書かない。これは
  ``scripts/skill_experience_run_gate.py`` が機械的に検査し、run.sh の前に通す。
* **やり直し** (DE-R7)。provenance が無い・transport_failure・aborted の run だけ、samples を開かずに user 裁定で
  退避してやり直せる (最大 2 回、退避した run は全て残し報告する)。completed / c0_gate の run はやり直さない。

実行 (repo root から、GPU 実走は user 裁定の後)::

    uv run python scripts/skill_experience_driver.py \\
        --run-dir experiments/20260926-experience-skill-pilot/results/run
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
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

from erre_sandbox.inference.ollama_adapter import (  # noqa: E402
    ChatMessage,
    ChatResponse,
    OllamaChatClient,
    OllamaUnavailableError,
)
from erre_sandbox.inference.sampling import ResolvedSampling  # noqa: E402
from scripts import skill_experience_battery as bat  # noqa: E402
from scripts import skill_experience_scorer as sc  # noqa: E402
from scripts import skill_lever_battery as v2bat  # noqa: E402
from scripts.skill_lever_scorer import messages_sha256  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Sequence

_EXP_DIR: Final[pathlib.Path] = (
    _REPO_ROOT / "experiments" / "20260926-experience-skill-pilot"
)
DEFAULT_RUN_DIR: Final[pathlib.Path] = _EXP_DIR / "results" / "run"
DEFAULT_ENDPOINT: Final[str] = "http://127.0.0.1:11434"
_MANIFEST: Final[pathlib.Path] = _EXP_DIR / "manifest.json"

RESENDS: Final[int] = 3  # 同じ seed での再送回数 (送信は初回と合わせて最大 4 回)
BACKOFF_S: Final[float] = 5.0
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

Key = tuple[str, int, int, int]  # (arm, replicate, probe 番号, k)


# ---------------------------------------------------------------- 順序 (§2.4)


def c0_schedule() -> list[Key]:
    return [
        (bat.ARM_C0, r, qi, k)
        for r in range(sc.FROZEN_R)
        for qi in range(len(v2bat.lever_probes()))
        for k in range(sc.FROZEN_K)
    ]


def state_schedule() -> list[Key]:
    out: list[Key] = []
    for r in range(sc.FROZEN_R):
        for qi in range(len(v2bat.lever_probes())):
            for k in range(sc.FROZEN_K):
                arms = sc.block_arm_order(sc.call_block(r, qi, k))
                out.extend((arm, r, qi, k) for arm in arms)
    return out


def schedule() -> list[Key]:
    """run 全体の呼び出し順 (C0 の 240 → 状態 arm の 1,920)。index = call_index."""
    return c0_schedule() + state_schedule()


# ------------------------------------------------------ 送った body の照合


class SentBodyMismatchError(RuntimeError):
    """送ろうとした body が凍結要求と違う。httpx 例外でないので adapter に包まれず、再送もされない."""


def _exact(got: object, want: object) -> bool:
    """型まで一致 (False == 0、4096.0 == 4096 を通さない)."""
    return type(got) is type(want) and got == want


def check_sent_body(body: object, key: Key) -> None:
    """送信前の wire body を凍結値と照合する。外れたら ``SentBodyMismatchError``."""
    arm, r, qi, k = key
    seed, sha = sc.expected_sample(arm, r, qi, k)
    problems: list[str] = []
    if not isinstance(body, dict) or set(body) != BODY_KEYS:
        msg = f"{key}: body keys differ from {sorted(BODY_KEYS)}"
        raise SentBodyMismatchError(msg)
    if not _exact(body["model"], v2bat.MODEL):
        problems.append(f"model={body['model']!r}")
    if not _exact(body["think"], v2bat.THINK):
        problems.append(f"think={body['think']!r}")
    if not _exact(body["stream"], False):
        problems.append(f"stream={body['stream']!r}")
    opts = body["options"]
    if not isinstance(opts, dict) or set(opts) != OPTION_KEYS:
        problems.append(f"options keys differ from {sorted(OPTION_KEYS)}")
    else:
        want = {
            "seed": seed,
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
    if messages_sha256(body["messages"]) != sha:
        problems.append("messages differ from the frozen renderer")
    if problems:
        msg = f"{key}: " + "; ".join(problems)
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
        self.expected: Key | None = None
        self.sent: list[dict[str, Any]] = []
        self.last_content_type: str | None = None

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        is_post = request.method == "POST"
        if is_post:
            if request.url.path != "/api/chat":
                msg = f"unexpected POST path {request.url.path!r}"
                raise SentBodyMismatchError(msg)
            if self.expected is None:
                msg = "chat request without an expected key"
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
    samples_fh: TextIO
    attempts_fh: TextIO
    observer: ObservingTransport
    llm: OllamaChatClient
    backoff_s: float
    call_index: int = 0
    records: list[sc.Sample] = field(default_factory=list)
    response_models: set[str] = field(default_factory=set)
    n_length: int = 0
    resends: int = 0
    meta_written: bool = False


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _write_line(fh: TextIO, obj: dict[str, Any]) -> None:
    fh.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")
    fh.flush()
    os.fsync(fh.fileno())


def write_json_durable(path: pathlib.Path, obj: object, *, exclusive: bool) -> None:
    """temp → flush → fsync → replace。exclusive なら既存ファイルを上書きしない."""
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
    """最初に照合を通って送った body の要求条件で meta.json を書く.

    run の途中で process が kill されても meta.json は残る (行の欠けは判定側で not_computed)。
    run 全体の同一性は check_sent_body が全送信で強制し、終了時に observed_meta で再確認する。
    """
    if state.meta_written or not state.observer.sent:
        return
    write_json_durable(
        state.run_dir / "meta.json",
        meta_of(state.observer.sent[0]),
        exclusive=True,
    )
    state.meta_written = True


def request_for(key: Key) -> tuple[list[ChatMessage], dict[str, Any]]:
    arm, r, qi, k = key
    probe = v2bat.lever_probes()[qi]
    msgs = bat.render_messages(arm, probe, v2bat.layout(r))
    options = {
        "seed": v2bat.sample_seed(r, qi, k),
        "num_ctx": v2bat.NUM_CTX,
        "num_predict": v2bat.NUM_PREDICT,
    }
    return [ChatMessage(**m) for m in msgs], options


async def call_with_resend(state: RunState, key: Key) -> tuple[str | None, dict]:
    """同じ要求を最大 1 + RESENDS 回送る。返り値 = (content または None, 最後に送った body).

    ``OllamaUnavailableError`` と、応答の message.content が文字列でない (adapter が str() で
    "None" 等にしてしまう) 場合を transport 失敗として再送する。
    """
    messages, options = request_for(key)
    state.observer.expected = key
    for attempt in range(1 + RESENDS):
        row: dict[str, Any] = {
            "call_index": state.call_index,
            "attempt": attempt,
            "at": _now(),
        }
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
            await asyncio.sleep(state.backoff_s)
    return None, state.observer.sent[-1]


async def run_phase(state: RunState, keys: Sequence[Key]) -> str | None:
    """keys を順に呼ぶ。transport 失敗が解けなければ raw=null を書いて REASON_TRANSPORT."""
    probes = v2bat.lever_probes()
    for key in keys:
        arm, r, qi, k = key
        raw, body = await call_with_resend(state, key)
        sample = sc.Sample(
            call_index=state.call_index,
            arm=arm,
            replicate=r,
            probe_id=probes[qi].probe_id,
            k=k,
            seed=body["options"]["seed"],
            prompt_sha256=messages_sha256(body["messages"]),
            raw=raw,
            parsed=None if raw is None else sc.parse_choice(raw),
        )
        _write_line(state.samples_fh, dataclasses.asdict(sample))
        state.records.append(sample)
        state.call_index += 1
        if state.call_index % 50 == 0:
            _progress(f"[driver] {state.call_index} calls ({_now()})")
        if raw is None:
            return REASON_TRANSPORT
    return None


def _progress(line: str) -> None:
    """進捗表示。stdout が使えない (detached 起動で閉じたハンドル等) ことで run を止めない."""
    try:
        print(line, flush=True)
    except (OSError, ValueError):
        pass


def c0_bottom_rate(records: Sequence[sc.Sample]) -> float:
    """判定と同じ ``bottom_rates`` で C0 の ⊥ 率 (C0 の全 key が揃っている前提)."""
    choices: dict[tuple[str, int, str], list[str | None]] = {}
    for s in sorted(records, key=lambda x: x.k):
        if s.arm == bat.ARM_C0:
            choices.setdefault((s.arm, s.replicate, s.probe_id), []).append(s.parsed)
    return float(sc.bottom_rates(choices, (bat.ARM_C0,), sc.FROZEN_R)[0])


def prepare_run_dir(run_dir: pathlib.Path) -> None:
    """再開しない: 既に何かがある dir では起動しない."""
    if run_dir.exists() and any(run_dir.iterdir()):
        msg = f"run dir is not empty (no resume): {run_dir}"
        raise FileExistsError(msg)
    run_dir.mkdir(parents=True, exist_ok=True)


def _sha256(path: pathlib.Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _git(*args: str) -> str | None:
    """git の stdout。実行できなければ None (「clean」に畳まない)."""
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
    "scripts/skill_experience_driver.py",
    "scripts/skill_experience_describe.py",
    "scripts/skill_experience_run_gate.py",
    "scripts/skill_experience_driver_mutation_check.py",
    "scripts/skill_experience_evaluate.py",
    "scripts/skill_experience_manifest.py",
    "scripts/skill_lever_manifest.py",
    "experiments/20260926-experience-skill-pilot/manifest.json",
    "experiments/20260926-experience-skill-pilot/prereg.md",
    "experiments/20260926-experience-skill-pilot/run.sh",
    "experiments/20260926-experience-skill-pilot/SEED",
    "experiments/20260926-skill-lever-pilot/manifest.json",
    "experiments/20260926-skill-lever-pilot/results/run/results.json",
    "scripts/skill_experience_battery.py",
    "scripts/skill_experience_scorer.py",
    "scripts/skill_lever_battery.py",
    "scripts/skill_lever_scorer.py",
    "scripts/stage_b_battery.py",
    "scripts/stage_b_scorer.py",
    "src/erre_sandbox/inference/ollama_adapter.py",
    "src/erre_sandbox/inference/sampling.py",
    "experiments/20260926-experience-skill-pilot/results/driver_mutation.json",
)
DRIVER_CERT: Final[pathlib.Path] = _EXP_DIR / "results" / "driver_mutation.json"
_DRIVER_TESTS: Final[pathlib.Path] = (
    _REPO_ROOT / "tests" / "test_skill_experience_driver"
)
# 判定 (run.sh) が最初に照合する凍結 manifest。実走前にも照合し、判定で拒否される run に GPU を使わない
MANIFEST_CHECKS: Final[tuple[str, ...]] = (
    "scripts/skill_lever_manifest.py",
    "scripts/skill_experience_manifest.py",
)


CERTIFIED_SCRIPTS: Final[tuple[str, ...]] = (
    "skill_experience_driver.py",
    "skill_experience_describe.py",
    "skill_experience_run_gate.py",
    "skill_experience_driver_mutation_check.py",
)


def certified_files() -> dict[str, str | None]:
    """driver 変異試験の certification が結び付くファイルの sha256 (変異対象・harness・test)."""
    here = pathlib.Path(__file__).resolve().parent
    out = {name: _sha256(here / name) for name in CERTIFIED_SCRIPTS}
    for p in sorted(_DRIVER_TESTS.glob("*.py")):
        out[f"tests/{p.name}"] = _sha256(p)
    return out


def driver_certification_problems(cert: pathlib.Path) -> list[str]:
    """driver の変異試験が全 KILLED で、記録 sha256 が現在の driver・test と一致すること."""
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
    """凍結 v2 / v3 manifest の検査 (run.sh と同じ script) が ``MANIFEST OK`` で終わること."""
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


async def run(
    run_dir: pathlib.Path,
    transport: httpx.AsyncBaseTransport,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    backoff_s: float = BACKOFF_S,
) -> str:
    """1 run を実行し、終了理由を返す.

    preflight は run dir を作る前 (失敗しても何も書かない)。非 transport の例外は provenance を
    書いてから再送出する。
    """
    observer = ObservingTransport(transport)
    async with httpx.AsyncClient(
        base_url=endpoint, transport=observer, timeout=TIMEOUT_S
    ) as http:
        env = await preflight(http)
        prepare_run_dir(run_dir)
        return await _run_prepared(run_dir, http, observer, env, endpoint, backoff_s)


async def _run_prepared(  # noqa: PLR0913
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
    try:
        llm = OllamaChatClient(model=v2bat.MODEL, client=http, timeout=TIMEOUT_S)
        with (
            (run_dir / "samples.jsonl").open("x", encoding="utf-8", newline="\n") as sf,
            (run_dir / "attempts.jsonl").open(
                "x", encoding="utf-8", newline="\n"
            ) as af,
        ):
            state = RunState(run_dir, sf, af, observer, llm, backoff_s)
            stop = await run_phase(state, c0_schedule())
            if stop is None:
                c0_rate = c0_bottom_rate(state.records)
                if c0_rate > sc.BOT_MAX:
                    stop = REASON_C0_GATE
            if stop is None:
                stop = await run_phase(state, state_schedule())
        # 実走中に重みが差し替わっていないこと (tag の再 pull 等)
        digest_end = (await preflight(http))["model_digest"]
        if digest_end != env["model_digest"]:
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
            "n_samples": 0 if state is None else len(state.records),
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
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=pathlib.Path, default=DEFAULT_RUN_DIR)
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    args = ap.parse_args(argv)
    problems = launch_problems()
    if problems:
        for p in problems:
            print(f"[driver] refuse to launch: {p}", flush=True)
        return EXIT_CODES[REASON_ABORTED]
    try:
        reason = asyncio.run(
            run(args.run_dir, httpx.AsyncHTTPTransport(), endpoint=args.endpoint)
        )
    except Exception as exc:  # noqa: BLE001 — 終了理由は provenance.json に書いてある
        print(f"[driver] aborted: {type(exc).__name__}: {exc}", flush=True)
        return EXIT_CODES[REASON_ABORTED]
    print(f"[driver] exit_reason={reason}", flush=True)
    return EXIT_CODES[reason]


if __name__ == "__main__":
    sys.exit(main())
