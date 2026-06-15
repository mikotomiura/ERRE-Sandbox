"""CLI: III-a deterministic replay driver (versioned-measurement ADR §5.2 primary).

Re-applies one captured ``floor`` + ``hint`` stream under both carry arms — the **only**
difference between the ON and OFF arm is ``stm_carry`` — and emits arm-tagged saturation
captures (+ a self-contained hint trace + a U4 sidecar) that flow **unchanged** into the
U4 manifest builder → versioned verdict CLI. The LLM is never re-invoked; the recorded
hint disposition is re-evaluated per arm (Codex HIGH-1), which is what makes the
contrast clean and the output bit-stable.

Pipeline per source capture (an individual-layer-on natural DuckDB carrying the PR-1
``swm_floor_input_trace`` + the ``swm_hint_engagement_trace``):

1. ``assemble_replay_source`` reads + fail-fast-validates the source into a canonical
   stream (dup / census / provenance, Codex HIGH-3) — ``evidence`` layer.
2. ``cognition.world_model_replay.replay_arm`` threads the unchanged reconcile kernel
   for each arm — ``cognition`` layer (HIGH-4).
3. this CLI writes each arm's saturation + hint rows into a fresh DuckDB and an
   arm-tagged sidecar that inherits the source provenance (persona / run_idx / seed /
   seed_salt), so the U4 builder's cross-checks pass (MED-1).

Then ``build_paired_manifest(contrast_kind="replay", hint_on/off=<arm db>)`` grounds the
3 pairs into a manifest (HIGH-2: hint wiring is mandatory or V3 → NOT_EVALUATED). Run as
``python -m erre_sandbox.cli.versioned_replay`` (the repo convention).

Scope: this is CPU plumbing — it computes nothing about the thesis. The GPU source run
and the real verdict are out of scope (a later task). An all-empty-floor source produces
no saturation rows and is rejected by the builder as unscorable (MED-4).
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final

import duckdb

from erre_sandbox.cognition.world_model_replay import ReplayInputTick, replay_arm
from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.capture_sidecar import (
    SidecarV1,
    read_sidecar,
    sidecar_path_for,
    write_sidecar_atomic,
)
from erre_sandbox.evidence.eval_store import atomic_temp_rename
from erre_sandbox.evidence.hint_engagement.trace_ddl import (
    TABLE_NAME as HINT_TABLE_NAME,
)
from erre_sandbox.evidence.hint_engagement.trace_ddl import (
    bootstrap_hint_engagement_trace_schema,
    build_hint_engagement_trace_row,
)
from erre_sandbox.evidence.hint_engagement.trace_ddl import (
    column_names as _hint_columns,
)
from erre_sandbox.evidence.saturation.replay_source import (
    ReplaySource,
    ReplaySourceError,
    assemble_replay_source,
)
from erre_sandbox.evidence.saturation.trace_ddl import (
    TABLE_NAME as SATURATION_TABLE_NAME,
)
from erre_sandbox.evidence.saturation.trace_ddl import (
    bootstrap_saturation_trace_schema,
    build_saturation_trace_rows,
)
from erre_sandbox.evidence.saturation.trace_ddl import (
    column_names as _saturation_columns,
)
from erre_sandbox.evidence.saturation.verdict_report import file_sha256
from erre_sandbox.evidence.saturation.versioned_verdict_manifest_builder import (
    CapturePairing,
    PairedManifestBuildError,
    build_paired_manifest,
)

if TYPE_CHECKING:
    from erre_sandbox.cognition.world_model_replay import ReplayOutputTick
    from erre_sandbox.evidence.saturation.versioned_verdict_report import (
        VersionedVerdictManifest,
    )

logger = logging.getLogger(__name__)

REPLAY_CONTRACT_VERSION: Final[str] = "versioned-replay-1"
"""Behavioural tag for the replay driver; recorded in each arm sidecar (audit drift)."""

ARTIFACT_KIND_REPLAY_ARM: Final[str] = "replay_arm"
"""Sidecar ``artifact_kind`` marking a replay output (no ``raw_dialog``; not a dialog
capture, so the normal capture audit does not apply — MED-1)."""

_STRUCTURAL_EXIT: Final[int] = 2
_REQUIRE_PAIRS: Final[int] = 3
"""N=3 binding: a single-seed contrast cannot yield a verdict."""

_ARM_SUFFIX: Final[dict[bool, str]] = {True: "replay_on", False: "replay_off"}


class ReplayDriverError(RuntimeError):
    """A source capture cannot be replayed (missing sidecar / wrong condition)."""


def _read_source(source_db: Path) -> tuple[ReplaySource, SidecarV1]:
    """Read + validate one source capture's stream and its provenance sidecar."""
    if not source_db.is_file():
        raise ReplayDriverError(f"source capture is not a file: {source_db}")
    sidecar_path = sidecar_path_for(source_db)
    if not sidecar_path.is_file():
        raise ReplayDriverError(
            f"source capture has no sidecar (need persona/run_idx/seed/seed_salt "
            f"provenance to tag replay arms): {sidecar_path}"
        )
    sidecar = read_sidecar(sidecar_path)
    if sidecar.condition != "natural":
        raise ReplayDriverError(
            f"source sidecar condition={sidecar.condition!r}, replay is a "
            "natural-condition contrast"
        )
    if sidecar.seed is None or sidecar.seed_salt is None:
        raise ReplayDriverError(
            f"source sidecar lacks seed / seed_salt provenance (pre-U4 capture): "
            f"{sidecar_path}"
        )
    con = duckdb.connect(str(source_db), read_only=True)
    try:
        source = assemble_replay_source(con)
    finally:
        con.close()
    if source.seed != sidecar.seed:
        raise ReplayDriverError(
            f"source row seed {source.seed} != sidecar seed {sidecar.seed} "
            f"({source_db})"
        )
    return source, sidecar


def _write_arm_capture(
    out_db: Path,
    results: list[ReplayOutputTick],
    *,
    run_id: str,
    seed: int,
) -> None:
    """Write one arm's saturation + hint rows into a fresh DuckDB (canonical order).

    ``results`` is already canonically ordered (``replay_arm`` sorts individuals then
    ticks); rows are inserted in that order and, within a tick, in floor-entry order, so
    the logical table content is deterministic (Codex MED-2: physical file bytes /
    sidecar timestamps are out of the determinism claim). Each arm DB is self-contained
    (it carries its own hint trace), so the manifest can point ``hint_on/off`` at the
    arm DB itself (HIGH-2).
    """
    sat_cols = _saturation_columns()
    sat_insert = (
        f"INSERT INTO {METRICS_SCHEMA}.{SATURATION_TABLE_NAME}"  # noqa: S608 — static identifiers only
        f" ({', '.join(sat_cols)}) VALUES ({', '.join('?' for _ in sat_cols)})"
    )
    hint_cols = _hint_columns()
    hint_insert = (
        f"INSERT INTO {METRICS_SCHEMA}.{HINT_TABLE_NAME}"  # noqa: S608 — static identifiers only
        f" ({', '.join(hint_cols)}) VALUES ({', '.join('?' for _ in hint_cols)})"
    )
    con = duckdb.connect(str(out_db), read_only=False)
    try:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {METRICS_SCHEMA}")
        bootstrap_saturation_trace_schema(con, METRICS_SCHEMA)
        bootstrap_hint_engagement_trace_schema(con, METRICS_SCHEMA)
        for r in results:
            for sat_row in build_saturation_trace_rows(
                r.snapshot,
                run_id=run_id,
                seed=seed,
                individual_id=r.individual_id,
                tick=r.tick,
                individual_layer_enabled=True,
            ):
                con.execute(sat_insert, sat_row.to_row())
            hint_row = build_hint_engagement_trace_row(
                r.disposition,
                run_id=run_id,
                seed=seed,
                individual_id=r.individual_id,
                tick=r.tick,
                individual_layer_enabled=True,
            )
            con.execute(hint_insert, hint_row.to_row())
    finally:
        con.close()


def _write_arm_sidecar(
    out_db: Path,
    *,
    source_sidecar: SidecarV1,
    source_sha256: str,
    stm_carry_on: bool,
    saturation_rows: int,
) -> None:
    """Write an arm-tagged sidecar inheriting source provenance (MED-1).

    All U4-builder-checked fields are pinned: ``status='complete'`` /
    ``condition='natural'`` / ``stm_carry_arm`` / ``seed`` / ``seed_salt`` / ``persona``
    / ``run_idx`` are inherited from the source so ``expected_run_id`` matches the row
    ``run_id``; ``duckdb_path`` is the final absolute arm-DB path (samefile guard). The
    extra ``artifact_kind`` / source SHA / contract version mark this as a non-dialog
    replay output (the normal capture audit does not apply — no ``raw_dialog``).
    """
    # Built via ``model_validate`` (not the typed ctor) so the ``extra='allow'`` audit
    # fields (artifact_kind / source SHA / contract version) are accepted.
    sidecar = SidecarV1.model_validate(
        {
            "status": "complete",
            "stop_reason": "complete",
            "focal_target": 0,
            "focal_observed": 0,
            "total_rows": saturation_rows,
            "wall_timeout_min": 0.0,
            "drain_completed": True,
            "runtime_drain_timeout": False,
            "git_sha": source_sidecar.git_sha,
            "captured_at": datetime.now(UTC).isoformat(),
            "persona": source_sidecar.persona,
            "condition": "natural",
            "run_idx": source_sidecar.run_idx,
            "duckdb_path": str(out_db.resolve(strict=False)),
            "elapsed_seconds": None,
            "stm_carry_arm": "on" if stm_carry_on else "off",
            "seed": source_sidecar.seed,
            "seed_salt": source_sidecar.seed_salt,
            "artifact_kind": ARTIFACT_KIND_REPLAY_ARM,
            "source_sha256": source_sha256,
            "replay_contract_version": REPLAY_CONTRACT_VERSION,
        }
    )
    write_sidecar_atomic(sidecar_path_for(out_db), sidecar)


def replay_source_to_pair(source_db: Path, out_dir: Path) -> CapturePairing:
    """Replay one source into an ON/OFF arm DuckDB pair (+ sidecars) in *out_dir*.

    Returns the :class:`CapturePairing` (with ``hint_on``/``hint_off`` pointed at the
    self-contained arm DBs, HIGH-2). The two arms share ``run_id`` / ``seed`` and differ
    only by ``stm_carry`` — exactly the seam the frozen scorer pairs on.
    """
    source, source_sidecar = _read_source(source_db)
    source_sha = file_sha256(source_db)
    out_dir.mkdir(parents=True, exist_ok=True)
    stream = [
        ReplayInputTick(
            individual_id=t.individual_id,
            tick=t.tick,
            floor=t.floor,
            source_disposition=t.source_disposition,
        )
        for t in source.ticks
    ]
    arm_dbs: dict[bool, Path] = {}
    for stm_carry_on in (True, False):
        results = replay_arm(stream, stm_carry=stm_carry_on)
        out_db = out_dir / f"{source.run_id}_{_ARM_SUFFIX[stm_carry_on]}.duckdb"
        _write_arm_capture(out_db, results, run_id=source.run_id, seed=source.seed)
        saturation_rows = sum(len(r.snapshot.base_floor.entries) for r in results)
        _write_arm_sidecar(
            out_db,
            source_sidecar=source_sidecar,
            source_sha256=source_sha,
            stm_carry_on=stm_carry_on,
            saturation_rows=saturation_rows,
        )
        arm_dbs[stm_carry_on] = out_db
    return CapturePairing(
        on_capture=arm_dbs[True],
        off_capture=arm_dbs[False],
        hint_on=arm_dbs[True],
        hint_off=arm_dbs[False],
    )


def run_replay(
    source_dbs: list[Path],
    *,
    out_dir: Path,
    source_run_id_base: str,
    manifest_path: Path,
) -> VersionedVerdictManifest:
    """Replay every source into arm pairs and build the grounded replay manifest.

    Each source becomes one ON/OFF pair; ``build_paired_manifest`` then machine-grounds
    the compose (sidecar cross-check + preflight assemble + N=3 completeness) with
    ``contrast_kind="replay"`` and hint wiring (HIGH-2). Raises on any structural
    defect; a valid return is the manifest the verdict CLI consumes.
    """
    pairings = [replay_source_to_pair(db, out_dir) for db in source_dbs]
    return build_paired_manifest(
        pairings,
        source_run_id_base=source_run_id_base,
        manifest_path=manifest_path,
        contrast_kind="replay",
        require_pairs=_REQUIRE_PAIRS,
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="erre-versioned-replay",
        description=(
            "Replay a fixed floor/hint stream under both carry arms (the only "
            "difference is stm_carry) and emit arm-tagged captures + a grounded replay "
            "manifest for the versioned verdict CLI. The LLM is never re-invoked."
        ),
    )
    parser.add_argument(
        "--source",
        required=True,
        action="append",
        metavar="PATH",
        help=(
            f"A source natural capture (repeat exactly {_REQUIRE_PAIRS} times for the "
            "N=3 binding). Must be individual-layer-on with a U4 sidecar."
        ),
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        metavar="DIR",
        help="Directory for the arm captures, sidecars and manifest.",
    )
    parser.add_argument(
        "--source-run-id-base",
        required=True,
        help="Pairing-key base; each pair gets <base>_pair<i> as its source_run_id.",
    )
    parser.add_argument(
        "--manifest",
        metavar="PATH",
        help="Manifest JSON output path (default <out-dir>/replay_manifest.json).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _build_arg_parser().parse_args(argv)
    out_dir = Path(args.out_dir)
    source_dbs = [Path(s) for s in args.source]
    manifest_path = (
        Path(args.manifest)
        if args.manifest is not None
        else out_dir / "replay_manifest.json"
    )

    try:
        manifest = run_replay(
            source_dbs,
            out_dir=out_dir,
            source_run_id_base=args.source_run_id_base,
            manifest_path=manifest_path,
        )
    except (ReplayDriverError, ReplaySourceError, PairedManifestBuildError) as exc:
        # A rejected replay is an expected control-flow outcome (bad source / mis-paired
        # compose), not a crash — report and exit non-zero with no manifest written.
        logger.error("replay rejected (no manifest written): %s", exc)  # noqa: TRY400
        return _STRUCTURAL_EXIT

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = manifest_path.with_name(manifest_path.name + ".tmp")
    tmp_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    atomic_temp_rename(tmp_path, manifest_path)

    logger.info(
        "replay manifest written sources=%d entries=%d out=%s",
        len(source_dbs),
        len(manifest.entries),
        manifest_path,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
