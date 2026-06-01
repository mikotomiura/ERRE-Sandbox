"""Orchestration: assemble all M10-0 individuation metric rows for a run.

``compute_individuation`` sequences loader → layer1 → Layer 2 pins and emits a
flat ``list[MetricResult]`` across three aggregation scopes:

* **per_individual** — burrows, the two behavioral rate metrics, zone, belief,
  recovery, plus the three Layer 2 ``cite_belief_discipline`` unsupported pins.
* **per_dyad** — centroid + SWM Jaccard over the *same-base* group. N=1 (the
  M10-0 golden case: one individual per base per run) emits a degenerate
  self-pair; N>=2 emits one row per sorted pair.
* **population** — Vendi diversity within each base persona.

No ``run``-scope rows are emitted (reserved for cross-metric correlation). The runner
owns provenance assembly (combined ``source_filter_hash`` for multi-window
scopes) and the burrows language/reference + preferred-zones resolution, so
layer1 stays pure (DA-M10I-10/11/14).
"""

from __future__ import annotations

import hashlib
import itertools
from dataclasses import dataclass, field, replace
from datetime import datetime  # noqa: TC003  # runtime use in dataclass field
from pathlib import Path  # noqa: TC003  # runtime use in dataclass field
from typing import TYPE_CHECKING

from erre_sandbox.evidence.individuation.cite_belief import all_cite_belief_pins
from erre_sandbox.evidence.individuation.individual_state_metrics import (
    development_stage_ordinal,
    narrative_coherence,
)
from erre_sandbox.evidence.individuation.layer1 import (
    MetricContext,
    action_adherence_rate,
    belief_variance,
    burrows_base_retention,
    cognitive_habit_recall_rate,
    intervention_recovery_rate,
    semantic_centroid_distance,
    vendi_diversity,
    world_model_overlap_jaccard,
    zone_behavior_consistency,
)
from erre_sandbox.evidence.individuation.loader import (
    IndividualStateWindow,
    IndividualWindow,
    build_development_source_filter_hash,
    build_narrative_source_filter_hash,
    build_world_model_overlap_source_filter_hash,
    individual_state_trace_table,
    load_individual_state_windows,
    load_individual_windows,
)
from erre_sandbox.evidence.individuation.policy import (
    DYAD_SEP,
    RESERVED_POPULATION_ID,
    TICK_AGGREGATE_SENTINEL,
    AggregationLevel,
)
from erre_sandbox.evidence.individuation.world_model_metrics import (
    world_model_overlap_jaccard_active,
)
from erre_sandbox.evidence.tier_a.burrows import tokenise_ja

if TYPE_CHECKING:
    from collections.abc import Callable

    from erre_sandbox.evidence.eval_store import AnalysisView
    from erre_sandbox.evidence.individuation.layer1 import EmbeddingProvider
    from erre_sandbox.evidence.individuation.models import MetricResult
    from erre_sandbox.evidence.tier_a.burrows import BurrowsReference


def _default_language_resolver(window: IndividualWindow) -> str:  # noqa: ARG001
    """M10-0 golden utterances are Japanese → burrows runs via the ja adapter.

    Injectable so unit tests / future en-de corpora can drive other branches.
    """
    return "ja"


def _default_burrows_reference(
    persona_id: str, language: str
) -> BurrowsReference | None:
    """Resolve a registered Burrows reference, or ``None`` if unavailable.

    The provider contract is "return ``None`` when the ``(persona_id, language)``
    pair has no registered reference (unregistered or unsupported)". Resolved for
    every language now (M11-C3a wired ja through the ``tokenise_ja`` adapter), so
    an injected provider must honour the same None-on-missing contract.
    """
    from erre_sandbox.evidence.reference_corpus.loader import (  # noqa: PLC0415
        ReferenceCorpusMissingError,
        load_reference,
    )

    try:
        return load_reference(persona_id, language)
    except ReferenceCorpusMissingError:
        return None


@dataclass(frozen=True, slots=True)
class IndividuationContext:
    """Inputs the runner needs that are not in the captured rows."""

    personas_dir: Path
    provider: EmbeddingProvider
    computed_at: datetime
    language_resolver: Callable[[IndividualWindow], str] = field(
        default=_default_language_resolver
    )
    burrows_reference_provider: Callable[[str, str], BurrowsReference | None] = field(
        default=_default_burrows_reference
    )


def compute_individuation(
    view: AnalysisView,
    *,
    run_id: str | None = None,
    ctx: IndividuationContext,
) -> list[MetricResult]:
    """Compute every Layer 1 + Layer 2 metric row for the run(s) in *view*."""
    results: list[MetricResult] = []
    zone_cache: dict[str, frozenset[str] | None] = {}
    # M11-C2: final-tick belief snapshot per individual (empty mapping when the
    # trace table is absent — a flag-off run never creates it, so belief_variance
    # falls back to the unchanged None -> unsupported path).
    trace_windows = load_individual_state_windows(view, run_id=run_id)
    for loaded in load_individual_windows(view, run_id=run_id):
        by_id = {w.individual_id: w for w in loaded.windows}
        for win in loaded.windows:
            results.extend(_per_individual_metrics(win, ctx, zone_cache, trace_windows))
        for base, members in loaded.base_groups:
            results.extend(_per_dyad_metrics(base, members, by_id, ctx, trace_windows))
            results.append(_population_vendi(base, members, by_id, ctx))
    return results


def _per_individual_metrics(
    win: IndividualWindow,
    ctx: IndividuationContext,
    zone_cache: dict[str, frozenset[str] | None],
    trace_windows: dict[tuple[str, str], IndividualStateWindow],
) -> list[MetricResult]:
    mctx = MetricContext(
        run_id=win.run_id,
        individual_id=win.individual_id,
        base_persona_id=win.base_persona_id,
        aggregation_level=AggregationLevel.PER_INDIVIDUAL,
        tick=TICK_AGGREGATE_SENTINEL,
        source_epoch_phase=win.epoch_phase,
        source_individual_layer_enabled=win.individual_layer_enabled,
        source_filter_hash=win.source_filter_hash,
    )
    # M11-C2: belief_variance reads the final-tick trace snapshot when present,
    # with trace-aware provenance (source_table + hash). Absent
    # trace -> None -> unsupported, with the unchanged raw_dialog provenance.
    # M10-A S2 (E3): the two diagnostic metrics read the final-tick narrative /
    # development substrate with their OWN per-metric provenance hash (never the
    # belief payload, DA-S2-6). Their substrate is the trace table, so even when
    # the trace is absent they stamp the (absent) trace table — never raw_dialog —
    # with final_tick=None marking "no trace" (DA-S2-6 / Codex CX3).
    trace = trace_windows.get((win.run_id, win.individual_id))
    trace_table = individual_state_trace_table()
    if trace is not None:
        belief_ctx = replace(
            mctx,
            source_table=trace.source_table,
            source_filter_hash=trace.source_filter_hash,
        )
        belief_input = (
            list(trace.belief_classes) if trace.belief_classes is not None else None
        )
        narrative_ctx = replace(
            mctx,
            source_table=trace.source_table,
            source_filter_hash=trace.narrative_source_filter_hash,
        )
        development_ctx = replace(
            mctx,
            source_table=trace.source_table,
            source_filter_hash=trace.development_source_filter_hash,
        )
        coherence_input = trace.coherence_score
        stage_input = trace.development_stage
    else:
        belief_ctx = mctx
        belief_input = None
        narrative_ctx = replace(
            mctx,
            source_table=trace_table,
            source_filter_hash=build_narrative_source_filter_hash(
                run_id=win.run_id,
                individual_id=win.individual_id,
                source_table=trace_table,
                final_tick=None,
                coherence_score=None,
                arc_segment_count=None,
            ),
        )
        development_ctx = replace(
            mctx,
            source_table=trace_table,
            source_filter_hash=build_development_source_filter_hash(
                run_id=win.run_id,
                individual_id=win.individual_id,
                source_table=trace_table,
                final_tick=None,
                development_stage=None,
            ),
        )
        coherence_input = None
        stage_input = None
    language = ctx.language_resolver(win)
    reference = ctx.burrows_reference_provider(win.base_persona_id, language)
    # ja has no built-in whitespace tokeniser. Pre-tokenise it with the shared
    # longest-match particle tokeniser (the single source that also built
    # reference_corpus/vectors.json) and feed the result via preprocessed_tokens
    # so the runtime test text and the committed profile use one tokenisation
    # convention (M11-C3a / DA-M11C-4: no SudachiPy). ``reference.function_words``
    # carries the closed particle list; en/de keep the built-in tokeniser. ja is
    # the only non-whitespace language wired here (rikyu ja pilot, DA-M11C-8).
    # The joined text passed to burrows_base_retention below is ignored once
    # preprocessed_tokens is non-None (compute_burrows_delta contract), so the
    # two joins need not be byte-identical.
    burrows_tokens: list[str] | None = None
    if language == "ja" and reference is not None:
        burrows_tokens = tokenise_ja(" ".join(win.utterances), reference.function_words)
    if win.base_persona_id not in zone_cache:
        zone_cache[win.base_persona_id] = _resolve_preferred_zones(
            ctx.personas_dir, win.base_persona_id
        )
    preferred_zones = zone_cache[win.base_persona_id]

    results = [
        burrows_base_retention(
            win.utterances,
            language=language,
            reference=reference,
            ctx=mctx,
            computed_at=ctx.computed_at,
            preprocessed_tokens=burrows_tokens,
        ),
        # M10-0 golden has no habit-fire / action channel (mode empty) -> None.
        cognitive_habit_recall_rate(None, ctx=mctx, computed_at=ctx.computed_at),
        action_adherence_rate(None, ctx=mctx, computed_at=ctx.computed_at),
        zone_behavior_consistency(
            win.zones, preferred_zones, ctx=mctx, computed_at=ctx.computed_at
        ),
        # M11-C2: final-tick promoted-belief class set (trace) or None (no trace).
        belief_variance(belief_input, ctx=belief_ctx, computed_at=ctx.computed_at),
        intervention_recovery_rate(ctx=mctx, computed_at=ctx.computed_at),
        # M10-A S2 (E3): NarrativeArc / DevelopmentState diagnostic metrics from
        # the final-tick trace (None -> unsupported, corrupt value -> fail-fast).
        narrative_coherence(
            coherence_input, ctx=narrative_ctx, computed_at=ctx.computed_at
        ),
        development_stage_ordinal(
            stage_input, ctx=development_ctx, computed_at=ctx.computed_at
        ),
    ]
    results.extend(
        all_cite_belief_pins(
            run_id=win.run_id,
            individual_id=win.individual_id,
            base_persona_id=win.base_persona_id,
            source_epoch_phase=win.epoch_phase,
            source_individual_layer_enabled=win.individual_layer_enabled,
            computed_at=ctx.computed_at,
        )
    )
    return results


def _per_dyad_metrics(
    base: str,
    members: tuple[str, ...],
    by_id: dict[str, IndividualWindow],
    ctx: IndividuationContext,
    trace_windows: dict[tuple[str, str], IndividualStateWindow],
) -> list[MetricResult]:
    results: list[MetricResult] = []
    dyad_base = f"{base}{DYAD_SEP}{base}"
    if len(members) == 1:
        only = by_id[members[0]]
        dctx = _dyad_context(
            individual_id=f"{members[0]}{DYAD_SEP}{members[0]}",
            base_persona_id=dyad_base,
            windows=[only],
        )
        results.append(
            semantic_centroid_distance(
                only.utterances,
                None,
                provider=ctx.provider,
                ctx=dctx,
                computed_at=ctx.computed_at,
            )
        )
        # M10-A S3 (E2b): a self-pair (N=1) is never the active VALID=1.0 cell —
        # it stays the frozen layer1 stub (unsupported), DA-S3-3 / C-2.
        results.append(
            world_model_overlap_jaccard(ctx=dctx, computed_at=ctx.computed_at)
        )
        return results
    for a, b in itertools.combinations(sorted(members), 2):
        win_a, win_b = by_id[a], by_id[b]
        dctx = _dyad_context(
            individual_id=f"{a}{DYAD_SEP}{b}",
            base_persona_id=dyad_base,
            windows=[win_a, win_b],
        )
        results.append(
            semantic_centroid_distance(
                win_a.utterances,
                win_b.utterances,
                provider=ctx.provider,
                ctx=dctx,
                computed_at=ctx.computed_at,
            )
        )
        results.append(
            _world_model_overlap_result(
                win_a, win_b, dctx=dctx, ctx=ctx, trace=trace_windows
            )
        )
    return results


def _world_model_overlap_result(
    win_a: IndividualWindow,
    win_b: IndividualWindow,
    *,
    dctx: MetricContext,
    ctx: IndividuationContext,
    trace: dict[tuple[str, str], IndividualStateWindow],
) -> MetricResult:
    """SWM key-Jaccard for a 2-distinct-individual dyad (M10-A S3 E2b, DA-S3-1/3).

    Active when **both** individuals have a present SWM key-set (``world_model_keys``
    not None) — stamping the trace table + a world-model-specific provenance hash
    (DA-S3-2 / C-1). Absent SWM on either side routes to the frozen ``layer1`` stub
    (unsupported), so the never-VALID claim continues to hold when input is absent.
    """
    trace_a = trace.get((win_a.run_id, win_a.individual_id))
    trace_b = trace.get((win_b.run_id, win_b.individual_id))
    if (
        trace_a is not None
        and trace_b is not None
        and trace_a.world_model_keys is not None
        and trace_b.world_model_keys is not None
    ):
        source_table = individual_state_trace_table()
        active_ctx = replace(
            dctx,
            source_table=source_table,
            source_filter_hash=build_world_model_overlap_source_filter_hash(
                run_id=dctx.run_id,
                source_table=source_table,
                members=(
                    (
                        trace_a.individual_id,
                        trace_a.final_tick,
                        trace_a.world_model_keys,
                    ),
                    (
                        trace_b.individual_id,
                        trace_b.final_tick,
                        trace_b.world_model_keys,
                    ),
                ),
            ),
        )
        return world_model_overlap_jaccard_active(
            trace_a.world_model_keys,
            trace_b.world_model_keys,
            ctx=active_ctx,
            computed_at=ctx.computed_at,
        )
    return world_model_overlap_jaccard(ctx=dctx, computed_at=ctx.computed_at)


def _population_vendi(
    base: str,
    members: tuple[str, ...],
    by_id: dict[str, IndividualWindow],
    ctx: IndividuationContext,
) -> MetricResult:
    windows = [by_id[m] for m in members]
    utterances = [u for w in windows for u in w.utterances]
    pctx = MetricContext(
        run_id=windows[0].run_id,
        individual_id=RESERVED_POPULATION_ID,
        base_persona_id=base,
        aggregation_level=AggregationLevel.POPULATION,
        tick=TICK_AGGREGATE_SENTINEL,
        source_epoch_phase=windows[0].epoch_phase,
        source_individual_layer_enabled=any(
            w.individual_layer_enabled for w in windows
        ),
        source_filter_hash=_combine_hash([w.source_filter_hash for w in windows]),
    )
    return vendi_diversity(
        utterances, provider=ctx.provider, ctx=pctx, computed_at=ctx.computed_at
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
    """Deterministic combined provenance hash for a multi-window scope."""
    joined = "\x1f".join(sorted(hashes))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _resolve_preferred_zones(
    personas_dir: Path, base_persona_id: str
) -> frozenset[str] | None:
    """Persona's preferred zones as a string set, or ``None`` if unavailable."""
    from erre_sandbox.evidence.source_navigator.compiler import (  # noqa: PLC0415
        load_persona_spec,
    )

    try:
        spec = load_persona_spec(personas_dir, base_persona_id)
    except (FileNotFoundError, OSError):
        return None
    return frozenset(str(z) for z in spec.preferred_zones)


__all__ = [
    "IndividuationContext",
    "compute_individuation",
]
