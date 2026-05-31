"""Reference-corpus QC tests for Burrows Delta (P1b / ME-6).

Three layers of assertion:

1. **Schema gate** — ``_provenance.yaml`` and ``vectors.json`` parse
   correctly, every provenance entry carries the ME-6 required keys,
   every registered persona/language pair round-trips through the
   loader, unregistered pairs raise
   :class:`ReferenceCorpusMissingError`. These tests run on every CI
   default-suite run (no heavy ML deps).
2. **Persona-discriminative gate** — short held-out excerpts from each
   real PD corpus are closer to their own persona profile than to the
   other persona's profile under the Burrows L1 distance. Validates
   that the toy reference is at least directionally informative on
   real text (not just synthetic round-trip).
3. **ME-6 5K-word chunk stability gate** — splits the longest available
   corpus (Nietzsche, ≥10K words) into ≥2 non-overlapping ≥5K-word
   chunks and checks that the persona-rank ordering produced by each
   chunk's Delta-against-reference vector is rank-stable across chunks
   (Spearman ρ ≥ 0.8). Toy-scale corpora (Kant 2.6K words, Rikyū 5
   verses) skip with explicit reopen reasons pointing to
   ``blockers.md`` "Burrows corpus license — corpus expansion".
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import pytest
import yaml

from erre_sandbox.evidence.reference_corpus import (
    ReferenceCorpusMissingError,
    available_personas,
    load_reference,
)
from erre_sandbox.evidence.reference_corpus._build_vectors import (
    BACKGROUND_CHUNK_DE,
    _tokenise_de,
    _tokenise_ja,
)
from erre_sandbox.evidence.reference_corpus.function_words import (
    FUNCTION_WORDS_JA,
)
from erre_sandbox.evidence.reference_corpus.loader import (
    _HERE,
    PROVENANCE_REQUIRED_KEYS,
    get_provenance_entries,
)
from erre_sandbox.evidence.tier_a.burrows import (
    BurrowsReference,
    compute_burrows_delta,
)

# ME-6: chunk size for the stability QC. The 5K-word floor follows
# stylometry guidance (Eder 2017 visualisation paper) that <5K-word
# chunks tend to be unreliable; the toy reference's smaller corpora
# (Kant 2.6K, Rikyū ~120 tokens) cannot satisfy this and skip
# explicitly so the reopen path stays visible.
CHUNK_QC_SIZE = 5000


# --- Spearman ρ helper -----------------------------------------------------
#
# Implemented in pure stdlib so the QC test runs on the default CI
# invocation (without ``[eval]`` extras / scipy). Handles ties via the
# average-rank convention.


def _ranks(values: Sequence[float]) -> list[float]:
    sorted_idx = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(sorted_idx):
        j = i
        anchor = values[sorted_idx[i]]
        while j + 1 < len(sorted_idx) and values[sorted_idx[j + 1]] == anchor:
            j += 1
        # Average rank for the tie group, 1-based.
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[sorted_idx[k]] = avg
        i = j + 1
    return ranks


def _spearman_rho(x: Sequence[float], y: Sequence[float]) -> float:
    if len(x) != len(y):
        raise ValueError("x and y must have equal length for Spearman ρ")
    if len(x) < 2:
        raise ValueError("Spearman ρ undefined for fewer than 2 observations")
    rx = _ranks(x)
    ry = _ranks(y)
    mean_x = sum(rx) / len(rx)
    mean_y = sum(ry) / len(ry)
    num = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry, strict=True))
    den_x = math.sqrt(sum((a - mean_x) ** 2 for a in rx))
    den_y = math.sqrt(sum((b - mean_y) ** 2 for b in ry))
    if den_x == 0 or den_y == 0:
        return float("nan")
    return num / (den_x * den_y)


# --- Schema gate ----------------------------------------------------------


def test_provenance_yaml_parses_and_has_entries() -> None:
    text = (_HERE / "_provenance.yaml").read_text(encoding="utf-8")
    parsed = yaml.safe_load(text)
    assert isinstance(parsed, dict)
    assert parsed.get("schema_version") == "0.1.0-m9eval"
    entries = parsed.get("entries")
    assert isinstance(entries, list)
    assert len(entries) >= 4  # 3 PD personas + at least one synthetic_4th


def test_provenance_required_keys_complete_for_every_entry() -> None:
    for idx, entry in enumerate(get_provenance_entries()):
        missing = PROVENANCE_REQUIRED_KEYS - set(entry.keys())
        assert not missing, f"entries[{idx}] missing keys {sorted(missing)}"


def test_every_provenance_entry_has_public_domain_true() -> None:
    # The toy reference scope is PD-only by design (Cambridge Edition /
    # Kaufmann translation deferred). If a future PR introduces a
    # restricted-license entry the contract test fires before the data
    # ships.
    for entry in get_provenance_entries():
        assert entry.get("public_domain") is True, (
            f"non-PD provenance entry: {entry.get('persona_id')!r}/"
            f"{entry.get('language')!r} — see blockers.md before adding"
        )


def test_available_personas_round_trips_through_loader() -> None:
    pairs = available_personas()
    assert pairs, "available_personas() empty — vectors.json or provenance broken"
    for persona_id, language in pairs:
        ref = load_reference(persona_id, language)
        assert isinstance(ref, BurrowsReference)
        assert ref.language == language


def test_unregistered_persona_raises() -> None:
    with pytest.raises(ReferenceCorpusMissingError):
        load_reference("plato", "de")


def test_cross_language_pair_raises() -> None:
    # kant has only 'de' provenance; ('kant', 'ja') must not silently
    # fall back to a different language.
    with pytest.raises(ReferenceCorpusMissingError):
        load_reference("kant", "ja")


# --- synthetic_4th = background mean (DB7 LOW-1) -------------------------


def test_synthetic_4th_de_profile_equals_background_mean() -> None:
    ref = load_reference("synthetic_4th", "de")
    assert ref.profile_freq == ref.background_mean


def test_synthetic_4th_ja_profile_equals_background_mean() -> None:
    ref = load_reference("synthetic_4th", "ja")
    assert ref.profile_freq == ref.background_mean


# --- Persona-discriminative on real toy corpora --------------------------


def _read_corpus(persona_id: str, language: str) -> str:
    # Locate the raw corpus via provenance lookup so this stays in lock
    # with the YAML record.
    for entry in get_provenance_entries():
        if entry.get("persona_id") == persona_id and entry.get("language") == language:
            corpus_path = str(entry.get("corpus_path") or "")
            if not corpus_path:
                pytest.skip(
                    f"persona_id={persona_id!r} language={language!r}"
                    f" has no raw corpus (analytical / synthetic only)",
                )
            return (_HERE / corpus_path).read_text(encoding="utf-8")
    pytest.fail(f"no provenance entry for {persona_id!r}/{language!r}")


def test_kant_excerpt_closer_to_kant_profile_than_to_nietzsche_profile() -> None:
    # Take the first 800 tokens of Kant as a held-out-ish probe. The
    # full Kant corpus seeded the Kant profile, so this is not a leakage-
    # free test, but the directional claim ("Kant text gets a smaller
    # Delta against Kant ref than against Nietzsche ref") is exactly
    # the stylometric signal the toy reference is meant to support.
    text = _read_corpus("kant", "de")
    head_tokens = _tokenise_de(text)[:800]
    kant_ref = load_reference("kant", "de")
    nietzsche_ref = load_reference("nietzsche", "de")

    d_self = compute_burrows_delta(
        text="ignored",
        reference=kant_ref,
        language="de",
        preprocessed_tokens=head_tokens,
    )
    d_other = compute_burrows_delta(
        text="ignored",
        reference=nietzsche_ref,
        language="de",
        preprocessed_tokens=head_tokens,
    )
    assert math.isfinite(d_self)
    assert math.isfinite(d_other)
    assert d_self < d_other, (
        f"Kant excerpt closer to Nietzsche than Kant: d_kant={d_self:.3f}"
        f" d_nietzsche={d_other:.3f}"
    )


def test_nietzsche_excerpt_closer_to_nietzsche_profile_than_to_kant_profile() -> None:
    text = _read_corpus("nietzsche", "de")
    head_tokens = _tokenise_de(text)[:800]
    kant_ref = load_reference("kant", "de")
    nietzsche_ref = load_reference("nietzsche", "de")

    d_self = compute_burrows_delta(
        text="ignored",
        reference=nietzsche_ref,
        language="de",
        preprocessed_tokens=head_tokens,
    )
    d_other = compute_burrows_delta(
        text="ignored",
        reference=kant_ref,
        language="de",
        preprocessed_tokens=head_tokens,
    )
    assert math.isfinite(d_self)
    assert math.isfinite(d_other)
    assert d_self < d_other, (
        f"Nietzsche excerpt closer to Kant than Nietzsche: d_nietzsche={d_self:.3f}"
        f" d_kant={d_other:.3f}"
    )


def test_build_and_runtime_ja_tokeniser_are_same_object() -> None:
    # M11-C3a drift gate: the reference builder's ``_tokenise_ja`` and the
    # runtime tokeniser must be the *same function object*, so the ja
    # tokenisation convention cannot drift between vectors.json and the
    # runtime Burrows path (Codex HIGH-2). _build_vectors re-exports it.
    from erre_sandbox.evidence.reference_corpus import _build_vectors
    from erre_sandbox.evidence.tier_a.burrows import tokenise_ja

    assert _build_vectors._tokenise_ja is tokenise_ja


def test_rikyu_ja_runtime_tokeniser_reproduces_committed_profile() -> None:
    # M11-C3a end-to-end parity (not a tautology): take the committed raw
    # corpus, tokenise it with the *runtime* adapter using the reference's own
    # function-word list, recompute the relative-frequency vector the same way
    # compute_burrows_delta counts (Counter over tokens / total), and assert it
    # reproduces the committed profile_freq bit-for-bit. This proves the
    # reference-generation pipeline and the runtime tokeniser emit identical
    # token→vector output (Codex MED-1: tokenise via ref.function_words).
    from erre_sandbox.evidence.tier_a.burrows import tokenise_ja

    text = _read_corpus("rikyu", "ja")
    ref = load_reference("rikyu", "ja")
    # Codex MED-1: assert the runtime particle list equals the build-time list
    # separately, then drive tokenisation from the runtime input itself.
    assert ref.function_words == FUNCTION_WORDS_JA
    tokens = tokenise_ja(text, ref.function_words)
    total = len(tokens)
    assert total > 0
    runtime_freq = tuple(tokens.count(fw) / total for fw in ref.function_words)
    assert runtime_freq == ref.profile_freq, (
        "runtime ja tokeniser did not reproduce the committed profile_freq"
        " bit-exact — tokenisation convention drift (rebuild vectors.json or"
        " check tokenise_ja)"
    )


def test_rikyu_excerpt_via_preprocessed_tokens_yields_finite_delta() -> None:
    # The Rikyū corpus is too small (5 verses, ~120 tokens after
    # particle tokenisation) to drive a discriminative claim; the
    # gate here is only "the loader + ja particle tokeniser produce a
    # finite Delta", i.e. the pipeline runs end-to-end on classical
    # Japanese without crashing or fold-to-NaN. Discriminative claim
    # for ja is deferred to corpus expansion (blockers.md).
    text = _read_corpus("rikyu", "ja")
    tokens = _tokenise_ja(text, FUNCTION_WORDS_JA)
    rikyu_ref = load_reference("rikyu", "ja")
    delta = compute_burrows_delta(
        text="ignored",
        reference=rikyu_ref,
        language="ja",
        preprocessed_tokens=tokens,
    )
    # Self-comparison Delta should be near zero (the profile was built
    # from this same text), but with a small token count and ties in
    # rank we accept any finite non-negative value.
    assert math.isfinite(delta)
    assert delta >= 0.0


# --- ME-6 5K-word chunk stability ----------------------------------------


@pytest.fixture
def nietzsche_5k_chunks() -> list[list[str]]:
    """Two non-overlapping ≥5K-word chunks of the Nietzsche corpus."""
    text = _read_corpus("nietzsche", "de")
    tokens = _tokenise_de(text)
    if len(tokens) < 2 * CHUNK_QC_SIZE:
        pytest.skip(
            f"Nietzsche corpus has {len(tokens)} tokens; ME-6 requires"
            f" ≥{2 * CHUNK_QC_SIZE} for the 5K-chunk stability test",
        )
    return [
        tokens[:CHUNK_QC_SIZE],
        tokens[CHUNK_QC_SIZE : 2 * CHUNK_QC_SIZE],
    ]


def test_me6_chunk_stability_nietzsche_persona_ranking_stable(
    nietzsche_5k_chunks: list[list[str]],
) -> None:
    """ME-6: rank ordering of personas under Burrows Δ is stable across chunks."""
    refs = [
        load_reference("kant", "de"),
        load_reference("nietzsche", "de"),
        load_reference("synthetic_4th", "de"),
    ]

    chunk_delta_vectors: list[list[float]] = []
    for chunk in nietzsche_5k_chunks:
        deltas = [
            compute_burrows_delta(
                text="ignored",
                reference=r,
                language="de",
                preprocessed_tokens=chunk,
            )
            for r in refs
        ]
        for d in deltas:
            assert math.isfinite(d), (
                "non-finite Δ in chunk-stability vector — std=0 dropped"
                " too many words; check vectors.json bg_std for de"
            )
        chunk_delta_vectors.append(deltas)

    # Pairwise Spearman ρ across chunk pairs. With 2 chunks we have one
    # pair; with N chunks we have C(N,2). Mean ρ ≥ 0.8 is the ME-6 gate.
    rhos: list[float] = [
        _spearman_rho(chunk_delta_vectors[i], chunk_delta_vectors[j])
        for i in range(len(chunk_delta_vectors))
        for j in range(i + 1, len(chunk_delta_vectors))
    ]
    assert rhos, "no chunk pairs available — fixture should have skipped"
    mean_rho = sum(rhos) / len(rhos)
    assert mean_rho >= 0.8, (
        f"ME-6 rank stability failed: mean Spearman ρ={mean_rho:.3f}"
        f" across {len(rhos)} chunk pairs; reopen condition documented"
        f" in blockers.md (chunk_stability rank instability)"
    )


def test_me6_chunk_stability_kant_skip_documents_reopen_path() -> None:
    """Kant corpus is below the ≥10K-word ME-6 floor — skip with reason."""
    text = _read_corpus("kant", "de")
    tokens = _tokenise_de(text)
    if len(tokens) >= 2 * CHUNK_QC_SIZE:
        pytest.fail(
            f"Kant corpus grew to {len(tokens)} tokens — promote to a real"
            f" stability assertion and remove this skip",
        )
    pytest.skip(
        f"Kant corpus has {len(tokens)} tokens (<{2 * CHUNK_QC_SIZE});"
        f" ME-6 5K-chunk stability deferred to m9-eval-corpus expansion"
        f" (Akademie-Ausgabe Bd. VIII full ingest)",
    )


def test_me6_chunk_stability_rikyu_skip_documents_reopen_path() -> None:
    """Rikyū corpus is far below ME-6 floor — skip with reason."""
    text = _read_corpus("rikyu", "ja")
    tokens = _tokenise_ja(text, FUNCTION_WORDS_JA)
    if len(tokens) >= 2 * CHUNK_QC_SIZE:
        pytest.fail(
            f"Rikyū corpus grew to {len(tokens)} tokens — promote to a real"
            f" stability assertion and remove this skip",
        )
    pytest.skip(
        f"Rikyū corpus has {len(tokens)} tokens (<{2 * CHUNK_QC_SIZE});"
        f" ME-6 5K-chunk stability deferred to m9-eval-corpus expansion"
        f" (青空文庫 / 国文大観 OCR pipeline)",
    )


# --- background-chunk QC --------------------------------------------------


def test_de_background_std_strictly_positive_for_every_function_word() -> None:
    # de has two pooled corpora (Kant + Nietzsche) and chunks of size
    # BACKGROUND_CHUNK_DE so every function word should occur in at
    # least one chunk with non-zero variance. A zero std here means
    # the function word never occurred — flag for removal from
    # FUNCTION_WORDS_DE rather than letting it silently get dropped
    # by compute_burrows_delta's std<=0 guard.
    ref = load_reference("kant", "de")
    zeros = [
        fw
        for fw, std in zip(ref.function_words, ref.background_std, strict=True)
        if std <= 0.0
    ]
    assert not zeros, (
        f"de function words with zero background std: {zeros};"
        f" remove them from FUNCTION_WORDS_DE or expand corpus"
    )


def test_de_background_chunk_size_constant_documented() -> None:
    # Sanity: the build script's BACKGROUND_CHUNK_DE constant is what
    # the test file reasons about. If someone bumps it without
    # rebuilding vectors.json the loaded background_std silently shifts
    # — we surface that mismatch by re-asserting the constant here.
    assert BACKGROUND_CHUNK_DE == 500, (
        "BACKGROUND_CHUNK_DE changed; rebuild vectors.json and update"
        " FUNCTION_WORDS_DE expectations if discriminative tests regress"
    )
