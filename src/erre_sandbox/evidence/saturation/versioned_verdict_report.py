"""Manifest + assembler + durable sidecar for the **versioned** saturation verdict.

The frozen ``score_versioned_saturation``
(:mod:`erre_sandbox.evidence.saturation.versioned_loader`) is the **sole** verdict
authority (versioned-measurement ADR §3): it re-scores an arm-tagged
:class:`~erre_sandbox.evidence.saturation.versioned_loader.ArmRunBundle` sequence into a
retention-across-fingerprint-change verdict and never touches the frozen saturation
statistics. This module is the **plumbing** around it — it adds no verdict logic. Three
concerns live here:

* **manifest** (案 C external tagging, F3 / DA-VM-5): the operator declares each
  capture's ``arm`` + a ``source_run_id`` pairing key in a JSON manifest, so the *trace
  schema is never changed* to carry the arm. A two-level manifest (``schema_version`` /
  ``contrast_kind`` / ``envelope`` / ``entries``) records the contrast envelope for
  audit (Codex HIGH-1) — full row-level envelope verification needs trace columns (案 B)
  and is out of scope (deferred to a run-harness task + superseding ADR).
* **assembler** (F4 fail-fast): the scorer pairs on ``(source_run_id, seed)`` and does
  **not** detect a mis-pairing (it never validates ``run_id`` and silently overwrites a
  duplicate row). The assembler closes that gap *before* the scorer sees the data —
  run_id/seed exactly-one, natural-key de-dup, hint identity match, cross-bundle /
  physical-alias de-dup, and per-pairing population (individual-id set) agreement. A
  structural violation raises a typed error; the scorer never runs on a broken compose.
* **sidecar** (frozen Pydantic): the serialised verdict + per-partition diagnostics +
  per-source provenance (sha256 / arm / run_id / seed / source_run_id / max_tick …) +
  the §3.0' thresholds echoed verbatim from the constants (forking-paths audit) + the
  normalised manifest and its SHA-256 (HIGH-1).

The split that the CLI relies on (F5): the assembler raises only on **structural**
anomalies (mis-tagged / duplicated / mis-paired inputs); everything the scorer treats as
a **scientific** outcome (empty/partial hint, ``individual_layer_enabled=False``, NaN,
short run, NO_PAIR, N≠3, INCONCLUSIVE) passes straight through so the CLI still writes a
sidecar and exits 0. See ``.steering/20260614-versioned-verdict-cli/decisions.md``.
"""

from __future__ import annotations

import json
import re
from datetime import datetime  # noqa: TC003 — runtime use in a pydantic field
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

import duckdb
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.hint_engagement.loader import read_hint_engagement_trace_rows
from erre_sandbox.evidence.hint_engagement.trace_ddl import (
    TABLE_NAME as HINT_TABLE_NAME,
)
from erre_sandbox.evidence.saturation import constants as _c
from erre_sandbox.evidence.saturation import versioned_constants as _vc
from erre_sandbox.evidence.saturation.loader import read_saturation_trace_rows
from erre_sandbox.evidence.saturation.trace_ddl import TABLE_NAME
from erre_sandbox.evidence.saturation.verdict_report import SeedReport, file_sha256
from erre_sandbox.evidence.saturation.versioned_loader import ArmRunBundle

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.evidence.hint_engagement.trace_ddl import HintEngagementTraceRow
    from erre_sandbox.evidence.saturation.loader import SeedScore
    from erre_sandbox.evidence.saturation.trace_ddl import SaturationTraceRow
    from erre_sandbox.evidence.saturation.versioned_loader import (
        VersionedPartitionScore,
        VersionedSaturationResult,
    )

VERSIONED_SATURATION_VERDICT_SCHEMA_VERSION: Final[str] = (
    "versioned-saturation-verdict-1"
)
"""Sidecar schema version — bump on any breaking field change."""

VERSIONED_VERDICT_MANIFEST_SCHEMA_VERSION: Final[str] = "versioned-verdict-manifest-1"
"""Manifest schema version the assembler accepts (Codex HIGH-1)."""

SCORER_CONTRACT_VERSION: Final[str] = "versioned-loader-1"
"""Behavioural contract tag for ``score_versioned_saturation`` (Codex MED-3).

Bumped by a deliberate edit whenever the versioned scorer's decision behaviour changes
(including the constants-external ``_CAP_TOL`` / ``[-1, 1]`` range checks that the
threshold echo cannot pin). Recorded in the sidecar so a reader can detect scorer drift
that a pure threshold echo would miss."""

VERSIONED_SATURATION_VERDICT_SIDECAR_SUFFIX: Final[str] = (
    ".versioned_saturation_verdict.json"
)
"""Sidecar suffix appended to the first capture's filename for the default --out."""

_SQL_IDENTIFIER_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
"""A bare, unquoted SQL identifier — the only shape the loader's SELECT accepts."""


# ---------------------------------------------------------------------------
# Typed errors (F4 / F5) — both are structural anomalies (non-zero exit, no sidecar)
# ---------------------------------------------------------------------------


class VersionedVerdictManifestError(RuntimeError):
    """Manifest unreadable / unparseable / schema-invalid / points at a missing file."""


class VersionedVerdictAssemblyError(RuntimeError):
    """Row-level integrity violation in a capture or across bundles (mis-tag / dup)."""


# ---------------------------------------------------------------------------
# Manifest models (案 C, JSON input; F3 / Codex HIGH-1)
# ---------------------------------------------------------------------------


class VersionedManifestEntry(BaseModel):
    """One arm-tagged capture: ``{capture, arm, source_run_id, hint_capture}``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    capture: str
    arm: Literal["ON", "OFF"]
    source_run_id: str
    hint_capture: str | None = None


class VersionedVerdictManifest(BaseModel):
    """The operator-supplied contrast manifest (two-level; Codex HIGH-1).

    ``envelope`` is a free-form operator declaration (persona set / model / N / I …)
    recorded for audit only — the trace schema carries no envelope columns (案 B is out
    of scope), so it cannot be verified row-level. ``contrast_kind`` is recorded, not
    over-constrained: both replay and live pair on ``source_run_id``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    contrast_kind: Literal["replay", "live"]
    envelope: dict[str, object] = Field(default_factory=dict)
    entries: tuple[VersionedManifestEntry, ...]


# ---------------------------------------------------------------------------
# Sidecar models (frozen Pydantic)
# ---------------------------------------------------------------------------


class VersionedFrozenThresholds(BaseModel):
    """§3.0' versioned thresholds + the inherited §3.0 values, echoed verbatim.

    Copied from :mod:`.versioned_constants` (the 7 new values) and :mod:`.constants`
    (the inherited §3.0 values the versioned gate reuses) so a reader can confirm no
    threshold was tuned after the result was seen (ADR §3.0' / decisions F-2). The
    constants-external ``_CAP_TOL`` / value-range checks are pinned by
    :data:`SCORER_CONTRACT_VERSION` instead (Codex MED-3).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    # §3.0' new (versioned_constants)
    rho_retain_min: float
    min_d_fp: int
    crossfp_channel_min: int
    retained_channel_min: int
    disappear_margin: float
    h_safety: int
    cancel_high: float
    # inherited §3.0 (constants) the versioned gate reuses
    engagement_min: float
    min_active_channels: int
    transient_high: float
    theta_high: float
    theta_low: float
    n_seeds: int
    epsilon_mod: float
    t_warmup: int
    max_total_modulation: float


class VersionedSourceProvenance(BaseModel):
    """One input capture's audit record (path + content hash + read summary)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str  # resolved
    raw_path: str  # as written in the manifest
    sha256: str
    row_count: int
    arm: str
    run_id: str
    seed: int
    source_run_id: str
    schema_name: str
    table: str
    min_tick: int | None
    max_tick: int | None
    n_individuals: int
    file_size_bytes: int
    hint_path: str | None
    hint_sha256: str | None
    hint_row_count: int | None


class VersionedPartitionReport(BaseModel):
    """Per-``(arm, run_id, source_run_id, seed)`` versioned diagnostics (ADR §2-§5)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    arm: str
    run_id: str
    source_run_id: str
    seed: int
    valid: bool
    invalid_reason: str | None
    d_fp: int
    r_retained: int
    retained_rate: float | None
    n_retained_channels: int
    n_crossfp_channels: int
    channel_disappearance_rate: float | None
    v1_pass: bool
    v2_status: str
    v4_pass: bool
    v3_status: str
    cancel_rate: float | None
    non_inferiority: str | None
    gate_pass: bool
    versioned_label: str | None
    control_complete: bool | None
    frozen_seed: SeedReport


class VersionedSaturationVerdictReport(BaseModel):
    """The serialised versioned verdict + per-partition evidence + provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    scorer_contract_version: str
    run_id: str
    computed_at: datetime
    contrast_kind: str
    on_verdict: str
    off_control_complete: bool | None
    notes: str
    manifest_sha256: str
    manifest: dict[str, object]
    on_partitions: tuple[VersionedPartitionReport, ...]
    off_partitions: tuple[VersionedPartitionReport, ...]
    sources: tuple[VersionedSourceProvenance, ...]
    thresholds: VersionedFrozenThresholds

    def to_sidecar_dict(self) -> dict[str, object]:
        """JSON-serialisable dict."""
        return self.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Manifest loading + path resolution (Codex MED-1)
# ---------------------------------------------------------------------------


def load_manifest(path: Path | str) -> VersionedVerdictManifest:
    """Read + schema-validate a versioned verdict manifest (structural on failure)."""
    p = Path(path)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VersionedVerdictManifestError(
            f"manifest unreadable or not valid JSON: {p}: {exc}"
        ) from exc
    try:
        manifest = VersionedVerdictManifest.model_validate(raw)
    except ValidationError as exc:
        raise VersionedVerdictManifestError(
            f"manifest does not match the versioned-verdict-manifest schema: {p}: {exc}"
        ) from exc
    if manifest.schema_version != VERSIONED_VERDICT_MANIFEST_SCHEMA_VERSION:
        raise VersionedVerdictManifestError(
            f"manifest schema_version {manifest.schema_version!r} != expected "
            f"{VERSIONED_VERDICT_MANIFEST_SCHEMA_VERSION!r}: {p}"
        )
    if not manifest.entries:
        raise VersionedVerdictManifestError(f"manifest has no entries: {p}")
    return manifest


def resolve_manifest_ref(manifest_path: Path | str, ref: str) -> Path:
    """Resolve a manifest-relative path against the manifest's parent dir (MED-1).

    A relative ``capture`` / ``hint_capture`` is interpreted relative to the manifest
    file's directory, never the process cwd, so the same manifest reads the same files
    regardless of where the CLI is invoked. Shared by the assembler and the CLI
    collision guard so both resolve identically.
    """
    candidate = Path(ref)
    if not candidate.is_absolute():
        candidate = Path(manifest_path).parent / candidate
    return candidate


def _require_sql_identifier(value: str, *, what: str) -> None:
    """Defence-in-depth: reject a non-identifier schema/table at the API too (MED-2)."""
    if not _SQL_IDENTIFIER_RE.match(value):
        raise VersionedVerdictAssemblyError(
            f"{what} is not a bare SQL identifier: {value!r}"
        )


# ---------------------------------------------------------------------------
# Assembler (F4 + Codex HIGH-1/2/5) — bundle 1 個 = capture 1 個
# ---------------------------------------------------------------------------


def _read_capture_with_hash_check(
    capture: Path, schema: str, table: str
) -> tuple[list[SaturationTraceRow], str]:
    """Read a capture read-only, bracketed by a before/after SHA-256 (HIGH-5)."""
    sha_before = file_sha256(capture)
    con = duckdb.connect(str(capture), read_only=True)
    try:
        rows = read_saturation_trace_rows(con, schema=schema, table=table)
    finally:
        con.close()
    sha_after = file_sha256(capture)
    if sha_before != sha_after:
        raise VersionedVerdictAssemblyError(
            f"capture changed on disk during read (sha256 mismatch): {capture}"
        )
    return rows, sha_after


def _read_hint_with_hash_check(
    hint_capture: Path, schema: str, table: str
) -> tuple[list[HintEngagementTraceRow], str]:
    """Read a hint capture read-only, bracketed by a before/after SHA-256 (HIGH-5)."""
    sha_before = file_sha256(hint_capture)
    con = duckdb.connect(str(hint_capture), read_only=True)
    try:
        rows = read_hint_engagement_trace_rows(con, schema=schema, table=table)
    finally:
        con.close()
    sha_after = file_sha256(hint_capture)
    if sha_before != sha_after:
        raise VersionedVerdictAssemblyError(
            f"hint capture changed on disk during read (sha256): {hint_capture}"
        )
    return rows, sha_after


def _derive_one(values: set[str | int], *, what: str, where: str) -> str | int:
    """Return the single member of *values* or raise (exactly-one, F4)."""
    if len(values) != 1:
        raise VersionedVerdictAssemblyError(
            f"{what} is not exactly-one in {where}: found {sorted(map(str, values))}"
        )
    return next(iter(values))


def _reject_saturation_natural_key_dup(
    rows: Sequence[SaturationTraceRow], where: str
) -> None:
    """Reject a duplicate ``(run_id,seed,individual_id,axis,key,tick)`` row (F4)."""
    seen: set[tuple[str, int, str, str, str, int]] = set()
    for r in rows:
        key = (r.run_id, r.seed, r.individual_id, r.axis, r.key, r.tick)
        if key in seen:
            raise VersionedVerdictAssemblyError(
                f"duplicate saturation natural key {key} in {where}"
            )
        seen.add(key)


def _reject_hint_natural_key_dup(
    rows: Sequence[HintEngagementTraceRow], where: str
) -> None:
    """Reject a duplicate ``(run_id,seed,individual_id,tick)`` hint row (F4)."""
    seen: set[tuple[str, int, str, int]] = set()
    for r in rows:
        key = (r.run_id, r.seed, r.individual_id, r.tick)
        if key in seen:
            raise VersionedVerdictAssemblyError(
                f"duplicate hint natural key {key} in {where}"
            )
        seen.add(key)


def _validate_hint(
    hint_rows: Sequence[HintEngagementTraceRow],
    *,
    capture_run_id: str,
    capture_seed: int,
    where: str,
) -> None:
    """Hint identity must match the ON capture exactly; dup rejected (F4).

    An *empty* hint capture is **not** a structural error: it flows through as
    ``hint_rows=[]`` so the scorer maps it to a scientific V3 INVALID (decisions table).
    Identity is only checked when the hint trace actually carries rows.
    """
    if not hint_rows:
        return
    hint_run_id = _derive_one(
        {r.run_id for r in hint_rows}, what="hint run_id", where=where
    )
    hint_seed = _derive_one({r.seed for r in hint_rows}, what="hint seed", where=where)
    if hint_run_id != capture_run_id or hint_seed != capture_seed:
        raise VersionedVerdictAssemblyError(
            f"hint identity ({hint_run_id!r}, {hint_seed}) does not match capture "
            f"({capture_run_id!r}, {capture_seed}) in {where}"
        )
    _reject_hint_natural_key_dup(hint_rows, where)


def _reject_capture_alias_dup(resolved: list[Path]) -> None:
    """Reject the same physical capture registered as two bundles (HIGH-2)."""
    for i in range(len(resolved)):
        for j in range(i + 1, len(resolved)):
            a, b = resolved[i], resolved[j]
            same = a == b or (
                a.exists() and b.exists() and a.samefile(b)  # hardlink-aware
            )
            if same:
                raise VersionedVerdictAssemblyError(
                    f"the same physical capture is registered twice: {a} and {b}"
                )


def _reject_cross_bundle_dups(
    bundles: Sequence[ArmRunBundle], individuals: Sequence[frozenset[str]]
) -> None:
    """Cross-bundle de-dup + per-pairing population agreement (HIGH-1/2).

    * ``(source_run_id, seed, arm)`` and ``(arm, run_id, seed)`` must each be unique —
      the scorer pairs on ``(source_run_id, seed)`` and would silently merge a re-used
      cell otherwise. A shared ``run_id`` across **different** arms is allowed (replay).
    * For every pairing ``(source_run_id, seed)`` that has both an ON and an OFF bundle,
      the two arms must cover the **same** set of ``individual_id`` (same population) —
      the only envelope agreement verifiable from the trace rows (HIGH-1).
    """
    seen_pair_arm: set[tuple[str, int, str]] = set()
    seen_arm_run_seed: set[tuple[str, str, int]] = set()
    pop_by_pair: dict[tuple[str, int], dict[str, frozenset[str]]] = {}
    for bundle, inds in zip(bundles, individuals, strict=True):
        seed = next(iter({r.seed for r in bundle.rows}))
        pair_arm = (bundle.source_run_id, seed, bundle.arm)
        if pair_arm in seen_pair_arm:
            raise VersionedVerdictAssemblyError(
                f"duplicate (source_run_id, seed, arm) bundle: {pair_arm}"
            )
        seen_pair_arm.add(pair_arm)
        arm_run_seed = (bundle.arm, bundle.run_id, seed)
        if arm_run_seed in seen_arm_run_seed:
            raise VersionedVerdictAssemblyError(
                f"duplicate (arm, run_id, seed) bundle: {arm_run_seed}"
            )
        seen_arm_run_seed.add(arm_run_seed)
        pop_by_pair.setdefault((bundle.source_run_id, seed), {})[bundle.arm] = inds
    for (source_run_id, seed), arms in pop_by_pair.items():
        if "ON" in arms and "OFF" in arms and arms["ON"] != arms["OFF"]:
            raise VersionedVerdictAssemblyError(
                "ON/OFF population (individual_id set) mismatch for pairing "
                f"(source_run_id={source_run_id!r}, seed={seed}): "
                f"ON\\OFF={sorted(arms['ON'] - arms['OFF'])} "
                f"OFF\\ON={sorted(arms['OFF'] - arms['ON'])}"
            )


def assemble_bundles(
    manifest: VersionedVerdictManifest,
    manifest_path: Path | str,
    *,
    schema: str = METRICS_SCHEMA,
    table: str = TABLE_NAME,
    hint_table: str = HINT_TABLE_NAME,
) -> tuple[list[ArmRunBundle], list[VersionedSourceProvenance]]:
    """Read + validate every capture into arm-tagged bundles (F4, fail-fast).

    Structural violations (mis-tag / dup / mis-pair / population mismatch / on-disk
    swap) raise :class:`VersionedVerdictAssemblyError` or
    :class:`VersionedVerdictManifestError`; the scorer never sees a broken compose.
    Everything the scorer treats as a scientific outcome is passed straight through.
    """
    manifest_path = Path(manifest_path)
    _require_sql_identifier(schema, what="--schema")
    _require_sql_identifier(table, what="--table")
    _require_sql_identifier(hint_table, what="hint table")

    bundles: list[ArmRunBundle] = []
    sources: list[VersionedSourceProvenance] = []
    individuals: list[frozenset[str]] = []
    resolved_captures: list[Path] = []

    for idx, entry in enumerate(manifest.entries):
        where = f"entry[{idx}] capture={entry.capture!r} arm={entry.arm}"
        capture = resolve_manifest_ref(manifest_path, entry.capture)
        if not capture.is_file():
            raise VersionedVerdictManifestError(
                f"manifest references a missing capture: {capture} ({where})"
            )
        resolved_captures.append(capture.resolve(strict=False))

        rows, sha = _read_capture_with_hash_check(capture, schema, table)
        if not rows:
            raise VersionedVerdictAssemblyError(
                f"capture has no saturation rows (run_id/seed undecidable): {where}"
            )
        run_id = str(_derive_one({r.run_id for r in rows}, what="run_id", where=where))
        seed = int(_derive_one({r.seed for r in rows}, what="seed", where=where))
        _reject_saturation_natural_key_dup(rows, where)

        hint_rows: list[HintEngagementTraceRow] | None = None
        hint_path_str: str | None = None
        hint_sha: str | None = None
        hint_count: int | None = None
        if entry.hint_capture is not None:
            hint_capture = resolve_manifest_ref(manifest_path, entry.hint_capture)
            if not hint_capture.is_file():
                raise VersionedVerdictManifestError(
                    f"manifest references a missing hint capture: {hint_capture} "
                    f"({where})"
                )
            hint_rows, hint_sha = _read_hint_with_hash_check(
                hint_capture, schema, hint_table
            )
            _validate_hint(
                hint_rows, capture_run_id=run_id, capture_seed=seed, where=where
            )
            hint_path_str = str(hint_capture.resolve(strict=False))
            hint_count = len(hint_rows)

        bundles.append(
            ArmRunBundle(
                arm=entry.arm,
                run_id=run_id,
                source_run_id=entry.source_run_id,
                rows=rows,
                hint_rows=hint_rows,
            )
        )
        individuals.append(frozenset(r.individual_id for r in rows))
        ticks = [r.tick for r in rows]
        sources.append(
            VersionedSourceProvenance(
                path=str(capture.resolve(strict=False)),
                raw_path=entry.capture,
                sha256=sha,
                row_count=len(rows),
                arm=entry.arm,
                run_id=run_id,
                seed=seed,
                source_run_id=entry.source_run_id,
                schema_name=schema,
                table=table,
                min_tick=min(ticks),
                max_tick=max(ticks),
                n_individuals=len({r.individual_id for r in rows}),
                file_size_bytes=capture.stat().st_size,
                hint_path=hint_path_str,
                hint_sha256=hint_sha,
                hint_row_count=hint_count,
            )
        )

    _reject_capture_alias_dup(resolved_captures)
    _reject_cross_bundle_dups(bundles, individuals)
    return bundles, sources


# ---------------------------------------------------------------------------
# Sidecar builders
# ---------------------------------------------------------------------------


def _frozen_thresholds() -> VersionedFrozenThresholds:
    """Snapshot the §3.0' + inherited §3.0 constants into the sidecar model."""
    return VersionedFrozenThresholds(
        rho_retain_min=_vc.RHO_RETAIN_MIN,
        min_d_fp=_vc.MIN_D_FP,
        crossfp_channel_min=_vc.CROSSFP_CHANNEL_MIN,
        retained_channel_min=_vc.RETAINED_CHANNEL_MIN,
        disappear_margin=_vc.DISAPPEAR_MARGIN,
        h_safety=_vc.H_SAFETY,
        cancel_high=_vc.CANCEL_HIGH,
        engagement_min=_c.ENGAGEMENT_MIN,
        min_active_channels=_c.MIN_ACTIVE_CHANNELS,
        transient_high=_c.TRANSIENT_HIGH,
        theta_high=_c.THETA_HIGH,
        theta_low=_c.THETA_LOW,
        n_seeds=_c.N_SEEDS,
        epsilon_mod=_c.EPSILON_MOD,
        t_warmup=_c.T_WARMUP,
        max_total_modulation=_c.MAX_TOTAL_MODULATION,
    )


def _seed_report(seed: SeedScore) -> SeedReport:
    """Serialise a frozen ``SeedScore`` into the shared ``SeedReport`` model."""
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


def _partition_report(part: VersionedPartitionScore) -> VersionedPartitionReport:
    return VersionedPartitionReport(
        arm=part.arm,
        run_id=part.run_id,
        source_run_id=part.source_run_id,
        seed=part.seed,
        valid=part.valid,
        invalid_reason=part.invalid_reason,
        d_fp=part.d_fp,
        r_retained=part.r_retained,
        retained_rate=part.retained_rate,
        n_retained_channels=part.n_retained_channels,
        n_crossfp_channels=part.n_crossfp_channels,
        channel_disappearance_rate=part.channel_disappearance_rate,
        v1_pass=part.v1_pass,
        v2_status=part.v2_status,
        v4_pass=part.v4_pass,
        v3_status=part.v3_status,
        cancel_rate=part.cancel_rate,
        non_inferiority=part.non_inferiority,
        gate_pass=part.gate_pass,
        versioned_label=part.versioned_label,
        control_complete=part.control_complete,
        frozen_seed=_seed_report(part.frozen_seed),
    )


def _partition_sort_key(part: VersionedPartitionScore) -> tuple[str, str, int]:
    return (part.arm, part.source_run_id, part.seed)


def _source_sort_key(src: VersionedSourceProvenance) -> tuple[str, str, int]:
    return (src.arm, src.source_run_id, src.seed)


def build_versioned_verdict_report(
    result: VersionedSaturationResult,
    *,
    run_id: str,
    computed_at: datetime,
    contrast_kind: str,
    manifest_sha256: str,
    manifest: VersionedVerdictManifest,
    sources: Sequence[VersionedSourceProvenance],
) -> VersionedSaturationVerdictReport:
    """Convert the scorer's dataclass result into the durable sidecar model.

    Partitions and sources are canonically sorted by ``(arm, source_run_id, seed)`` so a
    re-run over the same inputs renders a byte-stable sidecar (Codex LOW-1).
    """
    on_parts = tuple(
        _partition_report(p)
        for p in sorted(result.on_partitions, key=_partition_sort_key)
    )
    off_parts = tuple(
        _partition_report(p)
        for p in sorted(result.off_partitions, key=_partition_sort_key)
    )
    return VersionedSaturationVerdictReport(
        schema_version=VERSIONED_SATURATION_VERDICT_SCHEMA_VERSION,
        scorer_contract_version=SCORER_CONTRACT_VERSION,
        run_id=run_id,
        computed_at=computed_at,
        contrast_kind=contrast_kind,
        on_verdict=result.on_verdict,
        off_control_complete=result.off_control_complete,
        notes=result.notes,
        manifest_sha256=manifest_sha256,
        manifest=manifest.model_dump(mode="json"),
        on_partitions=on_parts,
        off_partitions=off_parts,
        sources=tuple(sorted(sources, key=_source_sort_key)),
        thresholds=_frozen_thresholds(),
    )


def versioned_saturation_verdict_sidecar_path_for(base_path: Path | str) -> Path:
    """Return the ``<base>.versioned_saturation_verdict.json`` sibling path."""
    p = Path(base_path)
    return p.with_name(p.name + VERSIONED_SATURATION_VERDICT_SIDECAR_SUFFIX)


def write_versioned_saturation_verdict_sidecar_atomic(
    path: Path | str, report: VersionedSaturationVerdictReport
) -> None:
    """Atomically write the verdict sidecar JSON (temp + same-fs rename).

    Refuses to clobber a pre-existing ``<out>.tmp`` (an unrelated file the fixed temp
    name would otherwise destroy, Codex MED-5).
    """
    from erre_sandbox.evidence.eval_store import atomic_temp_rename  # noqa: PLC0415

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


def read_versioned_saturation_verdict_sidecar(
    path: Path | str,
) -> VersionedSaturationVerdictReport:
    """Read + validate a ``*.versioned_saturation_verdict.json`` sidecar."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return VersionedSaturationVerdictReport.model_validate(raw)


__all__ = [
    "SCORER_CONTRACT_VERSION",
    "VERSIONED_SATURATION_VERDICT_SCHEMA_VERSION",
    "VERSIONED_SATURATION_VERDICT_SIDECAR_SUFFIX",
    "VERSIONED_VERDICT_MANIFEST_SCHEMA_VERSION",
    "VersionedFrozenThresholds",
    "VersionedManifestEntry",
    "VersionedPartitionReport",
    "VersionedSaturationVerdictReport",
    "VersionedSourceProvenance",
    "VersionedVerdictAssemblyError",
    "VersionedVerdictManifest",
    "VersionedVerdictManifestError",
    "assemble_bundles",
    "build_versioned_verdict_report",
    "load_manifest",
    "read_versioned_saturation_verdict_sidecar",
    "resolve_manifest_ref",
    "versioned_saturation_verdict_sidecar_path_for",
    "write_versioned_saturation_verdict_sidecar_atomic",
]
