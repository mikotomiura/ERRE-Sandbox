"""PR-18 案 B preference pair builder (軸 1 A2 = PR-16 既存 20 shard re-rank).

PR-17 ADR §軸 1 final form 通り、 PR-16 既存 20 shard forensic から
LoRA-on / no-LoRA generation pair を抽出し、 Burrows reduction% (= reference
Burrows Delta が小さい side が "good") で chosen/rejected (DPO / IPO 用) or
binary label (KTO 用) preference dataset を構築する。

Input: completion triples JSON (offline preprocessing で抽出済の per-prompt
LoRA-on + no-LoRA completion pair list)。 PR-16 既存 DuckDB shard からの
extraction は別 script (PR-16 completion triples extractor、
Phase 4 prep で実装) で実施し、 本 module は triples → preference pair
変換のみを担当 (offline 純関数的 surface)。

Output: ``preference_burrows.py`` の ``_load_preference_pair_records`` が
読む JSON 形式:

.. code-block:: json

    {
      "format_version": "1",
      "metadata": {...},
      "pair_records": [
        {"prompt": str, "chosen": str, "rejected": str, "burrows_delta": float},
        ...
      ],
      "binary_records": [
        {"prompt": str, "completion": str, "label": bool, "burrows_pct": float},
        ...
      ]
    }

QC filter は Phase 3 ``gated_burrows_reward.py`` の :func:`apply_qc_filter`
で適用 (E3 = QC PASS のみで pair 構築、 FAIL は除外)。

すべて pure Python (numpy なし)、 module load は ``[training]`` /
``[training-preference]`` extras-free ([[feedback_pre_push_ci_parity]])。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from erre_sandbox.evidence.tier_a.burrows import BurrowsReference


_LOGGER: Final = logging.getLogger(__name__)


FORMAT_VERSION: Final[str] = "1"
"""preference pair JSON の schema version (将来 schema 変更時に bump)."""


# ---------------------------------------------------------------------------
# Input + output dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CompletionTriple:
    """Per-prompt PR-16 既存 20 shard の completion triple (Phase 2 入力単位).

    extraction は別 script (PR-16 completion triples extractor、
    Phase 4 prep) で PR-16 DuckDB shard から実施、 本 module は triples →
    preference pair 変換のみを担当する純関数的 surface。
    """

    prompt: str
    lora_on_completion: str
    no_lora_completion: str
    stim_id: str
    run_id: int
    shard_pair_index: int = 0


@dataclass(frozen=True, slots=True)
class PreferencePairRecord:
    """DPO / IPO 用 chosen/rejected pair record."""

    prompt: str
    chosen: str
    rejected: str
    burrows_delta: float
    """abs(burrows_delta_chosen - burrows_delta_rejected)。 pair 強度の forensic。"""


@dataclass(frozen=True, slots=True)
class BinaryRecord:
    """KTO 用 binary label record (good/bad)."""

    prompt: str
    completion: str
    label: bool
    """True = good (Burrows Delta が reference に近い側)。"""

    burrows_pct: float
    """Burrows Delta の絶対値 (forensic、 small = closer to reference)."""


@dataclass(frozen=True, slots=True)
class PreferenceBuildResult:
    """Phase 2 出力 = ``preference_burrows.py`` の入力 JSON 内容."""

    format_version: str
    pair_records: tuple[PreferencePairRecord, ...]
    binary_records: tuple[BinaryRecord, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to JSON-compatible dict."""
        return {
            "format_version": self.format_version,
            "metadata": dict(self.metadata),
            "pair_records": [
                {
                    "prompt": r.prompt,
                    "chosen": r.chosen,
                    "rejected": r.rejected,
                    "burrows_delta": r.burrows_delta,
                }
                for r in self.pair_records
            ],
            "binary_records": [
                {
                    "prompt": r.prompt,
                    "completion": r.completion,
                    "label": r.label,
                    "burrows_pct": r.burrows_pct,
                }
                for r in self.binary_records
            ],
        }


# ---------------------------------------------------------------------------
# Triple loader
# ---------------------------------------------------------------------------


def load_completion_triples(triples_path: Path) -> list[CompletionTriple]:
    """Load completion triples JSON (offline extraction の出力).

    Expected schema:

    .. code-block:: json

        {
          "format_version": "1",
          "source_shard_pairs": [...],
          "completion_triples": [
            {
              "prompt": str,
              "lora_on_completion": str,
              "no_lora_completion": str,
              "stim_id": str,
              "run_id": int,
              "shard_pair_index": int
            },
            ...
          ]
        }

    Args:
        triples_path: Extraction script 出力 JSON path。

    Returns:
        ``list[CompletionTriple]``。

    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If JSON schema is invalid.
    """
    if not triples_path.is_file():
        msg = f"completion triples JSON not found: {triples_path}"
        raise FileNotFoundError(msg)
    payload = json.loads(triples_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = (
            "completion triples JSON root must be an object, got"
            f" {type(payload).__name__}"
        )
        raise TypeError(msg)
    raw_triples = payload.get("completion_triples")
    if raw_triples is None:
        msg = "completion triples JSON missing 'completion_triples' list"
        raise ValueError(msg)
    if not isinstance(raw_triples, list):
        msg = (
            "completion triples JSON 'completion_triples' must be a list,"
            f" got {type(raw_triples).__name__}"
        )
        raise TypeError(msg)
    return [
        CompletionTriple(
            prompt=str(t["prompt"]),
            lora_on_completion=str(t["lora_on_completion"]),
            no_lora_completion=str(t["no_lora_completion"]),
            stim_id=str(t["stim_id"]),
            run_id=int(t["run_id"]),
            shard_pair_index=int(t.get("shard_pair_index", 0)),
        )
        for t in raw_triples
    ]


# ---------------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------------


def build_preference_pairs(  # noqa: C901  # 4 軸 QC + pair + binary branch を 1 関数で集約 (PR-18 軸 1 A2)
    triples: Iterable[CompletionTriple],
    reference: BurrowsReference,
    *,
    language: str,
    qc_filter: Any | None = None,
    metadata_overrides: dict[str, Any] | None = None,
) -> PreferenceBuildResult:
    """Convert completion triples to DPO/IPO pairs + KTO binary records.

    For each triple:

    1. Apply optional ``qc_filter`` (E3 gated Burrows の QC filter callable)。
       両 completion とも QC PASS でない場合は除外。 片側のみ FAIL は片側を
       drop して KTO binary に残す (chosen 側のみ "good" label)。
    2. Burrows Delta を両 completion で計算。 NaN (= 計測不能) は除外。
    3. Smaller delta = closer to reference = chosen (DPO/IPO pair)。
    4. Binary record: chosen → label=True, rejected → label=False。

    Args:
        triples: ``CompletionTriple`` の iterable。
        reference: Burrows reference profile (DE / EN / JA)。
        language: Reference language tag ("de" 推奨、 Plan B kant-de 整合)。
        qc_filter: Optional callable ``(text: str) -> bool`` (Phase 3 で
            ``gated_burrows_reward.make_qc_filter()`` から生成)。 None 時は
            QC filter 適用なし (level 1 "gate なし" smoke 等)。
        metadata_overrides: 出力 JSON ``metadata`` に embed する追加 field。

    Returns:
        :class:`PreferenceBuildResult` (pair_records + binary_records)。
    """
    from erre_sandbox.evidence.tier_a.burrows import (  # noqa: PLC0415
        compute_burrows_delta,
    )

    pair_records: list[PreferencePairRecord] = []
    binary_records: list[BinaryRecord] = []
    dropped_qc_fail = 0
    dropped_delta_nan = 0
    total_triples = 0

    for triple in triples:
        total_triples += 1
        # per-triple scope binding。
        # stateful novelty_scorer (= MPNetNoveltyScorer rolling centroid) を
        # triple 境界で reset し、 各 triple 内の 2 candidate を等価条件で
        # 評価する。 QcFilterCallable.reset_state() は無い場合 no-op。
        reset_state = getattr(qc_filter, "reset_state", None) if qc_filter else None
        if callable(reset_state):
            reset_state()
        lora_pass = qc_filter is None or qc_filter(triple.lora_on_completion)
        no_lora_pass = qc_filter is None or qc_filter(triple.no_lora_completion)
        if not lora_pass and not no_lora_pass:
            dropped_qc_fail += 1
            continue

        lora_delta = (
            compute_burrows_delta(
                triple.lora_on_completion,
                reference,
                language=language,
            )
            if lora_pass
            else float("nan")
        )
        no_lora_delta = (
            compute_burrows_delta(
                triple.no_lora_completion,
                reference,
                language=language,
            )
            if no_lora_pass
            else float("nan")
        )

        lora_finite = lora_delta == lora_delta  # not NaN  # noqa: PLR0124
        no_lora_finite = no_lora_delta == no_lora_delta  # not NaN  # noqa: PLR0124

        if not lora_finite and not no_lora_finite:
            dropped_delta_nan += 1
            continue

        # Pair record (DPO/IPO): 両 finite な場合のみ
        if lora_finite and no_lora_finite:
            if lora_delta < no_lora_delta:
                chosen, rejected = (
                    triple.lora_on_completion,
                    triple.no_lora_completion,
                )
            elif no_lora_delta < lora_delta:
                chosen, rejected = (
                    triple.no_lora_completion,
                    triple.lora_on_completion,
                )
            else:
                # Tie = drop pair (preference signal なし)
                continue
            pair_records.append(
                PreferencePairRecord(
                    prompt=triple.prompt,
                    chosen=chosen,
                    rejected=rejected,
                    burrows_delta=abs(lora_delta - no_lora_delta),
                ),
            )

        # Binary records (KTO): 各 finite side ごとに good/bad label 化
        # good = reference に近い side (smaller delta)
        deltas: list[tuple[str, float, bool]] = []
        if lora_finite:
            is_lora_good = (not no_lora_finite) or lora_delta <= no_lora_delta
            deltas.append((triple.lora_on_completion, lora_delta, is_lora_good))
        if no_lora_finite:
            is_no_lora_good = (not lora_finite) or no_lora_delta < lora_delta
            deltas.append((triple.no_lora_completion, no_lora_delta, is_no_lora_good))
        for text, delta, label in deltas:
            binary_records.append(
                BinaryRecord(
                    prompt=triple.prompt,
                    completion=text,
                    label=label,
                    burrows_pct=delta,
                ),
            )

    metadata = {
        "total_triples": total_triples,
        "pair_record_count": len(pair_records),
        "binary_record_count": len(binary_records),
        "dropped_qc_fail": dropped_qc_fail,
        "dropped_delta_nan": dropped_delta_nan,
        "language": language,
    }
    if metadata_overrides is not None:
        metadata.update(metadata_overrides)

    _LOGGER.info(
        "build_preference_pairs: total=%d pair=%d binary=%d qc_fail=%d nan=%d",
        total_triples,
        len(pair_records),
        len(binary_records),
        dropped_qc_fail,
        dropped_delta_nan,
    )

    return PreferenceBuildResult(
        format_version=FORMAT_VERSION,
        pair_records=tuple(pair_records),
        binary_records=tuple(binary_records),
        metadata=metadata,
    )


def save_preference_pairs(result: PreferenceBuildResult, output_path: Path) -> None:
    """Persist build result as JSON (``preference_burrows.py`` 入力形式)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _LOGGER.info("save_preference_pairs: wrote %s", output_path)


__all__ = [
    "FORMAT_VERSION",
    "BinaryRecord",
    "CompletionTriple",
    "PreferenceBuildResult",
    "PreferencePairRecord",
    "build_preference_pairs",
    "load_completion_triples",
    "save_preference_pairs",
]
