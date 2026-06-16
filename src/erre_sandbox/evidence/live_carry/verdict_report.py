"""Durable sidecar contract for the III-a live-carry cross-arm verdict.

The scorer's :func:`~erre_sandbox.evidence.live_carry.scorer.score_live_carry` is a
pure function over a sequence of
:class:`~erre_sandbox.evidence.live_carry.trace_reader.LiveCarryCapture`; this module
is its **durable artifact contract**. A frozen Pydantic model serialises the routed
verdict, the M0/M1/M2 component outcomes, the per-source provenance (path + sha256 +
the matrix keys ``seed`` / ``arm`` / ``replicate_id`` + row counts), and the frozen
§0 thresholds — the last echoed verbatim from :mod:`.constants` so the sidecar itself
carries the evidence that no threshold was tuned after the result was seen
(forking-paths guard). Mirrors ``evidence.hint_engagement.verdict_report`` /
``evidence.saturation.verdict_report``.

No verdict logic lives here: ``score_live_carry`` owns the entire decision. This
module imports only the scorer's result types (for typing) and the constants — never
the cognition layer — so it stays on the ``evidence`` side of the dependency boundary.
What it serialises is **verdict-readiness** (a compute path), not a verdict: no GPU
live-exec data exists yet.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime  # noqa: TC003 — runtime use in a pydantic field
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict

from erre_sandbox.evidence.live_carry import constants as _c

if TYPE_CHECKING:
    from erre_sandbox.evidence.live_carry.scorer import LiveCarryResult

LIVE_CARRY_VERDICT_SCHEMA_VERSION: Final[str] = "live-carry-verdict-1"
"""Sidecar schema version — bump on any breaking field change."""

LIVE_CARRY_VERDICT_SIDECAR_SUFFIX: Final[str] = ".live_carry_verdict.json"
"""Sidecar suffix appended to the first capture's filename for the default --out."""

_SHA256_CHUNK: Final[int] = 1 << 20
"""1 MiB read chunk for the source-file sha256 (streamed, never slurped whole)."""


class FrozenThresholds(BaseModel):
    """The ADR §0 frozen values, echoed verbatim (reported, never re-decided)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    r_min: float
    degenerate_null_floor: float
    on_noise_factor: float
    m0_engagement_floor: int
    coverage_min: float
    min_tick_pairs: int
    m2_cap: float
    m2_transient_tol: float
    m2_coherence_margin: float
    m2_throughput_ratio: float
    reach_null_max: float
    reach_pos_min: float
    n_seed: int
    rerun_per_arm: int


class SourceProvenance(BaseModel):
    """One input capture's audit record (path + content hash + matrix keys)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    sha256: str
    seed: int | None
    arm: str | None
    replicate_id: int | None
    floor_row_count: int
    saturation_row_count: int
    coherence_row_count: int


class M0Report(BaseModel):
    """M0 engagement component (per-seed ON r0 retained-offset events)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    events_per_seed: tuple[int, ...]


class M1Report(BaseModel):
    """M1 distal-separation component (paired / null / sanity + gate flags)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    go: bool
    coverage_ok: bool
    nulls_complete: bool
    sanity_complete: bool
    rank_non_overlap: bool
    ratio_ok: bool
    on_noise_ok: bool
    s_on_off: tuple[float | None, ...]
    s_off_off_null: tuple[float | None, ...]
    s_on_on_sanity: tuple[float | None, ...]
    coverage_ratios: tuple[float | None, ...]
    valid_tick_pairs: tuple[int, ...]
    notes: tuple[str, ...]


class M2Report(BaseModel):
    """M2 boundedness / non-inferiority component."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    range_ok: bool
    cap_ok: bool
    coherence_ok: bool
    throughput_ok: bool
    notes: tuple[str, ...]


class LiveCarryVerdictReport(BaseModel):
    """The serialised cross-arm verdict + components + provenance + thresholds."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    run_id: str
    computed_at: datetime
    verdict: str
    seeds: tuple[int, ...]
    m0: M0Report | None
    m1: M1Report | None
    m2: M2Report | None
    notes: str
    sources: tuple[SourceProvenance, ...]
    thresholds: FrozenThresholds

    def to_sidecar_dict(self) -> dict[str, object]:
        """JSON-serialisable dict."""
        return self.model_dump(mode="json")


def _frozen_thresholds() -> FrozenThresholds:
    """Snapshot the ADR §0 constants into the sidecar model."""
    return FrozenThresholds(
        r_min=_c.R_MIN,
        degenerate_null_floor=_c.DEGENERATE_NULL_FLOOR,
        on_noise_factor=_c.ON_NOISE_FACTOR,
        m0_engagement_floor=_c.M0_ENGAGEMENT_FLOOR,
        coverage_min=_c.COVERAGE_MIN,
        min_tick_pairs=_c.MIN_TICK_PAIRS,
        m2_cap=_c.M2_CAP,
        m2_transient_tol=_c.M2_TRANSIENT_TOL,
        m2_coherence_margin=_c.M2_COHERENCE_MARGIN,
        m2_throughput_ratio=_c.M2_THROUGHPUT_RATIO,
        reach_null_max=_c.REACH_NULL_MAX,
        reach_pos_min=_c.REACH_POS_MIN,
        n_seed=_c.N_SEED,
        rerun_per_arm=_c.RERUN_PER_ARM,
    )


def file_sha256(path: Path | str) -> str:
    """Stream a file's SHA-256 (hex) for source provenance."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(_SHA256_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_live_carry_verdict_report(
    result: LiveCarryResult,
    *,
    run_id: str,
    computed_at: datetime,
    sources: tuple[SourceProvenance, ...],
) -> LiveCarryVerdictReport:
    """Convert the scorer's dataclass result into the durable sidecar model."""
    m0 = (
        None
        if result.m0 is None
        else M0Report(
            status=result.m0.status, events_per_seed=result.m0.events_per_seed
        )
    )
    m1 = (
        None
        if result.m1 is None
        else M1Report(
            go=result.m1.go,
            coverage_ok=result.m1.coverage_ok,
            nulls_complete=result.m1.nulls_complete,
            sanity_complete=result.m1.sanity_complete,
            rank_non_overlap=result.m1.rank_non_overlap,
            ratio_ok=result.m1.ratio_ok,
            on_noise_ok=result.m1.on_noise_ok,
            s_on_off=result.m1.s_on_off,
            s_off_off_null=result.m1.s_off_off_null,
            s_on_on_sanity=result.m1.s_on_on_sanity,
            coverage_ratios=result.m1.coverage_ratios,
            valid_tick_pairs=result.m1.valid_tick_pairs,
            notes=result.m1.notes,
        )
    )
    m2 = (
        None
        if result.m2 is None
        else M2Report(
            status=result.m2.status,
            range_ok=result.m2.range_ok,
            cap_ok=result.m2.cap_ok,
            coherence_ok=result.m2.coherence_ok,
            throughput_ok=result.m2.throughput_ok,
            notes=result.m2.notes,
        )
    )
    return LiveCarryVerdictReport(
        schema_version=LIVE_CARRY_VERDICT_SCHEMA_VERSION,
        run_id=run_id,
        computed_at=computed_at,
        verdict=result.verdict,
        seeds=result.seeds,
        m0=m0,
        m1=m1,
        m2=m2,
        notes=result.notes,
        sources=sources,
        thresholds=_frozen_thresholds(),
    )


def live_carry_verdict_sidecar_path_for(base_path: Path | str) -> Path:
    """Return the ``<base>.live_carry_verdict.json`` sibling path."""
    p = Path(base_path)
    return p.with_name(p.name + LIVE_CARRY_VERDICT_SIDECAR_SUFFIX)


def write_live_carry_verdict_sidecar_atomic(
    path: Path | str, report: LiveCarryVerdictReport
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


def read_live_carry_verdict_sidecar(path: Path | str) -> LiveCarryVerdictReport:
    """Read + validate a ``*.live_carry_verdict.json`` sidecar."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return LiveCarryVerdictReport.model_validate(raw)


__all__ = [
    "LIVE_CARRY_VERDICT_SCHEMA_VERSION",
    "LIVE_CARRY_VERDICT_SIDECAR_SUFFIX",
    "FrozenThresholds",
    "LiveCarryVerdictReport",
    "M0Report",
    "M1Report",
    "M2Report",
    "SourceProvenance",
    "build_live_carry_verdict_report",
    "file_sha256",
    "live_carry_verdict_sidecar_path_for",
    "read_live_carry_verdict_sidecar",
    "write_live_carry_verdict_sidecar_atomic",
]
