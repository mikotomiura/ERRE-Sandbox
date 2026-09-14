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
* ``bank_checksum`` は **消費した凍結 bank の bytes** から再計算
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


async def observe_ollama(
    endpoint: str, *, client: httpx.AsyncClient | None = None
) -> OllamaObservation:
    """``/api/version`` と ``/api/tags`` を読む。

    ``model_digest`` を CLI 引数で受けないのがこの関数の存在理由である。引数は
    著者の申告であり、封印との一致はそのとき「著者が正しく打った」ことしか
    示さない。
    """
    owned = client is None
    http = client if client is not None else httpx.AsyncClient(base_url=endpoint)
    try:
        version_resp = await http.get("/api/version")
        version_resp.raise_for_status()
        version = str(version_resp.json().get("version", "unknown"))

        tags_resp = await http.get("/api/tags")
        tags_resp.raise_for_status()
        digests = {
            str(model["name"]): str(model["digest"])
            for model in tags_resp.json().get("models", [])
        }
    finally:
        if owned:
            await http.aclose()
    return OllamaObservation(version=version, digests=digests)


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
    """

    inner: Any
    think_values: set[Any] = field(default_factory=set)
    models: set[str] = field(default_factory=set)
    calls: int = 0

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        sampling: ResolvedSampling,
        model: str | None = None,
        options: dict[str, Any] | None = None,
        think: bool | None = None,
    ) -> ChatResponse:
        self.calls += 1
        self.think_values.add(think)
        response = await self.inner.chat(
            messages, sampling=sampling, model=model, options=options, think=think
        )
        self.models.add(response.model)
        return response

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
        else OllamaChatClient(model=model, endpoint=endpoint)
    )
    spy = ThinkAndModelSpy(inner=inner)
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
            raise SystemExit(msg)
        before_digest = observed.digests.get(model)
        after_digest = after.digests.get(model)
        if before_digest != after_digest:
            msg = (
                f"[paper02] 実走中に {model} の digest が変わった: "
                f"{before_digest} -> {after_digest}。この run は封印を名乗れない。"
            )
            raise SystemExit(msg)

    cap = 2 * m_draws * k_contexts
    actual = llm_client.inner_invocations
    if actual > cap:
        msg = (
            f"[paper02] M-loop の呼び出し上限を超えた: {actual} > {cap} (cost ceiling)"
        )
        raise RuntimeError(msg)

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
    observed_m = _observed_m_draws(records)
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
        raise SystemExit(msg)

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
    metrics = {
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
) -> bool:
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
    """
    manifest_path = artifact_dir / "run-manifest.json"
    if not manifest_path.is_file():
        print(f"[verify] FAIL manifest が無い: {manifest_path}")
        return False
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    recorded_arm = manifest.get("arm")
    if recorded_arm != arm:
        print(
            f"[verify] FAIL この bundle のアームは {recorded_arm!r}、"
            f"指定は {arm!r}"
        )
        return False
    records_text = (artifact_dir / "run_records.jsonl").read_text(encoding="utf-8")
    annotation_text = (artifact_dir / "run_annotation.jsonl").read_text(
        encoding="utf-8"
    )

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

    if not ok:
        # 改竄された bundle の古い verdict を残さない。残すと「検査に落ちたのに
        # 判定だけ手元にある」状態になる。
        stale = artifact_dir / "run-verdict.json"
        if stale.exists():
            stale.unlink()
            print("[verify] 古い run-verdict.json を削除した")
        print("[verify] MISMATCH — 整合が取れないので scorer を走らせない")
        return False

    verdict = score_bank_annotation(
        annotation_rows=annotation_dicts,
        manifest=manifest,
        n_replicates=N_REPLICATES_DEFAULT,
        seed=POWER_SEED_DEFAULT,
        require_powered_scale=True,
    )
    verdict_dict = verdict_to_dict(verdict)
    verdict_text = handoff.canonical_dumps(verdict_dict) + "\n"
    verdict_path = artifact_dir / "run-verdict.json"
    verdict_path.write_text(verdict_text, encoding="utf-8", newline="\n")
    print(f"[verify] VERDICT {verdict.verdict}")
    print(f"[verify] reason: {'; '.join(verdict.reason)}")

    if paper_repo is not None:
        sealed_ok = run_sealed_seal_check(
            paper_repo=paper_repo,
            manifest_path=manifest_path,
            verdict_path=verdict_path,
            arm=arm,
        )
        if not sealed_ok:
            if manifest.get("sub_sealed_scale"):
                # 封印未満を自己申告している bundle は、封印検査に落ちるのが正しい。
                # harness 検証としては成功なので OK とするが、**前向き結果ではない**。
                print(
                    "[verify] NOTE 封印検査は落ちた。この bundle は "
                    "sub_sealed_scale=true を名乗っており、前向き結果ではない"
                )
            else:
                print(
                    "[verify] FAIL 封印検査に落ちた。封印規模を名乗る bundle が "
                    "verify_seal を通らないので OK と言わない"
                )
                return False
    print("[verify] OK")
    return True


def run_sealed_seal_check(
    *, paper_repo: Path, manifest_path: Path, verdict_path: Path, arm: str
) -> bool:
    """封印検査器 ``verify_seal.py`` を **そのまま** 走らせる (Codex HIGH-2).

    driver の整合検査は封印検査ではない。``model_digest`` や ``bank_checksum`` を
    改竄した manifest でも driver は verdict を出せる。正典を複製せず呼ぶ。
    """
    script = paper_repo / "analysis" / "scripts" / "verify_seal.py"
    if not script.is_file():
        print(f"[verify] NOTE 封印検査器が見つからないので照合を飛ばした: {script}")
        return True
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
    completed = subprocess.run(  # noqa: S603
        command, cwd=paper_repo, capture_output=True, text=True, check=False
    )
    for line in (completed.stdout + completed.stderr).splitlines():
        if line.strip():
            print(f"[verify][seal] {line}")
    return completed.returncode == 0


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
        paper_repo = args.paper_repo if args.paper_repo.is_dir() else None
        ok = asyncio.run(verify(artifact_dir, arm=args.arm, paper_repo=paper_repo))
        return 0 if ok else 1

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

    seal_hash = sealed_manifest_sha256(seal_manifest_path)
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
        )
    )
    metrics["driver_provenance"] = driver_provenance()
    out_dir = (
        args.artifact_dir if args.artifact_dir is not None else args.out_root / args.arm
    )
    _write(out_dir, rendered)
    (out_dir / "run-metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"[capture] {len(rendered) + 1} 個の成果物を {out_dir} に書いた")
    return 0


if __name__ == "__main__":
    sys.exit(main())
