"""Durable sidecar contract for the SWM hint-engagement verdict (instrument ADR §6).

The loader's
:func:`~erre_sandbox.evidence.hint_engagement.loader.score_hint_engagement` is a pure
function over a sequence of
:class:`~erre_sandbox.evidence.hint_engagement.trace_ddl.HintEngagementTraceRow`; this
module is its **durable artifact contract**. A frozen Pydantic model serialises the
routing verdict, the aggregate engagement metrics (emission / adoption / per-gate /
direction), the per-source provenance (path + sha256 + row_count + seeds + run_ids +
max_tick), and the frozen ADR §6 thresholds — the last echoed verbatim from
:mod:`.constants` so the sidecar itself carries the evidence that no threshold was
tuned after the result was seen (forking-paths guard, ADR §8).

No verdict logic lives here: ``score_hint_engagement`` owns the entire decision (global
stability gate, the (a)/(b)/(c) precedence cascade, boundary ties, the provenance-false
short-circuit). This module only converts its dataclass result + the read provenance
into the durable JSON model, mirroring ``evidence.saturation.verdict_report``. It
imports only the loader's result type (for typing) and the constants — never the
cognition layer — so it stays on the ``evidence`` side of the dependency boundary and
pulls in no ML stack.

Unlike the saturation verdict (which binds only for exactly ``N=3`` agreeing seeds), the
engagement instrument **pools** any number of seeds/runs (DA-EII-12): the loader unions
the eligible ticks for the rates and keys adopted-nudge channels by full run identity,
so the verdict CLI hands every capture's rows straight through with no per-seed gating.
The ``run_ids`` per source make that pooling auditable — a reader can confirm which runs
contributed channels without re-opening the DuckDB.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime  # noqa: TC003 — runtime use in a pydantic field
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict

from erre_sandbox.evidence.hint_engagement import constants as _c

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.evidence.hint_engagement.loader import HintEngagementResult
    from erre_sandbox.evidence.hint_engagement.trace_ddl import HintEngagementTraceRow

HINT_ENGAGEMENT_VERDICT_SCHEMA_VERSION: Final[str] = "hint-engagement-verdict-1"
"""Sidecar schema version — bump on any breaking field change."""

HINT_ENGAGEMENT_VERDICT_SIDECAR_SUFFIX: Final[str] = ".hint_engagement_verdict.json"
"""Sidecar suffix appended to the first capture's filename for the default --out."""

_SHA256_CHUNK: Final[int] = 1 << 20
"""1 MiB read chunk for the source-file sha256 (streamed, never slurped whole)."""


class FrozenThresholds(BaseModel):
    """The ADR §6 frozen decision-table values, echoed into the sidecar verbatim.

    Copied from :mod:`.constants` (the single source of truth) so a reader can confirm
    the verdict used the pre-registered thresholds and nothing was tuned after the
    result was seen (forking-paths guard, ADR §8). They are reported, never re-decided.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    warmup_ticks: int
    n_min: int
    channel_floor: int
    theta_e: float
    theta_a: float
    theta_dir: float
    adopted_channel_min: int


class SourceProvenance(BaseModel):
    """One input capture's audit record (path + content hash + read summary).

    ``run_ids`` is included because the engagement scorer keys adopted-nudge channels by
    full run identity (``(run_id, seed, individual_id, axis, key)``), so a verdict
    reader must be able to see which runs contributed channels to the pooled result
    (DA-HEV-4).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    sha256: str
    row_count: int
    seeds: tuple[int, ...]
    run_ids: tuple[str, ...]
    max_tick: int | None


class HintEngagementVerdictReport(BaseModel):
    """The serialised routing verdict + aggregate metrics + provenance + thresholds."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    run_id: str
    computed_at: datetime
    verdict: str
    emission_rate: float | None
    adoption_rate: float | None
    adopted_direction_consistency_rate: float | None
    per_gate_rejection_share: dict[str, float]
    dominant_gate: str | None
    n_eligible_ticks: int
    n_emitted: int
    n_adopted: int
    n_rejected: int
    n_eligible_channels: int
    notes: str
    seeds: tuple[int, ...]
    sources: tuple[SourceProvenance, ...]
    thresholds: FrozenThresholds

    def to_sidecar_dict(self) -> dict[str, object]:
        """JSON-serialisable dict."""
        return self.model_dump(mode="json")


def _frozen_thresholds() -> FrozenThresholds:
    """Snapshot the ADR §6 constants into the sidecar model."""
    return FrozenThresholds(
        warmup_ticks=_c.WARMUP_TICKS,
        n_min=_c.N_MIN,
        channel_floor=_c.CHANNEL_FLOOR,
        theta_e=_c.THETA_E,
        theta_a=_c.THETA_A,
        theta_dir=_c.THETA_DIR,
        adopted_channel_min=_c.ADOPTED_CHANNEL_MIN,
    )


def file_sha256(path: Path | str) -> str:
    """Stream a file's SHA-256 (hex) for source provenance."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(_SHA256_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_source_provenance(
    path: Path | str, rows: Sequence[HintEngagementTraceRow]
) -> SourceProvenance:
    """Build one capture's provenance record from its path + the rows read from it.

    The SHA-256 is of the file bytes (auditable identity); ``row_count`` / ``seeds`` /
    ``run_ids`` / ``max_tick`` summarise what the loader actually read, so a verdict
    reader can cross-check the trace coverage (and which runs/seeds the channels pool
    across) without re-opening the DuckDB.
    """
    seeds = tuple(sorted({r.seed for r in rows}))
    run_ids = tuple(sorted({r.run_id for r in rows}))
    max_tick = max((r.tick for r in rows), default=None)
    return SourceProvenance(
        path=str(path),
        sha256=file_sha256(path),
        row_count=len(rows),
        seeds=seeds,
        run_ids=run_ids,
        max_tick=max_tick,
    )


def build_hint_engagement_verdict_report(
    result: HintEngagementResult,
    *,
    run_id: str,
    computed_at: datetime,
    sources: tuple[SourceProvenance, ...],
) -> HintEngagementVerdictReport:
    """Convert the scorer's dataclass result into the durable sidecar model."""
    return HintEngagementVerdictReport(
        schema_version=HINT_ENGAGEMENT_VERDICT_SCHEMA_VERSION,
        run_id=run_id,
        computed_at=computed_at,
        verdict=result.verdict,
        emission_rate=result.emission_rate,
        adoption_rate=result.adoption_rate,
        adopted_direction_consistency_rate=result.adopted_direction_consistency_rate,
        per_gate_rejection_share=dict(result.per_gate_rejection_share),
        dominant_gate=result.dominant_gate,
        n_eligible_ticks=result.n_eligible_ticks,
        n_emitted=result.n_emitted,
        n_adopted=result.n_adopted,
        n_rejected=result.n_rejected,
        n_eligible_channels=result.n_eligible_channels,
        notes=result.notes,
        seeds=tuple(result.seeds),
        sources=sources,
        thresholds=_frozen_thresholds(),
    )


def hint_engagement_verdict_sidecar_path_for(base_path: Path | str) -> Path:
    """Return the ``<base>.hint_engagement_verdict.json`` sibling path."""
    p = Path(base_path)
    return p.with_name(p.name + HINT_ENGAGEMENT_VERDICT_SIDECAR_SUFFIX)


def write_hint_engagement_verdict_sidecar_atomic(
    path: Path | str, report: HintEngagementVerdictReport
) -> None:
    """Atomically write the verdict sidecar JSON (temp + same-fs rename)."""
    from erre_sandbox.evidence.eval_store import atomic_temp_rename  # noqa: PLC0415

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(
            report.to_sidecar_dict(), ensure_ascii=False, indent=2, sort_keys=True
        ),
        encoding="utf-8",
    )
    atomic_temp_rename(tmp, path)


def read_hint_engagement_verdict_sidecar(
    path: Path | str,
) -> HintEngagementVerdictReport:
    """Read + validate a ``*.hint_engagement_verdict.json`` sidecar."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return HintEngagementVerdictReport.model_validate(raw)


__all__ = [
    "HINT_ENGAGEMENT_VERDICT_SCHEMA_VERSION",
    "HINT_ENGAGEMENT_VERDICT_SIDECAR_SUFFIX",
    "FrozenThresholds",
    "HintEngagementVerdictReport",
    "SourceProvenance",
    "build_hint_engagement_verdict_report",
    "build_source_provenance",
    "file_sha256",
    "hint_engagement_verdict_sidecar_path_for",
    "read_hint_engagement_verdict_sidecar",
    "write_hint_engagement_verdict_sidecar_atomic",
]
