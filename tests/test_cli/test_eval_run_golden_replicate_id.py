"""III-a live §5.3 ``--replicate-id`` CLI wiring + sidecar provenance (ADR §0/§3).

CPU-only / offline. Three tiers:

1. **Fail-fast** — ``--replicate-id`` without ``--individual-layer on`` (and with the
   stimulus condition) is rejected by ``main`` with argparse exit code 2 before any
   capture begins (``_validate_replicate_id``).
2. **Sidecar provenance** — ``_publish_capture`` records ``replicate_id`` only for an
   arm-bearing capture (natural + individual layer on); ``None`` for a flag-off natural
   or a stimulus capture.
3. **Backward compatibility** — a pre-live-§5.3 sidecar JSON lacking ``replicate_id``
   still validates (``extra="allow"``) with ``replicate_id == None``.
"""

from __future__ import annotations

import argparse
import json
from typing import TYPE_CHECKING

import pytest

import erre_sandbox.cli.eval_run_golden as eg
from erre_sandbox.cli.eval_run_golden import CaptureResult
from erre_sandbox.evidence.capture_sidecar import (
    SidecarV1,
    read_sidecar,
    sidecar_path_for,
    write_sidecar_atomic,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pathlib import Path


# ---------------------------------------------------------------------------
# Tier 1: fail-fast on a contradictory --replicate-id combination
# ---------------------------------------------------------------------------


def test_replicate_id_without_individual_layer_fails_fast(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        eg.main(
            [
                "--persona",
                "kant",
                "--run-idx",
                "0",
                "--condition",
                "natural",
                "--output",
                str(tmp_path / "o.duckdb"),
                "--individual-layer",
                "off",
                "--replicate-id",
                "0",
            ]
        )
    assert exc.value.code == 2


def test_replicate_id_with_stimulus_fails_fast(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        eg.main(
            [
                "--persona",
                "kant",
                "--run-idx",
                "0",
                "--condition",
                "stimulus",
                "--output",
                str(tmp_path / "o.duckdb"),
                "--replicate-id",
                "1",
            ]
        )
    assert exc.value.code == 2


def test_replicate_id_rejects_out_of_domain(tmp_path: Path) -> None:
    """argparse ``choices=(0, 1)`` rejects a replicate index outside the domain."""
    with pytest.raises(SystemExit) as exc:
        eg.main(
            [
                "--persona",
                "kant",
                "--run-idx",
                "0",
                "--condition",
                "natural",
                "--output",
                str(tmp_path / "o.duckdb"),
                "--individual-layer",
                "on",
                "--stm-carry-arm",
                "on",
                "--replicate-id",
                "2",
            ]
        )
    assert exc.value.code == 2


# ---------------------------------------------------------------------------
# Tier 2: _publish_capture records replicate_id only for an arm-bearing capture
# ---------------------------------------------------------------------------


def _publish(
    tmp_path: Path,
    *,
    condition: str,
    individual_layer: str,
    stm_carry_arm: str = "off",
    replicate_id: int | None = 0,
) -> Path:
    args = argparse.Namespace(
        turn_count=1,
        wall_timeout_min=1.0,
        persona="kant",
        condition=condition,
        run_idx=0,
        individual_layer=individual_layer,
        stm_carry_arm=stm_carry_arm,
        replicate_id=replicate_id,
        compute_individuation=False,
    )
    final = tmp_path / "o.duckdb"
    temp = tmp_path / "o.duckdb.tmp"
    temp.write_text("x", encoding="utf-8")
    result = CaptureResult(
        run_id="kant_natural_run0",
        output_path=final,
        total_rows=1,
        focal_rows=1,
        seed=4242,
        seed_salt="m9-eval-v1",
    )
    rc = eg._publish_capture(args, result, temp, final)
    assert rc == 0
    return final


def test_publish_records_replicate_id_for_arm_bearing_capture(tmp_path: Path) -> None:
    final = _publish(
        tmp_path,
        condition="natural",
        individual_layer="on",
        stm_carry_arm="on",
        replicate_id=1,
    )
    sidecar = read_sidecar(sidecar_path_for(final))
    assert sidecar.replicate_id == 1
    assert sidecar.stm_carry_arm == "on"
    assert sidecar.seed == 4242


def test_publish_omits_replicate_id_for_flag_off_natural(tmp_path: Path) -> None:
    final = _publish(
        tmp_path, condition="natural", individual_layer="off", replicate_id=0
    )
    sidecar = read_sidecar(sidecar_path_for(final))
    assert sidecar.replicate_id is None


def test_publish_omits_replicate_id_for_stimulus(tmp_path: Path) -> None:
    final = _publish(
        tmp_path, condition="stimulus", individual_layer="off", replicate_id=0
    )
    sidecar = read_sidecar(sidecar_path_for(final))
    assert sidecar.replicate_id is None


# ---------------------------------------------------------------------------
# Tier 3: backward compatibility — a pre-live-§5.3 sidecar lacks replicate_id
# ---------------------------------------------------------------------------


def test_old_sidecar_without_replicate_id_validates_to_none(tmp_path: Path) -> None:
    payload = SidecarV1(
        status="complete",
        stop_reason="complete",
        focal_target=1,
        focal_observed=1,
        total_rows=1,
        wall_timeout_min=1.0,
        drain_completed=True,
        runtime_drain_timeout=False,
        git_sha="abc1234",
        captured_at="2026-06-16T00:00:00Z",
        persona="kant",
        condition="natural",
        run_idx=0,
        duckdb_path=str(tmp_path / "o.duckdb"),
    )
    path = tmp_path / "o.duckdb.capture.json"
    write_sidecar_atomic(path, payload)
    # Simulate a pre-live-§5.3 file: strip replicate_id from the JSON on disk.
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw.pop("replicate_id", None)
    path.write_text(json.dumps(raw), encoding="utf-8")

    sidecar = read_sidecar(path)
    assert sidecar.replicate_id is None
