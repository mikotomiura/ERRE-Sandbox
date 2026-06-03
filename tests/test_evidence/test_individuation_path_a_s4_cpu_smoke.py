"""M10-A S4 GPU smoke wiring: CPU-offline smoke subset (G0-1/3/4/6 + BLOCKED G0-2/5).

Exercises the harness gates on synthetic population captures (CPU, no GPU / model) and
pins the two review-mandated invariants: a ``BLOCKED_GPU`` gate is never a PASS, and
``cpu_subset_pass`` is not full-gate authorization (``full_gate_authorized`` stays False
while G0-2/5 are outstanding).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from erre_sandbox.evidence.individuation.path_a_s4_cpu_smoke import (
    SmokeGateStatus,
    g0_1_launcher_health,
    g0_2_inference_backend,
    g0_3_density_instrumentation,
    g0_4_h2_verdict_path,
    g0_5_provenance_db_column,
    g0_6_admission_invariance,
    run_cpu_smoke_gates,
)
from erre_sandbox.evidence.individuation.path_a_s4_runner import run_s4_decision
from tests.test_evidence.test_individuation_path_a_s4_runner import _captures, _ctx

if TYPE_CHECKING:
    from pathlib import Path


def test_g0_1_launcher_health_pass() -> None:
    result = g0_1_launcher_health("kant", world_size=21)
    assert result.status is SmokeGateStatus.PASS


def test_g0_1_launcher_health_fail_on_bad_persona() -> None:
    result = g0_1_launcher_health("not-a-persona", world_size=21)
    assert result.status is SmokeGateStatus.FAIL


def test_g0_3_density_instrumentation_computes(tmp_path: Path) -> None:
    captures = _captures(tmp_path, densities=(20, 20, 20))
    s4 = run_s4_decision(
        captures, focal_persona="kant", experiment_run_id="c", ctx=_ctx(tmp_path)
    )
    result = g0_3_density_instrumentation(s4)
    assert result.status is SmokeGateStatus.PASS


def test_g0_3_fails_on_short_capture_set(tmp_path: Path) -> None:
    """A 2-capture set must FAIL G0-3 (⑤ N=3, Codex MED-1).

    ``run_s4_decision`` completes on 2 captures (the gate matrix is INVALID), so the
    density instrumentation gate is what catches the capture-count shortfall.
    """
    captures = _captures(tmp_path, densities=(20, 20, 20))[:2]
    s4 = run_s4_decision(
        captures, focal_persona="kant", experiment_run_id="c", ctx=_ctx(tmp_path)
    )
    result = g0_3_density_instrumentation(s4)
    assert result.status is SmokeGateStatus.FAIL


def test_g0_4_h2_verdict_path(tmp_path: Path) -> None:
    captures = _captures(tmp_path, densities=(20, 20, 20))
    s4 = run_s4_decision(
        captures, focal_persona="kant", experiment_run_id="c", ctx=_ctx(tmp_path)
    )
    result = g0_4_h2_verdict_path(s4)
    assert result.status is SmokeGateStatus.PASS


def test_g0_6_admission_invariance_pass() -> None:
    result = g0_6_admission_invariance()
    assert result.status is SmokeGateStatus.PASS


def test_gpu_gates_are_blocked_not_pass() -> None:
    """A BLOCKED_GPU gate is its own status, never PASS (review point 2)."""
    for result in (g0_2_inference_backend(), g0_5_provenance_db_column()):
        assert result.status is SmokeGateStatus.BLOCKED_GPU
        assert result.status is not SmokeGateStatus.PASS


def test_run_cpu_smoke_gates_subset_pass_not_full_authorization(tmp_path: Path) -> None:
    captures = _captures(tmp_path, densities=(20, 20, 20))
    report = run_cpu_smoke_gates(
        captures, focal_persona="kant", experiment_run_id="c", ctx=_ctx(tmp_path)
    )
    # The four CPU gates pass...
    assert report.cpu_subset_pass is True
    # ...but the GPU gates are outstanding, so the full gate is NOT authorized.
    assert report.full_gate_authorized is False
    assert set(report.blocked_gpu_gates) == {"G0-2", "G0-5"}
    # BLOCKED_GPU gates are excluded from the CPU subset, never counted as PASS.
    blocked = [g for g in report.gates if g.status is SmokeGateStatus.BLOCKED_GPU]
    assert len(blocked) == 2
    assert all(g.status is not SmokeGateStatus.PASS for g in blocked)
