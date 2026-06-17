"""Durable sidecar contract for the bond-affinity cross-arm near-miss verdict.

The capture-level entry ``score_bond_affinity_captures`` (over the pure
``score_bond_affinity``, in :mod:`erre_sandbox.evidence.relational.loader`) yields a
``BondAffinityProbeResult``; this module is its **durable artifact contract**. A frozen
Pydantic model serialises the routed verdict, the §3 per-cell near-miss distributions,
the v2 null-hierarchy quantities (the per-seed
``s_*`` signals + the ``*_ok`` decision flags so no single statistic is opaque, scorer
LOW-1), the per-source provenance (path + sha256 + the matrix keys ``seed`` / ``arm`` /
``replicate_id`` + row counts), and the frozen §1 thresholds — the last echoed verbatim
from :mod:`.constants` so the sidecar itself carries the evidence that no threshold was
tuned after the result was seen (forking-paths guard). Mirrors
``evidence.live_carry.verdict_report`` / ``evidence.saturation.verdict_report``.

No verdict logic lives here: ``score_bond_affinity`` (and the thin captures wrapper) own
the entire decision. This module imports only the scorer's result types (for typing) and
the constants — never the cognition layer — so it stays on the ``evidence`` side of the
dependency boundary. What it serialises is **verdict-readiness** (a compute path), not a
verdict: no GPU live-exec bond-affinity data exists yet.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime  # noqa: TC003 — runtime use in a pydantic field
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict

from erre_sandbox.evidence.relational import constants as _c

if TYPE_CHECKING:
    from erre_sandbox.evidence.relational.loader import (
        BondAffinityProbeResult,
        CellStats,
    )

BOND_AFFINITY_VERDICT_SCHEMA_VERSION: Final[str] = "bond-affinity-verdict-1"
"""Sidecar schema version — bump on any breaking field change."""

BOND_AFFINITY_VERDICT_SIDECAR_SUFFIX: Final[str] = ".bond_affinity_verdict.json"
"""Sidecar suffix appended to the first capture's filename for the default --out."""

_SHA256_CHUNK: Final[int] = 1 << 20
"""1 MiB read chunk for the source-file sha256 (streamed, never slurped whole)."""


class FrozenThresholds(BaseModel):
    """The freeze-ADR §1 frozen values, echoed verbatim (reported, never re-decided)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    belief_threshold: float
    belief_min_interactions: int
    eps_band_lo: float
    cap_offset: float
    cap_saturation_tol: float
    r_min_bond: float
    degenerate_gap_floor: float
    on_noise_factor: float
    min_near_miss_n: int
    min_paired_seeds: int
    slope_window: int


class SourceProvenance(BaseModel):
    """One input capture's audit record (path + content hash + matrix keys)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    sha256: str
    seed: int | None
    arm: str | None
    replicate_id: int | None
    bond_row_count: int
    saturation_row_count: int


class CellReport(BaseModel):
    """One ``(seed, arm, replicate)`` cell's §3 near-miss distribution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    seed: int
    arm: str
    replicate: int
    n: int
    unique_dyads: int
    p90_abs: float | None
    p95_abs: float | None
    max_abs: float | None
    eps_band_density: float | None
    n_trust: int
    n_clash: int
    n_neutral: int


class BondAffinityVerdictReport(BaseModel):
    """The serialised cross-arm verdict + §3 cells + null hierarchy + provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    run_id: str
    computed_at: datetime
    verdict: str
    paired_seeds: tuple[int, ...]
    cells: tuple[CellReport, ...]
    s_on_off: dict[int, float]
    s_off_off_null: dict[int, float]
    s_on_on_null: dict[int, float]
    median_s_on_off: float | None
    max_off_off_null: float | None
    max_on_on_null: float | None
    magnitude_ok: bool
    rank_ok: bool
    on_noise_ok: bool
    null_degenerate: bool
    notes: str
    sources: tuple[SourceProvenance, ...]
    thresholds: FrozenThresholds

    def to_sidecar_dict(self) -> dict[str, object]:
        """JSON-serialisable dict."""
        return self.model_dump(mode="json")


def _frozen_thresholds() -> FrozenThresholds:
    """Snapshot the freeze-ADR §1 constants into the sidecar model."""
    return FrozenThresholds(
        belief_threshold=_c.BELIEF_THRESHOLD,
        belief_min_interactions=_c.BELIEF_MIN_INTERACTIONS,
        eps_band_lo=_c.EPS_BAND_LO,
        cap_offset=_c.CAP_OFFSET,
        cap_saturation_tol=_c.CAP_SATURATION_TOL,
        r_min_bond=_c.R_MIN_BOND,
        degenerate_gap_floor=_c.DEGENERATE_GAP_FLOOR,
        on_noise_factor=_c.ON_NOISE_FACTOR,
        min_near_miss_n=_c.MIN_NEAR_MISS_N,
        min_paired_seeds=_c.MIN_PAIRED_SEEDS,
        slope_window=_c.SLOPE_WINDOW,
    )


def _cell_report(cell: CellStats) -> CellReport:
    """Convert one scorer ``CellStats`` into the durable cell report model."""
    return CellReport(
        seed=cell.seed,
        arm=cell.arm,
        replicate=cell.replicate,
        n=cell.n,
        unique_dyads=cell.unique_dyads,
        p90_abs=cell.p90_abs,
        p95_abs=cell.p95_abs,
        max_abs=cell.max_abs,
        eps_band_density=cell.eps_band_density,
        n_trust=cell.n_trust,
        n_clash=cell.n_clash,
        n_neutral=cell.n_neutral,
    )


def file_sha256(path: Path | str) -> str:
    """Stream a file's SHA-256 (hex) for source provenance."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(_SHA256_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_bond_affinity_verdict_report(
    result: BondAffinityProbeResult,
    *,
    run_id: str,
    computed_at: datetime,
    sources: tuple[SourceProvenance, ...],
) -> BondAffinityVerdictReport:
    """Convert the scorer's dataclass result into the durable sidecar model."""
    return BondAffinityVerdictReport(
        schema_version=BOND_AFFINITY_VERDICT_SCHEMA_VERSION,
        run_id=run_id,
        computed_at=computed_at,
        verdict=result.verdict,
        paired_seeds=result.paired_seeds,
        cells=tuple(_cell_report(c) for c in result.cells),
        s_on_off=dict(result.s_on_off),
        s_off_off_null=dict(result.s_off_off_null),
        s_on_on_null=dict(result.s_on_on_null),
        median_s_on_off=result.median_s_on_off,
        max_off_off_null=result.max_off_off_null,
        max_on_on_null=result.max_on_on_null,
        magnitude_ok=result.magnitude_ok,
        rank_ok=result.rank_ok,
        on_noise_ok=result.on_noise_ok,
        null_degenerate=result.null_degenerate,
        notes=result.notes,
        sources=sources,
        thresholds=_frozen_thresholds(),
    )


def bond_affinity_verdict_sidecar_path_for(base_path: Path | str) -> Path:
    """Return the ``<base>.bond_affinity_verdict.json`` sibling path."""
    p = Path(base_path)
    return p.with_name(p.name + BOND_AFFINITY_VERDICT_SIDECAR_SUFFIX)


def write_bond_affinity_verdict_sidecar_atomic(
    path: Path | str, report: BondAffinityVerdictReport
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


def read_bond_affinity_verdict_sidecar(path: Path | str) -> BondAffinityVerdictReport:
    """Read + validate a ``*.bond_affinity_verdict.json`` sidecar."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return BondAffinityVerdictReport.model_validate(raw)


__all__ = [
    "BOND_AFFINITY_VERDICT_SCHEMA_VERSION",
    "BOND_AFFINITY_VERDICT_SIDECAR_SUFFIX",
    "BondAffinityVerdictReport",
    "CellReport",
    "FrozenThresholds",
    "SourceProvenance",
    "bond_affinity_verdict_sidecar_path_for",
    "build_bond_affinity_verdict_report",
    "file_sha256",
    "read_bond_affinity_verdict_sidecar",
    "write_bond_affinity_verdict_sidecar_atomic",
]
