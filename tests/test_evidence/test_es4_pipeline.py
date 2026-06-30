"""M13-ES4 end-to-end pipeline smoke under the deterministic mock seams.

Proves the whole apparatus (reference → score → decompose → controls → verdict)
runs LLM-free through the injectable seams and is byte-reproducible. The mock
verdict is a **plumbing** smoke, not a scientific result — so it is not asserted to
any particular value, only to be a member of the frozen vocabulary and identical
across runs.
"""

from __future__ import annotations

from dataclasses import asdict

from erre_sandbox.evidence.es4_actuator.mock_seams import (
    mock_encode,
    mock_inference,
    mock_judge,
    mock_score,
)
from erre_sandbox.evidence.es4_actuator.pipeline import run_phase
from erre_sandbox.evidence.es4_actuator.verdict_report import Verdict

_VOCAB = {
    "INVALID_SCORER",
    "INVALID_TASK_BATTERY",
    "NO_GO_EFFECT_ABSENT",
    "INCONCLUSIVE_UNDERPOWERED",
    "PASS",
    "GO",
}


def _run(phase: str):
    return run_phase(
        phase,  # type: ignore[arg-type]
        inference_fn=mock_inference,
        encoder_fn=mock_encode,
        judge_fn=mock_judge,
        score_fn=mock_score,
        projected_gpu_hours=0.0,
        bootstrap_seed=0,
    )


def test_phase0_mock_runs_and_is_in_vocab() -> None:
    v = _run("phase0")
    assert v.phase == "phase0"
    assert v.verdict in _VOCAB


def test_phase1_mock_runs_and_is_in_vocab() -> None:
    v = _run("phase1")
    assert v.phase == "phase1"
    assert v.verdict in _VOCAB


def test_mock_run_is_deterministic() -> None:
    assert asdict(_run("phase0")) == asdict(_run("phase0"))


def test_verdict_vocab_is_frozen_five_plus_pass_go() -> None:
    assert set(Verdict.__args__) == _VOCAB  # type: ignore[attr-defined]
