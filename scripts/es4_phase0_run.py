"""Run the M13-ES4 **Phase 0** feasibility/power gate.

Phase 0 is the binary gate (``design-final.md`` §4.1): apparatus validity, scorer
non-tautology, battery validity, effect-absence (strong upper-CI evidence) and
power/budget feasibility decide one of the five vocabulary outcomes; **PASS**
licenses the frozen Phase 1.

Two backends:

* ``--backend mock`` (default) — the deterministic LLM-free mock seams
  (:mod:`erre_sandbox.evidence.es4_actuator.mock_seams`): a **plumbing smoke** that
  proves the apparatus runs end-to-end and emits a verdict JSON (Session 1).
* ``--backend real`` — the SGLang fp8 ``qwen3:8b`` backend + MPNet encoder
  (Session 2), in two phases (ADR §7 phase-flip):

  * ``--phase A`` — generate + judge + adversarial-score everything and persist to
    ``--run-dir`` (SGLang up). Stop SGLang afterwards.
  * ``--phase B`` — replay the persisted Phase-A outputs + the live MPNet encoder
    through the unchanged pipeline → verdict JSON (SGLang down).
  * ``--phase full`` — A then B in one process (encoder coexists; use for the
    smoke, not the budget-measured real run).

``--smoke`` (real only) runs a tiny subset through every live seam to verify the
wiring (server boot / think-suppression / seed / judge / score / encoder /
persistence). A smoke verdict / output is **NOT** a scientific Phase 0 result.

Usage::

    uv run python scripts/es4_phase0_run.py                    # mock smoke
    # real wiring smoke (tiny subset through every live seam):
    python scripts/es4_phase0_run.py --backend real --smoke --run-dir <dir>
    # real Phase A (deferred budget-measured run) then Phase B:
    python scripts/es4_phase0_run.py --backend real --phase A --run-dir <dir>
    python scripts/es4_phase0_run.py --backend real --phase B --run-dir <dir> \
        --out verdict.json
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
    from collections.abc import Callable

    from erre_sandbox.evidence.es4_actuator.scenario import (
        GenerationRequest,
    )
    from erre_sandbox.evidence.es4_actuator.verdict_report import (
        Es4Verdict,
    )

_CAVEATS: Final[tuple[str, ...]] = (
    "claim boundary (design-final §0/§9): a GO (Phase 1) means ACTUATOR "
    "SUFFICIENCY (qwen3:8b frozen decoding: locomotion->temperature moves output "
    "into a divergent-favouring regime, on-task rarity up), NOT walking->creative "
    "divergence and NOT a re-proof of the closed-loop core thesis.",
    "forking-paths seal (design-final §5): the floors / MDE / bands / gains are "
    "frozen; whatever verdict (5 vocabulary) comes out is recorded as-is. "
    "INCONCLUSIVE_UNDERPOWERED and INVALID_* are kept distinct from "
    "NO_GO_EFFECT_ABSENT (ES-2/ES-3 discipline).",
)
_MOCK_CAVEAT: Final[str] = (
    "MOCK SMOKE: deterministic LLM-free mock seams (mock_seams). The verdict here "
    "is a PLUMBING smoke (apparatus runs end-to-end and emits JSON), NOT a "
    "scientific Phase 0 result."
)
_SMOKE_CAVEAT: Final[str] = (
    "REAL WIRING SMOKE: a tiny subset through the live SGLang + MPNet seams to "
    "verify wiring only. NOT a scientific Phase 0 result (frozen N is not met)."
)
_SMOKE_MAX_ADVERSARIAL: Final[int] = 8


def _stdout_utf8() -> None:
    if hasattr(sys.stdout, "reconfigure"):  # Δ / ≥ in reasons on a cp932 console
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]


def _forensic(verdict: Es4Verdict, *extra_caveats: str) -> dict[str, Any]:
    d = asdict(verdict)
    d["caveats"] = [*extra_caveats, *_CAVEATS]
    return d


def _emit(verdict: Es4Verdict, payload: dict[str, Any], out: Path | None) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    sys.stdout.write(f"[es4-phase0] verdict = {verdict.verdict}\n")
    sys.stdout.write(f"  reasons: {verdict.reasons}\n")
    sys.stdout.write(text + "\n")


def _run_mock(out: Path | None) -> int:
    verdict = run_phase(
        "phase0",
        inference_fn=mock_inference,
        encoder_fn=mock_encode,
        judge_fn=mock_judge,
        score_fn=mock_score,
        projected_gpu_hours=0.0,
    )
    _emit(verdict, _forensic(verdict, _MOCK_CAVEAT), out)
    return 0


def _smoke_filter() -> Callable[[GenerationRequest], bool]:
    from erre_sandbox.evidence.es4_actuator.battery import (  # noqa: PLC0415
        load_aut_battery,
        load_rat_battery,
    )

    first_obj = load_aut_battery().items[0].object_id
    first_rat = load_rat_battery().items[0].item_id

    def keep(req: GenerationRequest) -> bool:
        if req.task == "rat":
            return req.item_id == first_rat and req.seed_idx == 0
        if req.condition == "REF":
            return req.item_id == first_obj and req.seed_idx < 2  # noqa: PLR2004
        return (
            req.persona_id == "kant"
            and req.item_id == first_obj
            and req.condition in {"A0", "A2"}
            and req.seed_idx == 0
        )

    return keep


def _run_real_smoke(endpoint: str, run_dir: Path) -> int:
    from erre_sandbox.evidence.es4_actuator.backend import (  # noqa: PLC0415
        SglangBackend,
        load_phase_a,
        make_mpnet_encoder,
        run_phase_a,
    )

    backend = SglangBackend(endpoint=endpoint)
    sys.stdout.write(f"[es4-smoke] health-checking SGLang at {endpoint} ...\n")
    backend.health_check()
    manifest = run_phase_a(
        backend.inference,
        backend.judge,
        backend.score,
        run_dir,
        "phase0",
        smoke_filter=_smoke_filter(),
        max_adversarial=_SMOKE_MAX_ADVERSARIAL,
        overwrite=True,
        extra_manifest={"endpoint": endpoint, "kind": "real-wiring-smoke"},
    )
    data = load_phase_a(run_dir)
    sys.stdout.write(
        f"[es4-smoke] manifest: {json.dumps(manifest, ensure_ascii=False)}\n"
    )
    sample_gen = next(iter(data.responses.items()), ("<none>", ""))
    sys.stdout.write(
        f"[es4-smoke] sample generation [{sample_gen[0]}]:\n{sample_gen[1]}\n"
    )
    sys.stdout.write(
        f"[es4-smoke] judgements (first 5): {list(data.judgements.items())[:5]}\n"
    )
    sys.stdout.write(f"[es4-smoke] scores (first 5): {list(data.scores.items())[:5]}\n")

    sys.stdout.write("[es4-smoke] loading MPNet encoder (CPU) ...\n")
    encode = make_mpnet_encoder()
    ideas = [idea for (_obj, idea) in list(data.judgements)[:4]] or ["a brick doorstop"]
    emb = encode(ideas)
    sys.stdout.write(f"[es4-smoke] encoded {len(ideas)} ideas -> shape {emb.shape}\n")
    sys.stdout.write(f"[es4-smoke] CAVEAT: {_SMOKE_CAVEAT}\n")
    sys.stdout.write("[es4-smoke] WIRING OK (all live seams + persistence + encoder)\n")
    return 0


def _run_real_phase_a(endpoint: str, run_dir: Path) -> int:
    from erre_sandbox.evidence.es4_actuator.backend import (  # noqa: PLC0415
        SglangBackend,
        run_phase_a,
    )

    backend = SglangBackend(endpoint=endpoint)
    backend.health_check()
    manifest = run_phase_a(
        backend.inference,
        backend.judge,
        backend.score,
        run_dir,
        "phase0",
        extra_manifest={"endpoint": endpoint, "kind": "real-phase-a"},
    )
    sys.stdout.write(f"[es4-phaseA] persisted to {run_dir}\n")
    sys.stdout.write(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return 0


def _run_real_phase_b(run_dir: Path, out: Path | None) -> int:
    from erre_sandbox.evidence.es4_actuator.backend import (  # noqa: PLC0415
        make_mpnet_encoder,
        run_phase_b,
    )

    # projected_gpu_hours=None → total-inclusive Phase-0 budget (Codex HIGH-5).
    verdict, misses, extras = run_phase_b(run_dir, make_mpnet_encoder())
    if not misses.all_zero:
        sys.stdout.write(f"[es4-phaseB] ERROR replay misses: {vars(misses)}\n")
        return 2
    payload = _forensic(verdict)
    payload["extras"] = extras
    _emit(verdict, payload, out)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M13-ES4 Phase 0")
    parser.add_argument("--backend", choices=("mock", "real"), default="mock")
    parser.add_argument("--phase", choices=("A", "B", "full"), default="full")
    parser.add_argument("--smoke", action="store_true", help="real wiring smoke")
    parser.add_argument("--endpoint", default="http://127.0.0.1:30000")
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None, help="write forensic JSON")
    args = parser.parse_args(argv)
    _stdout_utf8()

    if args.backend == "mock":
        return _run_mock(args.out)

    if args.run_dir is None:
        parser.error("--backend real requires --run-dir")
    if args.smoke:
        return _run_real_smoke(args.endpoint, args.run_dir)
    # Codex HIGH-4: the budget-measured real run must go A → stop server → B; a
    # single-process `full` would bypass the phase-flip, so it is rejected.
    if args.phase == "A":
        return _run_real_phase_a(args.endpoint, args.run_dir)
    if args.phase == "B":
        return _run_real_phase_b(args.run_dir, args.out)
    parser.error("--backend real requires --phase A or B (full bypasses phase-flip)")
    return 2  # unreachable (parser.error exits)


if __name__ == "__main__":
    raise SystemExit(main())
