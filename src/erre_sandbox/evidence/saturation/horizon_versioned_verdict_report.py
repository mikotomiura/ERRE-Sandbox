"""Sidecar + builder for the **horizon-reserved** (Conditional-V2) saturation verdict.

Plumbing around the horizon compose scorer
(:func:`~erre_sandbox.evidence.saturation.horizon_versioned_loader.score_horizon_versioned_saturation`),
adding no verdict logic. It **reuses** the frozen versioned plumbing verbatim — the
manifest / assembler / per-source provenance / threshold echo are arm-and-manifest
concerns identical to the versioned verdict, so they are imported from
:mod:`erre_sandbox.evidence.saturation.versioned_verdict_report` (that frozen file is
never modified). On top it adds the Conditional-V2 forensic (admitted / excluded /
coverage), the frozen universal V2 verdict it overrides (``frozen`` sub-record, for the
diff), the mechanised compound ``overall_verdict`` (Codex U7 MED-3), and a runtime echo
of the frozen scorer's source-blob SHA-256s (Codex U7 MED-2: a provenance pin a pure
threshold echo cannot give).
"""

from __future__ import annotations

import hashlib
from datetime import datetime  # noqa: TC003 — runtime use in a pydantic field
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict

from erre_sandbox.evidence.saturation import versioned_constants as _vc
from erre_sandbox.evidence.saturation import versioned_loader as _vl
from erre_sandbox.evidence.saturation.versioned_verdict_report import (
    VersionedFrozenThresholds,
    VersionedPartitionReport,
    VersionedSourceProvenance,
    _frozen_thresholds,
    _partition_report,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.evidence.saturation.horizon_versioned_loader import (
        HorizonVersionedPartitionScore,
        HorizonVersionedSaturationResult,
    )
    from erre_sandbox.evidence.saturation.versioned_verdict_report import (
        VersionedVerdictManifest,
    )

HORIZON_VERSIONED_SATURATION_VERDICT_SCHEMA_VERSION: Final[str] = (
    "horizon-versioned-saturation-verdict-1"
)
"""Sidecar schema version — bump on any breaking field change."""

HORIZON_SCORER_CONTRACT_VERSION: Final[str] = "horizon-versioned-loader-1"
"""Behavioural contract tag for ``score_horizon_versioned_saturation`` (CV2 layer)."""

HORIZON_VERSIONED_SATURATION_VERDICT_SIDECAR_SUFFIX: Final[str] = (
    ".horizon_versioned_saturation_verdict.json"
)
"""Sidecar suffix appended to the first capture's filename for the default --out."""

_FROZEN_SCORER_SOURCES: Final[tuple[object, ...]] = (_vl, _vc)
"""Frozen modules whose source-blob SHA-256 is echoed for provenance (U7 MED-2)."""


# ---------------------------------------------------------------------------
# Sidecar models (frozen Pydantic)
# ---------------------------------------------------------------------------


class HorizonVersionedPartitionReport(BaseModel):
    """Frozen versioned partition (verbatim) + the horizon CV2 override + forensic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    frozen: VersionedPartitionReport  # the frozen versioned partition (frozen V2/gate)
    cv2_status: str
    n_admitted_channels: int
    n_excluded_channels: int
    coverage: float | None
    admitted_channels: tuple[str, ...]
    excluded_channels: tuple[str, ...]
    gate_pass: bool  # horizon (CV2-based) gate
    versioned_label: str | None  # horizon label


class HorizonVersionedSaturationVerdictReport(BaseModel):
    """The serialised horizon-reserved verdict + per-partition evidence + provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    scorer_contract_version: str
    frozen_scorer_contract_version: str
    run_id: str
    computed_at: datetime
    contrast_kind: str
    on_verdict: str
    off_control_complete: bool | None
    overall_verdict: str
    notes: str
    manifest_sha256: str
    manifest: dict[str, object]
    on_partitions: tuple[HorizonVersionedPartitionReport, ...]
    off_partitions: tuple[HorizonVersionedPartitionReport, ...]
    sources: tuple[VersionedSourceProvenance, ...]
    thresholds: VersionedFrozenThresholds
    frozen_scorer_blob_sha256: dict[str, str]

    def to_sidecar_dict(self) -> dict[str, object]:
        """JSON-serialisable dict."""
        return self.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _frozen_scorer_blob_sha256() -> dict[str, str]:
    """SHA-256 of the frozen scorer source files (provenance pin, Codex U7 MED-2)."""
    out: dict[str, str] = {}
    for module in _FROZEN_SCORER_SOURCES:
        path = Path(module.__file__)  # type: ignore[attr-defined]
        out[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _horizon_partition_report(
    part: HorizonVersionedPartitionScore,
) -> HorizonVersionedPartitionReport:
    f = part.cv2_forensic
    return HorizonVersionedPartitionReport(
        frozen=_partition_report(part.base),
        cv2_status=part.cv2_status,
        n_admitted_channels=f.n_admitted_channels,
        n_excluded_channels=f.n_excluded_channels,
        coverage=f.coverage,
        admitted_channels=f.admitted_channels,
        excluded_channels=f.excluded_channels,
        gate_pass=part.gate_pass,
        versioned_label=part.versioned_label,
    )


def _partition_sort_key(
    part: HorizonVersionedPartitionScore,
) -> tuple[str, str, int]:
    return (part.base.arm, part.base.source_run_id, part.base.seed)


def _source_sort_key(src: VersionedSourceProvenance) -> tuple[str, str, int]:
    return (src.arm, src.source_run_id, src.seed)


def build_horizon_versioned_verdict_report(
    result: HorizonVersionedSaturationResult,
    *,
    run_id: str,
    computed_at: datetime,
    contrast_kind: str,
    manifest_sha256: str,
    manifest: VersionedVerdictManifest,
    sources: Sequence[VersionedSourceProvenance],
) -> HorizonVersionedSaturationVerdictReport:
    """Convert the horizon scorer's result into the durable sidecar model.

    Partitions and sources are canonically sorted by ``(arm, source_run_id, seed)`` so a
    re-run over the same inputs renders a byte-stable sidecar.
    """
    on_parts = tuple(
        _horizon_partition_report(p)
        for p in sorted(result.on_partitions, key=_partition_sort_key)
    )
    off_parts = tuple(
        _horizon_partition_report(p)
        for p in sorted(result.off_partitions, key=_partition_sort_key)
    )
    return HorizonVersionedSaturationVerdictReport(
        schema_version=HORIZON_VERSIONED_SATURATION_VERDICT_SCHEMA_VERSION,
        scorer_contract_version=HORIZON_SCORER_CONTRACT_VERSION,
        frozen_scorer_contract_version="versioned-loader-1",
        run_id=run_id,
        computed_at=computed_at,
        contrast_kind=contrast_kind,
        on_verdict=result.on_verdict,
        off_control_complete=result.off_control_complete,
        overall_verdict=result.overall_verdict,
        notes=result.notes,
        manifest_sha256=manifest_sha256,
        manifest=manifest.model_dump(mode="json"),
        on_partitions=on_parts,
        off_partitions=off_parts,
        sources=tuple(sorted(sources, key=_source_sort_key)),
        thresholds=_frozen_thresholds(),
        frozen_scorer_blob_sha256=_frozen_scorer_blob_sha256(),
    )


def horizon_versioned_saturation_verdict_sidecar_path_for(
    base_path: Path | str,
) -> Path:
    """Return the ``<base>.horizon_versioned_saturation_verdict.json`` sibling path."""
    p = Path(base_path)
    return p.with_name(p.name + HORIZON_VERSIONED_SATURATION_VERDICT_SIDECAR_SUFFIX)


def write_horizon_versioned_saturation_verdict_sidecar_atomic(
    path: Path | str, report: HorizonVersionedSaturationVerdictReport
) -> None:
    """Atomically write the verdict sidecar JSON (temp + same-fs rename).

    Refuses to clobber a pre-existing ``<out>.tmp`` (Codex MED-5, mirrors the frozen
    versioned writer).
    """
    import json  # noqa: PLC0415

    from erre_sandbox.evidence.eval_store import atomic_temp_rename  # noqa: PLC0415
    from erre_sandbox.evidence.saturation.versioned_verdict_report import (  # noqa: PLC0415
        VersionedVerdictAssemblyError,
    )

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if tmp.exists():
        raise VersionedVerdictAssemblyError(
            f"refusing to overwrite a pre-existing temp file: {tmp}"
        )
    tmp.write_text(
        json.dumps(
            report.to_sidecar_dict(), ensure_ascii=False, indent=2, sort_keys=True
        ),
        encoding="utf-8",
    )
    atomic_temp_rename(tmp, path)


def read_horizon_versioned_saturation_verdict_sidecar(
    path: Path | str,
) -> HorizonVersionedSaturationVerdictReport:
    """Read + validate a ``*.horizon_versioned_saturation_verdict.json`` sidecar."""
    import json  # noqa: PLC0415

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return HorizonVersionedSaturationVerdictReport.model_validate(raw)


__all__ = [
    "HORIZON_SCORER_CONTRACT_VERSION",
    "HORIZON_VERSIONED_SATURATION_VERDICT_SCHEMA_VERSION",
    "HORIZON_VERSIONED_SATURATION_VERDICT_SIDECAR_SUFFIX",
    "HorizonVersionedPartitionReport",
    "HorizonVersionedSaturationVerdictReport",
    "build_horizon_versioned_verdict_report",
    "horizon_versioned_saturation_verdict_sidecar_path_for",
    "read_horizon_versioned_saturation_verdict_sidecar",
    "write_horizon_versioned_saturation_verdict_sidecar_atomic",
]
