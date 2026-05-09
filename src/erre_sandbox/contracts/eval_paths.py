"""Evaluation data-path contract.

The executable boundary between ``raw_dialog`` (training-eligible) and
``metrics`` (evaluation-only).

This module is the **API contract** layer of the 4-layer defence specified
in ``.steering/20260430-m9-eval-system/design-final.md``
§"DuckDB 単 file + named schema + 4 層 contract":

1. **API contract** (this module): schema-name constants, an explicit
   allow-list of ``raw_dialog`` columns, a constrained relation
   :class:`RawTrainingRelation` Protocol that exposes **only** raw rows
   (no DuckDB connection, no arbitrary SQL), and the
   :class:`EvaluationContaminationError` that every egress path must raise
   when a metric-shaped key surfaces.
2. **Behavioural CI test** (``tests/test_evidence/test_eval_paths_contract.py``):
   sentinel-row fixtures (``M9_EVAL_SENTINEL_LEAK_*``) that verify no
   training-egress route surfaces metric data.
3. **Static CI grep gate** (``.github/workflows/ci.yml``): fails the build
   if any module under the training-egress allowlist textually mentions
   ``metrics.``.
4. **Existing-egress audit** (``cli/export_log.py``): is included in the
   sentinel test scope because the M9 LoRA training pipeline reads
   ``dialog_turns`` through it.

Codex ``gpt-5.5 xhigh`` review (HIGH-1) elevated this contract from a
path-only convention to a behavioural one — grep alone cannot catch
dynamic SQL or quoted ``read_parquet`` calls, so the constrained
relation + sentinel test are the **primary** boundary, with grep as a
back-stop.

Layer rule (``contracts`` package): stdlib + pydantic only — no
``duckdb``, ``numpy``, or other heavy imports here. The DuckDB-backed
implementation lives in :mod:`erre_sandbox.evidence.eval_store`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Iterable, Iterator, Mapping

# ---------------------------------------------------------------------------
# Schema names
# ---------------------------------------------------------------------------

RAW_DIALOG_SCHEMA: Final[str] = "raw_dialog"
"""Name of the DuckDB schema that holds training-eligible dialog turns.

This is the **only** schema the LoRA training pipeline is allowed to read
through :func:`erre_sandbox.evidence.eval_store.connect_training_view`.
Tier 0 contract (DB5): every column here must be metric-free — turn id,
agent / persona / mode / zone, utterance, timestamp, reasoning trace.
"""

METRICS_SCHEMA: Final[str] = "metrics"
"""Name of the DuckDB schema that holds Tier A/B/C scores keyed by
``(run_id, persona_id, turn_idx)``.

Reading this schema from a training-loader code path is a contract
violation that must surface as :class:`EvaluationContaminationError`.
"""


# ---------------------------------------------------------------------------
# Column allow-list / forbidden patterns
# ---------------------------------------------------------------------------

INDIVIDUAL_LAYER_ENABLED_KEY: Final[str] = "individual_layer_enabled"
"""Single source of truth for the DB11 / M10-A individual-layer flag column name.

Exported so the training gate
(:func:`erre_sandbox.training.train_kant_lora.assert_phase_beta_ready`)
imports the same string the allow-list and the DDL lockstep check use,
keeping the m9-individual-layer-schema-add (B-1) contract on a single
canonical key. Changing the physical column name therefore requires
updating exactly one literal here.
"""

ALLOWED_RAW_DIALOG_KEYS: Final[frozenset[str]] = frozenset(
    {
        "id",
        "run_id",
        "dialog_id",
        "tick",
        "turn_index",
        "speaker_agent_id",
        "speaker_persona_id",
        "addressee_agent_id",
        "addressee_persona_id",
        "utterance",
        "mode",
        "zone",
        "reasoning",
        "epoch_phase",
        INDIVIDUAL_LAYER_ENABLED_KEY,
        "created_at",
    },
)
"""Closed allow-list of column names permitted on a ``raw_dialog`` row.

Any key emitted by a training-egress path MUST be a member of this set.
``mode`` / ``zone`` / ``reasoning`` are reserved for the M9 ingest CLI
that copies sqlite ``dialog_turns`` into DuckDB ``raw_dialog``; the
existing M8 sink only populates a subset of these (see
``cli/export_log.py``), which is a strict subset and therefore safe.

:data:`INDIVIDUAL_LAYER_ENABLED_KEY` is the DB11 / M10-A individual-layer
activation flag; training-egress paths require it to be ``FALSE`` for
every row, enforced at three layers: (1) the DDL ``BOOLEAN NOT NULL
DEFAULT FALSE`` constraint in
:data:`erre_sandbox.evidence.eval_store._RAW_DIALOG_DDL_COLUMNS`,
(2) the construction-time aggregate assert inside
``_DuckDBRawTrainingRelation.__init__``, and (3) the row-level scan
inside :func:`erre_sandbox.training.train_kant_lora.assert_phase_beta_ready`.
"""

FORBIDDEN_METRIC_KEY_PATTERNS: Final[tuple[str, ...]] = (
    "metric_",
    "score_",
    "vendi_",
    "burrows_",
    "icc_",
    "embedding_",
    "novelty_",
    "logit_",
    "judge_",
    "geval_",
    "prometheus_",
    "nli_",
    "mattr_",
    "empath_",
)
"""Substring prefixes that signal a metric-shaped key has leaked into a
training-egress payload.

These prefixes are used by :func:`assert_no_metrics_leak` as a
**defence-in-depth** check on top of the closed allow-list — a key like
``"empath_anger"`` would be rejected even if a future commit accidentally
added it to :data:`ALLOWED_RAW_DIALOG_KEYS`. Patterns are checked with
``str.startswith`` (case-sensitive) since column names are
canonicalised lower_snake_case throughout the codebase.
"""

SENTINEL_LEAK_PREFIX: Final[str] = "M9_EVAL_SENTINEL_LEAK_"
"""String prefix used by the contamination CI fixture.

If a value starting with this prefix appears in a training-egress payload
the boundary has been breached. Tests should plant sentinel values in the
``metrics`` schema and assert they never reach ``connect_training_view``
output — see :class:`EvaluationContaminationError` and
``tests/test_evidence/test_eval_paths_contract.py``.
"""


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class EvaluationContaminationError(RuntimeError):
    """Raised when a training-egress path attempts to expose metric data.

    Examples that MUST raise:

    * Calling a method on :class:`RawTrainingRelation` that would route
      to the ``metrics`` schema.
    * Building a row dict whose keys include any
      :data:`FORBIDDEN_METRIC_KEY_PATTERNS` prefix.
    * Surfacing a value with the :data:`SENTINEL_LEAK_PREFIX`.

    Catching this exception silently is a **contract bug**; tests assert
    the error type, not just any exception subclass.
    """


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


def assert_no_metrics_leak(keys: Iterable[str], *, context: str) -> None:
    """Raise :class:`EvaluationContaminationError` if any *keys* look metric-shaped.

    The check is layered: keys must (a) belong to the
    :data:`ALLOWED_RAW_DIALOG_KEYS` allow-list **and** (b) not start with
    any :data:`FORBIDDEN_METRIC_KEY_PATTERNS` prefix. *context* is woven
    into the error message so failures at sentinel fixtures point at the
    egress path that leaked.
    """
    keys_seen: list[str] = list(keys)
    forbidden: list[str] = []
    for key in keys_seen:
        for pattern in FORBIDDEN_METRIC_KEY_PATTERNS:
            if key.startswith(pattern):
                forbidden.append(key)
                break
    if forbidden:
        raise EvaluationContaminationError(
            f"{context}: forbidden metric-shaped key(s) {sorted(set(forbidden))!r}"
            f" leaked into training egress",
        )
    out_of_allowlist = [k for k in keys_seen if k not in ALLOWED_RAW_DIALOG_KEYS]
    if out_of_allowlist:
        raise EvaluationContaminationError(
            f"{context}: key(s) {sorted(set(out_of_allowlist))!r} are not on the"
            f" raw_dialog allow-list (expected subset of"
            f" {sorted(ALLOWED_RAW_DIALOG_KEYS)})",
        )


def assert_no_sentinel_leak(
    values: Iterable[object],
    *,
    context: str,
) -> None:
    """Raise :class:`EvaluationContaminationError` if any value is a leak sentinel.

    Used by the red-team contamination fixture: planting
    :data:`SENTINEL_LEAK_PREFIX` values in the ``metrics`` schema and
    checking that no such value ever surfaces through a training-egress
    route. Pure-string check; non-string values pass.
    """
    leaked: list[str] = [
        value
        for value in values
        if isinstance(value, str) and value.startswith(SENTINEL_LEAK_PREFIX)
    ]
    if leaked:
        raise EvaluationContaminationError(
            f"{context}: sentinel leak value(s) {leaked!r} surfaced through"
            f" a training-egress path",
        )


# ---------------------------------------------------------------------------
# Constrained relation Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class RawTrainingRelation(Protocol):
    """Read-only view onto ``raw_dialog`` rows for training pipelines.

    Implementations MUST NOT expose:

    * the underlying DuckDB ``Connection`` or ``DuckDBPyRelation``,
    * an arbitrary SQL execution method,
    * any column outside :data:`ALLOWED_RAW_DIALOG_KEYS`,
    * any join or subquery against :data:`METRICS_SCHEMA`.

    Callers that genuinely need ad-hoc SQL must use
    ``eval_store.export_raw_only_snapshot(out_path)`` (added in P0c) and
    run their query against the *snapshot* — that route is auditable in
    a single place.
    """

    @property
    def schema_name(self) -> str:
        """Always equal to :data:`RAW_DIALOG_SCHEMA`.

        Used by tests to verify the relation cannot be re-pointed at the
        ``metrics`` schema after construction.
        """

    @property
    def columns(self) -> tuple[str, ...]:
        """Tuple of column names exposed on each row.

        Must satisfy ``set(columns) <= ALLOWED_RAW_DIALOG_KEYS``; the
        sentinel test asserts this on every implementation.
        """

    def row_count(self) -> int:
        """Return the number of ``raw_dialog`` rows visible through the view."""

    def iter_rows(self) -> Iterator[Mapping[str, object]]:
        """Iterate over rows as plain dicts.

        Implementations should validate emitted keys via
        :func:`assert_no_metrics_leak` before yielding so a bug in the
        underlying SELECT cannot silently leak a forbidden column.
        """


__all__ = [
    "ALLOWED_RAW_DIALOG_KEYS",
    "FORBIDDEN_METRIC_KEY_PATTERNS",
    "INDIVIDUAL_LAYER_ENABLED_KEY",
    "METRICS_SCHEMA",
    "RAW_DIALOG_SCHEMA",
    "SENTINEL_LEAK_PREFIX",
    "EvaluationContaminationError",
    "RawTrainingRelation",
    "assert_no_metrics_leak",
    "assert_no_sentinel_leak",
]
