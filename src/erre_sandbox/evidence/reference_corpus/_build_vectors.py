"""Deterministic builder for ``vectors.json``.

Run as ``python -m erre_sandbox.evidence.reference_corpus._build_vectors``
once when the raw corpora under ``raw/`` change. The resulting
``vectors.json`` is committed so test runs are reproducible without the
build step (and without the heavy raw-text parsing on every test
collection).

Outputs schema::

    {
      "schema_version": "0.1.0-m9eval",
      "languages": {
        "<lang>": {
          "function_words": [<word>, ...],
          "background_mean": [<float>, ...],
          "background_std":  [<float>, ...],
          "personas": {
            "<persona_id>": {
              "profile_freq": [<float>, ...],
              "n_tokens":     <int|null>
            }
          }
        }
      }
    }

Background statistics (mean / std) are computed across **fixed-size
chunks** pooled across every persona corpus available for the language,
following stylometry chunk-stability practice (Eder 2017). Persona
profiles are computed across the whole persona corpus (single
frequency vector). For the synthetic 4th persona we set
``profile_freq = background_mean`` so it occupies the centre of the
function-word simplex (DB7 LOW-1).

The build is intentionally pure-Python with stdlib only — no numpy
import here, since this script also runs on machines that have not
installed the ``[eval]`` extras.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, pstdev
from typing import Final

from erre_sandbox.evidence.reference_corpus.function_words import (
    FUNCTION_WORDS_DE,
    FUNCTION_WORDS_JA,
)

# M11-C3a: the ja longest-match tokeniser now lives in ``tier_a.burrows`` as
# the single source shared by this builder and the runtime Burrows path
# (``individuation.runner`` feeds it into ``preprocessed_tokens``). Re-exported
# under the historical ``_tokenise_ja`` name so this builder and the QC tests
# keep importing the same function object — a drift-regression test asserts the
# identity (no SudachiPy). ``reference_corpus`` ->
# ``tier_a`` is the same dependency direction the loader already uses.
from erre_sandbox.evidence.tier_a.burrows import tokenise_ja as _tokenise_ja

SCHEMA_VERSION: Final = "0.1.0-m9eval"

# Tokens per chunk for the background-statistics pool. Small enough that
# the toy ja corpus still yields ≥3 chunks (134 chars / 30 ≈ 4 chunks);
# large enough that the de corpus yields a meaningful per-chunk
# frequency (Kant 2.6K words / 500 ≈ 5 chunks; Nietzsche 12K / 500 ≈
# 24 chunks). The ME-6 ≥5K-word stability test uses a separate
# CHUNK_QC_SIZE constant in the test file — these two sizes serve
# different purposes: BACKGROUND_CHUNK_SIZE feeds the build mean/std
# computation, CHUNK_QC_SIZE feeds the post-build Spearman-ρ stability
# diagnostic.
BACKGROUND_CHUNK_DE: Final = 500
BACKGROUND_CHUNK_JA: Final = 30


def _tokenise_de(text: str) -> list[str]:
    """Lower-case whitespace tokeniser for German.

    Mirrors the default tokeniser inside
    :func:`erre_sandbox.evidence.tier_a.burrows.compute_burrows_delta`
    so the build-time profile and the runtime test-text counts use the
    same conventions.
    """
    return [tok.lower() for tok in text.split() if tok]


def _persona_profile_freq(
    tokens: list[str],
    function_words: tuple[str, ...],
) -> list[float]:
    """Relative frequency of each function word in the full token stream."""
    if not tokens:
        return [0.0 for _ in function_words]
    total = len(tokens)
    # We deliberately walk function_words rather than Counter() so the
    # output ordering aligns with the ``function_words`` tuple — the
    # consumer (BurrowsReference) requires positional alignment.
    return [tokens.count(fw) / total for fw in function_words]


def _chunk_frequencies(
    tokens: list[str],
    function_words: tuple[str, ...],
    chunk_size: int,
) -> list[list[float]]:
    """Split tokens into ``chunk_size`` blocks and return per-chunk freq vectors.

    Trailing tokens that don't fill a final chunk are dropped — keeping
    chunk size constant matters more than salvaging a partial chunk
    that would skew the std with a different denominator.
    """
    out: list[list[float]] = []
    for start in range(0, len(tokens) - chunk_size + 1, chunk_size):
        chunk = tokens[start : start + chunk_size]
        out.append(_persona_profile_freq(chunk, function_words))
    return out


def _background_stats(
    pooled_chunks: list[list[float]],
    function_words: tuple[str, ...],
) -> tuple[list[float], list[float]]:
    """Compute per-function-word mean and population std across chunks."""
    n_words = len(function_words)
    if not pooled_chunks:
        return [0.0] * n_words, [0.0] * n_words
    means: list[float] = []
    stds: list[float] = []
    for word_idx in range(n_words):
        column = [chunk[word_idx] for chunk in pooled_chunks]
        means.append(mean(column))
        # pstdev returns 0.0 when len(column) == 1 — that's exactly the
        # signal compute_burrows_delta interprets as "skip this word"
        # (std<=0 path). Population std (divisor=N) is the convention in
        # the stylo R library; compute_burrows_delta only uses std as a
        # divisor so the choice of population vs sample doesn't change
        # ordering.
        stds.append(pstdev(column) if len(column) > 1 else 0.0)
    return means, stds


def build() -> dict[str, object]:
    """Build the vectors dict from the raw corpora and function-word lists."""
    here = Path(__file__).resolve().parent
    raw_dir = here / "raw"

    # --- German ----------------------------------------------------------
    fw_de = FUNCTION_WORDS_DE
    persona_tokens_de: dict[str, list[str]] = {}
    for persona_id, filename in (
        ("kant", "kant_de.txt"),
        ("nietzsche", "nietzsche_de.txt"),
    ):
        text = (raw_dir / filename).read_text(encoding="utf-8")
        persona_tokens_de[persona_id] = _tokenise_de(text)

    pooled_chunks_de: list[list[float]] = []
    for tokens in persona_tokens_de.values():
        pooled_chunks_de.extend(_chunk_frequencies(tokens, fw_de, BACKGROUND_CHUNK_DE))
    bg_mean_de, bg_std_de = _background_stats(pooled_chunks_de, fw_de)

    personas_de: dict[str, dict[str, object]] = {}
    for persona_id, tokens in persona_tokens_de.items():
        personas_de[persona_id] = {
            "profile_freq": _persona_profile_freq(tokens, fw_de),
            "n_tokens": len(tokens),
        }
    personas_de["synthetic_4th"] = {
        "profile_freq": list(bg_mean_de),
        "n_tokens": None,
    }

    # --- Japanese -------------------------------------------------------
    fw_ja = FUNCTION_WORDS_JA
    persona_tokens_ja: dict[str, list[str]] = {}
    rikyu_text = (raw_dir / "rikyu_ja.txt").read_text(encoding="utf-8")
    persona_tokens_ja["rikyu"] = _tokenise_ja(rikyu_text, fw_ja)

    pooled_chunks_ja: list[list[float]] = []
    for tokens in persona_tokens_ja.values():
        pooled_chunks_ja.extend(_chunk_frequencies(tokens, fw_ja, BACKGROUND_CHUNK_JA))
    bg_mean_ja, bg_std_ja = _background_stats(pooled_chunks_ja, fw_ja)

    personas_ja: dict[str, dict[str, object]] = {}
    for persona_id, tokens in persona_tokens_ja.items():
        personas_ja[persona_id] = {
            "profile_freq": _persona_profile_freq(tokens, fw_ja),
            "n_tokens": len(tokens),
        }
    personas_ja["synthetic_4th"] = {
        "profile_freq": list(bg_mean_ja),
        "n_tokens": None,
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "languages": {
            "de": {
                "function_words": list(fw_de),
                "background_mean": bg_mean_de,
                "background_std": bg_std_de,
                "personas": personas_de,
            },
            "ja": {
                "function_words": list(fw_ja),
                "background_mean": bg_mean_ja,
                "background_std": bg_std_ja,
                "personas": personas_ja,
            },
        },
    }


def main() -> None:
    out_path = Path(__file__).resolve().parent / "vectors.json"
    payload = build()
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    languages = payload["languages"]
    assert isinstance(languages, dict)  # build() shape contract
    for data in languages.values():
        assert isinstance(data, dict)
        fws = data["function_words"]
        personas = data["personas"]
        assert isinstance(fws, list)
        assert isinstance(personas, dict)


if __name__ == "__main__":
    main()
