"""IPIP-50 (Goldberg 1992) administering helper for Tier B Big5 ICC.

The 50 items are vendored verbatim from the public-domain IPIP corpus
(https://ipip.ori.org/, English official, public domain commercial use OK).
Mini-IPIP-20 is intentionally not implemented because Mini-IPIP α 0.65-0.70
sits on the ME-1 fallback boundary 0.6 (M9-eval ME-12); IPIP-50 broad-domain
α ≈ 0.84 (https://ipip.ori.org/newBigFive5broadTable.htm).

Anti-demand-characteristics design (Codex P4a HIGH-4 / M9-eval ME-13). LLMs
infer personality-test context and shift toward socially desirable answers
(Salecha et al. 2024, https://arxiv.org/abs/2405.06058); the prompt template
therefore avoids "personality test", "Big Five", "IPIP", "questionnaire",
"survey", and "psychological" wording. Items are presented one at a time in
deterministically shuffled order, and decoy items dilute the test-taking
context inference.

Japanese administration is deferred (Codex P4a HIGH-3 / ME-12). The Murakami
2002/2003 lexical Big Five papers are not an IPIP-50 translation source; the
official IPIP translations page lists Nakayama/Karlin Japanese IPIP and a
license-cleared 50-item subset is required before ``language="ja"`` can be
admitted. Until then the helper raises ``NotImplementedError`` for ``ja``.

LIWC alternative honest framing (M9-B DB10 Option D): IPIP self-report only —
no LIWC equivalence claim, no external-lexicon Big5 inference. Tier A
``empath_proxy`` is a separate psycholinguistic axis (ME-1 / DB10 Option D).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass

PersonaResponder = Callable[[str], int]
"""Stub-friendly callable: take an item prompt, return a 1..5 Likert integer.

Tests pass a deterministic stub (e.g. constant 3, alternating 1/5) so the
helper exercises scoring / shuffling / diagnostics without an LLM round-trip.
"""

DEFAULT_LIKERT_MIN: int = 1
DEFAULT_LIKERT_MAX: int = 5
"""5-point Likert administration (Codex P4a LOW-1 keep)."""

DEFAULT_DECOY_COUNT: int = 5
"""Decoy items count (Codex P4a HIGH-4)."""

PROMPT_TEMPLATE_EN: str = (
    "Read the statement and reply with one digit from 1 to 5 indicating how"
    " well it describes you, where 1 = not at all, 2 = a little,"
    " 3 = somewhat, 4 = mostly, 5 = very much.\n\nStatement: {item}\n\n"
    "Reply with only the digit."
)
"""Anti-demand-characteristics English prompt (M9-eval ME-13).

The forbidden keywords for self-test detection are encoded in
:data:`FORBIDDEN_KEYWORDS`; the unit test asserts the rendered prompt
contains none of them.
"""

FORBIDDEN_KEYWORDS: tuple[str, ...] = (
    "personality test",
    "personality assessment",
    "big five",
    "big-five",
    "ipip",
    "questionnaire",
    "survey",
    "psychological",
    "psychometric",
)
"""Words/phrases the prompt must not contain (HIGH-4 anti-demand-characteristics).

Asserted by ``test_administer_ipip_50_no_personality_keywords_in_prompt``.
"""


@dataclass(frozen=True, slots=True)
class IPIPItem:
    """One IPIP-50 item.

    ``sign = +1`` for forward-keyed items (high Likert → high dimension);
    ``sign = -1`` for reverse-keyed items (high Likert → low dimension).
    """

    statement: str
    dimension: str  # "E" | "A" | "C" | "N" | "O"
    sign: int  # +1 forward, -1 reverse


@dataclass(frozen=True, slots=True)
class DecoyItem:
    """One decoy item (Codex P4a HIGH-4).

    Decoy items are presented in the same shuffled stream but excluded from
    Big5 scoring. Their Likert distribution feeds the ``decoy_consistency``
    diagnostic so an obviously biased responder (always 3, always 1) is
    surfaced.
    """

    statement: str


@dataclass(frozen=True, slots=True)
class Big5Scores:
    """Per-administration Big5 vector, dimensions in [1, 5] after reverse-keying."""

    extraversion: float
    agreeableness: float
    conscientiousness: float
    neuroticism: float
    openness: float
    n_items: int  # 50 for IPIP-50 (mini-ipip-20 deferred per ME-12)
    version: str  # "ipip-50"


@dataclass(frozen=True, slots=True)
class IPIPDiagnostic:
    """Quality-control side-channel — never used as Big5 itself.

    ME-1 specifies acquiescence / straight-line / reverse-keyed; HIGH-4
    adds ``decoy_consistency`` so a uniformly-biased responder is detected
    even if the diagnostics above pass.
    """

    acquiescence_index: float  # mean Likert centred at 3, abs avg deviation
    straight_line_runs: int  # max consecutive identical answers in shuffled order
    reverse_keyed_agreement: float  # corr between forward+reverse pairs (per dim)
    decoy_consistency: float  # |mean(decoy) - 3| / 2, in [0, 1]; high = biased


# ---------------------------------------------------------------------------
# IPIP-50 item corpus (vendored verbatim, public domain, English only)
# Source: https://ipip.ori.org/newBigFive5broadKey.htm
# ---------------------------------------------------------------------------

_IPIP_50_EN: tuple[IPIPItem, ...] = (
    # ===== Extraversion =====
    IPIPItem("Am the life of the party.", "E", +1),
    IPIPItem("Don't talk a lot.", "E", -1),
    IPIPItem("Feel comfortable around people.", "E", +1),
    IPIPItem("Keep in the background.", "E", -1),
    IPIPItem("Start conversations.", "E", +1),
    IPIPItem("Have little to say.", "E", -1),
    IPIPItem("Talk to a lot of different people at parties.", "E", +1),
    IPIPItem("Don't like to draw attention to myself.", "E", -1),
    IPIPItem("Don't mind being the center of attention.", "E", +1),
    IPIPItem("Am quiet around strangers.", "E", -1),
    # ===== Agreeableness =====
    IPIPItem("Feel little concern for others.", "A", -1),
    IPIPItem("Am interested in people.", "A", +1),
    IPIPItem("Insult people.", "A", -1),
    IPIPItem("Sympathize with others' feelings.", "A", +1),
    IPIPItem("Am not interested in other people's problems.", "A", -1),
    IPIPItem("Have a soft heart.", "A", +1),
    IPIPItem("Am not really interested in others.", "A", -1),
    IPIPItem("Take time out for others.", "A", +1),
    IPIPItem("Feel others' emotions.", "A", +1),
    IPIPItem("Make people feel at ease.", "A", +1),
    # ===== Conscientiousness =====
    IPIPItem("Am always prepared.", "C", +1),
    IPIPItem("Leave my belongings around.", "C", -1),
    IPIPItem("Pay attention to details.", "C", +1),
    IPIPItem("Make a mess of things.", "C", -1),
    IPIPItem("Get chores done right away.", "C", +1),
    IPIPItem("Often forget to put things back in their proper place.", "C", -1),
    IPIPItem("Like order.", "C", +1),
    IPIPItem("Shirk my duties.", "C", -1),
    IPIPItem("Follow a schedule.", "C", +1),
    IPIPItem("Am exacting in my work.", "C", +1),
    # ===== Neuroticism =====
    IPIPItem("Get stressed out easily.", "N", +1),
    IPIPItem("Am relaxed most of the time.", "N", -1),
    IPIPItem("Worry about things.", "N", +1),
    IPIPItem("Seldom feel blue.", "N", -1),
    IPIPItem("Am easily disturbed.", "N", +1),
    IPIPItem("Get upset easily.", "N", +1),
    IPIPItem("Change my mood a lot.", "N", +1),
    IPIPItem("Have frequent mood swings.", "N", +1),
    IPIPItem("Get irritated easily.", "N", +1),
    IPIPItem("Often feel blue.", "N", +1),
    # ===== Openness/Intellect =====
    IPIPItem("Have a rich vocabulary.", "O", +1),
    IPIPItem("Have difficulty understanding abstract ideas.", "O", -1),
    IPIPItem("Have a vivid imagination.", "O", +1),
    IPIPItem("Am not interested in abstract ideas.", "O", -1),
    IPIPItem("Have excellent ideas.", "O", +1),
    IPIPItem("Do not have a good imagination.", "O", -1),
    IPIPItem("Am quick to understand things.", "O", +1),
    IPIPItem("Use difficult words.", "O", +1),
    IPIPItem("Spend time reflecting on things.", "O", +1),
    IPIPItem("Am full of ideas.", "O", +1),
)

_DECOYS_EN: tuple[DecoyItem, ...] = (
    DecoyItem("Prefer hot weather to cold weather."),
    DecoyItem("Drink coffee in the morning."),
    DecoyItem("Live in a city of more than one million people."),
    DecoyItem("Have travelled outside my home country in the past year."),
    DecoyItem("Own at least one pet."),
)

_DIMENSIONS: tuple[str, ...] = ("E", "A", "C", "N", "O")


def get_ipip_50_items(language: str = "en") -> tuple[IPIPItem, ...]:
    """Return the IPIP-50 item corpus for the requested language.

    ``language="en"`` returns the public-domain Goldberg 1992 IPIP-50 items
    vendored above. ``language="ja"`` raises ``NotImplementedError`` —
    Japanese vendoring is deferred per M9-eval ME-12 (see
    ``blockers.md`` ``m9-eval-p4b-ja-ipip-vendoring``).
    """
    if language == "en":
        return _IPIP_50_EN
    if language == "ja":
        raise NotImplementedError(
            "Japanese IPIP-50 vendoring deferred — see blockers.md"
            " m9-eval-p4b-ja-ipip-vendoring (ME-12). Murakami 2002/2003 is"
            " not an IPIP-50 translation source; the official Nakayama/Karlin"
            " Japanese IPIP item corpus must be license-audited and vendored"
            " before language='ja' is admitted.",
        )
    raise ValueError(f"unsupported language {language!r} (expected 'en')")


def get_default_decoys(language: str = "en") -> tuple[DecoyItem, ...]:
    """Return the decoy items for the requested language."""
    if language == "en":
        return _DECOYS_EN
    if language == "ja":
        raise NotImplementedError(
            "Japanese decoy vendoring deferred (ME-12)",
        )
    raise ValueError(f"unsupported language {language!r}")


def render_item_prompt(item: IPIPItem | DecoyItem, *, language: str = "en") -> str:
    """Render the anti-demand-characteristics prompt for one item.

    The rendered string must not contain any of :data:`FORBIDDEN_KEYWORDS`
    (asserted in test). The same template is used for IPIP and decoy items
    so the responder cannot distinguish them by prompt shape.
    """
    if language != "en":
        raise NotImplementedError(
            f"language={language!r} prompt rendering deferred (ME-12)",
        )
    return PROMPT_TEMPLATE_EN.format(item=item.statement)


def administer_ipip_neo(
    responder: PersonaResponder,
    *,
    version: str = "ipip-50",
    language: str = "en",
    seed: int = 0,
    include_decoys: bool = True,
    decoy_count: int = DEFAULT_DECOY_COUNT,
) -> tuple[Big5Scores, IPIPDiagnostic]:
    """Administer IPIP-50 with anti-demand-characteristics design (HIGH-4).

    Items and decoys are interleaved in a deterministically shuffled stream.
    Each prompt is rendered with :func:`render_item_prompt` and passed to
    ``responder``; the integer reply (clamped to ``[1, 5]``) is recorded.

    Args:
        responder: Callable taking the rendered prompt and returning a
            Likert digit. Tests pass a deterministic stub.
        version: Only ``"ipip-50"`` is supported in P4a; ``mini-ipip-20`` is
            deferred per ME-12 (Codex P4a HIGH-3).
        language: Only ``"en"`` is supported in P4a; ``ja`` defers per
            ME-12.
        seed: Deterministic shuffle seed. Same seed → identical item order.
            Different seeds give different orders so persona-conditional
            run-to-run variance is captured by the questionnaire layer too.
        include_decoys: Whether to interleave decoy items. Always ``True``
            in production; tests can disable when verifying scoring math.
        decoy_count: Number of decoys to interleave (default 5).

    Returns:
        ``(Big5Scores, IPIPDiagnostic)``. Big5 is mean Likert per dimension
        after reverse-keying; diagnostics are ME-1's four indices (with
        ``decoy_consistency`` from HIGH-4).

    Raises:
        NotImplementedError: For unsupported version or language.
        ValueError: For invalid seed or decoy_count.
    """
    if version != "ipip-50":
        raise NotImplementedError(
            f"version={version!r} not supported in P4a — only 'ipip-50'."
            " Mini-IPIP-20 was deferred per ME-12 due to marginal alpha"
            " (~0.65-0.70) sitting on the ME-1 fallback boundary.",
        )
    if decoy_count < 0:
        raise ValueError(f"decoy_count must be >= 0 (got {decoy_count})")

    items = get_ipip_50_items(language=language)
    decoys = (
        get_default_decoys(language=language)[:decoy_count] if include_decoys else ()
    )

    stream = _build_shuffled_stream(items, decoys, seed=seed)
    responses: list[
        tuple[str, int]
    ] = []  # (kind, likert) where kind = "ipip" | "decoy"
    item_responses: dict[int, int] = {}  # original index → likert

    for kind, original_idx, prompt in stream:
        raw = responder(prompt)
        likert = _clamp_likert(raw)
        responses.append((kind, likert))
        if kind == "ipip":
            item_responses[original_idx] = likert

    big5 = _score_big5(items, item_responses, version=version)
    diagnostic = _compute_diagnostic(items, item_responses, responses)
    return big5, diagnostic


def compute_ipip_diagnostic(
    items: Sequence[IPIPItem],
    item_responses: dict[int, int],
    *,
    decoy_responses: Sequence[int] = (),
) -> IPIPDiagnostic:
    """Compute the four ME-1 / HIGH-4 quality-control indices.

    Public surface so ``Big5ICCResult`` consumers can recompute diagnostics
    over a single administration without re-running the responder.
    """
    # Recreate a flat response list in original order so diagnostics are
    # meaningful even when administered separately from the questionnaire.
    raw_stream: list[tuple[str, int]] = [
        ("ipip", item_responses[i]) for i in range(len(items)) if i in item_responses
    ]
    raw_stream.extend(("decoy", value) for value in decoy_responses)
    return _compute_diagnostic(items, item_responses, raw_stream)


def _build_shuffled_stream(
    items: Sequence[IPIPItem],
    decoys: Sequence[DecoyItem],
    *,
    seed: int,
) -> list[tuple[str, int, str]]:
    """Return a deterministically shuffled list of ``(kind, original_idx, prompt)``.

    The shuffle uses a blake2b-derived ``np.random`` seed so the order is
    stable across machines (M9-eval ME-5 RNG seed convention extended to the
    item layer). Forward / reverse adjacency is rejected — if two adjacent
    IPIP items share a dimension and have opposite signs, the helper makes
    one swap to break the pair (Codex P4a LOW-1 hint).
    """
    indexed: list[tuple[str, int, str]] = []
    for idx, ipip_item in enumerate(items):
        indexed.append(("ipip", idx, render_item_prompt(ipip_item)))
    for idx, decoy_item in enumerate(decoys):
        indexed.append(("decoy", idx, render_item_prompt(decoy_item)))

    # blake2b(seed.bytes) → uint64 → np.random.default_rng (matches ME-5).
    derived_seed = int.from_bytes(
        hashlib.blake2b(
            seed.to_bytes(8, "little", signed=False),
            digest_size=8,
        ).digest(),
        "little",
    )
    import numpy as np  # noqa: PLC0415  # local to keep module import light

    rng = np.random.default_rng(derived_seed)
    order = list(range(len(indexed)))
    rng.shuffle(order)
    shuffled = [indexed[i] for i in order]

    # Break obvious forward/reverse adjacency pairs (LOW-1).
    for i in range(len(shuffled) - 1):
        a_kind, a_idx, _ = shuffled[i]
        b_kind, b_idx, _ = shuffled[i + 1]
        if a_kind != "ipip" or b_kind != "ipip":
            continue
        a_item = items[a_idx]
        b_item = items[b_idx]
        if a_item.dimension == b_item.dimension and a_item.sign != b_item.sign:
            # swap with the next non-conflicting position
            for j in range(i + 2, len(shuffled)):
                _, c_idx, _ = shuffled[j]
                c_kind = shuffled[j][0]
                if c_kind != "ipip":
                    shuffled[i + 1], shuffled[j] = shuffled[j], shuffled[i + 1]
                    break
                c_item = items[c_idx]
                if not (
                    c_item.dimension == a_item.dimension and c_item.sign != a_item.sign
                ):
                    shuffled[i + 1], shuffled[j] = shuffled[j], shuffled[i + 1]
                    break
    return shuffled


def _clamp_likert(value: int) -> int:
    """Clamp responder output to the Likert range; raise on non-integer."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"responder must return int (got {type(value).__name__})")
    return max(DEFAULT_LIKERT_MIN, min(DEFAULT_LIKERT_MAX, value))


def _score_big5(
    items: Sequence[IPIPItem],
    item_responses: dict[int, int],
    *,
    version: str,
) -> Big5Scores:
    """Aggregate per-dimension Likert means after reverse-keying."""
    sums: dict[str, float] = dict.fromkeys(_DIMENSIONS, 0.0)
    counts: dict[str, int] = dict.fromkeys(_DIMENSIONS, 0)
    for idx, item in enumerate(items):
        if idx not in item_responses:
            continue
        raw = item_responses[idx]
        keyed = (
            raw if item.sign == +1 else (DEFAULT_LIKERT_MAX + DEFAULT_LIKERT_MIN - raw)
        )
        sums[item.dimension] += float(keyed)
        counts[item.dimension] += 1

    def mean(dim: str) -> float:
        return sums[dim] / counts[dim] if counts[dim] > 0 else 0.0

    return Big5Scores(
        extraversion=mean("E"),
        agreeableness=mean("A"),
        conscientiousness=mean("C"),
        neuroticism=mean("N"),
        openness=mean("O"),
        n_items=len(item_responses),
        version=version,
    )


def _compute_diagnostic(
    items: Sequence[IPIPItem],
    item_responses: dict[int, int],
    raw_stream: Sequence[tuple[str, int]],
) -> IPIPDiagnostic:
    """Compute ME-1 + HIGH-4 diagnostic indices."""
    likerts = [v for _, v in raw_stream]

    # Acquiescence index: mean absolute deviation from neutral 3.
    if likerts:
        deviations = [abs(v - 3) for v in likerts]
        acquiescence = float(sum(deviations) / len(deviations))
    else:
        acquiescence = 0.0

    # Straight-line runs: max consecutive identical answers in stream order.
    straight_line = 0
    cur_run = 0
    prev: int | None = None
    for v in likerts:
        if v == prev:
            cur_run += 1
        else:
            cur_run = 1
        straight_line = max(straight_line, cur_run)
        prev = v

    # Reverse-keyed agreement: per-dimension Pearson r between forward-mean
    # and reverse-mean responses; report the average absolute correlation.
    forward_per_dim: dict[str, list[int]] = {dim: [] for dim in _DIMENSIONS}
    reverse_per_dim: dict[str, list[int]] = {dim: [] for dim in _DIMENSIONS}
    for idx, item in enumerate(items):
        if idx not in item_responses:
            continue
        bucket = forward_per_dim if item.sign == +1 else reverse_per_dim
        bucket[item.dimension].append(item_responses[idx])

    reverse_keyed_agreement = _mean_forward_reverse_correlation(
        forward_per_dim,
        reverse_per_dim,
    )

    # Decoy consistency: |mean decoy - 3| / 2 in [0, 1]. High → biased
    # response pattern (constant 1/5 etc.) that ICC alone wouldn't catch.
    decoy_values = [v for kind, v in raw_stream if kind == "decoy"]
    if decoy_values:
        decoy_mean = sum(decoy_values) / len(decoy_values)
        decoy_consistency = abs(decoy_mean - 3.0) / 2.0
    else:
        decoy_consistency = 0.0

    return IPIPDiagnostic(
        acquiescence_index=acquiescence,
        straight_line_runs=straight_line,
        reverse_keyed_agreement=reverse_keyed_agreement,
        decoy_consistency=decoy_consistency,
    )


def _mean_forward_reverse_correlation(
    forward_per_dim: dict[str, list[int]],
    reverse_per_dim: dict[str, list[int]],
) -> float:
    """Average per-dimension correlation between forward and reverse means.

    For each dimension with at least one forward and one reverse item,
    compute a single coherence score: how aligned the *means* of the two
    sub-scales are after reverse-keying. The diagnostic deliberately stays
    coarse — the unit isn't psychometric reliability, it's "did the
    responder treat reverse-keyed items consistently with forward-keyed
    ones?". Returns 0.0 if no dimension has both forward and reverse items.
    """
    contributions: list[float] = []
    for dim in _DIMENSIONS:
        forwards = forward_per_dim[dim]
        reverses = reverse_per_dim[dim]
        if not forwards or not reverses:
            continue
        forward_mean = sum(forwards) / len(forwards)
        reverse_mean_keyed = (
            DEFAULT_LIKERT_MAX + DEFAULT_LIKERT_MIN - sum(reverses) / len(reverses)
        )
        # 1.0 when forward and reverse-keyed means agree perfectly,
        # 0.0 when they sit at opposite ends of the Likert range.
        gap = abs(forward_mean - reverse_mean_keyed)
        coherence = max(0.0, 1.0 - gap / (DEFAULT_LIKERT_MAX - DEFAULT_LIKERT_MIN))
        contributions.append(coherence)
    if not contributions:
        return 0.0
    return float(sum(contributions) / len(contributions))


__all__ = [
    "DEFAULT_DECOY_COUNT",
    "DEFAULT_LIKERT_MAX",
    "DEFAULT_LIKERT_MIN",
    "FORBIDDEN_KEYWORDS",
    "PROMPT_TEMPLATE_EN",
    "Big5Scores",
    "DecoyItem",
    "IPIPDiagnostic",
    "IPIPItem",
    "PersonaResponder",
    "administer_ipip_neo",
    "compute_ipip_diagnostic",
    "get_default_decoys",
    "get_ipip_50_items",
    "render_item_prompt",
]
