"""DA-18 ADR A6+B2 hybrid (PR-7) — ja stratified downsample + en booster tests.

Covers the new ``--ja-drop-ratio`` / ``--en-booster-source`` / ``--ja-drop-seed``
CLI flags wired into :func:`train_kant_lora` and the kant-only corpus
collection logic in :func:`_collect_from_shards_weighted` (PR-7 prep).
The retrain itself (~3-5h GPU) is gated by the DA18-7 two-stage gate
(Gate 1 source 確定 + Gate 2 dry-run audit PASS) and runs in a separate
session — these tests cover code-prep only.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import duckdb
import pytest

from erre_sandbox.evidence.eval_store import (
    RAW_DIALOG_TABLE,
    bootstrap_schema,
)
from erre_sandbox.training.train_kant_lora import (
    _collect_from_shards_weighted,
    train_kant_lora,
)
from tests.test_training.conftest import make_kant_row

# The submodule has to be imported via importlib because the parent
# package's ``__init__.py`` re-exports the function ``train_kant_lora``
# under the same dotted path, shadowing module attribute access.
_TRAIN_KANT_LORA_MODULE = importlib.import_module(
    "erre_sandbox.training.train_kant_lora",
)

# ---------------------------------------------------------------------------
# DuckDB fixture helpers — synthetic kant corpus with ja / de / en mix.
# ---------------------------------------------------------------------------


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
    speaker_persona_id: str = "kant",
) -> Path:
    """Materialise a synthetic kant shard with the requested per-language counts.

    Each row carries a unique ``dialog_id`` so the group-aware stratified
    split distributes them across the train/eval cells deterministically
    (with the test seed).
    """
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
                utterance = pool[i % len(pool)]
                row = make_kant_row(
                    utterance=utterance,
                    individual_layer_enabled=False,
                )
                row["id"] = f"{dialog_prefix}-{lang}-{i}"
                row["dialog_id"] = f"{dialog_prefix}-{lang}-d{i}"
                row["turn_index"] = row_counter
                row["speaker_persona_id"] = speaker_persona_id
                row_counter += 1
                _insert_kant_row(con, row)
        con.execute("CHECKPOINT")
    finally:
        con.close()
    return db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_ja_drop_ratio_reduces_ja_count_to_target_fraction(
    tmp_path: Path,
) -> None:
    """test 1: ja_drop_ratio=0.1 keeps approximately 10% of ja examples per shard.

    With 10 ja examples per shard, ``round(10 * 0.1) = 1`` survives. Across
    two shards (20 ja total) we expect 2 surviving ja examples.
    Non-ja examples are untouched.
    """
    shard_a = _build_shard(
        tmp_path / "kant_natural_run0.duckdb",
        ja_n=10,
        de_n=4,
        en_n=4,
        dialog_prefix="natural0",
    )
    shard_b = _build_shard(
        tmp_path / "kant_natural_run1.duckdb",
        ja_n=10,
        de_n=4,
        en_n=4,
        dialog_prefix="natural1",
    )

    result = _collect_from_shards_weighted(
        [shard_a, shard_b],
        persona_id="kant",
        min_examples=1,
        seed=42,
        use_real_tokenizer=False,
        ja_drop_ratio=0.1,
        ja_drop_seed=42,
    )

    n_ja_train = sum(
        1 for ex in result.train_examples if ex["weight_metadata"]["language"] == "ja"
    )
    n_ja_eval = sum(
        1 for ex in result.eval_examples if ex["weight_metadata"]["language"] == "ja"
    )
    n_de = sum(
        1
        for ex in result.train_examples + result.eval_examples
        if ex["weight_metadata"]["language"] == "de"
    )
    n_en = sum(
        1
        for ex in result.train_examples + result.eval_examples
        if ex["weight_metadata"]["language"] == "en"
    )

    assert n_ja_train + n_ja_eval == 2, (
        f"Expected 2 ja examples after 0.1 drop (round(10*0.1)*2 shards), "
        f"got train={n_ja_train} + eval={n_ja_eval}"
    )
    assert n_de == 8, f"de count should be untouched (4 per shard × 2 = 8), got {n_de}"
    assert n_en == 8, f"en count should be untouched (4 per shard × 2 = 8), got {n_en}"


def test_ja_drop_seed_is_deterministic(tmp_path: Path) -> None:
    """test 3: ja_drop_seed=42 yields identical surviving ja examples across runs."""
    shard = _build_shard(
        tmp_path / "kant_natural_run0.duckdb",
        ja_n=10,
        de_n=2,
        en_n=2,
        dialog_prefix="seed0",
    )

    def _collect_ja_dialog_ids(ja_drop_seed: int) -> frozenset[str]:
        result = _collect_from_shards_weighted(
            [shard],
            persona_id="kant",
            min_examples=1,
            seed=42,
            use_real_tokenizer=False,
            ja_drop_ratio=0.5,  # keeps 5 of 10, exercising sample non-trivially
            ja_drop_seed=ja_drop_seed,
        )
        all_examples = result.train_examples + result.eval_examples
        return frozenset(
            str(ex["weight_metadata"]["dialog_id"])
            for ex in all_examples
            if ex["weight_metadata"]["language"] == "ja"
        )

    run_a = _collect_ja_dialog_ids(42)
    run_b = _collect_ja_dialog_ids(42)
    run_c = _collect_ja_dialog_ids(99)

    assert run_a == run_b, (
        "Same ja_drop_seed should produce identical ja example sets across runs"
    )
    # dialog_id is unique per row, so set size matches example count exactly
    assert len(run_a) == 5, (
        f"ja_drop_ratio=0.5 should keep 5 of 10 ja, got {len(run_a)}"
    )
    # Different seeds should (with overwhelming probability) yield different sets
    # — 5 of 10 sampled differently. C(10,5)=252 → P(coincide)=1/252≈0.4%.
    assert run_a != run_c, (
        "Different ja_drop_seed should yield different ja example sets "
        "(small false-positive risk ~0.4%, acceptable for unit test)"
    )


def test_persona_non_kant_with_ja_drop_raises_value_error(tmp_path: Path) -> None:
    """test 2a: persona_id='nietzsche' + ja_drop_ratio>0.0 raises ValueError."""
    shard = _build_shard(
        tmp_path / "nietzsche_natural_run0.duckdb",
        ja_n=4,
        de_n=4,
        en_n=4,
        dialog_prefix="ntz0",
        speaker_persona_id="nietzsche",
    )

    with pytest.raises(ValueError, match="kant-only"):
        train_kant_lora(
            [shard],
            output_dir=tmp_path / "out_ntz",
            persona_id="nietzsche",
            weighted=True,
            dry_run=True,
            ja_drop_ratio=0.1,
            use_real_tokenizer_for_weights=False,
        )


def test_persona_non_kant_with_en_booster_raises_value_error(tmp_path: Path) -> None:
    """test 2b: persona_id='rikyu' + en_booster_source!=None raises ValueError."""
    shard = _build_shard(
        tmp_path / "rikyu_natural_run0.duckdb",
        ja_n=4,
        de_n=4,
        en_n=4,
        dialog_prefix="rky0",
        speaker_persona_id="rikyu",
    )
    booster = _build_shard(
        tmp_path / "en_booster.duckdb",
        ja_n=0,
        de_n=0,
        en_n=4,
        dialog_prefix="boost",
        speaker_persona_id="kant",
    )

    with pytest.raises(ValueError, match="kant-only"):
        train_kant_lora(
            [shard],
            output_dir=tmp_path / "out_rky",
            persona_id="rikyu",
            weighted=True,
            dry_run=True,
            en_booster_source=booster,
            use_real_tokenizer_for_weights=False,
        )


def test_en_booster_appends_en_examples_and_filters_non_kant(tmp_path: Path) -> None:
    """test 4: en booster source loads, persona-filters, and language-filters.

    The booster source contains a mix of personas; only kant rows that are
    classified as English should be appended to base_train. The eval set
    remains bound to the primary shards (DP7-2 binding).
    """
    primary = _build_shard(
        tmp_path / "kant_natural_run0.duckdb",
        ja_n=2,
        de_n=4,
        en_n=4,
        dialog_prefix="primary",
    )
    # Booster shard: 6 kant en + 3 kant ja (should drop ja, keep en)
    # Plus a few non-kant rows that build_weighted_examples must filter.
    booster_path = tmp_path / "kant_en_booster.duckdb"
    con = _writable(booster_path)
    try:
        bootstrap_schema(con)
        row_counter = 0
        for i, utterance in enumerate(_EN_UTTERANCES):
            row = make_kant_row(utterance=utterance, individual_layer_enabled=False)
            row["id"] = f"boost-en-{i}"
            row["dialog_id"] = f"boost-en-d{i}"
            row["turn_index"] = row_counter
            row_counter += 1
            _insert_kant_row(con, row)
        # Booster ja rows — should be language-filtered out
        for i, utterance in enumerate(_JA_UTTERANCES[:3]):
            row = make_kant_row(utterance=utterance, individual_layer_enabled=False)
            row["id"] = f"boost-ja-{i}"
            row["dialog_id"] = f"boost-ja-d{i}"
            row["turn_index"] = row_counter
            row_counter += 1
            _insert_kant_row(con, row)
        # Cross-persona rows — should be persona-filtered out by build_weighted_examples
        for i, utterance in enumerate(_EN_UTTERANCES[:3]):
            row = make_kant_row(utterance=utterance, individual_layer_enabled=False)
            row["id"] = f"boost-ntz-{i}"
            row["dialog_id"] = f"boost-ntz-d{i}"
            row["turn_index"] = row_counter
            row["speaker_persona_id"] = "nietzsche"
            row_counter += 1
            _insert_kant_row(con, row)
        con.execute("CHECKPOINT")
    finally:
        con.close()

    result = _collect_from_shards_weighted(
        [primary],
        persona_id="kant",
        min_examples=1,
        seed=42,
        use_real_tokenizer=False,
        en_booster_source=booster_path,
    )

    booster_basename = booster_path.name
    booster_in_train = [
        ex
        for ex in result.train_examples
        if ex["weight_metadata"]["source_shard"] == booster_basename
    ]
    booster_in_eval = [
        ex
        for ex in result.eval_examples
        if ex["weight_metadata"]["source_shard"] == booster_basename
    ]

    # All 6 booster en examples should land in training (DP7-2: train-only)
    assert len(booster_in_train) == 6, (
        f"Expected 6 booster en examples in train, got {len(booster_in_train)}"
    )
    # No booster examples should land in eval (DP7-2: eval stays bound to v3/v4/v5)
    assert len(booster_in_eval) == 0, (
        f"DP7-2: booster must not contaminate eval, got "
        f"{len(booster_in_eval)} booster rows in eval"
    )
    # All booster examples must be kant (persona filter) and en (language filter)
    for ex in booster_in_train:
        metadata = ex["weight_metadata"]
        assert metadata["language"] == "en", (
            f"Booster example must be en, got {metadata['language']!r}"
        )


def test_no_op_when_default_kwargs(tmp_path: Path) -> None:
    """test 5 (regression): default ``ja_drop_ratio=0.0 + en_booster_source=None``
    produces output identical to omitting the kwargs entirely.

    Codex review LOW-2 (PR-7 prep, 2026-05-18) 反映: strengthen the
    no-op invariant by comparing full ``train_examples`` / ``eval_examples``
    dicts (text + sample_weight + weight_metadata) AND key audit fields
    (n_train / n_eval / synthetic_monolog_n / da18_hybrid absence), not
    just sorted text. nietzsche / rikyu / existing kant Plan B paths must
    see zero behaviour change when the new flags are at their defaults.
    """
    shard = _build_shard(
        tmp_path / "kant_natural_run0.duckdb",
        ja_n=6,
        de_n=4,
        en_n=4,
        dialog_prefix="noop",
    )

    baseline = _collect_from_shards_weighted(
        [shard],
        persona_id="kant",
        min_examples=1,
        seed=42,
        use_real_tokenizer=False,
    )
    with_default_flags = _collect_from_shards_weighted(
        [shard],
        persona_id="kant",
        min_examples=1,
        seed=42,
        use_real_tokenizer=False,
        ja_drop_ratio=0.0,
        en_booster_source=None,
        ja_drop_seed=42,
    )

    # Full structural identity (order-preserving): the random selections
    # used by the group-aware split and synthetic monolog code paths are
    # seeded deterministically, so two no-op invocations must produce
    # byte-identical Python lists.
    assert baseline.train_examples == with_default_flags.train_examples, (
        "Default kwargs must produce structurally identical train_examples "
        "(no-op invariant: text + sample_weight + weight_metadata all match)"
    )
    assert baseline.eval_examples == with_default_flags.eval_examples, (
        "Default kwargs must produce structurally identical eval_examples "
        "(no-op invariant)"
    )
    assert baseline.realised_examples == with_default_flags.realised_examples
    assert baseline.synthetic_monolog_n == with_default_flags.synthetic_monolog_n
    assert baseline.train_dialog_ids == with_default_flags.train_dialog_ids
    assert baseline.eval_dialog_ids == with_default_flags.eval_dialog_ids

    # Audit identity on key fields. ``metadata`` (list of weight_metadata)
    # and ``weights`` track train_examples 1:1, so equality on those carry
    # through.
    for key in ("n_train", "n_eval", "synthetic_monolog_n", "weights", "metadata"):
        assert baseline.audit.get(key) == with_default_flags.audit.get(key), (
            f"audit[{key!r}] must be identical under no-op invariant"
        )
    # MEDIUM-2: with default kwargs, the da18_hybrid block must NOT be
    # emitted (its presence would imply the DA-18 path was exercised).
    assert "da18_hybrid" not in baseline.audit
    assert "da18_hybrid" not in with_default_flags.audit


def test_da18_hybrid_audit_block_persists_provenance(tmp_path: Path) -> None:
    """Codex MEDIUM-2 (PR-7 prep, 2026-05-18): when DA-18 flags are
    exercised, ``audit["da18_hybrid"]`` carries the transform inputs and
    post-filter counts (DA18-7 Gate 1 provenance binding).
    """
    shard = _build_shard(
        tmp_path / "kant_natural_run0.duckdb",
        ja_n=10,
        de_n=4,
        en_n=4,
        dialog_prefix="audit",
    )
    booster = _build_shard(
        tmp_path / "kant_en_booster.duckdb",
        ja_n=0,
        de_n=0,
        en_n=4,
        dialog_prefix="bst",
    )

    result = _collect_from_shards_weighted(
        [shard],
        persona_id="kant",
        min_examples=1,
        seed=42,
        use_real_tokenizer=False,
        ja_drop_ratio=0.1,
        en_booster_source=booster,
        ja_drop_seed=42,
    )

    da18 = result.audit.get("da18_hybrid")
    assert isinstance(da18, dict), "da18_hybrid block must be present and a dict"
    assert da18["ja_drop_ratio"] == 0.1
    assert da18["ja_drop_seed"] == 42
    assert da18["ja_pre_drop_count"] == 10
    # round(10 * 0.1) = 1 surviving ja
    assert da18["ja_post_drop_count"] == 1
    assert da18["en_booster_source"] == str(booster)
    # booster shard has 4 kant en rows total → kant_count=4, en_kept=4
    assert da18["en_booster_rows_total"] == 4
    assert da18["en_booster_kant_count"] == 4
    assert da18["en_booster_en_kept"] == 4


def test_weighted_false_with_hybrid_flag_raises_value_error(tmp_path: Path) -> None:
    """Codex MEDIUM-1 (PR-7 prep, 2026-05-18): hybrid flags require
    ``weighted=True`` -- otherwise execution falls through to
    ``_collect_from_shards`` (non-weighted K-β path) and the new flags
    become a silent no-op. Reject the misuse at the entry point.
    """
    shard = _build_shard(
        tmp_path / "kant_natural_run0.duckdb",
        ja_n=4,
        de_n=4,
        en_n=4,
        dialog_prefix="wflag",
    )

    with pytest.raises(ValueError, match=r"require --weighted"):
        train_kant_lora(
            [shard],
            output_dir=tmp_path / "out_wflag_ja",
            persona_id="kant",
            weighted=False,  # explicit: hybrid flag must reject here
            dry_run=True,
            ja_drop_ratio=0.1,
            use_real_tokenizer_for_weights=False,
        )


def test_weighted_false_with_booster_raises_value_error(tmp_path: Path) -> None:
    """Codex MEDIUM-1 (PR-7 prep, 2026-05-18): same misuse path for
    ``en_booster_source``.
    """
    shard = _build_shard(
        tmp_path / "kant_natural_run0.duckdb",
        ja_n=4,
        de_n=4,
        en_n=4,
        dialog_prefix="wbst",
    )
    booster = _build_shard(
        tmp_path / "booster.duckdb",
        ja_n=0,
        de_n=0,
        en_n=4,
        dialog_prefix="wbst_b",
    )

    with pytest.raises(ValueError, match=r"require --weighted"):
        train_kant_lora(
            [shard],
            output_dir=tmp_path / "out_wflag_bst",
            persona_id="kant",
            weighted=False,
            dry_run=True,
            en_booster_source=booster,
            use_real_tokenizer_for_weights=False,
        )


def test_missing_en_booster_source_raises_file_not_found(tmp_path: Path) -> None:
    """Codex LOW-1 (PR-7 prep, 2026-05-18): missing booster path must
    raise ``FileNotFoundError`` (CLI rc=5 operator error) instead of an
    opaque DuckDB exception.
    """
    shard = _build_shard(
        tmp_path / "kant_natural_run0.duckdb",
        ja_n=2,
        de_n=2,
        en_n=2,
        dialog_prefix="missbst",
    )
    missing = tmp_path / "this_booster_does_not_exist.duckdb"

    with pytest.raises(FileNotFoundError, match=r"en_booster_source not found"):
        train_kant_lora(
            [shard],
            output_dir=tmp_path / "out_missbst",
            persona_id="kant",
            weighted=True,
            dry_run=True,
            min_examples=1,  # synthetic shard has only 6 examples
            en_booster_source=missing,
            use_real_tokenizer_for_weights=False,
        )


def test_ja_drop_ratio_out_of_range_raises_value_error(tmp_path: Path) -> None:
    """test 6 (defensive): ja_drop_ratio outside [0.0, 1.0] raises ValueError."""
    shard = _build_shard(
        tmp_path / "kant_natural_run0.duckdb",
        ja_n=2,
        de_n=2,
        en_n=2,
        dialog_prefix="bounds",
    )

    with pytest.raises(ValueError, match=r"ja_drop_ratio must be in \[0.0, 1.0\]"):
        train_kant_lora(
            [shard],
            output_dir=tmp_path / "out_bounds",
            persona_id="kant",
            weighted=True,
            dry_run=True,
            ja_drop_ratio=1.5,
            use_real_tokenizer_for_weights=False,
        )


def test_dry_run_persists_da18_hybrid_to_weight_audit_and_train_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEP1-3 fix (PR-7 follow-up, 2026-05-18): end-to-end persistence test.

    ``train_kant_lora(..., weighted=True, dry_run=True, ja_drop_ratio=0.05)``
    must produce:

    1. ``weight-audit.json`` on disk containing a populated ``da18_hybrid``
       block (forwarded via the new ``emit_weight_audit(extra=...)`` kwarg).
    2. A returned ``TrainRunSummary`` whose ``metadata["da18_hybrid"]`` is
       non-null with the same provenance content — this is exactly the
       payload that ``summary.to_dict()`` would write to
       ``train_metadata.json`` post-training, so verifying the summary in
       dry-run is equivalent to verifying the train_metadata.json that
       the next-session retrain will materialise.

    DA18-7 Gate 1 provenance binding (the ``train_metadata.json`` field
    ``en_booster_source`` must be persisted) is satisfied when this test
    passes.

    Note: ``DA14_N_EFF_FALLBACK_TRIGGER`` is monkeypatched down so the
    audit threshold does not abort the synthetic-shard run. Production
    threshold (1000) is unchanged; the real-corpus retrain still
    enforces the DA-14 invariant end-to-end.
    """
    monkeypatch.setattr(
        _TRAIN_KANT_LORA_MODULE,
        "DA14_N_EFF_FALLBACK_TRIGGER",
        1.0,
    )
    shard = _build_shard(
        tmp_path / "kant_natural_run0.duckdb",
        ja_n=10,
        de_n=8,
        en_n=8,
        dialog_prefix="persist",
    )
    output_dir = tmp_path / "out_persist"

    summary = train_kant_lora(
        [shard],
        output_dir=output_dir,
        persona_id="kant",
        weighted=True,
        dry_run=True,
        min_examples=1,  # synthetic shard has 26 examples (10+8+8)
        ja_drop_ratio=0.05,  # canonical PR-7 retrain ratio (DEP1-2 PASS)
        ja_drop_seed=42,
        use_real_tokenizer_for_weights=False,
    )

    # 1) weight-audit.json on disk contains da18_hybrid.
    audit_path = output_dir / "weight-audit.json"
    assert audit_path.exists(), "weight-audit.json must be written in dry-run"
    on_disk_audit = json.loads(audit_path.read_text(encoding="utf-8"))
    da18_on_disk = on_disk_audit.get("da18_hybrid")
    assert isinstance(da18_on_disk, dict), (
        "weight-audit.json must contain a populated da18_hybrid block "
        "(DEP1-3 fix: forwarded via emit_weight_audit(extra=...))"
    )
    assert da18_on_disk["ja_drop_ratio"] == 0.05
    assert da18_on_disk["ja_drop_seed"] == 42
    assert isinstance(da18_on_disk["ja_pre_drop_count"], int)
    assert isinstance(da18_on_disk["ja_post_drop_count"], int)
    # A6 単独 path (no en booster): provenance fields are null/zero.
    assert da18_on_disk["en_booster_source"] is None
    assert da18_on_disk["en_booster_rows_total"] == 0
    assert da18_on_disk["en_booster_kant_count"] == 0
    assert da18_on_disk["en_booster_en_kept"] == 0

    # 2) TrainRunSummary metadata.da18_hybrid is non-null and matches the
    # on-disk audit. ``summary.to_dict()`` is what writes train_metadata.json
    # post-training (train_kant_lora.py:1860/2151), so equality here means
    # the next-session retrain's train_metadata.json will also be populated.
    da18_in_summary = summary.metadata.get("da18_hybrid")
    assert isinstance(da18_in_summary, dict), (
        "TrainRunSummary.metadata['da18_hybrid'] must be non-null "
        "(DEP1-3 fix: _run_weighted_path forwards audit.get('da18_hybrid'))"
    )
    assert da18_in_summary == da18_on_disk, (
        "summary metadata and on-disk weight-audit.json must carry "
        "identical da18_hybrid provenance (forensic-replay invariant)"
    )

    # 3) summary.to_dict() (the JSON that would be written to
    # train_metadata.json) round-trips with da18_hybrid intact.
    summary_dict = summary.to_dict()
    assert summary_dict["metadata"]["da18_hybrid"] == da18_on_disk


def test_dry_run_default_kwargs_omits_da18_hybrid_from_weight_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEP1-3 no-op invariant: when the DA-18 path is NOT exercised,
    ``weight-audit.json`` must not contain ``da18_hybrid``.

    Protects existing v3/v4/v5_rebal_v1 retrain shapes and nietzsche /
    rikyu paths from leaking provenance fields they never set.
    """
    monkeypatch.setattr(
        _TRAIN_KANT_LORA_MODULE,
        "DA14_N_EFF_FALLBACK_TRIGGER",
        1.0,
    )
    shard = _build_shard(
        tmp_path / "kant_natural_run0.duckdb",
        ja_n=6,
        de_n=4,
        en_n=4,
        dialog_prefix="noopdry",
    )
    output_dir = tmp_path / "out_noop_persist"

    summary = train_kant_lora(
        [shard],
        output_dir=output_dir,
        persona_id="kant",
        weighted=True,
        dry_run=True,
        min_examples=1,  # synthetic shard has 14 examples (6+4+4)
        use_real_tokenizer_for_weights=False,
        # Note: NO ja_drop_ratio / en_booster_source kwargs (defaults apply).
    )

    audit_path = output_dir / "weight-audit.json"
    assert audit_path.exists()
    on_disk_audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert "da18_hybrid" not in on_disk_audit, (
        "default no-op path must not leak da18_hybrid into weight-audit.json"
    )
    assert summary.metadata.get("da18_hybrid") is None, (
        "default no-op path must leave summary.metadata.da18_hybrid as None"
    )
