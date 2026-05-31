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
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, cast

from erre_sandbox.contracts.eval_paths import (
    METRICS_SCHEMA,
    assert_no_metrics_leak,
    assert_no_sentinel_leak,
)
from erre_sandbox.evidence.individuation.trace_ddl import (
    TABLE_NAME as _INDIVIDUAL_STATE_TRACE_TABLE,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

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
    final tick with *different* ``belief_classes_json`` the final-tick belief set
    (DA-M11C2-8) is ambiguous, so we fail loud rather than pick arbitrarily.
    Byte-identical duplicates collapse silently (idempotent recompute).
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

    sql = (
        "SELECT run_id, individual_id, tick, belief_classes_json"  # noqa: S608  # identifiers are module constants
        f" FROM {table}"
    )
    params: tuple[object, ...] | None = None
    if run_id is not None:
        sql += " WHERE run_id = ?"
        params = (run_id,)
    sql += " ORDER BY run_id, individual_id, tick"

    # key -> {tick: set(belief_classes_json)} so a divergent final-tick is caught.
    grouped: dict[tuple[str, str], dict[int, set[str | None]]] = {}
    for row in view.execute(sql, params):
        key = (str(row[0]), str(row[1]))
        tick = cast("int", row[2])
        raw_json = None if row[3] is None else str(row[3])
        grouped.setdefault(key, {}).setdefault(tick, set()).add(raw_json)

    windows: dict[tuple[str, str], IndividualStateWindow] = {}
    for (r_run_id, individual_id), by_tick in grouped.items():
        final_tick = max(by_tick)
        variants = by_tick[final_tick]
        if len(variants) > 1:
            msg = (
                f"individual {individual_id!r} in run {r_run_id!r} has"
                f" divergent belief_classes_json at final tick {final_tick}"
                f" ({sorted(str(v) for v in variants)}); trace rows must be"
                " unique per tick (M11-C2)"
            )
            raise IndividualStateTraceConflictError(msg)
        raw_json = variants.pop()
        belief_classes = None if raw_json is None else tuple(json.loads(raw_json))
        windows[(r_run_id, individual_id)] = IndividualStateWindow(
            run_id=r_run_id,
            individual_id=individual_id,
            belief_classes=belief_classes,
            final_tick=final_tick,
            source_table=table,
            source_filter_hash=_trace_source_filter_hash(
                run_id=r_run_id,
                individual_id=individual_id,
                source_table=table,
                final_tick=final_tick,
                belief_classes=belief_classes,
            ),
        )
    return windows


__all__ = [
    "IndividualStateTraceConflictError",
    "IndividualStateWindow",
    "IndividualWindow",
    "IndividuationLoaderError",
    "LoadedRun",
    "load_individual_state_windows",
    "load_individual_windows",
]
