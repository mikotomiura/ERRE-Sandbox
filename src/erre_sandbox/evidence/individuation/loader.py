"""WP5 loader: per-individual utterance windows from ``raw_dialog.dialog``.

This is the **only** module that touches captured data. It is a pure
raw-row extractor: it opens nothing itself (it takes an already-opened
:class:`~erre_sandbox.evidence.eval_store.AnalysisView`), it constructs no
:class:`~erre_sandbox.evidence.individuation.models.MetricResult`, and it
imports neither ``models`` nor ``policy`` — keeping the contamination
surface tiny and auditable (decisions DA-M10I-10).

Two defences run at the row boundary, mirroring
``eval_store._DuckDBRawTrainingRelation.iter_rows``:

* :func:`~erre_sandbox.contracts.eval_paths.assert_no_metrics_leak` over the
  projected column names (a metric-shaped key would raise), and
* :func:`~erre_sandbox.contracts.eval_paths.assert_no_sentinel_leak` over the
  row values (a planted ``M9_EVAL_SENTINEL_LEAK_*`` value would raise).

A window spans the **whole run** for one individual. ``epoch_phase`` is a
single value in the M10-0 golden (``"autonomous"``), so an epoch split would
be dead code; instead an individual that ever spans >1 epoch raises
:class:`IndividuationLoaderError` so M10-A's ``"evaluation"`` rows fail loudly
rather than being silently averaged across epochs.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, TypeVar, cast

from erre_sandbox.contracts.eval_paths import (
    METRICS_SCHEMA,
    assert_no_metrics_leak,
    assert_no_sentinel_leak,
)
from erre_sandbox.evidence.individuation.trace_ddl import (
    TABLE_NAME as _INDIVIDUAL_STATE_TRACE_TABLE,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from erre_sandbox.evidence.eval_store import AnalysisView

# Schema version stamped into the source_filter_hash payload so a future
# loader revision perturbs every hash (honest provenance). Kept local rather
# than importing policy — loader stays models/policy-free.
_LOADER_HASH_SCHEMA_VERSION: Final[str] = "m10-0.loader.1"

# Projected columns — a strict subset of ALLOWED_RAW_DIALOG_KEYS. Order here
# is the SELECT order and the tuple-unpack order below; keep them in lockstep.
_PROJECTION: Final[tuple[str, ...]] = (
    "run_id",
    "speaker_agent_id",
    "speaker_persona_id",
    "tick",
    "turn_index",
    "utterance",
    "zone",
    "epoch_phase",
    "individual_layer_enabled",
)


class IndividuationLoaderError(RuntimeError):
    """Raised when a window cannot be formed from a structurally invalid run.

    The load-bearing case is an individual whose rows span more than one
    ``epoch_phase``: M10-0 windows are epoch-homogeneous by contract, so this
    is a loud failure rather than a silent cross-epoch average.
    """


@dataclass(frozen=True, slots=True)
class IndividualWindow:
    """One individual's whole-run utterance window (ordered, immutable)."""

    run_id: str
    individual_id: str  # speaker_agent_id
    base_persona_id: str  # speaker_persona_id
    utterances: tuple[str, ...]
    ticks: tuple[int, ...]  # parallel to utterances
    zones: tuple[str, ...]  # parallel to utterances ('' tolerated)
    epoch_phase: str  # single value (raises if mixed within the individual)
    individual_layer_enabled: bool
    source_filter_hash: str  # sha256 hex of the canonical projection payload


@dataclass(frozen=True, slots=True)
class LoadedRun:
    """All individuals captured in one ``run_id``."""

    run_id: str
    windows: tuple[IndividualWindow, ...]
    base_groups: tuple[tuple[str, tuple[str, ...]], ...]
    """``(base_persona_id, sorted individual_id tuple)`` for same-base scopes."""


def _source_filter_hash(
    *,
    run_id: str,
    individual_id: str,
    epoch_phase: str,
    individual_layer_enabled: bool,
    tick_lo: int,
    tick_hi: int,
) -> str:
    """Deterministic sha256 of the canonical projection payload.

    Mirrors the canonical-JSON-then-sha256 pattern in
    ``source_navigator/compiler.py``. The projection is embedded so a column
    set change perturbs the hash.
    """
    payload = {
        "schema_version": _LOADER_HASH_SCHEMA_VERSION,
        "run_id": run_id,
        "individual_id": individual_id,
        "epoch_phase": epoch_phase,
        "individual_layer_enabled": individual_layer_enabled,
        "tick_lo": tick_lo,
        "tick_hi": tick_hi,
        "projection": list(_PROJECTION),
    }
    canonical = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_individual_windows(
    view: AnalysisView,
    *,
    run_id: str | None = None,
) -> Iterator[LoadedRun]:
    """Yield one :class:`LoadedRun` per ``run_id`` present in the file.

    Args:
        view: An open read-only analysis view (``connect_analysis_view``).
        run_id: Restrict to a single run, or ``None`` for every run in the file.

    Raises:
        IndividuationLoaderError: An individual spans more than one epoch phase.
        EvaluationContaminationError: A metric-shaped key or sentinel value
            appears in the projected rows.
    """
    # Contamination defence on the (constant) projected key set — fail before
    # any row is materialised into a window.
    assert_no_metrics_leak(_PROJECTION, context="individuation.loader.projection")

    projection_sql = ", ".join(_PROJECTION)
    sql = f"SELECT {projection_sql} FROM raw_dialog.dialog"  # noqa: S608  # static identifiers only
    params: tuple[object, ...] | None = None
    if run_id is not None:
        sql += " WHERE run_id = ?"
        params = (run_id,)
    sql += " ORDER BY run_id, speaker_agent_id, tick, turn_index"

    rows = view.execute(sql, params)

    # Group rows by run_id, then by speaker_agent_id, preserving sort order.
    runs: dict[str, dict[str, list[tuple[object, ...]]]] = {}
    for row in rows:
        assert_no_sentinel_leak(row, context="individuation.loader.row")
        r_run_id = str(row[0])
        agent_id = str(row[1])
        runs.setdefault(r_run_id, {}).setdefault(agent_id, []).append(row)

    for r_run_id, agents in runs.items():
        windows: list[IndividualWindow] = []
        base_to_individuals: dict[str, list[str]] = {}
        for agent_id, agent_rows in agents.items():
            window = _build_window(r_run_id, agent_id, agent_rows)
            windows.append(window)
            base_to_individuals.setdefault(window.base_persona_id, []).append(
                window.individual_id
            )
        base_groups = tuple(
            (base, tuple(sorted(members)))
            for base, members in sorted(base_to_individuals.items())
        )
        yield LoadedRun(
            run_id=r_run_id,
            windows=tuple(windows),
            base_groups=base_groups,
        )


def _build_window(
    run_id: str,
    agent_id: str,
    agent_rows: list[tuple[object, ...]],
) -> IndividualWindow:
    """Assemble one individual's epoch-homogeneous whole-run window."""
    base_persona_id = str(agent_rows[0][2])
    epochs = {str(row[7]) for row in agent_rows}
    if len(epochs) > 1:
        msg = (
            f"individual {agent_id!r} in run {run_id!r} spans multiple"
            f" epoch phases {sorted(epochs)}; M10-0 windows are"
            " epoch-homogeneous (M10-A 'evaluation' rows must be split upstream)"
        )
        raise IndividuationLoaderError(msg)
    epoch_phase = epochs.pop()

    utterances = tuple(str(row[5]) for row in agent_rows)
    # tick is a DuckDB INTEGER column -> Python int; cast satisfies the
    # object-typed AnalysisView row tuple without a runtime conversion.
    ticks = tuple(cast("int", row[3]) for row in agent_rows)
    zones = tuple(str(row[6]) for row in agent_rows)
    # Any truthy individual_layer_enabled in the window flags the individual.
    layer_enabled = any(bool(row[8]) for row in agent_rows)
    tick_lo = min(ticks) if ticks else -1
    tick_hi = max(ticks) if ticks else -1

    return IndividualWindow(
        run_id=run_id,
        individual_id=agent_id,
        base_persona_id=base_persona_id,
        utterances=utterances,
        ticks=ticks,
        zones=zones,
        epoch_phase=epoch_phase,
        individual_layer_enabled=layer_enabled,
        source_filter_hash=_source_filter_hash(
            run_id=run_id,
            individual_id=agent_id,
            epoch_phase=epoch_phase,
            individual_layer_enabled=layer_enabled,
            tick_lo=tick_lo,
            tick_hi=tick_hi,
        ),
    )


# ---------------------------------------------------------------------------
# M11-C2: individual_state_trace reader (metrics schema, NOT raw_dialog egress)
# ---------------------------------------------------------------------------
#
# This reader intentionally reads the ``metrics`` schema (the trace table the
# eval orchestrator writes flag-on), so the raw_dialog egress contamination
# guards above do NOT apply here — it is a sanctioned metrics reader, like
# ``AnalysisView`` itself. The qualified name is composed from the
# ``METRICS_SCHEMA`` constant + the trace module's ``TABLE_NAME`` (never a
# schema-dot literal; CI eval-egress grep gate).

# Bumped independently of the raw_dialog loader so a trace-schema change
# perturbs only the belief_variance provenance hash.
_TRACE_LOADER_HASH_SCHEMA_VERSION: Final[str] = "m11-c2.trace_loader.1"


class IndividualStateTraceConflictError(RuntimeError):
    """Raised when an individual's max-tick has divergent trace rows.

    The trace DDL does not enforce ``(run_id, individual_id, tick)`` uniqueness.
    One row per tick is the contract; if two rows share the
    final tick with *different* ``belief_classes_json`` **or**
    ``world_model_keys_json`` the final-tick belief / SWM set (DA-M11C2-8 /
    M10-A E2 C5a) is ambiguous, so we fail loud rather than pick arbitrarily.
    Byte-identical duplicates collapse silently (idempotent recompute).
    """


class IndividualStateTraceSchemaError(RuntimeError):
    """Raised when a trace substrate payload is structurally corrupt.

    Two families fail fast rather than silently coerce:

    * a ``world_model_keys_json`` payload that is not a ``[["axis","key"], ...]``
      pair array (DA-S1-2 / Codex C5c), and
    * a M10-A S2 substrate value that cannot be a real measurement: a non-finite
      ``coherence_score`` or a negative ``arc_segment_count`` (DA-S2-5 / Codex
      CX4). ``None`` is *not* corrupt — it is the honest "no substrate" signal the
      diagnostic metrics degrade to ``unsupported`` on; only a present-but-broken
      value raises here.
    """


@dataclass(frozen=True, slots=True)
class IndividualStateWindow:
    """One individual's final-tick belief snapshot from ``individual_state_trace``.

    ``belief_classes`` is the **final-tick** promoted-belief class set (DA-M11C2-8,
    over-count-free), ``None`` when the final row's ``belief_classes_json`` is NULL
    (→ belief_variance unsupported). ``source_table`` / ``source_filter_hash`` feed
    the trace-aware provenance the runner stamps onto the belief_variance row.
    """

    run_id: str
    individual_id: str
    belief_classes: tuple[str, ...] | None
    final_tick: int
    source_table: str
    source_filter_hash: str
    world_model_keys: tuple[tuple[str, str], ...] | None = None
    """Final-tick SWM ``(axis, key)`` set (M10-A E2). ``None`` when no SWM was
    captured — the final row's ``world_model_keys_json`` is NULL, **or** the
    trace table predates E2 and has no ``world_model_keys_json`` column at all
    (backward compat, DA-S1-3). An empty tuple is a synthesised-but-empty SWM."""
    coherence_score: float | None = None
    """Final-tick NarrativeArc ``coherence_score`` (M10-A S2 E3); ``None`` when no
    arc was synthesised. Feeds ``narrative_coherence``."""
    development_stage: str | None = None
    """Final-tick DevelopmentState ``stage`` label (M10-A S2 E3); ``None`` when no
    stage advanced. Feeds ``development_stage_ordinal``."""
    arc_segment_count: int | None = None
    """Final-tick NarrativeArc segment count (M10-A S2 E3); part of the narrative
    provenance payload. ``None`` only in the never-constructed absent-trace case."""
    narrative_source_filter_hash: str = ""
    """Per-metric provenance hash for ``narrative_coherence`` — embeds the
    coherence_score + arc_segment_count, NOT the belief payload (DA-S2-6 / CX3)."""
    development_source_filter_hash: str = ""
    """Per-metric provenance hash for ``development_stage_ordinal`` — embeds the
    development_stage, NOT the belief payload (DA-S2-6 / CX3)."""


def _trace_source_filter_hash(
    *,
    run_id: str,
    individual_id: str,
    source_table: str,
    final_tick: int,
    belief_classes: tuple[str, ...] | None,
) -> str:
    """Deterministic sha256 of the final-tick trace projection.

    The final-tick payload (not the whole window) is embedded so the belief
    recompute provenance reflects exactly what fed ``belief_variance``, and a
    deterministic final-tick selection makes recompute hash-stable.
    """
    payload = {
        "schema_version": _TRACE_LOADER_HASH_SCHEMA_VERSION,
        "run_id": run_id,
        "individual_id": individual_id,
        "source_table": source_table,
        "final_tick": final_tick,
        "belief_classes": None if belief_classes is None else list(belief_classes),
    }
    canonical = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


_WORLD_MODEL_KEYS_COLUMN: Final[str] = "world_model_keys_json"
"""Trace column added at M10-A E2; absent in pre-E2 flag-on DuckDB files."""

_WORLD_MODEL_KEY_PAIR_LEN: Final[int] = 2

# M10-A S2 (E3): per-metric provenance hash schema-version tokens. Distinct from
# the belief token so the narrative / development recompute provenance never
# collides with belief_variance's even at the same final tick (DA-S2-6 / CX3).
_NARRATIVE_LOADER_HASH_SCHEMA_VERSION: Final[str] = "m10a-s2.narrative_loader.1"
_DEVELOPMENT_LOADER_HASH_SCHEMA_VERSION: Final[str] = "m10a-s2.development_loader.1"
# M10-A S3 (E2b): per-dyad SWM-overlap provenance token. Distinct from the belief /
# narrative / development tokens so the active world_model_overlap_jaccard recompute
# provenance never collides with another trace metric's (DA-S3-2 / C-1).
_WORLD_MODEL_OVERLAP_LOADER_HASH_SCHEMA_VERSION: Final[str] = (
    "m10a-s3.world_model_overlap_loader.1"
)
# Provenance metric-name labels (kept local; the loader stays models/policy-free).
# Must match the metric names in ``individual_state_metrics`` / ``world_model_metrics``
# / ``policy.METRIC_SPECS`` (pinned by test_individuation_trace_loader).
_NARRATIVE_METRIC_LABEL: Final[str] = "narrative_coherence"
_DEVELOPMENT_METRIC_LABEL: Final[str] = "development_stage_ordinal"
_WORLD_MODEL_OVERLAP_METRIC_LABEL: Final[str] = "world_model_overlap_jaccard"


def individual_state_trace_table() -> str:
    """Canonical qualified trace-table name (``METRICS_SCHEMA.individual_state_trace``).

    Used by the runner to stamp the **trace table** (never ``raw_dialog.dialog``)
    as the source of the M10-A S2 diagnostic metrics even when the trace is absent
    — so an unsupported narrative/development row never looks raw_dialog-derived
    (DA-S2-6 / Codex CX3).
    """
    return f"{METRICS_SCHEMA}.{_INDIVIDUAL_STATE_TRACE_TABLE}"


def _trace_metric_source_filter_hash(
    *,
    schema_version: str,
    metric_name: str,
    run_id: str,
    individual_id: str,
    source_table: str,
    final_tick: int | None,
    fields: dict[str, object],
) -> str:
    """Per-metric trace provenance sha256 (DA-S2-6 / Codex CX3).

    Embeds ``metric_name`` + identity + ``source_table`` + ``final_tick``
    (``None`` = absent trace, distinct from a real tick whose field is NULL) +
    the metric's own raw substrate ``fields``. ``allow_nan=False`` so a non-finite
    value can never be hashed and silently dropped later (Codex CX4) — the loader
    validates finiteness before calling this, so this is defence in depth.
    """
    payload = {
        "schema_version": schema_version,
        "metric_name": metric_name,
        "run_id": run_id,
        "individual_id": individual_id,
        "source_table": source_table,
        "final_tick": final_tick,
        "fields": fields,
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_narrative_source_filter_hash(
    *,
    run_id: str,
    individual_id: str,
    source_table: str,
    final_tick: int | None,
    coherence_score: float | None,
    arc_segment_count: int | None,
) -> str:
    """Provenance hash for ``narrative_coherence`` (coherence + arc-count payload)."""
    return _trace_metric_source_filter_hash(
        schema_version=_NARRATIVE_LOADER_HASH_SCHEMA_VERSION,
        metric_name=_NARRATIVE_METRIC_LABEL,
        run_id=run_id,
        individual_id=individual_id,
        source_table=source_table,
        final_tick=final_tick,
        fields={
            "coherence_score": coherence_score,
            "arc_segment_count": arc_segment_count,
        },
    )


def build_development_source_filter_hash(
    *,
    run_id: str,
    individual_id: str,
    source_table: str,
    final_tick: int | None,
    development_stage: str | None,
) -> str:
    """Provenance hash for ``development_stage_ordinal`` (stage-label payload)."""
    return _trace_metric_source_filter_hash(
        schema_version=_DEVELOPMENT_LOADER_HASH_SCHEMA_VERSION,
        metric_name=_DEVELOPMENT_METRIC_LABEL,
        run_id=run_id,
        individual_id=individual_id,
        source_table=source_table,
        final_tick=final_tick,
        fields={"development_stage": development_stage},
    )


def build_world_model_overlap_source_filter_hash(
    *,
    run_id: str,
    source_table: str,
    members: Sequence[tuple[str, int, tuple[tuple[str, str], ...] | None]],
) -> str:
    """Provenance hash for the active ``world_model_overlap_jaccard`` (E2b, C-1).

    A per-dyad metric, so the payload embeds **both** members'
    ``(individual_id, final_tick, world_model_keys)`` — the exact SWM substrate the
    Jaccard consumed — sorted by ``individual_id`` for pair symmetry. Uses its own
    schema-version token so it never collides with the belief / narrative /
    development trace hashes or the raw_dialog window hash (DA-S3-2). ``allow_nan``
    is irrelevant (no floats) but kept off for consistency with the other trace
    hashes.
    """
    member_payload: list[dict[str, object]] = sorted(
        (
            {
                "individual_id": individual_id,
                "final_tick": final_tick,
                "world_model_keys": (
                    None if keys is None else [list(pair) for pair in keys]
                ),
            }
            for individual_id, final_tick, keys in members
        ),
        key=lambda member: str(member["individual_id"]),
    )
    payload = {
        "schema_version": _WORLD_MODEL_OVERLAP_LOADER_HASH_SCHEMA_VERSION,
        "metric_name": _WORLD_MODEL_OVERLAP_METRIC_LABEL,
        "run_id": run_id,
        "source_table": source_table,
        "members": member_payload,
    }
    canonical = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _trace_has_world_model_column(view: AnalysisView) -> bool:
    """True when the trace table carries the E2 ``world_model_keys_json`` column.

    A pre-E2 flag-on DuckDB has the M11-C2 trace table but no SWM column, so the
    SELECT must omit it and the loader returns ``world_model_keys=None`` rather
    than failing on an unknown identifier (backward compat, DA-S1-3).
    """
    present = view.execute(
        "SELECT 1 FROM information_schema.columns"
        " WHERE table_schema = ? AND table_name = ? AND column_name = ?",
        (METRICS_SCHEMA, _INDIVIDUAL_STATE_TRACE_TABLE, _WORLD_MODEL_KEYS_COLUMN),
    )
    return bool(present)


def _parse_world_model_keys(
    raw_json: str | None,
) -> tuple[tuple[str, str], ...] | None:
    """Parse a ``[["axis","key"], ...]`` payload, fail-fast on a bad shape (C5c).

    ``None`` (NULL column / pre-E2 table) → ``None``. ``"[]"`` → empty tuple
    (synthesised-but-empty SWM). Any non-list payload, or an element that is not
    a 2-element list of strings, raises :class:`IndividualStateTraceSchemaError`
    — the contract is trusted-writer output, so a malformed payload is corruption,
    not a value to coerce.
    """
    if raw_json is None:
        return None
    parsed = json.loads(raw_json)
    if not isinstance(parsed, list):
        msg = f"world_model_keys_json is not a JSON array: {raw_json!r}"
        raise IndividualStateTraceSchemaError(msg)
    pairs: list[tuple[str, str]] = []
    for item in parsed:
        if (
            not isinstance(item, list)
            or len(item) != _WORLD_MODEL_KEY_PAIR_LEN
            or not all(isinstance(part, str) for part in item)
        ):
            msg = (
                "world_model_keys_json element is not a 2-string pair:"
                f" {item!r} (payload {raw_json!r})"
            )
            raise IndividualStateTraceSchemaError(msg)
        pairs.append((item[0], item[1]))
    return tuple(pairs)


def load_individual_state_windows(
    view: AnalysisView,
    *,
    run_id: str | None = None,
) -> dict[tuple[str, str], IndividualStateWindow]:
    """Final-tick belief snapshot per ``(run_id, individual_id)`` from the trace.

    Returns an empty mapping when the trace table is absent — a flag-off run
    never creates it (DA-M11C2-1), so the runner falls back to the ``None`` →
    ``unsupported`` belief_variance path unchanged. The whole-run rows for one
    individual collapse to the **final tick's** belief set (DA-M11C2-8); a
    divergent duplicate at the final tick raises
    :class:`IndividualStateTraceConflictError`.

    Args:
        view: An open read-only :class:`AnalysisView` (spans the metrics schema).
        run_id: Restrict to a single run, or ``None`` for every run.
    """
    table = f"{METRICS_SCHEMA}.{_INDIVIDUAL_STATE_TRACE_TABLE}"
    present = view.execute(
        "SELECT 1 FROM information_schema.tables"
        " WHERE table_schema = ? AND table_name = ?",
        (METRICS_SCHEMA, _INDIVIDUAL_STATE_TRACE_TABLE),
    )
    if not present:
        return {}

    # E2 (DA-S1-3): only SELECT the SWM column when it exists, so a pre-E2 trace
    # table reads cleanly with world_model_keys -> None. The M10-A S2 columns
    # (development_stage / coherence_score / arc_segment_count) exist from M11-C2,
    # so they need no backward-compat probe (unlike world_model_keys_json).
    has_swm = _trace_has_world_model_column(view)
    swm_select = f", {_WORLD_MODEL_KEYS_COLUMN}" if has_swm else ""
    sql = (
        "SELECT run_id, individual_id, tick, belief_classes_json,"  # noqa: S608  # identifiers are module constants
        f" development_stage, coherence_score, arc_segment_count{swm_select}"
        f" FROM {table}"
    )
    params: tuple[object, ...] | None = None
    if run_id is not None:
        sql += " WHERE run_id = ?"
        params = (run_id,)
    sql += " ORDER BY run_id, individual_id, tick"

    # key -> {tick: list[_TraceRowValues]} so a divergent final-tick is caught
    # per column (belief / SWM / dev / coherence / arc divergence, C5a).
    grouped: dict[tuple[str, str], dict[int, list[_TraceRowValues]]] = {}
    for row in view.execute(sql, params):
        key = (str(row[0]), str(row[1]))
        tick = cast("int", row[2])
        values = _TraceRowValues(
            belief_json=None if row[3] is None else str(row[3]),
            development_stage=None if row[4] is None else str(row[4]),
            coherence_score=None if row[5] is None else float(cast("float", row[5])),
            arc_segment_count=cast("int", row[6]),
            swm_json=None if (not has_swm or row[7] is None) else str(row[7]),
        )
        grouped.setdefault(key, {}).setdefault(tick, []).append(values)

    windows: dict[tuple[str, str], IndividualStateWindow] = {}
    for (r_run_id, individual_id), by_tick in grouped.items():
        final_tick = max(by_tick)
        final_rows = by_tick[final_tick]
        windows[(r_run_id, individual_id)] = _build_state_window(
            run_id=r_run_id,
            individual_id=individual_id,
            final_tick=final_tick,
            final_rows=final_rows,
            source_table=table,
        )
    return windows


@dataclass(frozen=True, slots=True)
class _TraceRowValues:
    """The substrate columns read from one trace row (loader-internal)."""

    belief_json: str | None
    development_stage: str | None
    coherence_score: float | None
    arc_segment_count: int
    swm_json: str | None


def _build_state_window(
    *,
    run_id: str,
    individual_id: str,
    final_tick: int,
    final_rows: list[_TraceRowValues],
    source_table: str,
) -> IndividualStateWindow:
    """Collapse one individual's final-tick rows into a window (conflict-checked).

    Each substrate column is resolved independently with :func:`_sole_final_variant`
    so a divergent duplicate at the final tick fails loud per column (C5a). The
    structural corruption checks (non-finite coherence, negative arc count) raise
    :class:`IndividualStateTraceSchemaError` before any hash is built (Codex CX4).
    """
    belief_raw = _sole_final_variant(
        {r.belief_json for r in final_rows},
        run_id=run_id,
        individual_id=individual_id,
        final_tick=final_tick,
        column="belief_classes_json",
    )
    swm_raw = _sole_final_variant(
        {r.swm_json for r in final_rows},
        run_id=run_id,
        individual_id=individual_id,
        final_tick=final_tick,
        column=_WORLD_MODEL_KEYS_COLUMN,
    )
    development_stage = _sole_final_variant(
        {r.development_stage for r in final_rows},
        run_id=run_id,
        individual_id=individual_id,
        final_tick=final_tick,
        column="development_stage",
    )
    coherence_score = _sole_final_variant(
        {r.coherence_score for r in final_rows},
        run_id=run_id,
        individual_id=individual_id,
        final_tick=final_tick,
        column="coherence_score",
    )
    arc_segment_count = _sole_final_variant(
        {r.arc_segment_count for r in final_rows},
        run_id=run_id,
        individual_id=individual_id,
        final_tick=final_tick,
        column="arc_segment_count",
    )
    # Structural corruption (present-but-broken) fails fast before hashing (CX4).
    if coherence_score is not None and not math.isfinite(coherence_score):
        msg = (
            f"individual {individual_id!r} in run {run_id!r}: non-finite"
            f" coherence_score {coherence_score!r} at final tick {final_tick}"
        )
        raise IndividualStateTraceSchemaError(msg)
    if arc_segment_count < 0:
        msg = (
            f"individual {individual_id!r} in run {run_id!r}: negative"
            f" arc_segment_count {arc_segment_count} at final tick {final_tick}"
        )
        raise IndividualStateTraceSchemaError(msg)
    belief_classes = None if belief_raw is None else tuple(json.loads(belief_raw))
    return IndividualStateWindow(
        run_id=run_id,
        individual_id=individual_id,
        belief_classes=belief_classes,
        final_tick=final_tick,
        source_table=source_table,
        source_filter_hash=_trace_source_filter_hash(
            run_id=run_id,
            individual_id=individual_id,
            source_table=source_table,
            final_tick=final_tick,
            belief_classes=belief_classes,
        ),
        world_model_keys=_parse_world_model_keys(swm_raw),
        coherence_score=coherence_score,
        development_stage=development_stage,
        arc_segment_count=arc_segment_count,
        narrative_source_filter_hash=build_narrative_source_filter_hash(
            run_id=run_id,
            individual_id=individual_id,
            source_table=source_table,
            final_tick=final_tick,
            coherence_score=coherence_score,
            arc_segment_count=arc_segment_count,
        ),
        development_source_filter_hash=build_development_source_filter_hash(
            run_id=run_id,
            individual_id=individual_id,
            source_table=source_table,
            final_tick=final_tick,
            development_stage=development_stage,
        ),
    )


_V = TypeVar("_V")


def _sole_final_variant(
    variants: set[_V],
    *,
    run_id: str,
    individual_id: str,
    final_tick: int,
    column: str,
) -> _V:
    """Return the single final-tick value for *column*, or raise on divergence.

    Byte-identical duplicates collapse (the caller passes a ``set``); two
    distinct non-collapsing values at the final tick are an ambiguous trace
    (C5a) → :class:`IndividualStateTraceConflictError`. Generic over the column
    value type (``str | None`` for belief/SWM/stage, ``float | None`` for
    coherence, ``int`` for arc count); each metric's provenance is derived from
    its own resolved value, independent of the others.
    """
    if len(variants) > 1:
        msg = (
            f"individual {individual_id!r} in run {run_id!r} has divergent"
            f" {column} at final tick {final_tick}"
            f" ({sorted(str(v) for v in variants)}); trace rows must be"
            " unique per tick (M11-C2 / M10-A E2)"
        )
        raise IndividualStateTraceConflictError(msg)
    return next(iter(variants))


__all__ = [
    "IndividualStateTraceConflictError",
    "IndividualStateTraceSchemaError",
    "IndividualStateWindow",
    "IndividualWindow",
    "IndividuationLoaderError",
    "LoadedRun",
    "build_development_source_filter_hash",
    "build_narrative_source_filter_hash",
    "build_world_model_overlap_source_filter_hash",
    "individual_state_trace_table",
    "load_individual_state_windows",
    "load_individual_windows",
]
