"""WP-report: the ``*.individuation.json`` sidecar model + atomic writer.

The sidecar is the **only** individuation output of a live capture run (the
``metrics.individuation`` DuckDB table is written by a separate analysis-side
ingestion path). It keeps provenance **nested** via
:meth:`~.models.MetricResult.to_sidecar_dict`.

An *error* sidecar (:func:`write_individuation_error_sidecar`) is written when
``--compute-individuation`` was requested but the pass raised: the published
capture keeps its return code, but the failure is made observable rather than
silently swallowed.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime  # noqa: TC003  # runtime use in pydantic field
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

# MetricResult must be importable at runtime: it is a pydantic field annotation
# on IndividuationReport, so a TYPE_CHECKING-only import leaves the model
# "not fully defined". models.py imports only ddl/policy (no eval_store), so
# this does not reintroduce the import cycle handled in _write_json_atomic.
from erre_sandbox.evidence.individuation.models import (
    MetricResult,  # noqa: TC001  # pydantic field needs runtime resolution
)
from erre_sandbox.evidence.individuation.policy import INDIVIDUATION_SCHEMA_VERSION

if TYPE_CHECKING:
    from collections.abc import Sequence

INDIVIDUATION_SIDECAR_SUFFIX: str = ".individuation.json"
"""Sidecar suffix appended to the published ``.duckdb`` filename."""


class IndividuationReport(BaseModel):
    """Per-run individuation summary serialised to the JSON sidecar."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    run_id: str
    computed_at: datetime
    counts_by_status: dict[str, int]
    counts_by_metric: dict[str, int]
    results: tuple[MetricResult, ...]

    def to_sidecar_dict(self) -> dict[str, object]:
        """JSON-serialisable dict (provenance kept nested per result)."""
        return self.model_dump(mode="json")


def build_report(
    run_id: str,
    results: Sequence[MetricResult],
    *,
    computed_at: datetime,
) -> IndividuationReport:
    """Tally statuses / metric counts and wrap the results into a report."""
    counts_by_status = Counter(r.status.value for r in results)
    counts_by_metric = Counter(r.metric_name for r in results)
    return IndividuationReport(
        schema_version=INDIVIDUATION_SCHEMA_VERSION,
        run_id=run_id,
        computed_at=computed_at,
        counts_by_status=dict(counts_by_status),
        counts_by_metric=dict(counts_by_metric),
        results=tuple(results),
    )


def individuation_sidecar_path_for(duckdb_path: Path | str) -> Path:
    """Return the ``<duckdb>.individuation.json`` sibling path."""
    p = Path(duckdb_path)
    return p.with_name(p.name + INDIVIDUATION_SIDECAR_SUFFIX)


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    # Lazy import avoids a package import cycle: eval_store imports
    # individuation.ddl (which triggers this package's __init__), so this
    # module must not import eval_store at module load (DA-M10I-10 boundary).
    from erre_sandbox.evidence.eval_store import atomic_temp_rename  # noqa: PLC0415

    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    atomic_temp_rename(tmp, path)


def write_individuation_sidecar_atomic(
    path: Path | str, report: IndividuationReport
) -> None:
    """Atomically write the success sidecar JSON."""
    _write_json_atomic(Path(path), report.to_sidecar_dict())


def read_individuation_sidecar(path: Path | str) -> IndividuationReport:
    """Read + validate a success ``*.individuation.json`` sidecar.

    The C3b verdict pipeline (DA-M11C3b-exec-3) reads Burrows rows from this
    sidecar rather than re-running ``compute_individuation``, so the individuation
    sidecar is the single source of the Burrows axis. Raises
    :class:`pydantic.ValidationError` for an *error* sidecar or a schema
    violation (an error sidecar lacks ``results`` / ``counts_by_status``), which
    the caller surfaces as a missing-evidence preflight failure.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return IndividuationReport.model_validate(raw)


def write_individuation_error_sidecar(
    path: Path | str,
    *,
    run_id: str,
    error_type: str,
    error_summary: str,
    computed_at: datetime,
) -> None:
    """Atomically write an *error* sidecar (capture rc preserved, failure visible)."""
    payload: dict[str, object] = {
        "schema_version": INDIVIDUATION_SCHEMA_VERSION,
        "run_id": run_id,
        "status": "error",
        "error_type": error_type,
        "error_summary": error_summary,
        "computed_at": computed_at.isoformat(),
    }
    _write_json_atomic(Path(path), payload)


__all__ = [
    "INDIVIDUATION_SIDECAR_SUFFIX",
    "IndividuationReport",
    "build_report",
    "individuation_sidecar_path_for",
    "read_individuation_sidecar",
    "write_individuation_error_sidecar",
    "write_individuation_sidecar_atomic",
]
