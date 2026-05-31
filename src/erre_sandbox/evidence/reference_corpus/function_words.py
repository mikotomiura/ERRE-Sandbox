"""Closed function-word lists per language for Burrows Delta.

Stylometry tradition (Burrows 2002; Eder/Rybicki/Kestemont 2016, R Journal
"Stylometry with R") computes Delta over a closed list of high-frequency
function words. The list is **language-specific**: cross-language reuse
(German list against an English text) yields meaningless z-scores.

For German (``de``) we use the 50-word list compiled from the German
high-frequency function-word inventory commonly cited in computational
stylistics (articles, pronouns, modal/auxiliary verbs, prepositions,
conjunctions). This is the same family of lists used by the R ``stylo``
package's German MFW preset; we pin a fixed subset so the M9 reference
profile is deterministic across runs.

For Japanese (``ja``) the analogue of "function words" is **particles**
(助詞) — closed-class single- or two-character morphemes carrying
grammatical function. We list 23 high-frequency particles drawn from
the standard Japanese particle inventory (case markers, topic/focus
markers, conjunctive particles, sentence-final particles). These match
across whitespace-free classical and modern text without requiring a
morphological analyser, which is important since SudachiPy / MeCab
integration is deferred to a later P1b iteration (see
``BurrowsTokenizationUnsupportedError`` in
:mod:`erre_sandbox.evidence.tier_a.burrows`).

The Japanese particle path is enumerated **as substrings** because we
cannot run a real tokeniser yet; the Burrows code consumes
``preprocessed_tokens`` from the loader, where each occurrence of a
listed particle in the source text is emitted as one token (and every
non-particle character is emitted as a single filler token, so the total
"token count" denominator is character-count-minus-whitespace).
"""

from __future__ import annotations

from typing import Final

FUNCTION_WORDS_DE: Final[tuple[str, ...]] = (
    # Articles
    "der",
    "die",
    "das",
    "den",
    "dem",
    "des",
    "ein",
    "eine",
    "einen",
    "einer",
    "eines",
    "einem",
    # Pronouns
    "ich",
    "du",
    "er",
    "sie",
    "es",
    "wir",
    "ihr",
    "sich",
    "mich",
    "dich",
    "mir",
    "dir",
    "ihm",
    "ihn",
    "ihnen",
    # Conjunctions
    "und",
    "oder",
    "aber",
    "denn",
    "weil",
    "dass",
    "daß",
    "wenn",
    "als",
    "wie",
    # Prepositions
    "von",
    "zu",
    "mit",
    "in",
    "auf",
    "an",
    "bei",
    "für",
    "über",
    "unter",
    "durch",
    "ohne",
)
"""High-frequency German function words (49 entries) used as the closed
Burrows list. Includes both modern ``dass`` and historical ``daß``
spellings since the 1784 Akademie-Ausgabe Kant text uses ``daß`` while
the 1883 Kröner-tradition Nietzsche edition modernised some forms."""


FUNCTION_WORDS_JA: Final[tuple[str, ...]] = (
    # Case-marking particles (格助詞)
    "の",
    "が",
    "を",
    "に",
    "で",
    "へ",
    "と",
    "から",
    "まで",
    "より",
    # Topic / focus / emphasis (副助詞・係助詞)  # noqa: ERA001
    "は",
    "も",
    "こそ",
    "さえ",
    "しか",
    "だけ",
    "ばかり",
    # Conjunctive (接続助詞)  # noqa: ERA001
    "ば",
    "ても",
    "けど",
    # Sentence-final / classical inflection (終助詞・古典助動詞)
    "けり",
    "なり",
    "べし",
)
"""High-frequency Japanese particles used as the closed Burrows list.

The set is deliberately small (23 entries) because the available
Japanese reference corpus (``rikyu_ja.txt``) is itself small (5 PD
道歌, ~134 chars). A larger list would have many zero-count entries
inflating the Burrows L1 sum with pure noise. Expansion to a full
particle inventory (~80 entries) is deferred to the m9-eval-corpus
follow-up task once a larger PD ja corpus is acquired (see
``blockers.md`` "Burrows corpus license — Rikyu corpus expansion").
"""


__all__ = [
    "FUNCTION_WORDS_DE",
    "FUNCTION_WORDS_JA",
]
