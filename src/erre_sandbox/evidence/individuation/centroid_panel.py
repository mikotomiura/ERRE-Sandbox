"""M11-C3b multi-encoder centroid panel (the sole centroid + floor source).

The C3b GO/NO-GO ADR requires the same utterances to be re-embedded by **each**
panel encoder (mpnet / e5-large primary, bge-m3 exploratory) and the
cross-individual centroid distance scaled against a within-individual odd/even
noise floor (ADR §2.1/§4.2/§5.1). M10-0's :func:`compute_individuation` already
emits an MPNet ``semantic_centroid_distance``, but calling it N times per encoder
would (a) re-run the encoder-independent Burrows/behavioral/belief metrics N times
and (b) collide their natural keys. So the encoder loop is isolated here, in a
C3b-only layer that leaves the M10-0 hot path byte-invariant (design-final §0
seam 2, DA-M11C3b-P1-2).

Role boundary (DA-M11C3b-P1-2): **this module is the only source** of
``semantic_centroid_distance`` (per_dyad) + ``semantic_centroid_within_floor``
(per_individual) for the C3b verdict. ``compute_individuation`` remains the
source of Burrows / behavioral / belief / Vendi. The verdict scorer reads
centroid + floor from this panel's rows, Burrows from the individuation rows.

Each emitted row carries the provider's ``embedding_model_id`` in provenance, so
the panel's per-encoder rows stay distinct under the HIGH-2 natural key
(``write_individuation_rows``, embedding_model_id component, DA-M11C3b-P1-5).
"""

from __future__ import annotations

import hashlib
import itertools
from typing import TYPE_CHECKING

from erre_sandbox.evidence.individuation.layer1 import (
    MetricContext,
    semantic_centroid_distance,
    semantic_centroid_within_floor,
)
from erre_sandbox.evidence.individuation.loader import (
    IndividualWindow,
    load_individual_windows,
)
from erre_sandbox.evidence.individuation.policy import (
    DYAD_SEP,
    TICK_AGGREGATE_SENTINEL,
    AggregationLevel,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from erre_sandbox.evidence.eval_store import AnalysisView
    from erre_sandbox.evidence.individuation.layer1 import EmbeddingProvider
    from erre_sandbox.evidence.individuation.models import MetricResult


def compute_centroid_panel(
    view: AnalysisView,
    *,
    encoders: Sequence[EmbeddingProvider],
    computed_at: datetime,
    run_id: str | None = None,
) -> list[MetricResult]:
    """Centroid (per_dyad) + within-floor (per_individual) for every encoder.

    Loads each run's per-individual windows **once** (shared across encoders)
    and, for each base-persona group and each ``encoders`` provider, emits:

    * one ``semantic_centroid_distance`` per sorted same-base dyad (N=1 emits a
      degenerate self-pair, mirroring the runner), and
    * one ``semantic_centroid_within_floor`` per individual (odd/even split).

    Args:
        view: An open read-only :class:`AnalysisView`.
        encoders: The panel providers (production: ``build_embedding_provider``
            per ADR §5.1 allowlist id; tests: ``stub_embedding_provider`` with
            distinct model ids). Each provider's ``embedding_model_id`` tags its
            rows.
        computed_at: Stamp for every emitted row's ``computed_at``.
        run_id: Restrict to a single run, or ``None`` for every run in the file.

    Returns:
        A flat ``list[MetricResult]`` across all runs / groups / encoders.
    """
    results: list[MetricResult] = []
    for loaded in load_individual_windows(view, run_id=run_id):
        by_id = {w.individual_id: w for w in loaded.windows}
        for base, members in loaded.base_groups:
            for provider in encoders:
                results.extend(
                    _dyad_centroid_rows(base, members, by_id, provider, computed_at)
                )
                for member in members:
                    win = by_id[member]
                    results.append(
                        semantic_centroid_within_floor(
                            win.utterances,
                            provider=provider,
                            ctx=_individual_context(win),
                            computed_at=computed_at,
                        )
                    )
    return results


def _dyad_centroid_rows(
    base: str,
    members: tuple[str, ...],
    by_id: dict[str, IndividualWindow],
    provider: EmbeddingProvider,
    computed_at: datetime,
) -> list[MetricResult]:
    """Per-dyad centroid rows for one base group / one encoder (mirrors runner)."""
    dyad_base = f"{base}{DYAD_SEP}{base}"
    if len(members) == 1:
        only = by_id[members[0]]
        dctx = _dyad_context(
            individual_id=f"{members[0]}{DYAD_SEP}{members[0]}",
            base_persona_id=dyad_base,
            windows=[only],
        )
        return [
            semantic_centroid_distance(
                only.utterances,
                None,
                provider=provider,
                ctx=dctx,
                computed_at=computed_at,
            )
        ]
    rows: list[MetricResult] = []
    for a, b in itertools.combinations(sorted(members), 2):
        win_a, win_b = by_id[a], by_id[b]
        dctx = _dyad_context(
            individual_id=f"{a}{DYAD_SEP}{b}",
            base_persona_id=dyad_base,
            windows=[win_a, win_b],
        )
        rows.append(
            semantic_centroid_distance(
                win_a.utterances,
                win_b.utterances,
                provider=provider,
                ctx=dctx,
                computed_at=computed_at,
            )
        )
    return rows


def _individual_context(win: IndividualWindow) -> MetricContext:
    return MetricContext(
        run_id=win.run_id,
        individual_id=win.individual_id,
        base_persona_id=win.base_persona_id,
        aggregation_level=AggregationLevel.PER_INDIVIDUAL,
        tick=TICK_AGGREGATE_SENTINEL,
        source_epoch_phase=win.epoch_phase,
        source_individual_layer_enabled=win.individual_layer_enabled,
        source_filter_hash=win.source_filter_hash,
    )


def _dyad_context(
    *,
    individual_id: str,
    base_persona_id: str,
    windows: list[IndividualWindow],
) -> MetricContext:
    return MetricContext(
        run_id=windows[0].run_id,
        individual_id=individual_id,
        base_persona_id=base_persona_id,
        aggregation_level=AggregationLevel.PER_DYAD,
        tick=TICK_AGGREGATE_SENTINEL,
        source_epoch_phase=windows[0].epoch_phase,
        source_individual_layer_enabled=any(
            w.individual_layer_enabled for w in windows
        ),
        source_filter_hash=_combine_hash([w.source_filter_hash for w in windows]),
    )


def _combine_hash(hashes: list[str]) -> str:
    """Deterministic combined provenance hash for a multi-window dyad scope.

    Mirrors ``runner._combine_hash`` so a panel per_dyad row's provenance hash
    matches the convention the M10-0 runner uses for the same dyad window pair
    (the verdict scorer keys on embedding_model_id, not this hash, but keeping
    the formula parallel avoids two divergent provenance conventions).
    """
    joined = "\x1f".join(sorted(hashes))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


__all__ = ["compute_centroid_panel"]
