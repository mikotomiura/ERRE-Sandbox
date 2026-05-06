"""``capture_sidecar`` — atomic JSON metadata sibling for eval capture files.

Spec: ``.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md`` §1.4.
Adopted in m9-eval-cli-partial-fix (ME-9 ADR) so partial / fatal / complete
captures can be **machine-distinguished** without re-opening the DuckDB file.

Design notes (Codex 2026-05-06 review reflected):

* ``CaptureStatus`` and ``StopReason`` are :class:`typing.Literal` so the
  ``_async_main`` 3-way ``match`` in :mod:`erre_sandbox.cli.eval_run_golden`
  can use ``assert_never`` for exhaustiveness.
* ``SidecarV1.model_config = ConfigDict(extra="allow")`` so a future
  ``event_log`` / ``q_and_a_subset`` additive field does not require a
  major schema_version bump (Codex Q2).
* ``write_sidecar_atomic`` reuses :func:`atomic_temp_rename` from
  :mod:`erre_sandbox.evidence.eval_store` for same-filesystem POSIX rename.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from erre_sandbox.evidence.eval_store import atomic_temp_rename

CaptureStatus = Literal["complete", "partial", "fatal"]
"""Top-level capture outcome (drives audit gate + return code)."""

StopReason = Literal[
    "complete",
    "wall_timeout",
    "fatal_duckdb_insert",
    "fatal_ollama",
    "fatal_drain_timeout",
    "fatal_incomplete_before_target",
    "fatal_runtime_exception",
]
"""Concrete reason capture stopped — pinned via Codex L2 review."""

SIDECAR_SUFFIX: Final[str] = ".capture.json"
"""Filename suffix appended to the DuckDB path (e.g. ``foo.duckdb.capture.json``)."""

SIDECAR_SCHEMA_VERSION: Final[str] = "1"
"""Current schema version. ``extra='allow'`` covers additive fields."""

_SIDECAR_MAX_BYTES: Final[int] = 1 * 1024 * 1024
"""Defensive cap on a single sidecar JSON read (security review 2026-05-06).

Sidecars are produced by our own CLI so legitimate files stay under a few KB
even with future ``event_log`` additions; a multi-MB sidecar after rsync
from G-GEAR is the symptom of corruption or tampering. The cap is generous
to avoid false positives but guards :func:`read_sidecar` against
loading-the-whole-file-into-memory DoS."""


class SidecarV1(BaseModel):
    """v1 metadata payload alongside ``<output>.duckdb``.

    The discriminated ``status`` + ``stop_reason`` pair is what the audit
    CLI (:mod:`erre_sandbox.cli.eval_audit`) reads to decide PASS / FAIL.
    ``total_rows`` and ``focal_observed`` are cross-checked against the
    DuckDB ``raw_dialog.dialog`` table; mismatch yields return code 5.
    """

    model_config = ConfigDict(extra="allow")

    schema_version: Literal["1"] = "1"
    status: CaptureStatus
    stop_reason: StopReason
    focal_target: int
    focal_observed: int
    total_rows: int
    wall_timeout_min: float
    drain_completed: bool
    runtime_drain_timeout: bool
    git_sha: str
    captured_at: str
    persona: str
    condition: Literal["stimulus", "natural"]
    run_idx: int
    duckdb_path: str


def sidecar_path_for(duckdb_path: Path | str) -> Path:
    """Return the conventional sidecar path for *duckdb_path*."""
    p = Path(duckdb_path)
    return p.with_suffix(p.suffix + SIDECAR_SUFFIX)


def expected_run_id(payload: SidecarV1) -> str:
    """Reconstruct the ``raw_dialog.dialog.run_id`` value the capture used.

    Reflects Codex H1 (audit must verify same-run integrity): the eval CLI
    builds ``run_id`` from ``f"{persona}_{condition}_run{run_idx}"`` and
    persists every row with it; audit re-derives the same string from the
    sidecar to detect cross-cell contamination.
    """
    return f"{payload.persona}_{payload.condition}_run{payload.run_idx}"


def write_sidecar_atomic(path: Path | str, payload: SidecarV1) -> None:
    """Atomically write *payload* as JSON to *path* (temp + same-fs rename).

    Uses :func:`atomic_temp_rename` so the rename fails loudly if *path*
    crosses a filesystem boundary (NFS / SMB / iCloud are out of scope per
    ME-2). The temp file lives next to *path* with a ``.tmp`` suffix and is
    overwritten on retry.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
    atomic_temp_rename(tmp, path)


def read_sidecar(path: Path | str) -> SidecarV1:
    """Read and validate a sidecar file.

    Raises :class:`pydantic.ValidationError` for schema violations (e.g.
    unknown ``status`` / ``stop_reason`` Literal value, missing required
    fields). The audit CLI converts this into return code 5 (mismatch);
    rescue tooling demands ``--force-rescue`` (Codex M4).

    Refuses files larger than :data:`_SIDECAR_MAX_BYTES` with
    :class:`OSError` so a corrupted / tampered sidecar cannot exhaust
    memory in the audit CLI (security review 2026-05-06 MEDIUM).
    """
    p = Path(path)
    size = p.stat().st_size
    if size > _SIDECAR_MAX_BYTES:
        msg = (
            f"sidecar {p!s} is {size} bytes, exceeds defensive cap {_SIDECAR_MAX_BYTES}"
        )
        raise OSError(msg)
    raw = json.loads(p.read_text(encoding="utf-8"))
    return SidecarV1.model_validate(raw)


__all__ = [
    "SIDECAR_SCHEMA_VERSION",
    "SIDECAR_SUFFIX",
    "CaptureStatus",
    "SidecarV1",
    "StopReason",
    "expected_run_id",
    "read_sidecar",
    "sidecar_path_for",
    "write_sidecar_atomic",
]
