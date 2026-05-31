"""Reference corpora for Tier A Burrows Delta (M9 evaluation system).

P1b deliverables (reference corpus, ME-6):

* ``_provenance.yaml`` — license, edition, translator, year and
  ``public_domain`` flag for every shipped reference. ME-6 mandates this
  metadata; without it a reference is not trustable for stylometric
  reproduction.
* :mod:`function_words` — closed function-word lists per language with
  citations to the curating literature.
* :mod:`loader` — :func:`load_reference` returns a frozen
  :class:`erre_sandbox.evidence.tier_a.burrows.BurrowsReference` for a
  ``(persona_id, language)`` pair, or raises
  :class:`ReferenceCorpusMissingError` if the pair is not registered.
* ``vectors.json`` — pre-computed background mean/std and per-persona
  ``profile_freq`` arrays. Built deterministically from the raw corpus
  files under ``raw/`` by ``_build_vectors`` (run once when the corpus
  changes; the resulting JSON is committed so test runs are reproducible
  without re-tokenising).
* ``raw/{kant_de,nietzsche_de,rikyu_ja}.txt`` — verbatim public-domain
  excerpts. Provenance is recorded in ``_provenance.yaml``; the synthetic
  4th persona (DB7 LOW-1 / ``personas/_synthetic_4th.yaml``) sits at the
  background mean and is computed analytically (no raw text needed).

Imports in this module are kept light — :mod:`yaml` and JSON loading
happen lazily inside :func:`loader.load_reference` so that the package
namespace does not pull I/O on import.
"""

from __future__ import annotations

from erre_sandbox.evidence.reference_corpus.loader import (
    ReferenceCorpusMissingError,
    available_personas,
    load_reference,
)

__all__ = [
    "ReferenceCorpusMissingError",
    "available_personas",
    "load_reference",
]
