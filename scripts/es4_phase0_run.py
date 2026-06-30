"""Run the M13-ES4 **Phase 0** feasibility/power gate (Session 1 = mock smoke).

Phase 0 is the binary gate (``design-final.md`` §4.1): apparatus validity, scorer
non-tautology, battery validity, effect-absence (strong upper-CI evidence) and
power/budget feasibility decide one of the five vocabulary outcomes; **PASS**
licenses the frozen Phase 1.

**Session 1 scope**: this CLI runs the *whole* pipeline through the deterministic
LLM-free mock seams (:mod:`erre_sandbox.evidence.es4_actuator.mock_seams`) — a
**plumbing smoke** that proves the apparatus executes end-to-end and emits a
verdict JSON, **not** a scientific Phase 0 result. Session 2 replaces the seams
with the real SGLang fp8 qwen3:8b backend + MPNet encoder + qwen judge and runs
the actual GPU Phase 0; nothing else about the apparatus changes.

Usage::

    uv run python scripts/es4_phase0_run.py            # mock smoke → prints verdict
    uv run python scripts/es4_phase0_run.py --out path.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from erre_sandbox.evidence.es4_actuator.mock_seams import (
    mock_encode,
    mock_inference,
    mock_judge,
    mock_score,
)
from erre_sandbox.evidence.es4_actuator.pipeline import run_phase

if TYPE_CHECKING:
    from erre_sandbox.evidence.es4_actuator.verdict_report import Es4Verdict

_CAVEATS: Final[tuple[str, ...]] = (
    "SESSION-1 MOCK SMOKE: the seams are deterministic LLM-free mocks "
    "(mock_seams). The verdict here is a PLUMBING smoke (the apparatus runs "
    "end-to-end and emits JSON), NOT a scientific Phase 0 result. Session 2 swaps "
    "the seams for the real SGLang fp8 qwen3:8b backend + MPNet encoder + qwen "
    "judge and runs the GPU Phase 0.",
    "claim boundary (design-final §0/§9): a GO (Phase 1) means ACTUATOR "
    "SUFFICIENCY (qwen3:8b frozen decoding: locomotion->temperature moves output "
    "into a divergent-favouring regime, on-task rarity up), NOT walking->creative "
    "divergence and NOT a re-proof of the closed-loop core thesis.",
    "forking-paths seal (design-final §5): the floors / MDE / bands / gains are "
    "frozen; whatever verdict (5 vocabulary) comes out is recorded as-is. "
    "INCONCLUSIVE_UNDERPOWERED and INVALID_* are kept distinct from "
    "NO_GO_EFFECT_ABSENT (ES-2/ES-3 discipline).",
)


def _forensic(verdict: Es4Verdict) -> dict[str, Any]:
    d = asdict(verdict)
    d["caveats"] = list(_CAVEATS)
    return d


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="M13-ES4 Phase 0 (Session 1 mock smoke)"
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="write forensic JSON here"
    )
    args = parser.parse_args(argv)

    if hasattr(
        sys.stdout, "reconfigure"
    ):  # UTF-8 console (Δ / ≥ in reasons, win cp932)
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    verdict = run_phase(
        "phase0",
        inference_fn=mock_inference,
        encoder_fn=mock_encode,
        judge_fn=mock_judge,
        score_fn=mock_score,
        projected_gpu_hours=0.0,
    )
    payload = _forensic(verdict)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(f"[es4-phase0 MOCK SMOKE] verdict = {verdict.verdict}\n")
    sys.stdout.write(f"  reasons: {verdict.reasons}\n")
    sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
