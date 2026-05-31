"""Reference-corpus loader for Burrows Delta.

Returns frozen
:class:`erre_sandbox.evidence.tier_a.burrows.BurrowsReference` instances
hydrated from the committed ``vectors.json`` and validated against
``_provenance.yaml`` (ME-6: every served reference must carry license /
edition / year / public_domain metadata).

Workflow at runtime:

1. ``_provenance.yaml`` defines the **registered set** — a persona /
   language pair only gets served if it has a provenance entry. Missing
   entries raise :class:`ReferenceCorpusMissingError` so silent fallback
   to a different language never happens.
2. ``vectors.json`` is the **pre-computed numerical artefact** built by
   :mod:`_build_vectors`. The loader fans the raw arrays into a
   :class:`BurrowsReference` (whose ``__post_init__`` validates equal
   lengths, finite values, non-negative std).
3. Lookups are cached per process (``functools.lru_cache``) so test
   runs that touch many references don't re-parse the YAML / JSON on
   every call.

The loader **does not** evaluate or compute Burrows Delta — that lives
in :mod:`erre_sandbox.evidence.tier_a.burrows`. This module's only
responsibility is constructing the reference object from disk in a
provenance-checked way.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Final

import yaml

from erre_sandbox.evidence.tier_a.burrows import BurrowsReference

_HERE: Final = Path(__file__).resolve().parent
_PROVENANCE_PATH: Final = _HERE / "_provenance.yaml"
_VECTORS_PATH: Final = _HERE / "vectors.json"

PROVENANCE_REQUIRED_KEYS: Final[frozenset[str]] = frozenset(
    {
        "persona_id",
        "language",
        "source",
        "edition",
        "translator",
        "year",
        "public_domain",
        "retrieval_url",
        "retrieval_date",
        "corpus_path",
        "approx_tokens",
        "corpus_too_small_for_chunk_qc",
        "notes",
    },
)
"""Every entry under ``_provenance.yaml`` ``entries`` must carry these
keys verbatim. Missing keys raise on first load — ME-6 requires the
metadata to be exhaustive, not best-effort."""


class ReferenceCorpusMissingError(KeyError):
    """Raised when the requested ``(persona_id, language)`` is unregistered.

    "Unregistered" means either no provenance entry, or a provenance
    entry exists but ``vectors.json`` lacks a matching numerical record
    — both are loader contract violations and surfaced identically so
    callers don't need to peek into either file to diagnose.
    """


class ReferenceCorpusSchemaError(ValueError):
    """Raised when the on-disk corpus artefacts are structurally broken.

    Examples: ``vectors.json`` missing the ``schema_version`` field,
    function-word vectors with mismatched lengths, ``_provenance.yaml``
    entry missing one of :data:`PROVENANCE_REQUIRED_KEYS`. We surface
    these eagerly so a corrupted commit is caught at the first
    :func:`load_reference` rather than lurking until a Burrows Delta
    NaN at evaluation time.
    """


@lru_cache(maxsize=1)
def _load_provenance_raw() -> tuple[tuple[tuple[str, object], ...], ...]:
    """Parse ``_provenance.yaml`` once per process.

    Returns a tuple of (key, value)-tuples per entry — hashable so that
    downstream lookups can also be ``lru_cache``-decorated.
    """
    text = _PROVENANCE_PATH.read_text(encoding="utf-8")
    parsed = yaml.safe_load(text)
    if not isinstance(parsed, dict):
        raise ReferenceCorpusSchemaError(
            "_provenance.yaml top-level must be a mapping, got"
            f" {type(parsed).__name__}",
        )
    entries = parsed.get("entries")
    if not isinstance(entries, list):
        raise ReferenceCorpusSchemaError(
            "_provenance.yaml must have an 'entries' list at top level",
        )
    out: list[tuple[tuple[str, object], ...]] = []
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ReferenceCorpusSchemaError(
                f"_provenance.yaml entries[{idx}] must be a mapping",
            )
        missing = PROVENANCE_REQUIRED_KEYS - set(entry.keys())
        if missing:
            raise ReferenceCorpusSchemaError(
                f"_provenance.yaml entries[{idx}] missing keys: {sorted(missing)}",
            )
        out.append(tuple(sorted(entry.items())))
    return tuple(out)


def get_provenance_entries() -> list[dict[str, object]]:
    """Return the parsed provenance entries as a list of dicts.

    Re-materialises the cached tuple-of-tuples representation into the
    dict form that callers expect. The cached representation stays
    hashable; this fan-out only allocates per call (cheap for a small
    list).
    """
    return [dict(pairs) for pairs in _load_provenance_raw()]


@lru_cache(maxsize=1)
def _load_vectors_raw() -> dict[str, object]:
    """Parse ``vectors.json`` once per process."""
    if not _VECTORS_PATH.is_file():
        raise ReferenceCorpusSchemaError(
            f"vectors.json missing at {_VECTORS_PATH}; run"
            f" `python -m erre_sandbox.evidence.reference_corpus._build_vectors`"
            f" to generate it from raw/",
        )
    parsed = json.loads(_VECTORS_PATH.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ReferenceCorpusSchemaError(
            f"vectors.json top-level must be a mapping, got {type(parsed).__name__}",
        )
    if "schema_version" not in parsed:
        raise ReferenceCorpusSchemaError("vectors.json missing 'schema_version'")
    if not isinstance(parsed.get("languages"), dict):
        raise ReferenceCorpusSchemaError("vectors.json 'languages' must be a mapping")
    return parsed


def available_personas(language: str | None = None) -> tuple[tuple[str, str], ...]:
    """List registered ``(persona_id, language)`` pairs.

    Args:
        language: Optionally restrict to a single language (``"de"`` /
            ``"ja"``). ``None`` returns every registered pair.

    Returns:
        Sorted tuple of ``(persona_id, language)`` pairs that have both
        a provenance entry and a ``vectors.json`` profile. Pairs that
        appear in only one of the two artefacts are excluded — they
        would also raise on :func:`load_reference`, and the contract
        for "available" is "loadable end-to-end".
    """
    vectors = _load_vectors_raw()
    languages_block = vectors["languages"]
    assert isinstance(languages_block, dict)
    provenance = get_provenance_entries()
    provenance_pairs = {(str(e["persona_id"]), str(e["language"])) for e in provenance}
    out: list[tuple[str, str]] = []
    for lang_key, lang_data in languages_block.items():
        if language is not None and lang_key != language:
            continue
        if not isinstance(lang_data, dict):
            continue
        personas_block = lang_data.get("personas")
        if not isinstance(personas_block, dict):
            continue
        for persona_id in personas_block:
            pair = (persona_id, lang_key)
            if pair in provenance_pairs:
                out.append(pair)
    return tuple(sorted(out))


def _provenance_for(persona_id: str, language: str) -> dict[str, object]:
    """Return the provenance entry for the pair, or raise."""
    for entry in get_provenance_entries():
        if entry.get("persona_id") == persona_id and entry.get("language") == language:
            return entry
    raise ReferenceCorpusMissingError(
        f"no provenance entry registered for persona_id={persona_id!r}"
        f" language={language!r} — see _provenance.yaml",
    )


def _vector_block_for(
    persona_id: str, language: str
) -> tuple[
    tuple[str, ...],
    tuple[float, ...],
    tuple[float, ...],
    tuple[float, ...],
]:
    """Return ``(function_words, bg_mean, bg_std, profile_freq)`` tuples."""
    vectors = _load_vectors_raw()
    languages_block = vectors["languages"]
    assert isinstance(languages_block, dict)
    if language not in languages_block:
        raise ReferenceCorpusMissingError(
            f"vectors.json has no language={language!r}; provenance entry"
            f" registered persona_id={persona_id!r} but vectors are absent",
        )
    lang_data = languages_block[language]
    if not isinstance(lang_data, dict):
        raise ReferenceCorpusSchemaError(
            f"vectors.json languages[{language!r}] must be a mapping",
        )
    personas_block = lang_data.get("personas")
    if not isinstance(personas_block, dict) or persona_id not in personas_block:
        raise ReferenceCorpusMissingError(
            f"vectors.json languages[{language!r}].personas missing"
            f" persona_id={persona_id!r}",
        )
    persona_block = personas_block[persona_id]
    if not isinstance(persona_block, dict) or "profile_freq" not in persona_block:
        raise ReferenceCorpusSchemaError(
            f"vectors.json languages[{language!r}].personas[{persona_id!r}]"
            f" missing 'profile_freq'",
        )
    fws = lang_data.get("function_words")
    bg_mean = lang_data.get("background_mean")
    bg_std = lang_data.get("background_std")
    profile = persona_block.get("profile_freq")
    if not (
        isinstance(fws, list)
        and isinstance(bg_mean, list)
        and isinstance(bg_std, list)
        and isinstance(profile, list)
    ):
        raise ReferenceCorpusSchemaError(
            f"vectors.json languages[{language!r}] vectors must all be lists",
        )
    return (
        tuple(str(w) for w in fws),
        tuple(float(v) for v in bg_mean),
        tuple(float(v) for v in bg_std),
        tuple(float(v) for v in profile),
    )


def load_reference(persona_id: str, language: str) -> BurrowsReference:
    """Hydrate a frozen :class:`BurrowsReference` for the given pair.

    Args:
        persona_id: Stable persona identifier (matches ``personas/*.yaml``
            and the keys under ``vectors.json``).
        language: ISO-ish language tag (``"de"`` / ``"ja"``).

    Returns:
        A frozen :class:`BurrowsReference` ready to be passed to
        :func:`erre_sandbox.evidence.tier_a.burrows.compute_burrows_delta`.

    Raises:
        ReferenceCorpusMissingError: ``(persona_id, language)`` is not
            registered in either ``_provenance.yaml`` or ``vectors.json``.
        ReferenceCorpusSchemaError: On-disk artefacts are structurally
            broken (missing schema fields, vector length mismatch, etc.).
    """
    # Provenance is the gating contract — fetch it first so an
    # unregistered pair never reaches the vectors lookup.
    _provenance_for(persona_id, language)
    fws, bg_mean, bg_std, profile = _vector_block_for(persona_id, language)
    return BurrowsReference(
        language=language,
        function_words=fws,
        background_mean=bg_mean,
        background_std=bg_std,
        profile_freq=profile,
    )
