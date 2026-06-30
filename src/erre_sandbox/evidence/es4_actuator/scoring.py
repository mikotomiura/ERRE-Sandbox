"""Appropriateness-gated divergent-quality (rarity) scoring for M13-ES4 (§2).

The estimand core (Codex HIGH-2): the primary per-generation quantity is **DQ =
on-task rarity**, the mean rarity of the first-K gate-passing ideas against a
**frozen common-use reference** ``R_object`` — *not* generation-to-generation
spread nor intra-list dispersion (both rise mechanically with temperature). The
reference is temperature-independent, so "the topic just scatters at high temp"
does **not** lift DQ.

Pipeline (``design-final.md`` §2.1):

1. **parse** the response into an idea list (newline / number split, trim, exact
   dedupe).
2. **(c) appropriateness gate** — a degeneracy filter (token length / distinct
   ratio / no n-gram loop) followed by an injectable binary judge
   (:data:`JudgeFn`; the real one is the SGLang qwen3 temp-0 judge, the test one a
   stub). Gate-passing count = ``V`` (fluency).
3. **V / missingness freeze** (selection-bias seal): DQ is the mean rarity over
   the **first-K-valid** ideas (high-V inflation guard), and **V < 2 → DQ = 0**
   (worst value, *not* drop) so a condition cannot lift its mean by dropping its
   low-V generations.

``rarity(idea) = 1 − max_{r∈R_object} cos(emb(idea), emb(r))`` (MPNet encoder via
the injectable :data:`EncoderFn`, reusing ``tier_b/vendi`` in production). Intra-
list dispersion and ``H_proxy`` (char-5gram entropy + zlib) are **supporting /
forensic** outputs the control battery consumes; they never drive DQ. numpy /
stdlib only; LLM is touched only through the seams.
"""

from __future__ import annotations

import math
import re
import zlib
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np

from erre_sandbox.evidence.es4_actuator import constants as _c

EncoderFn = Callable[["Sequence[str]"], np.ndarray]
"""Injectable semantic encoder: texts → ``(N, D)`` embedding matrix (rows not
required to be unit-normalised; :func:`_unit_rows` normalises). Production = MPNet
(``tier_b/vendi``); tests pass a deterministic stub."""

JudgeFn = Callable[[str, str], bool]
"""Injectable appropriateness judge: ``(object, idea) → is a valid on-task use``.
Production = SGLang qwen3 temp-0 binary judge; tests pass a deterministic stub."""

_NUMBER_BULLET_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(?:[-*•]+|\d+[.)])\s*")
_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"[a-z0-9']+")


@dataclass(frozen=True)
class RarityReference:
    """Frozen per-object common-use reference (the scoring input ``R_object``).

    Built by :mod:`reference` (§2.2b) and hash-frozen before any verdict
    generation; scoring consumes it read-only. ``embeddings`` rows align with
    ``texts`` and are unit-normalised.
    """

    object_id: str
    texts: tuple[str, ...]
    embeddings: np.ndarray
    content_hash: str
    fallback_curated_only: bool


# --- parsing + gate -----------------------------------------------------------


def parse_ideas(response: str) -> list[str]:
    """Split a response into an idea list (newline/number split, trim, dedupe)."""
    out: list[str] = []
    seen: set[str] = set()
    for raw_line in response.splitlines():
        line = _NUMBER_BULLET_RE.sub("", raw_line).strip()
        if not line:
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(line)
    return out


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def passes_degeneracy(idea: str) -> bool:
    """Degeneracy filter (§2.1 (c) stage 1): length / distinct-ratio / no loop."""
    toks = _tokens(idea)
    n = len(toks)
    if n < _c.IDEA_MIN_TOK or n > _c.IDEA_MAX_TOK:
        return False
    if len(set(toks)) / n < _c.DISTINCT_TOKEN_RATIO_MIN:
        return False
    if n >= 2 * _c.NGRAM_LOOP_N:
        grams = [
            tuple(toks[i : i + _c.NGRAM_LOOP_N]) for i in range(n - _c.NGRAM_LOOP_N + 1)
        ]
        if len(set(grams)) != len(grams):
            return False
    return True


def valid_ideas(response: str, obj: str, judge_fn: JudgeFn) -> list[str]:
    """Ideas passing the full (c) gate = degeneracy filter ∧ appropriateness judge.

    Exposed for :mod:`reference` (held-out frequency augmentation reuses the exact
    same gate).
    """
    return [
        idea
        for idea in parse_ideas(response)
        if passes_degeneracy(idea) and judge_fn(obj, idea)
    ]


# --- rarity + supporting metrics ----------------------------------------------


def _unit_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.where(norms == 0.0, 1.0, norms)


def rarity(idea_embeddings: np.ndarray, reference_embeddings: np.ndarray) -> np.ndarray:
    """``1 − max_r cos(idea, r)`` per idea (rows of ``idea_embeddings``).

    Both inputs are unit-normalised here, so the cosine is a plain dot product.
    """
    if idea_embeddings.size == 0 or reference_embeddings.size == 0:
        return np.zeros(idea_embeddings.shape[0], dtype=float)
    ideas = _unit_rows(np.asarray(idea_embeddings, dtype=float))
    ref = _unit_rows(np.asarray(reference_embeddings, dtype=float))
    cos = ideas @ ref.T
    return 1.0 - cos.max(axis=1)


def intra_list_dispersion(idea_embeddings: np.ndarray) -> float:
    """Mean pairwise ``1 − cos`` among valid ideas (supporting / forensic)."""
    n = idea_embeddings.shape[0]
    if n < 2:  # noqa: PLR2004 — dispersion needs a pair
        return 0.0
    unit = _unit_rows(np.asarray(idea_embeddings, dtype=float))
    cos = unit @ unit.T
    iu = np.triu_indices(n, k=1)
    return float(np.mean(1.0 - cos[iu]))


def h_proxy(text: str) -> float:
    """Entropy proxy = char-5gram Shannon entropy + (1 − zlib compression ratio).

    The (a2) held-out residual control regresses DQ on this to prove DQ is not an
    entropy re-encoding (§2.3).
    """
    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return 0.0
    if len(cleaned) >= 5:  # noqa: PLR2004 — 5-gram width
        grams = [cleaned[i : i + 5] for i in range(len(cleaned) - 4)]
        counts = Counter(grams)
        total = sum(counts.values())
        entropy = -sum((c / total) * math.log2(c / total) for c in counts.values())
    else:
        entropy = 0.0
    raw = cleaned.encode("utf-8")
    comp = zlib.compress(raw, level=6)
    ratio = len(comp) / len(raw) if raw else 1.0
    return entropy + (1.0 - ratio)


# --- per-generation score -----------------------------------------------------


@dataclass(frozen=True)
class GenerationScore:
    """The per-generation readout the decomposition / controls consume."""

    n_parsed: int
    n_valid: int
    """V (fluency): ideas passing the full (c) gate."""
    empty: bool
    parse_fail: bool
    is_garbage: bool
    dq: float
    """Appropriateness-gated divergent-quality (rarity), first-K-valid mean. 0 if
    V < 2 (worst value, not drop)."""
    dispersion: float
    h_proxy: float


def score_generation(
    response: str,
    obj: str,
    reference: RarityReference,
    encoder_fn: EncoderFn,
    judge_fn: JudgeFn,
) -> GenerationScore:
    """Score one generation (§2.1-§2.2). LLM only via ``encoder_fn`` / ``judge_fn``."""
    empty = response.strip() == ""
    parsed = parse_ideas(response)
    degeneracy_pass = [idea for idea in parsed if passes_degeneracy(idea)]
    valid = [idea for idea in degeneracy_pass if judge_fn(obj, idea)]
    is_garbage = empty or (len(parsed) > 0 and len(degeneracy_pass) == 0)
    parse_fail = (not empty) and len(parsed) == 0

    dq = 0.0
    dispersion = 0.0
    if len(valid) >= _c.MIN_VALID_IDEAS_FOR_DQ:
        first_k = valid[: _c.K_IDEAS]
        idea_emb = np.asarray(encoder_fn(first_k), dtype=float)
        dq = float(np.mean(rarity(idea_emb, reference.embeddings)))
        dispersion = intra_list_dispersion(idea_emb)

    return GenerationScore(
        n_parsed=len(parsed),
        n_valid=len(valid),
        empty=empty,
        parse_fail=parse_fail,
        is_garbage=is_garbage,
        dq=dq,
        dispersion=dispersion,
        h_proxy=h_proxy(response),
    )


__all__ = [
    "EncoderFn",
    "GenerationScore",
    "JudgeFn",
    "RarityReference",
    "h_proxy",
    "intra_list_dispersion",
    "parse_ideas",
    "passes_degeneracy",
    "rarity",
    "score_generation",
    "valid_ideas",
]
