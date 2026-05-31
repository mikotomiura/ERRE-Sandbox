"""M11-C3b verdict sidecar (``*.c3b_verdict.json``) contract (B-3).

The verdict scorer (:mod:`c3b_verdict`) is a pure function over dataclasses; this
module is its **durable artifact contract**: a frozen Pydantic model that
serialises the four-state verdict, the per-seed / per-axis / per-encoder-gate
evidence, and the encoder-panel provenance (id + revision SHA + library pin, ADR
§5.1) so a real run's GO/REJECT/inconclusive/invalid decision is reproducible and
auditable. The bge-m3 exploratory encoder is recorded with ``gated=False`` —
its centroid/floor gate is reported (報告必須) but never enters the agreement
aggregation (gate 非寄与, ADR §5.1).

Provenance source of record is ``d2-encoder-allowlist-plan-b.json`` (full SHA +
lib pin, normative). The SHAs/pins are transcribed here as module ``Final``
constants so the sidecar carries them without a runtime file read.
"""

from __future__ import annotations

import json
from datetime import datetime  # noqa: TC003  # runtime use in pydantic field
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict

from erre_sandbox.evidence.individuation.c3b_verdict import (
    EXPLORATORY_ENCODER_IDS,
    PRIMARY_ENCODER_IDS,
)
from erre_sandbox.evidence.individuation.policy import INDIVIDUATION_SCHEMA_VERSION

if TYPE_CHECKING:
    from erre_sandbox.evidence.individuation.c3b_verdict import (
        AxisResult,
        EncoderGate,
        SeedResult,
        VerdictReport,
    )

C3B_VERDICT_SIDECAR_SUFFIX: str = ".c3b_verdict.json"
"""Sidecar suffix appended to the pilot's verdict artifact filename."""

# Normative provenance (d2-encoder-allowlist-plan-b.json, ADR §5.1 / §8).
_ENCODER_REVISIONS: Final[dict[str, str]] = {
    "sentence-transformers/all-mpnet-base-v2": (
        "e8c3b32edf5434bc2275fc9bab85f82640a19130"
    ),
    "intfloat/multilingual-e5-large": "3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3",
    "BAAI/bge-m3": "5617a9f61b028005a4858fdac845db406aefb181",
}
LIB_PINS: Final[dict[str, str]] = {
    "sentence_transformers": "3.4.1",
    "transformers": "4.57.6",
}


class EncoderProvenance(BaseModel):
    """One panel encoder's normative identity (ADR §5.1)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_id: str
    revision_sha: str
    role: str  # "primary" | "exploratory"
    gated: bool


class AxisReport(BaseModel):
    """One hard axis' outcome for one seed (centroid / burrows / throughput)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: str
    reason: str


class EncoderGateReport(BaseModel):
    """One encoder's centroid gate evidence (ADR §4.2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    encoder_id: str
    outcome: str
    reason: str
    median_cross: float | None = None
    min_cross: float | None = None
    floor: float | None = None
    direction_positive: bool | None = None
    gated: bool


class SeedReport(BaseModel):
    """Per-seed scoring evidence (or the invalid reason that stopped it)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    seed: int
    valid: bool
    invalid_reason: str | None = None
    centroid: AxisReport | None = None
    burrows: AxisReport | None = None
    throughput: AxisReport | None = None
    encoder_gates: tuple[EncoderGateReport, ...] = ()
    exploratory_gates: tuple[EncoderGateReport, ...] = ()


class C3bVerdictReport(BaseModel):
    """The serialised four-state verdict + the evidence that produced it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    run_id: str
    computed_at: datetime
    verdict: str
    reason: str
    seeds: tuple[SeedReport, ...] = ()
    encoder_panel: tuple[EncoderProvenance, ...] = ()
    lib_pins: dict[str, str] = {}  # frozen model, value is read-only

    def to_sidecar_dict(self) -> dict[str, object]:
        """JSON-serialisable dict."""
        return self.model_dump(mode="json")


def _encoder_panel_provenance() -> tuple[EncoderProvenance, ...]:
    """Build the ADR §5.1 panel provenance (primary gated, exploratory ungated)."""
    primary = [
        EncoderProvenance(
            model_id=model_id,
            revision_sha=_ENCODER_REVISIONS[model_id],
            role="primary",
            gated=True,
        )
        for model_id in PRIMARY_ENCODER_IDS
    ]
    exploratory = [
        EncoderProvenance(
            model_id=model_id,
            revision_sha=_ENCODER_REVISIONS[model_id],
            role="exploratory",
            gated=False,
        )
        for model_id in EXPLORATORY_ENCODER_IDS
    ]
    return (*primary, *exploratory)


def _axis_report(axis: AxisResult | None) -> AxisReport | None:
    if axis is None:
        return None
    return AxisReport(outcome=axis.outcome.value, reason=axis.reason)


def _gate_report(gate: EncoderGate, *, gated: bool) -> EncoderGateReport:
    return EncoderGateReport(
        encoder_id=gate.encoder_id,
        outcome=gate.outcome.value,
        reason=gate.reason,
        median_cross=gate.median_cross,
        min_cross=gate.min_cross,
        floor=gate.floor,
        direction_positive=gate.direction_positive,
        gated=gated,
    )


def _seed_report(seed: SeedResult) -> SeedReport:
    return SeedReport(
        seed=seed.seed,
        valid=seed.valid,
        invalid_reason=seed.invalid_reason,
        centroid=_axis_report(seed.centroid),
        burrows=_axis_report(seed.burrows),
        throughput=_axis_report(seed.throughput),
        encoder_gates=tuple(_gate_report(g, gated=True) for g in seed.encoder_gates),
        exploratory_gates=tuple(
            _gate_report(g, gated=False) for g in seed.exploratory_gates
        ),
    )


def from_verdict_report(
    report: VerdictReport,
    *,
    computed_at: datetime,
) -> C3bVerdictReport:
    """Convert the scorer's dataclass verdict into the durable sidecar model."""
    return C3bVerdictReport(
        schema_version=INDIVIDUATION_SCHEMA_VERSION,
        run_id=report.run_id,
        computed_at=computed_at,
        verdict=report.verdict.value,
        reason=report.reason,
        seeds=tuple(_seed_report(s) for s in report.seeds),
        encoder_panel=_encoder_panel_provenance(),
        lib_pins=dict(LIB_PINS),
    )


def c3b_verdict_sidecar_path_for(base_path: Path | str) -> Path:
    """Return the ``<base>.c3b_verdict.json`` sibling path."""
    p = Path(base_path)
    return p.with_name(p.name + C3B_VERDICT_SIDECAR_SUFFIX)


def write_c3b_verdict_sidecar_atomic(
    path: Path | str, report: C3bVerdictReport
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


def read_c3b_verdict_sidecar(path: Path | str) -> C3bVerdictReport:
    """Read + validate a ``*.c3b_verdict.json`` sidecar."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return C3bVerdictReport.model_validate(raw)


__all__ = [
    "C3B_VERDICT_SIDECAR_SUFFIX",
    "LIB_PINS",
    "AxisReport",
    "C3bVerdictReport",
    "EncoderGateReport",
    "EncoderProvenance",
    "SeedReport",
    "c3b_verdict_sidecar_path_for",
    "from_verdict_report",
    "read_c3b_verdict_sidecar",
    "write_c3b_verdict_sidecar_atomic",
]
