"""U4 fork III-a paired-arm CLI wiring: ``--stm-carry-arm`` flag + sidecar provenance.

CPU-only / offline. Three tiers:

1. **Wiring** — ``--stm-carry-arm on`` reaches
   ``IndividualLayerConfig.stm_carry_enabled=True`` (and ``off`` keeps it False) via the
   ``capture_natural`` call ``_async_main`` makes. ``capture_natural`` /
   ``_publish_capture`` are spied so no Ollama / DuckDB is touched.
2. **Fail-fast** — ``--stm-carry-arm on`` without ``--individual-layer on`` (and with
   the stimulus condition) is rejected by ``main`` with argparse exit code 2 before any
   capture begins.
3. **Sidecar provenance** — ``_publish_capture`` records ``stm_carry_arm`` only for an
   arm-bearing capture (natural + individual layer on) and the actual ``seed`` /
   ``seed_salt`` for every capture.
"""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING, Any

import pytest

import erre_sandbox.cli.eval_run_golden as eg
from erre_sandbox.cli.eval_run_golden import CaptureResult
from erre_sandbox.evidence.capture_sidecar import read_sidecar, sidecar_path_for

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pathlib import Path


# ---------------------------------------------------------------------------
# Tier 1: --stm-carry-arm -> IndividualLayerConfig.stm_carry_enabled wiring
# ---------------------------------------------------------------------------


def _spy_natural_main(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Spy ``capture_natural`` + no-op ``_publish_capture``; return captured kwargs."""
    captured: dict[str, Any] = {}

    async def _spy_capture_natural(**kwargs: Any) -> CaptureResult:
        captured.update(kwargs)
        return CaptureResult(
            run_id="kant_natural_run0",
            output_path=kwargs["temp_path"],
            total_rows=1,
            focal_rows=1,
        )

    monkeypatch.setattr(eg, "capture_natural", _spy_capture_natural)
    monkeypatch.setattr(eg, "_publish_capture", lambda *_a, **_k: 0)
    return captured


def _natural_argv(tmp_path: Path, *, arm: str) -> list[str]:
    return [
        "--persona",
        "kant",
        "--run-idx",
        "0",
        "--condition",
        "natural",
        "--turn-count",
        "1",
        "--output",
        str(tmp_path / "o.duckdb"),
        "--individual-layer",
        "on",
        "--stm-carry-arm",
        arm,
    ]


def test_stm_carry_arm_on_wires_stm_carry_enabled_true(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = _spy_natural_main(monkeypatch)
    rc = eg.main(_natural_argv(tmp_path, arm="on"))
    assert rc == 0
    layer = captured["individual_layer"]
    assert layer is not None
    assert layer.enabled is True
    assert layer.stm_carry_enabled is True


def test_stm_carry_arm_off_keeps_stm_carry_enabled_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = _spy_natural_main(monkeypatch)
    rc = eg.main(_natural_argv(tmp_path, arm="off"))
    assert rc == 0
    layer = captured["individual_layer"]
    assert layer is not None
    assert layer.enabled is True
    assert layer.stm_carry_enabled is False


# ---------------------------------------------------------------------------
# Tier 2: fail-fast on a contradictory --stm-carry-arm combination
# ---------------------------------------------------------------------------


def test_stm_carry_arm_on_without_individual_layer_fails_fast(
    tmp_path: Path,
) -> None:
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
                "--stm-carry-arm",
                "on",
            ]
        )
    assert exc.value.code == 2


def test_stm_carry_arm_on_with_stimulus_fails_fast(tmp_path: Path) -> None:
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
                "--stm-carry-arm",
                "on",
            ]
        )
    assert exc.value.code == 2


# ---------------------------------------------------------------------------
# Tier 3: _publish_capture records arm + seed provenance into the sidecar
# ---------------------------------------------------------------------------


def _publish(
    tmp_path: Path,
    *,
    condition: str,
    individual_layer: str,
    stm_carry_arm: str,
    seed: int | None = 4242,
    seed_salt: str | None = "m9-eval-v1",
) -> Path:
    args = argparse.Namespace(
        turn_count=1,
        wall_timeout_min=1.0,
        persona="kant",
        condition=condition,
        run_idx=0,
        individual_layer=individual_layer,
        stm_carry_arm=stm_carry_arm,
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
        seed=seed,
        seed_salt=seed_salt,
    )
    rc = eg._publish_capture(args, result, temp, final)
    assert rc == 0
    return final


def test_publish_records_arm_for_arm_bearing_capture(tmp_path: Path) -> None:
    final = _publish(
        tmp_path, condition="natural", individual_layer="on", stm_carry_arm="on"
    )
    sidecar = read_sidecar(sidecar_path_for(final))
    assert sidecar.stm_carry_arm == "on"
    assert sidecar.seed == 4242
    assert sidecar.seed_salt == "m9-eval-v1"


def test_publish_omits_arm_for_flag_off_natural(tmp_path: Path) -> None:
    final = _publish(
        tmp_path, condition="natural", individual_layer="off", stm_carry_arm="off"
    )
    sidecar = read_sidecar(sidecar_path_for(final))
    assert sidecar.stm_carry_arm is None
    # seed provenance is still recorded for every capture.
    assert sidecar.seed == 4242


def test_publish_omits_arm_for_stimulus(tmp_path: Path) -> None:
    final = _publish(
        tmp_path, condition="stimulus", individual_layer="off", stm_carry_arm="off"
    )
    sidecar = read_sidecar(sidecar_path_for(final))
    assert sidecar.stm_carry_arm is None
