"""``--target-modules`` flag tests (PR-9 Phase 0e / DPN3, γ-lite;
extended in PR-13 Phase 1 / DPN13-1 with constrained MLP profiles).

Pins the CLI surface the γ-lite bundle path (``--target-modules
extended``) needs, plus the PR-13 structural redesign profiles:

* ``--target-modules attention`` (default) maps to q/k/v/o_proj (4
  modules, forensic continuity for v3/v4/v5_rebal_v2/r16_v1).
* ``--target-modules extended`` maps to q/k/v/o + gate/up/down_proj
  (7 modules, Qwen3-8B MLP-included LoRA injection, γ-lite rescue
  FAILURE confirmed in PR-12 DPN12-4).
* ``--target-modules constrained_mlp_gate`` maps to q/k/v/o + gate_proj
  (5 modules, PR-13 Candidate B, structural redesign first step).
* ``--target-modules constrained_mlp_down`` maps to q/k/v/o + down_proj
  (5 modules, PR-13 Candidate C, explicit contingency wiring).
* Invalid choice raises ``SystemExit`` via argparse (rc=2 contract).

Lazy-import discipline is preserved (no peft / torch / transformers
required for argparse-only assertions).
"""

from __future__ import annotations

import argparse

import pytest

from erre_sandbox.training.train_kant_lora import (
    CONSTRAINED_MLP_DOWN_TARGET_MODULES,
    CONSTRAINED_MLP_GATE_TARGET_MODULES,
    DEFAULT_TARGET_MODULES,
    EXTENDED_TARGET_MODULES_QWEN3,
    TARGET_MODULE_PROFILES,
    _build_arg_parser,
    _positive_int,
)


def test_attention_profile_matches_v5_baseline() -> None:
    """``attention`` profile = q/k/v/o_proj (forensic continuity)."""
    assert TARGET_MODULE_PROFILES["attention"] == DEFAULT_TARGET_MODULES
    assert TARGET_MODULE_PROFILES["attention"] == (
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
    )


def test_extended_profile_adds_qwen3_mlp() -> None:
    """``extended`` profile = attention + Qwen3-8B MLP projections."""
    assert TARGET_MODULE_PROFILES["extended"] == EXTENDED_TARGET_MODULES_QWEN3
    assert TARGET_MODULE_PROFILES["extended"] == (
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    )
    # Sanity: extended is a strict superset, not a different set.
    assert set(DEFAULT_TARGET_MODULES).issubset(
        set(EXTENDED_TARGET_MODULES_QWEN3),
    )
    assert len(EXTENDED_TARGET_MODULES_QWEN3) == 7
    assert len(DEFAULT_TARGET_MODULES) == 4


def test_argparse_default_is_attention() -> None:
    """``--target-modules`` defaults to ``attention`` (backward compat)."""
    parser = _build_arg_parser()
    args = parser.parse_args(
        [
            "--duckdb-glob",
            "dummy*.duckdb",
            "--output-dir",
            "out",
        ]
    )
    assert args.target_modules == "attention"
    assert TARGET_MODULE_PROFILES[args.target_modules] == DEFAULT_TARGET_MODULES


def test_argparse_accepts_extended() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args(
        [
            "--duckdb-glob",
            "dummy*.duckdb",
            "--output-dir",
            "out",
            "--target-modules",
            "extended",
        ]
    )
    assert args.target_modules == "extended"
    resolved = TARGET_MODULE_PROFILES[args.target_modules]
    assert resolved == EXTENDED_TARGET_MODULES_QWEN3


def test_argparse_rejects_invalid_choice() -> None:
    """argparse rejects unknown profile names with rc=2 contract."""
    parser = _build_arg_parser()
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(
            [
                "--duckdb-glob",
                "dummy*.duckdb",
                "--output-dir",
                "out",
                "--target-modules",
                "mlp_only",
            ]
        )
    assert excinfo.value.code == 2


# ---------------------------------------------------------------------------
# PR-13 Phase 1 / DPN13-1: constrained MLP profiles (B 採用 + C 明示的 contingency)
#
# Pins the new ``constrained_mlp_gate`` (Candidate B, q/k/v/o + gate_proj)
# and ``constrained_mlp_down`` (Candidate C, q/k/v/o + down_proj) profiles
# added to ``TARGET_MODULE_PROFILES``. The 8 tests below match the unit-test
# checklist in the constrained MLP ADR (`da-XX-constrained-mlp-adapter.md`
# §"Phase 1 unit test 8 件") so any drift between the ADR and the code is
# caught at CI time, not at GPU launch time.
# ---------------------------------------------------------------------------


def test_constrained_mlp_gate_profile_tuple_matches_adr() -> None:
    """Candidate B = q/k/v/o + gate_proj (5 modules, ADR 完全一致、順序固定)."""
    assert TARGET_MODULE_PROFILES["constrained_mlp_gate"] == (
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
    )
    assert (
        TARGET_MODULE_PROFILES["constrained_mlp_gate"]
        == CONSTRAINED_MLP_GATE_TARGET_MODULES
    )
    assert len(CONSTRAINED_MLP_GATE_TARGET_MODULES) == 5


def test_constrained_mlp_down_profile_tuple_matches_adr() -> None:
    """Candidate C = q/k/v/o + down_proj (5 modules, ADR 完全一致、順序固定)."""
    assert TARGET_MODULE_PROFILES["constrained_mlp_down"] == (
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "down_proj",
    )
    assert (
        TARGET_MODULE_PROFILES["constrained_mlp_down"]
        == CONSTRAINED_MLP_DOWN_TARGET_MODULES
    )
    assert len(CONSTRAINED_MLP_DOWN_TARGET_MODULES) == 5


def test_argparse_accepts_constrained_mlp_gate() -> None:
    """``--target-modules constrained_mlp_gate`` parses to Candidate B tuple."""
    parser = _build_arg_parser()
    args = parser.parse_args(
        [
            "--duckdb-glob",
            "dummy*.duckdb",
            "--output-dir",
            "out",
            "--target-modules",
            "constrained_mlp_gate",
        ]
    )
    assert args.target_modules == "constrained_mlp_gate"
    assert (
        TARGET_MODULE_PROFILES[args.target_modules]
        == CONSTRAINED_MLP_GATE_TARGET_MODULES
    )


def test_argparse_accepts_constrained_mlp_down() -> None:
    """``--target-modules constrained_mlp_down`` parses to Candidate C tuple."""
    parser = _build_arg_parser()
    args = parser.parse_args(
        [
            "--duckdb-glob",
            "dummy*.duckdb",
            "--output-dir",
            "out",
            "--target-modules",
            "constrained_mlp_down",
        ]
    )
    assert args.target_modules == "constrained_mlp_down"
    assert (
        TARGET_MODULE_PROFILES[args.target_modules]
        == CONSTRAINED_MLP_DOWN_TARGET_MODULES
    )


def test_argparse_rejects_constrained_mlp_typos() -> None:
    """argparse rejects near-miss profile names (e.g. 'constrained_mlp_xxx')."""
    parser = _build_arg_parser()
    for bad in ("constrained_mlp_xxx", "constrained_mlp", "mlp_gate", "gate"):
        with pytest.raises(SystemExit) as excinfo:
            parser.parse_args(
                [
                    "--duckdb-glob",
                    "dummy*.duckdb",
                    "--output-dir",
                    "out",
                    "--target-modules",
                    bad,
                ]
            )
        assert excinfo.value.code == 2, f"expected rc=2 for {bad!r}"


def test_existing_profiles_unchanged_by_pr13_addition() -> None:
    """``attention`` + ``extended`` profiles are byte-identical to PR-9/PR-12
    state (forensic continuity for the existing 8 verdict shards).

    The constrained MLP profile additions must not perturb the canonical
    tuples that adapter_config.json / train_metadata.json across all
    pre-PR-13 retrains were trained against (q/k/v/o_proj for attention;
    q/k/v/o + gate/up/down_proj for extended).
    """
    assert TARGET_MODULE_PROFILES["attention"] == DEFAULT_TARGET_MODULES
    assert TARGET_MODULE_PROFILES["attention"] == (
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
    )
    assert TARGET_MODULE_PROFILES["extended"] == EXTENDED_TARGET_MODULES_QWEN3
    assert TARGET_MODULE_PROFILES["extended"] == (
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    )
    assert len(TARGET_MODULE_PROFILES["attention"]) == 4
    assert len(TARGET_MODULE_PROFILES["extended"]) == 7


def test_target_module_profiles_keys_match_adr_exactly() -> None:
    """``TARGET_MODULE_PROFILES.keys()`` is the canonical set of 4 profiles.

    DPN13-1 binding: drift between the ADR §"target_modules profile 拡張
    仕様" and the code (e.g., a stray 5th profile sneaking in, or one of
    the four being removed) should fail this test before it can corrupt
    the argparse choices contract.
    """
    assert set(TARGET_MODULE_PROFILES.keys()) == {
        "attention",
        "extended",
        "constrained_mlp_gate",
        "constrained_mlp_down",
    }
    # The argparse ``choices`` builder takes ``sorted(...)`` so the lex order
    # below is exercised by the CLI surface as well.
    assert sorted(TARGET_MODULE_PROFILES.keys()) == [
        "attention",
        "constrained_mlp_down",
        "constrained_mlp_gate",
        "extended",
    ]


def test_constrained_mlp_profiles_do_not_interfere_with_positive_int() -> None:
    """PR-13 profile addition leaves the PR-12 Phase 9b ``_positive_int``
    validator untouched.

    The Codex MEDIUM-2 hardening (ASCII-only digits + 1 <= n <= 4096 upper
    bound) lives on the ``--lora-alpha`` axis. The new constrained MLP
    profiles only add keys to ``TARGET_MODULE_PROFILES``; the
    ``_positive_int`` validator must remain a separate, orthogonal contract
    so the two PR-12/PR-13 surfaces cannot couple regression-wise.
    """
    # Sanity: the validator still rejects all the cases PR-12 pinned.
    for bad in ("0", "-1", "1.5", "+", "１６", "9999999", "abc"):
        with pytest.raises(argparse.ArgumentTypeError):
            _positive_int(bad)
    # Sanity: valid inputs still pass through.
    assert _positive_int("16") == 16
    assert _positive_int("+32") == 32
    assert _positive_int("4096") == 4096
    # Argparse can still consume ``--lora-alpha 16`` together with a new
    # ``--target-modules constrained_mlp_gate`` profile in the same args.
    parser = _build_arg_parser()
    args = parser.parse_args(
        [
            "--duckdb-glob",
            "dummy*.duckdb",
            "--output-dir",
            "out",
            "--target-modules",
            "constrained_mlp_gate",
            "--lora-alpha",
            "32",
        ]
    )
    assert args.target_modules == "constrained_mlp_gate"
    assert args.lora_alpha == 32
