"""CLI + shard-aggregation tests for ``train_kant_lora`` (m9-c-spike Phase K β prep).

Covers four areas the existing gate tests do not:

* Lazy-import discipline — importing
  ``erre_sandbox.training.train_kant_lora`` must NOT pull the
  ``[training]`` extras (peft / transformers / bitsandbytes / datasets /
  accelerate / torch). The CI default install does not have these, and
  ``--dry-run`` must remain runnable in that environment.
* argparse surface — ``--help`` exits with rc 0, the mutually-exclusive
  ``--duckdb-glob`` / ``--db-path`` source group is enforced, and
  missing-required errors land on argparse's standard rc=2 path.
* ``--dry-run`` end-to-end — bootstrap a tiny DuckDB shard, feed it
  through the CLI with ``--dry-run``, and verify the exit code matches
  the gate decision (rc 0 / 2 / 4 for cleared / contamination /
  insufficient). The GPU stack must stay unimported throughout.
* Shard aggregation — ``_collect_from_shards`` must apply the loader-
  level assert per shard yet only enforce the realised-count threshold
  on the aggregate (per-shard counts are usually well below
  ``min_examples``).
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

from erre_sandbox.contracts.eval_paths import RAW_DIALOG_SCHEMA
from erre_sandbox.evidence.eval_store import RAW_DIALOG_TABLE, bootstrap_schema
from tests.test_training.conftest import make_kant_row

_FORBIDDEN_LAZY_MODULES: frozenset[str] = frozenset(
    {"torch", "peft", "transformers", "bitsandbytes", "datasets", "accelerate"},
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
        f"INSERT INTO {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}"  # noqa: S608  # module constants
        f" ({cols_sql}) VALUES ({placeholders})"
    )
    con.execute(sql, [row[k] for k in keys])


def _bootstrap_kant_shard(path: Path, n_clean: int, *, run_id: str) -> None:
    con = _writable(path)
    try:
        bootstrap_schema(con)
        for i in range(n_clean):
            row = make_kant_row(
                utterance=f"Pure reason iteration {i} of run {run_id}",
                individual_layer_enabled=False,
            )
            row["id"] = f"{run_id}-row-{i}"
            row["run_id"] = run_id
            row["turn_index"] = i
            _insert_kant_row(con, row)
        con.execute("CHECKPOINT")
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Lazy import discipline (CS-3 ``[training]``-extras-optional contract)
# ---------------------------------------------------------------------------


def test_module_import_does_not_pull_gpu_stack() -> None:
    """Importing the module must keep the GPU stack out of ``sys.modules``.

    A regression here would mean the gate cannot be exercised on a CI
    install that lacks the ``[training]`` extras — the exact use case
    ``_collect_from_shards`` was designed for (CS-3, the gate runs
    before any peft/transformers symbol is touched).
    """
    # Cache the currently-loaded forbidden modules so we only assert
    # against the *delta* introduced by re-importing the target.
    pre = _FORBIDDEN_LAZY_MODULES & set(sys.modules)
    sys.modules.pop("erre_sandbox.training.train_kant_lora", None)
    importlib.import_module("erre_sandbox.training.train_kant_lora")
    post = _FORBIDDEN_LAZY_MODULES & set(sys.modules)
    new = post - pre
    assert not new, (
        f"importing erre_sandbox.training.train_kant_lora pulled the GPU stack"
        f" eagerly: {sorted(new)}"
    )


# ---------------------------------------------------------------------------
# argparse surface
# ---------------------------------------------------------------------------


def test_cli_help_exits_zero() -> None:
    """``--help`` must exit 0; argparse default behavior."""
    mod = sys.modules.get(
        "erre_sandbox.training.train_kant_lora",
    ) or importlib.import_module("erre_sandbox.training.train_kant_lora")
    with pytest.raises(SystemExit) as excinfo:
        mod.main(["--help"])
    assert excinfo.value.code == 0


def test_cli_missing_required_args_argparse_error() -> None:
    """argparse signals operator error on the standard rc=2 path."""
    mod = sys.modules.get(
        "erre_sandbox.training.train_kant_lora",
    ) or importlib.import_module("erre_sandbox.training.train_kant_lora")
    with pytest.raises(SystemExit) as excinfo:
        mod.main([])
    assert excinfo.value.code == 2


def test_cli_db_path_and_glob_are_mutually_exclusive(tmp_path: Path) -> None:
    """``--db-path`` and ``--duckdb-glob`` must NOT be allowed together.

    argparse exits with rc 2 (its own usage error code) — distinct from
    the CS-3 contamination rc 2 because the run never starts.
    """
    mod = sys.modules.get(
        "erre_sandbox.training.train_kant_lora",
    ) or importlib.import_module("erre_sandbox.training.train_kant_lora")
    with pytest.raises(SystemExit) as excinfo:
        mod.main(
            [
                "--duckdb-glob",
                str(tmp_path / "*.duckdb"),
                "--db-path",
                str(tmp_path / "x.duckdb"),
                "--output-dir",
                str(tmp_path / "out"),
                "--dry-run",
            ],
        )
    assert excinfo.value.code == 2


def test_cli_glob_no_match_returns_rc5(tmp_path: Path) -> None:
    """Empty glob expansion is operator error → rc 5."""
    mod = sys.modules.get(
        "erre_sandbox.training.train_kant_lora",
    ) or importlib.import_module("erre_sandbox.training.train_kant_lora")
    rc = mod.main(
        [
            "--duckdb-glob",
            str(tmp_path / "no_match_*.duckdb"),
            "--output-dir",
            str(tmp_path / "out"),
            "--dry-run",
        ],
    )
    assert rc == 5


# ---------------------------------------------------------------------------
# --dry-run end-to-end (real DuckDB shards, no GPU stack import)
# ---------------------------------------------------------------------------


def test_dry_run_clears_gate_and_returns_rc0(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Bootstrap a single shard with > min_examples clean kant rows.

    Expectations:

    * ``main()`` returns 0.
    * No file is written into ``output_dir`` (dry-run contract).
    * The forbidden GPU modules stay out of ``sys.modules``.
    * A single JSON summary lands on stdout with ``training_executed=False``.
    """
    shard = tmp_path / "kant_dry_run.duckdb"
    _bootstrap_kant_shard(shard, n_clean=5, run_id="dry0")

    pre = _FORBIDDEN_LAZY_MODULES & set(sys.modules)

    mod = sys.modules.get(
        "erre_sandbox.training.train_kant_lora",
    ) or importlib.import_module("erre_sandbox.training.train_kant_lora")
    output_dir = tmp_path / "adapter_out"
    rc = mod.main(
        [
            "--db-path",
            str(shard),
            "--output-dir",
            str(output_dir),
            "--min-examples",
            "3",
            "--dry-run",
        ],
    )
    assert rc == 0
    assert not output_dir.exists(), "dry-run must not create output_dir"

    post = _FORBIDDEN_LAZY_MODULES & set(sys.modules)
    assert post - pre == set(), (
        f"dry-run pulled the GPU stack eagerly: {sorted(post - pre)}"
    )

    captured = capsys.readouterr()
    summary = json.loads(captured.out.strip().splitlines()[-1])
    assert summary["training_executed"] is False
    assert summary["realised_examples"] >= 3
    assert summary["min_examples_threshold"] == 3
    assert summary["db_paths"] == [str(shard)]
    assert summary["shard_stats"][0]["persona_examples"] >= 3


def test_dry_run_insufficient_data_returns_rc4(tmp_path: Path) -> None:
    """Below-threshold shard → :class:`InsufficientTrainingDataError` → rc 4."""
    shard = tmp_path / "kant_thin.duckdb"
    _bootstrap_kant_shard(shard, n_clean=2, run_id="thin0")

    mod = sys.modules.get(
        "erre_sandbox.training.train_kant_lora",
    ) or importlib.import_module("erre_sandbox.training.train_kant_lora")
    rc = mod.main(
        [
            "--db-path",
            str(shard),
            "--output-dir",
            str(tmp_path / "out"),
            "--min-examples",
            "10",
            "--dry-run",
        ],
    )
    assert rc == 4


def test_dry_run_evaluation_phase_row_returns_rc2(tmp_path: Path) -> None:
    """Bootstrap a shard with an ``epoch_phase=evaluation`` row.

    Loader-level aggregate assert (Codex HIGH-2) fires before the gate
    even sees the rows, so the CLI surfaces it as a contamination rc 2.
    """
    shard = tmp_path / "kant_contam.duckdb"
    con = _writable(shard)
    try:
        bootstrap_schema(con)
        contam = make_kant_row(
            utterance="LEAKED EVAL PHASE",
            epoch_phase="evaluation",
            individual_layer_enabled=False,
        )
        contam["id"] = "contam-1"
        _insert_kant_row(con, contam)
        clean = make_kant_row(
            utterance="Clean turn",
            individual_layer_enabled=False,
        )
        clean["id"] = "clean-1"
        clean["turn_index"] = 1
        _insert_kant_row(con, clean)
        con.execute("CHECKPOINT")
    finally:
        con.close()

    mod = sys.modules.get(
        "erre_sandbox.training.train_kant_lora",
    ) or importlib.import_module("erre_sandbox.training.train_kant_lora")
    rc = mod.main(
        [
            "--db-path",
            str(shard),
            "--output-dir",
            str(tmp_path / "out"),
            "--min-examples",
            "1",
            "--dry-run",
        ],
    )
    assert rc == 2


def test_dry_run_quantization_value_error_returns_rc5(tmp_path: Path) -> None:
    """argparse ``choices=`` makes this rc 2, but we keep a direct-call test
    so the :class:`ValueError` branch in ``train_kant_lora`` is exercised.
    """
    mod = sys.modules.get(
        "erre_sandbox.training.train_kant_lora",
    ) or importlib.import_module("erre_sandbox.training.train_kant_lora")
    shard = tmp_path / "kant.duckdb"
    _bootstrap_kant_shard(shard, n_clean=3, run_id="d")
    with pytest.raises(ValueError, match="quantization"):
        mod.train_kant_lora(
            [shard],
            tmp_path / "out",
            quantization="bogus",  # type: ignore[arg-type]
            min_examples=1,
            dry_run=True,
        )


# ---------------------------------------------------------------------------
# Shard aggregation — per-shard load assert + aggregate-threshold gate
# ---------------------------------------------------------------------------


def test_shards_aggregate_above_threshold_pass(tmp_path: Path) -> None:
    """Two thin shards (each below threshold) sum to a passing aggregate.

    Mirrors the production case where Phase B+C natural cells split the
    Kant corpus across five run files; no single file clears
    ``min_examples`` but the union does.
    """
    s1 = tmp_path / "kant_a.duckdb"
    s2 = tmp_path / "kant_b.duckdb"
    _bootstrap_kant_shard(s1, n_clean=3, run_id="a")
    _bootstrap_kant_shard(s2, n_clean=4, run_id="b")

    mod = sys.modules.get(
        "erre_sandbox.training.train_kant_lora",
    ) or importlib.import_module("erre_sandbox.training.train_kant_lora")
    summary = mod.train_kant_lora(
        [s1, s2],
        tmp_path / "out",
        min_examples=5,  # aggregate (7) >= 5 > each-shard (3, 4)
        dry_run=True,
    )
    assert summary.realised_examples == 7
    assert len(summary.shard_stats) == 2
    assert summary.shard_stats[0]["persona_examples"] == 3
    assert summary.shard_stats[1]["persona_examples"] == 4


def test_shards_one_contaminated_fails_at_loader(tmp_path: Path) -> None:
    """A single contaminated shard fails at ``connect_training_view``.

    Loader-level aggregate assert (Codex HIGH-2) runs on each shard
    independently — the clean second shard is never reached because the
    first shard's open raises :class:`EvaluationContaminationError`.
    """
    from erre_sandbox.contracts.eval_paths import EvaluationContaminationError

    s1 = tmp_path / "kant_contam.duckdb"
    s2 = tmp_path / "kant_clean.duckdb"
    con = _writable(s1)
    try:
        bootstrap_schema(con)
        bad = make_kant_row(utterance="LEAK", epoch_phase="evaluation")
        bad["id"] = "bad"
        _insert_kant_row(con, bad)
        con.execute("CHECKPOINT")
    finally:
        con.close()
    _bootstrap_kant_shard(s2, n_clean=5, run_id="ok")

    mod = sys.modules.get(
        "erre_sandbox.training.train_kant_lora",
    ) or importlib.import_module("erre_sandbox.training.train_kant_lora")
    with pytest.raises(EvaluationContaminationError):
        mod.train_kant_lora(
            [s1, s2],
            tmp_path / "out",
            min_examples=1,
            dry_run=True,
        )


def test_train_kant_lora_empty_db_paths_raises(tmp_path: Path) -> None:
    """No paths is a programming error — explicit ``FileNotFoundError``."""
    mod = sys.modules.get(
        "erre_sandbox.training.train_kant_lora",
    ) or importlib.import_module("erre_sandbox.training.train_kant_lora")
    with pytest.raises(FileNotFoundError):
        mod.train_kant_lora(
            [],
            tmp_path / "out",
            dry_run=True,
        )


# ---------------------------------------------------------------------------
# PR-16 DPN16-N (Codex strict review HIGH-1) — programmatic Burrows-aware
# loss guards: CLI ``main()`` 側と同じ 3 invariant が
# ``train_kant_lora()`` の関数頭でも適用されることを確認する。 silent no-op
# を防ぐ。
# ---------------------------------------------------------------------------


def test_train_kant_lora_negative_burrows_lambda_raises(tmp_path: Path) -> None:
    """λ < 0 は直接呼び出しでも ValueError (silent no-op を防ぐ)。"""
    mod = sys.modules.get(
        "erre_sandbox.training.train_kant_lora",
    ) or importlib.import_module("erre_sandbox.training.train_kant_lora")
    shard = tmp_path / "kant.duckdb"
    _bootstrap_kant_shard(shard, n_clean=3, run_id="a")
    with pytest.raises(ValueError, match="non-negative"):
        mod.train_kant_lora(
            [shard],
            tmp_path / "out",
            min_examples=1,
            dry_run=True,
            burrows_aware_loss_lambda=-0.1,
        )


def test_train_kant_lora_positive_burrows_lambda_requires_weighted(
    tmp_path: Path,
) -> None:
    """λ > 0 は ``weighted=True`` を要求する (KL term は WeightedTrainer 専用)。"""
    mod = sys.modules.get(
        "erre_sandbox.training.train_kant_lora",
    ) or importlib.import_module("erre_sandbox.training.train_kant_lora")
    shard = tmp_path / "kant.duckdb"
    _bootstrap_kant_shard(shard, n_clean=3, run_id="b")
    with pytest.raises(ValueError, match="requires weighted=True"):
        mod.train_kant_lora(
            [shard],
            tmp_path / "out",
            min_examples=1,
            dry_run=True,
            weighted=False,
            burrows_aware_loss_lambda=0.3,
        )


def test_train_kant_lora_positive_burrows_lambda_requires_reference_corpus(
    tmp_path: Path,
) -> None:
    """λ > 0 は ``burrows_reference_corpus`` の明示が必須 (silent no-op 回避)。"""
    mod = sys.modules.get(
        "erre_sandbox.training.train_kant_lora",
    ) or importlib.import_module("erre_sandbox.training.train_kant_lora")
    shard = tmp_path / "kant.duckdb"
    _bootstrap_kant_shard(shard, n_clean=3, run_id="c")
    with pytest.raises(ValueError, match="requires burrows_reference_corpus"):
        mod.train_kant_lora(
            [shard],
            tmp_path / "out",
            min_examples=1,
            dry_run=True,
            weighted=True,
            burrows_aware_loss_lambda=0.3,
            burrows_reference_corpus=None,
        )


# ---------------------------------------------------------------------------
# Subprocess smoke — exercises ``python -m`` invocation end-to-end so a
# regression in ``if __name__ == "__main__":`` wiring surfaces here rather
# than at the next overnight session.
# ---------------------------------------------------------------------------


def test_subprocess_help_exits_zero() -> None:
    """``python -m erre_sandbox.training.train_kant_lora --help`` must exit 0."""
    result = subprocess.run(
        [sys.executable, "-m", "erre_sandbox.training.train_kant_lora", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Phase β real Kant LoRA training entry" in result.stdout


# ---------------------------------------------------------------------------
# PR-12 Phase 1-pre: --lora-alpha CLI flag (DPN11-4 / DPN12-1 binding)
# ---------------------------------------------------------------------------
#
# The 5 tests below pin the four ways ``--lora-alpha`` can be used:
#
#   1. explicit value      → ``args.lora_alpha == 32`` (alpha/r=2.0 spelled out)
#   2. omitted             → ``args.lora_alpha is None`` (orchestrator
#                            resolves to ``rank * 2`` — PR-8 DPV8-1 default)
#   3. non-integer         → argparse rc=2 (caught by ``_positive_int``)
#   4. negative integer    → argparse rc=2 (caught by ``_positive_int``)
#   5. zero                → argparse rc=2 (caught by ``_positive_int``)
#
# Pre-registration: these criteria are part of PR-12 Phase 0b ADR binding
# (``da-XX-rescue-success-criteria.md`` references ``lora_alpha`` directly).


def test_lora_alpha_flag_parsed_when_specified() -> None:
    """``--lora-alpha 32`` populates ``args.lora_alpha`` as int 32."""
    mod = importlib.import_module("erre_sandbox.training.train_kant_lora")
    parser = mod._build_arg_parser()
    args = parser.parse_args(
        [
            "--duckdb-glob",
            "x.duckdb",
            "--output-dir",
            "out",
            "--lora-alpha",
            "32",
        ]
    )
    assert args.lora_alpha == 32
    assert isinstance(args.lora_alpha, int)


def test_lora_alpha_default_is_none_for_orchestrator_resolution() -> None:
    """Omitting ``--lora-alpha`` leaves ``args.lora_alpha`` as ``None``.

    The orchestrator (``train_kant_lora``) then resolves it to
    ``lora_rank * 2`` (PR-8 DPV8-1 H1 Pure Continuity default,
    backward-compatible with every wrapper that does not pass the flag).
    """
    mod = importlib.import_module("erre_sandbox.training.train_kant_lora")
    parser = mod._build_arg_parser()
    args = parser.parse_args(
        [
            "--duckdb-glob",
            "x.duckdb",
            "--output-dir",
            "out",
        ]
    )
    assert args.lora_alpha is None


def test_lora_alpha_non_integer_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    """``--lora-alpha abc`` exits rc=2 with argparse-style error.

    Pinning the ``SystemExit`` path keeps the
    ``_positive_int`` validator from drifting to a Python traceback in a
    future refactor. PR-12 Phase 9b (Codex MEDIUM-2): regex now catches
    this before ``int()`` runs, so the message is the ASCII-digit one.
    """
    mod = importlib.import_module("erre_sandbox.training.train_kant_lora")
    parser = mod._build_arg_parser()
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(
            [
                "--duckdb-glob",
                "x.duckdb",
                "--output-dir",
                "out",
                "--lora-alpha",
                "abc",
            ]
        )
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "ASCII decimal digits" in err


def test_lora_alpha_negative_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    """``--lora-alpha -1`` exits rc=2 (strictly positive required).

    PR-12 Phase 9b (Codex MEDIUM-2): the ASCII-digit regex (``^\\+?\\d+$``)
    rejects the leading ``-``, so the message is the regex one rather
    than the post-parse ``strictly positive`` one.
    """
    mod = importlib.import_module("erre_sandbox.training.train_kant_lora")
    parser = mod._build_arg_parser()
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(
            [
                "--duckdb-glob",
                "x.duckdb",
                "--output-dir",
                "out",
                "--lora-alpha",
                "-1",
            ]
        )
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "ASCII decimal digits" in err


def test_lora_alpha_zero_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    """``--lora-alpha 0`` exits rc=2 (zero disables the adapter)."""
    mod = importlib.import_module("erre_sandbox.training.train_kant_lora")
    parser = mod._build_arg_parser()
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(
            [
                "--duckdb-glob",
                "x.duckdb",
                "--output-dir",
                "out",
                "--lora-alpha",
                "0",
            ]
        )
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "strictly positive" in err


# ---------------------------------------------------------------------------
# PR-12 Phase 9b (Codex MEDIUM-2 反映): edge case hardening for ``_positive_int``
# ---------------------------------------------------------------------------
#
# Original 5 tests cover the obvious surface. Codex caught three subtle ways
# the validator was still permissive:
#
#   6. Unicode decimal digits ("１６" = full-width 16) — ``int()`` accepts
#      them, which is a surprising / hard-to-audit CLI experience. ASCII regex
#      now rejects.
#   7. Floats ("1.5") — ``int()`` raises ValueError so the original code
#      caught this, but pinning the error message protects the regex path.
#   8. Excessive value ("99999") — way above any sensible LoRA alpha
#      (HuggingFace examples cap at ~256 in practice). Catches typos /
#      accidental orders-of-magnitude.


def test_lora_alpha_unicode_digit_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    """``--lora-alpha １６`` (full-width Unicode) exits rc=2.

    Plain ``int("１６")`` returns 16 (Python accepts Unicode decimal digits),
    but a CLI flag should be ASCII-only for audit clarity.
    """
    mod = importlib.import_module("erre_sandbox.training.train_kant_lora")
    parser = mod._build_arg_parser()
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(
            [
                "--duckdb-glob",
                "x.duckdb",
                "--output-dir",
                "out",
                "--lora-alpha",
                "１６",  # U+FF11 + U+FF16 = "１６"
            ]
        )
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "ASCII decimal digits" in err


def test_lora_alpha_float_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    """``--lora-alpha 1.5`` exits rc=2 (not a valid integer literal)."""
    mod = importlib.import_module("erre_sandbox.training.train_kant_lora")
    parser = mod._build_arg_parser()
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(
            [
                "--duckdb-glob",
                "x.duckdb",
                "--output-dir",
                "out",
                "--lora-alpha",
                "1.5",
            ]
        )
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "ASCII decimal digits" in err


def test_lora_alpha_excessive_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    """``--lora-alpha 99999`` exits rc=2 (above _LORA_ALPHA_UPPER_BOUND).

    Pins the upper bound so a typo (``--lora-alpha 16000`` vs ``16``) does
    not silently configure a nonsense adapter. Cap (4096) is wide enough
    for any practical setup yet narrow enough to catch obvious errors.
    """
    mod = importlib.import_module("erre_sandbox.training.train_kant_lora")
    parser = mod._build_arg_parser()
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(
            [
                "--duckdb-glob",
                "x.duckdb",
                "--output-dir",
                "out",
                "--lora-alpha",
                "99999",
            ]
        )
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "<= 4096" in err
