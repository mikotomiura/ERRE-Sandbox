"""Unit tests for ``erre_sandbox.training.preference_pair_builder`` (PR-18 Phase 2).

Covers:

* :func:`load_completion_triples` — JSON schema 検証 + 不正入力時の error。
* :func:`build_preference_pairs` — Burrows Delta rank → chosen/rejected pair
  + binary label (KTO) 化、 QC filter integration、 NaN drop / tie drop。
* :func:`save_preference_pairs` — JSON roundtrip。

burrows.py + tier_a Burrows machinery を使うが、 mock な BurrowsReference
を直接構築して使う (CI default profile で完結)。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from erre_sandbox.evidence.tier_a.burrows import BurrowsReference
from erre_sandbox.training.preference_pair_builder import (
    FORMAT_VERSION,
    BinaryRecord,
    CompletionTriple,
    PreferencePairRecord,
    build_preference_pairs,
    load_completion_triples,
    save_preference_pairs,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_de_reference() -> BurrowsReference:
    """Synthetic German Burrows reference (3 function words).

    profile_freq の構造: "der" 大頻出 (0.6)、 "die" 中庸 (0.15)、 "das" 控えめ (0.10)。
    Burrows Delta が smaller になる side = "der" を多用する text。
    """
    return BurrowsReference(
        language="de",
        function_words=("der", "die", "das"),
        background_mean=(0.05, 0.05, 0.05),
        background_std=(0.02, 0.02, 0.02),
        profile_freq=(0.60, 0.15, 0.10),
    )


# ---------------------------------------------------------------------------
# Triple loader
# ---------------------------------------------------------------------------


def test_load_completion_triples_parses_schema(tmp_path: Path) -> None:
    triples_path = tmp_path / "triples.json"
    triples_path.write_text(
        json.dumps(
            {
                "format_version": "1",
                "source_shard_pairs": [{"lora_on_shard": "a", "no_lora_shard": "b"}],
                "completion_triples": [
                    {
                        "prompt": "frage 1",
                        "lora_on_completion": "der text der hier ist",
                        "no_lora_completion": "irgendwas anders",
                        "stim_id": "s1",
                        "run_id": 0,
                        "shard_pair_index": 0,
                    },
                ],
            },
        ),
        encoding="utf-8",
    )
    triples = load_completion_triples(triples_path)
    assert len(triples) == 1
    assert triples[0].prompt == "frage 1"
    assert triples[0].stim_id == "s1"
    assert triples[0].run_id == 0


def test_load_completion_triples_raises_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_completion_triples(tmp_path / "nope.json")


def test_load_completion_triples_raises_on_missing_list(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"format_version": "1"}), encoding="utf-8")
    with pytest.raises(ValueError, match=r"completion_triples"):
        load_completion_triples(p)


# ---------------------------------------------------------------------------
# Build pairs — happy path
# ---------------------------------------------------------------------------


def test_build_preference_pairs_chooses_smaller_delta_side() -> None:
    # LoRA-on text uses function words at higher freq (closer to profile) =>
    # smaller Burrows Delta => chosen
    triple = CompletionTriple(
        prompt="frage",
        lora_on_completion="der der der die das",  # delta closer to profile
        no_lora_completion="ich gehe weg etwas anders",  # function word density low
        stim_id="s1",
        run_id=0,
    )
    result = build_preference_pairs(
        [triple],
        _mock_de_reference(),
        language="de",
    )
    assert len(result.pair_records) == 1
    pair = result.pair_records[0]
    assert pair.chosen == "der der der die das"
    assert pair.rejected == "ich gehe weg etwas anders"
    # binary records: 2 (両 side) — lora-on は good, no-lora は bad
    assert len(result.binary_records) == 2
    lora_record = next(
        b for b in result.binary_records if b.completion == triple.lora_on_completion
    )
    no_lora_record = next(
        b for b in result.binary_records if b.completion == triple.no_lora_completion
    )
    assert lora_record.label is True
    assert no_lora_record.label is False


def test_build_preference_pairs_drops_tie() -> None:
    # 両 completion とも同じ Burrows Delta = tie → pair drop
    triple = CompletionTriple(
        prompt="frage",
        lora_on_completion="der die das",
        no_lora_completion="der die das",
        stim_id="s1",
        run_id=0,
    )
    result = build_preference_pairs(
        [triple],
        _mock_de_reference(),
        language="de",
    )
    # Tie = preference signal なしのため pair も binary も全 drop (design intent)。
    # `build_preference_pairs` の tie branch は ``continue`` で外側 for に戻り、
    # binary records 蓄積 step も skip する (両 candidate equally good ≠ KTO 学習材料)。
    assert result.pair_records == ()
    assert result.binary_records == ()


def test_build_preference_pairs_drops_empty_text() -> None:
    triple = CompletionTriple(
        prompt="frage",
        lora_on_completion="",
        no_lora_completion="",
        stim_id="s1",
        run_id=0,
    )
    result = build_preference_pairs(
        [triple],
        _mock_de_reference(),
        language="de",
    )
    # 両 text empty → Burrows Delta NaN → 全件 drop
    assert result.pair_records == ()
    assert result.binary_records == ()
    assert result.metadata["dropped_delta_nan"] == 1


def test_build_preference_pairs_with_qc_filter_excludes_failed_side() -> None:
    def qc_filter(text: str) -> bool:
        # 30 文字未満は FAIL
        return len(text) >= 30

    triple = CompletionTriple(
        prompt="frage",
        lora_on_completion="der der der die das ist lang genug text ok",  # PASS
        no_lora_completion="kurz",  # FAIL
        stim_id="s1",
        run_id=0,
    )
    result = build_preference_pairs(
        [triple],
        _mock_de_reference(),
        language="de",
        qc_filter=qc_filter,
    )
    # 片側 FAIL → pair は作れない (両 finite delta が必要)、 binary には PASS
    # 側のみ残る (good label)
    assert result.pair_records == ()
    assert len(result.binary_records) == 1
    assert result.binary_records[0].completion.startswith("der der der die das")
    assert result.binary_records[0].label is True


def test_build_preference_pairs_drops_both_qc_fail() -> None:
    def qc_filter(_text: str) -> bool:
        return False

    triple = CompletionTriple(
        prompt="frage",
        lora_on_completion="der die das ist text",
        no_lora_completion="ich gehe weg anders",
        stim_id="s1",
        run_id=0,
    )
    result = build_preference_pairs(
        [triple],
        _mock_de_reference(),
        language="de",
        qc_filter=qc_filter,
    )
    assert result.pair_records == ()
    assert result.binary_records == ()
    assert result.metadata["dropped_qc_fail"] == 1


def test_build_preference_pairs_metadata_overrides_merge() -> None:
    triple = CompletionTriple(
        prompt="frage",
        lora_on_completion="der die das text",
        no_lora_completion="ich gehe weg anders",
        stim_id="s1",
        run_id=0,
    )
    result = build_preference_pairs(
        [triple],
        _mock_de_reference(),
        language="de",
        metadata_overrides={
            "reward_definition": "gated_burrows_e3",
            "source": "pr16_20_shard",
        },
    )
    assert result.metadata["reward_definition"] == "gated_burrows_e3"
    assert result.metadata["source"] == "pr16_20_shard"
    assert result.metadata["language"] == "de"  # builder-emitted default 残存


# ---------------------------------------------------------------------------
# JSON roundtrip
# ---------------------------------------------------------------------------


def test_save_and_reload_roundtrip(tmp_path: Path) -> None:
    triple = CompletionTriple(
        prompt="frage",
        lora_on_completion="der der die das text",
        no_lora_completion="ich gehe weg anders",
        stim_id="s1",
        run_id=0,
    )
    result = build_preference_pairs(
        [triple],
        _mock_de_reference(),
        language="de",
    )
    out_path = tmp_path / "subdir" / "pairs.json"
    save_preference_pairs(result, out_path)
    assert out_path.is_file()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["format_version"] == FORMAT_VERSION
    assert "pair_records" in payload
    assert "binary_records" in payload
    assert payload["metadata"]["language"] == "de"


def test_dataclass_immutability() -> None:
    pair = PreferencePairRecord(prompt="p", chosen="c", rejected="r", burrows_delta=0.5)
    with pytest.raises((AttributeError, TypeError)):
        pair.prompt = "mutated"  # type: ignore[misc]
    binary = BinaryRecord(prompt="p", completion="c", label=True, burrows_pct=0.5)
    with pytest.raises((AttributeError, TypeError)):
        binary.label = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Codex HIGH-2 反映: build_preference_pairs() triple 境界で qc_filter.reset_state()
# ---------------------------------------------------------------------------


class _QcFilterWithResetTracker:
    """Stub qc_filter that tracks reset_state() call count + always passes."""

    def __init__(self) -> None:
        self.reset_count: int = 0
        self.call_count: int = 0

    def reset_state(self) -> None:
        self.reset_count += 1

    def __call__(self, text: str) -> bool:  # noqa: ARG002
        self.call_count += 1
        return True


def test_build_preference_pairs_calls_qc_filter_reset_state_per_triple() -> None:
    """HIGH-2: build_preference_pairs() が triple 境界で reset_state() を呼ぶ.

    DPN20-2 #3 binding: stateful novelty_scorer の rolling prior buffer を
    per-triple scope で reset する。 reset_state() の call 回数が
    triple 数と一致 (= 各 triple の開始前に reset される)。
    """
    triples = [
        CompletionTriple(
            prompt=f"prompt-{i}",
            lora_on_completion="der die das der die das der die das der die das",
            no_lora_completion="der die das der die das der die das der die das",
            stim_id=f"stim-{i}",
            run_id=1,
        )
        for i in range(3)
    ]
    qc_filter = _QcFilterWithResetTracker()
    reference = _mock_de_reference()
    build_preference_pairs(
        triples,
        reference,
        language="de",
        qc_filter=qc_filter,  # type: ignore[arg-type]  # stub matches protocol
    )
    # reset_state() は各 triple の処理開始時に 1 回呼ばれる
    assert qc_filter.reset_count == len(triples)
    # qc_filter 自体は各 triple で 2 candidate (lora + no_lora) を call
    assert qc_filter.call_count == len(triples) * 2


def test_build_preference_pairs_handles_qc_filter_without_reset_state() -> None:
    """HIGH-2 (auxiliary): reset_state を持たない qc_filter で no-op (no error)."""

    class _NoResetFilter:
        def __init__(self) -> None:
            self.call_count: int = 0

        def __call__(self, text: str) -> bool:  # noqa: ARG002
            self.call_count += 1
            return True

    triples = [
        CompletionTriple(
            prompt="p1",
            lora_on_completion="der die das der die das der die das der die das",
            no_lora_completion="der die das der die das der die das der die das",
            stim_id="stim-1",
            run_id=1,
        )
    ]
    no_reset_filter = _NoResetFilter()
    reference = _mock_de_reference()
    # qc_filter has no reset_state() — getattr fallback to no-op、 raise しない
    build_preference_pairs(
        triples,
        reference,
        language="de",
        qc_filter=no_reset_filter,  # type: ignore[arg-type]
    )
    assert no_reset_filter.call_count == 2
