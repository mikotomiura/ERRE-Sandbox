"""Read one bond-affinity capture into the cross-arm scorer's input shape.

Each live §5.3 capture is a ``.duckdb`` whose sibling ``.capture.json`` sidecar
carries the matrix-identity keys (``seed`` / ``stm_carry_arm`` / ``replicate_id``,
freeze ADR §0/§3) and whose ``metrics`` schema holds the two traces the bond-affinity
diagnostic reads — ``swm_bond_affinity_trace`` (the sub-threshold bond trajectory) and
``swm_modulation_saturation_trace`` (the cap-exposure join). This module opens the
capture **read-only** and pulls those traces via the **existing** lockstep readers —
:func:`~erre_sandbox.evidence.relational.loader.read_bond_affinity_trace_rows` and
:func:`~erre_sandbox.evidence.saturation.loader.read_saturation_trace_rows` — plus the
sidecar identity.

No scoring lives here: it only assembles the raw rows + the sidecar provenance into a
:class:`BondAffinityCapture`; the capture-level entry
:func:`~erre_sandbox.evidence.relational.loader.score_bond_affinity_captures` (and the
pure :func:`~erre_sandbox.evidence.relational.loader.score_bond_affinity` it wraps) owns
the entire decision. The sidecar's ``stm_carry_arm`` (``"on"`` / ``"off"``) is
normalised to the scorer's arm spelling (``"ON"`` / ``"OFF"``) here because the bond
scorer's cell keys are upper-case (unlike the live-carry scorer, which receives the raw
sidecar value). A genuinely unreadable capture raises :class:`BondAffinityReadError`
(loud-not-silent, mirroring ``live_carry.trace_reader``); matrix *incompleteness* is
**not** raised here — that is a scorer / assembler verdict (``INVALID_MEASUREMENT``), so
the sidecar's matrix keys are passed straight through (possibly ``None``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

import duckdb

from erre_sandbox.contracts.eval_paths import METRICS_SCHEMA
from erre_sandbox.evidence.capture_sidecar import read_sidecar, sidecar_path_for
from erre_sandbox.evidence.relational.loader import read_bond_affinity_trace_rows
from erre_sandbox.evidence.saturation.loader import read_saturation_trace_rows

if TYPE_CHECKING:
    from erre_sandbox.evidence.relational.bond_affinity_trace_ddl import (
        BondAffinityTraceRow,
    )
    from erre_sandbox.evidence.saturation.trace_ddl import SaturationTraceRow

_ARM_NORMALISE: Final[dict[str, str]] = {"on": "ON", "off": "OFF"}
"""Sidecar arm spelling (``Literal["on", "off"]``) → scorer cell-key spelling."""


class BondAffinityReadError(RuntimeError):
    """A capture could not be read (missing sidecar, unreadable DuckDB).

    A genuinely unreadable input is loud-not-silent; matrix *incompleteness*
    (missing / duplicate / role-swapped key) is **not** raised here — that is an
    assembler verdict (``INVALID_MEASUREMENT`` from
    :func:`~erre_sandbox.evidence.relational.loader.score_bond_affinity_captures`),
    so the sidecar's matrix keys are passed straight through (possibly ``None``) for
    the assembler / scorer to adjudicate.
    """


@dataclass(frozen=True, slots=True)
class BondAffinityCapture:
    """One capture's matrix identity + the two raw traces the scorer reads.

    ``arm`` is the **normalised** scorer spelling (``"ON"`` / ``"OFF"``), or ``None``
    for a capture that does not carry the arm (stimulus, flag-off natural, pre-live-§5.3
    sidecar). ``seed`` / ``replicate_id`` flow verbatim from the sidecar.
    """

    path: str
    seed: int | None
    arm: str | None
    replicate_id: int | None
    bond_rows: tuple[BondAffinityTraceRow, ...]
    saturation_rows: tuple[SaturationTraceRow, ...]


def read_bond_capture(
    duckdb_path: Path | str, *, schema: str = METRICS_SCHEMA
) -> BondAffinityCapture:
    """Open one capture read-only and assemble its sidecar identity + raw traces.

    The sidecar's matrix keys (``seed`` / ``stm_carry_arm`` / ``replicate_id``) are
    passed through — ``stm_carry_arm`` normalised to ``"ON"`` / ``"OFF"`` (``None`` for
    a non-arm capture) — so the assembler / scorer routes any incomplete matrix to
    ``INVALID_MEASUREMENT``. Raises :class:`BondAffinityReadError` only when the capture
    itself cannot be read (missing sidecar, unreadable DuckDB, unreadable trace).
    """
    path = Path(duckdb_path)
    try:
        sidecar = read_sidecar(sidecar_path_for(path))
    except (OSError, ValueError) as exc:
        msg = f"could not read sidecar for capture {path}: {exc}"
        raise BondAffinityReadError(msg) from exc
    try:
        con = duckdb.connect(str(path), read_only=True)
    except duckdb.Error as exc:
        msg = f"could not open capture DuckDB {path}: {exc}"
        raise BondAffinityReadError(msg) from exc
    try:
        bond_rows = tuple(read_bond_affinity_trace_rows(con, schema=schema))
        saturation_rows = tuple(read_saturation_trace_rows(con, schema=schema))
    except duckdb.Error as exc:
        msg = f"could not read traces from capture {path}: {exc}"
        raise BondAffinityReadError(msg) from exc
    finally:
        con.close()
    arm = (
        None if sidecar.stm_carry_arm is None else _ARM_NORMALISE[sidecar.stm_carry_arm]
    )
    return BondAffinityCapture(
        path=str(path),
        seed=sidecar.seed,
        arm=arm,
        replicate_id=sidecar.replicate_id,
        bond_rows=bond_rows,
        saturation_rows=saturation_rows,
    )


__all__ = [
    "BondAffinityCapture",
    "BondAffinityReadError",
    "read_bond_capture",
]
