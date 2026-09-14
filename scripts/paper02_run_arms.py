#!/usr/bin/env python
"""論文 02 — 前向き 2 アーム実走 driver (control = qwen3:8b / primary = llama3.1:8b).

封印 (``seal/arm-spec.json``、Zenodo deposit 済) が入力・出力・定数をすべて固定して
いる。**このファイルは契約を実装するのであって、設計を作り直すのではない。**

設計原理 (`.steering/20260914-paper02-run-driver/design.md`)::

    封印フィールドの値は run から **観測** して入れる。著者が打ち込んではならない。

著者が打った値は「その事柄が変わらなかった証拠」ではなく「著者が封印値を正しく
打った証拠」にすぎず、``verify_seal.py`` はその 2 つを区別できない。CLI 引数の
default に封印値を置くと検査は構造的に恒真になる。したがって:

* ``ollama_version`` は実走サーバの ``GET /api/version``
* ``model`` は応答が名乗るモデル (``ChatResponse.model``)
* ``model_digest`` は ``GET /api/tags`` の当該 digest
* ``think`` は apparatus が実際に渡した値 (spy で観測。定数を再掲しない)
* ``m_draws`` / ``k_contexts`` / ``context_ids`` は産出物・消費物から数える
* ``bank_checksum`` は **消費した凍結 bank を正規形へ直列化した上で** 再計算
  (ファイル bytes の sha256 ではない — 正規形なので CRLF に影響されない)
* ``sealed_manifest_sha256`` は ``seal/SEAL-MANIFEST.json`` から
  **同ファイルが申告する canonicalisation で** 再計算

``bank_checksum`` の意味論 (本 driver 最大の罠)
-----------------------------------------------
封印値 ``5e991dd63407…`` は完了済 run の ``bank_records.jsonl`` 4,800 行
(qwen3 の raw 応答を含む) の SHA-256 である。``manifest_field_map.shared`` に
置かれている = **両アームが同じ値を出せ**。新しいモデルの新しい draw では再現不能。

→ ``bank_checksum`` は **「消費した凍結 context bank の身元」** であって
**「産出した records の身元」ではない**。封印の
``not_minor_deviations`` = "substituting the frozen context bank" と読みが一致する。

雛形 ``scripts/ecl_bank_cproper_capture.py`` は manifest 直下の同じパスに
**産出 records のハッシュ**を書いている。複製すると正しいパスに間違った量が入り、
``verify_seal --run-manifest`` は必ず落ちる — しかもそれが分かるのは実走の後である。
本 driver は 2 つを別のパスに分ける::

    bank_checksum                          消費した凍結 bank (封印比較対象)
    artifacts["run_records.jsonl"].sha256  この run が産出した records

凍結 apparatus (``bank.py`` / ``bank_fixtures.py`` / ``bank_scorer.py``) と
``experiments/20260710-m13-c-proper/`` は import / read のみ。``src/erre_sandbox/``
は無改変 (sibling driver)。すべての成果物は ``handoff.canonical_dumps`` を通す
(6 桁量子化 = cross-platform libm drift の吸収)。
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, cast

import httpx

from erre_sandbox.inference.ollama_adapter import ChatResponse, OllamaChatClient
from erre_sandbox.inference.sampling import ResolvedSampling
from erre_sandbox.integration.embodied import handoff
from erre_sandbox.integration.embodied.bank import (
    BANK_ANNOTATION_SCHEMA_VERSION,
    BankAnnotationRow,
    BankLlmCallRecord,
    BankRecordReplayClient,
    attach_bank_observables,
    run_bank_mloop,
)
from erre_sandbox.integration.embodied.bank_fixtures import FrozenContext
from erre_sandbox.integration.embodied.bank_power import (
    K_MIN,
    M_MIN,
    N_REPLICATES_DEFAULT,
    POWER_SEED_DEFAULT,
)
from erre_sandbox.integration.embodied.bank_scorer import (
    score_bank_annotation,
    verdict_to_dict,
)
from erre_sandbox.schemas import Zone

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.inference.ollama_adapter import ChatMessage
    from erre_sandbox.integration.embodied.bank import BankCondition

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_PAPER_REPO = _REPO_ROOT.parent / "ERRE-Papers" / "collapsed-decision-space"
_DEFAULT_BANK = (
    _REPO_ROOT
    / "experiments"
    / "20260710-m13-c-proper"
    / "artifacts"
    / "bank_records.jsonl"
)
_DEFAULT_OUT_ROOT = _REPO_ROOT / "experiments" / "20260914-paper02-run" / "artifacts"

#: manifest の ``base_ts`` / ``retrieval_now``。実時刻を持たないのは決定性のため
#: (壁時計は sidecar ``run-metrics.json`` 側)。
_FIXED_CLOCK: Final[datetime] = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

RUN_MANIFEST_VERSION: Final[str] = "paper02-run-1"
_RESOLVED_FROM_TAG: Final[str] = "pre_bias_direct_parse"
_ARMS: Final[tuple[str, ...]] = ("control", "primary")

#: 2.5 時間の連続実行で 1 度でも超えれば全損する。既定の 60 秒では短い
#: (モデル再ロード / GPU の取り合いで実測 60 秒を超えうる)。
_CHAT_TIMEOUT_SECONDS: Final[float] = 300.0

#: 観測 API は短くてよいが、httpx 既定の 5 秒よりは緩める。
_OBSERVE_TIMEOUT_SECONDS: Final[float] = 30.0

#: transport 失敗の有界 retry 回数 (1 回の draw あたり)。
_TRANSPORT_RETRIES: Final[int] = 3
_TRANSPORT_RETRY_BACKOFF_S: Final[float] = 5.0

#: ``OllamaUnavailableError`` は単一型で、理由が文字列に入る。**transport 失敗
#: だけ**を retry する。内容の失敗 (non-JSON / parse 失敗) を retry すると、
#: 見た応答を捨てて引き直すことになり estimand が汚れる — transport 失敗は
#: 「要求が答えられなかった」であって応答の選択ではない。
_RETRIABLE_REASONS: Final[tuple[str, ...]] = (
    "timeout",
    "unreachable",
    "HTTP 502",
    "HTTP 503",
    "HTTP 504",
)

#: ``verify`` の終了コード。**2 を 0 にしない** — 封印検査に落ちた bundle が
#: exit 0 を返すと、緑が「前向き結果である」と読まれる (Codex/code-reviewer H4)。
VERIFY_OK: Final[int] = 0
VERIFY_FAIL: Final[int] = 1
VERIFY_SUB_SEALED: Final[int] = 2

_SEAL_OK: Final[str] = "ok"
_SEAL_FAILED: Final[str] = "failed"
_SEAL_NOT_RUN: Final[str] = "not_run"


class CaptureAbortedError(RuntimeError):
    """実走後のガードで停止する。**生データを道連れにしないための例外**。

    版ドリフト / セル不揃い / context 不一致は、成果物を書く前に停止すべきである。
    しかし素朴に ``SystemExit`` すると **2.5 時間分の raw が診断材料ごと消える**
    (code-reviewer H2)。records を携えて上げ、呼び出し側が隔離保存してから
    非ゼロ終了する。
    """

    def __init__(self, reason: str, records: Sequence[BankLlmCallRecord]) -> None:
        super().__init__(reason)
        self.reason = reason
        self.records = tuple(records)


def _is_retriable(exc: Exception) -> bool:
    message = str(exc)
    return any(reason in message for reason in _RETRIABLE_REASONS)


# --------------------------------------------------------------------------- #
# 封印の読み出し — 値は封印ファイルの bytes から。literal を持たない
# --------------------------------------------------------------------------- #


def load_arm_spec(path: Path) -> dict[str, Any]:
    """封印済 ``arm-spec.json`` を読む。値の正典はこのファイルだけである。"""
    if not path.is_file():
        msg = (
            f"[paper02] 封印契約が見つからない: {path}\n"
            "          --paper-repo で論文 repo を指すこと "
            "(collapsed-decision-space)。"
        )
        raise SystemExit(msg)
    spec = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict):
        msg = f"[paper02] {path} が JSON object でない"
        raise SystemExit(msg)
    return spec


def sealed_manifest_sha256(path: Path) -> str:
    """``SEAL-MANIFEST.json`` の自己ハッシュを **再計算** する。

    記録値 (``self_sha256``) を読むのではなく、同ファイルが
    ``self_hash_canonicalisation`` で申告する手順どおりに計算し、記録値と
    突き合わせる。両者が食い違う封印は内部的に壊れているので、そこで停止する
    (実走してから気づく類の破綻ではない)。
    """
    if not path.is_file():
        msg = f"[paper02] 封印 manifest が見つからない: {path}"
        raise SystemExit(msg)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    body = {key: value for key, value in manifest.items() if key != "self_sha256"}
    canonical = json.dumps(body, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    computed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    recorded = manifest.get("self_sha256")
    if computed != recorded:
        msg = (
            f"[paper02] 封印 manifest の自己ハッシュが不整合: "
            f"再計算 {computed} != 記録 {recorded!r}"
        )
        raise SystemExit(msg)
    return computed


# --------------------------------------------------------------------------- #
# 観測 — 実走サーバと実ファイルから採る
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class OllamaObservation:
    """実走する Ollama サーバから直接読んだ事実。"""

    version: str
    digests: dict[str, str]
    #: ``/api/ps`` が返した常駐モデル名。封印の照合対象ではない (VRAM 運用の材料)。
    resident: tuple[str, ...] = ()


async def observe_ollama(
    endpoint: str, *, client: httpx.AsyncClient | None = None
) -> OllamaObservation:
    """``/api/version`` / ``/api/tags`` / ``/api/ps`` を読む。

    ``model_digest`` を CLI 引数で受けないのがこの関数の存在理由である。引数は
    著者の申告であり、封印との一致はそのとき「著者が正しく打った」ことしか
    示さない。

    ``/api/ps`` は封印の照合対象ではないが、**常駐しているモデル**を記録する
    (code-reviewer M3/M4)。2 アームを続けて走らせると keep_alive の既定 5 分で
    両モデルが常駐し、16 GB では合計 12 GB 超になる。
    """
    owned = client is None
    http = (
        client
        if client is not None
        else httpx.AsyncClient(base_url=endpoint, timeout=_OBSERVE_TIMEOUT_SECONDS)
    )
    try:
        version_resp = await http.get("/api/version")
        version_resp.raise_for_status()
        version = str(
            _json_object(version_resp, "/api/version").get("version", "unknown")
        )

        tags_resp = await http.get("/api/tags")
        tags_resp.raise_for_status()
        digests: dict[str, str] = {}
        for model in _json_object(tags_resp, "/api/tags").get("models", []):
            if (
                not isinstance(model, dict)
                or "name" not in model
                or "digest" not in model
            ):
                msg = f"[paper02] /api/tags の応答に name/digest が無い: {model!r}"
                raise SystemExit(msg)
            digests[str(model["name"])] = str(model["digest"])

        resident: list[str] = []
        try:
            ps_resp = await http.get("/api/ps")
            ps_resp.raise_for_status()
        except httpx.HTTPError:
            resident = ["unobserved"]
        else:
            resident = [
                str(m.get("name", "?"))
                for m in _json_object(ps_resp, "/api/ps").get("models", [])
                if isinstance(m, dict)
            ]
    finally:
        if owned:
            await http.aclose()
    return OllamaObservation(version=version, digests=digests, resident=tuple(resident))


def _json_object(response: httpx.Response, what: str) -> dict[str, Any]:
    """応答を dict として読む。壊れていたら traceback でなく明示的に停止する。"""
    try:
        payload = response.json()
    except ValueError as exc:
        msg = f"[paper02] {what} の応答が JSON でない: {exc}"
        raise SystemExit(msg) from exc
    if not isinstance(payload, dict):
        msg = f"[paper02] {what} の応答が JSON object でない: {type(payload).__name__}"
        raise SystemExit(msg)
    return payload


def observe_uv_lock_sha256(lock_path: Path) -> str:
    """``uv.lock`` の bytes を hash する (定数を再掲しない)。"""
    if not lock_path.is_file():
        msg = f"[paper02] uv.lock が見つからない: {lock_path}"
        raise SystemExit(msg)
    return hashlib.sha256(lock_path.read_bytes()).hexdigest()


def observe_python() -> str:
    return platform.python_version()


def driver_provenance() -> dict[str, Any]:
    """driver 自身の身元を sidecar に残す (Codex LOW-8)。

    driver は封印の外にあるので、どの版が走ったかはどこにも記録されない。
    実走が一発勝負である以上、「何が書いたか」は後から確かめられる必要がある。
    ``dirty`` が真なら、この sha256 に対応する commit は存在しない。
    """
    source = Path(__file__).resolve()
    provenance: dict[str, Any] = {
        "path": source.name,
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    for key, command in (
        ("git_head", ["git", "rev-parse", "HEAD"]),
        ("git_dirty", ["git", "status", "--porcelain"]),
    ):
        try:
            completed = subprocess.run(  # noqa: S603
                command,
                cwd=_REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):  # pragma: no cover - env
            provenance[key] = "unavailable"
            continue
        if completed.returncode != 0:
            provenance[key] = "unavailable"
        elif key == "git_dirty":
            provenance[key] = bool(completed.stdout.strip())
        else:
            provenance[key] = completed.stdout.strip()
    return provenance


# --------------------------------------------------------------------------- #
# 直列化 (self-contained — ecl_bank_capture / ecl_bank_cproper_capture と同じ規約)
# --------------------------------------------------------------------------- #


def _bank_record_to_dict(record: BankLlmCallRecord) -> dict[str, Any]:
    return {
        "frozen_ctx_id": record.frozen_ctx_id,
        "condition": record.condition,
        "mc_index": record.mc_index,
        "system_prompt": record.system_prompt,
        "user_prompt": record.user_prompt,
        "sampling": record.sampling.model_dump(),
        "raw_response": record.raw_response,
        "pre_bias_destination_zone": (
            record.pre_bias_destination_zone.value
            if record.pre_bias_destination_zone is not None
            else None
        ),
    }


def _bank_record_from_dict(data: dict[str, Any]) -> BankLlmCallRecord:
    condition = data["condition"]
    if condition not in ("on", "off"):
        msg = f"invalid bank condition: {condition!r}"
        raise ValueError(msg)
    zone_value = data["pre_bias_destination_zone"]
    return BankLlmCallRecord(
        frozen_ctx_id=data["frozen_ctx_id"],
        condition=cast("BankCondition", condition),
        mc_index=data["mc_index"],
        system_prompt=data["system_prompt"],
        user_prompt=data["user_prompt"],
        sampling=ResolvedSampling.model_validate(data["sampling"]),
        raw_response=data["raw_response"],
        pre_bias_destination_zone=(
            Zone(zone_value) if zone_value is not None else None
        ),
    )


def _annotation_row_to_dict(row: BankAnnotationRow) -> dict[str, Any]:
    return {
        "frozen_ctx_id": row.frozen_ctx_id,
        "condition": row.condition,
        "mc_index": row.mc_index,
        "pre_bias_destination_zone": (
            row.pre_bias_destination_zone.value
            if row.pre_bias_destination_zone is not None
            else None
        ),
        "resolved_from": row.resolved_from,
    }


def _records_to_jsonl(records: Sequence[BankLlmCallRecord]) -> str:
    return "".join(
        f"{handoff.canonical_dumps(_bank_record_to_dict(r))}\n" for r in records
    )


def _records_from_jsonl(text: str) -> tuple[BankLlmCallRecord, ...]:
    return tuple(
        _bank_record_from_dict(json.loads(line))
        for line in text.splitlines()
        if line.strip()
    )


def _annotation_to_jsonl(rows: Sequence[BankAnnotationRow]) -> str:
    return "".join(
        f"{handoff.canonical_dumps(_annotation_row_to_dict(r))}\n" for r in rows
    )


def _annotation_dicts_from_jsonl(text: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def bank_checksum(records: Sequence[BankLlmCallRecord]) -> str:
    """``bank_records.jsonl`` 相当の正規形に対する SHA-256。

    完了済 run の manifest が ``bank_checksum`` として記録し、封印が
    ``context_bank.bank_checksum`` として固定した値と同じ計算である。
    """
    canonical = "\n".join(
        handoff.canonical_dumps(_bank_record_to_dict(r)) for r in records
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _row_keys(
    items: Sequence[BankLlmCallRecord] | Sequence[BankAnnotationRow],
) -> list[tuple[str, str, int]]:
    return [(i.frozen_ctx_id, i.condition, i.mc_index) for i in items]


def _annotation_rows_from_records(
    records: Sequence[BankLlmCallRecord],
) -> tuple[BankAnnotationRow, ...]:
    """annotation は records の関数である — capture と verify の両方がこれを使う。

    2 箇所で別々に組むと、``--verify`` の再導出が「同じ関数を 2 回書いた」ことの
    確認に落ちる。1 つにして、採点対象が生データから決まることを構造で保つ。
    """
    return tuple(
        BankAnnotationRow(
            frozen_ctx_id=record.frozen_ctx_id,
            condition=record.condition,
            mc_index=record.mc_index,
            pre_bias_destination_zone=record.pre_bias_destination_zone,
            resolved_from=_RESOLVED_FROM_TAG,
        )
        for record in records
    )


# --------------------------------------------------------------------------- #
# 凍結 context bank の消費 (再生成ではない)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class FrozenBank:
    """実走が **消費** する凍結 context bank。

    ``run_provenance_pass`` による再生成を採らないのは、再生成が封印と比較できる
    checksum を一切生まないからである (加えて実測で ``sampling_on.top_p`` が
    ``0.94`` / ``0.9400000000000001`` と byte 相違する — 6 桁量子化の非対称)。
    """

    checksum: str
    contexts: tuple[FrozenContext, ...]

    @property
    def context_ids(self) -> list[str]:
        return [ctx.frozen_ctx_id for ctx in self.contexts]


def load_frozen_bank(path: Path, *, k_contexts: int | None = None) -> FrozenBank:
    """凍結 bank ファイルを読み、checksum を再計算して context を復元する。

    ``k_contexts`` を与えると先頭 K 個に絞る (smoke 用)。**絞った時点で checksum は
    封印値と一致しなくなる** — それは正しい挙動であり、封印未満の run が
    pre-registered を名乗れないことを意味する。
    """
    if not path.is_file():
        msg = f"[paper02] 凍結 bank が見つからない: {path}"
        raise SystemExit(msg)
    records = _records_from_jsonl(path.read_text(encoding="utf-8"))
    if not records:
        msg = f"[paper02] 凍結 bank が空: {path}"
        raise SystemExit(msg)

    contexts = _frozen_contexts_from_records(records)
    if k_contexts is not None:
        if k_contexts > len(contexts):
            msg = (
                f"[paper02] 凍結 bank は context を {len(contexts)} 個しか持たない "
                f"(--k-contexts {k_contexts})"
            )
            raise SystemExit(msg)
        if k_contexts < len(contexts):
            contexts = contexts[:k_contexts]
            kept = {ctx.frozen_ctx_id for ctx in contexts}
            records = tuple(r for r in records if r.frozen_ctx_id in kept)
    return FrozenBank(checksum=bank_checksum(records), contexts=contexts)


def _frozen_contexts_from_records(
    records: Sequence[BankLlmCallRecord],
) -> tuple[FrozenContext, ...]:
    by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        entry = by_id.setdefault(record.frozen_ctx_id, {})
        entry.setdefault("system_prompt", record.system_prompt)
        entry.setdefault("user_prompt", record.user_prompt)
        if record.condition == "on":
            entry["sampling_on"] = record.sampling
        else:
            entry["sampling_off"] = record.sampling
    missing = [
        ctx_id
        for ctx_id, entry in by_id.items()
        if "sampling_on" not in entry or "sampling_off" not in entry
    ]
    if missing:
        msg = f"[paper02] 凍結 bank に on/off 双方を持たない context がある: {missing}"
        raise SystemExit(msg)
    contexts = [
        FrozenContext(
            frozen_ctx_id=ctx_id,
            system_prompt=entry["system_prompt"],
            user_prompt=entry["user_prompt"],
            sampling_on=entry["sampling_on"],
            sampling_off=entry["sampling_off"],
        )
        for ctx_id, entry in by_id.items()
    ]
    return tuple(sorted(contexts, key=lambda c: c.frozen_ctx_id))


# --------------------------------------------------------------------------- #
# 事前ゲート — 1 draw 目の前に封印と突き合わせる
# --------------------------------------------------------------------------- #


def preflight_problems(
    *,
    spec: dict[str, Any],
    arm: str,
    observed: OllamaObservation,
    uv_lock: str,
    python_version: str,
    bank: FrozenBank,
    seed: int | None = None,
    m_draws: int | None = None,
) -> list[str]:
    """封印と観測の差分を列挙する。空なら実走してよい。

    契約の検査 (``verify_seal.py``) は **run の後** に走る。それでは 2.5 時間と
    封印を失うので、同じ比較を先に行う。これは契約が含意しているが明文化して
    いない検査であり、本 driver の存在理由そのものである。
    """
    problems: list[str] = []
    if arm not in spec.get("arms", {}):
        return [f"未知のアーム {arm!r}; 封印は {sorted(spec.get('arms', {}))} を宣言"]
    arm_spec = spec["arms"][arm]
    environment = spec["environment"]

    def compare(label: str, got: Any, want: Any) -> None:
        if got != want:
            problems.append(f"{label}: 観測 {got!r} != 封印 {want!r}")

    compare("ollama_version", observed.version, environment["ollama_version"])
    compare("python", python_version, environment["python"])
    compare("uv_lock_sha256", uv_lock, environment["uv_lock_sha256"])

    model = str(arm_spec["model"])
    digest = observed.digests.get(model)
    if digest is None:
        problems.append(
            f"{arm}.model_digest: Ollama が {model!r} を持っていない "
            f"(利用可能: {sorted(observed.digests)})"
        )
    else:
        compare(f"{arm}.model_digest", digest, arm_spec["model_digest"])

    context_bank = spec["context_bank"]
    sealed_ids = list(context_bank["context_ids"])
    if bank.checksum != context_bank["bank_checksum"]:
        detail = ""
        if len(bank.context_ids) != len(sealed_ids):
            # K を削ると bank そのものが別物になる。封印は K を context bank の
            # 身元の一部として固定しているので、これは「規模が小さい」ではなく
            # 「別の bank を使った」である。
            detail = (
                f" — context を {len(bank.context_ids)} 個に絞っている "
                f"(封印は {len(sealed_ids)} 個)。K を削ると bank は別物になる"
            )
        problems.append(
            f"bank_checksum: 観測 {bank.checksum!r} != "
            f"封印 {context_bank['bank_checksum']!r}{detail}"
        )
    compare("context_ids", bank.context_ids, sealed_ids)

    # VRAM: 2 アームを続けて走らせると keep_alive の既定 5 分で両モデルが常駐し、
    # 16 GB では合計 12 GB 超になる (pilot 実測 6.0 + 6.4 GB)。CPU offload へ劣化
    # すると所要時間が倍増しうる (code-reviewer M4)。封印の照合対象ではないので
    # **停止させず警告に留める** — 判断は運用側にある。
    other_resident = [name for name in observed.resident if name != model]
    if other_resident:
        print(
            f"[preflight] ⚠ 別のモデルが常駐している: {other_resident}。"
            "16 GB では 2 モデル同時常駐で CPU offload へ劣化しうる "
            "(封印の照合対象ではない)",
            file=sys.stderr,
        )

    # 標本計画も draw 0 の時点で突き合わせる (Codex MEDIUM-6)。seed / M は
    # manifest に現れてから ``verify_seal`` が落とすが、それは実走の後である。
    sampling = spec.get("sampling", {})
    if seed is not None and "seed" in sampling:
        compare("seed", seed, sampling["seed"])
    if m_draws is not None and "m_draws" in sampling:
        compare("m_draws", m_draws, sampling["m_draws"])
    return problems


# --------------------------------------------------------------------------- #
# think / model の観測 spy
# --------------------------------------------------------------------------- #


@dataclass
class ThinkAndModelSpy:
    """M-loop が実際に渡した ``think`` と、応答が名乗った ``model`` を観測する。

    ``env_pins.think`` に定数 ``False`` を書けば封印と一致するが、それは
    「apparatus が think を切った」ことの証拠にならない。``run_bank_mloop`` が
    渡した値をそのまま拾うことで、manifest の ``think`` は観測になる
    (ECL v1 の sampling-spy と同型)。

    加えて実走を **5 時間生き延びさせる** 役目を負う (code-reviewer H1):

    * ``transport`` 失敗だけを有界 retry する。内容の失敗は retry しない
      (見た応答を捨てて引き直すのは応答の選択であり estimand が汚れる)
    * 応答を受け取るたび ``partial_path`` へ追記 flush する。途中で落ちても
      raw が 1 バイトも残らない事態を避ける。**部分データは採点できない**
      (``_observed_m_draws`` が完全なセルを要求する) のでチェリーピックには
      使えない
    * 呼び出し上限を **live に** 強制する (事後集計では発火しえない — L2)
    """

    inner: Any
    call_cap: int | None = None
    partial_path: Path | None = None
    think_values: set[Any] = field(default_factory=set)
    models: set[str] = field(default_factory=set)
    calls: int = 0
    retries: int = 0
    retry_reasons: list[str] = field(default_factory=list)

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        sampling: ResolvedSampling,
        model: str | None = None,
        options: dict[str, Any] | None = None,
        think: bool | None = None,
    ) -> ChatResponse:
        if self.call_cap is not None and self.calls >= self.call_cap:
            msg = (
                f"[paper02] M-loop の呼び出し上限に達した: "
                f"{self.calls} >= {self.call_cap} (cost ceiling)"
            )
            raise RuntimeError(msg)
        self.calls += 1
        self.think_values.add(think)
        response = await self._chat_with_bounded_retry(
            messages, sampling=sampling, model=model, options=options, think=think
        )
        self.models.add(response.model)
        self._flush_partial(response)
        return response

    async def _chat_with_bounded_retry(
        self,
        messages: Sequence[ChatMessage],
        **kwargs: Any,
    ) -> ChatResponse:
        last: Exception | None = None
        for attempt in range(_TRANSPORT_RETRIES + 1):
            try:
                return cast("ChatResponse", await self.inner.chat(messages, **kwargs))
            except Exception as exc:  # 分類してから再送出する
                if not _is_retriable(exc):
                    raise
                last = exc
                self.retries += 1
                self.retry_reasons.append(f"call {self.calls}: {exc}")
                print(
                    f"[capture] transport 失敗を retry する "
                    f"({attempt + 1}/{_TRANSPORT_RETRIES}): {exc}",
                    file=sys.stderr,
                )
                if attempt < _TRANSPORT_RETRIES:
                    await asyncio.sleep(_TRANSPORT_RETRY_BACKOFF_S)
        assert last is not None
        raise last

    def _flush_partial(self, response: ChatResponse) -> None:
        if self.partial_path is None:
            return
        row = {
            "call_index": self.calls,
            "model": response.model,
            "content": response.content,
            "observed_at": datetime.now(UTC).isoformat(),
        }
        self.partial_path.parent.mkdir(parents=True, exist_ok=True)
        with self.partial_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    async def close(self) -> None:
        close = getattr(self.inner, "close", None)
        if callable(close):
            await close()

    def observed_think(self) -> Any:
        if len(self.think_values) != 1:
            msg = (
                "[paper02] M-loop が単一の think 相で走っていない: "
                f"{sorted(map(repr, self.think_values))}"
            )
            raise SystemExit(msg)
        return next(iter(self.think_values))

    def observed_model(self) -> str:
        if len(self.models) != 1:
            msg = f"[paper02] 応答が単一のモデルを名乗っていない: {sorted(self.models)}"
            raise SystemExit(msg)
        return next(iter(self.models))


# --------------------------------------------------------------------------- #
# manifest / 描画
# --------------------------------------------------------------------------- #


def build_run_manifest(
    *,
    arm: str,
    seal_hash: str,
    bank: FrozenBank,
    records: Sequence[BankLlmCallRecord],
    records_jsonl: str,
    annotation_jsonl: str,
    m_draws: int,
    k_contexts: int,
    seed: int,
    env_pins: dict[str, Any],
    sub_sealed_scale: bool,
) -> dict[str, Any]:
    """封印 ``manifest_field_map`` が指す形の run manifest。

    ``run.m_draws`` / ``run.k_contexts`` は引数を書き写すのではなく **産出物から
    数える**。引数と実際の産出が食い違えば、封印比較はそこで落ちるべきである。
    """
    manifest: dict[str, Any] = {
        "run_manifest_version": RUN_MANIFEST_VERSION,
        "annotation_schema_version": BANK_ANNOTATION_SCHEMA_VERSION,
        "sealed_manifest_sha256": seal_hash,
        "arm": arm,
        "run": {
            "run_id": f"paper02-{arm}",
            "m_draws": m_draws,
            "k_contexts": k_contexts,
            "seed": seed,
            "base_ts": _FIXED_CLOCK.isoformat(),
            "retrieval_now": _FIXED_CLOCK.isoformat(),
            "context_ids": bank.context_ids,
        },
        "env_pins": env_pins,
        # 消費した凍結 bank の身元 — 封印 ``context_bank.bank_checksum`` の比較対象。
        "bank_checksum": bank.checksum,
        "artifacts": {
            # この run が産出した records。**bank_checksum とは別の量**である。
            "run_records.jsonl": {"sha256": _sha256(records_jsonl)},
            "run_annotation.jsonl": {"sha256": _sha256(annotation_jsonl)},
        },
        "call_cap": {"actual": len(records), "cap": 2 * m_draws * k_contexts},
        "cost_ceiling": {
            "max_llm_calls": 2 * m_draws * k_contexts,
            "model": env_pins.get("model"),
        },
        # 封印未満で走らせたことの自己申告。**保証ではない** — 封印値との一致は
        # 契約側の ``verify_seal.py`` が run.m_draws / thresholds.m_draws の二重で
        # 判定する。このフラグはそれを代替しない。
        "sub_sealed_scale": sub_sealed_scale,
    }
    return attach_bank_observables(manifest)


def render(
    *,
    arm: str,
    seal_hash: str,
    bank: FrozenBank,
    records: Sequence[BankLlmCallRecord],
    annotation_rows: Sequence[BankAnnotationRow],
    m_draws: int,
    k_contexts: int,
    seed: int,
    env_pins: dict[str, Any],
    sub_sealed_scale: bool,
) -> dict[str, str]:
    records_jsonl = _records_to_jsonl(records)
    annotation_jsonl = _annotation_to_jsonl(annotation_rows)
    manifest = build_run_manifest(
        arm=arm,
        seal_hash=seal_hash,
        bank=bank,
        records=records,
        records_jsonl=records_jsonl,
        annotation_jsonl=annotation_jsonl,
        m_draws=m_draws,
        k_contexts=k_contexts,
        seed=seed,
        env_pins=env_pins,
        sub_sealed_scale=sub_sealed_scale,
    )
    return {
        "run_records.jsonl": records_jsonl,
        "run_annotation.jsonl": annotation_jsonl,
        "run-manifest.json": handoff.canonical_dumps(manifest) + "\n",
    }


def _write(out_dir: Path, rendered: dict[str, str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, text in rendered.items():
        (out_dir / filename).write_text(text, encoding="utf-8", newline="\n")


def build_env_pins(
    *,
    model: str,
    model_digest: str,
    think: Any,
    ollama_version: str,
    uv_lock_sha256: str,
    python_version: str,
) -> dict[str, Any]:
    """封印 ``manifest_field_map.per_arm`` / ``shared`` が指す env pins。

    キーは ``model_digest`` であって ``qwen3_model_digest`` ではない。封印の
    ``legacy_note`` が「モデル固有キーは 2 つのモデル族に仕えられないので、前向き
    driver は ``env_pins.model_digest`` を出すことを要求する。driver が存在する
    前にフィールド名を宣言しておくことが pre-registration の一部である」と明文で
    定めている。
    """
    pins = handoff.capture_env_pins()
    pins.update(
        {
            "model": model,
            "model_digest": model_digest,
            "think": think,
            "ollama_version": ollama_version,
            "uv_lock_sha256": uv_lock_sha256,
            "python": python_version,
        }
    )
    return pins


# --------------------------------------------------------------------------- #
# capture
# --------------------------------------------------------------------------- #


async def capture(
    *,
    arm: str,
    spec: dict[str, Any],
    seal_hash: str,
    bank: FrozenBank,
    m_draws: int,
    seed: int,
    uv_lock: str,
    python_version: str,
    observed: OllamaObservation,
    endpoint: str = OllamaChatClient.DEFAULT_ENDPOINT,
    inner_chat: Any | None = None,
    reobserve: Any | None = None,
    partial_path: Path | None = None,
) -> tuple[dict[str, str], dict[str, Any]]:
    """1 アームを実走し、成果物と sidecar メトリクスを返す。

    ``inner_chat`` は M-loop の chat client。default は実 :class:`OllamaChatClient`
    であり、テストと Ollama-free の dry-run だけが mock を注入する。この seam が
    live 経路を変えることはない。

    ``endpoint`` は **観測と draw の両方**に使う (Codex HIGH-3)。観測だけを
    ``--endpoint`` に向け、draw を default に投げると、preflight した Ollama と
    実際に答えた Ollama が別物でも manifest は preflight 側の digest を名乗れてしまう。

    ``reobserve`` は実走**後**に同じ endpoint を読み直す関数。版や digest が走行中に
    動いていないことを確かめる (実走は 2.5 時間あり、その間に更新されうる)。
    """
    model = str(spec["arms"][arm]["model"])
    k_contexts = len(bank.contexts)

    inner = (
        inner_chat
        if inner_chat is not None
        else OllamaChatClient(
            model=model, endpoint=endpoint, timeout=_CHAT_TIMEOUT_SECONDS
        )
    )
    cap = 2 * m_draws * k_contexts
    spy = ThinkAndModelSpy(inner=inner, call_cap=cap, partial_path=partial_path)
    llm_client = BankRecordReplayClient.for_record(spy)

    started = time.monotonic()
    try:
        records = await run_bank_mloop(
            llm=llm_client, frozen_contexts=bank.contexts, m_draws=m_draws
        )
    finally:
        await spy.close()
    elapsed_s = time.monotonic() - started

    # 走行中に backend が動いていないか (自動更新は封印を破る — DA-P3B-36)。
    if reobserve is not None:
        after = await reobserve(endpoint)
        if after.version != observed.version:
            msg = (
                "[paper02] 実走中に ollama の版が変わった: "
                f"{observed.version} -> {after.version}。この run は封印を名乗れない。"
            )
            raise CaptureAbortedError(msg, records)
        before_digest = observed.digests.get(model)
        after_digest = after.digests.get(model)
        if before_digest != after_digest:
            msg = (
                f"[paper02] 実走中に {model} の digest が変わった: "
                f"{before_digest} -> {after_digest}。この run は封印を名乗れない。"
            )
            raise CaptureAbortedError(msg, records)

    actual = llm_client.inner_invocations
    if actual > cap:
        msg = (
            f"[paper02] M-loop の呼び出し上限を超えた: {actual} > {cap} (cost ceiling)"
        )
        raise CaptureAbortedError(msg, records)

    annotation_rows = _annotation_rows_from_records(records)

    observed_model = spy.observed_model()
    digest = observed.digests.get(observed_model, "unobserved")
    env_pins = build_env_pins(
        model=observed_model,
        model_digest=digest,
        think=spy.observed_think(),
        ollama_version=observed.version,
        uv_lock_sha256=uv_lock,
        python_version=python_version,
    )

    # run.m_draws / run.k_contexts は産出物から数える (引数を書き写さない)。
    try:
        observed_m = _observed_m_draws(records)
    except SystemExit as exc:  # 生データを道連れにしない (H2)
        raise CaptureAbortedError(str(exc), records) from exc
    produced_ids = sorted({r.frozen_ctx_id for r in records})
    observed_k = len(produced_ids)

    # 産出した context と消費した bank が食い違う manifest を出してはならない。
    # ``run.context_ids`` は消費した bank から、``run.k_contexts`` は産出物から
    # 来るので、黙って通すと内部矛盾した manifest が出る。
    if produced_ids != sorted(bank.context_ids):
        msg = (
            "[paper02] 産出 records の context が消費した bank と食い違う: "
            f"産出 {produced_ids} != bank {sorted(bank.context_ids)}"
        )
        raise CaptureAbortedError(msg, records)

    sub_sealed = observed_m < M_MIN or observed_k < K_MIN

    rendered = render(
        arm=arm,
        seal_hash=seal_hash,
        bank=bank,
        records=records,
        annotation_rows=annotation_rows,
        m_draws=observed_m,
        k_contexts=observed_k,
        seed=seed,
        env_pins=env_pins,
        sub_sealed_scale=sub_sealed,
    )
    metrics: dict[str, Any] = {
        "note": (
            "壁時計は自己申告である。ここに書かれた時刻は run manifest の外にあり、"
            "何かが何かより前に起きたことを証明しない (manifest は決定性のため "
            "固定時計を持つ)。"
        ),
        "arm": arm,
        "wall_clock_seconds": round(elapsed_s, 3),
        "llm_calls": actual,
        "recorded_at": datetime.now(UTC).isoformat(),
        "sub_sealed_scale": sub_sealed,
        # transport 失敗の retry 回数。0 でない run は「何事もなく通った」run では
        # ない。理由も残す (H1)。
        "transport_retries": spy.retries,
        "transport_retry_reasons": list(spy.retry_reasons),
        # ``/api/ps`` が返した常駐モデル。封印の照合対象ではない (M3/M4)。
        "resident_models_before": list(observed.resident),
    }
    return rendered, metrics


def _observed_m_draws(records: Sequence[BankLlmCallRecord]) -> int:
    """各 (context, condition) セルの draw 数。セル間で不揃いなら停止する。"""
    counts: dict[tuple[str, str], int] = {}
    for record in records:
        key = (record.frozen_ctx_id, record.condition)
        counts[key] = counts.get(key, 0) + 1
    distinct = set(counts.values())
    if len(distinct) != 1:
        msg = f"[paper02] セルごとの draw 数が不揃い: {sorted(distinct)}"
        raise SystemExit(msg)
    return next(iter(distinct))


# --------------------------------------------------------------------------- #
# verify — 整合ゲート → replay → 行整合 → **raw から再計算** → verdict
# --------------------------------------------------------------------------- #


async def verify(
    artifact_dir: Path,
    *,
    arm: str,
    paper_repo: Path | None = None,
    bank_path: Path | None = None,
) -> int:
    """committed bundle を Ollama-free で replay し、scorer を当てる。

    順序が A.6 M-4 そのものである: **shipped verdict を読まない**。raw annotation
    から ``score_bank_annotation`` で再計算したものだけが ``verdict.json`` になり、
    決定規則 (``apply_decision_rules.py``) はそれを読む。driver 内に
    「shipped verdict を決定規則へ渡す」経路を作らないので、順序が運用に依存しない。

    ``arm`` は必須である (Codex MEDIUM-7)。manifest の ``arm`` と突き合わせないと、
    control の bundle を primary として検証しても通ってしまう — 封印検査器が
    ``--arm`` を必須にしているのと同じ理由。

    ``paper_repo`` があれば、最後に**封印検査器そのもの**を走らせる
    (Codex HIGH-2)。driver 自身の整合検査は封印検査ではない: ``model_digest`` や
    ``bank_checksum`` を改竄した manifest でも driver は verdict を出せてしまう。
    正典は ``verify_seal.py`` なので、それを通るまで OK と言わない。
    **検査器に届かなかったことを「通った」に数えない** (code-reviewer H3)。

    返り値は終了コードである (``bool`` ではない — code-reviewer H4):

    * :data:`VERIFY_OK` — 整合が取れ、封印検査も通った
    * :data:`VERIFY_FAIL` — どこかが落ちた
    * :data:`VERIFY_SUB_SEALED` — 整合は取れたが封印規模でない bundle。
      **exit 0 にしない**。緑が「前向き結果である」と読まれないようにする

    ``replay が byte 一致`` が示すのは**決定性**であって改竄検知ではない
    (replay client は prompt を照合せず順に再生する)。records / annotation /
    manifest を整合的に書き換えた bundle は driver の検査を通る。外部性は
    リポジトリ内の検査では原理的に届かない
    (``feedback_offline_check_cannot_witness_outside``)。
    """
    manifest_path = artifact_dir / "run-manifest.json"
    if not manifest_path.is_file():
        print(f"[verify] FAIL manifest が無い: {manifest_path}")
        return VERIFY_FAIL
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        records_text = (artifact_dir / "run_records.jsonl").read_text(encoding="utf-8")
        annotation_text = (artifact_dir / "run_annotation.jsonl").read_text(
            encoding="utf-8"
        )
    except (OSError, ValueError) as exc:  # L1: traceback でなく明示的な FAIL
        print(f"[verify] FAIL bundle を読めない: {exc}")
        return VERIFY_FAIL

    recorded_arm = manifest.get("arm")
    if recorded_arm != arm:
        print(f"[verify] FAIL この bundle のアームは {recorded_arm!r}、指定は {arm!r}")
        return VERIFY_FAIL

    # ``sub_sealed_scale`` は自己申告なので、**記録から再計算して突き合わせる**
    # (code-reviewer H4)。突き合わせないと、封印対象フィールドを改竄した manifest に
    # このフラグを 1 行足すだけで封印検査の失敗を握り潰せる。
    run_config = manifest.get("run", {})
    try:
        recomputed_sub_sealed = (
            int(run_config["m_draws"]) < M_MIN or int(run_config["k_contexts"]) < K_MIN
        )
    except (KeyError, TypeError, ValueError) as exc:
        print(f"[verify] FAIL manifest.run から M/K を読めない: {exc}")
        return VERIFY_FAIL
    declared_sub_sealed = bool(manifest.get("sub_sealed_scale"))
    if declared_sub_sealed != recomputed_sub_sealed:
        print(
            f"[verify] FAIL sub_sealed_scale の自己申告 {declared_sub_sealed} が "
            f"記録された M/K から再計算した {recomputed_sub_sealed} と食い違う"
        )
        return VERIFY_FAIL

    committed_records = _records_from_jsonl(records_text)
    frozen_contexts = _frozen_contexts_from_records(committed_records)
    m_draws = int(manifest["run"]["m_draws"])
    annotation_dicts = _annotation_dicts_from_jsonl(annotation_text)

    ok = True

    # 整合ゲート: manifest の bytes と一致しない bundle は **決して採点しない**
    # (行キーを保ったまま zone だけ書き換える改竄は replay も行整合も通るため)。
    for name, text in (
        ("run_records.jsonl", records_text),
        ("run_annotation.jsonl", annotation_text),
    ):
        expected = manifest["artifacts"][name]["sha256"]
        actual = _sha256(text)
        if actual != expected:
            ok = False
            print(f"[verify] FAIL {name} sha256 {actual} != manifest {expected}")
        else:
            print(f"[verify] OK {name} sha256 が manifest と一致")

    # replay 決定性 (Ollama-free、byte 一致の再描画)
    replay_client = BankRecordReplayClient.for_replay(committed_records)
    replayed = await run_bank_mloop(
        llm=replay_client, frozen_contexts=frozen_contexts, m_draws=m_draws
    )
    if replay_client.inner_invocations != 0:
        ok = False
        touched = replay_client.inner_invocations
        print(f"[verify] FAIL replay が live LLM に触れた ({touched})")
    if _records_to_jsonl(replayed) != records_text:
        ok = False
        print("[verify] FAIL run_records.jsonl が replay で byte 不一致")
    else:
        print("[verify] OK replay が byte 一致")

    # records ↔ annotation の行単位キー整合 (集計値では見えない)
    committed_annotation_keys = [
        (str(d["frozen_ctx_id"]), str(d["condition"]), int(d["mc_index"]))
        for d in annotation_dicts
    ]
    if _row_keys(committed_records) != committed_annotation_keys:
        ok = False
        print("[verify] FAIL records / annotation の行単位キーがずれている")
    else:
        print("[verify] OK records / annotation の行単位キーが一致")

    # annotation を **replay した records から再導出** して byte 一致を要求する
    # (Codex HIGH-1)。manifest の sha256 照合だけでは、zone を書き換えたうえで
    # manifest の sha256 も揃えた改竄が通ってしまう — 行キーは保たれるので
    # 上の整合も抜ける。採点対象が生データの関数であることを、ここで閉じる。
    rederived = _annotation_to_jsonl(_annotation_rows_from_records(replayed))
    if rederived != annotation_text:
        ok = False
        print("[verify] FAIL annotation が records から再導出したものと byte 不一致")
    else:
        print("[verify] OK annotation は records から再導出できる")

    # 消費した凍結 bank を bundle 側から再導出できるようにする (code-reviewer M2)。
    # ここまでの検査は committed records しか見ておらず、``bank_checksum`` は
    # capture 時のコードだけが担保していた。bank を渡されたら独立に突き合わせる。
    if bank_path is not None:
        try:
            bank = load_frozen_bank(bank_path)
        except SystemExit as exc:
            ok = False
            print(f"[verify] FAIL 凍結 bank を読めない: {exc}")
        else:
            if bank.checksum != manifest.get("bank_checksum"):
                ok = False
                print(
                    f"[verify] FAIL bank_checksum {bank.checksum} != "
                    f"manifest {manifest.get('bank_checksum')}"
                )
            elif sorted(bank.context_ids) != sorted(
                {r.frozen_ctx_id for r in committed_records}
            ):
                ok = False
                print("[verify] FAIL 凍結 bank の context が records と食い違う")
            else:
                print("[verify] OK bank_checksum を凍結 bank から再導出して一致")

    if not ok:
        # 改竄された bundle の古い verdict を残さない。残すと「検査に落ちたのに
        # 判定だけ手元にある」状態になる。
        _drop_stale_verdict(artifact_dir)
        print("[verify] MISMATCH — 整合が取れないので scorer を走らせない")
        return VERIFY_FAIL

    # 記録された seed を **load-bearing にする** (code-reviewer M1)。manifest が
    # 名乗る seed と解析が使う seed が独立だと、封印の seed 照合は記録の一致しか
    # 示さない。
    try:
        recorded_seed = int(run_config["seed"])
    except (KeyError, TypeError, ValueError) as exc:
        print(f"[verify] FAIL manifest.run.seed を読めない: {exc}")
        return VERIFY_FAIL

    verdict = score_bank_annotation(
        annotation_rows=annotation_dicts,
        manifest=manifest,
        n_replicates=N_REPLICATES_DEFAULT,
        seed=recorded_seed,
        require_powered_scale=True,
    )
    verdict_dict = verdict_to_dict(verdict)
    verdict_text = handoff.canonical_dumps(verdict_dict) + "\n"
    verdict_path = artifact_dir / "run-verdict.json"
    verdict_path.write_text(verdict_text, encoding="utf-8", newline="\n")
    print(f"[verify] VERDICT {verdict.verdict}")
    print(f"[verify] reason: {'; '.join(verdict.reason)}")

    seal_outcome = (
        run_sealed_seal_check(
            paper_repo=paper_repo,
            manifest_path=manifest_path,
            verdict_path=verdict_path,
            arm=arm,
        )
        if paper_repo is not None
        else _SEAL_NOT_RUN
    )
    if paper_repo is None:
        print(
            "[verify] NOTE 論文 repo が指定されていない (または存在しない) ため "
            "封印検査を実行していない"
        )

    if recomputed_sub_sealed:
        # 封印未満の bundle は封印検査に落ちるのが正しい。harness 検証としては
        # 成功だが **前向き結果ではない** ので exit 0 にしない (code-reviewer H4)。
        print(
            f"[verify] SUB-SEALED 封印規模でない bundle (封印検査 = {seal_outcome})。"
            "harness の検証としては整合が取れているが、前向き結果ではない"
        )
        return VERIFY_SUB_SEALED

    # ここから先は「これは前向き結果だ」と名乗っている bundle である。
    # **検査器に届かなかったことを「通った」に数えない** (code-reviewer H3)。
    if seal_outcome != _SEAL_OK:
        reason = (
            "封印検査を実行できなかった"
            if seal_outcome == _SEAL_NOT_RUN
            else "封印検査に落ちた"
        )
        print(
            f"[verify] FAIL {reason}。封印規模を名乗る bundle が "
            "verify_seal を通るまで OK と言わない"
        )
        _quarantine_verdict(artifact_dir)
        return VERIFY_FAIL

    print("[verify] OK")
    return VERIFY_OK


def _drop_stale_verdict(artifact_dir: Path) -> None:
    stale = artifact_dir / "run-verdict.json"
    if stale.exists():
        stale.unlink()
        print("[verify] 古い run-verdict.json を削除した")


def _quarantine_verdict(artifact_dir: Path) -> None:
    """封印検査に落ちた verdict を **緑の名前で残さない** (code-reviewer M8)。"""
    verdict = artifact_dir / "run-verdict.json"
    if verdict.exists():
        deviation = artifact_dir / "run-verdict.DEVIATION.json"
        if deviation.exists():
            deviation.unlink()
        verdict.rename(deviation)
        print(f"[verify] verdict を {deviation.name} へ改名した (前向き結果ではない)")


def run_sealed_seal_check(
    *, paper_repo: Path, manifest_path: Path, verdict_path: Path, arm: str
) -> str:
    """封印検査器 ``verify_seal.py`` を **そのまま** 走らせる (Codex HIGH-2).

    driver の整合検査は封印検査ではない。``model_digest`` や ``bank_checksum`` を
    改竄した manifest でも driver は verdict を出せる。正典を複製せず呼ぶ。

    返すのは 3 値である (code-reviewer H3): :data:`_SEAL_OK` / :data:`_SEAL_FAILED` /
    :data:`_SEAL_NOT_RUN`。**「実行できなかった」を「通った」に畳まない** —
    畳むと `--paper-repo` の打ち間違いや WSL からの実行で、検査が無言で消える。
    """
    script = paper_repo / "analysis" / "scripts" / "verify_seal.py"
    if not script.is_file():
        print(f"[verify] NOTE 封印検査器が見つからない: {script}")
        return _SEAL_NOT_RUN
    command = [
        sys.executable,
        str(script),
        "--run-manifest",
        str(manifest_path),
        "--arm",
        arm,
        "--run-verdict",
        str(verdict_path),
    ]
    try:
        completed = subprocess.run(  # noqa: S603
            command, cwd=paper_repo, capture_output=True, text=True, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"[verify] NOTE 封印検査器を起動できなかった: {exc}")
        return _SEAL_NOT_RUN
    for line in (completed.stdout + completed.stderr).splitlines():
        if line.strip():
            print(f"[verify][seal] {line}")
    return _SEAL_OK if completed.returncode == 0 else _SEAL_FAILED


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _resolve_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    paper_repo: Path = args.paper_repo
    return (
        paper_repo / "seal" / "arm-spec.json",
        paper_repo / "seal" / "SEAL-MANIFEST.json",
    )


def _print_preflight(problems: list[str], *, arm: str) -> None:
    if problems:
        print(
            f"[preflight] {arm}: 封印と食い違う ({len(problems)} 件)", file=sys.stderr
        )
        for problem in problems:
            print(f"[preflight]   - {problem}", file=sys.stderr)
    else:
        print(f"[preflight] OK {arm}: 観測は封印と一致する")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="論文 02 前向き 2 アーム実走 driver (封印契約の実装)"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--preflight", action="store_true", help="環境を封印と突き合わせるだけ"
    )
    mode.add_argument("--capture", action="store_true", help="1 アームを実走する")
    mode.add_argument(
        "--verify", action="store_true", help="Ollama-free replay + scorer"
    )

    # ``--arm`` は必須で、manifest から推論しない。封印検査器が同じ理由で
    # ``--arm`` を必須にしている (誤ラベルの run がどちらかのアームに一致してしまう)。
    parser.add_argument("--arm", choices=_ARMS, help="control / primary")
    parser.add_argument("--paper-repo", type=Path, default=_DEFAULT_PAPER_REPO)
    parser.add_argument("--bank", type=Path, default=_DEFAULT_BANK)
    parser.add_argument("--out-root", type=Path, default=_DEFAULT_OUT_ROOT)
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--endpoint", default=OllamaChatClient.DEFAULT_ENDPOINT)
    # default は封印値。小さくできないと spend の前に検証できないが、
    # **default を小さくしてはならない**。
    parser.add_argument("--m-draws", type=int, default=M_MIN)
    parser.add_argument("--k-contexts", type=int, default=K_MIN)
    parser.add_argument("--seed", type=int, default=POWER_SEED_DEFAULT)
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="封印と食い違ったまま走る (harness 検証専用。前向き結果にはならない)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="空でない出力先へ上書きする (既定は拒否。古い verdict との取り違えを防ぐ)",
    )
    args = parser.parse_args(argv)

    # ``--arm`` は全モードで必須にする (Codex MEDIUM-7)。``--verify`` でも
    # manifest の ``arm`` と突き合わせないと、control の bundle を primary として
    # 検証しても通ってしまう。
    if args.arm is None:
        parser.error("--arm は必須である (control / primary)")

    if args.verify:
        artifact_dir = args.artifact_dir
        if artifact_dir is None:
            artifact_dir = args.out_root / args.arm
        # **存在しない論文 repo を None に畳んで飲み込まない** (code-reviewer H3)。
        # そのまま渡し、verify 側が「実行できなかった」を 3 値で扱う。
        return asyncio.run(
            verify(
                artifact_dir,
                arm=args.arm,
                paper_repo=args.paper_repo,
                bank_path=args.bank if args.bank.is_file() else None,
            )
        )

    spec_path, seal_manifest_path = _resolve_paths(args)
    spec = load_arm_spec(spec_path)
    bank = load_frozen_bank(args.bank, k_contexts=args.k_contexts)
    try:
        observed = asyncio.run(observe_ollama(args.endpoint))
    except httpx.HTTPError as exc:
        print(
            f"[paper02] Ollama に到達できない ({args.endpoint}): {exc}\n"
            "          封印は実走サーバの版と digest を固定しているので、"
            "観測できなければ実走してはならない。",
            file=sys.stderr,
        )
        return 1
    uv_lock = observe_uv_lock_sha256(_REPO_ROOT / "uv.lock")
    python_version = observe_python()

    problems = preflight_problems(
        spec=spec,
        arm=args.arm,
        observed=observed,
        uv_lock=uv_lock,
        python_version=python_version,
        bank=bank,
        seed=args.seed,
        m_draws=args.m_draws,
    )
    _print_preflight(problems, arm=args.arm)

    if args.preflight:
        return 1 if problems else 0

    # --capture は事前ゲートを必ず通る。skip フラグは設けない。
    # 封印と食い違ったまま走れる唯一の道は ``--smoke`` の明示 opt-in であり、
    # それは「前向き結果ではない」と名乗ることと同義である (Codex MEDIUM-6:
    # 警告だけでは seed の食い違いが実走の後まで残る)。
    if problems and not args.smoke:
        print(
            "[capture] 中止 — draw を 1 つも取らない。"
            "封印と食い違う実走は pre-registered として提示できない。\n"
            "          harness 検証のために意図してずらすなら --smoke を明示すること。",
            file=sys.stderr,
        )
        return 1
    if problems:
        print(
            f"[capture] ⚠ --smoke: 封印と {len(problems)} 点食い違ったまま走る。"
            "この成果物は前向き結果ではない。",
            file=sys.stderr,
        )

    out_dir = (
        args.artifact_dir if args.artifact_dir is not None else args.out_root / args.arm
    )

    # 出力先の上書きを黙って許さない (code-reviewer M5)。smoke と本番の default
    # 出力先が同じなので、古い run-verdict.json が残ったまま新しい manifest が
    # 座ると、手で両者を渡したときに組み合わせがずれる。
    if out_dir.exists() and any(out_dir.iterdir()) and not args.force:
        print(
            f"[capture] 中止 — 出力先が空でない: {out_dir}\n"
            "          上書きするなら --force を明示すること "
            "(古い run-verdict.json が残ると組み合わせがずれる)。",
            file=sys.stderr,
        )
        return 1

    # 試行の痕跡を append-only で残す (code-reviewer H5)。落ちた後に「もう一度
    # 走らせる」のは自然な対応だが、成果物は上書きされるので最終 bundle は
    # 一発目と区別できなくなる。**実走の前に入れておかないと意味がない。**
    attempts = out_dir / "attempts.jsonl"
    _append_attempt(
        attempts,
        {
            "event": "start",
            "argv": list(argv) if argv is not None else sys.argv[1:],
            "preflight_problems": problems,
            "smoke": bool(args.smoke),
            "requested_m_draws": args.m_draws,
            "requested_k_contexts": args.k_contexts,
            "driver": driver_provenance(),
        },
    )

    seal_hash = sealed_manifest_sha256(seal_manifest_path)
    try:
        rendered, metrics = asyncio.run(
            capture(
                arm=args.arm,
                spec=spec,
                seal_hash=seal_hash,
                bank=bank,
                m_draws=args.m_draws,
                seed=args.seed,
                uv_lock=uv_lock,
                python_version=python_version,
                observed=observed,
                endpoint=args.endpoint,
                reobserve=observe_ollama,
                partial_path=out_dir / "run_records.partial.jsonl",
            )
        )
    except CaptureAbortedError as exc:
        # **生データを道連れにしない** (code-reviewer H2)。manifest / annotation は
        # 書かない — 書くと bundle と誤認されうる。
        _write_quarantine(out_dir, exc)
        _append_attempt(attempts, {"event": "aborted", "reason": exc.reason})
        print(f"[capture] 中止: {exc.reason}", file=sys.stderr)
        quarantined = out_dir / "run_records.quarantine.jsonl"
        print(
            f"[capture] 生データを {quarantined} へ隔離した (bundle ではない。診断用)",
            file=sys.stderr,
        )
        return 1
    metrics["driver_provenance"] = driver_provenance()
    # draw 0 の時点で何が分かっていたかを成果物に残す (code-reviewer M7)。
    metrics["preflight_problems"] = problems
    metrics["smoke"] = bool(args.smoke)
    metrics["requested_m_draws"] = args.m_draws
    metrics["requested_k_contexts"] = args.k_contexts

    # 直前の run の verdict を残さない (code-reviewer M5)。新しい manifest と
    # 古い verdict の組み合わせは、手で検査器に渡したときにずれる。
    _drop_stale_verdict(out_dir)
    _write(out_dir, rendered)
    (out_dir / "run-metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _append_attempt(
        attempts,
        {
            "event": "captured",
            "llm_calls": metrics["llm_calls"],
            "transport_retries": metrics["transport_retries"],
            "sub_sealed_scale": metrics["sub_sealed_scale"],
        },
    )
    print(f"[capture] {len(rendered) + 1} 個の成果物を {out_dir} に書いた")
    return 0


def _append_attempt(path: Path, row: dict[str, Any]) -> None:
    """試行を **append-only** で記録する (code-reviewer H5)。

    落ちた後に走らせ直すのは自然な対応だが、成果物は上書きされるので最終 bundle は
    一発目と区別できなくなる。ここに残る行だけが「何回目か」を知っている。
    `feedback_declare_everything_then_show_unknown` の核心に触れるので、
    **実走の前に**入れておく必要がある。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"recorded_at": datetime.now(UTC).isoformat(), **row}
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def _write_quarantine(out_dir: Path, exc: CaptureAbortedError) -> None:
    """中止した run の生データだけを隔離保存する (code-reviewer H2)。

    **manifest / annotation は書かない** — 書くと bundle と誤認されうる。
    部分データは ``_observed_m_draws`` が完全なセルを要求するので採点できず、
    チェリーピックには使えない。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "run_records.quarantine.jsonl").write_text(
        _records_to_jsonl(exc.records), encoding="utf-8", newline="\n"
    )
    (out_dir / "quarantine-reason.txt").write_text(
        exc.reason + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    sys.exit(main())
