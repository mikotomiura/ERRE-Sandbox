"""Durable sidecar contract for the SWM saturation probe verdict (ADR section 3.4).

The loader's :func:`~erre_sandbox.evidence.saturation.loader.score_saturation` is a
pure function over
:class:`~erre_sandbox.evidence.saturation.loader.SaturationProbeResult` /
:class:`~erre_sandbox.evidence.saturation.loader.SeedScore` dataclasses; this module
is its **durable artifact contract**. A frozen Pydantic model serialises the 3-way
verdict, the per-seed diagnostics, the per-source provenance (path + sha256 +
row_count + seeds + max_tick), and the frozen ADR section 3.0 thresholds — the last
echoed verbatim from :mod:`.constants` so the sidecar itself carries the evidence
that no threshold was tuned after the result was seen (ADR section 7 forking-paths
guard).

No verdict logic lives here: ``score_saturation`` owns the entire decision (per-seed
partition, ``T_run >= 25``, provenance, NaN, gates, exactly ``N=3``, label agreement).
This module only converts its dataclass result + the read provenance into the durable
JSON model, mirroring ``evidence.individuation.c3b_verdict_report``. It imports only
the loader's result dataclasses and the constants — never the cognition layer — so it
stays on the ``evidence`` side of the dependency boundary and pulls in no ML stack.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime  # noqa: TC003 — runtime use in a pydantic field
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict

from erre_sandbox.evidence.saturation import constants as _c

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.evidence.saturation.loader import (
        SaturationProbeResult,
        SeedScore,
    )
    from erre_sandbox.evidence.saturation.trace_ddl import SaturationTraceRow

SATURATION_VERDICT_SCHEMA_VERSION: Final[str] = "saturation-verdict-1"
"""Sidecar schema version — bump on any breaking field change."""

SATURATION_VERDICT_SIDECAR_SUFFIX: Final[str] = ".saturation_verdict.json"
"""Sidecar suffix appended to the first capture's filename for the default --out."""

_SHA256_CHUNK: Final[int] = 1 << 20
"""1 MiB read chunk for the source-file sha256 (streamed, never slurped whole)."""


class FrozenThresholds(BaseModel):
    """The ADR section 3.0 frozen values, echoed into the sidecar verbatim.

    These are copied from :mod:`.constants` (the single source of truth) so a reader
    can confirm the verdict used the pre-registered thresholds and nothing was tuned
    after the result was seen (ADR section 7). They are reported, never re-decided.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_total_modulation: float
    fingerprint_precision: int
    epsilon_mod: float
    eta_pinned: float
    slope_tol: float
    w_term: int
    t_warmup: int
    t_run_min: int
    terminal_presence_min: int
    engagement_min: float
    min_active_channels: int
    drop_high: float
    transient_high: float
    theta_high: float
    theta_low: float
    n_seeds: int


class SourceProvenance(BaseModel):
    """One input capture's audit record (path + content hash + read summary)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    sha256: str
    row_count: int
    seeds: tuple[int, ...]
    max_tick: int | None


class SeedReport(BaseModel):
    """Per-seed diagnostics serialised from a ``SeedScore`` (ADR section 3.1-3.5)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    seed: int
    label: str
    valid: bool
    invalid_reason: str | None
    t_run: int
    sat_frac: float | None
    engagement_rate: float
    drop_rate: float
    transient_active_rate: float
    gate_pass: bool
    total_channels: int
    n_active: int
    n_eligible: int
    n_saturated: int
    n_transient_active: int
    n_terminal_exit: int
    n_boundary_floor: int


class SaturationVerdictReport(BaseModel):
    """The serialised 3-way verdict + per-seed evidence + provenance + thresholds."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    run_id: str
    computed_at: datetime
    verdict: str
    median_sat_frac: float | None
    n_valid_seeds: int
    notes: str
    seeds: tuple[SeedReport, ...]
    sources: tuple[SourceProvenance, ...]
    thresholds: FrozenThresholds

    def to_sidecar_dict(self) -> dict[str, object]:
        """JSON-serialisable dict."""
        return self.model_dump(mode="json")


def _frozen_thresholds() -> FrozenThresholds:
    """Snapshot the ADR section 3.0 constants into the sidecar model."""
    return FrozenThresholds(
        max_total_modulation=_c.MAX_TOTAL_MODULATION,
        fingerprint_precision=_c.FINGERPRINT_PRECISION,
        epsilon_mod=_c.EPSILON_MOD,
        eta_pinned=_c.ETA_PINNED,
        slope_tol=_c.SLOPE_TOL,
        w_term=_c.W_TERM,
        t_warmup=_c.T_WARMUP,
        t_run_min=_c.T_RUN_MIN,
        terminal_presence_min=_c.TERMINAL_PRESENCE_MIN,
        engagement_min=_c.ENGAGEMENT_MIN,
        min_active_channels=_c.MIN_ACTIVE_CHANNELS,
        drop_high=_c.DROP_HIGH,
        transient_high=_c.TRANSIENT_HIGH,
        theta_high=_c.THETA_HIGH,
        theta_low=_c.THETA_LOW,
        n_seeds=_c.N_SEEDS,
    )


def _seed_report(seed: SeedScore) -> SeedReport:
    return SeedReport(
        seed=seed.seed,
        label=seed.label,
        valid=seed.valid,
        invalid_reason=seed.invalid_reason,
        t_run=seed.t_run,
        sat_frac=seed.sat_frac,
        engagement_rate=seed.engagement_rate,
        drop_rate=seed.drop_rate,
        transient_active_rate=seed.transient_active_rate,
        gate_pass=seed.gate_pass,
        total_channels=seed.total_channels,
        n_active=seed.n_active,
        n_eligible=seed.n_eligible,
        n_saturated=seed.n_saturated,
        n_transient_active=seed.n_transient_active,
        n_terminal_exit=seed.n_terminal_exit,
        n_boundary_floor=seed.n_boundary_floor,
    )


def file_sha256(path: Path | str) -> str:
    """Stream a file's SHA-256 (hex) for source provenance."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(_SHA256_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_source_provenance(
    path: Path | str, rows: Sequence[SaturationTraceRow]
) -> SourceProvenance:
    """Build one capture's provenance record from its path + the rows read from it.

    The SHA-256 is of the file bytes (auditable identity); ``row_count`` / ``seeds``
    / ``max_tick`` summarise what the loader actually read, so a verdict reader can
    cross-check the trace coverage without re-opening the DuckDB.
    """
    seeds = tuple(sorted({r.seed for r in rows}))
    max_tick = max((r.tick for r in rows), default=None)
    return SourceProvenance(
        path=str(path),
        sha256=file_sha256(path),
        row_count=len(rows),
        seeds=seeds,
        max_tick=max_tick,
    )


def build_saturation_verdict_report(
    result: SaturationProbeResult,
    *,
    run_id: str,
    computed_at: datetime,
    sources: tuple[SourceProvenance, ...],
) -> SaturationVerdictReport:
    """Convert the scorer's dataclass result into the durable sidecar model."""
    return SaturationVerdictReport(
        schema_version=SATURATION_VERDICT_SCHEMA_VERSION,
        run_id=run_id,
        computed_at=computed_at,
        verdict=result.verdict,
        median_sat_frac=result.median_sat_frac,
        n_valid_seeds=result.n_valid_seeds,
        notes=result.notes,
        seeds=tuple(_seed_report(s) for s in result.seeds),
        sources=sources,
        thresholds=_frozen_thresholds(),
    )


def saturation_verdict_sidecar_path_for(base_path: Path | str) -> Path:
    """Return the ``<base>.saturation_verdict.json`` sibling path."""
    p = Path(base_path)
    return p.with_name(p.name + SATURATION_VERDICT_SIDECAR_SUFFIX)


def write_saturation_verdict_sidecar_atomic(
    path: Path | str, report: SaturationVerdictReport
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


def read_saturation_verdict_sidecar(path: Path | str) -> SaturationVerdictReport:
    """Read + validate a ``*.saturation_verdict.json`` sidecar."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return SaturationVerdictReport.model_validate(raw)


__all__ = [
    "SATURATION_VERDICT_SCHEMA_VERSION",
    "SATURATION_VERDICT_SIDECAR_SUFFIX",
    "FrozenThresholds",
    "SaturationVerdictReport",
    "SeedReport",
    "SourceProvenance",
    "build_saturation_verdict_report",
    "build_source_provenance",
    "file_sha256",
    "read_saturation_verdict_sidecar",
    "saturation_verdict_sidecar_path_for",
    "write_saturation_verdict_sidecar_atomic",
]
