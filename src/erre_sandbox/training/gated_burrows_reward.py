"""PR-18 案 B gated Burrows reward calc (軸 4 E3 final form).

PR-17 ADR §軸 4 final form: **E3 = gated Burrows score** = QC 通過 candidate
のみで Burrows reduction% rank、 QC FAIL candidate は preference pair から
除外する。 PR-16 教訓 (Vendi 圧迫を loss term 1 値で解消不可能、 hard gate
paradigm shift 必要) の直接反映。

DPN18-0 A binding で 3 level QC threshold を確定:

* ``"none"`` (level 1) = sanity check、 案 A の Vendi 圧迫再現確認
* ``"loose"`` (level 2) = length>=20 / langdetect>=0.6 / repetition<0.5
  / novelty>0.3
* ``"strict"`` (level 3) = length>=50 / langdetect>=0.85 / repetition<0.3
  / novelty>0.5

QC filter は 4 軸: length / language detection / n-gram repetition /
semantic novelty。 length / repetition は pure Python、 language detection
は langdetect (optional dep)、 semantic novelty は MPNet 等の embedding
(eval extras-only) を要する。

Phase 1 skeleton では language / novelty は callable injection で柔軟に
切替可能 (default = no-op = True passthrough)。

**実装範囲**: Phase 4 retrain は
``make_qc_filter(args.qc_level, language=args.language)`` を injection なしで
呼ぶため、 language_detector / novelty_scorer は default no-op (常に 1.0) =
**QC=loose / strict は実装上 length+repetition-only で実行** (langdetect /
MPNet 軸は default で全 PASS 化)。 ``preference-pairs-loose.json`` の
``metadata.qc_level="loose"`` は DPN18-0 A の 4 軸 loose と同名だが、 forensic
上は 「length+repetition-only loose」 と読み替えが必要 (DPN18-N2 caveat ③)。

**PR-20 で wire-in (DPN20-0 = Hybrid C+A 採用)**: langdetect-backed
LanguageDetector + MPNet embedding NoveltyScorer の wire-in を本 module で
formalize。 ``LanguageDetectorProtocol`` / ``NoveltyScorerProtocol`` を追加し、
``make_qc_filter()`` の ``language_detector`` / ``novelty_scorer`` 引数を
Protocol 型注釈に拡張 (既存 Callable type alias は back-compat のため残置)。
default = None で **back-compat default no-op** 完全保持 (PR-18 既存 test
全 PASS 維持)。

DPN20-0 採用 Hybrid C+A:

* ``"loose"`` = length + repetition + langdetect の **3 軸 active**
  (``min_semantic_novelty = 0.0`` へ refine、 novelty 軸 effective no-op
  for loose、 forensic 上 「length+repetition+langdetect-only loose」 と整合化)
* ``"strict"`` = length + repetition + langdetect + MPNet novelty の
  **4 軸完全 active** (既存値維持)

実 detector 実装は ``src/erre_sandbox/training/qc_detectors.py`` に
切り出し (lazy import + factory pattern、 [[feedback_pre_push_ci_parity]]
3 点セット = lazy import + mypy ignore_missing_imports + pytest importorskip)。

すべて pure Python (default path)、 module load は extras-free
([[feedback_pre_push_ci_parity]])。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Literal, Protocol, runtime_checkable

_LOGGER: Final = logging.getLogger(__name__)


QcThresholdLevel = Literal["none", "loose", "strict"]
"""DPN18-0 A binding: QC threshold 3 level smoke (gate なし / 緩い / 厳しい)."""


# ---------------------------------------------------------------------------
# QC threshold table (DPN18-0 A 確定値)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class QcThresholds:
    """4 軸 QC threshold (DPN18-0 A binding)."""

    min_token_length: int
    """str.split() で測る最小 token 数 (length)."""

    min_language_confidence: float
    """langdetect 等の confidence 下限 (語学一致 = 偽 polyglot 防止)."""

    max_repetition_ratio: float
    """``count(repeated 3-gram) / count(total 3-gram)`` 上限。"""

    min_semantic_novelty: float
    """Reference corpus median との embedding cosine 下限 (= novelty 確保)."""


THRESHOLD_TABLE: Final[dict[QcThresholdLevel, QcThresholds]] = {
    "none": QcThresholds(
        min_token_length=0,
        min_language_confidence=0.0,
        max_repetition_ratio=1.0,
        min_semantic_novelty=0.0,
    ),
    # DPN20-0 Hybrid C+A: loose で novelty 軸 effective no-op (>=0.0)、
    # forensic 上 「length+repetition+langdetect-only loose」 と整合化
    "loose": QcThresholds(
        min_token_length=20,
        min_language_confidence=0.6,
        max_repetition_ratio=0.5,
        min_semantic_novelty=0.0,
    ),
    "strict": QcThresholds(
        min_token_length=50,
        min_language_confidence=0.85,
        max_repetition_ratio=0.3,
        min_semantic_novelty=0.5,
    ),
}
# DPN20-0 Hybrid C+A 採用後の THRESHOLD_TABLE final form:
# * loose = length + repetition + langdetect の 3 軸 active (novelty=0.0 で
#   effective no-op、 forensic 上 「length+repetition+langdetect-only loose」 と整合)
# * strict = 4 軸完全 active (length>=50 / lang>=0.85 / rep<0.3 / novelty>=0.5)


# ---------------------------------------------------------------------------
# Detector protocols (DPN20-0 Hybrid C+A wire-in formalization)
# ---------------------------------------------------------------------------


@runtime_checkable
class LanguageDetectorProtocol(Protocol):
    """langdetect 等の language detector callable Protocol (DPN20-0 wire-in).

    Returns confidence (0.0〜1.0) that ``text`` is in ``expected_language``。
    実 implementation は ``erre_sandbox.training.qc_detectors.LangdetectAdapter``
    (lazy import + factory pattern、 [[feedback_pre_push_ci_parity]] 3 点セット)。
    default = None (= ``_default_language_detector`` = 常に 1.0) で back-compat 保持。
    """

    def __call__(self, text: str, *, expected_language: str) -> float: ...


@runtime_checkable
class NoveltyScorerProtocol(Protocol):
    """Semantic novelty scorer (MPNet cosine 等) callable Protocol (DPN20-0 wire-in).

    Returns novelty score (higher = more novel = closer to good zone)。
    実 implementation は ``erre_sandbox.training.qc_detectors.MPNetNoveltyScorer``
    (per-pair running centroid、 既存 ``tier_a/novelty.py:73-84`` pattern 踏襲)。
    default = None (= ``_default_novelty_scorer`` = 常に 1.0) で back-compat 保持。
    """

    def __call__(self, text: str) -> float: ...


LanguageDetector = Callable[..., float]
"""Legacy Callable type alias (PR-18 互換)。

DPN20-0 で ``LanguageDetectorProtocol`` を formalize したが、 既存 callable
注釈経路を残置 (型注釈互換のため)。 新規 code は ``LanguageDetectorProtocol``
を推奨。
"""

NoveltyScorer = Callable[[str], float]
"""Legacy Callable type alias (PR-18 互換)。

DPN20-0 で ``NoveltyScorerProtocol`` を formalize したが、 既存 callable
注釈経路を残置 (型注釈互換のため)。 新規 code は ``NoveltyScorerProtocol``
を推奨。
"""


class _NoOpLanguageDetector(LanguageDetectorProtocol):
    """Default no-op LanguageDetectorProtocol implementation (= 常に 1.0).

    ``make_qc_filter(language_detector=None)`` の back-compat default。
    PR-18 既存呼出経路 (= injection なし) は本 default を経由するため、
    DPN20-0 wire-in 後も既存 test 全 PASS 維持。 実 detector を使う
    場合は ``qc_detectors.make_langdetect_factory()`` 経由で
    ``LanguageDetectorProtocol`` 実装を inject すること。
    """

    def __call__(self, _text: str, *, expected_language: str) -> float:  # noqa: ARG002
        return 1.0


class _NoOpNoveltyScorer(NoveltyScorerProtocol):
    """Default no-op NoveltyScorerProtocol implementation (= 常に 1.0).

    ``make_qc_filter(novelty_scorer=None)`` の back-compat default。 PR-18
    既存呼出経路 (= injection なし) は本 default を経由するため、 DPN20-0
    wire-in 後も既存 test 全 PASS 維持。 実 scorer を使う場合は
    ``qc_detectors.make_mpnet_novelty_factory()`` 経由で
    ``NoveltyScorerProtocol`` 実装を inject すること。
    """

    def __call__(self, _text: str) -> float:
        return 1.0


_default_language_detector: LanguageDetectorProtocol = _NoOpLanguageDetector()
_default_novelty_scorer: NoveltyScorerProtocol = _NoOpNoveltyScorer()


# ---------------------------------------------------------------------------
# Pure-Python QC sub-checks (length / repetition)
# ---------------------------------------------------------------------------


def count_tokens(text: str) -> int:
    """str.split() で測る token 数 (length QC 入力)."""
    return len([t for t in text.split() if t])


def compute_repetition_ratio(text: str, *, n: int = 3) -> float:
    """``count(repeated n-gram) / count(total n-gram)`` を返す.

    text が n-gram より短い場合は 0.0 (= no repetition、 length check で別途
    判定される)。

    Args:
        text: 入力。
        n: n-gram の n (default 3)。

    Returns:
        ``[0.0, 1.0]`` の比率。
    """
    tokens = [t for t in text.split() if t]
    if len(tokens) < n:
        return 0.0
    ngrams = [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]
    total = len(ngrams)
    if total == 0:
        return 0.0
    unique = len(set(ngrams))
    repeated = total - unique
    return repeated / total


# ---------------------------------------------------------------------------
# QC filter assembly
# ---------------------------------------------------------------------------


def make_qc_filter(
    level: QcThresholdLevel,
    *,
    language: str = "de",
    language_detector: LanguageDetectorProtocol | None = None,
    novelty_scorer: NoveltyScorerProtocol | None = None,
) -> QcFilterCallable:
    """Build a QC filter callable for the requested threshold level.

    Args:
        level: ``"none"`` / ``"loose"`` / ``"strict"`` (DPN20-0 Hybrid C+A 確定)。
        language: Expected language code (Plan B kant-de 経路は ``"de"``)。
        language_detector: Optional :class:`LanguageDetectorProtocol` 実装。
            ``None`` = ``_default_language_detector`` (= 常に 1.0、 PR-18 back-compat)。
            実 detector は ``qc_detectors.make_langdetect_factory()`` 経由で inject。
        novelty_scorer: Optional :class:`NoveltyScorerProtocol` 実装。
            ``None`` = ``_default_novelty_scorer`` (= 常に 1.0、 PR-18 back-compat)。
            実 scorer は ``qc_detectors.make_mpnet_novelty_factory()`` 経由で inject。

    Returns:
        :class:`QcFilterCallable` instance (``__call__(text) -> bool``)。

    Raises:
        ValueError: If ``level`` is not in THRESHOLD_TABLE。
    """
    if level not in THRESHOLD_TABLE:
        msg = (
            f"make_qc_filter: unknown level {level!r}; expected"
            f" one of {sorted(THRESHOLD_TABLE)}"
        )
        raise ValueError(msg)
    return QcFilterCallable(
        thresholds=THRESHOLD_TABLE[level],
        level=level,
        language=language,
        language_detector=language_detector or _default_language_detector,
        novelty_scorer=novelty_scorer or _default_novelty_scorer,
    )


@dataclass(frozen=True, slots=True)
class QcFilterCallable:
    """4 軸 QC filter (length / language / repetition / novelty).

    callable: ``__call__(text: str) -> bool``。 True = PASS、 False = FAIL。

    **Novelty axis short-circuit (Hybrid C+A 補強)**:
    ``thresholds.min_semantic_novelty <= 0.0`` の場合 (= ``"loose"``
    level や ``"none"`` level)、 novelty axis を **completely skip** する。
    これにより loose level で MPNet ``novelty_scorer`` が呼ばれず、
    forensic 上の 「length+repetition+langdetect-only loose」 と実装が完全
    一致する (=  MPNet model load / stateful scorer side-effect を loose で
    完全回避)。

    **State reset**: :meth:`reset_state` を
    呼ぶと ``novelty_scorer`` の rolling prior buffer がクリアされる
    (per-pair/triple scope の境界で呼び出すこと)。
    :func:`build_preference_pairs` 内で triple 境界毎に reset_state() を
    呼ぶ実装が user binding mandatory。
    """

    thresholds: QcThresholds
    level: QcThresholdLevel
    language: str
    language_detector: LanguageDetectorProtocol
    novelty_scorer: NoveltyScorerProtocol

    def reset_state(self) -> None:
        """Reset stateful scorer (= MPNetNoveltyScorer rolling prior buffer).

        DPN20-2 #3 binding: builder 側で per-pair/triple scope の境界
        (= triple ごと、 等) で本 method を呼ぶ。 reset() を持たない
        scorer (= ``_NoOpNoveltyScorer`` 等の stateless) では no-op で
        skip する。
        """
        reset = getattr(self.novelty_scorer, "reset", None)
        if callable(reset):
            reset()

    def __call__(self, text: str) -> bool:
        # level "none" は全 sub-check が threshold 0 / 上限 1.0 / lower 0 のため
        # short-circuit せず通常 pipeline 通過 (= 常に True)。 ただし length
        # check の min_token_length=0 は 0 token も PASS とするため対応。
        if not text:
            # 空 string は level "none" 以外で必ず FAIL (length=0)。
            return self.thresholds.min_token_length == 0

        if count_tokens(text) < self.thresholds.min_token_length:
            return False

        if compute_repetition_ratio(text) > self.thresholds.max_repetition_ratio:
            return False

        lang_conf = self.language_detector(text, expected_language=self.language)
        if lang_conf < self.thresholds.min_language_confidence:
            return False

        # min_semantic_novelty <= 0.0 (loose level) では
        # novelty axis を short-circuit。 MPNet scorer の呼出 / model load /
        # stateful prior buffer 更新を loose では完全回避し、 forensic 上の
        # 「length+repetition+langdetect-only loose」 と実装一致を担保する。
        if self.thresholds.min_semantic_novelty <= 0.0:
            return True

        novelty = self.novelty_scorer(text)
        return novelty >= self.thresholds.min_semantic_novelty


# ---------------------------------------------------------------------------
# Per-candidate Burrows reward (E3 = gated Burrows reduction%)
# ---------------------------------------------------------------------------


def compute_gated_burrows_reward(
    text: str,
    *,
    qc_filter: QcFilterCallable,
    burrows_delta_text: float,
    burrows_delta_baseline: float,
) -> float:
    """Per-candidate gated Burrows reward = QC PASS 時 reduction%、 FAIL 時 -inf.

    PR-17 ADR §軸 4 E3 (= reward は 「QC 通過後の選別指標」) の per-candidate
    実装。 Burrows reduction% = (baseline - text) / baseline * 100 で、 値が
    大きいほど reference に近づいた (= better)。

    Args:
        text: Candidate text (QC filter 入力)。
        qc_filter: :func:`make_qc_filter` 出力 callable。
        burrows_delta_text: text の Burrows Delta (compute_burrows_delta で先に計算)。
        burrows_delta_baseline: baseline (e.g. no-LoRA) の Burrows Delta。

    Returns:
        QC PASS 時: reduction% (``float("nan")`` if baseline == 0)。
        QC FAIL 時: ``float("-inf")`` (= preference rank の最下位)。
    """
    if not qc_filter(text):
        return float("-inf")
    if burrows_delta_baseline == 0.0:
        return float("nan")
    return (
        (burrows_delta_baseline - burrows_delta_text) / burrows_delta_baseline * 100.0
    )


__all__ = [
    "THRESHOLD_TABLE",
    "LanguageDetector",
    "LanguageDetectorProtocol",
    "NoveltyScorer",
    "NoveltyScorerProtocol",
    "QcFilterCallable",
    "QcThresholdLevel",
    "QcThresholds",
    "compute_gated_burrows_reward",
    "compute_repetition_ratio",
    "count_tokens",
    "make_qc_filter",
]
