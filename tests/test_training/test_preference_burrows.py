"""Unit tests for ``erre_sandbox.training.preference_burrows`` (PR-18 Phase 1).

Covers:

* :class:`PreferenceAlgorithm` enum + :class:`PreferenceOptimizationConfig`
  validation (post_init invariants).
* :class:`PreferenceTrainingResult` ``as_metadata_dict`` serialisation
  (= ``train_metadata.json`` 5 新 field PR-17 ADR §後段 PR-18+ binding).
* :func:`get_preference_trainer_class` lazy dispatch + ImportError pass-through
  (trl extras-only dep の 3 点 set ``importorskip`` 確認).
* :class:`BurrowsTrackingCallback` skeleton behaviour (interval step + no-op
  時の placeholder, DPN18-0 C binding).
* :func:`_load_preference_pair_records` JSON schema 変換 (algorithm 別 shape).

trl / peft / transformers imports は lazy なので CI default profile (no
``[training-preference]`` extras) でも本 test file は import 可能。 trl が
実際に必要な test は ``pytest.importorskip("trl")`` で skip。
"""

from __future__ import annotations

import json
import math
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import pytest

from erre_sandbox.training.burrows_aware_loss import ReferenceUnigramTable
from erre_sandbox.training.preference_burrows import (
    DEFAULT_BURROWS_TRACKING_INTERVAL_STEPS,
    DEFAULT_LEARNING_RATE,
    DEFAULT_MAX_STEPS,
    BurrowsTrackingCallback,
    KtoLabelWeightDecision,
    PreferenceAlgorithm,
    PreferenceOptimizationConfig,
    PreferenceTrainingResult,
    _build_trainer_config_kwargs,
    _extract_train_loss_curve,
    _load_preference_pair_records,
    _load_validation_records,
    compute_kto_label_weights,
    get_preference_trainer_class,
    train_with_preference_opt,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    tmp_path: Path,
    *,
    algorithm: PreferenceAlgorithm = PreferenceAlgorithm.DPO,
    beta_or_tau: float = 0.1,
) -> PreferenceOptimizationConfig:
    warm = tmp_path / "warm"
    ref = tmp_path / "ref"
    pairs = tmp_path / "pairs.json"
    out = tmp_path / "out"
    warm.mkdir()
    ref.mkdir()
    pairs.write_text("{}", encoding="utf-8")
    return PreferenceOptimizationConfig(
        algorithm=algorithm,
        beta_or_tau=beta_or_tau,
        warm_start_adapter_path=warm,
        reference_adapter_path=ref,
        preference_pair_source=pairs,
        gated_burrows_qc_threshold="loose",
        output_dir=out,
    )


# ---------------------------------------------------------------------------
# Enum + config
# ---------------------------------------------------------------------------


def test_preference_algorithm_values_are_lowercase_strings() -> None:
    assert PreferenceAlgorithm.DPO.value == "dpo"
    assert PreferenceAlgorithm.KTO.value == "kto"
    assert PreferenceAlgorithm.IPO.value == "ipo"


def test_config_defaults_match_dpn18_0(tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    assert config.seed == 44
    assert config.max_steps == DEFAULT_MAX_STEPS
    assert config.learning_rate == DEFAULT_LEARNING_RATE
    assert (
        config.burrows_tracking_interval_steps
        == DEFAULT_BURROWS_TRACKING_INTERVAL_STEPS
    )


@pytest.mark.parametrize(
    ("beta", "max_steps", "lr", "interval"),
    [
        (0.0, 100, 1e-5, 50),
        (-0.1, 100, 1e-5, 50),
        (0.1, 0, 1e-5, 50),
        (0.1, 100, 0.0, 50),
        (0.1, 100, 1e-5, 0),
    ],
)
def test_config_post_init_rejects_non_positive_values(
    tmp_path: Path,
    beta: float,
    max_steps: int,
    lr: float,
    interval: int,
) -> None:
    warm = tmp_path / "warm"
    ref = tmp_path / "ref"
    pairs = tmp_path / "pairs.json"
    out = tmp_path / "out"
    warm.mkdir()
    ref.mkdir()
    pairs.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match=r"PreferenceOptimizationConfig:"):
        PreferenceOptimizationConfig(
            algorithm=PreferenceAlgorithm.DPO,
            beta_or_tau=beta,
            warm_start_adapter_path=warm,
            reference_adapter_path=ref,
            preference_pair_source=pairs,
            gated_burrows_qc_threshold="loose",
            output_dir=out,
            max_steps=max_steps,
            learning_rate=lr,
            burrows_tracking_interval_steps=interval,
        )


# ---------------------------------------------------------------------------
# Result serialisation (PR-17 ADR 5 新 field)
# ---------------------------------------------------------------------------


def test_result_as_metadata_dict_carries_pr17_adr_5_fields() -> None:
    result = PreferenceTrainingResult(
        algorithm="dpo",
        reward_definition="gated_burrows_e3",
        policy_warm_start_adapter="warm/path",
        reference_policy_adapter="ref/path",
        preference_pair_source="pairs.json",
        gated_burrows_qc_threshold="loose",
        beta_or_tau=0.1,
        seed=44,
        max_steps=500,
        final_loss=0.42,
        adapter_snapshot_path="out/snap",
        train_loss_curve=(0.9, 0.7),
    )
    payload = result.as_metadata_dict()
    # 5 新 field 全て embed されている (PR-17 ADR §後段 PR-18+ binding)
    assert payload["preference_optimization_algorithm"] == "dpo"
    assert payload["reward_definition"] == "gated_burrows_e3"
    assert payload["policy_warm_start_adapter"] == "warm/path"
    assert payload["reference_policy_adapter"] == "ref/path"
    assert payload["preference_pair_source"] == "pairs.json"
    # forensic hyperparam も embed
    assert payload["beta_or_tau"] == pytest.approx(0.1)
    assert payload["seed"] == 44
    assert payload["max_steps"] == 500
    assert payload["final_loss"] == pytest.approx(0.42)
    assert payload["train_loss_curve"] == [0.9, 0.7]
    # burrows_tracking は default empty list
    assert payload["burrows_tracking"] == []


class _StubTrainerState:
    def __init__(self, log_history: list[dict[str, object]]) -> None:
        self.log_history = log_history


class _StubTrainer:
    def __init__(self, log_history: list[dict[str, object]]) -> None:
        self.state = _StubTrainerState(log_history)


def test_extract_train_loss_curve_reads_finite_log_history_losses() -> None:
    trainer = _StubTrainer(
        [
            {"loss": "0.9", "step": 1},
            {"eval_loss": 0.4, "step": 1},
            {"loss": float("nan"), "step": 2},
            {"loss": "not-a-number", "step": 3},
            {"loss": 0.7, "step": 4},
        ],
    )

    assert _extract_train_loss_curve(trainer) == (0.9, 0.7)


# ---------------------------------------------------------------------------
# Lazy dispatch
# ---------------------------------------------------------------------------


def test_get_preference_trainer_class_requires_trl_extras() -> None:
    trl = pytest.importorskip("trl")
    trainer_cls, config_cls = get_preference_trainer_class(PreferenceAlgorithm.DPO)
    assert trainer_cls is trl.DPOTrainer
    assert config_cls is trl.DPOConfig


def test_get_preference_trainer_class_ipo_uses_dpo_trainer_with_loss_type() -> None:
    trl = pytest.importorskip("trl")
    trainer_cls, config_cls = get_preference_trainer_class(PreferenceAlgorithm.IPO)
    # IPO は DPOTrainer + loss_type="ipo" で利用する公式 pattern
    assert trainer_cls is trl.DPOTrainer
    assert config_cls is trl.DPOConfig


def test_get_preference_trainer_class_kto_uses_kto_trainer() -> None:
    trl = pytest.importorskip("trl")
    trainer_cls, config_cls = get_preference_trainer_class(PreferenceAlgorithm.KTO)
    assert trainer_cls is trl.KTOTrainer
    assert config_cls is trl.KTOConfig


def test_trl_trainer_signature_accepts_processing_class_not_tokenizer() -> None:
    """Regression: TRL 0.12+ renamed ``tokenizer`` → ``processing_class``.

    Phase 1.5 sweep failed 9/9 cells because the wrapper passed
    ``tokenizer=...`` to ``DPOTrainer/KTOTrainer.__init__()`` which raises
    ``TypeError`` on TRL 0.12+. This test pins the API contract: the
    keyword we depend on must be present, and the old keyword must not.
    """
    import inspect

    pytest.importorskip("trl")
    from trl import DPOTrainer, KTOTrainer

    for cls in (DPOTrainer, KTOTrainer):
        params = inspect.signature(cls.__init__).parameters
        # KTOTrainer in TRL 0.29.1 is a thin warn wrapper over
        # ``trl.experimental.kto.KTOTrainer`` with ``*args, **kwargs`` — fall
        # back to the experimental class for the real signature in that case.
        if "processing_class" not in params and set(params) == {
            "self",
            "args",
            "kwargs",
        }:
            from trl.experimental.kto import (
                KTOTrainer as _ExperimentalKTO,
            )

            params = inspect.signature(_ExperimentalKTO.__init__).parameters
        assert "processing_class" in params, (
            f"{cls.__name__} must accept processing_class kwarg (TRL 0.12+)"
        )
        # tokenizer kwarg is allowed via deprecated alias in some versions,
        # but our wrapper must NOT depend on it. We only assert the positive
        # presence of processing_class; older tokenizer-only signatures would
        # be caught by the signature check above.


# ---------------------------------------------------------------------------
# Pair records JSON loader
# ---------------------------------------------------------------------------


def test_load_preference_pair_records_dpo_returns_pair_dicts(tmp_path: Path) -> None:
    pairs_path = tmp_path / "pairs.json"
    pairs_path.write_text(
        json.dumps(
            {
                "format_version": "1",
                "pair_records": [
                    {
                        "prompt": "p1",
                        "chosen": "c1",
                        "rejected": "r1",
                        "burrows_delta": 0.5,
                    },
                    {
                        "prompt": "p2",
                        "chosen": "c2",
                        "rejected": "r2",
                        "burrows_delta": 0.7,
                    },
                ],
                "binary_records": [],
            },
        ),
        encoding="utf-8",
    )
    out = _load_preference_pair_records(pairs_path, algorithm=PreferenceAlgorithm.DPO)
    assert len(out) == 2
    assert out[0] == {"prompt": "p1", "chosen": "c1", "rejected": "r1"}
    # burrows_delta は forensic field なので runtime dataset には載らない
    assert "burrows_delta" not in out[0]


def test_load_preference_pair_records_kto_returns_binary_dicts(tmp_path: Path) -> None:
    pairs_path = tmp_path / "pairs.json"
    pairs_path.write_text(
        json.dumps(
            {
                "format_version": "1",
                "pair_records": [],
                "binary_records": [
                    {
                        "prompt": "p1",
                        "completion": "c1",
                        "label": True,
                        "burrows_pct": 0.6,
                    },
                    {
                        "prompt": "p2",
                        "completion": "c2",
                        "label": False,
                        "burrows_pct": 0.4,
                    },
                ],
            },
        ),
        encoding="utf-8",
    )
    out = _load_preference_pair_records(pairs_path, algorithm=PreferenceAlgorithm.KTO)
    assert len(out) == 2
    assert out[0] == {"prompt": "p1", "completion": "c1", "label": True}
    assert out[1]["label"] is False


# ---------------------------------------------------------------------------
# Burrows tracking callback (DPN18-0 C)
# ---------------------------------------------------------------------------


class _StubState:
    def __init__(self, global_step: int) -> None:
        self.global_step = global_step


def test_burrows_tracking_callback_no_op_without_validation_set(
    tmp_path: Path,
) -> None:
    config = _make_config(tmp_path)
    cb = BurrowsTrackingCallback(config)
    # validation_set_path = None なので step が interval に hit しても何も録らない
    cb.on_step_end(
        args=None,
        state=_StubState(global_step=config.burrows_tracking_interval_steps),
        control="control_sentinel",
    )
    assert cb.tracking == ()


def test_burrows_tracking_callback_skips_non_interval_steps(tmp_path: Path) -> None:
    config = _make_config(tmp_path)
    object.__setattr__(config, "burrows_tracking_interval_steps", 10)
    # validation_set_path を非 None に bypass で書き換える: 不可 (frozen)
    # → callback の interval branch のみ test
    cb = BurrowsTrackingCallback(config)
    cb.on_step_end(args=None, state=_StubState(global_step=5), control=None)
    cb.on_step_end(args=None, state=_StubState(global_step=0), control=None)
    assert cb.tracking == ()


def test_burrows_tracking_callback_records_nan_graceful_without_injection(
    tmp_path: Path,
) -> None:
    """validation_set_path が非 None でも tokenizer / reference / records が
    constructor 注入されていない (= 空 ``{}`` JSON 相当) 場合は、 step が interval
    に hit したら **NaN-graceful snapshot** を 1 件録る (= crash せず、 PR-22
    DPN22-1 back-compat scope #4)。 実 score は注入経路 (train_with_preference_opt)
    が tokenizer + reference + records を渡したときのみ算出される。
    """
    validation = tmp_path / "validation.json"
    validation.write_text("{}", encoding="utf-8")
    config = PreferenceOptimizationConfig(
        algorithm=PreferenceAlgorithm.DPO,
        beta_or_tau=0.1,
        warm_start_adapter_path=(tmp_path / "warm"),
        reference_adapter_path=(tmp_path / "ref"),
        preference_pair_source=(tmp_path / "pairs.json"),
        gated_burrows_qc_threshold="loose",
        output_dir=(tmp_path / "out"),
        burrows_tracking_interval_steps=10,
        burrows_validation_set_path=validation,
    )
    cb = BurrowsTrackingCallback(config)  # 注入なし
    cb.on_step_end(args=None, state=_StubState(global_step=20), control=None)
    assert len(cb.tracking) == 1
    entry = cb.tracking[0]
    assert entry["step"] == 20
    # NaN-graceful: 実値は出ない (注入欠落) が key + note は存在
    assert math.isnan(entry["validation_burrows_reduction_pct"])
    assert math.isnan(entry["validation_vendi_score"])
    assert "note" in entry


# ---------------------------------------------------------------------------
# v2 (ReferenceUnigramTable reverse-KL) happy-path — PR-22 DPN22-0/1
# ---------------------------------------------------------------------------


class _StubTokenizer:
    """Deterministic stub tokenizer (text -> token-id list) for unit tests.

    transformers 非依存。 ``encode`` は HF tokenizer の signature を模す
    (``add_special_tokens=False`` で content token のみ返す)。
    """

    def __init__(self, mapping: dict[str, list[int]]) -> None:
        self._mapping = mapping

    def encode(
        self,
        text: str,
        add_special_tokens: bool = True,  # noqa: ARG002, FBT001, FBT002
    ) -> list[int]:
        return list(self._mapping.get(text, []))


def _make_reference_table(
    probs: tuple[float, float, float],
    other: float,
) -> ReferenceUnigramTable:
    """K=3 function-word (token ids 10/20/30) + OTHER bucket の reference table."""
    return ReferenceUnigramTable(
        function_word_token_ids=(10, 20, 30),
        reference_probabilities=probs,
        other_bucket_probability=other,
        roundtrip_match_rate=1.0,
    )


def _validation_fixture() -> tuple[_StubTokenizer, list[dict[str, str]]]:
    """2 completion + stub tokenizer (token id 99 = OTHER bucket 行き)。"""
    tokenizer = _StubTokenizer(
        {
            "Die Wahrheit ist Pflicht.": [10, 10, 20, 30, 99],
            "Der Mensch handelt frei.": [10, 20, 20, 99, 99],
        }
    )
    records = [
        {"prompt": "p1", "completion": "Die Wahrheit ist Pflicht."},
        {"prompt": "p2", "completion": "Der Mensch handelt frei."},
    ]
    return tokenizer, records


def test_burrows_snapshot_v2_returns_finite_reverse_kl_reduction(
    tmp_path: Path,
) -> None:
    """v2 (B実): 注入された tokenizer + reference + records から実 reverse-KL
    reduction% + Jaccard Vendi + bootstrap CI lower を算出 (NaN placeholder 解消、
    caveat ⑥ resolved = NaN→実値)。"""
    validation = tmp_path / "validation.json"
    validation.write_text("placeholder", encoding="utf-8")
    config = PreferenceOptimizationConfig(
        algorithm=PreferenceAlgorithm.KTO,
        beta_or_tau=1.0,
        warm_start_adapter_path=(tmp_path / "warm"),
        reference_adapter_path=(tmp_path / "ref"),
        preference_pair_source=(tmp_path / "pairs.json"),
        gated_burrows_qc_threshold="loose",
        output_dir=(tmp_path / "out"),
        burrows_tracking_interval_steps=10,
        burrows_validation_set_path=validation,
    )
    tokenizer, records = _validation_fixture()
    reference = _make_reference_table((0.4, 0.3, 0.1), 0.2)
    cb = BurrowsTrackingCallback(
        config,
        tokenizer=tokenizer,
        reference_table=reference,
        validation_records=records,
    )
    cb.on_step_end(args=None, state=_StubState(global_step=20), control=None)
    assert len(cb.tracking) == 1
    entry = cb.tracking[0]
    assert entry["step"] == 20
    reduction = entry["validation_burrows_reduction_pct"]
    vendi = entry["validation_vendi_score"]
    ci_lower = entry["validation_burrows_ci_lower"]
    # 実 score: marginal が uniform より reference に近い → reduction% > 0
    assert math.isfinite(reduction)
    assert reduction > 0.0
    # 手計算: 2 completion の token 合算 ([10,10,20,30,99] + [10,20,20,99,99])
    # → fw bucket counts [10→3, 20→3, 30→1, OTHER(99)→3] = [3,3,1,3], total=10
    # → pooled marginal [0.3,0.3,0.1,0.3] vs ref [0.4,0.3,0.1,0.2]
    # → reverse-KL(pooled||ref)=0.0353, baseline=KL(uniform||ref)=0.1218
    # → reduction = (0.1218-0.0353)/0.1218*100 ≈ 71%
    assert reduction == pytest.approx(71.0, abs=2.0)
    assert math.isfinite(vendi)
    assert vendi >= 1.0  # Vendi >= 1 (2 distinct completions)
    assert math.isfinite(ci_lower)
    assert entry["validation_kernel_name"] == "lexical-5gram-jaccard"


def test_burrows_snapshot_v2_is_reference_sensitive(tmp_path: Path) -> None:
    """caveat ⑦ (c) の unit 証明: **同一 completion + tokenizer で reference を
    差し替えると reduction% が変化** する (= unigram quality が tracking score に
    伝播する経路の成立)。 v1 案 X (BurrowsReference) では構造的に不可能だった点。"""
    validation = tmp_path / "validation.json"
    validation.write_text("placeholder", encoding="utf-8")
    config = PreferenceOptimizationConfig(
        algorithm=PreferenceAlgorithm.KTO,
        beta_or_tau=1.0,
        warm_start_adapter_path=(tmp_path / "warm"),
        reference_adapter_path=(tmp_path / "ref"),
        preference_pair_source=(tmp_path / "pairs.json"),
        gated_burrows_qc_threshold="loose",
        output_dir=(tmp_path / "out"),
        burrows_tracking_interval_steps=10,
        burrows_validation_set_path=validation,
    )
    tokenizer, records = _validation_fixture()

    cb_a = BurrowsTrackingCallback(
        config,
        tokenizer=tokenizer,
        reference_table=_make_reference_table((0.4, 0.3, 0.1), 0.2),
        validation_records=records,
    )
    cb_b = BurrowsTrackingCallback(
        config,
        tokenizer=tokenizer,
        reference_table=_make_reference_table((0.1, 0.1, 0.1), 0.7),
        validation_records=records,
    )
    cb_a.on_step_end(args=None, state=_StubState(global_step=20), control=None)
    cb_b.on_step_end(args=None, state=_StubState(global_step=20), control=None)
    red_a = cb_a.tracking[0]["validation_burrows_reduction_pct"]
    red_b = cb_b.tracking[0]["validation_burrows_reduction_pct"]
    assert math.isfinite(red_a)
    assert math.isfinite(red_b)
    # reference 差し替えで reduction% が確実に変化 (decoupling 解消)
    assert red_a != pytest.approx(red_b, abs=1.0)


def test_burrows_snapshot_v2_nan_graceful_on_empty_tokenization(
    tmp_path: Path,
) -> None:
    """全 completion が空 token (tokenizer が空列を返す) の場合は NaN-graceful。"""
    validation = tmp_path / "validation.json"
    validation.write_text("placeholder", encoding="utf-8")
    config = PreferenceOptimizationConfig(
        algorithm=PreferenceAlgorithm.KTO,
        beta_or_tau=1.0,
        warm_start_adapter_path=(tmp_path / "warm"),
        reference_adapter_path=(tmp_path / "ref"),
        preference_pair_source=(tmp_path / "pairs.json"),
        gated_burrows_qc_threshold="loose",
        output_dir=(tmp_path / "out"),
        burrows_tracking_interval_steps=10,
        burrows_validation_set_path=validation,
    )
    tokenizer = _StubTokenizer({})  # 全 text 未登録 → 空 token
    records = [{"prompt": "p", "completion": "unknown text"}]
    cb = BurrowsTrackingCallback(
        config,
        tokenizer=tokenizer,
        reference_table=_make_reference_table((0.4, 0.3, 0.1), 0.2),
        validation_records=records,
    )
    cb.on_step_end(args=None, state=_StubState(global_step=20), control=None)
    entry = cb.tracking[0]
    assert math.isnan(entry["validation_burrows_reduction_pct"])


def test_burrows_tracking_callback_provides_all_hf_trainer_event_hooks(
    tmp_path: Path,
) -> None:
    """Regression: HF Trainer ``CallbackHandler`` enumerates a fixed event list
    and unconditionally calls ``getattr(callback, event)(args, state, control)``.

    Phase 1.5 sweep failed because the callback only defined ``on_step_end``;
    every cell hit ``AttributeError: ... no attribute 'on_init_end'`` during
    trainer initialisation. Verify the full duck-type contract: every event
    in transformers' fixed list returns ``control`` unchanged (passthrough).
    """
    config = _make_config(tmp_path)
    cb = BurrowsTrackingCallback(config)
    # transformers/trainer_callback.py CallbackHandler enumerates these event
    # names. Pinning the full set so future TRL/transformers upgrades that add
    # new event hooks surface here (vs. silently breaking at GPU launch).
    events = [
        "on_init_end",
        "on_train_begin",
        "on_train_end",
        "on_epoch_begin",
        "on_epoch_end",
        "on_step_begin",
        "on_step_end",
        "on_substep_end",
        "on_evaluate",
        "on_predict",
        "on_save",
        "on_log",
        "on_prediction_step",
    ]
    sentinel = object()
    for event in events:
        hook = getattr(cb, event)
        # all events must be callable (no AttributeError); on_step_end has its
        # own implementation, the rest are no-op passthroughs
        result = hook(args=None, state=_StubState(global_step=0), control=sentinel)
        if event == "on_step_end":
            # on_step_end with global_step=0 should return control unchanged
            # (the global_step<=0 branch returns control early)
            assert result is sentinel
        else:
            # passthrough returns control unchanged
            assert result is sentinel


def test_burrows_tracking_callback_getattr_raises_for_non_event_attributes(
    tmp_path: Path,
) -> None:
    """``__getattr__`` must only respond to ``on_*`` events, not silently
    swallow other typos / mistakes."""
    config = _make_config(tmp_path)
    cb = BurrowsTrackingCallback(config)
    with pytest.raises(AttributeError, match=r"has no attribute 'not_a_hook'"):
        cb.not_a_hook  # noqa: B018  # intentional attribute access for AttributeError


# ---------------------------------------------------------------------------
# _load_validation_records: schema/version/sha 検証 (PR-22 Codex MEDIUM-1)
# ---------------------------------------------------------------------------


def _write_valset(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "valset.json"
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return p


_VALSET_RECORDS = [
    {"prompt": "p1", "completion": "c1"},
    {"prompt": "p2", "completion": "c2"},
]
_VALSET_SHA = "f15f11eec722701e759952b30769f64ba02d4f974d2495be7c168fe9a236eb0b"


def test_load_validation_records_happy_path_no_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """format_version='1' + 一致 sha256 では warning なしで records を load."""
    path = _write_valset(
        tmp_path,
        {
            "format_version": "1",
            "records": _VALSET_RECORDS,
            "metadata": {"sha256": _VALSET_SHA},
        },
    )
    with caplog.at_level("WARNING"):
        records = _load_validation_records(path)
    assert records == _VALSET_RECORDS
    assert not [r for r in caplog.records if r.levelname == "WARNING"]


def test_load_validation_records_warns_on_unknown_format_version(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """未知 format_version は warning にとどめ best-effort load 続行 (fwd-compat)."""
    path = _write_valset(
        tmp_path,
        {
            "format_version": "99",
            "records": _VALSET_RECORDS,
            "metadata": {"sha256": _VALSET_SHA},
        },
    )
    with caplog.at_level("WARNING"):
        records = _load_validation_records(path)
    assert records == _VALSET_RECORDS  # best-effort load 続行
    assert any("format_version" in r.message for r in caplog.records)


def test_load_validation_records_warns_on_sha_mismatch(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """metadata.sha256 不一致 (records 編集) は provenance drift warning."""
    path = _write_valset(
        tmp_path,
        {
            "format_version": "1",
            "records": _VALSET_RECORDS,
            "metadata": {"sha256": "0" * 64},
        },
    )
    with caplog.at_level("WARNING"):
        records = _load_validation_records(path)
    assert records == _VALSET_RECORDS  # best-effort load 続行
    assert any("sha256 mismatch" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# KTO label imbalance weight (caveat ⑤ / Codex HIGH-3 fix、 DPN-rebind-1)
# ---------------------------------------------------------------------------


def _trl_band_would_warn(
    n_desirable: int, n_undesirable: int, des_w: float, und_w: float
) -> bool:
    """``trl.experimental.kto.kto_trainer`` の label-balance band check 再現.

    KTO 論文 Eq.(8)。 与えた weight が TRL の warning 条件 (= band 外) に該当するか
    を返す。 ``compute_kto_label_weights`` の算出 weight がこれを ``False`` にする
    (= TRL 警告を回避する) ことを cross-check するための reference 実装。
    """
    # trl-kto-weight-source-verbatim.txt と同じ clamp: num_undesirable は
    # ``len - num_desirable`` (clamped num_desirable 由来) を用いる (Codex LOW-1)。
    total = n_desirable + n_undesirable
    num_desirable = max(n_desirable, 1)
    num_undesirable = max(total - num_desirable, 1)
    if num_desirable == num_undesirable:
        return False
    des_lower = round((num_undesirable * und_w / num_desirable) * 1, 2)
    des_upper = round((num_undesirable * und_w / num_desirable) * 1.33, 2)
    und_lower = round((num_desirable * des_w / num_undesirable) / 1.33, 2)
    und_upper = round((num_desirable * des_w / num_undesirable) / 1, 2)
    des_in_range = des_lower <= des_w <= des_upper
    und_in_range = und_lower <= und_w <= und_upper
    return not (des_in_range or und_in_range)


def test_compute_kto_weights_imbalanced_desirable_majority() -> None:
    """PR-18 scale 87/10 → undesirable を up-weight し weighted_ratio=1.0 + band 内."""
    dec = compute_kto_label_weights([True] * 87 + [False] * 10)
    assert isinstance(dec, KtoLabelWeightDecision)
    assert dec.label_positive_count == 87
    assert dec.label_negative_count == 10
    assert dec.desirable_weight == pytest.approx(1.0)
    assert dec.undesirable_weight == pytest.approx(8.7)  # round(87/10, 2)
    assert dec.adjusted_side == "undesirable"
    assert dec.strategy == "rebalanced"
    assert dec.weighted_label_ratio == pytest.approx(1.0)
    # 算出 weight は TRL band 内 (= TRL warning を回避する)
    assert dec.und_weight_lower_bound == pytest.approx(6.54)
    assert dec.und_weight_upper_bound == pytest.approx(8.7)
    assert (
        _trl_band_would_warn(87, 10, dec.desirable_weight, dec.undesirable_weight)
        is False
    )


def test_compute_kto_weights_imbalanced_undesirable_majority() -> None:
    """10/87 → desirable を up-weight (対称)。 adjusted_side='desirable'."""
    dec = compute_kto_label_weights([True] * 10 + [False] * 87)
    assert dec.label_positive_count == 10
    assert dec.label_negative_count == 87
    assert dec.desirable_weight == pytest.approx(8.7)  # round(87/10, 2)
    assert dec.undesirable_weight == pytest.approx(1.0)
    assert dec.adjusted_side == "desirable"
    assert dec.strategy == "rebalanced"
    assert dec.weighted_label_ratio == pytest.approx(1.0)
    assert (
        _trl_band_would_warn(10, 87, dec.desirable_weight, dec.undesirable_weight)
        is False
    )


def test_compute_kto_weights_balanced_is_noop() -> None:
    """完全均衡 (39/39) → TRL band 非発火 = 1.0/1.0、 strategy='balanced'."""
    dec = compute_kto_label_weights([True] * 39 + [False] * 39)
    assert dec.desirable_weight == pytest.approx(1.0)
    assert dec.undesirable_weight == pytest.approx(1.0)
    assert dec.adjusted_side == "none"
    assert dec.strategy == "balanced"
    assert dec.weighted_label_ratio == pytest.approx(1.0)


def test_compute_kto_weights_round_boundary_stays_in_band() -> None:
    """割り切れない比 (100/3) でも round(2) 一致で TRL band 内 (v2 catch)."""
    dec = compute_kto_label_weights([True] * 100 + [False] * 3)
    assert dec.undesirable_weight == pytest.approx(round(100 / 3, 2))  # 33.33
    assert dec.desirable_weight == pytest.approx(1.0)
    # round(2) で揃えないと weight が band upper を僅かに超え TRL が warn する
    assert (
        _trl_band_would_warn(100, 3, dec.desirable_weight, dec.undesirable_weight)
        is False
    )


def test_compute_kto_weights_pr21_kant_de_61_9_forensic() -> None:
    """PR-21 kant_de 実データ [61,9] の caveat ⑤ rebind 実測値を test 層に pin.

    PR-21 GPU exec verdict ([[project_plan_b_kant_pr21_gpu_exec]]) で caveat ⑤
    (KTO label imbalance) が ``rebind_to_kto_w_weight`` 経由で実測解消した値の
    forensic regression。 generic な 87/10 test
    (:func:`test_compute_kto_weights_imbalanced_desirable_majority`) とは別に、
    PR-21 train-metadata に記録された実 label 分布 ``desirable 61 / undesirable 9``
    を machine-readable に固定する (caveat ⑤ over-claim guard:
    weight 未設定の解消のみで structural ceiling / binary floor は別軸 unresolved)。

    round(61/9, 2) = 6.78 は 9 に割り切れないため ``weighted_label_ratio`` は
    厳密 1.0 にならず 0.9997 程度 (round(2) 丸め artifact = DPN-pr24-impl-3 と整合)。
    band upper 端 (6.78) に着地し TRL warning は回避される。
    """
    dec = compute_kto_label_weights([True] * 61 + [False] * 9)
    assert isinstance(dec, KtoLabelWeightDecision)
    assert dec.label_positive_count == 61
    assert dec.label_negative_count == 9
    assert dec.desirable_weight == pytest.approx(1.0)
    assert dec.undesirable_weight == pytest.approx(6.78)  # round(61/9, 2)
    assert dec.adjusted_side == "undesirable"
    assert dec.strategy == "rebalanced"
    # round(2) 丸め artifact: 61/(6.78*9)=0.9997 ≈ 1.0 (厳密 1.0 ではない)
    assert dec.weighted_label_ratio == pytest.approx(1.0, abs=0.01)
    assert dec.weighted_label_ratio != pytest.approx(1.0, abs=1e-9)
    # 算出 weight は TRL band 上端に着地し warning を回避する
    assert dec.und_weight_upper_bound == pytest.approx(6.78)
    assert dec.und_weight_lower_bound == pytest.approx(5.10)
    assert (
        _trl_band_would_warn(61, 9, dec.desirable_weight, dec.undesirable_weight)
        is False
    )


def test_compute_kto_weights_degenerate_single_class_positive_only() -> None:
    """縮退 8/0 (negative ゼロ) → 1.0/1.0 維持 + degenerate strategy."""
    dec = compute_kto_label_weights([True] * 8)
    assert dec.label_positive_count == 8
    assert dec.label_negative_count == 0
    assert dec.desirable_weight == pytest.approx(1.0)
    assert dec.undesirable_weight == pytest.approx(1.0)
    assert dec.adjusted_side == "none"
    assert dec.strategy == "degenerate_single_class"
    assert math.isnan(dec.weighted_label_ratio)


def test_compute_kto_weights_degenerate_single_class_negative_only() -> None:
    """縮退 0/8 (positive ゼロ) → 1.0/1.0 維持 + degenerate strategy."""
    dec = compute_kto_label_weights([False] * 8)
    assert dec.label_positive_count == 0
    assert dec.label_negative_count == 8
    assert dec.strategy == "degenerate_single_class"
    assert dec.adjusted_side == "none"
    assert math.isnan(dec.weighted_label_ratio)


def test_compute_kto_weights_empty_raises_value_error() -> None:
    """空 0/0 → ValueError (model load 前 fail-fast、 user 承認)."""
    with pytest.raises(ValueError, match="empty label set"):
        compute_kto_label_weights([])


def test_build_trainer_config_kwargs_kto_injects_weights(tmp_path: Path) -> None:
    """KTO + kto_weights → desirable/undesirable_weight が kwargs に入る."""
    config = _make_config(tmp_path, algorithm=PreferenceAlgorithm.KTO, beta_or_tau=1.0)
    dec = compute_kto_label_weights([True] * 87 + [False] * 10)
    kwargs = _build_trainer_config_kwargs(config, kto_weights=dec)
    assert kwargs["desirable_weight"] == pytest.approx(1.0)
    assert kwargs["undesirable_weight"] == pytest.approx(8.7)
    assert kwargs["beta"] == pytest.approx(1.0)


def test_build_trainer_config_kwargs_kto_without_weights_is_back_compat(
    tmp_path: Path,
) -> None:
    """kto_weights=None (back-compat) → weight key を注入しない (従来 1.0/1.0 経路)."""
    config = _make_config(tmp_path, algorithm=PreferenceAlgorithm.KTO, beta_or_tau=1.0)
    kwargs = _build_trainer_config_kwargs(config)
    assert "desirable_weight" not in kwargs
    assert "undesirable_weight" not in kwargs


@pytest.mark.parametrize(
    "algorithm",
    [PreferenceAlgorithm.DPO, PreferenceAlgorithm.IPO],
)
def test_build_trainer_config_kwargs_non_kto_never_gets_weights(
    tmp_path: Path, algorithm: PreferenceAlgorithm
) -> None:
    """DPO/IPO には KTO 専用 weight kwargs を渡さない (regression、 追加 2)."""
    config = _make_config(tmp_path, algorithm=algorithm)
    dec = compute_kto_label_weights([True] * 87 + [False] * 10)
    # 誤って kto_weights を渡しても DPO/IPO 分岐では注入されない
    kwargs = _build_trainer_config_kwargs(config, kto_weights=dec)
    assert "desirable_weight" not in kwargs
    assert "undesirable_weight" not in kwargs


@pytest.mark.filterwarnings("ignore::FutureWarning")
def test_real_kto_config_accepts_injected_weights(tmp_path: Path) -> None:
    """実 KTOConfig が算出 weight を field に反映する (importorskip trl).

    ``from trl import KTOConfig`` は trl 0.29.1 で ``trl.experimental`` 移行の
    FutureWarning を出す (production ``get_preference_trainer_class`` の import
    経路と同一、 本変更とは無関係) ため、 本 test では当該 warning を許容する。
    """
    pytest.importorskip("trl")
    from trl import KTOConfig

    config = _make_config(tmp_path, algorithm=PreferenceAlgorithm.KTO, beta_or_tau=1.0)
    dec = compute_kto_label_weights([True] * 87 + [False] * 10)
    kwargs = _build_trainer_config_kwargs(config, kto_weights=dec)
    trainer_args = KTOConfig(**kwargs)
    assert trainer_args.desirable_weight == pytest.approx(1.0)
    assert trainer_args.undesirable_weight == pytest.approx(8.7)


def test_as_metadata_dict_carries_kto_weight_provenance() -> None:
    """KTO weight provenance 6 field + adjusted_side が train_metadata に embed."""
    dec = compute_kto_label_weights([True] * 87 + [False] * 10)
    result = PreferenceTrainingResult(
        algorithm="kto",
        reward_definition="gated_burrows_e3",
        policy_warm_start_adapter="warm/path",
        reference_policy_adapter="ref/path",
        preference_pair_source="pairs.json",
        gated_burrows_qc_threshold="loose",
        beta_or_tau=1.0,
        seed=44,
        max_steps=500,
        final_loss=0.42,
        adapter_snapshot_path="out/snap",
        kto_label_weights=dec,
    )
    payload = result.as_metadata_dict()
    assert payload["kto_desirable_weight"] == pytest.approx(1.0)
    assert payload["kto_undesirable_weight"] == pytest.approx(8.7)
    assert payload["kto_label_positive_count"] == 87
    assert payload["kto_label_negative_count"] == 10
    assert payload["kto_weighted_label_ratio"] == pytest.approx(1.0)
    assert payload["kto_weight_strategy"] == "rebalanced"
    assert payload["kto_weight_adjusted_side"] == "undesirable"
    # JSON 直列化可能 (nan を含まない rebalanced ケース)
    json.dumps(payload)


def test_as_metadata_dict_kto_provenance_is_none_for_dpo() -> None:
    """非 KTO (DPO) では KTO weight field が None (= 補正対象外を記録)."""
    result = PreferenceTrainingResult(
        algorithm="dpo",
        reward_definition="gated_burrows_e3",
        policy_warm_start_adapter="warm/path",
        reference_policy_adapter="ref/path",
        preference_pair_source="pairs.json",
        gated_burrows_qc_threshold="loose",
        beta_or_tau=0.1,
        seed=44,
        max_steps=500,
        final_loss=0.42,
        adapter_snapshot_path="out/snap",
    )
    payload = result.as_metadata_dict()
    assert payload["kto_desirable_weight"] is None
    assert payload["kto_undesirable_weight"] is None
    assert payload["kto_label_positive_count"] is None
    assert payload["kto_label_negative_count"] is None
    assert payload["kto_weighted_label_ratio"] is None
    assert payload["kto_weight_strategy"] is None
    assert payload["kto_weight_adjusted_side"] is None


# ---------------------------------------------------------------------------
# train_with_preference_opt wrapper 経路 (Codex MEDIUM-1: fail-fast / warn 保護)
# ---------------------------------------------------------------------------

_PB = "erre_sandbox.training.preference_burrows"


def _write_kto_pairs(tmp_path: Path, *, n_positive: int, n_negative: int) -> None:
    """``_make_config`` の preference_pair_source (tmp_path/pairs.json) を上書き."""
    records = [
        {"prompt": f"p{i}", "completion": f"c{i}", "label": True}
        for i in range(n_positive)
    ] + [
        {"prompt": f"n{i}", "completion": f"d{i}", "label": False}
        for i in range(n_negative)
    ]
    (tmp_path / "pairs.json").write_text(
        json.dumps({"format_version": "1", "binary_records": records}),
        encoding="utf-8",
    )


class _FakeConfig:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs


class _FakeTrainer:
    last_init_kwargs: ClassVar[dict[str, object]] = {}

    def __init__(self, **kwargs: object) -> None:
        type(self).last_init_kwargs = kwargs
        self.state = SimpleNamespace(log_history=[])

    def train(self) -> SimpleNamespace:
        return SimpleNamespace(training_loss=0.5)

    def save_model(self, output_dir: str) -> None:  # noqa: ARG002
        return None


def test_train_with_preference_opt_kto_empty_fails_before_model_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """KTO empty records → load_trainable_policy 到達前に ValueError (GPU 浪費回避).

    Codex MEDIUM-1: helper 単体だけでなく wrapper 経路で fail-fast-before-load を保護。
    """
    config = _make_config(tmp_path, algorithm=PreferenceAlgorithm.KTO, beta_or_tau=1.0)
    # _make_config の pairs.json は "{}" = binary_records 空 = label 0 件
    loaded: list[str] = []

    def _track_trainable(*_a: object, **_k: object) -> tuple[object, object]:
        loaded.append("trainable")
        return object(), object()

    def _track_ref(*_a: object, **_k: object) -> object:
        loaded.append("ref")
        return object()

    monkeypatch.setattr(f"{_PB}.load_trainable_policy", _track_trainable)
    monkeypatch.setattr(f"{_PB}.load_frozen_reference_policy", _track_ref)

    with pytest.raises(ValueError, match="empty label set"):
        train_with_preference_opt(config)
    assert loaded == []  # model load に到達していない (fail-fast before GPU)


def test_train_with_preference_opt_kto_single_class_warns_and_keeps_default_weights(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """KTO single-class (8/0) → WARNING + 1.0/1.0 が trainer config に流れる (挙動不変).

    Codex MEDIUM-1: single-class で warn しつつ 1.0/1.0 が trainer args に渡る wiring
    を保護 (heavy stack は monkeypatch でスタブ)。
    """
    config = _make_config(tmp_path, algorithm=PreferenceAlgorithm.KTO, beta_or_tau=1.0)
    _write_kto_pairs(tmp_path, n_positive=8, n_negative=0)
    loaded: list[str] = []

    def _track_trainable(*_a: object, **_k: object) -> tuple[object, object]:
        loaded.append("trainable")
        return object(), object()

    def _track_ref(*_a: object, **_k: object) -> object:
        loaded.append("ref")
        return object()

    monkeypatch.setattr(f"{_PB}.load_trainable_policy", _track_trainable)
    monkeypatch.setattr(f"{_PB}.load_frozen_reference_policy", _track_ref)
    monkeypatch.setattr(
        f"{_PB}.get_preference_trainer_class", lambda _algo: (_FakeTrainer, _FakeConfig)
    )
    # `from datasets import Dataset` を軽量スタブで満たす (extras 不要化)
    fake_datasets = types.ModuleType("datasets")
    fake_datasets.Dataset = SimpleNamespace(from_list=lambda recs: recs)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "datasets", fake_datasets)

    with caplog.at_level("WARNING"):
        result = train_with_preference_opt(config)

    # single-class は WARNING を出すが load まで進む (挙動不変、 fail-fast しない)
    assert any("single-class" in r.message for r in caplog.records)
    assert loaded == ["trainable", "ref"]
    # 1.0/1.0 が trainer config (TRL config kwargs) に流れた
    trainer_args = _FakeTrainer.last_init_kwargs["args"]
    assert isinstance(trainer_args, _FakeConfig)
    assert trainer_args.kwargs["desirable_weight"] == pytest.approx(1.0)
    assert trainer_args.kwargs["undesirable_weight"] == pytest.approx(1.0)
    # provenance に degenerate が記録される
    assert result.kto_label_weights is not None
    assert result.kto_label_weights.strategy == "degenerate_single_class"
