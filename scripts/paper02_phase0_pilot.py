#!/usr/bin/env python
"""論文 02 Phase 0 — verdict-blind feasibility pilot (2 個目モデルの実行可能性実測).

正典 = ``.steering/20260912-paper02-phase0/design-final.md``。
上位の不可侵 ADR = ``.steering/20260912-paper02-route/design-final.md`` §3。

この driver が測るのは **実行可能性だけ** である。verdict は計算しない。
PCI RR の Level 制では **結論 (または likely conclusion) を知ってしまうと
Level 0 = 対象外**になり Registered Report が恒久的に出せなくなるため、
禁止 P-1〜P-4 を *方針* ではなく *装置* で強制する。

禁止と、それを不可能にしている機構:

* **P-1** scorer を適用しない
  → :func:`install_scorer_import_guard` (実行時) / :func:`scorer_import_source_hits`
    (静的 AST) / :func:`imports_scorer_at_runtime` (subprocess の推移的 import)
* **P-2** ``T_on`` / ``T_off`` の対比を計算しない
  → :class:`_ProjectingChatClient` が **LLM の seam で** 応答を
    :class:`PilotDraw` (bool 2 つ) に射影し、``condition`` / ``frozen_ctx_id`` /
    zone 同一性 / ``raw_response`` を系から消す。``run_bank_mloop`` が組み立てる
    record には draw 情報が 1 ビットも入らない (全 draw が同一の scrubbed 応答)
* **P-3** ``rho_hat`` / power / permutation / entropy の判定を出さない
  → 成果物が **フラットなスカラの辞書** で、内訳の入れ物が存在しない
* **P-4** 集計は pooled のみ
  → 同上 + キー集合が whitelist と完全一致することを
    :func:`assert_verdict_blind` が書き出し直前に検査する

``src/erre_sandbox/**`` は 1 行も触らない (sibling driver = Option A)。
生 draw はディスクに書かない。したがって **byte 一致の replay-verify は
構造的に不可能**であり、それは blinding の代償として受けている
(``experiments/20260912-paper02-phase0/env.md``)。
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Self

import httpx

from erre_sandbox.cognition.parse import parse_llm_plan
from erre_sandbox.inference.ollama_adapter import (
    ChatMessage,
    ChatResponse,
    OllamaChatClient,
)
from erre_sandbox.inference.sampling import ResolvedSampling
from erre_sandbox.integration.embodied import handoff
from erre_sandbox.integration.embodied.bank import (
    BankRecordReplayClient,
    run_bank_mloop,
)
from erre_sandbox.integration.embodied.bank_fixtures import (
    BANK_LAMBDA_CTX,
    FrozenContext,
    build_competing_cue_substrate,
    run_provenance_pass,
)
from erre_sandbox.memory import EmbeddingClient, MemoryStore
from erre_sandbox.schemas import Zone

if TYPE_CHECKING:
    from collections.abc import Callable

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
_EXPERIMENT_DIR: Final[Path] = _REPO_ROOT / "experiments" / "20260912-paper02-phase0"
_DEFAULT_OUT_DIR: Final[Path] = _EXPERIMENT_DIR / "results"

PILOT_SCHEMA_VERSION: Final[str] = "paper02-phase0-pilot-1"

SCORER_MODULE: Final[str] = "erre_sandbox.integration.embodied.bank_scorer"
SCORER_NEEDLE: Final[str] = "bank_scorer"

PILOT_MODULE: Final[str] = "scripts.paper02_phase0_pilot"
"""陰性対照 = この driver 自身。"""

CPROPER_MODULE: Final[str] = "scripts.ecl_bank_cproper_capture"
"""**陽性対照。** この既存 driver は実際に ``bank_scorer`` を import している。
検査器は「cproper=陽性 / pilot=陰性」の**両方**を言えなければ壊れている
(DA-P0-2)。"""

_FIXED_CLOCK: Final[datetime] = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
_PROBE_SAMPLING: Final[ResolvedSampling] = ResolvedSampling(
    temperature=0.7, top_p=0.9, repeat_penalty=1.1
)

# provenance pass の mock 応答。parse される destination は下流で読まれないので
# (上位 §S0)、固定値で provenance を決定的にする。cproper driver と同一。
_PROVENANCE_PLAN_JSON: Final[str] = json.dumps(
    {
        "thought": "which zone calls to me?",
        "utterance": "bank provenance pass",
        "destination_zone": Zone.STUDY.value,
        "animation": "walk",
    }
)

_SCRUBBED_RESPONSE: Final[str] = json.dumps(
    {
        "thought": "scrubbed",
        "utterance": None,
        "destination_zone": None,
        "animation": None,
    }
)
"""``_ProjectingChatClient`` が M-loop へ返す固定応答。

実応答は seam で :class:`PilotDraw` へ射影された直後に捨てられ、M-loop には
**この定数だけ**が流れる。したがって ``run_bank_mloop`` が組み立てる
``BankLlmCallRecord`` 列は全 draw が同一で、draw 情報を一切持たない。
zone 名を含まない形にしてある。"""

_SCRUBBED_MODEL_TAG: Final[str] = "phase0-scrubbed"


# --------------------------------------------------------------------------- #
# 例外
# --------------------------------------------------------------------------- #


class ScorerImportError(RuntimeError):
    """P-1 違反 — scorer が import されようとした / 既に import されている。"""


class VerdictBlindError(RuntimeError):
    """P-2/P-3/P-4 違反 — 成果物が verdict-blind の形をしていない。"""


# --------------------------------------------------------------------------- #
# G1 — 実行時 import guard
# --------------------------------------------------------------------------- #


class _ScorerBlockingFinder:
    """``sys.meta_path`` 先頭に挿して scorer の import を raise させる finder。

    ``importlib.abc.MetaPathFinder`` を継承しない素の object にしてある —
    この driver は ``importlib`` を AST レベルで持たない (G2b) ため。
    """

    def find_spec(
        self,
        fullname: str,
        _path: Sequence[str] | None = None,
        _target: object | None = None,
    ) -> None:
        if SCORER_NEEDLE in fullname:
            raise ScorerImportError(
                f"P-1 violation: refusing to import {fullname!r} in the Phase 0 pilot"
            )


def install_scorer_import_guard() -> Callable[[], None]:
    """scorer を import できなくする。戻り値で uninstall できる。

    install 時に **既に import 済み**なら、その時点で :class:`ScorerImportError`
    を送出する (``sys.modules`` cache は finder を迂回するため、
    後から挿しても遅い)。
    """
    already = [name for name in sys.modules if SCORER_NEEDLE in name]
    if already:
        raise ScorerImportError(
            f"P-1 violation: scorer already imported before the guard: {already!r}"
        )
    finder = _ScorerBlockingFinder()
    sys.meta_path.insert(0, finder)

    def _uninstall() -> None:
        if finder in sys.meta_path:
            sys.meta_path.remove(finder)

    return _uninstall


# --------------------------------------------------------------------------- #
# G2 / G2b — 静的 AST 検査
# --------------------------------------------------------------------------- #


def scorer_import_source_hits(source_path: Path) -> tuple[str, ...]:
    """``source_path`` の ``Import`` / ``ImportFrom`` に現れる scorer 参照を返す。

    空 = 違反なし。**文字列定数は見ない** — この driver 自身が
    ``SCORER_NEEDLE`` / docstring / G3 の子プロセス用スニペットという形で
    ``"bank_scorer"`` を正当に名指しており、文字列まで走査すると
    **guard が自分自身を陽性と判定してしまう** (2026-09-12 実測)。

    文字列経由の動的 import は、この関数ではなく
    :func:`dynamic_import_source_hits` (機構そのものを AST で禁止) と
    :func:`install_scorer_import_guard` (実行時) と
    :func:`imports_scorer_at_runtime` (推移的) の 3 枚で閉じている。
    """
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            hits.extend(a.name for a in node.names if SCORER_NEEDLE in a.name)
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and SCORER_NEEDLE in node.module
        ):
            hits.append(node.module)
    return tuple(hits)


_DYNAMIC_IMPORT_NAMES: Final[frozenset[str]] = frozenset(
    {"importlib", "__import__", "exec", "eval"}
)


def dynamic_import_source_hits(source_path: Path) -> tuple[str, ...]:
    """``source_path`` が動的 import / 実行機構を **AST として** 持つかを返す。

    文字列定数は見ない — :func:`imports_scorer_at_runtime` が子プロセスへ渡す
    スニペットは ``importlib`` を含む文字列定数としてこの driver に埋め込まれる
    ため、そこまで弾くと自家中毒になる (design-final.md §2 G2b)。
    """
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            hits.extend(
                a.name
                for a in node.names
                if a.name.split(".")[0] in _DYNAMIC_IMPORT_NAMES
            )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.split(".")[0] in _DYNAMIC_IMPORT_NAMES
        ):
            hits.append(node.module)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _DYNAMIC_IMPORT_NAMES
        ):
            hits.append(node.func.id)
    return tuple(hits)


# --------------------------------------------------------------------------- #
# G3 — 実行時 (推移的) import 検査
# --------------------------------------------------------------------------- #

_RUNTIME_PROBE: Final[str] = (
    "import importlib, sys; "
    "importlib.import_module(sys.argv[1]); "
    "print(any('bank_scorer' in m for m in sys.modules))"
)


def imports_scorer_at_runtime(module_name: str) -> bool:
    """``module_name`` を子プロセスで import し、scorer が載るかを返す。

    静的検査 (G2) と違い **推移的** — 対象 module が間接的に scorer を引き込む
    場合も捕まえる。子プロセスで測るのは、親の pytest session が既に
    cproper 経由で scorer を import していることがあるため。
    """
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _RUNTIME_PROBE, module_name],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        encoding="utf-8",
        env=env,
        check=True,
    )
    return completed.stdout.strip() == "True"


# --------------------------------------------------------------------------- #
# G5 — 情報消去 (射影)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class PilotDraw:
    """1 draw から残す **すべて**。

    ``condition`` / ``frozen_ctx_id`` / zone 同一性 / ``raw_response`` は
    ここに入る場所が無い。per-context も per-condition も zone ヒストグラムも
    **型として書けない**のが、P-2/P-3/P-4 に対する構造的な防御である。
    """

    plan_parsed: bool
    zone_present: bool


def project_response(content: str) -> PilotDraw:
    """LLM の生応答を :class:`PilotDraw` へ射影する (情報消去が起きる関数)。

    3 状態を区別する:

    * 妥当な JSON + zone あり → ``(True, True)``
    * 妥当な JSON + ``destination_zone: null`` → ``(True, False)``
    * parse 不能 → ``(False, False)``

    ``BankLlmCallRecord.pre_bias_destination_zone`` は後ろ 2 つを両方 ``None``
    に潰すので、pilot は自前 parse で分ける (Codex MEDIUM-2)。
    """
    plan = parse_llm_plan(content)
    return PilotDraw(
        plan_parsed=plan is not None,
        zone_present=plan is not None and plan.destination_zone is not None,
    )


# --------------------------------------------------------------------------- #
# G4 — 書き出し直前の verdict-blind gate
# --------------------------------------------------------------------------- #

FORBIDDEN_TOKENS: Final[tuple[str, ...]] = (
    "rho",
    "power",
    "permutation",
    "entropy",
    "t_on",
    "t_off",
    "tv_bar",
    "tv_pool",
    "verdict",
    "per_context",
    "per_ctx",
    "condition",
    "histogram",
    "by_zone",
    "study",
    "peripatos",
    "chashitsu",
    "agora",
    "garden",
)

_PRIMARY_ONLY_KEYS: Final[frozenset[str]] = frozenset(
    {"plan_parse_band", "zone_present_band"}
)

_COMMON_KEYS: Final[frozenset[str]] = frozenset(
    {
        "pilot_schema_version",
        "role",
        "model",
        "model_digest",
        "model_size_bytes",
        "ollama_version",
        "ollama_ps_size",
        "ollama_ps_processor",
        "think_false_accepted",
        "think_omitted_accepted",
        "think_probe_status",
        "gpu_name",
        "gpu_total_mib",
        "gpu_baseline_used_mib",
        "gpu_peak_used_mib",
        "k_contexts",
        "m_draws",
        "n_draws",
        "latency_ms_mean",
        "latency_ms_p50",
        "latency_ms_p95",
        "wall_seconds",
        "seconds_per_draw",
        "projected_hours_9600_draws",
        "env_python",
        "env_pydantic",
        "env_httpx",
        "env_zone_bias_p",
        "platform",
        "uv_lock_sha256",
        "captured_at_utc",
    }
)

ALLOWED_KEYS: Final[Mapping[str, frozenset[str]]] = {
    "primary": _COMMON_KEYS | _PRIMARY_ONLY_KEYS,
    # reference アーム (`qwen3:8b`) は Phase 3 の control そのものなので、
    # parse 挙動を見ると R5 の予備結果を覗くことになる (Codex HIGH-3)。
    # → parse 系は射影自体を行わず、キーも持たない。
    "reference": _COMMON_KEYS,
}

THINK_PROBE_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "accepted",
        "rejected_http_error",
        "rejected_timeout",
        "unavailable",
        "parse_error",
        "other",
    }
)


ARTIFACT_LEAK_TOKENS: Final[tuple[str, ...]] = (
    "study",
    "peripatos",
    "chashitsu",
    "agora",
    "garden",
    "raw_response",
    "pre_bias_destination_zone",
    "frozen_ctx_id",
    "mc_index",
)
"""成果物ツリー走査 (G6) 用の、**より狭い** token 集合。

G4 (`FORBIDDEN_TOKENS`) は機械生成の payload を守るので、`verdict` や `power` の
ような語が現れたら即バグである。一方 G6 は**人間が書いた散文**を守る。
散文は blinding 設計そのものを説明する必要があり、そこで `verdict` や `power`
という語を使えないと記述が成立しない。**散文における危険は語彙ではなく
「draw のデータを貼ること」**なので、G6 は zone 名と生 record のフィールド名に
絞る (Codex HIGH-2 の趣旨 = raw response / prompt / zone 名の混入防止)。
"""


def forbidden_token_hits(
    text: str, tokens: Sequence[str] = FORBIDDEN_TOKENS
) -> tuple[str, ...]:
    """``text`` に現れた禁止語を返す (空 = 違反なし)。

    G4 の禁止語判定と、成果物ツリー全走査 (G6) が **同じ関数**を使う
    (負例は必ずこの判定を通る)。``tokens`` を差し替えて用途を分ける。
    """
    lowered = text.lower()
    return tuple(token for token in tokens if token in lowered)


def artifact_tree_leak_hits(root: Path) -> tuple[str, ...]:
    """``root`` 配下の全テキストファイルを走査し、``"<path>: <token>"`` を返す。

    動的 artifact (JSON) だけでなく、手書きの markdown も対象にする
    (Codex HIGH-2)。読めないファイル (binary) は読み飛ばさず **違反として扱う**
    — pilot の成果物に binary が生まれる経路は無いため。
    """
    hits: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            hits.append(f"{rel}: <unreadable-as-utf8>")
            continue
        hits.extend(
            f"{rel}: {token}"
            for token in forbidden_token_hits(text, ARTIFACT_LEAK_TOKENS)
        )
    return tuple(hits)


def assert_verdict_blind(payload: Mapping[str, object], *, role: str) -> None:
    """成果物が verdict-blind の形をしていなければ :class:`VerdictBlindError`。

    5 つの独立した判定を順に行う (どれを消しても対応する負例 test が落ちる):

    1. 平坦性 — 値に ``Mapping`` が現れない
    2. スカラ性 — 値は ``str`` / ``int`` / ``float`` / ``bool`` / ``None`` のみ
    3. 有限性 — ``float`` は有限 (``NaN`` / ``inf`` を弾く)
    4. キー集合 — whitelist と **完全一致** (過不足の両方を弾く)
    5. 禁止語 — キーと ``str`` 値に禁止語が現れない
    """
    allowed = ALLOWED_KEYS.get(role)
    if allowed is None:
        raise VerdictBlindError(f"unknown role: {role!r}")

    for key, value in payload.items():
        if isinstance(value, Mapping):
            raise VerdictBlindError(f"nested mapping under {key!r} — breaks flatness")
        if not isinstance(value, (str, int, float, bool, type(None))):
            raise VerdictBlindError(
                f"non-scalar value under {key!r} ({type(value).__name__}) — "
                "breakdowns must be unrepresentable"
            )
        if isinstance(value, float) and not math.isfinite(value):
            raise VerdictBlindError(f"non-finite float under {key!r}: {value!r}")

    actual = set(payload)
    if actual != set(allowed):
        missing = sorted(set(allowed) - actual)
        extra = sorted(actual - set(allowed))
        raise VerdictBlindError(
            f"key set mismatch for role {role!r}: missing={missing} extra={extra}"
        )

    for key, value in payload.items():
        hits = forbidden_token_hits(key)
        if hits:
            raise VerdictBlindError(f"forbidden token(s) {hits} in key {key!r}")
        if isinstance(value, str):
            hits = forbidden_token_hits(value)
            if hits:
                raise VerdictBlindError(
                    f"forbidden token(s) {hits} in the value of {key!r}"
                )


# --------------------------------------------------------------------------- #
# バンド化 (実数を出さない)
# --------------------------------------------------------------------------- #

BAND_LOW: Final[float] = 0.2
BAND_HIGH: Final[float] = 0.8


def rate_band(rate: float) -> str:
    """割合を 3 段のバンドへ落とす。**実数は出さない。**

    境界を 0.2 / 0.8 に置いているのは、上位 ADR §4.5 の R4 分岐が
    pooled ``none_rate > 0.5`` を条件に含むため — **0.5 に境界を置かない**ことで
    バンド値が R4 の閾値と直接一致しないようにしている (DA-P0-10)。
    """
    if rate < BAND_LOW:
        return "lt_0.2"
    if rate < BAND_HIGH:
        return "0.2_to_0.8"
    return "gte_0.8"


# --------------------------------------------------------------------------- #
# 射影する chat client (I-1 が起きる場所)
# --------------------------------------------------------------------------- #


class _ProjectingChatClient:
    """実 Ollama を叩き、応答を **その場で** 射影して scrubbed 応答を返す。

    ``run_bank_mloop`` は本番と同一の経路で回るが、この client を通した後の
    応答は全 draw で同一 (:data:`_SCRUBBED_RESPONSE`) なので、M-loop が
    組み立てる record 列は draw 情報を 1 ビットも持たない。

    ``collect_parse=False`` (role=reference) では :class:`PilotDraw` を
    **一切作らない** — parse 率が系のどこにも生じない。
    """

    def __init__(self, inner: Any, *, collect_parse: bool) -> None:
        self._inner = inner
        self._collect_parse = collect_parse
        self._latencies_s: list[float] = []
        self._draws: list[PilotDraw] = []
        self.calls = 0

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        sampling: ResolvedSampling,
        model: str | None = None,
        options: dict[str, Any] | None = None,
        think: bool | None = None,
    ) -> ChatResponse:
        started = time.perf_counter()
        response = await self._inner.chat(
            messages, sampling=sampling, model=model, options=options, think=think
        )
        self._latencies_s.append(time.perf_counter() - started)
        self.calls += 1
        if self._collect_parse:
            self._draws.append(project_response(response.content))
        if self.calls % 20 == 0:
            # 通し本数だけ。context / 条件 / zone は出さない (Codex MEDIUM-4)。
            print(f"[pilot] draw {self.calls}")
        return ChatResponse(
            content=_SCRUBBED_RESPONSE,
            model=_SCRUBBED_MODEL_TAG,
            eval_count=0,
            total_duration_ms=0.0,
        )

    async def close(self) -> None:
        close = getattr(self._inner, "close", None)
        if callable(close):
            await close()

    @property
    def latencies_ms_sorted(self) -> tuple[float, ...]:
        """昇順の latency (ms)。**ソート済** — 呼び出し順を持ち越さない。"""
        return tuple(sorted(v * 1000.0 for v in self._latencies_s))

    @property
    def draws(self) -> tuple[PilotDraw, ...]:
        return tuple(self._draws)


# --------------------------------------------------------------------------- #
# provenance mock (Ollama 非消費 — 実 spend は M-loop だけ)
# --------------------------------------------------------------------------- #


def _mock_embedding() -> EmbeddingClient:
    vec = [0.01] * EmbeddingClient.DEFAULT_DIM

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        inputs = body.get("input") or []
        count = len(inputs) if isinstance(inputs, list) else 1
        return httpx.Response(httpx.codes.OK, json={"embeddings": [vec] * count})

    return EmbeddingClient(
        client=httpx.AsyncClient(
            base_url=EmbeddingClient.DEFAULT_ENDPOINT,
            transport=httpx.MockTransport(handler),
        )
    )


def _store_factory() -> MemoryStore:
    return MemoryStore(db_path=":memory:")


class _ProvenanceMockChat:
    async def chat(self, *_args: Any, **_kwargs: Any) -> ChatResponse:
        return ChatResponse(
            content=_PROVENANCE_PLAN_JSON,
            model="bank-provenance-mock",
            eval_count=1,
            total_duration_ms=0.0,
        )


async def _build_frozen_contexts(*, k: int) -> tuple[FrozenContext, ...]:
    """cproper と **同一手順・同一 id** で凍結 context を作る。

    prompt が本番と byte 一致するので、pilot の parse 実測が本番の
    parse 実測の予測になる。
    """
    contexts: list[FrozenContext] = []
    for i in range(k):
        substrate = build_competing_cue_substrate(context_id=f"cproper-ctx-{i}")
        embedding = _mock_embedding()
        try:
            frozen = await run_provenance_pass(
                substrate=substrate,
                inner_chat=_ProvenanceMockChat(),
                store_factory=_store_factory,
                embedding=embedding,
                run_id=f"phase0-provenance-{i}",
                retrieval_now=_FIXED_CLOCK,
                base_ts=_FIXED_CLOCK,
                lambda_ctx=BANK_LAMBDA_CTX[0],
                seed=i,
            )
        finally:
            await embedding.close()
        contexts.append(frozen)
    return tuple(contexts)


# --------------------------------------------------------------------------- #
# preflight (digest / version / GPU)
# --------------------------------------------------------------------------- #


def _run_text(cmd: Sequence[str]) -> str:
    try:
        completed = subprocess.run(  # noqa: S603
            list(cmd), capture_output=True, encoding="utf-8", check=False
        )
    except OSError:
        return ""
    return completed.stdout or ""


def ollama_version() -> str:
    text = _run_text(["ollama", "--version"]).strip()
    match = re.search(r"(\d+\.\d+\.\d+)", text)
    return match.group(1) if match else "unknown"


def gpu_info() -> tuple[str, int]:
    text = _run_text(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total",
            "--format=csv,noheader,nounits",
        ]
    ).strip()
    if not text:
        return ("unknown", 0)
    name, _, total = text.splitlines()[0].partition(",")
    try:
        total_mib = int(total.strip())
    except ValueError:
        total_mib = 0
    return (name.strip(), total_mib)


def gpu_used_mib() -> int:
    text = _run_text(
        ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"]
    ).strip()
    if not text:
        return 0
    try:
        return int(text.splitlines()[0].strip())
    except ValueError:
        return 0


def ollama_ps_row(model: str) -> tuple[str, str]:
    """``ollama ps`` から ``(SIZE, PROCESSOR)`` を返す。

    ``PROCESSOR`` が ``100% GPU`` でなければ CPU へこぼれている = 載っていない。
    """
    for line in _run_text(["ollama", "ps"]).splitlines():
        if line.startswith(model):
            cells = re.split(r"\s{2,}", line.strip())
            if len(cells) >= 4:  # noqa: PLR2004
                return (cells[2].strip(), cells[3].strip())
    return ("unknown", "unknown")


def model_digest_and_size(model: str) -> tuple[str, int]:
    """``/api/tags`` から full digest と byte size を取る。"""
    try:
        response = httpx.get(
            f"{OllamaChatClient.DEFAULT_ENDPOINT}/api/tags", timeout=15.0
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return ("unknown", 0)
    for entry in response.json().get("models", []):
        if entry.get("name") == model or entry.get("model") == model:
            digest = str(entry.get("digest", "unknown"))
            return (digest.removeprefix("sha256:"), int(entry.get("size", 0)))
    return ("unknown", 0)


def _uv_lock_sha256() -> str:
    lock = _REPO_ROOT / "uv.lock"
    if not lock.is_file():
        return "unknown"
    return hashlib.sha256(lock.read_bytes()).hexdigest()


def unload_all_resident_models() -> tuple[str, ...]:
    """常駐している全モデルを unload し、その名前を返す。

    baseline VRAM を測る前に呼ぶ。**対象モデルだけ** stop すると、直前の run が
    残した別モデルが baseline にも peak にも乗り、「このモデルが何 MiB 使うか」が
    測れない (2026-09-12 実測: reference arm の peak 13617 MiB に primary arm の
    llama3.1 が同居していた)。

    ollama は次の要求で自動的に再 load するので、この unload は破壊的ではない。
    """
    stopped: list[str] = []
    for line in _run_text(["ollama", "ps"]).splitlines()[1:]:
        name = line.split()[0] if line.strip() else ""
        if name:
            _run_text(["ollama", "stop", name])
            stopped.append(name)
    if stopped:
        _wait_for_vram_to_settle()
    return tuple(stopped)


_SETTLE_POLL_S: Final[float] = 0.5
_SETTLE_STABLE_SAMPLES: Final[int] = 4
_SETTLE_TIMEOUT_S: Final[float] = 30.0


def _wait_for_vram_to_settle() -> int:
    """VRAM の解放が落ち着くまで待って、最後に見た値を返す。

    ``ollama stop`` は即座に戻るが unload は非同期なので、直後に測ると
    まだ解放されていない値を掴む (2026-09-12 実測: 直後 7486 MiB /
    数秒後 1623 MiB)。値が下がらなくなるまでポーリングする。
    """
    deadline = time.perf_counter() + _SETTLE_TIMEOUT_S
    last = gpu_used_mib()
    stable = 0
    while time.perf_counter() < deadline and stable < _SETTLE_STABLE_SAMPLES:
        time.sleep(_SETTLE_POLL_S)
        current = gpu_used_mib()
        stable = stable + 1 if current >= last else 0
        last = min(last, current)
    return last


# --------------------------------------------------------------------------- #
# think probe
# --------------------------------------------------------------------------- #

_PROBE_MESSAGES: Final[tuple[ChatMessage, ...]] = (
    ChatMessage(role="system", content="Reply with the single word: ok"),
    ChatMessage(role="user", content="ok"),
)


def _probe_status(exc: BaseException) -> str:
    """例外を **bounded な 1 トークン**へ落とす (メッセージは保存しない)。"""
    name = type(exc).__name__.lower()
    if "timeout" in name:
        return "rejected_timeout"
    if "unavailable" in name:
        return "rejected_http_error"
    if "json" in name or "validation" in name:
        return "parse_error"
    return "other"


async def think_probe(model: str) -> tuple[bool, bool, str]:
    """``think=False`` と ``think`` 省略の 2 通りを 1 回ずつ叩く。

    返り値 = ``(think_false_accepted, think_omitted_accepted, status)``。
    失敗の**全文は console に出す**が、成果物には status トークンしか残さない
    (Codex HIGH-2)。
    """
    status = "accepted"
    think_false_ok = False
    think_omitted_ok = False
    client = OllamaChatClient(model=model, timeout=180.0)
    try:
        try:
            await client.chat(_PROBE_MESSAGES, sampling=_PROBE_SAMPLING, think=False)
            think_false_ok = True
        except Exception as exc:  # noqa: BLE001 — probe は失敗そのものが観測対象
            status = _probe_status(exc)
            print(f"[pilot] think=False probe FAILED: {exc!r}")
        try:
            await client.chat(_PROBE_MESSAGES, sampling=_PROBE_SAMPLING)
            think_omitted_ok = True
        except Exception as exc:  # noqa: BLE001
            if status == "accepted":
                status = _probe_status(exc)
            print(f"[pilot] think-omitted probe FAILED: {exc!r}")
    finally:
        await client.close()
    return (think_false_ok, think_omitted_ok, status)


# --------------------------------------------------------------------------- #
# VRAM sampler
# --------------------------------------------------------------------------- #


class _VramSampler:
    """0.5 s 間隔で ``nvidia-smi`` を叩いて peak を取る。"""

    INTERVAL_S = 0.5

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._peak = 0
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            self._peak = max(self._peak, gpu_used_mib())
            self._stop.wait(self.INTERVAL_S)

    def __enter__(self) -> Self:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=5.0)

    @property
    def peak_mib(self) -> int:
        return self._peak


# --------------------------------------------------------------------------- #
# pooled 集計 → payload
# --------------------------------------------------------------------------- #


def pooled_bands(draws: Sequence[PilotDraw]) -> tuple[str, str]:
    """``PilotDraw`` 列から **バンド 2 つだけ**を作る。

    引数の型に ``condition`` も ``frozen_ctx_id`` も zone 名も無いので、
    per-context / per-condition / zone ヒストグラムは書きようがない。
    """
    if not draws:
        return ("lt_0.2", "lt_0.2")
    n = len(draws)
    return (
        rate_band(sum(d.plan_parsed for d in draws) / n),
        rate_band(sum(d.zone_present for d in draws) / n),
    )


def _percentile(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    idx = min(len(sorted_values) - 1, max(0, round(q * (len(sorted_values) - 1))))
    return sorted_values[idx]


def build_payload(
    *,
    role: str,
    model: str,
    model_digest: str,
    model_size_bytes: int,
    ollama_ver: str,
    ps_size: str,
    ps_processor: str,
    think_false_ok: bool,
    think_omitted_ok: bool,
    think_status: str,
    gpu_name: str,
    gpu_total: int,
    gpu_baseline: int,
    gpu_peak: int,
    k_contexts: int,
    m_draws: int,
    latencies_ms: Sequence[float],
    wall_seconds: float,
    draws: Sequence[PilotDraw],
) -> dict[str, object]:
    """フラットなスカラだけの payload を組む。"""
    n_draws = 2 * m_draws * k_contexts
    seconds_per_draw = wall_seconds / n_draws if n_draws else 0.0
    env = handoff.capture_env_pins()
    packages = env.get("packages", {})
    payload: dict[str, object] = {
        "pilot_schema_version": PILOT_SCHEMA_VERSION,
        "role": role,
        "model": model,
        "model_digest": model_digest,
        "model_size_bytes": model_size_bytes,
        "ollama_version": ollama_ver,
        "ollama_ps_size": ps_size,
        "ollama_ps_processor": ps_processor,
        "think_false_accepted": think_false_ok,
        "think_omitted_accepted": think_omitted_ok,
        "think_probe_status": think_status,
        "gpu_name": gpu_name,
        "gpu_total_mib": gpu_total,
        "gpu_baseline_used_mib": gpu_baseline,
        "gpu_peak_used_mib": gpu_peak,
        "k_contexts": k_contexts,
        "m_draws": m_draws,
        "n_draws": n_draws,
        "latency_ms_mean": round(
            sum(latencies_ms) / len(latencies_ms) if latencies_ms else 0.0, 3
        ),
        "latency_ms_p50": round(_percentile(latencies_ms, 0.50), 3),
        "latency_ms_p95": round(_percentile(latencies_ms, 0.95), 3),
        "wall_seconds": round(wall_seconds, 3),
        "seconds_per_draw": round(seconds_per_draw, 4),
        "projected_hours_9600_draws": round(seconds_per_draw * 9600 / 3600.0, 3),
        "env_python": str(env.get("python", "unknown")),
        "env_pydantic": str(packages.get("pydantic", "unknown")),
        "env_httpx": str(packages.get("httpx", "unknown")),
        "env_zone_bias_p": str(env.get("ERRE_ZONE_BIAS_P", "unset")),
        # ``platform.release()`` は Windows 11 でも "10" を返すので使わない。
        # ``platform.platform()`` は build 番号 (11 は 22000 以上) まで含む。
        "platform": platform.platform(),
        "uv_lock_sha256": _uv_lock_sha256(),
        "captured_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    if role == "primary":
        parse_band, zone_band = pooled_bands(draws)
        payload["plan_parse_band"] = parse_band
        payload["zone_present_band"] = zone_band
    return payload


# --------------------------------------------------------------------------- #
# pilot 本体
# --------------------------------------------------------------------------- #


async def run_pilot(
    *,
    model: str,
    role: str,
    m_draws: int,
    k_contexts: int,
    think_probe_result: tuple[bool, bool, str] = (True, True, "accepted"),
    gpu_baseline: int | None = None,
    inner_chat: Any | None = None,
) -> dict[str, object]:
    """1 モデル分の feasibility pilot を回して payload を返す。

    ``inner_chat`` は M-loop の chat client。既定は実 :class:`OllamaChatClient`
    (これが唯一 live な部分)。テストは決定的な mock を差し込む — この seam は
    live 経路を一切変えない (cproper driver と同じ約束)。

    ``gpu_baseline`` は **モデルを load する前** に測った GPU 使用量。
    :func:`main` が think probe より前に測って渡す — ここで測ると probe が
    既にモデルを常駐させており「baseline」にならない (2026-09-12 の smoke で
    実際に 8291 MiB という load 後の値が入った)。
    """
    collect_parse = role == "primary"
    model_digest, model_size = model_digest_and_size(model)
    ollama_ver = ollama_version()
    gpu_name, gpu_total = gpu_info()
    if gpu_baseline is None:
        gpu_baseline = gpu_used_mib()

    frozen_contexts = await _build_frozen_contexts(k=k_contexts)

    if inner_chat is not None:
        inner: Any = inner_chat
    else:
        inner = OllamaChatClient(model=model, timeout=300.0)
    projecting = _ProjectingChatClient(inner, collect_parse=collect_parse)
    llm = BankRecordReplayClient.for_record(projecting)

    started = time.perf_counter()
    with _VramSampler() as sampler:
        try:
            # 返り値は **参照しない**。scrubbed 応答しか入っていないが、
            # 触らないことを設計の約束として明示する (I-1 / Codex HIGH-1)。
            await run_bank_mloop(
                llm=llm, frozen_contexts=frozen_contexts, m_draws=m_draws
            )
        finally:
            await projecting.close()
    wall_seconds = time.perf_counter() - started

    cap = 2 * m_draws * k_contexts
    if projecting.calls > cap:
        raise RuntimeError(
            f"[pilot] call cap exceeded: {projecting.calls} > {cap} (cost ceiling)"
        )

    ps_size, ps_processor = ollama_ps_row(model)
    think_false_ok, think_omitted_ok, think_status = think_probe_result
    return build_payload(
        role=role,
        model=model,
        model_digest=model_digest,
        model_size_bytes=model_size,
        ollama_ver=ollama_ver,
        ps_size=ps_size,
        ps_processor=ps_processor,
        think_false_ok=think_false_ok,
        think_omitted_ok=think_omitted_ok,
        think_status=think_status,
        gpu_name=gpu_name,
        gpu_total=gpu_total,
        gpu_baseline=gpu_baseline,
        gpu_peak=sampler.peak_mib,
        k_contexts=k_contexts,
        m_draws=m_draws,
        latencies_ms=projecting.latencies_ms_sorted,
        wall_seconds=wall_seconds,
        draws=projecting.draws,
    )


def metrics_filename(role: str, model: str) -> str:
    return f"metrics-{role}-{re.sub(r'[^A-Za-z0-9.]+', '-', model)}.json"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "論文 02 Phase 0 verdict-blind feasibility pilot "
            "(実行可能性のみ。verdict は計算しない)"
        )
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--role", required=True, choices=sorted(ALLOWED_KEYS))
    parser.add_argument("--m-draws", type=int, default=6)
    parser.add_argument("--k-contexts", type=int, default=8)
    parser.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)

    uninstall = install_scorer_import_guard()
    try:
        # baseline は **常駐モデルを全部 unload してから、probe より前に** 測る。
        # probe はモデルを常駐させるので後で測ると load 後の値になり、
        # 他モデルが残っていると peak にそれが混ざる。
        stopped = unload_all_resident_models()
        if stopped:
            print(f"[pilot] unloaded before baseline: {', '.join(stopped)}")
        gpu_baseline = gpu_used_mib()

        # think=False が拒否されるなら draw に入らず止める (Stop 規則)。
        think_false_ok, think_omitted_ok, status = asyncio.run(think_probe(args.model))
        if not think_false_ok:
            print(
                f"[pilot] STOP: think=False rejected by {args.model} "
                f"(status={status}). No artifact written. "
                "モデル選定のやり直しを user 裁定に上げること (上位 ADR §4.8)。"
            )
            return 2
        print(
            f"[pilot] think probe ok (think=False={think_false_ok}, "
            f"omitted={think_omitted_ok}, status={status})"
        )

        payload = asyncio.run(
            run_pilot(
                model=args.model,
                role=args.role,
                m_draws=args.m_draws,
                k_contexts=args.k_contexts,
                think_probe_result=(think_false_ok, think_omitted_ok, status),
                gpu_baseline=gpu_baseline,
            )
        )

        assert_verdict_blind(payload, role=args.role)

        args.out_dir.mkdir(parents=True, exist_ok=True)
        out_path = args.out_dir / metrics_filename(args.role, args.model)
        out_path.write_text(
            handoff.canonical_dumps(payload) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"[pilot] wrote {out_path}")
    finally:
        uninstall()
    return 0


if __name__ == "__main__":
    sys.exit(main())
