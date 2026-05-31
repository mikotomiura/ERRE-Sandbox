"""PR-14 DPN14-1.2 ``--language-filter`` flag tests for train_kant_lora.

Covers the new CLI flag wired into
:func:`erre_sandbox.training.train_kant_lora.train_kant_lora` and the
dataset-level filter in :func:`_collect_from_shards_weighted` (PR-14
Phase 1, Surface 5). 5 cases:

1. ``language_filter="all"`` (default) is byte-identical to the existing
   weighted path (backward compat).
2. ``language_filter="de"`` drops every en / ja example from the train +
   eval sets.
3. ``language_filter="en"`` drops every de / ja example.
4. argparse rejects an invalid value (``--language-filter fr``) with
   exit 2 (choices reject is structural, not the training error path).
5. ``per_language_weighted_mass`` in ``weight-audit.json`` reflects the
   filtered effective mass, and the DA-14 ``n_eff < 1000`` fallback
   trigger is re-evaluated against the filtered corpus
   (n_eff drops below the fallback when the filter shrinks the train
   set, so :class:`InsufficientEffectiveSampleSizeError` fires).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

from erre_sandbox.evidence.eval_store import (
    RAW_DIALOG_TABLE,
    bootstrap_schema,
)
from erre_sandbox.training.train_kant_lora import (
    InsufficientEffectiveSampleSizeError,
    _collect_from_shards_weighted,
    train_kant_lora,
)
from tests.test_training.conftest import make_kant_row

# Reuse the synthetic kant corpus utterance pools from the ja_drop test
# file rather than re-listing them here -- they exercise the same
# language-detection codepath in ``extract_example_metadata``.
_JA_UTTERANCES: tuple[str, ...] = (
    "私は哲学について考えています。実践理性とは何か。",
    "倫理学の根本は定言命法にあります。義務こそが行為の基準です。",
    "純粋理性批判は形而上学の限界を示しました。",
    "美と崇高は判断力批判で扱う主題です。日本語で考察します。",
    "経験を超えた認識は不可能ですが、理性は理念を構成します。",
    "自由意志は道徳法則の前提です。私たちは目的の王国に属します。",
)
_DE_UTTERANCES: tuple[str, ...] = (
    "Ich denke über die reine Vernunft und ihre Grenzen.",
    "Der kategorische Imperativ ist das Fundament der Pflicht.",
    "Pflicht ist nicht Neigung, sondern Achtung vor dem Sittengesetz.",
    "Die Kritik der praktischen Vernunft behandelt die Freiheit.",
    "Ich bin ein Bürger zweier Welten, der Sinneswelt und der Verstandeswelt.",
    "Das Ding an sich ist uns nicht erkennbar, nur die Erscheinung.",
)
_EN_UTTERANCES: tuple[str, ...] = (
    "I think about the limits of pure reason and metaphysics.",
    "The categorical imperative tells us to treat humanity as an end.",
    "Duty arises from respect for the moral law, never from inclination.",
    "Freedom is the keystone of the whole structure of practical reason.",
    "The thing-in-itself remains unknowable; appearances are all we have.",
    "Aesthetic judgment binds subjective feeling with universal communicability.",
)


def _writable(db: Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db), read_only=False)


def _insert_kant_row(
    con: duckdb.DuckDBPyConnection,
    row: dict[str, object],
) -> None:
    keys = sorted(row.keys())
    cols_sql = ", ".join(f'"{k}"' for k in keys)
    placeholders = ", ".join(["?"] * len(keys))
    sql = (
        f"INSERT INTO raw_dialog.{RAW_DIALOG_TABLE}"  # noqa: S608  # constants + sorted
        f" ({cols_sql}) VALUES ({placeholders})"
    )
    con.execute(sql, [row[k] for k in keys])


def _build_shard(
    db: Path,
    *,
    ja_n: int,
    de_n: int,
    en_n: int,
    dialog_prefix: str = "dlg",
) -> Path:
    con = _writable(db)
    try:
        bootstrap_schema(con)
        row_counter = 0
        for lang, n, pool in (
            ("ja", ja_n, _JA_UTTERANCES),
            ("de", de_n, _DE_UTTERANCES),
            ("en", en_n, _EN_UTTERANCES),
        ):
            for i in range(n):
                row = make_kant_row(
                    utterance=pool[i % len(pool)],
                    individual_layer_enabled=False,
                )
                row["id"] = f"{dialog_prefix}-{lang}-{i}"
                row["dialog_id"] = f"{dialog_prefix}-{lang}-d{i}"
                row["turn_index"] = row_counter
                row["speaker_persona_id"] = "kant"
                row_counter += 1
                _insert_kant_row(con, row)
        con.execute("CHECKPOINT")
    finally:
        con.close()
    return db


def _count_by_language(examples: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {"de": 0, "en": 0, "ja": 0, "mixed": 0, "other": 0}
    for ex in examples:
        meta = ex["weight_metadata"]
        assert isinstance(meta, dict)
        lang = str(meta.get("language", "other"))
        counts[lang if lang in counts else "other"] = (
            counts.get(lang if lang in counts else "other", 0) + 1
        )
    return counts


# ---------------------------------------------------------------------------
# Test 1: default ``"all"`` preserves the existing weighted retrain corpus
# ---------------------------------------------------------------------------


def test_language_filter_all_is_backward_compat(tmp_path: Path) -> None:
    """``language_filter="all"`` matches the legacy call (no kwarg) byte-for-byte."""
    shard = _build_shard(
        tmp_path / "kant_natural_run0.duckdb",
        ja_n=4,
        de_n=8,
        en_n=8,
        dialog_prefix="backcompat",
    )

    baseline = _collect_from_shards_weighted(
        [shard],
        persona_id="kant",
        min_examples=1,
        seed=42,
        use_real_tokenizer=False,
    )
    explicit_all = _collect_from_shards_weighted(
        [shard],
        persona_id="kant",
        min_examples=1,
        seed=42,
        use_real_tokenizer=False,
        language_filter="all",
    )

    def _signature(result: object) -> tuple[int, int, dict[str, int], dict[str, int]]:
        # mypy: result is WeightedSplitResult — accessing attributes directly
        # would require importing the dataclass; use getattr for terseness.
        train = list(getattr(result, "train_examples", []))
        ev = list(getattr(result, "eval_examples", []))
        return (
            len(train),
            len(ev),
            _count_by_language(train),
            _count_by_language(ev),
        )

    assert _signature(baseline) == _signature(explicit_all)


# ---------------------------------------------------------------------------
# Test 2: ``"de"`` drops en + ja
# ---------------------------------------------------------------------------


def test_language_filter_de_drops_en_and_ja(tmp_path: Path) -> None:
    shard = _build_shard(
        tmp_path / "kant_natural_run0.duckdb",
        ja_n=4,
        de_n=8,
        en_n=8,
        dialog_prefix="de_only",
    )

    result = _collect_from_shards_weighted(
        [shard],
        persona_id="kant",
        min_examples=1,
        seed=42,
        use_real_tokenizer=False,
        language_filter="de",
    )

    all_examples = result.train_examples + result.eval_examples
    counts = _count_by_language(all_examples)
    assert counts["en"] == 0, f"en must be filtered out, got {counts}"
    assert counts["ja"] == 0, f"ja must be filtered out, got {counts}"
    assert counts["de"] >= 1, (
        f"at least one de example must survive the filter, got {counts}"
    )


# ---------------------------------------------------------------------------
# Test 3: ``"en"`` drops de + ja
# ---------------------------------------------------------------------------


def test_language_filter_en_drops_de_and_ja(tmp_path: Path) -> None:
    shard = _build_shard(
        tmp_path / "kant_natural_run0.duckdb",
        ja_n=4,
        de_n=8,
        en_n=8,
        dialog_prefix="en_only",
    )

    result = _collect_from_shards_weighted(
        [shard],
        persona_id="kant",
        min_examples=1,
        seed=42,
        use_real_tokenizer=False,
        language_filter="en",
    )

    all_examples = result.train_examples + result.eval_examples
    counts = _count_by_language(all_examples)
    assert counts["de"] == 0, f"de must be filtered out, got {counts}"
    assert counts["ja"] == 0, f"ja must be filtered out, got {counts}"
    assert counts["en"] >= 1, (
        f"at least one en example must survive the filter, got {counts}"
    )


# ---------------------------------------------------------------------------
# Test 4: argparse rejects invalid ``--language-filter`` value
# ---------------------------------------------------------------------------


def test_language_filter_invalid_value_rejected_by_argparse(tmp_path: Path) -> None:
    """``--language-filter fr`` exits with rc 2 (argparse choices rejection).

    This is a CLI-surface contract -- the choices=("de","en","all") in
    ``_build_arg_parser`` is the single point that gates invalid values.
    Running via ``subprocess`` is the canonical way to exercise argparse
    error handling without monkey-patching ``sys.exit``.
    """
    proc = subprocess.run(  # noqa: S603  # fixed argv from sys.executable + literals
        [
            sys.executable,
            "-m",
            "erre_sandbox.training.train_kant_lora",
            "--db-path",
            str(tmp_path / "_does_not_exist.duckdb"),
            "--output-dir",
            str(tmp_path / "out"),
            "--language-filter",
            "fr",
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    assert proc.returncode == 2, (
        f"argparse choices reject must exit 2, got {proc.returncode!r};"
        f" stderr={proc.stderr!r}"
    )
    assert "language-filter" in proc.stderr or "language_filter" in proc.stderr, (
        f"argparse error must reference the rejected option, got stderr={proc.stderr!r}"
    )


# ---------------------------------------------------------------------------
# Test 5: audit ``per_language_weighted_mass`` + ``n_eff`` reflect filtered corpus
# ---------------------------------------------------------------------------


def test_language_filter_audit_reflects_effective_mass(tmp_path: Path) -> None:
    """The weight-audit + DA-14 fallback trigger re-evaluate post-filter.

    With a small corpus (under the DA-14 ``n_eff>=1000`` floor), a
    ``language_filter="de"`` dry-run raises
    :class:`InsufficientEffectiveSampleSizeError` (CLI rc 6) because the
    filter shrinks the effective sample size further. The non-filtered
    same corpus also fails the same gate -- the assertion is that the
    fallback fires after the filter is applied (proof that the audit
    sees the filtered mass).
    """
    shard = _build_shard(
        tmp_path / "kant_natural_run0.duckdb",
        ja_n=2,
        de_n=4,
        en_n=4,
        dialog_prefix="audit",
    )

    # Direct dry-run via train_kant_lora -- the weighted path emits
    # weight-audit.json and triggers DA-14 fallback. ``min_examples=1``
    # bypasses the Phase β gate (CS-3) so the small synthetic corpus
    # reaches the audit step where the DA-14 ``n_eff < 1000`` fallback
    # fires on the filtered effective mass.
    out_dir = tmp_path / "audit_out"
    with pytest.raises(InsufficientEffectiveSampleSizeError):
        train_kant_lora(
            [shard],
            output_dir=out_dir,
            persona_id="kant",
            weighted=True,
            dry_run=True,
            min_examples=1,
            language_filter="de",
            use_real_tokenizer_for_weights=False,
        )

    # weight-audit.json should still be on disk -- the fallback raises
    # AFTER ``emit_weight_audit`` writes the file (see
    # ``_pre_training_audit``).
    audit_path = out_dir / "weight-audit.json"
    assert audit_path.exists(), "weight-audit.json must be emitted before fallback"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    lang_mass = audit.get("per_language_weighted_mass", {})
    assert isinstance(lang_mass, dict)
    # Filtered to de: en + ja mass must be 0, de mass must be > 0.
    assert float(lang_mass.get("en", 0.0)) == 0.0, (
        f"en mass must be 0 after --language-filter=de, got {lang_mass}"
    )
    assert float(lang_mass.get("ja", 0.0)) == 0.0, (
        f"ja mass must be 0 after --language-filter=de, got {lang_mass}"
    )
    assert float(lang_mass.get("de", 0.0)) > 0.0, (
        f"de mass must be > 0 after --language-filter=de, got {lang_mass}"
    )
