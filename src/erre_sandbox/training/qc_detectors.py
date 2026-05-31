"""PR-20 DPN20-0 Hybrid C+A wire-in: LangdetectAdapter + MPNetNoveltyScorer.

PR-18 DPN18-0 A 4 軸 QC binding (length + langdetect + repetition + MPNet
novelty) と forensic 整合を取るために、 PR-20 で実 detector を
``make_qc_filter()`` に inject 可能な経路で実装する。

採用案: DPN20-0 Hybrid C+A:

* QC=loose: length + repetition + langdetect の 3 軸 active
  (``THRESHOLD_TABLE["loose"].min_semantic_novelty = 0.0`` で novelty 軸
  effective no-op)
* QC=strict: length + repetition + langdetect + MPNet novelty の 4 軸完全 active

**設計制約**: heavy deps top-level import 禁止 ([[architecture-rules]] +
[[feedback_pre_push_ci_parity]] 3 点セット = lazy import + mypy
``ignore_missing_imports`` + pytest ``importorskip``)。 ``langdetect`` および
``sentence_transformers`` は ``[project.optional-dependencies].eval`` 経由で
install され、 本 module の class ``__init__`` / ``__call__`` body 内で
**関数 body 内 lazy import** を行う。 module load は base install (eval extras
なし) でも失敗しない (= ``from erre_sandbox.training import qc_detectors`` は
OK、 ただし factory 呼出時に extras 必要)。

参考: 既存実装

* a prior langdetect-based classifier helper — langdetect
  DetectorFactory.seed + detect_langs + candidate filtering pattern
* ``src/erre_sandbox/evidence/tier_a/novelty.py:33-108`` — per-pair running
  centroid + MPNet lazy load pattern
* ``src/erre_sandbox/evidence/tier_b/vendi.py:312-378`` — MPNet encode +
  cosine kernel pattern
"""

from __future__ import annotations

import logging
import math
from collections import deque
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.training.gated_burrows_reward import (
        LanguageDetectorProtocol,
        NoveltyScorerProtocol,
    )

_LOGGER: Final = logging.getLogger(__name__)

_DEFAULT_LANG_MIN_LENGTH: Final[int] = 5
"""LangdetectAdapter で 短文 fragile 防止のため return 0.0 強制する閾値 (token 数)。"""

_DEFAULT_LANG_SEED: Final[int] = 0
"""``langdetect.DetectorFactory.seed`` 設定値 (deterministic、 既存
``compute_burrows_delta.py:67`` と同値)."""

_DEFAULT_NOVELTY_MODEL: Final[str] = "sentence-transformers/all-mpnet-base-v2"
"""MPNetNoveltyScorer default model ID (既存 ``tier_a/novelty.py:102`` と同値)."""

_DEFAULT_NOVELTY_WINDOW: Final[int] = 16
"""MPNetNoveltyScorer per-pair running centroid の rolling window size default."""


# ---------------------------------------------------------------------------
# LangdetectAdapter (LanguageDetectorProtocol 実装)
# ---------------------------------------------------------------------------


class LangdetectAdapter:
    """``langdetect`` を ``LanguageDetectorProtocol`` に adapt する実 detector.

    既存の langdetect 分類 helper の
    ``_classify_utterance()`` pattern を per-text confidence 返却 API に
    変換。 短文 (``min_length`` 未満) は fragile 判定なので 0.0 を返し、
    QC FAIL 扱いにする。

    Args:
        min_length: 入力 text の最小 token 数 (``str.split()`` 基準)。 未満は
            confidence=0.0 強制 (短文 fragile 防止、 DPN20-1 binding 値 = 5)。
        seed: ``langdetect.DetectorFactory.seed`` 値 (deterministic
            reproducibility のため)。 既存 ``compute_burrows_delta.py:67`` と
            合わせて 0 を default。
    """

    def __init__(
        self,
        *,
        min_length: int = _DEFAULT_LANG_MIN_LENGTH,
        seed: int = _DEFAULT_LANG_SEED,
    ) -> None:
        self._min_length = min_length
        self._seed = seed
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Set ``DetectorFactory.seed`` once per instance (idempotent)."""
        if self._initialized:
            return
        # heavy dep behind eval extras
        from langdetect import DetectorFactory  # noqa: PLC0415

        DetectorFactory.seed = self._seed
        self._initialized = True

    def __call__(self, text: str, *, expected_language: str) -> float:
        """Return confidence (0.0〜1.0) that ``text`` is in ``expected_language``.

        Args:
            text: 入力 text。
            expected_language: 期待言語 code (kant-de 経路は ``"de"``)。

        Returns:
            ``[0.0, 1.0]`` の confidence。 short text / detection failure /
            expected_language が candidate に無い場合は 0.0。

        Notes:
            短文判定 (token 数 < ``min_length``) は ja/zh 等の
            CJK 文字を含む text には適用しない (空白なし表記で不当に
            FAIL するのを防止、 user DPN20-2 #4 + 既存
            ``compute_burrows_delta.py:104`` pattern)。
        """
        # DPN20-2 #4: CJK 文字 (CJK Unified Ideographs / Hiragana / Katakana 等
        # ord > 0x3000) を含む場合は token 数 short-circuit を skip
        is_cjk = any(ord(c) > 0x3000 for c in text)  # noqa: PLR2004
        if not is_cjk and len(text.split()) < self._min_length:
            return 0.0
        try:
            # heavy dep behind eval extras
            from langdetect import detect_langs  # noqa: PLC0415
            from langdetect.lang_detect_exception import (  # noqa: PLC0415
                LangDetectException,
            )
        except ImportError:
            _LOGGER.warning(
                "langdetect not installed; LangdetectAdapter returning 0.0."
                " Install via 'uv sync --extra eval'.",
            )
            return 0.0

        self._ensure_initialized()

        try:
            candidates = detect_langs(text)
        except LangDetectException:
            return 0.0
        if not candidates:
            return 0.0
        for cand in candidates:
            if str(cand.lang) == expected_language:
                return float(cand.prob)
        return 0.0


# ---------------------------------------------------------------------------
# MPNetNoveltyScorer (NoveltyScorerProtocol 実装、 per-pair running centroid)
# ---------------------------------------------------------------------------


class MPNetNoveltyScorer:
    """MPNet embedding cosine novelty scorer (per-pair running centroid).

    既存 ``src/erre_sandbox/evidence/tier_a/novelty.py:33-88`` の
    ``compute_semantic_novelty()`` (一括計算) を per-call API に分解。
    ``__call__(text)`` 呼出ごとに:

    1. text を encode (lazy import + lazy model load)
    2. prior buffer (rolling window) の centroid 計算
    3. novelty = ``1 - cos(text_emb, centroid)``
    4. text_emb を prior buffer に追加 (max ``window_size`` まで rolling)

    prior buffer が empty の場合 (= first text) は 1.0 (= max novelty) を返す。

    **State scope binding (user DPN20-2 #3)**: 本 scorer は rolling prior
    buffer を **per-instance state** として保持するため、 ``__call__()`` の
    結果は **呼出順序に依存** する (= 同じ text 列を渡しても、 instance を
    跨ぐと結果が変わる)。 builder 側で以下のいずれかを必ず採用:

    * **per-pair/triple scope 固定**: pair/triple ごとに新 instance を生成
      (= builder が ``MPNetNoveltyScorer(...)`` を毎回呼ぶ)
    * **scope 切替時 reset()**: 同 instance を共有しつつ、 scope の境界で
      :meth:`reset` を呼んで prior buffer を空に戻す

    **Thread safety**: 本 scorer は **thread-safe ではない** (per-instance
    state は protected されない)。 multi-thread 経路で使うなら caller 側で
    locking する。 PR-20 spike runner は単一 process で順次呼出のため OK。

    Args:
        model_id: SentenceTransformer model ID (既存 ``tier_a/novelty.py:102``
            と同 ``"sentence-transformers/all-mpnet-base-v2"`` を default)。
        window_size: Rolling window size (default 16)。 1+ で per-pair running
            centroid の anchor 範囲を制御。
    """

    def __init__(
        self,
        *,
        model_id: str = _DEFAULT_NOVELTY_MODEL,
        window_size: int = _DEFAULT_NOVELTY_WINDOW,
    ) -> None:
        if window_size < 1:
            msg = f"MPNetNoveltyScorer: window_size must be >= 1, got {window_size}"
            raise ValueError(msg)
        self._model_id = model_id
        self._window_size = window_size
        self._model: Any | None = None
        self._prior_embeddings: deque[list[float]] = deque(maxlen=window_size)

    def reset(self) -> None:
        """Clear the rolling prior buffer (state scope reset).

        DPN20-2 #3 binding: pair/triple scope boundary 等で同 instance を
        共有しつつ prior buffer を空に戻す API。 lazy-loaded model
        (``self._model``) は不変保持 (model load cost ~5-10s を再支払いしない)。
        """
        self._prior_embeddings.clear()

    def _ensure_model(self) -> Any:
        """Lazy-load SentenceTransformer (1 instance per scorer, idempotent)."""
        if self._model is not None:
            return self._model
        from sentence_transformers import (  # noqa: PLC0415  # heavy ML dep behind eval extras
            SentenceTransformer,
        )

        self._model = SentenceTransformer(self._model_id)
        return self._model

    def _encode(self, text: str) -> list[float]:
        """Encode single text to ``list[float]`` (L2-normalized for cosine)."""
        model = self._ensure_model()
        vec = model.encode([text], show_progress_bar=False)
        # vec shape = (1, D)
        flat = [float(x) for x in vec[0]]
        norm = math.sqrt(sum(x * x for x in flat))
        if norm == 0.0:
            return flat
        return [x / norm for x in flat]

    @staticmethod
    def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
        """Cosine similarity of two L2-normalized vectors (= dot product)."""
        if len(a) != len(b):
            msg = f"vector length mismatch: {len(a)} vs {len(b)}"
            raise ValueError(msg)
        return float(sum(x * y for x, y in zip(a, b, strict=True)))

    def __call__(self, text: str) -> float:
        """Return novelty score (higher = more novel, in ``[0.0, 2.0]``).

        Returns:
            ``1 - cos(text_emb, prior_centroid)`` if prior buffer non-empty,
            else ``1.0`` (max novelty for first text)。
        """
        if not text:
            return 0.0
        text_emb = self._encode(text)
        if not self._prior_embeddings:
            self._prior_embeddings.append(text_emb)
            return 1.0
        # Compute centroid (mean across prior embeddings)
        dim = len(text_emb)
        centroid = [0.0] * dim
        for prior in self._prior_embeddings:
            for i, x in enumerate(prior):
                centroid[i] += x
        n = len(self._prior_embeddings)
        centroid = [x / n for x in centroid]
        # L2-normalize centroid
        c_norm = math.sqrt(sum(x * x for x in centroid))
        if c_norm == 0.0:
            # Antipodal prior turns cancelled; treat as max novelty
            # (1.0、 既存 tier_a/novelty.py:73-84 pattern と同 fallback)
            self._prior_embeddings.append(text_emb)
            return 1.0
        centroid_unit = [x / c_norm for x in centroid]
        cos_sim = self._cosine_similarity(text_emb, centroid_unit)
        novelty = 1.0 - cos_sim
        self._prior_embeddings.append(text_emb)
        return float(novelty)


# ---------------------------------------------------------------------------
# Factory functions (PR-20 caller = pr18_build_preference_pairs.py で利用)
# ---------------------------------------------------------------------------


def make_langdetect_factory(
    *,
    min_length: int = _DEFAULT_LANG_MIN_LENGTH,
    seed: int = _DEFAULT_LANG_SEED,
) -> LanguageDetectorProtocol:
    """Return a :class:`LangdetectAdapter` instance.

    使用例::

        from erre_sandbox.training.gated_burrows_reward import make_qc_filter
        from erre_sandbox.training.qc_detectors import make_langdetect_factory

        qc_filter = make_qc_filter(
            "loose",
            language="de",
            language_detector=make_langdetect_factory(),
        )

    Args:
        min_length: 短文 fragile 防止閾値 (default 5、 DPN20-1 binding)。
        seed: deterministic seed (default 0、 既存 compute_burrows_delta.py 同値)。

    Returns:
        :class:`LangdetectAdapter` instance。
    """
    return LangdetectAdapter(min_length=min_length, seed=seed)


def make_mpnet_novelty_factory(
    *,
    model_id: str = _DEFAULT_NOVELTY_MODEL,
    window_size: int = _DEFAULT_NOVELTY_WINDOW,
) -> NoveltyScorerProtocol:
    """Return a :class:`MPNetNoveltyScorer` instance.

    使用例::

        from erre_sandbox.training.gated_burrows_reward import make_qc_filter
        from erre_sandbox.training.qc_detectors import make_mpnet_novelty_factory

        qc_filter = make_qc_filter(
            "strict",
            language="de",
            novelty_scorer=make_mpnet_novelty_factory(window_size=16),
        )

    Args:
        model_id: SentenceTransformer model ID (default
            "sentence-transformers/all-mpnet-base-v2")。
        window_size: rolling window (default 16、 DPN20-1 binding)。

    Returns:
        :class:`MPNetNoveltyScorer` instance。
    """
    return MPNetNoveltyScorer(model_id=model_id, window_size=window_size)


__all__ = [
    "LangdetectAdapter",
    "MPNetNoveltyScorer",
    "make_langdetect_factory",
    "make_mpnet_novelty_factory",
]
