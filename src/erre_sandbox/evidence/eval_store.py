"""DuckDB-backed evaluation store — m9-eval-system Phase 0 (P0b + P0c).

This module is the **implementation half** of the four-layer evaluation
contamination contract; the policy half lives in
:mod:`erre_sandbox.contracts.eval_paths`. The single training-egress
entry point is :func:`connect_training_view`, which opens a DuckDB file
read-only and returns a :class:`RawTrainingRelation` that exposes only
``raw_dialog`` rows — never the ``metrics`` schema, never an arbitrary
SQL execution surface.

P0c additions (this commit):

* :func:`bootstrap_schema` — idempotent CREATE for ``raw_dialog.dialog``
  and ``metrics.tier_{a,b,c}``. The raw column set is locked in lockstep
  with :data:`ALLOWED_RAW_DIALOG_KEYS` (module-load-time check).
* :class:`AnalysisView` + :func:`connect_analysis_view` — Mac-side
  read-only multi-schema reader for analytics / notebooks. NOT a
  training-egress route; the grep gate in CI keeps the metric schema
  reference confined to this module.
* :func:`export_raw_only_snapshot` — Parquet export of ``raw_dialog``
  only, the sanctioned route for callers that need ad-hoc SQL on raw
  rows (run the SQL against the snapshot, not the live file).
* :func:`write_with_checkpoint` and :func:`atomic_temp_rename` — the
  two ME-2 helpers that implement the G-GEAR → Mac snapshot semantics
  documented in
  ``.steering/20260430-m9-eval-system/decisions.md`` §ME-2.

Both :func:`connect_training_view` and :func:`connect_analysis_view`
open the underlying DuckDB file with ``read_only=True``. Any write
attempt against either handle (even via private attribute access) must
surface as a DuckDB error — the test suite covers both paths.
"""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Self

import duckdb

from erre_sandbox.contracts.eval_paths import (
    ALLOWED_RAW_DIALOG_KEYS,
    INDIVIDUAL_LAYER_ENABLED_KEY,
    METRICS_SCHEMA,
    RAW_DIALOG_SCHEMA,
    EvaluationContaminationError,
    RawTrainingRelation,
    assert_no_metrics_leak,
    assert_no_sentinel_leak,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Iterator, Mapping

RAW_DIALOG_TABLE: str = "dialog"
"""Table name inside :data:`RAW_DIALOG_SCHEMA` (qualified
``raw_dialog.dialog``).

Kept as a public constant so :func:`bootstrap_schema` and the contract
test agree on the same physical name.
"""

# ---------------------------------------------------------------------------
# Bootstrap DDL — column set locked in lockstep with the contract.
# ---------------------------------------------------------------------------

_RAW_DIALOG_DDL_COLUMNS: tuple[tuple[str, str], ...] = (
    ("id", "TEXT"),
    ("run_id", "TEXT"),
    ("dialog_id", "TEXT"),
    ("tick", "INTEGER"),
    ("turn_index", "INTEGER"),
    ("speaker_agent_id", "TEXT"),
    ("speaker_persona_id", "TEXT"),
    ("addressee_agent_id", "TEXT"),
    ("addressee_persona_id", "TEXT"),
    ("utterance", "TEXT"),
    ("mode", "TEXT"),
    ("zone", "TEXT"),
    ("reasoning", "TEXT"),
    ("epoch_phase", "TEXT"),
    # B-1 (m9-individual-layer-schema-add, Codex HIGH-1): NOT NULL +
    # DEFAULT FALSE keeps the column bivalent and lets existing INSERTs
    # that omit the new column still succeed with explicit false.
    ("individual_layer_enabled", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("created_at", "TIMESTAMP"),
)

_BOOTSTRAP_COLUMN_NAMES: frozenset[str] = frozenset(
    name for name, _ in _RAW_DIALOG_DDL_COLUMNS
)
if _BOOTSTRAP_COLUMN_NAMES != ALLOWED_RAW_DIALOG_KEYS:
    # Fail-fast at import: divergence here would silently widen the
    # contract, which is the exact failure mode the four-layer defence
    # is meant to prevent.
    raise EvaluationContaminationError(
        "bootstrap DDL column set"
        f" {sorted(_BOOTSTRAP_COLUMN_NAMES)} diverges from"
        f" ALLOWED_RAW_DIALOG_KEYS {sorted(ALLOWED_RAW_DIALOG_KEYS)}"
        " — update both in lockstep",
    )

_METRIC_TIERS: tuple[str, ...] = ("tier_a", "tier_b", "tier_c")

_METRIC_TIER_COLUMNS: str = (
    '"run_id" TEXT,'
    ' "persona_id" TEXT,'
    ' "turn_idx" INTEGER,'
    ' "metric_name" TEXT,'
    ' "metric_value" DOUBLE,'
    ' "notes" TEXT'
)
"""Generic per-metric row shape used by all three tiers at P0c.

Tier A is per-turn, Tier B is per-100-turn aggregate, Tier C is judge
score; later phases may introduce tier-specific columns. The current
shape is intentionally narrow so the contract surface stays tight.
"""


def _inspect_raw_dialog_columns(
    conn: duckdb.DuckDBPyConnection,
) -> list[str]:
    """Return ordered column names of ``raw_dialog.dialog``.

    Module-level helper used by both :class:`_DuckDBRawTrainingRelation`
    construction and :func:`export_raw_only_snapshot`. Raises
    :class:`EvaluationContaminationError` if the table is missing.
    """
    rows = conn.execute(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_schema = ? AND table_name = ?"
        " ORDER BY ordinal_position",
        (RAW_DIALOG_SCHEMA, RAW_DIALOG_TABLE),
    ).fetchall()
    if not rows:
        raise EvaluationContaminationError(
            f"{RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE} not found in DuckDB"
            f" file; cannot construct training view (was the schema"
            f" bootstrapped? — see bootstrap_schema)",
        )
    return [str(row[0]) for row in rows]


class _DuckDBRawTrainingRelation:
    """Concrete :class:`RawTrainingRelation` backed by a read-only DuckDB connection.

    Designed as a **constrained facade**:

    * The connection is held privately; no public attribute exposes it.
    * Only a fixed SELECT against ``raw_dialog.dialog`` is ever issued.
    * Column projection is the **intersection** of the physical columns
      with :data:`ALLOWED_RAW_DIALOG_KEYS`; any column outside the
      allow-list is dropped before the row reaches the caller, and a
      mismatch between the physical schema and the allow-list raises
      :class:`EvaluationContaminationError` at construction.
    """

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn
        physical_columns = _inspect_raw_dialog_columns(conn)
        outside_allowlist = [
            col for col in physical_columns if col not in ALLOWED_RAW_DIALOG_KEYS
        ]
        if outside_allowlist:
            raise EvaluationContaminationError(
                f"raw_dialog.{RAW_DIALOG_TABLE} contains column(s)"
                f" {sorted(outside_allowlist)!r} that are not on the"
                f" raw_dialog allow-list"
                f" ({sorted(ALLOWED_RAW_DIALOG_KEYS)})",
            )
        self._columns: tuple[str, ...] = tuple(physical_columns)
        # Belt-and-braces: confirm we never aliased the metrics schema in.
        if any(col.startswith(f"{METRICS_SCHEMA}.") for col in self._columns):
            raise EvaluationContaminationError(
                f"raw_dialog projection includes a {METRICS_SCHEMA}-qualified"
                f" column: {self._columns!r}",
            )

        # Aggregate row-level contamination check (Codex HIGH-2 / DB11 /
        # B-1): ``connect_training_view()`` is the loader boundary
        # contracted by blockers.md §B-1, so we raise *before* any caller
        # can reach ``iter_rows`` past a row that carries
        # ``epoch_phase=evaluation`` or a truthy / NULL
        # ``individual_layer_enabled``. SQL aggregate is used (not a
        # ``WHERE`` filter) to avoid silently diluting the
        # ``min_examples`` count check downstream in
        # ``assert_phase_beta_ready``. The aggregate is skipped when
        # either column is absent (legacy / pre-B-1 schemas) — those
        # cases are still picked up by ``assert_phase_beta_ready``
        # itself, so backwards compatibility at the loader is
        # preserved.
        column_set = frozenset(self._columns)
        if "epoch_phase" in column_set and INDIVIDUAL_LAYER_ENABLED_KEY in column_set:
            agg_row = self._conn.execute(
                "SELECT"  # noqa: S608  # all interpolations are module-private constants
                " COALESCE(SUM(CASE WHEN LOWER(epoch_phase) = 'evaluation'"
                " THEN 1 ELSE 0 END), 0),"
                f" COALESCE(SUM(CASE WHEN {INDIVIDUAL_LAYER_ENABLED_KEY}"
                f" IS NOT FALSE THEN 1 ELSE 0 END), 0)"
                f" FROM {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}",
            ).fetchone()
            eval_count = int(agg_row[0]) if agg_row else 0
            ind_count = int(agg_row[1]) if agg_row else 0
            if eval_count > 0:
                raise EvaluationContaminationError(
                    f"raw_dialog.{RAW_DIALOG_TABLE}: {eval_count} row(s)"
                    f" carry epoch_phase~='evaluation' (case-insensitive)"
                    f" at construction time — rejecting at the loader"
                    f" boundary (Codex HIGH-2 / DB11 / B-1)",
                )
            if ind_count > 0:
                raise EvaluationContaminationError(
                    f"raw_dialog.{RAW_DIALOG_TABLE}: {ind_count} row(s)"
                    f" carry truthy or NULL {INDIVIDUAL_LAYER_ENABLED_KEY}"
                    f" at construction time — rejecting at the loader"
                    f" boundary (Codex HIGH-2 / DB11 / B-1)",
                )

    # ------------------------------------------------------------------
    # Protocol surface
    # ------------------------------------------------------------------

    @property
    def schema_name(self) -> str:
        return RAW_DIALOG_SCHEMA

    @property
    def columns(self) -> tuple[str, ...]:
        return self._columns

    def row_count(self) -> int:
        result = self._conn.execute(
            f"SELECT COUNT(*) FROM {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}",  # noqa: S608  # constants are module-private literals, no user input
        ).fetchone()
        if result is None:
            return 0
        return int(result[0])

    def iter_rows(self) -> Iterator[Mapping[str, object]]:
        # Quote each column with DuckDB identifier rules so any future
        # column added to the allow-list cannot collide with reserved
        # keywords (``order``, ``mode``, ``zone`` are all candidates).
        projection = ", ".join(f'"{col}"' for col in self._columns)
        sql = f"SELECT {projection} FROM {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}"  # noqa: S608  # projection comes from validated allow-list, identifiers are module constants
        cursor = self._conn.execute(sql)
        rows = cursor.fetchall()
        for row in rows:
            row_dict: dict[str, object] = dict(zip(self._columns, row, strict=True))
            assert_no_metrics_leak(row_dict.keys(), context="iter_rows")
            assert_no_sentinel_leak(row_dict.values(), context="iter_rows")
            yield row_dict

    def close(self) -> None:
        """Release the underlying DuckDB connection. Idempotent."""
        with contextlib.suppress(duckdb.Error):
            self._conn.close()


def connect_training_view(db_path: str | Path) -> RawTrainingRelation:
    """Open *db_path* read-only and return a constrained training-egress view.

    This is the **only** training-loader entry point in the codebase.
    Any caller that bypasses it (raw ``duckdb.connect``, direct
    ``read_parquet`` against the metrics schema, etc.) violates the
    contract — the static grep gate in CI catches the obvious shapes,
    while the sentinel test catches the dynamic ones.
    """
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        return _DuckDBRawTrainingRelation(conn)
    except Exception:
        conn.close()
        raise


# ---------------------------------------------------------------------------
# P0c — schema bootstrap
# ---------------------------------------------------------------------------


def bootstrap_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Create ``raw_dialog.dialog`` and ``metrics.tier_{a,b,c}`` idempotently.

    *con* must be a writable connection (``read_only=False``); a
    read-only handle will surface DuckDB's own error. The DDL is
    ``CREATE … IF NOT EXISTS`` everywhere, so this is safe to call
    repeatedly on existing files (e.g. orchestration glue that doesn't
    track whether it already ran).

    The ``raw_dialog.dialog`` column set is identical to
    :data:`ALLOWED_RAW_DIALOG_KEYS`; the module-load-time check above
    refuses to import the module if the two ever drift.
    """
    raw_dialog_cols = ", ".join(
        f'"{name}" {ddl_type}' for name, ddl_type in _RAW_DIALOG_DDL_COLUMNS
    )

    con.execute(f"CREATE SCHEMA IF NOT EXISTS {RAW_DIALOG_SCHEMA}")
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {METRICS_SCHEMA}")

    con.execute(
        f"CREATE TABLE IF NOT EXISTS"
        f" {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}"
        f" ({raw_dialog_cols})",
    )

    for tier in _METRIC_TIERS:
        con.execute(
            f"CREATE TABLE IF NOT EXISTS"
            f" {METRICS_SCHEMA}.{tier}"
            f" ({_METRIC_TIER_COLUMNS})",
        )


# ---------------------------------------------------------------------------
# P0c — analysis view (Mac-side full read, NOT a training egress)
# ---------------------------------------------------------------------------


class AnalysisView:
    """Read-only handle that spans both ``raw_dialog`` and ``metrics``.

    Intended for Mac-side analytics, dashboards, and notebooks — i.e.
    any context where reading metric scores **is** the point. The
    training-egress contract therefore deliberately does NOT apply
    here: callers can run arbitrary SELECTs against either schema.

    What protects the boundary: the CI grep gate confines metric
    schema references to this module, so :func:`connect_analysis_view`
    is the sole sanctioned multi-schema reader. Any new training-side
    code path that imports this class would be surfaced by code review
    + the sentinel CI test (which scans documented training-egress
    modules — see ``.github/workflows/ci.yml`` ``eval-egress-grep-gate``
    job).
    """

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def execute(
        self,
        sql: str,
        params: tuple[object, ...] | None = None,
    ) -> list[tuple[object, ...]]:
        """Run *sql* against the read-only connection and fetch all rows."""
        cursor = (
            self._conn.execute(sql)
            if params is None
            else self._conn.execute(sql, params)
        )
        return list(cursor.fetchall())

    def close(self) -> None:
        """Release the underlying DuckDB connection. Idempotent."""
        with contextlib.suppress(duckdb.Error):
            self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def connect_analysis_view(db_path: str | Path) -> AnalysisView:
    """Open *db_path* read-only for full multi-schema analysis access.

    The ME-2 protocol mandates that only G-GEAR writes the file, while
    Mac consumes the post-CHECKPOINT snapshot read-only — this entry is
    the Mac-side enforcement of that role.
    """
    conn = duckdb.connect(str(db_path), read_only=True)
    return AnalysisView(conn)


# ---------------------------------------------------------------------------
# P4a — Tier B retrieval (M9-eval ME-15)
# ---------------------------------------------------------------------------

TIER_B_METRIC_SCHEMA_VERSION: str = "tier-b-v1"
"""Schema version embedded in Tier B sidecar ``notes`` JSON (ME-15).

Bumped when the notes JSON shape changes; consumers compare exact strings.
"""


@dataclass(frozen=True, slots=True)
class TierBMetricRow:
    """One row of ``metrics.tier_b`` decoded for analysis-side consumers.

    The physical column ``turn_idx`` is reused to carry the per-100-turn
    ``window_index`` (M9-eval ME-15 / Codex P4a MEDIUM-2). Helpers expose
    the field by its semantic name and parse the sidecar ``notes`` JSON so
    downstream code does not accidentally join a window aggregate to a raw
    turn.
    """

    window_index: int
    metric_value: float
    window_start_turn: int
    window_end_turn: int
    window_size: int
    metric_schema_version: str
    notes_raw: str | None  # untouched JSON for forward-compat fields


def _parse_tier_b_notes(notes: str | None) -> dict[str, object]:
    """Parse the Tier B sidecar JSON; missing fields default to zero / None.

    Tier B uses a fixed schema (ME-15) rather than free-form JSON to keep
    consumer code simple. The schema is small enough that an unconditional
    ``json.loads`` call is cheap; we still tolerate ``None`` / empty input
    for rows written before the schema was finalised.
    """
    if not notes:
        return {}
    try:
        parsed = json.loads(notes)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


def fetch_tier_b_metric(
    view: AnalysisView,
    *,
    run_id: str,
    persona_id: str,
    metric_name: str,
) -> list[TierBMetricRow]:
    """Return Tier B rows for ``(run_id, persona_id, metric_name)``.

    Helper that centralises the ``turn_idx → window_index`` rename and the
    sidecar JSON parsing so downstream code (notebooks, dashboards, the
    eventual M9-C-adopt quorum logic) sees stable field names. ME-14
    requires the DB9 quorum code to read the *primary* CI only; this helper
    is the retrieval half — the per-window values feed into the cluster-only
    bootstrap before the quorum decision is made.

    Args:
        view: Read-only :class:`AnalysisView` (Mac-side, ME-2 protocol).
        run_id: Capture run identifier matching ``raw_dialog.run_id``.
        persona_id: Persona under evaluation.
        metric_name: One of the Tier B identifiers — e.g.
            ``"tier_b.vendi_score"`` / ``"tier_b.big5_stability_icc"``.

    Returns:
        List of :class:`TierBMetricRow`, ordered by ``window_index`` ascending.
    """
    select_sql = (
        f"SELECT turn_idx, metric_value, notes FROM {METRICS_SCHEMA}.tier_b"  # noqa: S608  # identifier is module-private constant
        " WHERE run_id = ? AND persona_id = ? AND metric_name = ?"
        " ORDER BY turn_idx"
    )
    rows = view.execute(select_sql, (run_id, persona_id, metric_name))
    decoded: list[TierBMetricRow] = []
    for row in rows:
        window_index_raw, metric_value_raw, notes_raw = row
        notes_str = notes_raw if isinstance(notes_raw, str) else None
        notes = _parse_tier_b_notes(notes_str)
        decoded.append(
            TierBMetricRow(
                window_index=_coerce_int(window_index_raw),
                metric_value=_coerce_float(metric_value_raw),
                window_start_turn=_coerce_int(notes.get("window_start_turn", 0)),
                window_end_turn=_coerce_int(notes.get("window_end_turn", 0)),
                window_size=_coerce_int(notes.get("window_size", 0)),
                metric_schema_version=_coerce_str(
                    notes.get("metric_schema_version", ""),
                ),
                notes_raw=notes_str,
            ),
        )
    return decoded


def _coerce_int(value: object) -> int:
    """Best-effort int coercion for DuckDB ``object`` row values."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, (str, float)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    return 0


def _coerce_float(value: object) -> float:
    """Best-effort float coercion for DuckDB ``object`` row values."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _coerce_str(value: object) -> str:
    """Best-effort str coercion for notes JSON values."""
    if isinstance(value, str):
        return value
    return ""


def make_tier_b_notes(
    *,
    window_start_turn: int,
    window_end_turn: int,
    window_size: int,
    kernel_name: str | None = None,
    ipip_version: str | None = None,
    icc_formula: str | None = None,
) -> str:
    """Build the Tier B ``notes`` JSON with the fixed ME-15 schema.

    The same writer is used by Vendi, IPIP-NEO and Big5 ICC persisters so
    the JSON shape stays uniform across sub-metrics. Optional fields are
    included only when set; consumers tolerate their absence.
    """
    payload: dict[str, object] = {
        "window_start_turn": int(window_start_turn),
        "window_end_turn": int(window_end_turn),
        "window_size": int(window_size),
        "metric_schema_version": TIER_B_METRIC_SCHEMA_VERSION,
    }
    if kernel_name is not None:
        payload["kernel_name"] = kernel_name
    if ipip_version is not None:
        payload["ipip_version"] = ipip_version
    if icc_formula is not None:
        payload["icc_formula"] = icc_formula
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# P0c — Parquet snapshot (raw rows only)
# ---------------------------------------------------------------------------


def export_raw_only_snapshot(
    src_path: str | Path,
    out_path: str | Path,
) -> None:
    """Copy ``raw_dialog.dialog`` from *src_path* to a Parquet *out_path*.

    The metrics schema is never touched. Callers that need ad-hoc SQL
    over raw rows should run that SQL against the snapshot — keeping a
    single auditable egress route is one of the HIGH-1 fixes from the
    Codex review (see ``.steering/20260430-m9-eval-system/codex-review.md``).
    """
    src = str(src_path)
    out = str(out_path)
    if "'" in out:
        # The COPY statement embeds *out* as a quoted string literal;
        # an internal single quote would break the boundary. Reject
        # rather than try to escape (the project never produces such
        # paths in practice).
        raise ValueError(
            f"export_raw_only_snapshot: out_path must not contain a"
            f" single quote (got {out!r})",
        )
    conn = duckdb.connect(src, read_only=True)
    try:
        physical = _inspect_raw_dialog_columns(conn)
        outside = [c for c in physical if c not in ALLOWED_RAW_DIALOG_KEYS]
        if outside:
            raise EvaluationContaminationError(
                f"raw_dialog.{RAW_DIALOG_TABLE} contains column(s)"
                f" {sorted(outside)!r} outside the allow-list; refusing"
                f" to snapshot",
            )
        # Defence-in-depth: re-run the metric-prefix check on the
        # projection that will land in the Parquet file.
        assert_no_metrics_leak(physical, context="export_raw_only_snapshot")
        projection = ", ".join(f'"{col}"' for col in physical)
        copy_sql = (
            f"COPY (SELECT {projection} FROM {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE})"  # noqa: S608  # identifiers are module constants, path validated above
            f" TO '{out}' (FORMAT PARQUET)"
        )
        conn.execute(copy_sql)
    finally:
        with contextlib.suppress(duckdb.Error):
            conn.close()


# ---------------------------------------------------------------------------
# P0c — ME-2 helpers (CHECKPOINT + atomic same-fs rename)
# ---------------------------------------------------------------------------


def write_with_checkpoint(con: duckdb.DuckDBPyConnection) -> None:
    """Flush the WAL via ``CHECKPOINT`` and close *con* (ME-2 step 1).

    G-GEAR-side helper invoked at the end of each capture session: it
    guarantees the on-disk file is consistent before the snapshot copy
    + rsync to Mac. Decision is logged in
    ``.steering/20260430-m9-eval-system/decisions.md`` §ME-2.
    """
    con.execute("CHECKPOINT")
    with contextlib.suppress(duckdb.Error):
        con.close()


def atomic_temp_rename(
    temp_path: Path | str,
    final_path: Path | str,
) -> None:
    """POSIX same-filesystem atomic rename (ME-2 step 4).

    Verifies that *temp_path* and *final_path* live on the same
    filesystem device; ``Path.replace`` otherwise falls back to copy +
    remove on Linux, which loses atomicity and would let the analysis
    view momentarily observe a torn file. NFS / SMB / iCloud-shared
    paths are explicitly out of scope (see ME-2).
    """
    temp_path = Path(temp_path)
    final_path = Path(final_path)
    temp_dev = temp_path.parent.stat().st_dev
    final_dev = final_path.parent.stat().st_dev
    if temp_dev != final_dev:
        raise OSError(
            f"atomic_temp_rename requires same filesystem;"
            f" temp_path on st_dev={temp_dev},"
            f" final_path on st_dev={final_dev}",
        )
    temp_path.replace(final_path)


__all__ = [
    "RAW_DIALOG_TABLE",
    "TIER_B_METRIC_SCHEMA_VERSION",
    "AnalysisView",
    "TierBMetricRow",
    "atomic_temp_rename",
    "bootstrap_schema",
    "connect_analysis_view",
    "connect_training_view",
    "export_raw_only_snapshot",
    "fetch_tier_b_metric",
    "make_tier_b_notes",
    "write_with_checkpoint",
]
