"""CLI smoke tests for ``scripts/m9-c-adopt/rescore_vendi_alt_kernel.py``.

Plan B verdict prep (`.steering/20260516-m9-c-adopt-plan-b-eval-gen/
design.md` §1.2) extended the script with ``--v2-shards`` / ``--nolora-shards``
/ ``--kernel-type`` / ``--allowlist-path`` flags so the same code path can
score the Plan B kant_r8v3 retrain artifact and the Plan B no-LoRA control
shards (blocker 2 of the prep PR — hard-coded shard paths). These tests pin
the new CLI surface without requiring sentence-transformers or sklearn at
collection time.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "m9-c-adopt" / "rescore_vendi_alt_kernel.py"


@pytest.fixture(scope="module")
def rescore_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "rescore_vendi_alt_kernel",
        _SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["rescore_vendi_alt_kernel"] = module
    spec.loader.exec_module(module)
    return module


def _build_parser(rescore_module: Any) -> Any:
    """Reconstruct the argparse parser without executing ``main``.

    ``main`` is one ~250-line function so the parser is rebuilt here by
    re-running the ``argparse`` block via a lightweight re-import trick:
    we monkeypatch ``argparse.ArgumentParser.parse_args`` to return the
    parsed Namespace and stop main's first side effect (``logging.
    basicConfig``).
    """
    raise NotImplementedError  # see direct parse_known_args() instead below


def _parse(rescore_module: Any, argv: list[str]) -> Any:
    """Run argparse only by invoking main() under a guard that aborts
    immediately after CLI parsing.

    The script's main() loads DuckDB shards right after ``parse_args``;
    we trigger that and capture the SystemExit from the shard-load failure
    while returning the parsed namespace via a sentinel exception.
    """

    class _CapturedArgs(BaseException):
        def __init__(self, ns: Any) -> None:
            self.ns = ns

    import argparse

    real_parse_args = argparse.ArgumentParser.parse_args

    def _capture(self: argparse.ArgumentParser, args: list[str] | None = None) -> Any:
        ns = real_parse_args(self, args)
        raise _CapturedArgs(ns)

    argparse.ArgumentParser.parse_args = _capture  # type: ignore[method-assign]
    try:
        try:
            rescore_module.main(argv)
        except _CapturedArgs as captured:
            return captured.ns
        raise AssertionError("parser did not raise _CapturedArgs")
    finally:
        argparse.ArgumentParser.parse_args = real_parse_args  # type: ignore[method-assign]


# ----- CLI parsing & validation tests -----


def test_default_shards_back_compat(rescore_module: Any) -> None:
    """No --v2-shards/--nolora-shards flags → existing Plan A defaults."""
    ns = _parse(
        rescore_module,
        [
            "--encoder",
            "sentence-transformers/all-mpnet-base-v2",
            "--output",
            "output.json",
        ],
    )
    assert list(ns.v2_shards) == list(rescore_module._V2_SHARDS)
    assert list(ns.nolora_shards) == list(rescore_module._NOLORA_SHARDS)
    assert ns.kernel_type == "semantic"
    assert ns.allowlist_path == rescore_module._D2_ALLOWLIST_PATH


def test_custom_shards_override_defaults(rescore_module: Any) -> None:
    """Custom shard paths replace the Plan A constants."""
    ns = _parse(
        rescore_module,
        [
            "--encoder",
            "sentence-transformers/all-mpnet-base-v2",
            "--output",
            "output.json",
            "--v2-shards",
            "data/eval/a.duckdb",
            "data/eval/b.duckdb",
            "--nolora-shards",
            "data/eval/c.duckdb",
        ],
    )
    assert ns.v2_shards == [Path("data/eval/a.duckdb"), Path("data/eval/b.duckdb")]
    assert ns.nolora_shards == [Path("data/eval/c.duckdb")]


def test_kernel_type_lexical_5gram_defaults_encoder(rescore_module: Any) -> None:
    """--kernel-type lexical_5gram + no --encoder → encoder defaults to
    the lexical_5gram allowlist key (post _resolve_encoder_default)."""
    ns = _parse(
        rescore_module,
        [
            "--kernel-type",
            "lexical_5gram",
            "--output",
            "output.json",
            "--v2-shards",
            "data/eval/a.duckdb",
            "--nolora-shards",
            "data/eval/b.duckdb",
            "--allowlist-path",
            ".steering/20260517-m9-c-adopt-plan-b-design/d2-encoder-allowlist-plan-b.json",
        ],
    )
    assert ns.kernel_type == "lexical_5gram"
    assert ns.encoder is None  # raw parse, before _resolve_encoder_default
    rescore_module._resolve_encoder_default(ns)
    assert ns.encoder == rescore_module._LEXICAL_5GRAM_ENCODER_KEY


def test_kernel_type_lexical_5gram_rejects_wrong_encoder(
    rescore_module: Any,
) -> None:
    """--kernel-type lexical_5gram + --encoder=foo → SystemExit on
    _resolve_encoder_default."""
    ns = _parse(
        rescore_module,
        [
            "--kernel-type",
            "lexical_5gram",
            "--encoder",
            "sentence-transformers/all-mpnet-base-v2",
            "--output",
            "output.json",
            "--v2-shards",
            "data/eval/a.duckdb",
            "--nolora-shards",
            "data/eval/b.duckdb",
        ],
    )
    with pytest.raises(SystemExit, match="lexical_5gram"):
        rescore_module._resolve_encoder_default(ns)


def test_kernel_type_semantic_requires_encoder(rescore_module: Any) -> None:
    """--kernel-type semantic + no --encoder → SystemExit on
    _resolve_encoder_default."""
    ns = _parse(
        rescore_module,
        [
            "--output",
            "output.json",
            "--v2-shards",
            "data/eval/a.duckdb",
            "--nolora-shards",
            "data/eval/b.duckdb",
        ],
    )
    with pytest.raises(SystemExit, match="required"):
        rescore_module._resolve_encoder_default(ns)


def test_kernel_type_invalid_choice_rejected(rescore_module: Any) -> None:
    """argparse choices=() guard catches unknown kernel families."""
    with pytest.raises(SystemExit):
        _parse(
            rescore_module,
            [
                "--encoder",
                "x",
                "--output",
                "output.json",
                "--kernel-type",
                "byte_pair_v1",
            ],
        )


# ----- lexical_5gram pool-fit semantics -----


def test_encode_pools_lexical_5gram_returns_unit_normed_matrices(
    rescore_module: Any,
) -> None:
    """``_encode_pools_lexical_5gram`` returns L2-normed dense matrices
    sized to the per-condition input counts. Each row's norm must be 1.0
    (within numerical tolerance) so the downstream ``unit @ unit.T``
    cosine recovery works exactly the same as the semantic path."""
    pytest.importorskip("sklearn")
    v2_texts = [
        "alpha bravo charlie delta echo",
        "alpha bravo charlie delta foxtrot",
    ]
    nolora_texts = [
        "zulu yankee whiskey victor uniform",
    ]
    v2_unit, nolora_unit = rescore_module._encode_pools_lexical_5gram(
        v2_texts,
        nolora_texts,
    )
    assert v2_unit.shape[0] == len(v2_texts)
    assert nolora_unit.shape[0] == len(nolora_texts)
    assert v2_unit.shape[1] == nolora_unit.shape[1]  # shared TF-IDF vocab
    v2_norms = np.linalg.norm(v2_unit, axis=1)
    nolora_norms = np.linalg.norm(nolora_unit, axis=1)
    assert np.allclose(v2_norms, 1.0, atol=1e-9)
    assert np.allclose(nolora_norms, 1.0, atol=1e-9)


def test_encode_pools_lexical_5gram_pool_fit_vs_per_window_fit(
    rescore_module: Any,
) -> None:
    """Pool-fit IDF and per-window-fit IDF give different cosine values
    because TF-IDF reweights by document frequency over the corpus seen
    at ``fit_transform`` time. DE-1 documents that the rescore design
    intentionally uses pool-fit (apples-to-apples IDF) and is not
    numerically equivalent to ``make_tfidf_5gram_cosine_kernel`` invoked
    per resample window."""
    pytest.importorskip("sklearn")
    from erre_sandbox.evidence.tier_b.vendi_lexical_5gram import (
        make_tfidf_5gram_cosine_kernel,
    )

    v2_texts = [
        "alpha bravo charlie delta echo",
        "alpha bravo charlie delta foxtrot",
    ]
    nolora_texts = [
        "alpha bravo charlie delta november",
    ]
    v2_unit, _ = rescore_module._encode_pools_lexical_5gram(
        v2_texts,
        nolora_texts,
    )
    pool_fit_cosine = float((v2_unit[0] @ v2_unit[1]).item())

    window_kernel = make_tfidf_5gram_cosine_kernel()
    per_window_matrix = window_kernel(v2_texts)
    per_window_cosine = float(per_window_matrix[0, 1])

    # Both are in [0, 1] (TF-IDF non-negative), diagonal=1, but the
    # off-diagonal differs because pool-fit IDF saw an extra document.
    assert 0.0 <= pool_fit_cosine <= 1.0
    assert 0.0 <= per_window_cosine <= 1.0
    assert pool_fit_cosine != pytest.approx(per_window_cosine, abs=1e-6)
