"""M10-A S3.5 path(a) gate verdict sidecar (``*.path_a_verdict.json``) contract.

The scorer (:mod:`path_a_gate`) is a pure function over dataclasses; this module
is its **durable artifact contract**: a frozen Pydantic model that serialises the
five-state verdict, the per-seed / per-criterion evidence, and — crucially — the
:data:`~erre_sandbox.evidence.individuation.path_a_gate.NULL_CONTROL_KIND`
(``"swm_key_shuffle_projection"``) so the over-claim boundary (MF-1: this is the
measured-space projection of the §3.A④ null-control, **not** the ADR-literal
promoted-belief record label-shuffle) lives on the artifact itself.

Naming (CX-MED-3): the scorer returns a
:class:`~erre_sandbox.evidence.individuation.path_a_gate.PathAScoreReport`
dataclass; this module's Pydantic model is :class:`PathAVerdictReport` — mirroring
the C3b ``VerdictReport`` / ``C3bVerdictReport`` split.

The path(a) sidecar never reads the frozen ``c3b_verdict.json`` (the two gates are
independent, reactivate §3.X); it only serialises this evaluator's output.
"""

from __future__ import annotations

import json
from datetime import datetime  # noqa: TC003  # runtime use in pydantic field
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from erre_sandbox.evidence.individuation.policy import INDIVIDUATION_SCHEMA_VERSION

if TYPE_CHECKING:
    from erre_sandbox.evidence.individuation.path_a_gate import (
        CriterionResult,
        NullControlResult,
        PathAScoreReport,
        SeedScore,
    )

PATH_A_VERDICT_SIDECAR_SUFFIX: str = ".path_a_verdict.json"
"""Sidecar suffix appended to the path(a) gate artifact filename."""


class CriterionReport(BaseModel):
    """One criterion's (①②③) outcome for one seed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: str
    reason: str


class NullControlReport(BaseModel):
    """④ swm_key_shuffle_projection 3-way evidence for one seed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: str
    reason: str
    central: float | None = None
    p95: float | None = None
    k: int
    swm_raw_key_count: int | None = None
    swm_unique_key_count: int | None = None


class SeedReport(BaseModel):
    """Per-seed scoring evidence (or the invalid reason that stopped it)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_idx: int
    verdict: str
    reason: str
    invalid_reason: str | None = None
    belief_variance: CriterionReport | None = None
    belief_distribution: CriterionReport | None = None
    jaccard_separation: CriterionReport | None = None
    null_control: NullControlReport | None = None
    jaccard_median: float | None = None
    jaccard_valid_count: int | None = None
    belief_distribution_summary: tuple[
        tuple[str, tuple[tuple[str, int], ...]], ...
    ] = ()


class PathAVerdictReport(BaseModel):
    """The serialised five-state path(a) verdict + the evidence that produced it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    run_id: str
    computed_at: datetime
    verdict: str
    reason: str
    null_control_kind: str
    null_control_conformance: str
    seeds: tuple[SeedReport, ...] = ()

    def to_sidecar_dict(self) -> dict[str, object]:
        """JSON-serialisable dict."""
        return self.model_dump(mode="json")


def _criterion_report(result: CriterionResult | None) -> CriterionReport | None:
    if result is None:
        return None
    return CriterionReport(outcome=result.outcome.value, reason=result.reason)


def _null_control_report(result: NullControlResult | None) -> NullControlReport | None:
    if result is None:
        return None
    return NullControlReport(
        outcome=result.outcome.value,
        reason=result.reason,
        central=result.central,
        p95=result.p95,
        k=result.k,
        swm_raw_key_count=result.swm_raw_key_count,
        swm_unique_key_count=result.swm_unique_key_count,
    )


def _seed_report(seed: SeedScore) -> SeedReport:
    return SeedReport(
        run_idx=seed.run_idx,
        verdict=seed.verdict.value,
        reason=seed.reason,
        invalid_reason=seed.invalid_reason,
        belief_variance=_criterion_report(seed.belief_variance),
        belief_distribution=_criterion_report(seed.belief_distribution),
        jaccard_separation=_criterion_report(seed.jaccard_separation),
        null_control=_null_control_report(seed.null_control),
        jaccard_median=seed.jaccard_median,
        jaccard_valid_count=seed.jaccard_valid_count,
        belief_distribution_summary=seed.belief_distribution_summary,
    )


def from_score_report(
    report: PathAScoreReport,
    *,
    computed_at: datetime,
) -> PathAVerdictReport:
    """Convert the scorer's dataclass report into the durable sidecar model."""
    return PathAVerdictReport(
        schema_version=INDIVIDUATION_SCHEMA_VERSION,
        run_id=report.run_id,
        computed_at=computed_at,
        verdict=report.verdict.value,
        reason=report.reason,
        null_control_kind=report.null_control_kind,
        null_control_conformance=report.null_control_conformance,
        seeds=tuple(_seed_report(s) for s in report.seeds),
    )


def path_a_verdict_sidecar_path_for(base_path: Path | str) -> Path:
    """Return the ``<base>.path_a_verdict.json`` sibling path."""
    p = Path(base_path)
    return p.with_name(p.name + PATH_A_VERDICT_SIDECAR_SUFFIX)


def write_path_a_verdict_sidecar_atomic(
    path: Path | str, report: PathAVerdictReport
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


def read_path_a_verdict_sidecar(path: Path | str) -> PathAVerdictReport:
    """Read + validate a ``*.path_a_verdict.json`` sidecar."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return PathAVerdictReport.model_validate(raw)


__all__ = [
    "PATH_A_VERDICT_SIDECAR_SUFFIX",
    "CriterionReport",
    "NullControlReport",
    "PathAVerdictReport",
    "SeedReport",
    "from_score_report",
    "path_a_verdict_sidecar_path_for",
    "read_path_a_verdict_sidecar",
    "write_path_a_verdict_sidecar_atomic",
]
