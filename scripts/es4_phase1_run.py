"""Run the M13-ES4 **Phase 1** full verdict (Session 1 = mock smoke).

Phase 1 runs **only after a Phase 0 PASS** (``design-final.md`` §4.2 / §8) with
every constant frozen. The INCONCLUSIVE-first conjunctive verdict renders one of
the five vocabulary outcomes; **GO = actuator sufficiency only** (over-claim guard
§9), never "walking → divergence" nor a re-proof of the closed-loop core thesis.

**Session 1 scope**: like the Phase 0 script, this is a deterministic LLM-free
mock smoke through :mod:`erre_sandbox.evidence.es4_actuator.mock_seams` — it proves
the Phase 1 pipeline executes end-to-end and emits a verdict JSON. Session 2/3
swap in the real backend and run the GPU Phase 1.

Usage::

    uv run python scripts/es4_phase1_run.py
    uv run python scripts/es4_phase1_run.py --out path.json
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
    "SESSION-1 MOCK SMOKE: deterministic LLM-free mock seams (mock_seams). The "
    "verdict is a PLUMBING smoke, NOT a scientific result. Phase 1 may run only "
    "after a real Phase 0 PASS (Session 2). Session 2/3 swap in the real SGLang "
    "fp8 qwen3:8b backend + MPNet encoder + qwen judge.",
    "GO = ACTUATOR SUFFICIENCY ONLY (design-final §9): qwen3:8b frozen decoding, "
    "locomotion->temperature (gain_p=0) moves output into a divergent-favouring "
    "regime (on-task rarity up). Because locomotion is the ONLY temperature "
    "channel, no locomotion-specific divergence beyond temperature is claimed "
    "(A2 == M2 distribution-matched equivalence makes this explicit). DQ is named "
    "appropriateness-gated divergent-quality (rarity), never 'originality'.",
    "forking-paths seal (design-final §5): floors / MDE / bands / gains frozen; "
    "the 5-vocabulary verdict is recorded as-is (INVALID_* / "
    "INCONCLUSIVE_UNDERPOWERED / NO_GO_EFFECT_ABSENT / GO).",
)


def _forensic(verdict: Es4Verdict) -> dict[str, Any]:
    d = asdict(verdict)
    d["caveats"] = list(_CAVEATS)
    return d


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="M13-ES4 Phase 1 (Session 1 mock smoke)"
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
        "phase1",
        inference_fn=mock_inference,
        encoder_fn=mock_encode,
        judge_fn=mock_judge,
        score_fn=mock_score,
    )
    payload = _forensic(verdict)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(f"[es4-phase1 MOCK SMOKE] verdict = {verdict.verdict}\n")
    sys.stdout.write(f"  reasons: {verdict.reasons}\n")
    sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
