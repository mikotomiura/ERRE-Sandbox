"""Build a **versioned-verdict 案 C manifest** from arm-tagged paired captures (U4).

The verdict authority (:mod:`erre_sandbox.cli.versioned_saturation_verdict`) consumes a
JSON *manifest* that externally tags each capture with its ``arm`` (ON / OFF) and a
``source_run_id`` pairing key — the trace schema never carries the arm (案 B is out of
scope). Hand-writing that manifest for a fork III-a paired run (ON×3 + OFF×3) before a
multi-hour GPU capture is the exact mis-tag / mis-pair fragility the
versioned-measurement chain exists to remove.

This module builds the manifest **and machine-grounds it** so a wrong compose fails fast
*before* it can be scored or claimed (it cannot prevent a wrong GPU capture from running
— it runs after capture — only stop a wrong capture being scored as a valid pair):

* **sidecar cross-check** — every capture's ``SidecarV1`` must declare
  ``status == "complete"``, ``condition == "natural"``, the same ``stm_carry_arm`` as
  the operator's role assignment, a ``duckdb_path`` that ``samefile``-resolves to the
  referenced capture (stale / swapped sidecar guard), and a consistent
  ``seed`` + ``seed_salt`` lineage.
* **preflight assemble** — the candidate manifest is run through the *same*
  ``assemble_bundles`` the verdict CLI uses, read-only, so the actual capture-row
  ``seed`` / ``run_id`` (which depend on the seed-manifest ``salt``, not on ``run_idx``
  parity) ground the pairing.
* **N=3 completeness** — exactly ``require_pairs`` pairs, that many distinct *actual*
  seeds, each with exactly one ON and one OFF, all one persona / natural condition.

``source_run_id`` is assigned per pair (``{base}_pair{i}``) so each contrast is
audit-distinct, mirroring the existing versioned tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import ValidationError

from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.capture_sidecar import (
    SidecarV1,
    expected_run_id,
    read_sidecar,
    sidecar_path_for,
)
from erre_sandbox.evidence.saturation.trace_ddl import TABLE_NAME
from erre_sandbox.evidence.saturation.versioned_verdict_report import (
    VERSIONED_VERDICT_MANIFEST_SCHEMA_VERSION,
    VersionedManifestEntry,
    VersionedVerdictAssemblyError,
    VersionedVerdictManifest,
    VersionedVerdictManifestError,
    assemble_bundles,
    resolve_manifest_ref,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Sequence


class PairedManifestBuildError(RuntimeError):
    """A paired-arm manifest could not be built (mis-tag / mis-pair / stale sidecar)."""


@dataclass(frozen=True)
class CapturePairing:
    """One ON/OFF capture pair (and optional hint captures) for a single seed."""

    on_capture: Path
    off_capture: Path
    hint_on: Path | None = None
    hint_off: Path | None = None


# ``arm`` Literal in the manifest is upper-case; the sidecar records lower-case.
_ARM_BY_ROLE: dict[str, Literal["ON", "OFF"]] = {"on": "ON", "off": "OFF"}


def _resolved(path: Path) -> Path:
    return path.resolve(strict=False)


def _read_sidecar_for(capture: Path) -> SidecarV1:
    """Read the capture's sidecar, wrapping any read/parse error as a build error."""
    sidecar_path = sidecar_path_for(capture)
    if not sidecar_path.is_file():
        raise PairedManifestBuildError(
            f"capture has no sidecar (cannot cross-check arm/seed): {sidecar_path}"
        )
    try:
        return read_sidecar(sidecar_path)
    except (ValidationError, OSError, ValueError) as exc:
        raise PairedManifestBuildError(
            f"sidecar unreadable or schema-invalid: {sidecar_path}: {exc}"
        ) from exc


def _check_sidecar_declares_arm(
    capture: Path, sidecar: SidecarV1, expected_arm: Literal["ON", "OFF"]
) -> None:
    """Fail-fast the sidecar-side declaration for one capture (HIGH-2)."""
    where = f"capture={capture}"
    if sidecar.status != "complete":
        raise PairedManifestBuildError(
            f"{where}: sidecar status={sidecar.status!r}, manifest requires "
            "'complete' (a partial / fatal capture is not pair-eligible)"
        )
    if sidecar.condition != "natural":
        raise PairedManifestBuildError(
            f"{where}: sidecar condition={sidecar.condition!r}, expected 'natural' "
            "(the stm-carry arm is a natural-condition contrast)"
        )
    if sidecar.stm_carry_arm is None:
        raise PairedManifestBuildError(
            f"{where}: sidecar has no stm_carry_arm (not an arm-bearing capture; "
            "produce it with --individual-layer on --stm-carry-arm on|off)"
        )
    declared = _ARM_BY_ROLE[sidecar.stm_carry_arm]
    if declared != expected_arm:
        raise PairedManifestBuildError(
            f"{where}: declared arm {expected_arm} but the capture's sidecar says "
            f"stm_carry_arm={sidecar.stm_carry_arm!r} ({declared})"
        )
    if sidecar.seed is None or sidecar.seed_salt is None:
        raise PairedManifestBuildError(
            f"{where}: sidecar has no seed / seed_salt provenance (pre-U4 capture); "
            "cannot ground the ON/OFF pairing on the actual seed"
        )
    # Stale / swapped sidecar guard: the sidecar must describe THIS file.
    recorded = Path(sidecar.duckdb_path)
    if _resolved(recorded) != _resolved(capture) and not (
        recorded.exists() and capture.exists() and recorded.samefile(capture)
    ):
        raise PairedManifestBuildError(
            f"{where}: sidecar duckdb_path={sidecar.duckdb_path!r} does not resolve "
            "to this capture (stale or swapped sidecar)"
        )


def build_paired_manifest(
    pairings: Sequence[CapturePairing],
    *,
    source_run_id_base: str,
    manifest_path: Path,
    contrast_kind: Literal["replay", "live"] = "live",
    envelope: dict[str, object] | None = None,
    schema: str = METRICS_SCHEMA,
    table: str = TABLE_NAME,
    require_pairs: int = 3,
) -> VersionedVerdictManifest:
    """Build + machine-ground a 案 C manifest from paired ON/OFF captures.

    ``manifest_path`` is where the manifest will be written; manifest-relative capture
    refs (and the preflight assemble) resolve against its parent, so the grounding sees
    the same files the verdict CLI later will. ``require_pairs`` is the N=3 binding (a
    single-seed contrast cannot yield a verdict); a different count raises.

    Raises :class:`PairedManifestBuildError` on any mis-tag / mis-pair / stale-sidecar /
    completeness violation, and surfaces the assembler's own structural errors.
    """
    if len(pairings) != require_pairs:
        raise PairedManifestBuildError(
            f"expected exactly {require_pairs} pair(s) (N=3 binding), got "
            f"{len(pairings)}; a single-seed contrast cannot yield a verdict"
        )

    # 1) Build the candidate entries (ON then OFF per pair, per-pair source_run_id).
    entries: list[VersionedManifestEntry] = []
    resolved_captures: list[Path] = []
    sidecars: list[SidecarV1] = []
    for i, pair in enumerate(pairings):
        source_run_id = f"{source_run_id_base}_pair{i}"
        for capture, hint, arm in (
            (pair.on_capture, pair.hint_on, "ON"),
            (pair.off_capture, pair.hint_off, "OFF"),
        ):
            resolved = resolve_manifest_ref(manifest_path, str(capture))
            if not resolved.is_file():
                raise PairedManifestBuildError(
                    f"pair {i} {arm}: capture is not a file: {resolved}"
                )
            sidecar = _read_sidecar_for(resolved)
            _check_sidecar_declares_arm(resolved, sidecar, arm)  # type: ignore[arg-type]
            entries.append(
                VersionedManifestEntry(
                    capture=str(capture),
                    arm=arm,  # type: ignore[arg-type]
                    source_run_id=source_run_id,
                    hint_capture=str(hint) if hint is not None else None,
                )
            )
            resolved_captures.append(resolved)
            sidecars.append(sidecar)

    # 2) Within-pair + cross-pair sidecar-level checks (cheap, before DuckDB reads).
    _check_pairing_consistency(sidecars, require_pairs=require_pairs)

    candidate = VersionedVerdictManifest(
        schema_version=VERSIONED_VERDICT_MANIFEST_SCHEMA_VERSION,
        contrast_kind=contrast_kind,
        envelope=envelope or {},
        entries=tuple(entries),
    )

    # 3) Preflight assemble: ground the compose in actual capture rows (HIGH-1/2/5).
    try:
        _bundles, sources = assemble_bundles(
            candidate, manifest_path, schema=schema, table=table
        )
    except (VersionedVerdictAssemblyError, VersionedVerdictManifestError) as exc:
        raise PairedManifestBuildError(
            f"preflight assemble rejected the candidate manifest: {exc}"
        ) from exc

    # 4) Cross-check actual row seed / run_id against the sidecar's recorded values.
    for entry, sidecar, source in zip(entries, sidecars, sources, strict=True):
        if sidecar.seed != source.seed:
            raise PairedManifestBuildError(
                f"capture={entry.capture}: actual row seed {source.seed} != sidecar "
                f"seed {sidecar.seed} (swapped capture or wrong sidecar)"
            )
        if expected_run_id(sidecar) != source.run_id:
            raise PairedManifestBuildError(
                f"capture={entry.capture}: actual row run_id {source.run_id!r} != "
                f"sidecar-derived {expected_run_id(sidecar)!r}"
            )

    # 5) N=3 completeness on the *actual* seeds (HIGH-5).
    _check_seed_completeness(sources, require_pairs=require_pairs)
    return candidate


def _check_pairing_consistency(
    sidecars: Sequence[SidecarV1],
    *,
    require_pairs: int,
) -> None:
    """Within-pair (persona/run_idx/seed) + cross-pair (one salt, distinct seeds)."""
    salts = {sc.seed_salt for sc in sidecars}
    if len(salts) != 1:
        raise PairedManifestBuildError(
            f"captures span multiple seed_salt lineages {sorted(map(str, salts))}; "
            "a contrast must share one seed-manifest salt"
        )
    personas = {sc.persona for sc in sidecars}
    if len(personas) != 1:
        raise PairedManifestBuildError(
            f"captures span multiple personas {sorted(personas)}; one contrast = "
            "one persona"
        )
    run_idxs: list[int] = []
    for i in range(require_pairs):
        on_sc, off_sc = sidecars[2 * i], sidecars[2 * i + 1]
        if on_sc.run_idx != off_sc.run_idx:
            raise PairedManifestBuildError(
                f"pair {i}: ON run_idx {on_sc.run_idx} != OFF run_idx "
                f"{off_sc.run_idx} (ON/OFF of a pair must share run_idx → seed)"
            )
        if on_sc.seed != off_sc.seed:
            raise PairedManifestBuildError(
                f"pair {i}: ON seed {on_sc.seed} != OFF seed {off_sc.seed} "
                "(ON/OFF cannot pair on (source_run_id, seed))"
            )
        run_idxs.append(on_sc.run_idx)
    if len(set(run_idxs)) != require_pairs:
        raise PairedManifestBuildError(
            f"pairs do not have distinct run_idx (got {run_idxs}); each pair must be a "
            "distinct seed"
        )


def _check_seed_completeness(sources: Sequence[object], *, require_pairs: int) -> None:
    """Exactly ``require_pairs`` distinct actual seeds, each with one ON + one OFF."""
    arms_by_seed: dict[int, list[str]] = {}
    for src in sources:
        seed = int(src.seed)  # type: ignore[attr-defined]
        arms_by_seed.setdefault(seed, []).append(str(src.arm))  # type: ignore[attr-defined]
    if len(arms_by_seed) != require_pairs:
        raise PairedManifestBuildError(
            f"expected {require_pairs} distinct actual seeds, got "
            f"{sorted(arms_by_seed)} ({len(arms_by_seed)})"
        )
    for seed, arms in sorted(arms_by_seed.items()):
        if sorted(arms) != ["OFF", "ON"]:
            raise PairedManifestBuildError(
                f"seed {seed} must have exactly one ON and one OFF, got {sorted(arms)}"
            )


__all__ = [
    "CapturePairing",
    "PairedManifestBuildError",
    "build_paired_manifest",
]
