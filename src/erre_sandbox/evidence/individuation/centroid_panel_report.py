"""M11-C3b centroid-panel sidecar (``*.centroid_panel.json``) model + IO.

The C3b verdict reads its centroid + within-floor evidence from this sidecar and
**only** this sidecar (DA-M11C3b-P1-2: the panel is the sole centroid source).
The panel is never written into the ``metrics.individuation`` DuckDB table — that
keeps the M10-0 ``write_individuation_rows`` contract (full-run replace,
embedding-keyed dedup) untouched and dissolves both C3b write caveats by
construction (DA-M11C3b-exec-1 / blockers.md): there is no second full-run
replace for a run_id and no in-batch dedup over the per-(dyad, encoder) panel
rows (a degenerate dyad's encoder-independent ``embedding_model_id=None`` rows
simply coexist in the JSON list).

Mirrors :mod:`erre_sandbox.evidence.individuation.report` (Pydantic model +
``to_sidecar_dict`` + atomic temp-rename writer + sibling-path helper + reader).
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime  # noqa: TC003  # runtime use in pydantic field
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

# MetricResult is a pydantic field annotation on CentroidPanelReport, so it must
# resolve at runtime (models.py imports only ddl/policy, no eval_store cycle).
from erre_sandbox.evidence.individuation.models import (
    MetricResult,  # noqa: TC001  # pydantic field needs runtime resolution
)
from erre_sandbox.evidence.individuation.policy import INDIVIDUATION_SCHEMA_VERSION

if TYPE_CHECKING:
    from collections.abc import Sequence

CENTROID_PANEL_SIDECAR_SUFFIX: str = ".centroid_panel.json"
"""Sidecar suffix appended to the published ``.duckdb`` filename."""


class CentroidPanelReport(BaseModel):
    """Per-run multi-encoder centroid + within-floor panel, serialised to JSON."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    run_id: str
    computed_at: datetime
    encoder_ids: tuple[str, ...]
    counts_by_status: dict[str, int]
    results: tuple[MetricResult, ...]

    def to_sidecar_dict(self) -> dict[str, object]:
        """JSON-serialisable dict (provenance kept nested per result)."""
        return self.model_dump(mode="json")


def build_centroid_panel_report(
    run_id: str,
    results: Sequence[MetricResult],
    encoder_ids: Sequence[str],
    *,
    computed_at: datetime,
) -> CentroidPanelReport:
    """Tally statuses and wrap panel ``results`` into a report."""
    counts_by_status = Counter(r.status.value for r in results)
    return CentroidPanelReport(
        schema_version=INDIVIDUATION_SCHEMA_VERSION,
        run_id=run_id,
        computed_at=computed_at,
        encoder_ids=tuple(encoder_ids),
        counts_by_status=dict(counts_by_status),
        results=tuple(results),
    )


def centroid_panel_sidecar_path_for(duckdb_path: Path | str) -> Path:
    """Return the ``<duckdb>.centroid_panel.json`` sibling path."""
    p = Path(duckdb_path)
    return p.with_name(p.name + CENTROID_PANEL_SIDECAR_SUFFIX)


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    # Lazy import avoids the eval_store ↔ individuation package import cycle
    # (the same boundary report.py respects).
    from erre_sandbox.evidence.eval_store import atomic_temp_rename  # noqa: PLC0415

    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    atomic_temp_rename(tmp, path)


def write_centroid_panel_sidecar_atomic(
    path: Path | str, report: CentroidPanelReport
) -> None:
    """Atomically write the panel sidecar JSON."""
    _write_json_atomic(Path(path), report.to_sidecar_dict())


def read_centroid_panel_sidecar(path: Path | str) -> CentroidPanelReport:
    """Read + validate a ``*.centroid_panel.json`` sidecar."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return CentroidPanelReport.model_validate(raw)


__all__ = [
    "CENTROID_PANEL_SIDECAR_SUFFIX",
    "CentroidPanelReport",
    "build_centroid_panel_report",
    "centroid_panel_sidecar_path_for",
    "read_centroid_panel_sidecar",
    "write_centroid_panel_sidecar_atomic",
]
