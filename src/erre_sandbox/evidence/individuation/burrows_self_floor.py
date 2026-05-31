"""M10-A S2 (E4): Burrows within-individual self-floor diagnostic (CPU only).

reactivate ADR §3.E ⑦ — measure how far **self-subsamples** of one persona's
own corpus drift from that persona's committed Burrows reference, to judge
whether the frozen ``BURROWS_DELTA_MAX = 4.0`` base-retention threshold is even
reachable (the forensic finding: every individual sat at delta 9–12, suggesting
4.0 is below the intrinsic noise floor for the tiny rikyu reference).

**This is a calibration input, NOT a verdict** (Codex CX6): it computes no
confidence interval, makes no GO/NO-GO decision, and does **not** rewrite the
frozen ``BURROWS_DELTA_MAX`` (a new Δ_self_max, if ever adopted, is a separate
superseding ADR). The frozen value is *read* (from the frozen ``c3b_verdict``)
only to report whether 4.0 falls inside the observed self-delta band.

Statistical limitations are deliberately surfaced in the result (CX6): the
reference / background statistics were built from the **same** 5-poem corpus the
subsamples are drawn from, so this is *not* an independent split-half
reliability; the odd/even split is imbalanced (3 vs 2 poems) and the
leave-one-out jackknife points are mutually dependent. With ~134 characters the
function-word counts are sparse, which inflates every delta.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

from erre_sandbox.evidence import reference_corpus
from erre_sandbox.evidence.individuation.c3b_verdict import BURROWS_DELTA_MAX
from erre_sandbox.evidence.reference_corpus.loader import (
    get_provenance_entries,
    load_reference,
)
from erre_sandbox.evidence.tier_a.burrows import compute_burrows_delta, tokenise_ja

if TYPE_CHECKING:
    from erre_sandbox.evidence.tier_a.burrows import BurrowsReference

_REFERENCE_CORPUS_DIR: Final[Path] = Path(reference_corpus.__file__).resolve().parent

_LIMITATION: Final[str] = (
    "Not an independent split-half reliability: the reference / background"
    " statistics were built from the same corpus the subsamples are drawn from."
    " The odd/even split is imbalanced (even=poems[0::2], odd=poems[1::2]) and the"
    " leave-one-out jackknife points are mutually dependent. The ~134-character"
    " corpus makes function-word counts sparse, inflating every delta. Use only as"
    " a calibration input: no CI, no GO/NO-GO, no threshold update."
)


@dataclass(frozen=True, slots=True)
class SubsampleDelta:
    """One self-subsample's Burrows delta against the committed reference."""

    label: str
    poem_count: int
    char_count: int
    token_count: int
    present_function_words: int
    """std>0 reference function words that actually occur (count>0) in this
    subsample — a sparsity gauge (the delta sum still ranges over *all* std>0
    words, scoring absent ones against their profile z)."""
    delta: float | None
    """Burrows delta, or ``None`` when ``compute_burrows_delta`` returned NaN
    (empty subsample / no surviving function word) — never fabricated."""


@dataclass(frozen=True, slots=True)
class BurrowsSelfFloorResult:
    """Calibration-only self-floor measurement (NOT a verdict, Codex CX6)."""

    persona_id: str
    language: str
    corpus_poem_count: int
    corpus_char_count: int
    surviving_function_words: int
    """Count of reference function words with std>0 — the constant denominator of
    the delta sum (reference-determined, independent of the subsample)."""
    split_half: tuple[SubsampleDelta, SubsampleDelta]
    jackknife: tuple[SubsampleDelta, ...]
    min_delta: float | None
    median_delta: float | None
    max_delta: float | None
    frozen_delta_self_max: float
    """The frozen ``BURROWS_DELTA_MAX`` (4.0), read for comparison — NOT modified."""
    delta_self_max_within_observed_band: bool | None
    """Whether 4.0 falls within ``[min_delta, max_delta]``; ``None`` when no finite
    delta was observed. A 4.0 below the whole band = threshold under the noise
    floor (calibration signal, not a decision)."""
    no_ci: bool
    no_go_no_go: bool
    no_threshold_update: bool
    limitation: str

    def to_summary_dict(self) -> dict[str, object]:
        """JSON-serialisable summary (for steering / sidecar records)."""
        return {
            "persona_id": self.persona_id,
            "language": self.language,
            "corpus_poem_count": self.corpus_poem_count,
            "corpus_char_count": self.corpus_char_count,
            "surviving_function_words": self.surviving_function_words,
            "frozen_delta_self_max": self.frozen_delta_self_max,
            "min_delta": self.min_delta,
            "median_delta": self.median_delta,
            "max_delta": self.max_delta,
            "delta_self_max_within_observed_band": (
                self.delta_self_max_within_observed_band
            ),
            "split_half": [_subsample_dict(s) for s in self.split_half],
            "jackknife": [_subsample_dict(s) for s in self.jackknife],
            "no_ci": self.no_ci,
            "no_go_no_go": self.no_go_no_go,
            "no_threshold_update": self.no_threshold_update,
            "limitation": self.limitation,
        }


def _subsample_dict(s: SubsampleDelta) -> dict[str, object]:
    return {
        "label": s.label,
        "poem_count": s.poem_count,
        "char_count": s.char_count,
        "token_count": s.token_count,
        "present_function_words": s.present_function_words,
        "delta": s.delta,
    }


def _load_corpus_poems(persona_id: str, language: str) -> list[str]:
    """Read the persona's raw corpus, one non-empty line (poem) per element."""
    corpus_path: str | None = None
    for entry in get_provenance_entries():
        if entry.get("persona_id") == persona_id and entry.get("language") == language:
            raw = entry.get("corpus_path")
            corpus_path = str(raw) if raw else None
            break
    if not corpus_path:
        msg = f"no corpus_path registered for {persona_id!r}/{language!r}"
        raise ValueError(msg)
    text = (_REFERENCE_CORPUS_DIR / corpus_path).read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]


def _subsample(
    label: str, poems: list[str], reference: BurrowsReference, language: str
) -> SubsampleDelta:
    """Burrows delta of a poem subsample vs the committed reference (ja path)."""
    text = "".join(poems)
    tokens = tokenise_ja(text, reference.function_words)
    counts = Counter(t.lower() for t in tokens if t)
    present = sum(
        1
        for fw, std in zip(
            reference.function_words, reference.background_std, strict=True
        )
        if std > 0.0 and counts.get(fw, 0) > 0
    )
    delta = compute_burrows_delta(
        text, reference, language=language, preprocessed_tokens=tokens
    )
    return SubsampleDelta(
        label=label,
        poem_count=len(poems),
        char_count=sum(len(p) for p in poems),
        token_count=len(tokens),
        present_function_words=present,
        delta=float(delta) if math.isfinite(delta) else None,
    )


def compute_burrows_self_floor(
    persona_id: str = "rikyu", language: str = "ja"
) -> BurrowsSelfFloorResult:
    """Measure the within-individual Burrows self-floor (calibration, not verdict).

    Splits the persona's own reference corpus into (a) an odd/even split-half and
    (b) leave-one-poem-out jackknife subsamples, scoring each against the
    committed reference. Aggregates are taken over the **finite** deltas of all
    subsamples (split-half ∪ jackknife).
    """
    poems = _load_corpus_poems(persona_id, language)
    reference = load_reference(persona_id, language)
    surviving_fw = sum(1 for std in reference.background_std if std > 0.0)

    even = _subsample("even", poems[0::2], reference, language)
    odd = _subsample("odd", poems[1::2], reference, language)
    jackknife = tuple(
        _subsample(
            f"jackknife_drop_{i}", poems[:i] + poems[i + 1 :], reference, language
        )
        for i in range(len(poems))
    )

    finite = [s.delta for s in (even, odd, *jackknife) if s.delta is not None]
    min_delta = min(finite) if finite else None
    max_delta = max(finite) if finite else None
    median_delta = statistics.median(finite) if finite else None
    within_band = (
        None
        if (min_delta is None or max_delta is None)
        else (min_delta <= BURROWS_DELTA_MAX <= max_delta)
    )

    return BurrowsSelfFloorResult(
        persona_id=persona_id,
        language=language,
        corpus_poem_count=len(poems),
        corpus_char_count=sum(len(p) for p in poems),
        surviving_function_words=surviving_fw,
        split_half=(even, odd),
        jackknife=jackknife,
        min_delta=min_delta,
        median_delta=median_delta,
        max_delta=max_delta,
        frozen_delta_self_max=BURROWS_DELTA_MAX,
        delta_self_max_within_observed_band=within_band,
        no_ci=True,
        no_go_no_go=True,
        no_threshold_update=True,
        limitation=_LIMITATION,
    )


__all__ = [
    "BurrowsSelfFloorResult",
    "SubsampleDelta",
    "compute_burrows_self_floor",
]
