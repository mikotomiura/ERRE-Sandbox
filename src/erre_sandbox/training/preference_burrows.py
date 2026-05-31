"""PR-18 案 B (Composite Burrows preference optimization) trainer wrapper.

Architecture decision: PR-17 ADR ``da-XX-composite-burrows-preference-optimization.md``
(6 軸 final form、 DPN18-N 反映):

* 軸 1 (preference data) = A2 = PR-16 既存 20 shard re-rank
* 軸 2 (algorithm) = **B2 KTO + τ=1.0 確定** (DPN18-N、 Phase 1.5 preflight
  spike outcome、 sensitivity stdev=0.0024 = 最 robust + envelope ~3 min/cell)
* 軸 3 (policy 配置) = C3 = PR-16 λ=0.3 best-Burrows warm start + frozen
  reference = PR-14 control snapshot
* 軸 4 (reward) = E3 = gated Burrows (QC fail 除外 + 通過後 Burrows rank)
  — 注: DPN18-0 A の 4 軸 (length + langdetect + repetition + MPNet novelty)
  のうち langdetect / MPNet は default no-op、 PR-18 実 retrain では
  length+repetition-only で実行 (wire-in は別途)
* 軸 5 (学習 surface) = D1 = TRL trainer (KTOTrainer、
  ``trl.experimental.kto`` 由来 = stable promotion 未確定、
  ``[training-preference]`` extras-only dep)
* 軸 6 (採用基準) = PR-15 継承固定 (gauntlet 3 件 + DPN15-2a 4 OR-joined
  contingency)、 Burrows row PASS = ``reduction ≥ +1.5pt`` OR ``CI lower が
  Run 1 control 比で改善`` (PR-17 OR predicate、 DPN17-N2)

Public surfaces:

* :class:`PreferenceAlgorithm` — B1/B2/B3 enum.
* :class:`PreferenceOptimizationConfig` — algorithm-neutral config dataclass.
* :class:`PreferenceTrainingResult` — forensic outcome (embedded in
  ``train_metadata.json`` for PR-19 verdict).
* :func:`get_preference_trainer_class` — lazy dispatch to TRL trainer.
* :func:`train_with_preference_opt` — end-to-end retrain entry (Phase 4).
* :class:`BurrowsTrackingCallback` — epoch-wise Burrows tracking (DPN18-0 C).

All TRL / peft / transformers imports are lazy (inside function bodies) so
module load stays free of ``[training-preference]`` / ``[training]`` extras
([[feedback_pre_push_ci_parity]] 3 点 set: lazy import + mypy ignore + test
importorskip). Mypy ``ignore_missing_imports`` for ``trl.*`` is configured
in ``pyproject.toml`` ``[tool.mypy.overrides]``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence

# burrows_aware_loss は同 package + extras-free (torch は同 module 内で lazy) の
# ため top-level import 可 (= 循環なし)。 numpy / evidence (bootstrap_ci / vendi)
# のみ snapshot 内 lazy (training→evidence の lazy 慣習 + numpy base dep)。
from erre_sandbox.training.burrows_aware_loss import (
    DEFAULT_EPS,
    ReferenceUnigramTable,
    load_reference_unigram_table,
)

_LOGGER: Final = logging.getLogger(__name__)

_CANONICAL_REFERENCE_UNIGRAM_PATH: Final = Path(
    "data/burrows_aware_loss/reference_unigram_kant_de.json"
)
"""DPN16-1.5 caveat: ``burrows_reference_corpus=None`` 時の fallback path
(``train_with_preference_opt`` が validation set 接続時のみ参照)。"""

_VALIDATION_VENDI_KERNEL_NAME: Final = "lexical-5gram-jaccard"
"""PR-22 DPN22-2 #1: pure Jaccard char-5gram kernel 識別子。 eval verdict の
sklearn TF-IDF cosine (``lexical-5gram``) とは metric family が異なるため
別名で区別する (caveat 併記)。"""

_MIN_TOKENS_FOR_CI: Final = 5
"""PR-22 code review MEDIUM-2: per-completion bootstrap CI への寄与最小 token 数。

これ未満の completion は縮退 one-hot marginal となり reverse-KL reduction% が
極端な outlier になるため CI 寄与から除外 (pooled marginal には全 token 寄与)。"""

_SUPPORTED_VALIDATION_FORMAT_VERSIONS: Final = frozenset({"1"})
"""Validation set loader が認識する ``format_version`` 集合。

「再生成は ``format_version`` で吸収」を実コードで担保する。
未知 version は schema 変更の可能性として warning (loader 更新を促す)、 records 形が
互換なら best-effort load を続行する (= 過度な hard-fail を避けつつ silent mis-load
を防ぐ)。"""


# ---------------------------------------------------------------------------
# Enums and constants
# ---------------------------------------------------------------------------


class PreferenceAlgorithm(StrEnum):
    """PR-17 ADR §軸 2 candidates (B1/B2/B3, Phase 1.5 spike で確定)."""

    DPO = "dpo"
    """B1 = standard DPO (Rafailov et al. 2024)、 β KL constraint。"""

    KTO = "kto"
    """B2 = Kahneman-Tversky Optimization、 1 sample binary label (good/bad)。"""

    IPO = "ipo"
    """B3 = Identity-PO (over-fitting 抑制、 regularization 強化)。"""


QcThresholdLevel = Literal["none", "loose", "strict"]
"""DPN18-0 A binding: QC threshold 3 level smoke (gate なし / 緩い / 厳しい)."""


DEFAULT_BASE_MODEL: Final[str] = "Qwen/Qwen3-8B"
"""PR-14/16 と同じ base model (Plan B kant-de 経路の唯一の選択)。"""

DEFAULT_BURROWS_TRACKING_INTERVAL_STEPS: Final[int] = 50
"""DPN18-0 C: epoch-wise Burrows tracking callback の発火 step 間隔。"""

DEFAULT_MAX_STEPS: Final[int] = 500
"""Phase 4 preference optimization の default max_steps。

PR-14 SFT (2500 steps) より少ない。 preference optimization は warm start
adapter から start するため step 数は SFT より小さく、 ~3-5h GPU envelope に
収めるための target。 Phase 1.5 spike outcome で調整可。
"""

DEFAULT_LEARNING_RATE: Final[float] = 1e-5
"""Phase 4 preference optimization の default LR。

PR-14 SFT (2e-4) より 1 桁低い。 preference optimization は base SFT の
weight を起点に refine するため LR sensitivity が強く、 paper standard
(DPO: 5e-7〜1e-5、 KTO: 5e-7〜5e-6) に整合させた controllable default。
"""


# ---------------------------------------------------------------------------
# Config + result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PreferenceOptimizationConfig:
    """Algorithm-neutral config for composite Burrows preference optimization.

    PR-17 ADR §6 軸 final form 通り、 algorithm (axis B) は instance 生成時に
    確定するが、 ``beta_or_tau`` の default 値は DPN18-0 B で記録の paper
    standard を採用 (B1 DPO β=0.1、 B2 KTO τ=1.0、 B3 IPO regularizer=1.0)。

    The wrapper expects warm start + frozen reference adapter paths to point
    at peft-saved LoRA snapshots (e.g. PR-16 Run 2.3 = ``data/lora/m9-c-adopt-v2/
    kant_de_lora_burrows_aware_lambda0.3_seed44_v1/`` for the trainable
    policy and PR-14 control = ``kant_de_lora_seed44_v1/`` for the frozen
    reference, the C3 推奨 配置).
    """

    algorithm: PreferenceAlgorithm
    """B1/B2/B3 selection (Phase 1.5 preflight spike outcome で確定)."""

    beta_or_tau: float
    """DPO β / KTO τ / IPO regularizer (DPN18-0 B paper standard)."""

    warm_start_adapter_path: Path
    """Trainable policy 初期化 adapter (C3 推奨 = PR-16 λ=0.3 best-Burrows)."""

    reference_adapter_path: Path
    """Frozen reference policy adapter (C3 = PR-14 control snapshot)."""

    preference_pair_source: Path
    """A2 経路 = preference_pair_builder.py が出力する JSON path."""

    gated_burrows_qc_threshold: QcThresholdLevel
    """E3 gated Burrows QC threshold level (DPN18-0 A 参照)."""

    output_dir: Path
    """Adapter snapshot 保存 dir (``kant_de_pref_<algo>_e3_warmlam0.3_seed44_v1``)."""

    seed: int = 44
    """Plan B kant-de 経路の lineage seed (PR-14/16 と同)."""

    max_steps: int = DEFAULT_MAX_STEPS
    learning_rate: float = DEFAULT_LEARNING_RATE
    base_model: str = DEFAULT_BASE_MODEL

    burrows_tracking_interval_steps: int = DEFAULT_BURROWS_TRACKING_INTERVAL_STEPS
    """DPN18-0 C: 何 step ごとに validation Burrows reduction% を計測するか。"""

    burrows_validation_set_path: Path | None = None
    """PR-16 既存 20 shard subset の rescore artefact JSON (Burrows tracking 入力)。

    None 時は callback は no-op で skip (Phase 1.5 spike で軽量検証に使う)。
    """

    burrows_reference_corpus: Path | None = None
    """DPN16-1.5 caveat 継承: ``data/burrows_aware_loss/reference_unigram_kant_de.json``

    None 時は callback が canonical path に fallback する。 roundtrip=0.6122
    < 0.80 の caveat は PR-19 verdict で併記 mandatory。
    """

    def __post_init__(self) -> None:
        if self.beta_or_tau <= 0.0:
            msg = (
                "PreferenceOptimizationConfig: beta_or_tau must be > 0,"
                f" got {self.beta_or_tau!r}"
            )
            raise ValueError(msg)
        if self.max_steps <= 0:
            msg = (
                "PreferenceOptimizationConfig: max_steps must be > 0,"
                f" got {self.max_steps!r}"
            )
            raise ValueError(msg)
        if self.learning_rate <= 0.0:
            msg = (
                "PreferenceOptimizationConfig: learning_rate must be > 0,"
                f" got {self.learning_rate!r}"
            )
            raise ValueError(msg)
        if self.burrows_tracking_interval_steps <= 0:
            msg = (
                "PreferenceOptimizationConfig: burrows_tracking_interval_steps"
                f" must be > 0, got {self.burrows_tracking_interval_steps!r}"
            )
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class PreferenceTrainingResult:
    """Forensic outcome embedded in ``train_metadata.json`` (PR-19 verdict 入力).

    PR-17 ADR §後段 PR-18+ binding で pre-register の 5 新 field を含む:

    * ``preference_optimization_algorithm`` — algorithm.value (one of "dpo"/"kto"/"ipo")
    * ``reward_definition`` — "gated_burrows_e3" (E3 binding)
    * ``policy_warm_start_adapter`` — warm_start_adapter_path
    * ``reference_policy_adapter`` — reference_adapter_path
    * ``preference_pair_source`` — preference_pair_source
    """

    algorithm: str
    reward_definition: str
    policy_warm_start_adapter: str
    reference_policy_adapter: str
    preference_pair_source: str

    gated_burrows_qc_threshold: str
    beta_or_tau: float
    seed: int
    max_steps: int
    final_loss: float

    adapter_snapshot_path: str
    """保存先 dir (``kant_de_pref_<algo>_e3_warmlam0.3_seed44_v1``)."""

    burrows_tracking: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    """DPN18-0 C: epoch-wise Burrows tracking 時系列。

    各 entry = {``step``: int, ``validation_burrows_reduction_pct``: float,
    ``validation_burrows_ci_lower``: float, ``validation_vendi_score``: float}。
    PR-19 verdict で C3 warm start erosion 仮説検証材料。
    """

    train_loss_curve: tuple[float, ...] = field(default_factory=tuple)
    """TRL ``Trainer.state.log_history`` 由来の per-log-step loss series."""

    kto_label_weights: KtoLabelWeightDecision | None = None
    """DPN-rebind-1: KTO label imbalance 補正の算出結果 (caveat ⑤ fix)。

    KTO algorithm のときのみ非 None。 ``adapter`` 単体 (``train_metadata.json``)
    から「どの weight で訓練したか / 縮退で skip したか」を辿れるよう
    :meth:`as_metadata_dict` で 6 flat field + ``adjusted_side`` として emit する。
    DPO/IPO では None。
    """

    def as_metadata_dict(self) -> dict[str, Any]:
        """Serialise to ``train_metadata.json`` 用 dict.

        Returns:
            5 新 field + hyperparam + forensic time series + KTO weight
            provenance (DPN-rebind-1) を含む dict。
        """
        kto = self.kto_label_weights
        return {
            "preference_optimization_algorithm": self.algorithm,
            "reward_definition": self.reward_definition,
            "policy_warm_start_adapter": self.policy_warm_start_adapter,
            "reference_policy_adapter": self.reference_policy_adapter,
            "preference_pair_source": self.preference_pair_source,
            "gated_burrows_qc_threshold": self.gated_burrows_qc_threshold,
            "beta_or_tau": self.beta_or_tau,
            "seed": self.seed,
            "max_steps": self.max_steps,
            "final_loss": self.final_loss,
            "adapter_snapshot_path": self.adapter_snapshot_path,
            "burrows_tracking": list(self.burrows_tracking),
            "train_loss_curve": list(self.train_loss_curve),
            # DPN-rebind-1: KTO weight provenance (非 KTO は None)。
            "kto_desirable_weight": kto.desirable_weight if kto else None,
            "kto_undesirable_weight": kto.undesirable_weight if kto else None,
            "kto_label_positive_count": kto.label_positive_count if kto else None,
            "kto_label_negative_count": kto.label_negative_count if kto else None,
            "kto_weighted_label_ratio": kto.weighted_label_ratio if kto else None,
            "kto_weight_strategy": kto.strategy if kto else None,
            "kto_weight_adjusted_side": kto.adjusted_side if kto else None,
        }


# ---------------------------------------------------------------------------
# KTO label imbalance weight (caveat ⑤ fix)
# ---------------------------------------------------------------------------


_KTO_BAND_UPPER_COEFF: Final = 1.33
"""TRL KTO label-balance band の上側係数 (= 4/3)。

``trl.experimental.kto.kto_trainer`` (trl 0.29.1) の正準値、 bounds の出典は
KTO 論文 Eq.(8) https://huggingface.co/papers/2402.01306。 出典は
verbatim 保存した参照ソースに基づく (推測実装禁止)。"""


@dataclass(frozen=True, slots=True)
class KtoLabelWeightDecision:
    """KTO label imbalance 補正の算出結果 (caveat ⑤ fix、 DPN-rebind-1).

    pure 関数 :func:`compute_kto_label_weights` の戻り値。 TRL
    ``desirable_weight`` / ``undesirable_weight`` を KTO 論文 Eq.(8) の band に
    従い算出し、 forensic provenance (``train_metadata.json``) と unit test の
    band cross-check に使う。
    """

    label_positive_count: int
    """n_desirable = ``label is True`` の record 数。"""

    label_negative_count: int
    """n_undesirable = ``label is False`` の record 数。"""

    desirable_weight: float
    """KTOConfig に渡す ``desirable_weight`` (動かさない側は 1.0)。"""

    undesirable_weight: float
    """KTOConfig に渡す ``undesirable_weight`` (動かさない側は 1.0)。"""

    weighted_label_ratio: float
    """``(desirable_weight·n_pos) / (undesirable_weight·n_neg)``。

    target = 1.0 (完全均衡)。 縮退 (片側ゼロ) では未定義 = ``nan``。
    """

    strategy: str
    """``"balanced"`` | ``"rebalanced"`` | ``"degenerate_single_class"``。"""

    adjusted_side: Literal["desirable", "undesirable", "none"]
    """1.0 から動かした側 (補正なし / 縮退は ``"none"``)。"""

    und_weight_lower_bound: float
    """TRL Eq.(8) ``undesirable_weight`` 推奨 band 下端 (balanced/縮退は ``nan``)。"""

    und_weight_upper_bound: float
    """同上端。"""

    des_weight_lower_bound: float
    """TRL Eq.(8) ``desirable_weight`` 推奨 band 下端 (balanced/縮退は ``nan``)。"""

    des_weight_upper_bound: float
    """同上端。"""


def compute_kto_label_weights(labels: Sequence[bool]) -> KtoLabelWeightDecision:
    """KTO label 分布から TRL 正準 band 内の weight を算出する (pure、 trl 非依存).

    DPN-rebind-1: weighted loss mass を完全均衡 (``weighted_label_ratio`` = 1.0)
    にする閉形式解。 少数派 class の weight のみを上げ (TRL の EITHER/OR, NOT
    BOTH に整合)、 多数派は 1.0 維持。 算出 weight は ``round(_, 2)`` で TRL band
    check (同じ丸め) と桁を揃える。

    scope (over-claim 禁止): 本関数は **caveat ⑤ = weight 未設定の解消のみ**。
    縮退 (片側ゼロ) の解消は corpus/QC 軸 (別タスク) であり、 ここでは補正を skip して
    1.0/1.0 を返すに留める (caller が WARNING)。

    Args:
        labels: KTO binary record の ``label`` (``True``=desirable /
            ``False``=undesirable)。

    Returns:
        :class:`KtoLabelWeightDecision`。

    Raises:
        ValueError: ``labels`` が空 (= KTO train 不成立、 model load 前 fail-fast)。
    """
    n_total = len(labels)
    if n_total == 0:
        msg = (
            "compute_kto_label_weights: empty label set (0 records); KTO training"
            " cannot proceed (fail-fast before model load)"
        )
        raise ValueError(msg)

    n_pos = sum(1 for label in labels if label)
    n_neg = n_total - n_pos
    nan = float("nan")

    # 縮退 (片側ゼロ): weight 補正は両クラス存在が前提。 1.0/1.0 維持 (caller warn)。
    if n_pos == 0 or n_neg == 0:
        return KtoLabelWeightDecision(
            label_positive_count=n_pos,
            label_negative_count=n_neg,
            desirable_weight=1.0,
            undesirable_weight=1.0,
            weighted_label_ratio=nan,
            strategy="degenerate_single_class",
            adjusted_side="none",
            und_weight_lower_bound=nan,
            und_weight_upper_bound=nan,
            des_weight_lower_bound=nan,
            des_weight_upper_bound=nan,
        )

    # balanced: TRL band 非発火 (num_desirable == num_undesirable)。
    if n_pos == n_neg:
        return KtoLabelWeightDecision(
            label_positive_count=n_pos,
            label_negative_count=n_neg,
            desirable_weight=1.0,
            undesirable_weight=1.0,
            weighted_label_ratio=1.0,
            strategy="balanced",
            adjusted_side="none",
            und_weight_lower_bound=nan,
            und_weight_upper_bound=nan,
            des_weight_lower_bound=nan,
            des_weight_upper_bound=nan,
        )

    # imbalanced: 少数派を up-weight して weighted_ratio=1.0 (TRL band の `/1` 端)。
    adjusted_side: Literal["desirable", "undesirable", "none"]
    if n_pos > n_neg:
        # desirable majority → undesirable を上げる
        undesirable_weight = round(n_pos / n_neg, 2)
        desirable_weight = 1.0
        adjusted_side = "undesirable"
    else:
        # undesirable majority → desirable を上げる
        desirable_weight = round(n_neg / n_pos, 2)
        undesirable_weight = 1.0
        adjusted_side = "desirable"

    weighted_label_ratio = (desirable_weight * n_pos) / (undesirable_weight * n_neg)

    # TRL Eq.(8) band を最終 weight で再現 (forensic + in-range cross-check)。
    und_center = n_pos * desirable_weight / n_neg
    des_center = n_neg * undesirable_weight / n_pos
    und_weight_lower_bound = round(und_center / _KTO_BAND_UPPER_COEFF, 2)
    und_weight_upper_bound = round(und_center / 1, 2)
    des_weight_lower_bound = round(des_center * 1, 2)
    des_weight_upper_bound = round(des_center * _KTO_BAND_UPPER_COEFF, 2)

    return KtoLabelWeightDecision(
        label_positive_count=n_pos,
        label_negative_count=n_neg,
        desirable_weight=desirable_weight,
        undesirable_weight=undesirable_weight,
        weighted_label_ratio=weighted_label_ratio,
        strategy="rebalanced",
        adjusted_side=adjusted_side,
        und_weight_lower_bound=und_weight_lower_bound,
        und_weight_upper_bound=und_weight_upper_bound,
        des_weight_lower_bound=des_weight_lower_bound,
        des_weight_upper_bound=des_weight_upper_bound,
    )


# ---------------------------------------------------------------------------
# Algorithm dispatch
# ---------------------------------------------------------------------------


def get_preference_trainer_class(algorithm: PreferenceAlgorithm) -> tuple[Any, Any]:
    """Lazy-load + dispatch to TRL trainer + config class.

    PR-17 軸 5 (D1 = TRL trainer) implementation。 TRL >= 0.11 で IPO は
    DPOTrainer + ``loss_type="ipo"`` 経由で利用可能 (separate IPOTrainer は
    存在しない、 公式 doc: https://huggingface.co/docs/trl/main/en/dpo_trainer)。
    KTOTrainer は独立 class。

    Args:
        algorithm: ``PreferenceAlgorithm`` enum value.

    Returns:
        ``(trainer_class, config_class)`` tuple。

    Raises:
        ImportError: If ``[training-preference]`` extras is not installed.
        ValueError: If algorithm is not recognised.
    """
    if algorithm is PreferenceAlgorithm.DPO:
        from trl import DPOConfig, DPOTrainer  # noqa: PLC0415

        return DPOTrainer, DPOConfig
    if algorithm is PreferenceAlgorithm.KTO:
        from trl import KTOConfig, KTOTrainer  # noqa: PLC0415

        return KTOTrainer, KTOConfig
    if algorithm is PreferenceAlgorithm.IPO:
        # IPO は DPOTrainer + loss_type="ipo" 構成 (TRL 公式 pattern)
        from trl import DPOConfig, DPOTrainer  # noqa: PLC0415

        return DPOTrainer, DPOConfig
    msg = f"unknown preference algorithm: {algorithm!r}"
    raise ValueError(msg)


def _build_trainer_config_kwargs(
    config: PreferenceOptimizationConfig,
    *,
    kto_weights: KtoLabelWeightDecision | None = None,
) -> dict[str, Any]:
    """Map ``PreferenceOptimizationConfig`` to TRL config kwargs.

    Algorithm-specific mapping:

    * DPO: ``beta`` = β, ``loss_type`` = "sigmoid" (standard)
    * KTO: ``beta`` = τ (TRL KTOConfig uses ``beta`` field for τ),
      ``desirable_weight`` / ``undesirable_weight`` = label imbalance 補正
      (DPN-rebind-1、 ``kto_weights`` 注入時のみ)
    * IPO: ``beta`` = regularizer, ``loss_type`` = "ipo" (DPOConfig 経由)

    Args:
        config: :class:`PreferenceOptimizationConfig`.
        kto_weights: KTO label imbalance 補正の算出結果 (DPN-rebind-1)。 KTO
            algorithm のときのみ ``desirable_weight`` / ``undesirable_weight``
            を注入する。 None (= back-compat) なら従来の 1.0/1.0 経路。 DPO/IPO
            には **一切注入しない** (KTOConfig 専用 field のため)。

    Returns:
        TRL ``DPOConfig`` / ``KTOConfig`` への kwargs dict。
    """
    common: dict[str, Any] = {
        "output_dir": str(config.output_dir),
        "max_steps": config.max_steps,
        "learning_rate": config.learning_rate,
        "seed": config.seed,
        "beta": config.beta_or_tau,
        "remove_unused_columns": False,
    }
    if config.algorithm is PreferenceAlgorithm.DPO:
        common["loss_type"] = "sigmoid"
    elif config.algorithm is PreferenceAlgorithm.IPO:
        common["loss_type"] = "ipo"
    elif config.algorithm is PreferenceAlgorithm.KTO and kto_weights is not None:
        # caveat ⑤ fix: KTO label imbalance 補正 (DPN-rebind-1)。 DPO/IPO は
        # KTOConfig 専用 field を持たないため、 ここ (KTO 分岐) でのみ注入する。
        common["desirable_weight"] = kto_weights.desirable_weight
        common["undesirable_weight"] = kto_weights.undesirable_weight
    return common


# ---------------------------------------------------------------------------
# Adapter loading
# ---------------------------------------------------------------------------


def load_trainable_policy(
    base_model: str,
    warm_start_adapter_path: Path,
    *,
    quantization: Literal["nf4", "fp4"] | None = "nf4",
) -> tuple[Any, Any]:
    """Load trainable policy (warm start adapter, C3 推奨).

    PR-14/16 と同 pattern (``_load_qwen3_8b_with_quantization`` 参考)、 ただし
    adapter は既存 LoRA snapshot を peft.PeftModel.from_pretrained で load し
    ``is_trainable=True`` で trainable mode 化する。

    Args:
        base_model: HF Hub model ID (default Qwen3-8B)。
        warm_start_adapter_path: peft-saved LoRA snapshot dir。
        quantization: "nf4"/"fp4" or None (full precision、 デバッグ用)。

    Returns:
        ``(tokenizer, peft_policy_model)`` — trainable mode。
    """
    import torch  # noqa: PLC0415
    from peft import PeftModel  # noqa: PLC0415
    from transformers import (  # noqa: PLC0415
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
    )

    tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call,unused-ignore]
        base_model,
        trust_remote_code=True,
        use_fast=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    load_kwargs: dict[str, object] = {
        "torch_dtype": torch.bfloat16,
        "device_map": "auto",
    }
    if quantization in {"nf4", "fp4"}:
        bnb_config = BitsAndBytesConfig(  # type: ignore[no-untyped-call,unused-ignore]
            load_in_4bit=True,
            bnb_4bit_quant_type=quantization,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        load_kwargs["quantization_config"] = bnb_config

    base = AutoModelForCausalLM.from_pretrained(
        base_model,
        trust_remote_code=True,
        **load_kwargs,
    )
    policy = PeftModel.from_pretrained(
        base,
        str(warm_start_adapter_path),
        is_trainable=True,
    )
    return tokenizer, policy


def load_frozen_reference_policy(
    base_model: str,
    reference_adapter_path: Path,
    *,
    quantization: Literal["nf4", "fp4"] | None = "nf4",
) -> Any:
    """Load frozen reference policy (C3 = PR-14 control snapshot).

    Args:
        base_model: HF Hub model ID。
        reference_adapter_path: peft-saved LoRA snapshot dir。
        quantization: 同上。

    Returns:
        peft.PeftModel — frozen mode (``is_trainable=False``)。
    """
    import torch  # noqa: PLC0415
    from peft import PeftModel  # noqa: PLC0415
    from transformers import (  # noqa: PLC0415
        AutoModelForCausalLM,
        BitsAndBytesConfig,
    )

    load_kwargs: dict[str, object] = {
        "torch_dtype": torch.bfloat16,
        "device_map": "auto",
    }
    if quantization in {"nf4", "fp4"}:
        bnb_config = BitsAndBytesConfig(  # type: ignore[no-untyped-call,unused-ignore]
            load_in_4bit=True,
            bnb_4bit_quant_type=quantization,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        load_kwargs["quantization_config"] = bnb_config

    base = AutoModelForCausalLM.from_pretrained(
        base_model,
        trust_remote_code=True,
        **load_kwargs,
    )
    return PeftModel.from_pretrained(
        base,
        str(reference_adapter_path),
        is_trainable=False,
    )


# ---------------------------------------------------------------------------
# Burrows tracking callback (DPN18-0 C)
# ---------------------------------------------------------------------------


class BurrowsTrackingCallback:
    """Epoch-wise Burrows tracking callback (DPN18-0 C binding、 PR-22 v2 実装).

    TRL trainer の ``on_step_end`` callback で N step ごとに validation set
    の Burrows reduction% + Vendi score を計算、 ``train_metadata.json`` に
    時系列保存する forensic callback。

    **PR-22 DPN22-0 (v2 = ReferenceUnigramTable reverse-KL)**:
    :meth:`_compute_validation_burrows_snapshot` は constructor 注入された
    tokenizer + :class:`~erre_sandbox.training.burrows_aware_loss.ReferenceUnigramTable`
    (= ``--burrows-reference-corpus``) + validation records から、 validation
    completion の function-word token-id marginal を集計し reference との
    **reverse-KL** ``KL(marginal || reference)`` を測る (model forward なし =
    B実)。 reference を distance の入力にするため、 v2 unigram 差し替えで値が変化
    する (caveat ⑦ (c) 充足)。 注入が無い (config-only 構築) 場合は NaN-graceful
    snapshot を返す (back-compat、 DPN22-1 #4)。

    限界 (DPN22-0 caveat ⑥ 主張範囲): model forward しないため tracking は step
    不変の定数列。 caveat ⑥ resolved は **「NaN placeholder 解消」 に限定**し、
    model 進行に伴う Burrows erode の時系列検出 (= C実) は Phase 4 別 script に
    defer 継続する。

    HuggingFace ``transformers.Trainer`` の ``CallbackHandler`` は
    callback object の各 event method (``on_init_end`` / ``on_train_begin``
    / ``on_step_end`` 等) を fixed list で順次 ``getattr(cb, event)(...)`` で
    呼ぶ。 すべての event method が存在しないと ``AttributeError``。 transformers
    extras を import-time に依存させたくないので、 ``transformers.TrainerCallback``
    を継承する代わりに ``__getattr__`` で ``on_*`` event をすべて no-op
    passthrough にする duck-type 互換 pattern を使う (= 我々が必要な
    ``on_step_end`` だけ explicit 実装、 他は control を素通し)。
    """

    def __init__(
        self,
        config: PreferenceOptimizationConfig,
        *,
        tokenizer: Any = None,
        reference_table: ReferenceUnigramTable | None = None,
        validation_records: list[dict[str, str]] | None = None,
    ) -> None:
        """Construct the callback.

        Args:
            config: :class:`PreferenceOptimizationConfig` (interval + path 等)。
            tokenizer: HF tokenizer (``train_with_preference_opt`` が
                ``:662`` で load 済を constructor 注入、 DPN22-1 #2)。 ``None``
                時は snapshot が NaN-graceful (back-compat)。
            reference_table: ``--burrows-reference-corpus`` を load した
                :class:`ReferenceUnigramTable` (reverse-KL の reference)。
            validation_records: ``[{prompt, completion}]`` の list (PR-22
                ``pr22_build_validation_set.py`` 生成、 ``:603`` で load 注入)。
        """
        self._config = config
        self._tracking: list[dict[str, Any]] = []
        self._tokenizer = tokenizer
        self._reference_table = reference_table
        self._validation_records: list[dict[str, str]] = validation_records or []

    @property
    def tracking(self) -> tuple[dict[str, Any], ...]:
        """Time-series snapshot for embedding into ``train_metadata.json``."""
        return tuple(self._tracking)

    def __getattr__(self, name: str) -> Any:
        """Provide no-op passthrough for any unimplemented ``on_*`` event hook.

        HF Trainer's :class:`~transformers.trainer_callback.CallbackHandler`
        iterates a fixed event list (``on_init_end`` / ``on_train_begin`` /
        ``on_epoch_begin`` etc.) and calls each on every callback. We only
        need ``on_step_end``; let everything else return ``control`` unchanged
        so we duck-type-conform without importing transformers at module load.

        Raises:
            AttributeError: For any non-``on_*`` attribute name (preserves
                normal attribute-error semantics).
        """
        if name.startswith("on_"):

            def _passthrough(
                args: Any = None,  # noqa: ARG001
                state: Any = None,  # noqa: ARG001
                control: Any = None,
                **_kwargs: Any,
            ) -> Any:
                return control

            return _passthrough
        msg = f"{type(self).__name__!r} object has no attribute {name!r}"
        raise AttributeError(msg)

    def on_step_end(
        self,
        args: Any,  # noqa: ARG002  # TRL/transformers callback API requires this position
        state: Any,
        control: Any,
        **_kwargs: Any,
    ) -> Any:
        """TRL/transformers Trainer callback hook (PR-18 forensic surface).

        Args:
            args: TrainingArguments (TRL DPOConfig / KTOConfig)。
            state: TrainerState (state.global_step を読む)。
            control: TrainerControl (return for downstream callback chain)。
            _kwargs: Trainer の追加 kwargs (model / tokenizer 等、 本 callback
                では未使用)。

        Returns:
            control (mutate せず passthrough)。
        """
        global_step = int(getattr(state, "global_step", 0))
        if global_step <= 0:
            return control
        if global_step % self._config.burrows_tracking_interval_steps != 0:
            return control
        if self._config.burrows_validation_set_path is None:
            # validation set 未指定時は no-op (Phase 1.5 spike 軽量モード)
            return control

        snapshot = self._compute_validation_burrows_snapshot(global_step)
        self._tracking.append(snapshot)
        _LOGGER.info(
            "BurrowsTrackingCallback step=%d burrows_reduction_pct=%.4f"
            " vendi_score=%.4f",
            global_step,
            snapshot.get("validation_burrows_reduction_pct", float("nan")),
            snapshot.get("validation_vendi_score", float("nan")),
        )
        return control

    def _compute_validation_burrows_snapshot(self, step: int) -> dict[str, Any]:
        """v2 (DPN22-0、 model-forward-free) Burrows reverse-KL snapshot.

        注入された tokenizer + :class:`ReferenceUnigramTable` + validation records
        から、 validation completion の function-word token-id marginal を
        (K+1)-partition (function word ∪ OTHER) で集計し、 reference との
        **reverse-KL** ``KL(marginal || reference)`` を測る (訓練 loss term
        ``compute_burrows_kl_term`` と同 family、 forensic consistency、 DPN22-1 #2)。

        * ``validation_burrows_reduction_pct`` = ``(baseline - measured)/baseline*100``
          (baseline = ``KL(uniform_partition || reference)``、 DPN22-1)。 pooled
          marginal (全 completion token 合算) から算出。
        * ``validation_burrows_ci_lower`` = per-completion reduction% の percentile
          bootstrap lower (``bootstrap_ci`` 再利用、 DPN22-2 #2、 seed=config.seed)。
        * ``validation_vendi_score`` = completion 集合に pure Jaccard char-5gram
          kernel (``make_lexical_5gram_kernel`` 再利用、 numpy のみ、 DPN22-2 #1)。

        reference を distance 入力にするため v2 unigram 差し替えで値が変化する
        (caveat ⑦ (c))。 tokenizer / reference / records 未注入 or 全 completion
        が空 token の場合は NaN-graceful (back-compat、 DPN22-1 #4)。 model forward
        なしのため step 不変 (over-fit 時系列検出は Phase 4 C実 defer)。
        """
        reference = self._reference_table
        records = self._validation_records
        if reference is None or self._tokenizer is None or not records:
            return _nan_snapshot(
                step, "validation tokenizer/reference/records not injected"
            )

        completions = [
            str(rec["completion"])
            for rec in records
            if isinstance(rec, dict) and rec.get("completion")
        ]
        if not completions:
            return _nan_snapshot(step, "no non-empty validation completions")

        import numpy as np  # noqa: PLC0415  # base dep, lazy to keep module load minimal

        from erre_sandbox.evidence.bootstrap_ci import bootstrap_ci  # noqa: PLC0415
        from erre_sandbox.evidence.tier_b.vendi import (  # noqa: PLC0415
            compute_vendi,
            make_lexical_5gram_kernel,
        )

        fw_index = {
            int(tid): i for i, tid in enumerate(reference.function_word_token_ids)
        }
        k = len(reference.function_word_token_ids)
        p_ref = np.array(
            [
                *reference.reference_probabilities,
                reference.other_bucket_probability,
            ],
            dtype=float,
        )

        def _reverse_kl(p_m: Any) -> float:
            pm = np.clip(p_m, DEFAULT_EPS, None)
            pr = np.clip(p_ref, DEFAULT_EPS, None)
            return float(np.sum(pm * (np.log(pm) - np.log(pr))))

        # baseline = KL(uniform (K+1)-partition || reference) (DPN22-1)
        uniform = np.full(k + 1, 1.0 / float(k + 1), dtype=float)
        baseline = _reverse_kl(uniform)
        if not math.isfinite(baseline) or baseline <= 0.0:
            return _nan_snapshot(step, "degenerate uniform baseline KL")

        def _reduction(measured: float) -> float:
            return (baseline - measured) / baseline * 100.0

        # pooled marginal は全 completion token を合算 (= primary reduction%、
        # 安定)。 per_completion marginals は bootstrap CI 用で、 縮退 short
        # completion は除外済 (_aggregate_function_word_marginals、 MEDIUM-2)。
        pooled, per_marginals = _aggregate_function_word_marginals(
            completions, self._tokenizer, fw_index, k
        )
        total = float(pooled.sum())
        if total <= 0.0:
            return _nan_snapshot(step, "all validation completions tokenised empty")

        reduction_pct = _reduction(_reverse_kl(pooled / total))
        if not math.isfinite(reduction_pct):
            # reference が Laplace-smoothed 前提 (eps clamp で発散はしないが、
            # 外部編集 reference の病的入力に対する belt-and-braces)。
            return _nan_snapshot(step, "non-finite reduction (pathological reference)")
        per_completion = [_reduction(_reverse_kl(m)) for m in per_marginals]
        ci_lower = (
            bootstrap_ci(per_completion, seed=self._config.seed).lo
            if per_completion
            else float("nan")
        )
        vendi_score = compute_vendi(
            completions,
            kernel=make_lexical_5gram_kernel(),
            kernel_name=_VALIDATION_VENDI_KERNEL_NAME,
        ).score

        return {
            "step": step,
            "validation_burrows_reduction_pct": float(reduction_pct),
            "validation_burrows_ci_lower": float(ci_lower),
            "validation_vendi_score": float(vendi_score),
            "validation_kernel_name": _VALIDATION_VENDI_KERNEL_NAME,
            "validation_completion_count": len(completions),
            "note": (
                "v2 reverse-KL(marginal || reference) vs uniform baseline,"
                " model-forward-free (DPN22-0); Vendi kernel = pure Jaccard"
                " char-5gram (eval TF-IDF cosine とは family 相違)"
            ),
        }


def _aggregate_function_word_marginals(
    completions: list[str],
    tokenizer: Any,
    fw_index: dict[int, int],
    k: int,
) -> tuple[Any, list[Any]]:
    """Tokenise each completion → function-word ∪ OTHER partition counts.

    Args:
        completions: validation completion 文字列 list。
        tokenizer: HF tokenizer (``encode(text, add_special_tokens=False)``)。
        fw_index: function-word token-id → partition index (0..K-1) の dict。
        k: function-word 数 (OTHER bucket は index ``k``)。

    Returns:
        ``(pooled, per_completion_marginals)``:

        * ``pooled`` — 全 completion token 合算の (K+1,) count 配列 (primary
          reduction% 用、 安定)。
        * ``per_completion_marginals`` — 正規化済 (K+1,) marginal の list。
          ``_MIN_TOKENS_FOR_CI`` 未満の短い completion は縮退 one-hot を避けるため
          除外 (bootstrap CI 入力のみ、 pooled には全 token 寄与、 MEDIUM-2)。
    """
    import numpy as np  # noqa: PLC0415

    pooled = np.zeros(k + 1, dtype=float)
    per_completion_marginals: list[Any] = []
    for text in completions:
        counts = np.zeros(k + 1, dtype=float)
        n_tok = 0
        for tid in tokenizer.encode(text, add_special_tokens=False):
            n_tok += 1
            counts[fw_index.get(int(tid), k)] += 1.0
        if n_tok == 0:
            continue
        pooled += counts
        if n_tok >= _MIN_TOKENS_FOR_CI:
            per_completion_marginals.append(counts / counts.sum())
    return pooled, per_completion_marginals


def _nan_snapshot(step: int, note: str) -> dict[str, Any]:
    """NaN-graceful Burrows tracking snapshot (注入欠落 / degenerate marginal 用).

    DPN22-1 #4 back-compat: validation set が config で有効でも、 tokenizer /
    reference / records が無い・全 completion が空 token の場合は crash せず
    NaN snapshot を返す (gate 判定は finite filter で graceful、 caveat ⑥ の
    resolved 主張は実 score を出せた cell に限る)。
    """
    return {
        "step": step,
        "validation_burrows_reduction_pct": float("nan"),
        "validation_burrows_ci_lower": float("nan"),
        "validation_vendi_score": float("nan"),
        "validation_kernel_name": _VALIDATION_VENDI_KERNEL_NAME,
        "validation_completion_count": 0,
        "note": note,
    }


def _load_validation_records(path: Path) -> list[dict[str, str]]:
    """PR-22 validation set JSON から ``[{prompt, completion}]`` records を load.

    Schema (``pr22_build_validation_set.py`` 生成、 DPN22-1 #1)::

        {"format_version": "1",
         "records": [{"prompt": str, "completion": str}, ...],
         "metadata": {"source": str, "sha256": str, ...}}

    空 ``{}`` / ``records`` 欠落 / completion 欠落 record は graceful skip
    (callback 側で NaN-graceful、 back-compat)。

    ``format_version`` を ``_SUPPORTED_VALIDATION_FORMAT_VERSIONS``
    で明示チェックし、 ``metadata.sha256`` を ``records`` canonical JSON から再計算して
    照合する (= provenance 自己検証)。不一致 / 未知 version は warning にとどめ、
    records 形が互換なら best-effort load を続行する (DPN22-1 #1 の forward-compat、
    silent mis-load 防止)。

    Args:
        path: validation set JSON path。

    Returns:
        ``[{prompt, completion}]`` の list (completion 非空のみ)。

    Raises:
        FileNotFoundError: If ``path`` does not exist (spike runner が必ず
            実 path を渡すため、 欠落は設定誤りとして fail-fast)。
    """
    if not path.is_file():
        msg = (
            f"train_with_preference_opt: burrows_validation_set_path not found: {path}"
        )
        raise FileNotFoundError(msg)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return []

    version = payload.get("format_version")
    if version not in _SUPPORTED_VALIDATION_FORMAT_VERSIONS:
        _LOGGER.warning(
            "validation set format_version=%r not in supported %s (%s);"
            " best-effort load — loader 更新が必要な可能性",
            version,
            sorted(_SUPPORTED_VALIDATION_FORMAT_VERSIONS),
            path,
        )

    raw_records = payload.get("records", [])
    expected_sha = payload.get("metadata", {}).get("sha256")
    if expected_sha is not None and isinstance(raw_records, list):
        canonical = json.dumps(raw_records, sort_keys=True, ensure_ascii=False)
        actual_sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if actual_sha != expected_sha:
            _LOGGER.warning(
                "validation set records sha256 mismatch (metadata=%s actual=%s, %s);"
                " records が編集された可能性 — provenance drift",
                expected_sha,
                actual_sha,
                path,
            )

    return [
        {
            "prompt": str(rec.get("prompt", "")),
            "completion": str(rec["completion"]),
        }
        for rec in raw_records
        if isinstance(rec, dict) and rec.get("completion")
    ]


# ---------------------------------------------------------------------------
# End-to-end retrain entry point
# ---------------------------------------------------------------------------


def _extract_train_loss_curve(trainer: Any) -> tuple[float, ...]:
    """Extract finite per-log-step losses from TRL/transformers Trainer state."""
    state = getattr(trainer, "state", None)
    log_history = getattr(state, "log_history", ())
    if not isinstance(log_history, list | tuple):
        return ()

    losses: list[float] = []
    for entry in log_history:
        if not isinstance(entry, dict):
            continue
        raw_loss = entry.get("loss")
        if raw_loss is None:
            continue
        try:
            loss = float(raw_loss)
        except (TypeError, ValueError):
            continue
        if math.isfinite(loss):
            losses.append(loss)
    return tuple(losses)


def train_with_preference_opt(
    config: PreferenceOptimizationConfig,
) -> PreferenceTrainingResult:
    """Run composite Burrows preference optimization (Phase 4 entry point).

    Steps (DPN-rebind-1/2: preference records + KTO label-weight 判定を model
    load の **前** に実行する順序):

    1. Validate adapter / preference-pair paths
    2. Load preference pair dataset from A2 source (JSON path)
    3. (KTO のみ) :func:`compute_kto_label_weights` で label imbalance を補正。
       空 records は ``ValueError`` で fail-fast、 単一クラスは WARNING + 1.0/1.0。
    4. Load trainable policy (warm start = C3 推奨 = λ=0.3 best-Burrows adapter)
    5. Load frozen reference policy (C3 = PR-14 control snapshot)
    6. Build TRL trainer (algorithm dispatch + algorithm-specific config、
       KTO は weight 注入)
    7. Attach :class:`BurrowsTrackingCallback` (DPN18-0 C)
    8. Run trainer.train()
    9. Save trained adapter snapshot to ``output_dir``
    10. Return :class:`PreferenceTrainingResult` for ``train_metadata.json``

    Args:
        config: :class:`PreferenceOptimizationConfig`.

    Returns:
        :class:`PreferenceTrainingResult` with forensic time series + adapter
        snapshot path.

    Raises:
        ImportError: If ``[training-preference]`` / ``[training]`` extras
            are not installed.
        FileNotFoundError: If preference_pair_source or adapter paths do
            not exist.
        ValueError: KTO で preference records が空 (label 0 件) のとき、 GPU/model
            load の前に fail-fast する (DPN-rebind-2、 ``compute_kto_label_weights``)。
    """
    if not config.warm_start_adapter_path.is_dir():
        msg = (
            "train_with_preference_opt: warm_start_adapter_path not a dir:"
            f" {config.warm_start_adapter_path}"
        )
        raise FileNotFoundError(msg)
    if not config.reference_adapter_path.is_dir():
        msg = (
            "train_with_preference_opt: reference_adapter_path not a dir:"
            f" {config.reference_adapter_path}"
        )
        raise FileNotFoundError(msg)
    if not config.preference_pair_source.is_file():
        msg = (
            "train_with_preference_opt: preference_pair_source not found:"
            f" {config.preference_pair_source}"
        )
        raise FileNotFoundError(msg)

    _LOGGER.info(
        "train_with_preference_opt: algorithm=%s qc=%s warm=%s ref=%s",
        config.algorithm.value,
        config.gated_burrows_qc_threshold,
        config.warm_start_adapter_path,
        config.reference_adapter_path,
    )

    # DPN-rebind-1/2: preference records を GPU/model load の **前** に読み、 KTO の
    # label imbalance を補正 + 縮退を早期処理する (修正 3、 GPU 浪費回避)。
    #   * 空 (0 records) → compute_kto_label_weights が ValueError = load 前 fail-fast
    #   * 片側ゼロ (single-class) → WARNING + 1.0/1.0 維持 (挙動不変、 corpus/QC 委譲)
    preference_records = _load_preference_pair_records(
        config.preference_pair_source,
        algorithm=config.algorithm,
    )
    kto_weights: KtoLabelWeightDecision | None = None
    if config.algorithm is PreferenceAlgorithm.KTO:
        kto_weights = compute_kto_label_weights(
            [bool(rec["label"]) for rec in preference_records]
        )
        if kto_weights.strategy == "degenerate_single_class":
            _LOGGER.warning(
                "KTO label imbalance correction skipped: single-class labels"
                " (positive=%d negative=%d); weight stays 1.0/1.0. caveat ⑤ scope"
                " = weight unset only; single-class degeneration is a corpus/QC"
                " axis (out of weight-fix scope).",
                kto_weights.label_positive_count,
                kto_weights.label_negative_count,
            )
        else:
            _LOGGER.info(
                "KTO label weights: desirable=%.2f undesirable=%.2f"
                " (positive=%d negative=%d weighted_ratio=%.4f strategy=%s"
                " adjusted_side=%s)",
                kto_weights.desirable_weight,
                kto_weights.undesirable_weight,
                kto_weights.label_positive_count,
                kto_weights.label_negative_count,
                kto_weights.weighted_label_ratio,
                kto_weights.strategy,
                kto_weights.adjusted_side,
            )

    tokenizer, policy = load_trainable_policy(
        config.base_model,
        config.warm_start_adapter_path,
    )
    ref_policy = load_frozen_reference_policy(
        config.base_model,
        config.reference_adapter_path,
    )

    # Lazy import — GPU/extras stack only after the fail-fast guards above.
    from datasets import Dataset  # noqa: PLC0415

    train_dataset = Dataset.from_list(preference_records)

    trainer_cls, config_cls = get_preference_trainer_class(config.algorithm)
    trainer_config_kwargs = _build_trainer_config_kwargs(
        config, kto_weights=kto_weights
    )
    trainer_args = config_cls(**trainer_config_kwargs)

    # PR-22 DPN22-0/1: validation set 接続時のみ reference unigram + records を
    # load し callback に constructor 注入 (= Burrows reverse-KL tracking 有効化)。
    reference_table: ReferenceUnigramTable | None = None
    validation_records: list[dict[str, str]] | None = None
    if config.burrows_validation_set_path is not None:
        reference_corpus_path = (
            config.burrows_reference_corpus or _CANONICAL_REFERENCE_UNIGRAM_PATH
        )
        reference_table = load_reference_unigram_table(reference_corpus_path)
        validation_records = _load_validation_records(
            config.burrows_validation_set_path
        )
        _LOGGER.info(
            "burrows tracking enabled: reference=%s (hash=%s) validation_records=%d",
            reference_corpus_path,
            reference_table.distribution_hash[:12],
            len(validation_records),
        )

    callback = BurrowsTrackingCallback(
        config,
        tokenizer=tokenizer,
        reference_table=reference_table,
        validation_records=validation_records,
    )
    # TRL 0.12+ renamed ``tokenizer`` → ``processing_class`` (Trainer base).
    # Older 0.11 path is not supported; pyproject pins trl>=0.11,<1 but the
    # resolved versions in CI/dev are 0.18+ which accept processing_class.
    trainer = trainer_cls(
        model=policy,
        ref_model=ref_policy,
        args=trainer_args,
        train_dataset=train_dataset,
        processing_class=tokenizer,
        callbacks=[callback],
    )

    train_output = trainer.train()
    final_loss = float(getattr(train_output, "training_loss", float("nan")))
    train_loss_curve = _extract_train_loss_curve(trainer)

    config.output_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(config.output_dir))

    result = PreferenceTrainingResult(
        algorithm=config.algorithm.value,
        reward_definition="gated_burrows_e3",
        policy_warm_start_adapter=str(config.warm_start_adapter_path),
        reference_policy_adapter=str(config.reference_adapter_path),
        preference_pair_source=str(config.preference_pair_source),
        gated_burrows_qc_threshold=config.gated_burrows_qc_threshold,
        beta_or_tau=config.beta_or_tau,
        seed=config.seed,
        max_steps=config.max_steps,
        final_loss=final_loss,
        adapter_snapshot_path=str(config.output_dir),
        burrows_tracking=callback.tracking,
        train_loss_curve=train_loss_curve,
        kto_label_weights=kto_weights,
    )

    metadata_path = config.output_dir / "train_metadata.json"
    metadata_path.write_text(
        json.dumps(result.as_metadata_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _LOGGER.info(
        "train_with_preference_opt: complete final_loss=%.4f snapshot=%s",
        final_loss,
        config.output_dir,
    )
    return result


def _load_preference_pair_records(
    preference_pair_source: Path,
    *,
    algorithm: PreferenceAlgorithm,
) -> list[dict[str, Any]]:
    """Read preference_pair_builder.py の出力 JSON を algorithm 別 dataset shape に変換.

    A2 経路 = ``preference_pair_builder.py`` の出力 JSON schema:

    .. code-block:: json

        {
          "format_version": "1",
          "pair_records": [
            {"prompt": str, "chosen": str, "rejected": str, "burrows_delta": float},
            ...
          ],
          "binary_records": [
            {"prompt": str, "completion": str, "label": bool, "burrows_pct": float},
            ...
          ]
        }

    Algorithm 別 shape:

    * DPO / IPO → ``pair_records`` を ``{"prompt", "chosen", "rejected"}`` の
      list[dict] として返す
    * KTO → ``binary_records`` を ``{"prompt", "completion", "label"}`` の
      list[dict] として返す

    Args:
        preference_pair_source: builder の出力 JSON path。
        algorithm: 軸 2 selection。

    Returns:
        TRL trainer に渡せる list[dict]。
    """
    payload = json.loads(preference_pair_source.read_text(encoding="utf-8"))
    if algorithm in {PreferenceAlgorithm.DPO, PreferenceAlgorithm.IPO}:
        pair_records = payload.get("pair_records", [])
        return [
            {
                "prompt": rec["prompt"],
                "chosen": rec["chosen"],
                "rejected": rec["rejected"],
            }
            for rec in pair_records
        ]
    if algorithm is PreferenceAlgorithm.KTO:
        binary_records = payload.get("binary_records", [])
        return [
            {
                "prompt": rec["prompt"],
                "completion": rec["completion"],
                "label": bool(rec["label"]),
            }
            for rec in binary_records
        ]
    msg = f"unknown preference algorithm: {algorithm!r}"
    raise ValueError(msg)


__all__ = [
    "DEFAULT_BASE_MODEL",
    "DEFAULT_BURROWS_TRACKING_INTERVAL_STEPS",
    "DEFAULT_LEARNING_RATE",
    "DEFAULT_MAX_STEPS",
    "BurrowsTrackingCallback",
    "KtoLabelWeightDecision",
    "PreferenceAlgorithm",
    "PreferenceOptimizationConfig",
    "PreferenceTrainingResult",
    "QcThresholdLevel",
    "compute_kto_label_weights",
    "get_preference_trainer_class",
    "load_frozen_reference_policy",
    "load_trainable_policy",
    "train_with_preference_opt",
]
