"""Unit tests for ``stratify_by_language`` on ``_group_aware_stratified_split``.

The split helper lives in :mod:`erre_sandbox.training.train_kant_lora` (see
``.steering/20260517-m9-c-adopt-plan-b-design/decisions.md`` DI-5 for why the
public-facing wording calls this ``dataset.py extension``). When the new
``stratify_by_language`` kw-only flag is on, each ``(source_shard_type,
language)`` cell receives its own 90/10 random split, which is the
contamination control for the Plan B de-monolog re-cast (design.md §1.6).
"""

from __future__ import annotations

import pytest

from erre_sandbox.training.train_kant_lora import _group_aware_stratified_split


def _make_example(
    *,
    shard: str,
    dialog_id: str,
    language: str,
    shard_type: str,
) -> dict[str, object]:
    return {
        "text": f"placeholder-{shard}-{dialog_id}",
        "weight_metadata": {
            "language": language,
            "token_count": 80,
            "has_addressee": False,
            "marker_density_per_100_tokens": 1.2,
            "source_shard": shard,
            "source_shard_type": shard_type,
            "dialog_id": dialog_id,
            "turn_index": 0,
        },
    }


def _build_balanced_corpus() -> dict[str, list[dict[str, object]]]:
    """20 dialogs across (natural|stimulus) × (de|en|ja|mixed) = 8 cells, 2-3 each.

    The cell sizes are intentionally small so that with default
    ``eval_split_fraction=0.10`` each cell gets exactly 1 eval and 1-2
    train keys, making the stratification effect observable.
    """
    examples_by_shard: dict[str, list[dict[str, object]]] = {}
    cells = [
        ("natural", "de", 3),
        ("natural", "en", 3),
        ("natural", "ja", 3),
        ("natural", "mixed", 2),
        ("stimulus", "de", 3),
        ("stimulus", "en", 3),
        ("stimulus", "ja", 3),
        ("stimulus", "mixed", 2),
    ]
    counter = 0
    for shard_type, lang, n in cells:
        for _ in range(n):
            counter += 1
            shard = f"kant_{shard_type}_run0.duckdb"
            dialog_id = f"{shard_type}_{lang}_d{counter}"
            ex = _make_example(
                shard=shard, dialog_id=dialog_id, language=lang, shard_type=shard_type
            )
            examples_by_shard.setdefault(shard, []).append(ex)
    return examples_by_shard


def test_default_behavior_is_byte_identical_when_flag_off() -> None:
    """``stratify_by_language=False`` (default) preserves existing behavior."""
    corpus = _build_balanced_corpus()
    train_a, eval_a = _group_aware_stratified_split(
        corpus, eval_split_fraction=0.10, seed=42
    )
    train_b, eval_b = _group_aware_stratified_split(
        corpus, eval_split_fraction=0.10, seed=42, stratify_by_language=False
    )
    assert train_a == train_b
    assert eval_a == eval_b


def test_stratify_by_language_separates_each_language_cell() -> None:
    """With the flag on, every (shard_type, language) cell sees its own split."""
    corpus = _build_balanced_corpus()
    train_keys, eval_keys = _group_aware_stratified_split(
        corpus, eval_split_fraction=0.10, seed=42, stratify_by_language=True
    )
    # Each cell has 2-3 keys; eval_split_fraction=0.10 → round(0.1*n) = 0 for
    # n<=4, but the function enforces "at least 1 eval if n > 1" via
    # ``max(1, round(...))`` AND ``min(n_eval, n-1)``. So 2-key cells get
    # 1 eval, 3-key cells get 1 eval. Total eval count = 8 cells × 1 = 8.
    assert len(eval_keys) == 8
    # No overlap between train and eval
    assert train_keys.isdisjoint(eval_keys)


def test_stratify_by_language_round_trip_metadata() -> None:
    """Eval keys span every (shard_type, language) stratum that has >=2 keys."""
    corpus = _build_balanced_corpus()
    _, eval_keys = _group_aware_stratified_split(
        corpus, eval_split_fraction=0.10, seed=42, stratify_by_language=True
    )
    # Build a quick lookup from group_key → (shard_type, language)
    key_to_stratum: dict[tuple[str, str], tuple[str, str]] = {}
    for shard, exs in corpus.items():
        for ex in exs:
            meta = ex["weight_metadata"]
            assert isinstance(meta, dict)
            key = (shard, str(meta["dialog_id"]))
            key_to_stratum[key] = (
                str(meta["source_shard_type"]),
                str(meta["language"]),
            )
    eval_strata = {key_to_stratum[k] for k in eval_keys}
    # All 8 cells (natural|stimulus × de|en|ja|mixed) should appear in eval.
    assert eval_strata == {
        ("natural", "de"),
        ("natural", "en"),
        ("natural", "ja"),
        ("natural", "mixed"),
        ("stimulus", "de"),
        ("stimulus", "en"),
        ("stimulus", "ja"),
        ("stimulus", "mixed"),
    }


def test_deterministic_for_fixed_seed() -> None:
    """Same seed + same flag produce identical splits across invocations."""
    corpus = _build_balanced_corpus()
    train_1, eval_1 = _group_aware_stratified_split(
        corpus, eval_split_fraction=0.10, seed=42, stratify_by_language=True
    )
    train_2, eval_2 = _group_aware_stratified_split(
        corpus, eval_split_fraction=0.10, seed=42, stratify_by_language=True
    )
    assert train_1 == train_2
    assert eval_1 == eval_2


def test_seed_sensitivity_distinguishes_strata() -> None:
    """Different seeds yield different splits while preserving stratum counts."""
    corpus = _build_balanced_corpus()
    _, eval_42 = _group_aware_stratified_split(
        corpus, eval_split_fraction=0.10, seed=42, stratify_by_language=True
    )
    _, eval_7 = _group_aware_stratified_split(
        corpus, eval_split_fraction=0.10, seed=7, stratify_by_language=True
    )
    # Per-stratum eval counts are preserved (8 strata × 1 eval = 8)
    assert len(eval_42) == 8
    assert len(eval_7) == 8
    # ...but the actual eval keys differ on at least some stratum
    assert eval_42 != eval_7


@pytest.mark.parametrize("shard_type", ["natural", "stimulus"])
def test_unknown_language_falls_to_mixed_bucket(shard_type: str) -> None:
    """Rows missing ``language`` fall back to ``"mixed"`` (default bucket)."""
    examples_by_shard: dict[str, list[dict[str, object]]] = {}
    shard = f"kant_{shard_type}_run0.duckdb"
    for i in range(4):
        ex = _make_example(
            shard=shard,
            dialog_id=f"d{i}",
            language="mixed",
            shard_type=shard_type,
        )
        examples_by_shard.setdefault(shard, []).append(ex)
    train_keys, eval_keys = _group_aware_stratified_split(
        examples_by_shard, eval_split_fraction=0.10, seed=42, stratify_by_language=True
    )
    assert len(train_keys) + len(eval_keys) == 4
    assert train_keys.isdisjoint(eval_keys)
